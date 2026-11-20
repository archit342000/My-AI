import pytest
import json
from unittest.mock import ANY, MagicMock, patch, AsyncMock
from backend.chat.tool_handler import ToolHandler, _activity_from_chunk, _agent_run_chunk, _run_failed

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
        
    plain = [c for c in chunks if '"agent_run"' not in c and c != "\n\n"]
    assert plain[0] == "chunk1" and len(plain) == 2  # the agent's chunk and the tool result (agent_run lines and line ends are separate)
    assert "completed execution successfully" in chunks[-1]
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
        
    assert len([c for c in chunks if '"agent_run"' not in c and c != "\n\n"]) == 2
    assert "chunk1" in chunks
    assert '\\"key\\": \\"value\\"' in chunks[-1]
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
        
    assert len([c for c in chunks if '"agent_run"' not in c]) == 1
    assert "could not be resolved" in chunks[-1]
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
        parent_type="main",
        duration_ms=ANY
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




# ---- durations -------------------------------------------------------------------------------------------------

def _clock(*values):
    """A stand-in for the module's `time` whose monotonic() returns the given values in order."""
    fake = MagicMock()
    fake.monotonic.side_effect = list(values)
    return fake


def _delta(chunk):
    return json.loads(chunk[len("data: "):])["choices"][0]["delta"]["tool_result"]


@pytest.mark.anyio
@patch('backend.database.db')
async def test_a_pure_tool_stores_and_sends_its_duration(mock_db_instance, mock_registry, tool_handler):
    mock_db_instance.get_messages.return_value = []
    mock_registry.get_tool.return_value = {"type": "function"}
    mock_registry.resolve_implementation.return_value = AsyncMock(return_value="ok")
    with patch('backend.chat.tool_handler.time', _clock(10.0, 10.25)):
        chunks = [c async for c in tool_handler.handle_tool_calls([{"id": "t1", "function": {"name": "x", "arguments": "{}"}}])]
    assert mock_db_instance.add_tool_result.call_args.kwargs["duration_ms"] == 250
    assert _delta(chunks[0])["duration_ms"] == 250


@pytest.mark.anyio
@patch('backend.database.db')
async def test_an_agent_tool_duration_covers_the_whole_run(mock_db_instance, mock_registry, tool_handler):
    mock_db_instance.get_messages.return_value = []
    mock_registry.get_tool.return_value = {"type": "agent"}
    mock_registry.resolve_implementation.return_value = object()
    tool_handler.agent_handler = MagicMock()

    async def run(*a, **k):
        yield "chunk"
    tool_handler.agent_handler.execute_agent.side_effect = run
    tool_handler.agent_handler.result = "done"
    with patch('backend.chat.tool_handler.time', _clock(5.0, 43.0)):
        chunks = [c async for c in tool_handler.handle_tool_calls([{"id": "t1", "function": {"name": "agent", "arguments": "{}"}}])]
    assert mock_db_instance.add_tool_result.call_args.kwargs["duration_ms"] == 38000
    assert _delta(chunks[-1])["duration_ms"] == 38000


@pytest.mark.anyio
@pytest.mark.parametrize("branch", ["unknown", "unresolved_agent", "clipboard"])
@patch('backend.database.db')
async def test_refusals_and_unresolved_calls_also_carry_a_duration(mock_db_instance, branch, mock_registry, tool_handler):
    mock_db_instance.get_messages.return_value = []
    mock_registry._registry = {}
    name, args = "x", "{}"
    if branch == "unknown":
        mock_registry.get_tool.return_value = None
    elif branch == "unresolved_agent":
        mock_registry.get_tool.return_value = {"type": "agent"}
        mock_registry.resolve_implementation.return_value = None
    else:
        from backend import config
        mock_registry.get_tool.return_value = {"type": "agent"}
        name, args = "file_system_agent", json.dumps({"instruction": "A" * (config.MAX_FS_AGENT_INSTRUCTION_LENGTH + 1)})
        tool_handler.chat_handler._pending_confirmation = None
        tool_handler.chat_handler._validation_bypass_next = False
    with patch('backend.chat.tool_handler.time', _clock(1.0, 1.5)):
        chunks = [c async for c in tool_handler.handle_tool_calls([{"id": "t1", "function": {"name": name, "arguments": args}}])]
    assert mock_db_instance.add_tool_result.call_args.kwargs["duration_ms"] == 500
    assert _delta(chunks[-1])["duration_ms"] == 500


