import pytest
import json
from flask import Flask
from unittest.mock import MagicMock, patch
from backend.tools.router import tools_bp

@pytest.fixture
def app():
    app = Flask(__name__)
    app.register_blueprint(tools_bp, url_prefix='/tools')
    return app

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
    with patch('httpx.Client.get') as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200, 
            content=b"vnc data", 
            headers={"content-type": "text/html"}
        )
        resp = client.get('/tools/portal/vnc/test.html')
        assert resp.status_code == 200
        assert resp.data == b"vnc data"
        assert resp.headers["content-type"] == "text/html"

def test_proxy_portal_vnc_error(client):
    with patch('httpx.Client.get', side_effect=Exception("error")):
        resp = client.get('/tools/portal/vnc/test.html')
        assert resp.status_code == 502

def test_proxy_portal_init(client):
    with patch('httpx.Client.post') as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200, 
            json=lambda: {"url": "http://portal"}
        )
        resp = client.post('/tools/portal/init')
        assert resp.status_code == 200
        assert resp.json["url"] == "http://portal"

def test_proxy_portal_init_error(client):
    with patch('httpx.Client.post', side_effect=Exception("error")):
        resp = client.post('/tools/portal/init')
        assert resp.status_code == 500

def test_clarification_response_missing_id(client):
    resp = client.post('/tools/clarification/response', json={"content": "no id"})
    assert resp.status_code == 400

def test_clarification_response_not_found(client, mock_registry, mock_db):
    mock_registry.get.return_value = None
    mock_db.resolve_callback.side_effect = Exception("Not found")
    resp = client.post('/tools/clarification/response', json={"callback_id": "unknown"})
    assert resp.status_code == 404


def test_run_file_defaults_sql_target_to_sqlite(client):
    """Direct run-file without sql_target runs SQL on sqlite, never mysql."""
    from unittest.mock import AsyncMock
    with patch('backend.tools.implementations.code_executor.run_file', new_callable=AsyncMock) as run:
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
