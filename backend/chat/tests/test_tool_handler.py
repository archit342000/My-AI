import pytest
import json
from unittest.mock import MagicMock, patch, AsyncMock
from backend.chat.tool_handler import ToolHandler

@pytest.fixture
def mock_db():
    with patch('backend.database.db') as mock:
        yield mock
        
@pytest.fixture
def mock_global_db():
    with patch('backend.database.db') as mock:
        yield mock

@pytest.fixture
def mock_registry():
    with patch('backend.chat.tool_handler.ToolRegistry') as mock:
        mock.get_spec.return_value = MagicMock(admin_only=False)  # ordinary tools unless a test says otherwise
        yield mock

@pytest.fixture
def tool_handler():
    chat_handler = MagicMock()
    handler = ToolHandler("chat_123", chat_handler, parent_message_id=100)
    handler._user_id = "user-a"  # the chat owner (normally read from the db on first use)
    return handler

def test_init(tool_handler):
    assert tool_handler.chat_id == "chat_123"
    assert tool_handler.parent_message_id == 100
    assert tool_handler.parent_type == "main"
    assert tool_handler.agent_handler is not None
    assert tool_handler.agent_handler.parent_message_id == 100

@pytest.mark.anyio
@patch('backend.database.db')
async def test_handle_tool_calls_idempotency(mock_db_instance, tool_handler):
    mock_db_instance.get_messages.return_value = [
        {"role": "tool", "tool_call_id": "call_1", "content": "already done"}
    ]
    
    tool_calls = [{"id": "call_1", "function": {"name": "test_tool", "arguments": "{}"}}]
    
    chunks = []
    async for chunk in tool_handler.handle_tool_calls(tool_calls):
        chunks.append(chunk)
        
    assert len(chunks) == 0
    mock_db_instance.get_messages.assert_called_with("chat_123", parent_type="main")

@pytest.mark.anyio
async def test_handle_tool_calls_missing_name(mock_db, tool_handler):
    tool_calls = [{"id": "call_1", "function": {"arguments": "{}"}}]
    chunks = []
    async for chunk in tool_handler.handle_tool_calls(tool_calls):
        chunks.append(chunk)
    assert len(chunks) == 0

@pytest.mark.anyio
@patch('backend.database.db')
async def test_handle_tool_calls_bad_args(mock_db_instance, mock_registry, tool_handler):
    mock_db_instance.get_messages.return_value = []
    mock_registry.get_tool.return_value = {"type": "function"}
    mock_registry.resolve_implementation.return_value = AsyncMock(return_value="success")
    
    # Should use empty dict for args
    tool_calls = [{"id": "call_1", "function": {"name": "test_tool", "arguments": "invalid json"}}]
    
    chunks = []
    async for chunk in tool_handler.handle_tool_calls(tool_calls):
        chunks.append(chunk)
        
    assert len(chunks) == 1
    mock_impl = mock_registry.resolve_implementation.return_value
    # args should be empty dict because of bad json

@pytest.mark.anyio
@patch('backend.database.db')
async def test_handle_tool_calls_unregistered_tool(mock_db_instance, mock_registry, tool_handler):
    mock_db_instance.get_messages.return_value = []
    mock_registry.get_tool.return_value = None
    mock_registry._registry = {"available_tool": {}}
    
    tool_calls = [{"id": "call_1", "function": {"name": "test_tool", "arguments": "{}"}}]
    
    chunks = []
    async for chunk in tool_handler.handle_tool_calls(tool_calls):
        chunks.append(chunk)
        
    assert len(chunks) == 1
    assert "not found in registry" in chunks[0]
    mock_db_instance.add_tool_result.assert_called_once()
    assert "not found in registry" in mock_db_instance.add_tool_result.call_args.kwargs['content']

@pytest.mark.anyio
@patch('backend.database.db')
async def test_handle_tool_calls_agent_tool_no_result(mock_db_instance, mock_registry, tool_handler):
    mock_db_instance.get_messages.return_value = []
    mock_registry.get_tool.return_value = {"type": "agent"}
    
    async def mock_agent_flow(agent, agent_name, **kwargs):
        yield "agent_stream"
        
    mock_registry.resolve_implementation.return_value = mock_agent_flow
    tool_handler.agent_handler = MagicMock()
    
    async def execute_agent_mock(*args, **kwargs):
        yield "chunk1"
        
    tool_handler.agent_handler.execute_agent.side_effect = execute_agent_mock
    tool_handler.agent_handler.result = None
    
    tool_calls = [{"id": "call_1", "function": {"name": "test_agent", "arguments": "{}"}}]
    
    chunks = []
    async for chunk in tool_handler.handle_tool_calls(tool_calls):
        chunks.append(chunk)
        
    assert len(chunks) == 2
    assert chunks[0] == "chunk1"
    assert "completed execution successfully" in chunks[1]
    mock_db_instance.add_tool_result.assert_called_once()
    assert "completed execution successfully" in mock_db_instance.add_tool_result.call_args.kwargs['content']

