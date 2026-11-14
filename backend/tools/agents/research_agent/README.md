# Research Agent
**Role:** A high-assurance orchestration agent that executes a deterministic, multi-phase research pipeline: Context Scouting, Strategy Planning, Sequential Section Execution (with self-reflection), and Final Synthesis/Auditing.

## 📂 Subdirectories
| Folder | Responsibility |
| :--- | :--- |
| `tests/` | Comprehensive test suite for the multi-phase state machine, resumption logic, and JSON schema compliance. |

## 📄 Core Files
| File | Purpose | Key Symbols/Exports |
| :--- | :--- | :--- |
| `agent.py` | Orchestration class `ResearchAgent` managing the full research lifecycle. | `ResearchAgent`, `flow_fn` |
| `prompts.py` | 10+ specialized prompt templates for scouting, planning, reflection, triage, and synthesis. | `PLANNER_SYSTEM_PROMPT`, `SCOUT_SYSTEM_PROMPT`, etc. |
| `research_utils.py` | Helpers for structured JSON extraction, citation normalization, and report sanitization. | `_extract_json_from_text`, `_normalize_citations` |
| `schemas.py` | Strict Pydantic-like JSON schemas for all structured LLM output phases. | `SCOUT_JSON_SCHEMA`, `PLAN_GENERATOR_JSON_SCHEMA`, etc. |
| `progress.py` | Pure builder of the structured progress snapshot (`research_progress`: steps with state and duration, counts, phase) from the plan, the stored events and `visited_urls`; the agent stores it as a collection and streams it. | `build_progress` |
| `constants.py` | Database event markers used for thread-safe state reconstruction. | `EVENT_SCOUT_START`, `EVENT_PLAN_APPROVED`, etc. |

## 🧩 Architectural Context
*   **Dependencies:** `backend.database`, `backend.mcp_client.tavily_client`, `backend.file_system.manager`.
*   **State Machine:**
    1.  **Scouting Phase**: Gathers initial broad context on the topic.
    2.  **Planning Phase**: Generates a structured research plan (requires user approval).
    3.  **Execution Phase**: Processes sections **sequentially**. Each section runs its own internal sub-cycle:
        *   *Initial Search* -> *Reflection* (Gaps) -> *Follow-up Search* -> *Triage* (Evidence Selection) -> *Drafting* (Writer) -> *Summarization*.
    4.  **Synthesis Phase**: Merges all section summaries, performs a global audit, and generates the final report in the FileSystem.
*   **Resumption:** The agent is designed to be fully resumable. It reconstructs its current position in the pipeline by scanning DB history for specific `role='event'` markers.

## 🛠️ Usage & Conventions
*   **Daily search limit:** Every search query counts against the chat owner's `RATE_LIMIT_SEARCHES_PER_DAY` (`check_search_limit`, before the query's own error handling). Each query is one hit (a section's initial-search retry runs its queries, and so counts, again). An initial search over the limit raises `SearchLimitReached`: the section is not retried and the research run halts (`Section N failed: Error: Daily web search limit reached. Research halted.`). A follow-up gap search over the limit is skipped (the results of that gap batch are dropped, even queries that ran before the limit) and the section carries on with the results it has.
*   **Persistence:** All intermediate search results and drafts are stored as `collections` linked to the chat.
*   **Verification:** Mechanically verifies LLM output against JSON schemas at every phase.
*   **Sequentiality:** Currently executes sections one by one to ensure context continuity (later sections see summaries of previous ones).
*   **Testing:** Run `PYTHONPATH=. ./venv/bin/python -m pytest backend/tools/agents/research_agent/tests/`.
