import pytest
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from backend.tools.agents.search_web_agent.agent import flow_fn

@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.chat_id = "test_chat"
    agent.parent_message_id = 123
    agent.model = "test-model"
    
    # Correctly mock an async generator
    def mock_inference(*args, **kwargs):
        async def gen():
            yield "Synthesized answer"
        return gen()
        
    agent.run_inference_step = MagicMock(side_effect=mock_inference)
    return agent

@pytest.fixture(autouse=True)
def search_limit():
    """The per-user search limit check (the test chats have no owner); allowed unless a test says otherwise."""
    with patch('backend.tools.agents.search_web_agent.agent.check_search_limit', return_value=None) as check:
        yield check


@pytest.fixture
def mock_tavily():
    with patch('backend.tools.agents.search_web_agent.agent.tavily_client') as mock:
        mock.connect = AsyncMock()
        mock.execute_tool = AsyncMock()
        yield mock

@pytest.fixture
def mock_db():
    with patch('backend.tools.agents.search_web_agent.agent.db') as mock:
        yield mock

@pytest.fixture
def mock_config():
    with patch('backend.tools.agents.search_web_agent.agent.config') as mock:
        mock.MAX_SEARCH_RESULTS = 5
        mock.TIMEOUT_TAVILY_SEARCH_ASYNC = 10
        mock.SEARCH_WEB_AGENT_MAX_CHARS_PER_RESULT = 15000
        mock.SEARCH_WEB_AGENT_MAX_TOKENS = 1000
        mock.SEARCH_WEB_AGENT_THINKING_BUDGET = 500
        yield mock

@pytest.mark.anyio
async def test_search_web_normal_depth_with_answer(mock_agent, mock_tavily, mock_db, mock_config):
    # Mock Tavily returning a native answer
    mock_res = MagicMock()
    mock_res.content = [MagicMock(text=json.dumps({
        "answer": "Tavily Answer",
        "results": [{"url": "url1", "title": "T1", "content": "C1"}]
    }))]
    mock_tavily.execute_tool.return_value = mock_res
    
    gen = flow_fn(mock_agent, "search_web", "query", depth="normal")
    chunks = [c async for c in gen]
    
    assert "Tavily Answer" in chunks
    assert mock_agent.result == "Tavily Answer"
    mock_tavily.execute_tool.assert_called_once()

@pytest.mark.anyio
async def test_search_web_normal_depth_no_answer(mock_agent, mock_tavily, mock_db, mock_config):
    # Mock Tavily returning only results
    mock_res = MagicMock()
    mock_res.content = [MagicMock(text=json.dumps({
        "results": [{"url": "url1", "title": "T1", "content": "C1"}]
    }))]
    mock_tavily.execute_tool.return_value = mock_res
    
    gen = flow_fn(mock_agent, "search_web", "query", depth="normal")
    chunks = [c async for c in gen]
    
    assert "Title: T1" in chunks[0]
    assert "URL: url1" in chunks[0]
    assert "C1" in chunks[0]
    assert mock_agent.result == chunks[0]

@pytest.mark.anyio
async def test_search_web_advanced_depth_synthesis(mock_agent, mock_tavily, mock_db, mock_config):
    # Mock Tavily search
    mock_res = MagicMock()
    mock_res.content = [MagicMock(text=json.dumps({
        "results": [{"url": "url1", "title": "T1", "content": "C1", "raw_content": "Raw C1"}]
    }))]
    mock_tavily.execute_tool.return_value = mock_res
    
    # Mock DB history for agent.result update
    mock_db.get_messages.return_value = [{"role": "assistant", "content": "Synthesized answer"}]
    
    gen = flow_fn(mock_agent, "search_web", "query", depth="advanced")
    chunks = [c async for c in gen]
    
    # Synthesis should have been called
    assert "Synthesized answer" in chunks
    assert mock_agent.result == "Synthesized answer"
    assert mock_agent.run_inference_step.called is True
    # Verify raw_content was used in the prompt
    args, kwargs = mock_agent.run_inference_step.call_args
    assert "Raw C1" in kwargs["messages"][1]["content"]

