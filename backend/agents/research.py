import json
import asyncio
import re
import os
import urllib.parse
import base64
import html
from backend.logger import log_event
from bs4 import BeautifulSoup
import httpx
import markdownify
from backend.prompts import (
    RESEARCH_SCOUT_PROMPT,
    RESEARCH_PLANNER_PROMPT,
    RESEARCH_REFLECTION_PROMPT,
    RESEARCH_TRIAGE_PROMPT,
    RESEARCH_STEP_WRITER_PROMPT,
    RESEARCH_STEP_WRITER_STRUCTURED_PROMPT,
    RESEARCH_STEP_SUMMARY_PROMPT,
    RESEARCH_VISION_PROMPT,
    RESEARCH_DETECTIVE_PROMPT,
    RESEARCH_SURGEON_PROMPT,
    RESEARCH_SURGEON_STRUCTURED_PROMPT,
    RESEARCH_SYNTHESIS_PROMPT
)
from backend.utils import (
    create_chunk, validate_research_plan,
    get_current_time, is_safe_web_url
)
from backend.mcp_client import tavily_client, playwright_client
from backend.llm import stream_chat_completion
from backend import config

# --- Configuration ---
# All behavior is now controlled via backend.config




async def generate_scout_response(api_url, model, messages, chat_id=None, model_name=None, api_key=None, **kwargs):
    display_model = model_name or model
    log_event("research_scout_interactive_start", {"chat_id": chat_id, "model": model})

    current_time = get_current_time()

    scout_prompt = f"""You are the Research Context Scout.
    Your goal is to gather crystal-clear requirements from the user before launching a deep research task.
    You MUST ask clarifying questions if the user's request is ambiguous.
    Once you have absolute certainty about the research goals, scope, and constraints, you MUST call the `finalize_scouting` tool with a comprehensive summary.
    Current Time: {current_time}
    """

    system_msg = {"role": "system", "content": scout_prompt}

    # We only send the system prompt and the interactive history (which is pre-filtered by script.js to only show visible things)
    messages_to_send = [system_msg] + messages

    tools = [{
        "type": "function",
        "function": {
            "name": "finalize_scouting",
            "description": "Call this tool ONLY when you have fully understood the user's research request and need no further clarification.",
            "parameters": {
                "type": "object",
                "properties": {
                    "context_summary": {
                        "type": "string",
                        "description": "A highly detailed summary of the research topic, scope, constraints, and user preferences."
                    }
                },
                "required": ["context_summary"]
            }
        }
    }]

    payload = {
        "model": model,
        "messages": messages_to_send,
        "tools": tools,
        "tool_choice": "auto",
        "stream": True
    }
    if api_key:
        payload["api_key"] = api_key

    full_content = ""
    full_reasoning = ""
    current_tool_call = None
    tool_calls = []

    try:
        from backend.llm import stream_chat_completion
        async for chunk_str in stream_chat_completion(api_url, payload):
            try:
                chunk = json.loads(chunk_str[6:])
                delta = chunk['choices'][0]['delta']
                finish_reason = chunk['choices'][0].get('finish_reason')

                if 'tool_calls' in delta and delta['tool_calls']:
                    tc_chunk = delta['tool_calls'][0]
                    if 'id' in tc_chunk:
                        if current_tool_call: tool_calls.append(current_tool_call)
                        current_tool_call = {
                            "id": tc_chunk['id'],
                            "type": "function",
                            "function": {"name": tc_chunk['function']['name'], "arguments": ""}
                        }

                    if 'function' in tc_chunk and 'arguments' in tc_chunk['function']:
                        current_tool_call['function']['arguments'] += tc_chunk['function']['arguments']

                elif 'content' in delta or 'reasoning_content' in delta:
                    content_chunk = delta.get('content', '')
                    reasoning_chunk = delta.get('reasoning_content', '') or delta.get('reasoning', '')

                    if reasoning_chunk:
                        full_reasoning += reasoning_chunk
                        yield f"data: {create_chunk(model, reasoning=reasoning_chunk)}\n\n"

                    if content_chunk:
                        full_content += content_chunk
                        yield f"data: {create_chunk(model, content=content_chunk)}\n\n"

                if finish_reason == 'tool_calls':
                    if current_tool_call:
                        tool_calls.append(current_tool_call)
                        current_tool_call = None
            except Exception:
                pass

        # Handle Tool Call for Finalizing Scouting
        if tool_calls:
            for tc in tool_calls:
                if tc['function']['name'] == 'finalize_scouting':
                    args_str = tc['function']['arguments']
                    try:
                        args = json.loads(args_str)
                        summary = args.get("context_summary", "Gathered context successfully.")
                    except:
                        summary = args_str

                    # 1. Update Database State
                    from backend.storage import update_chat_research_state
                    update_chat_research_state(chat_id, 'planning')

                    # 2. Tell Frontend to retroactively hide all scout turns
                    yield f"data: {json.dumps({'__phase_transition__': True, 'new_state': 'planning'})}\n\n"

                    # 3. Tell Frontend to inject the formal tool call
                    result_msg = f"## Scout Context Gathered\n\n{summary}"
                    yield f"data: {json.dumps({'__inject_tool_call__': True, 'tool_call_id': tc['id'], 'name': 'finalize_scouting', 'result': result_msg})}\n\n"

                    yield f"data: {create_chunk(model, content='\n\n**Scouting Complete. Transitioning to Planning phase...**')}\n\n"
                    break

    except Exception as e:
        log_event("research_scout_error", {"error": str(e)})
        yield f"data: {create_chunk(model, content=f'**Error during scouting:** {str(e)}')}\n\n"

    yield "data: [DONE]\n\n"


async def generate_planner_response(api_url, model, messages, approved_plan=None, chat_id=None, model_name=None, api_key=None, **kwargs):
    display_model = model_name or model
    log_event("research_planner_interactive_start", {"chat_id": chat_id, "model": model})

    current_time = get_current_time()

    planner_prompt = f"""You are the Research Planner.
    Your goal is to propose a structured `<research_plan>` block based on the gathered context.
    The user can review your plan, ask for changes, or approve it.
    If the user asks for changes, update the `<research_plan>` accordingly.
    You must output a complete, valid `<research_plan>` XML block whenever you propose a strategy.
    Current Time: {current_time}
    """

    system_msg = {"role": "system", "content": planner_prompt}
    messages_to_send = [system_msg] + messages

    payload = {
        "model": model,
        "messages": messages_to_send,
        "stream": True
    }
    if api_key:
        payload["api_key"] = api_key

    try:
        from backend.llm import stream_chat_completion
        async for chunk_str in stream_chat_completion(api_url, payload):
            try:
                chunk = json.loads(chunk_str[6:])
                delta = chunk['choices'][0]['delta']

                if 'content' in delta or 'reasoning_content' in delta:
                    content_chunk = delta.get('content', '')
                    reasoning_chunk = delta.get('reasoning_content', '') or delta.get('reasoning', '')

                    if reasoning_chunk:
                        yield f"data: {create_chunk(model, reasoning=reasoning_chunk)}\n\n"

                    if content_chunk:
                        yield f"data: {create_chunk(model, content=content_chunk)}\n\n"
            except Exception:
                pass

    except Exception as e:
        log_event("research_planner_error", {"error": str(e)})
        yield f"data: {create_chunk(model, content=f'**Error during planning:** {str(e)}')}\n\n"

    yield "data: [DONE]\n\n"


def _extract_json_from_text(text):
    """
    Robustly extracts the first JSON object from a string.
    Useful for background tasks (like ranking) where the model might
    prefix output with a <think> block or other commentary.
    """
    if not text:
        return None
    
    # AGENTS.md Compliance: Extract JSON ONLY from the content portion.
    # We explicitly strip <think> blocks to satisfy the "never use reasoning for logic" rule.
    clean_text = text
    if "<think>" in clean_text:
        clean_text = re.sub(r'<think>.*?</think>', '', clean_text, flags=re.DOTALL).strip()
    if "</think>" in clean_text:
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


async def _stream_research_call(api_url, payload, display_model, activity_type, 
                                 thought_limit=None, content_threshold=None, 
                                 step_id=None, is_background=True, api_key=None):
    """
    Unified streaming wrapper for all research LLM calls.
    Implements active meander detection and AGENTS.md compliance.
    
    Yields UI activity chunks via {"type": "activity", "data": str}.
    Returns the final accumulated (and potentially tagged) string via {"type": "result", "data": str}.
    """
    full_content = ""
    full_reasoning = ""
    reasoning_token_count = 0
    is_json_mode = "response_format" in payload
    
    # Ensure stream is enabled
    payload = dict(payload)
    payload["stream"] = True
    if api_key:
        payload["api_key"] = api_key

    was_meandered = False
    
    try:
        async for line in stream_chat_completion(api_url, payload):
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
                
                if reasoning:
                    full_reasoning += reasoning
                    reasoning_token_count += 1
                    
                    if is_background and reasoning_token_count % config.RESEARCH_UI_STREAM_UPDATE_INTERVAL == 0:
                        snippet = _clean_thinking_snippet(full_reasoning)
                        yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, activity_type, {'message': f'...{snippet}', 'state': 'thinking', 'step_id': step_id})}\n\n"}
                
                # Active Meander Detection
                if thought_limit and content_threshold is not None:
                    if len(full_reasoning) > thought_limit and len(full_content) < content_threshold:
                        was_meandered = True
                        if is_background:
                            yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, activity_type, {'message': 'Meander limit reached. Truncating stream.', 'state': 'warning', 'step_id': step_id})}\n\n"}
                        break # Stop the LLM stream physically
            except:
                continue
                
        # Finalize output based on AGENTS.md
        final_output = ""
        if is_json_mode:
            # Structured output: prioritize reasoning (Local AI backend quirk)
            final_output = full_content or full_reasoning
        else:
            # Standard chat: wrap reasoning in tags
            if full_reasoning:
                final_output += f"<think>\n{full_reasoning}\n</think>\n"
            final_output += (full_content or "")
            
        yield {"type": "result", "data": final_output, "meandered": was_meandered}

    except Exception as e:
        log_event("research_stream_call_error", {"error": str(e)})
        yield {"type": "result", "data": "", "meandered": False}


