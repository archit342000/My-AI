---
id: MYAI-2
title: "S10: VNC desktop reachable without a password"
status: done
created: 2026-11-08
updated: 2026-11-09
links:
  blocks: [MYAI-39]
  conflicts_with: [MYAI-3]
  relates_to: [MYAI-32]
---

## Description
Report S10 (Medium). playwright_mcp runs x11vnc -nopw and websockify on 6080; every container on secure-internal can reach the desktop, including sandboxed code. Evidence: playwright_mcp/entrypoint.sh:34. **Blocked on a design decision**: passing a password to the browser in a URL violates security.md; options are a server-side authenticated websocket proxy that performs RFB auth, or removing the VNC port from the compose network.

## Acceptance criteria
- [x] VNC requires auth, and the password never reaches the browser
- [x] Portal still connects from the UI
- [x] Decision recorded between the options above (recorded 2026-11-09 in Plan > Context: websockify HTTP auth)

## Plan

**Date:** 2026-11-09  **Status:** Validated

### Objective
Make the portal's VNC desktop in `playwright_mcp` require authentication, so other containers on `secure-internal` (and pages loaded in the container's own Chromium) can't view or drive it. Keep the portal working from the UI. The credential stays server-side: the browser never sees it.

### Context
- Requirement: Description and Acceptance criteria above. Branch from `origin/develop` (at `6a13e04`, after the MYAI-1 merge).
- **Decision (user, 2026-11-09):** use websockify's built-in HTTP auth rather than RFB auth in the app proxy or a new WebSocket bridge in `server.py`. Reasons: no new dependency, small code change, a full-strength key instead of an 8-character VNC password.
- Current behaviour:
  - `playwright_mcp/entrypoint.sh` starts `x11vnc -display :99 -forever -nopw -bg -quiet -xkb`. With no `-localhost`, raw RFB port 5900 listens on all interfaces with no password. It then starts `websockify --web /usr/share/novnc 6080 localhost:5900`, also with no auth.
  - The app proxies both surfaces server-side:
    - `proxy_portal_vnc` in `backend/tools/router.py:246-267` fetches the noVNC files from `http://playwright_mcp:6080/{path}` with httpx.
    - `portal_ws_proxy` in `app.py:61-115` opens `ws://playwright_mcp:6080/websockify` with `websocket-client`'s `create_connection`.
  - The browser reaches both only through the app, behind `require_auth`. Callers: the React UI (`frontend/src/features/tools/PortalDialog.tsx:13`) and the legacy UI (`static/js/browser-portal.js:127`), via `/api/tools/portal/vnc/vnc.html?...&path=api/tools/portal/ws`.
  - Members of `secure-internal` (`docker/docker-compose.yml`): app, bastion_ssh (SSH published on host port 2222), tavily_mcp, playwright_mcp, inference-proxy, the relay code_runner_mcp and mysql_db. Since MYAI-1, sandboxed code sits on `runner-net` only.
- Installed websockify (in image `my-ai-playwright_mcp`): Debian package 0.10.0.
  - `--auth-plugin CLASS` takes a dotted path and is loaded with `__import__`; `--auth-source ARG` is passed to its constructor.
  - `--web-auth` applies the plugin to GET/HEAD of the static files as well as to the WebSocket upgrade (`websockifyserver.py:247-283`, `websocketproxy.py:59-81`).
  - Plugins raise `websockify.auth_plugins.AuthenticationError(response_code=...)`.
  - The stock `BasicHTTPAuth` takes the secret on the command line and compares with `==`, so it isn't used.
- Secret: `PLAYWRIGHT_MCP_API_KEY` is already mounted in both `app` and `playwright_mcp` (compose). The app reads it with `get_secret` (`backend/config.py`, used in `backend/mcp_client.py:103`). The playwright side keeps its own `get_secret` in `playwright_mcp/server.py:32`. Reusing this key means no new secret.
- Rules:
  - `docs/standards/security.md`: secrets only via get_secret / secret files, never logged or returned; internal MCP services use their own API keys; short error bodies with no `str(e)`.
  - `docs/standards/docker.md`: secrets via `secrets:`; healthchecks for substantially changed services; never `--privileged`.
  - `docs/standards/testing.md`: tests for changed code.
  - `CLAUDE.md` / `AGENTS.md`: git-flow, feature branch into develop.
