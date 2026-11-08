from flask import Flask, request, jsonify, Response, send_from_directory
from werkzeug.exceptions import RequestEntityTooLarge
from backend.logging import log_event
import logging
import os
import time
import json
import requests
import shutil
from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv()

logger = logging.getLogger(__name__)

# Set correct timezone dynamically for the process
if os.environ.get('TZ') is None:
    os.environ['TZ'] = 'Asia/Kolkata'
if os.name != 'nt' and hasattr(time, 'tzset'):
    time.tzset()

from backend import config
from backend.rag import RAGProvider
from backend.database import db
from backend.database.init_db import init_db
from backend.models import get_embedding_model
from backend.file_system import (
    FileSystemChannelManager, file_system_bp
)
from backend.files import FileManager, files_bp
from backend.task_manager import task_manager
from backend.database import response_cache as cache_system
from backend.version import get_version, VERSION_MAJOR, VERSION_MINOR, VERSION_PATCH
from backend.chat.router import chat_bp, openai_bp, personas_bp, skills_bp
from backend.tools.router import tools_bp
from backend.files.router import files_bp
from backend.logging.router import logs_bp
from backend.models import models_bp

# _agent_callbacks moved to ChatHandler

app = Flask(__name__, static_folder='static')
# Register New Chat Architecture Blueprints
app.register_blueprint(chat_bp, url_prefix='/api/chats')
app.register_blueprint(personas_bp, url_prefix='/api')
app.register_blueprint(skills_bp, url_prefix='/api')
app.register_blueprint(tools_bp, url_prefix='/api/tools')
app.register_blueprint(openai_bp, url_prefix='/v1/chat')
app.register_blueprint(file_system_bp, url_prefix='/api/file_systems')
app.register_blueprint(logs_bp, url_prefix='/api/logs')
app.register_blueprint(files_bp, url_prefix='/api/files')
app.register_blueprint(models_bp, url_prefix='/api/models')

from flask_sock import Sock
import websocket as ws_client
import threading
sock = Sock(app)
app.config['SOCK_SERVER_OPTIONS'] = {'subprotocols': ['binary']}

@sock.route('/api/tools/portal/ws')
def portal_ws_proxy(ws):
    """
    Bidirectional WebSocket proxy: browser <-> playwright_mcp websockify.
    Uses a background thread to forward upstream→browser while the main
    thread handles browser→upstream. This avoids poll-loop timing issues
    with flask-sock's receive() semantics.
    """
    upstream_url = "ws://playwright_mcp:6080/websockify"
    closed = threading.Event()
    upstream = None

    try:
        upstream = ws_client.create_connection(upstream_url)

        # Thread: upstream (VNC) → browser
        def upstream_to_browser():
            try:
                while not closed.is_set():
                    try:
                        opcode, data = upstream.recv_data(control_frame=False)
                        if not data:
                            break
                        ws.send(data)
                    except Exception:
                        break
            finally:
                closed.set()

        t = threading.Thread(target=upstream_to_browser, daemon=True)
        t.start()

        # Main thread: browser → upstream (VNC)
        while not closed.is_set():
            try:
                data = ws.receive()
                if data is None:
                    break
                if isinstance(data, bytes):
                    upstream.send_binary(data)
                else:
                    upstream.send(data)
            except Exception:
                break

    except Exception as e:
        logger.error(f"Portal WS proxy error: {e}")
    finally:
        closed.set()
        if upstream:
            try:
                upstream.close()
            except Exception:
                pass


@sock.route('/api/tools/code-execution/ws')
def code_execution_ws_proxy(ws):
    """
    Bidirectional WebSocket proxy: browser <-> code_runner_mcp /ws/execute.
    Handles relative path resolution and folder tree collection first, 
    then opens the websocket connection to code_runner_mcp.
    """
    # Wait for the first message which contains filePath and chat_id
    closed = threading.Event()
    upstream = None
    try:
        init_msg_raw = ws.receive()
        if not init_msg_raw:
            return
        init_msg = json.loads(init_msg_raw)
        if init_msg.get("type") != "init":
            ws.send(json.dumps({"type": "stderr", "data": "Error: First message must be init.\n"}))
            return
            
        file_path = init_msg.get("filePath")
        chat_id = init_msg.get("chat_id")
        sql_target = init_msg.get("sql_target", "sqlite")
        
        if not file_path or not chat_id:
            ws.send(json.dumps({"type": "stderr", "data": "Error: Missing filePath or chat_id.\n"}))
            return
            
        # Walk and collect files like run_file does!
        from backend.tools.implementations.code_executor import collect_project_files
        
        try:
            lang, files_list, entry_file = collect_project_files(chat_id, file_path)
        except Exception as e:
            ws.send(json.dumps({"type": "stderr", "data": f"Error: {e}\n"}))
            ws.send(json.dumps({"type": "exit", "code": 1}))
            return
            
        # Get configured code execution timeout
        timeout = db.get_setting("code_runner_timeout", config.CODE_RUNNER_DEFAULT_TIMEOUT)

        # 2. Connect to code_runner_mcp
        api_key = config.CODE_RUNNER_API_KEY
        upstream_url = f"{config.CODE_RUNNER_URL.replace('http://', 'ws://').rstrip('/')}/ws/execute?api_key={api_key}"
        
        upstream = ws_client.create_connection(upstream_url)
        
        # Send initial configuration to code_runner_mcp
        config_payload = {
            "language": lang,
            "files": files_list,
            "entry_file": entry_file,
            "args": [],
            "sql_target": sql_target,
            "timeout": timeout
        }
        upstream.send(json.dumps(config_payload))
        
        # Thread: upstream (code_runner) -> browser
        def upstream_to_browser():
            try:
                while not closed.is_set():
                    try:
                        data = upstream.recv()
                        if not data:
                            break
                        # Send directly to the browser
                        ws.send(data)
                    except Exception:
                        break
            finally:
                closed.set()
                try:
                    ws.close()
                except Exception:
                    pass
                
        t = threading.Thread(target=upstream_to_browser, daemon=True)
        t.start()
        
        # Main thread: browser -> upstream
        while not closed.is_set():
            try:
                data = ws.receive()
                if data is None:
                    break
                # Forward input to upstream
                upstream.send(data)
            except Exception:
                break
                
    except Exception as e:
        logger.error(f"Code execution WS proxy error: {e}", exc_info=True)
        try:
            ws.send(json.dumps({"type": "stderr", "data": f"Proxy error: {e}\n"}))
        except Exception:
            pass
    finally:
        closed.set()
        if upstream:
            try:
                upstream.close()
            except Exception:
                pass

