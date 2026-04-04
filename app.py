from flask import Flask, request, jsonify, Response, send_from_directory
from backend.logger import log_event
import logging

logger = logging.getLogger(__name__)
import os
import time
import json
import requests
from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv()

# Set correct timezone dynamically for the process
if os.environ.get('TZ') is None:
    os.environ['TZ'] = 'Asia/Kolkata'
if os.name != 'nt' and hasattr(time, 'tzset'):
    time.tzset()

from backend import config
from backend.rag import MemoryRAG, ResearchRAG
from backend.db_wrapper import db
from backend.storage import init_db
from backend.canvas_manager import (
    export_canvas_markdown,
    export_canvas_html,
    export_canvas_pdf,
    get_canvas_versions,
    get_canvas_version,
    restore_canvas_version,
    get_canvas_diff,
    share_canvas,
    unshare_canvas,
    get_shared_users,
    create_canvas as manager_create_canvas
)

# Import channel manager for per-chat locking
from backend.canvas_channel import CanvasChannelManager
from backend.agents.research import generate_research_response
from backend.agents.chat import generate_chat_response
from backend.task_manager import task_manager
from backend.cache_system import cache_system
from backend.version import get_version

app = Flask(__name__, static_folder='static')
# Limit request size to 16MB to prevent unbounded payload DoS (e.g. extremely large JSON arrays)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Determine config path
config_path = os.path.join(os.path.dirname(__file__), 'backend', 'model_config.json')
try:
    with open(config_path, 'r', encoding='utf-8') as f:
        model_cfg = json.load(f)
    embedding_model = model_cfg.get('embedding', 'embeddinggemma/embeddinggemma-300M-Q8_0')
except Exception as e:
    log_event("config_load_error", {"error": str(e)})
    # Fallback default
    embedding_model = "embeddinggemma/embeddinggemma-300M-Q8_0"

# Initialize components with config
init_db()
rag = MemoryRAG(persist_path=config.CHROMA_PATH, api_url=config.AI_URL, api_key=config.AI_API_KEY, embedding_model=embedding_model)
research_rag = ResearchRAG(persist_path=config.CHROMA_PATH, api_url=config.AI_URL, api_key=config.AI_API_KEY, embedding_model=embedding_model)
task_manager.recover_tasks()

# Initialize canvas channel manager for per-chat locking
import asyncio
try:
    loop = asyncio.get_event_loop()
    loop.run_until_complete(CanvasChannelManager.initialize())
except RuntimeError:
    asyncio.run(CanvasChannelManager.initialize())

CANVASES_DIR = os.path.join(config.DATA_DIR, "canvases")
os.makedirs(CANVASES_DIR, exist_ok=True)

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
    logger = logging.getLogger(__name__)
    logger.debug("[API] GET /api/chats - listing all chats")
    chats = db.get_all_chats()
    logger.debug("[API] GET /api/chats - completed, count=%d", len(chats))
    return jsonify(chats)

@app.route('/api/chats', methods=['DELETE'])
def clear_all_chats():
    # Get all chat IDs before deleting so we can clean up ChromaDB
    all_chats = db.get_all_chats()
    db.delete_all_chats()
    for chat in all_chats:
        research_rag.cleanup_chat(chat.get('id', ''))
    return jsonify({"success": True})

@app.route('/api/chats/<chat_id>', methods=['GET'])
def get_chat_details(chat_id):
    logger.debug("[API] GET /api/chats/%s - getting chat details", chat_id)
    chat = db.get_chat_full(chat_id)
    if not chat:
        logger.debug("[API] GET /api/chats/%s - chat not found", chat_id)
        return jsonify({"error": "Chat not found"}), 404
    # Replaced task_manager.is_task_running logic with generic active status
    chat["is_research_running"] = task_manager.is_task_running(chat_id)
    logger.debug("[API] GET /api/chats/%s - completed, has_messages=%d", chat_id, len(chat.get('messages', [])))
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
    canvas_mode = data.get('canvas_mode', False)
    logger.debug("[API] POST /api/chats/save - chat_id=%s title=%s", chat_id, title)

    if not chat_id or '..' in chat_id or '/' in chat_id or '\\' in chat_id:
        return jsonify({"error": "Invalid or missing chat_id"}), 400

    # Check if chat has canvases in DB - auto-enable canvas_mode if so
    canvases = db.get_chat_canvases(chat_id)
    if len(canvases) > 0:
        canvas_mode = True

    # Check if chat exists. Only allow new chats to be saved via this endpoint.
    existing_chat = db.get_chat(chat_id)
    if existing_chat:
        return jsonify({"error": "Cannot overwrite existing chat history via save endpoint. Use Action-Based APIs."}), 403

    db.save_chat(
        chat_id=chat_id,
        title=title,
        timestamp=time.time(),
        memory_mode=1 if memory_mode else 0,
        research_mode=1 if research_mode else 0,
        is_vision=1 if data.get('is_vision', False) else 0,
        last_model=data.get('last_model'),
        vision_model=data.get('vision_model'),
        max_tokens=max_tokens,
        folder=data.get('folder'),
        search_depth_mode=data.get('search_depth_mode', 'regular'),
        research_completed=data.get('research_completed', 0),
        canvas_mode=1 if canvas_mode else 0,
        enable_thinking=1 if data.get('enable_thinking', True) else 0,
        temperature=data.get('temperature', 1.0),
        top_p=data.get('top_p', 1.0),
        top_k=data.get('top_k', 40),
        min_p=data.get('min_p', 0.05),
        presence_penalty=data.get('presence_penalty', 0.0),
        frequency_penalty=data.get('frequency_penalty', 0.0)
    )

    if messages is not None:
        logger.debug("[API] POST /api/chats/save - clearing and adding %d messages", len(messages))
        db.clear_messages(chat_id=chat_id)
        for msg in messages:
            db.add_message(
                chat_id=chat_id,
                role=msg['role'],
                content=msg.get('content'),
                model=msg.get('model'),
                timestamp=time.time(),
                tool_calls=json.dumps(msg.get('tool_calls')) if msg.get('tool_calls') else None,
                tool_call_id=msg.get('tool_call_id'),
                name=msg.get('name')
            )
        logger.debug("[API] POST /api/chats/save - completed saving %d messages", len(messages))

    logger.debug("[API] POST /api/chats/save - completed, success=True")
    return jsonify({"success": True})