@pytest.mark.anyio
async def test_an_admin_only_refusal_carries_a_duration(tool_handler):
    tool_handler._user_id = "u1"
    with patch('backend.chat.tool_handler.db') as handler_db, patch('backend.database.db') as global_db, \
         patch('backend.chat.tool_handler.time', _clock(2.0, 2.1)):
        handler_db.get_user.return_value = {"id": "u1", "role": "user"}
        global_db.get_messages.return_value = []
        chunks = await _run_calls(tool_handler, "git_agent")
    assert global_db.add_tool_result.call_args.kwargs["duration_ms"] == 100
    assert _delta(chunks[0])["duration_ms"] == 100


@pytest.mark.anyio
@patch('backend.database.db')
async def test_a_call_skipped_as_already_done_sends_and_stores_nothing(mock_db_instance, tool_handler):
    mock_db_instance.get_messages.return_value = [{"role": "tool", "tool_call_id": "t1"}]
    chunks = [c async for c in tool_handler.handle_tool_calls([{"id": "t1", "function": {"name": "x", "arguments": "{}"}}])]
    assert chunks == []
    mock_db_instance.add_tool_result.assert_not_called()


# ---- helper runs (agent_run) -----------------------------------------------------------------------------------



def _line(delta, parent_type="helper", **extra):
    return "data: " + json.dumps({"parent_type": parent_type, "choices": [{"delta": delta}], **extra}) + "\n\n"


def test_activity_comes_from_the_helpers_own_event_text_or_the_tool_it_called():
    assert _activity_from_chunk(_line({"role": "event", "content": "  Searching the web  "}), "helper") == "Searching the web"
    call = {"id": "c", "function": {"name": "visit_page", "arguments": "{}"}}
    assert _activity_from_chunk(_line({"tool_calls": [call]}), "helper") == "Using visit_page"
    assert len(_activity_from_chunk(_line({"role": "event", "content": "x" * 500}), "helper")) == 120


@pytest.mark.parametrize("line", [
    _line({"role": "event", "content": "other agent"}, parent_type="nested"),                      # another helper's own chunk
    _line({"role": "event", "content": "main"}, parent_type="main"),
    _line({"tool_result": {"name": "n", "content": "c"}}),                                      # a result
    "data: " + json.dumps({"parent_type": "helper", "agent_run": {"id": "x"}}) + "\n\n",         # a run line (nested handler)
    _line({"content": "plain answer text"}),                                                    # not activity
    _line({"role": "event", "content": "   "}),
    "data: not json\n\n", "event: ping\n\n", "", None,
])
def test_activity_ignores_other_agents_results_run_lines_and_garbage(line):
    assert _activity_from_chunk(line, "helper") is None


@pytest.mark.parametrize("result,failed", [
    ("Error: Daily web search limit reached.", True), ("error: lowercase too", True), ("Search failed. Try again.", True),
    ("Mock Agent failed. Try again.", True), ("Visit page failed. Try again.", True), ("Browsing agent failed during execution. Try again.", True),
    ("Here is the answer.\nError: appears later", False), ("The search did not fail", False), ("", False), (None, False), ("Searching… done", False),
    ("Checkout failed for order 42", False), ("3 results failed to load, the rest is fine", False), ("Search failed after 3 attempts. Try again.", True),
    ("Browsing agent failed during execution. Try again.", True), ("Visit page agent failed to return a response.", True),
])
def test_run_failed_reads_the_first_line_only(result, failed):
    assert _run_failed(result) is failed


