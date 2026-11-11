import logging
import json
import asyncio
import contextvars
import re
import sqlite3
import time
from time import time as _epoch_seconds
from typing import List, Dict, Any, Optional, AsyncGenerator

from backend.database import db
from backend.tools import ToolRegistry
from backend.logging import log_event
from backend.chat.models import ParsedToolCall

logger = logging.getLogger(__name__)

_UNSET = object()

ACTIVITY_MAX_CHARS = 120
_FAILED_RESULT_RE = re.compile(r"^(error:|[a-z][\w ]{0,40} failed(\.|:|\s+(during execution|to return a response|after \d+ attempts)))", re.IGNORECASE)


def _activity_from_chunk(line: str, agent_name: str) -> Optional[str]:
    """Activity of a helper from one of its stream lines (never raises: it only observes)."""
    try:
        return _read_activity(line, agent_name)
    except (AttributeError, TypeError, IndexError, KeyError):
        return None


def _read_activity(line: str, agent_name: str) -> Optional[str]:
    """
    What a helper is doing now, read from one stream line the helper produced: its latest event text, or the tool it just
    called (`Using <tool>`). Lines of other agents (a nested helper has its own `parent_type`), main-turn lines, results
    and `agent_run` lines give None. Cut to `ACTIVITY_MAX_CHARS`.
    """
    if not isinstance(line, str) or not line.startswith("data: "):
        return None
    try:
        data = json.loads(line[6:])
    except ValueError:
        return None
    if not isinstance(data, dict) or "agent_run" in data or data.get("parent_type") != agent_name:
        return None
    choices = data.get("choices")
    delta = choices[0].get("delta") if isinstance(choices, list) and choices and isinstance(choices[0], dict) else None
    if not isinstance(delta, dict) or "tool_result" in delta:
        return None
    text = None
    if delta.get("role") == "event" and isinstance(delta.get("content"), str):
        text = delta["content"]
    elif isinstance(delta.get("tool_calls"), list) and delta["tool_calls"]:
        function = (delta["tool_calls"][0] or {}).get("function") or {}
        if isinstance(function.get("name"), str) and function["name"]:
            text = f"Using {function['name']}"
    text = (text or "").strip()
    return text[:ACTIVITY_MAX_CHARS] if text else None


def _run_failed(result: Any) -> bool:
    """True when a helper's result reads as a failure: its first line starts with `Error:` or is an agent's own failure text (`<name> failed.`, `<name> failed:`, `... failed during execution`, `... failed after N attempts`). A normal first line that merely contains "failed" does not count."""
    first_line = str(result or "").strip().split("\n", 1)[0]
    return bool(_FAILED_RESULT_RE.match(first_line))


