# CHANGELOG
 
## v2.3.0
* **Site Visit Tool Fallback**: Implemented a new `playwright_mcp` container for the site visit tool, which attempts to scrape using requests first and falls back to a Playwright headless browser if it fails.
* **Separated MCP Services**: Split the previous `research_mcp` container into two separate, dedicated MCP servers: `tavily_mcp` (for searching and mapping) and `playwright_mcp` (for visiting URLs and fetching images).
* **Normal Chat Integration**: The robust new `visit_page_tool` is now directly available to the standard Chat agent.
* **Output Sanitization**: Implemented basic output sanitization (stripping suspicious scripts and remaining HTML) at the MCP layer before returning data to the main server.

## v2.2.2
* **3D Background Animation (Antigravity Inspired)**: Implemented an interactive 3D particle cloud background using Vanilla JS and Canvas. Features autonomous "breathing" motion, smooth mouse/touch following, and a zero-lag volumetric ripple effect on click/tap.
* **Complete UI Redesign**: Overhauled the application theme, changing the primary accent color from Electric Violet to Ocean Blue (`#3B82F6`) and the neutral scale from Pure Zinc to Slate.
* **Design Directives Updated**: Updated `docs/design_directives.md` and `AGENTS.md` to reflect the new Ocean Blue standard and deprecate Electric Violet.

## v2.2.1 (Full Height UI Overlays)
* **Full Height UI Canvases**: The Research Report and Global Knowledge Base overlays now span the full height of the viewport on all devices.
* **Mobile Flush Edges**: Added mobile responsiveness to strip the border and border-radius off full-screen canvases for a flush, native full-screen feel on touch devices.
* **Version Bump**: Incremented version to v2.2.1.

## v2.2.0 (Memory Management & VRAM Optimization)
* **Memory Management UI**: Added a comprehensive Memory Canvas Overlay for searching, filtering, editing, and deleting memories directly from the UI.
* **Enhanced Memory API**: Implemented RESTful endpoints (`PUT`, `DELETE`) to support granular memory modification and cleanup.
* **System Settings Integration**: Added a dedicated "Manage Memories" module within the System Settings for unified configuration control.
* **Version Bump**: Incremented version to v2.2.0.

## v2.1.1 (Model Lifecycle & VRAM Optimization)
* **Model Lifecycle Tracking**: Added full support for tracking model states (`unloaded`, `loading`, `loaded`) through a corrected `/api/v1/models` proxy that respects the `llama.cpp` server-specific `status` object.
* **Improved Management Consistency**: Moved loading/unloading logic from `/api/v1/models` to unprefixed `/api/models/load` and `/api/models/unload` endpoints to align with `llama.cpp` native management paths.
* **Proactive VRAM Management**: Implemented automatic "pre-inference" cleanups that purge unnecessary models from GPU/RAM before starting a new chat or research session.
* **Multi-Model Exclusions**: Enhanced the unloader utility to support multiple simultaneous exclusions, allowing the Research Agent to keep Main, Vision, and Embedding models co-resident while purging others.
* **UI Status Indicators**: Added real-time "Loading..." and "Active" status badges to the model selection dropdown and research activity readouts.
* **Version Bump**: Incremented version to v2.1.1.

## v2.1.0 (MCP Architecture Migration)
* **Architecture Overhaul**: Migrated all external-facing tools (web search, web scraping, PDF extraction, map, etc.) to a dedicated Model Context Protocol (MCP) server container (`research_mcp`).
* **Security & Isolation**: External operations now run entirely outside the main app container, significantly reducing the blast radius of potential vulnerabilities.
* **Network Communication**: The main Flask backend now communicates with the MCP server using Server-Sent Events (SSE) over HTTP (`mcp.client.sse`).
* **Chat Integration**: The chat agent (`generate_chat_response`) now dynamically fetches external tool schemas from the MCP server and executes them via the MCP client, while retaining internal tools (memory, time) within the main app.
* **Research Integration**: The deep research engine (`generate_research_response`) now offloads all heavy lifting (fetching URLs, downloading PDFs, querying Tavily) to the MCP server via direct client execution, keeping only the orchestration and database logic in the main app container.
* **Version Bump**: Incremented version to v2.1.0.

