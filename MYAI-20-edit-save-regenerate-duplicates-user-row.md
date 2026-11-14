---
id: MYAI-20
title: "Edit \"Save & regenerate\" duplicates the user row and drops images"
status: done
created: 2026-11-09
updated: 2026-11-09
links:
  blocks: [MYAI-21]
  blocked_by: [MYAI-6, MYAI-11]
  conflicts_with: [MYAI-22]
  relates_to: [MYAI-43, MYAI-44]
---

## Description
Found while planning MYAI-6 and MYAI-11. In `MessageList.tsx`, edit "Save & regenerate" goes through `regenerateFrom` -> `sendTurn` with `files: []`, posting to `/v1/chat/completions`, which stores a second user row. `edit_message` (`message_ops.py`) replaces multimodal content with the parsed text only, so images are dropped. The edit route also does not check the message role (an assistant message can be edited through the user-edit path).

## Acceptance criteria
- [x] Save & regenerate leaves one user row with the edited text
- [x] Images and attachments on the edited message are kept
- [x] Editing is limited to user messages (or the allowed roles are stated and enforced)
- [x] Regeneration still produces a reply

## Plan

**Date:** 2026-11-09  **Status:** Validated  **Base:** origin/develop 6a13e04  **Depends on:** MYAI-11 (chat-scoped `edit_message`, empty-content 400), MYAI-6 (React `resumeTurn`)

### Objective
Make edit "Save & regenerate" in the React UI:
- keep exactly one user row, with the edited text;
- keep the message's images and its attachment note;
- allow edits only on user messages;
- still produce a new reply.

### Context
- Requirement: Description and Acceptance criteria above.
- React flow (`frontend/src/features/chat/MessageList.tsx`):
  - `UserTurn.save(regenerate)` calls `chatsApi.editMessage(chatId, turn.id, draft)` (`frontend/src/api/chats.ts:27`), then `onRegenerate(turn.id, draft)`.
  - `onRegenerate` is `regenerateFrom` (line 385), which calls `sendTurn({ text, files: [], history, userTurnExists: true })`.
  - That posts to `/v1/chat/completions`, and `chat_completions` (`backend/chat/router.py:248`) persists every posted user message, so a second user row is added.
  - MYAI-6 moves Retry (`retry`, `retryLast`) to `resumeTurn` and leaves `regenerateFrom` only for this edit path.
- Edit route: `edit_message_endpoint` (`backend/chat/router.py:534`) passes `content` to `db.edit_message`.
  - `MessageOpsMixin.edit_message` (`backend/database/wrapper/message_ops.py:429`) runs `UPDATE messages SET content = ? WHERE id = ?` and truncates every later message.
  - The draft is the parsed text only (`parseUserContent` in `frontend/src/lib/chat-model.ts:37` joins text parts and drops `image_url` parts), so multimodal content becomes plain text and the images are lost.
  - The route doesn't check the message's role.
  - MYAI-11 (planned) scopes the edit to `chat_id`, returns 404 for a message from another chat and 400 for empty or whitespace-only content.
- Stored user content (`chat_completions`, router.py:270-330) is one of two forms:
  - a plain string, optionally ending with `\n\n[System Note: The user has attached the following files ...]`;
  - a JSON list of a text part (with that note appended) plus `image_url` parts.
- After an edit truncates later messages, the edited user message is the last one, so `/api/chats/<id>/resume` (`resume_chat`, router.py:447) regenerates from it without storing a new row. MYAI-6's `resumeTurn` wraps that.
- Legacy UI (`static/script.js:2738-2760`): editing deletes the message (cascading) and sends a new one, so there's one user row (no duplicate). The legacy UI isn't changed (see Risks).
- Tests:
  - `backend/chat/tests/test_router.py::test_edit_message_endpoint` (line 314);
  - `backend/database/wrapper/tests/test_message_ops.py`;
  - `frontend/src/features/chat/MessageList.test.tsx`.
- Rules:
  - `docs/standards/api.md`: 403 for a forbidden operation, 404 not found, 400 invalid input; body `{"error": ...}`.
  - `docs/standards/python.md`: docstrings and hints.
  - `docs/standards/testing.md`: separate pytest processes per suite; env vars.
  - `docs/standards/frontend.md`.

