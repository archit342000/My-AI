"""
Tests for backend.database.wrapper.chat_ops (ChatOpsMixin).

Coverage:
- ensure_chat_exists / get_chat
- save_chat / update_chat / update_* helpers
- rename_chat, update_chat_model, update_chat_vision_model, update_chat_max_tokens
- mark_research_completed, update_chat_file_system_mode, update_research_state
- delete_chat  ← FK-safety regression: file_systems + all child tables
- delete_all_chats ← FK-safety regression: same ordering requirement
- get_chat_full
- get_listed_chats (sidebar list: chats with a message, file or chat artifact) vs get_all_chats (every chat)
- workspace CRUD (create / rename / delete)
- update_chat_workspace
"""

import os
import sqlite3
import pytest
import tempfile
import shutil
import time
from unittest.mock import patch

from backend.database.init_db import init_db
from backend.database.db_wrapper import DatabaseWrapper


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _db_path_patches(db_path):
    """Return the three patches required to redirect DB_PATH."""
    return (
        patch("backend.database.db_layer.DB_PATH", db_path),
        patch("backend.database.init_db.DB_PATH", db_path),
        patch("backend.database.db_wrapper.DB_PATH", db_path),
    )


def _raw_conn(db_path: str) -> sqlite3.Connection:
    """Open a raw SQLite connection to the temp DB with FK enforcement."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _seed_file_attachment(db_path: str, chat_id: str, file_id: str = "f_001"):
    """
    Insert a row into the `files` table referencing *chat_id*.
    This simulates a chat that has a file attachment.
    """
    conn = _raw_conn(db_path)
    try:
        conn.execute(
            """
            INSERT INTO files (id, chat_id, original_filename, stored_filename,
                               mime_type, file_size, processing_status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (file_id, chat_id, "doc.pdf", "stored_doc.pdf", "application/pdf", 1024, "ready"),
        )
        conn.commit()
    finally:
        conn.close()


def _seed_file_system_with_children(
    db_path: str,
    chat_id: str,
    fs_id: str = "fs_001",
):
    """
    Insert rows into file_systems, file_system_versions, and
    file_system_permissions — the three-table FK chain that caused the
    original IntegrityError bug.
    """
    conn = _raw_conn(db_path)
    try:
        conn.execute(
            """
            INSERT INTO file_systems
                (id, chat_id, workspace_id, title, filename, timestamp, file_system_type, current_version)
            VALUES (?, ?, NULL, ?, ?, ?, 'custom', 1)
            """,
            (fs_id, chat_id, "Test FS", "test.md", time.time()),
        )
        conn.execute(
            """
            INSERT INTO file_system_versions
                (file_system_id, chat_id, workspace_id, version_number, content, author, timestamp)
            VALUES (?, ?, NULL, 1, 'hello', 'user', ?)
            """,
            (fs_id, chat_id, time.time()),
        )
        conn.execute(
            """
            INSERT INTO file_system_permissions
                (file_system_id, chat_id, workspace_id, user_id, permission, timestamp)
            VALUES (?, ?, NULL, 'user1', 'write', ?)
            """,
            (fs_id, chat_id, time.time()),
        )
        conn.commit()
    finally:
        conn.close()


def _count(db_path: str, table: str, where: str, params: tuple) -> int:
    conn = _raw_conn(db_path)
    try:
        cur = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}", params)
        return cur.fetchone()[0]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def temp_db():
    """
    Per-test isolated SQLite DB.  Using function scope ensures each test
    starts from a clean slate — important for FK-safety tests that verify
    complete row removal.
    """
    tmp_dir = tempfile.mkdtemp()
    db_path = os.path.join(tmp_dir, "test_chats.db")
    p1, p2, p3 = _db_path_patches(db_path)
    with p1, p2, p3:
        from backend.database.cache_layer import cache_layer
        with cache_layer._global_lock:
            cache_layer._tables.clear()
        init_db()
        wrapper = DatabaseWrapper()
        # Expose the raw path so helper functions can use it
        wrapper._test_db_path = db_path
        yield wrapper
    shutil.rmtree(tmp_dir)


# ---------------------------------------------------------------------------
# Basic CRUD
# ---------------------------------------------------------------------------

class TestEnsureAndGetChat:
    def test_ensure_chat_creates_record(self, temp_db):
        temp_db.ensure_chat_exists("chat_ensure_1", "u1")
        chat = temp_db.get_chat("chat_ensure_1")
        assert chat is not None
        assert chat["id"] == "chat_ensure_1"

    def test_ensure_chat_is_idempotent(self, temp_db):
        temp_db.ensure_chat_exists("chat_idem", "u1")
        temp_db.ensure_chat_exists("chat_idem", "u1")  # second call must not raise
        assert temp_db.get_chat("chat_idem") is not None

    def test_get_chat_returns_none_for_missing(self, temp_db):
        assert temp_db.get_chat("nonexistent_xyz") is None


