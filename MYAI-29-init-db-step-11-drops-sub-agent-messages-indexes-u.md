---
id: MYAI-29
title: "init_db step 11 drops sub_agent_messages indexes until the next start"
status: done
created: 2026-11-09
updated: 2026-11-09
links:
  blocks: [MYAI-34]
  conflicts_with: [MYAI-6, MYAI-25, MYAI-31]
---

## Description
Found while planning MYAI-25. Migration step 11 in `backend/database/init_db.py` rebuilds dependent tables lacking ON DELETE CASCADE, after step 3 has created the indexes. It re-creates only `idx_messages_chat_id` and `idx_pending_cb_chat` (and `idx_files_chat_id` after MYAI-25). On a `sub_agent_messages` rebuild, `idx_sub_agent_chat_parent` and `idx_sub_agent_sequence` are missing until the next start. Fix: re-run the step 3 index block after step 11 (or re-create every index of a rebuilt table).

## Acceptance criteria
- [x] All step 3 indexes exist right after a step 11 rebuild, on the same run
- [x] `init_db()` stays idempotent (test runs it twice and against a pre-cascade schema)

## Plan

**Date:** 2026-11-09  **Status:** Validated  **Base:** origin/develop 6a13e04

### Objective
After `init_db()` migration step 11 rebuilds a dependent table, every index on that table must exist again in the same run. Today only `idx_messages_chat_id` and `idx_pending_cb_chat` are re-created, so the `sub_agent_messages` and `collections` indexes are missing until the next start.

### Context
- Requirement: Description and Acceptance criteria above. The Description names `sub_agent_messages`. `collections` has the same gap (`idx_collections_chat_parent`, `idx_collections_parent_type`, lines 509-510), so it's covered too: the same defect in the same loop.
- `backend/database/init_db.py`:
  - Indexes are created in three places:
    - line 312 (`idx_pending_cb_chat`, right after `pending_callbacks`);
    - lines 367-368 (`idx_exec_history_*`);
    - step `# 3. Create Indexes`, lines 500-510 (`messages`, `file_systems`, `file_system_versions`, `file_system_permissions`, `memories`, `sub_agent_messages`, `collections`).
  - Step `# 11.` (line 920 onwards) rebuilds `messages`, `files`, `sub_agent_messages`, `collections` and `pending_callbacks` when their DDL lacks `ON DELETE CASCADE` (rename to `_old`, create, copy, drop). The drop takes the old table's indexes with it.
  - The "Re-create indices" branch (lines 1021-1025) only handles `messages` and `pending_callbacks`.
  - Step 11 runs after step 3, so anything step 3 created on a rebuilt table is gone for the rest of that run.
  - Step `# 8.` (lines 663-786) has the same effect for the workspace schema migration. It renames `file_systems` to `file_systems_old` (line 694), rebuilds `file_system_versions` and `file_system_permissions` (736-776) and drops `file_systems_old` (784), which removes `idx_file_systems_*` and `idx_file_system_*_file_system_id` until the next start. A final `_create_indexes` call after step 11 also covers step 8.
- MYAI-25 (planned, conflicts_with) adds `idx_files_chat_id` to step 3 and a `files` branch to the same step 11 block.
- MYAI-6 (planned, conflicts_with) changes the `messages` definition in `dependent_tables`.
- Tests: `backend/database/tests/test_init_db.py` (`test_init_db` runs `init_db()` twice; `test_db_schema_cascade_integrity` at line 116; `test_init_db_with_legacy_data`).
- `docs/data.md` Migrations: idempotent `init_db()`; rule 5, a test that runs `init_db()` twice and against a previous-schema database.

### Approach
- **One index function.** Add a module-level `_create_indexes(c) -> None` in `init_db.py`, holding every `CREATE INDEX IF NOT EXISTS` statement: the step 3 list, line 312's `idx_pending_cb_chat`, and lines 367-368's `idx_exec_history_*`.
  - Call it where step 3 is today, which is after every table is created, so moving 312 and 367-368 there changes no outcome.
  - Call it again after step 11's whole `try/except` block, not inside the `try`, so it still runs when a rebuild fails and the `except` only logs (lines 1028-1029). This covers both step 8 and step 11 rebuilds.
  - All statements are `IF NOT EXISTS`, so the second call is a no-op when nothing was rebuilt.
