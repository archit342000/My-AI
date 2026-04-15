# llama.cpp / Local LLM Integration Guide (v3.1.0)

This document details the exact streaming behavior, payload structures, and known quirks of local LLMs running through llama.cpp's OpenAI-compatible `/v1/chat/completions` endpoint.

Local reasoning models (like `nvidia/nemotron-3-nano`, `DeepSeek-R1`, etc.) often exhibit non-standard behaviors compared to OpenAI's official API. Understanding these differences is critical for writing robust backend parsing logic.

> [!IMPORTANT]
> **Separation of Concerns**: The inference server (llama.cpp) is managed in a **separate repository**. This application (My-AI) is purely a consumer and interacts with it only through URLs and API keys defined in `secrets/`. This repository contains NO orchestration or deployment logic for the inference server itself.

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

When a strict JSON schema is enforced using OpenAI's structured output parameter (`response_format`), `llama.cpp` follows standard behavior.

### Sequential Flow:
1. **The Reasoning Phase (`reasoning_content`)**: Identical to standard chat. The model may explain its approach here.
2. **JSON Generation Phase (`content`)**:
   The model streams the entire valid JSON object strictly adhering to the requested schema using the standard `"content"` key.
   ```json
   data: {"choices":[{"delta":{"content":"{\n  \"name\": \"Elena\"\n}"}}]}
   ```
3. **Completion**: `"finish_reason": "stop"`.

## 4. Structured JSON Output (Non-Streaming: `stream: false`)

Standard behavior applies. The JSON payload is found in the primary `content` field.

### Response Structure:
1. **`choices[0].message.content`**: Contains the **entire valid JSON payload**.
2. **`choices[0].message.reasoning_content`**: Contains the model's internal reasoning (if applicable).
   ```json
   {
     "choices": [
       {
         "message": {
           "role": "assistant",
           "content": "{ \"name\": \"Eleanor Whitaker\", \"age\": 34 }",
           "reasoning_content": "Thinking...",
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
    "args": ["--model", "..."],
    "preset": "[model-alias]\nctx-size = 4096..."
  }
}
```

## 6. Model Lifecycle: Loading & Unloading

Models are managed dynamically by the server.

### Automatic Loading:
When a request is sent to `/v1/chat/completions` or `/v1/embeddings` for a model that is currently `"unloaded"`, the server automatically initiates the loading process.
*   **Behavior**: The request will block/wait while the status transitions from `"unloaded"` -> `"loading"` -> `"loaded"`.
*   **Timeout Handling**: If a model is large, the initial request may exceed standard client timeouts (like the 5s default in `httpx`). **Recommendation**: Set `TIMEOUT_LLM_ASYNC` in `backend/config.py` to a higher value (e.g., 300 seconds) for large model loading scenarios.

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


## 8. Meandering Mitigation & Handover Rules

Reasoning models can sometimes "meander" (reach thought limits or produce excessive reasoning compared to final content). 

### 8.1 Disabling Reasoning Fallback
If a model persists in meandering during a structured output task (Scout, Planner, etc.), the backend can force it to skip the reasoning phase entirely. This is achieved by passing a custom parameter to the inference endpoint.

**Implementation:**
```json
{
  "chat_template_kwargs": {
    "enable_thinking": false
  }
}
```
When this is active, `reasoning_content` will be empty, and the model will jump straight to the `content` (JSON) phase.

### 8.2 Safe Message History & Handovers
1. **Internal History**: Always preserve the `<think>` blocks in the conversation history within a specific agent loop (e.g., Scout iterating). This allows the model to maintain context.
2. **Inter-Agent Handovers**: Always **strip** `<think>` blocks when passing one agent's output as a prompt to another (e.g., Scout results to Planner). This prevents the next agent from being influenced or confused by the previous agent's internal monologue.

### 8.3 The Thinking Protocol (Standardization)

To ensure consistent behavior across all agents (Chat, Research, Canvas), the system enforces a global parameters standard:

1.  **Mandatory Kwarg**: Every LLM call from the `chat.py` or `research.py` agents MUST provide `chat_template_kwargs={"enable_thinking": bool}`.
2.  **State Management**:
    - **Default**: The system defaults to `enable_thinking: True` for conversational agents to preserve logical chain-of-thought.
    - **Optimization**: For structured output tasks (like Scout or Planner generating pure JSON), it may be set to `False` to reduce latency and "meandering".
3.  **Backend Enforcement**: The `backend/llm.py` logic handles the injection of this kwarg into the final payload sent to the inference endpoint.

### 8.4 Summary for Backend Implementation

1. **Stateful Parsers**: Accumulate both `content` and `reasoning_content`.
2. **Always Wrap Reasoning**: The backend must wrap `reasoning_content` in `<think>` tags for both logging and history to ensure UI consistency and model context.
3. **Strict JSON Field**: Treat `content` as the only source of truth for the final JSON payload when `response_format` is requested. `reasoning_content` is exclusively for the thinking process.
4. **chat_template_kwargs support**: The backend's `stream_chat_completion()` and `chat_completion()` functions accept an optional `chat_template_kwargs` parameter. This allows passing custom parameters to the inference template, such as `{"enable_thinking": False}` to skip the reasoning phase entirely. This is useful as a fallback when a model persists in meandering during structured output tasks.

### 8.5 Timeout Configuration

For model loading operations, the default 5-second timeout may be insufficient for large models. Configure the timeout via `backend/config.py`:

```python
TIMEOUT_LLM_ASYNC = 300  # 5 minutes for large model loading
TIMEOUT_LLM_BLOCKING = None  # None = infinite for local queue
```