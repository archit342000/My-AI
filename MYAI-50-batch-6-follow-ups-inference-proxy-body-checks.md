---
id: MYAI-50
title: "Batch 6 follow-ups: inference_proxy JSON body checks, tavily path guard"
status: todo
created: 2026-11-09
updated: 2026-11-20
links:
  relates_to: [MYAI-18, MYAI-22]
---

## Description
Items found in review of the merged batch 6 PRs (#72, #73) that the validated plans did not cover.

1. **inference_proxy JSON bodies (from MYAI-22).** `inference_proxy/router.py` (lines around 49, 83, 112, 171, 207) still reads `data = request.json or {}`, so a missing, malformed or non-object body gives Flask's HTML 400/415 or a 500 instead of `{"error": ...}` 400. It is a separate service, so it cannot import `backend/utils.read_json_object`; decide between a local copy and a shared module. Same acceptance as the backend routers (docs/standards/api.md).
2. **tavily_mcp protected paths (from MYAI-18).** `AuthMiddleware` guards a literal list (`/sse`, `/messages/...`). `/messages` and `/sse/` skip it and only reach Starlette's redirect to the protected route (no bypass today), and a changed mount path would silently leave routes unguarded. Fix idea: derive the paths from the app settings, or protect everything except an allowlist such as `/health`; add tests for `/messages`, `/sse/` and `//`-prefixed paths.

## Acceptance criteria
- [ ] inference_proxy routes return 400 `{"error": ...}` for a missing, malformed or non-object JSON body, with tests
- [ ] The tavily_mcp guard covers every MCP route without a hard-coded path list (or the list is derived from the app), with path-variant tests

## Plan

**Date:** 2026-11-20  **Status:** Validated

### Objective
Make the inference proxy answer `400 {"error": ...}` for a missing, malformed or non-object JSON body, and make the Tavily MCP key check cover every HTTP route instead of a fixed path list.

### Context
- Requirement: the two items and acceptance criteria of this ticket.
- `inference_proxy/router.py` reads `data = request.json or {}` in `proxy_load_model` (`POST /load`), `proxy_unload_model` (`POST /unload`), `proxy_chat_completions` (`POST /v1/chat/completions`), `proxy_embeddings` (`POST /v1/embeddings`) and `proxy_test_model_speed` (`POST /test-speed`, which also does an unguarded `int(data.get("target_context_threshold", 128000))`). The blueprint is mounted at `/api/models` (`inference_proxy/app.py`).
- The proxy runs as `python3 inference_proxy/app.py` with flat imports (`import config`, `from loader import …`), so `backend.utils` is not importable without changing `sys.path`; its tests add `inference_proxy/` to `sys.path` (`inference_proxy/tests/test_router.py`).
- `backend/utils.py` `read_json_object(required=True, extra=None)` is the backend's rule: `400 {"error": "Request body must be a JSON object"}` for a missing, malformed or non-object body (`docs/standards/api.md`).
- `tavily_mcp/server.py`: `FastMCP` with default paths (`/sse`, `/messages/`), `app = mcp.sse_app(); app.add_middleware(AuthMiddleware)`. `AuthMiddleware` guards only `path in ["/sse", "/messages/"] or path.startswith("/messages/")`; other paths (including `/messages`, `/sse/`, `//sse`) pass through. The service has no other routes (no health route). Tests: `tavily_mcp/tests/test_server.py` (`test_auth_middleware`, `/health` expected to pass through).
- Docs: `tavily_mcp/README.md` (Security line names `/sse` and `/messages/`), `inference_proxy/README.md`, `docs/standards/security.md` (MCP key checks fail closed).

### Approach
- inference_proxy: a local copy of the backend helper in a new `inference_proxy/request_body.py` (`read_json_object`, same messages and behaviour), used by all five routes. Rejected: importing `backend.utils` (needs a `sys.path` change in the service and its tests, and `config` name clashes).
- tavily_mcp: guard every `http` and `websocket` scope (a websocket without the key is closed); only `lifespan` passes. No allowlist, since the service serves nothing else.

### Out of scope
- The `str(e)` texts in the proxy's 500 bodies (MYAI-105 covers older error texts; not in this ticket's criteria).
- Adding a health route or healthcheck to tavily_mcp.
- Validating `/test-speed`'s `target_context_threshold` value (an unguarded `int()`; not a body-shape problem).

### Steps
#### Step 1: `read_json_object` for the inference proxy
- **Status:** todo
- **Depends on:** none
- **Files:** `inference_proxy/request_body.py` (create); `inference_proxy/tests/test_request_body.py` (create)
- **Change:** copy `read_json_object` from `backend/utils.py` (same signature, messages, absent-body rules, `RecursionError` handling and cached parse), with a docstring pointing at the original so the two stay in step.
- **Verification:** tests mirror `backend/tests/test_utils.py` cases: no body, `null`, `[]`, malformed JSON, deeply nested JSON, a UTF-8 BOM, the cached parse, non-JSON content type, a valid object, `required=False`.

