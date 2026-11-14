---
id: MYAI-8
title: "N9: empty chats listed in the sidebar"
status: done
created: 2026-11-08
updated: 2026-11-09
links:
  blocks: [MYAI-35]
  relates_to: [MYAI-25, MYAI-48]
---

## Description
Report N9 (Medium). Upload or artifact creation for an unsent chat creates a chat row, and get_all_chats lists every chat, so empty 'New Conversation' entries appear in the sidebar. Suggested fix: list only chats with at least one message or file; invalidate the chats cache on message and file inserts and deletes. Not blocked.

## Acceptance criteria
- [x] A chat with no messages or files is not listed
- [x] Chats with a message or file are listed
- [x] Sidebar updates after a message or file is added or removed

## Plan
**Date:** 2026-11-09  **Status:** Validated
**Base:** origin/develop @ 6a13e04 (read-only checkout used for planning).

### Objective
Stop chats that hold no content (no message, no uploaded file, no chat-scoped artifact) from appearing in the sidebar and workspace chat lists, while keeping every chat with content listed and keeping an open chat usable even if it is not listed. Make the sidebar refresh whenever a message or file is added or removed through the UI.

### Context
- **Requirement:** Description and Acceptance criteria of this ticket.
- **Assumptions (no user available):**
  - A1. "File" means either an uploaded file (`files` row with this `chat_id`) or a chat-scoped artifact (`file_systems` row with this `chat_id`). Both are user content; hiding a chat that holds one would make that content unreachable from the sidebar.
  - A2. Per AC 2, a chat whose only content is an uploaded file is listed. The ghost case the report describes is then closed by deleting the server file when its composer chip is removed (Step 5) and by hiding chats whose upload failed after `ensure_chat_exists` already ran (`backend/files/router.py:36` runs before the file is validated).
  - A3. Empty chat rows stay in the database. This ticket only filters the list; it does not delete or garbage-collect rows.
  - A4. The DB layer is SQLite only (`backend/database/db_layer.py`, `sqlite3`); there is no MySQL path to cover. The new SQL uses only plain `EXISTS` subqueries.
- **Rules that apply:** `AGENTS.md` (db via `db` mixins, tests for changed code then `scripts/check.sh`, `ruff check .`, keep component READMEs accurate); `docs/standards/testing.md` (1:1 test files, regression test per bug fix, temp DBs); `docs/standards/frontend.md` (typecheck, lint, test from `frontend/`; Testing Library tests for components with logic); `docs/data.md` (no raw SQL outside the wrapper; no schema change needed here).
- **Current behaviour:**
  - `ChatOpsMixin.get_all_chats` (`backend/database/wrapper/chat_ops.py`) selects every `chats` row joined to `workspaces`, unfiltered. `list_chats` in `backend/chat/router.py` (`GET /api/chats`) returns it as-is.
  - `get_all_chats` is also used by `FileSystemChannelManager.cleanup_stale_channels` (`backend/file_system/channel.py`), which must keep seeing every existing chat, including empty ones with a live channel, and by `clear_all_chats` in `backend/chat/router.py`.
  - `CachedDatabase.get_table` (`backend/database/cache_layer.py`) always runs the query and only fills the row cache, so the backend list is never served stale. The "invalidate the chats cache" part of the suggested fix applies to the frontend React Query cache (`queryKeys.chats` in `frontend/src/api/chats.ts`), not to the backend.
  - Chat rows with no content come from `ensure_chat_exists` (called by `/api/files/upload`, `PATCH /api/chats/<id>`, `/v1/chat/completions`, `FileSystemManager` artifact creation in `backend/file_system/manager.py`) and from `POST /api/chats/save`, which upserts the row directly with `save_chat`.
  - Frontend: `useChatList` (`frontend/src/features/chat/useChatQueries.ts`) feeds `SidebarChats` (`frontend/src/features/sidebar/RecentChats.tsx`) and `WorkspacePage`. Sends refresh the list in `consume` (`frontend/src/features/chat/send-turn.ts`). These do **not** refresh it: a finished upload in `Composer` (`frontend/src/features/composer/Composer.tsx`), the message delete helper `remove` in `frontend/src/features/chat/MessageList.tsx`, and the `create`/`remove` mutations in `frontend/src/features/artifacts/ArtifactPanel.tsx`. Removing a composer chip (`remove` in `Composer.tsx`) only drops it locally, so the uploaded file and its chat row stay on the server.
  - The open chat loads through `GET /api/chats/<id>` (`get_chat_history_full`, via `ChatHandler.get_history`), not through the list, so an unlisted chat still opens, renders and sends. `sendTurn` for an existing route chat needs only `queryKeys.chat(id)` data, which `ChatPage` already loads.

