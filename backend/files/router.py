from flask import Blueprint, request, jsonify, Response
import logging
import os
import uuid
import mimetypes
from backend import config
from backend.logging import log_event, error_detail
from backend.auth.ownership import claim_chat, require_chat_owner, require_file_owner
from backend.database import db
from backend.rag import RAGProvider
from backend.models import get_embedding_model
from .manager import FileManager

logger = logging.getLogger(__name__)
files_bp = Blueprint('files', __name__)

# Initialize FileManager lazily or on import?
# Better to initialize it when needed or have a getter to ensure RAGManager is ready
def get_file_manager():
    embedding_model = get_embedding_model()
    rag_manager = RAGProvider.get_manager(
        persist_path=config.CHROMA_PATH,
        embedding_model=embedding_model
    )
    return FileManager(rag_manager=rag_manager)

@files_bp.route('/upload', methods=['POST'])
async def upload_file_endpoint():
    """Upload a file and process it."""
    logger.info("[UPLOAD_ENDPOINT] Starting upload")

    chat_id = request.form.get('chat_id')
    logger.debug(f"[UPLOAD_ENDPOINT] chat_id={chat_id}")
    if not chat_id:
        return jsonify({"error": "chat_id is required"}), 400

    # Create the chat for the caller (the file row has a foreign key to it), or refuse another user's chat.
    denied = claim_chat(chat_id)
    if denied:
        return denied

    if 'file' not in request.files:
        logger.error("[UPLOAD_ENDPOINT] No file in request.files")
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    logger.debug(f"[UPLOAD_ENDPOINT] file.filename={file.filename}")
    if file.filename == '':
        logger.error("[UPLOAD_ENDPOINT] Empty filename")
        return jsonify({"error": "No file selected"}), 400

    # Check file size early
    file_content = file.read()
    logger.debug(f"[UPLOAD_ENDPOINT] file.size={len(file_content)} bytes")
    if len(file_content) > config.FILE_UPLOAD_MAX_SIZE:
        return jsonify({"error": f"File too large. Maximum size is {config.FILE_UPLOAD_MAX_SIZE} bytes"}), 400

    # Write temp file early for heuristic testing if needed
    temp_path = os.path.join(config.FILE_STORAGE_PATH, f"temp_{uuid.uuid4().hex}")
    os.makedirs(config.FILE_STORAGE_PATH, exist_ok=True)
    with open(temp_path, 'wb') as f:
        f.write(file_content)

    file_manager = get_file_manager()

    # Validate file type
    mime_type = file.mimetype
    ext = os.path.splitext(file.filename)[1].lower()
    
    from backend.file_types import EXHAUSTIVE_TEXT_EXTENSIONS
    
    # Try exhaustive registry first
    expected_mime = EXHAUSTIVE_TEXT_EXTENSIONS.get(ext)
    
    # Fallback to core expected mimes if not in exhaustive text registry
    if not expected_mime:
        expected_mime = {
            '.pdf': 'application/pdf',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.heic': 'image/heic',
            '.mp4': 'video/mp4',
            '.webm': 'video/webm',
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav'
        }.get(ext)

    if expected_mime:
        mime_type = expected_mime
    elif mime_type not in config.FILE_UPLOAD_ALLOWED_TYPES:
        # Unknown extension/MIME. Use heuristic fallback.
        if file_manager.is_readable_text(temp_path):
            mime_type = 'text/plain' # Generic text assignment
        else:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return jsonify({"error": "Unsupported binary file type or unrecognized extension."}), 400

    try:
        logger.info(f"[UPLOAD_ENDPOINT] Calling file_manager.upload_file_async for {file.filename}")
        metadata = await file_manager.upload_file_async(
            file_path=temp_path,
            chat_id=chat_id,
            original_filename=file.filename
        )

        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)

        if metadata:
            return jsonify({
                "success": True,
                "file_id": metadata.file_id,
                "original_filename": metadata.original_filename,
                "mime_type": metadata.mime_type,
                "file_size": metadata.file_size
            })
        else:
            log_event("files_upload_error", {"error": "no metadata returned for the uploaded file"})
            return jsonify({"error": "Could not read the uploaded file. Try another file."}), 500

    except Exception as e:
        if os.path.exists(temp_path):
            try: os.remove(temp_path)
            except: pass
        logger.error(f"[UPLOAD_ENDPOINT] Exception: {e}", exc_info=True)
        log_event("files_upload_error", {"error": error_detail(e)})
        return jsonify({"error": "Could not upload the file. Try again."}), 500

@files_bp.route('', methods=['GET'])
def list_files_endpoint():
    """List all files for current chat."""
    chat_id = request.args.get('chat_id')
    if not chat_id:
        return jsonify({"error": "chat_id is required"}), 400
    denied = require_chat_owner(chat_id)
    if denied:
        return denied

    file_manager = get_file_manager()
    files = file_manager.get_chat_files(chat_id)
    return jsonify({
        "success": True,
        "files": [{
            "file_id": f.file_id,
            "original_filename": f.original_filename,
            "stored_filename": f.stored_filename,
            "mime_type": f.mime_type,
            "file_size": f.file_size,
            "content_text": f.content_text,
            "created_at": f.created_at
        } for f in files]
    })

@files_bp.route('/<file_id>', methods=['GET'])
def get_file_endpoint(file_id):
    """Get file metadata."""
    denied = require_file_owner(file_id)
    if denied:
        return denied
    file_manager = get_file_manager()
    metadata = file_manager.get_file(file_id)
    if not metadata:
        return jsonify({"error": "File not found"}), 404

    return jsonify({
        "success": True,
        "file_id": metadata.file_id,
        "chat_id": metadata.chat_id,
        "original_filename": metadata.original_filename,
        "stored_filename": metadata.stored_filename,
        "mime_type": metadata.mime_type,
        "file_size": metadata.file_size,
        "content_text": metadata.content_text,
        "created_at": metadata.created_at
    })

@files_bp.route('/<file_id>/status', methods=['GET'])
def get_file_status_endpoint(file_id):
    """Get file processing status."""
    denied = require_file_owner(file_id)
    if denied:
        return denied
    result = db.get_file(file_id)
    if not result:
        return jsonify({"error": "File not found"}), 404

    return jsonify({
        "success": True,
        "file_id": file_id,
        "processing_status": result.get('processing_status') or 'pending'
    })

@files_bp.route('/<file_id>', methods=['DELETE'])
def delete_file_endpoint(file_id):
    """Delete a file."""
    denied = require_file_owner(file_id)
    if denied:
        return denied
    file_manager = get_file_manager()
    success = file_manager.delete_file(file_id)
    if success:
        return jsonify({"success": True})
    return jsonify({"error": "File not found"}), 404