class TestGetListedChats:
    """The sidebar list hides chats that hold no content; get_all_chats keeps returning every chat."""

    def _ids(self, rows):
        return [r["id"] for r in rows]

    def test_empty_chat_is_not_listed_but_still_exists(self, temp_db):
        temp_db.ensure_chat_exists("listed_empty", "u1")
        assert "listed_empty" not in self._ids(temp_db.get_listed_chats("u1"))
        assert "listed_empty" in self._ids(temp_db.get_all_chats("u1"))  # internal callers still see it
        assert temp_db.get_chat("listed_empty") is not None

    def test_chat_with_a_message_a_file_or_an_artifact_is_listed(self, temp_db):
        db_path = temp_db._test_db_path
        for chat in ("listed_msg", "listed_file", "listed_art"):
            temp_db.ensure_chat_exists(chat, "u1")
        temp_db.add_message("listed_msg", role="user", content="hi")
        _seed_file_attachment(db_path, "listed_file")
        _seed_file_system_with_children(db_path, "listed_art")
        ids = self._ids(temp_db.get_listed_chats("u1"))
        assert {"listed_msg", "listed_file", "listed_art"} <= set(ids)

    def test_workspace_name_is_populated(self, temp_db):
        ws = temp_db.create_workspace("Listed WS", "u1")
        ws_id = ws["id"]
        temp_db.ensure_chat_exists("listed_ws_chat", "u1")
        temp_db.update_chat_workspace("listed_ws_chat", ws_id)
        temp_db.add_message("listed_ws_chat", role="user", content="hi")
        row = next(r for r in temp_db.get_listed_chats("u1") if r["id"] == "listed_ws_chat")
        assert row["workspace_name"] == "Listed WS"

    def test_chat_leaves_the_list_when_its_last_content_is_removed_and_returns_with_new_content(self, temp_db):
        db_path = temp_db._test_db_path
        temp_db.ensure_chat_exists("listed_toggle", "u1")
        msg_id = temp_db.add_message("listed_toggle", role="user", content="hi")
        assert "listed_toggle" in self._ids(temp_db.get_listed_chats("u1"))
        temp_db.delete_message("listed_toggle", msg_id)
        assert "listed_toggle" not in self._ids(temp_db.get_listed_chats("u1"))
        temp_db.add_message("listed_toggle", role="user", content="again")
        assert "listed_toggle" in self._ids(temp_db.get_listed_chats("u1"))

        temp_db.ensure_chat_exists("listed_file_toggle", "u1")
        _seed_file_attachment(db_path, "listed_file_toggle", file_id="f_toggle")
        assert "listed_file_toggle" in self._ids(temp_db.get_listed_chats("u1"))
        temp_db.delete_file("f_toggle")
        assert "listed_file_toggle" not in self._ids(temp_db.get_listed_chats("u1"))

    def test_ordering_is_newest_first(self, temp_db):
        db_path = temp_db._test_db_path
        for chat, ts in (("listed_old", 100.0), ("listed_new", 300.0), ("listed_mid", 200.0)):
            temp_db.save_chat(chat, chat, ts, enable_thinking=1, user_id="u1")
            _seed_file_attachment(db_path, chat, file_id=f"f_{chat}")  # a file does not bump the timestamp
        ids = [i for i in self._ids(temp_db.get_listed_chats("u1")) if i.startswith("listed_")]
        assert ids == ["listed_new", "listed_mid", "listed_old"]


class TestSaveChat:
    def test_save_chat_creates_and_reads_back(self, temp_db):
        temp_db.save_chat(
            "chat_save_1", "My Chat", time.time(),
            enable_thinking=1, last_model="llama3", vision_model="llava", user_id="u1")
        chat = temp_db.get_chat("chat_save_1")
        assert chat["title"] == "My Chat"
        assert chat["last_model"] == "llama3"
        assert chat["vision_model"] == "llava"

    def test_save_chat_upsert_updates_fields(self, temp_db):
        temp_db.save_chat("chat_upsert", "Original", time.time(), enable_thinking=1, user_id="u1")
        # Re-save with different model; title should update (not custom)
        temp_db.save_chat("chat_upsert", "Updated", time.time(), enable_thinking=1, last_model="qwen", user_id="u1")
        chat = temp_db.get_chat("chat_upsert")
        assert chat["last_model"] == "qwen"

    def test_get_all_chats_includes_saved(self, temp_db):
        temp_db.save_chat("chat_list_1", "L1", time.time(), enable_thinking=1, user_id="u1")
        temp_db.save_chat("chat_list_2", "L2", time.time(), enable_thinking=1, user_id="u1")
        all_chats = temp_db.get_all_chats("u1")
        ids = [c["id"] for c in all_chats]
        assert "chat_list_1" in ids
        assert "chat_list_2" in ids


