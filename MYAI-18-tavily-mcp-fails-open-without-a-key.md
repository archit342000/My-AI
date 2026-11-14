---
id: MYAI-18
title: "tavily_mcp fails open without a key"
status: done
created: 2026-11-09
updated: 2026-11-09
links:
  relates_to: [MYAI-3, MYAI-50]
---

## Description
Found while planning MYAI-3. `tavily_mcp/server.py` `AuthMiddleware` only checks the key `if MCP_API_KEY:` and compares with `!=`, so with no key configured every MCP route is open to any container on secure-internal, and the compare isn't constant-time. Same pattern as playwright_mcp (MYAI-3) and code_runner (MYAI-4), which now fail closed.

## Acceptance criteria
- [x] Requests without the key return 401
- [x] With an empty MCP_API_KEY, protected routes return 401 (fail closed)
- [x] Key compare is constant-time
- [x] The backend caller still works with the key

## Plan

**Date:** 2026-11-09  **Status:** Validated  **Base:** origin/develop 6a13e04

### Objective
Make `tavily_mcp` fail closed. MCP routes (`/sse`, `/messages/`) must return 401 when the key is wrong or missing, and also when `MCP_API_KEY` itself is empty. Compare keys in constant time. MYAI-3 plans the same change for `playwright_mcp`; it is still todo, and develop still has the fail-open pattern there (`playwright_mcp/server.py:459, 467`), so it's a planned precedent, not landed code.

### Context
- Requirement: Description and Acceptance criteria above.
- Current code (`tavily_mcp/server.py`):
  - `MCP_API_KEY = get_secret("MCP_API_KEY", "")` (line 48), via the module's own `get_secret` (line 39).
  - `AuthMiddleware.__call__` (lines 226-251) protects `path in ["/sse", "/messages/"]` or `path.startswith("/messages/")`, but only `if MCP_API_KEY:`. It compares `api_key != MCP_API_KEY` after a decode.
  - It has a dead uppercase header lookup (ASGI header names are lowercase).
  - The app is `mcp.sse_app()` with `add_middleware(AuthMiddleware)` (lines 281-282).
- Caller: `backend/mcp_client.py` `MCPClient._establish_session` sends `{"X-MCP-API-KEY": get_secret("MCP_API_KEY", "")}` (`tavily_client`, line 174). The app and `tavily_mcp` both mount the `MCP_API_KEY` secret (`docker/docker-compose.yml`). So the backend caller already sends the key, and only the server changes.
- Tests: `tavily_mcp/tests/test_server.py::test_auth_middleware` (line 99) covers websocket passthrough, `/health` passthrough and a wrong key with `MCP_API_KEY` patched to `"secret"`. `scripts/check.sh` runs `tavily_mcp` tests (`PYTHONPATH=. pytest tavily_mcp`).
- Rules:
  - `docs/standards/security.md`: internal MCP services use their own API keys; never log secrets.
  - MYAI-3's plan for `playwright_mcp` (same middleware shape, fail closed on all protected paths, decided by the user 2026-11-09).
  - `docs/standards/python.md`: docstring on the changed method.
  - `docs/standards/testing.md`: test command and env vars.
  - MCP services keep their local `get_secret`. The user approved this exception on 2026-11-09, but it isn't in the standards yet (`python.md:35` and `security.md:5` still say `backend/config.py` only). MYAI-4 Step 5 adds it. This ticket adds no new secret reads, so it doesn't depend on that edit landing first.

### Approach
Same change as MYAI-3 Step 1, applied to `tavily_mcp`.
- For protected paths:
  - If `not MCP_API_KEY`, log a warning (path only) and return the 401 `JSONResponse({"error": "Unauthorized"})`.
  - Otherwise read `dict(scope.get("headers", [])).get(b"x-mcp-api-key", b"")` and return 401 unless `hmac.compare_digest(value, MCP_API_KEY.encode("utf-8"))`. Comparing bytes to bytes means non-ASCII input can't raise.
