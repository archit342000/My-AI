# Python standards

Applies to `app.py`, `backend/`, `inference_proxy/`, the MCP servers and `scripts/`.
General rules (venv, config, `db`, logging, errors) are in `docs/standards/coding.md`.

## Language and style

- **Version:** Python 3.12 (matches the Docker images). Run everything with `venv/bin/python`.
- **Formatting:** PEP 8, 4-space indent, double-quoted strings for new code. Match the surrounding file when editing.
  No formatter is configured; do not reformat code you are not changing.
- **Linting:** `venv/bin/python -m ruff check .` (config in `pyproject.toml`, tool installed from `requirements-dev.txt`) must pass; `scripts/check.sh` runs it.
  It enforces correctness rules only (syntax errors, undefined names). Also remove unused imports and variables in code you touch
  (`ruff check --select F401,F841 <file>`); enabling those repo-wide is a future cleanup, not a requirement for unrelated files.
- **Type checking:** not enforced (no mypy/pyright). Hints are documentation; keep them accurate.
- **Naming:** `snake_case` functions and modules, `PascalCase` classes, `UPPER_CASE` constants, `_leading_underscore` for module-private names.
- **Imports:** standard library, third party, then local (`backend.*`), each group separated by a blank line.
  Import at module top. Local imports inside functions only to break a real import cycle.
- **Type hints:** annotate parameters and return types of every new or changed public function.
  Use `Optional[...]`, `Dict`, `List` from `typing` as the codebase does, or built-in generics in new files.
  Use `Pydantic` models for data crossing a boundary (API payloads, tool arguments).
- **Docstrings:** every module, class and public function. One-line summary, then `Args:`, `Returns:`, `Raises:` when not obvious
  (the style used in `backend/error_handling.py`). Docstrings are the per-function documentation (see `docs/standards/docs.md`).

## Async

- Flask routes and tool functions that call MCP or HTTP clients are `async`. Do not block the event loop:
  no `time.sleep`, `requests` or blocking file/DB loops inside `async def`. Use `await asyncio.sleep`, `httpx.AsyncClient`, or a thread executor.
- Streaming endpoints yield incrementally (`AsyncGenerator`); never buffer a whole response to return it at once.
- Shared mutable state needs a lock (see the `threading.Lock` in `CircuitBreaker`).

## External calls

- Every call to the LLM, embeddings, search or browsing goes through `backend/error_handling.py` (retry, jitter, circuit breaker).
- Set an explicit timeout on every network call. Never rely on the library default.
- Read configuration and secrets only through `backend/config.py` (`get_secret`). No `os.getenv` elsewhere, no hardcoded URLs or keys.

## Errors and logging

Follow `docs/standards/errors-and-logging.md`. In short: specific exceptions, no masked failures, `log_event()` instead of `print()`,
and never log secrets.

## Database

- Use `db` from `backend.database` only. Multi-statement changes run in one transaction (`BEGIN IMMEDIATE`).
  Delete child rows before parents (foreign keys are enforced). See `docs/pitfalls.md`.
- Schema changes are idempotent migrations in `init_db()` with a test; see `docs/data.md`.

## Dependencies

- Pin exact versions in `requirements.txt` (`==`). Add a library only when the standard library or an existing dependency cannot do the job.
- Check the current version and API in the official docs first (rule 8 in `coding.md`). See `docs/standards/dependencies.md`.
