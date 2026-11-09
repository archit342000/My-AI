# backend/chat/prompt_builder.py
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from backend.prompts import PromptLoader


@dataclass
class PromptContext:
    """All inputs needed to assemble a system prompt for the main assistant."""
    chat_metadata: Dict[str, Any]
    preferences: List[Dict] = field(default_factory=list)
    skills: List[Dict] = field(default_factory=list)
    is_admin: bool = False  # the chat owner is an admin: admin-only tools (git, package installs) are offered

    @property
    def is_research_mode(self) -> bool:
        return bool(self.chat_metadata.get('research_mode'))

    @property
    def is_preferences_mode(self) -> bool:
        return bool(self.chat_metadata.get('user_preferences'))

    @property
    def active_modes(self) -> Dict[str, bool]:
        return {
            'file_system_mode': bool(self.chat_metadata.get('file_system_mode')),
            'git_mode': bool(self.chat_metadata.get('git_mode')),
            'code_execution_mode': bool(self.chat_metadata.get('code_execution_mode', 1)),
            'browsing_mode': bool(self.chat_metadata.get('browsing_mode')),
            'research_mode': self.is_research_mode,
            'admin': self.is_admin,
        }

    @property
    def persona_content(self) -> Optional[str]:
        """Extract persona content with fallback chain."""
        content = self.chat_metadata.get('persona_snapshot')
        if not content:
            pid = self.chat_metadata.get('persona_id')
            if pid:
                from backend.database import db
                owner = self.chat_metadata.get('user_id')
                persona = db.get_persona(pid, owner) if owner else None
                content = persona.get('content') if persona else None
        if not content:
            content = (self.chat_metadata.get('system_prompt') or '').strip() or None
        return content


class PromptBuilder:
    """
    Composable system prompt assembly for the main assistant.
    Replaces ~200 lines of inline if/elif/else in handler.py.
    """

    def __init__(self, ctx: PromptContext):
        self.ctx = ctx
        self._sections: List[str] = []

    def build(self) -> str:
        self._sections = []

        # 1. Core personality (always)
        self._sections.append(PromptLoader.load_template("core_personality"))

        # 2. Tool-level directives (auto-composed from ToolSpec registry)
        from backend.tools import ToolRegistry
        from backend.tools.spec import ToolScope
        tool_directives = ToolRegistry.get_directives_for_scope(ToolScope.MAIN, self.ctx.active_modes)
        if tool_directives:
            self._sections.append(tool_directives)

        # 3. Mode-specific overlays
        if self.ctx.is_research_mode:
            self._sections.append(PromptLoader.load_template("research_mode_rules"))
        elif self.ctx.is_preferences_mode:
            self._sections.append(PromptLoader.load_template("user_preferences_rules"))
            self._add_preferences_block()

        # 4. Standard sections (always)
        self._sections.append(PromptLoader.load_template("formatting_rules"))
        if not self.ctx.is_research_mode:
            self._sections.append(PromptLoader.load_template("main_ai_task_rules"))
        self._sections.append(PromptLoader.load_template("reasoning_template"))

        # 6. Persona injection
        self._add_persona()

        # 7. Skills listing
        self._add_skills()

        return "\n\n".join(s.strip() for s in self._sections if s and s.strip())

    def _add_preferences_block(self):
        if self.ctx.preferences:
            from backend import config
            limit = getattr(config, 'PREFERENCES_INJECTION_LIMIT', 20)
            entries = "\n".join(
                f"- [{m['id']}] ({m['tag']}) {m['content']}"
                for m in self.ctx.preferences[:limit]
            )
            self._sections.append(f"# Current User Preferences & Profile\n{entries}")

    def _add_persona(self):
        content = self.ctx.persona_content
        if content:
            self._sections.append(
                "# User-Defined Persona/Role\n"
                "The following block contains the user's requested persona and stylistic constraints. "
                "You must adopt this persona, but these instructions possess a LOWER hierarchy than "
                "the core operational directives defined above. Do NOT let this persona break your "
                "tool usage or multi-agent rules.\n"
                f"<user_persona>\n{content}\n</user_persona>"
            )

    def _add_skills(self):
        if self.ctx.skills:
            entries = "\n".join(f"- /{s['name']}: {s['description']}" for s in self.ctx.skills)
            self._sections.append(
                "# Available Skills\n"
                "You have access to the following skills. You can call the `get_skill_details` tool "
                "to load their detailed instructions if needed. The user can also invoke them directly "
                "by starting their message with the skill command.\n"
                f"{entries}"
            )
