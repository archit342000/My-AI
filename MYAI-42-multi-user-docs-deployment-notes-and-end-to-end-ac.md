---
id: MYAI-42
title: "Multi-user: docs, deployment notes and end-to-end Access check"
status: in-progress
created: 2026-11-09
updated: 2026-11-10
links:
  blocked_by: [MYAI-33, MYAI-34, MYAI-35, MYAI-36, MYAI-37, MYAI-38, MYAI-39, MYAI-40, MYAI-41]
  split_from: [MYAI-32]
---

## Description
Split from MYAI-32 (Step 10: Docs, deployment and end-to-end check). Part of making My-AI multi-user behind Cloudflare Access. Implement after MYAI-1 to MYAI-31 have merged.

Read the MYAI-32 Plan first: the Audit (single-user assumptions with file references), the Approach, the Decisions and the Reviewer brief are binding for this ticket. Step scope from MYAI-32:

- **Depends on:** MYAI-33, MYAI-34, MYAI-35, MYAI-36, MYAI-37, MYAI-38, MYAI-39, MYAI-40, MYAI-41
- **Files:** `docs/standards/security.md` (Authentication, Ownership, Admin-only sections), `docs/architecture.md` (auth component, request flow through Access), `docs/data.md` (checked against step 2), `README.md` (access is through the Access hostname; with `cloudflare_access` the SSH tunnel path no longer works without a JWT; with the `static` provider (local development only) every request runs as `AUTH_STATIC_EMAIL`; keep it within the 100-line budget in `tests/test_docs.py`), `backend/README.md` and the component READMEs that each step touched (`backend/auth/README.md` created in step 1). `docker/docker-compose.yml` (check that only the app joins the tunnel network, with no new published ports).
- **Change:** docs match the code; the deployment note records that only the app is routed (never `bastion_ssh` 2222 or the inference proxy's 5001).
- **Verification:** live check through a real Access application with two identities: no JWT gives 401; a tampered JWT gives 401; user B gets 404 for user A's chat, file and artifact; user B gets 403 on admin routes. Full `pytest`, `npm` checks and `ruff check .`.

## Acceptance criteria
- [ ] `docs/standards/security.md`, `docs/architecture.md`, `docs/data.md`, `README.md` (within its line budget), `backend/README.md` and the touched component READMEs match the code
- [ ] The deployment notes say only the app is routed through the tunnel (never `bastion_ssh` 2222 or inference-proxy 5001)
- [ ] Live check through a real Access application with two identities: no or tampered JWT gives 401; cross-user chat, file and artifact access gives 404; admin routes give 403 to a user
- [ ] The full `pytest`, the frontend checks and `ruff check .` pass

## Plan
**Date:** 2026-11-09  **Status:** Validated

### Objective
Finish the multi-user work.
- Connect the app, and only the app, to the gateway's tunnel network, with no new published ports.
- Bring every affected doc into line with the code after MYAI-33 to MYAI-41.
- Record the deployment rules.
- Prove the whole design end to end through a real Cloudflare Access application with two identities: authentication, ownership, admin gating, WebSocket upgrades and rate limits.

### Context
- **Requirement:** this ticket's Description and Acceptance criteria. MYAI-32 Plan: Audit item 14, Step 10, Decisions 1-4. Open items handed over: MYAI-33 Risks (the Access header on WebSocket upgrades is undocumented; JWKS outage recovery), MYAI-41 Risks (Access edge redirect on an expired session), and MYAI-39 (left at "Draft - unresolved issues"; its live checks need to have passed).
- **Assumes merged:** MYAI-33 to MYAI-41, each with its own docs updates (security, api, data, tools, frontend and component READMEs).
- **Current deployment** (`docker/docker-compose.yml`):
  - The `app` service publishes no port and is on `secure-internal` (MYAI-1 adds `runner-net`).
  - `bastion_ssh` publishes `2222:2222` (43-44); `inference-proxy` publishes `5001:5001` (87-88).
  - The gateway and `cloudflared` live in a separate repo (MYAI-32 Out of scope), so the app needs a network the gateway's connector can reach.
- **Doc rules:**
  - `docs/standards/docs.md`.
  - `tests/test_docs.py` budgets: `README_MAX_LINES = 100`, `DOCS_MAX_LINES = 200`, `AGENTS_MAX_LINES = 80`. Backticked paths in docs must resolve, and README table file references must exist.
  - `docs/standards/review.md` item 6: a `docs/pitfalls.md` entry for traps found.
- **Gitflow:** `docs/standards/gitflow.md` (release notes come later, not here).

### Approach
- **Tunnel network:**
  - A new top-level network, `edge`, declared `external: true` with `name: ${EDGE_NETWORK:-my-ai-edge}`. The gateway repo creates it and attaches its `cloudflared` service to it.
  - Only `app` joins it, alongside its existing networks. No service gains a `ports:` entry. The gateway reaches `http://app:5000` over `edge`.
  - `bastion_ssh` and `inference-proxy` keep their host ports but never join `edge`, so neither is reachable through the tunnel.
  - A compose check, `docker compose -f docker/docker-compose.yml config`, confirms that only `app` lists `edge`.
- **Docs pass:** one read-through of every doc touched by MYAI-33 to MYAI-41, against the code, fixing drift only (no new design):
  - `docs/standards/security.md`, `docs/standards/api.md`, `docs/architecture.md`, `docs/data.md`, `docs/tools.md`, `docs/frontend.md`, `docs/standards/frontend.md`.
  - `README.md`, `backend/README.md`, `backend/auth/README.md` and the component READMEs those tickets changed.
  - Additions:
    - `docs/architecture.md`: a "Request flow" paragraph: Access, then tunnel, then `app` (`authenticate_request`), then the owner checks.
    - `docs/standards/security.md`: a "Deployment" subsection: only `app` on `edge`; never route `bastion_ssh` or `inference-proxy`; `AUTH_PROVIDER=static` only for local development; set `ADMIN_EMAIL`; add users with `python -m backend.auth.cli`.
    - `docs/pitfalls.md`: entries for traps the work confirmed:
      - streaming generators run without the user context (MYAI-35);
      - a JWKS outage fails closed (MYAI-33);
      - the Access header on WebSockets (as observed in the live check);
      - Access edge redirects on an expired session (as observed).
  - `README.md` is at the 100-line budget and must stay net zero. MYAI-33 already replaced line 63 (`secrets/APP_PASSWORD`) and line 74 ("accessible at `http://localhost:5000`"). This step confirms both are gone. If not, it rewrites them in place: line 63 as the `ADMIN_EMAIL` setup line, and line 74 as one line saying access is through the Access hostname, with deployment rules in `docs/standards/security.md`. Nothing else is added.
  - `docs/standards/docker.md:17` ("Services share the `secure-internal` network") gains one clause: `app` also joins `runner-net` (MYAI-1) and `edge` (this ticket).
- **End-to-end check:** run through a real Access application (a throwaway hostname or the gateway's staging route), with two Access identities added as users with the CLI (one admin, one user).
  - **Data isolation:** `docker/docker-compose.yml:17` hard-codes the real data path, so the check runs from the deployment checkout (where `secrets/` is populated), with:
    - the production stack stopped for the duration (container names and host ports are fixed, so two stacks can't run side by side);
    - an override file kept in the evidence folder (not committed), passed as a second `-f`, that remaps only the `app` data volume (container target `/app/backend/data`) to a copy of the data directory (`cp -a` of the real one, taken while the stack is stopped). Only `docker/docker-compose.yml` plus that override are used, never `docker/docker-compose.testing.yml` (which also mounts the real path).
  - Before `up`, `docker compose -f docker/docker-compose.yml -f <override> config` must show the copy's path as the `app` volume source and no service mounting the real data path; otherwise the check doesn't start.
  - After the check, the production stack is restarted unchanged. The scenarios are in Step 3. Evidence (HTTP status lines, screenshots, logs with tokens redacted) goes to `~/.claude/tickets/My-AI/MYAI-42-evidence/`.
  - If no Access application is available, this ticket stays open, with the gap reported. It is not closed on local checks alone.
- **Rejected:**
  - Publishing `app:5000` on the host for the gateway: it exposes the app outside Access.
  - Defining the `edge` network in this repo: the gateway owns the tunnel, so it owns the network.

### Out of scope
New features or design changes (findings become new tickets); the gateway repo's own config; release notes and version bump (`docs/release.md`, a later release step); removing the legacy UI.

### Steps
#### Step 1: Tunnel network in compose
- **Status:** todo
- **Depends on:** none within this plan (the 401 check needs MYAI-33 merged; run it from the deployment checkout with `secrets/` populated)
- **Files:** `docker/docker-compose.yml` (modify): the `edge` external network and the `app` service's `networks`.
- **Change:** as in Approach.
- **Verification:**
  - `docker network create my-ai-edge` (throwaway), then `docker compose -f docker/docker-compose.yml config`: only `app` lists `edge`, and the set of `ports:` entries is unchanged (only `2222` and `5001`).
  - A container on `edge` can reach `http://app:5000/api/version` (401 without a token) and can't reach `bastion_ssh:2222` or `inference-proxy:5001`.

#### Step 2: Docs pass
- **Status:** todo
- **Depends on:** 1
- **Files:** `docs/architecture.md`, `docs/standards/security.md`, `docs/standards/docker.md`, `docs/pitfalls.md`, `README.md` (modify). Drift fixes, if any, in `docs/standards/api.md`, `docs/data.md`, `docs/tools.md`, `docs/frontend.md`, `docs/standards/frontend.md`, `backend/README.md`, `backend/auth/README.md` and the READMEs touched by MYAI-33 to MYAI-41 (each fix listed in Implementation notes).
- **Change:** as in Approach. Every statement checked against the code it describes.
- **Verification:**
  - `pytest tests` (budgets, links, README tables).
  - `grep -rn "APP_PASSWORD\|require_auth\|HTTP Basic" docs README.md backend --include=*.md | grep -v docs/archive` finds nothing (after the README lines above are confirmed or rewritten).
  - The security "Deployment" subsection names both `bastion_ssh` (2222) and `inference-proxy` (5001) as never routed (checked by grep for `2222` and `5001` in it).
  - A reviewer-style read of the security section against `backend/auth/` finds no mismatch.

#### Step 3: End-to-end check through Access
- **Status:** todo
- **Depends on:** 1
- **Files:** none in the repo; evidence in `~/.claude/tickets/My-AI/MYAI-42-evidence/`.
- **Change:** run the scenarios and record the results.
- **Verification:** each scenario passes, with evidence:
  1. **Authentication:**
     - A request to the app hostname with no Access session is stopped by Access.
     - A direct request on `edge` without the header gets 401.
     - A request with a tampered token (one changed signature byte) gets 401.
  2. **Identity:** `/api/me` shows the right email and role for both identities; an Access identity that isn't a local user gets 403.
  3. **WebSocket:** the code-run WebSocket works through the tunnel for the admin. The `Cf-Access-Jwt-Assertion` header is present on the upgrade (recorded from the app log). An upgrade without it gets 401.
  4. **Ownership:** for each resource the user gets 404 with user A's id, and their lists don't show A's items:
     - A's chat URL, history, stream and resume;
     - A's uploaded file and file-system artifact (get, raw, export);
     - A's persona, skill and preference;
     - A's code-run history and live run.
  5. **Admin gating:**
     - The user gets 403 on system settings, logs, model load and `/legacy/`.
     - The user can't open the portal or enable git mode.
     - The admin can do all of these.
  6. **Isolation (from MYAI-39):** a cookie set in A's browsing session is absent in B's, and two simultaneous runs execute one after the other.
  7. **Rate limits:** with `RATE_LIMIT_TURNS_PER_MINUTE=2` on the throwaway stack, the user's third send within a minute gets 429.
  8. **Expired session:** after the Access session is revoked, the UI behaviour is recorded (the app banner, or an Access redirect, per MYAI-41 Risks).
  9. **Data:** after the run, the copy's original chats are all owned by the admin and intact (row counts match the source), and the real data directory's `chats.db` checksum is unchanged from before the check.
  Any failure becomes a bug ticket linked `relates_to` here and blocks closing.

#### Step 4: Full gate
- **Status:** todo
- **Depends on:** 2, 3
- **Files:** none.
- **Change:** none.
- **Verification:** on a `feature/<topic>` branch from `develop`, with the PR into `develop` (`docs/standards/gitflow.md`). With the env from `docs/standards/testing.md`: `pytest tests`, `pytest backend`, `pytest inference_proxy`, `pytest tavily_mcp`, `cd code_runner_mcp && PYTHONPATH=. pytest`; in `frontend/`, `npm run typecheck`, `lint`, `test`, `build`; `ruff check .`.

### Tests
No new unit tests; the work is compose, docs and live verification. The docs guardrails run in `pytest tests`.

### Risks and open questions
- **The live check needs a real Access application and two identities.** That's the user's dependency; Step 3 says the ticket stays open without them.
- **MYAI-39's plan was left with unresolved validation.** Its live checks (scenario 6) confirm the implemented behaviour here.
- **If the Access header is missing on WebSocket upgrades** (scenario 3), MYAI-33's recorded fallback (accept the `CF_Authorization` cookie on upgrades only) becomes a follow-up ticket.

### Success criteria
- [ ] Only `app` joins the gateway's `edge` network, and no new ports are published.
- [ ] Docs match the code (security, API, architecture, data, tools, frontend, READMEs), with deployment rules and pitfalls recorded; `pytest tests` passes.
- [ ] All Step 3 scenarios pass through a real Access application, with evidence recorded.
- [ ] Full test suites, frontend checks and `ruff check .` pass.

### Reviewer brief
- **Objective:** connect only `app` to the gateway's tunnel network with no new published ports, align all docs with MYAI-33 to MYAI-41, record the deployment rules and pitfalls, and prove the design end to end through a real Cloudflare Access application with two identities.
- **Key decisions:**
  - An external `edge` network (`${EDGE_NETWORK:-my-ai-edge}`, owned by the gateway repo) is joined only by `app`. `bastion_ssh` and `inference-proxy` are never on it.
  - The docs pass fixes drift only. It adds a request-flow paragraph, a security "Deployment" subsection, the `docker.md` network line and pitfalls entries. The README stays net zero.
  - The end-to-end check runs from the deployment checkout with the production stack stopped and a non-committed override pointing `app` at a copy of the data, gated by `compose config`. It covers nine scenarios: authentication, identity, WebSocket header, ownership, admin gating, isolation, rate limits, expired session and data integrity.
  - The ticket stays open without a real Access application. Failures become linked bug tickets.
- **Out of scope:** new features, the gateway repo's config, release notes, legacy UI removal.
- **Success criteria:** as listed in the Plan.

The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- **Round 1:** the validator returned FAIL (3 BLOCKING, 5 MINOR). My judgement: FAIL.
  - BLOCKING:
    - README budget and the `APP_PASSWORD` grep: partly covered by MYAI-33 Step 8, but this plan now confirms or rewrites lines 63 and 74 net zero.
    - The data-copy mechanism was missing, a real-data risk because compose hard-codes the data path: fixed with a stopped-stack copy, an override and a `config` gate.
  - MINOR, fixed: the `secrets/` precondition (run from the deployment checkout); `docker.md:17`; the gitflow branch; a grep for 2222 and 5001; the MYAI-33 dependency noted on Step 1.
- **Round 2 (diff-scoped):** the validator returned PASS (0 BLOCKING, 1 MINOR). My judgement: PASS. MINOR, fixed: the override's container target, a ban on `docker-compose.testing.yml`, and the `config` gate checking that no service mounts the real path.

## Implementation notes
### Autopilot run (2026-11-09)
batch-autopilot item 12/13; branch feature/multi-user-live-check, base feature/multi-user-frontend-gating (stacked on the MYAI-41 PR); no pre-existing dirty files. Step 3 needs a real Cloudflare Access application with two identities, which this session does not have: it will be run only as a local emulation (real app, stub JWKS) and recorded as such; the ticket stays open per its plan.

### Baseline (2026-11-09)
backend+tests: 10 failed (async-plugin baseline), frontend 355 passed.

### Implementation progress
- [x] Step 1: Tunnel network in compose - docker/docker-compose.yml: external network `edge` (`${EDGE_NETWORK:-my-ai-edge}`), only `app` joins it. `docker compose config` shows only `app` on `edge`; the published ports are unchanged (2222 bastion_ssh, 5001 inference-proxy). NOT run: a container on `edge` reaching `app:5000` and failing to reach 2222/5001 (needs building and starting the stack, whose compose file hard-codes the real data path).
- [x] Step 2: Docs pass - README.md (deployment line rewritten in place, still 100 lines), docs/architecture.md (Request flow), docs/standards/security.md (Deployment), docs/standards/docker.md (edge clause), docs/pitfalls.md (Multi-user: user context outside the request, JWKS outage). `grep APP_PASSWORD|require_auth|HTTP Basic` finds nothing. Not added: pitfalls for the Access header on WebSocket upgrades and for an expired-session edge redirect, because both need the real Access check to be observed (written only from observation).
- [~] Step 3: End-to-end check - NOT done through a real Access application (none available to this session). Local emulation instead (real app, real `CloudflareAccessProvider` with a local JWKS stub, throwaway DATA_DIR, signed test JWTs, alice admin / bob user; script and output in MYAI-42-evidence/e2e_local.py and e2e_local.out): 14 checks passed: scenario 1 (no, tampered, garbage, foreign-key, wrong-audience, expired token and static/legacy paths all 401), 2 (`/api/me`, unknown Access identity 403), 3 (WebSocket upgrade without the header refused, owner's run starts, another user "Chat not found"), 4 (14 cross-user requests all 404, lists clean, data intact), 5 (user 403 on settings, agents, browser, logs, legacy, model load/unload, portal; admin never 403; the git-mode probe only reached a 404 for a foreign chat, the real 403 is covered in MYAI-38's live check), 7 (third send 429, admin exempt), 9 (a legacy ownerless chat became the admin's, bob 404, nothing lost), and no JWT in the server log. Scenarios 6 (cookie isolation, simultaneous runs), 8 (expired Access session in a real browser) and the real-Access parts of 1 to 3 (login redirect, header on the tunnel's upgrade) are NOT covered. Per the plan this ticket stays open until they are run.
- [x] Step 4: Full gate - backend+tests 10 failed (baseline) / 1633 passed; inference_proxy 46 passed; tavily_mcp 5 failed (baseline, untouched) / 13 passed; code_runner_mcp 214 passed, 1 skipped; playwright_mcp 8 failed (baseline) / 71 passed; frontend typecheck, lint clean, vitest 355 passed, build ok; ruff clean.
- Branch: feature/multi-user-live-check (base feature/multi-user-frontend-gating).
PR: https://github.com/archit342000/My-AI/pull/95, branch feature/multi-user-live-check, base feature/multi-user-frontend-gating (the real-Access end-to-end check is still open)

## Verification

### Live Access check through the gateway (2026-11-10, from the architanand.dev session)
Real setup: `https://myai.architanand.dev` → Cloudflare Access app (owner-only, AUD `39c2a567…991d`) → tunnel `local` → `edge` → `my-ai:5000`.
- PASS: login through Access works; My-AI loads; chat works (once a loadable model is selected); non-WebSocket portal calls (`POST /api/tools/portal/init`, `GET /api/tools/code-execution/history/<id>`) return 200 via the tunnel; without a JWT, `/` and `/api/me` return 401 from `edge`.
- FAIL (portal black): `GET /api/tools/portal/vnc/vnc.html?autoconnect=true&resize=scale&path=api/tools/portal/ws` returns **308** to `http://myai.architanand.dev/api/tools/portal/vnc/?autoconnect=true...`. Cause: `backend/tools/router.py:284-285` registers `/portal/vnc/` with `defaults={'path': 'vnc.html'}` plus `/portal/vnc/<path:path>`; Werkzeug redirects a URL that equals a rule's defaults to the canonical rule (redirect_defaults), and builds it with `http` because the app sees plain HTTP behind the tunnel (no ProxyFix / X-Forwarded-Proto). The browser blocks the http URL inside the https page, noVNC never loads, and no WebSocket request reaches the app. Reproduced with a Werkzeug Map in the app container; upstream `playwright_mcp:6080/vnc.html` itself returns 200.
- Suggested fix: avoid the defaults redirect (`redirect_defaults=False` on the rule, or drop the defaults rule), and trust the tunnel's `X-Forwarded-Proto` (`werkzeug.middleware.proxy_fix.ProxyFix(app.wsgi_app, x_proto=1)`) so other redirects use https.
- Still open: whether `Cf-Access-Jwt-Assertion` arrives on WebSocket upgrades (portal `/api/tools/portal/ws`, live run `/api/tools/code-execution/ws`), blocked by the above. Code execution was also reported broken; not yet diagnosed (no `/api/tools/code-execution/ws` request seen in the logs).

### Findings from the live check: status (2026-11-10)
- **Portal black (308 to http): fixed in PR #100** (bugfix/portal-vnc-redirect-and-proxy-headers, base develop): the entry page is its own route (no `defaults` redirect) and `ProxyFix(x_proto=1)` keeps redirects https; tests fail without the change. Needs a redeploy and a re-check through the tunnel (not re-run).
- **Code execution "broken": diagnosed.** Two separate causes. (1) The deployed runtime refuses every run: `runner_cleanup_error path=/tmp/hsperfdata_root ... Operation not permitted` (a root-owned directory left in the image's `/tmp` by a JVM run at build time, which the server running as `runner` cannot remove), so `POST /execute` answers `error: "Runner cleanup failed."` (reproduced from the app container through the relay). Fixed by the split-uid isolation PR #98 (cleanup removes only the runner uid's files, `/tmp` is a tmpfs); the deployed container was not modified (existing-containers rule). It stays broken until #98 is merged and the runtime is rebuilt. (2) The React UI has no live-run WebSocket client at all (`/api/tools/code-execution/ws` is used only by the legacy `static/script.js`; React only lists history), which is why no such request ever reached the app: a missing frontend feature, not a regression, not part of this ticket.
- **Still open:** whether `Cf-Access-Jwt-Assertion` arrives on WebSocket upgrades: the portal `/api/tools/portal/ws` can be checked once #100 is deployed; the live-run socket cannot be checked from the React UI (needs the legacy UI or a custom client).

### Live re-check after deploy (2026-11-10, user-confirmed)
Deployed develop (PRs #98, #99, #100) to the production stack. PASS: code execution works (`/execute` through the relay returns uid 61001, no cleanup error; runtime `CapEff 0xe0`); the browser portal loads through `https://myai.architanand.dev` (the black frame persisted only because Chrome had cached the earlier permanent 308 redirect; a fresh/private tab or cleared site data fixed it). Because the portal's noVNC WebSocket (`/api/tools/portal/ws`) connects through Access, the Access identity reaches WebSocket upgrades (cookie or header; which of the two was not distinguished). Still NOT covered (needs a second Access identity): user B 404 on user A's data, user 403 on admin routes, rate limit at the edge, simultaneous browser sessions.

## Review history
### Round 1 - 2026-11-09
Verdict: Request changes (one Haiku reviewer; compose and docs diff). Resolution: fixed 6, rejected 2. Checks: `pytest tests` 66 passed, `docker compose config` ok, README 99 lines.
- R1-1 [MAJOR] README quick start fails on a fresh checkout (external `edge` network not created) - Fixed: README step 3 and security.md say to create it once (`docker network create "${EDGE_NETWORK:-my-ai-edge}"`); README stays within budget (an Optional-secrets comment block merged).
- R1-2 [MINOR] pitfall said task recovery runs a turn - Fixed (the worker runs the turn; recovery only logs under the owner).
- R1-3 [MINOR] unsupported "until every check is deployed, add only the admin" - Fixed (deleted).
- R1-4 [MINOR] CLI instruction did not say where to run it - Fixed (inside the app container with `docker compose exec app`).
- R1-5 [MINOR] APP_PASSWORD/HTTP Basic in docs/archive - Rejected: the archive is history (`docs/standards/docs.md`); the other HTTP Basic hits are the portal VNC credential.
- R1-6 [NIT] README budget wording ("under 100") vs the test (`<= 100`) - Rejected: pre-existing wording mismatch, the test is the rule.
- R1-7 [NIT] compose comment hard-coded the network name - Fixed.
- R1-8 [NIT] "ADMIN_EMAIL (the first user)" - Fixed ("seeded as the admin on every start").

## Log
- 2026-11-09: created (split from MYAI-32 Step 10)
- 2026-11-09: linked split_from MYAI-32 (Step 10)
- 2026-11-09: linked blocked_by MYAI-33
- 2026-11-09: linked blocked_by MYAI-34
- 2026-11-09: linked blocked_by MYAI-35
- 2026-11-09: linked blocked_by MYAI-36
- 2026-11-09: linked blocked_by MYAI-37
- 2026-11-09: linked blocked_by MYAI-38
- 2026-11-09: linked blocked_by MYAI-39
- 2026-11-09: linked blocked_by MYAI-40
- 2026-11-09: linked blocked_by MYAI-41
- 2026-11-09: plan validated, 2 rounds
- 2026-11-09 batch-autopilot: shipped https://github.com/archit342000/My-AI/pull/95, base feature/multi-user-frontend-gating. Step 3 only emulated locally; the ticket stays open until the real Access check is run.
- 2026-11-10: live Access check: login/chat pass; portal black (308 to http from the vnc defaults route, no ProxyFix); WebSocket check blocked; finding noted in Verification
- 2026-11-10: live-check findings triaged: portal fix PR #100; code execution diagnosed (runtime cleanup failure, fixed by #98 once deployed; React has no live-run socket); ticket stays open for the WebSocket header check
- 2026-11-10: deployed; code execution and browser portal confirmed working through Access; WebSocket upgrade works; multi-identity checks still open
