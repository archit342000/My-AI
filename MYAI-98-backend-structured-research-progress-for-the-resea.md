---
id: MYAI-98
title: "Backend: structured research progress for the research plan card"
status: in-progress
created: 2026-11-11
updated: 2026-11-11
links:
  split_from: [MYAI-96]
---

## Description
Item 2 of MYAI-96. The design shows research as a card in the chat: the plan's steps, which are done, which one is running, counts such as "3 of 6 steps · 12 pages read", a duration per finished step, and Stop research. Today research progress arrives only as loose activity labels and a `research_plan` file.

Needed: structured progress events (the list of steps, each step's state and duration, counts) that the chat can draw live and after a reload.

## Acceptance criteria
- [x] Research sends structured progress events: steps, each step's state, counts
- [x] Each finished step has a duration (from the stored section event timestamps)
- [x] The same progress is available after a reload
- [x] `docs/standards/api.md` and `frontend/src/api/` types are updated in the same change
- [x] Frontend follow-up noted: research plan card in `features/chat/MessageList.tsx`

## Plan
**Date:** 2026-11-11  **Status:** Validated

### Objective
Give the chat a structured view of a research run (its plan's steps, each step's state and time, steps done of total, pages read, and the run's phase) as a stream event while it runs and as stored data after a reload, so the frontend can draw the research plan card.

### Context
- Requirement: ticket Description and Acceptance criteria. Planned against `develop` at 7dd16d3.
- Rules: `AGENTS.md` (`db` only, `log_event`, tests 1:1, README kept accurate); `docs/standards/api.md` (SSE format with project extensions; contract changes update `frontend/src/api/` in the same change); `docs/standards/testing.md`; `backend/tools/agents/research_agent/README.md` (state is rebuilt from `role='event'` markers).
- Current behaviour:
  - `backend/tools/agents/research_agent/agent.py` `ResearchAgent` (`AGENT_NAME = "research"`, anchored on the calling tool call's id as `parent_message_id`): `run` goes scout, planner (plan stored as a `research_plan` collection, user approval), executor (`_run_executor` loops sections from `plan["sections"]`, each `{heading, description, queries}`), synthesis. Progress is only free-text events through `_emit_event` (stored as `role="event"` rows in `sub_agent_messages` with a `timestamp`, and streamed as `event` deltas). Section start is `"[Section N] Starting Execution: Section N"`; section end is `"Section N complete."`; failures are `"❌ ..."` events; `flow_fn` records a final failure event.
  - Pages read: the `visited_urls` collection (list of URLs) maintained by `_execute_internal_searches`.
  - `backend/database/wrapper/history_ops.py`: when serving a chat, collections anchored on an assistant message's tool call id are attached to that message as `collections` (so a collection stored under the research tool call reaches `GET /api/chats/<id>` with no route change).
  - `backend/database/wrapper/artifact_ops.py` `add_collection(..., overwrite=True)` replaces a collection of the same type.
  - Frontend: `frontend/src/api/types.ts` `StoredMessage` has no `collections`; `frontend/src/features/chat/stream-reducer.ts` `StreamChunk` ignores chunks without `choices`.

### Approach
- New pure module `backend/tools/agents/research_agent/progress.py` with `build_progress(plan, history, visited_urls, phase)` returning a JSON-ready snapshot: `{"title", "phase", "steps": [{"index", "heading", "state", "duration_ms"}], "steps_done", "steps_total", "pages_read"}`. `phase` is one of `scouting`, `planning`, `awaiting_approval`, `executing`, `synthesizing`, `done`, `failed`. A step's `state` (`pending`, `running`, `done`, `failed`) and `duration_ms` come from the stored section start and complete events and their timestamps, using the same marker constants as `_run_executor`.
- `ResearchAgent._publish_progress(phase)` builds the snapshot, stores it as a `research_progress` collection (overwrite, anchored like the agent's other collections), and yields one SSE line `f"data: {json.dumps({'parent_type': 'research', 'research_progress': snapshot})}\n\n"`, the wire form every agent chunk already uses (`ManualChunkEmitter`, `docs/standards/api.md` Streaming), so it passes through `ToolHandler` and the router unchanged. It is called when the plan awaits approval, when it is approved, at each section start and completion, at synthesis start, on completion, and on each halting failure (including `flow_fn`'s).
- Deviation from the acceptance criterion's "uses the timing from MYAI-97": step duration comes from the section start and complete event timestamps, which are separate writes minutes apart (unlike the same-transaction rows MYAI-97 rejects for tool timing), so MYAI-97's columns are not needed. Decision: the `blocked_by MYAI-97` link can be removed (suggested to the user; not done by the plan).
- Frontend contract: `ResearchProgress` type, `StoredMessage.collections` (typed loosely, with the `research_progress` item shape) and `StreamChunk.research_progress`. Drawing the card is the noted follow-up. "Stop research" uses the existing chat Stop.
- Rejected: parsing the free-text events in the frontend (fragile, wording would become contract); new `role` rows in `sub_agent_messages` (the agent's history is replayed to the model and scanned for events).

### Out of scope
- The research plan card in `features/chat/MessageList.tsx` (frontend follow-up, recorded in Implementation notes).
- Changing the research pipeline, its prompts or its event texts.
- A separate stop route for research.

### Steps
#### Step 1: Progress builder
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/tools/agents/research_agent/progress.py` (create): `build_progress`; `backend/tools/agents/research_agent/constants.py` (modify): new `SECTION_TAG_FORMAT = "[Section {}] "` and `EVENT_FAILURE_MARKER = "❌"`, used by `agent.py` in place of the literals; `backend/tools/agents/research_agent/tests/test_progress.py` (create), `tests/test_constants.py` (modify).
- **Change:** derive step states, durations, counts and pages from the plan, the agent's event history and `visited_urls`; tolerate a missing plan (no steps) and events for indices outside the plan (ignored).
- **Verification:** tests: no plan; plan awaiting approval; first step running; two done with durations from timestamps; a failed step after a `❌` section event; all done; pages counted from `visited_urls`.

#### Step 2: Publish from the agent
- **Status:** todo
- **Depends on:** 1
- **Files:** `backend/tools/agents/research_agent/agent.py` (modify): new `ResearchAgent._publish_progress`, calls in `run`, `_run_planner`, `_run_executor`, `_run_single_section`, `_run_synthesis`, and `flow_fn`'s failure path (only when the `ResearchAgent` instance exists; if construction itself failed nothing is published and the existing failure event stands); `backend/tools/agents/research_agent/tests/test_agent.py` (modify).
- **Change:** store the snapshot as the `research_progress` collection with `overwrite=True` and yield the `research_progress` chunk at each point listed in Approach; a failure while publishing is logged with `log_event` (add `from backend.logging import log_event` to `agent.py`) and does not stop the research run (progress is display data). Replace the `[Section N] ` prefix literal and the `❌` failure literals with the new constants. In `flow_fn`, set `research_agent = None` before the `try` so the failure path can check it.
- **Verification:** tests with the DB and inference mocked as the existing agent tests do: a run through plan approval and two sections yields `research_progress` chunks in order with the expected phases and states, and the stored collection matches the last chunk; each published chunk is a `data: <json>\n\n` string; a halting failure publishes `phase: "failed"`.

#### Step 3: Available after a reload
- **Status:** todo
- **Depends on:** 2
- **Files:** `backend/database/wrapper/tests/test_history_ops.py` (modify).
- **Change:** no code change expected (tested in `history_ops.py`'s own test file); pin that a `research_progress` collection anchored on a tool call id is attached to that assistant message's `collections` in the served history. If it is not, attach it in `backend/database/wrapper/history_ops.py` and record the deviation.
- **Verification:** the new test passes.

#### Step 4: Frontend types
- **Status:** todo
- **Depends on:** 2
- **Files:** `frontend/src/api/types.ts` (modify): `ResearchProgress`, `StoredMessage.collections`; `frontend/src/features/chat/stream-reducer.ts` (modify): `StreamChunk.research_progress`; `frontend/src/features/chat/stream-reducer.test.ts` (modify).
- **Change:** optional fields only; the reducer keeps ignoring the chunk. The served shape only gains an item type inside the existing `collections` field and a new stream chunk, both additive, so the legacy UI needs no change.
- **Verification:** `npm run typecheck`, `npm run lint`, `npm run test` pass; a reducer test shows a `research_progress` chunk leaves the live turn unchanged.

#### Step 5: Docs
- **Status:** todo
- **Depends on:** 4
- **Files:** `docs/standards/api.md` (modify): Streaming; `backend/tools/agents/research_agent/README.md` (modify).
- **Change:** document the `research_progress` chunk and collection (fields, phases, states, when it is sent); add `progress.py` to the README's files table; record the frontend follow-up in Implementation notes. Check that the legacy UI (`static/script.js`, `static/js/`) is unaffected by the added keys (it reads named fields only) and record the check in Implementation notes, as `docs/standards/api.md`'s breaking-change rule requires.
- **Verification:** `venv/bin/python -m pytest tests -q -p no:cacheprovider` passes.

### Tests
- Backend: `EMBEDDING_URL="http://mock" AI_URL="http://mock" AI_API_KEY="dummy" PYTHONPATH=. venv/bin/python -m pytest backend/tools/agents/research_agent/tests`, `backend/database/tests`, then `backend/tools`, `backend` and `tests`; `venv/bin/ruff check .`.
- Frontend: in `frontend/`, `npm run typecheck`, `npm run lint`, `npm run test`.
- Gate: `scripts/check.sh`.

### Risks and open questions
- Event texts become an internal contract between the agent and `progress.py`; both use the same constants from `constants.py`, and `test_progress.py` pins them.
- Steps are the plan's sections; scouting, planning and synthesis show as `phase`, not as steps (assumption, matches "3 of 6 steps").

### Success criteria
- [ ] Research sends `research_progress` chunks with steps, each step's state, counts and pages read
- [ ] Each finished step has a duration
- [ ] The latest progress is stored and served with the chat after a reload
- [ ] `docs/standards/api.md` and `frontend/src/api/` types are updated in the same change
- [ ] Frontend follow-up recorded

### Reviewer brief
- Objective: research sends a structured `research_progress` snapshot (title, phase, steps with state and duration, steps done of total, pages read) while it runs and stores the latest one for reloads.
- Decisions: pure `progress.py` builds the snapshot from the plan, the agent's stored events and `visited_urls`; `ResearchAgent._publish_progress` stores it as an overwritten `research_progress` collection under the research tool call and yields it as an SSE `data:` line; served through the existing `collections` on the assistant message; step durations from stored event timestamps (deviation from "uses MYAI-97 timing", needs the user's sign-off); publishing failures are logged and never stop research; frontend gets optional types only.
- Out of scope: drawing the card, changing the research pipeline or its texts, a research-only stop route.
- Success: chunks and stored snapshot carry steps, states, counts, pages and durations; api.md and frontend types updated.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- Round 1: validator FAIL. Judged FAIL. Valid BLOCKING, fixed: the chunk must be an SSE `data:` string like every agent chunk (Approach, Step 2 test). Valid MINOR, fixed: section prefix and failure marker moved to `constants.py`; deviation from MYAI-97 timing recorded with reason; `flow_fn` construction failure handled; additive shape needs no legacy-UI change; `history_ops.py` tested in its own test file. Accepted: Step 5's docs check plus the Tests section suites.
- Round 2 (diff-scoped): validator PASS. Judged PASS. Valid MINOR, fixed inline: literal replacement assigned to Step 2; `log_event` import; `research_agent = None` before the `try`. The user approved the event-timestamp approach on 2026-11-11: the `blocked_by MYAI-97` link was removed and the acceptance criterion reworded; status set to "Validated".
- 2026-11-11 correction after validation: database tests moved to the 1:1 files under `backend/database/wrapper/tests/` (found while validating MYAI-101).
- 2026-11-11 correction after validation: last step also checks the legacy UI against the added keys (`docs/standards/api.md`), found while validating MYAI-102.

## Implementation notes
### Autopilot run (2026-11-11)
- Mode: automatic (batch-autopilot, item 4/9)
- Branch: feature/research-progress-events  PR base: develop  Starting commit: 32d33f73cd578e1a29080f9a12092caf1c36c073
- Dirty before start: none
- Work files: none yet
- Counters: fix 0/10, review 1/5, re-verify 1
- Last completed stage: 6 ship  Next: none
- Hard blocker: none
- WIP commit: none

### Autopilot decisions (2026-11-11)
- Stage 1: plan already Validated in ticket; reused.
### Baseline (2026-11-11)
- backend/tools/agents/research_agent tests: 33 passed before changes.

### Implementation progress
- [x] Step 1: pure `progress.py` (`build_progress`) + constants (`SECTION_TAG_FORMAT`, `EVENT_FAILURE_MARKER`, `PROGRESS_PHASES`) + tests
- [x] Step 2: `ResearchAgent._publish_progress` (stores the `research_progress` collection, overwrite, and yields a `data:` chunk) called at scouting, awaiting approval, every executor loop top and section start, synthesizing, done and each halting failure, plus `flow_fn`'s failure path (`research_agent = None` before the try) - agent.py
- [x] Step 3: reload path pinned by a test in `backend/database/wrapper/tests/test_history_ops.py` (no code change needed: the collection anchored on the tool call id reaches the assistant message's `collections`)
- [x] Step 4: frontend `ResearchProgress`, `StoredCollection`, `StoredMessage.collections`, `StreamChunk.research_progress` + reducer test
- [x] Step 5: docs (api.md, research_agent README). Legacy UI check: `static/script.js` reads `json.choices?.[0]?.delta` before using a chunk, so the new chunk is ignored.
- Deviation: only the `[Section N] ` prefix literals were moved to the constants; the many `❌` literals in agent.py were left (a test pins the marker's value, and `progress.py` uses the constant) to keep the diff small.
- Frontend follow-up (not done, out of scope): research plan card in features/chat/MessageList.tsx. The plan's note that `blocked_by MYAI-97` can be removed was already applied by the user.

### Smoke test (2026-11-11)
- backend + tests 1682 pass; frontend typecheck, lint, 1106 unit tests; ruff clean.
- Stage 5: resolve-review done inline by the author (not via the skill).
PR: https://github.com/archit342000/My-AI/pull/127, branch feature/research-progress-events, base develop

## Verification
### Verification plan (2026-11-11)
**Diff base:** develop tip. Full form.

**Environment:** the real research pipeline needs a model, web search and a user approving a plan, so the scenarios drive the real `ResearchAgent` code (`run`, `_run_executor`, `_emit_event`, `_publish_progress`, real DB writes, real timestamps) in-process against a throwaway `DATA_DIR`, with only the inference-heavy parts replaced: `_run_single_section` is a small stand-in that emits the agent's own start and complete events (via `_emit_event`) with short sleeps, and `_run_synthesis` is a no-op. The real Flask backend is then started on the same data dir (`scripts/start_backend.sh`, port 5315, static auth) and the chat is read over HTTP. Never touches backend/data. Teardown: kill the backend, rm the temp dir, check port and processes.

| ID | Criterion | Scenario | Type | Files | Expected |
|----|-----------|----------|------|-------|----------|
| P1 | structured events | full run: scouting, plan approved, 3 sections, synthesizing, done | happy | agent.py, progress.py | `research_progress` chunks in phase order scouting? (only when scout not finalized), executing (steps_done 0,1,2,3), synthesizing, done; every chunk is a `data: {json}` line with parent_type research |
| P2 | step durations | same run | happy | progress.py | each finished step has duration_ms >= the sleep (300 ms) taken from real event timestamps; pending steps null |
| P3 | stored snapshot == last chunk | read the collection from the DB after the run | happy | agent.py | equal to the last streamed snapshot |
| P4 | available after a reload | start the real backend, GET /api/chats/<id> | happy | history_ops.py | the assistant message's `collections` holds the `research_progress` item with the final snapshot |
| P5 | awaiting approval | run with a plan but no approval event | edge | agent.py | last chunk phase awaiting_approval, steps pending |
| P6 | failure | executor section raises | failure | agent.py | last chunk phase failed, the failing step state failed, chat research_state failed; stored and served after reload |
| P7 | publishing never stops research | DB write of the collection raises once | failure | agent.py | the run still completes; error logged |
| P8 | older chats | a chat with no research collections loads over HTTP | regression | | 200, no collections key problems |
| R1 | no server errors | backend log | non-functional | | no traceback |

Scripts: `scripts/drive98.py` (in-process driver), `scripts/check98.py` (HTTP check), `scripts/run_all.sh`.
### Results (2026-11-11)
Verified at HEAD 32d33f7 plus uncommitted:
- backend/database/wrapper/tests/test_history_ops.py 5de64523ee16d700d7aa423702dd5483c467f242
- backend/tools/agents/research_agent/README.md 3888c59d9f2fcaaf4ce71ea0bd020de11ec2bd14
- backend/tools/agents/research_agent/agent.py 6c2f9ad55447b00a557e7b4e299f8ab57637f739
- backend/tools/agents/research_agent/constants.py b0efcc3d423a0fcaf20cf604eeb3d9538cf899ab
- backend/tools/agents/research_agent/tests/test_agent.py fc6ec840d00e04914eaf9391f7edbd2a70356334
- backend/tools/agents/research_agent/tests/test_constants.py 9ab2ff4e5e69c9516826c6f3cd41036d309d5346
- docs/standards/api.md e9332cb6d8775018807666a2402358f9fb2a1b16
- frontend/src/api/types.ts 33ed7c560b962512f0d34a7a7b50e400a4e4bb17
- frontend/src/features/chat/stream-reducer.test.ts d768967c0065bf5be542c3859b6523865dfd1bee
- frontend/src/features/chat/stream-reducer.ts a024b22d43d198a5cade4b4c29da54ef0f0d970b
- backend/tools/agents/research_agent/progress.py 18c46f6b253d52fb8ddbfdb1227f1f18ee006cff
- backend/tools/agents/research_agent/tests/test_progress.py 1ccb3e51793182b5f9b5b1733f13536daa24a1e3

Evidence: `~/.claude/tickets/My-AI/MYAI-98-evidence/` (results.txt, drive.log, backend.log, scripts/). Real ResearchAgent code and real DB in-process on a temp data dir, then the real backend read over HTTP; torn down (port free, dir removed).

| ID | Status |
|----|--------|
| P1-P3 | PASS (phases executing x4 with steps_done 0,1,2,3, then synthesizing, done; step durations 303-304 ms from real timestamps; stored snapshot equals the last chunk) |
| P4 | PASS (reload: the assistant message served by GET /api/chats/<id> carries the final snapshot) |
| P5 | PASS (awaiting approval, steps pending) |
| P6 | PASS (failure: phase failed, failing step failed, chat research_state failed, served after reload) |
| P7 | PASS (a failing progress write is skipped and research completes) |
| P8 | PASS (older chat loads) |
| R1 | PASS (no traceback in the backend log) |
Gaps: the scouting phase chunk and the in-section start publish are not exercised live (the stand-in section replaces `_run_single_section`, and scout was pre-finalized); the real pipeline (model, web search, user approval) was not run. Unit tests cover the publish points around the executor loop.
Regression: backend+tests 1682, frontend 1106 pass.
Verdict: verified (9 PASS, 0 FAIL, 0 BLOCKED), with the gaps above.
- Re-verify note (2026-11-11, after review fixes): the harness's synthesis stand-in now stores the completion event like the real synthesis (a harness bug: with the fix, 'done' needs it); P1 and P7 first failed against the stale stand-in, then passed. Final: 9 PASS, 0 FAIL.

## Review history
### Round 1 - 2026-11-11
Verdict: Request changes (4 MAJOR) -> after resolution Approve. One Haiku reviewer, working tree vs develop. 13 findings.
- R1-1 [MAJOR] agent.py:403 - 'done' published whenever synthesis returns, also when paused or halted - Static - Fixed (done only with the stored completion event; failed after a halting failure event; nothing when paused; tests)
- R1-2 [MAJOR] 'planning' never published - Static - Fixed (published before the planner; test)
- R1-3 [MAJOR] pages read stale during a section - Static - Fixed in part: also published after the initial and gap searches of each section (not mid-search; documented in api.md). No unit test for the in-section publishes (the section state machine is not unit-testable cheaply); not exercised live either
- R1-4 [MAJOR] progress.py - a retried step stays 'failed', duration spans the failed attempt - Static - Fixed (state by event order, last start to complete; tests)
- R1-5 [MINOR] plan missing / invalid exits publish nothing - Fixed (failed; test)
- R1-6 [MINOR] duration spans downtime - Fixed with R1-4 (last start), documented
- R1-7 [MINOR] bare Exception in _publish_progress - Rejected: never stopping research on a display failure is the requirement; the broad catch is deliberate and noted in the docstring
- R1-8 [MINOR] re-attached stream misses the snapshot - Documented in api.md (the stored collection and the next snapshot cover it)
- R1-9 [MINOR] StoredMessage lacks collections - Fixed (the first insert had not applied)
- R1-10 [NIT] duration comment - Fixed. R1-11 [NIT] inf timestamp - Fixed (test). R1-12 [NIT] implicit Optional - Fixed. R1-13 [NIT] blank lines/import - Rejected (cosmetic)
Resolved inline by the author. Re-verified: live harness re-run, backend+tests, ruff, typecheck, lint.

## Log
- 2026-11-11: created (split from MYAI-96 at the user's request)
- 2026-11-11: linked blocked_by MYAI-97
- 2026-11-11: linked split_from MYAI-96
- 2026-11-11: plan validated, 2 rounds (assumption: step durations from event timestamps, not MYAI-97)
- 2026-11-11: unlinked blocked_by MYAI-97 (user decision: research step times come from stored event timestamps)
- 2026-11-11: autopilot started (batch-autopilot)
- 2026-11-11: implemented, smoke tests pass
- 2026-11-11: verify: 9 PASS, 0 FAIL, fix 0/10
- 2026-11-11: review round 1 resolved (10 fixed, 3 rejected/documented); re-verified
- 2026-11-11: batch-autopilot: shipped, base develop (https://github.com/archit342000/My-AI/pull/127)
