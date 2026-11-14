---
id: MYAI-19
title: "Resume and send can race on one chat"
status: done
created: 2026-11-09
updated: 2026-11-09
links:
  blocks: [MYAI-35]
  blocked_by: [MYAI-6, MYAI-7]
  conflicts_with: [MYAI-22]
---

## Description
Found while planning MYAI-7. MYAI-7 adds a turn claim to `/v1/chat/completions` so a second send while a turn runs gets 400. `resume_chat` (`/api/chats/<id>/resume`) is not guarded, so a Resume and a send at the same instant can still start two turns on one chat. MYAI-6 also routes Retry through resume, which makes this path more common.

## Acceptance criteria
- [x] Resume while a turn is running or starting is rejected (400, no new turn)
- [x] Send while a resume-started turn runs is rejected
- [x] The client shows the rejection as a toast
- [x] Normal resume and reattach still work

## Plan

**Date:** 2026-11-09  **Status:** Validated  **Base:** origin/develop 6a13e04  **Depends on:** MYAI-7 (turn claim), MYAI-6 (React `resumeTurn`)

### Objective
Allow one turn per chat across both entry points, `POST /v1/chat/completions` (send) and `POST /api/chats/<id>/resume`. MYAI-7 guards only send, so a resume and a send arriving together can still start two turns. Give resume the same guard, and make the clients show a rejection as a toast.

### Context
- Requirement: Description and Acceptance criteria above.
- Planned in MYAI-7 (not on develop yet):
  - `TaskManager.claim_turn(chat_id) -> bool` and `release_turn_claim(chat_id)` (`backend/task_manager/manager.py`).
  - `chat_completions` claims before any DB write and returns `400 {"error": "a response is already in progress"}` on False.
  - The claim is released by `Response.call_on_close` and in the route's `except`.
  - The React client's `consume` (`send-turn.ts`) shows a 400 as a toast only.
- Current `resume_chat` (`backend/chat/router.py:447-501`):
  - It builds `ChatHandler(chat_id)`, finds the last user message (400 if none), resolves the model and strips mode flags.
  - It returns `Response(generate_stream())`, which calls `handler.initiate_chat(...)`.
  - It has no running-turn check.
  - Its `except` returns `str(e)` (MYAI-5 scope, not touched here).
- Callers of resume:
  - React: none on develop. MYAI-6 Step 7 adds `resumeStream` in `frontend/src/api/completions.ts` and `resumeTurn` in `frontend/src/features/chat/send-turn.ts`, used by Retry (MYAI-6 Step 8).
  - Legacy Resume banner: `static/script.js:3007-3008` posts to `/resume` when `isResume` is set (banner markup at 3687-3705; its confirm handler at 3707-3716 calls `sendMessage(null, null, true)`). On an error, `sendMessage`'s catch (3382-3400) writes `API Error: <message>` inline into the bot row. With the guard, a rejected legacy Resume shows `API Error: a response is already in progress` inline. That is an acceptable visible message for the legacy UI, so it's left as is (no toast change).
  - Legacy: `static/js/clarification-popover.js`. The Cancel button posts `/resume` with `{"action": "cancel"}` while the turn is still waiting for the clarification. The body passes through `extra_body` into `initiate_chat`, and no backend code reads `action`. While the turn is running, `ChatHandler.process_message` (`backend/chat/handler.py:182-196`, reached from `initiate_chat` at line 168) only reattaches (`task_reattach`), so today Cancel cancels nothing; the fire-and-forget fetch (clarification-popover.js:151-156) ignores the response. With the new guard, that call would get 400 and still do nothing. The proper cancel is `POST /api/chats/<id>/stop` (`stop_chat`, router.py:503), which stops the task, rolls back and runs `callback_registry.cleanup_chat`.
- Tests:
  - `backend/chat/tests/test_router.py::test_resume_chat` (line 244).
  - `static/js/tests/test_clarification-popover.js` (node:test plus jsdom from the root `package.json`).
  - React tests from MYAI-6/7 in `send-turn.test.ts`.
- Rules:
  - `docs/standards/api.md`: 400 for invalid requests; error body `{"error": ...}`; streaming section updated by MYAI-7.
  - `docs/standards/testing.md`: commands and env vars.
  - `docs/standards/frontend.md`: toasts via `showToast`.

