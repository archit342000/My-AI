import asyncio
import threading
from contextlib import asynccontextmanager
import pytest
from unittest.mock import MagicMock, patch
from backend.tools.implementations.code_executor import run_code, run_file, install_packages, list_packages

@pytest.fixture
def mock_db():
    with patch('backend.tools.implementations.code_executor.db') as mock:
        mock.get_setting.side_effect = lambda key, default=None: default
        yield mock

@pytest.fixture
def mock_requests():
    with patch('backend.tools.implementations.code_executor.requests') as mock:
        yield mock

@pytest.mark.asyncio
async def test_run_code_safe(mock_db, mock_requests):
    # Setup mock response
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "stdout": "hello world\n",
        "stderr": "",
        "exit_code": 0,
        "execution_time_ms": 15,
        "timed_out": False
    }
    mock_requests.post.return_value = mock_resp

    res = await run_code(
        code="print('hello world')",
        language="python",
        chat_id="chat123",
        tool_call_id="tc1"
    )

    assert "Exit Code:** 0" in res
    assert "Time:** 15ms" in res
    assert "hello world" in res
    mock_db.add_code_execution_record.assert_called_once()

@pytest.mark.asyncio
async def test_run_code_dangerous_denied(mock_db, mock_requests):
    # Dangerous code (import os) triggers clarification
    with patch('backend.tools.implementations.code_executor.request_clarification', return_value="No, cancel") as mock_clarify:
        res = await run_code(
            code="import os\nos.system('rm -rf /')",
            language="python",
            chat_id="chat123",
            tool_call_id="tc1"
        )
        assert res == "Execution cancelled by user."
        mock_clarify.assert_called_once()
        mock_requests.post.assert_not_called()

@pytest.mark.asyncio
async def test_run_code_dangerous_approved(mock_db, mock_requests):
    # Setup mock response
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "stdout": "dangerous output\n",
        "stderr": "",
        "exit_code": 0,
        "execution_time_ms": 20,
        "timed_out": False
    }
    mock_requests.post.return_value = mock_resp

    with patch('backend.tools.implementations.code_executor.request_clarification', return_value="Yes, run it"):
        res = await run_code(
            code="import os\nos.system('echo dangerous')",
            language="python",
            chat_id="chat123",
            tool_call_id="tc1"
        )
        assert "dangerous output" in res
        mock_requests.post.assert_called_once()

@pytest.mark.asyncio
async def test_install_packages_approved(mock_db, mock_requests):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "success": True,
        "stdout": "Successfully installed numpy",
        "stderr": ""
    }
    mock_requests.post.return_value = mock_resp

    with patch('backend.tools.implementations.code_executor.request_clarification', return_value="Yes, install"):
        res = await install_packages(
            packages=["numpy"],
            package_manager="pip",
            chat_id="chat123",
            tool_call_id="tc1"
        )
        assert "Successfully installed packages" in res
        assert "numpy" in res

@pytest.mark.asyncio
async def test_list_packages(mock_db, mock_requests):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "packages": [{"name": "numpy", "version": "1.26.0"}],
        "package_manager": "pip"
    }
    mock_requests.get.return_value = mock_resp

    res = await list_packages(
        package_manager="pip",
        chat_id="chat123",
        tool_call_id="tc1"
    )
    assert "numpy" in res
    assert "1.26.0" in res


