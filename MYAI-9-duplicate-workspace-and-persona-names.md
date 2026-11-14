---
id: MYAI-9
title: "N10: duplicate workspace and persona names"
status: done
created: 2026-11-08
updated: 2026-11-09
links:
  blocks: [MYAI-35, MYAI-36]
  conflicts_with: [MYAI-22]
---

## Description
Report N10 (Low to Medium). Workspaces and personas allow duplicate names; expand state is keyed by name. Skills already reject duplicates with 400 on develop. The frontend part (toasts) is in the merged UX PR; the backend 400 is missing. Suggested fix: 400 with a JSON error on duplicate names for workspace create (backend/chat/router.py) and persona create, using a name_exists method next to each create in the db wrapper. Not blocked.

## Acceptance criteria
- [x] Duplicate workspace name returns 400 with a JSON error
- [x] Duplicate persona name returns 400 with a JSON error
- [x] The frontend shows the message

## Plan
**Date:** 2026-11-09  **Status:** Validated

### Objective
Reject duplicate workspace and persona names in the backend with a `400` and a JSON error body, on both create and rename/update, so the frontend (which keys workspace expand state by name) never sees two entries with the same name. The frontend already surfaces the server's `error` string; this change only adds the missing backend check and the tests around it. Planned against origin/develop at 6a13e04.

### Context
- **Requirement:** ticket Description and Acceptance criteria (400 + JSON error for duplicate workspace and persona names; the frontend shows the message).
- **Assumptions and decisions (no user available):**
  1. **Rename/update paths are also checked.** Otherwise a rename gets around the create check and brings back the same name collision. The skills pattern does the same: `update_skill` returns the same 400 as `create_skill` (`backend/chat/router.py`).
  2. **Comparison is case-insensitive and ignores leading/trailing whitespace** (`LOWER(TRIM(name)) = LOWER(TRIM(?))`). "Work" and "work " look identical in the sidebar, so they should count as duplicates. Skills only compare case-sensitively because that is what their `UNIQUE` column does, not because anyone chose it. SQLite `LOWER` only folds ASCII; that is accepted (see Risks).
  3. **Renaming an item to its own name, or changing only its case, is allowed**: the check excludes the item's own id.
  4. **Application-level check, no `UNIQUE` constraint or migration.** Existing databases may already hold duplicates, and a constraint change means recreating the table (`docs/data.md` "Migrations", rule 3). Existing duplicates are left as they are. Stored names are not changed (no new trimming on write).
  5. **Error body shapes follow `docs/standards/api.md`:** workspace routes use the plain `{"error": "..."}`. Persona routes keep `{"success": false, "error": "..."}` for compatibility.
  6. **Messages:** `A workspace named '<name>' already exists` and `A persona named '<name>' already exists`, matching the existing frontend test fixture wording in `frontend/src/features/settings/PersonasDialog.test.tsx`.
- **Rules that apply:** `AGENTS.md` (use `db` from `backend.database`, with no raw SQL outside the wrapper; every source file has a matching test; run `scripts/check.sh` and `ruff check .`). `docs/standards/api.md` ("Validate before acting, and fail with `400` (not a partial write)"). `docs/standards/testing.md` (backend test command with mock env vars).
- **Current behaviour:**
  - `backend/chat/router.py`: `create_workspace` (POST `/api/chats/workspaces`) and `rename_workspace` (PATCH `/api/chats/workspaces/<id>`, which updates the icon before the name) call `db.create_workspace` and `db.rename_workspace` with no name check. `create_persona` and `update_persona` (POST `/api/personas`, PUT `/api/personas/<id>`) call `db.create_persona` and `db.update_persona` with no name check.
  - Skills pattern: the `skills.name TEXT UNIQUE` column (`backend/database/init_db.py`), plus `create_skill`/`update_skill`, which catch `sqlite3.IntegrityError` and return `{"success": False, "error": "A skill with the name '...' already exists"}, 400`.
  - Wrapper: `ChatOpsMixin.create_workspace` and `rename_workspace` in `backend/database/wrapper/chat_ops.py`. `PersonaOperations.create_persona` and `update_persona` in `backend/database/wrapper/persona_ops.py`. Both are mixed into one `db` class in `backend/database/db_wrapper.py`, so the new method names must be distinct.
  - Schema: `workspaces.name` and `personas.name` are plain `TEXT` with no constraint (`backend/database/init_db.py`).
  - Frontend: `apiRequest` in `frontend/src/api/client.ts` throws `ApiError` whose message is the body's `error` string. `Sidebar.tsx` `createWorkspace` and `RecentChats.tsx` `run()` (rename, and "Move to new workspace") show it with `showToast`. `PersonasDialog.tsx` shows it in a `role="alert"` block. Existing tests: `frontend/src/app/Sidebar.test.tsx` ("a rejected workspace create shows the server message"), `frontend/src/features/settings/PersonasDialog.test.tsx` (rejected create with "already exists"), and `frontend/src/api/client.test.ts` (server error message is carried).

