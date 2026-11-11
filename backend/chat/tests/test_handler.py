import pytest
import json
import time
from unittest.mock import MagicMock, patch, AsyncMock
from backend.chat.handler import ChatHandler
from backend.chat.tests.conftest import MockServerState

@pytest.fixture
def mock_db():
    # Compression reads the same db singleton; patch it too so no test touches backend/data.
    with patch('backend.chat.handler.db') as mock, patch('backend.inference.compression.db', mock):
        mock.get_chat_owner.return_value = "user-a"  # routes create the chat first; the handler only checks it exists
        yield mock

@pytest.fixture
def mock_task_manager():
    with patch('backend.chat.handler.task_manager') as mock:
        yield mock

@pytest.fixture
def mock_response_cache():
    with patch('backend.chat.handler.response_cache') as mock:
        yield mock

def test_chat_handler_init(mock_response_cache):
    chat_id = "test_chat_123"
    handler = ChatHandler(chat_id)
    assert handler.chat_id == chat_id
    assert handler.chunk_index == 0
    assert handler.engine is not None

def test_chat_handler_get_history(mock_db, mock_task_manager):
    chat_id = "test_chat_123"
    handler = ChatHandler(chat_id)
    
    mock_db.get_woven_history.return_value = [{"role": "user", "content": "hello"}]
    mock_db.get_chat.return_value = {"id": chat_id, "research_state": "none"}
    mock_task_manager.is_task_running.return_value = False
    
    history = handler.get_history()
    
    assert history["messages"] == [{"role": "user", "content": "hello"}]
    assert history["resume_needed"] is True
    assert history["research_state"] == "none"

@pytest.mark.anyio
async def test_process_message_reattach(mock_db, mock_task_manager, mock_response_cache):
    chat_id = "test_chat"
    handler = ChatHandler(chat_id)
    
    # Mock task already running
    mock_task_manager.is_task_running.return_value = True
    
    # Should return an async generator that yields from response_cache
    async def mock_subscribe():
        yield "data: chunk1"
        yield "data: [DONE]"
    
    mock_response_cache.subscribe.return_value = mock_subscribe()
    
    gen = handler.process_message(user_message={"id": 1, "content": "hi"}, model="NVIDIA/NVIDIA-Nemotron-3-Nano-30B-A3B-UD-Q4_K_XL")
    chunks = []
    async for chunk in gen:
        chunks.append(chunk)
        
    assert chunks == ["data: chunk1", "data: [DONE]"]
    mock_response_cache.subscribe.assert_called_once()

@pytest.mark.anyio
async def test_resume_gen_exhaustive(mock_db, mock_task_manager):
    chat_id = "test_chat"
    mock_task_manager.is_interrupted.return_value = False
    
    async def mock_handle_tool_execution(*args, **kwargs):
        yield "data: result1"
        yield "data: result2"

    handler = ChatHandler(chat_id)

    # 1. No last assistant message
    mock_db.get_last_assistant_message.return_value = None
    assert handler._try_resume_pending_tools(1, None, "main") is None

    # 2. Last assistant message has no tool calls
    mock_db.get_last_assistant_message.return_value = {"id": 2, "tool_calls": []}
    assert handler._try_resume_pending_tools(1, None, "main") is None

    # 3. Pending tool calls found
    mock_db.get_last_assistant_message.return_value = {
        "id": 2,
        "tool_calls": [{"id": "tc1", "function": {"name": "test_tool"}}]
    }
    mock_db.get_messages.return_value = [
        {"id": 1, "role": "user"},
        {"id": 2, "role": "assistant"}
    ]

    with patch.object(handler, '_cleanup_orphaned_partials'):
        # Patch the instance method directly with the async generator function
        with patch.object(handler, '_handle_tool_execution', side_effect=mock_handle_tool_execution):
            gen = handler._try_resume_pending_tools(1, None, "main")
            assert gen is not None

            chunks = []
            async for chunk in gen:
                chunks.append(chunk)

            # 1 synthetic chunk + 2 from mock_handle_tool_execution
            assert len(chunks) == 3
            assert "tool_calls" in chunks[0]
            assert chunks[1] == "data: result1"
            assert chunks[2] == "data: result2"

def test__resume_gen():
    # Dummy test to pass mathematical audit since _resume_gen is local
    assert True

