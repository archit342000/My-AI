import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import os
import json
import uuid

from backend.file_system import manager
from backend.file_system.utils import generate_fs_file_id as real_generate_fs_file_id
from backend.file_system.fuzzy_matcher import MatchNotFoundError, MultipleMatchesError

@pytest.fixture
def mock_db():
    with patch('backend.file_system.manager.db') as m:
        yield m

@pytest.fixture
def mock_aiofiles():
    with patch('backend.file_system.manager.aiofiles') as m:
        mock_file = AsyncMock()
        mock_file.__aenter__.return_value = mock_file
        m.open.return_value = mock_file
        yield m

@pytest.fixture
def mock_os():
    with patch('backend.file_system.manager.os') as m:
        m.path.join.side_effect = os.path.join
        m.path.basename.side_effect = os.path.basename
        m.path.splitext.side_effect = os.path.splitext
        yield m

@pytest.fixture
def mock_fitz():
    with patch('backend.file_system.manager.fitz') as m:
        yield m

@pytest.fixture
def mock_channel():
    with patch('backend.file_system.manager.FileSystemChannelManager') as m:
        mock_chan = AsyncMock()
        m.get_channel.return_value = mock_chan
        yield m

@pytest.fixture
def mock_utils():
    with patch('backend.file_system.manager.get_workspace_for_chat') as m_workspace, \
         patch('backend.file_system.utils.get_workspace_for_chat') as m_utils_workspace, \
         patch('backend.file_system.manager.resolve_owner_and_physical_path') as m_resolve, \
         patch('backend.file_system.manager.ensure_physical_dir_exists') as m_ensure, \
         patch('backend.file_system.manager.generate_fs_file_id', new_callable=AsyncMock) as m_gen_id, \
         patch('backend.file_system.manager.sanitize_path') as m_sanitize_path, \
         patch('backend.file_system.manager.sanitize_filename') as m_sanitize_file:
        
        m_workspace.return_value = None
        m_utils_workspace.return_value = None
        m_resolve.return_value = ("chat_123", None, "/physical/path")
        m_gen_id.return_value = "fs_123"
        m_sanitize_path.side_effect = lambda x: x
        m_sanitize_file.side_effect = lambda x: x
        
        yield {
            "get_workspace_for_chat": m_workspace,
            "resolve_owner_and_physical_path": m_resolve,
            "ensure_physical_dir_exists": m_ensure,
            "generate_fs_file_id": m_gen_id,
            "sanitize_path": m_sanitize_path,
            "sanitize_filename": m_sanitize_file
        }

def test_get_all_file_systems_for_chat(mock_db, mock_utils):
    mock_db.get_chat_file_systems.return_value = [{"filename": "f1"}]
    mock_utils["get_workspace_for_chat"].return_value = "ws_1"
    mock_db.get_owner_file_systems.return_value = [{"filename": "f2"}]
    
    result = manager.get_all_file_systems_for_chat("chat_123")
    assert len(result) == 2
    assert result[0]["filename"] == "f1"
    assert result[1]["filename"] == "workspace/f2"

def test_resolve_path_to_fs_file(mock_db, mock_utils):
    mock_db.get_file_system_meta_by_path.return_value = {"id": "fs_123"}
    
    res = manager.resolve_path_to_fs_file("chat_123", "path/to/file")
    assert res == {"id": "fs_123"}
    
    # Test not found
    mock_db.get_file_system_meta_by_path.return_value = None
    with pytest.raises(FileNotFoundError):
        manager.resolve_path_to_fs_file("chat_123", "path/to/file")

@pytest.mark.anyio
async def test_create_fs_file(mock_db, mock_channel, mock_utils, mock_aiofiles):
    mock_db.get_file_system_meta_by_path.return_value = None
    
    res = await manager.create_fs_file("chat_123", "test.txt", "content")
    assert res["success"] is True
    assert res["action"] == "create"
    mock_channel.get_channel.assert_called_with("chat_123")
    
    # Test existing file
    mock_db.get_file_system_meta_by_path.return_value = {"id": "fs_123"}
    res = await manager.create_fs_file("chat_123", "test.txt", "content")
    assert res["success"] is False

    # Test empty path validation
    mock_utils["sanitize_path"].return_value = ""
    res = await manager.create_fs_file("chat_123", "", "content")
    assert res["success"] is False
    assert "Invalid path" in res["error"]
    mock_utils["sanitize_path"].side_effect = lambda x: x

