# CHANGELOG

## v1.5.1 (Research Engine Bug Fixes)
* **Bug Fix**: Fixed `UnboundLocalError` related to `follow_up_content` in the research engine's section execution phase.
* **Bug Fix**: Fixed an undefined `log_event` variable reference in utility functions used for URL safety checks.
* **Code Quality**: Addressed minor exception raising linting warnings in the utils file.
* **Version Bump**: Incremented version to v1.5.1.

## v1.5.0 (Secure Remote Architecture & Connection Hardening)
* **Secure Remote Access (Bastion SSH)**: Introduced a hardened OpenSSH bastion container (`bastion_ssh`) on an isolated bridge network, enabling secure remote access via encrypted SSH tunnels without exposing the application port (5000) directly to the host or internet.
* **Unified Connection Management**: Purged all frontend input fields and client-side logic for LLM server URLs and API keys. Connection details are now strictly managed as backend secrets (Docker Secrets/Env), preventing misconfiguration and protecting sensitive credentials.
* **Network Isolation & Resolution**: Migrated the application to a strictly isolated `secure-internal` Docker network. Implemented `host.docker.internal` gateway resolution to allow the containerized backend to communicate with host-resident LM Studio instances natively.
* **Automated Port Tunneling**: Reconfigured the networking stack to support seamless "Local Forwarding" strategies, allowing mobile and remote devices to browse the interface securely via Tailscale through the Bastion.
* **Backend Robustness**: Hardened the Flask `/v1/chat/completions` proxy and model routes to enforce backend configuration and prevent empty-string overrides from legacy frontend artifacts.
* **Version Bump**: Incremented version to v1.5.0.

## v1.4.0 (Dockerization & Security Hardening)
* **Containerization**: Added `Dockerfile` using Python 3.12-slim and `docker-compose.yml` to isolate the backend application.
* **Non-Root Execution**: Hardened the Docker container to execute entirely under a restricted `appuser`.
* **Volume Mapping Strategy**: Centralized dynamic storage elements (SQLite DB, ChromaDB vectors, logs, and task manifests) into a configurable `DATA_DIR`, designed for volume mapping (`user_data`).
* **Docker Secrets Implementation**: Replaced `os.getenv` configuration with `get_secret` to strictly enforce loading sensitive API keys and configuration values via Docker Compose Secrets.
* **App-Level Hardening**: Introduced HTTP Basic Authentication middleware guarded by an `APP_PASSWORD` secret to prevent unauthorized UI and API access.
* **Agent Operational Policy Update**: Updated `AGENTS.md` to strictly forbid autonomous operations targeting the main Docker stack (`docker compose up/down`). Isolated verification allowed only through strictly uniquely named, ephemeral containers.
* **Authentication Proxy for Model Listings**: Rewrote frontend `/v1/models` fetching logic to route through a dedicated Flask backend proxy (`/api/v1/models`). This securely bridges requests to the configured `LM_STUDIO_URL` by injecting the localized authentication secret on the server side, resolving cross-origin and authentication errors triggered by the removal of frontend API key exposure.
* **Version Bump**: Incremented version to 1.4.0.

## v1.3.1
* **Developer Guide Expansion**: Significantly expanded `AGENTS.md` to include comprehensive architectural guidelines, UI constraints (Luminous Material), and backend operational rules for AI agents and human contributors.
* **Version Bump**: Incremented version to 1.3.1.

## v1.3.0 (Research Architecture Overhaul)
* **Complete Research Pipeline Rewrite**: Deprecated `deep_research.py` in favor of a rebuilt, highly-resilient `research.py` engine featuring strict token budgeting, semantic triage, and a multi-phase generation strategy.
* **Phase 0 & 1 — Context Scout & Planning**: Integrated a pre-planning "Scout" phase that classifies the user's topic, evaluates time-sensitivity, and executes preliminary contextual searches *before* designing the sequential XML research plan.
* **Phase 2 — Section-by-Section Synthesis**: Shifted from global context dumping to localized generation. The engine now fetches sources, reflects, triages information, and writes the report one section at a time, drastically reducing context bloat and hallucination.
* **Phase 3 — Audit & "Surgeon" Patching**: Introduced an automated post-generation quality phase. A "Detective" agent scans the stitched report for contradictions and missing citations, followed by a "Surgeon" agent that surgically patches specific paragraphs rather than rewriting entire sections.
* **Mechanical Citation Enforcement**: Implemented deterministic regex-based citation normalizers (`_normalize_citations`, `_strip_invalid_citations`) that aggressively strip out hallucinated `[N]` references that don't match the active `source_registry`.
* **Meander Detection System**: Built an active stream monitor that strictly enforces reasoning limits (e.g., `RESEARCH_MEANDER_THOUGHT_LIMIT`) and automatically truncates `<think>` blocks if the local model falls into an infinite reasoning loop.
* **Strict Reasoning Directives**: Updated prompts across all research agents (Scout, Planner, Executor, Detective, Surgeon) with highly specific system directives to tightly control and guide chain-of-thought pathways.
* **System & UI Fixes**: 
    *   Refactored the deep research resume state serialization to flawlessly recover `accumulated_summaries` across application reloads.
    *   Fixed intelligence logs UI to cleanly parse and render markdown wrappers and unclosed `<think>` tags without JSON artifacting.
    *   Resolved `undefined serverModels` reference in frontend payloads.
