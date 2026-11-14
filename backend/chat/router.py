from flask import Blueprint, Response, jsonify
import logging
import json
import time
from typing import Dict, Any

from backend.chat.handler import ChatHandler
from backend.auth import rate_limit
from backend.auth.context import current_user, current_user_id
from backend.auth.ownership import claim_chat, reject_foreign_chat, require_chat_owner, require_workspace_owner
from backend.chat.message_edit import merge_edited_user_content
from backend.database import db
from backend.logging import log_event, error_detail
from backend.task_manager import task_manager
from backend.utils import read_json_object
from backend.file_system import FileSystemChannelManager
from backend.files.router import get_file_manager
from backend import config
from backend.error_handling import USER_STREAM_ERROR
import os

logger = logging.getLogger(__name__)



chat_bp = Blueprint('chat', __name__)
openai_bp = Blueprint('openai', __name__)

FILE_SYSTEMS_DIR = os.path.join(config.DATA_DIR, "file_systems")
STILL_STOPPING = "The chat is still stopping its response; try again in a moment."

# =============================================================================
# GLOBAL CHAT MANAGEMENT (Route Prefix: /api/chats)
# =============================================================================

@chat_bp.route('', methods=['GET'])
@chat_bp.route('/', methods=['GET'])
def list_chats():
    logger.debug("[API] GET /api/chats - listing chats that have content")
    chats = db.get_listed_chats(current_user_id())
    return jsonify(chats)

@chat_bp.route('/workspaces', methods=['GET'])
def list_workspaces():
    workspaces = db.get_all_workspaces(current_user_id())
    return jsonify(workspaces)

@chat_bp.route('/workspaces', methods=['POST'])
def create_workspace():
    data, err = read_json_object()
    if err:
        return err
    name = data.get('name')
    if not name:
        return jsonify({"error": "Missing workspace name"}), 400
    if db.workspace_name_exists(name, current_user_id()):
        return jsonify({"error": f"A workspace named '{name}' already exists"}), 400
    workspace = db.create_workspace(name, current_user_id())
    return jsonify(workspace)

@chat_bp.route('/workspaces/<workspace_id>', methods=['PATCH'])
def rename_workspace(workspace_id):
    denied = require_workspace_owner(workspace_id)
    if denied:
        return denied
    data, err = read_json_object(required=False)
    if err:
        return err
    new_name = data.get('name')
    has_icon = 'icon' in data
    if not new_name and not has_icon:
        return jsonify({"error": "Missing workspace update fields (name or icon)"}), 400
    # Check before any write so a rejected rename changes neither the name nor the icon.
    if new_name and db.workspace_name_exists(new_name, current_user_id(), exclude_id=workspace_id):
        return jsonify({"error": f"A workspace named '{new_name}' already exists"}), 400
    if has_icon:
        db.update_workspace_icon(workspace_id, data.get('icon'))
    if new_name:
        db.rename_workspace(workspace_id, new_name)
    return jsonify({"success": True})

@chat_bp.route('/workspaces/<workspace_id>', methods=['DELETE'])
def delete_workspace(workspace_id):
    denied = require_workspace_owner(workspace_id)
    if denied:
        return denied
    db.delete_workspace(workspace_id)
    return jsonify({"success": True})

@chat_bp.route('', methods=['DELETE'])
@chat_bp.route('/', methods=['DELETE'])
def clear_all_chats():
    """Deletes every chat of the caller. Their running turns are stopped first (a turn that has not ended in time is a 409)."""
    user_id = current_user_id()
    mine = {c['id'] for c in db.get_all_chats(user_id)}
    # One shared deadline: the request waits at most TASK_STOP_WAIT_SECONDS in total. A turn that starts
    # while the others are stopping is caught by the next pass.
    deadline = time.monotonic() + config.TASK_STOP_WAIT_SECONDS
    stopped = []
    while True:
        running = [cid for cid in task_manager.running_chat_ids() if cid in mine]
        if not running:
            break
        if stopped and time.monotonic() >= deadline:
            log_event("chat_clear_all_stop_timeout", {"chat_ids": running})
            return jsonify({"error": STILL_STOPPING}), 409
        for chat_id in running:
            task_manager.stop_task(chat_id)
        still_running = [
            chat_id for chat_id in running
            if not task_manager.stop_task_and_wait(chat_id, max(0.0, deadline - time.monotonic()))
        ]
        if still_running:
            log_event("chat_clear_all_stop_timeout", {"chat_ids": still_running})
            return jsonify({"error": STILL_STOPPING}), 409
        stopped += running
    from backend.tools.callbacks import callback_registry
    from backend.database import response_cache
    for chat_id in stopped:
        callback_registry.cleanup_chat(chat_id)
        response_cache.cleanup_chat(chat_id)
    for chat_id in mine:
        task_manager.forget_chat(chat_id)
    db.delete_all_chats(user_id)
    return jsonify({"success": True})

