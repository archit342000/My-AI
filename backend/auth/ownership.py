"""Owner checks for routes: only the owner of a chat or workspace may see or change it.

Every check returns None when the current user owns the row, otherwise a ready `(response, 404)` tuple, so a route
does `denied = require_chat_owner(chat_id); if denied: return denied`. A foreign id and a missing id look the same
(404), checks fail closed when there is no current user, and admins get no bypass.
"""
from typing import Optional

from flask import jsonify

from backend.auth.context import current_user_id
from backend.database import db
from backend.logging import log_event


def _not_found(message: str) -> tuple:
    return jsonify({"error": message}), 404


def _deny(kind: str, row_id: str, message: str) -> tuple:
    log_event("access_denied", {"kind": kind, "id": row_id})
    return _not_found(message)


def require_chat_owner(chat_id: str) -> Optional[tuple]:
    """
    Check that the current user owns `chat_id`.

    Returns:
        None when the user owns it, else a `(response, 404)` tuple (foreign or missing chat, or no user).
    """
    user_id = current_user_id()
    if not user_id:
        return _not_found("Chat not found")
    owner = db.get_chat_owner(chat_id)
    if owner is None:
        return _not_found("Chat not found")
    if owner != user_id:
        return _deny("chat", chat_id, "Chat not found")
    return None


def require_workspace_owner(workspace_id: str) -> Optional[tuple]:
    """
    Check that the current user owns `workspace_id`.

    Returns:
        None when the user owns it, else a `(response, 404)` tuple.
    """
    user_id = current_user_id()
    if not user_id:
        return _not_found("Workspace not found")
    owner = db.get_workspace_owner(workspace_id)
    if owner is None:
        return _not_found("Workspace not found")
    if owner != user_id:
        return _deny("workspace", workspace_id, "Workspace not found")
    return None


def claim_chat(chat_id: str) -> Optional[tuple]:
    """
    Create `chat_id` for the current user if it does not exist, and check that the current user owns it.

    Returns:
        None when the chat is (now) the current user's, else a 404 response (another user's chat, or no user).
    """
    user_id: Optional[str] = current_user_id()
    if not user_id:
        return _not_found("Chat not found")
    if db.ensure_chat_exists(chat_id, user_id) != user_id:
        return _deny("chat", chat_id, "Chat not found")
    return None


def reject_foreign_chat(chat_id: str) -> Optional[tuple]:
    """
    Refuse (404) an existing chat that belongs to someone else; let a missing chat or the user's own chat through.

    For routes that must validate input before `claim_chat` creates the chat, but must not let that validation reveal
    anything about another user's chat. Writes nothing.

    Returns:
        None when the chat is missing or the current user's, else a `(response, 404)` tuple (also with no user).
    """
    user_id = current_user_id()
    if not user_id:
        return _not_found("Chat not found")
    owner = db.get_chat_owner(chat_id)
    if owner is not None and owner != user_id:
        return _deny("chat", chat_id, "Chat not found")
    return None
