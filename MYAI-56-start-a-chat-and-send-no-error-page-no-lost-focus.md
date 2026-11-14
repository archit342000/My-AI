---
id: MYAI-56
title: "Start a chat and send: no error page, no lost focus, temporary chat works"
status: done
epic: MYAI-53
created: 2026-11-10
updated: 2026-11-10
links:
  blocks: [MYAI-61, MYAI-73]
  conflicts_with: [MYAI-58]
---

## Description
Sending the first message navigates before the chat exists; when the fetch wins the race the page shows "This chat no longer exists." for the whole reply. The composer is remounted on navigation (focus and typed text lost, mobile keyboard closes), the page flashes blank, a temporary chat cannot send at all, and while one chat streams every other chat's composer shows Stop and ignores Enter silently.

Findings (MYAI-52, Verification): A-11, A-12, A-13, A-15, A-16, A-17. Evidence and the live test rig are in `~/.claude/tickets/My-AI/MYAI-52-evidence/`.

## Acceptance criteria
- [x] First send never shows an error or blank state, including when the create call takes 1s
- [x] The composer keeps focus and its text across the first send; text typed during the stream start is kept
- [x] The new chat is in the sidebar and highlighted as soon as it is sent
- [x] A temporary chat sends, streams and can be saved
- [x] While chat A streams, chat B's composer does not show Stop for A; a blocked send says why
- [x] A missing chat (real 404) still shows the not-found message, with a way back

## Plan
**Date:** 2026-11-10  **Status:** Validated

### Objective
Make starting a chat and sending a message solid: the first send never shows an error or a blank page, the composer keeps focus and text, the new chat is listed at once, a temporary chat can send, and a send blocked by another chat's running turn says so.

### Context
- **Requirement:** this ticket's Description and Acceptance criteria (findings A-11, A-12, A-13, A-15, A-16, A-17 in MYAI-52).
- **Rules:** `docs/standards/frontend.md` (server data through TanStack Query with keys from `api/`, UI state in Zustand stores, one component per file, tests for `src/state/` and components with logic, new user flows get a Playwright spec in `e2e/`), `docs/standards/api.md` (the turn-in-progress refusal text is a contract; unchanged here). No backend change.
- **Server facts:** `POST /v1/chat/completions` creates the chat for the caller itself (`claim_chat`, `backend/chat/router.py` `chat_completions`); `PATCH /api/chats/<id>` also creates it and stores title and modes (`patch_chat_endpoint`); `GET /api/chats/<id>` is 404 until one of them has run.
- **Current code (`frontend/src/`):**
  - `features/composer/Composer.tsx` `send`: for a new chat it calls `navigate('/chat/<id>')` and then `sendTurn`; the route id comes from `useParams`. `streaming` is `useStreamStore(chatId) !== null`, for any chat.
  - `features/chat/send-turn.ts` `sendTurn`: refuses with the toast "Could not load this chat…" when the chat is not new and has no cached detail (this hits a temporary chat, whose `isNewChat` is false); starts the stream store, then `chatsApi.patch` for a new chat, then streams. `sendTurn`, `resumeTurn` and `reattachTurn` return silently when the store is busy. `consume` refreshes the sidebar list on the first chunk.
  - `features/chat/ChatPage.tsx`: `isPending` renders `.chat-loading`; any `error` replaces the page (title, transcript, composer) with `.chat-error`. `features/chat/useChatQueries.ts` `useChatDetail` does not retry a 404.
  - `features/home/HomePage.tsx` and `ChatPage.tsx` each render their own `<Composer />`; `app/RootLayout.tsx` renders `<Outlet />` inside `<main>`.
  - `state/stream-store.ts` holds one in-flight turn (`chatId`, `live`, `pending`, `controller`).
  - Measured (MYAI-52, script `s4.mjs`): hero, then blank for about 30ms, then transcript; focus on `<body>` after the first send; with the PATCH delayed 400ms the page shows "This chat no longer exists." until the stream ends.

