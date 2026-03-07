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

## 2. Design & UI Delegation (`docs/design_directives.md`)

When modifying the frontend, styling, or animations, this document (`AGENTS.md`) defers completely to **`docs/design_directives.md`**.

*   **Single Source of Truth**: The `docs/design_directives.md` file is the absolute authority on all things related to the Luminous Material UI, CSS custom properties, responsive breakpoints, structural logic, and motion design.
*   **Mandatory Reading**: If your task involves modifying HTML, CSS, or any DOM manipulation in `script.js`, you **must** parse and adhere to `docs/design_directives.md` before writing code. Do not invent new styling conventions or introduce UI frameworks.

---

## 3. Best Practices for Development & Contribution

### 3.1 Handling Database Schema Changes & Migration (CRITICAL)
*   **Never Break Existing Data**: The overarching rule for `backend/storage.py` is backward compatibility. Any change to the SQLite schema (adding columns, creating new tables) **MUST** include migration logic.
*   **Migration Pattern**: Use `ALTER TABLE` queries inside `init_db()` and wrap them in `try-except sqlite3.OperationalError:` blocks to silently and safely upgrade existing `chats.db` files without causing startup crashes or data loss for existing users.
*   **ChromaDB Sync**: The RAG system relies on ChromaDB. If you modify how chat data is structured or saved, ensure the vector embeddings stay perfectly synchronized. If a user deletes a chat or resets memory, ChromaDB must be purged accordingly. Never orphan vector data when metadata changes.

### 3.2 Standardized Logging & Dependencies
*   **Use `log_event`**: Do not use standard Python `print()` statements for backend logic tracing. Always import and use `log_event` from `backend.logger` (e.g., `log_event("action_name", {"key": "value"})`). This ensures the event is properly written to the `network_index.jsonl` file and can be debugged via the frontend's `/logs` UI.
*   **Dependency Management**: If you introduce a new Python library to solve a task, you **must** immediately append it to `requirements.txt`. Do not assume the environment will permanently retain pip installs across container restarts or deployments.

### 3.3 Git & Branching Strategy
*   **Standardized Branch Naming**: Every branch name **MUST** start with the target version number you are bumping to, followed by a descriptive hyphenated name.
    *   **Valid Example**: `1.3.1-update-agents-md`
    *   **Valid Example**: `1.4.0-feature-deep-research`
    *   **Invalid Example**: `feature/vision-improvements` (Missing version prefix).
*   **Commit Messages**: Keep commit messages concise, descriptive, and Git-agnostic. The first line should be an imperative summary under 50 characters, followed by an empty line and detailed reasoning if needed.
*   **Verification Before Commit**: Always run the application locally to test functionality (both Light and Dark modes) before submitting code. If modifying the frontend, visually verify all structural and animation changes.

### 3.4 Agent-Specific Operational Best Practices
If you are an AI agent working on this codebase, you must strictly adhere to these operational rules to prevent common execution failures:
*   **Verify Before Marking Complete**: Never assume a file write or search-and-replace command succeeded flawlessly. **Always** use read tools (`read_file`, `list_files`, etc.) to inspect the file state and syntax *after* making a change.
*   **Diagnose Before Modifying Environment**: If you encounter an error (e.g., ModuleNotFoundError), do not immediately attempt to install new packages or edit `requirements.txt`. Read the error logs carefully; prioritize fixing code imports, typos, or file path issues over attempting to alter the environment.
*   **Background Processes & Port Conflicts**: When testing the Flask app, run it in the background (`python3 app.py &`) so your terminal is not blocked. If you need to restart it, you **must** kill the existing process occupying port 5000 first (`kill -9 $(lsof -t -i:5000) 2>/dev/null || true`).
*   **Vanilla DOM Mutations**: Avoid destructive `innerHTML` assignments when updating complex UI components, as this destroys existing event listeners. Prefer `document.createElement()` and `appendChild()`, or ensure the application's global event delegation system in `script.js` catches the new elements.
*   **Edit Source, Not Artifacts**: Never modify files inside `.git/`, `__pycache__/`, or `chroma_db/` directly via text editors. Only interact with the database via Python scripts and only touch the source code files.
*   **Prevent File Truncation (Use Diffs)**: Never overwrite entire large files using full-file write tools, as this frequently leads to accidental truncation or missing code blocks. You **must** use targeted search-and-replace or merge diff tools to modify existing files.
*   **Exact Diffs**: When using search-and-replace or merge diff tools, ensure the `<SEARCH>` block exactly matches the existing file contents line-for-line, including all whitespace and indentation.

### 3.5 Versioning & Releases (SemVer)
*   This project strictly follows [Semantic Versioning 2.0.0](https://semver.org/).
*   **Mandatory Updates**: When a PR introduces a functionality change, bug fix, or UI modification, you **must** bump the version globally across the project.
    *   This includes updating:
        1.  `docs/versioning_directives.md`
        2.  `changelog.md` (Add a new detailed block at the top under the new version header)
        3.  `README.md` (Update the displayed version badge/text)

### 3.6 When to Update `AGENTS.md` (Strict AI Protocol)
This document is a living contract and the ultimate source of truth for AI agents operating on this repository.

**CRITICAL RULE FOR AI AGENTS:**
If any proposed codebase update, feature request, or architectural shift contradicts a rule in this `AGENTS.md` document, or falls completely outside its established scope (e.g., introducing a frontend framework like React), **YOU MUST HALT**.
You are strictly forbidden from executing the change autonomously. You must first:
1.  Explain to the human user exactly how the request violates or exceeds `AGENTS.md`.
2.  Ask for explicit permission to proceed with the codebase change.
3.  Ask for explicit permission to permanently update `AGENTS.md` to reflect this new paradigm.
**ONLY after receiving human approval for both may you proceed.**

You should proactively propose an update to this file if:
*   A new core architectural dependency or framework is authorized.
*   A new "anti-pattern" or recurring agent execution failure is identified.
*   The API payload structures from local LLMs change in future LM Studio releases.

---

## 4. LM Studio & Backend Integrations (`docs/lm_studio_integration.md`)

When modifying backend logic related to LLM inference, chunk streaming, or the `/v1/chat/completions` API endpoints, you **must** refer to `docs/lm_studio_integration.md`.

*   **API Deviations**: Local models running through LM Studio do not behave identically to OpenAI. The integration guide explicitly details handling for `reasoning_content` streams, missing tags, and critical JSON schema deviations.
*   **Mandatory Reading**: If your task involves editing `app.py`, `backend/llm.py`, or any agent logic that parses model output, read `docs/lm_studio_integration.md` to prevent stream-parsing failures.