### Approach
- **Merge the edit server-side.** Add a pure helper `merge_edited_user_content(old_content: str, new_text: str) -> str` in a new module `backend/chat/message_edit.py`:
  - If `old_content` parses as a JSON list, replace the first text part's text with `new_text` (inserting a text part if there is none), keep every other part in order, and re-serialise.
  - Otherwise use `new_text`.
  - In both cases, if the old text ended with a `[System Note: ...]` block and `new_text` doesn't contain one, re-append that block. The model then still gets the file ids, and this keeps working once MYAI-21 hides the note from the draft.
- **Role check.** Add a read method `get_message(chat_id: str, message_id: int) -> dict | None` to `MessageOpsMixin`, returning `role` and `content` for a message in that chat. In `edit_message_endpoint`:
  - Fetch it. If it's None, return 404 (consistent with MYAI-11).
  - If `role != "user"`, return 403 `{"error": "Only user messages can be edited"}`.
  - Otherwise compute the merged content and call `db.edit_message`.
  MYAI-11's validation (string, not whitespace-only) runs before this.
- **Regenerate via resume.** In `UserTurn.save(true)`, after a successful edit, call MYAI-6's `resumeTurn(queryClient, chatId)` instead of `onRegenerate`. Remove `regenerateFrom` and the `onRegenerate` prop if nothing else uses them after MYAI-6; otherwise leave them.
- Rejected alternatives:
  - Send the images again from the client: the client only has data URLs from parsing, not the file ids, and resending would duplicate the row anyway.
  - Merge in `edit_message` inside the transaction: it mixes content rules into the DB layer, and MYAI-11 is already restructuring that method.

### Steps
#### Step 1: Merge helper
- **Files:** `backend/chat/message_edit.py` (create): `merge_edited_user_content`, plus the module and function docstrings.
- **Change:** as in Approach.
  - Content is multimodal only if it parses as a JSON list whose items are all dicts. Invalid JSON, a non-list value, or a list containing non-dicts (for example `["a"]`) is plain text.
  - Note handling always works on decoded text, never on the raw JSON string. In the multimodal case, it works on the first text part's `text` after parsing (the router appends the note there, router.py:304, 321), then re-serialises. In the plain case, it works on the string itself.
  - The note is the last occurrence of `\n\n[System Note:` running to the end of that text.
  - The plain path is a pure replacement: `new_text` as is, plus the re-appended note.
- **Verification:** Step 4 unit tests.

#### Step 2: `get_message` in the wrapper
- **Files:** `backend/database/wrapper/message_ops.py` (modify): new `get_message(chat_id, message_id)`, with a docstring and type hints.
- **Change:** a parameterised `SELECT id, role, content FROM messages WHERE id = ? AND chat_id = ?`, returning a dict or None. Same connection pattern as `get_last_assistant_message`.
- **Verification:** Step 4 wrapper tests.

#### Step 3: Edit route checks role and merges
- **Files:** `backend/chat/router.py` (modify): `edit_message_endpoint`.
- **Change:** as in Approach. Order:
  1. MYAI-11's body validation (400);
  2. `db.get_message` (404 if missing);
  3. role check (403);
  4. merge;
  5. `db.edit_message` (404 if it returns False, per MYAI-11).
  `edit_message`'s own chat-scoped check (MYAI-11) stays the authority. The pre-read is only for the role check and the merge, so step 5's 404 is still reachable (for example, the message was deleted in between) and is kept.
  Log 403s with `log_event("chat_edit_rejected_role", {"chat_id": ..., "message_id": ...})`. Log the step 2 404 with the same event MYAI-11 uses for its 404 (`chat_edit_message_not_found`).
- **Verification:** Step 4 router tests.

#### Step 4: Backend tests
- **Files:**
  - `backend/chat/tests/test_message_edit.py` (create);
  - `backend/database/wrapper/tests/test_message_ops.py` (modify);
  - `backend/chat/tests/test_router.py` (modify).
