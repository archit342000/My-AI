---
id: MYAI-77
title: "Background: dot sphere and night stars to the new spec"
status: done
created: 2026-11-10
updated: 2026-11-11
links:
  split_into: [MYAI-93]
  blocks: [MYAI-91]
  blocked_by: [MYAI-76]
---

## Description
Update the ambient background (`frontend/src/lib/particles.ts`, `components/background`) to Rule book Part 3: 75% size, 600 dots on a computer and 250 on a phone placed by the golden angle, oval stretch to the screen's shape, Azure dot colours, strength by screen kind (open, reading, working), still stars at night, no haze. It reacts to the pointer, ripples on send and pulses while the app is working; pressing the app's mark sends a ripple.

Design system: repository `console-at-rest` (github.com/archit342000/console-at-rest, local `~/Coding/repos/console-at-rest`): `RULEBOOK.md`, `tokens.css`, `tokens.json`, `reference/console-at-rest.html`.

## Acceptance criteria
- [ ] Sphere size, dot count, spacing, stretch and colours match the rule book on computer and phone
- [ ] A shared "words on the sphere" helper draws the fade behind each line and button, re-measures on resize and font load, and uses the `--fade` values (rule book 3.3)
- [ ] Strength follows the screen kind: full on Home, dimmed behind chats and settings
- [ ] Ripple on send, pulse while thinking, ripple on pressing the app's mark
- [ ] Still stars at night, none by day, no haze
- [ ] Drawn once and still under reduced motion; no measurable slowdown while typing or streaming
- [ ] Checked in a browser on computer and phone, day and night

## Plan

## Implementation notes

## Verification

## Review history

## Log
- 2026-11-10: created
- 2026-11-10: added to epic MYAI-75
- 2026-11-10: linked blocked_by MYAI-76 (needs its pieces first)
- 2026-11-10: linked blocks MYAI-91 (provides pieces it needs)
- 2026-11-11: added criterion for the words-on-the-sphere helper (rule book 1.2)
- 2026-11-11: merged into MYAI-93 at the user's request (all work after MYAI-76 done as one ticket); not implemented separately; closed and removed from epic MYAI-75
- 2026-11-11: linked split_into MYAI-93 (scope moved there in full)