def test_the_agent_run_line_is_a_data_line_tagged_with_the_callers_parent_type():
    line = _agent_run_chunk("research", {"id": "t1", "name": "search_web", "state": "running"})
    assert line.startswith("data: ") and line.endswith("\n\n")
    assert json.loads(line[6:]) == {"parent_type": "research", "agent_run": {"id": "t1", "name": "search_web", "state": "running"}}


def _agent_setup(handler, mock_registry, chunks, result="the answer", raises=None):
    mock_registry.get_tool.return_value = {"type": "agent"}
    mock_registry.resolve_implementation.return_value = object()
    handler.agent_handler = MagicMock()
    handler.agent_handler.result = result

    async def run(*a, **k):
        for c in chunks:
            yield c
        if raises:
            raise raises
    handler.agent_handler.execute_agent.side_effect = run


def _runs(chunks):
    return [json.loads(c[6:])["agent_run"] for c in chunks if c.startswith("data: ") and '"agent_run"' in c]


@pytest.mark.anyio
@patch('backend.database.db')
async def test_a_helper_run_sends_start_activity_updates_and_a_done_end_with_the_duration(mock_db, mock_registry, tool_handler):
    mock_db.get_messages.return_value = []
    call = {"id": "c", "function": {"name": "visit_page", "arguments": "{}"}}
    _agent_setup(tool_handler, mock_registry, [_line({"role": "event", "content": "Searching"}, "search_web"), _line({"role": "event", "content": "Searching"}, "search_web"),
                                               _line({"tool_calls": [call]}, "search_web"), _line({"content": "text"}, "search_web")])
    with patch('backend.chat.tool_handler.time', _clock(5.0, 43.0)):
        chunks = [c async for c in tool_handler.handle_tool_calls([{"id": "t1", "function": {"name": "search_web", "arguments": "{}"}}])]
    runs = _runs(chunks)
    assert [(r["state"], r["activity"]) for r in runs] == [("running", None), ("running", "Searching"), ("running", "Using visit_page"), ("done", "Using visit_page")]
    assert all(r["id"] == "t1" and r["name"] == "search_web" and r["parent_id"] is None for r in runs)  # top-level run: no parent
    assert runs[0]["duration_ms"] is None and runs[-1]["duration_ms"] == 38000 and isinstance(runs[0]["started_at"], float)
    assert mock_db.add_tool_result.call_args.kwargs["duration_ms"] == 38000  # the same number as the tool result's
    assert chunks[-1].startswith("data: ") and "tool_result" in chunks[-1]  # the result still comes last


@pytest.mark.anyio
@pytest.mark.parametrize("result", ["Error: Daily web search limit reached.", "Search failed. Try again."])
@patch('backend.database.db')
async def test_a_helper_whose_result_reads_as_a_failure_ends_failed(mock_db, mock_registry, tool_handler, result):
    mock_db.get_messages.return_value = []
    _agent_setup(tool_handler, mock_registry, [], result=result)
    chunks = [c async for c in tool_handler.handle_tool_calls([{"id": "t1", "function": {"name": "search_web", "arguments": "{}"}}])]
    assert _runs(chunks)[-1]["state"] == "failed"


@pytest.mark.anyio
@patch('backend.database.db')
async def test_a_helper_that_raises_ends_failed_and_the_exception_still_propagates(mock_db, mock_registry, tool_handler):
    mock_db.get_messages.return_value = []
    _agent_setup(tool_handler, mock_registry, [_line({"role": "event", "content": "Working"}, "search_web")], raises=RuntimeError("boom"))
    seen = []
    with pytest.raises(RuntimeError):
        async for c in tool_handler.handle_tool_calls([{"id": "t1", "function": {"name": "search_web", "arguments": "{}"}}]):
            seen.append(c)
    runs = _runs(seen)
    assert runs[0]["state"] == "running" and runs[-1]["state"] == "failed" and isinstance(runs[-1]["duration_ms"], int)


