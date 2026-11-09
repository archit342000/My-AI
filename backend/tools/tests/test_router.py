import pytest
import json
from flask import Flask
from unittest.mock import MagicMock, patch
from backend.tools.router import tools_bp

@pytest.fixture
def app(login_as, user_a):
    app = Flask(__name__)
    app.register_blueprint(tools_bp, url_prefix='/tools')
    login_as(app, user_a)
    return app

@pytest.fixture(autouse=True)
def owned_by_user_a(owner_db):
    """Ownership checks read owners from the db: by default every chat belongs to user_a (the logged-in user)."""
    return owner_db

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def mock_db():
    with patch('backend.database.db') as mock:
        yield mock

@pytest.fixture
def mock_registry():
    with patch('backend.tools.router.callback_registry') as mock:
        mock._callbacks = {}
        yield mock

def test_get_active_callbacks(client, mock_registry, mock_db):
    mock_registry._callbacks = {
        "cb1": {"chat_id": "chat1", "response": None}
    }
    mock_db.get_pending_callbacks.return_value = [{"callback_id": "cb2"}]
    mock_db.get_messages.return_value = []
    
    resp = client.get('/tools/active/chat1')
    assert resp.status_code == 200
    data = resp.json
    assert "cb1" in data["active_callback_ids"]
    assert "cb2" in data["active_callback_ids"]

def test_clarification_response_success(client, mock_registry):
    mock_registry.get.return_value = {"chat_id": "chat1"}
    
    resp = client.post('/tools/clarification/response', json={
        "callback_id": "cb1",
        "content": "My Answer"
    })
    
    assert resp.status_code == 200
    assert resp.json["success"] is True
    mock_registry.resolve.assert_called_once()

def test_clarification_response_db_fallback(client, mock_registry, mock_db):
    mock_registry.get.return_value = None # Not in memory
    mock_db.get_callback_chat_id.return_value = "chat1"
    
    resp = client.post('/tools/clarification/response', json={
        "callback_id": "cb_db",
        "content": "DB Answer"
    })
    
    assert resp.status_code == 200
    mock_db.resolve_callback.assert_called_once()

def test_get_preferences(client, mock_db):
    mock_db.get_all_preferences.return_value = [{"id": "p1", "content": "X", "tag": "pref"}]
    
    resp = client.get('/tools/preferences')
    assert resp.status_code == 200
    assert resp.json["preferences"][0]["id"] == "p1"

def test_add_preference(client, mock_db):
    mock_db.add_preference.return_value = "new_id"
    
    resp = client.post('/tools/preferences', json={"content": "new", "tag": "pref"})
    assert resp.status_code == 200
    assert resp.json["id"] == "new_id"

def test_update_agent_config(client):
    with patch('backend.chat.agent_handler.AGENT_PROFILES', {}) as mock_profiles:
        resp = client.patch('/tools/config/agents/search_web', json={
            "thinking_profile": "precision",
            "max_tokens": 1000,
            "thinking_budget": 500
        })
        assert resp.status_code == 200
        assert mock_profiles["search_web"] == "precision"

def test_get_agents_config(client):
    with patch('backend.chat.agent_handler.AGENT_PROFILES', {"search_web": "precision"}):
        resp = client.get('/tools/config/agents')
        assert resp.status_code == 200
        assert resp.json["search_web"]["thinking_profile"] == "precision"

def test_get_browser_config(client):
    with patch('backend.config.BROWSER_STEALTH_LEVEL', 'minimal'):
        resp = client.get('/tools/config/browser')
        assert resp.status_code == 200
        assert resp.json["stealth_level"] == "minimal"

def test_update_browser_config(client):
    with patch('backend.config.BROWSER_STEALTH_LEVEL', 'minimal'):
        resp = client.patch('/tools/config/browser', json={"stealth_level": "advanced"})
        assert resp.status_code == 200
        from backend import config
        assert config.BROWSER_STEALTH_LEVEL == "advanced"

def test_update_browser_config_invalid(client):
    resp = client.patch('/tools/config/browser', json={"stealth_level": "invalid"})
    assert resp.status_code == 400

