# Cache Directives

**Note:** This document may contain outdated information. The code is the source of truth. For discrepancies, see `IMPLEMENTATION_DISCREPANCIES.md`.

## Overview

This document describes the cache system architecture, write-through patterns, TTL expiration rules, WAL durability mechanism, and best practices for all agents working with caching.

## Cache System Architecture

The application uses **two separate cache systems**:

1. **Response Cache** (`cache_system.py`): For SSE streaming with WAL support
2. **Cache-Aside Pattern** (`cache_layer.py`): For database read caching

This document covers the **Response Cache** system.

## Architecture Overview

### Component Location

The cache system is implemented in `backend/cache_system.py` and exposes a singleton `cache_system` object of type `ResponseCache`.

### Cache Model

The cache uses an **in-memory buffer with WAL (Write-Ahead Log) durability** model:

- **Primary storage**: In-memory dictionary (`self._cache`)
- **Durability layer**: WAL files in `{DATA_DIR}/cache/{chat_id}.wal`
- **Recovery**: WAL replay on application restart

```
┌─────────────────────────────────────────────────────────────┐
│                 Cache Architecture                          │
├─────────────────────────────────────────────────────────────┤
│  Memory Cache: {chat_id: {'chunks': [], 'subscribers': [],  │
│                           'lock': Lock,                     │
│                           'last_updated': timestamp,        │
│                           'status': 'active'}}              │
│                                                             │
│  WAL Files: {chat_id}.wal (JSON lines format)              │
│                                                             │
│  Recovery: On restart, replay WAL to reconstruct cache     │
└─────────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **Cache is authoritative** for active operations
2. **WAL provides durability** across restarts
3. **Streaming via subscribers** for real-time updates
4. **Thread-safe** with per-chat locks

## Core Operations

### initialize_chat(chat_id)

Prepares cache for a new active chat.

```python
from backend.cache_system import cache_system

# Initialize before starting a chat
cache_system.initialize_chat(chat_id)
```

**What it does:**
- Creates in-memory structure for the chat
- Initializes empty chunks and subscribers lists
- Creates/clears WAL file for the chat
- Sets status to 'active'

**Rule 1: Must call before append_chunk**

Always call `initialize_chat()` before starting to append chunks to a new chat.

```python
# Correct
cache_system.initialize_chat(chat_id)
cache_system.append_chunk(chat_id, chunk_data)

# Incorrect - may fail silently
cache_system.append_chunk(chat_id, chunk_data)
```

### append_chunk(chat_id, chunk_data)

Appends a data chunk to the cache and WAL.

```python
# Append a streaming chunk
cache_system.append_chunk(chat_id, chunk_data)
```

**What it does:**
1. Adds entry to in-memory chunks list
2. Updates `last_updated` timestamp
3. Notifies all subscribers (if any)
4. Writes to WAL file for durability

**Thread safety:** Uses per-chat lock for thread-safe operations.

**Rule 2: Check chat is initialized**

If the chat is not initialized, append_chunk silently returns.

```python
# Always ensure chat is initialized first
if not cache_system.is_active(chat_id):
    cache_system.initialize_chat(chat_id)

cache_system.append_chunk(chat_id, chunk_data)
```

### subscribe(chat_id)

Returns a generator that yields chunks for a chat. Replays existing history first, then streams new chunks.

```python
# Subscribe to a chat stream
for chunk in cache_system.subscribe(chat_id):
    process(chunk)
```

**What it does:**
1. Recovers from WAL if chat not in memory (on restart)
2. Replays all existing chunks to a new subscriber queue
3. Yields new chunks as they arrive
4. Handles `[[DONE]]` and `[[ERROR]]` sentinel values

**Rule 3: Handle sentinel values**

The generator yields special sentinel values:

```python
for chunk in cache_system.subscribe(chat_id):
    if chunk == "data: [DONE]\n\n":
        print("Stream completed")
        break
    if chunk == "[[ERROR]]":
        print("Stream error occurred")
        break
    process(chunk)
```

### mark_completed(chat_id, cleanup=True)

Finalizes a chat and returns aggregated content.

```python
# Mark chat as completed
full_content = cache_system.mark_completed(chat_id, cleanup=True)
```

**What it does:**
1. Appends `[[DONE]]` sentinel to notify subscribers
2. Aggregates all chunks into full content
3. Filters out internal research activity noise
4. Combines content with reasoning (if any)
5. Optionally cleans up chat (deletes WAL, removes from memory)

**Parameters:**
- `chat_id`: The chat identifier
- `cleanup`: If True, immediately deletes WAL and removes from memory

**Rule 4: Use cleanup=False for later cleanup**

If you need to use the cached content after marking completed, use `cleanup=False`:

```python
# Get content without immediate cleanup
full_content = cache_system.mark_completed(chat_id, cleanup=False)

