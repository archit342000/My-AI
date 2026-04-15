"""Token counting module using HuggingFace transformers tokenizer.

This module provides accurate token counting for embedding models using the
actual tokenizer from HuggingFace. It loads the HuggingFace token from
secrets/HF_TOKEN (with fallback to HF_TOKEN environment variable).
"""
import os
from transformers import AutoTokenizer
import logging

# Suppress noisy sequence length warnings from transformers tokenizer
# since we handle explicit truncation/chunking in our own pipeline.
import transformers
transformers.logging.set_verbosity_error()

# HuggingFace token loading
def _get_hf_token():
    """Load HuggingFace token from secrets or environment variable.

    Returns:
        str or None: The HuggingFace token if available, None otherwise.
    """
    # Try to load from secrets first
    try:
        with open("/run/secrets/HF_TOKEN", "r") as f:
            return f.read().strip()
    except (IOError, FileNotFoundError):
        pass

    # Fallback to environment variable
    return os.environ.get("HF_TOKEN", None)


# Global tokenizer instance
_tokenizer = None


def get_tokenizer():
    """Get the embedding model tokenizer, loading it lazily.

    The tokenizer is loaded from the 'embedding_tokenizer' model ID in
    backend/model_config.json. HuggingFace token is used for authenticated models.

    Returns:
        AutoTokenizer: The transformers tokenizer instance.
    """
    global _tokenizer

    if _tokenizer is not None:
        return _tokenizer

    import json
    import os

    # Load model config to get the embedding tokenizer name
    config_path = os.path.join(os.path.dirname(__file__), "model_config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        model_config = json.load(f)

    tokenizer_name = model_config.get("embedding_tokenizer")
    if not tokenizer_name:
        raise ValueError("model_config.json missing 'embedding_tokenizer' field")

    # Get HuggingFace token for authenticated models
    hf_token = _get_hf_token()

    # Load the tokenizer
    _tokenizer = AutoTokenizer.from_pretrained(
        tokenizer_name,
        token=hf_token if hf_token else None
    )

    return _tokenizer


def count_tokens(text: str) -> int:
    """Count tokens in text using the embedding model's tokenizer.

    Args:
        text: The text to count tokens for.

    Returns:
        int: The number of tokens in the text.
    """
    tokenizer = get_tokenizer()
    return len(tokenizer.encode(text, add_special_tokens=False))


def truncate_text_by_tokens(text: str, max_tokens: int, model_max_tokens: int = None) -> str:
    """Truncate text to fit within token limit.

    Args:
        text: The text to truncate.
        max_tokens: Maximum number of tokens allowed.
        model_max_tokens: Optional model's maximum context window. If provided,
            will use the smaller of max_tokens and model_max_tokens.

    Returns:
        The truncated text that fits within the token limit.
    """
    if not text:
        return text

    # Use the smaller of max_tokens and model_max_tokens if provided
    token_limit = max_tokens
    if model_max_tokens is not None:
        token_limit = min(max_tokens, model_max_tokens)

    # Always use accurate token counting via tokenizer

    # Get tokenizer to encode/decode
    tokenizer = get_tokenizer()
    encoded = tokenizer.encode(text, add_special_tokens=False)

    if len(encoded) <= token_limit:
        return text

    # Truncate to max_tokens and decode
    truncated = encoded[:token_limit]
    return tokenizer.decode(truncated, skip_special_tokens=True)


def split_text_by_tokens(text: str, max_tokens: int) -> list:
    """Split text into a list of chunks, ensuring each is within max_tokens.

    This is a 'Hard Split' of last resort. It does not respect structure
    (paragraphs/sentences) but guarantees 100% compliance with token limits
    without data loss (no truncation).

    Args:
        text: The text to split.
        max_tokens: Maximum tokens per chunk.

    Returns:
        List[str]: Chunks that are each <= max_tokens.
    """
    if not text:
        return []

    tokenizer = get_tokenizer()
    encoded = tokenizer.encode(text, add_special_tokens=False)

    if len(encoded) <= max_tokens:
        return [text]

    chunks = []
    for i in range(0, len(encoded), max_tokens):
        chunk_ids = encoded[i:i + max_tokens]
        chunks.append(tokenizer.decode(chunk_ids, skip_special_tokens=True))

    return chunks
