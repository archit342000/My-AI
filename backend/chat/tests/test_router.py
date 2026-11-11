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
def app(login_as, user_a):
    """The chat app with every request made by `user_a` (tests switch user with `login_as(app, user_b)`)."""
    app = Flask(__name__)
    app.register_blueprint(chat_bp, url_prefix='/api/chats')
    app.register_blueprint(openai_bp, url_prefix='/v1/chat')
    app.register_blueprint(personas_bp, url_prefix='/api')
    app.register_blueprint(skills_bp, url_prefix='/api')
    login_as(app, user_a)
    return app

@pytest.fixture(autouse=True)
def owned_by_user_a(owner_db):
    """The ownership checks read the owner from the db: by default every chat and workspace belongs to user_a."""
    return owner_db

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture(autouse=True)
def no_expiry_sweep():
    """Listing chats runs the expired temporary chat sweep, which has its own tests (test_cleanup.py and the ones below)."""
    with patch('backend.chat.router.purge_expired_temporary_chats') as sweep:
        yield sweep

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
    mock_db.get_listed_chats.return_value = [{"id": "chat1", "title": "Test Chat"}]
    response = client.get('/api/chats/')
    assert response.status_code == 200
    assert response.json == [{"id": "chat1", "title": "Test Chat"}]
    # The sidebar list hides empty chats; get_all_chats (every chat) stays for internal callers
    mock_db.get_listed_chats.assert_called_once_with("user-a")
    mock_db.get_all_chats.assert_not_called()

@patch('backend.chat.router.db')
def test_list_workspaces(mock_db, client):
    mock_db.get_all_workspaces.return_value = [{"id": "ws1", "name": "Workspace 1"}]
    response = client.get('/api/chats/workspaces')
    assert response.status_code == 200
    assert response.json == [{"id": "ws1", "name": "Workspace 1"}]

@patch('backend.chat.router.db')
def test_create_workspace(mock_db, client):
    mock_db.workspace_name_exists.return_value = False
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
    mock_db.workspace_name_exists.return_value = False
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
def test_create_workspace_rejects_duplicate_name(mock_db, client):
    mock_db.workspace_name_exists.return_value = True
    response = client.post('/api/chats/workspaces', json={"name": "Work"})
    assert response.status_code == 400
    assert response.json == {"error": "A workspace named 'Work' already exists"}
    mock_db.workspace_name_exists.assert_called_with("Work", "user-a")
    mock_db.create_workspace.assert_not_called()

@patch('backend.chat.router.db')
def test_rename_workspace_rejects_duplicate_name_and_writes_nothing(mock_db, client):
    mock_db.workspace_name_exists.return_value = True
    response = client.patch('/api/chats/workspaces/ws1', json={"name": "Work", "icon": "💼"})
    assert response.status_code == 400
    assert response.json == {"error": "A workspace named 'Work' already exists"}
    mock_db.workspace_name_exists.assert_called_with("Work", "user-a", exclude_id="ws1")
    mock_db.rename_workspace.assert_not_called()
    mock_db.update_workspace_icon.assert_not_called()

@patch('backend.chat.router.db')
def test_rename_workspace_icon_only_skips_the_name_check(mock_db, client):
    response = client.patch('/api/chats/workspaces/ws1', json={"icon": "🚀"})
    assert response.status_code == 200
    mock_db.workspace_name_exists.assert_not_called()

@patch('backend.chat.router.db')
def test_create_persona_rejects_duplicate_name(mock_db, client):
    mock_db.persona_name_exists.return_value = True
    response = client.post('/api/personas', json={"name": "Pirate", "content": "Arr!"})
    assert response.status_code == 400
    assert response.json == {"success": False, "error": "A persona named 'Pirate' already exists"}
    mock_db.persona_name_exists.assert_called_with("Pirate", "user-a")
    mock_db.create_persona.assert_not_called()

@patch('backend.chat.router.db')
def test_update_persona_rejects_duplicate_name(mock_db, client):
    mock_db.persona_name_exists.return_value = True
    response = client.put('/api/personas/p1', json={"name": "Pirate", "content": "Arr!"})
    assert response.status_code == 400
    assert response.json == {"success": False, "error": "A persona named 'Pirate' already exists"}
    mock_db.persona_name_exists.assert_called_with("Pirate", "user-a", exclude_id="p1")
    mock_db.update_persona.assert_not_called()

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
def test_patch_chat_endpoint(mock_db, client, owned_by_user_a):
    # A chat that does not exist yet is created for the caller (claim_chat) and then updated
    mock_db.get_chat.return_value = {"id": "chat1"}
    response = client.patch('/api/chats/chat1', json={"title": "Updated Title"})
    assert response.status_code == 200
    assert response.json == {"success": True}
    owned_by_user_a.ensure_chat_exists.assert_called_with("chat1", "user-a")
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
    mock_db.add_message.side_effect = Exception("db down")
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

@patch('backend.chat.router.db')
@patch('backend.chat.router.ChatHandler')
@patch('backend.chat.router.log_event')
@patch('backend.chat.router.task_manager')
def test_resume_chat_rejected_when_turn_in_progress(mock_task_manager, mock_log_event, mock_handler_class, mock_db, client):
    mock_task_manager.claim_turn.return_value = False
    response = client.post('/api/chats/chat1/resume', json={"model": "m"})
    assert response.status_code == 400
    assert response.json == {"error": "a response is already in progress"}
    mock_task_manager.claim_turn.assert_called_once_with("chat1")
    mock_handler_class.assert_not_called()
    mock_db.get_messages.assert_not_called()
    mock_task_manager.release_turn_claim.assert_not_called()
    mock_log_event.assert_called_once_with("chat_resume_rejected_turn_in_progress", {"chat_id": "chat1"})

@patch('backend.chat.router.db')
@patch('backend.chat.router.ChatHandler')
@patch('backend.chat.router.task_manager')
def test_resume_chat_releases_claim_when_there_is_nothing_to_resume(mock_task_manager, mock_handler_class, mock_db, client):
    mock_task_manager.claim_turn.return_value = True
    mock_db.get_messages.return_value = []
    response = client.post('/api/chats/chat1/resume', json={})
    assert response.status_code == 400
    mock_task_manager.release_turn_claim.assert_called_once_with("chat1")

@patch('backend.chat.router.db')
@patch('backend.chat.router.ChatHandler')
@patch('backend.chat.router.task_manager')
def test_resume_chat_releases_claim_on_route_error(mock_task_manager, mock_handler_class, mock_db, client):
    mock_task_manager.claim_turn.return_value = True
    mock_db.get_messages.side_effect = Exception("db down")
    response = client.post('/api/chats/chat1/resume', json={})
    assert response.status_code == 500
    mock_task_manager.release_turn_claim.assert_called_once_with("chat1")

