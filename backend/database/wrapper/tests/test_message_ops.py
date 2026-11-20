import os
import pytest
import tempfile
import shutil
import json
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

def test_message_ops(temp_db):
    db = temp_db
    chat_id = "test_msg_ops"
    
    db.ensure_chat_exists(chat_id, "u1")
    
    msg_id = db.add_message(
        chat_id=chat_id,
        role="user",
        content="hello database",
        parent_id=None
    )
    assert msg_id is not None
    
    messages = db.get_messages(chat_id)
    assert len(messages) == 1
    assert messages[0]['content'] == "hello database"
    assert messages[0]['id'] == msg_id

    # Test add_tool_result (will add a message with role tool)
    tool_msg_id = db.add_tool_result(
        chat_id=chat_id,
        tool_call_id="call_123",
        name="test_tool",
        content="tool output"
    )
    assert tool_msg_id is not None

    # Test get_last_assistant_message
    db.add_message(
        chat_id=chat_id,
        role="assistant",
        content="hello user"
    )
    last_assistant = db.get_last_assistant_message(chat_id)
    assert last_assistant is not None
    assert last_assistant['content'] == "hello user"

    # Test sub-agent messages
    sub_msg_id = db.add_message(
        chat_id=chat_id,
        role="assistant",
        content="sub agent content",
        parent_id=msg_id,
        parent_type="search"
    )
    sub_messages = db.get_all_sub_agent_messages(chat_id)
    assert len(sub_messages) == 1
    assert sub_messages[0]['content'] == "sub agent content"

    # Test edit_message
    db.edit_message(chat_id, msg_id, "hello edited")
    msgs_after_edit = db.get_messages(chat_id)
    assert msgs_after_edit[0]['content'] == "hello edited"

    # Test delete_sub_agent_message
    db.delete_sub_agent_message(chat_id, sub_msg_id)
    assert len(db.get_all_sub_agent_messages(chat_id)) == 0

    # Test truncate_messages
    # Let's add a bunch of messages and test truncation
    for i in range(5):
        db.add_message(chat_id, role="user", content=f"msg {i}")
    
    msgs_before_trunc = db.get_messages(chat_id)
    assert len(msgs_before_trunc) > 5

    # Truncate to keep the first 2 messages (index up to 2)
    db.truncate_messages(chat_id, 2)
    msgs_after_trunc = db.get_messages(chat_id)
    assert len(msgs_after_trunc) == 2
    # Test rollback_to_last_user_message
    db.add_message(chat_id, role="user", content="user latest")
    db.add_message(chat_id, role="assistant", content="assistant latest")
    res = db.rollback_to_last_user_message(chat_id)
    # delete_message does not return a value, so res is None
    assert res is None or res is True

    # Verify rollback worked
    msgs_after_rollback = db.get_messages(chat_id)
    assert msgs_after_rollback[-1]['role'] == "user"
    rolled_back_msgs = db.get_messages(chat_id)
    assert rolled_back_msgs[-1]['role'] == "user"

    # Test delete_message
    msg_to_delete = rolled_back_msgs[-1]['id']
    db.delete_message(chat_id, msg_to_delete)
    msgs_after_del = db.get_messages(chat_id)
    assert msg_to_delete not in [m['id'] for m in msgs_after_del]

    # Test clear_messages
    db.clear_messages(chat_id)
    assert len(db.get_messages(chat_id)) == 0

def test_message_delete_pointers_cascade(temp_db):
    db = temp_db
    chat_id = "test_msg_pointers"
    db.ensure_chat_exists(chat_id, "u1")
    
    msg1_u = db.add_message(chat_id, "user", "User 1")
    msg2_a = db.add_message(chat_id, "assistant", "Asst 1")
    msg3_u = db.add_message(chat_id, "user", "User 2")
    msg4_a = db.add_message(chat_id, "assistant", "Asst 2")
    
    # 1. Assert initial pointer state
    chat = db.get_chat(chat_id)
    assert chat["last_user_id"] == msg3_u
    assert chat["last_assistant_id"] == msg4_a
    
    # 2. Delete msg4_a (latest assistant message)
    db.delete_message(chat_id, msg4_a)
    
    # 3. Assert pointers rolled back correctly
    chat_after = db.get_chat(chat_id)
    assert chat_after["last_user_id"] == msg3_u
    assert chat_after["last_assistant_id"] == msg2_a
    
    # Assert order map updated to exclude deleted message
    order_map = db.get_message_order_map(chat_id)
    assert not any(e.get('id') == msg4_a for e in order_map if e.get('type') == 'message')

def test_message_delete_history_compression_invalidation(temp_db):
    db = temp_db
    chat_id = "test_msg_compression"
    db.ensure_chat_exists(chat_id, "u1")
    
    msg1 = db.add_message(chat_id, "user", "msg 1")
    msg2 = db.add_message(chat_id, "assistant", "msg 2")
    
    # Set history_compression metadata manually
    comp_data = {"boundary_message_id": msg2, "summary": "Old summary"}
    db.update_chat(chat_id, history_compression=json.dumps(comp_data))
    
    # Assert history_compression set
    chat = db.get_chat(chat_id)
    assert chat["history_compression"] is not None
    
    # Delete message at/before the boundary
    db.delete_message(chat_id, msg2)
    
    # Assert history_compression is now None (invalidated)
    chat_after = db.get_chat(chat_id)
    assert chat_after.get("history_compression") is None