- **Change:**
  - Helper cases:
    - plain to plain;
    - plain with a note, edited without the note: the note is kept;
    - an edit that includes the note: no duplicate;
    - JSON list with images: the text is replaced and the images are kept in order;
    - JSON list with no text part: a text part is inserted;
    - invalid JSON: treated as plain.
  - Wrapper (real test DB, per the existing `conftest.py`): `get_message` returns the row for a matching chat, and None for a wrong chat or a missing id.
  - Router:
    - an assistant message gives 403 and `edit_message` isn't called;
    - a missing message gives 404;
    - a user message calls `edit_message` with the merged content;
    - update `test_edit_message_endpoint` so `mock_db.get_message.return_value = {"id": 1, "role": "user", "content": "old"}` and `edit_message` is asserted with the merged content (`"new content"`).
- **Verification:**
  - `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q backend/chat/tests backend/database/wrapper/tests/test_message_ops.py`
  - then `... -m pytest -q backend` (the parent suite, its own process).

#### Step 5: React regenerates via resume
- **Files:** `frontend/src/features/chat/MessageList.tsx` (modify): `UserTurn.save`; remove `regenerateFrom` and the `onRegenerate` prop. `frontend/src/features/chat/MessageList.test.tsx` (modify).
- **Change:**
  - `save(true)` calls `resumeTurn(queryClient, chatId)` after the edit succeeds; `save(false)` is unchanged.
  - Remove `regenerateFrom` and the `onRegenerate` prop. After MYAI-6 moves Retry to resume and this step moves the edit path, nothing uses them.
  - A failed edit still shows the toast and doesn't regenerate.
  - Tests:
    - Save & regenerate calls `editMessage`, then `resumeTurn`, and never `sendTurn`.
    - Save only calls `editMessage` and not `resumeTurn`.
    - An edit failure gives a toast and no `resumeTurn`.
- **Verification:** `cd frontend && npm run typecheck && npm run lint && npm run test`.

#### Step 6: Docs
- **Files:**
  - `docs/standards/api.md`: no change, since 403 is already defined.
  - `backend/chat/README.md` (modify): add a `message_edit.py` row to the Core Files table, and add a Flow item 6, **Edits**: `PUT /api/chats/<id>/messages/<id>` edits user messages only, keeping images and the attachment note via `merge_edited_user_content`.
  - `backend/database/wrapper/README.md`: no change (it lists mixins, not methods).
- **Verification:** `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q tests` (docs guardrails, its own process).

#### Step 7: Full gate and live check
- **Change:**
  - Run `venv/bin/ruff check .` and `scripts/check.sh`.
  - Live check with a throwaway `DATA_DIR` (if a compose stack is used: in a /tmp copy, strip `container_name:` and `ports:`, prefix every `image:` with a unique verify name, and repoint host-absolute binds such as `/home/archit-anand/docker-data/shared/...` to /tmp, as in MYAI-17 Step 7), driving the React UI with Playwright:
    - L1: send a message with an image and a PDF, wait for the reply, then Edit, change the text and Save & regenerate. The DB has one user row with the new text, the `image_url` part and the System Note. A new reply arrives. After a reload, the image chip still shows.
    - L2: `PUT` an edit on an assistant message id gives 403.
- **Verification:** all pass; results go in Verification.

### Tests
- Preconditions: a `venv` with `requirements.txt` and `requirements-dev.txt`; `npm ci` in `frontend/`.
- `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q backend`, then the same with `tests`.
- `cd frontend && npm run typecheck && npm run lint && npm run test`
- `venv/bin/ruff check .`, then `scripts/check.sh`
- Live checks L1-L2

### Risks and open questions
- **Ordering.** Land this after MYAI-11 (same route and wrapper method) and MYAI-6 (`resumeTurn`). Without MYAI-6, Step 5 can't use resume. In that case, block this step rather than keep `sendTurn`.
- **Legacy UI unchanged.** Its edit deletes the message and sends a new one, so there's no duplicate row, but images are lost unless re-attached. Out of scope; noted as a known gap.
- **"Allowed roles".** Only `user` can be edited, which is the AC's default. The React UI only offers Edit on user turns.
- **Overlap with MYAI-21.** MYAI-21 hides the note in the UI. This plan re-appends the note on edit, so the two compose.
- No blocking open questions.