* **Codebase Cleanup**: Purged legacy unit/integration test files (`test_*.py`), removed Playwright UI testing scripts, and erased debugging logs (`DEEP_RESEARCH_AUDIT.md`) to streamline the production repository.
* **Version Bump**: Incremented version to 1.3.0.

## v1.2.0
* **Sequential Research Pipeline**: Rewrote the entire execution phase from parallel to sequential step processing. Each step now builds on accumulated context from prior steps, enabling progressive understanding.
* **Per-Step Reflection & Gap Filling**: Added an LLM-based reflection phase after each step that analyzes extracted content, identifies information gaps, and executes up to 2 targeted follow-up searches to fill them.
* **Deterministic URL Selection**: Replaced the AI-based URL ranking LLM call with a deterministic heuristic (Tavily score + domain diversity), eliminating an entire LLM round-trip per step.
* **Enhanced Content Extraction**: Implemented a multi-strategy extraction chain for deep mode — direct HTTP GET with markdownify, Tavily Extract fallback for JS-rendered pages, and PyMuPDF (`fitz`) fallback for PDF documents.
* **Phase 2.5 — Retrieval Planning**: Added a pre-report phase where the LLM generates cross-step retrieval queries based on accumulated summaries, capturing comparisons, contradictions, and synthesis points across research steps.
* **Multi-Query Semantic Retrieval**: Reporter context is now assembled via dynamic per-query token budgeting across step goals + interconnected queries, replacing the old flat chunk dump.
* **Unlimited Storage, Budgeted Retrieval**: Removed the 400k token storage cap. All extracted content is stored in ChromaDB; the 400k budget now applies only to the final retrieval for the reporter.
* **Vision Processing Refactor**: Extracted vision model integration into reusable helper functions (`_process_images_in_content`, `_process_tavily_search_images`) for both regular and deep modes.
* **Conservative Plan Modification**: Reflection can now suggest modifications to future steps when findings necessitate it, with full logging and user visibility.
* **Embedding Model Update**: Switched default embedding model to `text-embedding-embeddinggemma-300m`.
* **New Frontend Activity Types**: Added `reflection`, `follow_up_search`, and `retrieval_planning` activity renderers for step-by-step execution visibility.
* **Version Bump**: Incremented version to 1.2.0.

## v1.1.5
* **Phase 0: Context Scout**: Implemented a pre-planning analysis phase that classifies research topics, assesses time-sensitivity, and gathers preliminary web context to inform the main research strategy.
* **Enhanced Planning Strategy**: Relaxed the strict "maximum isolation" constraint on research steps, allowing the planner to design a logical progression where later steps can build on earlier foundational findings.
* **Per-Step Search Parameters**: The research plan now supports granular control over each search step, with optional `<topic>`, `<time_range>`, `<start_date>`, and `<end_date>` parameters.
* **Thought Process Persistence & UX**: Fixed an issue where planning thoughts disappeared on reload and optimized the real-time display to filter out raw JSON activity chunks, showing only human-readable reasoning.
* **Version Bump**: Incremented version to 1.1.5.

## v1.1.4
* **Research Resume Compatbility Fix**: Research agent now resumes properly after user resumes the conversation.
* **Fix Embedding Model**: Fixed embedding model to use `text-embedding-qwen3-embedding-0.6b` instead of `text-embedding-jina-embeddings-v5-text-small-retrieval`.
* **Version Bump**: Incremented version to 1.1.4.

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
    * **Server Link Mapping**: Fixed a critical bug where Research agents were ignoring the `LM_STUDIO_URL` setting and defaulting to localhost.
    * **Unified Configuration**: Centralized all backend connection parameters (`LM_STUDIO_URL`, `EMBEDDING_MODEL`, `CHROMA_PATH`) into a dedicated `backend/config.py` for system-wide consistency.
    * **Robust URL Suffixing**: Implemented automated detection and handling of the `/v1` suffix in inference URLs to prevent connection failures.
    * **Standardized Defaults**: Aligned global embedding defaults with Jina v5 architecture requirements.
* **Version Bump**: Incremented version to 1.1.2.

## v1.1.1
* **Research Optimization**: Scaled down context parameters for better performance with local 512k context windows (originally built for 1M).
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
    * The "Temporary Chat" button is now automatically greyed out and disabled during active Research sessions or when a conversation has already started.
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
* **Research Architecture**: Implemented a multi-pass ($n+1$) research agent with real-time web browsing, link discovery, and structured reporting capabilities.
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