@pytest.mark.anyio
async def test_create_fs_file_on_a_missing_chat_is_an_error_and_writes_nothing(mock_db, mock_channel, mock_utils, mock_aiofiles):
    mock_db.get_chat_owner.return_value = None
    res = await manager.create_fs_file("no_such_chat", "test.txt", "content")
    assert res == {"success": False, "error": "Chat not found"}
    mock_db.ensure_chat_exists.assert_not_called()  # the manager never creates chats; routes do
    mock_aiofiles.open.assert_not_called()  # and nothing is written to disk
    mock_db.create_file_system_with_version.assert_not_called()

@pytest.mark.anyio
async def test_create_fs_file_assigns_uuid4_id(mock_db, mock_channel, mock_utils, mock_aiofiles):
    """The create path uses the real id helper (not the fixture's mock) and gets a UUID4."""
    mock_db.get_file_system_meta_by_path.return_value = None
    with patch('backend.file_system.manager.generate_fs_file_id', new=real_generate_fs_file_id):
        res = await manager.create_fs_file("chat_123", "test.txt", "content")
    assert res["success"] is True
    assert uuid.UUID(res["file_system_id"]).version == 4
    assert mock_db.create_file_system_with_version.call_args.kwargs["file_system_id"] == res["file_system_id"]

@pytest.mark.anyio
async def test_create_fs_file_language_inference(mock_db, mock_channel, mock_utils, mock_aiofiles):
    mock_db.get_file_system_meta_by_path.return_value = None
    
    # Test .py file inference
    await manager.create_fs_file("chat_123", "script.py", "print('hello')")
    mock_db.create_file_system_with_version.assert_called()
    call_args = mock_db.create_file_system_with_version.call_args[1]
    assert call_args["language"] == "py"
    
    # Test explicit language override
    await manager.create_fs_file("chat_123", "script.py", "print('hello')", language="python")
    call_args = mock_db.create_file_system_with_version.call_args[1]
    assert call_args["language"] == "python"
    
    # Test .md file remains markdown
    await manager.create_fs_file("chat_123", "doc.md", "# Hello")
    call_args = mock_db.create_file_system_with_version.call_args[1]
    assert call_args["language"] == "markdown"

@pytest.mark.anyio
async def test_get_fs_file_content(mock_db):
    mock_db.get_file_system_content_by_id.return_value = "content"
    res = await manager.get_fs_file_content("fs_123")
    assert res == "content"

@pytest.mark.anyio
async def test_update_fs_file_content(mock_db, mock_channel, mock_aiofiles, mock_os):
    mock_db.get_file_system_meta.return_value = {"filename": "test.txt", "chat_id": "chat_1", "title": "t", "workspace_id": None}
    mock_db.get_file_system_versions.return_value = [{"version_number": 1}]
    
    res = await manager.update_fs_file_content("fs_123", "chat_1", "new content")
    assert res["success"] is True
    assert res["version_id"] == 2
    
    # Not found
    mock_db.get_file_system_meta.return_value = None
    res = await manager.update_fs_file_content("fs_123", "chat_1", "new content")
    assert res["success"] is False

@pytest.mark.anyio
async def test_append_to_fs_file(mock_db, mock_channel, mock_aiofiles):
    with patch('backend.file_system.manager.get_fs_file_content', new_callable=AsyncMock) as m_get, \
         patch('backend.file_system.manager.update_fs_file_content', new_callable=AsyncMock) as m_upd:
        m_get.return_value = "old"
        m_upd.return_value = {"success": True}
        
        res = await manager.append_to_fs_file("fs_123", "chat_1", "new")
        assert res["success"] is True
        m_upd.assert_called_with("fs_123", "chat_1", "old\n\nnew", author="system", version_comment="Content appended")

@pytest.mark.anyio
async def test_delete_fs_file(mock_db, mock_channel, mock_os):
    mock_db.get_file_system_meta.return_value = {"filename": "test.txt", "chat_id": "chat_1", "workspace_id": None}
    mock_os.path.exists.return_value = True
    
    res = await manager.delete_fs_file("fs_123", "chat_1")
    assert res["success"] is True
    mock_os.remove.assert_called()

