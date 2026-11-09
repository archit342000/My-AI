import json
import os
import sqlite3
import pytest
from unittest.mock import patch, MagicMock
from backend.database.init_db import init_db, _rebuild_table_with_cascade, _repair_leftover_old_tables
from backend.database.db_layer import make_connection

@pytest.fixture
def temp_db_path(tmp_path):
    return str(tmp_path / "test_init.db")

@pytest.fixture(autouse=True)
def patch_db_path(temp_db_path):
    with patch("backend.database.init_db.DB_PATH", temp_db_path), \
         patch("backend.database.db_layer.DB_PATH", temp_db_path):
        yield temp_db_path

def test_init_db(temp_db_path):
    # Should create DB and apply schema/migrations without errors
    init_db()
    
    # Run a second time to ensure idempotency and migration skipping logic
    init_db()
    
    conn = make_connection()
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in c.fetchall()]
    assert "chats" in tables
    assert "messages" in tables
    assert "file_systems" in tables
    assert "file_system_counters" not in tables
    conn.close()

def test_init_db_with_legacy_data(temp_db_path):
    # Setup legacy tables to trigger migrations
    conn = make_connection()
    c = conn.cursor()
    # Mock legacy canvases table (to be renamed to file_systems)
    c.execute("CREATE TABLE canvases (id TEXT, chat_id TEXT, title TEXT, filename TEXT, folder TEXT, timestamp REAL)")
    c.execute("CREATE TABLE canvas_versions (id INTEGER PRIMARY KEY, canvas_id TEXT, chat_id TEXT, version_number INTEGER, content TEXT, author TEXT, timestamp REAL, comment TEXT)")
    c.execute("CREATE TABLE canvas_permissions (id INTEGER PRIMARY KEY, canvas_id TEXT, chat_id TEXT, user_id TEXT, permission TEXT, timestamp REAL)")
    c.execute("CREATE TABLE canvas_counters (chat_id TEXT PRIMARY KEY, counter INTEGER DEFAULT 0)")
    
    # Mock legacy chats table
    c.execute("CREATE TABLE chats (id TEXT PRIMARY KEY, memory_mode INTEGER, canvas_mode INTEGER, folder TEXT, message_order_map TEXT)")
    # Insert a dummy chat with a folder to trigger workspace migration
    c.execute("INSERT INTO chats (id, memory_mode, canvas_mode, folder, message_order_map) VALUES ('c1', 1, 1, 'Test Folder', '[1, 2]')")
    # Insert another with invalid json map
    c.execute("INSERT INTO chats (id, memory_mode, canvas_mode, folder, message_order_map) VALUES ('c2', 1, 1, NULL, 'invalid')")
    
    # Mock legacy messages
    c.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, chat_id TEXT, role TEXT, content TEXT, parent_type TEXT)")
    c.execute("INSERT INTO messages (id, chat_id, role, content) VALUES (1, 'c1', 'user', 'hello')")
    c.execute("INSERT INTO messages (id, chat_id, role, content) VALUES (2, 'c1', 'assistant', '<think>hmm</think>hi')")
    
    # Mock sub_agent_messages
    c.execute("CREATE TABLE sub_agent_messages (id INTEGER PRIMARY KEY, chat_id TEXT, parent_message_id TEXT, agent_name TEXT, role TEXT, content TEXT, sequence_order INTEGER, parent_type TEXT)")
    c.execute("INSERT INTO sub_agent_messages (chat_id, parent_message_id, agent_name, role, content, sequence_order, parent_type) VALUES ('c1', '1', 'canvas_agent', 'assistant', 'test', 1, 'canvas_agent')")
    c.execute("INSERT INTO sub_agent_messages (chat_id, parent_message_id, agent_name, role, content, sequence_order, parent_type) VALUES ('c1', '1', 'file_agent', 'assistant', 'test file', 2, 'file_agent')")
    
    # Mock collections
    c.execute("CREATE TABLE collections (id INTEGER PRIMARY KEY, chat_id TEXT, parent_message_id TEXT, parent_type TEXT, collection_type TEXT, items TEXT)")
    c.execute("INSERT INTO collections (chat_id, parent_message_id, parent_type, collection_type, items) VALUES ('c1', '1', 'file_agent', 'code', '[]')")

    # Mock pending_callbacks
    c.execute("CREATE TABLE pending_callbacks (callback_id TEXT PRIMARY KEY, chat_id TEXT, parent_type TEXT, tool_name TEXT, status TEXT DEFAULT 'pending')")
    c.execute("INSERT INTO pending_callbacks (callback_id, chat_id, parent_type, tool_name) VALUES ('cb1', 'c1', 'file_agent', 'grep_uploaded_file')")

    conn.commit()
    conn.close()
    
    # Run init_db to trigger migrations on legacy data
    init_db()
    
    # Verify migrations
    conn = make_connection()
    c = conn.cursor()
    c.execute("SELECT user_preferences, file_system_mode, workspace_id FROM chats WHERE id='c1'")
    row = c.fetchone()
    assert row[0] == 1 # memory_mode migrated
    assert row[1] == 1 # canvas_mode migrated
    assert row[2] is not None # workspace_id assigned
    
    c.execute("SELECT parent_type FROM sub_agent_messages WHERE agent_name='file_system_agent'")
    sub_agent_rows = c.fetchall()
    assert len(sub_agent_rows) > 0

    # Verify rebranding of file_agent to document_agent
    c.execute("SELECT agent_name, parent_type FROM sub_agent_messages WHERE agent_name='document_agent'")
    doc_sub_agent_rows = c.fetchall()
    assert len(doc_sub_agent_rows) == 1
    assert doc_sub_agent_rows[0] == ('document_agent', 'document_agent')

    c.execute("SELECT parent_type FROM collections WHERE parent_type='document_agent'")
    coll_rows = c.fetchall()
    assert len(coll_rows) == 1

    c.execute("SELECT parent_type FROM pending_callbacks WHERE parent_type='document_agent'")
    cb_rows = c.fetchall()
    assert len(cb_rows) == 1
    
    c.execute("SELECT reasoning_content FROM messages WHERE id=2")
    reasoning = c.fetchone()[0]
    assert reasoning == "hmm"

    # The legacy counter tables are gone (canvas_counters is renamed on the way, then dropped)
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('canvas_counters', 'file_system_counters')")
    assert c.fetchall() == []

    # The ON DELETE CASCADE recreate keeps rows and adds the attachments column
    c.execute("PRAGMA table_info(messages)")
    assert "attachments" in [r[1] for r in c.fetchall()]
    c.execute("SELECT COUNT(*) FROM messages")
    assert c.fetchone()[0] == 2
    conn.close()

