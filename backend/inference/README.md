# backend/inference
**Role:** Provides a unified interface for interacting with LLM APIs, handling chat completions, streaming responses, and embeddings while managing request serialization and model lifecycle.

## 📄 Core Files
| File | Purpose | Key Symbols/Exports |
| :--- | :--- | :--- |
| `__init__.py` | Package entry point and export aggregator. | `InferenceEngine`, `ManualChunkEmitter` |
| `emitter.py` | Simulates SSE streaming for system-generated content. | `ManualChunkEmitter` |
| `engine.py` | Core singleton for LLM and embedding requests. | `InferenceEngine`, `AsyncMPSemaphore` |

## 🧩 Architectural Context
*   **Dependencies:**
    - `httpx`: Underlying engine for asynchronous HTTP communication.
    - `backend.config`: Configuration for server endpoints, API keys, and timeouts.
    - `backend.logging`: Auditing and performance tracking for all LLM calls.
    - `backend.models`: Interaction with the model lifecycle management system.
*   **Flow:**
    1. **Dispatch:** Components (e.g., `ChatHandler`) call `InferenceEngine.stream()` or `chat()`.
    2. **Synchronization:** The engine acquires a cross-process semaphore to enforce parallelism limits.
    3. **Pre-flight:** It ensures the requested model is loaded on the target server.
    4. **Normalization:** Messages are normalized to standard formats.
    5. **Execution:** Performs the HTTP request and processes the result.
    6. **Token Interception (App-Side Parsing):** The engine routes raw text through the `inference_proxy/parsers` module. Based on model signatures, it strips `<think>` or `<|channel>thought` tags dynamically, segregating them into the UI-compatible `reasoning_content` stream.
    7. **Logging:** Records the transaction, including payloads and timing metadata.

## 🛠️ Usage & Conventions
*   **Patterns:** 
    - **Singleton:** The `InferenceEngine` maintains shared state and configuration for the entire application.
    - **SSE Emulation:** `ManualChunkEmitter` allows agents to inject status events and content into the UI stream without making an LLM call.
    *   **Multimodal Handling:** Specifically handles browser screenshots and image-based context injection for vision-capable models.
    *   **Performance:** Uses an `AsyncMPSemaphore` to share concurrency limits across multiple Gunicorn workers without blocking individual asyncio event loops.
    *   **Testing:**
        - **Local:** Unit tests in `tests/` ensure strict compliance with the 1:1 exhaustive testing rule. `engine.py` tests include a background threaded `http.server` acting as a mock `llama.cpp` server to simulate real API streaming, embedding behaviors, and inference errors natively.
        - **Run Command:** `EMBEDDING_URL="http://mock" AI_URL="http://mock" ./venv/bin/python3 -m pytest backend/inference/tests/`
