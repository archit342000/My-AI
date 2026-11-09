# tavily_mcp
**Role:** A FastMCP-based server providing web search and site mapping capabilities using the Tavily API.

## 📂 Subdirectories
| Folder | Responsibility |
| :--- | :--- |
| `tests/` | Unit and integration tests for Tavily tools, search caching, and authentication middleware. |

## 📄 Core Files
| File | Purpose | Key Symbols/Exports |
| :--- | :--- | :--- |
| `server.py` | Main FastMCP server implementation with Tavily search tools. | `search_web`, `audit_search`, `mcp` |
| `requirements.txt` | Python dependencies for the server. | `httpx`, `FastMCP`, etc. |

## 🧩 Architectural Context
*   **Dependencies:** `httpx`, `FastMCP`.
*   **Flow:** The server acts as a proxy for the Tavily API. It implements a local cache (`_tavily_search_cache`) to store raw search results, allowing agents to "audit" their previous search for more detail without re-triggering API calls.
*   **Security:** Enforces `X-MCP-API-KEY` via `AuthMiddleware` on `/sse` and `/messages/`; the routes are rejected with 401 when the key is wrong or missing, and also when `MCP_API_KEY` itself is not configured (fail closed). Sanitizes search outputs to prevent prompt injection or script execution in the host environment.
*   **Parameter Support:** Supports granular search parameters including `topic` (general, news, finance) and `time_range` (day, week, month, year) for freshness.

## 🛠️ Usage & Conventions
*   **Audit Logic:** When `search_web` is called with a `chat_id`, the raw content is cached for 1 hour. Use `audit_search` with the same `chat_id` to retrieve it.
*   **Topic Filtering:** Use `topic="news"` for current events to ensure Tavily uses its optimized news index.
*   **Testing:** Run tests with `PYTHONPATH=. pytest tavily_mcp/tests/`.

## 🛠️ Key Symbols/Exports
| Symbol | Purpose |
| :--- | :--- |
| `search_web` | Primary tool for web searching with AI summaries and image results. |
| `audit_search` | Retrieves raw content from the most recent search in a chat context. |
| `async_tavily_search_tool` | Optimized search tool for background research tasks with customizable depth. |
| `async_tavily_map_tool` | Generates a site map for a given URL to discover deep content paths. |
| `AuthMiddleware` | Starlette middleware ensuring all SSE requests are authenticated. |
