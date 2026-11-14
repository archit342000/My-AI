---
id: MYAI-64
title: "Per-chat settings: restore modes, model and persona; fix thinking profile and sliders"
status: done
epic: MYAI-53
created: 2026-11-10
updated: 2026-11-10
links:
  blocked_by: [MYAI-63]
  blocks: [MYAI-70]
---

## Description
Mode toggles and user preferences reset on reload and are never read from the opened chat; thinking profile "None" still sends `enable_thinking: true`; the slider's number box clamps on every keystroke and its track shows no fill.

Findings (MYAI-52, Verification): A-61, A-62, A-63, A-64. Evidence and the live test rig are in `~/.claude/tickets/My-AI/MYAI-52-evidence/`.

## Acceptance criteria
- [ ] Opening a chat restores its modes, model, persona and sampling values; a new chat starts from the saved defaults
- [x] Mode toggles survive a reload
- [x] Thinking profile None sends `enable_thinking: false`
- [x] Slider number box accepts typing and clearing, clamps on blur; track shows the fill; numbers align the same way
- [x] Status text clears after a few seconds

## Plan
**Date:** 2026-11-10  **Status:** Validated

### Objective
Make chat settings behave per chat again: opening a chat restores its modes, model, persona and sampling values, a new chat starts from saved defaults, toggles survive a reload, the thinking profile "None" really turns thinking off, and the slider control works.