@chat_bp.route('/save', methods=['POST'])
def save_chat_endpoint():
    data, err = read_json_object()
    if err:
        return err
    chat_id = data.get('chat_id')
    title = data.get('title', 'New Chat')
    messages = data.get('messages')
    user_preferences = data.get('user_preferences', False)
    research_mode = data.get('research_mode', False)
    max_tokens = data.get('max_tokens', 16384)
    thinking_budget_tokens = data.get('thinking_budget_tokens', 2000)
    file_system_mode = data.get('file_system_mode', False)
    browsing_mode = data.get('browsing_mode', False)
    logger.debug("[API] POST /api/chats/save - chat_id=%s title=%s", chat_id, title)

    if not chat_id or '..' in chat_id or '/' in chat_id or '\\' in chat_id:
        return jsonify({"error": "Invalid or missing chat_id"}), 400

    existing_chat = db.get_chat(chat_id)
    if existing_chat:
        denied = require_chat_owner(chat_id)  # another user's chat is a 404, never a 403
        if denied:
            return denied
        return jsonify({"error": "Cannot overwrite existing chat history via save endpoint. Use Action-Based APIs."}), 403

    # Ids must be strings (a list or object would reach sqlite and fail with a 500)
    for field in ('persona_id', 'workspace_id', 'folder'):
        if data.get(field) and not isinstance(data.get(field), str):
            return jsonify({"error": f"{field} must be a string"}), 400

    # A persona must be the caller's (a falsy persona_id is saved as before, i.e. none)
    if data.get('persona_id') and not db.get_persona(data.get('persona_id'), current_user_id()):
        return jsonify({"error": "Persona not found"}), 404

    save_workspace_id = data.get('workspace_id') or data.get('folder')
    if save_workspace_id:
        denied = require_workspace_owner(save_workspace_id)
        if denied:
            return denied

    # Claim the new chat for the caller first (404 if another user created it meanwhile); the writes below then only
    # touch the caller's own row.
    denied = claim_chat(chat_id)
    if denied:
        return denied

    file_systems = db.get_chat_file_systems(chat_id)
    if len(file_systems) > 0:
        file_system_mode = True

    db.save_chat(
        chat_id=chat_id,
        title=title,
        timestamp=time.time(),
        user_preferences=1 if user_preferences else 0,
        research_mode=1 if research_mode else 0,
        is_vision=1 if data.get('is_vision', False) else 0,
        last_model=data.get('last_model'),
        vision_model=data.get('vision_model'),
        max_tokens=max_tokens,
        thinking_budget_tokens=thinking_budget_tokens,
        workspace_id=data.get('workspace_id') or data.get('folder'),
        persona_id=data.get('persona_id'),
        research_completed=data.get('research_completed', 0),
        file_system_mode=1 if file_system_mode else 0,
        browsing_mode=1 if browsing_mode else 0,
        enable_thinking=1 if data.get('enable_thinking', True) else 0,
        temperature=data.get('temperature', 1.0),
        top_p=data.get('top_p', 1.0),
        top_k=data.get('top_k', 40),
        min_p=data.get('min_p', 0.05),
        presence_penalty=data.get('presence_penalty', 0.0),
        frequency_penalty=data.get('frequency_penalty', 0.0),
        user_id=current_user_id()
    )
    db.update_chat(chat_id=chat_id, thinking_profile=data.get('thinking_profile', 'general'))

    return jsonify({"success": True})