#### Step 2: Use it in the five routes
- **Status:** todo
- **Depends on:** Step 1
- **Files:** `inference_proxy/router.py` (modify: the five handlers); `inference_proxy/tests/test_router.py` (modify)
- **Change:** each handler starts with `data, error = read_json_object()` and returns `error` when set (`/unload` too: it forwards the body). Intended changes: an absent or non-object body on any of the five routes now gets the body error instead of the route's own missing-field text (`/load` "Missing 'model' parameter", `/v1/chat/completions` "Missing 'model' or 'messages'", `/v1/embeddings` "Missing 'model' or 'input'", `/test-speed` "Model is required"), and a `null` body on `/unload` is a 400 instead of forwarding `{}` (the callers, `frontend/src/api/settings.ts` and `backend/inference/engine.py`, always send an object).
- **Verification:** parametrized tests over the five routes with no body, malformed JSON and a JSON list: 400 with the JSON error and no upstream call; tests pin the body error on each route, and the missing-field texts still answer for an object without the field; existing route tests pass.

#### Step 3: Tavily key check on every HTTP route
- **Status:** todo
- **Depends on:** none
- **Files:** `tavily_mcp/server.py` (modify: `AuthMiddleware`); `tavily_mcp/tests/test_server.py` (modify)
- **Change:** every `http` and `websocket` scope needs the key: HTTP gets the existing 401 JSON response; a websocket gets an ASGI `{"type": "websocket.close", "code": 1008}` send (a `JSONResponse` is not valid there); `lifespan` passes. Update the docstring. Rewrite `test_auth_middleware` (its `/health` pass-through with `send=None`) and replace `test_auth_leaves_other_paths_and_scopes_alone_even_without_a_key` with a test that only `lifespan` passes, both using a mock `send`.
- **Verification:** tests: `/sse`, `/sse/`, `/messages`, `/messages/x`, `//sse`, `/health` without a key are 401; a websocket scope without a key gets a `websocket.close` message with code 1008 (asserted on the message type, not through the HTTP-status helper); with the key they reach the app; a lifespan scope passes; the other existing key tests pass.

#### Step 4: Docs
- **Status:** todo
- **Depends on:** Steps 2, 3
- **Files:** `inference_proxy/README.md`, `tavily_mcp/README.md`, `docs/standards/api.md` (modify: the `read_json_object` rule also applies to the inference proxy through its local copy)
- **Change:** a line each.
- **Verification:** `pytest tests` passes.

### Tests
- `EMBEDDING_URL="http://mock" AI_URL="http://mock" AI_API_KEY="dummy" PYTHONPATH=. venv/bin/python -m pytest <suite>` for `inference_proxy`, `tavily_mcp` and `tests`, each in its own process; `venv/bin/python -m ruff check .`; `scripts/check.sh`.

### Risks and open questions
- The local copy can drift from `backend/utils.py`; the docstring names the original and the tests use the same cases.
- A future tavily route that must be public (health) would need an explicit exemption then.
- Owner-facing choice recorded: a local copy, not a shared module (the ticket left it open; `docs/standards/api.md` covers the backend routers only).
- No `docs/pitfalls.md` entry: the change removes the path-list trap rather than leaving one.

### Success criteria
- [ ] inference_proxy routes return 400 `{"error": ...}` for a missing, malformed or non-object body, with tests (Steps 1-2)
- [ ] The tavily_mcp guard covers every HTTP route without a path list, with path-variant tests (Step 3)
- [ ] `scripts/check.sh` passes

### Reviewer brief
- Objective: the inference proxy answers 400 `{"error": ...}` for missing, malformed or non-object JSON bodies, and the Tavily MCP key check covers every HTTP and websocket route.
- Key decisions: a local copy of `read_json_object` in `inference_proxy/request_body.py` (not a shared module: flat imports, separate service); every route's missing-field text for absent bodies becomes the body error; tavily guards all `http` and `websocket` scopes (websocket closed with 1008), only `lifespan` passes.
- Out of scope: `str(e)` in the proxy's 500 bodies, a tavily health route, `/test-speed`'s threshold value check.
- Success criteria: as listed in the plan.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
Path: pair, Haiku validators, judged against the code.
- Round 1: L1 FAIL, L2 PASS. Disproved: the local copy contradicts api.md (api.md covers the backend routers only; the ticket left the choice open). Minors fixed (venv commands, drop the threshold check, name both tavily tests, test cases, intended text changes, websocket guard).
- Round 2 (run because round 1's minor fixes added the websocket guard): PASS. Minors fixed inline (websocket.close 1008, all five routes' text changes).

## Implementation notes

## Verification

## Review history

## Log
- 2026-11-09: created from the review of PRs #72 and #73 (user asked for follow-ups for anything not in the plans)
- 2026-11-20: plan validated, 2 rounds
