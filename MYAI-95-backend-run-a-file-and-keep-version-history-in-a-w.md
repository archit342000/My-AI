---
id: MYAI-95
title: "Backend: run a file and keep version history in a workspace"
status: in-progress
created: 2026-11-11
updated: 2026-11-11
links:
  conflicts_with: [MYAI-102]
  relates_to: [MYAI-93, MYAI-96]
---

## Description
The file browser of the Console at Rest design offers Run and Version history for the open file, in the Files panel beside a chat and on a workspace page. The backend supports both only for a chat:

- `POST /api/tools/code-execution/run-file` (`backend/tools/router.py`, `api_run_file`) requires `chat_id` and resolves the path inside that chat's files; there is no workspace form.
- The version routes under `/api/file_systems/<id>/versions`, `/current-version`, `/diff` and `/restore` need a chat (the frontend already notes "every version endpoint needs a chat").

Found while building MYAI-93 (frontend only). Until this exists the frontend switches both buttons off on a workspace page and says why ("A file can be run from the Files panel of a chat", "Version history is kept for files in a chat").

Needed: accept `workspace_id` in place of `chat_id` on the run-file route (same ownership check as the workspace file routes, same runner limits), and make the version routes work for a file that belongs to a workspace.

## Acceptance criteria
- [x] `run-file` runs a workspace file given `workspace_id` and `path`, with the workspace ownership check
- [x] Version list, current version, diff and restore work for a workspace file
- [x] Tests cover both scopes, a workspace the caller does not own, and a missing file
- [x] `docs/standards/api.md` documents the changed routes
- [x] Frontend follow-up noted: switch Run and Version history on for the workspace scope (`features/artifacts/FileBrowser.tsx`)

## Plan
**Date:** 2026-11-11  **Status:** Validated

### Objective
Let a workspace file be run and have its version history read, compared and restored without a chat, so the Files panel on a workspace page can offer Run and Version history as it does beside a chat.

### Context
- Requirement: ticket Description and Acceptance criteria. Planned against `develop` at 7dd16d3.
- Rules: `AGENTS.md`; `docs/standards/api.md` (thin routes, `400` invalid, `404` foreign scope, no `str(e)`, contract changes update `frontend/src/api/` in the same change); `docs/standards/testing.md`; `docs/standards/security.md` (ownership on every route).
- Current behaviour:
  - Run: `backend/tools/router.py` `api_run_file` requires `chat_id`, checks `require_chat_owner`, calls `resolve_run_target(chat_id, path)` then `run_file(..., chat_id=...)`. In `backend/tools/implementations/code_executor.py`: `resolve_run_target` resolves via `resolve_owner_and_physical_path(chat_id, path)`; `run_file` returns "Error: Missing chat context." without a chat; `_call_runner` keys the run slot on `db.get_chat_owner(chat_id)`; dangerous code asks through `request_clarification(chat_id=...)`; the run record is saved only `if chat_id` (`code_execution_history.chat_id` is NOT NULL with a chat foreign key).
  - `backend/file_system/utils.py` `resolve_owner_and_physical_path(chat_id, path, workspace_id=...)` already routes to the workspace when `chat_id` is None and `workspace_id` is given.
  - Versions in `backend/file_system/router.py`: `GET /<id>/versions`, `GET /<id>/versions/<n>`, `POST /<id>/versions/<n>/restore`, `POST /<id>/diff`, `GET /<id>/current-version` each return 400 without `chat_id`, even with `workspace_id`. `GET /<id>/versions/<n>` also ignores `workspace_id` and has no `_fs_meta_or_404`. The blueprint hook `require_fs_owner` already checks any `workspace_id` given.
  - Manager (`backend/file_system/manager.py`): `get_file_system_versions`, `get_fs_file_version`, `get_fs_file_diff` accept `workspace_id` and work with `chat_id=None`. `restore_fs_file_version` syncs the disk file with `resolve_owner_and_physical_path(chat_id, safe_path)` without `workspace_id`, so with no chat it resolves the wrong place.
  - `db.get_workspace_owner(workspace_id)` exists (`backend/database/wrapper/chat_ops.py`).
  - Frontend: `frontend/src/api/filesystem.ts` already sends `workspace_id` on the version calls; `runFile(chatId, path)` sends only `chat_id`. `features/artifacts/FileBrowser.tsx` switches Run and Version history off without a chat.

