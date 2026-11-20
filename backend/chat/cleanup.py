"""Removal of temporary chats that nobody saved or discarded (a tab that closed or crashed)."""
import logging
import time
from typing import Callable, List, Optional

from backend import config
from backend.database import db
from backend.logging import log_event
from backend.task_manager import task_manager

logger = logging.getLogger(__name__)

# At most this many chats are removed by one chat-list request (the rest go on the next one), so a listing stays quick.
MAX_REMOVED_PER_CALL = 20


def purge_expired_temporary_chats(user_id: str, delete_chat: Callable[[str], bool], now: Optional[float] = None) -> List[str]:
    """
    Delete one user's unsaved temporary chats older than `TEMPORARY_CHAT_TTL_SECONDS` (since their last activity).

    `delete_chat(chat_id)` removes a chat completely and returns False when it could not (its turn did not stop in time).
    A chat whose turn is running or being started (a send has claimed its turn) is skipped, never stopped, and a chat that
    was saved since it was looked up is skipped. A failure on one chat is logged and left for the next call; this never raises,
    so a listing that triggers it still answers. At most `MAX_REMOVED_PER_CALL` chats are removed per call. Returns the ids removed.
    """
    removed: List[str] = []
    try:
        cutoff = (time.time() if now is None else now) - config.TEMPORARY_CHAT_TTL_SECONDS
        expired = db.get_expired_temporary_chats(user_id, cutoff)
    except Exception as e:  # the listing must not fail because of housekeeping
        log_event("temporary_chat_purge_error", {"error": str(e)})
        logger.error(f"Could not look for expired temporary chats: {e}")
        return removed
    for chat_id in expired[:MAX_REMOVED_PER_CALL]:
        # Hold the chat's turn slot while it is removed: a send that arrives meanwhile is refused instead of writing into a deleted chat.
        if not task_manager.claim_turn(chat_id):
            continue
        try:
            if task_manager.is_task_running(chat_id):
                continue
            current = db.get_chat(chat_id)
            if not current or not current.get("is_temporary"):
                continue  # saved (or gone) since the lookup
            if delete_chat(chat_id):
                removed.append(chat_id)
                log_event("temporary_chat_expired", {"chat_id": chat_id})
        except Exception as e:
            log_event("temporary_chat_purge_error", {"chat_id": chat_id, "error": str(e)})
            logger.error(f"Could not remove the expired temporary chat {chat_id}: {e}")
        finally:
            task_manager.release_turn_claim(chat_id)
    return removed
