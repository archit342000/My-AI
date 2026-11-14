---
id: MYAI-28
title: "CODE_RUNNER_MAX_TIMEOUT is defined but never enforced"
status: done
created: 2026-11-09
updated: 2026-11-09
links:
  conflicts_with: [MYAI-4, MYAI-22, MYAI-23, MYAI-27]
  relates_to: [MYAI-17]
---

## Description
Found while planning MYAI-17. `backend/config.py:397` defines `CODE_RUNNER_MAX_TIMEOUT` (120 s), but nothing reads it. The execution timeout comes from the `code_runner_timeout` setting (`code_executor.py:58, 251`), and the runtime accepts any client timeout (`code_runner_mcp/server.py:39, 173`). A large setting allows unbounded runs and can exceed MYAI-17's relay idle timeout (600 s).

## Acceptance criteria
- [x] The backend clamps the timeout to `CODE_RUNNER_MAX_TIMEOUT` for run_code, run_file and live runs
- [x] The runtime rejects or clamps a timeout above its own maximum
- [x] The settings UI or API rejects values above the maximum with 400

## Plan

**Date:** 2026-11-09  **Status:** Validated  **Base:** origin/develop 6a13e04

### Objective
Bound every code execution timeout:
- The backend clamps the `code_runner_timeout` setting to `CODE_RUNNER_MAX_TIMEOUT` for `run_code`, `run_file` and live runs.
- The settings API rejects out-of-range values with 400.
- The runtime clamps any client timeout to its own ceiling, which stays below the relay idle timeout planned in MYAI-17.

### Context
- Requirement: Description and Acceptance criteria above.
- Config (`backend/config.py:396-397`): `CODE_RUNNER_DEFAULT_TIMEOUT` (env, 30) and `CODE_RUNNER_MAX_TIMEOUT` (env, 120). Nothing reads `CODE_RUNNER_MAX_TIMEOUT`.
- Readers of the setting, `db.get_setting("code_runner_timeout", config.CODE_RUNNER_DEFAULT_TIMEOUT)`:
  - `run_code` (`backend/tools/implementations/code_executor.py:58`) and `run_file` (line 251). Both send `timeout` to the runner and wait `timeout + 5` on `requests.post`.
  - Live runs: `code_execution_ws_proxy` (`app.py:155`) puts it in the WebSocket `config_payload`.
- Writes: `update_system_settings` (`backend/tools/router.py:317-331`) stores any key and value with no validation. `get_system_settings` (around line 311) fills in the default.
- UIs:
  - React: `SystemSettingsModal.tsx:93` has a number input with `min={1}` and no max, and no tests.
  - Legacy: the `static/index.html:709` slider is `min="5" max="120"`, which matches the default max.