- **Remove the per-table branch** in step 11 (lines 1021-1025); `_create_indexes` replaces it.
- **MYAI-25.** If it has landed, move `idx_files_chat_id` into `_create_indexes` and drop its step 11 branch. If it hasn't, MYAI-25 adds its index to `_create_indexes` instead. Note this on MYAI-25 when this lands.
- Rejected: adding more per-table branches. That's the pattern that caused the gap, because every new index needs remembering in two places.

### Steps
#### Step 1: `_create_indexes`
- **Files:** `backend/database/init_db.py` (modify).
- **Change:**
  - New `_create_indexes(c)` with a docstring saying it is the only place indexes are defined, and that it's called after table creation and again after step 11.
  - Move the statements from lines 312, 367-368 and 500-510 into it. Step 3's comment block now calls `_create_indexes(c)`.
  - After step 11's `try/except`, call `_create_indexes(c)`.
  - Delete the "Re-create indices" `if/elif`.
- **Verification:** Step 2 tests; `grep -n "CREATE INDEX" backend/database/init_db.py` shows statements only inside `_create_indexes`.

#### Step 2: Tests
- **Files:** `backend/database/tests/test_init_db.py` (modify).
- **Change:**
  - Helper `_index_names(c, table)`: `SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=?`.
  - In `test_init_db` (fresh DB, `init_db()` twice), assert that the full expected index set exists. Put the names list in the test.
  - New `test_init_db_restores_indexes_after_cascade_rebuild`:
    1. Before any `init_db()`, create a minimal `chats` table (pattern at line 45) with row `id='c1'`; connections enforce FKs (`db_layer.py:126`). Then create pre-cascade copies of `messages`, `sub_agent_messages`, `collections` and `pending_callbacks`: copy each `CREATE TABLE` from `dependent_tables` exactly (all columns, including those step 3 indexes and the step 11 copy need, because `collections` and `pending_callbacks` get no add-column migration), with `ON DELETE CASCADE` removed from the FKs. Insert one row each with `chat_id='c1'` and every NOT NULL column filled (for example `sub_agent_messages.agent_name`, `sequence_order` and `role`; `collections.collection_type` and `items`; `pending_callbacks.tool_name`). A NOT NULL failure during the copy is swallowed by step 11's `except`, so the row assertions below catch it.
    2. Run `init_db()` once. Assert each table's DDL now contains `ON DELETE CASCADE` (the rebuild ran), that the full expected index set (the same list as in `test_init_db`) exists after that single run, that the rows survived, and that no `*_old` table is left.
    3. Run `init_db()` again; same assertions (idempotent).
  - Extend `test_init_db_with_legacy_data` (which triggers the step 8 workspace migration) to assert the `idx_file_systems_*` and `idx_file_system_*_file_system_id` indexes exist after one run.
  - Direct test of `_create_indexes`: on a DB after `init_db()`, drop two indexes, call `_create_indexes(c)` and assert they're back. Call it twice to show it's idempotent.
- **Verification:** `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q backend/database`, then `... -m pytest -q backend`.

#### Step 3: Full gate
- **Change:** run `venv/bin/python -m ruff check .`, the `tests` suite in its own process, and `scripts/check.sh`. No change to `docs/data.md`, which doesn't list indexes; the docstring documents the rule. Check `backend/database/README.md` (lines 17 and 25 describe `init_db.py`) and add a short note that indexes are defined in `_create_indexes` if it lists schema elements.
- **Verification:** all pass.

### Tests
- Preconditions: a `venv` with `requirements.txt` and `requirements-dev.txt`.
- `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q backend`, then the same with `tests`.
- `venv/bin/python -m ruff check .`, then `scripts/check.sh`.

### Risks and open questions
- **Moving the line 312 and 367-368 statements.** They now run with the step 3 call, after all tables exist, so nothing between their old and new positions depends on them. Check during implementation that no statement between line 312 and step 3 relies on those indexes; none should, since indexes only affect performance.
- **Merge with MYAI-25 and MYAI-6** (same blocks; see links). Whichever lands second moves its index or definition into the new structure.
- **Pre-existing, out of scope:**
  - Step 11's rebuild isn't wrapped in its own transaction (`docs/data.md` rule 3). Its `except` only logs, so a failed copy can leave a `<table>_old` behind, still owning the index names, which makes later `CREATE INDEX IF NOT EXISTS` on the new table a no-op.
  - This plan adds no rebuild and doesn't change that. The new test asserts that no `*_old` table is left in the normal path.
  - Possible follow-up ticket: wrap each step 11 rebuild in a savepoint and repair leftover `_old` tables.
