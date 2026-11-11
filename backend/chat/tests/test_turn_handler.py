import pytest
import time
import json
import asyncio
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
        
    mock_db.set_turn_duration.return_value = True
    chunks = [c async for c in TurnHandler.handle_turn(chat_id, parent_id, mock_run_fn)]
    assert chunks[:2] == ["chunk1", "chunk2"] and len(chunks) == 3
    assert chunks[2].startswith("data: ") and json.loads(chunks[2][6:])["turn"]["duration_ms"] >= 0
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



@pytest.mark.anyio
async def test_a_finished_turn_sends_and_stores_its_duration_last(mock_db, mock_log_event):
    clock = MagicMock()
    clock.monotonic.side_effect = [100.0, 146.0]
    clock.time.return_value = 5.0
    mock_db.set_turn_duration.return_value = True

    async def run():
        yield "chunk"

    with patch('backend.chat.turn_handler.time', clock):
        chunks = [c async for c in TurnHandler.handle_turn("c1", 7, run)]
    assert chunks[0] == "chunk"
    assert json.loads(chunks[-1][6:]) == {"turn": {"duration_ms": 46000}}
    assert chunks[-1].endswith("\n\n")
    mock_db.set_turn_duration.assert_called_once_with("c1", 7, 46000)


@pytest.mark.anyio
async def test_a_turn_that_raises_stores_and_sends_no_duration(mock_db, mock_log_event):
    async def run():
        yield "chunk"
        raise ValueError("boom")

    chunks = []
    with pytest.raises(ValueError):
        async for c in TurnHandler.handle_turn("c1", 7, run):
            chunks.append(c)
    assert chunks == ["chunk"]
    mock_db.set_turn_duration.assert_not_called()


@pytest.mark.anyio
async def test_a_cancelled_turn_stores_and_sends_no_duration(mock_db, mock_log_event):
    async def run():
        yield "chunk"
        raise asyncio.CancelledError()

    chunks = []
    with pytest.raises(asyncio.CancelledError):
        async for c in TurnHandler.handle_turn("c1", 7, run):
            chunks.append(c)
    assert chunks == ["chunk"]
    mock_db.set_turn_duration.assert_not_called()


@pytest.mark.anyio
async def test_a_failing_duration_write_does_not_break_the_turn(mock_db, mock_log_event):
    mock_db.set_turn_duration.side_effect = RuntimeError("db down")

    async def run():
        yield "chunk"

    chunks = [c async for c in TurnHandler.handle_turn("c1", 7, run)]
    assert chunks == ["chunk"]  # nothing stored, so no event either
    assert any(c.args[0] == "turn_duration_error" for c in mock_log_event.call_args_list)


@pytest.mark.anyio
async def test_no_user_message_means_nothing_to_store_against(mock_db, mock_log_event):
    async def run():
        yield "chunk"

    chunks = [c async for c in TurnHandler.handle_turn("c1", None, run)]
    mock_db.set_turn_duration.assert_not_called()
    assert chunks == ["chunk"]


@pytest.mark.anyio
async def test_a_stopped_turn_that_returns_normally_stores_and_sends_nothing(mock_db, mock_log_event, not_interrupted):
    not_interrupted.is_interrupted.return_value = True

    async def run():
        yield "chunk"  # the handler returns normally after seeing the stop flag

    chunks = [c async for c in TurnHandler.handle_turn("c1", 7, run)]
    assert chunks == ["chunk"]
    mock_db.set_turn_duration.assert_not_called()


@pytest.mark.anyio
async def test_no_event_when_no_row_was_updated(mock_db, mock_log_event):
    mock_db.set_turn_duration.return_value = False

    async def run():
        yield "chunk"

    assert [c async for c in TurnHandler.handle_turn("c1", 7, run)] == ["chunk"]
    assert any(c.args[0] == "turn_duration_not_stored" for c in mock_log_event.call_args_list)
