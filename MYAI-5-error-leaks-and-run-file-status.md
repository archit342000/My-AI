---
id: MYAI-5
title: "S4 and S5: raw errors returned to clients; missing file returns 200"
status: done
created: 2026-11-08
updated: 2026-11-09
links:
  conflicts_with: [MYAI-3, MYAI-11, MYAI-22, MYAI-26]
  relates_to: [MYAI-23]
---

## Description
Report S4 (Low) and S5 (Low). S4: backend/tools/router.py returns upstream error text (MCP Server error: resp.text, line 281) and str(e) (lines 286, 103, 144) to clients. S5: /code-execution/run-file returns 200 with an error string when the file does not exist (run_file in code_executor.py). Suggested fix: generic messages to clients with details logged via log_event(); 404 for a missing file. Not blocked.

## Acceptance criteria
- [x] Upstream error text and exception strings are not returned to clients
- [x] Missing file returns 404 with a short error body
- [x] Details still appear in logs

## Plan
**Date:** 2026-11-09  **Status:** Validated

### Objective
Stop `backend/tools/router.py` returning upstream response text and `str(e)` to clients, and make `POST /api/tools/code-execution/run-file` return `404` with a short `{"error": ...}` body when the file does not exist. Failure details move to `log_event()` (and stay in the app log), per the errors-and-logging and API standards.

### Context
- Requirement: Description and Acceptance criteria above. Branch from `origin/develop` (read at `6a13e04`); line numbers below are from that commit.
- Rules:
  - `docs/standards/api.md` (Requests and responses): error body `{"error": "<short message>"}`; `404` not found, `400` invalid input, `500` unexpected; no `str(e)` of internal exceptions.
  - `docs/standards/security.md` (Errors): short message, no stack traces or internal paths; details to `log_event` / app log.
  - `docs/standards/errors-and-logging.md`: `log_event(event_type, data)` for handled errors; `event_type` is `<component>_<event>` ending in `_error`; `data` flat with ids and an `error` string; truncate large blobs; tools return `Error...` text for expected failures (agent contract).
  - `docs/standards/api.md` (Structure): routes stay thin; logic lives in domain code.
  - `docs/standards/testing.md`: update/add tests in `backend/tools/tests/`; a bug fix adds a regression test.
- Current behaviour (`backend/tools/router.py`):
  - `get_preferences` (def l.97, except l.102-103) and `reset_preferences` (def l.138, except l.143-144) return `{"error": str(e)}`, 500, with no logging.
  - `proxy_portal_init` (def l.270, body to l.286): on non-200 upstream it returns `{"error": f"MCP Server error: {resp.text}"}` with the upstream status (l.281); on any exception `{"error": str(e)}`, 500 (l.286). Both log via `logger.error` only.
  - `api_run_file` (def l.345, body to l.371): calls `code_executor.run_file` and always returns `{"result": result}` with 200, even when `result` is an error string; its `except` returns `{"error": str(e)}`, 500 (l.371).
- Current behaviour (`backend/tools/implementations/code_executor.py`, `run_file` l.180-): resolves the path with `resolve_owner_and_physical_path` (from `backend/file_system/utils.py`, raises `ValueError` for reserved `workspace/` paths or a missing chat_id), returning `"Error: Failed to resolve file path: {e}"`; returns `"Error: File '{path}' does not exist."` when `os.path.exists` is false (l.201-202); on runner failure returns `"Error: Failed to execute file. Code runner service is unavailable: {e}"` (l.299). `collect_project_files` (l.135-178, used by the live-run WebSocket in `app.py:145-152`) repeats the same two resolves (target and chat root, l.137-138) and the existence check, raising `FileNotFoundError`.
- Callers: React `frontend/src/api/settings.ts` (preferences), `frontend/src/api/filesystem.ts` `portalApi.init`; legacy `static/js/browser-portal.js:116` reads `err.error`. No UI calls `/code-execution/run-file` (grep of `frontend/src` and `static/js`). The `{"error": ...}` shape is unchanged, so no client changes are needed.
- Existing tests: `backend/tools/tests/test_router.py` (`test_get_preferences`, `test_reset_preferences`, `test_proxy_portal_init`, `test_proxy_portal_init_error` expects 500 for a generic `Exception`, `test_run_file_defaults_sql_target_to_sqlite` patches `run_file` with chat_id `c1` and a non-existent file); `backend/tools/tests/test_code_executor.py` (`test_run_file`).
- Assumptions (no user available):
  - A1: upstream non-200 from `/portal/init` is returned as `502` (bad gateway) rather than passing the upstream status through, matching the existing precedent in `proxy_portal_vnc` (l.267). `docs/standards/api.md` does not list 502, but it is the established code for an unreachable/failed upstream in this file; `httpx.HTTPError` (connect/timeout) also maps to `502` "Could not reach browser portal service"; any other exception stays `500` with a generic message.
  - A2: the run-file route pre-checks existence via a shared helper; a path that fails to resolve (`ValueError`) returns `400` "Invalid file path".
  - A3: the agent-facing `Error...` strings from `run_file` stay as they are (tool contract), except dropping the raw `{e}` from the runner-unavailable message, which is reachable from the run-file route and already logged.

