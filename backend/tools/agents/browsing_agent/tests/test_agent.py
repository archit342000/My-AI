import pytest
from unittest.mock import AsyncMock, patch, MagicMock, call
import uuid
import json

from backend.tools.agents.browsing_agent.agent import flow_fn
from backend.tools import ToolRegistry, ToolScope
from backend.tools.agents.browsing_agent.prompts import BROWSING_AGENT_SYSTEM_PROMPT_TEXT, BROWSING_AGENT_SYSTEM_PROMPT_VISION

@pytest.fixture
def mock_agent():
    agent = AsyncMock()
    agent.chat_id = "test_chat"
    agent.parent_message_id = "test_parent"
    agent.model = "test-text-model"
    agent.result = None
    
    async def mock_run_inference(*args, **kwargs):
        yield "chunk1"
        yield "chunk2"
    
    agent.run_inference_step = MagicMock(side_effect=mock_run_inference)
    return agent

@pytest.fixture
def mock_config():
    with patch('backend.tools.agents.browsing_agent.agent.config') as mock_conf:
        mock_conf.BROWSER_STEALTH_LEVEL = 1
        mock_conf.BROWSING_AGENT_MAX_TURNS = 3
        mock_conf.BROWSING_AGENT_MAX_TOKENS = 1000
        mock_conf.BROWSING_AGENT_THINKING_BUDGET = 100
        mock_conf.BROWSING_AGENT_FAILSAFE_TURNS = 2
        yield mock_conf

@pytest.fixture
def mock_db():
    with patch('backend.tools.agents.base.db') as db_mock:
        with patch('backend.tools.agents.browsing_agent.agent.db', new=db_mock):
            db_mock.get_chat_owner.return_value = "user-1"  # the chat owner: a regular user by default
            db_mock.get_user.return_value = {"id": "user-1", "role": "user"}
            yield db_mock

@pytest.fixture
def mock_playwright_client():
    with patch('backend.tools.agents.browsing_agent.agent.playwright_client', new_callable=AsyncMock) as client:
        yield client

@pytest.fixture
def mock_load_model_config():
    with patch('backend.models.load_model_config') as load_cfg:
        load_cfg.return_value = {
            "cat1": {"text": "test-text-model", "vision": "test-vision-model"}
        }
        yield load_cfg


@pytest.mark.anyio
async def test_flow_fn_first_run_text_model(mock_agent, mock_config, mock_db, mock_playwright_client, mock_load_model_config):
    # Setup
    mock_db.get_messages.side_effect = [
        [], # 1. initial is_resume check
        [], # 2. iteration 1 history check
        [{"role": "assistant"}] # 3. post-inference check
    ]
    mock_db.get_chat.return_value = {"browsing_session_id": "sess_123"}
    mock_db.get_task_list.return_value = [{"id": "task1"}]

    # Run
    chunks = [chunk async for chunk in flow_fn(mock_agent, "browsing_agent", "search python")]

    # Assertions
    assert chunks == ["chunk1", "chunk2"]
    
    # Event emitted
    mock_db.add_message.assert_any_call(
        chat_id="test_chat", role='event', content='Browsing Agent Started.',
        parent_id="test_parent", parent_type='browsing_agent'
    )
    
    # Session started
    assert mock_playwright_client.connect.called
    mock_playwright_client.execute_tool.assert_any_call("browser_start_session", {
        "session_id": mock_playwright_client.execute_tool.call_args_list[0][0][1]["session_id"],
        "profile_id": "user-1",
        "attach_portal": False,
        "stealth_level": 1,
        "scope": None
    })
    
    # Check that cleanup was called
    mock_playwright_client.execute_tool.assert_any_call("browser_end_session", {"session_id": "sess_123"})
    
    # Check if run_inference_step was called with BASE tools
    args, kwargs = mock_agent.run_inference_step.call_args
    assert kwargs["tools"] == ToolRegistry.get_tools_for_scope(ToolScope.BROWSING_BASE)
    assert kwargs["model_name"] == "test-text-model"
    
    assert mock_agent.result == "Browsing Agent completed."


