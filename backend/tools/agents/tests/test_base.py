# backend/tools/agents/tests/test_base.py
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from backend.tools.agents.base import BaseAgent, AgentConfig

class MockAgent(BaseAgent):
    def get_system_prompt(self, **kwargs):
        return "system_prompt"

    def get_tools(self, iteration, task_list, db_history):
        return [{"function": {"name": "test_tool"}}]

    def format_user_message(self, **kwargs):
        return f"user_message: {kwargs.get('instruction', '')}"

@pytest.fixture
def agent_config():
    return AgentConfig(
        name="mock_agent",
        display_name="Mock Agent",
        max_turns=3,
        failsafe_turns=1,
        max_tokens=100,
        thinking_budget=10,
        require_task_list=True,
        enable_safety_audit=False
    )

@pytest.fixture
def agent_handler():
    handler = MagicMock()
    handler.chat_id = "chat_1"
    handler.parent_message_id = 100
    handler.model = "test-model"
    # mock run_inference_step
    async def mock_inference(**kwargs):
        yield "chunk"
    handler.run_inference_step = mock_inference
    return handler

@pytest.mark.anyio
@patch('backend.tools.agents.base.db')
async def test_base_agent_lifecycle_start(mock_db, agent_handler, agent_config):
    # First run (no history)
    mock_db.get_messages.return_value = []
    mock_db.get_task_list.return_value = None
    
    agent = MockAgent(agent_handler, agent_config)
    
    # We yield from run, so let's iterate
    chunks = []
    async for chunk in agent.run(instruction="do work"):
        chunks.append(chunk)
        
    # Check start event was added
    mock_db.add_message.assert_any_call(
        chat_id="chat_1",
        role="event",
        content="Mock Agent Started.",
        parent_id=100,
        parent_type="mock_agent"
    )

@pytest.mark.anyio
@patch('backend.tools.agents.base.db')
async def test_base_agent_lifecycle_resume(mock_db, agent_handler, agent_config):
    # Resume run (history exists)
    mock_db.get_messages.return_value = [{"role": "event", "content": "Mock Agent Started."}]
    mock_db.get_task_list.return_value = ["task 1"]
    
    # Mock update message so completion returns immediately
    mock_db.get_messages.side_effect = [
        [{"role": "event", "content": "Mock Agent Started."}], # check resume
        [{"role": "event", "content": "Mock Agent Started."}], # rebuild history
        [{"role": "event", "content": "Mock Agent Started."}, {"role": "assistant", "content": "Finished"}] # completion check
    ]
    
    agent = MockAgent(agent_handler, agent_config)
    
    chunks = []
    async for chunk in agent.run(instruction="do work"):
        chunks.append(chunk)
        
    # Start event should NOT be logged again
    assert not any(
        call.kwargs.get("content") == "Mock Agent Started."
        for call in mock_db.add_message.call_args_list
    )

@pytest.mark.anyio
@patch('backend.tools.agents.base.db')
async def test_base_agent_task_list_gating(mock_db, agent_handler, agent_config):
    # Require task list and none exists
    mock_db.get_messages.return_value = []
    mock_db.get_task_list.return_value = None
    
    agent = MockAgent(agent_handler, agent_config)
    
    # Spy on run_inference_step parameters
    inference_spy = AsyncMock(return_value=AsyncMock())
    agent_handler.run_inference_step = inference_spy
    
    # We only run one iteration for the test
    mock_db.get_messages.side_effect = [
        [], # resume check
        [], # rebuild history
        []  # completion check (forces break)
    ]
    
    async for _ in agent.run(instruction="do work"):
        pass
        
    # Verify it used the MANAGE_TASK_LIST_TOOL
    assert inference_spy.called
    call_args = inference_spy.call_args.kwargs
    assert len(call_args["tools"]) == 1
    assert call_args["tools"][0]["function"]["name"] == "manage_task_list"



@pytest.mark.anyio
@patch('backend.tools.agents.base.log_event')
@patch('backend.tools.agents.base.db')
async def test_base_agent_failure_sends_a_fixed_message_and_logs_the_detail(mock_db, mock_log_event, agent_handler, agent_config):
    mock_db.get_messages.return_value = []
    mock_db.get_task_list.return_value = None

    async def boom(**kwargs):
        raise RuntimeError("/secret/path db locked")
        yield

    agent_handler.run_inference_step = boom
    agent = MockAgent(agent_handler, agent_config)
    chunks = [c async for c in agent.run(instruction="do work")]
    assert "Error: Mock Agent failed. Try again." in chunks
    assert agent_handler.result == "Mock Agent failed. Try again."
    mock_db.add_message.assert_any_call(chat_id="chat_1", role="event", content="Mock Agent failed. Try again.", parent_id=100, parent_type="mock_agent")
    assert mock_log_event.call_args.args[0] == "agent_failed_error" and "db locked" in mock_log_event.call_args.args[1]["error"]
    assert "secret" not in "".join(str(c) for c in chunks)


@pytest.mark.anyio
async def test_base_agent_on_error_has_no_exception_text(agent_handler, agent_config):
    agent = MockAgent(agent_handler, agent_config)
    assert await agent.on_error(RuntimeError("/secret/path")) == "Mock Agent failed. Try again."
