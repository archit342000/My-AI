# Tool Directives

## Overview

This document defines the tool architecture, registration patterns, execution rules, and best practices for all agents working with tools in the system.

## Tool Architecture

### Tool Types

Tools are categorized into three types:

| Type | Description | Examples |
|------|-------------|----------|
| **Built-in Tools** | Core tools defined in tools.py | `get_time`, `manage_core_memory` |
| **MCP Tools** | Tools from Model Context Protocol servers | `search_web`, `audit_search`, `visit_page_tool` |
| **System Tools** | Auto-invoked tools, not callable by LLM | `validate_output_format` |

### Tool Registration

**Rule 1: All tools must be registered in tools.py**

Tools are defined as OpenAI-compatible function schemas:

```python
MY_TOOL = {
    "type": "function",
    "function": {
        "name": "my_tool",
        "description": "Tool description",
        "parameters": {
            "type": "object",
            "properties": {
                "param1": {"type": "string", "description": "Param description"}
            },
            "required": ["param1"]
        }
    }
}
```

**Rule 2: Tool names must be snake_case**

Tool names follow snake_case convention:

```python
# Good
"search_web", "visit_page_tool", "manage_core_memory"

# Bad
"searchWeb", "VisitPageTool", "my-tool"
```

## Available Tools

### Core Tools

#### get_time

Returns the current local date and time.

```python
GET_TIME_TOOL = {
    "type": "function",
    "function": {
        "name": "get_time",
        "description": "Returns the current local date and time...",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }
}
```

**Rule 3: Always use get_time for temporal queries**

Never rely on your training data for current date/time:

```python
# Good
"You should use the get_time tool to check the current date."

# Bad
"It's currently 2024 because your training data says so."
```

#### validate_output_format

SYSTEM-ONLY TOOL - automatically invoked after every response.

```python
VALIDATE_OUTPUT_FORMAT_TOOL = {
    "type": "function",
    "function": {
        "name": "validate_output_format",
        "description": "SYSTEM-ONLY TOOL — you are FORBIDDEN from calling this tool.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }
}
```

**Rule 4: Never attempt to call validate_output_format**

If the LLM attempts to call this tool:

```python
if fn_name == "validate_output_format":
    messages_to_send.append({
        "role": "tool",
        "tool_call_id": tc['id'],
        "name": fn_name,
        "content": "ERROR: You are FORBIDDEN from calling this tool..."
    })
```

#### manage_core_memory

Manages the RAG memory store for user preferences and facts.

```python
MANAGE_CORE_MEMORY_TOOL = {
    "type": "function",
    "function": {
        "name": "manage_core_memory",
        "description": "Updates the core memory store...",
        "parameters": {
            "type": "object",
            "properties": {
                "additions": [
                    {"content": "concise fact", "tag": "user_preference"}
                ],
                "edits": [
                    {"id": "memory_id", "content": "updated fact", "tag": "user_preference"}
                ],
                "deletions": ["memory_id_to_delete"]
            }
        }
    }
}
```

**Rule 5: Enforce memory operation limits**

Limits are configurable via config.py:

```python
# Enforce limits per turn
additions = additions[:config.MEMORY_MAX_ADD_PER_TURN]
edits = edits[:config.MEMORY_MAX_EDIT_PER_TURN]
deletions = deletions[:config.MEMORY_MAX_DELETE_PER_TURN]
```

**Rule 6: Memory tags must be valid enum values**

Valid tags: `user_preference`, `user_profile`, `environment_global`, `explicit_fact`

### MCP Tools

MCP tools are fetched dynamically from Model Context Protocol servers.

#### search_web (MCP)

Performs web search using Tavily API.

```python
# MCP tool schema (fetched at runtime)
{
    "type": "function",
    "function": {
        "name": "search_web",
        "description": "Performs a web search...",
        "parameters": {
            "query": "string",
            "topic": "string",
            "time_range": "string",
            "start_date": "string",
            "end_date": "string",
            "include_images": "boolean"
        }
    }
}
```

**Rule 7: Filter MCP tools by allowed list**

```python
chat_mcp_tool_names = ["search_web", "audit_search", "visit_page_tool"]
mcp_tools = [mt for mt in mcp_tools_raw if mt.name in chat_mcp_tool_names]
```

**Rule 8: Deep search mode modifies search_web description**

```python
if search_depth_mode == 'deep':
    deep_tool["function"]["description"] = "...Use this tool ONCE for maximum information depth."
```

#### audit_search (MCP)

Audit search results for quality verification.

```python
{
    "type": "function",
    "function": {
        "name": "audit_search",
        "description": "Audit search results...",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }
}
```