@app.route('/api/chats/<chat_id>', methods=['PATCH'])
def patch_chat_endpoint(chat_id):
    data = request.json
    new_title = data.get('title')
    last_model = data.get('last_model')
    vision_model = data.get('vision_model')
    max_tokens = data.get('max_tokens')
    folder = data.get('folder')
    enable_thinking = data.get('enable_thinking')
    temperature = data.get('temperature')
    top_p = data.get('top_p')
    top_k = data.get('top_k')
    min_p = data.get('min_p')
    presence_penalty = data.get('presence_penalty')
    frequency_penalty = data.get('frequency_penalty')

    existing_chat = db.get_chat(chat_id)
    if not existing_chat:
        return jsonify({"error": "Chat not found"}), 404

    # Block model changes in Research
    if existing_chat.get('research_mode'):
        if last_model and last_model != existing_chat.get('last_model'):
             return jsonify({"error": "Model cannot be changed in Research"}), 400
        if vision_model and vision_model != existing_chat.get('vision_model'):
             return jsonify({"error": "Vision model cannot be changed in Research"}), 400

    if new_title:
        db.rename_chat(chat_id=chat_id, new_title=new_title)
    if last_model:
        db.update_chat_model(chat_id=chat_id, last_model=last_model)
    if vision_model:
        db.update_chat_vision_model(chat_id=chat_id, vision_model=vision_model)
    if max_tokens is not None:
        db.update_chat_max_tokens(chat_id=chat_id, max_tokens=max_tokens)
    if 'folder' in data:
        db.update_chat_folder(chat_id=chat_id, folder=data['folder'])
    if 'research_completed' in data:
        db.mark_research_completed(chat_id=chat_id, completed=data['research_completed'])
    if 'memory_mode' in data:
        db.update_chat(chat_id=chat_id, memory_mode=1 if data['memory_mode'] else 0)
    if 'research_mode' in data:
        db.update_chat(chat_id=chat_id, research_mode=1 if data['research_mode'] else 0)
    if 'canvas_mode' in data:
        db.update_chat(chat_id=chat_id, canvas_mode=1 if data['canvas_mode'] else 0)
    if 'is_vision' in data:
        db.update_chat(chat_id=chat_id, is_vision=1 if data['is_vision'] else 0)
    if 'search_depth_mode' in data:
        db.update_chat(chat_id=chat_id, search_depth_mode=data['search_depth_mode'])
    if 'enable_thinking' in data:
        db.update_chat(chat_id=chat_id, enable_thinking=1 if data['enable_thinking'] else 0)
    if temperature is not None:
        db.update_chat(chat_id=chat_id, temperature=temperature)
    if top_p is not None:
        db.update_chat(chat_id=chat_id, top_p=top_p)
    if top_k is not None:
        db.update_chat(chat_id=chat_id, top_k=top_k)
    if min_p is not None:
        db.update_chat(chat_id=chat_id, min_p=min_p)
    if presence_penalty is not None:
        db.update_chat(chat_id=chat_id, presence_penalty=presence_penalty)
    if frequency_penalty is not None:
        db.update_chat(chat_id=chat_id, frequency_penalty=frequency_penalty)

    # Check if any supported fields were provided
    supported_fields = [
        'title', 'last_model', 'vision_model', 'max_tokens', 'folder', 
        'research_completed', 'memory_mode', 'research_mode', 'canvas_mode', 
        'is_vision', 'search_depth_mode'
    ]
    if not any(field in data for field in supported_fields):
        return jsonify({"error": "Missing fields"}), 400

    return jsonify({"success": True})

@app.route('/api/chats/<chat_id>', methods=['DELETE'])
def remove_chat(chat_id):
    db.delete_chat(chat_id=chat_id)
    research_rag.cleanup_chat(chat_id)
    # Release canvas channel for this chat
    CanvasChannelManager.release_channel(chat_id)
    return jsonify({"success": True})

@app.route('/api/canvas/channel/status', methods=['GET'])
def get_channel_status():
    """
    Get status of canvas channel for specific chat.
    Returns lock status and queue depth.
    """
    chat_id = request.args.get('chat_id')
    if not chat_id:
        return jsonify({"error": "chat_id parameter required"}), 400

    if chat_id not in CanvasChannelManager._channels:
        return jsonify({
            "chat_id": chat_id,
            "exists": False,
            "state": "not_found"
        })

    channel = CanvasChannelManager._channels[chat_id]
    return jsonify({
        "chat_id": chat_id,
        "exists": True,
        "state": channel.state.value,
        "current_operation": channel._current_operation,
        "total_operations": channel._total_operations,
        "avg_wait_time": channel._total_wait_time / max(1, channel._total_operations)
    })

@app.route('/api/chats/<chat_id>/stop', methods=['POST'])
def stop_chat_endpoint(chat_id):
    task_manager.stop_task(chat_id)
    return jsonify({"success": True})

@app.route('/api/chats/<chat_id>/messages/truncate', methods=['POST'])
def truncate_chat_messages(chat_id):
    data = request.json
    index = data.get('index')
    if index is None:
        return jsonify({"error": "Index required"}), 400
    
    success = db.truncate_messages(chat_id, int(index))
    return jsonify({"success": success})

