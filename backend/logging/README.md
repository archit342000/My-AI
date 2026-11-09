# backend/logging
**Role:** Provides a comprehensive observability system for tracking LLM calls, tool executions, and system events, featuring structured JSON logging and a specialized network index for the UI.

## 📂 Subdirectories
| Folder | Responsibility |
| :--- | :--- |

## 📄 Core Files
| File | Purpose | Key Symbols/Exports |
| :--- | :--- | :--- |
| `__init__.py` | Package entry point and export aggregator. | `log_event`, `log_llm_call`, `log_tool_call` |
| `logger.py` | Core logging logic and structured data persistence. | `log_event`, `log_llm_call`, `log_tool_call`, `log_embedding_call` |
| `router.py` | API endpoints for log retrieval and log UI support. Admin only (a blueprint `before_request`), since the logs and raw database tables hold every user's data. | `logs_bp` |

## 🧩 Architectural Context
*   **Dependencies:**
    - `backend.config`: Configuration for log storage paths (defaulting to `DATA_DIR/logs`).
    - `logging`: Standard Python logging for the `app.log` file and stdout.
*   **Flow:**
    1. **Capture:** Components across the backend call `log_event` or specialized transaction loggers.
    2. **Storage:** Transactions (LLM/Tool calls) are saved as individual JSON files for deep inspection.
    3. **Indexing:** A summary entry is appended to `network_index.jsonl` to facilitate fast lookups in the UI.
    4. **Visualization:** `router.py` serves these logs via API, which are rendered in the project's specialized log viewer.

## 🛠️ Usage & Conventions
*   **Patterns:** 
    - **Structured Logging:** All transactions are logged as JSON to ensure machine-readability and consistent parsing.
    - **High-Performance Tail:** `router.py` uses binary seek-from-end logic to efficiently retrieve the latest application logs without reading the entire file.
    - **Category Isolation:** Logs are separated into `llm_calls`, `tool_calls`, and `general` events to prevent volume-based fragmentation.
*   **Log Storage:** 
    - `llm_calls/`: Contains request payloads and full accumulated responses.
    - `tool_calls/`: Audits external tool usage and embedding requests.
    - `general/`: Daily JSONL files for general system events.
*   **Testing:**
    - **Local:** Unit tests in `tests/` ensure strict compliance with the 1:1 exhaustive testing rule. Tests for `logger.py` verify log generation and formatting into temporary directories. `router.py` tests use the Flask test client to verify endpoint behavior and binary file seeking logic.
    - **Run Command:** `EMBEDDING_URL="http://mock" AI_URL="http://mock" ./venv/bin/python3 -m pytest backend/logging/tests/`
