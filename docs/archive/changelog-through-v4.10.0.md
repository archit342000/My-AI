# CHANGELOG

## v4.10.0
* **Clipboard Tool & DB Operations**:
    - **Database Operations**: Introduced `clipboard_ops.py` for clipboard metadata storage and state management.
    - **Clipboard Capability**: Added `backend/tools/catalog/clipboard.py` and `backend/tools/clipboard.py` along with comprehensive unit tests to support Clipboard interactions.
* **Tools Catalog Refactoring**:
    - **Monolithic Definitions Cleanup**: Completely removed `backend/tools/definitions.py` and split/cleaned up catalog definitions into dedicated modules in `backend/tools/catalog/`.
* **Agent Prompts & Rules Restructuring**:
    - **Directive Naming Migration**: Renamed `*_directives.txt` files to `*_rules.txt` under `backend/prompts/templates/directives/` for styling/naming consistency.
    - **Directive Integrations**: Updated template integration and rules parameters within `PromptBuilder` and agent prompt templates.
* **Version Bump**: Incremented version globally to 4.10.0.

## v4.9.0
* **Unified Tool Registry (ToolSpec)**:
    - **Declarative Specifications**: Replaced the separate `registry.json`, `definitions.py`, and `prompts.py` files with a single declarative `ToolSpec` dataclass for all agent-facing capabilities.
    - **Catalog Migration**: Migrated all system capabilities into dedicated domain files under `backend/tools/catalog/` (e.g. `filesystem.py`, `git.py`, `code.py`, `web.py`, etc.).
    - **Usage Directives Integration**: Co-located agent prompts and spatial/temporal usage instructions directly inside their corresponding tool definitions.
* **Structured Response Models (Pydantic)**:
    - **Type-Safe Messaging**: Introduced structured Pydantic schemas (`SSEEvent`, `ParsedToolCall`, `ToolResult`, and `AgentResult`) in `backend/chat/models.py`.
    - **Handler Refactoring**: Refactored the core chat handler (`ChatHandler`) and tool handler (`ToolHandler`) to operate on type-safe models instead of raw dictionaries, eliminating runtime type errors.
* **Composable Prompt Assembly (PromptBuilder)**:
    - **Prompt Refactoring**: Extracted 200+ lines of complex inline if-else template generation from the chat handler into a clean, testable `PromptBuilder` and `PromptContext` design pattern.
    - **Dynamic Directives Composition**: Enabled automatic overlay compilation of mode-specific instructions (e.g., code runner, user preferences, git, files) based on active chat configurations.
* **Abstract BaseAgent Lifecycle**:
    - **Agent Standardization**: Created a unified `BaseAgent` abstract base class to encapsulate the looping, retry, failsafe turn counter, context restoration, and safety auditing logic for sub-agents.
    - **Duplicate Code Elimination**: Refactored `BrowsingAgent`, `DocumentAgent`, `FileSystemAgent`, and `GitAgent` to inherit from the common base agent class, reducing duplicate orchestration logic by hundreds of lines.
* **Decoupled Prompts & Templates**:
    - **Template Segregation**: Moved inline system prompts, tool usage instructions, and agent directives out of python source files and into clean `.txt` files under `backend/prompts/templates/`.
    - **Prompts Loader**: Added a robust dynamic template loader (`backend/prompts/loader.py`) with full test coverage.
* **Stateless Inference Proxy Decoupling**:
    - **App-Specific Logic Cleanup**: Refactored message normalization in both backend and proxy ends to exclude application-specific database keys and rely strictly on standard OpenAI-compliant allow-lists.
    - **Dynamic Swapping**: Decoupled active model swapping categories from hardcoded classifications, resolving categories dynamically from loaded configuration maps.
    - **Dynamic Telemetry & Speed Tests**: Allowed the `/test-speed` endpoint to accept customizable context-accumulation topics directly via POST request payloads.
    - **Robust Null Parameter Filtering**: Excluded `None` fields (like `name`, `tool_call_id`, and `tool_calls`) from normalization outputs to prevent llama.cpp validation failures on serialized `null` values.
* **Version Bump**: Incremented version globally to 4.9.0.

