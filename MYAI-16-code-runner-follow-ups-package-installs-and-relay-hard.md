---
id: MYAI-16
title: "Code runner follow-up: restore package installs (after MYAI-1)"
status: done
created: 2026-11-09
updated: 2026-11-09
links:
  blocks: [MYAI-39]
  conflicts_with: [MYAI-4, MYAI-17]
  split_into: [MYAI-17]
---

## Description
Follow-up to MYAI-1 (PR #54, sandbox isolation). MYAI-1 moved sandboxed code to `code_runner_runtime` on an internal `runner-net` with no egress, behind a TCP relay `code_runner_mcp` (code_runner_mcp/relay.py) that forwards port 8100 only. Consequences and residuals left for this ticket:

1. **`/install` is broken.** The runtime has no egress, so package installs always fail (MYAI-1 R1-2). Restoring it must not reopen S1 (general internet or mysql_db reach).
   - Option A (preferred): an allowlisted package proxy (e.g. devpi or a pip/npm pull-through cache) on `runner-net`, with egress only to `pypi.org`, `files.pythonhosted.org` and `registry.npmjs.org`. The runtime uses it via `PIP_INDEX_URL` / `npm_config_registry`. The proxy holds no app secrets.
   - Option B (do first, cheap): bake common packages (numpy, pandas, requests, etc.) into the runner image so most runs never install.
2. **Relay hardening** (MYAI-1 residuals R2-6, R2-7, R4-8, R4-9). Moved to MYAI-17 on 2026-11-09 (user decision):
   - no connection cap or idle timeout on the relay;
   - relay runs the full runner image (toolchains) on secure-internal; use a slim pinned image (python:3.12-slim was not available locally to verify in MYAI-1);
   - duplicate build of the same image for runtime and relay in docker/docker-compose.yml;
   - relay healthcheck depends on the runtime being up.

Out of scope (accepted residual): the runtime API key remains readable by sandboxed code; with no egress it cannot leave the sandbox. Revisit only if egress is added beyond the package proxy.

PR #54 merged into develop 2026-11-09 (6a13e04); unblocked.

## Acceptance criteria
- [x] Common packages are preinstalled in the runner image and importable in a sandboxed run
- [x] `/install` succeeds for a PyPI package (and npm, if the runner supports npm) through the package proxy
- [x] Sandboxed code still cannot reach the internet, mysql_db:3306 or app:5000 (re-run MYAI-1 V2); the proxy only reaches the allowlisted registry hosts
- [x] The package proxy container holds no app secrets
- [x] Docs updated (docs/standards/docker.md, architecture/security docs, code_runner_mcp/README.md, install_packages tool description)

## Plan
**Date:** 2026-11-09  **Status:** Validated

### Objective
Restore `/install` (pip and npm) for the sandboxed code runner without reopening MYAI-1 S1 (sandbox reach to the internet, `mysql_db` or `app`), and bake common Python packages into the runner image so most runs never install. Relay hardening (Description item 2) is split out to a separate ticket (see Risks and open questions); this plan covers Description item 1 and the install-related acceptance criteria only.

### Context
- **Requirement:** Description item 1, options A and B. User direction 2026-11-09: allowlisted package proxy on `runner-net` with egress only to `pypi.org`, `files.pythonhosted.org`, `registry.npmjs.org`; bake common packages first; pick a concrete proxy and justify it; record what Docker networking can enforce.
- **Acceptance criteria covered here:** AC1 (preinstalled packages), AC2 (`/install` via proxy, pip and npm), AC3 (isolation re-check, proxy only reaches registry hosts), AC4 (proxy holds no app secrets), AC8 (docs, install part). AC5-AC7 (relay) go to the split ticket.
- **Assumptions:** (a) npm is supported (`server.py` `install_packages` handles `npm`; `nodejs npm` are in `docker/Dockerfile.code-runner`), so AC2 includes npm. (b) Only Python packages are baked; npm baking is not required by AC1. (c) No persistent package cache (a cache volume can be added later). (d) Host firewall changes are not applied by this work; an optional host rule is documented (open question 1). (e) Base image tags are pinned to the current stable tag verified at implement time (`docs/standards/dependencies.md`, `docs/standards/docker.md`).
- **Rules:** `docs/standards/docker.md` (pinned base, non-root, no extra capabilities, no secrets, healthcheck on any new service, resource limits for untrusted work, `--no-cache-dir`, manifests copied before source); `docs/standards/security.md` (sandbox network rules, line 14 and "Tools and sandboxing"); `docs/standards/dependencies.md` (pin exact versions, confirm in official docs); `docs/standards/coding.md` rule 9 (never modify existing containers; use uniquely named temporary ones); `docs/standards/testing.md` (suite commands, `scripts/check.sh` gate); `tests/test_docs.py` budgets (README <= 100 lines, docs <= 200; `README.md` is at 100 lines now, so edits there must not add lines); AGENTS.md rules 1-3.
- **Current behaviour (origin/develop 6a13e04):**
  - `docker/docker-compose.yml`: `code_runner_runtime` is only on `runner-net` (`internal: true`); relay `code_runner_mcp` is on `secure-internal` and `runner-net`.
  - `code_runner_mcp/server.py` `install_packages`: runs `pip install --user --no-cache-dir <pkgs>` or `npm install --no-save <pkgs>` (cwd `/home/runner`) with the container's environment inherited; always fails now (no egress, MYAI-1 R1-2).
  - `code_runner_mcp/executor.py` `prepare_sandbox`: user code gets a stripped env with `PYTHONPATH=/home/runner/.local/lib/python3.12/site-packages` and `NODE_PATH=/home/runner/node_modules`, so user-installed packages are importable; system site-packages (`/usr/local/lib/python3.12/site-packages`) are on the default path.
  - `docker/Dockerfile.code-runner`: `FROM python:3.12-slim`; copies all of `code_runner_mcp/` then installs `requirements.txt` (no sandbox packages).
  - `backend/tools/catalog/code.py` `INSTALL_PACKAGES.description` says installs are not available. `README.md:15` and `code_runner_mcp/README.md:21` say `/install` fails.
- **What Docker networking can enforce (recorded design facts):**
  1. `internal: true` on a bridge network: Docker installs no outbound route/NAT for it, so containers only on that network cannot reach the internet. This is what keeps `code_runner_runtime` offline.
  2. Separate user-defined bridges are isolated from each other (Docker's isolation chains); a container reaches only networks it is attached to. So a proxy on `runner-net` + a dedicated egress network cannot reach `secure-internal` services (`mysql_db`, `app`), and the runtime cannot use the egress network.
  3. Docker and Compose have no per-destination egress allowlist (no FQDN or IP policy key) for bridge networks. The supported hook for custom rules is the host `DOCKER-USER` iptables chain, which can match the egress bridge interface (fixed via `driver_opts: com.docker.network.bridge.name`) and restrict it to TCP 443 plus DNS (port 53). A hostname allowlist at IP level is not practical: `pypi.org`/`files.pythonhosted.org` (Fastly) and `registry.npmjs.org` (Cloudflare) sit on shared, changing CDN ranges, so an IP allowlist would be brittle and would still admit other sites on those CDNs.
  4. Therefore the host allowlist is enforced at the application layer by a proxy with no generic forwarding function (fixed upstreams only), on a network topology that Docker does enforce. The proxy container's own namespace has general egress; this residual is stated in the docs and narrowed by the optional host rule.

### Approach
- **Option B first:** bake a pinned set of common Python packages into the runner image system-wide (as root, before `USER runner`).
- **Option A: nginx reverse proxy (`nginxinc/nginx-unprivileged`, pinned alpine tag) as service `pkg-proxy`.** It joins `runner-net` (so the runtime can reach it) and a new non-internal bridge `pkg-egress` (its only route out). It is not on `secure-internal`, has no secrets, no volumes and a read-only root filesystem.
  - Fixed upstream locations only: `/pypi/simple/` -> `https://pypi.org/simple/`, `/pypi/files/` -> `https://files.pythonhosted.org/`, `/npm/` -> `https://registry.npmjs.org/`. Upstream TLS is verified (`proxy_ssl_verify on`, `proxy_ssl_server_name on`, `proxy_ssl_trusted_certificate /etc/ssl/certs/ca-certificates.crt`; nginx has no default CA store), upstream `Host` is fixed, client `Authorization`/`Cookie` headers are dropped.
  - Absolute upstream URLs in index and metadata responses are rewritten to the matching proxy location (`sub_filter`: `https://files.pythonhosted.org/` -> `http://pkg-proxy:8080/pypi/files/`, `https://registry.npmjs.org/` -> `http://pkg-proxy:8080/npm/`; `sub_filter_once off` so every URL in a page is rewritten, not only the first; upstream `Accept-Encoding` cleared, types include the PEP 691 JSON and HTML simple types and `application/json`), so pip and npm fetch files through the proxy. This does not depend on npm's `replace-registry-host` behaviour.
  - Only `GET`/`HEAD` (`limit_except`); a `default_server` returns 404 for any other path or `Host`; absolute-URI (forward-proxy style) requests and `CONNECT` are refused; registry locations live in a server block with `server_name pkg-proxy`, and `/healthz` is answered by every server block (including the default) so the local healthcheck works regardless of `Host`. DNS via Docker's embedded resolver (`127.0.0.11`) with variables so CDN IP changes are picked up.
  - Runtime uses it through environment on `code_runner_runtime`: `PIP_INDEX_URL=http://pkg-proxy:8080/pypi/simple/`, `PIP_TRUSTED_HOST=pkg-proxy`, `npm_config_registry=http://pkg-proxy:8080/npm/`, plus `npm_config_audit=false` and `npm_config_fund=false` (npm's audit is a `POST` the proxy refuses). `server.py` already passes the container env to pip/npm, so no runner code change is needed.
- **Rejected alternatives:** devpi-server + Verdaccio (two stateful services and images to maintain for one feature); Squid forward proxy with a `dstdomain` ACL (a generic forwarder: CONNECT tunnels and arbitrary methods/bodies to the allowed hosts, domain-fronting exposure on shared CDNs, and the allowlist is a config ACL on a component built to reach anywhere); giving the runtime egress with host iptables only (reopens S1; IP allowlists for CDNs are not workable, see fact 3); host `DOCKER-USER` rule as the primary control (host change outside the repo and compose; kept as optional defence in depth).
- **MYAI-4 overlap:** MYAI-4 adds package-name validation to `InstallRequest` and refuses an empty key in `server.py`. This plan does not touch `server.py`. Compatibility notes for MYAI-4: names must still allow version specifiers (`pkg==1.2`) and npm scoped names (`@scope/pkg`); rejecting URLs, paths and leading `-` complements the proxy (option injection such as `--index-url` cannot reach any other host anyway, since the runtime has no route except `runner-net`). Whichever lands second rebases; no shared lines expected beyond `code_runner_mcp/README.md`.

### Steps
#### Step 1: Bake common Python packages into the runner image
- **Files:** `code_runner_mcp/requirements-sandbox.txt` (create); `docker/Dockerfile.code-runner` (modify).
- **Change:** list exact-pinned (`==`) common packages: numpy, pandas, scipy, matplotlib, requests, sympy, beautifulsoup4, pyyaml, pillow, tabulate (selection procedure: take each package's latest stable release from its PyPI page on the implement date, per `docs/standards/coding.md` rule 8, that has a CPython 3.12 manylinux wheel and resolves together with `requirements.txt`; record the chosen versions in Implementation notes). In the Dockerfile, copy `code_runner_mcp/requirements.txt` and `requirements-sandbox.txt` first, run one `pip install --no-cache-dir -r requirements.txt -r requirements-sandbox.txt` as root, then copy the rest of `code_runner_mcp/` (manifest-first layering per `docs/standards/docker.md`).
- **Verification:** build with a unique tag; `docker run --rm --network none <tag> python3 -c "import numpy, pandas, scipy, matplotlib, requests, sympy, bs4, yaml, PIL, tabulate"` exits 0 as user `runner`.

#### Step 2: Add the package proxy image and config
- **Files:** `docker/pkg-proxy/nginx.conf` (create); `docker/Dockerfile.pkg-proxy` (create).
- **Change:** Dockerfile `FROM nginxinc/nginx-unprivileged:<X.Y.Z>-alpine` where X.Y.Z is the current stable nginx release from nginx.org on the implement date (exact patch tag, never `latest` or `stable`; record it in Implementation notes), built with the repo root as context (`context: ..`, as the existing services) and `COPY docker/pkg-proxy/nginx.conf /etc/nginx/nginx.conf` (replacing the base config, so the stock `conf.d/default.conf` is not loaded; no host mount), runs as the image's non-root user on port 8080; check the base for `/etc/ssl/certs/ca-certificates.crt` before writing the Dockerfile; if absent, `USER root`, `RUN apk add --no-cache ca-certificates`, then `USER 101` (the base image's non-root `nginx` user). Config implements the Approach bullets: three fixed upstream locations, TLS verification, fixed upstream `Host`, dropped auth/cookie headers, `sub_filter` rewrites to the location URLs given in Approach with `sub_filter_once off`, `GET`/`HEAD` only, 404 `default_server`, `/healthz`, embedded-DNS resolver, temp paths under `/tmp` so the root filesystem can be read-only.
- **Verification:** `docker build -f docker/Dockerfile.pkg-proxy -t <unique-tag> .` from the repo root succeeds (exercises the COPY path), then `docker run --rm <unique-tag> nginx -t` passes and `docker run --rm <unique-tag> ls /etc/ssl/certs/ca-certificates.crt` exits 0.

#### Step 3: Wire the proxy into compose
- **Files:** `docker/docker-compose.yml` (modify): new service `pkg-proxy`, new network `pkg-egress`, `code_runner_runtime.environment`.
- **Change:** `pkg-proxy` builds `docker/Dockerfile.pkg-proxy` with `context: ..`; networks `runner-net` and `pkg-egress` only; no `secrets:`, no `volumes:`; `read_only: true` with `tmpfs: /tmp`; `cap_drop: [ALL]`; `security_opt: [no-new-privileges:true]`; `deploy.resources.limits` (small memory/CPU); `healthcheck` on `/healthz` (busybox `wget`); `restart: unless-stopped`; comment stating its reach. `pkg-egress`: bridge, not internal, `driver_opts: com.docker.network.bridge.name: myai-pkg-egress`, comment that only `pkg-proxy` joins it. Add the index variables (including `npm_config_audit=false`, `npm_config_fund=false`) to `code_runner_runtime.environment`. Update the `runner-net` comment (relay and proxy join it). Do not change the relay service (split ticket).
- **Verification:** `docker compose -f docker/docker-compose.yml config --quiet` succeeds (with dummy secret files in a temporary copy if needed); rendered config shows `pkg-proxy` on exactly `runner-net` and `pkg-egress` and `code_runner_runtime` still only on `runner-net`.

#### Step 4: Update the install tool description
- **Files:** `backend/tools/catalog/code.py` (modify) `INSTALL_PACKAGES.description`.
- **Change:** replace the "Currently not available" sentence: installs go through an allowlisted package proxy (PyPI and npm registry only); common Python packages (list) are preinstalled, so check `list_packages` before installing.
- **Verification:** `EMBEDDING_URL="http://mock" AI_URL="http://mock" AI_API_KEY="dummy" PYTHONPATH=. venv/bin/python -m pytest backend/tools` passes.

#### Step 5: Update docs
- **Files (modify):** `docs/standards/docker.md` (Compose section: `pkg-proxy` and `pkg-egress` exception next to the `runner-net` note; add `pkg-proxy` (`/healthz`) to the healthcheck list); `docs/standards/security.md` (line 14 and "Tools and sandboxing": proxy topology, the four Docker-enforcement facts in short form, residual proxy egress, optional host rule, documented and not applied: in `DOCKER-USER`, for traffic in from `myai-pkg-egress`, accept TCP 443 and UDP/TCP 53 (the embedded resolver forwards queries from the container's namespace), drop the rest); `docs/architecture.md` "Tool isolation" (one sentence on `pkg-proxy`); `code_runner_mcp/README.md` (dependencies: baked packages and `requirements-sandbox.txt`; Network: `/install` goes through `pkg-proxy`, residual that user code can also fetch from the registries via the proxy); `README.md:15` (replace the "currently fails" clause without adding lines); `docs/pitfalls.md` (one entry under a new `## Docker and sandboxing` section placed before `## Known defects (not yet fixed)`, core lesson only: Docker cannot allowlist egress by host, so sandbox egress goes only through fixed-upstream proxies, never by putting the runtime on a non-internal network). The security.md text states plainly that the registry-only limit is enforced at the nginx layer and the host rule is the only network-level control on the proxy's egress.
- **Verification:** `PYTHONPATH=. venv/bin/python -m pytest tests` (docs guardrails: budgets and references) passes.

#### Step 6: Run the suites and the merge gate
- **Files:** none.
- **Change:** run `cd code_runner_mcp && PYTHONPATH=. ../venv/bin/python -m pytest`, the backend and docs suites (Step 4/5 commands), `venv/bin/ruff check .`, then `scripts/check.sh`.
- **Verification:** all pass with no regressions.

#### Step 7: Live isolation and install verification on a throwaway stack
- **Files:** evidence under `~/.claude/tickets/My-AI/MYAI-16-evidence/` (reusing `MYAI-1-evidence/scripts/verify_myai1_relay.sh` and `runner_probe_relay.py`); no repo files.
- **Change:** bring up a copy of the stack with a unique compose project name, dummy secrets and no clashing published ports (`docs/standards/coding.md` rule 9). Scenarios:
  - AC1: sandboxed run imports the baked packages.
  - AC2: `/install` via the relay succeeds for a small PyPI package (for example `six`) and an npm package (for example `is-number`), with `npm install` exiting 0 and no audit `POST` reaching the proxy (proxy access log); a following sandboxed run imports/requires each.
  - AC3: re-run MYAI-1 V1/V2 (sandbox cannot reach `example.com`, `1.1.1.1`, `mysql_db:3306`, `app:5000`; external DNS lookup from the sandbox fails); from the sandbox, requests to `pkg-proxy` with `Host: example.com`, an absolute URI `http://example.com/`, `CONNECT example.com:443`, a `POST`, and an unknown path all fail (404/405/400); `pkg-proxy` cannot reach `mysql_db:3306` or `app:5000`; `docker inspect` shows `pkg-proxy` networks are `runner-net` and `pkg-egress` only.
  - AC4: `pkg-proxy` has no `/run/secrets` and no secret-bearing environment variables.
  - Control: MYAI-1 V10 (app reaches internet, `mysql_db` and the relay) still passes. Remove the throwaway stack afterwards.
- **Verification:** every scenario PASS, results recorded in the ticket's Verification section with evidence links.

### Tests
- No Python source changes in `code_runner_mcp`, so no new unit tests there; its suite is re-run (Step 6). Backend tool catalog and docs guardrail suites cover Steps 4-5.
- The proxy config and compose topology are verified by `nginx -t`, `docker compose config` and the live scenarios in Step 7 (the repo has no compose-parsing test and no YAML library in `requirements*.txt`; adding one is out of scope).

### Risks and open questions
- **Split (size gate):** relay hardening is an independent area (relay code, a new slim relay image, compose de-duplication, healthcheck) and would push this plan past about 10 steps. Recommend a new ticket "Relay hardening after MYAI-1" covering: R2-6 connection cap and idle timeout in `code_runner_mcp/relay.py` with tests; R2-7 slim pinned relay image without toolchains (copy only `relay.py`); R4-8 duplicate build of `my-ai-code-runner` for `code_runner_runtime` and `code_runner_mcp`; R4-9 relay healthcheck that reflects the relay itself (for example a TCP self-check on its listener) instead of proxying `/health` to the runtime; plus AC5-AC7 and the relay part of AC8. Until then the relay keeps running `my-ai-code-runner`, which Step 1 makes larger (baked packages); the split ticket's slim relay image removes that. This ticket's AC5-AC7 should move there.
- **Open question 1 (non-blocking):** apply the optional host `DOCKER-USER` rule on the deployment host? It narrows the proxy container's egress to TCP 443 and DNS but needs root on the host and survives outside compose. Default: documented, not applied.
- **Residual:** sandboxed code can reach `pkg-proxy` directly, so it can download from the three registries (the same capability `/install` gives) and send GET request paths to them. Exfiltration through public download statistics is low-bandwidth and delayed; accepted, stated in docs. The MYAI-1 accepted residual (runtime API key readable by user code) stays acceptable because the only new path is GET-only to fixed registry hosts.
- **Risk:** `sub_filter` rewriting depends on registry response formats (absolute file/tarball URLs). Mitigation: Step 7 exercises real pip (JSON simple API) and npm installs; a format change shows up as a failed install, not an isolation break.
- **Risk:** pinned base tags may not be pullable from this host (MYAI-1 hit this with `python:3.12-slim`). Mitigation: verify the tag pulls before Step 2; if not, record and pick the nearest pinned tag that does.
- **Risk:** image size grows with baked packages (numpy, pandas, scipy, matplotlib). Accepted for fewer installs; list kept short.
- **Risk:** `pip install --user` packages persist in the runtime container's writable layer and are lost on recreate (existing behaviour; tool description already says so).

### Success criteria
- [ ] Baked packages import in a sandboxed run (AC1)
- [ ] `/install` succeeds for a PyPI package and an npm package through `pkg-proxy`, and the packages are importable afterwards (AC2)
- [ ] MYAI-1 V1/V2 re-run passes; proxy refuses non-registry hosts, `CONNECT`, absolute URIs and non-GET methods; proxy cannot reach `mysql_db` or `app` (AC3)
- [ ] `pkg-proxy` has no secrets (AC4)
- [ ] Docs, README and the `install_packages` description updated; Docker enforcement facts recorded in `docs/standards/security.md` (AC8, install part)
- [ ] Code runner, backend and docs suites, `ruff check .` and `scripts/check.sh` pass
- [x] Split ticket for relay hardening recommended to the user (AC5-AC7) (done: user approved, MYAI-17 created 2026-11-09)

### Amendment (2026-11-09): throwaway stack isolation
Found while validating MYAI-17. `docker/docker-compose.yml` uses fixed `container_name`s, published ports (2222, 5001), fixed `image:` tags (`my-ai-code-runner`) and host-absolute bind mounts to live data (`/home/archit-anand/docker-data/shared/My-AI-data`, `.../My-AI-playwright-data`). A copy started under a new project name would collide with the live stack, retag live images, and read and write live data. Any throwaway stack in this plan must follow MYAI-17 Step 7: copy to /tmp; in the copy, delete `container_name:` and `ports:`, prefix every `image:` with a unique verify name, and repoint host-absolute binds to empty /tmp directories; check with `grep -nE '/home/archit-anand|container_name|ports:|image: my-ai'` (no matches); start only the needed services with `--no-deps`; and clean up by image filter.

### Validation log
- **Round 1:** validator PASS, 7 MINOR. My judgement: pass; all 7 checked and valid, applied: (1) docs and Step 7 state that the registry-only limit is nginx-layer and the host rule is the only network-level control; (2) `server_name pkg-proxy` for registry locations and `/healthz` in every server block (busybox `wget` sends `Host: localhost`); (3) explicit version and tag selection procedure instead of bare placeholders (`docs/standards/coding.md` rule 8); (4) `context: ..` and a `docker build` verification that exercises the COPY; (5) npm audit is a `POST` the proxy refuses: `npm_config_audit=false`/`npm_config_fund=false` on the runtime and a Step 7 check; (6) `docs/pitfalls.md` entry (`docs/standards/review.md` item 6); (7) split note covers the relay image growing from baked packages (both services use `image: my-ai-code-runner`).
- **Round 2:** validator PASS, 10 MINOR (3 were "checked, no defect"). My judgement: pass; applied: `proxy_ssl_trusted_certificate` (nginx has no default CA store); COPY destination `/etc/nginx/nginx.conf`; CA bundle check plus `ls` verification; explicit `sub_filter` location mappings; host rule must allow DNS 53 (embedded resolver forwards from the container namespace); pitfalls entry trimmed to one core lesson (`docs/pitfalls.md` header: "Keep each entry to the core lesson"); docker.md healthcheck list names `pkg-proxy`.
- **Round 3:** validator FAIL, 1 BLOCKING, 2 MINOR. My judgement: the BLOCKING is valid (nginx `sub_filter_once` defaults to on, so only the first file URL per index page would be rewritten and AC2 would fail); fixed in Approach and Step 2. MINORs valid and applied: explicit `USER root` / `USER 101` for the conditional CA install; pitfalls section placed before `## Known defects (not yet fixed)` (`docs/pitfalls.md:47`).
- **Round 4:** validator PASS, 1 MINOR (unpinned `apk add ca-certificates`). My judgement: pass. MINOR disproved as a standards issue: `docs/standards/docker.md` pins base tags only, and the existing Dockerfiles install system packages unpinned (`docker/Dockerfile.code-runner` apt line). Accepted as is.

## Implementation notes

### Autopilot run (2026-11-09)
Batch 7 item. Branch bugfix/code-runner-package-proxy from origin/develop 2e81c08, PR base develop. Dirty files before start: none. The relay-hardening items (Description item 2) are MYAI-17 and not part of this change (AC5-AC7 moved there). Overlaps: docker-compose.yml, code_runner_mcp/README.md, docs/standards/security.md and docker.md with the open runner PRs.

### Baseline (2026-11-09)
At develop 2e81c08: `pytest backend tests` only the 10 async-plugin failures; runner tests (throwaway deps) 31 pass.

### Implementation progress
- [x] Step 1: `code_runner_mcp/requirements-sandbox.txt` (numpy 2.5.4, pandas 3.1.1, scipy 1.18.1, matplotlib 3.11.2, requests 2.34.2, sympy 1.14.0, beautifulsoup4 4.15.0, pyyaml 6.0.3, pillow 13.0.0, tabulate 0.10.0: the latest stable releases with a CPython 3.12 manylinux wheel on 2026-11-09, resolved together by the build); `Dockerfile.code-runner` copies the manifests first and installs both lists as root before `USER runner`
- [x] Step 2: `docker/Dockerfile.pkg-proxy` on `nginxinc/nginx-unprivileged:1.30.6-alpine` (the current stable nginx on nginx.org; it ships `/etc/ssl/certs/ca-certificates.crt`, so no apk step) and `docker/pkg-proxy/nginx.conf`: three fixed upstreams, TLS verification, fixed upstream Host, auth/cookie/accept-encoding stripped, `sub_filter` URL rewrites, GET/HEAD only, 404 default server, `/healthz`
- [x] Step 3: compose: service `pkg-proxy` (runner-net and pkg-egress only; read-only, tmpfs /tmp, cap_drop ALL, no-new-privileges, limits, healthcheck), network `pkg-egress` (fixed bridge name `myai-pkg-egress`), the pip/npm variables on `code_runner_runtime`; the relay is untouched
- [x] Step 4: `install_packages` tool description
- [x] Step 5: security.md (topology, what Docker enforces, residuals, the optional host rule), docker.md, architecture.md, code_runner_mcp/README.md, README.md (still 100 lines), pitfalls.md
- [x] Step 6: ruff clean; backend/tests/runner suites pass; scripts/check.sh not run as a whole (pytest-asyncio missing)
- [x] Step 7: throwaway stack (below)
Defect found by the live check and fixed: `proxy_set_header` at the http level is not inherited by locations that set their own, so `Accept-Encoding ""` (and the auth/cookie stripping) did not apply and gzip bodies bypassed `sub_filter` (pip then tried files.pythonhosted.org directly). Each location now repeats the four lines; noted in nginx.conf and pitfalls.md.

### Smoke test (2026-11-09)
`pytest backend tests` 1129 pass, only the 10 baseline failures; runner tests 32 pass + 1 skipped; docs guardrails pass; `nginx -t` ok; `docker compose config` ok; ruff clean.
None yet. MYAI-1 evidence scripts (~/.claude/tickets/My-AI/MYAI-1-evidence/scripts) can be reused for the isolation re-check.
Decision (user, 2026-11-09): split approved. Relay hardening criteria (connection cap and idle timeout, slim relay image and no duplicate build, the relay's own healthcheck) moved to MYAI-17.

PR: https://github.com/archit342000/My-AI/pull/82, branch bugfix/code-runner-package-proxy, base develop

## Verification
### Verification plan (2026-11-09, full form: sandbox network isolation)
A throwaway compose project (`myai16v`) following the plan's isolation amendment: generated from the real service definitions into /tmp (no container names, no published ports, images `myai16v-*`, dummy secret, no live mounts, `grep -nE '/home/archit-anand|container_name|ports:|image: my-ai'` empty), services started with `--no-deps`: `code_runner_runtime`, the relay, `pkg-proxy` and two stand-in listeners named `mysql_db` and `app` on `secure-internal`. Probes run from a helper container on `secure-internal` (the app's role) through the relay. Scripts in `scripts/`, the generated compose is saved as `throwaway-compose.yml`.
| ID | Criterion | Scenario | Expected |
|----|-----------|----------|----------|
| V1 | AC1 | baked packages: a sandboxed run imports them (and the image, offline, as user runner) | imports ok |
| V2 | AC2 | `/install` of `six==1.17.0` (pip) and `is-number@7.0.0` (npm) through the relay, then import/require in a sandboxed run | both install through the proxy and are usable |
| V3 | AC3 | from the sandbox: example.com, 1.1.1.1, mysql_db:3306, app:5000, DNS; proxy with Host example.com, an absolute URI, CONNECT, POST, unknown path; a registry GET | all blocked or refused (404/405/403); the registry GET works |
| V4 | AC4 | the proxy container: secrets, environment, mounts, networks, hardening | no /run/secrets, no secret-like env, no mounts, runner-net + pkg-egress only, read-only, caps dropped |
| V5 | AC3 | proxy reach: mysql_db and app from the proxy; POSTs in its log | unreachable; only the deliberate POST (403), no npm audit POST |
| V10 | control | from secure-internal: internet, mysql_db, relay health | still reachable |
Not run yet.

### Results (2026-11-09)
**Commit verified:** 2e81c08 (+ uncommitted). Hashes: requirements-sandbox.txt b2753618, Dockerfile.code-runner 517ecf2a, Dockerfile.pkg-proxy 32f0b666, nginx.conf 02b9a069, docker-compose.yml 9bdf3083, code.py 8283106f, security.md 4d008865, docker.md d505afb0, architecture.md e9cc9fbf, pitfalls.md e79ade63, README.md df9fc15e, README.md 8b16d50e.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | v1-baked.log (offline, user runner: numpy 2.5.4, pandas 3.1.1, scipy 1.18.1, matplotlib 3.11.2) and v1-v10.log (sandboxed run through the relay) |
| V2 | PASS | v1-v10.log: pip `Successfully installed six-1.17.0` and import ok; npm `added 1 package` and `require` ok. The first attempt failed for pip because of the header-inheritance defect above: v1-v10-attempt1-headers-not-inherited.log |
| V3 | PASS | v1-v10.log: sandbox connects to example.com, 1.1.1.1, mysql_db, app and DNS all fail; proxy answers 404 (other Host, absolute URI, unknown path), 405 (CONNECT), 403 (POST); the registry GET returns 200 |
| V4 | PASS | v4-v5.log: no /run/secrets, no secret-like variables, 0 mounts, networks `pkg-egress` and `runner-net`, read-only, caps dropped, healthy |
| V5 | PASS | v4-v5.log: `mysql_db` and `app` do not resolve from the proxy; the only POST in its log is the deliberate one (403); npm ran with audit off. Note: the proxy shares runner-net with the relay and runtime and can reach them (documented) |
| V10 | PASS | v1-v10.log: internet and mysql_db reachable from secure-internal, relay health ok |

Teardown: the project removed (`down -v`), images `myai16v-*` and the pulled nginx base removed, /tmp removed; containers, networks and images identical to the snapshots; the live stack untouched. **Verdict: verified (6/6 PASS).** Gaps: the optional host `DOCKER-USER` rule was not applied (documented only); the proxy's own egress is limited to the registries by its configuration, not by the network; the runner image grew from 1.81 GB to 2.27 GB.

### Results (re-run 1, 2026-11-09, after review fixes)
Re-run V1, V2, V3, V10 plus new V6 (registry redirect stays on the proxy) and V4/V5 hardening re-check on a fresh throwaway stack: all PASS (v1-v10 rerun log, v4-v5-rerun.log; redirect `/pypi/simple/Six/` -> 200 at `http://pkg-proxy:8080/pypi/simple/six/`). Proxy: networks pkg-egress + runner-net, read-only, caps dropped, 64m tmpfs /tmp, 256m, healthy, no secrets/env; the only POST in its log is the deliberate one. Teardown identical to snapshots. Verdict: verified (all PASS).

## Review history
### Round 1 - 2026-11-09
Haiku reviewer, uncommitted diff vs origin/develop 2e81c08. Verdict: Request changes (13 findings).
- R1-2, R1-4, R1-5, R1-7, R1-8, R1-9 - Fixed (header repeats, method limits, body/length stripping, redirect rewrite, proxy_ssl_name, buffering for files, docs)
- R1-1, R1-6, R1-11, R1-12, R1-13 - Rejected with evidence (not defects in this design)
- R1-3, R1-10 - Deferred to the batch follow-up ticket
Resolution: runtime config changed, so live verification was re-run (above): all PASS. Runner tests 32 pass + 1 skipped; `pytest backend tests` only the 10 baseline failures; ruff clean.

## Log
- 2026-11-09: created as follow-up to MYAI-1 (R1-2 /install break and relay residuals)
- 2026-11-09: plan validated, 4 rounds (install restoration only; relay hardening recommended as a separate ticket)
- 2026-11-09: split: relay hardening moved to MYAI-17.
- 2026-11-09: plan amended: throwaway stack isolation (see Plan > Amendment).
- 2026-11-09: linked split_into MYAI-17 (relay hardening split out 2026-11-09)
- 2026-11-09: linked conflicts_with MYAI-4 (install_packages tool description in backend/tools/catalog/code.py)
- 2026-11-09: linked conflicts_with MYAI-17 (adjacent code_runner_runtime and relay blocks in docker/docker-compose.yml)
- 2026-11-09: linked blocks MYAI-39
- 2026-11-09: autopilot started (batch-autopilot)
- 2026-11-09: implemented, smoke tests pass
- 2026-11-09: verified live, 6/6 PASS (one defect found and fixed during the run)
- 2026-11-09: reviewed (round 1, 13 findings: 6 fixed, 5 rejected, 2 deferred), re-verified 6/6 PASS
- 2026-11-09: PR #82 opened (batch-autopilot: shipped, base develop)
- 2026-11-09: closed (PR merged into develop)
