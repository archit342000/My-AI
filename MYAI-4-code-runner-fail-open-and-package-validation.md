---
id: MYAI-4
title: "S2 and S3: code runner fails open without a key and accepts raw package arguments"
status: done
created: 2026-11-08
updated: 2026-11-09
links:
  conflicts_with: [MYAI-16, MYAI-26, MYAI-27, MYAI-28]
---

## Description
Report S2 (Medium) and S3 (Medium), code_runner_mcp. S2: when no key is configured the auth check is skipped (code_runner_mcp/server.py:23-28, verify_api_key). S3: InstallRequest.packages is passed unvalidated to pip and npm, so option injection is possible (server.py:46-49). Suggested fix: refuse to start with an empty key, and validate package names (strict pattern, no leading -, no URLs or paths, count and length caps). Not blocked.

## Acceptance criteria
- [x] Startup refuses an empty key
- [x] Package names with a leading -, URLs or paths are rejected with 400
- [x] Valid package names are still installed

## Plan
**Date:** 2026-11-09  **Status:** Validated  **Base:** origin/develop 6a13e04

### Objective
Close two medium findings in the code runner service (`code_runner_mcp/server.py`, run as `code_runner_runtime` since MYAI-1): (S2) the API key check is skipped when no key is configured, on both HTTP routes and the `/ws/execute` WebSocket; (S3) `/install` passes `InstallRequest.packages` straight to `pip install` / `npm install`, so a caller can inject options (`--index-url ...`, `-r file`), URLs or local paths. After this change the service refuses to start without a key, and `/install` accepts only plain package names (with optional version or extras) and rejects everything else with 400.