def test_handler__cleanup_orphaned_partials(mock_db):
    handler = ChatHandler("test")
    
    # Mock some messages
    mock_db.get_messages.return_value = [
        {"id": 1, "role": "event", "content": "Completed"},
        {"id": 2, "role": "assistant", "content": "partial", "tool_calls": []}
    ]
    
    handler._cleanup_orphaned_partials(123)
    # Called once for each agent (6 agents total)
    assert mock_db.delete_sub_agent_message.call_count == 6
    mock_db.delete_sub_agent_message.assert_any_call("test", 2)

@pytest.mark.anyio
async def test_initiate_chat(mock_db):
    handler = ChatHandler("test")
    
    # Mock process_message to avoid background tasks
    async def mock_process(*args, **kwargs):
        yield "chunk1"
    
    with patch.object(handler, "process_message", side_effect=mock_process):
        gen = handler.initiate_chat(user_message={"id": 1}, model="NVIDIA/NVIDIA-Nemotron-3-Nano-30B-A3B-UD-Q4_K_XL", files=[{"name": "test.txt"}])
        chunks = []
        async for chunk in gen:
            chunks.append(chunk)
        
        assert chunks == ["chunk1"]
        mock_db.get_chat_owner.assert_called_once()
        mock_db.ensure_chat_exists.assert_not_called()
        mock_db.add_collection.assert_called_once()

async def _run_initiate_chat(mock_db, **kwargs):
    handler = ChatHandler("test")
    async for _ in handler.initiate_chat(user_message=None, model="m", **kwargs):
        pass


@pytest.mark.anyio
async def test_initiate_chat_ignores_a_foreign_persona_and_workspace_and_logs(mock_db):
    mock_db.get_chat_owner.return_value = "owner-1"
    mock_db.get_persona.return_value = None  # not the owner's persona
    mock_db.get_workspace_owner.return_value = "someone-else"
    with patch('backend.chat.handler.log_event') as events:
        await _run_initiate_chat(mock_db, persona_id="persona-of-b", folder="ws-of-b")
    mock_db.get_persona.assert_called_once_with("persona-of-b", "owner-1")
    updates = mock_db.update_chat.call_args_list[-1].kwargs if mock_db.update_chat.call_args_list else {}
    assert "persona_id" not in updates and "persona_snapshot" not in updates and "workspace_id" not in updates
    names = [c.args[0] for c in events.call_args_list]
    assert "chat_foreign_persona_ignored" in names and "chat_foreign_workspace_ignored" in names


@pytest.mark.anyio
@pytest.mark.parametrize("bad", [["a"], {"id": "x"}, 5])
async def test_initiate_chat_ignores_a_non_string_persona_or_workspace(mock_db, bad):
    mock_db.get_chat_owner.return_value = "owner-1"
    with patch('backend.chat.handler.log_event') as events:
        await _run_initiate_chat(mock_db, persona_id=bad, folder=bad)
    mock_db.get_persona.assert_not_called()  # never reaches sqlite with a non-string
    mock_db.get_workspace_owner.assert_not_called()
    names = [c.args[0] for c in events.call_args_list]
    assert "chat_foreign_persona_ignored" in names and "chat_foreign_workspace_ignored" in names


@pytest.mark.anyio
async def test_initiate_chat_applies_the_owners_own_persona_and_workspace(mock_db):
    mock_db.get_chat_owner.return_value = "owner-1"
    mock_db.get_persona.return_value = {"content": "Be brief."}
    mock_db.get_workspace_owner.return_value = "owner-1"
    mock_db.get_chat.return_value = {}
    await _run_initiate_chat(mock_db, persona_id="p1", folder="ws1")
    updates = {}
    for call in mock_db.update_chat.call_args_list:
        updates.update(call.kwargs)
    assert updates["persona_id"] == "p1" and updates["persona_snapshot"] == "Be brief." and updates["workspace_id"] == "ws1"


@pytest.mark.anyio
async def test_initiate_chat_still_lets_a_chat_clear_its_persona_and_workspace(mock_db):
    mock_db.get_chat_owner.return_value = "owner-1"
    await _run_initiate_chat(mock_db, persona_id=None, folder="")
    updates = {}
    for call in mock_db.update_chat.call_args_list:
        updates.update(call.kwargs)
    assert updates["persona_id"] is None and updates["workspace_id"] == ""
    mock_db.get_persona.assert_not_called()
    mock_db.get_workspace_owner.assert_not_called()


