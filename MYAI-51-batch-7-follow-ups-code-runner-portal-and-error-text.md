---
id: MYAI-51
title: "Batch 7 follow-ups: dockerignore secrets, package-list drift, install pre-validation, error-text leftovers"
status: todo
created: 2026-11-09
updated: 2026-11-20
---

## Description
Items found in the reviews of the batch 7 PRs (#74 to #83) that the validated plans did not cover. Each is small and independent; they can be split when planned.

1. **`.dockerignore` lacks `secrets/` and `.env*` (from MYAI-16, R1-3).** `docs/standards/security.md` says they are ignored, but `.dockerignore` does not list them, and the pkg-proxy and code-runner builds use context `..` (the repo root), so the secrets directory is sent to the builder. The images are clean (the Dockerfiles only COPY what they need). Fix the file or the standard, and check every Dockerfile's COPY lines.
2. **Package list duplicated (from MYAI-16, R1-10).** The baked package list appears in the `install_packages` description (`backend/tools/catalog/code.py`) and in `code_runner_mcp/requirements-sandbox.txt`; nothing checks that they match. Add a test that compares the names, or build the description from one source.
3. **`install_packages` approval shows unvalidated specs (from MYAI-4, R1-8, R1-9).** The user approves raw specs before the runner validates them (no backend pre-validation), and a runner 422 is reported as "service unavailable" (only 400 is mapped).
4. **`run_file` failure statuses (from MYAI-5, R1-4).** Only a missing file is a 404; an unsupported extension or an unavailable runner still returns 200 with an error string. Also `backend/tools/implementations/README.md` does not list `code_executor.py`.
5. **`proxy_portal_init` error text (from MYAI-3).** It still returns `resp.text` / `str(e)` on non-401 errors; use fixed messages with the detail in `log_event`.
6. **Live-run outer error path sends no exit frame (from MYAI-23, R1-2).** The prepare path sends one; the outer path never did. The frontend may wait for it.
7. **Resolver exception type (from MYAI-26, R1-2).** `run_file`/`run_code` map any `ValueError` to the resolver's text; a dedicated resolver exception would avoid returning an unrelated `ValueError`'s message.
8. **x11vnc is passwordless inside the container (from MYAI-2, R1-3).** Documented as an accepted residual (processes in the container can reach it); a generated `-rfbauth` password would close it.
9. **pkg-proxy egress is limited only by nginx (from MYAI-16).** The network (`pkg-egress`) is a normal bridge; the optional host `DOCKER-USER` rule is documented but not applied or tested. Decide whether to ship and verify the rule.
10. **Two timeout ceilings (from MYAI-28 R1-1 and MYAI-17).** `CODE_RUNNER_MAX_TIMEOUT` (default 120) and the runtime's fixed 580 differ, and the relay's 600 s idle timeout depends on the code_runner_timeout staying below it; align or document them in one place.

## Acceptance criteria
- [ ] `secrets/` and `.env*` are in `.dockerignore` (or the standard is corrected), with a check
- [ ] A test fails when the install_packages description and `requirements-sandbox.txt` disagree
- [ ] A bad package spec or a runner 422 gives a clear error to the user
- [ ] `run_file` returns a proper status for unsupported extensions and an unavailable runner, with tests
- [ ] `proxy_portal_init` and the live-run outer path return fixed messages and an exit frame, with tests
- [ ] The resolver raises its own exception type
- [ ] A decision is recorded for the x11vnc password and the DOCKER-USER rule
- [ ] The timeout ceilings are aligned or documented once

## Plan

**Date:** 2026-11-20  **Status:** Validated

### Objective
Close the batch 7 review leftovers: keep secrets out of Docker build contexts, guard the baked package list against drift, give clear errors for bad package specs and for files that cannot run, send an exit frame on every live-run failure, stop passing arbitrary `ValueError` text to people, record the x11vnc and DOCKER-USER decisions, and document the timeout chain in one place.

### Context
- Requirement: items 1-10 and the eight acceptance criteria. The owner chose one plan for all ten items (2026-11-20).
- Item 1: `.dockerignore` lacks `.env`, `.env.*` and `secrets/`, contradicting `docs/standards/security.md` ("`.env`, `.env.*` and `secrets/` are gitignored and in `.dockerignore`"). Every compose build uses context `..`; `docker/Dockerfile.rag-grid-search` (`docker/docker-compose.testing.yml`) does `COPY --chown=appuser:appuser . .`, so it would bake them in. Other Dockerfiles COPY only named files.
- Item 2: the `install_packages` description (`backend/tools/catalog/code.py` `INSTALL_PACKAGES`) lists numpy, pandas, scipy, matplotlib, requests, sympy, beautifulsoup4, pyyaml, pillow, tabulate; `code_runner_mcp/requirements-sandbox.txt` pins the same ten. Nothing checks they match. Catalog tests: `backend/tools/catalog/tests/test_catalog.py`.
- Item 3: `install_packages` (`backend/tools/implementations/code_executor.py`) asks for approval with the raw specs, then posts `/install`; a runner 400 becomes `"Error: Invalid package request: <detail>"`, a 422 (FastAPI body validation) falls to "Code runner service is unavailable". Runner rules: `code_runner_mcp/package_names.py` `validate_packages` (max 20 specs, 100 chars each, pip and npm patterns).
- Item 4: `api_run_file` (`backend/tools/router.py`) returns 404 for a missing file and 400 "Invalid file path" for any `ValueError`, then `200 {"result": <text>}` for everything else, including an unsupported extension (`"Error: File extension '<ext>' is not supported for execution."`) and an unavailable or busy runner (`RUNNER_BUSY_MESSAGE`, `RUNNER_UNAVAILABLE_MESSAGE`, and the literal "Error: Failed to execute file. Code runner service is unavailable."). A non-string `path` is not rejected. `backend/tools/implementations/README.md` does not list `code_executor.py`. Clients: `frontend/src/api/filesystem.ts` `runFile`, and the legacy UI's run action in `static/script.js`.
- Item 5: `proxy_portal_init` (`backend/tools/router.py`) already answers fixed messages (503/502/500); its logs still use `resp.text[:500]` and `str(e)` instead of `error_detail(e)`.
- Item 6: the live-run WebSocket (`app.py` `code_execution_ws_proxy`) sends `{"type":"exit","code":1}` after the prepare and setup errors, but not after "First message must be init.", "Missing filePath or chat_id.", the connect failure, or the outer `except Exception`. `tests/test_app.py` asserts the current frames (the outer path and connect failure send stderr only).
- Item 7: the tool `run_file` already passes only `PathRuleError` (`backend/file_system/utils.py`) through and hides other `ValueError`s. The WebSocket prepare path echoes `f"Error: {e}"` for every `ValueError` from `collect_project_files`, including the unsupported-extension `ValueError` it raises itself, and the tool returns `"Error: File '<path>' does not exist."` for a missing file.
- Item 8: `playwright_mcp/entrypoint.sh` starts `x11vnc ... -nopw ... -localhost`; `docs/standards/security.md` and `playwright_mcp/README.md` record it as an accepted residual.
- Item 9: the host `DOCKER-USER` rule for `myai-pkg-egress` is documented in `docs/standards/security.md` as optional and not applied.
- Item 10: `CODE_RUNNER_MAX_TIMEOUT` (`backend/config.py`, 120) ≤ `MAX_TIMEOUT` (`code_runner_mcp/server.py`, 580) < `IDLE_TIMEOUT` (`code_runner_mcp/relay.py`, 600); only `code_runner_mcp/README.md` explains the chain.
- Rules: `docs/standards/errors-and-logging.md` (fixed messages, `error_detail`, only the project's own exception class passes through), `docs/standards/api.md` (status codes, breaking changes update React and legacy clients), `docs/standards/security.md`, `docs/standards/docker.md`, `docs/standards/testing.md`.

### Approach
- Item 1: add `**/.env`, `**/.env.*` and `**/secrets/` (matching at any depth, like `.gitignore`), with `!.env.example` re-included; no env file exists in the tree today, so nothing a Dockerfile copies is excluded, and a future frontend `.env.*` file would be excluded from builds on purpose (secrets never go into images; `docker/Dockerfile` builds the frontend from `COPY frontend/ ./`, so such a file would not reach the build). A docs-guardrail test asserts `.dockerignore` contains them.
- Item 2: a test reads the package names from `requirements-sandbox.txt` and asserts the description lists exactly those names (order-insensitive).
- Item 3: validate specs in the backend before asking for approval by importing the runner's own rules (`from code_runner_mcp.package_names import validate_packages`, as `code_executor.py` already imports `code_runner_mcp.safety`), so there is one copy. `packages` must be a list of strings. The list and string checks run before `validate_packages` (which would accept a bare string letter by letter and raise `TypeError` on a non-string entry), and the lowercased manager name is passed, as today. Any rejection (non-list, non-string entry, or `ValueError` from the rules) returns the fixed, actionable text "Error: Some package names are not valid. Use plain names such as numpy or numpy==2.0, at most 20." and logs the detail with `error_detail`; no approval is asked. A runner 400 or 422 returns the same text (detail logged). Rejected: a backend copy of the rules (drift), a runner validation endpoint (network call before approval).
- Item 4: the run-file route keeps 500 "Could not run the file. Try again." for failures that are not input problems (a non-`ValueError` from resolving, an exception from `run_file`), and answers with `{"error": ...}` bodies: 400 for a non-string path; for resolver failures the text from `run_target_error` (item 7) without its `Error: ` prefix, with 404 for a missing file ("That file does not exist.", replacing "File not found"), 400 for `PathRuleError` and other `ValueError`s; 400 "This file type can't be run." for an unsupported extension (checked after resolving, with the same `CODE_EXTENSION_MAP`); and 503 "The code runner is unavailable. Try again shortly." when `run_file` returns `RUNNER_BUSY_MESSAGE`, `RUNNER_UNAVAILABLE_MESSAGE` or the service-unavailable result (a new constant for today's literal, which `run_file` also returns for any non-2xx from the runner). Other results (including the confirmation and cancelled texts) stay 200 `{"result": ...}`. The tool's text results for the model are unchanged apart from item 7's texts. The only caller is the React Files panel (`frontend/src/features/artifacts/FileBrowser.tsx` through `frontend/src/api/client.ts` `apiRequest`, which throws `ApiError` with the body's `error`), so no client change is needed; the legacy UI runs files over the WebSocket, not this route.
- Item 5: log with `error_detail(e)`; the upstream body stays capped in the log only. Response bodies are already fixed messages.
- Item 6: every failure path of the live-run socket ends with stderr then `{"type":"exit","code":1}`, sent through one local helper that keeps today's guard (a send to a socket the browser already closed is ignored).
- Item 7 (redesigned after two rounds: each caller decided separately what text to show): the resolver (`resolve_owner_and_physical_path` in `backend/file_system/utils.py`, wrapped by `code_executor.py` `resolve_run_target`) already raises its own class, `PathRuleError`, for every message meant for people, and `run_code` resolves no path. What is missing is one place that turns a run-target failure into text. A new `UnsupportedFileTypeError(ValueError)` (message "This file type can't be run.") replaces the plain `ValueError` that `collect_project_files` raises for an unsupported extension, and `run_file`'s own extension check returns the same text (`"Error: This file type can't be run."`). A new `run_target_error(e, scope_log) -> str` in `code_executor.py` decides the text for a failure to resolve or collect the run target: `PathRuleError` and `UnsupportedFileTypeError` → `"Error: " + their text`; `FileNotFoundError` → `"Error: That file does not exist."`; any other `ValueError` → `"Error: Could not open that file. Check the path and try again."` with `log_event("code_executor_run_target_error", {**scope_log, "error": error_detail(e)})` (the only case that logs), where `scope_log` is the route's `{"chat_id"}` or `{"workspace_id"}` dict plus the path. Non-`ValueError` failures are not passed to it: callers keep their existing internal-failure handling (the route's 500, the socket's "Could not prepare the file for execution."). The tool `run_file`, the run-file route (Step 7) and the WebSocket prepare path all call it, so no caller shows an exception's text or a path. `docs/standards/errors-and-logging.md` names `UnsupportedFileTypeError` as the second class whose wording is passed through.
- Items 8, 9: owner decisions (below).
- Item 10: document the chain once in `docs/standards/security.md` ("Tools and sandboxing" section) and replace the two chain sentences in `code_runner_mcp/README.md` with a pointer; a test reads the three values and asserts `CODE_RUNNER_MAX_TIMEOUT <= MAX_TIMEOUT` and `min(CODE_RUNNER_MAX_TIMEOUT, MAX_TIMEOUT) < IDLE_TIMEOUT` for the configured value.

### Out of scope
- Changing `x11vnc` or applying a host firewall rule before the owner decides.
- The `.env.example` file and other build-context trimming (`backend/data`, logs).

### Steps
#### Step 1: Secrets out of build contexts
- **Status:** todo
- **Depends on:** none
- **Files:** `.dockerignore` (modify); `tests/test_docs.py` (modify: new test)
- **Change:** add `**/.env`, `**/.env.*`, `**/secrets/` and `!**/.env.example`; test parses `.dockerignore` and asserts them.
- **Verification:** `pytest tests` passes and fails with an entry removed; `grep -n "COPY" docker/Dockerfile*` shows only `Dockerfile.rag-grid-search` copies the whole context (now filtered).

#### Step 2: Baked package list drift test
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/tools/catalog/tests/test_catalog.py` (modify)
- **Change:** read names (before `==`, skipping blank and `#` lines) from `code_runner_mcp/requirements-sandbox.txt`, extract the list from `INSTALL_PACKAGES`'s description, compare as sets.
- **Verification:** passes now; fails when a name is removed from either side (checked once).

#### Step 3: Validate package specs before approval
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/tools/implementations/code_executor.py` (modify: `install_packages`); `backend/tools/tests/test_code_executor.py` (modify)
- **Change:** as in Approach item 3. The existing test that expects the runner's detail in the result ("Error: Invalid package request: Invalid package: '--index-url=x'") changes on purpose to the fixed text.
- **Verification:** tests: an invalid spec, a string instead of a list and an integer entry are refused before `request_clarification` is called, and `"PIP"` still works, with the fixed text and a log; a runner 400 and a 422 give the same text, not "unavailable"; valid specs still ask for approval.

#### Step 4: One place decides a run-target failure's text
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/tools/implementations/code_executor.py` (modify: `UnsupportedFileTypeError`, `run_target_error`, `run_file`, `collect_project_files`); `app.py` (modify: prepare path calls `run_target_error` for `ValueError`/`FileNotFoundError`); `docs/standards/errors-and-logging.md` (modify: the second pass-through class); `backend/tools/tests/test_code_executor.py`, `tests/test_app.py` (modify)
- **Change:** as in Approach item 7.
- **Verification:** `run_target_error` tests for the four cases (texts; a log only for the other-`ValueError` case, with the caller's scope; the missing-file socket test keeps `assert_not_called` on the log); `run_file` tests updated on purpose: a missing file gives "Error: That file does not exist." and an unsupported extension "Error: This file type can't be run." (the tests that pin the old path-bearing and extension texts change); socket tests: `test_code_execution_ws_proxy_keeps_its_own_user_facing_messages` changes to the new texts and its extension fixture raises `UnsupportedFileTypeError`; `test_code_execution_ws_proxy_hides_an_unexpected_prepare_error_and_logs_it` (a `RuntimeError`) keeps "Could not prepare the file for execution."; an unrelated `ValueError` shows the generic text and is logged on every path.

#### Step 5: Portal init logs
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/tools/router.py` (modify: `proxy_portal_init`); `backend/tools/tests/test_router.py` (modify)
- **Change:** `error_detail(e)` in the `HTTPError` and generic logs; keep the capped upstream body in the non-200 log.
- **Verification:** tests assert the log payload uses the `Type: message` form and the response bodies are unchanged.

#### Step 6: Exit frame on every live-run failure
- **Status:** todo
- **Depends on:** Step 4 (same function and test module in `app.py` / `tests/test_app.py`)
- **Files:** `app.py` (modify: `code_execution_ws_proxy`); `tests/test_app.py` (modify)
- **Change:** a small local helper sends stderr then the exit frame, ignoring a send to an already closed socket (as the outer path does today); used by the init, missing-field, connect-failure and outer error paths. The legacy client (`static/script.js` `runFileDirectly`) already handles an exit frame after stderr (it does on the prepare path today).
- **Verification:** tests: each failure path's frames end with `{"type":"exit","code":1}` (the tests for the connect failure and the outer path are updated); a socket whose `send` raises on every call during an early-path error (init, missing field, connect failure) raises nothing; the success path is unchanged.

#### Step 7: Proper statuses from the run-file route
- **Status:** todo
- **Depends on:** Step 4
- **Files:** `backend/tools/router.py` (modify: `api_run_file`); `backend/tools/implementations/code_executor.py` (modify: a constant for today's service-unavailable literal, next to `RUNNER_BUSY_MESSAGE` and `RUNNER_UNAVAILABLE_MESSAGE`); `backend/tools/tests/test_router.py` (modify); `backend/tools/implementations/README.md` (modify: list `code_executor.py`); `docs/standards/api.md` (modify: add 503 to the status list; the run-file paragraph gains the 400, 404 and 503 cases, new text)
- **Change:** as in Approach item 4. The non-string path check runs first. The route catches `FileNotFoundError` itself for the 404 status (as today) and `ValueError` for 400, and takes the body text from `run_target_error` with the leading `Error: ` removed (404 body "That file does not exist."); the unsupported-extension 400 is checked in the route after resolving. `run_file` returns the new service-unavailable constant instead of the literal, and the route compares the result with the three constants. Logs use `str(path)[:200]`. Non-`ValueError` failures keep today's 500.
- **Verification:** route tests: non-string path 400; missing file 404 with the new body (`test_run_file_missing_file_is_a_404_and_does_not_run` and `test_run_file_missing_file_is_a_404_through_the_real_resolver` change on purpose; `test_run_file_invalid_path_is_a_400` changes to the generic text); `PathRuleError` 400 with its text; other `ValueError` 400 generic; unsupported extension 400; each of the three runner-unavailable results 503 with an `error` key; the confirmation text stays 200; `test_run_file_resolver_failure_is_a_generic_500_and_logged` still passes; a normal result is 200 `{"result": ...}`. `frontend/src/features/artifacts/FileBrowser.test.tsx` (create; no test renders `FileBrowser` today) mocks `codeExecApi.runFile` to reject with `ApiError(503, ...)` and checks the failed state shows its message (rendered with the providers and stores `FileBrowser` needs).

#### Step 8: Timeout chain documented once, with a check
- **Status:** todo
- **Depends on:** none
- **Files:** `docs/standards/security.md` (modify: "Tools and sandboxing"), `code_runner_mcp/README.md` (modify: replace the chain sentences with a pointer), `code_runner_mcp/relay.py` (modify: the comment saying nothing caps `code_runner_timeout`), `backend/tests/test_config.py` (modify: new test)
- **Change:** one paragraph: setting `code_runner_timeout` ≤ `CODE_RUNNER_MAX_TIMEOUT` ≤ runtime `MAX_TIMEOUT` (580) < relay `IDLE_TIMEOUT` (600), and why. The test reads `MAX_TIMEOUT` and `IDLE_TIMEOUT` from the two files and asserts `CODE_RUNNER_DEFAULT_TIMEOUT <= CODE_RUNNER_MAX_TIMEOUT <= MAX_TIMEOUT` and `min(CODE_RUNNER_MAX_TIMEOUT, MAX_TIMEOUT) < IDLE_TIMEOUT` for the code defaults (the config module reloaded with the two env variables unset), so the result does not depend on the environment.
- **Verification:** `pytest backend/tests/test_config.py` and `pytest tests` pass.

#### Step 9: Record the owner's decisions
- **Status:** todo
- **Depends on:** Step 8 (same file, `docs/standards/security.md`)
- **Files:** `docs/standards/security.md` (modify: the existing residual sentences in the "Authentication" section, line 17); `tests/test_docs.py` (modify: new test)
- **Change:** edit the two existing sentences in place (no second copy): x11vnc's passwordless localhost access becomes "Decision (2026-11-20): kept passwordless on the container's localhost; only processes inside `playwright_mcp` can reach it, and a password would add a secret handoff to websockify for little gain."; the optional `DOCKER-USER` rule gets "Decision (2026-11-20): left optional; the rule lives on the host, outside this repo's deploy, and limits ports only.". `playwright_mcp/README.md` unchanged.
- **Verification:** a `tests/test_docs.py` test asserts both "Decision (2026-11-20)" sentences are in `docs/standards/security.md` (fails today); `pytest tests` passes.

### Tests
- `pytest backend/tools`, `pytest backend`, `pytest tests`, `ruff check .` (env vars per `docs/standards/testing.md`); `cd code_runner_mcp && PYTHONPATH=. pytest` (parity reads its file); frontend `npm run typecheck`, `lint`, `test`; `node --test static/tests/test_script.js static/tests/test_logs.js` if the legacy caller changes; `scripts/check.sh`.

### Risks and open questions
- The backend imports the runner's package rules from `code_runner_mcp`, so a change there changes both (intended).
- The React Files panel is the only run-file caller and already shows an error body; the legacy UI uses the WebSocket and does not call the route.

### Decisions for the owner
1. **x11vnc password (item 8).** Today: passwordless on the container's localhost, accepted residual (`docs/standards/security.md`). Options: (a) keep and re-confirm the accepted risk; (b) generate an `-rfbauth` password at container start and give it to websockify's upstream connection, closing access from other processes in the container. Recommendation: (a): only processes inside `playwright_mcp` can reach it, and (b) adds a secret handoff between x11vnc and websockify for little gain.
   **Owner's answer (2026-11-20): (a)**.
2. **DOCKER-USER rule (item 9).** Today: documented, optional, not applied. Options: (a) keep it optional and say so as a decision; (b) ship a script and a verification step for the host rule. Recommendation: (a): the rule lives on the host, outside this repo's deploy, and limits ports only.
   **Owner's answer (2026-11-20): (a)**.

### Success criteria
- [ ] `secrets/` and `.env*` are in `.dockerignore`, with a check (Step 1)
- [ ] A test fails when the install_packages description and `requirements-sandbox.txt` disagree (Step 2)
- [ ] A bad package spec or a runner 422 gives a clear error (Step 3)
- [ ] `run_file` returns a proper status for unsupported extensions and an unavailable runner, with tests (Step 7)
- [ ] `proxy_portal_init` logs with `error_detail` and the live-run outer path sends an exit frame, with tests (Steps 5, 6)
- [ ] The resolver raises its own exception type: met by the existing `PathRuleError` (`backend/file_system/utils.py`), covered by the `run_target_error` tests; no other exception's text is shown on any path (Step 4)
- [ ] Decisions recorded for x11vnc and DOCKER-USER (Step 9)
- [ ] The timeout ceilings are documented once, with a check (Step 8)
- [ ] `scripts/check.sh` passes

### Reviewer brief
- Objective: close the batch 7 leftovers in one plan (owner's choice): secrets out of build contexts, a drift test for the baked package list, clear package-spec errors, proper run-file statuses, portal logs with `error_detail`, an exit frame on every live-run failure, no exception text shown for run targets, the x11vnc and DOCKER-USER decisions recorded, the timeout chain documented once.
- Key decisions: `**/` patterns in `.dockerignore` with a guardrail test; package specs validated before approval by importing `code_runner_mcp.package_names`, with one fixed actionable text; `run_target_error` decides the text for every run-target failure (only `PathRuleError` and the new `UnsupportedFileTypeError` pass their wording through) and is used by the tool, the route and the socket; the route keeps 500 for internal failures and adds 400/404/503 with `{"error"}` bodies; x11vnc stays passwordless and the DOCKER-USER rule optional (owner decisions, recorded in security.md with a test).
- Out of scope: changing x11vnc or the host firewall, `.env.example` and other build-context trimming.
- Success criteria: as listed in the plan.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
Path: pair, Haiku validators, judged against the code.
- Round 1: both FAIL. Valid (blocking): a missing-file path and package `ValueError` text shown to people; the resolver criterion had no step. Minors fixed (run-file clients, 503 in api.md, `**/` patterns, timeout chain assert, README entries, test fixtures).
- Round 2: L2 PASS; L1 FAIL. Valid: the tool's missing-file text still carried the path (blocking; second failure of per-caller text decisions) -> redesigned around one `run_target_error`.
- Round 3 (full): L1 PASS; L2 FAIL. Valid: internal resolver failures would turn from 500 into 400 (blocking). Also found that an earlier edit of mine had deleted Context items 7-10 and Approach items 1-6; rebuilt.
- Round 4 (full): both PASS. Minors fixed inline (logging branch, status mechanics, tests named, FileBrowser test, package input checks, Step 6 after Step 4).
- Owner decisions (2026-11-20): x11vnc and DOCKER-USER kept as accepted (a). Owner round 1: FAIL, valid (no automated check of the recorded decisions); fixed with an in-place edit and a docs guardrail test. Owner round 2 read a stale copy of the ticket; its issues were already fixed.

## Implementation notes

## Verification

## Review history

## Log
- 2026-11-09: created from the review findings of batch 7 (user asked for follow-ups for anything not in the plans)
- 2026-11-20: plan validated, 4 rounds (+2 owner-decision rounds)
