import json
import asyncio
import datetime
import re
import os
import urllib.parse
from backend.logger import log_event, log_tool_call, log_llm_call
from bs4 import BeautifulSoup
from backend.prompts import (
    RESEARCH_SCOUT_PROMPT,
    RESEARCH_PLANNER_PROMPT,
    RESEARCH_REFLECTION_PROMPT,
    RESEARCH_TRIAGE_PROMPT,
    RESEARCH_STEP_WRITER_PROMPT,
    RESEARCH_STEP_SUMMARY_PROMPT,
    RESEARCH_VISION_PROMPT,
    RESEARCH_DETECTIVE_PROMPT,
    RESEARCH_SURGEON_PROMPT,
    RESEARCH_SYNTHESIS_PROMPT,
)
from backend.utils import (
    create_chunk, validate_research_plan,
    get_current_time, is_safe_web_url
)
from backend.mcp_client import tavily_client, playwright_client
from backend.llm import stream_chat_completion
from backend.canvas_manager import (
    create_canvas,
    get_canvas_content,
    update_canvas_content,
    append_to_canvas,
    patch_canvas_section,
    get_chat_canvases_with_details
)
from backend.db_wrapper import db
from backend import config
from backend.agents.research_schemas import (
    SCOUT_JSON_SCHEMA,
    PLANNER_JSON_SCHEMA,
    REFLECTION_JSON_SCHEMA,
    TRIAGE_JSON_SCHEMA,
    WRITER_JSON_SCHEMA,
    SUMMARY_JSON_SCHEMA,
    DETECTIVE_JSON_SCHEMA,
    SURGEON_JSON_SCHEMA,
    SYNTHESIS_JSON_SCHEMA
)
from backend.agents.research_utils import (
    _is_transient_error,
    _get_sampling_params,
    _extract_json_from_text,
    _execute_mcp_tool,
    _stream_research_call,
    _fetch_and_encode_image,
    _create_activity_chunk,
    _clean_thinking_snippet,
    _strip_thinking,
    _select_top_urls,
    _process_images_in_content,
    _extract_content_for_url,
    _process_tavily_search_images,
    _normalize_citations,
    _strip_report_images,
    _strip_invalid_citations
)

# --- Configuration ---
# All behavior is now controlled via backend.config

# =====================================================================
# CORE RESEARCH LOOP: Section Execution & Reflection
# =====================================================================


