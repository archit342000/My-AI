# backend/database
**Role:** Provides a unified, modular persistence layer and a hybrid caching system for chat data, messages, workspaces, and application state.

## 📂 Subdirectories
| Folder | Responsibility |
| :--- | :--- |
| `wrapper/` | Domain-specific database operation mixins (chats, messages, artifacts, etc.). |

## 📄 Core Files
| File | Purpose | Key Symbols/Exports |
| :--- | :--- | :--- |
| `__init__.py` | Package entry point and singleton export aggregator. | `db`, `response_cache`, `init_db` |
| `cache_layer.py` | Hybrid row-level locking cache with Cache-Aside pattern. | `RowState`, `_log_cache_op` |
| `cache_system.py` | Response cache for active chat streaming with WAL support. | `ResponseCache`, `response_cache` |
| `db_layer.py` | Low-level SQLite connection management. | `make_connection`, `DB_PATH` |
| `db_wrapper.py` | Unified modular database wrapper using mixin composition. | `DatabaseWrapper` |
| `init_db.py` | Schema initialization, table creation, and data migrations. | `init_db`, `_assign_owners`, `_create_indexes` (the only place indexes are defined; re-run after table rebuilds) |

## 🧩 Architectural Context
*   **Dependencies:**
    - `sqlite3`: Underlying relational database engine.
    - `backend.config`: Configuration for database paths and cache TTLs.
    - `backend.logging`: Detailed auditing for database and cache operations.
*   **Flow:**
    1. **Initialization:** On application startup, `init_db()` ensures the SQLite schema is up-to-date and performs any required data migrations.
    2. **Database Access:** Components use the `db` singleton. Methods called on `db` are resolved via mixins in the `wrapper/` directory.
    3. **Streaming Cache:** During active LLM generation, `ChatHandler` appends chunks to `response_cache`. This system uses a Write-Ahead Log (WAL) to ensure durability and supports multiple subscribers for a single stream.
    4. **Persistence Cache:** `cache_layer.py` provides row-level caching for high-frequency DB reads, reducing SQLite overhead.

## 🛠️ Usage & Conventions
*   **Patterns:** 
    - **Mixin Composition:** `DatabaseWrapper` inherits from multiple specialized classes (e.g., `ChatOpsMixin`, `MessageOpsMixin`) to keep the codebase modular and manageable.
    - **Cache-Aside:** High-volume data is read from the cache first, falling back to the database on a miss.
    - **Thread Safety:** Uses a hierarchy of locks (Global -> Table -> Row) to ensure consistency in a multi-threaded environment.
*   **Conventions:** Never write raw SQL outside of this directory; always use the `db` wrapper to maintain schema abstraction. `messages.duration_ms` (tool call or turn time in milliseconds, nullable) is written by `add_message` / `add_tool_result` and `set_turn_duration`.
*   **Testing:**
    - **Local:** Unit tests in `tests/` verify caching logic, connection management, schema initialization, and the database wrapper.
    - **Run Command:** `EMBEDDING_URL="http://mock" AI_URL="http://mock" ./venv/bin/python3 -m pytest backend/database/tests/`
