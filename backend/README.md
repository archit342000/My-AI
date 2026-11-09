# backend
**Role:** The core engine of the application, containing global configuration, resilience strategies, and foundational shared modules.

## 📂 Subdirectories
| Folder | Responsibility |
| :--- | :--- |
| `auth/` | Identity providers, per-request current user and the user CLI. |
| `chat/` | High-level orchestration and turn management. |
| `database/` | Persistent storage and hybrid caching layer. |
| `file_system/` | Virtualized file artifact management and versioning. |
| `files/` | User-uploaded file processing and content extraction. |
| `inference/` | Unified interface for LLM and embedding APIs. |
| `logging/` | Structured event auditing and performance tracking. |
| `models/` | Model lifecycle management and configuration. |
| `rag/` | Knowledge retrieval and vector store coordination. |
| `task_manager/` | Asynchronous background task execution. |
| `tools/` | Capability definitions and tool implementation registry. |

## 📄 Core Files
| File | Purpose | Key Symbols/Exports |
| :--- | :--- | :--- |
| `config.py` | Central configuration hub (env/secrets/timeouts). | `DATA_DIR`, `AI_URL`, `TIMEOUTS` |
| `error_handling.py` | Resilience patterns (Retry, Jitter, Circuit Breaker). | `CircuitBreaker`, `execute_with_retry` |
| `file_types.py` | Exhaustive registry of supported file and code extensions. | `EXHAUSTIVE_TEXT_EXTENSIONS` |
| `mcp_client.py` | Client for Model Context Protocol (MCP) tool servers. | `MCPClient` |

## 🧪 Testing
| Test File | Scope |
| :--- | :--- |
| `tests/test_config.py` | Global configuration loading, secrets, and environment overrides. |
| `tests/test_error_handling.py` | Error classification, retry logic, and circuit breaker states. |
| `tests/test_mcp_client.py` | Model Context Protocol (MCP) connection and tool execution. |
| `tests/test_file_types.py` | Exhaustive MIME type and extension mapping. |
| `tests/test_prompts.py` | Base system prompt composition through `PromptBuilder`. |

*   **Run Tests:** `EMBEDDING_URL="http://mock" AI_URL="http://mock" AI_API_KEY="dummy" PYTHONPATH=. ./venv/bin/python -m pytest backend/tests/`

## 🧩 Architectural Context
*   **Initialization:** On startup, the system reads `config.py` and initializes core singletons (`db`, `task_manager`, `RAGManager`).
*   **Resilience:** All external calls (to LLM, Search, Browsing) are wrapped in `error_handling` logic to prevent cascading failures.
*   **Extensibility:** The backend uses MCP to dynamically load tools from external servers like Playwright or Tavily.

## 🛠️ Usage & Conventions
*   **Patterns:** 
    - **Global Configuration:** Always use `backend.config` rather than hardcoding values.
    - **Self-Healing:** `validation.py` monitors LLM output for formatting errors (like unclosed tags) and can trigger automatic "splice-fixes" or regeneration.
*   **Security:** Sensitive keys and paths are pulled via `get_secret` to ensure compatibility with Docker Secrets and environment-based deployments.
