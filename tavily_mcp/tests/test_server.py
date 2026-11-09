import hashlib
import hmac
import pytest
import json
import time
from unittest.mock import MagicMock, patch, AsyncMock
from tavily_mcp.server import (
    sanitize_output,
    get_secret,
    execute_tavily_search,
    audit_tavily_search,
    async_tavily_search,
    async_tavily_map,
    _tavily_search_cache,
    AuthMiddleware
)

@pytest.mark.parametrize("input_text,expected", [
    ("Hello world", "Hello world"),
    ("<p>Hello</p>", "Hello"),
    ("javascript:alert(1)", "alert(1)"),
    ("eval('evil')", "'evil')"),
])
def test_sanitize_output(input_text, expected):
    assert sanitize_output(input_text) == expected

def test_get_secret():
    with patch("builtins.open", side_effect=IOError):
        with patch.dict("os.environ", {"TEST_TAVILY": "key"}):
            assert get_secret("TEST_TAVILY") == "key"

@pytest.mark.asyncio
async def test_audit_tavily_search():
    _tavily_search_cache.clear()
    res = await audit_tavily_search("test-chat")
    assert "Error: No recent search" in res
    _tavily_search_cache["test-chat"] = {
        "raw_content": "Raw Data",
        "timestamp": time.time()
    }
    res = await audit_tavily_search("test-chat")
    assert res == "Raw Data"
    _tavily_search_cache["test-chat"]["timestamp"] = time.time() - 4000
    res = await audit_tavily_search("test-chat")
    assert "Error: The previous search data has expired" in res

@pytest.mark.asyncio
async def test_execute_tavily_search_success():
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "answer": "The answer is 42",
            "results": [{"title": "T1", "url": "U1", "content": "C1", "score": 0.9}],
            "images": ["I1"]
        }
        mock_post.return_value = mock_response
        with patch("tavily_mcp.server.TAVILY_API_KEY", "dummy"):
            res_str = await execute_tavily_search("q", chat_id="c1")
            res = json.loads(res_str)
            assert "42" in res["standard_output"]
            assert "c1" in _tavily_search_cache

@pytest.mark.asyncio
async def test_async_tavily_search_scenarios():
    with patch("httpx.AsyncClient.post") as mock_post:
        # Success
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [], "images": []}
        mock_post.return_value = mock_response
        with patch("tavily_mcp.server.TAVILY_API_KEY", "dummy"):
            res = json.loads(await async_tavily_search("q"))
            assert "results" in res
        
        # Failure
        mock_post.side_effect = Exception("API Error")
        res = json.loads(await async_tavily_search("q"))
        assert "error" in res
        assert "API Error" in res["error"]

@pytest.mark.asyncio
async def test_async_tavily_map_scenarios():
    with patch("httpx.AsyncClient.post") as mock_post:
        # Success
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_post.return_value = mock_response
        with patch("tavily_mcp.server.TAVILY_API_KEY", "dummy"):
            res = json.loads(await async_tavily_map("url", "inst"))
            assert "results" in res
        
        # Failure
        mock_post.side_effect = Exception("Map Error")
        res = json.loads(await async_tavily_map("url", "inst"))
        assert "error" in res
        assert "Map Error" in res["error"]

@pytest.mark.asyncio
async def test_auth_middleware():
    mock_app = AsyncMock()
    middleware = AuthMiddleware(mock_app)
    await middleware({"type": "websocket"}, None, None)
    mock_app.assert_called_once()
    mock_app.reset_mock()
    await middleware({"type": "http", "path": "/health"}, None, None)
    mock_app.assert_called_once()
    mock_app.reset_mock()
    with patch("tavily_mcp.server.MCP_API_KEY", "secret"):
        send_mock = AsyncMock()
        await middleware({"type": "http", "path": "/sse", "headers": [(b"x-mcp-api-key", b"wrong")]}, None, send_mock)
        mock_app.assert_not_called()
        send_mock.assert_called()


