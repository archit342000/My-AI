# My-AI Developer & Agents Guide

This document provides essential context, architectural constraints, operational rules, and best practices for AI agents and human developers working on the `My-AI` repository.

## 1. System Architecture & File Organization

The application follows a clean separation between a vanilla web frontend and a Python backend.

*   **Frontend**: Built with **strictly Vanilla HTML, CSS, and JS**.
    *   **No UI frameworks** (React, Vue, Svelte) and **No CSS frameworks** (Tailwind, Bootstrap) are allowed.
    *   Logic is contained in a single `static/script.js` file utilizing procedural DOM mutations and event delegation.
    *   Styling is managed via `static/styles.css` using CSS Custom Properties.
*   **Backend**: A **Flask** (Python) service orchestrating chat loops, RAG, and deep research agents.
    *   **Task Management**: Uses an asynchronous producer-consumer architecture (`task_manager.py` and `cache_system.py`) to handle chat streaming without blocking the main Flask thread.
    *   **Persistence**: Metadata and chat histories are stored in a local **SQLite** database (`storage.py`), while vector embeddings for RAG are managed via **ChromaDB** (`rag.py`).
*   **Operating Modes**:
    *   **Standard Chat**: Fast, direct inference streams.
    *   **Deep Research**: A multi-pass, asynchronous autonomous engine (`research.py`) that executes web searches, analyzes content, and synthesizes reports without locking the UI.

---

## 2. Design & UI Constraints (`design_directives.md`)

When modifying the UI, you must strictly adhere to the project's **Luminous Material** design philosophy:

*   **No Inline Structural Styles**: Do not use JS to manually manipulate inline CSS for structure or animations. Always apply or toggle CSS classes (e.g., using the `.dark` class for Dark Mode).
*   **Motion-First DOM**: Every visibility or position change requires transitions (typically using `opacity` and `transform`). Avoid `display: none` for animated elements; use `visibility: hidden` with opacity instead.
*   **Color-Injected Shadows**: Never use pure black shadows on colored elements. Always inject the brand primary color (e.g., `rgba(37, 99, 235, 0.15)`).
*   **Markdown & Code**: Content rendering must use `marked.js` and `highlight.js` (loaded via CDN) directly onto the DOM without intermediate VDOM layers.

---

## 3. Best Practices for Development & Contribution

### 3.1 Handling Database & Schema Changes
*   **SQLite Migrations**: The `backend/storage.py` file initializes the database. If adding new columns or tables, you must ensure backwards compatibility. Use `ALTER TABLE` queries in `init_db()` wrapped in `try-except` blocks to smoothly migrate existing local databases (`chats.db`) for current users.
*   **ChromaDB Sync**: The RAG system relies on ChromaDB. If you modify how chat data is structured or saved, ensure the vector embeddings stay perfectly synchronized. If a user deletes a chat or resets memory, ChromaDB must be purged accordingly.

### 3.2 Git & Branching Strategy
*   **Branch Naming**: Feature and bugfix branches should strictly lead with the target version they aim to bump, or a descriptive prefix, e.g., `1.3.1-fix-streaming-bug` or `feature/vision-improvements`.
*   **Commit Messages**: Keep commit messages concise, descriptive, and Git-agnostic. The first line should be an imperative summary under 50 characters, followed by an empty line and detailed reasoning if needed.
*   **Verification Before Commit**: Always run the application locally to test functionality (both Light and Dark modes) before submitting code. If modifying the frontend, visually verify all structural and animation changes.

### 3.3 Versioning & Releases (SemVer)
*   This project strictly follows [Semantic Versioning 2.0.0](https://semver.org/).
*   **Mandatory Updates**: When a PR introduces a functionality change, bug fix, or UI modification, you **must** bump the version globally across the project.
    *   This includes updating:
        1.  `versioning_directives.md`
        2.  `changelog.md` (Add a new detailed block at the top under the new version header)
        3.  `README.md` (Update the displayed version badge/text)

---

# LM Studio / Local LLM Integration Guide

This section details the exact streaming behavior, payload structures, and known quirks of local LLMs running through LM Studio's OpenAI-compatible `/v1/chat/completions` endpoint.

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

**🚨 IMPORTANT NOTE ON TAGS 🚨**
Local models emitting `reasoning_content` **do not** include `<think>` or `</think>` tags in the stream. If your system requires these tags for message history or internal routing, the **backend driver** must explicitly wrap the `reasoning_content` value with tags before storing the message.

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
4. **The Argument Streaming Phase**:
   Subsequent chunks append JSON strings to the `arguments` key.
5. **The Completion Signal**:
   `"finish_reason": "tool_calls"`, then `[DONE]`.

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
2. **Fallback Logic**: If `response_format` is requested, always prioritize checking `reasoning_content` if `content` is empty.
3. **Finish Reason Maturity**: Do not trigger tool parsing until `finish_reason` is specifically `"tool_calls"`.
4. **Structured Mapping**: For both streaming and non-streaming, treat `reasoning_content` as the primary source of truth for the final response when a schema is enforced.

```python
# Universal extraction logic:
final_result = response.content or response.reasoning_content
if is_json_requested:
    return json.loads(final_result)
```
