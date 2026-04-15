# Chat Agent Directives

## Overview

This document describes the chat agent architecture, message handling patterns, mode configurations, and best practices for all agents working with the chat system.

## Architecture Overview

### Component Location

The chat agent is implemented in `backend/agents/chat.py` and provides the `generate_chat_response()` function as the main entry point.

### Tool Error Handling (Actual Implementation)

When a user message triggers multiple tool calls, the system uses **graceful degradation**:

```
┌─────────────────────────────────────────────────────────────────┐
│      Chat Agent Graceful Degradation Flow                       │
├─────────────────────────────────────────────────────────────────┤
│  User Message → Execute All Operations                         │
│    ├── Tool 1 (with retry)                                     │
│    ├── Tool 2 (with retry)                                     │
│    ├── Tool 3 (with retry)                                     │
│    ├── Tool 4 (with retry)                                     │
│    └── Canvas Operation (with retry)                           │
│                                                                 │
│  Each tool handles errors independently                        │
│  If a tool fails → Error sent to LLM, turn continues          │
│  User gets partial value from successful tools                 │
└─────────────────────────────────────────────────────────────────┘
```

**Rule 1: Tool errors do not fail the entire transaction**

If the user message requires 4 tool calls and one fails, the other 3 can still succeed.
When a tool fails after exhausting retries:
1. The error is formatted as a tool result
2. The error is sent to the LLM as the tool's response
3. The tool loop continues with other tools
4. The turn completes with mixed success/failure

**Rule 2: Component-level retries within graceful degradation**

Each tool operation retries up to 2 times before reporting error:

```python
# Component-level retry within graceful degradation
def execute_tool_with_retry(tool_call, max_retries=2):
    for attempt in range(max_retries + 1):
        try:
            return execute_tool(tool_call)
        except TransientError:
            if attempt == max_retries:
                raise  # Component failed, error sent to LLM
            time.sleep(backoff(attempt))
```

- Component retry happens **within** the tool operation
- If component exhausts retries → error sent to LLM, turn continues
- Partial success is reported to user via successful tools

**Note:** Research mode follows a different pattern - per-step resilience with 3 attempts per LLM call, then section failure if all attempts fail. This aligns with research's need for data completeness.

### Chat Flow Architecture

The chat agent follows a multi-phase flow:

```
┌─────────────────────────────────────────────────────────────┐
│              Chat Agent Flow                               │
├─────────────────────────────────────────────────────────────┤
│  Phase 1: Setup & Context                                  │
│    - Initialize MCP clients (Tavily, Playwright)          │
│    - Filter and configure tools                           │
│    - Build system prompt with mode-specific guidance      │
│    - Manage canvas inventory                              │
│                                                            │
│  Phase 2: First LLM Call                                   │
│    - Stream content, reasoning, and tool calls          │
│    - Accumulate full response state                       │
│                                                            │
│  Phase 3: Tool Execution Loop                              │
│    - Execute tool calls (up to MAX_TOOL_ROUNDS=8)       │
│    - Stream tool results and reasoning                  │
│    - Append results to message history                    │
│                                                            │
│  Phase 4: Second LLM Call                                  │
│    - Validate output format                               │
│    - Apply fixes or regenerate if needed                │
│                                                            │
│  Phase 5: Finalization                                     │
│    - Stream corrected content (if validation applied)   │
│    - Yield DONE signal                                    │
└─────────────────────────────────────────────────────────────┘
```

## Function Signature

### generate_chat_response()

Main entry point for chat interactions.

```python
async def generate_chat_response(
    api_url,              # LLM API endpoint
    model,                # Model name for responses
    messages,             # Message history
    extra_body,           # Additional parameters (visionModel, etc.)
    rag=None,             # RAG manager for memory (optional)
    memory_mode=False,    # Enable memory mode
    search_depth_mode='regular',  # 'regular' or 'deep'
    chat_id=None,         # Chat identifier
    has_vision=False,     # Enable vision capabilities
    api_key=None,         # API key for LLM
    research_mode=False,  # Enable research mode
    research_completed=False,  # Research already completed
    initial_tool_calls=None,  # Pre-existing tool calls
    resume_state=None,    # State for resuming interrupted chats
    canvas_mode=False,    # Enable canvas mode
    active_canvas_context=None  # Current active canvas
) -> Generator[str, None, None]
```

**Returns:** Generator yielding SSE chunks for streaming.

## Modes

### Memory Mode

Enables core memory management via RAG.

**Enables:**
- `MANAGE_CORE_MEMORY_TOOL` in available tools
- `MEMORY_SYSTEM_PROMPT` instead of base prompt
- Memory store injection into system prompt
- Memory limit enforcement

**Rule 4: Enforce memory limits in memory mode**

Memory operations are limited per turn:

