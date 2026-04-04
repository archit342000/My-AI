"""
Centralized Canvas Management Module

This module provides a unified interface for canvas operations across all agents
(normal chats and research mode). It handles:
- Canvas CRUD operations
- Version management
- Folder organization
- Export functionality
- Permission management
"""

import os
import re
import json
import time
import sqlite3
from typing import Optional, Dict, List, Tuple, Any
from backend.config import DATA_DIR
from backend.logger import log_event
from backend.db_wrapper import db, DB_PATH
from backend.storage import lock_manager, execute_with_retry, sync_canvas_search_index, delete_canvas_versions_after
from backend.canvas_channel import CanvasChannelManager
import fitz # PyMuPDF

CANVASES_DIR = os.path.join(DATA_DIR, "canvases")


def ensure_canvases_dir():
    """Ensure the canvases directory exists."""
    os.makedirs(CANVASES_DIR, exist_ok=True)


async def generate_canvas_id(chat_id: str, canvas_type: str = "custom") -> str:
    """
    Generate a unique canvas ID using the atomic SQLite counter-based system.
    """
    counter = db.get_next_canvas_counter(chat_id)
    return str(counter)


def sanitize_filename(text: str) -> str:
    """
    Sanitize text for use in filenames.

    Args:
        text: The text to sanitize

    Returns:
        Sanitized string safe for filenames
    """
    # Remove or replace invalid characters
    safe = re.sub(r'[^\w\s\-]', '_', str(text))
    # Replace multiple underscores with single
    safe = re.sub(r'_+', '_', safe)
    # Remove leading/trailing underscores
    safe = safe.strip('_')
    return safe


def generate_canvas_filename(chat_id: str, canvas_id: str) -> str:
    """Generate a consistent, sanitized filename for a canvas file.

    Args:
        chat_id: The chat identifier
        canvas_id: The canvas identifier

    Returns:
        Sanitized filename in format {chat_id}_{canvas_id}.md
    """
    safe_chat_id = re.sub(r'[^a-zA-Z0-9_\-]', '', str(chat_id))
    safe_canvas_id = sanitize_filename(canvas_id)
    return f"{safe_chat_id}_{safe_canvas_id}.md"


async def create_canvas(
    chat_id: str,
    canvas_id: Optional[str] = None,
    title: str = "Untitled Canvas",
    content: str = "",
    folder: str = "",
    tags: Optional[List[str]] = None,
    author: str = "system",
    version_comment: str = "Initial version"
) -> Dict[str, Any]:
    """
    Create a new canvas.

    Args:
        chat_id: The chat identifier
        canvas_id: Optional custom canvas ID (auto-generated if not provided)
        title: Display title for the canvas
        content: Initial markdown content
        folder: Folder path for organization
        tags: List of tags for organization
        author: Author of the canvas
        version_comment: Comment for the initial version

    Returns:
        Dictionary with canvas details including ID
    """
    channel = CanvasChannelManager.get_channel(chat_id)
    # Map author role to channel source ('ai' or 'user')
    source = "ai" if author == "system" else "user"
    
    await channel.acquire(source)
    try:
        ensure_canvases_dir()

        if canvas_id is None:
            canvas_id = await generate_canvas_id(chat_id, "custom")

        filename = generate_canvas_filename(chat_id, canvas_id)
        filepath = os.path.join(CANVASES_DIR, filename)

        # Write initial content
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        # Ensure chat exists before creating canvas to avoid FK failure
        db.ensure_chat_exists(chat_id)

        # Save metadata and create initial version in a single transaction
        # to satisfy foreign key constraints
        db.create_canvas_with_version(
            canvas_id=canvas_id,
            chat_id=chat_id,
            title=title,
            filename=filename,
            content=content,
            author=author,
            comment=version_comment,
            folder=folder,
            canvas_type="custom",
            tags=tags
        )
        version_id = 1  # We know it's version 1

        # Update chat's canvas_mode flag to enable canvas mode for this chat
        db.update_chat_canvas_mode(chat_id, True)

        # Sync to FTS5 search index (non-blocking - don't fail on error)
        try:
            sync_canvas_search_index(canvas_id, chat_id)
        except Exception as e:
            # Log but don't fail canvas creation on FTS5 sync error
            import logging
            logging.error(f"Failed to sync FTS5 index for canvas {canvas_id}: {e}")

        return {
            "success": True,
            "canvas_id": canvas_id,
            "title": title,
            "filename": filename,
            "filepath": filepath,
            "version_id": version_id,
            "timestamp": time.time()
        }
    finally:
        await channel.release()


