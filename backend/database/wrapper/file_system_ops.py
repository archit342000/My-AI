import time
import json
import sqlite3
import os
from ..db_layer import make_connection
from ..cache_layer import cache_layer
from .base import BaseMixin

class FileSystemOpsMixin(BaseMixin):
    """
    Mixin for FileSystem operations (metadata, versions, counting).
    """

    def get_file_system_meta(self, file_system_id: str, chat_id: str = None, workspace_id: str = None):
        """Get file_system metadata."""
        owner_id = chat_id or workspace_id
        self._log_db_wrapper_op("GET_FILE_SYSTEM_META_START", owner_id, f"file_system_id={file_system_id}")
        fetch_start = time.time()
        
        def _fetch():
            conn = make_connection()
            try:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                if workspace_id and chat_id:
                    # If both are provided, we should match exactly one context (usually workspace is shared)
                    # But the caller should ideally specify one. 
                    # To be safe, we match rows where either owner matches, but since we FetchOne,
                    # we prioritize the explicit workspace_id if it's a workspace file_system.
                    c.execute("SELECT * FROM file_systems WHERE id = ? AND ((chat_id = ? AND workspace_id IS NULL) OR (workspace_id = ?))", (file_system_id, chat_id, workspace_id))
                elif workspace_id:
                    c.execute("SELECT * FROM file_systems WHERE id = ? AND workspace_id = ?", (file_system_id, workspace_id))
                else:
                    c.execute("SELECT * FROM file_systems WHERE id = ? AND chat_id = ?", (file_system_id, chat_id))
                row = c.fetchone()
                return dict(row) if row else None
            finally:
                conn.close()

        # Use a precise owner key to avoid cache collisions between chat-local and workspace-shared file_systems
        if workspace_id and chat_id:
            owner_key = f"ws:{workspace_id}:chat:{chat_id}"
        elif workspace_id:
            owner_key = f"ws:{workspace_id}"
        else:
            owner_key = f"chat:{chat_id}"
            
        result = cache_layer.get("file_systems", f"{owner_key}:{file_system_id}", _fetch, ttl=300)
        self._log_db_wrapper_op("GET_FILE_SYSTEM_META_END", owner_id, f"file_system_id={file_system_id} duration_ms={(time.time() - fetch_start)*1000:.2f}")
        return result

    def get_file_system_meta_by_path(self, path: str, chat_id: str = None, workspace_id: str = None):
        """Get file_system metadata by its relative path (stored in filename)."""
        self._log_db_wrapper_op("GET_FILE_SYSTEM_META_BY_PATH_START", chat_id or workspace_id, f"path={path}")
        fetch_start = time.time()
        
        def _fetch():
            conn = make_connection()
            try:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                if workspace_id:
                    c.execute("SELECT * FROM file_systems WHERE filename = ? AND workspace_id = ?", (path, workspace_id))
                else:
                    c.execute("SELECT * FROM file_systems WHERE filename = ? AND chat_id = ?", (path, chat_id))
                row = c.fetchone()
                return dict(row) if row else None
            finally:
                conn.close()
                
        # Use a precise owner key to avoid cache collisions between chat-local and workspace-shared file_systems
        if workspace_id and chat_id:
            owner_key = f"ws:{workspace_id}:chat:{chat_id}"
        elif workspace_id:
            owner_key = f"ws:{workspace_id}"
        else:
            owner_key = f"chat:{chat_id}"
            
        result = cache_layer.get("file_systems", f"{owner_key}:path:{path}", _fetch, ttl=300)
        self._log_db_wrapper_op("GET_FILE_SYSTEM_META_BY_PATH_END", chat_id or workspace_id, f"path={path} duration_ms={(time.time() - fetch_start)*1000:.2f}")
        return result

    def _get_file_system_meta_fetch_internal(self, file_system_id: str, chat_id: str = None, workspace_id: str = None):
        """Internal fetch for file_system metadata."""
        conn = make_connection()
        try:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            if workspace_id:
                c.execute("SELECT * FROM file_systems WHERE id = ? AND workspace_id = ?", (file_system_id, workspace_id))
            else:
                c.execute("SELECT * FROM file_systems WHERE id = ? AND chat_id = ?", (file_system_id, chat_id))
            row = c.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def save_file_system_meta(self, file_system_id: str, chat_id: str = None, workspace_id: str = None, title: str = None,
                         filename: str = None, file_system_type: str = None,
                         folder: str = None, tags=None, current_version: int = None,
                         language: str = None, navigation_history: str = None,
                         navigation_index: int = None):
        """Upsert file_system metadata."""
        owner_id = chat_id or workspace_id
        self._log_db_wrapper_op("SAVE_FILE_SYSTEM_META_START", owner_id, f"file_system_id={file_system_id}")
        write_start = time.time()
        
        existing = self.get_file_system_meta(file_system_id, chat_id=chat_id, workspace_id=workspace_id)
        if existing:
            title = title if title is not None else existing.get('title', 'Untitled')
            filename = filename if filename is not None else existing.get('filename', f"{file_system_id}.md")
            file_system_type = file_system_type if file_system_type is not None else existing.get('file_system_type', 'custom')
            folder = folder if folder is not None else existing.get('folder')
            tags = tags if tags is not None else existing.get('tags')
            current_version = current_version if current_version is not None else existing.get('current_version')
            language = language if language is not None else existing.get('language', 'markdown')
            navigation_history = navigation_history if navigation_history is not None else existing.get('navigation_history', '[]')
            navigation_index = navigation_index if navigation_index is not None else existing.get('navigation_index', -1)
        else:
            title = title or 'Untitled'
            filename = filename or f"{file_system_id}.md"
            file_system_type = file_system_type or 'custom'
            current_version = current_version or 1
            language = language or 'markdown'
            navigation_history = navigation_history or '[]'
            navigation_index = navigation_index if navigation_index is not None else -1
            
        if isinstance(tags, (list, dict)): tags = json.dumps(tags)

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute("BEGIN IMMEDIATE")
                try:
                    if workspace_id:
                        c.execute("SELECT 1 FROM file_systems WHERE id = ? AND workspace_id = ?", (file_system_id, workspace_id))
                        exists = c.fetchone() is not None
                        if exists:
                            c.execute("""
                                UPDATE file_systems SET
                                    title = ?, filename = ?, folder = ?, tags = ?, file_system_type = ?,
                                    current_version = ?, language = ?, navigation_history = ?, navigation_index = ?, timestamp = ?
                                WHERE id = ? AND workspace_id = ?
                            """, (title, filename, folder, tags, file_system_type, current_version, language, navigation_history, navigation_index, time.time(), file_system_id, workspace_id))
                        else:
                            c.execute("""
                                INSERT INTO file_systems (id, chat_id, workspace_id, title, filename, timestamp, folder, tags, file_system_type, current_version, language, navigation_history, navigation_index)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (file_system_id, chat_id, workspace_id, title, filename, time.time(), folder, tags, file_system_type, current_version, language, navigation_history, navigation_index))
                    else:
                        c.execute("SELECT 1 FROM file_systems WHERE id = ? AND chat_id = ?", (file_system_id, chat_id))
                        exists = c.fetchone() is not None
                        if exists:
                            c.execute("""
                                UPDATE file_systems SET
                                    title = ?, filename = ?, folder = ?, tags = ?, file_system_type = ?,
                                    current_version = ?, language = ?, navigation_history = ?, navigation_index = ?, timestamp = ?
                                WHERE id = ? AND chat_id = ?
                            """, (title, filename, folder, tags, file_system_type, current_version, language, navigation_history, navigation_index, time.time(), file_system_id, chat_id))
                        else:
                            c.execute("""
                                INSERT INTO file_systems (id, chat_id, workspace_id, title, filename, timestamp, folder, tags, file_system_type, current_version, language, navigation_history, navigation_index)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (file_system_id, chat_id, workspace_id, title, filename, time.time(), folder, tags, file_system_type, current_version, language, navigation_history, navigation_index))
                    
                    if chat_id:
                        c.execute("UPDATE chats SET timestamp = ? WHERE id = ?", (time.time(), chat_id))
                    elif workspace_id:
                        c.execute("UPDATE workspaces SET timestamp = ? WHERE id = ?", (time.time(), workspace_id))
                    
                    conn.commit()
                except:
                    conn.rollback()
                    raise
            finally:
                conn.close()

        _write()
        owner_key = f"ws:{workspace_id}" if workspace_id else f"chat:{chat_id}"
        row_id = f"{owner_key}:{file_system_id}"
        cache_layer.invalidate("file_systems", row_id)
        cache_layer.invalidate("file_systems", f"{owner_key}:{file_system_id}:current_version")
        if existing and existing.get('filename'):
            cache_layer.invalidate("file_systems", f"{owner_key}:path:{existing['filename']}")
        cache_layer.invalidate("file_systems", f"{owner_key}:path:{filename}")
        cache_layer.invalidate("file_systems")
        self._log_db_wrapper_op("SAVE_FILE_SYSTEM_META_END", owner_id, f"file_system_id={file_system_id} duration_ms={(time.time() - write_start)*1000:.2f}")

    def create_file_system_with_version(self, file_system_id: str, chat_id: str = None, workspace_id: str = None, title: str = None,
                                   filename: str = None, content: str = None, author: str = 'system',
                                   comment: str = 'Initial version', folder: str = None,
                                   file_system_type: str = 'custom', tags=None, language: str = 'markdown'):
        """Create file_system metadata and initial version atomically."""
        owner_id = chat_id or workspace_id
        self._log_db_wrapper_op("CREATE_FILE_SYSTEM_WITH_VERSION_START", owner_id, f"file_system_id={file_system_id}")
        write_start = time.time()
        if isinstance(folder, list): folder = json.dumps(folder)
        if isinstance(tags, (list, dict)): tags = json.dumps(tags)

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute("BEGIN IMMEDIATE")
                try:
                    if workspace_id:
                        c.execute("SELECT 1 FROM file_systems WHERE id = ? AND workspace_id = ?", (file_system_id, workspace_id))
                        exists = c.fetchone() is not None
                        if exists:
                            c.execute("""
                                UPDATE file_systems SET
                                    title = ?, filename = ?, folder = ?, tags = ?, file_system_type = ?,
                                    current_version = ?, language = ?, navigation_history = ?, navigation_index = ?, timestamp = ?
                                WHERE id = ? AND workspace_id = ?
                            """, (title, filename, folder, tags, file_system_type, 1, language, '[1]', 0, time.time(), file_system_id, workspace_id))
                        else:
                            c.execute("""
                                INSERT INTO file_systems (id, chat_id, workspace_id, title, filename, timestamp, folder, tags, file_system_type, current_version, language, navigation_history, navigation_index)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (file_system_id, chat_id, workspace_id, title, filename, time.time(), folder, tags, file_system_type, 1, language, '[1]', 0))
                    else:
                        c.execute("SELECT 1 FROM file_systems WHERE id = ? AND chat_id = ?", (file_system_id, chat_id))
                        exists = c.fetchone() is not None
                        if exists:
                            c.execute("""
                                UPDATE file_systems SET
                                    title = ?, filename = ?, folder = ?, tags = ?, file_system_type = ?,
                                    current_version = ?, language = ?, navigation_history = ?, navigation_index = ?, timestamp = ?
                                WHERE id = ? AND chat_id = ?
                            """, (title, filename, folder, tags, file_system_type, 1, language, '[1]', 0, time.time(), file_system_id, chat_id))
                        else:
                            c.execute("""
                                INSERT INTO file_systems (id, chat_id, workspace_id, title, filename, timestamp, folder, tags, file_system_type, current_version, language, navigation_history, navigation_index)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (file_system_id, chat_id, workspace_id, title, filename, time.time(), folder, tags, file_system_type, 1, language, '[1]', 0))
                    
                    c.execute("""
                        INSERT INTO file_system_versions (file_system_id, chat_id, workspace_id, version_number, content, author, timestamp, comment)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (file_system_id, chat_id, workspace_id, 1, content, author, time.time(), comment))

                    if chat_id:
                        c.execute("UPDATE chats SET timestamp = ? WHERE id = ?", (time.time(), chat_id))
                    elif workspace_id:
                        c.execute("UPDATE workspaces SET timestamp = ? WHERE id = ?", (time.time(), workspace_id))

                    conn.commit()
                except:
                    conn.rollback()
                    raise
            finally:
                conn.close()

        _write()
        owner_key = f"ws:{workspace_id}" if workspace_id else f"chat:{chat_id}"
        cache_layer.invalidate("file_systems", f"{owner_key}:{file_system_id}")
        cache_layer.invalidate("file_systems", f"{owner_key}:{file_system_id}:versions")
        cache_layer.invalidate("file_systems", f"{owner_key}:{file_system_id}:current_version")
        cache_layer.invalidate("file_systems")
        return 1

    def get_owner_file_systems(self, chat_id: str = None, workspace_id: str = None):
        """Get all file_systems for a chat or workspace."""
        def _fetch():
            conn = make_connection()
            try:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                if workspace_id:
                    c.execute("SELECT * FROM file_systems WHERE workspace_id = ? ORDER BY timestamp DESC", (workspace_id,))
                else:
                    c.execute("SELECT * FROM file_systems WHERE chat_id = ? ORDER BY timestamp DESC", (chat_id,))
                return [dict(row) for row in c.fetchall()]
            finally:
                conn.close()
        return cache_layer.get_table("file_systems", _fetch, key_extractor=lambda row: row.get('id', ''), ttl=300)

    def get_chat_file_systems(self, chat_id: str):
        """Legacy wrapper for get_owner_file_systems"""
        return self.get_owner_file_systems(chat_id=chat_id)

    def get_file_system_versions(self, file_system_id: str, chat_id: str = None, workspace_id: str = None):
        """Get version history for a file_system."""
        def _fetch():
            conn = make_connection()
            try:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                if workspace_id:
                    c.execute("SELECT * FROM file_system_versions WHERE file_system_id = ? AND workspace_id = ? ORDER BY version_number DESC", (file_system_id, workspace_id))
                else:
                    c.execute("SELECT * FROM file_system_versions WHERE file_system_id = ? AND chat_id = ? ORDER BY version_number DESC", (file_system_id, chat_id))
                return [dict(row) for row in c.fetchall()]
            finally:
                conn.close()
        owner_key = f"ws:{workspace_id}" if workspace_id else f"chat:{chat_id}"
        return cache_layer.get("file_systems", f"{owner_key}:{file_system_id}:versions", _fetch, ttl=300)

    def get_file_system_content_by_id(self, file_system_id: str, chat_id: str = None, workspace_id: str = None):
        """Get the full content of the latest version of a file_system."""
        version = self.get_file_system_current_version(file_system_id, chat_id=chat_id, workspace_id=workspace_id)
        return version.get('content') if version else None

    def save_file_system_version(self, file_system_id: str, chat_id: str = None, workspace_id: str = None, version_number: int = 1,
                            content: str = None, author: str = 'system', comment: str = None):
        """Save a new version for an existing file_system."""
        owner_id = chat_id or workspace_id
        self._log_db_wrapper_op("SAVE_FILE_SYSTEM_VERSION_START", owner_id, f"file_system_id={file_system_id} v={version_number}")
        write_start = time.time()
        
        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute("BEGIN IMMEDIATE")
                try:
                    c.execute("""
                        INSERT INTO file_system_versions (file_system_id, chat_id, workspace_id, version_number, content, author, timestamp, comment)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (file_system_id, chat_id, workspace_id, version_number, content, author, time.time(), comment))
                    
                    if workspace_id:
                        c.execute("UPDATE file_systems SET current_version = ?, timestamp = ? WHERE id = ? AND workspace_id = ?", 
                                  (version_number, time.time(), file_system_id, workspace_id))
                        c.execute("UPDATE workspaces SET timestamp = ? WHERE id = ?", (time.time(), workspace_id))
                    else:
                        c.execute("UPDATE file_systems SET current_version = ?, timestamp = ? WHERE id = ? AND chat_id = ?", 
                                  (version_number, time.time(), file_system_id, chat_id))
                        c.execute("UPDATE chats SET timestamp = ? WHERE id = ?", (time.time(), chat_id))
                    
                    conn.commit()
                except:
                    conn.rollback()
                    raise
            finally:
                conn.close()

        _write()
        owner_key = f"ws:{workspace_id}" if workspace_id else f"chat:{chat_id}"
        cache_layer.invalidate("file_systems", f"{owner_key}:{file_system_id}:versions")
        cache_layer.invalidate("file_systems", f"{owner_key}:{file_system_id}:current_version")
        self._log_db_wrapper_op("SAVE_FILE_SYSTEM_VERSION_END", owner_id, f"file_system_id={file_system_id} duration_ms={(time.time() - write_start)*1000:.2f}")

    def sync_file_system_search_index(self, file_system_id: str, chat_id: str = None, workspace_id: str = None):
        """Synchronize the FTS5 search index for a file_system."""
        owner_id = chat_id or workspace_id
        self._log_db_wrapper_op("SYNC_FILE_SYSTEM_INDEX_START", owner_id, f"file_system_id={file_system_id}")
        
        meta = self.get_file_system_meta(file_system_id, chat_id=chat_id, workspace_id=workspace_id)
        content = self.get_file_system_content_by_id(file_system_id, chat_id=chat_id, workspace_id=workspace_id)
        
        if not meta or content is None:
            return False

        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute("DELETE FROM file_systems_search WHERE id = ?", (file_system_id,))
                c.execute("INSERT INTO file_systems_search (id, title, content) VALUES (?, ?, ?)", 
                          (file_system_id, meta['title'], content))
                conn.commit()
            except sqlite3.OperationalError:
                pass # FTS5 might be missing
            finally:
                conn.close()
        
        _write()
        return True

    def get_file_system_current_version(self, file_system_id: str, chat_id: str = None, workspace_id: str = None):
        """Get the current prioritized version of a file_system."""
        def _fetch():
            conn = make_connection()
            try:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                if workspace_id:
                    c.execute("SELECT current_version FROM file_systems WHERE id = ? AND workspace_id = ?", (file_system_id, workspace_id))
                else:
                    c.execute("SELECT current_version FROM file_systems WHERE id = ? AND chat_id = ?", (file_system_id, chat_id))
                row = c.fetchone()
                if row and row['current_version'] is not None:
                    if workspace_id:
                        c.execute("SELECT * FROM file_system_versions WHERE file_system_id = ? AND workspace_id = ? AND version_number = ?", (file_system_id, workspace_id, row['current_version']))
                    else:
                        c.execute("SELECT * FROM file_system_versions WHERE file_system_id = ? AND chat_id = ? AND version_number = ?", (file_system_id, chat_id, row['current_version']))
                    v_row = c.fetchone()
                    if v_row: return dict(v_row)
                
                if workspace_id:
                    c.execute("SELECT * FROM file_system_versions WHERE file_system_id = ? AND workspace_id = ? ORDER BY version_number DESC LIMIT 1", (file_system_id, workspace_id))
                else:
                    c.execute("SELECT * FROM file_system_versions WHERE file_system_id = ? AND chat_id = ? ORDER BY version_number DESC LIMIT 1", (file_system_id, chat_id))
                row = c.fetchone()
                return dict(row) if row else None
            finally:
                conn.close()
        owner_key = f"ws:{workspace_id}" if workspace_id else f"chat:{chat_id}"
        return cache_layer.get("file_systems", f"{owner_key}:{file_system_id}:current_version", _fetch, ttl=300)

    def delete_file_system(self, file_system_id: str, chat_id: str = None, workspace_id: str = None):
        """Delete a file_system and all associated data."""
        owner_id = chat_id or workspace_id
        self._log_db_wrapper_op("DELETE_FILE_SYSTEM_START", owner_id, f"file_system_id={file_system_id}")
        write_start = time.time()
        
        meta = self.get_file_system_meta(file_system_id, chat_id=chat_id, workspace_id=workspace_id)
        
        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute("BEGIN IMMEDIATE")
                try:
                    if workspace_id:
                        c.execute("DELETE FROM file_system_versions WHERE file_system_id = ? AND workspace_id = ?", (file_system_id, workspace_id))
                        c.execute("DELETE FROM file_system_permissions WHERE file_system_id = ? AND workspace_id = ?", (file_system_id, workspace_id))
                        c.execute("DELETE FROM file_systems WHERE id = ? AND workspace_id = ?", (file_system_id, workspace_id))
                    else:
                        c.execute("DELETE FROM file_system_versions WHERE file_system_id = ? AND chat_id = ?", (file_system_id, chat_id))
                        c.execute("DELETE FROM file_system_permissions WHERE file_system_id = ? AND chat_id = ?", (file_system_id, chat_id))
                        c.execute("DELETE FROM file_systems WHERE id = ? AND chat_id = ?", (file_system_id, chat_id))
                    
                    # FTS5 cleanup
                    try:
                        c.execute("DELETE FROM file_systems_search WHERE id = ?", (file_system_id,))
                    except sqlite3.OperationalError: pass
                    
                    if chat_id:
                        c.execute("UPDATE chats SET timestamp = ? WHERE id = ?", (time.time(), chat_id))
                    elif workspace_id:
                        c.execute("UPDATE workspaces SET timestamp = ? WHERE id = ?", (time.time(), workspace_id))
                    
                    conn.commit()
                except:
                    conn.rollback()
                    raise
            finally:
                conn.close()

        _write()
        owner_key = f"ws:{workspace_id}" if workspace_id else f"chat:{chat_id}"
        row_id = f"{owner_key}:{file_system_id}"
        cache_layer.invalidate("file_systems", row_id)
        cache_layer.invalidate("file_systems", f"{owner_key}:{file_system_id}:versions")
        cache_layer.invalidate("file_systems", f"{owner_key}:{file_system_id}:current_version")
        if meta and meta.get('filename'):
            cache_layer.invalidate("file_systems", f"{owner_key}:path:{meta['filename']}")
        # Invalidate full listing caches
        cache_layer.invalidate("file_systems")
        self._log_db_wrapper_op("DELETE_FILE_SYSTEM_END", owner_id, f"file_system_id={file_system_id} duration_ms={(time.time() - write_start)*1000:.2f}")

    def get_file_system_version_content(self, file_system_id: str, chat_id: str = None, workspace_id: str = None, version_number: int = 1):
        """Get the content of a specific file_system version."""
        def _fetch():
            conn = make_connection()
            try:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                if workspace_id:
                    c.execute("SELECT content FROM file_system_versions WHERE file_system_id = ? AND workspace_id = ? AND version_number = ?", 
                              (file_system_id, workspace_id, version_number))
                else:
                    c.execute("SELECT content FROM file_system_versions WHERE file_system_id = ? AND chat_id = ? AND version_number = ?", 
                              (file_system_id, chat_id, version_number))
                row = c.fetchone()
                return row['content'] if row else None
            finally:
                conn.close()
        owner_key = f"ws:{workspace_id}" if workspace_id else f"chat:{chat_id}"
        return cache_layer.get("file_systems", f"{owner_key}:{file_system_id}:v{version_number}", _fetch, ttl=300)

    def delete_file_system_versions_after(self, file_system_id: str, chat_id: str = None, workspace_id: str = None, up_to_version: int = 1):
        """Delete all versions after a certain number (for branching/restoring)."""
        owner_id = chat_id or workspace_id
        self._log_db_wrapper_op("DELETE_VERSIONS_AFTER_START", owner_id, f"file_system_id={file_system_id} up_to={up_to_version}")
        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute("BEGIN IMMEDIATE")
                try:
                    if workspace_id:
                        c.execute("DELETE FROM file_system_versions WHERE file_system_id = ? AND workspace_id = ? AND version_number > ?", 
                                  (file_system_id, workspace_id, up_to_version))
                        c.execute("UPDATE file_systems SET current_version = ? WHERE id = ? AND workspace_id = ?", 
                                  (up_to_version, file_system_id, workspace_id))
                    else:
                        c.execute("DELETE FROM file_system_versions WHERE file_system_id = ? AND chat_id = ? AND version_number > ?", 
                                  (file_system_id, chat_id, up_to_version))
                        c.execute("UPDATE file_systems SET current_version = ? WHERE id = ? AND chat_id = ?", 
                                  (up_to_version, file_system_id, chat_id))
                    conn.commit()
                    return c.rowcount
                except:
                    conn.rollback()
                    raise
            finally:
                conn.close()
        
        result = _write()
        owner_key = f"ws:{workspace_id}" if workspace_id else f"chat:{chat_id}"
        cache_layer.invalidate("file_systems", f"{owner_key}:{file_system_id}")
        cache_layer.invalidate("file_systems", f"{owner_key}:{file_system_id}:versions")
        cache_layer.invalidate("file_systems", f"{owner_key}:{file_system_id}:current_version")
        return result

    def delete_chat_file_system_files(self, chat_id: str):
        """Delete all file_system metadata for a chat."""
        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute("BEGIN IMMEDIATE")
                try:
                    c.execute("DELETE FROM file_systems WHERE chat_id = ?", (chat_id,))
                    c.execute("DELETE FROM file_system_versions WHERE chat_id = ?", (chat_id,))
                    conn.commit()
                except:
                    conn.rollback()
                    raise
            finally:
                conn.close()
        _write()
        cache_layer.invalidate("file_systems")
        return True

    def migrate_file_system_owner(self, old_id: str, new_id: str, old_chat_id: str, old_workspace_id: str, new_chat_id: str, new_workspace_id: str, new_filename: str, new_title: str):
        """Atomically migrate a file_system and its versions to a new owner and new ID."""
        old_owner_id = old_chat_id or old_workspace_id
        new_owner_id = new_chat_id or new_workspace_id
        self._log_db_wrapper_op("MIGRATE_FILE_SYSTEM_OWNER_START", new_owner_id, f"old_id={old_id} new_id={new_id}")
        
        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute("BEGIN IMMEDIATE")
                try:
                    # Update versions
                    if old_workspace_id:
                        c.execute("UPDATE file_system_versions SET file_system_id = ?, chat_id = ?, workspace_id = ? WHERE file_system_id = ? AND workspace_id = ?",
                                  (new_id, new_chat_id, new_workspace_id, old_id, old_workspace_id))
                    else:
                        c.execute("UPDATE file_system_versions SET file_system_id = ?, chat_id = ?, workspace_id = ? WHERE file_system_id = ? AND chat_id = ?",
                                  (new_id, new_chat_id, new_workspace_id, old_id, old_chat_id))

                    # Update permissions
                    if old_workspace_id:
                        c.execute("UPDATE file_system_permissions SET file_system_id = ?, chat_id = ?, workspace_id = ? WHERE file_system_id = ? AND workspace_id = ?",
                                  (new_id, new_chat_id, new_workspace_id, old_id, old_workspace_id))
                    else:
                        c.execute("UPDATE file_system_permissions SET file_system_id = ?, chat_id = ?, workspace_id = ? WHERE file_system_id = ? AND chat_id = ?",
                                  (new_id, new_chat_id, new_workspace_id, old_id, old_chat_id))

                    # Update main file_system metadata
                    if old_workspace_id:
                        c.execute("UPDATE file_systems SET id = ?, chat_id = ?, workspace_id = ?, filename = ?, title = ?, timestamp = ? WHERE id = ? AND workspace_id = ?",
                                  (new_id, new_chat_id, new_workspace_id, new_filename, new_title, time.time(), old_id, old_workspace_id))
                    else:
                        c.execute("UPDATE file_systems SET id = ?, chat_id = ?, workspace_id = ?, filename = ?, title = ?, timestamp = ? WHERE id = ? AND chat_id = ?",
                                  (new_id, new_chat_id, new_workspace_id, new_filename, new_title, time.time(), old_id, old_chat_id))
                    
                    if new_chat_id:
                        c.execute("UPDATE chats SET timestamp = ? WHERE id = ?", (time.time(), new_chat_id))
                    if new_workspace_id:
                        c.execute("UPDATE workspaces SET timestamp = ? WHERE id = ?", (time.time(), new_workspace_id))

                    conn.commit()
                except:
                    conn.rollback()
                    raise
            finally:
                conn.close()

        _write()
        
        # Invalidate old caches
        old_owner_key = f"ws:{old_workspace_id}" if old_workspace_id else f"chat:{old_chat_id}"
        cache_layer.invalidate("file_systems", f"{old_owner_key}:{old_id}")
        cache_layer.invalidate("file_systems", f"{old_owner_key}:{old_id}:versions")
        cache_layer.invalidate("file_systems", f"{old_owner_key}:{old_id}:current_version")
        
        # Invalidate new caches
        new_owner_key = f"ws:{new_workspace_id}" if new_workspace_id else f"chat:{new_chat_id}"
        cache_layer.invalidate("file_systems", f"{new_owner_key}:{new_id}")
        cache_layer.invalidate("file_systems", f"{new_owner_key}:{new_id}:versions")
        cache_layer.invalidate("file_systems", f"{new_owner_key}:{new_id}:current_version")
