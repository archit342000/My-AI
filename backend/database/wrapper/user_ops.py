import logging
import time
import uuid
from typing import Optional
from backend.database.db_layer import make_connection

logger = logging.getLogger(__name__)

_COLUMNS = "id, email, role, is_active, created_at"


def _row_to_user(row) -> dict:
    return {"id": row[0], "email": row[1], "role": row[2], "is_active": bool(row[3]), "created_at": row[4]}


class UserOpsMixin:
    """
    Mixin providing operations for the users table.
    Emails are trimmed and lower-cased on write; lookups are case-insensitive.
    """

    def get_user_by_email(self, email: str) -> Optional[dict]:
        """Return the user with this email (case-insensitive) or None."""
        try:
            with make_connection() as conn:
                row = conn.execute(
                    f"SELECT {_COLUMNS} FROM users WHERE email = ? COLLATE NOCASE", (email.strip(),)
                ).fetchone()
                return _row_to_user(row) if row else None
        except Exception as e:
            logger.error(f"UserOpsMixin.get_user_by_email error: {e}")
            raise

    def get_user(self, user_id: str) -> Optional[dict]:
        """Return the user with this id or None."""
        try:
            with make_connection() as conn:
                row = conn.execute(f"SELECT {_COLUMNS} FROM users WHERE id = ?", (user_id,)).fetchone()
                return _row_to_user(row) if row else None
        except Exception as e:
            logger.error(f"UserOpsMixin.get_user error: {e}")
            raise

    def create_user(self, email: str, role: str = "user") -> dict:
        """Create an active user. Raises sqlite3.IntegrityError for a duplicate email."""
        user_id = uuid.uuid4().hex
        email = email.strip().lower()
        try:
            with make_connection() as conn:
                conn.execute(
                    "INSERT INTO users (id, email, role, is_active, created_at) VALUES (?, ?, ?, 1, ?)",
                    (user_id, email, role, time.time()),
                )
                conn.commit()
        except Exception as e:
            logger.error(f"UserOpsMixin.create_user error: {e}")
            raise
        return self.get_user(user_id)

    def set_user_active(self, email: str, active: bool) -> bool:
        """Activate or deactivate a user. Returns False if no such user exists."""
        try:
            with make_connection() as conn:
                cur = conn.execute(
                    "UPDATE users SET is_active = ? WHERE email = ? COLLATE NOCASE",
                    (1 if active else 0, email.strip()),
                )
                conn.commit()
                return cur.rowcount > 0
        except Exception as e:
            logger.error(f"UserOpsMixin.set_user_active error: {e}")
            raise

    def list_users(self) -> list:
        """Return all users ordered by creation time."""
        try:
            with make_connection() as conn:
                rows = conn.execute(f"SELECT {_COLUMNS} FROM users ORDER BY created_at, email").fetchall()
                return [_row_to_user(r) for r in rows]
        except Exception as e:
            logger.error(f"UserOpsMixin.list_users error: {e}")
            raise

    def get_admin_user(self) -> Optional[dict]:
        """Return the first active admin (oldest first) or None."""
        try:
            with make_connection() as conn:
                row = conn.execute(
                    f"SELECT {_COLUMNS} FROM users WHERE role = 'admin' AND is_active = 1 "
                    "ORDER BY created_at, email LIMIT 1"
                ).fetchone()
                return _row_to_user(row) if row else None
        except Exception as e:
            logger.error(f"UserOpsMixin.get_admin_user error: {e}")
            raise
