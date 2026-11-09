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

def test_task_ops(temp_db):
    db = temp_db
    chat_id = "test_chat_tasks"
    parent_id = 1
    
    # Ensure chat exists to satisfy foreign key constraint
    db.ensure_chat_exists(chat_id, "u1")
    
    tasks = [{"id": 1, "task": "Do thing A"}, {"id": 2, "task": "Do thing B"}]
    
    # 1. Set Task List
    success = db.set_task_list(
        chat_id=chat_id,
        data=tasks,
        parent_id=parent_id
    )
    assert success is True
    
    # 2. Get Task List
    retrieved_tasks = db.get_task_list(chat_id, parent_id=parent_id)
    assert len(retrieved_tasks) == 2
    assert retrieved_tasks[0]['task'] == "Do thing A"
    
    # 3. Update Task List (overwrite)
    new_tasks = [{"id": 1, "task": "Do thing A (done)"}]
    db.set_task_list(chat_id, new_tasks, parent_id=parent_id)
    
    retrieved_updated = db.get_task_list(chat_id, parent_id=parent_id)
    assert len(retrieved_updated) == 1
    assert retrieved_updated[0]['task'] == "Do thing A (done)"

    # 4. Get Latest Task List (ignoring specific parent_id anchor)
    latest_tasks = db.get_latest_task_list(chat_id)
    assert len(latest_tasks) == 1
    assert latest_tasks[0]['task'] == "Do thing A (done)"

