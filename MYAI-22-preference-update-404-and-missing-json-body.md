---
id: MYAI-22
title: "Unknown preference update returns 500; routes crash without a JSON body"
status: done
created: 2026-11-09
updated: 2026-11-09
links:
  conflicts_with: [MYAI-5, MYAI-6, MYAI-7, MYAI-9, MYAI-11, MYAI-19, MYAI-20, MYAI-28]
  relates_to: [MYAI-43, MYAI-50]
---

## Description
Found while planning MYAI-11. `update_preference` in `backend/tools/router.py` returns 500 for an unknown id (MYAI-11 fixes only delete). Routes that read `request.json` / `request.get_json()` raise when the body is missing or not JSON, giving 500 instead of 400.

## Acceptance criteria
- [x] Updating an unknown preference returns 404 with {"error": ...}
- [x] Routes that need a JSON body return 400 with {"error": ...} when it is missing or invalid
- [x] Valid requests are unchanged

## Plan

**Date:** 2026-11-09  **Status:** Validated  **Base:** origin/develop 6a13e04

### Objective
- Return 404 `{"error": ...}` when updating a preference that doesn't exist (MYAI-11 covers delete only).
- Make every Flask route that reads a JSON body return 400 `{"error": ...}` when the body is missing, isn't JSON, or isn't a JSON object, instead of a 500 or Flask's HTML 400/415 page.
- Valid requests behave as today.

### Context
- Requirement: Description and Acceptance criteria above.
- `update_preference` (`backend/tools/router.py:117-127`):
  - It reads `request.json` and returns 400 when `content` or `tag` is missing.
  - It returns 500 "Failed to update preference" when `db.update_preference` returns False.
  - `PreferenceOperations.update_preference` (`backend/database/wrapper/preference_ops.py:53`) returns `rowcount > 0`, so False means no row with that id (DB errors raise instead).
- JSON-body reads on develop (29 found by grep: 28 to change, plus line 35 excluded; Flask 3.1.3 per `requirements.txt`):
  - `backend/chat/router.py`: lines 41, 50, 75, 128, 253, 461, 473, 535, 617, 634, 676, 702.
  - `backend/file_system/router.py`: 64, 110, 540, 779, 811, 950, 966, 1017, 1032. Line 35 is excluded: it's `request.get_json(silent=True)` inside the blueprint's `before_request` hook `normalize_workspace_id` (lines 22-57), which runs for every request and deliberately ignores errors. It stays as is.
  - `backend/tools/router.py`: 69, 108, 119, 191, 236, 321, 349.
  - Most are `data = request.json` followed by `data.get(...)`.
  - These 11 sites use `request.json or {}`: chat 50; file_system 64, 110, 540, 779, 811, 950, 966, 1017, 1032; tools 349. That turns a JSON `null` body into `{}`, but a body-less call still fails today (415 or 400).
  - `resume_chat` (461, 473) reads `request.json.get` / `.items()` directly inside a `try`.
- Flask 3 behaviour:
  - `request.json` raises `UnsupportedMediaType` (415) when the content type isn't JSON, and `BadRequest` (400, HTML) when the body is malformed.
  - A body of `null`, a list or a string gives a non-dict, so `.get` raises `AttributeError`.
  - Inside a broad `try/except Exception` (for example `resume_chat`, 451-499), these become 500 with `str(e)`. Elsewhere the client gets Flask's HTML 400/415 page, or a 500 from the `AttributeError`, so the Description's "500" applies to some sites only. Either way the body isn't the `{"error": ...}` JSON that api.md requires.
  - `request.get_json(silent=True)` returns None instead of raising.
- The only app-level error handler is for 413 (`app.py:341`).
- `backend/utils.py` holds small shared helpers, tested in `backend/tests/test_utils.py`.
- Rules:
  - `docs/standards/api.md`: 400 for invalid input; body `{"error": "<short message>"}`; validate before acting; keep the personas/skills `"success": false` form where those routes use it.
  - `docs/standards/security.md`: validate every request body.
  - `docs/standards/python.md`: docstrings and hints.
  - `docs/standards/testing.md`: suites run separately, with env vars.

