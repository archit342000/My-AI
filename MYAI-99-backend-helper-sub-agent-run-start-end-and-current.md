---
id: MYAI-99
title: "Backend: helper (sub-agent) run start, end and current activity"
status: in-progress
created: 2026-11-11
updated: 2026-11-11
links:
  conflicts_with: [MYAI-100]
  blocked_by: [MYAI-97]
  split_from: [MYAI-96]
---

## Description
Item 3 of MYAI-96. The design shows helpers at work as a card: each helper's name, what it is doing now, whether it is working or done, and for how long. Today a sub-agent's steps arrive tagged with its name and are grouped inside the Thought process box.

Needed: an explicit start and end per sub-agent run, its current activity, and whether helpers can run at the same time, live and after a reload.

## Acceptance criteria
- [x] Each sub-agent run has an explicit start and end event with its name
- [ ] The current activity of a running helper is sent (unit-tested; not shown live: no helper available here streams status events)
- [x] Durations come from the timing in MYAI-97
- [x] Whether helpers can run in parallel is documented
- [x] `docs/standards/api.md` and `frontend/src/api/` types are updated in the same change
- [x] Frontend follow-up noted: helpers card in `features/chat/MessageList.tsx`

## Plan
**Date:** 2026-11-11  **Status:** Validated

### Objective
Send an explicit start, end and current activity for every helper (sub-agent) run, live and after a reload, so the chat can draw the helpers card (name, what it is doing now, working or done, for how long).

### Context
- Requirement: ticket Description and Acceptance criteria. Planned against `develop` at 7dd16d3, after MYAI-97 (blocked_by): MYAI-97 adds a per-call timer and `duration_ms` in the same `ToolHandler` branch this plan extends.
- Rules: `AGENTS.md`; `docs/standards/api.md` (SSE extensions; contract changes update `frontend/src/api/`); `docs/standards/testing.md`.
- Current behaviour:
  - `backend/chat/tool_handler.py` `ToolHandler.handle_tool_calls` handles tool calls one after another. For an agent tool (`tool_meta["type"] == "agent"`) it sets `agent_handler.parent_message_id = tc_id`, iterates `AgentHandler.execute_agent(name, flow_fn, **args)` and re-yields every chunk, then stores and yields the `tool_result`. Sub-agent chunks carry `parent_type` = the agent's name. There is no start or end signal besides the tool call and its result.
  - Helpers never run at the same time: calls are handled sequentially and no agent code uses `asyncio.gather` or `create_task` (`backend/tools/agents`, `backend/chat`). An agent may call another (research calls `search_web`), so runs nest. A nested call goes through `ChatHandler._handle_tool_execution`, which sets that `ToolHandler.parent_type` to the calling agent's name and anchors it on the outer tool call id (`agent_handler.py`), so a nested run's own `tool_result` and `agent_run` chunks carry the outer agent's `parent_type`, while the nested agent's own output carries its own name.
  - Sub-agent tool calls reach the stream only as the merged synthetic tool-call chunk `_handle_tool_execution` yields, not as fragments.
  - Failure texts agents return: `"<display name> failed: ..."` (`backend/tools/agents/base.py`), `"Document agent failed: ..."`, `"Visit page agent failed to return a response."`, `"Browsing agent failed during execution: ..."`, and `ToolHandler`'s own `"Error: ..."` refusals.
  - While a turn runs, a reloading client re-attaches with `GET /api/chats/<id>/stream`, which replays every chunk the turn has yielded: `TaskExecutor._process_chunk` (`backend/task_manager/executor.py`) appends each one to `response_cache`, and `response_cache.subscribe` sends them all first (`backend/database/cache_system.py`). Chunks yielded from tool execution, including the new `agent_run` ones, go through the same path.
  - `backend/chat/handler.py` `ChatHandler._parse_sse_delta` reads a `data:` line into an `SSEEvent` (event text, tool call, and so on).
  - `backend/database/wrapper/history_ops.py` attaches collections anchored on an assistant message's parent user message or on its tool call ids to that message as `collections`; `artifact_ops.add_collection(..., overwrite=True)` replaces a collection of the same type under the same anchor.
  - Frontend: `frontend/src/features/chat/stream-reducer.ts` tags steps with the agent from `parent_type` and ignores chunks without `choices`; `frontend/src/api/types.ts`.

