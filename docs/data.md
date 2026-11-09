# Data and storage

All persistent state lives under `DATA_DIR` (`backend/config.py`, default `./backend/data`, `/app/backend/data` in Docker).
Mount it as a volume; losing it loses chats, files and vectors.

## Layout

| Path (under `DATA_DIR`) | Contents |
|------|----------|
| `chats.db` | SQLite database: all relational data (see below) |
| `chroma_db/` | ChromaDB persistent store: vector collections for file, research and preference RAG (`CHROMA_PATH`) |
| `files/` | Uploaded files (`FILE_STORAGE_PATH`) |
| `file_systems/` | Physical storage for the virtual per-chat file system |
| `logs/` | `llm_calls/`, `tool_calls/`, `general/*.jsonl`, `app.log`, `network_index.jsonl` (see `docs/standards/errors-and-logging.md`) |
| `tasks/`, `cache/` | Background task state and cache files |

## SQLite

- Access only through `db` from `backend.database` (mixins in `backend/database/wrapper/`). Connections come from `make_connection`
  with a 30 s timeout and foreign keys on.
- Main tables: `workspaces`, `chats`, `messages`, `sub_agent_messages`, `personas`, `skills`, `memories`, `files`, `collections`,
  `file_systems` (+ `file_system_versions`, `file_system_permissions`, `file_system_counters`), `pending_callbacks`,
  `system_settings`, `clipboard`, `code_execution_history`. `backend/database/init_db.py` is the authority for columns.
- Artifact (`file_systems`) ids are UUID4 strings. Older artifacts may still have per-owner numeric ids, which keep working.
  `file_system_counters` is legacy and no longer used to create ids.
- One writer at a time. Keep transactions short and never hold one across `await` or network calls (`docs/pitfalls.md`).

## Migrations

There is no version table. `init_db()` runs on every start and must be idempotent:

1. Add new tables with `CREATE TABLE IF NOT EXISTS`.
2. Add columns by checking `PRAGMA table_info` and then `ALTER TABLE ... ADD COLUMN` with a default.
3. Renames and constraint changes recreate the table inside one transaction and also recreate child tables that reference it.
4. Backfill data in the same step. Never drop user data without an explicit, documented decision.
5. Add a test in `backend/database/tests/` that runs `init_db()` twice and against a database created by the previous schema.

## Vector store

- ChromaDB collections are managed only by `RAGManager` (`backend/rag/manager.py`). If the embedding model changes dimension, the
  manager recreates the collection, so re-indexing is automatic but not free.
- Retrieval is hybrid (vector plus BM25). Tune parameters with the grid-search scripts in `scripts/`; see `backend/rag/README.md`.

## Backup and restore

- Back up by stopping the app (or at least pausing writes) and copying the whole `DATA_DIR`. Copying `chats.db` alone while the app
  runs can capture an inconsistent state; use `sqlite3 chats.db ".backup <file>"` for a live copy.
- Restore by stopping the app, replacing `DATA_DIR`, and starting it; `init_db()` migrates older databases forward.
- Log files are safe to delete or rotate; everything else is user data.