def test_init_db_error():
    with patch("backend.database.init_db.make_connection") as mock_make:
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.execute.side_effect = Exception("Mock DB Init Error")
        mock_make.return_value = mock_conn
        
        with pytest.raises(Exception, match="Mock DB Init Error"):
            init_db()

def test_db_schema_cascade_integrity(temp_db_path):
    init_db()
    conn = make_connection()
    c = conn.cursor()

    # 1. Insert Workspace
    c.execute("INSERT INTO workspaces (id, name, timestamp) VALUES ('w1', 'Test Workspace', 123.45)")

    # 2. Insert Chat referencing w1
    c.execute("""
        INSERT INTO chats (id, title, timestamp, workspace_id)
        VALUES ('c1', 'Test Chat', 123.45, 'w1')
    """)

    # 3. Insert Message referencing c1
    c.execute("""
        INSERT INTO messages (chat_id, role, content, timestamp)
        VALUES ('c1', 'user', 'hello', 123.45)
    """)

    # 4. Insert File System referencing c1 (workspace_id must be NULL)
    c.execute("""
        INSERT INTO file_systems (id, chat_id, workspace_id, title, filename, timestamp, current_version)
        VALUES ('fs1', 'c1', NULL, 'Test FS', 'test.md', 123.45, 1)
    """)

    # 5. Insert File System Version referencing fs1
    c.execute("""
        INSERT INTO file_system_versions (file_system_id, chat_id, workspace_id, version_number, content, timestamp)
        VALUES ('fs1', 'c1', NULL, 1, 'File content', 123.45)
    """)

    conn.commit()

    # Verify everything exists initially
    c.execute("SELECT workspace_id FROM chats WHERE id = 'c1'")
    assert c.fetchone()[0] == 'w1'

    c.execute("SELECT count(*) FROM messages WHERE chat_id = 'c1'")
    assert c.fetchone()[0] == 1

    c.execute("SELECT count(*) FROM file_systems WHERE id = 'fs1' AND chat_id = 'c1'")
    assert c.fetchone()[0] == 1

    c.execute("SELECT count(*) FROM file_system_versions WHERE file_system_id = 'fs1' AND chat_id = 'c1'")
    assert c.fetchone()[0] == 1

    # 6. Delete Workspace w1 -> chats.workspace_id should become NULL (ON DELETE SET NULL)
    c.execute("DELETE FROM workspaces WHERE id = 'w1'")
    conn.commit()

    c.execute("SELECT workspace_id FROM chats WHERE id = 'c1'")
    assert c.fetchone()[0] is None

    # 7. Delete Chat c1 -> should cascade delete messages and file_systems.
    # Note: file_system_versions uses a composite FK (file_system_id, chat_id, workspace_id)
    # where workspace_id is NULL. Under SQLite's MATCH SIMPLE rule, composite foreign keys containing NULLs
    # do not trigger cascading deletes on the child table. This is why delete_chat handles the cleanup
    # of file_system_versions and file_system_permissions explicitly in a transaction.
    # Here, we verify the native cascading deletions for messages and file_systems.
    c.execute("DELETE FROM chats WHERE id = 'c1'")
    conn.commit()

    c.execute("SELECT count(*) FROM messages WHERE chat_id = 'c1'")
    assert c.fetchone()[0] == 0

    c.execute("SELECT count(*) FROM file_systems WHERE id = 'fs1' AND chat_id = 'c1'")
    assert c.fetchone()[0] == 0

    conn.close()

