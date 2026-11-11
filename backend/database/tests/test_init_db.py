import json
import os
import sqlite3
import pytest
from unittest.mock import patch, MagicMock
from backend.database.init_db import init_db, _create_indexes, _rebuild_table_with_cascade, _repair_leftover_old_tables, _assign_owners, _skills_name_is_globally_unique
from backend.database.db_layer import make_connection

@pytest.fixture
def temp_db_path(tmp_path):
    return str(tmp_path / "test_init.db")

@pytest.fixture(autouse=True)
def admin_email():
    """Rows without an owner are assigned to the admin, so a configured ADMIN_EMAIL is the normal case."""
    with patch("backend.config.ADMIN_EMAIL", "admin@test"):
        yield


@pytest.fixture(autouse=True)
def patch_db_path(temp_db_path):
    with patch("backend.database.init_db.DB_PATH", temp_db_path), \
         patch("backend.database.db_layer.DB_PATH", temp_db_path):
        yield temp_db_path

# Every index the schema defines (all of them live in init_db._create_indexes).
EXPECTED_INDEXES = {
    "messages": {"idx_messages_chat_id"},
    "files": {"idx_files_chat_id"},
    "file_systems": {"idx_file_systems_chat_id", "idx_file_systems_title"},
    "file_system_versions": {"idx_file_system_versions_file_system_id"},
    "file_system_permissions": {"idx_file_system_permissions_file_system_id"},
    "memories": {"idx_memories_tag", "idx_memories_user_id"},
    "sub_agent_messages": {"idx_sub_agent_chat_parent", "idx_sub_agent_sequence"},
    "collections": {"idx_collections_chat_parent", "idx_collections_parent_type"},
    "pending_callbacks": {"idx_pending_cb_chat"},
    "code_execution_history": {"idx_exec_history_chat", "idx_exec_history_created"},
    "workspaces": {"idx_workspaces_user_id"},
    "chats": {"idx_chats_user_id"},
    "personas": {"idx_personas_user_id"},
    "skills": {"idx_skills_user_id"},
}


def _index_names(conn, table):
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=?", (table,)).fetchall()
    return {r[0] for r in rows}


def _assert_all_indexes(conn):
    for table, expected in EXPECTED_INDEXES.items():
        missing = expected - _index_names(conn, table)
        assert not missing, f"{table} is missing {sorted(missing)}"


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
    _assert_all_indexes(conn)
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
    # The workspace migration (step 8) and the cascade rebuild (step 11) drop tables: all indexes are back after one run
    _assert_all_indexes(conn)
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


