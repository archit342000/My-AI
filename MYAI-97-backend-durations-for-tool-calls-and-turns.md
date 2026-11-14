---
id: MYAI-97
title: "Backend: durations for tool calls and turns"
status: in-progress
created: 2026-11-11
updated: 2026-11-11
links:
  conflicts_with: [MYAI-100]
  blocks: [MYAI-99]
  split_from: [MYAI-96]
---

## Description
Item 1 of MYAI-96. The design shows how long each tool call took ("0.1 s", "38 s") and how long the whole Thought process took ("46 s"). The stream and stored messages carry no start or end time for a tool call or an assistant turn.

Needed: a start and end time (or a duration) per tool call and per assistant turn, sent in the stream and kept in stored messages, so a reload shows the same numbers.

## Acceptance criteria
- [x] Each tool call carries a duration in the stream and in stored messages
- [x] Each assistant turn carries a duration in the stream and in stored messages
- [x] Older messages without durations still load
- [x] `docs/standards/api.md` and the frontend types in `frontend/src/api/` are updated in the same change
- [x] Frontend follow-up noted: show durations in `features/chat/TimelineEntry.tsx` and `ThoughtBox.tsx`

## Plan
**Date:** 2026-11-11  **Status:** Validated

### Objective
Record how long each tool call and each assistant turn took, send it in the stream and keep it with the stored messages, so the chat can show "0.1 s" on a tool row and "46 s" on the Thought process box, live and after a reload.

### Context
- Requirement: ticket Description and Acceptance criteria. Planned against `develop` at 7dd16d3.
- Rules: `AGENTS.md` (`db` only, no raw SQL outside the wrapper, `log_event`, tests 1:1); `docs/data.md` Migrations (idempotent `init_db()`, add columns with a default, test `init_db()` twice and on an older schema); `docs/standards/api.md` (SSE format, contract changes update `frontend/src/api/` in the same change); `docs/standards/testing.md`.
- Current behaviour:
  - `backend/chat/tool_handler.py` `ToolHandler.handle_tool_calls`: runs each tool (pure via `_execute_pure_tool`, agent via `AgentHandler.execute_agent`), stores the result with `db.add_tool_result(...)` and yields a `tool_result` delta `{name, content, tool_call_id}`. Six branches store a result (unknown tool, admin-only refusal, clipboard refusal, agent, agent not resolved, pure); no timing is taken.
  - `backend/chat/handler.py` `ChatHandler._handle_tool_execution`, `tools_disabled` branch: refuses every call with `db.add_message(role="tool", ...)` and yields a `tool_result` delta without going through `ToolHandler`.
  - Writers in `message_ops.py` invalidate the `messages`, `chats` and `chats_full` cache entries (main) or the anchor's entry (sub-agent); `get_messages` reads through `cache_layer`.
  - `backend/database/wrapper/message_ops.py` `add_message` writes `messages` (main) or `sub_agent_messages` (other `parent_type`) with a `timestamp` of the write time; `add_tool_result` wraps it. Reads use `SELECT *`, so new columns reach `GET /api/chats/<id>` and `sub_agent_history` without serializer changes.
  - `backend/chat/turn_handler.py` `TurnHandler.handle_turn` already measures `time.time() - start_time` but only logs it (`turn_handler_end`); `_persist_final_state` updates the chat timestamp.
  - `backend/database/init_db.py`: `messages` and `sub_agent_messages` get columns through the `message_cols` / `sub_agent_cols` migration lists.
  - Frontend: `frontend/src/api/types.ts` `StoredMessage`, `StoredSubAgentRow`; `frontend/src/features/chat/stream-reducer.ts` `ToolResultDelta`, `StreamChunk` (a chunk without `choices` is ignored).

