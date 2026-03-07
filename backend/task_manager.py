import os
import json
import asyncio
import threading
import time
import inspect
from backend.storage import add_message
from backend.logger import log_event
from backend import config
from backend.cache_system import cache_system

TASKS_DIR = "./backend/tasks"
LOGS_DIR = "./backend/task_logs"

os.makedirs(TASKS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)


def _strip_images_from_messages(messages):
    """
    Returns a deep copy of messages with base64 image data replaced by a placeholder.
    """
    cleaned = []
    if not messages: return cleaned
    for msg in messages:
        msg_copy = dict(msg)
        content = msg_copy.get('content')
        if isinstance(content, list):
            new_parts = []
            for part in content:
                if isinstance(part, dict) and part.get('type') == 'image_url':
                    new_parts.append({
                        'type': 'image_url',
                        'image_url': {'url': '[image data stripped for storage]'}
                    })
                else:
                    new_parts.append(part)
            msg_copy['content'] = new_parts
        cleaned.append(msg_copy)
    return cleaned

class TaskManager:
    def __init__(self):
        self.interrupted_tasks = set()
        self.active_tasks = {} # chat_id -> asyncio.Task
    
    def stop_task(self, chat_id):
        self.interrupted_tasks.add(chat_id)
        
        # Proper asyncio cancellation
        task = self.active_tasks.get(chat_id)
        if task:
            try:
                loop = task.get_loop()
                loop.call_soon_threadsafe(task.cancel)
                log_event("task_stop_signal_sent", {"chat_id": chat_id})
            except Exception as e:
                log_event("task_stop_error", {"chat_id": chat_id, "error": str(e)})

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
        """Generic starter for any chat task (normal or deep research)."""
        cache_system.initialize_chat(chat_id)
        if chat_id in self.interrupted_tasks:
            self.interrupted_tasks.remove(chat_id)

        # Filter kwargs for persistent JSON storage (exclude complex objects like 'rag')
        persistent_info = {
            "chat_id": chat_id,
            "status": "running",
            "timestamp": time.time(),
        }

        # Explicitly copy serializable fields we care about
        for key in ['model', 'messages', 'approved_plan', 'search_depth_mode', 'vision_model', 'mode', 'memory_mode', 'has_vision', 'resume_state', 'model_name', 'api_url']:
            if key in kwargs:
                if key == 'messages':
                    persistent_info[key] = _strip_images_from_messages(kwargs[key])
                else:
                    persistent_info[key] = kwargs[key]

        # Save to disk
        with open(os.path.join(TASKS_DIR, f"{chat_id}.json"), "w") as f:
            json.dump(persistent_info, f)
            
        # Pass ALL kwargs (including objects) to the thread
        runtime_info = {**persistent_info, **kwargs}

        threading.Thread(target=self._run_task, args=(runtime_info, execute_fn), daemon=True).start()

    def start_research_task(self, model, messages, approved_plan, chat_id, search_depth_mode, vision_model, execute_fn, **kwargs):
        self.start_chat_task(
            chat_id,
            execute_fn,
            model=model,
            messages=messages,
            approved_plan=approved_plan,
            search_depth_mode=search_depth_mode,
            vision_model=vision_model,
            mode="research",
            **kwargs
        )
        
    def _run_task(self, task_info, execute_fn):
        chat_id = task_info["chat_id"]
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        lm_studio_url = config.LM_STUDIO_URL
        
        # Build kwargs for execution function
        fn_kwargs = {
            "api_url": task_info.get("api_url", lm_studio_url),
            "model": task_info.get("model"),
            "messages": task_info.get("messages"),
            "chat_id": chat_id
        }

        import inspect
        sig = inspect.signature(execute_fn)
        valid_kwargs = [p for p in sig.parameters]

        # Handle all task_info keys that should be passed as kwargs
        for key in ['approved_plan', 'search_depth_mode', 'vision_model', 'model_name', 'resume_state', 'rag_engine', 'extra_body', 'rag', 'memory_mode', 'has_vision']:
            if key in task_info and key in valid_kwargs:
                fn_kwargs[key] = task_info[key]

        async def consume():
            try:
                # Execution function call (may be sync or async generator)
                if inspect.iscoroutinefunction(execute_fn):
                    generator = await execute_fn(**fn_kwargs)
                else:
                    generator = execute_fn(**fn_kwargs)
                
                # Handle both sync (standard chat) and async (deep research) generators
                if inspect.isasyncgen(generator):
                    async for chunk in generator:
                        if chat_id in self.interrupted_tasks:
                            raise InterruptedError("Task stopped")
                        cache_system.append_chunk(chat_id, chunk)
                else:
                    for chunk in generator:
                        if chat_id in self.interrupted_tasks:
                            raise InterruptedError("Task stopped")
                        cache_system.append_chunk(chat_id, chunk)
                        await asyncio.sleep(0) # Allow cancellation check
                    
                task_info["status"] = "completed"
                final_content = cache_system.mark_completed(chat_id, cleanup=False)
                
                if final_content:
                     add_message(chat_id, 'assistant', final_content, model=task_info.get("model"))
                     if task_info.get("mode") != "research" and task_info.get("memory_mode"):
                        try:
                            msgs = task_info.get("messages", [])
                            user_content = ""
                            for m in reversed(msgs):
                                if m['role'] == 'user':
                                    c = m.get('content', '')
                                    if isinstance(c, str): user_content = c
                                    elif isinstance(c, list):
                                        user_content = next((p['text'] for p in c if p.get('type') == 'text'), "")
                                    break

                            if fn_kwargs.get("rag"):
                                clean_content = final_content
                                if "<think>" in final_content:
                                    import re
                                    clean_content = re.sub(r'<think>.*?</think>', '', final_content, flags=re.DOTALL).strip()
                                if user_content and clean_content:
                                    fn_kwargs["rag"].add_conversation_turn(user_content, clean_content, chat_id)
                        except Exception as e:
                            log_event("rag_update_error", {"error": str(e)})

            except (InterruptedError, asyncio.CancelledError):
                log_event("task_interrupted", {"chat_id": chat_id})
                task_info["status"] = "interrupted"
                task_info["error"] = "Task stopped by user."

            except Exception as e:
                import traceback
                traceback.print_exc()
                err_msg = json.dumps({"error": str(e)})
                cache_system.append_chunk(chat_id, f"data: {err_msg}\n\n")
                cache_system.append_chunk(chat_id, "[[ERROR]]")
                task_info["status"] = "failed"
                task_info["error"] = str(e)
                
                # Try to recover partial content/reasoning to preserve activities
                final_content = cache_system.mark_completed(chat_id, cleanup=False)
                if final_content:
                    add_message(chat_id, 'assistant', final_content + f"\n\n**Process interrupted by error:** {str(e)}", model=task_info.get("model"))
                else:
                    add_message(chat_id, 'assistant', f"Error: {str(e)}", model=task_info.get("model"))

            finally:
                cache_system.cleanup_chat(chat_id)
                if fn_kwargs.get("rag") and hasattr(fn_kwargs["rag"], "cleanup_chat"):
                    try: fn_kwargs["rag"].cleanup_chat(chat_id)
                    except: pass
                
                # Persist final state
                save_keys = ['chat_id', 'status', 'timestamp', 'model', 'messages', 'approved_plan', 
                           'search_depth_mode', 'vision_model', 'mode', 'memory_mode', 'has_vision', 
                           'resume_state', 'model_name', 'api_url', 'error']
                persistent_info = {k: v for k, v in task_info.items() if k in save_keys}
                try:
                    with open(os.path.join(TASKS_DIR, f"{chat_id}.json"), "w") as f:
                        json.dump(persistent_info, f)
                except: pass

        try:
            main_task = loop.create_task(consume())
            self.active_tasks[chat_id] = main_task
            loop.run_until_complete(main_task)
        except Exception:
            pass 
        finally:
            self.active_tasks.pop(chat_id, None)
            loop.close()

    def is_task_running(self, chat_id):
        if cache_system.is_active(chat_id):
            return True
        task_path = os.path.join(TASKS_DIR, f"{chat_id}.json")
        if os.path.exists(task_path):
            try:
                with open(task_path, "r") as f:
                    task = json.load(f)
                return task.get("status") == "running"
            except (json.JSONDecodeError, ValueError):
                log_event("task_file_corrupted", {"chat_id": chat_id})
                return False
        return False

    def recover_tasks(self):
        if not os.path.exists(TASKS_DIR): return
        for filename in os.listdir(TASKS_DIR):
            if filename.endswith(".json"):
                filepath = os.path.join(TASKS_DIR, filename)
                try:
                    with open(filepath, "r") as f:
                        task = json.load(f)
                    if task.get("status") == "running":
                        chat_id = task.get('chat_id', filename.replace('.json', ''))
                        task["status"] = "interrupted"
                        task["error"] = "Server restarted."
                        with open(filepath, "w") as f:
                            json.dump(task, f)
                        add_message(chat_id, 'assistant', "System: Task interrupted by server restart.")
                except:
                    pass

task_manager = TaskManager()
