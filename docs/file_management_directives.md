# File Management Directives (v3.1.0)

## Overview

The File Management system handles the lifecycle of user-uploaded files, from initial storage and MIME type detection to content extraction and RAG indexing. It is designed for robustness, supporting both synchronous and asynchronous extraction patterns.

## Architecture

The system is centered around the `FileManager` class in `backend/file_manager.py`.

### Component Diagram

```mermaid
graph TD
    A[Client Upload] --> B[FileManager.upload_file]
    B --> C[Local Storage: {DATA_DIR}/uploads]
    B --> D[Database: files table]
    B --> E[Extraction Pipeline]
    E --> F[PDFExtractor]
    E --> G[DocxExtractor]
    E --> H[TextExtractor]
    F/G/H --> I[Store in RAG: FileRAG]
```

## Storage Pattern

- **Path**: `{DATA_DIR}/uploads/{chat_id}/{stored_filename}`
- **Persistence**: File metadata is stored in the SQLite `files` table.
- **Cleanup**: Files are deleted from disk and DB when a chat is deleted via `db.delete_chat()`.

## Extraction Pipeline

The extraction pipeline operates in two distinct phases: text extraction (MIME-dependent) and heuristic chunking (MIME-independent).

### 1. MIME-Aware Text Extraction
1. **PDF**: Uses `fitz` (PyMuPDF). Supports OCR via Tesseract if configured.
2. **DOCX**: Uses `python-docx`.
3. **Text/Code**: Standard UTF-8 reading with fallback to Latin-1.
4. **Images**: Metadata only extraction (or vision processing if enabled).

### 2. Heuristic File Type Classifier (`backend/chunking.py`)
Once text is extracted, the system **bypasses file extensions entirely** and evaluates the raw multi-paragraph content to determine its chunking strategy:
*   **The Dual-Engine Evaluator:** It simultaneously scores documents using a **Code Analyzer** (measuring Syntax Density: weighted regex hits / total word count) and a **Document Analyzer** (measuring Natural Language Stopwords and Punctuation boundaries).
*   **Routing Truths:** File mapping logic is enforced via `CODE_THRESHOLD` and `DOC_THRESHOLD`. If a document beats *both* thresholds (e.g. a Python Enhancement Proposal), it is correctly routed as `mixed` content for hybrid chunking, regardless of whether it was uploaded as a `.pdf` or a `.txt`.

### Background Processing

- **Current Chat Files**: Processed synchronously for immediate availability in the conversation.
- **Batch/Historical Files**: Processed asynchronously to avoid blocking the main thread.
- **Status Tracking**: `processing_status` in the `files` table tracks `pending`, `processing`, `completed`, and `failed`.

## Rules for Agents

### Rule 1: Always Use `FileManager`
Do not attempt direct disk access for file manipulation. Use `FileManager.save_file()` and `FileManager.get_file()`.

### Rule 2: Respect File State
Before attempting to read file content for RAG or context, check that `processing_status` is `completed`.

### Rule 3: Parameter Configuration
All file-related limits (size, count, types) must be fetched from `backend/config.py`.

| Setting | Purpose |
|---------|---------|
| `FILE_UPLOAD_MAX_SIZE` | Hard limit for individual file uploads |
| `FILE_UPLOAD_ALLOWED_TYPES` | List of supported extensions |
| `PDF_EXTRACTOR_ENABLED` | Feature flag for PDF processing |
| `PDF_PAGE_LIMIT` | Max pages to extract to prevent OOM |

## Security Considerations

- **Filename Sanitization**: All uploaded filenames are sanitized via `werkzeug.utils.secure_filename`.
- **MIME Validation**: The system validates actual file content vs. reported MIME type.
- **Quota Management**: Agents should verify chat-level file counts before allowing new uploads.