@pytest.mark.asyncio
async def test_run_file(mock_db, mock_requests):
    import tempfile
    import shutil
    import os

    # Create temp directory layout representing chat root
    temp_chat_root = tempfile.mkdtemp()

    try:
        # Write files inside temp root
        os.makedirs(os.path.join(temp_chat_root, "utils"), exist_ok=True)
        main_py_path = os.path.join(temp_chat_root, "main.py")
        with open(main_py_path, "w") as f:
            f.write("from utils.math import add\nprint(add(1, 2))")

        helper_py_path = os.path.join(temp_chat_root, "utils", "math.py")
        with open(helper_py_path, "w") as f:
            f.write("def add(a, b): return a + b")

        # Mock resolve_owner_and_physical_path
        with patch('backend.tools.implementations.code_executor.resolve_owner_and_physical_path') as mock_resolve:
            mock_resolve.side_effect = lambda chat_id, path, **kwargs: (
                chat_id, None, os.path.join(temp_chat_root, path) if path else temp_chat_root
            )

            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "stdout": "3\n",
                "stderr": "",
                "exit_code": 0,
                "execution_time_ms": 12,
                "timed_out": False
            }
            mock_requests.post.return_value = mock_resp

            res = await run_file(
                path="main.py",
                chat_id="chat123",
                tool_call_id="tc1"
            )

            assert "main.py" in res
            assert "Exit Code:** 0" in res
            assert "3" in res

            # Verify that BOTH files were gathered and sent to the endpoint
            called_args, called_kwargs = mock_requests.post.call_args
            files_sent = called_kwargs["json"]["files"]
            assert len(files_sent) == 2
            paths_sent = {f["path"] for f in files_sent}
            assert "main.py" in paths_sent
            assert "utils/math.py" in paths_sent or "utils\\math.py" in paths_sent
    finally:
        shutil.rmtree(temp_chat_root)



# ---- resolve_run_target and the run_file error strings ---------------------------------------------------------

def test_resolve_run_target_returns_the_paths_for_an_existing_file(tmp_path):
    from backend.tools.implementations.code_executor import resolve_run_target
    (tmp_path / "main.py").write_text("print(1)")
    with patch('backend.tools.implementations.code_executor.resolve_owner_and_physical_path') as resolve:
        resolve.side_effect = lambda chat_id, path, **kw: (chat_id, None, str(tmp_path / path) if path else str(tmp_path))
        assert resolve_run_target("c1", "main.py") == (str(tmp_path / "main.py"), str(tmp_path))


def test_resolve_run_target_raises_for_a_missing_file_and_lets_resolver_errors_through(tmp_path):
    from backend.tools.implementations.code_executor import resolve_run_target
    with patch('backend.tools.implementations.code_executor.resolve_owner_and_physical_path') as resolve:
        resolve.side_effect = lambda chat_id, path, **kw: (chat_id, None, str(tmp_path / path) if path else str(tmp_path))
        with pytest.raises(FileNotFoundError):
            resolve_run_target("c1", "nope.py")
        resolve.side_effect = ValueError("reserved path")
        with pytest.raises(ValueError):
            resolve_run_target("c1", "workspace/x.py")
        resolve.side_effect = RuntimeError("db down")
        with pytest.raises(RuntimeError):
            resolve_run_target("c1", "x.py")


def test_run_file_for_a_missing_file_still_returns_the_agent_error_string(tmp_path):
    import asyncio
    with patch('backend.tools.implementations.code_executor.resolve_owner_and_physical_path') as resolve:
        resolve.side_effect = lambda chat_id, path, **kw: (chat_id, None, str(tmp_path / path) if path else str(tmp_path))
        res = asyncio.run(run_file(path="nope.py", chat_id="c1", tool_call_id="tc"))
    assert res == "Error: File 'nope.py' does not exist."


def test_run_file_runner_unavailable_message_has_no_exception_text(tmp_path, mock_db, mock_requests):
    import asyncio
    (tmp_path / "main.py").write_text("print(1)")
    mock_requests.post.side_effect = RuntimeError("connect to 10.1.2.3:8100 refused")
    with patch('backend.tools.implementations.code_executor.resolve_owner_and_physical_path') as resolve:
        resolve.side_effect = lambda chat_id, path, **kw: (chat_id, None, str(tmp_path / path) if path else str(tmp_path))
        res = asyncio.run(run_file(path="main.py", chat_id="c1", tool_call_id="tc"))
    assert res == "Error: Failed to execute file. Code runner service is unavailable."
    assert "10.1.2.3" not in res


def test_run_file_non_input_resolver_failure_keeps_its_detail_out_of_the_result():
    import asyncio
    with patch('backend.tools.implementations.code_executor.resolve_owner_and_physical_path', side_effect=RuntimeError("db at /secret/chats.db locked")):
        res = asyncio.run(run_file(path="a.py", chat_id="c1", tool_call_id="tc"))
    assert res == "Error: Failed to resolve file path."


