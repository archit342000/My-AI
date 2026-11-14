---
id: MYAI-45
title: "read_file tool is unregistered and never awaits RAG retrieval"
status: done
created: 2026-11-09
updated: 2026-11-10
links:
  relates_to: [MYAI-32, MYAI-37]
---

## Description
Found while planning MYAI-37. `read_file` in `backend/tools/files.py` isn't referenced by any tool catalog spec or registry mapping, so the model can't call it. It's also broken: line 44 calls the async `FileRAG.retrieve_for_file` (`backend/rag/file_rag.py:109`) without `await`, so the query path gets a coroutine and always fails into its error branch. Only `backend/tools/tests/test_files.py`, `backend/tools/README.md:20` and a comment in `backend/config.py:290` refer to it.

Decide whether to remove it (with its tests and doc references) or register and fix it. If it's kept, it needs MYAI-37's `file_for_chat` ownership check.

## Acceptance criteria
- [x] `read_file` is either removed, with its tests and references, or registered, awaited correctly and owner-checked
- [x] Tests pass and `ruff check .` is clean

## Plan
**Date:** 2026-11-09  **Status:** Validated

### Objective
Remove the dead `read_file` tool. No catalog spec registers it, so the model can't call it, and its query path never awaits the async RAG call. Its job (reading and searching uploaded files) is already done by the document-agent tools, which MYAI-37 makes owner-checked.

### Context
- `backend/tools/files.py` defines `read_file(file_id, query=None, **kwargs)`. Line 44 calls the async `FileRAG.retrieve_for_file` (`backend/rag/file_rag.py:109`) without `await`.
- Nothing in `backend/tools/catalog/` or the registry (`backend/tools/__init__.py`, `spec.py`) references it, and no non-test code imports `backend.tools.files` (grep, 2026-11-09).
- **References:**
  - `backend/tools/tests/test_files.py` (its only test);
  - `backend/tools/README.md:20` (the `files.py` row);
  - `backend/config.py:290-291` (`READ_FILE_CONTENT_LIMIT` and its comment, used nowhere else).
- **References kept on purpose:**
  - The `read_file` display label in `static/js/constants.js` (`TOOL_DISPLAY_CONFIG`) and in `frontend/src/features/chat/tool-labels.generated.ts`, generated from it. Old chats may contain `read_file` tool calls, and they still render with this label.
  - The `"read_file"` strings in `backend/tools/tests/test_safety.py` and `frontend/src/lib/chat-model.test.ts`, which are arbitrary tool names in test data.
  - `static/js/message-manager.js:40`, which strips an old System Note wording that mentions `read_file` from stored messages. Old chats still contain that text, so the strip stays.
- **Rules:** `docs/standards/testing.md` (no orphaned tests); `AGENTS.md` 1 (README accuracy). No dependency changes, since `files.py` imports only internal modules.
- **Cross-ticket:** MYAI-37's plan already leaves `read_file` unchanged, as unregistered; its Description still names `backend/tools/files.py`. A Log note on MYAI-37 records that this ticket deletes the file.
- **Assumption:** removing it is preferred to registering it, since registering would duplicate the document-agent tools.

### Approach
Delete the module, its test, the README row and the unused config value. Keep the display labels for historical messages.
- Rejected: registering and fixing it, which adds a second, overlapping file-reading tool for the model.

### Out of scope
The document-agent tools (MYAI-37); display labels.

