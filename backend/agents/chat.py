
import json
from backend.logger import log_event
from backend.prompts import BASE_SYSTEM_PROMPT, MEMORY_SYSTEM_PROMPT
from backend.tools import MEMORY_SEARCH_TOOL, TAVILY_SEARCH_TOOL, AUDIT_TAVILY_SEARCH_TOOL, GET_TIME_TOOL, VALIDATE_OUTPUT_FORMAT_TOOL
from backend.utils import create_chunk, execute_tavily_search, audit_tavily_search, get_current_time
from backend.llm import stream_chat_completion, chat_completion
from backend.validation import (
    validate_output_format, parse_fixes, find_fix_locations, apply_fixes,
    build_fix_messages, build_regeneration_messages
)


def _stream_and_accumulate(api_url, model, payload):
    """
    Streams a chat completion call, yielding (sse_chunk_string, final_state) tuples.
    
    During streaming: yields (chunk_string, None) for each SSE chunk.
    After streaming:  yields (None, (full_content, full_reasoning, tool_calls)) once.
    """
    tool_calls = []
    current_tool_call = None
    full_content = "<think>\n"
    
    # We maintain a flag so we can close the reasoning block if actual content starts
    # when the model uses `reasoning_content` API (like DeepSeek R1).
    reasoning_closed = False
    used_reasoning_api = False

    # Inject the <think> prefix to match the .jinja template's prefilled generation prompt
    yield (f"data: {create_chunk(model, content='<think>\n')}\n\n", None)
    
    for chunk_str in stream_chat_completion(api_url, payload):
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
                    tool_name = current_tool_call['function']['name']
                    # Don't inject anything into the content stream for tool calls.
                    # Tool info is sent via reasoning_content by generate_chat_response.
                    
                if 'function' in tc_chunk and 'arguments' in tc_chunk['function']:
                    current_tool_call['function']['arguments'] += tc_chunk['function']['arguments']
            
            elif 'content' in delta or 'reasoning_content' in delta:
                content = delta.get('content', '')
                reasoning = delta.get('reasoning_content', '') or delta.get('reasoning', '')
                
                # If the model explicitly sends reasoning_content, map it directly into the stream as content
                if reasoning:
                    used_reasoning_api = True
                    full_content += reasoning
                    yield (f"data: {create_chunk(model, content=reasoning)}\n\n", None)
                
                if content:
                    # If this is the very first time we see standard `content` after using `reasoning_content`, 
                    # we must close the `<think>` block first.
                    if used_reasoning_api and not reasoning_closed and "<think>" in full_content and "</think>" not in full_content:
                        full_content += "\n</think>\n"
                        yield (f"data: {create_chunk(model, content='\n</think>\n')}\n\n", None)
                        reasoning_closed = True
                    
                    full_content += content
                    yield (f"data: {json.dumps(chunk)}\n\n", None)
            
            if finish_reason == 'tool_calls':
                if current_tool_call:
                    tool_calls.append(current_tool_call)
                    current_tool_call = None
        except Exception:
            pass

    # Yield the final accumulated state
    yield (None, (full_content, tool_calls))


def _stream_corrected_content(model, fixed_content):
    """
    Re-stream fixed content to the frontend as SSE chunks.
    Splits the content into reasonable chunk sizes for smooth rendering.
    """
    CHUNK_SIZE = 50  # characters per chunk
    for i in range(0, len(fixed_content), CHUNK_SIZE):
        chunk_text = fixed_content[i:i + CHUNK_SIZE]
        yield f"data: {create_chunk(model, content=chunk_text)}\n\n"


