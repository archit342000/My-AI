# backend/tools/agents
**Role:** specialized implementation logic for autonomous sub-agents that run independent inference loops to solve complex tasks.

## 📂 Subdirectories
| Folder | Responsibility |
| :--- | :--- |
| `browsing_agent/` | Coordinates multi-step web interaction and data extraction. |
| `document_agent/` | Specialized in analyzing and summarizing uploaded documents and images. |
| `file_system_agent/` | Manages complex read/write operations across system-like artifacts. |
| `research_agent/` | Performs deep, multi-phase investigation and report generation. |
| `search_web_agent/` | Simplified agent for performing and synthesizing web searches. |
| `visit_page_agent/` | Simplified agent for reading and extracting data from a specific URL. |

## 🧩 Architectural Context
*   **Isolation:** Each agent runs in its own context managed by `AgentHandler`. They typically have their own system prompts and restricted toolsets.
*   **Recursive Handoff:** Agents can call other tools (and sometimes other agents) to fulfill their primary instruction.
*   **Streaming:** All agent activity is streamed back to the `ChatHandler` using a standardized format to ensure UI consistency.

## 🛠️ Usage & Conventions
*   **Handoff Pattern:** The main assistant delegates to these agents via the `ToolHandler`.
*   **Helper runs:** `ToolHandler` announces each run (`agent_run` stream chunk: start, activity, end with the duration; finished runs stored as the `agent_runs` collection). Runs are sequential and may nest (research calls the search helper); no helpers run in parallel.
*   **Persistence:** Agent messages are stored in the `sub_agent_messages` table and are anchored to the tool call that spawned them. Additionally, all agents emit `role="event"` messages (`Started`, `Completed`, `Failed`) to ensure consistent UI activity tracking and crash recovery.
*   **Testing:**
    - **Local:** Unit tests in each agent's `tests/` subdirectory ensure strict compliance with the exhaustive 1:1 testing rule.
    - **Run Command:** `EMBEDDING_URL="http://mock" AI_URL="http://mock" ./venv/bin/python3 -m pytest backend/tools/agents/*/tests/`
