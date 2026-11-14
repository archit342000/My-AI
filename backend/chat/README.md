# backend/chat
**Role:** Manages the high-level orchestration of chat sessions, including message handling, tool execution, and sub-agent coordination.

## 📂 Subdirectories
| Folder | Responsibility |
| :--- | :--- |

## 📄 Core Files
| File | Purpose | Key Symbols/Exports |
| :--- | :--- | :--- |
| `__init__.py` | Package entry point and export aggregator. | `ChatHandler`, `TurnHandler`, `AgentHandler`, `ToolHandler`, `chat_bp`, `personas_bp` |
| `agent_handler.py` | Orchestrates sub-agents with isolated contexts; `sources` collects the web pages an agent run used. | `AgentHandler` |
| `handler.py` | Core chat flow logic and background task management. | `ChatHandler`, `THINKING_PROFILES` |
| `sources.py` | Per-chat numbered sources (`SourceRegistry`, `[[n]]` markers, the `Sources:` block shown to the model). | `SourceRegistry`, `format_sources_block` |
| `message_edit.py` | Merges an edited user message back into its stored content, keeping images and the attachment note. | `merge_edited_user_content` |
| `router.py` | Flask API endpoints for chat management, completions, and persona CRUD. | `chat_bp`, `openai_bp`, `personas_bp` |
| `tool_handler.py` | Dispatches and executes tool calls (pure or agent-based); numbers web pages and file reads as sources and shows the numbers with the result. | `ToolHandler` |
| `turn_handler.py` | Serializes turns and ensures state persistence; stores and sends the sources an answer cited (`sources=` registry). | `TurnHandler` |
| `validators.py` | Enforces clipboard-first checks and parses LLM confirmations. | `validate_fs_agent_instruction`, `parse_confirmation_response` |

## 🧩 Architectural Context
*   **Dependencies:**
    - `backend.database`: Persistent storage for messages, chats, and workspaces.
    - `backend.inference`: LLM interaction and streaming.
    - `backend.task_manager`: Asynchronous execution of chat turns.
    - `backend.tools`: Tool definitions and implementation registry.
    - `backend.logging`: Standardized event logging and tracking.
*   **Flow:**
    1. **Request:** `router.py` receives a chat request (e.g., via `openai_bp`). Every chat route checks the owner first (`backend/auth/ownership.py`: another user's chat is a 404 and nothing is written), and `chat_completions` creates the chat for the caller. `chat_completions` and `resume_chat` then claim the chat's turn slot (`task_manager.claim_turn`) and return 400 if a turn is already in progress (`docs/standards/api.md`).
    1b. **Turn limit:** `chat_completions` and `resume_chat` count one turn per user against `backend.auth.rate_limit.turn_limiter` after the git-mode check and before any claim or write; over the limit is `429` with `Retry-After`.
    2. **Orchestration:** `ChatHandler` initiates a background task.
    3. **Execution:** `TurnHandler` wraps the turn logic, ensuring serial execution.
    4. **Inference & Tools:** `ChatHandler` streams from `InferenceEngine`. If tool calls are detected, `ToolHandler` executes them, potentially delegating to `AgentHandler` for sub-agent flows.
    5. **Streaming:** Chunks are delivered to the client via a response cache and SSE.
    6. **Edits:** `PUT /api/chats/<id>/messages/<id>` edits user messages only (403 otherwise) and merges the new text into the stored content with `merge_edited_user_content`, so images and the attachment note survive; the client then regenerates with `POST /api/chats/<id>/resume`.

## 🛠️ Usage & Conventions
*   **Patterns:** 
    - **Delegation:** `ChatHandler` acts as a facade, delegating specific responsibilities to `ToolHandler` and `AgentHandler`.
    - **Serial Execution:** `TurnHandler` prevents race conditions by ensuring only one assistant turn runs at a time for a given chat.
    - **Anchoring:** Messages are "woven" together using parent IDs to maintain strict hierarchy (especially for sub-agents).
*   **Stop and delete:** `POST /<id>/stop` waits for the turn's worker to exit before rolling back and answers `stopped: true|false`. `DELETE /<id>` and `DELETE /` (clear all) stop the caller's running turns first and answer `409` without deleting when one has not ended within `TASK_STOP_WAIT_SECONDS` (contract in `docs/standards/api.md`).
*   **Testing:** 
    - **Local:** Specialized unit tests are located in `tests/` within this directory.
      - **Run Command:** `EMBEDDING_URL="http://mock" AI_URL="http://mock" ./venv/bin/python3 -m pytest backend/chat/tests/`
    - **Integration:** See project-level `tests/` directory for full system integration tests.
