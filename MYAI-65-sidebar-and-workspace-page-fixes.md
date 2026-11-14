---
id: MYAI-65
title: "Sidebar and workspace page fixes"
status: done
epic: MYAI-53
created: 2026-11-10
updated: 2026-11-10
---

## Description
Workspace icons shrink to a dot, the collapsed rail clips the logo, the footer and buttons differ from legacy, the resize handle is dead, two links reload the page, the icon picker overflows, and the workspace page is half-styled.

Findings (MYAI-52, Verification): A-30, A-65, A-66, A-67, A-68, A-69, A-70, A-71. Evidence and the live test rig are in `~/.claude/tickets/My-AI/MYAI-52-evidence/`.

## Acceptance criteria
- [ ] Workspace icons keep their size with long names
- [x] Collapsed rail is centred and unclipped
- [ ] Footer geometry, temp-chat dimming, new-workspace icon and Logs active state match legacy or are deliberate and documented
- [x] Sidebar can be resized and remembers width and collapsed state
- [x] Logs link and workspace delete navigate without a page load
- [x] Icon picker fits the viewport and scrolls
- [x] Workspace page header wraps at 390px with no horizontal overflow
- [x] Workspace page: one Files section, no phantom folder, styled rename, chat count, cards with a surface

## Plan
**Date:** 2026-11-10  **Status:** Validated

### Objective
Fix the sidebar and the workspace page: workspace icons that keep their size, a clean collapsed rail, footer and buttons in line with legacy, a working resize handle with remembered state, in-app navigation for Logs and workspace delete, a scrolling icon picker, and a finished workspace page that fits a phone.

### Context
- **Requirement:** this ticket's Description and Acceptance criteria (findings A-30 and A-65 to A-71 in MYAI-52).
- **Rules:** `docs/standards/frontend.md` (no inline styles except `// dynamic-style`, CSS custom properties, UI state in Zustand stores with tests, device preferences may stay global, real buttons and links, `ConfirmDialog` for destructive actions), `docs/frontend.md` (legacy class names, `localStorage` key names; the theme and artifact-drawer width are global device preferences).
- **Legacy reference:** `static/script.js` `syncSidebarWidth` and the `#sidebar-resizer` drag handling set `--sidebar-width` on the root (`frontend/src/styles/legacy.css`: `main { margin-left: var(--sidebar-width, 16rem) }`, `.resize-handle` rules); the temporary-chat button is dimmed to 0.4 inside an existing chat (`updateTempChatBtnState`); the new-workspace button uses a grid-plus icon; the workspace view shows a stats line (`#workspace-view-stats`) and rename, icon and delete buttons (`static/js/workspace-manager.js`).
- **Current code (`frontend/src/`):**
  - `features/sidebar/RecentChats.tsx`: `WorkspaceFolder` and `ChatLink` use inline `style` objects (10 in the `test/inline-style.test.ts` baseline); the workspace icon has no `flex-shrink: 0` and collapses when the name is long; the "Move to workspace" submenu items use the `grid` icon for every workspace.
  - `app/Sidebar.tsx`: `<div className="resize-handle" id="sidebar-resizer" />` has no handlers; the Logs entry is `<a href="/logs">` in both layouts; the footer has a `.sidebar-user` row; new-workspace uses the `grid` icon.
  - `state/ui-store.ts`: `sidebarCollapsed` starts from the viewport width and is not stored.
  - `styles/components.css` "Collapsed sidebar rail": the brand is forced visible and is clipped at the left edge at 1440px (logo x 3 to 18), and the toggle sits at x=47 while the rail icons are at 36.
  - `features/sidebar/IconPickerDialog.tsx` + `.icon-picker__grid`: the grid is taller than the dialog's visible body at 900px height and the last row is cut; the footer button is a legacy `.btn-secondary`.
  - `features/workspace/WorkspacePage.tsx`: 7 inline `style` blocks, legacy `.btn-primary`/`.btn-secondary`/`.btn-ghost` buttons, a rename `<input>` with inline styles, `window.location.assign('/')` after delete, an extra "Files" heading above `ArtifactPanel` (which has its own), files shown only while `artifactsOpen`, no chat count; the header row does not wrap (cut at 390px).
  - `features/artifacts/artifact-tree.ts` `buildTree` renders the server's placeholder directory entry `{ type: 'directory', filename: 'workspace' }` (`backend/file_system/router.py`) as an empty "workspace" folder.

