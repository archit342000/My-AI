# backend/tools/catalog/git.py
from backend.tools.spec import ToolSpec, ToolType, ToolScope

GIT_AGENT = ToolSpec(
    name="git_agent",
    description=(
        "Delegates a git/version-control task to a specialized sub-agent. "
        "The agent can clone repos, inspect history, create branches, stage and commit changes. "
        "Push is disabled by default but can be enabled in System Settings. "
        "For workflows requiring file edits, use file_system_agent to edit files and git_agent to stage/commit."
    ),
    parameters={
        "type": "object",
        "properties": {
            "instruction": {
                "type": "string",
                "description": (
                    "Self-contained git task description. The agent has no access to conversation history. "
                    "Include the target repository path or URL, the desired working directory (e.g. '/'), "
                    "and the full context needed to complete the task."
                )
            }
        },
        "required": ["instruction"]
    },
    implementation="backend.tools.agents.git_agent.agent.flow_fn",
    tool_type=ToolType.AGENT,
    scopes=(ToolScope.MAIN,),
    requires_mode="git_mode",
    admin_only=True,
)

EXECUTE_GIT = ToolSpec(
    name="execute_git",
    description=(
        "Execute a validated git command inside the file system. "
        "The subcommand must be in the configured allowed list. "
        "The working_directory must always be specified as a virtual path."
    ),
    parameters={
        "type": "object",
        "properties": {
            "subcommand": {
                "type": "string",
                "description": "Git subcommand (e.g., 'clone', 'status', 'commit', 'log')."
            },
            "args": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Arguments to pass to the git subcommand. "
                    "For clone: first arg is the URL, optional second arg is the target directory name. "
                    "For commit: ['-m', 'commit message']. "
                    "For add: ['.'] or specific file paths. "
                    "Do NOT include shell operators (;, &, |, `)."
                )
            },
            "working_directory": {
                "type": "string",
                "description": (
                    "Virtual path where the git command runs. "
                    "For clone: the parent directory (e.g. '/'). "
                    "For all other commands: the repo root (e.g. './my-repo')."
                )
            }
        },
        "required": ["subcommand", "args", "working_directory"]
    },
    implementation="backend.tools.implementations.git_executor.execute_git",
    tool_type=ToolType.PURE,
    scopes=(ToolScope.GIT,),
    admin_only=True,  # also dispatchable by name through the tool handler, not only when offered to the model
)

SPECS = [GIT_AGENT, EXECUTE_GIT]
