import os
import shutil
import sqlite3
import tempfile
from unittest.mock import patch

import pytest

from backend.database.db_wrapper import DatabaseWrapper
from backend.database.init_db import init_db


@pytest.fixture
def db():
    tmp_dir = tempfile.mkdtemp()
    db_path = os.path.join(tmp_dir, "test_users.db")
    with patch("backend.database.db_layer.DB_PATH", db_path), \
         patch("backend.database.init_db.DB_PATH", db_path), \
         patch("backend.database.db_wrapper.DB_PATH", db_path), \
         patch("backend.config.ADMIN_EMAIL", ""):
        init_db()
        yield DatabaseWrapper()
    shutil.rmtree(tmp_dir)


def test_create_and_get_user(db):
    user = db.create_user("  Alice@Example.com ", "user")
    assert user["email"] == "alice@example.com"
    assert user["role"] == "user"
    assert user["is_active"] is True
    assert db.get_user(user["id"]) == user
    assert db.get_user("missing") is None


def test_lookup_is_case_insensitive(db):
    user = db.create_user("bob@example.com")
    assert db.get_user_by_email("BOB@Example.COM")["id"] == user["id"]
    assert db.get_user_by_email("nobody@example.com") is None


def test_duplicate_email_raises(db):
    db.create_user("dup@example.com")
    with pytest.raises(sqlite3.IntegrityError):
        db.create_user("DUP@example.com")


def test_invalid_role_raises(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.create_user("r@example.com", "root")


def test_set_user_active(db):
    db.create_user("c@example.com")
    assert db.set_user_active("C@example.com", False) is True
    assert db.get_user_by_email("c@example.com")["is_active"] is False
    assert db.set_user_active("c@example.com", True) is True
    assert db.get_user_by_email("c@example.com")["is_active"] is True
    assert db.set_user_active("missing@example.com", False) is False


def test_list_users_and_get_admin(db):
    assert db.list_users() == []
    assert db.get_admin_user() is None
    db.create_user("u@example.com", "user")
    admin = db.create_user("a@example.com", "admin")
    assert [u["email"] for u in db.list_users()] == ["u@example.com", "a@example.com"]
    assert db.get_admin_user()["id"] == admin["id"]
    db.set_user_active("a@example.com", False)
    assert db.get_admin_user() is None
