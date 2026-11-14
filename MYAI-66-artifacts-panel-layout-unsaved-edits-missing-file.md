---
id: MYAI-66
title: "Artifacts panel: layout, unsaved edits, missing file actions"
status: done
epic: MYAI-53
created: 2026-11-10
updated: 2026-11-10
---

## Description
The files drawer covers the composer and messages, clips the selected row, discards unsaved edits silently, and lacks the legacy file actions (rename, move, new folder, download, copy, version diff).

Findings (MYAI-52, Verification): A-72, A-73, A-74, A-75. Evidence and the live test rig are in `~/.claude/tickets/My-AI/MYAI-52-evidence/`.

## Acceptance criteria
- [x] Opening the drawer resizes the chat instead of covering it on desktop
- [x] Selected row is never clipped
- [x] Leaving a file with unsaved edits asks first
- [x] Rename, move, new folder, delete folder, download and copy work
- [x] Version history shows a diff and handles errors

## Plan
**Date:** 2026-11-10  **Status:** Validated

### Objective
Make the files panel usable: on desktop it sits beside the chat instead of on top of it, the selected row is never clipped, unsaved edits are not lost silently, the common file actions exist (rename, move, new folder, delete folder, download, copy), and version history shows a diff and handles errors.

### Context
- **Requirement:** this ticket's Description and Acceptance criteria (findings A-72 to A-75 in MYAI-52).
- **Rules:** `docs/standards/frontend.md` (typed API calls in `src/api/`, server data through TanStack Query with invalidation, one component per file, `ConfirmDialog` for destructive actions, no inline styles except `// dynamic-style`, new user flows get a Playwright spec), `docs/standards/security.md` (model or user HTML only through `renderMarkdown`; the HTML preview stays in a sandboxed iframe). No backend change.
- **Server API (exists, read in `backend/file_system/router.py`):** `PATCH /api/file_systems/<id>` (content, `title`, `folder`), `POST /api/file_systems/directory` and `DELETE /api/file_systems/directory` (`chat_id` or `workspace_id`, `path`; delete only removes an empty directory), `GET /api/file_systems/<id>/raw`, `GET …/versions`, `GET …/versions/<n>`, `POST …/versions/<n>/restore`, `POST …/diff` (`version1`, `version2`), `GET …/current-version`.
- **Legacy reference:** the right sidebar pushes the chat: `frontend/src/styles/legacy.css` has `main { margin-right: var(--right-sidebar-width, 0px) }`; `static/index.html` has rename/move through the prompt and file-explorer dialogs, `#new-file-system-btn`, `#new-file-system-folder-btn`, `#file-system-panel-copy-btn`, `#file-system-panel-download-btn`, and a `#version-diff-panel` in the version history dialog.
- **Current code (`frontend/src/`):**
  - `features/artifacts/ArtifactDrawer.tsx` + `.artifact-drawer` (`styles/components.css` "Artifact drawer"): `position: fixed; top: 72px; right: 16px; bottom: 16px`, drawn over the transcript and the right part of the composer; width in `--artifact-width` on the drawer element.
  - `features/artifacts/ArtifactPanel.tsx`: `.artifact-tree--compact { max-height: 40% }` clips the selected row; `setDraft(null)` on every selection change and no guard on close; the viewer unmounts while the next file loads; actions are New file, Preview/Edit, Versions, Export, Delete, Save.
  - `features/artifacts/VersionsDialog.tsx`: 6 inline `style` blocks, legacy `.btn-secondary` buttons, `show()` has no error handling, no diff, no marker for the current version.
  - `api/filesystem.ts` `artifactsApi`: `list`, `get`, `create`, `update`, `remove`, `versions`, `version`, `restore`, `exportUrl`, `rawUrl`, `folders`.

