import os
import uuid
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

def test_file_system_ops(temp_db):
    db = temp_db
    chat_id = "test_chat_fs"
    fs_id = "fs_123"
    filename = "test_file.txt"
    
    # Ensure chat exists to satisfy foreign key constraint
    db.ensure_chat_exists(chat_id, "u1")
    
    # 1. Save FS Meta & _get_file_system_meta_fetch_internal
    db.save_file_system_meta(
        file_system_id=fs_id,
        chat_id=chat_id,
        title="Test File",
        filename=filename,
        file_system_type="text/plain",
        folder="/",
        current_version=1
    )
    
    # 2. Get FS Meta
    meta = db.get_file_system_meta(fs_id, chat_id=chat_id)
    assert meta is not None
    assert meta['filename'] == filename
    
    # Test _get_file_system_meta_fetch_internal
    internal_meta = db._get_file_system_meta_fetch_internal(fs_id, chat_id=chat_id)
    assert internal_meta['filename'] == filename
    
    # 3. Get FS Meta by path
    meta_by_path = db.get_file_system_meta_by_path(filename, chat_id=chat_id)
    assert meta_by_path is not None
    assert meta_by_path['id'] == fs_id
    
    # 4. Save FS Version & Content
    db.save_file_system_version(
        file_system_id=fs_id,
        chat_id=chat_id,
        version_number=1,
        content="hello world",
        comment="Initial version"
    )
    db.save_file_system_version(
        file_system_id=fs_id,
        chat_id=chat_id,
        version_number=2,
        content="hello updated",
        comment="Second version"
    )
    
    # 5. create_file_system_with_version
    fs_id_2 = "fs_124"
    db.create_file_system_with_version(
        file_system_id=fs_id_2,
        chat_id=chat_id,
        title="File 2",
        filename="test2.txt",
        file_system_type="text/plain",
        folder="/",
        content="content 2",
        comment="Init"
    )    
    # 6. get_all_file_systems was removed: no code path may list every user's file systems
    assert not hasattr(db, "get_all_file_systems")
    
    # 7. get_owner_file_systems
    owner_fs = db.get_owner_file_systems(chat_id=chat_id)
    assert len(owner_fs) >= 2
    
    # 8. get_chat_file_systems
    chat_fs = db.get_chat_file_systems(chat_id)
    assert len(chat_fs) >= 2
    
    # 9. get_file_system_versions
    versions = db.get_file_system_versions(fs_id, chat_id=chat_id)
    assert len(versions) == 2
    
    # 10. get_file_system_content_by_id
    content_list = db.get_file_system_content_by_id(fs_id, chat_id=chat_id)
    assert content_list == "hello updated"
    
    # 11. sync_file_system_search_index
    db.sync_file_system_search_index(fs_id, chat_id=chat_id)
    meta_updated = db.get_file_system_meta(fs_id, chat_id=chat_id)
    assert meta_updated is not None

    # 12. get_file_system_current_version
    cur_version = db.get_file_system_current_version(fs_id, chat_id=chat_id)
    assert cur_version is not None
    assert cur_version['version_number'] == 2

    # 14. get_file_system_version_content
    v1_content = db.get_file_system_version_content(fs_id, chat_id=chat_id, version_number=1)
    assert v1_content == "hello world"
    
    # 15. delete_file_system_versions_after
    db.delete_file_system_versions_after(fs_id, chat_id=chat_id, up_to_version=1)
    versions_after = db.get_file_system_versions(fs_id, chat_id=chat_id)
    assert len(versions_after) == 1

    # 17. migrate_file_system_owner
    chat_id_new = "chat_migrated"
    db.ensure_chat_exists(chat_id_new, "u1")
    db.migrate_file_system_owner(
        old_id=fs_id, new_id="fs_123_migrated", 
        old_chat_id=chat_id, old_workspace_id=None, 
        new_chat_id=chat_id_new, new_workspace_id=None, 
        new_filename="test_migrated.txt", new_title="Migrated"
    )
    assert db.get_file_system_meta(fs_id, chat_id=chat_id) is None
    migrated_meta = db.get_file_system_meta("fs_123_migrated", chat_id=chat_id_new)
    assert migrated_meta is not None
    assert migrated_meta['filename'] == "test_migrated.txt"

    # 18. delete_chat_file_system_files
    db.delete_chat_file_system_files(chat_id)
    owner_fs_after = db.get_owner_file_systems(chat_id=chat_id)
    assert len(owner_fs_after) == 0

    # 19. delete_file_system
    db.delete_file_system("fs_123_migrated", chat_id=chat_id_new)
    assert db.get_file_system_meta("fs_123_migrated", chat_id=chat_id_new) is None