def _http_scope(path, key=None):
    headers = [] if key is None else [(b"x-mcp-api-key", key)]
    return {"type": "http", "path": path, "headers": headers}


async def _run_middleware(scope, mcp_api_key):
    """Runs the middleware with the given configured key; returns (app_called, status or None)."""
    app = AsyncMock()
    send = AsyncMock()
    with patch("tavily_mcp.server.MCP_API_KEY", mcp_api_key):
        await AuthMiddleware(app)(scope, None, send)
    status = send.call_args_list[0].args[0]["status"] if send.call_args_list else None
    return app.called, status


# The tests below use anyio because pytest-asyncio is not installed in the dev venv; the older tests in this
# module use asyncio. Align the markers when that dependency is pinned.
@pytest.mark.anyio
async def test_auth_missing_or_wrong_key_is_rejected_with_401():
    for scope in (_http_scope("/sse"), _http_scope("/sse", b"wrong"), _http_scope("/messages/abc", b"wrong"),
                  _http_scope("/messages/", b"")):
        assert await _run_middleware(scope, "secret") == (False, 401), scope["path"]


@pytest.mark.anyio
async def test_auth_correct_key_reaches_the_app_wrong_keys_of_any_length_do_not():
    assert await _run_middleware(_http_scope("/sse", b"secret"), "secret") == (True, None)
    assert await _run_middleware(_http_scope("/messages/abc", b"secret"), "secret") == (True, None)
    for wrong in (b"secreT", b"secre", b"secret-and-more", b"s"):   # same length, shorter, longer
        assert await _run_middleware(_http_scope("/sse", wrong), "secret") == (False, 401), wrong


@pytest.mark.anyio
async def test_auth_compares_digests_with_compare_digest():
    with patch("tavily_mcp.server.hmac.compare_digest", wraps=hmac.compare_digest) as compare:
        await _run_middleware(_http_scope("/sse", b"secret"), "secret")
    assert compare.call_args.args == (hashlib.sha256(b"secret").digest(), hashlib.sha256(b"secret").digest())


@pytest.mark.anyio
async def test_auth_rejects_a_repeated_key_header_in_either_order():
    for headers in ([(b"x-mcp-api-key", b"secret"), (b"x-mcp-api-key", b"other")],
                    [(b"x-mcp-api-key", b"other"), (b"x-mcp-api-key", b"secret")],
                    [(b"x-mcp-api-key", b"secret"), (b"x-mcp-api-key", b"secret")]):
        scope = {"type": "http", "path": "/sse", "headers": headers}
        assert await _run_middleware(scope, "secret") == (False, 401), headers


@pytest.mark.anyio
async def test_auth_never_logs_the_key_or_a_forged_newline(caplog):
    import logging
    with caplog.at_level(logging.WARNING):
        await _run_middleware(_http_scope("/sse", b"super-secret-guess"), "super-secret-value")
        await _run_middleware(_http_scope("/messages/%0aFORGED\nline", b"x"), "")
    assert "super-secret" not in caplog.text
    assert "\nline" not in caplog.text and "Unauthorized access attempt" in caplog.text


@pytest.mark.anyio
async def test_auth_fails_closed_when_no_key_is_configured():
    for key in ("", None):
        for scope in (_http_scope("/sse"), _http_scope("/sse", b"anything"), _http_scope("/messages/x", b"")):
            assert await _run_middleware(scope, key) == (False, 401), (key, scope["path"])


@pytest.mark.anyio
async def test_auth_non_ascii_key_is_rejected_without_raising():
    assert await _run_middleware(_http_scope("/sse", "sécret".encode("utf-8")), "secret") == (False, 401)
    assert await _run_middleware(_http_scope("/sse", b"\xff\xfe"), "secret") == (False, 401)


@pytest.mark.anyio
async def test_auth_leaves_other_paths_and_scopes_alone_even_without_a_key():
    assert await _run_middleware(_http_scope("/health"), "") == (True, None)
    assert await _run_middleware({"type": "websocket"}, "") == (True, None)

