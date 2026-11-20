import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json
from backend.tools.agents.document_agent.agent import is_vision_model, flow_fn
from backend.tools.agents.document_agent.prompts import DOCUMENT_AGENT_VISION_SYSTEM_PROMPT

# Testing is_vision_model
def test_is_vision_model_true():
    with patch('backend.tools.agents.document_agent.agent.load_model_config', return_value={
        'research': {'vision': 'model-vision-1'},
        'general': {'vision': 'model-vision-2', 'vision2': 'model-vision-3'}
    }):
        assert is_vision_model('model-vision-2') is True
        assert is_vision_model('model-vision-1') is True
        assert is_vision_model('non-vision') is False

def test_is_vision_model_exception():
    with patch('backend.tools.agents.document_agent.agent.load_model_config', side_effect=Exception("Error")):
        assert is_vision_model('model-vision-2') is False

# Testing flow_fn
@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.chat_id = "test_chat"
    agent.parent_message_id = "test_parent"
    agent.model = "test_model"
    agent.result = None
    
    async def mock_inference(*args, **kwargs):
        yield "inference_chunk"
    
    agent.run_inference_step = mock_inference
    return agent

@pytest.fixture
def mock_db():
    with patch('backend.tools.agents.base.db') as db_mock:
        with patch('backend.tools.agents.document_agent.agent.db', new=db_mock), \
             patch('backend.tools.agents.document_agent.agent.file_for_chat',
                   side_effect=lambda file_id, chat_id: db_mock.get_file(file_id)):  # by default the file is the caller's
            yield db_mock

@pytest.fixture
def mock_log_tool_call():
    with patch('backend.tools.agents.document_agent.agent.log_tool_call') as log:
        yield log

@pytest.mark.anyio
async def test_flow_fn_file_not_found(mock_agent, mock_db, mock_log_tool_call):
    mock_db.get_file.return_value = None
    gen = flow_fn(mock_agent, "document_agent", "missing_id", "query")
    res = [chunk async for chunk in gen]
    assert "Error: File with ID missing_id not found." in res[0]
    assert "not found" in mock_agent.result

@pytest.mark.anyio
async def test_flow_fn_image_no_vision(mock_agent, mock_db, mock_log_tool_call):
    mock_agent.model = "non-vision-model"
    with patch('backend.tools.agents.document_agent.agent.is_vision_model', return_value=False), \
         patch('backend.tools.agents.document_agent.agent.get_document_agent_tools'):
        mock_db.get_file.return_value = {
            'mime_type': 'image/jpeg',
            'original_filename': 'test.jpg'
        }
        gen = flow_fn(mock_agent, "document_agent", "file_id", "query")
        res = [chunk async for chunk in gen]
        assert any("does not support vision" in r for r in res)

@pytest.mark.anyio
async def test_flow_fn_image_with_vision(mock_agent, mock_db, mock_log_tool_call):
    with patch('backend.tools.agents.document_agent.agent.is_vision_model', return_value=True), \
         patch('backend.tools.agents.document_agent.agent.get_embedding_model'), \
         patch('backend.tools.agents.document_agent.agent.RAGProvider'), \
         patch('backend.tools.agents.document_agent.agent.FileManager') as mock_fm, \
         patch('backend.tools.agents.document_agent.agent.get_document_agent_tools'):
        
        mock_db.get_file.return_value = {
            'mime_type': 'image/jpeg',
            'original_filename': 'test.jpg',
            'stored_filename': 'test_store.jpg'
        }
        mock_db.get_messages.return_value = []
        mock_fm_instance = mock_fm.return_value
        mock_fm_instance.encode_file_for_vision.return_value = ("base64data", "image/jpeg")
        
        captured_kwargs = {}
        async def mock_inf(*args, **kwargs):
            captured_kwargs.update(kwargs)
            yield "inference_chunk"
            
        mock_agent.run_inference_step = mock_inf
        
        gen = flow_fn(mock_agent, "document_agent", "file_id", "query")
        res = [chunk async for chunk in gen]
        
        assert any("Using vision analysis" in r for r in res)
        assert any("inference_chunk" in r for r in res)
        assert captured_kwargs.get("tools") == []
        assert captured_kwargs.get("messages")[0]["content"] == DOCUMENT_AGENT_VISION_SYSTEM_PROMPT.format()

