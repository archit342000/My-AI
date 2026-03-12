# llama.cpp / Local LLM Integration Guide

This document details the exact streaming behavior, payload structures, and known quirks of local LLMs running through llama.cpp's OpenAI-compatible `/v1/chat/completions` endpoint.

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

When a strict JSON schema is enforced using OpenAI's structured output parameter (`response_format`), local integrations via llama.cpp exhibit a major deviation from standard behavior.

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

## 5. Model Inventory & Status (`/v1/models`)

The `/v1/models` endpoint provides a list of available models, but includes a critical **`status`** object not found in the standard OpenAI spec. This allows the backend to track model readiness.

### Status Object Structure:
```json
{
  "id": "model-alias",
  "object": "model",
  "status": {
    "value": "unloaded", // Possible: "unloaded", "loading", "loaded"
    "args": ["/app/llama-server", "--model", "..."],
    "preset": "[model-alias]\nctx-size = 4096..."
  }
}
```

## 6. Model Lifecycle: Loading & Unloading

Models are managed dynamically by the server.

### Automatic Loading:
When a request is sent to `/v1/chat/completions` or `/v1/embeddings` for a model that is currently `"unloaded"`, the server automatically initiates the loading process.
*   **Behavior**: The request will block/wait while the status transitions from `"unloaded"` -> `"loading"` -> `"loaded"`.
*   **Timeout Handling**: If a model is large, the initial request may exceed standard client timeouts (like the 5s default in `httpx`).

### Manual Loading:
The server allows manual triggering of a model load, which is useful when switching models via chat settings or preparing a model for inference ahead of time.

*   **Endpoint**: `POST /models/load`
*   **Payload**:
    ```json
    {
      "model": "model-id-to-load"
    }
    ```
*   **Response**: `{"success": true}`
*   **Success Indicator**: The model status in `/v1/models` will return to `"loaded"`.

### Manual Unloading:
The server supports a custom endpoint for releasing GPU/RAM resources by unloading specific models.

*   **Endpoint**: `POST /models/unload`
*   **Payload**:
    ```json
    {
      "model": "model-id-to-unload"
    }
    ```
*   **Response**: `{"success": true}`
*   **Success Indicator**: The model status in `/v1/models` will return to `"unloaded"`.

## 7. Embeddings API (`/v1/embeddings`)

The server provides a standard OpenAI-compatible embeddings endpoint.

### Request Format:
```json
{
  "input": "Text to embed",
  "model": "embedding-model-alias"
}
```

### Response Format:
```json
{
  "model": "embedding-model-alias",
  "object": "list",
  "data": [
    {
      "object": "embedding",
      "index": 0,
      "embedding": [0.0676, 0.0662, -0.0243, ...]
    }
  ],
  "usage": {
    "prompt_tokens": 3,
    "total_tokens": 3
  }
}
```


## 8. Summary for Backend Implementation

Any backend client or utility function designed to handle llama.cpp MUST account for these deviations:

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