---
id: MYAI-112
title: "Frontend: Run and Version history in the workspace scope"
status: todo
created: 2026-11-14
updated: 2026-11-14
links:
  relates_to: [MYAI-95]
---

## Description
The server now accepts `workspace_id` for run-file and the version routes (list, single version, current, diff, restore). Switch the buttons on for the workspace scope in `features/artifacts/FileBrowser.tsx` (remove the `if (!scope.chatId) return;` guard in `runFile` and the disabled-state text on the workspace page). A run of dangerous code in a workspace is refused with a message asking to run it from a chat; show it as a failed run. Depends on the workspace rename fix only for the rename dialog, not for this.

## Acceptance criteria
- [ ] Run works for a workspace file and shows the output or the refusal
- [ ] Version history lists, compares and restores for a workspace file
- [ ] Unit tests cover the workspace scope

## Plan

## Implementation notes

## Verification

## Review history

## Log
- 2026-11-14: created from the follow-ups of the batch run for MYAI-94 to MYAI-103