class TestUpdateChatHelpers:
    def test_update_chat_title(self, temp_db):
        temp_db.ensure_chat_exists("chat_upd", "u1")
        temp_db.rename_chat("chat_upd", "New Title")
        assert temp_db.get_chat("chat_upd")["title"] == "New Title"

    def test_update_last_user_and_assistant_ids(self, temp_db):
        temp_db.ensure_chat_exists("chat_ids", "u1")
        temp_db.update_last_user_id("chat_ids", 42)
        temp_db.update_last_assistant_id("chat_ids", 99)
        chat = temp_db.get_chat("chat_ids")
        assert chat["last_user_id"] == 42
        assert chat["last_assistant_id"] == 99

    def test_update_chat_model(self, temp_db):
        temp_db.ensure_chat_exists("chat_model", "u1")
        temp_db.update_chat_model("chat_model", "mistral")
        assert temp_db.get_chat("chat_model")["last_model"] == "mistral"

    def test_update_chat_vision_model(self, temp_db):
        temp_db.ensure_chat_exists("chat_vision", "u1")
        temp_db.update_chat_vision_model("chat_vision", "llava-next")
        assert temp_db.get_chat("chat_vision")["vision_model"] == "llava-next"

    def test_update_chat_max_tokens(self, temp_db):
        temp_db.ensure_chat_exists("chat_maxtok", "u1")
        temp_db.update_chat_max_tokens("chat_maxtok", 4096)
        assert temp_db.get_chat("chat_maxtok")["max_tokens"] == 4096

    def test_mark_research_completed(self, temp_db):
        temp_db.ensure_chat_exists("chat_research", "u1")
        temp_db.mark_research_completed("chat_research", 1)
        assert temp_db.get_chat("chat_research")["research_completed"] == 1

    def test_update_chat_file_system_mode(self, temp_db):
        temp_db.ensure_chat_exists("chat_fsmode", "u1")
        temp_db.update_chat_file_system_mode("chat_fsmode", True)
        assert temp_db.get_chat("chat_fsmode")["file_system_mode"] == 1

    def test_update_research_state(self, temp_db):
        temp_db.ensure_chat_exists("chat_rstate", "u1")
        temp_db.update_research_state("chat_rstate", "synthesizing")
        assert temp_db.get_chat("chat_rstate")["research_state"] == "synthesizing"


class TestGetChatFull:
    def test_get_chat_full_returns_messages(self, temp_db):
        temp_db.ensure_chat_exists("chat_full", "u1")
        temp_db.add_message("chat_full", role="user", content="hi")
        full = temp_db.get_chat_full("chat_full")
        assert full["id"] == "chat_full"
        assert any(m["content"] == "hi" for m in full["messages"])

    def test_get_chat_full_returns_none_for_missing(self, temp_db):
        assert temp_db.get_chat_full("no_such_chat") is None


# ---------------------------------------------------------------------------
# delete_chat — FK-safety regression tests
# ---------------------------------------------------------------------------

