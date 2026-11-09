from datetime import datetime, timezone
from typing import List, Dict, Optional
from backend.database.db_layer import make_connection
from backend.database.wrapper.chat_ops import _require_user_id
import uuid

_PERSONA_COLUMNS = 'id, name, content, is_default, timestamp, research_mode, file_system_mode, browsing_mode, git_mode, code_execution_mode'

class PersonaOperations:
    def _row_to_dict(self, row) -> Dict:
        if not row: return None
        return {
            "id": row[0],
            "name": row[1],
            "content": row[2],
            "is_default": row[3],
            "timestamp": row[4],
            "research_mode": row[5] if len(row) > 5 else 0,
            "file_system_mode": row[6] if len(row) > 6 else 0,
            "browsing_mode": row[7] if len(row) > 7 else 0,
            "git_mode": row[8] if len(row) > 8 else 0,
            "code_execution_mode": row[9] if len(row) > 9 else 1
        }

    def get_all_personas(self, user_id: str) -> List[Dict]:
        """Get one user's personas."""
        _require_user_id(user_id)
        with make_connection() as conn:
            c = conn.cursor()
            c.execute(f'SELECT {_PERSONA_COLUMNS} FROM personas WHERE user_id = ? ORDER BY timestamp DESC', (user_id,))
            return [self._row_to_dict(row) for row in c.fetchall()]

    def get_persona(self, persona_id: str, user_id: str) -> Optional[Dict]:
        """Get a persona by ID; None when it does not exist or belongs to another user."""
        _require_user_id(user_id)
        with make_connection() as conn:
            c = conn.cursor()
            c.execute(f'SELECT {_PERSONA_COLUMNS} FROM personas WHERE id = ? AND user_id = ?', (persona_id, user_id))
            return self._row_to_dict(c.fetchone())

    def get_default_persona(self, user_id: str) -> Optional[Dict]:
        """Get the user's default persona if one exists (each user has their own default)."""
        _require_user_id(user_id)
        with make_connection() as conn:
            c = conn.cursor()
            c.execute(f'SELECT {_PERSONA_COLUMNS} FROM personas WHERE is_default = 1 AND user_id = ? LIMIT 1', (user_id,))
            return self._row_to_dict(c.fetchone())

    def persona_name_exists(self, name: str, user_id: str, exclude_id: str | None = None) -> bool:
        """
        Whether another persona of this user already uses this name (case-insensitive, ignoring surrounding spaces).

        Args:
            name: The candidate persona name.
            user_id: Owner whose personas are checked; other users' names do not count.
            exclude_id: A persona id to leave out, so updating a persona under its own name is allowed.

        Returns:
            True if a different persona has the same name.
        """
        _require_user_id(user_id)
        sql = 'SELECT 1 FROM personas WHERE LOWER(TRIM(name)) = LOWER(TRIM(?)) AND user_id = ?'
        params = [name, user_id]
        if exclude_id is not None:
            sql += ' AND id != ?'
            params.append(exclude_id)
        conn = make_connection()
        try:
            c = conn.cursor()
            c.execute(sql + ' LIMIT 1', params)
            return c.fetchone() is not None
        finally:
            conn.close()

    def create_persona(self, name: str, content: str, user_id: str, is_default: int = 0, research_mode: int = 0, file_system_mode: int = 0, browsing_mode: int = 0, git_mode: int = 0, code_execution_mode: int = 1) -> Dict:
        """Create a new persona owned by `user_id`. Making it the default clears only that user's other defaults."""
        _require_user_id(user_id)
        persona_id = "persona_" + uuid.uuid4().hex[:16]
        timestamp = datetime.now(timezone.utc).timestamp()
        
        if research_mode == 1:
            file_system_mode = 0
            browsing_mode = 0

        with make_connection() as conn:
            c = conn.cursor()
            
            # If making this default, clear the user's other defaults
            if is_default == 1:
                c.execute('UPDATE personas SET is_default = 0 WHERE user_id = ?', (user_id,))
                
            c.execute(
                'INSERT INTO personas (id, name, content, is_default, timestamp, research_mode, file_system_mode, browsing_mode, git_mode, code_execution_mode, user_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (persona_id, name, content, is_default, timestamp, research_mode, file_system_mode, browsing_mode, git_mode, code_execution_mode, user_id)
            )
            conn.commit()
            
        return {
            "id": persona_id,
            "name": name,
            "content": content,
            "is_default": is_default,
            "timestamp": timestamp,
            "research_mode": research_mode,
            "file_system_mode": file_system_mode,
            "browsing_mode": browsing_mode,
            "git_mode": git_mode,
            "code_execution_mode": code_execution_mode
        }

    def update_persona(self, persona_id: str, name: str, content: str, user_id: str, is_default: int = 0, research_mode: int = 0, file_system_mode: int = 0, browsing_mode: int = 0, git_mode: int = 0, code_execution_mode: int = 1) -> bool:
        """
        Update a persona of `user_id`. Returns False (changing nothing) when it does not exist or belongs to another user.

        The target row is updated first; only when it matched and is made the default are the user's other defaults cleared.
        """
        _require_user_id(user_id)
        if research_mode == 1:
            file_system_mode = 0
            browsing_mode = 0

        with make_connection() as conn:
            c = conn.cursor()
            
            c.execute(
                'UPDATE personas SET name = ?, content = ?, is_default = ?, research_mode = ?, file_system_mode = ?, browsing_mode = ?, git_mode = ?, code_execution_mode = ? WHERE id = ? AND user_id = ?',
                (name, content, is_default, research_mode, file_system_mode, browsing_mode, git_mode, code_execution_mode, persona_id, user_id)
            )
            matched = c.rowcount > 0
            if matched and is_default == 1:
                c.execute('UPDATE personas SET is_default = 0 WHERE user_id = ? AND id != ?', (user_id, persona_id))
            conn.commit()
            return matched

    def delete_persona(self, persona_id: str, user_id: str) -> bool:
        """Delete a persona of `user_id`. Returns False when it does not exist or belongs to another user."""
        _require_user_id(user_id)
        with make_connection() as conn:
            c = conn.cursor()
            c.execute('DELETE FROM personas WHERE id = ? AND user_id = ?', (persona_id, user_id))
            deleted = c.rowcount > 0
            conn.commit()
            return deleted
