import time
import uuid
import sqlite3
import logging
from ..db_layer import make_connection
from .base import BaseMixin
from .chat_ops import _require_user_id

class PreferenceOpsMixin(BaseMixin):
    """
    Mixin for User Preference operations (per-user facts).
    """

    def get_all_preferences(self, user_id: str) -> list:
        """Get one user's preferences from the database."""
        _require_user_id(user_id)
        self._log_db_wrapper_op("GET_ALL_PREFERENCES_START")
        fetch_start = time.time()
        def _fetch():
            conn = make_connection()
            try:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute("SELECT * FROM memories WHERE user_id = ? ORDER BY timestamp DESC", (user_id,))
                return [dict(row) for row in c.fetchall()]
            finally:
                conn.close()
        result = _fetch()
        self._log_db_wrapper_op("GET_ALL_PREFERENCES_END", None, f"count={len(result)} duration_ms={(time.time() - fetch_start)*1000:.2f}")
        return result

    def add_preference(self, content: str, tag: str, user_id: str) -> str:
        """Add a new preference owned by `user_id`."""
        _require_user_id(user_id)
        self._log_db_wrapper_op("ADD_PREFERENCE_START", None, f"tag={tag}")
        write_start = time.time()
        preference_id = str(uuid.uuid4())
        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute("BEGIN IMMEDIATE")
                try:
                    c.execute('INSERT INTO memories (id, content, tag, timestamp, user_id) VALUES (?, ?, ?, ?, ?)', 
                              (preference_id, content, tag, time.time(), user_id))
                    conn.commit()
                except:
                    conn.rollback()
                    raise
            finally:
                conn.close()
        _write()
        self._log_db_wrapper_op("ADD_PREFERENCE_END", None, f"preference_id={preference_id} duration_ms={(time.time() - write_start)*1000:.2f}")
        return preference_id

    def update_preference(self, preference_id: str, new_content: str, new_tag: str, user_id: str) -> bool:
        """Update a preference of `user_id`. Returns False when it does not exist or belongs to another user."""
        _require_user_id(user_id)
        self._log_db_wrapper_op("UPDATE_PREFERENCE_START", None, f"preference_id={preference_id}")
        write_start = time.time()
        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute("BEGIN IMMEDIATE")
                try:
                    c.execute('UPDATE memories SET content = ?, tag = ?, timestamp = ? WHERE id = ? AND user_id = ?', 
                              (new_content, new_tag, time.time(), preference_id, user_id))
                    count = c.rowcount
                    conn.commit()
                    return count > 0
                except:
                    conn.rollback()
                    raise
            finally:
                conn.close()
        result = _write()
        self._log_db_wrapper_op("UPDATE_PREFERENCE_END", None, f"preference_id={preference_id} updated={result} duration_ms={(time.time() - write_start)*1000:.2f}")
        return result

    def delete_preference(self, preference_id: str, user_id: str) -> bool:
        """Delete a preference of `user_id`. Returns False when it does not exist or belongs to another user."""
        _require_user_id(user_id)
        self._log_db_wrapper_op("DELETE_PREFERENCE_START", None, f"preference_id={preference_id}")
        write_start = time.time()
        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute("BEGIN IMMEDIATE")
                try:
                    c.execute("DELETE FROM memories WHERE id = ? AND user_id = ?", (preference_id, user_id))
                    count = c.rowcount
                    conn.commit()
                    return count > 0
                except:
                    conn.rollback()
                    raise
            finally:
                conn.close()
        result = _write()
        self._log_db_wrapper_op("DELETE_PREFERENCE_END", None, f"preference_id={preference_id} deleted={result} duration_ms={(time.time() - write_start)*1000:.2f}")
        return result

    def clear_preferences(self, user_id: str) -> int:
        """Delete all of one user's preferences; other users' preferences are untouched."""
        _require_user_id(user_id)
        self._log_db_wrapper_op("CLEAR_PREFERENCES_START")
        write_start = time.time()
        def _write():
            conn = make_connection()
            try:
                c = conn.cursor()
                c.execute("BEGIN IMMEDIATE")
                try:
                    c.execute("SELECT COUNT(*) FROM memories WHERE user_id = ?", (user_id,))
                    count = c.fetchone()[0]
                    c.execute("DELETE FROM memories WHERE user_id = ?", (user_id,))
                    conn.commit()
                    return count
                except:
                    conn.rollback()
                    raise
            finally:
                conn.close()
        deleted_count = _write()
        self._log_db_wrapper_op("CLEAR_PREFERENCES_END", None, f"deleted={deleted_count} duration_ms={(time.time() - write_start)*1000:.2f}")
        return deleted_count
