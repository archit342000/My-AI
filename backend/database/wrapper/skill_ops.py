import sqlite3
import time
import logging
from ..db_layer import make_connection
from .base import BaseMixin
from .chat_ops import _require_user_id

logger = logging.getLogger(__name__)

class SkillOpsMixin(BaseMixin):
    """
    Mixin for skill-level database operations (CRUD).
    """

    def add_skill(self, skill_id: str, name: str, description: str, instructions: str, user_id: str) -> bool:
        """
        Inserts a skill owned by `user_id`, or updates it when `skill_id` already exists and belongs to `user_id`.

        Returns:
            True when a row was written; False when `skill_id` belongs to another user (nothing is changed).
            A name already used by another skill of the same user raises `sqlite3.IntegrityError`.
        """
        _require_user_id(user_id)
        self._log_db_wrapper_op("ADD_SKILL_START", skill_id, f"name={name}")
        write_start = time.time()
        
        conn = make_connection()
        try:
            c = conn.cursor()
            c.execute("BEGIN IMMEDIATE")
            
            try:
                c.execute('''
                    INSERT INTO skills (id, name, description, instructions, timestamp, user_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        description = excluded.description,
                        instructions = excluded.instructions,
                        timestamp = excluded.timestamp
                    WHERE skills.user_id = excluded.user_id
                ''', (skill_id, name, description, instructions, time.time(), user_id))
                written = c.rowcount > 0

                c.execute("COMMIT")
            except Exception as e:
                c.execute("ROLLBACK")
                raise e
        finally:
            conn.close()

        db_write_duration = (time.time() - write_start) * 1000
        self._log_db_wrapper_op("ADD_SKILL_END", skill_id, f"written={written} duration_ms={db_write_duration:.2f}")
        return written

    def get_skill(self, skill_id: str, user_id: str) -> dict:
        """
        Retrieves a skill by its ID; None when it does not exist or belongs to another user.
        """
        _require_user_id(user_id)
        conn = make_connection()
        try:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM skills WHERE id = ? AND user_id = ?", (skill_id, user_id))
            row = c.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_skill_by_name(self, name: str, user_id: str) -> dict:
        """
        Retrieves one user's skill by its name (names are unique per user).
        """
        _require_user_id(user_id)
        conn = make_connection()
        try:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM skills WHERE name = ? AND user_id = ?", (name, user_id))
            row = c.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_all_skills(self, user_id: str) -> list:
        """
        Retrieves one user's skills ordered by timestamp descending.
        """
        _require_user_id(user_id)
        conn = make_connection()
        try:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM skills WHERE user_id = ? ORDER BY timestamp DESC", (user_id,))
            return [dict(row) for row in c.fetchall()]
        finally:
            conn.close()

    def delete_skill(self, skill_id: str, user_id: str) -> bool:
        """
        Deletes a skill of `user_id`. Returns False when it does not exist or belongs to another user.
        """
        _require_user_id(user_id)
        self._log_db_wrapper_op("DELETE_SKILL_START", skill_id)
        write_start = time.time()

        conn = make_connection()
        try:
            c = conn.cursor()
            c.execute("BEGIN IMMEDIATE")
            
            try:
                c.execute("DELETE FROM skills WHERE id = ? AND user_id = ?", (skill_id, user_id))
                deleted = c.rowcount > 0
                c.execute("COMMIT")
            except Exception as e:
                c.execute("ROLLBACK")
                raise e
        finally:
            conn.close()

        db_write_duration = (time.time() - write_start) * 1000
        self._log_db_wrapper_op("DELETE_SKILL_END", skill_id, f"deleted={deleted} duration_ms={db_write_duration:.2f}")
        return deleted