### Approach
- Replace each `str(e)` / `resp.text` response with a short fixed message and add a `log_event(..., {"error": ...})` call (keeping `logger.error`/`logger.exception` for the app log). Event names: `tools_preferences_get_error`, `tools_preferences_reset_error`, `tools_portal_init_error` (with `status_code` and upstream body truncated to 500 chars), `tools_run_file_error` (with `chat_id`, `path`).
- For the 404: add a small public helper in `code_executor.py`, `resolve_run_target(chat_id, path) -> tuple[str, str]` (new), that resolves the target and chat-root paths, lets the resolver's exceptions propagate (its `ValueError` means invalid input) and raises `FileNotFoundError` when the target does not exist; `collect_project_files` reuses it. `run_file` uses it and converts the exceptions to its current `Error...` strings (agent behaviour unchanged). `api_run_file` calls it before `run_file` and maps `FileNotFoundError` to `404 {"error": "File not found"}`, `ValueError` to `400 {"error": "Invalid file path"}`, and anything else to a logged generic 500. This keeps the router thin and the logic in one place.
- Rejected: matching `result.startswith("Error: File '")` in the route (brittle string coupling); making `run_file` raise (breaks the agent tool contract in `docs/tools.md`); a structured result type from `run_file` (larger change than needed).

### Steps
#### Step 1: Generic errors for preferences routes
- **Files:** `backend/tools/router.py` (modify) `get_preferences`, `reset_preferences`.
- **Change:** in each `except Exception as e`, call `log_event("tools_preferences_get_error" | "tools_preferences_reset_error", {"error": str(e)})` and `logger.exception(...)`, and return `{"error": "Failed to load preferences"}` / `{"error": "Failed to reset preferences"}` with 500.
- **Verification:** new router tests (Tests section) assert 500, the fixed message, that the exception text is absent from the body, and that `log_event` was called with the error.

#### Step 2: Generic errors for `/portal/init`
- **Files:** `backend/tools/router.py` (modify) `proxy_portal_init`.
- **Change:** non-200 upstream: `log_event("tools_portal_init_error", {"status_code": resp.status_code, "error": resp.text[:500]})`, keep `logger.error`, return `{"error": "Browser portal failed to start"}`, 502. `httpx.HTTPError`: log, return `{"error": "Could not reach browser portal service"}`, 502. Other `Exception`: log, return `{"error": "Failed to start browser portal"}`, 500.
- **Verification:** tests for upstream non-200 (body text absent, 502, logged), `httpx.ConnectError` (502), generic `Exception` (500, message text absent); existing `test_proxy_portal_init` still passes.

