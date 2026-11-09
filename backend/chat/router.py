from flask import Blueprint, request, Response, jsonify
import logging
import json
import time
from typing import Dict, Any

from backend.chat.handler import ChatHandler
from backend.database import db
from backend.logging import log_event
from backend.task_manager import task_manager
from backend.file_system import FileSystemChannelManager
from backend.files.router import get_file_manager
from backend import config
import os

logger = logging.getLogger(__name__)

chat_bp = Blueprint('chat', __name__)
openai_bp = Blueprint('openai', __name__)

FILE_SYSTEMS_DIR = os.path.join(config.DATA_DIR, "file_systems")

# =============================================================================
# GLOBAL CHAT MANAGEMENT (Route Prefix: /api/chats)
# =============================================================================

@chat_bp.route('', methods=['GET'])
@chat_bp.route('/', methods=['GET'])
def list_chats():
    logger.debug("[API] GET /api/chats - listing all chats")
    chats = db.get_all_chats()
    return jsonify(chats)

@chat_bp.route('/workspaces', methods=['GET'])
def list_workspaces():
    workspaces = db.get_all_workspaces()
    return jsonify(workspaces)

@chat_bp.route('/workspaces', methods=['POST'])
def create_workspace():
    data = request.json
    name = data.get('name')
    if not name:
        return jsonify({"error": "Missing workspace name"}), 400
    workspace = db.create_workspace(name)
    return jsonify(workspace)

@chat_bp.route('/workspaces/<workspace_id>', methods=['PATCH'])
def rename_workspace(workspace_id):
    data = request.json or {}
    new_name = data.get('name')
    has_icon = 'icon' in data
    if not new_name and not has_icon:
        return jsonify({"error": "Missing workspace update fields (name or icon)"}), 400
    if has_icon:
        db.update_workspace_icon(workspace_id, data.get('icon'))
    if new_name:
        db.rename_workspace(workspace_id, new_name)
    return jsonify({"success": True})

@chat_bp.route('/workspaces/<workspace_id>', methods=['DELETE'])
def delete_workspace(workspace_id):
    db.delete_workspace(workspace_id)
    return jsonify({"success": True})

@chat_bp.route('', methods=['DELETE'])
@chat_bp.route('/', methods=['DELETE'])
def clear_all_chats():
    all_chats = db.get_all_chats()
    db.delete_all_chats()
    return jsonify({"success": True})

@chat_bp.route('/save', methods=['POST'])
def save_chat_endpoint():
    data = request.json
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

    file_systems = db.get_chat_file_systems(chat_id)
    if len(file_systems) > 0:
        file_system_mode = True

    existing_chat = db.get_chat(chat_id)
    if existing_chat:
        return jsonify({"error": "Cannot overwrite existing chat history via save endpoint. Use Action-Based APIs."}), 403

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
        frequency_penalty=data.get('frequency_penalty', 0.0)
    )
    db.update_chat(chat_id=chat_id, thinking_profile=data.get('thinking_profile', 'general'))

    return jsonify({"success": True})

@chat_bp.route('/<chat_id>', methods=['PATCH'])
def patch_chat_endpoint(chat_id):
    data = request.json
    new_title = data.get('title')
    last_model = data.get('last_model')
    vision_model = data.get('vision_model')
    max_tokens = data.get('max_tokens')
    thinking_budget_tokens = data.get('thinking_budget_tokens')
    workspace_id = data.get('workspace_id') or data.get('folder')
    enable_thinking = data.get('enable_thinking')
    thinking_profile = data.get('thinking_profile')

    existing_chat = db.get_chat(chat_id)
    if not existing_chat:
        db.ensure_chat_exists(chat_id)
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

    # 3. Database Cleanup
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
    try:
        handler = ChatHandler(chat_id)
        result = handler.get_history()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error fetching history for chat {chat_id}: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@openai_bp.route('/completions', methods=['POST'])
