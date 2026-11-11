import json
import pytest
import time
from unittest.mock import MagicMock, patch, AsyncMock
from backend.chat.turn_handler import TurnHandler

@pytest.fixture
def mock_db():
    with patch('backend.chat.turn_handler.db') as mock:
        yield mock

@pytest.fixture(autouse=True)
def not_interrupted():
    with patch('backend.chat.turn_handler.task_manager') as tm:
        tm.is_interrupted.return_value = False
        yield tm

@pytest.fixture
def mock_log_event():
    with patch('backend.chat.turn_handler.log_event') as mock:
        yield mock

@pytest.mark.anyio
async def test_turn_handler_handle_turn(mock_db, mock_log_event):
    chat_id = "test_chat"
    parent_id = 1
    
    async def mock_run_fn():
        yield "chunk1"
        yield "chunk2"
        
    chunks = []
    async for chunk in TurnHandler.handle_turn(chat_id, parent_id, mock_run_fn):
        chunks.append(chunk)
        
    assert chunks == ["chunk1", "chunk2"]
    mock_db.update_chat.assert_called_once()
    mock_log_event.assert_any_call("turn_handler_start", {"chat_id": chat_id, "parent_id": parent_id, "model": None})
    mock_log_event.assert_any_call("turn_persistence_finalized", {"chat_id": chat_id, "parent_id": parent_id})
    # Ensure turn_handler_end is called
    assert any(call.args[0] == "turn_handler_end" for call in mock_log_event.call_args_list)

@pytest.mark.anyio
async def test_turn_handler_error(mock_db, mock_log_event):
    chat_id = "test_chat"
    parent_id = 1
    
    async def mock_run_fn_error():
        yield "chunk1"
        raise ValueError("Simulated error")
        
    with pytest.raises(ValueError, match="Simulated error"):
        async for _ in TurnHandler.handle_turn(chat_id, parent_id, mock_run_fn_error):
            pass
            
    mock_log_event.assert_any_call("turn_handler_error", {"chat_id": chat_id, "error": "Simulated error"})
    # Ensure end event is also fired
    assert any(call.args[0] == "turn_handler_end" for call in mock_log_event.call_args_list)

def test_persist_final_state_success(mock_db, mock_log_event):
    TurnHandler._persist_final_state("chat_123", 456, "some_model")
    mock_db.update_chat.assert_called_once()
    assert mock_db.update_chat.call_args[0][0] == "chat_123"
    mock_log_event.assert_called_with("turn_persistence_finalized", {
        "chat_id": "chat_123",
        "parent_id": 456
    })

def test_persist_final_state_error(mock_db, mock_log_event, caplog):
    mock_db.update_chat.side_effect = Exception("DB error")
    TurnHandler._persist_final_state("chat_123", 456, "some_model")
    
    mock_log_event.assert_called_with("turn_persistence_error", {
        "chat_id": "chat_123", 
        "error": "DB error"
    })

@pytest.mark.anyio
async def test_turn_handler_cancellation_resilience(mock_db, mock_log_event):
    import asyncio
    chat_id = "test_chat"
    parent_id = 1
    
    # Mock generator that simulates a task cancellation
    async def mock_run_fn_cancelled():
        yield "chunk1"
        raise asyncio.CancelledError("Turn cancelled")
        
    with pytest.raises(asyncio.CancelledError):
        async for chunk in TurnHandler.handle_turn(chat_id, parent_id, mock_run_fn_cancelled):
            assert chunk == "chunk1"
            
    # Verify that turn_handler_end is still executed in the finally block
    assert any(call.args[0] == "turn_handler_end" for call in mock_log_event.call_args_list)
    # Ensure update_chat (which is post-stream persistence) is NOT called because of the cancellation
    mock_db.update_chat.assert_not_called()



# ---- cited sources ---------------------------------------------------------------------------------------------

def _registry():
    from backend.chat.sources import SourceRegistry
    r = SourceRegistry()
    r.add("web", "A", "https://a")
    r.add("web", "B", "https://b")
    r.add("file", "a.py", "a.py", "lines 1-5")
    return r


async def _run(mock_db, rows, registry, run=None):
    mock_db.get_messages.return_value = rows

    async def default():
        yield "chunk"

    return [c async for c in TurnHandler.handle_turn("c1", 7, run or default, sources=registry)]


