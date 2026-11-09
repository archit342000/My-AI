from flask import Blueprint, request, jsonify, Response
import logging
import json
import os
import mimetypes
from backend.auth.ownership import claim_chat, owns_chat, reject_foreign_chat, require_chat_owner, require_workspace_owner
from backend.database import db
from backend.utils import read_json_object
from backend import config
from backend.file_system import (
    get_file_system_versions,
    get_fs_file_version,
    restore_fs_file_version,
    get_fs_file_diff,
    FileSystemChannelManager
)

logger = logging.getLogger(__name__)

file_system_bp = Blueprint('file_system', __name__)

FILE_SYSTEMS_DIR = os.path.join(config.DATA_DIR, "file_systems")

@file_system_bp.before_request
def normalize_workspace_id():
    """
    If workspace_id is "default" and chat_id is present, resolve it to the chat's actual workspace ID.
    This handles cases where the client sends "default" as a workspace_id fallback.
    """
    chat_id = request.args.get('chat_id')
    workspace_id = request.args.get('workspace_id')
    
    # Check request JSON body
    data = None
    if request.is_json:
        try:
            data = request.get_json(silent=True)
            if data:
                if not chat_id:
                    chat_id = data.get('chat_id')
                if not workspace_id:
                    workspace_id = data.get('workspace_id')
        except Exception:
            pass

    if workspace_id == "default" and chat_id:
        from backend.file_system.utils import get_workspace_for_chat
        resolved_ws_id = get_workspace_for_chat(chat_id)
        if resolved_ws_id:
            # Update request query arguments
            from werkzeug.datastructures import MultiDict
            args = MultiDict(request.args)
            if 'workspace_id' in args:
                args['workspace_id'] = resolved_ws_id
            request.args = args
            
            # Update request JSON dictionary
            if isinstance(data, dict) and 'workspace_id' in data:
                data['workspace_id'] = resolved_ws_id

# Routes that may name a chat that does not exist yet: they create it with `claim_chat`.
_CHAT_CREATING_ENDPOINTS = {"file_system.create_fs_file_route", "file_system.create_directory_route"}
# Read routes that may name a chat that does not exist yet and just return an empty result (the UI lists a new chat's
# artifacts before the chat row exists); another user's existing chat is still 404.
_MISSING_CHAT_OK_ENDPOINTS = _CHAT_CREATING_ENDPOINTS | {"file_system.list_file_systems_endpoint"}


def _request_ids():
    """
    Every chat_id and workspace_id the request carries, from the query string, the JSON body and the URL.

    Routes differ in which source they read (some prefer the query, some the body), so all of them are collected and
    every one must be owned. Returns `(chat_ids, workspace_ids)` as lists of non-empty strings, or None when a value
    is not a string.
    """
    chat_ids, workspace_ids = [], []
    sources = [(request.args.getlist('chat_id'), chat_ids), (request.args.getlist('workspace_id'), workspace_ids)]
    body = request.get_json(silent=True) if request.is_json else None
    if isinstance(body, dict):
        sources += [([body.get('chat_id')], chat_ids), ([body.get('workspace_id')], workspace_ids)]
    sources.append(([(request.view_args or {}).get('chat_id')], chat_ids))
    for values, target in sources:
        for value in values:
            if value in (None, ""):
                continue
            if not isinstance(value, str):
                return None
            target.append(value)
    return chat_ids, workspace_ids


@file_system_bp.before_request
def require_fs_owner():
    """
    Owner check for every file-system route, run after `normalize_workspace_id` so it sees the resolved workspace.

    Each chat and workspace the request names must belong to the current user, otherwise 404 (nothing is read or
    written). A chat that does not exist yet passes only on the two creating routes (which then `claim_chat`) and the list route. The
    "default" workspace sentinel (a chat with no workspace) passes only next to a chat that passed its own check above (owned, or
    on the create and list routes not yet existing: nothing foreign is read or written, "default" meaning "no workspace"). No ids at all passes:
    the route's own "required" check answers.
    """
    ids = _request_ids()
    if ids is None:
        return jsonify({"error": "Invalid chat_id or workspace_id"}), 400
    chat_ids, workspace_ids = ids
    missing_ok = request.endpoint in _MISSING_CHAT_OK_ENDPOINTS
    for chat_id in chat_ids:
        denied = reject_foreign_chat(chat_id) if missing_ok else require_chat_owner(chat_id)
        if denied:
            return denied
    for workspace_id in workspace_ids:
        if workspace_id == "default" and chat_ids:
            continue  # "no workspace": the chat check above governs
        denied = require_workspace_owner(workspace_id)
        if denied:
            return denied
    return None


def _fs_meta_or_404(file_system_id, chat_id, workspace_id=None):
    """
    Look up a file system's metadata under the caller's chat or workspace.

    Returns `(meta, None)`, or `(None, response)` with a 404 when the id is unknown under that chat or workspace
    (which is also what another user's file system looks like). A `disk:` id returns `(None, None)`: it has no row.
    """
    if file_system_id.startswith("disk:"):
        return None, None  # a file that exists only on disk has no row; the owner check already ran and the route answers as before
    # Workspace artifacts are stored without a chat_id: look under the chat's workspace too, as the manager does.
    if not workspace_id and chat_id:
        from backend.file_system.utils import get_workspace_for_chat
        workspace_id = get_workspace_for_chat(chat_id)
    meta = db.get_file_system_meta(file_system_id=file_system_id, chat_id=chat_id, workspace_id=workspace_id)
    if not meta:
        return None, (jsonify({"success": False, "error": "FileSystem not found"}), 404)
    return meta, None