@pytest.mark.anyio
@patch('backend.database.db')
async def test_an_unresolved_helper_implementation_sends_a_failed_run_and_pure_tools_send_none(mock_db, mock_registry, tool_handler):
    mock_db.get_messages.return_value = []
    mock_registry.get_tool.return_value = {"type": "agent"}
    mock_registry.resolve_implementation.return_value = None
    chunks = [c async for c in tool_handler.handle_tool_calls([{"id": "t1", "function": {"name": "ghost", "arguments": "{}"}}])]
    runs = _runs(chunks)
    assert [r["state"] for r in runs] == ["running", "failed"] and runs[0]["started_at"] == runs[1]["started_at"]  # an explicit start, then the end
    mock_registry.get_tool.return_value = {"type": "function"}
    mock_registry.resolve_implementation.return_value = AsyncMock(return_value="ok")
    chunks = [c async for c in tool_handler.handle_tool_calls([{"id": "t2", "function": {"name": "get_time", "arguments": "{}"}}])]
    assert _runs(chunks) == []


@pytest.mark.anyio
@patch('backend.database.db')
async def test_a_nested_run_carries_its_outer_runs_id_and_the_callers_parent_type(mock_db, mock_registry):
    mock_db.get_messages.return_value = []
    nested = ToolHandler("chat_123", MagicMock(), parent_message_id="outer-call", parent_type="research")
    nested._user_id = "user-a"
    _agent_setup(nested, mock_registry, [])
    chunks = [c async for c in nested.handle_tool_calls([{"id": "inner", "function": {"name": "search_web", "arguments": "{}"}}])]
    for line in (c for c in chunks if '"agent_run"' in c):
        payload = json.loads(line[6:])
        assert payload["parent_type"] == "research" and payload["agent_run"]["parent_id"] == "outer-call"


@pytest.mark.anyio
@patch('backend.database.db')
async def test_finished_runs_are_stored_in_one_collection_merged_by_id_across_handlers(mock_db, mock_registry, tool_handler):
    stored = {}
    mock_db.get_messages.return_value = []
    mock_db.get_collections.side_effect = lambda *a, **k: [{"collection_type": "agent_runs", "items": json.dumps(stored["items"])}] if "items" in stored else []
    mock_db.add_collection.side_effect = lambda **kw: stored.update(items=kw["items"], kw=kw)
    _agent_setup(tool_handler, mock_registry, [])
    [c async for c in tool_handler.handle_tool_calls([{"id": "t1", "function": {"name": "search_web", "arguments": "{}"}}])]
    [c async for c in tool_handler.handle_tool_calls([{"id": "t2", "function": {"name": "visit_page", "arguments": "{}"}}])]
    assert [r["id"] for r in stored["items"]] == ["t1", "t2"] and all(r["state"] == "done" for r in stored["items"])
    kw = stored["kw"]
    assert kw["collection_type"] == "agent_runs" and kw["overwrite"] is True and kw["parent_message_id"] == 100 and kw["parent_type"] == "main"
    # a resumed turn (a new handler for the same anchor) adds to the stored list; a repeated id replaces its own record
    again = ToolHandler("chat_123", MagicMock(), parent_message_id=100)
    again._user_id = "user-a"
    _agent_setup(again, mock_registry, [])
    mock_db.get_messages.return_value = []
    [c async for c in again.handle_tool_calls([{"id": "t3", "function": {"name": "search_web", "arguments": "{}"}}])]
    assert [r["id"] for r in stored["items"]] == ["t1", "t2", "t3"]


@pytest.mark.anyio
@patch('backend.database.db')
async def test_a_failing_run_store_is_logged_and_does_not_stop_the_turn(mock_db, mock_registry, tool_handler):
    import sqlite3
    mock_db.get_messages.return_value = []
    mock_db.get_collections.side_effect = sqlite3.OperationalError("locked")
    _agent_setup(tool_handler, mock_registry, [])
    with patch('backend.chat.tool_handler.log_event') as events:
        chunks = [c async for c in tool_handler.handle_tool_calls([{"id": "t1", "function": {"name": "search_web", "arguments": "{}"}}])]
    assert _runs(chunks)[-1]["state"] == "done" and "tool_result" in chunks[-1]
    assert any(c.args[0] == "agent_run_store_error" for c in events.call_args_list)


