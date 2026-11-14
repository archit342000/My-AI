---
id: MYAI-23
title: "Live-run WebSocket and run_code return exception text"
status: done
created: 2026-11-09
updated: 2026-11-09
links:
  conflicts_with: [MYAI-27, MYAI-28]
  relates_to: [MYAI-5, MYAI-12, MYAI-26]
---

## Description
Found while planning MYAI-5. `app.py`'s live-run WebSocket sends `f"Error: {e}"` from `collect_project_files` to the client, and `run_code` in `backend/tools/implementations/code_executor.py` puts `{e}` in its runner-unavailable message. `docs/standards/security.md` and `api.md` say not to return `str(e)` of internal exceptions.

## Acceptance criteria
- [x] The live-run WebSocket sends short fixed error messages; details go to log_event
- [x] run_code's runner-unavailable message has no exception text; details are logged
- [x] Known user-facing messages (file does not exist, not supported) are unchanged

## Plan

**Date:** 2026-11-09  **Status:** Validated  **Base:** origin/develop 6a13e04

### Objective
Stop the live-run WebSocket (`/api/tools/code-execution/ws` in `app.py`) and `run_code` from sending raw exception text to the client or the model. Send short fixed messages instead, log the details, and leave the known user-facing messages ("does not exist", "not supported") exactly as they are.

### Context
- Requirement: Description and Acceptance criteria above. Scope is exactly these two places (see Risks for the same pattern elsewhere).
- `code_execution_ws_proxy` (`app.py:117` onwards) has two exception paths:
  - Around `collect_project_files(chat_id, file_path)`: `except Exception as e` sends `{"type": "stderr", "data": f"Error: {e}\n"}` and then `exit 1`.
  - The outer `except Exception as e`: `logger.error(...)`, then it sends `f"Proxy error: {e}\n"`. This covers `ws_client.create_connection` failures. The upstream URL carries `?api_key=...`, so exception text that echoes the URL could leak the key to the browser.
  - `log_event` is imported at `app.py:3`.
- `collect_project_files` (`backend/tools/implementations/code_executor.py`) raises:
  - `FileNotFoundError(f"File '{path}' does not exist.")` (line 141);
  - `ValueError(f"File extension '{ext}' is not supported for execution.")` (line 146);
  - the resolver's `ValueError`s from `resolve_owner_and_physical_path` (`backend/file_system/utils.py`) for invalid paths, whose messages are written by our code.
- `run_code` (`code_executor.py:92-98`): `except Exception as e` logs and returns `f"Error: Failed to execute code. Code runner service is unavailable: {e}"` to the model.
- Tests: `tests/test_app.py::test_code_execution_ws_proxy` (line 174) and `test_code_execution_ws_proxy_defaults_sql_target_to_sqlite`; `backend/tools/tests/test_code_executor.py::test_run_code_*`.
- Rules:
  - `docs/standards/security.md` and `api.md`: no `str(e)` of internal exceptions to clients.
  - `docs/standards/errors-and-logging.md`: details via `log_event` with `<component>_<event>` names; tool results start with `Error` so the agent can recover.
  - `docs/standards/testing.md`.
- Overlap:
  - MYAI-5 adds `resolve_run_target` and changes `run_file` (same module, different functions).
  - MYAI-12 changes generic tool exception handling in `tool_handler.py` (a different layer).

### Approach
- **WS prepare errors.** Catch `(FileNotFoundError, ValueError)` separately and send `f"Error: {e}\n"` as today. These messages are ours and user-facing: missing file, unsupported extension, invalid path. Every other `Exception` sends a fixed `"Error: Could not prepare the file for execution.\n"`, then `log_event("code_execution_ws_prepare_error", {"chat_id": ..., "file_path": ..., "error": type(e).__name__})`. Log the type name, as on the other paths, because the message may hold internal paths. In every prepare error, the `{"type": "exit", "code": 1}` frame still follows the stderr frame, as today.
- **WS proxy errors.** The outer handler sends a fixed `"Error: Code runner is unavailable.\n"`.
  - Change the existing `logger.error(f"Code execution WS proxy error: {e}", exc_info=True)` to log the type name only, with no `exc_info`. The message and traceback can contain the upstream URL with `?api_key=`, and `security.md` says never to log API keys. This is in scope: it's the same handler.
  - Add `log_event("code_execution_ws_proxy_error", {"chat_id": ..., "error": type(e).__name__})`. Use the type name, not the message, because the message can include the upstream URL with `api_key`.
  - `chat_id` may be unset if the error happens before init. Default it to None.
