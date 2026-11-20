import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from backend.tools.agents.file_system_agent.agent import flow_fn
from backend.tools import ToolRegistry, ToolScope

@pytest.fixture
def mock_agent():
    agent = AsyncMock()
    agent.chat_id = "test_chat"
    agent.parent_message_id = "test_parent"
    agent.model = "test-model"
    agent.result = None
    
    async def mock_run_inference(*args, **kwargs):
        yield "chunk1"
        yield "chunk2"
    
    agent.run_inference_step = MagicMock(side_effect=mock_run_inference)
    return agent

@pytest.fixture
def mock_config():
    with patch('backend.tools.agents.file_system_agent.agent.config') as mock_conf:
        mock_conf.FILE_SYSTEM_AGENT_MAX_TURNS = 3
        mock_conf.FILE_SYSTEM_AGENT_FAILSAFE_TURNS = 2
        mock_conf.FILE_SYSTEM_AGENT_MAX_TOKENS = 1000
        mock_conf.FILE_SYSTEM_AGENT_THINKING_BUDGET = 100
        yield mock_conf

@pytest.fixture
def mock_db():
    with patch('backend.tools.agents.base.db') as db:
        yield db

@pytest.mark.anyio
async def test_flow_fn_first_run(mock_agent, mock_config, mock_db):
    # Setup
    mock_db.get_messages.side_effect = [
        [], # is_resume check
        [], # loop 1 start
        [{"role": "assistant", "content": "summary"}], # loop 1 end
        [{"role": "assistant", "content": "summary"}]  # final check
    ]
    mock_db.get_task_list.return_value = [{"id": "task1"}]

    chunks = [chunk async for chunk in flow_fn(mock_agent, "create a file")]
    assert chunks == ["chunk1", "chunk2"]
    mock_db.add_message.assert_any_call(
        chat_id="test_chat", role='event', content='FileSystem Agent Started.',
        parent_id="test_parent", parent_type='file_system_agent'
    )
    args, kwargs = mock_agent.run_inference_step.call_args
    assert kwargs["tools"] == ToolRegistry.get_tools_for_scope(ToolScope.FILE_SYSTEM)
    assert mock_agent.result == "summary"

@pytest.mark.anyio
async def test_flow_fn_resume(mock_agent, mock_config, mock_db):
    mock_db.get_messages.side_effect = [
        [{"role": "assistant"}], # is_resume
        [{"role": "assistant"}], # loop 1 start
        [{"role": "assistant", "content": "done"}], # loop 1 end
        [{"role": "assistant", "content": "done"}]  # final check
    ]
    mock_db.get_task_list.return_value = [{"id": "task1"}]

    chunks = [chunk async for chunk in flow_fn(mock_agent, "instruction")]
    assert not any("FileSystem Agent Started." in str(c) for c in mock_db.add_message.mock_calls)

@pytest.mark.anyio
async def test_flow_fn_no_task_list_planning_enforcement(mock_agent, mock_config, mock_db):
    mock_db.get_messages.side_effect = [
        [], # is_resume
        [], # loop 1 start (planning)
        [{"role": "assistant", "content": "planned", "tool_calls": [{"name": "manage_task_list"}]}], # loop 1 end
        [{"role": "assistant", "content": "planned"}], # loop 2 start
        [{"role": "assistant", "content": "summary"}], # loop 2 end
        [{"role": "assistant", "content": "summary"}]  # final check
    ]
    mock_db.get_task_list.side_effect = [[], [{"id": "t1"}], [{"id": "t1"}], [{"id": "t1"}], [{"id": "t1"}]]

    chunks = [chunk async for chunk in flow_fn(mock_agent, "instruction")]
    args, kwargs = mock_agent.run_inference_step.call_args_list[0]
    assert kwargs["tools"] == [ToolRegistry.get_spec("manage_task_list").to_openai_schema()]

@pytest.mark.anyio
async def test_flow_fn_fails_to_init_task_list(mock_agent, mock_config, mock_db):
    mock_db.get_messages.side_effect = [
        [], # is_resume
        [], # loop 1 start
        [{"role": "assistant", "content": "failed"}], # loop 1 end
        [], # force break by returning empty
        [], [] # padding
    ]
    mock_db.get_task_list.return_value = [] # Always empty

    chunks = [chunk async for chunk in flow_fn(mock_agent, "instruction")]
    
    mock_db.add_message.assert_any_call(
        chat_id="test_chat", role='user',
        content='System Constraint: You MUST initialize your task list using manage_task_list before taking ANY other actions or responding.',
        parent_id="test_parent", parent_type='file_system_agent'
    )