def test_preference_routes_use_the_callers_id(app, login_as, user_b, mock_db):
    login_as(app, user_b)
    client = app.test_client()
    mock_db.get_all_preferences.return_value = []
    mock_db.add_preference.return_value = "p1"
    mock_db.update_preference.return_value = False  # user_a's preference: not found for user_b
    mock_db.delete_preference.return_value = False
    mock_db.clear_preferences.return_value = 0
    client.get('/tools/preferences')
    mock_db.get_all_preferences.assert_called_once_with(user_b["id"])
    client.post('/tools/preferences', json={"content": "c", "tag": "t"})
    mock_db.add_preference.assert_called_once_with("c", "t", user_b["id"])
    assert client.put('/tools/preferences/pa', json={"content": "x", "tag": "t"}).status_code == 404
    mock_db.update_preference.assert_called_once_with("pa", "x", "t", user_b["id"])
    assert client.delete('/tools/preferences/pa').status_code == 404
    mock_db.delete_preference.assert_called_once_with("pa", user_b["id"])
    client.post('/tools/preferences/reset')
    mock_db.clear_preferences.assert_called_once_with(user_b["id"])


def test_update_preference(client, mock_db):
    mock_db.update_preference.return_value = True
    resp = client.put('/tools/preferences/p1', json={"content": "updated", "tag": "tag1"})
    assert resp.status_code == 200
    assert resp.json["success"] is True

def test_update_preference_unknown_id_is_a_404(client, mock_db):
    mock_db.update_preference.return_value = False
    resp = client.put('/tools/preferences/p1', json={"content": "updated", "tag": "tag1"})
    assert resp.status_code == 404
    assert resp.json == {"error": "Preference not found"}

def test_delete_preference(client, mock_db):
    mock_db.delete_preference.return_value = True
    resp = client.delete('/tools/preferences/p1')
    assert resp.status_code == 200
    assert resp.json["success"] is True

@patch('backend.tools.router.log_event')
def test_delete_preference_not_found(mock_log_event, client, mock_db):
    mock_db.delete_preference.return_value = False
    resp = client.delete('/tools/preferences/missing')
    assert resp.status_code == 404
    assert resp.json == {"error": "Preference not found"}
    mock_log_event.assert_called_once_with("tools_preference_delete_not_found", {"preference_id": "missing"})

def test_reset_preferences(client, mock_db):
    mock_db.clear_preferences.return_value = 5
    resp = client.post('/tools/preferences/reset')
    assert resp.status_code == 200
    assert resp.json["deleted"] == 5

def test_proxy_portal_vnc(client):
    with patch('backend.mcp_client.portal_vnc_auth_header', return_value={"Authorization": "Basic cG9ydGFsOms="}), patch('httpx.Client.get') as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200, 
            content=b"vnc data", 
            headers={"content-type": "text/html"}
        )
        resp = client.get('/tools/portal/vnc/test.html')
        assert resp.status_code == 200
        assert resp.data == b"vnc data"
        assert resp.headers["content-type"] == "text/html"
        assert mock_get.call_args.kwargs["headers"] == {"Authorization": "Basic cG9ydGFsOms="}

def test_proxy_portal_vnc_error(client):
    with patch('backend.mcp_client.portal_vnc_auth_header', return_value={"Authorization": "Basic cG9ydGFsOms="}), \
         patch('httpx.Client.get', side_effect=Exception("error")):
        resp = client.get('/tools/portal/vnc/test.html')
        assert resp.status_code == 502

def test_proxy_portal_vnc_without_a_key_is_a_503_and_calls_nothing(client):
    with patch('backend.mcp_client.portal_vnc_auth_header', return_value={}), patch('httpx.Client.get') as mock_get:
        resp = client.get('/tools/portal/vnc/test.html')
    assert resp.status_code == 503
    assert resp.json == {"error": "Browser portal is not configured"}
    mock_get.assert_not_called()

def test_proxy_portal_vnc_upstream_401_is_a_502(client):
    with patch('backend.mcp_client.portal_vnc_auth_header', return_value={"Authorization": "Basic cG9ydGFsOms="}), patch('httpx.Client.get') as mock_get:
        mock_get.return_value = MagicMock(status_code=401, content=b"", headers={})
        resp = client.get('/tools/portal/vnc/test.html')
    assert resp.status_code == 502
    assert resp.json == {"error": "Could not reach browser portal service"}

def test_proxy_portal_init(client):
    with patch('backend.config.get_secret', return_value="k"), patch('httpx.Client.post') as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200, 
            json=lambda: {"url": "http://portal"}
        )
        resp = client.post('/tools/portal/init')
        assert resp.status_code == 200
        assert resp.json["url"] == "http://portal"
        assert mock_post.call_args.kwargs["headers"] == {"X-MCP-API-KEY": "k"}

