---
id: MYAI-71
title: "Research mode UI in React: investigate, then plan"
status: done
epic: MYAI-53
created: 2026-11-10
updated: 2026-11-10
links:
  split_from: [MYAI-70]
  split_into: [MYAI-92]
  relates_to: [MYAI-62]
---

## Description
Spike. The legacy UI has a research-mode experience that the React UI lacks or only half supports: the Regular/Deep depth choice, the rule that research mode turns the file-system and browsing toggles off, persona-locked modes, the research plan shown in the files panel with Approve and Suggest-edit, per-agent activity renderers (`static/js/agent-renderers.js`), the completed/ongoing research states, discard, and the model-switch overlay while a model loads. None of it could be exercised in the MYAI-52 audit (it needs the research, search and browser services), and parts of the legacy code call endpoints that may no longer exist. This ticket establishes, by reading and by running, what exists on the server today and what the React UI must do, and ends with child tickets and plans, not with a port.

Findings (MYAI-52, Verification): A-58 (research plan and progress UI, model-switch overlay), A-62 (research depth).

## Acceptance criteria
- [x] A written map of the research-mode flow: each legacy UI element, the request or stream event behind it, and whether the server still supports it (endpoint and code reference)
- [x] The same flow run end to end once on a throwaway instance with the real services, in the legacy UI and in the React UI, with the differences listed
- [ ] A decision list for the user: port, drop or defer each element
- [ ] Follow-up tickets created (after the user agrees) with a plan each

## Plan
**Date:** 2026-11-10  **Status:** Validated

### Objective
Find out, by reading the code and by one real run, what the research-mode experience requires of the React UI today, and turn that into decisions and planned follow-up tickets. This spike writes no product code.

### Context
- **Requirement:** this ticket's Description and Acceptance criteria (findings A-58 and the research-depth part of A-62 in MYAI-52).
- **Rules:** `AGENTS.md` (stop and ask before contradicting a documented rule; inference is external), `docs/standards/testing.md` (never touch `backend/data`; use a throwaway data directory), `docs/tools.md` (tools and MCP services), the ticket rules (follow-up tickets are created only after the user agrees).
- **What is known (read during the audit, not yet verified end to end):**
  - Legacy UI pieces: the deep-research toggle (`static/index.html` `#deep-research-toggle`) and a Regular/Deep selector that is commented out in the markup (`#research-mode-selector`, "for future implementation"); `updateResearchUI` in `static/script.js` (research mode switches the file-system and browsing toggles off, persona flags lock modes, a running research blocks the toggle); the research plan opened in the files panel with Approve and Suggest-edit (`#file-system-panel-approve-btn`, `#file-system-plan-edit-area`; the Approve handler posts `type: 'approved'` to `/api/tools/clarification/response` after reading `/api/chats/<id>/agent/callback/latest`); `approvedPlanPayload` in `sendMessage`; per-agent renderers in `static/js/agent-renderers.js`; `research_state` and `research_completed` on the chat (`had_research` exists only in the backend); `POST /api/chats/<id>/discard`; the model-switch overlay in `static/js/model-manager.js` `loadModel`.
  - Server: `backend/chat/router.py` has `discard` and refuses a model change on a research chat; `backend/chat/handler.py` `get_history` returns `research_state`; `backend/tools/catalog/research.py` and `backend/tools/agents/` hold the research tool and agents. No route named `agent/callback/latest` was seen in `backend/chat/router.py`.
  - React today: a Research Agent toggle in `features/tools/ToolsMenu.tsx` and `researchMode` in the completion body (`api/completions.ts`); nothing else.
- **What is not known:** which legacy calls still exist on the server; how the plan approval reaches the planner now; what events a research turn streams; which services a research turn needs.

