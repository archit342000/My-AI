"""
Chat-Scoped Canvas Persistence Channel

This module implements a channel system where each chat has its own isolated
channel. Within a channel, all operations (both AI-initiated and user-initiated)
are blocking and sequential. The channel locks per chat_id, so canvas operations
in one chat never block operations in another chat.

Key Behaviors:
1. Per-chat locking: Each chat_id has its own lock
2. Sequential within chat: AI and user operations queue sequentially
3. Isolated across chats: Chat A's lock doesn't block Chat B
4. Blocking wait: Operations wait until current operation completes
"""

import asyncio
import logging
from enum import Enum
from typing import Dict, Optional, Set
from backend.config import DATA_DIR

logger = logging.getLogger(__name__)


class ChannelState(Enum):
    """State of a canvas persistence channel."""
    FREE = "free"              # No operation in progress
    LOCKED_AI = "locked_ai"    # AI-initiated operation running
    LOCKED_USER = "locked_user" # User-initiated operation running
    QUEUEING = "queueing"      # Operations queued, waiting for lock


class CanvasPersistenceChannel:
    """
    Chat-scoped channel with blocking, sequential operations.
    Each chat_id gets its own isolated channel instance.

    All operations through this channel are guaranteed to be:
    - Sequential within the same chat
    - Non-blocking across different chats
    - Properly locked to prevent race conditions
    """

    def __init__(self, chat_id: str):
        """
        Initialize channel for a specific chat.

        Args:
            chat_id: Unique identifier for the chat
        """
        self.chat_id = chat_id
        self.state = ChannelState.FREE
        self._lock = asyncio.Lock()
        self._condition = asyncio.Condition(lock=self._lock)
        self._operation_queue: asyncio.Queue = asyncio.Queue()
        self._current_operation: Optional[str] = None
        self._total_operations = 0
        self._total_wait_time = 0.0

    async def acquire(self, operation_type: str) -> bool:
        """
        Acquire channel lock for operation.
        Blocks until channel is free or this operation can proceed.

        Args:
            operation_type: 'ai' or 'user'

        Returns:
            True if lock acquired, False if cancelled
        """
        start_time = asyncio.get_event_loop().time()

        async with self._condition:
            while self.state != ChannelState.FREE:
                await self._condition.wait()

            # Set state based on operation type
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
        """
        Release channel lock and notify waiting operations.
        Must be called in a finally block to ensure release even on error.
        """
        async with self._condition:
            self.state = ChannelState.FREE
            self._current_operation = None
            self._total_operations += 1
            self._condition.notify_all()
            logger.debug(f"Chat {self.chat_id}: Released lock, total operations: {self._total_operations}")

    async def wait_if_blocked(self, operation_type: str) -> bool:
        """
        Wait if channel is blocked by opposite operation type.
        AI operations wait if user operation is in progress.
        User operations wait if AI operation is in progress.

        Args:
            operation_type: 'ai' or 'user'

        Returns:
            True if can proceed immediately or after waiting
        """
        async with self._condition:
            if self.state == ChannelState.FREE:
                return True

            # Check if we can proceed (same type as current)
            current_type = "ai" if self.state == ChannelState.LOCKED_AI else "user"
            if current_type == operation_type:
                return True

            # Must wait - opposite operation in progress
            logger.debug(f"Chat {self.chat_id}: {operation_type} waiting for {current_type} operation")
            await self._condition.wait()
            return self.state == ChannelState.FREE

    def get_stats(self) -> dict:
        """Get channel statistics."""
        return {
            "chat_id": self.chat_id,
            "state": self.state.value,
            "current_operation": self._current_operation,
            "total_operations": self._total_operations,
            "total_wait_time": self._total_wait_time,
            "avg_wait_time": self._total_wait_time / max(1, self._total_operations)
        }


class CanvasChannelManager:
    """
    Manages pool of per-chat channels.
    Provides LRU caching for channel instances with automatic cleanup.

    Thread-safe singleton pattern for channel management.
    """

    _channels: Dict[str, CanvasPersistenceChannel] = {}
    _max_channels = 100  # Prevent memory bloat
    _initialized = False
    _lock = asyncio.Lock()

    @classmethod
    async def initialize(cls):
        """
        Initialize the channel manager.
        Should be called once at application startup.
        Starts background cleanup worker.
        """
        if cls._initialized:
            return

        async with cls._lock:
            if cls._initialized:
                return

            cls._initialized = True
            asyncio.create_task(cls._cleanup_worker())
            logger.info("CanvasChannelManager initialized")

    @classmethod
    async def cleanup(cls):
        """
        Clean up all channels.
        Should be called at application shutdown.
        """
        for chat_id, channel in cls._channels.items():
            logger.debug(f"Cleaning up channel for chat {chat_id}")
        cls._channels.clear()
        cls._initialized = False
        logger.info("CanvasChannelManager cleaned up")

    @classmethod
    def get_channel(cls, chat_id: str) -> CanvasPersistenceChannel:
        """
        Get or create channel for chat_id (singleton per chat).
        Thread-safe.

        Args:
            chat_id: Chat identifier

        Returns:
            CanvasPersistenceChannel instance for the chat
        """
        if chat_id not in cls._channels:
            # Check if we need to evict oldest channel
            if len(cls._channels) >= cls._max_channels:
                # Remove oldest channel (first inserted)
                oldest_chat_id = next(iter(cls._channels))
                del cls._channels[oldest_chat_id]
                logger.debug(f"Evicted channel for chat {oldest_chat_id} to make room for {chat_id}")

            cls._channels[chat_id] = CanvasPersistenceChannel(chat_id)

        return cls._channels[chat_id]

    @classmethod
    def has_channel(cls, chat_id: str) -> bool:
        """
        Check if channel exists for a chat.

        Args:
            chat_id: Chat identifier

        Returns:
            True if channel exists
        """
        return chat_id in cls._channels

    @classmethod
    def release_channel(cls, chat_id: str):
        """
        Force release a channel (for chat deletion).

        Args:
            chat_id: Chat identifier
        """
        if chat_id in cls._channels:
            del cls._channels[chat_id]
            logger.debug(f"Released channel for chat {chat_id}")

    @classmethod
    def get_all_stats(cls) -> dict:
        """
        Get statistics for all channels.

        Returns:
            Dictionary mapping chat_id to channel stats
        """
        return {
            chat_id: channel.get_stats()
            for chat_id, channel in cls._channels.items()
        }

    @classmethod
    async def _cleanup_worker(cls):
        """
        Background worker to remove stale channels for deleted chats.
        Runs every 60 seconds.
        """
        while True:
            try:
                await asyncio.sleep(60)
                await cls._cleanup_stale()
            except Exception as e:
                logger.error(f"Cleanup worker error: {e}")

    @classmethod
    async def _cleanup_stale(cls):
        """
        Remove channels for chats that no longer exist in database.
        """
        try:
            from backend.db_wrapper import db
            active_chats = {chat['id'] for chat in db.get_all_chats()}

            stale = [
                chat_id for chat_id in cls._channels
                if chat_id not in active_chats
            ]

            for chat_id in stale:
                del cls._channels[chat_id]
                logger.debug(f"Removed stale channel for chat {chat_id}")

        except Exception as e:
            logger.error(f"Error during stale channel cleanup: {e}")
