import os
import pytest
import tempfile
import shutil
import time
from unittest.mock import patch
from backend.database.init_db import init_db
from backend.database.db_wrapper import DatabaseWrapper
from backend.database.cache_system import cache_system

@pytest.fixture(scope="module")
def temp_db():
    tmp_dir = tempfile.mkdtemp()
    db_path = os.path.join(tmp_dir, "test_chats_history.db")
    with patch("backend.database.db_layer.DB_PATH", db_path), \
         patch("backend.database.init_db.DB_PATH", db_path), \
         patch("backend.database.db_wrapper.DB_PATH", db_path):
        init_db()
        wrapper = DatabaseWrapper()
        yield wrapper
    shutil.rmtree(tmp_dir)

def test_history_weaving_basic(temp_db):
    db = temp_db
    chat_id = "test_history_weaving_basic"
    db.ensure_chat_exists(chat_id, "u1")
    
    main_msg_id = db.add_message(
        chat_id=chat_id,
        role="user",
        content="main message",
        parent_id=None
    )
    
    db.add_message(
        chat_id=chat_id,
        role="assistant",
        content="sub agent content",
        parent_id=main_msg_id,
        parent_type="search_web"
    )
    
    history = db.get_woven_history(chat_id)
    assert len(history) >= 1
    assert history[0]['id'] == main_msg_id

def test_message_order_map(temp_db):
    db = temp_db
    chat_id = "test_order_map"
    db.ensure_chat_exists(chat_id, "u1")

    order_map = db.get_message_order_map(chat_id)
    assert order_map == []

    new_map = [1, 2, 3]
    assert db.update_message_order_map(chat_id, new_map) is True
    
    order_map_after = db.get_message_order_map(chat_id)
    assert order_map_after == new_map

