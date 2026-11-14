---
id: MYAI-70
title: "Settings parity: clear all chats, git settings, new-chat defaults, search in manage dialogs"
status: done
epic: MYAI-53
created: 2026-11-10
updated: 2026-11-10
links:
  blocked_by: [MYAI-64, MYAI-67, MYAI-73]
  split_into: [MYAI-71, MYAI-72]
---

## Description
The React System Settings and manage dialogs lack several legacy features: clear all chats, the git agent settings (GitHub token and allowed commands), the new-chat defaults (thinking profile, user preferences, max tokens, thinking budget), and search, filter and sort in the memory and skills lists. Legacy "Reset app" cleared the saved connection settings (which no longer exist under Cloudflare Access) together with the saved model and theme, then reloaded; it is recorded as dropped.

Findings (MYAI-52, Verification): A-62 (chat defaults), A-80 (except the speed-test chart). Research-mode UI and the model-switch overlay moved to MYAI-71, the speed test to MYAI-72. Evidence and the live test rig are in `~/.claude/tickets/My-AI/MYAI-52-evidence/`.

## Acceptance criteria
- [x] System Settings can delete all chats after a confirmation, and the app returns to an empty home page
- [x] An admin can save a GitHub token (shown only as configured or not) and choose the allowed git commands
- [x] New-chat defaults (thinking profile, user preferences, max tokens, thinking budget) can be set in System Settings and are used by the next new chat
- [x] The memory list can be searched, filtered by tag and sorted; the skills list can be searched
- [x] "Reset app" is recorded as dropped in `docs/frontend.md`; no legacy-only settings feature remains undocumented there

## Plan
**Date:** 2026-11-10  **Status:** Validated

### Objective
Add the settings features the legacy UI had and the React UI lacks: clear all chats, git agent settings, new-chat defaults, and search, filter and sort in the memory and skills lists; and record "Reset app" as dropped.

### Context
- **Requirement:** this ticket's Description and Acceptance criteria (findings A-62 and A-80 in MYAI-52, without the speed test and the research UI).
- **Assumes merged:** MYAI-64 (the settings store has a persisted `defaults` snapshot next to the active values, `resetToDefaults()`, and the chat-scoped flag) and MYAI-67 (System Settings built on `Field`, `Input`, `Button`, class-based `Section`).
- **Rules:** `docs/standards/frontend.md` (typed API calls in `src/api/`, `ConfirmDialog` for destructive actions, pure logic in `src/lib/` with tests, UI primitives, admin gating is convenience only), `docs/standards/security.md` (never keep secrets in frontend state or storage: the token is sent once and never read back), `docs/frontend.md` (admin gating list, Known gaps).
- **Server API (exists):**
  - `DELETE /api/chats` deletes the caller's chats and their data (`backend/chat/router.py` `clear_all_chats`); `chatsApi.bulkDelete` already wraps it and nothing calls it.
  - `GET /api/tools/config/settings` (admin) returns `github_pat_configured` (never the token), `git_allowed_commands`, `git_known_commands` and the code-runner values; `POST` accepts `github_pat` (the placeholder `__REDACTED__` is ignored) and `git_allowed_commands` (`backend/tools/router.py` `get_system_settings`, `update_system_settings`).
- **Legacy reference:** `static/js/settings-manager.js`: `loadGitSettings`, `saveGitPat`, `saveAllowedCommands` (one checkbox per known command, saved on change); `chatDefaults` (`thinkingProfile`, `userPreferences`, `maxTokens`, `thinkingBudgetTokens`) edited under "New Chat Defaults"; `resetAppInteractive` removes `my_ai_server_link`, `my_ai_api_token_secure`, the model keys and the theme key and reloads. `static/js/preferences-manager.js`: text search over content, a tag filter and newest/oldest sort. `static/js/skills-manager.js` `renderSkills`: text search over name and description.
- **Current code (`frontend/src/`):** `features/settings/SystemSettingsModal.tsx` (Appearance, Capabilities, Code runner, Manage, Danger zone with "Reset preferences"); `features/settings/CrudList.tsx` `CrudDialog` renders every item; `features/settings/PreferencesDialog.tsx`, `SkillsDialog.tsx`; `api/settings.ts` `settingsApi.getSystem`, `saveCodeRunner`; `lib/labels.ts` `memoryTagLabel`.

