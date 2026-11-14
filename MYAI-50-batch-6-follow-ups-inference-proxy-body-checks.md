---
id: MYAI-50
title: "Batch 6 follow-ups: inference_proxy JSON body checks, tavily path guard"
status: todo
created: 2026-11-09
updated: 2026-11-09
links:
  relates_to: [MYAI-18, MYAI-22]
---

## Description
Items found in review of the merged batch 6 PRs (#72, #73) that the validated plans did not cover.

1. **inference_proxy JSON bodies (from MYAI-22).** `inference_proxy/router.py` (lines around 49, 83, 112, 171, 207) still reads `data = request.json or {}`, so a missing, malformed or non-object body gives Flask's HTML 400/415 or a 500 instead of `{"error": ...}` 400. It is a separate service, so it cannot import `backend/utils.read_json_object`; decide between a local copy and a shared module. Same acceptance as the backend routers (docs/standards/api.md).
2. **tavily_mcp protected paths (from MYAI-18).** `AuthMiddleware` guards a literal list (`/sse`, `/messages/...`). `/messages` and `/sse/` skip it and only reach Starlette's redirect to the protected route (no bypass today), and a changed mount path would silently leave routes unguarded. Fix idea: derive the paths from the app settings, or protect everything except an allowlist such as `/health`; add tests for `/messages`, `/sse/` and `//`-prefixed paths.

## Acceptance criteria
- [ ] inference_proxy routes return 400 `{"error": ...}` for a missing, malformed or non-object JSON body, with tests
- [ ] The tavily_mcp guard covers every MCP route without a hard-coded path list (or the list is derived from the app), with path-variant tests

## Plan

## Implementation notes

## Verification

## Review history

## Log
- 2026-11-09: created from the review of PRs #72 and #73 (user asked for follow-ups for anything not in the plans)
