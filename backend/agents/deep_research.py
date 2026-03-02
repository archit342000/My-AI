import json
import asyncio
import re
import urllib.parse
import base64
import html
from backend.logger import log_event
from bs4 import BeautifulSoup
import httpx
import markdownify
from backend.prompts import (
    DEEP_RESEARCH_SCOUT_PROMPT,
    DEEP_RESEARCH_PLANNER_PROMPT,
    DEEP_RESEARCH_REFLECTION_PROMPT,
    DEEP_RESEARCH_RETRIEVAL_QUERY_PROMPT,
    DEEP_RESEARCH_REPORTER_PROMPT,
    DEEP_RESEARCH_VISION_PROMPT
)
from backend.tools import GET_TIME_TOOL
from backend.utils import (
    create_chunk, visit_page, estimate_tokens, validate_research_plan,
    get_domain, check_url_safety, execute_tavily_search,
    get_current_time, async_tavily_search, async_tavily_map,
    async_tavily_extract, async_chat_completion, is_safe_web_url
)
from backend.llm import stream_chat_completion, chat_completion
from backend.agents.chat import _stream_and_accumulate
from backend.rag import DeepResearchRAG
from backend.validation import (
    validate_output_format, parse_fixes, find_fix_locations, apply_fixes,
    build_fix_messages, build_regeneration_messages
)
from backend import config

# --- Configuration ---
MAX_PLAN_RETRIES = 2
MAX_FOLLOW_UP_SEARCHES = 2  # Max follow-up gap-filling searches per step


def _extract_json_from_text(text):
    """
    Robustly extracts the first JSON object from a string.
    Useful for background tasks (like ranking) where the model might
    prefix output with a <think> block or other commentary.
    """
    if not text:
        return None
    # First, try to parse the whole thing (fastest path)
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    # Try to find a JSON object or array
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        start = text.find(start_char)
        if start == -1:
            continue
        depth = 0
        for i in range(start, len(text)):
            if text[i] == start_char: depth += 1
            elif text[i] == end_char: depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i+1])
                except json.JSONDecodeError:
                    break
    return None


async def _fetch_and_encode_image(url):
    if not is_safe_web_url(url):
        return None
    try:
        current_url = url
        resp = None
        async with httpx.AsyncClient(timeout=config.TIMEOUT_IMAGE_FETCH, follow_redirects=False) as client:
            for _ in range(5):
                resp = await client.get(current_url)
                if resp.status_code in (301, 302, 303, 307, 308):
                    next_url = resp.headers.get('Location')
                    if not next_url:
                        break
                    next_url = urllib.parse.urljoin(current_url, next_url)
                    if not is_safe_web_url(next_url):
                        return None
                    current_url = next_url
                else:
                    break
                    
            if not resp:
                return None
            resp.raise_for_status()
            mime = resp.headers.get('content-type', 'image/jpeg').split(';')[0].strip()
            b64 = base64.b64encode(resp.content).decode('utf-8')
            return f"data:{mime};base64,{b64}"
    except:
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
                    "__deep_research_activity__": True,
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
    if len(text) < 15:
        return "Analyzing and structuring research approach..."
    # Take last 120 chars for a readable trailing snippet
    if len(text) > 120:
        text = text[-120:]
        # Try to start at a word boundary
        first_space = text.find(' ')
        if first_space != -1 and first_space < 30:
            text = text[first_space + 1:]
    return text


# =====================================================================
# HELPER FUNCTIONS: URL Selection, Extraction, Vision, Reflection
# =====================================================================

def _select_top_urls(results, n=4):
    """Deterministic URL selection: sort by Tavily score, pick top N with domain diversity.
    No LLM call needed — replaces the old AI-based URL ranking."""
    if not results:
        return []
    
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


async def _extract_pdf_content(pdf_bytes):
    """Extract text from PDF bytes using pymupdf (fitz). Returns markdown-formatted text."""
    try:
        import fitz  # pymupdf
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages = []
        for page in doc:
            text = page.get_text("text")
            if text.strip():
                pages.append(text.strip())
        doc.close()
        return "\n\n---\n\n".join(pages) if pages else None
    except ImportError:
        print("[DeepResearch] pymupdf not installed. Skipping PDF extraction.")
        return None
    except Exception as e:
        print(f"[DeepResearch] PDF extraction error: {e}")
        return None


async def _process_images_in_content(content, url, vision_model, api_url, vlm_lock):
    """Extract and describe images found in markdown content using a vision model.
    Returns the content with image descriptions appended."""
    if not vision_model or not content:
        return content
    
    # Detect image URLs in markdownified text: ![alt text](https://example.com/img.jpg)
    img_matches = re.findall(r'!\[([^\]]*)\]\((https?://[^\)]+)\)', content)
    
    valid_images = []
    for alt, img_url in img_matches:
        # Sanitize URL
        img_url = html.unescape(img_url).split('#')[0].strip()
        parsed_path = urllib.parse.urlparse(img_url).path.lower()
        if parsed_path.endswith(('.png', '.jpg', '.jpeg', '.webp')) and 'icon' not in img_url.lower() and 'logo' not in img_url.lower():
            if len(valid_images) < 2:  # Cap at 2 images per page
                valid_images.append((alt, img_url))
    
    if not valid_images:
        return content
    
    descriptions = []
    for alt, img_url in valid_images:
        try:
            base64_img = await _fetch_and_encode_image(img_url)
            if not base64_img:
                continue
            
            payload = {
                "model": vision_model,
                "messages": [
                    {"role": "system", "content": DEEP_RESEARCH_VISION_PROMPT.format(url=url, alt=alt or "Untitled")},
                    {"role": "user", "content": [{"type": "image_url", "image_url": {"url": base64_img}}]}
                ],
                "max_tokens": 2048,
                "temperature": 0.1
            }
            
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    if vlm_lock:
                        async with vlm_lock:
                            img_desc = await async_chat_completion(api_url, payload)
                    else:
                        img_desc = await async_chat_completion(api_url, payload)
                    
                    if img_desc and len(img_desc) > 50:
                        c_match = re.search(r'<caption_for_report>(.*?)</caption_for_report>', img_desc, re.DOTALL)
                        d_match = re.search(r'<detailed_description>(.*?)</detailed_description>', img_desc, re.DOTALL)
                        
                        ai_caption = c_match.group(1).strip() if c_match else (alt or 'Extracted Visual Data')
                        ai_detail = d_match.group(1).strip() if d_match else img_desc.strip()
                        
                        triplet_block = (
                            f"\n\n### [IMAGE DETECTED]\n"
                            f"**Original Title**: {alt or 'Untitled'}\n"
                            f"**AI Generated Caption**: {ai_caption}\n"
                            f"**URL**: {img_url}\n"
                            f"**Vision Model Detailed Description**: {ai_detail}\n"
                        )
                        descriptions.append(triplet_block)
                    break
                except Exception:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
        except Exception:
            pass
    
    if descriptions:
        content += "\n\n" + "\n".join(descriptions)
    
    return content