### Context
- **Requirement:** ticket Description and Acceptance criteria above. Line numbers in the Description predate MYAI-1; current code re-checked at 6a13e04.
- **Assumptions (no user available):**
  - A1. "Valid package names are still installed" is verified as "valid names pass validation and reach the pip/npm subprocess with the expected argv". Real installs fail today because `code_runner_runtime` has no egress (accepted MYAI-1 residual R1-2); they return through the package proxy in MYAI-16.
  - A2. Allowed forms: pip `name`, `name[extra,...]`, `name<op>version` (ops `==`, `!=`, `<=`, `>=`, `~=`, `<`, `>`, one specifier only); npm `name`, `@scope/name`, each optionally `@<version-or-tag>`. Anything with `:` (URLs, `git+`, `file:`, `github:`), `/` outside an npm scope, leading `-`, leading `.` or `~`, whitespace, or `;` (pip environment markers) is rejected.
  - A3. Caps: at most 20 packages per request, each at most 100 characters (npm's own name limit is 214; 100 is ample for real names plus a version).
  - A4. The 400 body is FastAPI's `{"detail": "<short reason>"}`, naming the first rejected entry (`repr`, truncated to 50 characters). This matches the existing 400 for an unsupported manager in `install_packages`. Known gap: `docs/standards/api.md` asks for `{"error": ...}`, but it is written for the Flask app; the FastAPI runner already uses `detail`. The reason is the caller's own input, not internal detail. The backend turns it into an `Error:` message (Step 4).
- **Rules that apply:** `docs/standards/python.md` (applies to the MCP servers: docstrings with Args/Returns/Raises and type hints on new modules and public functions; config only through `backend/config.py`). This rule has no documented exception for MCP servers today, but the runner image does not ship `backend/` (and `playwright_mcp/server.py` already keeps its own `get_secret`). So `server.py` keeps its existing `os.environ` reads for `API_KEY_FILE` / `CODE_RUNNER_API_KEY` and adds no new variables, and Step 5 records the exception in `python.md` and `security.md`. This is a standards edit, so it needs owner sign-off (`docs/standards/docs.md`), flagged under Risks. `docs/standards/coding.md` (rule 9: never modify existing containers; build temporary ones with unique names). `docs/standards/security.md` (validate every request body, 400 for bad input; never log or return secrets), `docs/standards/api.md` ("Validate before acting, and fail with 400"; thin routes), `docs/standards/errors-and-logging.md` (no masked failures; tools return text starting `Error` so the agent can recover), `docs/standards/testing.md` (every module has `tests/test_<module>.py`; code_runner tests run as `cd code_runner_mcp && PYTHONPATH=. pytest`), `docs/pitfalls.md` (code_runner tests run from inside that directory), `docs/standards/docs.md` (README tables must list existing files; enforced by `tests/test_docs.py`), `AGENTS.md` (venv/bin/python, `ruff check .`, `scripts/check.sh`, keep README accurate).
- **Current behaviour:**
  - `code_runner_mcp/server.py` module level: reads `API_KEY` from `API_KEY_FILE` (read errors swallowed by `except Exception: pass`), falls back to env `CODE_RUNNER_API_KEY`, and continues with `API_KEY = ""` if both are empty.
  - `verify_api_key` only raises 401 `if API_KEY and x_api_key != API_KEY` (fail-open). `execute_ws` has the same `if expected_api_key and ...` guard.
  - `InstallRequest(packages: List[str], package_manager: str)` has no validators; `install_packages` builds `["pip", "install", "--user", "--no-cache-dir"] + pkgs` or `["npm", "install", "--no-save"] + pkgs` and runs it with `subprocess.run` (no shell).
  - The service is started by `CMD ["python", "server.py"]` in `docker/Dockerfile.code-runner`; compose gives `code_runner_runtime` `API_KEY_FILE=/run/secrets/CODE_RUNNER_API_KEY` (`docker/docker-compose.yml`). The relay service `code_runner_mcp` runs `relay.py` and never imports `server.py`, so it is unaffected.
  - Backend caller `install_packages` in `backend/tools/implementations/code_executor.py` calls `res.raise_for_status()` inside a broad `except`, so a 400 would be reported as "Code runner service is unavailable".
  - Tests: `code_runner_mcp/tests/test_server.py` sets `CODE_RUNNER_API_KEY=testkey` before `from server import app` and has no `/install` tests; `backend/tools/tests/test_code_executor.py::test_install_packages_approved` mocks `requests`.

### Approach
- **Fail closed at startup.** Replace the module-level key loading with a small function `load_api_key()` (new, in `server.py`). If `API_KEY_FILE` is set and the file exists, it reads the file; read errors on an existing file propagate instead of being swallowed. It strips the file value. If the result is empty, the file is absent or `API_KEY_FILE` is unset, it falls back to `CODE_RUNNER_API_KEY` (stripped), as today. If that is still empty, it raises `RuntimeError` with a message naming both variables but never a value. `API_KEY = load_api_key()` runs at module level, so `python server.py` (and any import) exits non-zero before uvicorn binds. Both auth checks become unconditional and use `hmac.compare_digest` (same lines being rewritten; constant-time compare is the standard way to compare a secret).
  - Rejected: checking in a FastAPI startup/lifespan hook (the module would still import with an empty key, and test clients that skip lifespan would run fail-open).
- **Allowlist package specs in a separate module.** New `code_runner_mcp/package_names.py` with `validate_packages(manager, packages) -> None` raising `ValueError` with a short reason, using the A2 patterns (full-match regexes, ASCII only) and A3 caps. `install_packages` normalises the manager, rejects an unsupported manager (existing 400), calls `validate_packages`, and converts `ValueError` to `HTTPException(400)` before building the command. A separate module keeps the route thin (`api.md`) and gives MYAI-16 one place to reuse when installs go through the proxy; the proxy changes only the index/registry the subprocess uses (`PIP_INDEX_URL`, `npm_config_registry`), not the accepted names.
  - Rejected: a Pydantic validator on `InstallRequest` (FastAPI returns 422 for those, but the criterion and `security.md` require 400; a custom exception handler would change 422 to 400 for every route).
  - Rejected: a denylist of dangerous options (incomplete by nature; the ticket asks for a strict pattern).
- **Backend surfaces the 400.** In the backend `install_packages`, when the runner answers 400, return `Error: Invalid package request: <detail>` instead of the "service unavailable" message, so the agent can correct the names. No backend pre-validation (one source of truth in the runner).

### Steps
#### Step 1: Fail closed when no API key is configured
- **Files:** `code_runner_mcp/server.py` (modify): add `import hmac`; module-level key loading replaced by new `load_api_key()`; `verify_api_key` (add `-> None` and a docstring); `execute_ws` (keep the existing `websocket: WebSocket, api_key: Optional[str] = None` signature; add only `-> None` and a docstring) with its key check at the top.
- **Change:** as in Approach. `load_api_key()` returns the stripped key or raises `RuntimeError`; module sets `API_KEY = load_api_key()`. `verify_api_key` raises 401 when `x_api_key is None` or `not hmac.compare_digest(x_api_key.encode("utf-8"), API_KEY.encode("utf-8"))` (the None check first and bytes on both sides, so a missing or non-ASCII header is a clean 401, not a `TypeError`); `execute_ws` closes with 1008 on the same condition. `load_api_key()` gets a docstring (Returns/Raises) and a `-> str` hint. Remove the swallowed `try/except` around the file read.
- **Verification:** Step 3 tests; `cd code_runner_mcp && PYTHONPATH=. ../venv/bin/python -c "import server"` with `CODE_RUNNER_API_KEY` and `API_KEY_FILE` unset exits non-zero with the `RuntimeError` message.

#### Step 2: Add package-name validation and use it in `/install`
- **Files:** `code_runner_mcp/package_names.py` (create): `validate_packages`, the pip and npm patterns, `MAX_PACKAGES`, `MAX_PACKAGE_LENGTH`. `code_runner_mcp/server.py` (modify): `install_packages`.
- **Change:** as in Approach. The module has a docstring, and `validate_packages(manager: str, packages: list[str]) -> None` has Args/Raises. The `ValueError` message is `Invalid package: <repr(entry)[:50]>` (or `Too many packages (max 20)` / `Package name too long (max 100)`), and `install_packages` passes it through unchanged as the 400 `detail` (A4). `install_packages` gets a `-> dict` hint and a docstring. Exact full-match patterns (`re.fullmatch`, `re.ASCII`):
  - pip: `[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?(?:\[[A-Za-z0-9._-]+(?:,[A-Za-z0-9._-]+)*\])?(?:(?:==|!=|<=|>=|~=|<|>)[A-Za-z0-9.*+!_-]+)?`. This allows `==1.*`, local `+` versions and `!` epochs. It rejects `,` outside extras, so there is one specifier only.
  - npm: `(?:@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*(?:@[A-Za-z0-9.^~<>=*+_-]+)?`. This allows `^`, `~`, `>=4`, `*` and dist-tags. It rejects `:`, `/` outside the scope, spaces and `||`.
  Both patterns make a leading `-`, `.`, `~` or `/` impossible. Validation runs after the empty-list early return and the manager check, and before the command is built, so no subprocess starts for a rejected request. Non-string items are already rejected by Pydantic (422); the validator also rejects empty strings.
- **Verification:** Step 3 tests.

#### Step 3: Tests for the runner
- **Files:** `code_runner_mcp/tests/test_package_names.py` (create); `code_runner_mcp/tests/test_server.py` (modify).
- **Change:**
  - `test_package_names.py`: accepted pip forms (`requests`, `numpy==1.26.4`, `pandas>=2.0`, `requests[socks]`, `zope.interface`); accepted npm forms (`lodash`, `lodash@4.17.21`, `@types/node`, `@babel/core@^7.0.0`, `left-pad@latest`); rejected: leading `-` (`--index-url=http://x`, `-r`, `-e .`), URLs (`https://x/y.whl`, `git+https://...`, `github:u/r`, `file:../x`), paths (`./pkg`, `../pkg`, `/tmp/p`, `~/p`, `u/r` for npm), whitespace, `;` markers, empty string, over-length entry, more than `MAX_PACKAGES` entries.
  - `test_server.py`: `load_api_key()` raises with no file and no env, reads the file when `API_KEY_FILE` points to one, and falls back to env when `API_KEY_FILE` is unset, points to a missing file or yields an empty value, and raises (no fallback) when `API_KEY_FILE` exists but can't be read (e.g. points to a directory). Use `tmp_path` and `monkeypatch.delenv(..., raising=False)` for both `CODE_RUNNER_API_KEY` and `API_KEY_FILE` first, because `test_server.py` sets the former at import time; importing `server` in a subprocess with both unset exits non-zero; `/install` with a rejected spec returns 400 and does not call `subprocess.run` (patch `server.subprocess.run`); `/install` with valid names for pip and npm returns 200 and `subprocess.run` receives the expected argv (A1), with `server.os.makedirs` also patched (the npm branch creates `/home/runner`, which doesn't exist on dev machines and would be written outside `tmp_path`); `/install` without a key still returns 401.