async def _execute_section_reflection_and_write(
        api_url, model, section_heading, section_description, section_queries,
        extracted_content, accumulated_summaries, section_index,
        n_sections, original_topic, full_plan_text,
        search_depth_mode, vision_model, vlm_lock, chat_id,
        display_model, source_registry, next_source_id, mode_guidance, entity_glossary,
        image_results=None, api_key=None, vision_enabled=True):
    """Multi-turn conversation for a single research section (KV cache reuse).

    Acts as an async generator, yielding UI chunks in real-time and streaming
    the section writing turn directly to the frontend.

    Returns progress info with each step completion for partial failure recovery.
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
    today_date = datetime.date.today().strftime("%A, %B %d, %Y")
    system_prompt = RESEARCH_REFLECTION_PROMPT.format(
        original_topic=original_topic,
        section_heading=section_heading,
        section_description=section_description,
        section_queries=queries_text,
        section_number=section_index + 1,
        total_sections=n_sections,
        remaining_sections=n_sections - (section_index + 1),
        full_plan=full_plan_text,
        accumulated_summaries=summaries_text,
        max_gaps=config.RESEARCH_MAX_GAPS_PER_SECTION,
        max_queries_per_section=config.RESEARCH_MAX_QUERIES_PER_SECTION,
        today_date=today_date
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Here is the data gathered for section '{section_heading}':\n\n{content_payload}"}
    ]

    # ---- TURN 1: Gap Analysis (3-Turn Resilience) ----
    yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, 'reflection', {'message': f'Analyzing findings for section: {section_heading}...', 'step_id': section_index})}\n\n"}

    reflection_success = False
    reflection = None
    raw_response = ""

    for attempt in [1, 2, 3]:
        reflection_payload = {
            "model": model,
            "messages": messages,
            **_get_sampling_params(attempt=attempt),
            "max_tokens": config.RESEARCH_MAX_TOKENS_REFLECTION,
            "response_format": {"type": "json_schema", "json_schema": {"name": "reflection", "schema": REFLECTION_JSON_SCHEMA}}
        }

        if attempt > 1:
            status_desc = "meandering" if attempt == 2 else "failing validation"
            yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Reflection {status_desc}. Fallback mode (Attempt {attempt}/3)...', 'icon': '⚠️', 'step_id': section_index})}\n\n"}

        raw_response = ""
        meandered = False
        gen = _stream_research_call(
            api_url, reflection_payload, display_model, "reflection",
            thought_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_REFLECTION_TOKENS,
            content_threshold=config.RESEARCH_MEANDER_CONTENT_THRESHOLD_TOKENS,
            step_id=section_index,
            api_key=api_key, chat_id=chat_id, enable_thinking=(attempt == 1)
        )
        async for packet in gen:
            if packet["type"] == "activity": yield packet
            elif packet["type"] == "result":
                raw_response = packet["data"]
                meandered = packet.get("meandered", False)
        
        if meandered and attempt == 1:
            continue

        reflection = _extract_json_from_text(raw_response) if raw_response else None
        if reflection and isinstance(reflection, dict) and "gaps" in reflection:
            reflection_success = True
            break

    if not reflection_success:
        yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, 'needs_retry', {'state': 'section_execution', 'message': f'Gap analysis failed for section: {section_heading}.'})}\n\n"}
        yield "data: [DONE]\n\n"
        yield {"type": "result", "data": (None, None, None, None, next_source_id)}
        return

    gaps = reflection.get("gaps", [])
    plan_mod = reflection.get("plan_modification")

    # Yield reflection progress checkpoint (for partial recovery)
    yield {"type": "reflection_checkpoint", "data": {"reflection": reflection, "raw_response": raw_response, "plan_mod": plan_mod}}

    messages.append({"role": "assistant", "content": raw_response})

    # ---- TURN 2 (conditional): Gap-Filling ----
    if gaps:
        follow_up_queries = [g["query"] for g in gaps[:config.RESEARCH_MAX_GAPS_PER_SECTION] if g.get("query")]

        if follow_up_queries:
            yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, 'follow_up_search', {'message': f'Filling {len(follow_up_queries)} gap(s) for section: {section_heading}...', 'step_id': section_index, 'queries': follow_up_queries})}\n\n"}

            follow_up_content_text = ""
            for fq in follow_up_queries:
                mcp_res = await _execute_mcp_tool(tavily_client, "async_tavily_search_tool", {"query": fq, "max_results": config.RESEARCH_TAVILY_MAX_RESULTS_FOLLOWUP}, chat_id=chat_id)
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
                                raw_content_from_search=fu_r.get('raw_content'), api_key=api_key, chat_id=chat_id, vision_enabled=vision_enabled
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

    # ---- TURN 2.5: Information Triage (3-Turn Resilience) ----
    yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Triaging core facts for section: {section_heading}...', 'icon': '🧠'})}\n\n"}

    triage_prompt = RESEARCH_TRIAGE_PROMPT.format(
        section_heading=section_heading,
        today_date=today_date,
        accumulated_summaries=summaries_text
    )
    messages.append({"role": "user", "content": triage_prompt})
    triage_messages = messages
    triage_result = None
    raw_triage = ""

    for attempt in [1, 2, 3]:
        triage_payload = {
            "model": model,
            "messages": triage_messages,
            **_get_sampling_params(attempt=attempt),
            "max_tokens": config.RESEARCH_MAX_TOKENS_TRIAGE,
            "response_format": {"type": "json_schema", "json_schema": {"name": "triage", "schema": TRIAGE_JSON_SCHEMA}}
        }

        if attempt > 1:
            yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Triage fallback (Attempt {attempt}/3)...', 'icon': '🛡️'})}\n\n"}

        gen = _stream_research_call(
            api_url, triage_payload, display_model, "status",
            thought_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_TRIAGE_TOKENS,
            content_threshold=config.RESEARCH_MEANDER_CONTENT_THRESHOLD_TOKENS,
            api_key=api_key, chat_id=chat_id, enable_thinking=(attempt == 1)
        )
        
        raw_triage = ""
        async for packet in gen:
            if packet["type"] == "activity": yield packet
            elif packet["type"] == "result":
                raw_triage = packet["data"]
                if packet.get("meandered"):
                    raw_triage = None
                
        triage_result = _extract_json_from_text(raw_triage) if raw_triage else None
        if triage_result and isinstance(triage_result, dict) and triage_result.get("core_facts"):
            # Unique Fact Validation & Capping
            raw_facts = triage_result.get("core_facts", [])
            seen_texts = set()
            unique_valid_facts = []
            
            for f in raw_facts:
                txt = f.get('fact', '').strip().lower()
                if txt and txt not in seen_texts:
                    seen_texts.add(txt)
                    unique_valid_facts.append(f)
            
            # Reject if model repeated itself excessively or produced a suspiciously long list
            repeat_count = len(raw_facts) - len(unique_valid_facts)
            if repeat_count > 2 or len(unique_valid_facts) > config.RESEARCH_TRIAGE_MAX_FACTS + 10:
                triage_result = None
                continue
                
            # Cap the final result
            triage_result["core_facts"] = unique_valid_facts[:config.RESEARCH_TRIAGE_MAX_FACTS]
            break

    if not triage_result:
        yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, 'needs_retry', {'state': 'triaging', 'message': f'Failed to extract core facts for \"{section_heading}\".'})}\n\n"}
        return

    # Format the output for the writer
    core_facts_array = triage_result.get("core_facts", [])
    core_facts_lines = []
    for f in core_facts_array:
        fact_text = f.get('fact', '')
        sources = f.get('sources', [])
        if fact_text and sources:
            source_str = ", ".join([f"[Source {s}]" for s in sources])
            core_facts_lines.append(f"- {fact_text} {source_str}")

    if not core_facts_lines:
        yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, 'needs_retry', {'state': 'triaging', 'message': f'Extraction for \"{section_heading}\" returned no valid points.'})}\n\n"}
        return

    core_facts_str = "\n".join(core_facts_lines)

    # Yield triage progress checkpoint (for partial recovery)
    yield {"type": "triage_checkpoint", "data": {"triage_result": triage_result, "core_facts_str": core_facts_str}}

    # Show status update
    fact_count = len(core_facts_array)
    yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Extracted {fact_count} core facts for drafting.', 'icon': '📂'})}\n\n"}

    messages.append({"role": "assistant", "content": raw_triage or "{}"})

    # ---- TURN 3: Section Writing (3-Turn Resilience) ----
    yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, 'writing', {'message': f'Drafting section: {section_heading}...', 'step_id': section_index})}\n\n"}

    glossary_str = "\n".join([f"- {k}: {v}" for k, v in entity_glossary.items()]) if entity_glossary else "None yet."
    writer_prompt = RESEARCH_STEP_WRITER_PROMPT.format(
        section_heading=section_heading,
        accumulated_summaries=summaries_text,
        entity_glossary=glossary_str,
        mode_guidance=mode_guidance,
        today_date=today_date
    )
    messages.append({"role": "user", "content": writer_prompt})
    writer_messages = messages
    raw_section = ""

    for attempt in [1, 2, 3]:
        writer_payload = {
            "model": model,
            "messages": writer_messages,
            **_get_sampling_params(attempt=attempt),
            "max_tokens": config.RESEARCH_MAX_TOKENS_STEP_WRITER,
            "response_format": {"type": "json_schema", "json_schema": {"name": "section_draft", "schema": WRITER_JSON_SCHEMA}}
        }

        if attempt > 1:
            yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Drafting fallback (Attempt {attempt}/3)...', 'icon': '🛡️'})}\n\n"}

        gen = _stream_research_call(
            api_url, writer_payload, display_model, "status",
            thought_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_STEP_WRITER_TOKENS,
            content_threshold=config.RESEARCH_MEANDER_CONTENT_THRESHOLD_TOKENS,
            step_id=section_index,
            api_key=api_key, chat_id=chat_id, enable_thinking=(attempt == 1)
        )

        raw_section = ""
        async for packet in gen:
            if packet["type"] == "activity": yield packet
            elif packet["type"] == "result":
                raw_section = packet["data"]
                if packet.get("meandered") and attempt == 1:
                    raw_section = None

        if raw_section:
            parsed = _extract_json_from_text(raw_section)
            if parsed and isinstance(parsed, dict) and "markdown_content" in parsed:
                markdown = parsed["markdown_content"]
                if len(_strip_thinking(markdown).strip()) >= config.RESEARCH_MIN_SECTION_LEN:
                    raw_section = markdown # Overwrite with final content
                    break
        
        raw_section = None # Reset for next attempt if quality check fails

    if not raw_section:
        yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, 'needs_retry', {'state': 'writing', 'message': f'Failed to generate section \"{section_heading}\".'})}\n\n"}
        return

    # Process entities from reasoning if any (before stripping)
    if "<think>" in raw_section:
        match = re.search(r'<think>(.*?)</think>', raw_section, re.DOTALL)
        if match:
            entity_matches = re.findall(r'Entity:\s*"([^"]+)"\s*\(([^)]+)\)', match.group(1), re.IGNORECASE)
            for term, definition in entity_matches:
                if term not in entity_glossary:
                    entity_glossary[term] = definition

    # Preserve full response in history
    messages.append({"role": "assistant", "content": raw_section or ""})

    # Strip trailing bibliographies the LLM might have added
    section_text = raw_section or ""
    for ref_header in ['\n## References', '\n### References', '\n## Sources', '\n### Sources']:
        if ref_header in section_text:
            section_text = section_text.split(ref_header)[0]

    section_text = re.sub(r'<section_summary>.*?</section_summary>', '', section_text, flags=re.DOTALL).strip()

    # Yield write progress checkpoint (for partial recovery)
    yield {"type": "write_checkpoint", "data": {"section_text": section_text, "entity_glossary": entity_glossary.copy()}}

    # ---- TURN 4: Section Summary (3-Turn Resilience) ----
    summary_points = []
    if section_index < n_sections - 1:
        yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Generating summary for section: {section_heading}...', 'icon': '📋'})}\n\n"}

        summary_prompt = RESEARCH_STEP_SUMMARY_PROMPT.format(today_date=today_date)
        messages.append({"role": "user", "content": summary_prompt})
        summary_messages = messages

        for attempt in [1, 2, 3]:
            summary_payload = {
                "model": model,
                "messages": summary_messages,
                **_get_sampling_params(attempt=attempt),
                "max_tokens": config.RESEARCH_MAX_TOKENS_SUMMARY,
                "response_format": {"type": "json_schema", "json_schema": {"name": "section_summary", "schema": SUMMARY_JSON_SCHEMA}}
            }

            if attempt > 1:
                yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Summary fallback (Attempt {attempt}/3)...', 'icon': '🛡️'})}\n\n"}

            gen = _stream_research_call(
                api_url, summary_payload, display_model, "status", 
                thought_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_SUMMARY_TOKENS,
                content_threshold=config.RESEARCH_MEANDER_CONTENT_THRESHOLD_TOKENS,
                api_key=api_key, chat_id=chat_id, enable_thinking=(attempt == 1)
            )
            
            raw_summary = ""
            async for packet in gen:
                if packet["type"] == "activity": yield packet
                elif packet["type"] == "result":
                    raw_summary = packet["data"]
                    if packet.get("meandered") and attempt == 1:
                        raw_summary = None

            parsed = _extract_json_from_text(raw_summary) if raw_summary else None
            if parsed and isinstance(parsed, dict) and "summary_points" in parsed:
                summary_points = parsed["summary_points"]
                break

        if not summary_points:
            yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, 'needs_retry', {'state': 'writing', 'message': f'Failed to generate summary for \"{section_heading}\".'})}\n\n"}
            yield "data: [DONE]\n\n"
            yield {"type": "result", "data": (None, None, None, None, next_source_id)}
            return

    # Yield summary checkpoint (for partial recovery)
    yield {"type": "summary_checkpoint", "data": {"summary_points": summary_points}}

    yield {"type": "activity", "data": f"data: {_create_activity_chunk(display_model, 'reflection', {'message': f'Section complete: {section_heading}', 'step_id': section_index})}\n\n"}

    yield {"type": "result", "data": (section_text, summary_points, plan_mod, follow_up_content, next_source_id)}

def _format_plan_as_markdown(xml_plan):
    """Converts a <research_plan> XML string into a readable Markdown preview."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(xml_plan, 'html.parser')
        title = soup.find('title').get_text() if soup.find('title') else "Research Strategy"
        md = f"# {title}\n\n"
        
        for idx, section in enumerate(soup.find_all('section')):
            heading = section.find('heading').get_text() if section.find('heading') else f"Section {idx+1}"
            desc = section.find('description').get_text() if section.find('description') else ""
            md += f"## {heading}\n"
            if desc:
                md += f"{desc}\n\n"
            
            queries = section.find_all('query')
            if queries:
                md += "### Key Research Queries\n"
                for q in queries:
                    md += f"- {q.get_text()}\n"
                md += "\n"
        
        md += "---\n*This plan has been automatically generated based on your request. The agent will now execute these steps and compile a report.*"
        return md
    except Exception as e:
        return f"**Error formatting plan:** {str(e)}"

