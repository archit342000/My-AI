"""
Tool implementations for user preference CRUD operations.
Orchestrates adding, editing, and deleting preferences via the database layer.
"""
import logging
from typing import Optional
from backend.database import db
from backend.logging import log_event

logger = logging.getLogger(__name__)


def _missing_owner(tool: str) -> str:
    """The tool result when the server did not supply the chat owner (the model never supplies it)."""
    log_event("tool_missing_owner", {"tool": tool})
    return f"Error: {tool} could not run because the chat has no owner."


def add_user_preference(content, tag, user_id: Optional[str] = None, **kwargs):
    """
    Adds a new preference or profile fact about the user.

    `user_id` is injected by the server from the chat owner; it is never a model argument.
    """
    if not user_id:
        return _missing_owner("add_user_preference")
    try:
        pref_id = db.add_preference(content, tag, user_id)
        all_prefs = db.get_all_preferences(user_id)
        pref_dump = "\n".join([f"[{m['id']}] ({m['tag']}) {m['content']}" for m in all_prefs])
        return f"Added preference [{pref_id[:8]}]: {content[:50]}\n\nCurrent User Preferences ({len(all_prefs)} entries):\n{pref_dump}"
    except Exception as e:
        logger.error(f"Failed to add user preference: {e}", exc_info=True)
        return f"Error: Failed to add user preference: {str(e)}"


def edit_user_preference(id, content, tag, user_id: Optional[str] = None, **kwargs):
    """
    Updates an existing user preference or profile entry (only the owner's own).
    """
    if not user_id:
        return _missing_owner("edit_user_preference")
    try:
        success = db.update_preference(id, content, tag, user_id)
        all_prefs = db.get_all_preferences(user_id)
        pref_dump = "\n".join([f"[{m['id']}] ({m['tag']}) {m['content']}" for m in all_prefs])
        status = "OK" if success else "NOT FOUND"
        return f"Updated preference [{id[:8]}]: {status}\n\nCurrent User Preferences ({len(all_prefs)} entries):\n{pref_dump}"
    except Exception as e:
        logger.error(f"Failed to edit user preference: {e}", exc_info=True)
        return f"Error: Failed to edit user preference: {str(e)}"


def delete_user_preference(id, user_id: Optional[str] = None, **kwargs):
    """
    Deletes an outdated or contradictory user preference (only the owner's own).
    """
    if not user_id:
        return _missing_owner("delete_user_preference")
    try:
        success = db.delete_preference(id, user_id)
        all_prefs = db.get_all_preferences(user_id)
        pref_dump = "\n".join([f"[{m['id']}] ({m['tag']}) {m['content']}" for m in all_prefs])
        status = "OK" if success else "NOT FOUND"
        return f"Deleted preference [{id[:8]}]: {status}\n\nCurrent User Preferences ({len(all_prefs)} entries):\n{pref_dump}"
    except Exception as e:
        logger.error(f"Failed to delete user preference: {e}", exc_info=True)
        return f"Error: Failed to delete user preference: {str(e)}"
