# LM Studio / Local LLM Integration Guide

This document details the exact streaming behavior, payload structures, and known quirks of local LLMs running through LM Studio's OpenAI-compatible `/v1/chat/completions` endpoint.

Local reasoning models (like `nvidia/nemotron-3-nano`, `DeepSeek-R1`, etc.) often exhibit non-standard behaviors compared to OpenAI's official API. Understanding these differences is critical for writing robust backend parsing logic.

## 1. Standard Chat Completion (Streaming)

When processing standard text generation requests with `stream: true`, the model splits its output into two distinct phases: a "thinking" phase and an "answering" phase.

### Sequential Flow:
1. **The Reasoning Phase (`reasoning_content`)**:
   The stream begins by emitting chunks where the delta object contains a `"reasoning_content"` key, but *not* a `"content"` key.
   ```json
   data: {"choices":[{"delta":{"role":"assistant","reasoning_content":"Thinking..."}}]}
   ```

2. **The Transition Phase**:
   Usually marked by a switch from `reasoning_content` to the standard `content` key, often providing a newline whitespace first.

3. **The Content Phase (`content`)**:
   The model streams the final, user-facing answer using the standard `"content"` key.

**🚨 IMPORTANT NOTE ON TAGS (CRITICAL FOR DATABASE) 🚨**
Local models emitting `reasoning_content` **do not** include `<think>` or `</think>` tags in the stream.
If the system requires these tags for message history (e.g., storing in SQLite `chats.db`), the **backend driver** must explicitly wrap the accumulated `reasoning_content` string with tags before insertion.

**Mandatory Python Implementation:**
```python
# During stream aggregation:
full_reasoning += chunk.choices[0].delta.reasoning_content or ""
full_content += chunk.choices[0].delta.content or ""

# Before saving to DB:
final_db_string = ""
if full_reasoning:
    final_db_string += f"<think>\n{full_reasoning}\n</think>\n\n"
final_db_string += full_content
```

4. **The Completion Signal**:
   A final chunk containing `"finish_reason": "stop"`, followed by `[DONE]`.

## 2. Tool Call Execution (Streaming)

When `tools` are provided and `stream: true`, the model accumulates tool arguments after a reasoning phase.

### Sequential Flow:
1. **The Reasoning Phase (`reasoning_content`)**: Identical to standard chat.
2. **Transition**: Empty/newline `content` block.
3. **Tool Call Initialization Phase (`tool_calls`)**:
   The first tool call chunk provides the metadata (`id`, `name`, `type`). `arguments` is typically an empty string.
   ```json
   data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"...","type":"function","function":{"name":"...","arguments":""}}]}}]}
   ```
4. **The Argument Streaming Phase (Buffering Rule)**:
   Subsequent chunks append JSON string fragments to the `arguments` key. **Never** attempt to `json.loads()` these fragments sequentially. You must aggregate the entire string into a buffer first.
5. **The Completion Signal**:
   The final chunk returns `"finish_reason": "tool_calls"`. Only at this exact moment is it safe to parse the accumulated `arguments` buffer into JSON.

## 3. Structured JSON Output (Streaming: `stream: true`)

**🚨 CRITICAL QUIRK IDENTIFIED 🚨**

When a strict JSON schema is enforced using OpenAI's structured output parameter (`response_format`), local integrations via LM Studio exhibit a major deviation from standard behavior.

**Instead of returning the structured JSON in the `"content"` key, it streams the entire generated JSON object inside the `"reasoning_content"` key.**

### Sequential Flow:
1. **JSON Generation Phase (`reasoning_content`)**:
   The model streams the entire valid JSON object strictly adhering to the requested schema. **The standard `"content"` key is completely missing or empty.**
   ```json
   data: {"choices":[{"delta":{"reasoning_content":"{\n  \"name\": \"Elena\"\n}"}}]}
   ```
2. **Completion**: `"finish_reason": "stop"`.

## 4. Structured JSON Output (Non-Streaming: `stream: false`)

Even without streaming, the quirk persists. When `response_format` is provided, the primary output location is swapped.

### Response Structure:
1. **`choices[0].message.content`**: Set to an empty string (`""`).
2. **`choices[0].message.reasoning_content`**: Contains the **entire valid JSON payload**.
   ```json
   {
     "choices": [
       {
         "message": {
           "role": "assistant",
           "content": "",
           "reasoning_content": "{ \"name\": \"Eleanor Whitaker\", \"age\": 34 }",
           "tool_calls": []
         },
         "finish_reason": "stop"
       }
     ]
   }
   ```
3. **`finish_reason`**: Remains `"stop"`.

## 5. Summary for Backend Implementation

Any backend client or utility function designed to handle LM Studio MUST account for these deviations:

1. **Stateful Parsers**: Accumulate both `content` and `reasoning_content`.
2. **Empty Content Bug Avoidance**: Never wait for or assume that the `"content"` key will eventually populate if `response_format` (JSON Schema) is requested. It frequently resolves to `""` or `None`.
3. **Finish Reason Maturity**: Do not trigger `json.loads(arguments)` or `execute_tool()` logic until `finish_reason` explicitly changes to `"tool_calls"`.
4. **Structured Mapping / Safe Extraction**: When extracting non-streaming payloads or finalized streamed payloads with strict formats enforced, the ultimate source of truth must default to `reasoning_content` if `content` fails.

```python
# Universal Safe Extraction (CRITICAL IMPLEMENTATION):
try:
    # 1. Check primary content block
    content_payload = getattr(message, 'content', '') or ''
    # 2. Check reasoning block (quirk fallback)
    reasoning_payload = getattr(message, 'reasoning_content', '') or ''

    # 3. Aggressive extraction
    final_raw_string = content_payload if len(content_payload) > 5 else reasoning_payload

    # 4. Safe Parse
    if is_json_requested:
        final_result = json.loads(final_raw_string)
        return final_result

except json.JSONDecodeError as e:
    log_event("json_parse_error", {"raw": final_raw_string, "error": str(e)})
    return None # Prevent background task crash
```