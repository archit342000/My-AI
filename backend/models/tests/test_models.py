import pytest
import os
import json
from unittest.mock import patch, MagicMock, mock_open
from flask import Flask

# Import the models package
from backend.models import (
    models_bp,
    load_model_config,
    get_embedding_model,
    get_research_main_model,
    get_research_vision_model,
    get_general_text_model,
    get_general_vision_model,
    get_general_vision2_model,
    get_general_coder_model,
    get_model_metadata,
)
import backend.models

@pytest.fixture(autouse=True)
def reset_caching():
    """Reset cached config before each test."""
    backend.models._cached_config = None
    yield
    backend.models._cached_config = None

@pytest.fixture
def test_app(login_as, admin_a):
    """A minimal Flask app with the models blueprint, logged in as an admin (users are tested with `login_as(test_app, user_b)`)."""
    app = Flask(__name__)
    app.register_blueprint(models_bp, url_prefix='/api/models')
    login_as(app, admin_a)
    return app

@pytest.fixture
def client(test_app):
    return test_app.test_client()

# -------------------------------------------------------------------------
# Test Config Helpers & Caching / Fallback
# -------------------------------------------------------------------------

@patch("backend.models.requests.get")
def test_load_model_config_from_proxy(mock_get):
    """Test successful dynamic loading from the external proxy."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "embedding": "proxy_embedding_model",
        "research": {"main": "proxy_research_main"},
        "general": {"text": "proxy_general_text"}
    }
    mock_get.return_value = mock_response

    config = load_model_config()
    assert config["embedding"] == "proxy_embedding_model"
    assert config["research"]["main"] == "proxy_research_main"
    assert config["general"]["text"] == "proxy_general_text"
    
    # Assert requests.get was called
    mock_get.assert_called_once_with(f"{backend.models.PROXY_URL}/api/models/config", timeout=5)

@patch("backend.models.requests.get")
def test_load_model_config_caching(mock_get):
    """Test that dynamic loading is cached and doesn't repeat requests."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"embedding": "proxy_embedding_model"}
    mock_get.return_value = mock_response

    # Load first time
    config1 = load_model_config()
    # Load second time
    config2 = load_model_config()

    assert config1 == config2
    # requests.get should be called exactly once due to caching
    mock_get.assert_called_once()

@patch("backend.models.requests.get")
def test_load_model_config_local_fallback(mock_get):
    """Test robust local fallback to config.json when proxy is offline."""
    # Force requests to fail
    mock_get.side_effect = Exception("Proxy offline")

    dummy_local_config = {
        "embedding": "fallback_embedding_model",
        "research": {"main": "fallback_research_main"},
        "general": {
            "text": "fallback_general_text",
            "vision": "fallback_general_vision",
            "vision2": "fallback_general_vision2",
            "coder": "fallback_general_coder"
        }
    }
    
    # Mock builtins open to read dummy_local_config
    with patch("builtins.open", mock_open(read_data=json.dumps(dummy_local_config))):
        config = load_model_config()
        
    assert config["embedding"] == "fallback_embedding_model"
    assert config["research"]["main"] == "fallback_research_main"
    assert config["general"]["text"] == "fallback_general_text"

# -------------------------------------------------------------------------
# Test Helper Functions
# -------------------------------------------------------------------------

@patch("backend.models.load_model_config")
def test_get_model_helpers(mock_load_cfg):
    dummy_config = {
        "embedding": "emb_model",
        "research": {
            "main": "res_main_model",
            "vision": "res_vision_model"
        },
        "general": {
            "text": "gen_text_model",
            "vision": "gen_vision_model",
            "vision2": "gen_vision2_model",
            "coder": "gen_coder_model"
        }
    }
    mock_load_cfg.return_value = dummy_config

    assert get_embedding_model() == "emb_model"
    assert get_research_main_model() == "res_main_model"
    assert get_research_vision_model() == "res_vision_model"
    assert get_general_text_model() == "gen_text_model"
    assert get_general_vision_model() == "gen_vision_model"
    assert get_general_vision2_model() == "gen_vision2_model"
    assert get_general_coder_model() == "gen_coder_model"

@patch("backend.models.load_model_config")
def test_get_research_vision_model_fallback(mock_load_cfg):
    """Test research vision model fallbacks to general vision model when not explicitly declared."""
    dummy_config = {
        "research": {
            "main": "res_main_model"
        },
        "general": {
            "vision": "gen_vision_fallback_model"
        }
    }
    mock_load_cfg.return_value = dummy_config
    assert get_research_vision_model() == "gen_vision_fallback_model"

# -------------------------------------------------------------------------
# Test Model Metadata Matching
# -------------------------------------------------------------------------

@patch("backend.models.load_model_config")
def test_get_model_metadata(mock_load_cfg):
    dummy_config = {
        "model_metadata": {
            "model_A": {"context_window": 100, "tokenizer": "tokenizer_A"},
            "model_B": {"context_window": 200, "tokenizer": "tokenizer_B"}
        }
    }
    mock_load_cfg.return_value = dummy_config

    # Exact match
    meta = get_model_metadata("model_A")
    assert meta["context_window"] == 100

    # case-insensitive match
    meta_case = get_model_metadata("MODEL_b")
    assert meta_case["context_window"] == 200

    # Tokenizer match
    meta_tok = get_model_metadata("tokenizer_A")
    assert meta_tok["context_window"] == 100

    # Mapped HF name match
    # HF name "Qwen/Qwen3.6-35B-A3B" maps to "Qwen/Qwen3.6-35B-A3B-UD-Q4_K_XL"
    dummy_config_mapped = {
        "model_metadata": {
            "Qwen/Qwen3.6-35B-A3B-UD-Q4_K_XL": {"context_window": 500}
        }
    }
    mock_load_cfg.return_value = dummy_config_mapped
    meta_mapped = get_model_metadata("Qwen/Qwen3.6-35B-A3B")
    assert meta_mapped["context_window"] == 500

    # Missing model metadata should raise ValueError
    with pytest.raises(ValueError, match="Model metadata not found"):
        get_model_metadata("non_existent_model")