### Approach
- **Read first.** Trace each legacy UI element to its request or stream event, then to the server code that answers it, and record whether it still exists. The result is a table in this ticket (element, legacy code, request or event, server code, state: works / broken in legacy / gone).
- **Then run once.** On a throwaway instance (the MYAI-52 rig's `up.sh` pattern, a temporary `DATA_DIR`, static auth), with the real model proxy and the search, browser and code services the trace shows are needed, run one short research turn in the legacy UI and the same in the React UI, capturing the stream (`/v1/chat/completions` body), the stored messages and screenshots. Nothing is run against the live app's data. The user is asked before the shared model server is used.
- **Then decide.** For each element propose port, drop or defer with a size estimate, and list the open product questions (for example whether Deep mode is still wanted).
- **Then hand over.** Present the decision list; after the user answers, create the follow-up tickets in this epic and plan each with the plan skill.
- **Rejected:** planning the port now from the legacy code alone (parts of it call endpoints that may be gone, and none of it could be run in the audit).

### Out of scope
- Writing or changing product code.
- Clarification prompts for ordinary turns (MYAI-62) and the thought-box timeline (MYAI-55), which the research UI will build on.

### Steps
#### Step 1: Trace the legacy research UI
- **Status:** todo
- **Depends on:** none
- **Files:** read only: `static/script.js`, `static/js/agent-renderers.js`, `static/js/model-manager.js`, `static/js/file-system-ui.js`, `static/index.html`; this ticket (`## Implementation notes`)
- **Change:** list every research-mode UI element with the function that drives it and the request or stream field it depends on.
- **Verification:** the table has a row for each item named in the ticket Description (depth choice, mode exclusions, persona locks, plan approve and suggest-edit, agent renderers, research states, discard, model-switch overlay), each with a file and function reference.

#### Step 2: Trace the server side
- **Status:** todo
- **Depends on:** 1
- **Files:** read only: `backend/chat/router.py`, `backend/chat/handler.py`, `backend/tools/router.py`, `backend/tools/callbacks.py`, `backend/tools/catalog/research.py`, `backend/tools/agents/`, `docs/tools.md`, `docs/architecture.md`, `docs/pitfalls.md` (it records undefined names in `backend/tools/agents/research_agent/agent.py` and `research_utils.py`); this ticket
- **Change:** for each row add the route or code that serves it today, or "not found" with the search that showed it.
- **Verification:** every row has a server reference or a "not found" with the grep used; the list of external services a research turn needs is written down.

#### Step 3: One real run in both UIs
- **Status:** todo
- **Depends on:** 2
- **Files:** `~/.claude/tickets/My-AI/MYAI-71-evidence/` (create: stream capture, stored messages, screenshots, the commands used)
- **Change:** as in Approach ("Then run once"). If a needed service cannot be reached from a throwaway instance, record which one and stop this step there.
- **Verification:** the evidence folder holds the captured stream and the chat detail of one research turn per UI, or a written reason why the run was not possible; the trace table gains an "observed" column.

#### Step 4: Decision list
- **Status:** todo
- **Depends on:** 3
- **Files:** this ticket (`## Implementation notes`)
- **Change:** as in Approach ("Then decide").
- **Verification:** each row carries a proposal (port, drop, defer), a rough size (S, M, L) and any question for the user; the list is shown to the user.

#### Step 5: Follow-up tickets and plans
- **Status:** todo
- **Depends on:** 4
- **Files:** `~/.claude/tickets/My-AI/` (new tickets in epic MYAI-53, created after the user agrees)
- **Change:** create the agreed tickets and plan each with the plan skill; link them `split_from` this ticket.
- **Verification:** every "port" row maps to a ticket with a validated plan; "drop" rows are recorded in `docs/frontend.md` by the ticket that implements the neighbouring feature; this ticket lists the created ids.

### Tests
None: the spike changes no code. Its outputs are the trace table, the evidence folder and the decision list. The run in Step 3 is a manual spike run, not a test.

### Risks and open questions
- **The real run needs the shared model server and external services;** it is done once, on a throwaway data directory, and only after the user agrees to use the model server.
- **The legacy research flow may itself be partly broken;** the trace marks such rows so they are not ported as they are.
- **Size:** the port is expected to become several tickets; this spike does not commit to their scope.

### Success criteria
- [ ] Trace table: each legacy research element with its request or event and current server support
- [ ] One research turn run end to end in both UIs on a throwaway instance (or the blocking reason recorded), with evidence
- [ ] Decision list presented to the user
- [ ] Follow-up tickets created and planned after the user agrees
### Reviewer brief
- **Objective:** establish what research mode needs from the React UI today and turn it into decisions and planned follow-up tickets; no product code.
- **Decisions:** read the legacy UI and the server first and record a trace table; then one real research turn in both UIs on a throwaway data directory, only after the user agrees to use the shared model server; then a port/drop/defer list; follow-up tickets are created and planned only after the user answers.
- **Out of scope:** product code, clarification prompts (MYAI-62), the thought-box timeline (MYAI-55).
- **Success criteria:** trace table with server support per element; one end-to-end run per UI with evidence, or the blocking reason; decision list presented; follow-up tickets planned after agreement.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- **Round 1:** validator PASS (4 minor). Judged PASS after checking `static/index.html` and `docs/pitfalls.md`. Fixed inline: the Regular/Deep selector is commented out in legacy; `had_research` is backend-only; `docs/pitfalls.md` added to the reading list (known undefined names in the research agent); the run is named a manual spike run.

## Implementation notes
Read-only trace done 2026-11-10 (Steps 1, 2, 4). No product code, so no branch or PR. Steps 3 and 5 are NOT done: both need the user (shared model server use; agreement before follow-up tickets).

### Trace table (legacy element -> request/event -> server today)
| Element | Legacy code | Request / event | Server today | State |
|---|---|---|---|---|
| Research Agent toggle | index.html `#deep-research-toggle`, script.js:138 | sets `researchMode` in completion body; `research_mode` on chat create/update | chat/router.py:101,148,218; handler.py:115,310 | works; React has the toggle (ToolsMenu, settings-store) |
| Regular/Deep depth | index.html:324 `#research-mode-selector` | none | none | commented out in legacy ("future implementation"): nothing to port |
| Mode exclusions | script.js:1975 `updateResearchUI` | local state: research on forces file-system and browsing off, closes the files panel | none (client rule) | legacy only; React: check ToolsMenu for the rule |
| Persona locks | script.js:1979-1986 | persona `research_mode`/`file_system_mode`/`browsing_mode` flags | persona fields exist (PersonasDialog.tsx knows research) | legacy only for the lock behaviour |
| Plan in files panel + Approve | script.js:4495-4560 | GET `/api/chats/<id>/agent/callback/latest`, POST `/api/tools/clarification/response` `{callback_id, chat_id, type:'approved'}`, then `sendMessage(null,{approvedPlan:true})` | `callback/latest` NOT FOUND (grep `agent/callback|callback/latest` in backend, inference_proxy, docs: no hits); `clarification/response` exists (tools/router.py:65); `GET /api/tools/active/<chat>` lists pending callback ids (tools/router.py:14) and script.js:657 uses it | legacy Approve broken at step 1; the working path is `tools/active` + `clarification/response` |
| Suggest edit | script.js:4381 button, :4577 submit; index.html:1617 `#file-system-plan-edit-area` | POST `/api/tools/clarification/response` `{callback_id, chat_id, type:'edit', content}`; callback id found from the chat's tool call with status `awaiting_response` | same endpoint as Approve (tools/router.py:65), no separate route needed | legacy path looks workable; unverified live (needs a running research turn) |
| Agent renderers | static/js/agent-renderers.js (`appendSubAgentActivity`, `getSharedAgentCard`, `renderTaskListCard`) | sub-agent messages (`parent_type` sub-agent) and stream events | stored with `parent_id`/`parent_type`; React keeps sub-agent steps but does not draw them yet | partly covered by the thought-box work (MYAI-55/54) |
| Research states | script.js:715-716, 3091 | `research_state` (none/ongoing/failed) and `research_completed` on chat detail and stream | handler.py:71-86 returns state; router.py:156,214 sets completed; `had_research` is DB-only | server works; React ignores |
| Discard | legacy button | POST `/api/chats/<id>/discard` | chat/router.py:746 (stops task, deletes state files, RAG, file systems, clears messages) | works; React has no UI |
| Model-switch overlay | model-manager.js:315 `loadModel` | POST `/api/models/load` | inference_proxy/router.py:46 (proxy, mounted under models) | works; React has no overlay; chat router refuses a model change on a research chat (router.py:196) |

External services a research turn needs: model proxy, search (Tavily MCP), browser and code runner MCP per docs/tools.md.
Known server defects: `backend/tools/agents/research_agent/agent.py` uses undefined names and `research_utils.py` calls an undefined `_get_sampling_params` (docs/pitfalls.md:72), so a research turn may fail at runtime before any UI matters.

### Decision list (proposal, for the user)
| Element | Proposal | Size | Question |
|---|---|---|---|
| Depth Regular/Deep | drop (user: leave it commented out, 2026-11-10) | - | decided |
| Mode exclusions + persona locks | port | S | none |
| Plan Approve (via `tools/active` + `clarification/response`) | port, after the research agent runs again | M | fix the undefined names first (backend ticket) |
| Suggest edit | port together with Approve (same endpoint, same dependency on a working research turn) | M | user to confirm: port together, or defer both until the research agent runs again |
| Agent renderers | defer to the thought-box work | M | |
| Research states + discard | port | M | |
| Model-switch overlay | port | S | |
| Research agent server defects | new backend ticket | M | must come first |

### Step 3 results: one research turn in each UI (2026-11-10)
Evidence: `~/.claude/tickets/My-AI/MYAI-71-evidence/` (scripts/, shots/ with `*-stream.txt`, `*-chat.json`, screenshots; legacy-backend.log). Throwaway backends (React :7101, legacy :7102) on a copy of the audit data, against the real inference proxy, Tavily and Playwright MCP containers. Question: "Research: what is the capital of Australia? Keep the research minimal." Model: Nemotron-3-Nano-30B.
- **Both UIs got the same result: the research agent failed at its first step.** Stream events: "Starting research topic analysis...", three "scout_analysis inference failed. Retrying" lines, then "Scout phase failed: Failed to extract valid JSON for scout_analysis". Cause (docker logs): llama-server answers 400 to the scout call, `common_sampler_init: error initializing grammar sampler` / `Failed to initialize samplers`. The tool then reports "Agent 'research' completed execution successfully" and the main model answers "Canberra" itself. No plan was produced, so Approve, Suggest edit and the plan panel could not be exercised in either UI.
- This is a server/model problem, not a UI one: the agent's structured-output grammar is rejected by the current llama-server/model. The undefined names in docs/pitfalls.md:72 were not reached.
- **Differences seen (React on a develop-based build vs legacy):** legacy shows a "Research" badge on the chat title and in the sidebar list, React shows none; legacy shows the final answer, React showed only the Thought Process header and an empty reply row (the stored chat has four rows: user, empty assistant, tool, assistant "Canberra"; the one-row-per-turn change in PR #101 targets this, not verified for research); progress event lines were in the stream for both.
- Not observed in either UI: plan panel, Approve, Suggest edit, per-agent renderers, research states other than none, discard, model-switch overlay.

### Not done
- Step 3 done 2026-11-10 (user approved): see Step 3 results below.
- Step 5 (follow-up tickets): not created; the user decided to defer Approve and Suggest edit until the research agent works again, and no tickets were agreed yet.
- Step 5 (follow-up tickets): created only after the user answers the decision list.

## Verification

## Review history

## Log
- 2026-11-10: created (split from MYAI-70)
- 2026-11-10: added to epic MYAI-53
- 2026-11-10: plan validated, 1 rounds
- 2026-11-10 batch-autopilot: partly done (trace and decision list written; live run and follow-up tickets wait for the user); no code, no PR
- 2026-11-10: user decisions: depth selector stays commented out (drop); live run on the model server approved; Suggest edit row corrected (it uses the same endpoint as Approve)
- 2026-11-10: live research run done in both UIs (agent fails at scout step on a llama-server grammar error); Approve and Suggest edit deferred by the user until the research agent works; no follow-up tickets created
- 2026-11-10: linked split_into MYAI-92 (findings of the spike moved to a follow-up ticket)
- 2026-11-10: closed by the user. Map, live run and partial decisions done; criteria 3 (rest of the decision list) and 4 (follow-up tickets with a plan) carried over to MYAI-92
