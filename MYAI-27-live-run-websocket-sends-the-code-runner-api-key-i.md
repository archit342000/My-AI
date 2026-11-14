---
id: MYAI-27
title: "Live-run WebSocket sends the code runner API key in the URL"
status: done
created: 2026-11-09
updated: 2026-11-09
links:
  conflicts_with: [MYAI-4, MYAI-23, MYAI-28]
  relates_to: [MYAI-32, MYAI-39]
---

## Description
Found while planning MYAI-23. `app.py` `code_execution_ws_proxy` connects to `ws://.../ws/execute?api_key=<key>`, and `code_runner_mcp/server.py` `execute_ws` reads the key from the query string. Keys in URLs end up in logs and exception text. Move the key to a header (for example `X-API-KEY`, as the HTTP routes use) on both sides.

## Acceptance criteria
- [x] The proxy sends the key in a header, not the URL
- [x] `execute_ws` accepts the header and rejects a missing or wrong key (1008)
- [x] The query-string key is no longer accepted
- [x] Live runs still work end to end

## Plan

**Date:** 2026-11-09  **Status:** Validated  **Base:** origin/develop 6a13e04

### Objective
Send the code runner API key for the live-run WebSocket in an `X-API-KEY` header instead of the `?api_key=` query string, on both the app proxy and the runner, and stop accepting the query-string form. Live runs must still work end to end.

### Context
- Requirement: Description and Acceptance criteria above.
- App side: `code_execution_ws_proxy` (`app.py:117` onwards) builds `upstream_url = f"{...}/ws/execute?api_key={api_key}"` (line 159) from `config.CODE_RUNNER_API_KEY` and calls `ws_client.create_connection(upstream_url)` (websocket-client 1.8.0, `requirements.txt`).
- Runner side: `execute_ws(websocket: WebSocket, api_key: Optional[str] = None)` (`code_runner_mcp/server.py:151-157`) reads the key from the query string. It closes with 1008 when `API_KEY and api_key != API_KEY`, and has no check at all when no key is configured. The HTTP routes use `verify_api_key` with the `X-API-KEY` header (line 26).
- Path: app, then the TCP relay `code_runner_mcp` (`code_runner_mcp/relay.py`, which forwards bytes, so headers pass through unchanged), then `code_runner_runtime`. The relay needs no change.
- No other caller: a grep for `ws/execute` finds only `app.py`, `server.py` and `code_runner_mcp/tests/test_server.py`. The browser connects to the app's `/api/tools/code-execution/ws`, never to the runner.
- Tests:
  - `code_runner_mcp/tests/test_server.py`: `test_websocket_auth_failure` (line 38), `test_websocket_sql_mysql_is_rejected` (45) and `test_websocket_execute` (58) all use `?api_key=`.
  - `tests/test_app.py::test_code_execution_ws_proxy` (line 174) asserts `create_connection.assert_called_once()`.
- Linked:
  - MYAI-4 Step 1 rewrites this key check (fail closed, `hmac.compare_digest`; conflicts_with).
  - MYAI-23 edits the same `app.py` handler's error paths (conflicts_with).
- Rules:
  - `docs/standards/security.md`: never log or echo keys; internal MCP services use their own keys.
  - `docs/standards/testing.md`: the code runner suite runs from inside `code_runner_mcp`.
  - `docs/standards/python.md`: hints and docstrings on changed functions.

### Approach
- **Runner.** Read the key from `websocket.headers.get("x-api-key")` (Starlette headers are case-insensitive) and remove the `api_key` query parameter from the signature.
  - This step only swaps where the key comes from. MYAI-4 owns the comparison (fail closed, `None` check, `hmac.compare_digest`). If MYAI-4 has landed, keep its condition and feed it the header value. If not, keep today's condition with the header value (a missing header is `None`, which is rejected whenever a key is configured).
  - A `?api_key=` query parameter is ignored, so a query-only client is rejected.
- **App.** `ws_client.create_connection(f"{base}/ws/execute", header=[f"X-API-KEY: {api_key}"])`, with no query string. This is websocket-client's list-of-strings header form, which MYAI-2 also uses.
- Rejected: accepting both forms during a transition. There's a single caller in the same repo, deployed together, so there's nothing to transition.

### Steps
#### Step 1: Runner reads the header
- **Files:** `code_runner_mcp/server.py` (modify): `execute_ws` (signature, key check, docstring, `-> None`).
- **Change:** as in Approach. Never log the key. Don't change the comparison logic itself (MYAI-4 owns it).
- **Verification:** Step 3 runner tests.

#### Step 2: App sends the header
- **Files:** `app.py` (modify): `code_execution_ws_proxy`, the `upstream_url` and `create_connection` lines.
- **Change:** as in Approach. The key no longer appears in any URL, so the exception and log text MYAI-23 deals with can't contain it.
- **Verification:** Step 3 app tests.