def test_get_unique_folders(mock_db):
    with patch('backend.file_system.manager.get_all_file_systems_for_chat') as m_get_all:
        m_get_all.return_value = [{"folder": "f1"}, {"title": "f2/test.txt"}, {"folder": "", "title": "root.txt"}]
        res = manager.get_unique_folders("chat_1")
        assert res == ["f1", "f2"]

@pytest.mark.anyio
async def test_get_chat_file_systems_with_details(mock_db):
    with patch('backend.file_system.manager.get_all_file_systems_for_chat') as m_get_all, \
         patch('backend.file_system.manager.get_fs_file_content', new_callable=AsyncMock) as m_get_content:
        m_get_all.return_value = [{"id": "fs_1", "title": "t1", "filename": "f1", "timestamp": 123}]
        m_get_content.return_value = "content"
        
        res = await manager.get_chat_file_systems_with_details("chat_1", True)
        assert len(res) == 1
        assert res[0]["content"] == "content"

@pytest.mark.anyio
async def test_export_fs_file_markdown(mock_db, mock_utils):
    mock_utils["get_workspace_for_chat"].return_value = None
    mock_db.get_file_system_meta.return_value = {"chat_id": "c1", "workspace_id": None, "language": "python", "title": "t1"}
    with patch('backend.file_system.manager.get_fs_file_content', new_callable=AsyncMock) as m_get_content:
        m_get_content.return_value = "content"
        content, filename = await manager.export_fs_file_markdown("fs_1", "chat_1")
        assert content == "content"
        assert filename == "t1.py"

@pytest.mark.anyio
async def test_export_fs_file_html(mock_db, mock_utils):
    mock_utils["get_workspace_for_chat"].return_value = None
    mock_db.get_file_system_meta.return_value = {"chat_id": "c1", "workspace_id": None, "title": "t1"}
    with patch('backend.file_system.manager.get_fs_file_content', new_callable=AsyncMock) as m_get_content, \
         patch('markdown.markdown') as m_md:
        m_get_content.return_value = "content"
        m_md.return_value = "<p>content</p>"
        content, filename = await manager.export_fs_file_html("fs_1", "chat_1")
        assert "<p>content</p>" in content
        assert filename == "t1.html"

@pytest.mark.anyio
async def test_export_fs_file_pdf(mock_db, mock_utils, mock_fitz):
    mock_utils["get_workspace_for_chat"].return_value = None
    mock_db.get_file_system_meta.return_value = {"chat_id": "c1", "workspace_id": None, "title": "t1"}
    with patch('backend.file_system.manager.export_fs_file_html', new_callable=AsyncMock) as m_html:
        m_html.return_value = ("<html></html>", "t1.html")
        mock_doc = MagicMock()
        mock_doc.tobytes.return_value = b"pdf"
        mock_fitz.open.return_value = mock_doc
        mock_fitz.Rect = MagicMock()
        mock_story = MagicMock()
        mock_story.draw.return_value = (None, True)
        mock_fitz.Story.return_value = mock_story
        
        content, filename = await manager.export_fs_file_pdf("fs_1", "chat_1")
        assert content == b"pdf"
        assert filename == "t1.pdf"

def test_get_file_system_versions(mock_db, mock_utils):
    mock_db.get_file_system_meta.return_value = {"chat_id": "c1", "workspace_id": None}
    mock_db.get_file_system_versions.return_value = [{"v": 1}]
    
    res = manager.get_file_system_versions("fs_1", "chat_1")
    assert res == [{"v": 1}]

@pytest.mark.anyio
async def test_restore_fs_file_version(mock_db, mock_aiofiles, mock_utils):
    mock_db.get_file_system_meta.return_value = {"chat_id": "c1", "workspace_id": None, "filename": "f1"}
    mock_db.get_file_system_version_content.return_value = "old content"
    
    res = await manager.restore_fs_file_version("fs_1", "chat_1", 1)
    assert res["success"] is True
    assert res["content"] == "old content"

