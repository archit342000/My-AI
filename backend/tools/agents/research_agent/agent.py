import json
import asyncio
import uuid
import logging
from typing import AsyncGenerator, Dict, Any, List

from backend.tools.time_utils import get_current_date
from backend.inference import ManualChunkEmitter
from backend.database import db
from backend import config
from backend.auth.rate_limit import SearchLimitReached, check_search_limit
from backend.error_handling import CircuitOpenError
from .prompts import (
    PLANNER_SYSTEM_PROMPT, 
    SCOUT_SYSTEM_PROMPT,
    RESEARCH_EXECUTOR_SYSTEM_PROMPT,
    RESEARCH_REFLECTION_PROMPT,
    RESEARCH_TRIAGE_PROMPT,
    RESEARCH_STEP_WRITER_PROMPT,
    RESEARCH_STEP_SUMMARY_PROMPT,
    RESEARCH_AUDITOR_PROMPT,
)
from .constants import (
    EVENT_SCOUT_FINALIZED, EVENT_PLAN_APPROVED, EVENT_PLAN_START,
    EVENT_SCOUT_START, EVENT_ALL_SECTIONS_DONE,
    EVENT_SECTION_PREFIX, EVENT_SECTION_START_PREFIX, EVENT_SECTION_COMPLETE_SUFFIX,
    EVENT_INITIAL_SEARCHES_PREFIX, EVENT_INITIAL_SEARCHES_DONE, 
    EVENT_REFLECTION_DONE, EVENT_REFLECTION_START, 
    EVENT_GAP_SEARCHES_START, EVENT_GAP_SEARCHES_IN_PROGRESS,
    EVENT_GAP_SEARCHES_DONE, EVENT_TRIAGE_START, EVENT_TRIAGE_DONE,
    EVENT_WRITER_START, EVENT_WRITER_DONE,
    EVENT_SUMMARY_START, EVENT_SUMMARY_DONE,
    EVENT_SYNTHESIS_START, EVENT_SYNTHESIS_POST,
    EVENT_RESEARCH_COMPLETE, PLAN_APPROVAL_SIGNAL,
)
from .schemas import (
    SCOUT_JSON_SCHEMA,
    PLAN_GENERATOR_JSON_SCHEMA,
    REFLECTION_JSON_SCHEMA,
    TRIAGE_JSON_SCHEMA,
    WRITER_JSON_SCHEMA,
    SUMMARY_JSON_SCHEMA
)
from .research_utils import (
    _extract_json_from_text, 
    _format_plan_as_markdown,
    _execute_mcp_tool,
    _normalize_citations,
    _strip_report_images
)

logger = logging.getLogger(__name__)

class SectionState:
    """
    Encapsulates the progress markers for a specific research section 
    to enable thread-safe concurrent execution.
    """
    def __init__(self, index: int):
        self.index = index
        self.has_initial_search = False
        self.has_reflection = False
        self.has_gap_searches = False
        self.has_triage = False
        self.has_writer = False
        self.has_summary = False