def test_init_db_preference_migration(temp_db_path):
    conn = make_connection()
    c = conn.cursor()
    # Create tables
    c.execute("CREATE TABLE chats (id TEXT PRIMARY KEY)")
    c.execute("INSERT INTO chats (id) VALUES ('c1')")
    c.execute("""
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT,
            role TEXT,
            content TEXT,
            timestamp REAL,
            model TEXT,
            tool_calls TEXT,
            tool_call_id TEXT,
            name TEXT,
            parent_id INTEGER,
            parent_type TEXT DEFAULT 'main',
            reasoning_content TEXT
        )
    """)
    c.execute("""
        CREATE TABLE sub_agent_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT,
            parent_message_id TEXT,
            parent_type TEXT DEFAULT 'main',
            agent_name TEXT,
            sequence_order INTEGER,
            role TEXT,
            content TEXT,
            tool_calls TEXT,
            tool_call_id TEXT,
            name TEXT,
            model TEXT,
            reasoning_content TEXT,
            timestamp REAL
        )
    """)
    # Insert assistant message with manage_user_preferences tool call
    tc_json = '[{"id": "call_1", "type": "function", "function": {"name": "manage_user_preferences", "arguments": "{\\"additions\\": [{\\"content\\": \\"Likes apple\\", \\"tag\\": \\"preference\\"}], \\"edits\\": [{\\"id\\": \\"id_xyz\\", \\"content\\": \\"New tag content\\", \\"tag\\": \\"other\\"}], \\"deletions\\": [\\"id_del\\"]}"}}]'
    c.execute("INSERT INTO messages (chat_id, role, content, tool_calls, timestamp) VALUES ('c1', 'assistant', 'Thinking', ?, 123.45)", (tc_json,))
    
    # Insert tool response message
    c.execute("INSERT INTO messages (chat_id, role, content, name, tool_call_id, timestamp) VALUES ('c1', 'tool', 'Operations summary', 'manage_user_preferences', 'call_1', 123.46)")
    
    conn.commit()
    conn.close()
    
    # Run init_db
    init_db()
    
    # Verify migration results
    conn = make_connection()
    c = conn.cursor()
    
    # Check assistant message tool calls
    c.execute("SELECT tool_calls FROM messages WHERE role='assistant'")
    tc_res = c.fetchone()[0]
    import json
    tc_list = json.loads(tc_res)
    assert len(tc_list) == 3
    assert tc_list[0]["id"] == "call_1_add_0"
    assert tc_list[0]["function"]["name"] == "add_user_preference"
    assert json.loads(tc_list[0]["function"]["arguments"]) == {"content": "Likes apple", "tag": "preference"}
    
    assert tc_list[1]["id"] == "call_1_edit_0"
    assert tc_list[1]["function"]["name"] == "edit_user_preference"
    assert json.loads(tc_list[1]["function"]["arguments"]) == {"id": "id_xyz", "content": "New tag content", "tag": "other"}
    
    assert tc_list[2]["id"] == "call_1_del_0"
    assert tc_list[2]["function"]["name"] == "delete_user_preference"
    assert json.loads(tc_list[2]["function"]["arguments"]) == {"id": "id_del"}
    
    # Check tool response messages (should be 3 new messages, old one deleted)
    c.execute("SELECT tool_call_id, name, content FROM messages WHERE role='tool' ORDER BY tool_call_id")
    resp_rows = c.fetchall()
    assert len(resp_rows) == 3
    assert resp_rows[0][0] == "call_1_add_0"
    assert resp_rows[0][1] == "add_user_preference"
    assert "Added preference: Likes apple" in resp_rows[0][2]
    
    assert resp_rows[1][0] == "call_1_del_0"
    assert resp_rows[1][1] == "delete_user_preference"
    assert "Deleted preference [id_del]: OK" in resp_rows[1][2]
    
    assert resp_rows[2][0] == "call_1_edit_0"
    assert resp_rows[2][1] == "edit_user_preference"
    assert "Updated preference [id_xyz]: OK" in resp_rows[2][2]
    
    conn.close()


