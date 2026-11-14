---
id: MYAI-11
title: "B2 and B3: wrong status codes for preference delete and message edit"
status: done
created: 2026-11-08
updated: 2026-11-09
links:
  blocks: [MYAI-20]
  conflicts_with: [MYAI-5, MYAI-22]
  relates_to: [MYAI-43]
---

## Description
Report B2 (Medium) and B3 (Low to Medium). B2: deleting an unknown preference returns 500 (backend/tools/router.py:135); it should be 404 with a JSON error. B3: editing a message with empty content is accepted by the check (only None is rejected, router.py:537), and the edit is not scoped to the chat_id, so a message id from another chat can be edited through this chat's URL (db.edit_message returns success unconditionally). Not blocked.

## Acceptance criteria
- [x] Unknown preference delete returns 404 with {"error": ...}
- [x] Empty edit content returns 400
- [x] A message from another chat cannot be edited through this chat's URL

## Plan
**Date:** 2026-11-09  **Status:** Validated

### Objective
Make two API error paths follow `docs/standards/api.md`: deleting an unknown preference returns `404 {"error": ...}` instead of 500, and editing a message rejects empty content with 400 and refuses (404) a message id that does not belong to the chat in the URL, without touching any data in either chat.

### Context
- Requirement: the Description and Acceptance criteria above. Code read at origin/develop 6a13e04; implementation branches from origin/develop.
- Assumptions:
  - Whitespace-only content counts as empty (decision): an all-whitespace edit would leave a blank user turn and then truncate the reply, which is never a useful edit. Rule: `content` must be a `str` and `content.strip()` must be non-empty, otherwise 400. Non-empty content is stored exactly as sent (no trimming), matching current behaviour.
  - A message id from another chat (or a non-existent id) is treated as "not found": `404 {"error": "Message not found"}`. 404 rather than 403 because the resource does not exist under this chat's URL and this avoids confirming ids from other chats.
  - Success responses keep their current shape (`{"success": true}`), so no client contract change.
- Rules: `docs/standards/api.md` (status codes 400/404, error body `{"error": "<short message>"}`, "Validate before acting, and fail with 400 (not a partial write)", routes stay thin, logic outside router); `docs/standards/errors-and-logging.md` (`log_event` for handled errors, `snake_case` `<component>_<event>` names); `AGENTS.md` (use `db` from `backend.database`, no raw SQL outside the database layer, matching `tests/test_<module>.py`, run `scripts/check.sh` and `ruff check .`); `docs/pitfalls.md` (targeted edits to `backend/chat/router.py`).
- Current behaviour:
  - `backend/tools/router.py` `delete_preference` (def at line 130, failure return at 135): returns `{"error": "Failed to delete preference"}, 500` whenever `db.delete_preference` returns False. `backend/database/wrapper/preference_ops.py` `delete_preference` already returns `rowcount > 0`, so False means "no such id".
  - `backend/chat/router.py` `edit_message_endpoint` (lines 533-541): rejects only `content is None`; returns `{"success": success}` with 200 whatever `db.edit_message` returns.
  - `backend/database/wrapper/message_ops.py` `MessageOpsMixin.edit_message` (lines 429-523): `UPDATE messages SET content = ? WHERE id = ?` with no `chat_id` filter, deletes `sub_agent_messages` and SSE chunks for that id, then purges this chat's messages with `id > message_id`, rewrites pointers, and always returns True. So a foreign id edits the other chat's message and also truncates the URL chat's history.
  - Clients: React `frontend/src/features/chat/MessageList.tsx` `save()` shows a toast with the server `error` on a non-2xx (`ApiError` in `frontend/src/api/client.ts`); legacy `static/js/preferences-manager.js` delete only reloads on `res.ok`. Legacy UI does not call the edit PUT. No client change is needed.

