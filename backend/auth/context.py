"""The current user of a request or background task, held in a ContextVar."""
from contextlib import contextmanager
from contextvars import ContextVar, Token
from functools import wraps
from typing import Callable, Iterator, Optional

from flask import jsonify

_current_user: ContextVar[Optional[dict]] = ContextVar("current_user", default=None)


def set_current_user(user: Optional[dict]) -> Token:
    """Set the current user ({id, email, role}) and return the token for reset_current_user."""
    return _current_user.set(user)


def reset_current_user(token: Token) -> None:
    """Restore the user that was current before the matching set_current_user call."""
    _current_user.reset(token)


def current_user() -> Optional[dict]:
    """Return the current user dict, or None outside an authenticated request or task."""
    return _current_user.get()


def current_user_id() -> Optional[str]:
    """Return the current user's id, or None."""
    user = _current_user.get()
    return user["id"] if user else None


@contextmanager
def user_context(user: Optional[dict]) -> Iterator[None]:
    """Run a block (for example in a worker thread) as `user`, restoring the previous user afterwards."""
    token = set_current_user(user)
    try:
        yield
    finally:
        reset_current_user(token)


def admin_required(fn: Callable) -> Callable:
    """Route decorator: return 403 unless the current user is an admin."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or user.get("role") != "admin":
            return jsonify({"error": "Forbidden"}), 403
        return fn(*args, **kwargs)
    return wrapper
