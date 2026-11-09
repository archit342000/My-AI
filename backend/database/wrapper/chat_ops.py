import sqlite3
import time
import json
from ..db_layer import make_connection
from ..cache_layer import cache_layer
from ..cache_system import cache_system
from .base import BaseMixin

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

    def get_all_chats(self):
        """Get all chats with cache-first semantics (table-level)."""
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

        return cache_layer.get_table("chats", _fetch, key_extractor=lambda row: row.get('id', ''), ttl=300)

    # =========================================================================
    # WORKSPACE OPERATIONS
    # =========================================================================

    def get_all_workspaces(self):
        """Get all workspaces."""
        def _fetch():
            conn = make_connection()
            try:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute('''
                    SELECT w.*
                    FROM workspaces w
                    LEFT JOIN chats c ON w.id = c.workspace_id
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
        return cache_layer.get_table("workspaces", _fetch, key_extractor=lambda row: row.get('id', ''), ttl=300)

    def workspace_name_exists(self, name: str, exclude_id: str | None = None) -> bool:
        """
        Whether another workspace already uses this name (case-insensitive, ignoring surrounding spaces).

        Args:
            name: The candidate workspace name.
            exclude_id: A workspace id to leave out, so renaming a workspace to its own name is allowed.

        Returns:
            True if a different workspace has the same name.
        """
        conn = make_connection()
        try:
            c = conn.cursor()
            sql = "SELECT 1 FROM workspaces WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))"
            params = [name]
            if exclude_id is not None:
                sql += " AND id != ?"
                params.append(exclude_id)
            c.execute(sql + " LIMIT 1", params)
            return c.fetchone() is not None
        finally:
            conn.close()

    def create_workspace(self, name: str, icon: str = None):
        """Create a new workspace."""
        import uuid
        workspace_id = f"ws_{uuid.uuid4().hex}"
        
        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute("INSERT INTO workspaces (id, name, timestamp, icon) VALUES (?, ?, ?, ?)", (workspace_id, name, time.time(), icon))
                conn.commit()
            finally:
                conn.close()
                
        _write()
        cache_layer.invalidate("workspaces")
        return {"id": workspace_id, "name": name, "timestamp": time.time(), "icon": icon}

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

    def ensure_chat_exists(self, chat_id: str):
        """
        Check if a chat exists in the DB, and if not, create a skeleton record.
        Bypasses the cache to avoid stale hits causing FOREIGN KEY failures.
        """
        # Always read from DB directly — a stale cache hit on a deleted chat would
        # skip creation here, then the file_system INSERT would fail FK validation.
        existing = self._get_chat_fetch_internal(chat_id)
        if not existing:
            self._log_db_wrapper_op("ENSURE_CHAT_EXISTS_MISS", chat_id)
            self.save_chat(
                chat_id=chat_id,
                title="New Conversation",
                timestamp=time.time(),
                enable_thinking=1
            )
        else:
            self._log_db_wrapper_op("ENSURE_CHAT_EXISTS_HIT", chat_id)

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
                  research_state: str = 'none'):
        """
        Save chat with Cache-Aside pattern (DB write + cache invalidation).
        """
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
                                      research_state)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                ''', (chat_id, title, timestamp, user_preferences, research_mode,
                      is_vision, last_model, vision_model, max_tokens, thinking_budget_tokens,
                      is_custom_title if is_custom_title is not None else 0,
                      workspace_id, persona_id, research_completed, had_research, file_system_mode, browsing_mode, enable_thinking,
                      temperature, top_p, top_k, min_p, presence_penalty, frequency_penalty,
                      research_state))
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
                    'browsing_session_id', 'git_mode', 'code_execution_mode', 'timestamp'
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

    def delete_all_chats(self):
        """NUCLEAR: Deletes all chats and all associated data in FK-safe order."""
        self._log_db_wrapper_op("DELETE_ALL_CHATS_START", "GLOBAL")
        write_start = time.time()

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute("BEGIN IMMEDIATE")
                try:
                    # Deepest children first (FK → file_systems)
                    c.execute("DELETE FROM file_system_versions")
                    c.execute("DELETE FROM file_system_permissions")
                    try:
                        c.execute("DELETE FROM file_systems_search")
                    except sqlite3.OperationalError:
                        pass  # FTS5 may be unsupported
                    c.execute("DELETE FROM file_systems")
                    # Chat-level children (FK → chats)
                    c.execute("DELETE FROM sub_agent_messages")
                    c.execute("DELETE FROM collections")
                    c.execute("DELETE FROM pending_callbacks")
                    c.execute("DELETE FROM files")
                    c.execute("DELETE FROM messages")
                    c.execute("DELETE FROM code_execution_history")
                    c.execute("DELETE FROM clipboard")
                    # Parent rows last
                    c.execute("DELETE FROM chats")
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise
            finally:
                c.execute("PRAGMA foreign_keys=ON")
                conn.close()

        _write()
        db_write_duration = (time.time() - write_start) * 1000
        # Wipe all caches
        cache_layer.clear_cache()
        self._log_db_wrapper_op("DELETE_ALL_CHATS_END", "GLOBAL", f"duration_ms={db_write_duration:.2f}")

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
