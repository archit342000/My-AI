---
id: MYAI-3
title: "S9: /portal/init runs without authentication"
status: done
created: 2026-11-08
updated: 2026-11-09
links:
  blocks: [MYAI-39]
  conflicts_with: [MYAI-2, MYAI-5]
  relates_to: [MYAI-18, MYAI-32]
---

## Description
Report S9 (Medium). AuthMiddleware in playwright_mcp covers only /sse and /messages/, so POST /portal/init launches Chromium without a key, reachable from any container on secure-internal. The backend caller (backend/tools/router.py) sends no key. Evidence: playwright_mcp/server.py:448-476 and :809-812, :848. Suggested fix: apply the same check to /portal/init, fail closed when PLAYWRIGHT_MCP_API_KEY is empty, and send X-MCP-API-KEY from the backend caller. Not blocked.

## Acceptance criteria
- [x] POST /portal/init without a key returns 401
- [x] POST /portal/init with the key still works; the backend sends the key
- [x] Fails closed when PLAYWRIGHT_MCP_API_KEY is empty

## Plan

**Date:** 2026-11-09  **Status:** Validated

### Objective
Require the `PLAYWRIGHT_MCP_API_KEY` on `POST /portal/init` in `playwright_mcp`, so other containers on `secure-internal` can't launch the portal Chromium without it. The app's proxy must send the key. The check must fail closed when the key is empty.

### Context
- Requirement: Description and Acceptance criteria above. Branch from `origin/develop` (`6a13e04`).
- Assumptions (no user available):
  - A1: "fails closed" applies to every path `AuthMiddleware` protects in `playwright_mcp` (`/sse`, `/messages/`, `/portal/...`), not just `/portal/init`. One rule for the whole service is simpler and safer than fail-open MCP next to a fail-closed portal. Compose always mounts the secret (`docker/docker-compose.yml:77-78`), so normal deployments don't change. `tavily_mcp`'s identical middleware is out of scope (see Risks).
  - A2: protect the `/portal/` prefix, not only the exact `/portal/init` path, so any later portal route is covered by default.
  - A3: when the app has no key, the app proxy returns 503 without calling upstream. This matches MYAI-2's portal VNC proxy behaviour.
- Current behaviour:
  - `AuthMiddleware.__call__` (`playwright_mcp/server.py:452-476`) checks only `/sse` and `/messages/`, and only `if MCP_API_KEY:`, so an empty key lets everything through. It compares with `!=` and `.decode("utf-8")`, which raises on non-UTF-8 header bytes. The `X-MCP-API-KEY` fallback lookup is dead code, because ASGI header names are lowercase.
  - `MCP_API_KEY = get_secret("PLAYWRIGHT_MCP_API_KEY", "")` is read once at import (`server.py:39`).
  - `portal_init` (`server.py:809-844`) is registered with `@mcp.custom_route`. The middleware is attached at `server.py:847-848` (`app = mcp.sse_app(); app.add_middleware(AuthMiddleware)`).
  - `proxy_portal_init` (`backend/tools/router.py:269-285`) posts to `{base_url}/portal/init` with no headers. It returns `resp.text` and `str(e)` on errors.
  - The MCP client already sends the key as `X-MCP-API-KEY` from `get_secret(...)` (`backend/mcp_client.py:103`). `get_secret` lives in `backend/config.py:6`. The router imports `log_event` (`backend/tools/router.py:5`, from `backend/logging/logger.py:153`); `playwright_mcp` is a separate service and has only its stdlib `logger`.
  - Callers of `/api/tools/portal/init`: `frontend/src/api/filesystem.ts:71` and `static/js/browser-portal.js:116`. They need no change, because the key is added server-side.
  - Existing tests: `backend/tools/tests/test_router.py` `test_proxy_portal_init` and `test_proxy_portal_init_error`. `playwright_mcp/tests/test_server.py` has no middleware tests.