@pytest.mark.anyio
async def test_flow_fn_image_encode_fails(mock_agent, mock_db, mock_log_tool_call):
    with patch('backend.tools.agents.document_agent.agent.is_vision_model', return_value=True), \
         patch('backend.tools.agents.document_agent.agent.get_embedding_model'), \
         patch('backend.tools.agents.document_agent.agent.RAGProvider'), \
         patch('backend.tools.agents.document_agent.agent.FileManager') as mock_fm, \
         patch('backend.tools.agents.document_agent.agent.get_document_agent_tools'):
        
        mock_db.get_file.return_value = {
            'mime_type': 'image/jpeg',
            'original_filename': 'test.jpg',
            'stored_filename': 'test_store.jpg'
        }
        mock_db.get_messages.return_value = []
        mock_fm_instance = mock_fm.return_value
        mock_fm_instance.encode_file_for_vision.return_value = (None, None)
        
        gen = flow_fn(mock_agent, "document_agent", "file_id", "query")
        res = [chunk async for chunk in gen]
        
        assert any("Failed to encode image" in r for r in res)

@pytest.mark.anyio
async def test_flow_fn_text_autonomous_loop(mock_agent, mock_db, mock_log_tool_call):
    with patch('backend.tools.agents.document_agent.agent.get_document_agent_tools', return_value=[{"function": {"name": "test_tool"}}]), \
         patch('backend.tools.agents.document_agent.agent.config') as mock_config:
          
        mock_config.DOCUMENT_AGENT_MAX_TURNS = 5
        mock_config.DOCUMENT_AGENT_FAILSAFE_TURNS = 2
        mock_config.DOCUMENT_AGENT_MAX_TOKENS = 1000
        mock_config.DOCUMENT_AGENT_THINKING_BUDGET = 100
        mock_db.get_file.return_value = {
            'mime_type': 'text/plain',
            'original_filename': 'test.txt'
        }
        mock_db.get_messages.side_effect = [
            [], # check resume
            [], # rebuild history (iteration 1)
            [{"role": "assistant", "content": "done"}], # completion check
            [{"role": "assistant", "content": "done"}]  # final fetch
        ]
        mock_db.get_task_list.return_value = ["task1"]
        
        gen = flow_fn(mock_agent, "document_agent", "file_id", "query")
        res = [chunk async for chunk in gen]
        
        assert any("Initiating investigation" in r for r in res)
        assert mock_agent.result == "done"

@pytest.mark.anyio
async def test_flow_fn_text_turn_limit_reached(mock_agent, mock_db, mock_log_tool_call):
    with patch('backend.tools.agents.document_agent.agent.get_document_agent_tools', return_value=[{"function": {"name": "test_tool"}}]), \
         patch('backend.tools.agents.document_agent.agent.config') as mock_config:
          
        mock_config.DOCUMENT_AGENT_MAX_TURNS = 1
        mock_config.DOCUMENT_AGENT_FAILSAFE_TURNS = 2
        mock_config.DOCUMENT_AGENT_MAX_TOKENS = 1000
        mock_config.DOCUMENT_AGENT_THINKING_BUDGET = 100
        mock_db.get_file.return_value = {
            'mime_type': 'text/plain',
            'original_filename': 'test.txt'
        }
        
        msg_history = [
            {"role": "tool", "name": "test_tool", "content": "result"}
        ]
        
        def mock_get_messages(*args, **kwargs):
            return list(msg_history)
        
        mock_db.get_messages.side_effect = mock_get_messages
        mock_db.get_task_list.return_value = ["task"]
        
        def mock_add_message(*args, **kwargs):
            content = kwargs.get("content", "")
            # BaseAgent injects turn limit warning
            if "TURN LIMIT REACHED" in content:
                msg_history.append({"role": "user", "content": content})
                msg_history.append({"role": "assistant", "content": "final synthesis"})
                
        mock_db.add_message.side_effect = mock_add_message
        
        gen = flow_fn(mock_agent, "document_agent", "file_id", "query")
        res = [chunk async for chunk in gen]
        assert mock_agent.result == "final synthesis"