@pytest.mark.anyio
async def test_flow_fn_first_run_vision_model(mock_agent, mock_config, mock_db, mock_playwright_client, mock_load_model_config):
    # Setup
    mock_agent.model = "test-vision-model"
    
    mock_db.get_messages.side_effect = [
        [], 
        [
            {"role": "tool", "name": "browser_screenshot", "content": "base64_1"},
            {"role": "tool", "name": "browser_screenshot", "content": "base64_2"},
        ],
        [{"role": "assistant"}]
    ]
    mock_db.get_chat.return_value = {"browsing_session_id": "sess_123"}
    mock_db.get_task_list.return_value = [{"id": "task1"}]

    # Run
    chunks = [chunk async for chunk in flow_fn(mock_agent, "browsing_agent", "search python")]

    # Assertions
    args, kwargs = mock_agent.run_inference_step.call_args
    assert kwargs["tools"] == ToolRegistry.get_tools_for_scope(ToolScope.BROWSING_VISION)
    assert kwargs["model_name"] == "test-vision-model"
    
    # Check screenshot pruning
    messages = kwargs["messages"]
    system_prompt = messages[0]["content"]
    assert "Vision Mode: ENABLED" in system_prompt
    
    # We injected two screenshots in history. Pruning means the first one becomes "[Previous screenshot omitted...]"
    history_msgs = messages[2:]
    assert history_msgs[0]["content"] == [{"type": "text", "text": "[Previous screenshot omitted to save context]"}]
    assert history_msgs[1]["content"] == "base64_2" # latest is kept


@pytest.mark.anyio
async def test_flow_fn_with_scope_and_criteria(mock_agent, mock_config, mock_db, mock_playwright_client, mock_load_model_config):
    mock_db.get_messages.side_effect = [
        [],
        [],
        [{"role": "assistant"}]
    ]
    mock_db.get_chat.return_value = {"browsing_session_id": "sess_123"}
    mock_db.get_task_list.return_value = [{"id": "task1"}]

    chunks = [chunk async for chunk in flow_fn(
        mock_agent, "browsing_agent", "search", 
        scope=["github.com", "python.org"], 
        success_criteria="Find code", 
        start_url="https://github.com"
    )]
    
    args, kwargs = mock_agent.run_inference_step.call_args
    system_prompt = kwargs["messages"][0]["content"]
    assert "SUCCESS CRITERIA" in system_prompt
    assert "Find code" in system_prompt
    assert "STARTING URL" in system_prompt
    assert "https://github.com" in system_prompt
    assert "SCOPE RESTRICTION" in system_prompt
    assert "github.com, python.org" in system_prompt
    
    # Check that update session with scope was called
    mock_playwright_client.execute_tool.assert_any_call("browser_start_session", {
        "session_id": "sess_123",
        "profile_id": "user-1",
        "attach_portal": False,
        "stealth_level": 1,
        "scope": ["github.com", "python.org"]
    })


@pytest.mark.anyio
async def test_flow_fn_resume_run(mock_agent, mock_config, mock_db, mock_playwright_client, mock_load_model_config):
    mock_db.get_messages.side_effect = [
        [{"role": "user", "content": "prev"}], # is_resume check -> True
        [{"role": "user", "content": "prev"}], # history build
        [{"role": "assistant"}] # completion
    ]
    mock_db.get_chat.return_value = {"browsing_session_id": "sess_resume_123"}
    mock_db.get_task_list.return_value = [{"id": "task1"}]

    chunks = [chunk async for chunk in flow_fn(mock_agent, "browsing_agent", "search")]
    
    # Event shouldn't be added for resume
    assert not any("Browsing Agent Started" in str(call) for call in mock_db.add_message.mock_calls)
    
    # Session resumed
    mock_playwright_client.execute_tool.assert_any_call("browser_start_session", {
        "session_id": "sess_resume_123",
        "profile_id": "user-1",
        "attach_portal": False,
        "stealth_level": 1,
        "scope": None
    })


@pytest.mark.anyio
async def test_flow_fn_no_task_list(mock_agent, mock_config, mock_db, mock_playwright_client, mock_load_model_config):
    mock_db.get_messages.side_effect = [
        [],
        [],
        [{"role": "assistant", "content": "", "tool_calls": [{"name": "manage_task_list"}]}], # not completion, another turn
        [{"role": "assistant", "content": ""}], # completion
        [{"role": "assistant", "content": ""}], # safe termination
    ]
    mock_db.get_chat.return_value = {"browsing_session_id": "sess_123"}
    # Return empty list first, then populated list
    mock_db.get_task_list.side_effect = [[], [{"id": "t1"}], [{"id": "t1"}], [{"id": "t1"}], [{"id": "t1"}]]

    chunks = [chunk async for chunk in flow_fn(mock_agent, "browsing_agent", "search")]
    
    # Check that tools was restricted to MANAGE_TASK_LIST_TOOL on first call
    args, kwargs = mock_agent.run_inference_step.call_args_list[0]
    assert kwargs["tools"] == [ToolRegistry.get_spec("manage_task_list").to_openai_schema()]


