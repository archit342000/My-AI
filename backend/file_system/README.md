# backend/file_system
**Role:** Manages virtualized "file system" artifacts that are persistent across chat turns, supporting multi-user workspaces, versioning, and complex file operations.

## 📂 Subdirectories
| Folder | Responsibility |
| :--- | :--- |

## 📄 Core Files
| File | Purpose | Key Symbols/Exports |
| :--- | :--- | :--- |
| `__init__.py` | Package entry point and high-level API aggregator. | `create_fs_file`, `get_fs_file_content` |
| `channel.py` | Per-chat locking system to prevent concurrent write race conditions. | `FileSystemChannelManager` |
| `fuzzy_matcher.py` | Utilities for exact and fuzzy text matching during file edits. | `_find_exact_match` |
| `manager.py` | Core logic for path resolution, CRUD, versioning, and tool implementations. `create_fs_file` returns an error for a missing chat instead of creating one. | `ls_files_for_tool`, `replace_fs_text` |
| `models.py` | Enum definitions for channel state. | `ChannelState` |
| `router.py` | Flask API endpoints for frontend artifact interaction. A blueprint hook (`require_fs_owner`) checks every `chat_id` and `workspace_id` in the query, body and URL against the current user (foreign or unknown is 404, non-string is 400; a not-yet-existing chat passes only on the two create routes, which claim it). Listing without a chat or workspace is a 400. | `file_system_bp` |
| `utils.py` | Path sanitization, ID generation, and ownership resolution helpers. | `resolve_owner_and_physical_path` |

## 🧩 Architectural Context
*   **Dependencies:**
    - `backend.database`: Persistence for metadata, version history, and permissions.
    - `backend.config`: Root directories for file and workspace storage.
    - `aiofiles`: Asynchronous file system I/O.
*   **Flow:**
    1. **Mounting:** Virtual paths starting with `workspace/` are routed to shared workspace directories; all others are local to the chat.
    2. **Locking:** Every operation must acquire a `FileSystemPersistenceChannel` for the specific chat to ensure serial execution across AI and user agents.
    3. **Persistence:** Files are mirrored on disk (current version) and tracked in SQLite (all versions).
    4. **Versioning:** Edits create new versions with parent pointers, allowing for non-linear history navigation (undo/redo).

*   **Patterns:** 
    - **Virtualized Hierarchy:** Agents interact with a clean, relative path structure that maps to secure, isolated physical locations.
    - **Channel Serialization:** Prevents the "lost update" problem in a multi-agent or collaborative environment.
    - **Search-Enabled:** Uses FTS5 (via DB sync) to allow fast searching across all artifacts in a session.
    - **Out-of-band Content Resolution:** File writing and editing tools (`create_fs_file`, `replace_fs_text`, `replace_fs_lines`) support an optional `clipboard_key` parameter to retrieve content directly from the database clipboard, preventing context bloat.
*   **Conventions:** Never manipulate files in `DATA_DIR/file_systems` directly; always use the `manager` API to keep metadata and versioning in sync.
*   **Testing:**
    - **Local:** Unit tests in `tests/` ensure strict compliance with the exhaustive 1:1 testing rule, verifying path resolution, FTS5 sync, locking channels, and artifact CRUD operations.
    - **Run Command:** `EMBEDDING_URL="http://mock" AI_URL="http://mock" ./venv/bin/python3 -m pytest backend/file_system/tests/`
