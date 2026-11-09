import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.tools.agents.document_agent.tools import (
    _get_managers,
    document_agent_rag_tool,
    grep_uploaded_file_tool,
    read_uploaded_file_tool
)

@pytest.fixture(autouse=True)
def own_file():
    """By default the file belongs to the caller's owner: file_for_chat returns the row (chat "file-chat")."""
    with patch('backend.tools.agents.document_agent.tools.file_for_chat',
               return_value={"id": "file_id", "chat_id": "file-chat"}) as mock:
        yield mock


def test_get_managers():
    with patch('backend.tools.agents.document_agent.tools.get_embedding_model') as mock_get_emb, \
         patch('backend.tools.agents.document_agent.tools.RAGProvider') as mock_rag_provider, \
         patch('backend.tools.agents.document_agent.tools.FileManager') as mock_fm, \
         patch('backend.tools.agents.document_agent.tools.FileRAG') as mock_file_rag:
        
        mock_emb = MagicMock()
        mock_get_emb.return_value = mock_emb
        
        mock_manager = MagicMock()
        mock_rag_provider.get_manager.return_value = mock_manager
        
        fm, fr = _get_managers()
        
        assert fm == mock_fm.return_value
        assert fr == mock_file_rag.return_value
        mock_fm.assert_called_once_with(rag_manager=mock_manager)
        mock_file_rag.assert_called_once_with(rag_manager=mock_manager)

@pytest.mark.anyio
async def test_document_agent_rag_tool_no_results():
    mock_fm = MagicMock()
    mock_fr = MagicMock()
    mock_fr.retrieve_for_file = AsyncMock(return_value=[])
    
    with patch('backend.tools.agents.document_agent.tools._get_managers', return_value=(mock_fm, mock_fr)):
        res = await document_agent_rag_tool("chat_id", "file_id", "query", depth="standard")
        assert res["success"] is True
        assert res["results"] == []
        assert "No semantic matches" in res["message"]
        mock_fr.retrieve_for_file.assert_awaited_once_with("file_id", "query", n_results=5, chat_id="chat_id", file_chat_id="file-chat")

@pytest.mark.anyio
async def test_document_agent_rag_tool_with_results():
    mock_fm = MagicMock()
    mock_fr = MagicMock()
    mock_fr.retrieve_for_file = AsyncMock(return_value=["res1"])
    
    with patch('backend.tools.agents.document_agent.tools._get_managers', return_value=(mock_fm, mock_fr)):
        res = await document_agent_rag_tool("chat_id", "file_id", "query", depth="deep")
        assert res["success"] is True
        assert res["results"] == ["res1"]

@pytest.mark.anyio
async def test_grep_uploaded_file_tool():
    mock_fm = MagicMock()
    mock_fm.grep_file = MagicMock(return_value={"success": True})
    mock_fr = MagicMock()
    
    with patch('backend.tools.agents.document_agent.tools._get_managers', return_value=(mock_fm, mock_fr)):
        res = await grep_uploaded_file_tool("chat_id", "file_id", "query", True, 200)
        assert res == {"success": True}
        mock_fm.grep_file.assert_called_once_with("file_id", "query", True, 200)

@pytest.mark.anyio
async def test_read_uploaded_file_tool():
    mock_fm = MagicMock()
    mock_fm.read_file_range = MagicMock(return_value={"content": "hello"})
    mock_fr = MagicMock()
    
    with patch('backend.tools.agents.document_agent.tools._get_managers', return_value=(mock_fm, mock_fr)):
        res = await read_uploaded_file_tool("chat_id", "file_id", 1, 10, None)
        assert res == {"content": "hello"}
        mock_fm.read_file_range.assert_called_once_with("file_id", 1, 10, None)



@pytest.mark.anyio
@pytest.mark.parametrize("call", [
    lambda: document_agent_rag_tool("chat_of_b", "file_of_a", "query"),
    lambda: grep_uploaded_file_tool("chat_of_b", "file_of_a", "query"),
    lambda: read_uploaded_file_tool("chat_of_b", "file_of_a"),
])
async def test_every_document_tool_refuses_a_file_outside_the_callers_chats(call, own_file):
    own_file.return_value = None  # another user's (or a missing) file
    with patch('backend.tools.agents.document_agent.tools._get_managers') as managers:
        assert await call() == {"success": False, "error": "File not found"}
    managers.assert_not_called()  # no FileManager or RAG access at all
    own_file.assert_called_once_with("file_of_a", "chat_of_b")


@pytest.mark.anyio
async def test_document_tools_read_a_file_of_the_same_user_from_another_chat(own_file):
    own_file.return_value = {"id": "f", "chat_id": "older-chat-of-the-same-user"}
    mock_fr = MagicMock()
    mock_fr.retrieve_for_file = AsyncMock(return_value=["hit"])
    with patch('backend.tools.agents.document_agent.tools._get_managers', return_value=(MagicMock(), mock_fr)):
        res = await document_agent_rag_tool("current-chat", "f", "q")
    assert res["results"] == ["hit"]
    # retrieval is pinned to the chat the file record belongs to
    assert mock_fr.retrieve_for_file.call_args.kwargs["file_chat_id"] == "older-chat-of-the-same-user"