def test_init_db_replace_migration(temp_db_path):
    conn = make_connection()
    c = conn.cursor()
    # Create tables
    c.execute("CREATE TABLE chats (id TEXT PRIMARY KEY)")
    c.execute("INSERT INTO chats (id) VALUES ('c1')")
    c.execute("""
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT,
            role TEXT,
            content TEXT,
            timestamp REAL,
            model TEXT,
            tool_calls TEXT,
            tool_call_id TEXT,
            name TEXT,
            parent_id INTEGER,
            parent_type TEXT DEFAULT 'main',
            reasoning_content TEXT
        )
    """)
    c.execute("""
        CREATE TABLE sub_agent_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT,
            parent_message_id TEXT,
            parent_type TEXT DEFAULT 'main',
            agent_name TEXT,
            sequence_order INTEGER,
            role TEXT,
            content TEXT,
            tool_calls TEXT,
            tool_call_id TEXT,
            name TEXT,
            model TEXT,
            reasoning_content TEXT,
            timestamp REAL
        )
    """)
    # Insert assistant message with replace_fs_text tool call
    tc_json = '[{"id": "call_text_1", "type": "function", "function": {"name": "replace_fs_text", "arguments": "{\\"path\\": \\"test.py\\", \\"expected_version\\": 1, \\"edits\\": [{\\"target_text\\": \\"old\\", \\"new_content\\": \\"new\\", \\"start_line\\": 10, \\"end_line\\": 10, \\"allow_multiple\\": true}]}"}}]'
    c.execute("INSERT INTO messages (chat_id, role, content, tool_calls, timestamp) VALUES ('c1', 'assistant', 'Thinking', ?, 123.45)", (tc_json,))
    
    # Insert tool response message
    resp_json = '{"success": true, "file_system_id": "fs_123", "version_id": 2, "message": "Applied 1 of 1 edits.", "edit_results": [{"edit_index": 0, "status": "applied"}], "diff": "-old\\n+new"}'
    c.execute("INSERT INTO messages (chat_id, role, content, name, tool_call_id, timestamp) VALUES ('c1', 'tool', ?, 'replace_fs_text', 'call_text_1', 123.46)", (resp_json,))
    
    conn.commit()
    conn.close()
    
    # Run init_db
    init_db()
    
    # Verify migration results
    conn = make_connection()
    c = conn.cursor()
    
    # Check assistant message tool calls
    c.execute("SELECT tool_calls FROM messages WHERE role='assistant'")
    tc_res = c.fetchone()[0]
    import json
    tc_list = json.loads(tc_res)
    assert len(tc_list) == 1
    assert tc_list[0]["id"] == "call_text_1"
    assert tc_list[0]["function"]["name"] == "replace_fs_text"
    args = json.loads(tc_list[0]["function"]["arguments"])
    assert args["path"] == "test.py"
    assert args["expected_version"] == 1
    assert args["target_text"] == "old"
    assert args["new_content"] == "new"
    assert args["start_line"] == 10
    assert args["end_line"] == 10
    assert args["allow_multiple"] is True
    
    # Check tool response message
    c.execute("SELECT tool_call_id, name, content FROM messages WHERE role='tool'")
    resp_rows = c.fetchall()
    assert len(resp_rows) == 1
    assert resp_rows[0][0] == "call_text_1"
    assert resp_rows[0][1] == "replace_fs_text"
    resp_content = json.loads(resp_rows[0][2])
    assert resp_content["success"] is True
    assert resp_content["file_system_id"] == "fs_123"
    assert resp_content["version_id"] == 2
    assert "Applied edit" in resp_content["message"]
    assert resp_content["diff"] == "-old\n+new"
    assert resp_content["edit_results"] == [{"edit_index": 0, "status": "applied"}]
    
    conn.close()


def _message_columns(conn):
    return {r[1]: r for r in conn.execute("PRAGMA table_info(messages)").fetchall()}


