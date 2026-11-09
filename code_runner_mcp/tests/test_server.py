from fastapi.testclient import TestClient
import os
import pytest
from unittest.mock import patch

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



# ---- timeout clamping ----------------------------------------------------------------------------------------------

def test_parse_timeout_clamps_and_validates():
    import server
    assert server._parse_timeout(10000) == server.MAX_TIMEOUT
    assert server._parse_timeout(server.MAX_TIMEOUT) == server.MAX_TIMEOUT
    assert server._parse_timeout(0) == 1
    assert server._parse_timeout(-7) == 1
    assert server._parse_timeout(30) == 30
    assert server._parse_timeout(None) == 30
    assert server._parse_timeout("10") == 10
    assert server._parse_timeout("99999") == server.MAX_TIMEOUT
    for bad in (True, False, "x", "1.5", "-3", "", 1.5, [], {}, "٣"):
        with pytest.raises(ValueError):
            server._parse_timeout(bad)


def _executed_with(timeout_value):
    from executor import ExecutionResult
    done = ExecutionResult(stdout="", stderr="", exit_code=0, execution_time_ms=1, language="python", timed_out=False)
    body = {"language": "python", "code": "print(1)"}
    if timeout_value != "omit":
        body["timeout"] = timeout_value
    with patch("server.CodeExecutor.execute", return_value=done) as execute:
        res = client.post("/execute", headers={"X-API-KEY": "testkey"}, json=body)
    return res, execute


@pytest.mark.parametrize("sent,expected", [(10000, 580), ("10", 10), (None, 30), ("omit", 30), (0, 1), (45, 45)])
def test_execute_clamps_the_client_timeout(sent, expected):
    res, execute = _executed_with(sent)
    assert res.status_code == 200
    assert execute.call_args.kwargs["timeout"] == expected


@pytest.mark.parametrize("sent,status", [(True, 422), (1.5, 422), ([], 422), ("x", 400), ("1.5", 400)])
def test_execute_rejects_a_non_integer_timeout_before_running_anything(sent, status):
    res, execute = _executed_with(sent)
    assert res.status_code == status
    execute.assert_not_called()


def _ws_run(config_extra):
    config = {"language": "python", "code": "print(1)", **config_extra}
    with client.websocket_connect("/ws/execute?api_key=testkey") as ws:
        ws.send_json(config)
        frames = []
        while True:
            frame = ws.receive_json()
            frames.append(frame)
            if frame.get("type") == "exit":
                return frames


def test_websocket_clamps_a_huge_timeout_and_the_run_uses_the_clamped_value():
    import asyncio
    import server
    waited = []
    real_wait_for = asyncio.wait_for

    async def spy_wait_for(awaitable, timeout=None):
        waited.append(timeout)
        return await real_wait_for(awaitable, timeout=timeout)

    with patch("server.asyncio.wait_for", spy_wait_for):
        frames = _ws_run({"timeout": 10000})
    assert waited and waited[-1] == server.MAX_TIMEOUT
    assert frames[-1] == {"type": "exit", "code": 0}


@pytest.mark.parametrize("bad", ["x", True, 1.5])
def test_websocket_rejects_a_non_integer_timeout_with_a_clear_frame(bad):
    frames = _ws_run({"timeout": bad})
    assert frames == [{"type": "stderr", "data": "Error: timeout must be an integer.\n"}, {"type": "exit", "code": 1}]


def test_websocket_treats_a_null_or_missing_timeout_as_the_default():
    assert _ws_run({"timeout": None})[-1] == {"type": "exit", "code": 0}
    assert _ws_run({})[-1] == {"type": "exit", "code": 0}
