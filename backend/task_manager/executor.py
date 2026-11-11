import json
import logging
import inspect
import asyncio
from typing import Any, Callable

from backend.database import db, response_cache
from backend.error_handling import USER_STREAM_ERROR
from backend.logging import log_event, error_detail

logger = logging.getLogger(__name__)

class TaskExecutor:
    """
    Executes the generation function and processes chunks.
    
    Handles:
    - SSE chunk caching.
    - Specialized signals (e.g., __FLUSH_SSE__).
    - Turn finalization in the DB.
    """
    def __init__(self, chat_id: str, execute_fn: Callable, manager: Any, kwargs: dict):
        self.chat_id = chat_id
        self.execute_fn = execute_fn
        self.manager = manager
        self.kwargs = kwargs

    async def run(self):
        """Runs the generator loop."""
        response_cache.initialize_chat(self.chat_id, overwrite=True)
        self._save_task_state("running")
        is_cancelled = False
        
        try:
            # 1. Start the generator
            if inspect.iscoroutinefunction(self.execute_fn):
                gen = await self.execute_fn(**self.kwargs)
            else:
                gen = self.execute_fn(**self.kwargs)

            # 2. Iterate through chunks
            if inspect.isasyncgen(gen):
                async for chunk in gen:
                    await self._process_chunk(chunk)
            else:
                for chunk in gen:
                    await self._process_chunk(chunk)
                    # Allow asyncio to process interruptions if sync generator
                    await asyncio.sleep(0)

        except asyncio.CancelledError:
            is_cancelled = True
            log_event("task_cancelled", {"chat_id": self.chat_id})
        except Exception as e:
            logger.error(f"Error in TaskExecutor for {self.chat_id}: {e}", exc_info=True)
            log_event("task_executor_error", {"chat_id": self.chat_id, "error": error_detail(e)})
            response_cache.append_chunk(self.chat_id, f"data: {json.dumps({'error': USER_STREAM_ERROR})}\n\n")
            response_cache.append_chunk(self.chat_id, "[[ERROR]]")
        finally:
            self._clear_task_state()
            # Ensure we signal the end of the stream to subscribers
            if not is_cancelled:
                response_cache.append_chunk(self.chat_id, "[[DONE]]")
            else:
                response_cache.append_chunk(self.chat_id, "[[ERROR]]")
            # Orphan sweep: clear any transient chunks left behind by interrupted or failed tasks
            response_cache.clear_sse_chunks(self.chat_id)

    def _save_task_state(self, status: str):
        """Persists task state to disk for recovery."""
        import os
        import time
        from backend.config import DATA_DIR
        tasks_dir = os.path.join(DATA_DIR, "tasks")
        os.makedirs(tasks_dir, exist_ok=True)
        
        task_file = os.path.join(tasks_dir, f"{self.chat_id}.json")
        state = {
            "chat_id": self.chat_id,
            "status": status,
            "model": self.kwargs.get("model_name") or self.kwargs.get("model"),
            "timestamp": time.time()
        }
        try:
            with open(task_file, "w") as f:
                json.dump(state, f)
        except Exception as e:
            logger.error(f"Failed to save task state: {e}")

    def _clear_task_state(self):
        """Removes task state from disk on completion."""
        import os
        from backend.config import DATA_DIR
        task_file = os.path.join(DATA_DIR, "tasks", f"{self.chat_id}.json")
        if os.path.exists(task_file):
            try: os.remove(task_file)
            except: pass

    async def _process_chunk(self, chunk: Any):
        """Processes a single yielded chunk from the generator."""
        if self.manager.is_interrupted(self.chat_id):
            raise asyncio.CancelledError("Task interrupted by manager signal.")

        # Regular SSE chunk or status update
        response_cache.append_chunk(self.chat_id, chunk)