#### Step 3: Shared run-target resolver
- **Files:** `backend/tools/implementations/code_executor.py` (modify) `run_file`; new function `resolve_run_target`.
- **Change:** add `resolve_run_target(chat_id, path) -> tuple[str, str]` returning `(physical_target_path, chat_root_dir)`: both `resolve_owner_and_physical_path` calls (l.196-197 / l.137-138), no wrapping of resolver exceptions (the resolver's own `ValueError`s for invalid input propagate as-is; any other exception, such as a DB failure in `get_workspace_for_chat`, also propagates unchanged), then `FileNotFoundError(f"File '{path}' does not exist.")` when the target does not exist. `run_file` replaces its try/except (l.195-199) and existence check (l.201-202) with one call, catching `FileNotFoundError` first (returns `Error: File '...' does not exist.`) and then `Exception` (returns `Error: Failed to resolve file path: {e}`), exactly as now. `collect_project_files` replaces its l.137-141 with the same call (same exception types and messages as now, so `app.py` is unaffected). Change the runner-unavailable return (l.299) to `"Error: Failed to execute file. Code runner service is unavailable."`; this wording change is intentional (the string reaches clients in the run-file 200 body, and the exception is already logged at l.298).
- **Verification:** `test_run_file` still passes; new `test_code_executor.py` tests for `resolve_run_target` (existing file returns path, missing raises `FileNotFoundError`, bad path raises `ValueError`) using `tmp_path` with `resolve_owner_and_physical_path` patched; a test that `run_file` on a missing file still returns the `does not exist` string; a test that the runner-unavailable result does not contain the exception text. Tests go in the existing `backend/tools/tests/test_code_executor.py`, where this module is already tested (`docs/standards/testing.md` rule 1 requires `backend/tools/implementations/tests/`; the current location is a pre-existing deviation this plan leaves in place, since moving the file is out of scope).

#### Step 4: 404 and generic 500 for run-file
- **Files:** `backend/tools/router.py` (modify) `api_run_file`.
- **Change:** after the 400 input check, import and call `resolve_run_target(chat_id, path)` (local import from `backend.tools.implementations.code_executor`, as `run_file` is now), in its own `try` block placed before the existing `run_file` try, with clauses in this order: `except FileNotFoundError`, `except ValueError`, `except Exception` (the last logs `tools_run_file_error` and returns the generic 500 below), so only resolver input errors become 400 and a `ValueError` from `run_file` itself is not misreported; `FileNotFoundError` returns `{"error": "File not found"}`, 404; `ValueError` returns `{"error": "Invalid file path"}`, 400. In the existing `except`, add `log_event("tools_run_file_error", {"chat_id": chat_id, "path": path, "error": str(e)})` and return `{"error": "Failed to run file"}`, 500.
- **Verification:** router tests (patch `backend.tools.implementations.code_executor.resolve_run_target` and `run_file`): an existing file reaches `run_file` and returns 200 `{"result": ...}`; missing file returns 404 with the short body and `run_file` not called; `ValueError` returns 400; a generic resolver exception returns 500 without its text and calls `log_event`; `run_file` raising returns 500 without the exception text and calls `log_event`. Update `test_run_file_defaults_sql_target_to_sqlite` to also patch `resolve_run_target` so it reaches `run_file`.

#### Step 5: Run checks
- **Files:** none.
- **Change:** run the suites below.
- **Verification:** all pass; `grep -n "str(e)\|resp.text" backend/tools/router.py` shows matches only inside `log_event`/`logger` calls.

### Tests
- Add/update in `backend/tools/tests/test_router.py` (Steps 1, 2, 4) and `backend/tools/tests/test_code_executor.py` (Step 3); patch `backend.tools.router.log_event` to assert logging, and `httpx.Client.post` / `run_file` / `resolve_run_target` at the boundary.
- Commands (repo root): `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest backend/tools/tests -q`, then `backend/tools/implementations/tests`, `backend/tests`, `tests`, then `scripts/check.sh --python-only` (ruff + all Python suites). No frontend change, so the frontend suite is not required.

### Risks and open questions
- Overlap MYAI-3: it will add `X-MCP-API-KEY` to `proxy_portal_init`. Same function, different lines; whichever lands second rebases. With A1, an upstream 401 (missing key) surfaces as 502, which avoids confusing it with the app's own auth.
- Overlap MYAI-2: changes `proxy_portal_vnc` (auth to websockify); this plan does not touch that function.
- Overlap MYAI-11: changes `delete_preference` to 404 in the same file; this plan does not touch `delete_preference` or `update_preference`.
- `run_code` in `code_executor.py` (l.98) has the same `{e}` in its runner-unavailable string; it is not reachable from a router endpoint, so it is left as-is (follow-up candidate, not in scope).
- Changing the `/portal/init` upstream-failure status from passthrough to 502 is a minor contract change; both UIs only read `err.error` and `res.ok`, so they are unaffected.
- `app.py` live-run WebSocket (l.149-150) sends `f"Error: {e}"` from `collect_project_files` to the client; its messages are the fixed `does not exist`/`not supported` texts or resolver `ValueError`s, and it is outside `router.py`, so it is not changed here (follow-up candidate).
- `backend/tools/implementations/README.md` does not list `code_executor.py` at all (pre-existing gap); this plan does not change that README, as adding a helper does not alter the documented components. Follow-up candidate.
- `run_file` keeps `Error: Failed to resolve file path: {e}` for non-input resolver failures (agent contract). Via the route this is only reachable if the resolver fails on `run_file`'s second resolve after the pre-check succeeded (transient DB error). Accepted as a narrow residual; the implementer may use a fixed message for the non-`ValueError` branch if it does not break `test_code_executor.py`.
- No blocking open questions.

### Success criteria
- [ ] No response body from `backend/tools/router.py` contains `str(e)` or upstream `resp.text` (preferences get/reset, portal init, run-file).
- [ ] `POST /api/tools/code-execution/run-file` with a non-existent file returns 404 `{"error": "File not found"}`.
- [ ] Each replaced error path calls `log_event` with an `_error` event and the detail in `error`.
- [ ] Agent-facing `run_file` behaviour for a missing file is unchanged.
- [ ] `scripts/check.sh --python-only` passes.


### Validation log
- **Round 1** (Haiku): PASS, 8 MINOR. My judgement: pass. Valid and fixed: run_file also needs `chat_root_dir` (helper now returns both paths); `collect_project_files` duplicates the resolve/exists check (helper reused there); 502 not in api.md (precedent `proxy_portal_vnc` l.267 cited in A1); test location vs testing.md rule 1 (noted as pre-existing deviation); implementations README gap (noted in Risks, no change); missing happy-path route test (added); line refs (corrected); runner-unavailable wording change (stated as intentional).
- **Round 2** (Haiku): PASS, 6 MINOR. My judgement: pass. Valid and fixed: re-raise must keep message text; ordering of the resolver call vs the generic `except`; testing.md wording ("requires", not "suggests"). Accepted: 502 (already justified in A1), app.py WebSocket `str(e)` (out of scope, in Risks).
- **Round 3** (Haiku): FAIL, 1 BLOCKING, 3 MINOR. My judgement: BLOCKING valid — wrapping every resolver exception as `ValueError` would turn a DB failure in `get_workspace_for_chat` (`backend/file_system/utils.py` l.48) into 400. Fixed: no wrapping; route resolves in its own try with `FileNotFoundError`->404, `ValueError`->400, other->logged 500; test added. MINOR valid and fixed: Tests commands now include `backend/tools/implementations/tests`; explicit except handling for the pre-check. Test-location MINOR already addressed.
- **Round 4** (Haiku): PASS, 4 MINOR. My judgement: pass; round-3 BLOCKING confirmed resolved against `code_executor.py` l.135-202, `app.py` l.145-152, `router.py` l.345-371. Past round 3 with no valid BLOCKING, so stopped. MINORs: residual `{e}` in run_file's resolve-failure string (accepted, logged in Risks, implementer's discretion); 502 and test location (accepted, already disclosed); double resolve per request (accepted, negligible cost).