### Approach
- **Same claim on resume.** At the top of `resume_chat`, before `ChatHandler` and any DB read, call `task_manager.claim_turn(chat_id)`.
  - On False: `log_event("chat_resume_rejected_turn_in_progress", {"chat_id": chat_id})` and return the same 400 body as send.
  - On True: build the response as today, then `response.call_on_close(lambda: task_manager.release_turn_claim(chat_id))`. Release explicitly on the "no user message" 400 and in the `except` path.
  - Since send and resume share one claim per chat, either one blocks the other in both orders.
- **React.** The toast-only handling of a 400 is MYAI-7 Step 5's new `ApiError` status 400 branch in `consume`; on develop, `consume` interrupts on any error. If `resumeTurn` (MYAI-6) uses `consume`, it inherits that branch; if it has its own consumer, add the same branch there.
- **Legacy Cancel uses stop.** Change the popover's Cancel to `POST /api/chats/<id>/stop`, which really cancels and cleans up the callback. Today's resume call only reattaches while the turn waits, and the new guard would turn it into an ignored 400. Confirm with Playwright on the legacy UI during verify.
- Rejected alternatives:
  - An `is_task_running` check alone in resume: it has the same check-then-act race that MYAI-7 avoided.
  - Exempting `action: cancel` from the guard: the backend ignores `action`, so the request would still start a turn.

### Steps
#### Step 1: Guard `resume_chat`
- **Files:** `backend/chat/router.py` (modify): `resume_chat`.
- **Change:** as in Approach. The claim comes first; it is released on every non-stream return and in `except`; the stream path releases via `call_on_close`. No other behaviour changes.
- **Verification:** Step 2 tests.

#### Step 2: Backend tests
- **Files:** `backend/chat/tests/test_router.py` (modify).
- **Change:**
  - Update `test_resume_chat` so the patched `backend.chat.router.task_manager.claim_turn` returns True, and assert that `release_turn_claim` is called after the response is consumed and closed.
  - New tests:
    - Claim False gives 400 with the exact body, and `ChatHandler` and `db.get_messages` are never called.
    - The no-user-message 400 releases the claim.
    - An exception gives 500 and releases the claim.
    - A regression test with a real `TaskManager()` patched in as `backend.chat.router.task_manager`, its cleanup thread suppressed by patching `threading.Thread` while constructing it (the `manager` fixture in `backend/task_manager/tests/test_manager.py`). Mock `ChatHandler` so `initiate_chat` is an async generator that yields one chunk and then waits on an `asyncio.Event`, and mock `db` as the existing tests do. Use the Flask test client with `buffered=False`, read the first chunk and don't close the response, which holds it open. With a send held open, resume gets 400; with a resume held open, send gets 400; after `response.close()`, the other is accepted.
    - `test_reattach_stream` still passes, and a new case shows that `GET /api/chats/<id>/stream` still returns 204 while only a claim is held.
- **Verification:** `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q backend/chat/tests/test_router.py backend/task_manager/tests/test_manager.py`, then `... -m pytest -q backend` (parent directories, which includes `backend/tests/`), passes.

#### Step 3: React rejection toast for resume
- **Files:** `frontend/src/features/chat/send-turn.test.ts` (modify). `frontend/src/features/chat/send-turn.ts` (modify) only if, after MYAI-6 and MYAI-7 land, `resumeTurn` doesn't reach MYAI-7's 400 branch in `consume`; then add the same branch to its consumer. The test fails until MYAI-7's branch exists.
- **Change:** add a test where `resumeStream` (mocked fetch) returns 400 with `{"error": "a response is already in progress"}`. Assert a toast with that message is shown, `useStreamStore.getState().interrupted` is null, and the stream state is finished.
- **Verification:** `cd frontend && npm run typecheck && npm run lint && npm run test` passes.