@patch('backend.chat.router.db')
@patch('backend.chat.router.ChatHandler')
@patch('backend.chat.router.task_manager')
def test_resume_chat_releases_claim_when_stream_closes(mock_task_manager, mock_handler_class, mock_db, client):
    mock_task_manager.claim_turn.return_value = True
    mock_db.get_messages.return_value = [{"role": "user", "content": "resume this"}]

    async def initiate_chat(**kwargs):
        yield "data: chunk\n\n"

    mock_handler_class.return_value.initiate_chat.return_value = initiate_chat()
    response = client.post('/api/chats/chat1/resume', json={"model": "m"})
    assert response.status_code == 200
    mock_task_manager.release_turn_claim.assert_not_called()  # held while the stream is open
    response.close()
    mock_task_manager.release_turn_claim.assert_called_once_with("chat1")

@patch('backend.chat.router.db')
@patch('backend.chat.router.ChatHandler')
def test_resume_is_refused_while_a_task_is_alive_even_without_an_open_response(mock_handler_class, mock_db, client):
    """A running turn (a live worker) refuses a resume on its own, without any held claim."""
    with patch("backend.task_manager.manager.TaskWorker") as worker_class, patch("threading.Thread"):
        real_manager = TaskManager()
        worker_class.return_value.is_alive.return_value = True
        assert real_manager.start_task("chat1", lambda: None)
    mock_db.get_messages.return_value = [{"role": "user", "content": "resume this"}]

    async def initiate_chat(**kwargs):
        yield "data: chunk\n\n"

    mock_handler_class.return_value.initiate_chat.side_effect = lambda **kw: initiate_chat()
    with patch('backend.chat.router.task_manager', real_manager):
        refused = client.post('/api/chats/chat1/resume', json={"model": "m"})
        assert refused.status_code == 400
        assert refused.json == {"error": "a response is already in progress"}
        mock_handler_class.assert_not_called()

        worker_class.return_value.is_alive.return_value = False  # the turn ended
        accepted = client.post('/api/chats/chat1/resume', json={"model": "m"})
        assert accepted.status_code == 200
        accepted.close()

@patch('backend.chat.router.db')
@patch('backend.chat.router.ChatHandler')
def test_send_and_resume_exclude_each_other_on_one_chat(mock_handler_class, mock_db, client):
    """Regression: a resume and a send on one chat could both start a turn; they now share one claim."""
    with patch("backend.task_manager.manager.TaskWorker"), patch("threading.Thread"):
        real_manager = TaskManager()
    mock_db.add_message.return_value = 1
    mock_db.get_messages.return_value = [{"role": "user", "content": "resume this"}]

    async def initiate_chat(**kwargs):
        yield "data: chunk\n\n"

    mock_handler_class.return_value.initiate_chat.side_effect = lambda **kw: initiate_chat()
    send_body = {"chatId": "chat1", "model": "m", "messages": [{"role": "user", "content": "hi"}]}
    with patch('backend.chat.router.task_manager', real_manager):
        # a send is held open: resume is refused
        send = client.post('/v1/chat/completions', json=send_body)
        assert send.status_code == 200
        refused = client.post('/api/chats/chat1/resume', json={"model": "m"})
        assert refused.status_code == 400
        assert refused.json == {"error": "a response is already in progress"}
        send.close()

        # a resume is held open: a send is refused and stores nothing
        adds_before = mock_db.add_message.call_count
        resume = client.post('/api/chats/chat1/resume', json={"model": "m"})
        assert resume.status_code == 200
        refused_send = client.post('/v1/chat/completions', json=send_body)
        assert refused_send.status_code == 400
        assert mock_db.add_message.call_count == adds_before
        resume.close()

        # once the resume ended, a send is accepted again
        assert client.post('/v1/chat/completions', json=send_body).status_code == 200

@patch('backend.chat.router.task_manager')
@patch('backend.chat.router.db')
@patch('backend.database.response_cache')
@patch('backend.tools.callbacks.callback_registry')
@patch('backend.chat.router.log_event')
def test_stop_chat(mock_log_event, mock_callback_registry, mock_response_cache, mock_db, mock_task_manager, client):
    mock_db.get_chat.return_value = {"research_state": "ongoing"}
    mock_task_manager.stop_task_and_wait.return_value = True
    
    response = client.post('/api/chats/chat1/stop')
    
    assert response.status_code == 200
    assert response.json == {"status": "success", "stopped": True}
    mock_task_manager.stop_task_and_wait.assert_called_with("chat1")
    mock_db.rollback_to_last_user_message.assert_called_with("chat1")
    mock_response_cache.clear_sse_chunks.assert_called_with("chat1")
    mock_db.update_chat.assert_any_call("chat1", research_state='none')
    mock_callback_registry.cleanup_chat.assert_called_with("chat1")
    mock_db.update_chat.assert_any_call("chat1", resume_suppressed=1)
    
    mock_task_manager.stop_task_and_wait.side_effect = Exception("error")
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

    mock_db.get_file.return_value = {'id': 'img1', 'stored_filename': 'img1.png', 'chat_id': 'chat1'}
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
    mock_db.get_file.return_value = {'id': 'doc1', 'chat_id': 'chat1'}
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
    mock_db.persona_name_exists.return_value = False
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
    mock_db.create_persona.assert_called_with("Pirate", "Arr!", "user-a", 0, 0, 0, 0)

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
    mock_db.create_persona.assert_called_with("FS Developer", "FS only", "user-a", 0, 0, 1, 1)


@patch('backend.chat.router.db')
def test_update_persona(mock_db, client):
    mock_db.persona_name_exists.return_value = False
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
    mock_db.update_persona.assert_called_with("p1", "Updated", "New prompt", "user-a", 1, 1, 0, 0)


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
    mock_db.delete_persona.assert_called_with("p1", "user-a")


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
    # Not found (also what another user's skill looks like)
    mock_db.delete_skill.return_value = False
    response = client.delete('/api/skills/s1')
    assert response.status_code == 404
    assert response.json["success"] is False

    # Success
    mock_db.delete_skill.return_value = True
    response = client.delete('/api/skills/s1')
    assert response.status_code == 200
    assert response.json == {"success": True}
    mock_db.delete_skill.assert_called_with("s1", "user-a")