# Later, explicitly clean up
cache_system.cleanup_chat(chat_id)
```

### cleanup_chat(chat_id)

Removes a chat from cache and deletes its WAL file.

```python
cache_system.cleanup_chat(chat_id)
```

**Rule 5: Cleanup is separate from mark_completed**

`cleanup_chat()` is only needed if you used `mark_completed(chat_id, cleanup=False)`.

### is_active(chat_id)

Checks if a chat is currently in memory.

```python
if cache_system.is_active(chat_id):
    # Chat is active in memory
    pass
else:
    # Chat may need recovery from WAL or initialization
    pass
```

### recover_from_wal(chat_id, ttl_seconds=None)

Reconstructs cache state from WAL file. Called automatically by `subscribe()` if needed.

```python
# Manual recovery (usually not needed)
cache_system.recover_from_wal(chat_id)

# With custom TTL
cache_system.recover_from_wal(chat_id, ttl_seconds=3600)
```

**When to use:**
- Manual recovery after corrupted memory state
- Testing scenarios

**Note on TTL:** When `ttl_seconds` is not provided (None), recovered entries use the default `CACHE_ENTRY_TTL_SECONDS` from `config.py` (default: 1 hour). Pass `ttl_seconds` to override.

**Important:** The `recover_from_wal()` method does NOT automatically set TTL on recovered entries if `ttl_seconds=None` - they will use the default TTL from config.

## Streaming Pattern

### The Subscriber Model

The cache uses a **subscriber-based streaming model**:

```
┌─────────────────────────────────────────────────────────────┐
│                  Streaming Pattern                          │
├─────────────────────────────────────────────────────────────┤
│  1. Initialize chat                                        │
│  2. Subscribe (creates queue, replays history)            │
│  3. Append chunks (updates cache, notifies subscribers)    │
│  4. Subscriber receives chunks via generator              │
│  5. Mark completed (sends DONE, optional cleanup)         │
└─────────────────────────────────────────────────────────────┘
```

### Complete Streaming Example

```python
from backend.cache_system import cache_system

def process_chat_stream(chat_id):
    # Initialize if not active
    if not cache_system.is_active(chat_id):
        cache_system.initialize_chat(chat_id)

    # Subscribe to stream
    def stream_handler():
        for chunk in cache_system.subscribe(chat_id):
            if chunk == "data: [DONE]\n\n":
                break
            if chunk == "[[ERROR]]":
                print("Error in stream")
                break
            # Process chunk (e.g., send to client)
            yield chunk

    # Start streaming
    for chunk in stream_handler():
        send_to_client(chunk)

    # Get final content
    final = cache_system.mark_completed(chat_id, cleanup=True)
    return final
```

## WAL Durability

### WAL Format

Each WAL file uses **JSON lines format**:

```json
{"timestamp": 1234567890.123, "data": "data: {...}\n"}
{"timestamp": 1234567890.456, "data": "data: {...}\n"}
```

**Rule 6: WAL is append-only**

WAL files are append-only. Entries are never modified or deleted until cleanup.

**Rule 7: Handle WAL corruption gracefully**

During recovery, malformed JSON lines are silently skipped:

```python
# In recover_from_wal()
try:
    entry = json.loads(line)
    chunks.append(entry)
except:
    pass  # Skip malformed entries
```

### WAL Recovery

**Automatic recovery** happens when:
1. `subscribe()` is called
2. Chat is not in memory (`chat_id not in self._cache`)
3. WAL file exists

**Manual recovery** can be triggered via `recover_from_wal(chat_id)`.

**Rule 8: WAL path format**

WAL files are stored at: `{DATA_DIR}/cache/{chat_id}.wal`

## TTL Expiration

### TTL in Cache System

The cache system **DOES implement TTL expiration** via:
- `_is_expired(chat_id)`: Checks if a cache entry is expired based on `last_updated` and TTL
- `cleanup_expired()`: Removes all expired entries from the cache

The `ResponseCache` class handles TTL internally using `CACHE_ENTRY_TTL_SECONDS` from `config.py`.

**Note:** This is different from the Cache-Aside pattern (`cache_layer.py`) which provides row-level caching for database reads.

### TTL in Cache-Aside Pattern (cache_layer.py)

The Cache-Aside pattern uses **varying TTL values** based on data type:

| Data Type | TTL | Rationale |
|-----------|-----|-----------|
| `chats` (partial) | 300s (5 min) | Recent chat metadata changes frequently |
| `chats_full` | 60s (1 min) | Full chat content changes rapidly |
| `canvases` | 300s (5 min) | Canvas metadata updates periodically |

**Rule 9: Use internal TTL methods**

The cache system handles TTL internally. Use these methods:

```python
# Check if a chat entry is expired
if cache_system._is_expired(chat_id):
    # Entry is expired - consider fallback to DB
    pass