- Rules:
  - `docs/standards/security.md`: read secrets via `get_secret`; never log or return secrets; internal MCP services use their own API keys; short `{"error": ...}` bodies, and don't copy the `str(e)` pattern into new code.
  - `docs/standards/testing.md`: test every changed function; bug fixes add a regression test. `playwright_mcp` tests aren't in `scripts/check.sh`.
  - `docs/pitfalls.md:42-43`: `playwright_mcp` tests fail under the main venv, so run them in the service image.
  - `AGENTS.md`: keep the component README accurate; run `ruff check .` and `scripts/check.sh`.
- Related: MYAI-2 (Validated, not yet implemented) also edits `playwright_mcp/server.py`'s neighbourhood, `backend/tools/router.py` (`proxy_portal_vnc`), `backend/mcp_client.py`, and adds a TCP healthcheck. See Risks.

### Approach
1. **Server middleware.** Generalise the protected-path test to `/sse`, `/messages/...` and `/portal/...`. For those paths:
   - Reject with 401 when `MCP_API_KEY` is empty (fail closed), and log a warning that the key is not configured.
   - Otherwise compare the raw header bytes with `MCP_API_KEY.encode()` using `hmac.compare_digest`. This is constant-time, and non-UTF-8 input becomes a clean 401.
   - Unprotected paths pass through unchanged.
2. **App proxy.** `proxy_portal_init` reads the key with `get_secret("PLAYWRIGHT_MCP_API_KEY", "")` and sends it as `X-MCP-API-KEY`.
   - Empty key: 503 `{"error": "Browser portal is not configured"}`, and no upstream call.
   - Upstream 401: record it with `log_event` (status only, never the key) and return 502 `{"error": "Browser portal authentication failed"}`.
   - The other error paths are unchanged (see Risks).

Rejected alternatives:
- Per-route check inside `portal_init`: a second auth code path; the middleware already exists for this.
- Shared helper in `backend/mcp_client.py`: a one-line `get_secret` call doesn't need it, and it avoids a merge conflict with MYAI-2's helper in that file.
- Fail closed only for `/portal/`: leaves `/sse` and `/messages/` fail-open in the same service for no benefit (A1).

### Steps
#### Step 1: Harden and extend `AuthMiddleware`
- **Files:** `playwright_mcp/server.py` (modify): `AuthMiddleware.__call__`; add `import hmac` to the module imports.
- **Change:**
  - Protected when `path in ("/sse", "/messages/")`, `path.startswith("/messages/")` or `path.startswith("/portal/")`.
  - For protected paths: if `not MCP_API_KEY`, log a warning (path only) and send the 401 `JSONResponse({"error": "Unauthorized"})`.
  - Otherwise take `dict(scope.get("headers", [])).get(b"x-mcp-api-key", b"")` and 401 unless `hmac.compare_digest(value, MCP_API_KEY.encode("utf-8"))`.
  - Drop the dead uppercase lookup and the `.decode`. Never log the key or the header value.
- **Verification:** Step 3 unit tests; live checks L1-L3.

#### Step 2: App proxy sends the key
- **Files:** `backend/tools/router.py` (modify): `proxy_portal_init`.
- **Change:**
  - Add a local import `from backend.config import get_secret`, next to the existing local imports, and read `key = get_secret("PLAYWRIGHT_MCP_API_KEY", "")`.
  - Reading the secret inline is deliberate: it is a secret, not configuration, and it matches `backend/mcp_client.py:103`.
  - If the key is empty, call `log_event("portal_init_unconfigured", {})` and return 503 `{"error": "Browser portal is not configured"}` without opening an `httpx.Client`.
  - Otherwise `client.post(..., headers={"X-MCP-API-KEY": key}, timeout=60.0)`.
  - If `resp.status_code == 401`, call `log_event("portal_init_auth_failed", {"status": 401})` (never the key) and return 502 `{"error": "Browser portal authentication failed"}`, before the existing non-200 branch.
- **Verification:** Step 4 tests; live check L4.

#### Step 3: Server middleware tests
- **Files:** `playwright_mcp/tests/test_server.py` (modify). New async tests that call `AuthMiddleware(inner_app)` directly with a fake ASGI `scope`, `receive` and `send`. Patch `playwright_mcp.server.MCP_API_KEY` with `monkeypatch`.
- **Cases:**
  - `/portal/init`: no key header gives 401 and the inner app is not called; wrong key gives 401; correct key reaches the inner app.
  - Server key empty: 401 for `/portal/init` and for `/sse`, even with an empty header.
  - Non-UTF-8 header bytes give 401, not an exception.
  - `/messages/abc` with the correct key passes.
  - An unprotected path (for example `/other`) passes with no key.
  - A non-http scope (`lifespan`) passes.
