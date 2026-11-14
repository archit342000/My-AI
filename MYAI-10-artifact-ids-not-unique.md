---
id: MYAI-10
title: "N11: artifact ids collide across owners"
status: done
created: 2026-11-08
updated: 2026-11-09
links:
  blocks: [MYAI-24]
  relates_to: [MYAI-43]
---

## Description
Report N11 (Low to Medium). Artifact ids come from a per-owner counter (backend/file_system/utils.py:100 returns str(counter)), and the owner-change path also uses the counter (manager.py). Ids are unique only within an owner. Suggested fix: UUID ids for new artifacts, the owner-change path included; existing ids are left alone (migration not needed, noted in the PR). Check static/js/file-system-ui.js for numeric parsing. Not blocked.

## Acceptance criteria
- [x] New artifact ids are UUIDs, including after an owner change
- [x] Existing artifacts still open
- [x] Legacy UI parsing checked

## Plan
**Date:** 2026-11-09  **Status:** Validated

### Objective
Make new artifact (file_system) ids globally unique by generating UUID4 strings, both for newly created artifacts and when an artifact is re-keyed after an owner change, instead of the per-owner integer counter. Existing ids stay as they are, with no data migration.

### Context
- **Requirement:** see Description and Acceptance criteria. Code was read at origin/develop 6a13e04 (`/tmp/myai-develop`); implementation branches from origin/develop.
- **Assumptions:**
  - Format is `str(uuid.uuid4())`, the canonical 36-char form with hyphens. The `<path:file_system_id>` routes in `backend/file_system/router.py` and `encodeURIComponent` in `frontend/src/api/filesystem.ts` already accept it.
  - An owner change always assigns a fresh UUID, even to a legacy numeric artifact. Keeping the old numeric id could collide in the destination owner.
  - The `file_system_counters` table and `db.get_next_file_system_counter` (`backend/database/wrapper/file_system_ops.py`) are left in place but no longer called. Dropping them would be a schema change (`docs/data.md` "Migrations"), which is out of scope. There is no schema change, so no migration test is needed.
- **Rules:** `AGENTS.md`; `docs/standards/python.md` (remove unused imports in touched code; schema changes need migrations); `docs/standards/testing.md`; `docs/data.md` line 22 lists `file_system_counters`. Checks: `scripts/check.sh`.
- **Current behaviour:**
  - `generate_fs_file_id` (`backend/file_system/utils.py`) returns `str(db.get_next_file_system_counter(...))`. Its only caller is `create_file_system` in `backend/file_system/manager.py`, near line 154.
  - `update_file_system_metadata` (`manager.py`, around line 767) calls `str(db.get_next_file_system_counter(...))` directly when `owner_changed`, then calls `db.migrate_file_system_owner(old_id, new_id, ...)`.
  - The schema (`backend/database/init_db.py`, `file_systems`) has `id TEXT` with `UNIQUE(id, chat_id, workspace_id)`, so ids are unique only per owner.
  - `_extract_fs_file_type` checks the `plan_`/`research_`/`section_` prefixes. A UUID never matches them, so it stays `custom`, the same as numeric ids today.
- **Frontend parsing (checked):**
  - Legacy `static/js/file-system-ui.js` treats ids as strings: `c.id.startsWith(...)` at line 67, `===` comparison at line 96, `dataset.file_systemId` at line 98. It has no `parseInt`/`Number` on ids.
  - `static/js/version-manager.js` interpolates ids into URLs as strings.
  - React `frontend/src/api/filesystem.ts` types `id: string`. No numeric parsing of artifact ids was found in `frontend/src` or `static/js`. Listings sort by `timestamp` or title, never by id.

### Approach
- Generate ids with `uuid.uuid4()` in one helper, `generate_fs_file_id`, and use it in both the create and owner-change paths, so there is a single source of ids.
- Rejected alternative: a global counter. It needs a schema change and is still guessable.
- Rejected alternative: prefixing the counter with the owner id. It produces long, leaky ids and is still not a UUID.
- Legacy numeric ids keep working because every lookup is by string id plus owner.

