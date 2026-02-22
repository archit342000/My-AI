import requests
from bs4 import BeautifulSoup
import json
import time
import datetime
from urllib.parse import urlparse
from backend.config import (
    TAVILY_API_KEY, TAVILY_BASE_URL, SEARCH_DEPTH, MAX_SEARCH_RESULTS, 
    MIN_SEARCH_RESULTS, INCLUDE_ANSWER, INCLUDE_RAW_CONTENT, 
    RELEVANCE_THRESHOLD, SEARCH_CACHE_TTL,
    TIMEOUT_TAVILY_SEARCH, TIMEOUT_TAVILY_SEARCH_ASYNC,
    TIMEOUT_TAVILY_MAP, TIMEOUT_TAVILY_EXTRACT,
    TIMEOUT_LLM_ASYNC, TIMEOUT_WEB_SCRAPE
)
from backend.logger import log_tool_call, log_llm_call

_tavily_search_cache = {}

def get_current_time():
    """Returns the current local date and time as a formatted string."""
    now = datetime.datetime.now()
    return now.strftime("%A, %B %d, %Y %I:%M:%S %p")

def execute_tavily_search(query, topic="general", time_range=None, start_date=None, end_date=None, include_images=False, chat_id=None):
    if not TAVILY_API_KEY:
        return "Error: TAVILY_API_KEY is not configured.", "Tavily API key missing"

    url = f"{TAVILY_BASE_URL}/search"
    
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": SEARCH_DEPTH,
        "topic": topic if topic in ["general", "news", "finance"] else "general",
        "max_results": MAX_SEARCH_RESULTS,
        "include_answer": INCLUDE_ANSWER,
        "include_raw_content": INCLUDE_RAW_CONTENT,
        "include_images": include_images,
        "include_image_descriptions": include_images
    }

    if time_range and time_range in ["day", "week", "month", "year", "d", "w", "m", "y"]:
        payload["time_range"] = time_range
    if start_date: payload["start_date"] = start_date
    if end_date: payload["end_date"] = end_date

    start_time = time.time()
    try:
        import httpx
        with httpx.Client(timeout=TIMEOUT_TAVILY_SEARCH) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            
            duration = time.time() - start_time
            log_tool_call("tavily_search", payload, data, duration_s=duration, chat_id=chat_id)
            
            answer = data.get("answer", "")
            results = data.get("results", [])
            images = data.get("images", [])
            
            filtered_results = []
            for res in results:
                score = res.get("score", 0)
                if score >= RELEVANCE_THRESHOLD or len(filtered_results) < MIN_SEARCH_RESULTS:
                    filtered_results.append(res)
            
            output_parts = []
            if answer:
                output_parts.append(f"AI Summary from Tavily: {answer}\n")
                
            raw_contents_for_cache = []
            for res in filtered_results:
                title = res.get("title", "No Title")
                href = res.get("url", "")
                content = res.get("content", "")
                raw = res.get("raw_content", "No raw content available.")
                
                output_parts.append(f"Title: {title}\nLink: {href}\nContent Snippet: {content}")
                raw_contents_for_cache.append(f"Title: {title}\nLink: {href}\nRaw Content:\n{raw}")
                
            standard_output = "\n---\n".join(output_parts)
            raw_output = "\n================\n".join(raw_contents_for_cache)
            
            if not standard_output.strip():
                standard_output = "No basic results found."
            if not raw_output.strip():
                raw_output = "No raw content available."
                
            if chat_id:
                _tavily_search_cache[chat_id] = {
                    "raw_content": raw_output,
                    "timestamp": time.time()
                }
            
            if include_images and images:
                formatted_output = [{"type": "text", "text": standard_output}]
                for img in images:
                    img_url = img.get("url", "") if isinstance(img, dict) else img
                    img_desc = img.get("description", "") if isinstance(img, dict) else ""
                    
                    if img_url:
                        if img_desc:
                            formatted_output.append({"type": "text", "text": f"\nImage Description: {img_desc}"})
                        else:
                            formatted_output.append({"type": "text", "text": "\nImage:"})
                            
                        formatted_output.append({
                            "type": "image_url",
                            "image_url": {"url": img_url}
                        })
                return formatted_output, None
            
            return standard_output, None
    except Exception as e:
        log_tool_call("tavily_search_error", payload, {"error": str(e)}, duration_s=time.time()-start_time, chat_id=chat_id)
        return f"Tavily search failed: {str(e)}", str(e)
