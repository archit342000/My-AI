---
id: MYAI-47
title: "Code runner: split-uid isolation spike"
status: done
created: 2026-11-09
updated: 2026-11-10
links:
  blocked_by: [MYAI-39]
  relates_to: [MYAI-1, MYAI-32]
  split_from: [MYAI-39]
---

## Description
Split from MYAI-39 (user decision, 2026-11-09). MYAI-39 serialises code runs and does a bounded cleanup between runs. This spike prototypes stronger cross-run isolation in the real runtime container (`code_runner_runtime`, after MYAI-1, MYAI-16 and MYAI-17), measures it, and only then writes a plan.

The candidate design, from MYAI-39's validation rounds 6-16 (its Validation log keeps the detail):
- the server runs as root with only `SETUID`, `SETGID` and `KILL`, plus `no-new-privileges` and `init`;
- user code runs as `runner`, and package installs as `runner-pkg` into `/opt/runner`;
- tmpfs scratch mounts;
- `/run/secrets` locked from user code;
- post-run cleanup of processes, IPC and scratch, run as the target uid;
- a health gate that taints on any cleanup failure.

This needs a documented exception to `docs/standards/docker.md` (approved in principle by the user).

Open questions to settle by trying them, not on paper:
- How does the root server, without `CAP_DAC_OVERRIDE`, inspect or clear `runner`-owned sandbox directories?
- Can the root server read the key secret given the host file's mode?
- Do `RLIMIT_AS`/`RLIMIT_NPROC` or cgroup limits let the JVM, Go and Node start?
- What `PATH` and `TMPDIR` do the package commands need?
- Are the keyring calls blocked under the deployed seccomp profile?
- Is `/proc/sys` or `/sys` writable?
- Is `preexec_fn` safe with the server's threads?