- Note: `playwright_mcp` tests aren't in `scripts/check.sh`. They are run directly (Tests section).

### Approach
1. **Gate websockify.** A small auth plugin, `playwright_mcp/vnc_auth.py`, reads the key from the secret file named by `--auth-source` and checks the HTTP Basic password with `hmac.compare_digest`. It rejects everything when the key is missing or empty (fail closed). It is enabled with `--web-auth`, so the noVNC files and the WebSocket both need auth.
2. **Close raw RFB.** Run x11vnc with `-localhost`, so port 5900 is reachable only inside the container.
3. **Add the credential in the app.** Both app proxies send `Authorization: Basic base64("portal:" + key)` upstream. When the key is empty, they refuse without contacting upstream: 503 for HTTP, close for WS.
4. **Startup.** The entrypoint skips websockify with a clear log line when the secret file is missing or empty, so the portal is unavailable rather than open. The MCP server still starts.

Rejected alternatives:
- RFB auth in the app proxy: needs a DES dependency and handshake code, and VNC passwords are capped at 8 characters.
- WebSocket bridge in `server.py`: needs a new `websockets` dependency and the most new code.
- Stock `BasicHTTPAuth`: secret on the command line and a non-constant-time compare.
- Removing the VNC port from the compose network (the ticket's second option): the app reaches noVNC over `secure-internal`, so the portal would need a new path anyway. Gating the existing path is smaller, and with `-localhost` the raw RFB port does leave the network.

Out of scope, listed under Risks: `/portal/init` auth (MYAI-3); the CDP port 9222; `Xvfb -ac`.

### Steps
#### Step 1: websockify auth plugin
- **Files:** `playwright_mcp/vnc_auth.py` (create), new class `ApiKeyBasicAuth`.
- **Change:**
  - `__init__(src)` stores the secret file path.
  - `authenticate(headers, target_host, target_port)` reads and strips the file on each call, so key rotation needs no restart. If the file is unreadable or empty, it raises `AuthenticationError(response_code=401)`.
  - It parses `Authorization: Basic ...` (bad base64 or a missing `:` gives 401), compares the password as UTF-8 bytes with `hmac.compare_digest` (so non-ASCII input is a clean 401, not a `TypeError`), and ignores the username.
  - It never logs the key or the header.
  - Import `AuthenticationError` from `websockify.auth_plugins` at module level. websockify is only present in the container; tests stub the module.
- **Verification:** Step 6 unit tests.

#### Step 2: Entrypoint changes
- **Files:** `playwright_mcp/entrypoint.sh` (modify).
- **Change:**
  - x11vnc: add `-localhost`; keep `-nopw`, since websockify is the gate and 5900 is no longer reachable from outside the container.
  - websockify: if `/run/secrets/PLAYWRIGHT_MCP_API_KEY` is missing or empty, echo "portal VNC disabled: PLAYWRIGHT_MCP_API_KEY not set" and skip it. Otherwise run `PYTHONPATH=/app websockify --web /usr/share/novnc --web-auth --auth-plugin playwright_mcp.vnc_auth.ApiKeyBasicAuth --auth-source /run/secrets/PLAYWRIGHT_MCP_API_KEY 6080 localhost:5900 &`.
  - The MCP server `exec` is unchanged.
- **Verification:** V1-V4 and V7 in the verification plan.

#### Step 2b: Compose healthcheck for playwright_mcp
- **Files:** `docker/docker-compose.yml` (modify), service `playwright_mcp`.
- **Change:** add a `healthcheck:` with `test: ["CMD", "python3", "-c", "import socket; socket.create_connection(('localhost', 8001), timeout=3)"]` (a TCP connect to the MCP server). It needs no key and doesn't depend on websockify, so it stays healthy when the portal is disabled. This is required by `docs/standards/docker.md:23` for a substantially changed service. Use `interval: 30s`, `timeout: 5s`, `retries: 3`, `start_period: 30s` (Xvfb, fluxbox and the MCP import start first). In `docs/standards/docker.md:23`, change the start to "Health checks: `code_runner_runtime` and the relay `code_runner_mcp` define one (`GET /health`), `playwright_mcp` a TCP check on 8001; other services define none yet." Keep the rest of the line.
- **Verification:** `docker compose -f docker/docker-compose.yml config` is valid; in the live stack the service reports healthy (V8).

#### Step 3: Shared header helper on the app side
- **Files:** `backend/mcp_client.py` (modify), new function `portal_vnc_auth_header() -> dict`, placed next to `playwright_server_url`. Callers import it as `from backend.mcp_client import portal_vnc_auth_header`: inside `proxy_portal_vnc`, matching the local-import style at `router.py:272`, and at module level in `app.py`, next to the flask_sock imports.
- **Change:** add `import base64` to the module imports. The function returns `{"Authorization": "Basic " + base64("portal:" + key)}` using `get_secret("PLAYWRIGHT_MCP_API_KEY", "")`, or `{}` when the key is empty.
- **Verification:** Step 6 backend tests.

#### Step 4: noVNC static proxy sends the header
- **Files:** `backend/tools/router.py` (modify), `proxy_portal_vnc`.
- **Change:**
  - Get the header from `portal_vnc_auth_header()`. If it is empty, return `{"error": "Browser portal is not configured"}` with 503 and don't call upstream.
  - Otherwise pass `headers=` to `client.get`.
  - If upstream returns 401 (key mismatch), log a warning without the key and return 502 with the existing short error.
- **Verification:** Step 6 tests.

#### Step 5: WebSocket proxy sends the header
- **Files:** `app.py` (modify), `portal_ws_proxy`.
- **Change:**
  - Get the header from `portal_vnc_auth_header()`. If it is empty, log a warning and return without connecting; flask-sock closes the socket.
  - Otherwise call `ws_client.create_connection(upstream_url, header=[f"Authorization: {value}"])`, the header list form of websocket-client 1.8.0.
  - The rest of the forwarding loop is unchanged.
- **Verification:** Step 6 tests.

#### Step 6: Tests
- **Files:**
  - `playwright_mcp/tests/test_vnc_auth.py` (create). Stubs `websockify.auth_plugins` in `sys.modules` with a fake `AuthenticationError`, and uses a tmp secret file. Cases: correct password; wrong password; non-ASCII password; missing header; non-Basic scheme; bad base64; no colon; missing file; empty file; rotated key picked up on the next call.
  - `backend/tools/tests/test_router.py` (modify):
    - `test_proxy_portal_vnc` asserts the Authorization header is sent.
    - New test: empty key gives 503 and upstream is not called.
    - New test: upstream 401 gives 502.
  - Existing proxy tests (`test_proxy_portal_vnc`, `test_proxy_portal_vnc_error`, `test_portal_ws_proxy`, `test_portal_ws_proxy_connection_failure`) patch `portal_vnc_auth_header` where it is used (`backend.mcp_client.portal_vnc_auth_header` for the router's local import, `app.portal_vnc_auth_header` for app.py) to return a fixed header. Otherwise the new empty-key guard short-circuits them in a test environment with no secret.
  - `tests/test_app.py` (modify):
    - `test_portal_ws_proxy` asserts `create_connection` is called with the header.
    - New test: empty key means `create_connection` is not called.
  - `backend/tests/test_mcp_client.py` (modify): direct tests for `portal_vnc_auth_header()` (key set gives the correct Basic value; empty key gives `{}`).
- **Verification:** commands in the Tests section pass.

#### Step 7: Docs
- **Files:**
  - `playwright_mcp/README.md` (modify): add `vnc_auth.py` to the files table and describe portal VNC auth (websockify HTTP auth with the MCP key, x11vnc on localhost, disabled when the key is unset).
  - `docs/standards/security.md` (modify): one sentence in Authentication saying the portal VNC is gated by websockify auth with `PLAYWRIGHT_MCP_API_KEY`, added server-side by the app proxies, and never sent to the browser.
- **Verification:** `scripts/check.sh` docs guardrails pass.

### Tests
- `venv/bin/python -m pytest playwright_mcp/tests/test_vnc_auth.py -q -p no:cacheprovider`
- `scripts/check.sh --python-only` (ruff, tests/, backend/, ...), then full `scripts/check.sh` before shipping.
- Live checks (the verify skill): a throwaway compose stack with a unique project name, dummy secrets and no published ports, as in MYAI-1.
  - V1: from a container on secure-internal, `GET playwright_mcp:6080/vnc.html` returns 401 without auth and 200 with the right auth.
  - V2: a WebSocket upgrade to `/websockify` is rejected without auth.
  - V3: raw TCP to `playwright_mcp:5900` is refused.
  - V4: from inside the container, `localhost:6080` also needs auth.
  - V5: via the app (APP_PASSWORD set), the portal opens in a real browser (Playwright): noVNC connects and the canvas renders.
  - V6: the browser's network log and the page source contain neither the key nor an `Authorization: Basic` value for the upstream.
  - V7: with an empty secret, websockify isn't running, the app returns 503 for `/api/tools/portal/vnc/vnc.html`, and MCP tools still work.
  - V8: `playwright_mcp` healthcheck reports healthy, including with the portal disabled.

### Risks and open questions
- Reusing `PLAYWRIGHT_MCP_API_KEY` means one leaked key opens both the MCP API and the desktop. This is acceptable for now, since both are the same service; a separate secret could be added later.
- noVNC still renders a password prompt if upstream asks for RFB auth. It won't, because x11vnc keeps `-nopw` behind localhost.
- Other unauthenticated surfaces in the same container, out of scope:
  - `/portal/init` (MYAI-3, same middleware area; ship separately).
  - CDP on 9222: Chromium binds it to localhost by default; to be confirmed during verify and noted.
  - `Xvfb -ac`: local only.
- Pages loaded in the container's Chromium can reach `localhost:6080`, but they can't supply the key; V4 covers this.
- websockify is from the distro package (unpinned apt). The auth-plugin API is stable in 0.10.x, and the image pins the base tag.

### Success criteria
- [ ] websockify returns 401 for noVNC files and the WebSocket without the key (V1, V2, V4)
- [ ] Port 5900 is not reachable from other containers (V3)
- [ ] The portal still connects from the UI through the app (V5)
- [ ] The key never reaches the browser (V6)
- [ ] Fails closed with no key (V7, unit tests)
- [ ] playwright_mcp has a healthcheck (V8)
- [ ] Tests added and passing; docs updated

### Amendment (2026-11-09): throwaway stack isolation
Found while validating MYAI-17. `docker/docker-compose.yml` uses fixed `container_name`s, published ports (2222, 5001), fixed `image:` tags (`my-ai-code-runner`) and host-absolute bind mounts to live data (`/home/archit-anand/docker-data/shared/My-AI-data`, `.../My-AI-playwright-data`). A copy started under a new project name would collide with the live stack, retag live images, and read and write live data. Any throwaway stack in this plan must follow MYAI-17 Step 7: copy to /tmp; in the copy, delete `container_name:` and `ports:`, prefix every `image:` with a unique verify name, and repoint host-absolute binds to empty /tmp directories; check with `grep -nE '/home/archit-anand|container_name|ports:|image: my-ai'` (no matches); start only the needed services with `--no-deps`; and clean up by image filter.

### Validation log
- Round 1 (Haiku): FAIL, 1 BLOCKING and 6 MINOR. My judgement: FAIL is valid.
  - BLOCKING, no healthcheck for a substantially changed service (docker.md:23): valid. Added Step 2b and V8.
  - Member list was missing mysql_db: valid (compose:157). Fixed.
  - Existing proxy tests would short-circuit on the empty-key guard: valid. Step 6 now patches the helper at the right targets.
  - Imports not stated: valid. Step 3 now states them.
  - Rejected option 2 had no reason: valid. Reason added.
  - compare_digest on str raises TypeError for non-ASCII: valid. Now compares bytes; test case added.
  - No offline test for the entrypoint gating: accepted as covered by V7 (live). Left for the implement stage.
- Round 2 (Haiku, diff-scoped): PASS with 4 MINOR. My judgement: PASS; the earlier BLOCKING item is resolved.
  - docker.md wording not spelled out: valid. Exact text given.
  - No start_period: valid. Timings added.
  - Missing `import base64`: valid (checked mcp_client.py imports). Added.
  - V7/V8 order: cosmetic. Reordered.
- Round 3 (Haiku, diff-scoped): PASS with 4 MINOR. My judgement: PASS. Stop rule met (round 3, no valid BLOCKING).
  - Probe command under-specified: valid. Exact CMD pinned.
  - Keep "(GET /health)" and the rest of the docker.md line: valid. Wording adjusted.
  - Other two items: confirmations, no change needed.

## Implementation notes

### Autopilot run (2026-11-09)
Batch 7 item. Branch bugfix/portal-vnc-auth from origin/develop 2e81c08, PR base develop. Dirty files before start: none. MYAI-3 (PR #74, open) edits neighbouring code: expect conflicts in backend/tools/router.py, backend/tools/tests/test_router.py, playwright_mcp/README.md and docs/standards/security.md.

### Baseline (2026-11-09)
At develop 2e81c08: `pytest backend tests` only the 10 async-plugin failures.

### Implementation progress
- [x] Step 1: playwright_mcp/vnc_auth.py (`ApiKeyBasicAuth`: Basic password vs the key file, sha256 digests with compare_digest, re-read per request, fails closed)
- [x] Step 2: entrypoint: x11vnc `-localhost`; websockify with `--web-auth` and the plugin only when the secret file is non-empty, otherwise "portal VNC disabled"
- [x] Step 2b: compose healthcheck for playwright_mcp (TCP 8001) and the docker.md line
- [x] Step 3: `portal_vnc_auth_header()` in backend/mcp_client.py
- [x] Steps 4-5: the static proxy sends the header (503 without a key, 502 on upstream 401) and the WebSocket proxy connects with it (no key: no connection)
- [x] Step 6: tests (plugin: 12; proxy tests updated and added; mcp_client helper); existing proxy tests patch `portal_vnc_auth_header`
- [x] Step 7: playwright_mcp/README.md, docs/standards/security.md. ruff clean; scripts/check.sh not run as a whole (pytest-asyncio missing)

### Smoke test (2026-11-09)
`pytest backend tests` 1134 pass + the 10 baseline failures; `playwright_mcp/tests/test_vnc_auth.py` 12 pass (run with the throwaway `--target` deps); ruff clean; `docker compose config` valid.
Status on develop (checked at e327094, 2026-11-08): Still present on develop: x11vnc -nopw in playwright_mcp/entrypoint.sh.

PR: https://github.com/archit342000/My-AI/pull/75, branch bugfix/portal-vnc-auth, base develop

## Verification
### Verification plan (2026-11-09, full form: auth in front of a remote desktop)
Throwaway containers on a throwaway network (`myai2v-net`) from the existing local images (nothing rebuilt or retagged, no live mounts, dummy keys, no ports except 127.0.0.1:5093/5092 for the app), following the plan's isolation amendment. Scripts in `scripts/`.
| ID | Criterion | Scenario | Expected |
|----|-----------|----------|----------|
| V1 | AC1 | from another container: noVNC files with no, wrong, empty and right credentials | 401, 401, 401, 200 |
| V2 | AC1 | WebSocket upgrade on /websockify with no, wrong and right credentials | 401, 401, 101 |
| V3 | AC1 | raw TCP to port 5900 from another container | refused |
| V4 | AC1 | from inside the container: localhost:6080 | 401 (x11vnc still reachable on localhost) |
| V5 | AC2 | the portal URL through the app (APP_PASSWORD set) in a real browser | noVNC loads, connects through the app's WebSocket proxy, the desktop renders |
| V6 | AC1 | browser network log and page source | neither the key nor the Authorization value |
| V7 | fail closed | empty secret | websockify not started, app proxy 503, MCP server still healthy |
| V8 | healthcheck | `--health-cmd` as in compose | healthy, also with the portal disabled |
Not run yet.

### Results (2026-11-09)
**Commit verified:** 2e81c08 (+ uncommitted). Hashes: vnc_auth.py c0b2b222, entrypoint.sh 08515cbc, docker-compose.yml c4204aa7, docker.md ec2735f7, mcp_client.py 2999976c, router.py 36418d80, app.py d0df8735, test_vnc_auth.py 92d16b50, test_router.py af17df7f, test_app.py 61bed8a1, test_mcp_client.py b6e87884, README.md 12f22f6e, security.md 17f85464.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | v1-v3.log: 401 without, with a wrong, empty password and for a static file; 200 with the key (any username) |
| V2 | PASS | v1-v3.log: 401, 401, 101 Switching Protocols |
| V3 | PASS | v1-v3.log: ConnectionRefusedError for playwright_mcp:5900 |
| V4 | PASS | v4.log: localhost:6080 gives 401; localhost:5900 reachable inside the container (expected) |
| V5 | PASS | v5-v6.log, ui-portal.png: canvas rendered, WebSocket opened through /api/tools/portal/ws, Fluxbox desktop visible |
| V6 | PASS | v5-v6.log: no leak in requests, responses or page source |
| V7 | PASS | v7-v8.log: "portal VNC disabled: PLAYWRIGHT_MCP_API_KEY not set", 6080 refused, app proxy 503 `Browser portal is not configured` |
| V8 | PASS | v7-v8.log and the first container: healthy (also with the portal disabled) |

Teardown: the four containers and the network removed, /tmp dirs removed, containers, networks and images (same ids) identical to the snapshots, live `playwright_mcp` and app containers still running untouched. **Verdict: verified (8/8 PASS).**

## Review history
### Round 1 - 2026-11-09
Verdict: Approve with comments. Scope: origin/develop 2e81c08..working tree, 13 files, single Haiku reviewer.
- R1-1 [MINOR] `[ -s ]` starts websockify for a whitespace-only secret, unlike the plugin and the app - Static - Fixed (entrypoint tests for a non-whitespace byte; live: a blank secret disables it, 6080 refused)
- R1-2 [MINOR] a websockify that dies at startup was silent - Static - Fixed (bounded wait for port 6080, an ERROR log line when it does not come up)
- R1-3 [MINOR] x11vnc is still passwordless to processes inside the container - Static - Fixed in docs as an accepted residual risk (README, security.md); a generated `-rfbauth` password is beyond the plan
- R1-4 [MINOR] header-parsing cases untested - Static - Fixed (case-insensitive scheme, empty username, colon in the password, unpadded and empty tokens; 20 plugin tests)
- R1-5 [MINOR] test fixture left the re-imported module in sys.modules - Static - Fixed (monkeypatch.delitem)
- R1-6 [NIT] trailing blank line in mcp_client.py - Static - Fixed
Resolution: fixed 6. Checks: `pytest backend tests` only the 10 baseline failures, 20 plugin tests pass, ruff clean, bash -n ok. Runtime change (entrypoint): V1-V3 and V7 re-run in throwaway containers, all PASS (v1-v3-v7-rerun.log).

## Log
- 2026-11-08: created from reports/full-scope-final-report-2026-11-08.md
- 2026-11-09: design decision by user: websockify HTTP auth with PLAYWRIGHT_MCP_API_KEY; plan drafted.
- 2026-11-09: plan validated, 3 rounds.
- 2026-11-09: plan amended: throwaway stack isolation (see Plan > Amendment).
- 2026-11-09: linked conflicts_with MYAI-3 (portal proxies in backend/tools/router.py, playwright_mcp README and security.md)
- 2026-11-09: linked relates_to MYAI-32 (multi-user investigation covers per-user portal and code-runner isolation)
- 2026-11-09: linked blocks MYAI-39
- 2026-11-09: autopilot started (batch-autopilot)
- 2026-11-09: implemented, smoke tests pass
- 2026-11-09: verified live, 8/8 PASS
- 2026-11-09: review round 1 Approve with comments; fixed 6; live re-run PASS
- 2026-11-09: shipped, PR https://github.com/archit342000/My-AI/pull/75
- 2026-11-09: batch-autopilot: shipped, base develop
- 2026-11-09: closed (PR merged into develop)