def generate_chat_response(api_url, model, messages, extra_body, rag=None, memory_mode=False, chat_id=None, has_vision=False):
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
    # 1. Setup Tools & Prompts
    tools = [TAVILY_SEARCH_TOOL, AUDIT_TAVILY_SEARCH_TOOL, GET_TIME_TOOL, VALIDATE_OUTPUT_FORMAT_TOOL]
    system_prompt = BASE_SYSTEM_PROMPT
    
    if memory_mode:
        tools.append(MEMORY_SEARCH_TOOL)
        system_prompt = MEMORY_SYSTEM_PROMPT
        
    # Append Capability Notes
    v_status = "ENABLED" if has_vision else "DISABLED"
    v_note = f"\n\n# System Capabilities\n- Vision Support: {v_status}. "
    if not has_vision:
        v_note += "You CANNOT process images. If you use search_web, you must set include_images=false."
    else:
        v_note += "You CAN process images. You may use search_web with include_images=true to fetch visual context."
    system_prompt += v_note
        
    # 2. Context Management
    messages_to_send = [{"role": "system", "content": system_prompt}]
    
    user_system_msgs = [m for m in messages if m['role'] == 'system']
    history = [m for m in messages if m['role'] != 'system']
    
    if user_system_msgs:
        combined = "\n\n".join([m['content'] for m in user_system_msgs])
        messages_to_send.append({"role": "system", "content": f"### User Instructions ###\n{combined}"})

    messages_to_send.extend(history[-20:]) 

    # 3. First LLM Call
    payload = {
        "model": model,
        "messages": list(messages_to_send),
        "tools": tools if tools else None,
        "tool_choice": "auto" if tools else None,
        "stream": True,
        **extra_body
    }

    full_content = ""
    tool_calls = []
    tool_flow_prefix = ""  # Preserved for redact reconstruction

    for sse_chunk, final_state in _stream_and_accumulate(api_url, model, payload):
        if final_state is not None:
            full_content, tool_calls = final_state
        elif sse_chunk is not None:
            yield sse_chunk

    # In the no-tool-call path, validatable_content is the same as full_content.
    validatable_content = full_content

    # 4. Tool Execution Loop
    if tool_calls:
        # --- 4a. Close first <think> block if unclosed ---
        # The model may stop for tool_calls before outputting </think>.
        # Close it so the frontend has a complete first <think> block.
        if "<think>" in full_content and "</think>" not in full_content:
            close_tag = "\n</think>\n"
            full_content += close_tag
            yield f"data: {create_chunk(model, content=close_tag)}\n\n"

        # Build LLM history with the closed content
        messages_to_send.append({
            "role": "assistant",
            "content": full_content if full_content else None,
            "tool_calls": tool_calls
        })
        
        # --- 4b. Open a <think> block for tool execution logs ---
        tool_think_open = "<think>\n"
        full_content += tool_think_open
        yield f"data: {create_chunk(model, content=tool_think_open)}\n\n"

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

            if fn_name == "search_memory" and rag:
                query = args.get("query", "...")
                log = f"Calling: search_memory(\"{query}\")\n"
                full_content += log
                yield f"data: {create_chunk(model, content=log)}\n\n"
                
                context_result = rag.retrieve_context(query)
                if not context_result: context_result = "No relevant results found."
                messages_to_send.append({
                    "role": "tool", "tool_call_id": tc['id'], "name": fn_name,
                    "content": f"<context>{context_result}</context>"
                })
                
                res_log = f"Result: {context_result}\n"
                full_content += res_log
                yield f"data: {create_chunk(model, content=res_log)}\n\n"
                has_real_tools = True
            elif fn_name == "search_web":
                query = args.get("query", "...")
                topic = args.get("topic", "general")
                time_range = args.get("time_range")
                start_date = args.get("start_date")
                end_date = args.get("end_date")
                include_images = args.get("include_images", False) and has_vision
                
                log = f"Calling: search_web(\"{query}\")\n"
                full_content += log
                yield f"data: {create_chunk(model, content=log)}\n\n"
                
                search_result, _ = execute_tavily_search(
                    query=query, topic=topic, time_range=time_range, 
                    start_date=start_date, end_date=end_date, include_images=include_images, chat_id=chat_id
                )
                messages_to_send.append({
                    "role": "tool", "tool_call_id": tc['id'], "name": fn_name,
                    "content": search_result
                })
                
                res_log = "Result: Search completed.\n"
                full_content += res_log
                yield f"data: {create_chunk(model, content=res_log)}\n\n"
                has_real_tools = True
            elif fn_name == "audit_search":
                log = "Calling: audit_search()\n"
                full_content += log
                yield f"data: {create_chunk(model, content=log)}\n\n"
                
                raw_result = audit_tavily_search(chat_id)
                messages_to_send.append({
                    "role": "tool", "tool_call_id": tc['id'], "name": fn_name,
                    "content": raw_result
                })
                
                res_log = "Result: Audit available.\n"
                full_content += res_log
                yield f"data: {create_chunk(model, content=res_log)}\n\n"
                has_real_tools = True
            elif fn_name == "get_time":
                log = "Calling: get_time()\n"
                full_content += log
                yield f"data: {create_chunk(model, content=log)}\n\n"
                
                current_time = get_current_time()
                messages_to_send.append({
                    "role": "tool", "tool_call_id": tc['id'], "name": fn_name,
                    "content": current_time
                })
                
                res_log = f"Result: {current_time}\n"
                full_content += res_log
                yield f"data: {create_chunk(model, content=res_log)}\n\n"
                has_real_tools = True

        # --- 4c. Close the tool log <think> block ---
        tool_think_close = "</think>\n"
        full_content += tool_think_close
        yield f"data: {create_chunk(model, content=tool_think_close)}\n\n"

        # --- 4d. Snapshot prefix for redact reconstruction ---
        tool_flow_prefix = full_content

        # --- 4e. Second LLM call ---
        if has_real_tools:
            final_payload = {
                "model": model,
                "messages": list(messages_to_send),
                "stream": True, 
                **extra_body
            }

            for sse_chunk, final_state in _stream_and_accumulate(api_url, model, final_payload):
                if final_state is not None:
                    next_content, _ = final_state
                    full_content += next_content
                    # Only the final LLM call's content is subject to validation
                    validatable_content = next_content
                elif sse_chunk is not None:
                    yield sse_chunk

    # ==================== 5. CLEAN UP ARTIFICIAL <think> PREFIX ====================
    # _stream_and_accumulate always prepends <think>\n to match the jinja template prefill.
    # But the model may never close it (e.g., skips reasoning entirely).
    # Fix it on validatable_content; mirror to full_content.
    if "<think>" in validatable_content and "</think>" not in validatable_content:
        close_tag = "\n</think>"
        validatable_content = validatable_content.rstrip() + close_tag
        full_content = full_content.rstrip() + close_tag

    # 5.b) If the model entirely skips reasoning, remove the empty think block.
    for empty_block in ("<think>\n\n</think>", "<think>\n</think>"):
        validatable_content = validatable_content.replace(empty_block, "")
        full_content = full_content.replace(empty_block, "")

    # ==================== 6. OUTPUT FORMAT VALIDATION & HEALING ====================
    # Validate ONLY the last LLM response, not the accumulated multi-turn blob.
    full_reasoning = ""
    if "<think>" in validatable_content:
        import re
        try:
            full_reasoning = re.search(r'<think>(.*?)</think>', validatable_content, re.DOTALL).group(1)
        except:
            pass
            
    validation_errors = validate_output_format(validatable_content, full_reasoning)
    
    if validation_errors:
        error_codes = [e['code'] for e in validation_errors]
        log_event("validation_triggered", {"chat_id": chat_id, "errors": error_codes})
        
        # --- Phase 1: Redact and re-stream preserved prefix ---
        yield f"data: {json.dumps({'__redact__': True, 'message': 'Formatting issue detected. Correcting...','__reset_accumulator__': True})}\n\n"
        
        # Re-stream the tool flow prefix so the frontend preserves first reasoning + tool logs
        if tool_flow_prefix:
            for chunk in _stream_corrected_content(model, tool_flow_prefix):
                yield chunk
        
        # --- Phase 2: Ask AI for contextual splice fixes (non-streaming) ---
        fix_messages = build_fix_messages(messages_to_send, validatable_content, validation_errors)
        fix_payload = {
            "model": model,
            "messages": fix_messages,
            **extra_body
        }
        log_event("validation_fix_attempt", {"chat_id": chat_id, "strategy": "contextual_splice"})
        fix_response = chat_completion(api_url, fix_payload)
        
        fix_applied = False
        if fix_response:
            fixes = parse_fixes(fix_response)
            if fixes:
                log_event("validation_fixes_parsed", {"chat_id": chat_id, "count": len(fixes)})
                locations = find_fix_locations(validatable_content, fixes)
                if locations:
                    fixed_content = apply_fixes(validatable_content, locations)
                    
                    # Re-validate the fixed content
                    recheck_errors = validate_output_format(fixed_content, full_reasoning)
                    if not recheck_errors:
                        log_event("validation_fix_success", {"chat_id": chat_id})
                        validatable_content = fixed_content
                        full_content = tool_flow_prefix + fixed_content
                        fix_applied = True
                        
                        # Stream the corrected second response
                        for chunk in _stream_corrected_content(model, fixed_content):
                            yield chunk
                    else:
                        log_event("validation_fix_failure", {"chat_id": chat_id, "reason": "recheck_failed", "errors": [e['code'] for e in recheck_errors]})
                else:
                    log_event("validation_fix_failure", {"chat_id": chat_id, "reason": "splice_points_not_found"})
            else:
                log_event("validation_fix_failure", {"chat_id": chat_id, "reason": "no_fixes_parsed"})
        
        # --- Phase 3: Fallback — full regeneration ---
        if not fix_applied:
            log_event("validation_fallback", {"chat_id": chat_id, "strategy": "full_regeneration"})
            regen_messages = build_regeneration_messages(messages_to_send, validation_errors)
            regen_payload = {
                "model": model,
                "messages": regen_messages,
                "stream": True,
                **extra_body
            }
            
            validatable_content = ""
            
            for sse_chunk, final_state in _stream_and_accumulate(api_url, model, regen_payload):
                if final_state is not None:
                    validatable_content, _ = final_state
                    full_content = tool_flow_prefix + validatable_content
                elif sse_chunk is not None:
                    yield sse_chunk
            
            # Final validation check
            full_reasoning = ""
            if "<think>" in validatable_content:
                import re
                try:
                    full_reasoning = re.search(r'<think>(.*?)</think>', validatable_content, re.DOTALL).group(1)
                except:
                    pass
                    
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


