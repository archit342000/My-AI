import os
import pytest
import tempfile
import shutil
from unittest.mock import patch, AsyncMock
from backend.database.init_db import init_db
from backend.database.db_wrapper import DatabaseWrapper

@pytest.fixture(scope="module")
def temp_db():
    tmp_dir = tempfile.mkdtemp()
    db_path = os.path.join(tmp_dir, "test_chats.db")
    with patch("backend.database.db_layer.DB_PATH", db_path), \
         patch("backend.database.init_db.DB_PATH", db_path), \
         patch("backend.database.db_wrapper.DB_PATH", db_path):
        init_db()
        wrapper = DatabaseWrapper()
        with patch("backend.tools.clipboard.db", wrapper):
            yield wrapper
    shutil.rmtree(tmp_dir)

def test_clipboard_write_and_read(temp_db):
    chat_id = "test-chat-tool-id"
    temp_db.save_chat(chat_id, "Title", 0.0, 1, user_id="u1")

    from backend.tools.clipboard import clipboard_write, clipboard_read

    # Write
    write_res = clipboard_write("Verbatim text blob content", chat_id)
    assert write_res["success"] is True
    key = write_res["key"]
    assert key.startswith("cb-")

    # Read
    read_res = clipboard_read(key, chat_id)
    assert read_res["success"] is True
    assert read_res["content"] == "Verbatim text blob content"

    # Read non-existent
    read_fail = clipboard_read("cb-fake123", chat_id)
    assert read_fail["success"] is False
    assert "not found" in read_fail["error"]

@pytest.mark.anyio
async def test_clipboard_copy_file(temp_db):
    chat_id = "test-chat-tool-id"
    # Create file system meta and mock file content retrieval
    from backend.tools.clipboard import clipboard_copy_file
    
    file_content = "line 1\nline 2\nline 3\nline 4\nline 5"
    
    # Mock resolve_path_to_fs_file and get_fs_file_content
    with patch("backend.file_system.manager.resolve_path_to_fs_file") as mock_resolve, \
         patch("backend.file_system.manager.get_fs_file_content", new_callable=AsyncMock) as mock_get_content:
        
        mock_resolve.return_value = {
            "id": "fs-id-123",
            "chat_id": chat_id,
            "workspace_id": None,
            "current_version": 1
        }
        mock_get_content.return_value = file_content
        
        # Test full copy
        res = await clipboard_copy_file("src/main.py", chat_id)
        assert res["success"] is True
        key = res["key"]
        assert res["lines"] == 5
        
        # Verify stored value
        assert temp_db.clipboard_get(chat_id, key) == file_content

        # Test sliced copy (lines 2 to 4)
        res_slice = await clipboard_copy_file("src/main.py", chat_id, start_line=2, end_line=4)
        assert res_slice["success"] is True
        key_slice = res_slice["key"]
        assert res_slice["lines"] == 3
        assert temp_db.clipboard_get(chat_id, key_slice) == "line 2\nline 3\nline 4"
