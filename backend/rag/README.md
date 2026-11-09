# backend/rag
**Role:** Provides a comprehensive Retrieval-Augmented Generation (RAG) framework, including document chunking, semantic embedding generation, vector storage (ChromaDB), and specialized retrieval logic for files and research.

## 📂 Subdirectories
| Folder | Responsibility |
| :--- | :--- |

## 📄 Core Files
| File | Purpose | Key Symbols/Exports |
| :--- | :--- | :--- |
| `__init__.py` | Package entry point and high-level export aggregator. | `RAGManager`, `FileRAG` |
| `chunking.py` | Language-aware text splitting and metadata extraction. | `chunk_code_text`, `chunk_document_text`, `content_to_index_text` |
| `embeddings.py` | Integration with external embedding inference services. | `AIEmbeddingFunction` |
| `file_rag.py` | Semantic search and indexing for user-uploaded files. | `FileRAG` |
| `manager.py` | Central controller for vector collections and lifecycle. | `RAGManager` |
| `providers.py` | Factory pattern for singleton `RAGManager` access. | `RAGProvider` |
| `store.py` | Lower-level ChromaDB abstraction and search logic. | `RAGStore` |
| `token_counter.py` | Accurate token counting for context limit enforcement. | `count_tokens` |

## 🧩 Architectural Context
*   **Dependencies:**
    - `chromadb`: Underlying vector database for persistence.
    - `tiktoken`: Used for token-aware chunking.
    - `backend.config`: Stores vector store paths and embedding model settings.
*   **Flow:**
    1. **Ingestion:** Stored file content is JSON (`pages` for PDFs, `text` for everything else); `content_to_index_text` unwraps it (pages become page markers, text becomes plain text) before the documents are passed through `chunking.py` (file type is detected on that plain text, so CSV and TSV uploads now use the row-based spreadsheet chunker; a stored wrapper with an invalid payload raises and the file is not indexed) to create semantically meaningful segments. The stored content is not changed.
    2. **Embedding:** Segments are converted to vectors via `AIEmbeddingFunction`.
    3. **Storage:** Vectors and metadata are stored in specialized ChromaDB collections managed by `RAGManager`.
    4. **Retrieval:** Agents perform hybrid (semantic + keyword) searches to gather relevant context for LLM prompts.

## 🛠️ Usage & Conventions
*   **Patterns:** 
    - **Hybrid Search:** Combines Vector Search (for concept) and BM25 (for exact keywords) to maximize retrieval accuracy.
    - **Singleton Access:** Always use `RAGProvider.get_manager()` to interact with the RAG system to ensure cross-process consistency.
    *   **Metadata Extraction:** Chunks include breadcrumbs (line numbers, headers, exports) to provide the LLM with structural context.
    *   **Configuration:** Vector dimensions are validated against the current model configuration on startup to prevent index corruption.
    *   **Testing:**
        - **Local:** Unit tests in `tests/` ensure strict compliance with the exhaustive 1:1 testing rule. `test_chunking.py` verifies language-aware splitting (Python, C++, JS, SQL, etc.), while other tests verify hybrid search, ChromaDB persistence, and embedding normalization.
        - **Run Command:** `EMBEDDING_URL="http://mock" AI_URL="http://mock" ./venv/bin/python3 -m pytest backend/rag/tests/`