### Steps
#### Step 1: UUID id helper
- **Files:** `backend/file_system/utils.py` (add `import uuid`; add new sync function `new_fs_file_id() -> str`; modify `generate_fs_file_id`)
- **Change:** `new_fs_file_id()` returns `str(uuid.uuid4())`. `generate_fs_file_id` keeps its signature (so the `create_file_system` caller is unchanged), drops the `db.get_next_file_system_counter` call, and returns `new_fs_file_id()`. Update its docstring. The `db` import stays, because `get_workspace_for_chat` uses it.
- **Verification:** `venv/bin/python -c "import uuid; from backend.file_system.utils import new_fs_file_id; uuid.UUID(new_fs_file_id())"` exits 0. This needs the venv precondition in the Tests section, and runs with `PYTHONPATH=.` and the mock env vars from `scripts/check.sh`). The full unit tests come in Step 3.

#### Step 2: Owner-change path uses the helper
- **Files:** `backend/file_system/manager.py` (modify the `from .utils import (...)` block to add `new_fs_file_id`; modify the `owner_changed` branch of `update_file_system_metadata`, which is sync)
- **Change:** replace `new_id = str(db.get_next_file_system_counter(...))` with `new_id = new_fs_file_id()`.
- **Verification:** `grep -rn get_next_file_system_counter backend --include=*.py` shows no callers outside `backend/database/wrapper/file_system_ops.py` (the definition) and tests. The owner-change test is added in Step 3.

#### Step 3: Tests
- **Files:**
  - `backend/file_system/tests/test_utils.py` (modify `test_generate_fs_file_id`; add `test_new_fs_file_id`)
  - `backend/file_system/tests/test_manager.py` (add `test_update_file_system_metadata_owner_change_uses_uuid`)
  - `backend/database/wrapper/tests/test_file_system_ops.py` (add `test_legacy_numeric_id_still_readable_and_migratable`)
- **Change:**
  - **utils:** the result parses with `uuid.UUID(...)`, two calls differ, and the patched counter is not called.
  - **manager:** `resolve_owner_and_physical_path` returns a different owner (for example `(None, "ws_1", path)`) than `resolve_path_to_fs_file`'s meta (`chat_id="c1"`). Assert that `mock_db.migrate_file_system_owner` receives a `new_id` that is a valid UUID and not equal to the old id, and that the result's `file_system_id` equals it.
  - **DB:** using the same temp-DB setup as the existing tests in that file, call `db.ensure_chat_exists` for chats A, B and C. Then create an artifact with id `"1"` via `db.create_file_system_with_version` in A and in B. Assert that both are retrievable with `db.get_file_system_meta("1", chat_id=...)`. This shows legacy numeric ids still open. Then call `db.migrate_file_system_owner(old_id="1", new_id=<uuid>, old_chat_id=A, old_workspace_id=None, new_chat_id=C, new_workspace_id=None, new_filename=..., new_title=...)`. Assert that it opens under the new owner with its versions (`get_file_system_versions`) and that B's `"1"` is untouched. Uniqueness of new ids is covered by the utils test, since ids no longer depend on the owner.
- **Verification:** `scripts/check.sh --python-only` passes. For a quicker loop, run `venv/bin/python -m pytest backend/file_system backend/database -q` with `PYTHONPATH=.` and the mock env vars from `scripts/check.sh`.

#### Step 4: Docs
- **Files:** `docs/data.md` (modify the `file_systems` bullet near line 22)
- **Change:** note that artifact ids are UUID4 strings, that legacy artifacts may still have numeric ids, and that `file_system_counters` is legacy and unused. `backend/file_system/README.md` line 17 ("ID generation" for `utils.py`) stays accurate, so it needs no change. Re-read it after the edit to confirm.
- **Verification:** the "docs guardrails" step of `scripts/check.sh --python-only` passes.

#### Step 5: Full checks and legacy UI smoke test
- **Files:** none
- **Change:** run `scripts/check.sh`. In the legacy UI and the React UI, create an artifact, open it, rename it, move it into and out of `workspace/` (the owner change), and open an artifact that existed before the change.
- **Verification:** all check steps PASS, and each artifact opens with its versions in both UIs. The verify stage records the evidence in the ticket's `## Verification` section.

