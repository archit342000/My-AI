import requests
import json
import time
from backend.logger import log_llm_call, log_event
from backend import config

import httpx

async def stream_chat_completion(url, payload):
    """
    Streams the chat completion from the OpenAI-compatible local AI API (Async).
    Yields parsed chunks and logs the final result.
    """
    start_time = time.time()
    full_response = ""
    full_reasoning = ""
    model = payload.get("model", "unknown")
    
    base_url = url.rstrip("/")
    if not base_url.endswith("/v1"):
        endpoint = f"{base_url}/v1/chat/completions"
    else:
        endpoint = f"{base_url}/chat/completions"

    headers = {
        "Content-Type": "application/json"
    }
    
    request_payload = dict(payload)
    if "api_key" in request_payload:
        headers["Authorization"] = f"Bearer {request_payload.pop('api_key')}"
    elif config.AI_API_KEY:
        headers["Authorization"] = f"Bearer {config.AI_API_KEY}"

    try:
        timings = None
        async with httpx.AsyncClient(timeout=httpx.Timeout(config.TIMEOUT_LLM_ASYNC or 5.0, read=None), headers=headers) as client:
            async with client.stream("POST", endpoint, json=request_payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line: continue
                    
                    if not line.startswith('data: '): continue
                    if line == 'data: [DONE]':
                        break
                    
                    try:
                        data_json = json.loads(line[6:])
                        if 'timings' in data_json:
                            timings = data_json['timings']
                        choices = data_json.get('choices', [])
                        if choices:
                            delta = choices[0].get('delta', {})
                            if 'content' in delta: full_response += delta['content'] or ''
                            if 'reasoning_content' in delta: full_reasoning += delta.get('reasoning_content', '')
                    except:
                        pass
                        
                    yield line
        
        # Log the full transaction
        duration = time.time() - start_time
        is_json_requested = "response_format" in payload
        final_log_text = ""
        
        if is_json_requested:
            # For JSON, the 'full_response' should be empty, and 'full_reasoning' contains the JSON.
            final_log_text = full_response or full_reasoning
        else:
            if full_reasoning:
                final_log_text += f"<think>\n{full_reasoning}\n</think>\n"
            final_log_text += (full_response or "")
            
        log_llm_call(payload, final_log_text, model, duration_s=duration, call_type="stream", timings=timings)
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        error_msg = f"Error in stream_chat_completion: {e}"
        log_event("llm_stream_error", {"error": str(e)})
        yield f"data: {json.dumps({'error': str(e)})}"


def chat_completion(url, payload):
    """
    Non-streaming chat completion. Returns the full response content as a string.
    """
    start_time = time.time()
    try:
        # Ensure non-streaming and create local copy
        request_payload = dict(payload)
        request_payload["stream"] = False
        model = request_payload.get("model", "unknown")
        
        base_url = url.rstrip("/")
        if not base_url.endswith("/v1"):
            endpoint = f"{base_url}/v1/chat/completions"
        else:
            endpoint = f"{base_url}/chat/completions"
            
        headers = {
            "Content-Type": "application/json"
        }
        if "api_key" in request_payload:
            headers["Authorization"] = f"Bearer {request_payload.pop('api_key')}"
        elif config.AI_API_KEY:
            headers["Authorization"] = f"Bearer {config.AI_API_KEY}"

        response = requests.post(
            endpoint,
            json=request_payload,
            headers=headers,
            timeout=config.TIMEOUT_LLM_BLOCKING or (5, 60)
        )
        response.raise_for_status()
        
        data = response.json()
        timings = data.get("timings")
        
        msg = data.get("choices", [{}])[0].get("message", {})
        content = msg.get("content", "")
        reasoning = msg.get("reasoning_content", "")
        
        # AGENTS.md compliance: always prioritize gathering all emitted signals.
        # However, for structured output (json_schema or json_object), 
        # Local AI backend quirks mean the JSON is often in reasoning_content.
        
        is_json_requested = "response_format" in payload
        final_output = ""
        
        if is_json_requested:
            # AGENTS.md: For structured output, local AI backends often stream the JSON inside 'reasoning_content'.
            # We prioritize it as the primary functional payload. No tags.
            if reasoning and not content:
                final_output = reasoning
            elif content:
                final_output = content
            elif reasoning:
                final_output = reasoning
        else:
            # Standard chat: Preserving reasoning in history via <think> tags,
            # but functional logic in research.py will ignore it.
            if reasoning:
                final_output += f"<think>\n{reasoning}\n</think>\n"
            if content:
                final_output += content
        
        # Log the full transaction
        duration = time.time() - start_time
        log_llm_call(payload, final_output, model, duration_s=duration, call_type="blocking", timings=timings)
        
        return final_output
        
    except Exception as e:
        log_event("llm_blocking_error", {"error": str(e)})
        return ""