### Approach
- Scope rule for the five version routes and run-file: `chat_id` or `workspace_id` is required; neither is 400. When both are given, behaviour is as today. Ownership: the blueprint hook for file-system routes; `require_chat_owner` or `require_workspace_owner` on the run route.
- Version routes accept `workspace_id` in place of `chat_id` and pass it through; `GET /<id>/versions/<n>` gains `_fs_meta_or_404` and passes `workspace_id`. `restore_fs_file_version` passes `workspace_id` to its disk-sync path resolution.
- Run route accepts `workspace_id` in place of `chat_id`. `resolve_run_target` and `run_file` take an optional `workspace_id`; a new helper `_run_owner(chat_id, workspace_id)` in `code_executor.py` returns the chat owner or `db.get_workspace_owner(workspace_id)` for `_call_runner`'s slot key. The run record stays chat-only (no schema change).
- Dangerous code in a workspace run (no chat to ask in): refused with "This file needs your confirmation before it runs. Run it from a chat to confirm." (assumption: safest; there is no clarification channel without a chat).
- Frontend contract: `artifactsApi.runFile` takes a `ScopeRef` instead of a chat id and sends `chat_id` or `workspace_id`; its caller passes its scope, keeping chat behaviour. Switching the buttons on for workspaces stays a follow-up, as the ticket says.
- Rejected: a hidden chat per workspace for runs (extra rows, leaks into the chat list); a workspace run-history table (schema change, not asked).

### Out of scope
- Switching Run and Version history on in `features/artifacts/FileBrowser.tsx` for the workspace scope (frontend follow-up, recorded in Implementation notes).
- `navigate-version`, `delete-future-versions`, exports, folder and tag routes, which also require `chat_id`.
- Run history for workspace runs.

### Steps
#### Step 1: Version routes accept a workspace
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/file_system/router.py` (modify): `get_file_system_versions_endpoint`, `get_fs_file_version_endpoint`, `restore_fs_file_version_endpoint`, `get_fs_file_diff_endpoint`, `get_file_system_current_version_endpoint`.
- **Change:** require `chat_id` or `workspace_id` (400 `"chat_id or workspace_id is required"` when neither); `workspace_id` is read from the query string, and on restore and diff also from the JSON body (as `chat_id` is), since the hook already checks both; `workspace_id="default"` without a chat stays the hook's 404, unchanged; `get_fs_file_version_endpoint` adds `_fs_meta_or_404` and passes `workspace_id`.
- **Verification:** new tests in `backend/file_system/tests/test_router.py`: each route with only `workspace_id` answers 200 with the right data for a workspace file (restore's disk write is checked in Step 2); neither id is 400; another user's workspace is 404 (added to the foreign-user parametrised table); a missing file is 404.

#### Step 2: Restore syncs the workspace file on disk
- **Status:** todo
- **Depends on:** 1
- **Files:** `backend/file_system/manager.py` (modify): `restore_fs_file_version`.
- **Change:** resolve the disk path with `resolve_owner_and_physical_path(actual_chat_id, safe_path, workspace_id=actual_workspace_id)` so a workspace file is written in the workspace directory.
- **Verification:** new test in `backend/file_system/tests/test_manager.py`: restoring a workspace file with `chat_id=None` rewrites the file under the workspace directory and moves the current version.

#### Step 3: Runner accepts a workspace
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/tools/implementations/code_executor.py` (modify): `resolve_run_target`, `run_file`, `_call_runner`, new `_run_owner`.
- **Change:** optional `workspace_id` threaded through; "Missing chat context" only when both are missing; slot owner from `_run_owner`; dangerous code without a chat returns the refusal message; record saved only with a chat. `collect_project_files` keeps its chat signature.
- **Verification:** new tests in `backend/tools/tests/test_code_executor.py`: `_run_owner` for a chat, a workspace and neither; a workspace run resolves inside the workspace directory and takes the slot as the workspace owner; no record written; dangerous code in a workspace is refused without calling the runner; chat runs unchanged.

