import asyncio
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
