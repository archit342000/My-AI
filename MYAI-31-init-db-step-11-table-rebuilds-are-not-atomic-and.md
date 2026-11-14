---
id: MYAI-31
title: "init_db step 11 table rebuilds are not atomic and can leave _old tables"
status: done
created: 2026-11-09
updated: 2026-11-09
links:
  relates_to: [MYAI-48]
  blocks: [MYAI-34]
  conflicts_with: [MYAI-6, MYAI-25, MYAI-29]
---

## Description
Found while planning MYAI-29. Migration step 11 in `backend/database/init_db.py` (lines 920-1029) rebuilds `messages`, `files`, `sub_agent_messages`, `collections` and `pending_callbacks` to add ON DELETE CASCADE: rename to `<table>_old`, create, copy, drop. The rebuild isn't wrapped in its own transaction or savepoint (`docs/data.md` Migrations rule 3 says recreate inside one transaction), and its `except` only logs. A failure part-way (for example a NOT NULL violation in the copy) can leave `<table>_old` behind holding the data and the index names, with a new empty `<table>`, and later starts don't repair it.

## Acceptance criteria
- [x] Each table rebuild is atomic: on failure the original table and its data are unchanged
- [x] A leftover `<table>_old` from an earlier failed run is detected and repaired safely, or reported without data loss
- [x] Failures are logged with the table name and don't abort unrelated migrations
- [x] Migration tests cover a failing copy and a leftover `_old` table (run twice, and against a previous schema)

## Plan

**Date:** 2026-11-09  **Status:** Validated  **Base:** origin/develop 6a13e04

### Objective
Make each migration step 11 table rebuild in `init_db()` atomic, so a failure leaves the original table and its data untouched. Detect and safely repair `<table>_old` leftovers from earlier failed runs. Log failures with the table name without aborting the other migrations.

### Context
- Requirement: Description and Acceptance criteria above.
- Current step 11 (`backend/database/init_db.py:920-1029`). For each table in `dependent_tables` (`messages`, `files`, `sub_agent_messages`, `collections`, `pending_callbacks`) whose DDL lacks `ON DELETE CASCADE`:
  1. `ALTER TABLE x RENAME TO x_old`;
  2. `CREATE TABLE x`;
  3. `INSERT INTO x (...) SELECT ... FROM x_old`, using `x_old`'s columns;
  4. `DROP TABLE x_old`;
  5. re-create two indexes.
  The whole loop sits in one `try/except Exception` that only logs, and a failure stops the loop for the remaining tables.
- Transactions:
  - `init_db` uses one connection from `make_connection()` (`backend/database/db_layer.py:102`; WAL, `PRAGMA foreign_keys=ON`) and commits once at the end (line 1510).
  - Python 3.12's `sqlite3` legacy transaction mode opens a transaction implicitly only before DML, so the step 11 DDL isn't inside any transaction.
  - After a failed `INSERT`, the rename has already happened, and the final commit persists the half-done state: `x_old` holds the data and an empty new `x` exists. The index names stay attached to `x_old`.
- All five rebuilt tables reference only `chats(id)` (lines 937, 951, 970, 982, 998). Nothing references them, so no child foreign key is rewritten.
- Checked locally (Python 3.12.3, SQLite 3.45.1): with `PRAGMA foreign_keys=OFF` set outside a transaction, `SAVEPOINT rb` → `CREATE TABLE x_new` → `INSERT ... SELECT` → `DROP TABLE x` → `ALTER TABLE x_new RENAME TO x` → `RELEASE rb` works. On a NOT NULL failure in the copy, `ROLLBACK TO rb; RELEASE rb` leaves the original `x`, its rows and its index intact, with no `x_new` left. This is SQLite's documented table-rebuild order: new table, copy, drop old, rename new.
- `docs/data.md` Migrations:
  - rule 1: idempotent `init_db()`;
  - rule 3: recreate inside one transaction;
  - rule 4: never drop user data without an explicit decision;
  - rule 5: tests that run `init_db()` twice and against a previous schema.
- Linked (conflicts_with):
  - MYAI-29 adds `_create_indexes(c)` after step 11. With the new order (`x` is dropped, then `x_new` is renamed), the old indexes go with the dropped table, so the post-step call still matters.
  - MYAI-25 adds the `files` index in this block.
  - MYAI-6 changes the `messages` definition.
- Tests: `backend/database/tests/test_init_db.py` (`temp_db_path` fixture; pre-creation pattern at line 45; `test_db_schema_cascade_integrity` at 116).