## Implementation notes

### Autopilot run (2026-11-09)
Batch 7 item. Branch bugfix/error-bodies-and-missing-file from origin/develop 2e81c08, PR base develop. Dirty files before start: none. The plan's line numbers predate the merged batches (the router now uses `read_json_object`); the changes were located by function.

### Baseline (2026-11-09)
At develop 2e81c08: `pytest backend tests` only the 10 async-plugin failures (backend/tools: 8 asyncio-marked).

### Implementation progress
- [x] Step 1: preferences get/reset: fixed messages, `logger.exception` and `tools_preferences_*_error` events
- [x] Step 2: portal init: upstream non-200 gives 502 "Browser portal failed to start", `httpx.HTTPError` 502 "Could not reach browser portal service", other errors 500 "Failed to start browser portal"; `tools_portal_init_error` events (upstream text capped at 500 chars in the event only)
- [x] Step 3: `resolve_run_target` in code_executor.py, used by `run_file` and `collect_project_files`; agent-facing strings unchanged except the runner-unavailable message, which no longer carries the exception text
- [x] Step 4: `api_run_file`: 404 "File not found", 400 "Invalid file path", generic 500 "Failed to run file" with `tools_run_file_error` events
- [x] Step 5: no `str(e)`/`resp.text` left in a response body of the router (the remaining matches are inside `log_event` calls); ruff clean. scripts/check.sh not run as a whole (pytest-asyncio missing)
Note: the existing `test_run_file` (asyncio-marked, cannot run here) exercises the changed `run_file`; the new sync tests and the live check cover the same paths.

### Smoke test (2026-11-09)
`pytest backend tests` 1160+ pass, only the 10 baseline failures; ruff clean.
Status on develop (checked at e327094, 2026-11-08): Still present on develop: str(e) and resp.text returned at backend/tools/router.py:281, 286; run-file returns 200 with the error string.

PR: https://github.com/archit342000/My-AI/pull/76, branch bugfix/error-bodies-and-missing-file, base develop

