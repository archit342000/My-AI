import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from backend.task_manager.executor import TaskExecutor

@pytest.fixture
def mock_manager():
    manager = MagicMock()
    manager.is_interrupted.return_value = False
    return manager

@pytest.fixture
def kwargs():
    return {"model_name": "test-model"}

def test_init(mock_manager, kwargs):
    def dummy_fn(): pass
    executor = TaskExecutor("chat1", dummy_fn, mock_manager, kwargs)
    assert executor.chat_id == "chat1"
    assert executor.execute_fn == dummy_fn
    assert executor.manager == mock_manager
    assert executor.kwargs == kwargs

@pytest.mark.anyio
async def test_run_async_gen_func(mock_manager, kwargs):
    # This is an async generator function
    async def dummy_gen(**kw):
        yield "chunk1"
        yield "chunk2"
    
    executor = TaskExecutor("chat1", dummy_gen, mock_manager, kwargs)
    with patch("backend.task_manager.executor.response_cache") as mock_cache:
        with patch.object(executor, "_save_task_state") as mock_save, \
             patch.object(executor, "_clear_task_state") as mock_clear:
            await executor.run()
            mock_cache.initialize_chat.assert_called_once_with("chat1", overwrite=True)
            mock_save.assert_called_once_with("running")
            mock_clear.assert_called_once()
            mock_cache.append_chunk.assert_any_call("chat1", "chunk1")
            mock_cache.append_chunk.assert_any_call("chat1", "chunk2")
            mock_cache.append_chunk.assert_any_call("chat1", "[[DONE]]")
            mock_cache.clear_sse_chunks.assert_called_once_with("chat1")

@pytest.mark.anyio
async def test_run_coroutine_returning_list(mock_manager, kwargs):
    # This is a coroutine function
    async def dummy_coro(**kw):
        return ["chunk1", "chunk2"]
        
    executor = TaskExecutor("chat1", dummy_coro, mock_manager, kwargs)
    with patch("backend.task_manager.executor.response_cache") as mock_cache:
        with patch.object(executor, "_save_task_state"), \
             patch.object(executor, "_clear_task_state"):
            await executor.run()
            mock_cache.append_chunk.assert_any_call("chat1", "chunk1")
            mock_cache.append_chunk.assert_any_call("chat1", "chunk2")

@pytest.mark.anyio
async def test_run_sync_generator(mock_manager, kwargs):
    def dummy_gen(**kw):
        yield "chunk1"
        yield "chunk2"
    
    executor = TaskExecutor("chat1", dummy_gen, mock_manager, kwargs)
    with patch("backend.task_manager.executor.response_cache") as mock_cache:
        with patch.object(executor, "_save_task_state"), \
             patch.object(executor, "_clear_task_state"):
            await executor.run()
            mock_cache.append_chunk.assert_any_call("chat1", "chunk1")
            mock_cache.append_chunk.assert_any_call("chat1", "chunk2")

@pytest.mark.anyio
async def test_run_cancelled(mock_manager, kwargs):
    async def dummy_gen(**kw):
        raise asyncio.CancelledError()
        yield "chunk"
    
    executor = TaskExecutor("chat1", dummy_gen, mock_manager, kwargs)
    with patch("backend.task_manager.executor.response_cache") as mock_cache, \
         patch("backend.task_manager.executor.log_event") as mock_log:
        with patch.object(executor, "_save_task_state"), \
             patch.object(executor, "_clear_task_state"):
            await executor.run()
            mock_log.assert_called_once_with("task_cancelled", {"chat_id": "chat1"})
            mock_cache.append_chunk.assert_any_call("chat1", "[[ERROR]]")

@pytest.mark.anyio
async def test_run_exception(mock_manager, kwargs):
    async def dummy_gen(**kw):
        raise ValueError("test error")
        yield "chunk"
    
    executor = TaskExecutor("chat1", dummy_gen, mock_manager, kwargs)
    with patch("backend.task_manager.executor.response_cache") as mock_cache, patch("backend.task_manager.executor.log_event") as mock_log:
        with patch.object(executor, "_save_task_state"), \
             patch.object(executor, "_clear_task_state"):
            await executor.run()
            mock_cache.append_chunk.assert_any_call("chat1", f"data: {json.dumps({'error': 'Something went wrong while answering. Try sending again.'})}\n\n")
            assert not any('test error' in str(c) for c in mock_cache.append_chunk.call_args_list)
            assert any(c.args[0] == 'task_executor_error' and 'test error' in c.args[1]['error'] for c in mock_log.call_args_list)
            mock_cache.append_chunk.assert_any_call("chat1", "[[ERROR]]")

def test_save_task_state(mock_manager, kwargs):
    executor = TaskExecutor("chat1", lambda: None, mock_manager, kwargs)
    with patch("os.makedirs") as mock_makedirs, \
         patch("builtins.open") as mock_open, \
         patch("json.dump") as mock_dump:
        executor._save_task_state("running")
        mock_makedirs.assert_called_once()
        mock_open.assert_called_once()
        mock_dump.assert_called_once()

def test_save_task_state_exception(mock_manager, kwargs):
    executor = TaskExecutor("chat1", lambda: None, mock_manager, kwargs)
    with patch("os.makedirs"), \
         patch("builtins.open", side_effect=Exception("error")), \
         patch("backend.task_manager.executor.logger.error") as mock_logger:
        executor._save_task_state("running")
        mock_logger.assert_called_once()

def test_clear_task_state(mock_manager, kwargs):
    executor = TaskExecutor("chat1", lambda: None, mock_manager, kwargs)
    with patch("os.path.exists", return_value=True), \
         patch("os.remove") as mock_remove:
        executor._clear_task_state()
        mock_remove.assert_called_once()

def test_clear_task_state_exception(mock_manager, kwargs):
    executor = TaskExecutor("chat1", lambda: None, mock_manager, kwargs)
    with patch("os.path.exists", return_value=True), \
         patch("os.remove", side_effect=Exception("error")):
        executor._clear_task_state()

@pytest.mark.anyio
async def test_process_chunk(mock_manager, kwargs):
    executor = TaskExecutor("chat1", lambda: None, mock_manager, kwargs)
    with patch("backend.task_manager.executor.response_cache") as mock_cache:
        await executor._process_chunk("chunk_data")
        mock_cache.append_chunk.assert_called_once_with("chat1", "chunk_data")

@pytest.mark.anyio
async def test_process_chunk_interrupted(mock_manager, kwargs):
    mock_manager.is_interrupted.return_value = True
    executor = TaskExecutor("chat1", lambda: None, mock_manager, kwargs)
    with pytest.raises(asyncio.CancelledError, match="Task interrupted by manager signal."):
        await executor._process_chunk("chunk_data")