def test_init_db_restores_indexes_after_cascade_rebuild():
    # Pre-cascade tables (no ON DELETE CASCADE): migration 11 renames, recreates and drops each one, which
    # drops its indexes. They must exist again right after the same run, not only after the next start.
    conn = make_connection()
    conn.execute("CREATE TABLE chats (id TEXT PRIMARY KEY, title TEXT, timestamp REAL)")
    conn.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, role TEXT, content TEXT, "
                 "timestamp REAL, parent_type TEXT DEFAULT 'main')")
    conn.execute("CREATE TABLE sub_agent_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT NOT NULL, "
                 "parent_message_id TEXT NOT NULL, parent_type TEXT DEFAULT 'main', agent_name TEXT NOT NULL, "
                 "sequence_order INTEGER NOT NULL, role TEXT NOT NULL, content TEXT, tool_calls TEXT, "
                 "tool_call_id TEXT, name TEXT, model TEXT, reasoning_content TEXT, timestamp REAL)")
    conn.execute("CREATE TABLE collections (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT NOT NULL, "
                 "parent_message_id TEXT NOT NULL, parent_type TEXT NOT NULL DEFAULT 'main', "
                 "collection_type TEXT NOT NULL, items TEXT NOT NULL, timestamp REAL)")
    conn.execute("CREATE TABLE pending_callbacks (callback_id TEXT PRIMARY KEY, chat_id TEXT NOT NULL, "
                 "parent_message_id INTEGER, parent_type TEXT DEFAULT 'main', tool_name TEXT NOT NULL, "
                 "question TEXT, options TEXT, status TEXT DEFAULT 'pending', response TEXT, "
                 "created_at REAL, resolved_at REAL)")
    conn.execute("INSERT INTO chats (id, title, timestamp) VALUES ('c1', 't', 1.0)")
    conn.execute("INSERT INTO messages (chat_id, role, content, timestamp) VALUES ('c1', 'user', 'hi', 1.0)")
    conn.execute("INSERT INTO sub_agent_messages (chat_id, parent_message_id, agent_name, sequence_order, role) "
                 "VALUES ('c1', '1', 'search_agent', 1, 'assistant')")
    conn.execute("INSERT INTO collections (chat_id, parent_message_id, collection_type, items) "
                 "VALUES ('c1', '1', 'code', '[]')")
    conn.execute("INSERT INTO pending_callbacks (callback_id, chat_id, tool_name) VALUES ('cb1', 'c1', 'ask')")
    conn.commit()
    conn.close()

    for run in range(2):  # the second run is the idempotency check
        init_db()
        conn = make_connection()
        for table in ("messages", "sub_agent_messages", "collections", "pending_callbacks"):
            assert "ON DELETE CASCADE" in conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()[0], (run, table)
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 1, (run, table)
        assert conn.execute("SELECT name FROM sqlite_master WHERE name LIKE '%\\_old' ESCAPE '\\'").fetchall() == []
        _assert_all_indexes(conn)
        conn.close()


def test_create_indexes_restores_dropped_indexes_and_is_idempotent():
    init_db()
    conn = make_connection()
    conn.execute("DROP INDEX idx_sub_agent_sequence")
    conn.execute("DROP INDEX idx_exec_history_created")
    assert "idx_sub_agent_sequence" not in _index_names(conn, "sub_agent_messages")
    c = conn.cursor()
    _create_indexes(c)
    _create_indexes(c)
    _assert_all_indexes(conn)
    conn.close()


def test_init_db_finishes_and_restores_indexes_when_a_rebuild_fails():
    # messages (pre-cascade) rebuilds fine; the pre-cascade files table holds a row the new NOT NULL
    # columns reject, so its copy fails, step 11 only logs, and init_db() still completes with its indexes.
    conn = make_connection()
    conn.execute("CREATE TABLE chats (id TEXT PRIMARY KEY, title TEXT, timestamp REAL)")
    conn.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT, role TEXT, content TEXT, "
                 "timestamp REAL, parent_type TEXT DEFAULT 'main')")
    conn.execute("CREATE TABLE files (id TEXT PRIMARY KEY, chat_id TEXT, original_filename TEXT, stored_filename TEXT, "
                 "mime_type TEXT, file_size INTEGER, content_text TEXT, processing_status TEXT, created_at REAL)")
    conn.execute("INSERT INTO chats (id, title, timestamp) VALUES ('c1', 't', 1.0)")
    conn.execute("INSERT INTO messages (chat_id, role, content, timestamp) VALUES ('c1', 'user', 'hi', 1.0)")
    conn.execute("INSERT INTO files (id, chat_id) VALUES ('f1', 'c1')")  # NULL names: the rebuild copy fails
    conn.commit()
    conn.close()

    init_db()

    conn = make_connection()
    assert "ON DELETE CASCADE" in conn.execute("SELECT sql FROM sqlite_master WHERE name='messages'").fetchone()[0]
    assert conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 1
    # The tables that were not rebuilt keep every index and the rebuilt messages table has its index again.
    for table, expected in EXPECTED_INDEXES.items():
        assert expected <= _index_names(conn, table), table
    conn.close()