### Approach
- **Per-table helper.** `_rebuild_table_with_cascade(conn, c, table, create_sql) -> bool`, at module level in `init_db.py`:
  1. Build `new_sql` by replacing the leading `CREATE TABLE <table>` with `CREATE TABLE <table>_new`. Use an anchored regex on the definition, which always starts `CREATE TABLE <name> (`.
  2. `SAVEPOINT rebuild_<table>`; `DROP TABLE IF EXISTS <table>_new` (leftovers); execute `new_sql`.
  3. Read the old columns with `PRAGMA table_info(<table>)` and the new ones with `PRAGMA table_info(<table>_new)` (after the CREATE, inside the savepoint). If any old column is missing from the new table, raise a `sqlite3.Error` (rule 4: never drop data silently). Otherwise copy exactly the old columns, by name: `INSERT INTO <table>_new (cols) SELECT cols FROM <table>`. New columns take their defaults.
  4. Save the old table's index definitions: `SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=? AND sql IS NOT NULL` (auto-indexes have NULL sql and come back with the constraints). Then `DROP TABLE <table>`, `ALTER TABLE <table>_new RENAME TO <table>`, and re-run each saved index statement. The indexes then exist again on success, in the same run, for every rebuilt table. Without this, the drop would lose them: MYAI-29's issue, fixed here for step 11.
  5. `RELEASE rebuild_<table>`; return True.
  6. On `sqlite3.Error` (narrowed from bare `Exception`, per `errors-and-logging.md`; the raise in item 3 uses this type too): `ROLLBACK TO rebuild_<table>`; `RELEASE rebuild_<table>`; `logger.error` and `log_event("db_migration_rebuild_error", {"table": ..., "error": type(e).__name__})`; return False. The original table is unchanged, and the next start retries.
- **Foreign keys off around the loop.** Before the loop, `conn.commit()` (end any implicit transaction, since the PRAGMA is ignored inside one), then `PRAGMA foreign_keys=OFF`. After the loop, run `PRAGMA foreign_key_check` and log any rows as an error (no rebuild should create violations, since the data is the same), then `PRAGMA foreign_keys=ON` in a `finally`.
  - The early `conn.commit()` makes steps 0-10 durable before step 11. That's already effectively true, since their DDL runs outside any transaction, so it doesn't change what can be rolled back.
- **Leftover repair, before the loop.** For each table `t` in `dependent_tables`, if `t_old` exists:
  - `t` is missing: rename `t_old` back to `t`.
  - `t` exists and is empty, and `t_old` has rows: inside a savepoint, drop the empty `t` and rename `t_old` to `t`. That's the state the old code left after a failed copy.
  - Both have rows: don't touch either. The rebuild of `t` can still run, because the helper uses `t_new` and never touches `t_old`, so there's no name collision. `logger.error` plus `log_event("db_migration_leftover_old_table_error", {"table": t, "rows_old": n})`, for manual resolution (rule 4).
  - `t_old` is empty: drop it.
  Repaired tables then go through the normal rebuild check.
- **Loop.** Call the helper for each table that needs it. One failure doesn't stop the others. Remove the outer `try/except` around the loop body, since the helper handles its own errors; keep one for an unexpected error in the repair or PRAGMA code, and log it.
- Rejected: wrapping the whole `init_db()` in one transaction. It's a much larger change, and SQLite PRAGMAs and some DDL inside it complicate things. Per-table savepoints meet rule 3 for this step.

### Steps
#### Step 1: Rebuild helper
- **Files:** `backend/database/init_db.py` (modify): add `from backend.logging import log_event` (init_db.py has none; same form as `backend/tools/clarify.py:2`); new `_rebuild_table_with_cascade` with a docstring (Args, Returns) and type hints.
- **Change:** as in Approach.
- **Verification:** Step 4 tests.

#### Step 2: Leftover repair
- **Files:** `backend/database/init_db.py` (modify): new `_repair_leftover_old_tables(conn, c, tables) -> None`, with a docstring.
- **Change:** as in Approach. Each repair runs in its own savepoint.
- **Verification:** Step 4 tests.

#### Step 3: Rewire step 11
- **Files:** `backend/database/init_db.py` (modify): the step 11 block.
- **Change:**
  - Keep `dependent_tables` as is.
  - Before the loop: commit, then foreign keys off.
  - Run the repair.
  - The loop calls the helper.
  - Then the foreign key check and foreign keys back on (`finally`).
  - Remove the old per-table index branch (lines 1021-1025): the helper now re-creates every index of a rebuilt table. If MYAI-29 has landed, its post-step-11 `_create_indexes` call stays as a harmless backstop.
- **Verification:** Step 4 tests; `init_db()` on a fresh DB still runs clean (`test_init_db`).

