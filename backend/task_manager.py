import os
import json
import asyncio
import threading
from backend.storage import add_message
from backend.logger import log_event
from backend import config

TASKS_DIR = "./backend/tasks"
LOGS_DIR = "./backend/task_logs"

os.makedirs(TASKS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)


def _strip_images_from_messages(messages):
    """
    Returns a deep copy of messages with base64 image data replaced by a placeholder.
    Prevents enormous task JSON files (base64 images can be 100s of KB each).
    """
    cleaned = []
    for msg in messages:
        msg_copy = dict(msg)
        content = msg_copy.get('content')
        if isinstance(content, list):
            new_parts = []
            for part in content:
                if isinstance(part, dict) and part.get('type') == 'image_url':
                    # Replace the heavy base64 data with a lightweight placeholder
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
        self.active_queues = {} # chat_id -> list of SSE queues
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
                
    def start_research_task(self, model, model_name, messages, approved_plan, chat_id, search_depth_mode, vision_model, execute_fn):
        task_info = {
            "chat_id": chat_id,
            "model": model,
            "model_name": model_name,
            "vision_model": vision_model,
            "messages": _strip_images_from_messages(messages),
            "approved_plan": approved_plan,
            "search_depth_mode": search_depth_mode,
            "status": "running"
        }
        with open(os.path.join(TASKS_DIR, f"{chat_id}.json"), "w") as f:
            json.dump(task_info, f)
            
        with open(os.path.join(LOGS_DIR, f"{chat_id}.log"), "w") as f:
            f.write("") # Clear log
            
        threading.Thread(target=self._run_task, args=(task_info, execute_fn), daemon=True).start()
        
    def _run_task(self, task_info, execute_fn):
        chat_id = task_info["chat_id"]
        log_path = os.path.join(LOGS_DIR, f"{chat_id}.log")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        full_content = ""
        activity_reasoning = ""
        llm_reasoning = ""
        
        lm_studio_url = config.LM_STUDIO_URL

        generator = execute_fn(
            lm_studio_url, 
            task_info["model"], 
            task_info["messages"], 
            task_info["approved_plan"], 
            chat_id=chat_id, 
            search_depth_mode=task_info["search_depth_mode"],
            vision_model=task_info.get("vision_model")
        )
        
        async def consume():
            nonlocal full_content, activity_reasoning, llm_reasoning
            chunk_index = 0
            
            # --- Incremental Raw Streaming Backup ---
            raw_stream_backup_path = os.path.join(LOGS_DIR, f"{chat_id}_streaming_backup.txt")
            # Clear it out at start
            with open(raw_stream_backup_path, "w") as bf:
                bf.write("")
                
            last_backup_len = 0 # To track when we should append
            
            try:
                async for chunk in generator:
                    if chat_id in self.interrupted_tasks:
                        raise InterruptedError("Task was stopped by user.")
                    chunk_index += 1
                    # Write to log
                    with open(log_path, "a") as f:
                        f.write(json.dumps({"type": "chunk", "data": chunk, "index": chunk_index}) + "\n")
                        
                    # Accumulate logic for saving
                    try:
                        if isinstance(chunk, str) and chunk.startswith("data: "):
                            if chunk.strip() != "data: [DONE]":
                                data_json = json.loads(chunk[6:])
                                
                                # Handle accumulator reset (triggered by validation healing)
                                if data_json.get('__reset_accumulator__'):
                                    full_content = ""
                                    llm_reasoning = ""
                                    with open(raw_stream_backup_path, "w") as bf:
                                        bf.write("\n\n--- VALIDATION TRIGGERED REGENERATION / HEALING ---\n\n")
                                    continue
                                    
                                choices = data_json.get('choices', [])
                                if choices:
                                    delta = choices[0].get('delta', {})
                                    
                                    # Ensure deep research activity events are saved to the SQLite database
                                    reasoning_raw = delta.get('reasoning_content', '') or delta.get('reasoning', '') or ''
                                    
                                    new_content_char = ''
                                    new_reasoning_char = ''
                                    
                                    if 'content' in delta:
                                        new_content_char = delta.get('content', '') or ''
                                        full_content += new_content_char
                                    if reasoning_raw:
                                        new_reasoning_char = reasoning_raw
                                        
                                        is_activity = False
                                        try:
                                            parsed = json.loads(new_reasoning_char)
                                            if parsed.get('__deep_research_activity__'):
                                                is_activity = True
                                        except (json.JSONDecodeError, TypeError, AttributeError):
                                            pass
                                            
                                        if is_activity:
                                            activity_reasoning += new_reasoning_char
                                        else:
                                            llm_reasoning += new_reasoning_char
                                        
                                    # Incrementally dump to standard text file backup
                                    with open(raw_stream_backup_path, "a") as bf:
                                        if new_reasoning_char:
                                            bf.write(new_reasoning_char)
                                        if new_content_char:
                                            bf.write(new_content_char)
                                            
                    except:
                        pass
                    
                    # Notify active stream readers
                    if chat_id in self.active_queues:
                        for q in self.active_queues[chat_id]:
                            q.put((chunk, chunk_index))
                            
                # Finished successfully
                store_content = full_content
                full_reasoning = activity_reasoning + ("\n" + llm_reasoning if llm_reasoning else "")
                if full_reasoning.strip():
                    store_content = f"{full_content}\n<think>\n{full_reasoning}\n</think>"

                add_message(chat_id, 'assistant', store_content, model=task_info.get("model_name"))

                # Update status AFTER saving message to avoid race condition where frontend sees 'completed'
                # but DB doesn't have the message yet.
                task_info["status"] = "completed"
                with open(os.path.join(TASKS_DIR, f"{chat_id}.json"), "w") as f:
                    json.dump(task_info, f)

                with open(log_path, "a") as f:
                    f.write(json.dumps({"type": "done", "data": "DONE"}) + "\n")

                # Persist Finalized Raw Backup
                backup_path = os.path.join(LOGS_DIR, f"{chat_id}_final_backup.md")
                with open(backup_path, "w") as f:
                    f.write(store_content)
                
            except Exception as e:
                import traceback
                error_trace = traceback.format_exc()
                log_event("task_execution_error", {"chat_id": chat_id, "error": str(e), "traceback": error_trace})
                sse_err_msg = f'data: {json.dumps({"error": str(e)})}\n\n'
                with open(log_path, "a") as f:
                    f.write(json.dumps({"type": "error", "data": sse_err_msg}) + "\n")
                if chat_id in self.active_queues:
                    for q in list(self.active_queues.get(chat_id, [])):
                        # Push error with a distinctly high index so it always passes filter
                        q.put((sse_err_msg, float('inf')))
                
                task_info["status"] = "failed"
                task_info["error"] = str(e)
                with open(os.path.join(TASKS_DIR, f"{chat_id}.json"), "w") as f:
                    json.dump(task_info, f)
            finally:
                if chat_id in self.interrupted_tasks:
                    self.interrupted_tasks.remove(chat_id)
                if chat_id in self.active_queues:
                    for q in list(self.active_queues[chat_id]):
                        q.put(StopIteration)
        
        loop.run_until_complete(consume())
        loop.close()

    def stream_task(self, chat_id):
        import queue
        q = queue.Queue()
        
        if chat_id not in self.active_queues:
            self.active_queues[chat_id] = []
        
        # Step 1: Attach queue FIRST to capture any new chunks being produced.
        # This prevents the race condition where chunks generated between reading
        # the log file and attaching the queue would be lost.
        self.active_queues[chat_id].append(q)
        
        try:
            # Step 2: Read existing log for historical chunks
            log_path = os.path.join(LOGS_DIR, f"{chat_id}.log")
            max_log_index = 0
            
            if os.path.exists(log_path):
                with open(log_path, "r") as f:
                    for line in f:
                        try:
                            item = json.loads(line)
                            if item["type"] == "chunk":
                                yield item["data"]
                                if "index" in item and item["index"]:
                                    max_log_index = max(max_log_index, item["index"])
                            elif item["type"] == "error":
                                yield item["data"]
                                # If an error is found in the log, we should stop streaming
                                return
                            elif item["type"] == "done":
                                yield "data: [DONE]\n\n"
                                # If task is done, no need to consume from queue
                                return
                        except json.JSONDecodeError:
                            pass
            
            # Step 3: If the task already completed, no need to consume from queue
            task_path = os.path.join(TASKS_DIR, f"{chat_id}.json")
            if os.path.exists(task_path):
                with open(task_path, "r") as f:
                    task = json.load(f)
                if task.get("status") in ["completed", "failed", "interrupted"]:
                    return
            else:
                return
            
            # Step 4: Consume from the live queue.
            # The queue may contain chunks that were ALSO written to the log (overlap).
            # Skip any chunk whose index is <= max_log_index.
            while True:
                item = q.get()
                if item is StopIteration:
                    break
                    
                chunk, chunk_index = item
                if chunk_index <= max_log_index:
                    continue  # We already yielded this from the log file
                    
                yield chunk
        finally:
            if q in self.active_queues.get(chat_id, []):
                self.active_queues[chat_id].remove(q)

    def is_task_running(self, chat_id):
        task_path = os.path.join(TASKS_DIR, f"{chat_id}.json")
        if os.path.exists(task_path):
            with open(task_path, "r") as f:
                task = json.load(f)
            return task.get("status") == "running"
        return False

    def recover_tasks(self, execute_fn):
        """
        On server startup, handle any tasks that were left in 'running' state.
        Instead of blindly restarting (which wastes Tavily API credits and
        duplicates ChromaDB data), mark them as 'interrupted' so the user
        can decide to re-trigger from the UI.
        """
        for filename in os.listdir(TASKS_DIR):
            if filename.endswith(".json"):
                filepath = os.path.join(TASKS_DIR, filename)
                try:
                    with open(filepath, "r") as f:
                        task = json.load(f)
                    if task.get("status") == "running":
                        chat_id = task.get('chat_id', filename.replace('.json', ''))
                        log_event("task_recovery_interrupted", {"chat_id": chat_id})
                        
                        task["status"] = "interrupted"
                        task["error"] = "Server was restarted while this research task was running. Please re-trigger the research."
                        with open(filepath, "w") as f:
                            json.dump(task, f)
                        
                        # Write a user-facing error to the log so stream_task shows it
                        log_path = os.path.join(LOGS_DIR, f"{chat_id}.log")
                        with open(log_path, "a") as f:
                            err_chunk = f'data: {json.dumps({"error": "Research was interrupted by a server restart. Please start a new research session."})}'
                            f.write(json.dumps({"type": "error", "data": err_chunk}) + "\n")
                except Exception as e:
                    log_event("task_recovery_error", {"filename": filename, "error": str(e)})

task_manager = TaskManager()