@chat_bp.route('/<chat_id>', methods=['PATCH'])
def patch_chat_endpoint(chat_id):
    data, err = read_json_object()
    if err:
        return err
    new_title = data.get('title')
    last_model = data.get('last_model')
    vision_model = data.get('vision_model')
    max_tokens = data.get('max_tokens')
    thinking_budget_tokens = data.get('thinking_budget_tokens')
    workspace_id = data.get('workspace_id') or data.get('folder')
    enable_thinking = data.get('enable_thinking')
    thinking_profile = data.get('thinking_profile')

    # A target workspace must belong to the caller; checked before anything is created or written.
    if workspace_id:
        denied = require_workspace_owner(workspace_id)
        if denied:
            return denied
    denied = claim_chat(chat_id)
    if denied:
        return denied
    existing_chat = db.get_chat(chat_id)

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
    if thinking_budget_tokens is not None:
        db.update_chat(chat_id=chat_id, thinking_budget_tokens=thinking_budget_tokens)
    if 'workspace_id' in data:
        db.update_chat_workspace(chat_id=chat_id, workspace_id=workspace_id)
    if 'research_completed' in data:
        db.mark_research_completed(chat_id=chat_id, completed=data['research_completed'])
    if 'user_preferences' in data:
        db.update_chat(chat_id=chat_id, user_preferences=1 if data['user_preferences'] else 0)
    if 'research_mode' in data:
        db.update_chat(chat_id=chat_id, research_mode=1 if data['research_mode'] else 0)
    if 'file_system_mode' in data:
        db.update_chat(chat_id=chat_id, file_system_mode=1 if data['file_system_mode'] else 0)
    if 'browsing_mode' in data:
        db.update_chat(chat_id=chat_id, browsing_mode=1 if data['browsing_mode'] else 0)
    if 'is_vision' in data:
        db.update_chat(chat_id=chat_id, is_vision=1 if data['is_vision'] else 0)
    if 'thinking_profile' in data:
        db.update_chat(chat_id=chat_id, thinking_profile=data['thinking_profile'])
    if 'enable_thinking' in data:
        db.update_chat(chat_id=chat_id, enable_thinking=1 if data['enable_thinking'] else 0)
    temperature = data.get('temperature')
    top_p = data.get('top_p')
    top_k = data.get('top_k')
    min_p = data.get('min_p')
    presence_penalty = data.get('presence_penalty')
    frequency_penalty = data.get('frequency_penalty')

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
    if 'resume_suppressed' in data:
        db.update_chat(chat_id=chat_id, resume_suppressed=int(data['resume_suppressed']))

    return jsonify({"success": True})

@chat_bp.route('/<chat_id>', methods=['DELETE'])
def remove_chat(chat_id):
    denied = require_chat_owner(chat_id)
    if denied:
        return denied
    # End the chat's turn first: a worker that outlives the chat would write rows for a chat that is gone.
    if not task_manager.stop_task_and_wait(chat_id):
        log_event("chat_delete_stop_timeout", {"chat_id": chat_id})
        return jsonify({"error": STILL_STOPPING}), 409
    from backend.tools.callbacks import callback_registry
    from backend.database import response_cache
    callback_registry.cleanup_chat(chat_id)
    response_cache.cleanup_chat(chat_id)
    from backend.rag import RAGProvider
    from backend.models import get_embedding_model
    from backend.files.manager import FileManager

    # 1. Setup RAG and File Manager for cleanup
    embedding_model = get_embedding_model()
    rag_manager = RAGProvider.get_manager(
        persist_path=config.CHROMA_PATH,
        embedding_model=embedding_model
    )
    file_manager = FileManager(rag_manager=rag_manager)

    # 2. Physical Cleanup of Files (Disk + RAG)
    try:
        chat_files = db.get_chat_files(chat_id)
        for f in chat_files:
            file_manager.delete_file(f['id'])
    except Exception as e:
        logger.error(f"Error during physical file cleanup for chat {chat_id}: {e}")

    # 3. Database Cleanup (the task files go first: a failure there leaves the chat intact)
    task_manager.forget_chat(chat_id)
    db.delete_chat(chat_id=chat_id)
    
    FileSystemChannelManager.release_channel(chat_id)
    return jsonify({"success": True})

# =============================================================================
# INDIVIDUAL CHAT OPERATIONS (Route Prefix: /api/chats/<chat_id>)
# =============================================================================

@chat_bp.route('/<chat_id>', methods=['GET'])
def get_chat_history_full(chat_id):
    """
    Retrieves full woven history for a specific chat.
    Endpoint: GET /api/chats/<chat_id>
    """
    denied = require_chat_owner(chat_id)
    if denied:
        return denied
    try:
        handler = ChatHandler(chat_id)
        result = handler.get_history()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error fetching history for chat {chat_id}: {e}", exc_info=True)
        log_event("chat_history_error", {"chat_id": chat_id, "error": error_detail(e)})
        return jsonify({"error": "Could not load the chat. Try again."}), 500

def _forbid_git_mode_for_non_admin(body):
    """
    403 when the request turns git mode on and the caller is not an admin (git reaches host-wide tools).

    Returns None when the request does not enable git mode or the caller is an admin.
    """
    user = current_user()
    if isinstance(body, dict) and body.get('gitMode') and not (user and user.get('role') == 'admin'):
        return jsonify({"error": "Forbidden"}), 403
    return None