### Success criteria
- [ ] Save & regenerate leaves one user row with the edited text (Step 5, L1)
- [ ] Images and the attachment note on the edited message are kept (Steps 1 and 4, L1)
- [ ] Editing a non-user message returns 403 (Steps 3-4, L2)
- [ ] Regeneration produces a reply (L1)
- [ ] Docs updated; all checks pass

### Validation log
- Round 1 (2026-11-09, Haiku): FAIL, 1 BLOCKING and 9 MINOR. My judgement: PASS after fixes. The BLOCKING item is disproved, and all 9 minors are valid and applied.
  - B1: `backend/chat/tests` and the wrapper tests in one process breaks the testing.md:48 rule. Disproved: suites are the top-level rows in testing.md's table (`pytest backend`, `pytest tests`, ...), and both paths are inside the `backend` suite, which check.sh runs as one process. No change.
  - M2: note handling on JSON text. Fixed: it works on the decoded first text part.
  - M3: lists of non-dicts. Fixed: treated as plain.
  - M4: conditional removal of `regenerateFrom`. Fixed: always removed.
  - M5: MYAI-17 reference. Fixed: isolation rules inlined.
  - M6: 404 not logged. Fixed: same event as MYAI-11.
  - M7: authority between pre-read and edit. Stated.
  - M8: test mock shape. Specified.
  - M9: plain-text scope. Stated as a pure replacement.
  - M10: README Flow location. Named Flow item 6.
  Marked Validated: no valid BLOCKING and all minors applied.

## Implementation notes
### Autopilot run (2026-11-09)
- Mode: automatic (batch-autopilot batch 2, item 2/3)
- Branch: bugfix/edit-regenerate-keeps-user-row  PR base: develop  Starting commit: 6307ffb
- Dirty before start: none
- Work files: backend/chat/message_edit.py, backend/chat/tests/test_message_edit.py, backend/chat/router.py, backend/chat/tests/test_router.py, backend/chat/README.md, backend/database/wrapper/message_ops.py, backend/database/wrapper/tests/test_message_ops.py, frontend/src/features/chat/MessageList.tsx, frontend/src/features/chat/MessageList.test.tsx
- Counters: fix 0/10, review 1/5, re-verify 1
- Last completed stage: 6 ship  Next: none
- Hard blocker: none
- WIP commit: none

### Autopilot decisions (2026-11-09)
- Stage 1: plan already Validated (1 round); reused, not re-planned. Written against 6a13e04; develop is now 6307ffb with MYAI-6/10/11 merged, so the plan's "MYAI-11 (planned)" and "MYAI-6" items now exist in the code.

### Baseline (2026-11-09)
At develop 6307ffb: backend/chat/tests 113 pass; backend/database/wrapper/tests 72 pass; frontend vitest 276 pass (48 files). Other backend suites fail only on async tests (pytest-asyncio not installed in the venv): database/tests 2, tools/tests 6, research_agent 2, tavily_mcp 5, code_runner_mcp.

### Implementation progress
- [x] Step 1: merge helper - backend/chat/message_edit.py (`merge_edited_user_content`)
- [x] Step 2: `get_message` - backend/database/wrapper/message_ops.py
- [x] Step 3: edit route role check + merge - backend/chat/router.py (404 / 403 `Only user messages can be edited` / merged content)
- [x] Step 4: backend tests - backend/chat/tests/test_message_edit.py (new), test_router.py, database/wrapper/tests/test_message_ops.py
- [x] Step 5: React Save & regenerate resumes - frontend/src/features/chat/MessageList.tsx (+ tests); `regenerateFrom`, `historyBefore` and the `onRegenerate` prop removed
- [x] Step 6: docs - backend/chat/README.md
- [x] Step 7: full checks (see Smoke test); live check is the verify stage
Branch: bugfix/edit-regenerate-keeps-user-row

### Smoke test (2026-11-09)
chat 125 pass; database/wrapper 73; backend/tests 25; tests 32; ruff clean; `scripts/check.sh --python-only`: only the baseline async-plugin failures; frontend vitest 279 pass, typecheck clean, lint only the existing forms.tsx warning, build ok.

