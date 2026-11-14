---
id: MYAI-13
title: "N5: Artifacts toggle does nothing on workspace pages"
status: done
created: 2026-11-08
updated: 2026-11-09
---

## Description
Report N5 (Medium), partial. The Artifacts toggle is hidden on Home (merged), but on /workspace/:id the panel is always mounted (WorkspacePage.tsx renders ArtifactPanel unconditionally), so the toggle has no effect there. Suggested fix: gate the workspace panel on artifactsOpen like the chat page does, or hide the toggle there. Not blocked, but the behaviour choice should be confirmed.

## Acceptance criteria
- [x] The toggle shows or hides the panel on /workspace/:id
- [x] Behaviour choice confirmed (gate or hide) (2026-11-09: gate, Implementation notes)

## Plan
**Date:** 2026-11-09  **Status:** Validated

### Objective
Make the top-right Files/Artifacts toggle (`#nav-files-btn` in `RootLayout`) actually show and hide the files panel on `/workspace/:workspaceId`, by gating the workspace's `ArtifactPanel` on the shared `artifactsOpen` UI-store flag the same way `ChatPage` gates its `ArtifactDrawer`. The toggle stays visible on workspace pages (user decision, 2026-11-09).

### Context
- **Requirement:** AC1 "The toggle shows or hides the panel on /workspace/:id". AC2 (gate vs hide) is already decided: gate.
- **Assumptions:**
  - Keep the workspace page's current inline layout (`.artifact-inline` block under the "Files" heading); do not switch it to the right-hand `ArtifactDrawer` overlay. "Matching the chat page" means the same gating mechanism (select `artifactsOpen` from `useUiStore`, render conditionally), not the same layout. Swapping to the drawer would be a larger visual change than the ticket asks for.
  - The page's own "Files" `<h2>` (WorkspacePage) is gated together with the panel (a heading over nothing would be misleading). Note `ArtifactPanel` also renders its own `<h2 className="artifact-panel__title">Files</h2>` inside `<section aria-label="Artifacts">`, so two "Files" headings exist today when the panel shows; removing the page-level one is out of scope for this ticket.
  - When open, pass `onClose={() => setArtifactsOpen(false)}` to `ArtifactPanel` so the panel shows its "Close files panel" button, as the chat drawer does (`ArtifactDrawer.tsx` passes `onClose`; `ArtifactPanel.tsx` renders the close `IconButton` only when `onClose` is set).
  - `artifactsOpen` is global and starts `false` (`state/ui-store.ts`), so workspace files are now hidden until the user clicks the toggle, and the open/closed state carries over between chat and workspace pages. This is accepted as the intended consequence of the gate decision.
- **Docs and rules:** `AGENTS.md` (run tests; small edits; stop and ask on rule conflicts), `docs/standards/frontend.md` (before finishing run `npm run typecheck`, `npm run lint`, `npm run test` from `frontend/`; component tests query by role/label where possible), `docs/standards/testing.md`, `docs/standards/git.md` (changelog generated from commits; no manual changelog edit). `docs/frontend.md` and `frontend/README.md` do not describe the workspace files panel, so no doc update is needed.
- **Current behaviour (origin/develop 6a13e04):**
  - `frontend/src/app/RootLayout.tsx` `RootLayout`: renders `#nav-files-btn` (calls `toggleArtifacts`) on every path except `/` and `/logs*`.
  - `frontend/src/features/chat/ChatPage.tsx` `ChatPage`: `const artifactsOpen = useUiStore((s) => s.artifactsOpen);` then `{artifactsOpen ? <ArtifactDrawer scope={{ chatId: data.id }} /> : null}`.
  - `frontend/src/features/workspace/WorkspacePage.tsx` `WorkspacePage`: always renders `<h2>Files</h2>` and `<div className="artifact-inline"><ArtifactPanel scope={{ workspaceId }} /></div>`; already imports `useUiStore` (used via `getState()` for `setNewChatWorkspaceId`). It has early returns before the main JSX (`if (!workspace) ...`), so any new hook must be called above them.
  - `frontend/src/features/workspace/WorkspacePage.test.tsx`: no test touches the files panel or `artifactsOpen`; no `beforeEach` resets the UI store.
  - `frontend/src/features/chat/ChatPage.test.tsx`: precedent test "mounts the artifact panel only when artifacts are open" (sets `useUiStore.setState({ artifactsOpen: true })`, waits for `.artifact-panel`).

### Approach
Mirror `ChatPage`: read `artifactsOpen` (and `setArtifactsOpen`) with `useUiStore` selectors at the top of `WorkspacePage`, and wrap the "Files" heading plus the `.artifact-inline` block in `{artifactsOpen ? (...) : null}`, passing `onClose` to `ArtifactPanel`. No store, layout, CSS or RootLayout changes.
Rejected: hiding the toggle on workspace pages (user chose gate); replacing the inline panel with `ArtifactDrawer` (larger visual change, not requested); per-page open state (would diverge from how chat works).

