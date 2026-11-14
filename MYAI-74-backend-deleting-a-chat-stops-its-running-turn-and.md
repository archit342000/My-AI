---
id: MYAI-74
title: "Backend: deleting a chat stops its running turn, and /stop answers only once the turn has ended"
status: done
created: 2026-11-10
updated: 2026-11-10
links:
  relates_to: [MYAI-73]
---

## Description
Two server-side gaps found in the race pass of the frontend audit (MYAI-52, Verification, "Race pass 2026-11-10", findings A-87 and A-91). They are outside the frontend epic MYAI-53, which excludes backend changes; MYAI-73 works around both from the React client only.

1. **Delete does not stop a turn.** `DELETE /api/chats/<id>` (`backend/chat/router.py`, the handler that ends in `db.delete_chat` and `FileSystemChannelManager.release_channel`) removes the chat while its task keeps running: the server generates the whole reply for a chat that no longer exists (17s in the test, `race2.mjs` F). Any client that does not stop first (legacy UI, a second tab, the API) triggers it. `DELETE /api/chats` (clear all) has the same shape.
2. **`/stop` answers before the turn has ended.** `stop_chat` calls `task_manager.stop_task`, which only signals the worker (`backend/task_manager/manager.py` `stop_task`, `worker.py` `stop`), then rolls back and answers. `claim_turn` refuses while the worker is alive, so a Retry or send right after the answer can get 400 "a response is already in progress", and `GET /api/chats/<id>` can still report `is_running: true`. Messages the dying worker writes after the rollback are also possible (not observed; to check).

Evidence and scripts: `~/.claude/tickets/My-AI/MYAI-52-evidence/` (`scripts/race2.mjs`, cases F, S1, S2, N).

## Acceptance criteria
- [x] Deleting a chat with a running turn stops the turn; no task, stream cache or task-state file is left for the deleted chat, and nothing is written for it afterwards
- [x] Clearing all chats stops every running turn of that user first
- [x] When `POST /api/chats/<id>/stop` answers, the turn has ended: an immediate send or resume is accepted and `GET /api/chats/<id>` reports `is_running: false`, with a bounded wait and a defined answer if the worker does not exit in time
- [x] After a stop the chat holds nothing written by the stopped turn after the rollback
- [x] `docs/standards/api.md` and the component README describe the new behaviour; tests cover both paths

## Plan
**Date:** 2026-11-10  **Status:** Validated - minors logged

### Objective
Make the server end a chat's turn before it deletes the chat, and make `/stop` answer only after the turn's worker has exited (within a bounded wait), so no turn runs for a deleted chat and a Retry right after Stop is accepted.