#### Step 4: Legacy Cancel calls stop
- **Files:** `static/js/clarification-popover.js` (modify): `cancelBtn.onclick`. `static/js/tests/test_clarification-popover.js` (modify).
- **Change:**
  - `fetch(`${API_MODULES.CHATS}/${config.chatId}/stop`, { method: "POST" })`, with no body.
  - On a non-OK response, call `config.showNotification` with a short error, matching the Confirm path's style.
  - The popover is still hidden.
  - Test: Cancel (with `showConfirm` resolving true) calls the `/stop` URL with POST and never `/resume`.
- **Verification:** run `npm ci` at the repo root once (for jsdom), then `node --test static/js/tests/test_clarification-popover.js` passes.

#### Step 5: Docs
- **Files:**
  - `docs/standards/api.md` (modify): extend MYAI-7's one-turn-per-chat bullet to say `POST /api/chats/<id>/resume` returns the same 400.
  - `backend/chat/README.md` (modify): one line saying resume claims the turn like send.
  - `static/js/README.md`: no change unless it describes the Cancel call (check).
- **Verification:** `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q tests` passes.

#### Step 6: Full gate and live check
- **Change:**
  - Run `venv/bin/ruff check .` and `scripts/check.sh`.
  - Live check against a throwaway `DATA_DIR`, with the stack isolation rules from MYAI-17 Step 7 if a compose stack is used:
    - L1: start a send, then immediately POST resume for the same chat: 400 and no new user or assistant rows.
    - L2: the reverse order gives the same result.
    - L3: after the turn ends, Retry (React) and resume work.
    - L4: in the legacy UI, a clarification Cancel stops the turn, and the chat isn't left in a running state.
- **Verification:** all pass; results go in Verification.

### Tests
- Preconditions: a `venv` with `requirements.txt` and `requirements-dev.txt` installed (pytest and ruff are in the dev file, `docs/standards/dependencies.md`), and `npm ci` at the repo root and in `frontend/`.
- Separate pytest processes, as `docs/standards/testing.md` requires: `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q backend`, then the same with `tests`.
- `cd frontend && npm run typecheck && npm run lint && npm run test`
- `node --test static/js/tests/test_clarification-popover.js` (after the root `npm ci`)
- `venv/bin/ruff check .`, then `scripts/check.sh`
- Live checks L1-L4

### Risks and open questions
- **Ordering.** This plan needs MYAI-7 (`claim_turn`) and should land after MYAI-6 (`resumeTurn`). If MYAI-6 hasn't landed, Step 3 reduces to checking that no React code calls resume.
- **Legacy Cancel behaviour change.** It now really stops the turn, rolls back to the last user message and sets `resume_suppressed=1`, which hides the resume banner (`stop_chat`, router.py:503-524). Previously it reattached and cancelled nothing. That's the intended meaning of "Cancel Process", but it is user-visible.
- **Resume no longer reattaches.** Resume while a turn runs used to reattach via `initiate_chat` (`task_reattach`); it now returns 400. Clients reattach through `GET /api/chats/<id>/stream` (`reattach_stream`), which is unchanged and re-verified in Step 2 and L3.
- **`resume_chat` still returns `str(e)` on 500.** That's MYAI-5 / MYAI-23 territory and isn't changed here; expect a merge conflict in the same function.
- **Assumption: acceptance criterion 3 is narrowed for the legacy UI.** The criterion says "toast". React gets a toast. The legacy Resume banner keeps its existing inline `API Error: a response is already in progress` (script.js:3382-3400), to avoid reworking legacy error handling. Flagged to the owner; if a legacy toast is wanted, add a `showNotification` call in that catch for a 400.
- No blocking open questions.

### Success criteria
- [ ] Resume while a turn runs or is starting returns 400 and starts nothing (Step 2, L1)
- [ ] Send while a resume-started turn runs returns 400 (Step 2, L2)
- [ ] Clients show the rejection: a toast in React (Step 3); in the legacy UI, an inline `API Error` for the Resume banner (unchanged handling) and a notification for Cancel (Step 4)
- [ ] Normal resume, Retry and reattach still work (Step 2, L3)
- [ ] Docs updated; all checks pass

