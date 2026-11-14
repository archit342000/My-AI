---
id: MYAI-67
title: "Settings dialogs, logs and tool dialogs polish"
status: done
epic: MYAI-53
created: 2026-11-10
updated: 2026-11-10
links:
  blocks: [MYAI-70]
---

## Description
Dialogs mix legacy and new buttons and input heights, sub-dialog titles and form buttons are inconsistent, cards are clipped, the logs table overflows and expands the wrong rows after refresh, and the code-history dialog reads the wrong chat.

Findings (MYAI-52, Verification): A-76, A-77, A-78, A-79, A-81, A-82. Evidence and the live test rig are in `~/.claude/tickets/My-AI/MYAI-52-evidence/`.

## Acceptance criteria
- [ ] One button and input system in every dialog
- [ ] Titles, form spacing and footer buttons are consistent (Cancel then primary, in the footer)
- [x] Persona form offers only the flags the server stores (see the plan: the persona API ignores `git_mode` and `code_execution_mode`, so a Code Execution toggle needs a backend change that is outside this epic)
- [x] No clipped cards or touching controls
- [x] Logs page is centred, scrolls horizontally inside the table, keeps the right rows expanded
- [ ] Code history uses the open chat and renders runs readably with an error state

## Plan
**Date:** 2026-11-10  **Status:** Validated

### Objective
Give the settings dialogs, the logs page and the tool dialogs one consistent look and correct behaviour: a single button and input system, consistent titles and form footers, no clipped or touching controls, a centred logs page whose expanded rows survive refresh, and a code-history dialog that reads the open chat.

### Context
- **Requirement:** this ticket's Description and Acceptance criteria (findings A-76 to A-79, A-81, A-82 in MYAI-52).
- **Rules:** `docs/standards/frontend.md` (reuse UI primitives, no inline styles except `// dynamic-style`, CSS custom properties, selectors instead of whole-store subscriptions, stable keys, tests for components with logic), `docs/frontend.md`. The epic excludes backend changes.
- **Server facts:** `POST` and `PUT /api/personas` read `name`, `content`, `is_default`, `research_mode`, `file_system_mode`, `browsing_mode` only (`backend/chat/router.py` `create_persona`, `update_persona`); `git_mode` and `code_execution_mode` are ignored. `GET /api/tools/code-execution/history/<chat_id>` returns the chat's runs (`backend/tools/router.py` `get_execution_history`).
- **Current code (`frontend/src/`):**
  - `features/settings/SystemSettingsModal.tsx`: code-runner fields use raw `<input style={inputStyle}>` (`features/settings/form-styles.ts`), the legacy `Field`, `Section`, `Status` from `features/settings/forms.tsx` (6 inline styles) and a legacy `.btn-primary` submit; 2 more inline styles in the file.
  - `components/ui/Modal.tsx` + `.ui-modal__header-row`: with `onBack` the title ends up centred, without it left-aligned; `footer` prop renders `.modal-footer`.
  - `features/settings/CrudList.tsx`: the dialog title stays the list title while a form is open; the forms (`SkillsDialog.tsx`, `PersonasDialog.tsx`, `PreferencesDialog.tsx`) render Save then Cancel inside the body (`.crud-actions`), unlike `PromptDialog` and `ConfirmDialog` (footer, Cancel then primary); hint text has no bottom margin before the next field (`components/ui/Field.tsx`, "Field, Input, Textarea" block).
  - `features/settings/PersonasDialog.tsx` `FLAGS` includes `git_mode`, which the server does not store.
  - `features/settings/AgentConfigDialog.tsx`: the last `.agent-card` touches the footer border; number inputs show native spinners. `features/settings/ModelsDialog.tsx`: the "Run speed test" button follows the `Select` with no gap.
  - `features/logs/LogsPage.tsx`: `expanded` is a set of row indexes while the query refetches every 5 seconds; `.logs-page { padding-inline-start: 280px }` assumes an expanded sidebar and the table wrapper lets the table run under the right edge.
  - `features/tools/CodeHistoryDialog.tsx`: uses the streaming chat's id before the route's, prints each run as raw JSON, no error state, 4 inline styles. `features/tools/PortalDialog.tsx`: 3 inline styles.