def test_messages_attachments_column_on_fresh_db():
    init_db()
    init_db()
    conn = make_connection()
    cols = _message_columns(conn)
    conn.close()
    assert "attachments" in cols
    assert cols["attachments"][3] == 0  # nullable


def test_messages_attachments_added_and_backfilled_from_file_collections():
    # Previous schema: messages with ON DELETE CASCADE but without attachments, so only the
    # PRAGMA/ALTER path of the new migration runs (not the CASCADE recreate).
    conn = make_connection()
    conn.execute("CREATE TABLE chats (id TEXT PRIMARY KEY, title TEXT, timestamp REAL)")
    conn.execute("""
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, role TEXT, content TEXT, timestamp REAL,
            model TEXT, tool_calls TEXT, tool_call_id TEXT, name TEXT, parent_id INTEGER,
            parent_type TEXT DEFAULT 'main', reasoning_content TEXT,
            FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE TABLE collections (
            id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT NOT NULL, parent_message_id TEXT NOT NULL,
            parent_type TEXT NOT NULL DEFAULT 'main', collection_type TEXT NOT NULL, items TEXT NOT NULL, timestamp REAL
        )
    """)
    conn.execute("INSERT INTO chats (id, title, timestamp) VALUES ('c1', 't', 1.0)")
    for mid, role, content in [(1, "user", "with files"), (2, "assistant", "reply"), (3, "user", "no files"),
                               (4, "user", "bad items"), (5, "user", "wrong type")]:
        conn.execute("INSERT INTO messages (id, chat_id, role, content, timestamp) VALUES (?, 'c1', ?, ?, 1.0)",
                     (mid, role, content))
    items = [{"file_id": "f1", "name": "a.txt", "size": 3, "mime_type": "text/plain", "extra": "dropped"}, "junk"]
    conn.execute("INSERT INTO collections (chat_id, parent_message_id, parent_type, collection_type, items) "
                 "VALUES ('c1', '1', 'main', 'files', ?)", (json.dumps(items),))
    conn.execute("INSERT INTO collections (chat_id, parent_message_id, parent_type, collection_type, items) "
                 "VALUES ('c1', '4', 'main', 'files', 'not json')")
    conn.execute("INSERT INTO collections (chat_id, parent_message_id, parent_type, collection_type, items) "
                 "VALUES ('c1', '5', 'main', 'code', '[{\"file_id\": \"x\"}]')")
    conn.commit()
    conn.close()

    init_db()
    init_db()  # idempotent: no error and no duplicate column

    conn = make_connection()
    assert "attachments" in _message_columns(conn)
    rows = {r[0]: r[1] for r in conn.execute("SELECT id, attachments FROM messages").fetchall()}
    contents = {r[0]: r[1] for r in conn.execute("SELECT id, content FROM messages").fetchall()}
    conn.close()
    assert json.loads(rows[1]) == [{"file_id": "f1", "name": "a.txt", "size": 3, "mime_type": "text/plain"}]
    assert rows[2] is None   # assistant rows are never backfilled
    assert rows[3] is None   # no files collection
    assert rows[4] is None   # unparsable items
    assert rows[5] is None   # collection of another type
    assert contents[1] == "with files"  # other columns intact


def test_messages_attachments_backfill_runs_once():
    init_db()
    conn = make_connection()
    conn.execute("INSERT INTO chats (id, title, timestamp) VALUES ('c1', 't', 1.0)")
    cur = conn.execute("INSERT INTO messages (chat_id, role, content, timestamp) VALUES ('c1', 'user', 'late', 1.0)")
    msg_id = cur.lastrowid
    conn.execute("INSERT INTO collections (chat_id, parent_message_id, parent_type, collection_type, items) "
                 "VALUES ('c1', ?, 'main', 'files', ?)", (str(msg_id), json.dumps([{"file_id": "f1", "name": "a.txt"}])))
    conn.commit()
    conn.close()

    init_db()  # the column already exists, so the backfill must not run again

    conn = make_connection()
    row = conn.execute("SELECT attachments FROM messages WHERE id = ?", (msg_id,)).fetchone()
    conn.close()
    assert row[0] is None


