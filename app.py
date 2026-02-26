from flask import Flask, request, jsonify, Response, send_from_directory
from backend.logger import log_event
import os
import time
import json
import requests
from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv()

from backend.config import LM_STUDIO_URL, EMBEDDING_MODEL, CHROMA_PATH
from backend.rag import MemoryRAG, DeepResearchRAG
from backend.storage import init_db, get_all_chats, get_chat, save_chat, add_message, clear_messages, delete_chat, delete_all_chats, rename_chat
from backend.agents.deep_research import generate_deep_research_response
from backend.agents.chat import generate_chat_response
from backend.task_manager import task_manager

app = Flask(__name__, static_folder='static')

# Initialize components with config
init_db()
rag = MemoryRAG(persist_path=CHROMA_PATH, api_url=LM_STUDIO_URL, embedding_model=EMBEDDING_MODEL)
deep_research_rag = DeepResearchRAG(persist_path=CHROMA_PATH, api_url=LM_STUDIO_URL, embedding_model=EMBEDDING_MODEL)
task_manager.recover_tasks(generate_deep_research_response)

@app.route('/')
@app.route('/chat/<chat_id>')
def index(chat_id=None):
    return send_from_directory('static', 'index.html')

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
        deep_research_rag.cleanup_chat(chat.get('id', ''))
    return jsonify({"success": True})

@app.route('/api/chats/<chat_id>', methods=['GET'])
def get_chat_details(chat_id):
    chat = get_chat(chat_id)
    if not chat:
        return jsonify({"error": "Chat not found"}), 404
    chat["is_research_running"] = task_manager.is_task_running(chat_id)
    return jsonify(chat)

