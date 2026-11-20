---
id: MYAI-44
title: "Follow-ups from batch 2 (PRs #58-#60): sendTurn cleanup, edit race, /resume claim, Retry on other tabs"
status: todo
created: 2026-11-09
updated: 2026-11-20
links:
  relates_to: [MYAI-7, MYAI-20, MYAI-24, MYAI-43]
---

## Description
Gaps found while shipping MYAI-7 (one turn per chat, PR #58), MYAI-20 (edit keeps images and one user row, PR #59) and MYAI-24 (drop the counter table, PR #60). None block those PRs. The image-message `[object Object]` rendering found in the same batch is item 5 of MYAI-43.

1. **Unused `sendTurn` options.** After MYAI-20 removed `regenerateFrom`, nothing in production passes `history` or `userTurnExists` to `sendTurn` (frontend/src/features/chat/send-turn.ts, `SendArgs`); only send-turn.test.ts uses them. Remove both options, their branch (the optimistic "pending" row logic keyed on `userTurnExists`) and the tests that exercise them. Deferred from the MYAI-20 review (R1-8) because MYAI-7's PR also edits `sendTurn`/`consume`; do it after #58 and #59 are merged.
2. **Edit route reads stale content.** `edit_message_endpoint` (backend/chat/router.py) reads the stored message with `db.get_message`, merges the new text into it, then calls `db.edit_message`. A write to the same message between the two (another tab editing it) is overwritten with the older images and note. Fix: pass the expected old content to `edit_message` and fail with 409/404 when it changed, or do the merge inside the edit transaction. Low reach for a single-user app; deferred from the MYAI-20 review (R1-9).
3. **`/resume` is not claimed.** `resume_chat` (backend/chat/router.py) does not use `claim_turn`, so a Resume (Retry, and now Save & regenerate) racing a send can still start first and the send then attaches to it. Claim the turn slot in `resume_chat` and return the same 400 `a response is already in progress`; the React `resumeTurn` then needs the same toast-only handling for that 400 that `sendTurn` has. Known limit of MYAI-7.
4. **A tab that did not start the turn offers "Retry response" under the in-flight user message.** `showUserRetry` in MessageList.tsx is true when the last user turn has no reply and nothing is streaming in this tab, so in a second tab the button appears while another tab's turn is running; clicking it calls `/resume` (see item 3). Hide it while the chat is running server-side (`is_running` from the chat detail) or until item 3 makes the server refuse it.
5. **Rejected-send UX.** After the 400 for a send during a running turn, the typed draft is cleared and not restored (MYAI-7 known limit). Restore the composer text when `sendTurn` is refused with a 400.
6. **Brief refusal after Stop or after a turn ends.** A send right after Stop, or right after the last chunk, can get the 400 for a few milliseconds because the worker thread is still alive (`is_task_running`). Option: have the router wait briefly for the worker to finish, or release/refresh on task end. Only worth doing if users hit it.

## Acceptance criteria
- [ ] `sendTurn` has no unused options and its tests match
- [ ] An edit never overwrites a concurrent change to the same message
- [ ] `/resume` refuses with the same 400 while a turn runs or is starting, and the client shows it as a toast
- [ ] Retry is not offered under an in-flight user message in a tab that did not start the turn
- [ ] A refused send keeps the typed draft (or the decision to keep it cleared is recorded)

## Plan

**Date:** 2026-11-20  **Status:** Validated

### Objective
Close the batch 2 follow-ups that are still open: remove `sendTurn`'s dead options, make a message edit fail instead of overwriting a concurrent change, and stop offering "Retry response" in a tab while the chat's turn runs elsewhere. Record the items that later work already fixed.

### Context
- Requirement: this ticket's six items and five acceptance criteria.
- Already done on develop (no code needed, verified by existing tests):
  - Item 3: `resume_chat` (`backend/chat/router.py`) claims the turn (`task_manager.claim_turn`) and answers `400 {"error": "a response is already in progress"}`; React `resumeTurn` shows it as a toast only (`frontend/src/features/chat/send-turn.ts` `consume`). Tests: `backend/chat/tests/test_router.py` `test_resume_chat_rejected_when_turn_in_progress`; `send-turn.test.ts` "shows the turn-in-progress refusal as a toast only, no inline error row".
  - Item 5: a send refused with 400/429 puts the text and files back (`frontend/src/features/composer/Composer.tsx` `onRefused`); tests in `Composer.test.tsx` ("puts the sent text back after the server refuses it…", "keeps the text and files when the send is refused"); `docs/frontend.md` documents it.
- Item 1: `SendArgs.history` and `SendArgs.userTurnExists` (`send-turn.ts`) are passed only by `send-turn.test.ts`; the only production caller is `Composer.tsx` `send()`. Retry and regenerate use `resumeTurn`.
- Item 2: `edit_message_endpoint` (`backend/chat/router.py`, PUT/PATCH `/<chat_id>/messages/<int:message_id>`) reads `db.get_message`, merges with `merge_edited_user_content` (`backend/chat/message_edit.py`), then calls `db.edit_message` (`backend/database/wrapper/message_ops.py`), which writes under `BEGIN IMMEDIATE` but only re-checks existence. Compare-and-set precedent: `chat_ops.py` `mark_chat_temporary` (conditional UPDATE, `rowcount`). Frontend: `chatsApi.editMessage` (`frontend/src/api/chats.ts`) from `UserTurn.save` in `frontend/src/features/chat/MessageList.tsx`, which toasts any error and keeps the editor open.
- Item 4: `showUserRetry` in `MessageList.tsx` ignores the server's `is_running`; `ChatPage.tsx` uses `data.is_running` only to reattach and does not pass it to `MessageList`. `GET /api/chats/<id>` returns `is_running` (`backend/chat/handler.py` `get_history`).
- Item 6 has no acceptance criterion; a send right after a normal turn end is not retried (`openAfterStop` only retries after a stop).
- Rules: `docs/standards/api.md` (status codes; `409` conflict; error body), `docs/standards/errors-and-logging.md` (plain messages, `log_event`), `docs/standards/testing.md`, `docs/standards/frontend.md`, `AGENTS.md` (db layer only).

### Approach
- Item 1: delete both options and the code that reads them; `sendTurn` always builds history from the cache and always shows the optimistic user row. Delete the two F-16 tests that only exercise the options and drop `history` from the numbering test.
- Item 2: compare-and-set inside the existing edit transaction. `db.edit_message` takes an optional `expected_content`; inside `BEGIN IMMEDIATE` it re-reads the row and, when the stored content differs, raises a new `MessageChangedError` (database layer) without its own `ROLLBACK`: the function's existing `except Exception: ROLLBACK; raise` handler rolls back once and re-raises it. The router passes the content it merged from and answers `409 {"error": "This message has changed. Review it and try again."}` with a `log_event`. The frontend invalidates the chat query on a 409 (`docs/standards/frontend.md`: "Invalidate, do not refetch by hand") and shows the server's message, keeping the editor open. Rejected: merging inside the transaction (moves `message_edit` logic into the db layer).
- Item 4: `ChatPage` passes `running={!!data?.is_running}` to `MessageList`; `showUserRetry` is false while `running` is true. When that turn ends this tab either reattached to it (then it streams here) or the next chat refetch clears the flag.
- Items 3 and 5: recorded as done; no change. Item 6: out of scope.

### Out of scope
- Item 6 (retrying a send made in the milliseconds after a normal turn end): no criterion, and no report of users hitting it.
- Refusing an edit while a turn is running (not asked).
- Retry under an assistant reply (`retry()`), which is MYAI-43 item 2.

### Steps
#### Step 1: Remove `history` and `userTurnExists` from `sendTurn`
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/features/chat/send-turn.ts` (modify: `SendArgs`, `sendTurn`); `frontend/src/features/chat/send-turn.test.ts` (modify)
- **Change:** remove both fields and their branches (the uncached-chat check runs always; `pending` is always built). Remove the tests "streams without an optimistic pending user when the turn already exists" and "regenerate sends the edited turn once…", and seed the cache instead of passing `history` in "numbers the pending user turn…".
- **Verification:** `npm run typecheck` (no caller passes the options), `npm run test` passes; `grep -n "userTurnExists" frontend/src` finds nothing.

#### Step 2: Compare-and-set in `edit_message`
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/database/wrapper/message_ops.py` (modify: `edit_message` and its docstring, new `MessageChangedError`); `backend/database/__init__.py` (modify: `from .wrapper.message_ops import MessageChangedError`, added to `__all__`); `backend/database/wrapper/tests/test_message_ops.py` (modify)
- **Change:** optional `expected_content: Optional[str] = None`; when given, inside the existing `BEGIN IMMEDIATE`, the existence query also selects `content`, and the stored `content` (`None` treated as `""`) is compared with it; on a mismatch raise `MessageChangedError` (no inner `ROLLBACK`; the existing outer handler rolls back and re-raises, so the caller sees `MessageChangedError`, not an `OperationalError`). Without the argument the behaviour is unchanged.
- **Verification:** tests: matching content edits as before; a changed content raises `MessageChangedError` (`pytest.raises(MessageChangedError)`, not a broad `Exception`), and the message, later messages and collections are untouched; omitted argument unchanged; existing edit tests pass.

#### Step 3: 409 from the edit route
- **Status:** todo
- **Depends on:** Step 2
- **Files:** `backend/chat/router.py` (modify: `edit_message_endpoint`); `backend/chat/tests/test_router.py` (modify)
- **Change:** import `MessageChangedError` from `backend.database` (re-exported there, Step 2; `log_event` and `error_detail` are already imported in the router); pass `expected_content=existing.get("content") or ""` (the value the merge used); `except MessageChangedError as e` → `log_event("chat_edit_message_conflict_error", {"chat_id", "message_id", "error": error_detail(e)})` and `409` with the fixed message. Update the `assert_called_with("chat1", 1, ...)` in `test_edit_message_endpoint` and `test_edit_message_endpoint_handles_missing_stored_content` for the new argument.
- **Verification:** route test: `edit_message` raising `MessageChangedError` gives 409 with that body; a real-db test (temp db) where `db.get_message` is patched with a side effect that updates the row before returning gives 409 and leaves the newer content; existing edit route tests pass.

#### Step 4: Frontend handling of the 409
- **Status:** todo
- **Depends on:** Step 3
- **Files:** `frontend/src/features/chat/MessageList.tsx` (modify: `UserTurn.save`); `frontend/src/features/chat/MessageList.test.tsx` (modify)
- **Change:** import `ApiError` from `../../api/client`; in `save`'s catch, first branch: `err instanceof ApiError && err.status === 409` → `queryClient.invalidateQueries({ queryKey: queryKeys.chat(chatId) })`, error toast with the server's message, `return` (editor stays open with the person's draft, nothing regenerates). Other errors keep today's handling after it.
- **Verification:** test: a 409 invalidates the chat query, toasts the message, does not call `resumeTurn`, keeps the editor open.

#### Step 5: Hide the user Retry while the chat runs elsewhere
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/features/chat/ChatPage.tsx` (modify: pass `running`); `frontend/src/features/chat/MessageList.tsx` (modify: prop and `showUserRetry`); `frontend/src/features/chat/MessageList.test.tsx`, `frontend/src/features/chat/ChatPage.test.tsx` (modify)
- **Change:** new optional `running` prop (default false); `showUserRetry` also requires `!running`.
- **Verification:** tests: last user turn without a reply and `running` true shows no Retry; `running` false shows it (existing test); ChatPage passes `is_running` from the chat detail; after a Stop in this tab the chat detail is refetched (`stopTurn` already invalidates it once `/stop` answers) and Retry shows again.

#### Step 6: Docs
- **Status:** todo
- **Depends on:** Steps 3, 4, 5
- **Files:** `docs/standards/api.md` (modify: 409 also covers an edit of a message that changed meanwhile), `backend/chat/README.md` (modify: Edits step), `docs/frontend.md` (modify: Retry hidden while the chat runs elsewhere; edit conflict reloads)
- **Change:** one line each, matching the behaviour above; `docs/frontend.md` (191 lines) stays under the 200-line budget.
- **Verification:** `pytest tests` passes, including `tests/test_docs.py` (line budget).

### Tests
- Backend: `pytest backend/database`, `pytest backend/chat`, then `pytest backend`, `pytest tests` (env vars per `docs/standards/testing.md`), `ruff check .`.
- Frontend (in `frontend/`): `npm run typecheck`, `npm run lint`, `npm run test`.
- `scripts/check.sh`.

### Risks and open questions
- A 409 is also returned when the same tab saves twice quickly against a stale read; the reload then shows the saved text, which is the intended outcome (the message wording does not blame another window).
- `is_running` is read from the chat detail. While it is true, `ChatPage`'s reattach effect attaches this tab to the running turn, and the end of that stream invalidates the chat, so the flag clears. If the reattach is skipped (this tab stopped a turn in the last 3 s), Retry stays hidden until the chat is next loaded.

### Success criteria
- [ ] `sendTurn` has no `history`/`userTurnExists` options and its tests match (Step 1)
- [ ] An edit whose message changed since it was read is refused with 409 and changes nothing (Steps 2-4)
- [ ] `/resume` refuses with the same 400 while a turn runs or is starting, shown as a toast (already on develop; existing tests)
- [ ] The user-bubble Retry is hidden while the chat's turn runs in another tab (Step 5)
- [ ] A refused send keeps the typed draft (already on develop; existing tests)
- [ ] `scripts/check.sh` passes

### Reviewer brief
- Objective: remove `sendTurn`'s dead `history`/`userTurnExists` options, refuse an edit whose message changed since it was read (409), and hide the user-bubble Retry while the chat's turn runs in another tab; items 3 and 5 are already on develop.
- Key decisions: compare-and-set inside `edit_message`'s existing `BEGIN IMMEDIATE` (`MessageChangedError`, re-exported from `backend.database`, raised without an inner ROLLBACK); the route answers 409 and logs with `error_detail`; the client invalidates the chat query on 409 and keeps the draft; `ChatPage` passes `is_running` to `MessageList` as `running`.
- Out of scope: item 6 (send right after a normal turn end), refusing edits while a turn runs, Retry under assistant replies (MYAI-43).
- Success criteria: as listed in the plan.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
Path: pair, Haiku validators, judged against the code.
- Round 1: both FAIL. Valid: double ROLLBACK would turn the conflict into an OperationalError (blocking); a 409 refetch by hand against docs/standards/frontend.md (blocking). Disproved: Retry staying hidden forever in another tab (the reattach effect streams the turn there and refreshes at its end). Minors fixed (test assertion, neutral wording, branch order, event name, import, dependencies, line budget).
- Round 2: L2 PASS; L1 FAIL. Valid: the conflict log must use `error_detail(e)` (blocking). Minors fixed (re-export, ApiError import, docstring, exact exception in tests, Stop test).
- Round 3 (scoped): both PASS. Minors fixed inline (existing test assertions named, existence query selects content, real-db conflict hook, draft kept).

## Implementation notes

## Verification
Not run yet.

## Review history
None yet.

## Log
- 2026-11-09: created from the batch 2 findings (PRs #58, #59, #60)
- 2026-11-20: plan validated, 3 rounds