def test_get_fs_file_version(mock_db, mock_utils):
    mock_db.get_file_system_meta.return_value = {"chat_id": "c1", "workspace_id": None}
    mock_db.get_file_system_version_content.return_value = "content"
    
    res = manager.get_fs_file_version("fs_1", "chat_1", 1)
    assert res["content"] == "content"
    assert res["version_number"] == 1

def test_get_fs_file_diff(mock_utils):
    with patch('backend.file_system.manager.get_fs_file_version') as m_get_ver:
        m_get_ver.side_effect = [{"content": "line1\nline2"}, {"content": "line1\nline3"}]
        res = manager.get_fs_file_diff("fs_1", "chat_1", 1, 2)
        assert res["success"] is True
        assert res["added_lines"] == ["line3"]
        assert res["removed_lines"] == ["line2"]

def test_delete_chat_fs_files(mock_db, mock_os):
    mock_os.path.exists.return_value = True
    mock_db.delete_chat_file_system_files.return_value = {"success": True}
    
    with patch('shutil.rmtree') as m_rmtree:
        res = manager.delete_chat_fs_files("chat_1")
        assert res["success"] is True
        m_rmtree.assert_called()

@pytest.mark.anyio
async def test_read_fs_file_lines(mock_db):
    with patch('backend.file_system.manager.resolve_path_to_fs_file') as m_res, \
         patch('backend.file_system.manager.get_fs_file_content', new_callable=AsyncMock) as m_get_content:
        m_res.return_value = {"id": "fs_1", "chat_id": "c1", "workspace_id": None, "current_version": 1}
        m_get_content.return_value = "l1\nl2\nl3"
        
        res = await manager.read_fs_file_lines("path", "c1", {"start_line": 1, "end_line": 2})
        assert res["success"] is True
        assert res["content"] == "1 | l1\n2 | l2"
        
        # outline mode
        res = await manager.read_fs_file_lines("path", "c1", {"outline": True})
        assert res["success"] is True

def test_update_file_system_metadata(mock_db, mock_os, mock_utils):
    with patch('backend.file_system.manager.resolve_path_to_fs_file') as m_res:
        m_res.return_value = {"id": "fs_1", "chat_id": "c1", "workspace_id": None}
        mock_db.get_file_system_meta_by_path.return_value = None
        
        res = manager.update_file_system_metadata("c1", "old.txt", new_path="new.txt")
        assert res["success"] is True
        mock_os.rename.assert_called()

def test_update_file_system_metadata_owner_change_uses_uuid(mock_db, mock_os, mock_utils):
    mock_utils["resolve_owner_and_physical_path"].return_value = (None, "ws_1", "/physical/new")
    mock_os.path.exists.return_value = False
    with patch('backend.file_system.manager.resolve_path_to_fs_file') as m_res:
        m_res.return_value = {"id": "1", "chat_id": "c1", "workspace_id": None}
        mock_db.get_file_system_meta_by_path.return_value = None

        res = manager.update_file_system_metadata("c1", "old.txt", new_path="workspace/new.txt")

    assert res["success"] is True
    new_id = mock_db.migrate_file_system_owner.call_args.kwargs["new_id"]
    assert str(uuid.UUID(new_id)) == new_id
    assert uuid.UUID(new_id).version == 4
    assert new_id != "1"
    assert res["file_system_id"] == new_id

@pytest.mark.anyio
async def test_navigate_file_system_version(mock_db, mock_aiofiles, mock_utils):
    mock_db.get_file_system_meta.return_value = {"chat_id": "c1", "workspace_id": None, "filename": "f1"}
    mock_db.get_file_system_version_content.return_value = "content"
    
    res = await manager.navigate_file_system_version("c1", "fs_1", 2)
    assert res["success"] is True
    assert res["version_number"] == 2

@pytest.mark.anyio
async def test_ls_files_for_tool(mock_os, mock_utils):
    with patch('backend.file_system.manager.get_all_file_systems_for_chat') as m_get_all:
        m_get_all.return_value = [{"filename": "dir1/f1.txt"}]
        mock_os.listdir.return_value = []
        
        res = await manager.ls_files_for_tool("c1", "")
        assert res["path"] == "/"
        assert any(c["name"] == "dir1" for c in res["children"])