@pytest.mark.anyio
@patch('backend.database.db')
async def test_handle_tool_calls_agent_tool_with_result(mock_db_instance, mock_registry, tool_handler):
    mock_db_instance.get_messages.return_value = []
    mock_registry.get_tool.return_value = {"type": "agent"}
    
    async def mock_agent_flow(agent, agent_name, **kwargs):
        yield "agent_stream"
        
    mock_registry.resolve_implementation.return_value = mock_agent_flow
    tool_handler.agent_handler = MagicMock()
    
    async def execute_agent_mock(*args, **kwargs):
        yield "chunk1"
        
    tool_handler.agent_handler.execute_agent.side_effect = execute_agent_mock
    tool_handler.agent_handler.result = {"key": "value"}
    
    tool_calls = [{"id": "call_1", "function": {"name": "test_agent", "arguments": "{}"}}]
    
    chunks = []
    async for chunk in tool_handler.handle_tool_calls(tool_calls):
        chunks.append(chunk)
        
    assert len(chunks) == 2
    assert chunks[0] == "chunk1"
    assert '\\"key\\": \\"value\\"' in chunks[1]
    mock_db_instance.add_tool_result.assert_called_once()
    assert '{"key": "value"}' in mock_db_instance.add_tool_result.call_args.kwargs['content']

@pytest.mark.anyio
@patch('backend.database.db')
async def test_handle_tool_calls_agent_tool_unresolved(mock_db_instance, mock_registry, tool_handler):
    mock_db_instance.get_messages.return_value = []
    mock_registry.get_tool.return_value = {"type": "agent"}
    mock_registry.resolve_implementation.return_value = None
    
    tool_calls = [{"id": "call_1", "function": {"name": "test_agent", "arguments": "{}"}}]
    
    chunks = []
    async for chunk in tool_handler.handle_tool_calls(tool_calls):
        chunks.append(chunk)
        
    assert len(chunks) == 1
    assert "could not be resolved" in chunks[0]
    mock_db_instance.add_tool_result.assert_called_once()
    assert "could not be resolved" in mock_db_instance.add_tool_result.call_args.kwargs['content']

@pytest.mark.anyio
@patch('backend.database.db')
async def test_handle_tool_calls_pure_function(mock_db_instance, mock_registry, tool_handler):
    mock_db_instance.get_messages.return_value = []
    mock_registry.get_tool.return_value = {"type": "function"}
    
    mock_impl = AsyncMock(return_value={"result": "pure_success"})
    mock_registry.resolve_implementation.return_value = mock_impl
    
    tool_calls = [{"id": "call_2", "function": {"name": "pure_tool", "arguments": '{"arg1": "val1"}'}}]
    
    chunks = []
    async for chunk in tool_handler.handle_tool_calls(tool_calls):
        chunks.append(chunk)
        
    assert len(chunks) == 1
    assert '\\"result\\": \\"pure_success\\"' in chunks[0]
    mock_db_instance.add_tool_result.assert_called_once()
    assert '{"result": "pure_success"}' in mock_db_instance.add_tool_result.call_args.kwargs['content']

@pytest.mark.anyio
async def test_execute_pure_tool_unresolved(mock_registry, tool_handler):
    mock_registry.resolve_implementation.return_value = None
    result = await tool_handler._execute_pure_tool("bad_tool", {})
    assert "could not be resolved" in result

@pytest.mark.anyio
async def test_execute_pure_tool_var_keyword(mock_registry, tool_handler):
    async def mock_impl(**kwargs):
        return kwargs
        
    mock_registry.resolve_implementation.return_value = mock_impl
    result = await tool_handler._execute_pure_tool("tool1", {"arg": 1}, tc_id="t1")
    assert result["arg"] == 1
    assert result["chat_id"] == "chat_123"
    assert result["tool_call_id"] == "t1"