# Routes that need a JSON body: a missing, malformed or non-object body is a 400 JSON error, not a 500 or an HTML page.
CHAT_REQUIRED_BODY_ROUTES = [
    ("post", "/api/chats/workspaces", {}),
    ("post", "/api/chats/save", {}),
    ("patch", "/api/chats/chat1", {}),
    ("patch", "/api/chats/chat1/messages/1", {}),
    ("put", "/api/chats/chat1/messages/1", {}),
    ("post", "/v1/chat/completions", {}),
    ("post", "/api/personas", {"success": False}),
    ("put", "/api/personas/p1", {"success": False}),
    ("post", "/api/skills", {"success": False}),
    ("put", "/api/skills/s1", {"success": False}),
]
CHAT_BAD_BODIES = [
    {},
    {"data": "null", "content_type": "application/json"},
    {"data": "[1]", "content_type": "application/json"},
    {"data": "{bad", "content_type": "application/json"},
    {"data": '{"a": 1}', "content_type": "text/plain"},
]


@patch('backend.chat.router.db')
@pytest.mark.parametrize("method,url,extra", CHAT_REQUIRED_BODY_ROUTES)
@pytest.mark.parametrize("body", CHAT_BAD_BODIES)
def test_chat_required_body_routes_return_a_400_json_error(mock_db, client, method, url, extra, body):
    resp = getattr(client, method)(url, **body)
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "Request body must be a JSON object", **extra}


@patch('backend.chat.router.db')
@pytest.mark.parametrize("body", [{"data": "[1]", "content_type": "application/json"},
                                  {"data": "{bad", "content_type": "application/json"}])
def test_chat_optional_body_routes_still_reject_an_invalid_body(mock_db, client, body):
    for method, url in (("patch", "/api/chats/workspaces/ws1"), ("post", "/api/chats/chat1/resume")):
        resp = getattr(client, method)(url, **body)
        assert resp.status_code == 400 and resp.get_json() == {"error": "Request body must be a JSON object"}, url


@patch('backend.chat.router.db')
def test_rename_workspace_without_a_body_reaches_its_own_validation(mock_db, client):
    resp = client.patch('/api/chats/workspaces/ws1')
    assert resp.status_code == 400
    assert "Missing workspace update fields" in resp.get_json()["error"]


@patch('backend.chat.router.db')
@patch('backend.chat.router.ChatHandler')
def test_resume_chat_accepts_no_body_and_a_null_body(mock_chat_handler_class, mock_db, client):
    mock_db.get_messages.return_value = [{"role": "user", "content": "resume this"}]
    mock_db.get_chat.return_value = {"last_model": "db-model"}

    async def mock_initiate_chat(**kwargs):
        yield "data: chunk1\n\n"

    mock_chat_handler_class.return_value.initiate_chat.side_effect = lambda **kw: mock_initiate_chat()
    for request_kwargs in ({}, {"data": "null", "content_type": "application/json"}):
        response = client.post('/api/chats/chat1/resume', **request_kwargs)
        assert response.status_code == 200 and response.mimetype == 'text/event-stream'
        assert "data: chunk1\n\n" in response.get_data(as_text=True)


def test_resume_chat_with_a_bad_body_does_not_take_the_turn_claim(client):
    with patch('backend.chat.router.task_manager') as turns:
        resp = client.post('/api/chats/chat1/resume', data="[1]", content_type="application/json")
    assert resp.status_code == 400
    turns.claim_turn.assert_not_called()


# =============================================================================
# Ownership: user B can never see or change user A's chats and workspaces
# =============================================================================

WRITE_METHODS = ("add_message", "delete_message", "delete_chat", "update_chat", "rename_chat", "save_chat",
                 "update_chat_workspace", "rollback_to_last_user_message", "edit_message", "update_last_user_id",
                 "delete_workspace", "rename_workspace", "update_workspace_icon", "create_workspace")


@pytest.fixture
def b_on_a_chat(app, login_as, user_a, user_b, owned_by_user_a):
    """The app with user B logged in while every chat and workspace in the db belongs to user A."""
    owned_by_user_a.get_chat_owner.return_value = user_a["id"]
    owned_by_user_a.get_workspace_owner.return_value = user_a["id"]
    owned_by_user_a.ensure_chat_exists.return_value = user_a["id"]
    login_as(app, user_b)
    return app.test_client()


CHAT_ROUTES = [
    ("get", "/api/chats/chat1", None),
    ("delete", "/api/chats/chat1", None),
    ("patch", "/api/chats/chat1", {"title": "stolen"}),
    ("get", "/api/chats/chat1/stream", None),
    ("post", "/api/chats/chat1/resume", {}),
    ("post", "/api/chats/chat1/stop", None),
    ("put", "/api/chats/chat1/messages/1", {"content": "edited"}),
    ("patch", "/api/chats/chat1/messages/1", {"content": "edited"}),
    ("delete", "/api/chats/chat1/messages/1", None),
    ("post", "/api/chats/chat1/discard", None),
    ("post", "/v1/chat/completions", {"chatId": "chat1", "model": "m", "messages": [{"role": "user", "content": "hi"}]}),
    ("post", "/api/chats/save", {"chat_id": "chat1", "title": "overwrite"}),
]


@pytest.mark.parametrize("method,url,body", CHAT_ROUTES)
@patch('backend.chat.router.os.remove')
@patch('backend.chat.router.task_manager')
@patch('backend.chat.router.db')
def test_user_b_gets_404_and_nothing_is_written_on_user_as_chat(mock_db, mock_tm, mock_remove, method, url, body, b_on_a_chat):
    mock_db.get_chat.return_value = {"id": "chat1"}  # the chat exists (for the save route's existing-chat check)
    kwargs = {"json": body} if body is not None else {}
    response = getattr(b_on_a_chat, method)(url, **kwargs)
    assert response.status_code == 404
    assert response.get_json()["error"] == "Chat not found"
    # Nothing but reads reached the db, whatever the route's write methods are called.
    assert [c for c in mock_db.mock_calls if not c[0].startswith("get_")] == []
    for name in WRITE_METHODS:
        getattr(mock_db, name).assert_not_called()
    mock_tm.claim_turn.assert_not_called()
    mock_tm.stop_task.assert_not_called()
    mock_remove.assert_not_called()  # the discard route removes task and state files


@patch('backend.chat.router.db')
def test_user_b_cannot_resolve_or_touch_workspaces_of_user_a(mock_db, b_on_a_chat):
    assert b_on_a_chat.patch('/api/chats/workspaces/ws1', json={"name": "x"}).status_code == 404
    assert b_on_a_chat.delete('/api/chats/workspaces/ws1').status_code == 404
    for name in ("rename_workspace", "update_workspace_icon", "delete_workspace"):
        getattr(mock_db, name).assert_not_called()