def test_messages_attachments_backfilled_on_cascade_recreate_path():
    # messages without ON DELETE CASCADE: migration 11 recreates the table (the new definition already
    # has the column), and the backfill must still run once.
    conn = make_connection()
    conn.execute("CREATE TABLE chats (id TEXT PRIMARY KEY, title TEXT, timestamp REAL)")
    conn.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, role TEXT, content TEXT, "
                 "timestamp REAL, parent_type TEXT DEFAULT 'main')")
    conn.execute("CREATE TABLE collections (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT NOT NULL, "
                 "parent_message_id TEXT NOT NULL, parent_type TEXT NOT NULL DEFAULT 'main', "
                 "collection_type TEXT NOT NULL, items TEXT NOT NULL, timestamp REAL)")
    conn.execute("INSERT INTO chats (id, title, timestamp) VALUES ('c1', 't', 1.0)")
    conn.execute("INSERT INTO messages (id, chat_id, role, content, timestamp) VALUES (1, 'c1', 'user', 'with files', 1.0)")
    conn.execute("INSERT INTO messages (id, chat_id, role, content, timestamp) VALUES (2, 'c1', 'user', 'plain', 1.0)")
    conn.execute("INSERT INTO collections (chat_id, parent_message_id, parent_type, collection_type, items) "
                 "VALUES ('c1', '1', 'main', 'files', ?)",
                 (json.dumps([{"file_id": "f1", "name": "a.txt", "size": 3, "mime_type": "text/plain", "extra": 1}]),))
    conn.commit()
    conn.close()

    init_db()
    init_db()

    conn = make_connection()
    assert "ON DELETE CASCADE" in conn.execute("SELECT sql FROM sqlite_master WHERE name = 'messages'").fetchone()[0]
    rows = {r[0]: r[1] for r in conn.execute("SELECT id, attachments FROM messages").fetchall()}
    conn.close()
    assert json.loads(rows[1]) == [{"file_id": "f1", "name": "a.txt", "size": 3, "mime_type": "text/plain"}]
    assert rows[2] is None


def test_init_db_drops_file_system_counters_and_keeps_numeric_id_artifacts():
    # A database from the previous schema: current tables plus the counter table, holding an artifact
    # with an old per-owner numeric id.
    init_db()
    conn = make_connection()
    conn.execute("CREATE TABLE file_system_counters (owner_id TEXT PRIMARY KEY, counter INTEGER DEFAULT 0)")
    conn.execute("INSERT INTO file_system_counters (owner_id, counter) VALUES ('chat_old', 7)")
    conn.execute("INSERT INTO chats (id, title, timestamp) VALUES ('chat_old', 't', 1.0)")
    conn.execute("INSERT INTO file_systems (id, chat_id, workspace_id, title, filename, timestamp, folder, current_version) "
                 "VALUES ('7', 'chat_old', NULL, 'Old', 'old.txt', 1.0, '', 1)")
    conn.execute("INSERT INTO file_system_versions (file_system_id, chat_id, workspace_id, version_number, content, author, timestamp, comment) "
                 "VALUES ('7', 'chat_old', NULL, 1, 'old body', 'system', 1.0, 'init')")
    conn.commit()
    conn.close()

    init_db()
    init_db()  # idempotent

    conn = make_connection()
    assert conn.execute("SELECT name FROM sqlite_master WHERE name = 'file_system_counters'").fetchall() == []
    assert conn.execute("SELECT title FROM file_systems WHERE id = '7' AND chat_id = 'chat_old'").fetchone()[0] == "Old"
    assert conn.execute("SELECT content FROM file_system_versions WHERE file_system_id = '7' AND chat_id = 'chat_old'").fetchone()[0] == "old body"
    conn.close()


# ---- migration 11: atomic table rebuilds and repair of leftover `_old` tables --------------------------------

PRE_CASCADE = {
    "messages": "CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, role TEXT, content TEXT, "
                "timestamp REAL, parent_type TEXT DEFAULT 'main')",
    "sub_agent_messages": "CREATE TABLE {name} (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT NOT NULL, "
                          "parent_message_id TEXT NOT NULL, parent_type TEXT DEFAULT 'main', agent_name TEXT NOT NULL, "
                          "sequence_order INTEGER NOT NULL, role TEXT NOT NULL, content TEXT, tool_calls TEXT, "
                          "tool_call_id TEXT, name TEXT, model TEXT, reasoning_content TEXT, timestamp REAL)",
    "collections": "CREATE TABLE {name} (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT NOT NULL, "
                   "parent_message_id TEXT NOT NULL, parent_type TEXT NOT NULL DEFAULT 'main', "
                   "collection_type TEXT NOT NULL, items TEXT NOT NULL, timestamp REAL)",
    "pending_callbacks": "CREATE TABLE {name} (callback_id TEXT PRIMARY KEY, chat_id TEXT NOT NULL, "
                         "parent_message_id INTEGER, parent_type TEXT DEFAULT 'main', tool_name TEXT NOT NULL, "
                         "question TEXT, options TEXT, status TEXT DEFAULT 'pending', response TEXT, "
                         "created_at REAL, resolved_at REAL)",
}
INSERT_ROW = {
    "sub_agent_messages": "INSERT INTO {name} (chat_id, parent_message_id, agent_name, sequence_order, role) "
                          "VALUES ('c1', '1', 'search_agent', {n}, 'assistant')",
    "collections": "INSERT INTO {name} (chat_id, parent_message_id, collection_type, items) VALUES ('c1', '1', 'code', '[]')",
    "pending_callbacks": "INSERT INTO {name} (callback_id, chat_id, tool_name) VALUES ('cb{n}', 'c1', 'ask')",
}


