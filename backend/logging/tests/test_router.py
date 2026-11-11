import pytest
import os
import json
from flask import Flask
from backend.logging.router import logs_bp, _tail_file
from unittest.mock import patch, mock_open

@pytest.fixture
def app(login_as, admin_a):
    """The logs app logged in as an admin; a regular user is tested with `login_as(app, user_b)`."""
    app = Flask(__name__)
    app.register_blueprint(logs_bp, url_prefix='/logs')
    login_as(app, admin_a)
    return app

@pytest.fixture
def client(app):
    return app.test_client()

@patch('backend.logging.router.os.getcwd')
@patch('backend.logging.router.send_from_directory')
def test_logs_page(mock_send, mock_getcwd, client):
    mock_getcwd.return_value = "/mock/dir"
    mock_send.return_value = "html content"
    
    res = client.get('/logs/ui')
    assert res.status_code == 200
    mock_send.assert_called_with("/mock/dir/static", "logs.html")

@patch('backend.logging.router.config.DATA_DIR', '/mock/data')
@patch('backend.logging.router.os.path.exists')
def test_get_log_index(mock_exists, client):
    # Not exists
    mock_exists.return_value = False
    res = client.get('/logs')
    assert res.status_code == 200
    assert res.json == []
    
    # Exists
    mock_exists.return_value = True
    m_open = mock_open(read_data='{"a": 1}\n\n{"b": 2}\ninvalid\n{"c": 3}\n')
    with patch('builtins.open', m_open):
        res = client.get('/logs?limit=2')
        assert res.status_code == 200
        # should return reversed last 2 valid entries
        assert res.json == [{"c": 3}, {"b": 2}]

@patch('backend.logging.router.config.DATA_DIR', '/mock/data')
@patch('backend.logging.router.os.path.exists')
def test_get_log_detail(mock_exists, client):
    # Missing path
    res = client.get('/logs/detail')
    assert res.status_code == 400
    
    # Path traversal attempt
    res = client.get('/logs/detail?path=../../etc/passwd')
    assert res.status_code == 403
    
    # Not exists
    mock_exists.return_value = False
    res = client.get('/logs/detail?path=llm_calls/1.json')
    assert res.status_code == 404
    
    # Success
    mock_exists.return_value = True
    m_open = mock_open(read_data='{"key": "value"}')
    with patch('builtins.open', m_open):
        res = client.get('/logs/detail?path=llm_calls/1.json')
        assert res.status_code == 200
        assert res.json == {"key": "value"}

@patch('backend.logging.router.config.DATA_DIR', '/mock/data')
@patch('backend.logging.router.os.path.exists')
@patch('backend.logging.router.os.listdir')
def test_get_event_logs(mock_listdir, mock_exists, client):
    # Not exists
    mock_exists.return_value = False
    res = client.get('/logs/events')
    assert res.status_code == 200
    assert res.json == []
    
    # No files
    mock_exists.return_value = True
    mock_listdir.return_value = ["not_an_event.txt"]
    res = client.get('/logs/events')
    assert res.status_code == 200
    assert res.json == []
    
    # With files
    mock_listdir.return_value = ["20231010_events.jsonl", "20231011_events.jsonl"]
    m_open = mock_open(read_data='{"event": 1}\n{"event": 2}')
    with patch('builtins.open', m_open):
        res = client.get('/logs/events')
        assert res.status_code == 200
        assert res.json == [{"event": 2}, {"event": 1}]

@patch('backend.logging.router.config.DATA_DIR', '/mock/data')
@patch('backend.logging.router.os.path.exists')
@patch('backend.logging.router._tail_file')
def test_get_app_logs(mock_tail, mock_exists, client):
    # Not exists
    mock_exists.return_value = False
    res = client.get('/logs/app')
    assert res.status_code == 200
    assert res.json == {"logs": [], "total": 0}
    
    # Exists
    mock_exists.return_value = True
    mock_tail.return_value = ["line 1", "line 2"]
    res = client.get('/logs/app?limit=10')
    assert res.status_code == 200
    assert res.json == {"logs": ["line 2", "line 1"], "total": 2}
    mock_tail.assert_called_with('/mock/data/logs/app.log', 10)

def test__tail_file(tmp_path):
    log_file = tmp_path / "app.log"
    
    # Empty file
    log_file.write_text("")
    assert _tail_file(str(log_file), 5) == []
    
    # Few lines
    log_file.write_text("line1\nline2\nline3\n")
    assert _tail_file(str(log_file), 2) == ["line2", "line3"]
    
    # Chunking test
    assert _tail_file(str(log_file), 10, chunk_size=2) == ["line1", "line2", "line3"]