def test_run_file_invalid_path_keeps_the_resolvers_message_for_the_agent():
    import asyncio
    with patch('backend.tools.implementations.code_executor.resolve_owner_and_physical_path', side_effect=ValueError("reserved path 'workspace/'")):
        res = asyncio.run(run_file(path="workspace/a.py", chat_id="c1", tool_call_id="tc"))
    assert res == "Error: Failed to resolve file path: reserved path 'workspace/'"


def test_install_packages_reports_a_rejected_package_request_clearly(mock_db, mock_requests):
    import asyncio
    from backend.tools.implementations.code_executor import install_packages
    mock_requests.post.return_value = MagicMock(status_code=400, json=lambda: {"detail": "Invalid package: '--index-url=x'"})
    with patch('backend.tools.implementations.code_executor.request_clarification', return_value="Yes, install"):
        res = asyncio.run(install_packages(packages=["--index-url=x"], package_manager="pip", chat_id="c1", tool_call_id="tc"))
    assert res == "Error: Invalid package request: Invalid package: '--index-url=x'"
    assert "unavailable" not in res


def test_install_packages_other_failures_still_say_the_service_is_unavailable(mock_db, mock_requests):
    import asyncio
    from backend.tools.implementations.code_executor import install_packages
    mock_requests.post.side_effect = RuntimeError("boom")
    with patch('backend.tools.implementations.code_executor.request_clarification', return_value="Yes, install"):
        res = asyncio.run(install_packages(packages=["requests"], package_manager="pip", chat_id="c1", tool_call_id="tc"))
    assert res.startswith("Error: Failed to install packages. Code runner service is unavailable")


# ---- timeout clamping ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("stored,expected", [(30, 30), (500, 120), (120, 120), (0, 1), (-5, 1), ("45", 45), ("999", 120)])
def test_effective_code_runner_timeout_is_clamped(stored, expected):
    from backend.tools.implementations.code_executor import effective_code_runner_timeout
    with patch('backend.tools.implementations.code_executor.db.get_setting', return_value=stored), \
         patch('backend.tools.implementations.code_executor.config.CODE_RUNNER_MAX_TIMEOUT', 120):
        assert effective_code_runner_timeout() == expected


@pytest.mark.parametrize("stored", [True, False, "abc", "4.5", "-3", 1.5, None, [1], "٣", "9" * 5000])
def test_effective_code_runner_timeout_rejects_a_stored_value_of_the_wrong_type(stored):
    from backend.tools.implementations.code_executor import effective_code_runner_timeout
    with patch('backend.tools.implementations.code_executor.db.get_setting', return_value=stored), \
         patch('backend.tools.implementations.code_executor.log_event') as log:
        with pytest.raises(ValueError):
            effective_code_runner_timeout()
    log.assert_called_once()
    assert log.call_args.args[0] == "code_executor_timeout_invalid"


def test_run_file_sends_the_clamped_timeout_and_waits_longer_than_compile_plus_run(tmp_path):
    import asyncio
    (tmp_path / "main.py").write_text("print(1)")
    with patch('backend.tools.implementations.code_executor.resolve_owner_and_physical_path') as resolve, \
         patch('backend.tools.implementations.code_executor.db') as db, \
         patch('backend.tools.implementations.code_executor.requests') as req, \
         patch('backend.tools.implementations.code_executor.config.CODE_RUNNER_MAX_TIMEOUT', 120):
        resolve.side_effect = lambda chat_id, path, **kw: (chat_id, None, str(tmp_path / path) if path else str(tmp_path))
        db.get_setting.side_effect = lambda key, default=None: 9999 if key == "code_runner_timeout" else default
        req.post.return_value = MagicMock(json=lambda: {"stdout": "1\n", "stderr": "", "exit_code": 0, "execution_time_ms": 1, "timed_out": False})
        asyncio.run(run_file(path="main.py", chat_id="c1", tool_call_id="tc"))
    assert req.post.call_args.kwargs["json"]["timeout"] == 120
    assert req.post.call_args.kwargs["timeout"] == 140  # 120 + the compile budget (15 s) + margin


