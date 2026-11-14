---
id: MYAI-79
title: "Layers that open on top: pop-ups, windows, sheets, messages"
status: done
created: 2026-11-10
updated: 2026-11-11
links:
  split_into: [MYAI-93]
  blocks: [MYAI-81, MYAI-82, MYAI-83, MYAI-84, MYAI-85, MYAI-87, MYAI-89]
  blocked_by: [MYAI-78]
---

## Description
Rebuild the things that open over the app to Rule book Part 7.11 and Part 6: the confirming pop-up (only for what cannot be undone), the large window shell (title, status, close), the bottom sheet on phones, the small pop-up attached to a button, brief messages including one with Undo, the notice strip, the whole-screen wait, and the bigger view with zoom. Replaces `Modal`, `ConfirmDialog`, `Toast`.

Design system: repository `console-at-rest` (github.com/archit342000/console-at-rest, local `~/Coding/repos/console-at-rest`): `RULEBOOK.md`, `tokens.css`, `tokens.json`, `reference/console-at-rest.html`.

## Acceptance criteria
- [ ] Pop-ups are used only to confirm irreversible actions; everything else that was a dialog has a designed home
- [ ] On a phone, pop-ups rise from the bottom and large windows fill the screen
- [ ] Brief messages stack correctly, last 2.6 s, or 6 s with Undo
- [ ] Escape and Back close the newest layer first; focus is kept inside and returned afterwards
- [ ] Layer order follows the six fixed layers
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
- 2026-11-10: linked blocks MYAI-87 (provides pieces it needs)
- 2026-11-10: linked blocks MYAI-89 (provides pieces it needs)
- 2026-11-11: merged into MYAI-93 at the user's request (all work after MYAI-76 done as one ticket); not implemented separately; closed and removed from epic MYAI-75
- 2026-11-11: linked split_into MYAI-93 (scope moved there in full)
