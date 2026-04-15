
import asyncio
import json
import re
from backend.logger import log_event, log_tool_call, log_llm_call
import time
import logging
from backend.prompts import (
    BASE_SYSTEM_PROMPT,
    MEMORY_SYSTEM_PROMPT,
    CANVAS_MODE_GUIDANCE
)
from backend.db_wrapper import db
from backend.tools import (
    MANAGE_CORE_MEMORY_TOOL,
    GET_TIME_TOOL,
    VALIDATE_OUTPUT_FORMAT_TOOL,
    INITIATE_RESEARCH_PLAN_TOOL,
    MANAGE_CANVAS_TOOL,
    PREVIEW_CANVASES_TOOL,
    CREATE_CANVAS_TOOL,
    READ_CANVAS_TOOL,
    READ_FILE_TOOL
)
from backend.utils import create_chunk, get_current_time
from backend.canvas_manager import (
    create_canvas,
    get_canvas_content,
    update_canvas_content,
    append_to_canvas,
    patch_canvas_section,
    delete_section,
    validate_patch_action,
    get_chat_canvases_with_details,
    read_canvas_section
)
from backend.db_wrapper import db
from backend import config
from backend.file_manager import file_manager
from backend.mcp_client import tavily_client, playwright_client
from backend.llm import stream_chat_completion, chat_completion
import datetime
from backend.validation import (
    validate_output_format, parse_fixes, find_fix_locations, apply_fixes,
    build_fix_messages, build_regeneration_messages
)
from backend.error_handling import classify_error, create_error_response, is_retryable, execute_with_retry


async def execute_with_retry_async(func, max_retries: int = None, backoff_base: float = 1.0):
    """
    Execute an async function with exponential backoff retry.

    Args:
        func: The async function to execute
        max_retries: Maximum retry attempts (default from config)
        backoff_base: Base backoff time in seconds

    Returns:
        Result from func if successful

    Raises:
        Exception: From func if all retries exhausted
    """
    if max_retries is None:
        max_retries = config.RETRY_COUNT

    for attempt in range(max_retries + 1):
        try:
            return await func()
        except Exception as e:
            error_type = classify_error(e)

            # Check if retryable
            if not is_retryable(error_type):
                raise  # Non-retryable, fail immediately

            if attempt == max_retries:
                raise  # Exhausted retries

            # Calculate and apply backoff with jitter
            delay = backoff_base * (2 ** attempt)
            import random
            delay += random.uniform(0, 0.5)  # Add jitter
            await asyncio.sleep(delay)


async def _stream_and_accumulate(api_url, model, payload, chat_id=None, chat_template_kwargs=None):
    """
    Streams a chat completion call, yielding (sse_chunk_string, final_state) tuples.
    
    During streaming: yields (chunk_string, None) for each SSE chunk.
    After streaming:  yields (None, (full_content, full_reasoning, tool_calls)) once.
    """
    tool_calls = []
    current_tool_call = None
    full_content = ""
    full_reasoning = ""
    
    async for chunk_str in stream_chat_completion(api_url, payload, chat_id=chat_id, chat_template_kwargs=chat_template_kwargs):
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
                    # Ensure arguments is a string before accumulating
                    arg_value = tc_chunk['function']['arguments']
                    if isinstance(arg_value, str):
                        current_tool_call['function']['arguments'] += arg_value
                    else:
                        # If arguments is not a string, convert to string representation
                        current_tool_call['function']['arguments'] += str(arg_value)

            elif 'content' in delta or 'reasoning_content' in delta:
                content = delta.get('content', '')
                reasoning = delta.get('reasoning_content', '') or delta.get('reasoning', '')

                if reasoning:
                    full_reasoning += reasoning
                    yield (f"data: {create_chunk(model, reasoning=reasoning)}\n\n", None)

                if content:
                    full_content += content
                    yield (f"data: {create_chunk(model, content=content)}\n\n", None)

            if finish_reason == 'tool_calls':
                if current_tool_call:
                    tool_calls.append(current_tool_call)
                    current_tool_call = None
        except Exception:
            pass

    # Yield the final accumulated state
    yield (None, (full_content, full_reasoning, tool_calls))


def _stream_corrected_content(model, fixed_content, fixed_reasoning=""):
    """
    Re-stream fixed content and reasoning to the frontend as SSE chunks.
    Splits the content into reasonable chunk sizes for smooth rendering.
    """
    CHUNK_SIZE = 50  # characters per chunk
    
    # First stream reasoning if provided
    if fixed_reasoning:
        for i in range(0, len(fixed_reasoning), CHUNK_SIZE):
            chunk_text = fixed_reasoning[i:i + CHUNK_SIZE]
            yield f"data: {create_chunk(model, reasoning=chunk_text)}\n\n"
            
    # Then stream content
    for i in range(0, len(fixed_content), CHUNK_SIZE):
        chunk_text = fixed_content[i:i + CHUNK_SIZE]
        yield f"data: {create_chunk(model, content=chunk_text)}\n\n"