### Approach
- **One form system.** The code-runner form uses `Field`, `Input` and `Button` from `components/ui/`; `features/settings/forms.tsx` keeps only what is still used, rewritten on classes (`Section`, `Status`), and `form-styles.ts` is deleted. Number inputs hide the native spinner (one rule on `.ui-input[type="number"]`).
- **Titles and footers.** `Modal` left-aligns the title in both cases (back button, title, spacer, close). `CrudDialog` takes the form's title ("New skill", "Edit skill", and so on) while a form is open and passes the form's buttons to the `Modal` footer in the order Cancel, Save; forms submit through the `form` attribute. Fields get a bottom margin so a hint never touches the next label.
- **Persona flags.** The Git mode toggle is removed from the form because the server does not store it; no Code Execution toggle is added (it would be ignored too). A backend follow-up is suggested in Risks.
- **Spacing.** The agent card list gets bottom padding inside the scrolling body; the speed-test button gets the standard field gap.
- **Logs page.** The page uses the shared `--sidebar-width` inset instead of a fixed 280px and a centred content column with a maximum width; the table scrolls horizontally inside `.logs-table-wrap`. Expanded rows are tracked by a stable row key built by a pure helper `rowKey(entry, index)` in `features/logs/log-levels.ts` (the feature's existing tested module for log-row logic) (id or timestamp plus log file when present, else a hash of the row's JSON), so a refresh keeps the same rows open.
- **Code history.** The dialog reads the chat id from the route (`useMatch('/chat/:chatId')`), renders each run as a card keyed by the run's id (language, time, code, output, exit status) from a typed `CodeRun` in `api/filesystem.ts`, and shows loading, empty and error states. `PortalDialog` moves its inline styles to classes and shows the server's error text in the standard error style.
- **Rejected:** adding persona flags the API ignores; a table library for the logs.

### Out of scope
- Backend support for `git_mode` and `code_execution_mode` on personas.
- Missing legacy features in these dialogs (git PAT, clear all chats, reset app, telemetry chart, preferences and skills search): MYAI-70.
- Phone layout of dialogs: MYAI-59. Slider and Chat Settings behaviour: MYAI-64.

### Steps
#### Step 1: Modal header and form footers
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/components/ui/Modal.tsx` (modify: header layout), `frontend/src/components/ui/Modal.test.tsx` (modify), `frontend/src/features/settings/CrudList.tsx` (modify: form title and footer slot), `frontend/src/features/settings/CrudList.test.tsx` (modify), `frontend/src/features/settings/SkillsDialog.tsx`, `PersonasDialog.tsx`, `PreferencesDialog.tsx` (modify: buttons to the footer, `FLAGS` without `git_mode`), their tests `SkillsDialog.test.tsx`, `PersonasDialog.test.tsx`, `PreferencesDialog.test.tsx` (modify), `frontend/src/api/settings.ts` (modify: the persona create and update body type no longer includes `git_mode`; `PersonasDialog`'s `EMPTY` and submitted body drop it), `frontend/src/styles/components.css` (modify: "Modal", "Field, Input, Textarea" and "Manage lists" blocks)
- **Change:** as in Approach ("Titles and footers", "Persona flags").
- **Verification:** component tests: with and without `onBack` the title is the first text after the optional back button and is not centred by a class; opening a form changes the dialog title and puts Cancel then Save in the footer; Save in the footer submits the form; the persona form has no Git mode switch and its request body carries no `git_mode`.

#### Step 2: System Settings on primitives
- **Status:** todo
- **Depends on:** 1
- **Files:** `frontend/src/features/settings/SystemSettingsModal.tsx` (modify), `frontend/src/features/settings/SystemSettingsModal.test.tsx` (modify), `frontend/src/features/settings/forms.tsx` (modify), `frontend/src/features/settings/form-styles.ts` (delete), `frontend/src/features/settings/ModelsDialog.tsx` (modify: imports and spacing class), `frontend/src/features/settings/ChatSettingsModal.tsx` (modify only for the `Status` import if it changes), `frontend/src/styles/components.css` (modify: new "Settings sections" block, number-input spinner rule), `frontend/src/test/inline-style.test.ts` (modify: remove the `SystemSettingsModal.tsx` and `forms.tsx` entries)
- **Change:** as in Approach ("One form system", "Spacing": the speed-test gap). The code-runner form keeps its own "Save code runner settings" button inside its section (it saves one section of a dialog that has no single submit), now as a primary `Button`; the Cancel-then-primary footer rule applies to dialogs that are one form.
- **Verification:** component tests: the code-runner fields are labelled inputs with the `ui-input` class and saving still posts the four values; no element in the dialog has a `style` attribute. The inline-style guard passes with the lower baseline.

#### Step 3: Agent cards
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/styles/components.css` (modify: "Agent configuration cards" block)
- **Change:** as in Approach ("Spacing": the card list padding). This is the "clipped card" of finding A-79: the last card ran into the footer border.
- **Verification:** live (MYAI-52 rig, 1440x900, Agent configuration scrolled to the end): the last card's bottom edge is at least 12px above the footer's top border.