def _table_names(conn):
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def _ddl(conn, table):
    return conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()[0]


def _seed(setup):
    """Create a DB with a chat 'c1', let `setup(conn)` add old-schema tables, then close it."""
    conn = make_connection()
    conn.execute("CREATE TABLE chats (id TEXT PRIMARY KEY, title TEXT, timestamp REAL)")
    conn.execute("INSERT INTO chats (id, title, timestamp) VALUES ('c1', 't', 1.0)")
    setup(conn)
    conn.commit()
    conn.close()


def _pre_cascade(conn, table, name=None, rows=1):
    name = name or table
    conn.execute(PRE_CASCADE[table].format(name=name))
    for n in range(rows):
        if table == "messages":
            conn.execute(f"INSERT INTO {name} (chat_id, role, content, timestamp) VALUES ('c1', 'user', 'm{n}', 1.0)")
        else:
            conn.execute(INSERT_ROW[table].format(name=name, n=n + 1))


def test_failed_rebuild_leaves_the_original_table_unchanged_and_the_others_migrate():
    def setup(conn):
        _pre_cascade(conn, "messages")
        # old definition is looser than the new one: the NULL collection_type cannot be copied
        conn.execute("CREATE TABLE collections (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, "
                     "parent_message_id TEXT, parent_type TEXT, collection_type TEXT, items TEXT, timestamp REAL)")
        conn.execute("INSERT INTO collections (chat_id, parent_message_id, collection_type, items) VALUES ('c1', '1', 'code', '[]')")
        conn.execute("INSERT INTO collections (chat_id, parent_message_id, collection_type, items) VALUES ('c1', '2', NULL, '[]')")
        _pre_cascade(conn, "pending_callbacks")
    _seed(setup)

    with patch("backend.database.init_db.log_event") as log:
        for _ in range(2):  # the second run retries and ends in the same state without raising
            init_db()
            conn = make_connection()
            assert "ON DELETE CASCADE" not in _ddl(conn, "collections")
            assert _count(conn, "collections") == 2
            assert not {"collections_new", "collections_old"} & _table_names(conn)
            assert "ON DELETE CASCADE" in _ddl(conn, "messages") and _count(conn, "messages") == 1
            assert "ON DELETE CASCADE" in _ddl(conn, "pending_callbacks") and _count(conn, "pending_callbacks") == 1
            conn.close()
    errors = [c.args for c in log.call_args_list if c.args[0] == "db_migration_rebuild_error"]
    assert errors and all(a[1]["table"] == "collections" for a in errors)


def test_rebuilt_tables_cascade_when_a_chat_is_deleted():
    _seed(lambda conn: [_pre_cascade(conn, t) for t in ("messages", "sub_agent_messages")])
    init_db()
    conn = make_connection()  # foreign keys are on for every new connection
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    conn.execute("DELETE FROM chats WHERE id='c1'")
    conn.commit()
    assert _count(conn, "messages") == 0 and _count(conn, "sub_agent_messages") == 0
    conn.close()


def test_successful_rebuilds_keep_every_index_in_the_same_run():
    _seed(lambda conn: [_pre_cascade(conn, t) for t in ("sub_agent_messages", "collections")])
    init_db()
    conn = make_connection()
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    for table in ("sub_agent_messages", "collections"):
        assert "ON DELETE CASCADE" in _ddl(conn, table)
    assert {"idx_sub_agent_chat_parent", "idx_sub_agent_sequence",
            "idx_collections_chat_parent", "idx_collections_parent_type"} <= names
    conn.close()


