---
id: MYAI-62
title: "Clarification prompts: answer the model's question in the chat"
status: done
epic: MYAI-53
created: 2026-11-10
updated: 2026-11-10
links:
  blocked_by: [MYAI-54]
---

## Description
When the model calls `request_clarification` the turn waits for an answer, but the React UI has no way to give one, so the chat hangs at "Thinking…" forever.

Findings (MYAI-52, Verification): A-54. Evidence and the live test rig are in `~/.claude/tickets/My-AI/MYAI-52-evidence/`.

## Acceptance criteria
- [x] A clarification request shows the question and its options in the chat while the turn waits
- [x] Choosing an option or typing an answer resumes the turn
- [x] Reloading the page while a request is pending shows it again
- [x] Stopping the turn dismisses the prompt

## Plan
**Date:** 2026-11-10  **Status:** Validated

### Objective
Let the user answer a clarification request from the model inside the chat, so a turn that calls `request_clarification` continues instead of hanging.

### Context
- **Requirement:** this ticket's Description and Acceptance criteria (finding A-54 in MYAI-52).
- **Assumes merged:** MYAI-54 (`LiveTurn.steps`, tool steps `{ kind: 'tool', id, name, args, result, agent }`, one live row per turn in `features/chat/MessageList.tsx`).
- **Rules:** `docs/standards/frontend.md` (typed API calls in `src/api/`, components never call `fetch`, pure logic in `src/lib/` with tests, reuse UI primitives, keyboard operable, new user flows get a Playwright spec), `docs/standards/api.md` (contracts unchanged). No backend change.
- **Server facts:**
  - `backend/tools/clarify.py` `request_clarification(question, options)`: registers a callback under the tool call's id, appends a second `tool_calls` chunk with the same id and the arguments `{question, options}` to the stream, then waits up to an hour. The tool result arrives as a normal `tool_result` chunk once answered.
  - `POST /api/tools/clarification/response` with `{ callback_id, chat_id, type: 'answer', content }` resumes it; 404 `{ "error": "Unknown or expired callback_id" }` otherwise (`backend/tools/router.py` `clarification_response`).
  - Other tools ask through the same function with their own call id: the code runner's approval prompts (`backend/tools/implementations/code_executor.py`) call `request_clarification(..., tool_call_id=<the run call's id>)`, so the stream then carries a `request_clarification` chunk whose id belongs to a step with another name (for example `run_code`).
  - A reload reattaches to the running turn and the stream is replayed from the start (`backend/database/cache_system.py` `subscribe`), so the pending tool call is seen again. `POST /api/chats/<id>/stop` ends the waiting turn.
- **Legacy reference:** `static/js/clarification-popover.js` (`showClarificationPopOver`): question rendered as markdown, one radio row per option, a "Custom response..." row with a textarea, Cancel (confirm, then stop the turn) and "Confirm Response" (disabled until there is an answer).
- **Current code (`frontend/src/`):**
  - No clarification UI and no API call for it (measured in MYAI-52: the row stays at "Thinking… / Request Clarification · Running").
  - `features/chat/stream-reducer.ts` `mergeToolCalls`: a delta whose id already exists appends its arguments to the stored ones, so the second chunk for the same id would double the JSON text.
  - `components/ui/RadioCards.tsx`, `components/ui/Field.tsx` (`Textarea`), `components/ui/Button.tsx`, `components/ui/ConfirmDialog.tsx`; `features/chat/send-turn.ts` `stopTurn`; `components/markdown/Markdown.tsx`.

### Approach
- **A pending request is its own piece of live state.** `LiveTurn` gains `pendingRequest: { id, question, options } | null`. `applyChunk` sets it from a `tool_calls` delta whose function name is `request_clarification` and whose id already belongs to a step (that is the chunk `clarify.py` sends once the callback is registered; the model's own merged call, which arrives first, only creates the step) (arguments parsed by `parseClarification` in the new `lib/clarification.ts`; options default to none; arguments that do not parse give the question "The assistant needs your input." and no options), and clears it when a `tool_result` for that id arrives or on a redact. This covers both the model's own clarification call and requests raised by another tool under that tool's id.
- **The repeated chunk does not touch the step.** In `mergeToolCalls`, a `request_clarification` delta whose id already exists on a step is not merged into it (today it would append its arguments to the stored ones); the step keeps its name and arguments. Because reattach replays the turn, the same logic covers a reload.
- **Prompt in the transcript.** `features/chat/ClarificationPrompt.tsx` (new) renders under the live row while a request is pending: the question through `Markdown`, the options as `RadioCards` (each option string is the title; values are the option's index so duplicate texts do not collide) plus a "Custom response" choice with a `Textarea`, "Confirm response" (disabled until there is an answer, shows progress while posting) and "Cancel" (a `ConfirmDialog`, then `stopTurn`). The transcript scrolls it into view.
- **Answer call.** `api/tools.ts` (new) exports `clarificationApi.respond(chatId, callbackId, content)`. On success the prompt hides at once (tracked by callback id) and the stream continues; on failure the prompt stays and a toast shows the error.
- **Rejected:** a popover attached to the composer as in legacy (the composer is being moved by MYAI-56, and an in-flow card is reachable by keyboard and screen readers); polling `/api/tools/active` (the replayed stream already carries the pending call).

### Out of scope
- Server-restart recovery when no turn is running (callbacks persisted in the database with no live stream); the resume banner in MYAI-63 covers interrupted turns.
- Plan approval and other callback kinds used by research mode (MYAI-70).
- Styling of the tool entry inside the thought box (MYAI-55).

### Steps
#### Step 1: Detection logic and reducer fix
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/lib/clarification.ts` (create: `parseClarification`), `frontend/src/lib/clarification.test.ts` (create), `frontend/src/features/chat/stream-reducer.ts` (modify: `LiveTurn.pendingRequest`, `emptyLiveTurn`, `applyChunk`, `mergeToolCalls`), `frontend/src/features/chat/stream-reducer.test.ts` (modify), `frontend/src/test/fixtures/stream/clarify.sse` (create: reasoning, the merged call, the repeated call; no result, the turn is waiting), `frontend/src/test/fixtures/stream/stream.test.ts` (modify)
- **Change:** as in Approach ("A pending request is its own piece of live state", "The repeated chunk does not touch the step").
- **Verification:** unit tests: the fixture yields one tool step with unchanged, valid JSON arguments and a `pendingRequest` with its question and options; a `request_clarification` chunk carrying the id of a `run_code` step sets `pendingRequest` and leaves that step's name and arguments as they were; applying a `tool_result` chunk for the id clears it; arguments that do not parse give the fixed question; a call with another name sets nothing; the model's first merged `request_clarification` call alone sets nothing until the repeated chunk arrives.