#### Step 4: Logs page
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/features/logs/log-levels.ts` (modify: new `rowKey`), `frontend/src/features/logs/log-levels.test.ts` (modify), `frontend/src/features/logs/LogsPage.tsx` (modify: expanded set by key, row keys), `frontend/src/features/logs/LogsPage.test.tsx` (modify), `frontend/src/styles/components.css` (modify: "Logs page" block)
- **Change:** as in Approach ("Logs page").
- **Verification:** unit tests: `rowKey` is stable for the same row and differs for different rows. Component test: a row expanded before a refetch that prepends a new row is still the expanded one. Live (1440px): the table wrapper's right edge is inside the viewport, the wrapper scrolls horizontally, and the page's left and right margins inside `main` are equal within 16px.

#### Step 5: Code history and portal dialogs
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/api/filesystem.ts` (modify: `CodeRun` type, typed `codeExecApi.history`), `frontend/src/features/tools/CodeHistoryDialog.tsx` (modify), `frontend/src/features/tools/CodeHistoryDialog.test.tsx` (create), `frontend/src/features/tools/PortalDialog.tsx` (modify), `frontend/src/features/tools/PortalDialog.test.tsx` (modify), `frontend/src/styles/components.css` (modify: new "Tool dialogs" block), `frontend/src/test/inline-style.test.ts` (modify: remove the `CodeHistoryDialog.tsx` and `PortalDialog.tsx` entries)
- **Change:** as in Approach ("Code history"). The `CodeRun` fields are taken from the rows `db.get_code_execution_history` returns (read the function at implement time and type exactly those columns).
- **Verification:** component tests: on `/chat/c1` with another chat streaming the request is for `c1`; a run renders its code and output in separate blocks; an error response shows the error state; with no chat open the dialog says so.

#### Step 6: Docs and full checks
- **Status:** todo
- **Depends on:** 1, 2, 3, 4, 5
- **Files:** `docs/frontend.md` (modify only if a described component changes), `frontend/README.md` (modify only if affected)
- **Change:** docs match the code.
- **Verification:** from `frontend/`: `npm run typecheck`, `npm run lint`, `npm run test`, `npm run build`; from the repo root `pytest tests` and `scripts/check.sh --frontend-only`. Live pass over every dialog at 1440px in light and dark with the MYAI-52 rig (`scripts/tour.mjs d-light`, `d-dark`): no legacy pill buttons, no touching controls.

### Tests
- Unit: `features/logs/log-levels.test.ts`.
- Component: `Modal.test.tsx`, `CrudList.test.tsx`, `SkillsDialog.test.tsx`, `PersonasDialog.test.tsx`, `PreferencesDialog.test.tsx`, `SystemSettingsModal.test.tsx`, `LogsPage.test.tsx`, `CodeHistoryDialog.test.tsx`, `PortalDialog.test.tsx`.
- Guards: `test/inline-style.test.ts`, `test/css-coverage.test.ts`.

### Risks and open questions
- **Persona flags need a backend decision:** the persona API should either store `git_mode` and `code_execution_mode` or the columns should go. Suggest a backend ticket; until then the form shows only stored flags.
- **`CrudDialog`'s footer slot** changes how the three forms are wired; their existing tests cover save, validation and cancel and are updated in Step 1.
- **Shared files:** `components.css`; `ChatSettingsModal.tsx` is also changed by MYAI-64.