@pytest.mark.parametrize("sql", [
    "SELECT * FROM files WHERE chat_id = ? ORDER BY created_at DESC",   # artifact_ops.get_chat_files
    "DELETE FROM files WHERE chat_id = ?",                              # chat_ops.delete_all_chats
    "SELECT c.id FROM chats c WHERE EXISTS (SELECT 1 FROM files f WHERE f.chat_id = c.id) AND c.id = ?",  # sidebar filter
])
def test_files_chat_id_queries_use_the_index(sql):
    init_db()
    conn = make_connection()
    plan = " ".join(r[3] for r in conn.execute("EXPLAIN QUERY PLAN " + sql, ("c1",)))
    assert "idx_files_chat_id" in plan, plan
    conn.close()


def test_files_index_is_added_to_the_previous_schema_without_a_rebuild():
    # The previous schema: files already cascades (so step 11 does not rebuild it) but has no chat_id index.
    def setup(conn):
        conn.execute("CREATE TABLE files (id TEXT PRIMARY KEY, chat_id TEXT NOT NULL, original_filename TEXT NOT NULL, "
                     "stored_filename TEXT NOT NULL, mime_type TEXT NOT NULL, file_size INTEGER NOT NULL, content_text TEXT, "
                     "processing_status TEXT DEFAULT 'pending', created_at REAL DEFAULT (strftime('%s', 'now')), "
                     "FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE)")
        conn.execute("INSERT INTO files (id, chat_id, original_filename, stored_filename, mime_type, file_size) "
                     "VALUES ('f1', 'c1', 'a.txt', 's.txt', 'text/plain', 3)")
    _seed(setup)
    conn = make_connection()
    assert "idx_files_chat_id" not in _index_names(conn, "files")
    conn.close()
    for _ in range(2):
        init_db()
        conn = make_connection()
        assert "idx_files_chat_id" in _index_names(conn, "files") and _count(conn, "files") == 1
        assert not {n for n in _table_names(conn) if n.endswith(("_old", "_new"))}
        conn.close()


def test_files_index_exists_right_after_a_cascade_rebuild_of_files():
    # A pre-cascade files table is rebuilt by migration 11 in this very run; the index must survive it.
    def setup(conn):
        conn.execute("CREATE TABLE files (id TEXT PRIMARY KEY, chat_id TEXT NOT NULL, original_filename TEXT NOT NULL, "
                     "stored_filename TEXT NOT NULL, mime_type TEXT NOT NULL, file_size INTEGER NOT NULL, content_text TEXT, "
                     "processing_status TEXT DEFAULT 'pending', created_at REAL)")
        conn.execute("INSERT INTO files (id, chat_id, original_filename, stored_filename, mime_type, file_size) "
                     "VALUES ('f1', 'c1', 'a.txt', 's.txt', 'text/plain', 3)")
    _seed(setup)
    for _ in range(2):
        init_db()
        conn = make_connection()
        assert "ON DELETE CASCADE" in _ddl(conn, "files") and _count(conn, "files") == 1
        assert "idx_files_chat_id" in _index_names(conn, "files")
        conn.close()


def _users(conn):
    return conn.execute("SELECT email, role, is_active FROM users").fetchall()


def test_init_db_seeds_one_admin_idempotently(temp_db_path):
    with patch("backend.config.ADMIN_EMAIL", "admin@x.io"):
        init_db()
        init_db()
    conn = make_connection()
    assert _users(conn) == [("admin@x.io", "admin", 1)]
    conn.close()


def test_init_db_without_admin_email_seeds_nothing(temp_db_path):
    with patch("backend.config.ADMIN_EMAIL", ""):
        init_db()
    conn = make_connection()
    assert _users(conn) == []
    conn.close()


