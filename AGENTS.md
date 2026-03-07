# LM Studio / Local LLM Integration Guide

This document details the exact streaming behavior, payload structures, and known quirks of local LLMs running through LM Studio's OpenAI-compatible `/v1/chat/completions` endpoint. 

Local reasoning models (like `nvidia/nemotron-3-nano`, `DeepSeek-R1`, etc.) often exhibit non-standard behaviors compared to OpenAI's official API. Understanding these differences is critical for writing robust backend parsing logic.

---

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

**🚨 IMPORTANT NOTE ON TAGS 🚨**
Local models emitting `reasoning_content` **do not** include `<think>` or `</think>` tags in the stream. If your system requires these tags for message history or internal routing, the **backend driver** must explicitly wrap the `reasoning_content` value with tags before storing the message.

4. **The Completion Signal**: 
   A final chunk containing `"finish_reason": "stop"`, followed by `[DONE]`.

---

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
4. **The Argument Streaming Phase**: 
   Subsequent chunks append JSON strings to the `arguments` key.
5. **The Completion Signal**: 
   `"finish_reason": "tool_calls"`, then `[DONE]`.

---

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

---

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

---

## Summary for Backend Implementation

Any backend client or utility function designed to handle LM Studio MUST account for these deviations:

1. **Stateful Parsers**: Accumulate both `content` and `reasoning_content`.
2. **Fallback Logic**: If `response_format` is requested, always prioritize checking `reasoning_content` if `content` is empty.
3. **Finish Reason Maturity**: Do not trigger tool parsing until `finish_reason` is specifically `"tool_calls"`.
4. **Structured Mapping**: For both streaming and non-streaming, treat `reasoning_content` as the primary source of truth for the final response when a schema is enforced.

```python
# Universal extraction logic:
final_result = response.content or response.reasoning_content
if is_json_requested:
    return json.loads(final_result)
```