# Limit request size to 100MB to match FILE_UPLOAD_MAX_SIZE config
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024


# Initialize components with config - load models from model_loader (no fallbacks)
init_db()
embedding_model = get_embedding_model()

# Initialize RAGManager for Research and File RAG (singleton) via provider
rag_manager = RAGProvider.get_manager(
    persist_path=config.CHROMA_PATH,
    embedding_model=embedding_model
)

# Initialize file manager with shared RAG manager
file_manager = FileManager(rag_manager=rag_manager)

task_manager.recover_tasks()

# Initialize file_system channel manager for per-chat locking
FileSystemChannelManager.initialize()

import asyncio
try:
    loop = asyncio.get_event_loop()
    # Start InferenceEngine
    from backend.inference import InferenceEngine
    loop.run_until_complete(InferenceEngine().start())
except RuntimeError:
    from backend.inference import InferenceEngine
    asyncio.run(InferenceEngine().start())


FRONTEND_DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frontend', 'dist')
LEGACY_PREFIX = '/legacy'


def _react_enabled():
    return config.FRONTEND == 'react'


def _serve_react_index():
    if not os.path.isfile(os.path.join(FRONTEND_DIST, 'index.html')):
        return Response('Frontend not built. Run `npm ci && npm run build` in frontend/, '
                        'or set FRONTEND=legacy.', 503, {'Content-Type': 'text/plain'})
    return send_from_directory(FRONTEND_DIST, 'index.html')


def _serve_legacy_page(filename):
    """Serve a legacy HTML page under /legacy/ with its absolute asset paths rewritten."""
    with open(os.path.join('static', filename), encoding='utf-8') as f:
        html = f.read()
    html = (html.replace('src="/js/', f'src="{LEGACY_PREFIX}/js/')
                .replace('href="/styles.css"', f'href="{LEGACY_PREFIX}/styles.css"'))
    return Response(html, mimetype='text/html')


@app.route('/')
@app.route('/chat/<chat_id>')
@app.route('/workspace/<workspace_id>')
def index(chat_id=None, workspace_id=None):
    if _react_enabled():
        return _serve_react_index()
    return send_from_directory('static', 'index.html')

@app.route('/logs')
def react_logs_page():
    if _react_enabled():
        return _serve_react_index()
    return send_from_directory('static', 'logs.html')

@app.route('/assets/<path:path>')
def react_assets(path):
    if not _react_enabled():
        return Response('Not Found', 404)
    return send_from_directory(os.path.join(FRONTEND_DIST, 'assets'), path)

@app.route(LEGACY_PREFIX + '/')
@app.route(LEGACY_PREFIX + '/index.html')
def legacy_index():
    return _serve_legacy_page('index.html')

@app.route(LEGACY_PREFIX + '/logs.html')
def legacy_logs():
    return _serve_legacy_page('logs.html')

@app.route(LEGACY_PREFIX + '/<path:path>')
def legacy_assets(path):
    return send_from_directory('static', path)

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
    if not _react_enabled():
        return send_from_directory('static', path)
    # React mode: unknown /api paths are 404; existing files under static/ or frontend/dist/ are served
    # as files (realpath must stay inside the root); anything else is a client-side route and gets the index.
    if path == 'api' or path.startswith('api/'):
        return Response('Not Found', 404)
    for root in ('static', FRONTEND_DIST):
        root_real = os.path.realpath(root)
        candidate = os.path.realpath(os.path.join(root, path))
        if candidate.startswith(root_real + os.sep) and os.path.isfile(candidate):
            return send_from_directory(root, path)
    # A missing file (a path with an extension) is a 404, not the HTML index.
    if os.path.splitext(path)[1]:
        return Response('Not Found', 404)
    return _serve_react_index()


# Error handler for 413 Request Entity Too Large
@app.errorhandler(RequestEntityTooLarge)
def handle_large_file_error(e):
    """Handle files that exceed MAX_CONTENT_LENGTH."""
    return jsonify({
        "error": f"File too large. Maximum size is {100 * 1024 * 1024} bytes (100MB)"
    }), 413



@app.route('/api/version', methods=['GET'])
def get_version_endpoint():
    """Return the application version."""
    return jsonify({
        "version": get_version(),
        "major": VERSION_MAJOR,
        "minor": VERSION_MINOR,
        "patch": VERSION_PATCH
    })




if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