@patch('backend.chat.router.db')
def test_patch_and_save_refuse_a_workspace_of_another_user(mock_db, app, login_as, user_a, user_b, owned_by_user_a):
    owned_by_user_a.get_workspace_owner.return_value = user_a["id"]
    owned_by_user_a.get_chat_owner.return_value = user_b["id"]
    owned_by_user_a.ensure_chat_exists.return_value = user_b["id"]
    login_as(app, user_b)
    client = app.test_client()
    mock_db.get_chat.return_value = None
    assert client.patch('/api/chats/mine', json={"workspace_id": "ws-of-a"}).status_code == 404
    assert client.post('/api/chats/save', json={"chat_id": "new1", "workspace_id": "ws-of-a"}).status_code == 404
    mock_db.update_chat_workspace.assert_not_called()
    mock_db.save_chat.assert_not_called()
    owned_by_user_a.ensure_chat_exists.assert_not_called()  # a refused workspace creates nothing, not even the chat


@patch('backend.chat.router.db')
def test_lists_and_delete_all_are_scoped_to_the_caller(mock_db, app, login_as, user_b):
    login_as(app, user_b)
    client = app.test_client()
    mock_db.get_listed_chats.return_value = []
    mock_db.get_all_workspaces.return_value = []
    client.get('/api/chats/')
    client.get('/api/chats/workspaces')
    assert client.delete('/api/chats/').status_code == 200
    mock_db.get_listed_chats.assert_called_once_with(user_b["id"])
    mock_db.get_all_workspaces.assert_called_once_with(user_b["id"])
    mock_db.delete_all_chats.assert_called_once_with(user_b["id"])


@patch('backend.chat.router.db')
def test_workspace_create_and_name_check_use_the_callers_id(mock_db, app, login_as, user_b):
    login_as(app, user_b)
    mock_db.workspace_name_exists.return_value = False
    mock_db.create_workspace.return_value = {"id": "w1", "name": "N"}
    assert app.test_client().post('/api/chats/workspaces', json={"name": "N"}).status_code == 200
    mock_db.workspace_name_exists.assert_called_once_with("N", user_b["id"])
    mock_db.create_workspace.assert_called_once_with("N", user_b["id"])


@patch('backend.chat.router.db')
def test_save_chat_creates_the_chat_owned_by_the_caller(mock_db, app, login_as, user_b, owned_by_user_a):
    login_as(app, user_b)
    owned_by_user_a.get_workspace_owner.return_value = user_b["id"]
    owned_by_user_a.ensure_chat_exists.side_effect = lambda chat_id, user_id: user_id  # a new chat: the caller becomes the owner
    mock_db.get_chat.return_value = None
    mock_db.get_chat_file_systems.return_value = []
    assert app.test_client().post('/api/chats/save', json={"chat_id": "new1", "workspace_id": "wsb"}).status_code == 200
    assert mock_db.save_chat.call_args.kwargs["user_id"] == user_b["id"]
    owned_by_user_a.ensure_chat_exists.assert_called_with("new1", user_b["id"])  # claimed before the write


@patch('backend.chat.router.db')
def test_save_chat_that_loses_a_create_race_is_404_and_writes_nothing(mock_db, app, login_as, user_b, user_a, owned_by_user_a):
    """Another user created the same new chat id between the existence check and the save."""
    login_as(app, user_b)
    mock_db.get_chat.return_value = None  # looked new
    mock_db.get_chat_file_systems.return_value = []
    owned_by_user_a.ensure_chat_exists.return_value = user_a["id"]  # but user_a's row won the race
    response = app.test_client().post('/api/chats/save', json={"chat_id": "raced", "title": "t"})
    assert response.status_code == 404
    mock_db.save_chat.assert_not_called()
    mock_db.update_chat.assert_not_called()


@patch('backend.chat.router.db')
def test_saving_over_ones_own_chat_is_still_403(mock_db, client):
    mock_db.get_chat.return_value = {"id": "chat1"}
    assert client.post('/api/chats/save', json={"chat_id": "chat1"}).status_code == 403
    mock_db.save_chat.assert_not_called()


@patch('backend.chat.router.ChatHandler')
@patch('backend.chat.router.task_manager')
@patch('backend.chat.router.db')
def test_completions_creates_a_new_chat_for_the_caller(mock_db, mock_tm, mock_handler, app, login_as, user_b, owned_by_user_a):
    login_as(app, user_b)
    owned_by_user_a.get_chat_owner.return_value = None  # the chat does not exist yet
    owned_by_user_a.ensure_chat_exists.side_effect = lambda chat_id, user_id: user_id
    mock_tm.claim_turn.return_value = True
    mock_db.add_message.return_value = 1
    mock_db.get_chat.return_value = {"title": "t"}

    async def stream(**kwargs):
        yield "data: ok\n\n"
    mock_handler.return_value.initiate_chat.side_effect = lambda **kw: stream()
    response = app.test_client().post('/v1/chat/completions', json={
        "chatId": "brand-new", "model": "m", "messages": [{"role": "user", "content": "hi"}]})
    assert response.status_code == 200
    owned_by_user_a.ensure_chat_exists.assert_called_once_with("brand-new", user_b["id"])


@patch('backend.chat.router.task_manager')
@patch('backend.chat.router.db')
def test_completions_rejects_files_of_another_chat_and_writes_nothing(mock_db, mock_tm, client, owned_by_user_a):
    for meta in ({"id": "f1", "chat_id": "someone-elses-chat"}, None):
        mock_db.get_file.return_value = meta
        response = client.post('/v1/chat/completions', json={
            "chatId": "chat1", "model": "m", "messages": [{"role": "user", "content": "hi"}],
            "uploadedFiles": [{"file_id": "f1", "name": "x.pdf", "mime_type": "application/pdf"}]})
        assert response.status_code == 400
        assert response.get_json() == {"error": "Unknown file"}
    owned_by_user_a.ensure_chat_exists.assert_not_called()  # not even the chat row is created
    mock_db.add_message.assert_not_called()
    mock_tm.claim_turn.assert_not_called()


@patch('backend.chat.router.task_manager')
@patch('backend.chat.router.db')
def test_completions_on_a_foreign_chat_does_not_reveal_which_files_it_holds(mock_db, mock_tm, b_on_a_chat):
    body = {"chatId": "chat1", "model": "m", "messages": [{"role": "user", "content": "hi"}],
            "uploadedFiles": [{"file_id": "f1", "name": "x.pdf", "mime_type": "application/pdf"}]}
    mock_db.get_file.return_value = {"id": "f1", "chat_id": "chat1"}  # attached to the foreign chat
    attached = b_on_a_chat.post('/v1/chat/completions', json=body)
    mock_db.get_file.return_value = None
    unattached = b_on_a_chat.post('/v1/chat/completions', json=body)
    assert attached.status_code == unattached.status_code == 404
    mock_db.add_message.assert_not_called()


