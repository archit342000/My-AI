import os
import json
import datetime
import uuid

# Define log paths
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_BASE_DIR = os.path.join(BACKEND_DIR, "logs")
LLM_LOG_DIR = os.path.join(LOG_BASE_DIR, "llm_calls")
TOOL_LOG_DIR = os.path.join(LOG_BASE_DIR, "tool_calls")
GENERAL_LOG_DIR = os.path.join(LOG_BASE_DIR, "general")

# Ensure directories exist
os.makedirs(LLM_LOG_DIR, exist_ok=True)
os.makedirs(TOOL_LOG_DIR, exist_ok=True)
os.makedirs(GENERAL_LOG_DIR, exist_ok=True)

def _get_timestamp():
    return datetime.datetime.now()

def _save_log(directory, entry, prefix=""):
    timestamp = _get_timestamp()
    transaction_id = str(uuid.uuid4())
    safe_ts = timestamp.strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}{safe_ts}_{transaction_id[:8]}.json"
    filepath = os.path.join(directory, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(entry, f, indent=2, ensure_ascii=False)
    return filename

def log_llm_call(payload, response_text, model, chat_id=None, duration_s=0, call_type="stream"):
    """Logs an LLM transaction (request and final accumulated response)."""
    entry = {
        "timestamp": _get_timestamp().isoformat(),
        "chat_id": chat_id,
        "model": model,
        "type": call_type,
        "duration_s": round(duration_s, 3),
        "request": payload,
        "response": response_text
    }
    filename = _save_log(LLM_LOG_DIR, entry)
    
    # Update index
    index_path = os.path.join(LOG_BASE_DIR, "network_index.jsonl")
    index_entry = {
        "timestamp": entry["timestamp"],
        "category": "llm",
        "chat_id": chat_id,
        "model_tool": model,
        "type": call_type,
        "log_file": os.path.join("llm_calls", filename)
    }
    with open(index_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(index_entry) + "\n")

def log_tool_call(tool_name, payload, response_data, duration_s=0, chat_id=None):
    """Logs a tool/API call (e.g., Tavily search)."""
    entry = {
        "timestamp": _get_timestamp().isoformat(),
        "tool": tool_name,
        "chat_id": chat_id,
        "duration_s": round(duration_s, 3),
        "request": payload,
        "response": response_data
    }
    filename = _save_log(TOOL_LOG_DIR, entry, prefix=f"{tool_name}_")
    
    # Update index
    index_path = os.path.join(LOG_BASE_DIR, "network_index.jsonl")
    index_entry = {
        "timestamp": entry["timestamp"],
        "category": "tool",
        "chat_id": chat_id,
        "model_tool": tool_name,
        "type": "blocking",
        "log_file": os.path.join("tool_calls", filename)
    }
    with open(index_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(index_entry) + "\n")

def log_event(event_type, data):
    """Logs general system events."""
    timestamp = _get_timestamp()
    log_entry = {
        "timestamp": timestamp.isoformat(),
        "type": event_type,
        "data": data
    }
    filename = f"{timestamp.strftime('%Y%m%d')}_events.jsonl"
    filepath = os.path.join(GENERAL_LOG_DIR, filename)
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")
