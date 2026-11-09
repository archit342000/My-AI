import json
import pytest
import os
from unittest.mock import patch, MagicMock
import jwt
from werkzeug.exceptions import RequestEntityTooLarge
from backend.auth.providers import StaticProvider, CloudflareAccessProvider
from backend.auth.context import current_user

# Mock heavy initialization before importing app
with patch('backend.database.init_db.init_db'), \
     patch('backend.config.validate_auth_config'), \
     patch('backend.models.get_embedding_model'), \
     patch('backend.rag.RAGProvider.get_manager') as mock_get_manager, \
     patch('backend.task_manager.task_manager.recover_tasks'), \
     patch('backend.file_system.FileSystemChannelManager.initialize'), \
     patch('backend.inference.InferenceEngine.start'), \
     patch('flask_sock.Sock.route', return_value=lambda f: f):

    rag_manager_mock = MagicMock()
    rag_manager_mock._ensure_l2_collections.return_value = (MagicMock(), MagicMock())
    mock_get_manager.return_value = rag_manager_mock

    import app as flask_app
    from backend import config

@pytest.fixture(autouse=True)
def _caller_owns_the_chat():
    """The code-execution WebSocket checks the chat owner; by default the caller owns every chat (owner id "owner-1")."""
    with patch('app.owns_chat', return_value=True) as owns, patch('app.db.get_chat_owner', return_value="owner-1"):
        yield owns


ADMIN_ROW = {"id": "admin-1", "email": "admin@test", "role": "admin", "is_active": True, "created_at": 0.0}


@pytest.fixture(autouse=True)
def _authenticated_admin():
    """Every request is the active admin unless a test replaces the provider or the user lookup."""
    with patch('app.get_provider', return_value=StaticProvider("admin@test")), \
         patch('app.db.get_user_by_email', return_value=ADMIN_ROW):
        yield

@pytest.fixture
def app():
    flask_app.app.config.update({
        "TESTING": True,
    })
    yield flask_app.app

@pytest.fixture
def client(app):
    return app.test_client()

def test_index_route(client):
    """Test the root index route serves index.html in legacy mode."""
    with patch.object(config, 'FRONTEND', 'legacy'), patch('app.send_from_directory') as mock_send:
        mock_send.return_value = "index html content"
        response = client.get('/')
        assert response.status_code == 200
        assert response.data == b"index html content"
        mock_send.assert_called_with('static', 'index.html')

def test_chat_route(client):
    """Test the chat route serves index.html in legacy mode."""
    with patch.object(config, 'FRONTEND', 'legacy'), patch('app.send_from_directory') as mock_send:
        mock_send.return_value = "index html content"
        response = client.get('/chat/123')
        assert response.status_code == 200
        assert response.data == b"index html content"
        mock_send.assert_called_with('static', 'index.html')

def test_serve_static_route(client):
    """Test serving static files (legacy mode; React mode has its own fallback, see below)."""
    with patch.object(config, 'FRONTEND', 'legacy'), patch('app.send_from_directory') as mock_send:
        mock_send.return_value = "static file content"
        response = client.get('/some_static_file.js')
        assert response.status_code == 200
        assert response.data == b"static file content"
        mock_send.assert_called_with('static', 'some_static_file.js')

class _StubJWKS:
    def get_signing_key_from_jwt(self, token):
        raise jwt.PyJWKClientError("unknown kid")


def _cloudflare_provider():
    return CloudflareAccessProvider("team.cloudflareaccess.com", "aud", jwks_client=_StubJWKS())


@pytest.mark.parametrize("path", [
    '/api/me',
    '/',
    '/some_static_file.js',
    '/api/tools/code-execution/ws',
])
def test_authenticate_request_rejects_missing_identity(client, path):
    """No Access JWT gives 401 on API, SPA shell, static and WebSocket-upgrade paths."""
    with patch('app.get_provider', return_value=_cloudflare_provider()):
        response = client.get(path, headers={'Connection': 'Upgrade', 'Upgrade': 'websocket'})
    assert response.status_code == 401
    assert response.get_json() == {"error": "Unauthorized"}


def test_authenticate_request_rejects_invalid_token(client):
    with patch('app.get_provider', return_value=_cloudflare_provider()), patch('backend.auth.providers.log_event'):
        response = client.get('/api/me', headers={'Cf-Access-Jwt-Assertion': 'garbage'})
    assert response.status_code == 401