#### Step 4: Run route accepts a workspace
- **Status:** todo
- **Depends on:** 3
- **Files:** `backend/tools/router.py` (modify): `api_run_file`.
- **Change:** accept a string `workspace_id` when `chat_id` is absent; 400 `"Missing path, chat_id or workspace_id"` when `path` or both ids are missing (update the exact-message assertion in `backend/tools/tests/test_router.py`), 400 when an id is not a string or `workspace_id` is `"default"` (which means "no workspace" in `utils.py`); `require_workspace_owner` (add it to the `backend.auth.ownership` import) for a workspace; pass it to `resolve_run_target` and `run_file`; logs carry the scope id.
- **Verification:** new tests in `backend/tools/tests/test_router.py`: workspace run succeeds, foreign workspace is 404 and nothing runs, missing workspace file is 404, neither id is 400; existing chat tests pass.

#### Step 5: Frontend client
- **Status:** todo
- **Depends on:** 4
- **Files:** `frontend/src/api/filesystem.ts` (modify): `codeExecApi.runFile(scope, path)`; `frontend/src/api/filesystem.test.ts` (modify); `frontend/src/features/artifacts/FileBrowser.tsx` (modify): `runFile` passes `scope` instead of `scope.chatId`, keeping its `if (!scope.chatId) return;` guard (removing it is the follow-up); `frontend/src/features/artifacts/ArtifactPanel.test.tsx` (modify): the `toHaveBeenCalledWith('c', 'app.py')` assertion becomes `toHaveBeenCalledWith({ chatId: 'c' }, 'app.py')`; in `filesystem.test.ts` the existing `runFile('c1', 'src/app.py')` call becomes `runFile({ chatId: 'c1' }, 'src/app.py')` with the same body assertion.
- **Change:** send `chat_id` or `workspace_id` from the scope; chat behaviour unchanged.
- **Verification:** `npm run typecheck`, `npm run lint`, `npm run test` pass; new client test for the workspace body.

#### Step 6: Docs and follow-up note
- **Status:** todo
- **Depends on:** 4
- **Files:** `docs/standards/api.md` (modify), `backend/file_system/README.md` (modify), `backend/tools/README.md` (modify).
- **Change:** document that the version routes and run-file accept a workspace in place of a chat, the dangerous-code rule for workspace runs, and that workspace runs keep no history; record the frontend follow-up (switch on Run and Version history for workspaces in `FileBrowser.tsx`) in Implementation notes.
- **Verification:** `venv/bin/python -m pytest tests -q -p no:cacheprovider` passes.

### Tests
- Backend: `EMBEDDING_URL="http://mock" AI_URL="http://mock" AI_API_KEY="dummy" PYTHONPATH=. venv/bin/python -m pytest backend/file_system/tests`, `backend/tools/tests`, then `backend` and `tests`; `venv/bin/ruff check .`.
- Frontend: in `frontend/`, `npm run typecheck`, `npm run lint`, `npm run test`.
- Gate: `scripts/check.sh`.

### Risks and open questions
- Decision: dangerous code is refused in a workspace run rather than run unconfirmed (assumption).
- Workspace runs leave no run history; the run history list is chat-only today, so nothing visible is lost.

### Success criteria
- [ ] `run-file` runs a workspace file given `workspace_id` and `path`, with the workspace ownership check
- [ ] Version list, single version, current version, diff and restore work for a workspace file with only `workspace_id`
- [ ] Tests cover both scopes, a workspace the caller does not own, and a missing file
- [ ] `docs/standards/api.md` documents the changed routes
- [ ] Frontend follow-up recorded; `frontend/src/api/filesystem.ts` `runFile` takes a scope

