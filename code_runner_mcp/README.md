# code_runner_mcp
**Role:** An isolated, sandboxed REST API server for compiling and executing multi-file scripts and managing packages.

## 📂 Subdirectories
| Folder | Responsibility |
| :--- | :--- |
| `tests/` | Unit tests for server, executor, safety logic and the relay. |

## 📄 Core Files
| File | Purpose | Key Symbols/Exports |
| :--- | :--- | :--- |
| `server.py` | FastAPI application defining the endpoints and authorization. | `app`, `verify_api_key` |
| `executor.py` | Language-specific execution engine implementing subprocess execution, directory recreation, class parsing, and SQLite setup. MySQL is rejected: the runner holds no database credentials. | `CodeExecutor`, `ExecutionResult` |
| `safety.py` | Heuristics-based static analysis classifier for detecting potentially dangerous execution patterns. | `classify_code` |
| `relay.py` | TCP relay run by the `code_runner_mcp` service. Forwards port 8100 to `RELAY_TARGET` (`code_runner_runtime:8100`) and nothing else. Used so the app reaches the runner without being on the sandbox network. Caps concurrent connections (64, extra clients are closed), aborts sessions idle for 600 s, and answers its own health check on loopback port 8101. Runs from its own slim image (`docker/Dockerfile.relay`), not the runner image. | `parse_target`, `make_handler`, `handle_health` |

## 🧩 Architectural Context
*   **Dependencies:**
    - `fastapi`, `uvicorn`: Web frameworks.
    - Various OS language runtimes (gcc, g++, default-jdk, nodejs, npm, tsx, golang, rustc, php-cli, sqlite3).
*   **Network:** the runtime service `code_runner_runtime` is on `runner-net`, which is internal-only. User code has no internet, `mysql_db` or app access. The app reaches the runtime through the relay service `code_runner_mcp` (`relay.py`), which forwards port 8100 only. Residual reach: the runtime's `CODE_RUNNER_API_KEY` is readable by user code, and user code can call the runner (and the relay) on port 8100, and can hold up to 64 relay sessions (the connection cap) for up to 600 s each without traffic, which blocks the app's route to the runner for that time. A silent run longer than the 600 s idle timeout is cut by the relay, so keep `code_runner_timeout` below it. `/install` (pip/npm) needs outbound access, so it fails in this setup.
*   **Flow:**
    1. The main app container makes an HTTP request to `/execute`, `/install`, or `/packages`.
    2. `server.py` verifies the `X-API-KEY` header.
    3. For `/execute`, `executor.py` writes the requested files into a temporary sandbox directory, sets the cwd to the parent of the entry file, executes the code via a subprocess as the non-privileged `runner` user, and cleans up the sandbox directory.

## 🛠️ Usage & Conventions
*   **Patterns:** Sandbox isolation by recreating the directory structure under `/tmp/sandbox/<uuid>/` for each run.
*   **Testing:**
    - Test files are in `code_runner_mcp/tests/`.
    - To run tests: `venv/bin/python -m pytest code_runner_mcp/tests/`
