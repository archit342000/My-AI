from fastapi.testclient import TestClient
import os
import pytest

# Mock API Key environment variables before importing server
os.environ["CODE_RUNNER_API_KEY"] = "testkey"

from server import app

client = TestClient(app)

def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

def test_auth_failure():
    res = client.post("/execute", json={"language": "python", "code": "print(1)"})
    assert res.status_code == 401

def test_auth_success():
    headers = {"X-API-KEY": "testkey"}
    res = client.post(
        "/execute",
        headers=headers,
        json={"language": "python", "code": "print('Authenticated')"}
    )
    assert res.status_code == 200
    assert "Authenticated" in res.json()["stdout"]

def test_list_packages():
    headers = {"X-API-KEY": "testkey"}
    res = client.get("/packages?manager=pip", headers=headers)
    assert res.status_code == 200
    assert "packages" in res.json()
    assert res.json()["package_manager"] == "pip"

def test_websocket_auth_failure():
    import pytest
    from starlette.testclient import WebSocketDenialResponse
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/execute?api_key=wrongkey") as ws:
            pass

def test_websocket_sql_mysql_is_rejected():
    with client.websocket_connect("/ws/execute?api_key=testkey") as ws:
        ws.send_json({
            "language": "sql",
            "code": "SELECT 1;",
            "sql_target": "mysql",
            "timeout": 5
        })
        first = ws.receive_json()
        assert first.get("type") == "stderr"
        assert "MySQL is not available" in first.get("data", "")
        assert ws.receive_json() == {"type": "exit", "code": 1}

def test_websocket_execute():
    with client.websocket_connect("/ws/execute?api_key=testkey") as ws:
        ws.send_json({
            "language": "python",
            "code": "print('hello websocket')",
            "args": [],
            "timeout": 5
        })
        messages = []
        for _ in range(5):
            try:
                msg = ws.receive_json()
                messages.append(msg)
                if msg.get("type") == "exit":
                    break
            except Exception:
                break
        
        assert any(m.get("type") == "stdout" and "hello websocket" in m.get("data", "") for m in messages)
        assert any(m.get("type") == "exit" and m.get("code") == 0 for m in messages)

