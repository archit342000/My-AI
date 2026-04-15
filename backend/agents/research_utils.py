import json
import asyncio
import datetime
import re
import urllib.parse
import html
import time
import httpx
from backend.logger import log_event, log_tool_call
from backend import config
from backend.prompts import RESEARCH_VISION_PROMPT
from backend.llm import stream_chat_completion
from backend.mcp_client import tavily_client, playwright_client

def _is_transient_error(e):
    """
    Differentiates between transient server/network errors and fatal code logic errors.
    Returns True if we should allow the user to retry.
    """
    # Network/Inference errors are transient
    if isinstance(e, (httpx.NetworkError, httpx.TimeoutException, asyncio.TimeoutError)):
        return True
    
    # JSON or encoding errors from LLM streams are likely transient model failures
    if isinstance(e, (json.JSONDecodeError, UnicodeDecodeError)):
        return True

    # These indicate code bugs/logic errors and should NOT be retried
    if isinstance(e, (KeyError, AttributeError, TypeError, NameError, IndexError, ValueError)):
        return False
        
    # Default to retryable for unknown to be safe
    return True

def _get_sampling_params(attempt=1):
    """
    Returns the sampling parameters for research LLM calls.
    Attempt 1 uses the 'Heavy Reasoning' optimized parameters from config.
    Attempt 2+ or fallbacks use a conservative low-temperature setting with DRY boost.
    """
    if attempt == 1:
        return {
            "temperature": config.RESEARCH_SAMPLING_TEMPERATURE,
            "min_p": config.RESEARCH_SAMPLING_MIN_P,
            "dry_multiplier": config.RESEARCH_SAMPLING_DRY_MULTIPLIER,
            "dry_base": config.RESEARCH_SAMPLING_DRY_BASE,
            "dry_allowed_length": config.RESEARCH_SAMPLING_DRY_ALLOWED_LENGTH,
            "xtc_probability": config.RESEARCH_SAMPLING_XTC_PROBABILITY,
            "repeat_penalty": config.RESEARCH_SAMPLING_REPEAT_PENALTY
        }
    else:
        # Boost DRY parameters on retries to break repetition loops
        multiplier = config.RESEARCH_SAMPLING_DRY_MULTIPLIER + (config.RESEARCH_SAMPLING_DRY_RETRIAL_BOOST * (attempt - 1))
        return {
            "temperature": config.RESEARCH_TEMPERATURE_RETRY_FALLBACK,
            "dry_multiplier": min(multiplier, 2.0),
            "dry_base": config.RESEARCH_SAMPLING_DRY_BASE,
            "dry_allowed_length": config.RESEARCH_SAMPLING_DRY_ALLOWED_LENGTH,
            "repeat_penalty": 1.15
        }

def _extract_json_from_text(text):
    """
    Robustly extracts the first JSON object from a string.
    Useful for background tasks (like ranking) where the model might
    prefix output with a <think> block or other commentary.
    """
    if not text:
        return None
    
    # CLAUDE.md Compliance: Extract JSON ONLY from the content portion.
    # We explicitly strip <think> blocks to satisfy the "never use reasoning for logic" rule.
    # Replace regex with simpler splitting to prevent backtracking hangs on huge strings
    clean_text = text
    if "<think>" in clean_text:
        parts = clean_text.split("<think>")
        processed_parts = [parts[0]]
        for part in parts[1:]:
            if "</think>" in part:
                processed_parts.append(part.split("</think>")[-1])
        clean_text = "".join(processed_parts).strip()
    elif "</think>" in clean_text:
        clean_text = clean_text.split("</think>")[-1].strip()

    # First, try to parse the whole thing (fastest path)
    try:
        return json.loads(clean_text.strip())
    except json.JSONDecodeError:
        pass
    
    # Try to find a JSON object or array in the cleaned text
    target = clean_text
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        start = target.find(start_char)
        if start == -1:
            continue
        depth = 0
        for i in range(start, len(target)):
            if target[i] == start_char: 
                depth += 1
            elif target[i] == end_char:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(target[start:i+1])
                    except:
                        break
    return None