## Verification
### Verification plan (2026-11-09, full form: error handling across four routes)
Real backend app (5099, throwaway DATA_DIR), small fake upstreams (code runner on 5097, browser portal on 5096), `scripts/v5.py`. Never touches :5000/:5001, containers or a real chats.db.
| ID | Criterion | Scenario | Expected |
|----|-----------|----------|----------|
| V1 | AC2 | run-file on a missing file | 404 `{"error": "File not found"}` |
| V2 | regression | run-file on an existing file | 200 with the result |
| V3 | AC1, AC3 | portal init, upstream 500 with a traceback body | 502 generic, upstream text only in the log event |
| V4 | AC1, AC3 | preferences get and reset with the table renamed away (real DB error) | 500 generic, "no such table" only in the log events |
| V5 | AC1 | run-file with the runner down | 200 with the fixed "service is unavailable" text, no address or exception text |
| V6 | AC1 | portal init, upstream unreachable | 502 "Could not reach browser portal service" |
Not run yet.

### Results (2026-11-09)
**Commit verified:** 2e81c08 (+ uncommitted). Hashes: router.py b1a02c32, code_executor.py 68691ebb, test_router.py 38e83489, test_code_executor.py 132a4f33.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | v1-v6.log: 404 {"error":"File not found"} |
| V2 | PASS | v1-v6.log: 200 with the execution result |
| V3 | PASS | v1-v6.log: 502 generic; the traceback text found only in the `tools_portal_init_error` event |
| V4 | PASS | v1-v6.log: both routes 500 generic; "no such table" only in the two log events |
| V5 | PASS | v1-v6.log: the fixed message without the connection error |
| V6 | PASS | v1-v6.log: 502 without the port or exception text |

Teardown: processes stopped, ports free, /tmp data removed, containers and git status unchanged. **Verdict: verified (6/6 PASS).**

## Review history
### Round 1 - 2026-11-09
Verdict: Approve with comments. Scope: origin/develop 2e81c08..working tree, 4 files, single Haiku reviewer.
- R1-1 [MINOR] the app-log line still carried the full upstream body - Static - Fixed (capped at 500 chars like the event)
- R1-2 [MINOR] agent-path "Failed to resolve file path: {e}" still embeds exception text - Static - Fixed (input `ValueError`s keep the resolver message for the agent; any other resolver failure returns a fixed string and is logged; the plan allowed this)
- R1-3 [MINOR] user-supplied `path` unbounded in log events - Static - Fixed (capped at 200 chars)
- R1-4 [MINOR] only the missing-file case is a 404; other run_file failures (unsupported extension, runner unavailable) are still 200 with an error string - Static - Not in the plan or the ticket's criteria (AC2 names the missing file): recorded in the PR notes and for the follow-up ticket
- R1-5 [MINOR] portal init non-200 now always 502 - Static - Rejected: the plan's explicit choice (A1); the callers read only `error` and `ok`; stated in the PR notes
- R1-6 [MINOR] weak log assertion, no truncation test - Static - Fixed (exact event assertion, 500-char cap test)
- R1-7 [MINOR] no route test through the real resolver - Static - Fixed (404 and 200 through the real `resolve_run_target`)
- R1-8 [NIT] the route and run_file resolve the path twice - Static - Rejected: acceptable, the plan's design; a race could only turn into the agent error string
- R1-9 [NIT] extra blank lines - Static - Fixed
Resolution: fixed 6, rejected 2, disclosed/deferred 1. Checks: `pytest backend tests` only the baseline failures, ruff clean. Runtime change (logging, run_file branch): live V1-V6 re-run, all PASS (v1-v6-rerun.log).

## Log
- 2026-11-08: created from reports/full-scope-final-report-2026-11-08.md
- 2026-11-09: plan validated, 4 rounds
- 2026-11-09: linked conflicts_with MYAI-3 (both edit proxy_portal_init in backend/tools/router.py)
- 2026-11-09: linked conflicts_with MYAI-11 (adjacent preference routes in backend/tools/router.py)
- 2026-11-09: linked conflicts_with MYAI-22 (preference routes' body reads in backend/tools/router.py)
- 2026-11-09: linked relates_to MYAI-23 (MYAI-5 changes collect_project_files errors that the live-run WebSocket reports)
- 2026-11-09: linked conflicts_with MYAI-26 (run_file in code_executor.py)
- 2026-11-09: autopilot started (batch-autopilot)
- 2026-11-09: implemented, smoke tests pass
- 2026-11-09: verified live, 6/6 PASS
- 2026-11-09: review round 1 Approve with comments; fixed 6, rejected 2, 1 to follow-up; live re-run PASS
- 2026-11-09: shipped, PR https://github.com/archit342000/My-AI/pull/76
- 2026-11-09: batch-autopilot: shipped, base develop
- 2026-11-09: closed (PR merged into develop)