@app.route('/api/chats/<chat_id>/messages/<int:index>', methods=['PUT'])
def edit_chat_message_by_index(chat_id, index):
    data = request.json
    content = data.get('content')
    if content is None:
        return jsonify({"error": "Content required"}), 400
    
    success = db.edit_message_by_index(chat_id, index, content)
    return jsonify({"success": success})

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

    # 4. Cleanup canvases: Delete .md files and DB rows (Issue 2.4 fix)
    canvases = db.get_chat_canvases(chat_id=chat_id)
    for canvas in canvases:
        if canvas.get('filename'):
            file_path = os.path.join(CANVASES_DIR, canvas['filename'])
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except OSError:
                pass  # Best-effort
        db.delete_canvas_meta(canvas_id=canvas['id'], chat_id=chat_id)

    # 5. Cleanup messages: Wipe and allow restart
    db.clear_messages(chat_id=chat_id)
    return jsonify({"success": True})

@app.route('/api/version', methods=['GET'])
def get_version_endpoint():
    """Return the application version."""
    return jsonify({"version": get_version(), "major": 2, "minor": 3, "patch": 1})


@app.route('/api/memory/reset', methods=['POST'])
def reset_memory():
    success = rag.reset_memory()
    return jsonify({"success": success})

@app.route('/api/memory', methods=['GET'])
def get_memories():
    try:
        memories = rag.get_all_core_memories_raw()
        return jsonify({"success": True, "memories": memories})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/memory', methods=['POST'])
def add_memory():
    data = request.json
    content = data.get('content')
    tag = data.get('tag')
    if not content or not tag:
        return jsonify({"error": "Missing content or tag"}), 400
    doc_id = rag.add_core_memory(content, tag)
    if doc_id:
        return jsonify({"success": True, "id": doc_id})
    return jsonify({"error": "Failed to add memory"}), 500

@app.route('/api/memory/<doc_id>', methods=['PUT'])
def update_memory(doc_id):
    data = request.json
    content = data.get('content')
    tag = data.get('tag')
    if not content or not tag:
        return jsonify({"error": "Missing content or tag"}), 400
    success = rag.update_core_memory(doc_id, content, tag)
    if success:
        return jsonify({"success": True})
    return jsonify({"error": "Failed to update memory"}), 500

@app.route('/api/memory/<doc_id>', methods=['DELETE'])
def delete_memory(doc_id):
    success = rag.delete_core_memory(doc_id)
    if success:
        return jsonify({"success": True})
    return jsonify({"error": "Failed to delete memory"}), 500

# =============================================================================
# CANVAS ENDPOINTS
# =============================================================================

@app.route('/api/chats/<chat_id>/canvases', methods=['GET'])
async def list_canvases_endpoint(chat_id):
    from backend.canvas_manager import get_canvas_content
    canvases = db.get_chat_canvases(chat_id=chat_id)
    # Add content to each canvas for proper search/filtering
    canvases_with_content = []
    for canvas in canvases:
        content = await get_canvas_content(canvas['id'], chat_id)
        canvas_copy = dict(canvas)
        canvas_copy['content'] = content or ""
        canvases_with_content.append(canvas_copy)
    return jsonify({"success": True, "canvases": canvases_with_content})

@app.route('/api/canvases', methods=['POST'])
async def create_canvas_route():
    data = request.json
    chat_id = data.get('chat_id')
    title = data.get('title', 'Untitled Canvas')
    content = data.get('content')
    custom_canvas_id = data.get('id')

    if not chat_id or not content:
        return jsonify({"error": "Missing chat_id or content"}), 400

    try:
        result = await manager_create_canvas(
            chat_id=chat_id,
            canvas_id=custom_canvas_id,
            title=title,
            content=content or ''
        )
        return jsonify({
            "success": True,
            "id": result["canvas_id"],
            "title": result["title"],
            "filename": result["filename"]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/canvases/<canvas_id>', methods=['GET'])
async def get_canvas_endpoint(canvas_id):
    chat_id = request.args.get('chat_id')
    if not chat_id:
        return jsonify({"error": "chat_id query parameter is required"}), 400

    canvas = db.get_canvas_meta(canvas_id=canvas_id, chat_id=chat_id)
    if not canvas:
        return jsonify({"error": "Canvas not found"}), 404

    # Issue 4.1 fix: delegate file read to storage.py instead of raw open
    from backend.canvas_manager import get_canvas_content
    content = await get_canvas_content(canvas_id, chat_id)
    if content is None:
        return jsonify({"error": "Canvas file not found on disk"}), 404

    return jsonify({
        "success": True,
        "id": canvas_id,
        "chat_id": chat_id,
        "title": canvas['title'],
        "content": content,
        "timestamp": canvas['timestamp']
    })

@app.route('/api/canvases/<canvas_id>', methods=['PATCH'])
async def update_canvas_endpoint(canvas_id):
    """Update canvas content or metadata (folder, title)."""
    data = request.json or {}
    chat_id = data.get('chat_id') or request.args.get('chat_id')
    if not chat_id:
        return jsonify({"success": False, "error": "chat_id is required"}), 400

    canvas = db.get_canvas_meta(canvas_id=canvas_id, chat_id=chat_id)
    if not canvas:
        return jsonify({"success": False, "error": "Canvas not found"}), 404

    # Handle folder/metadata updates first
    new_folder = data.get('folder')
    new_title = data.get('title')
    
    # If explicitly updating folder or title without content
    if new_folder is not None or new_title is not None:
        db.save_canvas_meta(
            canvas_id=canvas_id,
            chat_id=chat_id,
            title=new_title or canvas['title'],
            filename=canvas['filename'],
            folder=new_folder if new_folder is not None else canvas.get('folder'),
            canvas_type=canvas.get('canvas_type', 'custom'),
            current_version=canvas.get('current_version')
        )

    # Handle content update (produces a new version)
    new_content = data.get('content')
    if new_content is not None:
        from backend.canvas_manager import update_canvas_content
        result = await update_canvas_content(canvas_id, chat_id, new_content, author="user")
        return jsonify(result)

    return jsonify({"success": True, "id": canvas_id})

@app.route('/api/canvases/<canvas_id>', methods=['DELETE'])
async def remove_canvas_endpoint(canvas_id):
    chat_id = request.args.get('chat_id')
    if not chat_id:
        return jsonify({"error": "chat_id is required"}), 400
        
    from backend.canvas_manager import delete_canvas
    result = await delete_canvas(canvas_id, chat_id)
    return jsonify(result)


@app.route('/api/canvases/<canvas_id>/export/markdown', methods=['GET'])
async def export_canvas_markdown_endpoint(canvas_id):
    """Export canvas as markdown file."""
    chat_id = request.args.get('chat_id')
    if not chat_id:
        return jsonify({"error": "chat_id is required"}), 400
        
    from backend.canvas_manager import export_canvas_markdown
    content, filename = await export_canvas_markdown(canvas_id, chat_id)
    if content is None:
        return jsonify({"error": filename}), 404

    return Response(
        content,
        mimetype='text/markdown',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Length': len(content)
        }
    )


@app.route('/api/canvases/<canvas_id>/export/html', methods=['GET'])
async def export_canvas_html_endpoint(canvas_id):
    """Export canvas as HTML file."""
    chat_id = request.args.get('chat_id')
    if not chat_id:
        return jsonify({"error": "chat_id is required"}), 400
        
    from backend.canvas_manager import export_canvas_html
    html_content, filename = await export_canvas_html(canvas_id, chat_id)
    if html_content is None:
        return jsonify({"error": filename}), 404

    return Response(
        html_content,
        mimetype='text/html',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Length': len(html_content)
        }
    )