async def _execute_mcp_tool(client, tool_name, arguments, chat_id=None):
    """
    Execute an MCP tool and log the call to the system-wide tool logs.
    Ensures that ALL requests, even failed ones, are recorded.
    """
    start_time = time.time()
    try:
        result = await client.execute_tool(tool_name, arguments)
        duration = time.time() - start_time
        
        # Extract text content for log index
        log_content = ""
        if hasattr(result, 'content') and result.content:
            log_content = result.content[0].text
        else:
            log_content = str(result)
            
        log_tool_call(tool_name, arguments, log_content, duration_s=duration, chat_id=chat_id)
        return result
    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"ERROR: MCP Tool '{tool_name}' failed: {str(e)}"
        log_tool_call(tool_name, arguments, error_msg, duration_s=duration, chat_id=chat_id)
        log_event("tool_execution_error", {"tool": tool_name, "error": str(e), "chat_id": chat_id})
        raise

async def _stream_research_call(api_url, payload, display_model, activity_type, enable_thinking,
                                 thought_limit=None, content_threshold=None, 
                                 step_id=None, is_background=True, api_key=None,
                                 chat_id=None):
    """
    Unified streaming wrapper for all research LLM calls.
    Implements active meander detection and CLAUDE.md compliance.
    
    Yields UI activity chunks via {"type": "activity", "data": str}.
    Returns the final accumulated (and potentially tagged) string via {"type": "result", "data": str}.
    """
    start_time = time.time()
    full_content = ""
    full_reasoning = ""
    reasoning_token_count = 0
    content_token_count = 0
    is_json_mode = "response_format" in payload
    
    # Ensure stream is enabled
    payload = dict(payload)
    payload["stream"] = True
    if api_key:
        payload["api_key"] = api_key

    # Llama.cpp specific: Handle enable_thinking toggle for fallbacks
    if not enable_thinking:
        payload = dict(payload)
        payload["chat_template_kwargs"] = payload.get("chat_template_kwargs", {})
        payload["chat_template_kwargs"]["enable_thinking"] = False

    was_meandered = False
    
    try:
        async for line in stream_chat_completion(api_url, payload, chat_id=chat_id):
            if not line.startswith('data: '): continue
            if line == 'data: [DONE]': break
            
            try:
                data_json = json.loads(line[6:])
                choices = data_json.get('choices', [])
                if not choices: continue
                
                delta = choices[0].get('delta', {})
                content = delta.get('content', '')
                reasoning = delta.get('reasoning_content', '') or delta.get('reasoning', '')
                
                if content:
                    full_content += content
                    content_token_count += 1
                    
                    if is_background:
                        if content_token_count % (config.RESEARCH_UI_STREAM_UPDATE_INTERVAL * 2) == 0:
                            yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, activity_type, {'message': 'Extracting and validating facts...', 'state': 'thinking', 'icon': '📂', 'step_id': step_id})}\n\n"}
                        
                        if content_token_count > 50:
                            tail = full_content[-300:]
                            if len(tail) > 100:
                                chunk_size = 40
                                counts = {}
                                for i in range(len(tail) - chunk_size):
                                    c = tail[i:i+chunk_size]
                                    counts[c] = counts.get(c, 0) + 1
                                    if counts[c] >= 4:
                                        was_meandered = True
                                        yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, activity_type, {'message': 'Repetition loop detected. Killing stream.', 'state': 'warning', 'step_id': step_id})}\n\n"}
                                        break
                            if was_meandered: break
                
                if reasoning:
                    full_reasoning += reasoning
                    reasoning_token_count += 1
                    
                    if is_background and reasoning_token_count % config.RESEARCH_UI_STREAM_UPDATE_INTERVAL == 0:
                        snippet = _clean_thinking_snippet(full_reasoning)
                        yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, activity_type, {'message': f'...{snippet}', 'state': 'thinking', 'step_id': step_id})}\n\n"}
                
                # Active Meander Detection (Token-Based)
                if thought_limit and content_threshold is not None:
                    if reasoning_token_count > thought_limit and content_token_count < content_threshold:
                        was_meandered = True
                        if is_background:
                            yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, activity_type, {'message': 'Meander limit reached. Truncating stream.', 'state': 'warning', 'step_id': step_id})}\n\n"}
                        break # Stop the LLM stream physically
            except:
                continue
                
        # Finalize output based on CLAUDE.md
        final_output = ""
        if full_reasoning:
            final_output += f"<think>\n{full_reasoning}\n</think>\n"
        final_output += (full_content or "")
            
        yield {"type": "result", "data": final_output, "content": full_content, "reasoning": full_reasoning, "meandered": was_meandered}

    except Exception as e:
        duration = time.time() - start_time
        log_event("research_stream_call_error", {"error": str(e), "chat_id": chat_id, "duration": duration})
        
        yield {"type": "result", "data": "", "meandered": False}