### Steps
#### Step 1: Remove the tool
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/tools/files.py` (delete); `backend/tools/tests/test_files.py` (delete); `backend/tools/README.md` (modify: drop the `files.py` row); `backend/config.py` (modify: drop `READ_FILE_CONTENT_LIMIT` and its comment).
- **Change:** as in Approach.
- **Verification:** `grep -rn "backend.tools.files\|READ_FILE_CONTENT_LIMIT" --include=*.py --include=*.md .` (excluding `venv`) finds nothing, and `grep -n "files.py\|read_file" backend/tools/README.md` prints nothing.

#### Step 2: Full checks
- **Status:** todo
- **Depends on:** 1
- **Files:** none.
- **Change:** none.
- **Verification:** with the env from `docs/standards/testing.md`: `venv/bin/python -m pytest backend/tools`, `backend/tests` and `tests` (the docs guardrails catch the README table), then `pytest backend`; `venv/bin/python -m ruff check .`.

### Tests
The deleted test file goes with its module; no new tests.

### Risks and open questions
None beyond the assumption above.

### Success criteria
- [x] `read_file`, its test, its README row and `READ_FILE_CONTENT_LIMIT` are gone; display labels remain.
- [x] Tests pass and `ruff check .` is clean.

### Reviewer brief
- **Objective:** remove the unregistered, broken `read_file` tool.
- **Key decisions:** delete `backend/tools/files.py`, its test, its README row and the unused `READ_FILE_CONTENT_LIMIT`. Keep the display labels and the legacy note-strip for old chats. Removing it is preferred to registering it, since the document-agent tools already cover the job.
- **Out of scope:** the document-agent tools, display labels.
- **Success criteria:** as listed in the Plan.

The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- **Round 1:** the validator returned PASS (0 BLOCKING, 4 MINOR). My judgement: PASS. All four MINOR issues fixed: the legacy note-strip reference classified as kept; a cross-ticket note for MYAI-37; the wrong `dependencies.md` citation dropped; a README grep added to the verification.

## Implementation notes
### Autopilot run (2026-11-09)
- Mode: automatic (batch-autopilot item 2/13)
- Branch: bugfix/remove-unregistered-read-file-tool  PR base: develop  Starting commit: cf5fc06f59f243df9739303928760952ee271748
- Dirty before start: none
- Work files: backend/tools/files.py (deleted), backend/tools/tests/test_files.py (deleted), backend/tools/README.md, backend/config.py
- Counters: fix 0/10, review 1/5, re-verify 0
- Last completed stage: 5 review (clean)  Next: done (shipped)
- Hard blocker: none
- WIP commit: none

### Autopilot decisions (2026-11-09)
- Plan already validated; stage 1 skipped.

### Baseline (2026-11-09)
`pytest backend/tools tests`: 8 failed, 343 passed (async-plugin failures in test_research_utils x2 and test_code_executor x6). `pytest backend`: 10 failed (those 8 + test_cache_system x2).

### Implementation progress
- [x] Step 1: Remove the tool - backend/tools/files.py, backend/tools/tests/test_files.py (deleted), backend/tools/README.md, backend/config.py
- [x] Step 2: Full checks
- Branch: bugfix/remove-unregistered-read-file-tool

### Smoke test (2026-11-09)
`pytest backend/tools backend/tests tests`: 8 failed (baseline), 393 passed. `pytest backend`: 10 failed (baseline), 1153 passed. `ruff check .`: clean. Greps for `backend.tools.files` / `READ_FILE_CONTENT_LIMIT` empty; README has no files.py row.

PR: https://github.com/archit342000/My-AI/pull/85, branch bugfix/remove-unregistered-read-file-tool, base develop

## Verification

### Verification plan and results (2026-11-09, light form)
Real app import on a throwaway DATA_DIR (/tmp, removed after). Evidence: `MYAI-45-evidence/verify-output.txt`.
| ID | Criterion | Scenario | Status |
|----|-----------|----------|--------|
| V1 | read_file removed with its tests/references | importing `backend.tools.files` raises ModuleNotFoundError; whole `backend.tools` package and `app` import cleanly | PASS |
| V2 | unused config removed | `backend.config` has no READ_FILE_CONTENT_LIMIT | PASS |
| V3 | tool not exposed | no `read_file` symbol in `backend.tools` | PASS |
| V4 | regression | `pytest backend` baseline failures only; ruff clean; display labels kept (`static/js/constants.js:25`, `tool-labels.generated.ts:5`) | PASS |
Verdict: verified (4/4). Note: an unrelated `no such table: chats` log line appears on import with an empty DB (stale-channel cleanup runs before init_db); not caused by this change.

## Review history

### Round 1 - 2026-11-09
Verdict: Approve with comments. Scope: origin/develop..working tree, 4 files, 1 Haiku reviewer; repo-wide grep clean (kept display labels and test-data strings are intentional).
- R1-1 [NIT] git index - deletions staged, two edits unstaged - Static - Fixed: ship stages all four paths together (no code change)
Resolution: 1 NIT, no code change. Review loop clean (1/5).

## Log
- 2026-11-09: created (found during MYAI-37 planning)
- 2026-11-09: linked relates_to MYAI-37 (found during MYAI-37 planning)
- 2026-11-09: plan validated, 1 round
- 2026-11-09: linked relates_to MYAI-32 (follow-up found during the epic)
- 2026-11-09: autopilot started (batch)
- 2026-11-09: implemented, smoke tests pass (baseline failures only)
- 2026-11-09: verified 4 PASS, 0 FAIL
- 2026-11-09: review round 1: Approve with comments (1 NIT)
- 2026-11-09: PR opened: https://github.com/archit342000/My-AI/pull/85 (base develop). batch-autopilot: shipped
- 2026-11-10: closed (merged into develop via the PR recorded in Implementation notes; deployed to myai.architanand.dev)