@pytest.mark.anyio
async def test_flow_fn_turn_limit(mock_agent, mock_config, mock_db):
    mock_config.FILE_SYSTEM_AGENT_MAX_TURNS = 1
    history = [{"role": "tool", "name": "replace_fs_text", "content": "ok"}]
    mock_db.get_messages.side_effect = [
        [], # is_resume
        history, # loop 1 start (limit hit, warn)
        history + [{"role": "user", "content": "[SYSTEM: TURN LIMIT REACHED]"}], # loop 2 start (already warned)
        [{"role": "assistant", "content": "final synthesis"}], # loop 2 end
        [{"role": "assistant", "content": "final synthesis"}]  # final check
    ]
    mock_db.get_task_list.return_value = [{"id": "t1"}]

    chunks = [chunk async for chunk in flow_fn(mock_agent, "instruction")]
    mock_db.add_message.assert_any_call(
        chat_id="test_chat", role='user',
        content='[SYSTEM: TURN LIMIT REACHED] You have exhausted your allowed operations. Summarize your findings immediately. Do not attempt any further actions.',
        parent_id="test_parent", parent_type='file_system_agent'
    )

@pytest.mark.anyio
async def test_flow_fn_failsafe(mock_agent, mock_config, mock_db):
    mock_config.FILE_SYSTEM_AGENT_MAX_TURNS = 1
    mock_config.FILE_SYSTEM_AGENT_FAILSAFE_TURNS = 1
    mock_db.get_messages.return_value = [{"role": "assistant", "content": "", "tool_calls": [{"name": "fake"}]}]
    mock_db.get_task_list.return_value = [{"id": "t1"}]

    chunks = [chunk async for chunk in flow_fn(mock_agent, "instruction")]
    assert any("FileSystem Agent Force Terminated" in str(c) for c in mock_db.add_message.mock_calls)
    assert mock_agent.result == "Operation forcibly terminated due to infinite loop."

@pytest.mark.anyio
async def test_flow_fn_empty_history_break(mock_agent, mock_config, mock_db):
    mock_db.get_messages.side_effect = [
        [], # is_resume check
        [], # loop 1 start
        []  # loop 1 post-inference check -> break
    ]
    mock_db.get_task_list.return_value = [{"id": "t1"}]
    chunks = [chunk async for chunk in flow_fn(mock_agent, "instruction")]
    assert chunks == ["chunk1", "chunk2"]

@pytest.mark.anyio
async def test_flow_fn_exception_caught(mock_agent, mock_config, mock_db):
    mock_db.get_messages.side_effect = Exception("DB error")
    chunks = [chunk async for chunk in flow_fn(mock_agent, "instruction")]
    
    assert len(chunks) == 1
    assert "FileSystem Agent failed. Try again." in chunks[0]
    assert "DB error" not in chunks[0]
    assert mock_agent.result == "FileSystem Agent failed. Try again."
    
    mock_db.add_message.assert_any_call(
        chat_id="test_chat",
        role='event',
        content='FileSystem Agent failed. Try again.',
        parent_id="test_parent",
        parent_type='file_system_agent'
    )


def test_format_user_message_with_clipboard_keys(mock_agent):
    from backend.tools.agents.file_system_agent.agent import FileSystemAgent
    cfg = MagicMock()
    fs_agent = FileSystemAgent(mock_agent, cfg)
    
    # Test formatting with no clipboard keys
    msg1 = fs_agent.format_user_message(instruction="Test instruction")
    assert msg1 == "Instruction: Test instruction"
    
    # Test formatting with clipboard keys
    msg2 = fs_agent.format_user_message(instruction="Test instruction", clipboard_keys=["cb-1234"])
    assert "Instruction: Test instruction" in msg2
    assert "Clipboard Keys Available: [cb-1234]" in msg2
    assert "Use these keys with the clipboard_key parameter" in msg2