### Approach
Add a separate listing query, `ChatOpsMixin.get_listed_chats()`. It returns the same row shape as `get_all_chats`, filtered with `WHERE EXISTS (messages) OR EXISTS (files) OR EXISTS (file_systems)` on `chat_id`. Point only `GET /api/chats` at it. `get_all_chats` stays unchanged, so channel cleanup and other internal callers keep seeing every chat. On the frontend, refresh `queryKeys.chats` after every UI path that adds or removes a message, file or chat artifact, and delete the server file when an uploaded chip is removed before sending.

Alternatives rejected:
- Filtering inside `get_all_chats`: `cleanup_stale_channels` would drop live channels of empty or new chats.
- Deleting empty chat rows: destructive, and it races the new-chat flow (chat row created by PATCH before the first message lands).
- Filtering on the client: every consumer would need the content counts, and the API would still leak empty rows.

### Steps
#### Step 1: Listing query in the DB wrapper
- **Files:** `backend/database/wrapper/chat_ops.py` (modify): new method `ChatOpsMixin.get_listed_chats`.
- **Change:** Same SELECT, join, `ORDER BY c.timestamp DESC` and `cache_layer.get_table("chats", ...)` call as `get_all_chats`, plus `WHERE EXISTS (SELECT 1 FROM messages m WHERE m.chat_id = c.id) OR EXISTS (SELECT 1 FROM files f WHERE f.chat_id = c.id) OR EXISTS (SELECT 1 FROM file_systems fs WHERE fs.chat_id = c.id)`. Use a parameterless query and a docstring saying why `get_all_chats` stays unfiltered. Do not change `get_all_chats`.
- **Verification:** Step 3 tests.

#### Step 2: Use it for the chat list endpoint
- **Files:** `backend/chat/router.py` (modify): `list_chats`.
- **Change:** Call `db.get_listed_chats()` instead of `db.get_all_chats()`. Leave `clear_all_chats` and every other caller unchanged.
- **Verification:** Step 3 router test.

#### Step 3: Backend tests
- **Files:** `backend/database/wrapper/tests/test_chat_ops.py` (modify), `backend/chat/tests/test_router.py` (modify, `test_list_chats`).
- **Change:** In `test_chat_ops.py`, add a test class for `get_listed_chats` using the existing `temp_db` fixture:
  - an `ensure_chat_exists`-only chat is excluded but is still returned by `get_all_chats` and `get_chat`;
  - chats with a message (`add_message`), a file (`save_file`) or a chat-scoped artifact (`save_file_system_meta`) are included, with `workspace_name` populated;
  - a chat drops out after its last message is deleted (`delete_message` / `clear_messages`) or its only file is deleted (`delete_file`), and comes back after a new message;
  - ordering is by timestamp descending, using explicit `save_chat(chat_id, title, timestamp, enable_thinking=1)` timestamps (not wall-clock time).
  Add `get_listed_chats` to the module docstring's coverage list. Update `test_list_chats` to mock `get_listed_chats` and assert that the endpoint calls it.
- **Verification:** `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest backend/database/wrapper/tests/test_chat_ops.py backend/chat/tests/test_router.py backend/file_system/tests/test_channel.py`, then `pytest backend/database` and `pytest backend`. The exclusion test must fail if the `WHERE` clause is reverted, and `test_list_chats` must fail if Step 2 is reverted.

#### Step 4: Refresh the sidebar on message and artifact changes
- **Files:** `frontend/src/features/chat/MessageList.tsx` (modify): module function `remove`; `frontend/src/features/artifacts/ArtifactPanel.tsx` (modify): `create` and `remove` mutations.
- **Change:** After a successful message delete, also invalidate `queryKeys.chats`. In `ArtifactPanel`, also invalidate `queryKeys.chats` on create and delete success when `scope` is chat-scoped (`scope.chatId`). Workspace-scoped artifacts do not affect chat listing. Leave the `retry` path alone: it regenerates, and `consume` already refreshes the list.
- **Verification:** Step 6 tests.