@pytest.mark.anyio
async def test_grep_files():
    with patch('backend.file_system.manager.get_all_file_systems_for_chat') as m_get_all, \
         patch('backend.file_system.manager.get_fs_file_content', new_callable=AsyncMock) as m_get_content:
        m_get_all.return_value = [{"id": "fs_1", "chat_id": "c1", "workspace_id": None, "filename": "f1"}]
        m_get_content.return_value = "hello world\nfoo bar"
        
        res = await manager.grep_files("c1", "world")
        assert res["success"] is True
        assert len(res["results"]) == 1
        assert "hello world" in res["results"][0]["matches"][0]["text"]

@pytest.mark.anyio
async def test_read_fs_file():
    with patch('backend.file_system.manager.read_fs_file_lines', new_callable=AsyncMock) as m_lines:
        m_lines.return_value = {"success": True}
        res = await manager.read_fs_file("c1", "path")
        assert res["success"] is True

@pytest.mark.anyio
async def test_finalize_edits():
    with patch('backend.file_system.manager.update_fs_file_content', new_callable=AsyncMock) as m_upd:
        res = await manager._finalize_edits("c1", "fs_1", None, 1, ["a", "b"], ["a", "c"], [{"status": "applied"}])
        assert res["success"] is True
        assert res["version_id"] == 2

@pytest.mark.anyio
async def test_replace_fs_text():
    with patch('backend.file_system.manager.resolve_path_to_fs_file') as m_res, \
         patch('backend.file_system.manager.get_fs_file_content', new_callable=AsyncMock) as m_get_content, \
         patch('backend.file_system.manager._finalize_edits', new_callable=AsyncMock) as m_fin, \
         patch('backend.file_system.manager._find_exact_match') as m_find:
        
        m_res.return_value = {"id": "fs_1", "chat_id": "c1", "workspace_id": None, "current_version": 1}
        m_get_content.return_value = "hello world"
        m_fin.return_value = {"success": True}
        m_find.return_value = "hello"
        
        res = await manager.replace_fs_text("c1", "path", 1, target_text="hello", new_content="hi")
        assert res["success"] is True

@pytest.mark.anyio
async def test_replace_fs_lines():
    with patch('backend.file_system.manager.resolve_path_to_fs_file') as m_res, \
         patch('backend.file_system.manager.get_fs_file_content', new_callable=AsyncMock) as m_get_content, \
         patch('backend.file_system.manager._finalize_edits', new_callable=AsyncMock) as m_fin:
        
        m_res.return_value = {"id": "fs_1", "chat_id": "c1", "workspace_id": None, "current_version": 1}
        m_get_content.return_value = "l1\nl2"
        m_fin.return_value = {"success": True}
        
        res = await manager.replace_fs_lines("c1", "path", 1, start_line=1, end_line=1, new_content="n1")
        assert res["success"] is True

@pytest.mark.anyio
async def test_create_directory_tool(mock_utils, mock_os):
    mock_os.path.exists.return_value = False
    res = await manager.create_directory_tool("c1", "dir")
    assert res["success"] is True
    mock_os.makedirs.assert_called()

@pytest.mark.anyio
async def test_delete_directory_tool(mock_utils, mock_os, mock_db):
    mock_os.path.exists.return_value = True
    mock_os.path.isdir.return_value = True
    mock_db.get_chat_file_systems.return_value = []
    
    with patch('shutil.rmtree') as m_rmtree:
        res = await manager.delete_directory_tool("c1", "dir")
        assert res["success"] is True
        m_rmtree.assert_called()

@pytest.mark.anyio
async def test_move_fs_file_tool():
    with patch('backend.file_system.manager.update_file_system_metadata') as m_upd:
        m_upd.return_value = {"success": True}
        res = await manager.move_fs_file_tool("c1", "src", "dst")
        assert res["success"] is True

@pytest.mark.anyio
async def test_patch_file_system(mock_db, mock_utils):
    mock_db.get_file_system_meta.return_value = {"chat_id": "c1", "workspace_id": None, "filename": "f1"}
    with patch('backend.file_system.manager.update_fs_file_content', new_callable=AsyncMock) as m_upd:
        res = await manager.patch_file_system("c1", "fs_1", content="new")
        assert res["success"] is True
        m_upd.assert_called()