async def _extract_content_for_url(url, search_depth_mode, vision_model, api_url, vlm_lock, raw_content_from_search=None):
    """Extract content from a single URL based on the search depth mode.
    
    Regular mode: Uses raw_content from Tavily search results directly.
    Deep mode: httpx GET → Tavily Extract fallback → pymupdf for PDFs.
    Both modes: Vision processing for inline images (deep mode only since regular uses text).
    
    Returns: (url, content_string) or (url, None) on failure.
    """
    if search_depth_mode == 'regular':
        # Regular mode: use raw_content from search results (already available)
        if raw_content_from_search and len(raw_content_from_search.strip()) > 50:
            return url, raw_content_from_search
        return url, None
    
    # ===== DEEP MODE EXTRACTION =====
    is_pdf = urllib.parse.urlparse(url).path.lower().endswith('.pdf')
    
    # Strategy 1: Direct HTTP GET
    content = None
    try:
        async with httpx.AsyncClient(timeout=config.TIMEOUT_WEB_SCRAPE, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                content_type = resp.headers.get('content-type', '').lower()
                
                if is_pdf or 'application/pdf' in content_type:
                    # PDF: try pymupdf first
                    content = await _extract_pdf_content(resp.content)
                    if content and len(content.strip()) > 100:
                        return url, content
                    # pymupdf failed, will try Tavily Extract below
                    content = None
                else:
                    # HTML: markdownify
                    md = markdownify.markdownify(resp.text)
                    if md and len(md.strip()) > 500:
                        # Vision processing for inline images (deep mode only)
                        if vision_model:
                            md = await _process_images_in_content(md, url, vision_model, api_url, vlm_lock)
                        return url, md
    except Exception:
        pass
    
    # Strategy 2: Tavily Extract fallback (handles JS-rendered pages and some PDFs)
    try:
        tavily_results = await async_tavily_extract([url])
        for tr in tavily_results:
            if tr.get('raw_content') and len(tr['raw_content'].strip()) > 100:
                return url, tr['raw_content']
    except Exception:
        pass
    
    return url, None


async def _process_tavily_search_images(images, step_index, vision_model, api_url, vlm_lock):
    """Process images from Tavily search results using vision model.
    Returns list of (triplet_block_text, img_url, step_index) tuples."""
    if not vision_model or not images:
        return []
    
    valid_images = []
    for img_url in images:
        if isinstance(img_url, dict):
            img_url = img_url.get("url", "")
        if isinstance(img_url, str):
            parsed_path = urllib.parse.urlparse(img_url).path.lower()
            if parsed_path.endswith(('.png', '.jpg', '.jpeg', '.webp')) and 'icon' not in img_url.lower() and 'logo' not in img_url.lower():
                if len(valid_images) < 2:
                    valid_images.append(img_url)
    
    results = []
    for img_url in valid_images:
        try:
            base64_img = await _fetch_and_encode_image(img_url)
            if not base64_img:
                continue
            
            payload = {
                "model": vision_model,
                "messages": [
                    {"role": "system", "content": DEEP_RESEARCH_VISION_PROMPT.format(url="Search Engine Results", alt="Contextual search image")},
                    {"role": "user", "content": [{"type": "image_url", "image_url": {"url": base64_img}}]}
                ],
                "max_tokens": 2048,
                "temperature": 0.1
            }
            
            for attempt in range(3):
                try:
                    if vlm_lock:
                        async with vlm_lock:
                            img_desc = await async_chat_completion(api_url, payload)
                    else:
                        img_desc = await async_chat_completion(api_url, payload)
                    
                    if img_desc and len(img_desc) > 50:
                        c_match = re.search(r'<caption_for_report>(.*?)</caption_for_report>', img_desc, re.DOTALL)
                        d_match = re.search(r'<detailed_description>(.*?)</detailed_description>', img_desc, re.DOTALL)
                        
                        ai_caption = c_match.group(1).strip() if c_match else 'Contextual search image'
                        ai_detail = d_match.group(1).strip() if d_match else img_desc.strip()
                        
                        triplet_block = (
                            f"\n\n### [IMAGE DETECTED]\n"
                            f"**Original Title**: Search Result Embedded Image\n"
                            f"**AI Generated Caption**: {ai_caption}\n"
                            f"**URL**: {img_url}\n"
                            f"**Vision Model Detailed Description**: {ai_detail}\n"
                        )
                        results.append((triplet_block, img_url, step_index))
                    break
                except Exception:
                    if attempt < 2:
                        await asyncio.sleep(2 ** attempt)
        except Exception:
            pass
    
    return results


async def _reflect_on_step(api_url, model, step_goal, step_description, step_query,
                           extracted_content, accumulated_summaries, step_index,
                           search_depth_mode, vision_model, vlm_lock, rag_engine, chat_id,
                           display_model):
    """Manages the multi-round reflection conversation for a single step.
    
    Round 1: Feed initial content → LLM finds gaps → outputs JSON
    Round 2 (if gaps): Execute follow-up searches → extract → feed again → updated JSON
    
    Returns: (summary_str, plan_modification_or_none, follow_up_content_buffer, activity_chunks)
    """
    activity_chunks = []  # SSE chunks to yield to UI
    follow_up_buffer = []  # Additional content from gap-filling
    
    # Format accumulated summaries for the prompt
    if accumulated_summaries:
        summaries_text = "\n".join([
            f"### Step {s['step']+1}: {s['goal']}\n{s['summary']}"
            for s in accumulated_summaries
        ])
    else:
        summaries_text = "No prior steps completed yet. This is the first step."
    
    # Build reflection system prompt
    reflection_prompt = DEEP_RESEARCH_REFLECTION_PROMPT.format(
        step_goal=step_goal,
        step_description=step_description,
        step_query=step_query,
        accumulated_summaries=summaries_text
    )
    
    # Format extracted content for the LLM
    content_text = ""
    for item in extracted_content:
        content_text += f"\n\n---\n[Source: {item['url']}]\n{item['content'][:15000]}\n"
    
    if not content_text.strip():
        content_text = "No content was successfully extracted for this step."
    
    # Reflection conversation
    messages = [
        {"role": "system", "content": reflection_prompt},
        {"role": "user", "content": f"Here is the extracted content from the initial search for step {step_index+1}:\n\n{content_text}"}
    ]
    
    activity_chunks.append(f"data: {_create_activity_chunk(display_model, 'reflection', {'message': f'Analyzing findings for step {step_index+1}...', 'step_id': step_index})}\n\n")
    
    reflection_payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
    }
    
    raw_response = await async_chat_completion(api_url, reflection_payload)
    reflection = _extract_json_from_text(raw_response) if raw_response else None
    
    if not reflection or not isinstance(reflection, dict):
        # Fallback: no structured reflection, return generic summary
        return "• Content was extracted but reflection analysis failed.", None, [], activity_chunks
    
    gaps = reflection.get("gaps", [])
    summary = reflection.get("summary", "• No summary available.")
    plan_mod = reflection.get("plan_modification")
    
    # If there are gaps, do follow-up searches (max MAX_FOLLOW_UP_SEARCHES)
    if gaps and len(gaps) > 0:
        follow_up_queries = [g["query"] for g in gaps[:MAX_FOLLOW_UP_SEARCHES] if g.get("query")]
        
        if follow_up_queries:
            activity_chunks.append(f"data: {_create_activity_chunk(display_model, 'follow_up_search', {'message': f'Filling {len(follow_up_queries)} gap(s) found in step {step_index+1}...', 'step_id': step_index, 'queries': follow_up_queries})}\n\n")
            
            follow_up_content_text = ""
            for fq in follow_up_queries:
                # Search
                fu_results, _ = await async_tavily_search(fq, max_results=10)
                fu_results = [r for r in fu_results if r.get('raw_content') or r.get('content')]
                
                if fu_results:
                    # Select top 2 from follow-up
                    fu_selected = _select_top_urls(fu_results, n=2)
                    
                    for fu_r in fu_selected:
                        fu_url = fu_r.get('url', '')
                        fu_content_result = None
                        
                        if search_depth_mode == 'regular':
                            fu_content_result = fu_r.get('raw_content', fu_r.get('content', ''))
                        else:
                            _, fu_content_result = await _extract_content_for_url(
                                fu_url, search_depth_mode, vision_model, api_url, vlm_lock,
                                raw_content_from_search=fu_r.get('raw_content')
                            )
                        
                        if fu_content_result and len(fu_content_result.strip()) > 50:
                            follow_up_buffer.append({"url": fu_url, "content": fu_content_result})
                            follow_up_content_text += f"\n\n---\n[Source: {fu_url}]\n{fu_content_result[:15000]}\n"
            
            # Round 2: Feed follow-up content back to reflection
            if follow_up_content_text.strip():
                messages.append({"role": "assistant", "content": raw_response})
                messages.append({"role": "user", "content": f"Here is the additional content gathered to fill the identified gaps:\n\n{follow_up_content_text}"})
                
                reflection_payload["messages"] = messages
                raw_response_2 = await async_chat_completion(api_url, reflection_payload)
                reflection_2 = _extract_json_from_text(raw_response_2) if raw_response_2 else None
                
                if reflection_2 and isinstance(reflection_2, dict):
                    summary = reflection_2.get("summary", summary)
                    plan_mod = reflection_2.get("plan_modification", plan_mod)
    
    activity_chunks.append(f"data: {_create_activity_chunk(display_model, 'reflection', {'message': f'Step {step_index+1} analysis complete.', 'step_id': step_index})}\n\n")
    
    return summary, plan_mod, follow_up_buffer, activity_chunks


