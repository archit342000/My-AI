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

def test_code_execution_ops(temp_db):
    db = temp_db
    chat_id = "test_chat_1"
    
    # Ensure chat exists
    db.ensure_chat_exists(chat_id, "u1")
    
    # 1. Add record
    record_id = "exec_1"
    db.add_code_execution_record(
        record_id=record_id,
        chat_id=chat_id,
        language="python",
        code="print('hello')",
        stdout="hello\n",
        stderr="",
        exit_code=0,
        execution_time_ms=10,
        timed_out=0,
        stdin="some_in",
        files_json='[]'
    )
    
    # 2. Get record
    record = db.get_code_execution_record(record_id)
    assert record is not None
    assert record["chat_id"] == chat_id
    assert record["language"] == "python"
    assert record["code"] == "print('hello')"
    assert record["stdout"] == "hello\n"
    assert record["exit_code"] == 0
    assert record["execution_time_ms"] == 10
    assert record["timed_out"] == 0
    assert record["stdin"] == "some_in"
    assert record["files_json"] == '[]'
    
    # 3. Get history for chat
    history = db.get_code_execution_history(chat_id, limit=10)
    assert len(history) == 1
    assert history[0]["id"] == record_id
    
    # 4. Delete history for chat
    db.delete_code_execution_history(chat_id)
    history_after = db.get_code_execution_history(chat_id, limit=10)
    assert len(history_after) == 0
    assert db.get_code_execution_record(record_id) is None
