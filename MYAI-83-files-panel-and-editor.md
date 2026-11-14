---
id: MYAI-83
title: "Files panel and editor"
status: done
created: 2026-11-10
updated: 2026-11-11
links:
  split_into: [MYAI-93]
  blocks: [MYAI-84, MYAI-88, MYAI-90]
  blocked_by: [MYAI-79, MYAI-80]
---

## Description
Rebuild the Files panel and editor (`features/artifacts`) to the design, bringing back what the legacy UI had: folder tree with counts, search across names and contents with the matching line, per-file menu and right-click (run, download, rename or move, delete), new file and folder, the where-and-name pop-up, editor with line numbers and current line, language and version labels, saving by itself, Code / Preview with live tick boxes, undo, redo, copy, run with an output strip, research-plan Approve / Suggest changes, a resizable panel, and Full screen.

Design system: repository `console-at-rest` (github.com/archit342000/console-at-rest, local `~/Coding/repos/console-at-rest`): `RULEBOOK.md`, `tokens.css`, `tokens.json`, `reference/console-at-rest.html`.

## Acceptance criteria
- [ ] Every feature listed works in the Files panel beside a chat and in a workspace
- [ ] Edits save by themselves with a Saving / Saved light; there is no Save button
- [ ] Full screen fills the window and returns exactly where it was
- [ ] On a phone: the list, then the editor, edge to edge
- [ ] Unsaved work is never lost when switching files or closing the panel
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
- 2026-11-10: linked blocks MYAI-84 (provides pieces it needs)
- 2026-11-10: linked blocks MYAI-88 (provides pieces it needs)
- 2026-11-10: linked blocks MYAI-90 (provides pieces it needs)
- 2026-11-11: merged into MYAI-93 at the user's request (all work after MYAI-76 done as one ticket); not implemented separately; closed and removed from epic MYAI-75
- 2026-11-11: linked split_into MYAI-93 (scope moved there in full)
