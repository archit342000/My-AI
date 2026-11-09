import os
import re
import json
import time
import logging
import difflib
from typing import Optional, Dict, List, Tuple, Any
import fitz # PyMuPDF
import aiofiles

from backend.logging import log_event
from backend.database import db

from .channel import FileSystemChannelManager
from .utils import (
    FILE_SYSTEMS_DIR, 
    WORKSPACES_DIR,
    sanitize_path,
    sanitize_filename,
    get_workspace_for_chat,
    resolve_owner_and_physical_path,
    ensure_physical_dir_exists,
    generate_fs_file_id, 
    new_fs_file_id,
    _extract_fs_file_type
)
from .fuzzy_matcher import _find_exact_match, MultipleMatchesError, MatchNotFoundError

logger = logging.getLogger(__name__)

def get_all_file_systems_for_chat(chat_id: str) -> List[Dict[str, Any]]:
    """Helper to get both chat-local and workspace-shared file_systems for a chat."""
    workspace_id = get_workspace_for_chat(chat_id)
    file_systems = db.get_chat_file_systems(chat_id)
    if workspace_id:
        ws_file_systems = db.get_owner_file_systems(workspace_id=workspace_id)
        for wc in ws_file_systems:
            if not wc['filename'].startswith("workspace/"):
                wc['filename'] = "workspace/" + wc['filename']
        file_systems.extend(ws_file_systems)
    return file_systems

def is_binary_file(filepath: str) -> bool:
    try:
        # Check by extension first for common binary/media types
        ext = os.path.splitext(filepath)[1].lower()
        if ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.heic', '.pdf', '.docx', '.mp4', '.webm', '.mp3', '.wav', '.zip', '.tar', '.gz', '.db', '.sqlite', '.exe', '.dll', '.so', '.o', '.a', '.pyc', '.bin']:
            return True
            
        with open(filepath, 'rb') as f:
            chunk = f.read(8000)
            return b'\0' in chunk
    except Exception:
        return True

def resolve_path_to_fs_file(chat_id: Optional[str], path: str, workspace_id: Optional[str] = None) -> Dict[str, Any]:
    """Resolve a relative virtual path to a file_system metadata object."""
    target_chat_id, target_workspace_id, physical_path = resolve_owner_and_physical_path(chat_id, path, workspace_id=workspace_id)
    
    safe_path = sanitize_path(path)
    if safe_path.startswith("workspace/") or safe_path == "workspace" or (chat_id is None and workspace_id is not None):
        lookup_path = safe_path
        if lookup_path.startswith("workspace/"):
            lookup_path = lookup_path[len("workspace/"):].strip("/")
        elif lookup_path == "workspace":
            lookup_path = ""
    else:
        lookup_path = safe_path
        
    file_system = db.get_file_system_meta_by_path(path=lookup_path, chat_id=target_chat_id, workspace_id=target_workspace_id)
    if not file_system:
        if os.path.exists(physical_path) and os.path.isfile(physical_path):
            parts = lookup_path.split('/')
            if '.git' in parts or any(p.startswith('.git') for p in parts):
                raise FileNotFoundError(f"No file_system found at path: {safe_path}")
                
            ext = os.path.splitext(lookup_path)[1].lower()
            lang = ext.lstrip('.') if ext else 'markdown'
            mtime = os.path.getmtime(physical_path)
            
            return {
                "id": f"disk:{safe_path}",
                "chat_id": target_chat_id,
                "workspace_id": target_workspace_id,
                "title": os.path.basename(lookup_path),
                "filename": safe_path,
                "timestamp": mtime,
                "folder": os.path.dirname(lookup_path),
                "tags": "[]",
                "file_system_type": "custom",
                "current_version": 1,
                "language": lang
            }
        raise FileNotFoundError(f"No file_system found at path: {safe_path}")
    return file_system

async def create_fs_file(
    chat_id: Optional[str],
    path: str,
    content: str = "",
    file_system_type: str = "custom",
    tags: Optional[List[str]] = None,
    author: str = "system",
    version_comment: str = "Initial version",
    language: str = "markdown",
    workspace_id: Optional[str] = None,
    clipboard_key: Optional[str] = None
) -> Dict[str, Any]:
    """Create a new file_system at a specific path with automatic persistence and locking."""
    if clipboard_key:
        if not chat_id:
            return {"success": False, "error": "chat_id is required to resolve clipboard_key."}
        resolved = db.clipboard_get(chat_id, clipboard_key)
        if resolved is None:
            return {"success": False, "error": f"Clipboard key '{clipboard_key}' not found."}
        content = resolved

    owner_id = chat_id or workspace_id
    if not owner_id:
        return {"success": False, "error": "Either chat_id or workspace_id must be provided."}
    channel = FileSystemChannelManager.get_channel(owner_id)
    source = "ai" if author == "system" else "user"

    await channel.acquire(source)
    try:
        target_chat_id, target_workspace_id, physical_path = resolve_owner_and_physical_path(chat_id, path, workspace_id=workspace_id)

        # Chats are created (and owner-checked) by the routes; a missing chat is an error here, not something to create.
        if target_chat_id and db.get_chat_owner(target_chat_id) is None:
            return {"success": False, "error": "Chat not found"}

        safe_path = sanitize_path(path)
        if not safe_path:
            return {
                "success": False,
                "error": "Invalid path: cannot create a file with an empty filename."
            }
        if safe_path.startswith("workspace/") or safe_path == "workspace":
            lookup_path = safe_path[len("workspace/"):].strip("/")
        else:
            lookup_path = safe_path

        # Infer language from extension if it's default markdown but path says otherwise
        if language == "markdown" and "." in lookup_path:
            ext = lookup_path.split(".")[-1].lower()
            if ext not in ["md", "markdown"]:
                language = ext

        # Check if already exists

        existing = db.get_file_system_meta_by_path(path=lookup_path, chat_id=target_chat_id, workspace_id=target_workspace_id)
        if existing:
            return {
                "success": False, 
                "error": f"A file_system already exists at path '{safe_path}'. Please use a different path or use replace_fs_text to update it."
            }

        ensure_physical_dir_exists(physical_path, is_file_path=True)
        file_system_id = await generate_fs_file_id(chat_id=target_chat_id, workspace_id=target_workspace_id, file_system_type=file_system_type)

        async with aiofiles.open(physical_path, mode='w', encoding='utf-8') as f:
            await f.write(content)

        # Derive title from path
        title = os.path.basename(lookup_path)

        # Diagnostic: log exactly what is being passed to the DB insert
        logger.info(
            f"[CREATE_FILE_SYSTEM] file_system_id={file_system_id!r} "
            f"chat_id={target_chat_id!r} workspace_id={target_workspace_id!r} "
            f"path={lookup_path!r} type={file_system_type!r}"
        )

        # Validate workspace exists BEFORE inserting (produces a clear error
        # instead of a cryptic FOREIGN KEY constraint failure)
        if target_workspace_id:
            from backend.database.db_layer import make_connection
            _ws_conn = make_connection()
            try:
                _ws_c = _ws_conn.cursor()
                _ws_c.execute("SELECT id FROM workspaces WHERE id = ?", (target_workspace_id,))
                if not _ws_c.fetchone():
                    raise ValueError(
                        f"Workspace '{target_workspace_id}' does not exist in the database. "
                        f"Cannot create a workspace file_system without a valid parent workspace."
                    )
            finally:
                _ws_conn.close()

        db.create_file_system_with_version(
            file_system_id=file_system_id, chat_id=target_chat_id, workspace_id=target_workspace_id, title=title,
            filename=lookup_path, content=content, author=author,
            comment=version_comment, folder="", file_system_type=file_system_type,
            tags=tags, language=language
        )
        if target_chat_id:
            db.update_chat_file_system_mode(target_chat_id, True)

        try:
            db.sync_file_system_search_index(file_system_id, chat_id=target_chat_id, workspace_id=target_workspace_id)
        except Exception as e:
            logger.error(f"Failed to sync FTS5 index for file_system {file_system_id}: {e}")

        return {
            "success": True, 
            "action": "create",
            "path": safe_path,
            "file_system_id": file_system_id, 
            "filepath": physical_path, 
            "version_id": 1, 
            "timestamp": time.time()
        }
    finally:
        await channel.release()

