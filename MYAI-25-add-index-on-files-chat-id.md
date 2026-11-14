---
id: MYAI-25
title: "Add an index on files.chat_id"
status: done
created: 2026-11-09
updated: 2026-11-09
links:
  conflicts_with: [MYAI-6, MYAI-29, MYAI-31]
  relates_to: [MYAI-8]
---

## Description
Found while planning MYAI-8. `files` has no `chat_id` index (only `idx_messages_chat_id` and `idx_file_systems_chat_id` exist in `backend/database/init_db.py`). MYAI-8's sidebar filter uses a correlated `EXISTS` on `files` per chat, and other lookups by chat also scan it. Adding the index is a migration under `docs/data.md`.

## Acceptance criteria
- [x] idx_files_chat_id exists on new and upgraded databases
- [x] The migration follows docs/data.md and is idempotent
- [x] Queries by chat_id use the index (EXPLAIN QUERY PLAN)

## Plan

**Date:** 2026-11-09  **Status:** Validated  **Base:** origin/develop 6a13e04

### Objective
Add `idx_files_chat_id` on `files(chat_id)` for new and upgraded databases, idempotently and following `docs/data.md`, so per-chat lookups (and MYAI-8's sidebar `EXISTS` filter) use an index instead of a table scan.

### Context
- Requirement: Description and Acceptance criteria above.
- `backend/database/init_db.py`:
  - `files` is created at line 240 (`chat_id TEXT NOT NULL`, with an FK to `chats` and `ON DELETE CASCADE`).
  - Step `# 3. Create Indexes` (lines 500-508) creates `idx_messages_chat_id`, `idx_file_systems_chat_id` and others with `CREATE INDEX IF NOT EXISTS`. There is none on `files`.
  - Step `# 11.` (line 920 onwards) rebuilds dependent tables that lack `ON DELETE CASCADE`. `files` is one of them: rename to `_old`, create, copy, drop. It runs after step 3, so a rebuild drops any index on the old table.
  - Step 11 re-creates only `idx_messages_chat_id` and `idx_pending_cb_chat` after a rebuild (lines 1021-1025). Without the same line for `files`, an upgraded DB would lose the new index on the migration run until the next start.
- Queries by `files.chat_id`:
  - `artifact_ops.py:29` (`SELECT * FROM files WHERE chat_id = ? ORDER BY created_at DESC`, `db.get_chat_files`, used by the chat router, the files manager and compression);
  - `chat_ops.py:347` (`DELETE FROM files WHERE chat_id = ?`);
  - MYAI-8's planned `EXISTS` subquery for the sidebar.
- `docs/data.md` Migrations:
  1. idempotent `init_db()`;
  5. a test that runs `init_db()` twice and against a database from the previous schema.
  - `docs/data.md` doesn't list indexes; `init_db.py` is the authority.
- Tests: `backend/database/tests/test_init_db.py` (`test_init_db`, `test_init_db_with_legacy_data`, `test_db_schema_cascade_integrity`).
- Rules: `docs/standards/testing.md` (separate suites, env vars); `AGENTS.md`.

### Approach
- Add `c.execute('CREATE INDEX IF NOT EXISTS idx_files_chat_id ON files(chat_id)')` to step 3, after `idx_messages_chat_id`. That covers new and already-cascaded databases on every start.
- In step 11's "Re-create indices" branch, add `elif table_name == 'files':` with the same statement, so a database rebuilt in that run keeps the index.
- Single-column index only. `get_chat_files` sorts by `created_at`, so a composite `(chat_id, created_at)` index would also serve the sort. But the ticket asks for `chat_id`, and the volumes are single-user. Noted under Risks.
- Rejected: a separate numbered migration step. `CREATE INDEX IF NOT EXISTS` in step 3 is already idempotent and matches how the other indexes are created.

### Steps
#### Step 1: Create the index
- **Files:** `backend/database/init_db.py` (modify): step 3 index block, and step 11's "Re-create indices" branch.
- **Change:** as in Approach.
- **Verification:** Step 2 tests.

#### Step 2: Tests
- **Files:** `backend/database/tests/test_init_db.py` (modify).
- **Change:**
  - `test_init_db` (fresh DB, `init_db()` twice): assert `idx_files_chat_id` is in `SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='files'`.
  - New `test_init_db_files_index_survives_cascade_rebuild`:
    1. Before any `init_db()`, create a minimal `chats` table and row, copying the pattern at `test_init_db.py:45` (connections enforce foreign keys, `db_layer.py:126, 153`). Then create a `files` table without `ON DELETE CASCADE` (columns as at line 240, FK without CASCADE) and insert a `files` row.
    2. Run `init_db()` once. `CREATE TABLE IF NOT EXISTS files` leaves the table alone, and the step 11 detector (`"ON DELETE CASCADE" not in current_sql`, line 1008) rebuilds it. Assert that the `files` DDL in `sqlite_master` now contains `ON DELETE CASCADE` (so the rebuild really ran, exercising the new branch), that the index exists, and that the row survived.
    3. Run `init_db()` again and assert it still exists.
  - New `test_files_chat_id_query_uses_index`: after `init_db()`, `EXPLAIN QUERY PLAN SELECT * FROM files WHERE chat_id = ?` contains `USING INDEX idx_files_chat_id`.
- **Verification:** `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q backend/database`, then `... -m pytest -q backend` (its own process).

#### Step 3: Full gate
- **Change:**
  - Run `venv/bin/ruff check .`, the `tests` suite in its own process, and `scripts/check.sh`.
  - Optional live check (it doesn't gate this step): run `mkdir -p /tmp/myai25`, then back up the live DB with `venv/bin/python -c "import sqlite3; s=sqlite3.connect('/home/archit-anand/docker-data/shared/My-AI-data/chats.db'); d=sqlite3.connect('/tmp/myai25/chats.db'); s.backup(d)"`. That's the `DATA_DIR` the compose app mounts; confirm the file name in that directory first. Never write to the live file. Run `init_db()` against the copy with `DATA_DIR` pointed at it, and check `PRAGMA index_list(files)` lists `idx_files_chat_id`.
  - No docs change: `docs/data.md` doesn't list indexes, and `init_db.py` is the authority. The Description calls this a migration under `docs/data.md`; the plan meets its rules (idempotent, tested twice and against a previous schema) but adds no text there.
- **Verification:** all pass; results go in Verification.

### Tests
- Preconditions: a `venv` with `requirements.txt` and `requirements-dev.txt`.
- `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q backend`, then the same with `tests`.
- `venv/bin/ruff check .`, then `scripts/check.sh`.

### Risks and open questions
- **Step 11 index gap.** Step 11 rebuilds only `messages`, `files`, `sub_agent_messages`, `collections` and `pending_callbacks`, and re-creates indexes only for `messages` and `pending_callbacks` (plus `files` after this change). `idx_sub_agent_chat_parent` and `idx_sub_agent_sequence` are lost on a `sub_agent_messages` rebuild until the next start. If more tables are ever added to step 11, they have the same gap. That's pre-existing and out of scope. Possible follow-up: re-run the step 3 block after step 11.
- **Composite index.** `(chat_id, created_at)` would also serve `get_chat_files`' `ORDER BY`. Not needed at current volumes.
- **Index build time on a large `files` table** is a one-off at startup. It is negligible for single-user data.
- No blocking open questions.

### Success criteria
- [ ] `idx_files_chat_id` exists on new and upgraded databases, including right after a step 11 rebuild (Step 2)
- [ ] The migration is idempotent and follows `docs/data.md` (`init_db()` twice, plus the previous-schema test)
- [ ] `EXPLAIN QUERY PLAN` for a `chat_id` lookup uses the index (Step 2)
- [ ] All checks pass

### Validation log
- Round 1 (2026-11-09, Haiku): FAIL, 1 BLOCKING and 9 MINOR. My judgement: PASS after fixes.
  - B1: no `chats` table before the FK-enforced insert. Valid (db_layer.py:126, 153). Fixed by copying the test_init_db.py:45 pattern.
  - M2: the test didn't prove the rebuild ran. Added a DDL `ON DELETE CASCADE` assertion.
  - M3: trigger facts. Stated.
  - M4: placeholder path and missing dir. Fixed.
  - M5: named the query-plan test.
  - M6: the Description's "migration" wording is reconciled.
  - M8: the risk is now about current behaviour. I checked the `dependent_tables` list and corrected it, since `sub_agent_messages` really does lose its indexes.
  - M10: the live check is optional and doesn't gate.
  - M7 and M9: confirmations, no change.
  The B1 fix copies an existing test pattern and I checked it in the repo, so I'm marking this Validated without another round.

## Implementation notes

### Autopilot run (2026-11-09)
Batch 5 item. Branch bugfix/files-chat-id-index from origin/develop a1a9333, PR base develop. Dirty files before start: none. The plan predates MYAI-29/31: develop now has `_create_indexes` (all index statements, also run after step 11) and an atomic step 11, so the index is added there and the step 11 re-create branch the plan mentions no longer exists.

### Baseline (2026-11-09)
At develop a1a9333: backend/database 150 pass, 2 fail (test_cache_system subscribe_generator*, async plugin missing); backend + tests only async-plugin failures.

### Implementation progress
- [x] Step 1: `idx_files_chat_id` added to `_create_indexes` in init_db.py
- [x] Step 2: tests: `files` added to EXPECTED_INDEXES (fresh DB, legacy DB, rebuild tests), EXPLAIN QUERY PLAN test, pre-cascade files rebuild test (init_db twice)
- [x] Step 3: ruff clean; no docs change (docs/data.md does not list indexes). The optional live check on a copy of the real DB was not run (never touch a real chats.db); throwaway old-schema DBs used instead. scripts/check.sh not run as a whole (pytest-asyncio missing)

### Smoke test (2026-11-09)
test_init_db.py 22 pass; `pytest backend tests` 951 pass, 10 fail (all async plugin, baseline); ruff clean.
None yet.

PR: https://github.com/archit342000/My-AI/pull/70, branch bugfix/files-chat-id-index, base develop

## Verification
### Verification plan (2026-11-09, light form: one index)
Real app (5099), throwaway `DATA_DIR`s /tmp/myai25-fresh and -old, fake proxy 5098, `scripts/v25.py`. Never touches :5000/:5001, containers, backend/data or a real chats.db.
| ID | Criterion | Scenario | Expected |
|----|-----------|----------|----------|
| V1 | AC1 | fresh DB, app start | `idx_files_chat_id` exists |
| V2 | AC1, AC2 | old-schema DB (pre-cascade `files` with a row): first start, restart | index exists after the FIRST start, files cascaded, row kept, restart changes nothing |
| V3 | AC3 | EXPLAIN QUERY PLAN | lookup by chat_id and the sidebar EXISTS both use the index |
Not run yet.

### Results (2026-11-09)
**Commit verified:** a1a9333 (+ uncommitted). Hashes: init_db.py 971dd65b, test_init_db.py f31c562e.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | v1-v3.log: fresh start API 200, index present |
| V2 | PASS | v1-v3.log: old schema had no index; after the first start index present, `files` cascaded, 1 row kept; restart stable |
| V3 | PASS | v1-v3.log: `SEARCH files USING INDEX idx_files_chat_id (chat_id=?)`; the sidebar EXISTS uses `COVERING INDEX idx_files_chat_id` |

Teardown: processes stopped, /tmp/myai25-* removed, ports free, containers unchanged. **Verdict: verified (3/3 PASS).** Gap: no real production-size DB.

## Review history
### Round 1 - 2026-11-09
Verdict: Approve with comments. Scope: origin/develop a1a9333..working tree, 2 files, single Haiku reviewer.
- R1-1 [MINOR] failed-rebuild test skipped the `files` index check - Static - Fixed (guard removed)
- R1-2 [MINOR] EXPLAIN test covered one of the three chat_id queries - Static - Fixed (parametrized: get_chat_files, delete, sidebar EXISTS)
- R1-3 [MINOR] no test for the develop-shaped `files` table (cascade, no index) - Static - Fixed (init_db twice, index added, no rebuild leftovers)
Resolution: fixed 3. Checks: test_init_db.py 25 pass, ruff clean. No runtime change (tests only), so no re-verify.

## Log
- 2026-11-09: created (follow-up found while planning MYAI-2 to MYAI-16)
- 2026-11-09: plan validated, 1 Haiku round.
- 2026-11-09: linked conflicts_with MYAI-6 (init_db step 11 dependent-table definitions)
- 2026-11-09: linked relates_to MYAI-8 (the index serves MYAI-8's sidebar EXISTS filter)
- 2026-11-09: linked conflicts_with MYAI-29 (same step 11 re-create-indices branch)
- 2026-11-09: linked conflicts_with MYAI-31 (step 11 rebuild loop)
- 2026-11-09: autopilot started (batch-autopilot)
- 2026-11-09: implemented, smoke tests pass
- 2026-11-09: verified live, 3/3 PASS
- 2026-11-09: review round 1 Approve with comments; fixed 3
- 2026-11-09: shipped, PR https://github.com/archit342000/My-AI/pull/70
- 2026-11-09: batch-autopilot: shipped, base develop
- 2026-11-09: closed, PR merged
