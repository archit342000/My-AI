---
id: MYAI-114
title: "Frontend: bounded Stop and docs"
status: todo
created: 2026-11-14
updated: 2026-11-14
links:
  relates_to: [MYAI-96]
---

## Description
Left over from MYAI-96 item 8: `POST /api/chats/<id>/stop` already waits for the worker (at most `TASK_STOP_WAIT_SECONDS`) and answers `"stopped": false` if it is still alive, but `docs/frontend.md` still says the server only signals the old worker and the client retries a refused send after a stop instead of using `stopped`. Make the client use `stopped` and update the docs.

## Acceptance criteria
- [ ] The client waits or reports using the `stopped` field instead of retrying a refused send
- [ ] `docs/frontend.md` matches the server behaviour
- [ ] Tests cover stopped true and false

## Plan

## Implementation notes

## Verification

## Review history

## Log
- 2026-11-14: created from the follow-ups of the batch run for MYAI-94 to MYAI-103