async def _fetch_and_encode_image(url):
    try:
        mcp_res = await playwright_client.execute_tool("fetch_and_encode_image_tool", {"url": url})
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


# =====================================================================
# HELPER FUNCTIONS: URL Selection, Extraction, Vision, Reflection
# =====================================================================


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




async def _process_images_in_content(content, url, vision_model, api_url, vlm_lock, display_model=None, step_id=None, api_key=None):
    """Extract and describe images found in markdown content using a vision model.
    Yields activity packets and finally the modified content string."""
    if not vision_model or not content:
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
            
            payload = {
                "model": vision_model,
                "messages": [
                    {"role": "system", "content": RESEARCH_VISION_PROMPT.format(url=url, alt=alt or "Untitled")},
                    {"role": "user", "content": [{"type": "image_url", "image_url": {"url": base64_img}}]}
                ],
                "max_tokens": config.RESEARCH_MAX_TOKENS_VISION,
                "temperature": config.RESEARCH_TEMPERATURE_VISION,
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
                            gen = _stream_research_call(api_url, payload, None, "vision", is_background=False, api_key=api_key)
                            async for packet in gen:
                                if packet["type"] == "result":
                                    img_desc = packet["data"]
                    else:
                        gen = _stream_research_call(api_url, payload, None, "vision", is_background=False, api_key=api_key)
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


async def _extract_content_for_url(url, search_depth_mode, vision_model, api_url, vlm_lock, display_model=None, step_id=None, raw_content_from_search=None, api_key=None):
    """Extract content from a single URL based on the search depth mode.
    
    Regular mode: Uses raw_content from Tavily search results directly.
    Deep mode: httpx GET → Tavily Extract fallback → pymupdf for PDFs.
    Both modes: Vision processing for inline images (deep mode only since regular uses text).
    
    Yields activity packets and finally the (url, content_string) or (url, None) tuple.
    """
    if search_depth_mode == 'regular':
        # Regular mode: use raw_content from search results (already available)
        if raw_content_from_search and len(raw_content_from_search.strip()) > config.RESEARCH_EXTRACT_MIN_RAW_CONTENT:
            content = raw_content_from_search
            # Vision processing for inline images (now enabled in regular mode too)
            if vision_model:
                async for packet in _process_images_in_content(content, url, vision_model, api_url, vlm_lock, display_model, step_id, api_key=api_key):
                    if packet["type"] == "activity":
                        yield packet
                    else:
                        content = packet["data"]
            yield {"type": "result", "data": (url, content)}
            return
        yield {"type": "result", "data": (url, None)}
        return
    
    # ===== DEEP MODE EXTRACTION =====
    
    # Strategy 1: MCP visit_page (Handles GET, HTML to Markdown, and PDF extraction, with Playwright Fallback)
    content = None
    try:
        mcp_res = await playwright_client.execute_tool("visit_page_tool", {"url": url, "max_chars": 40000, "detail_level": "deep"})
        extracted = mcp_res.content[0].text
        if extracted and "Error:" not in extracted and len(extracted.strip()) > (config.RESEARCH_CONTENT_MIN_LENGTH_DEEP if search_depth_mode == 'deep' else config.RESEARCH_CONTENT_MIN_LENGTH_REGULAR):
            # Vision processing for inline images
            if vision_model:
                async for packet in _process_images_in_content(extracted, url, vision_model, api_url, vlm_lock, display_model, step_id, api_key=api_key):
                    if packet["type"] == "activity":
                        yield packet
                    else:
                        extracted = packet["data"]
            yield {"type": "result", "data": (url, extracted)}
            return
    except Exception:
        pass
    
    yield {"type": "result", "data": (url, None)}


async def _process_tavily_search_images(images, section_index, vision_model, api_url, vlm_lock, display_model=None, api_key=None):
    """Process images from Tavily search results using vision model.
    Yields activity packets and finally the list of (triplet_block_text, img_url, section_index) tuples."""
    if not vision_model or not images:
        yield {"type": "result", "data": []}
        return
    
    # Pre-sanitize and filter by standard logic (extension + keywords)
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
                # Silently skip blocked images - they don't count towards the quota
                continue
            
            payload = {
                "model": vision_model,
                "messages": [
                    {"role": "system", "content": RESEARCH_VISION_PROMPT.format(url="Search Engine Results", alt="Contextual search image")},
                    {"role": "user", "content": [{"type": "image_url", "image_url": {"url": base64_img}}]}
                ],
                "max_tokens": config.RESEARCH_MAX_TOKENS_VISION,
                "temperature": config.RESEARCH_TEMPERATURE_VISION,
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
                            gen = _stream_research_call(api_url, payload, None, "vision", is_background=False, api_key=api_key)
                            async for packet in gen:
                                if packet["type"] == "result":
                                    img_desc = packet["data"]
                    else:
                        gen = _stream_research_call(api_url, payload, None, "vision", is_background=False, api_key=api_key)
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


async def _execute_section_reflection_and_write(
        api_url, model, section_heading, section_description, section_queries,
        extracted_content, accumulated_summaries, section_index,
        n_sections, original_topic, full_plan_text,
        search_depth_mode, vision_model, vlm_lock, chat_id,
        display_model, source_registry, next_source_id, mode_guidance, entity_glossary,
        image_results=None, api_key=None):
    """Multi-turn conversation for a single research section (KV cache reuse).
    
    Acts as an async generator, yielding UI chunks in real-time and streaming 
    the section writing turn directly to the frontend.
    """
    follow_up_buffer = []
    follow_up_content = ""

    def _get_or_create_source_id(url, title=None):
        nonlocal next_source_id
        for sid, entry in source_registry.items():
            if entry.get("url") == url:
                if title and not entry.get("title"):
                    entry["title"] = title
                return sid
        sid = next_source_id
        source_registry[sid] = {"url": url, "title": title or urllib.parse.urlparse(url).netloc}
        next_source_id += 1
        return sid

    gathered_text = ""
    gathered_images = ""
    for item in extracted_content:
        source_id = _get_or_create_source_id(item["url"], item.get("title"))
        content = item['content'][:config.RESEARCH_CONTENT_CHUNK_LIMIT]
        if "[IMAGE DETECTED]" in content:
            gathered_images += f"\n\n---\n[Source {source_id} Visual Data: {item['url']}]\n{content}\n"
        else:
            gathered_text += f"\n\n---\n[Source {source_id}: {item['url']}]\n{content}\n"

    # [NEW] Integrate search-level images (Tavily search results images)
    if image_results:
        gathered_images += "\n\n### [Search Results Visual Evidence]\n"
        for img_block, img_url, _ in image_results:
            gathered_images += f"\n{img_block}\n"

    content_payload = ""
    if gathered_text.strip():
        content_payload += f"## INITIAL SEARCH RESULTS (TEXT CONTENT)\n{gathered_text}"
    if gathered_images.strip():
        content_payload += f"\n\n## INITIAL SEARCH RESULTS (VISUAL EVIDENCE & DESCRIPTIONS)\n{gathered_images}"

    if not content_payload.strip():
        content_payload = "No content was successfully extracted for this initial search."

    if accumulated_summaries:
        summaries_text = "\n".join([
            f"### Section {s['section']+1}: {s['heading']}\n" + "\n".join(f"- {p}" for p in s.get('summary_points', []))
            for s in accumulated_summaries
        ])
    else:
        summaries_text = "No prior sections completed yet. This is the first section."

    queries_text = ", ".join(f'"{q}"' for q in section_queries) if section_queries else "N/A"

    system_prompt = RESEARCH_REFLECTION_PROMPT.format(
        original_topic=original_topic,
        section_heading=section_heading,
        section_description=section_description,
        section_queries=queries_text,
        section_number=section_index + 1,
        total_sections=n_sections,
        remaining_sections=n_sections - section_index - 1,
        full_plan=full_plan_text,
        accumulated_summaries=summaries_text,
        max_gaps=config.RESEARCH_MAX_GAPS_PER_SECTION,
        max_queries_per_section=config.RESEARCH_MAX_QUERIES_PER_SECTION,
        reasoning_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_REFLECTION
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Here is the data gathered for section '{section_heading}':\n\n{content_payload}"}
    ]

    # ---- TURN 1: Gap Analysis ----
    yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, 'reflection', {'message': f'Analyzing findings for section: {section_heading}...', 'step_id': section_index})}\n\n"}

    reflection_payload = {
        "model": model,
        "messages": messages,
        "temperature": config.RESEARCH_TEMPERATURE_REFLECTION,
        "max_tokens": config.RESEARCH_MAX_TOKENS_REFLECTION,
    }

    raw_response = ""
    gen = _stream_research_call(
        api_url, reflection_payload, display_model, "reflection",
        thought_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_REFLECTION,
        content_threshold=config.RESEARCH_MEANDER_CONTENT_THRESHOLD,
        step_id=section_index,
        api_key=api_key
    )
    async for packet in gen:
        if packet["type"] == "activity":
            yield packet
        elif packet["type"] == "result":
            raw_response = packet["data"]
            
    reflection = _extract_json_from_text(raw_response) if raw_response else None

    if not reflection or not isinstance(reflection, dict):
        reflection = {"gaps": [], "plan_modification": {"updates": [], "additions": []}}

    gaps = reflection.get("gaps", [])
    plan_mod = reflection.get("plan_modification")

    messages.append({"role": "assistant", "content": _strip_thinking(raw_response) or '{"gaps": []}'})

    # ---- TURN 2 (conditional): Gap-Filling ----
    if gaps:
        follow_up_queries = [g["query"] for g in gaps[:config.RESEARCH_MAX_GAPS_PER_SECTION] if g.get("query")]

        if follow_up_queries:
            yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, 'follow_up_search', {'message': f'Filling {len(follow_up_queries)} gap(s) for section: {section_heading}...', 'step_id': section_index, 'queries': follow_up_queries})}\n\n"}

            follow_up_content_text = ""
            for fq in follow_up_queries:
                mcp_res = await tavily_client.execute_tool("async_tavily_search_tool", {"query": fq, "max_results": config.RESEARCH_TAVILY_MAX_RESULTS_FOLLOWUP})
                try:
                    res_json = json.loads(mcp_res.content[0].text)
                    fu_results_raw = res_json.get("results", [])
                except:
                    fu_results_raw = []

                fu_results = [r for r in fu_results_raw if r.get('raw_content') or r.get('content')]

                if fu_results:
                    fu_selected = _select_top_urls(fu_results, n=config.RESEARCH_SELECT_TOP_URLS_FOLLOWUP_COUNT)
                    for fu_r in fu_selected:
                        fu_url = fu_r.get('url', '')
                        fu_content_result = None

                        if search_depth_mode == 'regular':
                            fu_content_result = fu_r.get('raw_content', fu_r.get('content', ''))
                        else:
                            async for fu_packet in _extract_content_for_url(
                                fu_url, search_depth_mode, vision_model, api_url, vlm_lock,
                                raw_content_from_search=fu_r.get('raw_content'), api_key=api_key
                            ):
                                if fu_packet["type"] == "activity":
                                    yield fu_packet
                                else:
                                    _, fu_content_result = fu_packet["data"]

                        if fu_content_result and len(fu_content_result.strip()) > config.RESEARCH_EXTRACT_MIN_RAW_CONTENT:
                            source_id = _get_or_create_source_id(fu_url, fu_r.get('title'))
                            follow_up_buffer.append({"url": fu_url, "title": fu_r.get('title'), "content": fu_content_result})
                            follow_up_content_text += f"\n\n---\n[Source {source_id}: {fu_url}]\n{fu_content_result[:config.RESEARCH_CONTENT_CHUNK_LIMIT]}\n"

            if follow_up_content_text.strip():
                fu_text = ""
                fu_imgs = ""
                for fu_item in follow_up_buffer:
                    source_id = _get_or_create_source_id(fu_item["url"], fu_item.get("title"))
                    content = fu_item["content"][:config.RESEARCH_CONTENT_CHUNK_LIMIT]
                    if "[IMAGE DETECTED]" in content:
                        fu_imgs += f"\n\n---\n[Source {source_id} Visual Data: {fu_item['url']}]\n{content}\n"
                    else:
                        fu_text += f"\n\n---\n[Source {source_id}: {fu_item['url']}]\n{content}\n"
                
                fu_payload = ""
                if fu_text.strip():
                    fu_payload += f"## FOLLOW-UP SEARCH RESULTS (TEXT CONTENT)\n{fu_text}"
                if fu_imgs.strip():
                    fu_payload += f"\n\n## FOLLOW-UP SEARCH RESULTS (VISUAL EVIDENCE & DESCRIPTIONS)\n{fu_imgs}"

                messages.append({"role": "user", "content": f"Here is the additional content gathered to fill the identified gaps:\n\n{fu_payload}"})
                messages.append({"role": "assistant", "content": "Acknowledged. I have structured the gap-filling content into text and visual evidence. I will now proceed to write the section."})

    # ---- TURN 2.5: Information Triage (Core Facts Extraction) ----
    yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Triaging core facts for section: {section_heading}...', 'icon': '🧠'})}\n\n"}

    triage_prompt = RESEARCH_TRIAGE_PROMPT.format(
        section_heading=section_heading,
        reasoning_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_REFLECTION
    )
    
    triage_messages_base = list(messages) # Base history
    core_facts_str = ""
    triage_success = False
    raw_triage = ""

    for attempt in range(config.RESEARCH_SURGEON_MAX_RETRIES): # 0: Initial, 1+: Warning/Retry
        triage_messages = list(triage_messages_base)
        if attempt == 1:
            # Stage 1: Warning & Self-Correction
            triage_messages.append({"role": "user", "content": triage_prompt})
            triage_messages.append({"role": "assistant", "content": raw_triage or ""})
            triage_messages.append({
                "role": "user", 
                "content": "Your reasoning was too long or you failed to provide valid JSON. Please be extremely concise. Output ONLY the valid JSON object with core facts extracted from the provided text."
            })
            yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, 'status', {'message': 'Triage meandered/failed. Warning and retrying...', 'icon': '⚠️'})}\n\n"}
        else:
            triage_messages.append({"role": "user", "content": triage_prompt})

        triage_payload = {
            "model": model,
            "messages": triage_messages,
            "temperature": config.RESEARCH_TEMPERATURE_REFLECTION if attempt == 0 else config.RESEARCH_TEMPERATURE_RETRY_FALLBACK,
            "max_tokens": config.RESEARCH_MAX_TOKENS_REFLECTION,
        }

        raw_triage = ""
        triage_meandered = False
        gen = _stream_research_call(
            api_url, triage_payload, display_model, "status",
            thought_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_REFLECTION,
            content_threshold=config.RESEARCH_MEANDER_CONTENT_THRESHOLD,
            api_key=api_key
        )
        async for packet in gen:
            if packet["type"] == "activity":
                yield packet
            elif packet["type"] == "result":
                raw_triage = packet["data"]
                triage_meandered = packet.get("meandered", False)
        
        # Stream-level meander detection is the single source of truth
        if triage_meandered:
            continue
        
        triage_result = _extract_json_from_text(raw_triage) if raw_triage else None
        
        if triage_result and isinstance(triage_result, dict) and triage_result.get("core_facts"):
            triage_success = True
            break

    if not triage_success:
        # Stage 2: Poison Prevention & Structured Fallback (Clean Context)
        yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, 'status', {'message': 'Triage persists in meandering. Falling back to structured mode...', 'icon': '🛡️'})}\n\n"}
        
        structured_payload = {
            "model": model,
            "messages": triage_messages_base + [{"role": "user", "content": triage_prompt}],
            "temperature": config.RESEARCH_TEMPERATURE_RETRY_FALLBACK,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "core_facts_array",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "core_facts": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "fact": {"type": "string"},
                                        "sources": {"type": "array", "items": {"type": "integer"}}
                                    },
                                    "required": ["fact", "sources"],
                                    "additionalProperties": False
                                }
                            }
                        },
                        "required": ["core_facts"],
                        "additionalProperties": False
                    }
                }
            }
        }
        raw_triage = ""
        gen = _stream_research_call(
            api_url, structured_payload, display_model, "status",
            thought_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_REFLECTION,
            content_threshold=config.RESEARCH_MEANDER_CONTENT_THRESHOLD,
            api_key=api_key
        )
        async for packet in gen:
            if packet["type"] == "activity":
                yield packet
            elif packet["type"] == "result":
                raw_triage = packet["data"]
                
        triage_result = _extract_json_from_text(raw_triage) if raw_triage else None

    if triage_result and isinstance(triage_result, dict):
        core_facts_array = triage_result.get("core_facts", [])
        if core_facts_array:
            # Format the output for the writer
            core_facts_lines = []
            for f in core_facts_array:
                if isinstance(f, dict):
                    fact_text = f.get('fact', '')
                    sources = f.get('sources', [])
                    if fact_text and sources:
                        source_str = ", ".join([f"[Source {s}]" for s in sources])
                        core_facts_lines.append(f"- {fact_text} {source_str}")

            if not core_facts_lines:
                raise ValueError("Triage extraction completed but no valid core facts could be parsed.")

            core_facts_str = "\n".join(core_facts_lines)
            
            # Show a brief preview of facts extracted
            fact_count = len(core_facts_array)
            yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Extracted {fact_count} core facts for drafting.', 'icon': '📂'})}\n\n"}
        else:
            raise ValueError("Triage extraction completed but no specific core facts were found.")
    else:
        raise ValueError("Triage extraction failed to return valid data.")
        
    messages.append({"role": "user", "content": triage_prompt})
    messages.append({"role": "assistant", "content": f"I have processed the Triage request. Here are the core facts I extracted:\n{core_facts_str}"})

    # ---- TURN 3: Section Writing (Streaming to Client) ----
    yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, 'writing', {'message': f'Drafting section: {section_heading}...', 'step_id': section_index})}\n\n"}

    # Format entity glossary for prompt
    glossary_str = "\n".join([f"- {k}: {v}" for k, v in entity_glossary.items()]) if entity_glossary else "None yet."

    writer_prompt = RESEARCH_STEP_WRITER_PROMPT.format(
        section_heading=section_heading,
        mode_guidance=mode_guidance,
        reasoning_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_STEP_WRITER,
        entity_glossary=glossary_str
    )
    writer_messages_base = list(messages)
    writer_success = False
    raw_section = ""

    for attempt in range(config.RESEARCH_SURGEON_MAX_RETRIES): # 0: Initial, 1+: Warning/Retry
        writer_messages = list(writer_messages_base)
        if attempt == 1:
            # Stage 1: Warning & Self-Correction — send back AI's exact response
            writer_messages.append({"role": "user", "content": writer_prompt})
            writer_messages.append({"role": "assistant", "content": raw_section or ""})
            writer_messages.append({
                "role": "user", 
                "content": "Your previous attempt meandered or produced insufficient content. Please be extremely concise. Focus on writing a high-density, data-rich markdown section immediately. Start with ## heading."
            })
            yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, 'status', {'message': 'Drafting meandered/too short. Warning and retrying...', 'icon': '⚠️'})}\n\n"}
        else:
            writer_messages.append({"role": "user", "content": writer_prompt})

        raw_section = ""
        writer_meandered = False
        writer_payload = {
            "model": model,
            "messages": writer_messages,
            "temperature": config.RESEARCH_TEMPERATURE_STEP_WRITER if attempt == 0 else config.RESEARCH_TEMPERATURE_RETRY_FALLBACK,
            "max_tokens": config.RESEARCH_MAX_TOKENS_STEP_WRITER,
        }
        gen = _stream_research_call(
            api_url, writer_payload, display_model, "status",
            thought_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_STEP_WRITER,
            content_threshold=config.RESEARCH_MEANDER_CONTENT_THRESHOLD,
            step_id=section_index,
            api_key=api_key
        )
        async for packet in gen:
            if packet["type"] == "activity":
                yield packet
            elif packet["type"] == "result":
                raw_section = packet["data"]
                writer_meandered = packet.get("meandered", False)
        
        # Stream-level meander detection is the single source of truth
        if writer_meandered:
            continue
        
        # Check content quality (strip reasoning for length check)
        clean_content = _strip_thinking(raw_section)
        if len(clean_content.strip()) >= config.RESEARCH_MIN_SECTION_LEN:
            writer_success = True
            break

    if not writer_success:
        # Stage 2: Poison Prevention & Structured Fallback (Clean Context)
        yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, 'status', {'message': 'Drafting meanders persist. Falling back to structured mode...', 'icon': '🛡️'})}\n\n"}
        
        writer_structured_prompt = RESEARCH_STEP_WRITER_STRUCTURED_PROMPT.format(
            section_heading=section_heading,
            mode_guidance=mode_guidance
        )
        
        structured_payload = {
            "model": model,
            "messages": writer_messages_base + [{"role": "user", "content": writer_structured_prompt}],
            "temperature": config.RESEARCH_TEMPERATURE_RETRY_FALLBACK,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "section_draft",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "markdown_content": {"type": "string"}
                        },
                        "required": ["markdown_content"],
                        "additionalProperties": False
                    }
                }
            }
        }
        
        raw_response = ""
        gen = _stream_research_call(
            api_url, structured_payload, display_model, "status",
            thought_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_STEP_WRITER,
            content_threshold=config.RESEARCH_MEANDER_CONTENT_THRESHOLD,
            api_key=api_key
        )
        async for packet in gen:
            if packet["type"] == "activity":
                yield packet
            elif packet["type"] == "result":
                raw_response = packet["data"]
                
        parsed = _extract_json_from_text(raw_response)
        
        if parsed and isinstance(parsed, dict) and "markdown_content" in parsed:
            raw_section = parsed["markdown_content"]
        else:
            if not raw_response or not raw_response.strip():
                raise ValueError("Writer extraction failed to return valid data after structured fallback.")
            raw_section = raw_response or ""

    # Process entities from reasoning if any (before stripping)
    if "<think>" in raw_section:
        match = re.search(r'<think>(.*?)</think>', raw_section, re.DOTALL)
        if match:
            entity_matches = re.findall(r'Entity:\s*"([^"]+)"\s*\(([^)]+)\)', match.group(1), re.IGNORECASE)
            for term, definition in entity_matches:
                if term not in entity_glossary:
                    entity_glossary[term] = definition

    # Strip reasoning from history — only clean content goes into shared messages
    section_text = _strip_thinking(raw_section)
    messages.append({"role": "user", "content": writer_prompt})
    messages.append({"role": "assistant", "content": section_text or ""})

    # Strip trailing bibliographies the LLM might have added
    for ref_header in ['\n## References', '\n### References', '\n## Sources', '\n### Sources']:
        if ref_header in section_text:
            section_text = section_text.split(ref_header)[0]

    section_text = re.sub(r'<section_summary>.*?</section_summary>', '', section_text, flags=re.DOTALL).strip()

    # ---- TURN 4: Section Summary (separate response → isolated task) ----
    summary_points = []
    if section_index < n_sections - 1:
        yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Generating summary for section: {section_heading}...', 'icon': '📋'})}\n\n"}

        summary_prompt = RESEARCH_STEP_SUMMARY_PROMPT.format(
            reasoning_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_SUMMARY
        )
        messages.append({"role": "user", "content": summary_prompt})

        summary_payload = {
            "model": model,
            "messages": messages,
            "temperature": config.RESEARCH_TEMPERATURE_SUMMARY,
            "max_tokens": config.RESEARCH_MAX_TOKENS_SUMMARY,
        }

        raw_summary = ""
        gen = _stream_research_call(
            api_url, summary_payload, display_model, "status",
            thought_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_SUMMARY,
            content_threshold=config.RESEARCH_MEANDER_CONTENT_THRESHOLD,
            api_key=api_key
        )
        async for packet in gen:
            if packet["type"] == "activity":
                yield packet
            elif packet["type"] == "result":
                raw_summary = packet["data"]

        if raw_summary:
            clean_summary = _strip_thinking(raw_summary)

            summary_points = [
                line.strip().lstrip('- •').strip()
                for line in clean_summary.split('\n')
                if line.strip() and line.strip().startswith('-') and len(line.strip()) > 10
            ]

    if not summary_points:
        summary_points = [f"Content gathered and section drafted for: {section_heading}"]

    yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, 'reflection', {'message': f'Section complete: {section_heading}', 'step_id': section_index})}\n\n"}

    yield {"type": "result", "data": (section_text, summary_points, plan_mod, follow_up_content, next_source_id)}