async def generate_chat_response(api_url, model, messages, extra_body, enable_thinking, rag=None, file_rag=None, memory_mode=False, search_depth_mode='regular', chat_id=None, has_vision=False, api_key=None, research_mode=False, research_completed=False, initial_tool_calls=None, resume_state=None, canvas_mode=False, active_canvas_context=None):
    """
    Handles standard chat interaction with validation and self-healing.
    
    Architecture:
      - full_content: accumulates everything streamed to the frontend. Used for storage.
      - validatable_content: only the last LLM call's raw output. Used for validation.
      - tool_flow_prefix: snapshot of full_content before the second LLM call.
        Used to reconstruct the full message if redact fires during validation.
    
    Frontend rendering uses three self-contained <think> blocks:
      <think>[first reasoning]</think>
      <think>[tool logs]</think>
      <think>[second reasoning]</think>
      [final answer]
    """
    # Ensure MCP clients are connected
    await tavily_client.connect()
    await playwright_client.connect()

    # Process uploaded files from extra_body
    uploaded_files = extra_body.get('uploaded_files', [])
    files_data = []
    if uploaded_files and file_rag:
        for file_info in uploaded_files:
            file_id = file_info.get('file_id')
            metadata = file_manager.get_file(file_id)
            if metadata:
                files_data.append({
                    'file_id': metadata.file_id,
                    'original_filename': metadata.original_filename,
                    'mime_type': metadata.mime_type,
                    'file_size': metadata.file_size,
                    'content_text': metadata.content_text,
                    'stored_filename': metadata.stored_filename
                })
                # Skip storing in RAG if already processed (prevents double embedding)
                existing_chunks = file_rag.get_file_chunks(file_id)
                if existing_chunks:
                    logger = logging.getLogger(__name__)
                    logger.debug(f"[CHAT_FILE_PROCESS] Skipping {file_id} - already in RAG")
                elif metadata.content_text:
                    # Store file content in RAG for semantic search
                    file_rag.store_file(file_id, chat_id, metadata.content_text)
        extra_body['files_data'] = files_data

    def strip_research_artifacts(msgs):
        """
        Strips <think>, <research_plan>, and <research_report> tags from 
        assistant messages that executed research tools, preventing context bloat.
        """
        import copy
        import re
        import json
        cleaned = []
        for msg in msgs:
            msg_copy = copy.copy(msg)
            if msg_copy.get('role') == 'assistant' and msg_copy.get('content'):
                content = msg_copy['content']
                tool_calls = msg_copy.get('tool_calls', [])
                if isinstance(tool_calls, str):
                    try:
                        tool_calls = json.loads(tool_calls)
                    except:
                        tool_calls = []
                
                is_research = False
                for tc in (tool_calls or []):
                    if isinstance(tc, dict):
                        fn_name = tc.get('function', {}).get('name')
                        if fn_name in ('initiate_research_plan', 'execute_research_plan'):
                            is_research = True
                            break
                
                if is_research:
                    content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
                    content = re.sub(r'<research_plan>.*?</research_plan>', '', content, flags=re.DOTALL)
                    content = re.sub(r'<research_report>.*?</research_report>', '', content, flags=re.DOTALL)
                    msg_copy['content'] = content.strip()
            cleaned.append(msg_copy)
        return cleaned

    chat_template_kwargs = {"enable_thinking": enable_thinking}

    # Fetch tools from MCP Servers
    tavily_tools_raw = await tavily_client.get_available_tools()
    playwright_tools_raw = await playwright_client.get_available_tools()
    mcp_tools_raw = tavily_tools_raw + playwright_tools_raw

    # Filter only the chat-facing tools
    chat_mcp_tool_names = ["search_web", "audit_search", "visit_page_tool"]
    mcp_tools = []

    # Map MCP tool schema to OpenAI tool schema
    for mcp_tool in mcp_tools_raw:
        if mcp_tool.name in chat_mcp_tool_names:
            mcp_tools.append({
                "type": "function",
                "function": {
                    "name": mcp_tool.name,
                    "description": mcp_tool.description,
                    "parameters": mcp_tool.inputSchema
                }
            })

    # 1. Setup Tools & Prompts
    # If deep search is enabled, the search_web tool automatically returns raw content.
    # We remove the audit_tavily_search tool to prevent redundancy/hallucination logic.
    tools = [GET_TIME_TOOL, VALIDATE_OUTPUT_FORMAT_TOOL]

    if research_mode and not research_completed:
        tools.append(INITIATE_RESEARCH_PLAN_TOOL)

    # Add file tools
    tools.append(READ_FILE_TOOL)

    if search_depth_mode == 'deep':
        # Find search_web from MCP and modify description, omit audit_search
        for mt in mcp_tools:
            if mt["function"]["name"] == "search_web":
                deep_tool = dict(mt)
                deep_tool["function"] = dict(mt["function"])
                deep_tool["function"]["description"] = "Performs a web search using Tavily to find information on a topic. Results include an AI-summarized answer and the FULL RAW text content of the primary pages. Use this tool ONCE for maximum information depth."
                tools.append(deep_tool)
    else:
        tools.extend(mcp_tools)

    system_prompt = BASE_SYSTEM_PROMPT

    if memory_mode:
        tools.append(MANAGE_CORE_MEMORY_TOOL)
        system_prompt = MEMORY_SYSTEM_PROMPT
        # Fetch current memories and inject them into the system prompt
        memories = db.get_all_memories()
        if memories:
            # Format memories for system prompt injection
            memories_lines = []
            for m in memories:
                tag = m.get('tag', 'explicit_fact')
                content = m.get('content', '')
                memories_lines.append(f"[{tag.upper()}] {content}")
            memories_block = "\n".join(memories_lines)
            system_prompt += f"\n\n## Current Global Memory Store\n<User Profile & Preferences>\n{memories_block}\n</User Profile & Preferences>\n"
        else:
            system_prompt += f"\n\n## Current Global Memory Store\n<User Profile & Preferences>\n(The memory store is currently empty. Add to it if needed.)\n</User Profile & Preferences>\n"

    # Append Capability Notes
    v_status = "ENABLED" if has_vision else "DISABLED"
    v_note = f"\n\n# System Capabilities\n- Vision Support: {v_status}. "
    if not has_vision:
        v_note += "You CANNOT process images."
    else:
        v_note += "You CAN process images. The search tool will automatically return images where relevant."
    system_prompt += v_note

    today_date = datetime.date.today().strftime("%A, %B %d, %Y")
    system_prompt = f"Today's date is: {today_date}.\n\n" + system_prompt

    # Research mode guidance removed - research mode is now controlled by tool availability
    
    if canvas_mode:
        tools.append(CREATE_CANVAS_TOOL)
        tools.append(MANAGE_CANVAS_TOOL)
        tools.append(READ_CANVAS_TOOL)
        tools.append(PREVIEW_CANVASES_TOOL)
        system_prompt += f"\n\n{CANVAS_MODE_GUIDANCE}"

    messages_to_send = [{"role": "system", "content": system_prompt}]

    # Filter out system messages from history as they are now dynamically regenerated
    history = [m for m in messages if m['role'] != 'system']

    # Filter out initiate_research_plan if research is completed
    if research_completed:
        tools = [t for t in tools if t.get('function', {}).get('name') != 'initiate_research_plan']

    messages_to_send.extend(history) 

    # 3. First LLM Call
    start_time = time.time()
    full_content = ""
    full_reasoning = ""
    current_content = ""
    current_reasoning = ""
    tool_calls = initial_tool_calls or []
    tool_flow_prefix = ""  # Preserved for redact reconstruction
    reasoning_flow_prefix = ""

    # Inject file inventory before sending to LLM (similar to canvas previews)
    if chat_id and files_data:
        messages_to_send = await inject_file_inventory_before_latest_user(messages_to_send, chat_id, files_data)

    # Inject previews before sending to LLM
    if chat_id and canvas_mode:
        messages_to_send = await inject_previews_before_latest_user(messages_to_send, chat_id)

    payload = {
        "model": model,
        "messages": strip_research_artifacts(list(messages_to_send)),
        "stream": True,
        **extra_body
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    if api_key:
        payload["api_key"] = api_key

    if not tool_calls:
        async for chunk_str, final_state in _stream_and_accumulate(api_url, model, payload, chat_id=chat_id, chat_template_kwargs=chat_template_kwargs):
            if chunk_str:
                yield chunk_str
            else:
                current_content, current_reasoning, tool_calls = final_state
                
        full_content += current_content
        full_reasoning += current_reasoning

    # In the no-tool-call path, validatable_content is the same as current_content.
    validatable_content = current_content

    # 4. Tool Execution Loop
    MAX_TOOL_ROUNDS = config.MAX_TOOL_ROUNDS
    tool_round = 0
    assistant_for_history = None  # Track assistant content for LLM history (not for persistence)
    while tool_calls and tool_round < MAX_TOOL_ROUNDS:
        tool_round += 1
        # Reconstruct full assistant message for history (with tags if reasoning exists)
        assistant_content_for_history = current_content
        if current_reasoning:
            assistant_content_for_history = f"<think>\n{current_reasoning}\n</think>\n{current_content}"

        # Track assistant content for LLM history (add to messages_to_send to preserve turn sequence)
        messages_to_send.append({
            "role": "assistant",
            "content": assistant_content_for_history if assistant_content_for_history else "",
            "tool_calls": tool_calls
        })
        
        if tool_calls:
            try:
                yield f"data: {json.dumps({'__assistant_tool_calls__': True, 'content': assistant_content_for_history if assistant_content_for_history else '', 'tool_calls': tool_calls})}\n\n"
            except TypeError as e:
                # Handle non-serializable tool call arguments
                error_msg = f"JSON serialization error: {str(e)}"
                log_event("tool_call_serialization_error", {"error": error_msg, "chat_id": chat_id})
                # Try to serialize with sanitized arguments
                sanitized_tool_calls = []
                for tc in tool_calls:
                    try:
                        sanitized_tc = {
                            "id": tc.get("id", ""),
                            "type": tc.get("type", "function"),
                            "function": {
                                "name": tc.get("function", {}).get("name", ""),
                                "arguments": str(tc.get("function", {}).get("arguments", ""))
                            }
                        }
                        sanitized_tool_calls.append(sanitized_tc)
                    except Exception:
                        sanitized_tool_calls.append({"error": "Unable to serialize tool call"})
                yield f"data: {json.dumps({'__assistant_tool_calls__': True, 'content': assistant_content_for_history if assistant_content_for_history else '', 'tool_calls': sanitized_tool_calls})}\n\n"
        
        has_real_tools = False
        for tc in tool_calls:
            fn_name = tc['function']['name']
            args_str = tc['function']['arguments']
            try:
                args = json.loads(args_str)
            except:
                args = {"query": args_str}

            # Handle forbidden tool call
            if fn_name == "validate_output_format":
                messages_to_send.append({
                    "role": "tool",
                    "tool_call_id": tc['id'],
                    "name": fn_name,
                    "content": "ERROR: You are FORBIDDEN from calling this tool. It is invoked automatically by the system. Do not attempt to call it again. Continue with your normal response."
                })
                has_real_tools = True
                continue

            # Handle forbidden system-only tool
            if fn_name == "execute_research_plan":
                messages_to_send.append({
                    "role": "tool",
                    "tool_call_id": tc['id'],
                    "name": fn_name,
                    "content": "ERROR: You are FORBIDDEN from calling this tool directly. It is invoked automatically by the system after a research plan is approved. Continue with your normal response."
                })
                has_real_tools = True
                continue

            if fn_name == "manage_core_memory":
                t0 = time.time()

                additions = args.get("additions") or []
                edits = args.get("edits") or []
                deletions = args.get("deletions") or []

                # Enforce config limits to prevent rogue overwrites
                additions = additions[:config.MEMORY_MAX_ADD_PER_TURN]
                edits = edits[:config.MEMORY_MAX_EDIT_PER_TURN]
                deletions = deletions[:config.MEMORY_MAX_DELETE_PER_TURN]

                results = []

                for item in additions:
                    if not isinstance(item, dict):
                        continue
                    content = item.get("content", "")
                    tag = item.get("tag", "explicit_fact")
                    memory_id = db.add_memory(content, tag)
                    if memory_id:
                        results.append(f"Successfully added memory. Assigned ID: {memory_id}")
                    else:
                        results.append(f"Failed to add memory: {content[:30]}...")

                for item in edits:
                    if not isinstance(item, dict):
                        continue
                    memory_id = item.get("id", "")
                    content = item.get("content", "")
                    tag = item.get("tag", "explicit_fact")
                    success = db.update_memory(memory_id, content, tag)
                    if success:
                        results.append(f"Successfully edited memory {memory_id}")
                    else:
                        results.append(f"Failed to edit memory {memory_id} (Not found or empty)")

                for memory_id in deletions:
                    if not isinstance(memory_id, str):
                        continue
                    success = db.delete_memory(memory_id)
                    if success:
                        results.append(f"Successfully deleted memory {memory_id}")
                    else:
                        results.append(f"Failed to delete memory {memory_id}")

                if not results:
                    results = ["No valid memory operations were performed."]

                context_result = "\n".join(results)

                messages_to_send.append({
                    "role": "tool", "tool_call_id": tc['id'], "name": fn_name,
                    "content": f"<tool_result>\n{context_result}\n</tool_result>"
                })

                duration = time.time() - t0
                log_tool_call(fn_name, args, context_result, duration_s=duration, chat_id=chat_id)
                yield f"data: {json.dumps({'__tool_result__': True, 'tool_call_id': tc['id'], 'name': fn_name, 'result': f'<tool_result>{context_result}</tool_result>'})}\n\n"
                has_real_tools = True
            elif fn_name == "search_web":
                query = args.get("query", "...")
                topic = args.get("topic", "general")
                time_range = args.get("time_range")
                start_date = args.get("start_date")
                end_date = args.get("end_date")
                include_images = has_vision
                
                t0 = time.time()
                mcp_args = {
                    "query": query, "topic": topic, "time_range": time_range,
                    "start_date": start_date, "end_date": end_date,
                    "include_images": include_images, "chat_id": chat_id
                }
                try:
                    async def do_search():
                        return await tavily_client.execute_tool("search_web", mcp_args)

                    mcp_res = await execute_with_retry_async(do_search)

                    # Parse JSON string from MCP tool result
                    try:
                        res_json = json.loads(mcp_res.content[0].text)
                        search_result = res_json.get("standard_output", "")
                        raw_result = res_json.get("raw_output", "")
                    except:
                        search_result = mcp_res.content[0].text
                        raw_result = ""

                    duration = time.time() - t0
                    log_tool_call("mcp_search_web", mcp_args, search_result, duration_s=duration, chat_id=chat_id)
                except Exception as e:
                    duration = time.time() - t0
                    error_type = classify_error(e)
                    retryable = is_retryable(error_type)
                    error_response = create_error_response(e, error_type, retryable=retryable, details={"chat_id": chat_id})
                    search_result = f"ERROR: MCP Tool 'search_web' failed: {error_response['error']}"
                    raw_result = ""
                    log_tool_call("mcp_search_web", mcp_args, search_result, duration_s=duration, chat_id=chat_id)
                    log_event("tool_execution_error", {"tool": "search_web", "error_type": error_type, "retryable": retryable, "error": str(e), "chat_id": chat_id})

                # If Deep Search mode is on, append raw content immediately
                if search_depth_mode == 'deep':
                    search_result = f"Summary:\n{search_result}\n\n==== RAW PAGE CONTENT ====\n{raw_result}"

                messages_to_send.append({
                    "role": "tool", "tool_call_id": tc['id'], "name": fn_name,
                    "content": search_result
                })

                yield f"data: {json.dumps({'__tool_result__': True, 'tool_call_id': tc['id'], 'name': fn_name, 'result': search_result})}\n\n"
                has_real_tools = True
            elif fn_name == "audit_search":
                t0 = time.time()
                mcp_args = {"chat_id": chat_id}
                try:
                    async def do_audit():
                        return await tavily_client.execute_tool("audit_search", mcp_args)

                    mcp_res = await execute_with_retry_async(do_audit)
                    raw_result = mcp_res.content[0].text

                    duration = time.time() - t0
                    log_tool_call(fn_name, args, raw_result, duration_s=duration, chat_id=chat_id)
                except Exception as e:
                    duration = time.time() - t0
                    error_type = classify_error(e)
                    retryable = is_retryable(error_type)
                    error_response = create_error_response(e, error_type, retryable=retryable, details={"chat_id": chat_id})
                    raw_result = f"ERROR: MCP Tool 'audit_search' failed: {error_response['error']}"
                    log_tool_call(fn_name, args, raw_result, duration_s=duration, chat_id=chat_id)
                    log_event("tool_execution_error", {"tool": "audit_search", "error_type": error_type, "retryable": retryable, "error": str(e), "chat_id": chat_id})
                
                messages_to_send.append({
                    "role": "tool", "tool_call_id": tc['id'], "name": fn_name,
                    "content": raw_result
                })
                yield f"data: {json.dumps({'__tool_result__': True, 'tool_call_id': tc['id'], 'name': fn_name, 'result': raw_result})}\n\n"

            elif fn_name == "visit_page_tool":
                url_arg = args.get("url", "...")
                t0 = time.time()

                mcp_args = {"url": url_arg}
                if "detail_level" in args:
                    mcp_args["detail_level"] = args["detail_level"]
                try:
                    async def do_visit():
                        return await playwright_client.execute_tool("visit_page_tool", mcp_args)

                    mcp_res = await execute_with_retry_async(do_visit)
                    raw_result = mcp_res.content[0].text

                    duration = time.time() - t0
                    log_tool_call(fn_name, args, raw_result, duration_s=duration, chat_id=chat_id)
                except Exception as e:
                    duration = time.time() - t0
                    error_type = classify_error(e)
                    retryable = is_retryable(error_type)
                    error_response = create_error_response(e, error_type, retryable=retryable, details={"chat_id": chat_id})
                    raw_result = f"ERROR: MCP Tool 'visit_page_tool' failed: {error_response['error']}"
                    log_tool_call(fn_name, args, raw_result, duration_s=duration, chat_id=chat_id)
                    log_event("tool_execution_error", {"tool": "visit_page_tool", "error_type": error_type, "retryable": retryable, "error": str(e), "chat_id": chat_id})
                
                # Truncate content to safe limit for LLM history (default 8000 from config)
                truncated_result = raw_result
                if len(raw_result) > config.MAX_CHARS_VISIT_PAGE:
                    truncated_result = raw_result[:config.MAX_CHARS_VISIT_PAGE] + "\n\n... (content truncated for length) ..."
                
                messages_to_send.append({
                    "role": "tool", "tool_call_id": tc['id'], "name": fn_name,
                    "content": truncated_result
                })
                yield f"data: {json.dumps({'__tool_result__': True, 'tool_call_id': tc['id'], 'name': fn_name, 'result': raw_result})}\n\n"
                has_real_tools = True
            elif fn_name == "manage_canvas":
                t0 = time.time()
                action = args.get("action", "create")
                canvas_id = args.get("id", None)  # Let canvas_manager generate if None
                title = args.get("title", "Untitled Canvas")
                content = args.get("content", "")
                target_section = args.get("target_section")

                # Validate target_section is provided for patch action (Rule 17)
                is_valid, error_msg = validate_patch_action(action, target_section)
                if not is_valid:
                    raw_result = {"success": False, "error": error_msg}
                    # Always append a tool reply so the assistant turn is not orphaned
                    messages_to_send.append({
                        "role": "tool", "tool_call_id": tc['id'], "name": fn_name,
                        "content": json.dumps(raw_result)
                    })
                    yield f"data: {json.dumps({'__tool_result__': True, 'tool_call_id': tc['id'], 'name': fn_name, 'result': json.dumps(raw_result)})}\n\n"
                    has_real_tools = True
                    continue

                # Use centralized canvas manager
                try:
                    if action == "create":
                        result = await create_canvas(
                            chat_id=chat_id,
                            canvas_id=canvas_id,
                            title=title,
                            content=content,
                            author="system"
                        )
                        final_content = content
                        sse_action = "create"

                    elif action == "append":
                        existing_content = await get_canvas_content(canvas_id, chat_id) or ""
                        result = await append_to_canvas(
                            canvas_id,
                            chat_id,
                            content,
                            author="system"
                        )
                        final_content = result.get("content", content)
                        sse_action = "append"

                    elif action == "patch" and target_section:
                        result = await patch_canvas_section(
                            canvas_id,
                            chat_id,
                            target_section,
                            content,
                            author="system"
                        )
                        final_content = await get_canvas_content(canvas_id, chat_id) or ""
                        sse_action = "replace"
                        patch_heading_found = result.get("section_replaced", True)

                    elif action == "delete_section" and target_section:
                        result = await delete_section(
                            canvas_id,
                            chat_id,
                            target_section,
                            author="system"
                        )
                        final_content = await get_canvas_content(canvas_id, chat_id) or ""
                        sse_action = "replace"
                        section_removed = result.get("section_removed", False)

                    elif action == "replace":
                        result = await update_canvas_content(
                            canvas_id,
                            chat_id,
                            content,
                            author="system"
                        )
                        final_content = content
                        sse_action = "replace"

                    else:
                        # Default to create if action is unknown
                        result = await create_canvas(
                            chat_id=chat_id,
                            canvas_id=canvas_id,
                            title=title,
                            content=content,
                            author="system"
                        )
                        final_content = content
                        sse_action = "create"

                    # Yield the __canvas_update__ SSE event for the frontend
                    yield f"data: {json.dumps({
                        '__canvas_update__': {
                            'action': sse_action,
                            'id': result.get("canvas_id", canvas_id),
                            'title': title,
                            'content': final_content
                        }
                    })}\n\n"

                    # Special handling for delete_section result message
                    if action == "delete_section":
                        section_removed = result.get("section_removed", False)
                        if section_removed:
                            tool_result = f"Section '{target_section}' deleted from canvas '{title}' successfully."
                        else:
                            tool_result = f"Section '{target_section}' not found in canvas '{title}'. No changes made."
                    else:
                        tool_result = f"Canvas '{title}' ({result.get('canvas_id', canvas_id)}) {action}d successfully."
                    messages_to_send.append({
                        "role": "tool", "tool_call_id": tc['id'], "name": fn_name,
                        "content": tool_result
                    })

                except Exception as e:
                    final_content = content
                    sse_action = "replace"
                    error_type = classify_error(e)
                    retryable = is_retryable(error_type)
                    error_response = create_error_response(e, error_type, retryable=retryable, details={"chat_id": chat_id, "action": action})
                    tool_result = f"ERROR: Failed to manage canvas: {error_response['error']}"
                    yield f"data: {json.dumps({
                        '__canvas_update__': {
                            'action': sse_action,
                            'id': canvas_id,
                            'title': title,
                            'content': final_content
                        }
                    })}\n\n"
                    messages_to_send.append({
                        "role": "tool", "tool_call_id": tc['id'], "name": fn_name,
                        "content": tool_result
                    })

                duration = time.time() - t0
                log_tool_call(fn_name, args, tool_result, duration_s=duration, chat_id=chat_id)
                yield f"data: {json.dumps({'__tool_result__': True, 'tool_call_id': tc['id'], 'name': fn_name, 'result': tool_result})}\n\n"
                has_real_tools = True
            elif fn_name == "create_canvas":
                # Handle the new dedicated create_canvas tool
                t0 = time.time()
                title = args.get("title", "Untitled Canvas")
                content = args.get("content", "")

                # Validate required fields
                if not title or not content:
                    raw_result = {"success": False, "error": "title and content are required for create_canvas"}
                    # Always append a tool reply so the assistant turn is not orphaned
                    messages_to_send.append({
                        "role": "tool", "tool_call_id": tc['id'], "name": fn_name,
                        "content": json.dumps(raw_result)
                    })
                    yield f"data: {json.dumps({'__tool_result__': True, 'tool_call_id': tc['id'], 'name': fn_name, 'result': json.dumps(raw_result)})}\n\n"
                    has_real_tools = True
                    continue

                # Create canvas without ID - backend will auto-generate
                try:
                    result = await create_canvas(
                        chat_id=chat_id,
                        canvas_id=None,  # Explicitly None to trigger auto-generation
                        title=title,
                        content=content,
                        author="system"
                    )

                    # Yield the __canvas_update__ SSE event for the frontend
                    yield f"data: {json.dumps({
                        '__canvas_update__': {
                            'action': 'create',
                            'id': result.get("canvas_id"),
                            'title': title,
                            'content': content
                        }
                    })}\n\n"

                    # Return the generated ID prominently for AI to use
                    tool_result = f"Canvas '{title}' created successfully with ID: {result.get('canvas_id')}"
                    messages_to_send.append({
                        "role": "tool", "tool_call_id": tc['id'], "name": fn_name,
                        "content": tool_result
                    })

                except Exception as e:
                    error_type = classify_error(e)
                    retryable = is_retryable(error_type)
                    error_response = create_error_response(e, error_type, retryable=retryable, details={"chat_id": chat_id, "action": "create"})
                    tool_result = f"ERROR: Failed to create canvas: {error_response['error']}"
                    messages_to_send.append({
                        "role": "tool", "tool_call_id": tc['id'], "name": fn_name,
                        "content": tool_result
                    })

                duration = time.time() - t0
                log_tool_call(fn_name, args, tool_result, duration_s=duration, chat_id=chat_id)
                yield f"data: {json.dumps({'__tool_result__': True, 'tool_call_id': tc['id'], 'name': fn_name, 'result': tool_result})}\n\n"
                has_real_tools = True
            elif fn_name == "read_canvas":
                # Handle the read_canvas tool
                t0 = time.time()
                canvas_id = args.get("id", None)
                target_section = args.get("target_section")

                if not canvas_id:
                    tool_result = {"success": False, "error": "canvas id is required"}
                    messages_to_send.append({
                        "role": "tool", "tool_call_id": tc['id'], "name": fn_name,
                        "content": json.dumps(tool_result)
                    })
                    duration = time.time() - t0
                    log_tool_call(fn_name, args, tool_result, duration_s=duration, chat_id=chat_id)
                    continue

                try:
                    result = await read_canvas_section(canvas_id, chat_id, target_section)

                    if not result.get("section_found"):
                        tool_result = {
                            "success": False,
                            "error": f"Section '{target_section}' not found in canvas {canvas_id}"
                        }
                    else:
                        tool_result = {
                            "success": True,
                            "id": result["canvas_id"],
                            "section": result["section_read"],
                            "char_count": result["char_count"],
                            "content": result.get("content", ""),
                            "message": "Content available for current turn only. Call read_canvas again to reference in later turns."
                        }

                    # Store content separately (not in conversation history)
                    read_content = result.get("content", "")

                except Exception as e:
                    tool_result = {"success": False, "error": str(e)}
                    read_content = ""

                # Log completion
                duration = time.time() - t0
                log_tool_call(fn_name, args, tool_result, duration_s=duration, chat_id=chat_id)
                yield f"data: {json.dumps({'__tool_result__': True, 'tool_call_id': tc['id'], 'name': fn_name, 'result': tool_result})}\n\n"

                messages_to_send.append({
                    "role": "tool",
                    "tool_call_id": tc['id'],
                    "name": fn_name,
                    "content": json.dumps(tool_result) if isinstance(tool_result, dict) else str(tool_result)
                })

                # Store content in a special key for frontend handling (not persisted)
                yield f"data: {json.dumps({'__read_canvas_content__': read_content, 'tool_call_id': tc['id']})}\n\n"
                has_real_tools = True
            elif fn_name == "read_file":
                # Handle the read_file tool
                t0 = time.time()
                file_id = args.get("file_id")
                query = args.get("query")

                if not file_id:
                    tool_result = {"success": False, "error": "file_id is required"}
                    messages_to_send.append({
                        "role": "tool", "tool_call_id": tc['id'], "name": fn_name,
                        "content": json.dumps(tool_result)
                    })
                    duration = time.time() - t0
                    log_tool_call(fn_name, args, tool_result, duration_s=duration, chat_id=chat_id)
                    continue

                try:
                    metadata = file_manager.get_file(file_id)

                    if not metadata:
                        tool_result = {"success": False, "error": f"File not found: {file_id}"}
                    else:
                        # RAG is enabled for text-based files
                        if config.FILE_RAG_ENABLED and metadata.content_text:
                            if query:
                                # Query mode: Use file_rag to find relevant chunks
                                rag_results = file_rag.retrieve_for_file(file_id, query, n_results=5) if file_rag else []

                                if rag_results:
                                    # Build context from chunks, respecting token limit
                                    rag_context = "\n\n".join([
                                        f"[Chunk {r['metadata']['chunk_index']}] {r['text']}"
                                        for r in rag_results
                                    ])
                                    # Truncate to token limit
                                    truncated_context = rag_context[:config.READ_FILE_CONTENT_LIMIT]
                                    # Remove embeddings from rag_results for JSON serialization
                                    rag_results_for_response = [
                                        {k: v for k, v in r.items() if k != 'embedding'}
                                        for r in rag_results
                                    ]
                                    tool_result = {
                                        "success": True,
                                        "file_id": file_id,
                                        "filename": metadata.original_filename,
                                        "rag_results": rag_results_for_response,
                                        "rag_context": truncated_context,
                                        "message": f"Found {len(rag_results)} relevant chunks (showing top results, truncated to {config.READ_FILE_CONTENT_LIMIT} chars)"
                                    }
                                else:
                                    tool_result = {
                                        "success": True,
                                        "file_id": file_id,
                                        "filename": metadata.original_filename,
                                        "rag_context": "",
                                        "message": "No relevant chunks found in the file"
                                    }
                            else:
                                # Full content mode: Return full content with truncation
                                content = metadata.content_text
                                truncated_content = content[:config.READ_FILE_CONTENT_LIMIT]
                                if len(content) > config.READ_FILE_CONTENT_LIMIT:
                                    message = f"File '{metadata.original_filename}' loaded ({len(content)} chars, truncated to {config.READ_FILE_CONTENT_LIMIT})"
                                else:
                                    message = f"File '{metadata.original_filename}' loaded ({len(content)} chars)"
                                tool_result = {
                                    "success": True,
                                    "file_id": file_id,
                                    "filename": metadata.original_filename,
                                    "content": truncated_content,
                                    "message": message
                                }
                        else:
                            # For images or files without text, provide metadata only
                            tool_result = {
                                "success": True,
                                "file_id": file_id,
                                "filename": metadata.original_filename,
                                "mime_type": metadata.mime_type,
                                "file_size": metadata.file_size,
                                "message": "This file does not have extractable text content."
                            }

                except Exception as e:
                    import traceback
                    error_details = {
                        "error": str(e),
                        "traceback": traceback.format_exc(),
                        "file_id": file_id,
                        "query": query
                    }
                    tool_result = {"success": False, "error": str(e)}
                    # Log the full error for debugging
                    log_event("read_file_error", error_details)

                duration = time.time() - t0
                log_tool_call(fn_name, args, tool_result, duration_s=duration, chat_id=chat_id)
                yield f"data: {json.dumps({'__tool_result__': True, 'tool_call_id': tc['id'], 'name': fn_name, 'result': tool_result})}\n\n"

                messages_to_send.append({
                    "role": "tool", "tool_call_id": tc['id'], "name": fn_name,
                    "content": json.dumps(tool_result) if isinstance(tool_result, dict) else str(tool_result)
                })
                has_real_tools = True
            elif fn_name == "initiate_research_plan":
                topic = args.get("topic")
                edits = args.get("edits")
                t0 = time.time()

                # Import locally to avoid circular dependencies
                from backend.agents.research import generate_research_response
                
                # We call generate_research_response with approved_plan=None.
                # It will run Scout and Planner, then stop and return the XML plan.
                research_gen = generate_research_response(
                    api_url=api_url,
                    model=model,
                    messages=messages, # Original messages for context
                    approved_plan=None,
                    chat_id=chat_id,
                    search_depth_mode=search_depth_mode,
                    vision_model=extra_body.get("visionModel"),
                    model_name=model,
                    api_key=api_key,
                    edits=edits,
                    topic_override=topic,
                    resume_state=resume_state,
                    vision_enabled=extra_body.get("visionEnabled", True)
                )
                plan_result = ""
                plan_reasoning = ""
                async for chunk in research_gen:
                    # Intercept planning activities to show them in the thought process wrapper 
                    # instead of the live activity feed.
                    if chunk.startswith("data: "):
                        try:
                            chunk_data = json.loads(chunk[6:])
                            delta = chunk_data['choices'][0]['delta']
                            if 'reasoning_content' in delta:
                                plan_reasoning += delta['reasoning_content']
                                try:
                                    parsed_act = json.loads(delta['reasoning_content'])
                                    if parsed_act.get('__research_activity__') and parsed_act.get('type') == 'planning':
                                        msg = parsed_act['data'].get('message', '')
                                        # Yield as standard reasoning to show in thought bubble
                                        yield f"data: {create_chunk(model, reasoning=f'\n🔍 {msg}\n')}\n\n"
                                        continue
                                except:
                                    pass
                        except:
                            pass
                    if chunk.startswith("data: "):
                        try:
                            # Direct manipulation of the raw JSON string to be fast
                            chunk = chunk.replace('"choices":', '"internal": true, "choices":')
                        except:
                            pass
                    yield chunk
                    
                    # Accumulate for tool result (we only care about the final XML or result)
                    try:
                        if chunk.startswith("data: "):
                            chunk_data = json.loads(chunk[6:])
                            delta = chunk_data['choices'][0]['delta']
                            content = delta.get('content', '')
                            if content:
                                plan_result += content
                    except:
                        pass

                messages_to_send.append({
                    "role": "tool", "tool_call_id": tc['id'], "name": fn_name,
                    "content": plan_result
                })
                
                duration = time.time() - t0
                log_tool_call(fn_name, args, plan_result, duration_s=duration, chat_id=chat_id)
                yield f"data: {json.dumps({'__tool_result__': True, 'tool_call_id': tc['id'], 'name': fn_name, 'result': plan_result})}\n\n"
                
                # 5. FINALIZATION: Sync the manual research result into full_content 
                # and stop the turn. We don't want the AI to "render" the plan again.
                full_content += plan_result
                full_reasoning += current_reasoning
                
                yield "data: [DONE]\n\n"
                
                # Persistence Fix: Update the assistant message that made the tool call with the plan result
                # since it was streamed directly to the frontend under that assistant bubble
                for m in reversed(messages_to_send):
                    if m.get('role') == 'assistant' and tc in m.get('tool_calls', []):
                        m_content = m.get('content') or ""
                        if plan_reasoning:
                            m_content += f"\n<think>\n{plan_reasoning}\n</think>\n"
                        m_content += plan_result
                        m['content'] = m_content
                        break
                
                # Persistence Fix: We must yield the transaction messages to save the tool result!
                clean_messages = filter_bloated_tool_results(messages_to_send)
                for msg in clean_messages:
                    if msg.get('role') == 'assistant' and 'model' not in msg:
                        msg['model'] = model
                yield f"__TRANSACTION_MESSAGES__:{json.dumps(clean_messages)}"
                return
            elif fn_name == "get_time":
                t0 = time.time()
                current_time = get_current_time()
                messages_to_send.append({
                    "role": "tool", "tool_call_id": tc['id'], "name": fn_name,
                    "content": current_time
                })
                
                duration = time.time() - t0
                log_tool_call(fn_name, args, current_time, duration_s=duration, chat_id=chat_id)
                yield f"data: {json.dumps({'__tool_result__': True, 'tool_call_id': tc['id'], 'name': fn_name, 'result': current_time})}\n\n"
                has_real_tools = True
            else:
                # Unrecognized or garbled tool call — return error so the
                # message history stays valid (every tool_call needs a result).
                log_event("tool_call_unrecognized", {"fn_name": fn_name, "chat_id": chat_id})
                err_log = f"Unrecognized tool: {fn_name}\n"
                # Stream to UI, do not append to history
                yield f"data: {create_chunk(model, reasoning=err_log)}\n\n"
                messages_to_send.append({
                    "role": "tool",
                    "tool_call_id": tc['id'],
                    "name": fn_name,
                    "content": f"ERROR: Unrecognized tool '{fn_name}'. This tool does not exist. Check your available tools and try again with a valid tool name."
                })
                has_real_tools = True

        # --- 4d. Snapshot prefix for redact reconstruction ---
        tool_flow_prefix = full_content
        reasoning_flow_prefix = full_reasoning

        # --- 4e. Send follow-up request ---
        if has_real_tools:
            payload["messages"] = strip_research_artifacts(list(messages_to_send))
            if tool_round >= MAX_TOOL_ROUNDS:
                payload.pop("tools", None)
                payload.pop("tool_choice", None)
            
            # 5. Second LLM Call (Validation & Response)
            start_time_val = time.time()
            current_content = ""
            current_reasoning = ""
            tool_calls = []

            async for chunk_str, final_state in _stream_and_accumulate(api_url, model, payload, chat_id=chat_id, chat_template_kwargs=chat_template_kwargs):
                if chunk_str:
                    yield chunk_str
                else:
                    current_content, current_reasoning, tool_calls = final_state

            full_content += current_content
            full_reasoning += current_reasoning
            # Only the final LLM call's content is subject to validation
            validatable_content = current_content
        else:
            break

    # ==================== 6. OUTPUT FORMAT VALIDATION & HEALING ====================
    # Validate ONLY the last LLM response, not the accumulated multi-turn blob.
    validation_errors = validate_output_format(validatable_content, current_reasoning)
    
    if validation_errors:
        error_codes = [e['code'] for e in validation_errors]
        log_event("validation_triggered", {"chat_id": chat_id, "errors": error_codes})
        
        # --- Phase 1: Redact and re-stream preserved prefix ---
        yield f"data: {json.dumps({'__redact__': True, 'message': 'Formatting issue detected. Correcting...','__reset_accumulator__': True})}\n\n"
        
        # Re-stream the tool flow prefix so the frontend preserves first reasoning + tool logs
        if tool_flow_prefix or reasoning_flow_prefix:
            for chunk in _stream_corrected_content(model, tool_flow_prefix, fixed_reasoning=reasoning_flow_prefix):
                yield chunk
        
        validation_tool_schema = [{
            "type": "function",
            "function": {
                "name": "validate_output_format",
                "description": "Validates the output format and allows the assistant to propose corrections.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        }]
        
        # Merge existing tools with the validation tool if any exist
        current_tools = payload.get("tools", [])
        if not isinstance(current_tools, list):
            current_tools = []
        combined_tools = current_tools + validation_tool_schema

        # Skip Splice attempt if response was completely empty (nothing to splice into)
        can_splice = 'NO_OUTPUT' not in error_codes and validatable_content.strip()
        
        # --- Phase 2: Ask AI for contextual splice fixes (non-streaming) ---
        fix_applied = False
        if can_splice:
            fix_messages = build_fix_messages(strip_research_artifacts(list(messages_to_send)), validatable_content, validation_errors)
            fix_payload = {
                "model": model,
                "messages": fix_messages,
                "tools": combined_tools,
                **extra_body
            }
            log_event("validation_fix_attempt", {"chat_id": chat_id, "strategy": "contextual_splice"})
            t0 = time.time()
            fix_response = chat_completion(api_url, fix_payload, chat_id=chat_id)
            # Log is handled inside chat_completion
            
            if fix_response:
                fixes = parse_fixes(fix_response)
                if fixes:
                    log_event("validation_fixes_parsed", {"chat_id": chat_id, "count": len(fixes)})
                    locations = find_fix_locations(validatable_content, fixes)
                    if locations:
                        fixed_content = apply_fixes(validatable_content, locations)
                        
                        # Re-validate the fixed content
                        recheck_errors = validate_output_format(fixed_content, current_reasoning)
                        if not recheck_errors:
                            log_event("validation_fix_success", {"chat_id": chat_id})
                            validatable_content = fixed_content
                            full_content = tool_flow_prefix + fixed_content
                            fix_applied = True
                            
                            # Stream the corrected second response
                            for chunk in _stream_corrected_content(model, fixed_content, fixed_reasoning=current_reasoning):
                                yield chunk
                        else:
                            log_event("validation_fix_failure", {"chat_id": chat_id, "reason": "recheck_failed", "errors": [e['code'] for e in recheck_errors]})
                    else:
                        log_event("validation_fix_failure", {"chat_id": chat_id, "reason": "splice_points_not_found"})
                else:
                    log_event("validation_fix_failure", {"chat_id": chat_id, "reason": "no_fixes_parsed"})
        else:
            log_event("validation_skip_splice", {"chat_id": chat_id, "reason": "no_output_for_anchor"})
        
        # --- Phase 3: Fallback — full regeneration ---
        if not fix_applied:
            log_event("validation_fallback", {"chat_id": chat_id, "strategy": "full_regeneration"})
            regen_messages = build_regeneration_messages(strip_research_artifacts(list(messages_to_send)), validation_errors)
            regen_payload = {
                "model": model,
                "messages": regen_messages,
                "stream": True,
                "tools": combined_tools,
                **extra_body
            }
            
            validatable_content = ""
            
            async for sse_chunk, final_state in _stream_and_accumulate(api_url, model, regen_payload, chat_template_kwargs=chat_template_kwargs):
                if final_state is not None:
                    validatable_content, regen_reasoning, _ = final_state
                    full_content = tool_flow_prefix + validatable_content
                    full_reasoning = reasoning_flow_prefix + regen_reasoning
                elif sse_chunk is not None:
                    yield sse_chunk
            
            final_errors = validate_output_format(validatable_content, full_reasoning)
            if final_errors:
                log_event("validation_final_failure", {"chat_id": chat_id, "errors": [e['code'] for e in final_errors]})
                # --- Phase 4: Give up — apologize ---
                yield f"data: {json.dumps({'__redact__': True, 'message': '','__reset_accumulator__': True})}\n\n"
                # Re-stream prefix one more time after second redact
                if tool_flow_prefix:
                    for chunk in _stream_corrected_content(model, tool_flow_prefix):
                        yield chunk
                error_msg = "I apologize, but I encountered a persistent formatting issue and was unable to generate a proper response. Please try asking your question again."
                validatable_content = error_msg
                full_content = tool_flow_prefix + error_msg
                yield f"data: {create_chunk(model, content=error_msg)}\n\n"
            else:
                log_event("validation_final_success", {"chat_id": chat_id})

    yield "data: [DONE]\n\n"

    # Append final assistant message with current turn's reasoning + content to messages_to_send
    final_assistant_content = current_content
    if current_reasoning:
        final_assistant_content = f"<think>\n{current_reasoning}\n</think>\n{current_content}"

    # Only append if we have content
    if final_assistant_content:
        # Check if the last message in messages_to_send is an assistant message
        # that we just added in the tool loop but didn't have content for yet.
        if messages_to_send and messages_to_send[-1].get('role') == 'assistant' and not messages_to_send[-1].get('content') and not messages_to_send[-1].get('tool_calls'):
             # Replace the empty placeholder with real content
             messages_to_send[-1]['content'] = final_assistant_content
        else:
            messages_to_send.append({
                "role": "assistant",
                "content": final_assistant_content,
                "tool_calls": []
            })

    # Prepare messages for atomic persistence (clean filtering for DB)
    clean_messages = filter_bloated_tool_results(messages_to_send)

    # Add model field to assistant messages if not present
    for msg in clean_messages:
        if msg.get('role') == 'assistant' and 'model' not in msg:
            msg['model'] = model

    # Yield messages for atomic persistence
    yield f"__TRANSACTION_MESSAGES__:{json.dumps(clean_messages)}"


async def inject_previews_before_latest_user(messages, chat_id):
    """
    Inject preview_canvases tool call and response before latest user message.

    Args:
        messages: List of conversation messages
        chat_id: The chat identifier

    Returns:
        Messages with preview tool call/response injected before latest user
    """
    if not chat_id:
        return messages

    try:
        canvases = await get_chat_canvases_with_details(chat_id, include_content=False)
    except Exception:
        return messages

    if not canvases:
        return messages

    # Format as tool response (inventory_data format)
    inventory_data = []
    for c in canvases:
        inventory_data.append({
            "id": c['id'],
            "title": c['title'],
            "preview": c.get('preview', '')
        })

    # Find the LAST user message
    latest_user_index = -1
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get('role') == 'user':
            latest_user_index = i
            break

    call_id = f"auto_preview_{int(time.time())}"

    # If no user message found, inject at the beginning (new chat case)
    if latest_user_index == -1:
        messages.insert(0, {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": call_id,
                "type": "function",
                "function": {
                    "name": "preview_canvases",
                    "arguments": "{}"
                }
            }]
        })
        messages.insert(1, {
            "role": "tool",
            "tool_call_id": call_id,
            "name": "preview_canvases",
            "content": json.dumps(inventory_data)
        })
    else:
        # Insert tool call (assistant role) before user message
        messages[latest_user_index:latest_user_index] = [{
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": call_id,
                "type": "function",
                "function": {
                    "name": "preview_canvases",
                    "arguments": "{}"
                }
            }]
        }]

        # Insert tool response after the tool call
        messages[latest_user_index + 1:latest_user_index + 1] = [{
            "role": "tool",
            "tool_call_id": call_id,
            "name": "preview_canvases",
            "content": json.dumps(inventory_data)
        }]
    return messages