@pytest.mark.anyio
async def test_flow_fn_no_task_list(mock_agent, mock_db, mock_log_tool_call):
    with patch('backend.tools.agents.document_agent.agent.get_document_agent_tools', return_value=[{"function": {"name": "test_tool"}}]), \
         patch('backend.tools.agents.document_agent.agent.config') as mock_config:
          
        mock_config.DOCUMENT_AGENT_MAX_TURNS = 1
        mock_config.DOCUMENT_AGENT_FAILSAFE_TURNS = 1
        mock_config.DOCUMENT_AGENT_MAX_TOKENS = 1000
        mock_config.DOCUMENT_AGENT_THINKING_BUDGET = 100
        mock_db.get_file.return_value = {
            'mime_type': 'text/plain',
            'original_filename': 'test.txt'
        }
        
        msg_history = []
        mock_db.get_messages.side_effect = lambda *args, **kwargs: list(msg_history)
        
        mock_db.get_task_list.side_effect = [[], [], ["task1"], ["task1"]]
        
        def mock_add_message(*args, **kwargs):
            msg_history.append({"role": kwargs.get("role", "user"), "content": kwargs.get("content", "")})
            if "MUST initialize your task list" in kwargs.get("content", ""):
                msg_history.append({"role": "assistant", "content": "ok"})
            
        mock_db.add_message.side_effect = mock_add_message
        gen = flow_fn(mock_agent, "document_agent", "file_id", "query")
        res = [chunk async for chunk in gen]
        
        assert mock_agent.result == "ok" or "Error: Document agent completed but returned no content." in mock_agent.result

@pytest.mark.anyio
async def test_flow_fn_absolute_limit(mock_agent, mock_db, mock_log_tool_call):
    with patch('backend.tools.agents.document_agent.agent.get_document_agent_tools', return_value=[{"function": {"name": "test_tool"}}]), \
         patch('backend.tools.agents.document_agent.agent.config') as mock_config:
          
        mock_config.DOCUMENT_AGENT_MAX_TURNS = 1
        mock_config.DOCUMENT_AGENT_FAILSAFE_TURNS = 1
        mock_config.DOCUMENT_AGENT_MAX_TOKENS = 1000
        mock_config.DOCUMENT_AGENT_THINKING_BUDGET = 100
        mock_db.get_file.return_value = {
            'mime_type': 'text/plain',
            'original_filename': 'test.txt'
        }
        
        msg_history = [{"role": "assistant", "content": None, "tool_calls": [{"id": "1"}]}]
        mock_db.get_messages.side_effect = lambda *args, **kwargs: list(msg_history)
        mock_db.get_task_list.return_value = ["task"]
        
        def mock_add_message(*args, **kwargs):
            msg_history.append({"role": kwargs.get("role", "event"), "content": kwargs.get("content", "")})
            
        mock_db.add_message.side_effect = mock_add_message
        
        gen = flow_fn(mock_agent, "document_agent", "file_id", "query")
        res = [chunk async for chunk in gen]
        
        assert any("Document Agent Force Terminated. (infinite loop prevention)" in str(m) for m in msg_history)
        assert mock_agent.result is not None

@pytest.mark.anyio
async def test_flow_fn_exception(mock_agent, mock_db, mock_log_tool_call):
    mock_db.get_messages.return_value = []
    mock_db.get_file.side_effect = Exception("DB error")
    gen = flow_fn(mock_agent, "document_agent", "file_id", "query")
    res = [chunk async for chunk in gen]
    
    assert mock_agent.result == "Document agent failed. Try again." and "DB error" not in mock_agent.result
    mock_db.add_message.assert_any_call(
        chat_id="test_chat",
        role='event',
        content='Document Agent failed. Try again.',
        parent_id="test_parent",
        parent_type='document_agent'
    )

@pytest.mark.anyio
async def test_flow_fn_get_messages_exception(mock_agent, mock_db, mock_log_tool_call):
    mock_db.get_messages.side_effect = Exception("DB fetch error")
    gen = flow_fn(mock_agent, "document_agent", "file_id", "query")
    res = [chunk async for chunk in gen]
    
    assert mock_agent.result == "Document agent failed. Try again." and "DB fetch error" not in mock_agent.result
    mock_db.add_message.assert_any_call(
        chat_id="test_chat",
        role='event',
        content='Document Agent failed. Try again.',
        parent_id="test_parent",
        parent_type='document_agent'
    )

@pytest.mark.anyio
async def test_flow_fn_pdf_hint(mock_agent, mock_db, mock_log_tool_call):
    with patch('backend.tools.agents.document_agent.agent.get_document_agent_tools', return_value=[]), \
         patch('backend.tools.agents.document_agent.agent.config') as mock_config:
          
        mock_db.get_file.return_value = {
            'mime_type': 'application/pdf',
            'original_filename': 'test.pdf'
        }
        mock_db.get_messages.side_effect = [
            [],
            [],
            [{"role": "assistant", "content": "done"}],
            [{"role": "assistant", "content": "done"}]
        ]
        mock_db.get_task_list.return_value = ["task"]
        
        gen = flow_fn(mock_agent, "document_agent", "file_id", "query")
        res = [chunk async for chunk in gen]
        
        assert any("Initiating investigation" in r for r in res)