## v4.8.1
* **Streaming Tool Call Repair & Aggregation Refinements**:
    - **Streaming JSON Repair**: Integrated tool call argument repair logic directly into the active SSE completion stream.
    - **Shared Delta Merging**: Created a unified `merge_tool_call_deltas` utility to resolve aggregation coupling across the engine, chat handler, and database persistence layers.
    - **Robust Log Reconstruction**: Refactored raw model output reconstruction with safe try-except fallback behavior.
    - **Predicate Purity**: Refactored `_is_generation_valid` into a side-effect-free, pure predicate.
    - **Test Isolation**: Resolved workspace test flakiness and improved cache layer isolation.
* **Version Bump**: Incremented version globally to 4.8.1.

## v4.8.0
* **Code Runner Integration & Tool Refinements**:
    - **Code Runner**: Implemented code runner functionality for executing code blocks within sandbox environments.
    - **Tool Refinements**: Refined and polished agent tools and execution flow.
* **Version Bump**: Incremented version globally to 4.8.0.

## v4.7.11
* **Robust Tool Call Parsing & Argument Salvaging**:
    - **Escaped and Unescaped Delimiters**: Updated Gemma 4 tool call parsing to support both `<|"|>` and `<|\"|>` string literal delimiters.
    - **Robust Key-Wrapping**: Upgraded JSON key wrapping in the proxy and backend validators to support unquoted alphanumeric, dash-based, and digit-based keys.
    - **Lenient JSON Salvaging**: Integrated `ast.literal_eval` to salvage single-quoted/Python dictionaries, and added an unclosed double-quotes auto-closer to repair truncated string values.
* **Version Bump**: Incremented version globally to 4.7.11.

## v4.7.10
* **Speed Test Enhancements**:
    - **Cancel Button**: Added a button to cancel the speed test execution.
    - **Illustration & Reasoning**: Fixed illustration rendering logic and disabled reasoning for the speed test.
* **Version Bump**: Incremented version globally to 4.7.10.

## v4.7.9
* **Docker Configuration**:
    - **Project Name**: Added project name `my-ai` to docker compose file.
* **Version Bump**: Incremented version globally to 4.7.9.

## v4.7.8
* **Search Web Agent Refinements**:
    - **Directives & Truncation**: Clarified directives for the web search agent to retrieve raw search results, and added per-search-result truncation logic.
* **UI & User Experience**:
    - **Header Actions**: Added ability to rename chats and workspaces directly from the header.
    - **Mermaid Diagrams**: Fixed rendering issues for Mermaid diagrams in the UI.
    - **Time-Based Sorting**: Enabled sorting of workspaces based on time.
* **Multi-Turn Chat Persistence**:
    - **Task List Persistence**: Added persistence for the main conversation task list across multiple turns.
* **Version Bump**: Incremented version globally to 4.7.8.

## v4.7.7
* **UI Enhancements & Polish**:
    - **Chat & Streaming**: Fixed chat loading logic to appear smoother, and resolved an issue where image preview and full view did not work during response streaming.
    - **Workspace & Sidebar Navigation**: Added and customized workspace icons, updated workspace header alignment, and moved the 'New File' button to the top of the sidebar.
    - **Control Panel & Inputs**: Made the max tokens and thinking budget values directly editable (bypassing the slider), and added a size limit to the main input field.
    - **Mobile & iPad Optimizations**: Fixed iPad background animation glitches, resolved mobile overflow on the Mermaid schematic viewer header, and corrected a folder long-press gesture issue in the file sidebar.
    - **Browser Portal**: Made the manual browser portal view full screen.
* **Version Bump**: Incremented version globally to 4.7.7.

## v4.7.6
* **Virtual File System & API Enhancements**:
    - **Blocked Virtual Workspace Path Arguments**: Modified `execute_git` subcommand to block `workspace/` prefixed arguments in git commands across all contexts, preventing incorrect physical folders from being created.
    - **Workspace ID Normalization**: Added a `before_request` hook and path resolution helper to automatically normalize `"default"` workspace IDs into the chat's actual registered workspace ID.
    - **Cleaned Sharing Code**: Completely removed all traces of the unused `/share`, `/unshare`, and `/shared-users` endpoints, database operations, manager functions, and test cases.