# =====================================================================
# MECHANICAL NORMALIZATION HELPERS
# =====================================================================

def _normalize_citations(report_text, source_registry):
    """Re-number all [N] citations sequentially from [1] and build a references list.
    Uses a two-phase placeholder approach to avoid collision between old and new IDs."""
    
    # Pre-process comma-separated or range citations
    def split_commas(match):
        nums = [n.strip() for n in match.group(1).split(',')]
        return ' '.join(f'[{n}]' for n in nums if n.isdigit())
    report_text = re.sub(r'\[\s*(\d+(?:\s*,\s*\d+)+)\s*\]', split_commas, report_text)
    
    def split_ranges(match):
        start = int(match.group(1))
        end = int(match.group(2))
        if start < end and end - start <= 20: 
            return ' '.join(f'[{i}]' for i in range(start, end + 1))
        return match.group(0)
    report_text = re.sub(r'\[(\d+)-(\d+)\]', split_ranges, report_text)

    # Clean up weird AI markdown formats for citations
    # Strip markdown link syntax: [1](#1) -> [1]
    report_text = re.sub(r'\[(\d+)\]\([^)]+\)', r'[\1]', report_text)
    # Strip nested brackets: [[1]] -> [1] or [[1]; [2]] -> [1]; [2]
    report_text = re.sub(r'\[\s*(\[\d+\](?:[^\[\]]*\[\d+\])*)\s*\]', r'\1', report_text)
    
    all_matches = set(int(m) for m in re.findall(r'\[(\d+)\]', report_text))
    valid_ids = sorted(sid for sid in all_matches if sid in source_registry)

    if not valid_ids:
        return report_text, []

    remap = {old: idx + 1 for idx, old in enumerate(valid_ids)}

    # Phase 1: valid citations → placeholders
    def to_placeholder(match):
        old_id = int(match.group(1))
        if old_id in remap:
            return f'[__REF_{remap[old_id]}__]'
        return match.group(0)

    temp = re.sub(r'\[(\d+)\]', to_placeholder, report_text)

    # Phase 2: placeholders → final sequential numbers
    def from_placeholder(match):
        return f'[{match.group(1)}]'

    normalized = re.sub(r'\[__REF_(\d+)__\]', from_placeholder, temp)

    # Build references (mapping to URLs, not chunks)
    references = []
    for old_id in valid_ids:
        new_id = remap[old_id]
        url = source_registry[old_id].get('url', 'Unknown Source')
        title = source_registry[old_id].get('title')
        if title:
            references.append(f"{new_id}. [{title}]({url})")
        else:
            # Display the actual URL instead of just "Source"
            references.append(f"{new_id}. [{url}]({url})")

    return normalized, references