PR: https://github.com/archit342000/My-AI/pull/59, branch bugfix/edit-regenerate-keeps-user-row, base develop

## Verification
### Verification plan (2026-11-09, light form: 3 runtime source files, new helper module, React flow)
**Diff base:** origin/develop 6307ffb. **Scope:** edit route (user-only, merge keeps images and attachment note), `get_message`, React Save & regenerate via `/resume`. Out of scope: legacy UI, MYAI-21 (hiding the note), the unclaimed `/resume`.
**Environment and isolation:** real Flask app from this branch on 127.0.0.1:5099 with the built React frontend, `DATA_DIR=/tmp/myai20-data` (fresh DB), `AI_PROXY_URL=http://127.0.0.1:5098` (fake inference proxy, fast mode, logs every upstream request body). Never touch :5000/:5001, containers or `backend/data`. Teardown: kill both PIDs, delete the temp dir, compare ports/containers/git status to the snapshot.
Scripts: `scripts/fake_proxy.py` (copy of the MYAI-6 one), `scripts/v20_api.py` (API + DB checks), `scripts/ui.js` (Playwright).

| ID | Criterion | Scenario | Type | Method | Files | Expected |
|----|-----------|----------|------|--------|-------|----------|
| V1 | One user row; images and attachments kept; reply produced | React UI: send a message with an image and a text file, wait for the reply, Edit the text (draft without the note), Save & regenerate | happy | browser + DB + upstream log | MessageList.tsx, message_edit.py, router.py | exactly one user row; its content has the edited text, the System Note and the image_url part; `attachments` still there; one new assistant reply; upstream last request holds the edited text, the file note and the image part; the file chip shows after a reload |
| V2 | Edits limited to user messages | PUT an edit on an assistant message id | failure | API + DB | router.py, message_ops.py | 403 `{"error": "Only user messages can be edited"}`; content unchanged |
| V3 | Chat scoping | PUT with a message id from another chat | failure | API + DB | router.py | 404 `{"error": "Message not found"}`; both chats unchanged |
| V4 | Validation | PUT empty and whitespace-only content | edge | API | router.py | 400 `{"error": "Content required"}`; unchanged |
| V5 | Plain edit | chat without files: edit the first of two turns | regression | API + DB | message_edit.py | content exactly as sent, later messages removed |
| V6 | Save without regenerate | React UI: Edit and Save (not regenerate) | happy | browser + DB | MessageList.tsx | one user row with the edited text, the old reply removed, no new upstream request |
| V7 | Regression | chat, wrapper, backend, tests dirs, ruff, vitest, typecheck, lint, build | regression | CLI | all | only baseline failures |

### Results (2026-11-09)
Verified at HEAD 6307ffbd5f06dd63c98a6b99075723386261e158 plus uncommitted (hash prefixes): backend/chat/README.md 68b69963, backend/chat/message_edit.py 43465c6e, backend/chat/router.py d435c191, backend/chat/tests/test_message_edit.py 9921efa1, backend/chat/tests/test_router.py 68da1b00, backend/database/wrapper/message_ops.py 94c0d8ab, backend/database/wrapper/tests/test_message_ops.py 27bd2e7c, frontend/src/features/chat/MessageList.test.tsx d2c16a71, frontend/src/features/chat/MessageList.tsx 8420d7da.
Isolation: app 127.0.0.1:5099 (DATA_DIR=/tmp/myai20-data, built React frontend), fake inference proxy 127.0.0.1:5098; :5000/:5001, containers and backend/data untouched. Teardown: both PIDs killed, 5098/5099 free, temp dir removed, containers and git status identical to the snapshot.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | v1-v6-ui.log, ui-v1-*.png: image + text file sent, edited to "describe these in one sentence", Save & regenerate: 1 user row, its content has the edited text, the System Note and the image_url part, `attachments` kept, 1 assistant reply, exactly one new upstream request holding the edited text, file note and image part; chips pic.png and notes.txt after a reload |
| V2 | PASS | v2-v5.log: edit on an assistant message id gave 403 `{"error": "Only user messages can be edited"}`, rows unchanged |
| V3 | PASS | v2-v5.log: message id from another chat gave 404, both chats unchanged |
| V4 | PASS | v2-v5.log: empty and whitespace-only content gave 400, unchanged |
| V5 | PASS | v2-v5.log: plain edit stored exactly as sent, later messages removed, other chat untouched |
| V6 | PASS | v1-v6-ui.log, ui-v6-after-save.png: Save without regenerate: 1 user row with the edited text, reply removed, no new upstream request |
| V7 | PASS | v7-regression.log: chat 125, wrapper 73, backend/tests 25, tests 32, ruff clean; vitest 279, typecheck clean, lint only the existing warning |

