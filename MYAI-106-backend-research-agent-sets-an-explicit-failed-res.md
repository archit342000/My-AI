---
id: MYAI-106
title: "Backend: research agent sets an explicit failed result when a phase fails"
status: todo
created: 2026-11-14
updated: 2026-11-14
links:
  relates_to: [MYAI-99]
---

## Description
MYAI-99 decides a helper run's `failed` state from the result text. The research agent's phase failures (scout, planner, executor, synthesis) emit a failure event and return without setting `agent.result`, so the run is recorded `done` even though `research_state` is `failed`. Have the research flow set a failed result (for example `Error: Research stopped...`) on each halting failure, or expose an explicit failed flag the tool handler reads.

## Acceptance criteria
- [ ] A research run that halts is recorded as `failed` in the `agent_run` stream and the stored `agent_runs`
- [ ] Tests force each phase failure and the search limit

## Plan

## Implementation notes

## Verification

## Review history

## Log
- 2026-11-14: created from the follow-ups of the batch run for MYAI-94 to MYAI-103
