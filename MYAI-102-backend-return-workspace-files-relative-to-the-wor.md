---
id: MYAI-102
title: "Backend: return workspace files relative to the workspace root"
status: in-progress
created: 2026-11-11
updated: 2026-11-11
links:
  conflicts_with: [MYAI-94, MYAI-95]
  split_from: [MYAI-96]
---

## Description
Item 6 of MYAI-96. Files in a workspace come back with a leading `workspace/` folder, so the file tree has one extra level the design does not have and the person never asked for.

Needed: return workspace files relative to the workspace's own root, or state which leading folder is the root so the frontend can hide it safely. MYAI-94 and MYAI-95 use the same paths, so this should land after them.

## Acceptance criteria
- [x] Workspace files are shown without the extra `workspace` level
- [x] Chat views that mix chat and workspace files still tell them apart
- [x] Existing file routes, search (MYAI-94) and run/versions (MYAI-95) keep working
- [x] `docs/standards/api.md` and `frontend/src/api/` types are updated in the same change
- [x] Frontend follow-up noted: drop the extra level in `features/artifacts/FileTree.tsx`

## Plan
**Date:** 2026-11-11  **Status:** Validated

### Objective
Stop the Files panel on a workspace page from showing an extra `workspace` folder level, by having the server say which leading folder is the workspace root and the frontend hide it in the tree, while every path the server accepts and returns stays as it is.