* **Version Bump**: Incremented version globally to 4.7.6.

## v4.7.5
* **UI Refinements & Fixes**:
    - **Mermaid Schematic Viewer**: Added mermaid schematic viewer to navigate mermaid.js schematics effectively.
    - **LaTeX Equation Scrolling**: Added logic for latex equations to scroll within callouts.
    - **Table Scrolling**: Added hybrid rendering logic making tables scrollable when exceeding thresholds.
    - **Chat Timestamp Logic**: Fixed a discrepancy in time units between the backend and JS for chats.
    - **Log Base64 Truncation**: Added logic to truncate base64-encoded elements in logs.
* **Version Bump**: Incremented version globally to 4.7.5.

## v4.7.4
* **Skill Store & Chat Enhancements**:
    - **Multimodal Skill Invocations**: Fixed an issue where the skill name wasn't getting replaced with the instructions when the user message had an image or file attachment (multimodal list payloads).
* **Version Bump**: Incremented version globally to 4.7.4.

## v4.7.3
* **UI Refinements & Fixes**:
    - **Logs Page UI**: Refined logs page UI and updated it to be compatible with the refactored app.
    - **Padding Adjustments**: Fixed excessive padding on the right due to compounding push of the file editor and file sidebar.
    - **Clarification Box Scrollability**: Resolved scrollability issues in the clarification tool box.
* **Skill Store & Chat Enhancements**:
    - **Skills Highlighting**: Added visual highlighting for skills in chat.
    - **Background Transparency**: Decreased background transparency for the user preference and skills stores.
* **Version Bump**: Incremented version globally to 4.7.3.

## v4.7.2
* **Inference Proxy Timeout & Retry Alignment**:
    - **Stream Read Timeout Upgrade**: Aligned the default `TIMEOUT_LLM_STREAM_READ` parameter from 60 seconds to **1800 seconds** (30 minutes) in the `inference_proxy` to tolerate prolonged prompt prefills on consumer hardware.
    - **Embedding Timeout Upgrade**: Aligned the default `TIMEOUT_EMBEDDING` parameter from 60 seconds to **1800 seconds** (30 minutes) in the `inference_proxy` to allow batch document and codebase embedding indexing under heavy workloads without timeouts.
    - **Retry Delay Realignment**: Adjusted `LLM_RETRY_DELAY` from 2.0 seconds to **0.5 seconds** in the `inference_proxy` to match prompt retry latency defaults in the main app.
    - **Configuration Test Suite**: Added dedicated test coverage in `inference_proxy/tests/test_config.py` verifying default settings and environmental overrides.
* **Version Bump**: Incremented version globally to 4.7.2.

## v4.7.1
* **Right Sidebar Layout & Padding Alignment**:
    - Synchronized right sidebar transition, width, and padding parameters to match the left sidebar exactly.
    - Implemented a robust, state-driven JS synchronization for `--right-sidebar-width` to resolve layout feedback locks.
    - Cleaned up the search artifacts input element in `static/index.html` to eliminate double-border styling and outline mismatches.
* **Version Bump**: Incremented version globally to 4.7.1.

## v4.7.0
* **Autonomous Git Agent & Safe Execution Tooling**:
    - Implemented a fully functional autonomous Git operations agent capable of performing safe clones, checkouts, branch operations, commits, status lookups, and log listings.
    - Integrated with a VFS-safe execution environment in `backend/tools/implementations/git_executor.py` to strictly restrict commands inside `FILE_SYSTEMS_DIR` paths, preventing path traversal and shell injection attacks.
* **Playwright Scraping Context Size Limit Upgrade**:
    - Documented update in `backend/config.py` changing `MAX_CHARS_VISIT_PAGE` from `8000` to `40000`. This expands web crawling context extraction limits to capture extremely dense document text and multi-page technical articles during autonomous page visits.
* **Version Bump**: Incremented version globally to 4.7.0.