@pytest.mark.parametrize("row", [None, {**ADMIN_ROW, "is_active": False}])
def test_authenticate_request_rejects_unknown_or_inactive_user(client, row):
    with patch('app.db.get_user_by_email', return_value=row), patch('app.log_event') as mock_log:
        response = client.get('/api/me')
    assert response.status_code == 403
    assert response.get_json() == {"error": "Forbidden"}
    reason = "unknown" if row is None else "inactive"
    mock_log.assert_called_once_with("auth_unknown_user", {"email": "admin@test", "reason": reason})


def test_api_me_returns_id_email_role(client):
    response = client.get('/api/me')
    assert response.status_code == 200
    assert response.get_json() == {"id": "admin-1", "email": "admin@test", "role": "admin"}


def test_current_user_is_set_in_the_request_and_reset_after(client):
    seen = {}
    real_jsonify = flask_app.jsonify

    def spy(*args, **kwargs):
        seen["user"] = current_user()
        return real_jsonify(*args, **kwargs)

    assert current_user() is None
    with patch('app.jsonify', side_effect=spy):
        assert client.get('/api/me').status_code == 200
    assert seen["user"] == {"id": "admin-1", "email": "admin@test", "role": "admin"}
    assert current_user() is None


def test_streamed_response_runs_as_the_request_user(app):
    """log_event inside a streamed body (read after teardown_request) still records the user."""
    from flask import Response
    seen = []

    def body():
        seen.append(current_user())
        yield "a"
        seen.append(current_user())
        yield "b"

    user = {"id": "u1", "email": "u@x.io", "role": "user"}
    with app.test_request_context('/'):
        from flask import g
        g.user = user
        response = flask_app.bind_user_to_stream(Response(body()))
    assert current_user() is None
    assert list(response.response) == ["a", "b"]
    assert seen == [user, user]
    assert current_user() is None


def test_bind_user_to_stream_leaves_other_responses_alone(app):
    from flask import Response
    with app.test_request_context('/'):
        from flask import g
        g.user = {"id": "u1", "email": "u@x.io", "role": "user"}
        plain = Response("text")
        assert flask_app.bind_user_to_stream(plain).response == [b"text"]
    with app.test_request_context('/'):
        anonymous = Response(iter(["x"]))
        original = anonymous.response
        assert flask_app.bind_user_to_stream(anonymous).response is original


def test_bind_user_to_stream_closes_the_source_generator(app):
    from flask import Response, g
    closed = []

    def body():
        try:
            yield "a"
            yield "b"
        finally:
            closed.append(True)

    with app.test_request_context('/'):
        g.user = {"id": "u1", "email": "u@x.io", "role": "user"}
        response = flask_app.bind_user_to_stream(Response(body()))
    assert next(iter(response.response)) == "a"
    response.close()
    assert closed == [True]


def test_authenticate_request_allows_known_user_to_static_route(client):
    # Pin the legacy UI: under FRONTEND=react the root serves frontend/dist, which may not be built.
    with patch.object(config, 'FRONTEND', 'legacy'), patch('app.send_from_directory') as mock_send:
        mock_send.return_value = "authorized content"
        response = client.get('/')
        assert response.status_code == 200
        assert response.data == b"authorized content"

def test_handle_large_file_error(client):
    """Test the 413 error handler."""
    # Temporarily set MAX_CONTENT_LENGTH to small value to trigger it easily
    old_max = flask_app.app.config['MAX_CONTENT_LENGTH']
    flask_app.app.config['MAX_CONTENT_LENGTH'] = 10
    
    # Send a request larger than 10 bytes
    response = client.post('/api/files/upload', data={'file': b'this is a very large string indeed'})
    assert response.status_code == 413
    assert b"File too large" in response.data
    
    flask_app.app.config['MAX_CONTENT_LENGTH'] = old_max

def test_get_version_endpoint(client):
    """Test the version endpoint."""
    with patch('app.get_version', return_value="v1.2.3"):
        with patch('app.VERSION_MAJOR', 1), patch('app.VERSION_MINOR', 2), patch('app.VERSION_PATCH', 3):
            response = client.get('/api/version')
            assert response.status_code == 200
            data = response.get_json()
            assert data['version'] == "v1.2.3"
            assert data['major'] == 1
            assert data['minor'] == 2
            assert data['patch'] == 3