async def get_canvas_content(canvas_id: str, chat_id: str) -> Optional[str]:
    """
    Get canvas content by ID.

    Args:
        canvas_id: The canvas identifier
        chat_id: The chat identifier

    Returns:
        The markdown content or None if not found
    """
    return db.get_canvas_content_by_id(canvas_id, chat_id)


async def update_canvas_content(
    canvas_id: str,
    chat_id: str,
    new_content: str,
    author: str = "user",
    version_comment: str = "Updated by user"
) -> Dict[str, Any]:
    """
    Update canvas content.

    Args:
        canvas_id: The canvas identifier
        chat_id: The chat identifier
        new_content: The new markdown content
        author: Author of the update
        version_comment: Comment for this version

    Returns:
        Dictionary with update details
    """
    channel = CanvasChannelManager.get_channel(chat_id)
    source = "ai" if author == "system" else "user"

    await channel.acquire(source)
    try:
        # Get current canvas
        canvas_meta = db.get_canvas_meta(canvas_id, chat_id)
        if not canvas_meta:
            return {"success": False, "error": "Canvas not found"}

        filepath = os.path.join(CANVASES_DIR, canvas_meta['filename'])

        # Save new content
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)

        # Create version record
        versions = db.get_canvas_versions(canvas_id, chat_id)
        next_version = (versions[0]['version_number'] if versions else 0) + 1
        db.save_canvas_version(canvas_id=canvas_id, chat_id=chat_id, version_number=next_version, content=new_content, author=author, comment=version_comment)
        version_id = next_version

        # Refresh metadata timestamp and current_version — pass canvas_id to target the correct row
        db.save_canvas(canvas_id=canvas_id, chat_id=chat_id, title=canvas_meta['title'], filename=canvas_meta['filename'], canvas_type="custom", current_version=version_id)

        # Sync to FTS5 search index (non-blocking - don't fail on error)
        try:
            sync_canvas_search_index(canvas_id, chat_id)
        except Exception as e:
            # Log but don't fail update on FTS5 sync error
            import logging
            logging.error(f"Failed to sync FTS5 index for canvas {canvas_id}: {e}")

        return {
            "success": True,
            "canvas_id": canvas_id,
            "version_id": version_id,
            "timestamp": time.time(),
            "content": new_content
        }
    finally:
        await channel.release()


# Removed _get_next_counter (now handled by get_next_canvas_counter in storage.py)


# Removed _create_version_record (now handled by save_canvas_version in storage.py)


def _extract_canvas_type(canvas_id: str) -> str:
    """
    Extract the type of canvas from its ID.

    Args:
        canvas_id: The canvas identifier

    Returns:
        Type string (plan, research, custom, section, etc.)
    """
    if canvas_id.startswith("plan_"):
        return "plan"
    elif canvas_id.startswith("research_"):
        return "research"
    elif canvas_id.startswith("section_"):
        return "section"
    else:
        return "custom"


def _apply_section_deletion(existing_content: str, target_section: str) -> Tuple[str, bool]:
    """
    Remove a section identified by target_section heading.

    Returns:
        (deleted_content, was_removed): was_removed is False when the heading
        was not found and the content was returned unchanged.
    """
    lines = existing_content.split('\n')
    result = []
    target_level = None
    in_target = False
    was_removed = False

    for line in lines:
        heading_match = re.match(r'^(#{1,6})\s+(.*)', line)
        if heading_match:
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()

            if heading_text == target_section.strip():
                # Start of target section - skip from here
                target_level = level
                in_target = True
                was_removed = True
                continue
            elif in_target and level <= target_level:
                # Reached next section of equal or higher level — stop skipping
                in_target = False

        if not in_target:
            result.append(line)

    return '\n'.join(result), was_removed


