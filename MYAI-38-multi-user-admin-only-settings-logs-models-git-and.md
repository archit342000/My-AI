---
id: MYAI-38
title: "Multi-user: admin-only settings, logs, models, git and legacy UI"
status: done
created: 2026-11-09
updated: 2026-11-10
links:
  blocks: [MYAI-39, MYAI-41, MYAI-42]
  blocked_by: [MYAI-33, MYAI-35]
  conflicts_with: [MYAI-36, MYAI-37]
  split_from: [MYAI-32]
---

## Description
Split from MYAI-32 (Step 6: Admin-only surfaces). Part of making My-AI multi-user behind Cloudflare Access. Implement after MYAI-1 to MYAI-31 have merged.

Read the MYAI-32 Plan first: the Audit (single-user assumptions with file references), the Approach, the Decisions and the Reviewer brief are binding for this ticket. Step scope from MYAI-32:

- **Depends on:** MYAI-33, MYAI-35
- **Files:** `backend/tools/router.py` (modify: `config/settings`, `config/agents`, `config/browser` get `admin_required`). `backend/logging/router.py` (modify: whole blueprint admin-only). `backend/models/__init__.py` (modify: only `GET` is open; other methods are admin-only; stop forwarding `Cf-Access-Jwt-Assertion` and cookies upstream). `backend/tools/implementations/git_executor.py` and `backend/chat/handler.py` (modify: git tools and `git_mode` only for admin-owned chats). `backend/tools/implementations/code_executor.py` (modify: `install_packages` admin-only). `app.py` (modify: `/legacy/*` admin-only). Tests for each.
- **Change:** as in Approach. A non-admin enabling `git_mode` gets 403; for a chat owned by a non-admin, the tool is not in the catalog.
- **Verification:** for each route, the admin gets 2xx and a user gets 403 with no side effect (settings unchanged, `config` globals unchanged).

## Acceptance criteria
- [x] System, agent and browser settings, `/api/logs/*`, model load and unload, and `/legacy/*` return 403 for non-admins with no side effect; package installs (a model tool with no route) are refused on the tool path for non-admin chats and run for the admin; the admin gets 2xx on the routes (tested per route)
- [x] Git tools and `git_mode` are available only in admin-owned chats
- [x] The model passthrough no longer forwards the Access JWT or cookies upstream
- [x] Tests pass and `ruff check .` is clean

## Plan
**Date:** 2026-11-09  **Status:** Validated

### Objective
Restrict everything that changes process-wide state, exposes other users' data, or reaches host-wide tools to the admin. That covers system, agent and browser settings, the log and raw-DB endpoints, model load/unload and other non-GET model calls, the git agent and git mode, package installs, and the legacy UI. Non-admins get 403 with no side effect. The model passthrough also stops forwarding the caller's identity and cookies upstream.

### Context
- **Requirement:** this ticket's Description and Acceptance criteria. MYAI-32 Plan: Audit items 9, 10 and 12, Step 6, Decision 4 (legacy UI is admin-only).
- **Assumes merged:**
  - MYAI-33: `backend/auth/context.py` with `current_user()` (`{id, email, role}`) and the `admin_required` decorator (403 `{"error": "Forbidden"}`); `db.get_user`.
  - MYAI-35: `db.get_chat_owner`; `backend/conftest.py` `login_as`, `user_a`, `user_b`.
  - MYAI-36: `ToolHandler` resolves the chat owner (`self.user_id`).
  - MYAI-28: settings validation in `update_system_settings`, and `code_runner_max_timeout` in `get_system_settings`.
  - MYAI-5 and MYAI-22: error shapes and `read_json_object`.