@app.route('/api/canvases/<canvas_id>/export/pdf', methods=['GET'])
async def export_canvas_pdf_endpoint(canvas_id):
    """Export canvas as PDF file."""
    chat_id = request.args.get('chat_id')
    if not chat_id:
        return jsonify({"error": "chat_id is required"}), 400
        
    from backend.canvas_manager import export_canvas_pdf
    pdf_content, filename = await export_canvas_pdf(canvas_id, chat_id)
    if pdf_content is None:
        return jsonify({"error": filename}), 404

    # Handle both bytes and string (for fallback)
    if isinstance(pdf_content, str):
        pdf_content = pdf_content.encode('utf-8')

    return Response(
        pdf_content,
        mimetype='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Length': len(pdf_content)
        }
    )


@app.route('/api/canvases/<canvas_id>/folder', methods=['POST'])
def set_canvas_folder(canvas_id):
    """Set folder for a canvas."""
    data = request.json or {}
    chat_id = data.get('chat_id')
    if not chat_id:
        return jsonify({"error": "chat_id is required"}), 400

    canvas = db.get_canvas_meta(canvas_id=canvas_id, chat_id=chat_id)
    if not canvas:
        return jsonify({"error": "Canvas not found"}), 404

    folder = data.get('folder', '')

    # Update folder in title if present
    base_title = canvas['title'].split('/')[-1]
    new_title = f"{folder}/{base_title}" if folder else base_title

    db.save_canvas_meta(canvas_id=canvas_id, chat_id=chat_id, title=new_title, filename=canvas['filename'], folder=folder)

    return jsonify({"success": True, "title": new_title})


@app.route('/api/canvases/<canvas_id>/tags', methods=['POST'])
def set_canvas_tags(canvas_id):
    """Set tags for a canvas."""
    data = request.json or {}
    chat_id = data.get('chat_id')
    if not chat_id:
        return jsonify({"error": "chat_id is required"}), 400

    canvas = db.get_canvas_meta(canvas_id=canvas_id, chat_id=chat_id)
    if not canvas:
        return jsonify({"error": "Canvas not found"}), 404

    data = request.json or {}
    tags = data.get('tags', [])

    # Ensure tags is a list
    if isinstance(tags, str):
        tags = [tags]

    db.save_canvas_meta(canvas_id=canvas_id, chat_id=chat_id, title=canvas['title'], filename=canvas['filename'], folder=canvas.get('folder'), tags=tags)

    return jsonify({"success": True, "tags": tags})


@app.route('/api/chats/<chat_id>/canvases/folders', methods=['GET'])
def get_chat_folders(chat_id):
    """Get unique folders for a chat's canvases."""
    from backend.canvas_manager import get_unique_folders
    folders = get_unique_folders(chat_id)
    return jsonify({"success": True, "folders": folders})


@app.route('/api/canvases/<canvas_id>/tags/<tag>', methods=['DELETE'])
def remove_canvas_tag(canvas_id, tag):
    """Remove a tag from a canvas."""
    chat_id = request.args.get('chat_id')
    if not chat_id:
        return jsonify({"error": "chat_id is required"}), 400

    canvas = db.get_canvas_meta(canvas_id=canvas_id, chat_id=chat_id)
    if not canvas:
        return jsonify({"error": "Canvas not found"}), 404

    # Parse existing tags
    try:
        current_tags = json.loads(canvas.get('tags', '[]'))
    except:
        current_tags = []

    # Remove tag if present
    if tag in current_tags:
        current_tags.remove(tag)

    db.save_canvas_meta(canvas_id=canvas_id, chat_id=chat_id, title=canvas['title'], filename=canvas['filename'], folder=canvas.get('folder'), tags=current_tags)

    return jsonify({"success": True, "tags": current_tags})