## v2.0.0 (Aurora + Obsidian Design Overhaul and AI backend migration)
* **AI Backend Migration**: Migrated from LM Studio to llama.cpp.
* **UI Fix (Tools Dropdown)**: Increased the opaqueness of the tools dropdown to match modal dialogs, ensuring better legibility and a more premium feel.
* **UX/Behavior Fix (Tool Toggles)**: Implemented sticky tool blocking. Enabling one tool now correctly blocks other tools from being engaged until the active tool is disabled.
* **UI Improvement**: Moved inline styles from the tools dropdown to CSS and added a smooth slide-up entry animation.
* **Complete UI Redesign**: Replaced the Luminous Material design system with the new "Aurora + Obsidian" aesthetic — atmospheric frosted glass surfaces, monochrome palette with Electric Violet (#A855F7) as the single accent color, and extreme typography weight contrast (200↔800).
* **Frosted Glass Surfaces**: All panels (sidebar, modals, input bar, chat header, toasts, tooltips, thought process containers) now use `backdrop-filter: blur(16px)` with translucent backgrounds, creating depth and atmosphere.
* **Ambient Background**: Added a fixed atmospheric layer with subtle violet radial gradient orbs that slowly drift — very subtle in dark mode (opacity 0.03), warmer and more present in light mode (opacity 0.09).
* **Color System Overhaul**: Migrated from Ocean Blue palette (`#3B82F6`) to Electric Violet (`#A855F7`) monochrome system. All buttons, toggles, active states, and accents now use violet.
* **Typography Refinement**: Section labels (RECENT CHATS, THOUGHT PROCESS, etc.) now use weight 200 with 0.15em letter-spacing for a signature ultra-thin uppercase look. Headings use weight 800 for dramatic contrast.
* **Hero Text**: Greeting text changed from gradient fill to solid white (dark) / near-black (light) for cleaner Obsidian aesthetic.
* **Light Mode**: Warm off-white background (#F8F7F4) with visible violet ambient presence; all surfaces use milky white glass treatment.
* **Favicon**: Updated from blue-teal gradient to violet gradient.
* **Version Bump**: Incremented version to v2.0.0 (MAJOR — significant UI/UX overhaul per SemVer).

## v1.7.6
* **UI Redesign (Logs)**: The Logs page has been fully redesigned to perfectly match the Luminous Material aesthetic of the main application.
* **UX Fix**: Implemented a responsive collapsible sidebar for the Logs page, significantly improving usability on mobile devices.
* **UI Fix (Logs)**: Fixed an issue where long model names or events were overflowing the sidebar width.
* **Version Bump**: Incremented version to v1.7.6.

## v1.7.5
* **Bug Fix (UI Responsiveness)**: Fixed an issue where long tables or wide table content generated by markdown in chat responses were truncating and overflowing off the screen on smaller devices. Tables now correctly wrap their text and constrain their width.
* **Version Bump**: Incremented version to v1.7.5.

## v1.7.4
* **Retraction**: Reverted the removal of `REASONING_TEMPLATE` from the prompts.
* **Version Bump**: Incremented version to v1.7.4

## v1.7.3
* **Removal**: Removed the `REASONING_TEMPLATE` from the prompts.
* **Version Bump**: Incremented version to v1.7.3.

## v1.7.2
* **Bug Fix (Backend State)**: Fixed an issue where the Deep Search state was prematurely overwritten during chat by passing the missing `search_depth_mode` argument to `save_chat` in `app.py`.
* **Bug Fix (Frontend Sync)**: Replaced a missing `syncChatState` function call with the correct `persistChat` method in `script.js` to ensure real-time UI toggles correctly hit the backend mid-conversation.
* **UX/Safety**: Toggling the Deep Search mode now immediately and persistently locks the state to the SQLite DB, preventing AI hallucinations upon reload.
* **Version Bump**: Incremented version to v1.7.2.

## v1.7.1
* **Feature**: Added folder renaming capabilities with full cross-context database updating.
* **UI Improvement**: Replaced inline chat renaming logic with the globally integrated modal input system (`showPromptModal`).
* **Version Bump**: Incremented version to v1.7.1.

## v1.7.0
* **Feature**: Added "Deep Search" mode which bypasses the audit tool and extracts the raw content directly into the prompt context for deeper analysis.
* **UI Improvement**: Consolidated "Research Agent" and "Deep Search" toggles into a single "Tools" dropdown menu in the chat input area.
* **UX/Safety**: "Research Agent" and "Deep Search" modes cannot be toggled after a conversation starts, enforcing persistence to prevent AI hallucinations.
* **Version Bump**: Incremented version to v1.7.0.

## v1.6.6
* **Bug Fix**: Fixed a bug in `backend/agents/research.py` where a failed triage extraction or empty facts would silently proceed, outputting an empty section. The process now correctly raises a `ValueError` which triggers a retry fallback mechanism, allowing the user to retry the extraction. A similar check was added to the fallback writer flow.
* **Version Bump**: Incremented version to v1.6.6.

## v1.6.5
* **Bug Fix**: Fixed a validation parsing error where the AI incorrectly placed query text as a tag attribute, causing empty query errors in `utils.py`. The regex recovery logic and LLM instructions were updated to robustly handle malformed XML.
* **UX Improvement**: Improved the error feedback mechanism in `backend/agents/research.py` to prevent the AI from repeatedly hallucinating missing tags when validation fails.
* **Version Bump**: Incremented version to v1.6.5.

## v1.6.4
* **Bug Fix**: Fixed a parameter mapping bug in `backend/storage.py`'s `save_chat` function where the `folder` value was being incorrectly assigned to the `is_custom_title` column and the `folder` column was receiving a hardcoded `0`.
* **Version Bump**: Incremented version to v1.6.4.

## v1.6.3
* **Bug Fix**: Fixed a bug in `backend/agents/chat.py` where tool schemas were deleted after the first tool execution, causing subsequent LLM rounds to hallucinate tools and crash with a `KeyError`. Tool definitions are now preserved until `MAX_TOOL_ROUNDS`.
* **Stability Fix**: Added proper asyncio task teardown logic in `backend/task_manager.py`'s `consume` coroutine to prevent "Task was destroyed but it is pending!" warnings when generations are interrupted or fail.
* **Version Bump**: Incremented version to 1.6.3.

## v1.6.2
* **Sidebar Layout Fix**: Chat names in the sidebar now dynamically span the full available width instead of truncating prematurely at 24 characters.
* **Rename Chat Fix**: When renaming a chat, the input field now correctly populates with the full, actual chat name instead of the visually truncated version.
* **Version Bump**: Incremented version to v1.6.2.

## v1.6.1
* **Folder Deletion**: Added a delete button to chat folders allowing users to remove a folder. Chats inside the folder will be safely moved back to "uncategorized".
* **Version Bump**: Incremented version to 1.6.1.

## v1.6.0
* **Chat Folders**: Allow categorising chats into folders.
* **Folder Sidebar UI**: Added a new UI section in the sidebar to organize chats by folder, separated from uncategorized chats.
* **Version Bump**: Incremented version to v1.6.0.

## v1.5.5
* **Bug Fix**: Fixed `UnboundLocalError` for `reasoning_flow_prefix` in `backend/agents/chat.py` occurring when chat responses encounter validation errors without prior tool calls.
* **Version Bump**: Incremented version to 1.5.5.

## v1.5.4
* **Bug Fix**: Fixed a marked.js parsing error when rendering empty code blocks. By checking if `code.text === 'string'`, it prevents `.replace()` errors in Highlight.js, resolving a bug in the UI log where `e.replace is not a function` was occurring.
* **Version Bump**: Incremented version to 1.5.4.

## v1.5.3 (Max Tokens Persistence & Defaults)
* **Default Output Tokens Bump**: Increased the default max token output for standard and vision models from 2k (2048) to 16k (16384).
* **Per-Chat Persistence (Storage Schema Update)**: Updated `backend/storage.py` and the SQLite `chats` schema via a safe `ALTER TABLE` migration to permanently store and recall `max_tokens` preferences per chat ID.
* **Live Update API**: Bound a slider `change` listener to send an immediate `PATCH` request to the backend `/api/chats/<id>`, ensuring token settings are saved as the user drags without requiring a formal chat submission.
* **Auto-Restoration Engine**: Updated `loadChat` in `script.js` to ingest `chat.max_tokens` from the backend upon reload and instantly snap the parameters interface back to the exact saved state.

## v1.5.2 (Chat Title Persistence)
* **Custom Chat Title Persistence**: Added database schema and backend logic to prevent manually renamed chat titles from being overwritten by auto-generated summaries.

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
