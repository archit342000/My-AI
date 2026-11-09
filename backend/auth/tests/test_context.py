from flask import Flask

from backend.auth.context import (
    admin_required, current_user, current_user_id, reset_current_user, set_current_user, user_context,
)

ADMIN = {"id": "a1", "email": "a@x.io", "role": "admin"}
USER = {"id": "u1", "email": "u@x.io", "role": "user"}


def test_defaults_to_no_user():
    assert current_user() is None
    assert current_user_id() is None


def test_set_and_reset():
    token = set_current_user(USER)
    assert current_user() == USER
    assert current_user_id() == "u1"
    reset_current_user(token)
    assert current_user() is None


def test_user_context_restores_previous_user():
    with user_context(ADMIN):
        with user_context(USER):
            assert current_user_id() == "u1"
        assert current_user_id() == "a1"
    assert current_user() is None


def test_user_context_restores_on_error():
    try:
        with user_context(USER):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert current_user() is None


def _client():
    app = Flask(__name__)

    @app.route("/x")
    @admin_required
    def x():
        return {"ok": True}
    return app.test_client()


def test_admin_required_blocks_user_and_anonymous():
    client = _client()
    assert client.get("/x").status_code == 403
    with user_context(USER):
        resp = client.get("/x")
    assert resp.status_code == 403
    assert resp.get_json() == {"error": "Forbidden"}


def test_admin_required_allows_admin():
    with user_context(ADMIN):
        assert _client().get("/x").get_json() == {"ok": True}