def _turn_rate_limited():
    """
    Count one turn start (send or resume) against the caller's per-minute limit.

    Returns None when the turn may go ahead (or the caller is an exempt admin), else the error response: 401 without a
    user (fail closed), 429 with `Retry-After` over the limit. Checked before any chat or turn is claimed or written.
    """
    user = current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    if rate_limit.is_exempt(user):
        return None
    allowed, retry_after = rate_limit.turn_limiter.try_acquire(user["id"])
    if allowed:
        return None
    log_event("rate_limited", {"kind": "turns"})
    response = jsonify({"error": "Too many requests; try again shortly."})
    response.status_code = 429
    response.headers["Retry-After"] = str(retry_after)
    return response


@openai_bp.route('/completions', methods=['POST'])
def chat_completions():
    """
    Primary OpenAI-compatible endpoint for chat streaming.
    Endpoint: POST /v1/chat/completions
    """
    data, err = read_json_object()
    if err:
        return err
    chat_id = data.get('chatId')
    user_message_raw = data.get('messages')[-1] if data.get('messages') else None
    
    # Extract OpenAI-standard fields
    model = data.get('model')  # No hardcoded fallback to gpt-4o
    files = data.get('uploadedFiles') # Support frontend field name
    
    if not chat_id:
        return jsonify({"error": "chatId is required"}), 400

    # Another user's chat is a 404 before anything else, so the file check below cannot reveal what that chat holds.
    denied = reject_foreign_chat(chat_id)
    if denied:
        return denied

    # Before anything is written or claimed: git mode is admin only.
    denied = _forbid_git_mode_for_non_admin(data)
    if denied:
        return denied

    # Per-user turn limit, before the file checks and the chat claim so a refused request writes nothing.
    denied = _turn_rate_limited()
    if denied:
        return denied

    if files is not None and not isinstance(files, list):
        return jsonify({"error": "uploadedFiles must be a list"}), 400

    # Every attached file must belong to this chat. Checked before the chat is claimed so a rejected request writes nothing.
    for attached in files or []:
        file_meta = db.get_file(attached.get('file_id')) if isinstance(attached, dict) else None
        if not file_meta or file_meta.get('chat_id') != chat_id:
            return jsonify({"error": "Unknown file"}), 400

    # Create the chat for the caller, or refuse (404) another user's chat, before any claim or write.
    denied = claim_chat(chat_id)
    if denied:
        return denied

    # One turn per chat: refuse before a message is stored if a turn is running or being started.
    turns = task_manager  # the same manager claims and releases, whatever happens to the module global
    if not turns.claim_turn(chat_id):
        log_event("chat_send_rejected_turn_in_progress", {"chat_id": chat_id})
        return jsonify({"error": "a response is already in progress"}), 400

    log_event("api_chat_completions", {"chat_id": chat_id, "model": model})

    try:
        # 1. Persist User Message if it's a new turn (the chat exists and is the caller's: claim_chat above)
        persisted_user_msg = None
        if user_message_raw and user_message_raw.get('role') == 'user':
            content = user_message_raw.get('content', '')
            
            # Append file attachment notification if files are present
            if files:
                file_notes = []
                vision_content = []
                
                # Check for images to inject directly for vision
                file_manager = get_file_manager()
                
                for f in files:
                    file_id = f.get('file_id')
                    mime = f.get('mime_type', '')
                    
                    if mime.startswith('image/'):
                        file_meta = db.get_file(file_id)
                        if file_meta:
                            stored_path = os.path.join(config.FILE_STORAGE_PATH, file_meta['stored_filename'])
                            if os.path.exists(stored_path):
                                encoded, mime_type = file_manager.encode_file_for_vision(stored_path)
                                if encoded:
                                    vision_content.append({
                                        "type": "image_url",
                                        "image_url": {"url": f"data:{mime_type};base64,{encoded}"}
                                    })
                    else:
                        file_notes.append(f"- {f.get('name', 'Unknown')} (ID: {file_id})")
                
                if vision_content:
                    note = ""
                    if file_notes:
                        # Parsed for display by splitAttachmentNote (chat-model.ts), kept on edit by message_edit.py.
                        note = "\n\n[System Note: The user has attached the following files. Use the `document_agent` tool with the provided file_id to read their contents if needed:\n" + "\n".join(file_notes) + "]"
                    
                    # Convert to multimodal list, preserving original text if it was a string
                    # If it was already a list, we merge
                    if isinstance(content, list):
                        # Find existing text block or create new one
                        text_block = next((b for b in content if b.get('type') == 'text'), None)
                        if text_block:
                            text_block['text'] += note
                        else:
                            content.insert(0, {"type": "text", "text": note})
                        content.extend(vision_content)
                    else:
                        content_list = [{"type": "text", "text": str(content) + note}]
                        content_list.extend(vision_content)
                        content = content_list
                elif file_notes:
                    # Parsed for display by splitAttachmentNote (chat-model.ts), kept on edit by message_edit.py.
                    note = "\n\n[System Note: The user has attached the following files. Use the `document_agent` tool with the provided file_id to read their contents if needed:\n" + "\n".join(file_notes) + "]"
                    if isinstance(content, list):
                        text_block = next((b for b in content if b.get('type') == 'text'), None)
                        if text_block:
                            text_block['text'] += note
                        else:
                            content.insert(0, {"type": "text", "text": note})
                    else:
                        content = str(content) + note
            
            # Final serialization if it's still a list/dict
            if isinstance(content, (list, dict)):
                content = json.dumps(content)
                
            # Keep only the stable file reference fields on the user message so attachments
            # survive reloads and Retry (resume) can reuse them.
            attachments = None
            if isinstance(files, list):
                attachments = [
                    {k: f[k] for k in ('file_id', 'name', 'size', 'mime_type') if k in f}
                    for f in files if isinstance(f, dict)
                ] or None

            msg_id = db.add_message(
                chat_id=chat_id,
                role='user',
                content=content,
                model=model,
                attachments=attachments
            )

            if files:
                db.add_collection(
                    chat_id=chat_id,
                    parent_message_id=msg_id,
                    parent_type="main",
                    collection_type="files",
                    items=files
                )

            # Update the last_user_id anchor
            db.update_last_user_id(chat_id, msg_id)
            persisted_user_msg = {"id": msg_id, **user_message_raw}

            # Auto-title: if the chat still has the default title, derive one
            # from the first user message content (first 50 chars).
            existing_chat = db.get_chat(chat_id)
            if existing_chat and existing_chat.get('title') == 'New Conversation' and content:
                # For structured content (vision), extract text portion
                title_source = content
                if title_source.startswith('[') or title_source.startswith('{'):
                    try:
                        parsed = json.loads(title_source)
                        if isinstance(parsed, list):
                            text_parts = [p.get('text', '') for p in parsed if isinstance(p, dict) and p.get('type') == 'text']
                            title_source = ' '.join(text_parts)
                    except (json.JSONDecodeError, TypeError):
                        pass
                auto_title = title_source[:50].strip()
                if auto_title:
                    db.rename_chat(chat_id, auto_title)

        # 3. Initialize Handler and Start Stream
        handler = ChatHandler(chat_id)
        
        # Pass extra body params (sampling, etc)
        extra_body = {k: v for k, v in data.items() if k not in ['messages', 'chatId', 'uploadedFiles', 'model']}
        
        def generate_stream():
            import asyncio
            async def run_gen():
                async for chunk in handler.initiate_chat(
                    files=files,
                    user_message=persisted_user_msg,
                    model=model,
                    **extra_body
                ):
                    yield chunk

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            gen = run_gen()
            try:
                while True:
                    try:
                        chunk = loop.run_until_complete(gen.__anext__())
                        yield chunk
                    except StopAsyncIteration:
                        break
                    except Exception as e:
                        logger.error(f"Stream generation error: {e}")
                        log_event("chat_stream_error", {"chat_id": chat_id, "error": error_detail(e)})
                        yield f"data: {json.dumps({'error': USER_STREAM_ERROR})}\n\n"
                        break
            finally:
                loop.close()

        response = Response(generate_stream(), mimetype='text/event-stream')
        # The claim is held until the stream ends or the client disconnects.
        response.call_on_close(lambda: turns.release_turn_claim(chat_id))
        return response

    except Exception as e:
        turns.release_turn_claim(chat_id)
        logger.error(f"Error in chat_completions route: {e}", exc_info=True)
        log_event("chat_completions_error", {"chat_id": chat_id, "error": error_detail(e)})
        return jsonify({"error": "Could not start the answer. Try sending again."}), 500