# Clean up all expired entries
cache_system.cleanup_expired()
```

**Note:** The `ResponseCache` class implements TTL expiration internally using `CACHE_ENTRY_TTL_SECONDS` from `config.py`.

### Automatic Cleanup

A background cleanup thread automatically calls `cleanup_expired()` every `CACHE_CLEANUP_INTERVAL` seconds (default: 5 minutes). This prevents cache entries from accumulating indefinitely.

See `backend/task_manager.py::start_cache_cleanup_thread()` for implementation details.

## Thread Safety

### Locking Mechanism

The cache system is **thread-safe** due to locking:

- `self._lock`: Global lock for cache dictionary access
- `chat_data['lock']`: Per-chat lock for chunk operations

**Rule 11: Access cache under lock**

When directly accessing cache data, use the per-chat lock:

```python
with cache_system._cache[chat_id]['lock']:
    # Safe to access chunks, subscribers
    chunks = cache_system._cache[chat_id]['chunks']
```

## Cache State Structure

### Internal Structure

Each chat entry in the cache has this structure:

```python
{
    'chunks': [
        {"timestamp": 1234567890.123, "data": "chunk_data"},
        ...
    ],
    'subscribers': [queue.Queue(), ...],
    'lock': threading.Lock(),
    'last_updated': 1234567890.456,
    'status': 'active'  # or 'recovered'
}
```

**Fields:**
- `chunks`: List of all chunks for the chat
- `subscribers`: List of subscriber queues
- `lock`: Thread lock for this chat
- `last_updated`: Unix timestamp of last update
- `status`: 'active' or 'recovered'

## Content Filtering

### mark_completed() Filtering

The `mark_completed()` function filters out:

1. **Internal chunks** (`json_data.get('internal') == True`)
2. **Research activity logs** (containing `__research_activity__`)
3. **UI thought snippets** (containing `🔍`)

**Rule 12: These filters are automatic**

Do not manually filter content - it's handled by `mark_completed()`.

## Error Handling

### Error Sentinels

The cache uses sentinel values to signal errors:

- `[[DONE]]`: Stream completed successfully
- `[[ERROR]]`: Error occurred during streaming

**Rule 13: Always check for error sentinel**

```python
for chunk in cache_system.subscribe(chat_id):
    if chunk == "[[ERROR]]":
        # Handle error
        break
```

### WAL Write Errors

WAL write errors are logged via `log_event()` but do not raise exceptions.

**Rule 14: WAL errors are non-fatal**

If WAL write fails, chunks are still cached in memory. The error is logged for debugging.

## Best Practices

### 1. Always Initialize Before Use

```python
# Correct
cache_system.initialize_chat(chat_id)

# Incorrect - may silently fail
cache_system.append_chunk(chat_id, chunk)
```

### 2. Use Cleanup=True When Done

```python
# Standard pattern
cache_system.mark_completed(chat_id, cleanup=True)
```

### 3. Handle Streaming Subscribers Properly

```python
# Always check for DONE and ERROR sentinels
for chunk in cache_system.subscribe(chat_id):
    if chunk == "data: [DONE]\n\n":
        break
    if chunk == "[[ERROR]]":
        break
    process(chunk)
```

### 4. Check is_active() Before Operations

```python
if not cache_system.is_active(chat_id):
    cache_system.initialize_chat(chat_id)
cache_system.append_chunk(chat_id, chunk)
```

### 5. Use Per-Chat Locks for Direct Access

```python
with cache_system._cache[chat_id]['lock']:
    # Access chunks safely
    pass
```

## Functions Reference

| Function | Purpose | Returns |
|----------|---------|---------|
| `initialize_chat(chat_id)` | Initialize cache for new chat | None |
| `append_chunk(chat_id, chunk_data)` | Append chunk to cache | None |
| `subscribe(chat_id)` | Subscribe to chat stream | Generator |
| `recover_from_wal(chat_id)` | Recover cache from WAL | None |
| `mark_completed(chat_id, cleanup=True)` | Finalize chat and get content | str or None |
| `cleanup_chat(chat_id)` | Remove chat from cache | None |
| `is_active(chat_id)` | Check if chat is in memory | bool |
| `_is_expired(chat_id)` | Check if entry is expired | bool |
| `cleanup_expired()` | Remove expired entries | None |

## Appendix: Complete Chat Lifecycle

```python
from backend.cache_system import cache_system

def complete_chat_lifecycle(chat_id):
    # 1. Initialize
    cache_system.initialize_chat(chat_id)

    # 2. Subscribe
    def stream_chunks():
        for chunk in cache_system.subscribe(chat_id):
            if chunk == "data: [DONE]\n\n":
                break
            if chunk == "[[ERROR]]":
                break
            yield chunk

    # 3. Stream chunks (in separate thread or async)
    # for chunk in stream_chunks():
    #     send_to_client(chunk)

    # 4. Append chunks (from producer)
    cache_system.append_chunk(chat_id, "data: {...}\n")

    # 5. Mark completed
    final_content = cache_system.mark_completed(chat_id, cleanup=True)

    return final_content
```
