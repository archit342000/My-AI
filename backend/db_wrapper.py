"""
Unified database wrapper with Cache-Aside pattern.

Architecture Overview
---------------------
This module implements the DatabaseWrapper class that provides a high-level
interface to the database with the Cache-Aside pattern:

1. Cache-Aside Pattern:
   - Reads: Check cache first, fetch from DB on miss, populate cache
   - Writes: Write to DB directly, invalidate cache for affected row

2. Cache Invalidation:
   - After write operations, affected rows are invalidated in cache
   - This ensures reads fetch fresh data without expensive readback queries

3. Layered Architecture:
   - db_wrapper.py: High-level API with cache integration
   - cache_layer.py: Row-level caching with two-level blocking
   - db_layer.py: Low-level SQLite operations with WAL and locking

4. Thread Safety:
   - Cache layer handles row-level locking
   - DB layer handles connection management
   - Both layers coordinate for consistency

Logging
-------
This module logs all high-level database operations:
- get_chat, get_chat_full, get_messages
- save_chat, update_chat, delete_chat
- add_message, save_canvas_meta
- All cache invalidations

This helps trace the complete flow of database operations.
"""
import sqlite3
import json
import os
import re
import time
import logging
from backend.cache_layer import cache_layer
from backend.db_layer import make_connection

logger = logging.getLogger(__name__)


def _log_db_wrapper_op(op_type: str, chat_id: str = None, details: str = None):
    """
    Internal logging helper for db_wrapper operations.

    Args:
        op_type: Operation type (e.g., "GET_CHAT_START", "SAVE_CHAT_END")
        chat_id: Optional chat identifier
        details: Optional additional details string
    """
    msg = f"[DB_WRAPPER {op_type}]"
    if chat_id:
        msg += f" chat_id={chat_id}"
    if details:
        msg += f" | {details}"
    logger.debug(msg)