#### Step 4: Tests
- **Files:** `backend/database/tests/test_init_db.py` (modify).
- **Change:** pre-create tables before `init_db()` using the line 45 pattern, with a `chats` row `c1`.
  - **Atomic failure:** a pre-cascade `collections` (DDL copied from `dependent_tables`, without `ON DELETE CASCADE`) with one valid row and one row that violates a NOT NULL constraint of the new definition, inserted with foreign keys off and a looser old DDL.
    - Run `init_db()`. `collections` still has the old DDL and both rows, there's no `collections_new` or `collections_old`, and the other dependent tables were rebuilt (cascade present).
    - `log_event` was called with `db_migration_rebuild_error` (patch `backend.database.init_db.log_event`).
    - Run `init_db()` again: the same state, and no exception.
  - **Leftover repair:**
    - an empty `sub_agent_messages` plus a `sub_agent_messages_old` with two rows, which is what the old code left. After `init_db()`, one `sub_agent_messages` table (cascade) with the two rows and no `_old`;
    - `pending_callbacks_old` only (no `pending_callbacks`): renamed back, then rebuilt;
    - both with rows: both kept, the leftover event logged, and nothing dropped.
  - **Column safety:** an old table with an extra column that isn't in the new definition gives a failed rebuild (logged) with the original table untouched.
  - **Indexes on success:** after a rebuild of pre-cascade `sub_agent_messages` and `collections`, `idx_sub_agent_chat_parent`, `idx_sub_agent_sequence`, `idx_collections_chat_parent` and `idx_collections_parent_type` exist in the same run.
  - **Direct helper tests:** `_rebuild_table_with_cascade` on a small table returns True and preserves rows and indexes; on a NOT NULL failure it returns False with the table unchanged; with an extra old column it returns False. `_repair_leftover_old_tables` gets each of the four states directly.
  - **Idempotent:** the atomic-failure and leftover scenarios each run `init_db()` twice, with the same end state and no exception the second time. `test_init_db` (twice) and `test_db_schema_cascade_integrity` still pass.
- **Verification:** `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q backend/database`, then `... -m pytest -q backend`.

#### Step 5: Docs and full gate
- **Files:** `docs/data.md` (modify): under Migrations rule 3, one sentence saying table rebuilds use `_rebuild_table_with_cascade`'s order (new table, copy, drop, rename, inside a savepoint with foreign keys off) and that leftovers are repaired on start.
- **Change:**
  - Run `venv/bin/python -m ruff check .`, the `tests` suite in its own process, and `scripts/check.sh`.
  - Optional live check: copy a real `chats.db` with Python's `sqlite3` backup API to `/tmp/myai31/` (`mkdir -p` first; never write the live file), run `init_db()` against the copy with `DATA_DIR` pointed there, and check there are no `_old` or `_new` tables and the row counts are unchanged.
- **Verification:** all pass; results go in Verification.

### Tests
- Preconditions: a `venv` with `requirements.txt` and `requirements-dev.txt`.
- `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q backend`, then the same with `tests`.
- `venv/bin/python -m ruff check .`, then `scripts/check.sh`.

### Risks and open questions
- **Merge order.** This touches the same block as MYAI-6, 25 and 29. Land MYAI-29 first if possible, since its `_create_indexes` makes Step 3's index handling simpler, then rebase this one.
- **The early commit before step 11** makes steps 0-10 durable even if a later step raises. As noted, their DDL already autocommits, so the practical change is only for DML backfills in steps 0-10, which are idempotent.
- **"Both have rows" leftovers** need a manual decision. The plan reports them rather than guessing (rule 4).
- **`foreign_keys=OFF` window.** It's limited to step 11 and restored in `finally`. `init_db` runs at startup before request handling.
- No blocking open questions.

### Success criteria
- [ ] A failing rebuild leaves the original table, data and indexes unchanged; a successful one keeps every index (Step 4)
- [ ] Leftover `_old` tables are repaired when safe, and reported without data loss otherwise (Step 4)
- [ ] Failures are logged with the table name; other tables still migrate (Step 4)
- [ ] Idempotent and previous-schema tests pass; docs updated; all checks pass

### Validation log
- Round 1 (2026-11-09, Haiku): FAIL, 1 BLOCKING and 7 MINOR. My judgement: PASS after fixes.
  - B1: event names must end in `_error` (`errors-and-logging.md`). Valid. Renamed (`db_migration_rebuild_error`, `db_migration_leftover_old_table_error`). A text-only fix, so I'm marking this Validated without another round.
  - M2: column rule contradiction. Now explicit: read both PRAGMAs, raise if an old column is missing, copy the old columns by name.
  - M3: rename collision with a leftover `t_old`. Disproved: the new helper uses `t_new` and never renames to `_old`. Stated.
  - M4: indexes lost on success. Valid. The helper now saves and re-creates every index of the rebuilt table, with a test.
  - M5: direct helper tests. Added.
  - M6: run-twice for the new scenarios. Added.
  - M7: broad catch. Narrowed to `sqlite3.Error`.
  - M8: explicit import. Added.