### Approach
- **One helper, no exceptions.** Add `read_json_object(required: bool = True, extra: dict | None = None) -> tuple[dict | None, tuple | None]` to `backend/utils.py`. It tells "absent" apart from "invalid" instead of using `get_json(silent=True)`, which returns None for both:
  1. `raw = request.get_data(cache=True)`. If `raw.strip()` is empty, the body is absent.
  2. Otherwise, if `not request.is_json`, it's invalid.
  3. Otherwise `data = request.get_json(silent=True)`. This must be Flask's cached object: the file_system `before_request` hook (`normalize_workspace_id`, router.py:44-57) rewrites `workspace_id` inside that same dict, so re-parsing the raw body would lose the rewrite. Checked locally with Flask 3.1: after the hook-style mutation, both `request.get_json(silent=True)` and `request.json` return the mutated dict, so the cached parse is shared and the helper's `get_json` call sees the rewrite.
  4. If `data` is None, tell `null` from malformed with `json.loads(raw)`: a `ValueError` means invalid; the literal `null` counts as absent.
  5. A non-empty dict, or `{}`, is returned as `(data, None)`, the same object routes get today from `request.json`.
  6. Any other falsy JSON value (`[]`, `""`, `0`, `false`) also counts as absent, which keeps exactly today's `request.json or {}` behaviour at the optional sites. Truthy non-dict values (`[1]`, `"x"`, `5`) are invalid.
  - Absent: `({}, None)` when `required` is False; otherwise the error.
  - Invalid: always the error, `(None, (jsonify({"error": "Request body must be a JSON object", **(extra or {})}), 400))`.
  - Routes use `data, err = read_json_object(...); if err: return err`, placed before any `try`.
  - Returning instead of raising means the routes' broad `except Exception` blocks can't turn the 400 into a 500.
- **Required vs optional.**
  - The 11 `request.json or {}` sites and `resume_chat` use `required=False`. For them, a body-less request (415/400 today) is now accepted as `{}` and then goes through the route's own field checks. That's a deliberate widening: those routes already treat their fields as optional.
  - Every other site uses `required=True`.
  - For the personas and skills routes, which use `{"success": false, "error": ...}` (api.md), the route adds `"success": false` to the 400 body. The helper takes an optional `extra: dict | None` that's merged into the error body.
- **Preference update 404.** When `db.update_preference` returns False, return `jsonify({"error": "Preference not found"}), 404` and `log_event("tools_preference_not_found", {"preference_id": ...})` (`log_event` is already imported in the tools router). This doesn't depend on MYAI-11. If MYAI-11 has landed, use the same event name as its delete 404 for consistency.
- Rejected alternatives:
  - An app-level `errorhandler` for `BadRequest`/`UnsupportedMediaType`: the broad `except Exception` in the routes catches them first, and it would also change unrelated 400s.
  - Pydantic models per route: correct but much larger, and Pydantic for structured payloads is a `python.md` / `security.md` convention that this ticket doesn't extend, so it stays with the shape check. Field validation stays as it is in each route.

### Steps
#### Step 1: Helper
- **Files:** `backend/utils.py` (modify): new `read_json_object(required: bool = True, extra: dict | None = None)`, with a docstring (Args, Returns).
- **Change:** as in Approach. Import `request` and `jsonify` from Flask inside the module.
- **Verification:** Step 2 tests.

#### Step 2: Helper tests
- **Files:** `backend/tests/test_utils.py` (modify).
- **Change:** use `app.test_request_context` from a minimal `Flask(__name__)` to cover:
  - a dict body returns the dict;
  - an absent body gives 400 with `required=True`, and `{}` with `required=False`;
  - `null`, `[]`, `""`, `0` and `false` give 400 with `required=True`, and `{}` with `required=False`;
  - a non-empty body with a wrong content type gives 400 in both modes;
  - malformed JSON gives 400 in both modes;
  - `[1]`, `"x"` and `5` give 400 in both modes;
  - `extra={"success": False}` is merged;
  - the returned dict is the same object as `request.get_json(silent=True)`. Mutate it after a first call and check that the helper returns the mutated dict, which mimics the `before_request` hook.
- **Verification:** `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q backend/tests/test_utils.py`.

#### Step 3: Use it in the chat router
- **Files:** `backend/chat/router.py` (modify): all 12 sites listed in Context.
- **Change:** replace each `request.json` read with the helper, using `required=False` for `request.json or {}` sites and for `resume_chat`. In `resume_chat`, read once and reuse `data` for `model` and `extra_body`. Personas and skills routes pass `extra={"success": False}`. Keep each route's existing field validation after the helper call.
- **Verification:** Step 6 tests.