- No blocking open questions.

### Success criteria
- [ ] Every index exists right after a step 11 rebuild, in the same run, for all rebuilt tables (Step 2)
- [ ] `init_db()` stays idempotent: run twice, and against a pre-cascade schema (Step 2)
- [ ] Indexes are defined in one place (Step 1 grep)
- [ ] All checks pass

### Validation log
- Round 1 (2026-11-09, Haiku): PASS, 10 MINOR. My judgement: PASS. Applied:
  - step 8 also drops the file_system indexes (lines 663-786), now covered by the final call, with a test;
  - the final call sits outside step 11's try, so it runs even after a failure;
  - the pre-cascade test setup is exact (c1 row, NOT NULL columns, full DDL);
  - the full index set is asserted;
  - a direct `_create_indexes` test;
  - the README check;
  - the orphaned `_old` table and missing transaction recorded as pre-existing follow-ups.
  The collections scope was confirmed.

## Implementation notes

### Autopilot run (2026-11-09)
Batch 4 item. Branch bugfix/step11-indexes from origin/develop 77fa8f2, PR base develop. Dirty files before start: none. Plan was written against 6a13e04; init_db.py is unchanged on develop in the planned regions.

### Baseline (2026-11-09)
At develop 77fa8f2: backend/database 134 pass, 2 fail (test_cache_system subscribe_generator*, async plugin missing); backend + tests: only async-plugin failures.

### Implementation progress
- [x] Step 1: `_create_indexes(c)` in init_db.py holds all 13 index statements; called after table creation and again after step 11; per-table branch removed
- [x] Step 2: tests in test_init_db.py (full index set in test_init_db and the legacy-data test, new cascade-rebuild test run twice, direct `_create_indexes` test)
- [x] Step 3: ruff clean; backend/database/README.md notes `_create_indexes`. scripts/check.sh not run as a whole (pytest-asyncio missing)

### Smoke test (2026-11-09)
test_init_db.py 13 pass; `pytest backend tests` 930 pass, 10 fail (all async plugin, baseline); ruff clean. Defect shown against develop's init_db in a scratch module: a pre-cascade `sub_agent_messages` ends with no indexes after one run. The new tests cannot be shown failing by reverting the file (not allowed), so that scratch run stands in.
None yet.

PR: https://github.com/archit342000/My-AI/pull/65, branch bugfix/step11-indexes, base develop

## Verification
### Verification plan (2026-11-09, full form: schema migration)
**Diff base:** origin/develop 77fa8f2. **Scope:** `init_db._create_indexes` and its two call sites (after table creation, after the step 11 rebuild). Out of scope: wrapping rebuilds in transactions, repairing leftover `_old` tables, the files index (MYAI-25).
**Environment and isolation:** the real app (`/tmp/gen/run_app.py`, port 5099) started by the script on throwaway `DATA_DIR`s `/tmp/myai29-fresh`, `-precascade`, `-legacy`, fake proxy on 5098. Never touch :5000/:5001, containers, `backend/data` or a real `chats.db`. Teardown: processes terminated by the script, /tmp/myai29-* removed; docker/ports/git snapshots `/tmp/gen/*-before29.txt`.
Scripts: `scripts/v29.py` (builds the old-schema DBs, starts the app, inspects `sqlite_master`, calls the API), `scripts/fake_proxy.py`.

| ID | Criterion | Scenario | Type | Method | Files | Expected |
|----|-----------|----------|------|--------|-------|----------|
| V1 | all indexes exist | fresh DB, real app start | happy | app + DB | init_db.py | every expected index present, `GET /api/chats` 200 |
| V2 | indexes exist right after a step 11 rebuild; idempotent | DB with pre-cascade messages, sub_agent_messages, collections, pending_callbacks and one row each: start the app once, inspect, restart | edge/regression | app + DB | init_db.py | after the FIRST start: all indexes present, DDL has ON DELETE CASCADE, rows kept, no `*_old` table, old chat listed; after a restart the index set is identical |
| V3 | step 8 rebuild also gets its indexes | legacy canvases schema DB, real app start | edge | app + DB | init_db.py | app starts, `GET /api/chats` 200, all indexes present (incl. `idx_file_systems_*`) |
| V4 | regression | backend, tests dirs, ruff | regression | CLI | all | only baseline async failures |
Not run yet.

