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

def test_update_preference_fail(client, mock_db):
    mock_db.update_preference.return_value = False
    resp = client.put('/tools/preferences/p1', json={"content": "updated", "tag": "tag1"})
    assert resp.status_code == 500

def test_delete_preference(client, mock_db):
    mock_db.delete_preference.return_value = True
    resp = client.delete('/tools/preferences/p1')
    assert resp.status_code == 200
    assert resp.json["success"] is True

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
