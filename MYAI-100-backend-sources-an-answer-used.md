---
id: MYAI-100
title: "Backend: sources an answer used"
status: in-progress
created: 2026-11-11
updated: 2026-11-11
links:
  conflicts_with: [MYAI-97, MYAI-99]
  split_from: [MYAI-96]
---

## Description
Item 4 of MYAI-96. The design shows numbered source chips under an answer ("1 playwright.dev · Auto-waiting") and a small number in the text where a source is used. The server sends no list of sources for an answer.

Needed: the sources an answer used (title, address or file and line), saved with the message, and a marker in the text where each is cited.

## Acceptance criteria
- [x] An answer's sources (title, address or file and line) are sent and stored with the message
- [x] The answer text marks where each source is cited
- [x] Answers without sources are unchanged
- [x] `docs/standards/api.md` and `frontend/src/api/` types are updated in the same change
- [x] Frontend follow-up noted: source chips under an answer

## Plan
**Date:** 2026-11-11  **Status:** Validated

### Objective
Keep the sources an answer used (web pages from search and page visits, and files read with line ranges), number them for the turn, have the model mark where it cites each one, and store and send the cited sources with the answer so the chat can show numbered source chips.

### Context
- Requirement: ticket Description and Acceptance criteria. Planned against `develop` at 7dd16d3.
- Rules: `AGENTS.md`; `docs/standards/api.md` (SSE extensions, additive contract changes update `frontend/src/api/`); `docs/standards/testing.md`; `backend/prompts/README.md` (templates).
- Current behaviour:
  - `backend/tools/agents/search_web_agent/agent.py` `flow_fn` gets Tavily `results` (each with `url`, `title`, `content`) and returns either Tavily's `answer` (no URLs), formatted snippets with `Title:`/`URL:`, raw results with `[Source]: <url>`, or an LLM synthesis; the result string is set on `agent.result` (`agent` is the `AgentHandler`).
  - `backend/tools/agents/visit_page_agent/agent.py` `flow_fn` scrapes one `url` and returns raw content or a synthesis.
  - `read_fs_file` (`backend/tools/catalog/filesystem.py`, implementation `backend.file_system.manager.read_fs_file`) is a pure tool with `path`, `start_line`, `end_line` arguments.
  - `backend/chat/tool_handler.py` `ToolHandler.handle_tool_calls` stores each result with `db.add_tool_result` and yields a `tool_result` delta; the tool result text is what the model sees. `backend/chat/agent_handler.py` `AgentHandler` carries `result` back to it.
  - The research agent numbers its own sources in its report file (`visited_urls`), separate from chat answers.
  - `backend/prompts/templates/formatting_rules.txt` (loaded by `backend/chat/prompt_builder.py`) already offers Markdown footnotes `[^1]`; there is no citation rule.
  - `backend/database/wrapper/history_ops.py` attaches collections anchored on an assistant message's parent user message to that message as `collections`.
  - `backend/chat/turn_handler.py` `TurnHandler.handle_turn` wraps every main turn (MYAI-97 adds turn-end work there; this plan adds next to it; linked `conflicts_with` MYAI-97 and MYAI-99).

