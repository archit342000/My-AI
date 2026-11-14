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

def test_sources_collection_is_served_on_its_assistant_row_only_and_the_chat_registry_is_not_served(temp_db):
    db = temp_db
    chat_id = "test_sources_history"
    db.ensure_chat_exists(chat_id, "u1")
    user_id = db.add_message(chat_id=chat_id, role="user", content="q")
    asst_id = db.add_message(chat_id=chat_id, role="assistant", content="answer [[1]]")
    cited = [{"n": 1, "kind": "web", "title": "A", "locator": "https://a", "detail": None}]
    db.add_collection(chat_id=chat_id, parent_message_id=asst_id, parent_type="main", collection_type="sources", items=cited, overwrite=True)
    db.add_collection(chat_id=chat_id, parent_message_id=f"chat:{chat_id}", parent_type="main", collection_type="source_registry", items=cited, overwrite=True)
    woven = {m["id"]: m for m in db.get_woven_history(chat_id)}
    assert [c["collection_type"] for c in woven[asst_id]["collections"]] == ["sources"]
    assert not woven[user_id].get("collections")
    found = [c for c in db.get_collections(chat_id, parent_message_id=f"chat:{chat_id}", parent_type="main") if c["collection_type"] == "source_registry"]
    assert len(found) == 1  # the registry is read back by the chat handler


def test_a_numeric_chat_id_does_not_attach_the_registry_to_a_message(temp_db):
    db = temp_db
    chat_id = "777"
    db.ensure_chat_exists(chat_id, "u1")
    db.add_message(chat_id=chat_id, role="user", content="q")
    asst_id = db.add_message(chat_id=chat_id, role="assistant", content="a")
    db.add_collection(chat_id=chat_id, parent_message_id=f"chat:{chat_id}", parent_type="main", collection_type="source_registry",
                      items=[{"n": 1, "kind": "web", "title": "A", "locator": "https://a", "detail": None}], overwrite=True)
    woven = {m["id"]: m for m in db.get_woven_history(chat_id)}
    assert not woven[asst_id].get("collections")
