import requests
import os
from bs4 import BeautifulSoup
import json
import time
import datetime
from urllib.parse import urlparse
from backend import config
from backend.logger import log_tool_call, log_llm_call, log_event
from backend.token_counter import count_tokens

def get_current_time():
    """Returns the current local date and time as a formatted string."""
    # Ensure the process respects the TZ environment variable if set
    if os.name != 'nt' and hasattr(time, 'tzset'):
        time.tzset()
    now = datetime.datetime.now()
    return now.strftime("%A, %B %d, %Y %I:%M:%S %p")

def get_domain(url):
    try:
        return urlparse(url).netloc
    except:
        return ""

def check_url_safety(url):
    """
    Checks if a URL is malicious using URLhaus API.
    Returns (is_safe, reason).
    """
    try:
        data = {'url': url}
        response = requests.post('https://urlhaus-api.abuse.ch/v1/url/', data=data, timeout=config.TIMEOUT_URLHAUS)
        if response.status_code == 200:
            json_resp = response.json()
            if json_resp.get('query_status') == 'ok':
                return False, f"Blocked by URLhaus: {json_resp.get('threat', 'malicious')}"
        return True, None
    except Exception as e:
        log_event("urlhaus_check_error", {"url": url, "error": str(e)})
        return True, None # Default to safe to avoid blocking if API down

import pypdf
import io
import random

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36'
]

import httpx
import asyncio
import re
from urllib.parse import urljoin
import threading
import ipaddress
import socket
from urllib.parse import urlparse

def is_safe_web_url(url):
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ['http', 'https']:
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        ip = socket.gethostbyname(hostname)
        ip_obj = ipaddress.ip_address(ip)
        if ip_obj.is_loopback or ip_obj.is_private or ip_obj.is_link_local or ip_obj.is_multicast or ip_obj.is_reserved:
            return False
        return True
    except Exception:
        return False

async def async_chat_completion(url, payload, chat_id=None):
    start_time = time.time()
    model = payload.get("model", "unknown")
    
    # Use timeout=None. When executing multiple parallel URL ranking/selection 
    # requests, a local inference server will queue them. 
    # A short timeout like 180s will cause the client to disconnect before 
    # the server even begins processing the later requests in the queue.
    base_url = url.rstrip("/")
    endpoint = f"{base_url}/v1/chat/completions"
        
    async with httpx.AsyncClient(timeout=config.TIMEOUT_LLM_ASYNC) as client:
        try:
            resp = await client.post(endpoint, json=payload)
            resp.raise_for_status()
            data = resp.json()
            
            content = ""
            reasoning = ""
            if "choices" in data and len(data["choices"]) > 0:
                msg = data["choices"][0]["message"]
                content = msg.get("content", "")
                reasoning = msg.get("reasoning_content", "")
                
            # docs/llama_cpp_integration.md compliance:
            # For structured output (json_schema or json_object), treat 'content' as the sole source of truth.
            # reasoning_content is strictly for internal thinking.
            
            is_json_requested = "response_format" in payload
            final_output = ""
            
            if is_json_requested:
                # docs/llama_cpp_integration.md: Treat 'content' as the ONLY source of truth for JSON.
                final_output = content
            else:
                # Standard chat: Preserving reasoning in history via <think> tags, 
                # but functional logic in research.py will ignore it.
                if reasoning:
                    final_output += f"<think>\n{reasoning}\n</think>\n"
                if content:
                    final_output += content
                
            log_llm_call(payload, final_output, model, chat_id=chat_id, duration_s=time.time()-start_time, call_type="async_blocking")
            return final_output
        except Exception as e:
            log_llm_call(payload, f"Error: {str(e)}", model, chat_id=chat_id, duration_s=time.time()-start_time, call_type="async_blocking_error")
            return ""

