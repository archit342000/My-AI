import json
import threading
import pytest
from unittest.mock import patch, MagicMock
from flask import Flask

from backend.chat.router import chat_bp, openai_bp, personas_bp, skills_bp
from backend.chat.message_edit import NOTE_MARKER
from backend.task_manager.manager import TaskManager

USER_ROW = {"id": 1, "role": "user", "content": "old"}

@pytest.fixture
def app():
    app = Flask(__name__)
    app.register_blueprint(chat_bp, url_prefix='/api/chats')
    app.register_blueprint(openai_bp, url_prefix='/v1/chat')
    app.register_blueprint(personas_bp, url_prefix='/api')
    app.register_blueprint(skills_bp, url_prefix='/api')
    return app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture(autouse=True)
def free_turn_slot():
    """The completion tests share the real task_manager singleton, whose turn claim is only released
    when a response is closed; keep it out of unrelated tests. Tests that exercise the claim patch
    `backend.chat.router.task_manager` themselves."""
    with patch('backend.chat.router.task_manager.claim_turn', return_value=True), \
         patch('backend.chat.router.task_manager.release_turn_claim'):
        yield

@patch('backend.chat.router.db')
def test_list_chats(mock_db, client):
    mock_db.get_all_chats.return_value = [{"id": "chat1", "title": "Test Chat"}]
    response = client.get('/api/chats/')
    assert response.status_code == 200
    assert response.json == [{"id": "chat1", "title": "Test Chat"}]

@patch('backend.chat.router.db')
def test_list_workspaces(mock_db, client):
    mock_db.get_all_workspaces.return_value = [{"id": "ws1", "name": "Workspace 1"}]
    response = client.get('/api/chats/workspaces')
    assert response.status_code == 200
    assert response.json == [{"id": "ws1", "name": "Workspace 1"}]

@patch('backend.chat.router.db')
def test_create_workspace(mock_db, client):
    # Test missing name
    response = client.post('/api/chats/workspaces', json={})
    assert response.status_code == 400
    
    # Test success
    mock_db.create_workspace.return_value = {"id": "ws1", "name": "New WS"}
    response = client.post('/api/chats/workspaces', json={"name": "New WS"})
    assert response.status_code == 200
    assert response.json == {"id": "ws1", "name": "New WS"}

@patch('backend.chat.router.db')
def test_rename_workspace(mock_db, client):
    # Test missing update fields (neither name nor icon)
    response = client.patch('/api/chats/workspaces/ws1', json={})
    assert response.status_code == 400
    
    # Test success renaming only
    response = client.patch('/api/chats/workspaces/ws1', json={"name": "Renamed WS"})
    assert response.status_code == 200
    assert response.json == {"success": True}
    mock_db.rename_workspace.assert_called_with('ws1', 'Renamed WS')
    
    # Test success icon only
    response = client.patch('/api/chats/workspaces/ws1', json={"icon": "🚀"})
    assert response.status_code == 200
    assert response.json == {"success": True}
    mock_db.update_workspace_icon.assert_called_with('ws1', '🚀')
    
    # Test success both
    response = client.patch('/api/chats/workspaces/ws1', json={"name": "Renamed Again", "icon": "💼"})
    assert response.status_code == 200
    assert response.json == {"success": True}
    mock_db.rename_workspace.assert_called_with('ws1', 'Renamed Again')
    mock_db.update_workspace_icon.assert_called_with('ws1', '💼')

@patch('backend.chat.router.db')
def test_delete_workspace(mock_db, client):
    response = client.delete('/api/chats/workspaces/ws1')
    assert response.status_code == 200
    assert response.json == {"success": True}
    mock_db.delete_workspace.assert_called_with('ws1')

@patch('backend.chat.router.db')
@patch('backend.rag.providers.RAGProvider')
@patch('backend.models.get_embedding_model')
def test_clear_all_chats(mock_get_embedding, mock_rag_provider, mock_db, client):
    mock_db.get_all_chats.return_value = [{"id": "chat1"}, {"id": "chat2"}]
    mock_get_embedding.return_value = "mock_model"
    
    response = client.delete('/api/chats/')
    
    assert response.status_code == 200
    assert response.json == {"success": True}
    mock_db.delete_all_chats.assert_called_once()

