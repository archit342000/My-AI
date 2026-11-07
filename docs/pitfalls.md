# Known pitfalls

Add an entry when you find or fix a bug that could affect others, or when a fix reveals a deeper
workflow issue. Keep each entry to the core lesson.

- **Missing `<think>` tags** from llama.cpp output.
- **File truncation on edits.**
- **Vision payloads in tool messages.**
- **Database locked errors.**
- **State restoration on failures.**
- **Sandbox first** for complex logic.
- **RAG grid search:** synthetic test data must be highly discriminative. Generic or repetitive
  data causes zero-recall metrics.
- **Running tests without the right environment:** many modules (especially `backend/`) need
  `EMBEDDING_URL`, `AI_URL` and `PYTHONPATH=.` set to bypass validation. See `docs/standards/testing.md`.
- **Foreign-key delete order in `delete_chat` / `delete_all_chats`:** SQLite enforces
  `PRAGMA foreign_keys=ON` per statement. Delete child rows in `file_system_versions` and
  `file_system_permissions` before `file_systems`, and all chat-level children before `chats`.
  Otherwise you get `sqlite3.IntegrityError: FOREIGN KEY constraint failed` when a chat has file
  attachments. Wrap the whole sequence in one `BEGIN IMMEDIATE` transaction.
