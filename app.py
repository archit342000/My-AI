from flask import Flask, request, jsonify, Response, send_from_directory
from backend.logger import log_event
import os
import time
import json
import requests
from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv()

from backend import config
from backend.rag import MemoryRAG, ResearchRAG
from backend.storage import init_db, get_all_chats, get_chat, save_chat, add_message, clear_messages, delete_chat, delete_all_chats, rename_chat
from backend.agents.research import generate_research_response
from backend.agents.chat import generate_chat_response
from backend.task_manager import task_manager
from backend.cache_system import cache_system

app = Flask(__name__, static_folder='static')
# Limit request size to 16MB to prevent unbounded payload DoS (e.g. extremely large JSON arrays)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Initialize components with config
init_db()
rag = MemoryRAG(persist_path=config.CHROMA_PATH, api_url=config.LM_STUDIO_URL, api_key=config.LM_STUDIO_API_KEY, embedding_model=config.EMBEDDING_MODEL)
research_rag = ResearchRAG(persist_path=config.CHROMA_PATH, api_url=config.LM_STUDIO_URL, api_key=config.LM_STUDIO_API_KEY, embedding_model=config.EMBEDDING_MODEL)
task_manager.recover_tasks()

@app.route('/')
@app.route('/chat/<chat_id>')
def index(chat_id=None):
    return send_from_directory('static', 'index.html')

@app.before_request
def require_auth():
    if not config.APP_PASSWORD:
        return
    auth = request.authorization
    if not auth or auth.password != config.APP_PASSWORD:
        return Response('Could not verify your access level for that URL.\n'
                        'You have to login with proper credentials', 401,
                        {'WWW-Authenticate': 'Basic realm="Login Required"'})

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

@app.route('/api/chats', methods=['GET'])
def list_chats():
    chats = get_all_chats()
    return jsonify(chats)

@app.route('/api/chats', methods=['DELETE'])
def clear_all_chats():
    # Get all chat IDs before deleting so we can clean up ChromaDB
    all_chats = get_all_chats()
    delete_all_chats()
    for chat in all_chats:
        research_rag.cleanup_chat(chat.get('id', ''))
    return jsonify({"success": True})

@app.route('/api/chats/<chat_id>', methods=['GET'])
def get_chat_details(chat_id):
    chat = get_chat(chat_id)
    if not chat:
        return jsonify({"error": "Chat not found"}), 404
    # Replaced task_manager.is_task_running logic with generic active status
    chat["is_research_running"] = task_manager.is_task_running(chat_id)
    return jsonify(chat)

@app.route('/api/chats/save', methods=['POST'])
def save_chat_endpoint():
    data = request.json
    chat_id = data.get('chat_id')
    title = data.get('title', 'New Chat')
    messages = data.get('messages')
    memory_mode = data.get('memory_mode', False)
    research_mode = data.get('research_mode', False)
    max_tokens = data.get('max_tokens', 16384)
    
    if not chat_id or '..' in chat_id or '/' in chat_id or '\\' in chat_id:
        return jsonify({"error": "Invalid or missing chat_id"}), 400
        
    save_chat(
        chat_id, 
        title, 
        time.time(), 
        memory_mode, 
        research_mode, 
        is_vision=data.get('is_vision', False),
        last_model=data.get('last_model'),
        vision_model=data.get('vision_model'),
        max_tokens=max_tokens,
        folder=data.get('folder')
    )
    
    if messages is not None:
        clear_messages(chat_id)
        for msg in messages:
            add_message(chat_id, msg['role'], msg['content'], msg.get('model'))
    
    return jsonify({"success": True})