async def _generate_retrieval_queries(api_url, model, user_query, step_goals_summaries):
    """Phase 2.5: Generate interconnected cross-step retrieval queries."""
    summaries_text = "\n".join([
        f"### Step {s['step']+1}: {s['goal']}\n{s['summary']}"
        for s in step_goals_summaries
    ])
    
    prompt = DEEP_RESEARCH_RETRIEVAL_QUERY_PROMPT.format(
        user_query=user_query,
        step_summaries=summaries_text
    )
    
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": prompt}],
        "temperature": 0.3,
    }
    
    raw = await async_chat_completion(api_url, payload)
    queries = _extract_json_from_text(raw) if raw else None
    
    if queries and isinstance(queries, list):
        return [q for q in queries if isinstance(q, str) and len(q.strip()) > 5]
    return []


# =====================================================================
# MAIN PIPELINE
# =====================================================================

async def generate_deep_research_response(api_url, model, messages, approved_plan=None, chat_id=None, search_depth_mode='regular', vision_model=None, model_name=None, resume_state=None):
    """
    Main Deep Research Pipeline
    
    Phase 0: Context Scout (pre-planning analysis)
    Phase 1: Planning (structured research plan generation)
    Phase 2: Sequential Step Execution (search → select → extract → reflect)
    Phase 2.5: Retrieval Planning (interconnected queries)
    Phase 3: Report Generation (with validation & healing)
    """
    display_model = model_name or model
    log_event("deep_research_start", {"chat_id": chat_id, "mode": 'execution' if approved_plan else 'planning', "model": model, "vision_model": vision_model})

    # ===== PARSE PLAN IF EXECUTING =====
    steps = []
    if approved_plan:
        try:
            xml_content = approved_plan.strip()
            if not xml_content.startswith("<research_plan>"):
                xml_content = f"<research_plan>\n{xml_content}\n</research_plan>"
                
            plan_root = BeautifulSoup(xml_content, 'html.parser')
            steps = plan_root.find_all('step')
        except Exception as e:
            yield f"data: {create_chunk(model, content=f'**Error parsing XML plan:** {str(e)}')}\n\n"
            yield "data: [DONE]\n\n"
            return

        if not steps:
            yield f"data: {create_chunk(model, content='**Plan has zero steps.**')}\n\n"
            yield "data: [DONE]\n\n"
            return
            
    n_steps = len(steps)
    if not resume_state:
        if not approved_plan:
            current_time = get_current_time()
            conversation_history = [m for m in messages if m['role'] != 'system']

            # ===== PHASE 0: CONTEXT SCOUT =====
            yield f"data: {_create_activity_chunk(display_model, 'planning', {'message': 'Analyzing your research query...', 'state': 'thinking'})}\n\n"

            scout_prompt = DEEP_RESEARCH_SCOUT_PROMPT.format(current_time=current_time)
            scout_messages = [{"role": "system", "content": scout_prompt}]
            scout_messages.extend(conversation_history[-5:])

            scout_payload = {
                "model": model,
                "messages": scout_messages,
                "temperature": 0.1,
            }

            scout_analysis = None
            scout_context_str = ""
            preliminary_search_results = ""

            try:
                raw_scout = await async_chat_completion(api_url, scout_payload)
                if raw_scout:
                    scout_analysis = _extract_json_from_text(raw_scout)

                if scout_analysis and isinstance(scout_analysis, dict):
                    log_event("deep_research_scout_complete", {
                        "chat_id": chat_id,
                        "topic_type": scout_analysis.get("topic_type"),
                        "time_sensitive": scout_analysis.get("time_sensitive"),
                        "confidence": scout_analysis.get("confidence"),
                        "needs_search": scout_analysis.get("needs_search")
                    })

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

                            prelim_results, _ = await async_tavily_search(
                                prelim_query, 
                                topic=prelim_topic, 
                                time_range=prelim_time_range
                            )

                            if prelim_results:
                                context_snippets = []
                                for r in prelim_results[:5]:
                                    title = r.get('title', 'Untitled')
                                    snippet = r.get('content', '')
                                    url = r.get('url', '')
                                    context_snippets.append(f"- **{title}** ({url}): {snippet}")
                                preliminary_search_results = "\n".join(context_snippets)

                                yield f"data: {_create_activity_chunk(display_model, 'planning', {'message': f'Gathered context from {len(prelim_results[:5])} sources.', 'state': 'thinking'})}\n\n"
                            else:
                                yield f"data: {_create_activity_chunk(display_model, 'planning', {'message': 'Preliminary search returned no results. Proceeding to planning...', 'state': 'thinking'})}\n\n"

                    scout_context_parts = []
                    scout_context_parts.append(f"## Context Analysis (from pre-planning scout)")
                    scout_context_parts.append(f"- **Topic Type:** {scout_analysis.get('topic_type', 'general')}")
                    scout_context_parts.append(f"- **Time-Sensitive:** {scout_analysis.get('time_sensitive', False)}")
                    scout_context_parts.append(f"- **Confidence Level:** {scout_analysis.get('confidence', 'unknown')}")
                    if scout_analysis.get('context_notes'):
                        scout_context_parts.append(f"- **Analysis Notes:** {scout_analysis['context_notes']}")
                    if preliminary_search_results:
                        scout_context_parts.append(f"\n### Preliminary Search Results (use these to inform your plan)")
                        scout_context_parts.append(preliminary_search_results)
                    scout_context_str = "\n".join(scout_context_parts)
                else:
                    log_event("deep_research_scout_failed", {"chat_id": chat_id, "raw_output": raw_scout[:200] if raw_scout else "empty"})
                    scout_context_str = "## Context Analysis\nScout analysis was not available. Proceed with general planning based on the user query alone."
            except Exception as e:
                log_event("deep_research_scout_error", {"chat_id": chat_id, "error": str(e)})
                scout_context_str = "## Context Analysis\nScout analysis encountered an error. Proceed with general planning based on the user query alone."

            # ===== PHASE 1: PLANNING =====
            system_prompt = DEEP_RESEARCH_PLANNER_PROMPT.format(
                current_time=current_time,
                scout_context=scout_context_str
            )
            messages_to_send = [{"role": "system", "content": system_prompt}]
            messages_to_send.extend(conversation_history[-10:])

            payload = {
                "model": model,
                "messages": messages_to_send,
                "stream": True,
                "temperature": 0.4,
                "top_p": 0.9,
                "max_tokens": 16384,
            }

            yield f"data: {_create_activity_chunk(display_model, 'planning', {'message': 'Designing research strategy...', 'state': 'thinking'})}\n\n"

            for attempt in range(1, MAX_PLAN_RETRIES + 1):
                payload["messages"] = list(messages_to_send)
                full_content = "<think>\n"
                full_reasoning = ""
                reasoning_token_count = 0

                for chunk_str in stream_chat_completion(api_url, payload):
                    try:
                        if not chunk_str.startswith("data: "): continue
                        chunk = json.loads(chunk_str[6:])
                        choices = chunk.get('choices', [])
                        if not choices: continue
                        delta = choices[0].get('delta', {})

                        content = delta.get('content', '')
                        reasoning = delta.get('reasoning_content', '') or delta.get('reasoning', '')

                        if content:
                            full_content += content
                            if "<think>" in full_content and "</think>" not in full_content:
                                reasoning_token_count += 1
                                if reasoning_token_count % 40 == 0:
                                    raw_snippet = full_content.replace('<think>', '').strip()
                                    snippet = _clean_thinking_snippet(raw_snippet)
                                    yield f"data: {_create_activity_chunk(display_model, 'planning', {'message': f'...{snippet}', 'state': 'thinking'})}\n\n"

                        if reasoning:
                            full_reasoning += reasoning
                            reasoning_token_count += 1
                            if reasoning_token_count % 40 == 0:
                                snippet = _clean_thinking_snippet(full_reasoning)
                                yield f"data: {_create_activity_chunk(display_model, 'planning', {'message': f'...{snippet}', 'state': 'thinking'})}\n\n"
                    except Exception as e:
                        pass

                if "<think>" in full_content and "</think>" not in full_content:
                    full_content = full_content.replace("<think>\n", "", 1).replace("<think>", "", 1)

                plan_source = full_content
                if not plan_source or '<research_plan>' not in plan_source:
                    if full_reasoning and '<research_plan>' in full_reasoning:
                        plan_source = full_reasoning

                if not plan_source or not plan_source.strip():
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
                    if attempt < MAX_PLAN_RETRIES:
                        messages_to_send = list(messages_to_send)
                        messages_to_send.append({"role": "assistant", "content": full_content})
                        messages_to_send.append({
                            "role": "user",
                            "content": f"Your output failed validation: {error}\nPlease regenerate the research plan targeting only the XML block."
                        })

            yield f"data: {create_chunk(model, content='**I was unable to generate a valid research plan.** Please try rephrasing your research topic or simplifying the request.')}\n\n"
            yield "data: [DONE]\n\n"
            return

        # =====================================================================
        # PHASE 2: SEQUENTIAL STEP EXECUTION
        # =====================================================================

        yield f"data: {_create_activity_chunk(display_model, 'phase', {'message': 'Beginning sequential research execution...', 'icon': '🚀', 'collapsible': True})}\n\n"

        # Instantiate RAG engine (no token limit for storage)
        rag_engine = DeepResearchRAG(persist_path=config.CHROMA_PATH, api_url=api_url, embedding_model=config.EMBEDDING_MODEL)
        vlm_lock = asyncio.Lock()

        accumulated_summaries = []  # List of {"step": int, "goal": str, "summary": str}
        step_goals_list = []  # For retrieval planning

        # Extract original user query for later use
        original_query = "Automated Deep Research Task"
        for m in messages:
            if m['role'] == 'user':
                content = m.get('content', '')
                if isinstance(content, list):
                    content = next((p.get('text', '') for p in content if p.get('type') == 'text'), '')
                if isinstance(content, str) and '<research_plan>' not in content:
                    original_query = content

        try:
            for step_idx, step_node in enumerate(steps):
                # --- Parse step XML ---
                goal_tag = step_node.find('goal')
                goal = goal_tag.get_text(strip=True) if goal_tag else 'Unknown Goal'
                desc_tag = step_node.find('description')
                description = desc_tag.get_text(strip=True) if desc_tag else ''
                query_tag = step_node.find('query')
                query = query_tag.get_text(strip=True) if query_tag else ''

                # Extract optional per-step search parameters
                topic_tag = step_node.find('topic')
                step_topic = topic_tag.get_text(strip=True) if topic_tag else 'general'
                time_range_tag = step_node.find('time_range')
                step_time_range = time_range_tag.get_text(strip=True) if time_range_tag else None
                start_date_tag = step_node.find('start_date')
                step_start_date = start_date_tag.get_text(strip=True) if start_date_tag else None
                end_date_tag = step_node.find('end_date')
                step_end_date = end_date_tag.get_text(strip=True) if end_date_tag else None

                # Check for plan modifications from previous step's reflection
                if accumulated_summaries: 
                    last_summary = accumulated_summaries[-1]
                    if last_summary.get('plan_modification'):
                        pm = last_summary['plan_modification']
                        if pm.get('step_index') == step_idx and pm.get('new_query'):
                            log_event("deep_research_plan_modified", {
                                "chat_id": chat_id,
                                "step_index": step_idx,
                                "original_query": query,
                                "new_query": pm['new_query'],
                                "reason": pm.get('reason', 'N/A')
                            })
                            query = pm['new_query']
                            yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Step {step_idx+1} query modified: {query}', 'icon': '🔄'})}\n\n"

                step_goals_list.append({"index": step_idx, "goal": goal})

                yield f"data: {_create_activity_chunk(display_model, 'phase', {'message': f'Step {step_idx+1}/{n_steps}: {goal}', 'icon': '📋', 'collapsible': True})}\n\n"

                # --- 1. SEARCH (20 results, per-step params) ---
                yield f"data: {_create_activity_chunk(display_model, 'search', {'query': query, 'step_id': step_idx, 'displayMessage': 'Searching...'})}\n\n"

                results, search_images = await async_tavily_search(
                    query,
                    topic=step_topic,
                    time_range=step_time_range,
                    start_date=step_start_date,
                    end_date=step_end_date,
                    max_results=20
                )

                # Pre-filter: remove results without content
                results = [r for r in results if r.get('raw_content') or r.get('content')]

                if not results:
                    yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'No results found for step {step_idx+1}. Skipping.', 'icon': '⚠️'})}\n\n"
                    accumulated_summaries.append({
                        "step": step_idx, "goal": goal,
                        "summary": "• No search results found for this step."
                    })
                    continue

                # Send search results to UI
                filtered_results = [{'title': r.get('title'), 'url': r.get('url'), 'snippet': r.get('content')} for r in results]
                yield f"data: {_create_activity_chunk(display_model, 'search_results', {'results': filtered_results, 'step_id': step_idx})}\n\n"

                # --- 2. SELECT (deterministic: top 4, domain diversity) ---
                selected = _select_top_urls(results, n=4)
                yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Selected {len(selected)} sources from {len(results)} results.', 'step_id': step_idx, 'icon': '🎯'})}\n\n"

                # --- 3. EXTRACT (mode-dependent) ---
                step_content_buffer = []  # In-memory buffer: [{"url": str, "content": str}]

                for sel_result in selected:
                    sel_url = sel_result.get('url', '')
                    yield f"data: {_create_activity_chunk(display_model, 'visit', {'url': sel_url})}\n\n"

                    _, extracted = await _extract_content_for_url(
                        sel_url, search_depth_mode, vision_model, api_url, vlm_lock,
                        raw_content_from_search=sel_result.get('raw_content')
                    )

                    if extracted and len(extracted.strip()) > 50:
                        step_content_buffer.append({"url": sel_url, "content": extracted})
                        yield f"data: {_create_activity_chunk(display_model, 'visit_complete', {'url': sel_url, 'chars': len(extracted)})}\n\n"
                    else:
                        yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Failed to extract content from {sel_url[:40]}...', 'icon': '⚠️'})}\n\n"

                # --- 3b. DEEP MODE: Map top 4 URLs for sub-pages ---
                if search_depth_mode == 'deep':
                    for sel_result in selected:
                        sel_url = sel_result.get('url', '')
                        yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Deep mapping: {sel_url[:40]}...', 'step_id': step_idx, 'icon': '🗺️'})}\n\n"

                        sub_mapped = await async_tavily_map(sel_url, instruction=f"Researching: {goal}. Find deep data pages.")
                        if sub_mapped:
                            # Extract content from mapped sub-URLs (limit to avoid explosion)
                            for mapped_url in sub_mapped[:5]:  # Max 5 sub-pages per mapped URL
                                if isinstance(mapped_url, dict):
                                    mapped_url = mapped_url.get('url', '')
                                if not mapped_url or mapped_url in [item['url'] for item in step_content_buffer]:
                                    continue

                                _, mapped_content = await _extract_content_for_url(
                                    mapped_url, search_depth_mode, vision_model, api_url, vlm_lock
                                )

                                if mapped_content and len(mapped_content.strip()) > 100:
                                    step_content_buffer.append({"url": mapped_url, "content": mapped_content})
                                    yield f"data: {_create_activity_chunk(display_model, 'visit_complete', {'url': mapped_url, 'chars': len(mapped_content)})}\n\n"

                # --- 3c. Process Tavily search images (vision, both modes) ---
                if vision_model and search_images:
                    image_results = await _process_tavily_search_images(
                        search_images, step_idx, vision_model, api_url, vlm_lock
                    )
                    for triplet_block, img_url, _ in image_results:
                        step_content_buffer.append({"url": img_url, "content": triplet_block})

                # --- 4. BATCH STORE in RAG (no token limit) ---
                for item in step_content_buffer:
                    rag_engine.store_chunk(chat_id, step_idx, item['url'], item['content'])

                yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Stored {len(step_content_buffer)} content items for step {step_idx+1}.', 'icon': '💾'})}\n\n"

                # --- 5. REFLECT (LLM conversation with gap-filling) ---
                summary, plan_mod, follow_up_content, reflection_activities = await _reflect_on_step(
                    api_url, model, goal, description, query,
                    step_content_buffer, accumulated_summaries, step_idx,
                    search_depth_mode, vision_model, vlm_lock, rag_engine, chat_id,
                    display_model
                )

                # Yield reflection activity chunks
                for chunk in reflection_activities:
                    yield chunk

                # Store follow-up content in RAG too
                for fu_item in follow_up_content:
                    rag_engine.store_chunk(chat_id, step_idx, fu_item['url'], fu_item['content'])

                # --- 6. ACCUMULATE summary ---
                accumulated_summaries.append({
                    "step": step_idx,
                    "goal": goal,
                    "summary": summary,
                    "plan_modification": plan_mod
                })

                yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Step {step_idx+1}/{n_steps} complete.', 'icon': '✅'})}\n\n"

        except Exception as e:
            yield f"data: {create_chunk(model, content=f'**Error during sequential execution phase:** {str(e)}')}\n\n"
            yield "data: [DONE]\n\n"
            return

        # =====================================================================
        # PHASE 2.5: RETRIEVAL PLANNING (Interconnected Queries)
        # =====================================================================

        yield f"data: {_create_activity_chunk(display_model, 'retrieval_planning', {'message': 'Generating retrieval strategy for report...', 'icon': '🔗'})}\n\n"

        interconnected_queries = await _generate_retrieval_queries(
            api_url, model, original_query, accumulated_summaries
        )

        log_event("deep_research_retrieval_queries", {
            "chat_id": chat_id,
            "step_queries": len(step_goals_list),
            "interconnected_queries": len(interconnected_queries),
            "queries": interconnected_queries
        })

        # Build unified query list with dynamic budget
        all_retrieval_queries = [
            *[{"query": sg["goal"], "step_filter": sg["index"]} for sg in step_goals_list],
            *[{"query": q, "step_filter": None} for q in interconnected_queries],
        ]

        yield f"data: {_create_activity_chunk(display_model, 'retrieval_planning', {'message': f'Retrieving context with {len(all_retrieval_queries)} queries ({len(step_goals_list)} step + {len(interconnected_queries)} cross-step)...', 'icon': '📚'})}\n\n"

        report_chunks = rag_engine.retrieve_for_report(chat_id, all_retrieval_queries, max_tokens=400000)

        yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Retrieved {len(report_chunks)} content chunks for report generation.', 'icon': '📊'})}\n\n"

    # =====================================================================
    # PHASE 3: MODULAR REPORT GENERATION (with validation & healing)
    # =====================================================================

    import os
    import json
    import re

    state_path = f"./backend/tasks/{chat_id}_state.json"
    resume_section_state = None
    if resume_state:
        if os.path.exists(state_path):
            try:
                with open(state_path, "r") as sf:
                    resume_section_state = json.load(sf)
            except: pass
            
        yield f"data: {_create_activity_chunk(display_model, 'status', {'message': 'Resuming from existing gathered context...', 'icon': '🔄'})}\n\n"
        # Since we skipped retrieval planning, we fetch all chunks globally
        report_chunks = rag_engine.get_all_chunks(chat_id)
        if not report_chunks:
            yield f"data: {_create_activity_chunk(display_model, 'status', {'message': 'Error: Missing context chunks for resumption.', 'icon': '❌'})}\n\n"
            yield "data: [DONE]\n\n"
            return
            
    global_processed_images = set()
    if resume_section_state:
        global_processed_images = set(resume_section_state.get('global_processed_images', []))
    else:
        # Build global processed images from report_chunks
        for c in report_chunks:
            text = c.get('text', '')
            imgs = re.findall(r'!\[.*?\]\((https?://.*?)\)', text)
            for img in imgs: global_processed_images.add(img.strip())
            
    yield f"data: {_create_activity_chunk(display_model, 'phase', {'message': f'Compiling final report ({search_depth_mode} mode)...', 'icon': '📝'})}\n\n"
    
    # 3.1 Pre-format chunks for prompts
    chunk_previews = []
    chunk_dict = {}
    for idx, c in enumerate(report_chunks):
        cid = idx + 1
        chunk_dict[cid] = c
        snippet = c.get('text', '')[:150].replace('\n', ' ') + "..."
        source_url = c.get('url', 'Unknown')
        chunk_previews.append(f"[{cid}] [Source: {source_url}] {snippet}")
    chunk_previews_str = "\n".join(chunk_previews)
    
    mode_guidance = "DEEP mode: Massive comprehensiveness required. Generate 10+ body sections." if search_depth_mode == 'deep' else "REGULAR mode: 4-8 body sections."

    # --- 3.2 Generate or Load Outline ---
    outline = None
    if resume_section_state and resume_section_state.get("sections"):
        outline = {
            "title": resume_section_state.get("title", "Research Report"),
            "sections": resume_section_state.get("sections", [])
        }
    else:
        yield f"data: {_create_activity_chunk(display_model, 'status', {'message': 'Planning report structure...', 'icon': '📐'})}\n\n"
        
        outline_prompt = DEEP_RESEARCH_OUTLINE_PROMPT.format(
            user_query=original_query,
            approved_plan=approved_plan or "Auto-generated implicitly",
            mode_guidance=mode_guidance,
            chunk_previews=chunk_previews_str
        )
        
        # 2-Strike Outline Retry
        for attempt in range(2):
            if attempt == 0:
                outline_payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": outline_prompt},
                        {"role": "user", "content": "Generate the report outline now based on the data previews above."}
                    ],
                    "temperature": 0.3, "max_tokens": 16384, "stream": True
                }
                raw_outline = ""
                full_reasoning = ""
                rt_count = 0
                for chunk_str in stream_chat_completion(api_url, outline_payload):
                    try:
                        if not chunk_str.startswith("data: "): continue
                        chunk = json.loads(chunk_str[6:])
                        if not chunk.get('choices'): continue
                        delta = chunk['choices'][0].get('delta', {})
                        content = delta.get('content', '')
                        reasoning = delta.get('reasoning_content') or delta.get('reasoning', '')
                        if content: raw_outline += content
                        if reasoning:
                            full_reasoning += reasoning
                            rt_count += 1
                            if rt_count % 40 == 0:
                                snippet = _clean_thinking_snippet(full_reasoning)
                                yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Structuring Report: {snippet}...', 'icon': '📐'})}\n\n"
                    except: pass
                outline = _extract_json_from_text(raw_outline) if raw_outline else None
            else:
                yield f"data: {_create_activity_chunk(display_model, 'status', {'message': 'Outline invalid. Using strict JSON fallback...', 'icon': '🔄'})}\n\n"
                
                from backend.llm_client import async_chat_completion
                fallback_payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": outline_prompt + "\n\nCRITICAL ERROR: DO NOT use <think>. Output ONLY valid JSON."},
                        {"role": "user", "content": "Generate the report outline now based on the data previews above."}
                    ],
                    "temperature": 0.3, "max_tokens": 16384,
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "outline_fallback", "strict": True,
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "sections": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "title": {"type": "string"},
                                                "type": {"type": "string"},
                                                "description": {"type": "string"},
                                                "chunk_ids": {"type": "array", "items": {"type": "integer"}}
                                            },
                                            "required": ["title", "type", "description", "chunk_ids"], "additionalProperties": False
                                        }
                                    }
                                },
                                "required": ["title", "sections"], "additionalProperties": False
                            }
                        }
                    }
                }
                raw_fb = await async_chat_completion(api_url, fallback_payload)
                try: outline = json.loads(raw_fb)
                except:
                    match = re.search(r'(\{[\s\S]*"sections"[\s\S]*\})', raw_fb or "")
                    if match:
                        try: outline = json.loads(match.group(1))
                        except: pass
                        
            if outline and isinstance(outline, dict) and 'sections' in outline:
                break
                
        if not outline or not isinstance(outline, dict) or 'sections' not in outline:
            yield f"data: {_create_activity_chunk(display_model, 'needs_retry', {'state': 'outline', 'message': 'Outline Generation FAILED permanently. Click resume to try again.'})}\n\n"
            yield "data: [DONE]\n\n"
            return
            
    report_title = outline.get('title', 'Research Report')
    sections = outline.get('sections', [])
    
    if not resume_section_state:
        yield f"data: {create_chunk(display_model, content=f'# {report_title}\n\n')}\n\n"
        
    running_summaries = resume_section_state.get('running_summaries', []) if resume_section_state else []
    used_citations = set(resume_section_state.get('used_citations', [])) if resume_section_state else set()
    full_report_text = resume_section_state.get('full_report_text', f"# {report_title}\n\n") if resume_section_state else f"# {report_title}\n\n"
    used_image_chunk_ids = set(resume_section_state.get('used_image_chunk_ids', [])) if resume_section_state else set()
    last_completed_idx = resume_section_state.get('last_completed_idx', -1) if resume_section_state else -1
    
    section_instructions = {
        "mandatory": "This is the Executive Summary. Synthesize the core high-level points. Do not get bogged down in deep specifics here.",
        "body": "This is a body section. Go extremely deep into the facts, data, and details. Maximize information density.",
        "comparison": "This section MUST explicitly compare and contrast different viewpoints, technologies, methods, or entities found in the data.",
        "nuances": "Highlight counter-arguments, edge-cases, missing data, caveats, contradictions, and weaknesses in the research.",
        "takeaways": "Write 3-7 bullet points of ultimate, synthesized takeaways. No new data here, just synthesis.",
        "references": ""
    }
    
    # --- 3.3 Section-by-section generation ---
    for sec_idx, section in enumerate(sections):
        if sec_idx <= last_completed_idx:
            yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Skipping completed section: {section.get("title")}', 'icon': '⏭️'})}\n\n"
            continue
            
        sec_title = section.get('title', f'Section {sec_idx+1}')
        sec_desc = section.get('description', '')
        sec_type = section.get('type', 'body')
        sec_chunk_ids = section.get('chunk_ids', [])
        
        if sec_type == 'references':
            yield f"data: {_create_activity_chunk(display_model, 'status', {'message': 'Generating references...', 'icon': '📚'})}\n\n"
            ref_text = "\n\n## References\n"
            sorted_citations = sorted(list(used_citations))
            if not sorted_citations:
                ref_text += "No external citations were used in this report.\n"
            else:
                for cid in sorted_citations:
                    if cid in chunk_dict:
                        url = chunk_dict[cid].get('url', 'Unknown Source')
                        ref_text += f"{cid}. [Source Link]({url})\n"
            yield f"data: {create_chunk(display_model, content=ref_text)}\\n\\n"
            yield "data: [DONE]\n\n"
            return
            
        yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Writing section: {sec_title}...', 'icon': '✍️'})}\n\n"
        
        if not sec_chunk_ids and sec_type not in ['takeaways', 'exec_summary']:
            # Assign top 5 globally if none assigned
            sec_chunk_ids = list(chunk_dict.keys())[:5]
            
        section_chunks_text = ""
        chunk_lookup = set()
        for cid in sec_chunk_ids:
            if cid in chunk_dict:
                chunk_lookup.add(cid)
                c = chunk_dict[cid]
                text = c.get('text', '')
                
                # Image dedup
                imgs = re.findall(r'!\[.*?\]\((https?://.*?)\)', text)
                for img in imgs:
                    if img in used_image_chunk_ids:
                        text = re.sub(r'!\[.*?\]\(' + re.escape(img) + r'\)', '', text)
                    else:
                        used_image_chunk_ids.add(img)
                
                source_url = c.get('url', 'Unknown')
                section_chunks_text += f"\n<chunk id=\"{cid}\" source=\"{source_url}\">\n{text}\n</chunk>\n"
                
        if not section_chunks_text.strip() and sec_type != 'takeaways':
            section_chunks_text = "No specific chunk data assigned. Synthesize from available context."
            
        summaries_text = "\n".join([f"## {s['title']}\n{s['summary']}" for s in running_summaries])
        specific_instruction = section_instructions.get(sec_type, "")
        
        section_prompt = DEEP_RESEARCH_SECTION_WRITER_PROMPT.format(
            section_title=sec_title, section_description=sec_desc, section_type=sec_type,
            running_summaries=summaries_text, user_query=original_query, mode_guidance=mode_guidance,
            section_chunks=section_chunks_text, section_specific_instruction=specific_instruction
        )
        
        clean_content = ""
        success = False
        
        for attempt in range(2):
            try:
                if attempt == 0:
                    section_payload = {
                        "model": model,
                        "messages": [
                            {"role": "system", "content": section_prompt},
                            {"role": "user", "content": f"Write the '{sec_title}' section now."}
                        ],
                        "stream": True, "temperature": 0.4, "top_p": 0.9, "max_tokens": 16384
                    }
                    section_content = ""
                    for sse_chunk, final_state in _stream_and_accumulate(api_url, model, section_payload):
                        if final_state is not None:
                            section_content, *_ = final_state
                        elif sse_chunk is not None:
                            yield sse_chunk
                            
                    clean_content = section_content
                    if "<think>" in clean_content:
                        clean_content = re.sub(r'<think>.*?</think>', '', clean_content, flags=re.DOTALL).strip()
                    if "</think>" in clean_content:
                        clean_content = clean_content.split("</think>")[-1].strip()
                else:
                    yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Recovering section {sec_idx+1} (Timeout/Empty/Invalid)...', 'icon': '🔄'})}\n\n"
                    from backend.llm_client import async_chat_completion
                    fallback_payload = {
                        "model": model,
                        "messages": [
                            {"role": "system", "content": section_prompt + "\n\nCRITICAL ERROR AVOIDANCE: Your previous attempt failed validation. DO NOT use `<think>`. Output ONLY valid JSON."},
                            {"role": "user", "content": f"Write the '{sec_title}' section now."}
                        ],
                        "temperature": 0.3, "max_tokens": 16384,
                        "response_format": {
                            "type": "json_schema",
                            "json_schema": {
                                "name": "section_fallback", "strict": True,
                                "schema": {
                                    "type": "object",
                                    "properties": {"section_markdown": {"type": "string"}},
                                    "required": ["section_markdown"], "additionalProperties": False
                                }
                            }
                        }
                    }
                    raw_fb = await async_chat_completion(api_url, fallback_payload)
                    try:
                        fb_json = json.loads(raw_fb)
                        if "section_markdown" in fb_json: clean_content = fb_json["section_markdown"]
                    except:
                        match = re.search(r'(\{[\s\S]*"section_markdown"[\s\S]*\})', raw_fb or "")
                        if match:
                            try:
                                fb_json = json.loads(match.group(1))
                                clean_content = fb_json.get("section_markdown", clean_content)
                            except: pass
                    yield f"data: {create_chunk(display_model, content=clean_content)}\n\n"
                            
                # Post-processing & Validation
                for ref_header in ['\n## References', '\n### References', '\n## Sources', '\n### Sources']:
                    if ref_header in clean_content:
                        clean_content = clean_content.split(ref_header)[0]
                        
                if len(clean_content.strip()) < 100:
                    raise Exception("Section too short / empty.")
                    
                embedded_images = [url.strip() for url in re.findall(r'!\[.*?\]\((https?://.*?)\)', clean_content)]
                if any(img not in global_processed_images for img in embedded_images):
                    raise Exception("Output contains hallucinated images not provided by the context.")
                    
                cited_ids = re.findall(r'\[(\d+)\]', clean_content)
                if any(int(cid) not in chunk_lookup for cid in cited_ids if cid.isdigit() and sec_type not in ['takeaways', 'exec_summary']):
                    raise Exception("Output contains invalid citations.")
                
                success = True
                break
            except Exception as e:
                log_event("deep_research_section_validation_error", {"chat_id": chat_id, "section": sec_title, "error": str(e), "attempt": attempt})

        if not success:
            yield f"data: {_create_activity_chunk(display_model, 'needs_retry', {'state': 'section', 'message': f'Section {sec_idx+1} Generation FAILED. Click resume to try again.'})}\n\n"
            state = {
                "title": outline.get("title", ""), "sections": outline.get("sections", []),
                "running_summaries": running_summaries, "used_citations": list(used_citations),
                "full_report_text": full_report_text, "used_image_chunk_ids": list(used_image_chunk_ids),
                "last_completed_idx": sec_idx - 1, "global_processed_images": list(global_processed_images)
            }
            with open(state_path, "w") as f: json.dump(state, f)
            yield "data: [DONE]\n\n"
            return
            
        summary_text = clean_content
        if summary_text.startswith('#'): summary_text = summary_text.split('\n', 1)[-1] if '\n' in summary_text else summary_text
        summary_text = summary_text.strip()[:500]
        if len(summary_text) == 500:
            last_period = summary_text.rfind('.')
            if last_period > 200: summary_text = summary_text[:last_period + 1]
        
        running_summaries.append({"title": sec_title, "summary": summary_text})
        for cid_str in re.findall(r'\[(\d+)\]', clean_content):
            try: used_citations.add(int(cid_str))
            except: pass
            
        yield f"data: {create_chunk(display_model, content='\n\n')}\n\n"
        full_report_text += "\n\n" + clean_content
        
        # Save state
        state = {
            "title": outline.get("title", ""), "sections": outline.get("sections", []),
            "running_summaries": running_summaries, "used_citations": list(used_citations),
            "full_report_text": full_report_text, "used_image_chunk_ids": list(used_image_chunk_ids),
            "last_completed_idx": sec_idx, "global_processed_images": list(global_processed_images)
        }
        with open(state_path, "w") as f: json.dump(state, f)

    yield "data: [DONE]\n\n"