```python
# Configurable limits
additions = additions[:config.MEMORY_MAX_ADD_PER_TURN]
edits = edits[:config.MEMORY_MAX_EDIT_PER_TURN]
deletions = deletions[:config.MEMORY_MAX_DELETE_PER_TURN]
```

**Rule 5: Memory operations are logged**

Each memory operation logs:
- Number of additions, edits, deletions
- Success/failure for each operation
- Assigned IDs for new memories

### Research Mode

Enables research planning capabilities.

**Enables:**
- `INITIATE_RESEARCH_PLAN_TOOL` in available tools
- `RESEARCH_MODE_GUIDANCE` in system prompt
- Research-specific flow handling

**Rule 6: Research mode tools removed on completion**

When `research_completed=True`, the `initiate_research_plan` tool is filtered out:

```python
if research_completed:
    tools = [t for t in tools if t.get('function', {}).get('name') != 'initiate_research_plan']
```

### Canvas Mode

Enables canvas document management.

**Enables:**
- `MANAGE_CANVAS_TOOL` in available tools
- `CANVAS_MODE_GUIDANCE` in system prompt
- Canvas inventory in context
- Active canvas context injection

**Rule 7: Canvas inventory is limited to 200 chars preview**

Canvas inventory uses truncated previews:

```python
content_preview = (canvas.get('content', '')[:200] or 'empty')
```

**Rule 8: Active canvas context is limited to CANVAS_ACTIVE_CONTEXT_CHAR_LIMIT**

```python
active_canvas_context['content'][:config.CANVAS_ACTIVE_CONTEXT_CHAR_LIMIT]
```

### Vision Mode

Enables image processing capabilities.

**Behavior:**
- `has_vision=True` enables image search
- System prompt indicates capability status
- Images are returned in search results when enabled

**Rule 9: Check has_vision before processing images**

```python
if not has_vision:
    v_note += "You CANNOT process images."
else:
    v_note += "You CAN process images. The search tool will automatically return images where relevant."
```

## Tool Handling

### Available Tools

The chat agent supports the following tools:

| Tool Name | Purpose | Mode |
|-----------|---------|------|
| `get_time` | Get current time | All modes |
| `validate_output_format` | Output validation (auto-called) | All modes |
| `manage_core_memory` | Memory management | Memory mode |
| `initiate_research_plan` | Research planning | Research mode |
| `manage_canvas` | Canvas management | Canvas mode |
| `search_web` | Web search (MCP) | All modes |
| `audit_search` | Search audit (MCP) | Regular search |
| `visit_page_tool` | Page visit (MCP) | All modes |

### Tool Restrictions

**Rule 10: validate_output_format is forbidden to call manually**

The `validate_output_format` tool is invoked automatically by the system after every response to check formatting. If the LLM attempts to call it:

```python
if fn_name == "validate_output_format":
    messages_to_send.append({
        "role": "tool",
        "tool_call_id": tc['id'],
        "name": fn_name,
        "content": "ERROR: You are FORBIDDEN from calling this tool. It is invoked automatically by the system. Do not attempt to call it again. Continue with your normal response."
    })
```

**Tool Description (from code):** "SYSTEM-ONLY TOOL — you are FORBIDDEN from calling this tool. It runs automatically after every response to check formatting. If issues are found, you will receive a tool result describing each issue and asking you to output <fix> blocks. Each <fix> block must contain <prefix> (the ~50 tokens before the fix point, copied exactly from your response), <correction> (the fix itself), and <suffix> (the ~50 tokens after the fix point, copied exactly from your response). If the fix point is near the start or end of your response, use whatever tokens are available instead of inventing tokens. Output ONLY the <fix> blocks with no commentary."

### Tool Execution Flow

**Rule 11: Each tool call is logged with timing**

```python
t0 = time.time()
# ... tool execution ...
duration = time.time() - t0
log_tool_call(fn_name, args, result, duration_s=duration, chat_id=chat_id)
```

**Rule 12: Tool errors are logged and reported**

```python
except Exception as e:
    search_result = f"ERROR: MCP Tool '{tool_name}' failed: {str(e)}"
    log_tool_call(fn_name, args, search_result, duration_s=duration, chat_id=chat_id)
    log_event("tool_execution_error", {"tool": tool_name, "error": str(e), "chat_id": chat_id})
```

### MCP Tools

MCP tools are fetched dynamically and filtered:

```python
# Filter only chat-facing tools
chat_mcp_tool_names = ["search_web", "audit_search", "visit_page_tool"]
mcp_tools = [mt for mt in mcp_tools_raw if mt.name in chat_mcp_tool_names]
```

**Rule 13: Deep search mode uses modified search_web description**

When `search_depth_mode == 'deep'`, the search tool description is modified:

```python
if search_depth_mode == 'deep':
    deep_tool["function"]["description"] = "Performs a web search using Tavily to find information on a topic. Results include an AI-summarized answer and the FULL RAW text content of the primary pages. Use this tool ONCE for maximum information depth."
```