### Results (2026-11-09)
**Commit verified:** 77fa8f29fe3eacd791cc522a129b2e47a95ef991 (+ uncommitted files)
Hashes: README.md 7b578667, init_db.py 3c00f3a3, test_init_db.py 99f62769.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | v1-v3.log: fresh DB, real app start, GET /api/chats 200, every expected index present |
| V2 | PASS | v1-v3.log: pre-cascade DB; after the FIRST start all indexes present, DDL cascaded, 1 row per table kept, no `*_old` table, old chat listed; a restart leaves the index set identical |
| V3 | PASS | v1-v3.log: legacy canvases DB (step 8), app starts, GET /api/chats 200, all indexes present |
| V4 | PASS (baseline) | test_init_db.py 13 pass; `pytest backend tests` 930 pass, 10 fail (all async plugin, baseline); ruff clean |

Notes: the "before" state is shown with develop's init_db in a scratch module (pre-cascade `sub_agent_messages` ends with no indexes after one run, Implementation notes). Two harness attempts failed for harness reasons (legacy fixture without `chats.timestamp`, which init_db does not add and is unrelated; then a leftover throwaway app on 5099 from the crashed run, killed): logs `v1-v3-attempt1-fixture.log`, `v1-v3-attempt2-leftover-app.log`. Teardown: processes stopped, /tmp/myai29-* removed, ports 5098/5099 free, containers and git status as before.
**Verdict: verified (4/4 PASS, 0 FAIL, 0 BLOCKED).** Gap: no real production-size DB was migrated.

## Review history
### Round 1 - 2026-11-09
Verdict: Request changes (1 MAJOR, judged below). Scope: origin/develop 77fa8f2..working tree, 3 files, single Haiku reviewer.
- R1-1 [MAJOR] init_db.py:1037 - a rebuild that fails after the RENAME leaves `<t>_old` owning the index names, so `IF NOT EXISTS` skips the new table's index and the comment "also when a rebuild failed" overclaims - Static - Deferred as pre-existing/out of scope (the plan lists the failed-copy `_old` leftover as out of scope; the fix, dropping index names before each RENAME in steps 8 and 11, changes the migration); the overclaiming comment and `_create_indexes` docstring were corrected to state the gap. Follow-up: drop a table's index names before its RENAME, or repair leftover `_old` tables.
- R1-2 [MINOR] test_init_db.py - no failure-path test - Static - Fixed (test where the files copy fails: init_db completes, messages rebuilt, other indexes present). It cannot show the R1-1 gap, which stays deferred.
- R1-3 [NIT] init_db.py:9 - no type hints/Args - Static - Fixed
Resolution: fixed 2, deferred 1 (documented). Checks: test_init_db.py 14 pass, `pytest backend tests` 931 pass + 10 baseline async failures, ruff clean. No runtime behaviour change (annotation, comments, test).

## Log
- 2026-11-09: created (follow-up found while planning MYAI-17 to MYAI-25)
- 2026-11-09: linked conflicts_with MYAI-25 (same step 11 re-create-indices branch)
- 2026-11-09: linked conflicts_with MYAI-6 (init_db step 11 definitions)
- 2026-11-09: plan validated, 1 Haiku round.
- 2026-11-09: linked conflicts_with MYAI-31 (step 11 rebuild loop and index re-creation)
- 2026-11-09: linked blocks MYAI-34
- 2026-11-09: autopilot started (batch-autopilot)
- 2026-11-09: implemented, smoke tests pass (only baseline async-plugin failures)
- 2026-11-09: verified live, 4/4 PASS
- 2026-11-09: review round 1: R1-1 MAJOR deferred as out of scope (documented gap), 2 fixed
- 2026-11-09: shipped, PR https://github.com/archit342000/My-AI/pull/65
- 2026-11-09: batch-autopilot: shipped, base develop
- 2026-11-09: closed, PR merged
