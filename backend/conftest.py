"""Shared fixtures for backend tests: two users, a way to log a test app in as one of them, and the ownership db mock."""
from unittest.mock import patch

import pytest
from flask import g

from backend.auth.context import reset_current_user, set_current_user


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    """Rate-limit counters are process-wide state; every test starts with empty windows."""
    from backend.auth import rate_limit
    rate_limit.reset_limiters()
    yield


@pytest.fixture
def user_a():
    """A regular user."""
    return {"id": "user-a", "email": "a@test.io", "role": "user"}


@pytest.fixture
def user_b():
    """A second regular user, for cross-user access tests."""
    return {"id": "user-b", "email": "b@test.io", "role": "user"}


@pytest.fixture
def admin_a(user_a):
    """`user_a` as an admin (same id, so ownership mocks that name user_a still match)."""
    return {**user_a, "role": "admin"}


@pytest.fixture
def two_users(user_a, user_b):
    """`(user_a, user_b)`."""
    return user_a, user_b


@pytest.fixture
def login_as():
    """
    Return `login_as(app, user)`, which makes every request to the test `app` run as `user`.

    It mirrors the app's `authenticate_request` hook: `g.user` and the current-user ContextVar are set before the
    view runs and reset after the request. Each call sets the user for the requests that follow, so a test can switch
    users. It does not mirror `bind_user_to_stream`: a streamed body does not run as the user in these tests.
    """
    def _login(app, user):
        state = app.config.setdefault("_TEST_LOGIN_STATE", {})
        state["user"] = user
        if app.config.get("_TEST_LOGIN_HOOKED"):
            return state

        @app.before_request
        def _set_user():
            current = app.config["_TEST_LOGIN_STATE"]["user"]
            g.user = current
            g._test_token = set_current_user(current)

        @app.teardown_request
        def _reset_user(exc=None):
            token = g.pop("_test_token", None)
            if token is not None:
                reset_current_user(token)

        app.config["_TEST_LOGIN_HOOKED"] = True
        return state
    return _login


@pytest.fixture
def owner_db(user_a):
    """
    The db behind `backend.auth.ownership`, mocked so every chat and workspace belongs to `user_a`.

    Tests change `get_chat_owner`, `get_workspace_owner` or `ensure_chat_exists` return values to model other owners.
    `log_event` is patched too, so refused requests write no log files.
    """
    with patch("backend.auth.ownership.db") as mock, patch("backend.auth.ownership.log_event"):
        mock.get_chat_owner.return_value = user_a["id"]
        mock.get_workspace_owner.return_value = user_a["id"]
        mock.ensure_chat_exists.return_value = user_a["id"]
        yield mock
