---
id: MYAI-75
type: epic
title: "Adopt the Console at Rest design system"
status: in-progress
created: 2026-11-10
updated: 2026-11-11
links:
  relates_to: [MYAI-53]
---

## Description
Apply the finished Console at Rest visual language to the My-AI React frontend, so My-AI becomes the first app built on it. The design was settled screen by screen with Archit on 2026-11-10 and is final at rule book version 1.1.

Design system: repository `console-at-rest` (github.com/archit342000/console-at-rest, local `~/Coding/repos/console-at-rest`): `RULEBOOK.md`, `tokens.css`, `tokens.json`, `reference/console-at-rest.html`.

## Scope
In scope: everything under `frontend/` needed to make every screen, pop-up and state match the rule book and the reference page, on computer, tablet and phone, day and night; restoring the file-editor features the legacy UI had; removing the old look once nothing uses it; frontend docs.
Out of scope: backend or API changes (if a screen seems to need one, stop and ask); changes to the design itself (those go to the design-system repository first, through its Part 8); extracting shared components into the design-system repository (later, when a second app needs them); the portfolio site; Android apps.

## Acceptance criteria
- [ ] Every screen and pop-up in the React frontend matches the reference page, in every state
- [ ] The frontend uses only the shared values; `legacy.css` is gone
- [ ] The five signatures are present: dot sphere, squared-off corner, Azure only on actions and selection, three typefaces by job, typewriter labels and tick rules
- [ ] The Rule book Part 10 checklist passes on every screen: computer, tablet and phone; day and night; solid panels; reduced motion; keyboard only
- [ ] No feature or setting available before the change is lost
- [ ] `scripts/check.sh --frontend-only` passes

## Breakdown
### 2026-11-10
Cut so that shared pieces land first and each screen owns its own files. No plans yet: planning is a separate job per ticket.

| Ticket | Area |
|---|---|
| MYAI-76 | Design foundations: shared values, typefaces and themes |
| MYAI-77 | Background: dot sphere and night stars to the new spec |
| MYAI-78 | Core building blocks: buttons, inputs, choices, menus, labels |
| MYAI-79 | Layers that open on top: pop-ups, windows, sheets, messages |
| MYAI-80 | App frame: navigation panel, header and page shells |
| MYAI-81 | Home and the message box |
| MYAI-82 | Conversation: messages, thought process and answer content |
| MYAI-83 | Files panel and editor |
| MYAI-84 | Workspace page |
| MYAI-85 | Settings as a full-screen page |
| MYAI-86 | Logs page |
| MYAI-87 | Tool windows: browser, code runs, version history |
| MYAI-88 | Awkward states and dead ends on every screen |
| MYAI-89 | Phones and Android behaviour |
| MYAI-90 | Wording pass |
| MYAI-91 | Remove the old look and final check |

Order: MYAI-76 first. Then MYAI-77 and MYAI-78 in parallel. Then MYAI-79 and MYAI-80. Then the screens (MYAI-81 to MYAI-87) and MYAI-89, largely in parallel. Then MYAI-88 and MYAI-90. MYAI-91 last. Run `order epic MYAI-75` for the waves.

### 2026-11-11
At the user's request, everything after MYAI-76 is one ticket: MYAI-93 (merges MYAI-77 to MYAI-91, which are closed and removed from the epic). The epic's children are now MYAI-76 and MYAI-93. Design system is at rule book v1.2.

## Notes
### 2026-11-10
- MYAI-53 (fix the React frontend regressions) changes many of the same files and excludes a visual redesign. Decide at planning time whether its children land first; landing them first avoids restyling code that is about to be fixed.
- The design was drawn from both the React code and the fuller legacy UI in `static/`. Where they differ, the reference page is right.
- Things deliberately left out of the design because they reuse existing pieces (extra settings, extra buttons, extra menu items) are built with the existing pieces as each screen is converted.

## Log
- 2026-11-10: created
- 2026-11-10: linked relates_to MYAI-53 (same frontend files; ordering to be decided at planning)
- 2026-11-10: added MYAI-76
- 2026-11-10: added MYAI-77
- 2026-11-10: added MYAI-78
- 2026-11-10: added MYAI-79
- 2026-11-10: added MYAI-80
- 2026-11-10: added MYAI-81
- 2026-11-10: added MYAI-82
- 2026-11-10: added MYAI-83
- 2026-11-10: added MYAI-84
- 2026-11-10: added MYAI-85
- 2026-11-10: added MYAI-86
- 2026-11-10: added MYAI-87
- 2026-11-10: added MYAI-88
- 2026-11-10: added MYAI-89
- 2026-11-10: added MYAI-90
- 2026-11-10: added MYAI-91
- 2026-11-11: in-progress (MYAI-76 started)
- 2026-11-11: removed MYAI-77 to MYAI-91 (merged into MYAI-93)
- 2026-11-11: added MYAI-93
- 2026-11-11: both children done (MYAI-76, MYAI-93), merged into develop