- **Verification:** `cd code_runner_mcp && PYTHONPATH=. ../venv/bin/python -m pytest -q` passes.

#### Step 4: Backend reports a rejected package request clearly
- **Files:** `backend/tools/implementations/code_executor.py` (modify): `install_packages`. `backend/tools/tests/test_code_executor.py` (modify).
- **Change:** before `raise_for_status()`, if `res.status_code == 400` return `Error: Invalid package request: <detail from JSON body>`. Other failures keep the current message. Add a test where the mocked response has `status_code = 400` and a `detail`; check the existing approved-install test still passes (set `status_code = 200` on its mock if needed).
- **Verification:** `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q backend/tools/tests/test_code_executor.py` passes (`docs/standards/testing.md`).

#### Step 5: Docs
- **Files:** `code_runner_mcp/README.md` (modify): Core Files row for `package_names.py`; Flow step 2 states the service refuses to start without a key; one line that `/install` accepts only plain names (rules in `package_names.py`). `backend/tools/catalog/code.py` (modify): `INSTALL_PACKAGES` `packages` item description says plain names with optional version only (no URLs, paths or options).
- **Change:** short edits only; keep the "installs currently fail, no outbound network" wording, which MYAI-16 will update. **Gated:** only if the owner's sign-off is recorded in this ticket's Implementation notes before Step 5 runs (`docs/standards/docs.md`: ask the owner before contradicting a documented rule), also add the exception from Context to `docs/standards/python.md` (config rule) and `docs/standards/security.md` (Secrets). Text: MCP services whose images don't ship `backend/` read their own secrets with a local helper in the same order (secret file, then env var) and never log or return them; `playwright_mcp` uses `get_secret` in its `server.py`, and `code_runner_mcp` uses `load_api_key`. Without sign-off, skip only these two edits; the code, README and catalog changes still go ahead.
- **Verification:** `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q tests/test_docs.py` passes (README table entries exist, length limits).