@patch('app.portal_vnc_auth_header', return_value={"Authorization": "Basic cG9ydGFsOms="})
@patch('app.logger.error')
@patch('app.ws_client.create_connection')
def test_portal_ws_proxy(mock_create_connection, mock_logger_error, mock_auth):
    """Test the WebSocket proxy function directly."""
    mock_upstream = MagicMock()
    mock_create_connection.return_value = mock_upstream

    import time
    def delayed_recv(*args, **kwargs):
        time.sleep(0.1)
        return (1, None) # None data breaks the loop
    mock_upstream.recv_data.side_effect = delayed_recv

    mock_ws = MagicMock()
    # Simulate receiving some data then closing
    mock_ws.receive.side_effect = [b"test_data", "string_data", None]

    # Run the proxy function
    flask_app.portal_ws_proxy(mock_ws)

    # Check if upstream was called correctly
    mock_create_connection.assert_called_with(
        "ws://playwright_mcp:6080/websockify", header=["Authorization: Basic cG9ydGFsOms="])
    mock_upstream.send_binary.assert_called_with(b"test_data")
    mock_upstream.send.assert_called_with("string_data")
    mock_upstream.close.assert_called_once()

@patch('app.portal_vnc_auth_header', return_value={"Authorization": "Basic cG9ydGFsOms="})
@patch('app.logger.error')
@patch('app.ws_client.create_connection')
def test_portal_ws_proxy_connection_failure(mock_create_connection, mock_logger_error, mock_auth):
    """Test that connection failures in the WebSocket proxy are caught and logged."""
    mock_create_connection.side_effect = Exception("Connection refused")
    
    mock_ws = MagicMock()
    flask_app.portal_ws_proxy(mock_ws)
    
    # Check that error was logged
    mock_logger_error.assert_called_once()
    assert "Portal WS proxy error: Connection refused" in mock_logger_error.call_args[0][0]

@patch('app.portal_vnc_auth_header', return_value={})
@patch('app.logger.warning')
@patch('app.ws_client.create_connection')
def test_portal_ws_proxy_without_a_key_does_not_connect(mock_create_connection, mock_logger_warning, mock_auth):
    flask_app.portal_ws_proxy(MagicMock())
    mock_create_connection.assert_not_called()
    mock_logger_warning.assert_called_once()


@patch('app.logger.error')
@patch('app.ws_client.create_connection')
@patch('backend.tools.implementations.code_executor.collect_project_files')
@patch('backend.database.db.get_setting')
def test_code_execution_ws_proxy(mock_get_setting, mock_collect_project_files, mock_create_connection, mock_logger_error):
    """Test the code execution WebSocket proxy behaves correctly under mock environments."""
    mock_get_setting.return_value = 30
    mock_collect_project_files.return_value = ("python", [{"path": "main.py", "content": "print(1)"}], "main.py")
    
    mock_upstream = MagicMock()
    mock_create_connection.return_value = mock_upstream
    
    # Simulate receiving some data then closing
    import json
    mock_ws = MagicMock()
    mock_ws.receive.side_effect = [
        json.dumps({"type": "init", "filePath": "main.py", "chat_id": "chat123"}),
        None
    ]
    
    # Run the proxy function
    with patch.object(config, "CODE_RUNNER_API_KEY", "testkey"):
        flask_app.code_execution_ws_proxy(mock_ws)

    # The key travels in a header, never in the URL
    url = mock_create_connection.call_args.args[0]
    assert url.endswith("/ws/execute") and "api_key" not in url and "testkey" not in url
    assert mock_create_connection.call_args.kwargs["header"] == ["X-API-KEY: testkey"]

    # Check if correct helper functions are called and upstream receives setup configuration
    mock_collect_project_files.assert_called_once_with("chat123", "main.py")
    mock_create_connection.assert_called_once()
    mock_upstream.send.assert_called_once()
    
    sent_payload = json.loads(mock_upstream.send.call_args[0][0])
    assert sent_payload["language"] == "python"
    assert sent_payload["entry_file"] == "main.py"


