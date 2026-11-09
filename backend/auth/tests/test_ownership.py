from unittest.mock import patch

import pytest
from flask import Flask

from backend.auth import ownership
from backend.auth.context import user_context


@pytest.fixture
def db():
    with patch("backend.auth.ownership.db") as mock, patch("backend.auth.ownership.log_event") as events:
        mock.events = events
        yield mock


def test_require_chat_owner_allows_the_owner(db, user_a):
    db.get_chat_owner.return_value = user_a["id"]
    with Flask(__name__).app_context(), user_context(user_a):
        assert ownership.require_chat_owner("c1") is None
    db.events.assert_not_called()


def test_require_chat_owner_refuses_a_foreign_chat_with_404_and_logs(db, user_a, user_b):
    db.get_chat_owner.return_value = user_a["id"]
    with Flask(__name__).app_context(), user_context(user_b):
        response, status = ownership.require_chat_owner("c1")
        assert status == 404 and response.get_json() == {"error": "Chat not found"}
    db.events.assert_called_once_with("access_denied", {"kind": "chat", "id": "c1"})


def test_require_chat_owner_missing_chat_is_404_without_a_log(db, user_a):
    db.get_chat_owner.return_value = None
    with Flask(__name__).app_context(), user_context(user_a):
        assert ownership.require_chat_owner("nope")[1] == 404
    db.events.assert_not_called()


@pytest.mark.parametrize("fn,arg", [(ownership.require_chat_owner, "c1"),
                                    (ownership.require_workspace_owner, "w1"),
                                    (ownership.claim_chat, "c1")])
def test_no_current_user_fails_closed(db, fn, arg):
    db.get_chat_owner.return_value = "someone"
    db.get_workspace_owner.return_value = "someone"
    with Flask(__name__).app_context():
        assert fn(arg)[1] == 404
    db.ensure_chat_exists.assert_not_called()


def test_admin_gets_no_bypass(db, user_a):
    admin = {"id": "admin-1", "email": "x@test.io", "role": "admin"}
    db.get_chat_owner.return_value = user_a["id"]
    db.get_workspace_owner.return_value = user_a["id"]
    with Flask(__name__).app_context(), user_context(admin):
        assert ownership.require_chat_owner("c1")[1] == 404
        assert ownership.require_workspace_owner("w1")[1] == 404


def test_require_workspace_owner(db, user_a, user_b):
    db.get_workspace_owner.return_value = user_a["id"]
    with Flask(__name__).app_context():
        with user_context(user_a):
            assert ownership.require_workspace_owner("w1") is None
        with user_context(user_b):
            response, status = ownership.require_workspace_owner("w1")
            assert status == 404 and response.get_json() == {"error": "Workspace not found"}
    db.events.assert_called_once_with("access_denied", {"kind": "workspace", "id": "w1"})
    db.get_workspace_owner.return_value = None
    with Flask(__name__).app_context(), user_context(user_a):
        assert ownership.require_workspace_owner("nope")[1] == 404


def test_claim_chat_creates_for_the_caller_and_refuses_a_foreign_chat(db, user_a, user_b):
    db.ensure_chat_exists.side_effect = lambda chat_id, user_id: user_id if chat_id == "new" else user_a["id"]
    with Flask(__name__).app_context():
        with user_context(user_b):
            assert ownership.claim_chat("new") is None
            db.ensure_chat_exists.assert_called_with("new", user_b["id"])
            assert ownership.claim_chat("owned-by-a")[1] == 404
        with user_context(user_a):
            assert ownership.claim_chat("owned-by-a") is None
    db.events.assert_called_once_with("access_denied", {"kind": "chat", "id": "owned-by-a"})


def test_reject_foreign_chat_only_refuses_an_existing_foreign_chat_and_never_writes(db, user_a, user_b):
    with Flask(__name__).app_context():
        with user_context(user_b):
            db.get_chat_owner.return_value = user_a["id"]
            assert ownership.reject_foreign_chat("c1")[1] == 404
            db.get_chat_owner.return_value = None  # missing: let the route validate and claim it
            assert ownership.reject_foreign_chat("new") is None
            db.get_chat_owner.return_value = user_b["id"]
            assert ownership.reject_foreign_chat("mine") is None
        assert ownership.reject_foreign_chat("c1")[1] == 404  # no current user: fail closed
    db.ensure_chat_exists.assert_not_called()
    db.events.assert_called_once_with("access_denied", {"kind": "chat", "id": "c1"})
