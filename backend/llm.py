import requests
import json
import time
from backend.logger import log_llm_call, log_event
from backend import config

import httpx

def _normalize_messages(messages):
    """
    Ensures message structure is strictly compliant with OAI spec.
    Strips prohibited fields from roles and ensures tool_calls have 'type'.
    """
    normalized = []
    for msg in messages:
        m = dict(msg)
        role = m.get('role')

        # Remove internal database/UI meta-fields
        for field in ['id', 'chat_id', 'timestamp', 'is_hidden', 'model']:
            m.pop(field, None)

        if role in ['system', 'user']:
            # User/System cannot have tool_calls or tool_call_id
            m.pop('tool_calls', None)
            m.pop('tool_call_id', None)
            m.pop('name', None)
        elif role == 'assistant':
            # Assistant can have tool_calls if non-empty
            tcs = m.get('tool_calls')
            # Handle stringified tool_calls from database history
            if isinstance(tcs, str):
                try:
                    tcs = json.loads(tcs)
                except (json.JSONDecodeError, TypeError):
                    tcs = []
            if isinstance(tcs, list) and len(tcs) > 0:
                for tc in tcs:
                    if isinstance(tc, dict):
                        tc['type'] = 'function' # Force type
                m['tool_calls'] = tcs
            else:
                m.pop('tool_calls', None)
            m.pop('tool_call_id', None)
            # Remove name if None (OAI spec: name must be string if present)
            if m.get('name') is None:
                m.pop('name', None)
        elif role == 'tool':
            # Tool message MUST have tool_call_id and content
            m.pop('tool_calls', None)
            if not m.get('tool_call_id'):
                m['tool_call_id'] = "unknown"
            # Tool messages require a name field (the tool name)
            if not m.get('name'):
                m['name'] = "unknown"
        
        # Ensure content is never None (OAI spec: must be string)
        if m.get('content') is None:
            m['content'] = ""

        normalized.append(m)
    return normalized

async def stream_chat_completion(url, payload, chat_id=None, chat_template_kwargs=None, timeout=None):
    """
    Streams the chat completion from the OpenAI-compatible local AI API (Async).
    Yields parsed chunks and logs the final result, even if closed early.

    Args:
        url: Base URL of the LLM API
        payload: Chat completion payload (will be modified with chat_template_kwargs if provided)
        chat_id: Optional chat ID for logging
        chat_template_kwargs: Optional dict of kwargs to pass to the chat template
            (e.g., {"enable_thinking": False} to skip reasoning phase)
        timeout: Optional custom timeout in seconds (defaults to config.TIMEOUT_LLM_ASYNC or 5.0)
    """
    # Normalize messages for strict OpenAI compatibility (e.g., llama.cpp/OAI spec)
    if "messages" in payload:
        payload["messages"] = _normalize_messages(payload["messages"])

    start_time = time.time()
    full_response = ""
    full_reasoning = ""
    tool_calls = {} # {index: tool_call_dict}
    model = payload.get("model", "unknown")
    timings = None

    # Apply chat_template_kwargs if provided
    if chat_template_kwargs:
        payload = dict(payload)
        payload["chat_template_kwargs"] = payload.get("chat_template_kwargs", {})
        payload["chat_template_kwargs"].update(chat_template_kwargs)

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
        # Use custom timeout if provided, otherwise use config or default to 5 seconds
        timeout_value = timeout or config.TIMEOUT_LLM_ASYNC or 5.0
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_value, read=None), headers=headers) as client:
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
                            elif 'reasoning' in delta: full_reasoning += delta.get('reasoning', '')
                            
                            if 'tool_calls' in delta:
                                for tc_delta in delta['tool_calls']:
                                    idx = tc_delta.get('index', 0)
                                    if idx not in tool_calls:
                                        tool_calls[idx] = tc_delta
                                    else:
                                        # Merge arguments
                                        if 'function' in tc_delta and 'arguments' in tc_delta['function']:
                                            if 'function' not in tool_calls[idx]: tool_calls[idx]['function'] = {'arguments': ''}
                                            tool_calls[idx]['function']['arguments'] += tc_delta['function']['arguments']
                    except:
                        pass
                        
                    yield line
                    
    except Exception as e:
        log_event("llm_stream_error", {"error": str(e), "url": endpoint, "chat_id": chat_id})
        yield f"data: {json.dumps({'error': str(e)})}"
    finally:
        # Log the transaction (full or partial)
        duration = time.time() - start_time
        final_log_text = ""
        if full_reasoning:
            final_log_text += f"<think>\n{full_reasoning}\n</think>\n"
        final_log_text += (full_response or "")
        
        # Sort and clean tool calls for logging
        sorted_tool_calls = [tool_calls[i] for i in sorted(tool_calls.keys())] if tool_calls else None
            
        log_llm_call(payload, final_log_text, model, chat_id=chat_id, duration_s=duration, call_type="stream", timings=timings, tool_calls=sorted_tool_calls)


def chat_completion(url, payload, chat_id=None, chat_template_kwargs=None):
    """
    Non-streaming chat completion. Returns the full response content as a string.

    Args:
        url: Base URL of the LLM API
        payload: Chat completion payload (will be modified with chat_template_kwargs if provided)
        chat_id: Optional chat ID for logging
        chat_template_kwargs: Optional dict of kwargs to pass to the chat template
            (e.g., {"enable_thinking": False} to skip reasoning phase)
    """
    # Normalize messages for strict OpenAI compatibility (e.g., llama.cpp/OAI spec)
    if "messages" in payload:
        payload["messages"] = _normalize_messages(payload["messages"])

    start_time = time.time()
    try:
        # Apply chat_template_kwargs if provided
        if chat_template_kwargs:
            payload = dict(payload)
            payload["chat_template_kwargs"] = payload.get("chat_template_kwargs", {})
            payload["chat_template_kwargs"].update(chat_template_kwargs)

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
        tool_calls = msg.get("tool_calls")
        if not tool_calls: # check for empty list
             tool_calls = None

        final_output = ""
        if reasoning:
            final_output += f"<think>\n{reasoning}\n</think>\n"
        if content:
            final_output += content
        
        # Log the full transaction
        duration = time.time() - start_time
        log_llm_call(payload, final_output, model, chat_id=chat_id, duration_s=duration, call_type="blocking", timings=timings, tool_calls=tool_calls)
        
        return final_output
        
    except Exception as e:
        duration = time.time() - start_time
        log_llm_call(payload, f"FAILED: {str(e)}", model, chat_id=chat_id, duration_s=duration, call_type="blocking")
        log_event("llm_blocking_error", {"error": str(e), "url": endpoint if 'endpoint' in locals() else url, "chat_id": chat_id})
        return ""
