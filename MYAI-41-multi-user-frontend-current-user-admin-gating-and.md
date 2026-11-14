---
id: MYAI-41
title: "Multi-user: frontend current user, admin gating and per-user local settings"
status: done
created: 2026-11-09
updated: 2026-11-10
links:
  blocks: [MYAI-42]
  blocked_by: [MYAI-33, MYAI-38]
  split_from: [MYAI-32]
---

## Description
Split from MYAI-32 (Step 9: Frontend). Part of making My-AI multi-user behind Cloudflare Access. Implement after MYAI-1 to MYAI-31 have merged.

Read the MYAI-32 Plan first: the Audit (single-user assumptions with file references), the Approach, the Decisions and the Reviewer brief are binding for this ticket. Step scope from MYAI-32:

- **Depends on:** MYAI-33, MYAI-38
- **Files:** `frontend/src/api/me.ts` (create); `frontend/src/state/settings-store.ts`, `frontend/src/lib/workspace-prefs.ts` (modify: user-namespaced keys, keeping the old keys for the admin on first load); the app shell and sidebar (modify: show the current user); the settings dialogs, the model load and unload controls, the logs route and the portal entry (modify: hidden for `role !== 'admin'`); `frontend/src/api/client.ts` (modify: 401 shows a reload prompt). Tests next to each file. `frontend/README.md`, `docs/frontend.md` (modify).
- **Change:** as in Approach.
- **Verification:** `npm run typecheck`, `lint`, `test`, `build`; component tests for the admin and user roles; a Playwright smoke test with the `static` provider as admin and as user.

## Acceptance criteria
- [ ] The UI shows the current user from `/api/me`
- [ ] Admin controls (the runner settings and admin links in the System dialog, agents, browser, model load/unload, logs, portal) are hidden for `role !== 'admin'`
- [ ] `localStorage` chat settings are per user: non-admin users get keys namespaced by user id; the admin keeps the existing key names and settings (no key renamed)
- [ ] 401 shows a reload prompt and 403 shows a toast
- [ ] `npm run typecheck`, `lint`, `test` and `build` pass

## Plan
**Date:** 2026-11-09  **Status:** Validated

### Objective
Make the React UI user-aware.
- It loads the current user from `GET /api/me` before rendering.
- It shows who is signed in.
- It hides admin-only controls from users: runner settings, agent config, model manager, browser stealth, logs, browser portal and the Git Agent toggle.
- It keeps each user's browser-local chat settings apart: non-admin users get keys namespaced by their user id, and the admin keeps the existing key names.
- It handles 401 with a "session expired, reload" banner and 403 with a toast.

### Context
- **Requirement:** this ticket's Description and Acceptance criteria. MYAI-32 Plan: Audit item 15, Step 9.
- **Assumes merged:**
  - MYAI-33: `GET /api/me` returns `{id, email, role}`; 401 and 403 from the auth hook.
  - MYAI-38: the backend returns 403 for the admin surfaces and git mode.
  - MYAI-39: the portal is admin-only.
  - MYAI-40: the 429 toast in `consume`.
  - MYAI-6, MYAI-7, MYAI-8, MYAI-13, MYAI-20 and MYAI-21: the frontend files they change (MessageList, send-turn, Composer, WorkspacePage, chat-model).
- **Current code** (`frontend/src/`):
  - `App.tsx` creates the `QueryClient` and renders routes from `app/routes.tsx` (with `/logs` mapped to `LogsPage`).
  - **Sidebar footer** (`app/Sidebar.tsx:72-88`): Settings (`chat-settings`), System (`system-settings`), and a Logs link.
  - **`SystemSettingsModal`** (`features/settings/SystemSettingsModal.tsx`):
    - Always fetches `settingsApi.getSystem` (admin-only after MYAI-38).
    - Shows runner settings, theme, vision and reset-preferences controls.
    - Links (lines 55-62) to `preferences`, `skills`, `personas` (per user), and `agent-config`, `models`, `stealth` (admin).
  - **`ToolsMenu`** (`features/tools/ToolsMenu.tsx`): the mode toggles, including `gitMode` (line 11), plus "Open browser portal" (48) and "Code execution history" (49).
  - **Persistence:**
    - `state/settings-store.ts` reads `localStorage` keys (`KEYS`: model, modelName, sampling, research, vision, persona) when the store is created.
    - `lib/workspace-prefs.ts` reads `chatWorkspaces` on each call.
    - `state/ui-store.ts` stores the theme (`my_ai_theme_mode`), a device preference rather than user data.
  - **`api/client.ts`:** `apiRequest` throws `ApiError(status, body, message)` on non-OK responses; `components/ui/toast-store.ts` provides toasts.
  - **Existing tests:** `api/client.test.ts`, `components/ui/*.test.tsx`, `lib/*.test.ts`, `features/chat/stream-reducer.test.ts`. Sibling tickets add more (for example `send-turn.test.ts`).
