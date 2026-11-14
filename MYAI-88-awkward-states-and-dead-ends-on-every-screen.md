---
id: MYAI-88
title: "Awkward states and dead ends on every screen"
status: done
created: 2026-11-10
updated: 2026-11-11
links:
  split_into: [MYAI-93]
  blocks: [MYAI-91]
  blocked_by: [MYAI-81, MYAI-82, MYAI-83, MYAI-84, MYAI-85, MYAI-86, MYAI-87]
---

## Description
Give every screen its empty, loading, problem, offline and long-text versions and the dead-end screens to Rule book 7.12 and 7.13: placeholder shapes matching the real layout, the notice strip with Try again, offline behaviour of the message box, one-line cut-off for long names, and the 'chat no longer exists' and 'something broke' screens with their dotted drawings.

Design system: repository `console-at-rest` (github.com/archit342000/console-at-rest, local `~/Coding/repos/console-at-rest`): `RULEBOOK.md`, `tokens.css`, `tokens.json`, `reference/console-at-rest.html`.

## Acceptance criteria
- [ ] Every screen has all five states and they match the reference
- [ ] A chat or workspace that no longer exists shows the dead-end screen, not a blank or raw error
- [ ] An unexpected failure shows 'Something broke on our side' with a way out
- [ ] No error code is shown unless asked for
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