async def get_fs_file_content(file_system_id: str, chat_id: str = None, workspace_id: str = None) -> Optional[str]:
    """Get file_system content by ID."""
    content = db.get_file_system_content_by_id(file_system_id, chat_id=chat_id, workspace_id=workspace_id)
    if content is not None:
        return content
        
    # Disk fallback
    if file_system_id.startswith("disk:"):
        virtual_path = file_system_id[5:]
        try:
            _, _, physical_path = resolve_owner_and_physical_path(chat_id, virtual_path, workspace_id=workspace_id)
            if os.path.exists(physical_path) and os.path.isfile(physical_path):
                if is_binary_file(physical_path):
                    return "[Binary File] This file contains binary content and cannot be displayed in the text editor."
                async with aiofiles.open(physical_path, mode='r', encoding='utf-8', errors='replace') as f:
                    return await f.read()
        except Exception as e:
            logger.error(f"Error reading physical file for disk fallback {virtual_path}: {e}")
            
    return None

async def update_fs_file_content(
    file_system_id: str,
    chat_id: str = None,
    new_content: str = None,
    author: str = "user",
    version_comment: str = "Updated by user",
    workspace_id: str = None,
    **kwargs
) -> Dict[str, Any]:
    """Update file_system content and create a new version."""
    # We still use the chat's channel lock to prevent concurrent user/AI edits in the same session.
    # If this is a cross-session workspace edit, we rely on SQLite's CONFLICT/Transaction locks.
    channel = FileSystemChannelManager.get_channel(chat_id) if chat_id else None
    source = "ai" if author == "system" else "user"

    if channel: await channel.acquire(source)
    try:
        file_system_meta = db.get_file_system_meta(file_system_id, chat_id=chat_id, workspace_id=workspace_id)
        if not file_system_meta:
            return {"success": False, "error": "FileSystem not found"}

        safe_path = file_system_meta['filename']
        actual_chat_id = file_system_meta.get('chat_id')
        actual_workspace_id = file_system_meta.get('workspace_id')
        
        if actual_workspace_id:
            physical_dir = os.path.join(WORKSPACES_DIR, sanitize_filename(actual_workspace_id))
        else:
            physical_dir = os.path.join(FILE_SYSTEMS_DIR, sanitize_filename(actual_chat_id))
            
        filepath = os.path.join(physical_dir, safe_path)
        ensure_physical_dir_exists(filepath, is_file_path=True)
        
        async with aiofiles.open(filepath, mode='w', encoding='utf-8') as f:
            await f.write(new_content)

        versions = db.get_file_system_versions(file_system_id, chat_id=actual_chat_id, workspace_id=actual_workspace_id)
        next_version = (versions[0]['version_number'] if versions else 0) + 1
        db.save_file_system_version(
            file_system_id=file_system_id, 
            chat_id=actual_chat_id, 
            workspace_id=actual_workspace_id,
            version_number=next_version, 
            content=new_content, 
            author=author, 
            comment=version_comment
        )
        
        # Update navigation path for non-linear undo/redo
        try:
            nav_history = json.loads(file_system_meta.get('navigation_history', '[]'))
            nav_index = int(file_system_meta.get('navigation_index', -1))
        except (json.JSONDecodeError, TypeError, ValueError):
            nav_history = []
            nav_index = -1

        # If we navigated back and are now editing, prune the "future" path
        if 0 <= nav_index < len(nav_history) - 1:
            nav_history = nav_history[:nav_index + 1]
        
        nav_history.append(next_version)
        nav_index = len(nav_history) - 1

        # Preserve or update file_system_type
        target_type = kwargs.get('file_system_type', file_system_meta.get('file_system_type', 'custom'))
        db.save_file_system_meta(
            file_system_id=file_system_id, 
            chat_id=actual_chat_id, 
            workspace_id=actual_workspace_id,
            title=file_system_meta['title'], 
            filename=file_system_meta['filename'], 
            file_system_type=target_type, 
            current_version=next_version,
            navigation_history=json.dumps(nav_history),
            navigation_index=nav_index
        )

        try:
            db.sync_file_system_search_index(file_system_id, chat_id=actual_chat_id, workspace_id=actual_workspace_id)
        except Exception as e:
            logger.error(f"Failed to sync FTS5 index for file_system {file_system_id}: {e}")

        return {"success": True, "action": "patch", "file_system_id": file_system_id, "version_id": next_version, "timestamp": time.time(), "content": new_content}
    finally:
        if channel: await channel.release()

async def append_to_fs_file(file_system_id: str, chat_id: str, content_to_append: str, author: str = "system", version_comment: str = "Content appended") -> Dict[str, Any]:
    existing_content = await get_fs_file_content(file_system_id, chat_id) or ""
    # Normalize bridge to ensure exactly two newlines between blocks
    new_content = existing_content.rstrip('\n') + "\n\n" + content_to_append.lstrip('\n')
    return await update_fs_file_content(file_system_id, chat_id, new_content, author=author, version_comment=version_comment)




async def delete_fs_file(file_system_id: str, chat_id: str = None, workspace_id: str = None) -> Dict[str, Any]:
    channel = FileSystemChannelManager.get_channel(chat_id) if chat_id else None
    if channel: await channel.acquire("user")
    try:
        file_system_meta = db.get_file_system_meta(file_system_id, chat_id=chat_id, workspace_id=workspace_id)
        if not file_system_meta:
            return {"success": False, "error": "FileSystem not found"}

        actual_chat_id = file_system_meta.get('chat_id')
        actual_workspace_id = file_system_meta.get('workspace_id')

        if actual_workspace_id:
            filepath = os.path.join(WORKSPACES_DIR, sanitize_filename(actual_workspace_id), file_system_meta['filename'])
        else:
            filepath = os.path.join(FILE_SYSTEMS_DIR, sanitize_filename(actual_chat_id), file_system_meta['filename'])

        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except OSError as e:
            log_event("file_system_file_delete_error", {"file_system_id": file_system_id, "error": str(e)})

        db.delete_file_system(file_system_id, chat_id=actual_chat_id, workspace_id=actual_workspace_id)
        return { "success": True, "action": "delete", "file_system_id": file_system_id }
    finally:
        if channel: await channel.release()

def get_unique_folders(chat_id: str) -> List[str]:
    file_systems = get_all_file_systems_for_chat(chat_id)
    folders = set()
    for file_system in file_systems:
        if file_system.get('folder'):
            folders.add(file_system['folder'])
        elif '/' in file_system['title']:
            folders.add(file_system['title'].split('/')[0])
    return sorted(list(folders))

