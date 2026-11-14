---
id: MYAI-73
title: "Stop and delete while a turn runs: wait for the server, keep the reply and the text"
status: done
epic: MYAI-53
created: 2026-11-10
updated: 2026-11-10
links:
  blocked_by: [MYAI-54, MYAI-56, MYAI-63]
  blocks: [MYAI-70]
  relates_to: [MYAI-74]
---

## Description
Races found with injected network latency (MYAI-52, Verification, "Race pass 2026-11-10": A-87 … A-91). After Stop the UI is ready again before the server has stopped: Retry or a new message is then refused ("a response is already in progress"), the stopped partial reply and the typed message are lost, and the screen can show replies the server has since rolled back. During the stop the live row and the "Stopped" row show together. A stale `is_running` flag makes the Stop button flash and drops the stopped reply when the chat is reopened. Deleting the chat that is streaming stops nothing.

Evidence and the scripts (`race.mjs`, `race2.mjs`) are in `~/.claude/tickets/My-AI/MYAI-52-evidence/`.

## Acceptance criteria
- [x] After Stop the chat stays busy ("Stopping") until the server has answered the stop request; only then are Retry and Send available
- [x] With the stop request delayed by 1.5s, Retry and a new message after Stop both start a turn; no "a response is already in progress" toast
- [x] After Stop the transcript matches the server (no rolled-back replies left on screen), with the stopped partial reply and Retry shown
- [x] The live row and the "Stopped" row are never shown together
- [ ] A send or Retry the server refuses keeps the stopped partial reply on screen and puts the typed text and files back in the composer
- [x] Reopening a stopped chat does not flash Stop and keeps nothing stale; a reattach shows Stop only when there is a stream to attach to
- [x] Deleting the streaming chat (or discarding a streaming temporary chat) stops its turn first; the home composer shows Send

## Plan
**Date:** 2026-11-10  **Status:** Validated

### Objective
Make Stop, Retry-after-Stop and delete-while-streaming follow the server's state instead of racing it, so nothing is refused, lost or shown stale on a slow connection.

### Context
- **Requirement:** this ticket's Description and Acceptance criteria (findings A-87 … A-91 in MYAI-52).
- **Rules:** `AGENTS.md` (run `scripts/check.sh`); the epic MYAI-53 Scope (backend or API changes are out of scope); `docs/standards/frontend.md` (UI state in Zustand stores, every file in `src/state/` has a Vitest test next to it, new user flows get a Playwright spec in `e2e/`); `docs/standards/api.md` (the refusal text "a response is already in progress" is part of the API contract).
- **Current code (`frontend/src/`):**
  - `features/chat/send-turn.ts`: `stopTurn` aborts the controller and then posts `chatsApi.stop`; `consume` catches the `AbortError`, calls `store.interrupt(...)`, and its `finally` refetches the chat and calls `finish()` without waiting for the stop request. `sendTurn` and `resumeTurn` call `start()`, and `consume` shows only a toast for a 400 with `TURN_IN_PROGRESS` or a 429. `reattachTurn` calls `start()` before `reattachStream` has answered (`api/completions.ts`: it returns `null` on a 204).
  - `state/stream-store.ts`: one slot (`chatId`, `live`, `pending`, `interrupted`, `controller`); `start()` clears `interrupted`. It has no test file.
  - `features/chat/MessageList.tsx` `MessageList`: renders `LiveAssistant` while the store's chat id is this chat and `InterruptedAssistant` when `interrupted` is set and no reply is persisted, so both show between `interrupt()` and `finish()`.
  - `features/chat/ChatPage.tsx`: the reattach effect runs when `data.is_running` is true and nothing is streaming.
  - `features/composer/Composer.tsx`: the Stop button calls `stopTurn()`.
  - `features/sidebar/RecentChats.tsx` `confirmDelete` and `features/chat/temporary-chat.ts` `discardTemporaryChat` call `chatsApi.remove` whatever the stream state.
- **Server facts (not changed):** `POST /api/chats/<id>/stop` (`backend/chat/router.py` `stop_chat`) signals the task and rolls the chat back to the last user message; `task_manager.stop_task` does not wait for the worker to exit, so a turn can count as running for a moment after the answer. `DELETE /api/chats/<id>` does not stop a running turn.
- **Legacy reference:** `static/script.js` (the stop handler around the `/stop` fetch): it awaits `/stop` and then reloads the chat.
- **Earlier tickets in this epic that change the same code (this plan builds on them):** MYAI-54 (one row per turn; `consume` keeps "refetch, then `finish()`"), MYAI-56 (`sendTurn` returns whether the turn started, takes `navigate` and `onAccepted`; Stop only in the streaming chat; one `<Composer />`), MYAI-63 (text of the Stop notice, resume banner).