@pytest.mark.anyio
async def test_flow_fn_fails_to_init_task_list(mock_agent, mock_config, mock_db, mock_playwright_client, mock_load_model_config):
    mock_db.get_messages.side_effect = [
        [],
        [],
        [{"role": "assistant", "content": ""}], # post-inference, still no task list
        [], # force break by returning empty history
        [], [], [], [] # padding to avoid StopIteration
    ]
    mock_db.get_chat.return_value = {"browsing_session_id": "sess_123"}
    mock_db.get_task_list.return_value = [] # always empty

    chunks = [chunk async for chunk in flow_fn(mock_agent, "browsing_agent", "search")]
    
    # System Constraint message added
    mock_db.add_message.assert_any_call(
        chat_id="test_chat", role='user',
        content='System Constraint: You MUST initialize your task list using manage_task_list before taking ANY other actions or responding.',
        parent_id="test_parent", parent_type='browsing_agent'
    )


@pytest.mark.anyio
async def test_flow_fn_turn_limit_reached(mock_agent, mock_config, mock_db, mock_playwright_client, mock_load_model_config):
    # Setup history with 3 browsing turns (limit is 3)
    history_at_limit = [
        {"role": "tool", "name": "browser_click", "content": ""},
        {"role": "tool", "name": "browser_click", "content": ""},
        {"role": "tool", "name": "browser_click", "content": ""},
    ]
    
    history_after_warn = history_at_limit + [{"role": "user", "content": "TURN LIMIT REACHED"}]
    
    mock_db.get_messages.side_effect = [
        [], # is_resume
        history_at_limit, # loop 1: detects limit, injects warning, continues
        history_after_warn, # loop 2: warns already injected, runs inference with NO tools
        [{"role": "assistant", "content": ""}], # loop 2 post inference: completes
        [], [] # padding
    ]
    mock_db.get_chat.return_value = {"browsing_session_id": "sess_123"}
    mock_db.get_task_list.return_value = [{"id": "t1"}]

    chunks = [chunk async for chunk in flow_fn(mock_agent, "browsing_agent", "search")]
    
    # Warning injected
    mock_db.add_message.assert_any_call(
        chat_id="test_chat", role='user',
        content='[SYSTEM: TURN LIMIT REACHED] You have exhausted your allowed operations. Summarize your findings immediately. Do not attempt any further actions.',
        parent_id="test_parent", parent_type='browsing_agent'
    )
    
    # Run inference with NO tools on loop 2 (active_tools becomes [] / None)
    args, kwargs = mock_agent.run_inference_step.call_args
    assert kwargs["tools"] == [] or kwargs["tools"] is None


@pytest.mark.anyio
async def test_flow_fn_infinite_loop_failsafe(mock_agent, mock_config, mock_db, mock_playwright_client, mock_load_model_config):
    # Simulate an infinite loop where it never returns just assistant role
    # Max turns = 3, Failsafe = 2, total iterations = 5
    
    mock_db.get_messages.return_value = [{"role": "assistant", "content": "", "tool_calls": [{"name": "fake"}]}]
    mock_db.get_chat.return_value = {"browsing_session_id": "sess_123"}
    mock_db.get_task_list.return_value = [{"id": "t1"}]
    
    chunks = [chunk async for chunk in flow_fn(mock_agent, "browsing_agent", "search")]
    
    # Assert force terminated
    mock_db.add_message.assert_any_call(
        chat_id="test_chat", role='event',
        content='Browsing Agent Force Terminated. (infinite loop prevention)',
        parent_id="test_parent", parent_type='browsing_agent'
    )
    assert mock_agent.result == "Operation forcibly terminated due to infinite loop."


@pytest.mark.anyio
async def test_flow_fn_cleanup_error(mock_agent, mock_config, mock_db, mock_playwright_client, mock_load_model_config):
    mock_db.get_messages.side_effect = [
        [],
        [],
        [{"role": "assistant", "content": ""}]
    ]
    mock_db.get_chat.return_value = {"browsing_session_id": "sess_123"}
    mock_db.get_task_list.return_value = [{"id": "task1"}]
    
    async def mock_execute(name, params):
        if name == "browser_end_session":
            raise Exception("Test cleanup error")
    mock_playwright_client.execute_tool.side_effect = mock_execute

    chunks = [chunk async for chunk in flow_fn(mock_agent, "browsing_agent", "search")]
    
    # It shouldn't crash
    assert mock_db.update_chat.call_args_list[-1] == call("test_chat", browsing_session_id=None)