### Success criteria
- [ ] One button and input system in every dialog
- [ ] Titles, form spacing and footer buttons are consistent (Cancel then primary, in the footer)
- [ ] Persona form offers only the flags the server stores
- [ ] No clipped cards or touching controls
- [ ] Logs page is centred, scrolls horizontally inside the table and keeps the right rows expanded
- [ ] Code history uses the open chat, renders runs readably and has an error state
- [ ] Checks pass
### Reviewer brief
- **Objective:** one consistent look and correct behaviour for the settings dialogs, the logs page and the tool dialogs.
- **Decisions:** code-runner form on `Field`/`Input`/`Button`, `form-styles.ts` deleted, `forms.tsx` reduced to class-based `Section` and `Status`; `Modal` title left-aligned with or without a back button; `CrudDialog` shows the form's title and puts Cancel then Save in the modal footer; fields get a bottom margin; the persona form drops the Git mode toggle and adds no Code Execution toggle because the persona API stores neither (backend follow-up suggested); spacing fixes for agent cards and the speed-test button; logs page uses `--sidebar-width`, a centred column, in-table horizontal scroll and row keys from `rowKey`; code history reads the route's chat, renders typed runs as cards with states; inline styles removed from the touched files.
- **Out of scope:** backend support for persona flags, missing legacy features in these dialogs (MYAI-70), phone layout (MYAI-59), slider and Chat Settings behaviour (MYAI-64).
- **Success criteria:** one button and input system; consistent titles, spacing and footers; persona form shows only stored flags; no clipped or touching controls; logs page centred with stable expanded rows; code history on the open chat with readable runs and an error state; checks pass.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- **Round 1:** validator PASS (5 minor). Judged PASS after checking `PersonasDialog.tsx`, `SystemSettingsModal.tsx`, `CodeHistoryDialog.tsx` and `log-levels.ts`. Fixed inline: `git_mode` leaves the persona body type and form state; the code-runner section keeps its own save button (stated); which finding the agent-card step closes; run cards keyed by id; why `rowKey` lives in the feature module.