### Validation log
- Round 1 (2026-11-09, Haiku): FAIL, 1 BLOCKING and 8 MINOR. My judgement: FAIL is valid; I checked all 9 against the code and all were valid.
  - B1: one pytest process mixed the `backend` and root `tests` suites (testing.md:48). Fixed: separate runs.
  - M2: Cancel doesn't start a second turn while running; it reattaches (handler.py:182-196). Rationale corrected; the change is still justified.
  - M3: no root `node_modules`. `npm ci` precondition added.
  - M4: venv precondition. Added.
  - M5: the 400 toast branch comes from MYAI-7, not develop. Dependency stated.
  - M6: `stop_chat` sets `resume_suppressed`. Added to Risks.
  - M7: resume-as-reattach becomes a 400. Stated as intended; reattach endpoint re-verified.
  - M8: parent directories (`backend/tests`). Added.
  - M9: regression test mechanics. Spelled out.
- Round 2 (2026-11-09, Haiku, diff-scoped): FAIL, 1 BLOCKING and 2 MINOR. Round 1's B1 was confirmed resolved, and the regression-test mechanics were confirmed feasible (Werkzeug `close()` runs `call_on_close`).
  - B1: the venv precondition omitted `requirements-dev.txt` (pytest, ruff). Valid. Fixed.
  - M2: legacy Resume banner caller missing. Valid (script.js:3007). Added; inline error accepted.
  - M3: wrong function cited for 182-196. Valid. It's `process_message`; fixed.
- Round 3 (2026-11-09, Haiku, diff-scoped): PASS, 2 MINOR. My judgement: PASS; round 2's B1 was confirmed resolved. Stop rule met.
  - M1: AC3's legacy narrowing wasn't recorded. Valid. Recorded under Risks as an assumption for the owner.
  - M2: banner line citation. Valid. Fixed.

## Implementation notes
### Autopilot run (2026-11-09)
- Mode: automatic (batch-autopilot batch 3, item 1/2)
- Branch: bugfix/resume-send-race  PR base: develop  Starting commit: 77a0908
- Dirty before start: none
- Work files: backend/chat/router.py, backend/chat/tests/test_router.py, backend/chat/README.md, docs/standards/api.md, frontend/src/features/chat/send-turn.ts, frontend/src/features/chat/send-turn.test.ts, static/js/clarification-popover.js, static/js/tests/test_clarification-popover.js
- Counters: fix 0/10, review 1/5, re-verify 1
- Last completed stage: 6 ship  Next: none
- Hard blocker: none
- WIP commit: none

### Autopilot decisions (2026-11-09)
- Stage 1: plan already Validated (3 rounds); reused, not re-planned. Written against 6a13e04; MYAI-6, 7 and 20 are now merged (develop 77a0908).

### Baseline (2026-11-09)
At develop 77a0908: backend/chat/tests 140 pass; backend/task_manager/tests 38 pass; frontend vitest 281 pass (48 files). Other backend suites fail only on async tests (pytest-asyncio not installed in the venv).

### Implementation progress
- [x] Step 1: guard `resume_chat` - backend/chat/router.py (claim first; released on the no-user-message 400, on error and when the response closes; 400 `a response is already in progress` + `chat_resume_rejected_turn_in_progress` log)
- [x] Step 2: backend tests - backend/chat/tests/test_router.py (400 refusal, release on nothing-to-resume / error / close, send and resume exclude each other both ways with a real TaskManager)
- [x] Step 3: React toast for the resume refusal - frontend/src/features/chat/send-turn.ts (+ test)
- [x] Step 4: legacy Cancel calls `/stop` - static/js/clarification-popover.js (+ 3 node tests; root `npm ci` run for jsdom)
- [x] Step 5: docs - docs/standards/api.md, backend/chat/README.md
- [x] Step 6: full checks (see Smoke test); live check is the verify stage
Branch: bugfix/resume-send-race
Deviation: `consume` only treats a 400 as toast-only for sends (MYAI-7 review R1-1 limited it so Retry keeps its inline error row for other 400s). For resume, the toast-only handling is therefore keyed on the refusal message (`TURN_IN_PROGRESS` constant in send-turn.ts), so the 400 "No user message found to resume from." still shows an inline interrupted row as before.

### Smoke test (2026-11-09)
chat 145 pass; task_manager 38; backend/tests 25; tests 32; ruff clean; `scripts/check.sh --python-only`: only the baseline async-plugin failures; frontend vitest 282 pass, typecheck clean, lint only the existing forms.tsx warning, build ok; `node --test static/js/tests/test_clarification-popover.js` 5 pass.

