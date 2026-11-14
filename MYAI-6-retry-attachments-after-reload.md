---
id: MYAI-6
title: "N14: retry does not resend attachments and they do not survive reload"
status: done
created: 2026-11-08
updated: 2026-11-09
links:
  blocks: [MYAI-19, MYAI-20, MYAI-21]
  conflicts_with: [MYAI-7, MYAI-22, MYAI-24, MYAI-25, MYAI-29, MYAI-31]
  relates_to: [MYAI-30, MYAI-43]
---

## Description
Report N14 (Low). Retry passes files: [] (MessageList retry), and the user turn has no file references in the server history, so attachments are lost after a reload. Suggested fix: persist file references on the server message (schema change, needs approval). **Blocked on a decision**: whether to change the message schema for this.

## Acceptance criteria
- [x] Retry resends the attachments of the original message
- [x] Attachments survive a page reload
- [x] Schema decision recorded (2026-11-09, Implementation notes)

## Plan
**Date:** 2026-11-09  **Status:** Validated

### Objective
Make a user turn's attachments durable and reusable: store the file references on the server-side user message (additive, nullable `messages.attachments` JSON column, approved 2026-11-09), show them on persisted user turns in the React UI so they survive a reload, and make Retry regenerate from the stored user message so the model gets the original attachments again instead of a text-only copy.

### Context
- **Requirement:** Description and Acceptance criteria above. Code read at origin/develop 6a13e04; implementation branches from origin/develop.
- **Assumptions (no user available):**
  - A1. "Retry resends the attachments" is satisfied by regenerating from the persisted user message, whose stored `content` already carries the image parts and the `[System Note: ...]` file list the model needs. Re-posting the files from the client is rejected (see Approach).
  - A2. Only main-chat user messages get `attachments`; `sub_agent_messages` is unchanged.
  - A3. Stored shape is a JSON array of `{file_id, name, size, mime_type}` (the `UploadedFile` shape in `frontend/src/api/completions.ts`); other client keys are dropped.
  - A4. Existing chats are backfilled from their `collections` rows of type `files` (rule 4 of `docs/data.md`), so old attachments also reappear after reload; rows without such a collection stay `NULL`.
  - A5. Chips are shown for every attachment, images included, matching the optimistic row (`LiveUser`); images also keep rendering from content parts as today.
- **Rules:** `docs/data.md` Migrations (idempotent `init_db()`, `PRAGMA table_info` check then `ALTER TABLE ... ADD COLUMN`, backfill in the same step, test that runs `init_db()` twice and against the previous schema); `AGENTS.md` (use `db`, no raw SQL outside the database layer, `log_event`, no masked errors, `venv/bin/python`, `ruff check .`, `scripts/check.sh`); `docs/standards/testing.md` (1:1 tests, regression tests); `docs/standards/frontend.md` (typed API responses in `src/api/`, no `!`, pure logic in `src/lib/` with tests, stable keys); `docs/standards/api.md` (`POST /api/chats/<id>/resume` is a documented generation endpoint).
- **Current behaviour:**
  - `backend/chat/router.py` `chat_completions` always persists `messages[-1]` as a new user row via `db.add_message` (appending the file note to `content`, image parts as JSON), then stores the files as a `collections` row of type `files` on that message; `ChatHandler.initiate_chat` (`backend/chat/handler.py`) stores them again as `file_uploads`. The model's history is read from the DB (`db.get_messages`), not from the client's `messages`.
  - `db.get_woven_history` (`backend/database/wrapper/history_ops.py`) attaches `collections` to messages, but only when the chat has an order map; the React `toTurns` (`frontend/src/lib/chat-model.ts`) ignores them, so user turns show no file chips after a reload (images render only because they are inline content parts).
  - `MessageList.tsx` `regenerateFrom` calls `sendTurn` with `files: []` for Retry (`retry`, `retryLast`) and for edit "Save & regenerate". Because the router persists every posted user message, a Retry also adds a second, text-only copy of the user turn (images dropped).
  - `messages` is created in two places in `backend/database/init_db.py`: the `CREATE TABLE IF NOT EXISTS messages` and the `dependent_tables['messages']` recreate used by migration 11 (ON DELETE CASCADE), which copies the old table's columns by name.
  - `get_messages` (`backend/database/wrapper/message_ops.py`) decodes JSON fields via `_parse_json_field`; `backend/inference/engine.py` whitelists message keys before calling the model, so a new key is not sent upstream.
  - Legacy UI (`static/js/message-manager.js`) already renders `files` collections on user rows and retries through `/resume` (`retryMessageAction` in `static/js/message-manager.js` calls `deps.sendMessage(null, null, true)`; `sendMessage` in `static/script.js` picks the `/resume` endpoint when `isResume`), so it needs no change and keeps working.

