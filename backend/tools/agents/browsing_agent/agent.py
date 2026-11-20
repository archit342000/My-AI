# backend/tools/agents/browsing_agent/agent.py
import json
import logging
import uuid
from typing import AsyncGenerator, Dict, Any, List

from backend.database import db
from backend import config
from backend.mcp_client import playwright_client
from .prompts import BROWSING_AGENT_SYSTEM_PROMPT_TEXT, BROWSING_AGENT_SYSTEM_PROMPT_VISION
from backend.tools import ToolRegistry, ToolScope
from backend.tools.agents.base import BaseAgent, AgentConfig

logger = logging.getLogger(__name__)


class BrowsingAgent(BaseAgent):
    def __init__(self, agent_handler: Any, agent_config: AgentConfig):
        super().__init__(agent_handler, agent_config)
        
        # Determine if vision mode is enabled based on the model
        from backend.models import load_model_config
        model_config = load_model_config()
        vision_models = set()
        for category in model_config.values():
            if isinstance(category, dict):
                for key, val in category.items():
                    if key.startswith("vision"):
                        vision_models.add(val)
        
        self.is_vision = agent_handler.model in vision_models
        logger.info(f"BrowsingAgent vision mode: {self.is_vision} (model={agent_handler.model})")

    def get_system_prompt(self, **kwargs) -> str:
        system_prompt_template = BROWSING_AGENT_SYSTEM_PROMPT_VISION if self.is_vision else BROWSING_AGENT_SYSTEM_PROMPT_TEXT
        prompt = system_prompt_template.format()

        success_criteria = kwargs.get("success_criteria")
        if success_criteria:
            prompt += f"\n\n## SUCCESS CRITERIA\nYou must evaluate your progress against this goal: {success_criteria}\nDO NOT consider the task complete until these criteria are met."
        
        start_url = kwargs.get("start_url")
        if start_url:
            prompt += f"\n\n## STARTING URL\nYou must begin your task by navigating to: {start_url}"

        scope = kwargs.get("scope")
        if scope:
            scope_str = ", ".join(scope)
            scope_directive = (
                f"\n\n## SCOPE RESTRICTION\nYou are strictly restricted to using `browser_navigate` ONLY for the "
                f"following domains: **{scope_str}**. However, you are free to click links that take you to other "
                f"domains if it helps accomplish your task. If you cannot complete your task within this scope, "
                f"or if a mandatory navigation is blocked by this rule, you must fail the task and explain the scope limitation."
            )
            prompt += scope_directive
        return prompt

    def get_tools(self, iteration: int, task_list: Any, db_history: List[Dict]) -> List[Dict]:
        scope = ToolScope.BROWSING_VISION if self.is_vision else ToolScope.BROWSING_BASE
        return ToolRegistry.get_tools_for_scope(scope)

    def format_user_message(self, **kwargs) -> str:
        return f"Instruction: {kwargs['query']}"

    def count_tool_turns(self, db_history: List[Dict], tools: List[Dict]) -> int:
        return sum(
            1 for m in db_history
            if m.get("role") == "tool" and m.get("name", "").startswith("browser_")
        )

    def _browser_profile(self) -> dict:
        """
        The browser profile for this chat's owner, chosen here (never by the model).

        Returns `{"profile_id": <owner id>, "attach_portal": <owner is an admin>}`: each user has their own persistent
        profile, and only the admin's sessions may attach to the portal Chromium. Raises when the chat has no owner.
        """
        owner = db.get_chat_owner(self.chat_id)
        if not owner:
            raise RuntimeError(f"Chat {self.chat_id} has no owner; no browser session is started")
        user = db.get_user(owner)
        return {"profile_id": owner, "attach_portal": bool(user and user.get("role") == "admin")}

    @staticmethod
    def _raise_on_start_error(result) -> None:
        """`browser_start_session` reports failures (an invalid profile id, a launch error) as `{"error": ...}` in its
        result rather than raising; turn that into an exception so the run fails at start with a clear message."""
        if getattr(result, "isError", False) is True:
            text = getattr(getattr(result, "content", [None])[0], "text", "") if getattr(result, "content", None) else ""
            raise RuntimeError(f"Could not start the browser session: {text or 'tool error'}")
        try:
            data = json.loads(result.content[0].text)
        except (AttributeError, IndexError, TypeError, ValueError):
            return
        if isinstance(data, dict) and data.get("error"):
            raise RuntimeError(f"Could not start the browser session: {data['error']}")

    async def on_start(self, **kwargs) -> None:
        try:
            session_id = f"sess_{self.chat_id}_{uuid.uuid4().hex[:8]}"
            db.update_chat(self.chat_id, browsing_session_id=session_id)
            
            chat_meta = db.get_chat(self.chat_id)
            if chat_meta and chat_meta.get("browsing_session_id"):
                session_id = chat_meta["browsing_session_id"]
            
            await playwright_client.connect()
            self._raise_on_start_error(await playwright_client.execute_tool("browser_start_session", {
                "session_id": session_id,
                **self._browser_profile(),
                "stealth_level": config.BROWSER_STEALTH_LEVEL,
                "scope": kwargs.get("scope")
            }))
        except Exception as e:
            db.update_chat(self.chat_id, browsing_session_id=None)
            raise e

    async def on_resume(self, **kwargs) -> None:
        chat_meta = db.get_chat(self.chat_id)
        session_id = chat_meta.get("browsing_session_id") if chat_meta else None
        
        if not session_id:
            session_id = f"sess_{self.chat_id}_{uuid.uuid4().hex[:8]}"
            db.update_chat(self.chat_id, browsing_session_id=session_id)
            logger.info(f"Resuming but session_id was missing. Initialized new session: {session_id}")
            
        await playwright_client.connect()
        self._raise_on_start_error(await playwright_client.execute_tool("browser_start_session", {
            "session_id": session_id,
            **self._browser_profile(),
            "stealth_level": config.BROWSER_STEALTH_LEVEL,
            "scope": kwargs.get("scope")
        }))

    async def on_cleanup(self) -> None:
        chat_meta = db.get_chat(self.chat_id)
        session_id = chat_meta.get("browsing_session_id") if chat_meta else None
        if session_id:
            try:
                await playwright_client.connect()
                await playwright_client.execute_tool("browser_end_session", {"session_id": session_id})
                logger.info(f"BrowsingAgent cleaned up session {session_id}")
            except Exception as e:
                logger.error(f"BrowsingAgent error cleaning up session: {e}")
            db.update_chat(self.chat_id, browsing_session_id=None)

    async def on_error(self, error: Exception) -> str:
        if "Connection refused" in str(error):
            return "Could not reach the browser. Try again in a moment."
        return "Browsing agent failed during execution. Try again."

    def build_history(self, db_history: List[Dict], **kwargs) -> List[Dict]:
        screenshot_indices = []
        for i, m in enumerate(db_history):
            if m.get("role") == "tool" and m.get("name") == "browser_screenshot":
                screenshot_indices.append(i)
        
        prune_set = set(screenshot_indices[:-1]) if len(screenshot_indices) > 1 else set()

        messages = []
        for i, m in enumerate(db_history):
            if m.get("role") in ["assistant", "tool", "user"]:
                content = m["content"]
                
                if m.get("name") == "browser_screenshot":
                    if i in prune_set:
                        content = [{"type": "text", "text": "[Previous screenshot omitted to save context]"}]
                    elif not self.is_vision:
                        content = [{"type": "text", "text": "[Screenshot captured. Use browser_read_page and browser_get_interactive_elements to understand the page.]"}]
                        
                msg = {"role": m["role"], "content": content}
                for key in ("tool_calls", "tool_call_id", "name", "reasoning_content"):
                    if m.get(key):
                        msg[key] = m[key]
                messages.append(msg)
        return messages


async def flow_fn(agent: Any, agent_name: str, query: str, **kwargs) -> AsyncGenerator[str, None]:
    """
    Main orchestration logic for the Browsing Agent.
    Delegated by the ToolHandler/AgentHandler.
    """
    cfg = AgentConfig(
        name="browsing_agent",
        display_name="Browsing Agent",
        max_turns=config.BROWSING_AGENT_MAX_TURNS,
        failsafe_turns=config.BROWSING_AGENT_FAILSAFE_TURNS,
        max_tokens=config.BROWSING_AGENT_MAX_TOKENS,
        thinking_budget=config.BROWSING_AGENT_THINKING_BUDGET,
    )
    ba = BrowsingAgent(agent, cfg)
    async for chunk in ba.run(query=query, **kwargs):
        yield chunk
