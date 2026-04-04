"""
Response Cache System with Write-Ahead Log (WAL) Support

This module implements a dual-layer caching system for active chat sessions:

1. In-Memory Cache: Stores recent chat chunks in memory for fast access during
   active conversations. Each chat has its own buffer with thread-safe locking.

2. Write-Ahead Log (WAL): A durability mechanism that writes chunks to disk
   immediately. The WAL serves two purposes:
   - Recovery: After a server restart, incomplete chats can be recovered
   -Streaming: Multiple subscribers can read from the same chat session

Architecture:
- Each active chat gets a unique chat_id
- Chunks are appended to both memory cache and WAL file
- Subscribers (HTTP streaming responses) connect to active chats
- TTL-based expiration automatically cleans up inactive sessions

Thread Safety:
- Global lock protects the cache dictionary
- Per-chat locks protect individual chat buffers and subscriber lists
- WAL writes are synchronous but non-blocking for cache operations

Usage Pattern:
1. initialize_chat(chat_id) - Start a new chat session
2. append_chunk(chat_id, data) - Add message chunks (streaming)
3. subscribe(chat_id) - Get a generator for streaming responses
4. mark_completed(chat_id) - Finalize and get complete content
5. cleanup_chat(chat_id) - Remove from cache and WAL

Alternatively, use cleanup_chat() directly to remove sessions without
recovery capability.
"""
import os
import json
import threading
import queue
import time
from backend.logger import log_event
from backend import config
from backend.db_wrapper import db

