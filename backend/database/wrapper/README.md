# backend/database/wrapper
**Role:** specialized mixins that extend the `DatabaseWrapper` with domain-specific database operations.

## 📂 Subdirectories
| Folder | Responsibility |
| :--- | :--- |
| `tests/` | Unit tests for all mixins. |

## 📄 Core Files
| File | Purpose | Key Symbols |
| :--- | :--- | :--- |
| `artifact_ops.py` | Operations for artifacts (canvas-like objects). | `ArtifactOpsMixin` |
| `base.py` | Base functionality, logging, and connection helpers. | `BaseMixin` |
| `callback_ops.py` | Persistence for pending clarification callbacks; `get_callback_chat_id` finds the chat a callback belongs to. | `CallbackOpsMixin` |
| `chat_ops.py` | CRUD for chats, workspaces, and chat metadata; FK-safe delete ordering. Owner-scoped: list, create, name-check and `delete_all_chats` take a `user_id` (empty raises `ValueError`); `ensure_chat_exists(chat_id, user_id)` returns the stored owner; `get_chat_owner`, `get_workspace_owner` read the DB directly; `get_all_chat_ids` is for system cleanup only. `get_listed_chats` returns the user's chats with content (message, file or chat artifact) for the sidebar. | `ChatOpsMixin` |
| `clipboard_ops.py` | Operations for chat clipboards. | `ClipboardOpsMixin` |
| `file_system_ops.py` | Operations for file system artifacts and versions. | `FileSystemOpsMixin` |
| `history_ops.py` | Logic for weaving message history and turn anchoring. | `HistoryOpsMixin` |
| `message_ops.py` | CRUD for messages and sub-agent messages. | `MessageOpsMixin` |
| `persona_ops.py` | CRUD operations for AI system Personas. Per user: every method takes a `user_id` (empty raises `ValueError`), a foreign id is "not found", and the default persona is per user. | `PersonaOperations` |
| `preference_ops.py` | Operations for user preferences and profile memories. Per user (`user_id` required; foreign ids are "not found"; `clear_preferences` clears only the caller's). | `PreferenceOpsMixin` |
| `settings_ops.py` | Dynamic system preferences and allowlist configurations. | `SettingsOpsMixin` |
| `skill_ops.py` | Retrieval and execution details for custom assistant skills. Per user: `add_skill` is an upsert that cannot take over another user's id (returns False), names are unique per user. | `SkillOpsMixin` |
| `task_ops.py` | Persistence related to background tasks. | `TaskOpsMixin` |
| `user_ops.py` | Users table: lookup by email or id, create, activate/deactivate, list. | `UserOpsMixin` |

## 🧩 Architectural Context
*   **Composition:** These files are not intended to be used in isolation. They are inherited by `DatabaseWrapper` in `backend/database/db_wrapper.py` to form a unified interface.
*   **Inheritance Hierarchy:** Most mixins inherit from `BaseMixin` to gain access to common utilities and logging.
*   **FK Delete Order:** `delete_chat` and `delete_all_chats` manually delete rows in child tables (deepest FK first: `file_system_versions` → `file_system_permissions` → `file_systems` → other chat-level children → `chats`) inside a single `BEGIN IMMEDIATE` transaction to avoid `sqlite3.IntegrityError: FOREIGN KEY constraint failed` when deleting chats with file attachments.

## 🛠️ Usage & Conventions
*   **Naming:** Methods follow a consistent naming convention (e.g., `get_chat`, `add_message`, `delete_workspace`).
*   **Encapsulation:** All SQL queries are encapsulated within these mixins to prevent leakages into the higher-level logic.
*   **Testing:**
    - **Local:** Unit tests in `tests/` verify SQL execution using an isolated temporary database.
    - **Run Command:** `EMBEDDING_URL="http://mock" AI_URL="http://mock" ./venv/bin/python3 -m pytest backend/database/wrapper/tests/`
    - `tests/conftest.py` documents the env var requirement; `tests/test_chat_ops.py` includes FK-safety regression tests for `delete_chat` and `delete_all_chats`, and tests for `get_listed_chats`.
