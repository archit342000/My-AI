---
id: MYAI-44
title: "Follow-ups from batch 2 (PRs #58-#60): sendTurn cleanup, edit race, /resume claim, Retry on other tabs"
status: todo
created: 2026-11-09
updated: 2026-11-09
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
Not planned yet. Items 1-6 are independent. Items 3 and 4 belong together; item 1 should wait for PRs #58 and #59.

## Implementation notes

## Verification
Not run yet.

## Review history
None yet.

## Log
- 2026-11-09: created from the batch 2 findings (PRs #58, #59, #60)