- Drop the dead uppercase lookup and the decode.
- Unprotected paths and non-HTTP scopes pass through unchanged.
- No backend change, because the caller already sends the key.
- Rejected: refusing to start with an empty key, as MYAI-4 does for the runner. That would take the whole container down, whereas a 401 per request keeps the process up and its logs readable. It also matches MYAI-3. (The app has no unprotected routes besides the SSE ones, so this is only about failure mode.)

### Steps
#### Step 1: Fail closed in `AuthMiddleware`
- **Files:** `tavily_mcp/server.py` (modify): `AuthMiddleware.__call__`; add `import hmac`.
- **Change:** as in Approach. Add a docstring to `__call__` stating which paths are protected and that an empty key rejects them. Never log the key or the header value.
- **Verification:** Step 2 tests.

#### Step 2: Tests
- **Files:** `tavily_mcp/tests/test_server.py` (modify): extend `test_auth_middleware` or add focused tests.
- **Change:** cover these cases:
  - A missing header on `/sse` gives 401, and the app is not called.
  - A wrong key on `/messages/abc` gives 401.
  - The correct key on `/sse` reaches the app.
  - With `MCP_API_KEY` patched to `""`, `/sse` with any header gives 401 (fail closed).
  - A non-ASCII header value gives 401 without raising.
  - `/health` and websocket scopes still pass through.
  Check the 401 status in the `send` mock's first call (`http.response.start`, `status == 401`).
  - Patch `tavily_mcp.server.hmac.compare_digest` with a wrapper and assert it is called for the correct-key case. This pins the constant-time compare criterion.
- **Verification:** `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q tavily_mcp` passes.

#### Step 3: Docs
- **Files:**
  - `tavily_mcp/README.md` (modify): one sentence in the Security bullet under Architectural Context saying MCP routes need `X-MCP-API-KEY` and are rejected when `MCP_API_KEY` is unset.
  - `docs/standards/security.md`: no change. Its Authentication rule already says internal MCP services use their own API keys. If MYAI-3 lands first with a fail-closed sentence, extend that sentence to name `tavily_mcp` too.
- **Verification:** `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q tests/test_docs.py` passes.