async def get_chat_file_systems_with_details(chat_id: str, include_content: bool = False) -> List[Dict[str, Any]]:
    file_systems = get_all_file_systems_for_chat(chat_id)
    results = []
    for file_system in file_systems:
        actual_chat_id = file_system.get('chat_id')
        actual_workspace_id = file_system.get('workspace_id')
        result = {"id": file_system['id'], "title": file_system['title'], "filename": file_system['filename'], "timestamp": file_system['timestamp']}
        content = await get_fs_file_content(file_system['id'], chat_id=actual_chat_id, workspace_id=actual_workspace_id) if include_content else ""
        if include_content: result["content"] = content
        result["type"] = _extract_fs_file_type(file_system['id'])
        result["preview"] = (content or "")[:200]
        result["folder"] = file_system['title'].split('/')[0] if '/' in file_system['title'] else ""
        results.append(result)
    return results

async def export_fs_file_markdown(file_system_id: str, chat_id: str) -> Tuple[Optional[str], str]:
    workspace_id = get_workspace_for_chat(chat_id)
    file_system_meta = db.get_file_system_meta(file_system_id, chat_id=chat_id, workspace_id=workspace_id)
    if not file_system_meta: return None, "FileSystem not found"
    
    actual_chat_id = file_system_meta.get('chat_id')
    actual_workspace_id = file_system_meta.get('workspace_id')
    content = await get_fs_file_content(file_system_id, chat_id=actual_chat_id, workspace_id=actual_workspace_id)
    if content is None: return None, "FileSystem content not found"
    
    language = file_system_meta.get('language', 'markdown')
    
    # Map language to extension (e.g. 'python' -> '.py')
    ext_map = {
        "markdown": ".md",
        "json": ".json",
        "html": ".html",
        "xml": ".xml",
        "python": ".py",
        "c": ".c",
        "cpp": ".cpp",
        "sql": ".sql"
    }
    ext = ext_map.get(language, ".txt")
    
    filename = f"{file_system_meta['title'].replace(' ', '_')}{ext}" if file_system_meta else f"file_system_{file_system_id}{ext}"
    return content, filename

async def export_fs_file_html(file_system_id: str, chat_id: str) -> Tuple[Optional[str], str]:
    import markdown
    workspace_id = get_workspace_for_chat(chat_id)
    file_system_meta = db.get_file_system_meta(file_system_id, chat_id=chat_id, workspace_id=workspace_id)
    if not file_system_meta: return None, "FileSystem not found"
    
    actual_chat_id = file_system_meta.get('chat_id')
    actual_workspace_id = file_system_meta.get('workspace_id')
    content = await get_fs_file_content(file_system_id, chat_id=actual_chat_id, workspace_id=actual_workspace_id)
    if content is None: return None, "FileSystem content not found"
    
    html_content = markdown.markdown(content, output_format='html5')
    title = file_system_meta['title']
    html_template = f"<!DOCTYPE html><html><head><title>{title}</title><style>body {{ font-family: sans-serif; max-width: 800px; margin: 0 auto; padding: 2rem; line-height: 1.6; }}</style></head><body>{html_content}</body></html>"
    return html_template, f"{title.replace(' ', '_')}.html"

async def export_fs_file_pdf(file_system_id: str, chat_id: str) -> Tuple[Optional[bytes], str]:
    html_content, _ = await export_fs_file_html(file_system_id, chat_id)
    if html_content is None: return None, "FileSystem not found"
    try:
        doc = fitz.open()
        story = fitz.Story(html_content)
        while True:
            page = doc.new_page()
            where = fitz.Rect(72, 72, page.rect.width - 72, page.rect.height - 72)
            story.place(where)
            _, finished = story.draw(page)
            if finished: break
        pdf_bytes = doc.tobytes()
        doc.close()
        workspace_id = get_workspace_for_chat(chat_id)
        file_system_meta = db.get_file_system_meta(file_system_id, chat_id=chat_id, workspace_id=workspace_id)
        filename = f"{file_system_meta['title'].replace(' ', '_')}.pdf" if file_system_meta else f"file_system_{file_system_id}.pdf"
        return pdf_bytes, filename
    except Exception as e:
        logger.error(f"PDF generation failed for file_system {file_system_id}: {e}")
        return None, f"PDF generation failed: {str(e)}"

def get_file_system_versions(file_system_id: str, chat_id: str = None, workspace_id: str = None) -> List[Dict[str, Any]]:
    """Get all versions for a file_system."""
    if not workspace_id and chat_id:
        from backend.file_system.utils import get_workspace_for_chat
        workspace_id = get_workspace_for_chat(chat_id)
    
    # Use the explicit owner context to get the correct metadata first
    file_system_meta = db.get_file_system_meta(file_system_id, chat_id=chat_id, workspace_id=workspace_id)
    if not file_system_meta:
        return []
    return db.get_file_system_versions(file_system_id, chat_id=file_system_meta.get('chat_id'), workspace_id=file_system_meta.get('workspace_id'))

async def restore_fs_file_version(file_system_id: str, chat_id: str, version_number: int, workspace_id: str = None) -> Dict[str, Any]:
    """Restore a file_system to a previous version by updating the navigation path."""
    if not workspace_id and chat_id:
        from backend.file_system.utils import get_workspace_for_chat
        workspace_id = get_workspace_for_chat(chat_id)
    
    file_system_meta = db.get_file_system_meta(file_system_id, chat_id=chat_id, workspace_id=workspace_id)
    if not file_system_meta:
        return {"success": False, "error": "FileSystem not found"}
        
    actual_chat_id = file_system_meta.get('chat_id')
    actual_workspace_id = file_system_meta.get('workspace_id')

    content = db.get_file_system_version_content(file_system_id, chat_id=actual_chat_id, workspace_id=actual_workspace_id, version_number=version_number)
    if content is None: 
        return {"success": False, "error": f"Version {version_number} not found"}

    try:
        nav_history = json.loads(file_system_meta.get('navigation_history', '[]'))
        nav_index = int(file_system_meta.get('navigation_index', -1))
    except (json.JSONDecodeError, TypeError, ValueError):
        nav_history = []
        nav_index = -1

    # Record the 'jump' in navigation history
    # If the requested version is already the current one at the current index, do nothing
    if 0 <= nav_index < len(nav_history) and nav_history[nav_index] == version_number:
        return {
            "success": True, 
            "file_system_id": file_system_id, 
            "version_number": version_number, 
            "content": content,
            "navigation_history": json.dumps(nav_history),
            "navigation_index": nav_index
        }

    # Prune future path if we are in the middle of history
    if 0 <= nav_index < len(nav_history) - 1:
        nav_history = nav_history[:nav_index + 1]
    
    nav_history.append(version_number)
    nav_index = len(nav_history) - 1
    
    db.save_file_system_meta(
        file_system_id=file_system_id,
        chat_id=actual_chat_id,
        workspace_id=actual_workspace_id,
        current_version=version_number,
        navigation_history=json.dumps(nav_history),
        navigation_index=nav_index
    )

    # Sync disk file
    try:
        safe_path = file_system_meta['filename']
        _, _, filepath = resolve_owner_and_physical_path(chat_id, safe_path)
        ensure_physical_dir_exists(filepath, is_file_path=True)
        async with aiofiles.open(filepath, mode='w', encoding='utf-8') as f:
            await f.write(content)
    except Exception as e:
        logger.error(f"Failed to sync disk file during restore: {e}")

    return {
        "success": True, 
        "file_system_id": file_system_id, 
        "version_number": version_number, 
        "content": content,
        "navigation_history": json.dumps(nav_history),
        "navigation_index": nav_index
    }