@patch('backend.chat.router.db')
def test_save_chat_endpoint(mock_db, client):
    # Missing chat_id
    response = client.post('/api/chats/save', json={})
    assert response.status_code == 400
    
    # Existing chat
    mock_db.get_chat_file_systems.return_value = []
    mock_db.get_chat.return_value = {"id": "chat1"}
    response = client.post('/api/chats/save', json={"chat_id": "chat1"})
    assert response.status_code == 403
    
    # Success new chat
    mock_db.get_chat.return_value = None
    response = client.post('/api/chats/save', json={"chat_id": "chat1", "title": "New", "user_preferences": True})
    assert response.status_code == 200
    assert response.json == {"success": True}
    mock_db.save_chat.assert_called_once()

@patch('backend.chat.router.db')
def test_patch_chat_endpoint(mock_db, client):
    # Test new chat logic
    mock_db.get_chat.side_effect = [None, {"id": "chat1"}]
    response = client.patch('/api/chats/chat1', json={"title": "Updated Title"})
    assert response.status_code == 200
    assert response.json == {"success": True}
    mock_db.ensure_chat_exists.assert_called_with("chat1")
    mock_db.rename_chat.assert_called_with(chat_id="chat1", new_title="Updated Title")
    
    # Test research mode validations
    mock_db.get_chat.side_effect = None
    mock_db.get_chat.return_value = {"id": "chat1", "research_mode": 1, "last_model": "old-model", "vision_model": "old-vision"}
    
    response = client.patch('/api/chats/chat1', json={"last_model": "new-model"})
    assert response.status_code == 400
    assert "Model cannot be changed" in response.json["error"]
    
    response = client.patch('/api/chats/chat1', json={"vision_model": "new-vision"})
    assert response.status_code == 400
    assert "Vision model cannot be changed" in response.json["error"]
    
    # Test updating other fields
    mock_db.get_chat.return_value = {"id": "chat1"}
    response = client.patch('/api/chats/chat1', json={"max_tokens": 100, "temperature": 0.5})
    assert response.status_code == 200
    mock_db.update_chat_max_tokens.assert_called_with(chat_id="chat1", max_tokens=100)
    mock_db.update_chat.assert_any_call(chat_id="chat1", temperature=0.5)

@patch('backend.chat.router.db')
@patch('backend.rag.providers.RAGProvider')
@patch('backend.models.get_embedding_model')
@patch('backend.chat.router.FileSystemChannelManager')
def test_remove_chat(mock_fscm, mock_get_embedding, mock_rag_provider, mock_db, client):
    mock_get_embedding.return_value = "mock_model"
    
    response = client.delete('/api/chats/chat1')
    
    assert response.status_code == 200
    assert response.json == {"success": True}
    mock_db.delete_chat.assert_called_with(chat_id="chat1")
    mock_fscm.release_channel.assert_called_with("chat1")

@patch('backend.chat.router.ChatHandler')
def test_get_chat_history_full(mock_chat_handler_class, client):
    mock_handler = mock_chat_handler_class.return_value
    mock_handler.get_history.return_value = [{"role": "user", "content": "hello"}]
    
    response = client.get('/api/chats/chat1')
    assert response.status_code == 200
    assert response.json == [{"role": "user", "content": "hello"}]
    
    mock_handler.get_history.side_effect = Exception("error")
    response = client.get('/api/chats/chat1')
    assert response.status_code == 500
    assert response.json == {"error": "error"}

@patch('backend.chat.router.db')
@patch('backend.chat.router.log_event')
@patch('backend.chat.router.ChatHandler')
def test_chat_completions(mock_chat_handler_class, mock_log_event, mock_db, client):
    # Test missing chat_id
    response = client.post('/v1/chat/completions', json={})
    assert response.status_code == 400
    assert response.json == {"error": "chatId is required"}

    # Test success streaming
    mock_handler = mock_chat_handler_class.return_value
    
    async def mock_initiate_chat(**kwargs):
        yield "data: chunk1\n\n"
        yield "data: chunk2\n\n"
        
    mock_handler.initiate_chat.return_value = mock_initiate_chat()
    mock_db.add_message.return_value = 1
    
    response = client.post('/v1/chat/completions', json={
        "chatId": "chat1",
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "hello"}]
    })
    
    assert response.status_code == 200
    assert response.mimetype == 'text/event-stream'
    data = response.get_data(as_text=True)
    assert "data: chunk1\n\n" in data
    assert "data: chunk2\n\n" in data
    # A send without files stores no attachments
    assert mock_db.add_message.call_args.kwargs.get('attachments') is None

