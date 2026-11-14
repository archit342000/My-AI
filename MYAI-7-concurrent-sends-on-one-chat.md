---
id: MYAI-7
title: "N8: concurrent sends on one chat lose a reply"
status: done
created: 2026-11-08
updated: 2026-11-09
links:
  blocks: [MYAI-19, MYAI-35, MYAI-40]
  conflicts_with: [MYAI-6, MYAI-22]
  relates_to: [MYAI-44]
---

## Description
Report N8 (Medium). Two simultaneous completions on one chat both return 200, and the chat ends up with two user rows and no reply for one of them. The reattach path checks is_task_running, but a send while a turn is running is not rejected. Suggested fix: reject a second send to a chat with a running task with 400 'a response is already in progress' before the user message is stored; the client shows it as a toast. Not blocked.

## Acceptance criteria
- [x] A second send while a turn is running is rejected with 400 and stores no message
- [x] The client shows the rejection as a toast
- [x] Reattach still works

## Plan
**Date:** 2026-11-09  **Status:** Validated

### Objective
Make the chat send endpoint enforce one turn per chat. A send to a chat whose turn is running (or is being started by another request) is rejected with `400 {"error": "a response is already in progress"}` before anything is written, and the React client shows that as a toast. Today two concurrent sends both store a user row and the second request silently attaches to the first turn, so one user message never gets a reply.

### Context
- **Requirement:** Description and Acceptance criteria above. Code read at origin/develop `6a13e04` (`/tmp/myai-develop`).
- **Assumptions:**
  - The "send path" is `chat_completions` in `backend/chat/router.py`, which *is* the OpenAI-compatible endpoint: `openai_bp` is mounted at `/v1/chat` (`app.py`, `register_blueprint(openai_bp, url_prefix='/v1/chat')`) and the React client (`frontend/src/api/completions.ts` `streamCompletion`) and legacy UI (`static/script.js`) both POST `/v1/chat/completions`. There is no separate send path, so one guard covers both.
  - The guard applies to every `/v1/chat/completions` request with a `chatId`, not only those whose last message is `role: user`: every such request starts a turn (`ChatHandler.initiate_chat` -> `process_message`).
  - Status `400` as the ticket says. `docs/standards/api.md` lists no `409`; 400 with "fail before acting, no partial write" matches it.
  - Single server process (`app.py` `app.run(...)`, `task_manager` is an in-memory singleton), so an in-process lock is sufficient; this is the existing assumption of `TaskManager`.
- **Rules:** `AGENTS.md` (tests per changed file, `scripts/check.sh`, `ruff check .`, `log_event()`, keep component READMEs accurate, no masking errors); `docs/standards/api.md` (status codes, error body `{"error": "<short message>"}`, validate before acting, client and legacy UI kept in sync on contract changes); `docs/standards/testing.md` (1:1 tests, regression test per bug fix, deterministic, no sleeps); `docs/standards/frontend.md` (reuse `Toast`/`showToast`).
- **Current behaviour:**
  - `chat_completions` (`backend/chat/router.py`) validates `chatId`, then `db.ensure_chat_exists`, `db.add_message`, `db.update_last_user_id`, auto-title, and only then returns a `Response(generate_stream())`. The turn is started lazily inside the generator: `ChatHandler.initiate_chat` -> `process_message` (`backend/chat/handler.py`) calls `task_manager.start_task` only `if not task_manager.is_task_running(...)`, else logs `task_reattach` and subscribes to the running turn. That `else` branch is how the second send "succeeds" with no reply of its own.
  - Race: the window between storing the message and `start_task` spans the whole route plus the start of streaming, so a plain `is_task_running` check at the top of the route would still let two simultaneous requests both pass (neither task has started yet).
  - `TaskManager` (`backend/task_manager/manager.py`) holds `_active_tasks` under `self._lock` (an `RLock`); `is_task_running`, `start_task`, `pop_task`, `stop_task` exist. No notion of a turn that is starting.
  - `reattach_stream` (`GET /api/chats/<id>/stream`) returns 204 when `is_task_running` is false, else subscribes to `response_cache`. It does not start turns and is not touched.
  - Client: `apiRequest` (`frontend/src/api/client.ts`) throws `ApiError(status, body, message)` with the server's `error` string on non-2xx. `consume` in `frontend/src/features/chat/send-turn.ts` catches it, calls `useStreamStore.interrupt({kind:'error', ...})` (inline error row with Retry) and `showToast(message, 'error')`, then in `finally` invalidates the chat query and calls `finish()`. `ChatPage.tsx` re-attaches when the refetched chat has `is_running` (from `ChatHandler.get_history`). So today a 400 already toasts, but also leaves a misleading empty "error + Retry" turn.
  - Legacy UI (`static/script.js`, around the `/v1/chat/completions` fetch) throws `new Error(errData.error ...)` on `!response.ok` (around line 3035); its `catch (error)` (around line 3382) renders `API Error: <message>` in the reply bubble, so it shows the new message without changes. Its optimistic user bubble stays until reload; accepted, the legacy UI is not the default client.