@chat_bp.route('/<chat_id>/stream', methods=['GET'])
def reattach_stream(chat_id):
    """
    Reattach to an in-progress generation stream.
    Returns 204 if no task is currently running (task already finished).
    """
    denied = require_chat_owner(chat_id)
    if denied:
        return denied
    if not task_manager.is_task_running(chat_id):
        return '', 204

    from backend.database import response_cache

    def generate_stream():
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def subscribe():
            async for chunk in response_cache.subscribe(chat_id):
                yield chunk

        gen = subscribe()
        try:
            while True:
                try:
                    chunk = loop.run_until_complete(gen.__anext__())
                    yield chunk
                except StopAsyncIteration:
                    break
        finally:
            loop.close()

    return Response(generate_stream(), mimetype='text/event-stream')

@chat_bp.route('/<chat_id>/resume', methods=['POST'])
def resume_chat(chat_id):
    """
    Resumes an interrupted chat turn from the last stored user message.

    Returns 400 {"error": "a response is already in progress"} if a turn for the chat is running or
    starting (sends and resumes share one claim per chat, docs/standards/api.md).
    """
    denied = require_chat_owner(chat_id)
    if denied:
        return denied
    resume_body, err = read_json_object(required=False)
    if err:
        return err
    denied = _forbid_git_mode_for_non_admin(resume_body)
    if denied:
        return denied
    denied = _turn_rate_limited()
    if denied:
        return denied
    # Keep a reference so the release in call_on_close targets the manager that took the claim,
    # even if the module-level name is rebound later (as tests do).
    turns = task_manager
    if not turns.claim_turn(chat_id):
        log_event("chat_resume_rejected_turn_in_progress", {"chat_id": chat_id})
        return jsonify({"error": "a response is already in progress"}), 400

    try:
        handler = ChatHandler(chat_id)
        
        # Get last user msg
        messages = db.get_messages(chat_id)
        last_user_msg = next((m for m in reversed(messages) if m['role'] == 'user'), None)
                
        if not last_user_msg:
            turns.release_turn_claim(chat_id)
            return jsonify({"error": "No user message found to resume from."}), 400

        model = resume_body.get('model')
        # Fallback: if frontend didn't send a model (e.g. models not yet loaded),
        # derive from DB to prevent NoneType crash in sub-agent inference
        if not model:
            chat_meta = db.get_chat(chat_id)
            model = chat_meta.get('last_model') if chat_meta else None
        if not model:
            last_asst = db.get_last_assistant_message(chat_id)
            model = last_asst.get('model') if last_asst else 'gpt-4o'
        # Strip mode flags — DB already has the correct state from the original turn.
        # Syncing from the frontend would corrupt mid-execution state (R2 fix).
        RESUME_STRIP_KEYS = {'model', 'researchMode', 'userPreferences', 'fileSystemMode', 'browsingMode'}
        extra_body = {k: v for k, v in resume_body.items() if k not in RESUME_STRIP_KEYS}
        
        def generate_stream():
            import asyncio
            async def run_gen():
                async for chunk in handler.initiate_chat(
                    user_message=last_user_msg,
                    model=model,
                    **extra_body
                ):
                    yield chunk

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            gen = run_gen()
            try:
                while True:
                    try:
                        chunk = loop.run_until_complete(gen.__anext__())
                        yield chunk
                    except StopAsyncIteration:
                        break
            finally:
                loop.close()

        response = Response(generate_stream(), mimetype='text/event-stream')
        # The claim is held until the stream ends or the client disconnects.
        response.call_on_close(lambda: turns.release_turn_claim(chat_id))
        return response
    except Exception as e:
        turns.release_turn_claim(chat_id)
        logger.error(f"Error in resume_chat route: {e}", exc_info=True)
        log_event("chat_resume_error", {"chat_id": chat_id, "error": error_detail(e)})
        return jsonify({"error": "Could not retry the answer. Try again."}), 500