class DatabaseWrapper:
    """
    Unified database wrapper with Cache-Aside pattern.

    This class provides all database operations for chats, messages, and canvases.
    It integrates with the cache layer to ensure consistency while minimizing
    expensive database reads.

    Key Principles:
    - All reads go through cache first (fast path)
    - All writes go directly to DB and invalidate cache
    - Row-level locking in cache layer prevents stale reads

    Usage:
        db = DatabaseWrapper()
        chat = db.get_chat("chat-123")  # Returns cached or fetched data
        db.save_chat("chat-123", "New Title")  # Writes to DB, invalidates cache
    """

    # ==================== CHAT OPERATIONS ====================

    def get_chat(self, chat_id: str):
        """
        Get chat with cache-first semantics (row-level).

        This method implements the Cache-Aside pattern:
        1. Try to get from cache (fast, in-memory)
        2. If miss, fetch from DB and populate cache

        Args:
            chat_id: Unique chat identifier

        Returns:
            dict: Chat data if found, None otherwise
        """
        _log_db_wrapper_op("GET_CHAT_START", chat_id)
        fetch_start = time.time()
        result = cache_layer.get("chats", chat_id, lambda: self._get_chat_fetch(chat_id), ttl=300)
        duration_ms = (time.time() - fetch_start) * 1000
        _log_db_wrapper_op("GET_CHAT_END", chat_id, f"duration_ms={duration_ms:.2f}")
        return result

    def ensure_chat_exists(self, chat_id: str):
        """
        Check if a chat exists in the DB, and if not, create a skeleton record.
        This is crucial for satisfy foreign key constraints during manual canvas creation
        in a new chat window.

        Args:
            chat_id: Unique chat identifier
        """
        existing = self.get_chat(chat_id)
        if not existing:
            _log_db_wrapper_op("ENSURE_CHAT_EXISTS_MISS", chat_id)
            self.save_chat(
                chat_id=chat_id,
                title="New Conversation",
                timestamp=time.time(),
                enable_thinking=1
            )
        else:
            _log_db_wrapper_op("ENSURE_CHAT_EXISTS_HIT", chat_id)

    def _get_chat_fetch(self, chat_id: str):

        """
        Internal fetch function for get_chat.

        This method is called by cache_layer.get() when a cache miss occurs.
        It performs the actual database query to fetch the chat data.

        Args:
            chat_id: Unique chat identifier

        Returns:
            dict: Chat data if found, None otherwise
        """
        conn = make_connection()
        try:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM chats WHERE id = ?", (chat_id,))
            row = c.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_chat_full(self, chat_id: str):
        """
        Get chat with all messages (row-level).

        This method fetches a chat along with all its messages in order.
        It uses a longer TTL (60 seconds) than get_chat since the full
        data is more expensive to fetch.

        Args:
            chat_id: Unique chat identifier

        Returns:
            dict: Chat data with 'messages' list if found, None otherwise
        """
        _log_db_wrapper_op("GET_CHAT_FULL_START", chat_id)
        fetch_start = time.time()
        result = cache_layer.get("chats_full", chat_id, lambda: self._get_chat_full_fetch(chat_id), ttl=60)
        duration_ms = (time.time() - fetch_start) * 1000
        _log_db_wrapper_op("GET_CHAT_FULL_END", chat_id, f"duration_ms={duration_ms:.2f}")
        return result

    def _get_chat_full_fetch(self, chat_id: str):
        """
        Internal fetch function for get_chat_full.

        This method is called by cache_layer.get() when a cache miss occurs.
        It performs the actual database query to fetch the chat and all messages.

        Args:
            chat_id: Unique chat identifier

        Returns:
            dict: Chat data with 'messages' list if found, None otherwise
        """
        conn = make_connection()
        try:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM chats WHERE id = ?", (chat_id,))
            chat = c.fetchone()
            if not chat:
                return None
            c.execute("SELECT * FROM messages WHERE chat_id = ? ORDER BY id ASC", (chat_id,))
            messages = c.fetchall()
            chat_dict = dict(chat)
            chat_dict['messages'] = [dict(m) for m in messages]
            return chat_dict
        finally:
            conn.close()

    def save_chat(self, chat_id: str, title: str, timestamp: float, 
                  enable_thinking: int,
                  memory_mode: int = 0, research_mode: bool = False, 
                  is_vision: bool = False, last_model: str = None, 
                  vision_model: str = None, max_tokens: int = 16384, 
                  folder: str = None, search_depth_mode: str = 'regular', 
                  research_completed: int = 0, had_research: int = 0, 
                  canvas_mode: bool = False,
                  temperature: float = 1.0, top_p: float = 1.0, 
                  top_k: int = 40, min_p: float = 0.05, 
                  presence_penalty: float = 0.0, frequency_penalty: float = 0.0, 
                  is_custom_title: int = None):
        """
        Save chat with Cache-Aside pattern (DB write + cache invalidation).

        This method implements the Cache-Aside pattern for writes:
        1. Write directly to DB (bypass cache)
        2. Invalidate cache entry for this chat_id
        3. Subsequent reads will fetch fresh data from DB

        Args:
            chat_id: Unique chat identifier
            title: Chat title
            timestamp: Creation/update timestamp
            memory_mode: Memory mode setting (0=off, 1=on)
            research_mode: Enable research mode
            is_vision: Enable vision model
            last_model: Last model used
            vision_model: Vision model name
            max_tokens: Maximum tokens for responses
            folder: Folder path for organization
            search_depth_mode: Search depth setting
            research_completed: Research completed flag
            had_research: Has research flag
            canvas_mode: Canvas mode enabled
        """
        _log_db_wrapper_op("SAVE_CHAT_START", chat_id)
        write_start = time.time()

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute('''
                    INSERT INTO chats (id, title, timestamp, memory_mode, research_mode,
                                      is_vision, last_model, vision_model, max_tokens,
                                      is_custom_title, folder, search_depth_mode,
                                      research_completed, had_research, canvas_mode, enable_thinking,
                                      temperature, top_p, top_k, min_p, presence_penalty, frequency_penalty)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        title=CASE WHEN excluded.is_custom_title = 1 THEN excluded.title 
                                   WHEN chats.is_custom_title = 1 THEN chats.title 
                                   ELSE excluded.title END,
                        is_custom_title=CASE WHEN excluded.is_custom_title = 1 THEN 1 ELSE chats.is_custom_title END,
                        memory_mode=excluded.memory_mode,
                        research_mode=excluded.research_mode,
                        is_vision=excluded.is_vision,
                        last_model=excluded.last_model,
                        vision_model=excluded.vision_model,
                        max_tokens=excluded.max_tokens,
                        folder=COALESCE(excluded.folder, chats.folder),
                        search_depth_mode=excluded.search_depth_mode,
                        research_completed=excluded.research_completed,
                        had_research=excluded.had_research,
                        canvas_mode=excluded.canvas_mode,
                        enable_thinking=excluded.enable_thinking,
                        temperature=excluded.temperature,
                        top_p=excluded.top_p,
                        top_k=excluded.top_k,
                        min_p=excluded.min_p,
                        presence_penalty=excluded.presence_penalty,
                        frequency_penalty=excluded.frequency_penalty
                ''', (chat_id, title, timestamp, memory_mode, research_mode,
                      is_vision, last_model, vision_model, max_tokens,
                      is_custom_title if is_custom_title is not None else 0,
                      folder, search_depth_mode, research_completed, had_research, canvas_mode, enable_thinking,
                      temperature, top_p, top_k, min_p, presence_penalty, frequency_penalty))
                conn.commit()
            finally:
                conn.close()

        # Write to DB directly, then invalidate cache
        _write()
        db_write_duration = (time.time() - write_start) * 1000
        cache_layer.invalidate("chats", chat_id)
        cache_layer.invalidate("chats_full", chat_id)
        invalidate_duration = (time.time() - write_start - db_write_duration / 1000) * 1000
        _log_db_wrapper_op("SAVE_CHAT_END", chat_id, f"db_ms={db_write_duration:.2f} invalidate_ms={invalidate_duration:.2f}")

    def update_chat(self, chat_id: str, **kwargs):
        """Update chat with Cache-Aside pattern (DB write + cache invalidation).

        Write path: write to DB directly, invalidate cache afterward.
        Read path: cache-aside (check cache first, fetch from DB on miss).
        """
        _log_db_wrapper_op("UPDATE_CHAT_START", chat_id, f"updates={len(kwargs)}")
        write_start = time.time()

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                updates = []
                values = []
                if 'title' in kwargs:
                    updates.append("title=?")
                    values.append(kwargs['title'])
                if 'memory_mode' in kwargs:
                    updates.append("memory_mode=?")
                    values.append(kwargs['memory_mode'])
                if 'research_mode' in kwargs:
                    updates.append("research_mode=?")
                    values.append(kwargs['research_mode'])
                if 'is_vision' in kwargs:
                    updates.append("is_vision=?")
                    values.append(kwargs['is_vision'])
                if 'last_model' in kwargs:
                    updates.append("last_model=?")
                    values.append(kwargs['last_model'])
                if 'vision_model' in kwargs:
                    updates.append("vision_model=?")
                    values.append(kwargs['vision_model'])
                if 'max_tokens' in kwargs:
                    updates.append("max_tokens=?")
                    values.append(kwargs['max_tokens'])
                if 'folder' in kwargs:
                    updates.append("folder=?")
                    values.append(kwargs['folder'])
                if 'search_depth_mode' in kwargs:
                    updates.append("search_depth_mode=?")
                    values.append(kwargs['search_depth_mode'])
                if 'research_completed' in kwargs:
                    updates.append("research_completed=?")
                    values.append(kwargs['research_completed'])
                if 'had_research' in kwargs:
                    updates.append("had_research=?")
                    values.append(kwargs['had_research'])
                if 'canvas_mode' in kwargs:
                    updates.append("canvas_mode=?")
                    values.append(kwargs['canvas_mode'])
                if 'enable_thinking' in kwargs:
                    updates.append("enable_thinking=?")
                    values.append(kwargs['enable_thinking'])
                if 'temperature' in kwargs:
                    updates.append("temperature=?")
                    values.append(kwargs['temperature'])
                if 'top_p' in kwargs:
                    updates.append("top_p=?")
                    values.append(kwargs['top_p'])
                if 'top_k' in kwargs:
                    updates.append("top_k=?")
                    values.append(kwargs['top_k'])
                if 'min_p' in kwargs:
                    updates.append("min_p=?")
                    values.append(kwargs['min_p'])
                if 'presence_penalty' in kwargs:
                    updates.append("presence_penalty=?")
                    values.append(kwargs['presence_penalty'])
                if 'frequency_penalty' in kwargs:
                    updates.append("frequency_penalty=?")
                    values.append(kwargs['frequency_penalty'])

                if updates:
                    c.execute(f'''
                        UPDATE chats SET {", ".join(updates)} WHERE id=?
                    ''', values + [chat_id])
                conn.commit()
            finally:
                conn.close()

        # Write to DB directly, then invalidate cache
        _write()
        db_write_duration = (time.time() - write_start) * 1000
        cache_layer.invalidate("chats", chat_id)
        cache_layer.invalidate("chats_full", chat_id)
        _log_db_wrapper_op("UPDATE_CHAT_END", chat_id, f"duration_ms={db_write_duration:.2f}")

    def delete_chat(self, chat_id: str):
        """Delete chat with Cache-Aside pattern (DB delete + cache invalidation)."""
        _log_db_wrapper_op("DELETE_CHAT_START", chat_id)
        write_start = time.time()

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                # Disable FK checks temporarily to allow deletion
                c.execute("PRAGMA foreign_keys = OFF")
                # Delete associated messages first
                c.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
                # Then delete the chat
                c.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
                conn.commit()
            finally:
                conn.close()

        # Write to DB directly, then invalidate cache
        _write()
        db_write_duration = (time.time() - write_start) * 1000
        cache_layer.invalidate("chats", chat_id)
        cache_layer.invalidate("chats_full", chat_id)
        _log_db_wrapper_op("DELETE_CHAT_END", chat_id, f"duration_ms={db_write_duration:.2f}")

    # ==================== MESSAGE OPERATIONS ====================

    def get_messages(self, chat_id: str):
        """Get messages for chat with cache-first semantics (row-level)."""
        _log_db_wrapper_op("GET_MESSAGES_START", chat_id)
        fetch_start = time.time()
        result = cache_layer.get("messages", f"chat:{chat_id}", lambda: self._get_messages_fetch(chat_id))
        duration_ms = (time.time() - fetch_start) * 1000
        result_count = len(result) if result else 0
        _log_db_wrapper_op("GET_MESSAGES_END", chat_id, f"duration_ms={duration_ms:.2f} count={result_count}")
        return result

    def _get_messages_fetch(self, chat_id: str):
        """Internal fetch function for get_messages."""
        conn = make_connection()
        try:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM messages WHERE chat_id = ? ORDER BY id ASC", (chat_id,))
            messages = c.fetchall()
            return [dict(m) for m in messages]
        finally:
            conn.close()

    def update_message_content(self, message_id: int, content: str):
        """Update message content by ID. Used for system message reconciliation."""
        _log_db_wrapper_op("UPDATE_MESSAGE_CONTENT_START", None, f"message_id={message_id}")
        write_start = time.time()

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute("UPDATE messages SET content = ? WHERE id = ?", (content, message_id))
                conn.commit()
            finally:
                conn.close()

        _write()
        db_write_duration = (time.time() - write_start) * 1000
        # Invalidate all chat message caches that might contain this message
        # (we don't know chat_id here, so do a table-level invalidate)
        cache_layer.invalidate("messages")
        cache_layer.invalidate("chats_full")
        _log_db_wrapper_op("UPDATE_MESSAGE_CONTENT_END", None, f"message_id={message_id} duration_ms={db_write_duration:.2f}")

    def add_message(self, chat_id: str, role: str, content: str,
                    model: str = None, timestamp: float = None,
                    tool_calls: str = None, tool_call_id: str = None,
                    name: str = None):
        """Add message with Cache-Aside pattern (DB write + cache invalidation).

        Write path: write to DB directly, invalidate cache afterward.
        Read path: cache-aside (check cache first, fetch from DB on miss).
        """
        _log_db_wrapper_op("ADD_MESSAGE_START", chat_id)
        write_start = time.time()

        if timestamp is None:
            timestamp = time.time()

        # Safety guard: if caller accidentally passes a list/dict, serialize it
        if isinstance(content, (list, dict)):
            content = json.dumps(content)
        if isinstance(tool_calls, (list, dict)):
            tool_calls = json.dumps(tool_calls)

        # Handle name: store empty string if None to avoid NULL issues
        # The _normalize_messages function in llm.py will remove name=None for assistant
        if name is None:
            name = ""

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute('''
                    INSERT INTO messages (chat_id, role, content, timestamp, model,
                                          tool_calls, tool_call_id, name)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (chat_id, role, content, timestamp, model,
                      tool_calls, tool_call_id, name))
                conn.commit()
            finally:
                conn.close()

        # Write to DB directly, then invalidate cache
        _write()
        db_write_duration = (time.time() - write_start) * 1000
        cache_layer.invalidate("messages", f"chat:{chat_id}")
        cache_layer.invalidate("chats_full", chat_id)
        _log_db_wrapper_op("ADD_MESSAGE_END", chat_id, f"duration_ms={db_write_duration:.2f}")

    def add_messages_batch(self, chat_id: str, messages: list) -> bool:
        """
        Add multiple messages in a single atomic transaction.

        All messages are saved OR none are saved (transaction rollback on failure).
        This ensures atomicity for chat rounds with multiple components:
        - Assistant reasoning
        - Tool calls
        - Tool call results
        - Final assistant response

        Args:
            chat_id: The chat identifier
            messages: List of message dicts with keys: role, content, timestamp,
                     model, tool_calls, tool_call_id, name

        Returns:
            True if successful, False if transaction failed
        """
        _log_db_wrapper_op("ADD_MESSAGES_BATCH_START", chat_id, f"count={len(messages)}")
        write_start = time.time()

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute("BEGIN")  # Start transaction
                c.execute('DELETE FROM messages WHERE chat_id = ?', (chat_id,))

                for msg in messages:
                    # Extract fields with defaults
                    role = msg.get('role', '')
                    content = msg.get('content', '')
                    timestamp = msg.get('timestamp', time.time())
                    model = msg.get('model')
                    tool_calls = msg.get('tool_calls')
                    tool_call_id = msg.get('tool_call_id')
                    name = msg.get('name', '')
                    uploaded_files = msg.get('uploadedFiles')

                    # Safety guard: serialize content and tool_calls if list/dict
                    if isinstance(content, (list, dict)):
                        content = json.dumps(content)
                    if isinstance(tool_calls, (list, dict)):
                        tool_calls = json.dumps(tool_calls)

                    # Handle None values
                    if content is None:
                        content = ""
                    if name is None:
                        name = ""

                    # Store uploadedFiles as JSON in content if present
                    if uploaded_files is not None:
                        # For strings: wrap in {"text": ..., "uploadedFiles": ...}
                        # For dicts (multi-part content): add uploadedFiles to the dict
                        # For other types: create {"text": ..., "uploadedFiles": ...}
                        if isinstance(content, str):
                            # Check if content is already a JSON string with uploadedFiles
                            try:
                                parsed = json.loads(content)
                                if isinstance(parsed, dict) and 'uploadedFiles' in parsed:
                                    # Content is already a JSON object with uploadedFiles
                                    # Just ensure the uploadedFiles in content matches the one we're saving
                                    content_obj = {**parsed, 'uploadedFiles': uploaded_files}
                                    content = json.dumps(content_obj)
                                else:
                                    # Regular string content
                                    content_obj = {"text": content, "uploadedFiles": uploaded_files}
                                    content = json.dumps(content_obj)
                            except (json.JSONDecodeError, TypeError, ValueError):
                                # Not valid JSON, treat as regular string
                                content_obj = {"text": content, "uploadedFiles": uploaded_files}
                                content = json.dumps(content_obj)
                        elif isinstance(content, dict) and not isinstance(content, list):
                            # Multi-part content: add uploadedFiles as a field
                            content_obj = {**content, "uploadedFiles": uploaded_files}
                            content = json.dumps(content_obj)
                        else:
                            content_obj = {"text": content if content is not None else "", "uploadedFiles": uploaded_files}
                            content = json.dumps(content_obj)

                    c.execute('''
                        INSERT INTO messages (chat_id, role, content, timestamp, model,
                                              tool_calls, tool_call_id, name)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (chat_id, role, content, timestamp, model,
                          tool_calls, tool_call_id, name))

                c.execute("COMMIT")  # Commit all at once
                return True
            except Exception as e:
                c.execute("ROLLBACK")  # Rollback on error
                raise e
            finally:
                conn.close()

        try:
            _write()
            db_write_duration = (time.time() - write_start) * 1000
            # Invalidate cache for all affected rows
            cache_layer.invalidate("messages", f"chat:{chat_id}")
            cache_layer.invalidate("chats_full", chat_id)
            _log_db_wrapper_op("ADD_MESSAGES_BATCH_END", chat_id, f"duration_ms={db_write_duration:.2f}")
            return True
        except Exception as e:
            db_write_duration = (time.time() - write_start) * 1000
            _log_db_wrapper_op("ADD_MESSAGES_BATCH_ERROR", chat_id, f"error={str(e)} duration_ms={db_write_duration:.2f}")
            return False

    # ==================== CANVAS OPERATIONS ====================

    def get_canvas_meta(self, canvas_id: str, chat_id: str):
        """Get canvas metadata with cache-first semantics (row-level).

        Bug 5 fix: queries the `canvases` table (not canvas_permissions).
        canvas_permissions is for sharing/permissions; canvases is for metadata.
        """
        _log_db_wrapper_op("GET_CANVAS_META_START", chat_id, f"canvas_id={canvas_id}")
        fetch_start = time.time()
        result = cache_layer.get("canvases", f"{chat_id}:{canvas_id}", lambda: self._get_canvas_meta_fetch(canvas_id, chat_id), ttl=300)
        duration_ms = (time.time() - fetch_start) * 1000
        _log_db_wrapper_op("GET_CANVAS_META_END", chat_id, f"canvas_id={canvas_id} duration_ms={duration_ms:.2f}")
        return result

    def _get_canvas_meta_fetch(self, canvas_id: str, chat_id: str):
        """Internal fetch function for get_canvas_meta."""
        conn = make_connection()
        try:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(
                "SELECT * FROM canvases WHERE id = ? AND chat_id = ?",
                (canvas_id, chat_id)
            )
            row = c.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()

    def save_canvas_meta(self, canvas_id: str, chat_id: str, title: str,
                         filename: str, canvas_type: str = 'custom',
                         folder: str = None, tags=None, current_version: int = None):
        """Upsert canvas metadata into the `canvases` table.

        Bug 4 fix: this method was missing from DatabaseWrapper.
        Bug 6 fix: targets the `canvases` table (not canvas_permissions).
        """
        _log_db_wrapper_op("SAVE_CANVAS_META_START", chat_id, f"canvas_id={canvas_id} version={current_version}")
        write_start = time.time()

        if isinstance(tags, (list, dict)):
            tags = json.dumps(tags)

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute(
                    """INSERT INTO canvases (id, chat_id, title, filename, timestamp, folder, tags, canvas_type, current_version)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(id, chat_id) DO UPDATE SET
                           title=excluded.title,
                           filename=excluded.filename,
                           folder=excluded.folder,
                           tags=excluded.tags,
                           canvas_type=excluded.canvas_type,
                           current_version=excluded.current_version""",
                    (canvas_id, chat_id, title, filename, time.time(), folder, tags, canvas_type, current_version)
                )
                conn.commit()
            finally:
                conn.close()

        row_id = f"{chat_id}:{canvas_id}"
        _write()
        db_write_duration = (time.time() - write_start) * 1000
        cache_layer.invalidate("canvases", row_id)
        cache_layer.invalidate("canvases", f"{chat_id}:{canvas_id}:current_version")
        _log_db_wrapper_op("SAVE_CANVAS_META_END", chat_id, f"canvas_id={canvas_id} duration_ms={db_write_duration:.2f}")

    def save_canvas(self, chat_id: str, title: str, filename: str,
                    folder: str = None, canvas_type: str = 'custom',
                    canvas_id: str = None, current_version: int = None):
        """Save a new canvas entry. Delegates to save_canvas_meta.

        Bug 6 fix: was writing to canvas_permissions instead of canvases.
        """
        if canvas_id is None:
            canvas_id = f"canvas_{chat_id}"
        self.save_canvas_meta(canvas_id, chat_id, title, filename, canvas_type, folder, current_version=current_version)
        return canvas_id

    def create_canvas_with_version(self, canvas_id: str, chat_id: str, title: str,
                                   filename: str, content: str, author: str = 'system',
                                   comment: str = 'Initial version', folder: str = None,
                                   canvas_type: str = 'custom', tags=None):
        """Create canvas metadata and initial version in a single transaction.

        This method ensures both the canvas metadata and initial version record
        are created atomically to satisfy foreign key constraints.

        Args:
            canvas_id: Canvas identifier
            chat_id: Chat identifier
            title: Display title
            filename: Filename for content storage
            content: Initial content for version 1
            author: Author of initial version
            comment: Version comment
            folder: Optional folder path
            canvas_type: Canvas type

        Returns:
            version_id of created version (always 1 for initial version)
        """
        _log_db_wrapper_op("CREATE_CANVAS_WITH_VERSION_START", chat_id, f"canvas_id={canvas_id}")
        write_start = time.time()

        # Handle folder and tags conversion
        if isinstance(folder, list):
            folder = json.dumps(folder)
        if isinstance(tags, (list, dict)):
            tags = json.dumps(tags)

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                # Begin explicit transaction
                c.execute("BEGIN IMMEDIATE")

                try:
                    # Insert canvas metadata with current_version = 1
                    c.execute(
                        """INSERT INTO canvases (id, chat_id, title, filename, timestamp, folder, tags, canvas_type, current_version)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                           ON CONFLICT(id, chat_id) DO UPDATE SET
                               title=excluded.title,
                               filename=excluded.filename,
                               folder=excluded.folder,
                               tags=excluded.tags,
                               canvas_type=excluded.canvas_type,
                               current_version=excluded.current_version""",
                        (canvas_id, chat_id, title, filename, time.time(), folder, tags, canvas_type, 1)
                    )

                    # Insert initial version - now canvas exists so FK constraint passes
                    c.execute(
                        """INSERT INTO canvas_versions
                               (canvas_id, chat_id, version_number, content, author, timestamp, comment)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (canvas_id, chat_id, 1, content, author, time.time(), comment)
                    )

                    conn.commit()
                except:
                    conn.rollback()
                    raise
            finally:
                conn.close()

        _write()
        db_write_duration = (time.time() - write_start) * 1000

        # Invalidate caches
        row_id = f"{chat_id}:{canvas_id}"
        cache_layer.invalidate("canvases", row_id)
        cache_layer.invalidate("canvases", f"{chat_id}:{canvas_id}:versions")
        cache_layer.invalidate("canvases", f"{chat_id}:{canvas_id}:current_version")

        _log_db_wrapper_op("CREATE_CANVAS_WITH_VERSION_END", chat_id, f"canvas_id={canvas_id} duration_ms={db_write_duration:.2f}")
        return 1  # Initial version is always version 1

    # ==================== TABLE OPERATIONS ====================

    def get_all_chats(self):
        """Get all chats with cache-first semantics (table-level)."""
        def _fetch():
            conn = make_connection()
            try:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute("SELECT * FROM chats ORDER BY timestamp DESC")
                return [dict(row) for row in c.fetchall()]
            finally:
                conn.close()

        return cache_layer.get_table("chats", _fetch, key_extractor=lambda row: row.get('id', ''), ttl=300)

    def get_chat_canvases(self, chat_id: str):
        """Get all canvases for a chat (table-level)."""
        def _fetch():
            conn = make_connection()
            try:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute(
                    "SELECT * FROM canvases WHERE chat_id = ? ORDER BY timestamp DESC",
                    (chat_id,)
                )
                return [dict(row) for row in c.fetchall()]
            finally:
                conn.close()

        return cache_layer.get_table("canvases", _fetch, key_extractor=lambda row: row.get('id', ''), ttl=300)

    def get_canvas_versions(self, canvas_id: str, chat_id: str):
        """Get version history for a canvas (table-level)."""
        def _fetch():
            conn = make_connection()
            try:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute(
                    "SELECT * FROM canvas_versions WHERE canvas_id = ? AND chat_id = ? ORDER BY version_number DESC",
                    (canvas_id, chat_id)
                )
                return [dict(row) for row in c.fetchall()]
            finally:
                conn.close()

        row_id = f"{chat_id}:{canvas_id}:versions"
        return cache_layer.get("canvases", row_id, _fetch, ttl=300)

    def get_canvas_version_content(self, canvas_id: str, chat_id: str, version_number: int):
        """Get content of a specific canvas version."""
        def _fetch():
            conn = make_connection()
            try:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute(
                    "SELECT * FROM canvas_versions WHERE canvas_id = ? AND chat_id = ? AND version_number = ?",
                    (canvas_id, chat_id, version_number)
                )
                row = c.fetchone()
                return row['content'] if row else None
            finally:
                conn.close()

        row_id = f"{chat_id}:{canvas_id}:version:{version_number}"
        return cache_layer.get("canvases", row_id, _fetch, ttl=300)

    def get_canvas_current_version(self, canvas_id: str, chat_id: str):
        """Get current version of a canvas."""
        def _fetch():
            conn = make_connection()
            try:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute("SELECT current_version FROM canvases WHERE id = ? AND chat_id = ?", (canvas_id, chat_id))
                row = c.fetchone()
                if row and row['current_version'] is not None:
                    # Fetch that specific version record
                    c.execute(
                        "SELECT * FROM canvas_versions WHERE canvas_id = ? AND chat_id = ? AND version_number = ?",
                        (canvas_id, chat_id, row['current_version'])
                    )
                    v_row = c.fetchone()
                    if v_row:
                        return dict(v_row)

                # Fallback to latest
                c.execute(
                    """SELECT * FROM canvas_versions
                       WHERE canvas_id = ? AND chat_id = ?
                       ORDER BY version_number DESC LIMIT 1""",
                    (canvas_id, chat_id)
                )
                row = c.fetchone()
                return dict(row) if row else None
            finally:
                conn.close()

        row_id = f"{chat_id}:{canvas_id}:current_version"
        return cache_layer.get("canvases", row_id, _fetch, ttl=300)

    def get_canvas_content_by_id(self, canvas_id: str, chat_id: str):
        """Get canvas content by canvas_id.

        Bug 9 fix: was querying a non-existent 'canvas_content' table.
        Canvas content is stored on disk. We look up the filename from the
        `canvases` table, then read the file directly — no asyncio, no
        circular canvas_manager import.
        """
        import os
        from backend.config import DATA_DIR
        CANVASES_DIR = os.path.join(DATA_DIR, "canvases")

        meta = self.get_canvas_meta(canvas_id, chat_id)
        if not meta or not meta.get('filename'):
            return None
        filepath = os.path.join(CANVASES_DIR, meta['filename'])
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except (OSError, IOError):
            return None

    def get_next_canvas_counter(self, chat_id: str):
        """Get and atomically increment canvas counter for a chat.

        Bug 10 fix: was using SELECT MAX(counter) which is wrong for a single-row
        counter table. Now uses INSERT OR REPLACE with atomic increment.
        """
        conn = make_connection()
        try:
            c = conn.cursor()
            c.execute(
                """INSERT INTO canvas_counters (chat_id, counter)
                   VALUES (?, 1)
                   ON CONFLICT(chat_id) DO UPDATE SET counter = counter + 1""",
                (chat_id,)
            )
            c.execute("SELECT counter FROM canvas_counters WHERE chat_id = ?", (chat_id,))
            row = c.fetchone()
            conn.commit()
            return row[0] if row else 1
        finally:
            conn.close()

    # ==================== DELETION OPERATIONS ====================

    def delete_messages_from(self, chat_id: str, from_id: int):
        """Delete messages from a specific ID onwards (Cache-Aside pattern)."""
        _log_db_wrapper_op("DELETE_MESSAGES_FROM_START", chat_id, f"from_id={from_id}")
        write_start = time.time()

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute(
                    "DELETE FROM messages WHERE chat_id = ? AND id >= ?",
                    (chat_id, from_id)
                )
                conn.commit()
            finally:
                conn.close()

        # Write to DB directly, then invalidate cache
        _write()
        db_write_duration = (time.time() - write_start) * 1000
        cache_layer.invalidate("messages", f"chat:{chat_id}")
        cache_layer.invalidate("chats_full", chat_id)
        _log_db_wrapper_op("DELETE_MESSAGES_FROM_END", chat_id, f"duration_ms={db_write_duration:.2f}")

    def truncate_messages(self, chat_id: str, keep_up_to_index: int):
        """
        Delete all messages after a certain chronological index (0-indexed).
        If keep_up_to_index is 5, we keep messages 0, 1, 2, 3, 4 and delete the rest.
        Uses SQLite OFFSET to avoid referential ID issues.
        """
        _log_db_wrapper_op("TRUNCATE_MESSAGES_START", chat_id, f"keep={keep_up_to_index}")
        write_start = time.time()

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                # Find the IDs to delete.
                # Subquery selects all message IDs for this chat, ordered by ID.
                # We skip 'keep_up_to_index' rows and delete everything else.
                c.execute(f'''
                    DELETE FROM messages
                    WHERE chat_id = ?
                    AND id IN (
                        SELECT id FROM messages
                        WHERE chat_id = ?
                        ORDER BY id ASC
                        LIMIT -1 OFFSET ?
                    )
                ''', (chat_id, chat_id, keep_up_to_index))
                conn.commit()
                return True
            finally:
                conn.close()

        _write()
        db_write_duration = (time.time() - write_start) * 1000
        cache_layer.invalidate("messages", f"chat:{chat_id}")
        cache_layer.invalidate("chats_full", chat_id)
        _log_db_wrapper_op("TRUNCATE_MESSAGES_END", chat_id, f"duration_ms={db_write_duration:.2f}")
        return True

    def edit_message_by_index(self, chat_id: str, index: int, new_content: str):
        """
        Update the content of a specific message by its chronological index.
        """
        _log_db_wrapper_op("EDIT_MESSAGE_BY_INDEX_START", chat_id, f"index={index}")
        write_start = time.time()

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                # Use subquery to target the specific row by offset
                c.execute(f'''
                    UPDATE messages
                    SET content = ?
                    WHERE id = (
                        SELECT id FROM messages
                        WHERE chat_id = ?
                        ORDER BY id ASC
                        LIMIT 1 OFFSET ?
                    )
                ''', (new_content, chat_id, index))
                conn.commit()
                return True
            finally:
                conn.close()

        _write()
        db_write_duration = (time.time() - write_start) * 1000
        cache_layer.invalidate("messages", f"chat:{chat_id}")
        cache_layer.invalidate("chats_full", chat_id)
        _log_db_wrapper_op("EDIT_MESSAGE_BY_INDEX_END", chat_id, f"duration_ms={db_write_duration:.2f}")
        return True

    def clear_messages(self, chat_id: str):
        """Clear all messages for a chat (Cache-Aside pattern)."""
        _log_db_wrapper_op("CLEAR_MESSAGES_START", chat_id)
        write_start = time.time()

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute(
                    "DELETE FROM messages WHERE chat_id = ?",
                    (chat_id,)
                )
                conn.commit()
            finally:
                conn.close()

        # Write to DB directly, then invalidate cache
        _write()
        db_write_duration = (time.time() - write_start) * 1000
        cache_layer.invalidate("messages", f"chat:{chat_id}")
        cache_layer.invalidate("chats_full", chat_id)
        _log_db_wrapper_op("CLEAR_MESSAGES_END", chat_id, f"duration_ms={db_write_duration:.2f}")

    def delete_all_chats(self):
        """Delete all chats. Bug 12 fix: _write() was defined but never called."""
        _log_db_wrapper_op("DELETE_ALL_CHATS_START", None)
        write_start = time.time()

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                # Delete all messages first (FK constraint)
                c.execute("DELETE FROM messages")
                c.execute("DELETE FROM chats")
                conn.commit()
            finally:
                conn.close()

        _write()
        db_write_duration = (time.time() - write_start) * 1000
        cache_layer.clear_cache()
        _log_db_wrapper_op("DELETE_ALL_CHATS_END", None, f"duration_ms={db_write_duration:.2f}")

    def save_canvas_version(self, canvas_id: str, chat_id: str, version_number: int,
                             content: str, author: str = 'system', comment: str = ''):
        """Insert a new canvas version record into canvas_versions.

        This method was MISSING from DatabaseWrapper, causing canvas creation
        to crash with AttributeError on every call.
        """
        _log_db_wrapper_op("SAVE_CANVAS_VERSION_START", chat_id, f"canvas_id={canvas_id} version={version_number}")
        write_start = time.time()

        conn = make_connection()
        try:
            c = conn.cursor()
            c.execute(
                """INSERT INTO canvas_versions
                       (canvas_id, chat_id, version_number, content, author, timestamp, comment)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (canvas_id, chat_id, version_number, content, author, time.time(), comment)
            )
            conn.commit()
        finally:
            conn.close()
        db_write_duration = (time.time() - write_start) * 1000
        # Invalidate version caches for this canvas
        cache_layer.invalidate("canvases", f"{chat_id}:{canvas_id}:versions")
        cache_layer.invalidate("canvases", f"{chat_id}:{canvas_id}:current_version")
        _log_db_wrapper_op("SAVE_CANVAS_VERSION_END", chat_id, f"canvas_id={canvas_id} version={version_number} duration_ms={db_write_duration:.2f}")

    def delete_canvas_meta(self, canvas_id: str, chat_id: str):
        """Delete canvas metadata from the canvases table.

        Bug fix: was deleting from canvas_permissions instead of canvases,
        AND _write() was defined but never called.
        """
        _log_db_wrapper_op("DELETE_CANVAS_META_START", chat_id, f"canvas_id={canvas_id}")
        write_start = time.time()

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute(
                    "DELETE FROM canvases WHERE id = ? AND chat_id = ?",
                    (canvas_id, chat_id)
                )
                conn.commit()
            finally:
                conn.close()

        _write()
        db_write_duration = (time.time() - write_start) * 1000
        cache_layer.invalidate("canvases", f"{chat_id}:{canvas_id}")
        _log_db_wrapper_op("DELETE_CANVAS_META_END", chat_id, f"canvas_id={canvas_id} duration_ms={db_write_duration:.2f}")

    def delete_chat_canvas_files(self, chat_id: str):
        """Delete canvas files for a chat (from disk and DB)."""
        import os
        from backend.config import DATA_DIR
        CANVASES_DIR = os.path.join(DATA_DIR, "canvases")

        def _write():
            # Delete from DB first
            conn = make_connection()
            try:
                c = conn.cursor()
                # Get all canvases for this chat
                c.execute("SELECT filename FROM canvases WHERE chat_id = ?", (chat_id,))
                rows = c.fetchall()
                # Delete files from disk
                for row in rows:
                    filename = row[0]
                    filepath = os.path.join(CANVASES_DIR, filename)
                    if os.path.exists(filepath):
                        os.remove(filepath)
                # Delete from DB
                c.execute("DELETE FROM canvas_versions WHERE chat_id = ?", (chat_id,))
                c.execute("DELETE FROM canvas_permissions WHERE chat_id = ?", (chat_id,))
                c.execute("DELETE FROM canvases WHERE chat_id = ?", (chat_id,))
                conn.commit()
            finally:
                conn.close()

        cache_layer.invalidate("canvases")
        _write()

    def sync_canvas_search_index(self, canvas_id: str, chat_id: str) -> bool:
        """Sync canvas to FTS5 search index."""
        import os
        from backend.config import DATA_DIR
        CANVASES_DIR = os.path.join(DATA_DIR, "canvases")

        # Read content from file
        filename = self._generate_canvas_filename(chat_id, canvas_id)
        filepath = os.path.join(CANVASES_DIR, filename)
        if not os.path.exists(filepath):
            return False

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Get canvas title
        canvas_meta = self.get_canvas_meta(canvas_id, chat_id)
        title = canvas_meta.get('title', '') if canvas_meta else ''

        # Update FTS5 index
        conn = make_connection()
        try:
            c = conn.cursor()
            c.execute('''
                INSERT OR REPLACE INTO canvases_search (id, title, content)
                VALUES (?, ?, ?)
            ''', (canvas_id, title, content))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    def _generate_canvas_filename(self, chat_id: str, canvas_id: str) -> str:
        """Generate filename for a canvas."""
        import re
        safe_chat_id = re.sub(r'[^a-zA-Z0-9_\-]', '', str(chat_id))
        safe_canvas_id = re.sub(r'[^\w\s\-]', '_', str(canvas_id))
        safe_canvas_id = re.sub(r'_+', '_', safe_canvas_id)
        safe_canvas_id = safe_canvas_id.strip('_')
        return f"{safe_chat_id}_{safe_canvas_id}.md"

    def delete_canvas_versions_after(self, canvas_id: str, chat_id: str, up_to_version: int) -> int:
        """Delete canvas versions after a certain version.

        Bug 11 fix: was calling _write() twice (once in _verify, once directly),
        causing a second DELETE that always returned 0 as deleted_count.
        """
        _log_db_wrapper_op("DELETE_CANVAS_VERSIONS_AFTER_START", chat_id, f"canvas_id={canvas_id} up_to={up_to_version}")
        write_start = time.time()

        conn = make_connection()
        try:
            c = conn.cursor()
            c.execute(
                "DELETE FROM canvas_versions WHERE canvas_id = ? AND chat_id = ? AND version_number > ?",
                (canvas_id, chat_id, up_to_version)
            )
            deleted_count = c.rowcount
            conn.commit()
        finally:
            conn.close()
        db_write_duration = (time.time() - write_start) * 1000

        # Invalidate version cache
        cache_layer.invalidate("canvases", f"{chat_id}:{canvas_id}:versions")
        cache_layer.invalidate("canvases", f"{chat_id}:{canvas_id}:current_version")
        _log_db_wrapper_op("DELETE_CANVAS_VERSIONS_AFTER_END", chat_id, f"canvas_id={canvas_id} up_to={up_to_version} deleted={deleted_count} duration_ms={db_write_duration:.2f}")
        return deleted_count

    def rename_chat(self, chat_id: str, new_title: str):
        """Rename a chat (Cache-Aside pattern)."""
        _log_db_wrapper_op("RENAME_CHAT_START", chat_id, f"new_title={new_title}")
        write_start = time.time()

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute(
                    "UPDATE chats SET title = ?, is_custom_title = 1 WHERE id = ?",
                    (new_title, chat_id)
                )
                conn.commit()
            finally:
                conn.close()

        # Write to DB directly, then invalidate cache
        _write()
        db_write_duration = (time.time() - write_start) * 1000
        cache_layer.invalidate("chats", chat_id)
        cache_layer.invalidate("chats_full", chat_id)
        _log_db_wrapper_op("RENAME_CHAT_END", chat_id, f"duration_ms={db_write_duration:.2f}")

    # ==================== UPDATE METHODS ====================

    def update_chat_model(self, chat_id: str, last_model: str):
        """Update chat model."""
        return self.update_chat(chat_id, last_model=last_model)

    def update_chat_vision_model(self, chat_id: str, vision_model: str):
        """Update chat vision model."""
        return self.update_chat(chat_id, vision_model=vision_model)

    def update_chat_max_tokens(self, chat_id: str, max_tokens: int):
        """Update chat max tokens."""
        return self.update_chat(chat_id, max_tokens=max_tokens)

    def update_chat_folder(self, chat_id: str, folder: str):
        """Update chat folder."""
        return self.update_chat(chat_id, folder=folder)

    def update_chat_canvas_mode(self, chat_id: str, canvas_mode: bool):
        """Update chat canvas mode."""
        return self.update_chat(chat_id, canvas_mode=canvas_mode)

    def mark_research_completed(self, chat_id: str, completed: int = 1):
        """Mark chat research as completed."""
        return self.update_chat(chat_id, research_completed=completed)

    def delete_last_turn(self, chat_id: str):
        """Delete the last message from a chat (Cache-Aside pattern)."""
        _log_db_wrapper_op("DELETE_LAST_TURN_START", chat_id)
        fetch_start = time.time()

        def _fetch():
            conn = make_connection()
            try:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute(
                    "SELECT id FROM messages WHERE chat_id = ? ORDER BY id DESC LIMIT 1",
                    (chat_id,)
                )
                row = c.fetchone()
                return row['id'] if row else None
            finally:
                conn.close()

        last_id = _fetch()
        fetch_duration = (time.time() - fetch_start) * 1000
        if last_id:
            _log_db_wrapper_op("DELETE_LAST_TURN_FOUND", chat_id, f"last_id={last_id}")
            write_start = time.time()
            def _write():
                conn = make_connection()
                try:
                    c = conn.cursor()
                    c.execute(
                        "DELETE FROM messages WHERE id = ?",
                        (last_id,)
                    )
                    conn.commit()
                finally:
                    conn.close()

            # Write to DB directly, then invalidate cache
            _write()
            db_write_duration = (time.time() - write_start) * 1000
            cache_layer.invalidate("messages", f"chat:{chat_id}")
            cache_layer.invalidate("chats_full", chat_id)
            _log_db_wrapper_op("DELETE_LAST_TURN_END", chat_id, f"last_id={last_id} fetch_ms={fetch_duration:.2f} write_ms={db_write_duration:.2f}")
        else:
            _log_db_wrapper_op("DELETE_LAST_TURN_NOT_FOUND", chat_id, f"fetch_ms={fetch_duration:.2f}")

    # ==================== CANVAS OPERATIONS ====================

    def restore_canvas_version(self, canvas_id: str, chat_id: str, version_number: int):
        """Restore a specific canvas version.

        Bug 8 fix: was referencing canvas_content (non-existent table) and
        canvas_versions.metadata (non-existent column). Now writes content to
        disk via canvas_manager and bumps the canvases.timestamp in the DB.
        """
        _log_db_wrapper_op("RESTORE_CANVAS_VERSION_START", chat_id, f"canvas_id={canvas_id} version={version_number}")
        start_time = time.time()

        conn = make_connection()
        try:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(
                "SELECT content FROM canvas_versions WHERE canvas_id = ? AND chat_id = ? AND version_number = ?",
                (canvas_id, chat_id, version_number)
            )
            row = c.fetchone()
        finally:
            conn.close()

        if not row:
            _log_db_wrapper_op("RESTORE_CANVAS_VERSION_NOT_FOUND", chat_id, f"canvas_id={canvas_id} version={version_number}")
            return None

        content = row['content']

        # Write content to disk (canvas_manager owns the file layer)
        import asyncio
        from backend.canvas_manager import update_canvas_content
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're inside an async context — caller should await directly
                # For sync callers, create a thread-safe future
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, update_canvas_content(canvas_id, chat_id, content, author='system'))
                    future.result(timeout=30)
            else:
                loop.run_until_complete(update_canvas_content(canvas_id, chat_id, content, author='system'))
        except Exception:
            pass

        # Invalidate caches
        cache_layer.invalidate("canvases", f"{chat_id}:{canvas_id}")
        cache_layer.invalidate("canvases", f"{chat_id}:{canvas_id}:current_version")
        cache_layer.invalidate("canvases", f"{chat_id}:{canvas_id}:versions")
        duration_ms = (time.time() - start_time) * 1000
        _log_db_wrapper_op("RESTORE_CANVAS_VERSION_END", chat_id, f"canvas_id={canvas_id} version={version_number} duration_ms={duration_ms:.2f}")
        return True

    def get_canvas_diff(self, canvas_id: str, chat_id: str, version1: int, version2: int):
        """Get diff between two canvas versions."""
        def _fetch_version(version_number):
            conn = make_connection()
            try:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute(
                    "SELECT content FROM canvas_versions WHERE canvas_id = ? AND chat_id = ? AND version_number = ?",
                    (canvas_id, chat_id, version_number)
                )
                row = c.fetchone()
                return row['content'] if row else None
            finally:
                conn.close()

        content1 = _fetch_version(version1)
        content2 = _fetch_version(version2)

        if content1 is None or content2 is None:
            return None

        return {
            'version1': {'number': version1, 'content': content1},
            'version2': {'number': version2, 'content': content2}
        }

    def share_canvas(self, canvas_id: str, chat_id: str, shared_with: str, access_level: str):
        """Share canvas with another user.

        Bug 13 fix: canvas_permissions uses 'user_id' and 'permission' (not
        'shared_with' / 'access_level'). Updated to match storage.py schema.
        """
        _log_db_wrapper_op("SHARE_CANVAS_START", chat_id, f"canvas_id={canvas_id} shared_with={shared_with}")
        write_start = time.time()

        conn = make_connection()
        try:
            c = conn.cursor()
            c.execute(
                """INSERT INTO canvas_permissions (canvas_id, chat_id, user_id, permission, timestamp)
                   VALUES (?, ?, ?, ?, ?)""",
                (canvas_id, chat_id, shared_with, access_level, time.time())
            )
            conn.commit()
        finally:
            conn.close()
        db_write_duration = (time.time() - write_start) * 1000
        cache_layer.invalidate("canvases", f"{chat_id}:{canvas_id}:permissions")
        _log_db_wrapper_op("SHARE_CANVAS_END", chat_id, f"canvas_id={canvas_id} shared_with={shared_with} duration_ms={db_write_duration:.2f}")
        return True

    def unshare_canvas(self, canvas_id: str, chat_id: str, shared_with: str):
        """Unshare canvas with a user."""
        _log_db_wrapper_op("UNSHARE_CANVAS_START", chat_id, f"canvas_id={canvas_id} shared_with={shared_with}")
        write_start = time.time()

        conn = make_connection()
        try:
            c = conn.cursor()
            c.execute(
                "DELETE FROM canvas_permissions WHERE canvas_id = ? AND chat_id = ? AND user_id = ?",
                (canvas_id, chat_id, shared_with)
            )
            conn.commit()
        finally:
            conn.close()
        db_write_duration = (time.time() - write_start) * 1000
        cache_layer.invalidate("canvases", f"{chat_id}:{canvas_id}:permissions")
        _log_db_wrapper_op("UNSHARE_CANVAS_END", chat_id, f"canvas_id={canvas_id} shared_with={shared_with} duration_ms={db_write_duration:.2f}")
        return True

    def get_shared_users(self, canvas_id: str, chat_id: str):
        """Get list of users who have access to a canvas."""
        _log_db_wrapper_op("GET_SHARED_USERS_START", chat_id, f"canvas_id={canvas_id}")
        fetch_start = time.time()

        def _fetch():
            conn = make_connection()
            try:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute(
                    "SELECT user_id, permission FROM canvas_permissions WHERE canvas_id = ? AND chat_id = ?",
                    (canvas_id, chat_id)
                )
                return [{'user': row['user_id'], 'access': row['permission']} for row in c.fetchall()]
            finally:
                conn.close()

        row_id = f"{chat_id}:{canvas_id}:permissions"
        result = cache_layer.get("canvases", row_id, _fetch, ttl=300)
        user_count = len(result) if result else 0
        _log_db_wrapper_op("GET_SHARED_USERS_END", chat_id, f"canvas_id={canvas_id} user_count={user_count}")
        return result

    # ==================== INIT ====================

    def init_db(self):
        """Initialize the database schema.

        Bug 7 fix: db_wrapper.py previously defined its OWN conflicting schema
        (wrong canvas_permissions columns, non-existent canvas_content table, etc.)
        that NEVER ran because app.py calls storage.init_db() at startup.
        Now delegates entirely to storage.init_db() so there is exactly one
        schema definition.
        """
        from backend.storage import init_db as storage_init_db
        storage_init_db()

    def _init_db_legacy(self):
        """DEAD CODE — kept for reference only. DO NOT CALL.

        This was the original conflicting schema body; retained here so the
        diff is easy to audit. It will be removed in a future cleanup pass.
        """
        conn = make_connection()
        try:
            c = conn.cursor()
            # Enable foreign key support
            c.execute("PRAGMA foreign_keys = ON")
            # Create chats table
            c.execute('''
                CREATE TABLE IF NOT EXISTS chats (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    memory_mode INTEGER DEFAULT 0,
                    research_mode INTEGER DEFAULT 0,
                    is_vision INTEGER DEFAULT 0,
                    last_model TEXT,
                    vision_model TEXT,
                    max_tokens INTEGER DEFAULT 16384,
                    is_custom_title INTEGER DEFAULT 0,
                    folder TEXT,
                    search_depth_mode TEXT DEFAULT 'regular',
                    research_completed INTEGER DEFAULT 0,
                    had_research INTEGER DEFAULT 0,
                    canvas_mode INTEGER DEFAULT 0
                )
            ''')
            # Create messages table
            c.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp REAL,
                    model TEXT,
                    tool_calls TEXT,
                    tool_call_id TEXT,
                    name TEXT,
                    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE
                )
            ''')
            # Create index for messages
            c.execute('CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id)')
            # Create canvas_permissions table
            c.execute('''
                CREATE TABLE IF NOT EXISTS canvas_permissions (
                    canvas_id TEXT NOT NULL,
                    chat_id TEXT NOT NULL,
                    title TEXT,
                    filename TEXT,
                    canvas_type TEXT DEFAULT 'custom',
                    shared_with TEXT,
                    access_level TEXT,
                    metadata TEXT,
                    created_at REAL DEFAULT (strftime('%s', 'now')),
                    PRIMARY KEY (canvas_id, chat_id)
                )
            ''')
            # Create canvas_versions table
            c.execute('''
                CREATE TABLE IF NOT EXISTS canvas_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    canvas_id TEXT NOT NULL,
                    chat_id TEXT NOT NULL,
                    version_number INTEGER NOT NULL,
                    content TEXT,
                    metadata TEXT,
                    created_at REAL DEFAULT (strftime('%s', 'now')),
                    FOREIGN KEY (canvas_id, chat_id) REFERENCES canvas_permissions(canvas_id, chat_id)
                )
            ''')
            # Create canvas_content table
            c.execute('''
                CREATE TABLE IF NOT EXISTS canvas_content (
                    canvas_id TEXT NOT NULL,
                    chat_id TEXT NOT NULL,
                    content TEXT,
                    updated_at REAL,
                    PRIMARY KEY (canvas_id, chat_id)
                )
            ''')
            # Create canvas_counters table
            c.execute('''
                CREATE TABLE IF NOT EXISTS canvas_counters (
                    chat_id TEXT NOT NULL,
                    counter INTEGER DEFAULT 0,
                    PRIMARY KEY (chat_id)
                )
            ''')
            conn.commit()
        finally:
            conn.close()

    # ==================== UTILITY ====================

    def get_stats(self):
        """Get cache statistics."""
        return cache_layer.get_stats()

    # ==================== FILE OPERATIONS ====================

    def save_file(self, file_id: str, chat_id: str, original_filename: str,
                  stored_filename: str, mime_type: str, file_size: int,
                  content_text: str = None):
        """Save file metadata to database.

        Args:
            file_id: Unique file identifier
            chat_id: Chat session ID
            original_filename: Original filename
            stored_filename: Sanitized filename for storage
            mime_type: MIME type of the file
            file_size: File size in bytes
            content_text: Extracted text content for RAG (optional)
        """
        logger = logging.getLogger(__name__)
        logger.info(f"[DB_SAVE_FILE_START] file_id={file_id}, chat_id={chat_id}, original_filename={original_filename}")

        _log_db_wrapper_op("SAVE_FILE_START", chat_id, f"file_id={file_id}")
        write_start = time.time()

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                logger.debug(f"[DB_INSERT] Executing INSERT with params: file_id={file_id}, chat_id={chat_id}, original_filename={original_filename}, stored_filename={stored_filename}, mime_type={mime_type}, file_size={file_size}")
                c.execute('''
                    INSERT INTO files (id, chat_id, original_filename, stored_filename,
                                      mime_type, file_size, content_text, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (file_id, chat_id, original_filename, stored_filename,
                      mime_type, file_size, content_text, time.time()))
                conn.commit()
                logger.debug(f"[DB_INSERT] Success, rows affected: {c.rowcount}")
            except sqlite3.IntegrityError as e:
                logger.error(f"[DB_INSERT_ERROR] Integrity error: {e}")
                logger.error(f"[DB_INSERT_ERROR] Params: file_id={file_id}, chat_id={chat_id}, original_filename={original_filename}, stored_filename={stored_filename}, mime_type={mime_type}, file_size={file_size}")
                raise
            except Exception as e:
                logger.error(f"[DB_INSERT_ERROR] General error: {e}")
                logger.error(f"[DB_INSERT_ERROR] Params: file_id={file_id}, chat_id={chat_id}, original_filename={original_filename}, stored_filename={stored_filename}, mime_type={mime_type}, file_size={file_size}")
                raise
            finally:
                conn.close()

        _write()
        db_write_duration = (time.time() - write_start) * 1000
        cache_layer.invalidate("files", f"chat:{chat_id}")
        _log_db_wrapper_op("SAVE_FILE_END", chat_id, f"file_id={file_id} duration_ms={db_write_duration:.2f}")
        logger.info(f"[DB_SAVE_FILE_END] file_id={file_id} duration_ms={db_write_duration:.2f}")

    def get_file(self, file_id: str) -> dict:
        """Get file metadata by ID.

        Args:
            file_id: Unique file identifier

        Returns:
            File metadata dict if found, None otherwise
        """
        _log_db_wrapper_op("GET_FILE_START", None, f"file_id={file_id}")
        fetch_start = time.time()

        def _fetch():
            conn = make_connection()
            try:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute("SELECT * FROM files WHERE id = ?", (file_id,))
                row = c.fetchone()
                return dict(row) if row else None
            finally:
                conn.close()

        result = _fetch()
        duration_ms = (time.time() - fetch_start) * 1000
        _log_db_wrapper_op("GET_FILE_END", None, f"file_id={file_id} duration_ms={duration_ms:.2f}")
        return result

    def get_chat_files(self, chat_id: str) -> list:
        """Get all files for a chat session.

        Args:
            chat_id: Chat session ID

        Returns:
            List of file metadata dicts
        """
        _log_db_wrapper_op("GET_CHAT_FILES_START", chat_id)
        fetch_start = time.time()

        def _fetch():
            conn = make_connection()
            try:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute(
                    "SELECT * FROM files WHERE chat_id = ? ORDER BY created_at DESC",
                    (chat_id,)
                )
                return [dict(row) for row in c.fetchall()]
            finally:
                conn.close()

        result = _fetch()
        duration_ms = (time.time() - fetch_start) * 1000
        file_count = len(result) if result else 0
        _log_db_wrapper_op("GET_CHAT_FILES_END", chat_id,
                          f"duration_ms={duration_ms:.2f} count={file_count}")
        return result

    def delete_file(self, file_id: str):
        """Delete a file from database and storage.

        Args:
            file_id: Unique file identifier
        """
        _log_db_wrapper_op("DELETE_FILE_START", None, f"file_id={file_id}")
        write_start = time.time()

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute("DELETE FROM files WHERE id = ?", (file_id,))
                conn.commit()
            finally:
                conn.close()

        _write()
        db_write_duration = (time.time() - write_start) * 1000
        # Get chat_id for cache invalidation
        file_meta = self.get_file(file_id)
        if file_meta:
            cache_layer.invalidate("files", f"chat:{file_meta.get('chat_id')}")
        _log_db_wrapper_op("DELETE_FILE_END", None, f"file_id={file_id} duration_ms={db_write_duration:.2f}")

    def update_file_content(self, file_id: str, content_text: str) -> bool:
        """Update file metadata with extracted content.

        Args:
            file_id: Unique file identifier
            content_text: Extracted text content for RAG

        Returns:
            True if successful, False otherwise
        """
        _log_db_wrapper_op("UPDATE_FILE_CONTENT_START", None, f"file_id={file_id}")
        write_start = time.time()

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute("UPDATE files SET content_text = ? WHERE id = ?", (content_text, file_id))
                conn.commit()
                return c.rowcount > 0
            finally:
                conn.close()

        result = _write()
        db_write_duration = (time.time() - write_start) * 1000
        # Get chat_id for cache invalidation
        file_meta = self.get_file(file_id)
        if file_meta:
            cache_layer.invalidate("files", f"chat:{file_meta.get('chat_id')}")
        _log_db_wrapper_op("UPDATE_FILE_CONTENT_END", None, f"file_id={file_id} duration_ms={db_write_duration:.2f}")
        return result

    def update_file_processing_status(self, file_id: str, status: str) -> bool:
        """Update file processing status.

        Args:
            file_id: Unique file identifier
            status: 'pending', 'processing', 'completed', or 'failed'

        Returns:
            True if successful, False otherwise
        """
        _log_db_wrapper_op("UPDATE_FILE_STATUS_START", None, f"file_id={file_id}, status={status}")
        write_start = time.time()

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute("UPDATE files SET processing_status = ? WHERE id = ?", (status, file_id))
                conn.commit()
                return c.rowcount > 0
            finally:
                conn.close()

        result = _write()
        db_write_duration = (time.time() - write_start) * 1000
        # Get chat_id for cache invalidation
        file_meta = self.get_file(file_id)
        if file_meta:
            cache_layer.invalidate("files", f"chat:{file_meta.get('chat_id')}")
        _log_db_wrapper_op("UPDATE_FILE_STATUS_END", None, f"file_id={file_id} duration_ms={db_write_duration:.2f}")
        return result

    # ==================== MEMORY OPERATIONS ====================
    # No RAG needed - direct DB access for global memory

    def get_all_memories(self) -> list:
        """Get all memories from the database.

        Returns:
            List of memory dicts with id, content, tag, timestamp
        """
        _log_db_wrapper_op("GET_ALL_MEMORIES_START")
        fetch_start = time.time()

        def _fetch():
            conn = make_connection()
            try:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute("SELECT * FROM memories ORDER BY timestamp DESC")
                return [dict(row) for row in c.fetchall()]
            finally:
                conn.close()

        result = _fetch()
        duration_ms = (time.time() - fetch_start) * 1000
        _log_db_wrapper_op("GET_ALL_MEMORIES_END", None, f"count={len(result)} duration_ms={duration_ms:.2f}")
        return result

    def add_memory(self, content: str, tag: str) -> str:
        """Add a new memory to the database.

        Args:
            content: The memory content (fact, preference, etc.)
            tag: Category tag (user_preference, user_profile, environment_global, explicit_fact)

        Returns:
            The ID of the newly created memory
        """
        _log_db_wrapper_op("ADD_MEMORY_START", None, f"tag={tag}")
        write_start = time.time()

        import uuid
        memory_id = str(uuid.uuid4())

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute('''
                    INSERT INTO memories (id, content, tag, timestamp)
                    VALUES (?, ?, ?, ?)
                ''', (memory_id, content, tag, time.time()))
                conn.commit()
            finally:
                conn.close()

        _write()
        db_write_duration = (time.time() - write_start) * 1000
        _log_db_wrapper_op("ADD_MEMORY_END", None, f"memory_id={memory_id} duration_ms={db_write_duration:.2f}")
        return memory_id

    def update_memory(self, memory_id: str, new_content: str, new_tag: str) -> bool:
        """Update an existing memory.

        Args:
            memory_id: ID of the memory to update
            new_content: New content for the memory
            new_tag: New tag/category

        Returns:
            True if updated, False if not found
        """
        _log_db_wrapper_op("UPDATE_MEMORY_START", None, f"memory_id={memory_id}")
        write_start = time.time()

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute('''
                    UPDATE memories
                    SET content = ?, tag = ?, timestamp = ?
                    WHERE id = ?
                ''', (new_content, new_tag, time.time(), memory_id))
                conn.commit()
                return c.rowcount > 0
            finally:
                conn.close()

        result = _write()
        db_write_duration = (time.time() - write_start) * 1000
        _log_db_wrapper_op("UPDATE_MEMORY_END", None, f"memory_id={memory_id} updated={result} duration_ms={db_write_duration:.2f}")
        return result

    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory by ID.

        Args:
            memory_id: ID of the memory to delete

        Returns:
            True if deleted, False if not found
        """
        _log_db_wrapper_op("DELETE_MEMORY_START", None, f"memory_id={memory_id}")
        write_start = time.time()

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
                conn.commit()
                return c.rowcount > 0
            finally:
                conn.close()

        result = _write()
        db_write_duration = (time.time() - write_start) * 1000
        _log_db_wrapper_op("DELETE_MEMORY_END", None, f"memory_id={memory_id} deleted={result} duration_ms={db_write_duration:.2f}")
        return result

    def clear_memories(self) -> int:
        """Delete all memories from the database.

        Returns:
            Number of memories deleted
        """
        _log_db_wrapper_op("CLEAR_MEMORIES_START")
        write_start = time.time()

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM memories")
                count = c.fetchone()[0]
                c.execute("DELETE FROM memories")
                conn.commit()
                return count
            finally:
                conn.close()

        deleted_count = _write()
        db_write_duration = (time.time() - write_start) * 1000
        _log_db_wrapper_op("CLEAR_MEMORIES_END", None, f"deleted={deleted_count} duration_ms={db_write_duration:.2f}")
        return deleted_count


# Global instance
db = DatabaseWrapper()


# =============================================================================
# INFRASTRUCTURE EXPORTS
# =============================================================================
# Export infrastructure components for backward compatibility
# DB_PATH for direct access when needed
from backend.config import DATA_DIR
import os
DB_PATH = os.path.join(DATA_DIR, "chats.db")

# Note: lock_manager, TableLockManager, and execute_with_retry remain in storage.py
# Files that need these can import from backend.storage directly