### Approach
- **Stop waits for the server.** `stopTurn` sets a new store flag `stopping`, starts the stop request, aborts the controller, and keeps the request's promise in a module variable. `consume`'s `finally` awaits that promise before its refetch, so the refetch always follows the rollback and `finish()` (which clears `stopping`) follows both. If the stop request fails, a toast says the server did not confirm the stop, and the flow continues as today.
- **Busy while stopping.** While `stopping` is set the composer button is disabled with the label "Stopping", and the interrupted row's Retry is disabled until the store is idle. `MessageList` renders the live row only when the store has no `interrupted` turn for this chat, so the two are never shown together, whether the turn was stopped or failed.
- **Retry after Stop is not refused.** `stopTurn` records the stopped chat id and the time the stop was answered (module variables). When a send or resume for that chat within 3 seconds of that time is refused with `TURN_IN_PROGRESS`, `sendTurn`/`resumeTurn` repeat the request (up to 5 attempts, 400ms apart, the store staying busy) before treating it as a refusal. This covers the moment after the stop answer when the server still counts the old worker as alive, without a backend change.
- **A refused request loses nothing.** `sendTurn` and `resumeTurn` read the store's `interrupted` turn before `start()` clears it and pass it to `consume` as a new optional argument `restoreOnRefusal`; on the toast-only refusal path `consume` calls `interrupt(restoreOnRefusal)` when it is for this chat. `SendArgs` gains `onRefused`; the composer keeps the last sent text and files in a ref and restores them on `onRefused` when the box is still empty. This covers a refusal that remains after the repeats, and one caused by another tab.
- **Reattach starts only with a stream.** `reattachTurn` no longer calls `start()` first: it guards against a second concurrent call with a module-level set of chat ids, asks for the stream, and calls `start()` only when a source came back; on `null` it only refetches the chat. `interrupted` is therefore kept and Stop does not flash.
- **Delete stops first.** A new `stopIfStreaming(chatId)` in `send-turn.ts` calls `stopTurn()` when that chat is the one in flight and resolves once the store is idle. `confirmDelete` (chat target) and `discardTemporaryChat` await it before `chatsApi.remove`.
- **Rejected:** waiting for `is_running` to turn false by polling after Stop (needs repeated requests and the server gives no event for it); a per-chat stream store (a larger change; MYAI-56 keeps one turn at a time).