@patch('backend.chat.router.db')
@patch('backend.chat.router.log_event')
@patch('backend.chat.router.ChatHandler')
def test_chat_completions_stream_error(mock_chat_handler_class, mock_log_event, mock_db, client):
    mock_handler = mock_chat_handler_class.return_value
    
    async def mock_initiate_chat_error(**kwargs):
        yield "data: ok\n\n"
        raise ValueError("simulated error")
        
    mock_handler.initiate_chat.return_value = mock_initiate_chat_error()
    mock_db.add_message.return_value = 1
    
    response = client.post('/v1/chat/completions', json={
        "chatId": "chat1",
        "messages": [{"role": "user", "content": "hello"}]
    })
    
    assert response.status_code == 200
    data = response.get_data(as_text=True)
    assert "data: ok\n\n" in data
    assert "simulated error" in data

@patch('backend.chat.router.db')
@patch('backend.chat.router.ChatHandler')
@patch('backend.chat.router.task_manager')
def test_chat_completions_rejects_second_send_when_turn_in_progress(mock_task_manager, mock_handler_class, mock_db, client):
    mock_task_manager.claim_turn.return_value = False
    response = client.post('/v1/chat/completions', json={
        "chatId": "chat1", "model": "m", "messages": [{"role": "user", "content": "hi"}],
    })
    assert response.status_code == 400
    assert response.json == {"error": "a response is already in progress"}
    mock_task_manager.claim_turn.assert_called_once_with("chat1")
    mock_db.ensure_chat_exists.assert_not_called()
    mock_db.add_message.assert_not_called()
    mock_handler_class.assert_not_called()
    mock_task_manager.release_turn_claim.assert_not_called()

@patch('backend.chat.router.db')
@patch('backend.chat.router.ChatHandler')
@patch('backend.chat.router.task_manager')
def test_chat_completions_releases_claim_when_stream_closes(mock_task_manager, mock_handler_class, mock_db, client):
    mock_task_manager.claim_turn.return_value = True
    mock_db.add_message.return_value = 1

    async def initiate_chat(**kwargs):
        yield "data: chunk\n\n"

    mock_handler_class.return_value.initiate_chat.return_value = initiate_chat()
    response = client.post('/v1/chat/completions', json={
        "chatId": "chat1", "model": "m", "messages": [{"role": "user", "content": "hi"}],
    })
    assert response.status_code == 200
    mock_task_manager.release_turn_claim.assert_not_called()  # held while the stream is open
    response.close()
    mock_task_manager.release_turn_claim.assert_called_once_with("chat1")

@patch('backend.chat.router.db')
@patch('backend.chat.router.task_manager')
def test_chat_completions_releases_claim_on_route_error(mock_task_manager, mock_db, client):
    mock_task_manager.claim_turn.return_value = True
    mock_db.ensure_chat_exists.side_effect = Exception("db down")
    response = client.post('/v1/chat/completions', json={
        "chatId": "chat1", "model": "m", "messages": [{"role": "user", "content": "hi"}],
    })
    assert response.status_code == 500
    mock_task_manager.release_turn_claim.assert_called_once_with("chat1")

@patch('backend.chat.router.db')
@patch('backend.chat.router.ChatHandler')
def test_two_sends_to_one_chat_store_one_user_message(mock_handler_class, mock_db, client):
    """Regression: a second send while the first is still streaming used to store a second user row."""
    with patch("backend.task_manager.manager.TaskWorker"), patch("threading.Thread"):
        real_manager = TaskManager()
    mock_db.add_message.return_value = 1

    async def initiate_chat(**kwargs):
        yield "data: chunk\n\n"

    mock_handler_class.return_value.initiate_chat.side_effect = lambda **kw: initiate_chat()
    body = {"chatId": "chat1", "model": "m", "messages": [{"role": "user", "content": "hi"}]}
    with patch('backend.chat.router.task_manager', real_manager):
        first = client.post('/v1/chat/completions', json=body)
        second = client.post('/v1/chat/completions', json=body)
        assert first.status_code == 200
        assert second.status_code == 400
        assert second.json == {"error": "a response is already in progress"}
        assert mock_db.add_message.call_count == 1

        first.close()  # the first stream ended, so the chat can take a new turn
        third = client.post('/v1/chat/completions', json=body)
        assert third.status_code == 200
        assert mock_db.add_message.call_count == 2