def test_message_attachments_round_trip(temp_db):
    db = temp_db
    db.ensure_chat_exists("attach_chat", "u1")
    refs = [{"file_id": "f1", "name": "a.txt", "size": 3, "mime_type": "text/plain"}]
    with_files = db.add_message("attach_chat", role="user", content="see file", attachments=refs)
    without = db.add_message("attach_chat", role="user", content="no file")
    sub_id = db.add_message("attach_chat", role="assistant", content="sub", parent_id=with_files,
                            parent_type="search", attachments=refs)

    by_id = {m["id"]: m for m in db.get_messages("attach_chat")}
    assert by_id[with_files]["attachments"] == refs
    assert by_id[without]["attachments"] is None
    # Sub-agent rows are unaffected: stored in sub_agent_messages, which has no attachments column
    assert sub_id is not None
    assert [m["content"] for m in db.get_all_sub_agent_messages("attach_chat")] == ["sub"]
    assert all("attachments" not in m for m in db.get_all_sub_agent_messages("attach_chat"))


def test_edit_message_is_scoped_to_chat(temp_db):
    db = temp_db
    for chat in ("edit_scope_a", "edit_scope_b"):
        db.ensure_chat_exists(chat, "u1")
    a_first = db.add_message("edit_scope_a", role="user", content="a first")
    a_reply = db.add_message("edit_scope_a", role="assistant", content="a reply")
    b_first = db.add_message("edit_scope_b", role="user", content="b first")
    b_reply = db.add_message("edit_scope_b", role="assistant", content="b reply")

    # A message id from another chat is refused and nothing changes in either chat
    assert db.edit_message("edit_scope_a", b_first, "hijacked") is False
    assert [m["content"] for m in db.get_messages("edit_scope_b")] == ["b first", "b reply"]
    assert [m["content"] for m in db.get_messages("edit_scope_a")] == ["a first", "a reply"]

    # A missing id is refused too
    assert db.edit_message("edit_scope_a", 999999, "x") is False
    assert [m["content"] for m in db.get_messages("edit_scope_a")] == ["a first", "a reply"]

    # An in-chat edit succeeds and truncates the later history
    assert db.edit_message("edit_scope_a", a_first, "a edited") is True
    assert [m["content"] for m in db.get_messages("edit_scope_a")] == ["a edited"]
    assert a_reply not in [m["id"] for m in db.get_messages("edit_scope_a")]
    assert [m["id"] for m in db.get_messages("edit_scope_b")] == [b_first, b_reply]


def test_get_message_is_scoped_to_the_chat(temp_db):
    db = temp_db
    for chat in ("get_msg_a", "get_msg_b"):
        db.ensure_chat_exists(chat, "u1")
    user_id = db.add_message("get_msg_a", role="user", content="hello")
    reply_id = db.add_message("get_msg_a", role="assistant", content="hi")

    assert db.get_message("get_msg_a", user_id) == {"id": user_id, "role": "user", "content": "hello"}
    assert db.get_message("get_msg_a", reply_id)["role"] == "assistant"
    assert db.get_message("get_msg_b", user_id) is None  # another chat's id
    assert db.get_message("get_msg_a", 999999) is None


def test_duration_ms_is_stored_on_main_and_sub_agent_tool_rows_and_defaults_to_null(temp_db):
    db = temp_db
    chat_id = "test_duration_rows"
    db.ensure_chat_exists(chat_id, "u1")
    anchor = db.add_message(chat_id=chat_id, role="assistant", content="calls")
    timed = db.add_tool_result(chat_id=chat_id, tool_call_id="t1", name="x", content="out", duration_ms=1234)
    untimed = db.add_tool_result(chat_id=chat_id, tool_call_id="t2", name="x", content="out")
    sub = db.add_tool_result(chat_id=chat_id, tool_call_id="t3", name="x", content="out", parent_id=anchor, parent_type="helper", duration_ms=56)
    rows = {m["id"]: m for m in db.get_messages(chat_id)}
    assert rows[timed]["duration_ms"] == 1234 and rows[untimed]["duration_ms"] is None
    sub_rows = db.get_messages(chat_id, parent_message_id=anchor, parent_type="helper")
    assert [m["duration_ms"] for m in sub_rows if m["id"] == sub] == [56]


def test_set_turn_duration_marks_the_last_assistant_row_after_the_message_and_refreshes_the_cache(temp_db):
    db = temp_db
    chat_id = "test_turn_duration"
    db.ensure_chat_exists(chat_id, "u1")
    first_user = db.add_message(chat_id=chat_id, role="user", content="q1")
    first_reply = db.add_message(chat_id=chat_id, role="assistant", content="a1")
    user = db.add_message(chat_id=chat_id, role="user", content="q2")
    mid = db.add_message(chat_id=chat_id, role="assistant", content="calls tool")
    db.add_tool_result(chat_id=chat_id, tool_call_id="t", name="x", content="out")
    last = db.add_message(chat_id=chat_id, role="assistant", content="final")
    assert [m["duration_ms"] for m in db.get_messages(chat_id)] == [None] * 6  # also fills the cache
    assert db.set_turn_duration(chat_id, user, 46000) is True
    rows = {m["id"]: m["duration_ms"] for m in db.get_messages(chat_id)}  # read after the write: cache was invalidated
    assert rows[last] == 46000 and rows[mid] is None and rows[first_reply] is None and rows[first_user] is None


def test_set_turn_duration_does_nothing_when_no_assistant_row_follows(temp_db):
    db = temp_db
    chat_id = "test_turn_duration_none"
    db.ensure_chat_exists(chat_id, "u1")
    user = db.add_message(chat_id=chat_id, role="user", content="q")
    assert db.set_turn_duration(chat_id, user, 10) is False
