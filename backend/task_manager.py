import os
import json
import asyncio
import threading
import time
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
    
    def stop_task(self, chat_id):
        self.interrupted_tasks.add(chat_id)
        task_path = os.path.join(TASKS_DIR, f"{chat_id}.json")
        if os.path.exists(task_path):
            with open(task_path, "r") as f:
                task = json.load(f)
            task["status"] = "interrupted"
            with open(task_path, "w") as f:
                json.dump(task, f)

    def start_chat_task(self, chat_id, execute_fn, **kwargs):
        """Generic starter for any chat task (normal or deep research)."""
        cache_system.initialize_chat(chat_id)

        task_info = {
            "chat_id": chat_id,
            "status": "running",
            "timestamp": time.time(),
            **kwargs
        }

        if "messages" in task_info:
            task_info["messages"] = _strip_images_from_messages(task_info["messages"])

        with open(os.path.join(TASKS_DIR, f"{chat_id}.json"), "w") as f:
            json.dump(task_info, f)
            
        threading.Thread(target=self._run_task, args=(task_info, execute_fn), daemon=True).start()

    def start_research_task(self, model, messages, approved_plan, chat_id, search_depth_mode, vision_model, execute_fn):
        self.start_chat_task(
            chat_id,
            execute_fn,
            model=model,
            messages=messages,
            approved_plan=approved_plan,
            search_depth_mode=search_depth_mode,
            vision_model=vision_model,
            mode="deep_research"
        )
        
    def _run_task(self, task_info, execute_fn):
        print(f"[DEBUG] Starting task {task_info['chat_id']}")
        chat_id = task_info["chat_id"]
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        lm_studio_url = config.LM_STUDIO_URL
        
        # Build kwargs for execution function
        fn_kwargs = {
            "api_url": lm_studio_url,
            "model": task_info.get("model"),
            "messages": task_info.get("messages"),
            "chat_id": chat_id
        }

        # Deep Research params
        if "approved_plan" in task_info:
            fn_kwargs["approved_plan"] = task_info["approved_plan"]
            fn_kwargs["search_depth_mode"] = task_info.get("search_depth_mode")
            fn_kwargs["vision_model"] = task_info.get("vision_model")

        # Normal Chat params (extracted from kwargs in start_chat_task)
        if "rag" in task_info:
             fn_kwargs["body_params"] = task_info.get("body_params", {})
             # Important: 'rag' passed in task_info is likely not thread-safe or picklable if it's an object.
             # However, start_chat_task is called from app.py where 'rag' is a global object reference.
             # Threading shares memory, so it's fine.
             fn_kwargs["rag"] = task_info.get("rag")
             fn_kwargs["memory_mode"] = task_info.get("memory_mode")
             fn_kwargs["has_vision"] = task_info.get("has_vision")

        try:
            generator = execute_fn(**fn_kwargs)
            
            async def consume():
                try:
                    async for chunk in generator:
                        if chat_id in self.interrupted_tasks:
                            raise InterruptedError("Task stopped")
                        
                        # print(f"[DEBUG] Chunk for {chat_id}: {chunk[:50]}")
                        cache_system.append_chunk(chat_id, chunk)

                    task_info["status"] = "completed"
                    final_content = cache_system.mark_completed(chat_id)
                    
                    print(f"[DEBUG] Task completed. Final content length: {len(final_content) if final_content else 0}")
                    
                    if final_content:
                         add_message(chat_id, 'assistant', final_content, model=task_info.get("model"))
                         print(f"[DEBUG] Message added to DB for {chat_id}")

                         if task_info.get("mode") != "deep_research" and task_info.get("memory_mode"):
                            try:
                                # Simple heuristic to get user message
                                msgs = task_info.get("messages", [])
                                user_content = ""
                                for m in reversed(msgs):
                                    if m['role'] == 'user':
                                        c = m.get('content', '')
                                        if isinstance(c, str): user_content = c
                                        elif isinstance(c, list):
                                            user_content = next((p['text'] for p in c if p.get('type') == 'text'), "")
                                        break
                                # Note: Actual RAG update logic usually requires the RAG object.
                                # If fn_kwargs["rag"] is valid, we could use it here.
                                if fn_kwargs.get("rag"):
                                    # Note: We are in a thread, rag.add_conversation_turn might be thread-safe or not.
                                    # Assuming ChromaDB client is thread-safe.
                                    # We need to extract the CLEAN content from final_content (remove <think> tags)
                                    clean_content = final_content
                                    if "<think>" in final_content:
                                        import re
                                        clean_content = re.sub(r'<think>.*?</think>', '', final_content, flags=re.DOTALL).strip()

                                    if user_content and clean_content:
                                        fn_kwargs["rag"].add_conversation_turn(user_content, clean_content, chat_id)
                            except Exception as e:
                                log_event("rag_update_error", {"error": str(e)})

                    with open(os.path.join(TASKS_DIR, f"{chat_id}.json"), "w") as f:
                        json.dump(task_info, f)

                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    err_msg = json.dumps({"error": str(e)})
                    cache_system.append_chunk(chat_id, f"data: {err_msg}\n\n")
                    cache_system.append_chunk(chat_id, "[[ERROR]]")
                    
                    task_info["status"] = "failed"
                    task_info["error"] = str(e)
                    with open(os.path.join(TASKS_DIR, f"{chat_id}.json"), "w") as f:
                        json.dump(task_info, f)
                    
                    add_message(chat_id, 'assistant', f"Error: {str(e)}", model=task_info.get("model"))

                finally:
                    if chat_id in self.interrupted_tasks:
                        self.interrupted_tasks.remove(chat_id)

            loop.run_until_complete(consume())
        except Exception as e:
             err_msg = json.dumps({"error": str(e)})
             cache_system.append_chunk(chat_id, f"data: {err_msg}\n\n")
             cache_system.append_chunk(chat_id, "[[ERROR]]")
        finally:
            loop.close()

    def is_task_running(self, chat_id):
        if cache_system.is_active(chat_id):
            return True
        task_path = os.path.join(TASKS_DIR, f"{chat_id}.json")
        if os.path.exists(task_path):
            with open(task_path, "r") as f:
                task = json.load(f)
            return task.get("status") == "running"
        return False

    def recover_tasks(self, execute_fn):
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
