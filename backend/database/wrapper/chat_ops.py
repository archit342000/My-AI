import sqlite3
import time
import json
from ..db_layer import make_connection
from ..cache_layer import cache_layer
from ..cache_system import cache_system
from .base import BaseMixin

def _require_user_id(user_id) -> str:
    """Return `user_id`, or raise ValueError when it is empty (an owner is required on every owned-table method)."""
    if not user_id or not isinstance(user_id, str):
        raise ValueError("user_id is required")
    return user_id


class ChatOpsMixin(BaseMixin):
    """
    Mixin for chat-level operations (CRUD, listing, metadata).
    """

    def get_chat(self, chat_id: str):
        """
        Get chat with cache-first semantics (row-level).
        """
        self._log_db_wrapper_op("GET_CHAT_START", chat_id)
        fetch_start = time.time()
        result = cache_layer.get("chats", chat_id, lambda: self._get_chat_fetch_internal(chat_id), ttl=300)
        duration_ms = (time.time() - fetch_start) * 1000
        self._log_db_wrapper_op("GET_CHAT_END", chat_id, f"duration_ms={duration_ms:.2f}")
        return result

    def get_all_chats(self, user_id: str) -> list[dict]:
        """Get one user's chats with cache-first semantics (table-level read, filtered by owner)."""
        _require_user_id(user_id)

        def _fetch():
            conn = make_connection()
            try:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute('''
                    SELECT c.*, w.name as workspace_name 
                    FROM chats c 
                    LEFT JOIN workspaces w ON c.workspace_id = w.id 
                    ORDER BY c.timestamp DESC
                ''')
                return [dict(row) for row in c.fetchall()]
            finally:
                conn.close()

        rows = cache_layer.get_table("chats", _fetch, key_extractor=lambda row: row.get('id', ''), ttl=300)
        return [row for row in rows if row.get('user_id') == user_id]

    def get_all_chat_ids(self) -> list[str]:
        """Ids of every chat of every user. For system cleanup only (never for a user-facing list)."""
        conn = make_connection()
        try:
            return [row[0] for row in conn.execute("SELECT id FROM chats").fetchall()]
        finally:
            conn.close()

    def get_chat_owner(self, chat_id: str) -> str | None:
        """Owner (`user_id`) of a chat, read straight from the DB so a stale cache cannot grant access. None if missing."""
        conn = make_connection()
        try:
            row = conn.execute("SELECT user_id FROM chats WHERE id = ?", (chat_id,)).fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def get_workspace_owner(self, workspace_id: str) -> str | None:
        """Owner (`user_id`) of a workspace, read straight from the DB. None if missing."""
        conn = make_connection()
        try:
            row = conn.execute("SELECT user_id FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def get_listed_chats(self, user_id: str) -> list[dict]:
        """
        Chats for the sidebar and workspace lists: only those that hold content (at least one message,
        uploaded file or chat-scoped artifact). Empty chats come from uploads, artifact creation or the
        first PATCH before any message exists, and would show up as blank "New Conversation" entries.
        Unsaved temporary chats (`is_temporary = 1`) are never listed.

        `get_all_chats` stays unfiltered by content on purpose: internal callers must see every row of the user,
        including empty ones. Both are scoped to `user_id`.

        Args:
            user_id: Owner whose chats are listed.

        Returns:
            Chat rows (same shape as `get_all_chats`, newest first), each with `workspace_name`.
        """
        _require_user_id(user_id)

        def _fetch():
            conn = make_connection()
            try:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute('''
                    SELECT c.*, w.name as workspace_name
                    FROM chats c
                    LEFT JOIN workspaces w ON c.workspace_id = w.id
                    WHERE (EXISTS (SELECT 1 FROM messages m WHERE m.chat_id = c.id)
                       OR EXISTS (SELECT 1 FROM files f WHERE f.chat_id = c.id)
                       OR EXISTS (SELECT 1 FROM file_systems fs WHERE fs.chat_id = c.id))
                      AND COALESCE(c.is_temporary, 0) = 0
                    ORDER BY c.timestamp DESC
                ''')
                return [dict(row) for row in c.fetchall()]
            finally:
                conn.close()

        rows = cache_layer.get_table("chats", _fetch, key_extractor=lambda row: row.get('id', ''), ttl=300)
        return [row for row in rows if row.get('user_id') == user_id]

    def mark_chat_temporary(self, chat_id: str) -> bool:
        """
        Mark a chat temporary only while it has no messages (one statement, so a save or a first message cannot be undone by
        a racing first-send mark). Returns True when the chat was marked.
        """
        conn = make_connection()
        try:
            c = conn.cursor()
            c.execute(
                "UPDATE chats SET is_temporary = 1 WHERE id = ? AND NOT EXISTS (SELECT 1 FROM messages m WHERE m.chat_id = ?)",
                (chat_id, chat_id),
            )
            marked = c.rowcount > 0
            conn.commit()
        finally:
            conn.close()
        if marked:
            cache_layer.invalidate("chats", chat_id)
        return marked

    def get_expired_temporary_chats(self, user_id: str, before_ts: float) -> list[str]:
        """Ids of one user's unsaved temporary chats whose last activity (`timestamp`) is older than `before_ts`."""
        _require_user_id(user_id)
        conn = make_connection()
        try:
            c = conn.cursor()
            c.execute(
                "SELECT id FROM chats WHERE user_id = ? AND COALESCE(is_temporary, 0) = 1 AND COALESCE(timestamp, 0) < ?",
                (user_id, before_ts),
            )
            return [row[0] for row in c.fetchall()]
        finally:
            conn.close()

    # =========================================================================
    # WORKSPACE OPERATIONS
    # =========================================================================

    def get_all_workspaces(self, user_id: str) -> list[dict]:
        """Get one user's workspaces."""
        _require_user_id(user_id)

        def _fetch():
            conn = make_connection()
            try:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute('''
                    SELECT w.*
                    FROM workspaces w
                    LEFT JOIN chats c ON w.id = c.workspace_id AND COALESCE(c.is_temporary, 0) = 0
                    GROUP BY w.id
                    ORDER BY CASE 
                        WHEN COALESCE(w.timestamp, 0) > COALESCE(MAX(c.timestamp), 0) 
                        THEN COALESCE(w.timestamp, 0) 
                        ELSE COALESCE(MAX(c.timestamp), 0) 
                    END DESC
                ''')
                return [dict(row) for row in c.fetchall()]
            finally:
                conn.close()
        rows = cache_layer.get_table("workspaces", _fetch, key_extractor=lambda row: row.get('id', ''), ttl=300)
        return [row for row in rows if row.get('user_id') == user_id]

    def workspace_name_exists(self, name: str, user_id: str, exclude_id: str | None = None) -> bool:
        """
        Whether another workspace of this user already uses this name (case-insensitive, ignoring surrounding spaces).

        Args:
            name: The candidate workspace name.
            user_id: Owner whose workspaces are checked; other users' names do not count.
            exclude_id: A workspace id to leave out, so renaming a workspace to its own name is allowed.

        Returns:
            True if a different workspace has the same name.
        """
        _require_user_id(user_id)
        conn = make_connection()
        try:
            c = conn.cursor()
            sql = "SELECT 1 FROM workspaces WHERE LOWER(TRIM(name)) = LOWER(TRIM(?)) AND user_id = ?"
            params = [name, user_id]
            if exclude_id is not None:
                sql += " AND id != ?"
                params.append(exclude_id)
            c.execute(sql + " LIMIT 1", params)
            return c.fetchone() is not None
        finally:
            conn.close()

    def create_workspace(self, name: str, user_id: str, icon: str = None) -> dict:
        """Create a new workspace owned by `user_id`."""
        _require_user_id(user_id)
        import uuid
        workspace_id = f"ws_{uuid.uuid4().hex}"
        
        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute("INSERT INTO workspaces (id, name, timestamp, icon, user_id) VALUES (?, ?, ?, ?, ?)", (workspace_id, name, time.time(), icon, user_id))
                conn.commit()
            finally:
                conn.close()
                
        _write()
        cache_layer.invalidate("workspaces")
        return {"id": workspace_id, "name": name, "timestamp": time.time(), "icon": icon, "user_id": user_id}

    def rename_workspace(self, workspace_id: str, new_name: str):
        """Rename an existing workspace."""
        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute("UPDATE workspaces SET name = ?, timestamp = ? WHERE id = ?", (new_name, time.time(), workspace_id))
                conn.commit()
            finally:
                conn.close()
                
        _write()
        cache_layer.invalidate("workspaces")
        # Invalidate chats since workspace name might be embedded or cached
        cache_layer.invalidate("chats")
        cache_layer.clear_cache()

    def update_workspace_icon(self, workspace_id: str, icon: str):
        """Update workspace icon."""
        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute("UPDATE workspaces SET icon = ?, timestamp = ? WHERE id = ?", (icon if icon else None, time.time(), workspace_id))
                conn.commit()
            finally:
                conn.close()
                
        _write()
        cache_layer.invalidate("workspaces")
        cache_layer.invalidate("chats")
        cache_layer.clear_cache()
        
    def delete_workspace(self, workspace_id: str):
        """Delete a workspace. Chats will have their workspace_id set to NULL."""
        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute("BEGIN IMMEDIATE")
                try:
                    c.execute("DELETE FROM workspaces WHERE id = ?", (workspace_id,))
                    # ON DELETE SET NULL on chats and ON DELETE CASCADE on file_systems handles the rest
                    conn.commit()
                except:
                    conn.rollback()
                    raise
            finally:
                conn.close()
                
        _write()
        cache_layer.invalidate("workspaces")
        cache_layer.invalidate("chats")
        cache_layer.clear_cache()

    def ensure_chat_exists(self, chat_id: str, user_id: str) -> str | None:
        """
        Check if a chat exists in the DB, and if not, create a skeleton record owned by `user_id`.
        Bypasses the cache to avoid stale hits causing FOREIGN KEY failures.

        Args:
            chat_id: The chat to look up or create.
            user_id: Owner for a newly created chat. An existing chat keeps its owner.

        Returns:
            The stored owner of the chat (None for a legacy ownerless row), which the caller compares with `user_id`
            to refuse another user's chat. Read back after a create, so a lost create race reports the winner.
        """
        _require_user_id(user_id)
        # Always read from DB directly — a stale cache hit on a deleted chat would
        # skip creation here, then the file_system INSERT would fail FK validation.
        existing = self._get_chat_fetch_internal(chat_id)
        if not existing:
            self._log_db_wrapper_op("ENSURE_CHAT_EXISTS_MISS", chat_id)
            self.save_chat(
                chat_id=chat_id,
                title="New Conversation",
                timestamp=time.time(),
                enable_thinking=1,
                user_id=user_id
            )
            return self.get_chat_owner(chat_id)
        self._log_db_wrapper_op("ENSURE_CHAT_EXISTS_HIT", chat_id)
        return existing.get('user_id')

    def save_chat(self, chat_id: str, title: str, timestamp: float, 
                  enable_thinking: int,
                  user_preferences: int = 0, research_mode: bool = False, 
                  is_vision: bool = False, last_model: str = None, 
                  vision_model: str = None, max_tokens: int = 16384, 
                  thinking_budget_tokens: int = 2000,
                  workspace_id: str = None, persona_id: str = None,
                  research_completed: int = 0, had_research: int = 0, 
                  file_system_mode: bool = False, browsing_mode: bool = False,
                  temperature: float = 1.0, top_p: float = 1.0, 
                  top_k: int = 40, min_p: float = 0.05, 
                  presence_penalty: float = 0.0, frequency_penalty: float = 0.0, 
                  is_custom_title: int = None,
                  research_state: str = 'none',
                  *, user_id: str) -> None:
        """
        Save chat with Cache-Aside pattern (DB write + cache invalidation).

        A new chat is owned by `user_id`. An existing chat keeps its owner, and is only updated when it already belongs
        to `user_id`: the conflict update is guarded, so a save can never overwrite another user's chat.
        """
        _require_user_id(user_id)
        self._log_db_wrapper_op("SAVE_CHAT_START", chat_id)
        write_start = time.time()

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute('''
                    INSERT INTO chats (id, title, timestamp, user_preferences, research_mode,
                                      is_vision, last_model, vision_model, max_tokens, thinking_budget_tokens,
                                      is_custom_title, workspace_id, persona_id,
                                      research_completed, had_research, file_system_mode, browsing_mode, enable_thinking,
                                      temperature, top_p, top_k, min_p, presence_penalty, frequency_penalty,
                                      research_state, user_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        title=CASE WHEN excluded.is_custom_title = 1 THEN excluded.title 
                                   WHEN chats.is_custom_title = 1 THEN chats.title 
                                   ELSE excluded.title END,
                        is_custom_title=CASE WHEN excluded.is_custom_title = 1 THEN 1 ELSE chats.is_custom_title END,
                        user_preferences=excluded.user_preferences,
                        research_mode=excluded.research_mode,
                        is_vision=excluded.is_vision,
                        last_model=excluded.last_model,
                        vision_model=excluded.vision_model,
                        max_tokens=excluded.max_tokens,
                        thinking_budget_tokens=excluded.thinking_budget_tokens,
                        workspace_id=COALESCE(excluded.workspace_id, chats.workspace_id),
                        persona_id=COALESCE(excluded.persona_id, chats.persona_id),
                        research_completed=excluded.research_completed,
                        had_research=excluded.had_research,
                        file_system_mode=excluded.file_system_mode,
                        browsing_mode=excluded.browsing_mode,
                        enable_thinking=excluded.enable_thinking,
                        last_user_id=COALESCE(excluded.last_user_id, chats.last_user_id),
                        last_assistant_id=COALESCE(excluded.last_assistant_id, chats.last_assistant_id),
                        temperature=excluded.temperature,
                        top_p=excluded.top_p,
                        top_k=excluded.top_k,
                        min_p=excluded.min_p,
                        presence_penalty=excluded.presence_penalty,
                        frequency_penalty=excluded.frequency_penalty,
                        research_state=excluded.research_state
                    WHERE chats.user_id IS excluded.user_id
                ''', (chat_id, title, timestamp, user_preferences, research_mode,
                      is_vision, last_model, vision_model, max_tokens, thinking_budget_tokens,
                      is_custom_title if is_custom_title is not None else 0,
                      workspace_id, persona_id, research_completed, had_research, file_system_mode, browsing_mode, enable_thinking,
                      temperature, top_p, top_k, min_p, presence_penalty, frequency_penalty,
                      research_state, user_id))
                conn.commit()
            finally:
                conn.close()

        _write()
        db_write_duration = (time.time() - write_start) * 1000
        cache_layer.invalidate("chats", chat_id)
        cache_layer.invalidate("chats_full", chat_id)
        cache_layer.invalidate("workspaces")
        self._log_db_wrapper_op("SAVE_CHAT_END", chat_id, f"db_ms={db_write_duration:.2f}")

    def update_chat(self, chat_id: str, **kwargs):
        """Update chat with Cache-Aside pattern (DB write + cache invalidation)."""
        self._log_db_wrapper_op("UPDATE_CHAT_START", chat_id, f"updates={len(kwargs)}")
        write_start = time.time()

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                updates = []
                values = []
                # Map kwargs to allowed columns
                allowed_fields = [
                    'title', 'user_preferences', 'research_mode', 'is_vision', 
                    'last_model', 'vision_model', 'max_tokens', 'thinking_budget_tokens', 'workspace_id', 'persona_id',
                    'persona_snapshot', 'history_compression',
                    'research_completed', 'had_research', 
                    'file_system_mode', 'browsing_mode', 'enable_thinking', 'temperature', 'top_p', 
                    'top_k', 'min_p', 'presence_penalty', 'frequency_penalty',
                    'last_user_id', 'last_assistant_id', 'research_state',
                    'resume_suppressed', 'thinking_profile',
                    'browsing_session_id', 'git_mode', 'code_execution_mode', 'timestamp', 'is_temporary'
                ]
                for field in allowed_fields:
                    if field in kwargs:
                        updates.append(f"{field}=?")
                        values.append(kwargs[field])

                if updates:
                    c.execute(f'''
                        UPDATE chats SET {", ".join(updates)} WHERE id=?
                    ''', values + [chat_id])
                conn.commit()
            finally:
                conn.close()

        _write()
        db_write_duration = (time.time() - write_start) * 1000
        cache_layer.invalidate("chats", chat_id)
        cache_layer.invalidate("chats_full", chat_id)
        cache_layer.invalidate("workspaces")
        self._log_db_wrapper_op("UPDATE_CHAT_END", chat_id, f"duration_ms={db_write_duration:.2f}")

    def update_last_user_id(self, chat_id: str, user_id: int):
        """Update last_user_id for a chat."""
        self.update_chat(chat_id, last_user_id=user_id)

    def update_last_assistant_id(self, chat_id: str, assistant_id: int):
        """Update last_assistant_id for a chat."""
        self.update_chat(chat_id, last_assistant_id=assistant_id)

    def rename_chat(self, chat_id: str, new_title: str):
        """Update chat title."""
        self.update_chat(chat_id, title=new_title)

    def update_chat_model(self, chat_id: str, last_model: str):
        """Update last used model."""
        self.update_chat(chat_id, last_model=last_model)

    def update_chat_vision_model(self, chat_id: str, vision_model: str):
        """Update vision model selection."""
        self.update_chat(chat_id, vision_model=vision_model)

    def update_chat_max_tokens(self, chat_id: str, max_tokens: int):
        """Update max tokens setting."""
        self.update_chat(chat_id, max_tokens=max_tokens)

    def update_chat_workspace(self, chat_id: str, workspace_id: str):
        """Update chat workspace assignment."""
        self.update_chat(chat_id, workspace_id=workspace_id)

    def mark_research_completed(self, chat_id: str, completed: int):
        """Toggle research completion status."""
        self.update_chat(chat_id, research_completed=completed)

    def update_chat_file_system_mode(self, chat_id: str, file_system_mode: bool):
        """Toggle file_system mode for a chat."""
        self.update_chat(chat_id, file_system_mode=file_system_mode)

    def update_research_state(self, chat_id: str, state: str):
        """Update the research state (none, ongoing)."""
        self.update_chat(chat_id, research_state=state)

    def delete_chat(self, chat_id: str):
        """Delete a chat and all its dependent rows in FK-safe order, inside a single transaction."""
        self._log_db_wrapper_op("DELETE_CHAT_START", chat_id)
        write_start = time.time()

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute("BEGIN IMMEDIATE")
                try:
                    # Delete deepest children first (they FK → file_systems)
                    c.execute("DELETE FROM file_system_versions WHERE chat_id = ?", (chat_id,))
                    c.execute("DELETE FROM file_system_permissions WHERE chat_id = ?", (chat_id,))
                    # FTS search index before the main file_systems table
                    try:
                        c.execute("DELETE FROM file_systems_search WHERE id IN (SELECT id FROM file_systems WHERE chat_id = ?)", (chat_id,))
                    except sqlite3.OperationalError:
                        pass  # FTS5 may be unsupported
                    c.execute("DELETE FROM file_systems WHERE chat_id = ?", (chat_id,))
                    # Other chat-level children (FK → chats)
                    c.execute("DELETE FROM sub_agent_messages WHERE chat_id = ?", (chat_id,))
                    c.execute("DELETE FROM collections WHERE chat_id = ?", (chat_id,))
                    c.execute("DELETE FROM pending_callbacks WHERE chat_id = ?", (chat_id,))
                    c.execute("DELETE FROM files WHERE chat_id = ?", (chat_id,))
                    c.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
                    c.execute("DELETE FROM code_execution_history WHERE chat_id = ?", (chat_id,))
                    c.execute("DELETE FROM clipboard WHERE chat_id = ?", (chat_id,))
                    # Parent row last — all FK children are already gone
                    c.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise
            finally:
                c.execute("PRAGMA foreign_keys=ON")
                conn.close()

        _write()
        db_write_duration = (time.time() - write_start) * 1000
        cache_system.delete_sse_chunks(chat_id)
        cache_layer.invalidate("chats", chat_id)
        cache_layer.invalidate("messages", f"chat:{chat_id}")
        cache_layer.invalidate("files", f"chat:{chat_id}")
        cache_layer.invalidate("chats_full", chat_id)
        cache_layer.invalidate("workspaces")
        self._log_db_wrapper_op("DELETE_CHAT_END", chat_id, f"duration_ms={db_write_duration:.2f}")

    def delete_all_chats(self, user_id: str) -> None:
        """
        Delete one user's chats and all their associated data in FK-safe order, in a single transaction.

        Other users' rows are untouched. File systems of the user's chats and of the user's workspaces are removed
        (the workspace rows are kept).

        Args:
            user_id: Owner whose chats are deleted.
        """
        _require_user_id(user_id)
        self._log_db_wrapper_op("DELETE_ALL_CHATS_START", user_id)
        write_start = time.time()
        own_chats = "SELECT id FROM chats WHERE user_id = ?"
        own_file_systems = (
            "SELECT id FROM file_systems WHERE chat_id IN (SELECT id FROM chats WHERE user_id = ?) "
            "OR workspace_id IN (SELECT id FROM workspaces WHERE user_id = ?)"
        )

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute("BEGIN IMMEDIATE")
                try:
                    # Deepest children first (FK -> file_systems)
                    c.execute(f"DELETE FROM file_system_versions WHERE file_system_id IN ({own_file_systems})", (user_id, user_id))
                    c.execute(f"DELETE FROM file_system_permissions WHERE file_system_id IN ({own_file_systems})", (user_id, user_id))
                    try:
                        c.execute(f"DELETE FROM file_systems_search WHERE id IN ({own_file_systems})", (user_id, user_id))
                    except sqlite3.OperationalError:
                        pass  # FTS5 may be unsupported
                    c.execute(f"DELETE FROM file_systems WHERE id IN ({own_file_systems})", (user_id, user_id))
                    # Chat-level children (FK -> chats)
                    for table in ("sub_agent_messages", "collections", "pending_callbacks", "files", "messages",
                                  "code_execution_history", "clipboard"):
                        c.execute(f"DELETE FROM {table} WHERE chat_id IN ({own_chats})", (user_id,))
                    # Parent rows last
                    c.execute("DELETE FROM chats WHERE user_id = ?", (user_id,))
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise
            finally:
                c.execute("PRAGMA foreign_keys=ON")
                conn.close()

        _write()
        db_write_duration = (time.time() - write_start) * 1000
        # Wipe all caches (the cache is shared by every user)
        cache_layer.clear_cache()
        self._log_db_wrapper_op("DELETE_ALL_CHATS_END", user_id, f"duration_ms={db_write_duration:.2f}")

    def get_chat_full(self, chat_id: str):
        """
        [LEGACY] Get chat with all messages (row-level).
        """
        self._log_db_wrapper_op("GET_CHAT_FULL_START", chat_id)
        fetch_start = time.time()
        
        def _fetch():
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
                c.execute("SELECT * FROM sub_agent_messages WHERE chat_id = ? ORDER BY sequence_order ASC", (chat_id,))
                sub_agent_messages = c.fetchall()
                chunks = cache_system.get_sse_chunks(chat_id)
                chat_dict = dict(chat)
                chat_dict['messages'] = [dict(m) for m in messages]
                chat_dict['sub_agent_messages'] = [dict(sm) for sm in sub_agent_messages]
                chat_dict['sse_chunks'] = chunks
                return chat_dict
            finally:
                conn.close()

        result = cache_layer.get("chats_full", chat_id, _fetch, ttl=60)
        duration_ms = (time.time() - fetch_start) * 1000
        self._log_db_wrapper_op("GET_CHAT_FULL_END", chat_id, f"duration_ms={duration_ms:.2f}")
        return result
