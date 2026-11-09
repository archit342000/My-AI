# code_runner_mcp
**Role:** An isolated, sandboxed REST API server for compiling and executing multi-file scripts and managing packages.

## 📂 Subdirectories
| Folder | Responsibility |
| :--- | :--- |
| `tests/` | Unit tests for server, executor, safety logic and the relay. |

## 📄 Core Files
| File | Purpose | Key Symbols/Exports |
| :--- | :--- | :--- |
| `server.py` | FastAPI application defining the endpoints and authorization. It refuses to start without an API key (`API_KEY_FILE` or `CODE_RUNNER_API_KEY`). | `app`, `verify_api_key`, `load_api_key` |
| `package_names.py` | Allowlist validation of `/install` package specs: plain names with an optional version or extras only; no options, URLs or paths, one version specifier at most, at most 20 packages. | `validate_packages` |
| `executor.py` | Language-specific execution engine implementing subprocess execution, directory recreation, class parsing, and SQLite setup. MySQL is rejected: the runner holds no database credentials. | `CodeExecutor`, `ExecutionResult` |
| `safety.py` | Heuristics-based static analysis classifier for detecting potentially dangerous execution patterns. | `classify_code` |
| `relay.py` | TCP relay run by the `code_runner_mcp` service. Forwards port 8100 to `RELAY_TARGET` (`code_runner_runtime:8100`) and nothing else. Used so the app reaches the runner without being on the sandbox network. Caps concurrent connections (64, extra clients are closed), aborts sessions idle for 600 s, and answers its own health check on loopback port 8101. Runs from its own slim image (`docker/Dockerfile.relay`), not the runner image. | `parse_target`, `make_handler`, `handle_health` |

## 🧩 Architectural Context
*   **Dependencies:**
    - `fastapi`, `uvicorn`: Web frameworks.
    - Various OS language runtimes (gcc, g++, default-jdk, nodejs, npm, tsx, golang, rustc, php-cli, sqlite3).
*   **Network:** the runtime service `code_runner_runtime` is on `runner-net`, which is internal-only. User code has no internet, `mysql_db` or app access. The app reaches the runtime through the relay service `code_runner_mcp` (`relay.py`), which forwards port 8100 only. Residual reach: the runtime's `CODE_RUNNER_API_KEY` is readable by user code, and user code can call the runner (and the relay) on port 8100, and can hold up to 64 relay sessions (the connection cap) for up to 600 s each without traffic, which blocks the app's route to the runner for that time. A silent run longer than the 600 s idle timeout is cut by the relay, so keep `code_runner_timeout` below it. `/install` (pip/npm) goes through `pkg-proxy`, an allowlisted nginx proxy (PyPI and the npm registry only) that the runtime reaches via `PIP_INDEX_URL` / `npm_config_registry`; user code can reach it too and so can download from those registries. Common Python packages (`requirements-sandbox.txt`) are baked into the image.
*   **Flow:**
    1. The main app container makes an HTTP request to `/execute`, `/install`, or `/packages`.
    2. `server.py` verifies the `X-API-KEY` header (HTTP routes and `/ws/execute` alike; a `?api_key=` query parameter is not accepted); the service refuses to start without a configured key.
    3. Client timeouts are clamped to `1..MAX_TIMEOUT` (580 s, below the relay idle timeout planned for the relay hardening change; a missing timeout means 30 s). `/execute` answers 400 for a non-integer string and 422 for a bool or float; the live-run WebSocket sends an `Error: timeout must be an integer.` frame and exit code 1.
4. For `/execute`, `executor.py` writes the requested files into a temporary sandbox directory, sets the cwd to the parent of the entry file, executes the code via a subprocess as the non-privileged `runner` user, and cleans up. Each run gets its own `HOME` and `TMPDIR` (`<sandbox>/home`, `<sandbox>/tmp`), and every user-code subprocess starts in its own session so its whole process group is killed when the run ends, times out or (WebSocket) the client disconnects.
5. Between runs `executor.clear_scratch()` removes everything in `SCRATCH_ROOTS` (`/tmp`, `/var/tmp`, `/dev/shm`) and `SANDBOX_BASE`, before a run (a failure refuses the run with `Runner cleanup failed.`) and after it (a failure is reported on the result, or as a stderr frame on the WebSocket) and logs `runner_cleanup_error`. Runs are serialised twice: by the app (`backend/tools/implementations/run_slot.py`) and by the runner itself (`executor.RUN_LOCK`, held from the pre-run clear to the post-run clear by `/execute` and `/ws/execute`), because the app can give up on a call (cancel, client timeout) while the runner is still busy; this is what makes clearing the shared directories safe. A live run's compile step is bounded (`COMPILE_TIMEOUT`, 15 s); a run that cannot get the lock within `LOCK_WAIT` (600 s) answers busy, on both routes. The lock is released before the final frame is sent, and only the run that holds it clears the shared directories. After a kill the runner waits (bounded) for the group to disappear, and gives up on output pipes held by a process that escaped the group (a `setsid` child) instead of hanging with the lock held. `/install` does not take the lock (admin only). Residuals: other paths writable by `runner` are not cleared; a process that calls `setsid` (or double-forks) escapes the group kill and can outlive the lock; a live run whose client disconnects while it is still queued for the lock starts and is killed on the first receive; and a silent program is stopped by its timeout, not by a client that stays connected without reading.

## 🛠️ Usage & Conventions
*   **Patterns:** Sandbox isolation by recreating the directory structure under `/tmp/sandbox/<uuid>/` for each run (`SANDBOX_BASE`).
*   **Testing:**
    - Test files are in `code_runner_mcp/tests/`.
    - To run tests: `venv/bin/python -m pytest code_runner_mcp/tests/`