#### Step 5: Composer uploads refresh the list; removed chips delete their server file
- **Files:** `frontend/src/api/files.ts` (modify): new export `deleteFile(fileId)` calling `DELETE /api/files/<id>` via `apiRequest` (add it to the existing `./client` import); `frontend/src/features/composer/Composer.tsx` (modify): upload queue effect `.then` and the `remove(key)` handler.
- **Change:** When an upload resolves, invalidate `queryKeys.chats` (the chat now has a file, AC 2 and AC 3). In `remove(key)`, if the chip has `uploaded`, call `deleteFile(uploaded.file_id)` and then invalidate `queryKeys.chats`; if the delete fails, the chip stays removed, a toast shows the error, and the list is still invalidated, so a leftover file keeps the chat listed (this is correct under AC 2). If a chip is removed while still uploading, record its key in a ref. When that upload resolves (`.then`), skip the state update, delete the file, and invalidate `queryKeys.chats` only after the delete settles. When it rejects (`.catch`), skip the toast and the state update. Chips that never reached the server need no call. Do not delete files on send (sent files are referenced by the message).
- **Verification:** Step 6 tests.

#### Step 6: Frontend tests
- **Files:** `frontend/src/features/chat/MessageList.test.tsx`, `frontend/src/features/artifacts/ArtifactPanel.test.tsx`, `frontend/src/features/composer/Composer.test.tsx` (modify); `frontend/src/api/files.test.ts` (create; direct test that `deleteFile` sends `DELETE /api/files/<encoded id>` and throws `ApiError` on a non-2xx response).
- **Change:** Assert that `queryKeys.chats` is invalidated after a message delete, after a chat-scoped artifact create/delete (and not for workspace scope), and after an upload completes. Assert that removing an uploaded chip calls `DELETE /api/files/<id>` and invalidates the list, that removing a queued (not uploaded) chip makes no call, and that removing a chip mid-upload deletes the file once the upload resolves, and shows no toast if that upload fails. Follow each file's existing fetch/XHR mocking pattern.
- **Verification:** from `frontend/`: `npm run typecheck`, `npm run lint`, `npm run test`.

#### Step 7: Docs and full checks
- **Files:** `backend/database/wrapper/README.md` (modify): `chat_ops.py` row, plus the tests note that names `test_chat_ops.py` coverage. Read `backend/chat/README.md` and `frontend/README.md` and update them only if they describe the chat list or the composer upload/remove behaviour (planning found no such text).
- **Change:** Note that `get_listed_chats` (sidebar list: chats with a message, file or chat artifact) and `get_all_chats` (every chat, for internal callers) both exist. No API doc change: the `GET /api/chats` response shape is unchanged; only its membership is.
- **Verification:** `venv/bin/ruff check .` (or `venv/bin/python -m ruff check .`) and `scripts/check.sh` both pass.

### Tests
- Backend: the new `get_listed_chats` tests and the updated `test_list_chats` (Step 3). Run the touched test files, then `backend/database`, `backend`, `tests`, each in its own pytest process per `docs/standards/testing.md`.
- Frontend: Step 6 additions to the existing Vitest/Testing Library files, then `npm run typecheck && npm run lint && npm run test` in `frontend/`.
- Final: `scripts/check.sh`.
- Live check for the verify stage: open a new chat, upload a file and then remove the chip (chat not listed); upload and keep it (chat listed); send a message (listed); delete the only message (chat leaves the sidebar, and the open chat still renders and can send); make an upload fail after `ensure_chat_exists` (not listed).

### Risks and open questions
- **Open chat not in sidebar:** after deleting its last message, the open chat disappears from the sidebar while it stays open. It remains usable (loaded by id), and sending brings it back. Accepted as the intended result of AC 1.
- **Query cost:** `files` has no `chat_id` index (only `idx_messages_chat_id` and `idx_file_systems_chat_id` exist in `backend/database/init_db.py`). A correlated `EXISTS` on `files` scans it per chat. This is fine for a single-user app's volumes. Adding `idx_files_chat_id` is a migration, deferred as a follow-up rather than added here.
- **Existing ghost rows:** rows already created stay in the DB and are only hidden (A3). Cleanup would be a separate ticket.
- **E2E:** no new user flow is added (existing sidebar, composer and message flows change behaviour only), so the `docs/standards/frontend.md` rule "New user flows get a Playwright spec" does not apply. This is a reasoned non-application, recorded here for review. The verify stage covers these flows live. The existing specs in `frontend/e2e/` do not depend on sidebar membership.
- **Temporary chats:** unaffected. They have no row until their first turn, and `discardTemporaryChat` deletes the row.
- **Open question (non-blocking):** should an unsent chat whose only content is an uploaded file stay listed? The plan follows AC 2 (listed). If the owner wants such chats hidden until the first message, change the Step 1 predicate to messages-plus-artifacts only, and keep Step 5.

