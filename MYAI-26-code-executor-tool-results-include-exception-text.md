---
id: MYAI-26
title: "code_executor tool results include exception text"
status: done
created: 2026-11-09
updated: 2026-11-09
links:
  conflicts_with: [MYAI-4, MYAI-5]
  relates_to: [MYAI-23]
---

## Description
Found while planning MYAI-23. `backend/tools/implementations/code_executor.py` still puts raw exception text into tool results returned to the model and shown in the UI: `run_file` (path resolve, line 199; runner unavailable, line 299), `install_packages` (line 386) and the packages list (line 417). MYAI-23 fixes `run_code` and the live-run WebSocket only. `docs/standards/security.md` and `errors-and-logging.md`: no `str(e)` of internal exceptions; details via `log_event`.

## Acceptance criteria
- [x] The four sites return short fixed `Error: ...` messages with no exception text
- [x] Details are logged with `log_event` (type name, no secrets)
- [x] Known user-facing messages (file does not exist, not supported) are unchanged

## Plan

**Date:** 2026-11-09  **Status:** Validated  **Base:** origin/develop 6a13e04

### Objective
Stop four tool results in `backend/tools/implementations/code_executor.py` from carrying raw exception text to the model and UI. Return short fixed `Error: ...` messages and log the details with `log_event`. Messages that are already ours and user-facing stay unchanged.