@app.route('/api/chats/save', methods=['POST'])
def save_chat_endpoint():
    data = request.json
    chat_id = data.get('chat_id')
    title = data.get('title', 'New Chat')
    messages = data.get('messages')
    memory_mode = data.get('memory_mode', False)
    deep_research_mode = data.get('deep_research_mode', False)
    
    if not chat_id:
        return jsonify({"error": "Missing chat_id"}), 400
        
    save_chat(
        chat_id, 
        title, 
        time.time(), 
        memory_mode, 
        deep_research_mode, 
        is_vision=data.get('is_vision', False),
        last_model=data.get('last_model')
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
    
    if new_title:
        rename_chat(chat_id, new_title)
    if last_model:
        from backend.storage import update_chat_model
        update_chat_model(chat_id, last_model)
        
    if not new_title and not last_model:
        return jsonify({"error": "Missing fields"}), 400
        
    return jsonify({"success": True})

@app.route('/api/chats/<chat_id>', methods=['DELETE'])
def remove_chat(chat_id):
    delete_chat(chat_id)
    deep_research_rag.cleanup_chat(chat_id)
    return jsonify({"success": True})

@app.route('/api/chats/<chat_id>/stop', methods=['POST'])
def stop_chat_endpoint(chat_id):
    task_manager.stop_task(chat_id)
    from backend.storage import delete_last_turn
    delete_last_turn(chat_id)
    return jsonify({"success": True})

@app.route('/api/config', methods=['POST'])
def update_config():
    global LM_STUDIO_URL, rag
    data = request.json
    
    updated = False
    if 'url' in data:
        LM_STUDIO_URL = data['url']
        updated = True

    if updated:
        from backend.config import EMBEDDING_MODEL
        rag = MemoryRAG(api_url=LM_STUDIO_URL, embedding_model=EMBEDDING_MODEL)

    return jsonify({"success": True, "url": LM_STUDIO_URL})

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

@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    try:
        data = request.json
        messages = data.get('messages', [])
        model = data.get('model', 'local-model')
        chat_id = data.get('chatId')
        memory_mode = data.get('memoryMode', False)
        deep_research_mode = data.get('deepResearchMode', False)
        search_depth_mode = data.get('searchDepthMode', 'regular')
        vision_model = data.get('visionModel')
        approved_plan = data.get('approvedPlan')
        last_model_name = data.get('lastModelName', model)

        
        extra_body = {k: v for k, v in data.items() if k not in ['messages', 'chatId', 'memoryMode', 'deepResearchMode', 'searchDepthMode', 'visionModel', 'stream', 'approvedPlan', 'lastModelName', 'hasVision']}

        # Persistent Chat Handling
        if chat_id:
            if messages and messages[-1]['role'] == 'user':
                user_msg = messages[-1]
                title = user_msg['content']

                # Only track vision/model history for regular chats, not deep research
                if not deep_research_mode:
                    has_image_in_messages = any(
                        isinstance(msg.get('content'), list) and any(
                            isinstance(part, dict) and part.get('type') == 'image_url' for part in msg['content']
                        ) for msg in messages
                    )
                    
                    # Check for is_vision from database first to avoid overwriting
                    existing_chat = get_chat(chat_id)
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
                    deep_research_mode, 
                    is_vision=new_is_vision, 
                    last_model=last_model_name
                )
                add_message(chat_id, 'user', user_msg['content'])

        if deep_research_mode and chat_id:
            if not task_manager.is_task_running(chat_id):
                task_manager.start_research_task(
                    last_model_name, messages, approved_plan, chat_id, search_depth_mode, vision_model, generate_deep_research_response
                )
            
            def generate_deep_stream():
                for chunk in task_manager.stream_task(chat_id):
                    yield chunk
            return Response(generate_deep_stream(), mimetype='text/event-stream')

        def generate_with_persistence():
            full_content = ""
            full_reasoning = ""
            
            has_vision = data.get('hasVision', False)
            generator = generate_chat_response(LM_STUDIO_URL, model, messages, extra_body, rag, memory_mode, chat_id=chat_id, has_vision=has_vision)
            try:
                for chunk in generator:
                    yield chunk
                    try:
                        if isinstance(chunk, str) and chunk.startswith("data: "):
                            if chunk.strip() == "data: [DONE]": continue
                            data_json = json.loads(chunk[6:])
                            
                            # Handle accumulator reset (triggered by validation healing)
                            if data_json.get('__reset_accumulator__'):
                                full_content = ""
                                full_reasoning = ""
                                continue
                            
                            choices = data_json.get('choices', [])
                            if choices:
                                delta = choices[0].get('delta', {})
                                if 'content' in delta:
                                    full_content += delta.get('content', '') or ''
                                if 'reasoning_content' in delta:
                                    full_reasoning += delta.get('reasoning_content', '') or ''
                    except Exception:
                        pass
            except GeneratorExit:
                return # Client disconnected, do not persist assistant partial response

            # Save assistant message to chat history DB
            if chat_id and (full_content or full_reasoning):
                # Combine reasoning and content for storage, wrapped in tags if reasoning exists
                final_content_for_db = full_content
                if full_reasoning:
                    final_content_for_db = f"<think>{full_reasoning}</think>\n{full_content}"

                add_message(chat_id, 'assistant', final_content_for_db, model=last_model_name)
                
                # RAG Memory Update — ONLY for standard chat, NEVER for deep research
                if memory_mode:
                    try:
                        user_content_str = ""
                        for m in reversed(messages):
                            if m['role'] == 'user':
                                c = m.get('content', '')
                                if isinstance(c, str): user_content_str = c
                                elif isinstance(c, list): 
                                    user_content_str = next((p['text'] for p in c if p.get('type') == 'text'), "")
                                break
                        
                        if user_content_str:
                            rag.add_conversation_turn(user_content_str, full_content, chat_id)
                    except Exception as e:
                        log_event("memory_rag_update_error", {"chat_id": chat_id, "error": str(e)})

        return Response(generate_with_persistence(), mimetype='text/event-stream')

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
    index_path = os.path.join("backend", "logs", "network_index.jsonl")
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
    base_logs = os.path.abspath(os.path.join("backend", "logs"))
    target_path = os.path.abspath(os.path.join(base_logs, rel_path))
    
    if not target_path.startswith(base_logs):
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
    event_dir = os.path.join("backend", "logs", "general")
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
