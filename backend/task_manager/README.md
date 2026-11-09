# backend/task_manager
**Role:** Coordinates the execution of long-running background tasks (e.g., chat turns, research loops) within isolated threads and asyncio loops, providing mechanisms for task interruption, recovery, and cache cleanup.

## 📂 Subdirectories
| Folder | Responsibility |
| :--- | :--- |

## 📄 Core Files
| File | Purpose | Key Symbols/Exports |
| :--- | :--- | :--- |
| `__init__.py` | Package entry point and singleton export aggregator. | `task_manager` |
| `executor.py` | Handles the generation loop and task state persistence. | `TaskExecutor` |
| `manager.py` | Central registry and lifecycle controller for background tasks. | `TaskManager` |
| `worker.py` | Thread-based worker that manages isolated asyncio event loops. | `TaskWorker` |

## 🧩 Architectural Context
*   **Dependencies:**
    - `backend.database`: Used for SSE chunk caching and turn finalization.
    - `backend.logging`: Records task lifecycle events and errors.
    - `backend.config`: Provides paths for task state files and cleanup intervals.
*   **Flow:**
    1. **Initiation:** Components (e.g., `ChatHandler`) submit a task via `start_task()`.
    2. **Isolation:** A `TaskWorker` thread is spawned, creating a dedicated `asyncio` loop for that specific chat ID. It runs inside `user_context` of the chat's owner, so `log_event` records `user_id`; `recover_tasks` now emits a `task_recovered` event for each flagged task, as the chat's owner (a failure there never removes the saved resume state).
    3. **Generation:** `TaskExecutor` iterates through the provided generator function, pushing chunks to the `response_cache`.
    4. **Interruption:** Users can signal a stop via `stop_task()`, which flags the task for cancellation and allows for clean rollback.
    5. **Cleanup:** A background thread periodically expires old cache entries and stale channels.

## 🛠️ Usage & Conventions
*   **Patterns:** 
    - **Worker-per-Chat:** Each chat session is isolated in its own thread to ensure high responsiveness and prevent global blocking.
    - **Crash Resilience:** The system maintains task state on disk (in `DATA_DIR/tasks`), enabling it to detect and flag interrupted tasks upon server restart for subsequent recovery.
*   **Turn claim:** `claim_turn(chat_id)` / `release_turn_claim(chat_id)` reserve a chat's single turn slot. `POST /v1/chat/completions` claims it before storing anything and releases it when the response closes or the request fails; a running task blocks new claims on its own (contract in `docs/standards/api.md`).
*   **Conventions:** The `task_manager` is a singleton; all background execution must be registered through it to ensure correct signal propagation and resource management.
*   **Testing:**
    - **Local:** Unit tests in `tests/` ensure strict compliance with the 1:1 exhaustive testing rule. Tests for `executor.py`, `manager.py`, and `worker.py` verify thread orchestration, asyncio event loops, and task state persistence.
    - **Run Command:** `EMBEDDING_URL="http://mock" AI_URL="http://mock" ./venv/bin/python3 -m pytest backend/task_manager/tests/`