@pytest.mark.anyio
async def test_flow_fn_text_model_screenshot_pruning(mock_agent, mock_config, mock_db, mock_playwright_client, mock_load_model_config):
    mock_agent.model = "test-text-model"
    
    mock_db.get_messages.side_effect = [
        [], 
        [
            {"role": "tool", "name": "browser_screenshot", "content": "base64_1"},
        ],
        [{"role": "assistant"}]
    ]
    mock_db.get_chat.return_value = {"browsing_session_id": "sess_123"}
    mock_db.get_task_list.return_value = [{"id": "task1"}]

    chunks = [chunk async for chunk in flow_fn(mock_agent, "browsing_agent", "search python")]

    args, kwargs = mock_agent.run_inference_step.call_args
    history_msgs = kwargs["messages"][2:]
    assert history_msgs[0]["content"] == [{"type": "text", "text": "[Screenshot captured. Use browser_read_page and browser_get_interactive_elements to understand the page.]"}]

@pytest.mark.anyio
async def test_flow_fn_resume_missing_session_id(mock_agent, mock_config, mock_db, mock_playwright_client, mock_load_model_config):
    mock_db.get_messages.side_effect = [
        [{"role": "user", "content": "prev"}], # is_resume check -> True
        [{"role": "user", "content": "prev"}], # history build
        [{"role": "assistant"}] # completion
    ]
    # Simulate DB having None for browsing_session_id
    mock_db.get_chat.return_value = {"browsing_session_id": None}
    mock_db.get_task_list.return_value = [{"id": "task1"}]

    chunks = [chunk async for chunk in flow_fn(mock_agent, "browsing_agent", "search")]
    
    # Verify that a new session_id was generated and stored in DB
    mock_db.update_chat.assert_any_call("test_chat", browsing_session_id=mock_playwright_client.execute_tool.call_args_list[0][0][1]["session_id"])
    
    # And start session was called with this new session_id
    mock_playwright_client.execute_tool.assert_any_call("browser_start_session", {
        "session_id": mock_playwright_client.execute_tool.call_args_list[0][0][1]["session_id"],
        "profile_id": "user-1",
        "attach_portal": False,
        "stealth_level": 1,
        "scope": None
    })

@pytest.mark.anyio
async def test_flow_fn_playwright_connection_failure(mock_agent, mock_config, mock_db, mock_playwright_client, mock_load_model_config):
    mock_db.get_messages.side_effect = [
        [], # is_resume check -> False
    ]
    mock_db.get_chat.return_value = {"browsing_session_id": None}
    
    # Mock playwright connection raising an error
    mock_playwright_client.connect.side_effect = Exception("Connection refused")
    
    chunks = [chunk async for chunk in flow_fn(mock_agent, "browsing_agent", "search")]
    
    # Verify we yielded the error message
    assert len(chunks) == 1
    assert "Failed to connect to browser session" in chunks[0]
    
    # Verify database event message was added
    mock_db.add_message.assert_any_call(
        chat_id="test_chat",
        role='event',
        content='Browsing Agent failed: Connection refused',
        parent_id="test_parent",
        parent_type='browsing_agent'
    )
    
    # Verify database session ID was cleaned up
    mock_db.update_chat.assert_any_call("test_chat", browsing_session_id=None)

@pytest.mark.anyio
async def test_flow_fn_execution_error(mock_agent, mock_config, mock_db, mock_playwright_client, mock_load_model_config):
    mock_db.get_messages.side_effect = [
        [], # is_resume check -> False
        [], # history build
    ]
    mock_db.get_chat.return_value = {"browsing_session_id": "sess_123"}
    mock_db.get_task_list.return_value = [{"id": "task1"}]
    
    # Mock run_inference_step to raise an exception
    mock_agent.run_inference_step.side_effect = Exception("Inference timeout")
    
    chunks = [chunk async for chunk in flow_fn(mock_agent, "browsing_agent", "search")]
    
    # Verify we yielded the error message
    assert len(chunks) == 1
    assert "Browsing agent failed during execution" in chunks[0]
    
    # Verify database event message was added
    mock_db.add_message.assert_any_call(
        chat_id="test_chat",
        role='event',
        content='Browsing Agent failed: Inference timeout',
        parent_id="test_parent",
        parent_type='browsing_agent'
    )
    
    # Verify browser_end_session was still called in finally block
    mock_playwright_client.execute_tool.assert_any_call("browser_end_session", {"session_id": "sess_123"})


