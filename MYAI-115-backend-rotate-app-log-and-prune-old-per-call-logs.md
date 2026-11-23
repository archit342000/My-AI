---
id: MYAI-115
title: "Backend: rotate app.log and prune old per-call logs"
status: todo
created: 2026-11-23
updated: 2026-11-23
---

## Description
`backend/logging/logger.py` on `develop` writes `logs/app.log` through a plain `logging.FileHandler`. It also writes one file per LLM, tool and embedding call under `logs/llm_calls/`, `logs/tool_calls/` and `logs/general/`, plus append-only index files. Nothing is ever rotated or deleted, so the logs grow without bound.

The old v3 logger solved this before the React rewrite replaced it. That code was never pushed and survives only in commit `a6232a2` ("feat(logger): rotate app.log and prune old logs on startup") on the local backup branch `backup/v3-local-2026-11-08` in the owner's laptop checkout. It used:
- a `RotatingFileHandler` for `app.log`, capped at `APP_LOG_MAX_BYTES` (default 10 MB);
- `prune_old_logs()` at startup, deleting per-call log files older than `LOG_RETENTION_DAYS` (default 14; `0` disables pruning).

Reimplement this for the new logger. Don't cherry-pick: the logger was rewritten.

## Acceptance criteria
- [ ] `app.log` rotates at a configurable size with a bounded number of backups.
- [ ] Per-call log files older than a configurable number of days are deleted at startup; `0` disables it.
- [ ] Index files stay consistent with the remaining files (pruned or rebuilt), or the chosen behaviour is documented.
- [ ] The `/logs` UI still works after rotation and pruning.
- [ ] The new settings are documented, with tests for rotation and pruning.

## Plan

## Implementation notes

## Verification

## Review history

## Log
- 2026-11-23: created (from the review of unpushed local v3 commits)