### Approach
- **Sidebar rows as CSS.** `WorkspaceFolder` and `ChatLink` move their inline styles into classes in a "Sidebar lists" block of `components.css`; the workspace icon and count never shrink and the name truncates. Submenu items show each workspace's own icon.
- **Rail.** In the collapsed state the brand logo, the toggle and the rail buttons share one centred column; the logo is not clipped.
- **Footer and buttons.** The email row stays (multi-user feature) but moves into the footer's bottom edge as a compact line so Settings, System and Logs keep the legacy positions relative to each other; the temporary-chat button is dimmed inside an existing chat as in legacy; the new-workspace button uses a grid-plus icon; the Logs entry is a router `NavLink` with an active state.
- **Resize and remembered state.** A hook `app/useSidebarResize.ts` (new) handles pointer drag and arrow keys on the handle, clamps the width (200 to 480px), and sets `--sidebar-width` on the root. Width and collapsed state are stored as device preferences by `ui-store` (direct `localStorage` reads and writes in the store, as it does for the theme) under new keys `my_ai_sidebar_width` and `my_ai_sidebar_collapsed`. They are global (not passed through `nsKey()`), an explicit exception like the theme key and `my_ai_artifact_width` in `features/artifacts/ArtifactDrawer.tsx`. At 768px and below the stored collapsed value is not read at all: the drawer always starts closed, as today.
- **Icon picker.** The grid scrolls inside the dialog body (bounded height), the selected icon is scrolled into view, and "Remove icon" is a `Button` in the dialog footer.
- **Workspace page.** Styles move to a "Workspace page" block; the header wraps at narrow widths; rename uses the `Input` primitive and `Button`s; rename, icon and delete are `IconButton`s; a stats line shows the chat count; the page always shows one Files section: the `artifactsOpen` gate and the extra `<h2>Files</h2>` go, the panel is rendered without `onClose`, and the top-right files button is not shown on workspace routes (`app/RootLayout.tsx`); delete navigates with the router after invalidating; chat cards get a visible surface. In the workspace scope the panel asks `buildTree` to hide the server's placeholder (a root directory entry named `workspace` with nothing under it) through a new option, so an empty workspace shows the panel's empty state; every other folder, including a user-created empty one, is kept, and the default behaviour (and its existing test) does not change.
- **Rejected:** removing the email row to match legacy pixel positions (it is a multi-user requirement); storing sidebar state per user (it is a device preference, like the theme).

### Out of scope
- Phone drawer behaviour and the menu button: MYAI-59. Artifact panel internals and file actions: MYAI-66.
- Drag-and-drop of chats between workspaces (works today, not in the findings).

### Steps
#### Step 1: Sidebar list rows
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/features/sidebar/RecentChats.tsx` (modify: `WorkspaceFolder`, `ChatLink`, `menuItems` icons), `frontend/src/features/sidebar/RecentChats.test.tsx` (create), `frontend/src/styles/components.css` (modify: new "Sidebar lists" block), `frontend/src/test/inline-style.test.ts` (modify: `RecentChats.tsx` baseline to the remaining dynamic lines), `frontend/src/test/css-coverage.test.ts` (modify: drop `folder-chevron-wrapper` from `TODO_UNSTYLED` once styled)
- **Change:** as in Approach ("Sidebar rows as CSS").
- **Verification:** component tests: a workspace with a 70-character name renders its icon with the non-shrinking class and the count; submenu items carry the workspace's icon. Guards pass with the lower baseline.

#### Step 2: Rail, footer, buttons and Logs link
- **Status:** todo
- **Depends on:** 1
- **Files:** `frontend/src/app/Sidebar.tsx` (modify), `frontend/src/app/Sidebar.test.tsx` (modify), `frontend/src/components/icons/icon-paths.ts` (modify: add a hand-drawn `grid-plus` glyph to `UI_ICON_PATHS`, taken from the legacy `#new-folder-btn` SVG in `static/index.html`), `frontend/src/styles/components.css` (modify: "Collapsed sidebar rail" block, `.sidebar-user`, dimmed temp-chat state, Logs active state)
- **Change:** as in Approach ("Rail", "Footer and buttons").
- **Verification:** component tests: Logs is a link handled by the router (no full navigation) with `aria-current` on `/logs`; on a chat route the temporary-chat button has the dimmed class. Live (MYAI-52 rig, 1440px): in the collapsed rail the logo's left edge is at or right of 8px and the logo, toggle and rail buttons share the same centre x (1px tolerance).