@pytest.mark.anyio
async def test_execute_pure_tool_strict_params(mock_registry, tool_handler):
    async def mock_impl(arg, chat_id):
        return f"{arg}_{chat_id}"
        
    mock_registry.resolve_implementation.return_value = mock_impl
    result = await tool_handler._execute_pure_tool("tool1", {"arg": 1}, tc_id="t1")
    assert result == "1_chat_123"

@pytest.mark.anyio
async def test_user_id_comes_from_the_chat_owner_never_from_the_model(mock_registry, tool_handler):
    received = {}

    def impl(content, user_id=None, **kwargs):
        received["user_id"] = user_id
        return "ok"

    mock_registry.resolve_implementation.return_value = impl
    # the model tries to act as another user; the server-side value must win (system_ctx overrides model arguments)
    assert await tool_handler._execute_pure_tool("tool1", {"content": "c", "user_id": "someone-else"}) == "ok"
    assert received["user_id"] == "user-a"


@pytest.mark.anyio
async def test_user_id_is_injected_into_a_tool_that_declares_it_without_var_keyword(mock_registry, tool_handler):
    def impl(content, user_id):
        return f"{content}:{user_id}"

    mock_registry.resolve_implementation.return_value = impl
    assert await tool_handler._execute_pure_tool("tool1", {"content": "c"}) == "c:user-a"


@pytest.mark.anyio
async def test_a_failing_owner_lookup_is_a_tool_error_not_an_exception(mock_registry):
    handler = ToolHandler("chat_9", MagicMock())
    received = {}

    def impl(content, user_id=None, **kwargs):
        received["user_id"] = user_id
        return "ran"

    mock_mod = patch('backend.chat.tool_handler.db')
    with mock_mod as owner_db:
        owner_db.get_chat_owner.side_effect = RuntimeError("database is locked")
        mock_registry.resolve_implementation.return_value = impl
        assert await handler._execute_pure_tool("tool1", {"content": "c"}) == "ran"  # no exception mid-stream
    assert received["user_id"] is None  # the tool then reports "no owner" itself


def test_tool_handler_resolves_the_chat_owner_lazily_and_once():
    with patch('backend.chat.tool_handler.db') as owner_db:
        owner_db.get_chat_owner.return_value = "owner-9"
        handler = ToolHandler("chat_9", MagicMock())
        owner_db.get_chat_owner.assert_not_called()  # building a handler needs no db access
        assert handler.user_id == "owner-9"
        assert handler.user_id == "owner-9"
    owner_db.get_chat_owner.assert_called_once_with("chat_9")


@pytest.mark.anyio
async def test_sync_tool_runs_as_the_current_user(mock_registry, tool_handler):
    """A sync tool implementation runs in an executor thread; it must still see the chat owner (log_event user_id)."""
    from backend.auth.context import current_user_id, user_context
    seen = []

    def mock_impl():
        seen.append(current_user_id())
        return "ok"

    mock_registry.resolve_implementation.return_value = mock_impl
    with user_context({"id": "owner-1"}):
        assert await tool_handler._execute_pure_tool("tool1", {}) == "ok"
    assert seen == ["owner-1"]


@pytest.mark.anyio
async def test_execute_pure_tool_sync_exception(mock_registry, tool_handler):
    def mock_impl():
        raise ValueError("sync error")
        
    mock_registry.resolve_implementation.return_value = mock_impl
    with patch('backend.chat.tool_handler.log_event') as log:
        result = await tool_handler._execute_pure_tool("tool1", {})
    # The model gets a fixed message without the exception text; the detail goes to the log event.
    assert result.startswith("Error") and "tool1" in result
    assert "sync error" not in result
    log.assert_any_call("tool_handler_tool_error", {
        "chat_id": tool_handler.chat_id, "name": "tool1", "id": None,
        "error_type": "ValueError", "error": "sync error",
    })

@pytest.mark.anyio
async def test_execute_pure_tool_async_exception(mock_registry, tool_handler):
    async def mock_impl():
        raise RuntimeError("/secret/path failed")

    mock_registry.resolve_implementation.return_value = mock_impl
    with patch('backend.chat.tool_handler.log_event') as log:
        result = await tool_handler._execute_pure_tool("tool2", {}, tc_id="tc9")
    assert result.startswith("Error") and "tool2" in result and "/secret/path" not in result
    assert log.call_args.args[1]["error"] == "/secret/path failed" and log.call_args.args[1]["id"] == "tc9"

