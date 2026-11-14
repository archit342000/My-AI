---
id: MYAI-59
title: "Mobile layout at 390px: bubble width, overlaps, drawer, dialogs"
status: done
epic: MYAI-53
created: 2026-11-10
updated: 2026-11-10
links:
  blocked_by: [MYAI-55, MYAI-57]
  conflicts_with: [MYAI-60]
---

## Description
On phones the assistant bubble is indented and narrow, the files button overlaps messages, the drawer hides the New-workspace button, is see-through and stays open behind dialogs, toasts cover the composer and dialogs have no small-screen layout.

Findings (MYAI-52, Verification): A-26, A-27, A-28, A-29, A-31, A-32, A-33, A-34 (A-30 moved to MYAI-65). Evidence and the live test rig are in `~/.claude/tickets/My-AI/MYAI-52-evidence/`.

## Acceptance criteria
- [x] Assistant bubble uses the full column width (as legacy) at 390px
- [x] The top bar (menu button, title, files button) is one opaque band; messages never show beside or behind its buttons
- [x] Drawer shows New Chat, Temporary Chat and New Workspace, is opaque, and closes when a dialog opens
- [x] Hamburger matches legacy size and position and does not cover page titles
- [x] No horizontal overflow on home, chat, logs and every dialog at 390px
- [x] Toasts appear above the composer, not on it
- [x] Dialogs fit the screen with padding and usable rows
- [x] Files button is shown on the home page as in legacy

## Plan
**Date:** 2026-11-10  **Status:** Validated

### Objective
Make the React UI fit a 390px phone the way the legacy UI did: full-width assistant bubble, an opaque top bar that content never shows around, a usable opaque drawer that closes for dialogs, legacy-sized menu button, toasts clear of the composer, dialogs that fit, and the files button on the home page.

### Context
- **Requirement:** this ticket's Description and Acceptance criteria (findings A-26 to A-29 and A-31 to A-34 in MYAI-52; A-30 moved to MYAI-65).
- **Assumes merged:** MYAI-55 (assistant row uses the legacy structure: `.assistant-header-row` with avatar and thought header, then full-width timeline and bubble; `.bot-turn` grid removed) and MYAI-57 (tools menu sheet on phones). MYAI-58 adds the `is-ios` class; on iPhones that already switches glass surfaces to the opaque legacy fallbacks (A-33). Legacy keeps blur on Android, so this ticket does not remove blur in general.
- **Rules:** `docs/standards/frontend.md` (CSS custom properties, no inline styles except `// dynamic-style`, real buttons with accessible names, keyboard operable, new user flows get a Playwright spec), `docs/frontend.md` (keep legacy class names).
- **Legacy reference (`frontend/src/styles/legacy.css`, `@media (max-width: 768px)` block around the "Floating Hamburguer Menu" comment, same rules as `static/styles.css`):** drawer 50% wide; `#mobile-toggle` 3.5rem square, radius 1rem, at 1.25rem/1.25rem, accent colour, hidden while the drawer is open; `#messages` padding `5rem 1rem 8rem`; `.message-row` padding `16px 8px`; `.avatar-wrapper` 28px. Measured (MYAI-52 `c-m-long-legacy.png`): bubble spans 25-365px of 390.
- **Current code (`frontend/src/`):**
  - `styles/components.css` "Mobile navigation (mobile-topbar, sidebar-scrim)": `.mobile-topbar` is a 40px circle at 10px/10px, always shown at 768px and below; "Collapsed sidebar rail": `#sidebar.sidebar-collapsed #temp-chat-btn { display: inline-flex !important }`. In the drawer the action row shows New Chat and the clock; the New-workspace button is pushed out of the 195px drawer.
  - `app/RootLayout.tsx`: the drawer closes on navigation only; `#nav-files-btn` is not rendered on `/` or `/logs`; `IconButton.mobile-topbar` toggles the drawer.
  - `styles/components.css` "Toasts": `.ui-toast-viewport` is fixed at `bottom: max(16px, safe-area)`; it covers the composer on a phone.
  - `styles/legacy.css` `.modal-content`: `width: 90%`, `max-height: 85vh`; `components.css` "Model manager rows": `.model-row__action` has a fixed width and `.model-row__name` truncates; "Message edit box": `.edit-box__actions` wraps to two rows at 390px.
  - `styles/legacy.css` `.chat-title-header`: translucent with blur; the files button (`.top-right-btn`, 54px) hangs 4px below it, and scrolled messages show beside and behind both buttons.
  - `features/logs/LogsPage.tsx` `.logs-toolbar`: the "Logs" title sits under the menu button on phones.