### Validation log
- **Round 1:** validator FAIL (1 BLOCKING, 9 MINOR). My judgement: pass on BLOCKING.
  - BLOCKING "a Playwright spec is required for new user flows" (`docs/standards/frontend.md:52`): disproved. No new flow is added; existing flows change behaviour only. Recorded as a reasoned non-application in Risks.
  - Valid MINOR, fixed:
    - Step 3 verification wording (a Step 2 revert is caught by `test_list_chats`).
    - Step 5 `deleteFile` failure path.
    - Step 5 mid-upload handling in `.catch` too.
    - Direct test for `deleteFile` (new `frontend/src/api/files.test.ts`).
    - Test docstring coverage list moved into Step 3.
    - README check for `backend/chat/README.md` and `frontend/README.md` (no matching text found).
    - `POST /api/chats/save` wording (`save_chat` upsert).
    - Deterministic timestamps in tests.
  - MINOR "upload-only unsent chat stays listed": already an open question; it follows AC 2.
- **Round 2:** validator PASS (0 BLOCKING, 4 MINOR), confirmed. All 4 were valid and fixed:
  - E2E bullet worded as a recorded exception.
  - Invalidate the list only after the mid-upload delete settles.
  - `save_chat(..., enable_thinking=1)` shown in Step 3.
  - `apiRequest` added to the `./client` import.
- **Round 3:** validator PASS, no issues. Confirmed by my own checks: `save_chat` signature, `files.ts` import, Composer upload effect structure. Stopped after round 3 with no open BLOCKING or MINOR items.

## Implementation notes
### Autopilot run (2026-11-09)
- Mode: automatic (batch-autopilot batch 4, item 1/4)
- Branch: bugfix/hide-empty-chats  PR base: develop  Starting commit: 77fa8f2
- Dirty before start: none
- Work files: backend/database/wrapper/chat_ops.py, backend/database/wrapper/tests/test_chat_ops.py, backend/database/wrapper/README.md, backend/chat/router.py, backend/chat/tests/test_router.py, frontend/src/api/files.ts, frontend/src/api/files.test.ts, frontend/src/features/chat/MessageList.tsx (+test), frontend/src/features/artifacts/ArtifactPanel.tsx (+test), frontend/src/features/composer/Composer.tsx (+test), frontend/src/test/invalidation.ts
- Counters: fix 0/10, review 0/5, re-verify 0
- Last completed stage: 2 implement  Next: 3 verify
- Hard blocker: none
- WIP commit: none

### Autopilot decisions (2026-11-09)
- Stage 1: plan already Validated (3 rounds); reused, not re-planned.

Status on develop (checked at e327094, 2026-11-08): Still present on develop: get_all_chats (backend/database/wrapper/chat_ops.py:25) has no filter.
Decision (user, 2026-11-09): chats whose only content is an uploaded file stay listed (AC 2 as written). This matches the plan, so no change is needed.

### Baseline (2026-11-09)
At develop 77fa8f2: wrapper tests 73 pass; backend/chat/tests 148 pass; backend/file_system 116 pass; frontend vitest 295 pass (48 files); the other backend suites fail only on async tests (pytest-asyncio not installed in the venv).

### Implementation progress
- [x] Step 1: `ChatOpsMixin.get_listed_chats` - backend/database/wrapper/chat_ops.py (`EXISTS` on messages / files / file_systems; `get_all_chats` unchanged)
- [x] Step 2: `list_chats` uses it - backend/chat/router.py
- [x] Step 3: backend tests - backend/database/wrapper/tests/test_chat_ops.py (`TestGetListedChats`, written first and failing before the implementation), backend/chat/tests/test_router.py
- [x] Step 4: sidebar refresh on message delete and chat-scoped artifact create/delete - frontend MessageList.tsx, ArtifactPanel.tsx
- [x] Step 5: composer upload refreshes the list; removing an uploaded chip deletes the server file (also when removed mid-upload) - frontend/src/api/files.ts (`deleteFile`), Composer.tsx
- [x] Step 6: frontend tests - src/api/files.test.ts (new), MessageList.test.tsx, ArtifactPanel.test.tsx, Composer.test.tsx, shared helper src/test/invalidation.ts (new)
- [x] Step 7: docs - backend/database/wrapper/README.md; full checks (see Smoke test); live check is the verify stage
Branch: bugfix/hide-empty-chats