async def _read_canvas_section_only(
    canvas_id: str,
    chat_id: str,
    target_section: str
) -> Tuple[str, bool]:
    """
    Read only a specific section of a canvas.

    Returns:
        (section_content, was_found)
    """
    existing_content = await get_canvas_content(canvas_id, chat_id) or ""
    lines = existing_content.split('\n')

    section_lines = []
    target_level = None
    in_target = False
    found = False

    for line in lines:
        heading_match = re.match(r'^(#{1,6})\s+(.*)', line)
        if heading_match:
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()

            if heading_text == target_section.strip():
                in_target = True
                target_level = level
                found = True
                section_lines.append(line)
                continue
            elif in_target and level <= target_level:
                in_target = False

        if in_target:
            section_lines.append(line)

    return '\n'.join(section_lines), found


def _apply_canvas_patch(existing_content: str, target_section: str, new_content: str) -> Tuple[str, bool]:
    """
    Replace a section identified by target_section heading with new_content.

    Returns:
        (patched_content, was_replaced): was_replaced is False when the heading
        was not found and the content was silently appended instead.
    """
    lines = existing_content.split('\n')
    result = []
    target_level = None
    in_target = False
    replaced = False

    for line in lines:
        heading_match = re.match(r'^(#{1,6})\s+(.*)', line)
        if heading_match:
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()

            if heading_text == target_section.strip():
                # Start of target section
                target_level = level
                in_target = True
                replaced = True
                result.append(new_content)
                continue
            elif in_target and level <= target_level:
                # Reached next section of equal or higher level — stop replacing
                in_target = False

        if not in_target:
            result.append(line)

    return '\n'.join(result), replaced


async def append_to_canvas(
    canvas_id: str,
    chat_id: str,
    content_to_append: str,
    author: str = "system",
    version_comment: str = "Content appended"
) -> Dict[str, Any]:
    """
    Append content to an existing canvas.

    Args:
        canvas_id: The canvas identifier
        chat_id: The chat identifier
        content_to_append: Content to add to the end
        author: Author of the append operation
        version_comment: Comment for this version

    Returns:
        Dictionary with append details
    """
    # Get current content
    existing_content = await get_canvas_content(canvas_id, chat_id) or ""
    new_content = existing_content + "\n\n" + content_to_append

    return await update_canvas_content(
        canvas_id,
        chat_id,
        new_content,
        author=author,
        version_comment=version_comment
    )


async def patch_canvas_section(
    canvas_id: str,
    chat_id: str,
    target_section: str,
    new_content: str,
    author: str = "system",
    version_comment: str = "Section updated"
) -> Dict[str, Any]:
    """
    Patch a specific section of a canvas.

    Args:
        canvas_id: The canvas identifier
        chat_id: The chat identifier
        target_section: The heading text to find and replace
        new_content: The new content for the section
        author: Author of the patch
        version_comment: Comment for this version

    Returns:
        Dictionary with patch details
    """
    # Get current content
    existing_content = await get_canvas_content(canvas_id, chat_id) or ""
    patched_content, was_replaced = _apply_canvas_patch(existing_content, target_section, new_content)

    # Update the canvas
    result = await update_canvas_content(
        canvas_id,
        chat_id,
        patched_content,
        author=author,
        version_comment=version_comment
    )

    result['section_replaced'] = was_replaced
    return result


async def delete_section(
    canvas_id: str,
    chat_id: str,
    target_section: str,
    author: str = "system",
    version_comment: str = "Section deleted"
) -> Dict[str, Any]:
    """
    Delete a specific section from a canvas.

    Args:
        canvas_id: The canvas identifier
        chat_id: The chat identifier
        target_section: The heading text to find and delete
        author: Author of the delete operation
        version_comment: Comment for this version

    Returns:
        Dictionary with delete details
    """
    # Get current content
    existing_content = await get_canvas_content(canvas_id, chat_id) or ""
    deleted_content, was_removed = _apply_section_deletion(existing_content, target_section)

    # Update the canvas only if section was found
    if was_removed:
        result = await update_canvas_content(
            canvas_id,
            chat_id,
            deleted_content,
            author=author,
            version_comment=version_comment
        )
        result['section_removed'] = True
    else:
        result = {
            "success": True,
            "canvas_id": canvas_id,
            "section_removed": False,
            "message": f"Section '{target_section}' not found"
        }

    return result