#### Step 4: Use it in the file system router
- **Files:** `backend/file_system/router.py` (modify): the 9 sites listed in Context (not the `before_request` hook at line 35).
- **Change:** same as Step 3.
- **Verification:** Step 6 tests.

#### Step 5: Tools router, including the preference 404
- **Files:** `backend/tools/router.py` (modify): all 7 sites listed in Context, and `update_preference`.
- **Change:** same as Step 3, plus the preference 404 from Approach.
- **Verification:** Step 6 tests.

#### Step 6: Route tests
- **Files:** `backend/chat/tests/test_router.py`, `backend/file_system/tests/test_router.py`, `backend/tools/tests/test_router.py` (modify; check the exact file names and use the existing ones).
- **Change:**
  - For each router, a parametrised test over its POST/PUT/PATCH endpoints that need a body: sending no body (`client.post(url)`) gives 400 with `{"error": "Request body must be a JSON object"}` (plus `"success": false` for personas and skills), and sending `data="null", content_type="application/json"` gives the same.
  - File system: a create with `workspace_id: "default"` and a `chat_id` still reaches the route with the resolved workspace id (patch `backend.file_system.utils.get_workspace_for_chat`, as `backend/file_system/tests/test_router.py:96` does). This guards the `before_request` rewrite.
  - Optional-body routes accept no body and a `null` body: `resume_chat`, with `backend.chat.router.task_manager` patched (harmless whether or not MYAI-19 has added `claim_turn`), `db.get_messages` returning one user message and `ChatHandler` mocked so `initiate_chat` yields one chunk; assert a 200 `text/event-stream`, not the "No user message" 400, and one `or {}` site per router (chat 50, tools 349, and one file_system site).
  - `update_preference` with `mock_db.update_preference.return_value = False` gives 404 `{"error": "Preference not found"}`.
  - Existing tests that send valid JSON keep passing unchanged.
- **Verification:** `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q backend`.

#### Step 7: Docs and full gate
- **Files:** `docs/standards/api.md` (modify): one bullet under the input rules saying JSON-body routes read through `read_json_object` (`backend/utils.py`) and return 400 for a missing or non-object body.
- **Change:** run `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q tests`, then `venv/bin/ruff check .` and `scripts/check.sh`.
- **Verification:** all pass.

### Tests
- Preconditions: a `venv` with `requirements.txt` and `requirements-dev.txt`.
- `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q backend`, then the same with `tests` (separate processes).
- `venv/bin/ruff check .`, then `scripts/check.sh`.
- Optional live check with a throwaway `DATA_DIR`: `curl -X POST /api/chats/workspaces` with no body gives 400 JSON; a normal create still works in the UI.

### Risks and open questions
- **Wide diff across three routers.** This overlaps MYAI-5, 9, 11, 19 and 20 (same files and some of the same functions). Land it after those, or rebase it on top: the change per site is mechanical.
- **415 becomes 400 for a wrong content type.** Clients always send JSON (React `apiRequest`, legacy `fetch` with `Content-Type: application/json`), so nothing depends on the 415.
- **Required vs optional is judged per site.** Today no site accepts a body-less call (Flask raises), so marking a site required can't break a body-less client. At the `or {}` sites, falsy bodies (`null`, `[]`, `""`, `0`, `false`) keep giving `{}` as today. For `resume_chat`, a `null` or absent body is new behaviour: it used to fail with a 500 (`request.json.get` on None) and now works. Step 6 tests both.
- **`app.py` routes and WebSocket handlers aren't touched.** The grep found no `request.json` there.
- No blocking open questions.

### Success criteria
- [ ] Updating an unknown preference returns 404 `{"error": ...}` (Steps 5-6)
- [ ] JSON-body routes return 400 `{"error": ...}` for a missing, non-JSON or non-object body (Steps 2-6)
- [ ] Valid requests are unchanged (existing tests pass)
- [ ] Docs updated; `scripts/check.sh` passes