### Approach
Add two read-only wrapper methods, `workspace_name_exists(name, exclude_id=None)` in `ChatOpsMixin` and `persona_name_exists(name, exclude_id=None)` in `PersonaOperations`. They query the database directly (not the workspace cache) with a case-insensitive, trimmed comparison. Call them in the four routes before any write, and return 400 with the route family's error shape. No frontend code change is needed, because the message path already exists and is tested. Acceptance criterion 3 is proven by those existing tests plus the later live verification.
Rejected alternatives: a `UNIQUE COLLATE NOCASE` constraint (needs a table-recreate migration and fails on databases that already hold duplicates); a single shared `name_exists(table, ...)` (passing the table name into SQL needs an allow-list, which is more surface for no benefit); frontend-only duplicate checks (the API would stay unprotected, and the ticket asks for the backend 400).

### Steps
#### Step 1: Workspace name lookup in the wrapper
- **Files:** `backend/database/wrapper/chat_ops.py` (modify; new method `ChatOpsMixin.workspace_name_exists`)
- **Change:** Add `workspace_name_exists(self, name: str, exclude_id: str | None = None) -> bool`. It runs `SELECT 1 FROM workspaces WHERE LOWER(TRIM(name)) = LOWER(TRIM(?)) [AND id != ?] LIMIT 1` using `make_connection()`, closes the connection in `finally`, and does not use the cache. Place it next to `create_workspace`. Add type hints and a docstring (summary, Args, Returns) per `docs/standards/python.md`.
- **Verification:** the Step 3 wrapper tests pass.

#### Step 2: Persona name lookup in the wrapper
- **Files:** `backend/database/wrapper/persona_ops.py` (modify; new method `PersonaOperations.persona_name_exists`)
- **Change:** Add `persona_name_exists(self, name: str, exclude_id: Optional[str] = None) -> bool`. It uses the same query against `personas` and the module's existing `with make_connection() as conn` style. Place it next to `create_persona`. Add type hints and a docstring (summary, Args, Returns) per `docs/standards/python.md`.
- **Verification:** the Step 3 wrapper tests pass.

#### Step 3: Wrapper tests
- **Files:** `backend/database/wrapper/tests/test_chat_ops.py` (modify; `TestWorkspaceOps`), `backend/database/wrapper/tests/test_persona_ops.py` (modify)
- **Change:** For each method, cover: an exact match is True; a different case or surrounding whitespace is True; an unrelated name is False; `exclude_id` set to the item's own id is False; `exclude_id` set to another item's id is still True when the name matches.
- **Verification:** `EMBEDDING_URL="http://mock" AI_URL="http://mock" AI_API_KEY="dummy" PYTHONPATH=. venv/bin/python -m pytest backend/database/wrapper/tests/test_chat_ops.py backend/database/wrapper/tests/test_persona_ops.py` passes.

#### Step 4: Workspace routes return 400 on duplicates
- **Files:** `backend/chat/router.py` (modify; `create_workspace`, `rename_workspace`)
- **Change:** In `create_workspace`, after the missing-name check, call `db.workspace_name_exists(name)`. If it is True, return `jsonify({"error": f"A workspace named '{name}' already exists"}), 400`. In `rename_workspace`, when `new_name` is given, run `db.workspace_name_exists(new_name, exclude_id=workspace_id)` **before** the icon update, so that a rejected request writes nothing. Return the same 400 if it is True.
- **Verification:** the Step 6 router tests pass.

#### Step 5: Persona routes return 400 on duplicates
- **Files:** `backend/chat/router.py` (modify; `create_persona`, `update_persona`)
- **Change:** After the required-fields check, call `db.persona_name_exists(name)` (create) or `db.persona_name_exists(name, exclude_id=persona_id)` (update). If it is True, return `jsonify({"success": False, "error": f"A persona named '{name}' already exists"}), 400` before calling `create_persona` or `update_persona`.
- **Verification:** the Step 6 router tests pass.