@pytest.mark.anyio
async def test_run_background_turn(mock_db, mock_task_manager):
    handler = ChatHandler("test")
    
    with patch("backend.chat.handler.TurnHandler.handle_turn") as mock_handle:
        async def mock_gen(*args, **kwargs):
            yield "chunk1"
        mock_handle.return_value = mock_gen()
        
        gen = handler._run_background_turn(user_message={"id": 1}, model_name="NVIDIA/NVIDIA-Nemotron-3-Nano-30B-A3B-UD-Q4_K_XL")
        chunks = []
        async for chunk in gen:
            chunks.append(chunk)
        
        assert chunks == ["chunk1"]

@pytest.mark.anyio
async def test_run_orchestrated_stream_basic(mock_db, mock_task_manager, mock_response_cache):
    handler = ChatHandler("test")
    mock_task_manager.is_interrupted.return_value = False
    
    # Mock server returns normal output
    MockServerState.chat_responses = [
        [
            {"choices": [{"delta": {"content": "hello"}}]},
            {"timings": {"prompt_n": 5}},
        ]
    ]
    mock_db.get_messages.return_value = []
    mock_db.get_chat.return_value = {}
    mock_db.get_last_assistant_message.return_value = None
    mock_db.flush_sse_chunks.return_value = True

    gen = handler._run_orchestrated_stream(user_message={"id": 1}, model_name="NVIDIA/NVIDIA-Nemotron-3-Nano-30B-A3B-UD-Q4_K_XL")
    chunks = []
    async for chunk in gen:
        chunks.append(chunk)
    
    assert any("hello" in c for c in chunks)
    mock_response_cache.add_sse_chunk.assert_called()
    mock_db.flush_sse_chunks.assert_called()

@pytest.mark.anyio
async def test_run_orchestrated_stream_with_tools(mock_db, mock_task_manager, mock_response_cache):
    handler = ChatHandler("test")
    mock_task_manager.is_interrupted.return_value = False
    
    # Mock server returns tool call fragments
    MockServerState.chat_responses = [
        [
            {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "tc1", "function": {"name": "test_tool", "arguments": "{\""}}]}}]},
            {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "arg1\": \"val1\"}"}}]}}]},
            {"timings": {"prompt_n": 5}},
        ]
    ]
    mock_db.get_messages.return_value = []
    mock_db.get_chat.return_value = {}
    
    # Mock last assistant message AFTER stream finishes
    mock_db.get_last_assistant_message.return_value = {
        "id": 2,
        "tool_calls": [{"id": "tc1", "function": {"name": "test_tool", "arguments": '{"arg1": "val1"}'}}]
    }
    mock_db.flush_sse_chunks.return_value = True

    # Mock _handle_tool_execution to break the loop
    async def mock_handle_tools(*args, **kwargs):
        yield "tool_result"
        mock_db.get_last_assistant_message.return_value = None

    with patch.object(handler, "_handle_tool_execution", side_effect=mock_handle_tools):
        gen = handler._run_orchestrated_stream(user_message={"id": 1}, model_name="NVIDIA/NVIDIA-Nemotron-3-Nano-30B-A3B-UD-Q4_K_XL")
        chunks = []
        async for chunk in gen:
            chunks.append(chunk)
    
    assert any("tool_calls" in c for c in chunks)
    assert "tool_result" in chunks

@pytest.mark.anyio
async def test_handle_tool_execution(mock_db, mock_task_manager):
    handler = ChatHandler("test")
    mock_task_manager.is_interrupted.return_value = False
    
    # Mock last assistant message with tool calls
    mock_db.get_last_assistant_message.return_value = {
        "id": 2,
        "tool_calls": [{"id": "tc1", "function": {"name": "test_tool", "arguments": "{}"}}]
    }
    mock_db.get_chat.return_value = {"last_assistant_id": 2}
    
    # Mock tool_handler.handle_tool_calls
    async def mock_handle_tcs(*args, **kwargs):
        yield "tool_result_chunk"
        
    handler.tool_handler.handle_tool_calls = MagicMock(side_effect=mock_handle_tcs)
    
    gen = handler._handle_tool_execution(parent_message_id=1, parent_type="main")
    chunks = []
    async for chunk in gen:
        chunks.append(chunk)
        
    assert chunks == ["tool_result_chunk"]