#### Step 4: Full gate and live check
- **Change:**
  - Run `venv/bin/ruff check .` and `scripts/check.sh`.
  - Live check: build from the repo root with `docker build -f docker/Dockerfile.mcp -t myai18-verify-tavily .` (the Dockerfile copies `tavily_mcp/requirements.txt`), then run a throwaway container and a unique name, no published ports and a dummy key. Use the image's `CMD` (`python3 -m tavily_mcp.server`, `docker/Dockerfile.mcp:21`; compose sets no command) and mount a dummy key file read-only at `/run/secrets/MCP_API_KEY` (mode 0644), which is the production path; compose uses Docker secrets. Also mount a dummy `TAVILY_API_KEY` the same way. The image doesn't contain the code (compose mounts `../tavily_mcp:/app/tavily_mcp`), so mount the implementation worktree's `tavily_mcp/` read-only at `/app/tavily_mcp`. Following the MYAI-17 Step 7 isolation rules, there are no live data mounts and no live container or image names.
  - From a second throwaway container on a unique network: `curl -s -o /dev/null -w '%{http_code}' --max-time 3` on `/sse` without the key gives 401; with the key it gives 200 (the stream opens and curl times out after sending the status). Then run the real client from a container built from the app image with the repo mounted: `MCPClient(server_url='http://<name>:8000/sse', api_key_secret_name='MCP_API_KEY')` connects and lists tools, with the dummy key supplied as env `MCP_API_KEY` (the backend's `get_secret` falls back to env).
  - Start a second instance with an empty key: `/sse` gives 401 even with a header.
  - Remove the containers, the network and the image.
- **Verification:** all pass; results go in Verification.

### Tests
- `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q tavily_mcp tests/test_docs.py`
- `venv/bin/ruff check .`, then `scripts/check.sh`
- Live check in Step 4

### Risks and open questions
- **A deployment without `MCP_API_KEY` loses web search.** Intended (fail closed). Compose mounts the secret for both the app and `tavily_mcp`.
- **Overlap with MYAI-3.** Same middleware pattern in a different file. The two can share wording in `security.md`; whichever lands second updates that sentence.
- **Shared key.** `MCP_API_KEY` is the generic name for tavily's key. Renaming it is out of scope.
- No blocking open questions.

### Success criteria
- [ ] `/sse` and `/messages/*` return 401 without the key or with a wrong one (Step 2, Step 4)
- [ ] An empty `MCP_API_KEY` rejects protected paths (Step 2, Step 4)
- [ ] The key compare is constant-time (`hmac.compare_digest` on bytes)
- [ ] The backend's tavily client still works with the key (Step 4, plus unchanged `backend/mcp_client.py`)
- [ ] README updated; tests, ruff and `scripts/check.sh` pass

### Validation log
- Round 1 (2026-11-09, Haiku): PASS, 0 BLOCKING and 8 MINOR. My judgement: PASS; I checked all 8 and all were valid, so I applied them.
  - MYAI-3 is a planned precedent, not landed code (playwright_mcp/server.py:459, 467). Reworded.
  - The README has no "server notes" section. Now names the Security bullet.
  - The get_secret exception isn't in the standards yet. Noted; it is added by MYAI-4 Step 5 and isn't a dependency here.
  - The live check used env, not the secrets path. Now mounts /run/secrets/MCP_API_KEY.
  - The real MCPClient wasn't exercised. Added a live MCPClient connect and tool list.
  - No build context, and curl on SSE hangs. `-f` with root context and `--max-time` added.
  - Constant-time criterion untested. A test now asserts `compare_digest` is called.
  - Wrong "/health" rationale (no such route). Reworded.
  Marked Validated: no BLOCKING in round 1 and all minors applied (same convention as MYAI-9 and MYAI-15; a further round was skipped to save quota).

## Implementation notes

### Autopilot run (2026-11-09)
Batch 6 item. Branch bugfix/tavily-fail-closed from origin/develop 24e912d, PR base develop. Dirty files before start: none.

### Baseline (2026-11-09)
At develop 24e912d: `pytest tavily_mcp` 5 pass, 5 fail (the `@pytest.mark.asyncio` tests: pytest-asyncio missing); `pytest backend tests` only the 10 async-plugin failures.

### Implementation progress
- [x] Step 1: `AuthMiddleware` fails closed (empty key or missing/wrong key gives 401), `hmac.compare_digest` on bytes, dead uppercase header lookup and decode removed, docstring added
- [x] Step 2: five new tests (marked `anyio`, because the existing `asyncio`-marked tests cannot run without pytest-asyncio): missing/wrong key, constant-time compare called, fail closed with an empty or missing key, non-ASCII key, other paths and scopes untouched
- [x] Step 3: tavily_mcp/README.md Security bullet; tests/test_docs.py passes
- [x] Step 4: ruff clean; live check below. Deviation: the plan's Docker build/containers were replaced by running the real ASGI app with uvicorn on throwaway ports, which exercises the same middleware over HTTP without touching Docker. scripts/check.sh not run as a whole (pytest-asyncio missing)
Defect shown against develop's server.py in a scratch module: with an empty key a request with no header reaches the app.

### Smoke test (2026-11-09)
`pytest tavily_mcp`: 10 pass, the same 5 baseline failures; `pytest backend tests` only the 10 baseline failures; tests/test_docs.py pass; ruff clean.
None yet.

PR: https://github.com/archit342000/My-AI/pull/72, branch bugfix/tavily-fail-closed, base develop

## Verification
### Verification plan (2026-11-09, light form)
The real tavily_mcp ASGI app run with uvicorn on throwaway ports (5097 key set, 5096 no key), throwaway keys, `scripts/v18.py`; no Docker, no live services, no network beyond localhost.
| ID | Criterion | Scenario | Expected |
|----|-----------|----------|----------|
| V1 | AC1, AC3 | /sse and /messages/ with no key, wrong key, non-ASCII key, right key | 401, 401, 401, right key accepted |
| V2 | AC2 | server started without MCP_API_KEY | protected routes 401 with or without a header |
| V3 | AC4 | `backend.mcp_client.MCPClient` with the key | connects and lists the tavily tools |
Not run yet.

### Results (2026-11-09)
**Commit verified:** 24e912d (+ uncommitted). Hashes: server.py 7970226f, test_server.py 4255b2cf, README.md 95c1dc9c.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | v1-v3.log: no key 401, wrong key 401, wrong key on /messages 401, non-ASCII key 401, right key 200 |
| V2 | PASS | v1-v3.log: no key, any key, /messages all 401 |
| V3 | PASS | v1-v3.log: MCPClient lists async_tavily_map_tool, async_tavily_search_tool, audit_search, search_web |

Teardown: both servers stopped, ports 5096/5097 free, containers and git status unchanged. **Verdict: verified (3/3 PASS).** Constant-time compare is pinned by a unit test (`compare_digest` called), not measurable live.

## Review history
### Round 1 - 2026-11-09
Verdict: Request changes (1 MAJOR, judged below). Scope: origin/develop 24e912d..working tree, 3 files, single Haiku reviewer.
- R1-1 [MAJOR] the premise "like the other MCP services" is false: playwright_mcp and code_runner_mcp still fail open - Static - Rejected as a defect of this change: it is the ticket's premise (MYAI-3 and MYAI-4 cover those services and are still open); the change and PR make no parity claim
- R1-2 [MINOR] protected path list is a literal; `/messages` and `/sse/` skip the guard - Static - Deferred: they only reach Starlette's redirect to the protected route, so no bypass; hardening (derive from the app settings or allowlist) is a follow-up
- R1-3 [MINOR] duplicate `x-mcp-api-key` headers decided by order - Static - Fixed (exactly one header required; tests in both orders)
- R1-4 [MINOR] compare_digest on raw bytes leaks the key length; docstring overstated - Static - Fixed (compare sha256 digests; docstring reworded)
- R1-5 [MINOR] two warnings per request, unsanitised path in the log - Static - Fixed (one warning with the reason, `{path!r}`)
- R1-6 [MINOR] test asserted compare_digest call count - Static - Fixed (behaviour tests with same-length, shorter and longer wrong keys; one test pins the digest arguments)
- R1-7 [MINOR] no test that the key is absent from logs, none for duplicate headers - Static - Fixed (caplog test, duplicate-header test); path cases deferred with R1-2
- R1-8 [MINOR] mixed asyncio and anyio markers unexplained - Static - Fixed (comment)
- R1-9 [NIT] import inside a test - Static - Fixed (module top; `logging` import in the caplog test kept local)
Resolution: fixed 7, rejected 1, deferred 1. Checks: `pytest tavily_mcp` 13 pass and the 5 baseline asyncio-marker failures, ruff clean. Runtime change in server.py: live V1-V3 re-run, all PASS (v1-v3-rerun.log).

## Log
- 2026-11-09: created (follow-up found while planning MYAI-2 to MYAI-16)
- 2026-11-09: plan validated, 1 Haiku round.
- 2026-11-09: linked relates_to MYAI-3 (same fail-closed AuthMiddleware change for another MCP server)
- 2026-11-09: autopilot started (batch-autopilot)
- 2026-11-09: implemented, smoke tests pass
- 2026-11-09: verified live, 3/3 PASS
- 2026-11-09: review round 1; fixed 7, rejected 1, deferred 1; live re-run PASS
- 2026-11-09: shipped, PR https://github.com/archit342000/My-AI/pull/72
- 2026-11-09: batch-autopilot: shipped, base develop
- 2026-11-09: linked relates_to MYAI-50 (follow-ups from batch 6)
- 2026-11-09: closed, PR merged