#### Step 6: Router tests
- **Files:** `backend/chat/tests/test_router.py` (modify; `test_create_workspace`, `test_rename_workspace`, `test_create_persona`, `test_update_persona`, plus new duplicate-case tests)
- **Change:** These tests patch `db` with a `MagicMock`, so an unset `*_name_exists` returns a truthy mock. Set `mock_db.workspace_name_exists.return_value = False` and `mock_db.persona_name_exists.return_value = False` in the existing success-path tests. Add tests that set them to True and assert:
  - a 400 response;
  - the JSON `error` contains "already exists" (persona tests also check `success is False`);
  - the matching write method is not called (`create_workspace`, `rename_workspace` and `update_workspace_icon` for a PATCH with both name and icon, `create_persona`, `update_persona`);
  - rename and update pass the right `exclude_id`.
- **Verification:** `EMBEDDING_URL="http://mock" AI_URL="http://mock" AI_API_KEY="dummy" PYTHONPATH=. venv/bin/python -m pytest backend/chat/tests/test_router.py` passes.

#### Step 7: Frontend confirmation (no code change)
- **Files:** none modified. Uses `frontend/src/app/Sidebar.test.tsx`, `frontend/src/features/settings/PersonasDialog.test.tsx` and `frontend/src/api/client.test.ts` as evidence.
- **Change:** None. Confirm the existing tests still pass, which shows a JSON `error` reaches a toast or the dialog alert. The live check of the real 400 being shown (workspace create, workspace rename, persona create and edit) belongs to the verify stage. The chain (`apiRequest` in `frontend/src/api/client.ts` -> `ApiError` -> `showToast` in `Sidebar.tsx`, the rename path in `RecentChats.tsx`, the persona dialog alert) is confirmed by code reading. Existing tests mock rejections with a generic `Error`, so they don't exercise the server's `error` body, and the rename path has no test; the real 400 display for all three flows is left to the verify stage.
- **Verification:** in `frontend/`, `npm run test` passes.

#### Step 8: Full gate
- **Files:** none.
- **Change:** Run `venv/bin/python -m ruff check .` and `scripts/check.sh`. No README or doc change is needed: `backend/database/wrapper/README.md` and `backend/chat/README.md` list files and mixins, not methods, and `docs/standards/api.md` already documents the 400 `{"error"}` contract. Also fix the stale mixin name in `backend/database/wrapper/README.md:20` (`PersonaOpsMixin` -> `PersonaOperations`, the class in `persona_ops.py:6`), since AGENTS.md rule 1 asks for touched components' READMEs to stay accurate. `scripts/check.sh` runs the parent test directories (`backend/`, `tests/`) required by AGENTS.md rule 2 and testing.md; don't stop after the per-file runs.
- **Verification:** both commands pass.

### Tests
- New: the wrapper lookup tests (Step 3) and the duplicate-case router tests (Step 6).
- Updated: the existing router success-path tests, so that the `*_name_exists` mocks return False.
- Commands: the per-file pytest commands in Steps 3 and 6 (mock env vars from `docs/standards/testing.md`), then `scripts/check.sh` (backend plus frontend) and `ruff check .`.

### Risks and open questions
- **Race (TOCTOU):** two simultaneous creates with the same name could both pass the check. This is a single-user app, so the risk is accepted; a `UNIQUE` index would be a separate migration ticket.
- **Existing duplicates** stay in place. Renaming one of them to its own current name passes (its own id is excluded), but renaming it to match the other one is rejected. No data clean-up is planned.
- **ASCII-only case folding** in SQLite `LOWER`: "Ä" and "ä" are not treated as duplicates. This is accepted as minor.
- **Out of scope, noted:** `rename_workspace` returns 200 for an unknown id; the persona routes do not trim names before storing; there is no `frontend/src/features/sidebar/RecentChats.test.tsx` for the rename toast path.
- No blocking open questions.

### Success criteria
- [ ] POST `/api/chats/workspaces` with an existing name (any case or surrounding whitespace) returns 400 `{"error": "A workspace named '...' already exists"}` and creates nothing.
- [ ] PATCH `/api/chats/workspaces/<id>` renaming to another workspace's name returns the same 400 and changes neither name nor icon; renaming to its own name succeeds.
- [ ] POST `/api/personas` and PUT `/api/personas/<id>` with another persona's name return 400 `{"success": false, "error": "A persona named '...' already exists"}` and write nothing; updating a persona while keeping its own name succeeds.
- [ ] The existing frontend tests showing the server `error` message pass.
- [ ] `ruff check .` and `scripts/check.sh` pass.