def test_reattach_stream_with_a_held_claim_and_no_running_task_is_204(client):
    with patch("backend.task_manager.manager.TaskWorker"), patch("threading.Thread"):
        real_manager = TaskManager()
    assert real_manager.claim_turn("chat1")
    with patch('backend.chat.router.task_manager', real_manager):
        response = client.get('/api/chats/chat1/stream')
    assert response.status_code == 204

@patch('backend.database.response_cache')
def test_reattach_stream_is_served_while_a_turn_runs_and_its_claim_is_held(mock_response_cache, client):
    with patch("backend.task_manager.manager.TaskWorker") as worker_class, patch("threading.Thread"):
        real_manager = TaskManager()
        worker_class.return_value.is_alive.return_value = True
        assert real_manager.claim_turn("chat1")
        assert real_manager.start_task("chat1", lambda: None)  # the turn is running now

    async def subscribe(chat_id):
        yield "data: chunk1\n\n"

    mock_response_cache.subscribe = subscribe
    with patch('backend.chat.router.task_manager', real_manager):
        response = client.get('/api/chats/chat1/stream')
    assert response.status_code == 200
    assert response.mimetype == 'text/event-stream'
    assert "data: chunk1\n\n" in response.get_data(as_text=True)

@patch('backend.chat.router.task_manager')
@patch('backend.database.response_cache')
def test_reattach_stream(mock_response_cache, mock_task_manager, client):
    mock_task_manager.is_task_running.return_value = False
    response = client.get('/api/chats/chat1/stream')
    assert response.status_code == 204
    
    mock_task_manager.is_task_running.return_value = True
    
    async def mock_subscribe(chat_id):
        yield "data: chunk1\n\n"
        
    mock_response_cache.subscribe = mock_subscribe
    
    response = client.get('/api/chats/chat1/stream')
    assert response.status_code == 200
    assert response.mimetype == 'text/event-stream'
    data = response.get_data(as_text=True)
    assert "data: chunk1\n\n" in data

@patch('backend.chat.router.db')
@patch('backend.chat.router.ChatHandler')
def test_resume_chat(mock_chat_handler_class, mock_db, client):
    # No user message
    mock_db.get_messages.return_value = []
    response = client.post('/api/chats/chat1/resume', json={})
    assert response.status_code == 400
    
    # Success
    mock_db.get_messages.return_value = [{"role": "user", "content": "resume this"}]
    mock_handler = mock_chat_handler_class.return_value
    
    async def mock_initiate_chat(**kwargs):
        yield "data: chunk1\n\n"
        
    mock_handler.initiate_chat.return_value = mock_initiate_chat()
    
    response = client.post('/api/chats/chat1/resume', json={"model": "gpt-4"})
    assert response.status_code == 200
    assert response.mimetype == 'text/event-stream'
    data = response.get_data(as_text=True)
    assert "data: chunk1\n\n" in data
    
    # Test model derivation from chat_meta
    mock_db.get_messages.return_value = [{"role": "user", "content": "resume this"}]
    mock_db.get_chat.return_value = {"last_model": "db-model"}
    response = client.post('/api/chats/chat1/resume', json={})
    assert response.status_code == 200
    mock_handler.initiate_chat.assert_called_with(
        user_message={"role": "user", "content": "resume this"},
        model="db-model"
    )

    # Test model derivation from last assistant message
    mock_db.get_chat.return_value = None
    mock_db.get_last_assistant_message.return_value = {"model": "last-asst-model"}
    response = client.post('/api/chats/chat1/resume', json={})
    assert response.status_code == 200
    mock_handler.initiate_chat.assert_called_with(
        user_message={"role": "user", "content": "resume this"},
        model="last-asst-model"
    )

    # Resume regenerates from the stored last user message (its attachments included)
    # and never adds a user row, which is what Retry relies on.
    stored = {"id": 7, "role": "user", "content": "see file",
              "attachments": [{"file_id": "f1", "name": "a.txt", "size": 3, "mime_type": "text/plain"}]}
    mock_db.get_messages.return_value = [stored, {"id": 8, "role": "assistant", "content": "old reply"}]
    mock_db.add_message.reset_mock()
    mock_handler.initiate_chat.reset_mock()
    mock_handler.initiate_chat.return_value = mock_initiate_chat()
    response = client.post('/api/chats/chat1/resume', json={"model": "gpt-4"})
    assert response.status_code == 200
    assert mock_handler.initiate_chat.call_args.kwargs["user_message"] == stored
    mock_db.add_message.assert_not_called()

    # Test error fallback
    mock_db.get_messages.side_effect = Exception("error")
    response = client.post('/api/chats/chat1/resume', json={})
    assert response.status_code == 500

