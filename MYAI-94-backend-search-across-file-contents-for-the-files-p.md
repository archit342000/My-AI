---
id: MYAI-94
title: "Backend: search across file contents for the Files panel"
status: in-progress
created: 2026-11-11
updated: 2026-11-11
links:
  conflicts_with: [MYAI-102]
  relates_to: [MYAI-93, MYAI-96]
---

## Description
The Files panel in the Console at Rest design searches file names and file contents and shows the matching line. The backend has no route for this: `backend/file_system/router.py` lists files and returns one file's content at a time, so the frontend can only search names, plus the contents of files it has already loaded. Found while planning MYAI-93 (frontend only; the frontend ships with the limited search until this exists).

Needed: a route under `/api/file_systems` that takes a chat or workspace scope and a query, searches the contents of that scope's files, and returns per match the file id, path, line number and the matching line (bounded result count, same access checks as the list route).

## Acceptance criteria
- [x] A scoped search route returns file id, path, line number and matching line for each hit, with a result limit
- [x] It enforces the same per-user and per-scope access as the existing file routes
- [x] Tests cover hits, no hits, the limit and a scope the caller may not read
- [x] `docs/standards/api.md` documents the route

## Plan
**Date:** 2026-11-11  **Status:** Validated

### Objective
Add a scoped content-search route so the Files panel can find text inside every file of a chat or workspace, not only names and already-opened files. Each hit returns file id, path, line number and the matching line, with a result limit and the same access rules as the list route.

### Context
- Requirement: ticket Description and Acceptance criteria. Planned against `develop` at 7dd16d3.
- Rules: `AGENTS.md` (config in `backend/config.py`, `db` from `backend.database`, `log_event`, no masked errors, README kept accurate); `docs/standards/api.md` (thin routes, `GET` read, `400` invalid input, `404` foreign scope, `{"error": ...}`, no `str(e)`; contract changes update `frontend/src/api/` in the same change); `docs/standards/testing.md` (1:1 tests, run dir then parents, env vars).
- Current behaviour:
  - `backend/file_system/router.py`: blueprint hook `require_fs_owner` checks every `chat_id`/`workspace_id` in query, body and URL (foreign or unknown is 404, non-string is 400). `list_file_systems_endpoint` (`GET ''`) builds the scope's file set: a chat's own files plus its workspace's files (prefixed `workspace/`), or a workspace's files (prefixed `workspace/`); a not-owned new chat lists nothing; neither id is 400.
  - `backend/file_system/manager.py`: `get_fs_file_content(file_system_id, chat_id, workspace_id)` reads current content; `grep_files` is the AI tool's grep (chat-only, regex option, per-file match lists with context), not the route's shape.
  - An FTS5 table `file_systems_search` exists (`backend/database/init_db.py`) but is optional (skipped when FTS5 is missing) and gives no line numbers.
  - Frontend: `frontend/src/api/filesystem.ts` `artifactsApi` has no search; the Files panel searches names and loaded contents locally (`frontend/src/features/artifacts/file-search.ts`).

### Approach
- New route `GET /api/file_systems/search?chat_id=|workspace_id=&q=&limit=` in `router.py`. Flask ranks the literal `/search` rule above the `/<path:file_system_id>` converter rule, so it does not collide with the get-file route; a test pins this.
- Logic in a new manager function `search_fs_contents(chat_id, workspace_id, query, limit)`: build the same file set as the list route (that set-building moves into a shared helper `_scope_file_systems` used by both, so paths match what the panel lists), read each file's current content with `get_fs_file_content`, scan line by line with a case-insensitive plain substring match (no regex: user input), stop at `limit` hits; `truncated` is true only when at least one more hit exists beyond `limit`. `search_fs_contents` is `async` (it awaits `get_fs_file_content`); `_scope_file_systems` is sync (DB reads only).
- Response: `{"results": [{"file_system_id", "path", "line_number", "line"}], "truncated": bool}`. `line` is cut to `FILE_SEARCH_MAX_LINE_CHARS` characters.
- Limits in `backend/config.py`: `FILE_SEARCH_DEFAULT_RESULTS` (50), `FILE_SEARCH_MAX_RESULTS` (200), `FILE_SEARCH_MAX_QUERY_CHARS` (200), `FILE_SEARCH_MAX_LINE_CHARS` (300). A `limit` above the max is clamped; non-integer or below 1 is 400. Empty or whitespace `q`, or `q` over the max, is 400.
- Access: the blueprint hook enforces ownership. The new endpoint joins `_MISSING_CHAT_OK_ENDPOINTS` in `router.py` (as `list_file_systems_endpoint` is), and follows the list route's rule for a chat that does not exist yet: the chat is dropped, a usable `workspace_id` is still searched, otherwise the result is empty (not 404), while another user's existing chat is still 404; 400 when neither id is given.
- Files whose content is `None` are skipped. An unexpected failure is logged with `log_event` and answers 500 `{"error": "Search failed"}`.
- Frontend contract: typed `artifactsApi.search(scope, q, limit?)` in `frontend/src/api/filesystem.ts` with a unit test. Wiring the Files panel to it is a follow-up (the ticket asks for the backend route).
- Rejected: FTS5 (optional table, no line numbers); reusing `grep_files` (chat-only, regex, different shape).