### Steps
#### Step 1: Gate the workspace files panel
- **Files:** `frontend/src/features/workspace/WorkspacePage.tsx` (modify), `WorkspacePage`.
- **Change:** add `const artifactsOpen = useUiStore((s) => s.artifactsOpen);` and `const setArtifactsOpen = useUiStore((s) => s.setArtifactsOpen);` next to the other hooks, above the `if (!workspace)` early returns. Render the `<h2>Files</h2>` and the `.artifact-inline` div only when `artifactsOpen` is true, and pass `onClose={() => setArtifactsOpen(false)}` to `ArtifactPanel`. Update the component doc comment if it still implies the files are always shown.
- **Verification:** `npm run typecheck` and `npm run lint` from `frontend/` pass (lint includes the rules-of-hooks check).

#### Step 2: Tests for the gate
- **Files:** `frontend/src/features/workspace/WorkspacePage.test.tsx` (modify).
- **Change:** reset `useUiStore.setState({ artifactsOpen: false })` in a new `beforeEach` (import `useUiStore` and `beforeEach`). Add tests, following the `ChatPage.test.tsx` precedent. Identify the panel by its region role and label (`ArtifactPanel` renders `<section aria-label="Artifacts">`, i.e. role `region`, name "Artifacts"), not by the "Files" heading, which appears twice when open. (a) with `artifactsOpen` false, the workspace renders but there is no "Artifacts" region and no "Files" heading at all; (b) with `artifactsOpen` true, the panel is present; (c) toggling the store (`toggleArtifacts` inside `act`) after render shows then hides the panel; (d) clicking "Close files panel" sets `artifactsOpen` to false and removes the panel. Mock `artifactsApi.list` (from `frontend/src/api/filesystem.ts`, as `ArtifactPanel.test.tsx` does) in the open-panel tests so the panel does not hit the network.
- **Verification:** `npx vitest run src/features/workspace/WorkspacePage.test.tsx` from `frontend/` passes; temporarily reverting Step 1 makes (a), (c) and (d) fail (implementer's sanity check, not committed).

#### Step 3: Full frontend checks
- **Files:** none.
- **Change:** run the full frontend suite and repo check.
- **Verification:** from `frontend/`: `npm run typecheck`, `npm run lint`, `npm run test`, `npm run build` all pass; then `scripts/check.sh` from the repo root passes (per `AGENTS.md`). The CSS coverage test (`src/test/css-coverage.test.ts`) still passes since `.artifact-inline` remains in use.

### Tests
- Updated: `frontend/src/features/workspace/WorkspacePage.test.tsx` (gate closed, gate open, toggle via store, close button).
- Commands: `npm run typecheck`, `npm run lint`, `npm run test`, `npm run build` in `frontend/`; `scripts/check.sh` at the repo root.
- No new Playwright spec: this changes an existing view's visibility, not a new user flow (`docs/standards/frontend.md` asks e2e only for new flows). A live browser check of the toggle on `/workspace/:id` belongs to the verify stage.

### Risks and open questions
- **Default hidden:** workspace files were always visible; after this they are hidden until the toggle is clicked, and the state is shared with chat pages. Impact: users may not find workspace files at first. Mitigation: this is the confirmed behaviour; the toggle is visible on the page. If it proves confusing, a follow-up could default the panel open on workspace pages (not planned).
- **Layout choice:** the plan keeps the inline panel rather than the chat drawer. If the user meant "use the drawer too", Step 1 changes to rendering `<ArtifactDrawer scope={{ workspaceId }} />` and removing the inline block (and possibly the `.artifact-inline` CSS rule). Not blocking; recorded as an assumption.
- No open blocking questions.

### Success criteria
- [ ] On `/workspace/:id`, toggling `artifactsOpen` (the Files button) shows the files panel when it becomes open and hides it when it becomes closed.
- [ ] The panel's "Close files panel" button hides it and the toggle can reopen it.
- [ ] `WorkspacePage.test.tsx` covers closed, open, toggle and close; the full frontend suite, build and `scripts/check.sh` pass.

### Validation log
- **Round 1** (Haiku Explore): validator PASS, 2 MINOR. My judgement: pass, both MINOR valid and fixed.
  1. MINOR, Step 2 tests querying the "Files" heading would hit two matches: valid. `ArtifactPanel.tsx:181` renders its own `<h2>Files</h2>` inside `<section aria-label="Artifacts">` (line 179). Fixed: tests identify the panel by role `region` named "Artifacts"; the Context assumption now records the duplicate heading as existing behaviour that this ticket does not change.
  2. MINOR, first success criterion was inverted ("shows when closed"): valid. Reworded to open shows, closed hides.
- **Round 2** (Haiku Explore, diff-scoped to the three changed parts): validator PASS, no issues. My judgement: pass. I spot-checked that a `section` with `aria-label` maps to role `region` and that `vite.config.ts` runs tests in jsdom with `src/test/setup.ts`. Plan marked Validated.

## Implementation notes

### Autopilot run (2026-11-09)
Batch 5 item. Branch bugfix/workspace-artifacts-toggle from origin/develop a1a9333, PR base develop. Dirty files before start: none.

### Baseline (2026-11-09)
At develop a1a9333: vitest 307 pass (49 files); typecheck clean; lint only the forms.tsx warning.

### Implementation progress
- [x] Step 1: WorkspacePage gates the Files heading and `ArtifactPanel` on `artifactsOpen`, with `onClose`
- [x] Step 2: four tests in WorkspacePage.test.tsx (closed, open, toggle after render, close button); written first and failing without the gate (3 of 4)
- [x] Step 3: vitest 311 pass, tsc clean, lint only forms.tsx, build ok. scripts/check.sh not run as a whole (pytest-asyncio missing)

### Smoke test (2026-11-09)
vitest 311 pass (49 files), typecheck clean, lint 1 existing warning, build ok.
Status on develop (checked at e327094, 2026-11-08): Still present on develop: WorkspacePage.tsx mounts ArtifactPanel without checking artifactsOpen.
Decision (user, 2026-11-09): gate the workspace ArtifactPanel on artifactsOpen, matching the chat page; keep the toggle visible on workspace pages.

PR: https://github.com/archit342000/My-AI/pull/68, branch bugfix/workspace-artifacts-toggle, base develop

## Verification
### Verification plan (2026-11-09, light form: one component)
Real app (5099, /tmp/myai13-data), built React UI, Playwright (`scripts/ui.js`). Never touches :5000/:5001, containers, backend/data or a real chats.db.
| ID | Criterion | Scenario | Expected |
|----|-----------|----------|----------|
| V1 | AC1 | /workspace/:id: initial, toggle on, toggle off | Artifacts region absent, present, absent |
| V2 | AC1 | the panel's own close button, then the toggle again | hides it; the toggle reopens it |
| V3 | AC1 | panel closed | no Files heading, workspace title still renders |
Not run yet.

### Results (2026-11-09)
**Commit verified:** a1a9333 (+ uncommitted). Hashes: WorkspacePage.tsx d039a7f5, WorkspacePage.test.tsx f5935a1b.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | ui.log, ui-v1-closed.png, ui-v1-open.png: panel count 0, 1, 0 |
| V2 | PASS | ui.log: close button hides it, toggle reopens it |
| V3 | PASS | ui.log: no Files heading while closed, workspace title present |

No console errors. Teardown: app and proxy stopped, /tmp/myai13-data removed, ports free, containers and git status as before. **Verdict: verified (3/3 PASS).**

## Review history
### Round 1 - 2026-11-09
Verdict: Approve with comments. Scope: origin/develop a1a9333..working tree, 2 files, single Haiku reviewer.
- R1-1 [MINOR] no Playwright spec for the toggle on workspace pages - Static - Rejected: the validated plan decided against a new e2e spec (visibility change of an existing view); the live browser check covered it
- R1-2 [MINOR] test isolation: store reset only in beforeEach - Static - Fixed (also in afterEach)
- R1-3 [NIT] doc comment over 100 columns - Static - Fixed
- R1-4 [NIT] test helper `open` renders rather than opens - Static - Fixed (renamed `renderPage`)
- R1-5 [NIT] open test did not check the page's own Files heading - Static - Fixed (two Files headings expected)
Resolution: fixed 4, rejected 1. Checks: WorkspacePage tests 11 pass, tsc clean, lint 1 existing warning. No runtime change (comment, tests), so no re-verify.

## Log
- 2026-11-08: created from reports/full-scope-final-report-2026-11-08.md
- 2026-11-09: behaviour decision recorded (gate the panel).
- 2026-11-09: plan validated, 2 rounds
- 2026-11-09: autopilot started (batch-autopilot)
- 2026-11-09: implemented, smoke tests pass
- 2026-11-09: verified live, 3/3 PASS
- 2026-11-09: review round 1 Approve with comments; fixed 4, rejected 1
- 2026-11-09: shipped, PR https://github.com/archit342000/My-AI/pull/68
- 2026-11-09: batch-autopilot: shipped, base develop
- 2026-11-09: closed, PR merged