@pytest.mark.anyio
@pytest.mark.parametrize("role,attach", [("user", False), ("admin", True)])
async def test_the_profile_comes_from_the_chat_owner_and_only_an_admin_attaches_to_the_portal(
        role, attach, mock_agent, mock_config, mock_db, mock_playwright_client, mock_load_model_config):
    mock_db.get_chat_owner.return_value = "owner-9"
    mock_db.get_user.return_value = {"id": "owner-9", "role": role}
    mock_db.get_messages.side_effect = [[], [], [{"role": "assistant"}]]
    mock_db.get_chat.return_value = {"browsing_session_id": "sess_1"}
    mock_db.get_task_list.return_value = [{"id": "task1"}]
    [chunk async for chunk in flow_fn(mock_agent, "browsing_agent", "search")]
    starts = [c.args[1] for c in mock_playwright_client.execute_tool.call_args_list if c.args[0] == "browser_start_session"]
    assert starts and all(a["profile_id"] == "owner-9" and a["attach_portal"] is attach for a in starts)


def _agent(chat_id="test_chat"):
    from backend.tools.agents.browsing_agent.agent import BrowsingAgent
    agent = BrowsingAgent.__new__(BrowsingAgent)
    agent.chat_id = chat_id
    return agent


@pytest.mark.anyio
async def test_a_chat_without_an_owner_starts_no_browser_session(mock_db, mock_playwright_client):
    mock_db.get_chat_owner.return_value = None
    with pytest.raises(RuntimeError, match="has no owner"):
        await _agent().on_start()
    assert not mock_playwright_client.execute_tool.called
    mock_db.update_chat.assert_any_call("test_chat", browsing_session_id=None)  # the half-started session is reset


@pytest.mark.anyio
async def test_a_resumed_chat_without_an_owner_starts_no_browser_session(mock_db, mock_playwright_client):
    mock_db.get_chat_owner.return_value = None
    mock_db.get_chat.return_value = {"browsing_session_id": "sess_1"}
    with pytest.raises(RuntimeError, match="has no owner"):
        await _agent().on_resume()
    assert not mock_playwright_client.execute_tool.called


@pytest.mark.anyio
@pytest.mark.parametrize("hook", ["on_start", "on_resume"])
async def test_a_start_error_from_the_playwright_server_fails_the_run(hook, mock_db, mock_playwright_client):
    mock_db.get_chat_owner.return_value = "owner-9"
    mock_db.get_user.return_value = {"id": "owner-9", "role": "user"}
    mock_db.get_chat.return_value = {"browsing_session_id": "sess_1"}
    result = MagicMock()
    result.content = [MagicMock(text=json.dumps({"error": "Invalid profile_id"}))]
    mock_playwright_client.execute_tool.return_value = result
    with pytest.raises(RuntimeError, match="Invalid profile_id"):
        await getattr(_agent(), hook)()


@pytest.mark.anyio
async def test_a_successful_start_result_is_accepted(mock_db, mock_playwright_client):
    mock_db.get_chat_owner.return_value = "owner-9"
    mock_db.get_user.return_value = {"id": "owner-9", "role": "user"}
    mock_db.get_chat.return_value = {"browsing_session_id": "sess_1"}
    result = MagicMock()
    result.content = [MagicMock(text=json.dumps({"status": "started"}))]
    mock_playwright_client.execute_tool.return_value = result
    await _agent().on_start()



@pytest.mark.anyio
async def test_a_tool_level_error_from_the_playwright_server_fails_the_run(mock_db, mock_playwright_client):
    mock_db.get_chat_owner.return_value = "owner-9"
    mock_db.get_user.return_value = {"id": "owner-9", "role": "user"}
    mock_db.get_chat.return_value = {"browsing_session_id": "sess_1"}
    result = MagicMock()
    result.isError = True
    result.content = [MagicMock(text="launch failed")]
    mock_playwright_client.execute_tool.return_value = result
    with pytest.raises(RuntimeError, match="launch failed"):
        await _agent().on_start()