#### Step 6: Full checks
- **Files:** none.
- **Change:** run `venv/bin/ruff check .` and `scripts/check.sh`.
- **Verification:** both pass. Optional live check (verify stage), in a throwaway container built from the repo root with `docker build -f docker/Dockerfile.code-runner -t myai4-verify-runner .` (compose builds with context `..` from `docker/`; unique tag, never `my-ai-code-runner`, which the compose service uses) and a unique name, run with `--network none` so it matches the runtime's no-egress network (no change to the compose services, per coding.md rule 9): with no key it exits instead of serving; with a dummy key file mounted read-only and `API_KEY_FILE` pointing to it, `/install` with `--index-url=x` returns 400 and with `requests` reaches pip (fails on network, per A1). Start it detached (`docker run -d --name myai4-verify-runner --network none -v <keyfile>:/run/secrets/k:ro -e API_KEY_FILE=/run/secrets/k ...`), with the dummy key file world-readable (mode 0644), since the image runs as `runner`. With `--network none` the port can't be published, so send requests with `docker exec myai4-verify-runner python -c` and a `urllib.request` one-liner: `POST http://127.0.0.1:8100/install`, `Content-Type: application/json`, header `X-API-KEY: <dummy>`, body `{"packages": [...], "package_manager": "pip"}` (the image has no curl). Expected: `["--index-url=x"]` gives 400. `["requests"]` gives 200 with `success: false` and a network error in `stderr`, which shows it reached pip. Remove the container and image afterwards.

