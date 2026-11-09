# backend/tools/spec.py
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum


class ToolType(Enum):
    PURE = "pure"
    AGENT = "agent"


class ToolScope(Enum):
    """Which agent contexts can use this tool."""
    MAIN = "main"                   # Main assistant
    FILE_SYSTEM = "file_system"     # File system agent internal tools
    BROWSING_BASE = "browsing_base" # Browsing agent (text mode)
    BROWSING_VISION = "browsing_vision"  # Browsing agent (vision extras)
    DOCUMENT_BASE = "document_base" # Document agent base tools
    DOCUMENT_PAGE = "document_page" # Document agent page-based reading
    DOCUMENT_LINE = "document_line" # Document agent line-based reading
    GIT = "git"                     # Git agent internal tools


@dataclass(frozen=True)
class ToolSpec:
    """
    Single source of truth for a tool definition.
    Replaces: definitions.py dict + registry.json entry + prompts.py directive.
    """
    name: str
    description: str
    parameters: Dict[str, Any]           # JSON Schema object
    implementation: str                   # Dotted import path (e.g. "backend.tools.time_utils.get_current_time")
    tool_type: ToolType = ToolType.PURE
    scopes: tuple = ()                   # Tuple of ToolScope values (frozen dataclass needs hashable)
    requires_mode: Optional[str] = None  # Mode flag name (e.g. "research_mode") — tool only appears when this mode is active
    admin_only: bool = False             # Reaches host-wide state (git, package installs): offered to and runnable by admin-owned chats only

    @property
    def directives(self) -> str:
        """Usage instructions loaded dynamically from prompt templates."""
        from backend.prompts.loader import PromptLoader
        try:
            return PromptLoader.load_template(f"directives/{self.name}")
        except FileNotFoundError:
            return ""

    def to_openai_schema(self) -> Dict[str, Any]:
        """Convert to OpenAI-compatible function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }

    def to_registry_entry(self) -> Dict[str, Any]:
        """Backwards-compatible registry.json format."""
        return {
            "type": self.tool_type.value,
            "implementation": self.implementation,
            "description": self.description,
        }