### Smoke test (2026-11-09)
wrapper 78 pass; chat 148; database/tests 61 + 2 baseline fails; file_system 116; backend/tests 25; tests 32; ruff clean; `scripts/check.sh --python-only`: only the baseline async-plugin failures; frontend vitest 305 pass (49 files), typecheck clean, lint only the existing forms.tsx warning, build ok.

PR: https://github.com/archit342000/My-AI/pull/63, branch bugfix/hide-empty-chats, base develop

## Verification
### Verification plan (2026-11-09, full form for the data path: new query behind `GET /api/chats` plus React refresh logic)
**Diff base:** origin/develop 77fa8f2. **Scope:** `ChatOpsMixin.get_listed_chats` behind `GET /api/chats` (chats with a message, uploaded file or chat artifact), sidebar refresh after message delete, chat artifact create/delete and composer upload, deleting the server file when an uploaded chip is removed. Out of scope: deleting empty chat rows, the `files.chat_id` index (MYAI-25).
**Environment and isolation:** this branch's app on 127.0.0.1:5099, built React frontend, `DATA_DIR=/tmp/myai8-data` (fresh DB), fake inference proxy on 5098 (fast mode). Never touch :5000/:5001, containers, `backend/data` or a real `chats.db`. Teardown: kill PIDs, delete the temp dir, compare ports/containers/git status to the snapshot.
Scripts: `scripts/fake_proxy.py`, `scripts/ui.js` (Playwright), `scripts/v8_api.py` (API + DB).

| ID | Criterion | Scenario | Type | Method | Files | Expected |
|----|-----------|----------|------|--------|-------|----------|
| V1 | Empty chat not listed; removed upload leaves nothing | UI: new chat, attach a file, wait until ready, remove the chip | happy/edge | browser + API | Composer.tsx, files.ts, chat_ops.py | after the remove: `GET /api/files/<id>` 404, the chat is absent from `GET /api/chats` and from the sidebar (no reload); the chat row still exists in the DB |
| V2 | A chat with a file is listed, sidebar updates | UI: new chat, attach a file and keep it | happy | browser + API | Composer.tsx | the chat appears in `GET /api/chats` and in the sidebar without a reload |
| V3 | A chat with a message is listed | UI: send a message in a new chat | happy | browser + API | chat_ops.py | listed with its title |
| V4 | List follows message deletes | UI: delete the only message of a chat without files | edge | browser + API | MessageList.tsx, chat_ops.py | the chat leaves the sidebar without a reload, the open chat still renders and can send, and a new send lists it again |
| V5 | Chat artifacts count as content | API: create an artifact for a new chat id, then delete it | edge | API | chat_ops.py | listed after create, not listed after delete |
| V6 | Failed upload leaves a hidden row | API: upload with no file part for a new chat id (the route creates the chat row before validating) | failure | API + DB | chat_ops.py | 400, the chat row exists in the DB, not in `GET /api/chats` |
| V7 | Ordering, workspace name, rows kept | API: list order, a chat inside a workspace, DB empties | regression | API + DB | chat_ops.py | newest first, `workspace_name` present, empty chats still in the DB (hidden, not deleted) |
| V8 | Regression | wrapper, chat, database, file_system, backend, tests dirs, ruff, vitest, typecheck, lint, build | regression | CLI | all | only baseline failures |

