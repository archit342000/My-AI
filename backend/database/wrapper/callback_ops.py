import time
import json
import logging
from backend.database.db_layer import make_connection

logger = logging.getLogger(__name__)


class CallbackOpsMixin:
    """Database operations for the pending_callbacks table."""

    def save_callback(self, callback_id: str, chat_id: str,
                      parent_message_id: int = None, parent_type: str = 'main',
                      tool_name: str = 'request_clarification',
                      question: str = '', options: list = None):
        """Persist a callback to DB for crash recovery."""
        conn = make_connection()
        try:
            c = conn.cursor()
            c.execute('''
                INSERT OR REPLACE INTO pending_callbacks
                (callback_id, chat_id, parent_message_id, parent_type,
                 tool_name, question, options, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            ''', (
                callback_id, chat_id, parent_message_id, parent_type,
                tool_name, question, json.dumps(options or []), time.time()
            ))
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to save callback {callback_id}: {e}")
        finally:
            conn.close()

    def get_callback_chat_id(self, callback_id: str) -> str | None:
        """Chat id a callback belongs to, or None when the callback is unknown."""
        conn = make_connection()
        try:
            row = conn.execute("SELECT chat_id FROM pending_callbacks WHERE callback_id = ?", (callback_id,)).fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def resolve_callback(self, callback_id: str, response: str):
        """Mark a callback as resolved with the user's response."""
        conn = make_connection()
        try:
            c = conn.cursor()
            c.execute('''
                UPDATE pending_callbacks
                SET status = 'resolved', response = ?, resolved_at = ?
                WHERE callback_id = ?
            ''', (response, time.time(), callback_id))
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to resolve callback {callback_id}: {e}")
        finally:
            conn.close()

    def get_pending_callbacks(self, chat_id: str):
        """Get all unresolved callbacks for a chat."""
        conn = make_connection()
        try:
            c = conn.cursor()
            c.execute(
                "SELECT * FROM pending_callbacks WHERE chat_id = ? AND status = 'pending'",
                (chat_id,)
            )
            cols = [desc[0] for desc in c.description]
            return [dict(zip(cols, row)) for row in c.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get pending callbacks for {chat_id}: {e}")
            return []
        finally:
            conn.close()

    def get_resolved_callback(self, callback_id: str):
        """Get a resolved callback's response (for crash recovery)."""
        conn = make_connection()
        try:
            c = conn.cursor()
            c.execute(
                "SELECT * FROM pending_callbacks WHERE callback_id = ? AND status = 'resolved'",
                (callback_id,)
            )
            row = c.fetchone()
            if row:
                cols = [desc[0] for desc in c.description]
                return dict(zip(cols, row))
            return None
        except Exception as e:
            logger.error(f"Failed to get resolved callback {callback_id}: {e}")
            return None
        finally:
            conn.close()

    def cleanup_callback(self, callback_id: str):
        """Remove a callback entry."""
        conn = make_connection()
        try:
            c = conn.cursor()
            c.execute("DELETE FROM pending_callbacks WHERE callback_id = ?", (callback_id,))
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to cleanup callback {callback_id}: {e}")
        finally:
            conn.close()

    def cleanup_chat_callbacks(self, chat_id: str):
        """Remove all callback entries for a chat."""
        conn = make_connection()
        try:
            c = conn.cursor()
            c.execute("DELETE FROM pending_callbacks WHERE chat_id = ?", (chat_id,))
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to cleanup callbacks for chat {chat_id}: {e}")
        finally:
            conn.close()