async def _fetch_and_encode_image(url):
    try:
        mcp_res = await _execute_mcp_tool(playwright_client, "fetch_and_encode_image_tool", {"url": url})
        res_json = json.loads(mcp_res.content[0].text)
        if "error" in res_json:
            return None
        return res_json.get("image")
    except Exception:
        return None

def _create_activity_chunk(model, activity_type, data):
    """Creates a special SSE chunk carrying structured activity data for the frontend."""
    return json.dumps({
        "object": "chat.completion.chunk",
        "model": model,
        "choices": [{
            "index": 0,
            "delta": {
                "reasoning_content": json.dumps({
                    "__research_activity__": True,
                    "type": activity_type,
                    "data": data
                })
            },
            "finish_reason": None
        }]
    })

def _clean_thinking_snippet(raw_text):
    """Cleans up raw model reasoning text for human-friendly UI display.
    Strips XML/JSON structural artifacts, collapses whitespace, and 
    extracts only readable natural language fragments."""
    text = raw_text
    # Strip XML tags (e.g. <research_plan>, <step>, <goal>, <query>, etc.)
    text = re.sub(r'<[^>]+>', ' ', text)
    # Strip JSON-style structural characters
    text = re.sub(r'[{}\[\]"]', ' ', text)
    # Strip markdown formatting artifacts
    text = re.sub(r'[*#`_~]', '', text)
    # Collapse multiple spaces and newlines into single spaces
    text = re.sub(r'\s+', ' ', text).strip()
    # If result is too short after cleaning, return a generic message
    if len(text) < config.RESEARCH_UI_THOUGHT_MIN_LENGTH:
        return "Analyzing and structuring research approach..."
    # Take last X chars for a readable trailing snippet
    if len(text) > config.RESEARCH_UI_THOUGHT_SNIPPET_LENGTH:
        text = text[-config.RESEARCH_UI_THOUGHT_SNIPPET_LENGTH:]
        # Try to start at a word boundary
        first_space = text.find(' ')
        if first_space != -1 and first_space < 30:
            text = text[first_space + 1:]
    return text

def _strip_thinking(text):
    """Strip <think>...</think> blocks from text. Handles unclosed tags."""
    if not text:
        return ""
    result = text
    # Strip closed <think>...</think> blocks
    result = re.sub(r'<think>.*?</think>', '', result, flags=re.DOTALL).strip()
    # Handle unclosed <think> (strip from <think> to end)
    if '<think>' in result:
        result = result.split('<think>')[0].strip()
    # Handle orphaned </think> (strip everything before it)
    if '</think>' in result:
        result = result.split('</think>')[-1].strip()
    return result

def _select_top_urls(results, n=None):
    """Deterministic URL selection: sort by Tavily score, pick top N with domain diversity.
    No LLM call needed — replaces the old AI-based URL ranking."""
    if not results:
        return []
    
    if n is None:
        n = config.RESEARCH_SELECT_TOP_URLS_COUNT
    
    # Sort by Tavily score descending
    sorted_results = sorted(results, key=lambda x: x.get('score', 0), reverse=True)
    
    selected = []
    domains_seen = set()
    
    # First pass: pick unique domains (highest scored first)
    for r in sorted_results:
        if len(selected) >= n:
            break
        domain = urllib.parse.urlparse(r.get('url', '')).netloc.lower()
        if domain not in domains_seen:
            selected.append(r)
            domains_seen.add(domain)
    
    # Second pass: if we still need more, fill with highest-scored remaining regardless of domain
    if len(selected) < n:
        for r in sorted_results:
            if len(selected) >= n:
                break
            if r not in selected:
                selected.append(r)
    
    return selected