def test_run_file_and_run_code_report_an_invalid_timeout_setting(tmp_path):
    import asyncio
    (tmp_path / "main.py").write_text("print(1)")
    with patch('backend.tools.implementations.code_executor.resolve_owner_and_physical_path') as resolve, \
         patch('backend.tools.implementations.code_executor.db') as db, \
         patch('backend.tools.implementations.code_executor.log_event'):
        resolve.side_effect = lambda chat_id, path, **kw: (chat_id, None, str(tmp_path / path) if path else str(tmp_path))
        db.get_setting.side_effect = lambda key, default=None: "abc" if key == "code_runner_timeout" else default
        res_file = asyncio.run(run_file(path="main.py", chat_id="c1", tool_call_id="tc"))
        res_code = asyncio.run(run_code(code="print(1)", language="python", chat_id="c1", tool_call_id="tc"))
    assert res_file == res_code == "Error: The code runner timeout setting is invalid. Fix it in Settings."


def test_run_code_sends_the_clamped_timeout_and_waits_longer_than_compile_plus_run():
    import asyncio
    with patch('backend.tools.implementations.code_executor.db') as db, \
         patch('backend.tools.implementations.code_executor.requests') as req, \
         patch('backend.tools.implementations.code_executor.config.CODE_RUNNER_MAX_TIMEOUT', 120):
        db.get_setting.side_effect = lambda key, default=None: 9999 if key == "code_runner_timeout" else default
        req.post.return_value = MagicMock(json=lambda: {"stdout": "1\n", "stderr": "", "exit_code": 0, "execution_time_ms": 1, "timed_out": False})
        asyncio.run(run_code(code="print(1)", language="python", chat_id="c1", tool_call_id="tc"))
    assert req.post.call_args.kwargs["json"]["timeout"] == 120
    assert req.post.call_args.kwargs["timeout"] == 140  # 120 + the compile budget (15 s) + margin


def test_run_code_runner_unavailable_message_has_no_exception_text_and_is_logged(mock_db, mock_requests):
    # asyncio.run keeps this test runnable without the pytest-asyncio plugin that the older tests need
    mock_requests.post.side_effect = ConnectionError("boom http://code_runner_mcp:8100/execute")
    with patch('backend.tools.implementations.code_executor.log_event') as log:
        res = asyncio.run(run_code(code="print(1)", language="python", chat_id="c1", tool_call_id="tc"))
    assert res == "Error: Failed to execute code. Code runner service is unavailable."
    assert "boom" not in res and "code_runner_mcp" not in res
    log.assert_called_once_with("code_executor_run_code_error", {"chat_id": "c1", "error": "ConnectionError"})


# ---- no exception text in tool results; details go to log_event -------------------------------------------------
# These tests use asyncio.run so they run without the pytest-asyncio plugin that the older tests above need.

def _resolver_for(tmp_path):
    return lambda chat_id, path, **kw: (chat_id, None, str(tmp_path / path) if path else str(tmp_path))


def test_run_file_keeps_the_resolvers_own_message_for_an_invalid_path():
    with patch('backend.tools.implementations.code_executor.resolve_owner_and_physical_path', side_effect=ValueError("Path is reserved")):
        res = asyncio.run(run_file(path="workspace/a.py", chat_id="c1", tool_call_id="tc"))
    assert res == "Error: Failed to resolve file path: Path is reserved"


def test_run_file_hides_an_internal_resolver_failure_and_logs_it():
    with patch('backend.tools.implementations.code_executor.resolve_owner_and_physical_path', side_effect=RuntimeError("db locked at /secret")), \
         patch('backend.tools.implementations.code_executor.log_event') as log:
        res = asyncio.run(run_file(path="a.py", chat_id="c1", tool_call_id="tc"))
    assert res == "Error: Failed to resolve file path."
    assert "/secret" not in res
    log.assert_called_once_with("code_executor_resolve_error", {"chat_id": "c1", "path": "a.py", "error": "RuntimeError"})


def test_run_file_known_user_facing_messages_are_unchanged(tmp_path):
    (tmp_path / "notes.xyz").write_text("hello")
    with patch('backend.tools.implementations.code_executor.resolve_owner_and_physical_path', side_effect=_resolver_for(tmp_path)):
        assert asyncio.run(run_file(path="nope.py", chat_id="c1", tool_call_id="tc")) == "Error: File 'nope.py' does not exist."
        assert asyncio.run(run_file(path="notes.xyz", chat_id="c1", tool_call_id="tc")) == "Error: File extension '.xyz' is not supported for execution."