### Tests
- New: `code_runner_mcp/tests/test_package_names.py`. Updated: `code_runner_mcp/tests/test_server.py`, `backend/tools/tests/test_code_executor.py`.
- Commands: `cd code_runner_mcp && PYTHONPATH=. ../venv/bin/python -m pytest -q`; `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q backend/tools/tests/test_code_executor.py tests/test_docs.py`; `venv/bin/ruff check .`; `scripts/check.sh`.

### Risks and open questions
- **Deployments without the secret stop starting the runtime.** Intended (S2). Compose already mounts `secrets/CODE_RUNNER_API_KEY`; the app uses the same secret via `get_secret`. Mitigation: the error message names `API_KEY_FILE` / `CODE_RUNNER_API_KEY`. The commit message should call this out, since the changelog is generated from commits (`docs/standards/git.md`).
- **Pattern too strict for some real specs** (multiple specifiers like `>=1,<2`, environment markers, npm aliases `npm:`). Accepted: the agent can pin one version; widen later if needed. Deliberately excluded because `:` and `,` outside extras open URL and alias forms.
- **MYAI-16 compatibility:** the proxy will be configured with env vars on the runtime, not with request arguments, so the validator stays as is. If MYAI-16 adds an index option, it must come from config, never from the request.
- **Not in scope:** `/packages` swallows errors (`except Exception: pass`) and the runtime key is readable by sandboxed code (accepted MYAI-1 residual). Not touched here.
- **Standards edit needs sign-off:** Step 5 adds an MCP-server exception to the `python.md` config rule and the `security.md` secrets rule, in the same order (file, then env) as `playwright_mcp`'s local `get_secret` (`server.py:32-37`; it reads the fixed path `/run/secrets/<name>`, while `load_api_key` reads the configurable `API_KEY_FILE`); `code_runner_mcp` reads the file and env inline today and uses the same order through `load_api_key` after Step 1. If the owner declines, the code still works; only the docs edit is dropped and the conflict stays recorded here.
- No blocking open questions.

### Success criteria
- [ ] `import server` / `python server.py` exits non-zero when neither `API_KEY_FILE` nor `CODE_RUNNER_API_KEY` yields a key (test plus manual check).
- [ ] HTTP routes and `/ws/execute` always require the key.
- [ ] `/install` returns 400 for entries with a leading `-`, URLs or paths (and for over-cap requests) without running pip/npm.
- [ ] Valid pip and npm names pass validation and reach the pip/npm subprocess with the expected argv (A1). The subprocess is mocked in tests; no real install is verified while the runtime has no egress (MYAI-16).
- [ ] Backend `install_packages` returns an `Error: Invalid package request` message for a 400.
- [ ] README and tool description updated; code_runner tests, backend tests, `ruff check .` and `scripts/check.sh` pass.

