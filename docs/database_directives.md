# Database Directives

## Overview

This document describes the SQLite database architecture, write mechanisms, migration strategies, and best practices for all agents working with data persistence.

## Database Schema

### Primary Tables

#### `chats`

Stores chat session metadata.

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PRIMARY KEY | Unique chat identifier |
| `title` | TEXT | Chat title |
| `timestamp` | REAL | Creation timestamp (epoch) |
| `memory_mode` | INTEGER | 1 if memory mode enabled, 0 otherwise |
| `research_mode` | INTEGER | 1 if research mode enabled, 0 otherwise |
| `is_vision` | INTEGER | 1 if vision mode enabled, 0 otherwise |
| `last_model` | TEXT | Last LLM model used |
| `vision_model` | TEXT | Vision-specific model |
| `max_tokens` | INTEGER | Max tokens for chat (default: 16384) |
| `is_custom_title` | INTEGER | 1 if title is user-customized |
| `folder` | TEXT | Folder for organization |
| `search_depth_mode` | TEXT | 'regular' or 'deep' |
| `research_completed` | INTEGER | 1 if research completed |
| `had_research` | INTEGER | 1 if research was used |
| `canvas_mode` | INTEGER | 1 if canvas mode enabled |
| `enable_thinking` | INTEGER | 1 if thinking logic enabled (default: 1) |
| `temperature` | REAL | Sampling temperature (default: 1.0) |
| `top_p` | REAL | Top-p sampling (default: 1.0) |
| `top_k` | INTEGER | Top-k sampling (default: 40) |
| `min_p` | REAL | Min-p sampling (default: 0.05) |
| `presence_penalty` | REAL | Presence penalty (default: 0.0) |
| `frequency_penalty` | REAL | Frequency penalty (default: 0.0) |

#### `messages`

Stores individual messages within chats.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | Message ID |
| `chat_id` | TEXT | Foreign key to chats(id) |
| `role` | TEXT | 'user', 'assistant', 'system' |
| `content` | TEXT | Message content (JSON-serialized if structured) |
| `timestamp` | REAL | Message timestamp (epoch) |
| `model` | TEXT | Model used for response |
| `tool_calls` | TEXT | JSON array of tool calls |
| `tool_call_id` | TEXT | Tool call identifier |
| `name` | TEXT | Tool name |

**Note on File Linking**: When a message contains uploaded files, they are stored within the `content` field as a JSON object:
```json
{
  "text": "User message text",
  "uploadedFiles": [
    {"id": "file_uuid", "name": "original.pdf", "type": "application/pdf"}
  ]
}
```
This pattern ensures that file context is preserved exactly when the user sent it.

#### `canvases`

Stores canvas metadata for persistent documents. Uses a **composite primary key**.

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT | Unique canvas identifier (local to chat) |
| `chat_id` | TEXT | Foreign key to chats(id) |
| `title` | TEXT | Canvas title |
| `filename` | TEXT | Markdown filename on disk |
| `timestamp` | REAL | Creation timestamp |
| `folder` | TEXT | Folder organization |
| `tags` | TEXT | JSON array of tags |
| `canvas_type` | TEXT | 'custom', 'code', 'document', etc. |
| `current_version` | INTEGER | Latest version number |

**Primary Key**: `(id, chat_id)`

#### `canvas_versions`

Stores version history for canvases.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT | Version ID |
| `canvas_id` | TEXT | Foreign key to canvases(id) |
| `chat_id` | TEXT | Foreign key to canvases(chat_id) |
| `version_number` | INTEGER | Version number |
| `content` | TEXT | Canvas markdown content |
| `author` | TEXT | Author identifier |
| `timestamp` | REAL | Version timestamp |
| `comment` | TEXT | Version comment |

**Foreign Key**: `(canvas_id, chat_id)` REFERENCES `canvases(id, chat_id)`

#### `files`

Stores user-uploaded file metadata and processing status.

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PRIMARY KEY | Unique file identifier |
| `chat_id` | TEXT | Foreign key to chats(id) |
| `original_filename` | TEXT | Original filename provided by user |
| `stored_filename` | TEXT | Sanitized filename for disk storage |
| `mime_type` | TEXT | Detected MIME type (e.g. 'application/pdf') |
| `file_size` | INTEGER | File size in bytes |
| `content_text` | TEXT | Extracted text content for RAG indexing |
| `created_at` | REAL | Creation timestamp (epoch) |
| `processing_status`| TEXT | 'pending', 'processing', 'completed', or 'failed' |

