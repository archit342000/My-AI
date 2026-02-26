import json
import asyncio
import re
import urllib.parse
import base64
from backend.logger import log_event
import xml.etree.ElementTree as ET
import httpx
import markdownify
from backend.prompts import (
    DEEP_RESEARCH_PLANNER_PROMPT, 
    DEEP_RESEARCH_URL_SELECTION_PROMPT, 
    DEEP_RESEARCH_REPORTER_PROMPT,
    DEEP_RESEARCH_VISION_PROMPT
)
from backend.tools import GET_TIME_TOOL
from backend.utils import (
    create_chunk, visit_page, estimate_tokens, validate_research_plan, 
    get_domain, check_url_safety, execute_tavily_search, 
    get_current_time, async_tavily_search, async_tavily_map, 
    async_tavily_extract, async_chat_completion
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


def _extract_json_from_text(text):
    """
    Robustly extracts the first JSON object from a string.
    Useful for background tasks (like ranking) where the model might
    prefix output with a <think> block or other commentary.
    """
    if not text: return None
    try:
        # Try direct parse first
        return json.loads(text.strip())
    except:
        # Look for { ... }
        match = re.search(r'(\{.*\})', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
    return None


async def _fetch_and_encode_image(url):
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_IMAGE_FETCH) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            mime = resp.headers.get('content-type', 'image/jpeg')
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


async def _process_step(api_url, model, chat_id, step_node, step_index, search_depth_mode, queue=None):
    """
    Handles a single step: Search -> Rank -> (Map if Deep)
    """
    goal = step_node.findtext('goal', 'Unknown Goal')
    description = step_node.findtext('description', '')
    query = step_node.findtext('query', '')
    
    if queue:
        queue.put_nowait(f"data: {_create_activity_chunk(model, 'search', {'query': query, 'step_id': step_index, 'displayMessage': 'Searching...'})}\n\n")

    # 1. Search (Always 1 search per step)
    results, images = await async_tavily_search(query)
    
    # Pre-filtering: remove empty raw_content
    results = [r for r in results if r.get('raw_content')]
    if not results:
        return [], [], images
    
    if queue:
        # Send all results back to UI
        filtered_results = [{'title': r.get('title'), 'url': r.get('url'), 'snippet': r.get('content')} for r in results]
        queue.put_nowait(f"data: {_create_activity_chunk(model, 'search_results', {'results': filtered_results, 'step_id': step_index})}\n\n")
        queue.put_nowait(f"data: {_create_activity_chunk(model, 'status', {'message': 'Evaluating sources...', 'step_id': step_index, 'icon': '🧠'})}\n\n")
        
    # 2. Rank via AI
    search_results_str = ""
    for idx, r in enumerate(results):
        search_results_str += f"<result id=\"{idx}\">\n  <title>{r.get('title', 'Untitled')}</title>\n  <url>{r.get('url', '')}</url>\n  <snippet>{r.get('content', '')}</snippet>\n</result>\n"

    rank_prompt = DEEP_RESEARCH_URL_SELECTION_PROMPT.format(
        goal=goal,
        description=description,
        search_results=search_results_str
    )
    
    rank_payload = {
        "model": model,
        "messages": [{"role": "system", "content": rank_prompt}],
        "temperature": 0.1,
    }
    
    ranked_urls_json = await async_chat_completion(api_url, rank_payload)
    ranked_urls = _extract_json_from_text(ranked_urls_json)
    
    if not ranked_urls or not isinstance(ranked_urls, list):
        # Fallback to score order
        ranked_urls = [r.get('url') for r in sorted(results, key=lambda x: x.get('score', 0), reverse=True)]

    # 3. Regular vs Deep split
    if search_depth_mode == 'regular':
        # Just pick top 4. Store raw_content for these immediately.
        top_4_urls = ranked_urls[:4]
        final_data_to_store = []
        for url in top_4_urls:
            res = next((r for r in results if r.get('url') == url), None)
            if res:
                final_data_to_store.append({"url": url, "raw_content": res['raw_content'], "step_index": step_index})
        return [], final_data_to_store, images

    else:
        # Deep Mode: Map top 4. 
        # instructions for mapping by AI? Or just use goal.
        map_urls = ranked_urls[:4]
        mapped_urls_all = []
        
        # We need 4 successful mappings
        success_count = 0
        tried_indices = 0
        
        while success_count < 4 and tried_indices < len(ranked_urls):
            target_url = ranked_urls[tried_indices]
            if queue:
                queue.put_nowait(f"data: {_create_activity_chunk(model, 'status', {'message': f'Deep mapping: {target_url[:30]}...', 'step_id': step_index, 'icon': '🗺️'})}\n\n")
            sub_mapped = await async_tavily_map(target_url, instruction=f"Researching: {goal}. Find deep data pages.")
            if sub_mapped:
                mapped_urls_all.extend(sub_mapped)
                success_count += 1
            tried_indices += 1
            
        # The URLs to explore are the mapped ones. 
        return mapped_urls_all, [], images

async def generate_deep_research_response(api_url, model, messages, approved_plan=None, chat_id=None, search_depth_mode='regular', vision_model=None):
    """
    Main n+1 Pass Pipeline
    """
    log_event("deep_research_start", {"chat_id": chat_id, "mode": 'execution' if approved_plan else 'planning', "model": model, "vision_model": vision_model})

    # ===== PARSE PLAN IF EXECUTING =====
    steps = []
    if approved_plan:
        try:
            xml_content = approved_plan.strip()
            if not xml_content.startswith("<research_plan>"):
                xml_content = f"<research_plan>\n{xml_content}\n</research_plan>"
                
            plan_root = ET.fromstring(xml_content)
            steps = plan_root.findall('step')
        except Exception as e:
            yield f"data: {create_chunk(model, content=f'**Error parsing XML plan:** {str(e)}')}\n\n"
            yield "data: [DONE]\n\n"
            return

        if not steps:
            yield f"data: {create_chunk(model, content='**Plan has zero steps.**')}\n\n"
            yield "data: [DONE]\n\n"
            return
            
    n_steps = len(steps)
    if not approved_plan:
        system_prompt = DEEP_RESEARCH_PLANNER_PROMPT
        messages_to_send = [{"role": "system", "content": system_prompt}]
        conversation_history = [m for m in messages if m['role'] != 'system']
        messages_to_send.extend(conversation_history[-10:])
        
        payload = {
            "model": model,
            "messages": messages_to_send,
            "stream": True,
            "temperature": 0.4,
            "top_p": 0.9,
            "max_tokens": 16384,
        }
        
        yield f"data: {_create_activity_chunk(model, 'planning', {'message': 'Analyzing your query and designing a research strategy...', 'state': 'thinking'})}\n\n"

        for attempt in range(1, MAX_PLAN_RETRIES + 1):
            payload["messages"] = list(messages_to_send)
            # Prefix <think>\n to match the .jinja template's prefilled generation prompt.
            # Since reasoning is template-enforced (not native), LM Studio sends ALL tokens
            # (reasoning + </think> + content) through delta.content.
            # This prefix reconstructs the complete <think>...</think> block for parsing.
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
                    # Also handle native reasoning_content for models that support it natively
                    reasoning = delta.get('reasoning_content', '') or delta.get('reasoning', '')

                    if content:
                        full_content += content
                        # While inside the <think> block (not yet closed), show thinking snippets
                        if "<think>" in full_content and "</think>" not in full_content:
                            reasoning_token_count += 1
                            if reasoning_token_count % 40 == 0:
                                snippet = full_content.replace('<think>', '').replace('\n', ' ').strip()[-150:]
                                yield f"data: {_create_activity_chunk(model, 'planning', {'message': f'...{snippet}', 'state': 'thinking'})}\n\n"
                                
                    if reasoning:
                        full_reasoning += reasoning
                        reasoning_token_count += 1
                        if reasoning_token_count % 40 == 0:
                            snippet = full_reasoning[-150:].replace('\n', ' ').strip()
                            yield f"data: {_create_activity_chunk(model, 'planning', {'message': f'...{snippet}', 'state': 'thinking'})}\n\n"
                except Exception as e:
                    pass

            # If the model never closed the think tag (skipped reasoning entirely),
            # strip the artificially prepended <think> to avoid polluting plan extraction
            if "<think>" in full_content and "</think>" not in full_content:
                full_content = full_content.replace("<think>\n", "", 1).replace("<think>", "", 1)
            
            plan_source = full_content
            if not plan_source or '<research_plan>' not in plan_source:
                if full_reasoning and '<research_plan>' in full_reasoning:
                    plan_source = full_reasoning

            if not plan_source or not plan_source.strip():
                yield f"data: {_create_activity_chunk(model, 'planning', {'message': f'Attempt {attempt}: No output received. Retrying...', 'state': 'warning'})}\n\n"
                continue

            yield f"data: {_create_activity_chunk(model, 'planning', {'message': 'Validating research plan structure...', 'state': 'validating'})}\n\n"

            clean_xml, error = validate_research_plan(plan_source)

            if clean_xml:
                yield f"data: {_create_activity_chunk(model, 'planning', {'message': 'Plan generated successfully!', 'state': 'complete'})}\n\n"
                yield f"data: {create_chunk(model, content=clean_xml)}\n\n"
                yield "data: [DONE]\n\n"
                return
            else:
                yield f"data: {_create_activity_chunk(model, 'planning', {'message': f'Validation issue: {error}. Refining plan...', 'state': 'warning'})}\n\n"
                if attempt < MAX_PLAN_RETRIES:
                    # Create a fresh copy to avoid mutation issues across retries
                    messages_to_send = list(messages_to_send)
                    messages_to_send.append({"role": "assistant", "content": full_content})
                    messages_to_send.append({
                        "role": "user",
                        "content": f"Your output failed validation: {error}\nPlease regenerate the research plan targeting only the XML block."
                    })

        yield f"data: {create_chunk(model, content='**I was unable to generate a valid research plan.** Please try rephrasing your research topic or simplifying the request.')}\n\n"
        yield "data: [DONE]\n\n"
        return

    # ===== PASS N EXECUTION PHASE (PARALLEL SEARCH & MAPPING) =====
    
    yield f"data: {_create_activity_chunk(model, 'phase', {'message': 'Initiating web searches...', 'icon': '🚀', 'collapsible': True})}\n\n"

    try:
        # Create asynchronous tasks for each step, use an asyncio Queue to stream updates
        ui_queue = asyncio.Queue()
        all_tasks = []
        for i, step_node in enumerate(steps):
            t = _process_step(api_url, model, chat_id, step_node, i, search_depth_mode, ui_queue)
            all_tasks.append(asyncio.create_task(t))
        
        # Async generator natively embedded: wait for all while yielding from queue
        active_tasks = list(all_tasks)
        
        while active_tasks:
            done, pending = await asyncio.wait(active_tasks, return_when=asyncio.FIRST_COMPLETED, timeout=0.1)
            while not ui_queue.empty():
                yield ui_queue.get_nowait()
            active_tasks = list(pending)
            
        # Final drain of queue after all tasks finish
        while not ui_queue.empty():
            yield ui_queue.get_nowait()

        # Collect results from completed tasks (already finished via asyncio.wait above)
        results_of_all_steps = [t.result() for t in all_tasks]
    except Exception as e:
        yield f"data: {create_chunk(model, content=f'**Error during parallel search phase:** {str(e)}')}\n\n"
        yield "data: [DONE]\n\n"
        return

    # Deduplication across all steps
    all_urls_to_extract = []  # List of (url, step_index) tuples
    seen_urls = set()
    
    # We also keep data that doesn't need extraction (Regular mode top 4 raw_content)
    manual_data_to_store = []
    tavily_images_to_process = []
    
    for step_idx, (mapped_urls, data_to_store, images) in enumerate(results_of_all_steps):
        for url in mapped_urls:
            if url not in seen_urls:
                all_urls_to_extract.append((url, step_idx))
                seen_urls.add(url)
        for d in data_to_store:
            if d['url'] not in seen_urls:
                 manual_data_to_store.append(d)
                 seen_urls.add(d['url'])
                 
        valid_t_images = []
        for img_url in images:
            if isinstance(img_url, dict):
                img_url = img_url.get("url", "")
            if isinstance(img_url, str):
                parsed_path = urllib.parse.urlparse(img_url).path.lower()
                if parsed_path.endswith(('.png', '.jpg', '.jpeg', '.webp')) and 'icon' not in img_url.lower() and 'logo' not in img_url.lower():
                    if len(valid_t_images) < 2:
                        valid_t_images.append(img_url)
        for img_url in valid_t_images:
            if img_url not in [i["url"] for i in tavily_images_to_process]:
                tavily_images_to_process.append({"url": img_url, "step_index": step_idx})

    # Instantiate Ephemeral Vector Store
    rag_engine = DeepResearchRAG(persist_path=config.CHROMA_PATH, api_url=api_url, embedding_model=config.EMBEDDING_MODEL)
    total_tokens_stored = 0
    TOKEN_LIMIT = 400000

    # ===== EXTRACTION PHASE =====
    if search_depth_mode == 'regular':
        yield f"data: {_create_activity_chunk(model, 'phase', {'message': f'Extracting content from {len(manual_data_to_store)} sources...', 'icon': '🧹', 'collapsible': True})}\n\n"
        for d in manual_data_to_store:
            yield f"data: {_create_activity_chunk(model, 'visit', {'url': d['url']})}\n\n"
            success, tok_count = rag_engine.store_chunk(chat_id, d.get('step_index', 0), d['url'], d['raw_content'])
            if success: 
                total_tokens_stored += tok_count
                yield f"data: {_create_activity_chunk(model, 'visit_complete', {'url': d['url'], 'chars': len(d['raw_content'])})}\n\n"
    else:
        # Deep Mode Extraction Loop
        yield f"data: {_create_activity_chunk(model, 'phase', {'message': f'Extracting content from {len(all_urls_to_extract)} sources...', 'icon': '⛏️', 'collapsible': True})}\n\n"
        
        # 1. Parallel requests for all URLs
        # Actually, let's process in batches for UI feedback
        batch_size = 5
        for i in range(0, len(all_urls_to_extract), batch_size):
            if total_tokens_stored >= TOKEN_LIMIT: break
            
            batch = all_urls_to_extract[i:i+batch_size]  # List of (url, step_idx) tuples
            batch_urls = [url for url, _ in batch]
            url_to_step = {url: step_idx for url, step_idx in batch}
            yield f"data: {_create_activity_chunk(model, 'status', {'message': f'Extracting batch {i//batch_size + 1}...', 'icon': '📥'})}\n\n"
            
            # Step 1: Try async standard GET for the whole batch using a shared client
            async def try_extract(client, url):
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        md = markdownify.markdownify(resp.text)
                        
                        # --- VISION EXTRACTION PHASE ---
                        if vision_model:
                            import re
                            # Detect raw absolute Image URLs from the markdownified text
                            # e.g., ![alt text](https://example.com/img.jpg)
                            img_matches = re.findall(r'!\[([^\]]*)\]\((https?://[^\)]+)\)', md)
                            
                            valid_images = []
                            for alt, img_url in img_matches:
                                # Prioritize likely genuine photos/diagrams
                                parsed_path = urllib.parse.urlparse(img_url).path.lower()
                                if parsed_path.endswith(('.png', '.jpg', '.jpeg', '.webp')) and 'icon' not in img_url.lower() and 'logo' not in img_url.lower():
                                    if len(valid_images) < 2:  # Cap at 2 high-quality images per page to save massive tokens
                                        valid_images.append((alt, img_url))
                                        
                            if valid_images:
                                descriptions = []
                                for alt, img_url in valid_images:
                                    try:
                                        base64_img = await _fetch_and_encode_image(img_url)
                                        if not base64_img: continue

                                        payload = {
                                            "model": vision_model,
                                            "messages": [
                                                {
                                                    "role": "system",
                                                    "content": DEEP_RESEARCH_VISION_PROMPT.format(url=url, alt=alt or "Untitled")
                                                },
                                                {
                                                    "role": "user",
                                                    "content": [
                                                        {"type": "image_url", "image_url": {"url": base64_img}}
                                                    ]
                                                }
                                            ],
                                            "max_tokens": 2048,
                                            "temperature": 0.1
                                        }
                                        max_retries = 3
                                        for attempt in range(max_retries):
                                            try:
                                                img_desc = await async_chat_completion(api_url, payload)
                                                if img_desc and len(img_desc) > 50:
                                                    # Parse the XML structure
                                                    c_match = re.search(r'<caption_for_report>(.*?)</caption_for_report>', img_desc, re.DOTALL)
                                                    d_match = re.search(r'<detailed_description>(.*?)</detailed_description>', img_desc, re.DOTALL)
                                                    
                                                    ai_caption = c_match.group(1).strip() if c_match else (alt or 'Extracted Visual Data')
                                                    ai_detail = d_match.group(1).strip() if d_match else img_desc.strip()
        
                                                    # Create the block that the reporter will see natively appended to the document
                                                    triplet_block = (
                                                        f"\n\n### [IMAGE DETECTED]\n"
                                                        f"**Original Title**: {alt or 'Untitled'}\n"
                                                        f"**AI Generated Caption**: {ai_caption}\n"
                                                        f"**URL**: {img_url}\n"
                                                        f"**Vision Model Detailed Description**: {ai_detail}\n"
                                                    )
                                                    descriptions.append(triplet_block)
                                                break
                                            except Exception as e:
                                                if attempt < max_retries - 1:
                                                    await asyncio.sleep(2 ** attempt)
                                                else:
                                                    raise
                                                    
                                    except Exception as e:
                                        pass
                                        
                                if descriptions:
                                    md += "\n\n" + "\n".join(descriptions)
                                    
                        return url, md
                    return url, None
                except Exception as e:
                    return url, None

            async with httpx.AsyncClient(timeout=TIMEOUT_WEB_SCRAPE, follow_redirects=True) as client:
                batch_results = await asyncio.gather(*[try_extract(client, u) for u in batch_urls])
            
            # Step 2: Handle successes and collect failures for Tavily Extract
            success_urls = []
            failed_urls = []
            for url, content in batch_results:
                if content and len(content.strip()) > 500: # Heuristic for success
                    success_urls.append((url, content))
                else:
                    failed_urls.append(url)
            
            # Step 3: Use Tavily Extract for failures
            if failed_urls:
                 yield f"data: {_create_activity_chunk(model, 'status', {'message': f'Fallback to Tavily Extract for {len(failed_urls)} URLs...', 'icon': '🔄'})}\n\n"
                 tavily_results = await async_tavily_extract(failed_urls)
                 for tr in tavily_results:
                     if tr.get('raw_content'):
                         success_urls.append((tr['url'], tr['raw_content']))

            # Step 4: Vault successes with correct step_index
            for url, content in success_urls:
                yield f"data: {_create_activity_chunk(model, 'visit', {'url': url})}\n\n"
                step_idx = url_to_step.get(url, 0)
                success, tok_count = rag_engine.store_chunk(chat_id, step_idx, url, content)
                if success: 
                    total_tokens_stored += tok_count
                    yield f"data: {_create_activity_chunk(model, 'visit_complete', {'url': url, 'chars': len(content)})}\n\n"
                
                if total_tokens_stored >= TOKEN_LIMIT:
                    yield f"data: {_create_activity_chunk(model, 'status', {'message': 'Global 400k token limit reached. Stopping extraction.', 'icon': '🛑'})}\n\n"
                    break

    # ===== SEARCH VISION PHASE =====
    if vision_model and tavily_images_to_process:
        yield f"data: {_create_activity_chunk(model, 'phase', {'message': f'Processing {len(tavily_images_to_process)} images from search engines...', 'icon': '🖼️', 'collapsible': True})}\n\n"
        
        async def process_tavily_image(client, item):
            img_url = item["url"]
            step_idx = item["step_index"]
            
            base64_img = await _fetch_and_encode_image(img_url)
            if not base64_img: return None, img_url, step_idx

            payload = {
                "model": vision_model,
                "messages": [
                    {
                        "role": "system",
                        "content": DEEP_RESEARCH_VISION_PROMPT.format(url="Search Engine Results", alt="Contextual search image")
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": base64_img}}
                        ]
                    }
                ],
                "max_tokens": 2048,
                "temperature": 0.1
            }
            max_retries = 3
            for attempt in range(max_retries):
                try:
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
                        return triplet_block, img_url, step_idx
                    break
                except Exception:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                    else:
                        pass
            return None, img_url, step_idx
            
        async with httpx.AsyncClient(timeout=TIMEOUT_WEB_SCRAPE, follow_redirects=True) as client:
            t_images_results = await asyncio.gather(*[process_tavily_image(client, img) for img in tavily_images_to_process])
            
        for result, img_url, step_idx in t_images_results:
            if result:
                success, tok_count = rag_engine.store_chunk(chat_id, step_idx, img_url, result)
                if success:
                    total_tokens_stored += tok_count
                    yield f"data: {_create_activity_chunk(model, 'visit_complete', {'url': 'Processed Search Image', 'chars': len(result)})}\n\n"

    # ===== FINAL +1 REPORT GENERATION PHASE (WITH VALIDATION) =====
    yield f"data: {_create_activity_chunk(model, 'phase', {'message': f'Compiling final report ({search_depth_mode} mode)...', 'icon': '📝'})}\n\n"
    
    # [Data fetching and prompt building... same as before]
    raw_chunks = rag_engine.get_all_chunks(chat_id)
    formatted_gathered_data = ""
    for idx, c in enumerate(raw_chunks):
        step_label = f" | Step: {c.get('step_index', 'N/A')}" if c.get('step_index') is not None else ""
        formatted_gathered_data += f"\n<chunk id=\"{idx+1}\" source=\"{c['url']}\"{step_label}>\n{c['text']}\n</chunk>\n"

    if not formatted_gathered_data.strip():
        formatted_gathered_data = "No data was successfully retrieved from the internet."

    original_query = "Automated Deep Research Task"
    for m in messages:
        if m['role'] == 'user':
            content = m.get('content', '')
            if isinstance(content, list):
                content = next((p.get('text', '') for p in content if p.get('type') == 'text'), '')
            if isinstance(content, str) and '<research_plan>' not in content:
                original_query = content

    research_mode_label = "DEEP" if search_depth_mode == 'deep' else "REGULAR"
    research_instruction = "This is a DEEP mode research. The AI MUST create a massively comprehensive, expansive, and aggressively thorough report. Break the information down into many granular sub-sections and leave no stone unturned." if search_depth_mode == 'deep' else "This is a REGULAR mode research. The AI MUST create a highly detailed and thoroughly comprehensive report with multiple distinct sections covering all aspects of the gathered data."
    
    reporter_prompt = DEEP_RESEARCH_REPORTER_PROMPT.format(
        user_query=original_query,
        approved_plan=approved_plan,
        gathered_data=formatted_gathered_data,
        research_mode_label=research_mode_label,
        research_instruction=research_instruction
    )

    messages_to_send = [
        {"role": "system", "content": reporter_prompt},
        {"role": "user", "content": "Generate the final research report now based on the gathered data provided in the system prompt."}
    ]

    reporter_payload = {
        "model": model,
        "messages": messages_to_send,
        "stream": True,
        "temperature": 0.4,
        "top_p": 0.9,
        "max_tokens": 32768
    }

    # Helper for streaming correction
    def _stream_corrected_report(fixed_content):
        CHUNK_SIZE = 100
        for i in range(0, len(fixed_content), CHUNK_SIZE):
            chunk_text = fixed_content[i:i + CHUNK_SIZE]
            yield f"data: {create_chunk(model, content=chunk_text)}\n\n"

    # Core generation loop
    full_content = ""
    for sse_chunk, final_state in _stream_and_accumulate(api_url, model, reporter_payload):
        if final_state is not None:
            full_content, _ = final_state
        elif sse_chunk is not None:
            yield sse_chunk

    # Cleanup Artificial Think Prefix
    if "<think>" in full_content and "</think>" not in full_content:
        full_content = full_content.rstrip() + "\n</think>"

    for empty_block in ("<think>\n\n</think>", "<think>\n</think>"):
        full_content = full_content.replace(empty_block, "")

    # Validation & Healing
    full_reasoning = ""
    if "<think>" in full_content:
        import re
        try:
            full_reasoning = re.search(r'<think>(.*?)</think>', full_content, re.DOTALL).group(1)
        except:
            pass

    validation_errors = validate_output_format(full_content, full_reasoning)
    if validation_errors:
        log_event("deep_research_reporter_validation_triggered", {"chat_id": chat_id, "errors": [e['code'] for e in validation_errors]})
        yield f"data: {json.dumps({'__redact__': True, 'message': 'Final report formatting issue detected. Repairing...', '__reset_accumulator__': True})}\n\n"
        
        fix_applied = False
        fix_messages = build_fix_messages(messages_to_send, full_content, validation_errors)
        fix_payload = { "model": model, "messages": fix_messages, "temperature": 0.1 }
        
        # Use synchronous chat_completion as we are in a generator that allows blocking
        fix_response = chat_completion(api_url, fix_payload)
        
        if fix_response:
            fixes = parse_fixes(fix_response)
            if fixes:
                locations = find_fix_locations(full_content, fixes)
                if locations:
                    fixed_content = apply_fixes(full_content, locations)
                    recheck = validate_output_format(fixed_content, full_reasoning)
                    if not recheck:
                        log_event("deep_research_reporter_fix_success", {"chat_id": chat_id})
                        full_content = fixed_content
                        fix_applied = True
                        for chunk in _stream_corrected_report(fixed_content):
                            yield chunk

        if not fix_applied:
            log_event("deep_research_reporter_fix_fallback", {"chat_id": chat_id, "strategy": "full_regeneration"})
            regen_messages = build_regeneration_messages(messages_to_send, validation_errors)
            regen_payload = reporter_payload.copy()
            regen_payload["messages"] = regen_messages
            
            full_content = ""
            for sse_chunk, final_state in _stream_and_accumulate(api_url, model, regen_payload):
                if final_state is not None:
                    full_content, _ = final_state
                elif sse_chunk is not None:
                    yield sse_chunk
                    
    yield "data: [DONE]\n\n"
