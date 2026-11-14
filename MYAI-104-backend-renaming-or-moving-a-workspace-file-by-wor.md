---
id: MYAI-104
title: "Backend: renaming or moving a workspace file by workspace_id answers 500"
status: todo
created: 2026-11-14
updated: 2026-11-14
links:
  relates_to: [MYAI-102, MYAI-95]
---

## Description
Found while verifying MYAI-102. `PATCH /api/file_systems/<id>` with only `workspace_id` (a title or folder change) answers 500: `update_file_system_metadata` / `resolve_owner_and_physical_path` raises `The 'workspace/' directory is reserved...` because the stored workspace file path starts with `workspace/` and no chat is given. Until it is fixed the Rename or move dialog cannot work on a workspace page. Reproduce: create a workspace file, PATCH it with `{workspace_id, title}`.

## Acceptance criteria
- [ ] Renaming and moving a workspace file by `workspace_id` works and keeps the file under the workspace
- [ ] Tests cover rename, move into a folder and a missing file for the workspace scope
- [ ] `docs/standards/api.md` notes the workspace form of the route if it changes

## Plan

## Implementation notes

## Verification

## Review history

## Log
- 2026-11-14: created from the follow-ups of the batch run for MYAI-94 to MYAI-103