def get_fs_file_version(file_system_id: str, chat_id: str = None, version_number: int = 1, workspace_id: str = None) -> Optional[Dict[str, Any]]:
    """Get a specific version of a file_system."""
    if not workspace_id and chat_id:
        from backend.file_system.utils import get_workspace_for_chat
        workspace_id = get_workspace_for_chat(chat_id)
    file_system_meta = db.get_file_system_meta(file_system_id, chat_id=chat_id, workspace_id=workspace_id)
    if not file_system_meta: return None
    content = db.get_file_system_version_content(file_system_id, chat_id=file_system_meta.get('chat_id'), workspace_id=file_system_meta.get('workspace_id'), version_number=version_number)
    if content is None: return None
    return {"content": content, "version_number": version_number}

def get_fs_file_diff(file_system_id: str, chat_id: str, version_a: int, version_b: int, workspace_id: str = None) -> Dict[str, Any]:
    """Get the diff between two versions of a file_system."""
    va = get_fs_file_version(file_system_id, chat_id, version_a, workspace_id=workspace_id)
    vb = get_fs_file_version(file_system_id, chat_id, version_b, workspace_id=workspace_id)
    if va is None: return {"success": False, "error": f"Version {version_a} not found"}
    if vb is None: return {"success": False, "error": f"Version {version_b} not found"}
    lines1, lines2 = va['content'].split('\n'), vb['content'].split('\n')
    added, removed = [], []
    for i in range(max(len(lines1), len(lines2))):
        l1 = lines1[i] if i < len(lines1) else ""
        l2 = lines2[i] if i < len(lines2) else ""
        if l1 != l2:
            if l1: removed.append(l1)
            if l2: added.append(l2)
    return {"success": True, "file_system_id": file_system_id, "from_version": version_a, "to_version": version_b, "added_lines": added, "removed_lines": removed, "stats": {"lines_added": len(added), "lines_removed": len(removed)}}


def delete_chat_fs_files(chat_id):
    import shutil
    from .utils import FILE_SYSTEMS_DIR, sanitize_filename
    path = os.path.join(FILE_SYSTEMS_DIR, sanitize_filename(chat_id))
    if os.path.exists(path):
        shutil.rmtree(path)
    return db.delete_chat_file_system_files(chat_id)

# --- Internal Patching Logic ---





async def read_fs_file_lines(path: str, chat_id: str, action_params: dict) -> Dict[str, Any]:
    try:
        file_system_meta = resolve_path_to_fs_file(chat_id, path)
    except FileNotFoundError as e:
        return {"success": False, "error": str(e)}

    file_system_id = file_system_meta['id']
    actual_chat_id = file_system_meta.get('chat_id')
    actual_workspace_id = file_system_meta.get('workspace_id')
    
    content = await get_fs_file_content(file_system_id, chat_id=actual_chat_id, workspace_id=actual_workspace_id) or ""
    lines = content.split('\n')
    total_lines = len(lines)
    current_version = file_system_meta['current_version']

    start_line = action_params.get("start_line")
    end_line = action_params.get("end_line")
    try:
        if start_line is not None:
            start_line = int(start_line)
        if end_line is not None:
            end_line = int(end_line)
    except (ValueError, TypeError):
        return {"success": False, "error": "start_line and end_line must be integers."}

    search_pattern = action_params.get("search_pattern")
    is_regex = action_params.get("is_regex", False)
    outline = action_params.get("outline", False)
    
    if outline:
        OUTLINE_PARSERS = {
            "markdown": r"^(#{1,6})\s+(.*)",
            "python": r"^\s*(def|class|async def)\s+(.*)",
            "sql": r"(?i)^\s*(CREATE|ALTER|DROP)\s+(TABLE|VIEW|PROCEDURE|FUNCTION)\s+(.*)",
            "html": r"<(h[1-6]|div id=)[^>]*>",
            "xml": r"<(h[1-6]|div id=)[^>]*>",
            "c": r"^\s*(class|struct)\s+\w+",
            "cpp": r"^\s*(class|struct)\s+\w+",
            "json": r"^\s*\"([^\"]+)\"\s*:\s*[{[]"
        }
        language = file_system_meta.get('language', 'markdown')
        pattern = OUTLINE_PARSERS.get(language)
        if not pattern:
            return {"success": False, "error": f"Outline mode not supported for language: {language}"}
        
        toc = []
        for i, line in enumerate(lines):
            if re.search(pattern, line):
                toc.append(f"{i + 1} | {line.strip()}")
        return {"success": True, "action": "read", "current_version": current_version, "content": "\n".join(toc)}
    
    if search_pattern:
        from backend.config import FILE_SYSTEM_MAX_SEARCH_RESULTS, FILE_SYSTEM_SEARCH_CONTEXT_LINES
        
        # Override with requested params if provided
        context_limit = min(action_params.get("context_lines", FILE_SYSTEM_SEARCH_CONTEXT_LINES), 10)
        match_limit = action_params.get("max_matches", FILE_SYSTEM_MAX_SEARCH_RESULTS)
        
        matches = []
        for i, line in enumerate(lines):
            if is_regex:
                try:
                    if re.search(search_pattern, line):
                        ctx_before = [f"{j+1} | {lines[j]}" for j in range(max(0, i - context_limit), i)]
                        ctx_after = [f"{j+1} | {lines[j]}" for j in range(i + 1, min(total_lines, i + 1 + context_limit))]
                        matches.append({"line_number": i + 1, "text": line, "context_before": ctx_before, "context_after": ctx_after})
                except re.error as e:
                    return {"success": False, "error": f"Invalid regex: {e}"}
            else:
                if search_pattern in line:
                    ctx_before = [f"{j+1} | {lines[j]}" for j in range(max(0, i - context_limit), i)]
                    ctx_after = [f"{j+1} | {lines[j]}" for j in range(i + 1, min(total_lines, i + 1 + context_limit))]
                    matches.append({"line_number": i + 1, "text": line, "context_before": ctx_before, "context_after": ctx_after})
                    
        total_matches = len(matches)
        matches = matches[:match_limit]
        warning = f"Match limit reached. {total_matches - match_limit} additional matches hidden. Refine your search pattern if you need to find a specific instance." if total_matches > match_limit else None
        return {
            "success": True, "action": "read", "current_version": current_version,
            "search_mode": True, "total_matches": total_matches, "matches_returned": len(matches),
            "warning": warning, "matches": matches
        }

    # Configuration limits
    DEFAULT_READ_LIMIT = 100
    MAX_BOUNDED_LIMIT = 300  # Absolute maximum lines an agent can request at once

    # Normalize inputs (1-indexed to 0-indexed)
    start_idx = max(0, start_line - 1) if start_line is not None else 0
    end_idx = end_line if end_line is not None else total_lines

    truncated = False
    warning_msg = None

    # Scenario 1: Naked Read (No bounds provided)
    if start_line is None and end_line is None:
        if total_lines > DEFAULT_READ_LIMIT:
            end_idx = DEFAULT_READ_LIMIT
            truncated = True
            warning_msg = f"FileSystem has {total_lines} lines. Only the first {DEFAULT_READ_LIMIT} lines are shown to protect context. Use start_line/end_line to read further, or outline=True for a map."
            
    # Scenario 2: Start line provided, but no end line
    elif start_line is not None and end_line is None:
        if (total_lines - start_idx) > DEFAULT_READ_LIMIT:
            end_idx = start_idx + DEFAULT_READ_LIMIT
            truncated = True
            warning_msg = f"Read truncated at {DEFAULT_READ_LIMIT} lines from start_line to protect context. Please provide an explicit end_line if you need more."

    # Scenario 3: Bounded Read (Both provided, or end_line provided)
    else:
        requested_lines = end_idx - start_idx
        if requested_lines > MAX_BOUNDED_LIMIT:
            end_idx = start_idx + MAX_BOUNDED_LIMIT
            truncated = True
            warning_msg = f"Requested {requested_lines} lines, which exceeds the absolute maximum of {MAX_BOUNDED_LIMIT}. Read has been truncated."

    # Final sanity bounds
    end_idx = min(total_lines, end_idx)

    formatted = [f"{i + 1} | {lines[i]}" for i in range(start_idx, end_idx)]
    result = {
        "success": True, "action": "read", 
        "file_system_id": file_system_meta['id'],
        "path": path,
        "current_version": current_version,
        "total_lines": total_lines, "content": "\n".join(formatted)
    }
    
    if truncated:
        result["truncated"] = True
        result["warning"] = warning_msg
        
    return result




