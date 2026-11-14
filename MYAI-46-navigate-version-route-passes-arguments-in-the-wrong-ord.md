---
id: MYAI-46
title: "navigate-version route passes arguments in the wrong order"
status: done
created: 2026-11-09
updated: 2026-11-10
links:
  conflicts_with: [MYAI-37]
  relates_to: [MYAI-32, MYAI-37]
---

## Description
Found while planning MYAI-37. `POST /api/file_systems/<id>/navigate-version` (`backend/file_system/router.py:1025`) calls `navigate_file_system_version(file_system_id, chat_id, version_number)`, but the function is defined as `navigate_file_system_version(chat_id, file_system_id, version_number)` (`backend/file_system/manager.py:790`). The chat id and file-system id are swapped, so the route can't succeed.

## Acceptance criteria
- [x] The route passes the arguments in the order the manager defines (keyword arguments preferred)
- [x] A route test navigates to a version and checks the result; a regression test fails without the fix
- [x] Tests pass and `ruff check .` is clean

## Plan
**Date:** 2026-11-09  **Status:** Validated

### Objective
Make `POST /api/file_systems/<id>/navigate-version` pass the chat id and file-system id to `navigate_file_system_version` in the right order, with a test that would fail without the fix.

### Context
- **Route:** `navigate_to_version_endpoint` (`backend/file_system/router.py:1014-1026`) calls `navigate_file_system_version(file_system_id, chat_id, version_number)`.
- **Manager:** the function is `navigate_file_system_version(chat_id, file_system_id, version_number)` (`backend/file_system/manager.py:790`), so the ids are swapped and the meta lookup fails.
- **Existing tests:**
  - `backend/file_system/tests/test_router.py:368-405` mocks the manager function and only checks the 200, so it misses the swap.
  - `backend/file_system/tests/test_manager.py:293` calls the manager directly in the right order.
- No frontend calls the route today (a grep of `frontend/src` and `static/js`), so nothing else depends on the bug.
- **Siblings that touch this file:** MYAI-22 (`read_json_object`) and MYAI-37 (owner hook); whichever lands first, rebase the other.
- **Rules:** `docs/standards/testing.md` (a regression test that fails without the fix).

### Approach
Call the manager with keyword arguments (`chat_id=`, `file_system_id=`, `version_number=`), so the order can't drift again.
- Rejected: reordering the positional arguments, which would be just as easy to break again.

### Out of scope
Other file-system routes; adding a UI for version navigation.

