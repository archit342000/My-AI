---
id: MYAI-78
title: "Core building blocks: buttons, inputs, choices, menus, labels"
status: done
created: 2026-11-10
updated: 2026-11-11
links:
  split_into: [MYAI-93]
  blocks: [MYAI-79, MYAI-80, MYAI-86]
  blocked_by: [MYAI-76]
---

## Description
Build the shared pieces every screen uses, to Rule book Part 7.1 to 7.5 and 7.14, in `frontend/src/components/ui`: the five button kinds with all states (including busy, small, icon-only with tips, link, toggle), text boxes of every kind used by My-AI, our own drop-down (bottom sheet on phones), switch, tick box, side-by-side pick-one / tabs, pick-one circles, slider, tags, menus (icons, groups, keys, ticked, off, menu inside a menu), hover tips, chips, count badges, the status light and typewriter label, tick rule, icons redrawn in the one outline style, and the keyboard focus ring.

Design system: repository `console-at-rest` (github.com/archit342000/console-at-rest, local `~/Coding/repos/console-at-rest`): `RULEBOOK.md`, `tokens.css`, `tokens.json`, `reference/console-at-rest.html`.

## Acceptance criteria
- [ ] Each piece exists once, matches the reference page in every state, day and night
- [ ] A control that is switched off for a changeable reason shows the reason
- [ ] The browser's own drop-down is not used anywhere
- [ ] Everything is reachable by keyboard with the shared focus ring; icon-only buttons have a tip and a spoken name
- [ ] The developer preview page (`features/dev`) shows all of them
- [ ] Checked in a browser on computer and phone, day and night

## Plan

## Implementation notes

## Verification

## Review history

## Log
- 2026-11-10: created
- 2026-11-10: added to epic MYAI-75
- 2026-11-10: linked blocked_by MYAI-76 (needs its pieces first)
- 2026-11-10: linked blocks MYAI-79 (provides pieces it needs)
- 2026-11-10: linked blocks MYAI-80 (provides pieces it needs)
- 2026-11-10: linked blocks MYAI-86 (provides pieces it needs)
- 2026-11-11: merged into MYAI-93 at the user's request (all work after MYAI-76 done as one ticket); not implemented separately; closed and removed from epic MYAI-75
- 2026-11-11: linked split_into MYAI-93 (scope moved there in full)
