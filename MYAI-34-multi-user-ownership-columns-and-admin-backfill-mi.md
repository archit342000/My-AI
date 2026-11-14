---
id: MYAI-34
title: "Multi-user: ownership columns and admin backfill migration"
status: done
created: 2026-11-09
updated: 2026-11-10
links:
  blocks: [MYAI-35, MYAI-36, MYAI-42]
  blocked_by: [MYAI-29, MYAI-31, MYAI-33]
  split_from: [MYAI-32]
---

## Description
Split from MYAI-32 (Step 2: Ownership schema and backfill). Part of making My-AI multi-user behind Cloudflare Access. Implement after MYAI-1 to MYAI-31 have merged.

Read the MYAI-32 Plan first: the Audit (single-user assumptions with file references), the Approach, the Decisions and the Reviewer brief are binding for this ticket. Step scope from MYAI-32:

- **Depends on:** MYAI-33
- **Files:** `backend/database/init_db.py` (modify): add `user_id TEXT DEFAULT NULL` to `workspaces`, `chats`, `personas`, `skills` and `memories`, backfilled to the admin in the same step; rebuild `skills` with `UNIQUE(user_id, name)` through `_rebuild_table_with_cascade`; add `idx_<table>_user_id` in `_create_indexes`. `backend/database/tests/test_init_db.py` (modify). `docs/data.md` (modify): `users`, ownership model, fix the stale RAG collection list.
- **Change:** columns are added with `PRAGMA table_info` checks and a default (rule 2), then backfilled. There is no schema-level `NOT NULL` or foreign key on `user_id`. Wrapper inserts require a non-empty `user_id`, and a test asserts that no root row has a NULL owner after `init_db()`. A database without an admin seed stops startup with a clear error rather than leaving ownerless rows.
- **Verification:** migration tests run from a pre-change schema with data (no row lost, every root row owned by the admin, skills uniqueness now per user), and again on an already-migrated database (idempotent).

## Acceptance criteria
- [x] `user_id TEXT DEFAULT NULL` is on `workspaces`, `chats`, `personas`, `skills` and `memories`, and every existing row is backfilled to the admin without loss
- [x] `skills` is unique on `(user_id, name)`, rebuilt with `_rebuild_table_with_cascade`; the new indexes are in `_create_indexes`
- [x] `init_db()` is idempotent: tested twice and from the previous schema with data
- [x] `docs/data.md` describes `users`, the ownership model and the real RAG collections
- [x] Tests pass and `ruff check .` is clean

## Plan
**Date:** 2026-11-09  **Status:** Validated

### Objective
Give every root row an owner. Add `user_id` to `workspaces`, `chats`, `personas`, `skills` and `memories`, backfill existing rows to the admin seeded by MYAI-33, make skill names unique per user, and index the new column. All of this goes through idempotent `init_db()` migrations that lose no data. This ticket changes the schema only; the wrapper and route scoping is MYAI-35 to MYAI-37.

### Context
- **Requirement:** this ticket's Description and Acceptance criteria. MYAI-32 Plan: Audit item 2, Approach "Ownership lives on the root tables only", Step 2.
- **Assumes merged:**
  - MYAI-33: the `users` table in step 1, with the admin seeded from `config.ADMIN_EMAIL` in its admin-seed block.
  - MYAI-31: `_rebuild_table_with_cascade(conn, c, table, create_sql) -> bool`. It builds `<table>_new` inside a savepoint, copies every old column by name (new columns take their defaults), refuses if an old column would be lost, re-creates the saved non-auto indexes, and on `sqlite3.Error` rolls back, logs `db_migration_rebuild_error` and returns False.
  - MYAI-29: `_create_indexes(c)`, called in step 3's place and again after step 11.
  - MYAI-24: step 14.
  - MYAI-9: name checks are application-level, with no `UNIQUE` on workspace or persona names.
- **Current schema** (`backend/database/init_db.py`):
  - `workspaces` (45), `personas` (54, its column additions at 68-99), `chats` (102), `memories` (255), and `skills` (316) with `name TEXT UNIQUE`.
  - Step 2 "Perform Migrations (Column Additions)" starts at 382 and runs before step 3 "Create Indexes" (500).
  - Step 8 inserts `workspaces` rows for legacy folders (806); those rows get a NULL `user_id` until the backfill.
  - `conn.commit()` is at 1510.
