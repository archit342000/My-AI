import pytest
import threading
import time
from unittest.mock import MagicMock, patch
from backend.task_manager.manager import TaskManager

# The `manager` fixture patches threading.Thread; keep a handle on the real class for the race test.
RealThread = threading.Thread

@pytest.fixture
def mock_worker_class():
    with patch("backend.task_manager.manager.TaskWorker") as mock_worker:
        yield mock_worker

@pytest.fixture
def manager(mock_worker_class):
    # disable cleanup thread by mocking it
    with patch("threading.Thread") as mock_thread:
        mgr = TaskManager()
        yield mgr

def test_init():
    with patch("threading.Thread") as mock_thread:
        mgr = TaskManager()
        assert mgr._active_tasks == {}
        assert isinstance(mgr.interrupted_tasks, set)
        assert mgr._cleanup_running is True
        mock_thread.assert_called_once()

def test_start_task(manager, mock_worker_class):
    def dummy_fn(): pass
    
    # Task not running
    res = manager.start_task("chat1", dummy_fn)
    assert res is True
    mock_worker_class.assert_called_once()
    mock_worker_instance = mock_worker_class.return_value
    mock_worker_instance.start.assert_called_once()
    assert "chat1" in manager._active_tasks

    # Task already running
    mock_worker_instance.is_alive.return_value = True
    res2 = manager.start_task("chat1", dummy_fn)
    assert res2 is False

    # Task not alive but in dict -> should pop
    mock_worker_instance.is_alive.return_value = False
    res3 = manager.start_task("chat1", dummy_fn)
    assert res3 is True

def test_start_task_removes_from_interrupted(manager, mock_worker_class):
    manager.interrupted_tasks.add("chat1")
    manager.start_task("chat1", lambda: None)
    assert "chat1" not in manager.interrupted_tasks

def test_stop_task(manager):
    worker_mock = MagicMock()
    manager._active_tasks["chat1"] = worker_mock
    manager.stop_task("chat1")
    assert "chat1" in manager.interrupted_tasks
    worker_mock.stop.assert_called_once()

def test_is_task_running(manager):
    worker_mock = MagicMock()
    worker_mock.is_alive.return_value = True
    manager._active_tasks["chat1"] = worker_mock
    assert manager.is_task_running("chat1") is True
    
    worker_mock.is_alive.return_value = False
    assert manager.is_task_running("chat1") is False
    
    assert manager.is_task_running("chat2") is False

def test_pop_task(manager):
    manager._active_tasks["chat1"] = "worker"
    manager.pop_task("chat1")
    assert "chat1" not in manager._active_tasks

def test_is_interrupted(manager):
    manager.interrupted_tasks.add("chat1")
    assert manager.is_interrupted("chat1") is True
    assert manager.is_interrupted("chat2") is False

def test_run_cache_cleanup(manager):
    manager._cleanup_running = False # To stop it immediately if we call it
    
    # Test one iteration manually
    manager._cleanup_running = True
    manager._active_tasks["chat1"] = MagicMock()
    
    def side_effect(*args, **kwargs):
        manager._cleanup_running = False
        
    with patch("backend.task_manager.manager.cache_system") as mock_cache_system, \
         patch("time.sleep", side_effect=side_effect), \
         patch("backend.file_system.channel.FileSystemChannelManager.cleanup_stale_channels") as mock_stale:
        manager._run_cache_cleanup()
        mock_cache_system.cleanup_expired.assert_called_once_with(active_chat_ids={"chat1"})
        mock_stale.assert_called_once()

def test_run_cache_cleanup_exception(manager):
    manager._cleanup_running = True
    def side_effect(*args, **kwargs):
        manager._cleanup_running = False
    
    with patch("backend.task_manager.manager.cache_system.cleanup_expired", side_effect=Exception("error")), \
         patch("backend.task_manager.manager.logger.error") as mock_logger, \
         patch("time.sleep", side_effect=side_effect):
        manager._run_cache_cleanup()
        mock_logger.assert_called_with("Cache cleanup error: error")

def test_run_cache_cleanup_fs_channel_exception(manager):
    manager._cleanup_running = True
    def side_effect(*args, **kwargs):
        manager._cleanup_running = False
    
    with patch("backend.task_manager.manager.cache_system.cleanup_expired"), \
         patch("backend.file_system.channel.FileSystemChannelManager.cleanup_stale_channels", side_effect=Exception("fs error")), \
         patch("backend.task_manager.manager.logger.error") as mock_logger, \
         patch("time.sleep", side_effect=side_effect):
        manager._run_cache_cleanup()
        mock_logger.assert_called_with("FileSystem channel cleanup error: fs error")

@pytest.fixture(autouse=True)
def chat_owner():
    """recover_tasks looks the owner up in the db; keep every test in this file off the real database."""
    with patch("backend.database.db.get_chat_owner", return_value="owner-1") as mock, \
         patch("backend.task_manager.manager.log_event"):  # never write to the real log directory
        yield mock