### Context
- **Requirement:** this ticket's Description and Acceptance criteria (findings A-61 to A-64 in MYAI-52).
- **Assumes merged:** MYAI-63 (the chat's `last_model` is saved on send; without it the model part of the first criterion has nothing to restore).
- **Rules:** `docs/standards/frontend.md` (UI state in Zustand stores with a test next to each, persisted browser state keeps existing key names and formats and goes through `nsKey()`, pure logic in `src/lib/` with tests, no derived data in state), `docs/frontend.md` (State section lists the keys; `settings-store.hydrate()` is the only place that reads storage).
- **Server facts:** `GET /api/chats/<id>` returns the chat's `last_model`, `persona_id`, `research_mode`, `file_system_mode`, `browsing_mode`, `git_mode`, `code_execution_mode`, `user_preferences`, `max_tokens`, `thinking_budget_tokens`, `thinking_profile`, `enable_thinking`, `temperature`, `top_p` (seen in the MYAI-52 API dump; `backend/chat/handler.py` `get_history` spreads the chat row). The completion request carries the modes and sampling values on every send (`api/completions.ts` `buildCompletionBody`).
- **Legacy reference:** `static/script.js` `loadChat` (block after `currentChatData = chat`): restores the model from `last_model`, the mode toggles, the persona and the sampling parameters from the chat. `static/js/settings-manager.js` `applyThinkingProfile`: sets `enable_thinking` from `THINKING_PROFILES` (`static/js/constants.js`: `none` is false, `general` and `precision` are true); `my_ai_chat_defaults` holds the new-chat defaults (`thinkingProfile`, `userPreferences`, `maxTokens`, `thinkingBudgetTokens`).
- **Current code (`frontend/src/`):**
  - `state/settings-store.ts`: one set of values for the whole app; `hydrate()` reads model, sampling, research mode, vision and persona; `fileSystemMode`, `browsingMode`, `codeExecutionMode` and `userPreferences` are never stored; nothing reads a chat's values.
  - `features/settings/ChatSettingsModal.tsx`: the thinking profile `Select` calls `setSampling({ thinking_profile })` only; a `saved` status message that never clears.
  - `components/ui/Slider.tsx`: the number input clamps on every change (typing 5000 gives 32768, the field cannot be emptied). `styles/components.css` "Slider (ui-slider)" rules are overridden by `styles/legacy.css` `input[type="range"]` and its track and thumb rules (higher specificity), so the fill gradient and sizes never apply.
  - `features/chat/ChatPage.tsx` and `features/home/HomePage.tsx` render the transcript; neither touches the settings store.
  - `api/types.ts` `ChatDetail` does not type the fields listed above.

### Approach
- **Defaults and active values.** The store keeps its current fields as the active values (what the next send uses) and adds a persisted `defaults` snapshot for new chats. `hydrate()` loads the defaults and copies them into the active values. Two new actions: `applyChat(detail, models)` sets the active values from a chat and marks the store as chat-scoped: the model only when `last_model` is in the loaded model list; the modes (git mode only for an admin); `userPreferences`; the persona; `max_tokens`, `thinking_budget_tokens` and `thinking_profile`, with `enable_thinking` derived from the profile; `temperature` and `top_p` only when the stored value is a number other than the server default 1.0 (otherwise they stay "model default"). Absent values (`null`, or the placeholder string `"None"` that `lib/chat-model.ts` `isAbsent` already recognises; the profile value `none` is a real value) are skipped; `resetToDefaults()` copies the defaults back and clears that mark. Setters always change the active values; they also write the defaults only while the store is not chat-scoped.
- **What is persisted.** Existing keys keep their names and formats. The three unsaved mode toggles go into a new key `my_ai_modes` (JSON, through `nsKey()`); `userPreferences` is read from and written to the legacy `my_ai_chat_defaults` object's `userPreferences` field, leaving its other fields untouched. Git mode stays unpersisted.
- **When values switch.** A hook `features/chat/useChatSettings.ts` (new), called at the top of `ChatPage` (before its early returns), runs the model-list query itself (the same key and function the composer uses, so both share one cached result) and calls `applyChat` once per opened chat, as soon as both the chat detail and the model list have loaded (not on every refetch, so edits made while the chat is open are kept). On a reload straight into a chat the apply therefore waits for the list instead of skipping the model. It reads the detail through `useChatDetail(chatId)` (the same query `ChatPage` uses). Its cleanup calls `resetToDefaults()` and clears the "applied" marker when the chat page unmounts or the chat id changes (so StrictMode's mount, cleanup, mount in development applies again), so the home page, a new chat and a temporary chat started from a chat all begin from the defaults. A toggle changed inside an open chat is kept for that visit and stored by the next send; a reload before sending falls back to the chat's stored values (accepted).
- **Thinking profile.** A pure helper `enableThinkingFor(profile)` in a new `lib/thinking.ts` mirrors the legacy table; `setSampling` applies it whenever `thinking_profile` changes.
- **Slider.** The number box keeps its own text while focused and commits on blur or Enter (parse, clamp, round to the step); Escape restores the value. Numbers are right-aligned and the native spinner is hidden. The slider CSS selectors are raised to `input[type="range"].ui-slider__input` so they win over the legacy rules and the fill shows.
- **Status text.** The "saved" message in `ChatSettingsModal` clears after three seconds.
- **Rejected:** PATCHing the chat on every toggle (the next send already stores the values server-side, and legacy's write-back made one chat's values the global default); a separate store per chat (the chat row on the server is the per-chat store).

### Out of scope
- New controls for top-k, min-p and penalties, and the System Settings UI for new-chat defaults and research depth: MYAI-70.
- Saving `last_model` with the chat: MYAI-63 (this ticket reads it).
- Persona mode presets applying toggles when a persona is chosen.

### Steps
#### Step 1: Types and the thinking helper
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/api/types.ts` (modify: add to `ChatDetail` the fields listed in Context that are not there yet; `last_model` exists and MYAI-63 adds `file_system_mode` and `resume_needed`), `frontend/src/lib/thinking.ts` (create: `enableThinkingFor`), `frontend/src/lib/thinking.test.ts` (create)
- **Change:** as in Approach ("Thinking profile": the helper).
- **Verification:** unit tests: `none` gives false, `general` and `precision` true, an unknown profile true.

#### Step 2: Store: defaults, active values, persistence
- **Status:** todo
- **Depends on:** 1
- **Files:** `frontend/src/state/settings-store.ts` (modify: `KEYS`, `defaults`, `hydrate`, setters, new `applyChat`, `resetToDefaults`), `frontend/src/state/settings-store.test.ts` (modify)
- **Change:** as in Approach ("Defaults and active values", "What is persisted", and `setSampling` applying `enableThinkingFor`).
- **Verification:** unit tests: toggling file-system mode, hydrating a fresh store and reading it back gives true; `applyChat` sets modes, `userPreferences`, persona and sampling from a detail and leaves storage unchanged; a detail with profile `none` gives `enable_thinking` false whatever the row says; a stored temperature of 1.0 leaves temperature unset; a setter after `applyChat` does not write the defaults; `resetToDefaults` restores them; a user (non-admin) never gets git mode from a chat; `my_ai_chat_defaults` keeps its other fields; setting the profile to `none` sets `enable_thinking` false; non-admin keys carry the user suffix.

#### Step 3: Apply on open, reset on new chat
- **Status:** todo
- **Depends on:** 2
- **Files:** `frontend/src/features/chat/useChatSettings.ts` (create), `frontend/src/features/chat/useChatSettings.test.tsx` (create), `frontend/src/features/chat/ChatPage.tsx` (modify), `frontend/src/features/chat/ChatPage.test.tsx` (modify)
- **Change:** as in Approach ("When values switch").
- **Verification:** component tests: opening a chat whose detail has file-system mode on and a persona sets both in the store; a refetch of the same chat does not overwrite a toggle changed meanwhile; opening a second chat applies its values; leaving the chat page (to `/`, or by starting a temporary chat from it) restores the defaults; a `last_model` missing from the model list leaves the current model; when the model list resolves after the detail, the model is still applied.

#### Step 4: Slider
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/components/ui/Slider.tsx` (modify), `frontend/src/components/ui/primitives.test.tsx` (modify: Slider block), `frontend/src/styles/components.css` (modify: "Slider (ui-slider)" block selectors, number alignment, spinner)
- **Change:** as in Approach ("Slider").
- **Verification:** component tests: typing 5000 then blurring commits 5000; clearing and blurring restores the previous value; an out-of-range entry is clamped on blur; Escape restores. Live (MYAI-52 rig, Chat Settings > Parameters): the track's computed `background-image` is a gradient and the thumb is 16px.

#### Step 5: Chat Settings dialog details
- **Status:** todo
- **Depends on:** 2
- **Files:** `frontend/src/features/settings/ChatSettingsModal.tsx` (modify: status timeout, "Reset to model default" alignment class, store read through selectors instead of the whole-store subscription), `frontend/src/features/settings/ChatSettingsModal.test.tsx` (create), `frontend/src/styles/components.css` (modify: "Chat Settings (chat-settings)" block)
- **Change:** as in Approach ("Status text"); the reset button lines up with the field labels.
- **Verification:** component tests with fake timers: choosing a model shows the status and it is gone after three seconds; choosing the profile "None" leaves `enable_thinking` false in the store.

#### Step 6: Request check, docs and full checks
- **Status:** todo
- **Depends on:** 3, 4, 5
- **Files:** `frontend/src/features/chat/send-turn.test.ts` (modify), `docs/frontend.md` (modify: State section: defaults and active values, the `my_ai_modes` key, per-chat restore), `frontend/README.md` (modify: Conventions line on persisted keys), `docs/standards/frontend.md` (modify only if its persisted-state sentence needs the new key named)
- **Change:** docs match the code.
- **Verification:** unit test: with the profile `none` the completion body has `enable_thinking: false`; after `applyChat` with file-system mode on the body has `fileSystemMode: true`. Then from `frontend/`: `npm run typecheck`, `npm run lint`, `npm run test`, `npm run build`; from the repo root `pytest tests` and `scripts/check.sh --frontend-only`. Live (MYAI-52 rig, `scripts/s5.mjs` test 8): after a reload and reopening the FILE chat the File System toggle is on.

### Tests
- Unit: `lib/thinking.test.ts`, `state/settings-store.test.ts`, `features/chat/send-turn.test.ts`.
- Component: `useChatSettings.test.tsx`, `ChatPage.test.tsx`, `primitives.test.tsx`, `ChatSettingsModal.test.tsx`.

### Risks and open questions
- **A chat opened in two tabs** keeps separate active values per tab; the server stores whatever the last send carried. Same as legacy.
- **The temporary chat** lives on `/` and never runs the hook, so nothing resets its values while it is open.
- **Shared files:** `ChatPage.tsx` is also changed by MYAI-56 and MYAI-63.

### Success criteria
- [ ] Opening a chat restores its modes, model, persona and sampling values; a new chat starts from the saved defaults
- [ ] Mode toggles survive a reload
- [ ] Thinking profile None sends `enable_thinking: false`
- [ ] Slider number box accepts typing and clearing and clamps on blur; the track shows the fill; numbers align the same way
- [ ] Status text clears after a few seconds
- [ ] Checks pass
### Reviewer brief
- **Objective:** chat settings are per chat again: restore on open, defaults for a new chat, toggles that survive a reload, a thinking profile "None" that disables thinking, a working slider.
- **Decisions:** the settings store keeps active values plus a persisted `defaults` snapshot; `applyChat(detail, models)` and `resetToDefaults()`; setters write defaults only while not chat-scoped; new key `my_ai_modes` through `nsKey()`, `userPreferences` in the legacy `my_ai_chat_defaults` object; `useChatSettings` in `ChatPage` applies once per chat when the detail and the model list have loaded and resets in its cleanup; `enable_thinking` always derived from the profile (`lib/thinking.ts`); temperature and top-p restored only when not the server default 1.0; no PATCH per toggle; slider number box commits on blur or Enter and its CSS outranks the legacy `input[type="range"]` rules.
- **Out of scope:** new sampling controls and the defaults UI (MYAI-70), saving `last_model` (MYAI-63), persona presets.
- **Success criteria:** opening a chat restores its modes, model, persona and sampling values and a new chat starts from defaults; toggles survive a reload; profile None sends `enable_thinking: false`; slider accepts typing, clamps on blur, shows its fill, aligns numbers; status text clears; checks pass.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- **Round 1:** validator FAIL (1 blocking, 9 minor). Judged FAIL. Valid blocking: resetting on `HomePage` mount missed a temporary chat started from a chat page (fixed: reset in the hook's cleanup). Minors fixed: unsent in-chat toggles on reload stated as accepted; dependency on MYAI-63 for `last_model` (linked `blocked_by`); temperature/top-p default handling and `userPreferences` restore; `enable_thinking` derived in `applyChat`; model list source; helper moved to `lib/thinking.ts`; README; selectors in `ChatSettingsModal`.
- **Round 2 (diff-scoped):** validator FAIL (1 blocking, 2 minor). Judged FAIL. Valid: on a reload into a chat the model list was not cached when the hook applied (fixed: the hook runs the model-list query and applies once both are loaded). Minors fixed: wording on the `"None"` placeholder; only missing `ChatDetail` fields are added.
- **Round 3 (diff-scoped):** validator PASS (2 minor). Judged PASS. Fixed inline: the applied marker is cleared in the cleanup (StrictMode); the hook reads the detail through `useChatDetail`.

## Implementation notes
### Autopilot run (2026-11-10)
- Mode: automatic (batch)
- Branch: bugfix/restore-chat-settings  PR base: bugfix/turn-follow-ups (stacked on PR #103)  Starting commit: ce2e1f9
- Dirty before start: none
- Work files: state/settings-store.ts(+test), lib/thinking.ts(+test), api/types.ts, features/chat/{useChatSettings,ChatPage}, settings/ChatSettingsModal(+test), ui/Slider.tsx, primitives.test.tsx, components.css, send-turn.test.ts, docs/frontend.md, README
- Counters: fix 0/10, review 4/5, re-verify 4
- Last completed stage: 4 verify  Next: done (shipped)
- Hard blocker: none
- WIP commit: none

### Autopilot decisions (2026-11-10)
- Stage 1: ticket already holds a validated plan; skipped re-planning.
- Step 5: the plan's "Reset to model default alignment" CSS was not changed: the button is already left-aligned under its slider; the A-64 alignment complaint was about the number boxes, which are now right-aligned.
PR: https://github.com/archit342000/My-AI/pull/104, branch bugfix/restore-chat-settings, base bugfix/turn-follow-ups

## Verification

### Acceptance review (2026-11-10)
Criteria ticked on the live and e2e results recorded in the PR's Testing section (checks run on throwaway backends during the autopilot run; scripts in `MYAI-64-evidence/`).
Left unticked, no PASS recorded:
- criterion 1: modes restored live; model and persona restore are unit/component tests only

### Verification plan (2026-11-10)
**Diff base:** ce2e1f9 (PR #103 tip). **Isolation:** throwaway DATA_DIR /tmp/myai64/data, stub model :5191, backend :5192 serving this branch's build; no containers touched. Scripts: `MYAI-64-evidence/scripts/` (up.sh, stub.py, serve.py, lib.mjs, v64.mjs). Teardown: kill listeners on 5191/5192, rm -rf /tmp/myai64.

| ID | Criterion | Scenario | Method | Files | Expected |
|----|-----------|----------|--------|-------|----------|
| V1 | toggles survive a reload | turn on File System Mode and Browsing, reload `/`, open the tools menu | browser | settings-store.ts | both on after reload; `my_ai_modes` in localStorage |
| V2 | opening a chat restores its modes; a new chat starts from defaults | chat A sent with File System on; set defaults back off; chat B sent with it off; open A from the sidebar, then B, then New chat | browser | useChatSettings.ts, settings-store.ts, ChatPage.tsx | A: on; B: off; New chat: defaults (off); the defaults in localStorage unchanged by toggling inside a chat |
| V3 | profile None sends enable_thinking false | choose Thinking profile None in Chat Settings, send; read the completion request body | browser+network | settings-store.ts, ChatSettingsModal.tsx | body has enable_thinking false |
| V4 | slider | Chat Settings > Parameters: typing, clearing, clamping, Escape; track fill and thumb size via computed style | browser | Slider.tsx, components.css | 5000 commits 5120 on blur; empty restores; track background is a gradient; thumb 16px; spinner hidden |
| V5 | status text clears | pick a model; status shown then gone after ~3s | browser | ChatSettingsModal.tsx | status gone within 4s |
| V6 | regression | vitest, typecheck, lint, build | CLI | all | pass |
| V7 | no console errors | collect console/page errors | browser | all | none unexpected |
Persona and model restore are covered by unit/component tests only (the stub has one model and no persona).


### Results (2026-11-10)
HEAD ce2e1f9 + uncommitted work.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | File System and Browsing toggled on, page reloaded: both still on; `my_ai_modes` = {"fileSystemMode":true,"browsingMode":true,"codeExecutionMode":true} |
| V2 | PASS | chat A (sent with File System on) opens with it on; chat B (off) opens off; New chat starts from the defaults (off); toggling Browsing inside B left `my_ai_modes` unchanged and did not carry into the new chat |
| V3 | PASS | after choosing Thinking profile None the completion body had `enable_thinking: false`, `thinking_profile: "none"` |
| V4 | PASS | typing 5000 then blur gives 5120 (step 256); clearing and blur restores the value; 99999 clamps to 32768; the track shows the fill and the thumb is 16px (`shots/V4-slider.png`); number box right-aligned, spinner hidden |
| V5 | PASS | "Model updated" shown, gone after 3.3s |
| V6 | PASS | vitest 484/484, typecheck, lint, build |
| V7 | PASS | no console/page/http errors |

Not verified live: persona and model restore (the stub has one model and no persona); unit and component tests cover them.
Verdict: verified (V1-V7 PASS; persona/model restore by tests only).

### Results (re-run 1, 2026-11-10)
V1-V5 PASS again after the round 1 fixes. Teardown done.

### Results (re-run 2, 2026-11-10)
V1-V5 PASS again; live Escape/Enter on the number box pass. Teardown done.

### Results (re-run 3, 2026-11-10)
V1-V5 PASS again after the round 3 fixes. Teardown done.

### Results (re-run 4, 2026-11-10)
V1-V5 PASS again after the round 4 edits. Final verdict: verified (persona and model restore by unit/component tests only).

## Review history
### Round 4 - 2026-11-10
Verdict: Approve with comments (0 BLOCKER/MAJOR, 4 MINOR). Resolution: fixed 4. Checks: vitest 499/499, typecheck, lint, build, scripts/check.sh --frontend-only pass; live V1-V5 pass again. Runtime changed only for MINOR items, so the loop ends.
- R4-1 [MINOR] settings-store.ts - corrupt `my_ai_modes` (`null`, a string, wrong types) threw at start-up - Static - Fixed: only an object of booleans is accepted; test
- R4-2 [MINOR] Prettier failed on settings-store.ts/test (clean at base) and three new files - Static - Fixed (prettier on those files only)
- R4-3 [MINOR] Composer effect used a render-time chatScoped for the skip - Static - Fixed: reads both from the store, keeps it in the deps
- R4-4 [MINOR] docs said the apply waits for the model list - Static - Fixed (loaded or failed)

### Round 3 - 2026-11-10
Verdict: Request changes (2 MAJOR, 1 MINOR, 1 NIT). Resolution: fixed 4. Checks: vitest 498/498, typecheck, lint, build; live V1-V5 pass again. Runtime changed.
- R3-1 [MAJOR] Composer.tsx - the default-model effect did not re-run when chat settings were left, so the home page could be left with no model - Static - Fixed: chatScoped subscribed and a dependency; test (failed before)
- R3-2 [MAJOR] settings-store.ts - an old chat that never set temperature/top p inherited the new-chat default instead of the model default - Static - Fixed: a stored 1.0 sets them unset, a missing field leaves them; tests (failed before)
- R3-3 [MINOR] Slider.tsx - the "ended by key" flag could swallow a later blur - Static - Fixed: cleared on the next focus; test
- R3-4 [NIT] flag name - Static - Fixed (`endedByKey`)

### Round 2 - 2026-11-10
Verdict: Request changes (2 MAJOR, 1 MINOR). Resolution: fixed 3. Checks: vitest 494/494, typecheck, lint, build; live V1-V5 pass again, plus live Escape (restores, dialog stays open) and Enter (commits once). Runtime changed.
- R2-1 [MAJOR] Slider.tsx - Escape committed the typed value (the blur it causes ran commit); regression from round 1 R1-7 - Static - Fixed: an `edited` ref makes the blur after Enter/Escape a no-op; test with real focus (failed before); live check
- R2-2 [MINOR] Slider.tsx - Enter committed twice (commit + blur) - Static - Fixed with the same ref; test asserts one call (failed before)
- R2-3 [MAJOR] Composer.tsx - the default-model effect could replace an opened chat's model - Static - Fixed: the effect reads the store and skips while chat settings are active; test (failed before)

### Round 1 - 2026-11-10
Verdict: Request changes (3 MAJOR, 6 MINOR, 2 NIT, one Haiku reviewer). Resolution: fixed 10, deferred 1. Checks: vitest 493/493, typecheck, lint, build; live V1-V5 pass again. Runtime changed.
- R1-1 [MAJOR] settings-store.ts - a sampling value saved before the fix ({none, thinking on}) kept sending thinking on after reload - Static - Fixed: loadSampling derives enable_thinking from the profile; test (failed before)
- R1-2 [MAJOR] a chat with no persona (NULL) kept the default persona and then stored it on the chat - Static - Fixed: null/"None"/"" clear the persona, a detail without the field leaves it; test (failed before)
- R1-3 [MAJOR] "Reset to model default" never reaches the server (omitted values are kept), so reopening brings the old temperature/top p back - Static - Deferred: fixing it needs a server change (the epic excludes backend changes); documented in docs/frontend.md and the PR notes; follow-up suggested
- R1-4 [MINOR] setters wrote the defaults until the chat's values had loaded - Static - Fixed: enterChat() marks the store chat-scoped when the page opens; tests (failed before)
- R1-5 [MINOR] a failed model list blocked the whole apply - Static - Fixed: apply with an empty list after an error (only the model is skipped); test (failed before)
- R1-6 [MINOR] focus and blur rounded an untouched slider value - Static - Fixed; test (failed before)
- R1-7 [MINOR] after Enter/Escape the next keystroke appended to the text - Static - Fixed: Enter and Escape end the edit and leave the box; test (failed before)
- R1-8 [MINOR] status test used real timers - Static - Fixed (fake timers)
- R1-9 [MINOR] missing tests - Static - Fixed (stored none profile, null persona, failed list, untouched focus/blur, --fill)
- R1-10 [NIT] README parentheses doubled - Static - Fixed
- R1-11 [NIT] picking the same model again did not restart the status timer - Static - Fixed (message id); test (failed before)


## Log
- 2026-11-10: created
- 2026-11-10: added to epic MYAI-53
- 2026-11-10: linked blocked_by MYAI-63 (it saves `last_model`, which this ticket restores)
- 2026-11-10: plan validated, 3 rounds
- 2026-11-10: linked blocks MYAI-70
- 2026-11-10: autopilot started (batch); implemented; verified
- 2026-11-10: review round 1 resolved (10 fixed, 1 deferred); re-verify pass
- 2026-11-10: review round 2 resolved (3 fixed); re-verify pass
- 2026-11-10: review round 3 resolved (4 fixed); re-verify pass
- 2026-11-10: review round 4 resolved; loop clean
- 2026-11-10: batch-autopilot: shipped, base bugfix/turn-follow-ups, PR #104
- 2026-11-10: acceptance criteria reviewed against the recorded results (4 ticked, 1 left open)
- 2026-11-10: closed by the user after the PR merged into develop; 1 acceptance criteria left unticked as known limits (see Verification, Acceptance review)