@pytest.mark.anyio
@patch('backend.database.db')
async def test_a_plain_text_agent_chunk_is_ended_so_the_next_data_line_stays_whole(mock_db, mock_registry, tool_handler):
    mock_db.get_messages.return_value = []
    _agent_setup(tool_handler, mock_registry, ["Search failed after 3 attempts."], result="Search failed after 3 attempts.")
    chunks = [c async for c in tool_handler.handle_tool_calls([{"id": "t1", "function": {"name": "search_web", "arguments": "{}"}}])]
    stream = "".join(chunks)
    assert "Search failed after 3 attempts.\n\ndata: " in stream  # the raw text line is closed before the end-of-run line
    assert [r["state"] for r in _runs([l + "\n\n" for l in stream.split("\n\n") if l.startswith("data: ")])] == ["running", "failed"]


@pytest.mark.parametrize("line", [
    _line({"tool_calls": ["not a dict"]}), _line({"tool_calls": [None]}), _line({"tool_calls": [{"function": "x"}]}),
    _line({"tool_calls": []}), "data: [1, 2]\n\n", "data: {\"parent_type\": \"helper\", \"choices\": [5]}\n\n",
])
def test_a_malformed_chunk_never_breaks_the_activity_reader(line):
    assert _activity_from_chunk(line, "helper") is None


@pytest.mark.anyio
@patch('backend.database.db')
async def test_a_malformed_helper_chunk_does_not_turn_a_working_helper_into_a_failed_run(mock_db, mock_registry, tool_handler):
    mock_db.get_messages.return_value = []
    _agent_setup(tool_handler, mock_registry, [_line({"tool_calls": ["junk"]}, "search_web")])
    chunks = [c async for c in tool_handler.handle_tool_calls([{"id": "t1", "function": {"name": "search_web", "arguments": "{}"}}])]
    assert _runs(chunks)[-1]["state"] == "done"


@pytest.mark.anyio
@pytest.mark.parametrize("error", [RuntimeError("db down"), OSError("disk"), ValueError("bad")])
@patch('backend.database.db')
async def test_any_failure_storing_a_run_is_logged_and_never_aborts_the_turn(mock_db, mock_registry, tool_handler, error):
    mock_db.get_messages.return_value = []
    mock_db.get_collections.return_value = []
    mock_db.add_collection.side_effect = error
    _agent_setup(tool_handler, mock_registry, [])
    with patch('backend.chat.tool_handler.log_event') as events:
        chunks = [c async for c in tool_handler.handle_tool_calls([{"id": "t1", "function": {"name": "search_web", "arguments": "{}"}}])]
    assert _runs(chunks)[-1]["state"] == "done" and "tool_result" in chunks[-1]
    assert any(c.args[0] == "agent_run_store_error" for c in events.call_args_list)


@pytest.mark.anyio
@patch('backend.database.db')
async def test_a_nested_run_is_stored_under_the_outer_tool_call_with_the_callers_parent_type(mock_db, mock_registry):
    mock_db.get_messages.return_value = []
    mock_db.get_collections.return_value = []
    nested = ToolHandler("chat_123", MagicMock(), parent_message_id="outer-call", parent_type="research")
    nested._user_id = "user-a"
    _agent_setup(nested, mock_registry, [])
    [c async for c in nested.handle_tool_calls([{"id": "inner", "function": {"name": "search_web", "arguments": "{}"}}])]
    kw = mock_db.add_collection.call_args.kwargs
    assert kw["collection_type"] == "agent_runs" and kw["parent_message_id"] == "outer-call" and kw["parent_type"] == "research"
    assert kw["items"][0]["id"] == "inner" and kw["items"][0]["parent_id"] == "outer-call"
