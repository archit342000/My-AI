---
id: MYAI-55
title: "Thought box: ordered timeline, correct live state, stable expansion"
status: done
epic: MYAI-53
created: 2026-11-10
updated: 2026-11-10
links:
  blocked_by: [MYAI-54]
  blocks: [MYAI-59, MYAI-60]
---

## Description
The thought box shows reasoning as a card inside a card, puts tool pills outside the box, says "Thought Process" while the model is still working, hides streaming reasoning, collapses itself when the turn completes, and has no full-view. Rebuild it on the step list from MYAI-54 as the legacy timeline: collapsible REASONING / CALL / TOOL RESULT entries in order inside one box.

Findings (MYAI-52, Verification): A-04, A-05, A-06, A-07, A-08, A-09, A-41. Evidence and the live test rig are in `~/.claude/tickets/My-AI/MYAI-52-evidence/`.

## Acceptance criteria
- [x] Expanded box lists the turn's steps in order as collapsible entries; no nested bubble styling
- [ ] Header shows the active state until the turn ends, with the latest activity label; it shows the finished state only after the stream ends
- [x] A box the user expanded stays expanded when the turn completes and across refetches
- [x] Tool activity is inside the box; the model label is not shown under an empty bubble
- [x] A full-view control opens the timeline in a dialog
- [ ] The redact/retry notice is styled, shows a spinner and no raw backend text
- [x] Matches the legacy box geometry at 1440px (header 56px tall) within 1px

## Plan
**Date:** 2026-11-10  **Status:** Validated

### Objective
Rebuild the thought box on the turn's step list (from MYAI-54) so it works like the legacy one: a header that shows the real live state, and an expandable timeline of collapsible entries (reasoning, tool call, tool result, event, sub-agent group) in the order they happened, with stable expansion, a full-view dialog and a styled retry notice.