def validate_patch_action(action: str, target_section: Optional[str]) -> Tuple[bool, str]:
    """
    Validate that target_section is provided for patch and delete_section actions.

    Args:
        action: The action type
        target_section: The target section value

    Returns:
        (is_valid, error_message)
    """
    if action in ("patch", "delete_section") and not target_section:
        return False, f"target_section is required for {action} action"
    return True, ""


async def read_canvas_section(
    canvas_id: str,
    chat_id: str,
    target_section: Optional[str] = None
) -> Dict[str, Any]:
    """
    Read a canvas or specific section.

    Args:
        canvas_id: The canvas identifier
        chat_id: The chat identifier
        target_section: Optional section name to read

    Returns:
        Dictionary with content details
    """
    if target_section:
        content, found = await _read_canvas_section_only(canvas_id, chat_id, target_section)
        return {
            "success": True,
            "canvas_id": canvas_id,
            "section_read": target_section,
            "content": content,
            "section_found": found,
            "char_count": len(content) if content else 0
        }
    else:
        content = await get_canvas_content(canvas_id, chat_id) or ""
        return {
            "success": True,
            "canvas_id": canvas_id,
            "section_read": "full",
            "content": content,
            "section_found": True,
            "char_count": len(content)
        }


async def delete_canvas(canvas_id: str, chat_id: str) -> Dict[str, Any]:
    """
    Delete a canvas, its versions, and its file. Protected by channel locking and DB table locks.
    """
    channel = CanvasChannelManager.get_channel(chat_id)
    
    await channel.acquire("user")
    try:
        canvas_meta = db.get_canvas_meta(canvas_id, chat_id)
        if not canvas_meta:
            return {"success": False, "error": "Canvas not found"}

        # 1. Delete file from disk
        filename = canvas_meta['filename']
        filepath = os.path.join(CANVASES_DIR, filename)
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except OSError as e:
            log_event("canvas_file_delete_error", {"canvas_id": canvas_id, "error": str(e)})

        # 2. Delete from DB (metadata and versions)
        # Note: we use comprehensive deletion if possible, but delete_canvas_meta 
        # only deletes the meta. We need to delete versions too.
        # Actually, let's just use a manual block wrapped in execute_with_retry if storage doesn't have it.
        # Wait, storage.py now has write_lock for canvas_versions.
        
        def _db_delete():
            conn = sqlite3.connect(DB_PATH, timeout=10.0)
            c = conn.cursor()
            c.execute("DELETE FROM canvas_versions WHERE canvas_id = ? AND chat_id = ?", (canvas_id, chat_id))
            c.execute("DELETE FROM canvas_permissions WHERE canvas_id = ? AND chat_id = ?", (canvas_id, chat_id))
            conn.commit()
            conn.close()
            
        from backend.storage import lock_manager
        with lock_manager.write_lock("canvas_versions"):
            execute_with_retry(_db_delete)
            
        db.delete_canvas_meta(canvas_id, chat_id)

        # 3. Sync search index (remove)
        try:
            from backend.storage import sync_canvas_search_index
            sync_canvas_search_index(canvas_id, chat_id) # The function should handle deletion if content is None
        except:
            pass

        return {"success": True, "canvas_id": canvas_id}
    finally:
        await channel.release()


def get_unique_folders(chat_id: str) -> List[str]:
    """
    Get unique folder names used for canvases in a chat.

    Args:
        chat_id: The chat identifier

    Returns:
        List of unique folder names
    """
    canvases = db.get_chat_canvases(chat_id)
    folders = set()
    for canvas in canvases:
        # Check explicit folder column first
        if canvas.get('folder'):
            folders.add(canvas['folder'])
        # Fallback: extract from title if formatted as folder/title
        elif '/' in canvas['title']:
            folders.add(canvas['title'].split('/')[0])
    
    return sorted(list(folders))