def test_leftover_old_tables_are_repaired_or_reported():
    def setup(conn):
        _pre_cascade(conn, "sub_agent_messages", rows=0)               # empty new table ...
        _pre_cascade(conn, "sub_agent_messages", "sub_agent_messages_old", rows=2)   # ... and the data in _old
        _pre_cascade(conn, "pending_callbacks", "pending_callbacks_old", rows=1)      # table missing, only _old
        _pre_cascade(conn, "collections", rows=1)                                      # both have rows
        _pre_cascade(conn, "collections", "collections_old", rows=2)
    _seed(setup)

    with patch("backend.database.init_db.log_event") as log:
        for _ in range(2):
            init_db()
            conn = make_connection()
            tables = _table_names(conn)
            assert "sub_agent_messages_old" not in tables and "pending_callbacks_old" not in tables
            assert _count(conn, "sub_agent_messages") == 2 and "ON DELETE CASCADE" in _ddl(conn, "sub_agent_messages")
            assert _count(conn, "pending_callbacks") == 1 and "ON DELETE CASCADE" in _ddl(conn, "pending_callbacks")
            # both held rows: nothing dropped, the old copy is kept for a manual decision
            assert _count(conn, "collections") == 1 and _count(conn, "collections_old") == 2
            conn.close()
    assert any(c.args[0] == "db_migration_leftover_old_table_error" and c.args[1]["table"] == "collections"
               for c in log.call_args_list)


def test_rebuild_helper_keeps_rows_and_indexes_and_rolls_back_failures():
    conn = make_connection()
    new_sql = "CREATE TABLE t (id INTEGER PRIMARY KEY, a TEXT NOT NULL, b TEXT DEFAULT 'x')"
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, a TEXT)")
    conn.execute("CREATE INDEX idx_t_a ON t(a)")
    conn.execute("INSERT INTO t (id, a) VALUES (1, 'one')")
    conn.commit()
    assert _rebuild_table_with_cascade(conn, "t", new_sql) is True
    assert conn.execute("SELECT id, a, b FROM t").fetchall() == [(1, "one", "x")]
    assert _index_names_of(conn, "t") == {"idx_t_a"}
    assert "t_new" not in _table_names(conn)

    # a NOT NULL violation in the copy: rolled back, the table and its index are as before
    conn.execute("CREATE TABLE u (id INTEGER PRIMARY KEY, a TEXT)")
    conn.execute("CREATE INDEX idx_u_a ON u(a)")
    conn.execute("INSERT INTO u (id, a) VALUES (1, NULL)")
    conn.commit()
    with patch("backend.database.init_db.log_event"):
        assert _rebuild_table_with_cascade(conn, "u", new_sql.replace("CREATE TABLE t", "CREATE TABLE u")) is False
    assert conn.execute("SELECT id, a FROM u").fetchall() == [(1, None)]
    assert _index_names_of(conn, "u") == {"idx_u_a"} and "u_new" not in _table_names(conn)

    # an old column that the new definition lacks would lose data: refused
    conn.execute("CREATE TABLE v (id INTEGER PRIMARY KEY, a TEXT, extra TEXT)")
    conn.execute("INSERT INTO v (id, a, extra) VALUES (1, 'x', 'keep me')")
    conn.commit()
    with patch("backend.database.init_db.log_event"):
        assert _rebuild_table_with_cascade(conn, "v", "CREATE TABLE v (id INTEGER PRIMARY KEY, a TEXT)") is False
    assert conn.execute("SELECT extra FROM v").fetchall() == [("keep me",)]
    conn.close()


def _index_names_of(conn, table):
    return {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=? AND sql IS NOT NULL", (table,))}


def test_repair_helper_handles_each_leftover_state():
    conn = make_connection()
    for name, rows in (("a", 0), ("a_old", 0), ("b_old", 2), ("c", 0), ("c_old", 2), ("d", 1), ("d_old", 1)):
        conn.execute(f"CREATE TABLE {name} (id INTEGER)")
        for n in range(rows):
            conn.execute(f"INSERT INTO {name} VALUES ({n})")
    conn.commit()
    with patch("backend.database.init_db.log_event") as log:
        _repair_leftover_old_tables(conn, ["a", "b", "c", "d", "e"])
    tables = _table_names(conn)
    assert "a_old" not in tables and _count(conn, "a") == 0          # empty _old dropped
    assert "b_old" not in tables and _count(conn, "b") == 2          # table missing: renamed back
    assert "c_old" not in tables and _count(conn, "c") == 2          # empty table replaced by the data
    assert _count(conn, "d") == 1 and _count(conn, "d_old") == 1     # both have rows: untouched, reported
    log.assert_called_once()
    assert log.call_args.args[0] == "db_migration_leftover_old_table_error" and log.call_args.args[1]["table"] == "d"
    conn.close()