## v4.6.2
* **Markdown LaTeX Rendering Improvements**:
    - **LaTeX Display Math Boundary Padding**: Preprocessed multiline display math blocks (`$$ ... $$`) in the frontend to ensure they are padded with boundary newlines and isolated on their own paragraph boundaries. This guarantees that `marked-katex-extension`'s block rule can correctly match and render block equations instead of falling back to standard markdown.
    - **Escape Sequence Protection**: Integrated a negative lookahead regex in the newline normalization pipeline (`/\\n(?![a-zA-Z])/g`) to protect LaTeX commands starting with the letter `n` (e.g., `\nabla`, `\nearrow`, `\nu`, `\neq`, `\neg`) from being corrupted into newline characters followed by plain text (e.g., preventing `\nabla` from rendering as a newline followed by `abla`).
* **Version Bump**: Incremented version globally to 4.6.2.

## v4.6.1
* **Model Pass-Through Support for Trailing Slashes**: Added route handling and custom endpoints to the backend models blueprint to gracefully resolve both `/api/models` and `/api/models/` without redirect loops or 404 errors, fixing settings menu and model switcher failures in the frontend.
* **Frontend Model Switcher Backdrop & Viewport Blocking**: Fixed a bug where switching models did not block the screen or show the loading spinner by integrating actual `#model-switch-overlay` and `.open` class toggles to block user interactions during model swaps.
* **Intelligent Model Swapping on Explicit Loading**: Replaced the stateless raw pass-through `/api/models/load` endpoint inside the inference proxy with the active `ensure_model_loaded` lifecycle engine, guaranteeing that previously loaded models in the same category are cleanly unloaded from GPU VRAM to prevent Out-Of-Memory (OOM) crashes before a new model is loaded.
* **Draft Chat Auto-Persistence Prevention**: Refactored the frontend chat draft state logic (`patchChat` and `onModelChanged`) to prevent saving empty placeholder chats to the database on page reload or "New Chat" click unless explicitly created within a workspace.
* **Version Bump**: Incremented version globally to 4.6.1.

## v4.6.0
* **Agentic Safety Guardrails**: Designed and implemented dynamic agentic safety audits to prevent execution loops and stagnation. Includes detection for consecutive broken tool call repeats (Error Loops), repetitive successful but redundant tool executions (Tool/Duplicate Action Loops), and task list stagnation (where the agent has not updated its high-level checklist for a set number of assistant turns), raising unified system interrupt alerts to prompt the agent to pivot.
* **App-Wide Test Suite Improvements**: Significantly refactored and expanded the test suite coverage across all layers of the application—backend core, database wrappers, file managers, PDF extractor, inference engines, loggers, agent tool implementations, and isolated MCP client tools—ensuring comprehensive coverage, fixing existing test issues, and preventing regressions.
* **Version Bump**: Incremented version globally to 4.6.0.

## v4.5.6
* **Media File RAG Skipping**: Updated the File Manager to completely skip text chunking and RAG (ChromaDB) indexing for media files (images, audio, and video) during all synchronous, asynchronous, and background file uploads, preserving performance and storage.
* **ChromaDB Custom Zero Embedding Function**: Implemented `ZeroEmbeddingFunction`, a custom, zero-latency embedding function returning zero-filled vectors for collections where embeddings are disabled. This prevents ChromaDB from automatically downloading or using its default `all-MiniLM-L6-v2` embedding model over the internet, while correctly maintaining the L2 distance space geometry and adding self-healing for embedding/schema configuration conflicts.
* **Version Bump**: Incremented version globally to 4.5.6.

## v4.5.5
* **Inference Proxy – Stream Interruption Semaphore Leak Fix**: Resolved a bug where interrupting an active streaming turn (e.g., closing the browser tab or clicking "Stop") caused the `AsyncMPSemaphore` concurrency lock inside the `inference_proxy` to be permanently leaked. The `stream_response` generator in `inference_proxy/router.py` was not explicitly calling `gen.aclose()` on the async generator before closing the event loop upon client disconnection (`GeneratorExit`). Because `GeneratorExit` is a `BaseException` and not caught by the original `except Exception` handler, the semaphore's `__aexit__` was never reached, causing all subsequent inference requests to hang indefinitely. Fixed by explicitly catching `GeneratorExit` and calling `loop.run_until_complete(gen.aclose())` before re-raising, and mirrored in the `finally` block to guarantee cleanup under all exit paths.
* **Docker Hostname RFC 1123 Compliance Fix**: Renamed the `inference_proxy` Docker Compose service and container to `inference-proxy` (hyphen instead of underscore). Hostnames with underscores are technically invalid per RFC 1123 and are rejected by strict async DNS resolvers (including `anyio`/`httpcore` used by `httpx`). This caused `httpx.ConnectError: [Errno -3] Temporary failure in name resolution` for all inference calls from the `app` container. Updated the service name, `container_name`, `depends_on` reference, and `AI_PROXY_URL` environment variable in `docker/docker-compose.yml`.
* **Version Bump**: Incremented version globally to 4.5.5.

