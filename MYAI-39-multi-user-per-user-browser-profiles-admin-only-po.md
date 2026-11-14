---
id: MYAI-39
title: "Multi-user: per-user browser profiles, admin-only portal, serialised code runs"
status: done
created: 2026-11-09
updated: 2026-11-10
links:
  blocks: [MYAI-42, MYAI-47]
  blocked_by: [MYAI-2, MYAI-3, MYAI-16, MYAI-35, MYAI-38]
  conflicts_with: [MYAI-36, MYAI-37, MYAI-40]
  relates_to: [MYAI-27]
  split_from: [MYAI-32]
  split_into: [MYAI-47]
---

## Description
Split from MYAI-32 (Step 7: Browser and code-runner isolation). Part of making My-AI multi-user behind Cloudflare Access. Implement after MYAI-1 to MYAI-31 have merged.

Read the MYAI-32 Plan first: the Audit (single-user assumptions with file references), the Approach, the Decisions and the Reviewer brief are binding for this ticket. Step scope from MYAI-32:

- **Depends on:** MYAI-35, MYAI-38
- **Files:** `playwright_mcp/server.py` (modify): `browser_start_session` takes `profile_id` (validated `^[a-z0-9_-]{1,64}$`) and uses `playwright_data/profiles/<profile_id>`; it attaches over CDP only when `profile_id` is the portal owner's. `backend/tools/agents/browsing_agent/agent.py` (modify: pass the profile from the chat owner). `backend/tools/router.py` and `app.py` (modify: portal routes and `portal_ws_proxy` are admin-only). `backend/tools/implementations/code_executor.py` and `app.py` (modify: a process-wide run lock and a per-user queue cap around `run_code`, `run_file` and live runs). `backend/config.py` (modify: the cap). Tests in `playwright_mcp/tests/`, `backend/tools/tests/`, `tests/test_app.py`.
- **Change:** as in Approach.
- **Verification:** unit tests: two users get different profile directories; a non-admin session never attaches over CDP; two concurrent runs do not overlap (timestamps); over-cap runs get a clear error. Live check on a throwaway stack: a cookie set in user A's session is absent in user B's. A file written to `/tmp` by one run is gone before the next run (decision 3).

## Acceptance criteria
- [ ] Agent browsing sessions use `playwright_data/profiles/<profile_id>`, chosen by the backend from the chat owner; `profile_id` is validated
- [ ] Only the admin's sessions attach to the portal Chromium over CDP; portal routes and the VNC WebSocket are admin-only
- [ ] Code runs (`run_code`, `run_file`, live runs) never overlap, and the per-user queue cap returns a clear error
- [ ] After each run, its process group is killed and its sandbox (with its per-run `HOME` and `TMPDIR`) and everything under `/tmp`, `/var/tmp` and `/dev/shm` is removed before the next run (decision 3; deeper cross-run isolation is in MYAI-47)
- [ ] Live check: a cookie set in user A's session is absent in user B's
- [ ] Tests pass and `ruff check .` is clean

## Plan
**Date:** 2026-11-09  **Status:** Validated (revision 2)

### Objective
Stop users sharing browser state or running code alongside each other.
- Agent browsing gets one persistent Playwright profile per user, chosen by the backend.
- Only the admin's sessions may attach to the portal Chromium. The portal routes and the VNC WebSocket are admin-only.
- Code runs are serialised process-wide, with a per-user cap on queued runs.
- After each run, the run's process group is killed and its sandbox and the scratch directories are cleared (decision 3). Stronger cross-run isolation is a known residual, handled by the MYAI-47 spike.

### Context
- **Requirement:** this ticket's Description and Acceptance criteria. MYAI-32 Plan: Audit items 11 and 12, Step 7, Decisions 2 and 3.
- **Assumes merged:**
  - MYAI-33: `forbid_non_admin`-style checks via `current_user()` (`forbid_non_admin` itself comes from MYAI-38); `db.get_user`.
  - MYAI-35: `db.get_chat_owner`, `owns_chat`; the `login_as` fixture.
  - MYAI-38: `forbid_non_admin()`, `admin_required`, and `owner_is_admin` in `ToolHandler`.
  - MYAI-2 and MYAI-3: the portal VNC auth header helper and the `/portal/init` API key, both server-side.
  - MYAI-1, MYAI-16 and MYAI-17: the runtime runs as one `runner` uid in `code_runner_runtime` behind the relay.
  - MYAI-27 and MYAI-28: the live-run WebSocket sends the key in a header, and timeouts are clamped.
  - MYAI-5, MYAI-23 and MYAI-26: short error messages.