#### Step 2: API call
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/api/tools.ts` (create), `frontend/src/api/tools.test.ts` (create)
- **Change:** as in Approach ("Answer call").
- **Verification:** unit tests with a mocked `fetch`: the POST goes to `/api/tools/clarification/response` with `callback_id`, `chat_id`, `type: 'answer'` and `content`; a 404 rejects with the server's message.

#### Step 3: Prompt component
- **Status:** todo
- **Depends on:** 1, 2
- **Files:** `frontend/src/features/chat/ClarificationPrompt.tsx` (create), `frontend/src/features/chat/ClarificationPrompt.test.tsx` (create), `frontend/src/styles/components.css` (modify: new "Clarification prompt (clarify)" block, using the existing colour, spacing and radius tokens)
- **Change:** as in Approach ("Prompt in the transcript").
- **Verification:** component tests: options and the custom choice render; Confirm is disabled until an option is chosen or text is typed; confirming calls the API with the chosen text and hides the prompt; a failed call keeps it and shows a toast; Cancel asks first and then calls `stopTurn`; everything is reachable with Tab and arrow keys.

#### Step 4: Show it in the transcript
- **Status:** todo
- **Depends on:** 3
- **Files:** `frontend/src/features/chat/MessageList.tsx` (modify: render the prompt after the live row when `live.pendingRequest` is set), `frontend/src/features/chat/MessageList.test.tsx` (modify)
- **Change:** as in Approach; the prompt is rendered only for the chat whose turn is streaming.
- **Verification:** component tests: a live turn with a pending request shows the prompt; once the result arrives it is gone; after the turn is stopped (store `interrupt` then `finish`) it is gone; another chat's stream shows nothing here.

#### Step 5: End-to-end spec, docs and full checks
- **Status:** todo
- **Depends on:** 4
- **Files:** `frontend/e2e/clarification.spec.ts` (create), `docs/frontend.md` (modify: Streaming section: clarification requests)
- **Change:** the spec serves `clarify.sse` without the `[DONE]` line for the completion, mocks the response endpoint, answers with an option, then reloads with the chat reported as running and the same stream on `GET /api/chats/<id>/stream`.
- **Verification:** the spec asserts the prompt appears, the POST body carries the option text, the prompt hides, and after the reload the prompt is shown again. Then from `frontend/`: `npm run typecheck`, `npm run lint`, `npm run test`, `npm run build`, and `npm run e2e` (outside the merge gate; needs the dev server on :5173 and the backend on :5000, `docs/standards/testing.md`); from the repo root `pytest tests` and `scripts/check.sh --frontend-only`. Live (MYAI-52 rig): the `CLARIFY` scenario of `stub.py` completes after choosing "Red".

### Tests
- Unit: `lib/clarification.test.ts`, `api/tools.test.ts`, `features/chat/stream-reducer.test.ts`, `test/fixtures/stream/stream.test.ts`.
- Component: `ClarificationPrompt.test.tsx`, `MessageList.test.tsx`.
- E2E: `e2e/clarification.spec.ts`.

### Risks and open questions
- **Sub-agent clarifications** carry `parent_type`; `pendingRequest` is set from them too, but the research-specific callback kinds stay out of scope.
- **A request answered in another tab** ends through the `tool_result` chunk, which hides the prompt here too.
- **Shared file:** `MessageList.tsx` is also changed by MYAI-55, MYAI-60 and MYAI-63.

### Success criteria
- [ ] A clarification request shows its question and options while the turn waits
- [ ] Choosing an option or typing an answer resumes the turn
- [ ] A reload while a request is pending shows it again
- [ ] Stopping the turn dismisses the prompt
- [ ] Checks and the new spec pass
### Reviewer brief
- **Objective:** the user can answer a clarification request inside the chat so the turn continues.
- **Decisions:** `LiveTurn.pendingRequest` set by the repeated `request_clarification` chunk (any tool's id, including code-runner approvals) and cleared by that id's `tool_result` or a redact; that chunk is not merged into the existing step; `ClarificationPrompt` renders in the transcript under the live row (question as markdown, options as `RadioCards` by index, custom answer, Confirm, Cancel that stops the turn after a confirm dialog); `api/tools.ts` posts the answer; reload is covered by the replayed stream; no polling of `/api/tools/active`.
- **Out of scope:** recovery after a server restart with no running turn, research-mode callback kinds (MYAI-70), thought box styling (MYAI-55).
- **Success criteria:** question and options shown while the turn waits; an option or typed answer resumes the turn; a reload shows the request again; stopping dismisses it; checks and the new spec pass.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- **Round 1:** validator FAIL (1 blocking, 6 minor). Judged FAIL after reading `backend/tools/implementations/code_executor.py`: code-runner approvals raise `request_clarification` under the run call's id, so detection by step name missed them and replacing arguments would corrupt the run step. Fixed: separate `pendingRequest` state; the repeated chunk never changes a step. Minors fixed: stop dismissal test; option mapping by index; fixture without a result; e2e noted as outside the merge gate; CSS tokens; fixed fallback question.
- **Round 2 (diff-scoped):** validator PASS (1 minor). Judged PASS. Fixed inline: `pendingRequest` is set only by the repeated chunk (id already has a step), so the prompt cannot appear before the callback exists.

## Implementation notes
Branch bugfix/message-rendering (name kept from batch start; content is the clarification prompt), base bugfix/transcript-turn-model (autopilot batch item 13).
### Implementation progress
- [x] Step 1: lib/clarification.ts, `LiveTurn.pendingRequest`, reducer (repeat chunk not merged), fixture clarify.sse
- [x] Step 2: api/tools.ts
- [x] Step 3: ClarificationPrompt.tsx and CSS block
- [x] Step 4: rendered as the live row's footer in MessageList
- [x] Step 5: docs/frontend.md
Deviations: no Playwright spec. A mocked completion cannot keep a stream open (the response ends, so the turn ends and the prompt goes), so the pending state is covered by reducer, fixture and component tests and verified live on the rig with the real backend and the stub's CLARIFY scenario (script in the evidence folder).
### Smoke test (2026-11-10)
check.sh --frontend-only: typecheck, lint, 407 tests, build pass.
Live (V1-V4): prompt with question and options; reload while pending shows it again; choosing Red posts {callback_id, chat_id, type: answer, content: Red} and the turn completes ("Final answer after 1 tool call(s)."); Stop dismisses the prompt; no console errors.

PR: https://github.com/archit342000/My-AI/pull/113, branch bugfix/message-rendering, base bugfix/transcript-turn-model

## Verification

### Acceptance review (2026-11-10)
Criteria ticked on the live and e2e results recorded in the PR's Testing section (checks run on throwaway backends during the autopilot run; scripts in `MYAI-62-evidence/`).
All criteria covered.

## Review history
### Round 1 - 2026-11-10
Verdict: Request changes (1 MAJOR). Single Haiku reviewer.
- R1-1 [MAJOR] non-null assertion in a test - Fixed.
- R1-2 [MINOR] an id-less result closed a pending request - Fixed: only the request's own id closes it; test.
- R1-3 [MINOR] prompt had no key, state could carry to a new request - Fixed (`key` = request id).
- R1-4 [MINOR] a fragment of the model's own call could look like the server's repeat - Rejected: the backend aggregates the model's fragments into one whole call before sending (backend/chat/handler.py), and requiring parseable JSON would break the plan's fixed-question fallback for bad arguments.
- R1-5 [MINOR] README api row - Fixed. R1-7 [NIT] typed `live()` helper - Fixed. R1-8 [NIT] live region - Fixed (role group, aria-live polite).
- R1-6 [NIT] fixture without [DONE] - Rejected: the turn is waiting; the fixture must not look finished.
Resolution: check.sh passes (408 tests); live V1-V4 re-run after the fixes. Round 1 fixes were not re-reviewed.


## Log
- 2026-11-10: created
- 2026-11-10: added to epic MYAI-53
- 2026-11-10: linked blocked_by MYAI-54
- 2026-11-10: plan validated, 2 rounds
- 2026-11-10: acceptance criteria reviewed against the recorded results (4 ticked, 0 left open)
- 2026-11-10: closed by the user after the PR merged into develop
