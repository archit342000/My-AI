# backend/tools/catalog/code.py
from backend.tools.spec import ToolSpec, ToolType, ToolScope

RUN_CODE = ToolSpec(
    name="run_code",
    description="Execute code in a sandboxed environment. Use this for calculations, data processing, algorithm verification, generating charts, or any task that benefits from running actual code. Returns stdout, stderr, and exit code.",
    parameters={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "The complete source code to execute."
            },
            "language": {
                "type": "string",
                "enum": ["python", "c", "cpp", "java", "javascript", "typescript", "go", "rust", "bash", "php", "sql"],
                "description": "The programming language of the code."
            },
            "stdin": {
                "type": "string",
                "description": "Optional standard input to feed to the program."
            },
            "sql_target": {
                "type": "string",
                "enum": ["sqlite"],
                "description": "For SQL: the database engine. Only 'sqlite' is supported. Defaults to 'sqlite'."
            }
        },
        "required": ["code", "language"]
    },
    implementation="backend.tools.implementations.code_executor.run_code",
    tool_type=ToolType.PURE,
    scopes=(ToolScope.MAIN,),
    requires_mode="code_execution_mode",
)

RUN_FILE = ToolSpec(
    name="run_file",
    description="Execute a code file from the virtual file system. Automatically includes ALL files in the project directory tree (recursively) so that cross-file imports, includes, and package structures resolve correctly.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The virtual file system path to the main entry file to execute."
            },
            "stdin": {
                "type": "string",
                "description": "Optional standard input to feed to the program."
            },
            "args": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional command-line arguments."
            },
            "sql_target": {
                "type": "string",
                "enum": ["sqlite"],
                "description": "For SQL files: which database engine to use. Defaults to 'sqlite'."
            }
        },
        "required": ["path"]
    },
    implementation="backend.tools.implementations.code_executor.run_file",
    tool_type=ToolType.PURE,
    scopes=(ToolScope.MAIN,),
    requires_mode="code_execution_mode",
)

INSTALL_PACKAGES = ToolSpec(
    name="install_packages",
    description="Install packages in the code execution sandbox. Requires user approval before proceeding. Installed packages persist until the code runner container is restarted. Currently not available: the sandbox has no outbound network, so installs fail. Do not retry; tell the user.",
    parameters={
        "type": "object",
        "properties": {
            "packages": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of package names to install."
            },
            "package_manager": {
                "type": "string",
                "enum": ["pip", "npm"],
                "description": "Which package manager to use."
            }
        },
        "required": ["packages", "package_manager"]
    },
    implementation="backend.tools.implementations.code_executor.install_packages",
    tool_type=ToolType.PURE,
    scopes=(ToolScope.MAIN,),
    requires_mode="code_execution_mode",
)

LIST_PACKAGES = ToolSpec(
    name="list_packages",
    description="List packages currently installed in the code execution sandbox. Use this to check what's available before writing code that depends on third-party libraries, or before requesting a package installation.",
    parameters={
        "type": "object",
        "properties": {
            "package_manager": {
                "type": "string",
                "enum": ["pip", "npm"],
                "description": "Which package manager to query."
            }
        },
        "required": ["package_manager"]
    },
    implementation="backend.tools.implementations.code_executor.list_packages",
    tool_type=ToolType.PURE,
    scopes=(ToolScope.MAIN,),
    requires_mode="code_execution_mode",
)

SPECS = [RUN_CODE, RUN_FILE, INSTALL_PACKAGES, LIST_PACKAGES]