def _strip_report_images(report_text):
    """Remove ALL ![alt](url) image embeds from the report.
    Vision processing still enriches the content via descriptions, but images
    are never embedded — the report model can't actually see them."""
    return re.sub(r'!\[([^\]]*)\]\((https?://[^\)]+)\)', '', report_text).strip()

def _strip_invalid_citations(report_text, valid_source_ids):
    """Mechanically remove any [N] citation where N is not in the source registry."""
    def check_citation(match):
        source_id = int(match.group(1))
        if source_id in valid_source_ids:
            return match.group(0) # Keep valid citation
        return '' # Strip invalid citation silently
        
    def split_commas(match):
        nums = [n.strip() for n in match.group(1).split(',')]
        return ' '.join(f'[{n}]' for n in nums if n.isdigit())
    report_text = re.sub(r'\[\s*(\d+(?:\s*,\s*\d+)+)\s*\]', split_commas, report_text)
    
    def split_ranges(match):
        start = int(match.group(1))
        end = int(match.group(2))
        if start < end and end - start <= 20:
            return ' '.join(f'[{i}]' for i in range(start, end + 1))
        return match.group(0)
    report_text = re.sub(r'\[(\d+)-(\d+)\]', split_ranges, report_text)

    # Strip basic [N] format (complex formatting is already handled by _normalize_citations later)
    return re.sub(r'\[(\d+)\]', check_citation, report_text)