class TestDeleteChat:
    """
    These tests specifically cover the FK-safety fix applied to delete_chat.

    Bug: deleting a chat that had file_system rows (with child rows in
    file_system_versions / file_system_permissions) raised:
        sqlite3.IntegrityError: FOREIGN KEY constraint failed

    Root causes:
    1. file_system_versions / file_system_permissions were not deleted before
       file_systems (or at all in the case of file_system_permissions).
    2. No explicit transaction, so partial deletes left the DB dirty.
    """

    def test_delete_plain_chat(self, temp_db):
        """Deleting a chat with no attachments must succeed."""
        temp_db.ensure_chat_exists("chat_del_plain", "u1")
        temp_db.delete_chat("chat_del_plain")
        assert temp_db.get_chat("chat_del_plain") is None

    def test_delete_chat_with_file_attachment(self, temp_db):
        """
        Regression: deleting a chat that has rows in the `files` table must
        not raise IntegrityError.
        """
        chat_id = "chat_del_file"
        db_path = temp_db._test_db_path
        temp_db.ensure_chat_exists(chat_id, "u1")
        _seed_file_attachment(db_path, chat_id, file_id="f_attach_001")

        # This must not raise sqlite3.IntegrityError
        temp_db.delete_chat(chat_id)

        assert temp_db.get_chat(chat_id) is None
        assert _count(db_path, "files", "chat_id = ?", (chat_id,)) == 0

    def test_delete_chat_with_file_system_and_children(self, temp_db):
        """
        Core regression: chat has file_systems → file_system_versions AND
        file_system_permissions.  All three tables must be cleaned up
        before the chats row is removed, or FK enforcement raises.
        """
        chat_id = "chat_del_fs"
        db_path = temp_db._test_db_path
        temp_db.ensure_chat_exists(chat_id, "u1")
        _seed_file_system_with_children(db_path, chat_id, fs_id="fs_del_001")

        # Verify seed data exists
        assert _count(db_path, "file_systems", "chat_id = ?", (chat_id,)) == 1
        assert _count(db_path, "file_system_versions", "chat_id = ?", (chat_id,)) == 1
        assert _count(db_path, "file_system_permissions", "chat_id = ?", (chat_id,)) == 1

        # Must not raise IntegrityError
        temp_db.delete_chat(chat_id)

        assert temp_db.get_chat(chat_id) is None
        assert _count(db_path, "file_systems", "chat_id = ?", (chat_id,)) == 0
        assert _count(db_path, "file_system_versions", "chat_id = ?", (chat_id,)) == 0
        assert _count(db_path, "file_system_permissions", "chat_id = ?", (chat_id,)) == 0

    def test_delete_chat_removes_messages(self, temp_db):
        chat_id = "chat_del_msgs"
        temp_db.ensure_chat_exists(chat_id, "u1")
        temp_db.add_message(chat_id, role="user", content="msg1")
        temp_db.add_message(chat_id, role="assistant", content="msg2")

        temp_db.delete_chat(chat_id)

        assert temp_db.get_chat(chat_id) is None
        assert len(temp_db.get_messages(chat_id)) == 0

    def test_delete_chat_removes_sub_agent_messages(self, temp_db):
        chat_id = "chat_del_sub"
        db_path = temp_db._test_db_path
        temp_db.ensure_chat_exists(chat_id, "u1")
        # Insert a sub_agent_messages row directly via raw SQL
        conn = _raw_conn(db_path)
        try:
            conn.execute(
                """
                INSERT INTO sub_agent_messages
                    (chat_id, parent_message_id, parent_type, agent_name,
                     sequence_order, role, content, timestamp)
                VALUES (?, ?, 'main', 'file_system_agent', 1, 'assistant', 'hi', ?)
                """,
                (chat_id, "msg_1", time.time()),
            )
            conn.commit()
        finally:
            conn.close()

        temp_db.delete_chat(chat_id)

        assert _count(db_path, "sub_agent_messages", "chat_id = ?", (chat_id,)) == 0

    def test_delete_chat_removes_pending_callbacks(self, temp_db):
        chat_id = "chat_del_cb"
        db_path = temp_db._test_db_path
        temp_db.ensure_chat_exists(chat_id, "u1")
        conn = _raw_conn(db_path)
        try:
            conn.execute(
                """
                INSERT INTO pending_callbacks
                    (callback_id, chat_id, tool_name, status, created_at)
                VALUES ('cb_001', ?, 'clarify', 'pending', ?)
                """,
                (chat_id, time.time()),
            )
            conn.commit()
        finally:
            conn.close()

        temp_db.delete_chat(chat_id)

        assert _count(db_path, "pending_callbacks", "chat_id = ?", (chat_id,)) == 0

    def test_delete_chat_removes_collections(self, temp_db):
        chat_id = "chat_del_col"
        db_path = temp_db._test_db_path
        temp_db.ensure_chat_exists(chat_id, "u1")
        conn = _raw_conn(db_path)
        try:
            conn.execute(
                """
                INSERT INTO collections
                    (chat_id, parent_message_id, parent_type, collection_type, items, timestamp)
                VALUES (?, 'msg_1', 'main', 'search_results', '[]', ?)
                """,
                (chat_id, time.time()),
            )
            conn.commit()
        finally:
            conn.close()

        temp_db.delete_chat(chat_id)

        assert _count(db_path, "collections", "chat_id = ?", (chat_id,)) == 0

    def test_delete_chat_does_not_affect_other_chats(self, temp_db):
        """Deleting one chat must leave sibling chats and their rows intact."""
        db_path = temp_db._test_db_path
        temp_db.ensure_chat_exists("chat_keep", "u1")
        temp_db.ensure_chat_exists("chat_gone", "u1")
        _seed_file_attachment(db_path, "chat_keep", file_id="f_keep")
        _seed_file_attachment(db_path, "chat_gone", file_id="f_gone")

        temp_db.delete_chat("chat_gone")

        assert temp_db.get_chat("chat_keep") is not None
        assert _count(db_path, "files", "chat_id = ?", ("chat_keep",)) == 1
        assert _count(db_path, "files", "chat_id = ?", ("chat_gone",)) == 0

    def test_delete_nonexistent_chat_is_noop(self, temp_db):
        """Deleting a chat that doesn't exist must not raise."""
        temp_db.delete_chat("ghost_chat_xyz")  # must not raise


# ---------------------------------------------------------------------------
# delete_all_chats — FK-safety regression tests
# ---------------------------------------------------------------------------

class TestDeleteAllChats:
    """
    Mirrors the delete_chat tests but for the nuclear delete path.
    The same FK-ordering and missing-table bugs were present here.
    """

    def test_delete_all_chats_clears_table(self, temp_db):
        temp_db.ensure_chat_exists("c1", "u1")
        temp_db.ensure_chat_exists("c2", "u1")
        temp_db.delete_all_chats("u1")
        assert len(temp_db.get_all_chats("u1")) == 0

    def test_delete_all_chats_with_file_attachments(self, temp_db):
        """
        Regression: file rows referencing chats must be removed before
        chats rows, otherwise FK enforcement raises IntegrityError.
        """
        db_path = temp_db._test_db_path
        temp_db.ensure_chat_exists("c_file_1", "u1")
        temp_db.ensure_chat_exists("c_file_2", "u1")
        _seed_file_attachment(db_path, "c_file_1", "fa_001")
        _seed_file_attachment(db_path, "c_file_2", "fa_002")

        # Must not raise
        temp_db.delete_all_chats("u1")

        assert len(temp_db.get_all_chats("u1")) == 0
        assert _count(db_path, "files", "1=1", ()) == 0

    def test_delete_all_chats_with_file_systems_and_children(self, temp_db):
        """
        Core regression: file_system_versions / file_system_permissions
        must be deleted before file_systems, before chats.
        """
        db_path = temp_db._test_db_path
        temp_db.ensure_chat_exists("c_fs_1", "u1")
        temp_db.ensure_chat_exists("c_fs_2", "u1")
        _seed_file_system_with_children(db_path, "c_fs_1", "fs_nuke_1")
        _seed_file_system_with_children(db_path, "c_fs_2", "fs_nuke_2")

        # Must not raise IntegrityError
        temp_db.delete_all_chats("u1")

        assert len(temp_db.get_all_chats("u1")) == 0
        assert _count(db_path, "file_systems", "1=1", ()) == 0
        assert _count(db_path, "file_system_versions", "1=1", ()) == 0
        assert _count(db_path, "file_system_permissions", "1=1", ()) == 0

    def test_delete_all_chats_removes_messages(self, temp_db):
        temp_db.ensure_chat_exists("c_msg", "u1")
        temp_db.add_message("c_msg", role="user", content="nuke me")
        temp_db.delete_all_chats("u1")
        assert len(temp_db.get_all_chats("u1")) == 0
        assert len(temp_db.get_messages("c_msg")) == 0

    def test_delete_all_chats_removes_pending_callbacks(self, temp_db):
        db_path = temp_db._test_db_path
        temp_db.ensure_chat_exists("c_cb", "u1")
        conn = _raw_conn(db_path)
        try:
            conn.execute(
                """
                INSERT INTO pending_callbacks
                    (callback_id, chat_id, tool_name, status, created_at)
                VALUES ('cb_nuke_1', 'c_cb', 'clarify', 'pending', ?)
                """,
                (time.time(),),
            )
            conn.commit()
        finally:
            conn.close()

        temp_db.delete_all_chats("u1")

        assert _count(db_path, "pending_callbacks", "1=1", ()) == 0

    def test_delete_all_chats_on_empty_db_is_noop(self, temp_db):
        """Nuclear delete on an already-empty database must not raise."""
        temp_db.delete_all_chats("u1")
        assert len(temp_db.get_all_chats("u1")) == 0


