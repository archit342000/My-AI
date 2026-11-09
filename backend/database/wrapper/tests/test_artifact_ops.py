import os
import pytest
import tempfile
import shutil
import json
from unittest.mock import patch
from backend.database.init_db import init_db
from backend.database.db_wrapper import DatabaseWrapper
from backend.database.cache_system import cache_system

@pytest.fixture(scope="module")
def temp_db():
    tmp_dir = tempfile.mkdtemp()
    db_path = os.path.join(tmp_dir, "test_chats_artifacts.db")
    with patch("backend.database.db_layer.DB_PATH", db_path), \
         patch("backend.database.init_db.DB_PATH", db_path), \
         patch("backend.database.db_wrapper.DB_PATH", db_path):
        init_db()
        wrapper = DatabaseWrapper()
        yield wrapper
    shutil.rmtree(tmp_dir)

def test_artifact_ops(temp_db):
    db = temp_db
    chat_id = "test_artifacts"
    db.ensure_chat_exists(chat_id, "u1")
    
    file_id = "file_123"
    db.save_file(
        file_id=file_id,
        chat_id=chat_id,
        original_filename="test.txt",
        stored_filename="test_stored.txt",
        mime_type="text/plain",
        file_size=100,
        content_text="file content"
    )
    
    file_meta = db.get_file(file_id)
    assert file_meta is not None
    assert file_meta['original_filename'] == "test.txt"
    
    files = db.get_chat_files(chat_id)
    assert len(files) == 1
    assert files[0]['id'] == file_id
    
    db.delete_file(file_id)
    assert db.get_file(file_id) is None

    # Test update_file_content
    file_id_2 = "file_124"
    db.save_file(
        file_id=file_id_2,
        chat_id=chat_id,
        original_filename="test2.txt",
        stored_filename="test_stored2.txt",
        mime_type="text/plain",
        file_size=100,
        content_text="old content"
    )
    res = db.update_file_content(file_id_2, "new content")
    assert res is True
    file_meta_2 = db.get_file(file_id_2)
    assert file_meta_2['content_text'] == "new content"

    # Test update_file_processing_status
    res = db.update_file_processing_status(file_id_2, "completed")
    assert res is True
    file_meta_2 = db.get_file(file_id_2)
    assert file_meta_2['processing_status'] == "completed"

    # Test flush_sse_chunks fallback path (no chunks)
    res = db.flush_sse_chunks(chat_id, model="test-model")
    assert res is True

    # Test collections
    parent_msg_id = 1
    db.add_collection(chat_id, parent_message_id=parent_msg_id, parent_type="main", collection_type="task_list", items=[])
    cols = db.get_collections(chat_id, parent_message_id=parent_msg_id, parent_type="main")
    assert len(cols) == 1
    assert cols[0]['collection_type'] == "task_list"
    assert cols[0]['items'] == "[]"