### Validation log
- Attempt 0 (2026-11-09, planner): not run. Spawning the Haiku validator (Explore, model haiku) failed with "Concurrent subagent limit reached ... Do not retry", so no validation round took place. The plan was self-checked against origin/develop 6a13e04 only. Next step: run the plan skill's validation rounds on this Plan before implementing.
- Round 1 (2026-11-09, Haiku, run from the main session): FAIL, 2 BLOCKING and 8 MINOR. My judgement: FAIL is valid; I checked all 10 against the code and all were valid.
  - B1: npm test hits `os.makedirs("/home/runner")` (server.py:80-81). Fixed: patch `server.os.makedirs`.
  - B2: the live check modified an existing service (coding.md rule 9). Fixed: throwaway container.
  - M3: test commands lacked the testing.md env vars. Fixed.
  - M4: compare_digest with None or non-ASCII. Fixed: None check and bytes.
  - M5: python.md config rule. Recorded as an exception (no backend/ in the runner image).
  - M6: docstrings and type hints required. Added.
  - M7: no exact patterns. Regexes written into Step 2.
  - M8: `detail` vs api.md `error`. Gap acknowledged in A4.
  - M9: env isolation in tests. Added delenv.
  - M10: criterion now states the subprocess is mocked.
- Round 2 (2026-11-09, Haiku, diff-scoped): FAIL, 1 BLOCKING and 6 MINOR. My judgement: FAIL is valid. Round 1's BLOCKING items were confirmed resolved.
  - B1: the claimed "documented exception" does not exist (python.md:35, security.md:5). Valid. Context now says so; Step 5 records the exception in the standards, with owner sign-off flagged under Risks.
  - M2: no unique image tag (compose uses `my-ai-code-runner`) and no secret mount. Valid. Fixed.
  - M3: a throwaway container has egress. Valid. `--network none`.
  - M4: fallback semantics unclear. Valid. Kept today's fallback to env.
  - M5: hints and docstrings on the changed functions. Valid. Added.
  - M6: `import hmac`. Valid. Added.
  - M7: 400 detail format only in A4. Valid. Moved into Step 2.
- Round 3 (2026-11-09, Haiku, diff-scoped): FAIL, 1 BLOCKING and 5 MINOR. My judgement: FAIL is valid. Round 2's B1 was confirmed resolved.
  - B1: the Step 5 standards edits had no sign-off gate (docs.md). Valid. They now run only after the owner's sign-off is recorded; otherwise only they are skipped.
  - M2: `execute_ws` is already `websocket: WebSocket`. Valid (server.py:152). Wording fixed.
  - M3: garbled `load_api_key` sentence. Valid. Rewritten.
  - M4: no test for an unreadable existing key file. Valid. Added.
  - M5: the live check had no build context or request method. Valid. Fixed.
  - M6: "existing practice" was overstated for code_runner_mcp. Valid. Reworded.
- Round 4 (2026-11-09, Haiku, diff-scoped): FAIL, 1 BLOCKING and 3 MINOR. Round 3's B1 was confirmed resolved for the doc edits.
  - B1: Step 1's env reads contradict python.md:35 / security.md:5 without sign-off. Partly valid: the reads exist today (server.py:14-24) and the change adds no new variables, so it adds no new violation. Still, the plan states a rule conflict, so I asked the owner: approved 2026-11-09 (Implementation notes), which resolves B1 and satisfies the Step 5 gate. With no valid BLOCKING left after round 4, I mark the plan Validated.
  - M2: live-check request had no method, body or `X-API-KEY` header. Valid (server.py:26). Fixed.
  - M3: detached run, key-file permissions for `runner`, expected 200/success false. Valid. Fixed.
  - M4: citation range 32-39 should be 32-37, and "matching" was approximate. Valid. Fixed.

## Implementation notes

### Autopilot run (2026-11-09)
Batch 7 item. Branch bugfix/code-runner-fail-closed from origin/develop 2e81c08, PR base develop. Dirty files before start: none.

### Baseline (2026-11-09)
At develop 2e81c08: `pytest backend tests` only the 10 async-plugin failures. `code_runner_mcp/tests/test_server.py` cannot be collected in the main venv (no fastapi); the runner tests were run with `pip --target /tmp/gen/crdeps -r code_runner_mcp/requirements.txt httpx` (nothing added to the venv): 133 pass, 1 skipped.