# ---------------------------------------------------------------------------
# Workspace operations
# ---------------------------------------------------------------------------

class TestWorkspaceOps:
    def test_create_and_list_workspace(self, temp_db):
        ws = temp_db.create_workspace("Alpha", "u1")
        assert ws["id"].startswith("ws_")
        workspaces = temp_db.get_all_workspaces("u1")
        assert any(w["id"] == ws["id"] for w in workspaces)

    def test_rename_workspace(self, temp_db):
        ws = temp_db.create_workspace("Beta", "u1")
        temp_db.rename_workspace(ws["id"], "Beta Renamed")
        workspaces = temp_db.get_all_workspaces("u1")
        assert any(w["name"] == "Beta Renamed" for w in workspaces)

    def test_workspace_name_exists(self, temp_db):
        ws = temp_db.create_workspace("Dup Name", "u1")
        other = temp_db.create_workspace("Other Name", "u1")
        assert temp_db.workspace_name_exists("Dup Name", "u1") is True
        assert temp_db.workspace_name_exists("  dup NAME ", "u1") is True  # case and surrounding spaces
        assert temp_db.workspace_name_exists("Unrelated Name", "u1") is False
        assert temp_db.workspace_name_exists("Dup Name", "u1", exclude_id=ws["id"]) is False  # its own name
        assert temp_db.workspace_name_exists("Dup Name", "u1", exclude_id=other["id"]) is True

    def test_update_chat_workspace(self, temp_db):
        ws = temp_db.create_workspace("Gamma", "u1")
        temp_db.ensure_chat_exists("chat_ws", "u1")
        temp_db.update_chat_workspace("chat_ws", ws["id"])
        assert temp_db.get_chat("chat_ws")["workspace_id"] == ws["id"]

    def test_delete_workspace_sets_chat_workspace_null(self, temp_db):
        """ON DELETE SET NULL: chats keep existing but workspace_id becomes NULL."""
        ws = temp_db.create_workspace("Delta", "u1")
        temp_db.ensure_chat_exists("chat_delta", "u1")
        temp_db.update_chat_workspace("chat_delta", ws["id"])
        temp_db.delete_workspace(ws["id"])
        chat = temp_db.get_chat("chat_delta")
        assert chat is not None
        assert chat["workspace_id"] is None

    def test_delete_workspace_removes_it_from_list(self, temp_db):
        ws = temp_db.create_workspace("Epsilon", "u1")
        temp_db.delete_workspace(ws["id"])
        workspaces = temp_db.get_all_workspaces("u1")
        assert not any(w["id"] == ws["id"] for w in workspaces)

    def test_create_workspace_with_icon(self, temp_db):
        ws = temp_db.create_workspace("Iconic Workspace", "u1", "🚀")
        assert ws["icon"] == "🚀"
        workspaces = temp_db.get_all_workspaces("u1")
        workspace_in_list = next(w for w in workspaces if w["id"] == ws["id"])
        assert workspace_in_list["icon"] == "🚀"

    def test_update_workspace_icon(self, temp_db):
        ws = temp_db.create_workspace("Temp Iconic", "u1", "💼")
        temp_db.update_workspace_icon(ws["id"], "🎨")
        workspaces = temp_db.get_all_workspaces("u1")
        workspace_in_list = next(w for w in workspaces if w["id"] == ws["id"])
        assert workspace_in_list["icon"] == "🎨"
        # Test clearing the icon
        temp_db.update_workspace_icon(ws["id"], None)
        workspaces2 = temp_db.get_all_workspaces("u1")
        workspace_in_list2 = next(w for w in workspaces2 if w["id"] == ws["id"])
        assert workspace_in_list2["icon"] is None

    @patch("time.time")
    def test_workspaces_ordered_by_last_used(self, mock_time, temp_db):
        # 1. Create three workspaces sequentially.
        mock_time.return_value = 100.0
        ws1 = temp_db.create_workspace("Workspace 1", "u1")
        
        mock_time.return_value = 200.0
        ws2 = temp_db.create_workspace("Workspace 2", "u1")
        
        mock_time.return_value = 300.0
        ws3 = temp_db.create_workspace("Workspace 3", "u1")
        
        # Default order without chats (sorted by creation timestamp descending): ws3, ws2, ws1.
        workspaces = temp_db.get_all_workspaces("u1")
        ids = [w["id"] for w in workspaces]
        assert ids == [ws3["id"], ws2["id"], ws1["id"]]
        
        # 2. Associate a chat with ws1, and set its timestamp to 400.0 (the most recent).
        mock_time.return_value = 400.0
        temp_db.ensure_chat_exists("chat_ws1", "u1")
        temp_db.save_chat("chat_ws1", "Chat 1", 400.0, enable_thinking=1, workspace_id=ws1["id"], user_id="u1")
        
        # Now ws1's last used timestamp (via chat_ws1) is 400.0, so order should be: ws1, ws3, ws2.
        workspaces = temp_db.get_all_workspaces("u1")
        ids = [w["id"] for w in workspaces]
        assert ids == [ws1["id"], ws3["id"], ws2["id"]]
        
        # 3. Rename ws2 at time 500.0. This will update ws2's workspace timestamp to 500.0.
        mock_time.return_value = 500.0
        temp_db.rename_workspace(ws2["id"], "Workspace 2 Renamed")
        
        # Now ws2's last used timestamp is 500.0, so order should be: ws2, ws1, ws3.
        workspaces = temp_db.get_all_workspaces("u1")
        ids = [w["id"] for w in workspaces]
        assert ids == [ws2["id"], ws1["id"], ws3["id"]]