@pytest.mark.anyio
async def test_search_web_raw_results(mock_agent, mock_tavily, mock_db, mock_config):
    mock_res = MagicMock()
    mock_res.content = [MagicMock(text=json.dumps({
        "results": [{"url": "url1", "content": "Snippet 1"}]
    }))]
    mock_tavily.execute_tool.return_value = mock_res
    
    gen = flow_fn(mock_agent, "search_web", "query", return_raw_results=True)
    chunks = [c async for c in gen]
    
    assert "Snippet 1" in chunks[0]
    assert "url1" in chunks[0]
    assert mock_agent.run_inference_step.called is False

@pytest.mark.anyio
async def test_search_web_retry_success(mock_agent, mock_tavily, mock_db, mock_config):
    # Fail first, succeed second
    mock_res = MagicMock()
    mock_res.content = [MagicMock(text=json.dumps({"answer": "Finally"}))]
    mock_tavily.execute_tool.side_effect = [Exception("Transient error"), mock_res]
    
    with patch('asyncio.sleep', AsyncMock()): # skip waiting
        gen = flow_fn(mock_agent, "search_web", "query", depth="normal")
        chunks = [c async for c in gen]
        
        assert "Finally" in chunks
        assert mock_tavily.execute_tool.call_count == 2

@pytest.mark.anyio
async def test_search_web_fatal_failure(mock_agent, mock_tavily, mock_db, mock_config):
    # Always fail
    mock_tavily.execute_tool.side_effect = Exception("Fatal error")
    
    with patch('asyncio.sleep', AsyncMock()):
        gen = flow_fn(mock_agent, "search_web", "query")
        chunks = [c async for c in gen]
        
        assert "Search failed after 3 attempts" in chunks[0]
        assert "Fatal error" not in chunks[0]
        assert mock_agent.result == chunks[0]
        assert mock_tavily.execute_tool.call_count == 3

@pytest.mark.anyio
async def test_search_web_no_results(mock_agent, mock_tavily, mock_db, mock_config):
    mock_res = MagicMock()
    mock_res.content = [MagicMock(text=json.dumps({"results": []}))]
    mock_tavily.execute_tool.return_value = mock_res
    
    gen = flow_fn(mock_agent, "search_web", "query")
    chunks = [c async for c in gen]
    
    assert "No results found" in chunks[0]
    assert mock_agent.result == "No results found for this query."

@pytest.mark.anyio
async def test_search_web_news_and_time(mock_agent, mock_tavily, mock_db, mock_config):
    mock_res = MagicMock()
    mock_res.content = [MagicMock(text=json.dumps({"answer": "News Answer"}))]
    mock_tavily.execute_tool.return_value = mock_res
    
    gen = flow_fn(mock_agent, "search_web", "query", topic="news", time_range="day", depth="normal")
    chunks = [c async for c in gen]
    
    assert "News Answer" in chunks
    args, kwargs = mock_tavily.execute_tool.call_args
    assert args[1]["topic"] == "news"
    assert args[1]["time_range"] == "day"

@pytest.mark.anyio
async def test_search_web_timeout(mock_agent, mock_tavily, mock_db, mock_config):
    # Mock timeout
    mock_tavily.execute_tool.side_effect = asyncio.TimeoutError()
    
    with patch('asyncio.sleep', AsyncMock()):
        gen = flow_fn(mock_agent, "search_web", "query")
        chunks = [c async for c in gen]
        
        assert "Search failed after 3 attempts" in chunks[0]

@pytest.mark.anyio
async def test_search_web_synthesis_failure(mock_agent, mock_tavily, mock_db, mock_config):
    mock_res = MagicMock()
    mock_res.content = [MagicMock(text=json.dumps({"results": [{"url": "u1", "content": "c1"}]}))]
    mock_tavily.execute_tool.return_value = mock_res
    
    # Fail during synthesis
    mock_agent.run_inference_step.side_effect = Exception("Synthesis failed")
    
    gen = flow_fn(mock_agent, "search_web", "query", depth="advanced")
    chunks = [c async for c in gen]
    
    assert "Search failed. Try again or rephrase the request." in chunks[0]
    assert "Synthesis failed" not in chunks[0]