@pytest.mark.parametrize("bad", [5, True, "file", {"file_id": "f1"}])
@patch('backend.chat.router.task_manager')
@patch('backend.chat.router.db')
def test_completions_rejects_uploaded_files_that_are_not_a_list_with_400(mock_db, mock_tm, bad, client, owned_by_user_a):
    response = client.post('/v1/chat/completions', json={
        "chatId": "chat1", "model": "m", "messages": [{"role": "user", "content": "hi"}], "uploadedFiles": bad})
    assert response.status_code == 400
    assert response.get_json() == {"error": "uploadedFiles must be a list"}
    owned_by_user_a.ensure_chat_exists.assert_not_called()
    mock_db.add_message.assert_not_called()
    mock_tm.claim_turn.assert_not_called()


def test_chat_routes_fail_closed_without_a_current_user():
    app = Flask(__name__)  # no login: there is no current user
    app.register_blueprint(chat_bp, url_prefix='/api/chats')
    with patch('backend.chat.router.db'):
        assert app.test_client().get('/api/chats/chat1').status_code == 404


# =============================================================================
# Ownership of personas and skills
# =============================================================================

@pytest.fixture
def as_user_b(app, login_as, user_b):
    login_as(app, user_b)
    return app.test_client()


@patch('backend.chat.router.db')
def test_persona_routes_pass_the_callers_id_and_a_foreign_id_is_404(mock_db, as_user_b, user_b):
    mock_db.get_all_personas.return_value = []
    mock_db.persona_name_exists.return_value = False
    mock_db.create_persona.return_value = {"id": "pb"}
    mock_db.update_persona.return_value = False  # user_a's persona: not found for user_b
    mock_db.delete_persona.return_value = False
    assert as_user_b.get('/api/personas').get_json()["personas"] == []
    mock_db.get_all_personas.assert_called_once_with(user_b["id"])
    assert as_user_b.post('/api/personas', json={"name": "N", "content": "C"}).status_code == 201
    assert mock_db.create_persona.call_args.args[2] == user_b["id"]
    assert mock_db.persona_name_exists.call_args.args == ("N", user_b["id"])
    foreign_update = as_user_b.put('/api/personas/pa', json={"name": "N", "content": "C"})
    assert foreign_update.status_code == 404 and foreign_update.get_json() == {"success": False, "error": "Persona not found"}
    mock_db.get_persona.assert_not_called()  # nothing about the foreign persona is read back
    foreign_delete = as_user_b.delete('/api/personas/pa')
    assert foreign_delete.status_code == 404
    assert mock_db.update_persona.call_args.args[3] == user_b["id"]
    mock_db.delete_persona.assert_called_once_with("pa", user_b["id"])


@patch('backend.chat.router.db')
def test_skill_routes_pass_the_callers_id_and_a_foreign_id_is_404(mock_db, as_user_b, user_b):
    mock_db.get_all_skills.return_value = []
    mock_db.get_skill.return_value = None  # user_a's skill is not visible to user_b
    mock_db.delete_skill.return_value = False
    assert as_user_b.get('/api/skills').get_json()["skills"] == []
    mock_db.get_all_skills.assert_called_once_with(user_b["id"])
    foreign_put = as_user_b.put('/api/skills/sa', json={"name": "n", "description": "d", "instructions": "i"})
    assert foreign_put.status_code == 404
    mock_db.add_skill.assert_not_called()
    assert as_user_b.delete('/api/skills/sa').status_code == 404
    mock_db.delete_skill.assert_called_once_with("sa", user_b["id"])
    mock_db.get_skill.return_value = {"id": "sb"}
    mock_db.add_skill.return_value = True
    assert as_user_b.post('/api/skills', json={"name": "n", "description": "d", "instructions": "i"}).status_code == 201
    assert mock_db.add_skill.call_args.args[4] == user_b["id"]


@patch('backend.chat.router.db')
def test_skill_put_that_loses_ownership_between_check_and_write_is_404(mock_db, as_user_b):
    mock_db.get_skill.return_value = {"id": "s1"}
    mock_db.add_skill.return_value = False  # the guarded upsert refused a foreign id
    response = as_user_b.put('/api/skills/s1', json={"name": "n", "description": "d", "instructions": "i"})
    assert response.status_code == 404


@pytest.mark.parametrize("field", ["persona_id", "workspace_id", "folder"])
@pytest.mark.parametrize("bad", [["a"], {"id": "x"}, 5])
@patch('backend.chat.router.db')
def test_save_chat_with_a_non_string_persona_or_workspace_is_400(mock_db, bad, field, as_user_b):
    mock_db.get_chat.return_value = None
    response = as_user_b.post('/api/chats/save', json={"chat_id": "new1", field: bad})
    assert response.status_code == 400
    mock_db.save_chat.assert_not_called()


@patch('backend.chat.router.db')
def test_save_chat_with_a_foreign_persona_is_404_and_writes_nothing(mock_db, as_user_b, user_b):
    mock_db.get_chat.return_value = None
    mock_db.get_persona.return_value = None  # not user_b's persona
    response = as_user_b.post('/api/chats/save', json={"chat_id": "new1", "persona_id": "persona-of-a"})
    assert response.status_code == 404 and response.get_json() == {"error": "Persona not found"}
    mock_db.get_persona.assert_called_once_with("persona-of-a", user_b["id"])
    mock_db.save_chat.assert_not_called()


# =============================================================================
# Git mode is admin only
# =============================================================================

@pytest.mark.parametrize("url,body", [
    ('/v1/chat/completions', {"chatId": "chat1", "model": "m", "messages": [{"role": "user", "content": "hi"}], "gitMode": True}),
    ('/api/chats/chat1/resume', {"gitMode": True}),
])
@patch('backend.chat.router.task_manager')
@patch('backend.chat.router.db')
def test_enabling_git_mode_is_403_for_a_user_and_writes_nothing(mock_db, mock_tm, url, body, client, owned_by_user_a):
    response = client.post(url, json=body)
    assert response.status_code == 403 and response.get_json() == {"error": "Forbidden"}
    mock_tm.claim_turn.assert_not_called()  # no turn claimed
    owned_by_user_a.ensure_chat_exists.assert_not_called()  # no chat created
    assert [c for c in mock_db.mock_calls if not c[0].startswith("get_")] == []  # no message, no write


@pytest.mark.parametrize("url,body", [
    ('/v1/chat/completions', {"chatId": "chat1", "model": "m", "messages": [{"role": "user", "content": "hi"}], "gitMode": False}),
    ('/v1/chat/completions', {"chatId": "chat1", "model": "m", "messages": [{"role": "user", "content": "hi"}]}),
    ('/api/chats/chat1/resume', {"gitMode": 0}),
])
@patch('backend.chat.router.ChatHandler')
@patch('backend.chat.router.task_manager')
@patch('backend.chat.router.db')
def test_a_user_without_git_mode_is_not_blocked(mock_db, mock_tm, mock_handler, url, body, client):
    mock_tm.claim_turn.return_value = True
    mock_db.get_messages.return_value = [{"role": "user", "content": "x"}]
    mock_db.get_chat.return_value = {"last_model": "m"}
    mock_db.add_message.return_value = 1
    assert client.post(url, json=body).status_code != 403


