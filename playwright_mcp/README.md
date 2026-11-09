# playwright_mcp
**Role:** A FastMCP-based server providing browser automation tools using Playwright, including session management, stealth navigation, and image extraction.

## 📂 Subdirectories
| Folder | Responsibility |
| :--- | :--- |
| `tests/` | Unit and integration tests for MCP tools, security filters, and HTML processing. |

## 📄 Core Files
| File | Purpose | Key Symbols/Exports |
| :--- | :--- | :--- |
| `server.py` | Main FastMCP server implementation with browser tools. | `visit_page_tool`, `browser_start_session`, `mcp` |
| `entrypoint.sh` | Shell script to start the server (typically in a container). | - |
| `requirements.txt` | Python dependencies for the server. | `playwright`, `FastMCP`, etc. |

## 🧩 Architectural Context
*   **Dependencies:** `playwright`, `playwright-stealth`, `selectolax`, `httpx`, `pypdf`.
*   **Flow:** The server listens for MCP requests (SSE) and executes browser commands. It maintains a global registry of browser sessions to allow persistent interactions.
*   **Security:** Implements SSRF protection by resolving hostnames and blocking private/reserved IP ranges. Uses an `AuthMiddleware` to enforce `X-MCP-API-KEY` on `/sse`, `/messages/` and `/portal/*`; all of them are rejected with 401 when `PLAYWRIGHT_MCP_API_KEY` is not configured (fail closed). The app adds the key to its `/api/tools/portal/init` proxy call. The noVNC display on port 6080 is a separate listener that this check does not cover.
*   **Stealth:** Uses `playwright-stealth` and custom JS injection to scrub CDP leaks and spoof browser fingerprints.

## 🛠️ Usage & Conventions
*   **Session Management:** Sessions are stored in a global `_sessions` dict and automatically cleaned up after 5 minutes of inactivity.
*   **Detail Levels:** `visit_page_tool` supports `basic`, `standard`, and `deep` levels, adjusting noise reduction and scroll depth accordingly.
*   **Testing:** Run tests with `PYTHONPATH=. pytest playwright_mcp/tests/` in the service image (they need `playwright` and `playwright-stealth`, which the main venv does not have; see `docs/pitfalls.md`).

## 🛠️ Key Symbols/Exports
| Symbol | Purpose |
| :--- | :--- |
| `visit_page_tool` | One-shot page visit and markdown extraction. |
| `browser_start_session` | Initializes a persistent browser context for sequential actions. |
| `browser_click` / `browser_type` | Interaction tools for active sessions. |
| `browser_read_page` | Extracts markdown from the current state of a session. |
| `fetch_and_encode_image_tool` | Downloads an image and returns it as a base64 data URI. |
| `is_safe_web_url` | Core security utility for SSRF prevention. |
