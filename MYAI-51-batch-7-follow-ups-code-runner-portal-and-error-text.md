---
id: MYAI-51
title: "Batch 7 follow-ups: dockerignore secrets, package-list drift, install pre-validation, error-text leftovers"
status: todo
created: 2026-11-09
updated: 2026-11-09
---

## Description
Items found in the reviews of the batch 7 PRs (#74 to #83) that the validated plans did not cover. Each is small and independent; they can be split when planned.

1. **`.dockerignore` lacks `secrets/` and `.env*` (from MYAI-16, R1-3).** `docs/standards/security.md` says they are ignored, but `.dockerignore` does not list them, and the pkg-proxy and code-runner builds use context `..` (the repo root), so the secrets directory is sent to the builder. The images are clean (the Dockerfiles only COPY what they need). Fix the file or the standard, and check every Dockerfile's COPY lines.
2. **Package list duplicated (from MYAI-16, R1-10).** The baked package list appears in the `install_packages` description (`backend/tools/catalog/code.py`) and in `code_runner_mcp/requirements-sandbox.txt`; nothing checks that they match. Add a test that compares the names, or build the description from one source.
3. **`install_packages` approval shows unvalidated specs (from MYAI-4, R1-8, R1-9).** The user approves raw specs before the runner validates them (no backend pre-validation), and a runner 422 is reported as "service unavailable" (only 400 is mapped).
4. **`run_file` failure statuses (from MYAI-5, R1-4).** Only a missing file is a 404; an unsupported extension or an unavailable runner still returns 200 with an error string. Also `backend/tools/implementations/README.md` does not list `code_executor.py`.
5. **`proxy_portal_init` error text (from MYAI-3).** It still returns `resp.text` / `str(e)` on non-401 errors; use fixed messages with the detail in `log_event`.
6. **Live-run outer error path sends no exit frame (from MYAI-23, R1-2).** The prepare path sends one; the outer path never did. The frontend may wait for it.
7. **Resolver exception type (from MYAI-26, R1-2).** `run_file`/`run_code` map any `ValueError` to the resolver's text; a dedicated resolver exception would avoid returning an unrelated `ValueError`'s message.
8. **x11vnc is passwordless inside the container (from MYAI-2, R1-3).** Documented as an accepted residual (processes in the container can reach it); a generated `-rfbauth` password would close it.
9. **pkg-proxy egress is limited only by nginx (from MYAI-16).** The network (`pkg-egress`) is a normal bridge; the optional host `DOCKER-USER` rule is documented but not applied or tested. Decide whether to ship and verify the rule.
10. **Two timeout ceilings (from MYAI-28 R1-1 and MYAI-17).** `CODE_RUNNER_MAX_TIMEOUT` (default 120) and the runtime's fixed 580 differ, and the relay's 600 s idle timeout depends on the code_runner_timeout staying below it; align or document them in one place.

## Acceptance criteria
- [ ] `secrets/` and `.env*` are in `.dockerignore` (or the standard is corrected), with a check
- [ ] A test fails when the install_packages description and `requirements-sandbox.txt` disagree
- [ ] A bad package spec or a runner 422 gives a clear error to the user
- [ ] `run_file` returns a proper status for unsupported extensions and an unavailable runner, with tests
- [ ] `proxy_portal_init` and the live-run outer path return fixed messages and an exit frame, with tests
- [ ] The resolver raises its own exception type
- [ ] A decision is recorded for the x11vnc password and the DOCKER-USER rule
- [ ] The timeout ceilings are aligned or documented once

## Plan

## Implementation notes

## Verification

## Review history

## Log
- 2026-11-09: created from the review findings of batch 7 (user asked for follow-ups for anything not in the plans)