### Results (2026-11-09)
**Commit verified:** 77fa8f29fe3eacd791cc522a129b2e47a95ef991 (+ uncommitted files)
Hashes: router.py 77fdb036, test_router.py c32a7e61, wrapper/README.md 0a287fff, chat_ops.py 9d703d09, test_chat_ops.py e25e85ca, files.ts d90fe0e4, ArtifactPanel.test.tsx a8eb3602, ArtifactPanel.tsx bc943808, MessageList.test.tsx df4f7152, MessageList.tsx 709d2a0a, Composer.test.tsx 218b5113, Composer.tsx ea3d11e2, files.test.ts 6e8089b7, test/invalidation.ts a21a384c.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | v1-v4-ui.log: listed while attached, after chip removal file 404, chat not listed, DB row kept |
| V2 | PASS | v1-v4-ui.log: listed, sidebar entry appears without reload |
| V3 | PASS | v1-v4-ui.log: listed, title in sidebar |
| V4 | PASS | v1-v4-ui.log: leaves list and sidebar after delete, chat stays open, send brings it back (sidebar keeps the chat's title) |
| V5 | PASS | v5-v7-api.log: chat artifact lists the chat, delete unlists it |
| V6 | PASS | v5-v7-api.log: failed upload 400, DB row exists, not listed |
| V7 | PASS | v5-v7-api.log: newest first, workspace_name present, 8 rows in DB vs 5 listed |
| V8 | PASS (baseline) | vitest 305 pass (49 files); tsc clean; lint only the existing forms.tsx warning; build ok; ruff clean; backend/chat + backend/database 287 pass, 2 fail (test_cache_system subscribe_generator, async, pytest-asyncio missing = baseline); file_system + tests 141 pass |

Notes: first V4 attempt failed because the harness expected the title of the second message; the chat keeps its first title, so the expectation was wrong (logs `v1-v4-ui-attempt2-title-expectation.log`; script fixed, not the product). No console errors. Teardown: app and proxy killed, /tmp/myai8-data removed, the same 14 containers, ports 5098/5099 free, :5000/:5001 untouched.
**Verdict: verified (8/8 PASS, 0 FAIL, 0 BLOCKED).** Gap: the legacy static UI was not exercised.

## Review history
### Round 1 - 2026-11-09
Verdict: Request changes (1 MAJOR). Scope: origin/develop 77fa8f2..working tree, 12 files + 2 untracked, single Haiku reviewer.
- R1-1 [MAJOR] send-turn.ts:85 - chat list refreshed only when the stream ends, so a brand-new chat is missing from the sidebar during generation - Static - Fixed (invalidate chats on the first chunk; send-turn.test.ts new test, failed before the fix)
- R1-2 [MINOR] Composer.tsx:231 - chip never removed before unmount/navigation leaves the uploaded file and a listed chat - Static - Deferred (follow-up: delete unsent uploads on unmount; file-only chats stay listed by decision)
- R1-3 [MINOR] chat_ops.py:44 - no return annotation/Returns - Static - Fixed
- R1-4 [MINOR] Composer.test.tsx - no test that sending keeps the uploaded file - Static - Fixed (new test)
- R1-5 [MINOR] test_chat_ops.py:189 - isinstance hedge on create_workspace result - Static - Fixed
- R1-6 [MINOR] legacy UI not updated - Static - Rejected: response shape unchanged; legacy UI out of scope (noted in the PR)
- R1-7 [MINOR] no e2e spec - Static - Rejected: the repo has no e2e/ directory
- R1-8 [NIT] files.ts:48 docstring vague - Static - Fixed
Dismissed: the Retry half of R1-1 (Retry keeps the stored user message, so the chat stays listed).
Resolution: fixed 5, rejected 2, deferred 1. Checks: vitest 307 pass, tsc clean, lint only the existing forms.tsx warning, wrapper+chat pytest 226 pass, ruff clean. Runtime change: send-turn.ts; UI scenarios V1-V4 re-run on the rebuilt frontend, all PASS (v1-v4-ui-rerun.log). Fast fake proxy cannot show mid-stream state, so the first-chunk refresh is covered by the unit test only.

## Log
- 2026-11-08: created from reports/full-scope-final-report-2026-11-08.md
- 2026-11-09: plan validated, 3 rounds
- 2026-11-09: file-only chats stay listed (user decision).
- 2026-11-09: linked relates_to MYAI-25 (the index serves MYAI-8's sidebar EXISTS filter)
- 2026-11-09: linked blocks MYAI-35
- 2026-11-09: autopilot started (batch-autopilot)
- 2026-11-09: implemented, smoke tests pass (only baseline async-plugin failures)
- 2026-11-09: verified live, 8/8 PASS
- 2026-11-09: review round 1 Request changes (1 MAJOR, 6 MINOR, 1 NIT); resolved: fixed 5, rejected 2, deferred 1; V1-V4 re-run PASS
- 2026-11-09: shipped, PR https://github.com/archit342000/My-AI/pull/63
- 2026-11-09: batch-autopilot: shipped, base develop
- 2026-11-09: linked relates_to MYAI-48 (follow-ups from batch 4)
- 2026-11-09: closed, PR merged