## v4.5.4
* **Workspace File Sidebar Enhancements**:
    - **Disable Auto-Open on Workspace Load**: Removed the behavior that automatically forced open/expanded the file sidebar (right sidebar) whenever a workspace page was loaded, allowing it to stay collapsed.
    - **Persistent Sidebar Toggle on Workspace Pages**: Enabled the files toggle button (`nav-files-btn`) on the workspace page, allowing the file sidebar to be opened or closed manually regardless of the workspace's files or content.
* **iOS / iPad Chat Sidebar Context Menu Fix**: Resolved an issue on iPads and iOS devices where right-clicking or long-pressing a chat in the sidebar triggered the default browser (Safari) context menu instead of opening the custom dropdown menu.
* **Version Bump**: Incremented version globally to 4.5.4.

## v4.5.3
* **Inference Proxy Modularization**: Refactored out the inference and model lifecycle management logic to reside as a modular, standalone external proxy microservice (`inference_proxy`).
* **Optimized Messages Rendering**: Optimized the rendering of chat messages in the frontend interface.
* **Version Bump**: Incremented version globally to 4.5.3.

## v4.5.2
* **Persona-Associated Agent Configurations**: Enabled persona-level toggles for Research, File System, and Browsing agents that automatically sync with general chat controls, lock active switches on selection, and enforce Research Agent exclusivity.
* **Version Bump**: Incremented version globally to 4.5.2.

## v4.5.1
* **LaTeX / KaTeX Responsive Equation Rendering**:
    - **Table-Wrapper Integration**: Wrapped all markdown table tags inside a responsive `.table-wrapper` container using a custom `marked.js` table renderer.
    - **Table Layout Sizing**: Switched table display rules to `table-layout: auto` and added dynamic scrolling constraints to allow columns to scale seamlessly around wide content (such as inline and block-level mathematical formulas).
    - **Smooth Inline Math Scrolling**: Configured `.katex` inline elements with horizontal overflow scrolling and hidden scrollbars to prevent long equations from overflowing the chat message bubbles or table borders while keeping text lines visually clean.
    - **Display Block Math Handling**: Configured `.katex-display` equations to respect maximum width boundaries and scroll horizontally using custom thin scrollbars.
* **Version Bump**: Incremented version globally to 4.5.1.

## v4.5.0
* **Dedicated Workspace View Pages & Sidebar File System Synchronization**:
    - **Dedicated Workspace Landing Pages**: Built a dedicated workspace view page (`/workspace/<workspace_id>`) displaying workspace statistics, a premium glassmorphic list of chats belonging to the workspace with rename/delete quick actions, and an empty state card with a shortcut to immediately create a chat.
* **Version Bump**: Incremented version globally to 4.5.0.