def estimate_tokens(msgs):
    """Estimate token count using the actual tokenizer."""
    total = 0
    for m in msgs:
        content = m.get('content', '')
        if isinstance(content, str) and content.strip():
            total += count_tokens(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get('type') == 'text' and part.get('text', '').strip():
                    total += count_tokens(part.get('text', ''))
        total += 4  # overhead per message (role, formatting tokens)
    return total

def create_chunk(model, content=None, reasoning=None, finish_reason=None, **kwargs):
    delta = {}
    if content: delta["content"] = content
    if reasoning: delta["reasoning_content"] = reasoning
    return json.dumps({
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        **kwargs
    })

def validate_research_plan(content):
    """
    Validates the research plan JSON against constraints.
    Returns (clean_json_str, error_message).
    """
    if not content or not content.strip():
        return None, "Empty content received."
    
    raw = content
    
    # 1. Strip CoT reasoning
    if '</think>' in raw:
        raw = raw.split('</think>')[-1].strip()
    raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
    
    # 2. Strip markdown code fences
    raw = re.sub(r'```(?:json)?\s*\n?', '', raw).strip()
    raw = raw.replace('```', '')
    
    # 3. Parse JSON
    try:
        # Find first '{' and last '}' to handle potential leading/trailing garbage
        start_idx = raw.find('{')
        end_idx = raw.rfind('}')
        if start_idx == -1 or end_idx == -1:
             return None, "No JSON object found."
        
        json_str = raw[start_idx:end_idx+1]
        plan = json.loads(json_str)
    except Exception as e:
        return None, f"JSON parsing failed: {str(e)}"
    
    # 4. Validate structure
    if not isinstance(plan, dict):
        return None, "Root must be a JSON object."
    
    title = plan.get('title')
    if not title:
        return None, "Plan is missing a valid 'title'."
    
    sections = plan.get('sections')
    if not isinstance(sections, list) or not sections:
        return None, "Plan must have at least one section in 'sections' array."
    
    total_queries = 0
    max_per_section = config.RESEARCH_MAX_QUERIES_PER_SECTION
    max_total = config.RESEARCH_MAX_TOTAL_QUERIES
    
    for i, sec in enumerate(sections):
        heading = sec.get('heading')
        if not heading:
            return None, f"Section {i+1} is missing a 'heading'."
        
        desc = sec.get('description')
        if not desc:
            return None, f"Section {i+1} ('{heading}') is missing a 'description'."
        
        queries = sec.get('queries')
        if not isinstance(queries, list) or not queries:
            return None, f"Section {i+1} ('{heading}') has no 'queries'."
        
        if len(queries) > max_per_section:
            return None, f"Section {i+1} has {len(queries)} queries (max {max_per_section})."
        
        for j, q in enumerate(queries):
             q_text = q.get('query') if isinstance(q, dict) else str(q)
             if not q_text or not q_text.strip():
                 return None, f"Section {i+1}, query {j+1} is empty."
        
        total_queries += len(queries)
    
    if total_queries > max_total:
        return None, f"Plan has {total_queries} total queries (max {max_total})."
    
    # Convert validated plan to XML for frontend compatibility
    import html
    xml_output = [f"<research_plan>\n  <title>{html.escape(title)}</title>"]
    for sec in sections:
        xml_output.append("  <section>")
        xml_output.append(f"    <heading>{html.escape(sec.get('heading', ''))}</heading>")
        xml_output.append(f"    <description>{html.escape(sec.get('description', ''))}</description>")
        for q in sec.get('queries', []):
            q_text = q.get('query') if isinstance(q, dict) else str(q)
            topic = q.get('topic') if isinstance(q, dict) else None
            time_range = q.get('time_range') if isinstance(q, dict) else None
            start_date = q.get('start_date') if isinstance(q, dict) else None
            end_date = q.get('end_date') if isinstance(q, dict) else None
            
            attr_str = ""
            if topic: attr_str += f' topic="{html.escape(topic)}"'
            if time_range: attr_str += f' time_range="{html.escape(time_range)}"'
            if start_date: attr_str += f' start_date="{html.escape(start_date)}"'
            if end_date: attr_str += f' end_date="{html.escape(end_date)}"'
            
            xml_output.append(f"    <query{attr_str}>{html.escape(q_text)}</query>")
        xml_output.append("  </section>")
    xml_output.append("</research_plan>")
    
    return "\n".join(xml_output), None

def _apply_canvas_patch(existing_content, target_section, new_content):
    """Replace a section identified by target_section heading with new_content.

    Returns:
        (patched_content, was_replaced): was_replaced is False when the heading
        was not found and the content was silently appended instead.
    """
    import re
    lines = existing_content.split('\n')
    result = []
    target_level = None
    in_target = False
    replaced = False

    for line in lines:
        heading_match = re.match(r'^(#{1,6})\s+(.*)', line)
        if heading_match:
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()

            if heading_text == target_section.strip():
                # Start of target section
                target_level = level
                in_target = True
                replaced = True
                result.append(new_content)
                continue
            elif in_target and level <= target_level:
                # Reached next section of equal or higher level — stop replacing
                in_target = False

        if not in_target:
            result.append(line)

    # If target was never found, append and signal misfire to caller
    if not replaced:
        result.append('\n\n' + new_content)

def strip_images_from_messages(messages):
    """
    Deep copies messages while replacing base64-encoded image data with placeholders.

    This is necessary because image data (typically base64 encoded) can be very large
    and would unnecessarily bloat JSON files on disk and the database.
    """
    cleaned = []
    if not messages:
        return cleaned

    for msg in messages:
        msg_copy = dict(msg)
        content = msg_copy.get('content')

        # Handle content that is a list (multimodal messages with text and images)
        if isinstance(content, list):
            new_parts = []
            for part in content:
                if isinstance(part, dict) and part.get('type') == 'image_url':
                    # Replace actual image data with a placeholder to save space
                    new_parts.append({
                        'type': 'image_url',
                        'image_url': {'url': '[image_data_stripped]'}
                    })
                else:
                    new_parts.append(part)
            msg_copy['content'] = new_parts
        
        # Ensure tool_calls are handled if they are not already strings
        if 'tool_calls' in msg_copy and isinstance(msg_copy['tool_calls'], (list, dict)):
             import json
             msg_copy['tool_calls'] = json.dumps(msg_copy['tool_calls'])

        cleaned.append(msg_copy)

    return cleaned
