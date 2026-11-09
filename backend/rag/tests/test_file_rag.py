import json
import pytest
import time
from unittest.mock import patch, MagicMock, AsyncMock
from backend.rag.file_rag import FileRAG

@pytest.fixture
def mock_rag_manager():
    manager = MagicMock()
    v_col = MagicMock()
    bm25_col = MagicMock()
    manager._ensure_l2_collections.return_value = (v_col, bm25_col)
    return manager

def test_file_rag_init(mock_rag_manager):
    file_rag = FileRAG(mock_rag_manager)
    assert file_rag._initialized is True
    assert file_rag.collection_name == "file_store"

def test_file_rag_init_no_manager():
    with pytest.raises(RuntimeError, match="FileRAG requires a RAGManager instance."):
        FileRAG()

@pytest.mark.anyio
@patch("backend.rag.file_rag.detect_file_type")
@patch("backend.rag.file_rag.strip_page_markers")
@patch("backend.rag.file_rag.chunk_document_text")
async def test_store_file(mock_chunk, mock_strip, mock_detect, mock_rag_manager):
    file_rag = FileRAG(mock_rag_manager)
    
    mock_detect.return_value = ('document', {})
    mock_strip.return_value = ('clean text', {})
    
    class MockChunk:
        def __init__(self, text, start, end):
            self.text = text
            self.line_start = start
            self.line_end = end
    
    mock_chunk.return_value = [MockChunk("t1", 1, 2)]
    
    with patch.object(file_rag, 'store', new_callable=MagicMock) as mock_store:
        async def mock_store_async(*args, **kwargs):
            return ["id1"]
        mock_store.side_effect = mock_store_async
        
        # Test basic document
        res = await file_rag.store_file("file1", "chat1", "some long text that meets the length requirement here "*5)
        assert res == ["id1"]
        mock_store.assert_called_once()
        
        # Test empty content
        res = await file_rag.store_file("file1", "chat1", "")
        assert res == []

@pytest.mark.anyio
@patch("backend.rag.file_rag.strip_page_markers")
@patch("backend.rag.file_rag.chunk_spreadsheet_text")
@patch("backend.rag.file_rag.chunk_code_text")
@patch("backend.rag.file_rag.chunk_mixed_text")
async def test_store_file_types(mock_mixed, mock_code, mock_spreadsheet, mock_strip, mock_rag_manager):
    file_rag = FileRAG(mock_rag_manager)
    mock_strip.return_value = ('clean text', {})
    
    class MockChunk:
        def __init__(self, text, start, end):
            self.text = text
            self.line_start = start
            self.line_end = end
            
    mock_spreadsheet.return_value = [MockChunk("t1", 1, 2)]
    mock_code.return_value = [MockChunk("t1", 1, 2)]
    mock_mixed.return_value = [MockChunk("t1", 1, 2)]
    
    with patch.object(file_rag, 'store', new_callable=MagicMock) as mock_store:
        async def mock_store_async(*args, **kwargs):
            return ["id1"]
        mock_store.side_effect = mock_store_async
        
        content = "some long text that meets the length requirement here "*5
        
        await file_rag.store_file("f1", "c1", content, file_type_override='spreadsheet')
        mock_spreadsheet.assert_called_once()
        
        await file_rag.store_file("f2", "c2", content, file_type_override='code')
        mock_code.assert_called_once()
        
        await file_rag.store_file("f3", "c3", content, file_type_override='mixed')
        mock_mixed.assert_called_once()

@pytest.mark.anyio
@patch("backend.rag.file_rag.detect_file_type")
@patch("backend.rag.file_rag.strip_page_markers")
@patch("backend.rag.file_rag.chunk_document_text")
async def test_store_file_page_based(mock_chunk, mock_strip, mock_detect, mock_rag_manager):
    file_rag = FileRAG(mock_rag_manager)
    
    mock_detect.return_value = ('document', {})
    mock_strip.return_value = ('clean text', [(1, 1)]) # page map as list of tuples
    
    class MockChunk:
        def __init__(self, text, start, end):
            self.text = text
            self.line_start = start
            self.line_end = end
    
    mock_chunk.return_value = [MockChunk("t1", 1, 2)]
    
    with patch.object(file_rag, 'store', new_callable=MagicMock) as mock_store:
        async def mock_store_async(*args, **kwargs):
            return ["id1"]
        mock_store.side_effect = mock_store_async
        
        res = await file_rag.store_file("file1", "chat1", "some long text that meets the length requirement here "*5)
        # Should not raise errors
        assert res == ["id1"]

@pytest.mark.anyio
async def test_retrieve_for_file(mock_rag_manager):
    file_rag = FileRAG(mock_rag_manager)
    with patch.object(file_rag, 'retrieve_by_query', new_callable=MagicMock) as mock_ret:
        async def mock_ret_async(*args, **kwargs):
            return [{"id": "1"}]
        mock_ret.side_effect = mock_ret_async
        
        res = await file_rag.retrieve_for_file("file1", "query")
        assert res == [{"id": "1"}]
        mock_ret.assert_called_once_with("query", n_results=5, where={"file_id": "file1"}, hybrid=True, chat_id=None)

def test_get_file_chunks(mock_rag_manager):
    file_rag = FileRAG(mock_rag_manager)
    with patch.object(file_rag, 'list_all') as mock_list:
        mock_list.return_value = ["chunk1"]
        res = file_rag.get_file_chunks("file1")
        assert res == ["chunk1"]
        mock_list.assert_called_once_with(where={"file_id": "file1"})

