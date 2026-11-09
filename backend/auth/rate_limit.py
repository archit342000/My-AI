"""Per-user rate limits: a small in-memory fixed-window limiter, and the web-search limit check for tools."""
import math
import threading
import time
from typing import Callable, Dict, Optional, Tuple

from backend import config
from backend.database import db
from backend.logging import log_event

SEARCH_LIMIT_MESSAGE = "Error: Daily web search limit reached."


class SearchLimitReached(Exception):
    """Raised inside the research agent when the chat owner's daily web search limit is used up."""


class FixedWindowLimiter:
    """
    Counts hits per key in fixed windows. State is in memory (one app process; a restart resets the windows).

    A `limit` of zero or less means unlimited. A denied attempt does not count and does not move the window.
    """

    def __init__(self, limit: int, window_seconds: int, clock: Callable[[], float] = time.monotonic):
        self.limit = limit
        self.window_seconds = window_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._windows: Dict[str, Tuple[float, int]] = {}

    def try_acquire(self, key: str) -> Tuple[bool, int]:
        """
        Record one hit for `key` if the limit allows it.

        Returns:
            `(True, 0)` when allowed, else `(False, seconds until the window resets)` (at least 1).
        """
        if self.limit <= 0:
            return True, 0
        with self._lock:
            now = self._clock()
            start, count = self._windows.get(key, (now, 0))
            if now - start >= self.window_seconds:
                start, count = now, 0
            if count >= self.limit:
                return False, max(1, math.ceil(start + self.window_seconds - now))
            self._windows[key] = (start, count + 1)
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._windows.clear()


# Module singletons. Callers use them through this module (`rate_limit.turn_limiter`) so tests can replace them.
turn_limiter = FixedWindowLimiter(config.RATE_LIMIT_TURNS_PER_MINUTE, 60)
search_limiter = FixedWindowLimiter(config.RATE_LIMIT_SEARCHES_PER_DAY, 86400)


def reset_limiters() -> None:
    """Clear both singletons (tests)."""
    turn_limiter.reset()
    search_limiter.reset()


def is_exempt(user: Optional[dict]) -> bool:
    """True for an admin when `RATE_LIMIT_EXEMPT_ADMIN` is on."""
    return bool(user and user.get("role") == "admin" and config.RATE_LIMIT_EXEMPT_ADMIN)


def check_search_limit(chat_id: str) -> Optional[str]:
    """
    Count one web search against the chat owner's daily limit.

    Returns:
        None when the search may go ahead, else the short error message to return to the model. A chat without a
        known owner is refused too (fail closed).
    """
    owner = db.get_chat_owner(chat_id)
    user = db.get_user(owner) if owner else None
    if not user:
        log_event("rate_limited", {"kind": "searches"})
        return SEARCH_LIMIT_MESSAGE
    if is_exempt(user):
        return None
    allowed, _ = search_limiter.try_acquire(user["id"])
    if allowed:
        return None
    log_event("rate_limited", {"kind": "searches"})
    return SEARCH_LIMIT_MESSAGE