### Out of scope
- Using the route in the Files panel (`features/artifacts/FileBrowser.tsx`, `file-search.ts`): frontend follow-up.
- Searching old versions, binary content, or across scopes.
- Changing the AI `grep_files` tool.

### Steps
#### Step 1: Config limits
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/config.py` (modify): new `FILE_SEARCH_DEFAULT_RESULTS`, `FILE_SEARCH_MAX_RESULTS`, `FILE_SEARCH_MAX_QUERY_CHARS`, `FILE_SEARCH_MAX_LINE_CHARS`.
- **Change:** add the four values with the defaults above, following the file's `os.getenv` pattern.
- **Verification:** importing `backend.config` with the test env vars gives `FILE_SEARCH_MAX_RESULTS == 200`; config tests pass.

#### Step 2: Shared scope file set
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/file_system/manager.py` (modify): new `_scope_file_systems(chat_id, workspace_id)`; `backend/file_system/router.py` (modify): `list_file_systems_endpoint` uses it.
- **Change:** move the chat-plus-workspace / workspace-only set building (with the `workspace/` prefix) out of the list route into the helper, with no behaviour change.
- **Verification:** existing list tests in `backend/file_system/tests/test_router.py` pass unchanged; new helper tests in `test_manager.py` cover chat with workspace, chat without, workspace only.

#### Step 3: Search function
- **Status:** todo
- **Depends on:** 1, 2
- **Files:** `backend/file_system/manager.py` (modify): new `async def search_fs_contents(chat_id, workspace_id, query, limit)`.
- **Change:** iterate the scope's files, read content with each row's own `chat_id` and `workspace_id` (as the list route does), case-insensitive substring match per line, hits in file then line order, stop at `limit` with `truncated`, cut long lines, skip `None` content and the binary placeholder `get_fs_file_content` returns for binary disk files.
- **Verification:** new tests in `backend/file_system/tests/test_manager.py`: hits across files with correct line numbers and paths, no hits, case-insensitivity, limit and `truncated`, long line cut, unreadable and binary files skipped, a content hit in a workspace file found from a chat scope with the `workspace/` path. Route test in Step 4 adds: a not-yet-created chat with an owned workspace searches the workspace.

