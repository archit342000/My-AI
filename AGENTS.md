# My-AI Developer & Agents Guide

This document provides essential context, architectural constraints, and operational rules for AI agents and human developers working on the `My-AI` repository.

## 1. System Architecture & File Organization

The application follows a clean separation between a vanilla web frontend and a Python backend.

*   **Frontend**: Built with **strictly Vanilla HTML, CSS, and JS**.
    *   **No UI frameworks** (React, Vue, Svelte) and **No CSS frameworks** (Tailwind, Bootstrap) are allowed.
    *   Logic is contained in a single `static/script.js` file utilizing procedural DOM mutations and event delegation.
    *   Styling is managed via `static/styles.css` using CSS Custom Properties.
*   **Backend**: A **Flask** (Python) service orchestrating chat loops, RAG, and deep research agents.
    *   **Task Management**: Uses an asynchronous producer-consumer architecture (`task_manager.py` and `cache_system.py`) to handle chat streaming without blocking the main Flask thread.
    *   **Persistence**: Metadata and chat histories are stored in **SQLite** (`storage.py`), while vector embeddings for RAG are managed via **ChromaDB** (`rag.py`).
*   **Operating Modes**:
    *   **Standard Chat**: Fast, direct inference streams.
    *   **Deep Research**: A multi-pass, asynchronous autonomous engine (`research.py`) that executes web searches, analyzes content, and synthesizes reports without locking the UI.

## 2. Design & UI Constraints (`design_directives.md`)

When modifying the UI, you must strictly adhere to the project's **Luminous Material** design philosophy:

*   **No Inline Structural Styles**: Do not use JS to manually manipulate inline CSS for structure or animations. Always apply or toggle CSS classes (e.g., using the `.dark` class for Dark Mode).
*   **Motion-First DOM**: Every visibility or position change requires transitions (typically using `opacity` and `transform`). Avoid `display: none` for animated elements; use `visibility: hidden` with opacity instead.
*   **Color-Injected Shadows**: Never use pure black shadows on colored elements. Always inject the brand primary color (e.g., `rgba(37, 99, 235, 0.15)`).
*   **Markdown & Code**: Content rendering must use `marked.js` and `highlight.js` (loaded via CDN) directly onto the DOM without intermediate VDOM layers.

## 3. Backend Operational Rules

*   **Database Interactions**: Use the provided helper functions in `backend/storage.py` for SQLite. Do not write raw SQL queries in the API routes.
*   **Asynchronous Tasks**: Any operation that takes longer than a few milliseconds (like LLM inference or web scraping) MUST be enqueued via `task_manager` to prevent blocking the Flask server.
*   **RAG Synchronization**: Ensure `ChromaDB` remains synchronized with `SQLite`. When a chat is deleted, its corresponding vectors must also be wiped.

---

## 4. LM Studio / Local LLM Integration Guide

This section details the exact streaming behavior, payload structures, and known quirks of local LLMs running through LM Studio's OpenAI-compatible `/v1/chat/completions` endpoint. Local reasoning models (like `nvidia/nemotron-3-nano`, `DeepSeek-R1`, etc.) often exhibit non-standard behaviors compared to OpenAI's official API. Understanding these differences is critical for writing robust backend parsing logic.

### 4.1 Standard Chat Completion (Streaming)

When processing standard text generation requests with `stream: true`, the model splits its output into two distinct phases: a "thinking" phase and an "answering" phase.

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

### 4.2 Tool Call Execution (Streaming)

When `tools` are provided and `stream: true`, the model accumulates tool arguments after a reasoning phase.

1. **The Reasoning Phase (`reasoning_content`)**: Identical to standard chat.
2. **Transition**: Empty/newline `content` block.
3. **Tool Call Initialization Phase (`tool_calls`)**: 
   The first tool call chunk provides the metadata (`id`, `name`, `type`). `arguments` is typically an empty string.
   ```json
   data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"...","type":"function","function":{"name":"...","arguments":""}}]}}]}
   ```
4. **The Argument Streaming Phase**: Subsequent chunks append JSON strings to the `arguments` key.
5. **The Completion Signal**: `"finish_reason": "tool_calls"`, then `[DONE]`.

### 4.3 Structured JSON Output (Streaming: `stream: true`)

**🚨 CRITICAL QUIRK IDENTIFIED 🚨**
When a strict JSON schema is enforced using OpenAI's structured output parameter (`response_format`), local integrations via LM Studio exhibit a major deviation from standard behavior. **Instead of returning the structured JSON in the `"content"` key, it streams the entire generated JSON object inside the `"reasoning_content"` key.**

1. **JSON Generation Phase (`reasoning_content`)**: 
   The model streams the entire valid JSON object strictly adhering to the requested schema. **The standard `"content"` key is completely missing or empty.**
   ```json
   data: {"choices":[{"delta":{"reasoning_content":"{\n  \"name\": \"Elena\"\n}"}}]}
   ```
2. **Completion**: `"finish_reason": "stop"`.

### 4.4 Structured JSON Output (Non-Streaming: `stream: false`)

Even without streaming, the quirk persists. When `response_format` is provided, the primary output location is swapped.

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

### 4.5 Summary for Backend Implementation

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

---

## 5. Testing & Contribution Directives

*   **Local Testing**: Developers must test features against both Light and Dark themes. The Flask server (`python3 app.py`) must be run locally to test the streaming backend and async event loops.
*   **Versioning**: This project strictly follows [Semantic Versioning 2.0.0](https://semver.org/).
*   **Documentation Updates**: Any changes to functionality must be reflected by incrementing the version across the following files:
    1.  `versioning_directives.md`
    2.  `changelog.md`
    3.  `README.md`
*   **Commit Requirements**: Always ensure pre-commit verifications (`pre_commit_instructions`) are executed prior to final submission.
