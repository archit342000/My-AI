import json
import logging
from backend.rag import RAGProvider, FileRAG
from backend.models import get_embedding_model
from backend.files.manager import FileManager
from backend import config
from backend.auth.ownership import file_for_chat

logger = logging.getLogger(__name__)

def _get_managers():
    embedding_model = get_embedding_model()
    rag_manager = RAGProvider.get_manager(
        persist_path=config.CHROMA_PATH,
        embedding_model=embedding_model
    )
    file_manager = FileManager(rag_manager=rag_manager)
    file_rag = FileRAG(rag_manager=rag_manager)
    return file_manager, file_rag

_FILE_NOT_FOUND = {"success": False, "error": "File not found"}


async def document_agent_rag_tool(chat_id: str, file_id: str, query: str, depth: str = "standard", **kwargs):
    """Tool wrapper for RAG retrieval. A file outside the caller's chats is "not found"."""
    file_row = file_for_chat(file_id, chat_id)
    if not file_row:
        return dict(_FILE_NOT_FOUND)
    _, file_rag = _get_managers()
    
    n_results = config.DOCUMENT_AGENT_RAG_DEPTH_MAP.get(depth, 5)
    
    # Pinned to the chat the file record belongs to, so chunks of another chat can never come back.
    results = await file_rag.retrieve_for_file(file_id, query, n_results=n_results, chat_id=chat_id, file_chat_id=file_row["chat_id"])
    
    if not results:
        return {"success": True, "results": [], "message": "No semantic matches found."}
        
    return {
        "success": True,
        "results": results
    }

async def grep_uploaded_file_tool(chat_id: str, file_id: str, query: str, is_regex: bool = False, context_chars: int = 300, **kwargs):
    """Tool wrapper for grep search. A file outside the caller's chats is "not found"."""
    if not file_for_chat(file_id, chat_id):
        return dict(_FILE_NOT_FOUND)
    file_manager, _ = _get_managers()
    return file_manager.grep_file(file_id, query, is_regex, context_chars)

async def read_uploaded_file_tool(chat_id: str, file_id: str, start_line: int = None, end_line: int = None, page: int = None, **kwargs):
    """Tool wrapper for line/page reading. A file outside the caller's chats is "not found"."""
    if not file_for_chat(file_id, chat_id):
        return dict(_FILE_NOT_FOUND)
    file_manager, _ = _get_managers()
    return file_manager.read_file_range(file_id, start_line, end_line, page)
