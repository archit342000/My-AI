import logging
import json
import asyncio
import contextvars
from typing import List, Dict, Any, Optional, AsyncGenerator

from backend.database import db
from backend.tools import ToolRegistry
from backend.logging import log_event
from backend.chat.models import ParsedToolCall

logger = logging.getLogger(__name__)

_UNSET = object()

class ToolHandler:
    """
    Orchestrates the execution of tool calls.
    Decides whether to execute a pure function or hand off to a sub-agent.
    """

    def __init__(self, chat_id: str, chat_handler: Any, parent_message_id: Optional[int] = None, parent_type: str = "main"):
        self.chat_id = chat_id
        self.chat_handler = chat_handler
        self.parent_message_id = parent_message_id
        self.turn_anchor_id = None
        self.parent_type = parent_type
        self._user_id = _UNSET
        # Initialize AgentHandler with the same anchoring ID
        from .agent_handler import AgentHandler
        self.agent_handler = AgentHandler(chat_id, chat_handler, parent_message_id=parent_message_id)

    @property
    def user_id(self) -> Optional[str]:
        """
        The chat owner, from the server: tools that touch user data get it through system_ctx, never from the model.

        Read from the db on first use and then kept, so building a handler needs no db access.
        """
        if self._user_id is _UNSET:
            self._user_id = db.get_chat_owner(self.chat_id)
        return self._user_id

    async def handle_tool_calls(
        self, 
        tool_calls: List[Dict[str, Any]]
    ) -> AsyncGenerator[str, None]:
        """
        Processes a list of tool calls sequentially.
        Yields chunks if sub-agents are involved, or simply executes pure tools.
        """
        for tc in tool_calls:
            parsed = ParsedToolCall.from_openai_delta(tc)
            tc_id = parsed.id
            name = parsed.name
            args = parsed.arguments
            args_str = parsed.raw_arguments

            # ── IDEMPOTENCY GUARD ──────────────────────────────────────
            # Skip tool calls that already have a result in the DB.
            # This prevents re-execution on resume after crash.
            if tc_id:
                from backend.database import db as _db
                existing = _db.get_messages(self.chat_id, parent_type=self.parent_type)
                already_done = any(
                    m.get('role') == 'tool' and m.get('tool_call_id') == tc_id
                    for m in existing
                )
                if already_done:
                    log_event("tool_call_skipped_idempotent", {
                        "chat_id": self.chat_id, "name": name, "id": tc_id
                    })
                    continue
            # ── END IDEMPOTENCY GUARD ──────────────────────────────────

            log_event("tool_call_dispatch", {"chat_id": self.chat_id, "name": name, "id": tc_id, "args_raw": args_str})

            if not name:
                logger.error(f"[TOOL] Skipping tool call with missing name. Full tc: {tc}")
                continue

            log_event("tool_call_execution", {"name": name, "id": tc_id})

            # Check Registry for Type
            tool_meta = ToolRegistry.get_tool(name)
            if not tool_meta:
                error_msg = f"Error: Tool '{name}' not found in registry. Available: {list(ToolRegistry._registry.keys())}"
                logger.warning(f"[TOOL] {error_msg}")

                from backend.database import db
                db.add_tool_result(
                    chat_id=self.chat_id,
                    tool_call_id=tc_id,
                    name=name,
                    content=error_msg,
                    parent_id=self.parent_message_id,
                    parent_type=self.parent_type
                )
                yield "data: " + json.dumps({
                    "parent_type": self.parent_type,
                    "choices": [{
                        "delta": {
                            "tool_result": {
                                "name": name,
                                "content": error_msg,
                                "tool_call_id": tc_id
                            }
                        }
                    }]
                }) + "\n\n"
                continue

            if tool_meta.get('type') == 'agent':
                log_event("tool_call_agent", {"chat_id": self.chat_id, "name": name, "id": tc_id, "args_raw": args_str})

                # ── CLIPBOARD ENFORCEMENT ────────────────────────────────
                if name == "file_system_agent":
                    bypass = False
                    if hasattr(self.chat_handler, '_validation_bypass_next'):
                        val = self.chat_handler._validation_bypass_next
                        if isinstance(val, bool):
                            bypass = val
                    if bypass:
                        self.chat_handler._validation_bypass_next = False
                        log_event("clipboard_enforcement_bypassed", {
                            "chat_id": self.chat_id, "tc_id": tc_id,
                        })
                    else:
                        from backend.chat.validators import (
                            validate_fs_agent_instruction, ValidationStatus,
                        )
                        validation = validate_fs_agent_instruction(args)

                        if validation.status in (
                            ValidationStatus.HARD_REJECT,
                            ValidationStatus.SOFT_REJECT,
                        ):
                            if validation.status == ValidationStatus.SOFT_REJECT:
                                self.chat_handler._pending_confirmation = {
                                    "tc_id": tc_id,
                                    "name": name,
                                    "args": args.copy(),
                                    "matched_patterns": validation.matched_patterns,
                                }

                            from backend.database import db as _vdb
                            _vdb.add_tool_result(
                                chat_id=self.chat_id,
                                tool_call_id=tc_id,
                                name=name,
                                content=validation.message,
                                parent_id=self.parent_message_id,
                                parent_type=self.parent_type,
                            )
                            yield "data: " + json.dumps({
                                "parent_type": self.parent_type,
                                "choices": [{"delta": {"tool_result": {
                                    "name": name,
                                    "content": validation.message,
                                    "tool_call_id": tc_id,
                                }}}]
                            }) + "\n\n"
                            continue
                # ── END CLIPBOARD ENFORCEMENT ────────────────────────────

                # 1. Handoff to AgentHandler
                flow_fn = ToolRegistry.resolve_implementation(name)
                logger.info(f"[TOOL] Resolved flow function for tool '{name}': {flow_fn}")
                if flow_fn:
                    # Specific agent overrides
                    if name == "search_web" and self.parent_type == "research":
                        args["return_raw_results"] = True

                    # SCOPED ANCHORING: Sub-agents use the tool_call_id as their parent anchor.
                    # This isolates their messages and task lists from the Main AI.
                    self.agent_handler.parent_message_id = tc_id
                    
                    # Capture the return value (summary) if the agent provides one
                    gen = self.agent_handler.execute_agent(name, flow_fn, **args)
                    it = gen.__aiter__()
                    agent_result = None
                    try:
                        while True:
                            chunk = await it.__anext__()
                            yield chunk
                    except StopAsyncIteration:
                        agent_result = self.agent_handler.result
                    
                    if agent_result is None:
                        agent_result = f"Agent '{name}' completed execution successfully."
                    
                    # Ensure structured data is serialized to JSON string for the frontend
                    agent_content_str = json.dumps(agent_result) if isinstance(agent_result, (dict, list)) else str(agent_result)

                    # Record the tool result with the ACTUAL content returned by the agent
                    from backend.database import db
                    log_event("tool_result_storing", {"chat_id": self.chat_id, "name": name, "tc_id": tc_id, "result_preview": agent_content_str[:200]})
                    db.add_tool_result(
                        chat_id=self.chat_id,
                        tool_call_id=tc_id,
                        name=name,
                        content=agent_content_str,
                        parent_id=self.parent_message_id,
                        parent_type=self.parent_type
                    )

                    # Yield synthetic result chunk for frontend rendering and phase boundary.
                    # Use self.parent_type so the frontend routes this result to the correct
                    # caller card (e.g. "main" Assistant or the parent agent).
                    yield "data: " + json.dumps({
                        "parent_type": self.parent_type,
                        "choices": [{
                            "delta": {
                                "tool_result": {
                                    "name": name,
                                    "content": agent_content_str,
                                    "tool_call_id": tc_id
                                }
                            }
                        }]
                    }) + "\n\n"
                else:
                    error_msg = f"Error: Agent implementation for '{name}' could not be resolved."
                    logger.error(f"[TOOL] {error_msg}")
                    from backend.database import db
                    db.add_tool_result(
                        chat_id=self.chat_id,
                        tool_call_id=tc_id,
                        name=name,
                        content=error_msg,
                        parent_id=self.parent_message_id,
                        parent_type=self.parent_type
                    )
                    yield "data: " + json.dumps({
                        "parent_type": self.parent_type,
                        "choices": [{
                            "delta": {
                                "tool_result": {
                                    "name": name,
                                    "content": error_msg,
                                    "tool_call_id": tc_id
                                }
                            }
                        }]
                    }) + "\n\n"
            else:
                log_event("tool_call_pure", {"chat_id": self.chat_id, "name": name, "id": tc_id, "args_raw": args_str})

                # 2. Pure Tool Execution
                # Injecting system context including tc_id for clarification support
                result = await self._execute_pure_tool(name, args, tc_id=tc_id)
                
                # Ensure structured data is serialized to JSON string for the frontend
                content_str = json.dumps(result) if isinstance(result, (dict, list)) else str(result)
                logger.info(f"[TOOL] Pure tool '{name}' returned: {content_str[:200]}")
                
                from backend.database import db
                log_event("tool_result_storing", {"chat_id": self.chat_id, "name": name, "tc_id": tc_id, "result_preview": content_str[:200]})
                db.add_tool_result(
                    chat_id=self.chat_id,
                    tool_call_id=tc_id,
                    name=name,
                    content=content_str,
                    parent_id=self.parent_message_id,
                    parent_type=self.parent_type
                )

                # Yield synthetic result chunk for frontend rendering and phase boundary
                yield "data: " + json.dumps({
                    "parent_type": self.parent_type,
                    "choices": [{
                        "delta": {
                            "tool_result": {
                                "name": name,
                                "content": content_str,
                                "tool_call_id": tc_id
                            }
                        }
                    }]
                }) + "\n\n"
    async def _execute_pure_tool(self, name: str, args: Dict[str, Any], tc_id: str = None) -> Any:
        """Dynamically resolves and executes a pure tool implementation."""
        import inspect
        impl = ToolRegistry.resolve_implementation(name)
        if not impl:
            return f"Error: Implementation for {name} could not be resolved."

        # Only inject system kwargs the function explicitly declares.
        # This prevents "unexpected keyword argument" errors for zero-arg tools like get_current_time.
        try:
            owner = self.user_id
        except Exception as e:  # a db failure must not raise mid-stream; tools that need the owner then report its absence
            logger.error(f"Could not read the owner of chat {self.chat_id}: {e}")
            owner = None
        system_ctx = {
            "chat_id": self.chat_id,
            "parent_message_id": self.parent_message_id,
            "turn_anchor_id": getattr(self, 'turn_anchor_id', self.parent_message_id),
            "tool_call_id": tc_id,
            "parent_type": self.parent_type,
            "user_id": owner
        }
        try:
            sig = inspect.signature(impl)
            has_var_keyword = any(
                p.kind == inspect.Parameter.VAR_KEYWORD
                for p in sig.parameters.values()
            )
            if has_var_keyword:
                full_args = {**args, **system_ctx}
            else:
                accepted = set(sig.parameters.keys())
                full_args = {**args, **{k: v for k, v in system_ctx.items() if k in accepted}}
        except (ValueError, TypeError):
            full_args = args

        try:
            if asyncio.iscoroutinefunction(impl):
                return await impl(**full_args)
            else:
                loop = asyncio.get_event_loop()
                # run_in_executor does not copy the context, so run in a copy to keep the current user (log_event user_id)
                context = contextvars.copy_context()
                return await loop.run_in_executor(None, lambda: context.run(impl, **full_args))
        except Exception as e:
            logger.error(f"Error executing tool {name}: {e}", exc_info=True)
            log_event("tool_handler_tool_error", {
                "chat_id": self.chat_id, "name": name, "id": tc_id,
                "error_type": type(e).__name__, "error": str(e)[:500],
            })
            # The model gets a fixed message; the exception detail (paths, internals) stays in the logs.
            return (f"Error: Tool '{name}' failed unexpectedly. "
                    "Check the arguments and try again, or use a different approach.")