@pytest.mark.anyio
@patch('backend.database.db')
async def test_handle_tool_calls_scoped_anchoring_validation(mock_db_instance, mock_registry, tool_handler):
    mock_db_instance.get_messages.return_value = []
    mock_registry.get_tool.return_value = {"type": "agent"}
    
    async def mock_agent_flow(agent, agent_name, **kwargs):
        yield "agent_stream_chunk"
    
    mock_registry.resolve_implementation.return_value = mock_agent_flow
    tool_handler.agent_handler = MagicMock()
    
    async def execute_agent_mock(*args, **kwargs):
        yield "streamed_chunk"
        
    tool_handler.agent_handler.execute_agent.side_effect = execute_agent_mock
    # Mock returning structured dict data
    tool_handler.agent_handler.result = {"summary": "done", "status": "success"}
    
    tool_calls = [{"id": "tc_agent_123", "function": {"name": "test_agent", "arguments": '{"param": 1}'}}]
    
    chunks = []
    async for chunk in tool_handler.handle_tool_calls(tool_calls):
        chunks.append(chunk)
        
    # Verify scoped anchoring: the parent message ID was shifted to the tool call's ID!
    assert tool_handler.agent_handler.parent_message_id == "tc_agent_123"
    
    # Assert JSON-serialized structured summary was saved in the DB
    mock_db_instance.add_tool_result.assert_called_once()
    saved_content = mock_db_instance.add_tool_result.call_args.kwargs['content']
    assert json.loads(saved_content) == {"summary": "done", "status": "success"}
    
    # Verify synthetic result chunk is yielded for frontend rendering
    assert any("streamed_chunk" in c for c in chunks)
    assert any("summary" in c and "status" in c for c in chunks)

@pytest.mark.anyio
@patch('backend.database.db')
async def test_handle_tool_calls_unregistered_tool_recovery(mock_db_instance, mock_registry, tool_handler):
    mock_db_instance.get_messages.return_value = []
    # Tool not found in registry
    mock_registry.get_tool.return_value = None
    mock_registry._registry = {"real_tool": {}}
    
    tool_calls = [{"id": "call_unknown", "function": {"name": "non_existent_tool", "arguments": "{}"}}]
    
    chunks = []
    async for chunk in tool_handler.handle_tool_calls(tool_calls):
        chunks.append(chunk)
        
    # Verify synthetic result chunk is yielded with error details
    assert len(chunks) == 1
    assert "choices" in chunks[0]
    
    # Verify that the DB was called with the error content
    mock_db_instance.add_tool_result.assert_called_once_with(
        chat_id="chat_123",
        tool_call_id="call_unknown",
        name="non_existent_tool",
        content="Error: Tool 'non_existent_tool' not found in registry. Available: ['real_tool']",
        parent_id=100,
        parent_type="main"
    )


@pytest.mark.anyio
@patch('backend.database.db')
async def test_handle_tool_calls_clipboard_enforcement_hard_reject(mock_db_instance, mock_registry, tool_handler):
    mock_db_instance.get_messages.return_value = []
    mock_registry.get_tool.return_value = {"type": "agent"}
    
    # Generate an instruction exceeding config.MAX_FS_AGENT_INSTRUCTION_LENGTH
    from backend import config
    long_instruction = "A" * (config.MAX_FS_AGENT_INSTRUCTION_LENGTH + 1)
    
    tool_calls = [{
        "id": "tc_hard_123",
        "function": {
            "name": "file_system_agent",
            "arguments": json.dumps({"instruction": long_instruction})
        }
    }]
    
    # Initialize pending confirmation to None
    tool_handler.chat_handler._pending_confirmation = None
    
    chunks = []
    async for chunk in tool_handler.handle_tool_calls(tool_calls):
        chunks.append(chunk)
        
    assert len(chunks) == 1
    assert "REJECTED:" in chunks[0]
    mock_db_instance.add_tool_result.assert_called_once()
    assert "REJECTED:" in mock_db_instance.add_tool_result.call_args.kwargs['content']
    assert tool_handler.chat_handler._pending_confirmation is None