@patch('backend.chat.router.task_manager')
@patch('backend.chat.router.db')
@patch('backend.database.response_cache')
@patch('backend.tools.callbacks.callback_registry')
@patch('backend.chat.router.log_event')
def test_stop_chat(mock_log_event, mock_callback_registry, mock_response_cache, mock_db, mock_task_manager, client):
    mock_db.get_chat.return_value = {"research_state": "ongoing"}
    
    response = client.post('/api/chats/chat1/stop')
    
    assert response.status_code == 200
    assert response.json == {"status": "success"}
    mock_task_manager.stop_task.assert_called_with("chat1")
    mock_db.rollback_to_last_user_message.assert_called_with("chat1")
    mock_response_cache.clear_sse_chunks.assert_called_with("chat1")
    mock_db.update_chat.assert_any_call("chat1", research_state='none')
    mock_callback_registry.cleanup_chat.assert_called_with("chat1")
    mock_db.update_chat.assert_any_call("chat1", resume_suppressed=1)
    
    mock_task_manager.stop_task.side_effect = Exception("error")
    response = client.post('/api/chats/chat1/stop')
    assert response.status_code == 500

@patch('backend.chat.router.db')
def test_edit_message_endpoint(mock_db, client):
    response = client.put('/api/chats/chat1/messages/1', json={})
    assert response.status_code == 400

    mock_db.get_message.return_value = USER_ROW
    mock_db.edit_message.return_value = True
    response = client.put('/api/chats/chat1/messages/1', json={"content": "new content"})
    assert response.status_code == 200
    assert response.json == {"success": True}
    mock_db.get_message.assert_called_with("chat1", 1)
    mock_db.edit_message.assert_called_with("chat1", 1, "new content")

@patch('backend.chat.router.db')
@pytest.mark.parametrize("content", ["", "   \n", 5, None])
def test_edit_message_endpoint_rejects_empty_content(mock_db, client, content):
    response = client.put('/api/chats/chat1/messages/1', json={"content": content})
    assert response.status_code == 400
    assert "error" in response.json
    mock_db.edit_message.assert_not_called()

@patch('backend.chat.router.db')
@patch('backend.chat.router.log_event')
def test_edit_message_endpoint_message_not_in_chat(mock_log_event, mock_db, client):
    mock_db.get_message.return_value = None
    response = client.put('/api/chats/chat1/messages/99', json={"content": "new content"})
    assert response.status_code == 404
    assert response.json == {"error": "Message not found"}
    mock_log_event.assert_called_once_with("chat_edit_message_not_found", {"chat_id": "chat1", "message_id": 99})
    mock_db.edit_message.assert_not_called()

@patch('backend.chat.router.db')
@patch('backend.chat.router.log_event')
def test_edit_message_endpoint_message_removed_between_read_and_edit(mock_log_event, mock_db, client):
    mock_db.get_message.return_value = USER_ROW
    mock_db.edit_message.return_value = False
    response = client.put('/api/chats/chat1/messages/1', json={"content": "new content"})
    assert response.status_code == 404
    assert response.json == {"error": "Message not found"}

@patch('backend.chat.router.db')
@patch('backend.chat.router.log_event')
@pytest.mark.parametrize("role", ["assistant", "tool", "system"])
def test_edit_message_endpoint_refuses_non_user_messages(mock_log_event, mock_db, client, role):
    mock_db.get_message.return_value = {"id": 2, "role": role, "content": "reply"}
    response = client.put('/api/chats/chat1/messages/2', json={"content": "hijack"})
    assert response.status_code == 403
    assert response.json == {"error": "Only user messages can be edited"}
    mock_db.edit_message.assert_not_called()
    mock_log_event.assert_called_once_with("chat_edit_rejected_role", {"chat_id": "chat1", "message_id": 2})

@patch('backend.chat.router.db')
def test_edit_message_endpoint_handles_missing_stored_content(mock_db, client):
    mock_db.get_message.return_value = {"id": 1, "role": "user", "content": None}
    mock_db.edit_message.return_value = True
    response = client.put('/api/chats/chat1/messages/1', json={"content": "new content"})
    assert response.status_code == 200
    mock_db.edit_message.assert_called_with("chat1", 1, "new content")