### Tests
Precondition: the repo `venv/` exists (`ls venv/bin/python`). If it is missing, create it with `python3 -m venv venv && venv/bin/pip install -r requirements-dev.txt` (that file includes `requirements.txt`). System `python3` is used only to create the venv. Every later Python run uses `venv/bin/python` (AGENTS.md rule 3).

Covered by Step 3. Run with `scripts/check.sh --python-only`, then the full `scripts/check.sh`.

### Risks and open questions
- **Longer ids:** UUIDs make tool outputs longer for the LLM. The impact is minor; tools key on paths, and ids are mostly UI-facing.
- **Stale links:** links, bookmarks or messages holding an old id still go stale after an owner change. This is existing behaviour (the id already changed there) and is not made worse.
- **Follow-up:** the `file_system_counters` table and `get_next_file_system_counter` could be removed in a later migration ticket. Not done here.
- **PR note:** state that existing ids are unchanged and that no migration is needed.
- **Open questions:** none blocking.

### Success criteria
- [ ] `generate_fs_file_id` and the owner-change path both produce UUID4 strings (unit tests).
- [ ] New ids do not depend on the owner: the utils test shows successive ids differ and the counter is not used.
- [ ] A legacy numeric-id artifact is still retrievable, and can be moved to a new owner under a UUID (DB test, plus the UI smoke test).
- [ ] Legacy UI (`static/js/file-system-ui.js`, `version-manager.js`) and React UI parsing confirmed string-safe, with a smoke test in both.
- [ ] `docs/data.md` updated, and `scripts/check.sh` passes.

### Validation log
- **Round 1:** validator FAIL. My judgement: FAIL (1 valid BLOCKING).
  1. BLOCKING, verification used bare `python`: valid (AGENTS.md rule 3). Changed to `venv/bin/python` / `scripts/check.sh`.
  2. Success criterion "two owners distinct ids" not tested: valid. Criterion reworded to owner-independence, covered by the utils test.
  3. Step 1 verified by later tests: valid. Added a direct one-liner.
  4. README "ID generation" not reviewed: valid as a note. The README stays accurate, and Step 4 says so.
  5. Legacy owner-change not exercised on a real DB: valid. The DB test now migrates the legacy `"1"` to a UUID.
  6. Evidence location vague: valid. Evidence goes in the ticket's Verification section.
  7. Grounding confirmation: no issue.
  8. No check that the counter is unused: valid. Added a grep verification to Step 2.
- **Round 2:** validator PASS. My judgement: PASS.
  - Minors applied: `ensure_chat_exists` for the FK made explicit, `migrate_file_system_owner` args named, unused `asyncio` dropped, venv precondition added.
  - README wording note: disproved as an issue, since the plan text already says no README edit.
- **Round 3:** validator PASS. My judgement: PASS (no BLOCKING), so I stopped per the round-3 rule.
  - Minors applied: Step 1 points to the venv precondition, the bootstrap wording was clarified, and the redundant `-r requirements.txt` was dropped.

## Implementation notes
### Autopilot run (2026-11-09)
- Mode: automatic (batch-autopilot, item 1/3)
- Branch: bugfix/unique-artifact-ids  PR base: develop  Starting commit: 6a13e04
- Dirty before start: none
- Work files: backend/file_system/utils.py, backend/file_system/manager.py, backend/file_system/tests/test_utils.py, backend/file_system/tests/test_manager.py, backend/database/wrapper/tests/test_file_system_ops.py, docs/data.md
- Counters: fix 0/10, review 1/5, re-verify 0
- Last completed stage: 6 ship  Next: none
- Hard blocker: none
- WIP commit: none

### Autopilot decisions (2026-11-09)
- Stage 1: plan already Validated (3 rounds); reused instead of re-planning.
### Baseline (2026-11-09)
`pytest backend/file_system backend/database`: 238 pass, 2 fail (test_cache_system::test_subscribe_generator, ::test_subscribe_generator_multi_subscriber: async tests unsupported, pytest-asyncio not installed in venv). Full `scripts/check.sh --python-only` backend suite also shows 8 more async-plugin failures in research_utils and code_executor tests, same cause, unrelated to this change.