def test_init_db_promotes_existing_user_with_admin_email(temp_db_path):
    with patch("backend.config.ADMIN_EMAIL", ""):
        init_db()
    conn = make_connection()
    conn.execute("INSERT INTO users (id, email, role, is_active) VALUES ('u1', 'Admin@X.io', 'user', 0)")
    conn.commit()
    conn.close()
    with patch("backend.config.ADMIN_EMAIL", "admin@x.io"):
        init_db()
    conn = make_connection()
    assert _users(conn) == [("Admin@X.io", "admin", 1)]
    conn.close()


def test_users_table_is_added_to_the_previous_schema(temp_db_path):
    with patch("backend.config.ADMIN_EMAIL", ""):
        init_db()
    conn = make_connection()
    conn.execute("DROP TABLE users")
    conn.commit()
    conn.close()
    with patch("backend.config.ADMIN_EMAIL", "admin@x.io"):
        init_db()
    conn = make_connection()
    assert _users(conn) == [("admin@x.io", "admin", 1)]
    conn.close()


# --- ownership (user_id on the root tables) ---

OWNED = ("workspaces", "chats", "personas", "skills", "memories")


def _previous_schema_with_data(conn):
    """The five root tables as they were before ownership (no user_id; skills.name globally unique) with two rows each."""
    conn.executescript("""
        CREATE TABLE workspaces (id TEXT PRIMARY KEY, name TEXT, timestamp REAL, icon TEXT DEFAULT NULL);
        CREATE TABLE personas (id TEXT PRIMARY KEY, name TEXT, content TEXT, is_default INTEGER DEFAULT 0, timestamp REAL);
        CREATE TABLE chats (id TEXT PRIMARY KEY, title TEXT, timestamp REAL, workspace_id TEXT);
        CREATE TABLE memories (id TEXT PRIMARY KEY, content TEXT NOT NULL, tag TEXT NOT NULL, timestamp REAL);
        CREATE TABLE skills (id TEXT PRIMARY KEY, name TEXT UNIQUE, description TEXT, instructions TEXT, timestamp REAL);
        INSERT INTO workspaces VALUES ('w1', 'W1', 1.0, NULL), ('w2', 'W2', 2.0, NULL);
        INSERT INTO personas VALUES ('p1', 'P1', 'c1', 0, 1.0), ('p2', 'P2', 'c2', 1, 2.0);
        INSERT INTO chats VALUES ('c1', 'T1', 1.0, 'w1'), ('c2', 'T2', 2.0, NULL);
        INSERT INTO memories VALUES ('m1', 'x', 'tag', 1.0), ('m2', 'y', 'tag', 2.0);
        INSERT INTO skills VALUES ('s1', 'alpha', 'd', 'i', 1.0), ('s2', 'beta', 'd2', 'i2', 2.0);
    """)
    conn.commit()


def _admin_id(conn):
    return conn.execute("SELECT id FROM users WHERE role = 'admin'").fetchone()[0]


def _skills_unique_columns(conn):
    cols = []
    for index in conn.execute("PRAGMA index_list(skills)").fetchall():
        if index[2] and not index[4]:  # unique, not partial
            cols.append([r[2] for r in conn.execute(f"PRAGMA index_info('{index[1]}')").fetchall()])
    return cols


def test_ownership_migrates_the_previous_schema_without_losing_rows():
    conn = make_connection()
    _previous_schema_with_data(conn)
    conn.close()
    init_db()
    conn = make_connection()
    admin = _admin_id(conn)
    for table in OWNED:
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 2
        assert conn.execute(f"SELECT COUNT(*) FROM {table} WHERE user_id IS NULL").fetchone()[0] == 0
        assert {r[0] for r in conn.execute(f"SELECT user_id FROM {table}")} == {admin}
        assert f"idx_{table}_user_id" in _index_names(conn, table)
    assert conn.execute("SELECT name, description, instructions FROM skills ORDER BY id").fetchall() == [
        ("alpha", "d", "i"), ("beta", "d2", "i2")]
    assert conn.execute("SELECT title, workspace_id FROM chats ORDER BY id").fetchall() == [("T1", "w1"), ("T2", None)]
    conn.close()