#### Step 3: Resize and remembered sidebar state
- **Status:** todo
- **Depends on:** 2
- **Files:** `frontend/src/app/useSidebarResize.ts` (create), `frontend/src/app/useSidebarResize.test.tsx` (create), `frontend/src/state/ui-store.ts` (modify: `sidebarWidth`, persistence of width and collapsed), `frontend/src/state/ui-store.test.ts` (modify), `frontend/src/app/Sidebar.tsx` (modify: handle props and separator semantics)
- **Change:** as in Approach ("Resize and remembered state").
- **Verification:** unit tests: dragging sets the width within the clamp and writes the key; arrow keys change it by a fixed step; a stored collapsed or expanded state is read at start on a wide viewport; at 768px and below the store starts collapsed whatever is stored. Component test: the handle has `role="separator"` and updates `--sidebar-width`.

#### Step 4: Icon picker
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/features/sidebar/IconPickerDialog.tsx` (modify), `frontend/src/features/sidebar/IconPickerDialog.test.tsx` (create), `frontend/src/styles/components.css` (modify: "Workspace icon picker" block)
- **Change:** as in Approach ("Icon picker").
- **Verification:** component tests: the current icon has `aria-pressed="true"`; "Remove icon" is in the dialog footer and calls `onPick(null)`. Live: at 1440x900 the dialog's bottom edge is inside the viewport and the grid scrolls.

#### Step 5: Workspace page
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/features/workspace/WorkspacePage.tsx` (modify), `frontend/src/features/workspace/WorkspacePage.test.tsx` (modify), `frontend/src/features/artifacts/artifact-tree.ts` (modify: `buildTree` option), `frontend/src/features/artifacts/artifact-tree.test.ts` (modify: add cases, keep the existing ones), `frontend/src/features/artifacts/ArtifactPanel.tsx` (modify: pass the option for a workspace scope), `frontend/src/app/RootLayout.tsx` and `frontend/src/app/RootLayout.test.tsx` (modify: no files button on `/workspace/*`), `frontend/src/styles/components.css` (modify: "Workspace page cards" block extended to the whole page), `frontend/src/test/inline-style.test.ts` (modify: remove the `WorkspacePage.tsx` entry), `frontend/src/test/css-coverage.test.ts` (modify: drop `workspace-view` from `TODO_UNSTYLED`)
- **Change:** as in Approach ("Workspace page").
- **Verification:** component tests: one heading named "Files"; the stats line shows "1 chat"; rename saves through the API and uses the `Input` primitive; delete confirms, invalidates and navigates with the router (no `window.location` call); a list holding only the placeholder directory shows the empty state. Unit tests: with the option, a lone root `workspace` directory entry is dropped, a `workspace` folder with files is kept and another empty folder is kept; without the option nothing is dropped.

#### Step 6: Browser checks, docs and full checks
- **Status:** todo
- **Depends on:** 1, 2, 3, 4, 5
- **Files:** `frontend/e2e/sidebar-workspace.spec.ts` (create), `docs/frontend.md` (modify: State section: the two sidebar keys as global device preferences; a short list of deliberate differences from legacy in the sidebar: the email row in the footer)
- **Change:** the spec mocks workspaces and chats, collapses and expands the sidebar, reloads, drags the handle, opens a workspace page at 1440px and at 390px.
- **Verification:** the spec asserts the collapsed state and width survive a reload, the workspace page has `scrollWidth` equal to the viewport width at 390px with the "New chat" button fully visible, and clicking Logs does not reload the document. Then from `frontend/`: `npm run typecheck`, `npm run lint`, `npm run test`, `npm run build`, and `npm run e2e` (outside the merge gate; needs the dev server and backend); from the repo root `pytest tests` and `scripts/check.sh --frontend-only`.