## v4.4.0
* **System-Wide Skill Store & Custom Trigger Executions**: Developed a fully-featured, premium Skill Store feature that allows users to create, view, update, and delete custom instructions (skills) executed natively by the LLM inference server:
    - **Interactive Settings Overlay & Fullscreen Glassmorphic Design**: Built a responsive, full-screen settings overlay modal (`max-width: 100%`) aligned with the premium look-and-feel of the User Preferences overlay. It supports complete AJAX-based CRUD flows, validation formatting (spaces automatically cleaned to hyphens in real-time), expandable instructions cards, and an intuitive layout.
    - **Slash Commands Dropdown & Autocomplete**: Added a high-fidelity glassmorphic autocomplete dropdown positioned immediately above the chat textarea that triggers when `/` is typed as the first character. Features system commands (`/help` and `/skills`) and custom database skills (e.g., `/git-helper`, `/python-debug`) with fluid keyboard arrow key navigation, Esc close, Tab or Enter selection, system/skill badges, and a sticky helper legend with virtual physical `<kbd>` keycaps.
    - **Zero-Latency Client-Side Interceptors**: Intercepts `/help` (opens an interactive help dialog) and `/skills` (opens the fullscreen Skills Store overlay) instantly in the client code without routing to the AI backend.
    - **Dynamic Prompt Compilation & Directives**: Added custom `GET_SKILL_DETAILS_DIRECTIVES` in `backend/tools/prompts.py` and composed them under the main `TOOL_DIRECTIVES` system prompt block.
    - **High-Contrast Skill Instruction Wrappers**: Dynamically compiles active skills inside user prompt histories, wrapping them inside structured, high-contrast delimiters (`[SKILL: {skill_name}]...[/SKILL]`) to partition custom directives cleanly from user chat text, while compressing older historical references to prevent context window bloat.
* **Version Bump**: Incremented version globally to 4.4.0.

## v4.3.5
* **Premium Chat Loading Animation System**: Designed and implemented a high-fidelity visual loading state for chat switching:
    - **Top Slim Neon Gradient Progress Loader**: Displays a thin, glowing neon-gradient progress indicator that slides and pulses along the top of the chat area until data loads.
    - **Shimmering Message Skeletons**: Displays elegant, shimmering user and assistant glassmorphic message bubbles during fetch latency.
    - **Interactive Sidebar Feedback**: Visual loading state animation added to the clicked chat item in the sidebar with click locking of all other sidebar items to prevent concurrent loading race conditions.
    - **Exception Resilience**: Wrapped the load lifecycle inside a try-catch-finally block to ensure loaders are cleared, clicks are released, and errors cleanly fallback to safe interface states under any error conditions.
* **Version Bump**: Incremented version globally to 4.3.5.

## v4.3.4
* **iPad Scrolling & Animation Fixes**: Resolved persistent scrolling and touch gesture interception issues on iPad/iOS devices for both the main chat messages container (`#messages`) and the system settings modal (`.modal-body`). Restored interactive 3D particle ripples and drift on the atmospheric background star animation canvas (`#bg-stars`).
* **Monolithic script.js Refactoring**: Refactored the monolithic `static/script.js` to extract modularized js scripts from it.
* **Version Bump**: Incremented version globally to 4.3.4.

## v4.3.3
* **Document Agent Rebranding**: Rebranded `file_agent` to `document_agent` throughout the application (modules, API endpoints, configurations, and database constraints) to avoid confusing it with the `file_system_agent`.
* **Database Migration**: Added automated database schema migration to dynamically rename existing `file_agent` entries to `document_agent` in the settings table.
* **Frontend Refactor**: Modularized some of static/script.js to break down the monolith.
* **Version Bump**: Incremented version globally to 4.3.3.

## v4.3.2
* **Concurrent File Uploading**: Enabled parallel/concurrent processing of file uploads in the frontend, preventing optimistic UI rendering from being blocked sequentially.
* **Resilient State Deletion**: Fixed the array filtering bug that incorrectly wiped out other uploaded files from `uploadedFiles` during file removal or upload failure.
* **Processing Status Cleanups**: Fixed the send button lockout issue caused by `"Processing Failed"` matching the word `"Processing"`, and resolved issues with click listeners on files in the `"Processing..."` state.
* **Visual Polish**: Added custom thin scrollbar styling and padding-right to the uploaded files stack (`#file-preview-container`) for consistent premium aesthetics.
* **Version Bump**: Incremented version globally to 4.3.2.

## v4.3.1
* **Preserve User Input Drafts**: Prevented the message input textarea from being cleared when the assistant response streaming completes or during live state synchronization.
* **Version Bump**: Incremented version globally to 4.3.1.