### Approach
Add a nullable `attachments TEXT` column on `messages`, written by the completions route when files are sent and backfilled from existing `files` collections. `get_messages` decodes it, so `GET /api/chats/<id>` returns it on user messages. The React chat model maps it to `files` on user turns and `UserTurn` renders chips. Retry (both buttons) deletes the old reply as today and then calls `POST /api/chats/<id>/resume`, which regenerates from the stored last user message, so attachments are reused exactly and no duplicate user row is created; this matches the legacy UI.
- Rejected: keep `sendTurn` and pass the stored files. The router would add a duplicate user row and append the file note a second time to text that already contains it.
- Rejected: read attachments only from `collections`. They are attached only when an order map exists, are stored twice (`files`, `file_uploads`), and the user decision asks for a field on the message.
- Rejected: a new "retry" flag on `/v1/chat/completions`. `/resume` already does this and is documented.
- Out of scope: edit "Save & regenerate" keeps using `sendTurn` (separate behaviour, see Risks); the `collections` writes are left as they are.

### Steps
#### Step 1: Schema and migration
- **Files:** `backend/database/init_db.py` (modify) `init_db`.
- **Change:** add `attachments TEXT` to both `messages` definitions (the `CREATE TABLE IF NOT EXISTS messages` and `dependent_tables['messages']`). After migration 11, add one block: if `PRAGMA table_info(messages)` lacks `attachments`, `ALTER TABLE messages ADD COLUMN attachments TEXT DEFAULT NULL`; then backfill: select user messages with `attachments IS NULL` that have a `collections` row with `collection_type='files'` and `parent_type='main'` (lowest id wins), parse its `items` JSON in Python, keep only `file_id`, `name`, `size`, `mime_type` from dict items (same rule as Step 4, so old and new rows share one shape), and `UPDATE` the message; skip rows whose items do not parse to a list (leave `NULL`). Log the count with `logger.info` like neighbouring migrations. No `try/except` around the new block.
- **Verification:** Step 2 tests.

#### Step 2: Migration tests
- **Files:** `backend/database/tests/test_init_db.py` (modify), new tests.
- **Change:** (a) fresh DB, `init_db()` twice: column exists once and is nullable. (b) previous schema: a `messages` table created with the current `ON DELETE CASCADE` definition minus `attachments` (so migration 11 skips the recreate and the PRAGMA/ALTER path runs), a `collections` table created by the fixture as the existing legacy fixture does, and a `collections` `files` row (items with an extra client key) for a user message, a user message without one, and one with unparsable items; `init_db()` twice: the first is backfilled with the sanitized items, the others stay `NULL`, other columns intact. (c) extend `test_init_db_with_legacy_data` (non-CASCADE `messages`, triggers the recreate) to assert the recreated table has `attachments` and rows survive.
- **Verification:** `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest backend/database/tests/test_init_db.py -q`.

#### Step 3: DB layer read and write
- **Files:** `backend/database/wrapper/message_ops.py` (modify) `add_message`, `get_messages`; `backend/database/wrapper/tests/test_message_ops.py` (modify).
- **Change:** `add_message` gains keyword `attachments: list | None = None`, JSON-encoded and inserted for `parent_type == "main"` only (sub-agent branch unchanged). `get_messages` decodes `attachments` with `_parse_json_field` like `tool_calls`. Tests: round trip of a list; default `NULL`; sub-agent insert unaffected.
- **Verification:** `pytest backend/database/wrapper/tests/test_message_ops.py backend/database/wrapper/tests/test_history_ops.py -q` (same env prefix).

#### Step 4: Persist attachments in the completions route
- **Files:** `backend/chat/router.py` (modify) `chat_completions`; `backend/chat/tests/test_router.py` (modify).
- **Change:** when `files` is a non-empty list, build `attachments` keeping only `file_id`, `name`, `size`, `mime_type` from each dict item, and pass it to `db.add_message(...)` for the user row; otherwise pass `None`. Content and the `collections` write are unchanged. Tests: extend `test_chat_completions_with_images` / `test_chat_completions_without_images` to assert `add_message` got the sanitized `attachments` (extra keys dropped); a send without files passes `None`. Extend `test_resume_chat`: resume passes the stored last user message (with its `attachments`) to `initiate_chat` (router level). Add to `backend/chat/tests/test_handler.py`, next to `test_initiate_chat`: `initiate_chat` with a `user_message` and no files does not call `db.add_message` for a user row (process_message mocked), which is the contract Retry relies on in Step 8.
- **Files (tests):** also `backend/chat/tests/test_handler.py` (modify).
- **Verification:** `pytest backend/chat/tests/test_router.py backend/chat/tests/test_handler.py -q` (same env prefix).

