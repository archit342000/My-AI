# My-AI Developer & Agents Guide

This document provides essential context, architectural constraints, and operational rules for AI agents working on the `My-AI` repository.

## Documentation Compliance

**Critical**: The documentation in the `docs/` directory defines the correct architecture and patterns for this codebase. Code must always adhere to the documentation.

**If you encounter drift between code and documentation**:
1. **Stop** - do not proceed with changes that violate documentation
2. Request explicit permission from the user
3. Once approved, update the relevant documentation to reflect the new approach
4. Only then proceed with implementation

This ensures the documentation remains accurate and authoritative.

## Quick Start Guide

Use this as your primary reference. For detailed technical specifications, follow the links to the `docs/` directory.
 
| Task | When to use / Context | Documentation |
| :--- | :--- | :--- |
| Understanding system architecture | High-level flow and component interactions | `docs/architecture.md` |
| Making any code change | **Start here** | (CLAUDE.md) |
| Frontend/UI changes | HTML, CSS, and Vanilla JS patterns | `docs/design_directives.md` |
| Database changes | Schema, SQLite, and DB wrapper usage | `docs/database_directives.md` |
| Adding/modifying config | Application configuration and settings | `docs/config_directives.md` |
| Tool implementation | MCP and external tool integration | `docs/tools_directives.md` |
| Canvas operations | Canvas-specific logic and interactions | `docs/canvas_directives.md` |
| Chat agent logic | Chat agent behavior and implementation | `docs/chat_agent.md` |
| Research agent logic | Research agent behavior and implementation | `docs/research_agent.md` |
| Error handling | Standard error patterns and propagation | `docs/error_handling.md` |
| Caching | Caching strategies and directives | `docs/cache_directives.md` |
| llama.cpp streaming | Llama.cpp integration and streaming | `docs/llama_cpp_integration.md` |
| File management | File operations and management rules | `docs/file_management_directives.md` |
| RAG infrastructure | RAG implementation and vector DB usage | `docs/rag_directives.md` |
| Testing & Grid Search | Testing patterns and Grid Search logic | `docs/testing_directives.md` |
| Versioning | Versioning and release rules | `docs/versioning_directives.md` |

---

## System Architecture

| Layer | Technology |
|-------|-----------|
| Frontend | Vanilla HTML5, CSS3, ES6+ (no frameworks) |
| Backend | Python 3.12 Flask |
| Inference | External llama.cpp server (OpenAI-compatible) |
| Vector DB | ChromaDB |
| Storage | SQLite |

**MCP Architecture**: External tools run in isolated containers (`tavily_mcp`, `playwright_mcp`).

---

## Project Boundaries & Inference

**IMPORTANT**: There is a strict separation between this application and the inference infrastructure.

1.  **Inference is External**: The `llama.cpp` server is a **separate repository**.
2.  **No Orchestration**: This codebase contains **zero** logic for starting, managing, or deploying the inference server.
3.  **Consumption Only**: The application purely consumes the inference API via URLs and API Keys provided in the `secrets/` directory.

Any attempt to add inference orchestration (Docker services, model loaders, etc.) to this repository is a violation of the system architecture.

---

## Critical Rules for AI Agents

1. **Library/Tool Versions**: Always confirm the latest version of any required library or tool from the internet before use. Consult their official documentation as needed.

2. **Python is NEVER to be used directly**: 
   - **Always** use the Python interpreter from `venv/` for ALL Python tasks
   - Activate with: `source venv/bin/activate`
   - Or use directly: `venv/bin/python <script.py>`
   - This applies to testing, development, and any code execution

3. **Frontend**: No frameworks. Single `static/script.js`, CSS Custom Properties only.

4. **Database**: Always use `db` from `backend/db_wrapper.py`. Never write raw SQL.

5. **Configuration**: All config in `backend/config.py`. Never hardcode values.

6. **Logging**: Use `log_event()` from `backend.logger`, not `print()`.

7. **Branch Naming**: All branches start with version number (e.g., `3.1.0-feature-name`).

8. **Docker**: Never modify existing containers. Build temporary ones with unique names.

10. **Prefer Incremental Edits**: Always prefer using the `Edit` tool to modify existing code rather than using the `Write` tool to overwrite entire files. This minimizes the risk of accidental deletions and preserves existing code structure. Even when using `Edit`, avoid replacing more code than necessary; target the smallest possible string to achieve the change.

11. **Avoid Tool Call Loops**: If you encounter a pattern of repeated, erroneous tool calls, you must stop the current approach and attempt a different strategy (e.g., different search terms, a different tool, or a different exploration method) instead of repeating the same failing actions.

12. **Avoid Masking Errors with Fallbacks**: Do not implement unnecessary error handling or fallbacks (e.g., empty `try-except` blocks, returning `None` or empty lists instead of propagating errors) that might mask underlying issues. Errors should be handled explicitly or allowed to propagate so they can be detected and debugged.

13. **Avoid Large File Updates**: Even if all changes are within a single file, avoid large, monolithic updates. Instead, apply small, incremental changes to ensure correctness and minimize the risk of error.

14. **Leverage Sub-agents**: For tasks requiring deep codebase exploration, extensive research, or complex multi-step reasoning, consider using the `Agent` tool. Delegating these specialized tasks to sub-agents is preferred as it preserves the main conversation's context and improves efficiency.


---

## Versioning

Follows [SemVer v2.0.0](https://semver.org/). Current: `v3.1.0`.

---

## Historical Pitfalls

* Missing `<think>` tags (llama.cpp)
* File truncation on edits
* Vision payloads in tool messages
* Database locked errors
* State restoration on failures
* Sandbox first for complex logic
* RAG Grid Search: Ensure synthetic testing data is highly discriminative; generic or repetitive data causes zero-recall metric issues.

**When to add to this section:**
- When you encounter or fix a bug that could affect other agents
- When the user points out issues with your changes that reveal a pattern
- When a fix reveals a deeper architectural or workflow issue

Add a concise description that captures the core lesson.

---

## Plan Mode

**Applies to**: `/plan`, `/brainstorm`, and any other skills or commands that require planning.

When you need to create a plan (via Plan Mode, `/plan`, `/brainstorm`, or any planning skill):

1. Create plan files in `plans/` with descriptive names like:
   - `migrate-cache-system-2026-04-04.md`
   - `refactor-auth-flow-2026-04-04.md`
   - `add-search-functionality-2026-04-04.md`

2. Use clear headings and structured steps. The plan should outline the approach, not just a todo list.

3. Include architecture decisions, file changes, and implementation approach

---

## Skills

See `SKILL.md` for available Claude Code skills (e.g., `/report` to generate reports).
