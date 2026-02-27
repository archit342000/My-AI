# CHANGELOG

## v1.2.0
* **Deep Research Resumption**:
    - **Resume Compatibility**: Implemented full state recovery for interrupted Deep Research tasks. Clients now automatically reconnect to the stream upon page reload.
    - **Event Streaming Endpoint**: Added `/api/chats/<chat_id>/events` to replay task logs and stream live updates to reconnected clients.
    - **Race Condition Fix**: Hardened `task_manager.py` to ensure data persistence before status updates, preventing synchronization issues.
    - **Duplicate Prevention**: Refined frontend logic to detect existing completion states and avoid duplicate message bubbles.
* **Refactoring**:
    - **Stream Processing**: Unified stream handling logic in `static/script.js` to reduce code duplication between `sendMessage` and `resumeStream`.
* **Version Bump**: Incremented version to 1.2.0.

## v1.1.3
* **RAG Engine Overhaul**:
    - **Proper Similarity Metric**: Switched ChromaDB to use `cosine` distance instead of default `L2`, resolving search relevance issues with Jina v5.
    - **Auto-Migration**: Implemented automatic detection and migration for stale L2 collections on startup, ensuring old Gemma-era embeddings don't pollute current results.
    - **Tuned Thresholds**: Recalibrated semantic similarity (`0.50`) and time-decay (`0.10`) for Jina v5's specific embedding distribution.
    - **Cleanup**: Stripped vestigial prefix logic causing potential retrieval interference.
* **AI Agent & Validation Stability**:
    - **Tool-Call Resilience**: Added a fallback handler for unrecognized/garbled tool names produced by the model, preventing orphaned history states.
    - **Multi-Round Tool Support**: Fixed follow-up LLM calls to include tool definitions, enabling sequential tool-calling (e.g., search memory then search web).
    - **Loop Safety**: Implemented a 5-round maximum for tool calling to prevent infinite recurring calls.
* **Version Bump**: Incremented version to 1.1.3.

## v1.1.2
* **RAG & Infrastructure Fixes**:
    * **Server Link Mapping**: Fixed a critical bug where Deep Research agents were ignoring the `LM_STUDIO_URL` setting and defaulting to localhost.
    * **Unified Configuration**: Centralized all backend connection parameters (`LM_STUDIO_URL`, `EMBEDDING_MODEL`, `CHROMA_PATH`) into a dedicated `backend/config.py` for system-wide consistency.
    * **Robust URL Suffixing**: Implemented automated detection and handling of the `/v1` suffix in inference URLs to prevent connection failures.
    * **Standardized Defaults**: Aligned global embedding defaults with Jina v5 architecture requirements.
* **Version Bump**: Incremented version to 1.1.2.

## v1.1.1
* **Deep Research Optimization**: Scaled down context parameters for better performance with local 512k context windows (originally built for 1M).
    * **Context Gathering**: Max tokens from web scraping reduced from 700k to 400k.
    * **Report Length**: Report limits halved from ~64k down to 32k (`max_tokens: 32768`).
* **Version Bump**: Incremented version to 1.1.1.

## v1.1.0
* **Intelligence (Logs) Overhaul**:
    * **High-Fidelity UI**: Completely redesigned the network and event logs interface with glassmorphism, refined typography, and info-dense layouts.
    * **Live Stream Search**: Integrated real-time filtering for both network requests and system events.
    * **Syntax Highlighting**: Added `highlight.js` integration for deep inspection of JSON payloads and Markdown returns.
    * **Telemetry Metrics**: Added latency tracking and transfer mode indicators.
    * **Resizable Workspace**: Integrated a custom resizable sidebar with state persistence.
    * **Deep Inspection**: Full payload visibility for all system events, resolving previous truncation issues.
* **Brain Architecture (Jina v5 Migration)**:
    * **State-of-the-Art Retrieval**: Migrated the default embedding model to `text-embedding-jina-embeddings-v5-text-small-retrieval`.
    * **Task-Specific Prefixing**: Implemented automated `Query:` and `Document:` prefixing logic to optimize retrieval accuracy according to Jina v5's architecture.
    * **Expanded Context**: Increased chunking limits to **2500 characters** to better utilize modern embedding context windows.
    * **Refined Filtering**: Calibrated the semantic similarity threshold to **0.35** for more precise memory recall.
* **Version Bump**: Incremented version to 1.1.0.


## v1.0.3
* **Pure Screen Centering**: The empty state (welcome hero) is now perfectly centered vertically and horizontally relative to the entire screen, ignoring sidebar offsets.
* **Mobile Responsiveness Overhaul**: 
    * The navigation panel now disappears entirely when collapsed on mobile, leaving only a floating hamburger menu.
    * Fixed Z-index hierarchy so that settings and dialogs appear on top of the mobile side panel.
* **UI Streamlining**:
    * Corrected the central alignment of the chat header title.
    * Removed the redundant "Last Model used" global indicator in favor of per-message attribution.
* **Version Bump**: Incremented version to 1.0.3.

## v1.0.2
* **Temporary Chat Guardrails**: 
    * The "Temporary Chat" button is now automatically greyed out and disabled during active Deep Research sessions or when a conversation has already started.
    * Added informative tooltips to the temporary chat button to explain its disabled state.
* **Transient Session Privacy**: 
    * Memory mode (RAG) is now explicitly forced OFF for all temporary chats.
    * The memory toggle switch is disabled and visually restricted while in a temporary chat to ensure zero context leakage.
* **Version Bump**: Incremented version to 1.0.2.

## v1.0.1
* **Rebranding**: Officially renamed the application from "LMStudioChat" to **My-AI**.
* **Global Reference Update**: Updated all internal and external references to align with the new brand identity.
* **Version Bump**: Incremented version to 1.0.1.

## v1.0.0 (Official Release)
* **Unified Architectural Overhaul**: Successfully migrated from a frontend-only mock to a robust **Python Flask Backend**.
* **Persistent Storage**: Integrated **SQLite** for reliable, long-term chat history and metadata storage.
* **Intelligent Memory (RAG)**: Developed an ephemeral and persistent memory system using **ChromaDB** to provide context-aware responses via semantic retrieval.
* **Deep Research Architecture**: Implemented a multi-pass ($n+1$) research agent with real-time web browsing, link discovery, and structured reporting capabilities.
* **Vision Integration**: Added support for multimodal inference, allowing the AI to "see" and describe attached images.
* **Premium UI/UX (Luminous Material)**:
    * Fully responsive Glassmorphism design system built with Vanilla CSS.
    * Integrated real-time Markdown and Syntax Highlighting (Highlight.js).
    * Added specialized UI for Research Agents with live activity feeds and interactive cards.
* **Modular Settings**: Comprehensive control over AI sampling parameters, system personas, and backend connection configurations.
* **Security & Performance**: Implemented security obfuscation for local API tokens and optimized the DOM for high-frequency streaming updates.

## v0.1.0 (Alpha Stage)
* Initial MVP with basic chat functionality.
* Design system established (Design Directives v1.0).