class ResearchAgent:
    """
    Runs the full research pipeline in a unified state machine.
    """
    AGENT_NAME = "research"

    def __init__(self, chat_id: str, parent_message_id: int, enable_thinking: bool, model: str):
        self.chat_id = chat_id
        self.parent_message_id = parent_message_id
        self.enable_thinking = enable_thinking
        self.model = model
        self.emitter = ManualChunkEmitter()
        self.file_system_lock = asyncio.Lock() # Serializes file_system writes
        self._sampling_kwargs = {}  # Extra sampling params forwarded to run_inference_step


    def _msg_from_db(self, m: Dict) -> Dict:
        """Build a message dict from a DB row, preserving reasoning_content for the inference engine."""
        msg = {"role": m["role"], "content": m.get("content", "")}
        if m.get("tool_calls"): msg["tool_calls"] = m["tool_calls"]
        if m.get("tool_call_id"): msg["tool_call_id"] = m["tool_call_id"]
        if m.get("name"): msg["name"] = m["name"]
        if m.get("reasoning_content"): msg["reasoning_content"] = m["reasoning_content"]
        return msg

    def _safe_json_loads(self, data: str, fallback: Any = None) -> Any:
        """Safe JSON parsing with fallback."""
        if not data:
            return fallback
        try:
            return json.loads(data)
        except Exception:
            return fallback

    def _is_suspended(self, history: List[Dict[str, Any]]) -> bool:
        """
        Detects if the agent is currently suspended waiting for tool results.
        Returns True if the last assistant message in history has tool_calls 
        that do not have corresponding 'tool' results later in the history.
        """
        # Concurrent safety: If history is empty, not suspended.
        if not history:
            return False
            
        # Find the last assistant message that has tool calls
        last_asst_with_tools = None
        for m in reversed(history):
            if m.get('role') == 'assistant' and m.get('tool_calls'):
                last_asst_with_tools = m
                break
        
        if not last_asst_with_tools:
            return False
            
        # Extract all tool_call_ids from this assistant message
        tc_ids = set()
        tcs = last_asst_with_tools.get('tool_calls')
        if isinstance(tcs, str):
            tcs = self._safe_json_loads(tcs, [])
        
        if not isinstance(tcs, list):
            tcs = [tcs]
            
        for tc in tcs:
            if tc.get('id'):
                tc_ids.add(tc['id'])
        
        if not tc_ids:
            return False
            
        # Check if all these IDs have results later in history
        asst_found = False
        for m in history:
            if not asst_found:
                if m == last_asst_with_tools:
                    asst_found = True
                continue
            if m.get('role') == 'tool' and m.get('tool_call_id') in tc_ids:
                tc_ids.remove(m['tool_call_id'])
                
        return len(tc_ids) > 0

    async def _emit_event(self, content: str, parent_type: str = None):
        """
        Emits a status event to the DB and the stream.
        """
        p_type = parent_type or self.AGENT_NAME
        db.add_message(
            chat_id=self.chat_id,
            role="event",
            content=content,
            parent_id=self.parent_message_id,
            parent_type=p_type
        )
        async for chunk in self.emitter.stream_message(event=content, parent_type=p_type):
            yield chunk

    async def _run_json_inference(
        self,
        agent: Any,
        messages: List[Dict],
        phase_name: str,
        schema: Dict,
        max_tokens: int,
        thinking_budget: int,
        parent_type: str = None
    ) -> AsyncGenerator[Any, None]:
        """
        Unified helper for JSON-based inference turns with retries and schema validation.
        Yields streaming chunks and finally the parsed JSON result.
        """
        p_type = parent_type or self.AGENT_NAME
        max_retries = config.RESEARCH_MAX_RETRIES
        sampling_params = self._sampling_kwargs.copy()

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    logger.info(f"Retrying {phase_name} (Attempt {attempt+1})")

                async for chunk in agent.run_inference_step(

                    agent_name=p_type,
                    messages=messages,
                    model_name=self.model,
                    max_tokens=max_tokens,
                    thinking_budget_tokens=thinking_budget,
                    **sampling_params,
                    response_format={
                        "type": "json_schema", 
                        "json_schema": {"name": phase_name, "schema": schema, "strict": True}
                    }
                ):
                    yield chunk
                
                # Verify and parse result from DB history
                db_history = db.get_messages(self.chat_id, parent_message_id=self.parent_message_id, parent_type=p_type)
                if not db_history:
                    raise ValueError(f"No history found after {phase_name} inference.")
                
                last_msg = db_history[-1]
                content = last_msg.get("content", "")
                
                result = _extract_json_from_text(content)
                if result:
                    # Success: Yield the parsed object as a result chunk
                    yield {"type": f"{phase_name}_result", "data": result}
                    return
                
                raise ValueError(f"Failed to extract valid JSON for {phase_name}")

            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    from .research_utils import _is_transient_error
                    # Explicitly allow retry on ValueError for JSON parse failures (1.2)
                    if _is_transient_error(e) or isinstance(e, ValueError):
                        logger.warning(f"Inference error in {phase_name}: {e}. Retrying...")
                        async for chunk in self._emit_event(f"⚠️ {phase_name} inference failed. Retrying ({attempt+2}/{max_retries+1})...", parent_type=p_type):
                            yield chunk
                        continue
                
                logger.error(f"Inference failed for {phase_name} after {attempt+1} attempts: {e}")
                # If we're here, we exhausted retries or hit a fatal error
                raise last_error

    def _validate_plan(self, plan: Dict) -> tuple[bool, str]:
        """
        Validates that the generated plan has the required structure for execution (4.1, 6.4).
        """
        if not plan:
            return False, "Plan is empty."
        
        sections = plan.get("sections", [])
        if not sections or not isinstance(sections, list):
            return False, "Plan has no sections."
        
        if len(sections) == 0:
            return False, "Plan contains zero sections."

        for i, s in enumerate(sections):
            if not s.get("heading"):
                return False, f"Section {i+1} is missing a heading."
            if not s.get("queries") or not isinstance(s.get("queries"), list):
                return False, f"Section {i+1} has missing or invalid 'queries' list."
        
        return True, "Valid"

    async def run(self, topic: str, agent_handler: Any) -> AsyncGenerator[str, None]:
        """
        Main orchestration loop for the research process.
        """
        
        # 0. Sync Main History
        db_history = db.get_messages(self.chat_id, parent_message_id=self.parent_message_id, parent_type=self.AGENT_NAME)
        has_plan_approved = any(m.get("role") == "event" and EVENT_PLAN_APPROVED in m.get("content", "") for m in db_history)
        has_scout_finalized = any(m.get("role") == "event" and EVENT_SCOUT_FINALIZED in m.get("content", "") for m in db_history)
        
        # Load the plan from collections if it exists
        colls = db.get_collections(self.chat_id, parent_message_id=self.parent_message_id, parent_type=self.AGENT_NAME)
        plan_coll = next((c for c in colls if c.get("collection_type") == "research_plan"), None)
        active_plan = self._safe_json_loads(plan_coll["items"], None) if plan_coll else None

        # Phase 0: Scout Phase (Context gathering, Search, and Clarification)
        scout_coll = next((c for c in colls if c.get("collection_type") == "scout_context"), None)
        scout_context = self._safe_json_loads(scout_coll["items"], "") if scout_coll else ""

        if not has_scout_finalized:
            try:
                async for chunk in self._run_scout(topic, agent_handler):
                    if isinstance(chunk, dict) and chunk.get("type") == "scout_context":
                        scout_context = chunk.get("data")
                        db.add_collection(
                            chat_id=self.chat_id,
                            parent_message_id=self.parent_message_id,
                            parent_type=self.AGENT_NAME,
                            collection_type="scout_context",
                            items=scout_context,
                            overwrite=True
                        )
                    else:
                        yield chunk
            except Exception as e:
                logger.error(f"Scout phase crashed: {e}", exc_info=True)
                async for chunk in self._emit_event(f"❌ Scout phase failed: {str(e)[:200]}"):
                    yield chunk
                db.update_chat(self.chat_id, research_state='failed')
                return
            
            # If we suspended during scout, stop.
            if not any(m.get("role") == "event" and EVENT_SCOUT_FINALIZED in m.get("content", "") for m in db.get_messages(self.chat_id, parent_message_id=self.parent_message_id, parent_type=self.AGENT_NAME)):
                return

        # Phase 1: Plan Generation (Strategy -> UI Review -> Approval)
        if not has_plan_approved:
            try:
                async for chunk in self._run_planner(topic, scout_context, agent_handler):
                    yield chunk
            except Exception as e:
                logger.error(f"Planner phase crashed: {e}", exc_info=True)
                async for chunk in self._emit_event(f"❌ Planner phase failed: {str(e)[:200]}"):
                    yield chunk
                db.update_chat(self.chat_id, research_state='failed')
                return
            
            # Re-check approval after run
            db_history = db.get_messages(self.chat_id, parent_message_id=self.parent_message_id, parent_type=self.AGENT_NAME)
            if not any(m.get("role") == "event" and EVENT_PLAN_APPROVED in m.get("content", "") for m in db_history):
                return
            
            # Reload plan after successful approval
            colls = db.get_collections(self.chat_id, parent_message_id=self.parent_message_id, parent_type=self.AGENT_NAME)
            plan_coll = next((c for c in colls if c.get("collection_type") == "research_plan"), None)
            active_plan = self._safe_json_loads(plan_coll["items"], None) if plan_coll else None

        if not active_plan:
            logger.error("No active plan found for execution phase.")
            async for chunk in self._emit_event("❌ Research plan is missing or corrupted. Cannot proceed."):
                yield chunk
            return

        # 1.5 Validate the plan (4.1, 6.4)
        is_valid, reason = self._validate_plan(active_plan)
        if not is_valid:
            logger.error(f"Plan validation failed: {reason}")
            async for chunk in self._emit_event(f"❌ Research plan validation failed: {reason}"):
                yield chunk
            return

        # Phase 2: Execution (Section Loop)
        try:
            async for chunk in self._run_executor(active_plan, agent_handler):
                yield chunk
        except Exception as e:
            logger.error(f"Executor phase crashed: {e}", exc_info=True)
            async for chunk in self._emit_event(f"❌ Execution phase failed: {str(e)[:200]}"):
                yield chunk
            db.update_chat(self.chat_id, research_state='failed')
            return

        # Phase 3: Assembly & Audit (Detective -> Surgeon -> Synthesis)
        try:
            async for chunk in self._run_synthesis(active_plan, agent_handler):
                yield chunk
        except Exception as e:
            logger.error(f"Synthesis phase crashed: {e}", exc_info=True)
            async for chunk in self._emit_event(f"❌ Synthesis phase failed: {str(e)[:200]}"):
                yield chunk
            db.update_chat(self.chat_id, research_state='failed')

    async def _run_scout(self, topic: str, agent: Any) -> AsyncGenerator[str, None]:
        """
        Iterative Scout Phase. Rebuilds history from DB every turn to ensure 
        determinism and handle suspension/resumption correctly.
        """
        today_date = get_current_date()
        turn_count = 0
        
        while True:
            turn_count += 1
            if turn_count > config.RESEARCH_SCOUT_MAX_TURNS:
                logger.warning(f"Scout reached max turn limit ({config.RESEARCH_SCOUT_MAX_TURNS}).")
                async for chunk in self._emit_event(f"❌ Scout phase reached turn limit ({config.RESEARCH_SCOUT_MAX_TURNS}). Halting."):
                    yield chunk
                # Reset chat state to prevent infinite resume loop (R3.1)
                db.update_chat(self.chat_id, research_state='failed')
                raise RuntimeError(f"Scout phase exceeded maximum turn limit of {config.RESEARCH_SCOUT_MAX_TURNS}.")

            # 1. Synchronize history from DB (Crucial for Resumption/Tools)
            db_history = db.get_messages(
                self.chat_id, 
                parent_message_id=self.parent_message_id, 
                parent_type=self.AGENT_NAME
            )
            
            # CHECK FOR SUSPENSION
            if self._is_suspended(db_history):
                break
            
            # 2. Construct the current Scout message stack
            messages = [
                {
                    "role": "system", 
                    "content": SCOUT_SYSTEM_PROMPT.format(
                        today_date=today_date
                    )
                },
                {
                    "role": "user",
                    "content": f"User research query: {topic}"
                }
            ]
            
            # --- START Event Marker ---
            if not db_history:
                async for chunk in self._emit_event(EVENT_SCOUT_START): yield chunk
            
            for m in db_history:
                if m.get("role") == "event":
                    continue

                messages.append(self._msg_from_db(m))

            # --- TURN A: Analysis (AI Turn) ---
            scout_analysis = None
            async for chunk in self._run_json_inference(
                agent=agent,
                messages=messages,
                phase_name="scout_analysis",
                schema=SCOUT_JSON_SCHEMA,
                max_tokens=config.RESEARCH_MAX_TOKENS_SCOUT,
                thinking_budget=config.RESEARCH_THINKING_BUDGET_SCOUT_TOKENS
            ):
                if isinstance(chunk, dict) and chunk.get("type") == "scout_analysis_result":
                    scout_analysis = chunk.get("data")
                else:
                    yield chunk
            
            if not scout_analysis:
                break

            # --- TURN B: Branching (Manual Tool Turns) ---
            
            # Handle Clarification (Suspension Point)
            if scout_analysis.get("clarifying_question"):
                question = scout_analysis["clarifying_question"]
                options = scout_analysis.get("clarifying_options") or []
                iteration = sum(1 for m in db_history if m.get("role") == "assistant")
                call_id = f"call_scout_mcq_{self.parent_message_id}_{iteration}"
                
                tool_call = {
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": "request_clarification",
                        "arguments": json.dumps({
                            "question": question,
                            "options": options
                        })
                    }
                }

                async for chunk in agent.run_inference_step(
                    agent_name=self.AGENT_NAME,
                    messages=[], 
                    model_name="internal",
                    custom_stream=self.emitter.stream_message(tool_calls=[tool_call])
                ):
                    yield chunk
                
                # Suspension Point: Wait for user interaction complete.
                break 

            # Handle Preliminary Search
            if scout_analysis.get("needs_search") and scout_analysis.get("preliminary_search"):
                search_params = scout_analysis["preliminary_search"]
                call_id = f"call_{uuid.uuid4().hex[:8]}"
                
                tool_call = {
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": "search_web",
                        "arguments": json.dumps({
                            "query": search_params.get("query"),
                            "topic": search_params.get("topic", "general"),
                            "time_range": search_params.get("time_range"),
                            "depth": "deep"
                        })
                    }
                }

                async for chunk in agent.run_inference_step(
                    agent_name=self.AGENT_NAME,
                    messages=[],
                    model_name="internal",
                    custom_stream=self.emitter.stream_message(tool_calls=[tool_call])
                ):
                    yield chunk
                
                # Result is now in DB history. Loop back to re-analyze.
                continue

            # No more tools needed; scouting finalized.
            async for chunk in self._emit_event(EVENT_SCOUT_FINALIZED): yield chunk
            yield {"type": "scout_context", "data": scout_analysis.get("context_notes", "")}
            break

    async def _run_planner(self, topic: str, scout_context: str, agent: Any) -> AsyncGenerator[str, None]:
        """
        Phase 1: Plan Generation.
        Generates a strategy, presents it via FileSystem with status:pending,
        and waits for user approval/feedback.
        """
        today_date = get_current_date()
        iteration = 0
        
        while True:
            iteration += 1
            if iteration > config.RESEARCH_MAX_PLAN_RETRIES + 2:
                logger.warning(f"Planner reached max iteration limit.")
                async for chunk in self._emit_event(f"❌ Plan generation exceeded maximum attempts ({config.RESEARCH_MAX_PLAN_RETRIES}). Halting."):
                    yield chunk
                # Reset chat state to prevent infinite resume loop (R3.1)
                db.update_chat(self.chat_id, research_state='failed')
                raise RuntimeError(f"Planner phase exceeded maximum iteration limit of {config.RESEARCH_MAX_PLAN_RETRIES + 2}.")

            # 1. Sync History to determine current state
            db_history = db.get_messages(
                self.chat_id, 
                parent_message_id=self.parent_message_id, 
                parent_type=self.AGENT_NAME
            )

            # --- Isolate Planner-specific history ---
            # We only want messages that happened AFTER the scouting phase ended.
            planner_history = []
            try:
                # Find the index of the hand-off event
                boundary_idx = next(i for i, m in enumerate(db_history) 
                                   if m.get("role") == "event" and EVENT_SCOUT_FINALIZED in m.get("content", ""))
                planner_history = db_history[boundary_idx + 1:]
            except StopIteration:
                # If not found (e.g. first run), history is empty
                planner_history = []
            
            # CHECK FOR SUSPENSION: If we have an unresolved MCQ/Clarification tool call, we stop and wait.
            if self._is_suspended(planner_history):
                break
            
            # Count assistant messages in this phase for deterministic turn IDs
            iteration = sum(1 for m in planner_history if m.get("role") == "assistant")

            # --- START Event Marker (Hand-off from Scout) ---
            if db_history and db_history[-1].get("role") == "event" and EVENT_SCOUT_FINALIZED in db_history[-1].get("content", ""):
                async for chunk in self._emit_event(EVENT_PLAN_START): yield chunk
            
            # --- Check for Approval Signal via Clarification Tool Result ---
            # We look for the MOST RECENT tool result for 'request_clarification'
            last_tool_res = next((m for m in reversed(db_history) if m.get("role") == "tool" and m.get("name") == "request_clarification"), None)
            if last_tool_res and last_tool_res.get("content") == PLAN_APPROVAL_SIGNAL:
                # Find the file_system ID created IN THIS SESSION
                create_tool_res = next((m for m in reversed(planner_history) if m.get("role") == "tool" and m.get("name") == "create_fs_file"), None)
                plan_file_system_id = None
                if create_tool_res and create_tool_res.get("content"):
                    res_data = self._safe_json_loads(create_tool_res["content"], {})
                    plan_file_system_id = res_data.get("file_system_id") or create_tool_res.get("content") # Fallback to raw string
                
                if plan_file_system_id:
                    # Deterministic state switch: Flip file_system type to lock buttons
                    async for chunk in agent.run_inference_step(
                        agent_name=self.AGENT_NAME,
                        messages=[],
                        model_name="internal",
                        custom_stream=self.emitter.stream_message(tool_calls=[{
                            "id": f"call_approve_file_system_{self.parent_message_id}_{iteration}",
                            "type": "function",
                            "function": {
                                "name": "patch_file_system",
                                "arguments": json.dumps({
                                    "id": plan_file_system_id,
                                    "file_system_type": "research_plan_approved"
                                })
                            }
                        }])
                    ):
                        yield chunk
                
                # Finalize phase transition
                async for chunk in self._emit_event(EVENT_PLAN_APPROVED): yield chunk

                # Plan is finalized and locked. Exit loop to proceed to Phase 2.
                return

            # --- Branch: Iterate (New Task or Refining Feedback) ---
            messages = [
                {"role": "system", "content": PLANNER_SYSTEM_PROMPT.format(
                    today_date=today_date,
                    max_queries_per_section=config.RESEARCH_MAX_QUERIES_PER_SECTION,
                    max_total_queries=config.RESEARCH_MAX_TOTAL_QUERIES
                )},
                {
                    "role": "user",
                    "content": f"Scout context: {scout_context}\n\nUser research query: {topic}"
                }
            ]
            
            for m in planner_history:
                if m.get("role") == "event":
                    continue
                messages.append(self._msg_from_db(m))

            # Turn A: AI Plan Generation
            plan_json = None
            async for chunk in self._run_json_inference(
                agent=agent,
                messages=messages,
                phase_name="research_plan",
                schema=PLAN_GENERATOR_JSON_SCHEMA,
                max_tokens=config.RESEARCH_MAX_TOKENS_PLANNING,
                thinking_budget=config.RESEARCH_THINKING_BUDGET_PLANNING_TOKENS
            ):
                if isinstance(chunk, dict) and chunk.get("type") == "research_plan_result":
                    plan_json = chunk.get("data")
                else:
                    yield chunk
            
            if not plan_json:
                break

            # Validate generated plan (4.1)
            is_valid, reason = self._validate_plan(plan_json)
            if not is_valid:
                logger.warning(f"Generated plan invalid: {reason}. Retrying...")
                async for chunk in self._emit_event(f"⚠️ Generated plan was invalid ({reason}). Retrying strategy..."):
                    yield chunk
                continue

            # Persist draft plan for continuity
            db.add_collection(
                chat_id=self.chat_id,
                parent_message_id=self.parent_message_id,
                parent_type=self.AGENT_NAME,
                collection_type="research_plan",
                items=plan_json,
                overwrite=True
            )

            # --- Turn B: Presentation (Manual Turn Injection) ---
            md_content = _format_plan_as_markdown(plan_json)
            
            # 1. Prepare FileSystem Management Tool Call
            create_tool_res = next((m for m in reversed(planner_history) if m.get("role") == "tool" and m.get("name") == "create_fs_file"), None)
            plan_file_system_id = None
            if create_tool_res and create_tool_res.get("content"):
                res_data = self._safe_json_loads(create_tool_res["content"], {})
                plan_file_system_id = res_data.get("file_system_id") or create_tool_res.get("content") # Fallback to raw string
            
            if plan_file_system_id:
                file_system_tool_call = {
                    "id": f"call_report_file_system_{self.parent_message_id}_{iteration}",
                    "type": "function",
                    "function": {
                        "name": "patch_file_system",
                        "arguments": json.dumps({
                            "id": plan_file_system_id,
                            "title": plan_json.get("title", "Research Plan"),
                            "content": md_content
                        })
                    }
                }
            else:
                file_system_tool_call = {
                    "id": f"call_report_file_system_{self.parent_message_id}_{iteration}",
                    "type": "function",
                    "function": {
                        "name": "create_fs_file",
                        "arguments": json.dumps({
                            "title": plan_json.get("title", "Research Plan"),
                            "content": md_content,
                            "file_system_type": "research_plan_pending",
                            "language": "markdown"
                        })
                    }
                }

            # 2. Prepare MCQ Tool Call (Approval Anchor)
            mcq_tool_call = {
                "id": f"call_planner_mcq_{self.parent_message_id}_{iteration}",
                "type": "function",
                "function": {
                    "name": "request_clarification",
                    "arguments": json.dumps({
                        "question": "Do you approve of this research plan?",
                        "options": [PLAN_APPROVAL_SIGNAL]
                    })
                }
            }

            # 3. Emit both tool calls
            async for chunk in agent.run_inference_step(
                agent_name=self.AGENT_NAME,
                messages=[],
                model_name="internal",
                custom_stream=self.emitter.stream_message(tool_calls=[file_system_tool_call, mcq_tool_call])
            ):
                yield chunk

            # Suspension Point: Wait for user interaction complete.
            # The task was blocked. Now the tool result is in DB. We loop back to Step 1.
            continue

    async def _run_executor(self, plan: dict, agent: Any) -> AsyncGenerator[str, None]:
        """
        Phase 2: Execution. Iterates through the plan's sections. 
        State is inferred entirely from the database on every turn.
        """
        title = plan.get("title", "Research Report")
        file_system_title = f"Report: {title[:40]}"
        
        # Check if we already created the file_system in a previous turn
        colls = db.get_collections(self.chat_id, parent_message_id=self.parent_message_id, parent_type=self.AGENT_NAME)
        file_system_coll = next((c for c in colls if c.get("collection_type") == "report_file_system_id"), None)
        
        if file_system_coll and file_system_coll.get("items"):
            self.file_system_id = self._safe_json_loads(file_system_coll["items"], "")
        else:
            try:
                from backend.file_system.manager import create_fs_file
                import re
                
                safe_title = re.sub(r'[^\w\s\-]', '_', title[:30]).strip().replace(' ', '_')
                report_path = f"Research_Reports/{safe_title}.md"
                
                file_system_res = await create_fs_file(
                    chat_id=self.chat_id,
                    path=report_path,
                    content="",
                    file_system_type="research_report"
                )
                self.file_system_id = file_system_res["file_system_id"]
                db.add_collection(
                    chat_id=self.chat_id,
                    parent_message_id=self.parent_message_id,
                    parent_type=self.AGENT_NAME,
                    collection_type="report_file_system_id",
                    items=self.file_system_id,
                    overwrite=True
                )
            except Exception as e:
                logger.error(f"FileSystem creation failed: {e}", exc_info=True)
                async for chunk in self._emit_event("⚠️ FileSystem creation failed. Content will be stored without live preview."):
                    yield chunk
                self.file_system_id = None
                # Cannot proceed without a file_system ID to track report state
                return
            
        sections = plan.get("sections", [])
        
        prev_pending = None
        stall_count = 0

        while True:
            # 1. Sync and Gather Summaries for Context
            db_history = db.get_messages(self.chat_id, parent_message_id=self.parent_message_id, parent_type=self.AGENT_NAME)
            colls = db.get_collections(self.chat_id, parent_message_id=self.parent_message_id, parent_type=self.AGENT_NAME)
            
            summaries = [self._safe_json_loads(c.get("items", ""), "") for c in colls if c.get("collection_type", "").endswith("_summary")]
            accumulated_summaries_text = "\n\n---\n\n".join(summaries) if summaries else "No prior sections completed yet." 
            
            # 2. Determine Next Section
            completed_indices = {
                int(m.get("content", "").split(EVENT_SECTION_PREFIX)[1].split(" ")[0])
                for m in db_history 
                if m.get("role") == "event" and m.get("content", "").startswith(EVENT_SECTION_PREFIX) and m.get("content", "").endswith(EVENT_SECTION_COMPLETE_SUFFIX)
            }
            
            pending_indices = [i for i in range(len(sections)) if i not in completed_indices]
            
            if not pending_indices:
                async for chunk in self._emit_event(EVENT_ALL_SECTIONS_DONE): yield chunk
                break
            
            # Stall Detection (2.2)
            if pending_indices == prev_pending:
                stall_count += 1
                if stall_count >= config.RESEARCH_MAX_SECTION_STALLS:
                    stalled_idx = pending_indices[0]
                    logger.error(f"Section {stalled_idx} stalled after {config.RESEARCH_MAX_SECTION_STALLS} attempts. Halting.")
                    async for chunk in self._emit_event(f"❌ Section {stalled_idx} failed repeatedly. Research halted to prevent incomplete report."): yield chunk
                    raise RuntimeError(f"Section {stalled_idx} stalled repeatedly after {config.RESEARCH_MAX_SECTION_STALLS} attempts.")
            else:
                stall_count = 0
                prev_pending = list(pending_indices)

            # Sequential execution (standard)
            idx = pending_indices[0]
            try:
                async for chunk in self._run_single_section(idx, sections[idx], plan, sections, accumulated_summaries_text, agent):
                    yield chunk
            except Exception as e:
                logger.error(f"Section {idx} failed fatally: {e}", exc_info=True)
                async for chunk in self._emit_event(f"❌ Section {idx} failed: {str(e)[:200]}. Research halted."):
                    yield chunk
                raise

    async def _run_single_section(self, current_idx, current_section, plan, sections, accumulated_summaries_text, agent) -> AsyncGenerator[str, None]:
        """Runs the state machine for a single research section with a unified global history."""
        state = SectionState(current_idx)
        prefix = f"[Section {current_idx}] "
        
        while True:
            db_history = db.get_messages(self.chat_id, parent_message_id=self.parent_message_id, parent_type=self.AGENT_NAME)
            self._parse_section_state(db_history, state)

            if not state.has_initial_search:
                # STATE 0: Start of Section -> Run Initial Searches
                async for chunk in self._emit_event(f"{prefix}{EVENT_SECTION_START_PREFIX}{current_idx}", parent_type=self.AGENT_NAME): yield chunk
                async for chunk in self._emit_event(f"{prefix}{EVENT_INITIAL_SEARCHES_PREFIX}{current_idx}...", parent_type=self.AGENT_NAME): yield chunk
                
                search_payload = ""
                for search_attempt in range(config.RESEARCH_SEARCH_RETRIES + 1):
                    search_payload = "## INITIAL SEARCH RESULTS\n"
                    try:
                        search_payload += await self._execute_internal_searches(current_section.get("queries", []), is_followup=False)
                    except SearchLimitReached:
                        raise  # not retried: the section fails with the limit message
                    except Exception as search_err:
                        logger.warning(f"Initial searches attempt {search_attempt + 1} failed: {search_err}")
                        search_payload = ""

                    if search_payload.strip() and search_payload.strip() != "## INITIAL SEARCH RESULTS":
                        break  # Got usable results

                    if search_attempt < config.RESEARCH_SEARCH_RETRIES:
                        async for chunk in self._emit_event(
                            f"{prefix}⚠️ No usable search results. Retrying ({search_attempt + 2}/{config.RESEARCH_SEARCH_RETRIES + 1})...",
                            parent_type=self.AGENT_NAME
                        ): yield chunk
                    else:
                        raise RuntimeError(
                            f"All initial searches for section {current_idx} returned zero usable results after {config.RESEARCH_SEARCH_RETRIES + 1} attempts."
                        )

                db.add_collection(

                    chat_id=self.chat_id,
                    parent_message_id=self.parent_message_id,
                    parent_type=self.AGENT_NAME,
                    collection_type=f"section_{current_idx}_initial_searches",
                    items=search_payload
                )
                async for chunk in self._emit_event(f"{prefix}{EVENT_INITIAL_SEARCHES_DONE}", parent_type=self.AGENT_NAME): yield chunk
                continue 
                
            elif not state.has_reflection:
                # STATE 1: Reflection Phase
                async for chunk in self._emit_event(f"{prefix}{EVENT_REFLECTION_START}", parent_type=self.AGENT_NAME): yield chunk
                
                messages = self._build_continuous_context(
                    current_idx, current_section, plan, sections, 
                    accumulated_summaries_text, db_history, "Reflection"
                )
                
                async for chunk in self._run_json_inference(
                    agent=agent,
                    messages=messages,
                    phase_name="reflection",
                    schema=REFLECTION_JSON_SCHEMA,
                    max_tokens=config.RESEARCH_MAX_TOKENS_REFLECTION,
                    thinking_budget=config.RESEARCH_THINKING_BUDGET_REFLECTION_TOKENS,
                    parent_type=self.AGENT_NAME
                ):
                    if isinstance(chunk, dict) and chunk.get("type") == "reflection_result": continue
                    yield chunk
                    
                async for chunk in self._emit_event(f"{prefix}{EVENT_REFLECTION_DONE}", parent_type=self.AGENT_NAME): yield chunk        
                continue
                
            elif not state.has_gap_searches:
                # STATE 1.5: Gap Searches
                async for chunk in self._emit_event(f"{prefix}{EVENT_GAP_SEARCHES_START}", parent_type=self.AGENT_NAME): yield chunk
                
                reflection_analysis = None
                reflection_msg = self._get_assistant_output_for_phase(db_history, f"{prefix}{EVENT_REFLECTION_DONE}")
                if reflection_msg:
                    reflection_analysis = _extract_json_from_text(reflection_msg.get("content", ""))
                
                followup_payload = "\n## FOLLOW-UP SEARCH RESULTS\n"
                if reflection_analysis and reflection_analysis.get("gaps"):
                    async for chunk in self._emit_event(f"{prefix}{EVENT_GAP_SEARCHES_IN_PROGRESS}", parent_type=self.AGENT_NAME): yield chunk
                    try:
                        followup_payload += await self._execute_internal_searches(reflection_analysis.get("gaps", []), is_followup=True)
                    except SearchLimitReached as limit:
                        # Keep the section's earlier results and move on; the DONE event below ends this state.
                        logger.warning(f"Follow-up searches skipped: {limit}")
                    
                    if not followup_payload.strip() or followup_payload.strip() == "## FOLLOW-UP SEARCH RESULTS":
                         async for chunk in self._emit_event(f"{prefix}⚠️ No usable follow-up search results found. Proceeding with available context.", parent_type=self.AGENT_NAME): yield chunk

                    db.add_collection(
                        chat_id=self.chat_id,
                        parent_message_id=self.parent_message_id,
                        parent_type=self.AGENT_NAME,
                        collection_type=f"section_{current_idx}_followup_searches",
                        items=followup_payload
                    )
                        
                async for chunk in self._emit_event(f"{prefix}{EVENT_GAP_SEARCHES_DONE}", parent_type=self.AGENT_NAME): yield chunk
                continue
                
            elif not state.has_triage:
                # STATE 2: Triage Phase
                async for chunk in self._emit_event(f"{prefix}{EVENT_TRIAGE_START}", parent_type=self.AGENT_NAME): yield chunk
                messages = self._build_continuous_context(
                    current_idx, current_section, plan, sections, 
                    accumulated_summaries_text, db_history, "Triage"
                )
                
                async for chunk in self._run_json_inference(
                    agent=agent,
                    messages=messages,
                    phase_name="triage",
                    schema=TRIAGE_JSON_SCHEMA,
                    max_tokens=config.RESEARCH_MAX_TOKENS_TRIAGE,
                    thinking_budget=config.RESEARCH_THINKING_BUDGET_TRIAGE_TOKENS,
                    parent_type=self.AGENT_NAME
                ):
                    if isinstance(chunk, dict) and chunk.get("type") == "triage_result": continue
                    yield chunk
                    
                async for chunk in self._emit_event(f"{prefix}{EVENT_TRIAGE_DONE}", parent_type=self.AGENT_NAME): yield chunk
                continue
                
            elif not state.has_writer:
                # STATE 3: Section Writer
                async for chunk in self._emit_event(f"{prefix}{EVENT_WRITER_START}", parent_type=self.AGENT_NAME): yield chunk
                messages = self._build_continuous_context(
                    current_idx, current_section, plan, sections, 
                    accumulated_summaries_text, db_history, "Writer"
                )
                
                async for chunk in self._run_json_inference(
                    agent=agent,
                    messages=messages,
                    phase_name="section_draft",
                    schema=WRITER_JSON_SCHEMA,
                    max_tokens=config.RESEARCH_MAX_TOKENS_STEP_WRITER,
                    thinking_budget=config.RESEARCH_THINKING_BUDGET_STEP_WRITER_TOKENS,
                    parent_type=self.AGENT_NAME
                ):
                    if isinstance(chunk, dict) and chunk.get("type") == "section_draft_result": continue
                    yield chunk
                
                last_msg = db.get_last_assistant_message(self.chat_id, parent_message_id=self.parent_message_id, parent_type=self.AGENT_NAME)
                if not last_msg:
                    raise RuntimeError(f"Writer phase for section {current_idx} produced no output.")

                parsed = _extract_json_from_text(last_msg.get("content", ""))
                if not parsed or "markdown_content" not in parsed:
                    raise RuntimeError(f"Writer phase for section {current_idx} failed to produce valid markdown content.")

                content_to_append = parsed["markdown_content"]
                if len(content_to_append.strip()) < config.RESEARCH_MIN_SECTION_LEN:
                    raise RuntimeError(f"Writer phase for section {current_idx} produced content below minimum length ({len(content_to_append)} < {config.RESEARCH_MIN_SECTION_LEN}).")

                db.add_collection(
                    chat_id=self.chat_id,
                    parent_message_id=self.parent_message_id,
                    parent_type=self.AGENT_NAME,
                    collection_type=f"section_{current_idx}_draft",
                    items=content_to_append,
                    overwrite=True
                )
                # Serialized FileSystem Update
                try:
                    async with self.file_system_lock:
                        from backend.file_system.manager import get_fs_file_content, update_fs_file_content
                        current_file_system_content = await get_fs_file_content(self.file_system_id, self.chat_id)
                        if current_file_system_content is None:
                            current_file_system_content = ""
                        new_content = current_file_system_content + "\n\n" + content_to_append
                        await update_fs_file_content(self.file_system_id, self.chat_id, new_content, author="research_agent")
                except Exception as e:
                    logger.error(f"FileSystem update failed for section {current_idx}: {e}", exc_info=True)
                    async for chunk in self._emit_event(f"{prefix}❌ FileSystem update failed for section {current_idx}: {str(e)[:200]}", parent_type=self.AGENT_NAME):
                        yield chunk
                    raise e
                    
                async for chunk in self._emit_event(f"{prefix}{EVENT_WRITER_DONE}", parent_type=self.AGENT_NAME): yield chunk
                continue
                
            elif not state.has_summary:
                # If this is the last section, we can skip the summary
                # (Summaries are primarily used as context for subsequent sections)
                if current_idx == len(sections) - 1:
                    logger.info(f"Skipping summary for final section {current_idx}")
                    async for chunk in self._emit_event(f"{EVENT_SECTION_PREFIX}{current_idx}{EVENT_SECTION_COMPLETE_SUFFIX}", parent_type=self.AGENT_NAME): yield chunk
                    break

                # STATE 4: Summarize
                async for chunk in self._emit_event(f"{prefix}{EVENT_SUMMARY_START}", parent_type=self.AGENT_NAME): yield chunk
                messages = self._build_continuous_context(
                    current_idx, current_section, plan, sections, 
                    accumulated_summaries_text, db_history, "Summary"
                )
                
                async for chunk in self._run_json_inference(
                    agent=agent,
                    messages=messages,
                    phase_name="section_summary",
                    schema=SUMMARY_JSON_SCHEMA,
                    max_tokens=config.RESEARCH_MAX_TOKENS_SUMMARY,
                    thinking_budget=config.RESEARCH_THINKING_BUDGET_SUMMARY_TOKENS,
                    parent_type=self.AGENT_NAME
                ):
                    if isinstance(chunk, dict) and chunk.get("type") == "section_summary_result": continue
                    yield chunk
                
                last_msg = db.get_last_assistant_message(self.chat_id, parent_message_id=self.parent_message_id, parent_type=self.AGENT_NAME)
                if not last_msg:
                    raise RuntimeError(f"Summary phase for section {current_idx} produced no output.")

                parsed_summary = _extract_json_from_text(last_msg.get("content", ""))
                if not parsed_summary or "summary_points" not in parsed_summary:
                    raise RuntimeError(f"Summary phase for section {current_idx} failed to produce valid summary points.")

                # Join array of strings into a single markdown summary (6.1)
                summary_points = parsed_summary["summary_points"]
                summary_text = "\n".join([f"- {p}" for p in summary_points]) if isinstance(summary_points, list) else str(summary_points)
                db.add_collection(
                    chat_id=self.chat_id,
                    parent_message_id=self.parent_message_id,
                    parent_type=self.AGENT_NAME,
                    collection_type=f"section_{current_idx}_summary",
                    items=summary_text,
                    overwrite=True
                )
                
                async for chunk in self._emit_event(f"{prefix}{EVENT_SUMMARY_DONE}", parent_type=self.AGENT_NAME): yield chunk
                async for chunk in self._emit_event(f"{EVENT_SECTION_PREFIX}{current_idx}{EVENT_SECTION_COMPLETE_SUFFIX}", parent_type=self.AGENT_NAME): yield chunk
                break
            else:
                # STATE 5: Done or Unhandled
                break

    def _parse_section_state(self, section_history: List[Dict], state: SectionState):
        """
        Parses the unified global history to determine which state-machine 
        milestones have already been completed for this specific section.
        """
        state.has_initial_search = False
        state.has_reflection = False
        state.has_gap_searches = False
        state.has_triage = False
        state.has_writer = False
        state.has_summary = False
        
        prefix = f"[Section {state.index}] "
        
        # Traverse in descending order to find the latest completed state for this section
        for m in reversed(section_history):
            if m.get("role") == "event":
                content = m.get("content", "")
                if not content.startswith(prefix):
                    continue
                
                phase_content = content[len(prefix):]
                
                # Due to sequential execution, a later completed phase implies earlier ones are done
                if EVENT_SUMMARY_DONE in phase_content:
                    state.has_summary = state.has_writer = state.has_triage = state.has_gap_searches = state.has_reflection = state.has_initial_search = True
                    break
                elif EVENT_WRITER_DONE in phase_content:
                    state.has_writer = state.has_triage = state.has_gap_searches = state.has_reflection = state.has_initial_search = True
                    break
                elif EVENT_TRIAGE_DONE in phase_content:
                    state.has_triage = state.has_gap_searches = state.has_reflection = state.has_initial_search = True
                    break
                elif EVENT_GAP_SEARCHES_DONE in phase_content:
                    state.has_gap_searches = state.has_reflection = state.has_initial_search = True
                    break
                elif EVENT_REFLECTION_DONE in phase_content:
                    state.has_reflection = state.has_initial_search = True
                    break
                elif EVENT_INITIAL_SEARCHES_DONE in phase_content:
                    state.has_initial_search = True
                    break
        
    def _get_assistant_output_for_phase(self, section_history: List[Dict], completion_event_text: str) -> Dict | None:
        """
        Locates the assistant message that belongs to a specific phase by anchoring backward 
        from its explicit completion event.
        """
        for i, m in enumerate(section_history):
            if m.get("role") == "event" and m.get("content") == completion_event_text:
                # Look backward for the immediate preceding assistant message
                for j in range(i - 1, -1, -1):
                    if section_history[j].get("role") in ["assistant"]:
                        return section_history[j]
        return None

    def _build_continuous_context(
        self,
        current_idx: int,
        current_section: Dict,
        plan: Dict,
        sections: List[Dict],
        accumulated_summaries_text: str,
        section_history: List[Dict],
        target_phase: str
    ) -> List[Dict]:
        """
        Dynamically reconstructs the exact LLM conversation history for the current section
        from the global history stream.
        target_phase can be: "Reflection", "Triage", "Writer", "Summary"
        """
        colls = db.get_collections(self.chat_id, parent_message_id=self.parent_message_id, parent_type=self.AGENT_NAME)
        
        today_date = get_current_date()
        messages = [{"role": "system", "content": RESEARCH_EXECUTOR_SYSTEM_PROMPT.format(today_date=today_date)}]
        
        prefix = f"[Section {current_idx}] "

        # 1. Reflection Phase
        initial_search_coll = next((c for c in colls if c.get("collection_type") == f"section_{current_idx}_initial_searches"), None)
        init_payload = self._safe_json_loads(initial_search_coll.get("items", ""), "No search results found.") if initial_search_coll else ""
        
        reflection_prompt = RESEARCH_REFLECTION_PROMPT.format(
            today_date=today_date,
            original_topic=plan.get("title", "Research Plan"),
            section_heading=current_section.get("heading", ""),
            section_description=current_section.get("description", ""),
            section_queries=", ".join([q.get("query") or q.get("search", "") for q in current_section.get("queries", [])]),
            section_number=current_idx + 1,
            total_sections=len(sections),
            remaining_sections=len(sections) - (current_idx + 1),
            full_plan=json.dumps(plan, indent=2), 
            accumulated_summaries=accumulated_summaries_text,
            max_gaps=config.RESEARCH_MAX_GAPS_PER_SECTION
        )
        messages.append({"role": "user", "content": f"{reflection_prompt}\n\nHere is the initial data gathered for section '{current_section.get('heading')}':\n\n{init_payload}"})
        if target_phase == "Reflection": return messages

        reflection_msg = self._get_assistant_output_for_phase(section_history, f"{prefix}{EVENT_REFLECTION_DONE}")
        if reflection_msg:
            messages.append(self._msg_from_db(reflection_msg))
        else:
            # Defensive placeholder (4.6)
            messages.append({"role": "assistant", "content": '{"analysis": "Section analysis incomplete.", "gaps": []}'})
            
        # 2. Triage Phase
        followup_search_coll = next((c for c in colls if c.get("collection_type") == f"section_{current_idx}_followup_searches"), None)
        followup_payload = self._safe_json_loads(followup_search_coll.get("items", ""), "") if followup_search_coll else ""
                
        triage_prompt = RESEARCH_TRIAGE_PROMPT.format(
            section_heading=current_section.get("heading", ""),
            today_date=today_date,
            accumulated_summaries=accumulated_summaries_text
        )
        if followup_payload:
            triage_user_msg = f"{triage_prompt}\n\nHere are the NEW follow-up search results gathered to fill the gaps:\n\n{followup_payload}\n\nPlease extract the exhaustive core facts using BOTH the initial data provided earlier and these new follow-up results."
        else:
            triage_user_msg = f"{triage_prompt}\n\nNo follow-up searches were needed. Please extract the exhaustive core facts using the initial data provided earlier in this conversation."
        messages.append({"role": "user", "content": triage_user_msg})
        if target_phase == "Triage": return messages

        triage_msg = self._get_assistant_output_for_phase(section_history, f"{prefix}{EVENT_TRIAGE_DONE}")
        if triage_msg:
            messages.append(self._msg_from_db(triage_msg))
        else:
            # Defensive placeholder (4.6)
            messages.append({"role": "assistant", "content": "I have extracted the core facts from the provided data."})
        
        # 3. Writer Phase
        writer_prompt = RESEARCH_STEP_WRITER_PROMPT.format(
            section_heading=current_section.get("heading", ""),
            accumulated_summaries=accumulated_summaries_text,
            entity_glossary="None yet.",
            mode_guidance="Be strictly factual and objective.",
            today_date=today_date
        )
        messages.append({"role": "user", "content": f"{writer_prompt}\n\nUse the core facts you just extracted in the previous turn as your strict blueprint, but use the raw text from the initial and follow-up data provided earlier to flesh out the narrative."})
        if target_phase == "Writer": return messages
        
        writer_msg = self._get_assistant_output_for_phase(section_history, f"{prefix}{EVENT_WRITER_DONE}")
        if writer_msg:
            messages.append(self._msg_from_db(writer_msg))
        else:
            # Defensive placeholder (4.6)
            messages.append({"role": "assistant", "content": "Section narrative drafted based on available facts."})

        # 4. Summary Phase
        messages.append({"role": "user", "content": RESEARCH_STEP_SUMMARY_PROMPT.format(today_date=today_date)})
        return messages

    async def _execute_internal_searches(self, queries: List[Dict], is_followup: bool = False) -> str:
        """
        Executes internal MCP searches, deduplicates against a global URL registry, 
        and formats the output payload, respecting all config constraints.
        """
        from backend import config
        from backend.mcp_client import tavily_client

        # Ensure MCP session is alive (7.5 — auto-reconnect)
        await tavily_client.connect()
        
        # Pull global registry of visited URLs
        colls = db.get_collections(self.chat_id, parent_message_id=self.parent_message_id, parent_type=self.AGENT_NAME)
        visited_coll = next((c for c in colls if c.get("collection_type") == "visited_urls"), None)
        # Use a list to maintain stable order for citations
        visited_urls = self._safe_json_loads(visited_coll.get("items", "[]"), []) if visited_coll else []
        
        payload = ""
        top_k = config.RESEARCH_SELECT_TOP_URLS_FOLLOWUP_COUNT if is_followup else config.RESEARCH_SELECT_TOP_URLS_COUNT
        min_len = config.RESEARCH_EXTRACT_MIN_RAW_CONTENT
        
        search_errors = []
        for q in queries:
            query_text = q.get("query") or q.get("search", "")
            if not query_text: continue

            # One query is one hit against the chat owner's daily limit. Outside the try below, so the generic
            # handler (which records a failed query and moves on) cannot swallow it.
            limit_message = check_search_limit(self.chat_id)
            if limit_message:
                raise SearchLimitReached(limit_message)

            try:
                mcp_res = await _execute_mcp_tool(
                    tavily_client, 
                    "async_tavily_search_tool", 
                    {"query": query_text, "max_results": config.RESEARCH_TAVILY_MAX_RESULTS_FOLLOWUP if is_followup else config.RESEARCH_TAVILY_MAX_RESULTS_INITIAL, "depth": "deep"},
                    chat_id=self.chat_id,
                    timeout=config.TIMEOUT_TAVILY_SEARCH_ASYNC # 60s
                )
                res_json = self._safe_json_loads(mcp_res.content[0].text, {})
                results = res_json.get("results", [])
                
                accepted = 0
                for r in results:
                    if accepted >= top_k:
                        break
                        
                    url = r.get("url")
                    if not url or url in visited_urls:
                        continue
                        
                    content = r.get("raw_content", r.get("content", ""))
                    if not content or len(content.strip()) < min_len:
                        continue
                        
                    if url not in visited_urls:
                        visited_urls.append(url)
                    source_id = visited_urls.index(url) + 1
                        
                    payload += f"\n---\n[Source {source_id}]: {url}\n{content[:config.RESEARCH_CONTENT_CHUNK_LIMIT]}\n"
                    accepted += 1
            except CircuitOpenError as e:
                logger.error(f"Circuit breaker open for search: {query_text}")
                search_errors.append(f"Circuit open: {query_text}")
                continue
            except Exception as e:
                logger.error(f"Internal search failed for '{query_text}': {e}")
                search_errors.append(f"Search failed: {query_text}: {e}")
                continue
                
        if search_errors and not payload.strip():
            # All searches failed AND we got no usable content
            raise RuntimeError(f"All searches failed: {'; '.join(search_errors[:3])}")
                
        # Save updated global registry
        if visited_urls:
            db.add_collection(
                chat_id=self.chat_id,
                parent_message_id=self.parent_message_id,
                parent_type=self.AGENT_NAME,
                collection_type="visited_urls",
                items=visited_urls,
                overwrite=True
            )
        return payload

    async def _run_synthesis(self, plan: dict, agent: Any) -> AsyncGenerator[str, None]:
        """
        Phase 3: Assembly & Audit. Runs post-processing (citations) and then the unified Auditor loop
        to finalize the file_system report.
        """
        from datetime import datetime
        from backend import config

        if not getattr(self, 'file_system_id', None):
            colls = db.get_collections(self.chat_id, parent_message_id=self.parent_message_id, parent_type=self.AGENT_NAME)
            file_system_coll = next((c for c in colls if c.get("collection_type") == "report_file_system_id"), None)
            if file_system_coll:
                self.file_system_id = self._safe_json_loads(file_system_coll["items"], "")
            else:
                logger.error("No file_system_id found for synthesis phase.")
                async for chunk in self._emit_event("❌ Report file_system is missing. Cannot finalize."):
                    yield chunk
                return

        today_date = get_current_date()
        
        # 1. Post-Processing Hook
        async for chunk in self._emit_event(EVENT_SYNTHESIS_POST): yield chunk
        from backend.file_system.manager import get_fs_file_content, update_fs_file_content
        current_content = await get_fs_file_content(self.file_system_id, self.chat_id)
        if current_content:
            try:
                colls = db.get_collections(self.chat_id, parent_message_id=self.parent_message_id, parent_type=self.AGENT_NAME)
                visited_urls_coll = next((c for c in colls if c.get("collection_type") == "visited_urls"), None)
                visited_urls = self._safe_json_loads(visited_urls_coll["items"], []) if visited_urls_coll and visited_urls_coll.get("items") else []
                if not isinstance(visited_urls, list):
                    logger.warning(f"visited_urls is not a list: {type(visited_urls)}. Defaulting to empty.")
                    visited_urls = []
                    
                source_registry = {i+1: {"url": url} for i, url in enumerate(visited_urls)}
                
                processed_report, references_list = _normalize_citations(current_content, source_registry)
                processed_report = _strip_report_images(processed_report)
                
                # Strip invalid citations (3.1)
                from .research_utils import _strip_invalid_citations
                valid_ids = set(source_registry.keys())
                processed_report = _strip_invalid_citations(processed_report, valid_ids)
                
                if references_list:
                    processed_report += "\n\n## References\n" + "\n".join(references_list)
                else:
                    processed_report += "\n\n## References\nNo external citations were used in this report.\n"
                    
                await update_fs_file_content(self.file_system_id, self.chat_id, processed_report, author="system")
            except Exception as e:
                logger.error(f"Synthesis post-processing failed: {e}", exc_info=True)
                async for chunk in self._emit_event(f"❌ Synthesis post-processing failed: {str(e)[:200]}"):
                    yield chunk
                raise e
        
        # 2. Tool-Calling Auditor Loop
        from backend.tools import ToolRegistry
        from .prompts import RESEARCH_AUDITOR_PROMPT, RESEARCH_FINAL_SYNTHESIS_PROMPT
        
        target_marker = EVENT_SYNTHESIS_START
        # Emit marker ONLY if it doesn't exist yet to keep history clean on resumption
        history_for_marker = db.get_messages(self.chat_id, parent_message_id=self.parent_message_id, parent_type=self.AGENT_NAME)
        if not any(m.get("role") == "event" and m.get("content") == target_marker for m in history_for_marker):
            async for chunk in self._emit_event(target_marker): yield chunk

        edit_turn_count = 0
        while True:
            db_history = db.get_messages(self.chat_id, parent_message_id=self.parent_message_id, parent_type=self.AGENT_NAME)
            
            # Isolate Auditor's history by finding the start of this phase
            start_idx = -1
            for i, m in enumerate(db_history):
                if m.get("role") == "event" and m.get("content") == target_marker:
                    start_idx = i
                    
            auditor_history = db_history[start_idx + 1:] if start_idx != -1 else []
            
            # CHECK FOR SUSPENSION
            if self._is_suspended(auditor_history):
                break
            
            messages = [{"role": "system", "content": RESEARCH_AUDITOR_PROMPT.format(today_date=today_date, file_system_id=self.file_system_id)}]
            
            # User instruction comes ONCE, after system prompt, before history
            messages.append({"role": "user", "content": f"The report is located in the file_system with ID: {self.file_system_id}. Please audit it now."})

            for m in auditor_history:
                if m.get("role") in ["assistant", "tool", "user"]:
                    messages.append(self._msg_from_db(m))
            
            task_list = db.get_task_list(self.chat_id, parent_id=self.parent_message_id, parent_type=self.AGENT_NAME)
            
            # STRICT MECHANICAL ENFORCEMENT: Audit checklist before action.
            # If no task list exists, the auditor physically cannot perform any other action.
            if not task_list:
                active_tools = [ToolRegistry.get_spec("manage_task_list").to_openai_schema()]
            else:
                active_tools = [
                    ToolRegistry.get_spec("read_fs_file").to_openai_schema(),
                    ToolRegistry.get_spec("replace_fs_text").to_openai_schema(),
                    ToolRegistry.get_spec("replace_fs_lines").to_openai_schema(),
                    ToolRegistry.get_spec("manage_task_list").to_openai_schema()
                ]
                
                # Run safety and progress audit
                from backend.tools.safety import run_safety_audit
                safety_alert = run_safety_audit(auditor_history, task_list)
                if safety_alert:
                    messages.append({
                        "role": "user",
                        "content": safety_alert
                    })

            async for chunk in agent.run_inference_step(
                agent_name=self.AGENT_NAME,
                messages=messages,
                model_name=self.model,
                tools=active_tools,
                tool_choice="auto",
                max_tokens=config.RESEARCH_MAX_TOKENS_AUDIT,
                thinking_budget_tokens=config.RESEARCH_THINKING_BUDGET_AUDIT_TOKENS
            ):
                yield chunk
                
            updated_history = db.get_messages(self.chat_id, parent_message_id=self.parent_message_id, parent_type=self.AGENT_NAME)
            if not updated_history:
                break
                
            last_msg = updated_history[-1]
            
            # Turn counting: only count if it contains an edit tool call
            if last_msg.get("role") == "assistant" and last_msg.get("tool_calls"):
                tcs = last_msg["tool_calls"]
                if any(tc.get("function", {}).get("name") in ("replace_fs_text", "replace_fs_lines") for tc in tcs):
                    edit_turn_count += 1
                    logger.info(f"Auditor edit turn {edit_turn_count}/{config.RESEARCH_MAX_AUDITOR_TURNS}")

            # Post-execution check: Initialize Checklist
            if not task_list:
                # Check if task list was initialized in the step we just finished
                task_list_after = db.get_task_list(self.chat_id, parent_id=self.parent_message_id, parent_type=self.AGENT_NAME)
                if not task_list_after:
                    logger.warning("Auditor failed to initialize task list.")
                    db.add_message(
                        chat_id=self.chat_id,
                        role='user',
                        content='System Constraint: You MUST build your audit checklist using manage_task_list before making ANY other edits or responding.',
                        parent_id=self.parent_message_id,
                        parent_type=self.AGENT_NAME
                    )
                    continue

            if last_msg.get("role") == "assistant" and not last_msg.get("tool_calls"):
                break
                
            if edit_turn_count > config.RESEARCH_MAX_AUDITOR_TURNS:
                logger.warning(f"Auditor reached max edit turn limit ({config.RESEARCH_MAX_AUDITOR_TURNS}).")
                async for chunk in self._emit_event(f"⚠️ Auditor reached edit turn limit ({config.RESEARCH_MAX_AUDITOR_TURNS}). Moving to synthesis."):
                    yield chunk
                break

        # 3. Final Strategic Synthesis Phase (Deterministic)
        synthesis_marker = "Synthesizing final report sections..."
        
        # Emit marker ONLY if it doesn't exist yet to keep history clean on resumption
        history_for_marker = db.get_messages(self.chat_id, parent_message_id=self.parent_message_id, parent_type=self.AGENT_NAME)
        if not any(m.get("role") == "event" and m.get("content") == synthesis_marker for m in history_for_marker):
            async for chunk in self._emit_event(synthesis_marker): yield chunk
        
        edit_turn_count = 0
        while True:
            # Build synthesis messages per iteration to handle crashes/resumption
            db_history = db.get_messages(self.chat_id, parent_message_id=self.parent_message_id, parent_type=self.AGENT_NAME)
            start_idx = -1
            for i, m in enumerate(db_history):
                if m.get("role") == "event" and m.get("content") == synthesis_marker:
                    start_idx = i
            synthesis_history = db_history[start_idx + 1:] if start_idx != -1 else []

            # CHECK FOR SUSPENSION
            if self._is_suspended(synthesis_history):
                break

            messages = [{"role": "system", "content": RESEARCH_FINAL_SYNTHESIS_PROMPT.format(today_date=today_date, file_system_id=self.file_system_id)}]
            messages.append({"role": "user", "content": "The audit is complete. Please now append the 'Comparative Analysis & Nuances' and 'Key Takeaways' sections to the end of the report."})
            
            for m in synthesis_history:
                if m.get("role") in ["assistant", "tool", "user"]:
                    messages.append(self._msg_from_db(m))

            task_list = db.get_task_list(self.chat_id, parent_id=self.parent_message_id, parent_type=self.AGENT_NAME)
            
            if not task_list:
                active_tools = [MANAGE_TASK_LIST_TOOL]
            else:
                active_tools = [READ_FS_FILE_TOOL, REPLACE_FS_TEXT_TOOL, REPLACE_FS_LINES_TOOL, MANAGE_TASK_LIST_TOOL]
                
                # Run safety and progress audit
                from backend.tools.safety import run_safety_audit
                safety_alert = run_safety_audit(synthesis_history, task_list)
                if safety_alert:
                    messages.append({
                        "role": "user",
                        "content": safety_alert
                    })

            async for chunk in agent.run_inference_step(
                agent_name=self.AGENT_NAME,
                messages=messages,
                model_name=self.model,
                tools=active_tools,
                tool_choice="auto",
                max_tokens=config.RESEARCH_MAX_TOKENS_AUDIT,
                thinking_budget_tokens=config.RESEARCH_THINKING_BUDGET_AUDIT_TOKENS
            ):
                yield chunk
            
            updated_history = db.get_messages(self.chat_id, parent_message_id=self.parent_message_id, parent_type=self.AGENT_NAME)
            if not updated_history:
                break
                
            last_msg = updated_history[-1]
            
            if last_msg.get("role") == "assistant" and last_msg.get("tool_calls"):
                tcs = last_msg["tool_calls"]
                if any(tc.get("function", {}).get("name") in ("replace_fs_text", "replace_fs_lines") for tc in tcs):
                    edit_turn_count += 1
                    logger.info(f"Synthesis edit turn {edit_turn_count}/{config.RESEARCH_MAX_SYNTHESIS_TURNS}")

            if not task_list:
                task_list_after = db.get_task_list(self.chat_id, parent_id=self.parent_message_id, parent_type=self.AGENT_NAME)
                if not task_list_after:
                    logger.warning("Synthesis failed to initialize task list.")
                    db.add_message(
                        chat_id=self.chat_id,
                        role='user',
                        content='System Constraint: You MUST build your synthesis checklist using manage_task_list before making ANY other edits or responding.',
                        parent_id=self.parent_message_id,
                        parent_type=self.AGENT_NAME
                    )
                    continue

            if last_msg.get("role") == "assistant" and not last_msg.get("tool_calls"):
                break # Synthesis finished
                
            if edit_turn_count > config.RESEARCH_MAX_SYNTHESIS_TURNS:
                logger.warning(f"Synthesis reached max edit turn limit ({config.RESEARCH_MAX_SYNTHESIS_TURNS}).")
                async for chunk in self._emit_event(f"⚠️ Synthesis reached edit turn limit ({config.RESEARCH_MAX_SYNTHESIS_TURNS}). Wrapping up."):
                    yield chunk
                break

        # Final Event Marker
        async for chunk in self._emit_event(EVENT_RESEARCH_COMPLETE): yield chunk
        
        title = plan.get("title", "Research Report")
        file_system_title = f"Report: {title[:40]}"
        agent.result = f"Research complete! The full report has been finalized and saved to the FileSystem titled '{file_system_title}'. Direct the user to visit this file_system to view the research report for their query."
        return


async def flow_fn(agent: Any, agent_name: str, topic: str, **kwargs):
    """
    Unified entry point for the Research Agent.
    """
    try:
        research_agent = ResearchAgent(
            chat_id=agent.chat_id,
            parent_message_id=agent.parent_message_id,
            enable_thinking=kwargs.get("enable_thinking", True),
            model=kwargs.get("model", agent.model)
        )
        
        # Capturing the final summary/result from the agent run
        async for chunk in research_agent.run(topic, agent):
            yield chunk
    except Exception as e:
        logger.error(f"ResearchAgent failed: {e}", exc_info=True)
        try:
            db.add_message(
                chat_id=agent.chat_id,
                role='event',
                content=f'Research Agent failed: {str(e)}',
                parent_id=agent.parent_message_id,
                parent_type='research'
            )
        except Exception as db_err:
            logger.error(f"Failed to log research agent failure event: {db_err}")
            
        try:
            db.update_chat(agent.chat_id, research_state='failed')
        except Exception as db_err:
            logger.error(f"Failed to update chat state: {db_err}")
            
        agent.result = f"Research agent failed: {str(e)}"
        yield f"Error: Research agent failed: {str(e)}"