#### Step 3: Tests
- **Files:** `code_runner_mcp/tests/test_server.py` (modify); `tests/test_app.py` (modify).
- **Change:**
  - Runner:
    - switch the three WebSocket tests to `client.websocket_connect("/ws/execute", headers={"X-API-KEY": "testkey"})`;
    - a missing header, a wrong header, and the old `?api_key=testkey` with no header are each rejected. Assert `pytest.raises(WebSocketDisconnect)` (from `starlette.websockets`) with `exc.value.code == 1008`. Starlette 0.45.3's `websocket_connect(url, **kwargs)` passes `headers=` through.
  - App: in `test_code_execution_ws_proxy`, use `patch.object(config, "CODE_RUNNER_API_KEY", "testkey")` (`tests/test_app.py:21` imports `from backend import config`). Assert that `create_connection.call_args.args[0]` ends with `/ws/execute` and contains no `api_key`, and that `create_connection.call_args.kwargs["header"] == ["X-API-KEY: testkey"]`.
- **Verification:**
  - `cd code_runner_mcp && PYTHONPATH=. ../venv/bin/python -m pytest -q`
  - `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q tests/test_app.py`

#### Step 4: Docs, full gate, live check
- **Files:** `code_runner_mcp/README.md` (modify): one line saying `/ws/execute` takes the key in `X-API-KEY`, like the HTTP routes. Outside the repo: `~/.claude/tickets/My-AI/MYAI-1-evidence/scripts/runner_probe_relay.py` (modify line 4 to send the header instead of the query string) for the live check.
- **Change:**
  - Run `venv/bin/ruff check .`, the `backend` and `tests` suites in their own processes, and `scripts/check.sh`.
  - Live check with a throwaway compose stack following MYAI-17 Step 7's isolation rules (copy to /tmp, strip `container_name:`/`ports:`, prefix `image:` tags, repoint host-absolute binds, `--no-deps app code_runner_runtime code_runner_mcp mysql_db`):
    - **Runner boundary:** the updated probe (`runner_probe_relay.py`, header form), run from the app container through the relay, streams output. A direct `/ws/execute?api_key=<key>` connection is refused with 1008.
    - **App route:** the React UI doesn't wire live runs (`docs/frontend.md:58`), so drive the legacy UI's live run (`static/script.js` uses `/api/tools/code-execution/ws`) with Playwright: create a `main.py` artifact in a chat, run it, and check that output streams. That exercises the app proxy's header change end to end.
  - Tear the stack down afterwards.
- **Verification:** all pass; results go in Verification.

### Tests
- Preconditions: a `venv` with `requirements.txt` and `requirements-dev.txt`.
- `cd code_runner_mcp && PYTHONPATH=. ../venv/bin/python -m pytest -q`
- `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q backend`, then the same with `tests`.
- `venv/bin/ruff check .`, then `scripts/check.sh`.

