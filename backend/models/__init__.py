import os
import json
from flask import Blueprint, request, Response
import requests

from backend import config
from backend.auth.context import forbid_non_admin

models_bp = Blueprint('models', __name__)

def __getattr__(name: str):
    if name == 'PROXY_URL':
        return config.AI_PROXY_URL.rstrip("/")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

DEFAULT_HARDCODED_CONFIG = {
    "research": {
        "main": "NVIDIA/NVIDIA-Nemotron-3-Nano-30B-A3B-UD-Q4_K_XL"
    },
    "general": {
        "text": "NVIDIA/NVIDIA-Nemotron-3-Nano-30B-A3B-UD-Q4_K_XL",
        "vision": "Qwen/Qwen3.6-35B-A3B-UD-Q4_K_XL",
        "vision2": "Qwen/Qwen3.5-122B-A10B-UD-Q2_K_XL",
        "vision_small": "Google/Gemma4-26B-A4B-it",
        "coder": "Qwen/Qwen3-Coder-Next-UD-Q4_K_XL"
    },
    "embedding": "embeddinggemma/embeddinggemma-300M-Q8_0",
    "embedding_tokenizer": "google/embeddinggemma-300m",
    "model_metadata": {
        "NVIDIA/NVIDIA-Nemotron-3-Nano-30B-A3B-UD-Q4_K_XL": {
            "context_window": 1048576,
            "tokenizer": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16"
        },
        "Qwen/Qwen3.6-35B-A3B-UD-Q4_K_XL": {
            "context_window": 262144,
            "tokenizer": "Qwen/Qwen3.6-35B-A3B"
        },
        "Qwen/Qwen3.5-122B-A10B-UD-Q2_K_XL": {
            "context_window": 262144,
            "tokenizer": "Qwen/Qwen3.5-122B-A10B"
        },
        "Google/Gemma4-26B-A4B-it": {
            "context_window": 150000,
            "tokenizer": "google/gemma-4-26B-A4B-it"
        },
        "Qwen/Qwen3-Coder-Next-UD-Q4_K_XL": {
            "context_window": 262144,
            "tokenizer": "Qwen/Qwen3-Coder-Next"
        }
    }
}

# Never sent upstream: the caller's identity and session.
_NOT_FORWARDED_HEADERS = {'host', 'cookie', 'authorization', 'cf-access-jwt-assertion'}

@models_bp.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
@models_bp.route('/', defaults={'path': ''}, endpoint='pass_through_slash', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
@models_bp.route('', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
def pass_through(path):
    """
    Stateless pass-through forwarding /api/models requests to the proxy microservice.

    Reading the model list (GET) is open to every user; loading, unloading and any other change is admin only. The
    caller's identity (the Access JWT, cookies, Authorization) is never forwarded: the proxy uses its own keys.
    """
    if request.method not in ('GET', 'HEAD'):
        denied = forbid_non_admin()
        if denied:
            return denied
    url = f"{config.AI_PROXY_URL.rstrip('/')}/api/models/{path}"
    headers = {key: value for key, value in request.headers if key.lower() not in _NOT_FORWARDED_HEADERS}
    response = requests.request(
        method=request.method,
        url=url,
        headers=headers,
        data=request.get_data(),
        params=request.args,
        allow_redirects=False,
        stream=True
    )
    
    def generate():
        for chunk in response.iter_content(chunk_size=4096):
            yield chunk

    return Response(
        generate(),
        status=response.status_code,
        headers={key: value for key, value in response.headers.items() if key.lower() not in ['content-encoding', 'transfer-encoding']}
    )

# -------------------------------------------------------------------------
# Static Config Helpers
# -------------------------------------------------------------------------

_cached_config = None

def load_model_config() -> dict:
    global _cached_config
    if _cached_config is not None:
        return _cached_config
    
    proxy_url = config.AI_PROXY_URL.rstrip("/")
    try:
        url = f"{proxy_url}/api/models/config"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        _cached_config = response.json()
        return _cached_config
    except Exception as e:
        import logging
        logging.warning(f"Failed to fetch model config from proxy: {e}. Trying local fallback.")
        
        try:
            config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "inference_proxy", "config.json"))
            with open(config_path, 'r', encoding='utf-8') as f:
                _cached_config = json.load(f)
                return _cached_config
        except Exception as fe:
            logging.error(f"Failed to load local config.json fallback: {fe}. Falling back to default hardcoded config.")
            _cached_config = DEFAULT_HARDCODED_CONFIG
            return _cached_config

def get_embedding_model() -> str:
    return load_model_config()['embedding']

def get_research_main_model() -> str:
    return load_model_config()['research']['main']

def get_research_vision_model() -> str:
    cfg = load_model_config()
    return cfg['research'].get('vision') or cfg['general']['vision']

def get_general_text_model() -> str:
    return load_model_config()['general']['text']

def get_general_vision_model() -> str:
    return load_model_config()['general']['vision']

def get_general_vision2_model() -> str:
    return load_model_config()['general']['vision2']

def get_general_coder_model() -> str:
    return load_model_config()['general']['coder']

def get_model_metadata(model_name: str) -> dict:
    config_data = load_model_config()
    metadata = config_data.get("model_metadata", {})
    if model_name in metadata:
        return metadata[model_name]
    
    hf_mapping = {
        "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16": "NVIDIA/NVIDIA-Nemotron-3-Nano-30B-A3B-UD-Q4_K_XL",
        "Qwen/Qwen3.6-35B-A3B": "Qwen/Qwen3.6-35B-A3B-UD-Q4_K_XL",
        "Qwen/Qwen3.5-122B-A10B": "Qwen/Qwen3.5-122B-A10B-UD-Q2_K_XL",
        "google/gemma-4-26B-A4B-it": "Google/Gemma4-26B-A4B-it",
        "Qwen/Qwen3-Coder-Next": "Qwen/Qwen3-Coder-Next-UD-Q4_K_XL"
    }
    mapped_name = hf_mapping.get(model_name)
    if mapped_name and mapped_name in metadata:
        return metadata[mapped_name]
    
    for k, v in metadata.items():
        if k.lower() == model_name.lower() or v.get("tokenizer", "").lower() == model_name.lower():
            return v
            
    raise ValueError(f"Model metadata not found for model: '{model_name}'")
