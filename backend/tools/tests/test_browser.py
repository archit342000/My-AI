import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from backend.tools.browser import (
    browser_navigate, 
    browser_read_page, 
    browser_screenshot,
    browser_click,
    browser_type,
    browser_scroll,
    browser_get_interactive_elements,
    browser_back
)

@pytest.fixture
def mock_playwright():
    with patch('backend.tools.browser.playwright_client') as mock:
        mock.connect = AsyncMock()
        mock.execute_tool = AsyncMock()
        yield mock

@pytest.fixture
def mock_db():
    with patch('backend.tools.browser.db') as mock:
        yield mock

@pytest.mark.anyio
async def test_browser_navigate(mock_playwright, mock_db):
    mock_db.get_chat.return_value = {"browsing_session_id": "session123"}
    mock_playwright.execute_tool.return_value = MagicMock(content=[MagicMock(text='{"status": "ok"}')])
    
    res = await browser_navigate(url="https://example.com", chat_id="chat1")
    
    assert res == '{"status": "ok"}'
    mock_playwright.execute_tool.assert_called_with(
        "browser_navigate", 
        {"session_id": "session123", "url": "https://example.com"}
    )

@pytest.mark.anyio
async def test_browser_read_page_truncation(mock_playwright, mock_db):
    mock_db.get_chat.return_value = {"browsing_session_id": "s1"}
    very_long_text = "A" * 15000
    mock_playwright.execute_tool.return_value = MagicMock(content=[MagicMock(text=very_long_text)])
    
    with patch('backend.config.BROWSING_AGENT_MAX_CHARS_PER_PAGE', 1000):
        res = await browser_read_page(chat_id="chat1")
        assert len(res) > 1000
        assert "[Truncated" in res
        assert res.startswith("A" * 1000)

@pytest.mark.anyio
async def test_browser_screenshot(mock_playwright, mock_db):
    mock_db.get_chat.return_value = {"browsing_session_id": "s1"}
    # Dummy base64 for "data:image/jpeg;base64,..."
    dummy_img = "data:image/jpeg;base64,/9j/4AAQSkZJRg=="
    mock_playwright.execute_tool.return_value = MagicMock(content=[MagicMock(text=json.dumps({"image": dummy_img}))])
    
    with patch('os.makedirs'), patch('builtins.open', MagicMock()):
        res = await browser_screenshot(chat_id="chat1")
        data = json.loads(res)
        assert data["status"] == "success"
        assert "screenshot_ref" in data

@pytest.mark.anyio
async def test_a_failing_screenshot_save_gives_a_fixed_message_and_logs_the_detail(mock_playwright, mock_db):
    mock_db.get_chat.return_value = {"browsing_session_id": "s1"}
    dummy_img = "data:image/jpeg;base64,/9j/4AAQSkZJRg=="
    mock_playwright.execute_tool.return_value = MagicMock(content=[MagicMock(text=json.dumps({"image": dummy_img}))])
    with patch('os.makedirs', side_effect=OSError("/secret/dir is read-only")), patch('backend.tools.browser.log_event') as events:
        res = await browser_screenshot(chat_id="chat1")
    assert json.loads(res) == {"error": "Could not process the screenshot. Try again."}
    assert "secret" not in res
    assert events.call_args.args[0] == "browser_screenshot_error" and "read-only" in events.call_args.args[1]["error"]

@pytest.mark.anyio
async def test_browser_click(mock_playwright, mock_db):
    mock_db.get_chat.return_value = {"browsing_session_id": "s1"}
    mock_playwright.execute_tool.return_value = MagicMock(content=[MagicMock(text='{"status": "clicked"}')])
    
    res = await browser_click(selector="#btn", chat_id="chat1")
    assert res == '{"status": "clicked"}'

@pytest.mark.anyio
async def test_browser_type(mock_playwright, mock_db):
    mock_db.get_chat.return_value = {"browsing_session_id": "s1"}
    mock_playwright.execute_tool.return_value = MagicMock(content=[MagicMock(text='{"status": "typed"}')])
    
    res = await browser_type(selector="#input", text="hello", chat_id="chat1", submit=True)
    assert res == '{"status": "typed"}'

@pytest.mark.anyio
async def test_browser_scroll(mock_playwright, mock_db):
    mock_db.get_chat.return_value = {"browsing_session_id": "s1"}
    mock_playwright.execute_tool.return_value = MagicMock(content=[MagicMock(text='{"status": "scrolled"}')])
    
    res = await browser_scroll(direction="down", chat_id="chat1")
    assert res == '{"status": "scrolled"}'

@pytest.mark.anyio
async def test_browser_get_interactive_elements(mock_playwright, mock_db):
    mock_db.get_chat.return_value = {"browsing_session_id": "s1"}
    mock_playwright.execute_tool.return_value = MagicMock(content=[MagicMock(text="button1, button2")])
    
    res = await browser_get_interactive_elements(chat_id="chat1")
    assert res == "button1, button2"

@pytest.mark.anyio
async def test_browser_get_interactive_elements_truncation(mock_playwright, mock_db):
    mock_db.get_chat.return_value = {"browsing_session_id": "s1"}
    long_text = "E" * 2000
    mock_playwright.execute_tool.return_value = MagicMock(content=[MagicMock(text=long_text)])
    
    with patch('backend.config.BROWSING_AGENT_MAX_CHARS_INTERACTIVE', 500):
        res = await browser_get_interactive_elements(chat_id="chat1")
        assert len(res) > 500
        assert "[Truncated" in res

@pytest.mark.anyio
async def test_browser_back(mock_playwright, mock_db):
    mock_db.get_chat.return_value = {"browsing_session_id": "s1"}
    mock_playwright.execute_tool.return_value = MagicMock(content=[MagicMock(text='{"status": "back"}')])
    
    res = await browser_back(chat_id="chat1")
    assert res == '{"status": "back"}'

@pytest.mark.anyio
async def test_get_session_id_fail(mock_db):
    mock_db.get_chat.return_value = {} # No browsing_session_id
    from backend.tools.browser import browser_back
    with pytest.raises(ValueError, match="No active browsing session found"):
        await browser_back(chat_id="chat1")

@pytest.mark.anyio
async def test_get_session_id_db_error(mock_db):
    mock_db.get_chat.side_effect = Exception("DB Locked")
    from backend.tools.browser import browser_back
    with pytest.raises(ValueError, match="No active browsing session found"):
        await browser_back(chat_id="chat1")