### Reviewer brief
- Objective: a workspace file can be run (`POST /api/tools/code-execution/run-file` with `workspace_id`) and its versions listed, read, compared, restored and its current version read with only `workspace_id`.
- Decisions: `chat_id` or `workspace_id` required on the five version routes and run-file; ownership via the file-system blueprint hook and `require_workspace_owner` on run-file; restore writes the workspace file on disk; the runner's slot is keyed on the workspace owner (`_run_owner`); workspace runs keep no run history (no schema change); dangerous code in a workspace run is refused with a plain message; `codeExecApi.runFile` takes a scope.
- Out of scope: switching Run and Version history on in `FileBrowser.tsx` for workspaces (follow-up), `navigate-version`, `delete-future-versions`, exports, folder and tag routes, workspace run history.
- Success: both scopes, a foreign workspace and a missing file tested; api.md and the READMEs document the changes.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- Round 1: validator FAIL. Judged FAIL. Valid BLOCKING: `ArtifactPanel.test.tsx` asserts `runFile('c', 'app.py')` and would fail (fixed: Step 5). Valid MINOR, fixed: exact symbol `codeExecApi.runFile` and the caller's chat guard kept; `require_workspace_owner` import; direct `_run_owner` test; Step 1 restore check limited to the route (disk write in Step 2); `"default"` rejected on run-file; where restore/diff read `workspace_id`. Rejected: step-level suite list (the Tests section already lists every suite; README updates in Step 6 land in the same change).
- Round 2 (diff-scoped): validator PASS. Judged PASS. Valid MINOR, fixed inline: existing `filesystem.test.ts` runFile call updated; exact expected values; run-file missing-id message and its test named; `"default"` rule stated for the version routes.

## Implementation notes
### Autopilot run (2026-11-11)
- Mode: automatic (batch-autopilot, item 2/9)
- Branch: bugfix/workspace-run-and-versions  PR base: develop  Starting commit: 32d33f73cd578e1a29080f9a12092caf1c36c073
- Dirty before start: none
- Work files: none yet
- Counters: fix 0/10, review 1/5, re-verify 1
- Last completed stage: 6 ship  Next: none
- Hard blocker: none
- WIP commit: none

### Autopilot decisions (2026-11-11)
- Stage 1: plan already Validated in ticket; reused.
### Baseline (2026-11-11)
- backend/file_system/tests + backend/tools/tests: 473 passed before changes.