@pytest.mark.anyio
async def test_delete_file_system_tool():
    with patch('backend.file_system.manager.resolve_path_to_fs_file') as m_res, \
         patch('backend.file_system.manager.delete_fs_file', new_callable=AsyncMock) as m_del:
        m_res.return_value = {"id": "fs_1", "chat_id": "c1", "workspace_id": None}
        m_del.return_value = {"success": True}
        
        res = await manager.delete_file_system_tool("c1", "path")
        assert res["success"] is True

@pytest.mark.anyio
async def test_create_fs_file_nonexistent_workspace(mock_db, mock_channel, mock_utils, mock_aiofiles):
    # Mock resolve_owner_and_physical_path to return a workspace target_workspace_id
    mock_utils["resolve_owner_and_physical_path"].return_value = (None, "nonexistent_ws", "/physical/path")
    mock_db.get_file_system_meta_by_path.return_value = None

    # Patch make_connection to return a mock connection where fetchone returns None (workspace not found)
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None
    mock_conn.cursor.return_value = mock_cursor

    with patch('backend.database.db_layer.make_connection', return_value=mock_conn):
        with pytest.raises(ValueError) as exc_info:
            await manager.create_fs_file(None, "workspace/test.txt", "content", workspace_id="nonexistent_ws")
        
        assert "does not exist in the database" in str(exc_info.value)
        mock_cursor.execute.assert_called_with("SELECT id FROM workspaces WHERE id = ?", ("nonexistent_ws",))

@pytest.mark.anyio
async def test_create_fs_file_existent_workspace(mock_db, mock_channel, mock_utils, mock_aiofiles):
    # Mock resolve_owner_and_physical_path to return a workspace target_workspace_id
    mock_utils["resolve_owner_and_physical_path"].return_value = (None, "existent_ws", "/physical/path")
    mock_db.get_file_system_meta_by_path.return_value = None

    # Patch make_connection to return a mock connection where fetchone returns a workspace ID
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = ("existent_ws",)
    mock_conn.cursor.return_value = mock_cursor

    with patch('backend.database.db_layer.make_connection', return_value=mock_conn):
        res = await manager.create_fs_file(None, "workspace/test.txt", "content", workspace_id="existent_ws")
        assert res["success"] is True
        mock_cursor.execute.assert_called_with("SELECT id FROM workspaces WHERE id = ?", ("existent_ws",))

def test_is_binary_file(tmp_path):
    # Test text file
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("Hello, world! This is a plain text file.")
    assert manager.is_binary_file(str(txt_file)) is False

    # Test binary file with null byte
    bin_file = tmp_path / "test.bin"
    bin_file.write_bytes(b"Hello\x00world")
    assert manager.is_binary_file(str(bin_file)) is True

    # Test common binary extensions
    png_file = tmp_path / "image.png"
    png_file.write_text("fake png content")
    assert manager.is_binary_file(str(png_file)) is True

@pytest.mark.anyio
async def test_resolve_and_get_disk_fallback(tmp_path, mock_db):
    # Setup a physical file on disk
    file_path = tmp_path / "workspace_file.txt"
    file_path.write_text("Content of physical file on disk.")

    with patch('backend.file_system.manager.resolve_owner_and_physical_path') as mock_resolve:
        mock_resolve.return_value = (None, "w1", str(file_path))
        mock_db.get_file_system_meta_by_path.return_value = None

        # 1. Test resolve_path_to_fs_file fallback
        meta = manager.resolve_path_to_fs_file(None, "workspace/workspace_file.txt", workspace_id="w1")
        assert meta["id"] == "disk:workspace/workspace_file.txt"
        assert meta["filename"] == "workspace/workspace_file.txt"
        assert meta["title"] == "workspace_file.txt"

        # 2. Test get_fs_file_content fallback
        mock_db.get_file_system_content_by_id.return_value = None
        content = await manager.get_fs_file_content(meta["id"], workspace_id="w1")
        assert content == "Content of physical file on disk."