@app.route('/api/canvases/<canvas_id>/tags/<tag>', methods=['POST'])
def add_canvas_tag(canvas_id, tag):
    """Add a tag to a canvas."""
    chat_id = request.args.get('chat_id')
    if not chat_id:
        return jsonify({"error": "chat_id is required"}), 400

    canvas = db.get_canvas_meta(canvas_id=canvas_id, chat_id=chat_id)
    if not canvas:
        return jsonify({"error": "Canvas not found"}), 404

    # Parse existing tags
    try:
        current_tags = json.loads(canvas.get('tags', '[]'))
    except:
        current_tags = []

    # Add tag if not present
    if tag not in current_tags:
        current_tags.append(tag)

    db.save_canvas_meta(canvas_id=canvas_id, chat_id=chat_id, title=canvas['title'], filename=canvas['filename'], folder=canvas.get('folder'), tags=current_tags)

    return jsonify({"success": True, "tags": current_tags})


@app.route('/api/canvases/<canvas_id>/versions', methods=['GET'])
async def get_canvas_versions_endpoint(canvas_id):
    """Get version history for a canvas."""
    chat_id = request.args.get('chat_id')
    if not chat_id:
        return jsonify({"error": "chat_id is required"}), 400
        
    versions = get_canvas_versions(canvas_id, chat_id)
    if not versions:
        return jsonify({
            "success": True,
            "canvas_id": canvas_id,
            "versions": []
        })

    # Clean up version data (remove content from response)
    versions_response = []
    for v in versions:
        versions_response.append({
            "version_number": v['version_number'],
            "author": v['author'],
            "timestamp": v['timestamp'],
            "comment": v.get('comment', '')
        })

    return jsonify({
        "success": True,
        "canvas_id": canvas_id,
        "versions": versions_response
    })


@app.route('/api/canvases/<canvas_id>/versions/<int:version_number>', methods=['GET'])
async def get_canvas_version_endpoint(canvas_id, version_number):
    """Get a specific version of a canvas content."""
    chat_id = request.args.get('chat_id')
    if not chat_id:
        return jsonify({"error": "chat_id is required"}), 400
        
    version = get_canvas_version(canvas_id, chat_id, version_number)
    if version is None:
        return jsonify({"success": False, "error": "Version not found"}), 404

    return jsonify({
        "success": True,
        "canvas_id": canvas_id,
        "version_number": version_number,
        "content": version['content']
    })


@app.route('/api/canvases/<canvas_id>/versions/<int:version_number>/restore', methods=['POST'])
async def restore_canvas_version_endpoint(canvas_id, version_number):
    """Restore a canvas to a previous version."""
    data = request.json or {}
    chat_id = data.get('chat_id') or request.args.get('chat_id')
    if not chat_id:
        return jsonify({"error": "chat_id is required"}), 400
        
    from backend.canvas_manager import restore_canvas_version
    result = await restore_canvas_version(canvas_id, chat_id, version_number)
    if result['success']:
        return jsonify(result)
    return jsonify(result), 404


@app.route('/api/canvases/<canvas_id>/diff', methods=['POST'])
async def get_canvas_diff_endpoint(canvas_id):
    """Get diff between two versions."""
    data = request.json or {}
    chat_id = data.get('chat_id') or request.args.get('chat_id')
    if not chat_id:
        return jsonify({"success": False, "error": "chat_id is required"}), 400

    version1 = data.get('version1')
    version2 = data.get('version2')

    if version1 is None or version2 is None:
        return jsonify({"success": False, "error": "version1 and version2 are required"}), 400

    from backend.canvas_manager import get_canvas_diff
    result = get_canvas_diff(canvas_id, chat_id, version1, version2)
    if result['success']:
        return jsonify(result)
    return jsonify(result), 400


@app.route('/api/canvases/<canvas_id>/current-version', methods=['GET'])
async def get_canvas_current_version_endpoint(canvas_id):
    """Get the current active version number for a canvas."""
    chat_id = request.args.get('chat_id')
    if not chat_id:
        return jsonify({"error": "chat_id is required"}), 400

    current_version_obj = db.get_canvas_current_version(canvas_id=canvas_id, chat_id=chat_id)
    current_version = current_version_obj.get('version_number') if current_version_obj else None

    return jsonify({
        "success": True,
        "canvas_id": canvas_id,
        "current_version": current_version
    })


@app.route('/api/canvases/<canvas_id>/navigate-version', methods=['POST'])
async def navigate_to_version_endpoint(canvas_id):
    """Navigate to a specific version of a canvas without creating a new version."""
    data = request.json or {}
    chat_id = data.get('chat_id')
    version_number = data.get('version_number')

    if not chat_id or version_number is None:
        return jsonify({"success": False, "error": "chat_id and version_number are required"}), 400

    from backend.canvas_manager import navigate_canvas_version
    result = await navigate_canvas_version(canvas_id, chat_id, version_number)
    return jsonify(result)


@app.route('/api/canvases/<canvas_id>/delete-future-versions', methods=['POST'])
async def delete_future_versions_endpoint(canvas_id):
    """Delete all versions after a specific version (for branch handling)."""
    data = request.json or {}
    chat_id = data.get('chat_id')
    up_to_version = data.get('up_to_version')

    if not chat_id:
        return jsonify({"error": "chat_id is required"}), 400
    if up_to_version is None:
        return jsonify({"error": "up_to_version is required"}), 400

    deleted_count = db.delete_canvas_versions_after(canvas_id=canvas_id, chat_id=chat_id, up_to_version=up_to_version)

    return jsonify({
        "success": True,
        "canvas_id": canvas_id,
        "deleted_versions": deleted_count,
        "up_to_version": up_to_version
    })


@app.route('/api/canvases/<canvas_id>/share', methods=['POST'])
def share_canvas_endpoint(canvas_id):
    """Share a canvas with another user."""
    data = request.json or {}
    chat_id = data.get('chat_id') or request.args.get('chat_id')
    if not chat_id:
        return jsonify({"error": "chat_id is required"}), 400

    canvas = db.get_canvas_meta(canvas_id=canvas_id, chat_id=chat_id)
    if not canvas:
        return jsonify({"error": "Canvas not found"}), 404

    user_id = data.get('user_id', 'any_user')
    permission = data.get('permission', 'write')

    from backend.canvas_manager import share_canvas
    result = share_canvas(canvas_id, chat_id, user_id, permission)
    if result['success']:
        return jsonify(result)
    return jsonify(result), 400