**Usage:** The `FileManager.upload_file()` function populates this table. Files are automatically cleaned up when the corresponding chat is deleted.

#### `canvas_counters`

Used for atomic ID generation per chat. Each chat has its own counter that increments atomically.

| Column | Type | Description |
|--------|------|-------------|
| `chat_id` | TEXT PRIMARY KEY | Foreign key to chats(id) |
| `counter` | INTEGER | Incrementing counter for canvas IDs |

**Usage:** The `get_next_canvas_counter(chat_id)` function uses this table to generate unique incrementing IDs for canvases within a chat.

#### `canvas_permissions`

Stores metadata for shared canvases. Note: This table combines both permissions and canvas metadata.

| Column | Type | Description |
|--------|------|-------------|
| `canvas_id` | TEXT | Foreign key to canvases(id) |
| `chat_id` | TEXT | Foreign key to canvases(chat_id) |
| `title` | TEXT | Canvas title |
| `filename` | TEXT | Markdown filename on disk |
| `canvas_type` | TEXT | 'custom', 'code', 'document', etc. |
| `shared_with` | TEXT | JSON array of user IDs or 'any_user' |
| `access_level` | TEXT | 'read' or 'write' |
| `metadata` | TEXT | JSON metadata for the canvas |
| `created_at` | REAL | Creation timestamp (epoch) |

**Primary Key**: `(canvas_id, chat_id)`

**Note:** The schema differs from the original permission-focused design. The table now stores comprehensive canvas metadata including sharing information.

#### `canvases_search`

FTS5 virtual table for full-text search on canvases.

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT | Foreign key to canvases(id) |
| `title` | TEXT | Canvas title (searchable) |
| `content` | TEXT | Canvas content (searchable) |

## Consistency & Caching (Cache-Aside)

The application implements a high-performance **Cache-Aside** strategy via `backend/cache_layer.py` and `backend/db_wrapper.py`.

### Hybrid Row-Level Locking
To ensure thread-safety and data consistency under high concurrency (especially during long-running research tasks), the system uses a **Hybrid Row-Level Locking** mechanism:
- **Two-Level Blocking**: Locks are managed at both the table and row level to prevent race conditions during "read-modify-write" cycles.
- **Atomic Batching**: Operations like `db.add_messages_batch()` use explicit `BEGIN` and `COMMIT` blocks to ensure atomicity at the SQLite level.

### WAL Flush Coordination
The cache layer coordinates with the SQLite **Write-Ahead Log (WAL)** to ensure that memory cache invalidation only occurs after successful disk commits. This prevents "stale cache" scenarios where the in-memory state outruns the persistent state.

## Write Mechanism Directives

### Rule 1: Always Use Unified DB Layer

Agents must use the `db` instance from `backend/db_wrapper.py` for all database operations.

**Note:** `storage.py` is partially deprecated. Some functions are still used:
- `lock_manager` - For database locking
- `execute_with_retry` - For retry logic
- `sync_canvas_search_index` - For FTS5 sync
- `delete_canvas_versions_after` - For version cleanup

Direct SQL queries are prohibited.

### Rule 2: Content Serialization

All structured content (lists, dicts) must be JSON-serialized before storage.

```python
# In add_message() - automatic serialization
if content is not None and not isinstance(content, str):
    content = json.dumps(content)

# For tool_calls
if tool_calls is not None and not isinstance(tool_calls, str):
    tool_calls = json.dumps(tool_calls)
```

### Rule 3: Atomic Operations for Write Functions

Each storage function performs its own transaction (begin, commit, close). Agents do not need to wrap calls in transactions for single operations.

```python
# Single operation is atomic
add_message(chat_id, "user", "Message 1")
add_message(chat_id, "assistant", "Response 1")

# For multiple related operations, wrap in try-except
try:
    save_chat(chat_id, "Title", timestamp)
    add_message(chat_id, "user", "Content")
    add_message(chat_id, "assistant", "Response")
except Exception as e:
    # Handle error - all operations roll back effectively
    log_error(e)
```

### Rule 4: NULL Handling for Content

Content fields must never be NULL. If content is None, it should be converted to empty string.

