---
id: MYAI-48
title: "Batch 4 follow-ups: abandoned uploads, AUTOINCREMENT reset, legacy UI refresh"
status: todo
created: 2026-11-09
updated: 2026-11-20
links:
  relates_to: [MYAI-8, MYAI-31]
---

## Description
Open items left by the merged batch 4 PRs (#63 to #66), found in review and verification.

1. **Abandoned uploads keep a listed chat (from the empty-chat list change).** The upload route creates the chat row, and a chat with a file counts as content. If the composer unmounts before sending (navigating between the home and chat pages remounts it) and the chip was never removed, the file stays on the server and the chat shows as a blank sidebar entry with no UI to remove the file. Fix idea: delete unsent uploaded files on composer unmount, or clean up stale file-only chats.
2. **AUTOINCREMENT high-water mark is reset by step 11 rebuilds.** `messages`, `sub_agent_messages` and `collections` use AUTOINCREMENT; the rebuild (old and new code) drops the table, so `sqlite_sequence` restarts at the highest copied id and ids of deleted tail rows can be reused (sub-agent rows and collections reference messages by a plain `parent_message_id`). Fix idea: read `seq` for the table before the drop and write it back for the renamed table, with a test.
3. **Legacy static UI does not refresh the chat list** after file changes and was not checked against `GET /api/chats` omitting empty chats.
4. **Rebuild paths without a `*_old` repair of index names** are now covered by the atomic rebuild; nothing to do unless the failure path of step 8 (workspace migration) is made atomic too. That step renames `file_systems` and its child tables the same way and is not wrapped in a savepoint (`docs/data.md` Migrations rule 3).

## Acceptance criteria
- [ ] Unsent uploaded files do not leave a listed blank chat after navigating away
- [ ] A table rebuild keeps the AUTOINCREMENT sequence (test: delete the tail row, rebuild, insert, id not reused)
- [ ] The legacy UI behaviour with the filtered chat list is checked and either fixed or recorded as out of scope
- [ ] Decision recorded on making the step 8 workspace migration atomic

## Plan

**Date:** 2026-11-20  **Status:** Validated

### Objective
Stop unsent uploads from leaving blank chats in the sidebar, keep the AUTOINCREMENT high-water mark through table rebuilds, and record decisions on the legacy UI list and the step 8 workspace migration.

### Context
- Requirement: the four items and acceptance criteria of this ticket.
- Item 1: `POST /api/files/upload` (`backend/files/router.py` `upload_file_endpoint`) calls `claim_chat` (creates the chat row via `db.ensure_chat_exists`) before validating the file. `GET /api/chats` lists a chat that has a message, a file or a chat-scoped artifact and is not temporary (`backend/database/wrapper/chat_ops.py` `get_listed_chats`), so a chat holding only staged files appears as "New Conversation". React deletes a new chat's staged files on New Chat, leaving `/`, discarding a temporary chat and `pagehide` (`docs/frontend.md` "Staged files"; `features/composer/draft-cleanup.ts`, `useDraftCleanup.ts`), but a crashed or killed tab and the legacy UI (its chip removal makes no DELETE call) leave the files and a listed chat. The temporary-chat purge (`backend/chat/cleanup.py` `purge_expired_temporary_chats`, called from `list_chats` in `backend/chat/router.py`) is the pattern for owner-scoped sweeps: claim the turn slot, re-check, delete with `_delete_chat_fully`, at most `MAX_REMOVED_PER_CALL`, never raise.
- Item 2: `_rebuild_table_with_cascade` (`backend/database/init_db.py`) copies rows with explicit ids into `<table>_new`, drops the old table and renames; SQLite's `sqlite_sequence` row for the table then equals the highest copied id, so ids of deleted tail rows can be reused. AUTOINCREMENT tables it rebuilds: `messages`, `sub_agent_messages`, `collections` (also used for `skills`, which has no AUTOINCREMENT). No test covers this.
- Item 3: the legacy UI (`static/script.js` `loadChats`, `static/js/attachment-manager.js`) never refreshes the list after an upload and never deletes removed or unsent uploads. It is served at `/legacy/` for one release and then removed (`docs/frontend.md`, `docs/architecture.md`).
- Item 4: step 8 of `init_db` (workspace migration) renames and rebuilds `file_systems`, `file_system_versions` and `file_system_permissions` outside any savepoint; `docs/data.md` Migrations rule 3 requires one transaction per rebuild. It only runs on databases from before workspaces.
- Rules: `docs/data.md` (Migrations, never drop user data without an explicit decision), `AGENTS.md`, `docs/standards/api.md`, `docs/standards/testing.md`.

### Approach
- Item 1, two parts:
  - Listing: a chat whose only content is uploaded files is not listed (`get_listed_chats` keeps messages and artifacts, drops the files clause). A React draft is held by the composer, so nothing visible is lost.
  - Clean-up: on its owner's next `GET /api/chats`, a chat with files but no messages, no artifacts, not temporary, created before the cutoff and with no file uploaded after it (`files.created_at`), with the cutoff `now - ABANDONED_UPLOAD_TTL_SECONDS` (config, default 86400), is removed like the temporary-chat purge (claim the turn slot, re-check, `_delete_chat_fully`, release). The cleanup module gets one shared loop for both kinds, and one removal budget per list request (`MAX_REMOVED_PER_CALL` across both kinds, temporary chats first). The re-check inside the claim is a fresh query (`db.is_abandoned_upload_chat(chat_id, cutoff)`), not the cached chat row.
- Item 2: only when the new table's SQL uses `AUTOINCREMENT` and `sqlite_sequence` exists (it is created by SQLite with the first AUTOINCREMENT table), read the table's `seq` inside the helper's savepoint before the drop and, after the rename, set it to `max(saved, current)`; otherwise the helper is unchanged (the `skills` rebuild and plain tables never touch `sqlite_sequence`).
- Item 3, checked: the legacy UI's `loadChats` (`static/script.js`) shows exactly what `GET /api/chats` returns, and its upload path (`static/js/attachment-manager.js`) does not reload the list after an upload, so after Step 1 it also stops listing file-only chats; its unsent uploads are never deleted by the client (chip removal makes no DELETE call) and are removed by the server-side clean-up after the TTL. No legacy change: recorded as out of scope because the legacy UI is removed next release.
- Item 4: an owner decision (below); the plan does not change step 8.

### Out of scope
- Legacy UI changes (item 3), including its object-URL revoke bug in `attachment-manager.js` remove handler.
- Step 8 changes (item 4) unless the owner decides otherwise.
- Bumping a chat's timestamp on upload.

### Steps
#### Step 1: Don't list file-only chats
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/database/wrapper/chat_ops.py` (modify: `get_listed_chats`); `backend/database/wrapper/tests/test_chat_ops.py` (modify: rename `test_chat_with_a_message_a_file_or_an_artifact_is_listed` to `test_chat_with_a_message_or_an_artifact_is_listed_but_not_with_only_files` and retarget it)
- **Change:** drop the `files` EXISTS clause.
- **Verification:** tests: a chat with only a file is not listed; with a message or an artifact it is; temporary rules unchanged.

#### Step 2: Query abandoned upload chats
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/database/wrapper/chat_ops.py` (modify: new `get_abandoned_upload_chats`, `is_abandoned_upload_chat`); `backend/config.py` (modify: `ABANDONED_UPLOAD_TTL_SECONDS`); `backend/database/wrapper/tests/test_chat_ops.py`, `backend/tests/test_config.py` (modify)
- **Change:** `get_abandoned_upload_chats(user_id, cutoff)` returns chat ids of the user's chats with a file, no message, no `file_systems` row, `is_temporary` 0, `timestamp` before the cutoff, no file with `created_at` at or after it and no file still `pending` or `processing`; `is_abandoned_upload_chat(chat_id, cutoff)` applies the same conditions to one chat, uncached.
- **Verification:** tests for each condition (including a recent file in an old chat) and another user's chat.

#### Step 3: Sweep them with the temporary-chat loop
- **Status:** todo
- **Depends on:** Step 2
- **Files:** `backend/chat/cleanup.py` (modify: shared loop, new `purge_abandoned_upload_chats`); `backend/chat/router.py` (modify: `list_chats` calls it after the temporary purge); `backend/chat/tests/test_cleanup.py`, `backend/chat/tests/test_router.py` (modify)
- **Change:** factor the claim, re-check, delete and release loop of `purge_expired_temporary_chats` into one helper taking the candidates, the re-check (temporary: still `is_temporary` as today; abandoned: `is_abandoned_upload_chat`) and the remaining budget, returning how many it removed; `list_chats` runs the temporary purge, then the abandoned purge with what is left of `MAX_REMOVED_PER_CALL`.
- **Verification:** the nine existing cleanup tests pass unchanged; new tests: an old file-only chat is deleted; one that got a message or a new file after the lookup, a running turn, or a young one is kept; the shared budget caps both kinds together; a failure is logged and the list still answers.

#### Step 4: Keep the AUTOINCREMENT sequence through rebuilds
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/database/init_db.py` (modify: `_rebuild_table_with_cascade`); `backend/database/tests/test_init_db.py` (modify)
- **Change:** when the create SQL contains `AUTOINCREMENT` (case-insensitive) and `sqlite_master` lists `sqlite_sequence`, read `seq` for the table before the drop; after the rename, if a value was saved, set the table's row to `max(seq, saved)` (insert the row if absent). All of it runs inside the helper's savepoint, before `RELEASE`, so a failure rolls back with it. Otherwise nothing changes.
- **Verification:** tests: a helper-level test on an AUTOINCREMENT table (insert 3, delete the third, rebuild, insert: id 4); for each of `messages`, `sub_agent_messages` and `collections` in their old schema without `ON DELETE CASCADE` (so step 11 rebuilds them; the test asserts the rebuilt SQL now has it), insert 3 rows, delete the third, run `init_db()`, insert one row: its id is 4; the helper still rebuilds a plain table without AUTOINCREMENT (`test_rebuild_helper_keeps_rows_and_indexes_and_rolls_back_failures`) and the `skills` rebuild; `init_db()` twice stays idempotent; existing rebuild tests pass.

#### Step 5: Docs
- **Status:** todo
- **Depends on:** Steps 1-4
- **Files:** `docs/frontend.md` (modify: "Staged files", in place: the file is at 191 of its 200-line budget), `docs/data.md` (modify: listed chats and the abandoned-upload removal next to the temporary-chat line; Migrations rule 3: rebuilds keep the AUTOINCREMENT sequence), `docs/standards/api.md` (modify: next to the temporary-chat sentence, `GET /api/chats` lists chats with a message or an artifact and also removes chats holding only files after `ABANDONED_UPLOAD_TTL_SECONDS`, default 86400), `backend/chat/README.md` (modify: `cleanup.py` row), `backend/database/wrapper/README.md` (modify: `get_listed_chats` no longer counts files; new chat_ops functions), `docs/pitfalls.md` (modify: table rebuilds and the AUTOINCREMENT sequence)
- **Change:** a line each.
- **Verification:** `pytest tests` passes, including `tests/test_docs.py` (line budgets).

#### Step 6: Record the step 8 decision
- **Status:** todo
- **Depends on:** Step 5 (same paragraph of `docs/data.md`)
- **Files:** `docs/data.md` (modify: Migrations rule 3); `tests/test_docs.py` (modify: new test)
- **Change:** record option (a), as the owner decided, at the end of Migrations rule 3: "Exception to rule 3 (owner decision, 2026-11-20): step 8, the workspace migration, rebuilds `file_systems` and its child tables without a savepoint. It runs only when the stored `file_systems` SQL lacks `UNIQUE(id, chat_id, workspace_id)`, which every database migrated since workspaces has. If its copy fails after the rename, `file_systems_old` is left and the step is not retried on the next start; restore from backup in that case."
- **Verification:** a `tests/test_docs.py` test asserts the phrase "Exception to rule 3" is in `docs/data.md` (fails today); `pytest tests` passes.

### Tests
- `pytest backend/database`, `pytest backend/chat`, `pytest backend`, `pytest tests`, `ruff check .`; frontend suite unchanged but run (`npm run test`) since the list contents change; `scripts/check.sh`.

### Risks and open questions
- A draft left open in a tab for longer than the TTL is removed before it is sent (the chat timestamp is its creation time); the send then fails with "Unknown file" and the composer keeps the text. One day is long enough for that to be rare.
- An upload into such a chat at the very moment the sweep deletes it (after the re-check) fails with a server error; the window is one delete long and only for chats idle for a day.
- A removal of a chat with files sets up the RAG manager inside the list request (`_delete_chat_fully`); the shared budget bounds it.
- Not listing file-only chats also hides one whose messages were all deleted but whose files remain; the sweep removes it after the TTL.

### Decisions for the owner
1. **Step 8 workspace migration atomicity (item 4).** `docs/data.md` Migrations rule 3: "Renames and constraint changes recreate the table inside one transaction". Step 8 does not; it runs only when the stored `file_systems` SQL lacks `UNIQUE(id, chat_id, workspace_id)` (true for databases from before workspaces; the live database has it). Options: (a) leave step 8 as is and record the exception in `docs/data.md`; (b) rewrite step 8 onto `_rebuild_table_with_cascade` with tests for the old schema. Recommendation: (a), because no current database runs it and (b) needs pre-workspace fixtures.
   **Owner's answer (2026-11-20): (a)** leave step 8 as is and record the exception in `docs/data.md`.

### Success criteria
- [ ] Unsent uploaded files do not leave a listed blank chat; old ones are removed (Steps 1-3)
- [ ] A table rebuild keeps the AUTOINCREMENT sequence (Step 4 test)
- [ ] Legacy UI behaviour with the filtered list is checked and recorded as out of scope (Approach, item 3)
- [ ] Decision recorded on the step 8 workspace migration (Step 6)
- [ ] `scripts/check.sh` passes

### Reviewer brief
- Objective: stop unsent uploads from leaving blank chats, keep the AUTOINCREMENT sequence through table rebuilds, record the legacy UI check and the step 8 decision.
- Key decisions: `GET /api/chats` lists chats with a message or an artifact (no longer file-only ones); file-only chats older than `ABANDONED_UPLOAD_TTL_SECONDS` (default 86400), with no recent or still-processing file, are removed on the owner's next list request through one shared purge loop and one per-request budget with the temporary-chat purge; the rebuild helper restores `sqlite_sequence` only for AUTOINCREMENT tables when that table exists, inside its savepoint; the legacy UI is unchanged (recorded); step 8 stays as is and is recorded as the exception to Migrations rule 3 (owner decision).
- Out of scope: legacy UI changes, step 8 changes, bumping a chat's timestamp on upload.
- Success criteria: as listed in the plan.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
Path: pair, Haiku validators, judged against the code.
- Round 1: both FAIL. Valid: wrapper README not updated, no step recording the step 8 decision, the legacy check not stated (blocking, L1); reading `sqlite_sequence` when it does not exist or for non-AUTOINCREMENT tables (blocking, L2). Minors fixed (fresh re-check query, recent-file condition, shared budget, config test, api.md, three-table tests, pitfall entry, frontend.md budget).
- Round 2 (scoped): both PASS. Minors fixed inline (old-schema fixtures, savepoint placement, still-processing files, api.md listing rule, test rename, legacy evidence).
- Owner decision (2026-11-20): step 8 left as is, recorded as the exception to rule 3. Owner round 1: FAIL, valid (the recorded reason must state the real gate and failure mode, and be checked by a test); fixed. Owner round 2 read a stale copy of the ticket; its issues were already fixed; the sentence was checked against `init_db.py` by hand.

## Implementation notes

## Verification

## Review history

## Log
- 2026-11-09: created from the review and verification of PRs #63 to #66 (user asked for a follow-up ticket)
- 2026-11-20: plan validated, 2 rounds (+2 owner-decision rounds)