@patch('app.ws_client.create_connection')
@patch('backend.tools.implementations.code_executor.collect_project_files')
@patch('backend.database.db.get_setting')
def test_code_execution_ws_proxy_sends_an_empty_header_not_the_word_none_without_a_key(mock_get_setting, mock_collect_project_files, mock_create_connection):
    import json
    mock_get_setting.return_value = 30
    mock_collect_project_files.return_value = ("python", [{"path": "main.py", "content": "print(1)"}], "main.py")
    mock_create_connection.return_value = MagicMock()
    mock_ws = MagicMock()
    mock_ws.receive.side_effect = [json.dumps({"type": "init", "filePath": "main.py", "chat_id": "chat123"}), None]
    with patch.object(config, "CODE_RUNNER_API_KEY", None):
        flask_app.code_execution_ws_proxy(mock_ws)
    assert mock_create_connection.call_args.kwargs["header"] == ["X-API-KEY: "]


@patch('app.ws_client.create_connection')
@patch('backend.tools.implementations.code_executor.collect_project_files')
@patch('backend.database.db.get_setting')
def test_code_execution_ws_proxy_defaults_sql_target_to_sqlite(mock_get_setting, mock_collect_project_files, mock_create_connection):
    """An init message without sql_target forwards sqlite to the runner, never mysql."""
    import json
    mock_get_setting.return_value = 30
    mock_collect_project_files.return_value = ("sql", [{"path": "q.sql", "content": "SELECT 1;"}], "q.sql")
    mock_upstream = MagicMock()
    mock_create_connection.return_value = mock_upstream
    mock_ws = MagicMock()
    mock_ws.receive.side_effect = [
        json.dumps({"type": "init", "filePath": "q.sql", "chat_id": "chat123"}),
        None
    ]

    flask_app.code_execution_ws_proxy(mock_ws)

    sent_payload = json.loads(mock_upstream.send.call_args[0][0])
    assert sent_payload["sql_target"] == "sqlite"


@patch('app.ws_client.create_connection')
@patch('backend.tools.implementations.code_executor.collect_project_files')
@patch('backend.database.db.get_setting')
def test_code_execution_ws_proxy_sends_the_clamped_timeout(mock_get_setting, mock_collect_project_files, mock_create_connection):
    import json
    mock_get_setting.return_value = 9999
    mock_collect_project_files.return_value = ("python", [{"path": "main.py", "content": "print(1)"}], "main.py")
    mock_upstream = MagicMock()
    mock_create_connection.return_value = mock_upstream
    mock_ws = MagicMock()
    mock_ws.receive.side_effect = [json.dumps({"type": "init", "filePath": "main.py", "chat_id": "chat123"}), None]
    with patch('backend.tools.implementations.code_executor.config.CODE_RUNNER_MAX_TIMEOUT', 120):
        flask_app.code_execution_ws_proxy(mock_ws)
    assert json.loads(mock_upstream.send.call_args[0][0])["timeout"] == 120


@patch('app.ws_client.create_connection')
@patch('backend.tools.implementations.code_executor.collect_project_files')
@patch('backend.database.db.get_setting')
@patch('backend.tools.implementations.code_executor.log_event')
def test_code_execution_ws_proxy_reports_an_invalid_timeout_setting_and_does_not_connect(mock_log, mock_get_setting, mock_collect_project_files, mock_create_connection):
    import json
    mock_get_setting.return_value = "abc"
    mock_collect_project_files.return_value = ("python", [{"path": "main.py", "content": "print(1)"}], "main.py")
    mock_ws = MagicMock()
    mock_ws.receive.side_effect = [json.dumps({"type": "init", "filePath": "main.py", "chat_id": "chat123"}), None]
    flask_app.code_execution_ws_proxy(mock_ws)
    frames = [json.loads(c.args[0]) for c in mock_ws.send.call_args_list]
    assert frames[0]["type"] == "stderr" and "timeout setting is invalid" in frames[0]["data"]
    assert frames[-1] == {"type": "exit", "code": 1}
    mock_create_connection.assert_not_called()


# ---- live-run WebSocket: fixed messages for unexpected errors, our own messages unchanged ----------------------

