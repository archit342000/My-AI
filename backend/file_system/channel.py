import asyncio
import logging
import threading
from typing import Dict, Optional
from .models import ChannelState
from backend import config

logger = logging.getLogger(__name__)

class FileSystemPersistenceChannel:
    """
    Chat-scoped channel with blocking, sequential operations.
    Each chat_id gets its own isolated channel instance.
    """

    def __init__(self, chat_id: str):
        self.chat_id = chat_id
        self.state = ChannelState.FREE
        self._lock = asyncio.Lock()
        self._condition = asyncio.Condition(lock=self._lock)
        self._current_operation: Optional[str] = None
        self._total_operations = 0
        self._total_wait_time = 0.0

    async def acquire(self, operation_type: str) -> bool:
        start_time = asyncio.get_event_loop().time()
        timeout = config.FILE_SYSTEM_CHANNEL_ACQUIRE_TIMEOUT

        async with self._condition:
            if self.state != ChannelState.FREE:
                try:
                    # wait_for(predicate) returns True when predicate is met.
                    # asyncio.wait_for raises TimeoutError if deadline is exceeded.
                    # On Python 3.12+, Condition.wait() properly re-acquires
                    # the lock before propagating CancelledError/TimeoutError.
                    await asyncio.wait_for(
                        self._condition.wait_for(lambda: self.state == ChannelState.FREE),
                        timeout=timeout
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        f"Chat {self.chat_id}: FileSystem channel acquire timed out "
                        f"after {timeout}s. Force-releasing stale lock "
                        f"(was: {self.state}, op: {self._current_operation})."
                    )
                    # Force-release the stale lock — the holder is assumed dead
                    self.state = ChannelState.FREE
                    self._current_operation = None

            if operation_type == "ai":
                self.state = ChannelState.LOCKED_AI
                self._current_operation = "ai_save"
            else:
                self.state = ChannelState.LOCKED_USER
                self._current_operation = "user_save"

            wait_time = asyncio.get_event_loop().time() - start_time
            self._total_wait_time += wait_time
            logger.debug(f"Chat {self.chat_id}: Acquired {operation_type} lock after {wait_time:.3f}s")
            return True


    async def release(self):
        async with self._condition:
            self.state = ChannelState.FREE
            self._current_operation = None
            self._total_operations += 1
            self._condition.notify_all()
            logger.debug(f"Chat {self.chat_id}: Released lock, total operations: {self._total_operations}")

    async def wait_if_blocked(self, operation_type: str) -> bool:
        async with self._condition:
            if self.state == ChannelState.FREE:
                return True
            current_type = "ai" if self.state == ChannelState.LOCKED_AI else "user"
            if current_type == operation_type:
                return True
            await self._condition.wait()
            return self.state == ChannelState.FREE

    def get_stats(self) -> dict:
        return {
            "chat_id": self.chat_id,
            "state": self.state.value,
            "current_operation": self._current_operation,
            "total_operations": self._total_operations,
            "total_wait_time": self._total_wait_time,
            "avg_wait_time": self._total_wait_time / max(1, self._total_operations)
        }

class FileSystemChannelManager:
    """Manages pool of per-chat channels."""
    _channels: Dict[str, FileSystemPersistenceChannel] = {}
    _max_channels = 100
    _initialized = False
    _lock = threading.RLock()

    @classmethod
    def initialize(cls):
        if cls._initialized:
            return
        with cls._lock:
            if cls._initialized:
                return
            cls._initialized = True
            logger.info("FileSystemChannelManager initialized")

    @classmethod
    def cleanup(cls):
        with cls._lock:
            cls._channels.clear()
            cls._initialized = False
            logger.info("FileSystemChannelManager cleaned up")

    @classmethod
    def get_channel(cls, chat_id: str) -> FileSystemPersistenceChannel:
        with cls._lock:
            if chat_id not in cls._channels:
                if len(cls._channels) >= cls._max_channels:
                    oldest_chat_id = next(iter(cls._channels))
                    del cls._channels[oldest_chat_id]
                cls._channels[chat_id] = FileSystemPersistenceChannel(chat_id)
            return cls._channels[chat_id]

    @classmethod
    def release_channel(cls, chat_id: str):
        with cls._lock:
            if chat_id in cls._channels:
                del cls._channels[chat_id]
                logger.info(f"Released channel for chat {chat_id}")

    @classmethod
    def cleanup_stale_channels(cls):
        """Remove channels for chats that no longer exist in the DB.
        Called from TaskManager's cleanup daemon thread — must be synchronous."""
        try:
            from backend.database import db
            active_chats = set(db.get_all_chat_ids())
            with cls._lock:
                stale = [cid for cid in cls._channels if cid not in active_chats]
                for cid in stale:
                    del cls._channels[cid]
                if stale:
                    logger.info(f"Cleaned up {len(stale)} stale file_system channels")
        except Exception as e:
            logger.error(f"Error during stale channel cleanup: {e}")