# -------------------------------------------------------------------------
# Test Flask Pass-Through Routing
# -------------------------------------------------------------------------

@patch("backend.models.requests.request")
def test_pass_through_streaming_proxy(mock_req, client):
    """Test standard chunk-by-chunk stream pass-through routing."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "text/event-stream"}
    # Mock chunk generator
    mock_response.iter_content.return_value = [b"data: chunk1\n\n", b"data: chunk2\n\n"]
    mock_req.return_value = mock_response

    response = client.post("/api/models/v1/chat/completions", json={"model": "model_x"})
    
    assert response.status_code == 200
    assert response.headers.get("Content-Type") == "text/event-stream"
    assert response.data == b"data: chunk1\n\ndata: chunk2\n\n"
    
    mock_req.assert_called_once()
    args, kwargs = mock_req.call_args
    assert kwargs["stream"] is True

def test_proxy_url_dynamic_resolution():
    """Test that accessing PROXY_URL dynamically reflects changes in config.AI_PROXY_URL."""
    from backend import config
    import backend.models

    original_url = config.AI_PROXY_URL
    try:
        config.AI_PROXY_URL = "http://temp-proxy-1"
        assert backend.models.PROXY_URL == "http://temp-proxy-1"

        config.AI_PROXY_URL = "http://temp-proxy-2/"
        assert backend.models.PROXY_URL == "http://temp-proxy-2"
    finally:
        config.AI_PROXY_URL = original_url

@patch("backend.models.requests.get")
@patch("builtins.open")
def test_load_model_config_ultimate_fallback(mock_file, mock_get):
    """Test that load_model_config returns the hardcoded default config when proxy and file open both fail."""
    mock_get.side_effect = Exception("Proxy error")
    mock_file.side_effect = FileNotFoundError("File not found")

    config_data = load_model_config()
    assert config_data == backend.models.DEFAULT_HARDCODED_CONFIG
    assert config_data["embedding"] == "embeddinggemma/embeddinggemma-300M-Q8_0"


@patch("backend.models.requests.request")
def test_pass_through_trailing_and_non_trailing_slashes(mock_req, client):
    """Test that both /api/models and /api/models/ correctly route to pass_through."""
    with patch("backend.config.AI_PROXY_URL", "http://localhost:5001"):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.iter_content.return_value = [b'{"success": true}']
        mock_req.return_value = mock_response

        # Test without trailing slash
        response_no_slash = client.get("/api/models")
        assert response_no_slash.status_code == 200
        assert response_no_slash.json == {"success": True}
        
        # Check forwarded URL
        _, kwargs = mock_req.call_args_list[-1]
        assert kwargs["url"] == "http://localhost:5001/api/models/"

        # Test with trailing slash
        response_slash = client.get("/api/models/")
        assert response_slash.status_code == 200
        assert response_slash.json == {"success": True}
        
        # Check forwarded URL
        _, kwargs = mock_req.call_args_list[-1]
        assert kwargs["url"] == "http://localhost:5001/api/models/"


@pytest.mark.parametrize("method,path", [("post", "/api/models/load"), ("put", "/api/models/x"), ("delete", "/api/models/x"),
                                          ("post", "/api/models/unload"), ("options", "/api/models/load")])
@patch("backend.models.requests.request")
def test_model_changes_are_403_for_a_user_and_nothing_is_forwarded(mock_req, method, path, test_app, login_as, user_b):
    login_as(test_app, user_b)
    response = getattr(test_app.test_client(), method)(path, json={"model": "m"})
    assert response.status_code == 403
    mock_req.assert_not_called()  # no load, unload or any other call reaches the proxy


@patch("backend.models.requests.request")
def test_model_list_stays_open_to_a_user_and_identity_headers_are_not_forwarded(mock_req, test_app, login_as, user_b):
    mock_response = MagicMock()
    mock_response.iter_content.return_value = [b"[]"]
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "application/json"}
    mock_req.return_value = mock_response
    login_as(test_app, user_b)
    response = test_app.test_client().get("/api/models/", headers={
        "Cf-Access-Jwt-Assertion": "jwt-token", "Cookie": "CF_Authorization=abc", "Authorization": "Bearer secret",
        "X-Custom": "kept", "Accept": "application/json"})
    assert response.status_code == 200
    forwarded = {k.lower(): v for k, v in mock_req.call_args.kwargs["headers"].items()}
    assert not {"cf-access-jwt-assertion", "cookie", "authorization", "host"} & set(forwarded)
    assert forwarded["x-custom"] == "kept" and forwarded["accept"] == "application/json"


@patch("backend.models.requests.request")
def test_the_admin_can_still_change_models_and_headers_are_stripped_for_every_method(mock_req, test_app):
    mock_response = MagicMock()
    mock_response.iter_content.return_value = [b"ok"]
    mock_response.status_code = 200
    mock_response.headers = {}
    mock_req.return_value = mock_response
    response = test_app.test_client().post("/api/models/load", json={"model": "m"}, headers={"Cookie": "CF_Authorization=abc", "CF-ACCESS-JWT-ASSERTION": "t"})
    assert response.status_code == 200
    forwarded = {k.lower() for k in mock_req.call_args.kwargs["headers"]}
    assert "cookie" not in forwarded and "cf-access-jwt-assertion" not in forwarded