def _agent_run_chunk(parent_type: str, run: Dict[str, Any]) -> str:
    """The `agent_run` stream line for a helper run (state running, done or failed)."""
    return "data: " + json.dumps({"parent_type": parent_type, "agent_run": run}) + "\n\n"


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

    @property
    def owner_is_admin(self) -> bool:
        """True when the chat owner is an admin. A missing owner or an unknown user is not (fail closed)."""
        if not self.user_id:
            return False
        owner = db.get_user(self.user_id)
        return bool(owner and owner.get('role') == 'admin')

    def _record_agent_run(self, run: Dict[str, Any]) -> None:
        """
        Keep a finished helper run in the `agent_runs` collection of this handler's anchor (merged by run id, so a resumed
        turn adds to the stored list), so a reload shows the same runs. A storage failure is logged, never raised.
        """
        from backend.database import db as _db
        try:
            colls = _db.get_collections(self.chat_id, parent_message_id=self.parent_message_id, parent_type=self.parent_type)
            coll = next((c for c in colls if c.get("collection_type") == "agent_runs"), None)
            runs = coll.get("items") if coll else []
            if isinstance(runs, str):
                runs = json.loads(runs)
            runs = [r for r in runs if isinstance(r, dict) and r.get("id") != run["id"]] if isinstance(runs, list) else []
            runs.append(run)
            _db.add_collection(chat_id=self.chat_id, parent_message_id=self.parent_message_id, parent_type=self.parent_type,
                               collection_type="agent_runs", items=runs, overwrite=True)
        except Exception as e:  # run records are display data: a storage failure is logged and must never abort the turn
            log_event("agent_run_store_error", {"chat_id": self.chat_id, "run": str(run.get("id"))[:100], "error": f"{type(e).__name__}: {e}"[:300]})

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
            started = time.monotonic()  # a call's duration_ms runs from here to its stored result

            # Check Registry for Type
            tool_meta = ToolRegistry.get_tool(name)
            if not tool_meta:
                error_msg = f"Error: Tool '{name}' not found in registry. Available: {list(ToolRegistry._registry.keys())}"
                logger.warning(f"[TOOL] {error_msg}")

                from backend.database import db
                duration_ms = int((time.monotonic() - started) * 1000)
                db.add_tool_result(
                    chat_id=self.chat_id,
                    tool_call_id=tc_id,
                    name=name,
                    content=error_msg,
                    parent_id=self.parent_message_id,
                    parent_type=self.parent_type,
                    duration_ms=duration_ms
                )
                yield "data: " + json.dumps({
                    "parent_type": self.parent_type,
                    "choices": [{
                        "delta": {
                            "tool_result": {
                                "name": name,
                                "content": error_msg,
                                "tool_call_id": tc_id,
                                "duration_ms": duration_ms
                            }
                        }
                    }]
                }) + "\n\n"
                continue

            # Admin-only tools (git, package installs) are refused for any other owner, even when the model names
            # one that was never offered to it.
            spec = ToolRegistry.get_spec(name)
            if spec is not None and spec.admin_only and not self.owner_is_admin:
                log_event("tool_admin_only_denied", {"chat_id": self.chat_id, "name": name, "id": tc_id})
                denied_msg = "Error: This tool is not available."
                from backend.database import db
                duration_ms = int((time.monotonic() - started) * 1000)
                db.add_tool_result(
                    chat_id=self.chat_id,
                    tool_call_id=tc_id,
                    name=name,
                    content=denied_msg,
                    parent_id=self.parent_message_id,
                    parent_type=self.parent_type,
                    duration_ms=duration_ms
                )
                yield "data: " + json.dumps({
                    "parent_type": self.parent_type,
                    "choices": [{"delta": {"tool_result": {"name": name, "content": denied_msg, "tool_call_id": tc_id, "duration_ms": duration_ms}}}]
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
                            duration_ms = int((time.monotonic() - started) * 1000)
                            _vdb.add_tool_result(
                                chat_id=self.chat_id,
                                tool_call_id=tc_id,
                                name=name,
                                content=validation.message,
                                parent_id=self.parent_message_id,
                                parent_type=self.parent_type,
                                duration_ms=duration_ms
                            )
                            yield "data: " + json.dumps({
                                "parent_type": self.parent_type,
                                "choices": [{"delta": {"tool_result": {
                                    "name": name,
                                    "content": validation.message,
                                    "tool_call_id": tc_id,
                                    "duration_ms": duration_ms,
                                }}}]
                            }) + "\n\n"
                            continue
                # ── END CLIPBOARD ENFORCEMENT ────────────────────────────

                # The helper run starts here (even if its implementation turns out not to be resolvable): a start chunk, an update
                # whenever its activity changes, an end chunk (done or failed).
                run = {
                    "id": tc_id, "name": name,
                    "parent_id": self.parent_message_id if self.parent_type != "main" else None,
                    "state": "running", "activity": None, "started_at": _epoch_seconds(), "duration_ms": None,
                }
                yield _agent_run_chunk(self.parent_type, run)

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
                            if isinstance(chunk, str) and not chunk.endswith("\n"):
                                yield "\n\n"  # an agent's plain-text chunk has no terminator: end its line so the next `data:` line stays whole
                            activity = _activity_from_chunk(chunk, name)
                            if activity and activity != run["activity"]:
                                run["activity"] = activity
                                yield _agent_run_chunk(self.parent_type, run)
                    except StopAsyncIteration:
                        agent_result = self.agent_handler.result
                    except Exception:
                        run.update(state="failed", duration_ms=int((time.monotonic() - started) * 1000))
                        self._record_agent_run(run)
                        yield _agent_run_chunk(self.parent_type, run)
                        raise
                    
                    if agent_result is None:
                        agent_result = f"Agent '{name}' completed execution successfully."
                    duration_ms = int((time.monotonic() - started) * 1000)
                    run.update(state="failed" if _run_failed(agent_result) else "done", duration_ms=duration_ms)
                    self._record_agent_run(run)
                    yield _agent_run_chunk(self.parent_type, run)
                    
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
                        parent_type=self.parent_type,
                        duration_ms=duration_ms
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
                                    "tool_call_id": tc_id,
                                    "duration_ms": duration_ms
                                }
                            }
                        }]
                    }) + "\n\n"
                else:
                    error_msg = f"Error: Agent implementation for '{name}' could not be resolved."
                    logger.error(f"[TOOL] {error_msg}")
                    from backend.database import db
                    duration_ms = int((time.monotonic() - started) * 1000)
                    run.update(state="failed", duration_ms=duration_ms)
                    self._record_agent_run(run)
                    yield _agent_run_chunk(self.parent_type, run)
                    db.add_tool_result(
                        chat_id=self.chat_id,
                        tool_call_id=tc_id,
                        name=name,
                        content=error_msg,
                        parent_id=self.parent_message_id,
                        parent_type=self.parent_type,
                        duration_ms=duration_ms
                    )
                    yield "data: " + json.dumps({
                        "parent_type": self.parent_type,
                        "choices": [{
                            "delta": {
                                "tool_result": {
                                    "name": name,
                                    "content": error_msg,
                                    "tool_call_id": tc_id,
                                    "duration_ms": duration_ms
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
                duration_ms = int((time.monotonic() - started) * 1000)
                db.add_tool_result(
                    chat_id=self.chat_id,
                    tool_call_id=tc_id,
                    name=name,
                    content=content_str,
                    parent_id=self.parent_message_id,
                    parent_type=self.parent_type,
                    duration_ms=duration_ms
                )

                # Yield synthetic result chunk for frontend rendering and phase boundary
                yield "data: " + json.dumps({
                    "parent_type": self.parent_type,
                    "choices": [{
                        "delta": {
                            "tool_result": {
                                "name": name,
                                "content": content_str,
                                "tool_call_id": tc_id,
                                "duration_ms": duration_ms
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