### Steps
#### Step 1: Fix the call
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/file_system/router.py` (modify): `navigate_to_version_endpoint`.
- **Change:** as in Approach.
- **Verification:** reading the diff shows the call uses keywords matching `manager.py:790`; Step 2's test proves it.

#### Step 2: Regression test
- **Status:** todo
- **Depends on:** 1
- **Files:** `backend/file_system/tests/test_router.py` (modify).
- **Change:** a focused test, `test_navigate_version_passes_ids_in_order`, that posts `{"chat_id": "c1", "version_number": 2}` to `/api/file_system/fs1/navigate-version` (the test app's prefix, `test_router.py:9-13`; production uses `/api/file_systems`). The existing `test_navigate_to_version_endpoint` stub (line 431) is kept for the coverage mapping. It asserts the mocked manager was awaited once with `chat_id="c1", file_system_id="fs1", version_number=2`, and that the route returns the manager's result. The existing combined test keeps its 200 check.
- **Verification:** the new test fails against the old positional call and passes with the fix; `venv/bin/python -m pytest backend/file_system` with the env from `docs/standards/testing.md`.

#### Step 3: Full checks
- **Status:** todo
- **Depends on:** 2
- **Files:** none.
- **Change:** none.
- **Verification:** with the env from `docs/standards/testing.md` (`EMBEDDING_URL`, `AI_URL`, `AI_API_KEY`, `PYTHONPATH=.`): `venv/bin/python -m pytest backend` and `venv/bin/python -m ruff check .`. If `venv/` is missing, create it first (`python3.12 -m venv venv && venv/bin/pip install -r requirements.txt -r requirements-dev.txt`).

### Tests
As in Step 2.

### Risks and open questions
None.

### Success criteria
- [x] The route passes the arguments by keyword, in the manager's order.
- [x] A regression test fails without the fix and passes with it.
- [x] Tests pass and `ruff check .` is clean.

### Reviewer brief
- **Objective:** fix the swapped ids in the navigate-version route.
- **Key decisions:** call `navigate_file_system_version` with keyword arguments; a regression test asserts the awaited keywords. Rebase against MYAI-22 or MYAI-37, whichever lands first.
- **Out of scope:** other file-system routes, a UI for version navigation.
- **Success criteria:** as listed in the Plan.

The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- **Round 1:** the validator returned PASS (0 BLOCKING, 5 MINOR). My judgement: PASS. All five MINOR issues fixed: the test URL prefix; the env for the full checks; Step 1 verified by reading the diff; the coverage stub kept; how to create `venv/` if missing.

## Implementation notes
### Autopilot run (2026-11-09)
- Mode: automatic (batch-autopilot item 3/13)
- Branch: bugfix/navigate-version-argument-order  PR base: develop  Starting commit: cf5fc06f59f243df9739303928760952ee271748
- Dirty before start: none
- Work files: backend/file_system/router.py, backend/file_system/tests/test_router.py
- Counters: fix 0/10, review 1/5, re-verify 0
- Last completed stage: 5 review (clean)  Next: done (shipped)
- Hard blocker: none
- WIP commit: none

### Autopilot decisions (2026-11-09)
- Plan already validated; stage 1 skipped.

### Baseline (2026-11-09)
`pytest backend/file_system`: 165 passed. `pytest backend`: 10 failed (async-plugin: test_cache_system x2, test_research_utils x2, test_code_executor x6), rest pass.

### Implementation progress
- [x] Step 1: Fix the call - backend/file_system/router.py (keyword arguments)
- [x] Step 2: Regression test - backend/file_system/tests/test_router.py `test_navigate_version_passes_ids_in_order` (failed before the fix, passes after)
- [x] Step 3: Full checks
- Branch: bugfix/navigate-version-argument-order

### Smoke test (2026-11-09)
`pytest backend/file_system`: 166 passed. `pytest backend tests`: 10 failed (baseline), 1200 passed. `ruff check .`: clean.

PR: https://github.com/archit342000/My-AI/pull/86, branch bugfix/navigate-version-argument-order, base develop

## Verification

### Verification plan and results (2026-11-09, light form)
Real app via Flask test client on throwaway DATA_DIR (/tmp, removed). Script: `MYAI-46-evidence/scripts/drive.py`; outputs `live-output.txt` (fixed) and `live-output-before-fix.txt` (origin/develop in a temporary worktree, removed).
| ID | Criterion | Scenario | Status |
|----|-----------|----------|--------|
| V1 | route passes ids in the manager's order | create file, edit to v2, POST navigate-version v1 -> 200 `{"success": true, "version_number": 1, "content": "v1 text"}`; current-version 1; raw "v1 text" | PASS |
| V2 | regression proof | same script on origin/develop: navigate returns `{"error": "FileSystem not found.", "success": false}` | PASS (fails before, works after) |
| V3 | route test | `test_navigate_version_passes_ids_in_order` fails on the old call, passes with the fix | PASS |
| V4 | regression | `pytest backend` baseline failures only; ruff clean | PASS |
Verdict: verified (4/4).

## Review history

### Round 1 - 2026-11-09
Verdict: Approve with comments. Scope: origin/develop..working tree, 2 files, 1 Haiku reviewer.
- R1-1 [MINOR] test_router.py:436 - mock without spec only records call shape - Static - Fixed: `autospec=True`; re-checked the test still fails on the old positional call
- R1-2 [NIT] router.py:1042 - 127-character line - Static - Fixed: wrapped
- R1-3 [MINOR] test_router.py:431 - placeholder stub kept beside the new test - Rejected: the validated Plan keeps the coverage stub and adds a focused test (Step 2)
Resolution: 2 Fixed, 1 Rejected; tests/ruff green; only tests and formatting changed (no re-verify needed). Review loop clean (1/5).

## Log
- 2026-11-09: created (found during MYAI-37 planning)
- 2026-11-09: linked relates_to MYAI-37 (found during MYAI-37 planning)
- 2026-11-09: linked conflicts_with MYAI-37 (both edit backend/file_system/router.py)
- 2026-11-09: plan validated, 1 round
- 2026-11-09: linked relates_to MYAI-32 (follow-up found during the epic)
- 2026-11-09: autopilot started (batch)
- 2026-11-09: implemented, smoke tests pass (baseline failures only)
- 2026-11-09: verified 4 PASS, 0 FAIL
- 2026-11-09: review round 1: Approve with comments; resolved
- 2026-11-09: PR opened: https://github.com/archit342000/My-AI/pull/86 (base develop). batch-autopilot: shipped
- 2026-11-10: closed (merged into develop via the PR recorded in Implementation notes; deployed to myai.architanand.dev)
