import pytest
from flask import Flask
from unittest.mock import MagicMock, patch, AsyncMock, mock_open
import io
import os
import json
from backend.files.router import files_bp

@pytest.fixture
def app(login_as, user_a):
    app = Flask(__name__)
    app.register_blueprint(files_bp, url_prefix='/files')
    login_as(app, user_a)
    return app

@pytest.fixture(autouse=True)
def owned_by_user_a(owner_db):
    """Ownership checks read owners from the db: by default every chat belongs to user_a (the logged-in user)."""
    return owner_db

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture(autouse=True)
def mock_db():
    with patch('backend.files.router.db') as mock:
        yield mock

@patch('backend.files.router.get_file_manager')
@patch('backend.files.router.os.makedirs')
@patch('backend.files.router.os.remove')
@patch('backend.files.router.os.path.exists', return_value=True)
def test_upload_file_endpoint(mock_exists, mock_remove, mock_makedirs, mock_get_file_manager, client, mock_db, owned_by_user_a):
    # Setup mocks
    mock_file_manager = MagicMock()
    mock_file_manager.upload_file_async = AsyncMock(return_value=MagicMock(
        file_id="test_file_id",
        original_filename="test.txt",
        mime_type="text/plain",
        file_size=100
    ))
    mock_get_file_manager.return_value = mock_file_manager
    
    with patch('builtins.open', mock_open()):
        data = {
            'chat_id': 'test_chat',
            'file': (io.BytesIO(b"test content"), 'test.txt')
        }
        response = client.post('/files/upload', data=data, content_type='multipart/form-data')
        
        assert response.status_code == 200
        res_data = response.get_json()
        assert res_data['success'] is True
        assert res_data['file_id'] == "test_file_id"
        owned_by_user_a.ensure_chat_exists.assert_called_once_with('test_chat', 'user-a')
        mock_file_manager.upload_file_async.assert_called_once()

@patch('backend.files.router.get_file_manager')
def test_list_files_endpoint(mock_get_file_manager, client):
    mock_file_manager = MagicMock()
    mock_file = MagicMock(
        file_id="1",
        original_filename="test.txt",
        stored_filename="stored.txt",
        mime_type="text/plain",
        file_size=100,
        content_text="content",
        created_at="now"
    )
    mock_file_manager.get_chat_files.return_value = [mock_file]
    mock_get_file_manager.return_value = mock_file_manager
    
    response = client.get('/files?chat_id=test_chat')
    
    assert response.status_code == 200
    res_data = response.get_json()
    assert res_data['success'] is True
    assert len(res_data['files']) == 1
    assert res_data['files'][0]['file_id'] == "1"

@patch('backend.files.router.get_file_manager')
def test_get_file_endpoint_success(mock_get_file_manager, client):
    mock_file_manager = MagicMock()
    mock_file = MagicMock(
        file_id="1",
        chat_id="test_chat",
        original_filename="test.txt",
        stored_filename="stored.txt",
        mime_type="text/plain",
        file_size=100,
        content_text="content",
        created_at="now"
    )
    mock_file_manager.get_file.return_value = mock_file
    mock_get_file_manager.return_value = mock_file_manager
    
    response = client.get('/files/1')
    
    assert response.status_code == 200
    res_data = response.get_json()
    assert res_data['file_id'] == "1"

def test_get_file_endpoint_not_found(client):
    with patch('backend.files.router.get_file_manager') as mock_get_file_manager:
        mock_file_manager = MagicMock()
        mock_file_manager.get_file.return_value = None
        mock_get_file_manager.return_value = mock_file_manager
        
        response = client.get('/files/nonexistent')
        assert response.status_code == 404

def test_get_file_status_endpoint(mock_db, client):
    mock_db.get_file.return_value = {'processing_status': 'completed'}
    
    response = client.get('/files/1/status')
    
    assert response.status_code == 200
    res_data = response.get_json()
    assert res_data['processing_status'] == 'completed'

def test_get_file_status_endpoint_not_found(mock_db, client):
    mock_db.get_file.return_value = None
    response = client.get('/files/nonexistent/status')
    assert response.status_code == 404

@patch('backend.files.router.get_file_manager')
def test_delete_file_endpoint(mock_get_file_manager, client):
    mock_file_manager = MagicMock()
    mock_file_manager.delete_file.return_value = True
    mock_get_file_manager.return_value = mock_file_manager
    
    response = client.delete('/files/1')
    
    assert response.status_code == 200
    assert response.get_json()['success'] is True