def test_skills_names_are_unique_per_user_after_migration():
    conn = make_connection()
    _previous_schema_with_data(conn)
    conn.close()
    init_db()
    conn = make_connection()
    assert ["user_id", "name"] in _skills_unique_columns(conn)
    assert ["name"] not in _skills_unique_columns(conn)
    conn.execute("INSERT INTO skills (id, name, user_id) VALUES ('s3', 'alpha', 'other-user')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO skills (id, name, user_id) VALUES ('s4', 'alpha', 'other-user')")
    conn.close()


def test_ownerless_skill_names_stay_unique_until_the_wrapper_sets_owners():
    init_db()
    conn = make_connection()
    conn.execute("INSERT INTO skills (id, name) VALUES ('s1', 'dup')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO skills (id, name) VALUES ('s2', 'dup')")
    conn.close()


def test_ownerless_skill_cannot_take_the_name_of_an_owned_skill():
    """The unchanged wrapper inserts without an owner; the guard keeps that from creating a clash that would stop the next start."""
    init_db()
    conn = make_connection()
    conn.execute("INSERT INTO skills (id, name, user_id) VALUES ('a', 'foo', ?)", (_admin_id(conn),))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO skills (id, name) VALUES ('b', 'foo')")
    conn.execute("INSERT INTO skills (id, name, user_id) VALUES ('c', 'foo', 'another-user')")  # owned names are per user
    conn.close()


def test_skill_name_guard_also_covers_updates_and_owned_inserts():
    init_db()
    conn = make_connection()
    admin = _admin_id(conn)
    conn.execute("INSERT INTO skills (id, name) VALUES ('x', 'foo')")
    conn.execute("INSERT INTO skills (id, name) VALUES ('y', 'bar')")
    with pytest.raises(sqlite3.IntegrityError):  # rename onto another ownerless skill
        conn.execute("UPDATE skills SET name = 'foo' WHERE id = 'y'")
    with pytest.raises(sqlite3.IntegrityError):  # owned insert of a name an ownerless skill holds
        conn.execute("INSERT INTO skills (id, name, user_id) VALUES ('z', 'foo', ?)", (admin,))
    conn.execute("INSERT INTO skills (id, name, user_id) VALUES ('o', 'baz', ?)", (admin,))
    with pytest.raises(sqlite3.IntegrityError):  # an owned skill cannot take an ownerless skill's name by rename either
        conn.execute("UPDATE skills SET name = 'foo' WHERE id = 'o'")
    conn.close()


def test_skill_name_guard_blocks_clearing_the_owner_when_the_name_is_taken():
    init_db()
    conn = make_connection()
    admin = _admin_id(conn)
    conn.execute("INSERT INTO skills (id, name, user_id) VALUES ('a', 'baz', ?)", (admin,))
    conn.execute("INSERT INTO skills (id, name, user_id) VALUES ('b', 'baz', 'user-b')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE skills SET user_id = NULL WHERE id = 'b'")
    assert conn.execute("SELECT user_id FROM skills WHERE id = 'b'").fetchone()[0] == "user-b"
    conn.close()


def test_skill_name_guard_allows_the_wrapper_upsert_of_an_owned_skill_when_another_user_shares_the_name():
    init_db()
    conn = make_connection()
    admin = _admin_id(conn)
    conn.execute("INSERT INTO skills (id, name, user_id) VALUES ('s1', 'x', ?)", (admin,))
    conn.execute("INSERT INTO skills (id, name, user_id) VALUES ('s2', 'x', 'user-b')")
    upsert = ("INSERT INTO skills (id, name, description) VALUES (?, 'x', 'new') "
              "ON CONFLICT(id) DO UPDATE SET name = excluded.name, description = excluded.description")
    conn.execute(upsert, ("s1",))
    conn.execute(upsert, ("s2",))
    assert conn.execute("SELECT id, description, user_id FROM skills ORDER BY id").fetchall() == [
        ("s1", "new", admin), ("s2", "new", "user-b")]
    conn.execute("INSERT INTO skills (id, name) VALUES ('s3', 'taken')")
    with pytest.raises(sqlite3.IntegrityError):  # a rename through the upsert onto an ownerless name is still caught
        conn.execute("INSERT INTO skills (id, name, description) VALUES ('s1', 'taken', 'r') "
                     "ON CONFLICT(id) DO UPDATE SET name = excluded.name")
    conn.close()


