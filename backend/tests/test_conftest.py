"""The shared two-user fixtures in backend/conftest.py."""
from flask import Flask, g

from backend.auth.context import current_user, current_user_id


def test_two_users_are_distinct_regular_users(two_users, user_a, user_b):
    assert two_users == (user_a, user_b)
    assert user_a["id"] != user_b["id"] and user_a["role"] == user_b["role"] == "user"


def test_login_as_sets_g_user_and_the_context_and_resets_it(login_as, user_a, user_b):
    app = Flask(__name__)
    seen = []

    @app.route("/who")
    def who():
        seen.append((g.user["id"], current_user_id()))
        return "ok"

    state = login_as(app, user_a)
    client = app.test_client()
    client.get("/who")
    assert seen == [(user_a["id"], user_a["id"])]
    assert current_user() is None
    login_as(app, user_b)  # switching users on the same app
    client.get("/who")
    assert seen[-1] == (user_b["id"], user_b["id"])
    assert state["user"] == user_b