def test_woven_history_detailed(temp_db):
    db = temp_db
    chat_id = "test_woven_history_detailed"
    db.ensure_chat_exists(chat_id, "u1")
    
    # 1. Create a structured turn sequence
    # Main User Message
    msg1_id = db.add_message(
        chat_id=chat_id,
        role="user",
        content="What is the weather?"
    )
    
    # Main Assistant Message with a tool call
    tool_call_item = {
        "id": "tc_123",
        "type": "function",
        "function": {
            "name": "get_weather",
            "arguments": '{"location": "San Francisco"}'
        }
    }
    msg2_id = db.add_message(
        chat_id=chat_id,
        role="assistant",
        content="Let me look that up.",
        tool_calls=[tool_call_item]
    )
    
    # Sub-agent execution anchored to the tool call
    sub_msg1_id = db.add_message(
        chat_id=chat_id,
        role="user",
        content="Querying API for SF weather...",
        parent_id="tc_123",  # Anchored to the tool call ID
        parent_type="search_weather_agent"
    )
    
    sub_msg2_id = db.add_message(
        chat_id=chat_id,
        role="assistant",
        content="API returned 68 degrees.",
        parent_id="tc_123",
        parent_type="search_weather_agent"
    )
    
    # Add a collection task list attached to the main user message
    db.add_collection(
        chat_id=chat_id,
        parent_message_id=msg1_id,
        parent_type="main",
        collection_type="task_list",
        items=[{"task": "Fetch weather data", "status": "completed"}]
    )
    
    # Add active/transient SSE chunks for a running turn (simulating active stream)
    # The active turn is anchored to msg2_id (assistant active)
    active_parent_id = msg2_id
    cache_system.initialize_chat(chat_id, overwrite=True)
    cache_system.add_sse_chunk(
        chat_id=chat_id,
        parent_message_id=active_parent_id,
        parent_type="main",
        chunk_index=0,
        chunk_type="thinking",
        content="Analyzing weather data..."
    )
    cache_system.add_sse_chunk(
        chat_id=chat_id,
        parent_message_id=active_parent_id,
        parent_type="main",
        chunk_index=1,
        chunk_type="content",
        content=" The weather in SF is sunny and 68 degrees."
    )
    
    # Add a ghost collection (search snippets) created during this active turn
    db.add_collection(
        chat_id=chat_id,
        parent_message_id=active_parent_id,
        parent_type="main",
        collection_type="search_results",
        items=["SF Weather API: Sunny, 68F"]
    )
    
    # Setup custom order map to include both messages and active SSE placeholder
    custom_map = [
        {"type": "message", "id": msg1_id},
        {"type": "message", "id": msg2_id},
        {"type": "sse", "parent_id": active_parent_id}
    ]
    db.update_message_order_map(chat_id, custom_map)
    
    # 2. Get woven history and verify everything is woven correctly
    woven = db.get_woven_history(chat_id)
    
    assert len(woven) == 3
    
    # Check User Message with nested collections
    user_turn = woven[0]
    assert user_turn["id"] == msg1_id
    assert user_turn["role"] == "user"
    assert "collections" in user_turn
    assert user_turn["collections"][0]["collection_type"] == "task_list"
    
    # Check Assistant Message with nested sub-agent history and tool-call anchoring
    asst_turn = woven[1]
    assert asst_turn["id"] == msg2_id
    assert asst_turn["role"] == "assistant"
    assert "sub_agent_history" in asst_turn
    sub_hist = asst_turn["sub_agent_history"]
    assert len(sub_hist) == 2
    assert sub_hist[0]["id"] == sub_msg1_id
    assert sub_hist[0]["agent_name"] == "search_weather_agent"
    assert sub_hist[1]["id"] == sub_msg2_id
    assert sub_hist[1]["agent_name"] == "search_weather_agent"
    
    # Check Active SSE Turn with nested ghost collections
    active_turn = woven[2]
    assert active_turn["id"] == f"sse_{active_parent_id}"
    assert active_turn["role"] == "assistant_active"
    assert active_turn["parent_id"] == str(active_parent_id)
    assert len(active_turn["chunks"]) == 2
    assert active_turn["chunks"][0]["chunk_type"] == "thinking"
    assert active_turn["chunks"][0]["content"] == "Analyzing weather data..."
    assert active_turn["chunks"][1]["chunk_type"] == "content"
    assert active_turn["chunks"][1]["content"] == " The weather in SF is sunny and 68 degrees."
    assert "collections" in active_turn
    assert active_turn["collections"][0]["collection_type"] == "search_results"
    
    # Cleanup sse chunks from cache
    cache_system.delete_sse_chunks(chat_id)

def test_agent_runs_collections_are_served_on_the_assistant_message_for_top_level_and_nested_runs(temp_db):
    import json
    db = temp_db
    chat_id = "test_agent_runs_history"
    db.ensure_chat_exists(chat_id, "u1")
    db.add_message(chat_id=chat_id, role="user", content="research this")
    asst_id = db.add_message(chat_id=chat_id, role="assistant", content="working",
                             tool_calls=[{"id": "tc_outer", "type": "function", "function": {"name": "research", "arguments": "{}"}}])
    top = [{"id": "tc_outer", "name": "research", "parent_id": None, "state": "done", "activity": None, "started_at": 1.0, "duration_ms": 5000}]
    nested = [{"id": "tc_inner", "name": "search_web", "parent_id": "tc_outer", "state": "done", "activity": "Searching", "started_at": 2.0, "duration_ms": 900}]
    # a top-level run is anchored on the assistant message's own id (the handler's parent_message_id), a nested run on the outer tool call id
    db.add_collection(chat_id=chat_id, parent_message_id=asst_id, parent_type="main", collection_type="agent_runs", items=top, overwrite=True)
    db.add_collection(chat_id=chat_id, parent_message_id="tc_outer", parent_type="research", collection_type="agent_runs", items=nested, overwrite=True)
    assistant = next(m for m in db.get_woven_history(chat_id) if m.get("role") == "assistant")
    runs = [json.loads(c["items"]) if isinstance(c["items"], str) else c["items"] for c in assistant["collections"] if c["collection_type"] == "agent_runs"]
    assert top in runs and nested in runs