async def _process_images_in_content(content, url, vision_model, api_url, vlm_lock, enable_thinking, display_model=None, step_id=None, api_key=None, chat_id=None, vision_enabled=True):
    """Extract and describe images found in markdown content using a vision model.
    Yields activity packets and finally the modified content string."""
    # Skip vision processing if not enabled
    if not vision_enabled or not vision_model or not content:
        yield {"type": "result", "data": content}
        return
    
    # Improved extraction: find all potential img tags and markdown image markers
    md_matches = re.findall(r'!\[([^\]]*)\]\((https?://[^\)]+)\)', content)
    
    # Robust HTML image extraction: find raw tags first, then pick attributes (order-agnostic)
    raw_html_tags = re.findall(r'<img [^>]*src=["\'](https?://[^"\']+)["\'][^>]*>', content)
    
    all_candidates = []
    # Add markdown candidates
    for alt, img_url in md_matches:
        all_candidates.append({"url": img_url, "alt": alt})
    
    # Add HTML candidates (try to find matching alts if possible, otherwise generic)
    for img_url in raw_html_tags:
        # Check if we already have this URL from markdown
        if not any(c["url"] == img_url for c in all_candidates):
            # Attempt to find alt for this specific tag in the original content (simple heuristics)
            alt_match = re.search(f'<img [^>]*alt=["\']([^"\']+)["\'][^>]*src=["\']{re.escape(img_url)}["\']', content)
            if not alt_match:
                alt_match = re.search(f'<img [^>]*src=["\']{re.escape(img_url)}["\'][^>]*alt=["\']([^"\']+)["\']', content)
            alt = alt_match.group(1) if alt_match else ""
            all_candidates.append({"url": img_url, "alt": alt})

    descriptions = []
    success_count = 0
    quota = config.RESEARCH_MAX_IMAGES_PER_PAGE

    for candidate in all_candidates:
        if success_count >= quota:
            break
            
        img_url = html.unescape(candidate["url"]).split('#')[0].strip()
        alt = candidate["alt"]
        
        # Extension and safety check
        parsed_path = urllib.parse.urlparse(img_url).path.lower()
        if not (parsed_path.endswith(('.png', '.jpg', '.jpeg', '.webp')) and 'icon' not in img_url.lower() and 'logo' not in img_url.lower()):
            continue

        try:
            yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, 'vision', {'message': f'Analyzing embedded image ({success_count+1}/{quota})...', 'state': 'thinking', 'step_id': step_id})}\n\n"}
            
            base64_img = await _fetch_and_encode_image(img_url)
            if not base64_img:
                # Silently skip blocked/broken images - they don't count towards the quota
                continue
            
            today_date = datetime.date.today().strftime("%A, %B %d, %Y")
            payload = {
                "model": vision_model,
                "messages": [
                    {"role": "system", "content": RESEARCH_VISION_PROMPT.format(url=url, alt=alt or "Untitled", today_date=today_date)},
                    {"role": "user", "content": [{"type": "image_url", "image_url": {"url": base64_img}}]}
                ],
                "max_tokens": config.RESEARCH_MAX_TOKENS_VISION,
                **_get_sampling_params(attempt=1),
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "vision_analysis",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "caption": {"type": "string"},
                                "detailed_description": {"type": "string"}
                            },
                            "required": ["caption", "detailed_description"],
                            "additionalProperties": False
                        }
                    }
                }
            }
            
            max_retries = config.RESEARCH_VISION_RETRIES
            img_desc = ""
            current_success = False
            
            for attempt in range(max_retries):
                try:
                    if vlm_lock:
                        async with vlm_lock:
                            gen = _stream_research_call(
                                api_url, payload, None, "vision", enable_thinking,
                                thought_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_VISION_TOKENS,
                                content_threshold=config.RESEARCH_MEANDER_CONTENT_THRESHOLD_TOKENS,
                                is_background=False, api_key=api_key
                            )
                            async for packet in gen:
                                if packet["type"] == "result":
                                    img_desc = packet["data"]
                    else:
                        gen = _stream_research_call(
                            api_url, payload, None, "vision", enable_thinking,
                            thought_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_VISION_TOKENS,
                            content_threshold=config.RESEARCH_MEANDER_CONTENT_THRESHOLD_TOKENS,
                            is_background=False, api_key=api_key
                        )
                        async for packet in gen:
                            if packet["type"] == "result":
                                img_desc = packet["data"]
                    
                    if img_desc and len(img_desc) > config.RESEARCH_VISION_MIN_RESPONSE_LENGTH:
                        parsed = _extract_json_from_text(img_desc)
                        if parsed and isinstance(parsed, dict):
                            ai_caption = parsed.get("caption", "").strip() or (alt or 'Extracted Visual Data')
                            ai_detail = parsed.get("detailed_description", "").strip() or img_desc.strip()
                        else:
                            ai_caption = (alt or 'Extracted Visual Data')
                            ai_detail = img_desc.strip()
                        
                        triplet_block = (
                            f"\n\n### [IMAGE DETECTED]\n"
                            f"**Original Title**: {alt or 'Untitled'}\n"
                            f"**AI Generated Caption**: {ai_caption}\n"
                            f"**URL**: {img_url}\n"
                            f"**Vision Model Detailed Description**: {ai_detail}\n"
                        )
                        descriptions.append(triplet_block)
                        current_success = True
                    break
                except Exception:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
            
            if current_success:
                success_count += 1
                
        except Exception:
            pass
    
    if descriptions:
        content += "\n\n" + "\n".join(descriptions)
    
    yield {"type": "result", "data": content}