PR: https://github.com/archit342000/My-AI/pull/61, branch bugfix/resume-send-race, base develop

## Verification
### Verification plan (2026-11-09, light form: 1 route guard, small client change, legacy Cancel; concurrency)
**Diff base:** origin/develop 77a0908. **Scope:** `resume_chat` claims the same per-chat turn slot as sends (400 `a response is already in progress`), React toast for that refusal, legacy popover Cancel calls `/stop`. Out of scope: legacy toast for the Resume banner (stays inline), MYAI-43/44 items.
**Environment and isolation:** this branch's Flask app on 127.0.0.1:5099 with the built React frontend, `DATA_DIR=/tmp/myai19-data` (fresh DB), `AI_PROXY_URL=http://127.0.0.1:5098` (fake proxy, slow mode 1 s/chunk for the API run, 3 s/chunk for the UI run, logs requests). Never touch :5000/:5001, containers or `backend/data`. Teardown: kill PIDs, delete the temp dir, compare ports/containers/git status to the snapshot.
Scripts: `scripts/fake_proxy.py`, `scripts/v19_api.py`, `scripts/ui.js`.
A "lone user message" chat (what Retry resumes from) is made through the real flow: send, wait for the reply, `DELETE` the assistant message.

| ID | Criterion | Scenario | Type | Method | Files | Expected |
|----|-----------|----------|------|--------|-------|----------|
| V1 | Resume while a turn runs is rejected | slow send running, then POST `/resume` | race | API + DB | chat/router.py | resume 400 `{"error": "a response is already in progress"}`; no new user or assistant row; the send finishes with 1 user + 1 assistant row |
| V2 | Send while a resume-started turn runs is rejected; resumes exclude each other | slow resume running, then a send; two resumes released together by a barrier | race | API + DB | chat/router.py, task_manager | the send gets 400 and stores nothing; of two simultaneous resumes exactly one 200 and one 400 |
| V3 | Normal resume and reattach still work | after the turn: a resume and a send; reattach GET during a running turn and after | regression | API | chat/router.py | both 200; reattach 200 `text/event-stream` while running, 204 after |
| V4 | Client shows the rejection as a toast; Retry normal | React UI: (a) Retry on a finished chat; (b) tab B (opened on the idle chat with a lone user message) clicks Retry while another request's resume is running | happy/race | browser + DB | send-turn.ts | (a) 1 user row, a new reply; (b) 400, the message shown once as a toast, no inline error row, the running turn completes with one reply |
| V5 | Legacy Cancel stops properly | `POST /api/chats/<id>/stop` during a running turn; and the popover's Cancel code path | failure/regression | API + node test | clarification-popover.js | stop 200, the chat is not left running (a new send accepted once the turn ended), popover test: Cancel calls `/stop`, never `/resume` |
| V6 | Regression | chat, task_manager, backend, tests dirs, ruff, vitest, typecheck, lint, build, node popover test | regression | CLI | all | only baseline failures |

### Results (2026-11-09)
Verified at HEAD 77a0908c1213e40eef728749b0129dfff4d2d677 plus uncommitted (hash prefixes): backend/chat/README.md 5ec7c3b3, backend/chat/router.py 47a83419, backend/chat/tests/test_router.py 17aaa9db, docs/standards/api.md f809f01f, frontend/src/features/chat/send-turn.test.ts f87520a8, frontend/src/features/chat/send-turn.ts 8d2e07ad, static/js/clarification-popover.js 4776bd9d, static/js/tests/test_clarification-popover.js 4683f311.
Isolation: app 127.0.0.1:5099 (DATA_DIR=/tmp/myai19-data, built React frontend), slow fake proxy 127.0.0.1:5098; :5000/:5001, containers and backend/data untouched. Teardown: PIDs killed, 5098/5099 free, temp dir removed, containers and git status identical to the snapshot.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | v1-v5-api.log: resume while a send ran gave 400 `{"error":"a response is already in progress"}`, rows unchanged; the send finished with 1 user + 1 assistant row |
| V2 | PASS | v1-v5-api.log: a send during a resume gave 400 and stored nothing; two simultaneous resumes gave `[200, 400]` and one reply |
| V3 | PASS | v1-v5-api.log: reattach 200 `text/event-stream` during a resume and 204 after; a normal send and a resume after the turn both 200 |
| V4 | PASS | v4-ui.log, ui-v4a-after-retry.png, ui-v4b-tabB-toast.png: (a) Retry on a finished chat: resume 200, 1 user row, a new reply; (b) tab B's Retry while another resume ran got 400, the message shown once (toast, no inline error row), the running turn completed with one reply; no console errors |
| V5 | PASS | v1-v5-api.log: `/stop` during a running turn 200, chat not left running, a send after it accepted; v6-regression.log: node popover tests (Cancel calls `/stop`, never `/resume`; failed stop notifies; declined confirm does nothing) |
| V6 | PASS | v6-regression.log: chat 145, task_manager 38, backend/tests 25, tests 32, ruff clean; vitest 282, typecheck clean, lint only the existing warning, node popover test 5 |