### Approach
- **The chat exists in the cache before the route changes.** For a new chat, `sendTurn` (not the composer) seeds `queryKeys.chat(id)` with an empty detail (id, title from the first message, no messages, `is_running: false`), adds the chat to the top of the `queryKeys.chats` list cache when that list is loaded (an unloaded list is left alone and loads with the chat in it), starts the stream store, and only then calls a `navigate` callback passed in `SendArgs`. `ChatPage` therefore mounts with data: no pending state.
- **A background 404 cannot blank a live page.** `ChatPage` shows the not-found or load-error message only when the query has no data; while a turn for this chat is in the stream store it never shows it. A real missing chat still gets the message, now with a "New chat" button that navigates to `/` (a new `.chat-error__action` class in the "Chat transcript helpers" block).
- **One composer for both routes.** `<Composer />` moves from `HomePage` and `ChatPage` into `RootLayout` (rendered after `<Outlet />` on `/` and `/chat/:chatId`), so navigation does not remount it and focus, text and staged files stay. It reads the chat id with `useMatch('/chat/:chatId')` (as `features/sidebar/RecentChats.tsx` does), and renders nothing when the open chat failed to load and has no data.
- **Temporary chat sends.** `sendTurn` skips the cached-detail check for a temporary chat (the server creates the row on the first turn and builds context from its own stored messages).
- **Per-chat streaming state in the composer.** The Stop button shows only when the open chat is the one streaming. When another chat is streaming, Send stays enabled and a send is refused with a toast ("Another chat is still generating. Wait for it to finish or stop it there."), keeping the text. `sendTurn` and `resumeTurn` show the same toast instead of returning silently.
- **The composer clears only what was accepted.** `sendTurn` resolves to whether the turn was accepted (it passed every pre-send check and started). `Composer.send` no longer navigates itself and no longer clears the text and staged files before the call: it clears them when `sendTurn` reports the turn as started (through an `onAccepted` callback in `SendArgs`, called right after the stream store starts, so the box empties at once) and leaves them untouched on a refusal. A PATCH that fails after that point still loses the text, as today. `/help` and `/skills` keep their own clearing. The `navigate` callback keeps `{ replace: true }`.
- **Rejected:** awaiting the PATCH before navigating (the user waits on a round trip with no feedback and the composer is still remounted); retrying the 404 in `useChatDetail` (still flashes the error and delays a real not-found); several concurrent streams in the store (larger change than the finding needs; one turn at a time stays the rule).

### Out of scope
- Running turns in several chats at once.
- Attachment staging rules across chats (ghost chats, stale chips): MYAI-61. This ticket keeps staged files across the first send only because the composer no longer remounts.
- Mobile keyboard behaviour: MYAI-58.
- Backend changes.

