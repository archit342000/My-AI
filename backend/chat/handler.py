import asyncio
import json
import time
import logging
from typing import List, Dict, Any, Optional, AsyncGenerator

from backend.utils import merge_tool_call_deltas

from backend.inference import InferenceEngine
from .turn_handler import TurnHandler
from .agent_handler import AgentHandler
from .tool_handler import ToolHandler
from backend.chat.models import SSEEvent, SSEEventType
from backend.database import db, response_cache
from backend.logging import log_event
from backend.task_manager import task_manager
from backend import config

logger = logging.getLogger(__name__)

THINKING_PROFILES = {
    "none": {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "min_p": 0.0, "presence_penalty": 1.5, "frequency_penalty": 1.0, "enable_thinking": False},
    "general": {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.0, "presence_penalty": 1.5, "frequency_penalty": 1.0, "enable_thinking": True},
    "precision": {"temperature": 0.6, "top_p": 0.95, "top_k": 20, "min_p": 0.0, "presence_penalty": 0.0, "frequency_penalty": 1.0, "enable_thinking": True}
}

class ChatHandler:
    """
    Handles the high-level chat flow logic.
    Coordinates between the Inference Engine, the Cache System, and the Database.
    """

    def __init__(self, chat_id: str):
        self.chat_id = chat_id
        self.engine = InferenceEngine()
        self.cache = response_cache
        self.tool_handler = ToolHandler(self.chat_id, self)
        self.chunk_index = 0
        # ── Soft Rejection State ──
        self._pending_confirmation = None      # Dict with stored TC details, or None
        self._validation_bypass_next = False   # Skip validation on next FS agent call
        # The chat's numbered sources: loaded by `_run_background_turn` for a main turn; sub-agents' handlers keep None
        self.source_registry = None

    def get_history(self) -> Dict[str, Any]:
        """
        Retrieves the full message history and determines if the chat was interrupted.
        Returns: {"messages": List[Dict], "resume_needed": bool}
        """
        # Use woven history for full turn-anchored reconstruction
        messages = db.get_woven_history(self.chat_id)
        
        chat_metadata = db.get_chat(self.chat_id) or {}
        
        # 2. Check for interruption (Resumption Logic)
        resume_needed = False
        is_running = task_manager.is_task_running(self.chat_id)
        
        if not is_running and messages:
            last_msg = messages[-1]
            role = last_msg.get('role')
            
            # 1. User message -> Interrupted (needs initial AI response)
            if role == 'user':
                resume_needed = True
            # 2. Assistant message with tool calls -> Interrupted (needs tool execution)
            elif role == 'assistant' and last_msg.get('tool_calls'):
                resume_needed = True
            # 3. Tool message -> Interrupted (needs AI follow-up to the result)
            elif role == 'tool':
                resume_needed = True

        # Sub-agent-level detection: if research_state is 'ongoing' but
        # nothing is running, the sub-agent was interrupted mid-execution
        research_state = chat_metadata.get('research_state', 'none')
        if research_state in ('ongoing', 'failed') and not is_running:
            resume_needed = True

        # Suppression: if the user explicitly stopped, don't show the banner
        if chat_metadata.get('resume_suppressed'):
            resume_needed = False
                
        return {
            **chat_metadata,
            "messages": messages,
            "resume_needed": resume_needed,
            "is_running": is_running,
            "research_state": research_state,
        }

    async def initiate_chat(
        self, 
        files: Optional[List[Dict]] = None, 
        user_message: Optional[Dict] = None,
        model: str = "gpt-4o",
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Initiates or continues a chat session.
        
        Point 2: If files are provided without a message, stores them and returns.
        Point 3: If a message is provided, triggers the inference engine.
        """
        # Routes create (or refuse) the chat before a handler runs, so the handler only checks that it exists.
        owner = db.get_chat_owner(self.chat_id)
        if owner is None:
            raise ValueError(f"Chat {self.chat_id} does not exist")
        owner_user = db.get_user(owner)
        owner_is_admin = bool(owner_user and owner_user.get('role') == 'admin')

        # Clear resume_suppressed flag on new normal turn
        db.update_chat(self.chat_id, resume_suppressed=0)
        
        # Sync mode flags from request to DB immediately
        db_updates = {}
        for flag_name, db_col in [
            ('researchMode', 'research_mode'),
            ('browsingMode', 'browsing_mode'),
            ('fileSystemMode', 'file_system_mode'),
            ('gitMode', 'git_mode'),
            ('codeExecutionMode', 'code_execution_mode')
        ]:
            val = kwargs.get(flag_name)
            if flag_name == 'gitMode' and val and not owner_is_admin:
                # Git reaches host-wide tools: only admin-owned chats get it (the routes already answer 403).
                log_event("chat_git_mode_denied", {"chat_id": self.chat_id})
                continue
            if val is not None:
                db_updates[db_col] = 1 if val else 0
        
        # Sync inference params from request to DB immediately
        if 'enable_thinking' in kwargs:
            db_updates['enable_thinking'] = 1 if kwargs['enable_thinking'] else 0
        for param in ['temperature', 'top_p', 'max_tokens', 'thinking_budget_tokens', 'top_k', 'min_p', 'presence_penalty', 'frequency_penalty', 'thinking_profile']:
            if param in kwargs and kwargs[param] is not None:
                db_updates[param] = kwargs[param]
        
        # Also sync userPreferences if provided in the payload to fix the race condition
        if 'userPreferences' in kwargs:
            db_updates['user_preferences'] = 1 if kwargs['userPreferences'] else 0

        # The stream has started, so a foreign workspace or persona cannot be answered with a 404 here: it is ignored and
        # logged (direct writes through save and patch are refused by the routes). A falsy value still clears the field.
        if 'folder' in kwargs and kwargs['folder'] is not None:
            folder = kwargs['folder']
            if not folder or (isinstance(folder, str) and db.get_workspace_owner(folder) == owner):
                db_updates['workspace_id'] = folder
            else:
                log_event("chat_foreign_workspace_ignored", {"chat_id": self.chat_id, "workspace_id": folder})

        if 'persona_id' in kwargs:
            new_persona_id = kwargs['persona_id']
            persona = db.get_persona(new_persona_id, owner) if new_persona_id and isinstance(new_persona_id, str) else None
            if new_persona_id and not persona:
                log_event("chat_foreign_persona_ignored", {"chat_id": self.chat_id, "persona_id": new_persona_id})
            else:
                db_updates['persona_id'] = new_persona_id
                # Snapshot the persona content at assignment time so future edits
                # to the persona record don't silently change this chat's behaviour.
                existing_chat = db.get_chat(self.chat_id)
                has_snapshot = existing_chat and existing_chat.get('persona_snapshot')
                if new_persona_id and not has_snapshot and persona.get('content'):
                    db_updates['persona_snapshot'] = persona['content']

        if db_updates:
            db.update_chat(self.chat_id, **db_updates)
        
        # 1. Handle file uploads (Collections)
        if files:
            # If we don't have a user message yet, these are 'standalone' uploads
            # for a new chat window.
            parent_id = user_message.get('id') if user_message else -1
            parent_type = "main" if user_message else "standalone"
            
            db.add_collection(
                chat_id=self.chat_id,
                parent_message_id=parent_id,
                parent_type=parent_type,
                collection_type="file_uploads",
                items=files
            )
            log_event("chat_files_stored", {"chat_id": self.chat_id, "count": len(files)})

        # 2. Process message if present
        if user_message:
            async for chunk in self.process_message(user_message, model, **kwargs):
                yield chunk

    async def process_message(
        self, 
        user_message: Dict[str, Any], 
        model: str,
        parent_type: str = "main",
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Handles Point 3 & 4: Launches background task and subscribes to output.
        """
        # 1. Start background task if not already running
        if not task_manager.is_task_running(self.chat_id):
            response_cache.initialize_chat(self.chat_id, overwrite=True)
            task_manager.start_task(
                chat_id=self.chat_id,
                execute_fn=self._run_background_turn,
                user_message=user_message,
                model_name=model,
                parent_type=parent_type,
                **kwargs
            )
            log_event("task_started_via_handler", {"chat_id": self.chat_id})
        else:
            log_event("task_reattach", {"chat_id": self.chat_id})

        # 2. Subscribe to the cache and yield to client
        async for chunk in response_cache.subscribe(self.chat_id):
            yield chunk

    async def _run_background_turn(self, **kwargs) -> AsyncGenerator[str, None]:
        """
        The actual generator that runs in the background task thread.
        It must yield chunks that TaskManager will append to the cache.
        """
        user_message = kwargs.get('user_message')
        model_name = kwargs.get('model_name')
        self.active_model = model_name  # Store for sub-agent access
        self.chunk_index = 0  # Reset for the start of a background turn
        parent_type = kwargs.get('parent_type', 'main')
        parent_message_id = user_message.get('id') if user_message else None

        # Re-initialize handlers with the anchoring ID for this turn
        from .tool_handler import ToolHandler
        self.tool_handler = ToolHandler(self.chat_id, self, parent_message_id=parent_message_id)

        # Numbered sources of this chat (so an old [[1]] keeps its meaning across turns)
        self.source_registry = self._load_source_registry()

        try:
            # Run via the TurnHandler to ensure serial execution even in background
            async for chunk in TurnHandler.handle_turn(
                chat_id=self.chat_id,
                parent_message_id=parent_message_id,
                run_fn=self._run_orchestrated_stream,
                model=model_name,
                sources=self.source_registry,
                user_message=user_message,
                model_name=model_name,
                parent_type=parent_type
            ):
                yield chunk
            
            # TurnHandler handles persistence natively via _persist_final_state
        except Exception as e:
            logger.error(f"Terminal error in background turn for {self.chat_id}: {e}", exc_info=True)
            # Yield error to client if they are listening
            yield f"data: {json.dumps({'error': 'An internal error occurred during generation.'})}\n\n"

    def _load_source_registry(self):
        """
        The chat's stored `source_registry` collection as a registry. Only an absent collection starts empty: an unreadable
        one raises (the turn fails before any tool runs) rather than restarting the numbers at 1 and reusing ones already
        shown to the model and in older answers.
        """
        from backend.chat.sources import SOURCE_REGISTRY_ANCHOR, SourceRegistry
        colls = db.get_collections(self.chat_id, parent_message_id=SOURCE_REGISTRY_ANCHOR.format(self.chat_id), parent_type="main")
        coll = next((c for c in colls if c.get("collection_type") == "source_registry"), None)
        if coll is None:
            return SourceRegistry()
        items = coll.get("items")
        if isinstance(items, str):
            items = json.loads(items)
        if not isinstance(items, list):
            raise ValueError("The stored source registry is not a list")
        return SourceRegistry.from_list(items)

    async def _run_orchestrated_stream(
        self, 
        user_message: Dict[str, Any],
        model_name: str,
        parent_type: str = "main",
        custom_stream: Optional[AsyncGenerator[str, None]] = None,
        agent_parent_message_id = None
    ) -> AsyncGenerator[str, None]:
        """
        Orchestrates a message stream (AI or Manual).
        Parses fragments, stores in cache, and flushes to DB on completion.
        """
        # Resolve the user-message anchor once per orchestration call
        last_user_ptr = None
        if parent_type == "main":
            last_user_ptr = user_message.get('id') if user_message else None

        # ── RESUME PRE-FLIGHT ──────────────────────────────────────────
        # Before entering the generation loop, check if the last assistant
        # message has pending (unexecuted) tool calls from a previous
        # interrupted turn. If found, skip the LLM and jump to tool
        # execution directly, preserving the original parent_message_id.
        if parent_type == "main" and custom_stream is None:
            _resume_gen = self._try_resume_pending_tools(
                last_user_ptr, agent_parent_message_id, parent_type
            )
            if _resume_gen is not None:
                async for chunk in _resume_gen:
                    yield chunk
                # Fall through to the while-True loop for LLM follow-up
                # (it will see the tool results in history now)
        # ── END RESUME PRE-FLIGHT ──────────────────────────────────────

        # Use a loop only for the main chat flow to handle tool chains automatically.
        # Sub-agents manage their own loops and history via their respective agents.
        iteration_count = 0
        max_iterations = getattr(config, 'MAX_TOOL_ROUNDS', 15)
        max_iterations_buffer = getattr(config, 'MAX_TOOL_CALLS_BUFFER', 5)
        hard_limit = max_iterations + max_iterations_buffer
        tools_disabled = False

        while True:
            iteration_count += 1
            if iteration_count > hard_limit:
                logger.error(f"[ChatHandler] Maximum tool loop iterations ({hard_limit}) exceeded for {self.chat_id}")
                yield f"data: {json.dumps({'error': 'The agent exceeded the maximum number of internal steps and was stopped.'})}\n\n"
                break

            if iteration_count > max_iterations:
                tools_disabled = True

            # 1. Determine the source stream
            if custom_stream:
                stream_gen = custom_stream
                custom_stream = None  # Clear so next iteration uses the engine
            elif parent_type == "main":
                # Fallback to engine for main turn (Turn -> Tool -> Turn chain)
                history = db.get_messages(self.chat_id, parent_message_id=agent_parent_message_id, parent_type=parent_type)
                chat_metadata = db.get_chat(self.chat_id) or {}
                is_research_mode = bool(chat_metadata.get('research_mode'))
                is_user_preferences = bool(chat_metadata.get('user_preferences'))
                is_browsing_mode = bool(chat_metadata.get('browsing_mode'))
                is_file_system_mode = bool(chat_metadata.get('file_system_mode'))
                is_git_mode = bool(chat_metadata.get('git_mode'))
                
                # Inject System Prompt for main turns
                if parent_type == "main":
                    from backend.chat.prompt_builder import PromptBuilder, PromptContext
                    
                    owner = chat_metadata.get('user_id')
                    owner_user = db.get_user(owner) if owner else None
                    ctx = PromptContext(
                        chat_metadata=chat_metadata,
                        preferences=db.get_all_preferences(owner) if is_user_preferences else [],
                        skills=db.get_all_skills(owner),
                        is_admin=bool(owner_user and owner_user.get('role') == 'admin'),
                    )
                    system_prompt = PromptBuilder(ctx).build()
                    skills_by_name = {s['name']: s for s in ctx.skills}


                    # 2. Parse tool calls in assistant messages to map tool_call_id to skill name
                    tool_call_to_skill = {}
                    for msg in history:
                        if msg.get('role') == 'assistant' and msg.get('tool_calls'):
                            for tc in msg['tool_calls']:
                                tc_id = tc.get('id')
                                fn = tc.get('function', {})
                                fn_name = fn.get('name')
                                if fn_name == 'get_skill_details' and tc_id:
                                    args_str = fn.get('arguments', '{}')
                                    if isinstance(args_str, str):
                                        try:
                                            args = json.loads(args_str)
                                        except Exception:
                                            args = {}
                                    else:
                                        args = args_str or {}
                                    skill_name = args.get('skill_name')
                                    if skill_name in skills_by_name:
                                        tool_call_to_skill[tc_id] = skill_name

                    # 3. Identify all invocations chronologically
                    invocations = []
                    for idx, msg in enumerate(history):
                        role = msg.get('role')
                        if role == 'user':
                            content = msg.get('content', '')
                            text_str = None
                            if isinstance(content, str) and content.startswith('/'):
                                text_str = content
                            elif isinstance(content, list):
                                for block in content:
                                    if (isinstance(block, dict) 
                                            and block.get('type') == 'text' 
                                            and isinstance(block.get('text'), str) 
                                            and block.get('text', '').startswith('/')):
                                        text_str = block['text']
                                        break
                            if text_str:
                                parts = text_str[1:].split(None, 1)
                                if parts:
                                    potential_name = parts[0]
                                    if potential_name in skills_by_name:
                                        invocations.append({
                                            "type": "user",
                                            "index": idx,
                                            "skill_name": potential_name,
                                            "skill_info": skills_by_name[potential_name],
                                            "message": msg
                                        })
                        elif role == 'tool':
                            tc_id = msg.get('tool_call_id')
                            if tc_id in tool_call_to_skill:
                                potential_name = tool_call_to_skill[tc_id]
                                invocations.append({
                                    "type": "ai",
                                    "index": idx,
                                    "skill_name": potential_name,
                                    "skill_info": skills_by_name[potential_name],
                                    "message": msg
                                })

                    # 4. Reconstruct history list with in-memory transformations applied
                    compiled_history = []
                    latest_inv = invocations[-1] if invocations else None

                    for idx, msg in enumerate(history):
                        is_inv = False
                        current_inv = None
                        for inv in invocations:
                            if inv['index'] == idx:
                                is_inv = True
                                current_inv = inv
                                break
                        
                        if is_inv and current_inv:
                            is_latest = (current_inv == latest_inv)
                            skill_info = current_inv['skill_info']
                            instructions = skill_info.get('instructions') or ''
                            skill_name = current_inv['skill_name']

                            if current_inv['type'] == 'user':
                                content = msg.get('content', '')
                                if isinstance(content, list):
                                    import copy
                                    new_msg = copy.deepcopy(msg)
                                    for block in new_msg.get('content', []):
                                        if (isinstance(block, dict) 
                                                and block.get('type') == 'text' 
                                                and isinstance(block.get('text'), str) 
                                                and block.get('text', '').startswith('/')):
                                            text_str = block['text']
                                            parts = text_str[1:].split(None, 1)
                                            remaining_text = parts[1] if len(parts) > 1 else ""
                                            if is_latest:
                                                wrapped_instructions = f"[SKILL: {skill_name}]\n{instructions}\n[/SKILL]"
                                                if remaining_text:
                                                    block['text'] = f"{wrapped_instructions}\n\n{remaining_text}"
                                                else:
                                                    block['text'] = wrapped_instructions
                                            break
                                    compiled_history.append(new_msg)
                                else:
                                    parts = content[1:].split(None, 1)
                                    remaining_text = parts[1] if len(parts) > 1 else ""
                                    
                                    new_msg = dict(msg)
                                    if is_latest:
                                        wrapped_instructions = f"[SKILL: {skill_name}]\n{instructions}\n[/SKILL]"
                                        if remaining_text:
                                            new_msg['content'] = f"{wrapped_instructions}\n\n{remaining_text}"
                                        else:
                                            new_msg['content'] = wrapped_instructions
                                    else:
                                        # Older user invocations are kept as is (starting with /skill_name prefix)
                                        pass
                                    compiled_history.append(new_msg)
                            
                            elif current_inv['type'] == 'ai':
                                compiled_history.append(msg)
                                
                                # Inject synthetic user message right after the tool response
                                synthetic_content = f"[SKILL: {skill_name}]\n{instructions}\n[/SKILL]" if is_latest else f"/{skill_name}"
                                compiled_history.append({
                                    "role": "user",
                                    "content": synthetic_content
                                })
                        else:
                            compiled_history.append(msg)

                    history = compiled_history
                    # ── END SKILLS COMPILATION ────────────────────────────────

                    history = [{"role": "system", "content": system_prompt}] + history

                confirmation_mode = (
                    self._pending_confirmation is not None
                    and parent_type == "main"
                )

                active_tools = []
                if not tools_disabled and not confirmation_mode:
                    from backend.tools import ToolRegistry
                    active_tools = ToolRegistry.get_main_tools(ctx.active_modes)

                stream_kwargs = {
                    "messages": history,
                    "model": model_name,
                    "chat_id": self.chat_id,
                }
                if active_tools:
                    stream_kwargs["tools"] = active_tools

                # Extract available generation parameters from chat_metadata
                if chat_metadata:
                    if 'enable_thinking' in chat_metadata and chat_metadata['enable_thinking'] is not None:
                        stream_kwargs['chat_template_kwargs'] = {
                            'enable_thinking': bool(chat_metadata['enable_thinking'])
                        }
                    
                    for param in ['temperature', 'top_p', 'top_k', 'min_p', 'presence_penalty', 'frequency_penalty', 'thinking_budget_tokens']:
                        if param in chat_metadata and chat_metadata[param] is not None:
                            stream_kwargs[param] = chat_metadata[param]

                if confirmation_mode:
                    stream_kwargs['max_tokens'] = 16
                    stream_kwargs['temperature'] = 0.0
                    stream_kwargs['chat_template_kwargs'] = {'enable_thinking': False}
                    log_event("clipboard_enforcement_confirmation_mode", {
                        "chat_id": self.chat_id,
                    })

                stream_gen = self.engine.stream(**stream_kwargs)
            else:
                # Sub-agents must provide a custom_stream (via run_inference_step)
                # If we get here without a stream in a sub-agent context, we stop.
                break

            # 2. Iterate through the current stream
            aggregated_tool_calls = {}  # index -> tool_call_dict
            # Use monotonic index across turn turns

            log_event("stream_start", {"chat_id": self.chat_id, "parent_type": parent_type, "anchor": last_user_ptr or agent_parent_message_id})

            async for line in stream_gen:
                # BREAK immediately if interrupted (don't even yield or cache)
                if task_manager.is_interrupted(self.chat_id):
                    log_event("stream_interrupted_mid_stream", {"chat_id": self.chat_id})
                    return

                # NOTE: The engine consumes "data: [DONE]" internally and never yields it.
                # This check is kept as a defensive guard only.
                if line.strip() == "data: [DONE]":
                    log_event("stream_done_sentinel_received", {"chat_id": self.chat_id})
                    break

                parsed = self._parse_sse_delta(line)

                # Tool-call fragments are aggregated locally; they must NOT be sent to the
                # client as raw partial JSON.  The single merged synthetic chunk is sent
                # after the loop ends (see below).
                if parsed and parsed.type == SSEEventType.TOOL_CALL:
                    try:
                        tc_deltas = json.loads(parsed.content)
                        if not isinstance(tc_deltas, list):
                            tc_deltas = [tc_deltas]

                        for tc_delta in tc_deltas:
                            idx = tc_delta.get('index', 0)
                            if idx not in aggregated_tool_calls:
                                aggregated_tool_calls[idx] = tc_delta.copy()
                            else:
                                merge_tool_call_deltas(aggregated_tool_calls[idx], tc_delta)
                    except Exception as e:
                        logger.error(f"[TOOL_DELTA] Error aggregating tool call delta: {e}. Raw content: {parsed.content}")
                    continue  # Do NOT yield raw tool_call fragments to the client.

                # Forward everything else (content, reasoning, etc.) to the client.
                # INJECTION: Ensure parent_type is included in the raw JSON payload for the frontend
                if parent_type and parent_type != "main":
                    try:
                        # Standard chunks are 'data: {JSON}'
                        if line.startswith("data: "):
                            json_data = json.loads(line[6:])
                            json_data["parent_type"] = parent_type
                            line = f"data: {json.dumps(json_data)}"
                    except Exception as e:
                        logger.error(f"Failed to inject parent_type into SSE chunk: {e}")

                yield line + "\n\n"

                if not parsed:
                    continue

                if parsed.type == SSEEventType.REDACT:
                    anchor = last_user_ptr if parent_type == "main" else agent_parent_message_id
                    logger.info(f"[REDACT] Redaction event received for chat_id={self.chat_id}. Resetting stream cache.")
                    self.cache.delete_sse_chunks(
                        chat_id=self.chat_id,
                        parent_message_id=anchor,
                        parent_type=parent_type
                    )
                    self.chunk_index = 0
                    aggregated_tool_calls.clear()
                    continue

                self.cache.add_sse_chunk(
                    chat_id=self.chat_id,
                    parent_message_id=last_user_ptr if parent_type == "main" else agent_parent_message_id,
                    parent_type=parent_type,
                    chunk_index=self.chunk_index,
                    chunk_type=parsed.type.value,
                    content=parsed.content
                )
                self.chunk_index += 1

            # --- Stream ended (engine consumed [DONE] or connection closed) ---
            log_event("stream_ended", {
                "chat_id": self.chat_id,
                "chunk_count": self.chunk_index,
                "tool_calls_aggregated": len(aggregated_tool_calls)
            })

            # 3. Handle Interruption Signal from TaskManager
            if task_manager.is_interrupted(self.chat_id):
                log_event("stream_interrupted_post_stream", {"chat_id": self.chat_id})
                break

            parent_anchor = last_user_ptr if parent_type == "main" else agent_parent_message_id

            # 4. Yield the synthetic tool call chunk and add to SSE cache as a single merged record
            if aggregated_tool_calls:
                # Apply JSON repair logic for tool call arguments in the stream
                for tc in aggregated_tool_calls.values():
                    func = tc.get("function", {})
                    args_str = func.get("arguments")
                    if isinstance(args_str, str) and args_str:
                        try:
                            json.loads(args_str)
                        except Exception:
                            repaired = self.engine._salvage_json_arguments(args_str)
                            if repaired is not None:
                                log_event("stream_tool_call_args_repaired", {
                                    "chat_id": self.chat_id,
                                    "tool_name": func.get("name"),
                                    "original": args_str,
                                    "repaired": repaired
                                })
                                func["arguments"] = repaired
                            else:
                                log_event("stream_tool_call_args_repair_failed", {
                                    "chat_id": self.chat_id,
                                    "tool_name": func.get("name"),
                                    "original": args_str
                                })

                tool_calls_list = list(aggregated_tool_calls.values())
                log_event("tool_calls_aggregated", {
                    "chat_id": self.chat_id,
                    "count": len(tool_calls_list),
                    "names": [tc.get('function', {}).get('name') for tc in tool_calls_list]
                })

                synthetic_delta = {
                    "choices": [{"delta": {"tool_calls": tool_calls_list}}]
                }
                if parent_type and parent_type != "main":
                    synthetic_delta["parent_type"] = parent_type
                synthetic_line = f"data: {json.dumps(synthetic_delta)}"
                yield synthetic_line + "\n\n"

                self.cache.add_sse_chunk(
                    chat_id=self.chat_id,
                    parent_message_id=parent_anchor,
                    parent_type=parent_type,
                    chunk_index=self.chunk_index,
                    chunk_type="tool_call",
                    content=json.dumps(tool_calls_list)
                )
                self.chunk_index += 1
                log_event("synthetic_tool_chunk_added", {"chat_id": self.chat_id, "parent_anchor": parent_anchor})

            # 5. Flush SSE cache to DB
            if not task_manager.is_interrupted(self.chat_id):
                sse_chunks_before_flush = self.cache.get_sse_chunks(self.chat_id)
                log_event("pre_flush_state", {
                    "chat_id": self.chat_id,
                    "sse_chunk_count": len(sse_chunks_before_flush),
                    "types": [c.get('chunk_type') for c in sse_chunks_before_flush],
                    "parent_anchor": parent_anchor
                })
                # Pass the model name and anchoring context to ensure isolation
                flush_ok = db.flush_sse_chunks(
                    self.chat_id, 
                    model=model_name,
                    parent_message_id=parent_anchor,
                    parent_type=parent_type
                )
                log_event("flush_result", {"chat_id": self.chat_id, "success": flush_ok})

            # 6. Inspection & Tool Execution Gate
            turn_anchor_id = agent_parent_message_id if parent_type != "main" else last_user_ptr

            last_msg = db.get_last_assistant_message(
                self.chat_id,
                parent_message_id=turn_anchor_id,
                parent_type=parent_type
            )

            log_event("tool_gate_check", {
                "chat_id": self.chat_id,
                "last_msg_id": last_msg.get('id') if last_msg else None,
                "has_tool_calls": bool(last_msg and last_msg.get('tool_calls')),
                "tool_calls_raw": (last_msg.get('tool_calls') if last_msg else None)
            })

            if last_msg and last_msg.get('tool_calls'):
                # Safety: Don't execute tools if turn was interrupted
                if task_manager.is_interrupted(self.chat_id):
                    break

                log_event("tool_execution_triggered", {"chat_id": self.chat_id, "parent_type": parent_type})
                
                # Execute tools in the current turn context
                async for tool_chunk in self._handle_tool_execution(
                    parent_message_id=turn_anchor_id,
                    parent_type=parent_type,
                    tools_disabled=tools_disabled
                ):
                    if task_manager.is_interrupted(self.chat_id):
                        break
                    yield tool_chunk
                
                # After tool execution, the main assistant loops back for follow-up.
                # Sub-agents manage their own loops, so we stop here.
                if parent_type == "main":
                    continue
                else:
                    break
            else:
                # ── CONFIRMATION GATE ────────────────────────
                if self._pending_confirmation is not None and parent_type == "main":
                    content = last_msg.get('content', '') if last_msg else ''
                    from backend.chat.validators import parse_confirmation_response
                    should_proceed = parse_confirmation_response(content)

                    log_event("clipboard_enforcement_confirmation_result", {
                        "chat_id": self.chat_id,
                        "raw_response": content[:100],
                        "decision": "PROCEED" if should_proceed else "REWRITE",
                        "patterns": self._pending_confirmation.get(
                            "matched_patterns", []
                        ),
                    })

                    if should_proceed:
                        self._validation_bypass_next = True

                    self._pending_confirmation = None
                    continue  # Loop back with tools re-enabled
                # ── END CONFIRMATION GATE ────────────────────

                # No more tool calls. The turn is truly finished.
                break

        # Finalize Research Mode state was here (REMOVED)

    async def _handle_tool_execution(self, parent_message_id: int, parent_type: str, tools_disabled: bool = False) -> AsyncGenerator[str, None]:
        """
        Inspects the last assistant message for tool calls and executes them 
        using ToolHandler, ensuring results are anchored to the correct parent.
        """
        last_msg = db.get_last_assistant_message(self.chat_id, parent_message_id=parent_message_id, parent_type=parent_type)
        if not last_msg or not last_msg.get('tool_calls'):
            return

        # For Main AI, we anchor tool results to the atomic last_assistant_id.
        # For Sub-Agents, we anchor to the provided parent_message_id (which is the tool_call_id).
        if parent_type == "main":
            chat_meta = db.get_chat(self.chat_id)
            assistant_message_id = chat_meta.get('last_assistant_id') if chat_meta else None
            if not assistant_message_id:
                logger.error(f"[TOOL_EXEC] No last_assistant_id found for chat {self.chat_id}, falling back to turn anchor.")
                assistant_message_id = parent_message_id
            # Turn anchor for Main AI is the user message ID
            turn_anchor_id = parent_message_id
        else:
            assistant_message_id = parent_message_id
            # Turn anchor for Agents is the tool_call_id
            turn_anchor_id = parent_message_id

        self.tool_handler.parent_message_id = assistant_message_id
        self.tool_handler.turn_anchor_id = turn_anchor_id
        self.tool_handler.parent_type = parent_type
        self.tool_handler.agent_handler.parent_message_id = assistant_message_id

        try:
            tcs = last_msg['tool_calls']

            if tools_disabled:
                # Intercept hallucinated tool calls and return an error
                tool_results = []
                for tc in tcs:
                    tool_call_id = tc.get("id")
                    tool_name = tc.get("function", {}).get("name", "unknown")
                    error_msg = f"Error: Tool execution denied. Maximum tool calls reached. You MUST provide a final response to the user."
                    
                    tool_result_obj = {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "name": tool_name,
                        "content": error_msg
                    }
                    tool_results.append(tool_result_obj)
                    
                    db.add_message(
                        chat_id=self.chat_id,
                        role="tool",
                        content=error_msg,
                        parent_message_id=assistant_message_id,
                        parent_type=parent_type,
                        tool_call_id=tool_call_id,
                        name=tool_name
                    )

                    delta = {
                        "choices": [{"delta": {"tool_result": tool_result_obj}}]
                    }
                    if parent_type and parent_type != "main":
                        delta["parent_type"] = parent_type
                        
                    yield f"data: {json.dumps(delta)}\n\n"
                return
            
            # Detect if research is being called to manage state locking
            has_research_call = any(tc.get('function', {}).get('name') == 'research' for tc in tcs)
            if has_research_call:
                 db.update_research_state(self.chat_id, "ongoing")
                 yield f"data: {json.dumps({'type': 'state_sync', 'research_state': 'ongoing'})}\n\n"

            async for chunk in self.tool_handler.handle_tool_calls(tcs):
                yield chunk

            # Reset Research Mode once the tool has returned its synthesis/report
            if has_research_call:
                 db.update_chat(self.chat_id, research_mode=0, research_state='none')
                 yield f"data: {json.dumps({'type': 'state_sync', 'research_mode': 0, 'research_state': 'none'})}\n\n"
        except Exception as e:
            logger.error(f"Error executing tool calls: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    def _try_resume_pending_tools(self, last_user_ptr, agent_parent_id, parent_type):
        """
        Detects pending (unexecuted) tool calls from a previous interrupted turn.
        Returns an async generator that re-executes them if found, None otherwise.
        
        This is the core of the resume bypass: instead of re-invoking the LLM
        (which would create a duplicate response and orphan sub-agent state),
        we jump straight to tool execution with the original parent_message_id.
        """
        anchor = agent_parent_id or last_user_ptr
        last_asst = db.get_last_assistant_message(
            self.chat_id, parent_message_id=anchor, parent_type="main"
        )
        if not last_asst or not last_asst.get('tool_calls'):
            return None

        try:
            tc_list = last_asst['tool_calls']
            tc_ids = {tc.get('id') for tc in tc_list if tc.get('id')}
        except Exception:
            return None

        if not tc_ids:
            return None

        # Check which tool results already exist (scoped to this turn only)
        all_msgs = db.get_messages(self.chat_id, parent_type="main")
        anchor_seen = False
        result_ids = set()
        for m in all_msgs:
            if not anchor_seen:
                if m.get('id') == anchor:
                    anchor_seen = True
                continue
            if m.get('role') == 'tool' and m.get('tool_call_id'):
                result_ids.add(m['tool_call_id'])
        pending = tc_ids - result_ids

        if not pending:
            return None

        # Clean up orphaned partial sub-agent messages from crash
        self._cleanup_orphaned_partials(last_asst['id'])

        pending_names = [
            tc.get('function', {}).get('name')
            for tc in tc_list if tc.get('id') in pending
        ]
        log_event("resume_pending_tools", {
            "chat_id": self.chat_id,
            "pending_count": len(pending),
            "tool_names": pending_names,
        })

        async def _resume_gen():
            # Re-emit tool calls to frontend so activity feed shows progress
            synthetic = {"choices": [{"delta": {"tool_calls": tc_list}}]}
            yield f"data: {json.dumps(synthetic)}\n\n"

            # Execute the pending tools with the ORIGINAL parent_message_id
            async for chunk in self._handle_tool_execution(
                parent_message_id=anchor, parent_type=parent_type
            ):
                if task_manager.is_interrupted(self.chat_id):
                    return
                yield chunk

        return _resume_gen()

    def _cleanup_orphaned_partials(self, assistant_message_id: int):
        """
        Removes orphaned partial sub-agent messages created during a crashed
        inference step. Uses event markers as checkpoints:
        - Finds the last 'Completed' event marker
        - Removes any trailing assistant messages without tool_calls
          (i.e., partial responses that were flushed mid-stream)
        """
        for agent_name in ['research', 'file_system_agent', 'browsing_agent', 'document_agent', 'search_web', 'visit_page']:
            sub_msgs = db.get_messages(
                self.chat_id,
                parent_message_id=assistant_message_id,
                parent_type=agent_name
            )
            if not sub_msgs:
                continue

            # Find last completion event marker
            last_complete_idx = -1
            for i, m in enumerate(sub_msgs):
                content = m.get('content') or ''
                if m.get('role') == 'event' and 'Completed' in content:
                    last_complete_idx = i

            # Remove trailing orphaned partial assistant messages
            # (messages after the last checkpoint that have no tool_calls
            # and are not tool results — indicating a partial flush)
            if last_complete_idx < len(sub_msgs) - 1:
                orphan_ids = []
                for m in sub_msgs[last_complete_idx + 1:]:
                    if (m.get('role') == 'assistant'
                            and not m.get('tool_calls')
                            and m.get('content', '').strip() != ''):
                        orphan_ids.append(m['id'])

                if orphan_ids:
                    for oid in orphan_ids:
                        db.delete_sub_agent_message(self.chat_id, oid)
                    log_event("orphan_cleanup", {
                        "chat_id": self.chat_id,
                        "agent": agent_name,
                        "removed": len(orphan_ids),
                    })

    def _parse_sse_delta(self, line: str) -> Optional[SSEEvent]:
        """Extracts content and type from a 'data: {...}' SSE line."""
        if not line.startswith("data: "):
            return None
            
        try:
            data = json.loads(line[6:])
            if "__redact__" in data:
                return SSEEvent(type=SSEEventType.REDACT, content=data.get("message", ""))
                
            delta = data.get("choices", [{}])[0].get("delta", {})
            
            if "role" in delta and delta["role"] == "event":
                return SSEEvent(type=SSEEventType.EVENT, content=delta.get("content", ""))
            if "reasoning_content" in delta and delta["reasoning_content"] is not None:
                return SSEEvent(type=SSEEventType.THINKING, content=delta["reasoning_content"])
            if "content" in delta and delta["content"] is not None:
                return SSEEvent(type=SSEEventType.CONTENT, content=delta["content"])
            if "tool_calls" in delta and delta["tool_calls"] is not None:
                return SSEEvent(type=SSEEventType.TOOL_CALL, content=json.dumps(delta["tool_calls"]))
            if "tool_result" in delta:
                return SSEEvent(type=SSEEventType.TOOL_RESULT, content=delta["tool_result"])
            
            return None
        except Exception as e:
            logger.error(f"Error parsing SSE delta: {e}")
            return None

    def cleanup(self):
        """Cleanup resources for this chat session."""
        self.cache.cleanup_chat(self.chat_id)