- **Rules:**
  - `docs/standards/frontend.md`: components-only `.tsx` exports (see MYAI-15), typed API modules, tests next to files.
  - `docs/frontend.md`: commands and layout.
  - `docs/standards/testing.md`.

### Approach
- **Current user:**
  - `api/me.ts` (new): a `CurrentUser` type and `meApi.get()`.
  - `state/user-store.ts` (new): a Zustand store holding `user: CurrentUser | null` and `sessionExpired: boolean`.
  - `app/UserGate.tsx` (new) wraps the routes in `App.tsx`:
    - It fetches `/api/me` with react-query (`staleTime: Infinity`), with a per-query `retry` that returns false for an `ApiError` with status 401, overriding `App.tsx`'s global `retry: 1`.
    - While loading it shows a minimal loading state. On success it sets the store, then renders the children (Step 2 adds the storage init and `hydrate()` call before rendering).
    - On a 401 it shows the same "Your session has expired." message with a Reload button that `RootLayout` uses, since `RootLayout` isn't mounted yet. On any other error it shows "Couldn't load your account. Reload."
  - Every user-dependent read therefore happens after the user is known.
  - `isAdmin` is derived as `user?.role === 'admin'`.
- **Namespaced storage:** `lib/user-storage.ts` (new).
  - `docs/standards/frontend.md` and `docs/frontend.md` say to keep existing `localStorage` key names and formats, so existing browsers keep their settings. To keep that rule, the admin, who owns all existing data, keeps the existing key names unchanged (`KEYS.*`, `chatWorkspaces`).
  - Only non-admin users get new, namespaced keys: `nsKey(base)` returns `base` for the admin and `` `${base}:${userId}` `` for any other user. No existing key is renamed or moved, and the formats don't change. Step 5 adds one sentence to both docs recording this.
  - `initUserStorage(user)` records the id and role. `nsKey` throws if called before it.
  - `settings-store.ts` creates its state from defaults only (no `localStorage` read at import), and gets a `hydrate()` action that reads all fields through `nsKey`; `hydrate()` is the only read path. Its setters write through `nsKey`.
  - `workspace-prefs.ts` uses `nsKey(WORKSPACE_PREFS_KEY)`.
  - The theme key stays global (a device preference).
- **Admin gating in the UI:**
  - Sidebar: the "System" button stays (theme, vision and per-user links live there). The Logs link renders only for admins. A new footer item shows the user's email (the `title` attribute has the role).
  - `SystemSettingsModal`:
    - `getSystem` runs only when `open && isAdmin`.
    - The runner-settings section renders only for admins.
    - The `agent-config`, `models` and `stealth` links render only for admins. The `preferences`, `skills` and `personas` links and the theme, vision and reset controls stay for everyone.
  - `ToolsMenu`: the `gitMode` toggle and "Open browser portal" render only for admins. A non-admin's stored `modes.gitMode` is forced false in `hydrate()`, so it's never sent.
  - The `LogsPage` route renders "Not available" for non-admins, without calling the logs API.
  - `DialogHost` renders `ModelsDialog`, `StealthDialog`, `AgentConfigDialog` and `PortalDialog` only for admins, so a stray `show('models')` can't open them (the load and unload buttons live in `ModelsDialog`).
  - Coverage note (the acceptance criterion is amended to match): the ticket's "system settings" means the admin-only parts of the System dialog (runner settings and the admin links), not the whole dialog, which also holds per-user controls.
- **Errors:**
  - `apiRequest` calls `useUserStore.getState().setSessionExpired(true)` on a 401. `RootLayout` shows a fixed banner, "Your session has expired.", with a Reload button (`location.reload()`).
  - On a 403 it shows the toast "You don't have access to that." once per response and still throws, so callers keep their flow.
  - The SSE path in `api/completions.ts` uses `apiRequest` for the initial response, so it's covered.
