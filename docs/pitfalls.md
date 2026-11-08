# Known pitfalls

Add an entry when you find or fix a bug that could affect others, or when a fix reveals a deeper
workflow issue. Keep each entry to the core lesson.

## Inference and streaming

- **Missing `<think>` tags:** llama.cpp returns reasoning in `reasoning_content` without `<think>` tags. Do not assume
  they are in the stream; wrap reasoning explicitly before saving it to SQLite.
- **Empty `content` with schema-constrained output:** when `response_format` enforces a JSON schema, `content` can be
  `None` or `""` (first seen with LM Studio, the previous backend; recheck against llama.cpp). Do not loop waiting for it;
  read the JSON from `reasoning_content`.
- **Vision payloads in tool messages:** base64 image data bloats logs, history and context. Truncate it before logging
  (`backend/logging`) and keep it out of persisted tool messages; send images only in the turn that needs them.
- **Streams outlive requests:** a turn keeps running if the client disconnects. Stream state lives in `response_cache`
  (WAL-backed), and clients re-attach through `/api/chats/<chat_id>/stream`. Do not tie generation to the request lifetime.
- **State restoration on failures:** when a turn or tool call fails, restore the previous state instead of leaving
  partial messages or half-applied tool results behind.

## Editing

- **File truncation on edits:** full-file writes to large files (`app.py`, `backend/chat/router.py`) can silently drop code.
  Use targeted edits and check the diff.
- **Sandbox first** for complex logic: prove it in `scratch/` or a temporary container before wiring it into the app.

## Database

- **Database locked errors:** SQLite allows one writer. Keep transactions short, never hold one across an `await`
  or a network call, and use `BEGIN IMMEDIATE` for multi-statement writes. The connection timeout is 30 s.
- **Foreign-key delete order in `delete_chat` / `delete_all_chats`:** SQLite enforces `PRAGMA foreign_keys=ON` per
  statement. Delete child rows in `file_system_versions` and `file_system_permissions` before `file_systems`, and all
  chat-level children before `chats`. Otherwise you get `sqlite3.IntegrityError: FOREIGN KEY constraint failed`
  when a chat has file attachments. Wrap the whole sequence in one `BEGIN IMMEDIATE` transaction.
- **Table-recreate migrations:** renaming or recreating a parent table can leave child foreign keys pointing at the
  old name (`file_system_versions` once referenced a dropped `file_systems_old`). Recreate children in the same
  migration. See `backend/database/init_db.py`.

## Testing and tooling

- **Running tests without the right environment:** many modules (especially `backend/`) need `EMBEDDING_URL`,
  `AI_URL` and `PYTHONPATH=.` set to bypass validation. See `docs/standards/testing.md`.
- **MCP service tests need their own dependencies:** `code_runner_mcp` tests must run from inside that directory
  (`PYTHONPATH=.`); `playwright_mcp` tests need its pinned Starlette and fail under the main `venv`.
- **RAG grid search:** synthetic test data must be highly discriminative. Generic or repetitive data causes
  zero-recall metrics.

## Known defects (not yet fixed)

- `backend/tools/agents/research_agent/agent.py` uses undefined names (`MANAGE_TASK_LIST_TOOL`, `READ_FS_FILE_TOOL`,
  `REPLACE_FS_TEXT_TOOL`, `REPLACE_FS_LINES_TOOL`), and `research_utils.py` calls an undefined `_get_sampling_params`.
  Ruff reports them as `F821`; they are ignored in `pyproject.toml` until fixed. Remove the ignore with the fix.