Residuals this should close (from MYAI-39's Risks):
- processes that leave their group;
- SysV and POSIX IPC objects;
- writes to the runner's home and package trees;
- the runner API key being readable by user code (MYAI-1);
- user code sharing the server's uid.

## Acceptance criteria
- [x] A prototype in the built runtime answers each open question, with evidence (commands, outputs, timings)
- [x] A decision on the isolation model, based on the evidence, is recorded here
- [x] A plan (or a set of implementation tickets) is written from that decision

## Plan
**Date:** 2026-11-09  **Status:** Validated

### Objective
Find out by experiment whether the split-uid isolation model works for the code runtime, and at what cost, then decide and plan it. This ticket produces evidence, a decision and a plan or implementation tickets. It doesn't ship code.

### Context
- **Requirement:** this ticket's Description and Acceptance criteria. The candidate design and its unresolved questions come from MYAI-39's Validation log (rounds 6-16).
- **Starting point:** after MYAI-1, MYAI-16, MYAI-17 and MYAI-39 have merged, with the runtime service `code_runner_runtime` built from `docker/Dockerfile.code-runner` and the `code_runner_mcp/` source. MYAI-39's bounded cleanup and backend run slot are in place.
- **Rules:**
  - `docs/standards/docker.md` (non-root, no extra capabilities): this design needs an exception, approved in principle by the user.
  - `docs/standards/docker.md` Testing containers: unique names for temporary builds, removed afterwards.
  - `AGENTS.md` 7: stop and ask before contradicting a documented rule. The exception is recorded only after the user sees the evidence.

### Approach
- Prototype on a throwaway branch: `feature/runner-split-uid-spike`, from `develop` (`docs/standards/gitflow.md`), never merged.
- The spike code lives in its own git worktree on that branch at `/home/archit-anand/docker-data/shared/Coding/My-AI/.claude/worktrees/runner-split-uid-spike` (`git worktree add /home/archit-anand/docker-data/shared/Coding/My-AI/.claude/worktrees/runner-split-uid-spike -b feature/runner-split-uid-spike develop`).
- Use a standalone compose file in the evidence folder (`MYAI-47-evidence/compose.spike.yml`). Its `build.context` is the absolute path of the spike worktree and its `dockerfile` is `docker/Dockerfile.code-runner`, and every command passes it by absolute path (`-f /home/archit-anand/.claude/tickets/My-AI/MYAI-47-evidence/compose.spike.yml`), so it works from any directory. It defines only the runtime service, from the spike image tagged `my-ai-spike-runtime`, with `container_name: my-ai-spike-runtime`, no host ports and its own network. It's run as `docker compose -p my-ai-spike -f /home/archit-anand/.claude/tickets/My-AI/MYAI-47-evidence/compose.spike.yml`.
- The base `docker/docker-compose.yml`, with its fixed container names and host ports, is never used. `docker/docker-compose.testing.yml` holds the RAG grid-search services and isn't a fit for a one-off runtime image, so the spike uses its own file. It still follows the unique-names and cleanup rules in `docs/standards/docker.md` (Testing containers).
- Answer each open question with a command and its output, not by reasoning.
- Then check the five residuals listed in MYAI-39's Risks against the prototype.
- Record everything in `~/.claude/tickets/My-AI/MYAI-47-evidence/`, and write the decision and the plan in this ticket.
- Rejected: designing on paper again. MYAI-39 showed that paper review doesn't converge here.

### Out of scope
Merging any code; changes to the real stack; per-user runtimes (only if the evidence points there, recorded as an option in the decision).

### Steps
#### Step 1: Prototype image and stack
- **Status:** todo
- **Depends on:** none
- **Files:**
  - On the spike branch only:
    - `docker/Dockerfile.code-runner`: users `runner` (`useradd -M`, no home; runs get `HOME` in their sandbox) and `runner-pkg` (`useradd -M -d /opt/runner/pkg-home`); create `/opt/runner/python` and `/opt/runner/node` (owner `runner-pkg:runner-pkg`, mode 0755) and `/opt/runner/pkg-home` (owner `runner-pkg`, mode 0700); the server runs as root;
    - `code_runner_mcp/executor.py` and `server.py` (children started as `runner` or `runner-pkg`);
    - a new `code_runner_mcp/spike_helpers.py` with two small helpers the server starts as a given uid: `make_sandbox` (create the sandbox and write files from stdin) and `clean_uid` (remove that uid's SysV and POSIX IPC objects and scratch files).
  - In the evidence folder: `compose.spike.yml` (capabilities `SETUID`, `SETGID` and `KILL` only, `no-new-privileges`, `init`, tmpfs scratch, `pids_limit`, the `CODE_RUNNER_API_KEY` secret from a throwaway file).
- **Change:** the minimum needed to run one user-code execution and one package install under the candidate model.
- **Verification:** `docker compose -p my-ai-spike -f /home/archit-anand/.claude/tickets/My-AI/MYAI-47-evidence/compose.spike.yml up -d --build` starts `my-ai-spike-runtime`. `docker exec my-ai-spike-runtime python -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8100/health').status)"` prints 200. One Python run through `/execute` (with the throwaway key in the `X-API-KEY` header, as `server.py:26` reads it) returns its output.
- **Teardown:** at the end of every working session and in Step 5, run `docker compose -p my-ai-spike -f /home/archit-anand/.claude/tickets/My-AI/MYAI-47-evidence/compose.spike.yml down -v --rmi local`, and in Step 5 `git worktree remove /home/archit-anand/docker-data/shared/Coding/My-AI/.claude/worktrees/runner-split-uid-spike`.

#### Step 2: Answer the open questions
- **Status:** todo
- **Depends on:** 1
- **Files:** evidence only.
- **Change:** run and record one experiment per question:
  1. **Sandbox ownership:** can the root server (no `CAP_DAC_OVERRIDE`, `CAP_CHOWN` or `CAP_FOWNER`) create a sandbox that `runner` can write, and later list and clear it? Try a server-created directory and a `runner`-helper-created one.
  2. **Secret readability:** first record the real file's owner and mode on the deployment host at the time of the test (`stat -c '%U %G %a' <repo>/secrets/CODE_RUNNER_API_KEY`, where `<repo>` is the deployment checkout). Then, with the throwaway key file set to the same owner and mode, can the server read `/run/secrets/CODE_RUNNER_API_KEY`? After `chmod 0700 /run/secrets`, does `runner` get `EACCES`?
  3. **Limits:** do Java (`javac` and `java`), Go and Node start and finish a small program under `RLIMIT_AS` and `RLIMIT_NPROC`, and under a cgroup-only memory bound? Record the smallest working values.
  4. **Package environment:** which `PATH`, `HOME` and `TMPDIR` do `pip install --target` and `npm install --prefix` need as `runner-pkg`, with MYAI-16's proxy variables?
  5. **Kernel interfaces:** as `runner`, do `keyctl` and `add_key` fail? Are `/proc/sys` and `/sys` read-only?
  6. **`preexec_fn`:** do rlimits set in a `preexec_fn` from the threaded server cause deadlocks over 200 concurrent spawns, compared with a `prlimit`-style wrapper?
  7. **Cleanup reach:** can a `runner`-uid helper remove that uid's SysV and POSIX IPC objects and scratch files, and can the server then verify the result?
- **Verification:** each question has a recorded command, its output, its run time (`time`, or the run's reported duration) and a one-line answer in `MYAI-47-evidence/answers.md`.

#### Step 3: Check the residuals
- **Status:** todo
- **Depends on:** 2
- **Files:** evidence only.
- **Change:** on the prototype, try each MYAI-39 residual from a user run:
  - a `setsid` background process;
  - a SysV shm segment and a POSIX queue;
  - writes that persist:
    - Run A, as `runner`, lists every writable directory (`find / \( -path /proc -o -path /sys \) -prune -o -type d -writable -print`) into `writable_dirs.txt` in the evidence folder, and records its own `HOME`. It tries to write a marker file into each listed directory outside the scratch mounts, and into `/opt/runner/python` and `/opt/runner/node`.
    - Run B reads `writable_dirs.txt` and checks for each marker.
    - `answers.md` records, per path, whether the write was refused, cleaned, or survived into run B;
  - reading the runner key;
  - acting on the server: `kill -STOP`, another signal, and a `ptrace` attach (for example `python -c` with `ctypes` calling `ptrace(PTRACE_ATTACH)`) on the server pid.
  For each, record whether it's blocked or cleaned before the next run.
- **Verification:** a table in `answers.md`: residual, attempt, result, closed (yes or no).

#### Step 4: Decision
- **Status:** todo
- **Depends on:** 3
- **Files:** this ticket (a "Decision" subsection in Implementation notes).
- **Change:**
  - Summarise the evidence and recommend one of: adopt split uids as prototyped, adopt with named changes, or a different model (for example per-user runtimes). Include the cost: run latency, cold caches, operational steps.
  - Ask the user to decide. If the decision needs the `docker.md` exception, record the user's approval.
- **Verification:** the decision is recorded with the user's answer.

#### Step 5: Plan or tickets
- **Status:** todo
- **Depends on:** 4
- **Files:** this ticket's Plan (a dated amendment), or new tickets linked `split_into`.
- **Change:** write the implementation plan from the decision and the evidence, using the `plan` skill. Then delete the spike branch and the `my-ai-spike` images and volumes.
- **Verification:** the implementation plan is validated, or the tickets are created. After the teardown, `docker ps -a`, `docker image ls`, `docker volume ls` and `docker network ls` show nothing named `my-ai-spike*`, and the spike branch is deleted locally and on origin, if it was pushed.

### Tests
None in the repo; this is a spike. Evidence replaces tests.

### Risks and open questions
- **The evidence may favour a different model** (for example per-user runtimes). Step 4 lets the user choose that.
- **Host-specific results** (kernel, Docker version) are recorded with `docker version` and `uname -r`, so they can be rechecked on the deployment host.

### Success criteria
- [ ] Every open question and residual has recorded evidence.
- [ ] The user has made and recorded a decision.
- [ ] An implementation plan or tickets exist, and the spike artefacts are removed.

### Reviewer brief
- **Objective:** settle the split-uid isolation model for the code runtime by experiment, get the user's decision, then plan. No code ships.
- **Key decisions:**
  - Prototype on `feature/runner-split-uid-spike` in its own worktree. A standalone `compose.spike.yml` (absolute build context, runtime service only, `my-ai-spike*` names, no host ports) runs under project `my-ai-spike`; the base compose is never used.
  - Seven question experiments and five residual experiments, each recorded with command, output, timing and answer in `answers.md`.
  - The user decides (and approves the `docker.md` exception if needed) before planning.
  - A full teardown of the spike containers, images, volumes, networks and worktree.
- **Out of scope:** merging code, changes to the real stack.
- **Success criteria:** as listed in the Plan.

The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- **Round 1:** the validator returned FAIL (5 BLOCKING, 3 MINOR). My judgement: FAIL. All five BLOCKING issues were in scope and fixed: the missing helpers; residual coverage; compose isolation from the base file; the gitflow branch name; timings, as the criteria require. MINOR, fixed: a `ptrace` attempt; a concrete key name and health command; teardown commands.
- **Round 2 (diff-scoped):** the validator returned FAIL (2 BLOCKING, 4 MINOR). My judgement: FAIL. BLOCKING, valid: the compose build context; the persistent-write experiment needed a write-then-check-in-the-next-run design. MINOR, fixed: the `X-API-KEY` header; `stat` of the real key; the reason for not using the testing compose file; the `/opt/runner` directories in the Dockerfile.
- **Round 3 (diff-scoped):** the validator returned FAIL (1 BLOCKING, 5 MINOR). My judgement: PASS, since the BLOCKING issue is disproved. User runs can't act as `runner-pkg`; a refused write to the package trees is what closes that residual, and admin installs persisting there is intended. MINOR, fixed: `HOME` for both users recorded; an absolute `-f` path and a fixed worktree location; the full key path and the mode at test time; directory modes and the `runner-pkg` home; `-type d` and a shared `writable_dirs.txt`.

### Implementation plan (2026-11-10)
**Date:** 2026-11-10  **Status:** Validated  (amendment to the validated spike plan; the spike plan above is frozen)

#### Objective
Implement the adopted split-uid isolation in the real code runtime (`code_runner_runtime`), so user code runs as a dedicated uid that cannot read the API key, write persistent paths, signal the server or survive a run, and every run is cleaned and verified before the next. Decision (user, 2026-11-10): adopt as evidenced, including the `docs/standards/docker.md` exception. Evidence: `~/.claude/tickets/My-AI/MYAI-47-evidence/answers.md`, `out/`, `harness/`, `compose.spike.yml`.

#### Context
- **Today** (`docker/Dockerfile.code-runner`): the server runs as `runner` (`useradd -m`, uid 1000 = the host user's uid), `CMD python server.py`; `docker/docker-compose.yml` `code_runner_runtime` has no `read_only`, no cap changes, the key as `/run/secrets/CODE_RUNNER_API_KEY` (`API_KEY_FILE`), `../code_runner_mcp:/app:ro`, `deploy.resources.limits` from `CODE_RUNNER_MEMORY_LIMIT`/`CODE_RUNNER_CPU_LIMIT`, a `/health` check.
- `code_runner_mcp/executor.py` (MYAI-39, merged): `SANDBOX_BASE=/tmp/sandbox`, `SCRATCH_ROOTS`, `RUN_LOCK`, `clear_scratch()` (server-side `rmtree`), `kill_group`, `_run_in_group` (`subprocess.Popen(..., start_new_session=True)`), `CodeExecutor.prepare_sandbox` (server writes files, `HOME`/`TMPDIR` in the sandbox), `execute` = `RUN_LOCK` + pre/post `clear_scratch`. `code_runner_mcp/server.py`: `/install` runs `pip install --user` / `npm install` in `/home/runner` with plain `subprocess.run`, `/packages`, `/ws/execute` (`asyncio.create_subprocess_exec`, `finish()`, `RUN_LOCK`), `/health` always `ok`, `load_api_key` (`API_KEY_FILE`).
- **Evidence the design rests on** (answers.md): root with only SETUID/SETGID/KILL cannot chown, clear runner-owned 0700 trees or `ipcrm` runner IPC, so a runner-uid helper does creation and cleanup; `RLIMIT_NPROC` is counted host-wide per uid (host uid 1000 has 2886 tasks), so the runner uids must not be real host uids and NPROC must be set after the uid switch (prlimit wrapper, not `preexec_fn` before `setuid`); `RLIMIT_AS` minimums Java 2 GB, Node/Go 1 GB; tmpfs `/tmp` must be `exec` and larger than 64 MB for Go (64 MB failed, 512 MB used 35 MB); `read_only: true` leaves only the tmpfs mounts and `/dev/mqueue` writable; compose ignores `uid/gid/mode` on file secrets, so the key goes inside a root-only `0700` tmpfs directory via an absolute secret target (`/run/keys/...`), readable by root only if the host file is world-readable (today `644`) or root-owned; pip needs only `PATH`, npm needs a writable `HOME` and cache.
- **Rules:** `docs/standards/docker.md` (non-root, no extra capabilities: the exception is recorded in Step 6; unique names for temporary builds; never modify existing containers), `docs/standards/security.md` (Tools and sandboxing), `docs/standards/testing.md`, `AGENTS.md`; `docs/pitfalls.md` (code_runner_mcp tests run from inside that directory with their own dependencies). The repo has no GitHub Actions.
- **Evidence on reads:** root without `CAP_DAC_OVERRIDE` can read world-readable files in directories it can traverse (answers.md Q1/Q2) but not inside runner-owned 0700 trees; the server therefore never reads or removes anything under a 0700 tree.
- **Assumptions:** runner uids 61001 (`runner`) and 61002 (`runner-pkg`) are free on the deployment host (checked at deploy with `getent passwd`); the host key file stays world-readable or becomes root-owned; the memory cgroup (`CODE_RUNNER_MEMORY_LIMIT`) also bounds the tmpfs scratch, so `/tmp` keeps the evidenced 512 MB size (tmpfs only consumes what is used; the Go build used about 35 MB) and the interaction with the memory limit is re-checked in Step 8.

#### Approach
Three ordered PRs from `develop`, each leaving a working runtime: **A (Steps 1-7)** the whole privilege model (image, compose, spawn, helper-made sandboxes, verified cleanup, installs, key, docs and the docker.md exception, container check script), verified live in Step 8 before it merges; **B (Step 9)** the health gate; **C (Step 10)** the full gate and wrap-up. The server runs as root with `SETUID`, `SETGID`, `KILL` only, `no-new-privileges`, `init`, `read_only`. A new `code_runner_mcp/sandbox_user.py` owns uids, the `prlimit` wrapper and the child environment; a new `code_runner_mcp/runner_helper.py` runs as the runner uid for `make_sandbox`, `remove_sandbox` and `clean_uid`. Sandbox rule (from the evidence): the helper creates each run directory owned by the runner uid with mode **0755** and the entry and project files **0644**, so the root server can traverse it and read the entry file (`os.path.exists`, the SQL read) without `DAC_OVERRIDE`; the server never removes or reads inside anything user code may have made 0700, and every `shutil.rmtree` of a sandbox is replaced by the helper. The existing `RUN_LOCK`, `clear_scratch()` (same name and "failed paths" return), `kill_group` and the bounded waits are kept so `server.py`, the app and the tests need no new wiring. Dev/test escape: `CODE_RUNNER_ALLOW_UNPRIVILEGED=1` is honoured only for a non-root process (tests); a root server always switches uid and refuses to start if the flag is also set; a non-root server without the flag refuses to start. Rejected: per-user runtimes (not needed for the evidenced residuals), `preexec_fn` limits (break for host-shared uids), server-side `rmtree` of runner-owned trees (EACCES).

#### Out of scope
App-side changes (`run_slot`, `code_executor.py`), the relay and `pkg-proxy` images, seccomp/AppArmor profile changes, user namespaces, a new `RLIMIT_AS` limit (memory stays in the cgroup), per-user runtimes, deploying to the production stack (a separate step after merge).

#### Steps
##### Step 1: Image users and layout (PR A)
- **Status:** todo
- **Depends on:** none
- **Files:** `docker/Dockerfile.code-runner` (modify).
- **Change:** create `runner` (uid/gid 61001) and `runner-pkg` (61002) with `useradd -M`, shell `nologin`, no home for `runner`; create `/opt/runner` (owner `root`, 0755), `/opt/runner/python` and `/opt/runner/node` (owner `runner-pkg`, 0755) and `/opt/runner/pkg-home` (owner `runner-pkg`, 0700); drop `USER runner` (the server runs as root; comment why); keep the toolchain layers and manifest-first caching; `/tmp/sandbox` is created by the server at startup (an image-time directory would be hidden by the tmpfs).
- **Verification:** `docker build` under the unique tag `my-ai-verify-runner`; `docker run --rm --entrypoint id my-ai-verify-runner runner` prints uid 61001, `runner-pkg` 61002; `ls -ld /opt/runner /opt/runner/*` shows the owners and modes.

##### Step 2: Compose hardening of the runtime (PR A)
- **Status:** todo
- **Depends on:** 1
- **Files:** `docker/docker-compose.yml` (modify `code_runner_runtime`).
- **Change:** `user: "0:0"`, `read_only: true`, `init: true`, `cap_drop: [ALL]`, `cap_add: [SETUID, SETGID, KILL]`, `security_opt: ["no-new-privileges:true"]`, `pids_limit: 512`; `tmpfs`: `/tmp:exec,size=512m,mode=1777`, `/var/tmp:size=16m,mode=1777`, `/dev/shm:size=16m,mode=1777`, `/run/keys:size=1m,mode=0700`; the secret in long syntax (`source: CODE_RUNNER_API_KEY`, `target: /run/keys/CODE_RUNNER_API_KEY`) and `API_KEY_FILE=/run/keys/CODE_RUNNER_API_KEY`; keep the memory/CPU limits, the proxy env vars, the `../code_runner_mcp:/app:ro` mount and the healthcheck. Comment each setting with the evidence it comes from.
- **Verification:** `docker compose -f docker/docker-compose.yml config -q` passes and the rendered config shows each setting on `code_runner_runtime` and no change on any other service (checked by diffing the rendered `config` output before and after); the live capability and mount checks run in Step 8.

##### Step 3: Uid, limits and environment module (PR A)
- **Status:** todo
- **Depends on:** 1
- **Files:** `code_runner_mcp/sandbox_user.py` (create); `code_runner_mcp/tests/test_sandbox_user.py` (create).
- **Change:** constants and env overrides for the runner and runner-pkg uid/gid (defaults 61001/61002) and `CODE_RUNNER_ALLOW_UNPRIVILEGED`; `check_privilege()` (root with CapEff SETUID/SETGID/KILL and the flag unset, or non-root with the flag set; every other combination, including root with the flag, raises so the service refuses to start, with a clear message); `spawn_kwargs(kind)` returning `user=`, `group=`, `extra_groups=[]`, `start_new_session=True` (nothing but `start_new_session` under the dev flag); `limited(argv)` prepending `prlimit` with named `--nproc`/`--nofile` constants and never `--as`; `run_env(sandbox_dir)` (`PATH`, `HOME`/`TMPDIR` inside the sandbox, `PYTHONPATH=/opt/runner/python`, `NODE_PATH=/opt/runner/node/node_modules`, `LANG`, `PYTHONUNBUFFERED`) replacing the dict built in `CodeExecutor.prepare_sandbox`; `pkg_env(manager)` (pip: `PATH` plus the `PIP_*` vars; npm: `HOME=/opt/runner/pkg-home`, `npm_config_cache` there, plus the `npm_config_*` vars).
- **Verification:** unit tests run from `code_runner_mcp/` with `PYTHONPATH=.` and the code-runner venv (`CR_PY=venv/bin/python` per AGENTS.md; it must have `code_runner_mcp/requirements.txt`, `httpx` and `pytest` installed, as `docs/standards/testing.md` runs these tests with it. In a checkout whose `venv` lacks `fastapi` (installing it upgrades Starlette and breaks the pinned `playwright_mcp` tests, `docs/pitfalls.md`), set `CR_PY=~/.cache/myai-venv-cr/bin/python` (a virtualenv created with `python3 -m venv ~/.cache/myai-venv-cr && ~/.cache/myai-venv-cr/bin/pip install -r code_runner_mcp/requirements.txt httpx pytest`, justified by the `docs/pitfalls.md` entry that MCP service tests need their own dependencies) and say so in the PR): kwargs per kind, `limited()` never contains `--as`, `check_privilege(euid=None, cap_eff=None)` takes the effective uid and the `CapEff` mask as injectable arguments (defaulting to `os.geteuid()` and `/proc/self/status`) so the root cases run without being root; it raises as non-root without the flag, passes as non-root with it, and raises as root with the flag set (user code can never run as root through the flag), env contents; `cd code_runner_mcp && PYTHONPATH=. $CR_PY -m pytest tests/test_sandbox_user.py`.

##### Step 4: Helper-made sandboxes and verified cleanup (PR A)
- **Status:** todo
- **Depends on:** 3
- **Files:** `code_runner_mcp/runner_helper.py` (create: `make_sandbox`, `remove_sandbox`, `clean_uid`, run as `python3 runner_helper.py <cmd>` under the runner uid); `code_runner_mcp/executor.py` (modify `prepare_sandbox`, `clear_scratch`, `scratch_roots`, the `shutil.rmtree(sandbox_dir)` calls in `_execute` and its `finally`, add `verify_clean`); `code_runner_mcp/server.py` (modify the sandbox creation, the SQL read and the `shutil.rmtree` calls in `execute_ws`'s `finish()` and outer `finally`); tests `code_runner_mcp/tests/test_runner_helper.py` (create), `test_executor.py`, `test_server.py` (modify).
- **Change:** the server creates `SANDBOX_BASE` (1777) at startup. `prepare_sandbox` sends the already validated file list (traversal checks stay in the server) to `make_sandbox`, which creates the per-run directory and every subdirectory for nested `files` with an explicit mode 0755 (owner runner uid; `home/` and `tmp/` 0700) and writes each file with an explicit 0644 (`os.open` modes, not the umask); the server's `os.path.exists(entry)` and SQL read work because root can traverse 0755 and read 0644, and they happen only before the first user process of that run starts (the runner owns those files, so a later symlink swap is never followed by root). Every server-side `shutil.rmtree(sandbox_dir)` becomes `remove_sandbox` through the helper (a failure is reported like any cleanup failure). `clear_scratch()` (same name, same failed-paths return) runs `clean_uid` as the runner uid (`os.kill(-1, SIGKILL)` for the uid, `ipcrm` of SysV shm/sem/msg, removal of the uid's entries in `SCRATCH_ROOTS`, `/dev/mqueue` and `SANDBOX_BASE`, restoring owner rwx on every directory (a `chmod` walk) before removing it so a user-made 0555 or 0000 tree cannot wedge cleanup, bounded by a timeout), then `verify_clean()` as the server (no `ipcs` object owned by the runner uid, no process of the uid in `/proc`, nothing left in `/dev/mqueue`, and any entry in the scratch roots or `SANDBOX_BASE` owned by the runner uid counts as a failure even when its contents cannot be listed). Pre/post-run calls and the `RUN_LOCK` wiring stay.
- **Verification:** unit tests of the pure parts (command construction, `verify_clean` parsing including the owned-but-unlistable case, path validation, explicit modes of created directories and files, the chmod-before-remove walk on a 0555 tree, "the server never reads inside a 0700 tree": the entry-file and SQL reads happen on 0644 files in a 0755 directory) with injected roots under `tmp_path` and a fake helper under the dev flag; the real uid switch is covered in Step 8. Existing cleanup tests keep passing.

##### Step 5: Spawn as the runner uid and install as runner-pkg (PR A)
- **Status:** todo
- **Depends on:** 4
- **Files:** `code_runner_mcp/executor.py` (modify `_run_in_group`, remove the env dict), `code_runner_mcp/server.py` (modify the three `asyncio.create_subprocess_exec` calls in `execute_ws` (compile, run, sql), `/install`, `/packages`, `load_api_key` error text, startup `check_privilege()`), tests `test_executor.py`, `test_server.py`, `conftest.py` (modify: set the dev flag before import), `code_runner_mcp/README.md` is edited in Step 6.
- **Change:** every user-code subprocess (compile, run, sql, WebSocket compile, run and sql) uses `spawn_kwargs("runner")`, `limited()` and `run_env()`. `/install` takes `RUN_LOCK`, runs as `runner-pkg` (`spawn_kwargs("pkg")`, `pkg_env`) with pip `--target /opt/runner/python --no-cache-dir` and npm `--prefix /opt/runner/node` (no `--user`, no `/home/runner`), then kills the pkg uid's processes; `/packages` lists from those trees (`pip list --path /opt/runner/python`, `npm list --prefix /opt/runner/node`) through `spawn_kwargs("pkg")` and `pkg_env`, so no subprocess the server starts for user-visible work runs as root; `load_api_key` keeps `API_KEY_FILE` and on `PermissionError` raises a message that the host key file must be readable by root (mode 644 or root-owned) because the server runs without `CAP_DAC_OVERRIDE`.
- **Verification:** existing code-runner suite green under the dev flag (`cd code_runner_mcp && PYTHONPATH=. $CR_PY -m pytest`); new tests assert the spawn kwargs and env (mocked `Popen`/`create_subprocess_exec`), the install argv/env/cwd/locking and the `PermissionError` message; `venv/bin/ruff check .` from the repo root.

##### Step 6: Docs and the documented exception (PR A)
- **Status:** todo
- **Depends on:** 5
- **Files:** `docs/standards/docker.md`, `docs/standards/security.md`, `docs/pitfalls.md`, `code_runner_mcp/README.md` (modify); `docker/docker-compose.yml` (comments).
- **Change:** `docker.md` gets an "Exception: code_runner_runtime" paragraph under the non-root rule (the server runs as root with only SETUID/SETGID/KILL, `no-new-privileges`, `init`, `read_only`, and drops every user-code process to a dedicated uid; approved by the user 2026-11-10; no other service may copy it); `security.md` "Tools and sandboxing" replaces the bounded-clean-up/residuals paragraph with the new model and the remaining residuals (shared kernel, no seccomp change, the host key-file mode requirement); `pitfalls.md` entries: `RLIMIT_NPROC` counts host-wide per uid, Docker tmpfs is `noexec` by default, compose ignores `uid/gid/mode` for file secrets, root without `DAC_OVERRIDE` cannot read or clear another uid's 0700 trees or IPC; `code_runner_mcp/README.md`: the file table (`sandbox_user.py`, `runner_helper.py`), the `server.py` row (it also refuses to start without the privilege check, not only without an API key), the line saying the runtime's `CODE_RUNNER_API_KEY` is readable by user code (now false), the line saying `/install` does not take the lock, the `setsid`/other-paths residual sentences, and the flow text about `HOME`/`TMPDIR`, installs and cleanup.
- **Verification:** `venv/bin/python -m pytest tests` (doc budgets and links); `grep -rn "home/runner\|pip install --user\|does not take the lock\|readable by user code" docs code_runner_mcp/README.md` finds nothing stale.

##### Step 7: Container check script (PR A)
- **Status:** todo
- **Depends on:** 5
- **Files:** `code_runner_mcp/tests/container_check.py` (create: a script run inside a built container, not collected by pytest because it is named without the `test_` prefix and guarded by `if __name__ == "__main__"`), `code_runner_mcp/tests/test_container_check.py` (create), `code_runner_mcp/README.md` (usage line).
- **Change:** scenarios from the evidence, each printing one PASS/FAIL line: all 11 languages run; the child runs as uid 61001 with `CapEff` 0; a `setsid` escapee, SysV shm/sem/msg, `/dev/shm` and `/dev/mqueue` leftovers are gone before the next run and `ipcs` is empty; writes to `/opt/runner/*`, `/app` and `/run/keys` are refused; the key and `/proc/<server>/environ` are unreadable; `kill` and `ptrace` on the server are refused; two simultaneous runs serialise; `RLIMIT_NPROC` 64 does not break forks; a Go build fits the `/tmp` size; pip and npm installs through `pkg-proxy` succeed and the packages import for user code but cannot be modified by it.
- **Verification:** `code_runner_mcp/tests/test_container_check.py` (create) imports the module and asserts the scenario table (names, one entry per evidenced scenario, no scenario that needs root at import time), which satisfies the one-test-file-per-module rule without running containers; the script itself is exercised live in Step 8; `venv/bin/ruff check .` covers both.

##### Step 8: Live verification of PR A (before it merges)
- **Status:** todo
- **Depends on:** 6, 7
- **Files:** a verification compose file in `~/.claude/tickets/My-AI/MYAI-47-evidence/impl/` (not committed).
- **Change:** build the runtime and a `pkg-proxy` copy under unique names (`my-ai-verify-runner`, `my-ai-verify-pkg-proxy`, project `my-ai-verify-iso`, own networks) with the fixed bridge name overridden: the `pkg-egress` network's `com.docker.network.bridge.name` (`docker/docker-compose.yml`, `myai-pkg-egress`, which says a second copy must override it) is set to a different name, so the copy does not exercise the optional host `DOCKER-USER` rule that matches the production name; never use the production container, network or bridge names. Mount the throwaway key file with mode 644. Run `container_check.py` inside the runtime container and record the outputs and timings. Also confirm `CapEff 00000000000000e0`, the read-only root and the tmpfs mounts, and that Java, Go and Node run under the 512 MB cgroup with the 512 MB `/tmp`.
- **Verification:** every scenario passes; evidence is saved under `.../MYAI-47-evidence/impl/`; teardown (`docker compose -p my-ai-verify-iso down -v --rmi local`, image and network removal) leaves nothing named `my-ai-verify*` (`docker ps -a`, `image ls`, `volume ls`, `network ls`) and the production containers are unchanged.

##### Step 9: Health gate (PR B)
- **Status:** todo
- **Depends on:** 8
- **Files:** `code_runner_mcp/executor.py` (a `TAINTED` flag set by a failed cleanup, cleared by the next successful one), `code_runner_mcp/server.py` (`/health`), `code_runner_mcp/tests/test_executor.py`, `test_server.py` (modify), `code_runner_mcp/tests/container_check.py` (add the forced-failure scenario), `code_runner_mcp/README.md` (modify).
- **Change:** `/health` answers 503 `{"status": "tainted"}` while tainted (200 `ok` with the same language list otherwise); runs are refused with `Runner cleanup failed.` as today; the compose healthcheck already calls `/health`, so the container shows `unhealthy`.
- **Verification:** unit tests (a failed post-run clear taints, a later success clears it, `/health` status codes); a forced failure in a uniquely named container (same teardown rules as Step 8) turns `docker inspect` health to `unhealthy` and back after a successful run.

##### Step 10: Full gate (PR C)
- **Status:** todo
- **Depends on:** 9
- **Files:** none.
- **Change:** none.
- **Verification:** env from `docs/standards/testing.md`: `venv/bin/python -m pytest backend tests` (baseline failures only), `cd code_runner_mcp && PYTHONPATH=. $CR_PY -m pytest`, `scripts/check.sh --python-only`, `venv/bin/ruff check .`, `docker compose -f docker/docker-compose.yml config -q`; each PR comes from a `feature/<topic>` branch off `develop` with the PR into `develop` (`docs/standards/gitflow.md`).

#### Tests
Unit: `test_sandbox_user.py`, `test_runner_helper.py`, extended `test_executor.py`/`test_server.py` (injected roots, mocked spawn, the dev flag), run from `code_runner_mcp/` with `$CR_PY`. Container-level: `tests/container_check.py` (Steps 7-9). No GitHub Actions; checks run locally.

#### Risks and open questions
- **tmpfs counts against the memory cgroup:** a 512 MB `/tmp` inside a 512 MB limit can starve a run if filled; the evidence ran it that way with a 35 MB Go build; Step 8 re-checks, and the mitigation is a higher memory limit, not a smaller tmpfs.
- **Host key file mode:** if the file becomes `0600` owned by a host uid, root (no `DAC_OVERRIDE`) cannot read it and the service refuses to start (clear message, Step 5).
- **Uid collision:** 61001/61002 must be unused on the host (checked at deploy with `getent passwd`); they are Dockerfile args and env overrides.
- **Cleanup helper cost:** about 28 ms median measured; a hung helper is bounded by a timeout and counts as a cleanup failure.
- **Open for deploy time (not this plan):** rebuilding and restarting `code_runner_runtime` on the production stack.

#### Success criteria
- [ ] User code runs as uid 61001 with no capabilities; the server holds only SETUID, SETGID, KILL, with `no-new-privileges`, `init` and a read-only root filesystem.
- [ ] After each run no process, SysV IPC object or scratch file of the run's uid survives, verified by the server; a failed clean-up refuses the next run and fails `/health`.
- [ ] User code cannot read the API key or the server's environment, cannot signal or ptrace the server, and cannot write `/opt/runner`, `/app` or any persistent path.
- [ ] Installs run as `runner-pkg` into `/opt/runner/{python,node}` and the packages import for user code.
- [ ] The `docs/standards/docker.md` exception, security docs, pitfalls and component README match the code.
- [ ] Unit suites and `ruff check .` pass; the container check script passes in a uniquely named build, and nothing named `my-ai-verify*` is left afterwards.

#### Reviewer brief
- **Objective:** run user code in the real code runtime as a dedicated non-host uid, with the server as root holding only SETUID/SETGID/KILL, a read-only root filesystem, verified per-run cleanup, a health gate, installs as a separate uid and the API key in a root-only tmpfs directory.
- **Key decisions:** three ordered PRs (A: the whole privilege model, verified live before merge; B: health gate; C: full gate); new `sandbox_user.py` (uids, `prlimit` wrapper never touching `RLIMIT_AS`, env) and `runner_helper.py` (create, remove and clean as the runner uid; sandboxes 0755 with 0644 files so the root server can read the entry file); `clear_scratch()`/`RUN_LOCK`/`kill_group` keep their names; an unprivileged dev flag only for tests; NPROC set after the uid switch; runner uids 61001/61002; tmpfs `/tmp` exec 512 MB; the docker.md exception lands in PR A.
- **Out of scope:** app changes, relay and `pkg-proxy` images, seccomp changes, user namespaces, per-user runtimes, production deploy.
- **Success criteria:** as listed in the plan.

The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

#### Validation log
- **Round 1:** validator FAIL (5 BLOCKING, 5 MINOR). My judgement: FAIL, all valid. Fixed: server reads and `rmtree` inside runner-owned 0700 trees (sandboxes are now helper-made 0755/0644, removal through the helper); PR A alone would break the runtime (sandbox creation, `/install`, read-only paths): the plan was regrouped so PR A holds the whole privilege model (Steps 1-7) with live verification (Step 8) before it merges; the verification stack must override the fixed `pkg-egress` bridge name; the interpreter wording and placeholders; stale README lines listed. MINOR fixed: `/opt/runner` owner, the three `create_subprocess_exec` calls, Step 2 verification not depending on PR C, the docker.md exception moved into PR A, tmpfs back to the evidenced 512 MB.
- **Round 2 (diff-scoped):** validator FAIL (2 BLOCKING, 8 MINOR). My judgement: FAIL. Item 1 (use `venv/bin/python`) was partly disproved: the main checkout's venv has fastapi but this worktree's venv does not (installing it upgrades Starlette and breaks the pinned playwright tests), so the plan now uses `venv/bin/python` with a documented fallback; item 2 valid: the dev flag is honoured only for non-root and root plus flag refuses to start (with a unit test). All MINOR fixed: garbled brief fragment and truncated Assumptions bullet repaired, bridge-name wording, chmod-walk before removing user-made non-writable trees, explicit 0755/0644 modes and read-only-before-user-code rule, `verify_clean` covers `/dev/mqueue` and runner-owned unlistable entries, `test_container_check.py` added, README server.py row.
- **Round 3 (diff-scoped):** validator PASS (0 BLOCKING, 3 MINOR). My judgement: PASS. MINOR fixed inline (mechanical): a concrete `CR_PY` fallback path citing `docs/pitfalls.md`; the injectable `euid`/`cap_eff` arguments of `check_privilege()`; `/packages` through `spawn_kwargs("pkg")`.


## Implementation notes
### Autopilot run (2026-11-09)
batch-autopilot item 13/13; branch feature/runner-per-user-isolation (base feature/multi-user-browser-profiles-portal, no repo changes expected: this is a spike, evidence only). Deviations from the plan, all to keep the real running stack untouched: no spike worktree or branch (no repo code is changed; the helpers live in the evidence folder); the spike image layers on the already built `my-ai-code-runner:latest` instead of rebuilding the toolchains (same Java, Go, Node, Python); experiments are driven by harness scripts run as the root "server" inside one container with only SETUID, SETGID and KILL, instead of modifying `executor.py`/`server.py`. Step 4 needs the user's decision and the `docker.md` exception: the run stops there.

### Baseline (2026-11-09)
Not applicable (no repo code or tests change). Real stack running (my-ai-app-1, code_runner_mcp, ...): not touched; spike names are `my-ai-spike*`.

### Implementation progress
- [x] Step 1: Prototype image and stack - `MYAI-47-evidence/compose.spike.yml` + `Dockerfile.spike` (layered on the built runtime image; project `my-ai-spike`, container `my-ai-spike-runtime`, no host ports, own network); caps SETUID/SETGID/KILL only (`CapEff 0xe0`), no-new-privileges, init, read_only, tmpfs scratch. No repo code changed (the helpers are harness scripts), so there is no spike worktree or branch.
- [x] Step 2: Open questions - all seven answered with commands, outputs and timings in `MYAI-47-evidence/answers.md` and `out/`.
- [x] Step 3: Residuals - all five checked on the prototype (table in `answers.md`).
- [ ] Step 4: Decision - NOT done: it needs the user's decision and approval of the `docs/standards/docker.md` exception (AGENTS.md rule 7). Recommendation recorded below.
- [ ] Step 5: Plan or tickets - blocked on Step 4. The spike containers, image and network are torn down; evidence stays.

### Decision (2026-11-10)
**User decision: adopt the recommendation as written, including the documented exception to `docs/standards/docker.md`** (the runtime server runs as root with only SETUID, SETGID and KILL, `no-new-privileges`, `init`, `read_only: true`; user code runs as dedicated non-host uids). Approved by the user on 2026-11-10 after seeing `MYAI-47-evidence/answers.md`. Step 4 done. Step 5: the implementation plan follows as a dated amendment below.

Recommendation as evidenced (pending-answer text kept for the record):
Recommendation from the evidence (details: `MYAI-47-evidence/answers.md`): adopt split uids with named changes: root server with only SETUID/SETGID/KILL, `no-new-privileges`, `init`, `read_only: true` rootfs, tmpfs scratch (`/tmp` exec, about 512 MB), dedicated high uids (not real host uids) for `runner` and `runner-pkg`, the API key in a root-only tmpfs directory, children started with `subprocess(user=...)` plus a `prlimit` wrapper, and a runner-uid cleanup helper after each run (28 ms median). All five MYAI-39 residuals closed on the prototype. Needs: the user's choice (adopt, adopt with changes, or another model) and approval of the docker.md exception.


### Implementation (2026-11-10, autopilot)
Implemented from the validated implementation plan above, in two PRs: PR A https://github.com/archit342000/My-AI/pull/98 (branch feature/runner-split-uid-isolation, base develop: Steps 1-7, docs, container check) and PR B https://github.com/archit342000/My-AI/pull/99 (branch feature/runner-health-gate, base PR A: Step 9). Step 8 (live verification) done before opening PR A: `impl/check6.txt` (9 scenarios PASS), `impl/ws.txt`; the verification stack `my-ai-verify-iso` was built under unique names and torn down (nothing named `my-ai-verify-runner|pkg-proxy|iso` left, production untouched). Step 10: code_runner_mcp 293/296 passed, `pytest tests` 66, ruff clean, backend+tests baseline 10 failures only. Deviations: PR C was not needed (it only held the full gate); the live forced-cleanup-failure check for the health gate is unit-tested only; `/opt/runner` needed a named volume (`runner_packages`) because the root filesystem is read-only (found live); package children start in `/opt/runner` (chdir happens before the uid switch, found live). Reviews: Haiku, 3 reviewers on PR A (findings fixed: entry_file escape, uid env validation, exact capability check, cleanup/lock cancellation window, /packages lock, real-/dev/mqueue test touch, vacuous tests, docs); deferred/accepted: PR B reviewed by tests only. Merge order: #98 then #99 (retarget #99 to develop first).
PR: https://github.com/archit342000/My-AI/pull/98, branch feature/runner-split-uid-isolation, base develop (health gate: #99 on top)

## Verification

## Review history

## Log
- 2026-11-09: created (split from MYAI-39 by user decision)
- 2026-11-09: linked split_from MYAI-39 (user decision: stronger runner isolation as a hands-on spike)
- 2026-11-09: linked blocked_by MYAI-39 (builds on the serialised runner)
- 2026-11-09: linked relates_to MYAI-32 (decision 3)
- 2026-11-09: linked relates_to MYAI-1 (runner key residual)
- 2026-11-09: plan validated, 3 rounds
- 2026-11-09 batch-autopilot: stopped at Step 4 (decision): Steps 1-3 done with evidence (MYAI-47-evidence/answers.md); needs the user's decision and the docker.md exception approval. No repo changes, no PR. Spike containers, image and network removed.
- 2026-11-10: decision recorded: adopt split uids as recommended; docker.md exception approved by the user (Step 4 done)
- 2026-11-10: implementation plan (amendment) validated, 3 rounds; split into PR A (Steps 1-7, live Step 8), PR B (Step 9), PR C (Step 10)
- 2026-11-10: autopilot: implemented; PR #98 (isolation) and #99 (health gate) open; live check passed; ticket left in-progress
- 2026-11-10: closed: PRs #98 (isolation), #99 (health gate), #100 merged and deployed; code execution and portal confirmed live