Verdict: verified. 6 of 6 pass, 0 FAIL, 0 BLOCKED. Not covered: the legacy Resume banner's inline error text and a live legacy clarification Cancel (needs a pending callback; covered by the node test and the stop API check).
Scripts: scripts/fake_proxy.py, v19_api.py, ui.js.
### Results (re-run 1, 2026-11-09)
Narrow re-run after review round 1 fixes (legacy popover failure notification and URL encoding; comments, docstring, line wrapping and tests elsewhere). HEAD 77a0908c1213e40eef728749b0129dfff4d2d677 plus uncommitted (hash prefixes): backend/chat/README.md 5ec7c3b3, backend/chat/router.py b0eea7c4, backend/chat/tests/test_router.py 16d2c907, docs/standards/api.md f809f01f, frontend/src/features/chat/send-turn.test.ts 6f04a11e, frontend/src/features/chat/send-turn.ts 10e668ea, static/js/clarification-popover.js fc7a22c4, static/js/tests/test_clarification-popover.js 8ac86cb8. No app was started (ports 5098/5099 free). Evidence in rerun1/ (router-diff.txt lists the router.py diff against 77a0908).

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS (carried forward) | first Results; the behaviour of `resume_chat` did not change since (router.py: comment, docstring and a local alias comment only; the guard code is the same) |
| V2 | PASS (carried forward) | first Results; same reason |
| V3 | PASS (carried forward) | first Results |
| V4 | PASS (carried forward) | first Results; send-turn.ts changed only by a comment and by wrapping the same condition |
| V5 | PASS | rerun1/v5-v6.log: node popover tests re-run, 6 pass (Cancel calls `/stop`, never `/resume`; a failed stop calls `showNotification("Stop failed", "Failed to stop the process.")` and still closes the popover; a declined confirm does nothing; the chat id is URL-encoded); the `/stop` API half is carried forward from the first Results (backend stop code unchanged) |
| V6 | PASS | rerun1/v5-v6.log: chat 146, task_manager 38, backend/tests 25, tests 32, ruff clean; vitest 282, typecheck clean, lint only the existing warning, build ok |

Verdict: verified. Latest status of every scenario PASS, 0 FAIL, 0 BLOCKED. Not covered: a live legacy clarification Cancel (needs a pending clarification callback) and a live re-run of V1-V4 on the final code (carried forward because their code paths are unchanged; the V6 suites cover the final code).

