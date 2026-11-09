import os
import pytest
import tempfile
import shutil
from unittest.mock import patch
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
        yield wrapper
    shutil.rmtree(tmp_dir)

def test_clipboard_ops(temp_db):
    db = temp_db
    chat_id = "test-chat-uuid"
    
    # Save parent chat first due to Foreign Key constraint
    db.save_chat(chat_id, "Test Title", 12345.6, 1, user_id="u1")

    # Set clipboard
    db.clipboard_set(chat_id, "cb-123", "Hello Clipboard")

    # Get clipboard
    content = db.clipboard_get(chat_id, "cb-123")
    assert content == "Hello Clipboard"

    # Get non-existent
    assert db.clipboard_get(chat_id, "cb-notexist") is None

    # Replace clipboard
    db.clipboard_set(chat_id, "cb-123", "New Content")
    assert db.clipboard_get(chat_id, "cb-123") == "New Content"

    # Delete clipboard
    assert db.clipboard_delete(chat_id, "cb-123") is True
    assert db.clipboard_get(chat_id, "cb-123") is None
    assert db.clipboard_delete(chat_id, "cb-123") is False

    # Test Cascade Delete on delete_chat
    db.clipboard_set(chat_id, "cb-123", "Cascade content")
    db.delete_chat(chat_id)
    assert db.clipboard_get(chat_id, "cb-123") is None
