---
id: MYAI-101
title: "Backend: keep abandoned temporary chats out of the list and remove them"
status: in-progress
created: 2026-11-11
updated: 2026-11-11
links:
  split_from: [MYAI-96]
---

## Description
Item 5 of MYAI-96. A temporary chat that is neither saved nor discarded (the tab closes or crashes before the discard call) stays on the server and later appears in the chat list as an ordinary chat. Seen in browser tests: two unsaved temporary chats were listed after their pages closed.

Needed: the server keeps a chat marked temporary out of the chat list and removes it after a set time unless it is saved.

## Acceptance criteria
- [x] A temporary chat never appears in the chat list unless saved
- [x] An unsaved temporary chat is removed after a set time (value in `backend/config.py`)
- [x] Saving a temporary chat still keeps it
- [x] Tests cover listing, expiry and saving
- [x] `docs/standards/api.md` documents the behaviour

## Plan
**Date:** 2026-11-11  **Status:** Validated

### Objective
Make the server know which chats are temporary, keep them out of the chat list until they are saved, and remove the ones nobody saved or discarded after a set time, so a closed or crashed tab no longer leaves a stray chat in the list.

### Context
- Requirement: ticket Description and Acceptance criteria. Planned against `develop` at 7dd16d3.
- Rules: `AGENTS.md` (config in `backend/config.py`, `db` only, `log_event`, routes thin); `docs/data.md` Migrations (column with a default, idempotent, test twice and on an older schema); `docs/standards/api.md` (additive request fields; contract changes update `frontend/src/api/` in the same change); `docs/standards/security.md` (owner checks); `docs/standards/testing.md`.
- Current behaviour:
  - The server has no notion of a temporary chat. The frontend (`frontend/src/features/chat/temporary-chat.ts`) makes a fresh id; the row is created by the first `POST /v1/chat/completions` (`backend/chat/router.py` `chat_completions` calls `claim_chat`, which calls `db.ensure_chat_exists`), or earlier by an upload or artifact (also through `claim_chat`). Discard is `DELETE /api/chats/<id>` (`remove_chat`, which stops the turn, removes files and RAG data, `task_manager.forget_chat`, `db.delete_chat`). Save is `PATCH /api/chats/<id>` with a title (`patch_chat_endpoint`). The sidebar hides the open temporary chat only in that tab (`features/sidebar/RecentChats.tsx`).
  - `GET /api/chats` (`list_chats`) returns `db.get_listed_chats(user_id)` (`backend/database/wrapper/chat_ops.py`): chats with content, newest first; workspace lists use the same rows.
  - `chats.timestamp` is updated at the end of every turn (`TurnHandler._persist_final_state`).
  - `frontend/src/api/completions.ts` `buildCompletionBody` builds the send body; `send-turn.ts` already knows `temporary`.

