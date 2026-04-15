"""
File Management Module

Handles file uploads, content extraction, and file-specific RAG operations
for the My-AI application. Supports PDF, DOCX, TXT, images, and audio/video files.
"""
import os
import uuid
import base64
import mimetypes
import time
import logging
import threading
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from backend.config import (
    DATA_DIR,
    FILE_UPLOAD_MAX_SIZE,
    FILE_STORAGE_PATH,
    PDF_EXTRACTOR_ENABLED,
    PDF_OCR_ENABLED,
    PDF_OCR_LANGUAGES,
    PDF_EXTRACTION_MIN_CONTENT,
    FILE_RAG_ENABLED,
)
from backend.db_wrapper import db
from backend.rag import FileRAG, RAGManager
from backend.pdf_extractor import PDFExtractor

logger = logging.getLogger(__name__)

# Supported file types with their MIME types
SUPPORTED_MIME_TYPES = {
    'application/pdf': '.pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
    'text/plain': '.txt',
    'image/png': '.png',
    'image/jpeg': '.jpg',
    'image/jpeg': '.jpeg',
    'image/gif': '.gif',
    'video/mp4': '.mp4',
    'audio/mpeg': '.mp3',
    'audio/wav': '.wav',
}

# Extension to MIME type mapping
EXTENSION_MIME_MAP = {
    '.pdf': 'application/pdf',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.txt': 'text/plain',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.mp4': 'video/mp4',
    '.mp3': 'audio/mpeg',
    '.wav': 'audio/wav',
}


@dataclass
class FileMetadata:
    """Metadata for a stored file."""
    file_id: str
    chat_id: str
    original_filename: str
    stored_filename: str
    mime_type: str
    file_size: int
    content_text: Optional[str] = None
    created_at: float = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()


