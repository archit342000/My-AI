---
id: MYAI-53
type: epic
title: "Fix the React frontend regressions found by the audit"
status: done
created: 2026-11-10
updated: 2026-11-10
links:
  relates_to: [MYAI-52, MYAI-75]
---

## Description
The audit in MYAI-52 found 86 defects (A-01 … A-86) in the React frontend on `develop` (5a15a5c): broken turn rendering and thought box, a start-chat race, a dead temporary chat, misplaced popovers, a mobile keyboard regression, many layout differences from the legacy UI, and tests that cannot see any of it. This epic fixes them. The legacy UI (`static/`, `/legacy/`) is the reference for behaviour and geometry unless a child ticket says otherwise.

## Scope
In scope: everything under `frontend/` needed to close A-01 … A-86, plus docs (`docs/frontend.md`, `frontend/README.md`) and tests.
Out of scope: backend or API changes (if a fix seems to need one, stop and ask), a visual redesign, removing the legacy UI.

## Acceptance criteria
- [x] The five reported bugs are fixed: one turn per message, working thought box, clean chat start, tools menu on its button, chat visible above the mobile keyboard
- [ ] Every finding A-01 … A-86 is fixed or explicitly closed with a reason in its child ticket
- [x] `scripts/check.sh --frontend-only` passes and the new end-to-end flows pass against a real backend with a scripted model
- [ ] Desktop (1440px) and phone (390px) screens checked in light and dark after the last child lands

## Breakdown
### 2026-11-10
Children are cut by area so each owns its files. Finding IDs refer to MYAI-52 (Verification).

| Ticket | Area | Findings |
|---|---|---|
| MYAI-54 | Transcript: one assistant turn per user message, with stored tool calls | A-01, A-02, A-03, A-10, A-14, A-55 |
| MYAI-55 | Thought box: ordered timeline, correct live state, stable expansion | A-04, A-05, A-06, A-07, A-08, A-09, A-41 |
| MYAI-56 | Start a chat and send: no error page, no lost focus, temporary chat works | A-11, A-12, A-13, A-15, A-16, A-17 |
| MYAI-57 | Popover placement: tools menu and every upward-opening popover | A-18, A-19, A-20, A-21 |
| MYAI-58 | Mobile keyboard and viewport: chat stays visible while typing | A-22, A-23, A-24, A-25 |
| MYAI-59 | Mobile layout at 390px: bubble width, overlaps, drawer, dialogs | A-26, A-27, A-28, A-29, A-31, A-32, A-33, A-34 |
| MYAI-60 | Chat row layout: match the legacy geometry on desktop | A-35, A-36, A-37, A-38, A-39, A-40, A-42, A-43, A-44, A-45, A-46 |
| MYAI-61 | Composer and attachments: button sizes, ghost chats, stale chips | A-47, A-48, A-49, A-50, A-51, A-52, A-53 |
| MYAI-62 | Clarification prompts: answer the model's question in the chat | A-54 |
| MYAI-63 | Turn follow-ups: files refresh, resume banner, stopped replies, links | A-56, A-57, A-58, A-59, A-60 |
| MYAI-64 | Per-chat settings: restore modes, model and persona; fix thinking profile and sliders | A-61, A-62, A-63, A-64 |
| MYAI-65 | Sidebar and workspace page fixes | A-30, A-65, A-66, A-67, A-68, A-69, A-70, A-71 |
| MYAI-66 | Artifacts panel: layout, unsaved edits, missing file actions | A-72, A-73, A-74, A-75 |
| MYAI-67 | Settings dialogs, logs and tool dialogs polish | A-76, A-77, A-78, A-79, A-81, A-82 |
| MYAI-68 | Light theme background and theme start-up | A-83, A-84 |
| MYAI-69 | Regression guards: real-shape fixtures, stub-backed e2e, inline styles | A-85, A-86 |
| MYAI-70 | Settings parity: clear all chats, git settings, new-chat defaults, search in manage dialogs | A-62 (chat defaults), A-80 |
| MYAI-71 | Research mode UI in React: investigate, then plan (spike) | A-58, A-62 (research depth) |
| MYAI-72 | Model speed test: streamed run with live figures | A-80 (speed test) |
| MYAI-73 | Stop and delete while a turn runs: wait for the server, keep the reply and the text | A-87, A-88, A-89, A-90, A-91 |