### Out of scope
- Backend changes: making `DELETE` stop the task, or `/stop` wait for the worker (see Risks).
- Stopping a turn before "Delete all chats": that button is added by MYAI-70, which calls `stopIfStreaming` (dated note in MYAI-70's Plan; MYAI-70 is blocked by this ticket).
- The doubled transcript at the end of a normal turn (A-14): MYAI-54. The create/fetch race on a new chat (A-11): MYAI-56.

### Steps
#### Step 1: Store flag and its tests
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/state/stream-store.ts` (modify: `stopping`, `setStopping`, reset in `start` and `finish`), `frontend/src/state/stream-store.test.ts` (create)
- **Change:** add the flag; `finish()` and `start()` clear it.
- **Verification:** unit tests for `start`, `update`, `interrupt`, `setStopping`, `finish` (the flag is false after `finish`; `start` clears `interrupted`).

#### Step 2: Stop order, refusal handling, reattach, `stopIfStreaming`
- **Status:** todo
- **Depends on:** 1
- **Files:** `frontend/src/features/chat/send-turn.ts` (modify: `stopTurn`, `consume` (new optional `restoreOnRefusal` argument), `sendTurn`, `resumeTurn`, `reattachTurn`, new `stopIfStreaming`, `SendArgs.onRefused`), `frontend/src/features/chat/send-turn.test.ts` (modify)
- **Change:** as in Approach ("Stop waits for the server", "Retry after Stop is not refused", "A refused request loses nothing", "Reattach starts only with a stream", `stopIfStreaming`). The fixtures in `src/test/fixtures/stream/` are recorded chunk sequences; this step changes the order of requests around a stream, not the chunks or how they are reduced, so the rule in `docs/standards/frontend.md` ("Streaming changes update the fixtures") has nothing to update here.
- **Verification:** unit tests: with the stop request pending, the chat is not refetched and the store stays busy; when it resolves the refetch runs and the store goes idle with `interrupted` set; a failed stop request shows the toast and still ends idle; a resume refused once with the in-progress text right after a stop is repeated and then streams with no toast; the same refusal more than 3 seconds after the stop answer is not repeated; refused on every attempt, or with no stop before it, it shows the toast and restores `interrupted` and a refused send calls `onRefused`; `reattachTurn` with a 204 never sets the store's chat id and keeps `interrupted`; two concurrent `reattachTurn` calls make one request; `stopIfStreaming` resolves at once for another chat and after idle for the streaming one.

#### Step 3: Transcript and composer
- **Status:** todo
- **Depends on:** 2
- **Files:** `frontend/src/features/chat/MessageList.tsx` (modify: `MessageList`, `InterruptedAssistant` gets a `busy` prop), `frontend/src/features/chat/MessageList.test.tsx` (modify), `frontend/src/features/composer/Composer.tsx` (modify: "Stopping" state of the button, `onRefused` restore), `frontend/src/features/composer/Composer.test.tsx` (modify)
- **Change:** as in Approach ("Busy while stopping", composer part of "A refused request loses nothing").
- **Verification:** component tests: with the store streaming and `interrupted` set (kind `stopped` and kind `error`), one bot row is shown and its Retry is disabled; once idle Retry is enabled; while `stopping` the button is disabled and named "Stopping"; after a refused send the textarea holds the sent text again, and it does not overwrite text typed meanwhile.

#### Step 4: Delete and discard stop the turn first
- **Status:** todo
- **Depends on:** 2
- **Files:** `frontend/src/features/sidebar/RecentChats.tsx` (modify: `confirmDelete`), `frontend/src/features/chat/temporary-chat.ts` (modify: `discardTemporaryChat`), `frontend/src/features/chat/temporary-chat.test.ts` (modify)
- **Change:** await `stopIfStreaming(id)` before `chatsApi.remove(id)` in both.
- **Verification:** unit test: discarding a temporary chat whose turn is in flight posts the stop before the delete; the sidebar path is covered by the spec in Step 5.

#### Step 5: End-to-end spec, docs, full checks
- **Status:** todo
- **Depends on:** 3, 4
- **Files:** `frontend/e2e/stop-races.spec.ts` (create), `docs/frontend.md` (modify: Streaming section: stop order, reattach rule, delete stops first)
- **Change:** a spec with mocked endpoints in the style of `e2e/chat-send.spec.ts`: the completion stream held open, `POST …/stop` delayed by 1.5s. Case 1: Stop, then Retry. Case 2: Stop, then a new message. Case 3: delete the streaming chat from the sidebar.
- **Verification:** the spec asserts: after Stop the button is "Stopping" and Retry is disabled until the stop answers; one bot row at all times; then Retry (case 1) and the new message (case 2) each post one request and no error toast appears; in case 3 the stop request is sent before the `DELETE` and the home composer shows Send. Then from `frontend/`: `npm run typecheck`, `npm run lint`, `npm run test`, `npm run build`; from the repo root `scripts/check.sh --frontend-only`. Live on the MYAI-52 rig (`~/.claude/tickets/My-AI/MYAI-52-evidence/scripts/`: `up.sh`, then `node race2.mjs SFN`): the timeline shows no refusal toast, no stale rows after Stop, no `/stream` Stop flash, and a `/stop` before the `DELETE`.

### Tests
- Unit: `state/stream-store.test.ts` (new), `features/chat/send-turn.test.ts`, `features/chat/temporary-chat.test.ts`.
- Component: `features/chat/MessageList.test.tsx`, `features/composer/Composer.test.tsx`.
- E2E: `e2e/stop-races.spec.ts`.

### Risks and open questions
- **Server keeps the old turn alive briefly after `/stop` answers** (`stop_task` only signals). Handled by the bounded repeat (5 attempts, 400ms apart). Nothing on the server bounds how long a worker takes to exit, so a slower exit still ends in the toast, with the reply and text kept; the acceptance criterion covers the delayed stop request, not this case. Only a server-side wait in `/stop` removes it (backend, outside this epic; raised to the owner in the epic's open points).
- **`DELETE` on the server does not stop a turn:** other clients (legacy UI, a second tab) can still leave a turn running for a deleted chat. Backend, outside this epic.
- **A stop request that never answers** keeps the chat in "Stopping" until the browser gives up on the request; `apiRequest` has no timeout of its own. Accepted: the state is truthful and a reload recovers.
- **Shared files:** `send-turn.ts`, `MessageList.tsx`, `Composer.tsx` are changed by MYAI-54, MYAI-56 and MYAI-63 first; this ticket is blocked by them and edits on top.

### Success criteria
- [ ] Busy ("Stopping") until the stop request is answered; then Retry and Send work with a 1.5s stop delay and no refusal toast
- [ ] Transcript after Stop matches the server; live and "Stopped" rows never together
- [ ] A refused send or Retry keeps the partial reply and restores the text and files
- [ ] No Stop flash when a stopped chat is reopened
- [ ] Deleting or discarding the streaming chat stops it first
- [ ] Checks and the new spec pass
### Reviewer brief
- **Objective:** Stop, Retry after Stop and delete-while-streaming follow the server's state, so nothing is refused, lost or shown stale on a slow connection.
- **Decisions:** `stopTurn` sets a `stopping` flag and `consume` waits for the stop request before its refetch and `finish()`; the composer shows a disabled "Stopping" button; the live row is rendered only when there is no interrupted turn for the chat, and Retry is disabled until idle; a send or resume refused as in-progress within 3 seconds of a stop is repeated (5 attempts, 400ms apart); a refusal restores the interrupted turn and, through `onRefused`, the composer's text and files; `reattachTurn` calls `start()` only when a stream came back; `stopIfStreaming(chatId)` runs before a chat delete and a temporary-chat discard. One turn at a time stays.
- **Out of scope:** backend changes (`DELETE` stopping the task, `/stop` waiting for the worker); "Delete all chats" (MYAI-70 calls `stopIfStreaming`); the doubled transcript at a normal end of turn (MYAI-54); the create/fetch race (MYAI-56).
- **Success criteria:** busy until the stop is answered, then Retry and Send work with a 1.5s stop delay and no refusal toast; transcript after Stop matches the server, live and "Stopped" rows never together; a refused send or Retry keeps the partial reply and restores text and files; no Stop flash on reopening; delete or discard stops the turn first; checks and the new spec pass.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- **Round 1 (Haiku): FAIL.** Judged FAIL. Valid BLOCKING: the plan accepted a refusal toast right after the stop answer (the server only signals the worker), against the second acceptance criterion; fixed with the bounded repeat. Valid MINOR, fixed: the no-backend rule is in the epic's Scope, not `AGENTS.md`; script path; `restoreOnRefusal` argument named; fixtures statement; "never both rows" now holds for failed turns too.
- **Round 2 (Haiku): FAIL.** Judged PASS. BLOCKING claim: the repeat cannot guarantee no toast because nothing bounds the worker's exit (`manager.py` `stop_task`, `claim_turn`). The facts are right, but the criterion is about a delayed stop request, which the plan meets; an unbounded worker exit is a different condition that only a backend change removes, and the epic excludes backend changes. Not blocking; the limit is now stated in Risks and raised to the owner. MINOR (valid, fixed inline): one repeat window (3 seconds, 5 attempts) with a test; the fixtures exemption is justified against the rule.

## Implementation notes
### Autopilot run (2026-11-10)
- Mode: automatic (batch)
- Branch: bugfix/stop-and-delete-while-running  PR base: bugfix/settings-dialogs-polish (stacked on PR #105)  Starting commit: e813e08
- Dirty before start: none
- Work files: state/stream-store(+test), chat/{send-turn,MessageList}(+tests), composer/Composer(+test), sidebar/RecentChats, chat/temporary-chat(+test), e2e/stop-races.spec.ts, docs/frontend.md
- Counters: fix 0/10, review 5/5, re-verify 5
- Last completed stage: 4 verify  Next: done (shipped)
- Hard blocker: none
- WIP commit: none

### Autopilot decisions (2026-11-10)
- Stage 1: ticket already holds a validated plan; skipped re-planning.
- The sidebar delete path has no component test of its own (the plan covers it through the e2e spec and the live check).
PR: https://github.com/archit342000/My-AI/pull/106, branch bugfix/stop-and-delete-while-running, base bugfix/settings-dialogs-polish

## Verification

### Acceptance review (2026-11-10)
Criteria ticked on the live and e2e results recorded in the PR's Testing section (checks run on throwaway backends during the autopilot run; scripts in `MYAI-73-evidence/`).
Left unticked, no PASS recorded:
- criterion 5: a send refused by the server: unit/component tests and the e2e mock only

### Verification plan (2026-11-10)
**Diff base:** e813e08 (PR #105 tip). **Isolation:** throwaway DATA_DIR /tmp/myai73/data, stub model :5191 (SLOW scenario streams for about 16s), backend :5192 serving this branch's build; the stop request is delayed by 1.5s in the browser (route); no containers touched. Scripts: `MYAI-73-evidence/scripts/` (up.sh, stub.py, serve.py, lib.mjs, v73.mjs). Teardown: kill listeners on 5191/5192, rm -rf /tmp/myai73.

| ID | Criterion | Scenario | Method | Files | Expected |
|----|-----------|----------|--------|-------|----------|
| V1 | busy until the stop is answered; Retry then works | SLOW turn, Stop, sample button/Retry for 1.5s, then Retry | browser | send-turn.ts, Composer.tsx, MessageList.tsx | button "Stopping" disabled and Retry disabled until the answer; Retry then streams a reply; no "already in progress" toast |
| V2 | new message after Stop works | same, then type a message | browser | send-turn.ts | the message starts a turn, no refusal toast |
| V3 | transcript matches the server after Stop | after the stop answers, compare rows with GET /api/chats/<id> | browser+API | send-turn.ts | stored: user row only; screen: user row + Stopped row with the partial reply and Retry |
| V4 | live and Stopped rows never together | sample the DOM every 30ms from the click | browser | MessageList.tsx | never more than one bot row; never `data-live` with `data-interrupted` |
| V5 | no Stop flash on reopening a stopped chat | open another chat and come back; sample the Stop button | browser | send-turn.ts, ChatPage.tsx | Stop button never appears |
| V6 | delete stops first | SLOW turn running, delete the chat from the sidebar | browser | RecentChats.tsx, send-turn.ts | POST stop before DELETE; home composer shows Send |
| V7 | regression | vitest, typecheck, lint, build, e2e specs | CLI | all | pass |
| V8 | no console errors | collect console/page errors | browser | all | none unexpected |
A refused send restoring the text and the repeat window are covered by unit/component tests (a refusal cannot be provoked from one tab).


### Results (2026-11-10)
HEAD e813e08 + uncommitted work. The stop request was delayed by 1.5s in the browser; the backend and stub are real.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | 47 samples with the button "Stopping" and disabled; Retry disabled during them; after the answer the button is "Send message" and Retry enabled; Retry started one `/resume` (no refusal toast), 1 bot row |
| V2 | PASS | a new message after Stop started a turn and its reply showed; no toast |
| V3 | PASS | server rolled back to roles ["user"]; screen: user row + one Stopped row with the partial reply and Retry (`shots/V3-after-stop.png`) |
| V4 | PASS | max 1 bot row in every sample; live and Stopped rows never together |
| V5 | PASS | reopening the stopped chat from the sidebar: the Stop button never appeared in 57 samples |
| V6 | PASS | deleting the chat that was generating sent `POST .../stop` then `DELETE ...`; home composer shows "Send message" |
| V7 | PASS | vitest 554/554, typecheck, lint, build, scripts/check.sh --frontend-only; e2e stop-races 3/3 (3 runs) |
| V8 | PASS | no console/page/http errors |

Not verified live: a send refused by the server after it was accepted here (the text restoring is covered by unit/component tests; a refusal cannot be provoked from one tab).
Verdict: verified (V1-V8 PASS).

### Results (re-run 1, 2026-11-10)
V1-V6 PASS again after the round 1 fixes; e2e 6/6. Teardown done.

### Results (re-run 2, 2026-11-10)
V1-V6 PASS again after the round 2 fixes; e2e 6/6. Teardown done.

### Results (re-run 3, 2026-11-10)
V1-V6 PASS again after the round 3 fixes; e2e 6/6 twice with the refuse-once mock. Teardown done.

### Results (re-run 4, 2026-11-10)
V1-V6 PASS again after the round 4 fixes; e2e 6/6. Teardown done.

### Results (re-run 5, 2026-11-10)
V1-V6 PASS again after the round 5 fixes; e2e 6/6. Teardown done. Final verdict: verified.

## Review history
### Round 5 - 2026-11-10 (last allowed)
Verdict: Request changes (2 MAJOR). Resolution: fixed 2. Checks: vitest 573/573, typecheck, lint, build, scripts/check.sh --frontend-only pass; e2e 6/6; live V1-V6 pass. The review cap (5) is reached.
- R5-1 [MAJOR] the server-stop path of stopIfStreaming returned at once, so the delete could run while the worker still ran - Static - Fixed: it polls the chat (bounded, 10 x 300ms) until it is no longer running; test (failed before)
- R5-2 [MAJOR] that path swallowed every stop error - Static - Fixed: only a 404 is silent; other failures show the same "did not confirm the stop" toast (shared helper with stopTurn); test (failed before)

### Round 4 - 2026-11-10
Verdict: Request changes (1 MAJOR, 5 MINOR, 2 NIT). Resolution: fixed 6, left 2 NITs. Checks: vitest 571/571, typecheck, lint, build; e2e 6/6; live V1-V6 pass. Runtime changed.
- R4-1 [MAJOR] the discard guard was not keyed to the chat: a temporary chat started during the previous discard was never discarded - Static - Fixed: keyed by id; test (failed before)
- R4-2 [MINOR] the Retry-400 branch ignored whether chunks had arrived and, for a chat not shown, fell through to an empty error row - Static - Fixed: only before any chunk, toast and no empty row when the chat is not shown; test (failed before)
- R4-3 [MINOR] delete stopped only turns held by this tab - Static - Fixed: a chat the list says is running is stopped on the server first (stop failures ignored); tests (failed before)
- R4-4 [MINOR] comment on `stopping` was wrong - Static - Fixed
- R4-5 [MINOR] stopIfStreaming waited for unrelated turns - Static - Fixed: resolves when this chat's turn ends; test (failed before)
- R4-6 [NIT] unclear comment on the new branch - Static - Fixed
- R4-7 [NIT] test-only reset exported - Static - Left (@internal, noted earlier)
- R4-8 [MINOR] no unit test for the sidebar delete path - Static - Covered by the stopIfStreaming unit tests, the e2e delete case and live V6; a component test of the context-menu flow was not added

### Round 3 - 2026-11-10
Verdict: Request changes (1 MAJOR, 5 MINOR, 1 NIT). Resolution: fixed 6, left 1 (documented earlier). Checks: vitest 566/566, typecheck, lint, build; e2e 6/6 twice (the mock now refuses the first send/Retry once right after the stop, so the repeat path is exercised end to end); live V1-V6 pass. Runtime changed.
- R3-1 [MAJOR] a Retry refused with a 400 other than "in progress" replaced the stopped partial reply with an empty error row - Static - Fixed: when a stopped row is waiting and the request itself was refused, the row stays (toast, `onRefused`); with nothing to restore the inline error row stays as before (existing test); test (failed before)
- R3-2 [MINOR] `chatIsOpen` change made a temporary chat open the files drawer - Static - Fixed: separate `chatIsShown` for the restore check; test (failed before)
- R3-3 [MINOR] ref written during render in Composer - Static - Fixed (effect)
- R3-4 [MINOR] a failed new-chat create loses the text - Static - Left: the page then shows not-found without a composer, so restoring would not help; already a documented known limit of the start-a-chat change
- R3-5 [MINOR] two discards at once deleted the chat twice - Static - Fixed (one in-flight discard); test (failed before)
- R3-6 [MINOR] the e2e mock never refused after the stop - Static - Fixed
- R3-7 [NIT] one over-wide condition - Static - Fixed (send-turn.ts and send-turn.test.ts were already not Prettier-clean at the base)

### Round 2 - 2026-11-10
Verdict: Request changes (4 MAJOR, 5 MINOR, 1 NIT). Resolution: fixed 8, partly fixed 1, documented 1. Checks: vitest 563/563, typecheck, lint, build; e2e 6/6; live V1-V6 pass again. Runtime changed.
- R2-1 [MAJOR] a refused send in a temporary chat dropped the stopped row (`chatIsOpen` ignored the landing page) - Static - Fixed; test (failed before)
- R2-2 [MAJOR] a refused send's text could land in another chat the user moved to - Static - Fixed: the composer restores only into the chat it was sent in; test (failed before)
- R2-3 [MAJOR] Stop during the retry window ended as an empty stopped turn, losing the row and the text - Static - Fixed: it ends as the refusal; test (failed before)
- R2-4 [MAJOR] the reattach early return left the attach connection open - Static - Fixed: the request is aborted; test (failed before)
- R2-5 [MINOR] the retry sleep was not abortable; tests use real-time waits - Static - Fixed in part: the sleep is abortable; the remaining real-time waits test timing itself and stay
- R2-6 [MINOR] `resetStopState` exported from production code - Static - Marked @internal; kept (resetting module state through module reloads would hide the point of the tests)
- R2-7 [MINOR] Prettier on temporary-chat.test.ts and stream-store.test.ts, one long condition - Static - Fixed (formatting limited to files clean at the base; send-turn.test.ts was already unformatted, so only the new code is formatted)
- R2-8 [MINOR] each repeated attempt uses one of the user's turns - Static - Documented in docs/frontend.md
- R2-9 [MINOR] a turn another tab starts within the 3s window is not attached until the next refetch - Static - Documented
- R2-10 [NIT] `stopTurn` compared no chat id - Static - Fixed; `as never` casts in tests left (existing style)

### Round 1 - 2026-11-10
Verdict: Request changes (3 MAJOR, 6 MINOR). Resolution: fixed 8, documented 1. Checks: vitest 559/559, typecheck, lint, build; e2e 6/6 (stop-races, chat-start, chat-send); live V1-V6 pass again. Runtime changed.
- R1-1 [MAJOR] reattachTurn could overwrite a turn that started while its request was out, and its catch cleared the other turn's busy state - Static - Fixed: re-check after the await (close the source), finish() only if this call started the store; test
- R1-2 [MAJOR] a chat refetched right after Stop can still say is_running; the page reattached and wiped the stopped row (the ticket's own symptom) - Static - Fixed: no reattach while a stopped/failed row exists for the chat or within 3s of its stop answer; two tests
- R1-3 [MAJOR] a stop request that never answers keeps the chat in Stopping - Static - Documented: the plan accepted it (a reload recovers); now stated in docs/frontend.md
- R1-4 [MINOR] test isolation (Date.now spies, module state) - Static - Fixed: restoreAllMocks and `resetStopState()` in afterEach
- R1-5 [MINOR] e2e delete assertion passed when `stop-answered` was absent - Static - Fixed
- R1-6 [MINOR] repeat could replay chunks after an error mid-stream; the sleep was not abortable - Static - Fixed: repeat only before any chunk; a Stop during the sleep aborts
- R1-7 [MINOR] a refused send put the stopped row back after the user left the chat - Static - Fixed (only if the chat is open); test
- R1-8 [MINOR] discarding a temporary chat cleared temporary mode before stopping its turn, so Send hit the busy toast - Static - Fixed: stop first; test asserts temporary mode is still on during the stop
- R1-9 [MINOR] Stop during a new-chat create toasted "did not confirm" for a chat the server did not have yet - Static - Fixed: a 404 from the stop is not reported; test


## Log
- 2026-11-10: created (from the race pass in MYAI-52)
- 2026-11-10: linked blocked_by MYAI-54 (same code in send-turn, MessageList, Composer; this ticket edits on top)
- 2026-11-10: linked blocked_by MYAI-56 (same code in send-turn, MessageList, Composer; this ticket edits on top)
- 2026-11-10: linked blocked_by MYAI-63 (same code in send-turn, MessageList, Composer; this ticket edits on top)
- 2026-11-10: linked blocks MYAI-70 (Delete all chats calls stopIfStreaming)
- 2026-11-10: plan validated, 2 rounds
- 2026-11-10: linked relates_to MYAI-74 (server-side fix for the same races)
- 2026-11-10: autopilot started (batch); implemented; verified
- 2026-11-10: review round 1 resolved (8 fixed, 1 documented); re-verify pass
- 2026-11-10: review round 2 resolved; re-verify pass
- 2026-11-10: review round 3 resolved; re-verify pass
- 2026-11-10: review round 4 resolved; re-verify pass
- 2026-11-10: review round 5 resolved; review cap reached
- 2026-11-10: batch-autopilot: shipped, base bugfix/settings-dialogs-polish, PR #106
- 2026-11-10: acceptance criteria reviewed against the recorded results (6 ticked, 1 left open)
- 2026-11-10: closed by the user after the PR merged into develop; 1 acceptance criteria left unticked as known limits (see Verification, Acceptance review)