@app.route('/api/canvases/<canvas_id>/unshare', methods=['POST'])
def unshare_canvas_endpoint(canvas_id):
    """Remove user access to a canvas."""
    data = request.json or {}
    chat_id = data.get('chat_id') or request.args.get('chat_id')
    if not chat_id:
        return jsonify({"error": "chat_id is required"}), 400

    canvas = db.get_canvas_meta(canvas_id=canvas_id, chat_id=chat_id)
    if not canvas:
        return jsonify({"error": "Canvas not found"}), 404

    user_id = data.get('user_id', 'any_user')

    from backend.canvas_manager import unshare_canvas
    result = unshare_canvas(canvas_id, chat_id, user_id)
    if result['success']:
        return jsonify(result)
    return jsonify(result), 400


@app.route('/api/canvases/<canvas_id>/shared-users', methods=['GET'])
def get_shared_users_endpoint(canvas_id):
    """Get list of users who have access to a canvas."""
    chat_id = request.args.get('chat_id')
    if not chat_id:
        return jsonify({"error": "chat_id is required"}), 400

    canvas = db.get_canvas_meta(canvas_id=canvas_id, chat_id=chat_id)
    if not canvas:
        return jsonify({"error": "Canvas not found"}), 404

    from backend.canvas_manager import get_shared_users
    users = get_shared_users(canvas_id, chat_id)
    return jsonify({
        "success": True,
        "canvas_id": canvas_id,
        "users": users
    })


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
    """Proxy GET models endpoints to the local AI backend, injecting the API key."""
    api_url = config.AI_URL.rstrip("/")
    
    base_url = api_url[:-3] if api_url.endswith('/v1') else api_url
    endpoint = f"{base_url}/v1/models"
    headers = {"Content-Type": "application/json"}
    if config.AI_API_KEY:
        headers["Authorization"] = f"Bearer {config.AI_API_KEY}"
        
    try:
        response = requests.get(endpoint, headers=headers, timeout=10)
        return Response(response.content, status=response.status_code, content_type=response.headers.get('content-type', 'application/json'))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/models/config', methods=['GET'])
def get_model_config():
    config_path = os.path.join(os.path.dirname(__file__), 'backend', 'model_config.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/models/load', methods=['POST'])
def proxy_load_model():
    """Proxy POST to llama.cpp /models/load."""
    data = request.json or {}
    api_url = config.AI_URL.rstrip("/")
    
    base_url = api_url[:-3] if api_url.endswith('/v1') else api_url
    endpoint = f"{base_url}/models/load"
        
    headers = {"Content-Type": "application/json"}
    if config.AI_API_KEY:
        headers["Authorization"] = f"Bearer {config.AI_API_KEY}"
        
    try:
        response = requests.post(endpoint, json=data, headers=headers, timeout=60)
        return Response(response.content, status=response.status_code, content_type=response.headers.get('content-type', 'application/json'))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/models/unload', methods=['POST'])
