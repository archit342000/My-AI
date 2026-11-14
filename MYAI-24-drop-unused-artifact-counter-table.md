---
id: MYAI-24
title: "Drop the unused artifact counter table"
status: done
created: 2026-11-09
updated: 2026-11-09
links:
  blocked_by: [MYAI-10]
  conflicts_with: [MYAI-6]
  relates_to: [MYAI-43, MYAI-44]
---

## Description
Follow-up to MYAI-10. Once MYAI-10 switches artifact ids to UUIDs, the `file_system_counters` table and `db.get_next_file_system_counter` (`backend/database/wrapper/file_system_ops.py`) are no longer called. Removing them is a schema change under `docs/data.md` Migrations. Depends on MYAI-10 being merged.

## Acceptance criteria
- [x] The table is dropped by a migration that follows docs/data.md
- [x] get_next_file_system_counter and its tests are removed
- [x] Existing databases upgrade cleanly; artifacts with old numeric ids still open

## Plan

**Date:** 2026-11-09  **Status:** Validated  **Base:** origin/develop 6a13e04  **Depends on:** MYAI-10 merged (no callers of the counter remain)

### Objective
Remove the `file_system_counters` table and `db.get_next_file_system_counter` once MYAI-10 has made artifact ids UUIDs. The removal must follow `docs/data.md`'s migration rules, so existing databases upgrade cleanly and artifacts with old numeric ids keep working.

### Context
- Requirement: Description and Acceptance criteria above.
- Code that references the table on develop:
  - `backend/database/init_db.py`:
    - step 0 (lines 19-40) renames `canvas_counters` to `file_system_counters` and its `chat_id` column to `owner_id`;
    - `CREATE TABLE IF NOT EXISTS file_system_counters` (line 233);
    - step 8 (line ~879) renames the column again (`OperationalError` is ignored);
    - step 10 (lines 899-918) repeats the canvas renames.
  - `backend/database/wrapper/file_system_ops.py:416-430`: `get_next_file_system_counter`, the only reader and writer.
  - Tests:
    - `backend/database/wrapper/tests/test_file_system_ops.py:116-118` (counter call);
    - `backend/file_system/tests/test_utils.py:80-84` (`test_generate_fs_file_id` patches the counter; MYAI-10 rewrites it);
    - `backend/database/tests/test_init_db.py` (`test_init_db` runs `init_db()` twice; `test_init_db_with_legacy_data` builds the legacy canvas tables).
  - Docs: `docs/data.md:22` lists `file_system_counters` among the main tables.
- After MYAI-10 (planned):
  - `generate_fs_file_id` and the owner-change path use `new_fs_file_id()` (UUID4).
  - The counter is defined but not called (MYAI-10 Step 2 checks this with a grep).
  - Old artifacts keep their numeric string ids in `file_systems.id`. The counter table only stores the next number per owner and isn't referenced by any foreign key.
- `docs/data.md` Migrations:
  1. no version table; `init_db()` must be idempotent;
  4. never drop user data without an explicit, documented decision;
  5. add a test that runs `init_db()` twice and against a database created by the previous schema.
  - Steps in `init_db()` are numbered comments (`# 0.` to `# 13.`). MYAI-6 also plans a new migration block.

### Approach
- **Documented drop decision.** The counter table holds only per-owner sequence numbers, not user content, and nothing reads it after MYAI-10. Dropping it loses no user data. This plan records that decision, which `docs/data.md` rule 4 requires, and says so in the commit message.
- **Migration.** Add a final block, `# 14. Drop the unused file_system_counters table (artifact ids are UUIDs since MYAI-10)`, just before `conn.commit()`. It runs `DROP TABLE IF EXISTS file_system_counters`, which is idempotent.
  - Remove the `CREATE TABLE IF NOT EXISTS file_system_counters` statement.
  - Leave the step 0, 8 and 10 rename statements alone. On an old DB they still rename `canvas_counters` on the way through, and step 14 then drops the result. On a new DB, the step 8 column rename hits "no such table", an `OperationalError` that is already ignored. Step 0's and step 10's renames run only when `canvases` exists, which means a legacy DB that has `canvas_counters`.
  - Removing the dead rename lines would be a needless edit to legacy migrations.