@chat_bp.route('/<chat_id>/stop', methods=['POST'])
def stop_chat(chat_id):
    """
    Interrupts a running turn and rolls back. Answers once the turn's worker has exited:
    `stopped` is false when it was still alive after TASK_STOP_WAIT_SECONDS (the rollback still ran).
    """
    denied = require_chat_owner(chat_id)
    if denied:
        return denied
    try:
        # Wait first, so the rollback follows the worker's last write.
        stopped = task_manager.stop_task_and_wait(chat_id)
        if not stopped:
            log_event("chat_stop_timeout", {"chat_id": chat_id})
        db.rollback_to_last_user_message(chat_id)
        from backend.database import response_cache
        response_cache.clear_sse_chunks(chat_id)

        # Reset research state if it was ongoing — prevents zombie 'ongoing' state
        chat_meta = db.get_chat(chat_id)
        if chat_meta and chat_meta.get('research_state') == 'ongoing':
            db.update_chat(chat_id, research_state='none')

        # Cleanup any pending clarification callbacks
        from backend.tools.callbacks import callback_registry
        callback_registry.cleanup_chat(chat_id)

        # Suppress resume banner — user explicitly stopped
        db.update_chat(chat_id, resume_suppressed=1)
        
        log_event("chat_stopped", {"chat_id": chat_id})
        return jsonify({"status": "success", "stopped": stopped})
    except Exception as e:
        logger.error(f"Error stopping chat {chat_id}: {e}", exc_info=True)
        log_event("chat_stop_error", {"chat_id": chat_id, "error": error_detail(e)})
        return jsonify({"error": "Could not stop the answer. Try again."}), 500