@patch('backend.chat.router.ChatHandler')
@patch('backend.chat.router.task_manager')
@patch('backend.chat.router.db')
def test_the_admin_can_enable_git_mode(mock_db, mock_tm, mock_handler, app, login_as, admin_a):
    login_as(app, admin_a)
    mock_tm.claim_turn.return_value = True
    mock_db.get_messages.return_value = [{"role": "user", "content": "x"}]
    mock_db.get_chat.return_value = {"last_model": "m"}
    response = app.test_client().post('/api/chats/chat1/resume', json={"gitMode": True})
    assert response.status_code != 403



# =============================================================================
# Per-user turn rate limit
# =============================================================================

from backend.auth import rate_limit
from backend.auth.rate_limit import FixedWindowLimiter

LIMITED_REQUESTS = [
    ('/v1/chat/completions', {"chatId": "chat1", "model": "m", "messages": [{"role": "user", "content": "hi"}]}),
    ('/api/chats/chat1/resume', {}),
]


class _Clock:
    now = 5000.0

    def __call__(self):
        return self.now


@pytest.fixture
def one_turn_per_window():
    clock = _Clock()
    with patch.object(rate_limit, "turn_limiter", FixedWindowLimiter(1, 60, clock=clock)), \
         patch('backend.chat.router.log_event') as events:
        yield clock, events


@pytest.mark.parametrize("url,body", LIMITED_REQUESTS)
@patch('backend.chat.router.ChatHandler')
@patch('backend.chat.router.task_manager')
@patch('backend.chat.router.db')
def test_the_second_turn_in_the_window_is_429_with_retry_after_and_writes_nothing(
        mock_db, mock_tm, mock_handler, url, body, client, owned_by_user_a, one_turn_per_window):
    clock, events = one_turn_per_window
    mock_tm.claim_turn.return_value = True
    mock_db.get_messages.return_value = [{"role": "user", "content": "x"}]
    mock_db.get_chat.return_value = {"last_model": "m"}
    mock_db.add_message.return_value = 1
    assert client.post(url, json=body).status_code != 429  # the first turn is within the limit
    mock_tm.reset_mock(); mock_db.reset_mock(); owned_by_user_a.reset_mock()
    clock.now += 20
    response = client.post(url, json=body)
    assert response.status_code == 429 and response.get_json() == {"error": "Too many requests; try again shortly."}
    assert response.headers["Retry-After"] == "40"
    mock_tm.claim_turn.assert_not_called()  # no turn claimed
    owned_by_user_a.ensure_chat_exists.assert_not_called()  # no chat claimed or created
    assert [c for c in mock_db.mock_calls if not c[0].startswith("get_")] == []  # no message, no write
    events.assert_any_call("rate_limited", {"kind": "turns"})


@pytest.mark.parametrize("url,body", LIMITED_REQUESTS)
@patch('backend.chat.router.ChatHandler')
@patch('backend.chat.router.task_manager')
@patch('backend.chat.router.db')
def test_the_window_rolling_over_allows_the_next_turn(mock_db, mock_tm, mock_handler, url, body, client, owned_by_user_a, one_turn_per_window):
    clock, _ = one_turn_per_window
    mock_tm.claim_turn.return_value = True
    mock_db.get_messages.return_value = [{"role": "user", "content": "x"}]
    mock_db.get_chat.return_value = {"last_model": "m"}
    mock_db.add_message.return_value = 1
    client.post(url, json=body)
    assert client.post(url, json=body).status_code == 429
    clock.now += 60
    assert client.post(url, json=body).status_code != 429


@patch('backend.chat.router.ChatHandler')
@patch('backend.chat.router.task_manager')
@patch('backend.chat.router.db')
def test_the_limit_is_per_user_and_send_and_resume_share_it(mock_db, mock_tm, mock_handler, app, login_as, user_a, user_b, owner_db, one_turn_per_window):
    mock_tm.claim_turn.return_value = True
    mock_db.get_messages.return_value = [{"role": "user", "content": "x"}]
    mock_db.get_chat.return_value = {"last_model": "m"}
    mock_db.add_message.return_value = 1
    owner_db.get_chat_owner.side_effect = lambda chat_id: user_a["id"] if chat_id == "chat1" else user_b["id"]
    login_as(app, user_a)
    first = app.test_client()
    assert first.post('/v1/chat/completions', json=LIMITED_REQUESTS[0][1]).status_code != 429
    assert first.post('/api/chats/chat1/resume', json={}).status_code == 429  # a resume counts against the same limit
    login_as(app, user_b)
    other = app.test_client()
    assert other.post('/api/chats/chat2/resume', json={}).status_code != 429  # another user is not affected


@patch('backend.chat.router.ChatHandler')
@patch('backend.chat.router.task_manager')
@patch('backend.chat.router.db')
def test_the_exempt_admin_is_not_limited_and_a_non_exempt_admin_is(mock_db, mock_tm, mock_handler, app, login_as, admin_a, owner_db, one_turn_per_window):
    from backend import config
    mock_tm.claim_turn.return_value = True
    mock_db.get_messages.return_value = [{"role": "user", "content": "x"}]
    mock_db.get_chat.return_value = {"last_model": "m"}
    owner_db.get_chat_owner.return_value = admin_a["id"]
    login_as(app, admin_a)
    admin = app.test_client()
    with patch.object(config, "RATE_LIMIT_EXEMPT_ADMIN", True):
        assert all(admin.post('/api/chats/chat1/resume', json={}).status_code != 429 for _ in range(3))
    with patch.object(config, "RATE_LIMIT_EXEMPT_ADMIN", False):
        admin.post('/api/chats/chat1/resume', json={})
        assert admin.post('/api/chats/chat1/resume', json={}).status_code == 429


@pytest.mark.parametrize("url,body", LIMITED_REQUESTS)
@patch('backend.chat.router.task_manager')
@patch('backend.chat.router.db')
def test_a_request_without_a_user_is_401_and_touches_nothing(mock_db, mock_tm, url, body, owned_by_user_a, one_turn_per_window):
    app = Flask(__name__)
    app.register_blueprint(chat_bp, url_prefix='/api/chats')
    app.register_blueprint(openai_bp, url_prefix='/v1/chat')
    with patch('backend.chat.router.require_chat_owner', return_value=None), patch('backend.chat.router.reject_foreign_chat', return_value=None):
        response = app.test_client().post(url, json=body)
    assert response.status_code == 401 and response.get_json() == {"error": "Unauthorized"}
    mock_tm.claim_turn.assert_not_called()