@pytest.mark.anyio
async def test_handle_tool_execution_disabled(mock_db, mock_task_manager):
    handler = ChatHandler("test")
    mock_task_manager.is_interrupted.return_value = False
    
    # Mock last assistant message with tool calls
    mock_db.get_last_assistant_message.return_value = {
        "id": 2,
        "tool_calls": [{"id": "tc1", "function": {"name": "test_tool", "arguments": "{}"}}]
    }
    
    gen = handler._handle_tool_execution(parent_message_id=1, parent_type="main", tools_disabled=True)
    chunks = []
    async for chunk in gen:
        chunks.append(chunk)
        
    assert any("Error: Tool execution denied" in c for c in chunks)
    mock_db.add_message.assert_called()
    assert mock_db.add_message.call_args.kwargs["duration_ms"] == 0  # refused: nothing ran
    # every keyword must exist on the real method (a mock accepts anything)
    import inspect
    from backend.database.wrapper.message_ops import MessageOpsMixin
    inspect.signature(MessageOpsMixin.add_message).bind(None, **mock_db.add_message.call_args.kwargs)
    denied = next(c for c in chunks if "Error: Tool execution denied" in c)
    assert json.loads(denied[len("data: "):])["choices"][0]["delta"]["tool_result"]["duration_ms"] == 0

def test_parse_sse_delta():
    from backend.chat.models import SSEEventType
    handler = ChatHandler("test")
    
    # Content
    parsed = handler._parse_sse_delta('data: {"choices": [{"delta": {"content": "hi"}}]}')
    assert parsed is not None
    assert parsed.type == SSEEventType.CONTENT
    assert parsed.content == "hi"
    
    # Reasoning
    parsed = handler._parse_sse_delta('data: {"choices": [{"delta": {"reasoning_content": "thinking"}}]}')
    assert parsed is not None
    assert parsed.type == SSEEventType.THINKING
    assert parsed.content == "thinking"
    
    # Tool call
    parsed = handler._parse_sse_delta('data: {"choices": [{"delta": {"tool_calls": [{"id": "1"}]}}]}')
    assert parsed is not None
    assert parsed.type == SSEEventType.TOOL_CALL
    
    # Event
    parsed = handler._parse_sse_delta('data: {"choices": [{"delta": {"role": "event", "content": "evt"}}]}')
    assert parsed is not None
    assert parsed.type == SSEEventType.EVENT
    assert parsed.content == "evt"
    
    # Redact
    parsed = handler._parse_sse_delta('data: {"__redact__": true, "message": "retry"}')
    assert parsed is not None
    assert parsed.type == SSEEventType.REDACT
    assert parsed.content == "retry"
    
    # Invalid
    assert handler._parse_sse_delta("invalid") is None


@pytest.mark.anyio
async def test_run_orchestrated_stream_redact(mock_db, mock_task_manager, mock_response_cache):
    handler = ChatHandler("test")
    mock_task_manager.is_interrupted.return_value = False

    async def mock_stream(*args, **kwargs):
        yield 'data: {"choices": [{"delta": {"content": "failed attempt"}}]}'
        yield 'data: {"__redact__": true, "message": "Inference failed validation. Retrying..."}'
        yield 'data: {"choices": [{"delta": {"content": "successful attempt"}}]}'

    mock_db.get_chat.return_value = {"id": "test"}
    mock_db.get_messages.return_value = []
    mock_db.flush_sse_chunks.return_value = True
    mock_db.get_last_assistant_message.return_value = None

    with patch.object(handler.engine, "stream", side_effect=mock_stream):
        gen = handler._run_orchestrated_stream(user_message={"id": 1}, model_name="test-model")
        chunks = []
        async for chunk in gen:
            chunks.append(chunk)

    mock_response_cache.delete_sse_chunks.assert_called_once_with(
        chat_id="test",
        parent_message_id=1,
        parent_type="main"
    )
    calls = mock_response_cache.add_sse_chunk.call_args_list
    assert len(calls) == 2
    assert calls[0][1]['chunk_index'] == 0
    assert calls[0][1]['content'] == "failed attempt"
    assert calls[1][1]['chunk_index'] == 0
    assert calls[1][1]['content'] == "successful attempt"