def test_run_file_runner_unavailable_has_no_exception_text_and_is_logged(tmp_path, mock_db, mock_requests):
    (tmp_path / "main.py").write_text("print(1)")
    mock_requests.post.side_effect = ConnectionError("boom http://code_runner_mcp:8100")
    with patch('backend.tools.implementations.code_executor.resolve_owner_and_physical_path', side_effect=_resolver_for(tmp_path)), \
         patch('backend.tools.implementations.code_executor.log_event') as log:
        res = asyncio.run(run_file(path="main.py", chat_id="c1", tool_call_id="tc"))
    assert res == "Error: Failed to execute file. Code runner service is unavailable."
    assert "boom" not in res and "code_runner_mcp" not in res
    log.assert_called_once_with("code_executor_run_file_error", {"chat_id": "c1", "error": "ConnectionError"})


def test_install_packages_runner_unavailable_has_no_exception_text_and_is_logged(mock_db, mock_requests):
    mock_requests.post.side_effect = ConnectionError("boom http://code_runner_mcp:8100")
    with patch('backend.tools.implementations.code_executor.request_clarification', return_value="Yes, install"), \
         patch('backend.tools.implementations.code_executor.log_event') as log:
        res = asyncio.run(install_packages(packages=["numpy"], package_manager="pip", chat_id="c1", tool_call_id="tc"))
    assert res == "Error: Failed to install packages. Code runner service is unavailable."
    assert "boom" not in res and "code_runner_mcp" not in res
    log.assert_called_once_with("code_executor_install_packages_error", {"chat_id": "c1", "error": "ConnectionError"})


def test_list_packages_runner_unavailable_has_no_exception_text_and_is_logged(mock_db, mock_requests):
    mock_requests.get.side_effect = ConnectionError("boom http://code_runner_mcp:8100")
    with patch('backend.tools.implementations.code_executor.log_event') as log:
        res = asyncio.run(list_packages(package_manager="pip", chat_id="c1", tool_call_id="tc"))
    assert res == "Error: Failed to fetch packages. Code runner service is unavailable."
    assert "boom" not in res and "code_runner_mcp" not in res
    log.assert_called_once_with("code_executor_list_packages_error", {"chat_id": "c1", "error": "ConnectionError"})



@pytest.mark.parametrize("path,logged", [(123, "123"), ({"p": 1}, "{'p': 1}"), ("x" * 500, "x" * 200)])
def test_run_file_internal_resolver_failure_logs_a_capped_string_path_even_for_odd_input(path, logged):
    with patch('backend.tools.implementations.code_executor.resolve_owner_and_physical_path', side_effect=AttributeError("boom")), \
         patch('backend.tools.implementations.code_executor.log_event') as log:
        res = asyncio.run(run_file(path=path, chat_id="c1", tool_call_id="tc"))
    assert res == "Error: Failed to resolve file path."
    log.assert_called_once_with("code_executor_resolve_error", {"chat_id": "c1", "path": logged, "error": "AttributeError"})


# --- the run slot: runner calls are serialised, keyed by the chat owner, and never block the event loop ------

from backend.tools.implementations import code_executor
from backend.tools.implementations.run_slot import RunQueueFull, RunQueueTimeout

RUNNER_CALLS = {
    "run_code": lambda: code_executor.run_code(code="print(1)", language="python", chat_id="c1", tool_call_id="tc"),
    "run_file": lambda: code_executor.run_file(path="main.py", chat_id="c1", tool_call_id="tc"),
    "install_packages": lambda: _approved_install(),
    "list_packages": lambda: code_executor.list_packages("pip", chat_id="c1"),
}


async def _approved_install():
    with patch('backend.tools.implementations.code_executor.request_clarification', return_value="Yes, install"):
        return await code_executor.install_packages(["requests"], "pip", chat_id="c1", tool_call_id="tc")


