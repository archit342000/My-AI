import requests
import os
from bs4 import BeautifulSoup
import json
import time
import datetime
from urllib.parse import urlparse
from backend import config
from backend.logger import log_tool_call, log_llm_call, log_event

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

async def async_chat_completion(url, payload):
    start_time = time.time()
    model = payload.get("model", "unknown")
    
    # Use timeout=None. When executing multiple parallel URL ranking/selection 
    # requests, a local inference server will queue them. 
    # A short timeout like 180s will cause the client to disconnect before 
    # the server even begins processing the later requests in the queue.
    base_url = url.rstrip("/")
    if not base_url.endswith("/v1"):
        endpoint = f"{base_url}/v1/chat/completions"
    else:
        endpoint = f"{base_url}/chat/completions"
        
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
                
            # AGENTS.md compliance: always prioritize gathering all emitted signals.
            # However, for structured output (json_schema or json_object), 
            # Local AI backend quirks mean the JSON is often in reasoning_content.
            # We don't wrap in <think> tags if it's the primary payload.
            
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
                
            log_llm_call(payload, final_output, model, duration_s=time.time()-start_time, call_type="async_blocking")
            return final_output
        except Exception as e:
            log_llm_call(payload, f"Error: {str(e)}", model, duration_s=time.time()-start_time, call_type="async_blocking_error")
            return ""

def estimate_tokens(msgs):
    total = 0
    for m in msgs:
        content = m.get('content', '')
        if isinstance(content, str):
            total += len(content) // 4
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get('type') == 'text':
                    total += len(part.get('text', '')) // 4
        total += 4  # overhead per message (role, formatting tokens)
    return total

def create_chunk(model, content=None, reasoning=None, finish_reason=None):
    delta = {}
    if content: delta["content"] = content
    if reasoning: delta["reasoning_content"] = reasoning
    return json.dumps({
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}]
    })

def validate_research_plan(content):
    """
    Validates and extracts clean Research Plan XML from potentially noisy model output.
    
    Expected format (section-based):
    <research_plan>
      <title>...</title>
      <section>
        <heading>...</heading>
        <description>...</description>
        <query>...</query>
        <query topic="news" time_range="week">...</query>
      </section>
      ...
    </research_plan>
    
    Returns (clean_xml_string, error_message). One will always be None.
    """
    import re
    
    if not content or not content.strip():
        return None, "Empty content received."
    
    raw = content
    
    # 1. Strip CoT reasoning
    if '</think>' in raw:
        raw = raw.split('</think>')[-1].strip()
    raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
    
    # 2. Strip markdown code fences
    raw = re.sub(r'```(?:xml)?\s*\n?', '', raw).strip()
    
    # 3. Fix malformed <query ... </query> tags where the opening tag is missing the closing '>'
    # This happens when the AI tries to put search text into the opening tag like an attribute.
    raw = re.sub(r'<query([^>]*?)</query>', r'<query>\1</query>', raw)
    
    # 4. Locate the XML block
    start_tag = "<research_plan>"
    end_tag = "</research_plan>"
    
    start_index = raw.find(start_tag)
    if start_index == -1:
        start_index_orig = content.find(start_tag)
        if start_index_orig == -1:
            return None, "Missing <research_plan> opening tag."
        raw = content
        start_index = start_index_orig
    
    end_index = raw.find(end_tag, start_index)
    if end_index == -1:
        return None, "Missing </research_plan> closing tag (XML may be truncated)."
    
    xml_candidate = raw[start_index : end_index + len(end_tag)]
    
    # 4. Parse and validate structure
    try:
        soup = BeautifulSoup(xml_candidate, 'html.parser')
    except Exception as e:
        return None, f"XML parsing failed: {str(e)}"
    
    plan_tag = soup.find('research_plan')
    if not plan_tag:
        return None, "Failed to parse <research_plan> structure."
    
    # 5. Validate title
    title_tag = plan_tag.find('title')
    if not title_tag or not title_tag.get_text(strip=True):
        return None, "Plan is missing a valid <title>."
    
    # 6. Validate sections
    sections = plan_tag.find_all('section')
    if not sections:
        return None, "Plan must have at least one <section>."
    
    total_queries = 0
    max_per_section = config.RESEARCH_MAX_QUERIES_PER_SECTION
    max_total = config.RESEARCH_MAX_TOTAL_QUERIES
    
    for i, sec in enumerate(sections):
        heading = sec.find('heading')
        if not heading or not heading.get_text(strip=True):
            return None, f"Section {i+1} is missing a valid <heading>."
        
        desc = sec.find('description')
        if not desc or not desc.get_text(strip=True):
            return None, f"Section {i+1} ('{heading.get_text(strip=True)}') is missing a <description>."
        
        queries = sec.find_all('query')
        if not queries:
            return None, f"Section {i+1} ('{heading.get_text(strip=True)}') has no <query> elements."
        
        if len(queries) > max_per_section:
            return None, f"Section {i+1} has {len(queries)} queries (max {max_per_section})."
        
        for j, q in enumerate(queries):
            if not q.get_text(strip=True):
                return None, f"Section {i+1}, query {j+1} is empty."
        
        total_queries += len(queries)
    
    if total_queries > max_total:
        return None, f"Plan has {total_queries} total queries (max {max_total})."
    
    # 7. Return the clean extracted XML
    return xml_candidate, None