- **Current code:**
  - **Playwright** (`playwright_mcp/server.py`):
    - `browser_start_session(session_id, stealth_level, scope)` (490-592) attaches to the portal Chromium over CDP whenever the portal process is running (503-524).
    - Otherwise it calls `launch_persistent_context` on the single `playwright_data/default_profile` (527-533). Two concurrent persistent contexts on one directory fail, which is today's behaviour too.
    - `_portal_user_data_dir` is `playwright_data/portal_profile` (71); `portal_init` is at 810.
  - **Browsing agent** (`backend/tools/agents/browsing_agent/agent.py:72-101`) calls `browser_start_session` with a server-generated `session_id` stored on the chat. The browser tools in `backend/tools/browser.py` read the session id from the chat, never from the model.
  - **Portal routes:** `/api/tools/portal/vnc/...` and `/api/tools/portal/init` (`backend/tools/router.py:246-288`), and the WebSocket `/api/tools/portal/ws` (`app.py:61`).
  - **Backend runs:**
    - `run_code` (`backend/tools/implementations/code_executor.py:42`) and `run_file` (180) POST to the runner with `requests` inside `async def`, running in the task worker's event loop.
    - The live run is `code_execution_ws_proxy` (`app.py:117`), a synchronous flask-sock handler thread.
  - **Runtime** (`code_runner_mcp/executor.py`):
    - Runs live in `/tmp/sandbox/<id>` (46), removed with `rmtree` (201, 331).
    - The environment sets `HOME` to the runner's home and `TMPDIR=/tmp` (110-118); `PYTHONPATH` and `NODE_PATH` are absolute.
    - `subprocess.run` (222, 261, 281) and the WebSocket path's `asyncio.create_subprocess_exec` (`code_runner_mcp/server.py:201`, 235) don't start a new session, so grandchildren survive a timeout.
