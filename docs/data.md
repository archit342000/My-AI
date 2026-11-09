# Data and storage

All persistent state lives under `DATA_DIR` (`backend/config.py`, default `./backend/data`, `/app/backend/data` in Docker).
Mount it as a volume; losing it loses chats, files and vectors.

## Layout

| Path (under `DATA_DIR`) | Contents |
|------|----------|
| `chats.db` | SQLite database: all relational data (see below) |
| `chroma_db/` | ChromaDB persistent store: vector store for file RAG: the `file_store_vector` and `file_store_bm25` collections (`CHROMA_PATH`; no research or preference collections are written) |
| `files/` | Uploaded files (`FILE_STORAGE_PATH`) |
| `file_systems/` | Physical storage for the virtual per-chat file system |
| `logs/` | `llm_calls/`, `tool_calls/`, `general/*.jsonl`, `app.log`, `network_index.jsonl` (see `docs/standards/errors-and-logging.md`) |
| `tasks/`, `cache/` | Background task state and cache files |

## SQLite

- Access only through `db` from `backend.database` (mixins in `backend/database/wrapper/`). Connections come from `make_connection`
  with a 30 s timeout and foreign keys on.
- Main tables: `users` (identity and role, seeded with the admin from `ADMIN_EMAIL`), `workspaces`, `chats`, `messages`, `sub_agent_messages`, `personas`, `skills`, `memories`, `files`, `collections`,
  `file_systems` (+ `file_system_versions`, `file_system_permissions`), `pending_callbacks`,
  `system_settings`, `clipboard`, `code_execution_history`. `backend/database/init_db.py` is the authority for columns.
- Ownership: `workspaces`, `chats`, `personas`, `skills` and `memories` carry `user_id` (nullable column, no foreign key); every other table
  inherits its owner through `chat_id` or `workspace_id` (artifact tables through `file_system_id`; `users` and `system_settings` are global). On every start `init_db()` assigns ownerless root rows to the admin and stops with an
  error when they exist and no admin is configured, or when ownerless skills share a name with another skill (rename or delete the duplicates). Skill names are unique per user (`UNIQUE(user_id, name)`); triggers (`trg_skills_unowned_name`, `..._update`) also reject any skill write that would share a name with another skill when either is ownerless (NULL owners are distinct under `UNIQUE`; the wrapper now always sets an owner, so they only guard legacy or direct writes).
- Artifact (`file_systems`) ids are UUID4 strings. Older artifacts may still have per-owner numeric ids, which keep working.
  `init_db()` drops the legacy `file_system_counters` table (migration 14). It held only per-owner sequence numbers, no user
  data; see Migrations rule 4 below.
- `messages.attachments` is a nullable JSON list of file references (`file_id`, `name`, `size`, `mime_type`) kept on user messages
  so attachments survive a reload and Retry. It is an additive column; `init_db()` backfills it once from existing `files` collections.
- One writer at a time. Keep transactions short and never hold one across `await` or network calls (`docs/pitfalls.md`).

## Migrations

There is no version table. `init_db()` runs on every start and must be idempotent:

1. Add new tables with `CREATE TABLE IF NOT EXISTS`.
2. Add columns by checking `PRAGMA table_info` and then `ALTER TABLE ... ADD COLUMN` with a default.
3. Renames and constraint changes recreate the table inside one transaction and also recreate child tables that reference it. Step 11 does this with `_rebuild_table_with_cascade` in `backend/database/init_db.py`: new table, copy by column name, drop, rename, re-create indexes, inside a per-table savepoint with foreign keys off (steps 0-10 are committed first, and `_assign_owners` commits before its skills rebuild, so each earlier step must stay idempotent), so a failed copy leaves the original table untouched. `_repair_leftover_old_tables` restores `<table>_old` leftovers from earlier failed runs on start, or logs them when both tables hold rows.
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
