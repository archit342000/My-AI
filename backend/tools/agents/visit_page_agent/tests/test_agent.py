import pytest
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from backend.tools.agents.visit_page_agent.agent import flow_fn

@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.chat_id = "test_chat"
    agent.parent_message_id = 123
    agent.model = "test-model"
    
    # Correctly mock an async generator
    def mock_inference(*args, **kwargs):
        async def gen():
            yield "Synthesized reading"
        return gen()
        
    agent.run_inference_step = MagicMock(side_effect=mock_inference)
    return agent

@pytest.fixture
def mock_playwright():
    with patch('backend.tools.agents.visit_page_agent.agent.playwright_client') as mock:
        mock.connect = AsyncMock()
        mock.execute_tool = AsyncMock()
        yield mock

@pytest.fixture
def mock_db():
    with patch('backend.tools.agents.visit_page_agent.agent.db') as mock:
        yield mock

@pytest.fixture
def mock_config():
    with patch('backend.tools.agents.visit_page_agent.agent.config') as mock:
        mock.MAX_CHARS_VISIT_PAGE = 10000
        mock.VISIT_PAGE_AGENT_MAX_TOKENS = 1000
        mock.VISIT_PAGE_AGENT_THINKING_BUDGET = 500
        yield mock

@pytest.mark.anyio
async def test_visit_page_raw_content(mock_agent, mock_playwright, mock_db, mock_config):
    mock_res = MagicMock()
    mock_res.content = [MagicMock(text="Raw Page Content")]
    mock_playwright.execute_tool.return_value = mock_res
    
    gen = flow_fn(mock_agent, "visit_page", "http://example.com", detail_level="high")
    chunks = [c async for c in gen]
    
    assert "Raw Page Content" in chunks
    assert mock_agent.result == "Raw Page Content"
    assert mock_agent.run_inference_step.called is False
    
    # Verify arguments
    args, kwargs = mock_playwright.execute_tool.call_args
    assert args[0] == "visit_page_tool"
    assert args[1]["url"] == "http://example.com"
    assert args[1]["detail_level"] == "high"
    assert args[1]["max_chars"] == 10000

@pytest.mark.anyio
async def test_visit_page_synthesis(mock_agent, mock_playwright, mock_db, mock_config):
    mock_res = MagicMock()
    mock_res.content = [MagicMock(text="Some text about cats.")]
    mock_playwright.execute_tool.return_value = mock_res
    
    # Mock DB history
    mock_db.get_messages.return_value = [{"role": "assistant", "content": "Synthesized reading"}]
    
    gen = flow_fn(mock_agent, "visit_page", "http://example.com", query="What about cats?")
    chunks = [c async for c in gen]
    
    assert "Synthesized reading" in chunks
    assert mock_agent.result == "Synthesized reading"
    assert mock_agent.run_inference_step.called is True
    
    # Verify prompt contains content
    args, kwargs = mock_agent.run_inference_step.call_args
    assert "Some text about cats." in kwargs["messages"][1]["content"]

@pytest.mark.anyio
async def test_visit_page_tool_error(mock_agent, mock_playwright, mock_db, mock_config):
    mock_res = MagicMock()
    mock_res.content = [MagicMock(text="Error: Connection refused")]
    mock_playwright.execute_tool.return_value = mock_res
    
    gen = flow_fn(mock_agent, "visit_page", "http://example.com")
    chunks = [c async for c in gen]
    
    assert "Error: Connection refused" in chunks
    assert mock_agent.result == "Error: Connection refused"

@pytest.mark.anyio
async def test_visit_page_empty_content(mock_agent, mock_playwright, mock_db, mock_config):
    mock_res = MagicMock()
    mock_res.content = [MagicMock(text="")]
    mock_playwright.execute_tool.return_value = mock_res
    
    gen = flow_fn(mock_agent, "visit_page", "http://example.com")
    chunks = [c async for c in gen]
    
    assert "Unknown error extracting content." in chunks[0]

@pytest.mark.anyio
async def test_visit_page_exception(mock_agent, mock_playwright, mock_db, mock_config):
    mock_playwright.execute_tool.side_effect = Exception("Crash")
    
    gen = flow_fn(mock_agent, "visit_page", "http://example.com")
    chunks = [c async for c in gen]
    
    assert "Visit page failed. Try again." in chunks[0]
    assert mock_agent.result == "Visit page failed. Try again."
    assert "Crash" not in mock_agent.result

@pytest.mark.anyio
async def test_visit_page_synthesis_failure(mock_agent, mock_playwright, mock_db, mock_config):
    mock_res = MagicMock()
    mock_res.content = [MagicMock(text="Valid content")]
    mock_playwright.execute_tool.return_value = mock_res
    
    mock_agent.run_inference_step.side_effect = Exception("Synthesis failed")
    
    gen = flow_fn(mock_agent, "visit_page", "http://example.com", query="query")
    chunks = [c async for c in gen]
    
    assert "Visit page failed. Try again." in chunks[0]

@pytest.mark.anyio
async def test_visit_page_startup_exception(mock_agent, mock_playwright, mock_db, mock_config):
    mock_db.get_messages.side_effect = Exception("DB Connection Error")
    
    gen = flow_fn(mock_agent, "visit_page", "http://example.com")
    chunks = [c async for c in gen]
    
    assert "Visit page failed. Try again." in chunks[0]
    assert mock_agent.result == "Visit page failed. Try again."
    
    # Check that it tried to log the failure event to the database
    mock_db.add_message.assert_called_once_with(
        chat_id=mock_agent.chat_id,
        role='event',
        content='Visit Page Agent Failed.',
        parent_id=mock_agent.parent_message_id,
        parent_type='visit_page'
    )


@pytest.mark.anyio
async def test_a_visit_failure_logs_the_detail_and_shows_none_of_it(mock_agent, mock_playwright, mock_db, mock_config):
    mock_playwright.execute_tool.side_effect = RuntimeError("/secret/place crashed")
    with patch('backend.tools.agents.visit_page_agent.agent.log_event') as events:
        chunks = [c async for c in flow_fn(mock_agent, "visit_page", "https://p.example")]
    assert chunks == ["Visit page failed. Try again."] and "secret" not in str(mock_agent.result)
    assert events.call_args.args[0] == "visit_page_agent_error" and "crashed" in events.call_args.args[1]["error"]