- **`run_code`.** Return `"Error: Failed to execute code. Code runner service is unavailable."` (no `{e}`) and add `log_event("code_executor_run_code_error", {"chat_id": chat_id, "error": type(e).__name__})` beside the existing `logger.error`.
  - The existing `logger.error` interpolates `{e}`. Leave it: it goes to the server log, not the client.
- Rejected alternative: map every exception type to a friendly message. Too broad; the two known types cover the user-facing cases.

### Steps
#### Step 1: Live-run WebSocket messages
- **Files:** `app.py` (modify): `code_execution_ws_proxy`, the prepare `try/except` and the outer `except`.
- **Change:** as in Approach. Initialise `chat_id = None` before the init message is parsed if it isn't already, so the outer handler can log it.
- **Verification:** Step 3 tests.

#### Step 2: `run_code` message
- **Files:** `backend/tools/implementations/code_executor.py` (modify): add `from backend.logging import log_event` to the imports (lines 1-12 don't have it); `run_code`, the `except` at lines 96-98.
- **Change:** as in Approach.
- **Verification:** Step 3 tests.

#### Step 3: Tests
- **Files:** `tests/test_app.py` (modify); `backend/tools/tests/test_code_executor.py` (modify). Patch `app.log_event` and `backend.tools.implementations.code_executor.log_event` (`log_event` writes files under `GENERAL_LOG_DIR`), plus `app.logger`, so the tests stay isolated. For the `create_connection` case, also patch `backend.tools.implementations.code_executor.collect_project_files` to succeed, as the existing tests at `tests/test_app.py:170-226` do. Precondition: a `venv` with `requirements.txt` and `requirements-dev.txt`.
- **Change:**
  - WS cases:
    - `collect_project_files` raising `FileNotFoundError("File 'x.py' does not exist.")` sends that exact text, prefixed `Error: `, then exit 1.
    - Raising `ValueError("File extension '.xyz' is not supported for execution.")` sends that exact text.
    - Raising `RuntimeError("db path /secret/x locked")` sends only `Error: Could not prepare the file for execution.` (the message isn't in any frame), and `app.log_event` is called with `code_execution_ws_prepare_error`.
    - `create_connection` raising `ConnectionRefusedError("ws://code_runner_mcp:8100/ws/execute?api_key=k")` sends `Error: Code runner is unavailable.`, never the key or the URL. It logs `code_execution_ws_proxy_error` with `ConnectionRefusedError`, and `app.logger.error` is called without the key in its arguments.
    - Each prepare error, known or not, is followed by an exit frame with code 1.
  - `run_code`: with `requests.post` raising `ConnectionError("boom http://x")`, the result is exactly the fixed message, `"boom"` is absent, and `log_event` is called.
  - Existing tests still pass.
- **Verification:**
  - `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q tests/test_app.py`
  - `... -m pytest -q backend/tools/tests/test_code_executor.py`
  - (separate processes: the `tests` and `backend` suites)

#### Step 4: Full gate
- **Change:** run `venv/bin/ruff check .`, then the `backend` and `tests` suites in their own processes, then `scripts/check.sh`. No docs change: `errors-and-logging.md` already states the rule, and no README describes these messages.
- **Verification:** all pass.

### Tests
- Preconditions: a `venv` with `requirements.txt` and `requirements-dev.txt`.
- `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q backend`, then the same with `tests`.
- `venv/bin/ruff check .`, then `scripts/check.sh`.

### Risks and open questions
- **The same `{e}` pattern exists elsewhere in `code_executor.py`, outside this ticket:**
  - `run_file`: line 199 (path resolve; MYAI-5 touches this function) and line 299 (runner unavailable);
  - `install_packages`: line 386 (MYAI-4 Step 4 touches this function);
  - the packages list: line 417.
  These are left alone to stay in scope. Possible follow-up ticket: "code_executor tool results include exception text".
- **The API key stays in the WS URL query string** (`app.py`, `?api_key=`). This change keeps it out of the client and out of this handler's log line. Moving the key to a header is a separate change (it needs the runner's `execute_ws` to accept a header). Possible follow-up.
- **Merge overlap** with MYAI-4 and MYAI-5 in `code_executor.py` (different functions).
- No blocking open questions.

### Success criteria
- [ ] The live-run WebSocket sends fixed messages for unexpected errors; details go to `log_event` (Steps 1 and 3)
- [ ] `run_code`'s runner-unavailable message has no exception text; details are logged (Steps 2-3)
- [ ] The "does not exist" and "not supported" messages are unchanged (Step 3)
- [ ] All checks pass

### Validation log
- Round 1 (2026-11-09, Haiku): FAIL, 1 BLOCKING and 6 MINOR. My judgement: PASS after fixes.
  - B1: `log_event` isn't imported in `code_executor.py` (lines 1-12). Valid. Import added in Step 2.
  - M2: patch targets for `log_event`. Valid. Specified.
  - M3: keep the exit frame. Valid. Stated and tested.
  - M4: the logger line writes the `api_key` URL. Valid (`security.md`). Now logs the type name only, in the same handler.
  - M5: inconsistent `str(e)`. Valid. Type name everywhere.
  - M6: the resolver raises only `ValueError`. Confirmation, no change.
  - M7: venv precondition in Step 3. Valid. Added.
  The B1 fix is a one-line import that I checked against the file, so I'm marking this Validated without another round.

## Implementation notes

### Autopilot run (2026-11-09)
Batch 7 item. Branch bugfix/live-run-error-text from origin/develop 2e81c08, PR base develop. Dirty files before start: none. Same function as MYAI-27 (PR #79), MYAI-28 (PR #78) and neighbouring code of MYAI-26: expect small conflicts in app.py and the tests.

### Baseline (2026-11-09)
At develop 2e81c08: `pytest backend tests` only the 10 async-plugin failures.

### Implementation progress
- [x] Step 1: `code_execution_ws_proxy`: `FileNotFoundError`/`ValueError` from `collect_project_files` keep their own messages; any other prepare error sends `Error: Could not prepare the file for execution.` (then exit 1) and logs `code_execution_ws_prepare_error` with the type name; the outer handler sends `Error: Code runner is unavailable.`, logs only the exception type (app log and `code_execution_ws_proxy_error` event), `chat_id` initialised before init
- [x] Step 2: `run_code`'s runner-unavailable result has no exception text; `code_executor_run_code_error` event
- [x] Step 3: tests (own messages unchanged, unexpected prepare error hidden and logged, connection error hidden and the key never logged, `run_code`)
- [x] Step 4: ruff clean; no docs change; scripts/check.sh not run as a whole (pytest-asyncio missing)
Note: `run_code` is only reachable through the agent tool path, so it has no live check; it is unit-tested and follows the same pattern verified live for `run_file` in the run-file ticket.

### Smoke test (2026-11-09)
`pytest backend tests` 1134+ pass, only the 10 baseline failures; ruff clean.
None yet.

PR: https://github.com/archit342000/My-AI/pull/80, branch bugfix/live-run-error-text, base develop

## Verification
### Verification plan (2026-11-09, light form)
The real backend app on 5099 (throwaway DATA_DIR) with the code runner deliberately unreachable and a distinctive dummy key; a WebSocket client against `/api/tools/code-execution/ws`; `scripts/v23.py`. Never touches :5000/:5001 or containers.
| ID | Criterion | Scenario | Expected |
|----|-----------|----------|----------|
| V1 | AC3 | live run of a missing file | `Error: File 'nope.py' does not exist.` then exit 1 (unchanged) |
| V2 | AC3 | live run of an unsupported extension | the unchanged "not supported" message, exit 1 |
| V3 | AC1 | runner unreachable | `Error: Code runner is unavailable.`; the key in neither the frames nor the app log; event logged |
| V4 | AC1 | a database error while resolving the path (`workspace/main.py` with the chats table moved away) | fixed message, exit 1, only the exception type logged |
Not run yet.

### Results (2026-11-09)
**Commit verified:** 2e81c08 (+ uncommitted). Hashes: app.py dfdd1cbe, code_executor.py 54ec43a7, test_app.py 32bff97c, test_code_executor.py 8699701b.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | v1-v4.log |
| V2 | PASS | v1-v4.log |
| V3 | PASS | v1-v4.log: fixed message; no key in the frames or the app log; `code_execution_ws_proxy_error` with ConnectionRefusedError |
| V4 | PASS | v1-v4.log: fixed message; one `code_execution_ws_prepare_error` event with OperationalError (the first attempt's V4 never reached this path: v1-v4-attempt1-weak-v4.log) |

Teardown: app stopped, ports free, /tmp removed, containers and git status unchanged. **Verdict: verified (4/4 PASS).** Gap: `run_code` (agent tool path) has no live check.

## Review history
### Round 1 - 2026-11-09
Verdict: Request changes (1 MAJOR). Scope: origin/develop 2e81c08..working tree, 4 files, single Haiku reviewer.
- R1-1 [MAJOR] the outer handler reported every failure (malformed init, settings read, ...) as "Code runner is unavailable" - Static - Fixed (the runner connection has its own try with that message; the outer handler says `Error: Code execution failed.`; events carry a `stage`; test for a settings failure). Small deviation from the plan, which named the one message for the outer handler
- R1-2 [MINOR] the outer path sends no exit frame, unlike the prepare path - Static - Not in the plan: that path never sent one; follow-up
- R1-3 [MINOR] only the exception type is logged, so an operator cannot tell a refusal from a timeout - Static - Rejected: the plan says to log the type name because the message can carry the URL with the key; richer (redacted) logging can follow now that the key moved to a header
- R1-4 [MINOR] no test for a non-runner failure reaching the outer handler - Static - Fixed (settings failure)
- R1-5 [NIT] duplicate/inline imports in the new tests - Static - Fixed (module-level, asyncio.run explained)
- R1-6 [NIT] run_code still logs the exception text - Static - No change: it goes to the server log, the URL has no key (header), the requirement says to leave it
Resolution: fixed 3, rejected 1, 1 to follow-up, 1 no change. Checks: `pytest backend tests` only the baseline failures, ruff clean. Runtime change (app.py): live V1-V4 re-run, all PASS (v1-v4-rerun.log).

## Log
- 2026-11-09: created (follow-up found while planning MYAI-2 to MYAI-16)
- 2026-11-09: plan validated, 1 Haiku round.
- 2026-11-09: linked relates_to MYAI-5 (MYAI-5 changes collect_project_files errors that the live-run WebSocket reports)
- 2026-11-09: linked relates_to MYAI-12 (tool error messages to the model, different layers)
- 2026-11-09: linked relates_to MYAI-26 (same fix for run_code and the WebSocket)
- 2026-11-09: linked conflicts_with MYAI-27 (same app.py WebSocket handler)
- 2026-11-09: linked conflicts_with MYAI-28 (app.py code_execution_ws_proxy)
- 2026-11-09: autopilot started (batch-autopilot)
- 2026-11-09: implemented, smoke tests pass
- 2026-11-09: verified live, 4/4 PASS
- 2026-11-09: review round 1 Request changes (1 MAJOR fixed); fixed 3, rejected 1, 1 to follow-up; live re-run PASS
- 2026-11-09: shipped, PR https://github.com/archit342000/My-AI/pull/80
- 2026-11-09: batch-autopilot: shipped, base develop
- 2026-11-09: closed (PR merged into develop)