def chat_completions():
    """
    Primary OpenAI-compatible endpoint for chat streaming.
    Endpoint: POST /v1/chat/completions
    """
    data = request.json
    chat_id = data.get('chatId')
    user_message_raw = data.get('messages')[-1] if data.get('messages') else None
    
    # Extract OpenAI-standard fields
    model = data.get('model')  # No hardcoded fallback to gpt-4o
    files = data.get('uploadedFiles') # Support frontend field name
    
    if not chat_id:
        return jsonify({"error": "chatId is required"}), 400

    log_event("api_chat_completions", {"chat_id": chat_id, "model": model})

    try:
        # 1. Ensure chat exists and metadata is settled
        db.ensure_chat_exists(chat_id)
        
        # 2. Persist User Message if it's a new turn
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
                        yield f"data: {json.dumps({'error': str(e)})}\n\n"
                        break
            finally:
                loop.close()

        return Response(generate_stream(), mimetype='text/event-stream')

    except Exception as e:
        logger.error(f"Error in chat_completions route: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@chat_bp.route('/<chat_id>/stream', methods=['GET'])
def reattach_stream(chat_id):
    """
    Reattach to an in-progress generation stream.
    Returns 204 if no task is currently running (task already finished).
    """
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
    Resumes an interrupted chat turn.
    """
    try:
        handler = ChatHandler(chat_id)
        
        # Get last user msg
        messages = db.get_messages(chat_id)
        last_user_msg = next((m for m in reversed(messages) if m['role'] == 'user'), None)
                
        if not last_user_msg:
            return jsonify({"error": "No user message found to resume from."}), 400

        model = request.json.get('model')
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
        extra_body = {k: v for k, v in request.json.items() if k not in RESUME_STRIP_KEYS}
        
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

        return Response(generate_stream(), mimetype='text/event-stream')
    except Exception as e:
        logger.error(f"Error in resume_chat route: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@chat_bp.route('/<chat_id>/stop', methods=['POST'])
def stop_chat(chat_id):
    """
    Interrupts a running turn and rolls back.
    """
    try:
        task_manager.stop_task(chat_id)
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
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error stopping chat {chat_id}: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@chat_bp.route('/<chat_id>/messages/<int:message_id>', methods=['PUT', 'PATCH'])
def edit_message_endpoint(chat_id, message_id):
    data = request.json
    content = data.get('content')
    if not isinstance(content, str) or not content.strip():
        return jsonify({"error": "Content required"}), 400

    success = db.edit_message(chat_id, message_id, content)
    if not success:
        log_event("chat_edit_message_not_found", {"chat_id": chat_id, "message_id": message_id})
        return jsonify({"error": "Message not found"}), 404
    return jsonify({"success": True})

@chat_bp.route('/<chat_id>/messages/<int:message_id>', methods=['DELETE'])
def delete_message_endpoint(chat_id, message_id):
    """Delete a message and subsequent history (cascading)."""
    db.delete_message(chat_id, message_id)
    return jsonify({"success": True})

@chat_bp.route('/<chat_id>/discard', methods=['POST'])
def discard_research_endpoint(chat_id):
    """
    Killed a research task, wipe state files, clean RAG,
    and reset chat to just the first user message.
    """
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
    personas = db.get_all_personas()
    return jsonify({"success": True, "personas": personas})


@personas_bp.route('/personas', methods=['POST'])
def create_persona():
    data = request.json
    name = data.get('name')
    content = data.get('content')
    is_default = data.get('is_default', 0)
    research_mode = data.get('research_mode', 0)
    file_system_mode = data.get('file_system_mode', 0)
    browsing_mode = data.get('browsing_mode', 0)

    if not name or not content:
        return jsonify({"success": False, "error": "Name and content are required"}), 400

    persona = db.create_persona(name, content, is_default, research_mode, file_system_mode, browsing_mode)
    return jsonify({"success": True, "persona": persona}), 201


@personas_bp.route('/personas/<persona_id>', methods=['PUT'])
def update_persona(persona_id):
    data = request.json
    name = data.get('name')
    content = data.get('content')
    is_default = data.get('is_default', 0)
    research_mode = data.get('research_mode', 0)
    file_system_mode = data.get('file_system_mode', 0)
    browsing_mode = data.get('browsing_mode', 0)

    if not name or not content:
        return jsonify({"success": False, "error": "Name and content are required"}), 400

    success = db.update_persona(persona_id, name, content, is_default, research_mode, file_system_mode, browsing_mode)
    if not success:
        return jsonify({"success": False, "error": "Persona not found"}), 404

    persona = db.get_persona(persona_id)
    return jsonify({"success": True, "persona": persona})


@personas_bp.route('/personas/<persona_id>', methods=['DELETE'])
def delete_persona(persona_id):
    success = db.delete_persona(persona_id)
    if not success:
        return jsonify({"success": False, "error": "Persona not found"}), 404
    return jsonify({"success": True})


# =============================================================================
# SKILLS STORE MANAGEMENT (Route Prefix: /api)
# =============================================================================

skills_bp = Blueprint('skills', __name__)


@skills_bp.route('/skills', methods=['GET'])
def get_skills():
    skills = db.get_all_skills()
    return jsonify({"success": True, "skills": skills})


@skills_bp.route('/skills', methods=['POST'])
def create_skill():
    data = request.json
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
        db.add_skill(skill_id, name, description, instructions)
        skill = db.get_skill(skill_id)
        return jsonify({"success": True, "skill": skill}), 201
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "error": f"A skill with the name '{name}' already exists"}), 400


@skills_bp.route('/skills/<skill_id>', methods=['PUT'])
def update_skill(skill_id):
    data = request.json
    name = data.get('name')
    description = data.get('description')
    instructions = data.get('instructions')

    if not name or not description or not instructions:
        return jsonify({"success": False, "error": "Name, description, and instructions are required"}), 400

    name = name.strip().replace(" ", "-").replace("/", "")
    if not name:
        return jsonify({"success": False, "error": "Invalid skill name"}), 400

    # Verify skill exists
    existing = db.get_skill(skill_id)
    if not existing:
        return jsonify({"success": False, "error": "Skill not found"}), 404

    import sqlite3
    try:
        db.add_skill(skill_id, name, description, instructions)
        skill = db.get_skill(skill_id)
        return jsonify({"success": True, "skill": skill})
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "error": f"A skill with the name '{name}' already exists"}), 400


@skills_bp.route('/skills/<skill_id>', methods=['DELETE'])
def delete_skill(skill_id):
    existing = db.get_skill(skill_id)
    if not existing:
        return jsonify({"success": False, "error": "Skill not found"}), 404
    db.delete_skill(skill_id)
    return jsonify({"success": True})

