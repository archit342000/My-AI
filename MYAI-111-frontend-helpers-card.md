---
id: MYAI-111
title: "Frontend: helpers card"
status: todo
created: 2026-11-14
updated: 2026-11-14
links:
  relates_to: [MYAI-99]
---

## Description
Draw the helpers card in `features/chat/MessageList.tsx` from the `agent_run` stream chunks (live) and the `agent_runs` collection (after a reload): each helper's name, current activity, working or done or failed, and how long; nested runs show under their parent (`parent_id`). Runs are sequential, so only one is working at a time. Types: `AgentRun` in `frontend/src/api/types.ts`; the reducer ignores the chunk today.

## Acceptance criteria
- [ ] The card shows name, activity, state and duration live and after a reload
- [ ] A nested run appears under its parent
- [ ] A failed run shows as failed
- [ ] Unit tests cover running, done, failed and nested runs

## Plan

## Implementation notes

## Verification

## Review history

## Log
- 2026-11-14: created from the follow-ups of the batch run for MYAI-94 to MYAI-103
