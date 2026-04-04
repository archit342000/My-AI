"""
Task Manager Module

This module provides the TaskManager class for managing long-running chat and research tasks.
It handles task lifecycle, interruption, persistence, and execution in separate threads with
asyncio event loops.

Architecture Overview
---------------------
Tasks in this system represent long-running operations (chat conversations, deep research)
that need to be executed asynchronously without blocking the main thread. The architecture
follows these principles:

1. Thread Isolation: Each task runs in its own daemon thread with a dedicated asyncio
   event loop. This prevents tasks from interfering with each other and allows proper
   cancellation.

2. State Persistence: Task state is written to disk (JSON files) on every significant
   state change. This enables recovery after server crashes or restarts.

3. Chunk Streaming: Execution functions yield chunks of content that are streamed to
   the client via the cache system. This provides real-time feedback during long operations.

4. Transaction Safety: For operations requiring atomicity (like saving multiple messages),
   special "__TRANSACTION_MESSAGES__" chunks carry JSON payload that gets saved in a
   database transaction. If the transaction fails, UI content is redacted.

Key features:
- Task execution in isolated threads with their own asyncio event loops
- Task interruption and cancellation support
- Disk persistence of task state for recovery
- Chunk-based streaming responses from execution functions
- Transaction-based message batching for atomic database operations
- Graceful error handling with partial content recovery

Usage Pattern
-------------
1. Call start_chat_task() or start_research_task() to begin execution
2. Task runs in background thread with consume() processing chunks
3. User can interrupt task via stop_task() - sets interruption flag
4. On completion/failure, task state is persisted to disk
5. On server restart, recover_tasks() marks orphaned tasks as interrupted
"""

import os
import json
import asyncio
import threading
import time
import inspect
import logging
from backend.db_wrapper import db
from backend.logger import log_event
from backend import config
from backend.cache_system import cache_system
from backend.utils import strip_images_from_messages

logger = logging.getLogger(__name__)

# Background cache cleanup thread
_cache_cleanup_thread = None
_cache_cleanup_running = False

# Directory paths for task persistence and logging
TASKS_DIR = os.path.join(config.DATA_DIR, "tasks")
LOGS_DIR = os.path.join(config.DATA_DIR, "task_logs")

# Ensure directories exist for task storage and logs
os.makedirs(TASKS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)