### Validation log
- **Round 1 (2026-11-09): not run.** Spawning the Haiku `Explore` validator failed with "Concurrent subagent limit reached ... Do not retry". No validation rounds took place. Before validating, the planner self-checked every path and symbol against /tmp/myai-develop at 6a13e04: router handlers, wrapper methods, `db_wrapper.py` composition, schemas, test files and classes, and frontend error paths and tests. This is not a substitute for validation: re-run `plan MYAI-9` once sub-agent capacity is free, before implementing.
- Round 1 (2026-11-09, Haiku, run from the main session): PASS, 0 BLOCKING and 5 MINOR. My judgement: PASS.
  - M1: `test_update_persona` doesn't exist. Disproved: it is at `backend/chat/tests/test_router.py:491`.
  - M2: docstrings and hints on the new methods. Valid. Added to Steps 1-2.
  - M3: frontend tests don't exercise the server body. Valid. Step 7 now says code reading, with the live display left to verify.
  - M4: README names `PersonaOpsMixin`. Valid (README:20 vs persona_ops.py:6). Fixed in Step 8.
  - M5: parent test directories. Valid. Step 8 notes `scripts/check.sh` covers them.
  The planner's own rounds were not run (subagent limit), so this round reviewed the whole plan rather than a diff. With no BLOCKING issues and all minors applied, I'm marking it Validated.

## Implementation notes

### Autopilot run (2026-11-09)
Batch 4 item. Branch bugfix/unique-names from origin/develop 77fa8f2, PR base develop. Dirty files before start: none. Plan was written against 6a13e04; develop moved but touched none of the planned files.

### Baseline (2026-11-09)
At develop 77fa8f2: wrapper + chat tests 221 pass; backend + tests dirs: only the async-plugin failures (pytest-asyncio not installed), 10 tests.

### Implementation progress
- [x] Steps 1-2: workspace_name_exists (chat_ops.py), persona_name_exists (persona_ops.py)
- [x] Step 3: wrapper tests (test_chat_ops.py, test_persona_ops.py)
- [x] Steps 4-5: four routes return 400 before any write (router.py)
- [x] Step 6: router tests (existing success paths set the mocks to False; 5 new tests)
- [x] Step 7: frontend tests unchanged and passing
- [x] Step 8: ruff clean; README mixin name fixed. scripts/check.sh not run as a whole (pytest-asyncio missing); parent dirs run directly.

### Smoke test (2026-11-09)
wrapper + chat pytest 228 pass; `pytest backend tests` 935 pass, 10 fail (all "async def functions are not natively supported", baseline); ruff clean; vitest Sidebar, PersonasDialog, client tests pass.
Status on develop (checked at e327094, 2026-11-08): Still present on develop for workspaces and personas; skills are already fixed.

PR: https://github.com/archit342000/My-AI/pull/64, branch bugfix/unique-names, base develop

## Verification
### Verification plan (2026-11-09, light form: four routes, no schema change)
**Diff base:** origin/develop 77fa8f2. **Scope:** `workspace_name_exists`, `persona_name_exists` and the 400 checks in the workspace create/rename and persona create/update routes. Out of scope: UNIQUE constraint, existing duplicates, trimming on write.
**Environment and isolation:** this branch's app on 127.0.0.1:5099, built React frontend, `DATA_DIR=/tmp/myai9-data` (fresh DB), fake proxy on 5098. Never touch :5000/:5001, containers, `backend/data` or a real `chats.db`. Teardown: kill recorded PIDs, remove /tmp/myai9-data, compare docker/ports/git snapshots (`/tmp/gen/*-before9.txt`).
Scripts (in `MYAI-9-evidence/scripts/`): `fake_proxy.py` (copy), `v9_api.py` (HTTP + DB), `ui.js` (Playwright).

| ID | Criterion | Scenario | Type | Method | Files | Expected |
|----|-----------|----------|------|--------|-------|----------|
| V1 | AC1 | POST workspace with a new name, then the same name, `work `/`WORK` variants, a different name | happy/edge | API + DB | router.py, chat_ops.py | 200 first; duplicates 400 `{"error": "A workspace named '...' already exists"}`; DB row count unchanged by rejected calls |
| V2 | AC1 | PATCH rename to another workspace's name (with and without icon), to its own name, to its own name in another case | edge | API + DB | router.py, chat_ops.py | other name: 400, name and icon unchanged; own name and case change: 200 |
| V3 | AC2 | POST/PUT persona with a taken name (case/space variants), own name on PUT, unknown id | happy/edge/failure | API + DB | router.py, persona_ops.py | 400 `{"success": false, "error": "A persona named '...' already exists"}`, nothing written; own name 200; unknown id with a free name still 404 |
| V4 | AC3 | UI: sidebar New Workspace with an existing name | happy | browser | (frontend unchanged) | toast shows the server message, no second workspace |
| V5 | AC3 | UI: rename a workspace to another's name | happy | browser | same | toast shows the message, name unchanged |
| V6 | AC3 | UI: persona dialog create with an existing name | happy | browser | same | the alert shows the message |
| V7 | regression | wrapper, chat, backend and tests dirs, ruff, vitest | regression | CLI | all | only baseline async failures |
Not run yet.