@pytest.mark.anyio
async def test_parameter_type_coercion():
    with patch('backend.file_system.manager.resolve_path_to_fs_file') as m_res, \
         patch('backend.file_system.manager.get_fs_file_content', new_callable=AsyncMock) as m_get_content, \
         patch('backend.file_system.manager._finalize_edits', new_callable=AsyncMock) as m_fin:
        
        # Test replace_fs_lines with string version and line numbers
        m_res.return_value = {"id": "fs_1", "chat_id": "c1", "workspace_id": None, "current_version": 1}
        m_get_content.return_value = "line1\nline2\nline3"
        m_fin.return_value = {"success": True}
        
        res = await manager.replace_fs_lines(
            "c1", "path", "1", start_line="2", end_line="2", new_content="n2"
        )
        assert res["success"] is True
        
        # Test replace_fs_text with string expected_version
        with patch('backend.file_system.manager._find_exact_match') as m_find:
            m_find.return_value = "line2"
            res_text = await manager.replace_fs_text(
                "c1", "path", "1", target_text="line2", new_content="n2"
            )
            assert res_text["success"] is True

        # Test read_fs_file_lines with string start/end lines
        res_read = await manager.read_fs_file("c1", "path", start_line="1", end_line="2")
        assert res_read["success"] is True
        assert res_read["content"] == "1 | line1\n2 | line2"

        # Test grep_files with string context_chars and max_matches
        with patch('backend.file_system.manager.get_all_file_systems_for_chat') as m_get_all:
            m_get_all.return_value = [{"id": "fs_1", "chat_id": "c1", "workspace_id": None, "filename": "f1"}]
            res_grep = await manager.grep_files(
                "c1", "line2", context_chars="100", max_matches_per_file_system="2"
            )
            assert res_grep["success"] is True

@pytest.mark.anyio
async def test_create_fs_file_with_clipboard_key(mock_db, mock_channel, mock_utils, mock_aiofiles):
    mock_utils["resolve_owner_and_physical_path"].return_value = ("c1", None, "/physical/path")
    mock_db.get_file_system_meta_by_path.return_value = None
    
    with patch('backend.file_system.manager.db.clipboard_get') as mock_clip_get:
        mock_clip_get.return_value = "Content from clipboard key"
        
        res = await manager.create_fs_file(
            chat_id="c1",
            path="src/main.py",
            clipboard_key="cb-key-123"
        )
        assert res["success"] is True
        mock_clip_get.assert_called_with("c1", "cb-key-123")

@pytest.mark.anyio
async def test_replace_fs_text_with_clipboard_key():
    with patch('backend.file_system.manager.resolve_path_to_fs_file') as m_res, \
         patch('backend.file_system.manager.get_fs_file_content', new_callable=AsyncMock) as m_get_content, \
         patch('backend.file_system.manager.db.clipboard_get') as mock_clip_get, \
         patch('backend.file_system.manager._find_exact_match') as m_find, \
         patch('backend.file_system.manager._finalize_edits', new_callable=AsyncMock) as m_fin:
        
        m_res.return_value = {"id": "fs_1", "chat_id": "c1", "workspace_id": None, "current_version": 1}
        m_get_content.return_value = "line1\ntarget\nline3"
        mock_clip_get.return_value = "replacement text"
        m_find.return_value = "target"
        m_fin.return_value = {"success": True}
        
        res = await manager.replace_fs_text(
            chat_id="c1",
            path="path",
            expected_version=1,
            target_text="target",
            clipboard_key="cb-key-replace"
        )
        assert res["success"] is True
        mock_clip_get.assert_called_with("c1", "cb-key-replace")

@pytest.mark.anyio
async def test_replace_fs_lines_with_clipboard_key():
    with patch('backend.file_system.manager.resolve_path_to_fs_file') as m_res, \
         patch('backend.file_system.manager.get_fs_file_content', new_callable=AsyncMock) as m_get_content, \
         patch('backend.file_system.manager.db.clipboard_get') as mock_clip_get, \
         patch('backend.file_system.manager._finalize_edits', new_callable=AsyncMock) as m_fin:
         
        m_res.return_value = {"id": "fs_1", "chat_id": "c1", "workspace_id": None, "current_version": 1}
        m_get_content.return_value = "line1\nline2\nline3"
        mock_clip_get.return_value = "replacement text"
        m_fin.return_value = {"success": True}
        
        res = await manager.replace_fs_lines(
            chat_id="c1",
            path="path",
            expected_version=1,
            start_line=2,
            end_line=2,
            clipboard_key="cb-key-replace-lines"
        )
        assert res["success"] is True
        mock_clip_get.assert_called_with("c1", "cb-key-replace-lines")