# ---------------------------------------------------------------------------
# Persona snapshot — isolation guarantee
# ---------------------------------------------------------------------------

class TestPersonaSnapshot:
    """
    Verifies that persona_snapshot is written when a persona is assigned to a
    chat and that subsequent edits to the persona record do NOT change the
    stored snapshot (i.e. the chat's effective prompt is frozen at assignment).
    """

    def test_snapshot_written_on_update_chat(self, temp_db):
        """update_chat with persona_snapshot= persists the value."""
        temp_db.ensure_chat_exists("chat_snap_1", "u1")
        temp_db.update_chat("chat_snap_1", persona_snapshot="You are a pirate.")
        chat = temp_db.get_chat("chat_snap_1")
        assert chat["persona_snapshot"] == "You are a pirate."

    def test_snapshot_persists_independently_of_persona_record(self, temp_db):
        """
        Core isolation check: editing the live persona record must not change
        the snapshot already stored on the chat row.
        """
        # Create a persona
        persona = temp_db.create_persona("Assistant", "You are a helpful assistant.", "u1")

        # Simulate assigning the persona and snapshotting its content
        temp_db.ensure_chat_exists("chat_snap_iso", "u1")
        temp_db.update_chat(
            "chat_snap_iso",
            persona_id=persona["id"],
            persona_snapshot=persona["content"],
        )

        # Now edit the persona (e.g. the user updates it in the UI)
        temp_db.update_persona(persona["id"], "Assistant v2", "You are a snarky assistant.", "u1")

        # The live record must reflect the new content
        updated = temp_db.get_persona(persona["id"], "u1")
        assert updated["content"] == "You are a snarky assistant."

        # But the chat's snapshot must still hold the original content
        chat = temp_db.get_chat("chat_snap_iso")
        assert chat["persona_snapshot"] == "You are a helpful assistant."

    def test_snapshot_starts_null_for_new_chat(self, temp_db):
        """A freshly created chat has no snapshot yet."""
        temp_db.ensure_chat_exists("chat_snap_null", "u1")
        chat = temp_db.get_chat("chat_snap_null")
        assert chat.get("persona_snapshot") is None

    def test_snapshot_not_overwritten_on_second_assignment(self, temp_db):
        """
        If a snapshot already exists (chat has been used), assigning a new
        persona_id must not silently erase the existing snapshot.
        This mirrors the handler logic: snapshot only on first write.
        """
        p1 = temp_db.create_persona("P1", "Persona One content", "u1")
        p2 = temp_db.create_persona("P2", "Persona Two content", "u1")

        temp_db.ensure_chat_exists("chat_snap_noover", "u1")
        # First assignment — snapshot written
        temp_db.update_chat(
            "chat_snap_noover",
            persona_id=p1["id"],
            persona_snapshot=p1["content"],
        )

        # Read snapshot to confirm it is set
        chat = temp_db.get_chat("chat_snap_noover")
        assert chat["persona_snapshot"] == "Persona One content"

        # Second assignment — only update persona_id (handler skips snapshot
        # because has_snapshot is True). Simulate that by NOT passing snapshot.
        temp_db.update_chat("chat_snap_noover", persona_id=p2["id"])

        # Snapshot should still be the original
        chat = temp_db.get_chat("chat_snap_noover")
        assert chat["persona_snapshot"] == "Persona One content"
        assert chat["persona_id"] == p2["id"]