## v4.3.0
* **Virtual Context Compression**: Implemented an automated sliding-window history compression pipeline to maintain coherence and prevent context window exhaustion in extremely long conversations:
    - **Dynamic Slicing & Summary Cache**: Keeps all historical messages persisted in the database, while caching a high-density conversation summary, active image attachments, and virtual file footnote references to reconstruct the active context.
    - **Centralized Model Metadata**: Standardized context limits and HuggingFace tokenizer configurations for all supported models.
    - **Precise Token Counting**: Integrated native HuggingFace template tokenizers with a ChatML fallback, correctly accounting for text formatting and image tokens (1000 tokens per image).
    - **Deletion Safeguard**: Implemented an automatic database-level check that invalidates and clears compression metadata if messages at or prior to the compression boundary are deleted, gracefully reverting the chat history to a clean, uncompressed state.
* **Version Bump**: Incremented version globally to 4.3.0.

## v4.2.1
* **Formatting Directives**: Explicitly documented frontend Markdown capabilities (Mermaid diagrams, Admonitions, Workspace Links, Task Lists, Math/KaTeX, Footnotes) and injected them into the system prompts to ensure the AI leverages rich UI formatting.
* **User Instruction Precedence**: Updated the core personality prompt to firmly enforce that explicit user requests regarding style, volume, tone, and formatting strictly override default efficiency rules, while maintaining the system's absolute authority over operational and security constraints.
* **Version Bump**: Incremented version globally to 4.2.1.

## v4.2.0
* **Persona Mechanims Redesign**: Implemented a new persona mechanim where the personas are persisted in the database and can be reused across conversations. 
* **Chat Settings and System Settings UI fixes**: Minor fixes to make the design more consistent.
* **Version Bump**: Incremented version globally to 4.2.0.

## v4.1.5
* **File System Download Fix**: Fixed a bug where the large file download button in the file system panel header failed to resolve the workspace context.
* **Version Bump**: Incremented version globally to 4.1.5.

## v4.1.4
* **Chat Auto-Scroll Fix**: Modified the frontend chat loading logic to automatically scroll to the bottom upon opening a chat, ensuring users see the most recent messages immediately.
* **Version Bump**: Incremented version globally to 4.1.4.

## v4.1.3
* **Direct Image Support**: Upgraded the chat router to automatically detect uploaded images and inject them directly into the main AI's message stream as multimodal `image_url` blocks, bypassing the `file_agent` to prevent vision information loss.
* **Full-Screen Image Previews**: Enhanced the frontend chat interface to allow users to click on inline image attachments, opening them in a responsive, full-screen modal lightbox.
* **Initialization Fix**: Resolved a `RuntimeError` during image processing by correctly provisioning a `RAGManager` singleton for the `FileManager` via dependency injection.
* **Version Bump**: Incremented version globally to 4.1.3.

## v4.1.2
* **File Agent Vision Prompt Fix**: Decoupled the system prompt used for one-shot multimodal image analysis (`FILE_AGENT_VISION_SYSTEM_PROMPT`) from the standard autonomous sub-agent task directives, preventing tool calling contradictions and tool-loss errors during image inspection.
* **Version Bump**: Incremented version globally to 4.1.2.

## v4.1.1
* **Background Animation Refinement**: Replaced CSS variable references (`var(--accent)` and `var(--accent-light)`) with direct hex color codes (`#3B82F6` and `#60A5FA`) in `static/js/bg-animation.js` to prevent Canvas 2D context parsing failures and eliminate the per-frame particle glittering effect.
* **Version Bump**: Incremented version globally to 4.1.1.

## v4.1.0
* **Playwright Fixes**: Resolved issues with stale Chromium SingletonLock files by implementing an automated cleanup in the entrypoint, ensuring reliable browser startup across container restarts.
* **Improved Markdown Formatting**: 
    - Enhanced the chat interface with rich rendering for images (with captions), blockquotes (with GitHub-style alerts), and task lists.
    - Integrated advanced code block management with syntax highlighting, language headers, and a dedicated copy-to-clipboard feature.
    - Added lightbox support for images and refined typography for a more polished reading experience.
* **Version Bump**: Incremented version to 4.1.0.

## v4.0.1
* **File System Tools Directives Refinement**: Update file system tools directives to explicitly state that the line numbers attached to the read tools results are not part of the content.
* **Version Bump**: Incremented version to 4.0.1.