```python
# In get_chat() - NULL protection
raw_content = m.get('content')
if raw_content is None:
    m['content'] = ""
else:
    try:
        m['content'] = json.loads(raw_content)
    except (jsonDecodeError, TypeError):
        m['content'] = raw_content
```

## Migration Strategy

### Rule 5: Use ALTER TABLE with Try-Except

Migrations must be defensive - use try-except to handle cases where columns already exist.

```python
# Safe migration pattern
try:
    c.execute('ALTER TABLE chats ADD COLUMN new_column INTEGER DEFAULT 0')
except sqlite3.OperationalError:
    pass  # Column already exists - safe to proceed
```

### Rule 6: Migration Code in init_db()

All schema evolution is handled in `init_db()` through defensive ALTER TABLE statements. The function is idempotent - safe to run multiple times.

```python
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Create base tables
    c.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            id TEXT PRIMARY KEY,
            title TEXT,
            ...
        )
    ''')

    # Add columns if they don't exist
    try:
        c.execute('ALTER TABLE chats ADD COLUMN new_feature INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass  # Already exists

    conn.commit()
    conn.close()
```

### Rule 7: Index Creation is Defensive

All index creation uses defensive patterns:

```python
try:
    c.execute('CREATE INDEX IF NOT EXISTS idx_chats_folder ON chats(folder)')
except sqlite3.OperationalError:
    pass
```

## FTS5 Search Index

### Rule 8: Always Sync After Write

After modifying canvas content, always sync the search index via `db.sync_canvas_search_index()`.

```python
from backend.db_wrapper import db

# After updating canvas content
db.save_canvas_version(canvas_id, chat_id, content)
db.sync_canvas_search_index(canvas_id, chat_id)  # Required
```

### Rule 9: Handle Index Corruption

The `db.fix_fts5_table()` function should be called on startup to detect and repair corrupted FTS5 tables.

```python
from backend.db_wrapper import db

# On application startup
if db.fix_fts5_table():
    log_event("fts5_recovered", {"timestamp": time.time()})
```

### Rule 10: Rebuild Index When Needed

Use `db.rebuild_canvas_search_index()` when:
- FTS5 returns unexpected results
- Manual index refresh is required
- After bulk canvas updates

```python
from backend.db_wrapper import db

indexed_count = db.rebuild_canvas_search_index()
log_event("index_rebuilt", {"count": indexed_count})
```

## Transaction Handling

### Rule 11: Single Operations are Self-Contained

Each storage function is a complete transaction. Do not attempt to combine multiple function calls into a single transaction unless you have specific performance requirements.

```python
# Standard pattern - each call is atomic
save_chat(chat_id, title, timestamp)
add_message(chat_id, "user", content)
add_message(chat_id, "assistant", response)
```

### Rule 12: Batch Operations for Deletion

Use `db.delete_chat()` for complete chat deletion. It handles:
1. Canvas file deletion from disk
2. Canvas metadata deletion from database
3. Message deletion
4. Chat metadata deletion
5. Row-level cache invalidation

```python
from backend.db_wrapper import db

# Complete chat deletion with cleanup
db.delete_chat(chat_id)
```

## Query Patterns

### Rule 13: Use get_chat() for Chat Retrieval

The `db.get_chat(chat_id)` function returns a complete chat with its metadata. For full history including messages, use `db.get_chat_full(chat_id)`.

```python
from backend.db_wrapper import db

chat = db.get_chat_full(chat_id)
for msg in chat['messages']:
    print(msg['content'])
```

### Rule 14: Use get_all_chats() for Listing

Use `db.get_all_chats()` to retrieve all chats ordered by timestamp (newest first).

```python
from backend.db_wrapper import db

chats = db.get_all_chats()
for chat in chats:
    print(f"{chat['title']} ({chat['timestamp']})")
```

### Rule 15: Use get_chat_canvases() for Canvas List

Retrieve all canvases for a specific chat.

```python
from backend.db_wrapper import db

canvases = db.get_chat_canvases(chat_id)
for canvas in canvases:
    print(canvas['title'])
```

## Data Integrity Rules

### Rule 16: Chat IDs are Persistent Identifiers

Chat IDs should be generated once and never changed. They are used as foreign keys throughout the database.

```python
import uuid

# Generate new chat ID
chat_id = str(uuid.uuid4())

# Use consistently
save_chat(chat_id, "Title", time.time())
```

### Rule 17: Timestamps Use Epoch Time