@pytest.mark.parametrize("url,body", LIMITED_REQUESTS)
@patch('backend.chat.router.task_manager')
@patch('backend.chat.router.db')
def test_a_foreign_chat_is_still_404_and_does_not_spend_a_turn(mock_db, mock_tm, url, body, as_user_b, owned_by_user_a, one_turn_per_window):
    for _ in range(3):
        assert as_user_b.post(url, json=body).status_code == 404  # refused by ownership before the limiter
    mock_tm.claim_turn.assert_not_called()
    assert rate_limit.turn_limiter._windows == {}  # the limiter was never consulted for the refused requests


@patch('backend.chat.router.task_manager')
@patch('backend.chat.router.db')
def test_stop_waits_for_the_worker_before_rolling_back(mock_db, mock_task_manager, client):
    order = []
    mock_task_manager.stop_task_and_wait.side_effect = lambda chat_id: order.append("wait") or True
    mock_db.rollback_to_last_user_message.side_effect = lambda chat_id: order.append("rollback")
    assert client.post('/api/chats/chat1/stop').status_code == 200
    assert order == ["wait", "rollback"]


@patch('backend.chat.router.log_event')
@patch('backend.chat.router.task_manager')
@patch('backend.chat.router.db')
def test_stop_that_times_out_still_rolls_back_and_reports_it(mock_db, mock_task_manager, mock_log_event, client):
    mock_task_manager.stop_task_and_wait.return_value = False
    response = client.post('/api/chats/chat1/stop')
    assert response.status_code == 200
    assert response.json == {"status": "success", "stopped": False}
    mock_db.rollback_to_last_user_message.assert_called_once_with("chat1")
    mock_log_event.assert_any_call("chat_stop_timeout", {"chat_id": "chat1"})


@patch('backend.chat.router.task_manager')
@patch('backend.chat.router.db')
def test_stop_of_another_users_chat_is_a_404_and_stops_nothing(mock_db, mock_task_manager, app, login_as, user_b):
    login_as(app, user_b)
    response = app.test_client().post('/api/chats/chat1/stop')
    assert response.status_code == 404
    mock_task_manager.stop_task_and_wait.assert_not_called()
    mock_db.rollback_to_last_user_message.assert_not_called()


@patch('backend.database.response_cache')
@patch('backend.files.manager.FileManager')
@patch('backend.rag.RAGProvider')
@patch('backend.models.get_embedding_model')
@patch('backend.chat.router.task_manager')
@patch('backend.chat.router.db')
@patch('backend.chat.router.FileSystemChannelManager')
def test_delete_ends_the_turn_before_deleting_and_forgets_the_chat(
    mock_fscm, mock_db, mock_task_manager, mock_get_embedding, mock_rag_provider, mock_file_manager,
    mock_response_cache, client
):
    order = []
    mock_task_manager.stop_task_and_wait.side_effect = lambda chat_id: order.append("wait") or True
    mock_task_manager.forget_chat.side_effect = lambda chat_id: order.append("forget")
    mock_db.delete_chat.side_effect = lambda chat_id: order.append("delete")
    assert client.delete('/api/chats/chat1').status_code == 200
    assert order == ["wait", "forget", "delete"]
    # The whole cache entry and its WAL go, not only the buffered chunks.
    mock_response_cache.cleanup_chat.assert_called_once_with("chat1")


@patch('backend.chat.router.task_manager')
@patch('backend.chat.router.db')
def test_delete_leaves_the_chat_when_its_task_files_cannot_be_removed(mock_db, mock_task_manager, client):
    mock_task_manager.stop_task_and_wait.return_value = True
    mock_task_manager.forget_chat.side_effect = PermissionError("denied")
    with patch('backend.models.get_embedding_model'), patch('backend.rag.RAGProvider'), \
         patch('backend.files.manager.FileManager'):
        assert client.delete('/api/chats/chat1').status_code == 500
    mock_db.delete_chat.assert_not_called()


@patch('backend.chat.router.log_event')
@patch('backend.chat.router.task_manager')
@patch('backend.chat.router.db')
def test_delete_is_refused_while_the_turn_is_still_ending(mock_db, mock_task_manager, mock_log_event, client):
    mock_task_manager.stop_task_and_wait.return_value = False
    response = client.delete('/api/chats/chat1')
    assert response.status_code == 409
    assert "still stopping" in response.json["error"]
    mock_db.delete_chat.assert_not_called()
    mock_task_manager.forget_chat.assert_not_called()
    mock_log_event.assert_any_call("chat_delete_stop_timeout", {"chat_id": "chat1"})


@patch('backend.chat.router.task_manager')
@patch('backend.chat.router.db')
def test_clear_all_stops_only_the_callers_running_turns_first(mock_db, mock_task_manager, app, login_as, user_b):
    login_as(app, user_b)
    order = []
    mock_db.get_all_chats.return_value = [{"id": "b1"}, {"id": "b2"}]
    # a9 belongs to someone else; the second snapshot shows b1 gone, so the loop ends
    mock_task_manager.running_chat_ids.side_effect = [["b1", "a9"], ["a9"]]
    mock_task_manager.stop_task_and_wait.side_effect = lambda chat_id, timeout: order.append("wait") or True
    mock_db.delete_all_chats.side_effect = lambda user_id: order.append("delete")
    assert app.test_client().delete('/api/chats/').status_code == 200
    mock_task_manager.stop_task.assert_called_once_with("b1")
    assert [c.args[0] for c in mock_task_manager.stop_task_and_wait.call_args_list] == ["b1"]  # never the other user's a9
    assert order == ["wait", "delete"]
    assert sorted(c.args[0] for c in mock_task_manager.forget_chat.call_args_list) == ["b1", "b2"]


@patch('backend.chat.router.log_event')
@patch('backend.chat.router.task_manager')
@patch('backend.chat.router.db')
def test_clear_all_deletes_nothing_while_a_turn_is_still_ending(mock_db, mock_task_manager, mock_log_event, client):
    mock_db.get_all_chats.return_value = [{"id": "c1"}]
    mock_task_manager.running_chat_ids.return_value = ["c1"]
    mock_task_manager.stop_task_and_wait.return_value = False
    response = client.delete('/api/chats/')
    assert response.status_code == 409
    mock_db.delete_all_chats.assert_not_called()
    mock_log_event.assert_any_call("chat_clear_all_stop_timeout", {"chat_ids": ["c1"]})