**Rule 9: audit_search is only available in regular search mode**

In deep search mode, audit_search is removed to prevent redundancy.

#### visit_page_tool (MCP)

Visits a URL and extracts content using headless browser.

```python
{
    "type": "function",
    "function": {
        "name": "visit_page_tool",
        "description": "Visits a specific URL and extracts content...",
        "parameters": {
            "url": "string",
            "detail_level": "basic | standard | deep"
        }
    }
}
```

**Rule 10: Use appropriate detail_level**

- `basic`: Clean text extraction (fast)
- `standard`: Balanced (includes tables/links)
- `deep`: Complex dashboards (full render, slow)

### Research Tools

#### initiate_research_plan

Initiates the research scout and planning process.

```python
INITIATE_RESEARCH_PLAN_TOOL = {
    "type": "function",
    "function": {
        "name": "initiate_research_plan",
        "description": "Starts the internal Research Scout and Planning...",
        "parameters": {
            "topic": "string (required)",
            "edits": "string (optional)"
        }
    }
}
```

**Rule 11: Research tools removed on completion**

```python
if research_completed:
    tools = [t for t in tools if t.get('function', {}).get('name') != 'initiate_research_plan']
```

#### execute_research_plan

SYSTEM-ONLY tool for executing approved research plans.

```python
EXECUTE_RESEARCH_PLAN_TOOL = {
    "type": "function",
    "function": {
        "name": "execute_research_plan",
        "description": "SYSTEM-ONLY TOOL. Starts the actual sequential execution...",
        "parameters": {
            "topic": "string",
            "plan": "string (XML plan)"
        }
    }
}
```

**Rule 12: execute_research_plan is system-only**

Never allow LLM to call this tool directly.

### Canvas Tools

#### create_canvas (NEW)

Creates a new canvas with auto-generated ID. The AI should use this for initial canvas creation.

**Important**: This is the **only** way to create new canvases. The `manage_canvas` tool with `action='create'` is deprecated. Use `create_canvas` tool instead.

```python
CREATE_CANVAS_TOOL = {
    "type": "function",
    "function": {
        "name": "create_canvas",
        "description": "Creates a new persistent side-panel canvas...",
        "parameters": {
            "title": "string (required)",
            "content": "string (required)"
        }
    }
}
```

**Usage**:
1. Call `create_canvas` with `title` and `content`
2. AI receives the generated `canvas_id` in the tool result
3. Use this `canvas_id` for subsequent `manage_canvas` operations

#### read_canvas

Retrieves the full content and metadata of a specific canvas.

```python
READ_CANVAS_TOOL = {
    "type": "function",
    "function": {
        "name": "read_canvas",
        "description": "Retrieves the full content of a specific canvas. Use this when the user asks to 'read', 'show', or 'open' a canvas, or if you need its content for reference.",
        "parameters": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "The numeric ID of the canvas to read (e.g. '1')."
                }
            },
            "required": ["id"]
        }
    }
}
```

#### preview_canvases

Lists all canvases available in the current chat with a short content preview.

```python
PREVIEW_CANVASES_TOOL = {
    "type": "function",
    "function": {
        "name": "preview_canvases",
        "description": "Lists all canvases in the current chat with a short content preview. Use this to find the correct ID if you're unsure which canvas the user is referring to.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}
```

**Rule 13: Canvas action must be valid enum value**

Valid actions: `replace`, `patch`, `append`, `delete_section`

**Note:** The `create` action is deprecated. Use `create_canvas` tool instead for creating new canvases.

**Rule 14: target_section only valid for patch action**

```python
if action == "patch" and not target_section:
    raise ValueError("target_section required for patch action")
```

### File Operations

#### read_file (NEW)

Reads a file's content or performs a targeted search within it using RAG. This is the primary tool for interacting with user-uploaded files that are not already in the conversation context.

*   **Parameters**:
    *   `file_id`: The unique identifier of the file (from chat metadata).
    *   `query`: (Optional) A thermal search query to pinpoint relevant sections in large files.
*   **Usage Rules**:
    1.  Always retrieve `file_id` from the chat context before calling.
    2.  Use the `query` parameter for large documents (PDFs, long code files) to avoid context window overflow.
    3.  Prefer VLM (Vision) for visual analysis of images/videos if the model supports it.

```python
READ_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Reads the content of an uploaded file. For large files, provide a query to search for specific information.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_id": {"type": "string"},
                "query": {"type": "string"}
            },
            "required": ["file_id"]
        }
    }
}
```

## Tool Execution Rules