- **Code removal.** Delete `get_next_file_system_counter` from `file_system_ops.py` and its test. Remove any `test_generate_fs_file_id` leftovers that still patch it (MYAI-10 should already have rewritten them; check).
- Rejected alternatives:
  - Keep the table: dead schema, which is the point of the ticket.
  - Rename the step 0/10 statements to drop `canvas_counters` directly: it changes legacy migration code paths with no benefit.

### Steps
#### Step 1: Migration in `init_db`
- **Files:** `backend/database/init_db.py` (modify): delete the `CREATE TABLE IF NOT EXISTS file_system_counters` block (line ~233); add step 14 before `conn.commit()`.
- **Change:** as in Approach. Number the block after whatever is last at implementation time; if MYAI-6's block has landed as 14, use 15. The comment names the decision.
- **Verification:** Step 3 tests.

#### Step 2: Remove the counter method and its test
- **Files:** `backend/database/wrapper/file_system_ops.py` (modify): delete `get_next_file_system_counter`. `backend/database/wrapper/tests/test_file_system_ops.py` (modify): delete the counter call and assert (lines 116-118), renumbering the step comments if needed. `backend/file_system/tests/test_utils.py` (modify if needed): if `test_generate_fs_file_id` still patches `backend.database.db.get_next_file_system_counter` (line 80 on develop) after MYAI-10, drop that patch.
- **Change:** first run `grep -rn "get_next_file_system_counter\|file_system_counters" backend app.py scripts static frontend/src`. The only hits allowed are the step 0/8/10 rename statements and the new step 14 block in `init_db.py`, plus test or doc lines this ticket updates. Any other caller blocks the ticket: MYAI-10 isn't fully landed.
- **Verification:** the grep result is recorded in Implementation notes.

#### Step 3: Migration tests
- **Files:** `backend/database/tests/test_init_db.py` (modify).
- **Change:**
  - In `test_init_db` (fresh DB, run twice), assert `file_system_counters` isn't in `sqlite_master`.
  - New `test_init_db_drops_file_system_counters` builds the previous schema:
    1. Run `init_db()` from a temp DB, then create `file_system_counters` with a row, as an old DB would have it.
    2. Create the chat with `db.ensure_chat_exists`, then insert a `file_systems` row with a numeric id (`"7"`) and a version row.
    3. Run `init_db()` twice.
    4. Assert that the table is gone, that the file system row and its versions still exist, and that `db.get_file_system_meta` and `db.get_file_system_versions` (`file_system_ops.py:14, 296`) return it by id `"7"`. This approximates a database from the previous schema (current schema plus the counter table, which is the only difference); `test_init_db_with_legacy_data` covers the older canvas-era schema.
  - Extend `test_init_db_with_legacy_data` (it already creates `canvas_counters`, line 42) to assert that neither `canvas_counters` nor `file_system_counters` exists afterwards.
- **Verification:** `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q backend/database`, then `... -m pytest -q backend` (the full suite, its own process).

#### Step 4: Docs and full gate
- **Files:** `docs/data.md` (modify): line 22 drops `file_system_counters` from the table list. Replace MYAI-10's "legacy and unused" note on the same bullet, if present, with one sentence: artifact ids are UUIDs, older numeric ids remain valid, and the counter table was dropped (an explicit decision under Migrations rule 4, since it held only sequence numbers, not user data). `backend/database/README.md` / `backend/database/wrapper/README.md`: update them only if they name the counter (check with grep).
- **Change:** run `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q tests`, `venv/bin/ruff check .` and `scripts/check.sh`.
- **Live check:**
  1. Copy a real `chats.db` to a throwaway `DATA_DIR`, using `venv/bin/python -c "import sqlite3; s=sqlite3.connect('<live>/chats.db'); d=sqlite3.connect('/tmp/myai24/chats.db'); s.backup(d)"` (the online backup that `docs/data.md`'s backup rule describes; the `sqlite3` CLI isn't installed here). Never touch the live file.
  2. Start the app against the copy (venv `python app.py` with `DATA_DIR` pointed at it, or a throwaway stack with the MYAI-17 Step 7 isolation rules).
  3. Check the table is gone, that an old numeric-id artifact opens in the React UI, and that a new artifact gets a UUID.
- **Verification:** all pass; results go in Verification.

