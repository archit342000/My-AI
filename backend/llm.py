import requests
import json
import time
from backend.logger import log_llm_call, log_event
from backend import config

def stream_chat_completion(url, payload):
    """
    Streams the chat completion from the LM Studio API.
    Yields parsed chunks and logs the final result.
    """
    start_time = time.time()
    full_response = ""
    stream_completed = False
    model = payload.get("model", "unknown")
    
    base_url = url.rstrip("/")
    if not base_url.endswith("/v1"):
        endpoint = f"{base_url}/v1/chat/completions"
    else:
        endpoint = f"{base_url}/chat/completions"

    try:
        response = requests.post(
            endpoint,
            json=payload,
            stream=True,
            timeout=(5, None) # Connect timeout 5s, read timeout None
        )
        
        for line in response.iter_lines():
            if not line: continue
            decoded_line = line.decode('utf-8')
            
            if not decoded_line.startswith('data: '): continue
            if decoded_line == 'data: [DONE]':
                stream_completed = True
                break
            
            try:
                data_json = json.loads(decoded_line[6:])
                choices = data_json.get('choices', [])
                if choices:
                    delta = choices[0].get('delta', {})
                    if 'content' in delta: full_response += delta['content'] or ''
                    if 'reasoning_content' in delta: full_reasoning = delta.get('reasoning_content', '')
                    # We don't log reasoning separately in the summary for now, but it's in the log file
            except:
                pass
                
            yield decoded_line
        
        # Log the full transaction
        duration = time.time() - start_time
        log_llm_call(payload, full_response, model, duration_s=duration, call_type="stream")
            
    except Exception as e:
        error_msg = f"Error in stream_chat_completion: {e}"
        log_event("llm_stream_error", {"error": str(e)})
        yield f"data: {json.dumps({'error': str(e)})}"


def chat_completion(url, payload):
    """
    Non-streaming chat completion. Returns the full response content as a string.
    """
    start_time = time.time()
    try:
        # Ensure non-streaming
        payload = dict(payload)
        payload["stream"] = False
        model = payload.get("model", "unknown")
        
        base_url = url.rstrip("/")
        if not base_url.endswith("/v1"):
            endpoint = f"{base_url}/v1/chat/completions"
        else:
            endpoint = f"{base_url}/chat/completions"
            
        response = requests.post(
            endpoint,
            json=payload,
            timeout=config.TIMEOUT_LLM_BLOCKING or (5, 60)
        )
        response.raise_for_status()
        
        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        # Log the full transaction
        duration = time.time() - start_time
        log_llm_call(payload, content, model, duration_s=duration, call_type="blocking")
        
        return content
        
    except Exception as e:
        log_event("llm_blocking_error", {"error": str(e)})
        return ""
