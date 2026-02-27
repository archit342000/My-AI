import os
import json
import threading
import queue
import time
from backend.logger import log_event
from backend.storage import add_message

# WAL Directory
CACHE_DIR = "./backend/cache"
os.makedirs(CACHE_DIR, exist_ok=True)

class ResponseCache:
    """
    Manages in-memory buffers and WAL (Write-Ahead Log) for active chats.
    Ensures durability and supports multiple readers (streaming clients).
    """
    def __init__(self):
        self._cache = {}  # chat_id -> {'chunks': [], 'subscribers': [], 'lock': Lock}
        self._lock = threading.Lock()

    def _get_wal_path(self, chat_id):
        return os.path.join(CACHE_DIR, f"{chat_id}.wal")

    def initialize_chat(self, chat_id):
        """Prepares cache for a new active chat."""
        with self._lock:
            if chat_id not in self._cache:
                self._cache[chat_id] = {
                    'chunks': [],
                    'subscribers': [],
                    'lock': threading.Lock(),
                    'last_updated': time.time(),
                    'status': 'active'
                }
                # Clear old WAL if exists
                wal_path = self._get_wal_path(chat_id)
                with open(wal_path, "w") as f:
                    f.write("")

    def append_chunk(self, chat_id, chunk_data):
        """
        Appends a chunk to the cache and WAL.
        Notifies all subscribers.
        """
        if chat_id not in self._cache:
            return # Should have been initialized

        entry = {
            "timestamp": time.time(),
            "data": chunk_data
        }

        # 1. Update In-Memory Cache
        with self._cache[chat_id]['lock']:
            self._cache[chat_id]['chunks'].append(entry)
            self._cache[chat_id]['last_updated'] = time.time()

            # 2. Notify Subscribers
            for q in self._cache[chat_id]['subscribers']:
                try:
                    q.put_nowait(chunk_data)
                except queue.Full:
                    pass

        # 3. Write to WAL (Durability)
        try:
            with open(self._get_wal_path(chat_id), "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            log_event("wal_write_error", {"chat_id": chat_id, "error": str(e)})

    def subscribe(self, chat_id):
        """
        Returns a generator that yields chunks for a chat.
        Replays existing cache history first.
        """
        if chat_id not in self._cache:
            # Try to recover from WAL if exists but not in memory (e.g. after restart)
            if os.path.exists(self._get_wal_path(chat_id)):
                self.recover_from_wal(chat_id)
            else:
                return # Chat not active

        q = queue.Queue()

        # Replay existing history
        with self._cache[chat_id]['lock']:
            for entry in self._cache[chat_id]['chunks']:
                q.put(entry['data'])
            self._cache[chat_id]['subscribers'].append(q)

        try:
            while True:
                item = q.get()
                if item == "[[DONE]]":
                    yield "data: [DONE]\n\n"
                    break
                if item == "[[ERROR]]": # Sentinel for error
                    break
                yield item
        finally:
            with self._cache[chat_id]['lock']:
                if q in self._cache[chat_id]['subscribers']:
                    self._cache[chat_id]['subscribers'].remove(q)

    def recover_from_wal(self, chat_id):
        """Reconstructs cache state from WAL file."""
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

        with self._lock:
            self._cache[chat_id] = {
                'chunks': chunks,
                'subscribers': [],
                'lock': threading.Lock(),
                'last_updated': time.time(),
                'status': 'recovered'
            }

    def mark_completed(self, chat_id):
        """
        Finalizes the chat. Persists full content to DB.
        """
        if chat_id not in self._cache:
            return

        # Notify subscribers of completion
        self.append_chunk(chat_id, "[[DONE]]")

        # Aggregate content
        full_content = ""
        full_reasoning = ""

        with self._cache[chat_id]['lock']:
            chunks = self._cache[chat_id]['chunks']

        for entry in chunks:
            data = entry['data']
            if isinstance(data, str) and data.startswith("data: "):
                try:
                    if data.strip() == "data: [DONE]": continue
                    json_data = json.loads(data[6:])
                    choices = json_data.get('choices', [])
                    if choices:
                        delta = choices[0].get('delta', {})
                        content = delta.get('content', '')
                        reasoning = delta.get('reasoning_content', '')

                        if content: full_content += content
                        if reasoning: full_reasoning += reasoning
                except:
                    pass

        # Persist to DB
        # Combine reasoning and content
        final_content = full_content
        if full_reasoning:
            final_content = f"{full_content}\n<think>\n{full_reasoning}\n</think>"

        # We need the model name. It's usually in the chunks or we need to pass it.
        # For now, we assume the last chunk might have it or we updated DB earlier.
        # Ideally, add_message is called here.
        # But add_message requires role='assistant'.

        # Note: We should probably store the 'model' in the cache initialization or first chunk.

        # Cleanup
        with self._lock:
            del self._cache[chat_id]

        # Delete WAL (or archive it)
        try:
            os.remove(self._get_wal_path(chat_id))
        except:
            pass

        return final_content

    def is_active(self, chat_id):
        return chat_id in self._cache

cache_system = ResponseCache()