### Results (2026-11-09)
**Commit verified:** 77fa8f29fe3eacd791cc522a129b2e47a95ef991 (+ uncommitted files)
Hashes: router.py 12e2abab, test_router.py be63b9d4, wrapper/README.md 4f5c73d0, chat_ops.py 55ae58d0, persona_ops.py 536c7241, test_chat_ops.py a044fe16, test_persona_ops.py 6c30dbb9.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | v1-v3-api.log: Work/work/"  WORK  " rejected 400 with the message, rows unchanged, a new name 200 |
| V2 | PASS | v1-v3-api.log: rename to a taken name with an icon: 400 and name and icon unchanged; own name, own name in another case, icon only, free name: 200 |
| V3 | PASS | v1-v3-api.log: persona POST/PUT duplicates 400 `{"success": false, "error": ...}`, nothing written; own name 200; unknown id 404 |
| V4 | PASS | v4-v6-ui.log, ui-v4-dup-create.png: toast shows the server message, no second workspace |
| V5 | PASS | v4-v6-ui.log, ui-v5-dup-rename.png: toast shows the message, Beta unchanged |
| V6 | PASS | v4-v6-ui.log, ui-v6-dup-persona.png: dialog alert shows the message; V6b (edit renamed to a taken name) the same, ui-v6-dup-persona-edit.png |
| V7 | PASS (baseline) | wrapper+chat pytest 228 pass; backend+tests 935 pass, 10 fail (all async, pytest-asyncio missing, baseline); ruff clean; vitest 295 pass; tsc clean; lint only the existing forms.tsx warning |

Notes: console errors in the UI run are the expected 400 resource logs. Teardown: app and proxy killed, /tmp/myai9-data removed, ports and containers identical to the snapshot, :5000/:5001 untouched. `scripts/check.sh` was not run as a whole (pytest-asyncio missing); its parts ran directly.
**Verdict: verified (7/7 PASS plus V6b, 0 FAIL, 0 BLOCKED).** Gap: the legacy static UI was not exercised.

## Review history
### Round 1 - 2026-11-09
Verdict: Approve with comments. Scope: origin/develop 77fa8f2..working tree, 7 files, single Haiku reviewer.
- R1-1 [MINOR] persona_ops.py:59 - `with make_connection()` does not close the connection, unlike the workspace method - Static - Fixed (try/finally close)
- R1-2 [MINOR] router.py:702 - an unknown persona id with a taken name now gets 400 instead of 404 - Static - Rejected: the plan checks before the write; negligible reach
- R1-3 [NIT] test_router.py:88 - blank-line spacing - Static - Fixed
- R1-4 [NIT] annotation style differs between the two methods - Static - Fixed (both `str | None`)
- R1-5 [NIT] LOWER(TRIM()) cannot use an index - Static - Rejected: small tables, noted in the plan risks
Resolution: fixed 3, rejected 2. Checks: wrapper+chat pytest 228 pass, ruff clean. No runtime behaviour change beyond closing a connection (V3 covers the persona method).

## Log
- 2026-11-08: created from reports/full-scope-final-report-2026-11-08.md
- 2026-11-09: plan drafted, unresolved issues (Haiku validation blocked by sub-agent concurrency limit; 0 rounds)
- 2026-11-09: plan validated, 1 Haiku round (run from the main session).
- 2026-11-09: linked conflicts_with MYAI-22 (workspace and persona route body reads in backend/chat/router.py)
- 2026-11-09: linked blocks MYAI-35
- 2026-11-09: linked blocks MYAI-36
- 2026-11-09: autopilot started (batch-autopilot)
- 2026-11-09: implemented, smoke tests pass (only baseline async-plugin failures)
- 2026-11-09: verified live, 7/7 PASS (+V6b)
- 2026-11-09: review round 1 Approve with comments; fixed 3, rejected 2
- 2026-11-09: V1-V3 re-run after review fixes, PASS (v1-v3-api-rerun.log)
- 2026-11-09: shipped, PR https://github.com/archit342000/My-AI/pull/64
- 2026-11-09: batch-autopilot: shipped, base develop
- 2026-11-09: closed, PR merged