# ---------------------------------------------------------------------------
# Ownership: every list, create and delete method is scoped to a user
# ---------------------------------------------------------------------------

class TestOwnership:
    @staticmethod
    def _ids(rows):
        return {r["id"] for r in rows}

    def test_lists_return_only_the_owners_rows(self, temp_db):
        temp_db.ensure_chat_exists("a_chat", "ua")
        temp_db.ensure_chat_exists("b_chat", "ub")
        temp_db.add_message("a_chat", "user", "hi")
        temp_db.add_message("b_chat", "user", "yo")
        wa = temp_db.create_workspace("WA", "ua")
        wb = temp_db.create_workspace("WB", "ub")
        assert self._ids(temp_db.get_all_chats("ua")) == {"a_chat"}
        assert self._ids(temp_db.get_listed_chats("ub")) == {"b_chat"}
        assert self._ids(temp_db.get_all_workspaces("ua")) == {wa["id"]}
        assert self._ids(temp_db.get_all_workspaces("ub")) == {wb["id"]}
        assert set(temp_db.get_all_chat_ids()) == {"a_chat", "b_chat"}  # system cleanup sees everyone

    def test_ensure_chat_exists_returns_the_stored_owner_and_never_re_owns(self, temp_db):
        assert temp_db.ensure_chat_exists("shared_id", "ua") == "ua"
        assert temp_db.ensure_chat_exists("shared_id", "ub") == "ua"
        assert temp_db.get_chat_owner("shared_id") == "ua"

    def test_save_chat_keeps_the_owner_of_an_existing_chat(self, temp_db):
        temp_db.save_chat("c1", "T", time.time(), enable_thinking=1, user_id="ua")
        temp_db.save_chat("c1", "T2", time.time(), enable_thinking=1, user_id="ub")
        assert temp_db.get_chat_owner("c1") == "ua"

    def test_owner_lookups_read_the_db_and_return_none_for_missing_rows(self, temp_db):
        ws = temp_db.create_workspace("Mine", "ua")
        assert temp_db.get_workspace_owner(ws["id"]) == "ua"
        assert temp_db.get_workspace_owner("nope") is None
        assert temp_db.get_chat_owner("nope") is None

    def test_workspace_name_exists_is_per_user(self, temp_db):
        temp_db.create_workspace("Same Name", "ua")
        assert temp_db.workspace_name_exists("same name", "ua") is True
        assert temp_db.workspace_name_exists("same name", "ub") is False
        temp_db.create_workspace("Same Name", "ub")  # two users may use one name

    def test_an_empty_user_id_is_refused(self, temp_db):
        for call in (lambda: temp_db.get_all_chats(""), lambda: temp_db.get_listed_chats(None),
                     lambda: temp_db.get_all_workspaces(""), lambda: temp_db.create_workspace("x", ""),
                     lambda: temp_db.workspace_name_exists("x", ""), lambda: temp_db.ensure_chat_exists("x", ""),
                     lambda: temp_db.delete_all_chats("")):
            with pytest.raises(ValueError):
                call()
        with pytest.raises(ValueError):
            temp_db.save_chat("c", "t", 1.0, enable_thinking=1, user_id="")

    def test_delete_all_chats_removes_only_the_callers_data(self, temp_db):
        temp_db.ensure_chat_exists("a_chat", "ua")
        temp_db.ensure_chat_exists("b_chat", "ub")
        wa = temp_db.create_workspace("WA", "ua")
        wb = temp_db.create_workspace("WB", "ub")
        temp_db.add_message("a_chat", "user", "mine")
        temp_db.add_message("b_chat", "user", "theirs")
        for chat_id, ws_id, fs_id in (("a_chat", None, "fs_a_chat"), (None, wa["id"], "fs_a_ws"),
                                      ("b_chat", None, "fs_b_chat"), (None, wb["id"], "fs_b_ws")):
            from backend.database.db_layer import make_connection
            c = make_connection()
            c.execute("INSERT INTO file_systems (id, chat_id, workspace_id, title, filename, folder, timestamp) "
                      "VALUES (?, ?, ?, 't', ?, '', 1.0)", (fs_id, chat_id, ws_id, fs_id))
            c.execute("INSERT INTO file_system_versions (file_system_id, chat_id, workspace_id, version_number, content, author, timestamp) "
                      "VALUES (?, ?, ?, 1, 'x', 'user', 1.0)", (fs_id, chat_id, ws_id))
            c.commit()
            c.close()
        temp_db.delete_all_chats("ua")
        from backend.database.db_layer import make_connection
        c = make_connection()
        left_chats = {r[0] for r in c.execute("SELECT id FROM chats")}
        left_fs = {r[0] for r in c.execute("SELECT id FROM file_systems")}
        left_versions = {r[0] for r in c.execute("SELECT file_system_id FROM file_system_versions")}
        left_messages = {r[0] for r in c.execute("SELECT content FROM messages")}
        left_ws = {r[0] for r in c.execute("SELECT id FROM workspaces")}
        c.close()
        assert left_chats == {"b_chat"}
        assert left_fs == {"fs_b_chat", "fs_b_ws"}
        assert left_versions == {"fs_b_chat", "fs_b_ws"}
        assert left_messages == {"theirs"}
        assert left_ws == {wa["id"], wb["id"]}  # workspace rows stay; only their file systems go


    def test_ensure_chat_exists_returns_the_stored_owner_when_another_user_created_the_row_first(self, temp_db):
        """A lost create race must not tell the loser it owns the chat."""
        temp_db.ensure_chat_exists("raced", "ua")
        with patch.object(temp_db, "_get_chat_fetch_internal", return_value=None):  # the miss was read before ua's insert
            assert temp_db.ensure_chat_exists("raced", "ub") == "ua"
        assert temp_db.get_chat_owner("raced") == "ua"

    def test_save_chat_never_updates_another_users_chat(self, temp_db):
        temp_db.save_chat("c1", "Original", time.time(), enable_thinking=1, user_id="ua")
        temp_db.save_chat("c1", "Hijacked", time.time(), enable_thinking=1, last_model="evil", user_id="ub")
        chat = temp_db.get_chat("c1")
        assert chat["title"] == "Original" and chat["last_model"] is None and chat["user_id"] == "ua"
        temp_db.save_chat("c1", "Renamed by owner", time.time(), enable_thinking=1, user_id="ua")
        assert temp_db.get_chat("c1")["title"] == "Renamed by owner"