Verdict: verified. 7 of 7 pass, 0 FAIL, 0 BLOCKED. Browser console errors: none.
**Found, pre-existing, not fixed here:** a user message that has an image shows `[object Object],[object Object]` as its text in the React UI even without any edit (preexisting-image-render.log, ui-preexisting-image-message.png). `GET /api/chats/<id>` returns multimodal content as a decoded list, and `toTurns` runs `String()` on it (`clean()` in frontend/src/lib/chat-model.ts, untouched by this ticket), so `parseUserContent` never sees the JSON. Consequence for this ticket: the edit box for an image message opens with that garbage text (V1 replaced the whole draft). The images and the note are still kept server-side, but saving without retyping would store the garbage as the text. Added to the follow-up ticket.
Not covered: the legacy UI (out of scope), PDF attachments.
Scripts: scripts/fake_proxy.py, v20_api.py, ui.js, ui_preexisting.js.
### Results (re-run 1, 2026-11-09)
Re-run after review round 1 fixes (message_edit.py multimodal detection, annotation, tests). HEAD 6307ffbd5f06dd63c98a6b99075723386261e158 plus uncommitted (hash prefixes): backend/chat/README.md 68b69963, backend/chat/message_edit.py 6f26e520, backend/chat/router.py d435c191, backend/chat/tests/test_message_edit.py bb22e0fb, backend/chat/tests/test_router.py 9a7bdb5b, backend/database/wrapper/message_ops.py d8af2747, backend/database/wrapper/tests/test_message_ops.py 27bd2e7c, frontend/src/features/chat/MessageList.test.tsx d2c16a71, frontend/src/features/chat/MessageList.tsx 8420d7da. Frontend rebuilt first; fresh throwaway state (app 5099, fake proxy 5098); ports free afterwards, containers and git status identical to the snapshot. Evidence in rerun1/.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | rerun1/v1-v6-ui.log: one user row with the edited text, System Note and image part kept, `attachments` kept, one reply, one upstream request with text + note + image, chips after reload |
| V2 | PASS | rerun1/v2-v5.log |
| V3 | PASS | rerun1/v2-v5.log |
| V4 | PASS | rerun1/v2-v5.log |
| V5 | PASS | rerun1/v2-v5.log |
| V6 | PASS | rerun1/v1-v6-ui.log |
| V7 | PASS | rerun1/v7-regression.log: chat 134, wrapper 73, backend/tests 25, tests 32, ruff clean; vitest 279, typecheck clean, lint only the existing warning |

Verdict: verified. 7 of 7 pass, 0 FAIL, 0 BLOCKED. Browser console errors: none. The pre-existing `[object Object]` rendering of image messages (see the first Results) is unchanged and tracked in the follow-up ticket.

