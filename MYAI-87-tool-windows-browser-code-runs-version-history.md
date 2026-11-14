---
id: MYAI-87
title: "Tool windows: browser, code runs, version history"
status: done
created: 2026-11-10
updated: 2026-11-11
links:
  split_into: [MYAI-93]
  blocks: [MYAI-88, MYAI-90]
  blocked_by: [MYAI-79]
---

## Description
Rebuild the three tool windows (`features/tools`, versions) on the large-window shell: the browser window (starting, live, not running with Try again), code run history (foldable runs with code, output or error, and how it ended), and version history (versions listed, the chosen one shown, Restore).

Design system: repository `console-at-rest` (github.com/archit342000/console-at-rest, local `~/Coding/repos/console-at-rest`): `RULEBOOK.md`, `tokens.css`, `tokens.json`, `reference/console-at-rest.html`.

## Acceptance criteria
- [ ] All three open from where the design puts them and match the reference
- [ ] Each has its empty, loading and failed states
- [ ] On a phone each is a full screen that Back closes
- [ ] Checked in a browser on computer and phone, day and night

## Plan

## Implementation notes

## Verification

## Review history

## Log
- 2026-11-10: created
- 2026-11-10: added to epic MYAI-75
- 2026-11-10: linked blocked_by MYAI-79 (needs its pieces first)
- 2026-11-10: linked blocks MYAI-88 (provides pieces it needs)
- 2026-11-10: linked blocks MYAI-90 (provides pieces it needs)
- 2026-11-11: merged into MYAI-93 at the user's request (all work after MYAI-76 done as one ticket); not implemented separately; closed and removed from epic MYAI-75
- 2026-11-11: linked split_into MYAI-93 (scope moved there in full)