## Review history
### Round 1 - 2026-11-09
Verdict: Request changes (1 MAJOR). Scope: 8 uncommitted files vs 77a0908 (small mode, one Haiku reviewer given the Description, Acceptance criteria and the plan's Objective/Approach/Out of scope/Success criteria). Findings checked against the code; all static.
- R1-1 [MAJOR] static/js/clarification-popover.js:154-160 - the Cancel failure notification calls `showNotification(message, "error")` but the injected `showNotification` is `window.showAlert(title, message)` (modals.js:292, agent-renderers.js:697/810): the modal title becomes the message and the body the word "error"; my new test pinned the mismatch (the same shape exists in the older Confirm error call at line 127, untouched) - Static - Fixed: `showNotification('Stop failed', 'Failed to stop the process.')` (title, message as window.showAlert expects); tests written first and failed before the fix; clarification-popover.js, test_clarification-popover.js
- R1-2 [MINOR] backend/chat/tests/test_router.py - the resume refusal is only tested with an open response holding the claim; the `worker.is_alive()` branch of `claim_turn` reached from resume (a running task with no open response) is not covered - Static - Fixed: new test with a real TaskManager and a live mocked worker: 400 with no ChatHandler call, then 200 after the worker ends; test_router.py
- R1-3 [MINOR] frontend/src/features/chat/send-turn.ts:63 and send-turn.test.ts - added lines over Prettier's 100 columns (docs/standards/frontend.md; the two files already fail `prettier --check` at the base and 91 files do repo-wide, so only my added lines are in scope) - Static - Fixed: my added lines over 100 columns wrapped by hand (the files already fail prettier at the base, not reformatted); send-turn.ts, send-turn.test.ts
- R1-4 [MINOR] send-turn.ts:43/63 and router.py (send and resume routes) - the refusal is matched by exact message string on the client and the literal is duplicated on the server; the contract is only named as "docs/standards/api.md" in a comment - Static - Fixed: comment on TURN_IN_PROGRESS names the string as an API contract shared with both routes (a `code` field in the 400 body is a larger API change, not done); send-turn.ts
- R1-5 [MINOR] static/js/clarification-popover.js Cancel - Cancel via `/stop` also rolls back the partial assistant output after the last user message, sets `resume_suppressed`, and clears SSE chunks (`stop_chat`); the plan's Risks record this as intended but nothing in the code says so - Static - Fixed: popover comment states /stop also rolls back the partial reply and hides the resume banner; clarification-popover.js
- R1-6 [NIT] backend/chat/router.py:473 - the `turns = task_manager` alias comment is hard to parse - Static - Fixed: alias comment reworded, router.py
- R1-7 [NIT] backend/chat/router.py `resume_chat` docstring does not mention the new 400 - Static - Fixed: resume_chat docstring describes the 400, router.py
- R1-8 [NIT] static/js/clarification-popover.js:155 - the chat id is not URL-encoded in the stop URL (the React client encodes it) - Static - Fixed: chat id URL-encoded in the stop URL (new test); clarification-popover.js
Dismissed: none. Pre-existing: the older Confirm error call in the same file has the same title/message mix-up (noted in R1-1, not changed).

Resolution: 8 Fixed, 0 Rejected. Runtime behaviour changed by R1-1 and R1-8 (static/js/clarification-popover.js, legacy Cancel only); R1-2 to R1-7 are tests, comments, docstrings and line wrapping. The legacy Cancel code path is covered by the node tests; a live re-run of V5's popover check is not needed (V5's API part and V1-V4, V6 files are unchanged). Checks: chat 146, task_manager 38, backend/tests 25, tests 32, ruff clean; vitest 282, typecheck clean, lint only the existing warning, build ok; node popover test 6 pass.


## Log
- 2026-11-09: created (follow-up found while planning MYAI-2 to MYAI-16)
- 2026-11-09: plan validated, 3 Haiku rounds.
- 2026-11-09: linked blocked_by MYAI-7 (resume reuses MYAI-7's claim_turn and 400 toast branch)
- 2026-11-09: linked blocked_by MYAI-6 (React resume path is MYAI-6's resumeTurn)
- 2026-11-09: linked conflicts_with MYAI-22 (resume_chat body reads)
- 2026-11-09: linked blocks MYAI-35
- 2026-11-09: autopilot started (batch-autopilot)
- 2026-11-09: implemented, smoke tests pass (only baseline async-plugin failures)
- 2026-11-09: verified: 6 PASS, 0 FAIL, 0 BLOCKED
- 2026-11-09: review round 1: Request changes (1 MAJOR, 4 MINOR, 3 NIT)
- 2026-11-09: review round 1 resolved: 8 fixed (legacy popover change covered by node tests)
- 2026-11-09: re-verified after review fixes (narrow: V5, V6; V1-V4 carried forward): all PASS
- 2026-11-09: PR opened #61 (batch-autopilot: shipped, base develop)
- 2026-11-09: PR #61 merged into develop; closed