def _run_ws_proxy(init=None):
    mock_ws = MagicMock()
    mock_ws.receive.side_effect = [json.dumps(init or {"type": "init", "filePath": "main.py", "chat_id": "chat123"}), None]
    flask_app.code_execution_ws_proxy(mock_ws)
    return [json.loads(c.args[0]) for c in mock_ws.send.call_args_list]


@pytest.mark.parametrize("error", [
    FileNotFoundError("File 'x.py' does not exist."),
    ValueError("File extension '.xyz' is not supported for execution."),
])
@patch('app.log_event')
@patch('backend.tools.implementations.code_executor.collect_project_files')
def test_code_execution_ws_proxy_keeps_its_own_user_facing_messages(mock_collect, mock_log, error):
    mock_collect.side_effect = error
    frames = _run_ws_proxy()
    assert frames == [{"type": "stderr", "data": f"Error: {error}\n"}, {"type": "exit", "code": 1}]
    mock_log.assert_not_called()


@patch('app.log_event')
@patch('backend.tools.implementations.code_executor.collect_project_files')
def test_code_execution_ws_proxy_hides_an_unexpected_prepare_error_and_logs_it(mock_collect, mock_log):
    mock_collect.side_effect = RuntimeError("db path /secret/x locked")
    frames = _run_ws_proxy()
    assert frames == [{"type": "stderr", "data": "Error: Could not prepare the file for execution.\n"}, {"type": "exit", "code": 1}]
    assert "/secret" not in json.dumps(frames)
    mock_log.assert_called_once_with("code_execution_ws_prepare_error", {"chat_id": "chat123", "file_path": "main.py", "error": "RuntimeError"})


@patch('app.log_event')
@patch('app.logger.error')
@patch('app.ws_client.create_connection')
@patch('backend.tools.implementations.code_executor.collect_project_files')
@patch('backend.database.db.get_setting', return_value=30)
def test_code_execution_ws_proxy_hides_a_connection_error_and_never_logs_the_key(mock_setting, mock_collect, mock_create, mock_logger_error, mock_log):
    mock_collect.return_value = ("python", [{"path": "main.py", "content": "print(1)"}], "main.py")
    mock_create.side_effect = ConnectionRefusedError("ws://code_runner_mcp:8100/ws/execute?api_key=SECRETKEY")
    frames = _run_ws_proxy()
    assert frames == [{"type": "stderr", "data": "Error: Code runner is unavailable.\n"}]
    assert "SECRETKEY" not in json.dumps(frames) and "code_runner_mcp" not in json.dumps(frames)
    mock_log.assert_called_once_with("code_execution_ws_proxy_error", {"chat_id": "chat123", "stage": "connect", "error": "ConnectionRefusedError"})
    assert "SECRETKEY" not in str(mock_logger_error.call_args)


@patch('app.log_event')
@patch('app.logger.error')
@patch('app.ws_client.create_connection')
@patch('backend.tools.implementations.code_executor.collect_project_files')
@patch('backend.database.db.get_setting', side_effect=RuntimeError("settings table at /secret is locked"))
def test_code_execution_ws_proxy_does_not_blame_the_runner_for_other_failures(mock_setting, mock_collect, mock_create, mock_logger_error, mock_log):
    mock_collect.return_value = ("python", [{"path": "main.py", "content": "print(1)"}], "main.py")
    frames = _run_ws_proxy()
    assert frames == [{"type": "stderr", "data": "Error: Code execution failed.\n"}]
    assert "/secret" not in json.dumps(frames)
    mock_create.assert_not_called()
    mock_log.assert_called_once_with("code_execution_ws_proxy_error", {"chat_id": "chat123", "stage": "proxy", "error": "RuntimeError"})



# --- Frontend mode switch (FRONTEND=legacy|react) ---------------------------

def test_react_mode_serves_built_index(client, tmp_path):
    """In react mode, SPA routes serve frontend/dist/index.html."""
    (tmp_path / "index.html").write_text("<div id=root></div>", encoding="utf-8")
    with patch.object(config, 'FRONTEND', 'react'), patch('app.FRONTEND_DIST', str(tmp_path)):
        for path in ('/', '/chat/abc', '/workspace/ws1', '/logs'):
            response = client.get(path)
            assert response.status_code == 200, path
            assert b'<div id=root>' in response.data, path


