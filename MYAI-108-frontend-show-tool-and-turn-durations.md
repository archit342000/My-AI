---
id: MYAI-108
title: "Frontend: show tool and turn durations"
status: todo
created: 2026-11-14
updated: 2026-11-14
links:
  relates_to: [MYAI-97]
---

## Description
The server now sends and stores `duration_ms` on every tool result and on each finished turn (`{"turn": {"duration_ms"}}` event and the last assistant row). Show them: the tool row duration in `features/chat/TimelineEntry.tsx` ("0.1 s") and the whole turn on the Thought process box in `ThoughtBox.tsx` ("46 s"), live and after a reload. Older rows have null and show nothing. Types are already in `frontend/src/api/types.ts` and `stream-reducer.ts`.

## Acceptance criteria
- [ ] A tool row shows its duration live and after a reload
- [ ] The Thought process box shows the turn duration after the turn ends and after a reload
- [ ] Rows without a duration show nothing
- [ ] Unit tests cover live and stored cases

## Plan

## Implementation notes

## Verification

## Review history

## Log
- 2026-11-14: created from the follow-ups of the batch run for MYAI-94 to MYAI-103