async def inject_file_inventory_before_latest_user(messages, chat_id, files_data):
    """
    Inject file inventory tool call and response before latest user message.

    Similar to inject_previews_before_latest_user but for uploaded files.
    The tool call is auto-injected and filtered from persistence.
    """
    if not files_data:
        return messages

    # Format file inventory
    inventory_data = []
    for f in files_data:
        inventory_data.append({
            "file_id": f['file_id'],
            "filename": f['original_filename'],
            "mime_type": f['mime_type'],
            "size": f['file_size']
        })

    # Find the LAST user message
    latest_user_index = -1
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get('role') == 'user':
            latest_user_index = i
            break

    call_id = f"auto_file_inventory_{int(time.time())}"

    # If no user message found, inject at the beginning (new chat case)
    if latest_user_index == -1:
        messages.insert(0, {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": call_id,
                "type": "function",
                "function": {
                    "name": "read_file",
                    "arguments": "{}"
                }
            }]
        })
        messages.insert(1, {
            "role": "tool",
            "tool_call_id": call_id,
            "name": "read_file",
            "content": json.dumps({
                "type": "inventory",
                "files": inventory_data,
                "message": f"{len(inventory_data)} file(s) available. Use read_file with file_id to access content."
            })
        })
    else:
        # Insert tool call (assistant role) before user message
        messages[latest_user_index:latest_user_index] = [{
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": call_id,
                "type": "function",
                "function": {
                    "name": "read_file",
                    "arguments": "{}"
                }
            }]
        }]

        # Insert tool response after the tool call
        messages[latest_user_index + 1:latest_user_index + 1] = [{
            "role": "tool",
            "tool_call_id": call_id,
            "name": "read_file",
            "content": json.dumps({
                "type": "inventory",
                "files": inventory_data,
                "message": f"{len(inventory_data)} file(s) available. Use read_file with file_id to access content."
            })
        }]

    return messages