### Implementation progress
- [x] Step 1: version routes accept workspace_id - backend/file_system/router.py
- [x] Step 2: restore syncs the workspace file on disk - manager.py
- [x] Step 3: runner accepts a workspace (`_run_owner`, workspace_id threaded, dangerous code refused) - code_executor.py
- [x] Step 4: run-file route accepts workspace_id - backend/tools/router.py
- [x] Step 5: frontend `codeExecApi.runFile(scope, path)` + tests - filesystem.ts, FileBrowser.tsx, tests
- [x] Step 6: docs (api.md, file_system and tools READMEs). Branch bugfix/workspace-run-and-versions.
- Frontend follow-up (not done, out of scope): switch Run and Version history on for the workspace scope in `features/artifacts/FileBrowser.tsx` (remove the `if (!scope.chatId) return;` guard and the disabled buttons' text).

### Smoke test (2026-11-11)
- backend + tests 1683 pass; frontend typecheck, lint, 1106 unit tests pass; ruff clean.
- Stage 5: resolve-review done inline by the author (not via the skill). R1-3 (restore swallows disk-write failure) is pre-existing: follow-up.
PR: https://github.com/archit342000/My-AI/pull/125, branch bugfix/workspace-run-and-versions, base develop

## Verification
### Verification plan (2026-11-11)
**Diff base:** develop tip. Full form (touches auth/ownership and the runner path).

**Environment:** real Flask app on 127.0.0.1:5312, throwaway `DATA_DIR`/`CHROMA_PATH` (mktemp), `AUTH_PROVIDER=static`; phase 1 runs as another user to seed a foreign workspace, phase 2 as the verifying user. `CODE_RUNNER_URL` points at a fake runner (`scripts/fake_runner.py`, port 5313) that records each /execute request and returns canned output (the real runner needs its own image). Never touches backend/data or containers. Teardown: kill recorded PIDs, rm temp dir, check port and processes.

| ID | Criterion | Scenario | Type | Files | Expected |
|----|-----------|----------|------|-------|----------|
| W1 | versions for a workspace file | create ws file, update twice, GET versions with only workspace_id | happy | file_system/router.py | 200, 3 versions |
| W2 | single version | GET versions/1 with only workspace_id | happy | router.py | 200, original content |
| W3 | current version | GET current-version | happy | router.py | 200, number 3 |
| W4 | diff | POST diff v1,v3 (workspace_id in body) | happy | router.py | added/removed lines |
| W5 | restore | POST restore v1 (workspace_id in body); then GET file and read the file on disk in the workspace dir | happy | router.py, manager.py | 200; content is v1 in the API and on disk |
| W6 | foreign workspace | all 5 version routes with another user's workspace | failure | router.py | 404, no content leaked |
| W7 | no scope | all 5 routes with neither id | failure | router.py | 400 |
| W8 | missing file | unknown file id in a workspace, versions, versions/1, current-version, diff | failure | router.py | 404 |
| W9 | chat regression | create chat file, update, versions/current/diff with chat_id | regression | router.py | unchanged 200s |
| R1 | run workspace file | run-file {path, workspace_id} for a.py (with a sibling module) | happy | tools/router.py, code_executor.py | 200; fake runner got entry_file a.py with the project files; result has the canned output |
| R2 | foreign workspace | run-file with another user's workspace | failure | tools/router.py | 404, runner not called |
| R3 | missing file | run-file for a path that is not there | failure | tools/router.py | 404 |
| R4 | bad scope | no ids, workspace_id default, workspace_id as a number, no path | failure | tools/router.py | 400 each |
| R5 | dangerous code | workspace file with os.system("rm -rf /") | failure | code_executor.py | 200 with the plain refusal text; runner not called |
| R6 | chat regression | run-file with chat_id | regression | tools/router.py | 200, runner called |
| R7 | logs | server log after the run | non-functional | | no traceback |

Scripts: `scripts/start_backend.sh`, `scripts/fake_runner.py`, `scripts/verify95.py`, `scripts/run_all.sh`.
### Results (2026-11-11)
Verified at HEAD 32d33f7 plus uncommitted:
- backend/file_system/README.md 9406df54c7dc65e1bc73ae66aab37dbb3bd4d3a6
- backend/file_system/manager.py cbbc575a012c78a3b7c94b959ec123262384c7fc
- backend/file_system/router.py 647e8d9dea45d2434cc1f21588a6fc4d92346ceb
- backend/file_system/tests/test_manager.py 58c6e2f9f8b7392bca924f2c304ee5c4f29bbb08
- backend/file_system/tests/test_router.py fa9f07e0eb793ca857aebaf82fff5e2edc599bd5
- backend/tools/README.md 7c7231b5e415b693ae2e0088b3c019bb2746a89a
- backend/tools/implementations/code_executor.py 756f70b5f02864ea3130372e7421368aaeba7997
- backend/tools/router.py 37cac3624ce0139946a242455ebe41b77cc5f583
- backend/tools/tests/test_code_executor.py b541e6085999cb4b54afaca53862d944f807e63e
- backend/tools/tests/test_router.py 4ffa10c00e3631684d89648b136145a721779be0
- docs/standards/api.md e314288e38c0266e8ed8948cc93a1611086df446
- frontend/src/api/filesystem.test.ts de6c063eacfc0700a6f09f3483770c4298104d8c
- frontend/src/api/filesystem.ts 9a4305ed61bac0fea40aad4125f768ccc054f8ff
- frontend/src/features/artifacts/ArtifactPanel.test.tsx 12620c1829b885d3f670765ba1272b54cdb6ec38
- frontend/src/features/artifacts/FileBrowser.tsx 7f5255f2ba653454059a7991d35591d6c82a3359

Evidence: `~/.claude/tickets/My-AI/MYAI-95-evidence/` (results.txt, backend logs, scripts/). Real app, throwaway data dir, fake runner on its own port; torn down (no process, port or dir left).

| ID | Status |
|----|--------|
| W1-W5 | PASS (versions, single version, current version, diff, restore incl. the file on disk in the workspace dir) |
| W6, W7, W8 | PASS (foreign workspace 404 with no leak, no scope 400, missing file 404, on the version routes) |
| W9 | PASS (chat versions unchanged) |
| R1 | PASS (workspace run reached the runner with the project files and returned its output) |
| R2-R5 | PASS (foreign 404 runner not called, missing 404, bad scope 400, dangerous code refused without running) |
| R6 | PASS (chat run unchanged) |
| R7 | PASS (no traceback in the server log) |
Regression: backend+tests 1683, frontend 1106 pass.
Verdict: verified (16 PASS, 0 FAIL, 0 BLOCKED). The real code runner was replaced by a fake that records requests (the real one needs its own image).

## Review history
### Round 1 - 2026-11-11
Verdict: Request changes (one MAJOR claimed, rejected; see below) -> after resolution Approve. One Haiku reviewer, working tree vs develop, requirement available. 10 findings.
- R1-1 [MAJOR] tests: no foreign-workspace or missing-file test for the version routes - Static - Rejected for the foreign part (the five routes are in the foreign-user table `test_user_b_gets_404_for_user_as_workspace` and `test_version_routes_for_a_missing_workspace_file_are_404` covers missing files); Fixed for the one real gap: a restore-of-a-missing-workspace-file test
- R1-2 [MINOR] router.py:1074 - body workspace_id 'default' passes unmapped - Static - Rejected: the blueprint hook already resolves 'default' (query and body) next to a chat and 404s it without one
- R1-3 [MINOR] manager.py:522 - restore swallows a failed disk write - Static - Pre-existing (the swallow is old code; not changed by this work)
- R1-4 [MINOR] code_executor.py:23 - refusal looks like a successful run - Static - Fixed (message starts with "Error:", so the panel shows it as failed; test and docs updated)
- R1-5 [MINOR] tools/README.md:9 - 'chat without an owner' - Static - Fixed
- R1-6 [MINOR] test_code_executor.py:560 - test name claims more than it asserts - Static - Fixed (split; added a chat dangerous-code test)
- R1-7 [MINOR] filesystem.test.ts:68 - no workspace-scope version client test - Static - Rejected: the version client code is unchanged and already sends workspace_id
- R1-8 [NIT] docs 'neither is a 400' wording - Static - Fixed
- R1-9 [NIT] _call_runner docstring - Static - Fixed
- R1-10 [NIT] single-version GET 404 body text now 'FileSystem not found' for a missing row - Static - Rejected: status unchanged, clients use the status
Resolved inline by the author. Re-verified after fixes: harness re-run, backend+file_system+tests 720 pass, ruff clean.

## Log
- 2026-11-11: created (backend gap found during MYAI-93)
- 2026-11-11: linked relates_to MYAI-96 (other backend gaps found with the design work)
- 2026-11-11: plan validated, 2 rounds
- 2026-11-11: linked conflicts_with MYAI-102 (both change workspace file paths)
- 2026-11-11: autopilot started (batch-autopilot)
- 2026-11-11: implemented, smoke tests pass
- 2026-11-11: verify: 16 PASS, 0 FAIL, fix 0/10
- 2026-11-11: review round 1 resolved (6 fixed, 4 rejected/pre-existing); re-verified
- 2026-11-11: batch-autopilot: shipped, base develop (https://github.com/archit342000/My-AI/pull/125)