### Risks and open questions
- **Merge order.** Land after MYAI-4 (same key check) and MYAI-23 (same app handler), and keep their changes.
- **Probe script.** The MYAI-1 probe (`runner_probe_relay.py`) uses the query-string form. Update it for the live check (it's an evidence script, not a repo file).
- No blocking open questions.

### Success criteria
- [ ] The proxy sends the key in `X-API-KEY`, never in the URL (Steps 2-3)
- [ ] `execute_ws` reads the header and rejects a missing or wrong key with 1008 (Steps 1 and 3)
- [ ] A query-string key is no longer accepted (Step 3, live check)
- [ ] Live runs work end to end (live check)

### Validation log
- Round 1 (2026-11-09, Haiku): PASS, 6 MINOR. My judgement: PASS. Applied:
  - the React UI doesn't wire live runs, so the app route is verified via the legacy UI (`static/script.js` uses the route);
  - the probe script is listed as a file to change;
  - exact app-test patch and assertions;
  - exact exception and 1008 assertions (headers kwarg confirmed in Starlette 0.45.3);
  - MYAI-4 owns the comparison, and this ticket only swaps the key source;
  - verification is now end to end, via the legacy UI.

## Implementation notes

### Autopilot run (2026-11-09)
Batch 7 item. Branch bugfix/live-run-ws-auth from origin/develop 2e81c08, PR base develop. Dirty files before start: none. Same code as MYAI-4 (PR #77) and MYAI-28 (PR #78) in `execute_ws` and its tests: expect conflicts; keep their changes.

### Baseline (2026-11-09)
At develop 2e81c08: `pytest backend tests` only the 10 async-plugin failures; runner tests need `pip --target /tmp/gen/crdeps -r code_runner_mcp/requirements.txt httpx` (31 pass, 1 skipped).

### Implementation progress
- [x] Step 1: `execute_ws(websocket)` reads `websocket.headers.get("x-api-key")`; the `api_key` query parameter is gone; the comparison is untouched (MYAI-4 owns it)
- [x] Step 2: `code_execution_ws_proxy` connects to `.../ws/execute` with `header=["X-API-KEY: <key>"]`
- [x] Step 3: runner tests (a missing key, a wrong key, the old query form, a right query key with a wrong header: all 1008) and the app test (no `api_key` or key in the URL, header list)
- [x] Step 4: README line; ruff clean; scripts/check.sh not run as a whole (pytest-asyncio missing). The probe script of the plan is replaced by the new live script
Deviation: the plan's throwaway compose stack and Playwright run of the legacy UI were replaced by a throwaway runner container plus the real app driven over a WebSocket (the same `/api/tools/code-execution/ws` the legacy UI uses).

### Smoke test (2026-11-09)
runner tests 35 pass + 1 skipped; `pytest backend tests` only the 10 baseline failures; tests/test_app.py 26 pass; ruff clean.
None yet.

PR: https://github.com/archit342000/My-AI/pull/79, branch bugfix/live-run-ws-auth, base develop

## Verification
### Verification plan (2026-11-09, light form)
Runner in a throwaway container (existing image, new code mounted read-only, 127.0.0.1:5090, dummy key, unique name); the real backend app on 5099 (throwaway DATA_DIR) against it; `scripts/v27.py`. Never touches :5000/:5001 or the live stack.
| ID | Criterion | Scenario | Expected |
|----|-----------|----------|----------|
| V1 | AC2, AC3 | direct to the runner: no key, wrong header, `?api_key=` only, right header | refused, refused, refused, runs and returns output |
| V2 | AC1, AC4 | a live run through the app's WebSocket proxy | streams output and exits 0; no key in any URL or log |
Not run yet.

### Results (2026-11-09)
**Commit verified:** 2e81c08 (+ uncommitted). Hashes: server.py 62d40629, app.py b1e76ab0, test_server.py 3e8d88e8, test_app.py aaf9ec8d, README.md 5842fba3.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | v1-v2.log: the three bad forms get a 403 handshake refusal (the 1008 close), the header form runs the code |
| V2 | PASS | v1-v2.log: output `live run works`, last frame exit 0 through the proxy; runner-log-lines.txt: the app's accepted connection logs as `/ws/execute` with no key, while the probe's old-form request shows the key in the URL (the leak removed); no key in the app log |

Teardown: container removed, app stopped, ports free, /tmp removed, containers, images and git status unchanged. **Verdict: verified (2/2 PASS).**

## Review history
### Round 1 - 2026-11-09
Verdict: Approve with comments. Scope: origin/develop 2e81c08..working tree, 5 files, single Haiku reviewer.
- R1-1 [MINOR] with no CODE_RUNNER_API_KEY the proxy sent the literal header `X-API-KEY: None` - Static - Fixed (empty value; test)
- R1-2 [NIT] a CR/LF in the operator-supplied key would inject a header - Static - Rejected: the key is operator config, websocket-client joins the entries, no user input reaches it
- R1-3 [NIT] the test asserts close code 1008 while the wire shows a 403 handshake - Static - Disclosed in the PR notes (a close before accept is a 403 on the wire, 1008 at the ASGI level)
Resolution: fixed 1, rejected 1, disclosed 1. Checks: runner tests pass, tests/test_app.py 27 pass, `pytest backend tests` only baseline failures, ruff clean. Runtime change (app.py): live V1-V2 re-run, all PASS (v1-v2-rerun.log).

## Log
- 2026-11-09: created (follow-up found while planning MYAI-17 to MYAI-25)
- 2026-11-09: linked conflicts_with MYAI-4 (MYAI-4 rewrites the execute_ws key check)
- 2026-11-09: linked conflicts_with MYAI-23 (same app.py WebSocket handler)
- 2026-11-09: plan validated, 1 Haiku round.
- 2026-11-09: linked conflicts_with MYAI-28 (execute_ws handler and app.py code_execution_ws_proxy)
- 2026-11-09: linked relates_to MYAI-32 (multi-user investigation covers per-user portal and code-runner isolation)
- 2026-11-09: linked relates_to MYAI-39
- 2026-11-09: autopilot started (batch-autopilot)
- 2026-11-09: implemented, smoke tests pass
- 2026-11-09: verified live, 2/2 PASS
- 2026-11-09: review round 1 Approve with comments; fixed 1; live re-run PASS
- 2026-11-09: shipped, PR https://github.com/archit342000/My-AI/pull/79
- 2026-11-09: batch-autopilot: shipped, base develop
- 2026-11-09: closed (PR merged into develop)
