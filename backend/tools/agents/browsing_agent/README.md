# Browsing Agent
**Role:** An autonomous sub-agent specialized in multi-step web interaction, navigation, and data extraction using a headless browser.

## 📂 Subdirectories
| Folder | Responsibility |
| :--- | :--- |
| `tests/` | Comprehensive test suite for vision detection, history pruning, and execution flow. |

## 📄 Core Files
| File | Purpose | Key Symbols/Exports |
| :--- | :--- | :--- |
| `agent.py` | Main orchestration loop managing browser sessions and turn limits. | `flow_fn` |
| `prompts.py` | System prompt templates for text-only and vision-enabled modes. | `BROWSING_AGENT_SYSTEM_PROMPT_TEXT`, `BROWSING_AGENT_SYSTEM_PROMPT_VISION` |

## 🧩 Architectural Context
*   **Dependencies:** `playwright_mcp` (via `playwright_client`), `backend.database`.
*   **Flow:** The agent follows a strict 4-Phase pipeline: Navigation, Observation (Mandatory), Interaction, and Verification. It maintains a persistent browser session across iterations.
*   **Vision Integration:** If a vision-capable model is used, the agent enables the `browser_screenshot` tool and prunes historical screenshots to manage context window efficiency.

## 🛠️ Usage & Conventions
*   **Planning First:** Mechanically enforces the creation of a task list via `manage_task_list` before allowing any browser actions.
*   **Turn Management:** Implements a hard limit on browsing actions (`BROWSING_AGENT_MAX_TURNS`) to prevent runaway costs/loops, with a graceful wrap-up injection.
*   **Scope Restriction:** Can be restricted to specific domains via the `scope` parameter, which is enforced both in the system prompt and at the MCP server level.
*   **Per-user profile:** `_browser_profile()` passes the chat owner as `profile_id` to `browser_start_session` (own persistent profile per user; an owner is required, otherwise the run fails). Only the admin's runs set `attach_portal`, so only they share the portal browser, which is admin only.
*   **Resumption:** Automatically detects existing history and attempts to re-attach to the previous browser session if still active.

## 🛠️ Key Symbols/Exports
| Symbol | Purpose |
| :--- | :--- |
| `flow_fn` | The entry point for the agent's orchestration logic. |
| `BROWSING_AGENT_TOOLS_BASE` | Set of tools available for text-only models. |
| `BROWSING_AGENT_TOOLS_VISION` | Set of tools available for vision-enabled models (includes `browser_screenshot`). |