## v4.0.0
* **Multi-Agent Architecture**: Implemented a comprehensive multi-agent system for specialized task handling, including dedicated agents for file systems, browsing, and research.
* **File System Agent**: Upgraded the simple canvas agent to a true File System Agent capable of managing local directories and files with high precision.
* **File Handling Evolution**: Introduced a dedicated File Agent for intelligent file reading, RAG integration, and multi-modal analysis.
* **Unified Research Architecture**: Fully unified the Research Agent with the normal chat flow, allowing for seamless transitions between research and standard conversation.
* **Agentic Tooling**: Upgraded Web Search and Visit Page tools to use an agentic architecture, significantly reducing AI context window usage through autonomous summarization.
* **Autonomous Browsing**: Implemented a new Autonomous Browsing Agent for complex, multi-step web interactions and data extraction.
* **Model Speed Testing**: Added a high-fidelity benchmark endpoint (`/api/models/test-speed`) to measure LLM performance (TTFT, TPS) directly from the UI.
* **Modular Backend Refactor**: Completed a major architectural overhaul, modularizing the backend into clean domains (chat, file_system, rag, tools, etc.) for better maintainability.
* **Documentation & Standards**: Established rigorous development standards including comprehensive `GEMINI.md`, `CLAUDE.md`, and `AGENTS.md` directives and 1:1 test mapping requirements.
* **Hybrid Search & RAG Enhancements**: Implemented BM25 + Vector fusion (Hybrid Search) and syntax-aware code chunking for superior retrieval quality.
* **PDF OCR Fallback**: Integrated OCR capabilities for scanned PDF processing.
* **Resilient Chat Persistence**: Enhanced chat state management for high compatibility with session resumes and multi-round tool interactions.
* **Version Bump**: Major version increment to v4.0.0 reflecting the significant architectural shift.
 
## v3.1.1
* **File Upload Input Block**: Fixed file upload input handling to prevent blocking issues. Implemented send button blocking while files are uploading or processing to prevent message send conflicts.
* **File Manager Refactoring**: Converted `FileManager` to use dependency injection with shared RAG manager instead of global instance pattern.
* **Documentation Compliance**: Updated all code comments referencing `AGENTS.md` to reference `CLAUDE.md` as the authoritative documentation source.
* **Version Bump**: Incremented version globally to v3.1.1.

## v3.1.0
* **File Reading Infrastructure**: Introduced a unified file management system supporting PDF extraction, intelligent chunking, and metadata tracking for enhanced RAG capabilities.
* **Configuration Consolidation**: Centralized execution retry limits and RAG parameters in `backend/config.py` as the system's single source of truth.
* **Documentation Synchronization**: Fully aligned all architectural directives with the v3.1.0 state, including new core guides for file management and testing.
* **Template Cleanup**: Purged obsolete experimental Jinja templates to ensure a clean, production-ready release state.
* **Version Bump**: Incremented version globally to v3.1.0.

## v3.0.0
* **Research Agent Overhaul**: Research agent chats can now continue after the report is generated. 
* **Canvas Mode**: Introduced canvas mode to store text as markdown files. 
* **Data Layer Overhaul**: Complete overhaul of the data layer to provide consistency across the application. 
* **Version Bump**: Incremented version globally to v3.0.0.

## v2.3.1
* **Animation Stability**: Fixed an issue where the "generating" animation and thought process dots would stop prematurely during multi-round tool calls. Animations now correctly persist or re-activate across tool transitions.
* **UX Refinement**: Optimized the content flow detection logic to be round-aware, ensuring the thinking state is correctly managed for sequential AI reasoning turns.
* **Favicon Modernization**: Replaced legacy Electric Violet favicons with Ocean Blue SVGs to unify the application's visual identity with the "Aurora + Obsidian" design system.
* **Documentation Refactor**: Completely rewrote the `README.md` to prioritize technical utility, updating outdated model references (Llama 3.3, Qwen 2.5), and hardening installation instructions.
* **Variable Renaming**: Renamed `LM_STUDIO_URL` to `AI_URL` and `LM_STUDIO_API_KEY` to `AI_API_KEY` globally to reflect the move towards generic local AI backend orchestration.
* **Version Bump**: Incremented version globally to v2.3.1.

## v2.3.0
* **Site Visit Tool Fallback**: Implemented a new `playwright_mcp` container for the site visit tool using a Playwright headless browser.
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
