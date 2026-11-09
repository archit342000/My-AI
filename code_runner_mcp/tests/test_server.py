from fastapi.testclient import TestClient
import os
import subprocess
import sys
import pytest
from unittest.mock import MagicMock, patch

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

WS_AUTH = {"X-API-KEY": "testkey"}


@pytest.mark.parametrize("url,headers", [
    ("/ws/execute", {}),                                          # no key
    ("/ws/execute", {"X-API-KEY": "wrongkey"}),                   # wrong key
    ("/ws/execute?api_key=testkey", {}),                          # the old query-string form is no longer accepted
    ("/ws/execute?api_key=testkey", {"X-API-KEY": "wrongkey"}),   # a right query key cannot rescue a wrong header
])
def test_websocket_refuses_a_missing_or_wrong_key_with_1008(url, headers):
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(url, headers=headers):
            pass
    assert exc.value.code == 1008

def test_websocket_sql_mysql_is_rejected():
    with client.websocket_connect("/ws/execute", headers=WS_AUTH) as ws:
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
    with client.websocket_connect("/ws/execute", headers=WS_AUTH) as ws:
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


# ---- API key loading: fail closed -----------------------------------------------------------------------------

@pytest.fixture
def keyless(monkeypatch):
    """Environment without any configured key (the module under test reads API_KEY_FILE at import time)."""
    monkeypatch.delenv("CODE_RUNNER_API_KEY", raising=False)
    monkeypatch.setattr("server.API_KEY_FILE", "")
    return monkeypatch


def test_load_api_key_raises_without_a_file_and_without_env(keyless):
    import server
    with pytest.raises(RuntimeError, match="API_KEY_FILE"):
        server.load_api_key()


def test_load_api_key_reads_and_strips_the_file(keyless, tmp_path):
    import server
    f = tmp_path / "key"
    f.write_text("  filekey\n")
    keyless.setattr("server.API_KEY_FILE", str(f))
    keyless.setenv("CODE_RUNNER_API_KEY", "envkey")
    assert server.load_api_key() == "filekey"      # the file wins over the environment


@pytest.mark.parametrize("file_state", ["unset", "missing", "empty"])
def test_load_api_key_falls_back_to_the_environment(keyless, tmp_path, file_state):
    import server
    if file_state == "missing":
        keyless.setattr("server.API_KEY_FILE", str(tmp_path / "nope"))
    elif file_state == "empty":
        (tmp_path / "empty").write_text("\n")
        keyless.setattr("server.API_KEY_FILE", str(tmp_path / "empty"))
    keyless.setenv("CODE_RUNNER_API_KEY", " envkey ")
    assert server.load_api_key() == "envkey"


def test_load_api_key_does_not_swallow_an_unreadable_key_file(keyless, tmp_path):
    import server
    keyless.setattr("server.API_KEY_FILE", str(tmp_path))      # a directory: exists, cannot be read
    keyless.setenv("CODE_RUNNER_API_KEY", "envkey")
    with pytest.raises(OSError):
        server.load_api_key()


def test_the_service_refuses_to_start_without_a_key(tmp_path):
    env = {k: v for k, v in os.environ.items() if k not in ("CODE_RUNNER_API_KEY", "API_KEY_FILE")}
    proc = subprocess.run([sys.executable, "-c", "import server"], cwd=os.path.dirname(os.path.dirname(__file__)),
                          env=env, capture_output=True, text=True, timeout=60)
    assert proc.returncode != 0
    assert "No API key configured" in proc.stderr


def test_every_route_requires_the_key():
    # control: the right key on the same route is not a 401
    assert client.post("/execute", headers={"X-API-KEY": "testkey"}, json={"language": "python", "code": "print(1)"}).status_code != 401
    assert client.post("/execute", json={"language": "python", "code": "print(1)"}).status_code == 401
    assert client.post("/install", json={"packages": ["requests"], "package_manager": "pip"}).status_code == 401
    assert client.post("/execute", headers={"X-API-KEY": "wrong"}, json={"language": "python", "code": "x"}).status_code == 401
    # a non-ASCII key (sent as raw bytes, which httpx needs for non-ASCII header values)
    assert client.post("/execute", headers={"X-API-KEY": "tëst".encode("utf-8")}, json={"language": "python", "code": "x"}).status_code == 401


def test_the_websocket_refuses_a_missing_or_wrong_key():
    from starlette.websockets import WebSocketDisconnect
    for url in ("/ws/execute", "/ws/execute?api_key=wrong"):
        with pytest.raises(WebSocketDisconnect) as e:
            with client.websocket_connect(url):
                pass
        assert e.value.code == 1008


# ---- /install: only plain package names ----------------------------------------------------------------------

AUTH = {"X-API-KEY": "testkey"}


@pytest.mark.parametrize("manager,packages", [
    ("pip", ["--index-url=http://evil/simple"]),
    ("pip", ["requests", "-r", "/etc/passwd"]),
    ("pip", ["https://evil/x.whl"]),
    ("pip", ["../pkg"]),
    ("npm", ["--registry=http://evil"]),
    ("npm", ["github:u/r"]),
    ("npm", ["a/b"]),
    ("pip", ["a"] * 21),
])
def test_install_rejects_options_urls_paths_and_too_many_packages_without_running_anything(manager, packages):
    with patch("server.subprocess.run") as run:
        res = client.post("/install", headers=AUTH, json={"packages": packages, "package_manager": manager})
    assert res.status_code == 400
    assert "detail" in res.json()
    run.assert_not_called()


def test_install_runs_pip_with_valid_names():
    with patch("server.subprocess.run", return_value=MagicMock(stdout="ok", stderr="", returncode=0)) as run:
        res = client.post("/install", headers=AUTH, json={"packages": ["requests", "numpy==1.26.4"], "package_manager": "pip"})
    assert res.status_code == 200 and res.json()["success"] is True
    assert run.call_args.args[0] == ["pip", "install", "--user", "--no-cache-dir", "requests", "numpy==1.26.4"]


def test_install_runs_npm_with_valid_names():
    with patch("server.subprocess.run", return_value=MagicMock(stdout="ok", stderr="", returncode=0)) as run, \
         patch("server.os.makedirs"):
        res = client.post("/install", headers=AUTH, json={"packages": ["lodash@4", "@types/node"], "package_manager": "npm"})
    assert res.status_code == 200 and res.json()["success"] is True
    assert run.call_args.args[0] == ["npm", "install", "--no-save", "lodash@4", "@types/node"]


def test_install_rejects_an_unsupported_manager_and_accepts_an_empty_list():
    assert client.post("/install", headers=AUTH, json={"packages": ["x"], "package_manager": "gem"}).status_code == 400
    assert client.post("/install", headers=AUTH, json={"packages": [], "package_manager": "pip"}).json()["success"] is True



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
    with client.websocket_connect("/ws/execute", headers=WS_AUTH) as ws:
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