### Implementation progress
- [x] Step 1: `load_api_key()` (file, else env, stripped; raises RuntimeError naming the variables, never a value; an unreadable key file propagates); `API_KEY` set at import so the service refuses to start; HTTP auth and `/ws/execute` unconditional via `_key_matches` (constant-time, a missing key never matches)
- [x] Step 2: code_runner_mcp/package_names.py (`validate_packages`, pip and npm patterns, caps 20 and 100) used by `/install` after the manager check: 400 with a short `detail`, nothing run
- [x] Step 3: tests: 73 package-name cases, key loading and fail-closed (including a subprocess import without a key), every route 401, WebSocket 1008, install 400/argv cases
- [x] Step 4: backend `install_packages` returns `Error: Invalid package request: <detail>` for a 400
- [x] Step 5 (partly): code_runner_mcp/README.md and the `install_packages` catalog description. **Skipped by the plan's own gate:** the exception to `docs/standards/python.md` and `docs/standards/security.md` (MCP services without `backend/` read their own secrets) needs the owner's sign-off, which is not recorded here; it goes to a follow-up ticket
- [x] Step 6: ruff clean; scripts/check.sh not run as a whole (pytest-asyncio missing)
Deviation: the plan builds an image; I ran the existing local runner image with the new code mounted read-only over `/app` (`--network none`, dummy key file, unique names), which tests the same server and avoids building or retagging.

### Smoke test (2026-11-09)
`code_runner_mcp` tests 133 pass + 1 skipped; `pytest backend tests` 1146+ pass, only the 10 baseline failures (8 in backend/tools); ruff clean; tests/test_docs.py pass.
Status on develop (checked at e327094, 2026-11-08): Still present on develop: fail-open check at server.py:26-28; InstallRequest has no validator at server.py:46.
Owner sign-off (user, 2026-11-09): approved recording an exception in docs/standards/python.md and security.md for MCP services whose images don't ship backend/ (local helper, secret file then env, never logged or returned). Step 5's gated edits go ahead.

PR: https://github.com/archit342000/My-AI/pull/77, branch bugfix/code-runner-fail-closed, base develop

## Verification
### Verification plan (2026-11-09, full form: auth and input validation on a sandbox service)
Throwaway containers from the existing local runner image with the new code mounted read-only over `/app`, `--network none`, a dummy world-readable key file, unique names, nothing rebuilt or retagged; probes run with `docker exec python`. Scripts in `scripts/`.
| ID | Criterion | Scenario | Expected |
|----|-----------|----------|----------|
| V1 | AC1 | start with no key, and with an empty key file | exits non-zero with the RuntimeError message |
| V2 | AC2 | `/install` with options, `-r`, URLs, paths, `github:`, `--registry`, 21 packages; no and wrong key | 400 with a short detail for every bad spec; 401 without or with a wrong key |
| V3 | AC3 | `/install` with `requests` (pip) and `lodash@4` (npm) | 200 and it reaches pip/npm (they fail only for lack of network) |
Not run yet.

### Results (2026-11-09)
**Commit verified:** 2e81c08 (+ uncommitted). Hashes: server.py b44e3ba1, package_names.py 60636c45, test_server.py 60b847c7, test_package_names.py e9595aff, code_executor.py 1b9cd684, test_code_executor.py 418e57a0, code.py 400e3c89, README.md d3ac2ab8.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | v1.log: container exit code 1 with no key and with an empty key file; the log names the variables, no value |
| V2 | PASS | v2-v3.log: 401, 401; 400 for the pip option, `-r`, URL, path, 21 packages and the npm option and `github:` spec, each with a short detail |
| V3 | PASS | v2-v3.log: 200 for pip `requests` ("No matching distribution found": no network) and npm `lodash@4` (npm error log), i.e. both reached the package manager |

Teardown: containers removed, /tmp dir removed, containers and images (same ids) identical to the snapshots, git status unchanged. **Verdict: verified (3/3 PASS).** Gap: no real install can be shown while the runtime has no egress (MYAI-16).