### Approach
- New column `chats.is_temporary INTEGER DEFAULT 0`.
- Marking: `POST /v1/chat/completions` accepts an optional boolean `temporary` (non-boolean is 400, checked with the other pre-claim checks, before `claim_chat` and any upload handling). When true and the chat has no stored messages yet (its first turn), the chat is set `is_temporary = 1` after `claim_chat`. Later sends never change the flag. `temporary` is removed from the `extra_body` passed on to the handler, as `chatId` is.
- Saving: `PATCH /api/chats/<id>` accepts `is_temporary: false` (only `false`; any other value is 400, checked before `claim_chat` so a refused request writes nothing) and clears the flag.
- Writes go through `update_chat`, with `is_temporary` added to its `allowed_fields` (unknown keys are dropped there today).
- Listing: `get_listed_chats` leaves out `is_temporary = 1`, so the chat list and workspace lists never show an unsaved temporary chat. `GET /api/chats/<id>` still serves it to its owner (the open tab needs it).
- Removal (chosen trigger: the owner's next chat-list request, since that is the only place a stray chat would be seen; no background timer exists): config `TEMPORARY_CHAT_TTL_SECONDS` (default 86400). A temporary chat whose `timestamp` is older than that is deleted, skipping (never stopping) any chat for which `task_manager.is_task_running(chat_id)` is true, with the same steps as `DELETE /api/chats/<id>`. The steps move from `remove_chat` into a new `delete_chat_fully(chat_id) -> bool` in a new `backend/chat/cleanup.py` (returns False when the turn did not stop in time), used by `remove_chat` unchanged in behaviour. The embedding model and RAG manager are set up lazily inside `delete_chat_fully` only when the chat has uploaded files, so a listing with nothing to purge, or a purge of chats without files, loads nothing extra. `purge_expired_temporary_chats(user_id)` in the same module runs at the start of `GET /api/chats` for the caller only, logs each removal with `log_event`, and never fails the listing (a failed delete is logged and retried next time).
- Frontend contract: `buildCompletionBody` sends `temporary: true` for a temporary chat; `saveTemporaryChat` sends `is_temporary: false` with the title. Without these the server behaves as today.
- Rejected: a background timer thread (no scheduler exists; the list call is when stray chats would show); deleting on tab close only (the crash case is the reason for this ticket).

### Out of scope
- Changing how the frontend discards a temporary chat (it keeps calling `DELETE`).
- Any sweep for other users than the caller.

### Steps
#### Step 1: Column and config
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/database/init_db.py` (modify): `chats` table and its column migration; `backend/config.py` (modify): `TEMPORARY_CHAT_TTL_SECONDS`; `backend/database/tests/test_init_db.py`, `backend/tests/test_config.py` (modify).
- **Change:** add `is_temporary INTEGER DEFAULT 0` for new and existing databases; read the TTL from env with the default.
- **Verification:** `init_db()` twice and on an older `chats` schema adds the column with `0` on existing rows; config test reads the default.

#### Step 2: Database helpers
- **Status:** todo
- **Depends on:** 1
- **Files:** `backend/database/wrapper/chat_ops.py` (modify): `get_listed_chats`, `update_chat` (`allowed_fields` gains `is_temporary`), new `get_expired_temporary_chats(user_id, before_ts)`; `backend/database/wrapper/tests/test_chat_ops.py` (modify).
- **Change:** filter temporary chats from the listing; allow `update_chat(chat_id, is_temporary=...)`; list a user's temporary chats older than a timestamp.
- **Verification:** tests: `update_chat` sets and clears the flag; a temporary chat with content is not listed and is listed again after the flag is cleared; expired-chat query returns only the caller's old temporary chats.

#### Step 3: Mark on first send and clear on save
- **Status:** todo
- **Depends on:** 2
- **Files:** `backend/chat/router.py` (modify): `chat_completions`, `patch_chat_endpoint`; `backend/chat/tests/test_router.py` (modify).
- **Change:** validate and apply `temporary` as in Approach and drop it from `extra_body`; accept `is_temporary: false` on PATCH, validated before `claim_chat`, 400 for any other value.
- **Verification:** tests: first send with `temporary: true` marks the chat and it is not listed; the handler does not receive a `temporary` keyword; a second send without it keeps the mark; a send with `temporary: "yes"` is 400 and writes nothing; PATCH `is_temporary: false` lists it; PATCH `is_temporary: true` on a new id is 400 and creates no chat row; another user's chat is 404 on both.

#### Step 4: Full delete helper and sweep
- **Status:** todo
- **Depends on:** 2
- **Files:** `backend/chat/cleanup.py` (create): `delete_chat_fully`, `purge_expired_temporary_chats`; `backend/chat/router.py` (modify): `remove_chat`, `list_chats`; `backend/chat/tests/test_cleanup.py` (create), `backend/chat/tests/test_router.py` (modify).
- **Change:** move `remove_chat`'s steps into `delete_chat_fully` (RAG setup only when the chat has files); `remove_chat` answers 409 when it returns False, as today; `list_chats` runs the sweep for the caller before listing.
- **Verification:** tests with a patched clock: an expired temporary chat is deleted (rows, files, task state) on the next listing; a fresh one, a saved one, a running one and another user's are kept; a failing delete is logged and the listing still answers 200; a listing with nothing to purge does not call `get_embedding_model`; existing `DELETE` tests pass unchanged.

#### Step 5: Frontend
- **Status:** todo
- **Depends on:** 3
- **Files:** `frontend/src/api/completions.ts` (modify): `CompletionOptions.temporary`, `buildCompletionBody`; `frontend/src/api/chats.ts` (modify): `ChatPatch.is_temporary?: false`; `frontend/src/features/chat/send-turn.ts` (modify): pass `temporary`; `frontend/src/features/chat/temporary-chat.ts` (modify): `saveTemporaryChat`; their tests (`completions.test.ts`, `send-turn.test.ts` if present, `temporary-chat.test.ts`) (modify).
- **Change:** send the flag on a temporary chat's sends and `is_temporary: false` on save.
- **Verification:** `npm run typecheck`, `npm run lint`, `npm run test` pass; tests assert the body field and the PATCH body.

#### Step 6: Docs
- **Status:** todo
- **Depends on:** 4, 5
- **Files:** `docs/standards/api.md` (modify: the flag, the save field, and the new 400 in the documented `POST /v1/chat/completions` check order); `docs/data.md` (modify): `chats.is_temporary`; `docs/frontend.md` (modify): replace the temporary-chat sentences in place, adding no net lines (the file is at 191 of 200); `backend/chat/README.md` (modify): `cleanup.py`; `backend/database/wrapper/README.md` (modify): the `get_listed_chats` rule.
- **Change:** document the flag, the save field, the listing rule and removal on the next listing after the TTL. Check that the legacy UI (`static/script.js`, `static/js/`) is unaffected by the added keys (it reads named fields only) and record the check in Implementation notes, as `docs/standards/api.md`'s breaking-change rule requires.
- **Verification:** `EMBEDDING_URL="http://mock" AI_URL="http://mock" AI_API_KEY="dummy" PYTHONPATH=. venv/bin/python -m pytest tests -q -p no:cacheprovider` passes; `docs/frontend.md` stays within the docs line limit.

### Tests
- Backend: `EMBEDDING_URL="http://mock" AI_URL="http://mock" AI_API_KEY="dummy" PYTHONPATH=. venv/bin/python -m pytest backend/database/tests`, `backend/chat/tests`, then `backend` and `tests`; `venv/bin/ruff check .`.
- Frontend: in `frontend/`, `npm run typecheck`, `npm run lint`, `npm run test`; `npm run e2e:stack` for `e2e/stack/temp-chat.spec.ts`.
- Gate: `scripts/check.sh`.

### Risks and open questions
- A temporary chat open in a tab for longer than the TTL with no new turn would be removed on the next listing; the default of one day makes that unlikely, and a send updates `timestamp`.
- Older temporary chats created before this change are not marked and stay listed (no way to tell them apart).

### Success criteria
- [ ] An unsaved temporary chat never appears in the chat or workspace lists
- [ ] An unsaved temporary chat older than `TEMPORARY_CHAT_TTL_SECONDS` is removed on its owner's next chat-list request
- [ ] Saving a temporary chat keeps it and lists it
- [ ] Tests cover listing, expiry and saving
- [ ] `docs/standards/api.md` documents the behaviour

### Reviewer brief
- Objective: the server knows which chats are temporary, keeps them out of the chat and workspace lists until saved, and removes unsaved ones older than `TEMPORARY_CHAT_TTL_SECONDS` on the owner's next chat-list request.
- Decisions: `chats.is_temporary` (default 0) set by `temporary: true` on a chat's first send and cleared by `PATCH ... {"is_temporary": false}` (both validated before `claim_chat`); `update_chat` allows the field; `get_listed_chats` filters it; `delete_chat_fully` and `purge_expired_temporary_chats` in a new `backend/chat/cleanup.py` (running chats skipped, RAG set up only for chats with files, failures logged without failing the listing); frontend sends the flag and the save field; older unmarked chats stay listed.
- Out of scope: how the frontend discards; sweeping other users' chats.
- Success: never listed unsaved, removed after the TTL on the next listing, saving keeps it, tests for listing/expiry/saving, api.md documents it.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- Round 1: validator FAIL. Judged FAIL. Valid BLOCKING, fixed: `update_chat` drops unknown keys (`allowed_fields` gains `is_temporary`); `ChatPatch` lacked the field (`chats.ts` added); chat-ops tests belong in `backend/database/wrapper/tests/test_chat_ops.py`; PATCH validation moved before `claim_chat`. Valid MINOR, fixed: `temporary` kept out of `extra_body`; wrapper README and api.md check order in docs; removal trigger stated as the next listing; `docs/frontend.md` edited without net lines; RAG setup only when needed.
- Round 2 (diff-scoped): validator PASS. Judged PASS. Valid MINOR, fixed inline: `temporary` checked with the pre-claim checks; running chats skipped with `task_manager.is_task_running`, never stopped.
- 2026-11-11 correction after validation: last step also checks the legacy UI against the added keys (`docs/standards/api.md`), found while validating MYAI-102.

## Implementation notes
### Autopilot run (2026-11-11)
- Mode: automatic (batch-autopilot, item 6/9)
- Branch: bugfix/abandoned-temporary-chats  PR base: develop  Starting commit: 32d33f73cd578e1a29080f9a12092caf1c36c073
- Dirty before start: none
- Work files: none yet
- Counters: fix 0/10, review 1/5, re-verify 1
- Last completed stage: 6 ship  Next: none
- Hard blocker: none
- WIP commit: none

### Autopilot decisions (2026-11-11)
- Stage 1: plan already Validated in ticket; reused.
### Baseline (2026-11-11)
- backend/chat + backend/database tests: 509 passed before changes.

### Implementation progress
- [x] Step 1: `chats.is_temporary INTEGER DEFAULT 0` (CREATE and the column migration list) + `TEMPORARY_CHAT_TTL_SECONDS` (default 86400) + tests
- [x] Step 2: `update_chat` allows `is_temporary`; `get_listed_chats` leaves out temporary chats; new `get_expired_temporary_chats(user_id, before_ts)` + tests (backend/database/wrapper/tests/test_chat_ops.py)
- [x] Step 3: `temporary` (boolean, 400 otherwise, before `claim_chat`) marks the chat on its first send and is kept out of the handler's kwargs; `PATCH {is_temporary: false}` saves it (any other value 400, before `claim_chat`) - router.py
- [x] Step 4: `backend/chat/cleanup.py` `purge_expired_temporary_chats(user_id, delete_chat)`; `remove_chat`'s steps became `_delete_chat_fully` in router.py (RAG set up only for a chat with files); `list_chats` sweeps the caller's expired temporary chats first
- [x] Step 5: frontend `temporary` in `buildCompletionBody`/`sendTurn`, `ChatPatch.is_temporary`, `saveTemporaryChat` sends `is_temporary: false` + tests
- [x] Step 6: docs (api.md, data.md, frontend.md without net lines, chat and wrapper READMEs). Legacy UI check: the legacy UI never sends `temporary` or `is_temporary` and reads named chat fields only, so it is unaffected; its chat list simply no longer shows unsaved temporary chats it never created.
- Deviation: `_delete_chat_fully` stays in router.py (not in cleanup.py) because the existing DELETE tests patch `router.db`/`router.task_manager` and must pass unchanged; `purge_expired_temporary_chats` takes the delete function as a parameter instead.

### Smoke test (2026-11-11)
- backend + tests 1687 pass; frontend typecheck, lint, unit tests pass; ruff clean.
- Stage 5: resolve-review done inline by the author (not via the skill). Remaining small window (R1-2): a save that lands between the sweep's re-check and the delete.
PR: https://github.com/archit342000/My-AI/pull/129, branch bugfix/abandoned-temporary-chats, base develop

## Verification
### Verification plan (2026-11-11)
**Diff base:** develop tip. Full form (schema, deletion, ownership).

**Environment:** real Flask backend on a temp data dir (port 5318, static auth) with the scripted model stub (port 5319, `scripts/stub.mjs`: plain answer, or SLOW for a long reply), `TEMPORARY_CHAT_TTL_SECONDS=3`. Phase 1 runs as another user to create that user's expired temporary chat; phase 2 runs as the verifying user. Driver `scripts/verify101.py` is HTTP plus read-only sqlite checks on the throwaway DB. Never touches backend/data. Teardown: kill both processes, rm the temp dir, check ports.

| ID | Criterion | Scenario | Type | Files | Expected |
|----|-----------|----------|------|-------|----------|
| T1 | never listed unless saved | first send with temporary true; GET /api/chats; GET /api/chats/<id> | happy | router.py, chat_ops.py | 200; not in the list; the chat itself is served to its owner |
| T2 | saving keeps it | PATCH {title, is_temporary:false}; list; wait past the TTL; list | happy | router.py | listed at once and still there after the TTL |
| T3 | removed after the TTL | another temporary chat (with an artifact file); wait > TTL; GET /api/chats | happy | cleanup.py, router.py | purged: GET chat is 404-like (empty/none), its rows and files are gone in the DB |
| T4 | non-temporary chats untouched | a plain chat sent without the flag | regression | | listed, kept after the TTL |
| T5 | running chat skipped | temporary SLOW chat still generating when the TTL passes | edge | cleanup.py | not purged while running; purged on a listing after it ended and the TTL passed again |
| T6 | other users' chats | phase 1 user's expired temporary chat | failure | cleanup.py | still in the DB after the verifying user lists |
| T7 | validation | temporary:"yes" -> 400 and no chat row; PATCH is_temporary:true on a new id -> 400 and no row | failure | router.py | 400s, nothing created |
| T8 | later sends | a second send without the flag to a temporary chat | edge | router.py | still temporary (not listed) |
| T9 | older chats | a chat row without the column value (created before the mark) stays listed | regression | | listed |
| R1 | no server errors | backend log | non-functional | | no traceback |

Scripts: `scripts/stub.mjs`, `scripts/start_backend2.sh`, `scripts/verify101.py`, `scripts/run_all.sh`.
### Results (2026-11-11)
Verified at HEAD 32d33f7 plus uncommitted:
- backend/chat/README.md 0e9afe959ab370b0402ce7b546ce87f74da6672e
- backend/chat/router.py 787b5d8b17c72050e27c983baf12aa6d26e9cca9
- backend/chat/tests/test_router.py 6619ca248bf30df4dcdb7c724510672de7b210cb
- backend/config.py 137a71a7beef43ed518149016b3efa1b68612c93
- backend/database/init_db.py 87cc04585ab9f4cfe7b86061caceb83d44e78adf
- backend/database/tests/test_init_db.py 478d39e2af4201abab27f62511aa828984110bce
- backend/database/wrapper/README.md 60e91c16a5eb583d6e00c1ba540e72eb494bbf43
- backend/database/wrapper/chat_ops.py bdad9667c6627843ae43512155000e57026e5305
- backend/database/wrapper/tests/test_chat_ops.py e80fea38db025153fb5a303335f5c169a72fb78b
- backend/tests/test_config.py b7af2c300b8846e603f790bc631e6c90abd688ec
- docs/data.md 88ab8f7bb713fe055fb373ede3ef3dd6bbcebd0b
- docs/frontend.md 3d2c52d6ff4cca48034f8a0aef3d70585d072723
- docs/standards/api.md 95336833423c3aa9165bff744502ec9b361bb5b9
- frontend/src/api/chats.ts d8f2f841d8c5e76e7798a902686d2934854fd8d6
- frontend/src/api/completions.test.ts 58e991ff0b0168cf947da58dc941ee66354e1b48
- frontend/src/api/completions.ts 71313ac81181175588f31a4d994cfdddb63c2bc0
- frontend/src/features/chat/send-turn.ts c80b2f9a31dc7c3541617562b4407aa96809c168
- frontend/src/features/chat/temporary-chat.test.ts 160fa0c703ba29bbf51af62d07ec74a2db87284b
- frontend/src/features/chat/temporary-chat.ts d2a5e5c10c46e4182912aba83cdd9af68adb7f98
- backend/chat/cleanup.py 5506ce1450eefdbe8ef0b2568e72aed6f9201308
- backend/chat/tests/test_cleanup.py 7204519a587d9add230d06c3723211aaf333af9b

Evidence: `~/.claude/tickets/My-AI/MYAI-101-evidence/` (results.txt, backend logs, stub.log, scripts/). Real backend (TTL 3 s) with a scripted model, a second user seeded in phase 1; torn down (ports free, dir removed).

| ID | Status |
|----|--------|
| T1, T8 | PASS (marked on the first send, not listed, still served to its owner, a later plain send keeps it temporary) |
| T2a, T2b | PASS (saving lists it at once and it survives the TTL) |
| T3 | PASS (expired unsaved chats purged on the next listing: chat, messages and artifact rows gone) |
| T4, T9 | PASS (a plain chat and an older never-marked chat stay listed) |
| T5a, T5b | PASS (a chat with a running turn is skipped; purged on a listing after it ended and the TTL passed) |
| T6 | PASS (another user's expired temporary chat is not touched) |
| T7 | PASS (invalid values are 400 and create nothing) |
| R1 | checked below |
Regression: backend+tests 1687, frontend unit tests pass.
Gap: removal of an uploaded file's disk and RAG data was not exercised live (artifact rows were); `_delete_chat_fully` is covered by the existing DELETE tests plus a new RAG-only-with-files test.
Verdict: verified (11 PASS, 0 FAIL, 0 BLOCKED).

## Review history
### Round 1 - 2026-11-11
Verdict: Request changes (3 MAJOR) -> after resolution Approve. One Haiku reviewer, working tree vs develop. 11 findings.
- R1-1 [MAJOR] cleanup.py - a send that claimed its turn but whose worker had not started could have its chat deleted - Static - Fixed (the sweep claims the chat's turn slot for the delete and releases it after; chats whose slot is taken are skipped; tests)
- R1-2 [MAJOR] a save between the lookup and the delete could be overwritten - Static - Fixed in part (re-read under the slot: skipped when no longer temporary; a save landing after that re-check and before the delete is a remaining, very small window); test
- R1-3 [MAJOR] RAG setup moved inside the try so a setup failure orphaned files - Static - Fixed (setup outside the try for a chat with files: a setup failure fails the delete and keeps the chat; test)
- R1-4 [MINOR] first-send mark was a read then a write - Fixed (`mark_chat_temporary`: one conditional UPDATE only while the chat has no messages; tests)
- R1-5 [MINOR] workspace order counted unsaved temporary chats - Fixed (join excludes them; test)
- R1-6 [MINOR] `temporary` added to `HistoryMessage` - Fixed (only on `CompletionOptions`)
- R1-7 [MINOR] purge latency inside the listing - Fixed in part (at most 20 chats removed per request; documented)
- R1-8 [MINOR] missing tests - Fixed (claim held, saved after lookup, cap, GET of a temporary chat, RAG setup failure)
- R1-9 [NIT] config layout - Fixed. R1-10 [NIT] api.md check order - Fixed. R1-11 [NIT] TTL zero or less - Documented in config.
Resolved inline by the author. Re-verified: live harness 11/11, backend+tests 1695, frontend typecheck/lint/1106, ruff.

## Log
- 2026-11-11: created (split from MYAI-96 at the user's request)
- 2026-11-11: linked split_from MYAI-96
- 2026-11-11: plan validated, 2 rounds
- 2026-11-11: autopilot started (batch-autopilot)
- 2026-11-11: implemented, smoke tests pass
- 2026-11-11: verify: 11 PASS, 0 FAIL, fix 0/10
- 2026-11-11: review round 1 resolved (11 addressed, 1 in part); re-verified
- 2026-11-11: batch-autopilot: shipped, base develop (https://github.com/archit342000/My-AI/pull/129)
