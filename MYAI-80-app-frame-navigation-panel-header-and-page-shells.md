---
id: MYAI-80
title: "App frame: navigation panel, header and page shells"
status: done
created: 2026-11-10
updated: 2026-11-11
links:
  split_into: [MYAI-93]
  blocks: [MYAI-81, MYAI-82, MYAI-83, MYAI-84, MYAI-85, MYAI-86, MYAI-89]
  blocked_by: [MYAI-78]
---

## Description
Rebuild the frame around every screen to Rule book Part 5: the floating navigation panel (New chat, temporary chat, new workspace, Workspaces, chats grouped by day with a per-chat menu including Move to a workspace, Settings / System / Logs), its collapsed icon rail with name tags, the content panel with header (title, status light, actions) and tick rule, the optional resizable side panel, and the full-screen page shell with Back used by Settings. Phone drawer behaviour is in the phone ticket.

Design system: repository `console-at-rest` (github.com/archit342000/console-at-rest, local `~/Coding/repos/console-at-rest`): `RULEBOOK.md`, `tokens.css`, `tokens.json`, `reference/console-at-rest.html`.

## Acceptance criteria
- [ ] Navigation panel open and collapsed match the reference; the choice persists
- [ ] Chat rows show time, selection and the per-chat menu (rename, move with sub-list, delete); right-click opens the same menu
- [ ] Header shows the page title, status light and actions on every screen
- [ ] The big content panel is tinted, not heavily blurred, so the sphere shows
- [ ] Tablet, computer and very-wide widths lay out as the rule book describes
- [ ] Checked in a browser on computer and phone, day and night

## Plan

## Implementation notes

## Verification

## Review history

## Log
- 2026-11-10: created
- 2026-11-10: added to epic MYAI-75
- 2026-11-10: linked blocked_by MYAI-78 (needs its pieces first)
- 2026-11-10: linked blocks MYAI-81 (provides pieces it needs)
- 2026-11-10: linked blocks MYAI-82 (provides pieces it needs)
- 2026-11-10: linked blocks MYAI-83 (provides pieces it needs)
- 2026-11-10: linked blocks MYAI-84 (provides pieces it needs)
- 2026-11-10: linked blocks MYAI-85 (provides pieces it needs)
- 2026-11-10: linked blocks MYAI-86 (provides pieces it needs)
- 2026-11-10: linked blocks MYAI-89 (provides pieces it needs)
- 2026-11-11: merged into MYAI-93 at the user's request (all work after MYAI-76 done as one ticket); not implemented separately; closed and removed from epic MYAI-75
- 2026-11-11: linked split_into MYAI-93 (scope moved there in full)