def update_file_system_metadata(chat_id: Optional[str], current_path: str, **kwargs) -> Dict[str, Any]:
    """
    Updates file_system metadata and physically moves the file if the path changes.
    """
    workspace_id = kwargs.get('workspace_id')
    try:
        file_system_meta = resolve_path_to_fs_file(chat_id, current_path, workspace_id=workspace_id)
    except FileNotFoundError as e:
        return {"success": False, "error": str(e)}

    file_system_id = file_system_meta['id']
    new_path = kwargs.pop('new_path', None)
    
    if new_path:
        # Safety: If old path had an extension and new one doesn't, preserve it
        _, old_ext = os.path.splitext(current_path)
        _, new_ext = os.path.splitext(new_path)
        if old_ext and not new_ext:
            new_path += old_ext

    # If the path has changed, check for collision
    safe_new_path = sanitize_path(new_path) if new_path else None
    safe_current_path = sanitize_path(current_path)

    if safe_new_path and safe_new_path != safe_current_path:
        target_chat_id, target_workspace_id, new_physical_path = resolve_owner_and_physical_path(chat_id, safe_new_path, workspace_id=workspace_id)
        
        lookup_path = safe_new_path
        if lookup_path.startswith("workspace/"):
            lookup_path = lookup_path[len("workspace/"):].strip("/")
        elif lookup_path == "workspace":
            lookup_path = ""
            
        existing = db.get_file_system_meta_by_path(path=lookup_path, chat_id=target_chat_id, workspace_id=target_workspace_id)
        if existing:
            return {"success": False, "error": f"Cannot rename to '{safe_new_path}'. File already exists."}
        
        # We need the old physical path to move it
        _, _, old_physical_path = resolve_owner_and_physical_path(chat_id, current_path, workspace_id=workspace_id)
        
        # Check if owner changed
        actual_chat_id = file_system_meta.get('chat_id')
        actual_workspace_id = file_system_meta.get('workspace_id')
        owner_changed = (actual_chat_id != target_chat_id) or (actual_workspace_id != target_workspace_id)
        
        try:
            if os.path.exists(old_physical_path):
                ensure_physical_dir_exists(new_physical_path, is_file_path=True)
                os.rename(old_physical_path, new_physical_path)
            
            # Update DB filename (the path) and title (basename)
            # Ensure we don't pass these twice if they are in kwargs
            kwargs.pop('title', None)
            kwargs.pop('filename', None)
            new_title = os.path.basename(lookup_path)
            
            if owner_changed:
                new_id = new_fs_file_id()
                db.migrate_file_system_owner(
                    old_id=file_system_id, new_id=new_id,
                    old_chat_id=actual_chat_id, old_workspace_id=actual_workspace_id,
                    new_chat_id=target_chat_id, new_workspace_id=target_workspace_id,
                    new_filename=lookup_path, new_title=new_title
                )
                file_system_id = new_id
                if kwargs:
                    db.save_file_system_meta(file_system_id, chat_id=target_chat_id, workspace_id=target_workspace_id, **kwargs)
            else:
                db.save_file_system_meta(file_system_id, chat_id=target_chat_id, workspace_id=target_workspace_id, filename=lookup_path, title=new_title, **kwargs)
        except OSError as e:
            logger.error(f"Failed to move physical file_system file {file_system_id} during path update: {e}")
            return {"success": False, "error": f"File system error: {e}"}
    else:
        # Just update other metadata
        actual_chat_id = file_system_meta.get('chat_id')
        actual_workspace_id = file_system_meta.get('workspace_id')
        db.save_file_system_meta(file_system_id, chat_id=actual_chat_id, workspace_id=actual_workspace_id, **kwargs)

    return {"success": True, "action": "rename", "file_system_id": file_system_id}

async def navigate_file_system_version(chat_id: str, file_system_id: str, version_number: int) -> Dict[str, Any]:
    """
    Navigate to a specific version of a file_system.
    Updates the DB current_version pointer and synchronizes the disk file.
    """
    logger.info(f"navigate_file_system_version: chat_id={chat_id} file_system_id={file_system_id} v={version_number}")
    
    workspace_id = get_workspace_for_chat(chat_id)
    file_system_meta = db.get_file_system_meta(file_system_id, chat_id=chat_id, workspace_id=workspace_id)
    if not file_system_meta:
        return {"success": False, "error": "FileSystem not found."}
        
    actual_chat_id = file_system_meta.get('chat_id')
    actual_workspace_id = file_system_meta.get('workspace_id')
    
    # 1. Update DB pointer
    db.save_file_system_meta(file_system_id, chat_id=actual_chat_id, workspace_id=actual_workspace_id, current_version=version_number)
    
    # 2. Get content for that version
    content = db.get_file_system_version_content(file_system_id, chat_id=actual_chat_id, workspace_id=actual_workspace_id, version_number=version_number)
    if content is None:
        return {"success": False, "error": f"Version {version_number} not found."}
    
    # 3. Synchronize file on disk (so disk matches DB current_version)
    if file_system_meta.get('filename'):
        try:
            safe_path = file_system_meta['filename']
            _, _, filepath = resolve_owner_and_physical_path(chat_id, safe_path)
            ensure_physical_dir_exists(filepath, is_file_path=True)
            async with aiofiles.open(filepath, mode='w', encoding='utf-8') as f:
                await f.write(content)
        except Exception as e:
            logger.error(f"Failed to sync disk file during navigation: {e}")
            
    return {
        "success": True,
        "file_system_id": file_system_id,
        "version_number": version_number,
        "content": content
    }