### Approach
- **Clear all chats.** A danger-zone button "Delete all chats" with a `ConfirmDialog` that names the consequence; on success it invalidates the chat and workspace lists, discards a temporary chat with the existing `discardTemporaryChat(queryClient)` (`features/chat/temporary-chat.ts`), closes the dialog and navigates to `/`. It is available to every user (the endpoint deletes only the caller's chats).
- **Git settings (admin only).** A "Git agent" section: a password-type field for the GitHub token with the status "Configured" or "Not configured" from `github_pat_configured`, saved with its own button and cleared from component state after the request; the allowed commands as a checkbox list from `git_known_commands`, saved on change with the full list. New typed calls `settingsApi.saveGitToken` and `settingsApi.saveGitAllowedCommands`.
- **New-chat defaults.** A "New chat defaults" section editing the store's `defaults` through a new `setDefaults(patch)` action (thinking profile, user preferences, max tokens, thinking budget), which derives `enable_thinking` from the profile as MYAI-64 does, persists them through the store's persisted `defaults` snapshot that MYAI-64 adds (after MYAI-64 the existing keys hold the defaults, not a chat's values: max tokens, thinking budget and profile in `my_ai_sampling_params`, `userPreferences` in `my_ai_chat_defaults`; no new key), and does not touch the active values of an open chat.
- **Search, filter, sort.** `CrudDialog` gains an optional `toolbar` slot and takes already-filtered `items`. Pure helpers in `lib/list-filter.ts` (new): `filterPreferences(items, { query, tag, sort })` and `filterSkills(items, query)`. The memory dialog gets a search `Input`, a tag `Select` (tags present in the list, labelled with `memoryTagLabel`) and a sort `Select` (Newest, Oldest); the skills dialog gets a search `Input`. An empty result shows "No matches".
- **Reset app.** Not ported: its purpose was to clear the pre-Access connection keys; the model and theme it also cleared can be changed in the dialogs. `docs/frontend.md` records it as dropped, and its Known gaps names the two legacy settings areas handled elsewhere (speed test: MYAI-72; research configuration: MYAI-71) until those land.
- **Rejected:** storing the token in the settings query cache (the server never returns it and the UI must not keep it); server-side search (the lists are small and already loaded).

- **Note 2026-11-10 (after validation):** before the delete-all request, the handler awaits `stopIfStreaming(chatId)` from `features/chat/send-turn.ts` (added by MYAI-73) for the chat in flight, if any, so no turn keeps running for a deleted chat (MYAI-52 A-91). One unit assertion: the stop is posted before the delete.

### Out of scope
- Research depth, research plan UI, model-switch overlay: MYAI-71. Speed test: MYAI-72.
- Backend changes, including persona flags (see MYAI-67).

### Steps
#### Step 1: List filtering logic
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/lib/list-filter.ts` (create), `frontend/src/lib/list-filter.test.ts` (create)
- **Change:** as in Approach ("Search, filter, sort": the helpers).
- **Verification:** unit tests: query matches case-insensitively on content (and on name or description for skills); tag filter keeps one tag; Newest and Oldest order by `timestamp`; empty query and no tag return everything.

#### Step 2: Search in the manage dialogs
- **Status:** todo
- **Depends on:** 1
- **Files:** `frontend/src/features/settings/CrudList.tsx` (modify: `toolbar` slot, "No matches" state), `frontend/src/features/settings/CrudList.test.tsx` (modify), `frontend/src/features/settings/PreferencesDialog.tsx` and `SkillsDialog.tsx` (modify), `PreferencesDialog.test.tsx` and `SkillsDialog.test.tsx` (modify), `frontend/src/styles/components.css` (modify: "Manage lists" block for the toolbar)
- **Change:** as in Approach ("Search, filter, sort": the dialogs).
- **Verification:** component tests: typing in the memory search narrows the rows; the tag filter and the sort change the rows and their order; the skills search matches a description; a query with no result shows "No matches" and the Add button still works.

#### Step 3: API calls and store action
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/api/settings.ts` (modify: system settings type with the git fields, `saveGitToken`, `saveGitAllowedCommands`), `frontend/src/api/settings.test.ts` (create), `frontend/src/state/settings-store.ts` (modify: `setDefaults`), `frontend/src/state/settings-store.test.ts` (modify)
- **Change:** as in Approach ("Git settings": the calls; "New-chat defaults": the action).
- **Verification:** unit tests: each call posts the expected body to `/api/tools/config/settings`; `setDefaults` changes the stored defaults, leaves the active values alone while the store is chat-scoped, and a following `resetToDefaults()` yields the new values.

#### Step 4: System Settings sections
- **Status:** todo
- **Depends on:** 3
- **Files:** `frontend/src/features/settings/SystemSettingsModal.tsx` (modify), `frontend/src/features/settings/GitSettingsSection.tsx` (create), `frontend/src/features/settings/ChatDefaultsSection.tsx` (create), tests `SystemSettingsModal.test.tsx` (modify), `GitSettingsSection.test.tsx` and `ChatDefaultsSection.test.tsx` (create), `frontend/src/styles/components.css` (modify: "Settings sections" block)
- **Change:** as in Approach ("Clear all chats", "Git settings", "New-chat defaults"). The git section is rendered for an admin only.
- **Verification:** component tests: "Delete all chats" asks first, calls `chatsApi.bulkDelete`, invalidates the lists and navigates to `/`; a user (non-admin) sees no git section and no settings request is made for it; saving a token posts it once and the field is empty afterwards with the status "Configured"; toggling a command posts the full allowed list; changing a default calls `setDefaults`.

#### Step 5: End-to-end spec, docs and full checks
- **Status:** todo
- **Depends on:** 2, 4
- **Files:** `frontend/e2e/settings-parity.spec.ts` (create: with the settings and chat endpoints mocked as `e2e/user-roles.spec.ts` does, delete all chats and land on an empty home page; save a token and see "Configured"; set a default thinking profile and see it on a new chat's request; search the memory list), `docs/frontend.md` (modify: admin gating list gains the git section; Known gaps or a "Dropped from legacy" line for "Reset app"), `frontend/README.md` (modify only if affected)
- **Change:** docs match the code.
- **Verification:** from `frontend/`: `npm run typecheck`, `npm run lint`, `npm run test`, `npm run build`, and `npm run e2e` for the new spec (outside the merge gate; the spec mocks the settings and chat endpoints, so it needs only the frontend dev server that Playwright starts); from the repo root `pytest tests` and `scripts/check.sh --frontend-only`. Live (MYAI-52 rig): delete all chats empties the sidebar; a default thinking profile set in System Settings is the profile of the next new chat.

### Tests
- Unit: `lib/list-filter.test.ts`, `api/settings.test.ts`, `state/settings-store.test.ts`.
- Component: `CrudList.test.tsx`, `PreferencesDialog.test.tsx`, `SkillsDialog.test.tsx`, `SystemSettingsModal.test.tsx`, `GitSettingsSection.test.tsx`, `ChatDefaultsSection.test.tsx`.
- E2E: `e2e/settings-parity.spec.ts`.

### Risks and open questions
- **Dropping "Reset app"** needs the user's agreement (acceptance criterion 5 records it); if they want it, the nearest equivalent is "clear this browser's saved settings", which is a different feature.
- **"Delete all chats" for every user** follows the endpoint's scope; if it should be admin only, the button is gated like the other admin controls.
- **Shared files:** `SystemSettingsModal.tsx`, `CrudList.tsx` and the "Settings sections" CSS block are rebuilt by MYAI-67 first; `docs/frontend.md` (State section) and `frontend/README.md` are also edited by MYAI-64; land MYAI-64 first and edit on top.

### Success criteria
- [ ] Delete all chats works behind a confirmation and returns to an empty home page
- [ ] An admin can save a GitHub token (status only) and choose allowed git commands
- [ ] New-chat defaults can be set and are used by the next new chat
- [ ] Memory list search, tag filter and sort; skills search
- [ ] "Reset app" recorded as dropped in the docs
- [ ] Checks pass
### Reviewer brief
- **Objective:** add the settings features the legacy UI had and React lacks: clear all chats, git agent settings, new-chat defaults, and search, filter and sort in the memory and skills lists; record "Reset app" as dropped.
- **Decisions:** "Delete all chats" behind a `ConfirmDialog`, also discarding a temporary chat; an admin-only "Git agent" section where the GitHub token is write-only (status from `github_pat_configured`, never kept in the query cache); new-chat defaults edited through a `setDefaults(patch)` store action that writes MYAI-64's persisted `defaults` snapshot (existing storage keys, no new key) and leaves an open chat's active values alone; `CrudDialog` gets a `toolbar` slot and takes filtered items, with pure helpers in `lib/list-filter.ts` (client-side, no server search); "Reset app" not ported; an e2e spec with mocked endpoints.
- **Out of scope:** research depth, research plan UI and the model-switch overlay (MYAI-71); the speed test (MYAI-72); backend changes, including persona flags.
- **Success criteria:** delete all chats works behind a confirmation and returns to an empty home page; an admin can save a GitHub token (status only) and choose allowed git commands; new-chat defaults are used by the next new chat; memory search, tag filter and sort, skills search; "Reset app" recorded as dropped; checks pass.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- **Round 1 (Haiku): FAIL.** Judged FAIL. Valid BLOCKING: no Playwright spec although `docs/standards/frontend.md` requires one for a user-facing flow; `e2e/settings-parity.spec.ts` added in Step 5. Other valid issues fixed in the same revision.
- **Round 2 (Haiku): FAIL.** Judged PASS: the one BLOCKING issue is disproved. Claim: writing defaults to `my_ai_sampling_params` overwrites active sampling values, because `settings-store.ts` writes that key on every change today. That describes the code before MYAI-64; this ticket is blocked by MYAI-64, whose plan ("Defaults and active values", "What is persisted") makes the existing keys the persisted defaults and stops setters writing them while a chat is open. Wording made explicit. MINOR (valid, fixed inline): e2e verification said it needs the backend although the spec mocks it; shared files list now names `frontend/README.md`.

## Implementation notes

PR: https://github.com/archit342000/My-AI/pull/107, branch feature/settings-parity, base bugfix/stop-and-delete-while-running

## Verification

### Acceptance review (2026-11-10)
Criteria ticked on the live and e2e results recorded in the PR's Testing section (checks run on throwaway backends during the autopilot run; scripts in `MYAI-70-evidence/`).
All criteria covered.

### Verification plan (2026-11-10)
**Diff base:** c540877 (PR #106 tip). **Isolation:** throwaway DATA_DIR /tmp/myai70/data, stub model :5191, backend :5192 serving this branch's build; the GitHub token used is a fake string written only to the throwaway data directory; no containers touched. Scripts: `MYAI-70-evidence/scripts/` (up.sh, stub.py, serve.py, lib.mjs, v70.mjs). Teardown: kill listeners on 5191/5192, rm -rf /tmp/myai70.

| ID | Criterion | Scenario | Method | Files | Expected |
|----|-----------|----------|--------|-------|----------|
| V1 | delete all chats | create two chats, System Settings > Delete all chats > confirm | browser+API | SystemSettingsModal.tsx | cancel deletes nothing; confirm empties the sidebar and `GET /api/chats` is `[]`; URL `/`; home hero |
| V2 | git settings (admin) | save a fake token, reload; tick a command, reload | browser+API | GitSettingsSection.tsx, settings.ts | status "Configured" after save, token field empty, token not in the page; the ticked command still ticked after reload; `GET settings` never contains the token |
| V3 | new-chat defaults used by the next new chat | set the default thinking profile to None and user preferences off; New Chat; send; read the request body | browser+network | settings-store.ts, ChatDefaultsSection.tsx | body has `thinking_profile: none`, `enable_thinking: false`, `userPreferences: false`; survives a reload |
| V4 | memory search/filter/sort, skills search | seed 3 memories and 2 skills through the API | browser+API | PreferencesDialog.tsx, SkillsDialog.tsx | search narrows; tag filter keeps one tag; Oldest reverses; skills search by description; "No matches" |
| V5 | delete all stops a running turn | start a SLOW turn, Delete all chats | browser+network | SystemSettingsModal.tsx | stop request before the bulk delete; no stuck "generating" state |
| V6 | regression | vitest, typecheck, lint, build, e2e specs | CLI | all | pass |
| V7 | no console errors | collect console/page errors | browser | all | none |
"Reset app" dropped is a documentation change (docs/frontend.md), checked by reading.


## Review history
### Round 2 - 2026-11-10
Verdict: Request changes (3 MAJOR). Single Haiku reviewer.
- R2-1 [MAJOR] refused stop still let delete run - Fixed: list re-checked after stops; aborts with a message if any chat still runs; test.
- R2-2 [MAJOR] list failure masked by cached fallback - Fixed: error propagates, nothing deleted; test.
- R2-3 [MAJOR] silent catch after delete - Fixed: error toast says chats were deleted but lists not refreshed; test asserts it.
- R2-4 [MINOR] overlapping command saves - Fixed: boxes disabled while a save is in flight; test.
- R2-5 [NIT] PROFILES type - Fixed (ThinkingProfile[]).
Resolution: check.sh passes (612 tests); live V1/V5/V2 and e2e 4/4 re-run. Round 2 fixes were not re-reviewed by a third round.

### Round 1 - 2026-11-10
Verdict: Request changes (2 MAJOR). Scope: 13 files vs c540877, single Haiku reviewer.
- R1-1 [MAJOR] SystemSettingsModal.tsx delete-all stops only this tab's turn - Fixed: stops every chat the fresh list reports running (server flag) plus this tab's; test added.
- R1-2 [MAJOR] Prettier - Fixed for new files and files clean at base; Rejected for files already unformatted at base (PreferencesDialog, SkillsDialog, SystemSettingsModal, their tests, CrudList.test, settings-store.test, components.css): formatting them would bury the change in unrelated churn.
- R1-3 [MINOR] token kept in mutation variables - Fixed: plain async call, no mutation.
- R1-4 [MINOR] allowed-commands drift - Fixed: rollback to last confirmed list, no sync over a pending save; tests added.
- R1-5 [MINOR] status tone from text - Fixed ({tone,message} state).
- R1-6 [MINOR] missing tests - Fixed (token failure, max tokens, thinking budget, user prefs toggle, rollback).
- R1-7 [MINOR] loosened inline-style guard - Fixed (`:not(.ui-slider__input)`).
- R1-8 [MINOR] duplicate "Preference" tag options - Fixed: options and filter go by label; test added.
- R1-9 [MINOR] slider label mismatch - Fixed (same names as ChatSettingsModal).
- R1-10 [MINOR] cleanup failure after delete reported as failure - Fixed: split; test added.
- R1-11 [NIT] duplicate imports - Fixed. R1-13 [NIT] `?? 0` - Fixed. R1-12 [NIT] `as never` in a test fixture - Rejected (same pattern used across the suite).
Resolution: check.sh passes (609 tests); live V1-V5 and e2e 4/4 re-run after the fixes.


## Log
- 2026-11-10: created
- 2026-11-10: added to epic MYAI-53
- 2026-11-10: scope split during planning: research UI and model-switch overlay to MYAI-71, speed test to MYAI-72; title and criteria rewritten
- 2026-11-10: linked blocked_by MYAI-64 (defaults live in its settings store)
- 2026-11-10: linked blocked_by MYAI-67 (it rebuilds the dialogs this ticket extends)
- 2026-11-10: plan validated, 2 rounds
- 2026-11-10: linked blocked_by MYAI-73 (Delete all chats calls stopIfStreaming)

### Results (2026-11-10)
| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | 2 chats; Cancel keeps 2; Delete all -> 0 chats via API, sidebar empty, URL `/`, hero shown, modal closed |
| V2 | PASS | token saved: "Configured", field cleared, token not in page text, GET settings has no token (`github_pat_configured` true); command toggle persisted across reload |
| V3 | PASS | next new chat body: thinking_profile none, enable_thinking false, userPreferences false |
| V4 | PASS | search "atlas" -> 1 row; Oldest reverses order; tag Project -> 1 row; "zzz" -> No matches; skills "french" -> /translate |
| V5 | PASS | requests: POST /stop then DELETE /api/chats; composer back to Send; 0 chats |
| V7 | PASS | no console/page errors in any group |
| V6 | pending | full check run below |
Not verified live: non-admin hiding of the Git section (component test only). Rig torn down.
- 2026-11-10: acceptance criteria reviewed against the recorded results (5 ticked, 0 left open)
- 2026-11-10: closed by the user after the PR merged into develop