- **Rules:** `docs/data.md` Migrations:
  1. `IF NOT EXISTS`.
  2. `PRAGMA table_info`, then `ADD COLUMN` with a default.
  3. Constraint changes rebuild the table in one transaction.
  4. Backfill in the same step; never drop data.
  5. A test that runs `init_db()` twice and from the previous schema.
  Also `AGENTS.md` 5 (no masked errors) and `docs/standards/testing.md`.
- **Docs drift to fix here:** `docs/data.md:11` says ChromaDB holds "file, research and preference RAG", but only `file_store` exists (`backend/rag/file_rag.py:26`). `docs/data.md:21` lists no `users` table; MYAI-33 didn't touch `data.md`.

### Approach
- **Fresh databases:** the `CREATE TABLE IF NOT EXISTS` statements for the five tables gain `user_id TEXT DEFAULT NULL`. The `skills` definition changes `name TEXT UNIQUE` to `name TEXT` plus a table constraint `UNIQUE(user_id, name)`.
- **Existing databases, column:** step 2 gets one loop over the five tables. For each, if `user_id` isn't in `PRAGMA table_info`, it runs `ALTER TABLE <t> ADD COLUMN user_id TEXT DEFAULT NULL` (rule 2). This runs before step 3, so the new indexes can be created there.
- **Indexes:** `_create_indexes` gains `idx_workspaces_user_id`, `idx_chats_user_id`, `idx_personas_user_id`, `idx_skills_user_id` and `idx_memories_user_id`.
- **Backfill and skills constraint:** a new numbered block, "Assign owners", runs right after MYAI-33's admin-seed block and before `conn.commit()`. It's numbered after whatever block is last at implementation time, as MYAI-24 does; this plan calls it "the owner block":
  1. Count rows with `user_id IS NULL` across the five tables.
  2. If there are any, look up the admin (`SELECT id FROM users WHERE email = ? AND role = 'admin'`, with `config.ADMIN_EMAIL`).
     - No admin while ownerless rows exist: raise `RuntimeError("Ownerless rows exist and no admin user is configured; set ADMIN_EMAIL")`, which stops startup (no masked error, `AGENTS.md` 5).
     - Otherwise `UPDATE <t> SET user_id = ? WHERE user_id IS NULL` for each table, logging the count per table (`log_event("db_migration_owner_backfill", {"table": t, "rows": n})`).
  3. If `skills` still has a single-column unique index on `name` (detected with `PRAGMA index_list(skills)` plus `PRAGMA index_info`), call `_rebuild_table_with_cascade(conn, c, "skills", SKILLS_TABLE_SQL)`.
     - On False, raise `RuntimeError`. The helper has already rolled back and logged it, and starting with the old global constraint would make per-user skill creation fail confusingly.
     - The step runs on every start, so ownerless rows created before MYAI-35 and MYAI-36 make inserts owner-aware are assigned to the admin at the next start. That's harmless while the admin is the only user (MYAI-33's Risks).
- **The wrapper requirement moves out:** the Description's "wrapper inserts require a non-empty `user_id`" belongs to MYAI-35 (`chat_ops`) and MYAI-36 (persona, skill and preference ops), which change those methods. This ticket only migrates the schema.
- **No `NOT NULL` or foreign key on `user_id`:** adding either needs a rebuild of every root table, including `chats`, with its many children. The wrapper requires an owner on insert from MYAI-35 and MYAI-36 onwards, and the owner block plus a test assert there are no NULL owners.
- **Rejected:**
  - Rebuilding all five tables to add `NOT NULL REFERENCES users(id)`: a large, risky migration for constraints the wrapper enforces anyway.
  - Backfilling in step 2: the admin row doesn't exist until the admin-seed block.
  - A partial unique index `ON skills(user_id, name)` while keeping the old `UNIQUE(name)`: the old constraint would still block two users from sharing a skill name.

### Out of scope
Owner-aware wrapper methods and routes (MYAI-35 to MYAI-37); per-user default persona semantics (MYAI-36); any child-table column.