@app.route('/api/chats/<chat_id>', methods=['PATCH'])
def patch_chat_endpoint(chat_id):
    data = request.json
    new_title = data.get('title')
    last_model = data.get('last_model')
    vision_model = data.get('vision_model')
    max_tokens = data.get('max_tokens')
    folder = data.get('folder')
    
    existing_chat = get_chat(chat_id)
    if not existing_chat:
        return jsonify({"error": "Chat not found"}), 404
        
    # Block model changes in Research
    if existing_chat.get('research_mode'):
        if last_model and last_model != existing_chat.get('last_model'):
             return jsonify({"error": "Model cannot be changed in Research"}), 400
        if vision_model and vision_model != existing_chat.get('vision_model'):
             return jsonify({"error": "Vision model cannot be changed in Research"}), 400
             
    if new_title:
        rename_chat(chat_id, new_title)
    if last_model:
        from backend.storage import update_chat_model
        update_chat_model(chat_id, last_model)
    if vision_model:
        from backend.storage import update_chat_vision_model
        update_chat_vision_model(chat_id, vision_model)
    if max_tokens is not None:
        from backend.storage import update_chat_max_tokens
        update_chat_max_tokens(chat_id, max_tokens)
    if 'folder' in data:
        from backend.storage import update_chat_folder
        update_chat_folder(chat_id, data['folder'])
        
    if not new_title and not last_model and not vision_model and max_tokens is None and 'folder' not in data:
        return jsonify({"error": "Missing fields"}), 400
        
    return jsonify({"success": True})

@app.route('/api/chats/<chat_id>', methods=['DELETE'])
def remove_chat(chat_id):
    delete_chat(chat_id)
    research_rag.cleanup_chat(chat_id)
    return jsonify({"success": True})

@app.route('/api/chats/<chat_id>/stop', methods=['POST'])
def stop_chat_endpoint(chat_id):
    task_manager.stop_task(chat_id)
    from backend.storage import delete_last_turn
    delete_last_turn(chat_id)
    return jsonify({"success": True})

@app.route('/api/chats/<chat_id>/discard', methods=['POST'])
def discard_research_endpoint(chat_id):
    """
    Killed a research task, wipe state files, clean RAG, 
    and reset chat to just the first user message.
    """
    # 1. Stop the task if running
    task_manager.stop_task(chat_id)
    
    # 2. Cleanup state files
    import re
    safe_chat_id = re.sub(r'[^a-zA-Z0-9_\-]', '', str(chat_id))
    state_path = os.path.join(config.DATA_DIR, "tasks", f"{safe_chat_id}_state.json")
    task_path = os.path.join(config.DATA_DIR, "tasks", f"{chat_id}.json")
    if os.path.exists(state_path): os.remove(state_path)
    if os.path.exists(task_path): os.remove(task_path)
    
    # 3. Cleanup RAG and active cache
    research_rag.cleanup_chat(chat_id)
    cache_system.cleanup_chat(chat_id)
    
    # 4. Cleanup messages: Wipe and allow restart
    clear_messages(chat_id)
    return jsonify({"success": True})

@app.route('/api/memory/reset', methods=['POST'])
def reset_memory():
    success = rag.reset_memory()
    return jsonify({"success": success})

