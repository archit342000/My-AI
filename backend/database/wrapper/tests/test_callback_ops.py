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

def test_callback_ops(temp_db):
    db = temp_db
    chat_id = "test_chat_callbacks"
    callback_id = "cb_123"
    
    # Ensure chat exists to satisfy foreign key constraint
    db.ensure_chat_exists(chat_id, "u1")
    
    # 1. Save Callback
    db.save_callback(
        callback_id=callback_id,
        chat_id=chat_id,
        parent_message_id=1,
        question="What is your name?",
        options=["Alice", "Bob"]
    )
    
    # 2. Get pending callbacks
    pending = db.get_pending_callbacks(chat_id)
    assert len(pending) == 1
    assert pending[0]['callback_id'] == callback_id
    assert pending[0]['question'] == "What is your name?"
    
    # 3. Resolve callback
    db.resolve_callback(callback_id, "Alice")
    
    # 4. Check pending again (should be 0)
    pending_after = db.get_pending_callbacks(chat_id)
    assert len(pending_after) == 0
    
    # 5. Get resolved callback
    resolved = db.get_resolved_callback(callback_id)
    assert resolved is not None
    assert resolved['response'] == "Alice"
    
    # 6. Cleanup
    db.cleanup_callback(callback_id)
    assert db.get_resolved_callback(callback_id) is None

    # 7. Test cleanup_chat_callbacks
    callback_id_2 = "cb_124"
    db.save_callback(
        callback_id=callback_id_2,
        chat_id=chat_id,
        parent_message_id=1,
        question="Are you okay?",
        options=["Yes", "No"]
    )
    assert len(db.get_pending_callbacks(chat_id)) == 1
    db.cleanup_chat_callbacks(chat_id)
    assert len(db.get_pending_callbacks(chat_id)) == 0


def test_get_callback_chat_id(temp_db):
    temp_db.ensure_chat_exists("chat_for_cb_lookup", "u1")
    temp_db.save_callback(callback_id="cb_lookup", chat_id="chat_for_cb_lookup", parent_message_id=1, question="?", options=[])
    assert temp_db.get_callback_chat_id("cb_lookup") == "chat_for_cb_lookup"
    assert temp_db.get_callback_chat_id("cb_unknown") is None
