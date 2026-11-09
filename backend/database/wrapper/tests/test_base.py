import os
import pytest
import tempfile
import shutil
import logging
import json
from unittest.mock import patch
from backend.database.init_db import init_db
from backend.database.db_wrapper import DatabaseWrapper
from backend.database.wrapper.base import BaseMixin

@pytest.fixture(scope="module")
def temp_db():
    tmp_dir = tempfile.mkdtemp()
    db_path = os.path.join(tmp_dir, "test_base.db")
    with patch("backend.database.db_layer.DB_PATH", db_path), \
         patch("backend.database.init_db.DB_PATH", db_path), \
         patch("backend.database.db_wrapper.DB_PATH", db_path):
        init_db()
        wrapper = DatabaseWrapper()
        yield wrapper
    shutil.rmtree(tmp_dir)

class DummyWrapper(BaseMixin):
    pass

def test_log_db_wrapper_op():
    wrapper = DummyWrapper()
    with patch('backend.database.wrapper.base.logger.debug') as mock_debug:
        wrapper._log_db_wrapper_op("TEST_OP", chat_id="chat_1", details="extra_info")
        mock_debug.assert_called_once()
        msg = mock_debug.call_args[0][0]
        assert "[DB_WRAPPER TEST_OP]" in msg
        assert "chat_id=chat_1" in msg
        assert "extra_info" in msg

def test_get_order_map_unsafe(temp_db):
    db = temp_db
    chat_id = "test_order_map"
    db.ensure_chat_exists(chat_id, "u1")
    
    # Empty order map
    order_map = db._get_order_map_unsafe(chat_id)
    assert order_map == []

    # Update order map
    new_map = [1, 2, 3]
    db.update_message_order_map(chat_id, new_map)
    order_map = db._get_order_map_unsafe(chat_id)
    assert order_map == new_map

def test_get_chat_fetch_internal(temp_db):
    db = temp_db
    chat_id = "test_fetch_internal"
    db.ensure_chat_exists(chat_id, "u1")

    chat = db._get_chat_fetch_internal(chat_id)
    assert chat is not None
    assert chat['id'] == chat_id

    # Non-existent chat
    chat_none = db._get_chat_fetch_internal("non_existent_chat")
    assert chat_none is None