# Search Web Agent
**Role:** A specialized agent that executes web searches via Tavily and synthesizes findings into concise, context-aware summaries.

## 📂 Subdirectories
| Folder | Responsibility |
| :--- | :--- |
| `tests/` | Comprehensive unit tests for search execution, retry logic, and synthesis. |

## 📄 Core Files
| File | Purpose | Key Symbols/Exports |
| :--- | :--- | :--- |
| `agent.py` | Orchestration logic for searching, retrying, and synthesizing results; reports each result page on `agent.sources`. | `flow_fn` |
| `prompts.py` | System prompt for the synthesis phase. | `SEARCH_AGENT_SYSTEM_PROMPT` |

## 🧩 Architectural Context
*   **Dependencies:** `backend.mcp_client.tavily_client`, `backend.database.db`.
*   **Flow:** 
    1.  **Search**: Calls `async_tavily_search_tool` via MCP.
    2.  **Optimization**: If `depth="normal"`, it returns the native Tavily answer or formatted snippets directly to save time/cost.
    3.  **Synthesis**: If `depth="advanced"`, it uses an LLM to extract specific information defined in the `context` parameter.
*   **Resumption**: This agent is typically used as a one-shot tool within a larger flow and does not maintain internal state between turns, though it logs results to the DB.

## 🛠️ Usage & Conventions
*   **Daily limit**: Each search counts once (not per retry) against the chat owner's `RATE_LIMIT_SEARCHES_PER_DAY` through `check_search_limit`; over it the agent returns `Error: Daily web search limit reached.` without calling Tavily.
*   **Retries**: Implements a 3-attempt retry loop for Tavily API failures with exponential backoff.
*   **Depth Control**: Supports `normal` (fast, snippet-based) and `advanced` (comprehensive, LLM-synthesized) search depths.
*   **Search Filters**: Supports `topic="news"` and `time_range` (e.g., `day`, `week`, `month`, `year`) for targeted searching.
*   **Synthesis Fallback**: If LLM synthesis fails, the agent yields a descriptive error message but ensures the session remains stable.
*   **Testing**: Run `PYTHONPATH=. ./venv/bin/python -m pytest backend/tools/agents/search_web_agent/tests/`.