@chat_bp.route('/<chat_id>/messages/<int:message_id>', methods=['PUT', 'PATCH'])
def edit_message_endpoint(chat_id, message_id):
    denied = require_chat_owner(chat_id)
    if denied:
        return denied
    data, err = read_json_object()
    if err:
        return err
    content = data.get('content')
    if not isinstance(content, str) or not content.strip():
        return jsonify({"error": "Content required"}), 400

    existing = db.get_message(chat_id, message_id)
    if existing is None:
        log_event("chat_edit_message_not_found", {"chat_id": chat_id, "message_id": message_id})
        return jsonify({"error": "Message not found"}), 404
    if existing.get("role") != "user":
        log_event("chat_edit_rejected_role", {"chat_id": chat_id, "message_id": message_id})
        return jsonify({"error": "Only user messages can be edited"}), 403

    # The editor only holds the text: keep the message's images and attachment note.
    merged = merge_edited_user_content(existing.get("content") or "", content)
    success = db.edit_message(chat_id, message_id, merged)
    if not success:
        log_event("chat_edit_message_not_found", {"chat_id": chat_id, "message_id": message_id})
        return jsonify({"error": "Message not found"}), 404
    return jsonify({"success": True})

@chat_bp.route('/<chat_id>/messages/<int:message_id>', methods=['DELETE'])
def delete_message_endpoint(chat_id, message_id):
    """Delete a message and subsequent history (cascading)."""
    denied = require_chat_owner(chat_id)
    if denied:
        return denied
    db.delete_message(chat_id, message_id)
    return jsonify({"success": True})

@chat_bp.route('/<chat_id>/discard', methods=['POST'])
def discard_research_endpoint(chat_id):
    """
    Killed a research task, wipe state files, clean RAG,
    and reset chat to just the first user message.
    """
    denied = require_chat_owner(chat_id)
    if denied:
        return denied
    from backend import config
    import os
    import re
    # 1. Stop the task if running
    task_manager.stop_task(chat_id)

    # 2. Cleanup state files
    safe_chat_id = re.sub(r'[^a-zA-Z0-9_\-]', '', str(chat_id))
    state_path = os.path.join(config.DATA_DIR, "tasks", f"{safe_chat_id}_state.json")
    task_path = os.path.join(config.DATA_DIR, "tasks", f"{chat_id}.json")
    if os.path.exists(state_path): os.remove(state_path)
    if os.path.exists(task_path): os.remove(task_path)

    # 3. Cleanup RAG and active cache
    from backend.rag import RAGProvider
    from backend.models import get_embedding_model
    from backend.database import response_cache
    
    response_cache.clear_sse_chunks(chat_id)

    # 4. Cleanup file_systems: Delete .md files and DB rows
    FILE_SYSTEMS_DIR = os.path.join(config.DATA_DIR, "file_systems")
    file_systems = db.get_chat_file_systems(chat_id=chat_id)
    for file_system in file_systems:
        if file_system.get('filename'):
            file_path = os.path.join(FILE_SYSTEMS_DIR, file_system['filename'])
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except OSError:
                pass
        db.delete_file_system_meta(file_system_id=file_system['id'], chat_id=chat_id)

    # 5. Cleanup messages: Wipe and allow restart
    db.clear_messages(chat_id=chat_id)

    # 6. Reset research state — clear_messages doesn't touch chat-level flags
    db.update_chat(chat_id, research_state='none', research_mode=0)

    return jsonify({"success": True})

# Removed obsolete sse_chunks endpoint.
# Active fragments are delivered via the woven history endpoint.

# History is delivered via the woven history endpoint.


# =============================================================================
# PERSONA MANAGEMENT (Route Prefix: /api)
# =============================================================================

personas_bp = Blueprint('personas', __name__)


@personas_bp.route('/personas', methods=['GET'])
def get_personas():
    personas = db.get_all_personas(current_user_id())
    return jsonify({"success": True, "personas": personas})