- **Verification:** run in the playwright image (Tests section). The new 401 cases fail on current develop, which makes them regression tests.

#### Step 4: Backend proxy tests
- **Files:** `backend/tools/tests/test_router.py` (modify).
- **Change:** patch `backend.config.get_secret` (the router's local import resolves it there) in all of these:
  - `test_proxy_portal_init`: patch it to return `"k"`, and assert `httpx.Client.post` was called with `headers={"X-MCP-API-KEY": "k"}`.
  - `test_proxy_portal_init_error`: patch it to return `"k"`, so the empty-key guard doesn't short-circuit it.
  - New `test_proxy_portal_init_no_key`: patch it to return `""`; expect 503 and `post` not called.
  - New `test_proxy_portal_init_upstream_401`: upstream 401 gives 502 with the short error body.
- **Verification:** `EMBEDDING_URL="http://mock" AI_URL="http://mock" AI_API_KEY="dummy" PYTHONPATH=. venv/bin/python -m pytest backend/tools/tests/test_router.py -q -p no:cacheprovider`

#### Step 5: Docs
- **Files:**
  - `playwright_mcp/README.md` (modify): the Security bullet says `AuthMiddleware` requires `X-MCP-API-KEY` on `/sse`, `/messages/` and `/portal/*`, and rejects all of them when `PLAYWRIGHT_MCP_API_KEY` is unset. Fix the Testing line to say the tests run in the service image (pitfalls.md), not the main venv.
  - `docs/standards/security.md` (modify): one sentence under Authentication saying internal MCP API-key checks fail closed when the key is empty, and that `playwright_mcp`'s portal endpoints need the key too, added server-side by the app.
- **No change needed:** `backend/tools/README.md` and `docs/standards/api.md` don't document `/portal/init` responses (no `portal/init` match in `docs/` or the READMEs).
- **Verification:** `scripts/check.sh` docs guardrails pass.

### Tests
- Playwright MCP (not in check.sh). Build a throwaway test image from the repo root, then run the tests as root (the image ends with `USER pwuser`, `docker/Dockerfile.playwright:35`, so pip can't write site-packages otherwise):
  - `docker build -f docker/Dockerfile.playwright -t myai-pw-test .`
  - `docker run --rm --user root -e PYTHONDONTWRITEBYTECODE=1 -v "$PWD":/src -w /src myai-pw-test sh -c "python3 -m pip install -q pytest==9.0.3 pytest-asyncio==1.3.0 && PYTHONPATH=. python3 -m pytest playwright_mcp/tests -q -p no:cacheprovider"`
  - The pins match the versions installed in the local `venv` (the repo pins neither); they are installed only in the throwaway container, and no requirements file changes. `PYTHONDONTWRITEBYTECODE=1` stops root-owned `__pycache__` from appearing in the checkout.
  - Remove the image afterwards with `docker rmi myai-pw-test`.
- Backend: the Step 4 command, then `ruff check .` and `scripts/check.sh --python-only`, then the full `scripts/check.sh` before shipping.
- Live checks (verify skill): a throwaway compose stack with a unique project name, dummy secrets and no published ports.
  - L1: from another container on `secure-internal`, `POST playwright_mcp:8001/portal/init` with no header gives 401 and no Chromium process starts (`pgrep -f remote-debugging-port` in the container).
  - L2: the same with the correct `X-MCP-API-KEY` gives 200 `created`, then `reused`.
  - L3: with an empty secret file, `/portal/init` and `/sse` both give 401 even with an empty header.
  - L4: through the app (`POST /api/tools/portal/init`), the portal opens from the UI. With the app's secret emptied, the app gives 503.

### Risks and open questions
- **Overlap with MYAI-2:**
  - Both edit `backend/tools/router.py` in adjacent functions (`proxy_portal_vnc` vs `proxy_portal_init`) and `playwright_mcp/README.md`. Both also add a sentence to the Authentication section of `docs/standards/security.md`. Expect trivial merge conflicts; whichever ships second rebases.
  - MYAI-3 deliberately doesn't touch `backend/mcp_client.py`, where MYAI-2 adds `portal_vnc_auth_header`.
  - MYAI-2's healthcheck is a plain TCP connect to 8001, so fail-closed auth can't make it unhealthy.
  - Both use `PLAYWRIGHT_MCP_API_KEY` and the same empty-key behaviour (503 at the app).
  - If MYAI-3 ships first, `playwright_mcp` still has no healthcheck. MYAI-3's change is a small middleware edit, not a "substantial change" under `docs/standards/docker.md:23`, so it doesn't add one; MYAI-2 does.
- **A1 behaviour change:** a `playwright_mcp` run without the secret (for example ad hoc local runs) loses MCP tools as well as the portal. This is intended (fail closed), and it's documented in the README.
- **Not done (out of scope):**
  - `proxy_portal_init` still returns `resp.text` / `str(e)` on other errors (pre-existing; security.md only forbids new uses). Could be a follow-up.
  - `tavily_mcp/server.py` `AuthMiddleware` has the same fail-open `if MCP_API_KEY:` and `!=` comparison. Suggest a separate ticket.
  - The key is read once at import, so rotation needs a container restart (unchanged).
  - `docs/standards/api.md:20-21` lists common status codes without 502/503. `proxy_portal_vnc` already returns 502, so the list is general rather than exhaustive, and it isn't edited here.
- **Open question (non-blocking):** confirm A1 (fail closed for MCP paths too). If the owner wants only `/portal/` to fail closed, Step 1 narrows to one condition, and the `/sse` case in Step 3 and L3 is dropped.

### Success criteria
- [ ] `POST /portal/init` without, or with the wrong, `X-MCP-API-KEY` returns 401 and launches nothing (Step 3, L1)
- [ ] With the key, `/portal/init` works, and the app proxy sends the key (Steps 2 and 4, L2 and L4)
- [ ] An empty `PLAYWRIGHT_MCP_API_KEY` rejects protected paths on the server and gives 503 at the app (Steps 3 and 4, L3 and L4)
- [ ] Tests added and passing (the playwright image run, plus `scripts/check.sh`); README and security.md updated

### Amendment (2026-11-09): throwaway stack isolation
Found while validating MYAI-17. `docker/docker-compose.yml` uses fixed `container_name`s, published ports (2222, 5001), fixed `image:` tags (`my-ai-code-runner`) and host-absolute bind mounts to live data (`/home/archit-anand/docker-data/shared/My-AI-data`, `.../My-AI-playwright-data`). A copy started under a new project name would collide with the live stack, retag live images, and read and write live data. Any throwaway stack in this plan must follow MYAI-17 Step 7: copy to /tmp; in the copy, delete `container_name:` and `ports:`, prefix every `image:` with a unique verify name, and repoint host-absolute binds to empty /tmp directories; check with `grep -nE '/home/archit-anand|container_name|ports:|image: my-ai'` (no matches); start only the needed services with `--no-deps`; and clean up by image filter.

### Validation log
- Round 1 (Haiku): FAIL, 2 BLOCKING and 8 MINOR. My judgement: FAIL is valid.
  - BLOCKING, the `my-ai-playwright_mcp` image tag is not defined by the repo: valid. It exists locally only as a compose-derived name. The Tests section now builds an explicit `myai-pw-test` image.
  - BLOCKING, pip can't install as `USER pwuser`: valid (`docker/Dockerfile.playwright:35`). Added `--user root`.
  - AGENTS.md rule 4 asks for `log_event`: valid for the router. Step 2 now uses `log_event`. The middleware keeps the stdlib `logger`, because `playwright_mcp` is a separate service with no `log_event`.
  - Inline `get_secret` vs "config in config.py": a secret, not configuration, with precedent at `mcp_client.py:103`. Added the rationale.
  - security.md overlap with MYAI-2: valid. Added to Risks.
  - `server.py:40` should be 39: valid. Fixed.
  - A1 scope: already recorded as an assumption and an open question. Kept.
  - Docs completeness: valid. Added a "no change needed" note for `backend/tools/README.md` and `api.md`.
  - Two items were confirmations; no change.
- Round 2 (Haiku, diff-scoped): PASS with 6 MINOR. My judgement: PASS; both BLOCKING items are resolved.
  - Unpinned pytest-asyncio: valid. Pinned to the local venv versions (pytest 9.0.3, pytest-asyncio 1.3.0).
  - `python` vs `python3`: both exist in the image (checked), but switched to `python3` to match the entrypoint.
  - Dockerfile line 33 should be 35: valid. Fixed.
  - Root-owned `__pycache__` in the bind mount: valid. Added `PYTHONDONTWRITEBYTECODE=1`.
  - The Approach still said "log a warning" for the 401 branch: valid. Aligned it with Step 2.
  - api.md status-code list lacks 502/503: noted in Risks. Not edited, because 502 is already used by `proxy_portal_vnc`.
- Round 3 (Haiku, diff-scoped): PASS with 2 MINOR. My judgement: PASS. Stop rule met (round 3, no valid BLOCKING).
  - The pins wording overstated the repo: valid. Reworded.
  - The api.md "general rather than exhaustive" rationale is an inference: accepted as is; it's deferred to the implement or review stage if the owner wants api.md updated.

## Implementation notes

### Autopilot run (2026-11-09)
Batch 7 item. Branch bugfix/portal-init-auth from origin/develop 2e81c08, PR base develop. Dirty files before start: none.

### Baseline (2026-11-09)
At develop 2e81c08: `pytest backend tests` only the 10 async-plugin failures; `playwright_mcp/tests` (needs playwright 1.59.0, playwright-stealth 1.0.6 and setuptools<81, installed with `pip --target /tmp/gen/pwdeps`, nothing added to the venv) 17 pass, 8 fail (asyncio-marked, pytest-asyncio missing).

### Implementation progress
- [x] Step 1: `AuthMiddleware` protects `/sse`, `/messages/...` and `/portal/...`, fails closed, one key header required, sha256 digests with `hmac.compare_digest`, one sanitised warning (same shape as the tavily_mcp fix)
- [x] Step 2: `proxy_portal_init` reads `PLAYWRIGHT_MCP_API_KEY` via `get_secret`, sends `X-MCP-API-KEY`; empty key gives 503 and no upstream call; upstream 401 gives 502 `Browser portal authentication failed` (never the key)
- [x] Step 3: six `anyio`-marked middleware tests (the older tests use asyncio): portal and MCP routes need the key, fail closed, bad keys (non-ASCII, wrong length, repeated header), pass-through paths and scopes, key never logged
- [x] Step 4: backend proxy tests updated and added (key header, 503, upstream 401)
- [x] Step 5: README and security.md
Deviation: the plan's Docker image and throwaway compose stack were replaced by a local run of the real ASGI apps (details in Verification) to stay clear of Docker and the live stack.

### Smoke test (2026-11-09)
`playwright_mcp/tests` 23 pass, 8 baseline failures; `pytest backend tests` only the 10 baseline failures; ruff clean; tests/test_docs.py pass.
Status on develop (checked at e327094, 2026-11-08): Still present on develop: /portal/init is registered at playwright_mcp/server.py:809 and not covered by the middleware check at :458.
Decision (user, 2026-11-09): fail closed on all protected paths (/portal/*, /sse, /messages/) when PLAYWRIGHT_MCP_API_KEY is empty. This matches the plan's assumption, so no plan change is needed.

PR: https://github.com/archit342000/My-AI/pull/74, branch bugfix/portal-init-auth, base develop

## Verification
### Verification plan (2026-11-09, full form: auth on an endpoint that launches a browser)
The real playwright_mcp ASGI app (uvicorn, 5095 with a key, 5094 without) and the real backend app (5099, throwaway DATA_DIR), throwaway keys, `PLAYWRIGHT_BROWSERS_PATH` an empty directory so no Chromium can start; `scripts/v3.py`. Never touches :5000/:5001, containers or the live portal.
| ID | Criterion | Scenario | Expected |
|----|-----------|----------|----------|
| V1 | AC1 | POST /portal/init with no, wrong and non-ASCII key; then the right key | 401 x3; right key passes auth (500 from the missing browser binary) |
| V2 | AC3 | server without a key: /portal/init, /sse, /messages/ | all 401 |
| V3 | AC2 | backend `POST /api/tools/portal/init` with the matching key | the key reaches the server (not 401, not 503) |
| V4 | AC2 | backend with a wrong key | 502 "Browser portal authentication failed", key not in the body |
| V5 | AC3 | backend with no key | 503 "Browser portal is not configured" |
Not run yet.

### Results (2026-11-09)
**Commit verified:** 2e81c08 (+ uncommitted). Hashes: server.py 5838214a, test_server.py a05b8ab5, router.py 6d6b3451, test_router.py b0d4910c, README.md 63cc2ccd, security.md bbf9520b.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | v1-v5.log: 401 without, with a wrong and with a non-ASCII key; the right key got a 500 from the missing browser binary, i.e. it passed the auth check |
| V2 | PASS | v1-v5.log: portal, sse and messages all 401 |
| V3 | PASS | v1-v5.log: the proxy's request reached the route (the 500 body is the route's missing-binary error wrapped by the proxy) |
| V4 | PASS | v1-v5.log: 502 with the short body |
| V5 | PASS | v1-v5.log: 503 with the short body |

Teardown: all processes stopped, ports free, /tmp dirs removed, containers unchanged; the Chromium processes seen by `pgrep` belong to the live container (`/ms-playwright`, `/app/playwright_data`), not this run. **Verdict: verified (5/5 PASS).** Gap: no real browser start was exercised (by design).

## Review history
### Round 1 - 2026-11-09
Verdict: Approve with comments. Scope: origin/develop 2e81c08..working tree, 6 files, single Haiku reviewer.
- R1-1 [MINOR] bypass path shapes and the real app wiring not tested - Static - Fixed (parametrised path variants under and outside the prefixes; a test through the real app with Starlette's TestClient)
- R1-2 [MINOR] the Playwright MCP suite is not in the merge gate (testing.md) - Static - Fixed by disclosure: the PR states it and how the tests were run (plan "Tests" section already says they run in the service image)
- R1-3 [MINOR] noVNC on port 6080 is still unauthenticated and undocumented here - Static - Fixed in docs (README says the 6080 listener is not covered); the fix itself is the portal VNC ticket
- R1-4 [NIT] protected-path predicate hard to read - Static - Fixed (`path == "/sse" or path.startswith(("/messages/", "/portal/"))`)
- R1-5 [NIT] anyio comment wording - Static - Fixed
Resolution: fixed 5. Checks: playwright_mcp tests 34 pass + 8 baseline asyncio failures, `pytest backend tests` only baseline failures, ruff clean. Runtime change (path predicate): live V1-V5 re-run, all PASS (v1-v5-rerun.log).

## Log
- 2026-11-08: created from reports/full-scope-final-report-2026-11-08.md
- 2026-11-09: plan validated, 3 rounds
- 2026-11-09: fail-closed scope confirmed by user (all protected paths).
- 2026-11-09: plan amended: throwaway stack isolation (see Plan > Amendment).
- 2026-11-09: linked conflicts_with MYAI-2 (portal proxies in backend/tools/router.py, playwright_mcp README and security.md)
- 2026-11-09: linked conflicts_with MYAI-5 (both edit proxy_portal_init in backend/tools/router.py)
- 2026-11-09: linked relates_to MYAI-18 (same fail-closed AuthMiddleware change for another MCP server)
- 2026-11-09: linked relates_to MYAI-32 (multi-user investigation covers per-user portal and code-runner isolation)
- 2026-11-09: linked blocks MYAI-39
- 2026-11-09: autopilot started (batch-autopilot)
- 2026-11-09: implemented, smoke tests pass
- 2026-11-09: verified live, 5/5 PASS
- 2026-11-09: review round 1 Approve with comments; fixed 5; live re-run PASS
- 2026-11-09: shipped, PR https://github.com/archit342000/My-AI/pull/74
- 2026-11-09: batch-autopilot: shipped, base develop
- 2026-11-09: closed (PR merged into develop)