- **Rejected:**
  - Clearing `localStorage` on user change: it would lose the other user's settings in a shared browser.
  - Server-side storage of chat settings: rejected in MYAI-32.
  - Hiding the whole System dialog from users: it holds per-user controls too.

### Out of scope
- A user-management UI.
- Legacy UI changes (admin-only, Decision 4).
- Backend changes (MYAI-33 to MYAI-40).
- Handling Cloudflare Access's own edge redirect on an expired session (outside the app; see Risks).

### Steps
#### Step 1: User API, store and gate
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/api/me.ts` (create), `frontend/src/api/me.test.ts` (create); `frontend/src/state/user-store.ts` (create), `frontend/src/state/user-store.test.ts` (create); `frontend/src/app/UserGate.tsx` (create), `frontend/src/app/UserGate.test.tsx` (create); `frontend/src/app/App.tsx` (modify).
- **Change:** as in Approach.
- **Verification:** with mocked `fetch`, `UserGate` shows loading, then its children with the store set; it shows the generic error state on a 500 and the session-expired message on a 401, with only one `/api/me` call for the 401 (no retry); and children aren't rendered before `/api/me` resolves.

#### Step 2: Namespaced storage
- **Status:** todo
- **Depends on:** 1
- **Files:** `frontend/src/lib/user-storage.ts` (create), `frontend/src/lib/user-storage.test.ts` (create); `frontend/src/app/UserGate.tsx` (modify: call `initUserStorage(user)` and `useSettingsStore.getState().hydrate()` before rendering the children), `frontend/src/app/UserGate.test.tsx` (modify); `frontend/src/state/settings-store.ts` (modify: `hydrate`, setters through `nsKey`); `frontend/src/lib/workspace-prefs.ts` (modify); tests `frontend/src/state/settings-store.test.ts` and `frontend/src/lib/workspace-prefs.test.ts` (create).
- **Change:** as in Approach.
- **Verification:**
  - Two non-admin users' settings don't overlap, and neither touches the admin's keys.
  - The admin reads and writes the existing key names, so existing values load unchanged.
  - `nsKey` before init throws.
  - `hydrate` forces `gitMode` false for a user.

#### Step 3: Admin gating
- **Status:** todo
- **Depends on:** 1
- **Files:** `frontend/src/app/Sidebar.tsx`, `frontend/src/features/settings/SystemSettingsModal.tsx`, `frontend/src/features/settings/DialogHost.tsx`, `frontend/src/features/tools/ToolsMenu.tsx`, `frontend/src/features/logs/LogsPage.tsx` (modify). Tests set the role with `useUserStore.setState({ user: {...} })`. MYAI-28's `SystemSettingsModal.test.tsx` sets an admin user in its setup, so its runner assertions still hold, and gains user-role cases. Component tests next to each (`Sidebar.test.tsx`, `SystemSettingsModal.test.tsx` (MYAI-28 creates it), `ToolsMenu.test.tsx`, `LogsPage.test.tsx`), created by this step where they don't exist yet.
- **Change:** as in Approach.
- **Verification:** for role `user`, the Logs link, runner settings, admin links, Git toggle and portal button are absent, `getSystem` isn't called, `LogsPage` doesn't fetch, and `DialogHost` doesn't render the four admin dialogs. For role `admin`, all are present. The email is shown for both.

#### Step 4: 401 and 403 handling
- **Status:** todo
- **Depends on:** 1
- **Files:** `frontend/src/api/client.ts`, `frontend/src/api/client.test.ts` (modify); `frontend/src/app/RootLayout.tsx` (modify: banner), `frontend/src/app/RootLayout.test.tsx` (create).
- **Change:** as in Approach.
- **Verification:** a 401 sets `sessionExpired` and the banner renders with a Reload button; a 403 shows the toast once and still throws `ApiError`.

#### Step 5: Docs, full checks and smoke test
- **Status:** todo
- **Depends on:** 2, 3, 4
- **Files:** `frontend/README.md`, `docs/frontend.md` (modify: `UserGate`, namespaced storage, admin gating, 401 and 403 behaviour); `docs/standards/frontend.md` (modify: one sentence under persisted state saying non-admin users' keys get a `:<userId>` suffix while existing names stay for the admin); `frontend/e2e/user-roles.spec.ts` (create: the smoke test below, per the `e2e/` rule in `docs/standards/frontend.md`).
- **Change:** docs match the code.
- **Verification:**
  - In `frontend/`: `npm run typecheck`, `npm run lint`, `npm run test`, `npm run build`.
  - `frontend/e2e/user-roles.spec.ts` (`npm run e2e`) against the app with `AUTH_PROVIDER=static` as the admin, in one browser context:
    - The email shows, and admin controls appear.
    - The spec then switches identity client-side with `page.route('/api/me', ...)`, which the storage isolation depends on: it returns user A (role `user`), picks a model and persona, then reloads with user B. A's choices are absent for B, and admin controls are hidden for both.
    - Restoring the real `/api/me` shows the admin's original settings.
  - Screenshots go in `~/.claude/tickets/My-AI/MYAI-41-evidence/`.

### Tests
Covered per step (Vitest and Testing Library), plus the smoke test.

### Risks and open questions
- **An expired Cloudflare Access session** may get an edge redirect to the login page rather than an app 401. `fetch` then fails with a network error and shows no banner. That's outside the app; MYAI-42's live check records the observed behaviour, and a follow-up can map network errors to the banner if needed.
- **Users share one browser device's theme,** by design (device preference).

### Success criteria
- [ ] The UI shows the current user from `/api/me`.
- [ ] Admin controls (runner settings, agent config, models, stealth, logs, portal, Git toggle) are hidden for users.
- [ ] `localStorage` chat settings are per user; the admin keeps the existing key names and settings, and no key is renamed.
- [ ] A 401 shows a reload banner; a 403 shows a toast.
- [ ] `npm run typecheck`, `lint`, `test` and `build` pass.

### Reviewer brief
- **Objective:** a user-aware React UI. It loads `/api/me` before rendering, shows the signed-in user, hides admin-only controls from users, keeps per-user chat settings apart in `localStorage`, shows a reload banner on 401 and a toast on 403.
- **Key decisions:**
  - `UserGate` wraps the routes: a react-query `/api/me` call with no retry on 401 (its own session-expired message), then `initUserStorage` and `settings-store.hydrate()` before rendering.
  - `nsKey` keeps the existing key names for the admin and adds `:<userId>` for other users, so no key is renamed (the standard's rule is kept). The settings store starts from defaults and only `hydrate()` reads. The theme stays global.
  - Hidden for users: the Logs link and route content, the runner section and admin links in the System dialog, the four admin dialogs in `DialogHost`, the Git Agent toggle (stored `gitMode` forced false) and the portal button.
  - `apiRequest`: 401 sets `sessionExpired` (banner in `RootLayout`); 403 shows a toast and still throws.
  - New `e2e/user-roles.spec.ts` switches identity with `page.route` on `/api/me`.
- **Out of scope:** user-management UI, legacy UI, backend, Cloudflare edge redirects.
- **Success criteria:** as listed in the Plan.

The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- **Round 1:** the validator returned FAIL (3 BLOCKING, 6 MINOR). My judgement: FAIL.
  - All three BLOCKING issues were valid and fixed:
    - Step ordering: the storage init moved to Step 2, which now owns the `UserGate` change.
    - The `e2e/` spec rule: `user-roles.spec.ts` added.
    - The documented "don't rename `localStorage` keys" rule: resolved by keeping the admin's existing keys unchanged and namespacing only other users. No key is renamed, and the docs sentence is added.
  - MINOR, fixed: the "system settings" interpretation; `DialogHost` gating for `ModelsDialog` and the others; the 401 state on the first `/api/me`; a per-query retry; role seeding in tests. The Context note needed no change.
- **Round 2 (diff-scoped):** the validator returned PASS (0 BLOCKING, 3 MINOR). My judgement: PASS. MINOR, fixed: the store starts from defaults; the e2e isolation check uses one context with `page.route`; the acceptance criterion is amended for "system settings".

## Implementation notes
### Autopilot run (2026-11-09)
batch-autopilot item 11/13; branch feature/multi-user-frontend-gating, base feature/multi-user-rate-limits (stacked on the MYAI-40 PR); no pre-existing dirty files.

### Baseline (2026-11-09)
frontend (on the base branch): typecheck, lint clean; vitest 316 passed. backend+tests: 10 failed (async-plugin baseline).

### Implementation progress
- [x] Step 1: User API, store and gate - api/me.ts, state/user-store.ts, app/UserGate.tsx, app/App.tsx (+tests)
- [x] Step 2: Namespaced storage - lib/user-storage.ts, state/settings-store.ts (defaults only, `hydrate()`, setters through `nsKey`, a user cannot set gitMode), lib/workspace-prefs.ts, src/test/setup.ts (every test starts signed in as the admin), src/test/roles.ts (+tests)
- [x] Step 3: Admin gating - Sidebar (email, Logs link), SystemSettingsModal, DialogHost, ToolsMenu, LogsPage (+tests; new css classes `.sidebar-user`, `.session-banner` in components.css)
- [x] Step 4: 401 and 403 - api/client.ts, app/RootLayout.tsx (+tests)
- [x] Step 5: Docs and checks - docs/frontend.md, docs/standards/frontend.md, frontend/README.md, e2e/user-roles.spec.ts
- Branch: feature/multi-user-frontend-gating (base feature/multi-user-rate-limits). Deviation: the plan puts `App.tsx` at `src/App.tsx`; it is `src/app/App.tsx`.
PR: https://github.com/archit342000/My-AI/pull/94, branch feature/multi-user-frontend-gating, base feature/multi-user-rate-limits

### Smoke test (2026-11-09)
frontend: typecheck, lint clean; vitest 354 passed (59 files); `npm run build` passes. backend+tests: 10 failed (identical baseline), 1633 passed. ruff clean.

## Verification

### Verification plan and results (2026-11-09)
Real built app (FRONTEND=react) on a throwaway DATA_DIR, `AUTH_PROVIDER=static`, headless Chrome, Playwright `e2e/user-roles.spec.ts` (identity switched with `page.route` on `/api/me`): V1 admin sees the signed-in email, Logs link, runner settings and model manager: PASS. V2 a user sees no Logs link, no runner section or admin links, and `/logs` shows "Not available": PASS. V3 user A turns Vision on (`my_ai_vision_enabled:user-a` set), user B starts with it off and writes nothing, the admin keeps the original key name and its own state: PASS (3 passed). Screenshots: MYAI-41-evidence/system-dialog-admin.png, system-dialog-user.png (the user's dialog has no code-runner section and only the per-user links).
Not run live: a real 401 from an expired Cloudflare Access session (an edge redirect, out of scope per the plan; covered by unit tests of `apiRequest`, `UserGate` and `RootLayout`).

## Review history
### Round 1 - 2026-11-09
Verdict: Approve with comments (one Haiku reviewer). Resolution: fixed 6, rejected 2. Checks: frontend typecheck, lint clean, vitest 355 passed, build ok; e2e spec 3 passed (before the fixes; the fixes are covered by unit tests).
- R1-1 [MINOR] nsKey inside the localStorage try/catch swallowed the "not initialised" error - Fixed (nsKey outside the try in settings-store and workspace-prefs).
- R1-2 [MINOR] `['me']` key inline - Fixed (`meKeys` in api/me.ts).
- R1-3 [MINOR] a 403 query was retried and toasted twice - Fixed: `shouldRetryQuery` (no retry for 401/403) used by the app default and UserGate; test.
- R1-4 [MINOR] formatting - Fixed what this change introduced (re-indented the admin-only Code runner block, wrapped the LogsPage ternary, prettier on new files); Sidebar and SystemSettingsModal were not prettier-clean at HEAD, so no whole-file reformat.
- R1-5 [NIT] module-level user assumes one user per page load - Fixed (stated in the user-storage header).
- R1-6 [NIT] api layer imports the toast and user stores - Rejected: the plan puts the 401/403 handling in `apiRequest`.
- R1-7 [NIT] collapsed rail shows no identity - Rejected: the plan shows the email in the sidebar footer; the rail is icons only.
- R1-8 [NIT] imports below code in test setup - Fixed.

## Log
- 2026-11-09: created (split from MYAI-32 Step 9)
- 2026-11-09: linked split_from MYAI-32 (Step 9)
- 2026-11-09: linked blocked_by MYAI-33
- 2026-11-09: linked blocked_by MYAI-38
- 2026-11-09: linked blocks MYAI-42
- 2026-11-09: acceptance criteria amended during planning: "system settings" means the System dialog's admin-only parts; namespacing keeps the admin's existing key names (docs rule on not renaming keys)
- 2026-11-09: plan validated, 2 rounds
- 2026-11-09 batch-autopilot: shipped https://github.com/archit342000/My-AI/pull/94, base feature/multi-user-rate-limits
- 2026-11-10: closed (merged into develop via the PR recorded in Implementation notes; deployed to myai.architanand.dev)