@personas_bp.route('/personas', methods=['POST'])
def create_persona():
    data, err = read_json_object(extra={"success": False})
    if err:
        return err
    name = data.get('name')
    content = data.get('content')
    is_default = data.get('is_default', 0)
    research_mode = data.get('research_mode', 0)
    file_system_mode = data.get('file_system_mode', 0)
    browsing_mode = data.get('browsing_mode', 0)

    if not name or not content:
        return jsonify({"success": False, "error": "Name and content are required"}), 400
    if db.persona_name_exists(name, current_user_id()):
        return jsonify({"success": False, "error": f"A persona named '{name}' already exists"}), 400

    persona = db.create_persona(name, content, current_user_id(), is_default, research_mode, file_system_mode, browsing_mode)
    return jsonify({"success": True, "persona": persona}), 201


@personas_bp.route('/personas/<persona_id>', methods=['PUT'])
def update_persona(persona_id):
    data, err = read_json_object(extra={"success": False})
    if err:
        return err
    name = data.get('name')
    content = data.get('content')
    is_default = data.get('is_default', 0)
    research_mode = data.get('research_mode', 0)
    file_system_mode = data.get('file_system_mode', 0)
    browsing_mode = data.get('browsing_mode', 0)

    if not name or not content:
        return jsonify({"success": False, "error": "Name and content are required"}), 400
    if db.persona_name_exists(name, current_user_id(), exclude_id=persona_id):
        return jsonify({"success": False, "error": f"A persona named '{name}' already exists"}), 400

    success = db.update_persona(persona_id, name, content, current_user_id(), is_default, research_mode, file_system_mode, browsing_mode)
    if not success:
        return jsonify({"success": False, "error": "Persona not found"}), 404

    persona = db.get_persona(persona_id, current_user_id())
    return jsonify({"success": True, "persona": persona})


@personas_bp.route('/personas/<persona_id>', methods=['DELETE'])
def delete_persona(persona_id):
    success = db.delete_persona(persona_id, current_user_id())
    if not success:
        return jsonify({"success": False, "error": "Persona not found"}), 404
    return jsonify({"success": True})


# =============================================================================
# SKILLS STORE MANAGEMENT (Route Prefix: /api)
# =============================================================================

skills_bp = Blueprint('skills', __name__)


@skills_bp.route('/skills', methods=['GET'])
def get_skills():
    skills = db.get_all_skills(current_user_id())
    return jsonify({"success": True, "skills": skills})


@skills_bp.route('/skills', methods=['POST'])
def create_skill():
    data, err = read_json_object(extra={"success": False})
    if err:
        return err
    name = data.get('name')
    description = data.get('description')
    instructions = data.get('instructions')

    if not name or not description or not instructions:
        return jsonify({"success": False, "error": "Name, description, and instructions are required"}), 400

    # Clean the name to make sure it's alphanumeric/dashes to prevent parsing issues
    name = name.strip().replace(" ", "-").replace("/", "")
    if not name:
        return jsonify({"success": False, "error": "Invalid skill name"}), 400

    import uuid
    import sqlite3
    skill_id = str(uuid.uuid4())
    try:
        db.add_skill(skill_id, name, description, instructions, current_user_id())
        skill = db.get_skill(skill_id, current_user_id())
        return jsonify({"success": True, "skill": skill}), 201
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "error": f"A skill with the name '{name}' already exists"}), 400


@skills_bp.route('/skills/<skill_id>', methods=['PUT'])
def update_skill(skill_id):
    data, err = read_json_object(extra={"success": False})
    if err:
        return err
    name = data.get('name')
    description = data.get('description')
    instructions = data.get('instructions')

    if not name or not description or not instructions:
        return jsonify({"success": False, "error": "Name, description, and instructions are required"}), 400

    name = name.strip().replace(" ", "-").replace("/", "")
    if not name:
        return jsonify({"success": False, "error": "Invalid skill name"}), 400

    # Verify skill exists
    existing = db.get_skill(skill_id, current_user_id())
    if not existing:
        return jsonify({"success": False, "error": "Skill not found"}), 404

    import sqlite3
    try:
        if not db.add_skill(skill_id, name, description, instructions, current_user_id()):
            return jsonify({"success": False, "error": "Skill not found"}), 404
        skill = db.get_skill(skill_id, current_user_id())
        return jsonify({"success": True, "skill": skill})
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "error": f"A skill with the name '{name}' already exists"}), 400


@skills_bp.route('/skills/<skill_id>', methods=['DELETE'])
def delete_skill(skill_id):
    if not db.delete_skill(skill_id, current_user_id()):
        return jsonify({"success": False, "error": "Skill not found"}), 404
    return jsonify({"success": True})