def test_delete_file(mock_rag_manager):
    file_rag = FileRAG(mock_rag_manager)
    with patch.object(file_rag, 'cleanup') as mock_clean:
        mock_clean.return_value = True
        res = file_rag.delete_file("file1")
        assert res is True
        mock_clean.assert_called_once_with({"file_id": "file1"})

def test_cleanup_chat(mock_rag_manager):
    file_rag = FileRAG(mock_rag_manager)
    with patch.object(file_rag, 'cleanup') as mock_clean:
        mock_clean.return_value = True
        res = file_rag.cleanup_chat("chat1")
        assert res is True
        mock_clean.assert_called_once_with({"chat_id": "chat1"})


async def _stored_chunks(file_rag, content, filename):
    captured = {}

    async def fake_store(documents, metadatas, ids, **kwargs):
        captured.update(documents=documents, metadatas=metadatas)
        return ids

    with patch.object(file_rag, 'store', side_effect=fake_store):
        await file_rag.store_file("file1", "chat1", content, filename=filename)
    return captured


@pytest.mark.anyio
async def test_store_file_indexes_page_json_as_page_text_with_page_numbers(mock_rag_manager):
    file_rag = FileRAG(mock_rag_manager)
    # Long pages, so each page ends up in its own chunk(s)
    pages = [("Quarterly revenue grew by twelve percent over the previous quarter.\n") * 200,
             ("Operating costs fell because of the new supplier contract signed in May.\n") * 200]
    captured = await _stored_chunks(file_rag, json.dumps({"format": "pages", "pages": pages}), "report.pdf")
    joined = "\n".join(captured["documents"])
    assert '"format"' not in joined and '\\n' not in joined and "PAGE_START" not in joined
    assert "Quarterly revenue" in joined and "Operating costs" in joined
    assert {m.get("page_number") for m in captured["metadatas"]} == {1, 2}
    assert all(m.get("line_start") is None for m in captured["metadatas"])


@pytest.mark.anyio
async def test_store_file_indexes_text_json_without_json_escapes(mock_rag_manager):
    file_rag = FileRAG(mock_rag_manager)
    text = "\n".join(f"Line number {n} of a plain notes file with enough words in it." for n in range(1, 6))
    captured = await _stored_chunks(file_rag, json.dumps({"format": "text", "text": text}), "notes.txt")
    joined = "\n".join(captured["documents"])
    assert '"format"' not in joined and '\\n' not in joined
    assert "Line number 3 of a plain notes file" in joined
    assert min(m["line_start"] for m in captured["metadatas"]) == 1


@pytest.mark.anyio
async def test_store_file_classifies_csv_text_json_as_a_spreadsheet(mock_rag_manager):
    file_rag = FileRAG(mock_rag_manager)
    csv = "\n".join(["name,amount,region"] + [f"customer {n},{n * 10},north" for n in range(1, 30)])
    captured = await _stored_chunks(file_rag, json.dumps({"format": "text", "text": csv}), "sales.csv")
    assert {m["file_type"] for m in captured["metadatas"]} == {"spreadsheet"}
    assert "customer 7,70,north" in "\n".join(captured["documents"])


@pytest.mark.anyio
async def test_store_file_refuses_a_stored_wrapper_with_an_invalid_payload(mock_rag_manager):
    file_rag = FileRAG(mock_rag_manager)
    bad = json.dumps({"format": "pages", "pages": "not a list", "padding": "x" * 80})
    with pytest.raises(ValueError):
        await file_rag.store_file("file1", "chat1", bad, filename="data.json")


@pytest.mark.anyio
async def test_retrieve_for_file_pins_the_files_chat_with_an_and_filter(mock_rag_manager):
    file_rag = FileRAG(mock_rag_manager)
    with patch.object(file_rag, "retrieve_by_query", new=AsyncMock(return_value=[])) as retrieve:
        await file_rag.retrieve_for_file("f1", "q", n_results=3, chat_id="current", file_chat_id="file-chat")
        retrieve.assert_awaited_once_with("q", n_results=3, where={"$and": [{"file_id": "f1"}, {"chat_id": "file-chat"}]},
                                          hybrid=True, chat_id="current")
        retrieve.reset_mock()
        await file_rag.retrieve_for_file("f1", "q")  # without file_chat_id the filter is unchanged
        assert retrieve.call_args.kwargs["where"] == {"file_id": "f1"}


def test_and_filter_returns_only_the_matching_chats_chunks_on_a_real_chroma_store(tmp_path):
    """The `$and` syntax must work on the installed ChromaDB: two chats' chunks, one file id used in both."""
    import chromadb
    client = chromadb.PersistentClient(path=str(tmp_path))
    collection = client.create_collection("chunks", embedding_function=None)
    vec = [1.0, 0.0, 0.0]
    collection.add(ids=["a1", "a2", "b1"], embeddings=[vec, vec, vec], documents=["A chunk 1", "A chunk 2", "B chunk"],
                   metadatas=[{"file_id": "f1", "chat_id": "chat-a"}, {"file_id": "f1", "chat_id": "chat-a"},
                              {"file_id": "f1", "chat_id": "chat-b"}])
    where = {"$and": [{"file_id": "f1"}, {"chat_id": "chat-a"}]}
    assert sorted(collection.get(where=where)["ids"]) == ["a1", "a2"]
    assert sorted(collection.query(query_embeddings=[vec], n_results=3, where=where)["ids"][0]) == ["a1", "a2"]