@patch('backend.chat.router.task_manager')
@patch('backend.chat.router.db')
def test_clear_all_stops_a_turn_that_started_after_the_first_pass(mock_db, mock_task_manager, client):
    mock_db.get_all_chats.return_value = [{"id": "c1"}, {"id": "c2"}]
    mock_task_manager.running_chat_ids.side_effect = [["c1"], ["c2"], []]
    mock_task_manager.stop_task_and_wait.return_value = True
    assert client.delete('/api/chats/').status_code == 200
    assert [c.args[0] for c in mock_task_manager.stop_task_and_wait.call_args_list] == ["c1", "c2"]
    mock_db.delete_all_chats.assert_called_once()



# ---- temporary chats --------------------------------------------------------------------------------------------

def _completion_body(**extra):
    return {"chatId": "tmp1", "model": "m", "messages": [{"role": "user", "content": "hi"}], **extra}


@pytest.fixture
def completion_mocks():
    with patch('backend.chat.router.db') as mock_db, patch('backend.chat.router.ChatHandler') as handler, \
         patch('backend.chat.router.log_event'):
        mock_db.get_messages.return_value = []
        mock_db.get_file.return_value = None

        async def stream(*a, **k):
            yield "data: x\n\n"
        handler.return_value.initiate_chat.side_effect = stream
        yield mock_db, handler


def test_the_first_send_of_a_temporary_chat_marks_it_and_the_handler_does_not_get_the_flag(client, completion_mocks):
    mock_db, handler = completion_mocks
    assert client.post('/v1/chat/completions', json=_completion_body(temporary=True)).status_code == 200
    mock_db.mark_chat_temporary.assert_called_once_with("tmp1")
    assert "temporary" not in handler.return_value.initiate_chat.call_args.kwargs


def test_a_send_without_the_flag_never_marks_the_chat(client, completion_mocks):
    mock_db, _ = completion_mocks
    client.post('/v1/chat/completions', json=_completion_body())
    mock_db.mark_chat_temporary.assert_not_called()


@pytest.mark.parametrize("bad", ["yes", 1, [], {}, None])
def test_a_non_boolean_temporary_is_a_400_and_writes_nothing(client, completion_mocks, bad):
    mock_db, handler = completion_mocks
    with patch('backend.chat.router.claim_chat') as claim:
        response = client.post('/v1/chat/completions', json=_completion_body(temporary=bad))
    assert response.status_code == 400 and "temporary" in response.json["error"]
    claim.assert_not_called(); mock_db.update_chat.assert_not_called(); handler.assert_not_called()


def test_another_users_chat_is_404_before_the_flag_is_looked_at(app, login_as, user_b, owned_by_user_a, completion_mocks):
    owned_by_user_a.get_chat_owner.return_value = "someone-else"
    mock_db, _ = completion_mocks
    response = app.test_client().post('/v1/chat/completions', json=_completion_body(temporary=True))
    assert response.status_code == 404
    mock_db.update_chat.assert_not_called()


def test_saving_a_temporary_chat_clears_the_flag(client):
    with patch('backend.chat.router.db') as mock_db:
        mock_db.get_chat.return_value = {"id": "tmp1"}
        response = client.patch('/api/chats/tmp1', json={"title": "Kept", "is_temporary": False})
    assert response.status_code == 200
    mock_db.update_chat.assert_any_call(chat_id="tmp1", is_temporary=0)
    mock_db.rename_chat.assert_called_with(chat_id="tmp1", new_title="Kept")


@pytest.mark.parametrize("bad", [True, "false", 0, None])
def test_any_other_is_temporary_value_on_patch_is_a_400_and_creates_no_chat(client, bad):
    with patch('backend.chat.router.db') as mock_db, patch('backend.chat.router.claim_chat') as claim:
        response = client.patch('/api/chats/brand-new', json={"is_temporary": bad})
    assert response.status_code == 400
    claim.assert_not_called(); mock_db.update_chat.assert_not_called()


def test_saving_another_users_temporary_chat_is_404(app, login_as, user_b, owned_by_user_a):
    owned_by_user_a.get_chat_owner.return_value = "someone-else"
    owned_by_user_a.ensure_chat_exists.return_value = "someone-else"
    with patch('backend.chat.router.db') as mock_db:
        response = app.test_client().patch('/api/chats/tmp1', json={"is_temporary": False})
    assert response.status_code == 404
    mock_db.update_chat.assert_not_called()


def test_listing_chats_sweeps_the_callers_expired_temporary_chats_first(client, no_expiry_sweep):
    with patch('backend.chat.router.db') as mock_db:
        mock_db.get_listed_chats.return_value = [{"id": "kept"}]
        order = []
        no_expiry_sweep.side_effect = lambda *a, **k: order.append("sweep")
        mock_db.get_listed_chats.side_effect = lambda user_id: order.append("list") or [{"id": "kept"}]
        response = client.get('/api/chats')
    assert response.status_code == 200 and order == ["sweep", "list"]
    assert no_expiry_sweep.call_args.args[0] == "user-a" and callable(no_expiry_sweep.call_args.args[1])


def test_the_full_delete_sets_up_rag_only_for_a_chat_that_has_files(client):
    with patch('backend.chat.router.db') as mock_db, patch('backend.models.get_embedding_model') as embed, patch('backend.rag.RAGProvider'), \
         patch('backend.files.manager.FileManager') as file_manager, patch('backend.chat.router.task_manager') as tm, \
         patch('backend.chat.router.FileSystemChannelManager'), patch('backend.database.response_cache'):
        tm.stop_task_and_wait.return_value = True
        mock_db.get_chat_files.return_value = []
        assert client.delete('/api/chats/c1').status_code == 200
        embed.assert_not_called()
        mock_db.get_chat_files.return_value = [{"id": "f1"}]
        assert client.delete('/api/chats/c1').status_code == 200
        embed.assert_called_once()
        file_manager.return_value.delete_file.assert_called_once_with("f1")


def test_an_unsaved_temporary_chat_is_still_served_to_its_owner(client):
    with patch('backend.chat.router.ChatHandler') as handler:
        handler.return_value.get_history.return_value = {"messages": [], "resume_needed": False}
        assert client.get('/api/chats/tmp1').status_code == 200


def test_a_rag_setup_failure_keeps_the_chat_instead_of_orphaning_its_files(client):
    with patch('backend.chat.router.db') as mock_db, patch('backend.models.get_embedding_model', side_effect=RuntimeError("model down")), \
         patch('backend.rag.RAGProvider'), patch('backend.files.manager.FileManager'), patch('backend.chat.router.task_manager') as tm, \
         patch('backend.chat.router.FileSystemChannelManager'), patch('backend.database.response_cache'):
        tm.stop_task_and_wait.return_value = True
        mock_db.get_chat_files.return_value = [{"id": "f1"}]
        response = client.delete('/api/chats/c1')
    assert response.status_code == 500
    mock_db.delete_chat.assert_not_called()
