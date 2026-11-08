# Architecture

My-AI is a Flask application that orchestrates a local llama.cpp inference server,
a vector store, and isolated MCP tool containers behind a React chat UI (see `docs/frontend.md`).

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, TypeScript, Vite (`frontend/`); legacy vanilla UI kept at `/legacy/` for one release |
| Backend | Python 3.12, Flask |
| Inference | External llama.cpp server (OpenAI-compatible), reached through `inference_proxy` |
| Vector DB | ChromaDB |
| Storage | SQLite |

## Project boundaries

Inference is external. The llama.cpp server lives in a separate repository.

1. This codebase contains no logic for starting, managing, or deploying the inference server.
2. The app only consumes the inference API, via URLs and keys in `secrets/`.
3. Adding inference orchestration (Docker services, model loaders, and so on) here violates the architecture.

## Tool isolation (MCP)

External tools run in separate containers and are reached through the Model Context
Protocol: `tavily_mcp` (search), `playwright_mcp` (browsing/scraping) and
`code_runner_mcp` (the relay to the sandboxed code runner, `code_runner_runtime`). The Flask app is the orchestrator.

## Component map

| Path | Responsibility |
|------|----------------|
| `app.py` | Flask entry point, routes, WebSocket proxying |
| `backend/chat/` | Turn orchestration, prompt assembly, tool handling |
| `backend/tools/` | Tool catalog and agent implementations |
| `backend/database/` | SQLite access layer and caching (`db`) |
| `backend/file_system/` | Virtualized per-chat file system with versioning |
| `backend/files/` | Uploaded-file processing and extraction |
| `backend/inference/` | LLM and embedding API client |
| `backend/models/` | Model lifecycle and configuration |
| `backend/rag/` | Retrieval and vector store coordination |
| `backend/task_manager/` | Background task execution |
| `backend/logging/` | Structured event auditing |
| `backend/config.py` | The only place configuration is read (env and secrets) |
| `inference_proxy/` | Proxy in front of llama.cpp |
| `frontend/` | React SPA (`src/`), built to `frontend/dist/` |
| `static/` | Legacy vanilla UI, served at `/legacy/` (removed in a later release) |

Each component directory has a short `README.md` with its purpose and local constraints.

## Startup and resilience

- On startup the app reads `backend/config.py` and initializes shared singletons
  (`db`, task manager, RAG managers).
- External calls (LLM, search, browsing) go through `backend/error_handling.py`
  (retry, jitter, circuit breaker).
- Secrets are read with `get_secret`, which works with Docker Secrets and environment variables.