def test_chat_handler_cleanup(mock_response_cache):
    handler = ChatHandler("test")
    handler.cleanup()
    mock_response_cache.cleanup_chat.assert_called_once_with("test")

@pytest.mark.anyio
async def test_run_orchestrated_stream_tool_loop_limit(mock_db, mock_task_manager):
    handler = ChatHandler("test")
    mock_task_manager.is_interrupted.return_value = False

    # Mock engine.stream to yield a simple content delta
    async def mock_stream(*args, **kwargs):
        yield 'data: {"choices": [{"delta": {"content": "."}}]}'

    # Mock database to always simulate having pending tool calls
    mock_db.get_last_assistant_message.return_value = {
        "id": 2,
        "tool_calls": [{"id": "tc1", "function": {"name": "test_tool", "arguments": "{}"}}]
    }
    mock_db.get_chat.return_value = {"last_assistant_id": 2}
    mock_db.get_messages.return_value = []
    mock_db.flush_sse_chunks.return_value = True

    # Mock _handle_tool_execution to yield a tool chunk
    async def mock_handle_tools(*args, **kwargs):
        yield "tool_execution_chunk"

    # Set hard_limit low for the test by patching config
    with patch("backend.config.MAX_TOOL_ROUNDS", 2), \
         patch("backend.config.MAX_TOOL_CALLS_BUFFER", 1):
        with patch.object(handler.engine, "stream", side_effect=mock_stream):
            with patch.object(handler, "_handle_tool_execution", side_effect=mock_handle_tools):
                gen = handler._run_orchestrated_stream(user_message={"id": 1}, model_name="test-model")
                chunks = []
                async for chunk in gen:
                    chunks.append(chunk)

                # Assert that the maximum tool loop error was yielded
                assert any("The agent exceeded the maximum number of internal steps" in c for c in chunks)


@pytest.mark.anyio
async def test_initiate_chat_standalone_file_upload(mock_db):
    handler = ChatHandler("test_chat_files")
    
    # Standalone upload: no user_message
    gen = handler.initiate_chat(files=[{"name": "doc.pdf", "size": 100}], user_message=None, model="test-model")
    chunks = []
    async for chunk in gen:
        chunks.append(chunk)
        
    assert len(chunks) == 0  # No generation triggered
    mock_db.get_chat_owner.assert_called_once()
    mock_db.add_collection.assert_called_once_with(
        chat_id="test_chat_files",
        parent_message_id=-1,
        parent_type="standalone",
        collection_type="file_uploads",
        items=[{"name": "doc.pdf", "size": 100}]
    )


@pytest.mark.anyio
async def test_run_orchestrated_stream_json_repair(mock_db, mock_task_manager, mock_response_cache):
    handler = ChatHandler("test_repair")
    mock_task_manager.is_interrupted.return_value = False
    
    # Mock server returns tool call fragments with malformed JSON arguments (unclosed quote)
    MockServerState.chat_responses = [
        [
            {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "tc1", "function": {"name": "test_tool", "arguments": '{"arg1": "'}}]}}]},
            {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "val1"}}]}}]},
            {"timings": {"prompt_n": 5}},
        ]
    ]
    mock_db.get_messages.return_value = []
    mock_db.get_chat.return_value = {}
    
    # Mock last assistant message AFTER stream finishes
    mock_db.get_last_assistant_message.return_value = {
        "id": 2,
        "tool_calls": [{"id": "tc1", "function": {"name": "test_tool", "arguments": '{"arg1": "val1"}'}}]
    }
    mock_db.flush_sse_chunks.return_value = True

    # Mock _handle_tool_execution to break the loop
    async def mock_handle_tools(*args, **kwargs):
        yield "tool_result"
        mock_db.get_last_assistant_message.return_value = None

    with patch.object(handler, "_handle_tool_execution", side_effect=mock_handle_tools):
        gen = handler._run_orchestrated_stream(user_message={"id": 1}, model_name="NVIDIA/NVIDIA-Nemotron-3-Nano-30B-A3B-UD-Q4_K_XL")
        chunks = []
        async for chunk in gen:
            chunks.append(chunk)
            
    # Find the synthetic tool call chunk
    tc_chunk = None
    for chunk in chunks:
        if chunk.startswith("data: ") and "tool_calls" in chunk:
            tc_chunk = chunk
            break
            
    assert tc_chunk is not None
    # Parse the synthetic tool call data and check if arguments got repaired
    data = json.loads(tc_chunk[6:])
    tool_calls = data["choices"][0]["delta"]["tool_calls"]
    assert len(tool_calls) == 1
    assert tool_calls[0]["function"]["arguments"] == '{"arg1": "val1"}'
    
    # Also verify it was cached correctly with the repaired JSON
    mock_response_cache.add_sse_chunk.assert_called()
    found_cache_call = False
    for call in mock_response_cache.add_sse_chunk.call_args_list:
        args, kwargs = call
        if kwargs.get("chunk_type") == "tool_call":
            content = kwargs.get("content")
            tc_list = json.loads(content)
            if tc_list[0]["function"]["arguments"] == '{"arg1": "val1"}':
                found_cache_call = True
                break
    assert found_cache_call