def test_ownerless_duplicates_stop_startup_with_a_clear_error():
    init_db()
    conn = make_connection()
    conn.execute("DROP TRIGGER trg_skills_unowned_name")
    conn.execute("DROP TRIGGER trg_skills_unowned_name_update")
    conn.execute("INSERT INTO skills (id, name) VALUES ('a', 'dup'), ('b', 'dup')")
    conn.commit()
    conn.close()
    with pytest.raises(RuntimeError, match="dup"):
        init_db()


def test_skill_name_guard_allows_an_upsert_of_the_same_skill():
    init_db()
    conn = make_connection()
    conn.execute("INSERT INTO skills (id, name, description) VALUES ('s1', 'x', 'old')")
    conn.execute("INSERT INTO skills (id, name, description) VALUES ('s1', 'x', 'new') "
                 "ON CONFLICT(id) DO UPDATE SET description = excluded.description")
    assert conn.execute("SELECT description FROM skills WHERE id = 's1'").fetchone()[0] == "new"
    conn.close()


def test_skill_name_guard_survives_the_skills_rebuild():
    conn = make_connection()
    _previous_schema_with_data(conn)
    conn.close()
    init_db()
    conn = make_connection()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO skills (id, name) VALUES ('x', 'alpha')")
    conn.close()


def test_ownership_migration_is_idempotent():
    conn = make_connection()
    _previous_schema_with_data(conn)
    conn.close()
    init_db()
    conn = make_connection()
    before = {t: conn.execute(f"SELECT * FROM {t} ORDER BY id").fetchall() for t in OWNED}
    conn.close()
    with patch("backend.database.init_db._rebuild_table_with_cascade") as rebuild, \
         patch("backend.database.init_db.log_event") as events:
        init_db()
    rebuild.assert_not_called()
    assert not [c for c in events.call_args_list if c.args[0] == "db_migration_owner_backfill"]
    conn = make_connection()
    assert {t: conn.execute(f"SELECT * FROM {t} ORDER BY id").fetchall() for t in OWNED} == before
    conn.close()


