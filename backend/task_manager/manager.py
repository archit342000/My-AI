import logging
import threading
import time
import os
import json
from typing import Dict, Any, Callable, Optional, Set
from backend.database import response_cache as cache_system
from backend import config
from .worker import TaskWorker

logger = logging.getLogger(__name__)

# Directory paths for task persistence
TASKS_DIR = os.path.join(config.DATA_DIR, "tasks")
try:
    os.makedirs(TASKS_DIR, exist_ok=True)
except Exception as e:
    import sys
    sys.stderr.write(f"WARNING: Failed to create task manager directories: {e}\n")

class TaskManager:
    """
    Modular Task Manager for managing background chat and researchturns.
    
    Responsibilities:
    - Lifecycle: Starting, stopping, and checking tasks.
    - Registry: Keeping track of active workers.
    - Persistence: Managing task state on disk.
    """
    
    def __init__(self):
        self._active_tasks: Dict[str, TaskWorker] = {}
        self._lock = threading.RLock()
        self.interrupted_tasks: Set[str] = set()
        self._claimed_turns: Set[str] = set()
        
        # Cache cleanup thread
        self._cleanup_running = True
        self._cleanup_thread = threading.Thread(target=self._run_cache_cleanup, daemon=True)
        self._cleanup_thread.start()

    def start_task(
        self, 
        chat_id: str, 
        execute_fn: Callable, 
        task_type: str = "chat",
        **kwargs
    ) -> bool:
        """Starts a task in a background thread."""
        with self._lock:
            if chat_id in self._active_tasks:
                if self._active_tasks[chat_id].is_alive():
                    logger.warning(f"Task for chat {chat_id} is already running.")
                    return False
                else:
                    self.pop_task(chat_id)

            if chat_id in self.interrupted_tasks:
                self.interrupted_tasks.remove(chat_id)

            worker = TaskWorker(chat_id, execute_fn, task_type, self, **kwargs)
            self._active_tasks[chat_id] = worker
            worker.start()
            return True

    def stop_task(self, chat_id: str):
        """Signals a task to stop."""
        with self._lock:
            self.interrupted_tasks.add(chat_id)
            if chat_id in self._active_tasks:
                self._active_tasks[chat_id].stop()

    def is_task_running(self, chat_id: str) -> bool:
        """Checks if a task is actively running in a thread."""
        with self._lock:
            worker = self._active_tasks.get(chat_id)
            return worker is not None and worker.is_alive()

    def claim_turn(self, chat_id: str) -> bool:
        """
        Claims the single turn slot of a chat. Returns False if a task is alive for the chat or
        another send already holds the claim. The caller holds the claim for the whole response
        and releases it with `release_turn_claim` when the response closes or the request fails;
        a live task blocks new claims on its own.
        """
        with self._lock:
            worker = self._active_tasks.get(chat_id)
            if chat_id in self._claimed_turns or (worker is not None and worker.is_alive()):
                return False
            self._claimed_turns.add(chat_id)
            return True

    def release_turn_claim(self, chat_id: str):
        """Releases a claim taken with `claim_turn`. Releasing an unclaimed chat is a no-op."""
        with self._lock:
            self._claimed_turns.discard(chat_id)

    def pop_task(self, chat_id: str):
        """Removes a task from the active registry."""
        with self._lock:
            self._active_tasks.pop(chat_id, None)

    def is_interrupted(self, chat_id: str) -> bool:
        """Checks if a task has been flagged for interruption."""
        return chat_id in self.interrupted_tasks

    def _run_cache_cleanup(self):
        """Background loop that cleans up expired cache entries."""
        while self._cleanup_running:
            try:
                # Provide a snapshot of active chat IDs to prevent "Ghost Subscribers"
                with self._lock:
                    active_ids = set(self._active_tasks.keys())
                cache_system.cleanup_expired(active_chat_ids=active_ids)

                # Stale file_system channel cleanup (relocated from FileSystemChannelManager)
                try:
                    from backend.file_system.channel import FileSystemChannelManager
                    FileSystemChannelManager.cleanup_stale_channels()
                except Exception as e:
                    logger.error(f"FileSystem channel cleanup error: {e}")
            except Exception as e:
                logger.error(f"Cache cleanup error: {e}")
            
            time.sleep(config.CACHE_CLEANUP_INTERVAL)

    def recover_tasks(self):
        """
        Recovers tasks that were running when the server crashed or restarted.
        
        Instead of just marking them as 'interrupted' and adding a system message,
        flags them as 'needs_resume'. The actual resume happens when the user
        loads the chat — get_history() detects resume_needed=True and the
        frontend shows a resume banner.
        """
        from backend.database import db
        try:
            if not os.path.exists(TASKS_DIR):
                return
        except Exception as e:
            logger.error(f"Failed to check task persistence directory: {e}")
            return

        logger.info("Task recovery initiated.")
        recovered_count = 0
        
        try:
            filenames = os.listdir(TASKS_DIR)
        except Exception as e:
            logger.error(f"Failed to list tasks persistence directory: {e}")
            return

        for filename in filenames:
            if filename.endswith(".json"):
                filepath = os.path.join(TASKS_DIR, filename)
                try:
                    with open(filepath, "r") as f:
                        task = json.load(f)

                    if task.get("status") == "running":
                        chat_id = task.get('chat_id', filename.replace('.json', ''))

                        # Mark as needing resume (NOT interrupted)
                        task["status"] = "needs_resume"
                        task["error"] = "Server restarted. Resume pending."

                        with open(filepath, "w") as f:
                            json.dump(task, f)

                        recovered_count += 1
                        logger.info(f"Task {chat_id} flagged for resume.")
                except Exception as e:
                    logger.error(f"Task recovery error for {filename}: {e}")
                    # Clean up corrupted state files
                    try:
                        os.remove(filepath)
                    except Exception:
                        pass

        if recovered_count:
            logger.info(f"Task recovery complete: {recovered_count} task(s) flagged for resume.")