@pytest.mark.anyio
async def test_flow_fn_already_warned(mock_agent, mock_db, mock_log_tool_call):
    with patch('backend.tools.agents.document_agent.agent.get_document_agent_tools', return_value=[{"function": {"name": "test_tool"}}]), \
         patch('backend.tools.agents.document_agent.agent.config') as mock_config:
          
        mock_config.DOCUMENT_AGENT_MAX_TURNS = 1
        mock_config.DOCUMENT_AGENT_FAILSAFE_TURNS = 2
        mock_config.DOCUMENT_AGENT_MAX_TOKENS = 1000
        mock_config.DOCUMENT_AGENT_THINKING_BUDGET = 100
        mock_db.get_file.return_value = {
            'mime_type': 'text/plain',
            'original_filename': 'test.txt'
        }
        
        msg_history = [
            {"role": "tool", "name": "test_tool", "content": "res"},
            {"role": "user", "content": "[SYSTEM: TURN LIMIT REACHED]"}
        ]
        mock_db.get_messages.side_effect = lambda *args, **kwargs: list(msg_history)
        mock_db.get_task_list.return_value = ["task"]
        
        captured_tools = []
        async def mock_inf(*args, **kwargs):
            captured_tools.append(kwargs.get("tools"))
            yield "done"
            msg_history.append({"role": "assistant", "content": "done"})
            
        mock_agent.run_inference_step = mock_inf
        
        gen = flow_fn(mock_agent, "document_agent", "file_id", "query")
        res = [chunk async for chunk in gen]
        
        assert [] in captured_tools or None in captured_tools

@pytest.mark.anyio
async def test_flow_fn_no_history_break(mock_agent, mock_db, mock_log_tool_call):
    with patch('backend.tools.agents.document_agent.agent.get_document_agent_tools', return_value=[]):
        mock_db.get_file.return_value = {
            'mime_type': 'text/plain',
            'original_filename': 'test.txt'
        }
        mock_db.get_messages.side_effect = [[], [], [], []] 
        
        gen = flow_fn(mock_agent, "document_agent", "file_id", "query")
        res = [chunk async for chunk in gen]
        
        assert mock_agent.result == "Error: Document agent completed but returned no content."


@pytest.mark.anyio
async def test_flow_fn_does_not_open_a_file_outside_the_callers_chats(mock_agent, mock_db, mock_log_tool_call):
    """An image of another user's must never reach the vision model: the file is "not found" before anything is read."""
    mock_db.get_messages.return_value = []
    mock_db.get_file.return_value = {"mime_type": "image/png", "original_filename": "secret.png", "stored_filename": "s.png", "chat_id": "chat-of-b"}
    with patch('backend.tools.agents.document_agent.agent.file_for_chat', return_value=None) as owned, \
         patch('backend.tools.agents.document_agent.agent.FileManager') as file_manager, \
         patch('backend.tools.agents.document_agent.agent.is_vision_model', return_value=True):
        res = [chunk async for chunk in flow_fn(mock_agent, "document_agent", "file_of_b", "query")]
    owned.assert_called_once_with("file_of_b", "test_chat")
    assert "not found" in mock_agent.result and "secret.png" not in str(res) + mock_agent.result
    file_manager.assert_not_called()  # the image is never encoded



@pytest.mark.anyio
async def test_a_document_failure_logs_the_detail_and_the_event_row_has_no_exception_text(mock_agent, mock_db, mock_log_tool_call):
    mock_db.get_messages.return_value = []
    mock_db.get_file.side_effect = Exception("/secret/place DB error")
    with patch('backend.tools.agents.document_agent.agent.log_event') as events:
        [c async for c in flow_fn(mock_agent, "document_agent", "file_id", "query")]
    assert events.call_args.args[0] == "document_agent_error" and "DB error" in events.call_args.args[1]["error"]
    assert all("secret" not in str(c) for c in mock_db.add_message.call_args_list)


def test_the_documents_status_lines_use_the_ellipsis_character():
    import inspect
    from backend.tools.agents.document_agent import agent as document_agent_module
    source = inspect.getsource(document_agent_module)
    for line in (l for l in source.splitlines() if 'yield f"Event:' in l):
        assert "..." not in line and "…" in line