All timestamp fields use Unix epoch time (float seconds since 1970).

```python
import time

timestamp = time.time()
save_chat(chat_id, "Title", timestamp)
```

### Rule 18: Custom Title Flag

When a user renames a chat, set `is_custom_title = 1` to prevent automatic title overwrites.

```python
from backend.db_wrapper import db

# User renames chat
db.rename_chat(chat_id, "Custom Title")
# Now is_custom_title = 1 in DB
```

## Error Handling

### Rule 19: Handle Database Locked Errors

SQLite may return "database is locked" errors under concurrent access. Implement retry with backoff.

```python
import sqlite3
import time

def safe_get_chat(chat_id, max_retries=3):
    for attempt in range(max_retries):
        try:
            return get_chat(chat_id)
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                time.sleep(0.1 * (attempt + 1))
                continue
            raise
```

### Rule 20: Handle JSON Deserialization Failures

Content stored as JSON may fail to deserialize. Always handle JSONDecodeError gracefully.

```python
try:
    structured_content = json.loads(raw_content)
except json.JSONDecodeError:
    structured_content = raw_content  # Fallback to raw string
```

## Best Practices

### 1. Always Use Provided Abstractions

Don't bypass `db_wrapper.py` functions with direct SQL.

### 2. Handle NULL Content

Ensure content fields are never NULL - convert to empty string.

### 3. Sync Search Index After Canvas Changes

FTS5 search index must be kept in sync with canvas content.

### 4. Use Retry for Locked Databases

Implement retry logic for "database is locked" errors.

### 5. Test Migration Idempotency

Migration code should be safe to run multiple times.

## Functions Reference

### Chat Operations

| Function | Purpose |
|----------|---------|
| `init_db()` | Initialize database schema (delegated to `storage.init_db`) |
| `db.get_all_chats()` | Get all chats ordered by timestamp |
| `db.get_chat(chat_id)` | Get chat metadata |
| `db.get_chat_full(chat_id)` | Get chat metadata and all messages |
| `db.save_chat(...)` | Create new chat |
| `db.update_chat(...)` | Update existing chat metadata |
| `db.rename_chat(chat_id, new_title)` | Rename chat (sets `is_custom_title=1`) |
| `db.delete_chat(chat_id)` | Delete chat and all related data |
| `db.delete_all_chats()` | Delete all chats |
| `db.clear_messages(chat_id)` | Clear all messages for a chat |
| `db.delete_last_turn(chat_id)` | Delete last user/assistant turn |

### Message Operations

| Function | Purpose |
|----------|---------|
| `db.add_message(chat_id, role, content, ...)` | Add message to chat |
| `db.update_message_content(msg_id, content)` | Update specific message text |
| `db.delete_messages_from(chat_id, from_id)` | Delete messages after a certain ID |

### Canvas Operations

| Function | Purpose |
|----------|---------|
| `db.save_canvas(canvas_id, chat_id, ...)` | Save canvas metadata |
| `db.get_chat_canvases(chat_id)` | Get all canvases for a chat |
| `db.get_canvas_meta(canvas_id, chat_id)` | Get single canvas metadata |
| `db.get_canvas_content_by_id(canvas_id, chat_id)` | Get canvas markdown content |
| `db.delete_canvas_meta(canvas_id, chat_id)` | Delete canvas metadata |
| `db.generate_canvas_filename(chat_id, canvas_id)` | Generate filename |
| `db.sync_canvas_search_index(canvas_id, chat_id)` | Sync FTS5 index |
| `db.rebuild_canvas_search_index()` | Rebuild entire FTS5 index |
| `db.fix_fts5_table()` | Detect and repair FTS5 corruption |
| `db.get_next_canvas_counter(chat_id)` | Get unique incrementing ID for chat |
| `db.save_canvas_version(cid, mid, content, ...)` | Save new content version |
| `db.get_canvas_versions(cid, mid)` | List version history |

## Appendix: SQLite Connection Pattern

While agents should use the provided functions, here's the underlying connection pattern:

```python
import sqlite3
import json
from backend.config import DATA_DIR

DB_PATH = os.path.join(DATA_DIR, "chats.db")

def get_db_connection():
    """Get a new database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Example usage within a function
conn = get_db_connection()
c = conn.cursor()
c.execute("SELECT * FROM chats WHERE id = ?", (chat_id,))
result = c.fetchone()
conn.commit()
conn.close()
```
