"""
One code run at a time, process-wide.

Every backend call to the code runner (runs, installs, package lists, live runs) takes the slot, so runs of different
users never overlap and a clean-up between runs never races another run. A user may hold at most
`CODE_RUNNER_MAX_QUEUED_PER_USER` places (the running one plus queued ones); more is refused at once, and a wait is bounded by
`CODE_RUNNER_QUEUE_TIMEOUT`.

`run_slot` is for threads (the live-run WebSocket); `async_run_slot` is for the tools running in a task worker's event
loop: it polls without blocking, so it never stalls the loop and never uses executor threads to wait.
"""
import asyncio
import threading
import time
from contextlib import asynccontextmanager, contextmanager
from typing import Dict, Optional

from backend import config


class RunQueueFull(Exception):
    """The user already holds the maximum number of places (running plus queued)."""


class RunQueueTimeout(Exception):
    """The slot did not become free within the queue timeout."""


_lock = threading.Lock()          # the slot itself
_guard = threading.Lock()         # protects _counts
_counts: Dict[str, int] = {}      # user id -> places held (running + queued)


def _enter(user_id: str) -> None:
    with _guard:
        if _counts.get(user_id, 0) >= config.CODE_RUNNER_MAX_QUEUED_PER_USER:
            raise RunQueueFull(user_id)
        _counts[user_id] = _counts.get(user_id, 0) + 1


def _leave(user_id: str) -> None:
    with _guard:
        remaining = _counts.get(user_id, 0) - 1
        if remaining > 0:
            _counts[user_id] = remaining
        else:
            _counts.pop(user_id, None)


@contextmanager
def run_slot(user_id: str, timeout: Optional[float] = None):
    """
    Hold the run slot for the block (blocking wait, for threads).

    Raises:
        RunQueueFull: the user already holds the maximum number of places.
        RunQueueTimeout: the slot was not free within `timeout` (default `CODE_RUNNER_QUEUE_TIMEOUT`); the block never runs.
    """
    wait = config.CODE_RUNNER_QUEUE_TIMEOUT if timeout is None else timeout
    _enter(user_id)
    acquired = False
    try:
        acquired = _lock.acquire(timeout=wait)
        if not acquired:
            raise RunQueueTimeout(user_id)
        yield
    finally:
        if acquired:
            _lock.release()
        _leave(user_id)


@asynccontextmanager
async def async_run_slot(user_id: str, timeout: Optional[float] = None, poll: float = 0.1):
    """
    Hold the run slot for the block without blocking the event loop (polls every `poll` seconds).

    A task cancelled while waiting never acquired the lock, so nothing leaks; once acquired, the release is in a `finally`.

    Raises:
        RunQueueFull, RunQueueTimeout: as for `run_slot`.
    """
    wait = config.CODE_RUNNER_QUEUE_TIMEOUT if timeout is None else timeout
    _enter(user_id)
    acquired = False
    try:
        deadline = time.monotonic() + wait
        while not _lock.acquire(blocking=False):
            if time.monotonic() >= deadline:
                raise RunQueueTimeout(user_id)
            await asyncio.sleep(poll)
        acquired = True
        yield
    finally:
        if acquired:
            _lock.release()
        _leave(user_id)