def filter_preview_canvases_tool(messages):
    """
    Step 1 of the persistence cleanup: Identify preview, read_canvas, and file inventory tool IDs.
    Returns (skip_ids, read_canvas_ids, file_inventory_ids).
    """
    skip_ids = set()
    read_canvas_ids = set()
    file_inventory_ids = set()
    for msg in messages:
        if msg.get('role') == 'assistant':
            tool_calls = msg.get('tool_calls')
            if not tool_calls:
                continue

            # Robustly handle stringified tool_calls from history
            if isinstance(tool_calls, str):
                try:
                    tool_calls = json.loads(tool_calls)
                except (json.JSONDecodeError, TypeError):
                    tool_calls = []

            if isinstance(tool_calls, list):
                for tc in tool_calls:
                    if not isinstance(tc, dict):
                        continue
                    tc_id = tc.get('id')
                    fn_name = tc.get('function', {}).get('name')
                    if tc_id:
                        if fn_name == 'preview_canvases':
                            skip_ids.add(tc_id)
                        elif fn_name == 'read_canvas':
                            read_canvas_ids.add(tc_id)
                        elif fn_name == 'read_file' and tc_id.startswith('auto_file_inventory_'):
                            # Skip auto-injected file inventory tool calls
                            file_inventory_ids.add(tc_id)

    return skip_ids, read_canvas_ids, file_inventory_ids