### Steps
#### Step 1: Fresh schema
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/database/init_db.py` (modify): the `CREATE TABLE IF NOT EXISTS` statements for `workspaces`, `personas`, `chats`, `memories` and `skills`.
- **Change:** add `user_id TEXT DEFAULT NULL` to each; on `skills`, replace `name TEXT UNIQUE` with `name TEXT` plus `UNIQUE(user_id, name)`. Keep the `skills` DDL in a module-level constant, `SKILLS_TABLE_SQL`, whose text starts exactly `CREATE TABLE skills (`, with no leading newline or indentation (write it as a plain string, not an indented triple-quoted block, or apply `.strip()`) (the form MYAI-31's helper's anchored regex expects). The fresh-schema statement runs `SKILLS_TABLE_SQL.replace("CREATE TABLE skills (", "CREATE TABLE IF NOT EXISTS skills (", 1)` (rule 1). The owner block passes `SKILLS_TABLE_SQL` unchanged to the helper.
- **Verification:** a fresh `init_db()` gives tables whose `PRAGMA table_info` includes `user_id`; inserting `(user_id='a', name='x')` and `(user_id='b', name='x')` works; inserting `('a','x')` twice raises `IntegrityError`.

#### Step 2: Column migration and indexes
- **Status:** todo
- **Depends on:** 1
- **Files:** `backend/database/init_db.py` (modify): step 2 (the loop) and `_create_indexes` (five indexes).
- **Change:** as in Approach.
- **Verification:** on a database created with the pre-change DDL, `init_db()` adds the column to all five tables and the five indexes exist; a second run changes nothing.

#### Step 3: Owner backfill and skills rebuild (the owner block)
- **Status:** todo
- **Depends on:** 2
- **Files:** `backend/database/init_db.py` (modify): new block `# <N>. Assign owners to root rows and make skill names unique per user`, where `<N>` is the next free block number, placed after MYAI-33's admin-seed block and before `conn.commit()`. It uses `log_event` (imported by MYAI-31) and `config` (imported by MYAI-33 as `from backend import config`); a module-level helper `_assign_owners(conn, c) -> None` with a docstring, holding the logic so it's testable.
- **Change:** as in Approach.
- **Verification:** the existing `backend/database/tests/test_init_db.py` tests pass (a fresh database has no ownerless rows, so the block is a no-op there). Full coverage is in Step 4.

#### Step 4: Migration tests
- **Status:** todo
- **Depends on:** 3
- **Files:** `backend/database/tests/test_init_db.py` (modify).
- **Change:** new tests that use `patch.object(backend.config, "ADMIN_EMAIL", "admin@test")` (init_db reads `config.ADMIN_EMAIL` through `from backend import config`) and patch `backend.database.init_db.log_event`:
  - **From the previous schema:** create the five tables with their current DDL (skills with `name TEXT UNIQUE`), insert two rows each (including a skill), and run `init_db()`. Every row is kept with its values, has `user_id` equal to the admin's id, and the skills table now has `UNIQUE(user_id, name)`, no single-column unique index on `name`, and `idx_skills_user_id` still exists.
  - **Twice:** a second `init_db()` gives the same row counts and owners, makes no rebuild call (patch `_rebuild_table_with_cascade` and assert it isn't called), and logs no backfill event.
  - **Fresh database:** `init_db()` twice raises nothing, and there are no NULL owners.
  - **NULL rows after the migration:** insert a chat with a NULL `user_id`, run `init_db()`, and it's owned by the admin.
  - **No admin configured:** with `ADMIN_EMAIL` unset and an ownerless row, `init_db()` raises `RuntimeError`; with no ownerless rows, it doesn't raise.
  - **Rebuild failure:** starting from the previous schema (skills with `name TEXT UNIQUE`), patch `_rebuild_table_with_cascade` to return False, and `init_db()` raises `RuntimeError`.
  - **`_assign_owners` directly:** counts and updates only NULL rows.
- **Verification:** `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q backend/database`, then `pytest -q backend`. The existing `test_init_db`, `test_init_db_with_legacy_data` and MYAI-29/31 tests still pass.

#### Step 5: Docs and full gate
- **Status:** todo
- **Depends on:** 4
- **Files:**
  - `docs/data.md` (modify):
    - Line 11: the only collection written is `file_store` (file RAG). `RAGManager.drop_all_collections` (`backend/rag/manager.py:114`) still names a legacy `research_store`.
    - Line 21: add `users` to the table list.
    - A short "Ownership" paragraph: `user_id` on the five root tables; child tables inherit through `chat_id` or `workspace_id`; the owner block assigns ownerless rows to the admin and stops startup if there's no admin; skill names are unique per user.
  - `backend/database/README.md` (modify, only if it lists tables or migration steps; check while implementing and record the result in Implementation notes).
- **Change:** docs match the code.
- **Verification:** `pytest tests` (docs guardrails), `pytest backend` and `ruff check .` pass.

### Tests
`backend/database/tests/test_init_db.py` as in Step 4. Commands: the env from `docs/standards/testing.md`, then `pytest backend/database`, `pytest backend`, `pytest tests`; `ruff check .`.

### Risks and open questions
- **The skills rebuild on a large table runs inside one savepoint.** That's fine at this data volume, and the helper rolls back on failure.
- **Startup now fails if ownerless data exists without `ADMIN_EMAIL`.** That's intended (MYAI-33 already makes `ADMIN_EMAIL` required in `validate_auth_config`). Recovery is to set it and restart.
- **Ownerless inserts between this merge and MYAI-35 and MYAI-36** belong to the admin until the next start. That's acceptable while the admin is the only user; don't add other users before MYAI-37.

### Success criteria
- [x] All five root tables have `user_id` on fresh and migrated databases, with the five indexes.
- [x] Existing rows are owned by the admin after the first start, with no row or value lost.
- [x] Skill names are unique per user, not globally.
- [x] `init_db()` is idempotent, tested twice and from the previous schema.
- [x] Startup stops with a clear error when ownerless rows exist and no admin is configured.
- [x] `docs/data.md` is updated; tests pass and `ruff check .` is clean.

### Reviewer brief
- **Objective:** add `user_id` to `workspaces`, `chats`, `personas`, `skills` and `memories`; backfill existing rows to the admin; make skill names unique per user. Schema only; no wrapper or route changes.
- **Key decisions:**
  - `user_id TEXT DEFAULT NULL`, added with `ADD COLUMN` in step 2. No `NOT NULL` or foreign key, so no rebuild of the root tables.
  - Five `idx_<table>_user_id` indexes in `_create_indexes`.
  - A new "owner block" runs after MYAI-33's admin-seed block and before `conn.commit()`, numbered at implementation time. `_assign_owners` assigns NULL owners to the admin on every start, logs `db_migration_owner_backfill`, and raises `RuntimeError` if ownerless rows exist with no admin.
  - Skills are rebuilt once with MYAI-31's `_rebuild_table_with_cascade` and `SKILLS_TABLE_SQL` (a plain string starting `CREATE TABLE skills (`, giving `UNIQUE(user_id, name)`); a failed rebuild raises.
  - "Wrapper inserts require `user_id`" moves to MYAI-35 and MYAI-36.
  - `docs/data.md`: the `users` table, an ownership paragraph, and the RAG collection line corrected.
- **Out of scope:** owner-aware wrapper methods and routes, per-user default persona semantics, child-table columns.
- **Success criteria:** as listed in the Plan.

The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- **Round 1:** the validator returned FAIL (1 BLOCKING, 7 MINOR). My judgement: FAIL.
  - The BLOCKING issue was valid: an `IF NOT EXISTS` skills DDL string doesn't match MYAI-31's anchored regex. Now one constant, `SKILLS_TABLE_SQL`, starts `CREATE TABLE skills (`, and the fresh-schema statement is derived from it.
  - The MINOR issues, all valid and fixed: the wrapper requirement moved to MYAI-35 and MYAI-36; the `research_store` caveat in `data.md`; the `log_event` and `config` imports named (MYAI-33 amended to add the `config` import); the patch target pinned; a standalone check for Step 3; numbering at implementation time, as MYAI-24 does (MYAI-33's seed block amended the same way); `idx_skills_user_id` asserted after the rebuild.
- **Round 2 (diff-scoped):** the validator returned PASS (0 BLOCKING, 3 MINOR). My judgement: PASS; the BLOCKING issue is confirmed fixed. The MINOR issues, fixed: no leading whitespace in `SKILLS_TABLE_SQL`; the rebuild-failure test starts from the previous schema; the wrapper-requirement move recorded in the Log.

## Implementation notes
### Autopilot run (2026-11-09)
- Mode: automatic (batch-autopilot item 4/13)
- Branch: feature/multi-user-ownership-columns  PR base: feature/multi-user-identity-access-jwt (stacked on MYAI-33's PR)  Starting commit: 0c5c989ef5247e07dacf5d0de60c8452228924f3
- Dirty before start: none
- Work files: backend/database/init_db.py, backend/database/tests/test_init_db.py, docs/data.md, backend/database/README.md
- Counters: fix 0/10, review 5/5, re-verify 4
- Last completed stage: 5 review round 1 resolved + re-verify PASS  Next: done (shipped)
- Hard blocker: none
- WIP commit: none

### Autopilot decisions (2026-11-09)
- Plan already validated (2 rounds); stage 1 skipped.
- Stacked on the MYAI-33 branch (blocked_by 33; MYAI-29/31 already merged on develop).
- Deviation: `_rebuild_table_with_cascade` takes `(conn, table, create_sql)` in the merged code (the Plan wrote `(conn, c, ...)`); used as merged.
- Decision: guard against ownerless duplicates with trigger `trg_skills_unowned_name` (first a partial unique index, replaced in review round 2). `UNIQUE(user_id, name)` treats NULL owners as distinct, so until MYAI-36 makes the wrapper set an owner, duplicate skill names would be allowed and the next-start backfill would then hit an IntegrityError. The partial index keeps names unique among ownerless rows. MYAI-36 may drop it. Detection of the old global constraint ignores partial indexes.
- Decision: the existing init_db tests that insert legacy rows now run with an autouse `ADMIN_EMAIL` patch, since ownerless rows without an admin stop startup by design.

### Baseline (2026-11-09)
`pytest backend/database`: 2 failed (test_cache_system subscribe_generator x2; async-plugin), 165 passed. `pytest backend`: 10 failed (same 2 + research_utils x2 + code_executor x6).

### Implementation progress
- [x] Step 1: Fresh schema - init_db.py (user_id on five tables; `SKILLS_TABLE_SQL`)
- [x] Step 2: Column migration and indexes - init_db.py (loop before step 3; five `idx_<t>_user_id` + partial unowned-skill index in `_create_indexes`)
- [x] Step 3: Owner block - `_assign_owners` and `_skills_name_is_globally_unique`; block 16 after the admin seed
- [x] Step 4: Migration tests - test_init_db.py (10 new tests)
- [x] Step 5: Docs - docs/data.md (users line already by MYAI-33; ownership paragraph; RAG collection fix), backend/database/README.md (checked: lists init_db symbols, updated)
- Branch: feature/multi-user-ownership-columns

### Smoke test (2026-11-09)
`pytest backend/database`: 2 failed (baseline), 175 passed. `pytest backend tests`: 10 failed (baseline), 1287 passed. `ruff check .`: clean.

PR: https://github.com/archit342000/My-AI/pull/87, branch feature/multi-user-ownership-columns, base feature/multi-user-identity-access-jwt

## Verification

### Verification plan and results (2026-11-09, full form for a migration)
Isolation: throwaway DATA_DIR in /tmp; the previous-schema database is produced by the stacked base's own `init_db` run from a temporary worktree of the base branch (removed), then the NEW code runs on it. Scripts: `MYAI-34-evidence/scripts/seed_old.py`, `check_new.py`; outputs `seed-output.txt`, `migrate-output.txt`.
| ID | Criterion | Scenario | Status |
|----|-----------|----------|--------|
| V1 | columns + backfill, no loss | old DB with 2 rows in each of 5 tables + 3 messages -> new init_db: all rows kept, all 10 root rows owned by the single admin, messages 3, FK violations 0 | PASS |
| V2 | skills unique per user | skills DDL is `UNIQUE(user_id, name)`; same name for another user allowed, same user twice -> IntegrityError | PASS |
| V3 | indexes | the five `idx_<t>_user_id` + `idx_skills_name_unowned` exist | PASS |
| V4 | idempotent | `init_db()` ran twice in the same process on the old DB with no error or change; unit test proves no rebuild and no backfill event on the second run | PASS |
| V5 | startup stops without admin | unit test: ownerless rows + no ADMIN_EMAIL -> RuntimeError; failed skills rebuild -> RuntimeError | PASS (unit) |
| V6 | regression | `pytest backend` baseline failures only; ruff clean; docs guardrails pass | PASS |
Verdict: verified (6/6). V5 is covered by unit tests only (destructive startup failure); not run live.

## Review history





### Round 5 - 2026-11-09
Verdict: Approve with comments (no BLOCKER/MAJOR). Scope: same change, 1 Haiku reviewer (iteration 5 of 5).
- R5-1 [MINOR] test_init_db.py:1154 - skills rebuild-failure test mocks the helper - Static - Rejected: the helper's real savepoint rollback is covered by existing tests (`test_failed_rebuild_leaves_the_original_table_unchanged...`, `test_rebuild_helper_keeps_rows_and_indexes_and_rolls_back_failures`)
- R5-2 [MINOR] test_init_db.py:1052 - setup insert inside the `pytest.raises` block - Static - Fixed
- R5-3 [MINOR] docs/data.md:24 - second startup-stop condition undocumented - Static - Fixed
- R5-4 [NIT] init_db.py - `_assign_owners` docstring lacked Raises - Static - Fixed
Resolution: 3 Fixed, 1 Rejected; tests/docs/docstring only (no re-verify needed). `pytest backend` 10 failed (baseline), 1297 pass; ruff clean. Review loop ended clean at the cap (5/5).

### Round 4 - 2026-11-09
Verdict: Request changes (1 MAJOR). Scope: same change, 1 Haiku reviewer.
- R4-1 [MAJOR] init_db.py:143 - the BEFORE INSERT guard also fired on the wrapper's `INSERT ... ON CONFLICT(id) DO UPDATE` of an existing owned skill when another user shares the name (the wrapper's NEW.user_id is NULL), blocking a legitimate edit - Static (reviewer probed) - Fixed: INSERT trigger skips ids that already exist (the UPDATE trigger covers renames); tests (two users share a name, wrapper upsert; rename via upsert still caught); live: edit allowed, new ownerless clash blocked
- R4-2 [MINOR] test_init_db.py:1026 - the "clear the owner" test did not exercise the update trigger's user_id branch - Static - Fixed: separate test with a second owner, asserting the owner is kept
Resolution: 2 Fixed. `pytest backend` 10 failed (baseline), 1297 pass; ruff clean. Runtime: init_db.py. Re-verify: migration re-run PASS (migrate-output-rerun4.txt) + wrapper guard check (wrapper-guard-output-rerun4.txt).

### Round 3 - 2026-11-09
Verdict: Request changes (2 MAJOR). Scope: same change, 1 Haiku reviewer.
- R3-1 [MAJOR] init_db.py trigger - guard was INSERT-only: an UPDATE rename could create two ownerless same-name skills, and the next start then raised a raw IntegrityError (the clash check compared only against the admin's rows) - Static (reviewer probed in memory) - Fixed: second trigger `trg_skills_unowned_name_update` (UPDATE OF name, user_id); startup check now covers any ownerless row sharing a name with another row; tests
- R3-2 [MAJOR] init_db.py trigger - guard was one-directional: an owned insert of a name an ownerless row holds created the clash - Static - Fixed: symmetric condition (either side ownerless); tests
- R3-3 [MINOR] docs/data.md - trigger scope overstated - Static - Fixed: wording
- R3-4 [MINOR] test_init_db.py - no tests for UPDATE paths, owned inserts, old-constraint kept on failed rebuild - Static - Fixed
Resolution: 4 Fixed. `pytest backend` 10 failed (baseline), 1295 pass; ruff clean. Runtime: init_db.py. Re-verify: migration re-run PASS + real wrapper guard check (wrapper-guard-output.txt).

### Round 2 - 2026-11-09
Verdict: Request changes (1 MAJOR). Scope: same change, 1 Haiku reviewer.
- R2-1 [MAJOR] skill_ops.py:28 + init_db.py - the unchanged `add_skill` inserts without an owner, so a runtime save of a name the admin owns succeeded and then stopped the next start (the clash check I added in round 1 raised) - Static - Fixed: a write-time guard, trigger `trg_skills_unowned_name` (rejects an ownerless skill whose name exists on another id; replaces the partial index `idx_skills_name_unowned`; created last in `_assign_owners`, since a rebuild drops triggers); startup clash check kept as a backstop; tests (guard, upsert of the same id, survives rebuild); live: wrapper dup -> IntegrityError, update ok, `init_db` ok after
- R2-2 [MINOR] docs/data.md:40 - rule 3 did not mention the new commit point - Static - Fixed
- R2-3 [MINOR] docs/data.md:24 - artifact tables inherit through `file_system_id` - Static - Fixed
- R2-4 [MINOR] docs/data.md:26 - ownerless uniqueness mechanism undocumented - Static - Fixed (trigger described)
- R2-5 [MINOR] test_init_db.py - guard survives rebuild not asserted - Static - Fixed
- R2-6 [MINOR] test_init_db.py:1063 - failed-rebuild test patches the helper, so the real rollback is not exercised - Static - Rejected: the helper's own rollback is covered by existing tests (`test_failed_rebuild_leaves_the_original_table_unchanged...`, `test_rebuild_helper_keeps_rows_and_indexes_and_rolls_back_failures`); this test is about stopping startup
- R2-7 [MINOR] test_init_db.py:932 - "previous schema" fixture is hand-written - Static - Rejected: the live check builds the previous schema with the stacked base's own `init_db` (migrate-output*.txt)
- R2-8 [MINOR] init_db.py:191 - RuntimeError says "see the migration log" without the sqlite error - Static - Rejected: the helper contract (MYAI-31) returns bool and logs the error with `db_migration_rebuild_error`
Resolution: 5 Fixed, 3 Rejected. `pytest backend` 10 failed (baseline), 1293 pass; ruff clean. Runtime: init_db.py. Re-verify: migration re-run PASS (migrate-output-rerun2.txt) + wrapper checks.

### Round 1 - 2026-11-09
Verdict: Request changes (1 BLOCKER, 1 MAJOR). Scope: working tree vs HEAD, 4 files, 1 Haiku reviewer.
- R1-1 [BLOCKER] init_db.py:174 - an ownerless skill sharing a name with an admin-owned skill (the unchanged wrapper still inserts without user_id) made the next start's backfill raise a raw IntegrityError, failing every start - Static (reviewer reproduced on an in-memory schema) - Fixed: `_assign_owners` checks first and raises RuntimeError naming the skills; unit test + live check
- R1-2 [MAJOR] docs/data.md:11 - RAG collections are `file_store_vector` and `file_store_bm25`, not `file_store` - Static (rag/store.py:23, manager.py:165) - Fixed
- R1-3 [MINOR] docs/data.md:24 - "every other table inherits" omitted `users`, `system_settings` - Static - Fixed
- R1-4 [MINOR] test_init_db.py - EXPECTED_INDEXES lacked the new indexes; no direct test of `_skills_name_is_globally_unique`, FK state, or data kept on a failed rebuild - Static - Fixed: tests added
- R1-5 [MINOR] skill_ops.py:70 - `get_skill_by_name` assumes a globally unique name - Static - Deferred: MYAI-36 plan already makes `get_skill_by_name` per user
- R1-6 [MINOR] init_db.py:178 - `_assign_owners` commits before the rebuild (backfill persists even if the rebuild fails) - Static - Rejected: idempotent and documented in the docstring; the rebuild needs no open transaction
Resolution: 4 Fixed, 1 Deferred, 1 Rejected. `pytest backend` 10 failed (baseline), 1290 pass; ruff clean. Runtime change: init_db.py. Re-verify: live migration re-run PASS (migrate-output-rerun1.txt) plus live collision check -> RuntimeError naming the skill.

## Log
- 2026-11-09: created (split from MYAI-32 Step 2)
- 2026-11-09: linked split_from MYAI-32 (Step 2)
- 2026-11-09: linked blocked_by MYAI-33
- 2026-11-09: linked blocked_by MYAI-29
- 2026-11-09: linked blocked_by MYAI-31
- 2026-11-09: linked blocks MYAI-35
- 2026-11-09: linked blocks MYAI-36
- 2026-11-09: linked blocks MYAI-42
- 2026-11-09: scope note: "wrapper inserts require a non-empty `user_id`" moved to MYAI-35 (chat_ops) and MYAI-36 (persona/skill/preference ops)
- 2026-11-09: plan validated, 2 rounds
- 2026-11-09: autopilot started (batch)
- 2026-11-09: implemented, smoke tests pass (baseline failures only)
- 2026-11-09: verified 6 PASS, 0 FAIL
- 2026-11-09: review round 1: Request changes (1 BLOCKER, 1 MAJOR); resolved, re-verified
- 2026-11-09: review round 2: Request changes (1 MAJOR); resolved (trigger guard), re-verified
- 2026-11-09: review round 3: Request changes (2 MAJOR); resolved (symmetric guard triggers), re-verified
- 2026-11-09: review round 4: Request changes (1 MAJOR); resolved, re-verified
- 2026-11-09: review round 5: Approve with comments; loop clean at cap
- 2026-11-09: PR opened: https://github.com/archit342000/My-AI/pull/87 (stacked on MYAI-33's PR). batch-autopilot: shipped
- 2026-11-10: closed (merged into develop via the PR recorded in Implementation notes; deployed to myai.architanand.dev)
