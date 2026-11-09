# backend/tools/implementations
**Role:** Houses concrete execution logic and external process execution wrappers for registered system tools (e.g., Git Operations).

## 📂 Subdirectories
| Folder | Responsibility |
| :--- | :--- |
| `tests/` | Comprehensive unit and live subprocess integration tests for tool implementations. |

## 📄 Core Files
| File | Purpose | Key Symbols/Exports |
| :--- | :--- | :--- |
| `run_slot.py` | The process-wide code-run slot: runs of different users never overlap; per-user queue cap and bounded wait. | `run_slot`, `async_run_slot`, `RunQueueFull`, `RunQueueTimeout` |
| `git_executor.py` | Validates, sanitizes, and executes allowed Git commands in a VFS-safe subprocess wrapper. | `execute_git` |

## 🧩 Architectural Context
*   **Dependencies:**
    - `backend.config`: Default configuration limits, timeouts, and known commands list.
    - `backend.database`: Resolves dynamic Git allowlists and credentials (GitHub PATs).
    - `backend.file_system.utils`: Maps virtual pathing contexts to isolated system directories.
*   **Flow:**
    1. **Invocation**: The main dispatcher calls `execute_git` with a target subcommand, arguments, working directory, and contextual IDs.
    2. **Security Checks**: Ensures the subcommand is allowed, arguments are free of shell metacharacters, and path resolution resides inside the VFS boundaries.
    3. **Subprocess Execution**: The git binary is executed in a highly scrubbed, non-inherited environment with timeouts.
    4. **DB Cache Invalidation**: For tree-modifying commands (e.g., `checkout`, `switch`, `reset`), any associated cached virtual file records are purged.

## 🛠️ Usage & Conventions
*   **Command Allowlist**: By default, commands are constrained to safe subsets. Allowlists can be updated via dynamic settings in the database (`git_allowed_commands`).
*   **Environment Shielding**: Subprocess executions must never inherit the parent shell's raw environment to prevent leakage of credentials or parent repository metadata (e.g., `GIT_DIR`, `GIT_WORK_TREE`).
*   **Testing**:
    - Location: `backend/tools/implementations/tests/test_git_executor.py`
    - Run Command: `PYTHONPATH=. ./venv/bin/python -m pytest backend/tools/implementations/tests/ -v`