async def _extract_content_for_url(url, search_depth_mode, vision_model, api_url, vlm_lock, enable_thinking, display_model=None, step_id=None, raw_content_from_search=None, api_key=None, chat_id=None, vision_enabled=True):
    """Extract content from a single URL based on the search depth mode."""
    if search_depth_mode == 'regular':
        if raw_content_from_search and len(raw_content_from_search.strip()) > config.RESEARCH_EXTRACT_MIN_RAW_CONTENT:
            content = raw_content_from_search
            if vision_model and vision_enabled:
                async for packet in _process_images_in_content(content, url, vision_model, api_url, vlm_lock, enable_thinking, display_model, step_id, api_key=api_key, vision_enabled=vision_enabled):
                    if packet["type"] == "activity":
                        yield packet
                    else:
                        content = packet["data"]
            yield {"type": "result", "data": (url, content)}
            return
        yield {"type": "result", "data": (url, None)}
        return

    content = None
    try:
        mcp_res = await _execute_mcp_tool(playwright_client, "visit_page_tool", {"url": url, "max_chars": 40000, "detail_level": "deep"}, chat_id=chat_id)
        extracted = mcp_res.content[0].text
        if extracted and "Error:" not in extracted and len(extracted.strip()) > (config.RESEARCH_CONTENT_MIN_LENGTH_DEEP if search_depth_mode == 'deep' else config.RESEARCH_CONTENT_MIN_LENGTH_REGULAR):
            if vision_model and vision_enabled:
                async for packet in _process_images_in_content(extracted, url, vision_model, api_url, vlm_lock, enable_thinking, display_model, step_id, api_key=api_key, vision_enabled=vision_enabled):
                    if packet["type"] == "activity":
                        yield packet
                    else:
                        extracted = packet["data"]
            yield {"type": "result", "data": (url, extracted)}
            return
    except Exception:
        pass
    
    yield {"type": "result", "data": (url, None)}