def audit_tavily_search(chat_id):
    if not chat_id or chat_id not in _tavily_search_cache:
        return "Error: No recent search found for this context to audit."
    
    cache_entry = _tavily_search_cache[chat_id]
    if time.time() - cache_entry["timestamp"] > SEARCH_CACHE_TTL:
        del _tavily_search_cache[chat_id]
        return "Error: The previous search data has expired from cache."
        
    return cache_entry["raw_content"]

import httpx

async def async_tavily_search(query, topic="general", time_range=None, start_date=None, end_date=None):
    url = f"{TAVILY_BASE_URL}/search"
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "basic",
        "topic": topic if topic in ["general", "news", "finance"] else "general",
        "max_results": 10,
        "include_answer": False,
        "include_raw_content": True,
        "include_images": True
    }
    if time_range and time_range in ["day", "week", "month", "year"]: payload["time_range"] = time_range
    if start_date: payload["start_date"] = start_date
    if end_date: payload["end_date"] = end_date

    start_time = time.time()
    async with httpx.AsyncClient(timeout=TIMEOUT_TAVILY_SEARCH_ASYNC) as client:
        try:
             resp = await client.post(url, json=payload)
             resp.raise_for_status()
             data = resp.json()
             log_tool_call("async_tavily_search", payload, data, duration_s=time.time()-start_time)
             return data.get("results", []), data.get("images", [])
        except Exception as e:
             log_tool_call("async_tavily_search_error", payload, {"error": str(e)}, duration_s=time.time()-start_time)
             return [], []

async def async_tavily_map(url_to_map, instruction):
    url = f"{TAVILY_BASE_URL}/map"
    payload = {
        "api_key": TAVILY_API_KEY,
        "url": url_to_map,
        "instructions": instruction,
        "max_depth": 3,
        "max_breadth": 10,
        "limit": 10,
        "allow_external": True,
        "exclude_paths": ["/login", "/signup", "/auth"],
        "exclude_domains": ["facebook.com", "twitter.com", "instagram.com"]
    }
    start_time = time.time()
    async with httpx.AsyncClient(timeout=TIMEOUT_TAVILY_MAP) as client:
        try:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            log_tool_call("async_tavily_map", payload, data, duration_s=time.time()-start_time)
            return data.get("results", [])
        except Exception as e:
            log_tool_call("async_tavily_map_error", payload, {"error": str(e)}, duration_s=time.time()-start_time)
            return []

async def async_tavily_extract(urls):
    if not urls: return []
    url = f"{TAVILY_BASE_URL}/extract"
    payload = {
        "api_key": TAVILY_API_KEY,
        "urls": urls,
        "extract_depth": "basic",
        "include_images": True,
        "format": "markdown"
    }
    start_time = time.time()
    async with httpx.AsyncClient(timeout=TIMEOUT_TAVILY_EXTRACT) as client:
        try:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            log_tool_call("async_tavily_extract", payload, data, duration_s=time.time()-start_time)
            return data.get("results", [])
        except Exception as e:
            log_tool_call("async_tavily_extract_error", payload, {"error": str(e)}, duration_s=time.time()-start_time)
            return []

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
        response = requests.post('https://urlhaus-api.abuse.ch/v1/url/', data=data, timeout=5)
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
from selectolax.lexbor import LexborHTMLParser
import markdownify
import re
from urllib.parse import urljoin
import threading

