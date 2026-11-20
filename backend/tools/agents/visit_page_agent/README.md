# Visit Page Agent
**Role:** A specialized agent that scrapes webpage content via Playwright and synthesizes specific answers based on the extracted text.

## 📂 Subdirectories
| Folder | Responsibility |
| :--- | :--- |
| `tests/` | Unit tests for scraping, synthesis logic, and error handling. |

## 📄 Core Files
| File | Purpose | Key Symbols/Exports |
| :--- | :--- | :--- |
| `agent.py` | Orchestration logic for scraping and LLM-based synthesis; reports the page it read on `agent.sources`. | `flow_fn` |
| `prompts.py` | System prompt for the precising reading phase. | `VISIT_PAGE_SYSTEM_PROMPT` |

## 🧩 Architectural Context
*   **Dependencies:** `backend.mcp_client.playwright_client`, `backend.database.db`.
*   **Flow:** 
    1.  **Scrape**: Calls `visit_page_tool` via MCP to get text/markdown from a URL.
    2.  **Raw Mode**: If no `query` is provided, the agent returns the raw extracted content directly.
    3.  **Synthesis Mode**: If a `query` is provided, it uses an LLM to answer the query based strictly on the extracted text.
*   **Resumption**: One-shot utility, does not maintain state across turns.

## 🛠️ Usage & Conventions
*   **Precision Reading**: The agent is instructed to state if information is missing rather than hallucinate based on internal knowledge.
*   **Detail Levels**: Supports `standard` and other detail levels supported by the underlying scraping tool.
*   **Testing**: Run `PYTHONPATH=. ./venv/bin/python -m pytest backend/tools/agents/visit_page_agent/tests/`.