### Context
- **Requirement:** this ticket's Description and Acceptance criteria.
- **Rules:** `AGENTS.md` (read the component README and keep it accurate; every source file has a matching test; `venv/bin/python`; configuration in `backend/config.py`; `db` from `backend.database`; `log_event()`; do not mask errors; run `scripts/check.sh` and `ruff check .`); `docs/standards/api.md` (SSE section: one turn per chat, the "a response is already in progress" refusal, `POST /api/chats/<id>/stop`); `docs/standards/testing.md` (each suite in its own pytest process).
- **Current code:**
  - `backend/task_manager/manager.py` `TaskManager`: `stop_task` adds the id to `interrupted_tasks` and calls `worker.stop()` under `_lock`; it does not wait. `is_task_running` and `claim_turn` treat a chat as busy while `worker.is_alive()`. `pop_task` (called from the worker's `finally`) takes `_lock`.
  - `backend/task_manager/worker.py` `TaskWorker.stop`: cancels the loop's asyncio tasks from another thread. `backend/task_manager/executor.py` `TaskExecutor`: `_process_chunk` raises `CancelledError` when the chat is flagged; `run`'s `finally` removes the task-state file and clears the stream cache.
  - `backend/chat/router.py`: `stop_chat` calls `stop_task`, then `db.rollback_to_last_user_message`, clears the stream cache, resets research state, cleans clarification callbacks, sets `resume_suppressed`, and answers `{"status": "success"}`. `remove_chat` deletes the chat's files, the chat row and releases the file-system channel without touching the task. `clear_all_chats` calls `db.delete_all_chats(current_user_id())` only. `discard_research_endpoint` also calls `stop_task` without waiting.
  - `backend/database/wrapper/chat_ops.py`: `get_chat_owner(chat_id)` returns the owner or `None`.
- **Tests today:** `backend/task_manager/tests/test_manager.py`, `backend/chat/tests/test_router.py` (`test_stop_chat`, `test_lists_and_delete_all_are_scoped_to_the_caller`), `backend/tests/test_config.py`.
- **Evidence:** MYAI-52 race pass (`race2.mjs` F: the reply is generated to the end after the delete; S1/S2: a request right after the stop is refused; C: `GET` reports `is_running: true` after the stop).

### Approach
- **Wait in the manager.** New `TaskManager.stop_task_and_wait(chat_id, timeout=None) -> bool`: signals exactly as `stop_task` does, then joins the worker thread outside `_lock` (the worker's `finally` needs the lock) for at most `timeout` seconds (default `config.TASK_STOP_WAIT_SECONDS`, new, env-overridable, default 5). Returns true when there was no worker or it has exited. `stop_task` stays for callers that must not wait. New `running_chat_ids() -> list[str]` returns a snapshot of chats with a live worker. New `forget_chat(chat_id)` removes what the manager keeps for a chat that is going away: the id in `interrupted_tasks` and the files `tasks/<chat_id>.json` (also left by `recover_tasks` as `needs_resume` with no live worker) and `tasks/<safe id>_state.json` (the two paths `discard_research_endpoint` removes today, the second built with the same id sanitisation, `re.sub(r'[^a-zA-Z0-9_\-]', '', chat_id)`).
- **`/stop` rolls back after the worker has exited.** `stop_chat` calls `stop_task_and_wait` first, so the rollback, the cache clear and the callback cleanup run after the worker's last write. The answer gains a field: `{"status": "success", "stopped": true}`; when the wait runs out it still rolls back as today, answers `"stopped": false` and logs `chat_stop_timeout`. The status code stays 200, so existing clients are unaffected.
- **Delete stops first, and refuses while a turn is still ending.** `remove_chat` calls `stop_task_and_wait` after the owner check and before any cleanup. When the worker has exited it cleans the chat's clarification callbacks and stream cache, continues as today, and calls `forget_chat`. When the wait runs out it deletes nothing, logs `chat_delete_stop_timeout` and answers `409 {"error": "The chat is still stopping its response; try again in a moment."}`: a live worker could otherwise write for a chat that no longer exists. `clear_all_chats` takes the caller's chat ids from `db.get_all_chats(current_user_id())`, signals every one that is in `running_chat_ids()` with `stop_task`, then waits for each with `stop_task_and_wait` against one shared deadline of `TASK_STOP_WAIT_SECONDS` (so the request waits at most that long in total); if any is still alive it deletes nothing, logs `chat_clear_all_stop_timeout` and answers the same 409; otherwise it cleans the clarification callbacks and stream cache of each chat it stopped, runs `db.delete_all_chats`, and calls `forget_chat` for each id.
- **Rejected:** blocking without a limit (a worker stuck in a long model or tool call would hang the request); deleting anyway on a timeout (the worker could write rows for a deleted chat); answering 409 from `/stop` on a timeout (clients treat a non-200 as "stop failed" although the rollback happened); killing the worker thread (Python has no safe way).

### Out of scope
- `discard_research_endpoint`: it has the same signal-without-wait shape but is not part of this ticket's requirement; noted under Risks.
- Making a worker blocked in a synchronous call cancellable sooner.
- Frontend changes: the React client's handling is MYAI-73; it needs nothing from this ticket and may later drop its repeat.

### Steps
#### Step 1: Configuration value
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/config.py` (modify: `TASK_STOP_WAIT_SECONDS`), `backend/tests/test_config.py` (modify)
- **Change:** add the setting (float, env `TASK_STOP_WAIT_SECONDS`, default 5) in the timeouts section of `backend/config.py` (next to `FILE_SYSTEM_CHANNEL_ACQUIRE_TIMEOUT`).
- **Verification:** the config test reads the default and an overridden value.

#### Step 2: Manager: stop and wait, running ids
- **Status:** todo
- **Depends on:** 1
- **Files:** `backend/task_manager/manager.py` (modify: `stop_task_and_wait`, `running_chat_ids`, `forget_chat`), `backend/task_manager/tests/test_manager.py` (modify), `backend/task_manager/README.md` (modify: Interruption step and conventions)
- **Change:** as in Approach ("Wait in the manager").
- **Verification:** unit tests with a real `TaskWorker` on a small generator: after `stop_task_and_wait` returns true, `is_task_running` is false and `claim_turn` succeeds; a generator held by a `threading.Event` (no sleeps) with a short timeout returns false, and true once the event is set; no worker returns true at once; the call does not deadlock with the worker's `pop_task`; `running_chat_ids` lists only live workers; `forget_chat` removes both files (including a `needs_resume` file with no worker) and the interrupted flag, and is a no-op when nothing exists.

#### Step 3: `/stop` waits, then rolls back
- **Status:** todo
- **Depends on:** 2
- **Files:** `backend/chat/router.py` (modify: `stop_chat`), `backend/chat/tests/test_router.py` (modify)
- **Change:** as in Approach ("`/stop` rolls back after the worker has exited").
- **Verification:** router tests: the wait is called before `rollback_to_last_user_message` (call order asserted); the answer is 200 with `stopped: true`; with the wait returning false the rollback still runs, the answer has `stopped: false` and `chat_stop_timeout` is logged; another user's chat still gets the 404 from `require_chat_owner` and nothing is stopped.

#### Step 4: Delete and clear-all stop first
- **Status:** todo
- **Depends on:** 2
- **Files:** `backend/chat/router.py` (modify: `remove_chat`, `clear_all_chats`), `backend/chat/tests/test_router.py` (modify)
- **Change:** as in Approach ("Delete stops first").
- **Verification:** router tests: deleting a chat calls the wait before `db.delete_chat`, cleans the callbacks and stream cache and calls `forget_chat`; on a timeout the answer is 409, `db.delete_chat` is not called and `chat_delete_stop_timeout` is logged; clear-all stops only the caller's running chats (a second user's running chat is not signalled) before `db.delete_all_chats`, and with one still alive answers 409, deletes nothing and logs `chat_clear_all_stop_timeout`.

#### Step 5: Contract docs and full checks
- **Status:** todo
- **Depends on:** 3, 4
- **Files:** `docs/standards/api.md` (modify: SSE section: `/stop` answers after the turn has ended, the `stopped` field and the timeout case; deleting a chat or all chats stops running turns first, and the 409 when a turn has not ended in time; add `409` to the list of status codes a route may return), `backend/chat/README.md` (modify: the stop and delete behaviour)
- **Change:** document the behaviour and the new setting where the task settings are described.
- **Verification:** `venv/bin/python -m pytest backend` (the backend suite, one process, as `scripts/check.sh` runs it), then `venv/bin/python -m pytest tests` (docs guardrails), `ruff check .`, `scripts/check.sh`. Live on the MYAI-52 rig (`~/.claude/tickets/My-AI/MYAI-52-evidence/scripts/`: `up.sh`, `node race2.mjs FS`): after a delete the completion stream ends within the wait instead of running to the end; a Retry sent right after the stop answer is accepted; the `GET` after the stop answer reports `is_running: false` and holds only the user message.

### Tests
- `backend/task_manager/tests/test_manager.py`, `backend/chat/tests/test_router.py`, `backend/tests/test_config.py`; commands as in Step 5.

### Risks and open questions
- **A worker blocked in a synchronous model or tool call** does not see the cancel until its next chunk: the wait runs out, `/stop` answers `stopped: false` and a send can still be refused until the worker exits. This is today's behaviour, now reported instead of hidden.
- **A send that has claimed the turn but not yet started its worker** (`claim_turn` in `chat_completions` and `resume_chat`) has no live worker, so a delete arriving in that moment goes through and the worker then starts for a deleted chat. The window is the few statements between the claim and `start_task`; not closed here (it would need the delete to honour the claim set).
- **Request threads wait up to 5 seconds** on stop, delete and clear-all (one shared deadline). Acceptable for a user action; the setting can be lowered.
- **A dying worker writing after the rollback** was not observed; Step 3's order removes the window when the worker exits in time. On a timeout the window stays, as today.
- **`discard_research_endpoint`** removes state files right after signalling; the same wait would fit there. Not changed here; worth a follow-up ticket if it shows up in practice.
- **Legacy UI and React both read only the status of `/stop`**, so the added field breaks neither. The React sidebar shows a failed delete as a toast with the server's message (`RecentChats.tsx` `run`), so the 409 needs no change there; how the legacy UI shows a failed delete was not checked.

### Success criteria
- [ ] Deleting a chat with a running turn ends the turn first; nothing is left or written for the deleted chat (a turn that has not ended in time refuses the delete with 409)
- [ ] Clear-all stops the caller's running turns first, and only theirs
- [ ] `/stop` answers after the worker has exited (or reports `stopped: false` after the bounded wait); an immediate send or resume is then accepted and `is_running` is false
- [ ] The rollback runs after the stopped worker's last write
- [ ] `docs/standards/api.md` and the READMEs describe the behaviour; tests and `scripts/check.sh` pass
### Reviewer brief
- **Objective:** the server ends a chat's turn before deleting the chat, and `/stop` answers only after the turn's worker has exited (bounded wait).
- **Decisions:** `TaskManager.stop_task_and_wait` (join outside the lock, `TASK_STOP_WAIT_SECONDS`, default 5), `running_chat_ids`, `forget_chat`; `stop_chat` waits before the rollback and answers 200 with `stopped: true|false`; `remove_chat` and `clear_all_chats` stop first and answer 409, deleting nothing, when a worker has not exited in time; clear-all uses one shared deadline and touches only the caller's chats; `stop_task` stays for callers that must not wait.
- **Out of scope:** `discard_research_endpoint`; making a worker blocked in a synchronous call cancellable sooner; frontend changes (MYAI-73).
- **Success criteria:** delete ends the turn first and leaves nothing behind (409 if the turn has not ended in time); clear-all stops only the caller's turns first; after `/stop` answers with `stopped: true` an immediate send or resume is accepted and `is_running` is false; the rollback follows the worker's last write; docs, READMEs, tests and `scripts/check.sh` pass.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- **Round 1 (Haiku): FAIL.** Judged FAIL. Valid BLOCKING: deleting on a timeout let a live worker write for a deleted chat (now a 409, nothing deleted); no step removed the task-state file, including a `needs_resume` file with no worker (now `forget_chat`). Valid MINOR, fixed: placement of the setting, clear-all's timeout answer and shared deadline, the backend suite command, the 404 for another user's chat, the interrupted flag on delete, an event instead of sleeps in the blocking test.
- **Round 2 (Haiku): PASS.** Judged PASS. MINOR, fixed inline: `409` added to the status-code list in `docs/standards/api.md`; clear-all cleans callbacks and the stream cache of the chats it stopped; the id sanitisation for the state file is named. MINOR, logged and not fixed: a delete between a send's turn claim and its `start_task` still goes through (recorded under Risks; closing it needs new design).

## Implementation notes
- [x] Steps 1-5 on branch bugfix/stop-and-delete-end-running-turn: `TASK_STOP_WAIT_SECONDS`, `stop_task_and_wait`/`running_chat_ids`/`forget_chat`, `/stop` waits then rolls back (`stopped` field), delete and clear-all stop first (409 on timeout), docs and READMEs.
- Smoke: scripts/check.sh --python-only passes.
- PR: https://github.com/archit342000/My-AI/pull/120, branch bugfix/stop-and-delete-end-running-turn, base develop

## Verification

### Acceptance review (2026-11-10)
Criteria ticked on the live and e2e results recorded in the PR's Testing section (checks run on throwaway backends during the autopilot run; scripts in `MYAI-74-evidence/`).
All criteria covered.
### Results (2026-11-10)
Live on a throwaway backend with a slow stub (evidence/scripts/v74.py): delete mid-turn 200 at once, stream ended after ~2.5 s, no rows or task files; stop gives stopped:true, is_running false, immediate send 200; clear-all same as delete; no tracebacks. Timeout paths: unit tests only.

## Review history
### Round 1 - 2026-11-10 (Haiku)
Fixed: R1-1 cache entry and WAL survived delete (now `cleanup_chat`); R1-3 clear-all race (re-check loop); R1-4 forget_chat swallowed OSError (now propagates, runs before the DB delete); R1-8/9 test patch target and assertions; R1-10 constant moved. Rejected: R1-2 rollback on timeout (planned decision, documented), R1-6 claim release (verified live: immediate send accepted), R1-7 first stop loop (signals all turns before the sequential waits). Deferred: R1-5 in-flight tool threads (documented limit; follow-up). Fixes not re-reviewed.

## Log
- 2026-11-10: created (server-side gaps from the race pass in MYAI-52)
- 2026-11-10: linked relates_to MYAI-74's client-side counterpart MYAI-73 (same races, handled from the client there)
- 2026-11-10: plan validated, 2 rounds
- 2026-11-10 batch-autopilot: shipped, base develop
- 2026-11-10: acceptance criteria reviewed against the recorded results (5 ticked, 0 left open)
- 2026-11-10: closed by the user after the PR merged into develop
