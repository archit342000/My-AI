# backend/tools/catalog/filesystem.py
from backend.tools.spec import ToolSpec, ToolType, ToolScope

CREATE_FS_FILE = ToolSpec(
    name="create_fs_file",
    description="Creates a new persistent file_system at the specified path. Returns the status. Fails if a file already exists at that path.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The full relative path including directories and filename (e.g. 'src/utils/math.py')."
            },
            "content": {
                "type": "string",
                "description": "Initial content for the file_system. Optional if clipboard_key is provided."
            },
            "clipboard_key": {
                "type": "string",
                "description": "Optional. If provided, content is sourced from this clipboard key instead of the 'content' parameter."
            },
            "file_system_type": {
                "type": "string",
                "description": "Optional type/status update (e.g. 'research_plan_approved')."
            }
        },
        "required": ["path"]
    },
    implementation="backend.file_system.manager.create_fs_file",
    tool_type=ToolType.PURE,
    scopes=(ToolScope.FILE_SYSTEM,),
)

CREATE_DIRECTORY = ToolSpec(
    name="create_directory",
    description="Creates a new empty directory in the file_system system.",
    parameters={
        "type": "object",
        "properties": {
            "path": { "type": "string", "description": "The full relative path of the directory to create (e.g. 'src/utils')." }
        },
        "required": ["path"]
    },
    implementation="backend.file_system.manager.create_directory_tool",
    tool_type=ToolType.PURE,
    scopes=(ToolScope.FILE_SYSTEM,),
)

DELETE_DIRECTORY = ToolSpec(
    name="delete_directory",
    description="Deletes an empty directory in the file_system system. Fails if the directory contains tracked files.",
    parameters={
        "type": "object",
        "properties": {
            "path": { "type": "string", "description": "The full relative path of the directory to delete (e.g. 'src/utils')." }
        },
        "required": ["path"]
    },
    implementation="backend.file_system.manager.delete_directory_tool",
    tool_type=ToolType.PURE,
    scopes=(),
)

REPLACE_FS_TEXT = ToolSpec(
    name="replace_fs_text",
    description="Finds and replaces text in a file_system specified by path. Returns status and a unified diff.",
    parameters={
        "type": "object",
        "properties": {
            "path": { "type": "string", "description": "The full relative path of the file_system." },
            "expected_version": { "type": "integer", "description": "Must match current version." },
            "target_text": { "type": "string", "description": "Exact text to find." },
            "new_content": { "type": "string", "description": "Replacement text. Use empty string to delete. Optional if clipboard_key is provided." },
            "clipboard_key": { "type": "string", "description": "Optional. If provided, new_content is sourced from this clipboard key." },
            "start_line": { "type": "integer", "description": "Optional. Disambiguates duplicate matches." },
            "end_line": { "type": "integer", "description": "Optional. Disambiguates duplicate matches." },
            "allow_multiple": { "type": "boolean", "description": "Optional. If true, replaces all occurrences." }
        },
        "required": ["path", "expected_version", "target_text"]
    },
    implementation="backend.file_system.manager.replace_fs_text",
    tool_type=ToolType.PURE,
    scopes=(ToolScope.FILE_SYSTEM,),
)

REPLACE_FS_LINES = ToolSpec(
    name="replace_fs_lines",
    description="Overwrites a line range in a file_system specified by path. Fallback when text matching fails.",
    parameters={
        "type": "object",
        "properties": {
            "path": { "type": "string", "description": "The full relative path of the file_system." },
            "expected_version": { "type": "integer", "description": "Must match current version." },
            "start_line": { "type": "integer", "description": "1-indexed start line." },
            "end_line": { "type": "integer", "description": "1-indexed end line." },
            "new_content": { "type": "string", "description": "Content to replace the line range with. Optional if clipboard_key is provided." },
            "clipboard_key": { "type": "string", "description": "Optional. If provided, new_content is sourced from this clipboard key." }
        },
        "required": ["path", "expected_version", "start_line", "end_line"]
    },
    implementation="backend.file_system.manager.replace_fs_lines",
    tool_type=ToolType.PURE,
    scopes=(ToolScope.FILE_SYSTEM,),
)

GREP_FILES = ToolSpec(
    name="grep_files",
    description="Searches for a text pattern across file_systems in this chat session. Use this to find which file contains specific information.",
    parameters={
        "type": "object",
        "properties": {
            "pattern": { "type": "string" },
            "is_regex": { "type": "boolean" },
            "path": { "type": "string", "description": "Optional. The directory or file path to search within (e.g., 'src/'). If omitted, searches all files." },
            "context_chars": { "type": "integer", "description": "Number of characters to return before and after each match. Default is 300.", "default": 300 },
            "max_matches_per_file_system": { "type": "integer", "default": 5 },
            "names_only": { "type": "boolean", "description": "If true, only returns the paths that match, without the surrounding text." }
        },
        "required": ["pattern"]
    },
    implementation="backend.file_system.manager.grep_files",
    tool_type=ToolType.PURE,
    scopes=(ToolScope.FILE_SYSTEM,),
)