def test_proxy_portal_init_error(client):
    with patch('backend.config.get_secret', return_value="k"), patch('httpx.Client.post', side_effect=Exception("error")):
        resp = client.post('/tools/portal/init')
        assert resp.status_code == 500

def test_proxy_portal_init_without_a_key_is_a_503_and_calls_nothing(client):
    with patch('backend.config.get_secret', return_value=""), patch('httpx.Client.post') as mock_post:
        resp = client.post('/tools/portal/init')
    assert resp.status_code == 503
    assert resp.json == {"error": "Browser portal is not configured"}
    mock_post.assert_not_called()

def test_proxy_portal_init_upstream_401_is_a_502_without_the_key(client):
    with patch('backend.config.get_secret', return_value="super-secret"), patch('httpx.Client.post') as mock_post:
        mock_post.return_value = MagicMock(status_code=401, text="Unauthorized")
        resp = client.post('/tools/portal/init')
    assert resp.status_code == 502
    assert resp.json == {"error": "Browser portal authentication failed"}
    assert "super-secret" not in resp.get_data(as_text=True)

def test_clarification_response_missing_id(client):
    resp = client.post('/tools/clarification/response', json={"content": "no id"})
    assert resp.status_code == 400

def test_clarification_response_not_found(client, mock_registry, mock_db):
    mock_registry.get.return_value = None
    mock_db.resolve_callback.side_effect = Exception("Not found")
    mock_db.get_callback_chat_id.return_value = "chat1"
    resp = client.post('/tools/clarification/response', json={"callback_id": "unknown"})
    assert resp.status_code == 404


def test_clarification_response_for_an_unknown_callback_is_404_and_resolves_nothing(client, mock_registry, mock_db):
    mock_registry.get.return_value = None
    mock_db.get_callback_chat_id.return_value = None
    resp = client.post('/tools/clarification/response', json={"callback_id": "ghost"})
    assert resp.status_code == 404
    mock_db.resolve_callback.assert_not_called()


def test_clarification_response_when_the_callback_lookup_fails_is_404(client, mock_registry, mock_db):
    mock_registry.get.return_value = None
    mock_db.get_callback_chat_id.side_effect = RuntimeError("database is locked")
    resp = client.post('/tools/clarification/response', json={"callback_id": "cb1"})
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "Unknown or expired callback_id"}
    mock_db.resolve_callback.assert_not_called()


def test_user_b_cannot_see_or_resolve_user_as_callbacks(app, login_as, user_b, mock_registry, mock_db, owned_by_user_a, user_a):
    owned_by_user_a.get_chat_owner.return_value = user_a["id"]
    login_as(app, user_b)
    client = app.test_client()
    mock_registry._callbacks = {"cb1": {"chat_id": "chat1", "response": None}}
    mock_db.get_pending_callbacks.return_value = [{"callback_id": "cb2"}]

    assert client.get('/tools/active/chat1').status_code == 404
    mock_db.get_pending_callbacks.assert_not_called()

    mock_registry.get.return_value = {"chat_id": "chat1"}  # in-memory path
    foreign = client.post('/tools/clarification/response', json={"callback_id": "cb1", "content": "x"})
    assert foreign.status_code == 404
    mock_registry.get.return_value = None
    mock_db.get_callback_chat_id.return_value = None
    unknown = client.post('/tools/clarification/response', json={"callback_id": "ghost", "content": "x"})
    assert foreign.get_json() == unknown.get_json()  # a foreign callback id is indistinguishable from an unknown one
    mock_registry.resolve.assert_not_called()

    mock_registry.get.return_value = None  # DB path
    mock_db.get_callback_chat_id.return_value = "chat1"
    assert client.post('/tools/clarification/response', json={"callback_id": "cb2", "content": "x"}).status_code == 404
    mock_db.resolve_callback.assert_not_called()


def test_run_file_defaults_sql_target_to_sqlite(client):
    """Direct run-file without sql_target runs SQL on sqlite, never mysql."""
    from unittest.mock import AsyncMock
    with patch('backend.tools.implementations.code_executor.resolve_run_target', return_value=("/p/q.sql", "/p")), \
         patch('backend.tools.implementations.code_executor.run_file', new_callable=AsyncMock) as run:
        run.return_value = {"stdout": "", "stderr": "", "exit_code": 0}
        resp = client.post('/tools/code-execution/run-file', json={"path": "q.sql", "chat_id": "c1"})
        assert resp.status_code == 200
        assert run.call_args.kwargs["sql_target"] == "sqlite"


