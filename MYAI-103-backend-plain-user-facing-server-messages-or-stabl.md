---
id: MYAI-103
title: "Backend: plain user-facing server messages or stable error codes"
status: in-progress
created: 2026-11-11
updated: 2026-11-11
links:
  split_from: [MYAI-96]
---

## Description
Item 7 of MYAI-96. Some error and status texts from the server reach the screen as written: three full stops instead of an ellipsis, error codes, raw exception text on the Logs page and in a failed file run.

Needed: a pass over user-facing server messages against the design's wording rules (say what happened and what to do, no codes), or a stable error code per failure so the frontend can word it.

## Acceptance criteria
- [x] User-facing server messages follow the wording rules, or each failure has a stable code
- [x] No raw exception text reaches the screen from the Logs page or a failed file run
- [x] Tests that assert exact messages are updated
- [x] `docs/standards/api.md` and `docs/standards/errors-and-logging.md` reflect the rule

## Plan
**Date:** 2026-11-11  **Status:** Validated

### Objective
Stop raw exception text, internal codes and three-dot ellipses from reaching the screen: every error or status text the server sends to the person (route error bodies, stream errors, retry notices, a failed file run) becomes a short, fixed, plain message that says what happened and what to do, while the detail goes to the logs.

### Context
- Requirement: ticket Description and Acceptance criteria; the Description allows a wording pass or stable codes. Planned against `develop` at 7dd16d3.
- Rules: `docs/standards/errors-and-logging.md` ("User-facing messages are short and actionable. Internal detail goes to logs"; `log_event` conventions, errors end in `_error`); `docs/standards/api.md` ("Do not return stack traces or `str(e)` of internal exceptions from new code"; error body `{"error": ...}`; streams send `data: {"error": ...}`); `docs/tools.md` (tool results begin `Error`/`Failed` for the model; kept); `AGENTS.md`.
- Current behaviour (user-facing sites that send `str(e)` or three dots):
  - Route 500 bodies with `str(e)`: `backend/file_system/router.py` (`create_fs_file_route`, `create_directory_route`, `delete_directory_route`, `update_file_system_endpoint`, `remove_fs_file_endpoint`); `backend/logging/router.py` (six routes, shown on the Logs page); `backend/files/router.py` (upload); `backend/chat/router.py` (history, `chat_completions`, `resume_chat`, stop).
  - Stream errors with `str(e)`: `backend/chat/router.py` `chat_completions` stream loop; `backend/chat/handler.py` `_handle_tool_execution`; `backend/task_manager/executor.py` `TaskExecutor` (unhandled turn failure).
  - Retry notices: `backend/inference/engine.py` sends `__redact__` messages "Inference failed validation. Retrying..." and `f"Error: {str(e)}. Retrying..."`; the frontend (`features/chat/stream-reducer.ts`) only swaps a trailing "..." for "…".
  - Failed file run: `backend/tools/implementations/code_executor.py` `run_file` has three resolve branches: `FileNotFoundError` (plain text), `ValueError` returning `f"Error: Failed to resolve file path: {e}"`, and any other error returning "Error: Failed to resolve file path." (logged); shown in the run card. `backend/tools/router.py` `api_run_file` answers `{"error": "Failed to run file"}`; `backend/files/router.py` answers `{"error": "Failed to process file"}`.
  - Agent failure texts with `str(e)`, shown as events in the Thought process and stored: `backend/tools/agents/research_agent/agent.py` (`❌ ... failed: {str(e)[:200]}` events, `flow_fn`'s `Research Agent failed: {str(e)}` event and result), `backend/tools/agents/document_agent/agent.py` (`Document agent failed: {str(e)}`), `backend/tools/agents/visit_page_agent/agent.py` (`Visit page failed: {str(e)}`), `backend/tools/agents/search_web_agent/agent.py` (`Search failed: {str(e)}` and the retry variant), `backend/tools/agents/base.py` (`<display name> failed: {str(e)}`).
  - Research status texts in `backend/tools/agents/research_agent/constants.py` and some literals in `agent.py` end in "...". Only some constants are compared on resume (for example `EVENT_SCOUT_FINALIZED`, `EVENT_PLAN_APPROVED`, the section complete markers, the `*_DONE` markers read by `_parse_section_state`, `EVENT_SYNTHESIS_START` and the literal "Synthesizing final report sections...", both matched by equality in `_run_synthesis`); a stored row's text must keep matching its constant.
  - The frontend (`frontend/src/features/chat/stream-reducer.ts`) swaps a trailing "..." for "…" only on the retry notice.

### Approach
- Wording pass, not codes (decision: fewer moving parts; the frontend already shows `error` as text). Rules, added to `errors-and-logging.md`: one or two short sentences; say what happened, then what to do; no exception text, ids, codes or stack traces; one "…" character, never "..."; the detail goes to `log_event` (`<component>_<event>_error`, with `error` = `type(e).__name__` and the message).
- Each site above gets a fixed message, for example: create file "Could not create the file. Try again."; logs "Could not read the logs. Try again in a moment."; upload "Could not upload the file. Try again."; stream "Something went wrong while answering. Try sending again."; retry notices "Checking the answer again…" and "The model did not respond. Trying again…"; failed path resolution keeps the resolver's own `ValueError` text (already written for people) without the "Failed to resolve file path:" prefix, and a generic "Error: Could not open that file." for anything else. Status codes stay as they are.
- Agent failures: the event and result keep a leading `Error`/`... failed` word (the model and `docs/tools.md` need it) but drop the exception text, which goes to `log_event`; for example "❌ The search step failed. Research stopped; you can start it again." and "Search failed. Try again or rephrase the request."
- Research texts: "..." becomes "…" in every research status text whose constant or literal is never compared on resume (each one checked with a grep in Step 5); a constant that is compared keeps its exact text, so stored runs still resume; the list of kept ones is recorded in Implementation notes.
- Also reworded: `api_run_file`'s "Failed to run file" ("Could not run the file. Try again.") and the files router's "Failed to process file" ("Could not read the uploaded file. Try another file.").
- Frontend: no change needed; the "..." swap in `stream-reducer.ts` stays for older servers.
- Rejected: stable error codes per failure (needs a code table and frontend wording for each; not needed once the server's own wording is plain).

### Out of scope
- Research markers that are compared on resume (reason above) and model-facing tool texts that contain no exception text.
- Error status codes and response shapes (unchanged).

### Steps
#### Step 1: Wording rule
- **Status:** todo
- **Depends on:** none
- **Files:** `docs/standards/errors-and-logging.md` (modify), `docs/standards/api.md` (modify: point the error-body rule at it).
- **Change:** add the rules from Approach and the kept exceptions.
- **Verification:** `EMBEDDING_URL="http://mock" AI_URL="http://mock" AI_API_KEY="dummy" PYTHONPATH=. venv/bin/python -m pytest tests -q -p no:cacheprovider` passes.

#### Step 2: File-system and files routes
- **Status:** todo
- **Depends on:** 1
- **Files:** `backend/file_system/router.py`, `backend/files/router.py` (modify); `backend/file_system/tests/test_router.py`, `backend/files/tests/test_router.py` (modify).
- **Change:** fixed messages at the listed sites, keeping `"success": False` where the body has it today; `log_event` with the detail (import `log_event` where missing); the files router's "Failed to process file" reworded.
- **Verification:** tests force each failure and assert the fixed message, the unchanged body keys, that the exception text is absent, and that `log_event` got the detail; `backend/files/tests/test_router.py`'s assertion of the old text updated.

#### Step 3: Logs routes
- **Status:** todo
- **Depends on:** 1
- **Files:** `backend/logging/router.py`, `backend/logging/tests/test_router.py` (modify).
- **Change:** fixed message on all six 500s, detail logged with `log_event` (`logs_read_error`), as the standard requires for handled errors (import `log_event`).
- **Verification:** tests as in Step 2 for each route.

#### Step 4: Chat routes and streams
- **Status:** todo
- **Depends on:** 1
- **Files:** `backend/chat/router.py`, `backend/chat/handler.py`, `backend/task_manager/executor.py` (modify); `backend/chat/tests/test_router.py`, `backend/chat/tests/test_handler.py`, `backend/task_manager/tests/test_executor.py` (modify).
- **Change:** fixed messages for the history, completions, resume and stop 500s and for the three stream error chunks; detail logged.
- **Verification:** tests: each forced failure sends the fixed text with no exception text; existing tests asserting the old text updated to the new one.

#### Step 5: Retry notices, file run and agents
- **Status:** todo
- **Depends on:** 1
- **Files:** `backend/inference/engine.py`, `backend/tools/implementations/code_executor.py`, `backend/tools/router.py`, `backend/tools/agents/base.py`, `backend/tools/agents/research_agent/agent.py`, `backend/tools/agents/research_agent/constants.py`, `backend/tools/agents/document_agent/agent.py`, `backend/tools/agents/visit_page_agent/agent.py`, `backend/tools/agents/search_web_agent/agent.py` (modify); their tests: `backend/inference/tests/test_engine.py`, `backend/tools/tests/test_code_executor.py` (assertions at the generic and prefixed resolve texts), `backend/tools/tests/test_router.py` (the "Failed to run file" assertions), `backend/tools/agents/tests/test_base.py`, `backend/tools/agents/{research,document,visit_page,search_web,file_system,git}_agent/tests/test_agent.py` (the last two assert `base.py`'s failure text), `frontend/src/features/artifacts/ArtifactPanel.test.tsx` (asserts "Failed to run file") (modify).
- **Change:** the two `__redact__` messages become fixed texts with "…"; `run_file`'s `ValueError` branch returns `Error: <resolver message>` (the resolver's own `ValueError` texts in `resolve_owner_and_physical_path` / `resolve_run_target` are deliberate user messages, not arbitrary exception text) and the generic branch "Error: Could not open that file."; `api_run_file`'s message reworded; agent failure texts as in Approach with the detail in `log_event`, including `backend/tools/browser.py`'s screenshot error and the research search error collected in `_execute_internal_searches`; research "..." texts changed as in Approach, after grepping each constant for comparisons.
- **Verification:** tests: invalid generation and a raised error each send the fixed notice without "..." or exception text; the resolve branches return the new texts; each agent's forced failure yields text without the exception message and logs it; a stored research run with the kept markers still resumes (existing resume tests pass).

#### Step 6: Sweep check
- **Status:** todo
- **Depends on:** 2, 3, 4, 5
- **Files:** none changed; run `grep -rnE "str\(e\)|\{e\}" backend --include=*.py` and `grep -rn "\.\.\." backend --include=*.py` (every three-dot sequence) and review the hits.
- **Change:** confirm every remaining hit is a log line, a prompt or docstring, a model-facing tool text without exception text, or a research marker kept on purpose; record the result in Implementation notes.
- **Verification:** the recorded list has no user-facing hit.

### Tests
- Python: the repo's `venv` lives in the main checkout (`/home/archit-anand/docker-data/shared/Coding/My-AI/venv`); a worktree uses that interpreter.
- Backend: `EMBEDDING_URL="http://mock" AI_URL="http://mock" AI_API_KEY="dummy" PYTHONPATH=. venv/bin/python -m pytest` on `backend/file_system/tests`, `backend/files/tests`, `backend/logging/tests`, `backend/chat/tests`, `backend/task_manager/tests`, `backend/inference/tests`, `backend/tools/tests`, `backend/tools/agents`, then `backend` and `tests`; `venv/bin/ruff check .`.
- Frontend: in `frontend/`, `npm run test` (fixtures or specs that assert server error text, if any, updated).
- Gate: `scripts/check.sh`.

### Risks and open questions
- Frontend tests or recorded fixtures may contain the old texts; Step 4 and the frontend run catch them.
- Decision: wording pass instead of codes (assumption, logged).

### Success criteria
- [ ] Every listed user-facing server message follows the wording rules
- [ ] No raw exception text reaches the screen from the Logs page, a failed file run, uploads, file routes or the chat stream
- [ ] Tests that assert exact messages are updated
- [ ] `docs/standards/api.md` and `docs/standards/errors-and-logging.md` state the rule

### Reviewer brief
- Objective: no raw exception text, internal detail or "..." reaches the person from server routes, streams, retry notices, file runs or agent failures; each site sends a short fixed message saying what happened and what to do, and the detail goes to `log_event`.
- Decisions: wording pass, not error codes; rules added to `errors-and-logging.md`; status codes and body keys unchanged; tool texts keep their leading `Error`/`failed` word for the model; research texts get "…" except constants compared on resume (kept exact so stored runs resume); the resolver's own `ValueError` texts are kept as user messages; a closing grep sweep is recorded.
- Out of scope: compared research markers; model-facing texts without exception text.
- Success: the listed messages follow the rules, no raw exception text on the Logs page, file runs, uploads, file routes, chat stream or agent events, exact-message tests updated, both standards docs state the rule.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- Round 1: validator FAIL. Judged FAIL. Valid BLOCKING, fixed: agent failure texts with exception text were missing (Context, Approach, Step 5); research "..." texts can change where the constant is not compared on resume; logs-route detail now goes to `log_event` as the standard says. Valid MINOR, fixed: the three `run_file` branches and their tests; `tools/router.py` and `files/router.py` fixed texts; venv path; `"success": False` kept; sweep greps both quote styles; full paths.
- Round 2 (diff-scoped): validator PASS. Judged PASS. (A second round-2 report, run by mistake against the unedited text, was disregarded.) Valid MINOR, fixed inline: synthesis markers named as kept; all agent test files and the frontend test named; `browser.py` and the research search error covered; resolver texts explained; sweep greps every "...".

## Implementation notes
### Autopilot run (2026-11-11)
- Mode: automatic (batch-autopilot, item 8/9)
- Branch: bugfix/plain-server-messages  PR base: develop  Starting commit: 32d33f73cd578e1a29080f9a12092caf1c36c073
- Dirty before start: none
- Work files: none yet
- Counters: fix 0/10, review 1/5, re-verify 1
- Last completed stage: 6 ship  Next: none
- Hard blocker: none
- WIP commit: none

### Autopilot decisions (2026-11-11)
- Stage 1: plan already Validated in ticket; reused.
### Baseline (2026-11-11)
- backend + tests: 1660 passed before changes.

### Implementation progress
- [x] Step 1: wording rules in `docs/standards/errors-and-logging.md` (what happened + what to do, no exception text/ids/codes/paths, one `…`, `ValueError` path-rule texts may be shown, model-facing tool results keep a leading Error/failed word, compared markers keep their text); api.md points at it
- [x] Step 2: file_system router (create file/folder, delete folder, save/delete disk file) and files router (upload) send fixed messages, detail to `log_event`; also `create_directory_tool`/`delete_directory_tool` in the manager (their `str(e)` reached the UI through the routes; a `ValueError` path-rule text is kept)
- [x] Step 3: six Logs routes: fixed message, `logs_read_error` event
- [x] Step 4: chat routes (history, completions, resume, stop) and the three stream error chunks (`chat_completions` loop, `_handle_tool_execution`, `TaskExecutor`) send fixed messages, detail logged
- [x] Step 5: retry notices (`Checking the answer again…`, `The model did not respond. Trying again…`); `run_file` resolve branches (`Error: <resolver's own ValueError text>`, `Error: Could not open that file.`); `api_run_file`; agent failure texts (base, browsing, document, visit_page, search_web, research) with detail in `log_event`; `browser_screenshot` error; research status texts `...` -> `…` except `EVENT_SYNTHESIS_START` and the literal 'Synthesizing final report sections...' (compared on resume)
- [x] Step 6: sweep. Remaining `str(e)`/`{e}` hits are log lines (`log_event` payloads) or model-facing tool results (file_system manager read/replace/rename tools, clipboard, tasks tool, regex messages). Those are read by the model, not shown as a screen message, and are left on purpose; one follow-up is suggested below. No remaining three-dot status text.
- Legacy UI check: `static/script.js` matches only the 'Database transaction' redact text, not the reworded notices.
- Deviation: the plan's api_run_file/files-router wording and the `flow_fn` result texts as written; `on_error` of the browsing agent also dropped its exception text (found in the sweep).

### Smoke test (2026-11-11)
- backend + tests 1676 pass; frontend typecheck, lint, 1105 unit tests; ruff clean.
- Stage 5: resolve-review done inline by the author (not via the skill). Follow-up suggested: bring the remaining model-facing tool results that carry exception text (list in the review round) in line with the rule. Also the PATCH rename 500 for workspace files (see the MYAI-102 notes) is unrelated.
PR: https://github.com/archit342000/My-AI/pull/131, branch bugfix/plain-server-messages, base develop

## Verification
### Verification plan (2026-11-11)
**Diff base:** develop tip. Full form (many user-visible texts).

**Environment:** real Flask backend on a temp data dir (port 5322, static auth) with a scripted model stub (port 5323) that answers 500 with a secret-looking message when the user text contains ERRPLEASE; `LLM_RETRY_DELAY=0.1`. Driver `scripts/verify103.py` is HTTP plus creating throwaway files in the temp data dir to force real failures. Never touches backend/data. Teardown: kill both, rm the temp dir, check ports.

| ID | Criterion | Scenario | Type | Files | Expected |
|----|-----------|----------|------|-------|----------|
| M1 | stream error + retry notices | send ERRPLEASE; read every SSE event | failure | engine.py, router.py | retry notices are the fixed texts with the ellipsis character, the final error chunk is the fixed text; no `500`, `boom`, path or `...` anywhere in the stream |
| M2 | Logs page | make `logs/x.json` a directory in the data dir; GET /api/logs/detail?path=x.json | failure | logging/router.py | 500 with the fixed message; no path, no `Is a directory`; the detail is in the events log |
| M3 | failed file run | run-file for a workspace-reserved path in a chat without a workspace | failure | code_executor.py, tools/router.py | the resolver's own plain text (or the 400/404 route texts), never a Python exception string |
| M4 | file routes | create a directory with an invalid path through the route; delete a disk-only file that cannot be deleted | failure | file_system router/manager | fixed messages; no exception text |
| M5 | unchanged behaviour | normal send, file create, logs index still work | regression | | 200s as before |
| R1 | detail logged | the events log holds the detail for M1-M4 | non-functional | | `..._error` events with the exception text |

Scripts: `scripts/stub.mjs`, `scripts/start_backend2.sh`, `scripts/verify103.py`, `scripts/run_all.sh`.
### Results (2026-11-11)
Verified at HEAD 32d33f7 plus uncommitted (files hashed in the run log; 40 files).

Evidence: `~/.claude/tickets/My-AI/MYAI-103-evidence/` (results.txt, backend.log, stub.log, scripts/). Real backend with a scripted model that fails with a secret-looking upstream message; torn down. Two harness fixes along the way (the streamed answer arrives in pieces; the first run also showed the older terminal stream error text 'An internal error occurred during generation.', which was reworded to the common fixed text and tested).

| ID | Status |
|----|--------|
| M1 | PASS (retry notices are 'The model did not respond. Trying again…', the final error is the fixed text, nothing raw in the stream: no 500, no 'boom', no path, no three dots) |
| M2 | PASS (a failing log read: fixed message only, no path or 'Is a directory') |
| M3a, M3b | PASS (reserved path and missing file answered with the routes' plain texts) |
| M4a, M4b | PASS (an invalid folder answers with the path rule's own plain text, no exception text; folder delete unchanged) |
| M5a, M5b | PASS (normal send and the logs index still work) |
| R1 | PASS (inference_stream_retry_error, inference_stream_error, logs_read_error events hold the detail) |
Not exercised live: upload failure, chat history/resume/stop 500s, agent failure texts, screenshot error (unit-tested with forced failures that assert the fixed text and that the exception text is absent).
Regression: backend+tests 1677, frontend 1105 pass.
Verdict: verified (9 PASS, 0 FAIL, 0 BLOCKED), with the live gaps above.

## Review history
### Round 1 - 2026-11-11
Verdict: Request changes (many MAJOR) -> after resolution Approve. Four Haiku reviewers (correctness, requirement coverage, tests, docs/security), 55 findings in total, many duplicates. Fixed:
- Raw exception text still reaching the screen: document-agent event row; PDF export body; PATCH move OSError text; the inference_proxy retry notices (sibling of the backend engine); a browsing-agent text naming Playwright; the Logs page's raw network message (now the server's plain message for server errors, a fixed sentence otherwise); `manager.py` text naming the `replace_fs_text` tool; the plan-invalid notice that showed the validator reason.
- Wrong status text: 'Research continues' before a stop; the stalled-section text; a search-limit stop now says so ('Try again tomorrow') instead of 'start it again'; research README updated.
- ValueError catch too broad: new `PathRuleError(ValueError)` raised only by the path rules; only it is passed through in the folder tools and `run_file`; other ValueErrors get the fixed text and a log entry.
- Detail logging: `log_event` added at the sites that only used `logger.error` (file create, disk save/delete, upload, background turn, research phase crashes); one helper `error_detail(e)` (type: message, cut to 300 chars) used for every new payload; one `USER_STREAM_ERROR` constant (backend/error_handling.py) instead of three literals; engine and tools-router log payloads use the documented format.
- Tests: log_event assertions for the chat routes, executor, document, visit_page, search_web, base agent, upload, file routes; new tests for the base-agent failure, research phase and section failures (including the search limit), the PDF export, the Logs page's two error cases, document status ellipsis; weak absence checks tightened.
- Docs: errors-and-logging.md (PathRuleError, error_detail, tool-result nuance, the compared literal named), security.md cross-link.
Rejected or left on purpose: R-tools-1 older model-facing tool results with `str(e)` in preferences, tasks, clipboard, git, files manager, tavily, research_utils and the file_system AI tools (read by the model, not screen messages; the rule now says so; suggested follow-up); bare 'Error:' prefix on a few agent yields (unchanged behaviour); the two three-dot truncation markers in a diff and an approval prompt (not status texts); stale fixture text in a test.
Resolved inline by the author. Re-verified: live harness 9/9, backend+tests 1699, frontend 1106, inference_proxy 46, ruff clean.

## Log
- 2026-11-11: created (split from MYAI-96 at the user's request)
- 2026-11-11: linked split_from MYAI-96
- 2026-11-11: plan validated, 2 rounds
- 2026-11-11: autopilot started (batch-autopilot)
- 2026-11-11: implemented, smoke tests pass
- 2026-11-11: verify: 9 PASS, 0 FAIL, fix 0/10
- 2026-11-11: review round 1 resolved (see Review history); re-verified
- 2026-11-11: batch-autopilot: shipped, base develop (https://github.com/archit342000/My-AI/pull/131)