def test_react_mode_without_build_returns_503(client, tmp_path):
    """A missing build gives an actionable 503, not a bare 404."""
    with patch.object(config, 'FRONTEND', 'react'), patch('app.FRONTEND_DIST', str(tmp_path)):
        response = client.get('/')
        assert response.status_code == 503
        assert b'npm run build' in response.data


def test_react_mode_serves_assets(client, tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log(1)", encoding="utf-8")
    with patch.object(config, 'FRONTEND', 'react'), patch('app.FRONTEND_DIST', str(tmp_path)):
        assert client.get('/assets/app.js').status_code == 200
        assert client.get('/assets/missing.js').status_code == 404


def test_react_mode_unknown_page_returns_the_index(client, tmp_path):
    """Unknown non-API GET paths are client-side routes (F7): they get the React index."""
    (tmp_path / "index.html").write_text("<div id=root>stub</div>", encoding="utf-8")
    with patch.object(config, 'FRONTEND', 'react'), patch('app.FRONTEND_DIST', str(tmp_path)):
        response = client.get('/no/such/page')
        assert response.status_code == 200
        assert b'<div id=root>stub</div>' in response.data


def test_react_mode_unknown_api_path_is_404_not_html(client, tmp_path):
    (tmp_path / "index.html").write_text("<div id=root>stub</div>", encoding="utf-8")
    with patch.object(config, 'FRONTEND', 'react'), patch('app.FRONTEND_DIST', str(tmp_path)):
        response = client.get('/api/no-such')
        assert response.status_code == 404
        assert b'<div id=root>' not in response.data


def test_react_mode_does_not_serve_files_outside_the_roots(client, tmp_path):
    (tmp_path / "index.html").write_text("<div id=root>stub</div>", encoding="utf-8")
    secret = tmp_path.parent / "outside-secret.txt"
    secret.write_text("TOP-SECRET", encoding="utf-8")
    link = tmp_path / "escape.txt"
    link.symlink_to(secret)
    try:
        with patch.object(config, 'FRONTEND', 'react'), patch('app.FRONTEND_DIST', str(tmp_path)):
            # Paths that resolve outside the roots are not files there; they have an extension, so 404.
            traversal = client.get('/..%2foutside-secret.txt')
            assert traversal.status_code == 404
            assert b'TOP-SECRET' not in traversal.data
            via_symlink = client.get('/escape.txt')
            assert via_symlink.status_code == 404
            assert b'TOP-SECRET' not in via_symlink.data
    finally:
        link.unlink()
        secret.unlink()


def test_react_mode_missing_file_with_extension_is_404(client, tmp_path):
    (tmp_path / "index.html").write_text("<div id=root>stub</div>", encoding="utf-8")
    with patch.object(config, 'FRONTEND', 'react'), patch('app.FRONTEND_DIST', str(tmp_path)):
        response = client.get('/missing.js')
        assert response.status_code == 404
        assert b'<div id=root>' not in response.data


def test_react_mode_bare_api_path_is_404(client, tmp_path):
    (tmp_path / "index.html").write_text("<div id=root>stub</div>", encoding="utf-8")
    with patch.object(config, 'FRONTEND', 'react'), patch('app.FRONTEND_DIST', str(tmp_path)):
        response = client.get('/api')
        assert response.status_code == 404
        assert b'<div id=root>' not in response.data


def test_legacy_mode_does_not_serve_assets(client):
    with patch.object(config, 'FRONTEND', 'legacy'):
        assert client.get('/assets/anything.js').status_code == 404


def test_legacy_mode_logs_route_serves_logs_html(client):
    with patch.object(config, 'FRONTEND', 'legacy'), \
         patch('app.send_from_directory') as mock_send:
        mock_send.return_value = "logs html"
        response = client.get('/logs')
        assert response.status_code == 200
        mock_send.assert_called_with('static', 'logs.html')


def test_legacy_under_prefix_rewrites_asset_paths(client):
    """/legacy/ serves the old UI with its absolute asset paths moved under /legacy/."""
    with patch.object(config, 'FRONTEND', 'react'):
        response = client.get('/legacy/')
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert 'src="/legacy/js/utils.js"' in html
        assert 'href="/legacy/styles.css"' in html
        assert 'src="/js/' not in html


def test_legacy_prefix_serves_js_files(client):
    with patch.object(config, 'FRONTEND', 'react'):
        assert client.get('/legacy/js/utils.js').status_code == 200


def test_frontend_setting_rejects_unknown_value():
    import importlib
    import backend.config as cfg
    with patch.dict(os.environ, {"FRONTEND": "vue"}):
        with pytest.raises(ValueError, match="FRONTEND must be"):
            importlib.reload(cfg)
    importlib.reload(cfg)


@patch('app.ws_client.create_connection')
@patch('backend.tools.implementations.code_executor.collect_project_files')
def test_code_execution_ws_proxy_refuses_a_chat_the_caller_does_not_own(mock_collect_project_files, mock_create_connection, _caller_owns_the_chat):
    import json
    _caller_owns_the_chat.return_value = False  # another user's chat
    mock_ws = MagicMock()
    mock_ws.receive.side_effect = [json.dumps({"type": "init", "filePath": "main.py", "chat_id": "chat-of-a"}), None]
    flask_app.code_execution_ws_proxy(mock_ws)
    sent = [json.loads(c.args[0]) for c in mock_ws.send.call_args_list]
    assert sent == [{"type": "stderr", "data": "Error: Chat not found.\n"}, {"type": "exit", "code": 1}]
    _caller_owns_the_chat.assert_called_once_with("chat-of-a")
    mock_collect_project_files.assert_not_called()  # the foreign chat's files are never read
    mock_create_connection.assert_not_called()


@pytest.mark.parametrize("path", ["/legacy/", "/legacy/index.html", "/legacy/logs.html", "/legacy/js/app.js"])
def test_legacy_ui_is_403_for_a_user_and_200_for_the_admin(client, path):
    user_row = {**ADMIN_ROW, "id": "user-1", "email": "u@test", "role": "user"}
    with patch('app.send_from_directory', return_value="static asset") as send, patch('app._serve_legacy_page', return_value="legacy page") as page, \
         patch('app.db.get_user_by_email', return_value=user_row):
        denied = client.get(path)
    assert denied.status_code == 403 and denied.get_json() == {"error": "Forbidden"}
    send.assert_not_called(); page.assert_not_called()  # nothing is served
    with patch('app.send_from_directory', return_value="static asset"), patch('app._serve_legacy_page', return_value="legacy page"):
        assert client.get(path).status_code == 200  # the autouse fixture's user is the admin


@pytest.mark.parametrize("method,path", [("get", "/api/tools/portal/vnc/"), ("get", "/api/tools/portal/vnc/vnc.html"), ("post", "/api/tools/portal/init"),
                                          ("get", "/api/tools/portal/ws"), ("get", "/api/tools/portal/anything/new")])
def test_the_portal_is_403_for_a_user_and_never_contacted(client, method, path):
    user_row = {**ADMIN_ROW, "id": "user-1", "email": "u@test", "role": "user"}
    with patch('app.db.get_user_by_email', return_value=user_row), patch('httpx.Client') as http, \
         patch('app.ws_client.create_connection') as ws_connect:
        response = getattr(client, method)(path, headers={"Connection": "Upgrade", "Upgrade": "websocket"})
    assert response.status_code == 403 and response.get_json() == {"error": "Forbidden"}
    ws_connect.assert_not_called()  # the VNC websocket upstream is never opened
    http.assert_not_called()


def test_the_portal_hook_lets_the_admin_through_and_ignores_other_paths(client):
    upstream = MagicMock(status_code=200, content=b"novnc", headers={"content-type": "text/html"})
    with patch('backend.mcp_client.portal_vnc_auth_header', return_value={"Authorization": "Basic x"}), \
         patch('httpx.Client') as http:  # no real network: the proxy talks to a fake upstream
        http.return_value.__enter__.return_value.get.return_value = upstream
        response = client.get('/api/tools/portal/vnc/')  # the autouse fixture's user is the admin
    assert response.status_code == 200 and response.data == b"novnc"
    http.return_value.__enter__.return_value.get.assert_called_once_with("http://playwright_mcp:6080/vnc.html", headers={"Authorization": "Basic x"})
    assert client.get('/api/version').status_code == 200  # other paths are not affected


def test_the_portal_is_refused_without_an_authenticated_user_and_never_contacted(client):
    with patch('app.db.get_user_by_email', return_value=None), patch('httpx.Client') as http, \
         patch('app.ws_client.create_connection') as ws_connect:
        responses = [client.get('/api/tools/portal/vnc/'), client.post('/api/tools/portal/init'), client.get('/api/tools/portal/ws')]
    assert all(r.status_code in (401, 403) for r in responses)
    http.assert_not_called(); ws_connect.assert_not_called()


# --- the live-run WebSocket takes the run slot ---------------------------------------------------------

from contextlib import contextmanager
from backend.tools.implementations.run_slot import RunQueueFull, RunQueueTimeout


def _ws_with_init(chat_id="chat123"):
    import json
    ws = MagicMock()
    ws.receive.side_effect = [json.dumps({"type": "init", "filePath": "main.py", "chat_id": chat_id}), None]
    return ws


@patch('app.ws_client.create_connection')
@patch('backend.tools.implementations.code_executor.collect_project_files')
@patch('backend.database.db.get_setting', return_value=30)
def test_the_live_run_holds_the_slot_of_the_chat_owner_for_the_whole_session(mock_setting, mock_collect, mock_connect):
    log = []

    @contextmanager
    def recording_slot(owner, *a, **k):
        log.append(("enter", owner))
        yield
        log.append(("exit", owner))

    mock_collect.return_value = ("python", [{"path": "main.py", "content": "print(1)"}], "main.py")
    upstream = MagicMock()
    upstream.send.side_effect = lambda *a, **k: log.append(("upstream", None))
    mock_connect.return_value = upstream
    with patch('app.run_slot', recording_slot):
        flask_app.code_execution_ws_proxy(_ws_with_init())
    assert log[0] == ("enter", "owner-1") and log[-1] == ("exit", "owner-1")
    assert ("upstream", None) in log  # the runner was used between enter and exit


@pytest.mark.parametrize("error", [RunQueueFull("u"), RunQueueTimeout("u")])
@patch('app.ws_client.create_connection')
@patch('backend.tools.implementations.code_executor.collect_project_files')
def test_a_busy_runner_gets_stderr_and_exit_frames_and_no_upstream_connection(mock_collect, mock_connect, error):
    import json

    @contextmanager
    def refusing(owner, *a, **k):
        raise error
        yield

    ws = _ws_with_init()
    with patch('app.run_slot', refusing), patch('app.log_event') as events:
        flask_app.code_execution_ws_proxy(ws)
    sent = [json.loads(c.args[0]) for c in ws.send.call_args_list]
    assert sent == [{"type": "stderr", "data": "Error: Code runner is busy; try again shortly.\n"}, {"type": "exit", "code": 1}]
    mock_connect.assert_not_called()
    assert events.call_args_list[-1].args[0] in ("code_runner_queue_full_error", "code_runner_queue_timeout_error")


@patch('app.ws_client.create_connection')
@patch('backend.tools.implementations.code_executor.collect_project_files')
def test_a_chat_without_an_owner_gets_the_unavailable_frames_without_taking_the_slot(mock_collect, mock_connect):
    import json
    ws = _ws_with_init()
    with patch('app.db.get_chat_owner', return_value=None), patch('app.run_slot') as slot, patch('app.log_event') as events:
        flask_app.code_execution_ws_proxy(ws)
    sent = [json.loads(c.args[0]) for c in ws.send.call_args_list]
    assert sent == [{"type": "stderr", "data": "Error: Code runner is unavailable for this request.\n"}, {"type": "exit", "code": 1}]
    slot.assert_not_called(); mock_connect.assert_not_called()
    events.assert_any_call("code_runner_no_owner_error", {"chat_id": "chat123"})



def test_redirects_use_the_scheme_the_tunnel_forwards(client):
    """Behind the tunnel the app sees plain HTTP: it must trust X-Forwarded-Proto so its own redirects stay https."""
    response = client.get('/api/tools/portal/vnc', headers={"X-Forwarded-Proto": "https", "Host": "myai.example.dev"})
    assert response.status_code in (301, 308)
    assert response.headers["Location"].startswith("https://myai.example.dev/")


def test_redirects_without_the_forwarded_header_keep_the_request_scheme(client):
    response = client.get('/api/tools/portal/vnc', headers={"Host": "myai.example.dev"})
    assert response.headers["Location"].startswith("http://myai.example.dev/")