# Routes that need a JSON body: a missing, malformed or non-object body is a 400 JSON error, not a 500 or an HTML page.
REQUIRED_BODY_ROUTES = [
    ("post", "/tools/clarification/response"),
    ("post", "/tools/preferences"),
    ("put", "/tools/preferences/p1"),
    ("patch", "/tools/config/agents/search"),
    ("patch", "/tools/config/browser"),
    ("post", "/tools/config/settings"),
]
BAD_BODIES = [
    {},                                                           # no body at all
    {"data": "null", "content_type": "application/json"},
    {"data": "[1]", "content_type": "application/json"},
    {"data": "{bad", "content_type": "application/json"},
    {"data": '{"a": 1}', "content_type": "text/plain"},
]


@pytest.mark.parametrize("method,url", REQUIRED_BODY_ROUTES)
@pytest.mark.parametrize("body", BAD_BODIES)
def test_required_body_routes_return_a_400_json_error(client, mock_db, method, url, body):
    resp = getattr(client, method)(url, **body)
    assert resp.status_code == 400
    assert resp.json == {"error": "Request body must be a JSON object"}


@pytest.mark.parametrize("body", [{"data": "[1]", "content_type": "application/json"},
                                  {"data": "{bad", "content_type": "application/json"}])
def test_optional_body_route_still_rejects_an_invalid_body(client, mock_db, body):
    resp = client.post("/tools/code-execution/run-file", **body)
    assert resp.status_code == 400 and resp.json == {"error": "Request body must be a JSON object"}


@pytest.mark.parametrize("body", [{}, {"data": "null", "content_type": "application/json"}])
def test_optional_body_route_accepts_no_body_and_reaches_its_own_validation(client, mock_db, body):
    resp = client.post("/tools/code-execution/run-file", **body)
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "Missing path or chat_id"}   # the route's own error, as JSON


# ---- error bodies never carry exception or upstream text; the detail goes to the log -------------------------

def test_get_preferences_failure_is_generic_and_logged(client, mock_db):
    mock_db.get_all_preferences.side_effect = RuntimeError("db path /secret/chats.db locked")
    with patch('backend.tools.router.log_event') as log:
        resp = client.get('/tools/preferences')
    assert resp.status_code == 500
    assert resp.json == {"error": "Failed to load preferences"}
    assert "/secret" not in resp.get_data(as_text=True)
    log.assert_any_call("tools_preferences_get_error", {"error": "db path /secret/chats.db locked"})


def test_reset_preferences_failure_is_generic_and_logged(client, mock_db):
    mock_db.clear_preferences.side_effect = RuntimeError("disk I/O error on /secret")
    with patch('backend.tools.router.log_event') as log:
        resp = client.post('/tools/preferences/reset')
    assert resp.status_code == 500
    assert resp.json == {"error": "Failed to reset preferences"}
    assert "/secret" not in resp.get_data(as_text=True)
    log.assert_any_call("tools_preferences_reset_error", {"error": "disk I/O error on /secret"})


def test_portal_init_upstream_failure_is_a_generic_502_and_logged(client):
    with patch('backend.config.get_secret', return_value="k"), patch('httpx.Client.post') as post, \
         patch('backend.tools.router.log_event') as log:
        post.return_value = MagicMock(status_code=500, text="Traceback ... /app/playwright_mcp/server.py")
        resp = client.post('/tools/portal/init')
    assert resp.status_code == 502
    assert resp.json == {"error": "Browser portal failed to start"}
    assert "Traceback" not in resp.get_data(as_text=True)
    log.assert_any_call("tools_portal_init_error", {"status_code": 500, "error": "Traceback ... /app/playwright_mcp/server.py"})


def test_portal_init_unreachable_service_is_a_502(client):
    import httpx
    with patch('backend.config.get_secret', return_value="k"), \
         patch('httpx.Client.post', side_effect=httpx.ConnectError("[Errno 111] playwright_mcp:8001")), \
         patch('backend.tools.router.log_event') as log:
        resp = client.post('/tools/portal/init')
    assert resp.status_code == 502
    assert resp.json == {"error": "Could not reach browser portal service"}
    assert "playwright_mcp" not in resp.get_data(as_text=True)
    log.assert_any_call("tools_portal_init_error", {"error": "[Errno 111] playwright_mcp:8001"})