#### Step 5: Frontend types and chat model
- **Files:** `frontend/src/api/types.ts` (modify) `StoredMessage`; `frontend/src/lib/chat-model.ts` (modify) `Turn`, `toTurns`, new exported `parseAttachments`; `frontend/src/lib/chat-model.test.ts` (modify).
- **Change:** `StoredMessage.attachments?: Nullable<unknown>` (decoded list from the server; absent on old rows). `parseAttachments(raw: unknown): UploadedFile[]` returns only array items with a string `file_id` and `name` (numeric `size`, string `mime_type`, defaults `0` and `''`), else `[]`. User `Turn` gains `files: UploadedFile[]`, filled by `toTurns`. Tests: list mapped; `null`, missing, non-array and malformed items give `[]`.
- **Verification:** `cd frontend && npx vitest run src/lib/chat-model.test.ts`.

#### Step 6: Show attachments on persisted user turns
- **Files:** `frontend/src/features/chat/MessageList.tsx` (modify) `UserTurn`; `frontend/src/features/chat/MessageList.test.tsx` (modify).
- **Change:** when `turn.files.length > 0`, render the same `message-attachments` / `message-file-chip` markup as `LiveUser` (key `file_id`), after the text, as `LiveUser` does. Test: turns from stored messages with `attachments` show the file names; without them no chip container.
- **Verification:** `cd frontend && npx vitest run src/features/chat/MessageList.test.tsx`.