### Approach
- New module `backend/chat/sources.py`: `SourceRegistry` per chat (loaded at the start of each main turn with `db.get_collections(chat_id, parent_message_id=chat_id, parent_type="main")`, taking the `source_registry` row and JSON-decoding its `items` before `from_list()`; saved with `db.add_collection(chat_id, chat_id, "main", "source_registry", registry.to_list(), overwrite=True)` once per tool result that added sources (before the numbered result is stored), so a turn that fails or is cancelled after numbering a result still leaves the numbers stored; numbers stay unique across turns and an old `[[1]]` still means the same source) with `add(kind, title, locator, detail=None) -> int` (numbers from 1, de-duplicated by `kind` + `locator`), `cited(text) -> list` (sources whose marker appears in `text`, in number order), and `MARKER_RE`. Kinds: `web` (`locator` = URL, `title` = page title) and `file` (`locator` = path, `detail` = `"lines A-B"` when given).
- Marker: `[[n]]` (double brackets, so it cannot clash with Markdown links or footnotes). A new rule in `formatting_rules.txt`: "When a tool result lists numbered sources, cite them with `[[n]]` right after the sentence that uses them; cite only numbers you were given."
- Registration (main turn only): agents report sources on a new `AgentHandler.sources` list (`search_web` adds each Tavily result's `url`/`title` in every depth; `visit_page` adds its `url` as both locator and title, since the page tool returns no title). `ToolHandler` registers them after the agent returns, and for `read_fs_file` registers the path and line range from the call's arguments. It then adds the numbers to the tool result stored and sent, so the model sees them: a string result gets a short block `Sources:\n[[1]] <title> - <locator>` appended; a dict result (such as `read_fs_file`'s) gets a `"sources"` key before it is serialized.
- Turn end: `TurnHandler.handle_turn` gains an optional `sources` argument (the registry), passed by `ChatHandler._run_background_turn`. After `run_fn` finishes normally it reads the turn's main assistant rows (`db.get_messages(chat_id)` filtered to `role == "assistant"` and id greater than the user message's), takes `registry.cited(...)` over their joined text, stores them as a `sources` collection anchored on the last of those rows' id (so it is served on that row only), and yields `"data: " + json.dumps({"sources": [{"n", "kind", "title", "locator", "detail"}]}) + "\n\n"`. No cited sources: nothing stored or sent, so answers without sources are unchanged.
- The registry lives on the main `ChatHandler` for the turn (`ChatHandler.__init__` sets `self.source_registry = None`; `_run_background_turn` loads it); `ToolHandler` registers only when its chat handler holds a registry, so sub-agents' isolated handlers (which never get one) skip it whatever their `parent_type`; research keeps its own report citations.
- Frontend contract: `AnswerSource` type, `StreamChunk.sources`; chips and marker rendering are the noted follow-up.
- Rejected: asking the model to output a sources list (unreliable, unverifiable); sources from every tool result (noise; only real pages and file reads count).

### Out of scope
- Source chips and marker rendering in the frontend (follow-up, recorded in Implementation notes).
- Sources inside research reports and sub-agents' own answers.

### Steps
#### Step 1: Source registry
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/chat/sources.py` (create): `SourceRegistry`, `MARKER_RE`, `format_sources_block`; `backend/chat/tests/test_sources.py` (create).
- **Change:** numbering, de-duplication, cited-source extraction, the text block appended for the model, `to_list()` / `from_list()` for storing and loading.
- **Verification:** tests: numbers from 1, duplicate locator keeps its number, a registry loaded from a stored list continues numbering after its highest number, `cited` returns only cited ones in order and ignores unknown numbers, block format.

#### Step 2: Agents report sources
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/chat/agent_handler.py` (modify): `AgentHandler.sources` (reset per `execute_agent`); `backend/tools/agents/search_web_agent/agent.py`, `backend/tools/agents/visit_page_agent/agent.py` (modify): `flow_fn`; their `tests/test_agent.py` and `backend/chat/tests/test_agent_handler.py` (modify).
- **Change:** append `{"kind": "web", "title", "locator", "detail": None}` per result or page; error paths add nothing.
- **Verification:** tests: each depth of `search_web` reports the result URLs; `visit_page` reports its URL; an error or "No results" reports none; `sources` is empty at the start of each run.

#### Step 3: Register and number in ToolHandler
- **Status:** todo
- **Depends on:** 1, 2
- **Files:** `backend/chat/handler.py` (modify): `_run_background_turn` loads the registry from the chat's `source_registry` collection onto the main handler and passes it to `TurnHandler.handle_turn`; `backend/chat/tool_handler.py` (modify): agent and pure branches of `handle_tool_calls`; `backend/chat/tests/test_handler.py`, `backend/chat/tests/test_tool_handler.py`, `backend/chat/tests/test_turn_handler.py` (modify).
- **Change:** add the optional `sources=None` parameter to `TurnHandler.handle_turn` (consumed there, not forwarded to `run_fn`) so the call from `_run_background_turn` works from this step on; when the chat handler holds a registry, register agent sources and `read_fs_file` path and lines, save the registry, and add the numbers to the stored and sent tool result.
- **Verification:** tests: a `search_web` result gets `Sources:` with `[[1]]`, `[[2]]`; a later `read_fs_file` dict result gets `"sources": [{"n": 3, ..."detail": "lines 10-20"}]`; a second turn of the same chat continues at `[[4]]`, also when the first turn was cancelled after numbering; an isolated sub-agent handler without a registry leaves results unchanged; a turn runs with `sources` passed and `run_fn` receives no `sources` keyword; the handler test shows the registry loaded and passed to `handle_turn`; a repeated URL keeps its number; a sub-agent's tool call is unchanged.

#### Step 4: Prompt rule
- **Status:** todo
- **Depends on:** 3
- **Files:** `backend/prompts/templates/formatting_rules.txt` (modify); `backend/chat/tests/test_prompt_builder.py` (modify).
- **Change:** add the citation rule as item 7 inside the `<formatting_directives>` block.
- **Verification:** prompt-builder test finds the rule in the built system prompt.

#### Step 5: Store and send cited sources
- **Status:** todo
- **Depends on:** 3
- **Files:** `backend/chat/turn_handler.py` (modify): `handle_turn`; `backend/chat/tests/test_turn_handler.py`, `backend/database/wrapper/tests/test_history_ops.py` (modify).
- **Change:** use the `sources` parameter added in Step 3; on normal completion do the turn-end work in Approach; no `sources` chunk or collection when none are cited or when the turn fails or is cancelled (the registry was already saved as sources were added).
- **Verification:** tests: an answer citing `[[2]]` stores and sends only source 2 as a `data: ...\n\n` line; an answer citing a number from an earlier turn resolves to that earlier source; no markers sends nothing; a cancelled turn sends nothing; the served history attaches `sources` to the assistant row and not to the user row.

#### Step 6: Frontend types and docs
- **Status:** todo
- **Depends on:** 5
- **Files:** `frontend/src/api/types.ts` (modify): `AnswerSource`; `frontend/src/features/chat/stream-reducer.ts`, `stream-reducer.test.ts` (modify): `StreamChunk.sources`; `docs/standards/api.md` (modify); `backend/chat/README.md`, `backend/tools/agents/search_web_agent/README.md`, `backend/tools/agents/visit_page_agent/README.md`, `backend/prompts/README.md` (modify where they describe these flows).
- **Change:** optional, additive types; document the marker, the tool-result block, the `sources` chunk and collection; record the frontend follow-up in Implementation notes. Check that the legacy UI (`static/script.js`, `static/js/`) is unaffected by the added keys (it reads named fields only) and record the check in Implementation notes, as `docs/standards/api.md`'s breaking-change rule requires.
- **Verification:** `npm run typecheck`, `npm run lint`, `npm run test` pass; `venv/bin/python -m pytest tests -q -p no:cacheprovider` passes.

### Tests
- Backend: `EMBEDDING_URL="http://mock" AI_URL="http://mock" AI_API_KEY="dummy" PYTHONPATH=. venv/bin/python -m pytest backend/chat/tests`, `backend/tools/agents/search_web_agent/tests`, `backend/tools/agents/visit_page_agent/tests`, `backend/database/tests`, then `backend` and `tests`; `venv/bin/ruff check .`.
- Frontend: in `frontend/`, `npm run typecheck`, `npm run lint`, `npm run test`.
- Gate: `scripts/check.sh`.

### Risks and open questions
- The model may not cite; then no sources are shown, which is honest. Prompt wording may need tuning after real use.
- Shares `turn_handler.py` and `tool_handler.py` with MYAI-97 and MYAI-99: land after them or expect merge conflicts (suggest `conflicts_with` links).
- Decision: `[[n]]` marker (assumption; the frontend follow-up renders it as a chip).

### Success criteria
- [ ] Web pages and file reads used in a turn are numbered and shown to the model with their numbers
- [ ] An answer's cited sources (title, address or file and lines) are stored with it and sent in the stream
- [ ] The answer text marks each citation with `[[n]]`
- [ ] Answers without citations are unchanged
- [ ] `docs/standards/api.md` and `frontend/src/api/` types are updated in the same change; frontend follow-up recorded

### Reviewer brief
- Objective: web pages and file reads used in a turn are numbered per chat, the model cites them as `[[n]]`, and the cited sources (kind, title, address or path, lines) are stored with the answer and sent as a `sources` SSE chunk.
- Decisions: `SourceRegistry` in `backend/chat/sources.py`, stored per chat as a `source_registry` collection and saved whenever a tool result adds sources; agents report sources on `AgentHandler.sources` (`search_web`, `visit_page` with its URL as title); `read_fs_file` adds path and lines; numbers are added to the stored tool result (text block or `sources` key on dict results); only the main handler holds a registry; `TurnHandler.handle_turn(sources=...)` stores cited sources on the turn's last assistant row and sends them after a normal finish; citation rule is item 7 of `formatting_rules.txt`; frontend gets optional types only.
- Out of scope: chips and marker rendering, research report citations, sub-agents' own answers.
- Success: numbered sources shown to the model, cited ones stored and sent, `[[n]]` markers, uncited answers unchanged, api.md and frontend types updated.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- Round 1: validator FAIL. Judged FAIL. Valid BLOCKING, fixed: numbering restarted every turn while stored results kept old numbers (registry is now per chat, loaded and saved); `TurnHandler` had no way to get the registry (parameter, call site and DB read named). Valid MINOR, fixed: SSE terminator; `visit_page` has no title (URL used); dict results get a `sources` key; collection anchored on the assistant row, not the user row; handler test file; rule placement; conflict links added (MYAI-97, MYAI-99).
- Round 2 (diff-scoped): validator FAIL. Judged FAIL. Valid BLOCKING, fixed: the new `handle_turn` parameter moved into Step 3 so no step leaves turns broken; the registry is saved during the turn, not only at its end. Valid MINOR, fixed: load/save calls named; registry presence (not `parent_type`) gates registration.
- Round 3 (diff-scoped): validator PASS. Judged PASS. Valid MINOR, fixed inline: `source_registry = None` default in `ChatHandler.__init__`; `test_turn_handler.py` added to Step 3; citations read from all the turn's assistant rows; registry saved once per tool result.
- 2026-11-11 correction after validation: database test moved to `backend/database/wrapper/tests/test_history_ops.py` (1:1 rule, found while validating MYAI-101).
- 2026-11-11 correction after validation: last step also checks the legacy UI against the added keys (`docs/standards/api.md`), found while validating MYAI-102.

## Implementation notes
### Autopilot run (2026-11-11)
- Mode: automatic (batch-autopilot, item 5/9)
- Branch: feature/answer-sources  PR base: develop  Starting commit: 32d33f73cd578e1a29080f9a12092caf1c36c073
- Dirty before start: none
- Work files: none yet
- Counters: fix 0/10, review 1/5, re-verify 1
- Last completed stage: 6 ship  Next: none
- Hard blocker: none
- WIP commit: none

### Autopilot decisions (2026-11-11)
- Stage 1: plan already Validated in ticket; reused.
### Baseline (2026-11-11)
- backend/chat, search_web_agent, visit_page_agent, database tests all passed before changes (about 330 in backend/chat).

### Implementation progress
- [x] Step 1: `backend/chat/sources.py` (`SourceRegistry`, `MARKER_RE`, `format_sources_block`) + tests. Dedup key is kind + locator + detail (so the same file read with other lines is a new source).
- [x] Step 2: `AgentHandler.sources` (reset per run); `search_web` reports each result with an address, `visit_page` its URL (title = URL) - agents and their tests
- [x] Step 3: `ToolHandler` registers and numbers (agent results get a `Sources:` block, `read_fs_file` dict results a `sources` key; registry saved once per result that added sources); `ChatHandler.source_registry` loaded per main turn and passed as `sources=` to `TurnHandler.handle_turn` (a keyword-only parameter)
- [x] Step 4: citation rule as item 7 in formatting_rules.txt + prompt-builder test
- [x] Step 5: `TurnHandler` stores the cited sources as a `sources` collection on the turn's last assistant row and sends one `sources` event (not after an exception, cancellation or stop; skipped when nothing is cited)
- [x] Step 6: frontend `AnswerSource`, `StoredCollection`, `StoredMessage.collections`, `StreamChunk.sources` + reducer test; api.md, READMEs. Legacy UI check: `static/script.js` reads `json.choices?.[0]?.delta` before use, so the `sources` chunk is ignored; the `Sources:` block is plain text in a tool result.
- Deviation: the stop check (`task_manager.is_interrupted`) was added in `TurnHandler` for the sources path (a stop ends the run normally); the same line also exists in the turn-duration change, expect a trivial merge conflict in `turn_handler.py`.
- Frontend follow-up (not done): source chips under an answer and `[[n]]` rendering.

### Smoke test (2026-11-11)
- backend + tests 1699 pass; frontend typecheck, lint, 1106 unit tests; ruff clean.
- Stage 5: resolve-review done inline by the author (not via the skill).
PR: https://github.com/archit342000/My-AI/pull/128, branch feature/answer-sources, base develop

## Verification
### Verification plan (2026-11-11)
**Diff base:** develop tip. Full form (stream contract, stored data, tool results shown to the model).

**Environment:** real Flask backend on a temp data dir (port 5316, static auth) with a scripted model (`scripts/stub.mjs`, port 5317) that reads the tool result it is given and cites the source number it finds there, so the model-sees-the-numbers path is exercised. The only tool available live is `read_fs_file` (a file source); web sources need the Tavily and Playwright MCP services, which are not available, so their reporting is covered by unit tests only (gap). Driver `scripts/verify100.py` is HTTP only. Never touches backend/data. Teardown: kill backend and stub, rm temp dir, check ports.

| ID | Criterion | Scenario | Type | Files | Expected |
|----|-----------|----------|------|-------|----------|
| S1 | numbered, shown to the model | turn A: model reads notes.md lines 2-4 | happy | tool_handler.py, sources.py | tool_result delta and stored tool row hold a `sources` list with n=1, kind file, detail "lines 2-4"; the stub cited [[1]] only because it found n in the tool result |
| S2 | cited sources stored and sent | same turn | happy | turn_handler.py | last stream event is `{"sources": [...n=1...]}`; GET chat: that assistant row has a `sources` collection equal to it; the user row has none |
| S3 | numbers continue across turns | turn B reads lines 6-8 | happy | handler.py | n=2 (new lines = new source), cited [[2]], sources event lists only 2 |
| S4 | repeat keeps its number | turn C reads lines 2-4 again | edge | sources.py | n=1 again |
| S5 | old number resolves later | turn D: answer cites [[1]] with no tool call | edge | turn_handler.py | sources event lists source 1 (from turn A) |
| S6 | uncited answers unchanged | turn E plain answer | regression | | no sources event; no sources collection on that row |
| S7 | unknown number ignored | turn F cites [[99]] | edge | | no sources event, nothing stored |
| S8 | stopped turn | SLOW answer citing [[1]], POST /stop after a few chunks | failure | turn_handler.py | no sources event; no sources collection |
| S9 | reload | GET the chat again | edge | history_ops.py | same collections; the hidden source_registry is not served on any message |
| R1 | no server errors | backend log | non-functional | | no traceback |

Scripts: `scripts/stub.mjs`, `scripts/start_backend2.sh`, `scripts/verify100.py`, `scripts/run_all.sh`.
### Results (2026-11-11)
Verified at HEAD 32d33f7 plus uncommitted:
- backend/chat/README.md 505f6222aa665e7d4eb7f597a2323b1b54935e37
- backend/chat/agent_handler.py 347e4967769502dc7a9a0688bc8bcc0e432197f1
- backend/chat/handler.py 0f21759c29d0b1b4a3a2fcb466df7d173fea470e
- backend/chat/tests/test_agent_handler.py 188bdb5e69987737a5495515f8661239ef5f4abd
- backend/chat/tests/test_handler.py 7d22aa0beb51ebc3fb7d518f86acc37fea3a5665
- backend/chat/tests/test_prompt_builder.py e1f359ae8513064d52dcf46fe3429335b3397579
- backend/chat/tests/test_tool_handler.py 342178a927e645516b3d1785f931d8679abf484e
- backend/chat/tests/test_turn_handler.py 99f23889d4c47dac5376178a0f4e9969fe2a0e6c
- backend/chat/tool_handler.py e456600b3ece29f35df7d1143824818cfb6cef72
- backend/chat/turn_handler.py 618170a1f07251ba4e621996d3fddbcc3246af91
- backend/database/wrapper/tests/test_history_ops.py 639edc035f125716a87ad132ee6bfd12e4436b68
- backend/prompts/README.md f30cf0dc9e0a199801a313b168590d3467e6e6ef
- backend/prompts/templates/formatting_rules.txt 3236f481aa1f413a14d9f7e1dac3ca083def0d9c
- backend/tools/agents/search_web_agent/README.md d30da79859b4df5399a2b88f9ddf40dc59051b56
- backend/tools/agents/search_web_agent/agent.py 039b2c6c8447b9e4c57190e7e1ceeb0e9b9e23be
- backend/tools/agents/search_web_agent/tests/test_agent.py 6e4181532ab0000c43423d650417b8b90cb2efa0
- backend/tools/agents/visit_page_agent/README.md d68f813954b81c1d4a41e7109d50fa8d9274704f
- backend/tools/agents/visit_page_agent/agent.py 9d10bcf54e4516328ab366233f10c3a61ffd8a6a
- backend/tools/agents/visit_page_agent/tests/test_agent.py 7cc7ff1b2b9ac7ba05e00d4bcf0de5843fcd0be2
- docs/standards/api.md f290716b3dc883d3cb9ed8ed7b1ce05502eaea85
- frontend/src/api/types.ts a11f7f90b706dfc36abbec36554323dd989f1f14
- frontend/src/features/chat/stream-reducer.test.ts 2ad031c8d1be5daafe258482fa6f65eb16fdbff0
- frontend/src/features/chat/stream-reducer.ts 53c82270ef049a68a44f8ddd7b226e87fd3162c4
- backend/chat/sources.py 1a70abb3c2469fc1b04ffddfe00d77adda31ba73
- backend/chat/tests/test_sources.py a44ac39a6472fae2de5b90f3d79234688c18f114

Evidence: `~/.claude/tickets/My-AI/MYAI-100-evidence/` (results.txt, backend.log, stub.log, scripts/). Real backend with a scripted model that cites the number it finds in the tool result; torn down (ports free, dir removed). The first run hit a harness bug (the served tool row's content is already decoded); fixed in the script, then all passed.

| ID | Status |
|----|--------|
| S1 | PASS (read_fs_file result numbered in the stream and in the stored tool row; the model cited the number it was shown) |
| S2 | PASS (sources event last; stored on the turn's last assistant row only) |
| S3-S5 | PASS (numbers continue across turns, a repeat keeps its number, an old number resolves later) |
| S6, S7 | PASS (uncited and unknown-number answers send and store nothing) |
| S8 | PASS (stopped turn: no sources) |
| S9 | PASS (reload serves the sources collections; the registry is not served) |
| R1 | PASS (no traceback) |
Gaps: web sources (search_web, visit_page) were not exercised live (the Tavily and Playwright MCP services are not available): covered by unit tests of the agents and of ToolHandler only.
Regression: backend+tests 1699, frontend 1106 pass.
Verdict: verified (10 PASS, 0 FAIL, 0 BLOCKED), with the web-source gap.

## Review history
### Round 1 - 2026-11-11
Verdict: Request changes (2 MAJOR) -> after resolution Approve. One Haiku reviewer, working tree vs develop. 10 findings.
- R1-1 [MAJOR] an unreadable stored registry became empty and was overwritten (numbers restart) - Static - Fixed (only an absent registry starts empty; an unreadable one raises before any tool runs; tests)
- R1-2 [MAJOR] a failed registry save was swallowed after the numbers reached the model - Static - Fixed (the save error propagates, so the call fails and nothing numbered is stored or shown; test)
- R1-3 [MINOR] turn-end sources write logs and continues while other errors propagate - Rejected as deliberate: the answer already exists and the sources are display data; same pattern as the turn's own state write; sqlite failure test added
- R1-4 [MINOR] titles could forge extra `[[n]]` lines - Fixed (titles collapse to one line, capped at 200; tests)
- R1-5 [MINOR] non-http web locators - Fixed (only http/https are sources; test)
- R1-6 [MINOR] file detail wrong for partial reads, outline reads, `/a.py` vs `a.py` - Fixed (from line N, lines 1-N, outline; path normalised; api.md aligned)
- R1-7 [MINOR] registry anchored on the chat id could attach to a message with the same numeric id - Fixed (anchor `chat:<id>`; test with a numeric chat id)
- R1-8 [MINOR] missing tests - Fixed (sqlite failure, `_id_after`, forged title, non-http, partial reads); the resumed-call case is the existing idempotency guard test
- R1-9 [NIT] `[[1, 2]]` not counted - Documented in the prompt rule (one number per marker)
- R1-10 [NIT] bool `n` accepted - Fixed; loading all messages at turn end noted, acceptable
Resolved inline by the author. Re-verified: live harness re-run, backend+tests, ruff.

## Log
- 2026-11-11: created (split from MYAI-96 at the user's request)
- 2026-11-11: linked split_from MYAI-96
- 2026-11-11: linked conflicts_with MYAI-97 (both change turn_handler.py and tool_handler.py)
- 2026-11-11: linked conflicts_with MYAI-99 (both change turn_handler.py and tool_handler.py)
- 2026-11-11: plan validated, 3 rounds
- 2026-11-11: autopilot started (batch-autopilot)
- 2026-11-11: implemented, smoke tests pass
- 2026-11-11: verify: 10 PASS, 0 FAIL (web sources not live), fix 0/10
- 2026-11-11: review round 1 resolved (8 fixed, 2 rejected/documented); re-verified
- 2026-11-11: batch-autopilot: shipped, base develop (https://github.com/archit342000/My-AI/pull/128)