def proxy_unload_model():
    """Proxy POST to llama.cpp /models/unload."""
    data = request.json or {}
    api_url = config.AI_URL.rstrip("/")
    
    base_url = api_url[:-3] if api_url.endswith('/v1') else api_url
    endpoint = f"{base_url}/models/unload"
        
    headers = {"Content-Type": "application/json"}
    if config.AI_API_KEY:
        headers["Authorization"] = f"Bearer {config.AI_API_KEY}"
        
    try:
        response = requests.post(endpoint, json=data, headers=headers, timeout=60)
        return Response(response.content, status=response.status_code, content_type=response.headers.get('content-type', 'application/json'))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    try:
        data = request.json
        raw_messages = data.get('messages', [])
        messages = []
        for msg in raw_messages:
            clean_msg = dict(msg)
            # AGENTS.md compliance: ensure all required string fields are never None
            if clean_msg.get('role') is None:
                clean_msg['role'] = "user"
            if clean_msg.get('content') is None:
                clean_msg['content'] = ""
            # AGENTS.md / llama.cpp compliance: 'content' MUST be a string or array.
            # If it's a dict/object (e.g. a raw tool result that wasn't serialized),
            # coerce it to a JSON string to prevent a 400 from the inference server.
            content_val = clean_msg.get('content')
            if content_val is not None and not isinstance(content_val, (str, list)):
                clean_msg['content'] = json.dumps(content_val)
            if clean_msg.get('tool_call_id') is None and clean_msg.get('role') == 'tool':
                clean_msg['tool_call_id'] = ""
            if clean_msg.get('name') is None and clean_msg.get('role') == 'tool':
                clean_msg['name'] = ""
            messages.append(clean_msg)
        model = data.get('model', 'local-model')
        chat_id = data.get('chatId')
        memory_mode = data.get('memoryMode', False)
        research_mode = data.get('researchMode', False)
        search_depth_mode = data.get('searchDepthMode') or 'regular'
        vision_model = data.get('visionModel')
        vision_enabled = data.get('visionEnabled', True)
        approved_plan = data.get('approvedPlan')
        resume_state = data.get('resumeState')
        last_model_name = data.get('lastModelName', model)
        canvas_mode = data.get('canvasMode', False)
        active_canvas_context = data.get('activeCanvasContext')
        enable_thinking = data.get('enable_thinking', True)

        # Check if chat has canvases in DB - auto-enable canvas_mode if so
        canvases = db.get_chat_canvases(chat_id=chat_id)
        if len(canvases) > 0:
            canvas_mode = True

        # Enforce secrets for security and to prevent empty frontend overrides
        api_url = config.AI_URL
        api_key = config.AI_API_KEY

        # Blacklist keys that should never be forwarded or overridden by client
        blacklist = [
            'messages', 'chatId', 'memoryMode', 'researchMode',
            'searchDepthMode', 'visionModel', 'stream', 'approvedPlan',
            'resumeState', 'lastModelName', 'hasVision', 'apiKey', 'apiUrl',
            'canvasMode', 'activeCanvasContext', 'enable_thinking'
        ]
        extra_body = {k: v for k, v in data.items() if k not in blacklist}

        if not chat_id or '..' in chat_id or '/' in chat_id or '\\' in chat_id:
             return jsonify({"error": "Invalid or missing chatId"}), 400

        # === 1. Handle Active Tasks (Resume/Stream) ===
        if task_manager.is_task_running(chat_id):
            # If task is running, subscribe to its cache stream
            def generate_stream():
                for chunk in cache_system.subscribe(chat_id):
                    if isinstance(chunk, str) and chunk.startswith("data: "):
                        yield chunk
                    elif isinstance(chunk, dict) and "data" in chunk and isinstance(chunk["data"], str) and chunk["data"].startswith("data: "):
                        # Unpack research activity dicts if they were saved as dicts
                        yield chunk["data"]
            return Response(generate_stream(), mimetype='text/event-stream')

        existing_chat = db.get_chat(chat_id=chat_id)
        res_comp = existing_chat.get('research_completed', 0) if existing_chat else 0
        
        # Reset if new cycle started (user sends message while mode is ON but previous run was finished)
        if research_mode and res_comp == 1 and messages and messages[-1]['role'] == 'user' and not approved_plan:
             res_comp = 0
             # Clean up previous research state to allow fresh start
             scout_history_path = os.path.join(config.DATA_DIR, "tasks", f"{chat_id}_scout_history.json")
             planner_history_path = os.path.join(config.DATA_DIR, "tasks", f"{chat_id}_planner_history.json")
             for p in [scout_history_path, planner_history_path]:
                 if os.path.exists(p):
                     try: os.remove(p)
                     except: pass

        # === 2. Persist User Message Immediately (for new turns) ===
        if messages and messages[-1]['role'] == 'user':
            user_msg = messages[-1]
            title = user_msg['content']
            
            # --- MODEL LOCKING FOR RESEARCH ---
            # Once a Research conversation starts, the models should not be allowed to change.
            if existing_chat and (existing_chat.get('research_mode') or existing_chat.get('had_research')):
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
                title = next((p.get('text', '') for p in title if p.get('type') == 'text'), "Image Message")

            if research_mode and existing_chat:
                # If we are in research mode and the chat already exists, 
                # preserve the original topic title unless it was manually named.
                # This prevents plan edits/clarifications from overwriting the research topic.
                if not existing_chat.get('is_custom_title'):
                    title = existing_chat.get('title', title)

            if isinstance(title, str):
                title = title[:50]
            else:
                title = "New Chat"
            # Extract folder from request or preserve existing
            folder = data.get('folder')
            if folder is None and existing_chat:
                folder = existing_chat.get('folder')

            db.save_chat(
                chat_id=chat_id,
                title=title,
                timestamp=time.time(),
                memory_mode=1 if memory_mode else 0,
                research_mode=1 if research_mode else 0,
                is_vision=1 if new_is_vision else 0,
                last_model=last_model_name,
                vision_model=vision_model,
                max_tokens=data.get('max_tokens', 16384),
                folder=folder,
                search_depth_mode=search_depth_mode,
                research_completed=res_comp,
                canvas_mode=1 if canvas_mode else 0,
                enable_thinking=1 if enable_thinking else 0,
                temperature=data.get('temperature', 1.0),
                top_p=data.get('top_p', 1.0),
                top_k=data.get('top_k', 40),
                min_p=data.get('min_p', 0.05),
                presence_penalty=data.get('presence_penalty', 0.0),
                frequency_penalty=data.get('frequency_penalty', 0.0)
            )
            content_to_save = json.dumps(user_msg['content']) if isinstance(user_msg['content'], (list, dict)) else user_msg['content']
            db.add_message(chat_id=chat_id, role='user', content=content_to_save, model=model)

        # === 3. Enqueue Background Task ===
        if research_mode and approved_plan:
            # Sync engineering URL and Key with the request
            if hasattr(research_rag.embedding_fn, 'api_url'):
                research_rag.embedding_fn.api_url = api_url
            if hasattr(research_rag.embedding_fn, 'api_key'):
                research_rag.embedding_fn.api_key = api_key

            # 1. Forge the tool call in history for 'execute_research_plan'
            import uuid
            tc_id = f"manual-{uuid.uuid4().hex[:8]}"
            plan_str = json.dumps(approved_plan) if not isinstance(approved_plan, str) else approved_plan
            topic = (existing_chat.get('title') if existing_chat else None) or "Deep Research Run"

            assist_tc = [{
                "id": tc_id,
                "type": "function",
                "function": {
                    "name": "execute_research_plan",
                    "arguments": json.dumps({"topic": topic, "plan": plan_str})
                }
            }]

            # Add messages to DB and local list for context
            db.add_message(chat_id=chat_id, role='assistant', content=None, tool_calls=json.dumps(assist_tc), model=model)
            messages.append({"role": "assistant", "content": None, "tool_calls": assist_tc, "model": model})

            tool_res = "Research execution started."
            db.add_message(chat_id=chat_id, role='tool', content=tool_res, tool_call_id=tc_id, name="execute_research_plan", model=model)
            messages.append({"role": "tool", "content": tool_res, "tool_call_id": tc_id, "name": "execute_research_plan", "model": model})

            # Get vision_enabled flag from request or default to True
            vision_enabled = data.get('visionEnabled', True)
            task_manager.start_research_task(
                model, messages, approved_plan, chat_id, search_depth_mode, vision_model, generate_research_response,
                model_name=last_model_name, resume_state=resume_state, rag_engine=research_rag, rag=rag, api_url=api_url, api_key=api_key,
                topic_override=topic, vision_enabled=vision_enabled
            )
        else:
            # Normal Chat Task or Research Planning phase
            if hasattr(rag.embedding_fn, 'api_url'):
                rag.embedding_fn.api_url = api_url
            if hasattr(rag.embedding_fn, 'api_key'):
                rag.embedding_fn.api_key = api_key
            has_vision = data.get('hasVision', False)
            
            initial_tool_calls = None
            topic_override = None
            if research_mode and messages and messages[-1]['role'] == 'user':
                # Check for Edit: Is this user message a follow-up to a draft plan?
                is_edit = False
                is_clarification = False
                
                last_assistant_msg = None
                for m in reversed(messages[:-1]):
                    if m['role'] == 'assistant' and m.get('content'):
                        last_assistant_msg = m
                        break
                
                if last_assistant_msg and '<research_plan>' in str(last_assistant_msg.get('content', '')):
                    is_edit = True
                
                # Check for Clarification: Does scout history exist without a planner history?
                scout_history_path = os.path.join(config.DATA_DIR, "tasks", f"{chat_id}_scout_history.json")
                planner_history_path = os.path.join(config.DATA_DIR, "tasks", f"{chat_id}_planner_history.json")
                if os.path.exists(scout_history_path) and not os.path.exists(planner_history_path):
                    try:
                        with open(scout_history_path, 'r') as f:
                            shist = json.load(f)
                        if shist and shist[-1]['role'] == 'assistant' and 'clarifying_question' in shist[-1]['content']:
                            is_clarification = True
                    except:
                        pass

                is_initial_research = False
                if research_mode and not res_comp:
                    # Trigger initial research if:
                    # 1. This is the very first turn (messages length 1 or 2 with system prompt)
                    # 2. Or, Research was just toggled ON in an existing chat (no history files exist yet)
                    is_new_chat_start = len(messages) <= (2 if messages and messages[0].get('role') == 'system' else 1)
                    no_research_history = not os.path.exists(scout_history_path) and not os.path.exists(planner_history_path)
                    
                    if (is_new_chat_start or no_research_history) and not approved_plan and not resume_state:
                        is_initial_research = True

                if is_edit or is_clarification or is_initial_research or resume_state:
                    import uuid
                    tc_id = f"manual-{uuid.uuid4().hex[:8]}"
                    
                    # Correctly identify the original topic from history
                    original_topic = "Unknown"
                    for m in messages:
                        if m['role'] == 'user' and not m.get('resumeState'):
                            content = m['content']
                            if isinstance(content, list):
                                original_topic = next((p.get('text', '') for p in content if p.get('type') == 'text'), "Unknown")
                            else:
                                original_topic = content
                            break
                    
                    user_input = messages[-1]['content']
                    
                    # Scenario 1 (Initial): Current input IS the topic
                    # Scenario 2 (Clarification): Current input IS the topic update
                    # Scenario 3 (Edit): Current input IS the refinement/edit
                    tool_args = {}
                    if is_initial_research or is_clarification:
                        tool_args = {"topic": user_input, "edits": None}
                    else:
                        tool_args = {"topic": original_topic, "edits": user_input}
                    
                    topic_override = tool_args["topic"]

                    initial_tool_calls = [{
                        "id": tc_id,
                        "type": "function",
                        "function": {
                            "name": "initiate_research_plan",
                            "arguments": json.dumps(tool_args)
                        }
                    }]
            
            task_manager.start_chat_task(
                chat_id,
                generate_chat_response,
                stream=True,
                model=model,
                messages=messages,
                resume_state=resume_state,
                canvas_mode=canvas_mode,
                active_canvas_context=active_canvas_context,
                extra_body=extra_body,
                rag=rag,
                memory_mode=memory_mode,
                search_depth_mode=search_depth_mode,
                has_vision=has_vision,
                api_url=api_url,
                api_key=api_key,
                research_mode=research_mode,
                research_completed=res_comp,
                initial_tool_calls=initial_tool_calls,
                topic_override=topic_override,
                enable_thinking=enable_thinking
            )

        # === 4. Return Stream Subscription ===
        def generate_stream():
            # Wait briefly for cache initialization to ensure subscriber doesn't miss start
            time.sleep(0.1)
            for chunk in cache_system.subscribe(chat_id):
                if isinstance(chunk, str) and chunk.startswith("data: "):
                    yield chunk
                elif isinstance(chunk, dict) and "data" in chunk and isinstance(chunk["data"], str) and chunk["data"].startswith("data: "):
                    yield chunk["data"]
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


@app.route('/api/logs/app', methods=['GET'])
def get_app_logs():
    """Get app logs from the log file."""
    log_file = os.path.join(config.DATA_DIR, "logs", "app.log")
    logs = []
    if os.path.exists(log_file):
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    logs.append(line.strip())
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    # Return last 1000 lines by default
    return jsonify({"logs": logs[-1000:], "total": len(logs)})


@app.route('/api/logs/app/lines', methods=['GET'])
def get_app_log_lines():
    """Get app logs within a line range."""
    log_file = os.path.join(config.DATA_DIR, "logs", "app.log")
    start = request.args.get('start', 0, type=int)
    end = request.args.get('end', 100, type=int)

    if not os.path.exists(log_file):
        return jsonify({"logs": [], "start": start, "end": end})

    try:
        with open(log_file, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            # Convert to JSON-serializable format
            logs = [line.rstrip('\n') for line in all_lines[start:end]]
        return jsonify({"logs": logs, "start": start, "end": end, "total": len(all_lines)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
