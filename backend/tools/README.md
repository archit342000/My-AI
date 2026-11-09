# backend/tools
**Role:** Manages the definition, registration, and dispatch of all system capabilities, including "pure" functional tools and complex autonomous sub-agents.


## 📂 Subdirectories
| Folder | Responsibility |
| :--- | :--- |
| `agents/` | Implementation logic for autonomous sub-agents (research, browsing, etc.). |
| `catalog/` | Unified ToolSpec definition files organized by domain. |
| Scratch area | Temporary workspace for transient tool-related data (created at runtime). |

## 📄 Core Files
| File | Purpose | Key Symbols/Exports |
| :--- | :--- | :--- |
| `__init__.py` | Central tool registry and implementation resolver. | `ToolRegistry` |
| `browser.py` | Implementation of browser-based interaction tools. | `browser_navigate`, `browser_screenshot` |
| `callbacks.py` | Persistence and management of pending tool clarifications. | `callback_registry` |
| `clarify.py` | Implementation for user clarification requests. | `request_clarification` |
| `clipboard.py` | Out-of-band text sharing clipboard tool implementations. | `clipboard_write`, `clipboard_read`, `clipboard_copy_file` |
| `preferences.py` | Management of long-term user profile facts. Tools receive `user_id` from the server (the chat owner, via `ToolHandler`), never from model arguments. | `add_user_preference`, `edit_user_preference`, `delete_user_preference` |
| `spec.py` | ToolSpec dataclass and scope/type enumerations. | `ToolSpec`, `ToolScope`, `ToolType` |
| `router.py` | API endpoints for interacting with tools and config. Callback routes (`/active/<chat_id>`, `/clarification/response`) check the chat owner; an unknown or foreign callback id is the same 404. | `tools_bp` |
| `tasks.py` | Implementation of persistent task/checklist management. | `manage_task_list` |
| `time_utils.py` | Local date and time utilities. | `get_current_time` |

## 🧪 Testing
| Test File | Scope |
| :--- | :--- |
| `tests/test_init.py` | Registry loading and implementation resolution logic. |
| `tests/test_spec.py` | ToolSpec serialization and compatibility tests. |
| `tests/test_clipboard.py` | Clipboard tools unit tests. |
| `catalog/tests/test_catalog.py` | Aggregated ToolSpec completeness and validation tests. |
| `tests/test_router.py` | Flask API endpoints, preference CRUD, and config updates. |
| `tests/test_callbacks.py` | In-memory and DB-persisted callback lifecycle. |
| `tests/test_browser.py` | MCP-based browser tool execution and screenshot handling. |
| `tests/test_tasks.py` | Agile task list state machine and persistence. |

*   **Run Tests:** `EMBEDDING_URL="http://mock" AI_URL="http://mock" AI_API_KEY="dummy" PYTHONPATH=. ./venv/bin/python -m pytest backend/tools/tests/`

## 🧩 Architectural Context
*   **Dependencies:**
    - `backend.database`: For persisting tool results, task lists, and memories.
    - `backend.logging`: Detailed auditing for all tool dispatches and results.
    - `backend.chat`: The primary consumer of tool definitions and implementations.
*   **Flow:**
    1. **Discovery:** The LLM is informed of tools defined in the tool catalog under `catalog/` via `ToolRegistry.get_main_tools()`.
    2. **Invocation:** Upon a tool call, `ToolHandler` queries `ToolRegistry` to find the implementation.
    3. **Execution:** Pure tools are executed directly; agents are initialized via `AgentHandler` for an autonomous multi-step turn.
    4. **Persistence:** Results are stored in the database, anchored to the specific tool call ID.

## 🛠️ Usage & Conventions
*   **Patterns:** 
    - **Registry Dispatch:** Decouples tool definition from implementation, allowing for dynamic loading and easy extension.
    - **Schema-Driven:** All tools use standard JSON-schema definitions to ensure reliable inference across different LLM providers.
    - **MCQ Clarifications:** Supports structured user feedback through multiple-choice options in the `request_clarification` tool.
*   **Adding Tools:**
    1. Create a `ToolSpec` in the appropriate module under `catalog/`.
    2. Import the spec and add it to `ALL_TOOL_SPECS` in `catalog/__init__.py`.
    3. Implement the function in the relevant module (or a new one).