## Implementation notes

### Autopilot run (2026-11-09)
Batch 4 item. Branch bugfix/atomic-table-rebuild from origin/develop 77fa8f2, PR base develop. Dirty files before start: none. The ticket's conflicting MYAI-29 is shipped as PR #65 (open, not merged), so this branch is based on develop without `_create_indexes`; the helper restores each rebuilt table's own indexes itself.

### Baseline (2026-11-09)
At develop 77fa8f2: backend/database 134 pass, 2 fail (test_cache_system subscribe_generator*, async plugin missing); backend + tests: only async-plugin failures.

### Implementation progress
- [x] Step 1: `_rebuild_table_with_cascade` (savepoint, new table, copy by name, drop, rename, saved indexes; narrowed to sqlite3.Error; log_event) in init_db.py
- [x] Step 2: `_repair_leftover_old_tables` (four states, each in a savepoint)
- [x] Step 3: step 11 rewired: commit, foreign keys off, repair, loop over the helper, foreign_key_check, foreign keys on in finally; old per-table index branch removed
- [x] Step 4: tests in test_init_db.py (failed rebuild atomic and others migrate, indexes kept, leftover repair via init_db twice, helper tests, repair tests)
- [x] Step 5: docs/data.md rule 3 sentence; ruff clean. scripts/check.sh not run as a whole (pytest-asyncio missing)
Deviation: a table repaired from `_old` (and rebuilt) has no indexes until the next start on this base, because the repair path has no saved index SQL (its indexes lived on the dropped empty table). PR #65's `_create_indexes` after step 11 closes this once both land.

### Smoke test (2026-11-09)
test_init_db.py 16 pass; `pytest backend tests` 933 pass, 10 fail (all async plugin, baseline); ruff clean. Defect shown against develop's init_db in a scratch module: a pre-cascade `collections` with an uncopyable row ends one run with `collections` empty and the data in `collections_old`.
None yet.

PR: https://github.com/archit342000/My-AI/pull/66, branch bugfix/atomic-table-rebuild, base develop

## Verification
### Verification plan (2026-11-09, full form: schema migration)
**Diff base:** origin/develop 77fa8f2. **Scope:** step 11 of `init_db()`: `_rebuild_table_with_cascade`, `_repair_leftover_old_tables`, the foreign-key window. Out of scope: wrapping the whole `init_db()` in one transaction; the optional copy of a real `chats.db` (the rule is to never touch a real chats.db, so it is not run).
**Environment and isolation:** the real app (`/tmp/gen/run_app.py`, port 5099) started by the script on throwaway `DATA_DIR`s `/tmp/myai31-ok`, `-fail`, `-left`, fake proxy on 5098. Never touch :5000/:5001, containers, `backend/data` or a real `chats.db`. Teardown: processes terminated by the script, /tmp/myai31-* removed; snapshots `/tmp/gen/*-before31.txt`.
Scripts: `scripts/v31.py`, `scripts/fake_proxy.py`.

| ID | Criterion | Scenario | Type | Method | Files | Expected |
|----|-----------|----------|------|--------|-------|----------|
| V1 | atomic rebuild keeps data and indexes; idempotent | pre-cascade messages, sub_agent_messages, collections, pending_callbacks with one row each: start the app, restart | happy | app + DB | init_db.py | cascaded, rows kept, every index present, no `_old`/`_new`; the restart changes nothing |
| V2 | failed copy leaves the original unchanged; others migrate; logged | collections with a NULL that the new NOT NULL rejects, plus other pre-cascade tables | failure | app + DB + log | init_db.py | collections keeps old DDL and both rows, no `_old`/`_new`; messages and pending_callbacks cascaded; error log names the table; same after a restart |
| V3 | leftover `_old` repaired or reported | empty sub_agent_messages + `_old` with rows; only `pending_callbacks_old`; collections and `collections_old` both with rows | edge | app + DB + log | init_db.py | first two restored and cascaded with their rows; the third kept as is and reported; restart stable |
| V4 | regression | backend, tests dirs, ruff | regression | CLI | all | only baseline async failures |
Not run yet.

