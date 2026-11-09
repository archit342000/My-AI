import pytest
import asyncio
from unittest.mock import MagicMock, patch, ANY
from backend.task_manager.worker import TaskWorker

@pytest.fixture
def mock_manager():
    return MagicMock()

@pytest.fixture(autouse=True)
def chat_owner():
    """The worker looks up the chat owner in the db; no test here may touch the real database."""
    with patch("backend.database.db.get_chat_owner", return_value="owner-1") as mock:
        yield mock

def test_init(mock_manager):
    def dummy_fn(): pass
    worker = TaskWorker("chat1", dummy_fn, "chat", mock_manager, kw1="v1")
    assert worker.chat_id == "chat1"
    assert worker.execute_fn == dummy_fn
    assert worker.task_type == "chat"
    assert worker.manager == mock_manager
    assert worker.kwargs == {"kw1": "v1"}
    assert worker.name == "TaskWorker-chat1"
    assert worker.daemon is True

def test_run(mock_manager):
    worker = TaskWorker("chat1", lambda: None, "chat", mock_manager)
    
    with patch("backend.task_manager.worker.asyncio.new_event_loop") as mock_new_loop, \
         patch("backend.task_manager.worker.asyncio.set_event_loop") as mock_set_loop, \
         patch("backend.task_manager.worker.TaskExecutor") as mock_executor_cls:
         
         mock_loop = MagicMock()
         mock_new_loop.return_value = mock_loop
         mock_executor_instance = mock_executor_cls.return_value
         
         worker.run()
         
         mock_new_loop.assert_called_once()
         mock_set_loop.assert_called_once_with(mock_loop)
         mock_executor_cls.assert_called_once_with(
            chat_id="chat1",
            execute_fn=worker.execute_fn,
            manager=mock_manager,
            kwargs={}
         )
         mock_loop.run_until_complete.assert_called_once_with(mock_executor_instance.run())
         mock_manager.pop_task.assert_called_once_with("chat1")
         mock_loop.close.assert_called_once()

def test_run_exception(mock_manager):
    worker = TaskWorker("chat1", lambda: None, "chat", mock_manager)
    
    with patch("backend.task_manager.worker.asyncio.new_event_loop") as mock_new_loop, \
         patch("backend.task_manager.worker.asyncio.set_event_loop"), \
         patch("backend.task_manager.worker.TaskExecutor"), \
         patch("backend.task_manager.worker.logger.error") as mock_logger:
         
         mock_loop = MagicMock()
         mock_loop.run_until_complete.side_effect = Exception("error")
         mock_new_loop.return_value = mock_loop
         
         worker.run()
         mock_logger.assert_called_once()
         mock_manager.pop_task.assert_called_once_with("chat1")
         mock_loop.close.assert_called_once()

def test_stop(mock_manager):
    worker = TaskWorker("chat1", lambda: None, "chat", mock_manager)
    worker.loop = MagicMock()
    worker.loop.is_running.return_value = True
    
    worker.stop()
    worker.loop.call_soon_threadsafe.assert_called_once_with(worker._cancel_all_tasks)

def test_stop_not_running(mock_manager):
    worker = TaskWorker("chat1", lambda: None, "chat", mock_manager)
    worker.loop = MagicMock()
    worker.loop.is_running.return_value = False
    
    worker.stop()
    worker.loop.call_soon_threadsafe.assert_not_called()

def test_stop_no_loop(mock_manager):
    worker = TaskWorker("chat1", lambda: None, "chat", mock_manager)
    worker.loop = None
    
    worker.stop()
    # Should not throw

def test_cancel_all_tasks(mock_manager):
    worker = TaskWorker("chat1", lambda: None, "chat", mock_manager)
    worker.loop = MagicMock()
    
    mock_task1 = MagicMock()
    mock_task2 = MagicMock()
    
    with patch("backend.task_manager.worker.asyncio.all_tasks", return_value=[mock_task1, mock_task2]):
        worker._cancel_all_tasks()
        mock_task1.cancel.assert_called_once()
        mock_task2.cancel.assert_called_once()


def test_run_logs_as_the_chat_owner_and_resets_the_user_afterwards(mock_manager):
    from backend.auth.context import current_user_id
    seen = []
    worker = TaskWorker("chat1", lambda: None, "chat", mock_manager)

    with patch("backend.task_manager.worker.TaskExecutor"), \
         patch("backend.task_manager.worker.asyncio.new_event_loop") as mock_new_loop, \
         patch("backend.task_manager.worker.asyncio.set_event_loop"):
        mock_loop = MagicMock()
        mock_loop.run_until_complete.side_effect = lambda _coro: seen.append(current_user_id())
        mock_new_loop.return_value = mock_loop
        worker.run()

    assert seen == ["owner-1"]
    assert current_user_id() is None


def test_run_for_a_chat_without_an_owner_runs_without_a_user(mock_manager, chat_owner):
    from backend.auth.context import current_user_id
    chat_owner.return_value = None
    seen = []
    worker = TaskWorker("gone", lambda: None, "chat", mock_manager)
    with patch("backend.task_manager.worker.TaskExecutor"), \
         patch("backend.task_manager.worker.asyncio.new_event_loop") as mock_new_loop, \
         patch("backend.task_manager.worker.asyncio.set_event_loop"):
        mock_loop = MagicMock()
        mock_loop.run_until_complete.side_effect = lambda _coro: seen.append(current_user_id())
        mock_new_loop.return_value = mock_loop
        worker.run()
    assert seen == [None]


def test_run_still_cleans_up_when_the_owner_lookup_raises(mock_manager, chat_owner):
    chat_owner.side_effect = RuntimeError("database is locked")
    worker = TaskWorker("chat1", lambda: None, "chat", mock_manager)
    with patch("backend.task_manager.worker.TaskExecutor"), \
         patch("backend.task_manager.worker.asyncio.new_event_loop") as mock_new_loop, \
         patch("backend.task_manager.worker.asyncio.set_event_loop"):
        mock_loop = MagicMock()
        mock_new_loop.return_value = mock_loop
        worker.run()
    mock_manager.pop_task.assert_called_once_with("chat1")  # the chat is not left registered as running
    mock_loop.close.assert_called_once()