### Approach
- New stream chunk `{"parent_type": <caller's parent_type>, "agent_run": {"id": tc_id, "name", "parent_id", "state", "activity", "started_at", "duration_ms"}}`: sent once with `state: "running"` before the agent starts, again whenever its activity changes, and once at the end with `state: "done"` or `"failed"` and `duration_ms` (from MYAI-97's timer). `parent_id` is the enclosing run's id for nested runs, else null. `started_at` is epoch seconds.
- Activity: the latest event text, or tool name from the merged tool-call chunk, in chunks whose `parent_type` equals the running agent's name, skipping chunks that carry `agent_run` or `tool_result` (those come from nested handlers); read with `_activity_from_chunk` in `ToolHandler`, cut to 120 characters; only changes are sent.
- Nesting rule: a run is nested when its `ToolHandler.parent_type` is not `"main"`; its `parent_id` is that handler's `parent_message_id` (the outer tool call id), else null.
- `failed`: the agent raised, its implementation could not be resolved, or `_run_failed(result)` matches the first line of its result against `^(Error:|[\w ]+ failed\b)` (case-insensitive), which covers the failure texts listed in Context; the pattern lives in that one helper.
- Stored: an `agent_runs` collection (a list of finished run records) with `parent_message_id` = the handler's `parent_message_id` and `parent_type` = the handler's `parent_type`; after each run ends the stored list is read, the record merged by `id`, and written back with `overwrite=True` (so a resumed turn keeps earlier runs). `GET /api/chats/<id>` serves it in `collections` with no route change. A reload mid-run sees the running state through the existing re-attach replay (no change needed); a turn stopped mid-run is rolled back as today.
- Parallel helpers: documented as "runs are sequential and may nest"; no concurrency is added.
- Frontend contract: `AgentRun` type and `StreamChunk.agent_run`; drawing the card is the noted follow-up.
- Rejected: wrapping in `AgentHandler.execute_agent` (it has no tool call id or result); a new table (one small list per turn fits collections).

### Out of scope
- The helpers card in `features/chat/MessageList.tsx` (frontend follow-up, recorded in Implementation notes).
- Running helpers in parallel.
- Research step progress (MYAI-98).

### Steps
#### Step 1: Run record helpers
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/chat/tool_handler.py` (modify): new `_activity_from_chunk`, `_run_failed`, `_agent_run_chunk`; `backend/chat/tests/test_tool_handler.py` (modify).
- **Change:** pure helpers: activity from an event delta or a tool-call delta of the agent's `parent_type` (ignore other agents' chunks and main chunks), failure rule, chunk builder.
- **Verification:** unit tests for each helper: activity from an event and from a merged tool-call chunk; chunks of another `parent_type` and chunks with `agent_run` or `tool_result` ignored; long text cut; `_run_failed` true for each failure text in Context and false for a normal result.

#### Step 2: Emit start, activity and end
- **Status:** todo
- **Depends on:** 1
- **Files:** `backend/chat/tool_handler.py` (modify): agent branch of `handle_tool_calls`; `backend/chat/tests/test_tool_handler.py` (modify).
- **Change:** before `execute_agent`, yield the `running` chunk; while re-yielding agent chunks, yield an `agent_run` update when activity changes; after the loop (and in an exception path that re-raises after yielding `failed`), yield the final chunk with `duration_ms`. The unresolved-implementation branch yields a single `failed` record.
- **Verification:** tests with a fake `flow_fn`: start, two activity updates (event then tool call), done with duration; an agent that raises yields `failed` and the exception still propagates as today; unresolved implementation yields `failed`; pure tools yield no `agent_run`.

#### Step 3: Store the runs
- **Status:** todo
- **Depends on:** 2
- **Files:** `backend/chat/tool_handler.py` (modify); `backend/chat/tests/test_tool_handler.py`, `backend/database/wrapper/tests/test_history_ops.py` (modify).
- **Change:** keep the turn's finished run records on the handler and write them as the `agent_runs` collection (`overwrite=True`) under `parent_message_id` after each run ends.
- **Verification:** tests: two runs in one turn store a two-item list; a second handler for the same anchor (resumed turn) adds to the stored list instead of replacing it; a nested run stores `parent_id` = the outer tool call id; the served history attaches `agent_runs` to the assistant message for a top-level run (anchored on that assistant message's own id, the handler's `parent_message_id`) and for a nested run (anchored on the outer tool call id).

#### Step 4: Frontend types
- **Status:** todo
- **Depends on:** 2
- **Files:** `frontend/src/api/types.ts` (modify): `AgentRun`; `frontend/src/features/chat/stream-reducer.ts` (modify): `StreamChunk.agent_run`; `frontend/src/features/chat/stream-reducer.test.ts` (modify).
- **Change:** optional fields only; the reducer keeps ignoring the chunk.
- **Verification:** `npm run typecheck`, `npm run lint`, `npm run test` pass; a reducer test shows an `agent_run` chunk leaves the live turn unchanged.

#### Step 5: Docs
- **Status:** todo
- **Depends on:** 3, 4
- **Files:** `docs/standards/api.md` (modify): Streaming; `backend/chat/README.md` (modify); `backend/tools/agents/README.md` (modify).
- **Change:** document the `agent_run` chunk, the `agent_runs` collection, the failure rule, and that helper runs are sequential and may nest; record the frontend follow-up in Implementation notes. Check that the legacy UI (`static/script.js`, `static/js/`) is unaffected by the added keys (it reads named fields only) and record the check in Implementation notes, as `docs/standards/api.md`'s breaking-change rule requires.
- **Verification:** `venv/bin/python -m pytest tests -q -p no:cacheprovider` passes.

### Tests
- Backend: `EMBEDDING_URL="http://mock" AI_URL="http://mock" AI_API_KEY="dummy" PYTHONPATH=. venv/bin/python -m pytest backend/chat/tests`, `backend/database/tests`, then `backend` and `tests`; `venv/bin/ruff check .`.
- Frontend: in `frontend/`, `npm run typecheck`, `npm run lint`, `npm run test`.
- Gate: `scripts/check.sh`.

### Risks and open questions
- Failure detection from result text is heuristic; the prefixes live in one helper with tests, and agents that need a precise signal can return a structured result later.
- Activity updates add chunks to the stream; only changes are sent, so the count stays small.

### Success criteria
- [ ] Each helper run sends an `agent_run` start and end with its name, state and duration
- [ ] A running helper's current activity is sent when it changes
- [ ] The turn's runs are stored and served with the chat after a reload
- [ ] Sequential and nested runs are documented
- [ ] `docs/standards/api.md` and `frontend/src/api/` types are updated in the same change; frontend follow-up recorded

### Reviewer brief
- Objective: every helper (sub-agent) run sends a start, activity updates and an end (`agent_run` SSE chunk with id, name, parent_id, state, activity, started_at, duration_ms) and the turn's finished runs are stored for reloads.
- Decisions: emitted from `ToolHandler`'s agent branch (after MYAI-97's timer); activity from the agent's own event text or merged tool-call chunk, skipping nested handlers' `agent_run`/`tool_result` chunks; nested when the handler's `parent_type` is not `main`; failure from an exception, an unresolved implementation or `_run_failed`'s single pattern; `agent_runs` collection merged by id under the handler's anchor and `parent_type`; mid-run reload relies on the existing re-attach replay; runs stay sequential and may nest; frontend gets optional types only.
- Out of scope: the helpers card, parallel helpers, research step progress.
- Success: start/end/activity streamed, runs stored and served, sequential/nested documented, api.md and frontend types updated.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- Round 1: validator FAIL. Judged FAIL. Valid BLOCKING, fixed: nested handlers tag their `tool_result`/`agent_run` chunks with the outer agent's `parent_type`, so activity now skips those chunk kinds (Context, Approach, Step 1 tests). Valid MINOR, fixed: nesting rule; collection `parent_type` and anchor; real failure texts and one pattern; merged tool-call chunk as the activity source; resumed turns merge instead of replace; Step 5 depends on 3. Accepted: the worktree has no `venv` (implement runs where the repo's `venv` exists, as the docs say).
- Round 2 (diff-scoped): validator FAIL. Judged PASS. BLOCKING disproved: the claim that `agent_run` chunks are not replayed on reload; `TaskExecutor._process_chunk` appends every yielded chunk to `response_cache` and `GET /api/chats/<id>/stream` replays them (`backend/task_manager/executor.py`, `backend/database/cache_system.py` `subscribe`); Context corrected to name that path. Valid MINOR, fixed inline: top-level anchor named in Step 3's test.
- 2026-11-11 correction after validation: database tests moved to the 1:1 files under `backend/database/wrapper/tests/` (found while validating MYAI-101).
- 2026-11-11 correction after validation: last step also checks the legacy UI against the added keys (`docs/standards/api.md`), found while validating MYAI-102.

## Implementation notes
### Autopilot run (2026-11-11)
- Mode: automatic (batch-autopilot, item 9/9)
- Branch: feature/helper-run-events  PR base: feature/turn-durations  Starting commit: 3744c80be4f9841ef4f6f2671c6fb1306cfaf74c
- Dirty before start: none
- Work files: none yet
- Counters: fix 0/10, review 1/5, re-verify 1
- Last completed stage: 6 ship  Next: none
- Hard blocker: none
- WIP commit: none

### Autopilot decisions (2026-11-11)
- Stage 1: plan already Validated in ticket; reused.
### Baseline (2026-11-11)
- backend/chat tests: 317 passed before changes (branch based on the MYAI-97 branch).

### Implementation progress
- [x] Step 1: pure helpers `_activity_from_chunk`, `_run_failed`, `_agent_run_chunk` in `backend/chat/tool_handler.py` + tests
- [x] Step 2: the agent branch of `handle_tool_calls` sends `agent_run` running at the start, on each change of activity, and done/failed at the end (duration = the tool result's duration, computed once); a raising helper sends failed then re-raises; an unresolved implementation sends one failed run
- [x] Step 3: finished runs stored as the `agent_runs` collection (merged by id, overwrite) under the handler's anchor and `parent_type`; a storage failure is logged, not raised; history weaving test added
- [x] Step 4: frontend `AgentRun` type, `StreamChunk.agent_run`, reducer test
- [x] Step 5: docs (api.md, chat README, agents README). Legacy UI check: `static/script.js` reads `json.choices?.[0]?.delta` with a guard, so the `agent_run` chunk is ignored.
- Frontend follow-up (not done): helpers card in features/chat/MessageList.tsx.
- Deviation: `started_at` uses a bound `time.time` (not the module's `time` object), so tests that patch the module's clock for MYAI-97's monotonic timer keep working; the log payload uses an inline detail string (the shared `error_detail` helper lives in another branch).

### Smoke test (2026-11-11)
- backend + tests 1711 pass; frontend typecheck, lint, 1107 unit tests; ruff clean.
- Stage 5: resolve-review done inline by the author (not via the skill).
PR: https://github.com/archit342000/My-AI/pull/132, branch feature/helper-run-events, base feature/turn-durations

## Verification
### Verification plan (2026-11-11)
**Diff base:** the MYAI-97 branch (this change is stacked on it). Full form (stream contract, stored data).

**Environment:** real Flask backend on a temp data dir (port 5324, static auth) with a scripted model (`scripts/stub.mjs`, port 5325) that calls a named helper when the message says AGENT <name>. Helpers available live: `search_web` (its Tavily service is not running, so the run ends failed after its retries: this exercises running → activity → failed and a mid-run reload) and `file_system_agent` (uses the same stub for its own model steps). `verify99.py` is HTTP only. Never touches backend/data. Teardown: kill backend and stub, rm the temp dir, check ports.

| ID | Criterion | Scenario | Type | Files | Expected |
|----|-----------|----------|------|-------|----------|
| H1 | start and end events with the name | turn that calls search_web | happy | tool_handler.py | agent_run chunks: running first, a final done or failed, all with id, name search_web, parent_id null, started_at |
| H2 | activity sent | same turn | happy | | at least one running chunk carries an activity text (the helper's status event) |
| H3 | duration from MYAI-97's timer | same turn | happy | | the final chunk's duration_ms equals the stored tool row's duration_ms |
| H4 | failure state | search_web with no Tavily | failure | | final state failed; the tool result text starts with the failure text |
| H5 | stored and served | GET /api/chats/<id> | happy | history_ops.py | the assistant message's collections hold agent_runs with the finished run |
| H6 | reload mid-run | start the turn, re-attach to GET /api/chats/<id>/stream after 1 s | edge | | the replay contains the running chunk(s) and later the end chunk |
| H7 | file_system_agent run | turn that calls the helper | happy | | its own agent_run sequence (done or failed, recorded as seen) |
| H8 | pure tool | read_fs_file turn | regression | | no agent_run chunks |
| R1 | no server errors | backend log | non-functional | | no unexpected traceback |

Scripts: `scripts/stub.mjs`, `scripts/start_backend2.sh`, `scripts/verify99.py`, `scripts/run_all.sh`.
### Results (2026-11-11)
Verified at HEAD 3744c80 plus uncommitted (backend/chat/README.md backend/chat/tests/test_tool_handler.py backend/chat/tool_handler.py backend/database/wrapper/tests/test_history_ops.py backend/tools/agents/README.md docs/standards/api.md frontend/src/api/types.ts frontend/src/features/chat/stream-reducer.test.ts frontend/src/features/chat/stream-reducer.ts ).

Evidence: `~/.claude/tickets/My-AI/MYAI-99-evidence/` (results.txt, backend.log, stub.log, scripts/). Real backend with a scripted model; torn down. The first run found a real defect: a helper's plain-text chunk (e.g. 'Search failed after 3 attempts...') carries no line terminator, so it glued onto the next `data:` line and the end-of-run chunk was lost on the wire (stored data was right). Fixed: such a chunk is now ended with a blank line before the next one (unit test added); re-run passed.

| ID | Status |
|----|--------|
| H1 | PASS (running first, failed last, with name, id, parent_id null, started_at) |
| H2 | BLOCKED live: search_web and file_system_agent stream no status events here, so there is no activity text to show (activity is covered by unit tests built from the real emitter's chunk format; the research helper emits events and is not runnable here) |
| H3 | PASS (the end chunk's duration equals the stored tool row's: 9123 ms) |
| H4 | PASS (no Tavily service: the run ends failed and the result text reads as a failure) |
| H5 | PASS (the finished run is stored and served in the assistant message's collections) |
| H6 | PASS (a reload mid-run replays running and later failed) |
| H7 | PASS (file_system_agent: running then done) |
| H8 | PASS (a pure tool sends no agent_run chunks) |
| R1 | PASS (no traceback) |
Regression: backend+tests 1711, frontend 1107 pass.
Verdict: partly verified: 7 PASS, 0 FAIL, 1 BLOCKED (live activity text).

## Review history
### Round 1 - 2026-11-11
Verdict: Request changes (2 MAJOR) -> after resolution Approve. One Haiku reviewer, working tree vs the MYAI-97 branch. 11 findings.
- R1-1 [MAJOR] an unresolved helper sent no start - Fixed (the running chunk is sent before the implementation is resolved; the unresolved run ends failed with the same started_at; test expects running then failed)
- R1-2 [MAJOR] the failure rule matched any 'X failed' first line (a page saying 'Checkout failed for order 42') - Fixed (pattern limited to Error: and the agents' own failure texts: failed. / failed: / failed during execution / failed to return a response / failed after N attempts; api.md aligned; false-positive tests)
- R1-3 [MINOR] a helper that sets no result inherited the previous helper's - Fixed in AgentHandler.execute_agent (result reset per run; test). The research flow's phase failures still set no result, so such a run is recorded done: recorded as a known limit of the heuristic (a follow-up can have the research agent set an explicit failed result)
- R1-4 [MINOR] a stopped run sends no end chunk - Documented in api.md (the turn is rolled back)
- R1-5 [MINOR] a malformed chunk could fail a working helper - Fixed (the activity reader never raises; tests incl. a run with a malformed chunk)
- R1-6 [MINOR] storage catch too narrow - Fixed (any failure is logged, never aborts the turn; tests for RuntimeError, OSError, ValueError)
- R1-7 [MINOR] activity never cleared - Documented (it is the last status text or tool)
- R1-8 [MINOR] test gaps - Fixed (nested storage anchor, false positives, malformed chunk, storage failures, stale result); 
- R1-9 [MINOR] docs on the exception path - Fixed. R1-10 [NIT] duplicated run building - Fixed with R1-1. R1-11 [NIT] mid-file import in tests - Fixed (moved to the top).
Resolved inline by the author. Re-verified: live harness re-run, backend+tests 1729, frontend 1107, ruff clean.

## Log
- 2026-11-11: created (split from MYAI-96 at the user's request)
- 2026-11-11: linked blocked_by MYAI-97
- 2026-11-11: linked split_from MYAI-96
- 2026-11-11: linked conflicts_with MYAI-100 (both change turn_handler.py and tool_handler.py)
- 2026-11-11: plan validated, 2 rounds
- 2026-11-11: autopilot started (batch-autopilot)
- 2026-11-11: implemented, smoke tests pass
- 2026-11-11: verify: 7 PASS, 0 FAIL, 1 BLOCKED (activity text live), fix 0/10 (one defect found by verify and fixed in the same pass)
- 2026-11-11: review round 1 resolved; re-verified
- 2026-11-11: batch-autopilot: shipped, base feature/turn-durations (https://github.com/archit342000/My-AI/pull/132)