## Review history
### Round 1 - 2026-11-09
Verdict: Request changes (2 MAJOR). Scope: 9 files vs 6307ffb (7 modified, 2 new; small mode, one Haiku reviewer given the Description, Acceptance criteria and the plan's Objective/Approach/Out of scope/Success criteria). Findings checked against the code; R1-1 reproduced by calling the helper.
- R1-1 [MAJOR] backend/chat/message_edit.py `_parse_parts` - a plain user text that is itself a JSON list of objects is treated as multimodal: `merge('[]', 'hello')` gives `[{"type": "text", "text": "hello"}]` and `merge('[{"a": 1}]', 'hello')` keeps the junk part - Confirmed - Fixed: only a non-empty list of objects typed text/image_url is multimodal (tests written first and failed before the fix), message_edit.py, test_message_edit.py
- R1-2 [MAJOR] backend/database/wrapper/message_ops.py:120 - new public `get_message` has no return annotation (docs/standards/python.md: annotate every new public function) - Static - Fixed: `-> dict | None`, message_ops.py
- R1-3 [MINOR] backend/chat/message_edit.py:4 vs backend/chat/router.py (two literals) - the note prefix is defined separately in the router and in the helper; if one changes, edits silently drop the note and the tests (hand-typed note) would not notice - Static - Fixed: completion tests assert the stored note contains message_edit.NOTE_MARKER so drift fails a test, test_router.py
- R1-4 [MINOR] backend/chat/message_edit.py - the merge replaces only the first text part while the editor draft joins all text parts; the router only ever writes one text part, so document the assumption - Static - Fixed: docstring states the single-text-part assumption, message_edit.py
- R1-5 [MINOR] backend/chat/tests - missing cases: None stored content, plain content shaped like a JSON list (R1-1), image before the text part, a user-typed second note marker - Static - Fixed: tests for plain JSON-shaped text, None content (helper and route), image before the text part, a user-typed note marker
- R1-6 [NIT] backend/chat/message_edit.py `_with_note` docstring is unclear ("empty of one already") - Static - Fixed: `_with_note` docstring reworded
- R1-7 [NIT] backend/chat/tests/test_router.py - the `USER_ROW` constant sits between two tests - Static - Fixed: USER_ROW moved to the top of test_router.py
Deferred (valid, not fixed here):
- R1-8 [MINOR] frontend/src/features/chat/send-turn.ts - `history` and `userTurnExists` are now unused by production code (only their tests use them) after `regenerateFrom` was removed - Deferred: removing them touches `sendTurn`/`consume` that the open one-turn-per-chat PR also edits; do it as a follow-up cleanup
- R1-9 [MINOR] backend/chat/router.py edit_message_endpoint - the content is read before the edit transaction, so a write to the same message in between would be overwritten with stale images/note - Deferred: accepted by the plan (pre-read only for the role check and merge, `edit_message` stays the authority); low reach for a single-user app, would need an expected-content check in `edit_message`
Dismissed: none.

Resolution: 7 Fixed, 0 Rejected, 2 Deferred (R1-8 unused `history`/`userTurnExists` options of `sendTurn`: cleanup after the open one-turn-per-chat PR lands; R1-9 stale pre-read in the edit route: accepted by the plan, low reach). Runtime behaviour changed by R1-1 (backend/chat/message_edit.py): live re-verify of V1 and V5 needed. Checks: chat 134, wrapper 73, backend/tests 25, tests 32, ruff clean (frontend untouched in this round: vitest 279 earlier).


## Log
- 2026-11-09: created (follow-up found while planning MYAI-2 to MYAI-16)
- 2026-11-09: plan validated, 1 Haiku round.
- 2026-11-09: linked blocked_by MYAI-11 (builds on MYAI-11's chat-scoped edit_message and empty-content 400)
- 2026-11-09: linked blocked_by MYAI-6 (Save & regenerate uses MYAI-6's resumeTurn)
- 2026-11-09: linked blocks MYAI-21 (the stripped draft relies on MYAI-20 re-appending the note on edit)
- 2026-11-09: linked conflicts_with MYAI-22 (edit_message_endpoint body read)
- 2026-11-09: linked relates_to MYAI-43 (batch 1 follow-ups)
- 2026-11-09: autopilot started (batch-autopilot)
- 2026-11-09: implemented, smoke tests pass (only baseline async-plugin failures)
- 2026-11-09: verified: 7 PASS, 0 FAIL, 0 BLOCKED; found pre-existing [object Object] text for image messages (added to MYAI-43)
- 2026-11-09: review round 1: Request changes (2 MAJOR, 3 MINOR + 2 deferred MINOR, 2 NIT)
- 2026-11-09: review round 1 resolved: 7 fixed, 2 deferred; message_edit.py changed, re-verify needed
- 2026-11-09: re-verified after review fixes: 7 PASS, 0 FAIL, 0 BLOCKED
- 2026-11-09: PR opened #59 (batch-autopilot: shipped, base develop)
- 2026-11-09: linked relates_to MYAI-44 (batch 2 follow-ups)
- 2026-11-09: PR #59 merged into develop; closed