@app.route('/api/memory/debug', methods=['GET'])
def debug_memory():
    try:
        results = rag.collection.get()
        return jsonify({
            "count": len(results['ids']),
            "documents": results['documents'],
            "metadatas": results['metadatas']
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

import httpx

@app.route('/api/v1/models', methods=['GET'])
@app.route('/v1/models', methods=['GET'])
def proxy_get_models():
    """Proxy GET models endpoints to LM Studio, injecting the API key."""
    api_url = config.LM_STUDIO_URL.rstrip("/")
    
    base_url = api_url[:-3] if api_url.endswith('/v1') else api_url
    endpoint = f"{base_url}{request.path}"
    headers = {"Content-Type": "application/json"}
    if config.LM_STUDIO_API_KEY:
        headers["Authorization"] = f"Bearer {config.LM_STUDIO_API_KEY}"
        
    try:
        response = requests.get(endpoint, headers=headers, timeout=10)
        return Response(response.content, status=response.status_code, content_type=response.headers.get('content-type', 'application/json'))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/v1/models/load', methods=['POST'])
def proxy_load_model():
    """Proxy POST /api/v1/models/load to LM Studio."""
    data = request.json or {}
    api_url = config.LM_STUDIO_URL.rstrip("/")
    
    base_url = api_url[:-3] if api_url.endswith('/v1') else api_url
    endpoint = f"{base_url}{request.path}"
        
    headers = {"Content-Type": "application/json"}
    if config.LM_STUDIO_API_KEY:
        headers["Authorization"] = f"Bearer {config.LM_STUDIO_API_KEY}"
        
    try:
        response = requests.post(endpoint, json=data, headers=headers, timeout=60)
        return Response(response.content, status=response.status_code, content_type=response.headers.get('content-type', 'application/json'))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/v1/models/unload', methods=['POST'])
def proxy_unload_model():
    """Proxy POST /api/v1/models/unload to LM Studio."""
    data = request.json or {}
    api_url = config.LM_STUDIO_URL.rstrip("/")
    
    base_url = api_url[:-3] if api_url.endswith('/v1') else api_url
    endpoint = f"{base_url}{request.path}"
        
    headers = {"Content-Type": "application/json"}
    if config.LM_STUDIO_API_KEY:
        headers["Authorization"] = f"Bearer {config.LM_STUDIO_API_KEY}"
        
    try:
        response = requests.post(endpoint, json=data, headers=headers, timeout=60)
        return Response(response.content, status=response.status_code, content_type=response.headers.get('content-type', 'application/json'))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    try:
        data = request.json
        messages = data.get('messages', [])
        model = data.get('model', 'local-model')
        chat_id = data.get('chatId')
        memory_mode = data.get('memoryMode', False)
        research_mode = data.get('researchMode', False)
        search_depth_mode = data.get('searchDepthMode', 'regular')
        vision_model = data.get('visionModel')
        approved_plan = data.get('approvedPlan')
        resume_state = data.get('resumeState')
        last_model_name = data.get('lastModelName', model)
        # Enforce secrets for security and to prevent empty frontend overrides
        api_url = config.LM_STUDIO_URL
        api_key = config.LM_STUDIO_API_KEY

        # Blacklist keys that should never be forwarded or overridden by client
        blacklist = [
            'messages', 'chatId', 'memoryMode', 'researchMode', 
            'searchDepthMode', 'visionModel', 'stream', 'approvedPlan', 
            'resumeState', 'lastModelName', 'hasVision', 'apiKey', 'apiUrl'
        ]
        extra_body = {k: v for k, v in data.items() if k not in blacklist}

        if not chat_id or '..' in chat_id or '/' in chat_id or '\\' in chat_id:
             return jsonify({"error": "Invalid or missing chatId"}), 400

        # === 1. Handle Active Tasks (Resume/Stream) ===
        if task_manager.is_task_running(chat_id):
            # If task is running, subscribe to its cache stream
            def generate_stream():
                for chunk in cache_system.subscribe(chat_id):
                    yield chunk
            return Response(generate_stream(), mimetype='text/event-stream')

        # === 2. Persist User Message Immediately (for new turns) ===
        if messages and messages[-1]['role'] == 'user':
            user_msg = messages[-1]
            title = user_msg['content']
            
            existing_chat = get_chat(chat_id)
            
            # --- MODEL LOCKING FOR RESEARCH ---
            # Once a Research conversation starts, the models should not be allowed to change.
            if existing_chat and existing_chat.get('research_mode'):
                prev_model = existing_chat.get('last_model')
                prev_vision = existing_chat.get('vision_model')
                
                # Check main model
                if prev_model and last_model_name != prev_model:
                    return jsonify({
                        "error": f"Model is locked for this Research conversation. (Locked: {prev_model}, Requested: {last_model_name})",
                        "locked_model": prev_model
                    }), 400
                
                # Check vision model
                if prev_vision and vision_model != prev_vision:
                    return jsonify({
                        "error": f"Vision model is locked for this Research conversation. (Locked: {prev_vision}, Requested: {vision_model})",
                        "locked_vision": prev_vision
                    }), 400

            if not research_mode:
                has_image_in_messages = any(
                    isinstance(msg.get('content'), list) and any(
                        isinstance(part, dict) and part.get('type') == 'image_url' for part in msg['content']
                    ) for msg in messages
                )
                current_is_vision = existing_chat.get('is_vision', 0) if existing_chat else 0
                new_is_vision = 1 if (has_image_in_messages or current_is_vision) else 0
            else:
                new_is_vision = 0

            if isinstance(title, list):
                title = next((p['text'] for p in title if p.get('type') == 'text'), "Image Message")
            title = title[:50] if isinstance(title, str) else "New Chat"

            save_chat(
                chat_id,
                title,
                time.time(),
                memory_mode,
                research_mode,
                is_vision=new_is_vision,
                last_model=last_model_name,
                vision_model=vision_model,
                max_tokens=data.get('max_tokens', 16384)
            )
            add_message(chat_id, 'user', user_msg['content'])

        # === 3. Enqueue Background Task ===
        if research_mode:
            # Sync engineering URL and Key with the request
            if hasattr(research_rag.embedding_fn, 'api_url'):
                research_rag.embedding_fn.api_url = api_url
            if hasattr(research_rag.embedding_fn, 'api_key'):
                research_rag.embedding_fn.api_key = api_key
            
            task_manager.start_research_task(
                model, messages, approved_plan, chat_id, search_depth_mode, vision_model, generate_research_response,
                model_name=last_model_name, resume_state=resume_state, rag_engine=research_rag, rag=rag, api_url=api_url, api_key=api_key
            )
        else:
            # Normal Chat Task
            if hasattr(rag.embedding_fn, 'api_url'):
                rag.embedding_fn.api_url = api_url
            if hasattr(rag.embedding_fn, 'api_key'):
                rag.embedding_fn.api_key = api_key
            has_vision = data.get('hasVision', False)
            task_manager.start_chat_task(
                chat_id,
                generate_chat_response,
                model=model,
                messages=messages,
                extra_body=extra_body,
                rag=rag,
                memory_mode=memory_mode,
                has_vision=has_vision,
                api_url=api_url,
                api_key=api_key
            )

        # === 4. Return Stream Subscription ===
        def generate_stream():
            # Wait briefly for cache initialization to ensure subscriber doesn't miss start
            time.sleep(0.1)
            for chunk in cache_system.subscribe(chat_id):
                yield chunk
        return Response(generate_stream(), mimetype='text/event-stream')

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        log_event("app_general_error", {"error": str(e), "traceback": error_trace})
        return jsonify({"error": str(e)}), 500

# ==================== LOG BROWSING ENDPOINTS ====================

@app.route('/logs')
def logs_page():
    return send_from_directory('static', 'logs.html')

@app.route('/api/logs', methods=['GET'])
def get_log_index():
    index_path = os.path.join(config.DATA_DIR, "logs", "network_index.jsonl")
    logs = []
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    logs.append(json.loads(line))
                except:
                    pass
    return jsonify(list(reversed(logs)))

@app.route('/api/logs/detail', methods=['GET'])
def get_log_detail():
    rel_path = request.args.get('path')
    if not rel_path:
        return jsonify({"error": "Missing path"}), 400
        
    # Security: Ensure path is within the logs directory
    base_logs = os.path.abspath(os.path.join(config.DATA_DIR, "logs"))
    target_path = os.path.abspath(os.path.join(base_logs, rel_path))
    
    if not target_path.startswith(base_logs + os.sep) and target_path != base_logs:
        return jsonify({"error": "Access denied"}), 403
        
    if not os.path.exists(target_path):
        return jsonify({"error": "File not found"}), 404
        
    try:
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/logs/events', methods=['GET'])
def get_event_logs():
    event_dir = os.path.join(config.DATA_DIR, "logs", "general")
    events = []
    if os.path.exists(event_dir):
        # Get latest event file
        files = sorted([f for f in os.listdir(event_dir) if f.endswith("_events.jsonl")], reverse=True)
        if files:
            with open(os.path.join(event_dir, files[0]), "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        events.append(json.loads(line))
                    except:
                        pass
    return jsonify(list(reversed(events)))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