## Streaming Pattern

### SSE Format

The chat agent yields Server-Sent Events in the following formats:

1. **Standard content chunks:**
   ```
   data: {"choices": [...], "delta": {"content": "..."}, ...}
   ```

2. **Reasoning chunks:**
   ```
   data: {"choices": [...], "delta": {"reasoning_content": "..."}, ...}
   ```

3. **Tool call markers:**
   ```
   data: {"__assistant_tool_calls__": True, "content": "...", "tool_calls": [...]}
   ```

4. **Tool result markers:**
   ```
   data: {"__tool_result__": True, "tool_call_id": "...", "name": "...", "result": "..."}
   ```

5. **Canvas update markers:**
   ```
   data: {"__canvas_update__": {"action": "...", "id": "...", "title": "...", "content": "..."}}
   ```

6. **Redact markers:**
   ```
   data: {"__redact__": True, "message": "Formatting issue detected. Correcting...", "__reset_accumulator__": true}
   ```

7. **Done signal:**
   ```
   data: [DONE]
   ```

### Streaming Functions

**_stream_and_accumulate()**

Streams and accumulates LLM response state:

```python
async def _stream_and_accumulate(api_url, model, payload, chat_id=None):
    """
    Yields:
      (chunk_string, None) for each SSE chunk
      (None, (full_content, full_reasoning, tool_calls)) at end
    """
```

**_stream_corrected_content()**

Re-streams corrected content in chunks:

```python
def _stream_corrected_content(model, fixed_content, fixed_reasoning=""):
    """
    Splits content into CHUNK_SIZE=50 character chunks.
    """
```

## Context Management

### Message History

**Rule 14: Only last 20 messages are kept in history**

```python
messages_to_send.extend(history[-20:])
```

### System Prompt Construction

**Rule 15: Date is prepended to system prompt**

```python
today_date = datetime.date.today().strftime("%A, %B %d, %Y")
system_prompt = f"Today's date is: {today_date}.\n\n" + system_prompt
```

### Canvas Context Injection

When canvas mode is active with an active canvas:

```python
if active_canvas_context and canvas_mode:
    canvas_ctx = f"""
### ACTIVE CANVAS ###
Canvas ID: {active_canvas_context['id']}
Content:
---
{active_canvas_context['content'][:config.CANVAS_ACTIVE_CONTEXT_CHAR_LIMIT]}
---
### END ACTIVE CANVAS ###
"""
    messages_to_send[0]["content"] += canvas_ctx
```

## Output Validation & Healing

### Validation Flow

The chat agent implements a multi-phase validation and healing process:

```
┌─────────────────────────────────────────────────────────────┐
│           Output Validation Flow                           │
├─────────────────────────────────────────────────────────────┤
│  Phase 1: Validate last LLM response                       │
│  Phase 2: Contextual splice fixes                          │
│  Phase 3: Full regeneration fallback                       │
│  Phase 4: Apologize if all fixes fail                      │
└─────────────────────────────────────────────────────────────┘
```

### Validation Phases

**Phase 1: Validation Check**

```python
validation_errors = validate_output_format(validatable_content, current_reasoning)
```

**Phase 2: Contextual Splice Fixes**

```python
fix_messages = build_fix_messages(messages_to_send, validatable_content, validation_errors)
fix_response = chat_completion(api_url, fix_payload, chat_id=chat_id)
fixes = parse_fixes(fix_response)
locations = find_fix_locations(validatable_content, fixes)
fixed_content = apply_fixes(validatable_content, locations)
```

**Phase 3: Full Regeneration**

```python
regen_messages = build_regeneration_messages(messages_to_send, validation_errors)
regen_payload = {"model": model, "messages": regen_messages, ...}
validatable_content, regen_reasoning, _ = _stream_and_accumulate(...)
```

**Phase 4: Apologize**

```python
if final_errors:
    error_msg = "I apologize, but I encountered a persistent formatting issue..."
    validatable_content = error_msg
    full_content = tool_flow_prefix + error_msg
```

**Rule 16: Only the last LLM call's content is validated**

```python
# Only the final LLM call's content is subject to validation
validatable_content = current_content
```

## Tool Round Limits

**Rule 17: Maximum 8 tool rounds**

```python
MAX_TOOL_ROUNDS = 8  # Configurable via MAX_TOOL_ROUNDS env variable
tool_round = 0
while tool_calls and tool_round < MAX_TOOL_ROUNDS:
    tool_round += 1
    # ... tool execution ...
```

After 8 rounds, tools are removed from the payload to force a final response:

```python
if tool_round >= MAX_TOOL_ROUNDS:
    payload.pop("tools", None)
    payload.pop("tool_choice", None)
```

## State Management

### Content Accumulation