@pytest.mark.anyio
@patch('backend.database.db')
async def test_handle_tool_calls_clipboard_enforcement_soft_reject(mock_db_instance, mock_registry, tool_handler):
    mock_db_instance.get_messages.return_value = []
    mock_registry.get_tool.return_value = {"type": "agent"}
    
    # Trigger a pattern-based soft reject
    instruction = "Write the following content to index.html:\n" + ("x" * 300)
    
    tool_calls = [{
        "id": "tc_soft_123",
        "function": {
            "name": "file_system_agent",
            "arguments": json.dumps({"instruction": instruction})
        }
    }]
    
    # Initialize pending confirmation to None
    tool_handler.chat_handler._pending_confirmation = None
    
    chunks = []
    async for chunk in tool_handler.handle_tool_calls(tool_calls):
        chunks.append(chunk)
        
    assert len(chunks) == 1
    assert "SOFT REJECT" in chunks[0]
    mock_db_instance.add_tool_result.assert_called_once()
    assert "SOFT REJECT" in mock_db_instance.add_tool_result.call_args.kwargs['content']
    
    # Check that pending confirmation was stored
    pending = tool_handler.chat_handler._pending_confirmation
    assert pending is not None
    assert pending["tc_id"] == "tc_soft_123"
    assert pending["name"] == "file_system_agent"


@pytest.mark.anyio
@patch('backend.database.db')
async def test_handle_tool_calls_clipboard_enforcement_bypass(mock_db_instance, mock_registry, tool_handler):
    mock_db_instance.get_messages.return_value = []
    mock_registry.get_tool.return_value = {"type": "agent"}
    
    # A flow function that yields a mocked result
    async def mock_agent_flow(agent, agent_name, **kwargs):
        yield "mocked_chunk"
    mock_registry.resolve_implementation.return_value = mock_agent_flow
    
    tool_handler.agent_handler = MagicMock()
    async def execute_agent_mock(*args, **kwargs):
        yield "mocked_chunk"
    tool_handler.agent_handler.execute_agent.side_effect = execute_agent_mock
    tool_handler.agent_handler.result = "success"
    
    # Normally this would trigger a soft reject, but with bypass it should proceed
    instruction = "Write the following content to index.html:\n" + ("x" * 300)
    tool_handler.chat_handler._validation_bypass_next = True
    
    tool_calls = [{
        "id": "tc_bypass_123",
        "function": {
            "name": "file_system_agent",
            "arguments": json.dumps({"instruction": instruction})
        }
    }]
    
    chunks = []
    async for chunk in tool_handler.handle_tool_calls(tool_calls):
        chunks.append(chunk)
        
    assert any("mocked_chunk" in c for c in chunks)
    assert tool_handler.chat_handler._validation_bypass_next is False # Check it was reset


async def _run_calls(handler, name):
    return [c async for c in handler.handle_tool_calls([{"id": "call_1", "function": {"name": name, "arguments": "{}"}}])]


@pytest.mark.anyio
@pytest.mark.parametrize("tool", ["git_agent", "execute_git", "install_packages"])
@pytest.mark.parametrize("role,owner", [("user", "u1"), (None, "u1"), ("admin", None)])  # a user, an unknown user, no owner
async def test_admin_only_tools_are_refused_for_a_non_admin_owner_and_nothing_runs(tool, role, owner, tool_handler):
    tool_handler._user_id = owner
    user_row = {"id": "u1", "role": role} if role else None
    with patch('backend.chat.tool_handler.db') as handler_db, patch('backend.database.db') as global_db, \
         patch('backend.chat.tool_handler.ToolRegistry.resolve_implementation') as resolve, \
         patch('backend.chat.tool_handler.log_event') as events:
        handler_db.get_user.return_value = user_row
        global_db.get_messages.return_value = []
        chunks = await _run_calls(tool_handler, tool)
    resolve.assert_not_called()  # neither the implementation nor the agent is resolved, let alone run
    assert "Error: This tool is not available." in "".join(chunks)
    assert any(c.args[0] == "tool_admin_only_denied" for c in events.call_args_list)
    global_db.add_tool_result.assert_called_once()


@pytest.mark.anyio
async def test_install_packages_runs_for_an_admin_owner(tool_handler, mock_registry):
    tool_handler._user_id = "a1"
    mock_registry.get_tool.return_value = {"type": "pure"}
    mock_registry.get_spec.return_value = MagicMock(admin_only=True)
    mock_registry.resolve_implementation.return_value = lambda **kw: "installed"
    with patch('backend.chat.tool_handler.db') as handler_db, patch('backend.database.db') as global_db:
        handler_db.get_user.return_value = {"id": "a1", "role": "admin"}
        global_db.get_messages.return_value = []
        chunks = await _run_calls(tool_handler, "install_packages")
    assert "not available" not in "".join(chunks)
    mock_registry.resolve_implementation.assert_called()