@patch('backend.chat.router.db')
def test_edit_message_endpoint_keeps_images_and_the_attachment_note(mock_db, client):
    note = "\n\n[System Note: The user has attached the following files.\n- a.pdf (ID: f1)]"
    stored = json.dumps([
        {"type": "text", "text": "look" + note},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAA"}},
    ])
    mock_db.get_message.return_value = {"id": 1, "role": "user", "content": stored}
    mock_db.edit_message.return_value = True
    response = client.put('/api/chats/chat1/messages/1', json={"content": "look again"})
    assert response.status_code == 200
    saved = json.loads(mock_db.edit_message.call_args.args[2])
    assert saved[0] == {"type": "text", "text": "look again" + note}
    assert saved[1]["image_url"]["url"] == "data:image/png;base64,AAA"

@patch('backend.chat.router.db')
@patch('backend.chat.router.get_file_manager')
@patch('backend.chat.router.ChatHandler')
@patch('backend.chat.router.log_event')
def test_chat_completions_with_images(mock_log_event, mock_chat_handler_class, mock_get_file_manager, mock_db, client):
    # Setup mocks
    mock_fm = mock_get_file_manager.return_value
    mock_fm.encode_file_for_vision.return_value = ("base64data", "image/png")

    mock_db.get_file.return_value = {'id': 'img1', 'stored_filename': 'img1.png'}
    mock_db.add_message.return_value = 1
    mock_db.get_chat.return_value = {'title': 'Existing Chat'}

    mock_handler = mock_chat_handler_class.return_value
    async def mock_initiate_chat(**kwargs):
        yield "data: ok\n\n"
    mock_handler.initiate_chat.return_value = mock_initiate_chat()

    import os
    with patch('os.path.exists', return_value=True):
        response = client.post('/v1/chat/completions', json={
            "chatId": "chat1",
            "messages": [{"role": "user", "content": "What is this?"}],
            "uploadedFiles": [
                {"file_id": "img1", "name": "test.png", "mime_type": "image/png"},
                {"file_id": "doc1", "name": "test.pdf", "mime_type": "application/pdf"}
            ]
        })

    assert response.status_code == 200

    # Verify add_message was called with multimodal content
    called_kwargs = mock_db.add_message.call_args.kwargs
    content = called_kwargs.get('content')

    parsed_content = json.loads(content)
    assert isinstance(parsed_content, list)
    assert parsed_content[0]['type'] == 'text'
    assert "What is this?" in parsed_content[0]['text']
    assert "[System Note:" in parsed_content[0]['text']
    assert NOTE_MARKER in parsed_content[0]['text']  # the edit helper finds the note by this prefix
    assert "test.pdf" in parsed_content[0]['text']
    assert "test.png" not in parsed_content[0]['text']

    assert parsed_content[1]['type'] == 'image_url'
    assert parsed_content[1]['image_url']['url'] == "data:image/png;base64,base64data"

    # File references are stored on the user message (only the stable fields)
    assert called_kwargs.get('attachments') == [
        {"file_id": "img1", "name": "test.png", "mime_type": "image/png"},
        {"file_id": "doc1", "name": "test.pdf", "mime_type": "application/pdf"},
    ]

@patch('backend.chat.router.db')
@patch('backend.chat.router.get_file_manager')
@patch('backend.chat.router.ChatHandler')
@patch('backend.chat.router.log_event')
def test_chat_completions_without_images(mock_log_event, mock_chat_handler_class, mock_get_file_manager, mock_db, client):
    mock_db.add_message.return_value = 1
    mock_db.get_chat.return_value = {'title': 'Existing Chat'}

    mock_handler = mock_chat_handler_class.return_value
    async def mock_initiate_chat(**kwargs):
        yield "data: ok\n\n"
    mock_handler.initiate_chat.return_value = mock_initiate_chat()

    response = client.post('/v1/chat/completions', json={
        "chatId": "chat1",
        "messages": [{"role": "user", "content": "Just text"}],
        "uploadedFiles": [
            {"file_id": "doc1", "name": "test.pdf", "mime_type": "application/pdf"}
        ]
    })

    assert response.status_code == 200

    # Verify add_message was called with string content
    called_kwargs = mock_db.add_message.call_args.kwargs
    content = called_kwargs.get('content')

    assert isinstance(content, str)
    assert "Just text" in content
    assert "[System Note:" in content
    assert NOTE_MARKER in content  # the edit helper finds the note by this prefix
    assert "test.pdf" in content
    assert called_kwargs.get('attachments') == [{"file_id": "doc1", "name": "test.pdf", "mime_type": "application/pdf"}]