### Approach
- **Row:** with MYAI-55's markup the bubble is already full width; this ticket adds the legacy phone values (row padding, 28px avatar, transcript side padding) in the "Chat transcript" block's phone media query and checks the result against legacy with the metrics script.
- **Top bar:** at 768px and below the chat title header is an opaque band (`--bg-primary`) 5rem tall (the 3.5rem buttons at 1.25rem from the top, leaving 0.25rem below; the transcript's legacy top padding is already 5rem), and the menu and files buttons are centred in it; pages without a title (home, workspace, logs) get the same band height reserved, so content starts below the buttons.
- **Menu button:** legacy geometry and colours for `.mobile-topbar`; hidden while the drawer is open (the scrim, Escape and the drawer's own toggle close it, as today).
- **Drawer:** the action row keeps all three actions by letting New Chat shrink (label stays) and wrapping if needed; the drawer surface is opaque at 768px and below; `RootLayout` closes the drawer when `useModalStore`'s `open` becomes non-null, only at 768px and below (the same `window.innerWidth <= 768` gate its other drawer effects use); the desktop sidebar is untouched.
- **Toasts:** at 768px and below the toast stack sits above the composer (`bottom: calc(var(--composer-h, 0px) + var(--space-4))`): `Composer` publishes `--composer-h` and removes it on unmount, so pages without a composer get the plain bottom offset.
- **Dialogs:** at 768px and below `.modal-content` uses the full width minus 8px margins and `max-height: calc(100dvh - 16px)`, the body keeps its bottom padding when it scrolls, model rows put the name on its own line above the badge and button, and the edit box buttons share one row (smaller padding).
- **Files button on home:** rendered on `/` as a disabled, dimmed button (legacy shows it dimmed there); it stays hidden on `/logs`.
- **Logs title:** the toolbar gets a 5rem left inset on phones (menu button: 1.25rem offset plus 3.5rem width, plus a gap) so the title clears the button.
- **Rejected:** removing blur on all phones (not legacy behaviour; iOS gets it through `is-ios`); a separate mobile component tree (CSS is enough).

### Out of scope
- Keyboard and viewport meta: MYAI-58. Tools sheet: MYAI-57. Workspace page header overflow (A-30) and the page's styling: MYAI-65. Artifact sheet: MYAI-66.
- Tablet breakpoints other than the existing 768px rule.

### Steps
#### Step 1: Assistant row and transcript padding on phones
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/styles/components.css` (modify: phone media query of the "Chat transcript" block)
- **Change:** as in Approach ("Row").
- **Verification:** MYAI-52 rig (`~/.claude/tickets/My-AI/MYAI-52-evidence/scripts/up.sh`, `node metrics.mjs m '/chat/{long}'`): `.bot-message .message-content-wrapper` x and width, `.bot-message .avatar` size and `.user-message` padding differ from legacy by at most 1px.

#### Step 2: Opaque top bar and button alignment
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/styles/components.css` (modify: "Mobile navigation" block: header band, `.top-right-btn` position, reserved band on untitled pages)
- **Change:** as in Approach ("Top bar").
- **Verification:** in the Step 7 spec: after scrolling a long chat, no message row intersects the rectangle of the menu button or the files button, and the header's computed background is opaque.

#### Step 3: Menu button and drawer
- **Status:** todo
- **Depends on:** 2
- **Files:** `frontend/src/styles/components.css` (modify: `.mobile-topbar`, drawer surface, action row; "Collapsed sidebar rail" temp-chat rule scoped so it does not force the button into the phone drawer row layout), `frontend/src/app/RootLayout.tsx` (modify: hide the menu button while the drawer is open, close the drawer when a dialog opens), `frontend/src/app/RootLayout.test.tsx` (modify)
- **Change:** as in Approach ("Menu button", "Drawer").
- **Verification:** component tests: opening a dialog through `useModalStore` while the drawer is open collapses the sidebar at a 390px width and leaves it open at 1440px; the menu button is not rendered (or is `hidden`) while the drawer is open. In the Step 7 spec: the three action buttons are inside the drawer's rectangle and the drawer's background alpha is 1.

#### Step 4: Toasts above the composer
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/styles/components.css` (modify: "Toasts" block, phone rule)
- **Change:** as in Approach ("Toasts").
- **Verification:** in the Step 7 spec: after `/help` on a phone viewport the toast's bottom edge is above `.input-container`'s top edge.

#### Step 5: Dialogs, model rows and edit box on phones
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/styles/components.css` (modify: "Modal", "Model manager rows" and "Message edit box" blocks, phone rules)
- **Change:** as in Approach ("Dialogs").
- **Verification:** in the Step 7 spec: System Settings, Model manager and the icon picker lie inside the viewport with at least 8px on each side; the last control of a scrolled dialog body is fully visible; a model name is not truncated when the row is wider than the name; the three edit buttons share one row.

#### Step 6: Files button on home and Logs title inset
- **Status:** todo
- **Depends on:** 2
- **Files:** `frontend/src/app/RootLayout.tsx` (modify: render `#nav-files-btn` disabled on `/`), `frontend/src/app/RootLayout.test.tsx` (modify), `frontend/src/styles/components.css` (modify: disabled state of `.top-right-btn`, `.logs-toolbar` phone inset in the "Logs page" block)
- **Change:** as in Approach ("Files button on home", "Logs title").
- **Verification:** component tests: on `/` the files button is present and disabled, on `/chat/c1` enabled, on `/logs` absent. In the Step 7 spec: the "Logs" heading does not intersect the menu button.

#### Step 7: Phone spec, docs and full checks
(The "in the Step 7 spec" verifications of Steps 2 to 6 are run here, once the spec exists; until then each step is checked by hand at 390px.)
- **Status:** todo
- **Depends on:** 1, 2, 3, 4, 5, 6
- **Files:** `frontend/e2e/mobile-layout.spec.ts` (create), `frontend/playwright.config.ts` (modify: add this spec to the phone project's `testMatch` and the desktop project's `testIgnore`; create that project with both settings if MYAI-58 has not), `docs/frontend.md` (modify: phone layout rules in the "Mobile" note; MYAI-58 creates that note, so create it here if it is not there yet)
- **Change:** the spec mocks chat data as `e2e/chat-send.spec.ts` does and runs the checks named in Steps 2 to 6, plus: `document.documentElement.scrollWidth` equals the viewport width on `/`, a chat, `/logs` and with each dialog open.
- **Verification:** `npm run e2e` passes the spec; from `frontend/`: `npm run typecheck`, `npm run lint`, `npm run test`, `npm run build`; from the repo root `pytest tests` and `scripts/check.sh --frontend-only`.

### Tests
- Component: `app/RootLayout.test.tsx`.
- E2E: `e2e/mobile-layout.spec.ts` (phone project).
- Guards: `test/css-coverage.test.ts`, `test/inline-style.test.ts` stay green.
- Live comparison: `metrics.mjs m` against the legacy instance (MYAI-52 rig).

### Risks and open questions
- **Hiding the menu button while the drawer is open** follows legacy; the drawer's own collapse button and the scrim remain as close controls.
- **A disabled files button on home** is legacy parity; if the user prefers it hidden there, drop Step 6's first part.
- **Depends on MYAI-55's class names;** if they differ at implement time, Step 1 targets the classes that ticket shipped.

### Success criteria
- [ ] Assistant bubble spans the column at 390px as in legacy (within 1px)
- [ ] Opaque top bar; no message visible beside or behind its buttons
- [ ] Drawer shows all three actions, is opaque and closes when a dialog opens
- [ ] Menu button has the legacy size and position and covers no page title
- [ ] No horizontal overflow on home, chat, logs and dialogs at 390px
- [ ] Toasts sit above the composer
- [ ] Dialogs fit with padding; model rows and edit buttons are usable
- [ ] Files button shown (disabled) on home
- [ ] Checks and the phone spec pass
### Reviewer brief
- **Objective:** the React UI fits a 390px phone as legacy did: full-width bubble, opaque top bar, usable drawer, legacy menu button, toasts clear of the composer, fitting dialogs, files button on home.
- **Decisions:** CSS-only where possible, in `styles/components.css` phone rules; legacy phone values for row padding and avatar; a 5rem opaque top band with both buttons inside it; `.mobile-topbar` takes the legacy geometry and is hidden while the drawer is open; drawer opaque at 768px and below, all three actions kept, closed when a dialog opens (phone widths only); toast stack offset by `--composer-h`; dialogs full width minus margins with `100dvh` cap; files button rendered disabled on `/`; blur is not removed for Android (legacy keeps it; iOS gets opaque surfaces through `is-ios` from MYAI-58).
- **Out of scope:** keyboard and viewport meta (MYAI-58), tools sheet (MYAI-57), workspace page (MYAI-65), artifact sheet (MYAI-66), other breakpoints.
- **Success criteria:** bubble width within 1px of legacy at 390px; opaque top bar with no content beside its buttons; drawer complete, opaque and closing for dialogs; legacy menu button covering no title; no horizontal overflow on home, chat, logs and dialogs; toasts above the composer; usable dialogs; disabled files button on home; checks and the phone spec pass.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- **Round 1:** validator FAIL (1 blocking, 6 minor). Judged FAIL. Valid blocking: the drawer auto-close on dialog open had no width gate and would collapse the desktop sidebar (fixed: 768px and below, verified at both widths). Minors fixed: when the Step 7 spec checks run; toast offset fallback for pages without a composer; `testIgnore` on the desktop project; the "Mobile" docs note; band height; logs inset value.
- **Round 2 (diff-scoped):** validator PASS (1 minor). Judged PASS. Fixed inline: the gap below the buttons is 0.25rem.

## Implementation notes
Branch bugfix/mobile-layout, base bugfix/popover-placement (autopilot batch item 10).
### Implementation progress
- [x] Step 1: assistant row at phone width - already at legacy geometry from the thought box row; a reply without a box now stacks avatar over answer (`.bot-turn` at 768px and below)
- [x] Step 2: opaque top band (`main::before`, 5rem), chat title header opaque with side inset
- [x] Step 3: `.mobile-topbar` legacy geometry/colour, hidden while the drawer is open; opaque drawer, three actions; RootLayout closes the drawer when a dialog opens (phone widths only) (+tests)
- [x] Step 4: toasts above the composer (`--composer-h`)
- [x] Step 5: dialogs full width less margin, `100dvh` cap, model rows wrap, edit box buttons on one row
- [x] Step 6: files button rendered disabled on `/`, absent on `/logs`; logs title inset (+tests)
- [x] Step 7: e2e/mobile-layout.spec.ts (new `phone` Playwright project; desktop project ignores it), docs/frontend.md "Mobile"
Decisions: the phone rules are the last block of components.css so they win over the earlier base rules (same specificity); `.mobile-topbar` uses the `hidden` attribute while the drawer is open.
### Smoke test (2026-11-10)
check.sh --frontend-only: typecheck, lint, 447 tests, build pass. e2e phone 6/6.
Not verified live: model manager rows wrapping and the edit box single-row buttons (the rig has no model list; /api/models answers 500 there), user-message actions height difference vs legacy (not in the acceptance criteria).

PR: https://github.com/archit342000/My-AI/pull/110, branch bugfix/mobile-layout, base bugfix/popover-placement

## Verification

### Acceptance review (2026-11-10)
Criteria ticked on the live and e2e results recorded in the PR's Testing section (checks run on throwaway backends during the autopilot run; scripts in `MYAI-59-evidence/`).
All criteria covered.

## Review history
### Round 1 - 2026-11-10
Verdict: Request changes (2 MAJOR). Single Haiku reviewer.
- R1-1 [MAJOR] logs title hidden under the top band - Fixed: `.logs-main` starts below the band (screenshot and e2e y >= 80 confirm it was a real defect); the side inset on the toolbar was dropped.
- R1-2 [MAJOR] spec did not cover the logs title position, model rows or the edit box - Fixed: spec asserts the heading's y, adds model-row wrapping and the edit box single-row/overflow cases (7 tests, passed twice in a row).
- R1-3 [MINOR] edit box buttons unmeasured - Fixed by the same spec case (one row, inside 390px).
- R1-4 [MINOR] raw 5rem values - Fixed: `--phone-topbar-h` and `--phone-topbar-inset`. The legacy 0.35 disabled opacity stays a literal.
- R1-5 [MINOR] fixed sleeps in the spec - Fixed: a `settled()` poll on the element's box.
- R1-6 [MINOR] docs said blur kept on Android - Fixed: docs say the drawer and band are opaque on phones, other surfaces keep blur.
Resolution: check.sh passes (447 tests); e2e phone 7/7 twice; live shots re-checked. Round 1 fixes were not re-reviewed. Not verified live beyond the spec: nothing else outstanding. Rig note: chat-send e2e fails on this rig only because /api/models answers 500 (console errors).


## Log
- 2026-11-10: created
- 2026-11-10: added to epic MYAI-53
- 2026-11-10: linked blocked_by MYAI-57
- 2026-11-10: linked conflicts_with MYAI-60
- 2026-11-10: linked blocked_by MYAI-55 (the row markup it lays out)
- 2026-11-10: scope note: A-30 moved to MYAI-65; A-33 on iPhones is the missing `is-ios` class (MYAI-58), legacy keeps blur on Android
- 2026-11-10: plan validated, 2 rounds
- 2026-11-10: acceptance criteria reviewed against the recorded results (8 ticked, 0 left open)
- 2026-11-10: closed by the user after the PR merged into develop