- **Rules:** `docs/standards/security.md` (sandboxing, no secrets); `docs/standards/python.md` (async must not block the loop; shared state needs a lock); `docs/standards/testing.md` (Playwright MCP tests aren't in CI); `AGENTS.md` 4 and 5.

### Approach
- **Per-user browser profiles (`playwright_mcp/server.py`):**
  - `browser_start_session` gains `profile_id: str` as its second parameter, right after `session_id` and before the defaulted ones (required, validated with `^[a-z0-9_-]{1,64}$`, otherwise an error result), and `attach_portal: bool = False`. The MCP tool schema changes on purpose; the backend is its only caller.
  - It attaches over CDP only when `attach_portal` is true and the portal is running. Otherwise it launches the persistent context at `playwright_data/profiles/<profile_id>`.
  - The old `default_profile` is no longer used, so its saved logins are dropped (the admin's portal logins in `portal_profile` stay).
- **Backend caller:** the browsing agent computes the chat owner (`db.get_chat_owner(self.chat_id)`) and the owner's role, then passes `profile_id=<owner id>` (MYAI-33 generates user ids as `uuid4().hex` (its Approach, "Users table and seed"), and those match the pattern) and `attach_portal=<owner is admin>` in both `browser_start_session` calls. With no owner, it raises (no session).
- **Admin-only portal:** an app-level `before_request`, `require_admin_for_portal`, registered after `authenticate_request`, does `return forbid_non_admin()` for any path starting with `/api/tools/portal/` (and returns None otherwise). That covers the VNC files, `/portal/init` and the WebSocket upgrade in one place.
- **Run serialisation:** new module `backend/tools/implementations/run_slot.py`:
  - One process-wide `threading.Lock`, plus a per-user counter under a small guard lock. The counter includes the user's running run and their queued runs.
  - On entry, if the counter is already at `config.CODE_RUNNER_MAX_QUEUED_PER_USER` (default 2: one running plus one queued), it raises `RunQueueFull`. The counter is decremented in a `finally` on every exit path.
  - `run_slot(user_id)` is a sync context manager. It calls `lock.acquire(timeout=config.CODE_RUNNER_QUEUE_TIMEOUT)` (default 120 s) and raises `RunQueueTimeout` when that returns False, so a timed-out run never proceeds unlocked.
  - `async_run_slot(user_id)` is an async one. It polls without blocking: `lock.acquire(blocking=False)`, and if that fails, `await asyncio.sleep(0.1)` and retry, until `CODE_RUNNER_QUEUE_TIMEOUT` passes and `RunQueueTimeout` is raised.
    - No thread ever waits on the lock on the task's behalf. If the task is cancelled while waiting, it never acquired the lock, so nothing can leak. Once acquired, `release` is in a `finally`.
    - This also uses no executor threads, so waiters can't starve the default pool used by `asyncio.to_thread`.
  - `run_code`, `run_file`, `install_packages` and `list_packages` (the backend callers of the runner) wrap their runner call in `async_run_slot(owner)`, with the owner from `db.get_chat_owner(chat_id)`. The backend therefore never posts a run while an admin install is in flight, so a run's HTTP timeout never includes waiting for an install. If `chat_id` is None or has no owner, they return `Error: Code runner is unavailable for this request.` without taking the slot.
  - The existing blocking `requests` calls inside these `async def` functions move to `await asyncio.to_thread(...)`: `requests.post` at `code_executor.py:93`, 294 and 381, and `requests.get` at 412. That way the event loop isn't stalled during the run either (`docs/standards/python.md`, Async).
  - The WebSocket wraps the upstream session in `run_slot(db.get_chat_owner(chat_id))`, the same key as the tools. If there's no owner, it sends the unavailable message as a `stderr` frame plus an `exit` frame without taking the slot. MYAI-37 has already checked that the caller owns that chat.
  - On either error, the tools return `Error: Code runner is busy; try again shortly.`, and the WebSocket sends that as a `stderr` frame plus an `exit` frame. Each rejection is logged with `log_event`: `code_runner_queue_full_error`, `code_runner_queue_timeout_error` or `code_runner_no_owner_error`, with the chat id.
- **Clean between runs** (`code_runner_mcp/executor.py`, `server.py`; the runtime source after MYAI-1 and MYAI-17, service `code_runner_runtime`). This is decision 3's bounded check, not a full isolation guarantee:
  - **Per-run `HOME` and `TMPDIR`:** `prepare_sandbox` creates `<sandbox>/home` and `<sandbox>/tmp` and sets `HOME` and `TMPDIR` to them in the run's environment. `PYTHONPATH` and `NODE_PATH` stay as they are, so installed packages still load.
  - **Process group:** every user-code subprocess starts with `start_new_session=True`. When it ends or times out, the runner sends SIGKILL to the whole group (`os.killpg`, catching only `ProcessLookupError`) and reaps the child. The sync paths move from `subprocess.run` to `Popen` with `communicate(timeout=...)` so the group id is known; the WebSocket path already uses `create_subprocess_exec`.
  - **Scratch clear:** after the group kill, the runner removes the sandbox directory and every entry under the scratch roots, which default to `/tmp`, `/var/tmp` and `/dev/shm`. The roots and the sandbox base (`/tmp/sandbox`, `executor.py:46`) are module-level settings. Both the executor's and the WebSocket handler's cleanups go through one function, `clear_scratch()`. It reads the roots and the sandbox base from the module globals on every call (not as default arguments), and `scratch_roots()` returns the values it would use, which replaces the `rmtree(..., ignore_errors=True)` at `server.py:340`. An autouse fixture in `code_runner_mcp/tests/conftest.py` points the roots and the sandbox base at `tmp_path` for every test, and asserts that `scratch_roots()` returns no default path, so no test can touch the real ones. A grep in Step 6 confirms that no test outside `code_runner_mcp/tests` imports the runtime's `executor` or `server`.
  - **Failures aren't masked:** the same clear also runs at the start of every run, before `prepare_sandbox`.
    - If the post-run clear can't remove a path, the run's result reports `Error: Runner cleanup failed.` (on the WebSocket, a `stderr` frame), and the runner logs `runner_cleanup_error` with the path (the runner uses Python `logging`; `log_event` is backend-only).
    - If the pre-run clear of the next run still can't remove it, that run is refused with the same error and doesn't execute.
    - So no run starts on top of another run's leftovers. This is a cleanup, not a security boundary (see Risks).
  - **Why no lock in the runner:** the backend's `run_slot` (Step 4) already serialises every backend call to the runner (runs, installs, package lists), so a scratch clear never overlaps another call.
- **Rejected:**
  - Per-user runtime containers, or split uids for the server and user code: stronger isolation, but its design needs hands-on checks in the real container. It moves to the MYAI-47 spike (user decision, 2026-11-09).
  - Sharing one persistent context per profile across that user's concurrent sessions: a larger refactor of the session registry; today's one-context-per-session limit stays (see Risks).
  - Holding a blocking lock inside the async tools: it would stall that worker's event loop.

### Out of scope
Cross-run isolation beyond the bounded cleanup above (split uids, IPC, stray `setsid` processes, home-tree writes, the readable runner key): the MYAI-47 spike. Restricting non-admin code execution (user decision: no restriction). Per-user portal containers (deferred by Decision 2); install isolation (`install_packages` is admin-only per MYAI-38); rate limits (MYAI-40); frontend hiding of the portal entry (MYAI-41).

### Steps
#### Step 1: Playwright profiles
- **Status:** todo
- **Depends on:** none
- **Files:** `playwright_mcp/server.py` (modify): `browser_start_session`. `playwright_mcp/entrypoint.sh` (modify): the stale-lock loop (lines 15-17) becomes `for profile_dir in /app/playwright_data/portal_profile /app/playwright_data/profiles/*; do` (no `default_profile`), so per-user profiles start after a container is recreated. `playwright_mcp/tests/test_server.py` (modify). `playwright_mcp/README.md` (modify: the `playwright_data/profiles/<user id>` layout, the retired `default_profile`, and the entrypoint's lock cleanup).
- **Change:** as in Approach.
- **Verification:** unit tests with a mocked Playwright object:
  - Two `profile_id`s give two different `user_data_dir` paths.
  - An invalid `profile_id` returns an error, with no launch.
  - `attach_portal=False` never calls `connect_over_cdp`, even with the portal running; `attach_portal=True` does when it's running.
  - `entrypoint.sh` clears the three Singleton files in `portal_profile` and in every `playwright_data/profiles/*/` (a shell glob); `default_profile` is no longer listed.
  - Run with the playwright image's pinned dependencies (this suite isn't in CI, `docs/standards/testing.md`).

#### Step 2: Browsing agent passes the profile
- **Status:** todo
- **Depends on:** 1
- **Files:** `backend/tools/agents/browsing_agent/agent.py` (modify): the two `browser_start_session` calls. `backend/tools/agents/browsing_agent/tests/test_agent.py` (modify).
- **Change:** as in Approach.
- **Verification:** with a mocked `playwright_client`, an admin-owned chat sends `profile_id=<admin id>, attach_portal=True`, a user-owned chat sends `profile_id=<user id>, attach_portal=False`, and a chat without an owner raises.

#### Step 3: Admin-only portal
- **Status:** todo
- **Depends on:** none
- **Files:** `app.py` (modify): `require_admin_for_portal`. `tests/test_app.py` (modify).
- **Change:** as in Approach.
- **Verification:** as a user, `GET /api/tools/portal/vnc/`, `POST /api/tools/portal/init` and a WebSocket upgrade to `/api/tools/portal/ws` give 403, and the upstream isn't contacted (`httpx` and `ws_client` mocks not called). As the admin, they pass the hook.

#### Step 4: Run slot
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/tools/implementations/run_slot.py` (create); `backend/tools/implementations/tests/test_run_slot.py` (create); `backend/tools/implementations/README.md` (modify: `run_slot.py` row); `backend/config.py` (modify): `CODE_RUNNER_MAX_QUEUED_PER_USER`, `CODE_RUNNER_QUEUE_TIMEOUT`; `backend/tests/test_config.py` (modify).
- **Change:** as in Approach.
- **Verification:**
  - Two threads holding `run_slot` never overlap: the first holds the slot until a `threading.Event` is set. The second is started, and after `second.join(timeout=<injected 0.2 s>)` it's still alive and hasn't recorded entry. After the event is set it enters and finishes. Every `join` is bounded (an injected short timeout, then an `is_alive()` assertion), and the injected queue timeout is longer than the 0.2 s join, so the second thread is still waiting rather than timed out. All timeouts in these tests are injected short values; there are no wall-clock sleeps beyond the 0.1 s poll interval, which is patched to 0.
  - With the cap at 2, the user's third concurrent entry (one running, one queued) raises `RunQueueFull`, while another user's run still queues.
  - A short timeout raises `RunQueueTimeout`, and the lock isn't held afterwards.
  - Cancelling an `async_run_slot` waiter leaves the lock free once the holder releases (a later run acquires it), and the counter back at zero.
  - While a waiter polls, `asyncio.to_thread` work on the same loop still runs (no executor threads are used for waiting).
  - `async_run_slot` doesn't block the event loop: another coroutine runs while waiting.
  - Counters return to zero after errors.

#### Step 5: Use the slot
- **Status:** todo
- **Depends on:** 4
- **Files:** `backend/tools/implementations/code_executor.py` (modify): `run_code`, `run_file`, `install_packages`, `list_packages`. `app.py` (modify): `code_execution_ws_proxy`. `backend/tools/tests/test_code_executor.py`, `tests/test_app.py` (modify).
- **Change:** as in Approach.
- **Verification:** `run_code`, `run_file`, `install_packages` and `list_packages` call the runner inside the slot (a patched slot records the owner), via `asyncio.to_thread` (patched `requests.post`/`requests.get` are called from a worker thread), and return the busy message on `RunQueueFull`. The rejection events are logged. A missing chat or owner returns the unavailable message without taking the slot. The WebSocket sends the busy frames and doesn't connect upstream when the slot can't be taken.

#### Step 6: Clean between runs
- **Status:** todo
- **Depends on:** none
- **Files:** `code_runner_mcp/executor.py` (modify: `prepare_sandbox` environment, the run subprocesses, `clear_scratch()` with injectable roots, used pre- and post-run); `code_runner_mcp/tests/conftest.py` (create, or extend if MYAI-4 or MYAI-28 added one: the autouse roots fixture); `code_runner_mcp/server.py` (modify: the WebSocket run's process group and cleanup); `code_runner_mcp/tests/test_executor.py`, `test_server.py` (modify); `code_runner_mcp/README.md` (modify).
- **Change:** as in Approach (Clean between runs).
- **Verification:**
  - Unit tests:
    - `HOME` and `TMPDIR` are inside the sandbox.
    - Every user-code subprocess call passes `start_new_session=True`, and the group is killed after it ends and after a timeout (patched).
    - With the scratch roots and sandbox base pointed at temporary directories: after a run, the sandbox and the scratch directories are empty.
    - A post-run removal that fails (patched) makes the run report the cleanup error. If the next run's pre-run clear also fails, that run is refused without executing.
    - WebSocket path: when the run times out (patched short timeout), and when the client disconnects mid-run (the handler's `finally`), the process group is killed and the scratch is cleared.
  - `cd code_runner_mcp && PYTHONPATH=. ../venv/bin/python -m pytest` (`docs/standards/testing.md`).
  - `grep -rln "code_runner_mcp.executor\|code_runner_mcp.server\|from executor import\|from server import" --include=*.py . | grep -v '^./code_runner_mcp/'` finds no test file.

#### Step 7: Docs, full gate and live check
- **Status:** todo
- **Depends on:** 1, 2, 3, 5, 6
- **Files:** `docs/standards/security.md` (modify: per-user browser profiles, admin-only portal, serialised runs, the bounded cleanup and its residuals); `backend/tools/README.md`, `backend/tools/agents/browsing_agent/README.md` (modify).
- **Change:** docs match the code.
- **Verification:**
  - With the env from `docs/standards/testing.md` (`EMBEDDING_URL`, `AI_URL`, `AI_API_KEY`, `PYTHONPATH=.`): `venv/bin/python -m pytest backend`, `venv/bin/python -m pytest tests`, the code-runner suite as in Step 6, the `playwright_mcp` suite as in Step 1 (with the playwright image's pinned dependencies), and `venv/bin/python -m ruff check .`.
  - Live check on a throwaway stack with two users (`AUTH_PROVIDER=static`, restarting with each email):
    - A cookie set on a test page in user A's browsing session is absent in user B's.
    - User B can't open the portal (403).
    - Two simultaneous runs from different users run one after the other (runner logs).
    - A file written to `/tmp/x` and a `sleep 600 &` started in the same process group by one run are gone before the next run.
  - Evidence goes in `~/.claude/tickets/My-AI/MYAI-39-evidence/`.

### Tests
Covered per step.

### Risks and open questions
- **Losing `default_profile`** means saved agent logins must be redone. The admin's portal profile is unaffected. Recorded for the PR notes.
- **Concurrent browsing sessions for the same user** on one profile still fail to launch a second persistent context, as today. A shared per-profile context is a follow-up if needed.
- **Serialising runs lowers throughput.** The queue cap and timeout keep waits bounded; per-user runtimes are the follow-up (Decision 3).
- **Known residuals of the bounded cleanup** (accepted for serialised runs; the MYAI-47 spike addresses them):
  - a process that leaves its group (`setsid`, double fork) survives;
  - SysV and POSIX IPC objects survive;
  - files a run writes into the runner's home (including the `PYTHONPATH` and `NODE_PATH` trees) survive and can affect later runs;
  - user code can read the runner API key (MYAI-1 residual) and call the runner directly, including `/install`;
  - user code shares the server's uid and can signal it.
  Non-admin users keep code execution (user decision).
- **Per-run `HOME`** means caches under `$HOME` start cold, which can slow some languages. That's acceptable; MYAI-47 can revisit it.

### Success criteria
- [ ] Agent browsing uses a per-user profile chosen by the backend; only admin sessions attach to the portal over CDP.
- [ ] Portal HTTP routes and the VNC WebSocket give 403 to non-admins.
- [ ] Code runs never overlap, and the per-user queue cap and timeout give a clear error.
- [ ] After each run, its process group is killed and its sandbox and the scratch directories are cleared; the residuals are documented.
- [ ] Live check: user A's cookie is absent in user B's session.
- [ ] Tests pass and `ruff check .` is clean.

### Reviewer brief
- **Objective:** per-user agent browser profiles; an admin-only portal and CDP attach; code runs serialised with a per-user queue cap; and, after each run, a bounded cleanup (process group killed; sandbox, per-run `HOME`/`TMPDIR` and the scratch directories cleared) before the next run.
- **Key decisions:**
  - `browser_start_session(session_id, profile_id, ..., attach_portal=False)` uses `profiles/<owner id>`, with CDP only for admin chats; `entrypoint.sh` clears locks for `profiles/*`.
  - An app `before_request` makes `/api/tools/portal/*` admin-only.
  - `run_slot` / `async_run_slot` (a non-blocking polled lock, a per-user cap, a timeout, keyed on the chat owner) wrap every backend call to the runner. The four `requests` calls move to `asyncio.to_thread`. Rejections are logged with `log_event`.
  - Runner: `start_new_session=True` and a group kill after every user-code run, plus one `clear_scratch()` (injectable roots, read at call time) before and after each run. A failed clear reports an error and refuses the next run if it persists.
  - Stronger isolation (split uids and the residuals listed under Risks) is deliberately out of scope and moves to MYAI-47. No restriction on non-admin code execution.
- **Out of scope:** the MYAI-47 isolation work, per-user portal containers, install isolation, rate limits, frontend.
- **Success criteria:** as listed in the Plan.

The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- **Revision 2 (2026-11-09):** scope reset at the user's request. The split-uid isolation and the absolute "nothing survives" guarantee are removed (moved to the MYAI-47 spike), and the bounded cleanup from decision 3 is restored. There's a fresh 5-round budget, with findings judged only against this scope. The earlier rounds below are kept as history.
- **Revision 2, round 1 (full check):** the validator returned FAIL (3 BLOCKING, 6 MINOR). My judgement: FAIL. All three BLOCKING issues were in scope and fixed:
  - the install and list calls blocked the event loop;
  - the scratch roots needed to be injectable so tests can't touch the real `/tmp`;
  - a failed clear was masked, so there's now a pre-run clear that refuses a run if the clear still fails.
  MINOR, fixed: venv test commands; Event-based ordering in place of timestamps; WebSocket timeout and disconnect tests; `profile_id` position; `log_event` names; the README profile layout.
- **Revision 2, round 2 (diff-scoped):** the validator returned FAIL (1 BLOCKING, 2 MINOR). My judgement: FAIL. BLOCKING, valid: not every test was guaranteed to override the roots, and the WebSocket cleanup at `server.py:340` bypassed them. Now there's one `clear_scratch()` and an autouse fixture. MINOR, fixed: the `playwright_mcp` suite added to the gate; a bounded join.
- **Revision 2, round 3 (diff-scoped):** the validator returned PASS (0 BLOCKING, 4 MINOR). My judgement: PASS. MINOR, fixed: roots read at call time, with `scratch_roots()` checked by the fixture; bounded joins with the queue timeout longer than the join; Step 7 depends on 1; a grep for other importers of the runner.
- **Round 1:** the validator returned FAIL (5 BLOCKING, 5 MINOR). My judgement: FAIL.
  - All five BLOCKING issues were valid and fixed:
    - The `/tmp` sweep left nested and sibling paths; now everything is wiped.
    - Cleanup could kill `/install` or `/packages`; now there's a runner-side lock over all endpoints.
    - The timed acquire's return value was unchecked and cancellation could leak the lock.
    - Blocking `requests` ran inside async code.
    - `entrypoint.sh` only cleared locks for the fixed profiles.
  - MINOR: `return forbid_non_admin()`; README row; narrow `ProcessLookupError`; cap semantics; no-owner rule. Disproved: the id format, since MYAI-33 uses `uuid4().hex`.
- **Round 2:** the validator returned FAIL (3 BLOCKING, 4 MINOR). My judgement: FAIL.
  - Valid and fixed:
    - The executor-thread acquire couldn't be made cancellation-safe; replaced with a non-blocking poll.
    - The runner WebSocket lock had the same issue; also a non-blocking poll, with timed acquire and 503 in the sync handlers.
    - The home package trees were writable; a manifest check was added.
  - MINOR, fixed: entrypoint lines and glob; executor starvation (resolved by the poll); install wait counted in the run timeout (the slot now also covers install and list); WebSocket key is the chat owner.
- **Round 3:** the validator returned FAIL (3 BLOCKING, 3 MINOR). My judgement: FAIL.
  - Valid and fixed: size and mtime can be forged, so sha256 is used; the lock is taken before `prepare_sandbox`; the `-xdev` check missed bind mounts and `/dev/shm`.
  - MINOR, fixed: cleanup order; no-owner rule for the WebSocket; the server writes no scratch files.
- **Round 4:** the validator returned FAIL (1 BLOCKING, 4 MINOR). My judgement: FAIL.
  - Valid and fixed: the tamper wipe only covered the package directories and re-baselined other files; now there's a full home wipe.
  - MINOR, fixed: the manifest is in memory only; the writable check runs as `runner` with prune and char devices excluded; single worker stated; ctime-gated re-hash.
- **Round 5 (cap):** the validator returned FAIL (1 BLOCKING, 3 MINOR). My judgement: FAIL.
  - BLOCKING, valid: errors during the post-run check could fail open. Fixed after the cap: the sequence runs in a `finally`, any error is treated as tamper, and a failed wipe marks the runner unhealthy, with tests.
  - MINOR:
    - Disproved: the "`code_runner_runtime` doesn't exist" claim. That service comes from MYAI-1, MYAI-16 and MYAI-17, which are assumed merged; the worktree predates them.
    - Fixed: `workers=1` goes in the `uvicorn.run` call; the racy-clean ctime rule.
  - **Unresolved:** these round 5 fixes haven't been re-validated, because the 5-round cap was reached. Re-validate them (a single diff-scoped round on "Home tree integrity", "Single process" and Step 6 Verification) before implementing.
- **Rounds 6-14 (beyond the cap, at the user's request, 2026-11-09):** every round returned FAIL. Each one closed real gaps:
  - fail-closed cleanup with a health gate re-checked after the lock;
  - a simplified design (`init`, tmpfs scratch, an empty home re-hashed in full, startup reset);
  - bounded reaps and compile;
  - admin-op cleanup order;
  - `pgids` plumbing;
  - FIFO-safe hashing;
  - a caller allowlist on the runtime and the relay.
  Round 14's open findings:
  - BLOCKING: SysV IPC objects survive between runs.
  - MINOR: keyrings; a survivor false positive from healthcheck probes; capability, IP and IPv6 checks for the allowlist; the relay failing closed on DNS; a pure ASGI middleware for the WebSocket; non-blocking re-resolve; mode bits in the manifest and a raising walk; `PR_SET_DUMPABLE`.
  - **Root cause:** user code runs as the same uid as the runner server, so it can also SIGSTOP or ptrace the server, which defeats every in-process defence. **Pending a user decision** on the isolation model (see Log).
- **Rounds 15-16 (split-uid design):** both FAIL. Round 15 led to sandbox ownership through a `runner` helper, `/run/secrets` set to 0700, the naming clarified, compose options, child rlimits, package commands and env. It disproved two claims: MYAI-4 already fails closed, and Docker's seccomp profile does block the keyring calls. Round 16 is open:
  - the root server (no `CAP_DAC_OVERRIDE`) can't walk the `runner`-owned 0700 `/tmp/sandbox`;
  - the package `env` lacks `PATH`;
  - `RLIMIT_AS` at 384 MiB breaks the JVM;
  - the root server can read the key only if the host file is world- or group-readable;
  - minor: ptrace wording; `preexec_fn` with threads; `/proc` and `/sys` in the writable check; package `TMPDIR`.
  Validation stopped here; these need hands-on checks in the real container (see Log).

## Implementation notes
### Autopilot run (2026-11-09)
- Mode: automatic (batch-autopilot item 9/13)
- Branch: feature/multi-user-browser-profiles-portal  PR base: feature/multi-user-admin-only-config (stacked on MYAI-38's PR #91; chain #84 > #87 > #88 > #89 > #90 > #91)  Starting commit: eafd046cddc743f2a331d559b3c0c6c3d78f8630
- Dirty before start: none
- Work files: none yet
- Counters: fix 0/10, review 0/5, re-verify 0
- Last completed stage: 1 plan (already validated, revision 2)  Next: 2 implement
- Hard blocker: none
- WIP commit: none

### Autopilot decisions (2026-11-09)
- Plan already validated; stage 1 skipped.
- Stacked on the MYAI-38 branch (blocked_by 35, 38; batch chain).

### Baseline (2026-11-09)
backend+tests: 10 failed (async-plugin: test_cache_system 2, test_research_utils 2, test_code_executor 6), rest pass. playwright_mcp: 8 asyncio-mark failures. code_runner_mcp (own venv /tmp/venv-cr): all pass.

### Implementation progress
- [x] Step 1: Playwright profiles - playwright_mcp/server.py, entrypoint.sh, tests
- [x] Step 2: Browsing agent passes the profile - browsing_agent/agent.py, tests
- [x] Step 3: Admin-only portal - app.py before_request, tests/test_app.py
- [x] Step 4: Run slot - backend/tools/implementations/run_slot.py, config.py, tests
- [x] Step 5: Use the slot - code_executor.py `_call_runner`, app.py WebSocket proxy, tests
- [x] Step 6: Clean between runs - code_runner_mcp/executor.py (clear_scratch, kill_group, _run_in_group, per-run HOME/TMPDIR), server.py (WebSocket), tests/conftest.py (autouse temp roots), tests
- [x] Step 7: Docs - docs/standards/security.md, backend/tools/README.md, browsing_agent/README.md, playwright_mcp/README.md, code_runner_mcp/README.md
- Branch: feature/multi-user-browser-profiles-portal (base feature/multi-user-admin-only-config)

### Smoke test (2026-11-09)
backend+tests: 10 failed (identical baseline), 1589 passed. code_runner_mcp: 192 passed, 1 skipped. playwright_mcp: 8 failed (baseline), 71 passed. ruff clean.
PR: https://github.com/archit342000/My-AI/pull/92, branch feature/multi-user-browser-profiles-portal, base feature/multi-user-admin-only-config

## Verification

### Verification plan and results (2026-11-09)
Live (real app, throwaway DATA_DIR, signed JWTs; evidence: MYAI-39-evidence/drive.out):
- V1 bob 403 on every /api/tools/portal route: PASS. V2 alice never 403: PASS (503/404/405 from the absent portal backend). V3 admin route regression: PASS. V4 bob's normal API 200: PASS.
- BLOCKED (live): cookie in user A's session absent in B's (needs a real Chromium and the playwright stack; covered by unit tests asserting distinct `profiles/<id>` dirs and no CDP attach for non-admin). Serialised runs and /tmp clean-up live (needs the runner container; running `clear_scratch` against this host's real /tmp is unsafe): covered by unit tests with temp roots (leftover file removed, backgrounded `sleep` group killed, runs do not overlap).

## Review history
### Round 1 - 2026-11-09
Verdict: Request changes (4 Haiku reviewers: correctness, standards/security, tests, requirements/docs; diff ~1.1k lines).
Resolution: fixing 20, rejecting 8, deferring 4. Checks after fixes: backend+tests 10 failed (baseline) / 1603 passed; code_runner_mcp 200 passed, 1 skipped; playwright_mcp 8 failed (baseline) / 71 passed; ruff clean.
- R1-1 [MAJOR] app.py slot.close / code_executor.py:42 - app frees the run slot while the runner may still run or clean up (disconnect, cancel) - Fixed: `executor.RUN_LOCK` held by `/execute` and `/ws/execute` from pre-run to post-run clear; tests (non-overlap, lock held until clean-up, disconnect).
- R1-2 [MAJOR] code_executor.py:152,379 - client timeout `timeout+5` < compile (15 s) + run - Fixed: `RUNNER_COMPILE_BUDGET = 20`.
- R1-3 [MAJOR] server.py compile phase unbounded - Fixed: `COMPILE_TIMEOUT` (15 s), group killed, exit 1; test.
- R1-4 [MINOR] disconnect releases slot before runner clean-up - Fixed by R1-1 (runner lock).
- R1-5 [MINOR] agent.py on_start/on_resume ignore `{"error"}` result - Fixed: `_raise_on_start_error`; tests.
- R1-6 [MINOR] install subprocess.run kills only the child - Deferred: `/install` is admin only and not a user-code run; no group kill added (follow-up).
- R1-7 [MINOR] same user's concurrent sessions share one profile dir (lock error) - Deferred: pre-existing (was one shared profile for everyone).
- R1-8 [NIT] rmtree onerror deprecated on 3.12 - Fixed (onexc when available).
- R1-9 [NIT] CDP `contexts[0] if ... else contexts[0]` - Pre-existing, untouched.
- R1-10 [MINOR] config values unbounded - Fixed: clamp (>=1, >=0); tests.
- R1-11 [MINOR] pid reuse after reap before group kill - Rejected: a pgid stays reserved while any member lives; the window after the leader is reaped with an empty group is negligible and kill_group only ignores ProcessLookupError.
- R1-12 [MINOR] README wording (off-by-one "queued", unavailable message) - Fixed.
- R1-13 [NIT] hard-coded SANDBOX_BASE/SCRATCH_ROOTS - Rejected: the runner image has no config module; module attributes are the injection point (documented in the README).
- R1-14 [MINOR] stale comment in `_execute` finally - Fixed.
- R1-15 [NIT] `scratch_roots()` wrapper, whitespace hunk, `execute(*args)` signature - Rejected: wrapper used by clear_scratch and is documented; whitespace hunk is the file's own; `execute` has a docstring and delegates to `_execute`.
- R1-16 [NIT] one blank line before find_project_root - Fixed.
- R1-17 [NIT] env vars documented only in config/security.md - Rejected: matches existing practice (no compose/.env documentation for the sibling CODE_RUNNER_* vars).
- R1-18 [MAJOR] weak admin-positive portal test, real network - Fixed: fake upstream, asserts 200 body and upstream call.
- R1-19 [MAJOR] vacuous try/except ownerless test - Fixed: tests call `on_start`/`on_resume` directly with `pytest.raises`.
- R1-20 [MAJOR] sleep-based group-kill tests - Fixed: pid sentinel + polling helpers (`tests/helpers.py`).
- R1-21 [MAJOR] playwright_mcp security tests only in ungated suite - Deferred: playwright suite is not in `scripts/check.sh` (repo rule); the new tests pass there (71 pass, only the 8 baseline failures); stated in the PR.
- R1-22..27 [MINOR] anonymous-portal test, config env test with clean_env, default-constants pin, async slot error release + runner error releases slot, WS compile-failure and `/execute` cleanup-error tests, uuid4 profile ids - Fixed (tests added).
- R1-28 [MINOR] PYTHONPATH pinned in test - Rejected: it is the image contract the requirement keeps (installed packages still load).
- R1-29 [NIT] mid-file imports - Fixed. [NIT] global os.unlink patch - Rejected (scoped to the with block). [NIT] kill_group no-op untested - Fixed.
- Incident: the first version of the new runner tests could run `clear_scratch()` against the real `/tmp` (a handler outliving the fixture's patch) and removed the contents of the host's `/tmp`, including the code-runner test venv. Fixed: `code_runner_mcp/tests/conftest.py` now replaces the roots for the whole session at import time and never restores them. Venv rebuilt at ~/.cache/myai-venv-cr.

### Rounds 2-5 - 2026-11-09 (runtime fixes re-reviewed by Haiku, cap of 5 reached)
- R2 (6 MAJOR/BLOCKER on the new runner lock): Fixed - outer finally cleared scratch without holding the lock; unbounded `communicate()` after a kill could wedge the lock (now bounded, pipes abandoned); `kill_group` waits (bounded) for the group; HTTP lock wait bounded (`LOCK_WAIT`, busy result); exit frame sent after the lock is released; cleanup failure appended to the run's own error; `isError` start results raise; test guard is an explicit raise, not an assert.
- R3: Fixed - every websocket send bounded (`SEND_TIMEOUT`), `kill_group` off the event loop on async paths, tests spy every frame/clear for the lock state, grandchild-based kill_group test. Rejected: pid reuse (negligible), group kill after a reaped leader. Deferred: HTTP run with a same-group child holding stdout (pre-existing subprocess behaviour).
- R4: Fixed - finish() could run twice via the TimeoutError handler (now idempotent, outside the try); readers and stdin errors kill the run; sync kill fallback.
- R5 (cap): Fixed - bounded stdin drain, kill before lock release even under cancellation, post-run clear on an unexpected error, docstring.
- Open at the cap, documented as residuals (security.md, code_runner_mcp/README.md; deeper isolation is the follow-up ticket): setsid/double-fork escapees outlive the lock; a queued live run whose client disconnects still starts; silent programs are bounded only by their timeout; cancelled reader tasks not awaited before release (nit); backend slot released on cancel while the runner is busy (the runner lock keeps runs serial).
- Checks after the last fix: backend+tests 10 failed (baseline) / 1604 passed; code_runner_mcp 214 passed, 1 skipped; playwright_mcp 8 failed (baseline) / 71 passed; ruff clean.

## Log
- 2026-11-09: created (split from MYAI-32 Step 7)
- 2026-11-09: linked split_from MYAI-32 (Step 7)
- 2026-11-09: linked blocked_by MYAI-35
- 2026-11-09: linked blocked_by MYAI-38
- 2026-11-09: linked blocked_by MYAI-2
- 2026-11-09: linked blocked_by MYAI-3
- 2026-11-09: linked blocked_by MYAI-16
- 2026-11-09: linked blocks MYAI-42
- 2026-11-09: linked conflicts_with MYAI-36 (shared files per MYAI-32 Steps intro)
- 2026-11-09: linked conflicts_with MYAI-37 (shared files per MYAI-32 Steps intro)
- 2026-11-09: linked conflicts_with MYAI-40 (shared files per MYAI-32 Steps intro)
- 2026-11-09: linked relates_to MYAI-27
- 2026-11-09: plan drafted, unresolved issues (5-round cap reached; round 5 fixes need one more validation round)
- 2026-11-09: validation rounds 6-14 run at user request; still FAIL; root cause (same uid for server and user code) needs a user decision
- 2026-11-09: validation stopped after round 16 (user asked why it isn't converging); open items recorded in Validation log
- 2026-11-09: plan revised (revision 2): scope reset to decision 3's bounded cleanup; split-uid isolation moved to MYAI-47; no restriction on non-admin code execution (user decisions)
- 2026-11-09: linked split_into MYAI-47 (user decision: stronger runner isolation as a hands-on spike)
- 2026-11-09: linked blocks MYAI-47 (builds on the serialised runner)
- 2026-11-09: plan validated (revision 2), 3 rounds
- 2026-11-09: autopilot started (batch)
- 2026-11-09 batch-autopilot: shipped https://github.com/archit342000/My-AI/pull/92, base feature/multi-user-admin-only-config
- 2026-11-10: closed (merged into develop via the PR recorded in Implementation notes; deployed to myai.architanand.dev)
