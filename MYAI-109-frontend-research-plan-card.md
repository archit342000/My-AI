---
id: MYAI-109
title: "Frontend: research plan card"
status: todo
created: 2026-11-14
updated: 2026-11-14
links:
  relates_to: [MYAI-98]
---

## Description
Draw the research plan card in `features/chat/MessageList.tsx` from the `research_progress` stream chunk (live) and the `research_progress` collection on the assistant message (after a reload): the steps with state and duration, "3 of 6 steps · 12 pages read", the phase, and Stop research (the chat's Stop). Types: `ResearchProgress`, `StoredCollection` in `frontend/src/api/types.ts`; the reducer currently ignores the chunk.

## Acceptance criteria
- [ ] The card shows steps, states, durations, counts and phase live
- [ ] After a reload it shows the stored latest snapshot
- [ ] Stop research stops the turn
- [ ] Unit tests cover live, reload, failed and awaiting-approval states

## Plan

## Implementation notes

## Verification

## Review history

## Log
- 2026-11-14: created from the follow-ups of the batch run for MYAI-94 to MYAI-103