### Validation log
- Round 1 (2026-11-09, Haiku): FAIL, 2 BLOCKING and 6 MINOR. My judgement: FAIL is valid; I checked all 8 against the code.
  - B1: `get_json(silent=True)` can't tell absent, null and malformed apart. Valid. The helper now parses explicitly.
  - B2: file_system line 35 is the `before_request` hook. Valid (lines 22-42). Excluded.
  - M3: the `or {}` sites don't accept a body-less call today. Valid. Widening stated; tests added.
  - M4: `null` at the `or {}` sites. Valid. `null` is treated as absent, so it still gives `{}`.
  - M5: wrong optional-site list (chat 128). Valid. Exact list of 11.
  - M6: "500" applies to some sites only. Valid. Context corrected.
  - M7: parity with MYAI-11. Valid. Made independent.
  - M8: MYAI-19 conditional. Valid. Patch unconditionally.
  - My own check while fixing B2: the hook mutates the cached JSON dict (router.py:55-57), so the helper must return Flask's cached `get_json(silent=True)` object. Spec and tests updated.
- Round 2 (2026-11-09, Haiku, diff-scoped): PASS, 6 MINOR. My judgement: PASS. Both round 1 BLOCKING items were confirmed resolved, the algorithm was confirmed against all six body cases, and the Werkzeug cache sharing was confirmed. All 6 minors were valid and applied:
  - hook line range and site count;
  - other falsy bodies at `or {}` sites, now kept as `{}` to preserve behaviour exactly;
  - resume `null` is new behaviour, not preserved;
  - resume test mocks specified;
  - patch target for `get_workspace_for_chat`;
  - Pydantic citation.

## Implementation notes

### Autopilot run (2026-11-09)
Batch 6 item. Branch bugfix/json-body-and-prefs from origin/develop 24e912d, PR base develop. Dirty files before start: none. Line numbers in the plan predate the merged batches; the sites were re-listed (28 body reads: chat 10 + resume 2, file_system 9, tools 7; the file_system before_request hook stays on `get_json(silent=True)`).

### Baseline (2026-11-09)
At develop 24e912d: `pytest backend tests` 963 pass, 10 fail (async plugin missing).

### Implementation progress
- [x] Step 1: `read_json_object(required=True, extra=None)` in backend/utils.py
- [x] Step 2: helper tests (absent bodies, invalid bodies, content type, extra, shared cached parse)
- [x] Steps 3-5: 26 sites use it (`required=False` where the code had `request.json or {}`); `resume_chat` reads the body once before taking the turn claim, so a bad body never holds the claim; `update_preference` returns 404 `{"error": "Preference not found"}` and logs `tools_preference_update_not_found` (same pattern as delete)
- [x] Step 6: parametrised route tests per router, resume with no or null body, the file system before_request rewrite, and the old `test_update_preference_fail` (which asserted 500) now asserts 404
- [x] Step 7: docs/standards/api.md bullet; ruff clean. scripts/check.sh not run as a whole (pytest-asyncio missing)

### Smoke test (2026-11-09)
`pytest backend` 1071 pass, 10 fail (all async plugin, baseline); `pytest tests` 32 pass; ruff clean.
None yet.

PR: https://github.com/archit342000/My-AI/pull/73, branch bugfix/json-body-and-prefs, base develop

## Verification
### Verification plan (2026-11-09, full form: 26 routes across three routers)
Real app (5099, /tmp/myai22-data), fake proxy 5098, `scripts/v22.py` (HTTP), `scripts/ui.js` (Playwright). Never touches :5000/:5001, containers, backend/data or a real chats.db.
| ID | Criterion | Scenario | Expected |
|----|-----------|----------|----------|
| V1 | AC2 | 14 required-body routes x (no body, null, list, malformed, text/plain) | 400 JSON `{"error": "Request body must be a JSON object"}` (+ success false for personas and skills) |
| V2 | AC2 | optional-body routes | invalid body 400 JSON; no body reaches the route's own handling |
| V3 | AC1 | PUT an unknown preference | 404 `{"error": "Preference not found"}` |
| V4 | AC3 | valid requests via API | unchanged statuses, rows stored |
| V5-V8 | AC3 | UI: create and rename a workspace, send a message | work; no 4xx/5xx |
Not run yet.

### Results (2026-11-09)
**Commit verified:** 24e912d (+ uncommitted). Hashes: utils.py 8b6c49f0, router.py d657f0cf, router.py 400df9ca, router.py a8a950a2, test_utils.py bf161429, test_router.py 54bf570b, test_router.py 21b0e622, test_router.py 64f18dd2, api.md 63387c9f.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | v1-v4-api.log: 70 requests, all 400 JSON with the expected body |
| V2 | PASS | v1-v4-api.log: invalid bodies 400; no body reaches each route's own 400 (e.g. "Missing chat_id/workspace_id or content") |
| V3 | PASS | v1-v4-api.log: 404 {"error": "Preference not found"} |
| V4 | PASS | v1-v4-api.log: workspace create/rename, preference add/update, persona create, completion, artifact create all 200/201, 2 messages stored |
| V5-V8 | PASS | ui.log: workspace created and renamed from the sidebar, message sent and reply shown, no failed /api requests, no console errors |