### Approach
- **Beside the chat on desktop.** Above 1024px an open drawer sets `--right-sidebar-width` on the root to its width plus its margin, so `main` (and with it the transcript and composer) narrows as in legacy; the drawer stays a fixed element in that freed column. At 1024px and below it remains an overlay, and the existing full-screen sheet at 768px is unchanged.
- **Tree never clips the selection.** The compact tree keeps a bounded height with its own scroll, and the selected row is scrolled into view when the selection changes or the viewer opens.
- **Unsaved edits are guarded.** One helper in `ArtifactPanel` (`confirmDiscard`) asks through a `ConfirmDialog` ("Discard unsaved changes?") before switching files, closing the drawer, creating a file or leaving edit mode with a dirty draft. The last loaded file stays on screen with a loading state until the next one arrives.
- **File actions.** Rename and move go through the existing `artifactsApi.update` (`PATCH` with `title` or `folder`); new calls `createDirectory` and `deleteDirectory`. The viewer toolbar gains a "More" `Menu` (Rename, Move to folder, Download, Copy contents) next to Export; the tree header gains "New folder"; a folder row gets a context `Menu` with "Delete folder" (confirmed; the server refuses a non-empty folder and its message is shown). Rename and new folder use `PromptDialog`; move uses a `Select` of the folders found in the loaded list (the tree's folder paths) plus the root. Folder menus use `Menu` in its point mode, as the sidebar does; `components/ui/ContextMenu.tsx` is the unused older primitive. Download uses `rawUrl` with a `download` attribute; Copy uses the clipboard API with a toast.
- **Version history.** `VersionsDialog` is rebuilt with primitives: a list with the current version marked (`current-version`), "View" (content preview), "Compare with current" (calls `diff` and renders the unified diff text in a `<pre>` with added and removed lines coloured), "Restore" behind a confirm, and an error state for every call.
- **Rejected:** moving the drawer into the flex layout of `main` (every page would need a new layout; the CSS variable is what legacy does); a diff library (the server returns the diff).

### Out of scope
- Undo/redo beyond the editor's own history, approve/suggest flows, autosave, the live terminal and "run file" (these depend on the code-execution WebSocket; MYAI-70 lists the remaining legacy features).
- Refreshing the panel during a turn and file links: MYAI-63. The workspace page around the panel: MYAI-65.
- Backend changes.

### Steps
#### Step 1: API calls
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/api/filesystem.ts` (modify: `createDirectory`, `deleteDirectory`, `diff`, `currentVersion`, `restore` scope fix), `frontend/src/api/filesystem.test.ts` (create)
- **Change:** typed wrappers for the endpoints listed in Context, with the scope sent the way each endpoint reads it: `createDirectory` in the body; `deleteDirectory` in the query; `diff` and the existing `restore` with `chat_id` in the body and `workspace_id` in the query (the server reads `workspace_id` from the query only, so `restore` is corrected); `versions`, `version` and `currentVersion` in the query. Rename and move use the existing `artifactsApi.update` (`title`, `folder`); no new wrappers for them.
- **Verification:** unit tests with a mocked `fetch`: each call hits the right method, path, body and query for a chat scope and, for the list, file and directory calls, a workspace scope; `restore` and `diff` put `workspace_id` in the query; the version calls are tested for the chat scope only.

#### Step 2: Drawer beside the chat
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/features/artifacts/ArtifactDrawer.tsx` (modify: publish and remove `--right-sidebar-width`), `frontend/src/features/artifacts/ArtifactDrawer.test.tsx` (create), `frontend/src/styles/components.css` (modify: "Artifact drawer" block)
- **Change:** as in Approach ("Beside the chat on desktop").
- **Verification:** component tests: mounting on a wide viewport sets the root variable to the width plus margin, resizing updates it, unmounting removes it; on a 1000px viewport it is not set. Live (MYAI-52 rig, 1440px): with the drawer open the composer's right edge is left of the drawer's left edge.

#### Step 3: Tree selection and unsaved-edit guard
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/features/artifacts/ArtifactPanel.tsx` (modify), `frontend/src/features/artifacts/ArtifactPanel.test.tsx` (modify), `frontend/src/styles/components.css` (modify: "Artifact panel" block: `.artifact-tree--compact`, viewer loading state)
- **Change:** as in Approach ("Tree never clips the selection", "Unsaved edits are guarded").
- **Verification:** component tests: with a dirty draft, selecting another file opens the confirm and keeps the draft on Cancel; closing the drawer asks too; without a draft neither asks; the selected row gets `scrollIntoView` called; the previous file stays rendered while the next is pending.

#### Step 4: File actions
- **Status:** todo
- **Depends on:** 1, 3
- **Files:** `frontend/src/features/artifacts/ArtifactPanel.tsx` (modify: toolbar menu, tree header, folder menu), `frontend/src/features/artifacts/MoveFileDialog.tsx` (create), `frontend/src/features/artifacts/MoveFileDialog.test.tsx` (create), `frontend/src/features/artifacts/ArtifactPanel.test.tsx` (modify), `frontend/src/styles/components.css` (modify: "Artifact panel" block for the new toolbar, header and dialog classes)
- **Change:** as in Approach ("File actions"); every successful action invalidates the artifacts list (and the open file when it changed).
- **Verification:** component tests: Rename PATCHes `title` and the tree shows the new name; Move PATCHes `folder`; New folder posts the path and the folder appears; Delete folder confirms, and a server refusal shows its message; Download points at `rawUrl`; Copy writes the content to the clipboard and shows a toast.

#### Step 5: Version history
- **Status:** todo
- **Depends on:** 1
- **Files:** `frontend/src/features/artifacts/VersionsDialog.tsx` (modify), `frontend/src/features/artifacts/VersionsDialog.test.tsx` (create), `frontend/src/lib/diff-lines.ts` (create: classify unified-diff lines as added, removed or context), `frontend/src/lib/diff-lines.test.ts` (create), `frontend/src/styles/components.css` (modify: new "Version history" block), `frontend/src/test/inline-style.test.ts` (modify: remove the `VersionsDialog.tsx` entry)
- **Change:** as in Approach ("Version history").
- **Verification:** unit tests for the line classifier. Component tests: the current version is marked; Compare renders added and removed lines with their classes; a failed View, Compare or Restore shows an error and leaves the dialog usable; Restore asks first.

#### Step 6: End-to-end spec, docs and full checks
- **Status:** todo
- **Depends on:** 2, 3, 4, 5
- **Files:** `frontend/e2e/artifact-overlay.spec.ts` (modify: the drawer no longer overlays the composer on desktop), `frontend/e2e/artifact-actions.spec.ts` (create), `docs/frontend.md` (modify: Known gaps: drop "The file tree shows one level…" if it is no longer true, list the file actions that exist and the workspace-scope limit on version history), `frontend/README.md` (no change expected: it does not describe the panel; check and leave)
- **Change:** the new spec mocks the file-system endpoints, edits a file, tries to switch files, cancels, saves, renames it and compares two versions.
- **Verification:** both specs pass (`npm run e2e`, outside the merge gate; needs the dev server and backend). Then from `frontend/`: `npm run typecheck`, `npm run lint`, `npm run test`, `npm run build`; from the repo root `pytest tests` and `scripts/check.sh --frontend-only`.

### Tests
- Unit: `api/filesystem.test.ts`, `lib/diff-lines.test.ts`.
- Component: `ArtifactDrawer.test.tsx`, `ArtifactPanel.test.tsx`, `MoveFileDialog.test.tsx`, `VersionsDialog.test.tsx`.
- E2E: `e2e/artifact-overlay.spec.ts`, `e2e/artifact-actions.spec.ts`.
- Guards: `test/inline-style.test.ts`, `test/css-coverage.test.ts`.

### Risks and open questions
- **`disk:` entries** (files on disk under a workspace) accept content updates only; Rename and Move are disabled for them with a tooltip.
- **Every version endpoint requires `chat_id`** (`versions`, `version`, `current-version`, `restore`, `diff`), so version history cannot work for a file opened in the workspace scope: the Versions button is hidden there (it fails today). Making it work is a backend change.
- **`--right-sidebar-width` is also read by legacy rules;** the variable is removed on close so other pages are unaffected.
- **Shared file:** `ArtifactPanel.tsx` is also changed by MYAI-60 (`artifactsKey`), MYAI-63 (requested path) and MYAI-65 (workspace page usage).

### Success criteria
- [ ] Opening the drawer resizes the chat instead of covering it on desktop
- [ ] Selected row is never clipped
- [ ] Leaving a file with unsaved edits asks first
- [ ] Rename, move, new folder, delete folder, download and copy work
- [ ] Version history shows a diff and handles errors
- [ ] Checks and the specs pass
### Reviewer brief
- **Objective:** files panel beside the chat on desktop, no clipped selection, guarded unsaved edits, the common file actions, version history with a diff and error handling.
- **Decisions:** above 1024px the open drawer publishes `--right-sidebar-width` so `main` narrows (legacy rule); overlay kept at 1024px and below; compact tree scrolls and keeps the selection in view; `confirmDiscard` before switching, closing, creating or leaving edit mode with a dirty draft; rename and move through the existing `artifactsApi.update`; new `createDirectory`, `deleteDirectory`, `diff`, `currentVersion`; `restore` sends `workspace_id` in the query; "More" menu, New folder, folder menu, `MoveFileDialog`; `VersionsDialog` rebuilt on primitives with Compare (server diff rendered through `lib/diff-lines.ts`); Versions hidden in the workspace scope because every version endpoint requires `chat_id`.
- **Out of scope:** undo/redo beyond the editor, approve/suggest, autosave, live terminal and run file (MYAI-70), refresh during a turn and file links (MYAI-63), the workspace page (MYAI-65), backend changes.
- **Success criteria:** drawer resizes the chat on desktop; selection never clipped; unsaved edits ask first; rename, move, new folder, delete folder, download and copy work; version history shows a diff and handles errors; checks and specs pass.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- **Round 1:** validator FAIL (1 blocking, 6 minor). Judged FAIL after reading `backend/file_system/router.py`: `restore` and `diff` read `workspace_id` from the query only, and every version endpoint requires `chat_id`. Fixed: per-endpoint scope rule, `restore` corrected, Versions hidden in the workspace scope. Minors fixed: folder source for Move; CSS file listed for Step 4; `Menu` in point mode instead of the unused `ContextMenu`; rename and move reuse `update`; README check.
- **Round 2 (diff-scoped):** validator PASS (1 minor). Judged PASS. Fixed inline: version-call tests limited to the chat scope.

## Implementation notes
Branch bugfix/files-panel, base develop (autopilot batch item 16).
### Implementation progress
- [x] Step 1: `artifactsApi` diff, currentVersion, createDirectory, deleteDirectory; `restore` scope fix (+ api/filesystem.test.ts)
- [x] Step 2: ArtifactDrawer publishes `--right-sidebar-width` above 1024px (+ ArtifactDrawer.test.tsx)
- [x] Step 3: selected row scrolled into view, `confirmDiscard` (switch, close, new file), previous file kept while the next loads (+tests)
- [x] Step 4: More menu (Rename, Move, Download, Copy), New folder, Delete folder (right-click), MoveFileDialog, `folderPaths`/`parentFolder` (+tests)
- [x] Step 5: VersionsDialog rebuilt (current marked, View, Compare with current, Restore with confirm, errors), lib/diff-lines.ts (+tests); inline-style baseline entry removed; Versions hidden in workspace scope
- [x] Step 6: e2e/artifact-actions.spec.ts, docs/frontend.md "Files panel"
Deviations: the server's diff is two line lists (`added_lines`, `removed_lines`, stats), not unified text, so `lib/diff-lines.ts` turns those into rows (removed first, then added) with a summary instead of classifying unified-diff lines.
### Smoke test (2026-11-10)
check.sh --frontend-only: typecheck, lint, 388 tests, build pass; e2e artifact-actions + artifact-overlay 4/4 twice.
Live (1440px, real backend): drawer left 964, composer right 924, main right 964 and `--right-sidebar-width` 476px; last of 14 files selected stays inside the tree box; editing then switching asks, Cancel keeps file14 and the draft, Save works; rename, new folder, move into it, copy (clipboard text), download (renamed file name) work; deleting a non-empty folder shows the server's refusal; version history lists 2 versions, compare shows "1 added, 1 removed".

PR: https://github.com/archit342000/My-AI/pull/116, branch bugfix/files-panel, base develop

## Verification

### Acceptance review (2026-11-10)
Criteria ticked on the live and e2e results recorded in the PR's Testing section (checks run on throwaway backends during the autopilot run; scripts in `MYAI-66-evidence/`).
All criteria covered.

## Review history
### Round 1 - 2026-11-10
Verdict: Request changes (4 MAJOR). Single Haiku reviewer.
- R1-1 [MAJOR] current-version error masked - Fixed: alert and Compare disabled; test.
- R1-2 [MAJOR] the header files button closed the panel without asking - Fixed: panel publishes `artifactsDirty`, the header button confirms; test.
- R1-3 [MAJOR] restore left a stale draft - Fixed: opening the history is guarded (confirmDiscard), so no draft exists at restore; test.
- R1-4 [MAJOR] a 960px drawer could squeeze the chat to nothing beside it - Fixed: side by side the width is capped so the chat keeps 400px; test.
- R1-5 rename with "/" moved the file - Fixed (rejected with a message). R1-6 MoveFileDialog kept an old choice - Fixed (remounted per open). R1-7 selection in a collapsed folder - Fixed (ancestors opened). R1-8 tree focus outline clipped - Fixed (top padding). R1-9 folder delete not keyboard reachable - Fixed (Delete key, Shift+F10 position). R1-10 list/detail errors masked - Fixed (alerts). R1-11 diff summary wording - Fixed ("No differing lines"). R1-13 boundary tests - Fixed. R1-14 scrollIntoView stub hygiene - Fixed.
- R1-12 [MINOR] e2e coverage of move, restore and folder delete - Deferred: covered by component tests and the live check; spec covers drawer, guard, rename and compare.
- Found live after R1-3: after Save the editor handed the stale text back as a new draft, so the file looked unsaved (pre-existing); fixed by clearing the draft only after the saved content has loaded; test.
Resolution: check.sh passes (396 tests); e2e 4/4 twice; live V1-V5 re-run. Round 1 fixes were not re-reviewed.


## Log
- 2026-11-10: created
- 2026-11-10: added to epic MYAI-53
- 2026-11-10: plan validated, 2 rounds
- 2026-11-10: acceptance criteria reviewed against the recorded results (5 ticked, 0 left open)
- 2026-11-10: closed by the user after the PR merged into develop