@pytest.fixture
def runner_env(tmp_path):
    """A mocked db and runner so each tool reaches its runner call; yields (db, requests, slot_log)."""
    (tmp_path / "main.py").write_text("print(1)")
    slot_log = []

    @asynccontextmanager
    async def recording_slot(owner, *a, **k):
        slot_log.append(("enter", owner))
        try:
            yield
        finally:
            slot_log.append(("exit", owner))

    with patch('backend.tools.implementations.code_executor.resolve_owner_and_physical_path') as resolve, \
         patch('backend.tools.implementations.code_executor.db') as db, \
         patch('backend.tools.implementations.code_executor.requests') as req, \
         patch('backend.tools.implementations.code_executor.async_run_slot', recording_slot), \
         patch('backend.tools.implementations.code_executor.log_event') as events:
        resolve.side_effect = lambda chat_id, path, **kw: (chat_id, None, str(tmp_path / path) if path else str(tmp_path))
        db.get_setting.side_effect = lambda key, default=None: default
        db.get_chat_owner.return_value = "owner-1"
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"stdout": "", "stderr": "", "exit_code": 0, "execution_time_ms": 1, "timed_out": False,
                                      "success": True, "packages": []}
        req.post.return_value = response
        req.get.return_value = response
        yield db, req, slot_log, events


@pytest.mark.parametrize("name", list(RUNNER_CALLS))
def test_every_runner_call_runs_inside_the_slot_of_the_chat_owner_in_a_worker_thread(name, runner_env):
    db, req, slot_log, _ = runner_env
    thread_of_call = []
    request_fn = req.get if name == "list_packages" else req.post
    request_fn.side_effect = lambda *a, **k: (thread_of_call.append(threading.current_thread()), request_fn.return_value)[1]
    asyncio.run(RUNNER_CALLS[name]())
    assert slot_log == [("enter", "owner-1"), ("exit", "owner-1")]  # the request happened between enter and exit
    assert thread_of_call and thread_of_call[0] is not threading.main_thread()  # not on the event loop's thread
    db.get_chat_owner.assert_called_with("c1")


@pytest.mark.parametrize("name", list(RUNNER_CALLS))
@pytest.mark.parametrize("error,event", [(RunQueueFull("u"), "code_runner_queue_full_error"), (RunQueueTimeout("u"), "code_runner_queue_timeout_error")])
def test_a_full_or_timed_out_slot_returns_the_busy_message_and_logs(name, error, event, runner_env):
    _, req, _, events = runner_env

    @asynccontextmanager
    async def refusing(owner, *a, **k):
        raise error
        yield

    with patch('backend.tools.implementations.code_executor.async_run_slot', refusing):
        result = asyncio.run(RUNNER_CALLS[name]())
    assert result == "Error: Code runner is busy; try again shortly."
    req.post.assert_not_called(); req.get.assert_not_called()  # nothing reached the runner
    events.assert_any_call(event, {"chat_id": "c1"})


@pytest.mark.parametrize("name", list(RUNNER_CALLS))
@pytest.mark.parametrize("owner", [None, ""])
def test_a_chat_without_an_owner_gets_the_unavailable_message_without_taking_the_slot(name, owner, runner_env):
    db, req, slot_log, events = runner_env
    db.get_chat_owner.return_value = owner
    result = asyncio.run(RUNNER_CALLS[name]())
    assert result == "Error: Code runner is unavailable for this request."
    assert slot_log == []
    req.post.assert_not_called(); req.get.assert_not_called()
    events.assert_any_call("code_runner_no_owner_error", {"chat_id": "c1"})


def test_a_call_without_a_chat_id_is_refused_too(runner_env):
    _, req, slot_log, _ = runner_env
    result = asyncio.run(code_executor.run_code(code="print(1)", language="python"))
    assert result == "Error: Code runner is unavailable for this request." and slot_log == []


@pytest.mark.parametrize("name", list(RUNNER_CALLS))
def test_a_runner_connection_error_still_releases_the_slot(name, runner_env):
    _, req, slot_log, _ = runner_env
    req.post.side_effect = ConnectionError("runner down")
    req.get.side_effect = ConnectionError("runner down")
    result = asyncio.run(RUNNER_CALLS[name]())
    assert "unavailable" in str(result)
    assert slot_log == [("enter", "owner-1"), ("exit", "owner-1")]