def test_flush_sse_chunks_main_detailed(temp_db):
    db = temp_db
    chat_id = "test_flush_main"
    db.ensure_chat_exists(chat_id, "u1")
    
    # 1. Create a parent user message
    msg_parent_id = db.add_message(
        chat_id=chat_id,
        role="user",
        content="Hello, call the tool."
    )
    
    # 2. Add an SSE placeholder to order map
    order_map = [
        {"type": "message", "id": msg_parent_id},
        {"type": "sse", "parent_id": msg_parent_id}
    ]
    db.update_message_order_map(chat_id, order_map)
    
    # 3. Add fragmented SSE chunks to the cache system
    cache_system.initialize_chat(chat_id, overwrite=True)
    
    # Thinking parts
    cache_system.add_sse_chunk(chat_id, msg_parent_id, "main", 0, "thinking", "Thinking part 1. ")
    cache_system.add_sse_chunk(chat_id, msg_parent_id, "main", 1, "thinking", "Thinking part 2.")
    
    # Content parts
    cache_system.add_sse_chunk(chat_id, msg_parent_id, "main", 2, "content", "Here is the response. ")
    cache_system.add_sse_chunk(chat_id, msg_parent_id, "main", 3, "content", "Enjoy!")
    
    # Tool call JSON delta fragments
    delta1 = {"index": 0, "id": "call_abc", "function": {"name": "calculator", "arguments": '{"a": '}}
    delta2 = {"index": 0, "function": {"arguments": '5, "b": 10}'}}
    
    cache_system.add_sse_chunk(chat_id, msg_parent_id, "main", 4, "tool_call", json.dumps(delta1))
    cache_system.add_sse_chunk(chat_id, msg_parent_id, "main", 5, "tool_call", json.dumps(delta2))
    
    # Tool result parts
    cache_system.add_sse_chunk(chat_id, msg_parent_id, "main", 6, "tool_result", "Result is 15")
    
    # 4. Flush SSE chunks to permanent DB
    res = db.flush_sse_chunks(chat_id, model="llama3-model", parent_message_id=msg_parent_id, parent_type="main")
    assert res is True
    
    # 5. Verify database storage & order map updates
    # The cache should be surgically cleaned up
    remaining_chunks = cache_system.get_sse_chunks(chat_id, parent_message_id=msg_parent_id, parent_type="main")
    assert len(remaining_chunks) == 0
    
    # Retrieve messages from DB
    messages = db.get_messages(chat_id)
    # We should have the parent user message, the aggregated assistant message, and the tool result message
    assert len(messages) == 3
    
    # Assistant message
    asst_msg = messages[1]
    assert asst_msg["role"] == "assistant"
    assert asst_msg["content"] == "Here is the response. Enjoy!"
    assert asst_msg["reasoning_content"] == "Thinking part 1. Thinking part 2."
    assert asst_msg["model"] == "llama3-model"
    assert str(asst_msg["parent_id"]) == str(msg_parent_id)
    
    # Verify tool calls were merged correctly
    tool_calls = asst_msg["tool_calls"]
    if isinstance(tool_calls, str):
        tool_calls = json.loads(tool_calls)
    assert len(tool_calls) == 1
    assert tool_calls[0]["id"] == "call_abc"
    assert tool_calls[0]["function"]["name"] == "calculator"
    assert tool_calls[0]["function"]["arguments"] == '{"a": 5, "b": 10}'
    
    # Tool result message
    tool_msg = messages[2]
    assert tool_msg["role"] == "tool"
    assert tool_msg["content"] == "Result is 15"
    assert str(tool_msg["parent_id"]) == str(msg_parent_id)
    
    # Verify order map was updated (replacing 'sse' entry with 'message' entries)
    new_map = db.get_message_order_map(chat_id)
    assert len(new_map) == 3
    assert new_map[0] == {"type": "message", "id": msg_parent_id}
    assert new_map[1] == {"type": "message", "id": asst_msg["id"]}
    assert new_map[2] == {"type": "message", "id": tool_msg["id"]}

def test_flush_sse_chunks_sub_agent(temp_db):
    db = temp_db
    chat_id = "test_flush_sub"
    db.ensure_chat_exists(chat_id, "u1")
    
    # 1. Create a parent message anchoring the sub-agent
    parent_id = db.add_message(
        chat_id=chat_id,
        role="assistant",
        content="Sub-agent is starting..."
    )
    
    # 2. Add SSE chunks for a sub-agent
    cache_system.initialize_chat(chat_id, overwrite=True)
    cache_system.add_sse_chunk(chat_id, parent_id, "sub_agent_x", 0, "thinking", "Sub thinking...")
    cache_system.add_sse_chunk(chat_id, parent_id, "sub_agent_x", 1, "content", "Sub agent content response")
    
    # 3. Flush sub-agent SSE chunks
    res = db.flush_sse_chunks(chat_id, model="sub-model", parent_message_id=parent_id, parent_type="sub_agent_x")
    assert res is True
    
    # 4. Verify sub-agent messages stored
    sub_messages = db.get_all_sub_agent_messages(chat_id)
    assert len(sub_messages) == 1
    sub_msg = sub_messages[0]
    assert sub_msg["role"] == "assistant"
    assert sub_msg["content"] == "Sub agent content response"
    assert sub_msg["reasoning_content"] == "Sub thinking..."
    assert str(sub_msg["parent_message_id"]) == str(parent_id)
    assert sub_msg["parent_type"] == "sub_agent_x"
    assert sub_msg["agent_name"] == "sub_agent_x"
    assert int(sub_msg["sequence_order"]) == 1