async def _process_tavily_search_images(images, section_index, vision_model, api_url, vlm_lock, enable_thinking, display_model=None, api_key=None, chat_id=None, vision_enabled=True):
    """Process images from Tavily search results using vision model."""
    # Skip vision processing if not enabled
    if not vision_enabled or not vision_model or not images:
        yield {"type": "result", "data": []}
        return
    
    candidates = []
    for img_url in images:
        if isinstance(img_url, dict):
            img_url = img_url.get("url", "")
        if isinstance(img_url, str):
            img_url = html.unescape(img_url).split('#')[0].strip()
            parsed_path = urllib.parse.urlparse(img_url).path.lower()
            if parsed_path.endswith(('.png', '.jpg', '.jpeg', '.webp')) and 'icon' not in img_url.lower() and 'logo' not in img_url.lower():
                candidates.append(img_url)
    
    results = []
    success_count = 0
    quota = config.RESEARCH_MAX_SEARCH_IMAGES

    for img_url in candidates:
        if success_count >= quota:
            break
            
        try:
            yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, 'vision', {'message': f'Analyzing search evidence ({success_count+1}/{quota})...', 'state': 'thinking', 'step_id': section_index})}\n\n"}
            
            base64_img = await _fetch_and_encode_image(img_url)
            if not base64_img:
                continue
            
            today_date = datetime.date.today().strftime("%A, %B %d, %Y")
            payload = {
                "model": vision_model,
                "messages": [
                    {"role": "system", "content": RESEARCH_VISION_PROMPT.format(url="Search Engine Results", alt="Contextual search image", today_date=today_date)},
                    {"role": "user", "content": [{"type": "image_url", "image_url": {"url": base64_img}}]}
                ],
                "max_tokens": config.RESEARCH_MAX_TOKENS_VISION,
                **_get_sampling_params(attempt=1),
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "vision_analysis",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "caption": {"type": "string"},
                                "detailed_description": {"type": "string"}
                            },
                            "required": ["caption", "detailed_description"],
                            "additionalProperties": False
                        }
                    }
                }
            }
            
            img_desc = ""
            current_success = False
            
            for attempt in range(config.RESEARCH_VISION_RETRIES):
                try:
                    if vlm_lock:
                        async with vlm_lock:
                            gen = _stream_research_call(
                            api_url, payload, None, "vision", enable_thinking,
                            thought_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_VISION_TOKENS,
                            content_threshold=config.RESEARCH_MEANDER_CONTENT_THRESHOLD_TOKENS,
                            is_background=False, api_key=api_key
                        )
                            async for packet in gen:
                                if packet["type"] == "result":
                                    img_desc = packet["data"]
                    else:
                        gen = _stream_research_call(
                            api_url, payload, None, "vision", enable_thinking,
                            thought_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_VISION_TOKENS,
                            content_threshold=config.RESEARCH_MEANDER_CONTENT_THRESHOLD_TOKENS,
                            is_background=False, api_key=api_key
                        )
                        async for packet in gen:
                            if packet["type"] == "result":
                                img_desc = packet["data"]
                    
                    if img_desc and len(img_desc) > config.RESEARCH_VISION_MIN_RESPONSE_LENGTH:
                        parsed = _extract_json_from_text(img_desc)
                        if parsed and isinstance(parsed, dict):
                            ai_caption = parsed.get("caption", "").strip() or 'Contextual search image'
                            ai_detail = parsed.get("detailed_description", "").strip() or img_desc.strip()
                        else:
                            ai_caption = 'Contextual search image'
                            ai_detail = img_desc.strip()
                        
                        triplet_block = (
                            f"\n\n### [IMAGE DETECTED]\n"
                            f"**Original Title**: Search Result Embedded Image\n"
                            f"**AI Generated Caption**: {ai_caption}\n"
                            f"**URL**: {img_url}\n"
                            f"**Vision Model Detailed Description**: {ai_detail}\n"
                        )
                        results.append((triplet_block, img_url, section_index))
                        current_success = True
                    break
                except Exception:
                    if attempt < config.RESEARCH_VISION_RETRIES - 1:
                        await asyncio.sleep(2 ** attempt)
            
            if current_success:
                success_count += 1
        except Exception:
            pass
    
    yield {"type": "result", "data": results}