### Approach
Add a per-chat **turn claim** to `TaskManager`: `claim_turn(chat_id) -> bool` atomically (under `self._lock`) returns False if a task for the chat is alive or a claim is already held, else records the claim and returns True. `release_turn_claim(chat_id)` drops it. `chat_completions` claims first thing after `chatId` validation, before any DB write; on False it logs and returns 400. On success the claim is released by `Response.call_on_close` (Werkzeug calls the response iterable's `close()` when the stream ends or the client disconnects), and explicitly in the route's `except` path if the route fails before returning the response. While the claim is held the turn is either starting (claim blocks) or running (`is_task_running` blocks); after release the running task alone still blocks. `is_task_running` is unchanged, so `process_message`, `reattach_stream`, `get_history` and `resume_chat` keep their behaviour.

Client: in `consume`, treat `ApiError` with status 400 (a pre-start rejection, nothing stored) as toast-only: show the toast, skip `interrupt`. The existing `finally` refetch then shows the other turn and `ChatPage` re-attaches to it if still running.

Rejected alternatives:
- `is_task_running` check at the top of the route: does not close the race (task starts in the generator, after the write).
- Start the task eagerly in the route under the lock: larger refactor of the handler/stream flow and changes when mode flags are synced; not needed.
- DB-level uniqueness or a "pending" DB row: needs a migration for an in-memory concern.
- Claim with a TTL: `call_on_close` gives a deterministic release; a TTL adds a timing knob and a config value.

### Steps
#### Step 1: Turn claim in TaskManager
- **Files:** `backend/task_manager/manager.py` (modify): `TaskManager.__init__` (new `_claimed_turns: Set[str]`), new methods `claim_turn`, `release_turn_claim`.
- **Change:** `claim_turn` takes `self._lock`, returns False if `chat_id` is in `_claimed_turns` or a live worker exists for it, otherwise adds the claim and returns True. `release_turn_claim` takes the lock and discards the claim (no error if absent). Docstrings say the claim covers the window between accepting a send and the task starting.
- **Verification:** new tests in `backend/task_manager/tests/test_manager.py`: claim succeeds once, second claim fails, claim fails while a (mocked) live worker exists, succeeds after release, release of an unclaimed chat is a no-op, and a concurrency test where N threads claim the same chat through a `threading.Barrier` and exactly one wins (deterministic, no sleeps).

#### Step 2: Guard the send route
- **Files:** `backend/chat/router.py` (modify): `chat_completions`.
- **Change:** right after the `chatId` check and before `log_event("api_chat_completions", ...)`/`db.ensure_chat_exists`, call `task_manager.claim_turn(chat_id)`; on False, `log_event("chat_send_rejected_turn_in_progress", {"chat_id": chat_id})` and return `jsonify({"error": "a response is already in progress"}), 400`. On success, build the `Response` as today and register `response.call_on_close(lambda: task_manager.release_turn_claim(chat_id))` before returning it. In the existing `except Exception` branch, release the claim before returning 500. Nothing else in the route changes.
- **Verification:** tests in `backend/chat/tests/test_router.py` (patching `backend.chat.router.task_manager`, as `test_reattach_stream` does): claim False -> 400 with the exact body and `db.add_message`/`db.ensure_chat_exists` never called; claim True -> 200 stream as today and `release_turn_claim` called once after the response is consumed and closed; route exception -> 500 and claim released. Update `test_chat_completions`, `test_chat_completions_stream_error`, `test_chat_completions_with_images`, `test_chat_completions_without_images` so the patched `task_manager.claim_turn` returns True (they otherwise hit the real singleton).

#### Step 3: Regression test for two sends at once
- **Files:** `backend/chat/tests/test_router.py` (modify).
- **Change:** a regression test that uses a real `TaskManager()` instance (constructed with `threading.Thread` patched, as the `manager` fixture in `backend/task_manager/tests/test_manager.py` does, so no cleanup thread runs) patched in as `backend.chat.router.task_manager`, with `ChatHandler` and `db` mocked as in the existing tests: first POST is accepted and its response is held open (not closed); a second POST to the same `chatId` returns 400 and `db.add_message` was called exactly once; after the first response is closed, a third POST is accepted. Fails on current develop (second POST returns 200).
- **Verification:** `EMBEDDING_URL="http://mock" AI_URL="http://mock" AI_API_KEY="dummy" PYTHONPATH=. venv/bin/python -m pytest backend/chat/tests/test_router.py backend/task_manager/tests/test_manager.py`.

#### Step 4: Reattach unchanged
- **Files:** none changed; `backend/chat/tests/test_router.py` `test_reattach_stream` stays as is.
- **Change:** confirm `reattach_stream` and `ChatHandler.process_message` still use only `is_task_running` (a held claim must not make reattach return a stream or 204 differently). Add one router test: with a real `TaskManager` holding a claim and no worker, `GET /api/chats/<id>/stream` still returns 204 (same as before), proving the claim does not leak into reattach.
- **Verification:** existing `test_reattach_stream` and the new test pass.

#### Step 5: Client shows the rejection as a toast only
- **Files:** `frontend/src/features/chat/send-turn.ts` (modify): `consume`; imports `ApiError` from `frontend/src/api/client.ts`.
- **Change:** in the `catch`, before the generic error branch, if `err instanceof ApiError && err.status === 400`, call `showToast(err.message, 'error')` and do not call `store.interrupt(...)`. The `finally` (query invalidation, `finish()`) is unchanged, so the refetch shows the running turn and `ChatPage` re-attaches via `is_running`.
- **Verification:** new tests in `frontend/src/features/chat/send-turn.test.ts` using `mockCompletion` returning `new Response(JSON.stringify({error:'a response is already in progress'}), {status:400})`: a toast with that message exists, `useStreamStore.getState().interrupted` is null, `chatId` is null after the call. Existing F-14 error tests still pass. `cd frontend && npm run typecheck && npm run lint && npm run test`.

#### Step 6: Docs
- **Files:** `docs/standards/api.md` (modify, "Streaming (SSE)" section); `backend/task_manager/README.md` (modify, "Flow"/"Usage & Conventions": the turn claim); `backend/chat/README.md` (modify: its Flow step 1, "`router.py` receives a chat request").
- **Change:** api.md: one bullet stating that one turn runs per chat and `POST /v1/chat/completions` returns `400 {"error": "a response is already in progress"}`, storing nothing, while a turn for that chat is running or starting; re-attach with `GET /api/chats/<id>/stream`. READMEs: one line each naming `claim_turn`/`release_turn_claim` and who calls them, linking to api.md for the contract (no repeated detail, per `docs/standards/docs.md`).
- **Verification:** `venv/bin/python -m pytest tests` (docs guardrails) passes.

#### Step 7: Full check
- **Files:** none.
- **Change:** run `venv/bin/python -m ruff check .` and `scripts/check.sh`.
- **Verification:** all suites PASS.

### Tests
- Backend: `backend/task_manager/tests/test_manager.py` (claim/release unit + threaded race), `backend/chat/tests/test_router.py` (400 path, release on close and on error, two-send regression, reattach unaffected; existing completion tests patched to claim True). Run per `docs/standards/testing.md`: the two files, then `pytest backend`, then `pytest tests`.
- Frontend: `frontend/src/features/chat/send-turn.test.ts`; `npm run typecheck`, `lint`, `test`, `build` in `frontend/`.
- Gate: `scripts/check.sh`.
- Live check (for the verify stage, not here): two simultaneous `curl` POSTs to `/v1/chat/completions` for one chat against a throwaway `DATA_DIR`; one 200 stream, one 400, one user row; then a reattach `GET` returns the stream.

### Risks and open questions
- **Release depends on `close()`.** If a WSGI server never closes the iterable, the claim would stick until restart. Werkzeug's dev server (used by `app.py`) and the Flask test client call `close()`; the regression test asserts release on close. Mitigation if needed later: release also on task start. Accepted.
- **`resume_chat` is not claimed.** A resume racing a send that has claimed but not yet started its task could still start first, and the send would then attach to it. Requires clicking Resume and sending in the same instant (Resume is only offered when nothing is running). Out of the ticket's scope; candidate follow-up ticket.
- **Message in the composer.** On rejection the typed text is not restored (the pending row is dropped by `finish()`). Accepted: the toast explains why, and the running turn is shown. Restoring the draft would be a separate UX change.
- **Resend right after Stop.** Stop aborts the fetch (claim released on close) and calls `POST /api/chats/<id>/stop`, but the worker can stay alive briefly until it sees the interrupt; a send in that window gets the 400 toast. This comes from `is_task_running`, not the claim, and is the intended rule (today that send would silently attach to the dying turn). Accepted; the toast tells the user to retry.
- **Environment.** Commands assume `venv/bin/python` exists in the implementation worktree (`AGENTS.md` rule 3); create it from `requirements-dev.txt` if missing.
- **Other 400s from completions** (`chatId is required`) now also skip the inline error row and only toast. Acceptable, since every 400 there means nothing was stored or started.
- No blocking open questions.

### Success criteria
- [ ] A second `POST /v1/chat/completions` for a chat with a running or starting turn returns 400 `{"error": "a response is already in progress"}` and writes no message (unit + regression tests).
- [ ] Two simultaneous sends produce exactly one stored user message and one turn (threaded claim test and router regression test).
- [ ] The React client shows the rejection as an error toast with no inline error/Retry row (send-turn test).
- [ ] Reattach behaves as before (existing and new reattach tests).
- [ ] `ruff check .` and `scripts/check.sh` pass; `docs/standards/api.md` and the touched READMEs describe the guard.

### Validation log
- **Round 1** (Haiku Explore): verdict PASS, 0 BLOCKING, 6 MINOR. My judgement: PASS. I checked all six against the repo and all are valid:
  1. Legacy UI display path not cited. Valid: `static/script.js` `catch (error)` around line 3382 renders `API Error: ...`. Context updated.
  2. Step 6 `backend/chat/README.md` edit was conditional. Valid: Flow step 1 names `router.py`. Made unconditional.
  3. Resend-after-Stop UX not in Risks. Valid: `stop_task` does not pop the worker; `worker.py` pops in its own `finally`. Risk added.
  4. The Step 3 real `TaskManager()` would start the cleanup thread. Valid: the `manager` fixture patches `threading.Thread`. Step 3 now does the same.
  5. No venv in `/tmp/myai-develop`. Valid as an environment note, not a plan defect. Risk added.
  6. Docs repetition across api.md and the READMEs. Valid per `docs/standards/docs.md`. Step 6 now keeps the contract in api.md and puts one linked line in each README.
- **Round 2** (Haiku Explore, scoped to the changes): verdict PASS, no issues. My judgement: PASS. Spot-checked `static/script.js` 3382-3399, the `manager` fixture in `test_manager.py`, and `backend/chat/README.md` Flow. All match. No valid BLOCKING or MINOR issues remain, so I stopped at 2 rounds.

## Implementation notes
### Autopilot run (2026-11-09)
- Mode: automatic (batch-autopilot batch 2, item 1/3)
- Branch: bugfix/one-turn-per-chat  PR base: develop  Starting commit: 6307ffb
- Dirty before start: none
- Work files: backend/task_manager/manager.py, backend/task_manager/tests/test_manager.py, backend/task_manager/README.md, backend/chat/router.py, backend/chat/tests/test_router.py, backend/chat/README.md, docs/standards/api.md, frontend/src/features/chat/send-turn.ts, frontend/src/features/chat/send-turn.test.ts
- Counters: fix 0/10, review 1/5, re-verify 1
- Last completed stage: 6 ship  Next: none
- Hard blocker: none
- WIP commit: none

### Autopilot decisions (2026-11-09)
- Stage 1: plan already Validated (2 rounds); reused, not re-planned (user said these tickets are planned). The plan was written against 6a13e04; develop is now 6307ffb (MYAI-6/10/11 merged), so line numbers may differ.

### Baseline (2026-11-09)
At develop 6307ffb: backend/task_manager/tests 35 pass; backend/chat/tests 113 pass; frontend vitest 276 pass (48 files). Backend suites elsewhere fail only on async tests (pytest-asyncio is not installed in the venv): database/tests 2, tools/tests 6, research_agent 2, tavily_mcp 5, code_runner_mcp.

### Implementation progress
- [x] Step 1: turn claim - backend/task_manager/manager.py (`claim_turn`, `release_turn_claim`), tests in task_manager/tests/test_manager.py (incl. 8-thread race)
- [x] Step 2: guard the send route - backend/chat/router.py; router tests for 400, release on close, release on error
- [x] Step 3: regression test with a real TaskManager (two sends, third after close) - backend/chat/tests/test_router.py
- [x] Step 4: reattach unchanged - test_reattach_stream_ignores_a_held_claim
- [x] Step 5: client toast-only on 400 - frontend/src/features/chat/send-turn.ts (+ tests)
- [x] Step 6: docs - docs/standards/api.md, backend/task_manager/README.md, backend/chat/README.md
- [x] Step 7: full checks (see Smoke test)
Branch: bugfix/one-turn-per-chat
Deviations: (1) the four existing completion tests are kept off the real singleton's claim through one autouse fixture in test_router.py instead of four per-test patches; (2) `consume` is shared with `resumeTurn` (added by MYAI-6 after this plan was written); the toast-only 400 rule is limited to `sendTurn` (review R1-1), so Retry keeps its inline error row for a 400.

### Smoke test (2026-11-09)
task_manager 38 pass; chat 118 pass; backend/tests 25; tests 32; ruff clean; `scripts/check.sh --python-only`: only the baseline async-plugin failures; frontend vitest 278 pass, typecheck clean, lint only the existing forms.tsx warning, build ok. The new regression test was not shown failing on develop by reverting (it asserts the second POST is 400, which develop returns as 200).

Status on develop (checked at e327094, 2026-11-08): Partly present: reattach checks is_task_running (backend/chat/router.py reattach_stream); the send path has no guard (chat_completions persists the user message without it).

PR: https://github.com/archit342000/My-AI/pull/58, branch bugfix/one-turn-per-chat, base develop

## Verification
### Verification plan (2026-11-09, light form: ~40 changed source lines in 4 files, plus concurrency)
**Diff base:** 6307ffb. **Scope:** one turn per chat: `claim_turn`/`release_turn_claim` (task_manager), the guard in `POST /v1/chat/completions`, client toast-only on a 400, docs. Out of scope: `resume_chat` is not claimed, restoring the composer draft.
**Environment and isolation:** real Flask app from this branch on 127.0.0.1:5099 with the built React frontend, `DATA_DIR=/tmp/myai7-data` (fresh DB), `AI_PROXY_URL=http://127.0.0.1:5098` (fake inference proxy with a slow streaming mode: ~1 s per chunk, 6 chunks, logs every request). Never touch :5000/:5001, containers or `backend/data`. Teardown: kill both PIDs, delete the temp dir, compare ports/containers/git status to the snapshot.
Scripts: `scripts/fake_proxy.py` (slow fake upstream), `scripts/v7_api.py` (concurrency driver: threads + DB checks), `scripts/ui.js` (Playwright, two tabs).

| ID | Criterion | Scenario | Type | Method | Files | Expected |
|----|-----------|----------|------|--------|-------|----------|
| V1 | One turn per chat | Fire two POSTs to `/v1/chat/completions` for one chat at the same instant (barrier-synchronised threads), slow upstream | happy/race | API + DB | task_manager/manager.py, chat/router.py | exactly one 200 stream and one 400 `{"error": "a response is already in progress"}`; one user row; one assistant reply; upstream got one request |
| V2 | Rejected send stores nothing | While a turn streams, send again (sequential) | failure | API + DB | chat/router.py | 400, same body, user row count unchanged |
| V3 | Reattach still works | During the running turn `GET /api/chats/<id>/stream`; after it ends the same GET | regression | API | chat/router.py | 200 `text/event-stream` carrying chunks while running, 204 after |
| V4 | Claim released | After the first turn ends, send again; also: send, drop the connection mid-stream, immediate send, then send after the turn finished | edge | API + DB | task_manager, chat/router.py | next send 200; after a client disconnect the still-running turn keeps rejecting (400) until it ends, then accepts |
| V5 | Independent chats | Two sends to two different chats at once | edge | API | task_manager | both 200 |
| V6 | Client shows a toast | React UI, same chat open in two tabs: send in tab A (slow reply), send in tab B | happy | browser | send-turn.ts | tab B shows a toast with the message, no inline error/Retry row; tab A's reply completes; one user row |
| V7 | Regression | task_manager, chat, tests dirs, ruff, vitest, typecheck, lint, build | regression | CLI | all | only baseline failures |

### Results (2026-11-09)
Verified at HEAD 6307ffbd5f06dd63c98a6b99075723386261e158 plus uncommitted (hash prefixes): backend/chat/README.md 6be42d41, backend/chat/router.py 035e5435, backend/chat/tests/test_router.py e264568f, backend/task_manager/README.md 5c7cbd56, backend/task_manager/manager.py f4684305, backend/task_manager/tests/test_manager.py a1193f82, docs/standards/api.md 2c079033, frontend/src/features/chat/send-turn.test.ts 0afd407f, frontend/src/features/chat/send-turn.ts 6396b7ca.
Isolation: app 127.0.0.1:5099 (DATA_DIR=/tmp/myai7-data, built React frontend), slow fake inference proxy 127.0.0.1:5098; :5000/:5001, containers and backend/data untouched. Teardown: both PIDs killed, 5098/5099 free, temp dir removed, containers and git status identical to the snapshot.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | v1-v5.log: two barrier-synchronised sends to one chat gave one 200 and one 400 `{"error":"a response is already in progress"}`; 1 user row, 1 assistant row, 1 upstream request |
| V2 | PASS | v1-v5.log: send while a turn streams: 400 with that body, user rows 1 before and after |
| V3 | PASS | v1-v5.log: `GET /api/chats/<id>/stream` during the turn 200 `text/event-stream` with chunks; after it ended 204 |
| V4 | PASS | v1-v5.log: send after the first turn finished 200; after a dropped connection the immediate send is 400 (the abandoned turn is still running), and 200 once it ended |
| V5 | PASS | v1-v5.log: two different chats at once both 200, one user row each |
| V6 | PASS | v6-ui.log, ui-v6-tabB-toast.png, ui-v6-tabA-done.png: second tab's send got 400; the message appears once on the page (a toast, no inline error row); tab A's reply completed; 2 user and 2 assistant rows (one per accepted send) |
| V7 | PASS | v7-regression.log: task_manager 38, chat 118, backend/tests 25, tests 32, ruff clean; vitest 278, typecheck clean, lint only the existing warning |

Verdict: verified. 7 of 7 pass, 0 FAIL, 0 BLOCKED. Browser console errors: none.
Harness notes (not product defects): the first two V6 attempts failed because of the harness. In attempt 1 the 6 s turn had already finished when tab B sent (logs kept as v6-ui-attempt1-*.log); in attempt 2 tab B opened the chat while the turn ran, so the page correctly re-attached and disabled sending (v6-ui-attempt2-*.log). The final run opens tab B on an idle chat, then starts the slow turn in tab A.
Observed, not part of this change: a tab that did not start the turn shows "Retry response" under the in-flight user message; clicking it calls `/resume`, which is not claimed (already listed in the plan's risks).
Not covered: `resume_chat` racing a send, restoring the typed draft after a rejection.
Scripts: scripts/fake_proxy.py (slow mode), v7_api.py, ui.js.
### Results (re-run 1, 2026-11-09)
Re-run after review round 1 fixes (router.py bound manager, send-turn.ts toast-only 400 limited to sendTurn, tests, docs). HEAD 6307ffbd5f06dd63c98a6b99075723386261e158 plus uncommitted (hash prefixes): backend/chat/README.md 6be42d41, backend/chat/router.py 36a048d6, backend/chat/tests/test_router.py b1401c6f, backend/task_manager/README.md 490421d6, backend/task_manager/manager.py 65a0a24e, backend/task_manager/tests/test_manager.py b435cc80, docs/standards/api.md b37a3583, frontend/src/features/chat/send-turn.test.ts 37039815, frontend/src/features/chat/send-turn.ts e70625f7. Frontend rebuilt first; fresh throwaway state (app 5099, fake proxy 5098); ports 5098/5099 free afterwards, containers and git status identical to the snapshot. Evidence in rerun1/.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | rerun1/v1-v5.log: two simultaneous sends gave 200 + 400, one user row, one reply, one upstream request |
| V2 | PASS | rerun1/v1-v5.log |
| V3 | PASS | rerun1/v1-v5.log |
| V4 | PASS | rerun1/v1-v5.log |
| V5 | PASS | rerun1/v1-v5.log |
| V6 | PASS | rerun1/v6-ui.log, ui-v6-*.png: tab B got 400, message shown once (toast only), tab A's reply completed, 2 user and 2 assistant rows; no console errors |
| V7 | PASS | rerun1/v7-regression.log: task_manager 38, chat 119, backend/tests 25, tests 32, ruff clean; vitest 278, typecheck clean, lint only the existing warning |

Verdict: verified. 7 of 7 pass, 0 FAIL, 0 BLOCKED. Retry (`/resume`) keeping its inline row for a 400 is covered by the restored unit test (no live scenario).

## Review history
### Round 1 - 2026-11-09
Verdict: Request changes (1 MAJOR). Scope: 9 uncommitted files vs 6307ffb (small mode, one Haiku reviewer given the Description, Acceptance criteria and the plan's Objective/Approach/Out of scope/Success criteria). Findings checked against the code; all static.
- R1-1 [MAJOR] frontend/src/features/chat/send-turn.ts:58 - the toast-only 400 rule is in the shared `consume`, so it also changes Retry (`resumeTurn`, `/resume` 400 "No user message found to resume from."), and the existing MYAI-6 resume test was edited (400 -> 500) instead of keeping that behaviour covered - Static - Fixed: toast-only 400 limited to sendTurn via a `refusalIsToastOnly` option on consume, original resume test (400 -> interrupted row + toast) restored; send-turn.ts, send-turn.test.ts
- R1-2 [MINOR] backend/task_manager/manager.py:81-83 and README.md:32 - docs say the claim covers the time until the task starts, but the router releases it only when the response closes (or on route failure) - Static - Fixed: claim_turn docstring and task_manager README describe the real lifetime; manager.py, README.md
- R1-3 [MINOR] backend/task_manager/tests/test_manager.py - the 8-thread race test would almost always pass under the GIL even without the lock; it is a smoke test and should say so - Static - Fixed: test comment says it is a smoke test; test_manager.py
- R1-4 [MINOR] backend/chat/tests/test_router.py test_reattach_stream_ignores_a_held_claim - with no running task, reattach is 204 with or without a claim, so it does not show reattach working during a running turn with a claim held; unexplained response_cache patch - Static - Fixed: two reattach tests (held claim without a task = 204; live worker plus held claim = 200 stream), unexplained patch dropped; test_router.py
- R1-5 [MINOR] backend/chat/router.py:424 - the close callback looks up the module-global `task_manager` at close time; bind the manager used for the claim - Static - Fixed: the manager that took the claim is bound once and used for the close callback and the except path; router.py
- R1-6 [NIT] docs - the client's toast-only rule for a 400 exists only in a code comment; mention it next to the api.md contract - Static - Fixed: api.md says the client shows a toast
Dismissed: reviewer finding "claim released only after the response closes, so an immediate resend can get a 400 for a few milliseconds": by design and described in the plan's Risks (resend right after Stop/finish); a live worker blocks for the same moment even without the claim; the user sees a toast, no data is lost; V4 shows the claim is released on close.

Resolution: 6 Fixed, 0 Rejected (1 reviewer finding dismissed earlier in the round with evidence). Runtime behaviour changed by R1-1 (frontend/src/features/chat/send-turn.ts: a 400 is toast-only for sendTurn only, resume keeps its inline row) and R1-5 (backend/chat/router.py): live re-verify of V1, V2, V4 and V6 needed. Checks: task_manager 38, chat 119, backend/tests 25, tests 32, ruff clean; vitest 278, typecheck clean, lint only the existing warning, build ok.


## Log
- 2026-11-08: created from reports/full-scope-final-report-2026-11-08.md
- 2026-11-09: plan validated, 2 rounds
- 2026-11-09: linked blocks MYAI-19 (resume reuses MYAI-7's claim_turn and 400 toast branch)
- 2026-11-09: linked conflicts_with MYAI-6 (chat_completions and consume in send-turn.ts)
- 2026-11-09: linked conflicts_with MYAI-22 (chat_completions body read)
- 2026-11-09: linked blocks MYAI-35
- 2026-11-09: linked blocks MYAI-40
- 2026-11-09: autopilot started (batch-autopilot)
- 2026-11-09: implemented, smoke tests pass (only baseline async-plugin failures)
- 2026-11-09: verified: 7 PASS, 0 FAIL, 0 BLOCKED
- 2026-11-09: review round 1: Request changes (1 MAJOR, 4 MINOR, 1 NIT; 1 dismissed)
- 2026-11-09: review round 1 resolved: 6 fixed; runtime files changed, re-verify needed
- 2026-11-09: re-verified after review fixes: 7 PASS, 0 FAIL, 0 BLOCKED
- 2026-11-09: PR opened #58 (batch-autopilot: shipped, base develop)
- 2026-11-09: linked relates_to MYAI-44 (batch 2 follow-ups)
- 2026-11-09: PR #58 merged into develop; closed