@file_system_bp.route('', methods=['POST'])
@file_system_bp.route('/', methods=['POST'])
async def create_fs_file_route():
    """Create a new file_system."""
    from backend.file_system import create_fs_file
    data, err = read_json_object(required=False)
    if err:
        return err
    chat_id = data.get('chat_id')
    workspace_id = data.get('workspace_id')
    title = data.get('title', 'Untitled FileSystem')
    folder = data.get('folder', '')
    content = data.get('content')
    file_system_type = data.get('file_system_type', 'custom')
    language = data.get('language', 'markdown')

    if (not chat_id and not workspace_id) or content is None:
        return jsonify({"error": "Missing chat_id/workspace_id or content"}), 400

    # Create the chat for the caller, or refuse (404) another user's chat or workspace, before any file is written.
    if workspace_id and workspace_id != "default":  # "default" means "no workspace" (see utils.resolve_owner_and_physical_path)
        denied = require_workspace_owner(workspace_id)
        if denied:
            return denied
    if chat_id:
        denied = claim_chat(chat_id)
        if denied:
            return denied

    from backend.file_system.utils import sanitize_path
    path_parts = []
    if folder:
        path_parts.append(folder)
    path_parts.append(title)
    computed_path = sanitize_path('/'.join(path_parts))

    try:
        result = await create_fs_file(
            chat_id=chat_id,
            path=computed_path,
            content=content,
            file_system_type=file_system_type,
            language=language,
            workspace_id=workspace_id
        )
        if not result.get("success"):
            return jsonify({"error": result.get("error", "Unknown error")}), 400
            
        return jsonify({
            "success": True,
            "id": result["file_system_id"],
            "title": title,
            "filename": result["path"]
        })
    except Exception as e:
        logger.error(f"[CREATE_FILE_SYSTEM_ROUTE] FAILED chat_id={chat_id!r} path={computed_path!r}: {type(e).__name__}: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@file_system_bp.route('/directory', methods=['POST'])
async def create_directory_route():
    """Create a new empty directory."""
    from backend.file_system.manager import create_directory_tool
    data, err = read_json_object(required=False)
    if err:
        return err
    chat_id = data.get('chat_id')
    workspace_id = data.get('workspace_id')
    path = data.get('path')

    if (not chat_id and not workspace_id) or not path:
        return jsonify({"error": "Missing chat_id/workspace_id or path"}), 400

    # The hook lets a new chat through; create it for the caller (or refuse one another user created meanwhile).
    if chat_id:
        denied = claim_chat(chat_id)
        if denied:
            return denied

    try:
        result = await create_directory_tool(chat_id=chat_id, path=path, workspace_id=workspace_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@file_system_bp.route('/directory', methods=['DELETE'])
async def delete_directory_route():
    """Delete an empty directory."""
    from backend.file_system.manager import delete_directory_tool
    chat_id = request.args.get('chat_id')
    workspace_id = request.args.get('workspace_id')
    path = request.args.get('path')

    if (not chat_id and not workspace_id) or not path:
        return jsonify({"error": "Missing chat_id/workspace_id or path"}), 400

    try:
        result = await delete_directory_tool(chat_id=chat_id, path=path, workspace_id=workspace_id)
        if not result.get("success"):
            return jsonify({"error": result.get("error", "Unknown error")}), 400
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _infer_language(filename: str, current_lang: str) -> str:
    """Helper to lazily infer language from filename if it's incorrectly set to markdown."""
    if (not current_lang or current_lang == "markdown") and "." in filename:
        ext = filename.split(".")[-1].lower()
        if ext not in ["md", "markdown"]:
            return ext
    return current_lang or "markdown"

@file_system_bp.route('', methods=['GET'])
async def list_file_systems_endpoint():
    """List all file_systems, optionally filtered by chat_id or workspace_id."""
    chat_id = request.args.get('chat_id')
    workspace_id = request.args.get('workspace_id')
    from backend.file_system.manager import get_fs_file_content
    from backend.file_system.utils import get_workspace_for_chat

    # A chat that does not exist yet (the UI lists a new chat's artifacts) has nothing to list, and a leftover directory
    # of a deleted chat must not be readable by naming its id. The hook already refused another user's chat.
    if chat_id and not owns_chat(chat_id):
        chat_id = None  # never read the chat's rows or directory
        if not workspace_id or workspace_id == "default":
            return jsonify({"success": True, "file_systems": []})

    file_systems_with_content = []
    
    if chat_id:
        file_systems = db.get_chat_file_systems(chat_id=chat_id)
        chat_workspace_id = get_workspace_for_chat(chat_id)
        if chat_workspace_id:
            ws_file_systems = db.get_owner_file_systems(workspace_id=chat_workspace_id)
            for wc in ws_file_systems:
                if not wc['filename'].startswith("workspace/"):
                    wc['filename'] = "workspace/" + wc['filename']
            file_systems.extend(ws_file_systems)
    elif workspace_id:
        file_systems = db.get_owner_file_systems(workspace_id=workspace_id)
        for wc in file_systems:
            if not wc['filename'].startswith("workspace/"):
                wc['filename'] = "workspace/" + wc['filename']
    else:
        return jsonify({"error": "chat_id or workspace_id is required"}), 400

    for file_system in file_systems:
        # Resolve actual owner for content fetching
        actual_chat_id = file_system.get('chat_id')
        actual_ws_id = file_system.get('workspace_id')
        
        content = await get_fs_file_content(file_system['id'], chat_id=actual_chat_id, workspace_id=actual_ws_id)
        file_system_copy = dict(file_system)
        file_system_copy['content'] = content or ""
        
        # Lazy language inference for existing files
        stored_lang = file_system.get('language', 'markdown')
        inferred_lang = _infer_language(file_system['filename'], stored_lang)
        file_system_copy['language'] = inferred_lang
        
        # If we inferred a better language, update the DB metadata lazily
        if inferred_lang != stored_lang:
             try:
                 db.save_file_system_meta(
                     file_system_id=file_system['id'],
                     chat_id=actual_chat_id,
                     workspace_id=actual_ws_id,
                     language=inferred_lang
                 )
             except Exception as e:
                 logger.warning(f"Failed to lazy-update language for {file_system['id']}: {e}")

        file_systems_with_content.append(file_system_copy)
        
    try:
        from backend.file_system.manager import is_binary_file
        from backend.file_system.utils import FILE_SYSTEMS_DIR, WORKSPACES_DIR, sanitize_filename
        
        def scan_physical_items(current_path, rel_path=""):
            items = []
            if not os.path.exists(current_path): return items
            
            if os.path.basename(current_path) == '.git' or os.path.basename(current_path).startswith('.git'):
                return items
            
            try:
                entries = os.listdir(current_path)
            except Exception:
                return items
                
            for item in entries:
                if item == '.git' or item.startswith('.git/'):
                    continue
                full_item_path = os.path.join(current_path, item)
                new_rel = f"{rel_path}/{item}" if rel_path else item
                
                if os.path.isdir(full_item_path):
                    items.append({
                        "id": f"disk:{new_rel}",
                        "type": "directory",
                        "filename": new_rel,
                        "title": item
                    })
                    items.extend(scan_physical_items(full_item_path, new_rel))
                elif os.path.isfile(full_item_path):
                    mtime = os.path.getmtime(full_item_path)
                    size = os.path.getsize(full_item_path)
                    ext = os.path.splitext(item)[1].lower()
                    lang = ext.lstrip('.') if ext else 'markdown'
                    
                    items.append({
                        "id": f"disk:{new_rel}",
                        "filename": new_rel,
                        "title": item,
                        "type": "file",
                        "timestamp": mtime,
                        "file_size": size,
                        "language": lang
                    })
            return items
            
        added_filenames = {item['filename'] for item in file_systems_with_content}
            
        if chat_id:
            base_chat_dir = os.path.join(FILE_SYSTEMS_DIR, sanitize_filename(chat_id))
            chat_physical = scan_physical_items(base_chat_dir)
            for item in chat_physical:
                if item['filename'] not in added_filenames:
                    if item.get('type') == 'file':
                        filepath = os.path.join(base_chat_dir, item['filename'])
                        if is_binary_file(filepath):
                            item['content'] = "[Binary File] This file contains binary content and cannot be displayed in the text editor."
                        else:
                            try:
                                with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                                    item['content'] = f.read(5000)
                            except Exception:
                                item['content'] = ""
                    file_systems_with_content.append(item)
                    added_filenames.add(item['filename'])
            
            chat_workspace_id = get_workspace_for_chat(chat_id)
            if chat_workspace_id:
                base_ws_dir = os.path.join(WORKSPACES_DIR, sanitize_filename(chat_workspace_id))
                ws_physical = scan_physical_items(base_ws_dir)
                for item in ws_physical:
                    old_rel = item['filename']
                    item['filename'] = "workspace/" + old_rel
                    if item.get('id'):
                        item['id'] = "disk:workspace/" + old_rel
                        
                    if item['filename'] not in added_filenames:
                        if item.get('type') == 'file':
                            filepath = os.path.join(base_ws_dir, old_rel)
                            if is_binary_file(filepath):
                                item['content'] = "[Binary File] This file contains binary content and cannot be displayed in the text editor."
                            else:
                                try:
                                    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                                        item['content'] = f.read(5000)
                                except Exception:
                                    item['content'] = ""
                        file_systems_with_content.append(item)
                        added_filenames.add(item['filename'])
                
                if not any(c.get('type') == 'directory' and c.get('filename') == 'workspace' for c in file_systems_with_content):
                     file_systems_with_content.append({"type": "directory", "filename": "workspace", "title": "workspace"})
        elif workspace_id:
            base_ws_dir = os.path.join(WORKSPACES_DIR, sanitize_filename(workspace_id))
            ws_physical = scan_physical_items(base_ws_dir)
            for item in ws_physical:
                old_rel = item['filename']
                item['filename'] = "workspace/" + old_rel
                if item.get('id'):
                    item['id'] = "disk:workspace/" + old_rel
                    
                if item['filename'] not in added_filenames:
                    if item.get('type') == 'file':
                        filepath = os.path.join(base_ws_dir, old_rel)
                        if is_binary_file(filepath):
                            item['content'] = "[Binary File] This file contains binary content and cannot be displayed in the text editor."
                        else:
                            try:
                                with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                                    item['content'] = f.read(5000)
                            except Exception:
                                item['content'] = ""
                    file_systems_with_content.append(item)
                    added_filenames.add(item['filename'])
                    
            if not any(c.get('type') == 'directory' and c.get('filename') == 'workspace' for c in file_systems_with_content):
                 file_systems_with_content.append({"type": "directory", "filename": "workspace", "title": "workspace"})
                 
    except Exception as e:
        logger.error(f"Error scanning physical items for frontend: {e}")

    return jsonify({"success": True, "file_systems": file_systems_with_content})


@file_system_bp.route('/chat/<chat_id>/folders', methods=['GET'])
def get_chat_folders(chat_id):
    """Get unique folders for a chat's file_systems."""
    from backend.file_system.manager import get_unique_folders
    folders = get_unique_folders(chat_id)
    return jsonify({"success": True, "folders": folders})


@file_system_bp.route('/raw', methods=['GET'])
async def get_raw_file_by_name_endpoint():
    """Get raw file_system content by filename."""
    chat_id = request.args.get('chat_id')
    filename = request.args.get('filename')
    workspace_id = request.args.get('workspace_id')
    
    if not chat_id or not filename:
        return jsonify({"error": "chat_id and filename are required"}), 400
        
    from backend.file_system.utils import sanitize_path
    filename = sanitize_path(filename)
    
    file_systems = db.get_chat_file_systems(chat_id=chat_id)
    target_fs = next((fs for fs in file_systems if fs['filename'] == filename), None)
    
    if not target_fs and workspace_id:
        ws_file_systems = db.get_owner_file_systems(workspace_id=workspace_id)
        clean_ws_filename = filename
        if clean_ws_filename.startswith("workspace/"):
            clean_ws_filename = clean_ws_filename[len("workspace/"):]
        target_fs = next((fs for fs in ws_file_systems if fs['filename'] == clean_ws_filename), None)
        
    if not target_fs:
        from backend.file_system.utils import resolve_owner_and_physical_path
        try:
            target_chat_id, target_workspace_id, physical_path = resolve_owner_and_physical_path(chat_id, filename, workspace_id=workspace_id)
            if os.path.exists(physical_path) and os.path.isfile(physical_path):
                with open(physical_path, 'rb') as f:
                    content = f.read()
                mime_type, _ = mimetypes.guess_type(filename)
                if not mime_type:
                    mime_type = 'application/octet-stream'
                return Response(content, mimetype=mime_type)
        except Exception as e:
            logger.error(f"Error fetching raw disk file by name {filename}: {e}")

    if not target_fs:
        return jsonify({"error": "File not found"}), 404
        
    from backend.file_system.manager import get_fs_file_content
    actual_chat_id = target_fs.get('chat_id')
    actual_workspace_id = target_fs.get('workspace_id')
    
    content = await get_fs_file_content(target_fs['id'], chat_id=actual_chat_id, workspace_id=actual_workspace_id)
    if content is None:
        return jsonify({"error": "File content not found"}), 404
        
    mime_type, _ = mimetypes.guess_type(filename)
    if not mime_type:
        mime_type = 'text/plain'
        
    return Response(content, mimetype=mime_type)

@file_system_bp.route('/<path:file_system_id>/raw', methods=['GET'])
async def get_raw_file_by_id_endpoint(file_system_id):
    """Get raw file_system content by ID."""
    chat_id = request.args.get('chat_id')
    workspace_id = request.args.get('workspace_id')
    
    if not chat_id and not workspace_id:
        return jsonify({"error": "chat_id or workspace_id is required"}), 400

    if file_system_id.startswith("disk:"):
        virtual_path = file_system_id[5:]
        from backend.file_system.utils import resolve_owner_and_physical_path
        try:
            target_chat_id, target_workspace_id, physical_path = resolve_owner_and_physical_path(chat_id, virtual_path, workspace_id=workspace_id)
            if os.path.exists(physical_path) and os.path.isfile(physical_path):
                with open(physical_path, 'rb') as f:
                    content = f.read()
                mime_type, _ = mimetypes.guess_type(virtual_path)
                if not mime_type:
                    mime_type = 'application/octet-stream'
                return Response(content, mimetype=mime_type)
        except Exception as e:
            logger.error(f"Error fetching raw disk file {virtual_path}: {e}")
            return jsonify({"error": "FileSystem file not found on disk"}), 404

    if workspace_id:
        file_system = db.get_file_system_meta(file_system_id=file_system_id, workspace_id=workspace_id)
    else:
        file_system = db.get_file_system_meta(file_system_id=file_system_id, chat_id=chat_id)
        
    if not file_system:
        return jsonify({"error": "FileSystem not found"}), 404

    from backend.file_system.manager import get_fs_file_content
    actual_chat_id = file_system.get('chat_id')
    actual_workspace_id = file_system.get('workspace_id')
    
    content = await get_fs_file_content(file_system_id, chat_id=actual_chat_id, workspace_id=actual_workspace_id)
    if content is None:
        return jsonify({"error": "FileSystem file not found on disk"}), 404

    filename = file_system['filename']
    mime_type, _ = mimetypes.guess_type(filename)
    if not mime_type:
        mime_type = 'text/plain'
        
    return Response(content, mimetype=mime_type)

@file_system_bp.route('/<path:file_system_id>', methods=['GET'])
async def get_file_system_endpoint(file_system_id):
    """Get a file_system and its content."""
    chat_id = request.args.get('chat_id')
    workspace_id = request.args.get('workspace_id')
    if not chat_id and not workspace_id:
        return jsonify({"error": "chat_id or workspace_id is required"}), 400

    if file_system_id.startswith("disk:"):
        virtual_path = file_system_id[5:]
        from backend.file_system.utils import resolve_owner_and_physical_path
        try:
            target_chat_id, target_workspace_id, physical_path = resolve_owner_and_physical_path(chat_id, virtual_path, workspace_id=workspace_id)
            if os.path.exists(physical_path) and os.path.isfile(physical_path):
                from backend.file_system.manager import is_binary_file, get_fs_file_content
                content = await get_fs_file_content(file_system_id, chat_id=chat_id, workspace_id=workspace_id)
                ext = os.path.splitext(virtual_path)[1].lower()
                lang = ext.lstrip('.') if ext else 'markdown'
                
                filename = virtual_path
                if target_workspace_id:
                    filename = "workspace/" + filename if not filename.startswith("workspace/") else filename
                
                return jsonify({
                    "success": True,
                    "id": file_system_id,
                    "chat_id": target_chat_id,
                    "workspace_id": target_workspace_id,
                    "title": os.path.basename(virtual_path),
                    "filename": filename,
                    "timestamp": os.path.getmtime(physical_path),
                    "folder": os.path.dirname(virtual_path).replace("workspace/", ""),
                    "tags": [],
                    "file_system_type": "custom",
                    "current_version": 1,
                    "language": lang,
                    "content": content
                })
        except Exception as e:
            logger.error(f"Error fetching disk file {virtual_path}: {e}")
            return jsonify({"error": "FileSystem file not found on disk"}), 404

    if workspace_id:
        file_system = db.get_file_system_meta(file_system_id=file_system_id, workspace_id=workspace_id)
    else:
        # Strictly look in chat context if no workspace_id is provided
        file_system = db.get_file_system_meta(file_system_id=file_system_id, chat_id=chat_id)
    if not file_system:
        return jsonify({"error": "FileSystem not found"}), 404

    from backend.file_system.manager import get_fs_file_content
    actual_chat_id = file_system.get('chat_id')
    actual_workspace_id = file_system.get('workspace_id')
    
    content = await get_fs_file_content(file_system_id, chat_id=actual_chat_id, workspace_id=actual_workspace_id)
    if content is None:
        return jsonify({"error": "FileSystem file not found on disk"}), 404

    filename = file_system['filename']
    if actual_workspace_id:
        filename = "workspace/" + filename

    # Lazy language inference for existing files
    stored_lang = file_system.get('language', 'markdown')
    inferred_lang = _infer_language(file_system['filename'], stored_lang)
    
    # If we inferred a better language, update the DB metadata lazily
    if inferred_lang != stored_lang:
        try:
            db.save_file_system_meta(
                file_system_id=file_system_id,
                chat_id=actual_chat_id,
                workspace_id=actual_workspace_id,
                language=inferred_lang
            )
        except Exception as e:
            logger.warning(f"Failed to lazy-update language for {file_system_id}: {e}")

    return jsonify({
        "success": True,
        "id": file_system_id,
        "chat_id": chat_id,
        "workspace_id": actual_workspace_id,
        "title": file_system['title'],
        "filename": filename,
        "content": content,
        "language": inferred_lang,
        "timestamp": file_system['timestamp'],
        "navigation_history": file_system.get('navigation_history', '[]'),
        "navigation_index": file_system.get('navigation_index', -1)
    })


@file_system_bp.route('/<path:file_system_id>', methods=['PATCH'])
async def update_file_system_endpoint(file_system_id):
    """Update file_system content or metadata (folder, title)."""
    data, err = read_json_object(required=False)
    if err:
        return err
    chat_id = data.get('chat_id') or request.args.get('chat_id')
    workspace_id = request.args.get('workspace_id') or data.get('workspace_id')
    if not chat_id and not workspace_id:
        return jsonify({"success": False, "error": "chat_id or workspace_id is required"}), 400

    if file_system_id.startswith("disk:"):
        virtual_path = file_system_id[5:]
        from backend.file_system.utils import resolve_owner_and_physical_path
        try:
            target_chat_id, target_workspace_id, physical_path = resolve_owner_and_physical_path(chat_id, virtual_path, workspace_id=workspace_id)
            new_content = data.get('content')
            if new_content is not None:
                with open(physical_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
            return jsonify({"success": True, "id": file_system_id})
        except Exception as e:
            logger.error(f"Error updating disk file {virtual_path}: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    if workspace_id:
        file_system = db.get_file_system_meta(file_system_id=file_system_id, workspace_id=workspace_id)
    else:
        # Strictly look in chat context if no workspace_id is provided
        file_system = db.get_file_system_meta(file_system_id=file_system_id, chat_id=chat_id)
    if not file_system:
        return jsonify({"success": False, "error": "FileSystem not found"}), 404

    actual_chat_id = file_system.get('chat_id')
    actual_workspace_id = file_system.get('workspace_id')

    new_path_direct = data.get('new_path')
    new_folder = data.get('folder')
    new_title = data.get('title')
    new_type = data.get('file_system_type')
    new_current_version = data.get('current_version')
    new_nav_history = data.get('navigation_history')
    new_nav_index = data.get('navigation_index')
    
    if any(x is not None for x in [new_path_direct, new_folder, new_title, new_type, new_current_version, new_nav_history, new_nav_index]):
        from backend.file_system.manager import update_file_system_metadata
        from backend.file_system.utils import sanitize_path
        
        current_path = file_system.get('filename')
        if actual_workspace_id:
            current_path = "workspace/" + current_path
            
        if new_path_direct is not None:
            computed_new_path = sanitize_path(new_path_direct)
            # If moving via direct path, we trust the path. No forced workspace/ prefix.
        else:
            target_folder = new_folder if new_folder is not None else file_system.get('folder', '')
            target_title = new_title if new_title is not None else file_system.get('title', os.path.basename(current_path))
            path_parts = []
            if target_folder:
                path_parts.append(target_folder)
            path_parts.append(target_title)
            computed_new_path = sanitize_path('/'.join(path_parts))
            # If just updating title/folder metadata for a workspace file, keep it in workspace
            if actual_workspace_id and not computed_new_path.startswith("workspace/"):
                 computed_new_path = "workspace/" + computed_new_path

        meta_result = update_file_system_metadata(
            chat_id=chat_id,
            current_path=current_path,
            new_path=computed_new_path,
            title=os.path.basename(computed_new_path),
            folder=os.path.dirname(computed_new_path).replace("workspace/", ""),
            file_system_type=new_type or file_system.get('file_system_type', 'custom'),
            current_version=new_current_version if new_current_version is not None else file_system.get('current_version'),
            navigation_history=new_nav_history if new_nav_history is not None else file_system.get('navigation_history'),
            navigation_index=new_nav_index if new_nav_index is not None else file_system.get('navigation_index', -1)
        )
        if not meta_result.get("success"):
            return jsonify(meta_result), 400
        file_system_id = meta_result.get("file_system_id", file_system_id)

    new_content = data.get('content')
    if new_content is not None:
        from backend.file_system.manager import update_fs_file_content
        result = await update_fs_file_content(
            file_system_id=file_system_id, 
            chat_id=actual_chat_id, 
            workspace_id=actual_workspace_id,
            new_content=new_content, 
            author="user",
            file_system_type=data.get('file_system_type')
        )
        return jsonify(result)

    return jsonify({"success": True, "id": file_system_id})


@file_system_bp.route('/<path:file_system_id>', methods=['DELETE'])
async def remove_fs_file_endpoint(file_system_id):
    """Delete a file_system."""
    chat_id = request.args.get('chat_id')
    workspace_id = request.args.get('workspace_id')
    if not chat_id and not workspace_id:
        return jsonify({"error": "chat_id or workspace_id is required"}), 400

    if file_system_id.startswith("disk:"):
        virtual_path = file_system_id[5:]
        from backend.file_system.utils import resolve_owner_and_physical_path
        try:
            target_chat_id, target_workspace_id, physical_path = resolve_owner_and_physical_path(chat_id, virtual_path, workspace_id=workspace_id)
            if os.path.exists(physical_path):
                if os.path.isdir(physical_path):
                    import shutil
                    shutil.rmtree(physical_path)
                else:
                    os.remove(physical_path)
            return jsonify({"success": True, "action": "delete", "file_system_id": file_system_id})
        except Exception as e:
            logger.error(f"Error deleting disk file {virtual_path}: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    if workspace_id:
        file_system = db.get_file_system_meta(file_system_id=file_system_id, workspace_id=workspace_id)
    else:
        # Strictly look in chat context if no workspace_id is provided
        file_system = db.get_file_system_meta(file_system_id=file_system_id, chat_id=chat_id)
    if not file_system:
        return jsonify({"success": False, "error": "FileSystem not found"}), 404

    actual_chat_id = file_system.get('chat_id')
    actual_workspace_id = file_system.get('workspace_id')

    from backend.file_system.manager import delete_fs_file
    result = await delete_fs_file(file_system_id, chat_id=actual_chat_id, workspace_id=actual_workspace_id)
    return jsonify(result)


@file_system_bp.route('/<path:file_system_id>/export/markdown', methods=['GET'])
async def export_fs_file_markdown_endpoint(file_system_id):
    """Export file_system as markdown file."""
    chat_id = request.args.get('chat_id')
    if not chat_id:
        return jsonify({"error": "chat_id is required"}), 400
        
    workspace_id = request.args.get('workspace_id')
    if workspace_id:
        file_system = db.get_file_system_meta(file_system_id=file_system_id, workspace_id=workspace_id)
    else:
        # Strictly look in chat context if no workspace_id is provided
        file_system = db.get_file_system_meta(file_system_id=file_system_id, chat_id=chat_id)
    if not file_system:
        return jsonify({"success": False, "error": "FileSystem not found"}), 404

    actual_chat_id = file_system.get('chat_id')
    actual_workspace_id = file_system.get('workspace_id')

    from backend.file_system.manager import export_fs_file_markdown
    content, filename = await export_fs_file_markdown(file_system_id, chat_id=actual_chat_id, workspace_id=actual_workspace_id)
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


@file_system_bp.route('/<path:file_system_id>/export/html', methods=['GET'])
async def export_fs_file_html_endpoint(file_system_id):
    """Export file_system as HTML file."""
    chat_id = request.args.get('chat_id')
    if not chat_id:
        return jsonify({"error": "chat_id is required"}), 400
        
    workspace_id = request.args.get('workspace_id')
    if workspace_id:
        file_system = db.get_file_system_meta(file_system_id=file_system_id, workspace_id=workspace_id)
    else:
        # Strictly look in chat context if no workspace_id is provided
        file_system = db.get_file_system_meta(file_system_id=file_system_id, chat_id=chat_id)
    if not file_system:
        return jsonify({"success": False, "error": "FileSystem not found"}), 404

    actual_chat_id = file_system.get('chat_id')
    actual_workspace_id = file_system.get('workspace_id')

    from backend.file_system.manager import export_fs_file_html
    html_content, filename = await export_fs_file_html(file_system_id, chat_id=actual_chat_id, workspace_id=actual_workspace_id)
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


@file_system_bp.route('/<path:file_system_id>/export/pdf', methods=['GET'])
async def export_fs_file_pdf_endpoint(file_system_id):
    """Export file_system as PDF file."""
    chat_id = request.args.get('chat_id')
    if not chat_id:
        return jsonify({"error": "chat_id is required"}), 400
        
    workspace_id = request.args.get('workspace_id')
    if workspace_id:
        file_system = db.get_file_system_meta(file_system_id=file_system_id, workspace_id=workspace_id)
    else:
        # Strictly look in chat context if no workspace_id is provided
        file_system = db.get_file_system_meta(file_system_id=file_system_id, chat_id=chat_id)
    if not file_system:
        return jsonify({"success": False, "error": "FileSystem not found"}), 404

    actual_chat_id = file_system.get('chat_id')
    actual_workspace_id = file_system.get('workspace_id')

    from backend.file_system.manager import export_fs_file_pdf
    pdf_content, filename = await export_fs_file_pdf(file_system_id, chat_id=actual_chat_id, workspace_id=actual_workspace_id)
    if pdf_content is None:
        return jsonify({"error": filename}), 404

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


@file_system_bp.route('/<path:file_system_id>/folder', methods=['POST'])
def set_file_system_folder(file_system_id):
    """Set folder for a file_system."""
    data, err = read_json_object(required=False)
    if err:
        return err
    chat_id = data.get('chat_id')
    if not chat_id:
        return jsonify({"error": "chat_id is required"}), 400

    workspace_id = request.args.get('workspace_id')
    if workspace_id:
        file_system = db.get_file_system_meta(file_system_id=file_system_id, workspace_id=workspace_id)
    else:
        # Strictly look in chat context if no workspace_id is provided
        file_system = db.get_file_system_meta(file_system_id=file_system_id, chat_id=chat_id)
    if not file_system:
        return jsonify({"error": "FileSystem not found"}), 404

    folder = data.get('folder', '')
    base_title = file_system['title'].split('/')[-1] if '/' in file_system['title'] else file_system['title']
    
    from backend.file_system.utils import sanitize_path
    path_parts = []
    if folder:
        path_parts.append(folder)
    path_parts.append(base_title)
    computed_new_path = sanitize_path('/'.join(path_parts))

    from backend.file_system.manager import update_file_system_metadata
    update_file_system_metadata(chat_id=chat_id, current_path=file_system['filename'], new_path=computed_new_path, title=base_title, folder=folder)
    return jsonify({"success": True, "title": base_title})


@file_system_bp.route('/<path:file_system_id>/tags', methods=['POST'])
def set_file_system_tags(file_system_id):
    """Set tags for a file_system."""
    data, err = read_json_object(required=False)
    if err:
        return err
    chat_id = data.get('chat_id')
    if not chat_id:
        return jsonify({"error": "chat_id is required"}), 400

    workspace_id = request.args.get('workspace_id')
    if workspace_id:
        file_system = db.get_file_system_meta(file_system_id=file_system_id, workspace_id=workspace_id)
    else:
        # Strictly look in chat context if no workspace_id is provided
        file_system = db.get_file_system_meta(file_system_id=file_system_id, chat_id=chat_id)
    if not file_system:
        return jsonify({"error": "FileSystem not found"}), 404

    actual_chat_id = file_system.get('chat_id')
    actual_workspace_id = file_system.get('workspace_id')

    tags = data.get('tags', [])
    if isinstance(tags, str):
        tags = [tags]

    db.save_file_system_meta(file_system_id=file_system_id, chat_id=actual_chat_id, workspace_id=actual_workspace_id, title=file_system['title'], filename=file_system['filename'], folder=file_system.get('folder'), tags=tags)
    return jsonify({"success": True, "tags": tags})
def remove_fs_file_tag(file_system_id, tag):
    """Remove a tag from a file_system."""
    chat_id = request.args.get('chat_id')
    if not chat_id:
        return jsonify({"error": "chat_id is required"}), 400

    workspace_id = request.args.get('workspace_id')
    if workspace_id:
        file_system = db.get_file_system_meta(file_system_id=file_system_id, workspace_id=workspace_id)
    else:
        # Strictly look in chat context if no workspace_id is provided
        file_system = db.get_file_system_meta(file_system_id=file_system_id, chat_id=chat_id)
    if not file_system:
        return jsonify({"error": "FileSystem not found"}), 404

    actual_chat_id = file_system.get('chat_id')
    actual_workspace_id = file_system.get('workspace_id')

    try:
        current_tags = json.loads(file_system.get('tags', '[]'))
    except:
        current_tags = []

    if tag in current_tags:
        current_tags.remove(tag)

    db.save_file_system_meta(file_system_id=file_system_id, chat_id=actual_chat_id, workspace_id=actual_workspace_id, title=file_system['title'], filename=file_system['filename'], folder=file_system.get('folder'), tags=current_tags)
    return jsonify({"success": True, "tags": current_tags})


@file_system_bp.route('/<path:file_system_id>/tags/<tag>', methods=['POST'])
def add_file_system_tag(file_system_id, tag):
    """Add a tag to a file_system."""
    chat_id = request.args.get('chat_id')
    if not chat_id:
        return jsonify({"error": "chat_id is required"}), 400

    workspace_id = request.args.get('workspace_id')
    if workspace_id:
        file_system = db.get_file_system_meta(file_system_id=file_system_id, workspace_id=workspace_id)
    else:
        # Strictly look in chat context if no workspace_id is provided
        file_system = db.get_file_system_meta(file_system_id=file_system_id, chat_id=chat_id)
    if not file_system:
        return jsonify({"error": "FileSystem not found"}), 404

    actual_chat_id = file_system.get('chat_id')
    actual_workspace_id = file_system.get('workspace_id')

    try:
        current_tags = json.loads(file_system.get('tags', '[]'))
    except:
        current_tags = []

    if tag not in current_tags:
        current_tags.append(tag)

    db.save_file_system_meta(file_system_id=file_system_id, chat_id=actual_chat_id, workspace_id=actual_workspace_id, title=file_system['title'], filename=file_system['filename'], folder=file_system.get('folder'), tags=current_tags)
    return jsonify({"success": True, "tags": current_tags})


@file_system_bp.route('/<path:file_system_id>/versions', methods=['GET'])
async def get_file_system_versions_endpoint(file_system_id):
    """Get version history for a file_system."""
    chat_id = request.args.get('chat_id')
    if not chat_id:
        return jsonify({"error": "chat_id is required"}), 400
        
    workspace_id = request.args.get('workspace_id')
    _, missing = _fs_meta_or_404(file_system_id, chat_id, workspace_id)
    if missing:
        return missing
    from backend.file_system.manager import get_file_system_versions
    versions = get_file_system_versions(file_system_id, chat_id, workspace_id=workspace_id)
    if not versions:
        return jsonify({
            "success": True,
            "file_system_id": file_system_id,
            "versions": []
        })

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
        "file_system_id": file_system_id,
        "versions": versions_response
    })


@file_system_bp.route('/<path:file_system_id>/versions/<int:version_number>', methods=['GET'])
async def get_fs_file_version_endpoint(file_system_id, version_number):
    """Get a specific version of a file_system content."""
    chat_id = request.args.get('chat_id')
    if not chat_id:
        return jsonify({"error": "chat_id is required"}), 400
        
    version = get_fs_file_version(file_system_id, chat_id, version_number)
    if version is None:
        return jsonify({"success": False, "error": "Version not found"}), 404

    return jsonify({
        "success": True,
        "file_system_id": file_system_id,
        "version_number": version_number,
        "content": version['content']
    })


@file_system_bp.route('/<path:file_system_id>/versions/<int:version_number>/restore', methods=['POST'])
async def restore_fs_file_version_endpoint(file_system_id, version_number):
    """Restore a file_system to a previous version."""
    data, err = read_json_object(required=False)
    if err:
        return err
    chat_id = data.get('chat_id') or request.args.get('chat_id')
    if not chat_id:
        return jsonify({"error": "chat_id is required"}), 400
        
    workspace_id = request.args.get('workspace_id')
    from backend.file_system.manager import restore_fs_file_version
    result = await restore_fs_file_version(file_system_id, chat_id, version_number, workspace_id=workspace_id)
    if result['success']:
        return jsonify(result)
    return jsonify(result), 404


@file_system_bp.route('/<path:file_system_id>/diff', methods=['POST'])
async def get_fs_file_diff_endpoint(file_system_id):
    """Get diff between two versions."""
    data, err = read_json_object(required=False)
    if err:
        return err
    chat_id = data.get('chat_id') or request.args.get('chat_id')
    if not chat_id:
        return jsonify({"success": False, "error": "chat_id is required"}), 400

    version1 = data.get('version1')
    version2 = data.get('version2')

    if version1 is None or version2 is None:
        return jsonify({"success": False, "error": "version1 and version2 are required"}), 400

    workspace_id = request.args.get('workspace_id')
    _, missing = _fs_meta_or_404(file_system_id, chat_id, workspace_id)
    if missing:
        return missing
    from backend.file_system.manager import get_fs_file_diff
    result = get_fs_file_diff(file_system_id, chat_id, version1, version2, workspace_id=workspace_id)
    if result['success']:
        return jsonify(result)
    return jsonify(result), 400


@file_system_bp.route('/<path:file_system_id>/current-version', methods=['GET'])
async def get_file_system_current_version_endpoint(file_system_id):
    """Get the current active version number for a file_system."""
    chat_id = request.args.get('chat_id')
    if not chat_id:
        return jsonify({"error": "chat_id is required"}), 400

    workspace_id = request.args.get('workspace_id')
    if workspace_id:
        file_system_meta = db.get_file_system_meta(file_system_id=file_system_id, workspace_id=workspace_id)
    else:
        # Strictly look in chat context if no workspace_id is provided
        file_system_meta = db.get_file_system_meta(file_system_id=file_system_id, chat_id=chat_id)
    if not file_system_meta:
        return jsonify({"error": "FileSystem not found"}), 404
        
    actual_chat_id = file_system_meta.get('chat_id')
    actual_workspace_id = file_system_meta.get('workspace_id')

    current_version_obj = db.get_file_system_current_version(file_system_id=file_system_id, chat_id=actual_chat_id, workspace_id=actual_workspace_id)
    current_version = current_version_obj.get('version_number') if current_version_obj else None

    return jsonify({
        "success": True,
        "file_system_id": file_system_id,
        "current_version": current_version
    })


@file_system_bp.route('/<path:file_system_id>/navigate-version', methods=['POST'])
async def navigate_to_version_endpoint(file_system_id):
    """Navigate to a specific version of a file_system without creating a new version."""
    data, err = read_json_object(required=False)
    if err:
        return err
    chat_id = data.get('chat_id')
    version_number = data.get('version_number')

    if not chat_id or version_number is None:
        return jsonify({"success": False, "error": "chat_id and version_number are required"}), 400

    _, missing = _fs_meta_or_404(file_system_id, chat_id, request.args.get('workspace_id'))
    if missing:
        return missing
    from backend.file_system.manager import navigate_file_system_version
    result = await navigate_file_system_version(
        chat_id=chat_id, file_system_id=file_system_id, version_number=version_number
    )
    return jsonify(result)


@file_system_bp.route('/<path:file_system_id>/delete-future-versions', methods=['POST'])
async def delete_future_versions_endpoint(file_system_id):
    """Delete all versions after a specific version (for branch handling)."""
    data, err = read_json_object(required=False)
    if err:
        return err
    chat_id = data.get('chat_id')
    up_to_version = data.get('up_to_version')

    if not chat_id:
        return jsonify({"error": "chat_id is required"}), 400
    if up_to_version is None:
        return jsonify({"error": "up_to_version is required"}), 400

    workspace_id = request.args.get('workspace_id')
    if workspace_id:
        file_system_meta = db.get_file_system_meta(file_system_id=file_system_id, workspace_id=workspace_id)
    else:
        # Strictly look in chat context if no workspace_id is provided
        file_system_meta = db.get_file_system_meta(file_system_id=file_system_id, chat_id=chat_id)
    if not file_system_meta:
        return jsonify({"error": "FileSystem not found"}), 404
        
    actual_chat_id = file_system_meta.get('chat_id')
    actual_workspace_id = file_system_meta.get('workspace_id')

    deleted_count = db.delete_file_system_versions_after(file_system_id=file_system_id, chat_id=actual_chat_id, workspace_id=actual_workspace_id, up_to_version=up_to_version)

    return jsonify({
        "success": True,
        "file_system_id": file_system_id,
        "deleted_versions": deleted_count,
        "up_to_version": up_to_version
    })


@file_system_bp.route('/channel/status', methods=['GET'])
def get_channel_status():
    """
    Get status of file_system channel for specific chat.
    Returns lock status and queue depth.
    """
    chat_id = request.args.get('chat_id')
    if not chat_id:
        return jsonify({"error": "chat_id is required"}), 400
    
    status = FileSystemChannelManager.get_status(chat_id)
    return jsonify(status)