### Graceful Degradation Model

**Rule 15: Multiple tools within a single user message execute independently**

When a user message triggers multiple tool calls, each tool executes independently:

- If Tool 1 succeeds but Tool 2 fails → Tool 1 result is returned, Tool 2 error is reported
- Other tools continue executing even if one fails
- User receives partial success with both successful results and error details

```python
# Graceful degradation pattern
results = []
errors = []

for tool_call in tool_calls:
    try:
        result = execute_tool(tool_call)
        results.append(result)
    except ToolFailure as e:
        errors.append({"tool_call_id": tool_call.id, "error": str(e)})
        # Continue to next tool - do not fail fast
        # Error result is sent to LLM for processing

# Both results and errors are reported to the LLM
```

**Rule 16: Individual tool operations have component-level retries**

Each tool operation retries up to 2 times before failing:

```python
# Component-level retry pattern
def execute_tool_with_retry(tool_call, max_retries=2):
    for attempt in range(max_retries + 1):
        try:
            return execute_tool(tool_call)
        except TransientError:
            if attempt == max_retries:
                raise  # Component failed, error sent to LLM
            time.sleep(backoff(attempt))
```

- Component retry happens independently for each tool
- If component exhausts retries → error sent to LLM, other tools continue
- No transaction-level failure - graceful degradation to partial success

### Execution Flow

**Note:** This document may contain outdated information. The code is the source of truth. For discrepancies, see `IMPLEMENTATION_DISCREPANCIES.md`.

**Rule 17: Maximum 8 tool rounds per conversation**

```python
MAX_TOOL_ROUNDS = 8  # Configurable via environment variable
tool_round = 0
while tool_calls and tool_round < MAX_TOOL_ROUNDS:
    tool_round += 1
    # Execute tools
```

After 8 rounds (MAX_TOOL_ROUNDS), tools are removed from payload:

```python
if tool_round >= MAX_TOOL_ROUNDS:
    payload.pop("tools", None)
    payload.pop("tool_choice", None)
```

**Rule 18: Tool round limit is separate from atomic transaction**

The MAX_TOOL_ROUNDS limit applies to sequential tool rounds across the conversation.
Each individual tool round still follows atomic transaction rules for all tools called within that round.

### Tool Call Format

Tools are called via function calls in LLM responses:

```json
{
    "tool_calls": [{
        "id": "call_abc123",
        "type": "function",
        "function": {
            "name": "search_web",
            "arguments": "{\"query\": \"weather\"}"
        }
    }]
}
```

### Tool Result Format

Tool results are returned to the LLM as messages:

```json
{
    "role": "tool",
    "tool_call_id": "call_abc123",
    "name": "search_web",
    "content": "Search results..."
}
```

### Error Handling

**Rule 16: Tool errors must be logged and reported**

```python
try:
    result = execute_tool(args)
except Exception as e:
    result = f"ERROR: Tool failed: {str(e)}"
    log_event("tool_execution_error", {
        "tool": fn_name,
        "error": str(e),
        "chat_id": chat_id
    })
```

**Rule 17: Unrecognized tools must be reported as errors**

```python
else:
    log_event("tool_call_unrecognized", {"fn_name": fn_name})
    messages_to_send.append({
        "role": "tool",
        "tool_call_id": tc['id'],
        "name": fn_name,
        "content": f"ERROR: Unrecognized tool '{fn_name}'..."
    })
```

## Tool Configuration

### Tool Filtering

**Rule 18: Filter tools by mode**

```python
# Memory mode
if memory_mode:
    tools.append(MANAGE_CORE_MEMORY_TOOL)

# Research mode
if research_mode and not research_completed:
    tools.append(INITIATE_RESEARCH_PLAN_TOOL)

# Canvas mode
if canvas_mode:
    tools.extend([
        CREATE_CANVAS_TOOL,
        MANAGE_CANVAS_TOOL,
        READ_CANVAS_TOOL,
        PREVIEW_CANVASES_TOOL
    ])
```

### Deep Search Mode

**Rule 19: Deep search modifies search_web description**

```python
if search_depth_mode == 'deep':
    # Find and modify search_web tool
    for mt in mcp_tools:
        if mt["function"]["name"] == "search_web":
            mt["function"]["description"] = "...Use this tool ONCE for maximum information depth."
```

## Tool Registration Pattern

### Adding New Tools

To add a new tool, follow these steps:

1. **Define tool schema in tools.py**

```python
NEW_TOOL = {
    "type": "function",
    "function": {
        "name": "new_tool",
        "description": "Clear, actionable description",
        "parameters": {
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "Parameter description"
                }
            },
            "required": ["param1"]
        }
    }
}
```