async def get_chat_canvases_with_details(chat_id: str, include_content: bool = False) -> List[Dict[str, Any]]:
    """
    Get all canvases for a chat with additional details.

    Args:
        chat_id: The chat identifier
        include_content: Whether to include content (expensive for large canvases)

    Returns:
        List of canvas dictionaries with metadata
    """
    canvases = db.get_chat_canvases(chat_id)

    results = []
    for canvas in canvases:
        result = {
            "id": canvas['id'],
            "title": canvas['title'],
            "filename": canvas['filename'],
            "timestamp": canvas['timestamp'],
        }

        content = await get_canvas_content(canvas['id'], chat_id) if include_content or True else ""

        if include_content:
            result["content"] = content

        # Extract type from canvas_id
        result["type"] = _extract_canvas_type(canvas['id'])

        # Rule 16: Canvas inventory uses 200 character preview
        result["preview"] = (content or "")[:200]

        # Extract folder if present in title
        result["folder"] = ""
        if '/' in canvas['title']:
            result["folder"] = canvas['title'].split('/')[0]

        results.append(result)

    return results


async def export_canvas_markdown(canvas_id: str, chat_id: str) -> Tuple[Optional[str], str]:
    """
    Export canvas as markdown.

    Args:
        canvas_id: The canvas identifier
        chat_id: The chat identifier

    Returns:
        Tuple of (content, filename) or (None, error_message)
    """
    content = await get_canvas_content(canvas_id, chat_id)
    if content is None:
        return None, "Canvas not found"

    canvas_meta = db.get_canvas_meta(canvas_id, chat_id)
    filename = f"{canvas_meta['title'].replace(' ', '_')}.md" if canvas_meta else f"canvas_{canvas_id}.md"

    return content, filename