Teardown: app and proxy stopped, /tmp/myai22-data removed, ports free, containers unchanged. **Verdict: verified (8/8 PASS).**

## Review history
### Round 1 - 2026-11-09
Verdict: Request changes (1 MAJOR, judged below). Scope: origin/develop 24e912d..working tree, 9 files, single Haiku reviewer.
- R1-1 [MAJOR] absent body on `required=False` sites now succeeds, so a body-less `resume_chat` and body-less file system calls (with the ids in the query) are accepted, where they used to fail - Static - Rejected as a defect: the validated plan chose this deliberately for routes whose fields are all optional (Risks section); the wording that called it "equal to `request.json or {}`" was wrong and is fixed in the helper docstring and docs/standards/api.md, and the PR states it
- R1-2 [MINOR] inference_proxy/router.py has the same `request.json or {}` pattern - Static - Deferred: outside backend/ and the plan; follow-up (needs a decision on sharing the helper with that service)
- R1-3 [MINOR] optional-route tests weak (`get_json() != ...` passes for HTML; one route only) - Static - Fixed (parametrised over every FS route and both absent forms, exact JSON error)
- R1-4 [MINOR] no Content-Type variant, BOM or nested-input tests - Static - Fixed (charset, `+json`, BOM, 200k-deep nesting)
- R1-5 [MINOR] RecursionError on deeply nested JSON gave a 500 - Static - Fixed (treated as invalid)
- R1-6 [MINOR] file_system before_request hook raised TypeError for a non-object body with chat_id and workspace_id=default - Static - Fixed (isinstance check, test)
- R1-7 [MINOR] unused `request` import in chat/router.py - Static - Fixed
- R1-8 [MINOR] helper lacked a return annotation, module a docstring - Static - Fixed
- R1-9 [MINOR] api.md said a missing body is always 400 - Static - Fixed (states the optional-body exception)
- R1-10 [MINOR] stale comment above the body read in resume_chat - Static - Fixed (moved)
- R1-11 [NIT] unreachable isinstance branch in update_system_settings - Static - Fixed (removed)
- R1-12 [NIT] helper control flow hard to read - Static - Fixed (restructured)
Resolution: fixed 10, rejected 1, deferred 1. Checks: `pytest backend` and `tests` only the 10 baseline async failures, ruff clean. Runtime change in utils.py, file_system/router.py, tools/router.py, chat/router.py: live V1-V8 re-run, all PASS (v1-v4-api-rerun.log, ui-rerun.log).

## Log
- 2026-11-09: created (follow-up found while planning MYAI-2 to MYAI-16)
- 2026-11-09: plan validated, 2 Haiku rounds.
- 2026-11-09: linked conflicts_with MYAI-5 (preference routes' body reads in backend/tools/router.py)
- 2026-11-09: linked conflicts_with MYAI-11 (preference routes and edit_message_endpoint body reads)
- 2026-11-09: linked conflicts_with MYAI-6 (chat_completions body read)
- 2026-11-09: linked conflicts_with MYAI-7 (chat_completions body read)
- 2026-11-09: linked conflicts_with MYAI-9 (workspace and persona route body reads in backend/chat/router.py)
- 2026-11-09: linked conflicts_with MYAI-19 (resume_chat body reads)
- 2026-11-09: linked conflicts_with MYAI-20 (edit_message_endpoint body read)
- 2026-11-09: linked conflicts_with MYAI-28 (update_system_settings body read and validation)
- 2026-11-09: linked relates_to MYAI-43 (batch 1 follow-ups)
- 2026-11-09: autopilot started (batch-autopilot)
- 2026-11-09: implemented, smoke tests pass
- 2026-11-09: verified live, 8/8 PASS
- 2026-11-09: review round 1 Request changes (1 MAJOR rejected with reason); fixed 10, deferred 1; live re-run PASS
- 2026-11-09: shipped, PR https://github.com/archit342000/My-AI/pull/73
- 2026-11-09: batch-autopilot: shipped, base develop
- 2026-11-09: linked relates_to MYAI-50 (follow-ups from batch 6)
- 2026-11-09: closed, PR merged