def test_portal_init_upstream_body_is_capped_in_the_log_event(client):
    with patch('backend.config.get_secret', return_value="k"), patch('httpx.Client.post') as post, \
         patch('backend.tools.router.log_event') as log:
        post.return_value = MagicMock(status_code=500, text="x" * 2000)
        resp = client.post('/tools/portal/init')
    assert resp.status_code == 502
    log.assert_any_call("tools_portal_init_error", {"status_code": 500, "error": "x" * 500})


def test_portal_init_unexpected_error_is_a_generic_500(client):
    with patch('backend.config.get_secret', return_value="k"), patch('httpx.Client.post', side_effect=ValueError("secret detail")), \
         patch('backend.tools.router.log_event') as log:
        resp = client.post('/tools/portal/init')
    assert resp.status_code == 500
    assert resp.json == {"error": "Failed to start browser portal"}
    log.assert_any_call("tools_portal_init_error", {"error": "secret detail"})


# ---- run-file: a missing file is a 404 ----------------------------------------------------------------------

def _run_file_request(client):
    return client.post('/tools/code-execution/run-file', json={"path": "nope.py", "chat_id": "c1"})


def test_run_file_missing_file_is_a_404_and_does_not_run(client):
    from unittest.mock import AsyncMock
    with patch('backend.tools.implementations.code_executor.resolve_run_target', side_effect=FileNotFoundError("File 'nope.py' does not exist.")), \
         patch('backend.tools.implementations.code_executor.run_file', new_callable=AsyncMock) as run:
        resp = _run_file_request(client)
    assert resp.status_code == 404
    assert resp.json == {"error": "File not found"}
    run.assert_not_called()


def test_run_file_invalid_path_is_a_400(client):
    from unittest.mock import AsyncMock
    with patch('backend.tools.implementations.code_executor.resolve_run_target', side_effect=ValueError("reserved path")), \
         patch('backend.tools.implementations.code_executor.run_file', new_callable=AsyncMock) as run:
        resp = _run_file_request(client)
    assert resp.status_code == 400
    assert resp.json == {"error": "Invalid file path"}
    run.assert_not_called()


def test_run_file_resolver_failure_is_a_generic_500_and_logged(client):
    from unittest.mock import AsyncMock
    with patch('backend.tools.implementations.code_executor.resolve_run_target', side_effect=RuntimeError("db down at /secret")), \
         patch('backend.tools.implementations.code_executor.run_file', new_callable=AsyncMock) as run, \
         patch('backend.tools.router.log_event') as log:
        resp = _run_file_request(client)
    assert resp.status_code == 500
    assert resp.json == {"error": "Failed to run file"}
    assert "/secret" not in resp.get_data(as_text=True)
    log.assert_any_call("tools_run_file_error", {"chat_id": "c1", "path": "nope.py", "error": "db down at /secret"})
    run.assert_not_called()


def test_run_file_execution_failure_is_a_generic_500_and_logged(client):
    from unittest.mock import AsyncMock
    with patch('backend.tools.implementations.code_executor.resolve_run_target', return_value=("/p/a.py", "/p")), \
         patch('backend.tools.implementations.code_executor.run_file', new_callable=AsyncMock, side_effect=RuntimeError("runner at 10.0.0.5 failed")), \
         patch('backend.tools.router.log_event') as log:
        resp = _run_file_request(client)
    assert resp.status_code == 500
    assert resp.json == {"error": "Failed to run file"}
    assert "10.0.0.5" not in resp.get_data(as_text=True)
    log.assert_any_call("tools_run_file_error", {"chat_id": "c1", "path": "nope.py", "error": "runner at 10.0.0.5 failed"})