class FileManager:
    """Handles file storage, retrieval, and content extraction."""

    def __init__(self, storage_path: str = None, rag_manager: RAGManager = None):
        self.storage_path = storage_path or FILE_STORAGE_PATH
        os.makedirs(self.storage_path, exist_ok=True)

        # Use provided RAGManager or create a new one
        self.rag_manager = rag_manager or RAGManager(persist_path=DATA_DIR)

        # Initialize FileRAG for chunked file embeddings (uses shared manager)
        self.file_rag = FileRAG(rag_manager=self.rag_manager) if FILE_RAG_ENABLED else None

        # Initialize PDF extractor
        self.pdf_extractor = PDFExtractor(ocr_languages=PDF_OCR_LANGUAGES)

    def _generate_file_id(self) -> str:
        """Generate a unique file ID."""
        return f"file_{uuid.uuid4().hex[:16]}"

    def _get_safe_filename(self, filename: str) -> str:
        """Sanitize filename to prevent path traversal."""
        # Get extension
        _, ext = os.path.splitext(filename)
        ext = ext.lower()

        # Generate safe name with UUID
        safe_name = f"{uuid.uuid4().hex[:16]}{ext}"
        return safe_name

    def _validate_file_type(self, mime_type: str) -> bool:
        """Check if MIME type is supported."""
        return mime_type in SUPPORTED_MIME_TYPES

    def _get_extension_for_mime(self, mime_type: str) -> str:
        """Get file extension for a MIME type."""
        return SUPPORTED_MIME_TYPES.get(mime_type, '')

    def save_file_metadata(self, file_id: str, chat_id: str, original_filename: str,
                          stored_filename: str, mime_type: str, file_size: int,
                          content_text: str = None) -> FileMetadata:
        """Save file metadata to database."""
        db.save_file(
            file_id=file_id,
            chat_id=chat_id,
            original_filename=original_filename,
            stored_filename=stored_filename,
            mime_type=mime_type,
            file_size=file_size,
            content_text=content_text
        )

        return FileMetadata(
            file_id=file_id,
            chat_id=chat_id,
            original_filename=original_filename,
            stored_filename=stored_filename,
            mime_type=mime_type,
            file_size=file_size,
            content_text=content_text
        )

    def extract_file_content(self, file_path: str, mime_type: str) -> str:
        """
        Extract text content from a file.

        Args:
            file_path: Path to the file
            mime_type: MIME type of the file

        Returns:
            Extracted text content
        """
        ext = os.path.splitext(file_path)[1].lower()

        # Text-based files
        if mime_type == 'text/plain' or ext == '.txt':
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except UnicodeDecodeError:
                # Try with different encoding
                try:
                    with open(file_path, 'r', encoding='latin-1') as f:
                        return f.read()
                except Exception as e:
                    logger.error(f"Error reading text file: {e}")
                    return ""

        # PDF files - use pymupdf with OCR fallback
        elif mime_type == 'application/pdf':
            return self._extract_pdf_content(file_path)

        # DOCX files
        elif mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
            return self._extract_docx_content(file_path)

        # Images - no text extraction, return placeholder
        elif mime_type.startswith('image/'):
            return f"[Image file: {os.path.basename(file_path)} - for visual analysis, use base64 encoding]"

        # Video files
        elif mime_type.startswith('video/'):
            return f"[Video file: {os.path.basename(file_path)} - frame extraction required]"

        # Audio files
        elif mime_type.startswith('audio/'):
            return f"[Audio file: {os.path.basename(file_path)} - transcription required]"

        return ""

    def _extract_pdf_content(self, file_path: str) -> str:
        """Extract text from PDF using pymupdf with OCR fallback."""
        if not PDF_EXTRACTOR_ENABLED:
            return "[PDF content - extraction disabled]"

        text, strategy = self.pdf_extractor.extract(file_path)

        if text and len(text.strip()) >= PDF_EXTRACTION_MIN_CONTENT:
            return text

        # Extraction failed - return appropriate message
        logger.warning(f"PDF text extraction failed for {file_path} (strategy: {strategy})")
        return f"[PDF content - text extraction failed. Strategy used: {strategy}]"

    def _extract_docx_content(self, file_path: str) -> str:
        """Extract text from DOCX using python-docx."""
        try:
            import docx

            doc = docx.Document(file_path)
            text_parts = []

            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_parts.append(paragraph.text)

            return '\n\n'.join(text_parts)

        except ImportError:
            logger.warning("python-docx not installed, install with: pip install python-docx")
            return "[DOCX content - install python-docx for text extraction]"
        except Exception as e:
            logger.error(f"Error extracting DOCX content: {e}")
            return f"[Error extracting DOCX: {str(e)}]"

    def encode_file_for_vision(self, file_path: str) -> Tuple[str, str]:
        """
        Encode a file as base64 for multi-modal vision analysis.

        Args:
            file_path: Path to the file

        Returns:
            Tuple of (base64_string, mime_type)
        """
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = 'application/octet-stream'

        try:
            with open(file_path, 'rb') as f:
                encoded = base64.b64encode(f.read()).decode('utf-8')
            return encoded, mime_type
        except Exception as e:
            logger.error(f"Error encoding file for vision: {e}")
            return "", mime_type

    def upload_file(self, file_path: str, chat_id: str, original_filename: str) -> Optional[FileMetadata]:
        """
        Upload and process a file.

        Args:
            file_path: Path to the file to upload
            chat_id: Chat session ID
            original_filename: Original filename

        Returns:
            FileMetadata if successful, None otherwise
        """
        try:
            logger.info(f"[UPLOAD_START] file_path={file_path}, chat_id={chat_id}, original_filename={original_filename}")

            # Validate file exists
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                return None
            logger.debug(f"[UPLOAD] File exists, size: {os.path.getsize(file_path)} bytes")

            # Get file info
            file_size = os.path.getsize(file_path)
            logger.debug(f"[UPLOAD] File size: {file_size} bytes")

            # Check size limit
            if file_size > FILE_UPLOAD_MAX_SIZE:
                logger.error(f"File too large: {file_size} > {FILE_UPLOAD_MAX_SIZE}")
                return None

            # Determine MIME type
            mime_type, _ = mimetypes.guess_type(file_path)
            logger.debug(f"[UPLOAD] MIME type (guessed): {mime_type}")

            # Handle unknown/unrecognized MIME types (None or octet-stream)
            if not mime_type or mime_type == 'application/octet-stream':
                # Try to determine from extension
                ext = os.path.splitext(file_path)[1].lower()
                mime_type = EXTENSION_MIME_MAP.get(ext, None)
                logger.debug(f"[UPLOAD] MIME type (from extension): {mime_type}")

            # Fallback: if still no valid MIME type, try to detect from file content
            if not mime_type or mime_type == 'application/octet-stream':
                # Try to detect PDF by checking for PDF header
                try:
                    with open(file_path, 'rb') as f:
                        header = f.read(8)
                        if header.startswith(b'%PDF-'):
                            mime_type = 'application/pdf'
                            logger.debug("[UPLOAD] MIME type (from PDF header): application/pdf")
                except Exception:
                    pass

            # Final validation
            if not self._validate_file_type(mime_type):
                logger.error(f"Unsupported file type: {mime_type}")
                return None
            logger.info(f"[UPLOAD] Valid MIME type: {mime_type}")

            # Generate safe filename
            safe_filename = self._get_safe_filename(original_filename)
            stored_path = os.path.join(self.storage_path, safe_filename)
            logger.debug(f"[UPLOAD] Stored path: {stored_path}")

            # Copy file to storage
            import shutil
            shutil.copy2(file_path, stored_path)
            logger.debug(f"[UPLOAD] File copied to storage")

            # Generate file ID
            file_id = self._generate_file_id()
            logger.debug(f"[UPLOAD] File ID: {file_id}")

            # Extract content for RAG (in background for faster response)
            content_text = self.extract_file_content(stored_path, mime_type)
            logger.debug(f"[UPLOAD] Content extracted, length: {len(content_text) if content_text else 0} chars")

            # Save metadata to DB
            logger.info(f"[UPLOAD] Saving metadata to DB...")
            metadata = self.save_file_metadata(
                file_id=file_id,
                chat_id=chat_id,
                original_filename=original_filename,
                stored_filename=safe_filename,
                mime_type=mime_type,
                file_size=file_size,
                content_text=content_text
            )
            logger.info(f"[UPLOAD] Metadata saved: file_id={file_id}")

            # Store in FileRAG for chunked embeddings (in background for faster response)
            if self.file_rag and content_text and len(content_text.strip()) > 50:
                try:
                    self.file_rag.store_file(file_id, chat_id, content_text, original_filename)
                    logger.debug(f"[UPLOAD] Added to FileRAG with chunked embeddings")
                except Exception as e:
                    logger.warning(f"Failed to add file to FileRAG: {e}")

            logger.info(f"[UPLOAD_SUCCESS] file_id={file_id}")
            return metadata

        except Exception as e:
            logger.error(f"[UPLOAD_ERROR] Error uploading file: {e}")
            import traceback
            logger.error(f"[UPLOAD_ERROR] Traceback: {traceback.format_exc()}")
            return None

    def upload_file_async(self, file_path: str, chat_id: str, original_filename: str) -> Optional[FileMetadata]:
        """
        Upload a file. For the current chat, processing is synchronous for immediate
        availability. For other chats (background), processing is async.

        Args:
            file_path: Path to the file to upload
            chat_id: Chat session ID
            original_filename: Original filename

        Returns:
            FileMetadata if successful, None otherwise
        """
        try:
            logger.info(f"[UPLOAD_ASYNC_START] file_path={file_path}, chat_id={chat_id}, original_filename={original_filename}")

            # Validate file exists
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                return None

            # Get file info
            file_size = os.path.getsize(file_path)
            logger.debug(f"[UPLOAD_ASYNC] File size: {file_size} bytes")

            # Check size limit
            if file_size > FILE_UPLOAD_MAX_SIZE:
                logger.error(f"File too large: {file_size} > {FILE_UPLOAD_MAX_SIZE}")
                return None

            # Determine MIME type
            mime_type, _ = mimetypes.guess_type(file_path)
            logger.debug(f"[UPLOAD_ASYNC] MIME type (guessed): {mime_type}")

            # Handle unknown/unrecognized MIME types
            if not mime_type or mime_type == 'application/octet-stream':
                ext = os.path.splitext(file_path)[1].lower()
                mime_type = EXTENSION_MIME_MAP.get(ext, None)
                logger.debug(f"[UPLOAD_ASYNC] MIME type (from extension): {mime_type}")

            # Fallback: check PDF header
            if not mime_type or mime_type == 'application/octet-stream':
                try:
                    with open(file_path, 'rb') as f:
                        header = f.read(8)
                        if header.startswith(b'%PDF-'):
                            mime_type = 'application/pdf'
                except Exception:
                    pass

            # Final validation
            if not self._validate_file_type(mime_type):
                logger.error(f"Unsupported file type: {mime_type}")
                return None

            # Generate safe filename
            safe_filename = self._get_safe_filename(original_filename)
            stored_path = os.path.join(self.storage_path, safe_filename)

            # Copy file to storage
            import shutil
            shutil.copy2(file_path, stored_path)

            # Generate file ID
            file_id = self._generate_file_id()

            # Save file metadata to database
            self.save_file_metadata(file_id, chat_id, original_filename, safe_filename, mime_type, file_size)

            # Extract content and store in FileRAG (synchronous for current chat)
            try:
                logger.info(f"[UPLOAD_ASYNC] Extracting content from {stored_path}")
                content_text = self.extract_file_content(stored_path, mime_type)
                logger.info(f"[UPLOAD_ASYNC] Content extracted: {len(content_text) if content_text else 0} chars")

                # Update file content in database
                self.update_file_content(file_id, content_text)

                # Store in FileRAG (synchronous - for current chat immediate availability)
                if self.file_rag and content_text and len(content_text.strip()) > 50:
                    try:
                        logger.info(f"[UPLOAD_ASYNC] Storing in FileRAG")
                        self.file_rag.store_file(file_id, chat_id, content_text, original_filename)
                        logger.info(f"[UPLOAD_ASYNC] Added to FileRAG")
                    except Exception as e:
                        logger.warning(f"[UPLOAD_ASYNC] Failed to add to FileRAG: {e}")
                else:
                    logger.info(f"[UPLOAD_ASYNC] Skipping FileRAG - file_rag={self.file_rag is not None}, content={len(content_text) if content_text else 0} chars")

                # Update status to completed
                self.update_file_processing_status(file_id, 'completed')
                logger.info(f"[UPLOAD_ASYNC] Completed for {file_id}")

            except Exception as e:
                logger.error(f"[UPLOAD_ASYNC_PROCESS_ERROR] Error: {e}", exc_info=True)
                try:
                    self.update_file_processing_status(file_id, 'failed')
                except:
                    pass

            # Return metadata (after processing for current chat)
            metadata = FileMetadata(
                file_id=file_id,
                chat_id=chat_id,
                original_filename=original_filename,
                stored_filename=safe_filename,
                mime_type=mime_type,
                file_size=file_size,
                content_text=content_text if content_text else "",
                created_at=time.time()
            )
            logger.info(f"[UPLOAD_ASYNC] Processing complete for {file_id}")

            return metadata

        except Exception as e:
            logger.error(f"[UPLOAD_ASYNC_ERROR] Error uploading file: {e}")
            import traceback
            logger.error(f"[UPLOAD_ASYNC_ERROR] Traceback: {traceback.format_exc()}")
            return None

    def _process_file_background(self, file_id: str, chat_id: str, stored_path: str, mime_type: str, original_filename: str = None):
        """
        Process file in background - extract content and add to RAG.
        Updates processing_status in database when complete.
        This is used for background processing of files (e.g., historical files,
        or when upload_file_async is called for non-current chats).
        """
        try:
            logger.info(f"[BG_PROCESS] Starting background processing for {file_id}")

            # Check if file is already processed (to prevent double embedding)
            # If the file has content in DB, it was likely already processed
            existing_file = db.get_file(file_id)
            if existing_file and existing_file.get('content_text'):
                logger.info(f"[BG_PROCESS] File {file_id} already has content, skipping FileRAG storage")
                self.update_file_processing_status(file_id, 'completed')
                return

            # Update status to processing
            logger.info(f"[BG_PROCESS] About to set status to 'processing'")
            self.update_file_processing_status(file_id, 'processing')
            logger.info(f"[BG_PROCESS] Status set to 'processing'")

            # Extract content
            logger.info(f"[BG_PROCESS] About to extract content from {stored_path}")
            content_text = self.extract_file_content(stored_path, mime_type)
            logger.info(f"[BG_PROCESS] Content extracted: {len(content_text) if content_text else 0} chars")

            # Update metadata with content
            logger.info(f"[BG_PROCESS] About to update file content")
            self.update_file_content(file_id, content_text)
            logger.info(f"[BG_PROCESS] File content updated")

            # Store in FileRAG
            if self.file_rag and content_text and len(content_text.strip()) > 50:
                try:
                    logger.info(f"[BG_PROCESS] About to store in FileRAG")
                    self.file_rag.store_file(file_id, chat_id, content_text, original_filename)
                    logger.info(f"[BG_PROCESS] Added to FileRAG")
                except Exception as e:
                    logger.warning(f"[BG_PROCESS] Failed to add to FileRAG: {e}")
            else:
                logger.info(f"[BG_PROCESS] Skipping FileRAG - file_rag={self.file_rag is not None}, content={len(content_text) if content_text else 0} chars")

            # Update status to complete
            logger.info(f"[BG_PROCESS] About to set status to 'completed'")
            self.update_file_processing_status(file_id, 'completed')
            logger.info(f"[BG_PROCESS] Completed for {file_id}")

        except Exception as e:
            logger.error(f"[BG_PROCESS_ERROR] Error: {e}", exc_info=True)
            # Update status to failed on error
            try:
                self.update_file_processing_status(file_id, 'failed')
            except:
                pass

    def update_file_content(self, file_id: str, content_text: str) -> bool:
        """
        Update file metadata with extracted content.

        Args:
            file_id: File ID
            content_text: Extracted text content

        Returns:
            True if successful, False otherwise
        """
        try:
            db.update_file_content(file_id, content_text)
            logger.info(f"[UPDATE_CONTENT] Updated file {file_id} with content")
            return True
        except Exception as e:
            logger.error(f"[UPDATE_CONTENT_ERROR] Error updating content: {e}")
            return False

    def update_file_processing_status(self, file_id: str, status: str) -> bool:
        """Update file processing status.

        Args:
            file_id: File ID
            status: 'pending', 'processing', 'completed', or 'failed'

        Returns:
            True if successful, False otherwise
        """
        try:
            db.update_file_processing_status(file_id, status)
            logger.info(f"[UPDATE_FILE_STATUS] Updated {file_id} to '{status}'")
            return True
        except Exception as e:
            logger.error(f"[UPDATE_FILE_STATUS_ERROR] Error: {e}")
            return False

    def get_file(self, file_id: str) -> Optional[FileMetadata]:
        """Get file metadata by ID."""
        result = db.get_file(file_id)
        if not result:
            return None

        # Get stored file path
        stored_path = os.path.join(self.storage_path, result['stored_filename'])

        return FileMetadata(
            file_id=result['id'],
            chat_id=result['chat_id'],
            original_filename=result['original_filename'],
            stored_filename=result['stored_filename'],
            mime_type=result['mime_type'],
            file_size=result['file_size'],
            content_text=result.get('content_text'),
            created_at=result.get('created_at', 0)
        )

    def delete_file(self, file_id: str) -> bool:
        """Delete a file and its associated data."""
        try:
            # Get file metadata
            metadata = self.get_file(file_id)
            if not metadata:
                return False

            # Delete from database
            db.delete_file(file_id)

            # Delete from storage
            stored_path = os.path.join(self.storage_path, metadata.stored_filename)
            if os.path.exists(stored_path):
                os.remove(stored_path)

            logger.info(f"File deleted: {file_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return False

    def get_chat_files(self, chat_id: str) -> List[FileMetadata]:
        """Get all files for a chat session."""
        results = db.get_chat_files(chat_id)

        files = []
        for row in results:
            files.append(FileMetadata(
                file_id=row['id'],
                chat_id=row['chat_id'],
                original_filename=row['original_filename'],
                stored_filename=row['stored_filename'],
                mime_type=row['mime_type'],
                file_size=row['file_size'],
                content_text=row.get('content_text'),
                created_at=row.get('created_at', 0)
            ))

        return files


# Global instance
file_manager = FileManager()