### Steps
#### Step 1: Seed, list and navigate from `sendTurn`
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/features/chat/send-turn.ts` (modify: `SendArgs` gains `navigate` and `onAccepted`, `sendTurn` returns whether the turn started, seeding and ordering, temporary-chat guard, busy toast in `sendTurn` and `resumeTurn`), `frontend/src/features/chat/send-turn.test.ts` (modify)
- **Change:** as in Approach ("The chat exists in the cache…", "Temporary chat sends", busy toast). A failed PATCH still ends the turn with its toast and removes the seeded detail and list entry.
- **Verification:** unit tests: for a new chat the detail and list caches hold the chat before `navigate` is called and before the PATCH resolves; a temporary chat with no cached detail posts the completion; a failed PATCH leaves no seeded entries; a send while another chat streams posts nothing, shows the toast, resolves to not accepted and calls neither `navigate` nor `onAccepted`; with the chat list not loaded the seeding does not throw.

#### Step 2: Chat page states
- **Status:** todo
- **Depends on:** 1
- **Files:** `frontend/src/features/chat/ChatPage.tsx` (modify: pending, error and not-found branches; remove its `<Composer />`), `frontend/src/features/chat/ChatPage.test.tsx` (modify), `frontend/src/styles/components.css` (modify: "Chat transcript helpers" block for the not-found action)
- **Change:** as in Approach ("A background 404 cannot blank a live page").
- **Verification:** component tests: with seeded data and a failing fetch the transcript and title render and no alert is shown; with no data and a 404 the not-found message and a "New chat" button render; with no data and a 500 the load-error message renders; with no data, a 404 and a turn for this chat in the stream store no alert is shown.

#### Step 3: One composer in the layout
- **Status:** todo
- **Depends on:** 1, 2
- **Files:** `frontend/src/app/RootLayout.tsx` (modify: render `<Composer />` on the two routes), `frontend/src/features/home/HomePage.tsx` (modify: remove its `<Composer />`), `frontend/src/features/composer/Composer.tsx` (modify: `useMatch`, per-chat `streaming` (open chat = route id, else the temporary chat id) including the `canSend` gate, `send` passes `navigate` and `onAccepted` to `sendTurn` and drops its own `navigate`, `setText('')` and `setAttachments([])` calls made before the send, hide for an unloaded chat), tests `frontend/src/app/RootLayout.test.tsx`, `frontend/src/features/home/HomePage.test.tsx`, `frontend/src/features/composer/Composer.test.tsx`, `frontend/src/features/chat/ChatPage.test.tsx` (modify)
- **Change:** as in Approach ("One composer for both routes", "Per-chat streaming state", "The composer clears only what was accepted").
- **Verification:** component tests: the composer is present on `/` and `/chat/c1` and absent on `/logs` and `/workspace/w1`; text typed before a route change from `/` to `/chat/x` is still in the box and the textarea is still the active element; Stop shows only for the streaming chat; sending in another chat shows the toast and keeps the text.

#### Step 4: End-to-end spec for the start flow
- **Status:** todo
- **Depends on:** 3
- **Files:** `frontend/e2e/chat-start.spec.ts` (create)
- **Change:** with the completion stream mocked as in `e2e/chat-send.spec.ts` and the chat `PATCH` delayed by one second: send from `/`; then the same in temporary mode.
- **Verification:** the spec asserts that no element with role `alert` appears, `#chat-textarea` stays focused, the sent text is visible within the first second, the sidebar shows the new chat as active, and the temporary chat shows its reply and can be saved. Run with `npm run e2e` (dev server on :5173, backend on :5000).

#### Step 5: Docs and full checks
- **Status:** todo
- **Depends on:** 4
- **Files:** `docs/frontend.md` (modify: Layout/State notes: the composer lives in the layout; one turn at a time), `frontend/README.md` (modify only if affected)
- **Change:** docs match the code.
- **Verification:** from `frontend/`: `npm run typecheck`, `npm run lint`, `npm run test`, `npm run build`; root `pytest tests` and `scripts/check.sh --frontend-only`.

### Tests
- Unit: `features/chat/send-turn.test.ts`.
- Component: `ChatPage.test.tsx`, `Composer.test.tsx`, `HomePage.test.tsx`, `RootLayout.test.tsx`.
- E2E: `e2e/chat-start.spec.ts`.
- Live check (verify stage): MYAI-52 rig, `scripts/s4.mjs` (timeline and delayed-PATCH cases) and `scripts/s5.mjs` test 7 (temporary chat).

### Risks and open questions
- **`#chat-input-area` is absolutely positioned inside `<main>`** (`styles/legacy.css`), so moving the element under `<Outlet />` keeps its place; the `--composer-h` effect keeps working because it is inside `Composer`.
- **Seeded list entry shape:** it must satisfy `ChatSummary` (`api/types.ts`) so `RecentChats` renders it; the first-chunk refresh replaces it with the server's row.
- **A turn already running on the server for the open chat** (reattach) is unchanged.