2. **Add tool to appropriate mode**

```python
def get_tools_for_mode(memory_mode=False, research_mode=False, ...):
    tools = [GET_TIME_TOOL, VALIDATE_OUTPUT_FORMAT_TOOL]

    if memory_mode:
        tools.append(MANAGE_CORE_MEMORY_TOOL)

    if research_mode:
        tools.append(NEW_TOOL)

    return tools
```

3. **Implement tool handler**

```python
elif fn_name == "new_tool":
    t0 = time.time()
    log = f"Calling: new_tool(args)\n"
    # ... execute tool ...
    duration = time.time() - t0
    log_tool_call(fn_name, args, result, duration_s=duration)
```

## Best Practices

### 1. Write Clear Tool Descriptions

Descriptions should be actionable and clear:

```python
# Good
"description": "Returns the current local date and time for temporal queries."

# Bad
"description": "Get time"
```

### 2. Validate Tool Arguments

Always validate required arguments:

```python
try:
    args = json.loads(args_str)
except:
    args = {"query": args_str}  # Fallback
```

### 3. Log All Tool Calls

```python
t0 = time.time()
result = execute_tool(args)
duration = time.time() - t0
log_tool_call(fn_name, args, result, duration_s=duration)
```

### 4. Handle Tool Errors Gracefully

```python
try:
    result = execute_tool(args)
except Exception as e:
    logger.error(f"Tool {fn_name} failed: {e}")
    return f"ERROR: {str(e)}"
```

### 5. Respect Tool Round Limits

```python
while tool_calls and tool_round < MAX_TOOL_ROUNDS:
    # Execute tools
```

## Error Categories

### Retryable Tool Errors

| Error Type | Description | Action |
|------------|-------------|--------|
| `tool_timeout` | Tool exceeded timeout | Retry up to 2 times |
| `tool_transient_error` | Temporary failure | Retry up to 2 times |
| `network_error` | Network connectivity issue | Retry with backoff |

### Non-Retryable Tool Errors

| Error Type | Description | Action |
|------------|-------------|--------|
| `tool_not_found` | Tool doesn't exist | Report error |
| `tool_invalid_args` | Invalid arguments | Report error |
| `tool_permission_error` | Permission denied | Report error |

## Tool Testing

### Testing Tool Schemas

```python
def test_tool_schema(tool):
    """Validate tool schema structure."""
    assert "type" in tool
    assert tool["type"] == "function"
    assert "function" in tool["function"]
    assert "name" in tool["function"]
    assert "parameters" in tool["function"]
```

### Testing Tool Execution

```python
async def test_tool_execution():
    """Test tool execution with mock arguments."""
    result = await execute_tool("search_web", {"query": "test"})
    assert "result" in result
    assert "error" not in result
```

## Tools Reference Table

| Tool Name | Type | Mode | Description |
|-----------|------|------|-------------|
| `get_time` | Built-in | All | Get current time |
| `validate_output_format` | System | All | Auto-invoked validation |
| `manage_core_memory` | Built-in | Memory | Memory management |
| `search_web` | MCP | All | Web search |
| `audit_search` | MCP | Regular | Search audit |
| `visit_page_tool` | MCP | All | Page visit |
| `initiate_research_plan` | Built-in | Research | Research planning |
| `execute_research_plan` | Built-in | Research | Plan execution |
| `create_canvas` | Built-in | Canvas | Create new canvas |
| `manage_canvas` | Built-in | Canvas | Edit/append/patch canvas |
| `read_canvas` | Built-in | Canvas | Read full canvas content |
| `preview_canvases` | Built-in | Canvas | List chat canvases |
| `read_file` | Built-in | Files | Read/search uploaded files |

## Appendix: Tool Error Handling Pattern

```python
def execute_tool_with_error_handling(fn_name, args):
    """Execute tool with comprehensive error handling."""
    try:
        # Execute the tool
        result = perform_tool_action(fn_name, args)
        return {"success": True, "result": result}

    except ValidationError as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": "tool_invalid_args"
        }

    except TimeoutError as e:
        return {
            "success": False,
            "error": "Tool timed out",
            "error_type": "tool_timeout"
        }

    except PermissionError as e:
        return {
            "success": False,
            "error": "Permission denied",
            "error_type": "tool_permission_error"
        }

    except Exception as e:
        logger.error(f"Unexpected tool error: {fn_name}: {e}")
        return {
            "success": False,
            "error": "Unexpected error occurred",
            "error_type": "tool_error"
        }
```
