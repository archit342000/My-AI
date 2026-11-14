---
id: MYAI-84
title: "Workspace page"
status: done
created: 2026-11-10
updated: 2026-11-11
links:
  split_into: [MYAI-93]
  blocks: [MYAI-88, MYAI-90]
  blocked_by: [MYAI-79, MYAI-80, MYAI-83]
---

## Description
Restyle the Workspace page (`features/workspace`) to the design: header with the workspace icon (icon picker), name, rename and delete, chat cards, and the file browser side by side with the editor. Includes the workspace menu in the navigation panel.

Design system: repository `console-at-rest` (github.com/archit342000/console-at-rest, local `~/Coding/repos/console-at-rest`): `RULEBOOK.md`, `tokens.css`, `tokens.json`, `reference/console-at-rest.html`.

## Acceptance criteria
- [ ] Page matches the reference on computer and phone
- [ ] Workspace icon can be changed with the icon picker and shows in the navigation panel
- [ ] Empty workspace shows the designed empty screen
- [ ] Rename and delete behave as designed (delete confirms)
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
- 2026-11-10: linked blocked_by MYAI-83 (needs its pieces first)
- 2026-11-10: linked blocks MYAI-88 (provides pieces it needs)
- 2026-11-10: linked blocks MYAI-90 (provides pieces it needs)
- 2026-11-11: merged into MYAI-93 at the user's request (all work after MYAI-76 done as one ticket); not implemented separately; closed and removed from epic MYAI-75
- 2026-11-11: linked split_into MYAI-93 (scope moved there in full)