def test_recover_tasks():
    with patch("threading.Thread"), \
         patch("os.path.exists", return_value=True), \
         patch("os.listdir", return_value=["task1.json"]), \
         patch("builtins.open") as mock_open, \
         patch("json.load", return_value={"status": "running", "chat_id": "task1"}), \
         patch("json.dump") as mock_dump:
        
        mgr = TaskManager()
        mgr.recover_tasks()
        mock_dump.assert_called_once()
        args, _ = mock_dump.call_args
        assert args[0]["status"] == "needs_resume"

def test_recover_tasks_no_dir():
    with patch("threading.Thread"), \
         patch("os.path.exists", return_value=False):
        mgr = TaskManager()
        mgr.recover_tasks() # Should return early
        
def test_recover_tasks_exception():
    with patch("threading.Thread"), \
         patch("os.path.exists", return_value=True), \
         patch("os.listdir", return_value=["task1.json"]), \
         patch("builtins.open", side_effect=Exception("error")), \
         patch("os.remove") as mock_remove:
        
        mgr = TaskManager()
        mgr.recover_tasks()
        mock_remove.assert_called_once()

def test_recover_tasks_ignore_non_json():
    with patch("threading.Thread"), \
         patch("os.path.exists", return_value=True), \
         patch("os.listdir", return_value=["task1.txt"]):
        
        mgr = TaskManager()
        with patch("builtins.open") as mock_open:
            mgr.recover_tasks()
            mock_open.assert_not_called()

def test_recover_tasks_filesystem_error_resilience():
    with patch("threading.Thread"), \
         patch("os.path.exists", side_effect=PermissionError("Permission denied")), \
         patch("backend.task_manager.manager.logger.error") as mock_logger:
        
        mgr = TaskManager()
        mgr.recover_tasks()
        mock_logger.assert_called_with("Failed to check task persistence directory: Permission denied")

def test_recover_tasks_listdir_error_resilience():
    with patch("threading.Thread"), \
         patch("os.path.exists", return_value=True), \
         patch("os.listdir", side_effect=PermissionError("Listdir failed")), \
         patch("backend.task_manager.manager.logger.error") as mock_logger:
        
        mgr = TaskManager()
        mgr.recover_tasks()
        mock_logger.assert_called_with("Failed to list tasks persistence directory: Listdir failed")


def test_claim_turn_and_release(manager):
    assert manager.claim_turn("c1") is True
    assert manager.claim_turn("c1") is False
    assert manager.claim_turn("c2") is True  # other chats are independent
    manager.release_turn_claim("c1")
    assert manager.claim_turn("c1") is True
    manager.release_turn_claim("never-claimed")  # no-op


def test_claim_turn_refused_while_task_alive(manager, mock_worker_class):
    mock_worker_class.return_value.is_alive.return_value = True
    assert manager.start_task("c1", lambda: None) is True
    assert manager.claim_turn("c1") is False
    mock_worker_class.return_value.is_alive.return_value = False
    assert manager.claim_turn("c1") is True


def test_claim_turn_only_one_concurrent_claimant_wins(manager):
    # Smoke test: under the GIL it would usually pass even without the lock, so it does not prove
    # the locking; that is established by claim_turn doing its check and add inside `self._lock`.
    workers = 8
    barrier = threading.Barrier(workers)
    results = []

    def claim():
        barrier.wait()
        results.append(manager.claim_turn("race-chat"))

    threads = [RealThread(target=claim) for _ in range(workers)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert results.count(True) == 1
    assert results.count(False) == workers - 1


def _recover_one_task(chat_id, owners):
    """Run recover_tasks over one running task and return the user id each log_event call saw."""
    from backend.auth.context import current_user_id
    seen = []
    with patch("threading.Thread"), \
         patch("os.path.exists", return_value=True), \
         patch("os.listdir", return_value=[f"{chat_id}.json"]), \
         patch("builtins.open"), \
         patch("json.load", return_value={"status": "running", "chat_id": chat_id}), \
         patch("json.dump"), \
         patch("backend.task_manager.manager.log_event",
               side_effect=lambda name, data: seen.append((name, data, current_user_id()))):
        TaskManager().recover_tasks()
    return seen


def test_recover_tasks_logs_task_recovered_as_the_chat_owner():
    from backend.auth.context import current_user_id
    assert _recover_one_task("chat1", None) == [("task_recovered", {"chat_id": "chat1"}, "owner-1")]
    assert current_user_id() is None  # reset afterwards


def test_recover_tasks_for_a_deleted_chat_logs_without_a_user(chat_owner):
    chat_owner.return_value = None
    assert _recover_one_task("gone", None) == [("task_recovered", {"chat_id": "gone"}, None)]


def test_recover_tasks_keeps_the_resume_state_when_the_owner_lookup_fails(chat_owner):
    chat_owner.side_effect = RuntimeError("database is locked")
    with patch("threading.Thread"), \
         patch("os.path.exists", return_value=True), \
         patch("os.listdir", return_value=["task1.json"]), \
         patch("builtins.open"), \
         patch("json.load", return_value={"status": "running", "chat_id": "task1"}), \
         patch("json.dump") as mock_dump, \
         patch("os.remove") as mock_remove, \
         patch("backend.task_manager.manager.log_event"):
        TaskManager().recover_tasks()
    assert mock_dump.call_args.args[0]["status"] == "needs_resume"
    mock_remove.assert_not_called()  # a failed owner lookup must not delete the state file just written