- **Current code:**
  - **Tools router** (`backend/tools/router.py`): `get_agents_config` and `update_agent_config` (148-226) change `config` module globals and `AGENT_PROFILES`. The browser config routes (228-243) change `config.BROWSER_STEALTH_LEVEL`. `get_system_settings` and `update_system_settings` (291-333) cover `github_pat`, `git_allowed_commands` and `code_runner_*`.
  - **Logs** (`backend/logging/router.py`): `logs_bp` serves `/ui`, `''`, `/detail`, `/events`, `/app`, `/app/lines`, `/db/tables` and `/db/table/<table_name>` (raw rows from 14 tables).
  - **Models** (`backend/models/__init__.py:52-77`): `pass_through` forwards every method and every request header except `Host` to the inference proxy.
  - **Frontend use:** `ChatSettingsModal` reads the model list (GET) for everyone (`frontend/src/features/settings/ChatSettingsModal.tsx:14`). Load, unload and the speed test are in `ModelsDialog`.
  - **Tools:**
    - `ToolSpec` (`backend/tools/spec.py`) has `requires_mode`.
    - `ToolRegistry.get_main_tools(active_modes)` and `get_directives_for_scope(scope, active_modes)` (`backend/tools/__init__.py:77-110`) filter on it.
    - `git_agent` (`backend/tools/catalog/git.py`, `requires_mode="git_mode"`) and `install_packages` (`backend/tools/catalog/code.py:70`, `requires_mode="code_execution_mode"`) are both MAIN-scope only.
    - `PromptContext.active_modes` (`backend/chat/prompt_builder.py:24-31`) comes from `chat_metadata`.
    - `ChatHandler` syncs `gitMode` into `git_mode` (`backend/chat/handler.py:110-119`) and builds tools with `get_main_tools(ctx.active_modes)` (456).
    - `ToolHandler._execute_pure_tool` dispatches by name (`backend/chat/tool_handler.py:265`), and agents go through `agent_handler.execute_agent` (163).
  - **Legacy UI:** routes at `app.py:298-319` (`legacy_index`, `legacy_logs`, `legacy_assets`).
- **Rules:** `docs/standards/security.md` (git allow-list, secrets never returned); `docs/standards/api.md` (403 for a forbidden operation); `docs/standards/testing.md`.

### Approach
- **Route gating:**
  - `admin_required` on `get_agents_config`, `update_agent_config`, both browser config routes, and both system settings routes. GET is included, since the settings expose the git allow-list and runner limits, and only the admin dialogs read them.
  - `logs_bp.before_request` calls a new `forbid_non_admin()` helper in `backend/auth/context.py`, which returns the same 403 or None, so every current and future logs route is covered.
  - The legacy routes get `admin_required`.
- **Model passthrough:**
  - `GET` stays open, since everyone needs the model list; other methods need admin.
  - For every method, including GET, forwarded headers drop `Host`, `Cookie`, `Authorization` and `Cf-Access-Jwt-Assertion` (case-insensitive), so the caller's identity token never reaches the proxy. The inference proxy uses its own keys (`inference_proxy/config.py:12-15`) and reads no client `Authorization`.
- **Admin-only tools:**
  - `ToolSpec` gains `admin_only: bool = False`, set on `git_agent`, `execute_git` (GIT scope, used inside the git agent) and `install_packages`. `execute_git` needs it because `ToolHandler.handle_tool_calls` dispatches any registry name (`tool_handler.py:69`), not only the tools offered to the model.
  - `PromptContext` gains `is_admin: bool = False`, and `active_modes` adds `"admin": is_admin`.
  - `get_main_tools` and `get_directives_for_scope` skip `admin_only` specs unless `active_modes.get("admin")`. With `active_modes=None` (agent scopes), they are skipped too, which is safe because both tools are MAIN-only.
  - `ChatHandler` computes `is_admin` from the chat owner's role (`db.get_user(db.get_chat_owner(chat_id))["role"] == "admin"`) and passes it to `PromptContext`.
  - **Enabling git mode:**
    - `chat_completions` (`backend/chat/router.py`) returns 403 `{"error": "Forbidden"}` before any write when the request body has a truthy `gitMode` and `current_user()` isn't an admin. This is the binding 403 from MYAI-32 Step 6, and it comes after MYAI-35's owner check and before `claim_chat` and `claim_turn`. `resume_chat` gets the same check before MYAI-19's `claim_turn`: its `RESUME_STRIP_KEYS` (`router.py:472`) doesn't include `gitMode`, so the flag reaches `initiate_chat`. A shared helper, `_forbid_git_mode_for_non_admin(body)`, in `backend/chat/router.py` serves both routes. The chat PATCH doesn't accept `git_mode`.
    - As defence in depth, `ChatHandler`'s mode sync (`handler.py:110-119`) drops a truthy `gitMode` for a non-admin owner before the DB write and logs `chat_git_mode_denied`.