### Tests
- Preconditions: a `venv` with `requirements.txt` and `requirements-dev.txt`.
- `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q backend`, then the same with `tests`.
- `venv/bin/ruff check .`, then `scripts/check.sh`.
- Live check on a copy of a real DB (Step 4).

### Risks and open questions
- **Ordering.** Must land after MYAI-10. Step 2's grep is the gate.
- **Rollback.** An older build started against the migrated DB recreates the table (`CREATE TABLE IF NOT EXISTS`, starting at 0), and its counter would then collide with old numeric ids. That only matters if someone downgrades past MYAI-10, which is already a different id scheme. Note it in the release notes.
- **Migration numbering** may clash with MYAI-6's new block; renumber at implementation time.
- No blocking open questions.

### Success criteria
- [ ] The table is dropped by an idempotent migration that follows `docs/data.md`, with the drop decision documented (Steps 1 and 3)
- [ ] `get_next_file_system_counter` and its tests are removed; the grep shows no callers (Step 2)
- [ ] Existing databases upgrade cleanly, and old numeric-id artifacts still open (Step 3, live check)
- [ ] Docs updated; all checks pass

### Validation log
- Round 1 (2026-11-09, Haiku): PASS, 8 MINOR. My judgement: PASS. All 8 were valid and applied:
  - the grep gate now allows step 14;
  - step numbering is `# 0.` to `# 13.`;
  - the test_utils.py edit is explicit;
  - the data.md wording is reconciled with MYAI-10;
  - the drop decision is documented in data.md;
  - the test setup uses real wrapper methods (and canvas_counters already exists in the legacy test);
  - the backup uses Python's online backup instead of the missing sqlite3 CLI;
  - the previous-schema approximation is stated.
  The uncaught-failure question (no table on a fresh DB) raised no issue: the step 8 rename is already wrapped in an OperationalError guard.

## Implementation notes
### Autopilot run (2026-11-09)
- Mode: automatic (batch-autopilot batch 2, item 3/3)
- Branch: bugfix/drop-artifact-counter  PR base: develop  Starting commit: 6307ffb
- Dirty before start: none
- Work files: backend/database/init_db.py, backend/database/wrapper/file_system_ops.py, backend/database/wrapper/tests/test_file_system_ops.py, backend/database/tests/test_init_db.py, backend/file_system/tests/test_utils.py, docs/data.md
- Counters: fix 0/10, review 1/5, re-verify 0
- Last completed stage: 6 ship  Next: none
- Hard blocker: none
- WIP commit: none