async def generate_research_response(api_url, model, messages, approved_plan=None, chat_id=None, search_depth_mode='regular', vision_model=None, model_name=None, resume_state=None, api_key=None):
    """
    Main Research Pipeline
    
    Phase 0: Context Scout (pre-planning analysis)
    Phase 1: Planning (structured research plan generation)
    Phase 2: Sequential Step Execution (search → select → extract → reflect → write)
    Phase 3: Assembly & Audit (stitch → normalize → audit patches → synthesis → references)
    """
    display_model = model_name or model
    log_event("research_start", {"chat_id": chat_id, "mode": 'execution' if approved_plan else 'planning', "model": model, "vision_model": vision_model})

    # Ensure MCP clients are connected
    await tavily_client.connect()
    await playwright_client.connect()

    accumulated_summaries = []
    source_registry = {}  # {global_source_id: {"url": str}}
    global_source_id = 1
    entity_glossary = {}
    structural_recommendation = "narrative"
    original_query = "Automated Research Task"
    for m in messages:
        if m['role'] == 'user':
            content = m.get('content', '')
            if isinstance(content, list):
                content = next((p.get('text', '') for p in content if p.get('type') == 'text'), '')
            if isinstance(content, str) and '<research_plan>' not in content:
                original_query = content

    # VLM concurrency lock (serialize vision model calls)
    vlm_lock = asyncio.Semaphore(1) if vision_model else None

    # Ensure MCP clients are connected
    if not tavily_client.session:
        await tavily_client.connect()
    if not playwright_client.session:
        await playwright_client.connect()

    # --- PHASE TRANSITION INJECTION ---
    # Hide the interactive planning turns and inject the finalized plan
    if approved_plan and not resume_state:
        yield f"data: {json.dumps({'__phase_transition__': True, 'new_state': 'executing'})}\n\n"

        result_msg = f"## Approved Research Plan\n\n{approved_plan}"
        tc_id = "call_plan_" + str(int(time.time()))
        yield f"data: {json.dumps({'__inject_tool_call__': True, 'tool_call_id': tc_id, 'name': 'finalize_planning', 'result': result_msg})}\n\n"

    # ===== PARSE PLAN IF EXECUTING =====
    sections = []
    total_query_count = 0
    if approved_plan:
        try:
            xml_content = approved_plan.strip()
            if not xml_content.startswith("<research_plan>"):
                xml_content = f"<research_plan>\n{xml_content}\n</research_plan>"
                
            plan_root = BeautifulSoup(xml_content, 'html.parser')
            for sec_node in plan_root.find_all('section'):
                heading_tag = sec_node.find('heading')
                heading = heading_tag.get_text(strip=True) if heading_tag else 'Untitled Section'
                desc_tag = sec_node.find('description')
                description = desc_tag.get_text(strip=True) if desc_tag else ''
                
                queries = []
                for q_tag in sec_node.find_all('query'):
                    query_text = q_tag.get_text(strip=True)
                    if query_text:
                        queries.append({
                            "search": query_text,
                            "topic": q_tag.get('topic', 'general'),
                            "time_range": q_tag.get('time_range'),
                            "start_date": q_tag.get('start_date'),
                            "end_date": q_tag.get('end_date'),
                        })
                
                sections.append({
                    "heading": heading,
                    "description": description,
                    "queries": queries
                })
                total_query_count += len(queries)
        except Exception as e:
            yield f"data: {create_chunk(model, content=f'**Error parsing XML plan:** {str(e)}')}\n\n"
            yield "data: [DONE]\n\n"
            return

        if not sections:
            yield f"data: {create_chunk(model, content='**Plan has zero sections.**')}\n\n"
            yield "data: [DONE]\n\n"
            return
            
    n_sections = len(sections)
    if not resume_state:
        if not approved_plan:
            current_time = get_current_time()
            conversation_history = [m for m in messages if m['role'] != 'system']

            # ===== PHASE 0: CONTEXT SCOUT =====
            yield f"data: {_create_activity_chunk(display_model, 'planning', {'message': 'Analyzing your research query...', 'state': 'thinking'})}\n\n"

            scout_prompt = RESEARCH_SCOUT_PROMPT.format(
                current_time=current_time,
                reasoning_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_SCOUT
            )
            scout_messages = [{"role": "system", "content": scout_prompt}]
            scout_messages.extend(conversation_history[-config.RESEARCH_CONTEXT_HISTORY_SCOUT:])

            scout_payload = {
                "model": model,
                "messages": scout_messages,
                "temperature": config.RESEARCH_TEMPERATURE_SCOUT,
            }

            scout_analysis = None
            scout_context_str = ""
            preliminary_search_results = ""

            raw_scout = ""
            try:
                gen = _stream_research_call(
                    api_url, scout_payload, display_model, "planning",
                    thought_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_SCOUT,
                    content_threshold=config.RESEARCH_MEANDER_CONTENT_THRESHOLD,
                    api_key=api_key
                )
                async for packet in gen:
                    if packet["type"] == "activity":
                        yield packet["data"]
                    elif packet["type"] == "result":
                        raw_scout = packet["data"]

                if raw_scout:
                    scout_analysis = _extract_json_from_text(raw_scout)

                if scout_analysis and isinstance(scout_analysis, dict):
                    log_event("research_scout_complete", {
                        "chat_id": chat_id,
                        "topic_type": scout_analysis.get("topic_type"),
                        "time_sensitive": scout_analysis.get("time_sensitive"),
                        "confidence": scout_analysis.get("confidence"),
                        "needs_search": scout_analysis.get("needs_search"),
                        "structural_recommendation": scout_analysis.get("structural_recommendation")
                    })
                    
                    structural_recommendation = scout_analysis.get("structural_recommendation", "narrative")

                    _topic = scout_analysis.get('topic_type', 'general')
                    _time_sens = scout_analysis.get('time_sensitive', False)
                    _conf = scout_analysis.get('confidence', 'unknown')
                    yield f"data: {_create_activity_chunk(display_model, 'planning', {'message': f'Topic classified as: {_topic} | Time-sensitive: {_time_sens} | Confidence: {_conf}', 'state': 'thinking'})}\n\n"

                    # Execute preliminary search if scout requests one
                    if scout_analysis.get("needs_search") and scout_analysis.get("preliminary_search"):
                        prelim = scout_analysis["preliminary_search"]
                        prelim_query = prelim.get("query", "")
                        prelim_topic = prelim.get("topic", "general")
                        prelim_time_range = prelim.get("time_range")

                        if prelim_query:
                            _pq_msg = f'Gathering preliminary context: "{prelim_query}"...'
                            yield f"data: {_create_activity_chunk(display_model, 'planning', {'message': _pq_msg, 'state': 'thinking'})}\n\n"

                            mcp_res = await tavily_client.execute_tool("async_tavily_search_tool", {
                                "query": prelim_query,
                                "topic": prelim_topic,
                                "time_range": prelim_time_range
                            })
                            try:
                                res_json = json.loads(mcp_res.content[0].text)
                                prelim_results = res_json.get("results", [])
                                prelim_images = res_json.get("images", [])
                            except:
                                prelim_results, prelim_images = [], []

                            if prelim_results:
                                context_snippets = []
                                for r in prelim_results[:config.RESEARCH_SCOUT_PRELIM_RESULTS_COUNT]:
                                    title = r.get('title', 'Untitled')
                                    snippet = r.get('content', '')
                                    url = r.get('url', '')
                                    context_snippets.append(f"- **{title}** ({url}): {snippet}")
                                preliminary_search_results = "\n".join(context_snippets)

                                if prelim_images:
                                    preliminary_search_results += "\n\n### Preliminary Visual Evidence:\n" + "\n".join([f"- {img.get('url') if isinstance(img, dict) else img}" for img in prelim_images[:5]])

                                yield f"data: {_create_activity_chunk(display_model, 'planning', {'message': f'Gathered context from {len(prelim_results[:config.RESEARCH_SCOUT_PRELIM_RESULTS_COUNT])} sources and {len(prelim_images[:5])} images.', 'state': 'thinking'})}\n\n"
                            else:
                                yield f"data: {_create_activity_chunk(display_model, 'planning', {'message': 'Preliminary search returned no results. Proceeding to planning...', 'state': 'thinking'})}\n\n"

                    scout_context_parts = []
                    scout_context_parts.append(f"## Context Analysis (from pre-planning scout)")
                    scout_context_parts.append(f"- **Topic Type:** {scout_analysis.get('topic_type', 'general')}")
                    scout_context_parts.append(f"- **Time-Sensitive:** {scout_analysis.get('time_sensitive', False)}")
                    scout_context_parts.append(f"- **Confidence Level:** {scout_analysis.get('confidence', 'unknown')}")
                    scout_context_parts.append(f"- **Recommended Structure:** {structural_recommendation}")
                    if scout_analysis.get('context_notes'):
                        scout_context_parts.append(f"- **Analysis Notes:** {scout_analysis['context_notes']}")
                    if preliminary_search_results:
                        scout_context_parts.append(f"\n### Preliminary Search Results (use these to inform your plan)")
                        scout_context_parts.append(preliminary_search_results)
                    scout_context_str = "\n".join(scout_context_parts)
                else:
                    log_event("research_scout_failed", {"chat_id": chat_id, "raw_output": raw_scout[:200] if raw_scout else "empty"})
                    scout_context_str = "## Context Analysis\nScout analysis was not available. Proceed with general planning based on the user query alone."
            except Exception as e:
                log_event("research_scout_error", {"chat_id": chat_id, "error": str(e)})
                scout_context_str = "## Context Analysis\nScout analysis encountered an error. Proceed with general planning based on the user query alone."

            # ===== PHASE 1: PLANNING =====
            system_prompt = RESEARCH_PLANNER_PROMPT.format(
                current_time=current_time,
                scout_context=scout_context_str,
                max_queries_per_section=config.RESEARCH_MAX_QUERIES_PER_SECTION,
                max_total_queries=config.RESEARCH_MAX_TOTAL_QUERIES,
                reasoning_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_PLANNING
            )
            messages_to_send = [{"role": "system", "content": system_prompt}]
            messages_to_send.extend(conversation_history[-config.RESEARCH_CONTEXT_HISTORY_PLANNING:])

            payload = {
                "model": model,
                "messages": messages_to_send,
                "stream": True,
                "temperature": config.RESEARCH_TEMPERATURE_PLANNING,
                "top_p": config.RESEARCH_TOP_P_PLANNING,
                "max_tokens": config.RESEARCH_MAX_TOKENS_PLANNING,
            }

            yield f"data: {_create_activity_chunk(display_model, 'planning', {'message': 'Designing research strategy...', 'state': 'thinking'})}\n\n"

            for attempt in range(1, config.RESEARCH_MAX_PLAN_RETRIES + 1):
                payload["messages"] = list(messages_to_send)
                plan_source = ""
                
                gen = _stream_research_call(
                    api_url, payload, display_model, "planning",
                    thought_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_PLANNING,
                    content_threshold=config.RESEARCH_MEANDER_CONTENT_THRESHOLD,
                    api_key=api_key
                )
                async for packet in gen:
                    if packet["type"] == "activity":
                        yield packet["data"]
                    elif packet["type"] == "result":
                        plan_source = packet["data"]
                
                if not plan_source.strip():
                    yield f"data: {_create_activity_chunk(display_model, 'planning', {'message': f'Attempt {attempt}: No output received. Retrying...', 'state': 'warning'})}\n\n"
                    continue

                yield f"data: {_create_activity_chunk(display_model, 'planning', {'message': 'Validating research plan structure...', 'state': 'validating'})}\n\n"

                clean_xml, error = validate_research_plan(plan_source)

                if clean_xml:
                    yield f"data: {_create_activity_chunk(display_model, 'planning', {'message': 'Plan generated successfully!', 'state': 'complete'})}\n\n"
                    yield f"data: {create_chunk(display_model, content=clean_xml)}\n\n"
                    yield "data: [DONE]\n\n"
                    return
                else:
                    yield f"data: {_create_activity_chunk(display_model, 'planning', {'message': f'Validation issue: {error}. Refining plan...', 'state': 'warning'})}\n\n"
                    if attempt < config.RESEARCH_MAX_PLAN_RETRIES:
                        messages_to_send = list(messages_to_send)
                        # Ensure we include the full trace if things go wrong
                        messages_to_send.append({"role": "assistant", "content": plan_source or ""})
                        messages_to_send.append({
                            "role": "user",
                            "content": f"Your output failed validation: {error}\nPlease correct the issue and regenerate the complete <research_plan> block carefully."
                        })

            yield f"data: {create_chunk(model, content='**I was unable to generate a valid research plan.** Please try rephrasing your research topic or simplifying the request.')}\n\n"
            yield "data: [DONE]\n\n"
            return

    # =====================================================================
    # PHASE 2: SECTION EXECUTION (for each section → queries → reflect → write)
    # =====================================================================

    yield f"data: {_create_activity_chunk(display_model, 'phase', {'message': 'Beginning sequential research execution...', 'icon': '🚀', 'collapsible': True})}\n\n"

    state_path = os.path.join(config.DATA_DIR, "tasks", f"{chat_id}_state.json")
    os.makedirs(os.path.dirname(state_path), exist_ok=True)

    content_budget = config.RESEARCH_CONTENT_BUDGET_DEEP if search_depth_mode == 'deep' else config.RESEARCH_CONTENT_BUDGET_REGULAR

    mode_guidance = "DEEP mode: Massive comprehensiveness required. Write extremely detailed, data-dense sections." if search_depth_mode == 'deep' else "REGULAR mode: Write comprehensive, well-structured sections with good detail."
    if structural_recommendation and structural_recommendation != "narrative":
        mode_guidance += f" Structural Recommendation: Use a '{structural_recommendation}' format for this section to best present the findings."

    # Load resume state if available
    if resume_state and os.path.exists(state_path):
        try:
            with open(state_path, "r", encoding="utf-8") as sf:
                saved = json.load(sf)
            accumulated_summaries = saved.get("accumulated_summaries", [])
            source_registry = {int(k): v for k, v in saved.get("source_registry", {}).items()}
            global_source_id = saved.get("global_source_id", 1)
            structural_recommendation = saved.get("structural_recommendation", "narrative")
            last_completed_section = saved.get("last_completed_section", -1)
            yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Resuming from section {last_completed_section + 2}...', 'icon': '🔄'})}\n\n"
        except Exception:
            last_completed_section = -1
    else:
        last_completed_section = -1

    # Extract the plan title
    plan_root_for_title = BeautifulSoup(approved_plan, 'html.parser')
    title_tag = plan_root_for_title.find('title')
    report_title = title_tag.get_text(strip=True) if title_tag else "Research Report"

    try:
        for section_idx, section in enumerate(sections):
            # Skip already-completed sections on resume
            if section_idx <= last_completed_section:
                yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Skipping completed section {section_idx+1}.', 'icon': '⏭️'})}\n\n"
                continue

            heading = section["heading"]
            description = section["description"]
            section_queries = section["queries"]

            yield f"data: {_create_activity_chunk(display_model, 'phase', {'message': f'Section {section_idx+1}/{n_sections}: {heading}', 'icon': '📋', 'collapsible': True})}\n\n"

            # --- INNER LOOP: Execute each query for this section ---
            section_content_buffer = []
            vlm_image_results = []

            for q_idx, query_info in enumerate(section_queries):
                query = query_info["search"]
                q_topic = query_info.get("topic", "general")
                q_time_range = query_info.get("time_range")
                q_start_date = query_info.get("start_date")
                q_end_date = query_info.get("end_date")

                yield f"data: {_create_activity_chunk(display_model, 'search', {'query': query, 'step_id': section_idx, 'displayMessage': f'Query {q_idx+1}/{len(section_queries)}: Searching...'})}\n\n"

                # --- SEARCH ---
                mcp_res = await tavily_client.execute_tool("async_tavily_search_tool", {
                    "query": query, "topic": q_topic, "time_range": q_time_range,
                    "start_date": q_start_date, "end_date": q_end_date,
                    "max_results": config.RESEARCH_TAVILY_MAX_RESULTS_INITIAL
                })
                try:
                    res_json = json.loads(mcp_res.content[0].text)
                    results_raw = res_json.get("results", [])
                    search_images = res_json.get("images", [])
                except:
                    results_raw, search_images = [], []

                results = [r for r in results_raw if r.get('raw_content') or r.get('content')]

                if not results:
                    yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'No results for query: {query[:40]}...', 'icon': '⚠️'})}\n\n"
                    continue

                filtered_results = [{'title': r.get('title'), 'url': r.get('url'), 'snippet': r.get('content')} for r in results]
                yield f"data: {_create_activity_chunk(display_model, 'search_results', {'results': filtered_results, 'step_id': section_idx})}\n\n"

                # --- SELECT ---
                selected = _select_top_urls(results, n=config.RESEARCH_SELECT_TOP_URLS_COUNT)
                yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Selected {len(selected)} sources from {len(results)} results.', 'step_id': section_idx, 'icon': '🎯'})}\n\n"

                # --- EXTRACT with content budget ---
                query_content_buffer = []
                accumulated_tokens = 0

                for sel_result in selected:
                    if accumulated_tokens >= content_budget:
                        yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Content budget reached for this query ({content_budget} tokens).', 'icon': '📊'})}\n\n"
                        break

                    sel_url = sel_result.get('url', '')
                    yield f"data: {_create_activity_chunk(display_model, 'visit', {'url': sel_url})}\n\n"

                    extracted = None
                    async for packet in _extract_content_for_url(
                        sel_url, search_depth_mode, vision_model, api_url, vlm_lock,
                        display_model=display_model, step_id=section_idx,
                        raw_content_from_search=sel_result.get('raw_content'), api_key=api_key
                    ):
                        if packet["type"] == "activity":
                            yield packet["data"]
                        else:
                            _, extracted = packet["data"]

                    if extracted and len(extracted.strip()) > config.RESEARCH_EXTRACT_MIN_TAVILY_CONTENT:
                        content_tokens = len(extracted) // 4
                        # Trim if exceeding budget
                        if accumulated_tokens + content_tokens > content_budget:
                            remaining_chars = (content_budget - accumulated_tokens) * 4
                            if remaining_chars > 0:
                                extracted = extracted[:remaining_chars]
                                content_tokens = len(extracted) // 4
                            else:
                                break
                        query_content_buffer.append({"url": sel_url, "title": sel_result.get('title'), "content": extracted})
                        accumulated_tokens += content_tokens
                        yield f"data: {_create_activity_chunk(display_model, 'visit_complete', {'url': sel_url, 'chars': len(extracted)})}\n\n"
                    else:
                        yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Failed to extract content from {sel_url[:40]}...', 'icon': '⚠️'})}\n\n"

                # --- PROCESS SEARCH IMAGES (VLM) ---
                if vision_model and search_images:
                    async for packet in _process_tavily_search_images(search_images, section_idx, vision_model, api_url, vlm_lock, display_model=display_model, api_key=api_key):
                        if packet["type"] == "activity":
                            yield packet["data"]
                        else:
                            vlm_image_results.extend(packet["data"])

                # --- DEEP MODE: Map top URLs for sub-pages ---
                if search_depth_mode == 'deep':
                    for sel_result in selected:
                        if accumulated_tokens >= content_budget:
                            break
                        sel_url = sel_result.get('url', '')
                        yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Deep mapping: {sel_url[:40]}...', 'step_id': section_idx, 'icon': '🗺️'})}\n\n"

                        mcp_res = await tavily_client.execute_tool("async_tavily_map_tool", {"url_to_map": sel_url, "instruction": f"Researching: {heading}. Find deep data pages."})
                        try:
                            res_json = json.loads(mcp_res.content[0].text)
                            sub_mapped = res_json.get("results", [])
                        except:
                            sub_mapped = []

                        if sub_mapped:
                            for mapped_url in sub_mapped[:config.RESEARCH_DEEP_MAP_MAX_URLS]:
                                if accumulated_tokens >= content_budget:
                                    break
                                if isinstance(mapped_url, dict):
                                    mapped_url = mapped_url.get('url', '')
                                if not mapped_url or mapped_url in [item['url'] for item in query_content_buffer]:
                                    continue

                                yield f"data: {_create_activity_chunk(display_model, 'visit', {'url': mapped_url})}\n\n"

                                deep_extracted = None
                                async for packet in _extract_content_for_url(
                                    mapped_url, search_depth_mode, vision_model, api_url, vlm_lock,
                                    display_model=display_model, step_id=section_idx, api_key=api_key
                                ):
                                    if packet["type"] == "activity":
                                        yield packet["data"]
                                    else:
                                        _, deep_extracted = packet["data"]

                                if deep_extracted and len(deep_extracted.strip()) > config.RESEARCH_MAP_MIN_CONTENT:
                                    content_tokens = len(deep_extracted) // 4
                                    if accumulated_tokens + content_tokens > content_budget:
                                        remaining_chars = (content_budget - accumulated_tokens) * 4
                                        if remaining_chars > 0:
                                            deep_extracted = deep_extracted[:remaining_chars]
                                            content_tokens = len(deep_extracted) // 4
                                        else:
                                            break
                                    query_content_buffer.append({"url": mapped_url, "title": None, "content": deep_extracted})
                                    accumulated_tokens += content_tokens
                                    yield f"data: {_create_activity_chunk(display_model, 'visit_complete', {'url': mapped_url, 'chars': len(deep_extracted)})}\n\n"

                section_content_buffer.extend(query_content_buffer)
                yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Query {q_idx+1} gathered {len(query_content_buffer)} items (~{accumulated_tokens}k tokens).', 'icon': '💾'})}\n\n"

            # --- Check if we got any content for this section ---
            if not section_content_buffer:
                yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'No content gathered for section: {heading}. Skipping.', 'icon': '⚠️'})}\n\n"
                accumulated_summaries.append({
                    "section": section_idx, "heading": heading,
                    "summary_points": ["No search results found for this section."]
                })
                continue

            yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Total: {len(section_content_buffer)} content items for section: {heading}', 'icon': '💾'})}\n\n"

            # --- SECTION-LEVEL PROCESSING: Reflect + Triage + Write + Summary ---
            section_text = summary_points = plan_mod = _ = None

            query_strings = [q["search"] for q in section_queries]
            async for packet in _execute_section_reflection_and_write(
                    api_url, model, heading, description, query_strings,
                    section_content_buffer, accumulated_summaries, section_idx,
                    n_sections, original_query, approved_plan,
                    search_depth_mode, vision_model, vlm_lock, chat_id,
                    display_model, source_registry, global_source_id, mode_guidance, entity_glossary,
                    image_results=vlm_image_results, api_key=api_key
                ):

                if packet["type"] in ("activity", "stream", "stream_chunk"):
                    yield packet["data"]
                elif packet["type"] == "result":
                    section_text, summary_points, plan_mod, _, global_source_id = packet["data"]

            yield f"data: {create_chunk(display_model, content=chr(10)*2)}\n\n"

            # Pair the section text directly with its summary object
            accumulated_summaries.append({
                "section": section_idx, "heading": heading,
                "summary_points": summary_points,
                "plan_modification": plan_mod,
                "section_text": section_text
            })

            # Handle plan modifications (adding new sections)
            if plan_mod and isinstance(plan_mod, dict):
                for addition in plan_mod.get('additions', []):
                    new_heading = addition.get('heading', '')
                    new_desc = addition.get('description', '')
                    new_queries_raw = addition.get('queries', [])
                    if new_heading and new_queries_raw and total_query_count + len(new_queries_raw) <= config.RESEARCH_MAX_TOTAL_QUERIES:
                        new_queries = [{"search": q, "topic": "general", "time_range": None, "start_date": None, "end_date": None} for q in new_queries_raw[:config.RESEARCH_MAX_QUERIES_PER_SECTION]]
                        sections.append({"heading": new_heading, "description": new_desc, "queries": new_queries})
                        n_sections = len(sections)
                        total_query_count += len(new_queries)
                        log_event("research_section_added", {"chat_id": chat_id, "heading": new_heading, "queries": len(new_queries)})
                        yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'New section added: {new_heading}', 'icon': '➕'})}\n\n"

            yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Section {section_idx+1}/{n_sections} complete: {heading}', 'icon': '✅'})}\n\n"

            # Save state for resume
            state = {
                "accumulated_summaries": accumulated_summaries,
                "source_registry": {str(k): v for k, v in source_registry.items()},
                "global_source_id": global_source_id,
                "last_completed_section": section_idx,
                "structural_recommendation": structural_recommendation,
                "entity_glossary": entity_glossary
            }
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump(state, f)

    except Exception as e:
        import traceback
        traceback.print_exc()
        log_event("research_section_execution_error", {"chat_id": chat_id, "error": str(e)})
        yield f"data: {create_chunk(model, content=f'**Error during section execution:** {str(e)}')}\n\n"
        yield f"data: {_create_activity_chunk(display_model, 'needs_retry', {'state': 'section_execution', 'message': f'Section execution failed: {str(e)}'})}\n\n"
        yield "data: [DONE]\n\n"
        return

    # =====================================================================
    # PHASE 3: ASSEMBLY & AUDIT
    # =====================================================================
    try:
        yield f"data: {_create_activity_chunk(display_model, 'phase', {'message': 'Assembling and auditing final report...', 'icon': '📝'})}\n\n"

        # If resuming directly into Phase 3, reload state
        if resume_state and not accumulated_summaries:
            state_path = os.path.join(config.DATA_DIR, "tasks", f"{chat_id}_state.json")
            if os.path.exists(state_path):
                with open(state_path, "r", encoding="utf-8") as sf:
                    saved = json.load(sf)
                accumulated_summaries = saved.get("accumulated_summaries", [])
                
                # Backward compatibility: handle old state files that had separate lists
                old_section_texts = saved.get("all_section_texts", [])
                if old_section_texts and accumulated_summaries and not any(s.get('section_text') for s in accumulated_summaries):
                    text_idx = 0
                    for s in accumulated_summaries:
                        # Attempt to map old section texts to non-skipped summaries
                        # (Older system usually had a one-to-one mapping for successful steps)
                        if s.get('summary_points') and "No search results found" not in str(s['summary_points'][0]):
                            if text_idx < len(old_section_texts):
                                s['section_text'] = old_section_texts[text_idx]
                                text_idx += 1

                source_registry = {int(k): v for k, v in saved.get("source_registry", {}).items()}
                entity_glossary = saved.get("entity_glossary", {})

        # Filter out steps that didn't produce a section (skipped steps)
        valid_summaries = [s for s in accumulated_summaries if s.get('section_text')]

        if not valid_summaries:
            yield f"data: {create_chunk(model, content='**Error: No sections were generated.**')}\n\n"
            yield "data: [DONE]\n\n"
            return

        # --- 3.1 Stitch sections ---
        plan_root_for_title = BeautifulSoup(approved_plan, 'html.parser')
        title_tag = plan_root_for_title.find('title')
        report_title = title_tag.get_text(strip=True) if title_tag else "Research Report"
        full_report = f"# {report_title}\n\n" + "\n\n".join([s['section_text'] for s in valid_summaries])

        # --- 3.2 Mechanical image stripping (vision enriches content, but images are never embedded) ---
        full_report = _strip_report_images(full_report)

        # --- 3.3 Pre-Audit Citation Validation ---
        # Mechanically remove any [N] tag that doesn't point to a real source
        valid_source_ids = set(source_registry.keys())
        for s in valid_summaries:
            s['section_text'] = _strip_invalid_citations(s['section_text'], valid_source_ids)

        # --- 3.4 Auditor (if enabled) ---
        if config.RESEARCH_AUDIT_ENABLED:
            yield f"data: {_create_activity_chunk(display_model, 'status', {'message': 'Running quality audit...', 'icon': '🔍'})}\n\n"

            # Build sections JSON for the auditor (paired data)
            report_sections_json = json.dumps(
                {s['heading']: s['section_text'] for s in valid_summaries},
                indent=2
            )

            auditor_prompt = RESEARCH_DETECTIVE_PROMPT.format(
                user_query=original_query,
                reasoning_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_AUDIT
            )

            auditor_messages = [
                {"role": "system", "content": "You are the Report Auditor pipeline."},
                {"role": "user", "content": f"Here is the report draft to audit:\n{report_sections_json}\n\n{auditor_prompt}"}
            ]

            # TURN 1: Detective
            detective_payload = {
                "model": model,
                "messages": auditor_messages,
                "temperature": config.RESEARCH_TEMPERATURE_AUDIT,
                "max_tokens": config.RESEARCH_MAX_TOKENS_AUDIT,
            }

            raw_audit = ""
            gen = _stream_research_call(
                api_url, detective_payload, display_model, "status",
                thought_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_AUDIT,
                content_threshold=config.RESEARCH_MEANDER_CONTENT_THRESHOLD,
                api_key=api_key
            )
            async for packet in gen:
                if packet["type"] == "activity":
                    yield packet["data"]
                elif packet["type"] == "result":
                    raw_audit = packet["data"]

            audit_result = _extract_json_from_text(raw_audit) if raw_audit else None
            
            log_event("research_detective_complete", {
                "chat_id": chat_id,
                "raw_output": raw_audit,
                "parsed_success": bool(audit_result)
            })

            auditor_messages.append({"role": "assistant", "content": _strip_thinking(raw_audit) or ""})

            if not audit_result or not isinstance(audit_result, dict):
                audit_result = {"issues": []}

            if audit_result and isinstance(audit_result, dict):
                issues = audit_result.get("issues", [])
                
                if issues:
                    yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Detective found {len(issues)} issue(s)... prioritizing fixes.', 'icon': '🔬'})}\n\n"
                    
                    # Group issues by section
                    issues_by_section = {}
                    for issue in issues:
                        sec_title = issue.get("section_title", "").strip()
                        if sec_title:
                            if sec_title not in issues_by_section:
                                issues_by_section[sec_title] = []
                            issues_by_section[sec_title].append(issue)
                    
                    # Filter based on severity thresholds
                    high_count = 0
                    med_count = 0
                    low_count = 0
                    
                    sections_to_rewrite = []
                    
                    # We process sections, determining highest severity in each
                    for sec_title, sec_issues in issues_by_section.items():
                        highest_severity = "Low"
                        for issue in sec_issues:
                            sev = issue.get("severity", "Low")
                            if sev == "High":
                                highest_severity = "High"
                                break
                            elif sev == "Medium" and highest_severity != "High":
                                highest_severity = "Medium"
                                
                        should_fix = False
                        if highest_severity == "High" and high_count < config.RESEARCH_AUDIT_MAX_HIGH_SEVERITY:
                            should_fix = True
                            high_count += 1
                        elif highest_severity == "Medium" and med_count < config.RESEARCH_AUDIT_MAX_MEDIUM_SEVERITY:
                            should_fix = True
                            med_count += 1
                        elif highest_severity == "Low" and low_count < config.RESEARCH_AUDIT_MAX_LOW_SEVERITY:
                            should_fix = True
                            low_count += 1
                            
                        if should_fix:
                            sections_to_rewrite.append((sec_title, sec_issues))

                    if sections_to_rewrite:
                        yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Surgeon correcting {len(sections_to_rewrite)} section(s)...', 'icon': '🔧'})}\n\n"
                    
                        for section_title, sec_issues in sections_to_rewrite:
                            # Format issues for prompt
                            issues_text = "\n".join([f"- [{i.get('severity', 'Low')}] {i.get('type', 'Unknown')}: {i.get('description', '')}" for i in sec_issues])
                            
                            surgeon_prompt = RESEARCH_SURGEON_PROMPT.format(
                                section_title=section_title,
                                issues_list=issues_text,
                                reasoning_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_AUDIT
                            )
                            
                            auditor_messages_base = list(auditor_messages)
                            surgeon_success = False
                            patched_section = ""

                            for attempt in range(config.RESEARCH_SURGEON_MAX_RETRIES): # 0: Initial, 1+: Warning/Retry
                                surgeon_messages = list(auditor_messages_base)
                                if attempt == 1:
                                    # Stage 1: Warning & Self-Correction
                                    surgeon_messages.append({"role": "user", "content": surgeon_prompt})
                                    surgeon_messages.append({"role": "assistant", "content": patched_section})
                                    surgeon_messages.append({
                                        "role": "user", 
                                        "content": "Your previous fix meandered or was invalid. Please be extremely concise. Output ONLY the corrected markdown section immediately."
                                    })
                                else:
                                    surgeon_messages.append({"role": "user", "content": surgeon_prompt})

                                surgeon_payload = {
                                    "model": model,
                                    "messages": surgeon_messages,
                                    "temperature": config.RESEARCH_TEMPERATURE_AUDIT if attempt == 0 else config.RESEARCH_TEMPERATURE_RETRY_FALLBACK,
                                    "max_tokens": config.RESEARCH_MAX_TOKENS_AUDIT,
                                }

                                yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Fixing: {section_title[:30]} (Attempt {attempt+1})...', 'icon': '✂️'})}\n\n"
                                
                                patched_section = ""
                                surgeon_meandered = False
                                gen = _stream_research_call(
                                    api_url, surgeon_payload, display_model, "status",
                                    thought_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_AUDIT,
                                    content_threshold=config.RESEARCH_MEANDER_CONTENT_THRESHOLD,
                                    api_key=api_key
                                )
                                async for packet in gen:
                                    if packet["type"] == "activity":
                                        yield packet["data"]
                                    elif packet["type"] == "result":
                                        patched_section = packet["data"]
                                        surgeon_meandered = packet.get("meandered", False)

                                # Stream-level meander detection is the single source of truth
                                if surgeon_meandered:
                                    continue
                                
                                # Validate actual content exists after stripping reasoning
                                if _strip_thinking(patched_section).strip():
                                    surgeon_success = True
                                    break

                            if not surgeon_success:
                                # Stage 2: Poison Prevention & Structured Fallback (Clean Context)
                                yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Surgeon meanders persistent for {section_title[:20]}. Structured fallback...', 'icon': '🛡️'})}\n\n"
                                
                                surgeon_structured_prompt = RESEARCH_SURGEON_STRUCTURED_PROMPT.format(
                                    section_title=section_title,
                                    issues_list=issues_text
                                )
                                
                                structured_payload = {
                                    "model": model,
                                    "messages": auditor_messages_base + [{"role": "user", "content": surgeon_structured_prompt}],
                                    "temperature": config.RESEARCH_TEMPERATURE_RETRY_FALLBACK,
                                    "response_format": {
                                        "type": "json_schema",
                                        "json_schema": {
                                            "name": "section_patch",
                                            "strict": True,
                                            "schema": {
                                                "type": "object",
                                                "properties": {
                                                    "patched_markdown": {"type": "string"}
                                                },
                                                "required": ["patched_markdown"],
                                                "additionalProperties": False
                                            }
                                        }
                                    }
                                }
                                
                                raw_response = ""
                                gen = _stream_research_call(
                                    api_url, structured_payload, display_model, "status",
                                    thought_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_AUDIT,
                                    content_threshold=config.RESEARCH_MEANDER_CONTENT_THRESHOLD,
                                    api_key=api_key
                                )
                                async for packet in gen:
                                    if packet["type"] == "activity":
                                        yield packet["data"]
                                    elif packet["type"] == "result":
                                        raw_response = packet["data"]
                                        
                                parsed = _extract_json_from_text(raw_response)
                                if parsed and isinstance(parsed, dict) and "patched_markdown" in parsed:
                                    patched_section = parsed["patched_markdown"]
                                else:
                                    patched_section = raw_response or ""

                            # Strip reasoning from patched section for storage
                            clean_patch = _strip_thinking(patched_section) if patched_section else ""
                            
                            if clean_patch.strip():
                                auditor_messages.append({"role": "user", "content": surgeon_prompt})
                                auditor_messages.append({"role": "assistant", "content": clean_patch})
                                
                                # Robust matching to apply the patch back to valid_summaries
                                clean_input_title = section_title.lstrip('#').strip().lower()
                                found = False
                                for s in valid_summaries:
                                    heading_lower = s['heading'].strip().lower()
                                    if heading_lower == clean_input_title or s['heading'] == section_title:
                                        s['section_text'] = clean_patch
                                        found = True
                                        break
                                    if (len(heading_lower) > 10 and heading_lower in clean_input_title) or (len(clean_input_title) > 10 and clean_input_title in heading_lower):
                                        s['section_text'] = clean_patch
                                        found = True
                                        break
                                
                                if not found:
                                    log_event("research_audit_patch_failed_to_match", {"chat_id": chat_id, "title": section_title})

                    # Re-stitch after patches
                    full_report = f"# {report_title}\n\n" + "\n\n".join([s['section_text'] for s in valid_summaries])
                else:
                    yield f"data: {_create_activity_chunk(display_model, 'status', {'message': 'No issues found — report is consistent.', 'icon': '✅'})}\n\n"

            # TURN 2: Synthesis (Comparative Analysis & Key Takeaways)
            yield f"data: {_create_activity_chunk(display_model, 'status', {'message': 'Generating synthesis sections...', 'icon': '🧩'})}\n\n"

            synthesis_prompt = RESEARCH_SYNTHESIS_PROMPT.format(
                reasoning_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_SYNTHESIS
            )

            auditor_messages.append({"role": "user", "content": synthesis_prompt})

            synthesis_payload = {
                "model": model,
                "messages": auditor_messages,
                "temperature": config.RESEARCH_TEMPERATURE_SYNTHESIS,
                "max_tokens": config.RESEARCH_MAX_TOKENS_SYNTHESIS,
            }

            raw_synthesis = ""
            gen = _stream_research_call(
                api_url, synthesis_payload, display_model, "status",
                thought_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_SYNTHESIS,
                content_threshold=config.RESEARCH_MEANDER_CONTENT_THRESHOLD,
                api_key=api_key
            )
            async for packet in gen:
                if packet["type"] == "activity":
                    yield packet["data"]
                elif packet["type"] == "result":
                    raw_synthesis = packet["data"]
            
            synthesis = _extract_json_from_text(raw_synthesis) if raw_synthesis else None

            if synthesis and isinstance(synthesis, dict):
                comp_analysis = synthesis.get("comparative_analysis", "")
                key_takeaways = synthesis.get("key_takeaways", "")
                if comp_analysis:
                    if not comp_analysis.strip().startswith("#"):
                        full_report += "\n\n## Comparative Analysis & Nuances\n\n" + comp_analysis
                    else:
                        full_report += "\n\n" + comp_analysis
                if key_takeaways:
                    if not key_takeaways.strip().startswith("#"):
                        full_report += "\n\n## Key Takeaways\n\n" + key_takeaways
                    else:
                        full_report += "\n\n" + key_takeaways
            else:
                yield f"data: {_create_activity_chunk(display_model, 'status', {'message': 'Synthesis generation failed. Proceeding without.', 'icon': '⚠️'})}\n\n"

        # --- 3.4 Mechanical citation normalization ---
        yield f"data: {_create_activity_chunk(display_model, 'status', {'message': 'Normalizing citations and generating references...', 'icon': '📚'})}\n\n"
        full_report, references_list = _normalize_citations(full_report, source_registry)

        # --- 3.5 Final image stripping (post-audit) ---
        full_report = _strip_report_images(full_report)

        # --- 3.6 Append References section ---
        if references_list:
            full_report += "\n\n## References\n" + "\n".join(references_list)
        else:
            full_report += "\n\n## References\nNo external citations were used in this report.\n"

        # --- 3.7 Stream final report ---
        yield f"data: {_create_activity_chunk(display_model, 'phase', {'message': 'Report complete!', 'icon': '✅'})}\n\n"
        yield f"data: {create_chunk(display_model, content=f'<final_report>{full_report}</final_report>')}\n\n"

        log_event("research_complete", {
            "chat_id": chat_id,
            "sections": len(valid_summaries),
            "sources": len(source_registry),
            "references": len(references_list)
        })

        from backend.storage import update_chat_research_state
        update_chat_research_state(chat_id, 'completed')

    except Exception as e:
        import traceback
        traceback.print_exc()
        log_event("research_report_generation_fatal_error", {"chat_id": chat_id, "error": str(e)})
        yield f"data: {_create_activity_chunk(display_model, 'needs_retry', {'state': 'assembly', 'message': f'Report assembly failed: {str(e)}'})}\n\n"

    yield "data: [DONE]\n\n"

