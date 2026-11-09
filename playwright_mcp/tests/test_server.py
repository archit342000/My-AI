import os
import re as _re
import uuid
import pytest
import asyncio
import time
import httpx
import json
from unittest.mock import MagicMock, patch, AsyncMock
from playwright_mcp.server import (
    is_safe_web_url, 
    sanitize_output, 
    clean_html_to_markdown,
    _extract_pdf_content,
    _get_session,
    _cleanup_expired_sessions,
    _sessions,
    get_secret,
    check_internet_connectivity,
    visit_page,
    fetch_and_encode_image,
    AuthMiddleware
)

@pytest.mark.parametrize("url,expected", [
    ("https://www.google.com", True),
    ("http://example.org/path?q=1", True),
    ("ftp://example.com", False),
    ("file:///etc/passwd", False),
    ("http://127.0.0.1", False),
    ("http://169.254.169.254", False),
    ("http://localhost", False),
])
def test_is_safe_web_url(url, expected):
    assert is_safe_web_url(url) == expected

@pytest.mark.parametrize("input_text,expected", [
    ("Hello world", "Hello world"),
    ("<p>Hello</p>", "Hello"),
    ("javascript:alert(1)", "alert(1)"),
    ("data:text/html,<html>", "text/html,"),
    ("eval('evil')", "'evil')"),
    ("window.location = '/'", "location = '/'"),
    ("document.cookie", ""),
])
def test_sanitize_output(input_text, expected):
    assert sanitize_output(input_text) == expected

def test_clean_html_to_markdown():
    html = """
    <html>
        <body>
            <nav>Menu</nav>
            <main>
                <h1>Title</h1>
                <p>Content with <a href="http://link.com">link</a>.</p>
            </main>
            <footer>Footer</footer>
        </body>
    </html>
    """
    md = clean_html_to_markdown(html, "http://example.com", detail_level="standard")
    assert "# Title" in md
    assert "[link](http://link.com)" in md
    assert "Menu" in md
    assert "Footer" in md
    
    md_basic = clean_html_to_markdown(html, "http://example.com", detail_level="basic")
    assert "Menu" not in md_basic
    assert "Footer" not in md_basic
    assert "[link]" not in md_basic

def test_clean_html_base64_stripping():
    html = '<p><img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="></p>'
    md = clean_html_to_markdown(html, "http://example.com")
    assert "[Base64 Image Omitted]" in md

@pytest.mark.asyncio
async def test_session_management():
    _sessions.clear()
    with pytest.raises(ValueError, match="Session not found"):
        await _get_session("non-existent")
    
    mock_context = MagicMock()
    _sessions["test-session"] = {
        "context": mock_context,
        "last_used": time.time()
    }
    session = await _get_session("test-session")
    assert session["context"] == mock_context
    
    _sessions["expired"] = {
        "context": MagicMock(),
        "last_used": time.time() - 600
    }
    await _cleanup_expired_sessions()
    assert "expired" not in _sessions
    assert "test-session" in _sessions

@pytest.mark.asyncio
async def test_extract_pdf_content():
    with patch("pypdf.PdfReader") as mock_reader:
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "PDF Content"
        mock_reader.return_value.pages = [mock_page]
        res = await _extract_pdf_content(b"fake pdf")
        assert res == "PDF Content"

def test_get_secret():
    with patch("builtins.open", side_effect=IOError):
        with patch.dict("os.environ", {"TEST_SECRET": "val"}):
            assert get_secret("TEST_SECRET") == "val"

@pytest.mark.asyncio
async def test_check_internet_connectivity():
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = MagicMock()
        assert await check_internet_connectivity() is True
        mock_get.side_effect = Exception("offline")
        assert await check_internet_connectivity() is False