```python
# Variables for tracking content
full_content = ""      # Accumulated for storage
full_reasoning = ""    # Accumulated reasoning
validatable_content = "" # Only last LLM call for validation
tool_flow_prefix = ""  # Snapshot for redact reconstruction
reasoning_flow_prefix = "" # Reasoning snapshot
```

### Tool Call State

```python
tool_calls = initial_tool_calls or []
current_tool_call = None
```

### History Building

Assistant messages include reasoning in <think> tags:

```python
assistant_content_for_history = current_content
if current_reasoning:
    assistant_content_for_history = f"<think>\n{current_reasoning}\n</think>\n{current_content}"
```

## MCP Client Management

### Client Connection

**Rule 18: MCP clients are connected at start**

```python
await tavily_client.connect()
await playwright_client.connect()
```

### Tool Fetching

MCP tools are fetched at runtime and filtered:

```python
tavily_tools_raw = await tavily_client.get_available_tools()
playwright_tools_raw = await playwright_client.get_available_tools()
mcp_tools_raw = tavily_tools_raw + playwright_tools_raw
```

## Error Handling

### Tool Execution Errors

**Rule 19: Tool errors are logged and reported to LLM**

```python
except Exception as e:
    search_result = f"ERROR: MCP Tool '{tool_name}' failed: {str(e)}"
    log_tool_call(fn_name, args, search_result, duration_s=duration, chat_id=chat_id)
    log_event("tool_execution_error", {"tool": tool_name, "error": str(e), "chat_id": chat_id})
```

### Unrecognized Tools

**Rule 20: Unrecognized tools are reported as errors**

```python
else:
    log_event("tool_call_unrecognized", {"fn_name": fn_name, "chat_id": chat_id})
    messages_to_send.append({
        "role": "tool",
        "tool_call_id": tc['id'],
        "name": fn_name,
        "content": f"ERROR: Unrecognized tool '{fn_name}'. This tool does not exist..."
    })
```

### Validation Failures

**Rule 21: Validation failures trigger healing flow**

```python
if validation_errors:
    log_event("validation_triggered", {"chat_id": chat_id, "errors": error_codes})
    # Initiate healing flow
```

## Best Practices

### 1. Always Use Streaming

The chat agent is designed for streaming. Never block on LLM calls.

```python
# Good: Streaming
async for chunk_str, final_state in _stream_and_accumulate(...):
    if chunk_str:
        yield chunk_str
```

### 2. Log Tool Calls with Timing

Always log tool execution with timing information.

```python
t0 = time.time()
result = execute_tool(args)
duration = time.time() - t0
log_tool_call(fn_name, args, result, duration_s=duration)
```

### 3. Handle Tool Errors Gracefully

Never let tool errors crash the agent.

```python
try:
    result = execute_tool(args)
except Exception as e:
    result = f"ERROR: Tool failed: {str(e)}"
    log_event("tool_execution_error", {"tool": fn_name, "error": str(e)})
```

### 4. Use Appropriate Modes

Enable only the modes you need to reduce complexity.

```python
# Only enable memory mode if needed
if memory_mode:
    tools.append(MANAGE_CORE_MEMORY_TOOL)
```

### 5. Respect Tool Round Limits

Don't try to bypass MAX_TOOL_ROUNDS.

```python
# Safe: Respect limit
while tool_calls and tool_round < MAX_TOOL_ROUNDS:
    # ...
```

## Functions Reference

### Main Entry Point

| Function | Purpose | Returns |
|----------|---------|---------|
| `generate_chat_response(...)` | Main chat handler | SSE generator |

### Internal Functions

| Function | Purpose | Returns |
|----------|---------|---------|
| `_stream_and_accumulate(...)` | Stream and accumulate state | (chunk, state) pairs |
| `_stream_corrected_content(...)` | Stream corrected content | SSE chunks |

## Appendix: Complete Flow Example

```python
async def example_chat_flow():
    # Initialize
    await tavily_client.connect()
    await playwright_client.connect()

    # Build tools and prompts based on mode
    tools = [GET_TIME_TOOL, VALIDATE_OUTPUT_FORMAT_TOOL]
    system_prompt = BASE_SYSTEM_PROMPT

    if memory_mode:
        tools.append(MANAGE_CORE_MEMORY_TOOL)
        system_prompt = MEMORY_SYSTEM_PROMPT

    # Send to LLM
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}],
        "stream": True,
        "tools": tools
    }

    # Stream and accumulate
    async for chunk_str, final_state in _stream_and_accumulate(api_url, model, payload):
        if chunk_str:
            yield chunk_str
        else:
            current_content, current_reasoning, tool_calls = final_state
            break

    # Execute tools if any
    for tc in tool_calls:
        # Tool execution and result streaming
        ...

    # Finalize
    yield "data: [DONE]\n\n"
```