### Tests
- Unit: `state/ui-store.test.ts`, `features/artifacts/artifact-tree.test.ts`.
- Component: `RecentChats.test.tsx`, `Sidebar.test.tsx`, `useSidebarResize.test.tsx`, `IconPickerDialog.test.tsx`, `WorkspacePage.test.tsx`.
- E2E: `e2e/sidebar-workspace.spec.ts`.
- Guards: `test/inline-style.test.ts`, `test/css-coverage.test.ts`.

### Risks and open questions
- **Footer position differs from legacy by the email row** on purpose; recorded as a deliberate difference (A-67).
- **`--sidebar-width` is read by legacy rules for `main`;** the collapsed rail width must keep its legacy value when collapsed.
- **Shared files:** `components.css` (most tickets), `RootLayout`-level mobile rules belong to MYAI-59.

### Success criteria
- [ ] Workspace icons keep their size with long names
- [ ] Collapsed rail is centred and unclipped
- [ ] Footer, temp-chat dimming, new-workspace icon and Logs active state match legacy or are recorded differences
- [ ] Sidebar can be resized and remembers width and collapsed state
- [ ] Logs link and workspace delete navigate without a page load
- [ ] Icon picker fits the viewport and scrolls
- [ ] Workspace page header wraps at 390px with no horizontal overflow
- [ ] Workspace page: one Files section, no phantom folder, styled rename, chat count, cards with a surface
- [ ] Checks pass
### Reviewer brief
- **Objective:** sidebar and workspace page fixed: stable workspace icons, clean rail, footer and buttons in line with legacy, working resize with remembered state, in-app navigation, scrolling icon picker, finished workspace page that fits a phone.
- **Decisions:** `RecentChats` inline styles become a "Sidebar lists" CSS block; rail centred; the email row stays (deliberate difference, documented); temp-chat dimmed inside a chat; `grid-plus` glyph added to `UI_ICON_PATHS`; Logs is a `NavLink`; `app/useSidebarResize.ts` drives `--sidebar-width`; `my_ai_sidebar_width` and `my_ai_sidebar_collapsed` are global keys (explicit exception to `nsKey()`), ignored at 768px and below; icon picker scrolls and uses a footer `Button`; workspace page on primitives with one always-visible Files section, a chat count, router navigation after delete, no files button on workspace routes; `buildTree` gets an opt-in option that hides only the server's empty root `workspace` placeholder.
- **Out of scope:** phone drawer and menu button (MYAI-59), artifact panel internals (MYAI-66), chat drag-and-drop.
- **Success criteria:** icons keep their size; rail centred and unclipped; footer and buttons match legacy or are documented differences; resize and remembered state; no page loads for Logs and workspace delete; icon picker fits; workspace header wraps at 390px; one Files section, no phantom folder, styled rename, chat count, card surfaces; checks pass.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- **Round 1:** validator FAIL (1 blocking, 7 minor). Judged FAIL. Valid blocking: the `buildTree` change would also hide user-created empty folders (fixed: opt-in option for the workspace scope that hides only the root `workspace` placeholder). Disproved: "the placeholder is not built in `router.py`" (lines 407 and 432 append it) and "no artifact-drawer width key exists" (`my_ai_artifact_width` in `ArtifactDrawer.tsx`). Minors fixed: what happens to the `artifactsOpen` gate, extra heading and files button; documented differences get a docs line; `grid-plus` glyph source; global-key exception stated; phone behaviour of stored state; the existing tree test stays.
- **Round 2 (diff-scoped):** validator PASS (1 minor). Judged PASS. Fixed inline: the persistence mechanism (direct `localStorage` in the store).