### Implementation progress
- [x] Step 1: UUID id helper - backend/file_system/utils.py (`new_fs_file_id`, `generate_fs_file_id` uses it)
- [x] Step 2: owner-change path - backend/file_system/manager.py
- [x] Step 3: tests - test_utils.py, test_manager.py, test_file_system_ops.py
- [x] Step 4: docs - docs/data.md
- [ ] Step 5: full checks done in smoke test; legacy/React UI smoke is left to verify
Branch: bugfix/unique-artifact-ids

### Smoke test (2026-11-09)
- `pytest backend/file_system backend/database -q`: 241 pass, 2 fail (same 2 as baseline).
- `scripts/check.sh --python-only`: ruff PASS, docs guardrails PASS, inference_proxy PASS; backend 10 fail (all `async def` plugin errors, baseline-type, none in touched code).
- `grep get_next_file_system_counter backend`: only the definition remains.

Status on develop (checked at e327094, 2026-11-08): Still present on develop: utils.py:100 returns str(counter).

PR: https://github.com/archit342000/My-AI/pull/55, branch bugfix/unique-artifact-ids, base develop

## Verification
### Verification plan (2026-11-09, light form: 2 runtime source files, ~10 changed lines)
**Diff base:** 6a13e04. **Scope:** artifact id generation (`utils.py`) and owner-change re-keying (`manager.py`); docs. Out of scope: dropping `file_system_counters`.
**Environment and isolation:** run the real Flask app (`app.py`, current branch) on port 5099 with `DATA_DIR=/tmp/myai10-data` (fresh temp dir, fresh sqlite DB created by `init_db`), mock `AI_URL`/`EMBEDDING_URL`. Real app on :5000, existing containers and `backend/data` are never touched. Teardown: kill recorded PID, delete the temp dir, compare ports/containers/git status to the snapshot. Harness `scripts/v10.py` (stdlib only) takes the base URL and DB path as arguments.

| ID | Criterion | Scenario | Type | Method | Files | Expected | Evidence |
|----|-----------|----------|------|--------|-------|----------|----------|
| V1 | New ids are UUIDs | POST /api/file_systems in chat A, then GET it by the returned id | happy | API | backend/file_system/utils.py | returned id parses as UUID4; GET 200 with same id | request/response log |
| V2 | New ids owner-independent | Create artifacts with the same title in chats A and B | edge | API | backend/file_system/utils.py | two different UUIDs, both GET 200 | log |
| V3 | UUID after owner change | PATCH artifact from chat A with new_path `workspace/...` (workspace W) | happy | API + DB | backend/file_system/manager.py | success; new id is UUID != old; opens under W with version intact; old id 404 in chat A | log, DB rows |
| V4 | Existing artifacts still open | Seed legacy row id `1` in chats A and B directly in the DB; GET/list both; rename in place | regression | API + DB | utils.py, manager.py | both open with versions, listed; in-place rename keeps id `1` | log |
| V5 | Legacy ids move to UUID | PATCH legacy `1` (chat A) to workspace | regression | API + DB | manager.py | new id is UUID; chat B `1` untouched | log |
| V6 | Failure paths | PATCH unknown id; move onto an existing path | failure | API | manager.py | 404; error and original id unchanged, no new row | log |
| V7 | Legacy UI parsing checked | grep `static/js` and `frontend/src` for numeric parsing of artifact ids | static | grep | n/a | no `parseInt`/`Number` on artifact ids | grep output |
| V8 | UI opens artifacts | Playwright against throwaway app: legacy UI lists/opens a UUID artifact and legacy `1` artifact | happy | browser | n/a | both open, no console errors | screenshot (BLOCKED if the UI needs the LLM backend) |
| V9 | Regression | `pytest backend/file_system backend/database`, `scripts/check.sh --python-only` | regression | CLI | all | only baseline failures | output |

Temporary scripts: `scripts/v10.py` (API/DB driver for V1-V6), `scripts/ui.js` (V8).