- **Dispatch guard:**
  - `ToolHandler.__init__` sets `self.owner_is_admin`: `db.get_user(self.user_id)["role"] == "admin"` when `self.user_id` (from MYAI-36) is set and the user exists; otherwise False, so a missing owner is denied.
  - `ToolHandler` checks `ToolRegistry.get_spec(name).admin_only` before running a pure tool or an agent. For a non-admin owner it returns `"Error: This tool is not available."` and logs `tool_admin_only_denied`. A model naming a hidden tool therefore can't run it.
- **Deviation from the acceptance criteria (recorded 2026-11-09):** package installs have no My-AI HTTP route (`install_packages` is only a model tool, `code_executor.py:336`; the runner's own `/install` is internal to `code_runner_mcp`). So "403" can't apply to them. They're refused on the tool path instead, and the criterion is amended to say so.
- **Rejected:**
  - Hiding the admin settings only in the frontend: the API would stay open.
  - Turning `git_mode` off in the DB for non-admin chats: there are none yet, and the runtime gate covers future ones without a migration.
  - Gating the model GET: it breaks model selection for every user.

### Out of scope
Frontend hiding of admin controls (MYAI-41); the portal routes and browser profiles (MYAI-39); rate limits (MYAI-40); user management UI.

### Steps
#### Step 1: Admin helper
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/auth/context.py` (modify): new `forbid_non_admin()`. `backend/auth/tests/test_context.py` (modify).
- **Change:** as in Approach.
- **Verification:** returns None for an admin and the 403 tuple for a user or no user.

#### Step 2: Settings, logs, models and legacy routes
- **Status:** todo
- **Depends on:** 1
- **Files:** `backend/tools/router.py` (modify: the six config routes). `backend/logging/router.py` (modify: blueprint hook). `backend/models/__init__.py` (modify: `pass_through`). `app.py` (modify: legacy routes). Tests: `backend/tools/tests/test_router.py`, `backend/logging/tests/test_router.py`, `backend/models/tests/test_models.py` (modify: their test apps use MYAI-35's `login_as` fixture with an admin for the existing tests, and a user for the new cases); `tests/test_app.py` (modify: its `app` fixture already stubs an admin, per MYAI-33).
- **Change:** as in Approach.
- **Verification:**
  - Each gated route gives 403 for a user, and the side effect doesn't happen: `config` globals, `AGENT_PROFILES`, `BROWSER_STEALTH_LEVEL` and `db.set_setting` unchanged; no file read in logs; no upstream call for non-GET model requests.
  - The admin gets the existing responses.
  - A model GET by a user is forwarded, and the forwarded headers have no `Cookie`, `Authorization` or `Cf-Access-Jwt-Assertion`.
  - `/legacy/` gives 403 for a user and 200 for the admin.

#### Step 3: Admin-only tools
- **Status:** todo
- **Depends on:** 1
- **Files:** `backend/tools/spec.py` (modify: `admin_only`). `backend/tools/catalog/git.py`, `backend/tools/catalog/code.py` (modify: set it). `backend/tools/__init__.py` (modify: the two filters). `backend/chat/prompt_builder.py` (modify: `is_admin`, `active_modes`). `backend/chat/handler.py` (modify: compute `is_admin`; deny `gitMode` for non-admins). `backend/chat/tool_handler.py` (modify: dispatch guard). `backend/chat/router.py` (modify: the `gitMode` 403 helper, called from `chat_completions` and `resume_chat`). Tests: `backend/tools/tests/test_init.py`, `backend/tools/tests/test_spec.py`, `backend/chat/tests/test_prompt_builder.py`, `test_handler.py`, `test_tool_handler.py` (modify: patch `db.get_user` and `get_chat_owner` for the owner role), and `test_router.py` (modify: log in through `login_as`).
- **Change:** as in Approach.
- **Verification:**
  - With `admin=False`, `get_main_tools` and the directives omit `git_agent` and `install_packages` even when `git_mode` and `code_execution_mode` are on; with `admin=True`, they're included.
  - `POST /v1/chat/completions` and `POST /api/chats/<id>/resume` with `gitMode: true` from a user give 403, with no message, chat or turn written and no turn claimed. From the admin they're accepted.
  - A handler test for a user-owned chat with `gitMode=True` leaves `git_mode` unset and logs the denial.
  - `ToolHandler` refuses `git_agent`, `execute_git` and `install_packages` for a user owner and for a missing owner, without calling the implementation or agent, and runs them for an admin owner.

#### Step 4: Docs and full gate
- **Status:** todo
- **Depends on:** 2, 3
- **Files:** `docs/standards/security.md` (modify: an "Admin-only" subsection listing these surfaces and the `admin_only` tool flag); `docs/tools.md` (modify: when to set `admin_only`); `backend/tools/README.md`, `backend/logging/README.md`, `backend/models/README.md` (modify: one line each).
- **Change:** docs match the code.
- **Verification:** with the env from `docs/standards/testing.md`: `pytest backend/auth`, `backend/tools`, `backend/logging`, `backend/models`, `backend/chat`, `tests`, then `pytest backend`; `ruff check .`. Live check with `AUTH_PROVIDER=static`, run twice and restarting the app between runs: first with `AUTH_STATIC_EMAIL` set to a user added with the CLI (settings, logs and model-load calls give 403; sending or resuming with git mode on gives 403), then with the admin email (all work).

### Tests
Covered per step. Each 403 test asserts that no side effect happened.

### Risks and open questions
- **The frontend shows admin controls to users until MYAI-41,** and those calls get 403. That's acceptable, because no non-admin users exist before MYAI-37 and MYAI-41 merge.
- **Agent-scope tools** don't check `admin_only`, because none are marked. If a later tool marks an agent-scope spec, the filter with `active_modes=None` already skips it.

### Success criteria
- [x] Settings (system, agents, browser), logs, model non-GET calls and the legacy UI give 403 for non-admins, with no side effect.
- [x] `git_agent`, `execute_git` and `install_packages` are neither offered to nor runnable by non-admin chats; enabling git mode gives 403 for non-admins.
- [x] The model passthrough no longer forwards the Access JWT, cookies or `Authorization`.
- [x] Tests pass and `ruff check .` is clean.

### Reviewer brief
- **Objective:** make everything process-wide or host-reaching admin-only: settings, logs and raw DB, model non-GET calls, the git agent, `execute_git` and git mode, package installs, the legacy UI. Non-admins get 403 (or a tool refusal) with no side effect; the model passthrough stops forwarding identity headers.
- **Key decisions:**
  - `admin_required` on the six config routes and the legacy routes; a `logs_bp.before_request` uses the new `forbid_non_admin()`.
  - The model passthrough leaves GET open; other methods need admin. `Cookie`, `Authorization` and `Cf-Access-Jwt-Assertion` are stripped for all methods.
  - `ToolSpec.admin_only` is set on `git_agent`, `execute_git` and `install_packages`. The registry filters them out unless `active_modes["admin"]` (from `PromptContext.is_admin`, the chat owner's role).
  - The `ToolHandler` dispatch guard uses `owner_is_admin` (a missing owner is denied).
  - Enabling git mode (`gitMode`) in completions or resume gives 403 for non-admins, through a shared helper before any write or claim; the handler drops it as defence in depth.
  - Package installs are refused on the tool path, since there's no route; the criterion is amended.
- **Out of scope:** frontend hiding (MYAI-41), portal (MYAI-39), rate limits (MYAI-40), user management UI.
- **Success criteria:** as listed in the Plan.

The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- **Round 1:** the validator returned FAIL (2 BLOCKING, 5 MINOR). My judgement: FAIL.
  - Both BLOCKING issues were valid and fixed:
    - `execute_git` was dispatchable by name, so it's now `admin_only`.
    - The binding design requires a 403 for enabling git mode, so `chat_completions` now returns 403 and the handler keeps the drop as defence.
  - MINOR, fixed: the `install_packages` mapping; `owner_is_admin` with None denied; tests use `login_as`; a two-run live check with a restart; header stripping applies to all methods (the proxy uses its own keys).
- **Round 2 (diff-scoped):** the validator returned FAIL (1 BLOCKING, 1 MINOR). My judgement: FAIL.
  - BLOCKING, valid: my claim that resume strips `gitMode` was wrong (`RESUME_STRIP_KEYS` at `router.py:472` doesn't include it). `resume_chat` now gets the same 403 through a shared helper, with a test.
  - MINOR, valid: the `install_packages` 403 is now an explicit deviation, with the criterion amended.
- **Round 3 (diff-scoped):** the validator returned PASS (0 BLOCKING, 2 MINOR). My judgement: PASS; the resume 403 is confirmed. MINOR, fixed: the Step 3 Files wording names both callers; the criterion's 2xx clause is scoped to the routes.

## Implementation notes
### Autopilot run (2026-11-09)
- Mode: automatic (batch-autopilot item 8/13)
- Branch: feature/multi-user-admin-only-config  PR base: feature/multi-user-scope-files-rag-code (stacked on MYAI-37's PR #90; chain #84 > #87 > #88 > #89 > #90)  Starting commit: f94baa4ac283d70c7e7356c5491b358ecf97ff02
- Dirty before start: none
- Work files: backend/auth/context.py, backend/tools/{router,spec,__init__}.py, backend/tools/catalog/{git,code}.py, backend/logging/router.py, backend/models/__init__.py, backend/chat/{router,handler,prompt_builder,tool_handler}.py, app.py, docs, tests
- Counters: fix 0/10, review 1/5, re-verify 0
- Last completed stage: 5 review (clean)  Next: done (shipped)
- Hard blocker: none
- WIP commit: none

### Autopilot decisions (2026-11-09)
- Plan already validated (3 rounds); stage 1 skipped.
- Stacked on the MYAI-37 branch (batch chain stacking so MYAI-42 has one base).
- Deviation: `ToolHandler.owner_is_admin` is a property that reads `db.get_user(self.user_id)` when used (not in `__init__`), like the lazy `user_id` from MYAI-36; same behaviour (missing owner or unknown user: denied).
- Deviation: the shared test fixtures gain `admin_a` (user_a's id with the admin role) in backend/conftest.py; the tools, logs and models route tests log in as it, and the new 403 cases use `user_b`.
- Note: `git_executor.py` and `code_executor.py` (named in the ticket's file list) needed no change: `execute_git` and `install_packages` are refused at dispatch through `ToolSpec.admin_only`.

### Baseline (2026-11-09)
`pytest backend tests` on the base (MYAI-37 branch): 10 failed (async-plugin: test_cache_system x2, test_research_utils x2, test_code_executor x6), 1487 passed.

### Implementation progress
- [x] Step 1: Admin helper - `forbid_non_admin()` in backend/auth/context.py (`admin_required` now uses it)
- [x] Step 2: Settings, logs, models, legacy - `admin_required` on the six `/config/*` routes and `/legacy/*`; `logs_bp.before_request`; model non-GET admin only; `Cookie`/`Authorization`/`Cf-Access-Jwt-Assertion` never forwarded
- [x] Step 3: Admin-only tools - `ToolSpec.admin_only` (git_agent, execute_git, install_packages); registry filters by `active_modes["admin"]`; `PromptContext.is_admin`; `ChatHandler` computes it from the owner and drops `gitMode` for non-admins (`chat_git_mode_denied`); `ToolHandler` dispatch guard (`tool_admin_only_denied`); `gitMode` 403 on completions and resume
- [x] Step 4: Docs - security.md (Admin-only section), docs/tools.md, tools/logging/models READMEs
- Branch: feature/multi-user-admin-only-config

### Smoke test (2026-11-09)
`pytest backend tests`: 10 failed (baseline), 1546 passed. `ruff check .`: clean.

PR: https://github.com/archit342000/My-AI/pull/91, branch feature/multi-user-admin-only-config, base feature/multi-user-scope-files-rag-code

## Verification

### Verification plan and results (2026-11-09)
Live: the real app on a throwaway DATA_DIR (/tmp, removed) with the MYAI-33 harness (signed test JWTs), `FRONTEND=legacy`, users alice (admin) and bob (user). Script `MYAI-38-evidence/scripts/drive.py`, results `live-results.json`.
| ID | Scenario | Status |
|----|----------|--------|
| V1 | bob gets 403 on 19 admin-only requests: system/agents/browser settings (GET and write), every logs route including `/db/tables` and `/db/table/<name>`, `/legacy/`, `/legacy/index.html`, `/legacy/logs.html`, model load, unload and DELETE | PASS |
| V2 | alice (admin) is never refused; settings, db tables and `/legacy/` answer 200 | PASS |
| V3 | a user can still reach the model list route (not 403; the proxy is not running here) | PASS |
| V4 | bob enabling git mode on completions or resume: 403 and no chat created | PASS |
| V5 | bob's own existing chat: resume with git mode is 403 (not 404) | PASS |
| V6 | alice's resume with git mode is not 403 | PASS |
| V7 | regression: `pytest backend tests` baseline failures only; ruff clean | PASS |
Verdict: verified (6 live checks + the suite). Covered by unit tests rather than live: no side effect after a 403 (config globals, agent profiles, `set_setting` and the upstream call are asserted untouched), the dispatch guard (a model naming `git_agent`, `execute_git` or `install_packages` for a user, an unknown user or a missing owner is refused without resolving the implementation), registry/prompt filtering, header stripping.

## Review history

### Round 1 - 2026-11-09
Verdict: Approve with comments (no BLOCKER/MAJOR). Scope: working tree vs HEAD, 30 files / ~430 lines, 1 Haiku reviewer.
- R1-1 [MINOR] prompts/directives/run_code.txt - the `run_code` directive (shown to every chat) told the model to use `install_packages`, a tool now withheld from non-admins - Static - Fixed: that section moved to `directives/install_packages.txt` (loaded only through the admin-only spec); tests assert a user's prompt never mentions it
- R1-2 [MINOR] app.py - with `FRONTEND=legacy` the legacy files are also served at `/`, `/index.html`, `/logs`, `/logs.html` and the static catch-all to every user - Static - Rejected as a defect, documented: only `/legacy/*` is in the Plan; in legacy mode these files are the main UI by deployment choice and every data route behind them is checked; security.md says so
- R1-3 [MINOR] tests - the directive tests were guarded by `if directive:`, so the install_packages branch asserted nothing - Static - Fixed (directive files must exist and be non-empty)
- R1-4 [NIT] test_tool_handler.py - a conditional `assert_not_called` - Static - Fixed (removed; `resolve.assert_not_called()` covers it)
- R1-5 [NIT] test_spec.py - `spec is None or ...` passed for missing tools - Static - Fixed
- R1-6 [NIT] auth/README.md - `forbid_non_admin` missing - Static - Fixed
Resolution: 5 Fixed, 1 Rejected/documented. `pytest backend tests` 10 failed (baseline), 1546 passed; ruff clean. Runtime: prompt template only (no route or scenario changed, so no re-verify). Review loop clean (1/5).

## Log
- 2026-11-09: created (split from MYAI-32 Step 6)
- 2026-11-09: linked split_from MYAI-32 (Step 6)
- 2026-11-09: linked blocked_by MYAI-33
- 2026-11-09: linked blocked_by MYAI-35
- 2026-11-09: linked blocks MYAI-39
- 2026-11-09: linked blocks MYAI-41
- 2026-11-09: linked blocks MYAI-42
- 2026-11-09: linked conflicts_with MYAI-36 (shared files per MYAI-32 Steps intro)
- 2026-11-09: linked conflicts_with MYAI-37 (shared files per MYAI-32 Steps intro)
- 2026-11-09: acceptance criterion amended during planning: package installs have no HTTP route, so they're refused on the tool path instead of 403
- 2026-11-09: plan validated, 3 rounds
- 2026-11-09: note from MYAI-37 review: `/api/logs/db/tables` and `/api/logs/db/table/<table_name>` currently return raw rows of every user (chats, messages, files, file_systems, sub_agent_messages...) to any authenticated user; make sure the logs `before_request` gate covers them and add a two-user test. docs/standards/security.md already lists the logs viewer as not yet covered.
- 2026-11-09: autopilot started (batch)
- 2026-11-09: implemented, smoke tests pass (baseline failures only)
- 2026-11-09: verified 6 live checks PASS
- 2026-11-09: review round 1: Approve with comments; resolved
- 2026-11-09: PR opened: https://github.com/archit342000/My-AI/pull/91 (stacked on MYAI-37's PR). batch-autopilot: shipped
- 2026-11-10: closed (merged into develop via the PR recorded in Implementation notes; deployed to myai.architanand.dev)