def test_run_file_missing_file_is_a_404_through_the_real_resolver(client, tmp_path):
    from unittest.mock import AsyncMock
    (tmp_path / "exists.py").write_text("print(1)")
    with patch('backend.tools.implementations.code_executor.resolve_owner_and_physical_path') as resolve, \
         patch('backend.tools.implementations.code_executor.run_file', new_callable=AsyncMock) as run:
        resolve.side_effect = lambda chat_id, path, **kw: (chat_id, None, str(tmp_path / path) if path else str(tmp_path))
        run.return_value = "ok"
        missing = client.post('/tools/code-execution/run-file', json={"path": "nope.py", "chat_id": "c1"})
        present = client.post('/tools/code-execution/run-file', json={"path": "exists.py", "chat_id": "c1"})
    assert missing.status_code == 404 and missing.json == {"error": "File not found"}
    assert present.status_code == 200 and present.json == {"result": "ok"}
    assert run.call_count == 1


# ---- code_runner_timeout validation and the exposed maximum ---------------------------------------------------

def test_settings_post_rejects_an_out_of_range_or_non_integer_timeout_and_writes_nothing(client, mock_db):
    with patch('backend.config.CODE_RUNNER_MAX_TIMEOUT', 120):
        for bad in (500, 121, 0, -1, True, False, "x", "4.5", 1.5, None, [30]):
            resp = client.post('/tools/config/settings', json={"code_runner_timeout": bad, "other": 1})
            assert resp.status_code == 400, bad
            assert resp.json == {"error": "code_runner_timeout must be an integer from 1 to 120"}
    mock_db.set_setting.assert_not_called()


def test_settings_post_accepts_a_valid_timeout_with_other_keys(client, mock_db):
    with patch('backend.config.CODE_RUNNER_MAX_TIMEOUT', 120):
        for ok in (1, 60, 120, "45"):
            mock_db.set_setting.reset_mock()
            resp = client.post('/tools/config/settings', json={"code_runner_timeout": ok, "other": 1})
            assert resp.status_code == 200, ok
            assert mock_db.set_setting.call_count == 2


def test_settings_post_stores_the_timeout_as_an_integer(client, mock_db):
    with patch('backend.config.CODE_RUNNER_MAX_TIMEOUT', 120):
        client.post('/tools/config/settings', json={"code_runner_timeout": "045"})
    mock_db.set_setting.assert_called_once_with("code_runner_timeout", 45)


def test_settings_post_rejects_an_absurdly_long_digit_string_with_400_not_500(client, mock_db):
    with patch('backend.config.CODE_RUNNER_MAX_TIMEOUT', 120):
        resp = client.post('/tools/config/settings', json={"code_runner_timeout": "9" * 5000})
    assert resp.status_code == 400
    mock_db.set_setting.assert_not_called()


def test_settings_post_never_stores_the_read_only_maximum(client, mock_db):
    resp = client.post('/tools/config/settings', json={"code_runner_max_timeout": 9999, "other": 1})
    assert resp.status_code == 200
    stored = [c.args[0] for c in mock_db.set_setting.call_args_list]
    assert stored == ["other"]


def test_settings_get_exposes_the_maximum(client, mock_db):
    mock_db.get_all_settings.return_value = {}
    with patch('backend.config.CODE_RUNNER_MAX_TIMEOUT', 120):
        resp = client.get('/tools/config/settings')
    assert resp.status_code == 200
    assert resp.json["code_runner_max_timeout"] == 120


# --- code execution: the chat owner is checked -------------------------------------------------

def test_execution_history_and_run_file_refuse_another_users_chat(app, login_as, user_a, user_b, owned_by_user_a, mock_db):
    from unittest.mock import AsyncMock
    owned_by_user_a.get_chat_owner.return_value = user_a["id"]
    login_as(app, user_b)
    client = app.test_client()
    with patch('backend.tools.implementations.code_executor.resolve_run_target') as resolve, \
         patch('backend.tools.implementations.code_executor.run_file', new_callable=AsyncMock) as run:
        history = client.get('/tools/code-execution/history/chat-of-a')
        run_resp = client.post('/tools/code-execution/run-file', json={"path": "main.py", "chat_id": "chat-of-a"})
    assert history.status_code == 404 and run_resp.status_code == 404
    mock_db.get_code_execution_history.assert_not_called()  # nothing about the foreign chat is read
    resolve.assert_not_called()
    run.assert_not_called()  # and nothing is executed


def test_execution_history_for_the_owner_still_works(client, mock_db):
    mock_db.get_code_execution_history.return_value = [{"id": 1}]
    assert client.get('/tools/code-execution/history/chat1').get_json() == [{"id": 1}]
    mock_db.get_code_execution_history.assert_called_once_with("chat1", limit=50, offset=0)

