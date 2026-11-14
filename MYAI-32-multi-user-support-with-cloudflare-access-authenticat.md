---
id: MYAI-32
title: "Multi-user support with Cloudflare Access authentication"
status: done
created: 2026-11-09
updated: 2026-11-09
links:
  relates_to: [MYAI-2, MYAI-3, MYAI-27, MYAI-45, MYAI-46, MYAI-47]
  split_into: [MYAI-33, MYAI-34, MYAI-35, MYAI-36, MYAI-37, MYAI-38, MYAI-39, MYAI-40, MYAI-41, MYAI-42]
---

## Description
> **Note: investigation only.** This ticket covers the investigation and the plan. No implementation happens here.
> The outcome is a validated plan that gets split into separate implementation tickets (e.g. identity, ownership
> migration, RAG/disk, tools, limits), linked back with `split_into`.

My-AI will be exposed through a new portfolio/gateway project (separate repo) over a Cloudflare Tunnel,
with Cloudflare Access protecting it. Today the app is single-user: one shared `APP_PASSWORD` via HTTP Basic
(`require_auth`, `app.py:312`; username is never checked) and no ownership on any data.

Goal: audit the app for single-user assumptions, then make it multi-user, with identity taken from the
Cloudflare Access JWT (`Cf-Access-Jwt-Assertion`, verified against the team's signing keys) and mapped by email
to a local user. Initially the only user is the owner (admin); invited users come later. Self-signup is out of scope.
Keep identity behind one small interface so a self-hosted provider (e.g. Authentik) can replace Access later.

Known areas (from initial survey 2026-11-09; the investigation must confirm and complete this list):
- **Identity:** replace Basic auth with JWT verification (`before_request` hook, WebSocket upgrades included);
  add a `users` table with roles `admin` | `user`. Decide how direct LAN access (no JWT) is handled.
- **Ownership:** add `user_id` to root tables (`workspaces`, `chats`, `personas`, `skills`, `memories`, `files`,
  `collections`, `file_systems`, `clipboard`, `code_execution_history`); child tables inherit through parents.
  Backfill existing rows to the admin. Scope every `db` wrapper query and route by user (IDOR prevention).
- **Settings:** split `system_settings` into admin-only global settings (model URLs, git allow-list) and per-user prefs.
- **RAG:** per-user ChromaDB collection namespacing, especially memory/preference RAG.
- **Disk:** per-user roots for `files/` and `file_systems/`, keeping the `realpath` containment check.
- **Tasks:** owner checks on the task manager and `pending_callbacks`.
- **Tools:** Playwright portal is one shared VNC browser (`/api/tools/portal/ws`), so it needs per-user sessions or locking;
  code runner needs per-user history, concurrency and quotas; git executor becomes admin-only.
- **Limits:** per-user rate limits on inference and Tavily.
- **Ops:** only the app is routed through the tunnel; never `bastion_ssh` (2222) or the published inference-proxy port.
  Log `user_id` in `log_event`.
- **Frontend:** current-user display; remove any Basic-auth assumptions; per-user prefs in settings store.

## Acceptance criteria
Criteria for this ticket (investigation):
- [x] Investigation findings recorded in Plan: full list of single-user assumptions with file references
- [x] Plan validated, covering approach, migration strategy and open decisions (e.g. LAN access, portal isolation model)
- [x] Work split into implementation tickets, each linked with `split_into` and ordered with `blocked_by` / `conflicts_with`

Target criteria to distribute across the implementation tickets:
- Requests without a valid Access JWT (bad signature, wrong audience, expired) get 401, including WebSocket upgrades
- First run migrates existing data to the admin user without loss; `init_db()` stays idempotent (tested twice and from the previous schema)
- User A cannot read, list, modify or delete user B's workspaces, chats, files, file systems, memories, personas, skills, collections or tasks (tested per route)
- RAG retrieval never returns another user's documents or memories
- Admin-only: global settings and git tools; non-admins get 403
- Playwright portal and code runner are isolated or serialised per user
- Per-user rate limits enforced on inference and search
- Docs updated: `docs/standards/security.md`, `docs/data.md`, `docs/architecture.md`, affected component READMEs
- Tests pass and `ruff check .` is clean

## Plan
**Date:** 2026-11-09  **Status:** Validated

### Objective
Turn the single-user app into a multi-user one behind Cloudflare Access. Every request is tied to a local user resolved from a verified Access JWT. Every piece of user data has an owner, and user A can never read, change or reach user B's data, tools or browser state. Global configuration and host-wide tools become admin-only. This plan is the investigation outcome: the full single-user audit, the design decisions, and the split into implementation tickets (one per step below). It assumes MYAI-1 to MYAI-31 have all merged, and builds on their plans.

### Context
**Requirement and assumptions**
- Requirement: the ticket Description and Acceptance criteria. Identity comes from `Cf-Access-Jwt-Assertion`, verified against the team's signing keys (RS256, `aud` = the Access application AUD tag, `iss` = `https://<team>.cloudflareaccess.com`, keys from `https://<team>.cloudflareaccess.com/cdn-cgi/access/certs`). The `email` claim is mapped to a local user. The implementation ticket re-checks these values in Cloudflare's docs before coding (`AGENTS.md`, dependencies rule).
- Initially the only user is the owner (admin). Invited users are added by the admin later (step 1 adds a CLI to add them). No self-signup.
- The app runs as one process (`app.py:350`, `app.run(... debug=True, use_reloader=False)`, `docker/Dockerfile:50`), so in-memory state (locks, rate counters, the turn claim) is process-wide. Multi-process serving is out of scope.
- The gateway project and the `cloudflared` connector live in a separate repo. Only the app's port 5000 is routed through the tunnel.

**Relevant rules**
- `AGENTS.md`: config only in `backend/config.py`; `db` only (no raw SQL); `log_event()`; tests per module; `ruff check .`; stop and ask before contradicting a documented rule.
- `docs/standards/security.md` "Authentication": `require_auth` is a `before_request` hook that covers every route, including WebSocket upgrades; no routes outside Flask; no exempt paths. This plan changes that section, which is what the ticket asks for.
- `docs/data.md` "Migrations" rules 1-5 (idempotent `init_db()`, table rebuilds in one transaction, backfill in the same step, test twice and from the previous schema). After MYAI-31, rebuilds use `_rebuild_table_with_cascade`. After MYAI-29, every index lives in `_create_indexes`.
- `docs/standards/api.md` / `errors-and-logging.md`: short `{"error": ...}` bodies, details in `log_event`. After MYAI-22, JSON bodies are read with `read_json_object` (`backend/utils.py`).

**Audit: single-user assumptions (checked at `bfd0b76`)**
1. *Identity.* `require_auth` (`app.py:312`) checks only the Basic password, never the username. `APP_PASSWORD` comes from `backend/config.py:19`, a compose secret (`docker/docker-compose.yml:25,163`) and tests (`tests/test_app.py:61-84`). The React client relies on browser Basic auth (`frontend/src/api/client.ts:29`, `credentials: 'same-origin'`). Nothing records who made a request.
2. *Root tables without an owner* (`backend/database/init_db.py`): `workspaces` (45), `chats` (102), `personas` (54), `skills` (316, with a global `name TEXT UNIQUE`), `memories` (255) and `system_settings` (327). Every other table hangs off one of these: `messages`, `files`, `sub_agent_messages`, `collections`, `pending_callbacks`, `clipboard` and `code_execution_history` through `chat_id`; `file_systems` (+ versions and permissions) through `chat_id` or `workspace_id`. The ticket's list named `files`, `collections`, `file_systems`, `clipboard` and `code_execution_history` as roots; they are not, so they inherit ownership. `file_system_counters` is dropped by MYAI-24. `file_systems_search` (FTS5, 373) has no owner columns and is searched by id.
3. *Unscoped list and delete queries*: `get_all_chats`, `delete_all_chats`, `get_all_workspaces` (`wrapper/chat_ops.py`), `get_listed_chats` (MYAI-8), `get_all_personas` and `get_default_persona` (`persona_ops.py`; `is_default` is global), `get_all_skills` and `get_skill_by_name` (`skill_ops.py`), `get_all_preferences` and `clear_preferences` (`preference_ops.py`), `workspace_name_exists` and `persona_name_exists` (MYAI-9).
4. *Routes that act on a client-supplied id with no ownership check*: every `/api/chats/<chat_id>...` route and the workspace routes (`backend/chat/router.py:48-603`); the personas and skills routes (609-735); `/api/files/*` (`backend/files/router.py`); all `/api/file_systems/*` routes, whose owner comes from the `chat_id`/`workspace_id` query or body (`backend/file_system/router.py:25-57` and 59-1063); `/api/tools/active/<chat_id>`, `/clarification/response` (resolves any `callback_id`), `/code-execution/history/<chat_id>` and `/code-execution/run-file` (`backend/tools/router.py`); the live-run WebSocket, which runs any `chat_id` + `filePath` (`app.py:117-148`).
5. *Chat ids are client-generated.* `POST /v1/chat/completions` calls `db.ensure_chat_exists(chat_id)` (`backend/chat/router.py:247-270`) and appends to whatever chat has that id. `/api/chats/save` refuses only existing ids. `uploadedFiles` file ids are loaded and sent to the model without checking that they belong to the chat (router.py:285-295). After MYAI-6, `/resume` also reloads stored `attachments`.
6. *Model tools take ids from model output*: `read_file` (`backend/tools/files.py:13`) and `document_agent_rag_tool` / `grep_uploaded_file_tool` (`backend/tools/agents/document_agent/tools.py:20-37`) accept any `file_id`. The preference tools (`backend/tools/preferences.py`) and `use_skill` (`backend/tools/skills_tool.py:18`) are global. Tools run in task threads with no request context; their only context is `chat_id` (`ToolHandler._execute_pure_tool`, `backend/chat/tool_handler.py:274-280`). The prompt builder injects every preference and every skill (`backend/chat/handler.py:306-307`).
7. *RAG.* Only one collection, `file_store` (`backend/rag/file_rag.py:26`), holds chunks with `file_id` and `chat_id` metadata. Retrieval filters by `file_id` only (110). There is no memory or preference RAG in code (memories go into the prompt in full), so the ticket's "memory/preference RAG" item does not exist. `docs/data.md` mentions research and preference collections, which is stale.
8. *Disk.* `files/<stored_filename>` (uuid names), `file_systems/<chat_id>` and `file_systems/workspaces/<ws_id>` (`backend/file_system/utils.py:7-8,72`), `screenshots/<chat_id>` (`backend/tools/browser.py:94`), `tasks/<chat_id>.json` (`backend/task_manager/executor.py:72-92`), and `cache/` keyed by chat (`backend/database/cache_system.py`). All are reached through ids that belong to an owned chat or workspace.
9. *Process-wide settings that any caller can change*: `/api/tools/config/settings` (GET/POST, arbitrary keys into `system_settings`, including `github_pat`, `git_allowed_commands` and `code_runner_*`); `/config/agents/<name>` PATCH changes module globals in `config` and `AGENT_PROFILES`; `/config/browser` PATCH changes `config.BROWSER_STEALTH_LEVEL` (`backend/tools/router.py:148-333`). The model passthrough forwards every method, including `load` and `unload`, to the inference proxy (`backend/models/__init__.py:52-77`). There are no per-user settings on the server: chat settings (persona, model, sampling) live in browser `localStorage` (`frontend/src/state/settings-store.ts`, `frontend/src/lib/workspace-prefs.ts`).
10. *Logs and raw DB access*: `/api/logs/*` returns every log stream, and `/api/logs/db/table/<name>` dumps raw rows from 14 tables (`backend/logging/router.py:179-249`). `log_event(event_type, data)` (`backend/logging/logger.py:153`) records no user.
11. *Shared browser state.* `playwright_mcp` has one portal Chromium with one profile (`playwright_mcp/server.py:69-71`). When the portal is running, every agent browsing session attaches to it over CDP (503-524) and so gets its cookies and logins. Otherwise sessions share `playwright_data/default_profile` (527-533). The portal VNC and WebSocket (`/api/tools/portal/*`, `app.py:61`) show one desktop to every caller (gated upstream by MYAI-2 and MYAI-3, but not per user). The browsing agent starts sessions itself (`backend/tools/agents/browsing_agent/agent.py:80-101`), so the backend controls the session arguments.
12. *Shared code runner.* Every run executes in one `code_runner_runtime` container as one uid (MYAI-1, 16, 17). `install_packages` changes that shared environment (MYAI-16's package proxy). Timeouts are global settings (MYAI-28). The git tools use the global `github_pat` and allow-list (`backend/tools/implementations/git_executor.py`).
13. *Background work.* `TaskManager` keys tasks and turn claims by `chat_id` (`backend/task_manager/manager.py:41-85`, MYAI-7 and MYAI-19). `recover_tasks` resumes tasks after a restart with no request context (107-151). The in-memory `callback_registry` is keyed by `callback_id` only (`backend/tools/callbacks.py`).
14. *Network reach to the app.* The app publishes no port. It is reached over `secure-internal`, through the bastion SSH tunnel (`docker/docker-compose.yml:36-47`, `README.md:74`). `playwright_mcp` is on the same network, so pages loaded in its Chromium can send requests to `app:5000`. The inference proxy publishes `5001` on the host (`docker/docker-compose.yml:87-88`).
15. *Frontend*: no current-user display; no handling of 401 or 403 beyond the error toast; admin controls (system settings, agents, browser, models, logs page) shown to everyone; the legacy UI at `/legacy/` (`app.py:298-319`) is due for removal (`docs/release.md:31`).

### Approach
- **Identity provider interface** in a new package, `backend/auth/` (create). `IdentityProvider.authenticate(request) -> Identity | None`, where `Identity` holds `email` and `subject`. There are two implementations, chosen by `config.AUTH_PROVIDER`:
  - `cloudflare_access`, the production one. It verifies the JWT with PyJWT and its JWKS client (keys cached, refreshed when an unknown `kid` arrives; RS256 only; `aud`, `iss` and `exp` all required).
  - `static`, for local development and tests. It maps every request to `config.AUTH_STATIC_EMAIL`, and the app refuses to start in `static` mode unless that is set.
  A self-hosted provider such as Authentik later becomes a third implementation.
- **One `before_request` hook**, `authenticate_request`, replaces `require_auth` and also covers WebSocket upgrades, because flask-sock routes are Flask routes.
  - No identity: 401 `{"error": "Unauthorized"}`.
  - Identity, but the email is not an active user: 403.
  - Otherwise the user is put on `flask.g.user` and into a `contextvars` variable that `log_event` reads.
  The SPA shell and assets need auth too, since Access already protects them at the edge. There are no exempt paths. `APP_PASSWORD` and Basic auth are removed.
- **Users table**: `users(id TEXT PK, email TEXT UNIQUE COLLATE NOCASE, role TEXT CHECK IN ('admin','user'), is_active INTEGER, created_at)`.
  - The first admin comes from `config.ADMIN_EMAIL` and is created by `init_db()` when missing.
  - `scripts/manage_users.py` (create) adds, deactivates and lists users. There is no user-management UI in this scope.
- **Ownership lives on the root tables only.** A `user_id TEXT DEFAULT NULL` column is added (`docs/data.md` rule 2: `ADD COLUMN` with a default; no table rebuild) to `workspaces`, `chats`, `personas`, `skills` and `memories`. Child tables inherit ownership through `chat_id` or `workspace_id`, so the only owner check needed is a single lookup of the root.
  - Existing rows are backfilled to the admin.
  - `skills` is rebuilt so that `UNIQUE(name)` becomes `UNIQUE(user_id, name)`, using MYAI-31's `_rebuild_table_with_cascade`.
  - `personas.is_default` becomes per user.
  - New indexes go in MYAI-29's `_create_indexes`.
  - `system_settings` stays global and becomes admin-only.
- **Scoping in the data layer, enforced in routes.** Every list, lookup, create and name-check method on a root table (chat, workspace, persona, skill and preference ops) takes a required `user_id`. Chat-keyed methods (`artifact_ops`, `task_ops`, `file_system_ops`, `code_execution_ops`, `clipboard_ops`, `message_ops`, `history_ops`, `callback_ops`) keep their signatures. Every caller reaches them only after an owner check on the chat or workspace: in routes through the helpers below, and in tools through the server-set `chat_id` (task lists and the clipboard are reached only from tools). Single-row access goes through two new helpers, `require_chat_owner(chat_id)` and `require_workspace_owner(workspace_id)`, which return 404 (not 403) for a missing row or another user's row, so ids can't be probed. File ids, file-system ids and callback ids are resolved to their chat or workspace, and that owner is checked.
- **Tools get the owner from the chat**, never from model arguments. `ToolHandler` adds `user_id` (the chat's owner, looked up once per turn) to `system_ctx`. File and RAG tools reject a `file_id` whose file is not in a chat owned by that user. RAG retrieval also adds `chat_id`/owner filters as defence in depth. `recover_tasks` and the task worker set the logging context from the chat's owner.
- **Admin-only surfaces** (403 for others): system settings, agent and browser config, `/api/logs/*`, model `load`/`unload` (model listing stays open), the git tools and `git_mode`, `install_packages`, the browser portal, and the legacy UI. They share one decorator, `admin_required`.
- **Tool isolation.**
  - Browsing: each user gets their own Playwright profile. The backend passes a `profile_id` derived from the user to `browser_start_session`, and `playwright_mcp` maps it to `playwright_data/profiles/<profile_id>`.
  - Portal: admin-only. Only the admin's sessions may attach to the portal over CDP.
  - Code runner: runs are serialised by one process-wide lock in the backend, so two users' code never runs at the same time in the shared runtime. There is also a per-user cap of concurrent runs that are queued.
- **Rate limits**: in-memory fixed-window counters keyed by `user_id`, set in `config.py`, on turn starts (send and resume) and on Tavily search calls. A limited request gets 429 `{"error": ...}`. The admin can be exempted by config.
- **Frontend**:
  - `GET /api/me` returns `{email, role}`.
  - The UI shows the current user and hides admin controls for users.
  - `localStorage` keys are namespaced by user id, so a shared browser doesn't mix one user's settings with another's.
  - 401 shows a "session expired, reload" state; 403 shows a toast.
- **Rejected alternatives**:
  - Per-user disk roots and moving existing files: every path is already reached through an owned chat or workspace id, and moving data adds migration risk for no added isolation.
  - A per-user Chromium or VNC container: heavy, and only the owner needs the portal now (revisit when invited users need it).
  - A trusted-LAN or source-IP bypass: `playwright_mcp` and any page it loads can reach `app:5000`, so a network-based bypass would let browsed pages act as a user.
  - `user_id` on every child table: duplicates the owner and invites drift.
  - Moving per-user chat settings into a server table: they are browser-local today and nothing needs them on the server.

### Out of scope
- User-management UI, invitations by email, self-signup, and per-user model allow-lists.
- Per-user browser portal containers. Running code as a separate uid or in a separate container per user.
- The gateway, the `cloudflared` deployment and the Access policy configuration (separate repo).
- Removing the legacy UI (`docs/release.md`); it is only restricted to the admin here.
- Multi-process or multi-worker serving.

### Steps
Each step becomes one implementation ticket (`split_into`), planned and validated on its own before implementation. The `Depends on` values become `blocked_by` links. Steps that edit the same files get `conflicts_with` links: `backend/tools/router.py` (3-7), `app.py` (1, 5-7), `backend/chat/router.py` (3, 4, 8), `backend/tools/implementations/code_executor.py` (6, 7), `backend/chat/handler.py` (4, 6), `docs/data.md` (2, 10) and `backend/config.py` (1, 7, 8).

#### Step 1: Identity, users and authentication hook
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/auth/__init__.py`, `backend/auth/providers.py`, `backend/auth/context.py` (create): `IdentityProvider`, `CloudflareAccessProvider`, `StaticProvider`, `get_provider`, `current_user`, `admin_required`. `app.py` (modify): replace `require_auth` with `authenticate_request`; add `GET /api/me`. `backend/config.py` (modify): remove `APP_PASSWORD`; add `AUTH_PROVIDER`, `CF_ACCESS_TEAM_DOMAIN`, `CF_ACCESS_AUD`, `AUTH_STATIC_EMAIL`, `ADMIN_EMAIL`. `backend/database/init_db.py` (modify): `users` table and admin seed. `backend/database/wrapper/user_ops.py` (create) and `backend/database/db_wrapper.py` (modify, mixin registration). `backend/logging/logger.py` (modify): `log_event` adds `user_id` from the context. `scripts/manage_users.py` (create). `requirements.txt` (modify): `PyJWT[crypto]` with an exact `==` pin of the current release, confirmed on PyPI and in its docs and installed in `venv/` (`docs/standards/dependencies.md`). `docker/docker-compose.yml` (modify): `APP_PASSWORD` secret out, new non-secret settings in. Tests: `backend/auth/tests/` (create), `tests/test_app.py` (modify: replace the four Basic-auth tests).
- **Change:** as in Approach. JWT failures (bad signature, wrong `aud`, wrong `iss`, expired, missing, `alg` other than RS256) give 401; an unknown or inactive email gives 403; WebSocket upgrades get the same treatment.
- **Verification:** unit tests sign tokens with a test RSA key and a stubbed JWKS: valid, bad signature, wrong `aud`, wrong `iss`, expired, `alg=none`/HS256, missing header, unknown email, inactive user; WebSocket upgrade without a token gets 401. `init_db()` is run twice and seeds one admin. `ruff check .`.

#### Step 2: Ownership schema and backfill
- **Status:** todo
- **Depends on:** 1
- **Files:** `backend/database/init_db.py` (modify): add `user_id TEXT DEFAULT NULL` to `workspaces`, `chats`, `personas`, `skills` and `memories`, backfilled to the admin in the same step; rebuild `skills` with `UNIQUE(user_id, name)` through `_rebuild_table_with_cascade`; add `idx_<table>_user_id` in `_create_indexes`. `backend/database/tests/test_init_db.py` (modify). `docs/data.md` (modify): `users`, ownership model, fix the stale RAG collection list.
- **Change:** columns are added with `PRAGMA table_info` checks and a default (rule 2), then backfilled. There is no schema-level `NOT NULL` or foreign key on `user_id`. Wrapper inserts require a non-empty `user_id`, and a test asserts that no root row has a NULL owner after `init_db()`. A database without an admin seed stops startup with a clear error rather than leaving ownerless rows.
- **Verification:** migration tests run from a pre-change schema with data (no row lost, every root row owned by the admin, skills uniqueness now per user), and again on an already-migrated database (idempotent).

#### Step 3: Scope chats, workspaces, messages and tasks
- **Status:** todo
- **Depends on:** 2
- **Files:** `backend/database/wrapper/chat_ops.py` (modify: `user_id` on every list, create and delete method, including `get_listed_chats`, `delete_all_chats` and `workspace_name_exists`); callers of `message_ops.py`, `history_ops.py`, `callback_ops.py` (check that each one is behind an owner check); `backend/auth/ownership.py` (create): `require_chat_owner`, `require_workspace_owner`. `backend/chat/router.py` (modify): every `chat_bp` and `openai_bp` route. In `chat_completions`, an existing chat owned by someone else gives 404, a new chat is created with the caller's `user_id`, and every `uploadedFiles` id must belong to that chat. `backend/tools/router.py` (modify): `/active/<chat_id>`, `/clarification/response` (resolve the callback's chat, then check the owner). `backend/task_manager/manager.py`, `worker.py` (modify): set the logging user context from the chat owner, including in `recover_tasks`. `tests/conftest.py` (create): the shared `two_users` fixture. Tests for each.
- **Change:** as in Approach. Cross-user access returns 404 and writes nothing.
- **Verification:** two-user route tests: user B gets 404 on list, get, patch, delete, stream, resume, stop, edit, discard and send to user A's chat; "delete all chats" removes only the caller's chats; workspace CRUD and name checks are per user.

#### Step 4: Scope personas, skills and preferences
- **Status:** todo
- **Depends on:** 2
- **Files:** `backend/database/wrapper/persona_ops.py`, `skill_ops.py`, `preference_ops.py` (modify: `user_id` everywhere, per-user default persona, `persona_name_exists`). `backend/chat/router.py` (modify: personas and skills routes). `backend/tools/router.py` (modify: preference routes). `backend/chat/tool_handler.py` (modify): `user_id` in `system_ctx` from the chat owner. `backend/tools/preferences.py`, `backend/tools/skills_tool.py` (modify: take `user_id`). `backend/chat/handler.py` (modify): per-user preferences and skills in the prompt. Tests for each.
- **Change:** as in Approach.
- **Verification:** two-user tests: route CRUD, the preference tools and `use_skill` see only the owner's rows; the prompt for user B contains none of user A's preferences or skills; the same skill name can exist for two users.

#### Step 5: Scope files, file systems, RAG and code execution
- **Status:** todo
- **Depends on:** 3
- **Files:** `backend/files/router.py` (modify, all routes). `backend/file_system/router.py` (modify: `normalize_workspace_id` and every route resolve and check the owner of `chat_id`/`workspace_id`). `backend/file_system/manager.py` (modify where it lists by owner). `backend/tools/files.py`, `backend/tools/agents/document_agent/tools.py` (modify: reject a file outside the caller's chats). `backend/rag/file_rag.py` (modify: `retrieve_for_file` also filters on `chat_id`). `backend/tools/router.py` (modify: `/code-execution/history/<chat_id>`, `/code-execution/run-file`). `app.py` (modify: `code_execution_ws_proxy` checks the init message's `chat_id` owner before `collect_project_files`). `backend/tools/clipboard.py`, `backend/tools/tasks.py` (check that they use only the server-set `chat_id`). Callers of `backend/database/wrapper/artifact_ops.py`, `file_system_ops.py`, `code_execution_ops.py`, `task_ops.py` and `clipboard_ops.py` (check that each one is behind an owner check). Tests for each.
- **Change:** as in Approach. Paths keep the existing `realpath` containment checks; no disk layout change.
- **Verification:** two-user tests for each `/api/files` and `/api/file_systems` route (including raw, export, versions and diff), run-file, history and the live-run WebSocket; `read_file` and the document-agent tools return "not found" for another user's file id; a RAG retrieval test shows no cross-user chunks.

#### Step 6: Admin-only surfaces
- **Status:** todo
- **Depends on:** 1, 3
- **Files:** `backend/tools/router.py` (modify: `config/settings`, `config/agents`, `config/browser` get `admin_required`). `backend/logging/router.py` (modify: whole blueprint admin-only). `backend/models/__init__.py` (modify: only `GET` is open; other methods are admin-only; stop forwarding `Cf-Access-Jwt-Assertion` and cookies upstream). `backend/tools/implementations/git_executor.py` and `backend/chat/handler.py` (modify: git tools and `git_mode` only for admin-owned chats). `backend/tools/implementations/code_executor.py` (modify: `install_packages` admin-only). `app.py` (modify: `/legacy/*` admin-only). Tests for each.
- **Change:** as in Approach. A non-admin enabling `git_mode` gets 403; for a chat owned by a non-admin, the tool is not in the catalog.
- **Verification:** for each route, the admin gets 2xx and a user gets 403 with no side effect (settings unchanged, `config` globals unchanged).

#### Step 7: Browser and code-runner isolation
- **Status:** todo
- **Depends on:** 3, 6
- **Files:** `playwright_mcp/server.py` (modify): `browser_start_session` takes `profile_id` (validated `^[a-z0-9_-]{1,64}$`) and uses `playwright_data/profiles/<profile_id>`; it attaches over CDP only when `profile_id` is the portal owner's. `backend/tools/agents/browsing_agent/agent.py` (modify: pass the profile from the chat owner). `backend/tools/router.py` and `app.py` (modify: portal routes and `portal_ws_proxy` are admin-only). `backend/tools/implementations/code_executor.py` and `app.py` (modify: a process-wide run lock and a per-user queue cap around `run_code`, `run_file` and live runs). `backend/config.py` (modify: the cap). Tests in `playwright_mcp/tests/`, `backend/tools/tests/`, `tests/test_app.py`.
- **Change:** as in Approach.
- **Verification:** unit tests: two users get different profile directories; a non-admin session never attaches over CDP; two concurrent runs do not overlap (timestamps); over-cap runs get a clear error. Live check on a throwaway stack: a cookie set in user A's session is absent in user B's. A file written to `/tmp` by one run is gone before the next run (decision 3).

#### Step 8: Per-user rate limits
- **Status:** todo
- **Depends on:** 3
- **Files:** `backend/auth/rate_limit.py` (create): a fixed-window limiter keyed by `user_id`. `backend/config.py` (modify: `RATE_LIMIT_TURNS_PER_MINUTE`, `RATE_LIMIT_SEARCHES_PER_DAY`, `RATE_LIMIT_EXEMPT_ADMIN`). `backend/chat/router.py` (modify: `chat_completions`, `resume_chat`, checked before MYAI-7's turn claim). The Tavily call sites `backend/tools/agents/search_web_agent/agent.py`, `backend/tools/agents/research_agent/agent.py` and `backend/tools/agents/research_agent/research_utils.py` (modify: check the chat owner's search limit before each `tavily_client.execute_tool`). Tests for each.
- **Change:** as in Approach. Exceeding a limit gives 429 `{"error": ...}` and a `log_event`, with nothing written.
- **Verification:** unit tests for the window rollover and per-user independence; route tests for 429 on send and resume; the search tool returns a short `Error:` result when the limit is hit.

#### Step 9: Frontend
- **Status:** todo
- **Depends on:** 1, 6
- **Files:** `frontend/src/api/me.ts` (create); `frontend/src/state/settings-store.ts`, `frontend/src/lib/workspace-prefs.ts` (modify: user-namespaced keys, keeping the old keys for the admin on first load); the app shell and sidebar (modify: show the current user); the settings dialogs, the model load and unload controls, the logs route and the portal entry (modify: hidden for `role !== 'admin'`); `frontend/src/api/client.ts` (modify: 401 shows a reload prompt). Tests next to each file. `frontend/README.md`, `docs/frontend.md` (modify).
- **Change:** as in Approach.
- **Verification:** `npm run typecheck`, `lint`, `test`, `build`; component tests for the admin and user roles; a Playwright smoke test with the `static` provider as admin and as user.

#### Step 10: Docs, deployment and end-to-end check
- **Status:** todo
- **Depends on:** 1-9
- **Files:** `docs/standards/security.md` (Authentication, Ownership, Admin-only sections), `docs/architecture.md` (auth component, request flow through Access), `docs/data.md` (checked against step 2), `README.md` (access is through the Access hostname; with `cloudflare_access` the SSH tunnel path no longer works without a JWT; with the `static` provider (local development only) every request runs as `AUTH_STATIC_EMAIL`; keep it within the 100-line budget in `tests/test_docs.py`), `backend/README.md` and the component READMEs that each step touched (`backend/auth/README.md` created in step 1). `docker/docker-compose.yml` (check that only the app joins the tunnel network, with no new published ports).
- **Change:** docs match the code; the deployment note records that only the app is routed (never `bastion_ssh` 2222 or the inference proxy's 5001).
- **Verification:** live check through a real Access application with two identities: no JWT gives 401; a tampered JWT gives 401; user B gets 404 for user A's chat, file and artifact; user B gets 403 on admin routes. Full `pytest`, `npm` checks and `ruff check .`.

### Tests
- Backend: `venv/bin/python -m pytest` for each touched package, then the full suite (`docs/standards/testing.md`). Every step adds two-user tests for its routes, built on a shared `two_users` fixture created in step 3 (`tests/conftest.py`, create).
- Migration: from the previous schema and run twice (`backend/database/tests/test_init_db.py`).
- Frontend: `npm run typecheck && npm run lint && npm test && npm run build` in `frontend/`.
- `ruff check .` at the end of every step.

### Risks and open questions
- **Open decision, LAN or SSH-tunnel access (recommended: no bypass).** In `cloudflare_access` mode every request needs a JWT, so the bastion tunnel path stops working for normal use. Local development uses `AUTH_PROVIDER=static`. The alternative, a trusted-network bypass, is rejected because `playwright_mcp` can reach `app:5000` (audit item 14).
- **Open decision, portal isolation model (recommended: admin-only portal plus per-user agent profiles).** Alternatives: a single-holder portal lock shared by users, or per-user portal containers. Both are larger, and only the owner needs the portal now.
- **Open decision, code-runner isolation (recommended: global run serialisation).** It costs throughput but needs no new infrastructure. Per-user runtimes or uids are the follow-up if load grows.
- **Open decision, legacy UI (recommended: admin-only until it is removed).** The alternative is to remove it before this work.
- **Risk:** a missed route or wrapper call leaks data. Mitigation: `user_id` is a required argument (no default) on every scoped wrapper method, so a missed caller fails in tests, plus the per-route two-user tests.
- **Risk:** JWKS fetch failures would lock everyone out. Mitigation: cached keys keep working, a fetch failure fails closed (401) and is logged, and there is no fallback to unauthenticated.
- **Risk:** client-generated chat ids could be claimed first by another user (squatting). Mitigation: owner check on every access; the client creates ids as UUIDs.
- **Risk:** `log_event` runs from threads without a request context. Mitigation: a context variable set in the hook and by the task worker; `user_id` is `null` when unknown, never guessed.

### Success criteria
- [ ] Requests without a valid Access JWT (bad signature, wrong audience, expired) get 401, including WebSocket upgrades (step 1).
- [ ] The first run migrates existing data to the admin without loss; `init_db()` stays idempotent, tested twice and from the previous schema (step 2).
- [ ] User A cannot read, list, modify or delete user B's workspaces, chats, files, file systems, memories, personas, skills, collections or tasks, tested per route (steps 3-5).
- [ ] RAG retrieval never returns another user's documents (step 5). There is no memory RAG to scope (audit item 7).
- [ ] Global settings, git tools, logs, model load and unload, and package installs are admin-only; non-admins get 403 (step 6).
- [ ] Playwright profiles are per user, the portal is admin-only, and code runs are serialised (step 7).
- [ ] Per-user rate limits are enforced on inference turns and search (step 8).
- [ ] Docs are updated: `docs/standards/security.md`, `docs/data.md`, `docs/architecture.md` and the affected component READMEs (steps 2, 9, 10).
- [ ] Tests pass and `ruff check .` is clean (every step).

### Decisions (2026-11-09, user approved the recommendations)
1. **LAN or SSH-tunnel access:** no bypass. In `cloudflare_access` mode every request needs a valid Access JWT, with no exception by network, source IP or header. `AUTH_PROVIDER=static` is for local development and tests only, and is never active at the same time. Reason: `playwright_mcp` and the pages it loads can reach `app:5000`, and forwarded headers can be forged inside the network.
2. **Portal isolation:** the portal (VNC, WebSocket, init) and attaching to its Chromium over CDP are admin-only. Agent browsing uses a persistent profile per user, chosen by the backend from the chat owner and never by the model. Per-user portals are deferred until invited users need manual logins.
3. **Code-runner isolation:** one process-wide lock serialises all code runs, plus a per-user cap on queued runs. `install_packages` is admin-only. Step 7 also confirms that nothing a run writes outside its sandbox directory (for example `/tmp`) survives into the next run, and clears it between runs if it does.
4. **Legacy UI:** `/legacy/*` is admin-only until it is removed under `docs/release.md`. It gets no multi-user work.

### Reviewer brief
- **Objective:** make My-AI multi-user behind Cloudflare Access. Every request is tied to a local user from a verified Access JWT, every piece of user data has an owner, and users can't reach each other's data, tools or browser state. Global configuration and host-wide tools become admin-only. This ticket only produces the plan; the 10 steps become separate implementation tickets, done after MYAI-1 to MYAI-31.
- **Key decisions:**
  - Identity goes through the `backend/auth/` `IdentityProvider` interface, with a `cloudflare_access` (JWT, RS256, `aud`/`iss`/`exp`) implementation and a dev-only `static` one.
  - One `before_request` hook gives 401 when there is no identity and 403 for an unknown or inactive user. It covers WebSocket upgrades too, and there are no exempt paths. `APP_PASSWORD` is removed.
  - New `users` table; the admin is seeded from `ADMIN_EMAIL`; there is a CLI to manage users.
  - `user_id TEXT DEFAULT NULL` is added to `workspaces`, `chats`, `personas`, `skills` and `memories`, and backfilled to the admin. Skills become unique per user. Child tables inherit ownership through the chat or workspace.
  - Methods on root tables take a required `user_id`. Chat-keyed methods sit behind `require_chat_owner` / `require_workspace_owner`, which return 404 for another user's data.
  - Tools get the owner from the server-side `chat_id`, never from model arguments.
  - Admin-only, via `admin_required`: system, agent and browser settings; logs; model load and unload; git; package installs; the portal; the legacy UI.
  - Browser profiles are per user, and only the admin's sessions may attach to the portal over CDP. Code runs are serialised process-wide, with a per-user queue cap.
  - In-memory per-user rate limits on turns and Tavily calls return 429.
  - Frontend: `/api/me`, user-namespaced `localStorage`, admin controls hidden from users.
  - No LAN bypass; no per-user disk roots.
- **Out of scope:** user-management UI and invitations, per-user portal containers or runtime uids, gateway and `cloudflared` deployment, removing the legacy UI, multi-process serving.
- **Success criteria:** the ticket's target acceptance criteria, mapped to steps 1-10.

The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- **Round 1:** the validator returned FAIL (3 BLOCKING, 6 MINOR). My judgement: FAIL.
  - B1, valid: `ADD COLUMN` without a default broke `docs/data.md` rule 2, and the schema was specified two ways. Now `user_id TEXT DEFAULT NULL` everywhere, with the wrapper and a test enforcing that `user_id` is set.
  - B2, valid: step 6 needs chat ownership. `Depends on` is now 1, 3.
  - B3, valid as an inconsistency: the Approach said every wrapper method takes `user_id`. It now says root-table methods take `user_id` and chat-keyed methods sit behind owner checks; their callers are added to steps 3 and 5.
  - The six MINOR issues were valid and fixed: the conftest file is now in step 3; `conflicts_with` links added; the README line budget noted; the `==` pin rule added; line 376 corrected to 373; for the previous-schema fixture, step 2 already requires the rule-5 tests and the fixture is left to the implementation ticket.
- **Round 2 (diff-scoped):** the validator returned PASS (0 BLOCKING, 3 MINOR). My judgement: PASS. All round 1 BLOCKING issues are confirmed fixed. Mechanical fixes for the three MINOR issues: `handler.py` and `docs/data.md` added to `conflicts_with`; `task_ops`/`clipboard_ops` callers added to step 5; the README wording for each provider mode corrected.

## Implementation notes

## Verification

## Review history

## Log
- 2026-11-09: created (investigation only; implementation to be split into separate tickets)
- 2026-11-09: linked relates_to MYAI-2, MYAI-3, MYAI-27 (portal and code-runner auth overlap with per-user tool isolation)
- 2026-11-09: started investigation and planning (status in-progress)
- 2026-11-09: plan validated, 2 rounds (10 steps to split into implementation tickets; 4 open decisions recorded)
- 2026-11-09: decisions recorded: no LAN bypass; admin-only portal + per-user browser profiles; global code-run serialisation; legacy UI admin-only (user approved)
- 2026-11-09: linked split_into MYAI-33 (Step 1)
- 2026-11-09: linked split_into MYAI-34 (Step 2)
- 2026-11-09: linked split_into MYAI-35 (Step 3)
- 2026-11-09: linked split_into MYAI-36 (Step 4)
- 2026-11-09: linked split_into MYAI-37 (Step 5)
- 2026-11-09: linked split_into MYAI-38 (Step 6)
- 2026-11-09: linked split_into MYAI-39 (Step 7)
- 2026-11-09: linked split_into MYAI-40 (Step 8)
- 2026-11-09: linked split_into MYAI-41 (Step 9)
- 2026-11-09: linked split_into MYAI-42 (Step 10)
- 2026-11-09: closed: investigation done; work split into MYAI-33 to MYAI-42 (Steps 1-10)
- 2026-11-09: MYAI-33 planning moved the user CLI from `scripts/manage_users.py` to `backend/auth/cli.py` (CI-tested) and added `id` to `/api/me`
- 2026-11-09: decision 3 amended (user, during MYAI-39 validation): the code runner splits uids (the server as root with only SETUID, SETGID and KILL; user code as `runner`; installs as `runner-pkg`), with a documented docker.md exception; runs stay serialised
- 2026-11-09: linked relates_to MYAI-47 (decision 3)
- 2026-11-09: decision 3 amendment reverted (user): no split uids in MYAI-39. MYAI-39 keeps the bounded cleanup; split-uid isolation moved to the spike MYAI-47; no restriction on non-admin code execution
- 2026-11-09: linked relates_to MYAI-45 (follow-up found during the epic)
- 2026-11-09: linked relates_to MYAI-46 (follow-up found during the epic)
