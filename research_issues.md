# Code Issues in the Research Engine (`backend/agents/research.py` and dependencies)

During a thorough scan of the codebase, several issues were found and resolved.

## 1. UnboundLocalError for `follow_up_content`

**File:** `backend/agents/research.py`

**Issue:**
Inside the `_execute_section_reflection_and_write` generator, there is a path where `follow_up_content` was referenced before assignment. Specifically, in the line `yield {"type": "result", "data": (section_text, summary_points, plan_mod, follow_up_content, next_source_id)}`, the `follow_up_content` variable was only assigned under certain conditions. If the "Gap-Filling" conditional didn't set `follow_up_content` or wasn't triggered, the variable would remain undefined, causing a crash when execution reached the final `yield`.

**Resolution:**
Defined `follow_up_content = None` (or `""`) near the start of the function block (specifically right next to `follow_up_buffer = []`) so that it is always in scope when execution reaches the `yield` statement.

## 2. Undefined Variable `log_event` in Utilities

**File:** `backend/utils.py`

**Issue:**
In the `check_url_safety` function, if an exception occurred during the request to the `urlhaus` API, the exception block attempted to call `log_event`. However, `log_event` was not imported from `backend.logger` at the top of the file, leading to an `UnboundLocalError: local variable 'log_event' referenced before assignment` (or `NameError: name 'log_event' is not defined` depending on the Python version).

**Resolution:**
Added `log_event` to the existing import statement: `from backend.logger import log_tool_call, log_llm_call, log_event`.

## 3. Raising NoneType Exception in Thread Runner

**File:** `backend/utils.py`

**Issue:**
In the `run_coro` function block inside `visit_page`, an exception wrapper used a list `ex = [None]` to catch exceptions from a threaded run. The exception raising condition `if ex[0]: raise ex[0]` triggers a pylint `raising-bad-type` warning (E0702) because `NoneType` could theoretically be raised if not handled carefully, though in context it works if `ex[0]` captures a valid Exception.

**Resolution:**
The current code works practically since `ex[0]` will be an `Exception` object when it evaluates to truthy, but pylint highlighted it as a risk.


## 4. Minor Linting and Code Quality Issues

**File:** `backend/agents/research.py`

**Issue:**
A follow-up comprehensive `pylint` scan revealed a few code quality issues:
- Unused variables: `all_section_texts` and `follow_up_content` were assigned but never explicitly used after the assignment in certain blocks.
- Unused imports: Unused utility functions (`GET_TIME_TOOL`, `visit_page`, `estimate_tokens`, etc.) were imported but never used.
- Bad Indentation: An assignment had 17 spaces instead of 16.
- Encoding warnings: `open()` was used without explicitly specifying an encoding.

**Resolution:**
- Removed unused imports and variables.
- Fixed indentation on the affected line.
- Explicitly added `encoding="utf-8"` to all `open()` calls.
- Replaced the unused unpacked `follow_up_content` variable with `_` in unpacking assignments.


## 5. FileNotFoundError During Section Execution (`state.json`)

**File:** `backend/agents/research.py`

**Issue:**
The research agent attempts to write checkpointing data after each completed section. It was trying to write to `./backend/tasks/{chat_id}_state.json`. When the application was containerized, this hardcoded static directory may not exist or the `appuser` may not have permission, resulting in a `[Errno 2] No such file or directory` crash.

**Resolution:**
Replaced the hardcoded path with a dynamic path utilizing the persistent volume configuration: `os.path.join(config.DATA_DIR, "tasks", f"{chat_id}_state.json")`. Additionally, added an `os.makedirs(os.path.dirname(state_path), exist_ok=True)` call right after the initialization to guarantee that the `tasks` directory is dynamically created inside the `DATA_DIR` before attempting to dump the JSON file.


## 6. Hardcoded Legacy Directories in Backend Services

**File(s):** `backend/cache_system.py`, `backend/rag.py`

**Issue:**
After the migration to a containerized Docker environment with a dedicated volume mount mapped via `DATA_DIR` (as specified in `backend/config.py`), some critical persistence locations still had hardcoded legacy paths relative to the development environment (`./backend/cache` and `./backend/chroma_db`).
If a Docker container mounts a volume to `/app/backend/data`, but the cache engine uses `./backend/cache`, the data is written directly to the container layer, leading to total data loss across restarts or container rebuilds.

**Resolution:**
- In `backend/cache_system.py`, replaced `CACHE_DIR = "./backend/cache"` with `CACHE_DIR = os.path.join(config.DATA_DIR, "cache")`.
- In `backend/rag.py`, replaced the default kwarg `persist_path="./backend/chroma_db"` with `persist_path=config.CHROMA_PATH` (which is correctly derived from `DATA_DIR` in the configuration).


## 7. NameError due to missing config import

**File(s):** `backend/cache_system.py`

**Issue:**
After updating `backend/cache_system.py` to use `config.DATA_DIR` instead of a hardcoded path, the application failed to start inside the container because `config` was not imported into the file. This resulted in a `NameError: name 'config' is not defined` crash at startup.

**Resolution:**
Added `from backend import config` to the imports in `backend/cache_system.py`. Validated the script via python execution to ensure the application starts without immediately crashing.