MOVE_FS_FILE = ToolSpec(
    name="move_fs_file",
    description="Moves or renames a file_system file to a new path.",
    parameters={
        "type": "object",
        "properties": {
            "source_path": { "type": "string", "description": "The current full relative path of the file_system." },
            "destination_path": { "type": "string", "description": "The new full relative path for the file_system." }
        },
        "required": ["source_path", "destination_path"]
    },
    implementation="backend.file_system.manager.move_fs_file_tool",
    tool_type=ToolType.PURE,
    scopes=(ToolScope.FILE_SYSTEM,),
)

DELETE_FS_FILE = ToolSpec(
    name="delete_fs_file",
    description="Permanently deletes a file_system file at the specified path.",
    parameters={
        "type": "object",
        "properties": {
            "path": { "type": "string", "description": "The full relative path of the file_system to delete." }
        },
        "required": ["path"]
    },
    implementation="backend.file_system.manager.delete_file_system_tool",
    tool_type=ToolType.PURE,
    scopes=(ToolScope.FILE_SYSTEM,),
)

READ_FS_FILE = ToolSpec(
    name="read_fs_file",
    description="Reads the content of a specific file_system by its path.",
    parameters={
        "type": "object",
        "properties": {
            "path": { "type": "string", "description": "The full relative path of the file_system." },
            "start_line": { "type": "integer", "description": "1-indexed start line." },
            "end_line": { "type": "integer", "description": "1-indexed end line." },
            "outline": { "type": "boolean", "description": "If true, returns a structural outline." }
        },
        "required": ["path"]
    },
    implementation="backend.file_system.manager.read_fs_file",
    tool_type=ToolType.PURE,
    scopes=(ToolScope.FILE_SYSTEM, ToolScope.GIT),
)

LS_FILES = ToolSpec(
    name="ls_files",
    description="Lists the files and directories in a specific path within the file_system system.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Optional. The directory path to list (e.g., 'src/components'). If omitted or '/', lists the root directory. Returns only immediate children, not the full recursive tree."
            }
        },
        "required": []
    },
    implementation="backend.file_system.manager.ls_files_for_tool",
    tool_type=ToolType.PURE,
    scopes=(ToolScope.FILE_SYSTEM, ToolScope.GIT),
)

PATCH_FILE_SYSTEM = ToolSpec(
    name="patch_file_system",
    description="Updates file metadata or content by ID.",
    parameters={
        "type": "object",
        "properties": {},
        "required": []
    },
    implementation="backend.file_system.manager.patch_file_system",
    tool_type=ToolType.PURE,
    scopes=(),
)

FILE_SYSTEM_AGENT = ToolSpec(
    name="file_system_agent",
    description="Delegates a file_system task to a specialized sub-agent capable of multi-step read/write operations across one or more file_systems.",
    parameters={
        "type": "object",
        "properties": {
            "instruction": {
                "type": "string",
                "description": (
                    "Self-contained task description. The agent has no access to conversation history. "
                    "For large files or code block creation/modification, first write the contents using clipboard_write "
                    "and reference the cb-... key here, specifying the key in clipboard_keys."
                )
            },
            "clipboard_keys": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of clipboard keys (e.g., ['cb-xxx']) holding content needed for this operation."
            }
        },
        "required": ["instruction"]
    },
    implementation="backend.tools.agents.file_system_agent.agent.flow_fn",
    tool_type=ToolType.AGENT,
    scopes=(ToolScope.MAIN,),
    requires_mode="file_system_mode",
)

PREVIEW_FILE_SYSTEMS = ToolSpec(
    name="preview_file_systems",
    description="SYSTEM-ONLY TOOL — this tool is automatically invoked by the system and you are FORBIDDEN from calling it. The system will provide file_system inventory as a tool response before your turn. Use the information from the tool response, do not attempt to call this tool.",
    parameters={
        "type": "object",
        "properties": {},
        "required": []
    },
    implementation="backend.tools.catalog.filesystem.preview_file_systems_noop",
    tool_type=ToolType.PURE,
    scopes=()
)

def preview_file_systems_noop(**kwargs):
    return {"success": True}

SPECS = [
    CREATE_FS_FILE,
    CREATE_DIRECTORY,
    DELETE_DIRECTORY,
    REPLACE_FS_TEXT,
    REPLACE_FS_LINES,
    GREP_FILES,
    MOVE_FS_FILE,
    DELETE_FS_FILE,
    READ_FS_FILE,
    LS_FILES,
    PATCH_FILE_SYSTEM,
    FILE_SYSTEM_AGENT,
    PREVIEW_FILE_SYSTEMS
]