@pytest.mark.anyio
async def test_cited_sources_are_stored_on_the_last_assistant_row_and_sent(mock_db, mock_log_event):
    rows = [{"id": 6, "role": "assistant", "content": "old [[1]]", "parent_type": "main"},
            {"id": 8, "role": "assistant", "content": "Looking [[2]]", "parent_type": "main"},
            {"id": 9, "role": "tool", "content": "x"},
            {"id": 10, "role": "assistant", "content": "Answer [[3]] and [[2]] and [[99]]", "parent_type": "main"}]
    chunks = await _run(mock_db, rows, _registry())
    assert chunks[0] == "chunk" and chunks[-1].startswith("data: ") and chunks[-1].endswith("\n\n")
    sent = json.loads(chunks[-1][6:])["sources"]
    assert [s["n"] for s in sent] == [2, 3] and sent[1] == {"n": 3, "kind": "file", "title": "a.py", "locator": "a.py", "detail": "lines 1-5"}
    stored = mock_db.add_collection.call_args.kwargs
    assert stored["parent_message_id"] == 10 and stored["collection_type"] == "sources" and stored["items"] == sent and stored["overwrite"] is True


@pytest.mark.anyio
async def test_an_old_turns_number_resolves_to_its_earlier_source(mock_db, mock_log_event):
    rows = [{"id": 8, "role": "assistant", "content": "As before [[1]]", "parent_type": "main"}]
    chunks = await _run(mock_db, rows, _registry())
    assert [s["title"] for s in json.loads(chunks[-1][6:])["sources"]] == ["A"]


@pytest.mark.anyio
async def test_an_answer_without_markers_sends_and_stores_nothing(mock_db, mock_log_event):
    chunks = await _run(mock_db, [{"id": 8, "role": "assistant", "content": "plain answer", "parent_type": "main"}], _registry())
    assert chunks == ["chunk"]
    mock_db.add_collection.assert_not_called()


@pytest.mark.anyio
async def test_no_registry_or_no_new_answer_row_changes_nothing(mock_db, mock_log_event):
    assert await _run(mock_db, [], None) == ["chunk"]
    assert await _run(mock_db, [{"id": 3, "role": "assistant", "content": "[[1]] earlier turn", "parent_type": "main"}], _registry()) == ["chunk"]
    mock_db.add_collection.assert_not_called()


@pytest.mark.anyio
async def test_a_failed_turn_sends_and_stores_no_sources(mock_db, mock_log_event):
    async def run():
        yield "chunk"
        raise ValueError("boom")

    mock_db.get_messages.return_value = [{"id": 8, "role": "assistant", "content": "[[1]]", "parent_type": "main"}]
    with pytest.raises(ValueError):
        async for _ in TurnHandler.handle_turn("c1", 7, run, sources=_registry()):
            pass
    mock_db.add_collection.assert_not_called()


@pytest.mark.anyio
async def test_a_stopped_turn_that_returns_normally_sends_and_stores_no_sources(mock_db, mock_log_event, not_interrupted):
    not_interrupted.is_interrupted.return_value = True
    chunks = await _run(mock_db, [{"id": 8, "role": "assistant", "content": "[[1]]", "parent_type": "main"}], _registry())
    assert chunks == ["chunk"]
    mock_db.add_collection.assert_not_called()


@pytest.mark.anyio
async def test_the_registry_is_not_passed_on_to_run_fn_and_an_unexpected_storage_failure_propagates(mock_db, mock_log_event):
    seen = {}

    async def run(*args, **kwargs):
        seen["kwargs"] = kwargs
        yield "chunk"

    mock_db.get_messages.return_value = [{"id": 8, "role": "assistant", "content": "[[1]]", "parent_type": "main"}]
    mock_db.add_collection.side_effect = RuntimeError("db down")
    # RuntimeError is not an expected storage error: it propagates like any turn failure
    with pytest.raises(RuntimeError):
        async for _ in TurnHandler.handle_turn("c1", 7, run, sources=_registry(), extra=1):
            pass
    assert seen["kwargs"] == {"extra": 1}


@pytest.mark.anyio
async def test_a_database_error_while_storing_cited_sources_is_logged_and_the_answer_still_finishes(mock_db, mock_log_event):
    import sqlite3
    mock_db.get_messages.return_value = [{"id": 8, "role": "assistant", "content": "[[1]]", "parent_type": "main"}]
    mock_db.add_collection.side_effect = sqlite3.OperationalError("locked")
    chunks = [c async for c in TurnHandler.handle_turn("c1", 7, _one_chunk, sources=_registry())]
    assert chunks == ["chunk"]
    assert any(c.args[0] == "turn_sources_error" for c in mock_log_event.call_args_list)


async def _one_chunk():
    yield "chunk"


def test_message_ids_are_compared_as_integers_and_odd_ids_never_count_as_later():
    from backend.chat.turn_handler import _id_after
    assert _id_after(10, 7) and _id_after("10", 7) and not _id_after(7, 7) and not _id_after("abc", 7) and not _id_after(None, 7)