## Implementation notes
### Autopilot run (2026-11-10)
- Mode: automatic (batch)
- Branch: bugfix/settings-dialogs-polish  PR base: bugfix/restore-chat-settings (stacked on PR #104)  Starting commit: 1e37be9
- Dirty before start: none
- Work files: components/ui/Modal(.test), settings/{CrudList,SkillsDialog,PersonasDialog,PreferencesDialog,SystemSettingsModal,ModelsDialog,forms}(+tests), api/{settings,filesystem}.ts, logs/{LogsPage,log-levels}(+tests), tools/{CodeHistoryDialog,PortalDialog}(+test), components.css, test/inline-style.test.ts, docs/frontend.md; deleted settings/form-styles.ts
- Counters: fix 0/10, review 5/5, re-verify 5
- Last completed stage: 4 verify  Next: done (shipped)
- Hard blocker: none
- WIP commit: none

### Autopilot decisions (2026-11-10)
- Stage 1: ticket already holds a validated plan; skipped re-planning.
- Step 3 (agent cards) was done as part of the CSS pass; no separate commit.
- The forms keep Save disabled until valid through a `setCanSave` callback to the dialog footer (the plan only said Save moves to the footer), so existing tests and behaviour hold.
PR: https://github.com/archit342000/My-AI/pull/105, branch bugfix/settings-dialogs-polish, base bugfix/restore-chat-settings

## Verification

### Acceptance review (2026-11-10)
Criteria ticked on the live and e2e results recorded in the PR's Testing section (checks run on throwaway backends during the autopilot run; scripts in `MYAI-67-evidence/`).
Left unticked, no PASS recorded:
- criterion 1: checked in System Settings only, not every dialog
- criterion 2: checked for the skill form only
- criterion 6: code-history error state: unit tests only

### Verification plan (2026-11-10)
**Diff base:** 1e37be9 (PR #104 tip). **Isolation:** throwaway DATA_DIR /tmp/myai67/data, stub model :5191, backend :5192 serving this branch's build; no containers touched. Scripts: `MYAI-67-evidence/scripts/` (up.sh, stub.py, serve.py, lib.mjs, v67.mjs). Teardown: kill listeners on 5191/5192, rm -rf /tmp/myai67.

| ID | Criterion | Scenario | Method | Files | Expected |
|----|-----------|----------|--------|-------|----------|
| V1 | one button/input system | System Settings: no `.btn-primary` legacy button, code-runner inputs are `.ui-input`, no inline styles in the dialog | browser | SystemSettingsModal.tsx, forms.tsx | 0 legacy buttons, 4 ui-input, 0 `[style]` inside |
| V2 | titles and footers | Skills dialog: Add shows "New skill", footer Cancel then Save; Edit shows "Edit skill"; sub-dialog title position equal with and without back button | browser | CrudList.tsx, Modal.tsx | titles left-aligned in both, footer order Cancel, Save |
| V3 | persona flags | Personas > Add | browser | PersonasDialog.tsx | no Git mode switch |
| V4 | no clipped cards, no touching controls | Agent configuration scrolled to the end: last card to footer gap; Model manager speed-test button gap | browser | components.css | gap >= 12px; button below the select with a gap |
| V5 | logs page | 1440px: wrapper right edge inside the viewport, horizontal scroll inside the wrapper, equal left/right margins; expand a row, generate a new request, wait for the 5s refresh: the same row is open | browser | LogsPage.tsx, log-levels.ts, components.css | as stated |
| V6 | code history | seed two runs for chat X in the throwaway DB; open chat X (another chat streaming) > Code execution history | browser+DB | CodeHistoryDialog.tsx | cards with code/output/exit status for chat X; error state not forced live (unit test) |
| V7 | spinner hidden | number inputs: computed appearance | browser | components.css | textfield |
| V8 | regression | vitest, typecheck, lint, build | CLI | all | pass |
| V9 | no console errors | collect console/page errors | browser | all | none |
Phone layout and a visual tour in light and dark are covered by screenshots only (shots/).


### Results (2026-11-10)
HEAD 1e37be9 + uncommitted work.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | System Settings: 0 `.btn-primary`, 4 `.ui-input` code-runner inputs, 0 inline styles inside (`shots/V1-system-settings.png`) |
| V2 | PASS | Skills list title "Skills" and form title "New skill" at the same x (457), footer buttons "Cancel", "Save", Cancel returns to "Skills" (`shots/V2-skill-form.png`) |
| V3 | PASS | Persona form: no Git switch (0 matches) (`shots/V3-persona-form.png`) |
| V4 | PASS | Agent configuration scrolled to the end: last card 48px above the body edge (6 cards); Model manager speed-test button 12px below the select (`shots/V4-*.png`) |
| V5 | PASS | 1440px: table wrapper right edge 1424 < 1440, left and right margins equal (0/0); with the Database stream an expanded row stayed expanded (same row, same detail) after a 5s refresh that added rows; at 420px the wrapper scrolls horizontally (674 > 394) and the page does not overflow (`shots/V5-logs*.png`) |
| V6 | PASS | two seeded runs for the open chat shown as cards (language, Passed / Failed (exit 1), time, code, output / error), no raw JSON (`shots/V6-code-history.png`); the "another chat streaming" case and the error state are covered by unit tests |
| V7 | PASS | number inputs have `appearance: textfield` (spinner hidden) |
| V8 | PASS | vitest 514/514, typecheck, lint, build |
| V9 | PASS | no console/page/http errors |

Not verified live: the Network and Events log streams (empty in the throwaway backend; the Database stream was used for the table), the code-history error state, a light/dark tour of all dialogs.
Verdict: verified (V1-V9 PASS; the gaps above are covered by tests or not exercised).

### Results (re-run 1, 2026-11-10)
V1-V6 PASS again after the round 1 fixes; Escape in the Skills form returns to the list (dialog stays open); Agent configuration footer shows Cancel, Save changes. Teardown done.

### Results (re-run 2, 2026-11-10)
V1-V6 PASS again after the round 2 fixes; focus is inside the dialog after Escape (on Add) and in a form (first input); the Close button in a form returns to the list. Teardown done.

### Results (re-run 3, 2026-11-10)
V1-V6 PASS again after the round 3 fixes. Teardown done.

### Results (re-run 4, 2026-11-10)
V1-V6 PASS again after the round 4 fixes. Teardown done.

### Results (re-run 5, 2026-11-10)
V1-V6 PASS again after the round 5 fixes. Teardown done. Final verdict: verified.

## Review history
### Round 5 - 2026-11-10 (last allowed)
Verdict: Request changes (1 MAJOR, 3 MINOR, 2 NIT). Resolution: fixed 4, left 2 NITs. Checks: vitest 532/532, typecheck, lint, build, scripts/check.sh --frontend-only pass; live V1-V6 pass. The review cap (5) is reached.
- R5-1 [MAJOR] AgentConfigDialog - the draft kept the cached values when a refetch landed after opening, so Save could write stale values over newer ones - Static - Fixed: the draft follows newer saved values while untouched, and never overwrites typed edits; test (failed before)
- R5-2 [MINOR] weak zone test - Static - Fixed (datetime and text asserted)
- R5-3 [MINOR] portal background and rowKeys limit not in docs - Static - Fixed (docs/frontend.md)
- R5-4 [MINOR] persona comment hid that an edit resets git/code-execution values server-side - Static - Fixed (comment states it; backend follow-up in the PR)
- R5-5 [NIT] `interface` for data shapes (FormFooter, CodeRun) - Static - Left: consistent with neighbouring code
- R5-6 [NIT] one long line in PersonasDialog.tsx - Static - Left: the file was not Prettier-formatted at base

### Round 4 - 2026-11-10
Verdict: Request changes (2 MAJOR, 4 MINOR, 1 NIT). Resolution: fixed 5, documented 1, handled at staging 1. Checks: vitest 531/531, typecheck, lint, build; live V1-V6 pass again. Runtime changed.
- R4-1 [MAJOR] AgentConfigDialog - a refetch while open overwrote typed edits - Static - Fixed: the draft is seeded once per open; test (failed before)
- R4-2 [MINOR] discard happened only on reopen with data present - Static - Fixed: closing clears the draft; the next open seeds again
- R4-3 [MAJOR] RunCard.test.tsx not Prettier-clean - Static - Fixed
- R4-4 [MINOR] times that already carry a zone were not read - Static - Fixed; test (failed before)
- R4-5 [MINOR] README said every modal closes on Escape - Static - Fixed: the CrudDialog form exception is stated there too (also noted in the PR as a design decision)
- R4-6 [MINOR] identical id-less log rows shift keys when the oldest falls off the row limit - Static - Documented as a known limit in rowKeys
- R4-7 [NIT] the deletion of form-styles.ts was staged alone - Static - Handled when staging

### Round 3 - 2026-11-10
Verdict: Request changes (1 MAJOR, 5 MINOR, 3 NIT). Resolution: fixed 7, documented 1, rejected 1 (one rejected finding covers two points). Checks: vitest 529/529, typecheck, lint, build; live V1-V6 pass again. Runtime changed.
- R3-1 [MAJOR] AgentConfigDialog - Cancel did not discard unsaved edits (the dialog stays mounted) - Static - Fixed: the draft resets from the saved values whenever the dialog opens/closes; test (failed before)
- R3-2 [MINOR] CrudList focus guard was a first-render flag (StrictMode) - Static - Fixed: focus moves only when the view really changes
- R3-3 [MINOR] a form left open survived a close from outside - Static - Fixed: editing/delete state reset when `open` becomes false; test (failed before)
- R3-4 [MINOR] vacuous RunCard assertion - Static - Fixed (unmount between renders)
- R3-5 [MINOR] non-null assertion in PersonasDialog.test.tsx - Static - Fixed
- R3-6 [MINOR] number-input spinner hidden app-wide - Static - Documented (it is the plan's decision); duplicate agent-card rule removed
- R3-7 [NIT] unreachable throw in CodeHistoryDialog - Static - Fixed: `skipToken`
- R3-8 [NIT] created_at shown raw - Static - Fixed: shown in the reader's locale in a `<time datetime>`; raw value kept if unreadable; test
- R3-9 [NIT] Save enabled for one paint when a form opens; raw inputs instead of the Input primitive - Static - Rejected: the controls already use the shared `ui-input`/`ui-textarea` classes (one input system); the one-frame state is corrected by the form's effect at once

### Round 2 - 2026-11-10
Verdict: Request changes (2 MAJOR, 8 MINOR/NIT). Resolution: fixed 11, documented 2. Checks: vitest 526/526, typecheck, lint, build; live V1-V6 pass again plus focus checks. Runtime changed.
- R2-1 [MAJOR] CrudList.tsx - swapping the list for a form (or back) left focus on the page, so Tab left the dialog - Static - Fixed: focus moves to the first control of the new view; test (failed before); live: after Escape focus is on "Add", in a form on the first input
- R2-2 [MAJOR] the test only pressed Escape - Static - Fixed: Escape, Close button and backdrop covered, plus focus after Add/Cancel/Escape
- R2-3 [MINOR] the back chevron steps up one level while a form is open - Static - Documented as a design choice in docs/frontend.md
- R2-4 [MINOR] non-null assertion in PersonasDialog.test.tsx - Static - Fixed
- R2-5 [MINOR] `id as string` in CodeHistoryDialog - Static - Fixed: narrowed inside queryFn
- R2-6 [MINOR] Prettier on new files and Modal.test.tsx - Static - Fixed (those files only)
- R2-7 [MINOR] dead `.crud-actions` CSS - Static - Fixed
- R2-8 [MINOR] editing a persona sent the whole row back - Static - Fixed: only the six stored fields; test (failed before)
- R2-9 [MINOR] RunCard outcome untested - Static - Fixed: RunCard.test.tsx
- R2-10 [NIT] mis-indented footer label - Static - Fixed
- R2-11 [NIT] redundant map in rowKeys, blank line - Static - Fixed
- R2-12 [NIT] portal iframe background changed from black to a neutral token - Static - Documented: no hard-coded colours in CSS; noted in the PR
- R2-13 [NIT] deletion staged alone - Static - Handled when staging for the commit

### Round 1 - 2026-11-10
Verdict: Request changes (2 MAJOR, 6 MINOR, 2 NIT, one Haiku reviewer). Resolution: fixed 9, rejected 0 (R1-9 trivially). Checks: vitest 519/519, typecheck, lint, build; live V1-V6 pass again. Runtime changed.
- R1-1 [MAJOR] RunCard was a second component in CodeHistoryDialog.tsx - Static - Fixed: `features/tools/RunCard.tsx`
- R1-2 [MAJOR] Agent configuration footer had no Cancel - Static - Fixed: Cancel then Save changes; new test file (failed before)
- R1-3 [MINOR] Escape or the close button in a form dropped the typed text with the whole dialog - Static - Fixed: while a form is open they return to the list (like Cancel); test (failed before); live Escape check
- R1-4 [MINOR] aria-label on `<pre>` - Static - Fixed: blocks sit in `role=group` containers; tests updated
- R1-5 [MINOR] identical log rows could swap expansion when an identical row arrived in front - Static - Fixed: ordinals counted from the end of the list; test (failed before). A row without an id whose own content changes between refreshes still collapses (nothing stable to key on)
- R1-6 [MINOR] index fallback key in LogsPage - Static - Fixed: `rowKeys` returns {entry, key} pairs
- R1-7 [MINOR] missing tests (Loading, null exit code) - Static - Fixed
- R1-8 [NIT] CodeRun doc comment - Static - Fixed
- R1-9 [NIT] double blank line in log-levels.test.ts - Static - Fixed


## Log
- 2026-11-10: created
- 2026-11-10: added to epic MYAI-53
- 2026-11-10: acceptance criterion on the persona form changed during planning: `POST/PUT /api/personas` do not read `git_mode` or `code_execution_mode` (`backend/chat/router.py` `create_persona`, `update_persona`), so the Git toggle shown today is never saved and a Code Execution toggle cannot work without a backend change
- 2026-11-10: plan validated, 1 rounds
- 2026-11-10: linked blocks MYAI-70
- 2026-11-10: autopilot started (batch); implemented; verified
- 2026-11-10: review round 1 resolved (9 fixed); re-verify pass
- 2026-11-10: review round 2 resolved (11 fixed, 2 documented); re-verify pass
- 2026-11-10: review round 3 resolved (7 fixed, 1 documented, 1 rejected); re-verify pass
- 2026-11-10: review round 4 resolved; re-verify pass
- 2026-11-10: review round 5 resolved; review cap reached
- 2026-11-10: batch-autopilot: shipped, base bugfix/restore-chat-settings, PR #105
- 2026-11-10: acceptance criteria reviewed against the recorded results (3 ticked, 3 left open)
- 2026-11-10: closed by the user after the PR merged into develop; 3 acceptance criteria left unticked as known limits (see Verification, Acceptance review)