### Context
- **Requirement:** this ticket's Description and Acceptance criteria (findings A-04 to A-09, A-41 in MYAI-52).
- **Assumes merged:** MYAI-54 (`Step`, assistant `Turn.steps`, `LiveTurn.steps`, selectors `turnText`, `turnTools`, one row per turn in `features/chat/MessageList.tsx`).
- **Rules:** `docs/standards/frontend.md` (one component per file named after it, pure logic in `src/lib/` and stores in `src/state/` with a test next to each, no inline styles except `// dynamic-style`, CSS custom properties, reuse `Modal`, keyboard operable), `docs/frontend.md` (keep legacy class names so `styles/legacy.css` applies).
- **Current code (`frontend/src/`):**
  - `features/chat/ThoughtBlock.tsx` exports `ThoughtHeader` and `ThoughtTimeline`; the body renders reasoning through `Markdown` with the bubble classes `message-content raw-text-content` (card inside a card).
  - `features/chat/ToolActivity.tsx` exports `ToolActivityCard`, `ToolSummary`, `ToolActivityFeed`; `MessageList.tsx` `BotBody` puts `ToolSummary` between header and bubble, keeps `expanded` in local state, and passes `active = !live.content`.
  - `MessageList.tsx` `LiveAssistant` prints `live.redactNotice` (the server's message text) inside `.validation-fixing`, which has no CSS rule in `styles/components.css`.
  - `styles/components.css`: "Chat transcript (bot-turn, …)" and "Tool activity (activity-item)" blocks; `.bot-turn` is a two-column grid (avatar | body).
- **Legacy reference:**
  - Row markup: `static/js/message-manager.js:166-200`: `.assistant-header-row` (avatar column + `.thought-section-wrapper` with `.thought-container` > `.thought-header` holding `.thought-status` and `.thought-actions` with a `.thought-full-view-btn`), then a full-width `.thought-timeline-wrapper` and a full-width `.message-content-wrapper`.
  - Entries: `static/js/agent-renderers.js:128-330`: `.activity-item` with `thinking-item` ("Reasoning"), `tool-call-item` ("Call: <tool>"), `tool-result-item` ("Tool Result: <tool>"), `event-divider`; `sub-agent-container` groups at lines 353 and 411; collapsed by default.
  - Full view: `#thought-full-view-modal` in `static/index.html`.
  - Measured at 1440px (MYAI-52 `metrics/d-chat-long.txt`): thought header 56px tall at x=513; bubble at x=464, width 768.

### Approach
- **Components (one per file, in `features/chat/`):**
  - `ThoughtBox.tsx` (new): header plus timeline for one turn. Props: `steps`, `active`, `turnKey`. Replaces `ThoughtBlock.tsx`.
  - `TimelineEntry.tsx` (new): one collapsible entry for a step, using the legacy classes and labels above; long text uses the existing clip-and-"Show more" behaviour moved from `ToolActivity.tsx`.
  - `ThoughtFullView.tsx` (new): a `Modal` showing the same timeline with every entry expanded (`TimelineEntry` takes a `defaultOpen` prop).
  - `ToolActivity.tsx` and `ThoughtBlock.tsx` are deleted once nothing imports them (`ToolSummary` is removed: tool activity lives in the box).
- **Pure logic in `lib/thought-timeline.ts` (new):** `timelineOf(steps)` returns the entries to show, in step order: a reasoning step yields a "Reasoning" entry, an event step yields an event divider, main-agent text steps are left out (they are the bubble), each tool step yields a call entry and, when it has a result, a result entry, and consecutive steps of one sub-agent are grouped under one entry labelled with `agentLabel` (`lib/labels.ts`). `statusOf(steps)` returns the live status line: the last event text, else the friendly name of a tool still running, else nothing.
- **Row layout as legacy:** the avatar sits beside the thought header in `.assistant-header-row`; the timeline and the bubble take the full row width under it. `.bot-turn` grid rules are replaced by rules for the legacy structure in the "Chat transcript" block of `components.css` (the values legacy sets inline become classes). A turn with no steps to show has no box; the avatar then sits beside the bubble's first line.
- **Live state:** `active` is true for the live row for as long as the turn streams. The header shows "Thinking…" with the dots and the status line while active and "Thought Process" after. The model label is rendered only once the turn has text.
- **Expansion state survives the swap from live to saved:** `state/thought-store.ts` (new Zustand store) keeps the expanded boxes by key `chatId:ordinal`, where the ordinal is the number of user turns up to and including the one the assistant turn answers; the live row counts the persisted user turns plus the pending one, so the key is the same before and after saving. Per-entry open state stays local to `TimelineEntry`.
- **Retry notice:** the live row shows a fixed, styled line ("Fixing the reply…") with the shared spinner (`.ui-spinner`) while `redactNotice` is set; the server's message text is not shown.
- **Rejected:** keeping the grid and only restyling the body (cannot reach the legacy geometry, and the bubble stays 44px narrower); storing expansion per message id (the live row has no id).

### Out of scope
- Remaining geometry differences outside the box (model label text and size, action rows, notices alignment, title field): MYAI-60.
- Mobile layout of the row: MYAI-59.
- Sub-agent rendering beyond a labelled group of entries (legacy's rich research and browsing renderers): MYAI-70.
- The turn model itself: MYAI-54.

### Steps
#### Step 1: Timeline logic
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/lib/thought-timeline.ts` (create: `timelineOf`, `statusOf`, entry types), `frontend/src/lib/thought-timeline.test.ts` (create)
- **Change:** as in Approach ("Pure logic").
- **Verification:** unit tests: order is kept; reasoning and event steps give their entries; text steps of the main agent are excluded; a tool with a result gives two entries and a running tool gives one; sub-agent steps are grouped per agent run; `statusOf` prefers the last event, then a running tool.

#### Step 2: Expansion store
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/state/thought-store.ts` (create: `expanded`, `toggle(key)`, `clearChat(chatId)`), `frontend/src/state/thought-store.test.ts` (create)
- **Change:** as in Approach ("Expansion state").
- **Verification:** unit tests: toggling a key flips it; `clearChat` removes only that chat's keys.

#### Step 3: Timeline entry
- **Status:** todo
- **Depends on:** 1
- **Files:** `frontend/src/features/chat/TimelineEntry.tsx` (create), `frontend/src/features/chat/TimelineEntry.test.tsx` (create), `frontend/src/styles/components.css` (modify: "Tool activity (activity-item)" block), `frontend/src/test/css-coverage.test.ts` (modify if a class styled here is in `TODO_UNSTYLED`)
- **Change:** a button header (`aria-expanded`) and a body per entry kind with the legacy classes and labels; reasoning text is rendered through `Markdown` with a class that carries no bubble styling; arguments are pretty-printed; long text is clipped with "Show more".
- **Verification:** component tests: each kind shows its label; Enter and click toggle the body; a group entry shows its nested entries when opened; no element in the body has the class `message-content`.

#### Step 4: Thought box and full view
- **Status:** todo
- **Depends on:** 2, 3
- **Files:** `frontend/src/features/chat/ThoughtBox.tsx` (create), `frontend/src/features/chat/ThoughtFullView.tsx` (create), `frontend/src/features/chat/ThoughtBox.test.tsx` (create), `frontend/src/styles/components.css` (modify: "Chat transcript" block: `.thought-status`, `.thought-actions`, full-view button)
- **Change:** the header row holds two real buttons side by side, not nested: the expand toggle (status, title and chevron, `aria-expanded`) and the full-view button; body lists `timelineOf(steps)`; expansion read from the store by `turnKey`; the full-view button opens `ThoughtFullView`.
- **Verification:** component tests: active shows "Thinking…" and the status line, inactive shows "Thought Process"; expansion follows the store; the full-view dialog opens, lists the entries and closes on Escape with focus back on the button.

#### Step 5: Use it in the transcript with the legacy row layout
- **Status:** todo
- **Depends on:** 4
- **Files:** `frontend/src/features/chat/MessageList.tsx` (modify: `BotBody`, `AssistantTurn`, `LiveAssistant`, `InterruptedAssistant`, turn ordinals), `frontend/src/features/chat/MessageList.test.tsx` (modify), `frontend/src/styles/components.css` (modify: "Chat transcript" block, replace `.bot-turn*` rules; add the retry-notice rule), `frontend/src/features/chat/ThoughtBlock.tsx` and `frontend/src/features/chat/ToolActivity.tsx` (delete, with `ToolActivity`-only CSS), `frontend/src/test/css-coverage.test.ts` (modify: remove from `TODO_UNSTYLED` every class this step gives a rule or stops using, such as `validation-fixing`, `thought-section-wrapper`, `full-width-reasoning`, `message-content-wrapper`, `thought-text`; a class still used elsewhere and still unstyled, such as `raw-text-content`, stays)
- **Change:** as in Approach ("Row layout as legacy", "Live state", "Retry notice"); deleting a turn calls `clearChat`.
- **Verification:** component tests: a box expanded on the live row is still expanded after the stream ends and the saved row renders; the model label is absent while the turn has no text; the retry notice shows the fixed text and not the chunk's message; no `ToolSummary` list outside the box.

#### Step 6: Geometry check, docs and full checks
- **Status:** todo
- **Depends on:** 5
- **Files:** `frontend/e2e/thought-box.spec.ts` (create), `docs/frontend.md` (modify: Streaming section sentence on how activity is shown), `frontend/README.md` (modify only if affected)
- **Change:** docs match the code. The spec mocks a two-round stream from `src/test/fixtures/stream/tools.sse` (the two-round fixture MYAI-54 adds) and the saved chat detail (as `e2e/chat-send.spec.ts` does): expand the box while streaming, wait for the turn to finish, open the full view and close it with Escape; it asserts the box is still expanded on the saved row and the dialog lists the entries (`npm run e2e`).
- **Verification:** from `frontend/`: `npm run typecheck`, `npm run lint`, `npm run test`, `npm run build`. Live, with the rig in `~/.claude/tickets/My-AI/MYAI-52-evidence/scripts/` (`up.sh`, then `node metrics.mjs d '/chat/{long}'` and `node metrics.mjs d '/chat/{long}' thought`): `.thought-container` and `.thought-header` differ from legacy by at most 1px in x, y, width and height, and `.message-content-wrapper` by at most 1px in x and width. Then `scripts/check.sh --frontend-only` from the repo root.

### Tests
- Unit: `lib/thought-timeline.test.ts`, `state/thought-store.test.ts`.
- Component: `TimelineEntry.test.tsx`, `ThoughtBox.test.tsx`, `MessageList.test.tsx`.
- E2E: `e2e/thought-box.spec.ts`.
- Guards: `test/css-coverage.test.ts` and `test/inline-style.test.ts` must stay green (no new inline styles).
- Commands: `npm run typecheck && npm run lint && npm run test && npm run build` in `frontend/`.

### Risks and open questions
- **Ordinal keys shift when an earlier turn is deleted.** Mitigation: `clearChat` on delete, which collapses every box in that chat.
- **Legacy CSS for `.activity-item` expects `.expanded > .activity-content`;** the React block added an extra wrapper for animation. The entry keeps one consistent structure and the `components.css` block is the single owner of these rules; check both themes.

### Success criteria
- [ ] Expanded box lists the steps in order as collapsible entries, with no bubble styling inside
- [ ] Header stays in the active state, with a status line, until the stream ends
- [ ] An expanded box stays expanded when the turn completes and after a refetch
- [ ] Tool activity is inside the box; no model label under an empty bubble
- [ ] Full-view dialog works with the keyboard
- [ ] Retry notice is styled, has a spinner and shows no server text
- [ ] Thought header matches legacy geometry at 1440px within 1px; the bubble matches in x and width
- [ ] `typecheck`, `lint`, `test`, `build` pass
### Reviewer brief
- **Objective:** thought box rebuilt on the turn's steps as the legacy timeline, with a truthful live header, stable expansion, a full-view dialog and a styled retry notice.
- **Decisions:** new `ThoughtBox.tsx`, `TimelineEntry.tsx`, `ThoughtFullView.tsx`; `ThoughtBlock.tsx`, `ToolActivity.tsx` and `ToolSummary` removed; entries built by `lib/thought-timeline.ts` (`timelineOf`, `statusOf`); legacy row layout (`.assistant-header-row`, full-width timeline and bubble) replaces the `.bot-turn` grid; header is active until the stream ends; expansion kept in `state/thought-store.ts` by `chatId:ordinal` (ordinal = user turns up to the one answered); retry notice shows fixed text, never the server's message; header has two sibling buttons (toggle, full view).
- **Out of scope:** geometry outside the box (MYAI-60), mobile row layout (MYAI-59), legacy per-agent renderers (MYAI-70), the turn model (MYAI-54).
- **Success criteria:** ordered collapsible entries with no bubble styling; active header with status until the stream ends; expansion survives completion and refetch; tools inside the box and no label under an empty bubble; keyboard-usable full view; styled notice without server text; header geometry within 1px of legacy; checks pass.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- **Round 1:** validator FAIL (2 blocking, 7 minor). Judged FAIL. Valid blocking: newly styled classes must leave `TODO_UNSTYLED` in `test/css-coverage.test.ts`; no Playwright spec for the new flows (added `e2e/thought-box.spec.ts`). Valid minors fixed: `timelineOf` did not name reasoning and event entries; two definitions of the ordinal; bubble height check owned by MYAI-60 (narrowed to x and width); nested interactive header (two sibling buttons); `defaultOpen` for the full view; legacy line range for sub-agent groups; `scripts/check.sh` in the final step.
- **Round 2 (diff-scoped):** validator PASS (4 minor). Judged PASS. Fixed inline: Step 3 names the allowlist file; `clearChat` wording; `raw-text-content` stays in the allowlist; the spec's stream source named.

## Implementation notes
Branch bugfix/thought-box-timeline, base bugfix/transcript-turn-model (a66ac20). Autopilot batch item 8.
### Implementation progress
- [x] Step 1: Timeline logic - lib/thought-timeline.ts (+test)
- [x] Step 2: Expansion store - state/thought-store.ts (+test)
- [x] Step 3: Timeline entry - features/chat/TimelineEntry.tsx (+test), components.css
- [x] Step 4: Thought box and full view - ThoughtBox.tsx, ThoughtFullView.tsx (+test), components.css
- [x] Step 5: Transcript - MessageList.tsx (+tests), ThoughtBlock.tsx and ToolActivity.tsx deleted, css-coverage allowlist trimmed
- [x] Step 6: e2e/thought-box.spec.ts, docs/frontend.md, geometry check
Deviations / decisions (autopilot, recorded):
- Sub-agent text steps are shown in the group as a "Response" entry (MYAI-54 kept them but did not draw them).
- The `.bot-turn` grid rules are kept for the no-box case (avatar beside the answer); the legacy row structure is used when there is a box.
- The full-view button is a sibling of the toggle, positioned over it just left of the chevron (legacy order), via CSS.
- Pending user rows now carry `ordinal` (set in send-turn from the history length): while a new chat streams, the saved copy of the user message can already be in the list, so counting turns would give a different key before and after saving. Found live (a probe showed the persisted and the pending user row both drawn during a new chat's stream: pre-existing, not changed here; follow-up).
- Prettier applied to new files and files clean at base only.
### Smoke test (2026-11-10)
check.sh --frontend-only: typecheck, lint, 418 tests, build pass.

PR: https://github.com/archit342000/My-AI/pull/108, branch bugfix/thought-box-timeline, base bugfix/transcript-turn-model

## Verification

### Acceptance review (2026-11-10)
Criteria ticked on the live and e2e results recorded in the PR's Testing section (checks run on throwaway backends during the autopilot run; scripts in `MYAI-55-evidence/`).
Left unticked, no PASS recorded:
- criterion 2: header active/finished state not recorded as checked live
- criterion 6: retry/redact notice not verified live (the stub emits no redact)

## Review history
### Round 1 - 2026-11-10
Verdict: Request changes (4 MAJOR). Single Haiku reviewer.
- R1-1 [MAJOR] statusOf preferred a stale event over a newer running tool - Fixed: one backward scan; test.
- R1-2 [MAJOR] raw px/rem in new CSS - Fixed: space/radius tokens and two named custom properties (--thought-action-size, --thought-inset); 10px/24px offsets kept as legacy geometry values.
- R1-3 [MAJOR] non-null assertions - Fixed.
- R1-4 [MAJOR] second component in TimelineEntry.tsx - Fixed: ClippedText.tsx with test.
- R1-5 [MINOR] turnReasoning/turnTools/lastEvent unused in production - Rejected: MYAI-54 selectors with their own tests, used by stream and reducer tests; removal is churn outside this ticket.
- R1-6 aria-label on a div - Fixed (role=group). R1-7 prettyArgs fallback - Fixed (comment). R1-8 PendingUser.ordinal optional - Fixed (required). R1-10 sub-agent-item had no rule - Fixed. R1-11 docs under Known gaps - Fixed (moved to Streaming). R1-12 weak no-bubble test - Fixed.
- R1-9 [MINOR] avatar padding-top differs - Rejected: measured live, avatar y within 0.6px of legacy.
- R1-13 [NIT] whole-chat delete leaves stale keys - Rejected: a few booleans per session, no behaviour effect.
Resolution: check.sh passes (420 tests); live V1-V7, geometry (header, container, content wrapper x/w within 1px) and e2e re-run after the fixes. Not verified live: retry notice (stub emits no redact), event rows and sub-agent groups (unit tests only).


## Log
- 2026-11-10: created
- 2026-11-10: added to epic MYAI-53
- 2026-11-10: linked blocked_by MYAI-54
- 2026-11-10: linked blocks MYAI-60
- 2026-11-10: plan validated, 2 rounds
- 2026-11-10: linked blocks MYAI-59
- 2026-11-10: acceptance criteria reviewed against the recorded results (5 ticked, 2 left open)
- 2026-11-10: closed by the user after the PR merged into develop; 2 acceptance criteria left unticked as known limits (see Verification, Acceptance review)
