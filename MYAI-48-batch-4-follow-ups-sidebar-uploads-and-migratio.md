---
id: MYAI-48
title: "Batch 4 follow-ups: abandoned uploads, AUTOINCREMENT reset, legacy UI refresh"
status: todo
created: 2026-11-09
updated: 2026-11-09
links:
  relates_to: [MYAI-8, MYAI-31]
---

## Description
Open items left by the merged batch 4 PRs (#63 to #66), found in review and verification.

1. **Abandoned uploads keep a listed chat (from the empty-chat list change).** The upload route creates the chat row, and a chat with a file counts as content. If the composer unmounts before sending (navigating between the home and chat pages remounts it) and the chip was never removed, the file stays on the server and the chat shows as a blank sidebar entry with no UI to remove the file. Fix idea: delete unsent uploaded files on composer unmount, or clean up stale file-only chats.
2. **AUTOINCREMENT high-water mark is reset by step 11 rebuilds.** `messages`, `sub_agent_messages` and `collections` use AUTOINCREMENT; the rebuild (old and new code) drops the table, so `sqlite_sequence` restarts at the highest copied id and ids of deleted tail rows can be reused (sub-agent rows and collections reference messages by a plain `parent_message_id`). Fix idea: read `seq` for the table before the drop and write it back for the renamed table, with a test.
3. **Legacy static UI does not refresh the chat list** after file changes and was not checked against `GET /api/chats` omitting empty chats.
4. **Rebuild paths without a `*_old` repair of index names** are now covered by the atomic rebuild; nothing to do unless the failure path of step 8 (workspace migration) is made atomic too. That step renames `file_systems` and its child tables the same way and is not wrapped in a savepoint (`docs/data.md` Migrations rule 3).

## Acceptance criteria
- [ ] Unsent uploaded files do not leave a listed blank chat after navigating away
- [ ] A table rebuild keeps the AUTOINCREMENT sequence (test: delete the tail row, rebuild, insert, id not reused)
- [ ] The legacy UI behaviour with the filtered chat list is checked and either fixed or recorded as out of scope
- [ ] Decision recorded on making the step 8 workspace migration atomic

## Plan

## Implementation notes

## Verification

## Review history

## Log
- 2026-11-09: created from the review and verification of PRs #63 to #66 (user asked for a follow-up ticket)