async def ls_files_for_tool(chat_id: str, path: str = None, **kwargs) -> Dict[str, Any]:
    """Tool implementation to list immediate children files and directories in a path."""
    target_path = sanitize_path(path).rstrip('/') if path else ""
    prefix = target_path + '/' if target_path else ""
    
    workspace_id = get_workspace_for_chat(chat_id)
    
    # Gather file_systems from Database (both chat and workspace)
    file_systems = get_all_file_systems_for_chat(chat_id)
    
    if target_path:
        filtered_file_systems = [c for c in file_systems if c['filename'].startswith(prefix) or c['filename'] == target_path]
    else:
        filtered_file_systems = file_systems
        
    children = {}
    for c in filtered_file_systems:
        filename = c['filename']
        if not filename.startswith(prefix):
            # should only happen if exact match on target_path
            children[os.path.basename(filename)] = {"type": "file", "name": os.path.basename(filename), "path": filename}
            continue
            
        remainder = filename[len(prefix):]
        parts = remainder.split('/')
        
        name = parts[0]
        if len(parts) > 1:
            # It's a directory
            if name not in children:
                children[name] = {"type": "directory", "name": name, "path": prefix + name}
        else:
            # It's a file
            children[name] = {"type": "file", "name": name, "path": filename}
    
    # 2. Gather physical directories (to find empty ones)
    try:
        from .utils import sanitize_filename
        
        dirs_to_scan = []
        
        # Determine which physical directories map to this path
        if target_path.startswith("workspace/") or target_path == "workspace":
            if workspace_id:
                rest_of_path = target_path[len("workspace/"):].strip("/")
                base_ws_dir = os.path.join(WORKSPACES_DIR, sanitize_filename(workspace_id))
                physical_dir = os.path.join(base_ws_dir, rest_of_path)
                dirs_to_scan.append((physical_dir, target_path))
        else:
            base_chat_dir = os.path.join(FILE_SYSTEMS_DIR, sanitize_filename(chat_id))
            physical_dir = os.path.join(base_chat_dir, target_path)
            dirs_to_scan.append((physical_dir, target_path))
            
            # If at root, we also need to expose the virtual "workspace" folder if we have a workspace
            if not target_path and workspace_id:
                if "workspace" not in children:
                    children["workspace"] = {
                        "type": "directory", 
                        "name": "workspace", 
                        "path": "workspace"
                    }
        
        for p_dir, v_path in dirs_to_scan:
            if os.path.exists(p_dir) and os.path.isdir(p_dir):
                for entry in os.listdir(p_dir):
                    if entry == '.git' or entry.startswith('.git/'):
                        continue
                    full_entry_path = os.path.join(p_dir, entry)
                    if os.path.isdir(full_entry_path):
                        if entry not in children:
                            v_prefix = v_path + '/' if v_path else ""
                            children[entry] = {
                                "type": "directory", 
                                "name": entry, 
                                "path": v_prefix + entry
                            }
                    elif os.path.isfile(full_entry_path):
                        if entry not in children:
                            v_prefix = v_path + '/' if v_path else ""
                            children[entry] = {
                                "type": "file", 
                                "name": entry, 
                                "path": v_prefix + entry
                            }
    except Exception as e:
        logger.error(f"Error scanning physical directories in ls_files: {e}")
            
    return {
        "path": target_path or "/",
        "children": list(children.values())
    }

async def grep_files(chat_id: str, pattern: str, is_regex: bool = False, path: str = None,
                        context_chars: int = 300, max_matches_per_file_system: int = 5,
                        names_only: bool = False, **kwargs) -> Dict[str, Any]:
    try:
        if context_chars is not None:
            context_chars = int(context_chars)
        if max_matches_per_file_system is not None:
            max_matches_per_file_system = int(max_matches_per_file_system)
    except (ValueError, TypeError):
        return {"success": False, "error": "context_chars and max_matches_per_file_system must be integers."}

    file_systems = get_all_file_systems_for_chat(chat_id)

    if path:
        target_path = sanitize_path(path).rstrip('/')
        prefix = target_path + '/'
        file_systems = [c for c in file_systems if c['filename'].startswith(prefix) or c['filename'] == target_path]

    results = []
    total_matches_found = 0

    for c in file_systems:
        file_system_id = c['id']
        actual_chat_id = c.get('chat_id')
        actual_workspace_id = c.get('workspace_id')
        filepath = c.get('filename', 'unknown')

        file_system_content = await get_fs_file_content(file_system_id, chat_id=actual_chat_id, workspace_id=actual_workspace_id) or ""
        lines = file_system_content.split('\n')

        # Pre-compute per-line character offsets for fast context slicing
        line_offsets = []
        offset = 0
        for line in lines:
            line_offsets.append(offset)
            offset += len(line) + 1  # +1 for '\n'

        matches = []
        for i, line in enumerate(lines):
            match_found = False
            if is_regex:
                try:
                    if re.search(pattern, line):
                        match_found = True
                except Exception:
                    pass
            else:
                if pattern in line:
                    match_found = True

            if match_found:
                if names_only:
                    results.append({"path": filepath, "file_system_id": file_system_id})
                    break  # Skip to next file_system

                line_start_off = line_offsets[i]
                line_end_off = line_start_off + len(line)

                ctx_before = file_system_content[max(0, line_start_off - context_chars):line_start_off]
                ctx_after = file_system_content[line_end_off + 1:min(len(file_system_content), line_end_off + 1 + context_chars)]

                matches.append({
                    "line_number": i + 1,
                    "text": f"{filepath}:{i+1}: {line}",
                    "context_before": ctx_before,
                    "context_after": ctx_after,
                })
                total_matches_found += 1

        if not names_only and matches:
            file_system_match_count = len(matches)
            truncated = False
            if file_system_match_count > max_matches_per_file_system:
                matches = matches[:max_matches_per_file_system]
                truncated = True

            results.append({
                "path": filepath,
                "file_system_id": file_system_id,
                "matches": matches,
                "matches_truncated": truncated,
            })

    return {
        "success": True,
        "summary": {
            "total_file_systems_searched": len(file_systems),
            "total_matches_found": total_matches_found if not names_only else len(results),
            "names_only_mode": names_only,
        },
        "results": results,
    }

async def read_fs_file(chat_id: str, path: str, start_line: int = None, end_line: int = None, outline: bool = False, **kwargs) -> Dict[str, Any]:
    action_params = {"start_line": start_line, "end_line": end_line, "outline": outline}
    return await read_fs_file_lines(path, chat_id, action_params)

async def _finalize_edits(chat_id: str, id: str, workspace_id: str, expected_version: int, original_lines: list, lines: list, edit_results: list) -> Dict[str, Any]:
    applied_any = any(r["status"] == "applied" for r in edit_results)
    if applied_any:
        new_file_system_content = '\n'.join(lines)
        await update_fs_file_content(id, chat_id=chat_id, workspace_id=workspace_id, new_content=new_file_system_content, author="ai")
    
    # Generate unified diff
    diff_lines = list(difflib.unified_diff(
        original_lines, lines,
        lineterm='', n=2
    ))
    diff_text = '\n'.join(diff_lines[:40])
    if len(diff_lines) > 40:
        diff_text += f"\n... ({len(diff_lines) - 40} more diff lines)"
    
    return {
        "success": all(r["status"] == "applied" for r in edit_results),
        "file_system_id": id,
        "version_id": (expected_version + 1) if applied_any else expected_version,
        "message": f"Applied {len([r for r in edit_results if r['status'] == 'applied'])} of {len(edit_results)} edits.",
        "edit_results": edit_results,
        "diff": diff_text
    }