### Approach
- Ownership check lives in the database layer (`edit_message`), inside the existing `BEGIN IMMEDIATE` transaction, before any write: `SELECT 1 FROM messages WHERE id = ? AND chat_id = ?`; if no row, roll back and return False; also add `AND chat_id = ?` to the content `UPDATE` as defence in depth. The router maps False to 404. Rejected alternative: checking ownership in the router with a separate read (race between check and write, and logic in the router against api.md).
- Content validation stays in the router (input validation is the router's job per api.md) and happens before calling the database.
- Preference delete: router maps False to 404 `{"error": "Preference not found"}`. No database change needed.
- Each new 4xx/404 path logs a `log_event` with ids (`tools_preference_delete_not_found`, `chat_edit_message_not_found`). Empty-content 400 is plain input validation and is not logged, matching the other 400 paths in these routers.

### Steps
#### Step 1: Scope `edit_message` to the chat
- **Files:** `backend/database/wrapper/message_ops.py` (modify), `MessageOpsMixin.edit_message`.
- **Change:** inside `_write()` after `BEGIN IMMEDIATE`, select the message by `id` and `chat_id`; if absent, `ROLLBACK` and return False before any UPDATE/DELETE or `cache_system.delete_sse_chunks` call. Add `AND chat_id = ?` to the content UPDATE. Guard the three `cache_layer.invalidate(...)` calls that follow `success = _write()` (outside `_write`, lines 517-519) so they run only when the result is True; keep the END log and include the result (`edited=<bool>`). Return the real result instead of a constant True.
- **Verification:** Step 3 database tests pass.

#### Step 2: Fix the two route handlers
- **Files:** `backend/chat/router.py` (modify), `edit_message_endpoint`; `backend/tools/router.py` (modify), `delete_preference`.
- **Change:** edit endpoint: return 400 `{"error": "Content required"}` when `content` is not a string or `content.strip()` is empty; call `db.edit_message`; if False, `log_event("chat_edit_message_not_found", {"chat_id": ..., "message_id": ...})` and return 404 `{"error": "Message not found"}`; else 200 `{"success": True}`. Preference delete: if False, `log_event("tools_preference_delete_not_found", {"preference_id": ...})` and return 404 `{"error": "Preference not found"}`. Use targeted edits (pitfalls.md). Check that `log_event` is imported in `backend/chat/router.py` (it is used by the stop endpoint).
- **Verification:** Step 3 router tests pass.

#### Step 3: Tests
- **Files:** `backend/chat/tests/test_router.py`, `backend/tools/tests/test_router.py`, `backend/database/wrapper/tests/test_message_ops.py` (modify).
- **Change:** see Tests below.
- **Verification:** `EMBEDDING_URL="http://mock" AI_URL="http://mock" AI_API_KEY="dummy" PYTHONPATH=. venv/bin/python -m pytest <file> -q` passes for each of the three test files, one process each.

#### Step 4: Full checks
- **Files:** none.
- **Change:** run the per-directory pytest targets from Tests (with the env prefix), then `venv/bin/python -m ruff check .` and `scripts/check.sh --python-only` (no frontend files change).
- **Verification:** all steps report PASS.

### Tests
- `backend/tools/tests/test_router.py`: new test, `mock_db.delete_preference.return_value = False` gives 404 with an `error` key; existing `test_delete_preference` still passes.
- `backend/chat/tests/test_router.py` (extend `test_edit_message_endpoint` or add tests): `""`, `"   \n"` and a non-string `content` give 400 and `db.edit_message` is not called; `edit_message` returning False gives 404 with `error`; valid content gives 200 `{"success": True}`.
- `backend/database/wrapper/tests/test_message_ops.py`: new test with two chats; calling `edit_message(chat_a, <id from chat_b>, ...)` returns False, chat B's message content is unchanged, chat A's messages (including ones with higher ids) are all still present; editing a non-existent id returns False; an in-chat edit returns True and removes the chat's later messages (new assertions; the existing call at line 73 checks only the edited content and must keep passing).
- Commands (env prefix required, per `docs/standards/testing.md` "Running tests" and `backend/database/wrapper/tests/conftest.py`, since `backend.config` validates at import). Run each target in its own pytest process (testing.md warns that combining suites causes duplicate-module collection errors), for example `EMBEDDING_URL="http://mock" AI_URL="http://mock" AI_API_KEY="dummy" PYTHONPATH=. venv/bin/python -m pytest backend/database/wrapper/tests -q`. Targets, changed dir first, then each parent up to the root (testing.md rule 3): `backend/database/wrapper/tests`, `backend/chat/tests`, `backend/tools/tests`, `backend/database/tests`, `backend/tests`, `tests`. Then `scripts/check.sh --python-only`, which sets the same env and runs ruff plus every Python suite (docs guardrails, full `backend`, `inference_proxy`, `tavily_mcp`, `code_runner_mcp`).

### Risks and open questions
- Overlap with MYAI-5: it also edits error responses in `backend/tools/router.py` (lines ~103, 144, 281, 286, the `str(e)` leaks). This plan touches only `delete_preference`; expect a small merge conflict if both land close together. Land one first and rebase the other.
- Behaviour change: clients that relied on 200 `{"success": false}` from edit, or on 500 from preference delete, now see 404. The React client and legacy UI both treat any non-2xx as failure, so no client change.
- Out of scope, noted only: `update_preference` also returns 500 for an unknown id; `request.json` being None (no JSON body) raises in these routes; edit does not check the message role. Candidates for separate tickets.
- Open questions: none blocking.

### Success criteria
- [ ] `DELETE /api/tools/preferences/<unknown>` returns 404 with `{"error": ...}`.
- [ ] `PUT /api/chats/<id>/messages/<mid>` with empty or whitespace-only content returns 400 and changes nothing.
- [ ] Editing a message id from another chat (or a missing id) through this chat's URL returns 404 and leaves both chats' messages unchanged.
- [ ] Valid in-chat edits behave as before (200 `{"success": true}`, later history truncated).
- [ ] New tests pass; `ruff check .` and `scripts/check.sh --python-only` pass.

### Validation log
- Round 1: validator PASS (0 blocking, 7 minor). My judgement: PASS, with these minors:
  1. Whitespace-only goes beyond "empty": out of scope. The caller asked for this decision and the plan records it under Assumptions.
  2. No existing edit test asserts the return value or truncation: valid. Test bullet reworded as new assertions (the line 73 call checks content only).
  3. Cache invalidation sits outside `_write`: valid. Step 1 now names the three `cache_layer.invalidate` calls.
  4. Step 1 verification points forward to Step 3: disproved as a problem. The verification uses tests written later in the same plan, and the order holds.
  5. Approximate line numbers: valid. Replaced with exact lines from 6a13e04.
  6. Parent test dirs per testing.md: valid. Added `backend` and the rule reference.
  7. Two SHAs in the ticket: disproved. e327094 is the 2026-11-08 status note, 6a13e04 is the current planning base. Both are correct for their dates.
- Round 2: validator FAIL (1 blocking, 3 minor). My judgement: one valid BLOCKING issue, fixed:
  1. [BLOCKING] Pytest commands lacked the required env vars: valid (`backend/database/wrapper/tests/conftest.py` lines 1-13, testing.md "Running tests"). Added the env prefix and one process per suite (testing.md warns about duplicate-module collection).
  2. Parent-dir list wrong (`backend/chat` and `backend/tools` are not parents; root `tests` missing): valid. The list is now the changed test dirs, then `backend/database/tests`, `backend/tests`, `tests`.
  3. Cache invalidation lines are 517-519: valid, fixed.
  4. `edit_message` ends at 523: valid, fixed.
- Round 3: validator PASS (0 blocking, 2 minor). My judgement: PASS. The round 2 blocking item is resolved (I checked the env prefix against testing.md and the conftest).
  1. check.sh does more than the backend suite: valid. Wording fixed.
  2. `venv/bin/python` is absent in the read-only checkout: out of scope. AGENTS.md rule 3 requires the project venv, and the implementer's worktree has one.
- Stopped after round 3: no valid BLOCKING issues remain and no minors are deferred.

## Implementation notes
### Autopilot run (2026-11-09)
- Mode: automatic (batch-autopilot, item 2/3)
- Branch: bugfix/preference-delete-message-edit-status  PR base: develop  Starting commit: 6a13e04
- Dirty before start: none
- Work files: backend/database/wrapper/message_ops.py, backend/chat/router.py, backend/tools/router.py, backend/chat/tests/test_router.py, backend/tools/tests/test_router.py, backend/database/wrapper/tests/test_message_ops.py
- Counters: fix 0/10, review 1/5, re-verify 0
- Last completed stage: 6 ship  Next: none
- Hard blocker: none
- WIP commit: none

### Autopilot decisions (2026-11-09)
- Stage 1: plan already Validated (3 rounds); reused, not re-planned (user confirmed all tickets are already planned).

### Baseline (2026-11-09)
wrapper tests 69 pass; backend/chat/tests 108 pass; backend/tools/tests 84 pass, 6 fail (test_code_executor async tests: pytest-asyncio not installed in the venv). backend/database/tests 2 fail (test_cache_system, same cause). Full check.sh also fails the same async-plugin tests in research_utils, tavily_mcp and code_runner_mcp.

### Implementation progress
- [x] Step 1: edit_message scoped to chat - backend/database/wrapper/message_ops.py
- [x] Step 2: route handlers - backend/chat/router.py, backend/tools/router.py
- [x] Step 3: tests - backend/chat/tests/test_router.py, backend/tools/tests/test_router.py, backend/database/wrapper/tests/test_message_ops.py
- [x] Step 4: full checks (see Smoke test)
Branch: bugfix/preference-delete-message-edit-status

### Smoke test (2026-11-09)
wrapper 70 pass; chat 113 pass; tools 85 pass + same 6 baseline fails; database/tests 56 pass + 2 baseline fails; backend/tests 25 pass; tests 32 pass; ruff clean; `scripts/check.sh --python-only`: backend 10 fail, tavily_mcp 5 fail, code_runner_mcp fail, all `async def` plugin errors (baseline cause, none in touched code). New test fails-without-fix not shown by reverting; pre-fix behaviour was 200/500 per the plan.

Status on develop (checked at e327094, 2026-11-08): Still present on develop: router.py:135 returns 500; edit_message_endpoint at chat/router.py:534 checks only None and does not filter by chat.

PR: https://github.com/archit342000/My-AI/pull/56, branch bugfix/preference-delete-message-edit-status, base develop

## Verification
### Verification plan (2026-11-09, light form: 3 runtime source files, ~20 changed lines)
**Diff base:** 6a13e04. **Scope:** `DELETE /api/tools/preferences/<id>` unknown id; `PUT /api/chats/<id>/messages/<mid>` content validation and chat scoping (`db.edit_message`). Out of scope: update_preference 500, missing JSON body, role check on edit.
**Environment and isolation:** real Flask app from this branch on 127.0.0.1:5099, `DATA_DIR=/tmp/myai11-data` (fresh sqlite DB from `init_db`), mock AI/embedding URLs. App on :5000, containers and `backend/data` never touched. Teardown: kill PID, remove temp dir, compare ports/containers to the snapshot. Harness `scripts/v11.py` (stdlib) refuses any base URL or DB path outside the throwaway env.

| ID | Criterion | Scenario | Type | Method | Files | Expected | Evidence |
|----|-----------|----------|------|--------|-------|----------|----------|
| V1 | Unknown pref delete 404 | DELETE unknown preference id | failure | API | backend/tools/router.py | 404 `{"error": "Preference not found"}` | log |
| V2 | Pref delete still works | create a preference row, DELETE it, DELETE again | happy/regression | API + DB | backend/tools/router.py | 200 `{"success": true}`, row gone; second delete 404 | log |
| V3 | Empty edit 400 | PUT with `""`, whitespace-only, missing, non-string content | edge | API + DB | backend/chat/router.py | each 400 `{"error": ...}`; messages unchanged | log |
| V4 | Cross-chat edit refused | PUT chat A URL with a message id from chat B | failure | API + DB | message_ops.py, chat/router.py | 404 `{"error": "Message not found"}`; chat B content unchanged; chat A history not truncated | log, DB rows |
| V5 | Missing id | PUT chat A with nonexistent id | failure | API | same | 404, chat A unchanged | log |
| V6 | Valid edit unchanged | PUT own message with new content | happy/regression | API + DB | same | 200 `{"success": true}`, content updated, later messages removed, chat B untouched | log |
| V7 | Whitespace content kept as sent | PUT `"  hi  "` | edge | API + DB | chat/router.py | 200 and stored as `"  hi  "` (no trim) | log |
| V8 | Regression | wrapper, chat, tools pytest dirs; ruff | regression | CLI | all | only baseline failures | output |

Temporary script: `scripts/v11.py` (API/DB driver).

### Results (2026-11-09)
Verified at HEAD 6a13e04114e9636ed903fbb8e177ad0b2e800bfc plus uncommitted: backend/chat/router.py ef9613de, backend/chat/tests/test_router.py 14d4eb0c, backend/database/wrapper/message_ops.py 513c08ba, backend/database/wrapper/tests/test_message_ops.py f5c13027, backend/tools/router.py 90992121, backend/tools/tests/test_router.py d39ffde2.
Isolation: app on 127.0.0.1:5099, DATA_DIR=/tmp/myai11-data; :5000 app, containers and backend/data untouched. Teardown: PID killed, temp dir removed; containers, ports and git status identical to the snapshot.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | v1-v7.log: unknown preference DELETE -> 404 `{"error": "Preference not found"}` |
| V2 | PASS | v1-v7.log: real preference deleted 200, gone from list, second delete 404 |
| V3 | PASS | v1-v7.log: `""`, whitespace, missing, 5, null, list all 400 `{"error": "Content required"}`; chat A messages unchanged |
| V4 | PASS | v1-v7.log: cross-chat edit 404 `{"error": "Message not found"}`; chat B content and chat A history unchanged |
| V5 | PASS | v1-v7.log: nonexistent id 404, chat A unchanged |
| V6 | PASS | v1-v7.log: own edit 200 `{"success": true}`, content updated, later messages removed, chat B untouched |
| V7 | PASS | v1-v7.log: `"  hi  "` stored exactly as sent |
| V8 | PASS | v8-pytest.log: wrapper 70, chat 113, tools 85 pass + 6 baseline async-plugin failures; ruff clean |

Verdict: verified. 8 PASS, 0 FAIL, 0 BLOCKED. Script: scripts/v11.py (evidence folder MYAI-11-evidence/).

## Review history
### Round 1 - 2026-11-09
Verdict: Request changes (1 MAJOR). Scope: 6 uncommitted files vs 6a13e04 (small diff, one Haiku reviewer, requirement and plan brief given). All findings checked against the code; all static.
- R1-1 [MAJOR] backend/tools/tests/test_router.py:128-132 and backend/chat/tests/test_router.py:334-338 - new 404 tests call the real log_event, which writes under DATA_DIR/logs (backend/data); docs/standards/testing.md says tests never touch backend/data and sibling tests patch log_event - Static - Fixed: log_event patched in both new 404 tests
- R1-2 [MINOR] same tests - the 404 logging (event name and ids) is not asserted - Static - Fixed: tests assert the log_event call (name and ids)
- R1-3 [MINOR] backend/database/wrapper/message_ops.py:429-430 - edit_message contract changed (returns False when the message is not in the chat) but has no `-> bool` or Returns note (docs/standards/python.md) - Static - Fixed: `-> bool` and Returns note on edit_message
- R1-4 [MINOR] backend/database/wrapper/tests/test_message_ops.py:181-182 - missing-id check asserts only the count, not contents - Static - Fixed: missing-id block asserts exact contents
- R1-5 [NIT] backend/database/wrapper/message_ops.py:449 - `AND chat_id = ?` on the UPDATE is redundant after the SELECT guard; planned as defence in depth but unexplained - Static - Fixed: comment says the chat_id filter is defence in depth
Dismissed: reviewer note on frontend/src/features/chat/MessageList.tsx:78 (a cleared draft now shows a 400 toast): intended behaviour per the plan, and client changes are out of scope. Pre-existing: none.
Resolution: 5 Fixed, 0 Rejected, 0 Deferred. Tests, a comment, a docstring and a return annotation only; no runtime behaviour change (no live re-verify needed). Checks: wrapper 70, chat 113, tools 85 + 6 baseline fails, database/tests 56 + 2 baseline fails, backend/tests 25, tests 32; ruff clean.


## Log
- 2026-11-08: created from reports/full-scope-final-report-2026-11-08.md
- 2026-11-09: plan validated, 3 rounds
- 2026-11-09: linked blocks MYAI-20 (builds on MYAI-11's chat-scoped edit_message and empty-content 400)
- 2026-11-09: linked conflicts_with MYAI-5 (adjacent preference routes in backend/tools/router.py)
- 2026-11-09: linked conflicts_with MYAI-22 (preference routes and edit_message_endpoint body reads)
- 2026-11-09: autopilot started (batch-autopilot)
- 2026-11-09: implemented, smoke tests pass (only baseline async-plugin failures)
- 2026-11-09: verified: 8 PASS, 0 FAIL, 0 BLOCKED
- 2026-11-09: review round 1: Request changes (1 MAJOR, 3 MINOR, 1 NIT)
- 2026-11-09: review round 1 resolved: 5 fixed (tests/comments/annotation only)
- 2026-11-09: PR opened #56 (batch-autopilot: shipped, base develop)
- 2026-11-09: linked relates_to MYAI-43 (batch 1 follow-ups)
- 2026-11-09: PR #56 merged into develop; closed