def test_legacy_numeric_id_still_readable_and_migratable(temp_db):
    db = temp_db
    for chat in ("legacy_a", "legacy_b", "legacy_c"):
        db.ensure_chat_exists(chat, "u1")
    for chat in ("legacy_a", "legacy_b"):
        db.create_file_system_with_version(
            file_system_id="1", chat_id=chat, title="Legacy", filename="legacy.txt", content="v1"
        )
    assert db.get_file_system_meta("1", chat_id="legacy_a") is not None
    assert db.get_file_system_meta("1", chat_id="legacy_b") is not None

    new_id = str(uuid.uuid4())
    db.migrate_file_system_owner(
        old_id="1", new_id=new_id,
        old_chat_id="legacy_a", old_workspace_id=None,
        new_chat_id="legacy_c", new_workspace_id=None,
        new_filename="moved.txt", new_title="Moved"
    )
    assert db.get_file_system_meta("1", chat_id="legacy_a") is None
    assert db.get_file_system_meta(new_id, chat_id="legacy_c")["filename"] == "moved.txt"
    assert len(db.get_file_system_versions(new_id, chat_id="legacy_c")) == 1
    assert db.get_file_system_meta("1", chat_id="legacy_b") is not None

def test_file_system_workspace_isolation(temp_db):
    db = temp_db
    chat_id = "chat_iso_1"
    workspace_id = "ws_iso_1"
    
    db.ensure_chat_exists(chat_id, "u1")
    # create_workspace is part of ChatOpsMixin, so db has it
    ws = db.create_workspace("Workspace Isolation Test", "u1")
    workspace_id = ws["id"]
    
    # 1. Create a workspace file system record
    db.create_file_system_with_version(
        file_system_id="fs_ws",
        workspace_id=workspace_id,
        chat_id=None,
        title="Workspace File",
        filename="ws_file.md",
        content="workspace content"
    )
    
    # 2. Create a chat-only file system record
    db.create_file_system_with_version(
        file_system_id="fs_chat",
        workspace_id=None,
        chat_id=chat_id,
        title="Chat File",
        filename="chat_file.md",
        content="chat content"
    )
    
    # Verify isolation in meta fetching
    meta_ws = db.get_file_system_meta("fs_ws", workspace_id=workspace_id)
    assert meta_ws is not None
    assert meta_ws["filename"] == "ws_file.md"
    
    meta_ws_under_chat = db.get_file_system_meta("fs_ws", chat_id=chat_id)
    assert meta_ws_under_chat is None
    
    meta_chat = db.get_file_system_meta("fs_chat", chat_id=chat_id)
    assert meta_chat is not None
    assert meta_chat["filename"] == "chat_file.md"
    
    meta_chat_under_ws = db.get_file_system_meta("fs_chat", workspace_id=workspace_id)
    assert meta_chat_under_ws is None
    
    # Verify isolation in owner listings
    ws_files = db.get_owner_file_systems(workspace_id=workspace_id)
    assert any(f["id"] == "fs_ws" for f in ws_files)
    assert not any(f["id"] == "fs_chat" for f in ws_files)
    
    chat_files = db.get_owner_file_systems(chat_id=chat_id)
    assert any(f["id"] == "fs_chat" for f in chat_files)
    assert not any(f["id"] == "fs_ws" for f in chat_files)

def test_file_system_fts_index(temp_db):
    db = temp_db
    chat_id = "chat_fts_1"
    db.ensure_chat_exists(chat_id, "u1")
    
    fs_id = "fs_fts"
    db.create_file_system_with_version(
        file_system_id=fs_id,
        chat_id=chat_id,
        title="Searchable File",
        filename="search.md",
        content="UniqueWordForFTS search text content"
    )
    
    # Sync index
    res = db.sync_file_system_search_index(fs_id, chat_id=chat_id)
    assert res is True
    
    # Verify record in fts search table directly
    from backend.database.db_layer import make_connection
    import sqlite3
    conn = make_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT content FROM file_systems_search WHERE id = ?", (fs_id,))
        row = c.fetchone()
        assert row is not None
        assert "UniqueWordForFTS" in row[0]
    except sqlite3.OperationalError:
        pass  # SQLite on host may not support FTS5
    finally:
        conn.close()
        
    # Delete file system
    db.delete_file_system(fs_id, chat_id=chat_id)
    
    # Verify record deleted from fts table
    conn = make_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM file_systems_search WHERE id = ?", (fs_id,))
        count = c.fetchone()[0]
        assert count == 0
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()

def test_file_system_versions_rollback(temp_db):
    db = temp_db
    chat_id = "chat_rollback_1"
    db.ensure_chat_exists(chat_id, "u1")
    
    fs_id = "fs_rollback"
    db.create_file_system_with_version(
        file_system_id=fs_id,
        chat_id=chat_id,
        title="Versioned File",
        filename="version.md",
        content="v1 content"
    )
    
    db.save_file_system_version(fs_id, chat_id=chat_id, version_number=2, content="v2 content")
    db.save_file_system_version(fs_id, chat_id=chat_id, version_number=3, content="v3 content")
    
    # Verify current is version 3
    meta = db.get_file_system_meta(fs_id, chat_id=chat_id)
    assert meta["current_version"] == 3
    
    # Rollback/delete versions after 1
    db.delete_file_system_versions_after(fs_id, chat_id=chat_id, up_to_version=1)
    
    # Verify current rolled back to 1
    meta_after = db.get_file_system_meta(fs_id, chat_id=chat_id)
    assert meta_after["current_version"] == 1
    
    # Verify version 2 and 3 contents are deleted
    versions = db.get_file_system_versions(fs_id, chat_id=chat_id)
    assert len(versions) == 1
    assert versions[0]["version_number"] == 1
    assert versions[0]["content"] == "v1 content"