# WAL Directory - Stores Write-Ahead Log files for chat recovery
CACHE_DIR = os.path.join(config.DATA_DIR, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

class ResponseCache:
    """
    Manages in-memory buffers and WAL (Write-Ahead Log) for active chat sessions.

    This class implements the core cache logic with thread-safe operations and
    TTL-based expiration. It supports a publish-subscribe pattern where multiple
    clients can subscribe to a single chat's streaming responses.

    Key Concepts:
    - Chunks: Individual message pieces from the LLM (often token-by-token)
    - Subscribers: Active connections (HTTP streaming, SSE, etc.) receiving chunks
    - TTL (Time-To-Live): Automatic cleanup of inactive chats after configurable time

    Thread Safety:
    - self._lock: Protects the main cache dictionary (thread-safe access to chat entries)
    - chat['lock']: Per-chat lock protects that chat's chunks and subscribers list

    Example Usage:
        cache = ResponseCache()
        cache.initialize_chat("chat-123")
        cache.append_chunk("chat-123", {"choices": [{"delta": {"content": "Hello"}}]})
        for chunk in cache.subscribe("chat-123"):
            print(chunk)
    """
    def __init__(self):
        self._cache = {}  # chat_id -> {'chunks': [], 'subscribers': [], 'lock': Lock}
        self._lock = threading.Lock()

    def _get_wal_path(self, chat_id):
        """
        Get the file path for a chat's Write-Ahead Log.

        Args:
            chat_id: Unique identifier for the chat session

        Returns:
            str: Full path to the WAL file (e.g., "/data/cache/chat-123.wal")
        """
        return os.path.join(CACHE_DIR, f"{chat_id}.wal")

    def initialize_chat(self, chat_id, ttl_seconds=None, overwrite=True):
        """
        Initialize a new chat session in the cache.

        Creates an entry for the chat with empty buffers and sets up the WAL file.
        If a previous WAL exists (from a crashed session), it is cleared.

        Args:
            chat_id: Unique identifier for this chat session
            ttl_seconds: Time-to-live in seconds before automatic cleanup.
                        Uses config.CACHE_ENTRY_TTL_SECONDS if None.

        Cache Entry Structure:
            {
                'chunks': [],              # List of message chunks in order
                'subscribers': [],         # List of queue.Queue objects for subscribers
                'lock': threading.Lock(),  # Per-chat lock for thread safety
                'last_updated': float,     # Unix timestamp of last modification
                'status': 'active',        # Current status: 'active', 'recovered', 'completed'
                'ttl': float               # Time-to-live in seconds
            }
        """
        if ttl_seconds is None:
            ttl_seconds = config.CACHE_ENTRY_TTL_SECONDS

        with self._lock:
            if chat_id not in self._cache:
                self._cache[chat_id] = {
                    'chunks': [],
                    'subscribers': [],
                    'lock': threading.Lock(),
                    'last_updated': time.time(),
                    'status': 'active',
                    'ttl': ttl_seconds
                }
                # Handle WAL file initialization
                wal_path = self._get_wal_path(chat_id)
                if overwrite:
                    # Clear old WAL if exists
                    with open(wal_path, "w") as f:
                        f.write("")
                elif os.path.exists(wal_path):
                    # For resuming: Reconstruct memory cache from existing WAL
                    # to ensure history is available for new subscribers immediately
                    # without waiting for the first chunk.
                    self.recover_from_wal(chat_id, ttl_seconds)

    def append_chunk(self, chat_id, chunk_data):
        """
        Appends a chunk to the cache and WAL.
        Notifies all subscribers.
        Updates last_updated timestamp for TTL checking.
        """
        if chat_id not in self._cache:
            return  # Should have been initialized

        entry = {
            "timestamp": time.time(),
            "data": chunk_data
        }

        # Step 1: Update In-Memory Cache (fast path for subscribers)
        with self._cache[chat_id]['lock']:
            self._cache[chat_id]['chunks'].append(entry)
            self._cache[chat_id]['last_updated'] = time.time()

            # Step 2: Notify Subscribers (real-time delivery)
            # Each subscriber gets a copy of the chunk via their queue
            # If a queue is full (backpressure), silently drop to avoid blocking
            for q in self._cache[chat_id]['subscribers']:
                try:
                    q.put_nowait(chunk_data)
                except queue.Full:
                    pass

        # Step 3: Write to WAL (durability - disk I/O)
        try:
            with open(self._get_wal_path(chat_id), "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            log_event("wal_write_error", {"chat_id": chat_id, "error": str(e)})

    def subscribe(self, chat_id):
        """
        Subscribe to a chat's streaming responses.

        This method implements a publish-subscribe pattern where clients can
        receive real-time updates as chunks arrive. The subscription works as:

        1. Recovery Check: If chat isn't in memory but WAL exists, recover
        2. Expiration Check: Clean up and return empty if TTL expired
        3. History Replay: Send all existing chunks first (in-order)
        4. Live Streaming: Yield new chunks as they arrive

        Args:
            chat_id: The chat session to subscribe to

        Returns:
            generator: Yields chunk data as strings. Special markers:
                - "data: [DONE]\n\n" - Stream completed successfully
                - Error chunks (if any) - Stream encountered an error

        Raises:
            StopIteration: When the stream completes or chat not found

        Example:
            for chunk in cache.subscribe("chat-123"):
                print(chunk, end='', flush=True)
        """
        if chat_id not in self._cache:
            # Try to recover from WAL if exists but not in memory (e.g. after restart)
            if os.path.exists(self._get_wal_path(chat_id)):
                self.recover_from_wal(chat_id)
            else:
                return  # Empty generator - chat not active
        elif self._is_expired(chat_id):
            # Chat expired, clean up
            self.cleanup_chat(chat_id)
            return  # Empty generator - chat expired

        # Check again after potential recovery/expiry check
        if chat_id not in self._cache:
            return  # Empty generator - chat still not active

        # Create subscriber queue for this client
        q = queue.Queue()

        # Replay existing history to new subscriber (catch-up)
        with self._cache[chat_id]['lock']:
            for entry in self._cache[chat_id]['chunks']:
                q.put(entry['data'])
            self._cache[chat_id]['subscribers'].append(q)

        # Yield chunks as they arrive (live streaming)
        # This blocks until chunks are available or [[DONE]] is received
        try:
            while True:
                item = q.get()  # Blocks until item available
                if item == "[[DONE]]":
                    yield "data: [DONE]\n\n"
                    break
                if item == "[[ERROR]]":  # Sentinel for error
                    break
                yield item
        finally:
            # Cleanup: Remove subscriber from list when done
            # Ensures no memory leaks from abandoned subscriber references
            with self._cache[chat_id]['lock']:
                if q in self._cache[chat_id]['subscribers']:
                    self._cache[chat_id]['subscribers'].remove(q)

    def _is_expired(self, chat_id):
        """
        Check if a cache entry has exceeded its TTL.

        Args:
            chat_id: The chat session to check

        Returns:
            bool: True if expired or not found, False if still active
        """
        if chat_id not in self._cache:
            return True
        entry = self._cache[chat_id]
        ttl = entry.get('ttl', config.CACHE_ENTRY_TTL_SECONDS)
        last_updated = entry.get('last_updated', 0)
        return (time.time() - last_updated) > ttl

    def cleanup_expired(self):
        """
        Remove all expired cache entries.

        This is a cleanup routine that should be called periodically (e.g., via
        background task or cron) to reclaim memory and clean up old WAL files.
        """
        with self._lock:
            expired = [cid for cid in self._cache if self._is_expired(cid)]
            for cid in expired:
                self.cleanup_chat(cid)

    def recover_from_wal(self, chat_id, ttl_seconds=None):
        """
        Reconstruct cache state from WAL file after restart or crash.

        When the server restarts, active chat sessions are lost from memory.
        The WAL files preserve the chunks that were written before the crash.
        This method reads the WAL and rebuilds the in-memory cache.

        Args:
            chat_id: The chat session to recover
            ttl_seconds: Optional TTL override for the recovered session

        WAL Format:
            Each line is a JSON object: {"timestamp": float, "data": chunk_data}
            Lines are appended as chunks arrive (append_chunk)
        """
        wal_path = self._get_wal_path(chat_id)
        if not os.path.exists(wal_path):
            return

        chunks = []
        try:
            with open(wal_path, "r") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        chunks.append(entry)
                    except:
                        pass
        except Exception:
            pass

        if ttl_seconds is None:
            ttl_seconds = config.CACHE_ENTRY_TTL_SECONDS

        with self._lock:
            self._cache[chat_id] = {
                'chunks': chunks,
                'subscribers': [],      # No subscribers after recovery (new connections)
                'lock': threading.Lock(),
                'last_updated': time.time(),  # Reset timestamp for TTL
                'status': 'recovered',      # Mark as recovered for debugging
                'ttl': ttl_seconds
            }

    def mark_completed(self, chat_id, cleanup=True):
        """
        Finalizes a completed chat session and returns aggregated content.

        This method:
        1. Sends [[DONE]] marker to all subscribers
        2. Parses and aggregates all chunks into complete content
        3. Extracts reasoning blocks (if any) and formats output

        Args:
            chat_id: The chat session to finalize
            cleanup: If True, immediately deletes WAL and removes from memory.
                    If False, keeps the session for potential recovery.

        Returns:
            str: The aggregated full content, with reasoning blocks wrapped
                 in  and  tags if present.

        Note:
            This is called automatically by the response handler when the
            LLM stream completes. Manual calls should ensure the chat has
            already sent [[DONE]] to subscribers.
        """
        if chat_id not in self._cache:
            return None

        # Notify subscribers of completion
        self.append_chunk(chat_id, "[[DONE]]")

        # Aggregate content
        full_content = ""
        full_reasoning = ""

        with self._cache[chat_id]['lock']:
            chunks = self._cache[chat_id]['chunks']

        # Aggregate all chunks into complete content
        # Each chunk is a JSON string prefixed with "data: " (Server-Sent Events format)
        for entry in chunks:
            data = entry['data']
            if isinstance(data, str) and data.startswith("data: "):
                try:
                    if data.strip() == "data: [DONE]":
                        continue  # Skip completion marker
                    json_data = json.loads(data[6:])  # Remove "data: " prefix

                    # Skip chunks marked as internal (e.g. delegated researcher chunks)
                    if json_data.get('internal'):
                        continue

                    choices = json_data.get('choices', [])
                    content = ""
                    reasoning = ""
                    if choices:
                        delta = choices[0].get('delta', {})
                        content = delta.get('content', '')
                        # Handle both reasoning_content (standard) and reasoning (legacy)
                        reasoning = delta.get('reasoning_content', '') or delta.get('reasoning', '')

                        # Note: We NO LONGER skip research activity noise here.
                        # This ensures the research log is persistent in the database
                        # after the task completes, allowing UI rehydration on reload.
                        # Standard '🔍' snippets (meander prevention) are still skipped
                        # from the 'actual content' but preserved in reasoning if needed.
                        if reasoning and isinstance(reasoning, str) and '🔍' in reasoning:
                            continue

                        if content: full_content += content
                        if reasoning: full_reasoning += reasoning
                except:
                    # Chunk parsing failed, skip it
                    pass

        final_content = full_content
        if full_reasoning:
            final_content = f"<think>\n{full_reasoning}\n</think>\n{full_content}"

        if cleanup:
            self.cleanup_chat(chat_id)

        return final_content

    def cleanup_chat(self, chat_id):
        """
        Remove chat from cache and delete its WAL file.

        This is called automatically when:
        - A chat completes and cleanup=True
        - A chat expires based on TTL
        - Manual cleanup is required

        Args:
            chat_id: The chat session to clean up
        """
        with self._lock:
            if chat_id in self._cache:
                del self._cache[chat_id]

        try:
            wal_path = self._get_wal_path(chat_id)
            if os.path.exists(wal_path):
                os.remove(wal_path)
        except:
            pass

    def is_active(self, chat_id):
        return chat_id in self._cache

cache_system = ResponseCache()