@pytest.mark.parametrize("name", ["run_code", "run_file"])
def test_the_http_timeout_covers_compile_time_plus_the_run(name, runner_env):
    _, req, _, _ = runner_env
    asyncio.run(RUNNER_CALLS[name]())
    assert req.post.call_args.kwargs["timeout"] >= 15 + 30 + 5  # compile 15 s + the run's default 30 s + margin



# ---- workspace runs (no chat) --------------------------------------------------------------------------------

def test_run_owner_is_the_chat_owner_then_the_workspace_owner_then_none():
    with patch('backend.tools.implementations.code_executor.db') as db:
        db.get_chat_owner.return_value = "chat-owner"
        db.get_workspace_owner.return_value = "ws-owner"
        assert code_executor._run_owner("c1", None) == "chat-owner"
        assert code_executor._run_owner("c1", "w1") == "chat-owner"  # a chat wins when both are given
        assert code_executor._run_owner(None, "w1") == "ws-owner"
        assert code_executor._run_owner(None, None) is None
        db.get_workspace_owner.assert_called_once_with("w1")


def test_resolve_run_target_passes_the_workspace_to_the_resolver(tmp_path):
    (tmp_path / "main.py").write_text("print(1)")
    with patch('backend.tools.implementations.code_executor.resolve_owner_and_physical_path') as resolve:
        resolve.side_effect = lambda chat_id, path, **kw: (chat_id, kw.get("workspace_id"), str(tmp_path / path) if path else str(tmp_path))
        assert code_executor.resolve_run_target(None, "main.py", workspace_id="w1") == (str(tmp_path / "main.py"), str(tmp_path))
        assert all(c.kwargs == {"workspace_id": "w1"} and c.args[0] is None for c in resolve.call_args_list)


def test_run_file_without_chat_or_workspace_is_still_the_missing_context_error():
    assert asyncio.run(code_executor.run_file(path="main.py")) == "Error: Missing chat context."


def test_a_workspace_run_takes_the_slot_of_the_workspace_owner_and_keeps_no_history(runner_env):
    db, req, slot_log, _ = runner_env
    db.get_workspace_owner.return_value = "ws-owner"
    result = asyncio.run(code_executor.run_file(path="main.py", workspace_id="w1", tool_call_id="tc"))
    assert "Exit Code" in result
    assert slot_log == [("enter", "ws-owner"), ("exit", "ws-owner")]
    db.get_chat_owner.assert_not_called()
    db.add_code_execution_record.assert_not_called()  # run history is chat-only
    req.post.assert_called_once()


def test_a_workspace_run_whose_workspace_has_no_owner_is_refused_without_calling_the_runner(runner_env):
    db, req, _, _ = runner_env
    db.get_workspace_owner.return_value = None
    result = asyncio.run(code_executor.run_file(path="main.py", workspace_id="w1", tool_call_id="tc"))
    assert result == code_executor.RUNNER_UNAVAILABLE_MESSAGE
    req.post.assert_not_called()


def test_dangerous_code_in_a_workspace_run_is_refused_without_asking_or_running(runner_env):
    _, req, _, _ = runner_env
    with patch('backend.tools.implementations.code_executor.classify_code', return_value="dangerous"), \
         patch('backend.tools.implementations.code_executor.request_clarification') as ask:
        result = asyncio.run(code_executor.run_file(path="main.py", workspace_id="w1", tool_call_id="tc"))
    assert result == "Error: This file needs your confirmation before it runs. Run it from a chat to confirm."
    ask.assert_not_called(); req.post.assert_not_called()


def test_a_chat_run_still_records_history(runner_env):
    db, req, _, _ = runner_env
    asyncio.run(code_executor.run_file(path="main.py", chat_id="c1", tool_call_id="tc"))
    db.add_code_execution_record.assert_called_once()


def test_dangerous_code_in_a_chat_run_still_asks_the_person(runner_env):
    _, req, _, _ = runner_env
    with patch('backend.tools.implementations.code_executor.classify_code', return_value="dangerous"), \
         patch('backend.tools.implementations.code_executor.request_clarification', return_value="No, cancel") as ask:
        result = asyncio.run(code_executor.run_file(path="main.py", chat_id="c1", tool_call_id="tc"))
    ask.assert_called_once()
    assert result == "Execution cancelled by user." and not req.post.called