### Approach
- New nullable column `duration_ms INTEGER` on `messages` and `sub_agent_messages`: on a `tool` row it is that tool call's run time; on an assistant row it is the whole turn's time and is set only on the last assistant row of a turn. Older rows stay `NULL` (no backfill: the start time was never stored).
- Tool timing: `handle_tool_calls` takes `time.monotonic()` when it starts handling a call and passes `duration_ms` to every `add_tool_result` (all six branches) and adds it to the `tool_result` delta. An agent call's time covers the whole sub-agent run. The `tools_disabled` refusals in `handler.py` store and send `duration_ms: 0` (nothing ran). Both handlers use `time.monotonic()` (imported as `time`), and tests patch the module's `time` attribute (`patch("backend.chat.tool_handler.time")`, `patch("backend.chat.turn_handler.time")`), never the global `time.monotonic` the event loop uses.
- Turn timing: `TurnHandler.handle_turn` computes the duration when `run_fn` finishes normally, stores it with a new `db.set_turn_duration(chat_id, after_message_id, duration_ms)` (the latest main assistant row with id greater than the triggering user message), then yields one event `data: {"turn": {"duration_ms": N}}`. A failed or stopped turn sends and stores nothing: the duration is written only after `run_fn` completes, so an exception or a cancellation (`asyncio.CancelledError`, how a stop ends the worker) skips it; a stop rolls the turn back anyway. `TurnHandler` switches its timer to `time.monotonic()`. A turn that ends normally after streaming an error event (for example `handler.py`'s inference error path) still records its time: it ran and ended. A resumed turn records the resumed part only.
- `add_message` / `add_tool_result` take an optional `duration_ms`.
- Frontend contract only: add the fields to `StoredMessage`, `StoredSubAgentRow`, `ToolResultDelta` and `StreamChunk`. Showing them is the noted follow-up.
- Rejected: deriving durations from `timestamp` differences (the call's start is not stored, and rows written in one transaction share times); a separate timings table (more joins for one number per row).

### Out of scope
- Showing durations in `features/chat/TimelineEntry.tsx` and `ThoughtBox.tsx` (frontend follow-up, recorded in Implementation notes).
- Research step and helper timing (MYAI-98, MYAI-99 build on this).

### Steps
#### Step 1: Columns
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/database/init_db.py` (modify): `CREATE TABLE` for `messages` and `sub_agent_messages`, and `message_cols` / `sub_agent_cols`; `backend/database/tests/test_init_db.py` (modify).
- **Change:** add `duration_ms INTEGER DEFAULT NULL` to both tables for new databases and to both migration lists (`message_cols`, `sub_agent_cols`, which follow the file's existing try/except `OperationalError` pattern) for existing ones.
- **Verification:** new tests: `init_db()` twice is fine; a database made with the old `messages`/`sub_agent_messages` columns gains `duration_ms` with rows kept and `NULL`.

#### Step 2: Write helpers
- **Status:** todo
- **Depends on:** 1
- **Files:** `backend/database/wrapper/message_ops.py` (modify): `add_message`, `add_tool_result`, new `set_turn_duration`; `backend/database/wrapper/tests/test_message_ops.py` (modify).
- **Change:** optional `duration_ms` written to either table; `set_turn_duration` updates the latest main assistant row after a given message id, invalidates `messages` (`chat:{chat_id}`), `chats` and `chats_full` for the chat, as `add_message` does for a main row, and returns whether a row was updated.
- **Verification:** new tests: duration stored on a main and a sub-agent tool row and read back by `get_messages`; omitted duration stays `NULL`; `set_turn_duration` picks the right row, does nothing when no assistant row follows, and a `get_messages` call made before it returns the new duration after it (cache invalidated).

#### Step 3: Tool call timing
- **Status:** todo
- **Depends on:** 2
- **Files:** `backend/chat/tool_handler.py` (modify): `handle_tool_calls`; `backend/chat/handler.py` (modify): `_handle_tool_execution` `tools_disabled` branch; `backend/chat/tests/test_tool_handler.py`, `backend/chat/tests/test_handler.py` (modify).
- **Change:** start a monotonic timer per call; pass `duration_ms` to every `add_tool_result` and include it in every `tool_result` delta; the `tools_disabled` refusals carry `duration_ms: 0`.
- **Verification:** new tests with `backend.chat.tool_handler.time` patched: a pure tool, an agent tool, the unknown-tool, admin-only and clipboard refusals, and the unresolved-agent branch each store and send an integer `duration_ms` matching the clock; a call skipped by the idempotency guard sends nothing; a `tools_disabled` refusal stores and sends `0`.

#### Step 4: Turn timing
- **Status:** todo
- **Depends on:** 2
- **Files:** `backend/chat/turn_handler.py` (modify): `handle_turn`; `backend/chat/tests/test_turn_handler.py` (modify).
- **Change:** on normal completion compute `duration_ms`, call `db.set_turn_duration`, yield the `turn` event; nothing on an exception.
- **Verification:** new tests with `backend.chat.turn_handler.time` patched: a finished turn yields `{"turn": {"duration_ms": N}}` as its last chunk and stores it; a turn that raises, and one cancelled with `asyncio.CancelledError`, yield no `turn` event and store nothing.

#### Step 5: Frontend types
- **Status:** todo
- **Depends on:** 3, 4
- **Files:** `frontend/src/api/types.ts` (modify): `StoredMessage.duration_ms`, `StoredSubAgentRow.duration_ms`; `frontend/src/features/chat/stream-reducer.ts` (modify): `ToolResultDelta.duration_ms`, `StreamChunk.turn`; `frontend/src/features/chat/stream-reducer.test.ts` (modify).
- **Change:** optional fields only; the reducer keeps ignoring a `turn` chunk.
- **Verification:** `npm run typecheck`, `npm run lint`, `npm run test` pass; a reducer test shows a `turn` chunk leaves the live turn unchanged.

#### Step 6: Docs
- **Status:** todo
- **Depends on:** 5
- **Files:** `docs/standards/api.md` (modify): Streaming; `docs/data.md` (modify): `messages.duration_ms`; `backend/chat/README.md` (modify: `turn_handler.py` and `tool_handler.py` rows), `backend/database/README.md` (modify: one Conventions line on `messages.duration_ms` and `set_turn_duration`).
- **Change:** document the `duration_ms` field on `tool_result` and stored rows, the `turn` event and when it is sent; record the frontend follow-up in Implementation notes. Check that the legacy UI (`static/script.js`, `static/js/`) is unaffected by the added keys (it reads named fields only) and record the check in Implementation notes, as `docs/standards/api.md`'s breaking-change rule requires.
- **Verification:** `EMBEDDING_URL="http://mock" AI_URL="http://mock" AI_API_KEY="dummy" PYTHONPATH=. venv/bin/python -m pytest tests -q -p no:cacheprovider` passes, then the full suites in Tests below.

### Tests
- Backend: `EMBEDDING_URL="http://mock" AI_URL="http://mock" AI_API_KEY="dummy" PYTHONPATH=. venv/bin/python -m pytest backend/database/tests`, `backend/chat/tests`, then `backend` and `tests`; `venv/bin/ruff check .`.
- Frontend: in `frontend/`, `npm run typecheck`, `npm run lint`, `npm run test`.
- Gate: `scripts/check.sh`. Optional: `npm run e2e:stack` to see the `turn` event on a real turn.

### Risks and open questions
- Recorded fixtures in `frontend/src/test/fixtures/api/` lack the new fields; they stay valid because the fields are optional.
- Decision: resumed turns record only the resumed part (assumption; the earlier part's start is not kept).

### Success criteria
- [ ] Every tool result carries `duration_ms` in the stream and in its stored row (main and sub-agent)
- [ ] A finished turn sends a `turn` event with `duration_ms` and stores it on its last assistant row
- [ ] Older messages without durations load unchanged
- [ ] `docs/standards/api.md`, `docs/data.md` and `frontend/src/api/` types updated in the same change
- [ ] Frontend follow-up recorded

### Reviewer brief
- Objective: every tool call and every finished assistant turn carries a duration in the stream and in stored messages.
- Decisions: nullable `duration_ms` on `messages` and `sub_agent_messages` (tool rows: the call; the turn's last assistant row: the whole turn); monotonic timers in `ToolHandler` (all six result branches) and `TurnHandler`; `tools_disabled` refusals carry 0; a new `{"turn": {"duration_ms"}}` SSE event after a normally finished turn, stored with `db.set_turn_duration` (cache invalidated); failed by exception or cancelled turns send and store nothing; resumed turns record the resumed part; no backfill; frontend gets optional types only.
- Out of scope: showing durations in the UI; research and helper timing.
- Success: durations in stream and storage for tools and turns, older rows load, api.md, data.md and frontend types updated.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- Round 1: validator FAIL. Judged FAIL. Valid BLOCKING, fixed: `set_turn_duration` must invalidate the message cache (Step 2); `handler.py` `tools_disabled` refusals were not covered (Context, Approach, Step 3). Valid MINOR, fixed: six result branches, not five; `DEFAULT NULL` and the existing migration pattern; README updates made firm; cancellation (`CancelledError`) path stated and tested; clock and patch target named; Step 6 runs the full suites.
- Round 2 (diff-scoped): validator PASS. Judged PASS. Valid MINOR, fixed inline: patch the module's `time`, not the global; turns ending normally after an error event still record time (stated); cache keys named; admin-only and clipboard branches tested; database README target named; env vars on the docs check. Item 7 (stop wording) needed no change.
- 2026-11-11 correction after validation: database tests moved to the 1:1 files under `backend/database/wrapper/tests/` (found while validating MYAI-101).
- 2026-11-11 correction after validation: last step also checks the legacy UI against the added keys (`docs/standards/api.md`), found while validating MYAI-102.

## Implementation notes
### Autopilot run (2026-11-11)
- Mode: automatic (batch-autopilot, item 3/9)
- Branch: feature/turn-durations  PR base: develop  Starting commit: 32d33f73cd578e1a29080f9a12092caf1c36c073
- Dirty before start: none
- Work files: none yet
- Counters: fix 0/10, review 1/5, re-verify 1
- Last completed stage: 6 ship  Next: none
- Hard blocker: none
- WIP commit: none

### Autopilot decisions (2026-11-11)
- Stage 1: plan already Validated in ticket; reused.
### Baseline (2026-11-11)
- backend/database + backend/chat tests all passed before changes (211 + 303).

### Implementation progress
- [x] Step 1: `duration_ms INTEGER DEFAULT NULL` on messages and sub_agent_messages (CREATE, migration lists and the cascade-rebuild DDLs) - init_db.py
- [x] Step 2: `add_message`/`add_tool_result` take duration_ms; new `set_turn_duration` (cache invalidated) - message_ops.py
- [x] Step 3: tool timing in all six result branches + tools_disabled refusals (0) - tool_handler.py, handler.py (the refusal delta only; the dict sent back to the model is unchanged)
- [x] Step 4: turn timing + `turn` SSE event - turn_handler.py
- [x] Step 5: frontend optional types + reducer test - types.ts, stream-reducer.ts
- [x] Step 6: docs - api.md, data.md, chat README, database README. Legacy UI check: `static/script.js` and `static/js/telemetry-chart.js` read `choices` with guards, so the `turn` chunk and the added key are ignored.
- Deviation: the cascade-rebuild DDLs in migration 11 also got the column (without it the rebuild dropped it and 6 init_db tests failed).
- Frontend follow-up (not done, out of scope): show durations in features/chat/TimelineEntry.tsx and ThoughtBox.tsx.

### Smoke test (2026-11-11)
- backend + tests 1677 pass; frontend typecheck, lint, 1106 unit tests; ruff clean.
- Stage 5: resolve-review done inline by the author (not via the skill).
PR: https://github.com/archit342000/My-AI/pull/126, branch feature/turn-durations, base develop

## Verification
### Verification plan (2026-11-11)
**Diff base:** develop tip. Full form (schema change + stream contract).

**Environment:** the repo's own stack launcher (`frontend/e2e/stack/start-stack.mjs`: real Flask backend on a temp data dir with a scripted model stub, ports 5195/5196, static auth). The driver `scripts/verify97.py` talks HTTP only. L1 uses a separate throwaway data dir holding an old-schema DB, started with `scripts/start_backend.sh` on port 5314. Never touches backend/data. Teardown: SIGTERM the launcher (it removes its temp dir), kill the L1 backend, rm its dir; check ports and processes.

| ID | Criterion | Scenario | Type | Files | Expected |
|----|-----------|----------|------|-------|----------|
| D1 | tool duration in stream and store | send a turn that calls one tool (stub TOOL) | happy | tool_handler.py, message_ops.py | `tool_result` delta has integer duration_ms; the stored tool row (GET chat) has the same value |
| D2 | turn duration in stream and store | same turn | happy | turn_handler.py | last stream event is `{"turn":{"duration_ms":N}}`, N >= the tool's; last assistant row has N; the earlier assistant row (with the tool call) has null |
| D3 | several tools | stub MULTI (3 rounds) | happy | | 3 tool rows with durations; only the final assistant row has the turn duration |
| D4 | plain turn | stub NOTHINK | happy | | turn event sent; last assistant row has it; no tool rows |
| D5 | reload shows the same numbers | GET the chat again and via a second request | edge | | identical values |
| D6 | stopped turn | stub SLOW, read some chunks, POST /stop | failure | turn_handler.py | no turn event; no duration on the partial assistant row |
| D7 | failed model call | stub ERR | failure | | no turn duration stored for a turn that ended in an error event is NOT required (ended normally); record what happens: stream ends cleanly, no traceback |
| L1 | older messages still load | old-schema DB with chat + rows, start the new backend on it, GET the chat | regression | init_db.py | 200, rows present, duration_ms null; second start fine |
| R1 | no server errors | logs of the runs | non-functional | | no traceback |

Scripts: `scripts/verify97.py`, `scripts/start_backend.sh`, `scripts/run_all.sh`.
### Results (2026-11-11)
Verified at HEAD 32d33f7 plus uncommitted:
- backend/chat/README.md 423b7c05bde43742ea38a006ae5058167f65ba7f
- backend/chat/handler.py 2ddb99fac52f910dcdfc83ef98a60d7fc10dabc8
- backend/chat/tests/test_handler.py 97ffa364801d94f97c0c642bee9c77732bb33a3a
- backend/chat/tests/test_tool_handler.py 904f935ea4b9d5672da41613fa2892b2b32c4dd1
- backend/chat/tests/test_turn_handler.py bda9369705a5194ddca6359fd8154bb5c9baaee7
- backend/chat/tool_handler.py afcbc8aa047b0b0be9113d906bee8506251a0c24
- backend/chat/turn_handler.py 84115de39f10d39954c57b042edaf56900168cd4
- backend/database/README.md 58cd00e32f9a95d6a5c4fee038afab43df84d3e3
- backend/database/init_db.py 0725d69a2680f445fb2bde539b1b26a65842e15c
- backend/database/tests/test_init_db.py d87cc9da445a5ef704a60ba9b8058500b7471d3c
- backend/database/wrapper/message_ops.py 27e42fd9115726c9a078a8c2ed6cda4e54d594f0
- backend/database/wrapper/tests/test_message_ops.py 7c6bde6178ddfc376cfffb07c2d16a7f43a5d6f1
- docs/data.md 68eb15e8d5251eb241a9c5e47f74196bd2d616fa
- docs/standards/api.md c01456d593fda798af244f61c5b923f1fa8cd472
- frontend/src/api/types.ts 84112961bcb072c8dcbc83bfd5979579f920dba1
- frontend/src/features/chat/stream-reducer.test.ts 547549d22c82ee54756b0a59c463788a3cc021fd
- frontend/src/features/chat/stream-reducer.ts 97472504f7fc5763a8eb7e426ce17af97e1b1f68

Evidence: `~/.claude/tickets/My-AI/MYAI-97-evidence/` (results.txt, stack.log, old-backend.log, scripts/). Real backend with the scripted model stub on a temp data dir; torn down (no process, port or dir left).

| ID | Status |
|----|--------|
| D1-D5 | PASS (tool and turn durations in the stream and stored, only the last assistant row carries the turn time, reload identical) |
| D6 | PASS (stopped turn: no turn event, nothing stored) |
| D7 | PASS as recorded: a failed model call ends the stream with no turn event and no stored duration (user row only) |
| L1 | PASS (old-schema DB migrates on start; old rows load with null durations) |
| R1 | PASS: the only tracebacks in the logs are the deliberate ERR scenario's model failure, logged by existing code |
Regression: backend+tests 1677, frontend 1106 pass.
Verdict: verified (9 PASS, 0 FAIL, 0 BLOCKED).

## Review history
### Round 1 - 2026-11-11
Verdict: Request changes (3 MAJOR claimed) -> after resolution Approve. One Haiku reviewer, working tree vs develop. 10 findings.
- R1-1 [MAJOR] handler.py:791 - tools_disabled refusal passes `parent_message_id=` which `add_message` does not accept (TypeError on the real db) - Confirmed by reading the signature (kwarg is old; the 0-duration refusal could never be stored) - Fixed (`parent_id=`; the test now binds the call's keywords to the real signature)
- R1-2 [MAJOR] turn_handler.py - a stop ends run_fn normally, so the turn was timed, stored and the event sent before the rollback - Static - Fixed (skipped when `task_manager.is_interrupted`; test)
- R1-3 [MAJOR] router.py - the `turn` chunk has no `choices` and reaches the OpenAI-compatible stream - Static - Rejected: api.md already lists project extensions in that stream (`error`, `__redact__`, `event` labels); the React client and legacy UI read `choices` with guards (checked)
- R1-4 [MINOR] api.md - '0' for refusals: only tool-round-limit refusals are 0 - Fixed
- R1-5 [MINOR] event sent though nothing stored - Fixed (event only when `set_turn_duration` stored a row; no-row case logged)
- R1-6 [MINOR] message_ops.py:291 - timing local shadows the new parameter - Fixed (renamed)
- R1-7 [NIT] test name - Fixed. R1-8 [NIT] blank lines - Rejected (cosmetic). R1-9 [NIT] set_turn_duration without BEGIN IMMEDIATE - Rejected (single UPDATE, busy timeout). R1-10 [NIT] ticket checkbox - already ticked.
Resolved inline by the author. Re-verified: harness re-run 8/8, backend+tests 1679 pass, ruff clean.

## Log
- 2026-11-11: created (split from MYAI-96 at the user's request)
- 2026-11-11: linked blocks MYAI-98
- 2026-11-11: linked blocks MYAI-99
- 2026-11-11: linked split_from MYAI-96
- 2026-11-11: plan validated, 2 rounds
- 2026-11-11: linked conflicts_with MYAI-100 (both change turn_handler.py and tool_handler.py)
- 2026-11-11: unlinked blocks MYAI-98 (user decision: research step times come from stored event timestamps)
- 2026-11-11: autopilot started (batch-autopilot)
- 2026-11-11: implemented, smoke tests pass
- 2026-11-11: verify: 9 PASS, 0 FAIL, fix 0/10
- 2026-11-11: review round 1 resolved (7 fixed, 3 rejected); re-verified
- 2026-11-11: batch-autopilot: shipped, base develop (https://github.com/archit342000/My-AI/pull/126)
