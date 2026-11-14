---
id: MYAI-90
title: "Wording pass"
status: done
created: 2026-11-10
updated: 2026-11-11
links:
  split_into: [MYAI-93]
  blocks: [MYAI-91]
  blocked_by: [MYAI-81, MYAI-82, MYAI-83, MYAI-84, MYAI-85, MYAI-86, MYAI-87]
---

## Description
Bring every label, button, message, error, time, date and number in the frontend in line with Rule book Part 9: verb-and-thing buttons, first-word capitals only, errors that say what happened and what to do, plain names for technical things with a hint, 24-hour times and day-before-month dates.

Design system: repository `console-at-rest` (github.com/archit342000/console-at-rest, local `~/Coding/repos/console-at-rest`): `RULEBOOK.md`, `tokens.css`, `tokens.json`, `reference/console-at-rest.html`.

## Acceptance criteria
- [ ] No button reads Submit, OK or Yes
- [ ] Only first words and proper names are capitalised
- [ ] Every error message says what happened and what to do next
- [ ] Times, dates, durations and numbers follow Part 9 everywhere
- [ ] Checked in a browser on computer and phone, day and night

## Plan

## Implementation notes

## Verification

## Review history

## Log
- 2026-11-10: created
- 2026-11-10: added to epic MYAI-75
- 2026-11-10: linked blocked_by MYAI-81 (needs its pieces first)
- 2026-11-10: linked blocked_by MYAI-82 (needs its pieces first)
- 2026-11-10: linked blocked_by MYAI-83 (needs its pieces first)
- 2026-11-10: linked blocked_by MYAI-84 (needs its pieces first)
- 2026-11-10: linked blocked_by MYAI-85 (needs its pieces first)
- 2026-11-10: linked blocked_by MYAI-86 (needs its pieces first)
- 2026-11-10: linked blocked_by MYAI-87 (needs its pieces first)
- 2026-11-10: linked blocks MYAI-91 (provides pieces it needs)
- 2026-11-11: merged into MYAI-93 at the user's request (all work after MYAI-76 done as one ticket); not implemented separately; closed and removed from epic MYAI-75
- 2026-11-11: linked split_into MYAI-93 (scope moved there in full)