@pytest.mark.asyncio
async def test_visit_page_orchestration():
    # We need to be careful with global state/mocks.
    # We mock fetch_with_playwright to avoid launching a browser.
    with patch("playwright_mcp.server.check_internet_connectivity", return_value=True):
        with patch("playwright_mcp.server.fetch_with_playwright", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = "Extracted Text"
            
            # Case 1: Valid external URL
            res = await visit_page("https://google.com")
            assert res == "Extracted Text"
            
            # Case 2: Forbidden URL (localhost)
            # is_safe_web_url should catch this.
            res = await visit_page("http://127.0.0.1")
            assert "forbidden" in res.lower()
            
            # Case 3: Internet Connectivity failure
            with patch("playwright_mcp.server.check_internet_connectivity", return_value=False):
                res = await visit_page("https://google.com")
                assert "connectivity failure" in res.lower()

@pytest.mark.asyncio
async def test_fetch_and_encode_image():
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake image"
        mock_response.headers = {"content-type": "image/png"}
        mock_get.return_value = mock_response
        
        res_json = await fetch_and_encode_image("https://example.com/img.png")
        res = json.loads(res_json)
        assert "image" in res
        assert "data:image/png;base64," in res["image"]
        
        mock_get.side_effect = Exception("Fetch failed")
        res_json = await fetch_and_encode_image("https://example.com/img.png")
        res = json.loads(res_json)
        assert "error" in res

@pytest.mark.asyncio
async def test_get_session_crashed_cleanup():
    _sessions.clear()
    
    # Mock page that is closed
    mock_page = MagicMock()
    mock_page.is_closed.return_value = True
    mock_context = AsyncMock()
    
    _sessions["crashed-session"] = {
        "context": mock_context,
        "page": mock_page,
        "last_used": time.time()
    }
    
    with pytest.raises(ValueError, match="Session is no longer active"):
        await _get_session("crashed-session")
        
    assert "crashed-session" not in _sessions
    mock_context.close.assert_called_once()

@pytest.mark.asyncio
async def test_fetch_and_encode_image_redirect_limit():
    with patch("httpx.AsyncClient.get") as mock_get:
        # Mock responses that keep redirecting
        mock_response = MagicMock()
        mock_response.status_code = 302
        mock_response.headers = {"Location": "https://example.com/redirect"}
        mock_get.return_value = mock_response
        
        res_json = await fetch_and_encode_image("https://example.com/img.png")
        res = json.loads(res_json)
        assert "error" in res
        assert "redirect loop" in res["error"]

@pytest.mark.asyncio
async def test_shutdown_event_cleanup():
    import playwright_mcp.server as server
    
    # Setup mocks for active sessions and portal process and playwright instance
    mock_process = MagicMock()
    mock_process.poll.return_value = None  # process is running
    server._portal_process = mock_process
    
    mock_context = AsyncMock()
    mock_browser = AsyncMock()
    
    server._sessions = {
        "sess-1": {"context": mock_context},
        "sess-2": {"browser_cdp": mock_browser}
    }
    
    mock_manager = AsyncMock()
    server._playwright_manager = mock_manager
    server._playwright_instance = MagicMock()
    
    # Call shutdown
    await server.shutdown_event()
    
    # Verify portal terminated/killed
    mock_process.terminate.assert_called_once()
    
    # Verify sessions closed
    mock_context.close.assert_called_once()
    mock_browser.close.assert_called_once()
    assert len(server._sessions) == 0
    
    # Verify playwright manager stopped
    mock_manager.stop.assert_called_once()
    assert server._playwright_instance is None
    assert server._playwright_manager is None


# ---- AuthMiddleware ------------------------------------------------------------------------------------------
# These tests use anyio so they run without the pytest-asyncio plugin, which the older tests in this module need.

def _scope(path, *keys):
    return {"type": "http", "path": path, "headers": [(b"x-mcp-api-key", k) for k in keys]}


async def _through_middleware(scope, configured_key):
    """Returns (inner_app_called, status of the first response message or None)."""
    inner = AsyncMock()
    send = AsyncMock()
    with patch("playwright_mcp.server.MCP_API_KEY", configured_key):
        await AuthMiddleware(inner)(scope, None, send)
    status = send.call_args_list[0].args[0]["status"] if send.call_args_list else None
    return inner.called, status


@pytest.mark.anyio
async def test_portal_routes_need_the_key():
    assert await _through_middleware(_scope("/portal/init"), "secret") == (False, 401)
    assert await _through_middleware(_scope("/portal/init", b"wrong"), "secret") == (False, 401)
    assert await _through_middleware(_scope("/portal/vnc", b"secret"), "secret") == (True, None)
    assert await _through_middleware(_scope("/portal/init", b"secret"), "secret") == (True, None)


@pytest.mark.anyio
async def test_mcp_routes_still_need_the_key():
    assert await _through_middleware(_scope("/sse"), "secret") == (False, 401)
    assert await _through_middleware(_scope("/messages/abc", b"wrong"), "secret") == (False, 401)
    assert await _through_middleware(_scope("/messages/abc", b"secret"), "secret") == (True, None)


@pytest.mark.anyio
async def test_protected_routes_fail_closed_without_a_configured_key():
    for key in ("", None):
        for path in ("/portal/init", "/sse", "/messages/x"):
            assert await _through_middleware(_scope(path), key) == (False, 401), (key, path)
            assert await _through_middleware(_scope(path, b""), key) == (False, 401), (key, path)
            assert await _through_middleware(_scope(path, b"anything"), key) == (False, 401), (key, path)


@pytest.mark.anyio
async def test_bad_keys_are_rejected_without_raising():
    for sent in ("sécret".encode("utf-8"), b"\xff\xfe", b"secre", b"secret-and-more"):
        assert await _through_middleware(_scope("/portal/init", sent), "secret") == (False, 401), sent
    assert await _through_middleware(_scope("/portal/init", b"secret", b"secret"), "secret") == (False, 401)   # repeated header


@pytest.mark.anyio
async def test_other_paths_and_scopes_pass_through_without_a_key():
    assert await _through_middleware(_scope("/other"), "") == (True, None)
    assert await _through_middleware({"type": "lifespan"}, "") == (True, None)


@pytest.mark.anyio
async def test_the_key_is_never_logged(caplog):
    import logging
    with caplog.at_level(logging.WARNING):
        await _through_middleware(_scope("/portal/init", b"super-secret-guess"), "super-secret-value")
    assert "super-secret" not in caplog.text and "Unauthorized access attempt" in caplog.text


@pytest.mark.anyio
@pytest.mark.parametrize("path", ["/portal/init/", "/portal//init", "/portal/", "/messages/", "/sse"])
async def test_path_variants_under_a_protected_prefix_need_the_key(path):
    assert await _through_middleware(_scope(path), "secret") == (False, 401), path


@pytest.mark.anyio
@pytest.mark.parametrize("path", ["/portal", "/PORTAL/init", "/portal%2Finit", "/sse/", "/messages"])
async def test_paths_outside_the_prefixes_are_not_routes_of_the_app_so_they_are_not_guarded_here(path):
    # They match no route (404, or Starlette's slash redirect which re-enters the middleware), so there is
    # nothing behind them to protect; this pins that the guard is the prefix rule and nothing broader.
    assert await _through_middleware(_scope(path), "secret") == (True, None), path


def test_the_real_app_rejects_portal_init_without_a_key():
    from starlette.testclient import TestClient
    from playwright_mcp.server import app
    with patch("playwright_mcp.server.MCP_API_KEY", "secret"):
        client = TestClient(app)
        assert client.post("/portal/init").status_code == 401
        assert client.post("/portal/init", headers={"X-MCP-API-KEY": "wrong"}).status_code == 401
        assert client.get("/sse").status_code == 401


# --- per-user browser profiles ----------------------------------------------------------------

from playwright_mcp import server as pw_server


@pytest.fixture
def fake_playwright(tmp_path, monkeypatch):
    """A mocked Playwright object; sessions and the portal state are reset around each test."""
    monkeypatch.chdir(tmp_path)
    context = MagicMock()
    context.pages = []
    context.new_page = AsyncMock(return_value=MagicMock())
    context.add_init_script = AsyncMock()
    playwright = MagicMock()
    playwright.chromium.launch_persistent_context = AsyncMock(return_value=context)
    browser = MagicMock()
    browser.contexts = [context]
    playwright.chromium.connect_over_cdp = AsyncMock(return_value=browser)
    pw_server._sessions.clear()
    with patch.object(pw_server, "_get_playwright", AsyncMock(return_value=playwright)), \
         patch.object(pw_server, "stealth_async", AsyncMock()):
        yield playwright
    pw_server._sessions.clear()


@pytest.mark.anyio
async def test_two_profiles_use_two_different_user_data_dirs(fake_playwright, tmp_path):
    await pw_server.browser_start_session("s1", "profile-a")
    await pw_server.browser_start_session("s2", "profile-b")
    dirs = [c.kwargs["user_data_dir"] for c in fake_playwright.chromium.launch_persistent_context.call_args_list]
    assert dirs == [os.path.join(str(tmp_path), "playwright_data", "profiles", "profile-a"),
                    os.path.join(str(tmp_path), "playwright_data", "profiles", "profile-b")]
    assert all(os.path.isdir(d) for d in dirs)
    assert not os.path.exists(os.path.join(str(tmp_path), "playwright_data", "default_profile"))  # the shared profile is retired


@pytest.mark.anyio
@pytest.mark.parametrize("bad", ["", "../etc", "a/b", "A_Upper", "x" * 65, "with space", "dot.dot", "a\\b"])
async def test_an_invalid_profile_id_is_an_error_and_nothing_is_launched(fake_playwright, bad):
    result = json.loads(await pw_server.browser_start_session("s1", bad))
    assert "error" in result
    fake_playwright.chromium.launch_persistent_context.assert_not_called()
    fake_playwright.chromium.connect_over_cdp.assert_not_called()
    assert "s1" not in pw_server._sessions


@pytest.mark.anyio
@pytest.mark.parametrize("good", ["a", uuid.uuid4().hex, "user_1-b", "x" * 64])
async def test_valid_profile_ids_are_accepted(fake_playwright, good):
    assert json.loads(await pw_server.browser_start_session("s1", good))["status"] == "created"


@pytest.mark.anyio
async def test_a_session_never_attaches_over_cdp_unless_attach_portal_is_set(fake_playwright):
    running = MagicMock()
    running.poll.return_value = None  # the portal Chromium is running
    with patch.object(pw_server, "_portal_process", running):
        user = json.loads(await pw_server.browser_start_session("s-user", "user-1"))
        admin = json.loads(await pw_server.browser_start_session("s-admin", "admin-1", attach_portal=True))
    assert user["status"] == "created"  # its own profile, even though the portal is running
    assert admin["status"] == "connected_cdp"
    fake_playwright.chromium.connect_over_cdp.assert_awaited_once()
    fake_playwright.chromium.launch_persistent_context.assert_awaited_once()


@pytest.mark.anyio
async def test_attach_portal_without_a_running_portal_falls_back_to_the_profile(fake_playwright):
    result = json.loads(await pw_server.browser_start_session("s1", "admin-1", attach_portal=True))
    assert result["status"] == "created"
    fake_playwright.chromium.connect_over_cdp.assert_not_called()


def test_profile_id_pattern_is_the_documented_one():
    assert _re.fullmatch(pw_server.PROFILE_ID_PATTERN, "abc_123-x") and not _re.fullmatch(pw_server.PROFILE_ID_PATTERN, "ABC")


def test_entrypoint_clears_locks_in_every_profile_and_no_longer_lists_default_profile():
    text = open(os.path.join(os.path.dirname(__file__), "..", "entrypoint.sh")).read()
    assert "/app/playwright_data/portal_profile" in text and "/app/playwright_data/profiles/*" in text
    assert "default_profile" not in text
    assert "SingletonLock" in text and "SingletonCookie" in text and "SingletonSocket" in text