### Results (2026-11-09)
**Commit verified:** 77fa8f29fe3eacd791cc522a129b2e47a95ef991 (+ uncommitted files)
Hashes: init_db.py d0b3a397, test_init_db.py 2c0412d6, docs/data.md 0cfd7bd6.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | v1-v3.log: API 200, all four tables cascaded with their row, no missing index, no `_old`/`_new`; restart: same index set, API 200 |
| V2 | PASS | v1-v3.log: collections keeps 2 rows and the old DDL after the first start and after a restart; messages and pending_callbacks cascaded with rows; error logged (app-fail-1.log) |
| V3 | PASS | v1-v3.log: sub_agent_messages restored with 2 rows, pending_callbacks restored with 1, collections 1 + collections_old 2 kept and reported ("hold rows"); restart stable |
| V4 | PASS (baseline) | test_init_db.py 16 pass; `pytest backend tests` 933 pass, 10 fail (all async plugin, baseline); ruff clean |

Notes: the before state is shown with develop's init_db in a scratch module (collections empty, data in `collections_old` after one run). Teardown: processes stopped, /tmp/myai31-* removed, ports 5098/5099 free, containers and git status unchanged. **Verdict: verified (4/4 PASS, 0 FAIL, 0 BLOCKED).** Gaps: no real production-size DB (not touched by rule); a table restored from `_old` has no indexes until the next start on this base (closed once PR #65 lands).

## Review history
### Round 1 - 2026-11-09
Verdict: Request changes (1 MAJOR). Scope: origin/develop 77fa8f2..working tree, 3 files, single Haiku reviewer.
- R1-1 [MAJOR] init_db.py:30-56,1107-1121 - ROLLBACK TO can raise when SQLite already ended the transaction, escaping the helper and leaving foreign_keys OFF (PRAGMA ignored inside a transaction) - Static - Fixed (`_abort_savepoint` guards on `conn.in_transaction`; the step-11 finally rolls back an open transaction before turning foreign keys on)
- R1-2 [MINOR] SAVEPOINT / exists() outside the try in both helpers - Static - Fixed (inside the try, table named in the log)
- R1-3 [MINOR] AUTOINCREMENT high-water mark (sqlite_sequence) not carried over by the rebuild - Static - Deferred as pre-existing: the old rename/create/copy/drop lost it the same way; follow-up: copy `seq` to the renamed table
- R1-4 [MINOR] `DROP TABLE IF EXISTS <t>_new` discards a pre-existing `_new` - Static - Rejected: `_new` is only ever created inside the helper's uncommitted savepoint, so a surviving one with rows cannot exist
- R1-5 [MINOR] the early commit changes what a later failure rolls back - Static - Fixed (comment and docs/data.md state it; earlier steps are idempotent, mostly DDL)
- R1-6 [MINOR] tests: foreign keys back on, real cascade, rollback branches - Static - Fixed in part (cascade-after-migration test added); the rolled-back-by-SQLite branch cannot be forced without mocking and is covered by the guard only
- R1-7 [MINOR] FK check only via logger, message scope - Static - Fixed (`db_migration_fk_check_error` event, reworded)
- R1-8 [NIT] docs/data.md wording "one transaction" vs savepoint - Static - Fixed ("per-table savepoint")
Resolution: fixed 6 (one partly), deferred 1, rejected 1. Checks: test_init_db.py 17 pass, `pytest backend tests` 934 pass + 10 baseline async failures, ruff clean. Runtime change: init_db.py; live V1-V3 re-run on throwaway DBs, all PASS (v1-v3-rerun.log).

## Log
- 2026-11-09: created (follow-up found while planning MYAI-29)
- 2026-11-09: linked conflicts_with MYAI-6 (step 11 dependent_tables definitions)
- 2026-11-09: linked conflicts_with MYAI-25 (step 11 rebuild loop)
- 2026-11-09: linked conflicts_with MYAI-29 (step 11 rebuild loop and index re-creation)
- 2026-11-09: plan validated, 1 Haiku round.
- 2026-11-09: linked blocks MYAI-34
- 2026-11-09: autopilot started (batch-autopilot)
- 2026-11-09: implemented, smoke tests pass (only baseline async-plugin failures)
- 2026-11-09: verified live, 4/4 PASS
- 2026-11-09: review round 1 Request changes (1 MAJOR); fixed 6, deferred 1, rejected 1; V1-V3 re-run PASS
- 2026-11-09: shipped, PR https://github.com/archit342000/My-AI/pull/66
- 2026-11-09: batch-autopilot: shipped, base develop
- 2026-11-09: linked relates_to MYAI-48 (follow-ups from batch 4)
- 2026-11-09: closed, PR merged