### Success criteria
- [ ] First send shows no error and no blank state, including with a 1s create delay
- [ ] Composer keeps focus and text across the first send
- [ ] New chat is listed and highlighted as soon as it is sent
- [ ] Temporary chat sends, streams and can be saved
- [ ] Stop appears only in the streaming chat; a blocked send explains itself
- [ ] A missing chat shows not-found with a way back
- [ ] `typecheck`, `lint`, `test`, `build` and the new spec pass
### Reviewer brief
- **Objective:** first send without error or blank page, composer keeps focus and text, new chat listed at once, temporary chat sends, blocked sends explain themselves.
- **Decisions:** `sendTurn` seeds the chat detail and list caches and starts the stream store before calling a `navigate` callback; it returns whether the turn started and calls `onAccepted`, and the composer clears its text and files only then; `ChatPage` shows not-found or load errors only with no data and never while this chat streams; one `<Composer />` in `RootLayout` for `/` and `/chat/:chatId`, reading the id with `useMatch`; a temporary chat skips the cached-detail check; Stop shows only in the streaming chat and a send blocked by another chat's turn shows a toast; one turn at a time stays.
- **Out of scope:** concurrent turns, attachment staging across chats (MYAI-61), mobile keyboard (MYAI-58), backend changes.
- **Success criteria:** no error or blank state on first send even with a 1s create delay; focus and text kept; chat listed and highlighted immediately; temporary chat sends and saves; per-chat Stop and explained refusals; real 404 shows not-found with a way back; checks and the new spec pass.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- **Round 1:** validator FAIL (1 blocking, 3 minor). Judged FAIL. Valid blocking: `Composer.send` clears text and navigates before `sendTurn`, so a refused send would lose text and navigate to a chat never created (fixed: `onAccepted`, boolean result, composer drops its own navigate and early clearing). Minors fixed: `scripts/check.sh`; unloaded chat list in the seeding; "New chat" target and new class.
- **Round 2 (diff-scoped):** validator PASS (5 minor). Judged PASS. Fixed inline: PATCH-failure text loss stated; `replace: true` kept; open-chat identity and `canSend` gate named; test for a 404 while streaming. No change needed: `/help` and `/skills` clearing (noted).