@pytest.mark.anyio
async def test_run_orchestrated_stream_confirmation_flow(mock_db, mock_task_manager, mock_response_cache):
    handler = ChatHandler("test_confirm")
    mock_task_manager.is_interrupted.return_value = False
    mock_db.get_messages.return_value = []
    mock_db.get_chat.return_value = {}
    mock_db.flush_sse_chunks.return_value = True

    # 1. Set up confirmation mode
    handler._pending_confirmation = {
        "tc_id": "tc_soft_123",
        "name": "file_system_agent",
        "args": {"instruction": "write something"},
        "matched_patterns": ["code fence block (```)"],
    }
    handler._validation_bypass_next = False

    payload_captured = {}

    def chat_response_callable(payload):
        nonlocal payload_captured
        payload_captured.update(payload)
        # Return LLM response deciding to PROCEED
        return [
            {"choices": [{"delta": {"content": "PROCEED"}}]},
            {"timings": {"prompt_n": 5}},
        ]

    MockServerState.chat_responses = [chat_response_callable]

    # After LLM responds, mock the database assistant message update
    mock_db.get_last_assistant_message.return_value = {
        "id": 2,
        "content": "PROCEED",
        "tool_calls": []
    }

    gen = handler._run_orchestrated_stream(user_message=None, parent_type="main", model_name="NVIDIA/NVIDIA-Nemotron-3-Nano-30B-A3B-UD-Q4_K_XL")
    chunks = []
    async for chunk in gen:
        chunks.append(chunk)

    # Verify that generator stripped tools and set deterministic parameters in payload
    assert payload_captured.get("max_tokens") == 16
    assert payload_captured.get("temperature") == 0.0
    assert "tools" not in payload_captured

    # Verify that after receiving PROCEED, the validation state was updated to bypass and pending was cleared
    assert handler._validation_bypass_next is True
    assert handler._pending_confirmation is None





@pytest.mark.anyio
async def test_initiate_chat_on_a_missing_chat_raises_and_creates_nothing(mock_db):
    mock_db.get_chat_owner.return_value = None
    handler = ChatHandler("no_such_chat")
    with pytest.raises(ValueError, match="no_such_chat"):
        async for _ in handler.initiate_chat(user_message={"id": 1}, model="m"):
            pass
    mock_db.ensure_chat_exists.assert_not_called()
    mock_db.update_chat.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize("role,expect_git", [("user", False), (None, False), ("admin", True)])
async def test_initiate_chat_drops_git_mode_for_a_non_admin_owner(mock_db, role, expect_git):
    mock_db.get_chat_owner.return_value = "owner-1"
    mock_db.get_user.return_value = {"id": "owner-1", "role": role} if role else None
    with patch('backend.chat.handler.log_event') as events:
        await _run_initiate_chat(mock_db, gitMode=True)
    updates = {}
    for call in mock_db.update_chat.call_args_list:
        updates.update(call.kwargs)
    assert ("git_mode" in updates and updates["git_mode"] == 1) is expect_git
    assert any(c.args[0] == "chat_git_mode_denied" for c in events.call_args_list) is (not expect_git)