def _preprocess_citations(text):
    """Expands ranges [1-3] and splits list-style citations [1, 2] into individual markers."""
    # Clean up weird AI markdown formats for citations
    # Strip markdown link syntax: [1](#1) -> [1]
    text = re.sub(r'\[(\d+)\]\([^)]+\)', r'[\1]', text)
    
    # Handle list-style [1, 2] -> [1] [2] with whitespace tolerance
    def split_commas(match):
        nums = [n.strip() for n in match.group(1).split(',')]
        return ' '.join(f'[{n}]' for n in nums if n.isdigit())
    text = re.sub(r'\[\s*(\d+(?:\s*,\s*\d+)+)\s*\]', split_commas, text)
    
    # Handle range-style [1-3] -> [1] [2] [3] with whitespace tolerance
    def split_ranges(match):
        start = int(match.group(1))
        end = int(match.group(2))
        if start < end and end - start <= 20: 
            return ' '.join(f'[{i}]' for i in range(start, end + 1))
        return match.group(0)
    text = re.sub(r'\[\s*(\d+)\s*-\s*(\d+)\s*\]', split_ranges, text)
    
    # Strip nested brackets: [[1]] -> [1]
    # Fixed the double backslash bug from original implementation
    text = re.sub(r'\[\s*(\[\d+\](?:[^\[\]]*\[\d+\])*)\s*\]', r'\1', text)
    
    return text


def _normalize_citations(report_text, source_registry):
    """Re-number all [N] citations sequentially from [1] and build a references list.
    Uses a two-phase placeholder approach to avoid collision between old and new IDs."""
    
    report_text = _preprocess_citations(report_text)
    
    # Find all unique citation IDs present in text (with whitespace tolerance)
    all_matches = set(int(m) for m in re.findall(r'\[\s*(\d+)\s*\]', report_text))
    valid_ids = sorted(sid for sid in all_matches if sid in source_registry)

    if not valid_ids:
        return report_text, []

    remap = {old: idx + 1 for idx, old in enumerate(valid_ids)}

    # Phase 1: valid citations -> placeholders (handling optional spaces)
    def to_placeholder(match):
        old_id = int(match.group(1))
        if old_id in remap:
            return f'[__REF_{remap[old_id]}__]'
        return "" # Strip invalid ones during normalization as a safety net

    temp = re.sub(r'\[\s*(\d+)\s*\]', to_placeholder, report_text)

    # Phase 2: placeholders -> final sequential numbers
    def from_placeholder(match):
        return f'[{match.group(1)}]'

    normalized = re.sub(r'\[__REF_(\d+)__\]', from_placeholder, temp)

    # Build references
    references = []
    for old_id in valid_ids:
        new_id = remap[old_id]
        url = source_registry[old_id].get('url', 'Unknown Source')
        title = source_registry[old_id].get('title')
        if title:
            references.append(f"{new_id}. [{title}]({url})")
        else:
            references.append(f"{new_id}. [{url}]({url})")

    return normalized, references

def _strip_report_images(report_text):
    """Remove ALL ![alt](url) image embeds from the report."""
    return re.sub(r'!\[([^\]]*)\]\((https?://[^\)]+)\)', '', report_text).strip()

def _strip_invalid_citations(report_text, valid_source_ids):
    """Mechanically remove any [N] citation where N is not in the source registry.
    Improved to handle whitespace and prevent orphaned punctuation."""
    report_text = _preprocess_citations(report_text)
    
    def check_citation(match):
        # match.group(1) is the leading whitespace
        # match.group(2) is the ID
        source_id = int(match.group(2))
        if source_id in valid_source_ids:
            return match.group(0) # Keep valid citation with its original whitespace
        return '' # Strip both citation and its leading whitespace
        
    # Match optional leading space + citation with optional interior spaces
    return re.sub(r'(\s*)\[\s*(\d+)\s*\]', check_citation, report_text)