async def export_canvas_html(canvas_id: str, chat_id: str) -> Tuple[Optional[str], str]:
    """
    Export canvas as HTML.

    Args:
        canvas_id: The canvas identifier
        chat_id: The chat identifier

    Returns:
        Tuple of (html_content, filename) or (None, error_message)
    """
    import markdown

    content = await get_canvas_content(canvas_id, chat_id)
    if content is None:
        return None, "Canvas not found"

    # Convert markdown to HTML
    html_content = markdown.markdown(content, output_format='html5')

    canvas_meta = db.get_canvas_meta(canvas_id, chat_id)
    title = canvas_meta['title'] if canvas_meta else f"Canvas_{canvas_id}"

    # Create HTML template
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 2rem; line-height: 1.6; }}
        h1, h2, h3 {{ border-bottom: 1px solid #eee; padding-bottom: 0.5rem; }}
        pre {{ background: #f5f5f5; padding: 1rem; border-radius: 4px; overflow-x: auto; }}
        code {{ font-family: 'Courier New', monospace; background: #f5f5f5; padding: 0.2rem 0.4rem; border-radius: 2px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
        th, td {{ border: 1px solid #ddd; padding: 0.5rem; text-align: left; }}
        th {{ background: #f5f5f5; }}
        img {{ max-width: 100%; }}
    </style>
</head>
<body>
{html_content}
</body>
</html>"""

    filename = f"{title.replace(' ', '_')}.html"

    return html_template, filename


async def export_canvas_pdf(canvas_id: str, chat_id: str) -> Tuple[Optional[bytes], str]:
    """
    Export canvas as PDF.

    Args:
        canvas_id: The canvas identifier
        chat_id: The chat identifier

    Returns:
        Tuple of (pdf_bytes, filename) or (None, error_message)
    """
    html_content, _ = await export_canvas_html(canvas_id, chat_id)
    if html_content is None:
        return None, "Canvas not found"

    try:
        # Use PyMuPDF's Story class for robust HTML-to-PDF rendering (version 1.25.0+)
        # This handles cross-platform wheels and supports complex layout/multi-page
        doc = fitz.open()
        story = fitz.Story(html_content)
        
        # Draw the story across as many pages as needed
        while True:
            page = doc.new_page()
            # 1 inch (72 points) margins
            # Manual inset: x0, y0, x1, y1
            where = fitz.Rect(72, 72, page.rect.width - 72, page.rect.height - 72)
            story.place(where)
            _, finished = story.draw(page)
            if finished:
                break
        
        pdf_bytes = doc.tobytes()
        doc.close()
        
        canvas_meta = db.get_canvas_meta(canvas_id, chat_id)
        filename = f"{canvas_meta['title'].replace(' ', '_')}.pdf" if canvas_meta else f"canvas_{canvas_id}.pdf"
        return pdf_bytes, filename
    except Exception as e:
        log_event("canvas_export_pdf_error", {"canvas_id": canvas_id, "error": str(e)})
        return None, f"PDF generation failed: {str(e)}"


def get_canvas_versions(canvas_id: str, chat_id: str) -> List[Dict[str, Any]]:
    """
    Get version history for a canvas.
    """
    return db.get_canvas_versions(canvas_id, chat_id)


def get_canvas_version(canvas_id: str, chat_id: str, version_number: int) -> Optional[Dict[str, Any]]:
    """
    Get a specific version of a canvas.
    """
    content = db.get_canvas_version_content(canvas_id, chat_id, version_number)
    if content is None:
        return None
    
    # We don't have the full record from get_canvas_version_content, but often content is all that's needed.
    # If full metadata is needed, we'd need a more comprehensive storage function.
    # For now, let's just return a dict with content.
    return {"content": content, "version_number": version_number}


async def restore_canvas_version(canvas_id: str, chat_id: str, version_number: int, author: str = "user") -> Dict[str, Any]:
    """
    Restore a canvas to a previous version and invalidate all future versions.
    """
    content = db.get_canvas_version_content(canvas_id, chat_id, version_number)
    if content is None:
        return {"success": False, "error": f"Version {version_number} not found"}

    # 1. Update the physical file
    canvas_meta = db.get_canvas_meta(canvas_id, chat_id)
    if not canvas_meta:
        return {"success": False, "error": "Canvas not found"}
    filepath = os.path.join(CANVASES_DIR, canvas_meta['filename'])
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    # 2. Invalidate future versions (truncate)
    delete_canvas_versions_after(canvas_id, chat_id, version_number)

    # 3. Refresh metadata and current_version
    db.save_canvas(canvas_id=canvas_id, chat_id=chat_id, title=canvas_meta['title'], filename=canvas_meta['filename'], canvas_type="custom", current_version=version_number)

    # 4. Refresh search index
    try:
        from backend.storage import sync_canvas_search_index
        sync_canvas_search_index(canvas_id, chat_id)
    except:
        pass

    return {
        "success": True, 
        "canvas_id": canvas_id, 
        "version_number": version_number,
        "content": content
    }

async def navigate_canvas_version(canvas_id: str, chat_id: str, version_number: int) -> Dict[str, Any]:
    """
    Navigate to a specific version of a canvas by updating the file content,
    but without creating a new version record.

    Args:
        canvas_id: The canvas identifier
        chat_id: The chat identifier
        version_number: The version number to navigate to

    Returns:
        Dictionary with navigation result
    """
    version = get_canvas_version(canvas_id, chat_id, version_number)
    if not version:
        return {"success": False, "error": f"Version {version_number} not found"}

    channel = CanvasChannelManager.get_channel(chat_id)
    # Navigation is user-initiated, so we use 'user' role for the lock
    await channel.acquire("user")
    try:
        canvas_meta = db.get_canvas_meta(canvas_id, chat_id)
        if not canvas_meta:
            return {"success": False, "error": "Canvas not found"}

        filepath = os.path.join(CANVASES_DIR, canvas_meta['filename'])
        
        # Overwrite the physical file with the selected version's content
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(version['content'])

        # Refresh metadata timestamp and current_version to reflect the state change
        db.save_canvas(canvas_id=canvas_id, chat_id=chat_id, title=canvas_meta['title'], filename=canvas_meta['filename'], canvas_type="custom", current_version=version_number)

        return {
            "success": True,
            "canvas_id": canvas_id,
            "version_number": version_number,
            "content": version['content']
        }
    finally:
        await channel.release()


def get_canvas_diff(canvas_id: str, chat_id: str, version_a: int, version_b: int) -> Dict[str, Any]:
    """
    Get the diff between two versions of a canvas.

    Args:
        canvas_id: The canvas identifier
        chat_id: The chat identifier
        version_a: First version number
        version_b: Second version number

    Returns:
        Dictionary with diff result
    """
    va = get_canvas_version(canvas_id, chat_id, version_a)
    vb = get_canvas_version(canvas_id, chat_id, version_b)

    if va is None:
        return {"success": False, "error": f"Version {version_a} not found"}
    if vb is None:
        return {"success": False, "error": f"Version {version_b} not found"}

    content1 = va['content']
    content2 = vb['content']

    # Simple diff: show lines that changed
    lines1 = content1.split('\n')
    lines2 = content2.split('\n')

    added = []
    removed = []

    # Create a simple line-by-line diff
    max_lines = max(len(lines1), len(lines2))
    for i in range(max_lines):
        line1 = lines1[i] if i < len(lines1) else ""
        line2 = lines2[i] if i < len(lines2) else ""
        if line1 != line2:
            if line1:
                removed.append(line1)
            if line2:
                added.append(line2)

    return {
        "success": True,
        "canvas_id": canvas_id,
        "from_version": version_a,
        "to_version": version_b,
        "added_lines": added,
        "removed_lines": removed,
        "stats": {
            "lines_added": len(added),
            "lines_removed": len(removed)
        }
    }


# ==============================================================================
# Canvas Collaboration (Shared Access - Single User Mode)
# ==============================================================================

def share_canvas(canvas_id: str, chat_id: str, user_id: str = "any_user", permission: str = "read") -> Dict[str, Any]:
    """
    Grant access to a user for a canvas. Uses retry logic and per-table write locking.
    """
    def _share():
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        c = conn.cursor()

        # Check if permission already exists
        c.execute("SELECT id FROM canvas_permissions WHERE canvas_id = ? AND chat_id = ? AND user_id = ?", (canvas_id, chat_id, user_id))
        row = c.fetchone()

        if row:
            # Update existing permission
            c.execute("""
                UPDATE canvas_permissions SET permission = ?, timestamp = ?
                WHERE canvas_id = ? AND chat_id = ? AND user_id = ?
            """, (permission, time.time(), canvas_id, chat_id, user_id))
        else:
            # Create new permission
            c.execute("""
                INSERT INTO canvas_permissions (canvas_id, chat_id, user_id, permission, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (canvas_id, chat_id, user_id, permission, time.time()))

        conn.commit()
        conn.close()
        return {"success": True, "canvas_id": canvas_id, "user_id": user_id, "permission": permission}

    from backend.storage import lock_manager
    with lock_manager.write_lock("canvas_permissions"):
        return execute_with_retry(_share, max_retries=3)


def unshare_canvas(canvas_id: str, chat_id: str, user_id: str = "any_user") -> Dict[str, Any]:
    """
    Remove access for a user to a canvas. Uses retry logic and per-table write locking.
    """
    def _unshare():
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        c = conn.cursor()
        c.execute("DELETE FROM canvas_permissions WHERE canvas_id = ? AND chat_id = ? AND user_id = ?", (canvas_id, chat_id, user_id))
        conn.commit()
        conn.close()
        return {"success": True, "canvas_id": canvas_id, "user_id": user_id}

    from backend.storage import lock_manager
    with lock_manager.write_lock("canvas_permissions"):
        return execute_with_retry(_unshare, max_retries=3)


def get_shared_users(canvas_id: str, chat_id: str) -> List[Dict[str, Any]]:
    """
    Get list of users who have access to a canvas. Uses execute_with_retry and per-table read locking.
    """
    def _get():
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM canvas_permissions WHERE canvas_id = ? AND chat_id = ?", (canvas_id, chat_id))
        rows = c.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    from backend.storage import lock_manager
    with lock_manager.read_lock("canvas_permissions"):
        return execute_with_retry(_get, max_retries=3)


# Legacy aliases for backward compatibility
get_canvas = get_canvas_content
update_canvas = update_canvas_content

def delete_chat_canvases(chat_id):
    """Delete canvas files for a chat (legacy alias)."""
    return db.delete_chat_canvas_files(chat_id)

delete_chat_canvases = delete_chat_canvases
