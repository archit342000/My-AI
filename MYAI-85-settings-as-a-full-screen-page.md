---
id: MYAI-85
title: "Settings as a full-screen page"
status: done
created: 2026-11-10
updated: 2026-11-11
links:
  split_into: [MYAI-93]
  blocks: [MYAI-88, MYAI-90]
  blocked_by: [MYAI-79, MYAI-80]
---

## Description
Move all settings out of dialogs into one full-screen Settings page to the design: a section list (tabs on a phone) and one scrolling column with Chat, Models, Personas, Skills, Memory, Agents and System, using the add / edit / delete list pattern, the speed test with its chart, and the whole-screen wait while models switch. Settings apply at once with no Save button. Every setting the app has today keeps a place.

Design system: repository `console-at-rest` (github.com/archit342000/console-at-rest, local `~/Coding/repos/console-at-rest`): `RULEBOOK.md`, `tokens.css`, `tokens.json`, `reference/console-at-rest.html`.

## Acceptance criteria
- [ ] Settings opens as a page with Back, not a pop-up; System opens the same page at its section
- [ ] All seven sections are present and no existing setting is lost
- [ ] Changes apply at once and show Saving / Saved
- [ ] Personas, skills and memory use the shared list pattern; deletes confirm
- [ ] Speed test shows the chart, four figures and Stop; switching models shows the whole-screen wait
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
- 2026-11-10: linked blocks MYAI-88 (provides pieces it needs)
- 2026-11-10: linked blocks MYAI-90 (provides pieces it needs)
- 2026-11-11: merged into MYAI-93 at the user's request (all work after MYAI-76 done as one ticket); not implemented separately; closed and removed from epic MYAI-75
- 2026-11-11: linked split_into MYAI-93 (scope moved there in full)