### Autopilot decisions (2026-11-09)
- Stage 1: plan already Validated (1 round); reused, not re-planned. MYAI-10 is merged (PR #55) so the plan's gate (no callers of the counter) can be checked now.

### Baseline (2026-11-09)
At develop 6307ffb: backend/database/tests 60 pass + 2 fail (test_cache_system async tests: pytest-asyncio not installed in the venv); backend/database/wrapper/tests 72 pass; backend/file_system 116 pass. Other backend suites fail only on async tests (tools 6, research_agent 2, tavily_mcp 5, code_runner_mcp).

### Implementation progress
- [x] Gate grep (`get_next_file_system_counter|file_system_counters` over backend app.py scripts static frontend/src docs): only the step 0/8/10 rename statements in init_db.py, the CREATE TABLE, the method and its test call, the test_utils patch and docs/data.md; no other callers
- [x] Step 1: migration - backend/database/init_db.py (CREATE TABLE removed; `# 14.` `DROP TABLE IF EXISTS file_system_counters` before the final commit, decision documented in the comment)
- [x] Step 2: method and tests removed - backend/database/wrapper/file_system_ops.py, tests/test_file_system_ops.py, backend/file_system/tests/test_utils.py (counter patch dropped)
- [x] Step 3: migration tests - backend/database/tests/test_init_db.py (fresh DB, legacy canvas DB, previous schema with a numeric-id artifact, run twice)
- [x] Step 4: docs - docs/data.md (table list, drop decision under Migrations rule 4); no database README names the counter
Branch: bugfix/drop-artifact-counter
Deviation: the live check uses a synthetic previous-schema DB (this branch's init_db plus the counter table and a numeric-id artifact) instead of a copy of the user's real chats.db, to keep real data out of the verification.

### Smoke test (2026-11-09)
database/tests 61 pass + 2 baseline fails; wrapper 72; file_system 116; backend/tests 25; tests 32; ruff clean; `scripts/check.sh --python-only`: only the baseline async-plugin failures. The new migration tests were not shown failing without the migration by reverting (they assert the table is gone and the numeric-id artifact survives).

PR: https://github.com/archit342000/My-AI/pull/60, branch bugfix/drop-artifact-counter, base develop

## Verification
### Verification plan (2026-11-09, light form: one migration statement, one removed method; data/migration so isolation is strict)
**Diff base:** origin/develop 6307ffb. **Scope:** `init_db` step 14 drops `file_system_counters` (and stops creating it); `get_next_file_system_counter` removed. Out of scope: the legacy canvas-era upgrade (unit test only), a copy of the user's real `chats.db` (not touched).
**Environment and isolation:** this branch's app on 127.0.0.1:5099, `DATA_DIR=/tmp/myai24-data`, built React frontend, `AI_PROXY_URL=http://127.0.0.1:5098` (fake proxy). The previous-schema DB is built synthetically: this branch's `init_db()` once, then the `file_system_counters` table with a row, a workspace, two chats (one in the workspace), an artifact with the old numeric id `7` and a version row. Never touch :5000/:5001, containers, `backend/data` or the real `chats.db`. Teardown: kill PIDs, remove the temp dir, compare ports/containers/git status to the snapshot.
Scripts: `scripts/seed_old_db.py`, `scripts/v24_api.py`, `scripts/ui.js`, `scripts/fake_proxy.py`.

| ID | Criterion | Scenario | Type | Method | Files | Expected |
|----|-----------|----------|------|--------|-------|----------|
| V1 | Table dropped by an idempotent migration; DB upgrades cleanly | start the app on the previous-schema DB twice (restart) | happy/idempotent | app start + DB | init_db.py | `file_system_counters` gone after the first start and still gone after the second; no startup error in the app log; the numeric-id artifact and its version row still in the DB |
| V2 | Old numeric-id artifacts still open | `GET /api/file_systems/7?chat_id=...` and its versions | regression | API | init_db.py, file_system_ops.py | 200 with content `old body`; versions list has 1 |
| V3 | Old numeric-id artifacts open in the UI | React UI: open the chat, open the files panel, open artifact 7 | regression | browser | n/a | content `old body` visible, no console errors |
| V4 | New ids and artifact operations unaffected | create a new artifact; rename in place; move to `workspace/` | regression | API + DB | file_system code paths | new id is a UUID; rename keeps the id; move gives a new UUID that opens under the workspace; old artifact 7 untouched |
| V5 | Method and tests removed; no callers | grep for `get_next_file_system_counter` and the table name over code and docs | static | grep | file_system_ops.py | only the legacy rename statements and the new drop remain in init_db.py |
| V6 | Regression | database, wrapper, file_system, backend, tests dirs, ruff | regression | CLI | all | only baseline failures |

### Results (2026-11-09)
Verified at HEAD 6307ffbd5f06dd63c98a6b99075723386261e158 plus uncommitted (hash prefixes): backend/database/init_db.py f2b847ce, backend/database/tests/test_init_db.py ff5bd1eb, backend/database/wrapper/file_system_ops.py acd256d8, backend/database/wrapper/tests/test_file_system_ops.py a073fb78, backend/file_system/tests/test_utils.py 0f002d7e, docs/data.md cd1325c1.
Isolation: app 127.0.0.1:5099 on a synthetic previous-schema DB in /tmp/myai24-data (this branch's init_db plus the counter table, a workspace, a chat and a numeric-id artifact; the user's real chats.db was not read or copied), fake proxy 5098; :5000/:5001, containers and backend/data untouched. Teardown: PIDs killed, 5098/5099 free, temp dir removed, containers and git status identical to the snapshot.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | v1-seed.log, v1-after-first-start.log, v1-v4-api.log, app-start1/2.log: `file_system_counters` existed before the first start, was gone after it and still gone after the restart; no migration or startup error in either app log; artifact `7` and its version row intact |
| V2 | PASS | v1-v4-api.log: `GET /api/file_systems/7` 200 with `old body`, versions 200 with 1 version |
| V3 | PASS | v3-ui.log, ui-3-opened.png: artifact `old.txt` (id 7) listed in the files panel, opened, content `old body` shown, no console errors |
| V4 | PASS | v1-v4-api.log: new artifact id is a UUID; rename kept the id; move to `workspace/` gave a new UUID that opens under the workspace; artifact 7 untouched |
| V5 | PASS | v5-grep.log: no caller of `get_next_file_system_counter`; the only table references left are the legacy rename statements and the new drop in init_db.py, tests and docs |
| V6 | PASS | v6-regression.log: database/tests 61 pass + 2 baseline, wrapper 72, file_system 116, backend/tests 25, tests 32, ruff clean |

Verdict: verified. 6 of 6 pass, 0 FAIL, 0 BLOCKED. Not covered: a copy of the real database (deliberately not touched), the legacy canvas-era upgrade (unit test only), a downgrade to a build that recreates the table (plan Risks).
Scripts: scripts/seed_old_db.py, v24_api.py, ui.js, fake_proxy.py.

## Review history
### Round 1 - 2026-11-09
Verdict: Approve with comments. Scope: 6 uncommitted files vs 6307ffb (small mode, one Haiku reviewer given the Description, Acceptance criteria and the plan's Objective/Approach/Out of scope/Success criteria). Findings checked against the code; all static.
- R1-1 [MINOR] docs/data.md:25 - the sentence "The old `file_system_counters` table was dropped by `init_db()`" is changelog-style in a reference doc (docs/standards/docs.md: docs describe the current state); say it as current state and name the migration step - Static - Fixed: reworded as current state naming migration 14, docs/data.md
Rejected / no change needed (valid observations, no defect):
- R1-2 [MINOR] init_db.py:1554 - the DROP is DDL and only joins the open transaction if an earlier DML already opened one: DROP IF EXISTS is idempotent and the last statement, so the outcome is the same either way (it was dropped in the live run); the code comment makes no "single final commit" claim - Rejected
- R1-3 [MINOR] test_init_db.py:498-517 - suggest also reading the numeric-id artifact through the wrapper after `init_db()`: `test_legacy_numeric_id_still_readable_and_migratable` (test_file_system_ops.py) already covers wrapper reads of numeric ids, and the live run read it through the API and UI - Rejected
- R1-4 [NIT] test_init_db.py:33 - the fresh-DB assertion passes because the CREATE was removed, not because of the migration (the new previous-schema test covers the migration); reviewer says no change required - Rejected
- R1-5 [NIT] test_file_system_ops.py:114-117 - the step comments now jump from 12 to 14: the numbering already skips 16, cosmetic - Rejected
- R1-6 [NIT] init_db.py steps 8 and 10 - the legacy rename statements are no-ops on fresh DBs; this is the approach the plan accepted (OperationalError already ignored), reviewer says no change required - Rejected
Dismissed: none. Pre-existing: none.

Resolution: 1 Fixed, 5 Rejected (evidence above). Docs only, no runtime change: no live re-verify needed. Checks: `pytest tests` (docs guardrails) 32 pass.


## Log
- 2026-11-09: created (follow-up found while planning MYAI-2 to MYAI-16)
- 2026-11-09: plan validated, 1 Haiku round.
- 2026-11-09: linked blocked_by MYAI-10 (the counter must have no callers (UUID ids from MYAI-10))
- 2026-11-09: linked conflicts_with MYAI-6 (new migration blocks at the end of init_db (renumber))
- 2026-11-09: linked relates_to MYAI-43 (batch 1 follow-ups)
- 2026-11-09: autopilot started (batch-autopilot)
- 2026-11-09: implemented, smoke tests pass (only baseline async-plugin failures)
- 2026-11-09: verified: 6 PASS, 0 FAIL, 0 BLOCKED
- 2026-11-09: review round 1: Approve with comments (3 MINOR, 3 NIT; 1 valid, 5 rejected)
- 2026-11-09: review round 1 resolved: 1 fixed (docs), 5 rejected
- 2026-11-09: PR opened #60 (batch-autopilot: shipped, base develop)
- 2026-11-09: linked relates_to MYAI-44 (batch 2 follow-ups)
- 2026-11-09: PR #60 merged into develop; closed