def filter_bloated_tool_results(messages):
    """
    Handles all filtering and redaction for database persistence.
    """
    import copy
    import json
    
    filtered = []
    skip_ids, read_canvas_ids, file_inventory_ids = filter_preview_canvases_tool(messages)
    placeholder = ""

    # Step 2: Filter and Redact
    for msg in messages:
        role = msg.get('role')
        
        # 1. Skip system messages
        if role == 'system':
            continue
            
        # 2. Handle assistant messages (filter out individual preview tool-call metadata)
        if role == 'assistant':
            tool_calls = msg.get('tool_calls')
            if tool_calls:
                # Robustly handle stringified tool_calls from history
                if isinstance(tool_calls, str):
                    try:
                        tool_calls = json.loads(tool_calls)
                    except (json.JSONDecodeError, TypeError):
                        tool_calls = []
                
                # Filter out preview calls from this specific assistant message
                if isinstance(tool_calls, list):
                    new_calls = [tc for tc in tool_calls if isinstance(tc, dict) and tc.get('id') not in skip_ids]
                    
                    # Skip entire message if it was ONLY previews and had no text content
                    if not new_calls and not msg.get('content'):
                        continue
                    
                    msg_copy = dict(msg)
                    msg_copy['tool_calls'] = new_calls
                    filtered.append(msg_copy)
                    continue
            
        # 3. Handle tool result messages
        if role == 'tool':
            call_id = msg.get('tool_call_id')
            msg_name = str(msg.get('name') or "")
            
            # A. Skip preview results entirely (they are transient and recreated every turn)
            if call_id in skip_ids or msg_name == 'preview_canvases':
                continue

            # A2. Skip file inventory tool results (they are transient and recreated every turn)
            if call_id in file_inventory_ids or (msg_name == 'read_file' and 'auto_file_inventory' in call_id):
                continue
            
            # B. Redact read_canvas results (unconditional preservation)
            # We preserve these because every tool call MUST have a corresponding result in history
            if call_id in read_canvas_ids or "read_canvas" in msg_name:
                msg_copy = copy.copy(msg)
                content = msg.get('content')
                
                try:
                    # Redaction logic (handles JSON strings, dicts, or raw text)
                    if isinstance(content, str):
                        try:
                            # Try parsing as JSON first
                            data = json.loads(content)
                            if isinstance(data, dict) and 'content' in data:
                                data['content'] = placeholder
                                msg_copy['content'] = json.dumps(data)
                            elif not content.strip():
                                msg_copy['content'] = placeholder
                            else:
                                msg_copy['content'] = placeholder
                        except (json.JSONDecodeError, TypeError):
                            if content.strip():
                                msg_copy['content'] = placeholder
                    elif isinstance(content, dict):
                        content_copy = copy.copy(content)
                        if 'content' in content_copy:
                            content_copy['content'] = placeholder
                        msg_copy['content'] = json.dumps(content_copy)
                    elif content:
                        msg_copy['content'] = placeholder
                except Exception:
                    msg_copy['content'] = placeholder
                
                filtered.append(msg_copy)
                continue
            
            # C. Safety Preserve: Any other tool result (like manage_core_memory) MUST be preserved
            # A tool result should NEVER be dropped unless it is a preview.
            filtered.append(msg)
            continue

        # 4. Final catch-all for all other messages
        filtered.append(msg)
        
    return filtered