## Implementation notes
Branch bugfix/workspace-page, base develop (autopilot batch item 15).
### Implementation progress
- [x] Step 1: RecentChats rows as CSS classes (`folder-*`, `chat-list-item-*`), each workspace's own icon in the move submenu; inline-style baseline entry removed (+test)
- [x] Step 2: `grid-plus` glyph, Logs as `NavLink` (rail and footer), temp-chat dimmed in a saved chat, centred rail (logo, toggle and buttons share one column), Logs/active state (+tests)
- [x] Step 3: `useSidebarResize` (pointer drag, arrow keys, separator semantics, `--sidebar-width` follows the real width), ui-store width and collapsed persistence under `my_ai_sidebar_width` / `my_ai_sidebar_collapsed` (+tests)
- [x] Step 4: icon picker scrolls, footer `Button`, current icon scrolled into view (+test)
- [x] Step 5: workspace page on primitives and classes (no inline styles), header wraps, chat count, one Files section (no gate, no heading, no close button), router navigation after delete, no files button on workspace routes, `buildTree` option hides the server's placeholder (+tests)
- [x] Step 6: e2e/sidebar-workspace.spec.ts, docs/frontend.md
Deviations: `--sidebar-width` is now synced from the sidebar's measured width (as the legacy `syncSidebarWidth` did), so `main` also follows the collapsed rail.
### Smoke test (2026-11-10)
check.sh --frontend-only: typecheck, lint, 376 tests, build pass; e2e sidebar-workspace 4/4 twice.
Live (1440x900): rail logo/toggle/buttons all centred at x=36 (logo left edge 25, was 0); collapsed state and a 380px width survive a reload; Logs click keeps the same document; picker dialog bottom 728px with a scrolling grid (832px content in a 360px box) and "Remove icon" in the footer; workspace page: one Files heading, "0 chats", no files button, no phantom folder; at 390px: no horizontal overflow, New chat button right edge 286px.
Not changed (documented): the email row stays in the footer (deliberate), footer geometry otherwise from legacy rules.

PR: https://github.com/archit342000/My-AI/pull/115, branch bugfix/workspace-page, base develop

## Verification

### Acceptance review (2026-11-10)
Criteria ticked on the live and e2e results recorded in the PR's Testing section (checks run on throwaway backends during the autopilot run; scripts in `MYAI-65-evidence/`).
Left unticked, no PASS recorded:
- criterion 1: long workspace names not recorded as checked
- criterion 3: footer pixel positions against legacy not verified (email row is a deliberate difference)

## Review history
### Round 1 - 2026-11-10
Verdict: Request changes (1 MAJOR). Single Haiku reviewer.
- R1-1 [MAJOR] the resize handle was live on a phone and wrote the desktop width - Fixed: handle hidden at 768px and below, hook and `setSidebarWidth` are no-ops on phones; tests.
- R1-2 side effect inside the zustand updater (`toggleSidebar`) - Fixed.
- R1-3 drag used the pointer x as the width and selected text - Fixed (distance from the sidebar's left edge, `user-select: none` while dragging).
- R1-4 icon test did not check identity - Fixed (compares the drawn paths). R1-5 scrollIntoView stub leak - Fixed.
- R1-6 fixed sleeps in the spec - Fixed (`settledBox` poll). R1-7 picker on a short window - Fixed: e2e at 600px height (dialog inside, grid scrolls).
- R1-8 [NIT] optional-call guards for jsdom - Rejected: kept where jsdom lacks the API (pointer capture, scrollIntoView), now commented.
Resolution: check.sh passes (378 tests); e2e 5/5 twice. Round 1 fixes were not re-reviewed.


## Log
- 2026-11-10: created
- 2026-11-10: added to epic MYAI-53
- 2026-11-10: plan validated, 2 rounds
- 2026-11-10: acceptance criteria reviewed against the recorded results (6 ticked, 2 left open)
- 2026-11-10: closed by the user after the PR merged into develop; 2 acceptance criteria left unticked as known limits (see Verification, Acceptance review)