#### Step 4: Route
- **Status:** todo
- **Depends on:** 3
- **Files:** `backend/file_system/router.py` (modify): new `search_file_systems_endpoint` on `GET /search`.
- **Change:** add `"file_system.search_file_systems_endpoint"` to `_MISSING_CHAT_OK_ENDPOINTS`; validate `q` (400 when empty or too long) and `limit` (400 when not an integer or below 1, clamped when above the max); 400 without a scope; when the chat is not owned (`owns_chat` false, i.e. not created yet) drop it and search the `workspace_id` if one is given and not `"default"`, else return an empty result (the list route's rule); await `search_fs_contents` and return the shape above; on an unexpected exception `log_event("file_system_search_error", ...)` (import `log_event` from `backend.logging`, as `manager.py` does) and 500 with a fixed message.
- **Verification:** new tests in `backend/file_system/tests/test_router.py`: hits, no hits, limit clamp and invalid limit, empty and too-long query, missing scope, a not-yet-created chat gives an empty result, another user's chat and workspace are 404 with nothing read (added to the existing foreign-user parametrised table), `/search` is not treated as a file id.

#### Step 5: Frontend client
- **Status:** todo
- **Depends on:** 4
- **Files:** `frontend/src/api/filesystem.ts` (modify): `FileSearchHit` type and `artifactsApi.search`; `frontend/src/api/filesystem.test.ts` (modify).
- **Change:** typed GET using the existing `scopeQuery` plus `q` and optional `limit`, mapping fields like the other calls.
- **Verification:** `npm run typecheck` and the new `filesystem.test.ts` case (URL and mapping) pass.

#### Step 6: Docs
- **Status:** todo
- **Depends on:** 4
- **Files:** `docs/standards/api.md` (modify), `backend/file_system/README.md` (modify).
- **Change:** document the route (scope, `q`, `limit`, response, errors, limits) in api.md; mention `search_fs_contents` and the route in the README's Core Files table.
- **Verification:** `venv/bin/python -m pytest tests -q -p no:cacheprovider` (docs guardrails) passes.

### Tests
- Backend: `EMBEDDING_URL="http://mock" AI_URL="http://mock" AI_API_KEY="dummy" PYTHONPATH=. venv/bin/python -m pytest backend/file_system/tests`, then `backend` and `tests`; `venv/bin/ruff check .`.
- Frontend: in `frontend/`, `npm run typecheck`, `npm run lint`, `npm run test`.
- Gate: `scripts/check.sh`.

### Risks and open questions
- Reading every file per search is linear in the scope's total size. Fine at current sizes; an index can follow if it gets slow.
- Decision: case-insensitive plain text, no regex (assumption; matches the design's search box).

### Success criteria
- [ ] `GET /api/file_systems/search` returns file id, path, line number and line per hit, with a default and maximum limit and a `truncated` flag
- [ ] Another user's chat or workspace is 404 and nothing is read; missing scope, bad query or bad limit is 400
- [ ] Tests cover hits, no hits, the limit and a foreign scope
- [ ] `docs/standards/api.md` and `backend/file_system/README.md` describe the route
- [ ] `frontend/src/api/filesystem.ts` has the typed client call

### Reviewer brief
- Objective: `GET /api/file_systems/search` searches the current contents of a chat's or workspace's files and returns file id, path, line number and line per hit, with a default and maximum limit and a `truncated` flag.
- Decisions: logic in `manager.search_fs_contents` over a shared `_scope_file_systems` helper (same file set and `workspace/` paths as the list route); case-insensitive plain text, no regex; limits in `backend/config.py` (limit above max clamped, bad limit/query 400); ownership by the blueprint hook, with the list route's rule for a not-yet-created chat; binary and unreadable files skipped; typed client `artifactsApi.search`.
- Out of scope: wiring the Files panel to the route, old versions, the AI `grep_files` tool.
- Success: hits, no hits, limit and foreign scope tested; api.md and the file_system README document the route.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- Round 1: validator FAIL. Judged FAIL. Valid BLOCKING: the new route was not in `_MISSING_CHAT_OK_ENDPOINTS`, so a not-yet-created chat would be 404 (fixed: Approach Access, Step 4). Valid MINOR, fixed: clamp vs 400 wording; `search_fs_contents` is async and the helper sync; `log_event` import named; `truncated` defined. Disproved: "worktree is detached, not develop" (detached at develop's tip 7dd16d3, same code).
- Round 2 (diff-scoped): validator PASS. Judged PASS. Valid MINOR, fixed inline: content read with each row's own ids plus a workspace-file hit test; not-yet-created chat with a workspace follows the list route's rule (searches the workspace) plus a test; binary placeholder skipped plus a test.

## Implementation notes
### Autopilot run (2026-11-11)
- Mode: automatic (batch-autopilot, item 1/9)
- Branch: bugfix/file-content-search  PR base: develop  Starting commit: 32d33f73cd578e1a29080f9a12092caf1c36c073
- Dirty before start: none
- Work files: backend/config.py, backend/file_system/{manager,router,README.md}, tests, docs/standards/api.md, frontend/src/api/filesystem(.test).ts
- Counters: fix 0/10, review 1/5, re-verify 1
- Last completed stage: 6 ship  Next: none
- Hard blocker: none
- WIP commit: none

### Autopilot decisions (2026-11-11)
- Stage 1: plan already Validated in ticket; reused.
### Baseline (2026-11-11)
- backend/file_system/tests: 238 passed before changes.

### Implementation progress
- [x] Steps 1-6: config limits, `_scope_file_systems` (router.py), `search_fs_contents` (manager.py), `GET /search` route, `artifactsApi.search` + test, docs (api.md, file_system README). Branch bugfix/file-content-search.
- Deviation: `_scope_file_systems` lives in router.py (not manager.py) and `search_fs_contents(file_systems, query, limit)` takes the scope's rows: the existing list tests patch `router.db`, so the helper must use it to keep them unchanged.

### Smoke test (2026-11-11)
- file_system tests 252 pass; backend 1606 pass; tests/ 68 pass; ruff clean; frontend typecheck, lint, 1106 unit tests pass.
- Stage 5: resolve-review done inline by the author for ten small findings (all MINOR/NIT), not via the skill, to keep the batch moving; one rejected finding (R1-6) with evidence.
- Stage 2: `_scope_file_systems` in router.py and `search_fs_contents(file_systems, ...)` in manager.py (plan said manager helper): needed so existing list tests patching `router.db` pass unchanged.
- Verify: scenario V1 superseded by V1b (wrong file-order expectation in the harness).
PR: https://github.com/archit342000/My-AI/pull/124, branch bugfix/file-content-search, base develop

## Verification
### Verification plan (2026-11-11)
**Diff base:** 32d33f7. Light form (small change).

**Environment:** real Flask app (`app.app.run`) on 127.0.0.1:5311, `DATA_DIR`/`CHROMA_PATH` in a mktemp dir, `AUTH_PROVIDER=static`, `ADMIN_EMAIL=verify@test.io`; no model needed. Harness `scripts/verify94.py` (in the evidence folder) drives HTTP only, plus a sqlite insert of a chat/workspace owned by another user in the throwaway DB. Never touches backend/data. Teardown: kill recorded PID, rm temp dir.

| ID | Criterion | Scenario | Type | Files | Expected |
|----|-----------|----------|------|-------|----------|
| V1 | hits with id/path/line/line | create 2 files in a chat (POST), search a term present on several lines | happy | router.py, manager.py | 200, hits with file_system_id, path, line_number, line; case-insensitive; file then line order |
| V2 | workspace scope | files in a workspace, search by workspace_id | happy | router.py | paths prefixed `workspace/` |
| V3 | chat + its workspace | chat in workspace, search by chat_id | happy | router.py | both chat and workspace files found |
| V4 | no hits | term absent | edge | manager.py | 200 empty, truncated false |
| V5 | limit | limit=1, limit above max, limit=0, limit=abc | edge | router.py | 1 hit + truncated true; clamp to max; 400; 400 |
| V6 | validation | missing q, whitespace q, q of 201 chars, no scope | failure | router.py | 400 each |
| V7 | access | another user's chat and workspace | failure | router.py | 404, no content in body |
| V8 | unknown chat | chat id that does not exist | edge | router.py | 200 empty |
| V9 | long line + unicode | a 1000-char line and a unicode match | edge | manager.py | line cut to 300; unicode found |
| V10 | regression | list route and get-file route for the same scope; file_system tests | regression | router.py | list shows same paths; `/search` not treated as a file id; suite passes |
| V11 | logs | server log after the run | non-functional | | no tracebacks |

Scripts: `scripts/verify94.py`.
### Results (2026-11-11)
Verified at HEAD 32d33f7 plus uncommitted:
- backend/config.py 4d9accc77bfe5374bb6669fdbbeb2ac81e65ef72
- backend/file_system/README.md 8a0008e568f6b26a6d3be3e87b09e90d0beaab7a
- backend/file_system/manager.py f176ac22a66d7a15919bfa9dd7e4a25771ad7aa3
- backend/file_system/router.py a1b1a56591562a6559f81b3577dad5a93450c51b
- backend/file_system/tests/test_manager.py f3775c51da031d2c9d7161f5c7c22370aace5131
- backend/file_system/tests/test_router.py cfd57a7595586ee4551f5ad453c73b2fac6aa0d6
- docs/standards/api.md 99caffcfff8237cce6c2dcd32b38a2eb486a9c3f
- frontend/src/api/filesystem.test.ts eb57b6cffe69aee813263f1cbd0843e64ed7d627
- frontend/src/api/filesystem.ts 0f2e4ba29e44a53f8f7e6db6f585ec481f47affb

Evidence: `~/.claude/tickets/My-AI/MYAI-94-evidence/` (results.txt, backend logs, scripts/). Real app, throwaway data dir, torn down (no process, port or dir left).

| ID | Status | Note |
|----|--------|------|
| V1 | superseded by V1b | harness expected an alphabetical file order that neither the plan nor the list route promises; V1 never changed in place (dated note, 2026-11-11) |
| V1b | PASS | hits grouped by file in the list route's order, lines ascending, case-insensitive match, shape complete |
| V2, V3 | PASS | workspace paths prefixed `workspace/`; chat scope includes its workspace files |
| V4, V5a-c, V6 | PASS | no hits; limit, clamp and 400s |
| V7 | PASS | another user's chat and workspace: 404, no secret in body |
| V8, V9, V10 | PASS | unknown chat empty 200; 300-char cut and unicode; list route and file-id route unaffected |
| V11 | PASS | no traceback in server log |
Regression: file_system tests 252, backend 1606, tests/ 68, frontend 1106 all pass.
Verdict: verified (12 PASS, 0 FAIL, 0 BLOCKED; V1 superseded).

## Review history
### Round 1 - 2026-11-11
Verdict: Approve with comments (one Haiku reviewer, working tree vs 32d33f7, requirement available). 10 findings, none BLOCKER/MAJOR.
- R1-1 [MINOR] manager.py:267 - 300-char cut can drop the match - Static - Fixed (line starts at the match when it lies beyond the cut; test)
- R1-2 [MINOR] manager.py:258 - splitlines numbers lines differently from the editor - Static - Fixed (split on \\n, trim CR; test)
- R1-3 [MINOR] manager.py:248 - every file read per request - Static - Fixed by documenting the cost in api.md (index is a follow-up)
- R1-4 [MINOR] router.py:99, README:16 - docs omit the search route as missing-chat-ok - Static - Fixed
- R1-5 [NIT] manager.py:252 - dead directory guard - Static - Fixed (removed)
- R1-6 [NIT] router.py:287 - unused import in list route - Rejected: still used at the `chat_workspace_id` lookup further down the route
- R1-7 [NIT] router.py:571 - q trimmed silently - Static - Fixed (documented)
- R1-8 [NIT] router.py:581 - default limit not clamped - Static - Fixed
- R1-9 [NIT] test_router.py:935 - misleading test name - Static - Fixed (renamed)
- R1-10 [NIT] manager.py:256 - startswith marker skips real text files - Static - Fixed (exact placeholder compare; test)
Resolution done inline by the author (small fixes), no separate resolve-review run. Re-verified after the fixes: harness 12 PASS (V1 superseded), file_system+tests 322 pass, ruff clean, typecheck clean.

## Log
- 2026-11-11: created (backend gap found while planning MYAI-93, as the user asked)
- 2026-11-11: linked relates_to MYAI-93 (the Files panel search uses it when it exists)
- 2026-11-11: linked relates_to MYAI-96 (other backend gaps found with the design work)
- 2026-11-11: plan validated, 2 rounds
- 2026-11-11: linked conflicts_with MYAI-102 (both change workspace file paths)
- 2026-11-11: autopilot started (batch-autopilot)
- 2026-11-11: implemented, smoke tests pass
- 2026-11-11: verify: 12 PASS, 0 FAIL (V1 superseded by V1b), fix 0/10
- 2026-11-11: review round 1 Approve with comments; all kept findings fixed; re-verified (12 PASS)
- 2026-11-11: batch-autopilot: shipped, base develop (PR 124)