### Results (2026-11-09)
Verified at HEAD 6a13e04114e9636ed903fbb8e177ad0b2e800bfc plus uncommitted: backend/database/wrapper/tests/test_file_system_ops.py a5dda112, backend/file_system/manager.py d54faa52, backend/file_system/tests/test_manager.py 65d31aca, backend/file_system/tests/test_utils.py 2c2f64d1, backend/file_system/utils.py 4185587b, docs/data.md 7f7d47bb.
Isolation proven: app on 127.0.0.1:5099, DATA_DIR=/tmp/myai10-data (chats.db there); real :5000 app, containers and backend/data untouched. Teardown: PID killed, temp dir removed, `docker ps -a` and listening ports identical to the pre-run snapshot.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | v1-v6.log: POST returned UUID4, GET 200 |
| V2 | PASS | v1-v6.log: same title in two chats gave two different UUIDs |
| V3 | PASS | v1-v6.log: PATCH to `workspace/` returned a new UUID, opens under workspace with 1 version, old id 404 |
| V4 | PASS | v1-v6.log: legacy `1` opens in two chats, lists, in-place rename keeps id `1` |
| V5 | PASS | v1-v6.log: legacy `1` moved to a UUID with content intact; other chat's `1` untouched |
| V6 | PASS | v1-v6.log: unknown id 404; rename onto existing path 400, no new row, id unchanged |
| V7 | PASS | v7-grep.log: only `parseInt` hits are version numbers/navigation index in version-manager.js, none on artifact ids |
| V8 | PARTIAL | v8-ui.log + ui-open-*.png: legacy UI lists and opens legacy `1` and a UUID artifact, no console errors. React UI not run: `frontend/dist` and `node_modules` absent (BLOCKED); React code only checked by grep (frontend/src has no numeric id parsing) |
| V9 | PASS | v9-pytest.log: 241 pass, 2 fail (baseline async-plugin); ruff and docs guardrails pass |

Verdict: verified (React UI rendering not run). 8 PASS, 1 PARTIAL (V8 React part BLOCKED), 0 FAIL.
Scripts: scripts/v10.py, scripts/ui.js (evidence folder MYAI-10-evidence/). ui.js was run with playwright from another session's temp node_modules and the system chromium.

## Review history
### Round 1 - 2026-11-09
Verdict: Approve with comments. Scope: 6 uncommitted files vs 6a13e04 (small diff, one Haiku reviewer, requirement and plan brief given). All findings checked against the code; all static (no runnable repro).
- R1-1 [MINOR] backend/file_system/tests/test_utils.py:80-93 - tests accept any UUID version, UUID4 not asserted - Static - Fixed: added version==4 asserts, test_utils.py
- R1-2 [MINOR] backend/file_system/tests/test_manager.py:293-305 - owner-change test does not assert version 4 - Static - Fixed: added version==4 assert, test_manager.py
- R1-3 [MINOR] backend/file_system/tests/test_manager.py (mock_utils fixture) - create path only tested with the id helper mocked - Static - Fixed: new test_create_fs_file_assigns_uuid4_id uses the real helper (could not show it fails pre-fix without reverting; pre-fix the id would be a MagicMock string)
- R1-4 [MINOR] backend/file_system/utils.py:100-104 - generate_fs_file_id docstring does not say the owner args are ignored/kept for signature compatibility - Static - Fixed: docstring note in utils.py
- R1-5 [NIT] backend/file_system/tests/test_utils.py:81 - counter patch kept only for assert_not_called, intent unclear - Static - Fixed: comment on the counter patch, test_utils.py
Dismissed: none. Pre-existing: none.
Resolution: 5 Fixed, 0 Rejected, 0 Deferred. Tests/comments/docs only, no runtime behaviour change. Checks: `pytest backend/file_system backend/database` 242 pass, 2 fail (baseline); ruff clean.


## Log
- 2026-11-08: created from reports/full-scope-final-report-2026-11-08.md
- 2026-11-09: plan validated, 3 rounds
- 2026-11-09: linked blocks MYAI-24 (the counter must have no callers (UUID ids from MYAI-10))
- 2026-11-09: autopilot started (batch-autopilot)
- 2026-11-09: implemented, smoke tests pass (only baseline async-plugin failures)
- 2026-11-09: verified: 8 PASS, 1 partial (React UI not built), 0 FAIL
- 2026-11-09: review round 1: Approve with comments (4 MINOR, 1 NIT)
- 2026-11-09: review round 1 resolved: 5 fixed (tests/comments only)
- 2026-11-09: PR opened #55 (batch-autopilot: shipped, base develop)
- 2026-11-09: linked relates_to MYAI-43 (batch 1 follow-ups)
- 2026-11-09: PR #55 merged into develop; closed