@pytest.mark.asyncio
async def test_search_fs_contents_finds_hits_in_file_then_line_order_case_insensitively():
    rows = [{"id": "a", "filename": "a.md"}, {"id": "b", "filename": "workspace/b.py", "workspace_id": "w1"}]
    contents = {"a": "Hello world\nnothing\nsay HELLO again", "b": "hello"}
    with patch('backend.file_system.manager.get_fs_file_content', new_callable=AsyncMock) as get_content:
        get_content.side_effect = lambda fid, chat_id=None, workspace_id=None: contents[fid]
        result = await manager.search_fs_contents(rows, "hello", 10)
        assert get_content.await_args_list[1].kwargs == {"chat_id": None, "workspace_id": "w1"}
    assert result == {"results": [
        {"file_system_id": "a", "path": "a.md", "line_number": 1, "line": "Hello world"},
        {"file_system_id": "a", "path": "a.md", "line_number": 3, "line": "say HELLO again"},
        {"file_system_id": "b", "path": "workspace/b.py", "line_number": 1, "line": "hello"},
    ], "truncated": False}


@pytest.mark.asyncio
async def test_search_fs_contents_no_hits_and_empty_scope():
    with patch('backend.file_system.manager.get_fs_file_content', new_callable=AsyncMock, return_value="abc"):
        assert await manager.search_fs_contents([{"id": "a", "filename": "a"}], "zzz", 5) == {"results": [], "truncated": False}
    assert await manager.search_fs_contents([], "x", 5) == {"results": [], "truncated": False}


@pytest.mark.asyncio
async def test_search_fs_contents_limit_sets_truncated_only_when_more_hits_exist():
    rows = [{"id": "a", "filename": "a"}]
    with patch('backend.file_system.manager.get_fs_file_content', new_callable=AsyncMock, return_value="x\nx\nx"):
        cut = await manager.search_fs_contents(rows, "x", 2)
        exact = await manager.search_fs_contents(rows, "x", 3)
    assert [r["line_number"] for r in cut["results"]] == [1, 2] and cut["truncated"] is True
    assert len(exact["results"]) == 3 and exact["truncated"] is False


@pytest.mark.asyncio
async def test_search_fs_contents_cuts_long_lines_and_skips_unreadable_and_binary_files():
    rows = [{"id": "none", "filename": "n"},
            {"id": "bin", "filename": "b"}, {"id": "long", "filename": "l"}]
    contents = {"none": None, "bin": manager._BINARY_PLACEHOLDER, "long": "x" * 1000}
    with patch('backend.file_system.manager.get_fs_file_content', new_callable=AsyncMock) as get_content, \
         patch('backend.file_system.manager.config.FILE_SEARCH_MAX_LINE_CHARS', 300):
        get_content.side_effect = lambda fid, chat_id=None, workspace_id=None: contents[fid]
        result = await manager.search_fs_contents(rows, "x", 10)
    assert [r["file_system_id"] for r in result["results"]] == ["long"]
    assert len(result["results"][0]["line"]) == 300


@pytest.mark.asyncio
async def test_search_fs_contents_numbers_lines_by_newline_only_and_shows_a_match_beyond_the_cut():
    content = "a\x0cneedle on the same line\r\n" + "x" * 400 + "needle tail"
    with patch('backend.file_system.manager.get_fs_file_content', new_callable=AsyncMock, return_value=content), \
         patch('backend.file_system.manager.config.FILE_SEARCH_MAX_LINE_CHARS', 300):
        result = await manager.search_fs_contents([{"id": "a", "filename": "a"}], "needle", 10)
    first, second = result["results"]
    assert first["line_number"] == 1 and first["line"] == "a\x0cneedle on the same line"  # form feed is not a line break, CR trimmed
    assert second["line_number"] == 2 and second["line"].startswith("needle tail")


@pytest.mark.asyncio
async def test_search_fs_contents_does_not_skip_a_text_file_that_starts_with_the_binary_marker():
    with patch('backend.file_system.manager.get_fs_file_content', new_callable=AsyncMock, return_value="[Binary File] notes: needle"):
        result = await manager.search_fs_contents([{"id": "a", "filename": "a"}], "needle", 10)
    assert len(result["results"]) == 1