### Context
- Requirement: Description and Acceptance criteria above.
- Sites on develop:
  - `run_file`, path resolve (lines 195-199): `except Exception as e: return f"Error: Failed to resolve file path: {e}"`. The resolver, `resolve_owner_and_physical_path` (`backend/file_system/utils.py`), raises `ValueError` with our own messages (reserved `workspace/` paths, missing chat; lines 50, 70). It also calls `db.get_chat` via `get_workspace_for_chat` (lines 28, 48), so DB errors of other types can come through. Those are internal.
  - `run_file`, runner call (lines 294-299): `... Code runner service is unavailable: {e}`.
  - `install_packages` (lines 381-386): `... Failed to install packages. Code runner service is unavailable: {e}`.
  - `list_packages` (lines 412-417): `... Failed to fetch packages. Code runner service is unavailable: {e}`.
  - The three runner `except`s (lines 298, 385, 416) also call `logger.error(f"...{e}")`; the path-resolve `except` logs nothing today (server log only; the API key is sent in a header, not the URL, so `requests` exception text doesn't contain it).
- `code_executor.py` doesn't import `log_event` (imports at lines 1-12). MYAI-23 adds `from backend.logging import log_event` and fixes `run_code` the same way.
- Tests: `backend/tools/tests/test_code_executor.py` (`test_install_packages_approved` line 79, `test_list_packages` 99, `test_run_file` 117; `requests` and `db` are patched).
- Linked:
  - MYAI-4 Step 4 adds a 400 branch in `install_packages` before `raise_for_status()` (conflicts_with).
  - MYAI-5 adds `resolve_run_target` and reworks `run_file`'s path resolution (conflicts_with).
  - MYAI-23 is the same fix for `run_code` (relates_to).
- Rules:
  - `docs/standards/security.md` and `api.md`: no `str(e)` of internal exceptions.
  - `docs/standards/errors-and-logging.md`: `log_event` names `<component>_<event>`; tool results start with `Error`.
  - `docs/standards/testing.md`.

### Approach
- **Path resolve in `run_file`.**
  - `except ValueError as e:` returns `f"Error: Failed to resolve file path: {e}"` (our messages, unchanged).
  - `except Exception as e:` returns `"Error: Failed to resolve file path."` and logs `log_event("code_executor_resolve_error", {"chat_id": chat_id, "path": path, "error": type(e).__name__})`.
  - If MYAI-5 has landed, apply the same split to wherever `run_file` now calls `resolve_run_target`. MYAI-5 lets the resolver's `ValueError` propagate there.
- **Runner-unavailable messages** (`run_file`, `install_packages`, `list_packages`): drop `: {e}`, and add `log_event("code_executor_<fn>_error", {"chat_id": chat_id, "error": type(e).__name__})` beside the existing `logger.error`, with `<fn>` being `run_file`, `install_packages` or `list_packages`.
  - In `install_packages`, keep MYAI-4's 400 branch (if landed) before `raise_for_status()`. Its `Error: Invalid package request: <detail>` text is the runner's validation message, not an exception.
- **Import:** add `from backend.logging import log_event` if MYAI-23 hasn't already.
- Log the type name only, matching MYAI-23.
- The catch-all `except Exception` blocks stay (existing code; `errors-and-logging.md` discourages them in new code). The added `log_event` call stops them from masking failures (AGENTS.md rule 5).

### Steps
#### Step 1: Fix the four sites
- **Files:** `backend/tools/implementations/code_executor.py` (modify): `run_file` (path-resolve `except`, runner `except`), `install_packages` and `list_packages` `except`s; the import.
- **Change:** as in Approach.
- **Verification:** Step 2 tests.

#### Step 2: Tests
- **Files:** `backend/tools/tests/test_code_executor.py` (modify).
- **Change:** patch `backend.tools.implementations.code_executor.log_event` in each new test (`log_event` writes under `GENERAL_LOG_DIR`).
  - `run_file`:
    - with `resolve_owner_and_physical_path` patched to raise `ValueError("Path is reserved")`, the result is `Error: Failed to resolve file path: Path is reserved`;
    - with it raising `RuntimeError("db locked at /secret")`, the result is exactly `Error: Failed to resolve file path.` and `log_event` is called with `code_executor_resolve_error`.
  - `run_file`, `install_packages`, `list_packages`: with `requests.post`/`get` raising `ConnectionError("boom http://x")`, each result is the fixed message without `"boom"`, and `log_event` is called with the matching event.
  - Setup notes: the `run_file` runner test follows `test_run_file`'s pattern (a temp dir plus patched `resolve_owner_and_physical_path`, test_code_executor.py:117-148), because `run_file` returns "does not exist" before the runner call when the file is missing. The `install_packages` test patches `request_clarification`, as `test_install_packages_approved` does (line 88).
  - The "File '...' does not exist." and "... is not supported" messages (code_executor.py:202, 208) are asserted unchanged.
  - Existing tests still pass.
- **Verification:** `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q backend/tools/tests/test_code_executor.py`, then `... -m pytest -q backend`.

#### Step 3: Full gate
- **Change:** run `venv/bin/ruff check .`, the `tests` suite in its own process, and `scripts/check.sh`. No docs change (`errors-and-logging.md` already states the rule).
- **Verification:** all pass.

### Tests
- Preconditions: a `venv` with `requirements.txt` and `requirements-dev.txt`.
- `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q backend`, then the same with `tests`.
- `venv/bin/ruff check .`, then `scripts/check.sh`.

### Risks and open questions
- **Merge order.** Land after MYAI-4, MYAI-5 and MYAI-23 (same file and functions; see links), then apply the changes to their versions of the functions.
- **The agent sees less detail on a runner outage.** "Service is unavailable" is enough to retry or tell the user; the detail is in the logs.
- No blocking open questions.

### Success criteria
- [ ] The four sites return fixed `Error: ...` messages with no exception text (Steps 1-2)
- [ ] Details are logged with `log_event`, type name only (Step 2)
- [ ] Resolver `ValueError` messages and the "does not exist" / "not supported" messages are unchanged (Step 2)
- [ ] All checks pass

### Validation log
- Round 1 (2026-11-09, Haiku): PASS, 7 MINOR. My judgement: PASS. Applied:
  - resolver exception types corrected (it can pass through DB errors);
  - the logger claim corrected;
  - test setup for run_file and install_packages;
  - AC3 assertions added;
  - the catch-all rationale stated.
  The venv precondition was already covered.

## Implementation notes

### Autopilot run (2026-11-09)
Batch 7 item. Branch bugfix/code-executor-error-text from origin/develop 2e81c08, PR base develop. Dirty files before start: none. The open PRs for the run-file, run_code and install changes touch the same functions and the end of the test file: expect conflicts; keep theirs and re-apply the split.

### Baseline (2026-11-09)
At develop 2e81c08: `pytest backend tests` only the 10 async-plugin failures.

### Implementation progress
- [x] Step 1: `from backend.logging import log_event`; the four sites: `run_file` path resolve (`ValueError` keeps the resolver's message, anything else returns `Error: Failed to resolve file path.` and logs `code_executor_resolve_error` with the path capped at 200 characters and the type name), `run_file`, `install_packages` and `list_packages` runner failures return fixed `... Code runner service is unavailable.` text and log `code_executor_run_file_error`, `code_executor_install_packages_error`, `code_executor_list_packages_error` (chat id, type name)
- [x] Step 2: six sync tests (`asyncio.run`, because the older tests in the file need pytest-asyncio): the resolver's own message, an internal resolver failure, the unchanged "does not exist" and "not supported" messages, and each runner failure
- [x] Step 3: ruff clean; no docs change; scripts/check.sh not run as a whole (pytest-asyncio missing)

### Smoke test (2026-11-09)
`pytest backend tests` 1135 pass, only the 10 baseline failures (6 in this file, asyncio-marked); ruff clean.
None yet.

PR: https://github.com/archit342000/My-AI/pull/81, branch bugfix/code-executor-error-text, base develop

## Verification
### Verification plan (2026-11-09, light form)
The real backend app on 5099 (throwaway DATA_DIR, code runner unreachable, distinctive dummy key) for `run-file`; the real `install_packages` and `list_packages` functions (agent-only, no route) called in-process against the same unreachable runner with the user approval stubbed; `scripts/v26.py`. Never touches :5000/:5001 or containers.
| ID | Criterion | Scenario | Expected |
|----|-----------|----------|----------|
| V1 | AC3 | run-file on an unsupported extension | the unchanged message |
| V2 | AC1, AC2 | run-file with the runner unreachable | fixed message, no exception text, event logged |
| V3 | AC1, AC2 | run-file with a database error while resolving (`workspace/...`, chats table moved away) | `Error: Failed to resolve file path.`, one event |
| V4 | AC1, AC2 | install_packages and list_packages with the runner unreachable | fixed messages, one event each |
Not run yet.

### Results (2026-11-09)
**Commit verified:** 2e81c08 (+ uncommitted). Hashes: code_executor.py 30a54912, test_code_executor.py 6837ad99.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | v1-v4.log |
| V2 | PASS | v1-v4.log: `Error: Failed to execute file. Code runner service is unavailable.`; the connection error is only in the event (type name) |
| V3 | PASS | v1-v4.log |
| V4 | PASS | v1-v4.log: both fixed messages, one event each |

Teardown: app stopped, ports free, /tmp removed, containers and git status unchanged. **Verdict: verified (4/4 PASS).** Gap: the "does not exist" message is covered by a unit test and was verified live in the run-file ticket.

## Review history
### Round 1 - 2026-11-09
Verdict: Request changes (1 MAJOR). Scope: origin/develop 2e81c08..working tree, 2 files, single Haiku reviewer.
- R1-1 [MAJOR] the catch-all resolve handler sliced a non-string `path` (`path[:200]`), so an odd JSON value turned a handled error into an escaping TypeError - Static - Fixed (`str(path)[:200]`; tests for an int, a dict and a 500-character path)
- R1-2 [MINOR] the `ValueError` branch returns any ValueError's text, not only the resolver's own messages - Static - Rejected: the plan specifies exactly this split; a dedicated resolver exception would change the resolver (follow-up idea)
- R1-3 [MINOR] other sites (`run_code`, the route, the WebSocket) still carry exception text - Static - Out of scope; handled in their own changes
- R1-4 [MINOR] repeated local imports in the new tests - Static - Fixed
- R1-5 [MINOR] no test of the path cap or a non-string path - Static - Fixed (same tests as R1-1)
- R1-6 [NIT] only the resolve event logs the path - Static - No change: the plan asks for it
Resolution: fixed 3, rejected 1, 2 out of scope/no change. Checks: `pytest backend tests` only the baseline failures, ruff clean. Runtime change (`str(path)`): live V1-V4 re-run, all PASS (v1-v4-rerun.log).

## Log
- 2026-11-09: created (follow-up found while planning MYAI-17 to MYAI-25)
- 2026-11-09: linked conflicts_with MYAI-4 (install_packages in code_executor.py)
- 2026-11-09: linked conflicts_with MYAI-5 (run_file in code_executor.py)
- 2026-11-09: linked relates_to MYAI-23 (same fix for run_code and the WebSocket)
- 2026-11-09: plan validated, 1 Haiku round.
- 2026-11-09: autopilot started (batch-autopilot)
- 2026-11-09: implemented, smoke tests pass
- 2026-11-09: verified live, 4/4 PASS
- 2026-11-09: review round 1 Request changes (1 MAJOR fixed); fixed 3, rejected 1; live re-run PASS
- 2026-11-09: shipped, PR https://github.com/archit342000/My-AI/pull/81
- 2026-11-09: batch-autopilot: shipped, base develop
- 2026-11-09: closed (PR merged into develop)