async def async_chat_completion(url, payload):
    start_time = time.time()
    model = payload.get("model", "unknown")
    
    # Use timeout=None. When executing multiple parallel URL ranking/selection 
    # requests, LMStudio (or any local Inference server) will queue them. 
    # A short timeout like 180s will cause the client to disconnect before 
    # the server even begins processing the later requests in the queue.
    async with httpx.AsyncClient(timeout=TIMEOUT_LLM_ASYNC) as client:
        try:
            resp = await client.post(f"{url}/v1/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()
            
            content = ""
            if "choices" in data and len(data["choices"]) > 0:
                content = data["choices"][0]["message"]["content"]
            
            log_llm_call(payload, content, model, duration_s=time.time()-start_time, call_type="async_blocking")
            return content
        except Exception as e:
            log_llm_call(payload, f"Error: {str(e)}", model, duration_s=time.time()-start_time, call_type="async_blocking_error")
            return ""

async def _async_visit_page(url, max_chars):
    try:
        headers = {'User-Agent': random.choice(USER_AGENTS)}
        
        async with httpx.AsyncClient(headers=headers, timeout=TIMEOUT_WEB_SCRAPE, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            # Handle PDF
            content_type = response.headers.get('Content-Type', '').lower()
            if 'application/pdf' in content_type or url.lower().endswith('.pdf'):
                try:
                    pdf_file = io.BytesIO(response.content)
                    reader = pypdf.PdfReader(pdf_file)
                    text = ""
                    for page in reader.pages:
                        page_text = page.extract_text() or ""
                        # Remove isolated page numbers
                        page_text = re.sub(r'(?m)^\s*\d+\s*$', '', page_text)
                        text += page_text + "\n"
                        
                    if not text.strip():
                        return "PDF content extracted but appears empty (possibly image-only)."
                        
                    # Clean PDF text artifacts
                    text = text.replace('\r', '\n').replace('\xa0', ' ')
                    
                    # Collapse multiple horizontal spaces and tabs into a single space
                    text = re.sub(r'[ \t]+', ' ', text)
                    
                    # Collapse excessive blank vertical lines into double newlines for paragraph spacing
                    text = re.sub(r'\n{3,}', '\n\n', text)
                    
                    text = text.strip()
                    
                    return f"[PDF Document]\n\n{text[:max_chars]}"
                except Exception as e:
                    return f"Error parsing PDF: {str(e)}"
                    
            # Handle HTML via selectolax Lexbor parser
            html_content = response.text
            parser = LexborHTMLParser(html_content)
            
            # Define noise selectors for aggressive pruning
            noise_selectors = [
                # Standard boilerplate
                "script", "style", "noscript", "svg", "nav", "footer", "header", "aside", "meta",
                # Ad networks & trackers
                "iframe", "ins.adsbygoogle", ".ad", ".advertisement", ".banner",
                "[class*='sponsor']", "[id*='taboola']", "[id*='outbrain']"
            ]
            
            # Aggressively strip known noise
            for selector in noise_selectors:
                for node in parser.css(selector):
                    node.decompose()
            
            # Main Content Isolation
            content_node = None
            for wrapper in ["article", "main", ".main-content", ".post-body"]:
                matches = parser.css(wrapper)
                if matches:
                    content_node = matches[0]
                    break
            
            if not content_node:
                content_node = parser.body
                
            if not content_node:
                content_node = parser.root

            if not content_node:
                return "Error: Could not find any valid content block on the page."
            
            clean_html = content_node.html
            
            # Semantic Markdown Conversion
            md_text = markdownify.markdownify(
                clean_html,
                heading_style="ATX",
                strip=['img', 'audio', 'video'],
                keep_inline_images_in=['a']
            )
            
            # Post-Processing
            def make_absolute(match):
                anchor_text = match.group(1)
                href = match.group(2)
                abs_url = urljoin(url, href)
                return f"[{anchor_text}]({abs_url})"
                
            md_text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', make_absolute, md_text)
            
            # Filter empty links
            md_text = re.sub(r'\[[^\]]*\]\(\s*\)', '', md_text)
            
            # Normalize spaces (e.g., non-breaking spaces)
            md_text = md_text.replace('\xa0', ' ').replace('\u200b', '')
            
            # Remove trailing whitespace from individual lines
            md_text = re.sub(r'[ \t]+$', '', md_text, flags=re.MULTILINE)
            
            # Trim excessive horizontal rules/decorations (limit to max 3 dashes/stars/equals)
            md_text = re.sub(r'([*_=]){4,}', r'\1\1\1', md_text)
            
            # Normalize whitespace: collapse 3+ newlines to 2
            md_text = re.sub(r'\n{3,}', '\n\n', md_text)
            
            text = md_text.strip()
            return text[:max_chars]
            
    except Exception as e:
        return f"Error visiting page: {str(e)}"

def visit_page(url, max_chars=8000):
    def run_coro(coro):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
            
        if loop and loop.is_running():
            result = [None]
            ex = [None]
            def runner():
                try:
                    result[0] = asyncio.run(coro)
                except Exception as e:
                    ex[0] = e
            t = threading.Thread(target=runner)
            t.start()
            t.join()
            if ex[0]: raise ex[0]
            return result[0]
        else:
            return asyncio.run(coro)
            
    return run_coro(_async_visit_page(url, max_chars))

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
    
    Handles:
    - CoT reasoning before the XML (text or <think> blocks)
    - Markdown code blocks wrapping the XML (```xml ... ```)
    - Whitespace and formatting variations
    
    Returns (clean_xml_string, error_message). One will always be None.
    """
    import re
    
    if not content or not content.strip():
        return None, "Empty content received."
    
    raw = content
    
    # 1. Strip CoT reasoning
    # Handle implicit reasoning start (missing <think> tag) by stripping everything before the last </think>
    if '</think>' in raw:
        raw = raw.split('</think>')[-1].strip()
    
    # Also strip standard explicit <think> blocks if any remain
    raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
    
    # 2. Strip markdown code fences (```xml ... ``` or ``` ... ```)
    raw = re.sub(r'```(?:xml)?\s*\n?', '', raw).strip()
    
    # 3. Locate the XML block
    start_tag = "<research_plan>"
    end_tag = "</research_plan>"
    
    start_index = raw.find(start_tag)
    if start_index == -1:
        # Check if it's in the original content (in case stripping removed it accidentally)
        start_index_orig = content.find(start_tag)
        if start_index_orig == -1:
            return None, "Missing <research_plan> opening tag."
        # Use original content if stripping broke it
        raw = content
        start_index = start_index_orig
    
    end_index = raw.find(end_tag, start_index)
    if end_index == -1:
        return None, "Missing </research_plan> closing tag (XML may be truncated)."
    
    # Extract just the XML block
    xml_candidate = raw[start_index : end_index + len(end_tag)]
    
    # 4. Parse and validate structure using html.parser (always available, no lxml needed)
    try:
        soup = BeautifulSoup(xml_candidate, 'html.parser')
    except Exception as e:
        return None, f"XML parsing failed: {str(e)}"
    
    plan_tag = soup.find('research_plan')
    if not plan_tag:
        return None, "Failed to parse <research_plan> structure."
    
    # 5. Validate required elements
    title_tag = plan_tag.find('title')
    if not title_tag or not title_tag.get_text(strip=True):
        return None, "Plan is missing a valid <title>."
    
    steps = plan_tag.find_all('step')
    if not steps:
        return None, "Plan must have at least one <step>."
    
    # Validate steps have actual content
    empty_steps = [i+1 for i, s in enumerate(steps) if not s.get_text(strip=True)]
    if empty_steps:
        return None, f"Step(s) {empty_steps} are empty."
    
    # 6. Return the clean extracted XML (preserving original formatting)
    return xml_candidate, None
