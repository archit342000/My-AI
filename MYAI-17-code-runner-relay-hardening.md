---
id: MYAI-17
title: "Code runner relay hardening (after MYAI-1)"
status: done
created: 2026-11-09
updated: 2026-11-09
links:
  conflicts_with: [MYAI-16]
  relates_to: [MYAI-28]
  split_from: [MYAI-16]
---

## Description
Split from MYAI-16 on 2026-11-09. MYAI-1 (PR #54) put the sandboxed `code_runner_runtime` on the internal `runner-net` behind a TCP relay, `code_runner_mcp` (`code_runner_mcp/relay.py`), which joins `secure-internal` and forwards port 8100 only. Residuals from MYAI-1's review (R2-6, R2-7, R4-8, R4-9):
- the relay has no connection cap and no idle timeout;
- the relay runs the full runner image (toolchains) on `secure-internal`; it should use a slim pinned image (python:3.12-slim could not be verified locally in MYAI-1);
- `docker/docker-compose.yml` builds the same image twice (runtime and relay);
- the relay healthcheck depends on the runtime being up.

MYAI-16 bakes common packages into the runner image, which makes the relay's image larger until this ticket lands.

## Acceptance criteria
- [x] Relay enforces a connection cap and an idle timeout, with tests
- [x] Relay runs a slim pinned image without toolchains; no duplicate image build
- [x] Relay healthcheck reflects the relay's own health, not the runtime's
- [x] Sandbox isolation unchanged (re-run MYAI-1 V2 and V10)
- [x] Docs updated (docs/standards/docker.md, code_runner_mcp/README.md)

## Plan

**Date:** 2026-11-09  **Status:** Validated  **Base:** origin/develop 6a13e04

### Objective
Harden the TCP relay `code_runner_mcp` (`code_runner_mcp/relay.py`), which is the app's only route to the sandboxed `code_runner_runtime`:
- cap concurrent connections and drop idle ones;
- run it from its own slim image without the runner's toolchains;
- stop building the runner image twice;
- give it a healthcheck that reflects its own state rather than the runtime's.

### Context
- Requirement: Description and Acceptance criteria above (MYAI-1 residuals R2-6, R2-7, R4-8, R4-9).
- Current code (`code_runner_mcp/relay.py`):
  - `parse_target`, `pipe(reader, writer, abort_pair)`, `make_handler(target_host, target_port)` and `main()`.
  - Constants `LISTEN_PORT = 8100` and `CONNECT_TIMEOUT = 5`.
  - Stdlib only (asyncio, logging, os).
  - No limit on concurrent sessions and no idle timeout.
  - Tests: `code_runner_mcp/tests/test_relay.py` (round trip, half-close, abort, unreachable target, target ends session, `parse_target`, `main()`).
- Compose (`docker/docker-compose.yml`):
  - `code_runner_runtime` and `code_runner_mcp` both `build` `docker/Dockerfile.code-runner` with the same `image: my-ai-code-runner`.
  - The relay runs `command: ["python3", "/app/relay.py"]` on `secure-internal` and `runner-net`.
  - The relay's healthcheck is `GET http://localhost:8100/health`. That request is forwarded to the runtime, so the relay reports unhealthy whenever the runtime is down.
  - `depends_on: [code_runner_runtime]`.
- `docker/Dockerfile.code-runner`: `FROM python:3.12-slim` plus gcc/g++, JDK, Go, Rust, Node/npm, PHP and sqlite. It runs as `runner`. MYAI-16 will add baked Python packages, making it bigger still.
- `python:3.12-slim` is available locally (pulled 2026-11-09), so a slim relay image can be built and verified. (MYAI-1 couldn't verify one.)
- Timeouts that bound legitimate quiet periods:
  - The execution timeout comes from the `code_runner_timeout` setting (`backend/tools/implementations/code_executor.py:58, 251`), defaulting to `CODE_RUNNER_DEFAULT_TIMEOUT`. `CODE_RUNNER_MAX_TIMEOUT` (`backend/config.py:397`, 120 s) is defined but not read anywhere, and the runtime accepts any client timeout (`server.py:39, 173`). So no code enforces an upper bound today.
  - Installs run up to 120 s (`server.py`), and the backend waits 130 s.
  - The WebSocket `/ws/execute` streams output, but a silent program can be quiet until its own timeout.
- Rules:
  - `docs/standards/docker.md`: pin base tags; non-root user; healthcheck on changed services; `restart: unless-stopped`; no extra capabilities.
  - `docs/standards/coding.md` rule 9: throwaway containers with unique names for checks.
  - `docs/standards/python.md`: docstrings and type hints on new public functions; configuration only through `backend/config.py`. The relay already reads `RELAY_TARGET` from the environment, and the new limits are module constants, so no new environment reads are added.
  - `docs/standards/testing.md`: code_runner tests run from inside `code_runner_mcp`.
- Overlap: MYAI-16 changes `docker/Dockerfile.code-runner` and `code_runner_runtime` in compose (pkg-proxy, baked packages). This ticket changes only the relay service and adds a new Dockerfile, so the two touch different compose blocks. Ship one first and rebase the other.

### Approach
- **Connection cap.** Add `MAX_CONNECTIONS = 64` as a module constant. `make_handler` gains an optional `max_connections` parameter (defaulting to the constant, so tests can lower it) and keeps a per-handler counter. A connection over the cap is closed immediately, with one `logger.warning`, and no upstream connection is opened. Rejecting rather than queuing keeps memory bounded.
- **Idle timeout.** Add `IDLE_TIMEOUT = 600` (seconds), well above the 130 s longest legitimate silence. `make_handler` gains an optional `idle_timeout` parameter, so tests can use a fraction of a second.
  - Each session records a last-activity time that `pipe` updates on every read in either direction.
  - A watchdog task per session aborts both transports once nothing has moved for `idle_timeout`, logging at warning level.
  - The watchdog is cancelled when the session ends.
- **Own health endpoint.** `main()` also starts a second asyncio server on `127.0.0.1:8101` (`HEALTH_PORT`). It answers any connection with `HTTP/1.0 200 OK` and the body `ok`, then closes, without touching the target. The compose healthcheck uses `urllib` against `http://localhost:8101/`. Because it binds to loopback, it isn't reachable from other containers.
- **Slim image, single build.** Add `docker/Dockerfile.relay`:
  - `FROM python:3.12-slim` (same pinned tag as the runner).
  - Create a non-root `relay` user.
  - `COPY code_runner_mcp/relay.py /app/relay.py` only; no pip install (stdlib only).
  - `USER relay`, `EXPOSE 8100`, `CMD ["python3", "/app/relay.py"]`.
  - The relay service builds it as `image: my-ai-code-runner-relay`, so `my-ai-code-runner` is built only once, by `code_runner_runtime`. Keep `depends_on` for start order only.
- Rejected alternatives:
  - TCP connect to 8100 as the healthcheck: each probe opens an upstream connection and logs a warning while the runtime is down.
  - Environment-configurable limits: new env reads would conflict with `python.md`, and constants are enough.
  - `socat`/`haproxy` in place of relay.py: a new dependency, and it would lose the tested half-close behaviour.

### Steps
#### Step 1: Connection cap and idle timeout in the relay
- **Files:** `code_runner_mcp/relay.py` (modify). Add the import `from collections.abc import Awaitable, Callable`. The last-activity clock uses `asyncio.get_running_loop().time()`, so no `time` import is needed.
  - New constants `MAX_CONNECTIONS` and `IDLE_TIMEOUT`.
  - `make_handler(target_host: str, target_port: int, max_connections: int = MAX_CONNECTIONS, idle_timeout: float = IDLE_TIMEOUT) -> Callable[[asyncio.StreamReader, asyncio.StreamWriter], Awaitable[None]]`.
  - `pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, abort_pair: tuple[asyncio.StreamWriter, ...], on_activity: Callable[[], None]) -> None`.
  - A new private watchdog coroutine.
- **Change:** as in Approach.
  - Restructure `handle` so the whole body after the cap check sits in one `try/finally`, including the unreachable-target early return (today it returns before the `try` at relay.py:47-50).
  - Check the cap, then increment immediately, with no `await` between the two.
  - The upstream connection, `pair` and the watchdog are created only after a successful connect. On the unreachable path, close `client_writer` only. Initialise `upstream_writer = None` and `watchdog = None` before the `try`; in the `finally`, decrement the counter, then cancel the watchdog if it exists and collect it with `await asyncio.gather(watchdog, return_exceptions=True)` (this neither raises the watchdog's `CancelledError` or other errors, nor hides a cancellation of the handler itself). Put the writer closes in their own inner `finally`, so they run whatever happens, then close and await `client_writer` and, if set, `upstream_writer` (the existing close logic, guarded).
  - This releases the slot on every path (unreachable target, error, normal end), and the watchdog can't outlive the session.
  - Docstrings and type hints on the changed public functions (`pipe`, `make_handler`).
  - Existing behaviour (half-close, abort on error, end on target reply) is unchanged.
- **Verification:** the existing `test_relay.py` tests still pass; new tests in Step 3.

#### Step 2: Relay health server
- **Files:** `code_runner_mcp/relay.py` (modify): new constant `HEALTH_PORT = 8101`, new `handle_health` coroutine, `main()`.
- **Change:** `main()` starts both servers (8100 on `0.0.0.0`, 8101 on `127.0.0.1`) and serves both until cancelled. `handle_health` reads up to the end of the request headers with a short timeout, writes the 200 response and closes. Docstrings and type hints on `handle_health` (new) and `main()` (changed), per `python.md`.
- **Verification:** Step 3 tests.

#### Step 3: Tests
- **Files:** `code_runner_mcp/tests/test_relay.py` (modify). Use the existing `_free_port` and asyncio patterns.
- **Change:** add tests for:
  - With `max_connections=1`, a second concurrent client is closed (EOF) while the first still works.
  - After the first client finishes, a new client is accepted again (the counter is released).
  - With `idle_timeout=0.2`, a session where neither side sends is closed within about 1 s.
  - A session with steady traffic below the timeout is not closed.
  - `handle_health` returns `200` and `ok` with no target running.
  - `main()` starts both listeners. Change the existing `main()` test's `fake_start_server` (test_relay.py:152-161) to append each call to a list instead of `calls.update`, and assert one call on `0.0.0.0:8100` with the relay handler and one on `127.0.0.1:8101` with `handle_health`.
  - The slot is released after an unreachable target: take a free port with `_free_port()` and build the handler with `max_connections=1` targeting it while nothing listens. A first client is closed (EOF). Then start an echo server on that same port; a second client through the same relay gets its echo back.
- **Verification:** `cd code_runner_mcp && PYTHONPATH=. ../venv/bin/python -m pytest -q` passes.

#### Step 4: Slim relay image
- **Files:** `docker/Dockerfile.relay` (create).
- **Change:** as in Approach.
- **Verification:** `docker build -f docker/Dockerfile.relay -t myai17-verify-relay .` from the repo root succeeds. `docker run --rm myai17-verify-relay sh -c 'which gcc go rustc node php java || true'` prints nothing (the empty output is the check; `|| true` makes the exit code meaningless), and `docker run --rm myai17-verify-relay id -un` prints `relay`. Remove the image afterwards.

#### Step 5: Compose
- **Files:** `docker/docker-compose.yml` (modify): service `code_runner_mcp` only.
- **Change:**
  - `build.dockerfile: docker/Dockerfile.relay` and `image: my-ai-code-runner-relay`.
  - Drop `command:` (the image's CMD runs the relay).
  - Healthcheck `test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8101/', timeout=3)"]`, keeping interval 30s, timeout 5s and retries 3, and adding `start_period: 10s`.
  - Keep the networks, `RELAY_TARGET`, `depends_on` and `restart`. Update the two comment lines above the service.
- **Verification:** `docker compose -f docker/docker-compose.yml config --quiet` succeeds (with dummy secret files in a temporary copy if the real ones are absent). The rendered config shows the relay with `my-ai-code-runner-relay` and the runtime alone with `my-ai-code-runner`.

#### Step 6: Docs
- **Files:**
  - `docs/standards/docker.md` (modify): the Health checks line says the relay checks its own loopback health port 8101; the Images section names `Dockerfile.relay` as the slim relay image.
  - `code_runner_mcp/README.md` (modify): the `relay.py` row and the Network bullet mention the connection cap, idle timeout, health port and separate image.
  - `docs/architecture.md`: only if it describes the relay image (it currently names the relay service only; no change expected).
- **Verification:** `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q tests/test_docs.py` passes.

#### Step 7: Live check and full gate
- **Files:** evidence under `~/.claude/tickets/My-AI/MYAI-17-evidence/` (reuse `MYAI-1-evidence/scripts/`); no repo files.
- **Change:** run `venv/bin/ruff check .` and `scripts/check.sh`. Then bring up a throwaway stack, as MYAI-1 did:
  - Copy the worktree to `/tmp/myai17-verify` and put dummy secret files in the copy's `secrets/`.
  - In the copy's `docker/docker-compose.yml`:
    - Delete every `container_name:` and `ports:` entry, so nothing collides with the live stack (bastion_ssh, tavily_mcp, playwright_mcp and inference-proxy fix names; 2222 and 5001 are published).
    - Rename every `image:` to a `myai17-verify-` prefix (`my-ai-code-runner` -> `myai17-verify-code-runner`, `my-ai-code-runner-relay` -> `myai17-verify-relay`), so the live image tags are never retagged.
    - Repoint every host-absolute bind mount (`/home/archit-anand/docker-data/shared/...`, for example the app's data dir and playwright data) to empty directories under `/tmp/myai17-verify-data/`, so the live data is never read or written.
    - Confirm the edited file with `grep -nE '/home/archit-anand|container_name|ports:|image: my-ai' docker-compose.yml`, which should show no matches.
  - From `docker/`, run `docker compose -p myai17-verify up -d --build --no-deps app code_runner_runtime code_runner_mcp mysql_db`. The live stack is never touched (coding.md rule 9).
  - Run `MYAI-1-evidence/scripts/verify_myai1_relay.sh myai17-verify <dummy key>` for the MYAI-1 checks.
  Checks:
  - L1: the relay is healthy.
  - L2: after `docker compose -p myai17-verify stop code_runner_runtime`, the relay stays healthy and app calls fail cleanly. While the runtime is stopped, open 70 TCP connections (more than `MAX_CONNECTIONS`) to the relay from the app container: `docker exec myai17-verify-app-1 python -c "import socket; [socket.create_connection(('code_runner_mcp', 8100), 3).close() for _ in range(70)]"`. The relay accepts each one, fails to reach the runtime and closes it. The connections are sequential, so this doesn't test the cap (the Step 3 unit test does); it checks that failed connects don't leak slots, since 70 leaks would exceed 64 and block the later call. Then `docker compose -p myai17-verify start code_runner_runtime`, wait for it to be healthy, and check that an app call succeeds, which shows no slot leaked. The unit test in Step 3 covers this exactly; L2 checks it end to end.
  - L3: MYAI-1 V2 (the sandbox can't reach the internet, `mysql_db` or `app`) and V10 (the app reaches the runner over HTTP and WebSocket) still pass.
  - L4: the relay container has no compilers.
  Afterwards run `docker compose -p myai17-verify down -v`, `docker images --filter 'reference=myai17-verify*' -q | xargs -r docker rmi` (covers the renamed and the project-named images) for the images compose names after the project, and remove `/tmp/myai17-verify` and `/tmp/myai17-verify-data`.
  Tear the stack down afterwards.
- **Verification:** all checks pass; results go in Verification.

### Tests
- `cd code_runner_mcp && PYTHONPATH=. ../venv/bin/python -m pytest -q`
- `EMBEDDING_URL=http://mock AI_URL=http://mock AI_API_KEY=dummy PYTHONPATH=. venv/bin/python -m pytest -q tests/test_docs.py`
- `venv/bin/ruff check .`, then `scripts/check.sh`
- Live checks L1-L4 (Step 7)

### Risks and open questions
- **Idle timeout vs. long silent runs.** 600 s covers the default execution timeout and the 130 s install wait, but the margin depends on the `code_runner_timeout` setting, which no code caps (`CODE_RUNNER_MAX_TIMEOUT` is unused). If the setting is raised above about 590 s, long silent runs would be cut. Mitigation: a comment beside `IDLE_TIMEOUT` naming the dependency. Enforcing `CODE_RUNNER_MAX_TIMEOUT` is out of scope (possible follow-up).
- **Cap of 64.** This is far above a single-user app's needs. Over-cap clients see a dropped connection, which the backend already reports as runner unavailable.
- **Merge order with MYAI-16** (different compose blocks; see Context).
- **The health port only shows that the relay process is serving.** Runtime health is still covered by the runtime's own healthcheck.
- No blocking open questions.

### Success criteria
- [ ] The relay rejects connections over the cap and closes idle sessions, with tests
- [ ] The relay image has no toolchains, runs as non-root, and is built separately; `my-ai-code-runner` is built once
- [ ] The relay healthcheck stays healthy when the runtime is down
- [ ] MYAI-1 isolation checks still pass
- [ ] Docs updated; tests, ruff and `scripts/check.sh` pass

### Validation log
- Round 1 (2026-11-09, Haiku): FAIL, 1 BLOCKING and 7 MINOR. My judgement: FAIL is valid; I checked all 8 against the code.
  - B1: a slot leaks when the target is unreachable (early return before the try at relay.py:47-50). Valid. Restructured with one try/finally and a test.
  - M2: `CODE_RUNNER_MAX_TIMEOUT` is unused, so no code caps the timeout. Valid (grep). Context and Risks corrected.
  - M3: the existing `main()` test would break with two `start_server` calls (test_relay.py:152-161). Valid. The test change is now specified.
  - M4: docstrings for `handle_health` and `main`. Valid. Added.
  - M5: a throwaway stack collides with the live one (fixed `container_name`s, published ports). Valid. Steps now spelled out (tmp copy, strip names and ports, `--no-deps`).
  - M6: V2 name clash with MYAI-1. Valid. Renamed to L1-L4.
  - M7: where the watchdog is cancelled. Valid. In the same finally.
  - M8: the `which` check relies on output. Valid. Clarified.
- Round 2 (2026-11-09, Haiku, diff-scoped): FAIL, 3 BLOCKING and 4 MINOR. My judgement: FAIL is valid; I checked all 7. Round 1's B1 was confirmed resolved in the design.
  - B1: the slot-release test can't reach a live target through a fixed-target handler. Valid. Now uses the same free port, with the listener started after the first failure.
  - B2: the copy kept live `image:` tags, and `--rmi local` doesn't remove custom tags. Valid. Images renamed with a `myai17-verify-` prefix and removed by name.
  - B3: the copy would mount live host data paths. Valid (compose bind to `/home/archit-anand/docker-data/shared/...`). Repointed to /tmp, with a grep check.
  - M4: the finally referenced `pair` and the watchdog on the unreachable path. Valid. Guarded, with None initialisation.
  - M5: L2 couldn't show a leak with a cap of 64. Valid. 70 calls, then exact restart commands.
  - M6: incomplete type hints. Valid. Full signatures given.
  - M7: no `id -un` command. Valid. Added.
- Round 3 (2026-11-09, Haiku, diff-scoped): FAIL, 1 BLOCKING and 3 MINOR. My judgement: FAIL is valid. Round 2's three BLOCKING items were confirmed resolved.
  - B1: awaiting the cancelled watchdog raises `CancelledError` and skips the writer closes. Valid (asyncio semantics). Now wrapped in `contextlib.suppress`.
  - M2: `Callable` and `Awaitable` imports missing. Valid (relay.py:6-8). Added.
  - M3: no exact command for the 70 calls. Valid. Given.
  - M4: image cleanup not enumerated. Valid. Filter-based removal added.
- Round 4 (2026-11-09, Haiku, diff-scoped): PASS, 4 MINOR. My judgement: PASS; round 3's B1 was confirmed resolved. Stop rule met (no valid BLOCKING after round 3).
  - M1: suppress covers only cancellation and hides an outer cancel. Valid. Replaced with `gather(return_exceptions=True)` and an inner finally for the closes.
  - M2: clock not named. Valid. `loop.time()`.
  - M3: sequential calls don't test the cap. Valid. Purpose reworded (leak check).
  - M4: redundant `rmi`. Valid. Single filter sweep.

## Implementation notes
Prior context: MYAI-1 Review history (residuals) and MYAI-16 Plan (compose changes for pkg-proxy).

### Autopilot run (2026-11-09)
Batch 7 item. Branch bugfix/code-runner-relay-hardening from origin/develop 2e81c08, PR base develop. Dirty files before start: none. MYAI-16 (PR #82) edits adjacent compose blocks and the same READMEs/docs: expect textual conflicts there.

### Baseline (2026-11-09)
At develop 2e81c08: `pytest backend tests` only the 10 async-plugin failures; runner tests (throwaway deps /tmp/gen/crdeps) 32 pass + 1 skipped.

### Implementation progress
- [x] Step 1: relay.py: `MAX_CONNECTIONS=64`, `IDLE_TIMEOUT=600`, `make_handler(..., max_connections, idle_timeout)`, `pipe(..., on_activity)`, `_watch_idle`; one try/finally releases the slot on every path
- [x] Step 2: `HEALTH_PORT=8101`, `handle_health`, `main()` serves both (health on 127.0.0.1)
- [x] Step 3: tests: cap + slot freed, unreachable-target slot freed, idle close, steady traffic kept, health, main() with two listeners (runner suite 37 pass + 1 skipped)
- [x] Step 4: `docker/Dockerfile.relay` (python:3.12-slim, user relay, only relay.py): image 120 MB vs 1.81 GB, no gcc/go/rustc/node/php/java
- [x] Step 5: compose relay: own Dockerfile and image `my-ai-code-runner-relay`, no command, healthcheck on 127.0.0.1:8101 with start_period 10s
- [x] Step 6: docs/standards/docker.md (images, health checks), code_runner_mcp/README.md
- [x] Step 7: live check (Verification)
Mutation check: removing the cap check fails the cap test; removing the slot release or the idle check makes the suite hang until killed (fails without the fix).

### Smoke test (2026-11-09)
Runner tests 37 pass + 1 skipped; `pytest tests` 32 pass; ruff clean; docker.md/README edits covered by docs guardrails.

PR: https://github.com/archit342000/My-AI/pull/83, branch bugfix/code-runner-relay-hardening, base develop

## Verification
### Verification plan (2026-11-09)
Throwaway compose project `myai17v` (no container names or published ports, no live mounts, runtime on the existing local image, relay built from Dockerfile.relay as `myai17v-relay`, stand-ins `mysql_db` and `app` on secure-internal; networks named `x_*`). Scripts in `MYAI-17-evidence/scripts/`, compose saved as `throwaway-compose.yml`. L1 relay healthy and the health port is loopback only; L2 runtime stopped: relay stays healthy, 70 failed connects leak no slot, recovery works; live cap: 70 held connections; L3 MYAI-1 V2/V10 (sandbox egress blocked, app reaches runner over HTTP and WebSocket); L4 relay image has no toolchains and runs as non-root. Idle timeout is covered by unit test only (600 s is not practical live).

### Results (2026-11-09)
**Commit verified:** 2e81c08 (+ uncommitted). Hashes: relay.py adf409a2, test_relay.py eb630665, Dockerfile.relay 8116aef1, docker-compose.yml 173e3c0a, docker.md d5213350, code_runner_mcp/README.md f3956f08.

| ID | Status | Evidence |
|----|--------|----------|
| L1 | PASS | l1-l4-l3.log: relay healthy; 8101 answers 200 `ok` inside the relay; from the app network 8100 reachable, 8101 refused |
| L2 | PASS | l2.log, l2b.log: runtime stopped, relay stays healthy after more than one interval and 8101 answers; 70 sequential connects all closed by the relay (no leak); after restart an app call returns 200 |
| L-cap | PASS | l1-l4-l3.log: 70 held connections: 64 stayed open, 6 closed by the relay (6 warnings in its log); a call works afterwards |
| L3 | PASS | l1-l4-l3.log: sandbox example.com, 1.1.1.1, mysql_db, app all BLOCKED; app HTTP and WebSocket runs OK |
| L4 | PASS | l1-l4-l3.log: no gcc/go/rustc/node/php/java in the relay, user `relay`, image 120 MB (runner image 1.81 GB, built once) |

Teardown: project removed (`down -v`), `myai17v-relay` removed, /tmp removed; containers, networks and images identical to the snapshots; live stack untouched. **Verdict: verified (5/5 PASS).** Gaps: idle timeout not exercised live (unit test only); the compose `start_period` was not timed.

### Results (re-run 1, 2026-11-09, after review fixes)
Fresh throwaway stack: relay healthy; 70 held connections 64 open / 6 closed; sandbox egress blocked; HTTP and WebSocket OK; runtime stopped: relay healthy and 70 connects closed with no leak; recovery call 200 (rerun1.log). Teardown identical to snapshots. Verdict: verified (all PASS).

## Review history
### Round 1 - 2026-11-09
Haiku, uncommitted diff vs origin/develop. Verdict: Request changes (2 MAJOR).
- R1-1 [MAJOR] relay.py IDLE_TIMEOUT precondition not enforced - Fixed: comment states that a larger code_runner_timeout ends a silent run at 600 s; README residual-reach sentence states it. Enforcing the cap is out of plan scope (the max-timeout change handles it).
- R1-2 [MAJOR] finally could block forever in wait_closed and release the slot early - Fixed: bounded `wait_closed` (CLOSE_TIMEOUT 5 s, then abort), slot released last. No dedicated test (a stuck flush is not reproducible deterministically); covered by the existing close paths.
- R1-3 [MINOR] pipe tasks orphaned on handler cancellation - Fixed: tasks cancelled and gathered in the finally.
- R1-4 [MINOR] sleeps in tests - Fixed: polling helper, wider idle margin (3 runs stable).
- R1-5 [MINOR] no slot-release test for the idle abort - Fixed: new test.
- R1-6 [MINOR] README misses the cap as an availability risk - Fixed.
- R1-7 [NIT] long signature - Fixed (Handler alias).
- R1-8 [NIT] one-element list cell - Rejected: simple and clear.
- R1-9 [NIT] coding.md rule 9 vs compose change - Rejected: rule 9 forbids touching live containers during testing, not editing the compose source.
Resolution: 7 fixed, 2 rejected. Runner tests 38 pass + 1 skipped x3 runs; ruff clean; live re-run PASS.

## Log
- 2026-11-09: created, split from MYAI-16 (relay hardening criteria)
- 2026-11-09: plan validated, 4 Haiku rounds.
- 2026-11-09: linked split_from MYAI-16 (relay hardening split out 2026-11-09)
- 2026-11-09: linked conflicts_with MYAI-16 (adjacent code_runner_runtime and relay blocks in docker/docker-compose.yml)
- 2026-11-09: linked relates_to MYAI-28 (the relay idle timeout must stay above the max execution timeout)
- 2026-11-09: implemented, verified live (5/5 PASS), reviewed (round 1: 7 fixed, 2 rejected), re-verified
- 2026-11-09: PR opened https://github.com/archit342000/My-AI/pull/83 (batch-autopilot: shipped, base develop)
- 2026-11-09: closed (PR merged into develop)