async def replace_fs_text(
    chat_id: str,
    path: str,
    expected_version: int,
    target_text: str,
    new_content: str = "",
    start_line: int = None,
    end_line: int = None,
    allow_multiple: bool = False,
    clipboard_key: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    if clipboard_key:
        resolved = db.clipboard_get(chat_id, clipboard_key)
        if resolved is None:
            return {"success": False, "error": f"Clipboard key '{clipboard_key}' not found."}
        new_content = resolved

    try:
        if expected_version is not None:
            expected_version = int(expected_version)
    except (ValueError, TypeError):
        return {"success": False, "error": f"expected_version must be an integer, got {expected_version}"}

    try:
        if start_line is not None:
            start_line = int(start_line)
        if end_line is not None:
            end_line = int(end_line)
    except (ValueError, TypeError):
        return {"success": False, "error": f"start_line and end_line must be integers, got {start_line} / {end_line}"}

    edits = [{
        "target_text": target_text,
        "new_content": new_content,
        "start_line": start_line,
        "end_line": end_line,
        "allow_multiple": allow_multiple
    }]

    try:
        file_system_meta = resolve_path_to_fs_file(chat_id, path)
    except FileNotFoundError as e:
        return {"success": False, "error": str(e)}
        
    id = file_system_meta['id']
    actual_chat_id = file_system_meta.get('chat_id')
    actual_workspace_id = file_system_meta.get('workspace_id')
    
    if id.startswith("disk:"):
        try:
            _, _, physical_path = resolve_owner_and_physical_path(chat_id, path, workspace_id=actual_workspace_id)
            if os.path.exists(physical_path) and os.path.isfile(physical_path):
                if is_binary_file(physical_path):
                    return {"success": False, "error": "Cannot edit binary files."}
                async with aiofiles.open(physical_path, mode='r', encoding='utf-8', errors='replace') as f:
                    disk_content = await f.read()
            else:
                disk_content = ""
            create_res = await create_fs_file(
                chat_id=chat_id,
                path=path,
                content=disk_content,
                workspace_id=actual_workspace_id,
                author="ai"
            )
            if not create_res.get("success"):
                return {"success": False, "error": f"Failed to initialize file record in database: {create_res.get('error')}"}
            file_system_meta = resolve_path_to_fs_file(chat_id, path, workspace_id=actual_workspace_id)
            id = file_system_meta['id']
            actual_chat_id = file_system_meta.get('chat_id')
            actual_workspace_id = file_system_meta.get('workspace_id')
            file_system_content = disk_content
            expected_version = file_system_meta['current_version']
        except Exception as e:
            return {"success": False, "error": f"Failed to upgrade disk file to VFS: {e}"}
    else:
        file_system_content = await get_fs_file_content(id, chat_id=actual_chat_id, workspace_id=actual_workspace_id)

    if expected_version != file_system_meta['current_version']:
        return {"success": False, "error": f"Write rejected. Expected version {expected_version}, but current is {file_system_meta['current_version']}."}

    lines = file_system_content.split('\n')
    original_lines = list(lines)
    
    cumulative_delta = 0
    edit_results = []

    for i, edit in enumerate(edits):
        target_text = edit.get("target_text")
        new_content = edit.get("new_content")
        s_line = edit.get("start_line")
        e_line = edit.get("end_line")
        allow_multiple = edit.get("allow_multiple", False)

        # Adjust bounds by cumulative delta
        adj_s_line = s_line + cumulative_delta if s_line is not None else None
        adj_e_line = e_line + cumulative_delta if e_line is not None else None

        start_idx = max(0, adj_s_line - 1) if adj_s_line is not None else 0
        end_idx = min(len(lines), adj_e_line) if adj_e_line is not None else len(lines)
        
        if adj_s_line is not None and adj_e_line is not None and start_idx > end_idx:
            edit_results.append({
                "edit_index": i, "status": "failed",
                "error": f"Adjusted bounds {adj_s_line}-{adj_e_line} are invalid."
            })
            break

        # 2. Execution Phase
        try:
            search_zone = '\n'.join(lines[start_idx:end_idx])
            
            if allow_multiple:
                if target_text not in search_zone:
                    raise MatchNotFoundError()
                new_search_zone = search_zone.replace(target_text, new_content)
            else:
                matched_target = _find_exact_match('\n'.join(lines), target_text, adj_s_line, adj_e_line)
                new_search_zone = search_zone.replace(matched_target, new_content)

            new_lines_from_zone = new_search_zone.split('\n') if new_search_zone else []
            old_zone_line_count = end_idx - start_idx
            lines = lines[:start_idx] + new_lines_from_zone + lines[end_idx:]
            cumulative_delta += (len(new_lines_from_zone) - old_zone_line_count)

            edit_results.append({"edit_index": i, "status": "applied"})

        except Exception as e:
            error_msg = str(e) or "Unknown error"
            hint = None
            if isinstance(e, MatchNotFoundError):
                from .fuzzy_matcher import _get_fuzzy_hint
                hint = _get_fuzzy_hint('\n'.join(lines), target_text, adj_s_line, adj_e_line)
                error_msg = "target_text not found in the specified bounds."
            elif isinstance(e, MultipleMatchesError):
                error_msg = "target_text found multiple times."
            
            res = {"edit_index": i, "status": "failed", "error": error_msg}
            if hint: res["hint_actual_content"] = hint
            edit_results.append(res)
            break

    return await _finalize_edits(actual_chat_id, id, actual_workspace_id, expected_version, original_lines, lines, edit_results)


async def replace_fs_lines(
    chat_id: str,
    path: str,
    expected_version: int,
    start_line: int,
    end_line: int,
    new_content: str = "",
    clipboard_key: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    if clipboard_key:
        resolved = db.clipboard_get(chat_id, clipboard_key)
        if resolved is None:
            return {"success": False, "error": f"Clipboard key '{clipboard_key}' not found."}
        new_content = resolved

    try:
        if expected_version is not None:
            expected_version = int(expected_version)
    except (ValueError, TypeError):
        return {"success": False, "error": f"expected_version must be an integer, got {expected_version}"}

    try:
        if start_line is not None:
            start_line = int(start_line)
        if end_line is not None:
            end_line = int(end_line)
    except (ValueError, TypeError):
        return {"success": False, "error": f"start_line and end_line must be integers, got {start_line} / {end_line}"}

    edits = [{
        "start_line": start_line,
        "end_line": end_line,
        "new_content": new_content
    }]

    try:
        file_system_meta = resolve_path_to_fs_file(chat_id, path)
    except FileNotFoundError as e:
        return {"success": False, "error": str(e)}

    id = file_system_meta['id']
    actual_chat_id = file_system_meta.get('chat_id')
    actual_workspace_id = file_system_meta.get('workspace_id')

    if id.startswith("disk:"):
        try:
            _, _, physical_path = resolve_owner_and_physical_path(chat_id, path, workspace_id=actual_workspace_id)
            if os.path.exists(physical_path) and os.path.isfile(physical_path):
                if is_binary_file(physical_path):
                    return {"success": False, "error": "Cannot edit binary files."}
                async with aiofiles.open(physical_path, mode='r', encoding='utf-8', errors='replace') as f:
                    disk_content = await f.read()
            else:
                disk_content = ""
            create_res = await create_fs_file(
                chat_id=chat_id,
                path=path,
                content=disk_content,
                workspace_id=actual_workspace_id,
                author="ai"
            )
            if not create_res.get("success"):
                return {"success": False, "error": f"Failed to initialize file record in database: {create_res.get('error')}"}
            file_system_meta = resolve_path_to_fs_file(chat_id, path, workspace_id=actual_workspace_id)
            id = file_system_meta['id']
            actual_chat_id = file_system_meta.get('chat_id')
            actual_workspace_id = file_system_meta.get('workspace_id')
            file_system_content = disk_content
            expected_version = file_system_meta['current_version']
        except Exception as e:
            return {"success": False, "error": f"Failed to upgrade disk file to VFS: {e}"}
    else:
        file_system_content = await get_fs_file_content(id, chat_id=actual_chat_id, workspace_id=actual_workspace_id)

    if expected_version != file_system_meta['current_version']:
        return {"success": False, "error": f"Write rejected. Expected version {expected_version}, but current is {file_system_meta['current_version']}."}

    lines = file_system_content.split('\n')
    original_lines = list(lines)
    
    cumulative_delta = 0
    edit_results = []

    for i, edit in enumerate(edits):
        new_content = edit.get("new_content")
        s_line = edit.get("start_line")
        e_line = edit.get("end_line")

        try:
            if s_line is not None:
                s_line = int(s_line)
            if e_line is not None:
                e_line = int(e_line)
        except (ValueError, TypeError):
            edit_results.append({
                "edit_index": i, "status": "failed",
                "error": f"start_line and end_line must be integers, got {s_line} / {e_line}"
            })
            break

        # Adjust bounds by cumulative delta
        adj_s_line = s_line + cumulative_delta if s_line is not None else None
        adj_e_line = e_line + cumulative_delta if e_line is not None else None

        start_idx = max(0, adj_s_line - 1) if adj_s_line is not None else 0
        end_idx = min(len(lines), adj_e_line) if adj_e_line is not None else len(lines)
        
        if adj_s_line is not None and adj_e_line is not None and start_idx > end_idx:
            edit_results.append({
                "edit_index": i, "status": "failed",
                "error": f"Adjusted bounds {adj_s_line}-{adj_e_line} are invalid."
            })
            break

        # 2. Execution Phase
        try:
            new_lines = new_content.split('\n') if new_content else []
            old_zone_line_count = end_idx - start_idx
            lines = lines[:start_idx] + new_lines + lines[end_idx:]
            cumulative_delta += (len(new_lines) - old_zone_line_count)

            edit_results.append({"edit_index": i, "status": "applied"})

        except Exception as e:
            error_msg = str(e) or "Unknown error"
            edit_results.append({"edit_index": i, "status": "failed", "error": error_msg})
            break

    return await _finalize_edits(actual_chat_id, id, actual_workspace_id, expected_version, original_lines, lines, edit_results)


async def create_directory_tool(chat_id: Optional[str], path: str, **kwargs) -> Dict[str, Any]:
    """Tool implementation to create an empty directory."""
    try:
        from .utils import sanitize_path
        safe_path = sanitize_path(path)
        workspace_id = kwargs.get('workspace_id')
        
        target_chat_id, target_workspace_id, physical_dir = resolve_owner_and_physical_path(chat_id, path, workspace_id=workspace_id)
        
        if os.path.exists(physical_dir):
            return {"success": False, "error": f"Directory already exists at path: {safe_path}"}
            
        os.makedirs(physical_dir, exist_ok=True)
        return {"success": True, "action": "create_dir", "path": safe_path}
    except Exception as e:
        logger.error(f"Failed to create directory {path}: {e}")
        return {"success": False, "error": str(e)}

async def delete_directory_tool(chat_id: Optional[str], path: str, **kwargs) -> Dict[str, Any]:
    """Tool implementation to delete a directory."""
    try:
        from .utils import sanitize_path
        import shutil
        workspace_id = kwargs.get('workspace_id')
        
        safe_path = sanitize_path(path)
        if not safe_path:
            return {"success": False, "error": "Cannot delete the root directory."}
            
        if safe_path == "workspace" or safe_path == "workspace/":
            return {"success": False, "error": "Cannot delete the virtual 'workspace' directory root."}
            
        target_chat_id, target_workspace_id, physical_dir = resolve_owner_and_physical_path(chat_id, path, workspace_id=workspace_id)
        
        if not os.path.exists(physical_dir) or not os.path.isdir(physical_dir):
            return {"success": False, "error": f"Directory not found: {safe_path}"}
            
        # Check if there are tracked file_systems inside this path
        if target_workspace_id:
            file_systems = db.get_owner_file_systems(workspace_id=target_workspace_id)
            lookup_prefix = safe_path
            if lookup_prefix.startswith("workspace/"):
                lookup_prefix = lookup_prefix[len("workspace/"):].strip("/")
            lookup_path = lookup_prefix
            lookup_prefix = lookup_prefix + '/'
        else:
            if not chat_id:
                return {"success": False, "error": "chat_id is required for local chat file systems."}
            file_systems = db.get_chat_file_systems(chat_id)
            lookup_prefix = safe_path + '/'
            lookup_path = safe_path
            
        for c in file_systems:
            if c['filename'].startswith(lookup_prefix) or c['filename'] == lookup_path:
                return {"success": False, "error": "Directory is not empty (contains tracked files). Delete the files first."}
                
        # If we reach here, it's safe to physically delete (even if it contains empty subfolders)
        shutil.rmtree(physical_dir)
        return {"success": True, "path": safe_path}
    except Exception as e:
        logger.error(f"Failed to delete directory {path}: {e}")
        return {"success": False, "error": str(e)}

async def move_fs_file_tool(chat_id: str, source_path: str, destination_path: str, **kwargs) -> Dict[str, Any]:
    """Tool implementation to move or rename a file_system file."""
    return update_file_system_metadata(chat_id, source_path, new_path=destination_path)

async def patch_file_system(chat_id: str, id: str, **kwargs) -> Dict[str, Any]:
    """
    Tool implementation to update file_system metadata or content by ID.
    Used by agents for state management (e.g. locking a research plan).
    """
    file_system_id = id
    workspace_id = get_workspace_for_chat(chat_id)
    file_system_meta = db.get_file_system_meta(file_system_id, chat_id=chat_id, workspace_id=workspace_id)
    if not file_system_meta:
        return {"success": False, "error": f"FileSystem not found with ID: {file_system_id}"}

    actual_chat_id = file_system_meta.get('chat_id')
    actual_workspace_id = file_system_meta.get('workspace_id')

    # 1. Update content if provided
    new_content = kwargs.get('content')
    if new_content is not None:
        await update_fs_file_content(
            file_system_id=file_system_id,
            chat_id=actual_chat_id,
            workspace_id=actual_workspace_id,
            new_content=new_content,
            author="system",
            version_comment=kwargs.get('comment', 'Updated via patch_file_system')
        )

    # 2. Update metadata (title, folder, type, etc.)
    # We use a copy of kwargs to avoid modifying the original for other tools
    meta_updates = {k: v for k, v in kwargs.items() if k not in ['id', 'content', 'comment']}
    
    if meta_updates:
        # If title or folder changes, we need to handle physical rename
        new_title = meta_updates.get('title')
        new_folder = meta_updates.get('folder')
        
        if new_title or new_folder:
            current_path = file_system_meta['filename']
            if actual_workspace_id:
                current_path = "workspace/" + current_path
            
            # Use update_file_system_metadata to handle the heavy lifting of renaming
            # Note: new_path logic in update_file_system_metadata will use new_title/new_folder
            update_file_system_metadata(chat_id=chat_id, current_path=current_path, **meta_updates)
        else:
            # Just standard metadata update
            db.save_file_system_meta(file_system_id, chat_id=actual_chat_id, workspace_id=actual_workspace_id, **meta_updates)

    return {
        "success": True, 
        "action": "patch", 
        "file_system_id": file_system_id,
        "path": file_system_meta['filename']
    }

async def delete_file_system_tool(chat_id: str, path: str, **kwargs) -> Dict[str, Any]:
    """Tool implementation to delete a file_system file."""
    try:
        file_system_meta = resolve_path_to_fs_file(chat_id, path)
    except FileNotFoundError as e:
        return {"success": False, "error": str(e)}

    # Call the existing delete logic
    return await delete_fs_file(file_system_meta['id'], chat_id=file_system_meta.get('chat_id'), workspace_id=file_system_meta.get('workspace_id'))


