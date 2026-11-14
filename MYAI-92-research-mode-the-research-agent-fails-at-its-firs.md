---
id: MYAI-92
title: "Research mode: the research agent fails at its first step, plus UI findings from the spike"
status: todo
created: 2026-11-10
updated: 2026-11-10
links:
  split_from: [MYAI-71]
---

## Description
Follow-up from the research-mode spike (MYAI-71). A real research turn was run once in the legacy and the React UI; both failed at the research agent's first step, so the plan panel, Approve and Suggest edit could not be exercised. This ticket collects every finding so the work can be planned.

### Finding 1: the research agent fails at its first step (server/model, blocks everything else)
- Run: "Research: what is the capital of Australia? Keep the research minimal.", model Nemotron-3-Nano-30B, on a throwaway backend against the real inference proxy, Tavily and Playwright MCP containers.
- Stream: "Starting research topic analysis...", three "scout_analysis inference failed. Retrying (n/4)", then "Scout phase failed: Failed to extract valid JSON for scout_analysis". The tool still reports "Agent 'research' completed execution successfully" and the main model answers by itself.
- Cause (docker logs): llama-server answers 400 to the scout call: `common_sampler_init: error initializing grammar sampler` / `Failed to initialize samplers`. The agent's structured-output request (grammar or JSON schema) is rejected by the current llama-server and model. The proxy relays it as `Client error '400 Bad Request' for url 'http://host.docker.internal:8080/v1/chat/completions'`.
- Open: which request field carries the grammar (look at `backend/tools/agents/research_agent/` scout call and `research_utils.py`), whether other models accept it, and whether the agent should fall back instead of reporting success.
- Separate known defect not reached by the run: `docs/pitfalls.md` line 72 lists undefined names in `research_agent/agent.py` (`MANAGE_TASK_LIST_TOOL`, `READ_FS_FILE_TOOL`, `REPLACE_FS_TEXT_TOOL`, `REPLACE_FS_LINES_TOOL`) and an undefined `_get_sampling_params` in `research_utils.py`. `_get_sampling_params` is called at `research_utils.py` lines 257 and 367.
- A failed agent reports success to the model and the user: the tool result should say it failed.

### Finding 2: legacy Approve calls a route that no longer exists
- `static/script.js` ~line 4495 (Approve handler) reads `GET /api/chats/<id>/agent/callback/latest`. No such route exists (grep of backend, inference_proxy and docs finds nothing), so Approve alerts "No active research session found to approve."
- The working path: `GET /api/tools/active/<chat_id>` (`backend/tools/router.py:14`) lists pending callback ids, and `POST /api/tools/clarification/response` (`backend/tools/router.py:65`) resolves them. Suggest edit (`static/script.js` ~4577) already uses that endpoint with `type: "edit"` and finds the callback from the chat's tool call with status `awaiting_response`.

### Finding 3: differences seen in the React UI (develop-based build, one research turn)
- No "Research" badge on the chat title or in the sidebar list (legacy shows both).
- The final answer was not shown: only the Thought Process header and an empty reply row. The stored chat has four rows: user, empty assistant, tool, assistant "The capital of Australia is Canberra." PR #101 (one assistant row per turn) targets this shape; not verified for research.
- Progress event lines ("Starting research topic analysis...", retries, failure) were in the stream in both UIs.

### Finding 4: legacy research-mode behaviour the React UI lacks (read from code, not exercised)
- Research on forces File System and Browsing off and closes the files panel (`static/script.js` `updateResearchUI`, ~line 1975); persona flags (`research_mode`, `file_system_mode`, `browsing_mode`) lock modes.
- Plan opens in the files panel with Approve and Suggest Changes (`static/index.html` ~1579 and ~1617).
- Per-agent activity renderers: `static/js/agent-renderers.js` (`appendSubAgentActivity`, `getSharedAgentCard`, `renderTaskListCard`).
- `research_state` (none, ongoing, failed) and `research_completed` on the chat (`backend/chat/handler.py` 71-86); React ignores them.
- Discard: `POST /api/chats/<id>/discard` (`backend/chat/router.py:746`); React has no UI.
- Model-switch overlay while a model loads: `static/js/model-manager.js` `loadModel` (`POST /api/models/load`); React has none. The chat router refuses a model change on a research chat (`router.py` ~196).
- The Regular/Deep depth selector is commented out in the legacy markup; decided to leave it out.

### Decisions already made (2026-11-10)
- Depth selector: stays out.
- Approve and Suggest edit: deferred until the research agent runs again; port them together (same endpoint, same dependency).
- Not decided: mode exclusions and persona locks (proposed port, S), research states and discard (port, M), model-switch overlay (port, S), agent renderers (defer to the thought-box work).

Evidence: `~/.claude/tickets/My-AI/MYAI-71-evidence/` (stream captures, stored chats, screenshots, backend log, scripts `up.sh` and `research-run.mjs`).

## Acceptance criteria
- [ ] A research turn against the current llama-server and model completes the scout step (or fails visibly: the tool result and the UI say it failed, not "completed successfully")
- [ ] The undefined names listed in `docs/pitfalls.md` are fixed or confirmed unreachable, with a test each
- [ ] A research turn produces a plan, so Approve and Suggest edit can be run end to end in the legacy and the React UI
- [ ] The React UI shows the final answer of a research turn and a Research badge, or each is recorded as a decision
- [ ] Mode exclusions, persona locks, research states, discard and the model-switch overlay each have a port, drop or defer decision, with a plan for each port

## Plan

## Implementation notes

## Verification

## Review history

## Log
- 2026-11-10: created from the findings of MYAI-71 (split from it)