class TaskManager:
    """
    Manages the lifecycle of chat and research tasks.

    Each task represents a long-running conversation or research operation associated
    with a unique chat_id. Tasks can be started, interrupted, and recovered after
    server restarts.

    Thread Safety:
    - interrupted_tasks: Protected by Python's GIL (safe for set operations)
    - active_tasks: Only accessed from the main thread during start/stop operations

    Attributes:
        interrupted_tasks: Set of chat_ids that have been marked for interruption.
        active_tasks: Dict mapping chat_ids to their running asyncio.Task objects.
    """

    def __init__(self):
        self.interrupted_tasks = set()
        self.active_tasks = {}  # chat_id -> asyncio.Task

    def __repr__(self):
        """String representation for debugging."""
        return f"<TaskManager active={len(self.active_tasks)} interrupted={len(self.interrupted_tasks)}>"
    
    def stop_task(self, chat_id):
        """
        Marks a task as interrupted and attempts to cancel its running asyncio task.

        This method performs three key operations:
        1. Adds the chat_id to interrupted_tasks set for quick checking during execution
        2. Cancels the associated asyncio task if it exists
        3. Updates the task's JSON file on disk to reflect the interrupted status

        Args:
            chat_id: Unique identifier for the chat/task to stop.
        """
        self.interrupted_tasks.add(chat_id)

        # Proper asyncio cancellation using thread-safe loop methods
        task = self.active_tasks.get(chat_id)
        if task:
            try:
                loop = task.get_loop()
                loop.call_soon_threadsafe(task.cancel)
                log_event("task_stop_signal_sent", {"chat_id": chat_id})
            except Exception as e:
                log_event("task_stop_error", {"chat_id": chat_id, "error": str(e)})

        # Update task state on disk to persist the interruption
        task_path = os.path.join(TASKS_DIR, f"{chat_id}.json")
        if os.path.exists(task_path):
            try:
                with open(task_path, "r") as f:
                    task_data = json.load(f)
                task_data["status"] = "interrupted"
                with open(task_path, "w") as f:
                    json.dump(task_data, f)
            except:
                pass

    def start_chat_task(self, chat_id, execute_fn, **kwargs):
        """
        Starts a new chat or research task in a background thread with its own event loop.

        This method:
        1. Initializes the cache system for the chat
        2. Clears any prior interruption state
        3. Serializes essential task info to disk (with images stripped from messages)
        4. Launches the task in a daemon thread with its own asyncio event loop

        Args:
            chat_id: Unique identifier for this chat session.
            execute_fn: The async or sync generator function to execute.
            **kwargs: Task parameters (model, messages, etc.) to pass to execute_fn.

        The function creates a persistent record on disk for task recovery after crashes.
        Complex objects (like RAG engines) are passed at runtime but not persisted.
        """
        # If we are resuming, we want to preserve the existing WAL for re-subscription
        is_resume = 'resume_state' in kwargs and kwargs['resume_state'] is not None
        cache_system.initialize_chat(chat_id, overwrite=(not is_resume))
        if chat_id in self.interrupted_tasks:
            self.interrupted_tasks.remove(chat_id)

        # Build persistent task info (only serializable data for disk storage)
        persistent_info = {
            "chat_id": chat_id,
            "status": "running",
            "timestamp": time.time(),
        }

        # Copy only serializable fields we need for persistence
        # Note: messages have images stripped; other complex objects excluded
        for key in ['model', 'messages', 'approved_plan', 'search_depth_mode', 'vision_model', 'vision_enabled', 'mode', 'memory_mode', 'has_vision', 'resume_state', 'model_name', 'api_url', 'api_key', 'canvas_mode', 'enable_thinking']:
            if key in kwargs:
                if key == 'messages':
                    persistent_info[key] = strip_images_from_messages(kwargs[key])
                else:
                    persistent_info[key] = kwargs[key]

        # Persist task info to disk for recovery after crashes
        with open(os.path.join(TASKS_DIR, f"{chat_id}.json"), "w") as f:
            json.dump(persistent_info, f)

        # Combine persistent data with runtime objects for thread execution
        runtime_info = {**persistent_info, **kwargs}

        # Start task in daemon thread (won't block program exit)
        threading.Thread(target=self._run_task, args=(runtime_info, execute_fn), daemon=True).start()

    def start_research_task(self, model, messages, approved_plan, chat_id, search_depth_mode, vision_model, execute_fn, vision_enabled=True, **kwargs):
        """
        Starts a deep research task with predefined research mode settings.

        This is a convenience wrapper around start_chat_task that sets mode="research"
        and passes research-specific parameters.

        Args:
            model: The model to use for research.
            messages: Conversation history and research queries.
            approved_plan: The research plan approved by the user.
            chat_id: Unique identifier for this research session.
            search_depth_mode: How deep the research should go.
            vision_model: Model for vision-based analysis (if applicable).
            vision_enabled: Whether to enable vision model for image analysis.
            execute_fn: The research execution function.
            **kwargs: Additional research parameters.
        """
        self.start_chat_task(
            chat_id,
            execute_fn,
            model=model,
            messages=messages,
            approved_plan=approved_plan,
            search_depth_mode=search_depth_mode,
            vision_model=vision_model,
            vision_enabled=vision_enabled,
            mode="research",
            **kwargs
        )
        
    def _run_task(self, task_info, execute_fn):
        """
        Main execution function that runs in a background thread with its own event loop.

        This method:
        1. Creates a new asyncio event loop (required for thread execution)
        2. Builds the kwargs dictionary for the execution function
        3. Dynamically determines which parameters the function accepts
        4. Runs the consume() async function to process the task

        Args:
            task_info: Dictionary containing all task data (from start_chat_task).
            execute_fn: The async/sync generator function to execute.
        """
        chat_id = task_info["chat_id"]

        # Each thread must have its own event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        ai_url = config.AI_URL

        # Build kwargs for execution function (runtime arguments)
        fn_kwargs = {
            "api_url": task_info.get("api_url", ai_url),
            "model": task_info.get("model"),
            "messages": task_info.get("messages"),
            "chat_id": chat_id
        }

        if "api_key" in task_info:
            fn_kwargs["api_key"] = task_info["api_key"]

        # Inspect the function signature to only pass valid parameters
        # This prevents errors when the function doesn't accept all possible args
        sig = inspect.signature(execute_fn)
        valid_kwargs = [p for p in sig.parameters]

        # Pass task_info keys that are both present and accepted by execute_fn
        for key in ['approved_plan', 'search_depth_mode', 'vision_model', 'vision_enabled', 'model_name', 'resume_state', 'rag_engine', 'extra_body', 'rag', 'memory_mode', 'has_vision', 'api_key', 'canvas_mode', 'active_canvas_context', 'research_mode', 'research_completed', 'initial_tool_calls', 'topic_override', 'enable_thinking']:
            if key in task_info and key in valid_kwargs:
                fn_kwargs[key] = task_info[key]

        async def consume():
            """
            Core task execution loop that processes chunks from the generator.

            This async function:
            1. Calls the execute_fn to get a generator
            2. Iterates over chunks (either async or sync)
            3. Checks for interruption after each chunk
            4. Handles special transaction message batches
            5. Appends regular chunks to the cache system

            Transaction messages allow batch-saving of multiple messages atomically
            via add_messages_batch(), avoiding partial message saves.

            Args:
                None

            Yields:
                Chunks from the execution function to the cache system.
            """
            generator = None
            transaction_messages = None
            try:
                # Execute the function - handle both async and sync generators
                if inspect.iscoroutinefunction(execute_fn):
                    # Async function - await the result which should be a generator
                    generator = await execute_fn(**fn_kwargs)
                else:
                    # Sync function - just call it directly
                    generator = execute_fn(**fn_kwargs)

                # Process chunks - handle both async generators (research) and sync (chat)
                if inspect.isasyncgen(generator):
                    async for chunk in generator:
                        # Check interruption - allows clean task cancellation
                        if chat_id in self.interrupted_tasks:
                            raise InterruptedError("Task stopped")

                        # Special chunks can carry transactional message batches
                        print(chunk)
                        if isinstance(chunk, str) and chunk.startswith("__TRANSACTION_MESSAGES__:"):
                            json_data = chunk[len("__TRANSACTION_MESSAGES__:"):]
                            if json_data:
                                try:
                                    transaction_messages = json.loads(json_data)
                                except json.JSONDecodeError as e:
                                    logger.error(f"Failed to parse transaction messages: {e}, data: {json_data[:100]}")
                                    transaction_messages = None
                            else:
                                transaction_messages = None
                        else:
                            # Regular content chunk - append to cache for streaming
                            cache_system.append_chunk(chat_id, chunk)
                else:
                    # Sync generator (standard chat) - iterate normally
                    for chunk in generator:
                        if chat_id in self.interrupted_tasks:
                            raise InterruptedError("Task stopped")

                        print(chunk)
                        if isinstance(chunk, str) and chunk.startswith("__TRANSACTION_MESSAGES__:"):
                            json_data = chunk[len("__TRANSACTION_MESSAGES__:"):]
                            if json_data:
                                try:
                                    transaction_messages = json.loads(json_data)
                                except json.JSONDecodeError as e:
                                    logger.error(f"Failed to parse transaction messages: {e}, data: {json_data[:100]}")
                                    transaction_messages = None
                            else:
                                transaction_messages = None
                        else:
                            cache_system.append_chunk(chat_id, chunk)
                            # Allow the event loop to process cancellation
                            await asyncio.sleep(0)

                task_info["status"] = "completed"
                final_content = cache_system.mark_completed(chat_id, cleanup=False)

                # If no transaction messages were yielded, use the old fallback method
                if transaction_messages is None:
                    if final_content:
                         db.add_message(chat_id, 'assistant', final_content, model=task_info.get("model"))
                else:
                    # Save all messages atomically in a single transaction
                    if transaction_messages:
                        success = db.add_messages_batch(chat_id, transaction_messages)
                        if not success:
                            # Transaction failed - this will trigger UI redaction
                            raise RuntimeError("Database transaction failed - messages not saved")

                    if task_info.get("mode") != "research" and task_info.get("memory_mode"):
                        try:
                            # Memory mode enabled - prepare for conversation memory updates
                            msgs = task_info.get("messages", [])
                            user_content = ""
                        except Exception as e:
                            log_event("cache_save_error", {"error": str(e)})

            except (InterruptedError, asyncio.CancelledError):
                # Task was interrupted by user or cancelled - log and mark as such
                log_event("task_interrupted", {"chat_id": chat_id})
                task_info["status"] = "interrupted"
                task_info["error"] = "Task stopped by user."

            except Exception as e:
                # Handle unexpected errors during task execution
                import traceback
                traceback.print_exc()  # Log full stack trace for debugging
                err_msg = json.dumps({"error": str(e)})

                # Send error to client for display
                cache_system.append_chunk(chat_id, f"data: {err_msg}\n\n")
                cache_system.append_chunk(chat_id, "[[ERROR]]")

                # Update task state to failed
                task_info["status"] = "failed"
                task_info["error"] = str(e)

                # If this was a transaction failure, we need to redact the UI content
                if "transaction failed" in str(e) or "Database transaction failed" in str(e):
                    # Send redact signal to clear UI content
                    cache_system.append_chunk(chat_id, '{"__redact__": true, "message": "Database transaction failed. Please try again."}')
                    cache_system.append_chunk(chat_id, "[[ERROR]]")
                    return  # Don't try to save partial content

                # Try to recover partial content/reasoning to preserve activities
                final_content = cache_system.mark_completed(chat_id, cleanup=False)
                if final_content:
                    db.add_message(chat_id, 'assistant', final_content + f"\n\n**Process interrupted by error:** {str(e)}", model=task_info.get("model"))
                else:
                    db.add_message(chat_id, 'assistant', f"Error: {str(e)}", model=task_info.get("model"))

            finally:
                # Clean up generator resources to prevent resource leaks
                if generator and hasattr(generator, 'aclose'):
                    try:
                        await generator.aclose()
                    except:
                        pass
                elif generator and hasattr(generator, 'close'):
                    try:
                        generator.close()
                    except:
                        pass

                # Cleanup cache and RAG resources
                cache_system.cleanup_chat(chat_id)
                if fn_kwargs.get("rag") and hasattr(fn_kwargs["rag"], "cleanup_chat"):
                    try:
                        fn_kwargs["rag"].cleanup_chat(chat_id)
                    except:
                        pass
                
                # Persist final task state for recovery after crashes
                save_keys = ['chat_id', 'status', 'timestamp', 'model', 'messages', 'approved_plan',
                           'search_depth_mode', 'vision_model', 'mode', 'memory_mode', 'has_vision',
                           'resume_state', 'model_name', 'api_url', 'error']
                persistent_info = {k: v for k, v in task_info.items() if k in save_keys}
                try:
                    with open(os.path.join(TASKS_DIR, f"{chat_id}.json"), "w") as f:
                        json.dump(persistent_info, f)
                except Exception:
                    pass  # Fail silently to avoid blocking cleanup

        # Run the consume task in the thread's event loop
        try:
            main_task = loop.create_task(consume())
            self.active_tasks[chat_id] = main_task
            loop.run_until_complete(main_task)
        except Exception:
            pass
        except asyncio.CancelledError:
            pass
        finally:
            # Clean up: remove from active tasks and cancel any remaining tasks
            self.active_tasks.pop(chat_id, None)
            try:
                # Cancel all remaining pending tasks in this loop to prevent leaks
                pending = asyncio.all_tasks(loop)
                for p in pending:
                    p.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception:
                pass
            loop.close()

    def is_task_running(self, chat_id):
        """
        Checks if a task is currently running or was interrupted mid-execution.

        A task is considered running if:
        1. The cache system reports it as active (recent activity), OR
        2. The task file on disk has status="running" (pending completion)

        This method helps avoid duplicate tasks for the same chat_id.

        Args:
            chat_id: The unique identifier of the task to check.

        Returns:
            True if the task is running or pending, False otherwise.
        """
        # Check cache system for active task (recent streaming activity)
        if cache_system.is_active(chat_id):
            return True

        # Check persisted task state from disk
        task_path = os.path.join(TASKS_DIR, f"{chat_id}.json")
        if os.path.exists(task_path):
            try:
                with open(task_path, "r") as f:
                    task = json.load(f)
                return task.get("status") == "running"
            except (json.JSONDecodeError, ValueError):
                # Task file is corrupted - log and return False
                log_event("task_file_corrupted", {"chat_id": chat_id})
                return False
        return False

    def recover_tasks(self):
        """
        Recovers tasks that were running when the server crashed or restarted.

        This method should be called on server startup to identify any tasks
        that were left in "running" state and mark them as interrupted.
        It also adds a system message to notify users of the interruption.

        This prevents orphaned tasks from appearing to be active indefinitely
        after an unexpected shutdown.
        """
        if not os.path.exists(TASKS_DIR):
            return

        # Scan all task JSON files
        for filename in os.listdir(TASKS_DIR):
            if filename.endswith(".json"):
                filepath = os.path.join(TASKS_DIR, filename)
                try:
                    with open(filepath, "r") as f:
                        task = json.load(f)

                    # If task was running when shutdown occurred, mark as interrupted
                    if task.get("status") == "running":
                        chat_id = task.get('chat_id', filename.replace('.json', ''))
                        task["status"] = "interrupted"
                        task["error"] = "Server restarted."

                        # Persist the updated state
                        with open(filepath, "w") as f:
                            json.dump(task, f)

                        # Notify user that task was interrupted by restart
                        logger.debug("[TASK] Adding recovery message to chat_id=%s", chat_id)
                        db.add_message(chat_id, 'assistant', "System: Task interrupted by server restart.", model=task.get("model"))
                except:
                    # Silently skip corrupted task files to avoid blocking recovery
                    pass