- Runtime (`code_runner_mcp/server.py`):
  - `ExecuteRequest.timeout: Optional[int] = 30` (line 39), passed to `CodeExecutor.execute`.
  - The WebSocket reads `config_data.get("timeout", 30)` (line 173) and passes it to `asyncio.wait_for` (line 297).
  - Neither caps the value.
  - The runtime image has no `backend/`, so it can't read `backend/config.py`. A module constant isn't a configuration read (`python.md`'s rule is about reading config and env), so no exception is needed.
- MYAI-17 plans a relay idle timeout of 600 s and notes that silent runs longer than about 590 s would be cut (relates_to).
- Rules:
  - `docs/standards/api.md`: 400 for invalid input, `{"error": ...}`.
  - `docs/standards/python.md`: config through `backend/config.py`.
  - `docs/standards/frontend.md`: components with logic get Testing Library tests.
  - `docs/standards/testing.md`.

### Approach
- **One backend helper.** `effective_code_runner_timeout() -> int` in `backend/tools/implementations/code_executor.py`:
  - reads the setting, falling back to `config.CODE_RUNNER_DEFAULT_TIMEOUT`;
  - accepts an int (not a bool) or a digit string. Anything else raises `ValueError("code_runner_timeout setting is invalid")` and logs `log_event("code_executor_timeout_invalid", {"value_type": ...})`. There's no silent default (AGENTS.md rule 5). The callers surface it: `run_code` and `run_file` return `Error: The code runner timeout setting is invalid. Fix it in Settings.`, and the WebSocket proxy sends the same text as a `stderr` frame, then `exit 1`. Step 2 stops new invalid values from being stored, so this only covers values already in the DB;
  - clamps to `1..config.CODE_RUNNER_MAX_TIMEOUT`.
  Used at `code_executor.py:58`, `code_executor.py:251` and `app.py:155` (imported there next to `collect_project_files`). Add `from backend.logging import log_event` to `code_executor.py` (it has none on develop, lines 1-12; skip it if a sibling ticket already added it, without duplicating). The existing `timeout + 5` waits then follow the clamped value.
- **Settings validation.** In `update_system_settings`, if `code_runner_timeout` is present it must be an integer (a JSON number or a digit string; not a bool) in `1..CODE_RUNNER_MAX_TIMEOUT`. Otherwise return 400 `{"error": "code_runner_timeout must be an integer from 1 to <max>"}` before any `set_setting` call, so nothing is partly written. Other keys are unchanged.
- **Expose the max.** `get_system_settings` adds a read-only `code_runner_max_timeout: config.CODE_RUNNER_MAX_TIMEOUT`.
  - `update_system_settings` skips that key if a client sends it back, so it's never stored.
  - React: `api/settings.ts` gets an optional field. The timeout input reads `max` from `system.data.code_runner_max_timeout`, not from the `runner` state, so it's never posted. With no field, there's no `max` attribute, and no hard-coded copy of the default.
  - Legacy: `static/js/settings-manager.js` sets `this.nodes.codeRunnerTimeout.max` from the same field where it loads the settings (around line 781). Set it before `.value`, because a range input clamps a value to its current max on assignment. When the field is absent, the HTML `max="120"` stays.
- **Runtime ceiling.** Add a module constant `MAX_TIMEOUT = 580` in `code_runner_mcp/server.py`, with a comment naming the relay `IDLE_TIMEOUT` (600) dependency. One helper is used by both paths: `_parse_timeout(value: object) -> int`.
  - `None` gives 30.
  - A `bool` raises `ValueError`.
  - An `int` is clamped to `1..MAX_TIMEOUT`.
  - A `str` of ASCII digits is converted with `int()`, then clamped.
  - Anything else raises `ValueError("timeout must be an integer")`.
  - `/execute`: change the field to `timeout: StrictInt | str | None = None` (Pydantic `StrictInt`, so bools and floats aren't coerced by lax mode). Bools, floats and lists fail model validation, giving FastAPI's 422. A non-digit string passes the model as `str`; `execute_code` calls `_parse_timeout(req.timeout)` and turns its `ValueError` into `HTTPException(400, "timeout must be an integer")`.
  - WebSocket: inside the handler's existing `try`, read `config_data.get("timeout")` and call `_parse_timeout` in its own `try/except ValueError`, before `prepare_sandbox`. On `ValueError`, send a `stderr` frame `Error: timeout must be an integer.` and an `exit` frame with code 1, log `logger.warning`, and return, so the outer `except` (server.py:~326) never sees it (AGENTS.md rule 5: no silent fallback). An explicit `null` gives 30, as a missing key does.
  - `None` now means 30 on both paths. Today, `None` on `/execute` reaches `subprocess.run(timeout=None)` (executor.py:253, 273), which means no timeout at all. This is an intended change.
  - Out-of-range integers are clamped, not rejected, so callers that send large values keep working.
- Rejected: a Pydantic `Field(le=...)` on the runtime model. FastAPI would return 422, not the documented 400, and the WebSocket path would need separate handling anyway.

### Steps
#### Step 1: Backend helper and callers
- **Files:** `backend/tools/implementations/code_executor.py` (modify): the `log_event` import; new `effective_code_runner_timeout`, with a docstring and hints; `run_code`; `run_file`. `app.py` (modify): `code_execution_ws_proxy`. Extend the function-local import beside `collect_project_files` (around line 147) with `effective_code_runner_timeout`, use it at line 155, and catch its `ValueError` to send the stderr and exit frames.
- **Change:** as in Approach.
- **Verification:** Step 4 tests.

#### Step 2: Settings API
- **Files:** `backend/tools/router.py` (modify): `update_system_settings` (add the function-local `from backend import config`, as `get_system_settings` has), `get_system_settings`. `frontend/src/api/settings.ts`, `frontend/src/features/settings/SystemSettingsModal.tsx` and `static/js/settings-manager.js` (modify): the max field.
- **Change:** as in Approach.
- **Verification:** Step 4 tests.

#### Step 3: Runtime clamp
- **Files:** `code_runner_mcp/server.py` (modify): add `import logging` and `logger = logging.getLogger(__name__)` (server.py has neither); new `MAX_TIMEOUT` and `_parse_timeout(value: object) -> int` with a docstring; `ExecuteRequest.timeout` (`StrictInt | str | None`, importing `StrictInt` from pydantic); `execute_code`; the WebSocket handler (line 173), with the explicit `try/except ValueError` described in Approach.
- **Change:** as in Approach.
- **Verification:** Step 4 runtime tests.

#### Step 4: Tests
- **Files:** `backend/tools/tests/test_code_executor.py`, `backend/tools/tests/test_router.py`, `tests/test_app.py`, `code_runner_mcp/tests/test_server.py` (modify); `frontend/src/features/settings/SystemSettingsModal.test.tsx` (create).
- **Change:**
  - Helper (patch `db.get_setting` and `log_event`): 30 gives 30; 500 gives `CODE_RUNNER_MAX_TIMEOUT`; 0 and -5 give 1; `"45"` gives 45.
  - `run_code` and `run_file` send the clamped timeout in the payload and use `timeout + 5` with the clamped value.
  - The app WebSocket test asserts the clamped `timeout` in `config_payload`.
  - Settings POST:
    - `{"code_runner_timeout": 500}`, `0`, `true` and `"x"` give 400 with `set_setting` not called;
    - `{"code_runner_timeout": 60, "other": 1}` gives 200 with both set.
  - Settings GET includes `code_runner_max_timeout`.
  - Runtime:
    - direct `_parse_timeout` tests: 10000 gives `MAX_TIMEOUT`; 0 gives 1; 30 gives 30; `None` gives 30; `"10"` gives 10; `True`, `"x"`, `1.5` and `[]` raise `ValueError`;
    - `/execute` with `timeout: 10000`, `"10"` or `null` calls `CodeExecutor.execute` with `MAX_TIMEOUT`, 10 or 30. Patch `server.CodeExecutor.execute` with `return_value=ExecutionResult(stdout="", stderr="", exit_code=0, execution_time_ms=1, language="python", timed_out=False)` (the response model, executor.py:10-17) and read its `timeout` kwarg. `true`, `1.5` and `[]` give 422 (model validation); `"x"` gives 400 (helper);
    - the WebSocket with `timeout: 10000` calls `_parse_timeout` with 10000 and runs with its result. Patch `server._parse_timeout` with `wraps=` the real function and assert the call and return value. The existing real-code `test_websocket_execute` (test_server.py:58-76) still completes;
    - the WebSocket with `timeout: "x"` or `true` gets the `Error: timeout must be an integer.` frame and exit code 1, not a "Server error" frame;
    - the WebSocket with `timeout: null` runs normally.
  - Backend helper: a stored `true` or `"abc"` raises `ValueError` and logs. `run_code` then returns the settings error message, and the WebSocket proxy sends it as a stderr frame.
  - React (`SystemSettingsModal.test.tsx`): mock `settingsApi.getSystem` with `vi.spyOn(settingsApi, 'getSystem').mockResolvedValue(...)`, the pattern in `PersonasDialog.test.tsx:13`. The timeout input has `max` equal to `code_runner_max_timeout`, and no `max` when the field is absent. Saving doesn't send `code_runner_max_timeout`.
  - Settings POST with `code_runner_max_timeout` in the body doesn't store it.
- **Verification:**
  - `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q backend`, then the same with `tests`;
  - `cd code_runner_mcp && PYTHONPATH=. ../venv/bin/python -m pytest -q`;
  - `cd frontend && npm run typecheck && npm run lint && npm run test`.

#### Step 5: Docs and full gate
- **Files:**
  - `code_runner_mcp/README.md` (modify): one line on the runtime `MAX_TIMEOUT` (580 s), its relation to the relay idle timeout, and the WebSocket rejecting a non-integer timeout.
  - `backend/config.py` comment on `CODE_RUNNER_MAX_TIMEOUT`: it must stay at or below the runtime `MAX_TIMEOUT`.
- **Change:** run `venv/bin/python -m ruff check .` and `scripts/check.sh`.
- **Verification:** all pass.

### Tests
- Preconditions: a `venv` with `requirements.txt` and `requirements-dev.txt`; `npm ci` in `frontend/`.
- The three Python suites and the frontend checks, as in Step 4; then `scripts/check.sh`.

### Risks and open questions
- **Stored values above the max** are clamped at run time; a stored value of the wrong type is an error the user sees. In the React settings the stored value shows until it is saved again. On the legacy slider, a stored value above the max shows as the max (range inputs clamp), while its label (settings-manager.js:782) still shows the stored value. Saving replaces it with the max.
- **Legacy slider.** Its `min` stays at 5 and its `max` now follows the API field.
- **Two ceilings.** The backend max is env-configurable; the runtime max is a constant (580). If the env value is raised above 580, the runtime clamps silently. The `config.py` comment states the limit.
- **Overlap.** `code_executor.py` is also edited by MYAI-4, 5, 23 and 26 (different lines). `app.py`'s handler is edited by MYAI-23 and 27, and `update_system_settings`' body read by MYAI-22. Expect small rebases.
- No blocking open questions.

### Success criteria
- [ ] `run_code`, `run_file` and live runs use a timeout clamped to `CODE_RUNNER_MAX_TIMEOUT` (Steps 1 and 4)
- [ ] The runtime clamps any client timeout to `MAX_TIMEOUT` (Steps 3-4)
- [ ] The settings API rejects out-of-range or non-integer timeouts with 400, writing nothing (Steps 2 and 4)
- [ ] The React settings input caps at the configured max (Step 4)
- [ ] All checks pass

### Validation log
- Round 1 (2026-11-09, Haiku): FAIL, 1 BLOCKING and 9 MINOR. My judgement: FAIL is valid; applied as follows.
  - B1: a non-integer WebSocket timeout was silently defaulted (AGENTS.md rule 5). Valid. The WebSocket now rejects it with an error frame and a log; `/execute` already returns 422.
  - M2: the "MYAI-4 exception" wasn't relevant to a constant. Reworded.
  - M3: ruff form. Valid. Now `venv/bin/python -m ruff`.
  - M4: the read-only max would be stored. Valid. Skipped server-side, and not put in the React `runner` state.
  - M5: `_clamp_timeout` direct tests. Added.
  - M6: the import is now unconditional (no duplicate).
  - M7: README named.
  - M8: the hard-coded 120 fallback was removed, and the test mock is specified.
  - M9: the legacy slider max follows the API.
  - M10: confirmation.
- Round 2 (2026-11-09, Haiku, diff-scoped): FAIL, 1 BLOCKING and 8 MINOR. My judgement: FAIL is valid; all were applied.
  - B1: server.py has no `logger`. Valid (grep). The import and logger are added in Step 3 Files.
  - M2: legacy `max` must be set before `value`. Fixed.
  - M3: `None` on `/execute` means no timeout today. Valid (executor.py:253, 273). Now mapped to 30, as an intended change, with a test.
  - M4: lax coercion of digit strings. Both paths now accept the same inputs.
  - M5: config import in the POST route. Added.
  - M6: the `app.py` local import line. Added.
  - M7: how the clamp is observed. Wrapped `wait_for` and patched `execute`.
  - M8: the helper's fallback. It now raises, and callers surface a settings error (rule 5).
  - M9: bool handling. Bools are rejected in both layers.
- Round 3 (2026-11-09, Haiku, diff-scoped): FAIL, 1 BLOCKING and 7 MINOR. My judgement: FAIL is valid. Simplified to one runtime helper, `_parse_timeout`, used by both paths.
  - B1: Pydantic lax mode coerces `true` to 1. Valid (checked by the validator on 2.12.5). The field is now `StrictInt | str | None`; the helper rejects bools, and the route returns 400.
  - M2-M4: signature, digit-string conversion and WebSocket `null`. Resolved by the single helper.
  - M5: `wait_for` patching was fragile. Replaced by `wraps=` on `_parse_timeout`.
  - M6: execute mock return value. Specified.
  - M7: legacy slider display. Reworded.
  - M8: placement relative to the outer `except`. Specified.
- Round 4 (2026-11-09, Haiku, diff-scoped): FAIL, 1 BLOCKING (status code claim). Round 3's B1 was confirmed resolved: StrictInt rejects bools (the validator ran Pydantic 2.12.5).
  - B1: a bool on `/execute` gets 422 from the model, not 400. Valid. The Approach and tests now say 422 for bool, float and list, and 400 for a non-digit string. The validator's own run confirms this, so the change is text only.
  Marked Validated: no BLOCKING left after round 4 (stop rule).

## Implementation notes

### Autopilot run (2026-11-09)
Batch 7 item. Branch bugfix/code-runner-max-timeout from origin/develop 2e81c08, PR base develop. Dirty files before start: none. MYAI-4 (PR #77, open) also edits code_runner_mcp/server.py and its tests: expect conflicts there.

### Baseline (2026-11-09)
At develop 2e81c08: `pytest backend tests` only the 10 async-plugin failures; frontend vitest 311 pass; runner tests need `pip --target /tmp/gen/crdeps -r code_runner_mcp/requirements.txt httpx` (32 pass, 1 skipped).

### Implementation progress
- [x] Step 1: `effective_code_runner_timeout()` in code_executor.py (int or digit string, clamped to `1..CODE_RUNNER_MAX_TIMEOUT`; any other stored type raises ValueError and logs `code_executor_timeout_invalid`); used by `run_code`, `run_file` (error text `Error: The code runner timeout setting is invalid. Fix it in Settings.`) and the live-run WebSocket proxy in app.py (stderr frame plus exit 1, no connection)
- [x] Step 2: `update_system_settings` rejects a non-integer or out-of-range `code_runner_timeout` with 400 before writing anything and never stores `code_runner_max_timeout`; `get_system_settings` returns the read-only max; the React input gets `max`, the legacy slider's max is set from the API before its value
- [x] Step 3: runtime `MAX_TIMEOUT = 580`, `_parse_timeout` (None gives 30, bools/floats/non-digit strings rejected, integers clamped); `/execute` takes `StrictInt | str | None` (400 for a bad string, 422 for a bool or float); the WebSocket sends an `Error: timeout must be an integer.` frame and exit 1; comment on `CODE_RUNNER_MAX_TIMEOUT` in config.py
- [x] Step 4: tests in all five places; new SystemSettingsModal.test.tsx
- [x] Step 5: code_runner_mcp/README.md; ruff clean; scripts/check.sh not run as a whole (pytest-asyncio missing)
Correction to the plan text: relay.py has no idle timeout yet (that is MYAI-17), so the comments and README say "planned".

### Smoke test (2026-11-09)
`pytest backend tests` 1153+ pass, only the 10 baseline failures; runner tests 49 pass + 1 skipped; vitest 314 pass; tsc clean; lint clean; build ok; ruff clean.
None yet.

PR: https://github.com/archit342000/My-AI/pull/78, branch bugfix/code-runner-max-timeout, base develop

## Verification
### Verification plan (2026-11-09, full form: limits across runtime, backend and two UIs)
Runner in a throwaway container (existing image, new code mounted read-only, published only on 127.0.0.1:5090, dummy key, unique name) so code never runs on the host; the real backend app on 5099 (throwaway DATA_DIR, `CODE_RUNNER_MAX_TIMEOUT=3`) against it; Playwright for the UIs. Scripts in `scripts/`.
| ID | Criterion | Scenario | Expected |
|----|-----------|----------|----------|
| V1 | AC2 | runtime `/execute` with 100000, "x", true, and 0 (sleeping code) | 200, 400, 422; timeout 0 clamps to 1 s and times out |
| V2 | AC3 | settings API: GET, bad values, a valid value, the read-only max | max 3 reported; 500/4/0/-1/"x"/true give 400 and store nothing; valid accepted; max never stored |
| V3 | AC1 | stored 9999 (max 3), run-file on code that sleeps 8 s | timed out after 3 s |
| V4 | AC1 | stored "abc" | the settings error text, no silent default |
| V5 | AC1 | the live-run WebSocket with stored 9999 | timed out after 3 s |
| V6 | AC3 | React System settings | timeout input max = 3 |
| V7 | AC3 | legacy System settings | slider max = 3 |
Not run yet.

### Results (2026-11-09)
**Commit verified:** 2e81c08 (+ uncommitted). Hashes: code_executor.py 1c99f8c9, app.py 243f6849, router.py 812daaa2, config.py 03f754f7, server.py c6e9b14a, README.md ae806990, settings.ts 609bd992, SystemSettingsModal.tsx 258a97d2, settings-manager.js df0fd503, test_code_executor.py 52c392d0, test_router.py 158ced7b, test_app.py 95f29d8e, test_server.py f731c968, SystemSettingsModal.test.tsx de1b7f8b.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | v1-v5.log: 200, 400, 422; timeout 0 timed out after 1.0 s |
| V2 | PASS | v1-v5.log: max 3; every bad value 400 with nothing stored; valid 2 accepted; no `code_runner_max_timeout` row |
| V3 | PASS | v1-v5.log: stored 9999 clamped to 3: timed out after 3.0 s |
| V4 | PASS | v1-v5.log: "Error: The code runner timeout setting is invalid. Fix it in Settings." |
| V5 | PASS | v1-v5.log: "Execution timed out after 3 seconds." after 3.0 s |
| V6 | PASS | v6-v7.log: input max = 3 |
| V7 | PASS | v6-v7.log: slider max = 3 (the first attempt read it before opening System Settings, a harness error: v6-v7-attempt1-modal-not-opened.log) |

Teardown: runner container removed, app stopped, ports free, containers, images and git status unchanged. **Verdict: verified (7/7 PASS).** Gap: the runtime's 580 s ceiling itself is covered by unit tests only (a live run that long was not attempted).

## Review history
### Round 1 - 2026-11-09
Verdict: Approve with comments. Scope: origin/develop 2e81c08..working tree, 14 files, single Haiku reviewer.
- R1-1 [MINOR] CODE_RUNNER_MAX_TIMEOUT above the runtime's 580 is advertised but clamped silently by the runtime - Static - Rejected: the plan accepts the two-ceiling gap (Risks) and the comment in config.py states the limit
- R1-2 [MINOR] a digit string over 4300 characters made the settings POST return 500 - Static - Fixed (digit strings over 9 characters are invalid: 400; test; live: 5000 digits gives 400)
- R1-3 [MINOR] the same stored value raised without the `code_executor_timeout_invalid` log - Static - Fixed (same length rule inside the validated branch; test)
- R1-4 [MINOR] a valid string such as "045" was stored as a string - Static - Fixed (stored as an integer; test; live: stored 2)
- R1-5 [MINOR] the WebSocket clamp test did not show the clamped value reaching the run - Static - Fixed (asserts the `asyncio.wait_for` timeout is 580)
- R1-6 [MINOR] no run_code clamp test - Static - Fixed
- R1-7 [MINOR] the legacy slider markup still says min 5 / max 120 - Static - Rejected: the plan keeps min 5 and the markup max as the fallback
- R1-8 [MINOR] the legacy label showed the stored value while the slider clamped - Static - Fixed (the label shows the slider's real value)
- R1-9 [MINOR] no legacy test for the max handling - Static - Fixed (two node tests)
- R1-10 [MINOR] non-null assertions in the new React test - Static - Fixed
- R1-11 [NIT] the touched input line is over 100 columns - Static - Rejected: the line was already long; reformatting it would enlarge the diff
- R1-12 [NIT] the runner's 400 uses FastAPI's `detail` - Static - Rejected: the runner's existing shape, never reached by the app
- R1-13 [NIT] README names a relay hardening change that is not in the repo - Static - Rejected: stated as "planned"
Resolution: fixed 8, rejected 5. Checks: `pytest backend tests` only the baseline failures, runner tests 49 pass, vitest 314 pass, legacy node tests 254 pass, ruff clean. Runtime changes: live V1-V7 re-run, all PASS (v1-v5-rerun.log, v6-v7-rerun.log).

## Log
- 2026-11-09: created (follow-up found while planning MYAI-17 to MYAI-25)
- 2026-11-09: linked relates_to MYAI-17 (the relay idle timeout must stay above the max execution timeout)
- 2026-11-09: plan validated, 4 Haiku rounds.
- 2026-11-09: linked conflicts_with MYAI-22 (update_system_settings body read and validation)
- 2026-11-09: linked conflicts_with MYAI-4 (ExecuteRequest and the execute_ws handler in code_runner_mcp/server.py)
- 2026-11-09: linked conflicts_with MYAI-27 (execute_ws handler and app.py code_execution_ws_proxy)
- 2026-11-09: linked conflicts_with MYAI-23 (app.py code_execution_ws_proxy)
- 2026-11-09: autopilot started (batch-autopilot)
- 2026-11-09: implemented, smoke tests pass
- 2026-11-09: verified live, 7/7 PASS
- 2026-11-09: review round 1 Approve with comments; fixed 8, rejected 5; live re-run PASS
- 2026-11-09: shipped, PR https://github.com/archit342000/My-AI/pull/78
- 2026-11-09: batch-autopilot: shipped, base develop
- 2026-11-09: closed (PR merged into develop)
