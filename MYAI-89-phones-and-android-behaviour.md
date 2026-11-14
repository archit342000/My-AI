---
id: MYAI-89
title: "Phones and Android behaviour"
status: done
created: 2026-11-10
updated: 2026-11-11
links:
  split_into: [MYAI-93]
  blocks: [MYAI-91]
  blocked_by: [MYAI-79, MYAI-80]
---

## Description
Make the app behave as Rule book Part 6 on phones: every screen edge to edge with no inset cards, drawing behind the status and gesture bars, 48 touch targets, the navigation panel as a slide-in drawer, pop-ups as bottom sheets, the message box riding above the keyboard, Back undoing the newest layer first and only leaving from Home, and solid panels where blur is unavailable.

Design system: repository `console-at-rest` (github.com/archit342000/console-at-rest, local `~/Coding/repos/console-at-rest`): `RULEBOOK.md`, `tokens.css`, `tokens.json`, `reference/console-at-rest.html`.

## Acceptance criteria
- [ ] No screen is an inset card on a phone
- [ ] All touch targets are at least 48
- [ ] Back order matches the rule book on a real Android device
- [ ] The message box stays visible above the keyboard
- [ ] Solid-panel mode is chosen automatically where blur is unsupported
- [ ] Checked in a browser on computer and phone, day and night

## Plan

## Implementation notes

## Verification

## Review history

## Log
- 2026-11-10: created
- 2026-11-10: added to epic MYAI-75
- 2026-11-10: linked blocked_by MYAI-79 (needs its pieces first)
- 2026-11-10: linked blocked_by MYAI-80 (needs its pieces first)
- 2026-11-10: linked blocks MYAI-91 (provides pieces it needs)
- 2026-11-11: merged into MYAI-93 at the user's request (all work after MYAI-76 done as one ticket); not implemented separately; closed and removed from epic MYAI-75
- 2026-11-11: linked split_into MYAI-93 (scope moved there in full)
