# CHANGELOG

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
