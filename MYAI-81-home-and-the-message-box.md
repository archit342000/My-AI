---
id: MYAI-81
title: "Home and the message box"
status: done
created: 2026-11-10
updated: 2026-11-11
links:
  split_into: [MYAI-93]
  blocks: [MYAI-88, MYAI-90]
  blocked_by: [MYAI-79, MYAI-80]
---

## Description
Restyle Home and the composer to the design: the greeting over the open sphere, the message box (attach, Tools menu with five switches and chips for what is on, send turning into Stop), slash-command suggestions, upload pills with progress and failure, the file drop area, and temporary chat (notice strip, dashed panel edge, Save chat).

Design system: repository `console-at-rest` (github.com/archit342000/console-at-rest, local `~/Coding/repos/console-at-rest`): `RULEBOOK.md`, `tokens.css`, `tokens.json`, `reference/console-at-rest.html`.

## Acceptance criteria
- [ ] Home shows the greeting over the sphere at full strength with no panel over it
- [ ] The greeting and the header's status word have the fade behind each line of words (rule book 3.3)
- [ ] Tools menu matches the design, including tools that are off with the reason shown
- [ ] Slash suggestions, upload states and drop-to-attach match the reference
- [ ] Temporary chat is clearly marked and can be saved
- [ ] All of it works on a phone above the keyboard
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
- 2026-11-11: added criterion for the words-on-the-sphere fade (rule book 1.2)
- 2026-11-11: merged into MYAI-93 at the user's request (all work after MYAI-76 done as one ticket); not implemented separately; closed and removed from epic MYAI-75
- 2026-11-11: linked split_into MYAI-93 (scope moved there in full)