Order (from the `blocked_by` links on the children):
- **Wave 1 (no blockers):** MYAI-54 turn model, MYAI-56 start and send, MYAI-57 popovers, MYAI-58 mobile keyboard, MYAI-65 sidebar and workspace page, MYAI-66 artifacts, MYAI-67 dialogs and logs, MYAI-68 theme and background, MYAI-69 guards, MYAI-71 research spike, MYAI-72 speed test.
- **Wave 2:** MYAI-55 thought box, MYAI-62 clarification, MYAI-63 turn follow-ups (all after 54); MYAI-61 composer (after 56).
- **Wave 3:** MYAI-59 mobile layout (after 55 and 57), MYAI-60 row geometry (after 55), MYAI-64 per-chat settings (after 63).
- **Wave 3 (added 2026-11-10):** MYAI-73 stop and delete races (after 54, 56 and 63).
- **Wave 4:** MYAI-70 settings parity (after 64, 67 and 73).
- Suggested first three for the reported bugs: MYAI-54, MYAI-56, MYAI-57, then MYAI-58 and MYAI-55. MYAI-69 early gives the others a real-backend e2e run.

Shared files (land one, merge `develop` into the other): `features/chat/MessageList.tsx` (54, 55, 60, 62, 63), `features/composer/Composer.tsx` (56, 58, 61), `features/chat/send-turn.ts` (54, 56, 63, 64), `features/artifacts/ArtifactPanel.tsx` (60, 63, 65, 66), `styles/components.css` (most).

Open points for the owner, raised by the plans:
- Persona API ignores `git_mode` and `code_execution_mode` (backend gap; MYAI-67 removes the dead Git toggle).
- "Reset app" is proposed as dropped (MYAI-70).
- Version history cannot work for workspace-scoped files without a backend change (MYAI-66 hides it there).
- MYAI-71 needs one run against the shared model server and the research services.
- Race pass (2026-11-10, MYAI-52): the reported "chat does not exist, then the messages are there" is A-11 (MYAI-56). Server side, `DELETE /api/chats/<id>` does not stop a running turn and `/stop` answers before the worker has exited; MYAI-73 handles both from the client, the backend fix is MYAI-74 (outside this epic). Remaining limit: if a worker takes more than about 2 seconds to exit after `/stop`, a Retry is still refused with a toast (reply and text kept).

## Notes
- 2026-11-10: test rig for live checks is in `MYAI-52-evidence/scripts/` (stub model, throwaway data dir, legacy instance for comparison).

## Log
- 2026-11-10: created
- 2026-11-10: added MYAI-54
- 2026-11-10: added MYAI-55
- 2026-11-10: added MYAI-56
- 2026-11-10: added MYAI-57
- 2026-11-10: added MYAI-58
- 2026-11-10: added MYAI-59
- 2026-11-10: added MYAI-60
- 2026-11-10: added MYAI-61
- 2026-11-10: added MYAI-62
- 2026-11-10: added MYAI-63
- 2026-11-10: added MYAI-64
- 2026-11-10: added MYAI-65
- 2026-11-10: added MYAI-66
- 2026-11-10: added MYAI-67
- 2026-11-10: added MYAI-68
- 2026-11-10: added MYAI-69
- 2026-11-10: added MYAI-70
- 2026-11-10: linked relates_to MYAI-52
- 2026-11-10: added MYAI-71
- 2026-11-10: added MYAI-72
- 2026-11-10: breakdown updated after planning (order, shared files, open points)
- 2026-11-10: added MYAI-73
- 2026-11-10: linked relates_to MYAI-75 (same frontend files; ordering to be decided at planning)
- 2026-11-10: closed by the user. All 20 children are done and merged into develop (PRs #101-#118). check.sh (all suites, 869 frontend tests) and the full Playwright run (61 tests) passed on the merged develop.
- 2026-11-10: criteria left unticked at close: (2) not every finding is fixed: the children's unticked criteria are known limits listed in each ticket, and the research-mode findings moved to MYAI-92; (4) no full desktop/phone, light/dark check was done on the merged develop, only per-feature checks inside each child.