## Review history
### Round 1 - 2026-11-09
Verdict: Request changes (1 MAJOR). Scope: origin/develop 2e81c08..working tree, 8 files, single Haiku reviewer.
- R1-1 [MAJOR] the npm name pattern was lowercase only, so legacy packages with capitals (`JSONStream`, `@Scope/pkg`) were rejected - Static - Fixed (capitals allowed in names and scopes; tests; live: `JSONStream` reaches npm)
- R1-2 [MINOR] an existing but empty key file falls through to CODE_RUNNER_API_KEY - Static - Rejected: the validated plan specifies exactly this order (file, else env when empty or absent) and a test pins it; an empty file plus no env still refuses to start
- R1-3 [MINOR] the "too long" 400 does not name the entry - Static - Rejected: the plan's wording for that message; the rejected-spec message does name it
- R1-4 [MINOR] no version-URL forms in the bad list - Static - Fixed (`pkg@git+...`, `pkg@file:..`, `pkg@http://..`, scoped, pip equivalents)
- R1-5 [MINOR] one-version-specifier limit undocumented - Static - Fixed (catalog description and README)
- R1-6 [MINOR] empty list with an unsupported manager returns 200; duplicate manager check - Static - Rejected: the plan's order (empty-list early return first)
- R1-7 [MINOR] unreachable else branch - Static - Fixed (removed)
- R1-8 [MINOR] the user approves the raw specs before the runner validates them - Static - Not in the plan (it says no backend pre-validation): follow-up ticket
- R1-9 [MINOR] a 422 from the runner is reported as "service unavailable" - Static - Not in the plan (400 only): follow-up ticket
- R1-10 [MINOR] no positive control in the every-route-401 test - Static - Fixed (correct key is not a 401; comment on the bytes header)
- R1-11 [NIT] redundant `re.ASCII` - Static - Rejected: harmless and explicit
- R1-12 [NIT] test isolation (module-level env, process-wide subprocess patch) - Static - Rejected: pre-existing pattern, tests restore their patches
- R1-13 [NIT] the WebSocket key is a query parameter (logged by access logs) - Static - Pre-existing; tracked as its own ticket (key in the live-run WebSocket URL)
Resolution: fixed 5, rejected 5, to follow-up 2, pre-existing 1. Checks: runner tests 151 pass, `pytest backend tests` only baseline failures, ruff clean. Runtime change (validator, dead branch): live V2/V3 re-run in a throwaway container, all PASS (v2-v3-rerun.log).

## Log
- 2026-11-08: created from reports/full-scope-final-report-2026-11-08.md
- 2026-11-09: plan drafted, unresolved issues (Haiku validation not run: concurrent subagent limit)
- 2026-11-09: plan validated, 4 Haiku rounds (run from the main session); owner sign-off on the standards exception.
- 2026-11-09: linked conflicts_with MYAI-16 (install_packages tool description in backend/tools/catalog/code.py)
- 2026-11-09: linked conflicts_with MYAI-26 (install_packages in code_executor.py)
- 2026-11-09: linked conflicts_with MYAI-27 (MYAI-4 rewrites the execute_ws key check)
- 2026-11-09: linked conflicts_with MYAI-28 (ExecuteRequest and the execute_ws handler in code_runner_mcp/server.py)
- 2026-11-09: autopilot started (batch-autopilot)
- 2026-11-09: implemented, smoke tests pass; standards-doc exception skipped (needs owner sign-off)
- 2026-11-09: verified live, 3/3 PASS
- 2026-11-09: review round 1 Request changes (1 MAJOR fixed); fixed 5, rejected 5, 2 to follow-up; live re-run PASS
- 2026-11-09: shipped, PR https://github.com/archit342000/My-AI/pull/77
- 2026-11-09: batch-autopilot: shipped, base develop
- 2026-11-09: closed (PR merged into develop)
