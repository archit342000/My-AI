# backend/tools/agents/base.py
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, AsyncGenerator
from abc import ABC, abstractmethod
import logging

from backend.database import db
from backend.logging import log_event, error_detail
from backend import config

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Declarative configuration for a looping sub-agent."""
    name: str                  # DB parent_type (e.g. "file_system_agent")
    display_name: str          # Human-readable (e.g. "FileSystem Agent")
    max_turns: int             # From config (e.g. config.FILE_SYSTEM_AGENT_MAX_TURNS)
    failsafe_turns: int        # From config (e.g. config.FILE_SYSTEM_AGENT_FAILSAFE_TURNS)
    max_tokens: int            # From config
    thinking_budget: int       # From config
    require_task_list: bool = True
    enable_safety_audit: bool = True


class BaseAgent(ABC):
    """
    Standardized lifecycle for looping sub-agents.

    Subclasses implement:
    - get_system_prompt(**kwargs) -> str
    - get_tools(iteration, task_list, db_history) -> List[Dict]
    - format_user_message(**kwargs) -> str

    Optional hooks:
    - on_start(**kwargs) -> None
    - on_complete(last_message) -> str
    - on_error(error) -> str
    - build_history(db_history, **kwargs) -> List[Dict]  (for custom history like screenshot pruning)
    - count_tool_turns(db_history, tools) -> int  (for custom turn counting)
    """

    def __init__(self, agent_handler: Any, agent_config: AgentConfig):
        self.agent = agent_handler
        self.config = agent_config
        self.chat_id = agent_handler.chat_id
        self.parent_message_id = agent_handler.parent_message_id

    @abstractmethod
    def get_system_prompt(self, **kwargs) -> str:
        pass

    @abstractmethod
    def get_tools(self, iteration: int, task_list: Any, db_history: List[Dict]) -> List[Dict]:
        pass

    @abstractmethod
    def format_user_message(self, **kwargs) -> str:
        pass

    # ── Optional hooks ──

    async def on_start(self, **kwargs) -> None:
        """Called once on first run (not on resume). Override for setup (e.g. Playwright session)."""
        pass

    async def on_resume(self, **kwargs) -> None:
        """Called once when resuming an existing run. Override for setup (e.g. Playwright session reconnection)."""
        pass

    async def on_complete(self, last_message: Dict) -> str:
        """Called when agent finishes. Returns the result summary."""
        return last_message.get("content", f"{self.config.display_name} completed.")

    async def on_error(self, error: Exception) -> str:
        """Called on unrecoverable error."""
        return f"{self.config.display_name} failed. Try again."

    async def on_cleanup(self) -> None:
        """Called in finally block. Override for cleanup (e.g. Playwright session teardown)."""
        pass

    def build_history(self, db_history: List[Dict], **kwargs) -> List[Dict]:
        """
        Convert DB history rows to message dicts.
        Override for custom behavior (e.g. browsing agent's screenshot pruning).
        """
        messages = []
        for m in db_history:
            if m.get("role") in ("assistant", "tool"):
                msg = {"role": m["role"], "content": m.get("content")}
                for key in ("tool_calls", "tool_call_id", "name", "reasoning_content"):
                    if m.get(key):
                        msg[key] = m[key]
                messages.append(msg)
        return messages

    def count_tool_turns(self, db_history: List[Dict], tools: List[Dict]) -> int:
        """Count how many tool result messages exist. Override for custom counting."""
        tool_names = {t["function"]["name"] for t in tools}
        return sum(
            1 for m in db_history
            if m.get("role") == "tool" and m.get("name") in tool_names
        )

    # ── Core lifecycle (NOT overridden) ──

    async def run(self, **kwargs) -> AsyncGenerator[str, None]:
        name = self.config.name
        try:
            existing_history = db.get_messages(
                self.chat_id, parent_message_id=self.parent_message_id, parent_type=name
            )
            is_resume = len(existing_history) > 0

            if not is_resume:
                await self.on_start(**kwargs)
                db.add_message(
                    chat_id=self.chat_id, role='event',
                    content=f'{self.config.display_name} Started.',
                    parent_id=self.parent_message_id, parent_type=name
                )
            else:
                logger.info(f"{self.config.display_name} resuming: chat_id={self.chat_id} existing_msgs={len(existing_history)}")
                await self.on_resume(**kwargs)

            iteration = 0
            while True:
                iteration += 1

                # Absolute failsafe
                if iteration > self.config.max_turns + self.config.failsafe_turns:
                    logger.warning(f"{self.config.display_name} reached absolute iteration limit ({iteration}). Force ending.")
                    db.add_message(
                        chat_id=self.chat_id, role='event',
                        content=f'{self.config.display_name} Force Terminated. (infinite loop prevention)',
                        parent_id=self.parent_message_id, parent_type=name
                    )
                    self.agent.result = "Operation forcibly terminated due to infinite loop."
                    return

                # Rebuild history
                db_history = db.get_messages(
                    self.chat_id, parent_message_id=self.parent_message_id, parent_type=name
                )
                history_msgs = self.build_history(db_history, **kwargs)
                messages = [
                    {"role": "system", "content": self.get_system_prompt(**kwargs)},
                    {"role": "user", "content": self.format_user_message(**kwargs)},
                ] + history_msgs

                # Task list gating
                task_list = db.get_task_list(
                    self.chat_id, parent_id=self.parent_message_id, parent_type=name
                )
                active_tools = self.get_tools(iteration, task_list, db_history)

                if self.config.require_task_list and not task_list:
                    from backend.tools import ToolRegistry
                    active_tools = [ToolRegistry.get_spec("manage_task_list").to_openai_schema()]

                # Turn limit enforcement
                tool_turns = self.count_tool_turns(db_history, self.get_tools(iteration, task_list, db_history))
                limit_hit = tool_turns >= self.config.max_turns

                if limit_hit:
                    already_warned = any(
                        m.get("role") == "user" and "TURN LIMIT REACHED" in m.get("content", "")
                        for m in db_history
                    )
                    if not already_warned:
                        logger.warning(f"{self.config.display_name} reached turn limit ({tool_turns}). Injecting wrap-up.")
                        db.add_message(
                            chat_id=self.chat_id, role='user',
                            content=f'[SYSTEM: TURN LIMIT REACHED] You have exhausted your allowed operations. Summarize your findings immediately. Do not attempt any further actions.',
                            parent_id=self.parent_message_id, parent_type=name
                        )
                        continue
                    active_tools = []  # Force text response

                # Safety audit
                if self.config.enable_safety_audit and task_list and not limit_hit:
                    from backend.tools.safety import run_safety_audit
                    alert = run_safety_audit(db_history, task_list)
                    if alert:
                        messages.append({"role": "user", "content": alert})

                # Inference step
                async for chunk in self.agent.run_inference_step(
                    agent_name=name,
                    messages=messages,
                    model_name=self.agent.model,
                    tools=active_tools if active_tools else None,
                    tool_choice="auto" if active_tools else None,
                    max_tokens=self.config.max_tokens,
                    thinking_budget_tokens=self.config.thinking_budget,
                ):
                    yield chunk

                # Completion check
                updated = db.get_messages(
                    self.chat_id, parent_message_id=self.parent_message_id, parent_type=name
                )
                if not updated:
                    break

                last_msg = updated[-1]

                # Task list init enforcement
                if self.config.require_task_list and not task_list:
                    task_list_after = db.get_task_list(
                        self.chat_id, parent_id=self.parent_message_id, parent_type=name
                    )
                    if not task_list_after:
                        logger.warning(f"{self.config.display_name} failed to initialize task list.")
                        db.add_message(
                            chat_id=self.chat_id, role='user',
                            content='System Constraint: You MUST initialize your task list using manage_task_list before taking ANY other actions or responding.',
                            parent_id=self.parent_message_id, parent_type=name
                        )
                        continue

                if last_msg.get("role") == "assistant" and not last_msg.get("tool_calls"):
                    result = await self.on_complete(last_msg)
                    db.add_message(
                        chat_id=self.chat_id, role='event',
                        content=f'{self.config.display_name} Completed.',
                        parent_id=self.parent_message_id, parent_type=name
                    )
                    self.agent.result = result
                    return

        except Exception as e:
            logger.error(f"{self.config.display_name} failed: {e}", exc_info=True)
            log_event("agent_failed_error", {"agent": self.config.display_name, "chat_id": self.chat_id, "error": error_detail(e)})
            error_msg = await self.on_error(e)
            try:
                db.add_message(
                    chat_id=self.chat_id, role='event',
                    content=f'{self.config.display_name} failed. Try again.',
                    parent_id=self.parent_message_id, parent_type=name
                )
            except Exception as db_err:
                logger.error(f"Failed to log {self.config.display_name} failure: {db_err}")
            self.agent.result = error_msg
            yield f"Error: {error_msg}"
        finally:
            await self.on_cleanup()