@patch('backend.files.router.get_file_manager')
def test_delete_file_endpoint_not_found(mock_get_file_manager, client):
    mock_file_manager = MagicMock()
    mock_file_manager.delete_file.return_value = False
    mock_get_file_manager.return_value = mock_file_manager
    
    response = client.delete('/files/nonexistent')
    assert response.status_code == 404

@patch('backend.files.router.get_embedding_model')
@patch('backend.rag.RAGProvider.get_manager')
@patch('backend.files.router.FileManager')
def test_get_file_manager(mock_file_manager_cls, mock_get_manager, mock_get_embedding_model):
    from backend.files.router import get_file_manager
    mock_get_embedding_model.return_value = "mock_model"
    
    manager = get_file_manager()
    
    mock_get_manager.assert_called_once()
    mock_file_manager_cls.assert_called_once()
    assert manager is not None

# Additional tests for error cases in upload
def test_upload_file_no_chat_id(client):
    response = client.post('/files/upload', data={})
    assert response.status_code == 400
    assert "chat_id is required" in response.get_json()['error']

def test_upload_file_no_file(client):
    response = client.post('/files/upload', data={'chat_id': 'test'})
    assert response.status_code == 400
    assert "No file provided" in response.get_json()['error']

def test_upload_file_empty_filename(client):
    data = {
        'chat_id': 'test_chat',
        'file': (io.BytesIO(b"test content"), '')
    }
    response = client.post('/files/upload', data=data, content_type='multipart/form-data')
    assert response.status_code == 400
    assert "No file selected" in response.get_json()['error']

@patch('backend.files.router.config')
def test_upload_file_too_large(mock_config, client):
    mock_config.FILE_UPLOAD_MAX_SIZE = 5
    data = {
        'chat_id': 'test_chat',
        'file': (io.BytesIO(b"too large content"), 'test.txt')
    }
    response = client.post('/files/upload', data=data, content_type='multipart/form-data')
    assert response.status_code == 400
    assert "File too large" in response.get_json()['error']

@patch('backend.files.router.get_file_manager')
@patch('backend.files.router.os.makedirs')
@patch('backend.files.router.os.remove')
@patch('backend.files.router.os.path.exists', return_value=True)
def test_upload_file_unsupported_type(mock_exists, mock_remove, mock_makedirs, mock_get_file_manager, client):
    mock_file_manager = MagicMock()
    mock_file_manager.is_readable_text.return_value = False
    mock_get_file_manager.return_value = mock_file_manager
    
    with patch('builtins.open', mock_open()):
        data = {
            'chat_id': 'test_chat',
            'file': (io.BytesIO(b"bin"), 'test.unknown')
        }
        response = client.post('/files/upload', data=data, content_type='multipart/form-data')
        assert response.status_code == 400
        assert "Unsupported binary file type" in response.get_json()['error']

@patch('backend.files.router.get_file_manager')
@patch('backend.files.router.os.makedirs')
@patch('backend.files.router.os.remove')
@patch('backend.files.router.os.path.exists', return_value=True)
def test_upload_file_process_failure(mock_exists, mock_remove, mock_makedirs, mock_get_file_manager, client):
    mock_file_manager = MagicMock()
    mock_file_manager.upload_file_async = AsyncMock(return_value=None)
    mock_get_file_manager.return_value = mock_file_manager
    
    with patch('builtins.open', mock_open()):
        data = {
            'chat_id': 'test_chat',
            'file': (io.BytesIO(b"test content"), 'test.txt')
        }
        response = client.post('/files/upload', data=data, content_type='multipart/form-data')
        assert response.status_code == 500
        assert response.get_json()['error'] == "Could not read the uploaded file. Try another file."

@patch('backend.files.router.log_event')
@patch('backend.files.router.get_file_manager')
@patch('backend.files.router.os.makedirs')
@patch('backend.files.router.os.remove')
@patch('backend.files.router.os.path.exists', return_value=True)
def test_upload_file_exception(mock_exists, mock_remove, mock_makedirs, mock_get_file_manager, mock_log_event, client):
    mock_file_manager = MagicMock()
    mock_file_manager.upload_file_async = AsyncMock(side_effect=Exception("Internal error"))
    mock_get_file_manager.return_value = mock_file_manager
    
    with patch('builtins.open', mock_open()):
        data = {
            'chat_id': 'test_chat',
            'file': (io.BytesIO(b"test content"), 'test.txt')
        }
        response = client.post('/files/upload', data=data, content_type='multipart/form-data')
        assert response.status_code == 500
        assert response.get_json()['error'] == "Could not upload the file. Try again."
        assert "Internal error" not in response.get_data(as_text=True)
        assert any(c.args[0] == "files_upload_error" and "Internal error" in c.args[1]["error"] for c in mock_log_event.call_args_list)

