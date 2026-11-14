---
id: MYAI-113
title: "Frontend: use the content search route in the Files panel"
status: todo
created: 2026-11-14
updated: 2026-11-14
links:
  relates_to: [MYAI-94]
---

## Description
`GET /api/file_systems/search` searches the contents of every file in a chat or workspace and returns file id, path, line number and line (`artifactsApi.search` already exists). Use it in the Files panel search (`features/artifacts/FileBrowser.tsx`, `file-search.ts`) instead of searching only names and already-loaded contents, show the matching line, and show a note when the result is truncated. Debounce the query.

## Acceptance criteria
- [ ] Searching finds text inside files that were never opened and shows the matching line
- [ ] A truncated result says so
- [ ] Empty and failing searches are handled
- [ ] Unit tests cover hits, no hits and truncation

## Plan

## Implementation notes

## Verification

## Review history

## Log
- 2026-11-14: created from the follow-ups of the batch run for MYAI-94 to MYAI-103