@patch('backend.logging.router.config.DATA_DIR', '/mock/data')
@patch('backend.logging.router.os.path.exists')
def test_get_app_log_lines(mock_exists, client, tmp_path):
    # Not exists
    mock_exists.return_value = False
    res = client.get('/logs/app/lines?start=0&end=10')
    assert res.status_code == 200
    assert res.json == {"logs": [], "start": 0, "end": 10}
    
    # Exists
    mock_exists.return_value = True
    m_open = mock_open(read_data="line0\nline1\nline2\nline3\n")
    with patch('builtins.open', m_open):
        res = client.get('/logs/app/lines?start=1&end=3')
        assert res.status_code == 200
        assert res.json == {"logs": ["line1", "line2"], "start": 1, "end": 3}


from unittest.mock import MagicMock

@patch('backend.logging.router.make_connection')
def test_get_db_tables_and_data(mock_make_connection, client):
    # Test tables list
    res = client.get('/logs/db/tables')
    assert res.status_code == 200
    assert "chat_tables" in res.json
    assert "global_tables" in res.json
    assert "chats" in res.json["chat_tables"]
    assert "workspaces" in res.json["global_tables"]

    # Test invalid table access block
    res = client.get('/logs/db/table/forbidden_table')
    assert res.status_code == 403

    # Mock DB cursor responses
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_make_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    mock_row = {"id": "chat1", "title": "Test Chat"}
    # mock fetchall returning sqlite3.Row-like dictionary objects
    mock_cursor.fetchall.return_value = [mock_row]

    # Test valid chat-bound table data retrieval with filter
    res = client.get('/logs/db/table/chats?chat_id=chat1')
    assert res.status_code == 200
    assert len(res.json) == 1
    assert res.json[0]["id"] == "chat1"
    mock_cursor.execute.assert_called_with(
        "SELECT * FROM chats WHERE id = ? ORDER BY rowid DESC LIMIT ?",
        ("chat1", 200)
    )

    # Test valid global table data retrieval (no chat_id filter)
    res = client.get('/logs/db/table/workspaces')
    assert res.status_code == 200
    mock_cursor.execute.assert_called_with(
        "SELECT * FROM workspaces ORDER BY rowid DESC LIMIT ?",
        (200,)
    )


LOGS_ROUTES = ["/logs/ui", "/logs", "/logs/", "/logs/detail?file=x", "/logs/events", "/logs/app", "/logs/app/lines",
               "/logs/db/tables", "/logs/db/table/chats", "/logs/db/table/messages?chat_id=c1"]


@pytest.mark.parametrize("url", LOGS_ROUTES)
@patch('backend.logging.router.make_connection')
@patch('backend.logging.router.send_from_directory')
@patch('backend.logging.router.os.path.exists', return_value=True)
@patch('builtins.open')
def test_every_logs_route_is_403_for_a_user_and_reads_nothing(mock_open_file, mock_exists, mock_send, mock_conn, url, app, login_as, user_b):
    login_as(app, user_b)
    response = app.test_client().get(url)
    assert response.status_code == 403 and response.get_json() == {"error": "Forbidden"}
    mock_conn.assert_not_called()  # no raw rows of any user
    mock_send.assert_not_called()
    mock_open_file.assert_not_called()


def test_logs_routes_are_403_without_a_user():
    app = Flask(__name__)  # not logged in
    app.register_blueprint(logs_bp, url_prefix='/logs')
    assert app.test_client().get('/logs/db/tables').status_code == 403



# ---- no raw exception text on the Logs page --------------------------------------------------------------------

@pytest.mark.parametrize("url", ['/logs', '/logs/detail?path=a.json', '/logs/events', '/logs/app', '/logs/app/lines', '/logs/db/table/chats'])
def test_a_failing_log_read_sends_a_fixed_plain_message_and_logs_the_detail(client, url, tmp_path):
    secret = "/secret/place/chats.db is locked"
    with patch('backend.logging.router.config.DATA_DIR', str(tmp_path)), \
         patch('backend.logging.router.os.path.exists', return_value=True), \
         patch('backend.logging.router.os.listdir', return_value=["2026_events.jsonl"]), \
         patch('builtins.open', side_effect=OSError(secret)), \
         patch('backend.logging.router.make_connection') as connect, \
         patch('backend.logging.router._tail_file', side_effect=OSError(secret)), \
         patch('backend.logging.router.log_event') as events:
        connect.return_value.cursor.side_effect = OSError(secret)
        res = client.get(url)
    assert res.status_code == 500
    assert res.json == {"error": "Could not read the logs. Try again in a moment."}
    assert "secret" not in res.get_data(as_text=True)
    assert events.call_args.args[0] == "logs_read_error" and secret in events.call_args.args[1]["error"]
