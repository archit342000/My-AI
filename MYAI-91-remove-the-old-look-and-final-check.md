---
id: MYAI-91
title: "Remove the old look and final check"
status: done
created: 2026-11-10
updated: 2026-11-11
links:
  split_into: [MYAI-93]
  blocked_by: [MYAI-77, MYAI-88, MYAI-89, MYAI-90]
---

## Description
Once every screen is converted: remove `legacy.css` and any styles, variables, fonts and components the new design replaced, update `docs/frontend.md` and `frontend/README.md`, and run the Rule book Part 10 checklist on every screen (computer, tablet, phone; day and night; solid panels; reduced motion; keyboard only).

Design system: repository `console-at-rest` (github.com/archit342000/console-at-rest, local `~/Coding/repos/console-at-rest`): `RULEBOOK.md`, `tokens.css`, `tokens.json`, `reference/console-at-rest.html`.

## Acceptance criteria
- [ ] `legacy.css` and unused old components are gone and nothing references them
- [ ] No raw colour, size, corner, shadow or speed remains outside the shared values
- [ ] The Part 10 checklist passes on every screen, with evidence recorded
- [ ] Frontend docs describe the new structure and point to the design-system repository
- [ ] `scripts/check.sh --frontend-only` passes
- [ ] Checked in a browser on computer and phone, day and night

## Plan

## Implementation notes

## Verification

## Review history

## Log
- 2026-11-10: created
- 2026-11-10: added to epic MYAI-75
- 2026-11-10: linked blocked_by MYAI-77 (needs its pieces first)
- 2026-11-10: linked blocked_by MYAI-88 (needs its pieces first)
- 2026-11-10: linked blocked_by MYAI-89 (needs its pieces first)
- 2026-11-10: linked blocked_by MYAI-90 (needs its pieces first)
- 2026-11-11: merged into MYAI-93 at the user's request (all work after MYAI-76 done as one ticket); not implemented separately; closed and removed from epic MYAI-75
- 2026-11-11: linked split_into MYAI-93 (scope moved there in full)