## Implementation notes
### Autopilot run (2026-11-10)
- Mode: automatic (batch)
- Branch: bugfix/start-chat-and-send  PR base: bugfix/transcript-turn-model (stacked on PR #101)  Starting commit: a66ac20
- Dirty before start: none
- Work files: send-turn.ts(+test), Composer.tsx(+test), ChatPage.tsx(+test), RootLayout.tsx(+test), HomePage.tsx(+test), components.css, e2e/chat-start.spec.ts, docs/frontend.md, MessageList.test.tsx
- Counters: fix 0/10, review 2/5, re-verify 2
- Last completed stage: 4 fix loop (none needed)  Next: done (shipped)
- Hard blocker: none
- WIP commit: none

### Autopilot decisions (2026-11-10)
- Stage 1: ticket already holds a validated plan; skipped re-planning.
PR: https://github.com/archit342000/My-AI/pull/102, branch bugfix/start-chat-and-send, base bugfix/transcript-turn-model

## Verification

### Acceptance review (2026-11-10)
Criteria ticked on the live and e2e results recorded in the PR's Testing section (checks run on throwaway backends during the autopilot run; scripts in `MYAI-56-evidence/`).
All criteria covered.

### Verification plan (2026-11-10)
**Diff base:** a66ac20 (PR #101 tip). **Isolation:** throwaway DATA_DIR /tmp/myai56/data, stub model :5191, backend :5192 serving this branch's build; no containers touched. Scripts: `MYAI-56-evidence/scripts/` (up.sh, stub.py, serve.py, lib.mjs, v56.mjs). Teardown: kill listeners on 5191/5192, rm -rf /tmp/myai56.

| ID | Criterion | Scenario | Method | Files | Expected |
|----|-----------|----------|--------|-------|----------|
| V1 | first send, no error/blank | send from `/`; sample alerts, `.chat-loading`, textarea focus every 50ms for the whole turn | browser | send-turn.ts, ChatPage.tsx, Composer.tsx, RootLayout.tsx | no alert ever; textarea focused after send |
| V2 | create call takes 1s | same with the PATCH delayed 1s (route.continue after delay) | browser | same | no alert; user message visible < 700ms; chat listed in sidebar < 700ms |
| V3 | text typed during stream start kept | after Enter type "more" at once | browser | Composer.tsx | textarea contains "more" |
| V4 | temporary chat sends/streams/saves | enable Temporary chat, send, then Save Chat | browser | send-turn.ts, Composer.tsx | reply shown, no alert, saved chat opens at /chat/<id> |
| V5 | per-chat Stop, blocked send says why | start SLOW in chat A; open chat B from sidebar; check Stop absent; type and send in B | browser | Composer.tsx, send-turn.ts | no Stop in B; toast with the busy text; text kept |
| V6 | real 404 | open /chat/does-not-exist | browser | ChatPage.tsx, Composer.tsx | not-found message + New chat button; composer absent; New chat goes to / |
| V7 | regression | vitest, typecheck, lint, build, e2e specs | CLI | all | pass |
| V8 | no console errors | collect console/page errors in V1-V6 | browser | all | none (expected 404 GET for a new chat excluded and listed) |


### Results (2026-11-10)
HEAD a66ac20 + uncommitted work.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | 67 samples over the turn: no alert, no loading state after the route change, textarea focused at the end (`shots/V1-after-send.png`) |
| V2 | PASS | create call delayed 1s: no alert at any sample; user message and sidebar title present at 700ms (`shots/V2-at-700ms.png`); focus kept |
| V3 | PASS | text typed right after Enter is in the textarea (`more`) |
| V4 | PASS | temporary chat replied (Plain answer...), no alert; Save Chat opened /chat/<id> with the reply |
| V5 | PASS | in chat B while A streams: no Stop button; send showed "Another chat is still generating. Wait for it to finish or stop it there."; text kept (first attempt used a page reload, which drops client state, so it was redone with sidebar navigation) |
| V6 | PASS | /chat/does-not-exist: "This chat no longer exists." + New chat button, composer absent; button goes to / where the composer is back |
| V7 | PASS | vitest 395/395 (see Smoke test), typecheck, lint, build, e2e chat-start + chat-send specs 3/3 |
| V8 | PASS | only console errors are the expected 404 GETs for a chat that does not exist on the server yet (V2, V4) or never did (V6); the seeded cache keeps the page up |

Verdict: verified (8/8 PASS).

### Results (re-run 1, 2026-11-10)
V1-V6 PASS again; new V9 PASS (draft typed in chat E is not in chat D's composer after switching); new V10 PASS (deleted chat revisited from cache shows "This chat no longer exists." and New chat). V7: vitest/typecheck/lint/build, e2e 3/3. Teardown done. Verdict: verified.

### Results (re-run 2, 2026-11-10)
V1-V6, V9, V10 PASS after the round 2 edits to ChatPage.tsx; e2e 3/3; teardown done. Verdict: verified.

## Review history
### Round 2 - 2026-11-10
Verdict: Approve with comments (0 BLOCKER/MAJOR, 5 MINOR, 1 NIT). Resolution: fixed 3, rejected 1, accepted/documented 1, deferred 1. Checks: vitest 404/404, typecheck, lint, build; e2e 3/3; live V1-V6, V9, V10 pass again.
- R2-1 [MINOR] docs/frontend.md - sentence contradicted the 404 behaviour - Static - Fixed
- R2-2 [MINOR] failed create lands on not-found with the composer hidden - Static - Accepted and documented in docs/frontend.md (same deferred cause as R1-1)
- R2-3 [MINOR] ChatPage.tsx - spinner instead of an error for a non-404 error while streaming with no data - Static - Fixed (restructured: spinner only while loading or a 404 during the chat's own start); existing tests cover the spinner cases
- R2-4 [MINOR] seedNewChat skips an unloaded list - Static - Rejected: same as R1-8
- R2-5 [MINOR] composer hidden on a failed chat untested - Static - Fixed: test added
- R2-6 [NIT] lines over 100 columns in test files - Static - Deferred: those files were already unformatted before this ticket

### Round 1 - 2026-11-10
Verdict: Request changes (5 MAJOR, 5 MINOR, 1 NIT from one Haiku reviewer). Resolution: fixed 7, rejected 3, deferred 2 (below). Checks: vitest 403/403 (before round 2 additions), typecheck, lint; e2e 3/3; live V1-V6, V9, V10 pass. Runtime changed (ChatPage.tsx, Composer.tsx, send-turn.ts).
- R1-1 [MAJOR] send-turn.ts:262 - failed create returns true after onAccepted cleared the composer and navigate moved the route, text lost - Static - Deferred: the plan states "a PATCH that fails after that point still loses the text, as today"; restoring it needs navigating back and restoring the draft (follow-up suggested, see PR notes)
- R1-2 [MAJOR] send-turn.ts:271 - a server 400/429 refusal arrives after onAccepted, text lost - Static - Deferred: same cause, same follow-up; client-side busy refusals (the common case) keep the text
- R1-3 [MAJOR] ChatPage.tsx - 404 with cached data suppressed not-found - Static - Fixed: a 404 shows not-found unless this chat's own turn is running; tests (failed before); live V10
- R1-4 [MAJOR] Composer.test.tsx - non-null assertion in new test - Static - Fixed
- R1-5 [MAJOR] tests missing - Static - Fixed in part: e2e now types during the pending create and asserts the text survives; saveTemporaryChat unit tests added (it had none); (c)/(d) test the deferred behaviour and were not added
- R1-6 [MINOR] Stop during create - Static - Rejected: unchanged from before this ticket (the stream starts aborted and is marked Stopped); out of plan scope
- R1-7 [MINOR] draft followed the user into another chat - Static - Fixed: composer drops text and chips on a chat switch, keeps them across its own first send; test (failed before); live V9
- R1-8 [MINOR] unloaded list not seeded - Static - Rejected: the sidebar always loads the list, and the first-chunk refresh already lists the chat if the list loaded early
- R1-9 [MINOR] ChatPage test sleeps and leaks store state - Static - Fixed (waitFor, reset in afterEach)
- R1-10 [MINOR] e2e highlight assertion weak and timing coupled - Static - Fixed (create call held by the test; asserts `.chat-list-item.active` contains the title)
- R1-11 [NIT] same-chat double submit blamed another chat - Static - Fixed (silent refusal for the same chat); test


## Log
- 2026-11-10: created
- 2026-11-10: added to epic MYAI-53
- 2026-11-10: linked conflicts_with MYAI-58
- 2026-11-10: linked conflicts_with MYAI-61
- 2026-11-10: plan validated, 2 rounds
- 2026-11-10: link changed: blocks MYAI-61 (was conflicts_with)
- 2026-11-10: linked blocks MYAI-73 (same code in send-turn, MessageList, Composer)
- 2026-11-10: autopilot started (batch)
- 2026-11-10: implemented, verified 8/8 PASS
- 2026-11-10: review round 1 resolved; re-verify pass
- 2026-11-10: review round 2 resolved; loop clean
- 2026-11-10: batch-autopilot: shipped, base bugfix/transcript-turn-model, PR #102
- 2026-11-10: acceptance criteria reviewed against the recorded results (6 ticked, 0 left open)
- 2026-11-10: closed by the user after the PR merged into develop
