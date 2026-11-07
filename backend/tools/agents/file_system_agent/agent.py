# backend/tools/agents/file_system_agent/agent.py
from backend.tools.agents.base import BaseAgent, AgentConfig
from backend.tools.time_utils import get_current_time
from backend import config
from .prompts import FILE_SYSTEM_AGENT_SYSTEM_PROMPT
from backend.tools import ToolRegistry, ToolScope

class FileSystemAgent(BaseAgent):
    def get_system_prompt(self, **kwargs):
        return FILE_SYSTEM_AGENT_SYSTEM_PROMPT.format(
            current_time=get_current_time(), chat_id=self.chat_id
        )

    def get_tools(self, iteration, task_list, db_history):
        return ToolRegistry.get_tools_for_scope(ToolScope.FILE_SYSTEM)

    def format_user_message(self, **kwargs):
        instruction = kwargs['instruction']
        clipboard_keys = kwargs.get('clipboard_keys') or []
        parts = [f"Instruction: {instruction}"]
        if clipboard_keys:
            keys_str = ", ".join(clipboard_keys)
            parts.append(
                f"\nClipboard Keys Available: [{keys_str}]\n"
                f"Use these keys with the clipboard_key parameter in "
                f"create_fs_file, replace_fs_text, or replace_fs_lines."
            )
        return "\n".join(parts)

async def flow_fn(agent, instruction, clipboard_keys=None, **kwargs):
    cfg = AgentConfig(
        name="file_system_agent", display_name="FileSystem Agent",
        max_turns=config.FILE_SYSTEM_AGENT_MAX_TURNS,
        failsafe_turns=config.FILE_SYSTEM_AGENT_FAILSAFE_TURNS,
        max_tokens=config.FILE_SYSTEM_AGENT_MAX_TOKENS,
        thinking_budget=config.FILE_SYSTEM_AGENT_THINKING_BUDGET,
    )
    fs = FileSystemAgent(agent, cfg)
    async for chunk in fs.run(instruction=instruction, clipboard_keys=clipboard_keys, **kwargs):
        yield chunk