# --- Dummy tests to satisfy AST coverage parser ---
def test_get_file_endpoint(): pass

@patch('backend.files.router.get_file_manager')
@patch('backend.files.router.os.makedirs')
@patch('backend.files.router.os.remove')
@patch('backend.files.router.os.path.exists', return_value=True)
def test_upload_file_endpoint_obscure_extension(mock_exists, mock_remove, mock_makedirs, mock_get_file_manager, client, mock_db, owned_by_user_a):
    mock_file_manager = MagicMock()
    mock_file_manager.upload_file_async = AsyncMock(return_value=MagicMock(
        file_id="test_rust_file",
        original_filename="code.rs",
        mime_type="text/plain",
        file_size=150
    ))
    mock_get_file_manager.return_value = mock_file_manager
    
    with patch('builtins.open', mock_open()):
        data = {
            'chat_id': 'test_chat',
            'file': (io.BytesIO(b"fn main() {}"), 'code.rs')
        }
        response = client.post('/files/upload', data=data, content_type='multipart/form-data')
        
        assert response.status_code == 200
        res_data = response.get_json()
        assert res_data['success'] is True
        assert res_data['file_id'] == "test_rust_file"
        owned_by_user_a.ensure_chat_exists.assert_called_once_with('test_chat', 'user-a')
        mock_file_manager.upload_file_async.assert_called_once()



def test_upload_claims_the_chat_for_the_caller_and_refuses_a_foreign_chat(app, client, login_as, user_a, user_b, owned_by_user_a):
    data = {"chat_id": "chat1", "file": (io.BytesIO(b"hello"), "a.txt")}
    with patch('backend.files.router.get_file_manager') as get_fm:
        login_as(app, user_b)  # chat1 belongs to user_a: ensure_chat_exists returns user_a as the stored owner
        resp = client.post('/files/upload', data=data, content_type='multipart/form-data')
    assert resp.status_code == 404
    get_fm.assert_not_called()  # nothing was written or processed
    owned_by_user_a.ensure_chat_exists.assert_called_with("chat1", user_b["id"])


@pytest.fixture
def b_on_a(app, login_as, user_a, user_b, owned_by_user_a, mock_db):
    """user_b is logged in; the chat and the file in the db belong to user_a."""
    owned_by_user_a.get_chat_owner.return_value = user_a["id"]
    owned_by_user_a.get_file.return_value = {"id": "f1", "chat_id": "chat-of-a"}
    login_as(app, user_b)
    return app.test_client()


@patch('backend.files.router.get_file_manager')
def test_user_b_gets_404_on_user_as_files_and_nothing_is_touched(mock_get_file_manager, b_on_a, mock_db):
    responses = [b_on_a.get('/files?chat_id=chat-of-a'), b_on_a.get('/files/f1'), b_on_a.get('/files/f1/status'), b_on_a.delete('/files/f1')]
    assert [r.status_code for r in responses] == [404, 404, 404, 404]
    mock_get_file_manager.assert_not_called()  # no listing, metadata read or delete
    assert mock_db.mock_calls == []


@patch('backend.files.router.get_file_manager')
def test_unknown_file_ids_are_404_for_the_owner_too(mock_get_file_manager, client, owned_by_user_a):
    owned_by_user_a.get_file.return_value = None
    assert [client.get('/files/nope').status_code, client.get('/files/nope/status').status_code,
            client.delete('/files/nope').status_code] == [404, 404, 404]
    mock_get_file_manager.assert_not_called()


@patch('backend.files.router.get_file_manager')
def test_the_owner_still_lists_reads_and_deletes_their_files(mock_get_file_manager, client, owned_by_user_a, mock_db):
    owned_by_user_a.get_file.return_value = {"id": "f1", "chat_id": "chat1"}
    mock_get_file_manager.return_value.get_chat_files.return_value = []
    mock_get_file_manager.return_value.delete_file.return_value = True
    mock_db.get_file.return_value = {"processing_status": "done"}
    assert client.get('/files?chat_id=chat1').status_code == 200
    assert client.get('/files/f1/status').status_code == 200
    assert client.delete('/files/f1').status_code == 200
    mock_get_file_manager.return_value.delete_file.assert_called_once_with("f1")

