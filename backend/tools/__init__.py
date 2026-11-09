import importlib
import logging
from typing import Dict, Any, Optional, Callable, List

from backend.tools.spec import ToolSpec, ToolType, ToolScope

logger = logging.getLogger(__name__)

class ToolRegistry:
    """
    Central registry for all tools and sub-agents.
    Aggregates specifications from backend.tools.catalog.
    """
    _specs_list: List[ToolSpec] = []
    _specs_dict: Dict[str, ToolSpec] = {}
    _registry: Dict[str, Any] = {}
    _loaded: bool = False

    @classmethod
    def _load(cls):
        if cls._loaded:
            return
        from backend.tools.catalog import ALL_TOOL_SPECS
        cls._specs_list = ALL_TOOL_SPECS
        cls._specs_dict = {}
        cls._registry = {}
        for spec in ALL_TOOL_SPECS:
            if spec.name not in cls._specs_dict:
                cls._specs_dict[spec.name] = spec
                cls._registry[spec.name] = spec.to_registry_entry()
        cls._loaded = True

    @classmethod
    def get_tool(cls, name: str) -> Optional[Dict[str, Any]]:
        """Backwards-compatible: returns registry-format dict."""
        cls._load()
        spec = cls._specs_dict.get(name)
        return spec.to_registry_entry() if spec else None

    @classmethod
    def get_spec(cls, name: str) -> Optional[ToolSpec]:
        cls._load()
        return cls._specs_dict.get(name)

    @classmethod
    def is_agent(cls, name: str) -> bool:
        cls._load()
        spec = cls.get_spec(name)
        return bool(spec and spec.tool_type == ToolType.AGENT)

    @classmethod
    def get_implementation(cls, name: str) -> Optional[str]:
        cls._load()
        spec = cls.get_spec(name)
        return spec.implementation if spec else None

    @classmethod
    def resolve_implementation(cls, name: str) -> Optional[Callable]:
        impl_path = cls.get_implementation(name)
        if not impl_path:
            return None
        try:
            module_path, attr_name = impl_path.rsplit('.', 1)
            module = importlib.import_module(module_path)
            return getattr(module, attr_name)
        except (ImportError, AttributeError) as e:
            logger.error(f"Failed to resolve implementation for {name}: {e}")
            return None

    @classmethod
    def get_tools_for_scope(cls, scope: ToolScope) -> List[Dict]:
        """Get OpenAI-schema tool dicts for a specific agent scope."""
        cls._load()
        return [s.to_openai_schema() for s in cls._specs_list if scope in s.scopes]

    @classmethod
    def get_directives_for_scope(cls, scope: ToolScope, active_modes: Optional[Dict[str, bool]] = None) -> str:
        """Compose all tool usage directives for a scope."""
        cls._load()
        directives_list = []
        for s in cls._specs_list:
            if scope not in s.scopes:
                continue
            if s.requires_mode and active_modes is not None:
                if not active_modes.get(s.requires_mode):
                    continue
            if s.admin_only and not (active_modes and active_modes.get("admin")):
                continue  # no active modes (agent scopes) means no admin
            directive = s.directives.strip()
            if directive:
                directives_list.append(directive)
        return "\n\n".join(directives_list)

    @classmethod
    def get_main_tools(cls, active_modes: Dict[str, bool]) -> List[Dict]:
        """
        Get the complete tool list for the main assistant.
        Handles mode-gated tools.
        """
        cls._load()
        tools = []
        for spec in cls._specs_list:
            if ToolScope.MAIN not in spec.scopes:
                continue
            if spec.requires_mode:
                if not active_modes.get(spec.requires_mode):
                    continue
            if spec.admin_only and not active_modes.get("admin"):
                continue
            tools.append(spec.to_openai_schema())
        return tools

PAGE_BASED_MIME_TYPES = frozenset([
    "application/pdf",
])

def get_document_agent_tools(mime_type: str) -> list:
    """Returns the correct tool set for the document agent based on the file's MIME type."""
    if mime_type.startswith('image/'):
        return []
    
    base_tools = ToolRegistry.get_tools_for_scope(ToolScope.DOCUMENT_BASE)
    if mime_type in PAGE_BASED_MIME_TYPES:
        page_tools = ToolRegistry.get_tools_for_scope(ToolScope.DOCUMENT_PAGE)
        return base_tools + page_tools
    else:
        line_tools = ToolRegistry.get_tools_for_scope(ToolScope.DOCUMENT_LINE)
        return base_tools + line_tools

__all__ = [
    "ToolRegistry",
    "ToolScope",
    "ToolType",
    "PAGE_BASED_MIME_TYPES",
    "get_document_agent_tools"
]