# =====================================================================
# MAIN RESEARCH HANDLER
# =====================================================================


async def generate_research_response(api_url, model, messages, approved_plan=None, chat_id=None, search_depth_mode='regular', vision_model=None, model_name=None, resume_state=None, api_key=None, edits=None, topic_override=None, vision_enabled=True):
    """
    Main Research Pipeline
    
    Phase 0: Context Scout (pre-planning analysis)
    Phase 1: Planning (structured research plan generation)
    Phase 2: Sequential Step Execution (search → select → extract → reflect → write)
    Phase 3: Assembly & Audit (stitch → normalize → audit patches → synthesis → references)
    """
    display_model = model_name or model
    full_reasoning = ""
    today_date = datetime.date.today().strftime("%A, %B %d, %Y")
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
                break # Identify the STARTING topic

    # VLM concurrency lock (serialize vision model calls)
    vlm_lock = asyncio.Semaphore(1) if vision_model else None

    # Ensure MCP clients are connected
    if not tavily_client.session:
        await tavily_client.connect()
    if not playwright_client.session:
        await playwright_client.connect()

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
    if not resume_state or resume_state in ["scouting", "planning"]:
        if not approved_plan:
            current_time = get_current_time()
            conversation_history = [m for m in messages if m['role'] != 'system']

            # ===== PHASE 0: CONTEXT SCOUT =====
            scout_history_path = os.path.join(config.DATA_DIR, "tasks", f"{chat_id}_scout_history.json")
            planner_history_path = os.path.join(config.DATA_DIR, "tasks", f"{chat_id}_planner_history.json")
            os.makedirs(os.path.dirname(scout_history_path), exist_ok=True)

            scout_messages = []
            scout_analysis = None
            preliminary_search_results = ""
            raw_scout = ""
            structural_recommendation = "narrative"

            # 1. Check if we can skip Scout (Edits present means scouting is done)
            scout_done = False
            if edits and os.path.exists(planner_history_path):
                scout_done = True
                # We need raw_scout from the first assistant message of the scout history to pass context if needed
                if os.path.exists(scout_history_path):
                    try:
                        with open(scout_history_path, 'r') as f:
                            hist = json.load(f)
                            # Find the last successful scout analysis and any search findings
                            for m in hist:
                                if m['role'] == 'user' and "Preliminary Search Results:" in str(m.get('content', '')):
                                    preliminary_search_results += f"\n{m['content']}"
                                
                                if m['role'] == 'assistant':
                                    content = m.get('content', '')
                                    test_analysis = _extract_json_from_text(content)
                                    if test_analysis and not test_analysis.get('clarifying_question'):
                                        raw_scout = content
                                        scout_analysis = test_analysis
                    except Exception:
                        # If history file is corrupted or unreadable, treat as if no history exists
                        pass

            # 2. If not skipping, load Scout history or start fresh
            if not scout_done:
                if os.path.exists(scout_history_path):
                    try:
                        with open(scout_history_path, 'r') as f:
                            scout_messages = json.load(f)
                        # If the last message was a user message (clarification response), we continue
                        # If the last was assistant, we might be resuming or it might be done
                        if scout_messages and scout_messages[-1]['role'] == 'assistant':
                            last_scout_raw = scout_messages[-1]['content']
                            scout_analysis = _extract_json_from_text(last_scout_raw)
                            if scout_analysis and not scout_analysis.get("clarifying_question"):
                                scout_done = True
                                raw_scout = last_scout_raw
                    except:
                        pass

                if not scout_messages:
                    scout_prompt = RESEARCH_SCOUT_PROMPT.format(
                        today_date=today_date
                    )
                    scout_topic = topic_override or original_query
                    scout_messages = [
                        {"role": "system", "content": scout_prompt},
                        {"role": "user", "content": scout_topic}
                    ]
                elif topic_override:
                    # If history exists and we have a new topic_override, it's likely a clarification response
                    # Append it if the last message was assistant
                    if scout_messages and scout_messages[-1]['role'] == 'assistant':
                        scout_messages.append({"role": "user", "content": topic_override})

            # 3. Scout iteration loop (if not done)
            while not scout_done:
                scout_analysis = None
                for attempt in [1, 2, 3]:
                    scout_payload = {
                        "model": model,
                        "messages": scout_messages,
                        **_get_sampling_params(attempt=attempt),
                        "max_tokens": config.RESEARCH_MAX_TOKENS_SCOUT,
                        "response_format": {"type": "json_schema", "json_schema": {"name": "scout_analysis", "schema": SCOUT_JSON_SCHEMA}}
                    }

                    try:
                        status_msg = 'Analyzing topic context...' if attempt == 1 else f'Auto-retrying analysis (Attempt {attempt}/3)...'
                        yield f"data: {_create_activity_chunk(display_model, 'planning', {'message': status_msg, 'state': 'thinking'})}\n\n"
                        
                        gen = _stream_research_call(
                            api_url, scout_payload, display_model, "planning",
                            thought_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_SCOUT_TOKENS,
                            content_threshold=config.RESEARCH_MEANDER_CONTENT_THRESHOLD_TOKENS,
                            api_key=api_key,
                            chat_id=chat_id,
                            enable_thinking=(attempt == 1)
                        )
                        
                        raw_scout = ""
                        scout_content = ""
                        scout_meandered = False
                        async for packet in gen:
                            if packet["type"] == "activity":
                                yield packet["data"]
                            elif packet["type"] == "result":
                                raw_scout = packet["data"]
                                scout_content = packet.get("content", "")
                                scout_meandered = packet.get("meandered", False)
                        
                        if scout_meandered and attempt == 1:
                            yield f"data: {_create_activity_chunk(display_model, 'planning', {'message': 'Scout analysis meandering. Falling back to structured mode...', 'state': 'warning'})}\n\n"
                            continue 
                        
                        if raw_scout:
                            scout_analysis = _extract_json_from_text(scout_content or raw_scout)
                        
                        if scout_analysis and isinstance(scout_analysis, dict):
                            # Success check
                            if scout_analysis.get("clarifying_question"):
                                scout_messages.append({"role": "assistant", "content": raw_scout})
                                with open(scout_history_path, 'w') as f:
                                    json.dump(scout_messages, f)
                                yield f"data: {_create_activity_chunk(display_model, 'planning', {'message': 'Topic requires clarification.', 'state': 'complete', 'clarification': True})}\n\n"
                                yield f"data: {create_chunk(display_model, content=scout_analysis['clarifying_question'], clarification=True)}\n\n"
                                yield "data: [DONE]\n\n"
                                return

                            if scout_analysis.get("needs_search") and scout_analysis.get("preliminary_search"):
                                prelim = scout_analysis["preliminary_search"]
                                prelim_query = prelim.get("query", "")
                                if prelim_query:
                                    yield f"data: {_create_activity_chunk(display_model, 'planning', {'message': f'Gathering context: \"{prelim_query}\"...', 'state': 'thinking'})}\n\n"
                                    mcp_res = await _execute_mcp_tool(tavily_client, "async_tavily_search_tool", {
                                        "query": prelim_query,
                                        "topic": prelim.get("topic", "general"),
                                        "time_range": prelim.get("time_range")
                                    }, chat_id=chat_id)
                                    try:
                                        res_json = json.loads(mcp_res.content[0].text)
                                        p_results = res_json.get("results", [])
                                        snippets = [f"- **{r.get('title')}** ({r.get('url')}): {r.get('content')}" for r in p_results[:config.RESEARCH_SCOUT_PRELIM_RESULTS_COUNT]]
                                        res_str = "\n".join(snippets)
                                        preliminary_search_results += f"\nResults for '{prelim_query}':\n{res_str}"
                                        scout_messages.append({"role": "assistant", "content": raw_scout})
                                        scout_messages.append({"role": "user", "content": f"Preliminary Search Results:\n{res_str}"})
                                        # Recurse Scout loop with fresh context
                                        break # Breaks attempt loop, moves to next for scout_turn
                                    except:
                                        pass
                            
                            # Final success state
                            scout_messages.append({"role": "assistant", "content": raw_scout})
                            scout_done = True
                            break
                        else:
                            if attempt < 3:
                                yield f"data: {_create_activity_chunk(display_model, 'planning', {'message': f'Attempt {attempt} failed validation. Retrying...', 'state': 'warning'})}\n\n"
                                continue
                    
                    except Exception as e:
                        log_event("research_scout_error", {"chat_id": chat_id, "error": str(e), "attempt": attempt})
                        if attempt == 3: raise
                        continue

                # Save history
                if scout_messages:
                    with open(scout_history_path, 'w') as f:
                        json.dump(scout_messages, f)

                if not scout_done and not scout_analysis:
                    yield f"data: {_create_activity_chunk(display_model, 'needs_retry', {'state': 'scouting', 'message': 'Scout analysis failed to produce a valid roadmap.'})}\n\n"
                    yield "data: [DONE]\n\n"
                    return

            # ===== PHASE 1: PLANNING (3-Turn Resilience) =====
            planner_messages = []
            if os.path.exists(planner_history_path):
                try:
                    with open(planner_history_path, 'r') as f:
                        planner_messages = json.load(f)
                except:
                    pass

            if not planner_messages:
                # Build context from scout
                scout_context_str = ""
                if scout_analysis:
                    scout_context_parts = [
                        f"## Research Objective\nTarget Topic: {topic_override or original_query}",
                        f"\n## Context Analysis",
                        f"- **Topic Type:** {scout_analysis.get('topic_type', 'general')}",
                        f"- **Time-Sensitive:** {scout_analysis.get('time_sensitive', False)}",
                        f"- **Analysis Notes:** {scout_analysis.get('context_notes', '')}"
                    ]
                    if preliminary_search_results:
                        scout_context_parts.append(f"\n### Preliminary Research Findings\n{preliminary_search_results}")
                    scout_context_str = "\n".join(scout_context_parts)
                else:
                    scout_context_str = f"## Research Objective\nTarget Topic: {topic_override or original_query}"

                system_prompt = RESEARCH_PLANNER_PROMPT.format(
                    today_date=today_date,
                    scout_context=scout_context_str,
                    max_queries_per_section=config.RESEARCH_MAX_QUERIES_PER_SECTION,
                    max_total_queries=config.RESEARCH_MAX_TOTAL_QUERIES,
                )
                handoff = json.dumps(scout_analysis) if scout_analysis else _strip_thinking(raw_scout)
                planner_messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": handoff}
                ]

            if edits:
                planner_messages.append({"role": "user", "content": f"User refinements: {edits}"})

            clean_xml = None
            for attempt in [1, 2, 3]:
                status_msg = 'Designing research strategy...' if attempt == 1 else f'Auto-retrying planning (Attempt {attempt}/3)...'
                yield f"data: {_create_activity_chunk(display_model, 'planning', {'message': status_msg, 'state': 'thinking'})}\n\n"

                payload = {
                    "model": model,
                    "messages": planner_messages,
                    "stream": True,
                    **_get_sampling_params(attempt=1 if attempt == 1 else 2),
                    "max_tokens": config.RESEARCH_MAX_TOKENS_PLANNING,
                    "response_format": {"type": "json_schema", "json_schema": {"name": "research_plan", "schema": PLANNER_JSON_SCHEMA}}
                }

                plan_source = ""
                plan_meandered = False
                gen = _stream_research_call(
                    api_url, payload, display_model, "planning",
                    thought_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_PLANNING_TOKENS,
                    content_threshold=config.RESEARCH_MEANDER_CONTENT_THRESHOLD_TOKENS,
                    api_key=api_key, chat_id=chat_id, enable_thinking=(attempt == 1)
                )

                async for packet in gen:
                    if packet["type"] == "activity": yield packet["data"]
                    elif packet["type"] == "result":
                        plan_source = packet.get("content", "")
                        plan_meandered = packet.get("meandered", False)

                if plan_meandered and attempt == 1:
                    yield f"data: {_create_activity_chunk(display_model, 'planning', {'message': 'Planning meandering. Switching to structured mode...', 'state': 'warning'})}\n\n"
                    continue

                if not plan_source.strip(): continue

                yield f"data: {_create_activity_chunk(display_model, 'planning', {'message': 'Validating strategy...', 'state': 'validating'})}\n\n"
                clean_xml, error = validate_research_plan(plan_source)

                if clean_xml:
                    planner_messages.append({"role": "assistant", "content": plan_source})
                    with open(planner_history_path, 'w') as f:
                        json.dump(planner_messages, f)
                    yield f"data: {_create_activity_chunk(display_model, 'planning', {'message': 'Strategy approved!', 'state': 'complete'})}\n\n"
                    
                    # Issue 3.4 fix: use full chat_id to avoid 8-char collision risk
                    canvas_id = f"plan_{chat_id}" if chat_id else "research_plan"
                    plan_md = _format_plan_as_markdown(clean_xml)

                    if chat_id:
                        try:
                            # Use centralized canvas manager
                            result = await create_canvas(
                                chat_id=chat_id,
                                canvas_id=canvas_id,
                                title="Research Strategy",
                                content=plan_md,
                                folder="research",
                                author="system",
                                version_comment="Research plan created"
                            )
                        except Exception as e:
                            log_event("research_plan_canvas_persist_error", {"chat_id": chat_id, "error": str(e)})

                    yield f"data: {json.dumps({'__canvas_update__': {'id': canvas_id, 'title': 'Research Strategy', 'content': plan_md, 'action': 'create'}})}\n\n"

                    yield f"data: {create_chunk(display_model, content=clean_xml)}\n\n"
                    yield "data: [DONE]\n\n"
                    return
                else:
                    yield f"data: {_create_activity_chunk(display_model, 'planning', {'message': f'Validation issue: {error}', 'state': 'warning'})}\n\n"
            
            yield f"data: {_create_activity_chunk(display_model, 'needs_retry', {'state': 'planning', 'message': 'Planning failed after 3 attempts. Please re-run.'})}\n\n"
            yield "data: [DONE]\n\n"
            return
            # Transition to Phase 2

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
            accumulated_summaries = []
    else:
        last_completed_section = -1
        accumulated_summaries = []

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
                mcp_res = await _execute_mcp_tool(tavily_client, "async_tavily_search_tool", {
                    "query": query, "topic": q_topic, "time_range": q_time_range,
                    "start_date": q_start_date, "end_date": q_end_date,
                    "max_results": config.RESEARCH_TAVILY_MAX_RESULTS_INITIAL
                }, chat_id=chat_id)
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
                        raw_content_from_search=sel_result.get('raw_content'), api_key=api_key, chat_id=chat_id, vision_enabled=vision_enabled
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
                if vision_model and vision_enabled and search_images:
                    async for packet in _process_tavily_search_images(search_images, section_idx, vision_model, api_url, vlm_lock, display_model=display_model, api_key=api_key, chat_id=chat_id, vision_enabled=vision_enabled):
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

                        mcp_res = await _execute_mcp_tool(tavily_client, "async_tavily_map_tool", {"url_to_map": sel_url, "instruction": f"Researching: {heading}. Find deep data pages."}, chat_id=chat_id)
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
                                    display_model=display_model, step_id=section_idx, api_key=api_key, chat_id=chat_id, vision_enabled=vision_enabled
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
            # Track progress for partial failure recovery
            section_progress = {"reflection": False, "triage": False, "write": False, "summary": False}

            query_strings = [q["search"] for q in section_queries]
            async for packet in _execute_section_reflection_and_write(
                    api_url, model, heading, description, query_strings,
                    section_content_buffer, accumulated_summaries, section_idx,
                    n_sections, original_query, approved_plan,
                    search_depth_mode, vision_model, vlm_lock, chat_id,
                    display_model, source_registry, global_source_id, mode_guidance, entity_glossary,
                    image_results=vlm_image_results, api_key=api_key, vision_enabled=vision_enabled
                ):

                if packet["type"] in ("activity", "stream", "stream_chunk"):
                    yield packet["data"]
                elif packet["type"] == "result":
                    section_text, summary_points, plan_mod, _, global_source_id = packet["data"]
                elif packet["type"].endswith("_checkpoint"):
                    # Handle progress checkpoint for partial failure recovery
                    checkpoint_type = packet["type"].replace("_checkpoint", "")
                    checkpoint_data = packet["data"]
                    section_progress[checkpoint_type] = True

                    # Save state immediately after each checkpoint
                    if chat_id:
                        try:
                            # Update the current section entry with progress
                            if section_idx >= len(accumulated_summaries):
                                accumulated_summaries.append({
                                    "section": section_idx,
                                    "heading": heading,
                                    "progress": {},
                                    "section_text": None,
                                    "summary_points": None
                                })
                            section_entry = accumulated_summaries[section_idx]
                            if 'progress' not in section_entry:
                                section_entry['progress'] = {}
                            section_entry['progress'][checkpoint_type] = {"status": "completed"}

                            # If checkpoint has data, store it
                            if checkpoint_type == "write" and checkpoint_data.get("section_text"):
                                section_entry['section_text'] = checkpoint_data["section_text"]
                            elif checkpoint_type == "summary" and checkpoint_data.get("summary_points"):
                                section_entry['summary_points'] = checkpoint_data["summary_points"]

                            # Save state to disk
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
                            log_event("research_checkpoint_save_error", {"chat_id": chat_id, "checkpoint": checkpoint_type, "error": str(e)})

            if section_text is None:
                # The sub-generator already yielded the 'needs_retry' chunk and [DONE]
                return

            yield f"data: {create_chunk(display_model, content=chr(10)*2)}\n\n"

            # Pair the section text directly with its summary object
            accumulated_summaries.append({
                "section": section_idx, "heading": heading,
                "summary_points": summary_points,
                "plan_modification": plan_mod,
                "section_text": section_text
            })

            # Emit canvas update for progressive rendering (Phase 8a) AND persist to disk (Issue 2.2 fix)
            canvas_action = "create" if section_idx == 0 else "append"
            canvas_id = f"research_{chat_id}" if chat_id else "research_report"  # Issue 3.4 fix: full chat_id
            canvas_title = "Research Report"  # Will be replaced by Synthesis later

            # For progressive updates, we send the section header + content
            progressive_content = f"## {heading}\n\n{section_text}\n\n"

            # Persist the progressive canvas to disk after every section (partial report recovery)
            if chat_id:
                try:
                    # Build the accumulated content from all completed sections so far
                    completed_sections = [
                        s for s in accumulated_summaries if s.get('section_text')
                    ]
                    accumulated_content = "\n\n".join(
                        f"## {s['heading']}\n\n{s['section_text']}" for s in completed_sections
                    )
                    # Use centralized canvas manager
                    if section_idx == 0:
                        # First section - create canvas
                        await create_canvas(
                            chat_id=chat_id,
                            canvas_id=canvas_id,
                            title=canvas_title,
                            content=accumulated_content,
                            folder="research",
                            author="system",
                            version_comment="Progressive research report"
                        )
                    else:
                        # Subsequent sections - append
                        await append_to_canvas(
                            canvas_id,
                            chat_id,
                            f"\n\n## {heading}\n\n{section_text}",
                            author="system",
                            version_comment="Added section"
                        )
                except Exception as e:
                    log_event("research_progressive_canvas_persist_error", {"chat_id": chat_id, "error": str(e)})

            yield f"data: {json.dumps({'__canvas_update__': {'id': canvas_id, 'title': canvas_title, 'content': progressive_content, 'action': canvas_action}})}\n\n"

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
        
        if _is_transient_error(e):
            yield f"data: {_create_activity_chunk(display_model, 'needs_retry', {'state': 'section_execution', 'message': f'Section execution interrupted: {str(e)}'})}\n\n"
        else:
            yield f"data: {create_chunk(model, content=f'**Fatal Error:** {str(e)}')}\n\n"
        
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

        # --- 3.1 Pre-Audit Citation Validation ---
        # Mechanically remove any [N] tag that doesn't point to a real source
        valid_source_ids = set(source_registry.keys())
        for s in valid_summaries:
            s['section_text'] = _strip_invalid_citations(s['section_text'], valid_source_ids)

        # --- 3.2 Stitch sections ---
        plan_root_for_title = BeautifulSoup(approved_plan, 'html.parser')
        title_tag = plan_root_for_title.find('title')
        report_title = title_tag.get_text(strip=True) if title_tag else "Research Report"
        full_report = f"# {report_title}\n\n" + "\n\n".join([s['section_text'] for s in valid_summaries])

        # --- 3.3 Mechanical image stripping (vision enriches content, but images are never embedded) ---
        full_report = _strip_report_images(full_report)

        # --- 3.4 Auditor (if enabled) ---
        if config.RESEARCH_AUDIT_ENABLED:
            yield f"data: {_create_activity_chunk(display_model, 'status', {'message': 'Running quality audit...', 'icon': '🔍'})}\n\n"

            # Build sections JSON for the auditor (structured data)
            report_sections_json = json.dumps(
                [{"id": i, "title": s['heading'], "content": s['section_text']} for i, s in enumerate(valid_summaries)],
                indent=2
            )

            auditor_prompt = RESEARCH_DETECTIVE_PROMPT.format(
                user_query=original_query,
                today_date=today_date
            )

            auditor_messages = [
                {"role": "system", "content": "You are the Report Auditor pipeline."},
                {"role": "user", "content": f"Here is the report draft to audit:\n{report_sections_json}\n\n{auditor_prompt}"}
            ]

            # TURN 1, 2, 3: Detective (Auditor) (Soft Fail)
            raw_audit = ""
            for attempt in [1, 2, 3]:
                detective_payload = {
                    "model": model,
                    "messages": auditor_messages,
                    **_get_sampling_params(attempt=attempt),
                    "max_tokens": config.RESEARCH_MAX_TOKENS_AUDIT,
                    "response_format": {"type": "json_schema", "json_schema": {"name": "report_audit", "schema": DETECTIVE_JSON_SCHEMA}}
                }

                if attempt > 1:
                    yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Detective fallback (Attempt {attempt}/3)...', 'icon': '🛡️'})}\n\n"

                gen = _stream_research_call(
                    api_url, detective_payload, display_model, "status",
                    thought_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_AUDIT_TOKENS,
                    content_threshold=config.RESEARCH_MEANDER_CONTENT_THRESHOLD_TOKENS,
                    api_key=api_key, chat_id=chat_id, enable_thinking=(attempt == 1)
                )
                async for packet in gen:
                    if packet["type"] == "activity": yield packet["data"]
                    elif packet["type"] == "result":
                        raw_audit = packet["data"]
                        if packet.get("meandered") and attempt == 1:
                            raw_audit = None
                
                if raw_audit and _extract_json_from_text(raw_audit):
                    break # Success
            
            audit_result = _extract_json_from_text(raw_audit) if raw_audit else None
            if not audit_result:
                yield f"data: {_create_activity_chunk(display_model, 'status', {'message': 'Detective audit failed. Proceeding with unwashed draft.', 'icon': '⚠️'})}\n\n"
            
            log_event("research_detective_complete", {
                "chat_id": chat_id,
                "raw_output": raw_audit,
                "parsed_success": bool(audit_result)
            })

            if audit_result and isinstance(audit_result, dict):
                auditor_messages.append({"role": "assistant", "content": raw_audit})
            else:
                audit_result = {"issues": []}

            if audit_result and isinstance(audit_result, dict):
                issues = audit_result.get("issues", [])
                
                if issues:
                    yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Detective found {len(issues)} issue(s)... prioritizing fixes.', 'icon': '🔬'})}\n\n"
                    
                    # Group issues by section ID
                    issues_by_section = {}
                    for issue in issues:
                        sec_id = issue.get("section_id")
                        if isinstance(sec_id, int) and 0 <= sec_id < len(valid_summaries):
                            if sec_id not in issues_by_section:
                                issues_by_section[sec_id] = []
                            issues_by_section[sec_id].append(issue)
                    
                    # Filter based on severity thresholds
                    high_count = 0
                    med_count = 0
                    low_count = 0
                    
                    sections_to_rewrite = []
                    
                    # We process sections, determining highest severity in each
                    for sec_id, sec_issues in issues_by_section.items():
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
                            sections_to_rewrite.append((sec_id, valid_summaries[sec_id]['heading'], sec_issues))

                    if sections_to_rewrite:
                        yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Surgeon correcting {len(sections_to_rewrite)} section(s)...', 'icon': '🔧'})}\n\n"
                    
                        for section_id, section_title, sec_issues in sections_to_rewrite:
                            # Format issues for prompt
                            issues_text = "\n".join([f"- [{i.get('severity', 'Low')}] {i.get('type', 'Unknown')}: {i.get('description', '')}" for i in sec_issues])
                            
                            surgeon_prompt = RESEARCH_SURGEON_PROMPT.format(
                                section_id=section_id,
                                section_title=section_title,
                                issues_list=issues_text,
                                today_date=today_date
                            )
                            
                            auditor_messages_base = list(auditor_messages)
                            surgeon_success = False
                            patched_section = ""

                            for attempt in [1, 2, 3]:
                                if attempt > 1:
                                    yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Surgeon fallback for {section_title[:20]} (Attempt {attempt}/3)...', 'icon': '🛡️'})}\n\n"

                                surgeon_payload = {
                                    "model": model,
                                    "messages": list(auditor_messages_base) + [{"role": "user", "content": surgeon_prompt}],
                                    **_get_sampling_params(attempt=1 if attempt == 1 else 2),
                                    "max_tokens": config.RESEARCH_MAX_TOKENS_AUDIT,
                                    "response_format": {"type": "json_schema", "json_schema": {"name": "section_patch", "schema": SURGEON_JSON_SCHEMA}}
                                }

                                yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Fixing: {section_title[:30]}...', 'icon': '✂️'})}\n\n"
                                
                                patched_section_raw = ""
                                gen = _stream_research_call(
                                    api_url, surgeon_payload, display_model, "status",
                                    thought_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_AUDIT_TOKENS,
                                    content_threshold=config.RESEARCH_MEANDER_CONTENT_THRESHOLD_TOKENS,
                                    api_key=api_key, chat_id=chat_id, enable_thinking=(attempt == 1)
                                )
                                async for packet in gen:
                                    if packet["type"] == "activity": yield packet["data"]
                                    elif packet["type"] == "result":
                                        patched_section_raw = packet["data"]
                                        if packet.get("meandered") and attempt == 1:
                                            patched_section_raw = None
                                
                                if patched_section_raw:
                                    parsed = _extract_json_from_text(patched_section_raw)
                                    if parsed and isinstance(parsed, dict) and "patched_markdown" in parsed:
                                        patched_section = parsed["patched_markdown"]
                                        surgeon_success = True
                                        break
                            
                            if not surgeon_success:
                                yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Surgeon failed for {section_title[:20]}. Skipping fix.', 'icon': '⚠️'})}\n\n"

                            # Strip reasoning from patched section for storage
                            clean_patch = _strip_thinking(patched_section) if patched_section else ""
                            
                            if clean_patch.strip():
                                auditor_messages.append({"role": "assistant", "content": patched_section or ""})
                                
                                # Precise ID-based application
                                valid_summaries[section_id]['section_text'] = clean_patch
                                log_event("research_surgeon_patch_applied", {"chat_id": chat_id, "section_id": section_id, "section_title": section_title})

                    # Re-stitch after patches
                    full_report = f"# {report_title}\n\n" + "\n\n".join([s['section_text'] for s in valid_summaries])
                else:
                    yield f"data: {_create_activity_chunk(display_model, 'status', {'message': 'No issues found — report is consistent.', 'icon': '✅'})}\n\n"

            # TURN 1 & 2: Synthesis
            yield f"data: {_create_activity_chunk(display_model, 'status', {'message': 'Generating synthesis sections...', 'icon': '🧩'})}\n\n"
            
            synthesis_prompt = RESEARCH_SYNTHESIS_PROMPT.format(
                today_date=today_date
            )

            raw_synthesis = ""
            for attempt in [1, 2, 3]:
                synthesis_payload = {
                    "model": model,
                    "messages": auditor_messages + [{"role": "user", "content": synthesis_prompt}],
                    **_get_sampling_params(attempt=attempt),
                    "max_tokens": config.RESEARCH_MAX_TOKENS_SYNTHESIS,
                    "response_format": {"type": "json_schema", "json_schema": {"name": "report_synthesis", "schema": SYNTHESIS_JSON_SCHEMA}}
                }

                if attempt > 1:
                    yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Synthesis fallback (Attempt {attempt}/3)...', 'icon': '🛡️'})}\n\n"

                gen = _stream_research_call(
                    api_url, synthesis_payload, display_model, "status",
                    thought_limit=config.RESEARCH_MEANDER_THOUGHT_LIMIT_SYNTHESIS_TOKENS,
                    content_threshold=config.RESEARCH_MEANDER_CONTENT_THRESHOLD_TOKENS,
                    api_key=api_key, chat_id=chat_id, enable_thinking=(attempt == 1)
                )
                async for packet in gen:
                    if packet["type"] == "activity": yield packet["data"]
                    elif packet["type"] == "result":
                        raw_synthesis = packet["data"]
                        full_reasoning = packet.get("reasoning", "")
                        if packet.get("meandered") and attempt == 1:
                            raw_synthesis = None
                
                if raw_synthesis and _extract_json_from_text(raw_synthesis):
                    break

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
        
        # Universal Canvas Integration (Phase 4)
        canvas_id = f"research_{chat_id}" if chat_id else "research_report"  # Issue 3.4 fix: full chat_id
        canvas_title = f"Research: {report_title[:40]}"

        # Persist to disk using centralized canvas manager
        if chat_id:
            try:
                result = await update_canvas_content(
                    canvas_id,
                    chat_id,
                    full_report,
                    author="system",
                    version_comment="Final report completed"
                )
            except Exception as e:
                log_event("research_final_canvas_persist_error", {"chat_id": chat_id, "error": str(e)})

        # Push to UI - report is now only sent to canvas, not conversation history
        yield f"data: {json.dumps({'__canvas_update__': {'id': canvas_id, 'title': canvas_title, 'content': full_report, 'action': 'create'}})}\n\n"

        # Persistence Fix: Yield a persistable content chunk for the messages table history (ensures context on reload)
        persist_content = f"Research complete. Click below to view the full report.\n\n<research_report>{full_report}</research_report>"
        
        if messages:
            for m in reversed(messages):
                if m.get('role') == 'tool' and m.get('name') == 'execute_research_plan':
                    m['content'] = full_report
                    break

            for m in reversed(messages):
                if m.get('role') == 'assistant' and 'execute_research_plan' in str(m.get('tool_calls', '')):
                    m_content = m.get('content') or ""
                    if full_reasoning:
                        m_content += f"\n<think>\n{full_reasoning}\n</think>\n"
                    m_content += persist_content
                    m['content'] = m_content
                    break
            
            yield f"__TRANSACTION_MESSAGES__:{json.dumps(messages)}"
            
        yield f"data: {create_chunk(display_model, content=persist_content)}\n\n"

        # Finalization: Mark research as complete and notify frontend to unlock chat
        if chat_id:
            db.mark_research_completed(chat_id)
            yield f"data: {json.dumps({'__research_finished__': True})}\n\n"

        log_event("research_complete", {
            "chat_id": chat_id,
            "sections": len(valid_summaries),
            "sources": len(source_registry),
            "references": len(references_list)
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        log_event("research_report_generation_fatal_error", {"chat_id": chat_id, "error": str(e)})
        
        if _is_transient_error(e):
            yield f"data: {_create_activity_chunk(display_model, 'needs_retry', {'state': resume_state or 'assembly', 'message': f'Process interrupted: {str(e)}'})}\n\n"
        else:
            yield f"data: {_create_activity_chunk(display_model, 'status', {'message': f'Fatal Code Error: {str(e)}. Please contact support.', 'icon': '☠️'})}\n\n"

    yield "data: [DONE]\n\n"

