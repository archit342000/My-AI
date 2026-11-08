# Errors and logging

## Errors

- Raise specific exceptions (`ValueError`, `CircuitOpenError`, a project exception); avoid bare `Exception` in new code.
- Catch only what you can handle at that layer. Otherwise log with context and re-raise. Never `except: pass`, and never return
  `None` or `[]` to hide a failure.
- External calls (LLM, embeddings, search, browsing) use `backend/error_handling.py`: retries with jitter and a circuit breaker.
  Callers must handle `CircuitOpenError`.
- Routes convert failures into the error body and status codes in `docs/standards/api.md`. Streams send `data: {"error": ...}` and end.
- Tools return text beginning `Error`/`Failed` for expected failures so the agent can recover (`docs/tools.md`).
- User-facing messages are short and actionable. Internal detail goes to logs.

## Logging

Use `backend/logging` only; no `print()` outside `scripts/` CLIs.

| Function | Use for | Written to |
|----------|---------|------------|
| `log_event(event_type, data)` | System events, state changes, handled errors | `logs/general/<date>_events.jsonl` |
| `log_llm_call(...)` | Every LLM request and full response | `logs/llm_calls/` + `network_index.jsonl` |
| `log_tool_call(...)` | Every tool dispatch and result | `logs/tool_calls/` + `network_index.jsonl` |
| `log_embedding_call(...)` | Embedding requests | `logs/tool_calls/` |
| `logging.getLogger(__name__)` | Diagnostics for developers | `logs/app.log` and stdout |

Conventions:

- `event_type` is `snake_case`, shaped `<component>_<event>` (`turn_handler_start`, `rag_collection_dropped`). Errors end in `_error`.
- `data` is a flat, JSON-serializable dict with ids (`chat_id`, `message_id`) and an `error` string where relevant.
- Never log secrets, tokens, the app password or raw uploaded documents. Truncate base64 and other large blobs before logging.
- Log at boundaries (start/end of a turn, each external call, each failure), not inside tight loops.
- The Logs page (`/logs`) reads these files through `/api/logs`; keep file names and formats stable.
- Logs are not backed up and may be deleted (`docs/data.md`).
