"""Model configuration loader - all model names must come from model_config.json"""
import json
import os
from backend.logger import log_event


def get_model_config_path():
    """Get the path to model_config.json"""
    return os.path.join(os.path.dirname(__file__), 'model_config.json')


def load_model_config():
    """
    Load the model configuration from model_config.json.

    Returns:
        dict: The model configuration

    Raises:
        FileNotFoundError: If model_config.json doesn't exist
        ValueError: If the config is invalid or missing required fields
    """
    config_path = get_model_config_path()

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Model config file not found at {config_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in model config: {e}")

    # Validate required fields
    if not isinstance(data, dict):
        raise ValueError("Model config must be a JSON object")

    # Validate embedding model exists
    if 'embedding' not in data or not data['embedding']:
        raise ValueError("Model config must have 'embedding' field")

    # Validate research models exist
    if 'research' not in data or not isinstance(data['research'], dict):
        raise ValueError("Model config must have 'research' field with object")
    if 'main' not in data['research'] or not data['research']['main']:
        raise ValueError("Model config must have 'research.main' field")
    if 'vision' not in data['research'] or not data['research']['vision']:
        raise ValueError("Model config must have 'research.vision' field")

    # Validate general models exist
    if 'general' not in data or not isinstance(data['general'], dict):
        raise ValueError("Model config must have 'general' field with object")
    if 'text' not in data['general'] or not data['general']['text']:
        raise ValueError("Model config must have 'general.text' field")

    return data


def get_embedding_model():
    """Get the embedding model name from config."""
    config = load_model_config()
    return config['embedding']


def get_research_main_model():
    """Get the research main model name from config."""
    config = load_model_config()
    return config['research']['main']


def get_research_vision_model():
    """Get the research vision model name from config."""
    config = load_model_config()
    return config['research']['vision']


def get_general_text_model():
    """Get the general text model name from config."""
    config = load_model_config()
    return config['general']['text']


def get_general_vision_model():
    """Get the general vision model name from config."""
    config = load_model_config()
    return config['general']['vision']


def get_general_vision2_model():
    """Get the general vision2 model name from config."""
    config = load_model_config()
    return config['general']['vision2']



def get_general_coder_model():
    """Get the general coder model name from config."""
    config = load_model_config()
    return config['general']['coder']


def validate_model_in_config(model_name):
    """
    Check if a model name exists in the config.

    Args:
        model_name: The model name to validate

    Returns:
        bool: True if the model exists in config, False otherwise
    """
    try:
        config = load_model_config()
        all_models = set()
        all_models.add(config['embedding'])
        all_models.add(config['research']['main'])
        all_models.add(config['research']['vision'])
        all_models.update(config['general'].values())

        return model_name in all_models
    except Exception:
        return False