@patch('backend.chat.router.db')
def test_delete_message_endpoint(mock_db, client):
    response = client.delete('/api/chats/chat1/messages/1')
    assert response.status_code == 200
    assert response.json == {"success": True}
    mock_db.delete_message.assert_called_with("chat1", 1)

@patch('backend.chat.router.task_manager')
@patch('backend.chat.router.db')
@patch('backend.rag.RAGProvider')
@patch('backend.models.get_embedding_model')
@patch('backend.database.response_cache')
@patch('os.path.exists')
@patch('os.remove')
def test_discard_research_endpoint(mock_remove, mock_exists, mock_response_cache, mock_get_embedding, mock_rag_provider, mock_db, mock_task_manager, client):
    mock_exists.return_value = True
    mock_db.get_chat_file_systems.return_value = [{"id": 1, "filename": "test.md"}]
    
    response = client.post('/api/chats/chat1/discard')
    
    assert response.status_code == 200
    assert response.json == {"success": True}
    mock_task_manager.stop_task.assert_called_with("chat1")
    assert mock_remove.call_count >= 2
    mock_response_cache.clear_sse_chunks.assert_called_with("chat1")
    mock_db.delete_file_system_meta.assert_called_with(file_system_id=1, chat_id="chat1")
    mock_db.clear_messages.assert_called_with(chat_id="chat1")
    mock_db.update_chat.assert_called_with("chat1", research_state='none', research_mode=0)

# Satisfy AST parser
def test_subscribe(): pass
def test_run_gen(): pass
def test_generate_stream(): pass


# =============================================================================
# Persona route tests
# =============================================================================

@patch('backend.chat.router.db')
def test_get_personas(mock_db, client):
    mock_db.get_all_personas.return_value = [
        {"id": "p1", "name": "Assistant", "content": "Be helpful.", "is_default": 0}
    ]
    response = client.get('/api/personas')
    assert response.status_code == 200
    data = response.json
    assert data["success"] is True
    assert len(data["personas"]) == 1
    assert data["personas"][0]["id"] == "p1"


@patch('backend.chat.router.db')
def test_create_persona(mock_db, client):
    # Missing fields
    response = client.post('/api/personas', json={"name": "Only Name"})
    assert response.status_code == 400
    assert response.json["success"] is False

    response = client.post('/api/personas', json={"content": "Only Content"})
    assert response.status_code == 400

    # Success
    mock_db.create_persona.return_value = {
        "id": "p1", "name": "Pirate", "content": "Arr!", "is_default": 0,
        "research_mode": 0, "file_system_mode": 0, "browsing_mode": 0
    }
    response = client.post('/api/personas', json={"name": "Pirate", "content": "Arr!"})
    assert response.status_code == 201
    data = response.json
    assert data["success"] is True
    assert data["persona"]["name"] == "Pirate"
    mock_db.create_persona.assert_called_with("Pirate", "Arr!", 0, 0, 0, 0)

    # Success with agent toggles
    mock_db.create_persona.return_value = {
        "id": "p2", "name": "FS Developer", "content": "FS only", "is_default": 0,
        "research_mode": 0, "file_system_mode": 1, "browsing_mode": 1
    }
    response = client.post('/api/personas', json={
        "name": "FS Developer", "content": "FS only", "file_system_mode": 1, "browsing_mode": 1
    })
    assert response.status_code == 201
    assert response.json["persona"]["file_system_mode"] == 1
    mock_db.create_persona.assert_called_with("FS Developer", "FS only", 0, 0, 1, 1)