@pytest.mark.anyio
async def test_search_web_initialization_failure(mock_agent, mock_tavily, mock_db, mock_config):
    mock_db.get_messages.side_effect = Exception("DB connection down")
    
    gen = flow_fn(mock_agent, "search_web", "query")
    chunks = [c async for c in gen]
    
    assert len(chunks) == 1
    assert "Search failed. Try again or rephrase the request." in chunks[0]
    assert mock_agent.result == "Search failed. Try again or rephrase the request."
    assert "DB connection down" not in mock_agent.result
    
    mock_db.add_message.assert_any_call(
        chat_id="test_chat",
        role='event',
        content='Search Web Agent Failed.',
        parent_id=123,
        parent_type='search_web'
    )

@pytest.mark.anyio
async def test_search_web_raw_results_truncation(mock_agent, mock_tavily, mock_db, mock_config):
    # Mock config to have a very small per result limit
    mock_config.SEARCH_WEB_AGENT_MAX_CHARS_PER_RESULT = 10
    
    mock_res = MagicMock()
    mock_res.content = [MagicMock(text=json.dumps({
        "results": [
            {"url": "url1", "content": "This is a very long snippet that exceeds ten characters"},
            {"url": "url2", "content": "Short"}
        ]
    }))]
    mock_tavily.execute_tool.return_value = mock_res
    
    gen = flow_fn(mock_agent, "search_web", "query", return_raw_results=True)
    chunks = [c async for c in gen]
    
    # Verify first result (long) is truncated
    assert "This is a " in chunks[0]
    assert "[... Content truncated due to length ...]" in chunks[0]
    assert "exceeds" not in chunks[0]
    
    # Verify second result (short) is NOT truncated and stays intact
    assert "Short" in chunks[0]
    assert "Short\n[... Content truncated due to length ...]" not in chunks[0]


@pytest.mark.anyio
async def test_search_web_stops_with_the_limit_message_and_never_calls_tavily(mock_agent, mock_tavily, mock_db, mock_config, search_limit):
    search_limit.return_value = "Error: Daily web search limit reached."
    chunks = [c async for c in flow_fn(mock_agent, "search_web", "q")]
    assert chunks == ["Error: Daily web search limit reached."]
    assert mock_agent.result == "Error: Daily web search limit reached."
    mock_tavily.execute_tool.assert_not_called()
    mock_tavily.connect.assert_not_called()
    search_limit.assert_called_once_with("test_chat")
    contents = [c.kwargs.get("content") for c in mock_db.add_message.call_args_list]
    assert "Search Web Agent Started." in contents and "Search Web Agent Failed." in contents


@pytest.mark.anyio
async def test_a_search_that_needs_retries_counts_as_one_hit(mock_agent, mock_tavily, mock_db, mock_config, search_limit):
    good = MagicMock()
    good.content = [MagicMock(text=json.dumps({"answer": "ok", "results": [{"title": "t", "url": "u", "content": "c"}]}))]
    mock_tavily.execute_tool.side_effect = [Exception("boom"), Exception("boom"), good]
    with patch('backend.tools.agents.search_web_agent.agent.asyncio.sleep', new_callable=AsyncMock):
        [c async for c in flow_fn(mock_agent, "search_web", "q")]
    assert mock_tavily.execute_tool.call_count == 3
    assert search_limit.call_count == 1



@pytest.mark.anyio
async def test_search_failures_log_the_detail_and_show_none_of_it(mock_agent, mock_tavily, mock_db, mock_config):
    mock_tavily.execute_tool.side_effect = RuntimeError("/secret/place tavily down")
    with patch('backend.tools.agents.search_web_agent.agent.asyncio.sleep', new_callable=AsyncMock), \
         patch('backend.tools.agents.search_web_agent.agent.log_event') as events:
        chunks = [c async for c in flow_fn(mock_agent, "search_web", "query")]
    assert chunks == ["Search failed after 3 attempts. Try again or rephrase the request."]
    assert "secret" not in str(mock_agent.result)
    assert events.call_args.args[0] == "search_web_agent_error" and "tavily down" in events.call_args.args[1]["error"] and events.call_args.args[1]["attempts"] == 3
