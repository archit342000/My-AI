# backend/files
**Role:** Handles user-uploaded files, including storage, metadata tracking, content extraction (with OCR support), and integration with the RAG (Retrieval-Augmented Generation) system.

## 📂 Subdirectories
| Folder | Responsibility |
| :--- | :--- |

## 📄 Core Files
| File | Purpose | Key Symbols/Exports |
| :--- | :--- | :--- |
| `__init__.py` | Package entry point and export aggregator. | `FileManager`, `PDFExtractor` |
| `manager.py` | Core file operations, storage management, and RAG integration. | `FileManager`, `FileMetadata` |
| `pdf_extractor.py` | Specialized PDF text extraction with OCR fallback. | `PDFExtractor` |
| `router.py` | API endpoints for uploading, deleting, and managing files. Upload claims the chat for the caller; list checks the chat owner and get, status and delete check the file's chat owner (another user's is a 404). | `files_bp` |

## 🧩 Architectural Context
*   **Dependencies:**
    - `backend.database`: Persistence for file metadata and processing status.
    - `backend.rag`: Semantic search and vector storage for uploaded content.
    - `backend.logging`: Transaction auditing and error tracking.
    - `backend.config`: File storage paths and upload constraints.
*   **Flow:**
    1. **Upload:** Files are received via `files_bp`, validated for size/type, and stored on disk.
    2. **Extraction:** `FileManager` detects the file type and uses the appropriate strategy (e.g., `PDFExtractor` for PDFs) to pull raw text.
    3. **Indexing:** Extracted text is sent to the RAG system to be chunked and embedded for semantic retrieval.
    4. **Availability:** Once status is marked as `completed`, the file's content can be queried via `FileRAG` or read directly via `read_file_range`.

## 🛠️ Usage & Conventions
*   **Patterns:** 
    - **OCR Fallback:** Scanned PDFs that fail standard text extraction are automatically passed through an OCR engine (EasyOCR) if enabled.
    - **Heuristic Content Typing:** Sniffs file headers and content to accurately categorize unknown or generic binary files.
    - **Context-Aware Reads:** Provides specialized read modes (Page-based for PDFs, Line-based for code) to ensure token efficiency.
*   **Conventions:** Always use `get_file_manager()` to ensure the manager is initialized with the current global RAG state.
*   **Testing:**
    - **Local:** Unit tests in `tests/` ensure strict compliance with the 1:1 exhaustive testing rule, verifying OCR fallback, binary sniffing, metadata persistence, and RAG indexing coordination.
    - **Run Command:** `EMBEDDING_URL="http://mock" AI_URL="http://mock" ./venv/bin/python3 -m pytest backend/files/tests/`