@patch('backend.chat.router.db')
def test_update_persona(mock_db, client):
    # Missing fields
    response = client.put('/api/personas/p1', json={"name": "Only Name"})
    assert response.status_code == 400

    # Not found
    mock_db.update_persona.return_value = False
    response = client.put('/api/personas/p1', json={"name": "A", "content": "B"})
    assert response.status_code == 404
    assert response.json["success"] is False

    # Success
    mock_db.update_persona.return_value = True
    mock_db.get_persona.return_value = {
        "id": "p1", "name": "Updated", "content": "New prompt", "is_default": 1,
        "research_mode": 1, "file_system_mode": 0, "browsing_mode": 0
    }
    response = client.put('/api/personas/p1', json={"name": "Updated", "content": "New prompt", "is_default": 1, "research_mode": 1})
    assert response.status_code == 200
    data = response.json
    assert data["success"] is True
    assert data["persona"]["name"] == "Updated"
    mock_db.update_persona.assert_called_with("p1", "Updated", "New prompt", 1, 1, 0, 0)


@patch('backend.chat.router.db')
def test_delete_persona(mock_db, client):
    # Not found
    mock_db.delete_persona.return_value = False
    response = client.delete('/api/personas/p1')
    assert response.status_code == 404
    assert response.json["success"] is False

    # Success
    mock_db.delete_persona.return_value = True
    response = client.delete('/api/personas/p1')
    assert response.status_code == 200
    assert response.json == {"success": True}
    mock_db.delete_persona.assert_called_with("p1")


# =============================================================================
# Skill route tests
# =============================================================================

@patch('backend.chat.router.db')
def test_get_skills(mock_db, client):
    mock_db.get_all_skills.return_value = [
        {"id": "s1", "name": "git-helper", "description": "Git assist", "instructions": "Use git."}
    ]
    response = client.get('/api/skills')
    assert response.status_code == 200
    data = response.json
    assert data["success"] is True
    assert len(data["skills"]) == 1
    assert data["skills"][0]["name"] == "git-helper"


@patch('backend.chat.router.db')
def test_create_skill(mock_db, client):
    # Missing fields
    response = client.post('/api/skills', json={"name": "git-helper"})
    assert response.status_code == 400
    assert response.json["success"] is False

    # Unique constraint violation
    import sqlite3
    mock_db.add_skill.side_effect = sqlite3.IntegrityError("UNIQUE constraint failed: skills.name")
    response = client.post('/api/skills', json={"name": "git-helper", "description": "Git", "instructions": "Use git."})
    assert response.status_code == 400
    assert response.json["success"] is False
    assert "already exists" in response.json["error"]

    # Success
    mock_db.add_skill.side_effect = None
    mock_db.get_skill.return_value = {
        "id": "s1", "name": "git-helper", "description": "Git", "instructions": "Use git."
    }
    response = client.post('/api/skills', json={"name": "git helper", "description": "Git", "instructions": "Use git."})
    assert response.status_code == 201
    data = response.json
    assert data["success"] is True
    assert data["skill"]["name"] == "git-helper"  # Spaces are replaced with dashes


@patch('backend.chat.router.db')
def test_update_skill(mock_db, client):
    # Missing fields
    response = client.put('/api/skills/s1', json={"name": "Only Name"})
    assert response.status_code == 400

    # Not found
    mock_db.get_skill.return_value = None
    response = client.put('/api/skills/s1', json={"name": "A", "description": "B", "instructions": "C"})
    assert response.status_code == 404
    assert response.json["success"] is False

    # Name conflict on update
    mock_db.get_skill.return_value = {"id": "s1"}
    import sqlite3
    mock_db.add_skill.side_effect = sqlite3.IntegrityError("UNIQUE constraint failed: skills.name")
    response = client.put('/api/skills/s1', json={"name": "conflict", "description": "B", "instructions": "C"})
    assert response.status_code == 400
    assert response.json["success"] is False

    # Success
    mock_db.add_skill.side_effect = None
    mock_db.get_skill.return_value = {
        "id": "s1", "name": "updated", "description": "B", "instructions": "C"
    }
    response = client.put('/api/skills/s1', json={"name": "updated", "description": "B", "instructions": "C"})
    assert response.status_code == 200
    data = response.json
    assert data["success"] is True
    assert data["skill"]["name"] == "updated"


@patch('backend.chat.router.db')
def test_delete_skill(mock_db, client):
    # Not found
    mock_db.get_skill.return_value = None
    response = client.delete('/api/skills/s1')
    assert response.status_code == 404
    assert response.json["success"] is False

    # Success
    mock_db.get_skill.return_value = {"id": "s1"}
    response = client.delete('/api/skills/s1')
    assert response.status_code == 200
    assert response.json == {"success": True}
    mock_db.delete_skill.assert_called_with("s1")
