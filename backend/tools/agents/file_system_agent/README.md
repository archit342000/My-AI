# file_system_agent
**Role:** A specialized, autonomous sub-agent responsible for file system lifecycle management, including creating, reading, editing, and reorganizing persistent documents.

## 📂 Subdirectories
| Folder | Responsibility |
| :--- | :--- |
| `tests/` | Unit tests for the file system agent flow, turn limits, and planning logic. |

## 📄 Core Files
| File | Purpose | Key Symbols/Exports |
| :--- | :--- | :--- |
| `agent.py` | Main orchestration logic for file system operations and tool-calling loops. | `flow_fn` |
| `prompts.py` | System prompt assembly for file system management instructions. | `FILE_SYSTEM_AGENT_SYSTEM_PROMPT` |

## 🧩 Architectural Context
*   **Dependencies:** `backend.database`, `backend.tools.time_utils`, `backend.tools.definitions`.
*   **Flow:** The agent starts or resumes a task, enforces a planning phase (task list), and executes file system operations (ls, grep, read, create, replace, etc.) in an autonomous loop until completion or turn limit.

## 🛠️ Usage & Conventions
*   **Patterns:** Strictly enforces a "Plan-then-Act" workflow using `manage_task_list`.
*   **Clipboard-First Flow:** Receives clipboard identifiers via `clipboard_keys` parameter to perform out-of-band file transfers rather than inlining large bodies of code.
*   **Testing:** Local tests in `tests/`. Run with `pytest backend/tools/agents/file_system_agent/tests/`.
