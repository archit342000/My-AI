import json
import time
from backend.logging import log_event
from backend import config
from .store import RAGStore
from .manager import RAGManager
from backend.rag.chunking import (
    detect_file_type,
    chunk_code_text,
    chunk_spreadsheet_text,
    chunk_mixed_text,
    chunk_document_text,
    extract_code_metadata,
    extract_document_metadata,
    strip_page_markers,
    resolve_page_number,
    content_to_index_text
)

class FileRAG(RAGStore):
    """File content storage with chunked embeddings for semantic search."""

    def __init__(self, rag_manager: RAGManager = None, persist_path=None, api_url=None, embedding_model=None, api_key=None):
        if rag_manager is None:
            raise RuntimeError("FileRAG requires a RAGManager instance.")
        self.rag_manager = rag_manager
        super().__init__(self.rag_manager, "file_store")
        self._initialized = True

    async def store_file(self, file_id, chat_id, content_text, filename=None, timestamp=None,
                   file_type_override=None):
        if not self._initialized or not content_text or len(content_text.strip()) < 50:
            return []

        # Stored content is JSON (pages or text): index the text itself, with page markers for PDFs.
        # Strip the markers and build the page map before detecting the type, so JSON or marker lines
        # do not skew the classification.
        clean_text, page_map = strip_page_markers(content_to_index_text(content_text))

        if file_type_override is not None:
            file_type = file_type_override
            detection_meta = {"overridden": True}
        else:
            file_type, detection_meta = detect_file_type(filename or "", clean_text)

        if file_type == 'spreadsheet':
            chunks = chunk_spreadsheet_text(clean_text, config.EMBEDDING_MAX_TOKENS_FILE)
            chunk_strategy = 'row-based'
        elif file_type == 'code':
            chunks = chunk_code_text(clean_text, config.EMBEDDING_MAX_TOKENS_FILE)
            chunk_strategy = 'syntax-aware'
        elif file_type == 'mixed':
            chunks = chunk_mixed_text(clean_text, config.EMBEDDING_MAX_TOKENS_FILE)
            chunk_strategy = 'hybrid'
        else:
            chunks = chunk_document_text(clean_text, config.EMBEDDING_MAX_TOKENS_FILE)
            chunk_strategy = 'paragraph-based'

        documents, metadatas, ids = [], [], []
        is_page_based = bool(page_map)  # True for PDFs; False for plain text, code, CSV

        for i, chunk in enumerate(chunks):
            doc_id = f"{file_id}_chunk_{i}"

            metadata = {
                "file_id": file_id,
                "chat_id": chat_id,
                "chunk_index": i,
                "timestamp": timestamp if timestamp is not None else time.time(),
                "file_type": file_type,
                "chunk_strategy": chunk_strategy,
            }

            if is_page_based:
                # Page-based docs (PDF): only store page_number, skip line metadata
                page_number = resolve_page_number(chunk.line_start, page_map)
                if page_number is not None:
                    metadata["page_number"] = page_number
            else:
                # Line-based docs (code, text, CSV): only store line positions
                if chunk.line_start is not None:
                    metadata["line_start"] = chunk.line_start
                if chunk.line_end is not None:
                    metadata["line_end"] = chunk.line_end

            if file_type == 'code':
                code_meta = extract_code_metadata(chunk.text, line_start=chunk.line_start or 1)
                metadata.update({
                    "function_names": json.dumps(code_meta.get('function_names', [])),
                    "class_names": json.dumps(code_meta.get('class_names', [])),
                    "imports": json.dumps(code_meta.get('imports', []))
                })
            elif file_type in ('document', 'unknown', 'mixed'):
                c_meta = extract_document_metadata(chunk.text)
                metadata.update({
                    "section_headers": json.dumps(c_meta.get('section_headers', [])),
                    "subsection_headers": json.dumps(c_meta.get('subsection_headers', []))
                })
            elif file_type == 'spreadsheet':
                metadata.update({
                    "column_count": detection_meta.get('column_count', 0),
                    "column_headers": json.dumps(detection_meta.get('headers', [])),
                    "has_headers": detection_meta.get('has_headers', False),
                    "data_row_count": detection_meta.get('data_row_count', 0)
                })
            documents.append(chunk.text)
            metadatas.append(metadata)
            ids.append(doc_id)

        return await self.store(documents, metadatas, ids, chat_id=chat_id)

    async def retrieve_for_file(self, file_id, query, n_results=5, hybrid=True, chat_id=None):
        return await self.retrieve_by_query(query, n_results=n_results, where={"file_id": file_id}, hybrid=hybrid, chat_id=chat_id)

    def get_file_chunks(self, file_id):
        return self.list_all(where={"file_id": file_id})

    def delete_file(self, file_id):
        return self.cleanup({"file_id": file_id})

    def cleanup_chat(self, chat_id):
        return self.cleanup({"chat_id": chat_id})