def test_fresh_database_has_owner_columns_and_no_ownerless_rows():
    init_db()
    init_db()
    conn = make_connection()
    for table in OWNED:
        assert "user_id" in [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        assert conn.execute(f"SELECT COUNT(*) FROM {table} WHERE user_id IS NULL").fetchone()[0] == 0
    assert ["user_id", "name"] in _skills_unique_columns(conn)
    conn.close()


def test_ownerless_chat_is_assigned_to_the_admin_on_the_next_start():
    init_db()
    conn = make_connection()
    conn.execute("INSERT INTO chats (id, title) VALUES ('late', 'created before owners were set')")
    conn.commit()
    admin = _admin_id(conn)
    conn.close()
    with patch("backend.database.init_db.log_event") as events:
        init_db()
    conn = make_connection()
    assert conn.execute("SELECT user_id FROM chats WHERE id = 'late'").fetchone()[0] == admin
    conn.close()
    events.assert_any_call("db_migration_owner_backfill", {"table": "chats", "rows": 1})


def test_ownerless_rows_without_an_admin_stop_startup():
    with patch("backend.config.ADMIN_EMAIL", ""):
        init_db()
        conn = make_connection()
        conn.execute("INSERT INTO chats (id, title) VALUES ('c1', 't')")
        conn.commit()
        conn.close()
        with pytest.raises(RuntimeError, match="ADMIN_EMAIL"):
            init_db()


def test_no_admin_and_no_ownerless_rows_starts_normally():
    with patch("backend.config.ADMIN_EMAIL", ""):
        init_db()
        init_db()


def test_failed_skills_rebuild_stops_startup_and_keeps_the_skills():
    conn = make_connection()
    _previous_schema_with_data(conn)
    conn.close()
    with patch("backend.database.init_db._rebuild_table_with_cascade", return_value=False):
        with pytest.raises(RuntimeError, match="skills"):
            init_db()
    conn = make_connection()
    assert conn.execute("SELECT name FROM skills ORDER BY id").fetchall() == [("alpha",), ("beta",)]
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert ["name"] in _skills_unique_columns(conn)  # still the old constraint
    conn.close()


def test_ownerless_skill_with_the_name_of_an_owned_skill_stops_startup_with_a_clear_error():
    init_db()
    conn = make_connection()
    admin = _admin_id(conn)
    conn.execute("DROP TRIGGER trg_skills_unowned_name")  # simulate rows written before the guard existed
    conn.execute("DROP TRIGGER trg_skills_unowned_name_update")
    conn.execute("INSERT INTO skills (id, name, user_id) VALUES ('a', 'foo', ?)", (admin,))
    conn.execute("INSERT INTO skills (id, name) VALUES ('b', 'foo')")
    conn.commit()
    conn.close()
    with pytest.raises(RuntimeError, match="foo"):
        init_db()
    conn = make_connection()
    assert conn.execute("SELECT COUNT(*) FROM skills WHERE user_id IS NULL").fetchone()[0] == 1  # nothing half-assigned
    conn.close()


def test_skills_name_is_globally_unique_detects_only_the_old_constraint():
    conn = make_connection()
    _previous_schema_with_data(conn)
    assert _skills_name_is_globally_unique(conn.cursor()) is True
    conn.close()
    init_db()
    conn = make_connection()
    assert _skills_name_is_globally_unique(conn.cursor()) is False  # per-user UNIQUE and the partial index do not count
    conn.close()


def test_assign_owners_leaves_foreign_keys_on():
    conn = make_connection()
    _previous_schema_with_data(conn)
    conn.close()
    init_db()
    conn = make_connection()
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    conn.close()


def test_assign_owners_updates_only_null_rows():
    init_db()
    conn = make_connection()
    admin = _admin_id(conn)
    conn.execute("INSERT INTO workspaces (id, name, user_id) VALUES ('mine', 'M', 'someone-else')")
    conn.execute("INSERT INTO workspaces (id, name) VALUES ('orphan', 'O')")
    conn.commit()
    _assign_owners(conn, conn.cursor())
    conn.commit()
    assert dict(conn.execute("SELECT id, user_id FROM workspaces")) == {"mine": "someone-else", "orphan": admin}
    conn.close()


def test_chats_is_temporary_column_on_a_fresh_db_and_added_to_an_older_chats_table():
    init_db()
    init_db()  # idempotent
    conn = make_connection()
    cols = {r[1]: r for r in conn.execute("PRAGMA table_info(chats)").fetchall()}
    conn.close()
    assert "is_temporary" in cols and cols["is_temporary"][4] == "0"  # default 0


def test_is_temporary_is_added_to_an_older_chats_schema_with_zero_on_existing_rows():
    conn = make_connection()
    conn.execute("CREATE TABLE chats (id TEXT PRIMARY KEY, title TEXT, timestamp REAL)")
    conn.execute("INSERT INTO chats (id, title, timestamp) VALUES ('c1', 't', 1.0)")
    conn.commit()
    conn.close()
    init_db()
    init_db()
    conn = make_connection()
    assert conn.execute("SELECT is_temporary FROM chats WHERE id = 'c1'").fetchall() == [(0,)]
    conn.close()
