
import json
from backend.logger import log_event, log_tool_call
import time
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
    full_content = ""
    full_reasoning = ""
    
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
                    
                if 'function' in tc_chunk and 'arguments' in tc_chunk['function']:
                    current_tool_call['function']['arguments'] += tc_chunk['function']['arguments']
            
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
    full_reasoning = ""
    current_content = ""
    current_reasoning = ""
    tool_calls = []
    tool_flow_prefix = ""  # Preserved for redact reconstruction

    for sse_chunk, final_state in _stream_and_accumulate(api_url, model, payload):
        if final_state is not None:
            current_content, current_reasoning, tool_calls = final_state
        elif sse_chunk is not None:
            yield sse_chunk
            
    full_content += current_content
    full_reasoning += current_reasoning

    # In the no-tool-call path, validatable_content is the same as current_content.
    validatable_content = current_content

    # 4. Tool Execution Loop
    MAX_TOOL_ROUNDS = 5
    tool_round = 0
    while tool_calls and tool_round < MAX_TOOL_ROUNDS:
        tool_round += 1
        # Reconstruct full assistant message for history (with tags if reasoning exists)
        assistant_content_for_history = current_content
        if current_reasoning:
            assistant_content_for_history = f"<think>{current_reasoning}</think>\n{current_content}"

        # Build LLM history with the closed content
        messages_to_send.append({
            "role": "assistant",
            "content": assistant_content_for_history if assistant_content_for_history else None,
            "tool_calls": tool_calls
        })
        
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
                t0 = time.time()
                query = args.get("query", "...")
                log = f"Calling: search_memory(\"{query}\")\n"
                current_reasoning += log
                yield f"data: {create_chunk(model, reasoning=log)}\n\n"
                
                context_result = rag.retrieve_context(query)
                if not context_result: context_result = "No relevant results found."
                messages_to_send.append({
                    "role": "tool", "tool_call_id": tc['id'], "name": fn_name,
                    "content": f"<context>{context_result}</context>"
                })
                
                duration = time.time() - t0
                log_tool_call(fn_name, args, context_result, duration_s=duration, chat_id=chat_id)
                res_log = f"Result: {context_result}\n"
                current_reasoning += res_log
                yield f"data: {create_chunk(model, reasoning=res_log)}\n\n"
                has_real_tools = True
            elif fn_name == "search_web":
                query = args.get("query", "...")
                topic = args.get("topic", "general")
                time_range = args.get("time_range")
                start_date = args.get("start_date")
                end_date = args.get("end_date")
                include_images = args.get("include_images", False) and has_vision
                
                log = f"Calling: search_web(\"{query}\")\n"
                current_reasoning += log
                yield f"data: {create_chunk(model, reasoning=log)}\n\n"
                
                search_result, _ = execute_tavily_search(
                    query=query, topic=topic, time_range=time_range, 
                    start_date=start_date, end_date=end_date, include_images=include_images, chat_id=chat_id
                )
                messages_to_send.append({
                    "role": "tool", "tool_call_id": tc['id'], "name": fn_name,
                    "content": search_result
                })
                
                # Note: Tavily search already logs internally, but we can log the abstraction wrapper too
                # or just rely on tavily's internal `log_tool_call` which is already invoked.
                res_log = "Result: Search completed.\n"
                current_reasoning += res_log
                yield f"data: {create_chunk(model, reasoning=res_log)}\n\n"
                has_real_tools = True
            elif fn_name == "audit_search":
                t0 = time.time()
                log = "Calling: audit_search()\n"
                current_reasoning += log
                yield f"data: {create_chunk(model, reasoning=log)}\n\n"
                
                raw_result = audit_tavily_search(chat_id)
                messages_to_send.append({
                    "role": "tool", "tool_call_id": tc['id'], "name": fn_name,
                    "content": raw_result
                })
                
                duration = time.time() - t0
                log_tool_call(fn_name, args, raw_result[:500] + ("..." if len(raw_result) > 500 else ""), duration_s=duration, chat_id=chat_id)
                res_log = "Result: Audit available.\n"
                current_reasoning += res_log
                yield f"data: {create_chunk(model, reasoning=res_log)}\n\n"
                has_real_tools = True
            elif fn_name == "get_time":
                t0 = time.time()
                log = "Calling: get_time()\n"
                current_reasoning += log
                yield f"data: {create_chunk(model, reasoning=log)}\n\n"
                
                current_time = get_current_time()
                messages_to_send.append({
                    "role": "tool", "tool_call_id": tc['id'], "name": fn_name,
                    "content": current_time
                })
                
                duration = time.time() - t0
                log_tool_call(fn_name, args, current_time, duration_s=duration, chat_id=chat_id)
                res_log = f"Result: {current_time}\n"
                current_reasoning += res_log
                yield f"data: {create_chunk(model, reasoning=res_log)}\n\n"
                has_real_tools = True
            else:
                # Unrecognized or garbled tool call — return error so the
                # message history stays valid (every tool_call needs a result).
                log_event("tool_call_unrecognized", {"fn_name": fn_name, "chat_id": chat_id})
                err_log = f"Unrecognized tool: {fn_name}\n"
                current_reasoning += err_log
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

        # --- 4e. Second LLM call ---
        if has_real_tools:
            final_payload = {
                "model": model,
                "messages": list(messages_to_send),
                "tools": tools if tools else None,
                "tool_choice": "auto" if tools else None,
                "stream": True, 
                **extra_body
            }

            for sse_chunk, final_state in _stream_and_accumulate(api_url, model, final_payload):
                if final_state is not None:
                    current_content, current_reasoning, tool_calls = final_state
                    full_content += current_content
                    full_reasoning += current_reasoning
                    # Only the final LLM call's content is subject to validation
                    validatable_content = current_content
                elif sse_chunk is not None:
                    yield sse_chunk
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


