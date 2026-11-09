import os
import uuid
import pytest
from unittest.mock import patch, MagicMock
from backend.file_system.utils import (
    sanitize_path, get_workspace_for_chat, resolve_owner_and_physical_path,
    ensure_physical_dir_exists, generate_fs_file_id, new_fs_file_id, sanitize_filename, _extract_fs_file_type
)

@pytest.fixture
def anyio_backend():
    return 'asyncio'

def test_sanitize_path():
    assert sanitize_path("foo/bar") == "foo/bar"
    assert sanitize_path("/foo/bar/") == "foo/bar"
    assert sanitize_path("../../foo/bar") == "foo/bar"
    assert sanitize_path("foo/./bar") == "foo/bar"
    assert sanitize_path("foo/*?bar") == "foo/__bar"
    assert sanitize_path("foo/bar (1).txt") == "foo/bar (1).txt"
    assert sanitize_path("foo/bar[2].txt") == "foo/bar[2].txt"
    assert sanitize_path("foo/bar+baz.txt") == "foo/bar+baz.txt"
    assert sanitize_path("foo/v=2.txt") == "foo/v=2.txt"
    assert sanitize_path("foo/bar,baz.txt") == "foo/bar,baz.txt"
    assert sanitize_path("") == ""
    assert sanitize_path("///") == ""
    assert sanitize_path(".") == ""
    assert sanitize_path("./") == ""

@patch("backend.database.db.get_chat")
def test_get_workspace_for_chat(mock_get_chat):
    mock_get_chat.return_value = {"workspace_id": "ws_123"}
    assert get_workspace_for_chat("c_123") == "ws_123"
    
    mock_get_chat.return_value = None
    assert get_workspace_for_chat("c_123") is None

@patch("backend.file_system.utils.get_workspace_for_chat")
def test_resolve_owner_and_physical_path_chat(mock_get_ws):
    chat, ws, phys = resolve_owner_and_physical_path("chat1", "some/path.txt")
    assert chat == "chat1"
    assert ws is None
    assert phys.endswith(os.path.join("chat1", "some/path.txt"))

@patch("backend.file_system.utils.get_workspace_for_chat")
def test_resolve_owner_and_physical_path_workspace(mock_get_ws):
    mock_get_ws.return_value = "ws_1"
    
    chat, ws, phys = resolve_owner_and_physical_path("chat1", "workspace/path.txt")
    assert chat is None
    assert ws == "ws_1"
    assert phys.endswith(os.path.join("ws_1", "path.txt"))
    
    # Test just "workspace"
    chat, ws, phys = resolve_owner_and_physical_path("chat1", "workspace")
    assert chat is None
    assert ws == "ws_1"
    assert phys.endswith("ws_1")

    # Test "default" workspace fallback
    chat, ws, phys = resolve_owner_and_physical_path("chat1", "workspace/path.txt", workspace_id="default")
    assert chat is None
    assert ws == "ws_1"
    assert phys.endswith(os.path.join("ws_1", "path.txt"))

@patch("backend.file_system.utils.get_workspace_for_chat")
def test_resolve_owner_and_physical_path_workspace_missing(mock_get_ws):
    mock_get_ws.return_value = None
    with pytest.raises(ValueError):
        resolve_owner_and_physical_path("chat1", "workspace/path.txt")

@patch("os.makedirs")
def test_ensure_physical_dir_exists(mock_makedirs):
    ensure_physical_dir_exists("/foo/bar/baz.txt", is_file_path=True)
    mock_makedirs.assert_called_with("/foo/bar", exist_ok=True)
    
    ensure_physical_dir_exists("/foo/bar", is_file_path=False)
    mock_makedirs.assert_called_with("/foo/bar", exist_ok=True)

@pytest.mark.anyio
@patch("backend.database.db.get_next_file_system_counter")
async def test_generate_fs_file_id(mock_get_counter):
    first = await generate_fs_file_id("chat1")
    second = await generate_fs_file_id("chat1")
    assert str(uuid.UUID(first)) == first
    assert uuid.UUID(first).version == 4
    assert first != second
    # The legacy per-owner counter must no longer be used for ids.
    mock_get_counter.assert_not_called()

def test_new_fs_file_id():
    ids = {new_fs_file_id() for _ in range(5)}
    assert len(ids) == 5
    for fs_id in ids:
        assert str(uuid.UUID(fs_id)) == fs_id
        assert uuid.UUID(fs_id).version == 4

def test_sanitize_filename():
    assert sanitize_filename("foo/bar") == "foo_bar"
    assert sanitize_filename("foo&*bar") == "foo_bar"
    assert sanitize_filename("_foo__bar_") == "foo_bar"
    assert sanitize_filename("foo-bar.txt") == "foo-bar_txt"

def test__extract_fs_file_type():
    assert _extract_fs_file_type("plan_123") == "plan"
    assert _extract_fs_file_type("research_abc") == "research"
    assert _extract_fs_file_type("section_abc") == "section"
    assert _extract_fs_file_type("other_abc") == "custom"
def test_resolve_owner_and_physical_path(): pass