### Context
- Requirement: ticket Description and Acceptance criteria; the Description allows either workspace-relative paths or "say which leading folder is the root so the frontend can hide it safely". Planned against `develop` at 7dd16d3.
- Rules: `AGENTS.md`; `docs/standards/api.md` (changing a response shape, path or `localStorage` key is a breaking change: update `frontend/src/api/` and the legacy UI in the same change; this change adds a `root` key to the list response, so both are checked: the React client is updated in Step 2, and the legacy UI reads the list body in `static/script.js` `fetchFileSystems` but takes only `data.file_systems`, which is unchanged, so the extra key breaks nothing there (recorded as an explicit exception to the rule's "update the legacy UI" part: no legacy code reads or needs the new key); decision: the legacy UI (served at `/legacy/`, removed in a later release per `docs/architecture.md`) keeps showing the `workspace` level as it does today, and the design's Files panel is the React one); `docs/standards/frontend.md`; `docs/standards/testing.md`.
- Current behaviour:
  - `backend/file_system/router.py` `list_file_systems_endpoint`: in a chat scope, the chat's own files are plain paths and its workspace's files get a `workspace/` prefix (the mount that tells them apart, used by the AI's file tools and by `backend/file_system/utils.py` `resolve_owner_and_physical_path`); in a workspace-only scope every file also gets `workspace/`, disk-only entries get ids `disk:workspace/<rel>`, and a `workspace` directory entry is always added. Other routes return or accept the same prefixed paths (`get_file_system_endpoint`, `update_file_system_endpoint`, `backend/file_system/manager.py` `get_all_file_systems_for_chat`).
  - `frontend/src/features/artifacts/artifact-tree.ts` `buildTree(items, { hidePlaceholder })` builds the tree from full paths; `hidePlaceholder` drops only an empty `workspace` folder. `FileBrowser.tsx` passes `hidePlaceholder: Boolean(scope.workspaceId)`, so a workspace with files shows them under `workspace/`.
  - MYAI-94 (search) and MYAI-95 (run and versions) use the same prefixed paths.

### Approach
- Keep every path and id unchanged (no breaking change, nothing for MYAI-94, MYAI-95 or the AI tools to follow).
- Add one field to the list response: `"root": "workspace/"` in a workspace-only scope, `"root": ""` in a chat scope (where `workspace/` is a real mount the person needs to see).
- Frontend: `artifactsApi.list` returns the root with the files; `buildTree` gains an option `root` that strips that prefix when nesting (the root's own directory entry is dropped) while each node keeps its full `path`, so opening, renaming, running and saving still send the server's paths. `hidePlaceholder` is replaced by `root`.
- Rejected: returning workspace-relative paths (changes ids such as `disk:workspace/...`, every route that echoes a path, and the AI's mount, for a display problem).

### Out of scope
- Changing the `workspace/` mount in chat scope or any path the AI tools use.
- Hiding the level in the legacy UI (`static/script.js`, `static/js/file-system-ui.js`); it is unaffected by the extra key and is planned for removal in a later release.
- Other places that print a path (editor title, run card); they keep the full path unless they already show a file name only.

### Steps
#### Step 1: Root in the list response
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/file_system/router.py` (modify): `list_file_systems_endpoint`; `backend/file_system/tests/test_router.py` (modify).
- **Change:** add `root` to every success response of the route, including the early empty answer for a not-yet-created chat (`root: ""`) and the fall-through to the workspace branch (`root: "workspace/"`).
- **Verification:** tests: workspace-only listing has `root == "workspace/"` and unchanged paths and ids; chat listing (with and without a workspace) has `root == ""`; the not-yet-created-chat empty listing has `root == ""`.

#### Step 2: Client returns the root
- **Status:** todo
- **Depends on:** 1
- **Files:** `frontend/src/api/filesystem.ts` (modify): `artifactsApi.list` result type and mapping; `frontend/src/features/artifacts/useChatHasNoFiles.ts` and `FileBrowser.tsx` (modify: read `.files`); `frontend/src/api/filesystem.test.ts`, `frontend/src/features/artifacts/useChatHasNoFiles.test.tsx` (modify).
- **Change:** return `{ files, root }`, with `root` defaulting to `""` when absent (older server).
- **Verification:** `npm run typecheck` passes; `filesystem.test.ts` (whose list stub returns `{ file_systems: [] }`) asserts the new `{ files, root }` result for both a present and an absent `root`.

#### Step 3: Tree hides the root level
- **Status:** todo
- **Depends on:** 2
- **Files:** `frontend/src/features/artifacts/artifact-tree.ts` (modify): `BuildTreeOptions.root` replacing `hidePlaceholder`, `buildTree`; `frontend/src/features/artifacts/FileBrowser.tsx` (modify): pass the listed root; `frontend/src/features/artifacts/artifact-tree.test.ts`, `ArtifactPanel.test.tsx` (modify).
- **Change:** nest by the path with `root` removed, skip the root directory entry, keep each node's full `path`.
- **Verification:** tests: with `root: "workspace/"`, `workspace/notes/a.md` shows as `notes > a.md` and its node path is still `workspace/notes/a.md`; the root directory entry alone gives an empty tree; with `root: ""` a chat's `workspace` folder is still shown; opening a file in the panel requests the full path.

#### Step 4: Docs
- **Status:** todo
- **Depends on:** 3
- **Files:** `docs/standards/api.md` (modify), `backend/file_system/README.md` (modify), `docs/frontend.md` (modify, Files panel lines).
- **Change:** document `root` and that the panel hides it; keep `docs/frontend.md` within its line limit. Record in Implementation notes that the ticket's frontend follow-up (dropping the extra level) is done here in `artifact-tree.ts`/`FileBrowser.tsx`, which is where the tree is built (`FileTree.tsx` only draws the nodes and needs no change).
- **Verification:** `EMBEDDING_URL="http://mock" AI_URL="http://mock" AI_API_KEY="dummy" PYTHONPATH=. venv/bin/python -m pytest tests -q -p no:cacheprovider` passes.

### Tests
- Backend: `EMBEDDING_URL="http://mock" AI_URL="http://mock" AI_API_KEY="dummy" PYTHONPATH=. venv/bin/python -m pytest backend/file_system/tests`, then `backend` and `tests`; `venv/bin/ruff check .`.
- Frontend: in `frontend/`, `npm run typecheck`, `npm run lint`, `npm run test`; `npm run e2e` for `e2e/artifact-actions.spec.ts` and `e2e/mobile-layout.spec.ts` (they mock the list body as `{ file_systems: ... }` with no `root`, which the client treats as `""`, so they should pass unchanged; the root-hiding path is covered by the unit tests in Step 3) and `npm run e2e:stack`.
- Gate: `scripts/check.sh`.

### Risks and open questions
- MYAI-94's planned `_scope_file_systems` helper refactors the same list route; whichever lands second merges the `root` field in (link `conflicts_with` kept).
- Decision: chosen the "say which folder is the root" option from the Description, not relative paths (assumption: smallest change that removes the extra level without a breaking change).

### Success criteria
- [ ] On a workspace page the Files panel shows files without the `workspace` level
- [ ] In a chat, the `workspace` folder still separates workspace files from chat files
- [ ] All existing file routes, MYAI-94 search paths and MYAI-95 run/version paths are unchanged
- [ ] `docs/standards/api.md` and `frontend/src/api/` are updated in the same change

### Reviewer brief
- Objective: the Files panel on a workspace page shows files without the extra `workspace` folder, with every server path and id unchanged.
- Decisions: the list route adds `root` (`"workspace/"` in a workspace-only scope, `""` otherwise, on every success answer); `artifactsApi.list` returns `{ files, root }` (absent root is `""`); `buildTree`'s `root` option replaces `hidePlaceholder`, nests without the root while nodes keep full paths; the legacy UI reads only `file_systems` and is left as is (explicit exception, recorded); the chat-scope `workspace/` mount stays.
- Out of scope: the mount and AI tool paths; other path displays; the legacy UI's display.
- Success: no extra level on a workspace page, chat still separates workspace files, all routes and MYAI-94/95 paths unchanged, api.md and frontend/src/api updated.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- Round 1: validator FAIL. Judged FAIL. Valid BLOCKING: the plan claimed an additive-field exemption that `docs/standards/api.md` does not have and ignored the legacy UI (fixed in round 2 and 3). Valid MINOR, fixed: the FileTree follow-up recorded (done in `artifact-tree.ts`); both `artifactsApi.list` callers named; `root` on the early empty answer; e2e specs named.
- Round 2 (diff-scoped): validator FAIL. Judged FAIL. Valid BLOCKING: the Context wrongly said the legacy UI never reads the list body (`static/script.js` `fetchFileSystems` does, reading only `data.file_systems`); corrected and the decision recorded. Valid MINOR, fixed: the e2e specs that mock the list body; Step 2's test expectation.
- Round 3 (diff-scoped): validator PASS. Judged PASS. Valid MINOR, fixed inline: the legacy-UI decision worded as an explicit exception; "planned for removal in a later release".

## Implementation notes
### Autopilot run (2026-11-11)
- Mode: automatic (batch-autopilot, item 7/9)
- Branch: feature/workspace-files-root  PR base: develop  Starting commit: 32d33f73cd578e1a29080f9a12092caf1c36c073
- Dirty before start: none
- Work files: none yet
- Counters: fix 0/10, review 1/5, re-verify 0
- Last completed stage: 5 review+resolve (1 iteration)  Next: 6 ship
- Hard blocker: none
- WIP commit: none

### Autopilot decisions (2026-11-11)
- Stage 1: plan already Validated in ticket; reused.
### Baseline (2026-11-11)
- backend/file_system/tests: 238 passed before changes.

### Implementation progress
- [x] Step 1: list route returns `root` (`workspace/` for a workspace-only scope, `""` otherwise, also on the early empty answer) - router.py + tests
- [x] Step 2: `artifactsApi.list` keeps returning the array and attaches `root` to it (`ArtifactList = Artifact[] & { root?: string }`, `""` when the server sends none)
- [x] Step 3: `buildTree({ root })` replaces `hidePlaceholder`: the root folder is the top of the tree, its own directory entry is dropped, nodes keep full paths; FileBrowser passes the listed root; tests (artifact-tree, ArtifactPanel, filesystem)
- [x] Step 4: docs (api.md, file_system README, frontend.md without net lines). The ticket's follow-up (drop the extra level) is done in `artifact-tree.ts`/`FileBrowser.tsx`; `FileTree.tsx` only draws nodes. Legacy UI check: `static/script.js` `fetchFileSystems` takes only `data.file_systems`, so the extra key breaks nothing; the legacy UI keeps the `workspace` level (explicit exception in the plan).
- Deviation: the plan said `artifactsApi.list` returns `{ files, root }`; it returns the array with `root` attached instead, so the ~35 existing mocks and cache consumers of the array keep working unchanged.

### Smoke test (2026-11-11)
- backend + tests 1664 pass; frontend typecheck, lint, 1110 unit tests; ruff clean.
- Stage 5: resolve-review done inline by the author (not via the skill). Follow-up suggested (pre-existing, out of scope): PATCH rename/move of a workspace file with only workspace_id answers 500 (`resolve_owner_and_physical_path` raises for the stored `workspace/` path), so the Rename or move dialog cannot work on a workspace page until that is fixed.
PR: https://github.com/archit342000/My-AI/pull/130, branch feature/workspace-files-root, base develop

## Verification
### Verification plan (2026-11-11)
**Diff base:** develop tip. Full form (API response shape and a visible UI change).

**Environment:** real Flask backend on a temp data dir (port 5320, static auth, the rebuilt React `dist`), scripted model stub on 5321 only so the app loads; API checks by `scripts/verify102.py` (HTTP only); UI checks in the in-app browser against the same backend. Never touches backend/data. Teardown: kill both, rm the temp dir, close the browser tab, check ports.

| ID | Criterion | Scenario | Type | Files | Expected |
|----|-----------|----------|------|-------|----------|
| A1 | root on a workspace list | workspace with a root file and a folder file; GET list by workspace_id | happy | router.py | `root == "workspace/"`, file paths still `workspace/...`, ids unchanged |
| A2 | chat list keeps the mount | chat in that workspace with its own file; GET list by chat_id | happy | router.py | `root == ""`, own file plain, workspace files `workspace/...` |
| A3 | unknown chat | GET list for a chat that does not exist | edge | router.py | empty list, `root == ""` |
| A4 | existing routes unchanged | GET one workspace file by id with workspace_id; PATCH rename keeps working | regression | | same paths and content as before |
| U1 | no extra level on the workspace page | open /workspace/<id> Files section | happy | artifact-tree.ts, FileBrowser.tsx | top level shows the folder and the root file directly, no `workspace` folder |
| U2 | full path used | open a file in the folder | happy | | its content loads (server got the full path); file name and path shown correctly |
| U3 | chat view keeps the mount | open the chat's Files panel | regression | | a `workspace` folder separates workspace files from the chat's own |
| U4 | empty workspace | a workspace with no files | edge | | the panel's empty state, no stray `workspace` folder |
| R1 | no server or console errors | backend log, browser console | non-functional | | none |

Scripts: `scripts/stub.mjs`, `scripts/start_backend2.sh`, `scripts/verify102.py`, `scripts/run_all.sh`.
### Results (2026-11-11)
Verified at HEAD 32d33f7 plus uncommitted:
- backend/file_system/README.md 26a4e9aa851295c8221d45f6e2b949e437b911d7
- backend/file_system/router.py 7c8babe11fc2d8eff01b3e2af4a161986bc7f863
- backend/file_system/tests/test_router.py 3398facd04eddc9a8ef2ab88d0c7ac17226cf3f7
- docs/frontend.md d416338ec0eff86bd90515bf44c250ee668c02d5
- docs/standards/api.md bb4b9a8bc8703aadbad7df1b512484c2e54f233b
- frontend/src/api/filesystem.test.ts ef592b0ae9c33f60602ee9779ed6489f73fd7900
- frontend/src/api/filesystem.ts 296aee40b12d84a9e1f7e83bf18505d826d3c6dc
- frontend/src/features/artifacts/ArtifactPanel.test.tsx 11583465cc54ff6f0cfd87fa15f52037dcc57dd9
- frontend/src/features/artifacts/FileBrowser.tsx 88e1c550398330aac7b3e9bd76cb5ad6fa39bd6e
- frontend/src/features/artifacts/artifact-tree.test.ts d2abaae8793487cd469eb8f05ca6b56bf996c6b1
- frontend/src/features/artifacts/artifact-tree.ts 6a885f61c3fbdf91a27728cdb205f4331de5cba9

Evidence: `~/.claude/tickets/My-AI/MYAI-102-evidence/` (results-api.txt, backend.log, stub.log, scripts/). Real backend with the rebuilt React dist on a temp data dir; UI checked in the in-app browser; torn down (ports free, dir removed). The first A1/A2 run hit a harness bug (the list also holds the disk-only `workspace/notes` directory entry; the filter now skips directory entries) and passed after the fix.

| ID | Status |
|----|--------|
| A1 | PASS (workspace list: `root` is `workspace/`, file paths and ids unchanged) |
| A2 | PASS (chat list: `root` empty, own file plain, workspace files under `workspace/`) |
| A3 | PASS (unknown chat: empty list, empty root) |
| A4a | PASS (a workspace file is still fetched by id) |
| A4b | NOT RUN as a pass: renaming a workspace file by PATCH with only `workspace_id` answered 500 (`ValueError: The 'workspace/' directory is reserved...` in `resolve_owner_and_physical_path`). This is outside this change (my diff touches only the list route, `git diff origin/develop -- backend/file_system/router.py`) and is a pre-existing defect, left as a suggested follow-up; the scenario was dropped from the harness |
| U1 | PASS (workspace page: the tree shows `notes` (1) with `plan.md` and `readme.md` at the top, no `workspace` level) |
| U2 | PASS (opening plan.md loaded its content; the request used the full server path) |
| U3 | PASS (chat Files panel: a `workspace` folder holds notes/plan.md and readme.md, `own.md` sits beside it) |
| U4 | PASS (empty workspace: `No files yet` empty state, no stray folder) |
| R1 | PASS with notes: the only 404s are fonts and favicon of the throwaway build (not from this change); the only traceback is the pre-existing rename 500 above |
Regression: backend+tests 1664, frontend 1110 pass.
Verdict: verified (9 PASS, 0 FAIL, 1 not verified because of a pre-existing defect).

## Review history
### Round 1 - 2026-11-11
Verdict: Request changes (2 MAJOR) -> after resolution Approve. One Haiku reviewer, working tree vs develop. 4 findings.
- R1-1 [MAJOR] FileBrowser.tsx:390 - the rename dialog for a file at the top of a workspace started on the hidden `workspace` folder, which is not an option - Static - Fixed (`folderInRoot` maps the hidden root to Top level; test fails without the fix)
- R1-2 [MAJOR] WorkspacePage.test.tsx - the empty-workspace test no longer tested the new contract - Static - Fixed (mock carries the root; waits for the real empty state)
- R1-3 [MINOR] attaching `root` to the array defeats React Query's structural sharing - Static - Fixed (`fetchArtifactList` returns a plain `{ files, root }` object for the query cache, built from `artifactsApi.list`, so existing mocks still work; consumers and one test updated)
- R1-4 [MINOR] doc said an unknown chat always has an empty root - Fixed (a new chat sent with an owned workspace is listed as that workspace, with `workspace/`)
Resolved inline by the author. Re-verified by unit tests (frontend 1112, backend+tests 1664, typecheck, lint, ruff). The live UI check was not re-run after this fix.

## Log
- 2026-11-11: created (split from MYAI-96 at the user's request)
- 2026-11-11: linked conflicts_with MYAI-94
- 2026-11-11: linked conflicts_with MYAI-95
- 2026-11-11: linked split_from MYAI-96
- 2026-11-11: plan validated, 3 rounds
- 2026-11-11: autopilot started (batch-autopilot)
- 2026-11-11: implemented, smoke tests pass
- 2026-11-11: verify: 9 PASS, 0 FAIL (rename of a workspace file 500s: pre-existing, noted), fix 0/10
- 2026-11-11: review round 1 resolved (4 fixed); unit re-verified, live UI not re-run
- 2026-11-11: batch-autopilot: shipped, base develop (https://github.com/archit342000/My-AI/pull/130)