def start_cache_cleanup_thread():
    """
    Start the background cache cleanup thread.

    This thread periodically calls cache_system.cleanup_expired() to remove
    expired cache entries and prevent memory bloat.
    """
    global _cache_cleanup_thread, _cache_cleanup_running

    if _cache_cleanup_thread is not None:
        return  # Already running

    _cache_cleanup_running = True

    def cleanup_loop():
        """Background loop that cleans up expired cache entries."""
        while _cache_cleanup_running:
            try:
                cache_system.cleanup_expired()
            except Exception as e:
                log_event("cache_cleanup_error", {"error": str(e)})

            # Sleep for the cleanup interval
            time.sleep(config.CACHE_CLEANUP_INTERVAL)

    _cache_cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True, name="CacheCleanup")
    _cache_cleanup_thread.start()
    log_event("cache_cleanup_started", {"interval": config.CACHE_CLEANUP_INTERVAL})


def stop_cache_cleanup_thread():
    """
    Stop the background cache cleanup thread.
    """
    global _cache_cleanup_thread, _cache_cleanup_running

    _cache_cleanup_running = False
    if _cache_cleanup_thread is not None:
        _cache_cleanup_thread.join(timeout=2.0)
        _cache_cleanup_thread = None


# Global singleton instance for task management across the application
# This ensures consistent task state and prevents duplicate tasks
task_manager = TaskManager()

# Start cache cleanup thread on module load
start_cache_cleanup_thread()