class TestTemporaryChats:
    """Unsaved temporary chats are kept out of the list and can be found once they are old."""

    def _ids(self, rows):
        return [r["id"] for r in rows]

    def test_update_chat_sets_and_clears_the_flag_and_it_defaults_to_zero(self, temp_db):
        temp_db.ensure_chat_exists("tmp_flag", "u1")
        assert not temp_db.get_chat("tmp_flag")["is_temporary"]
        temp_db.update_chat("tmp_flag", is_temporary=1)
        assert temp_db.get_chat("tmp_flag")["is_temporary"] == 1
        temp_db.update_chat("tmp_flag", is_temporary=0)
        assert temp_db.get_chat("tmp_flag")["is_temporary"] == 0

    def test_a_temporary_chat_with_content_is_not_listed_until_saved(self, temp_db):
        temp_db.ensure_chat_exists("tmp_listed", "u1")
        temp_db.add_message("tmp_listed", role="user", content="hi")
        temp_db.update_chat("tmp_listed", is_temporary=1)
        assert "tmp_listed" not in self._ids(temp_db.get_listed_chats("u1"))
        assert "tmp_listed" in self._ids(temp_db.get_all_chats("u1"))  # internal callers still see it
        temp_db.update_chat("tmp_listed", is_temporary=0)
        assert "tmp_listed" in self._ids(temp_db.get_listed_chats("u1"))

    def test_expired_query_returns_only_the_callers_old_unsaved_temporary_chats(self, temp_db):
        for chat, user, ts, temp in (("tmp_old", "u1", 100.0, 1), ("tmp_new", "u1", 900.0, 1), ("tmp_saved", "u1", 100.0, 0), ("tmp_other", "u2", 100.0, 1)):
            temp_db.save_chat(chat, chat, ts, enable_thinking=1, user_id=user)
            temp_db.update_chat(chat, is_temporary=temp, timestamp=ts)
        assert temp_db.get_expired_temporary_chats("u1", 500.0) == ["tmp_old"]
        assert temp_db.get_expired_temporary_chats("u2", 500.0) == ["tmp_other"]
        assert temp_db.get_expired_temporary_chats("u1", 50.0) == []

    def test_mark_chat_temporary_only_marks_a_chat_without_messages(self, temp_db):
        temp_db.ensure_chat_exists("tmp_mark_new", "u1")
        assert temp_db.mark_chat_temporary("tmp_mark_new") is True
        assert temp_db.get_chat("tmp_mark_new")["is_temporary"] == 1
        temp_db.ensure_chat_exists("tmp_mark_used", "u1")
        temp_db.add_message("tmp_mark_used", role="user", content="hi")
        assert temp_db.mark_chat_temporary("tmp_mark_used") is False  # a saved or already-used chat is not re-marked
        assert not temp_db.get_chat("tmp_mark_used")["is_temporary"]
        assert temp_db.mark_chat_temporary("no_such_chat") is False

    def test_workspace_order_ignores_the_activity_of_unsaved_temporary_chats(self, temp_db):
        older = temp_db.create_workspace("Order older", "u1")["id"]
        time.sleep(0.01)
        newer = temp_db.create_workspace("Order newer", "u1")["id"]
        temp_db.ensure_chat_exists("tmp_ws_chat", "u1")
        temp_db.update_chat_workspace("tmp_ws_chat", older)
        temp_db.update_chat("tmp_ws_chat", is_temporary=1, timestamp=9e9)

        def order():
            return [w["id"] for w in temp_db.get_all_workspaces("u1") if w["id"] in (older, newer)]

        assert order() == [newer, older]  # an unsaved chat does not lift its workspace
        temp_db.update_chat("tmp_ws_chat", is_temporary=0)
        assert order() == [older, newer]  # once saved it does