#### Step 7: Resume API helper and resumeTurn
- **Files:** `frontend/src/api/completions.ts` (modify) new `resumeStream(chatId, body, signal)`; `frontend/src/api/completions.test.ts` (create); `frontend/src/features/chat/send-turn.ts` (modify) new exported `resumeTurn(queryClient, chatId)`; `frontend/src/features/chat/send-turn.test.ts` (modify).
- **Change:** `resumeStream` POSTs `body` to `/api/chats/<id>/resume` through `apiRequest` and yields `readSse` chunks (throws on HTTP errors like `streamCompletion`). `resumeTurn` applies the same guards as `sendTurn` (model selected, not already streaming), starts the stream store with no pending row, builds the body with `buildCompletionBody` from current settings (`messages: []`, no files; the server reads the stored turn and drops `model`, `researchMode`, `userPreferences`, `fileSystemMode`, `browsingMode` via `RESUME_STRIP_KEYS`, while sampling, `gitMode` and `persona_id` are still synced by `initiate_chat`, as they are for today's `sendTurn` retry), and runs it through the existing `consume`. Tests: `completions.test.ts` covers `resumeStream` (POST to the resume URL with the body, yields parsed chunks, throws with the server message on a non-2xx response; mock `fetch`); `send-turn.test.ts`: posts to the resume URL with model and sampling; no pending row; HTTP error is shown as an interrupted turn plus toast; no request when a stream is running or no model.
- **Verification:** `cd frontend && npx vitest run src/api/completions.test.ts src/features/chat/send-turn.test.ts`.

#### Step 8: Retry uses resume
- **Files:** `frontend/src/features/chat/MessageList.tsx` (modify) `retry`, `retryLast`; `frontend/src/features/chat/MessageList.test.tsx` (modify).
- **Change:** `retry(assistantIdx)` keeps the delete and cache invalidation, then calls `resumeTurn(queryClient, chatId)`; `retryLast` calls `resumeTurn` directly. `regenerateFrom` stays for edit "Save & regenerate". Replace the test "retry sends the conversation history up to the replaced question" with: Retry on the last reply deletes that reply then calls `resumeTurn` and not `sendTurn`; user-bubble Retry calls `resumeTurn`; a failed delete shows a toast and does not resume.
- **Verification:** `cd frontend && npx vitest run src/features/chat/MessageList.test.tsx`.

#### Step 9: Full checks and docs
- **Files:** none expected. `backend/database/README.md`, `backend/chat/README.md`, `frontend/README.md` and `docs/frontend.md` do not describe message columns or the retry flow (checked at 6a13e04); re-check after implementing and update any that now disagree.
- **Change:** run the full gate.
- **Verification:** `venv/bin/python -m ruff check .`, then `scripts/check.sh` all PASS; `cd frontend && npm run typecheck && npm run lint && npm run test`. Legacy `static/js` tests unchanged.

### Tests
- Backend: `backend/database/tests/test_init_db.py`, `backend/database/wrapper/tests/test_message_ops.py`, `backend/chat/tests/test_router.py` (Steps 2-4), then parent dirs `backend/database/tests`, `backend/chat/tests`, `backend/`, and `tests/`, each in its own pytest process with the env prefix from `docs/standards/testing.md`.
- Frontend: `chat-model.test.ts`, `send-turn.test.ts`, `MessageList.test.tsx` (Steps 5-8), then `npm run typecheck`, `lint`, `test`, `build`.
- Live check for the verify stage: send a message with a text file and an image, reload: chips show; Retry the reply: one user row remains in `GET /api/chats/<id>` and the new reply refers to the files.

### Risks and open questions
- Edit "Save & regenerate" still posts through `/v1/chat/completions`, so it adds a second user row, and `edit_message` (`message_ops.py`, `UPDATE messages SET content = ?` with the edited draft, which is the parsed text only) replaces multimodal content with plain text (images dropped from the model's view; the `attachments` column survives the edit). Pre-existing, outside this ticket; suggest a separate ticket.
- Stored user text shown in the UI still contains the `[System Note: ...]` file list appended by the router. Pre-existing; could be stripped for display now that attachments are structured. Suggest a separate ticket.
- `/resume` ignores research, preferences, file-system and browsing toggles changed since the original turn (`RESUME_STRIP_KEYS`, `router.py` `resume_chat`), while sampling, `git_mode` and `persona_id` are synced from current settings (`initiate_chat`; the persona snapshot is kept once set, and `code_execution_mode` is not synced because the body key is `code_execution_mode` while the handler reads `codeExecutionMode`), as with today's retry. Same as the legacy UI; acceptable.
- Deleted files: the column keeps references after a file is removed from storage; chips still show the name, and the model's note references an id that `document_agent` may not find. Same as today's collections.
- Backfill on a large `messages` table runs once (guarded by `attachments IS NULL` and the existence of a `files` collection); a correlated `UPDATE` is acceptable at this app's scale.
- No open blocking questions.

### Success criteria
- [ ] Retry (last reply and user-bubble) regenerates from the stored user message: no duplicate user row, and the model input still holds the original image parts and file note.
- [ ] A sent message's attachments show as chips on its user turn after a reload, including chats created before the migration that have a `files` collection.
- [ ] `init_db()` is idempotent and migrates a pre-change database (including the CASCADE recreate path) without losing rows.
- [ ] `ruff check .` and `scripts/check.sh` pass.

### Validation log
- **Round 1:** validator PASS, 6 MINOR. My judgement: pass. (1) The backfill copied raw collection items. Valid: the router stores raw client dicts (`router.py` `items=files`). The backfill now sanitizes in Python. (2) The resume strip-keys wording was inaccurate. Valid: `RESUME_STRIP_KEYS` covers only 5 keys. Step 7 and Risks reworded. (3) `resumeStream` had no test file. Valid: there is no `completions.test.ts`. It is now created in Step 7. (4) There was no backend resume test. Valid: added a `test_resume_chat` extension. (5) The legacy retry attribution was wrong. Valid: corrected to `message-manager.js` and `script.js`. (6) The edit_message claim was unconfirmed. Checked and true: `UPDATE messages SET content = ?` with the parsed draft text. Kept, with the citation added.
- **Round 2 (diff-scoped):** validator PASS, 4 MINOR. My judgement: pass. (1) `code_execution_mode` is not synced. Valid: the handler reads `codeExecutionMode` while the body sends `code_execution_mode`. Reworded. (2) The persona snapshot is kept once set. Valid (`handler.py` `initiate_chat`). Reworded. (3) The router-level resume test only proves part of the contract. Partly valid: added a handler-level test in `test_handler.py`. (4) The fixture in Step 2(b) would hit the CASCADE recreate, not the ALTER path. Valid: the fixture now uses the CASCADE schema without `attachments`.
- **Round 3 (diff-scoped):** validator PASS, 3 MINOR. My judgement: pass, so I stopped after round 3. (1) The fixture must create `collections`. Valid: added to Step 2(b). (2) The handler test passes trivially because `initiate_chat` never adds user rows. Accepted as a regression guard and kept. The router-level `test_resume_chat` already asserts that `db.add_message` is not called. Deferred to implement for any tightening. (3) Persona id can change while the snapshot is kept. Informational, already covered in Risks, no change.

## Implementation notes
### Autopilot run (2026-11-09)
- Mode: automatic (batch-autopilot, item 3/3)
- Branch: bugfix/retry-attachments-after-reload  PR base: develop  Starting commit: 6a13e04
- Dirty before start: none
- Work files: backend/chat/router.py, backend/chat/tests/test_handler.py, backend/chat/tests/test_router.py, backend/database/init_db.py, backend/database/tests/test_init_db.py, backend/database/wrapper/message_ops.py, backend/database/wrapper/tests/test_message_ops.py, frontend/src/api/completions.ts, frontend/src/api/completions.test.ts, frontend/src/api/types.ts, frontend/src/features/chat/MessageList.tsx, frontend/src/features/chat/MessageList.test.tsx, frontend/src/features/chat/send-turn.ts, frontend/src/features/chat/send-turn.test.ts, frontend/src/lib/chat-model.ts, frontend/src/lib/chat-model.test.ts
- Counters: fix 0/10, review 1/5, re-verify 1
- Last completed stage: 6 ship  Next: none
- Hard blocker: none
- WIP commit: none

### Autopilot decisions (2026-11-09)
- Stage 1: plan already Validated (3 rounds); reused, not re-planned (user confirmed all tickets are already planned).

### Baseline (2026-11-09)
backend/database/tests 56 pass, 2 fail (test_cache_system async tests: pytest-asyncio not installed in the venv); wrapper tests 69 pass; backend/chat/tests 108 pass. Same async-plugin failures elsewhere in check.sh (tools, research_agent, tavily_mcp, code_runner_mcp). Frontend baseline: vitest 264 pass (47 files), typecheck clean, lint 1 pre-existing warning (forms.tsx:44, MYAI-15).

### Implementation progress
- [x] Step 1: schema + migration (attachments column, backfill) - backend/database/init_db.py
- [x] Step 2: migration tests - backend/database/tests/test_init_db.py
- [x] Step 3: DB read/write - backend/database/wrapper/message_ops.py, tests/test_message_ops.py
- [x] Step 4: persist attachments in completions route - backend/chat/router.py, chat/tests/test_router.py, test_handler.py
- [x] Step 5: frontend types + chat model - frontend/src/api/types.ts, src/lib/chat-model.ts(+test)
- [x] Step 6: chips on persisted user turns - frontend/src/features/chat/MessageList.tsx(+test)
- [x] Step 7: resumeStream/resumeTurn - frontend/src/api/completions.ts(+new completions.test.ts), src/features/chat/send-turn.ts(+test)
- [x] Step 8: Retry uses resume - MessageList.tsx, MessageList.test.tsx
- [x] Step 9: full checks; no README/docs describe message columns or retry (grepped database/chat/frontend READMEs, docs/frontend.md, docs/data.md)
Branch: bugfix/retry-attachments-after-reload

### Smoke test (2026-11-09)
Backend: test_init_db 8 pass, message_ops 7, chat tests 109 pass; ruff clean; `scripts/check.sh --python-only`: backend 10 fail / tavily_mcp 5 fail / code_runner_mcp fail, all `async def` plugin errors (pytest-asyncio missing), baseline cause, none in touched code. Frontend: vitest 276 pass (48 files), typecheck clean, lint only the pre-existing warning, `npm run build` ok. New tests not shown failing pre-fix by reverting (not reverted).


Status on develop (checked at e327094, 2026-11-08): Still present on develop: retry sends files: [] in MessageList.tsx.
Decision (user, 2026-11-09): schema change approved. Store file references on the server-side user message with an additive migration (nullable column or JSON field; old rows keep working).

PR: https://github.com/archit342000/My-AI/pull/57, branch bugfix/retry-attachments-after-reload, base develop

## Verification
### Verification plan (2026-11-09, full form: schema migration, backend + React frontend)
**Diff base:** 6a13e04. **Scope:** `messages.attachments` column and backfill (`init_db`), persisting file references in `POST /v1/chat/completions`, returning them in `GET /api/chats/<id>`, chips on persisted user turns, Retry via `POST /api/chats/<id>/resume`. Out of scope: edit "Save & regenerate", the `[System Note]` text in stored user messages, legacy UI changes.
**Environment and isolation:** real Flask app from this branch on 127.0.0.1:5099 with the built React frontend, `DATA_DIR=/tmp/myai6-data` (fresh sqlite DB), `AI_PROXY_URL=http://127.0.0.1:5098` pointing at a fake inference proxy (`scripts/fake_proxy.py`, logs every upstream request body). The real app on :5000, the real inference-proxy on :5001, containers and `backend/data` are never touched. Teardown: kill both PIDs, delete `/tmp/myai6-data`, compare ports, containers and git status to the snapshot.
**Plan note 2026-11-09 (during verification):** V3's expectation "list with non-dict items, no 500" is superseded by V3b. Reason: the 500 comes from the pre-existing file-note loop (`f.get('file_id')` on a non-dict item, `backend/chat/router.py` line 284 at HEAD and line 283 at 6a13e04) which runs before the changed code and is outside this ticket; the requirement only covers persisting file references. V3b: send with no files, empty list, a valid list and a dict with no known keys; expected NULL, NULL, sanitized list and a stored list (not a 500). The non-dict 500 is recorded as a pre-existing defect, not fixed here.
Scripts: `scripts/fake_proxy.py` (fake upstream), `scripts/v6_api.py` (API/DB driver, refuses non-throwaway URL/DB), `scripts/v6_migrate.py` (old-schema DB builder), `scripts/ui.js` (Playwright, system chromium).

| ID | Criterion | Scenario | Type | Method | Files | Expected |
|----|-----------|----------|------|--------|-------|----------|
| V1 | Migration on pre-change DB | Build a DB with the old `messages` schema (no `attachments`) holding user messages, a `files` collection (with an extra key), a message with unparsable items and a non-user row; start the app on it twice (restart) | happy/edge | DB + app start | init_db.py | column added once, user message with a files collection backfilled with only file_id/name/size/mime_type, others NULL, all rows kept, second start no-op, no startup error in the app log |
| V2 | Attachments stored | Upload a text file, then POST completions with `uploadedFiles` (two files, one with extra keys) | happy | API + DB | chat/router.py, message_ops.py | user row `attachments` = sanitized list; `GET /api/chats/<id>` returns it decoded on that message |
| V3 | No files | POST completions with no `uploadedFiles`; and `uploadedFiles: []`, and one with junk items | edge | API + DB | chat/router.py | `attachments` NULL for none/empty; junk items dropped (all junk -> NULL), no 500 |
| V4 | Retry reuses attachments | POST `/resume` after the reply exists: delete the old reply, resume | happy | API + DB + fake upstream log | chat/router.py, handler | new assistant row; user row count unchanged (no duplicate); upstream request's last user message contains the original text and file note (and image part when an image was sent) |
| V5 | Resume with no user message | POST `/resume` on an empty chat | failure | API | chat/router.py | 400 `No user message found to resume from.` |
| V6 | Attachments survive reload (UI) | In the React UI, attach a file, send, reload the page | happy | browser | MessageList.tsx, chat-model.ts | chip with the file name on the user turn before and after reload |
| V7 | Retry in the UI | Click Retry on the reply | happy | browser + DB | MessageList.tsx, send-turn.ts | new reply streams, one user row in the DB, fake upstream got the file note again, chip still shown |
| V8 | Old chat shows chips | Open (in the UI) a chat from V1's backfilled DB | regression | browser | init_db.py, chat-model.ts | chip shown for the backfilled message |
| V9 | Plain chats unchanged | UI send without files, reload | regression | browser | MessageList.tsx | no chip container, one user row |
| V10 | Regression | pytest dirs (database, chat, tools, tests), ruff, vitest, typecheck, lint, build | regression | CLI | all | only baseline failures |

### Results (2026-11-09)
Verified at HEAD 6a13e04114e9636ed903fbb8e177ad0b2e800bfc plus uncommitted (hash prefixes): backend/chat/router.py f701ef70, backend/chat/tests/test_handler.py 4da8bed9, backend/chat/tests/test_router.py 757dde72, backend/database/init_db.py 212b8ce5, backend/database/tests/test_init_db.py c018e8d8, backend/database/wrapper/message_ops.py b2e0b5e8, backend/database/wrapper/tests/test_message_ops.py 39bc6bc4, frontend/src/api/completions.ts dbcc8ca8, frontend/src/api/completions.test.ts 8206094d, frontend/src/api/types.ts b6ce5e3a, frontend/src/features/chat/MessageList.tsx 26739334, frontend/src/features/chat/MessageList.test.tsx fb3b46b9, frontend/src/features/chat/send-turn.ts 42eb550b, frontend/src/features/chat/send-turn.test.ts fdbeebfc, frontend/src/lib/chat-model.ts 29df034f, frontend/src/lib/chat-model.test.ts 80b35faf.
Isolation: app on 127.0.0.1:5099 (DATA_DIR=/tmp/myai6-data, built React frontend), fake inference proxy on 127.0.0.1:5098 (AI_PROXY_URL); the real app on :5000, the real inference-proxy on :5001 and `backend/data` were not touched. Teardown: both PIDs killed, 5098/5099 free, temp dir removed; containers and git status identical to the snapshot (the listening-port diff shows only unrelated ephemeral ports opened by other processes since the snapshot).

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | v1-migration.log, app-run2/3.log: old-schema DB gained `attachments` once; message 101 backfilled with only file_id/name/size/mime_type; assistant, no-collection, unparsable and non-files rows NULL; all rows kept; second start logged no migration |
| V2 | PASS | v2-v5.log: two uploaded files (one image) sent; stored list sanitized (extra key dropped); `GET /api/chats/<id>` returns it on the user message |
| V3 | superseded by V3b | the non-dict `uploadedFiles` item gives a 500 in the pre-existing file-note loop (`router.py` line 284, also line 284 at 6a13e04), before the changed code; see the plan note |
| V3b | PASS | v2-v5.log (none, empty), v3b.log: none and `[]` store NULL; valid list sanitized; a dict with no known keys stores `[{}]` (harmless, the UI skips it). Pre-existing 500 for non-dict items is not fixed here |
| V4 | PASS | v2-v5.log, upstream.jsonl: after deleting the reply, `/resume` produced one new assistant row, user row count stayed 1 (same id), upstream request held the original text, the `[System Note]` file list and the image part |
| V5 | PASS | v2-v5.log: `/resume` on a chat without a user message returns 400 `No user message found to resume from.` |
| V6 | PASS | v6-v9-ui.log, ui-v6-*.png: file chip on the user turn before and after reload |
| V7 | PASS | v6-v9-ui.log, ui-v7-after-retry.png: Retry in the UI gave one user row, one assistant row, upstream got the file note again, chip still shown |
| V8 | PASS | v6-v9-ui.log, ui-v8-oldchat.png: the migrated old chat shows the backfilled `legacy-notes.txt` chip |
| V9 | PASS | v6-v9-ui.log, ui-v9-plain.png: a plain chat has no chips and `attachments` NULL after reload |
| V10 | PASS | v10-regression.log: database 58 pass + 2 baseline, wrapper 70, chat 109, tools 84 + 6 baseline, backend/tests 25, tests 32, ruff clean; vitest 276 pass, typecheck clean, lint only the pre-existing warning (forms.tsx), build ok |

Verdict: verified. 10 of 10 pass (V3 superseded by V3b), 0 FAIL, 0 BLOCKED. Console errors in the browser run: none.
Not covered: image attachments in the React UI (only a text file was attached through the UI; the image path was exercised via the API in V2/V4), edit "Save & regenerate" (out of scope), a very large `messages` table backfill.
Scripts: scripts/fake_proxy.py, v6_migrate.py, v6_api.py, ui.js.
### Results (re-run 1, 2026-11-09)
Re-run after review round 1 fixes (init_db.py backfill gating, send-turn.ts helper, MessageList.tsx guard, tests, docs/data.md). HEAD 6a13e04114e9636ed903fbb8e177ad0b2e800bfc plus uncommitted (hash prefixes): backend/chat/router.py f701ef70, backend/chat/tests/test_router.py 757dde72, backend/database/init_db.py 1e70ffc5, backend/database/tests/test_init_db.py c1cea374, backend/database/wrapper/message_ops.py b2e0b5e8, backend/database/wrapper/tests/test_message_ops.py 0442c0e8, docs/data.md 9a4a2a52, frontend/src/api/completions.ts dbcc8ca8, frontend/src/api/completions.test.ts 8206094d, frontend/src/api/types.ts b6ce5e3a, frontend/src/features/chat/MessageList.tsx 6e8675f5, frontend/src/features/chat/MessageList.test.tsx fb3b46b9, frontend/src/features/chat/send-turn.ts 7498e7df, frontend/src/features/chat/send-turn.test.ts fdbeebfc, frontend/src/lib/chat-model.ts 29df034f, frontend/src/lib/chat-model.test.ts 80b35faf. Frontend rebuilt first. Fresh throwaway state (app 5099, fake proxy 5098, /tmp/myai6-data); ports 5098/5099 free afterwards, containers and git status identical to the snapshot. Evidence in rerun1/.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | rerun1/v1-migration.log, app-run2/3.log: column added once, message 101 backfilled (4 fields only), other rows NULL, migration logged on the first start only |
| V2 | PASS | rerun1/v2-v5.log (also re-run because it starts from a freshly migrated DB) |
| V3 | superseded by V3b | script still shows the known junk-item 500 (pre-existing) |
| V3b | PASS | rerun1/v3b.log |
| V4 | PASS | rerun1/v2-v5.log, upstream.jsonl |
| V5 | PASS | rerun1/v2-v5.log |
| V6 | PASS | rerun1/v6-v9-ui.log: chip before and after reload |
| V7 | PASS | rerun1/v6-v9-ui.log: Retry, one user row, file note re-sent, chip kept |
| V8 | PASS | rerun1/v6-v9-ui.log: migrated old chat shows its chip |
| V9 | PASS | rerun1/v6-v9-ui.log: plain chat has no chips, attachments NULL |
| V10 | PASS | rerun1/v10-regression.log: database/tests 60 pass + 2 baseline, wrapper 70, chat 108, backend/tests 25, tests 32, ruff clean; vitest 276, typecheck clean, lint only the pre-existing warning |

Verdict: verified. Latest status of every scenario PASS (V3 superseded by V3b), 0 FAIL, 0 BLOCKED. Browser console errors: none. Not covered: as before (image attachment through the React UI, edit "Save & regenerate", backfill on a very large table).

## Review history
### Round 1 - 2026-11-09
Verdict: Approve with comments (no BLOCKER or MAJOR kept). Scope: 16 files vs 6a13e04, ~436 changed lines, small mode, one Haiku reviewer given the Description, Acceptance criteria and the plan's Objective/Approach/Out of scope/Success criteria. All findings checked against the code; all static.
- R1-1 [MINOR] backend/chat/tests/test_handler.py:150-163 - the new handler test passes on the base code (initiate_chat never adds a user row on this path), so it does not test the change - Static - Fixed: handler test removed (router test_resume_chat already asserts add_message not called), test_handler.py
- R1-2 [MINOR] docs/data.md - the new `messages.attachments` column and its backfill are not described in docs (acceptance 3 is recorded only in the ticket and a code comment) - Static - Fixed: docs/data.md describes messages.attachments
- R1-3 [MINOR] backend/database/init_db.py:1040-1067 - the backfill rescans every user message with NULL attachments on every start; it should run only when the column is first introduced (including the CASCADE recreate path) - Static - Fixed: backfill runs only when messages lacked the column before migration 11 (ALTER and CASCADE-recreate paths), init_db.py; tests added
- R1-4 [MINOR] backend/database/init_db.py:1040 - `import json` inside init_db(); python.md wants module-top imports - Static - Fixed: `import json` at module top, init_db.py
- R1-5 [MINOR] backend/database/init_db.py:1053-1058 - malformed `files` collections are skipped silently, no log - Static - Fixed: logger.warning for skipped collections, init_db.py
- R1-6 [MINOR] backend/database/tests/test_init_db.py - backfill is tested only on the ALTER path; the CASCADE-recreate path is checked for column and rows only - Static - Fixed: new tests for the CASCADE-recreate backfill and run-once, test_init_db.py
- R1-7 [MINOR] frontend/src/features/chat/send-turn.ts:186-204 - resumeTurn duplicates sendTurn's completion body/modes block - Static - Fixed: shared completionBody helper, send-turn.ts
- R1-8 [NIT] frontend/src/features/chat/MessageList.tsx:413-417 - `userTurn` in retry() is now only an existence guard - Static - Fixed: retry() uses a plain `.some` guard, MessageList.tsx
- R1-9 [NIT] backend/database/wrapper/tests/test_message_ops.py:180 - `assert sub_id is not None` does not check the sub-agent branch - Static - Fixed: asserts the stored sub-agent row, test_message_ops.py
Pre-existing / out of scope:
- R1-10 (Deferred: MYAI-20) edit "Save & regenerate" still posts through the completions route, creating a new user row without attachments, so a later Retry resumes from it (reviewer called it MAJOR). Out of scope in the plan (Approach, Risks) and tracked by MYAI-20; the duplicate row exists at 6a13e04 - Pre-existing
- R1-11 (Deferred: follow-up, suggest a small ticket) retry() deletes the reply and resumeTurn then returns silently if a stream is already running: sendTurn had the same guard after the delete at 6a13e04 - Pre-existing
- R1-12 (Deferred: follow-up) backend/chat/router.py:482 RESUME_STRIP_KEYS does not strip `messages`/`chatId`/some mode flags: untouched code, harmless (live V4/V7 passed) - Pre-existing
Dismissed: `attachments?: Nullable<unknown>` and `chat-model.ts` importing `UploadedFile` from api/completions: `unknown` is deliberate because the server decodes arbitrary JSON and `parseAttachments` validates it; chat-model.ts already imports from `../api/types`, so the api-type import is the existing pattern.

Resolution: 9 Fixed, 0 Rejected, 3 Deferred (pre-existing). Runtime behaviour changed by R1-3 (backend/database/init_db.py) and R1-7/R1-8 (frontend/src/features/chat/send-turn.ts, MessageList.tsx): live re-verify of V1, V6-V9 required. Checks: database/tests 60 pass + 2 baseline, wrapper 70, chat 108, backend/tests 25, tests 32, ruff clean; vitest 276 pass, typecheck clean, lint only the pre-existing warning, build ok.


## Log
- 2026-11-08: created from reports/full-scope-final-report-2026-11-08.md
- 2026-11-09: schema decision recorded (approved, additive).
- 2026-11-09: plan validated, 3 rounds (stored attachments column, retry via /resume).
- 2026-11-09: linked blocks MYAI-19 (React resume path is MYAI-6's resumeTurn)
- 2026-11-09: linked blocks MYAI-20 (Save & regenerate uses MYAI-6's resumeTurn)
- 2026-11-09: linked blocks MYAI-21 (needs Turn.files and messages.attachments from MYAI-6)
- 2026-11-09: linked conflicts_with MYAI-7 (chat_completions and consume in send-turn.ts)
- 2026-11-09: linked conflicts_with MYAI-22 (chat_completions body read)
- 2026-11-09: linked conflicts_with MYAI-24 (new migration blocks at the end of init_db (renumber))
- 2026-11-09: linked conflicts_with MYAI-25 (init_db step 11 dependent-table definitions)
- 2026-11-09: linked conflicts_with MYAI-29 (init_db step 11 definitions)
- 2026-11-09: linked relates_to MYAI-30 (uses messages.attachments for pills once MYAI-6 merges)
- 2026-11-09: linked conflicts_with MYAI-31 (step 11 dependent_tables definitions)
- 2026-11-09: autopilot started (batch-autopilot)
- 2026-11-09: implemented, smoke tests pass (only baseline async-plugin failures)
- 2026-11-09: verified: 10 PASS (V3 superseded by V3b), 0 FAIL, 0 BLOCKED
- 2026-11-09: review round 1: Approve with comments (7 MINOR, 2 NIT, 3 pre-existing)
- 2026-11-09: review round 1 resolved: 9 fixed, 3 deferred; runtime files changed, re-verify needed
- 2026-11-09: re-verified after review fixes: all PASS (V3 superseded by V3b), 0 FAIL, 0 BLOCKED
- 2026-11-09: PR opened #57 (batch-autopilot: shipped, base develop)
- 2026-11-09: linked relates_to MYAI-43 (batch 1 follow-ups)
- 2026-11-09: PR #57 merged into develop; closed
