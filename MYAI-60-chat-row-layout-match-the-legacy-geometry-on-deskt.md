---
id: MYAI-60
title: "Chat row layout: match the legacy geometry on desktop"
status: done
epic: MYAI-53
created: 2026-11-10
updated: 2026-11-10
links:
  blocked_by: [MYAI-55]
  conflicts_with: [MYAI-59]
---

## Description
At 1440px the assistant row differs from legacy: bubble 44px narrower and shifted, thought header 9px shorter, avatar 15px higher, model label smaller and showing the raw id, action rows and notices misaligned, title rename field and edit box unstyled or unfocused, links unreadable in dark.

Findings (MYAI-52, Verification): A-35, A-36, A-37, A-38, A-39, A-40, A-42, A-43, A-44, A-45, A-46. Evidence and the live test rig are in `~/.claude/tickets/My-AI/MYAI-52-evidence/`.

## Acceptance criteria
- [x] Metric diff against legacy at 1440px shows no difference above 1px for bubble, thought header, avatar, model label and footer
- [x] Model label shows the legacy display name
- [x] Action rows, Stopped/Retry and inline errors align with the bubble
- [x] Chat title rename field looks like the title pill; edit box is focused on open and has no native resize handle
- [x] Links and code blocks are readable in both themes
- [x] Files button is dimmed when the chat has no files

## Plan
**Date:** 2026-11-10  **Status:** Validated

### Objective
Close the remaining differences between the React chat row and the legacy one at 1440px: model label text and style, action rows and notices aligned with the bubble, a styled title rename field, a focused edit box, readable links and code in both themes, and a dimmed files button for chats without files.

### Context
- **Requirement:** this ticket's Description and Acceptance criteria (findings A-35 to A-40 and A-42 to A-46 in MYAI-52).
- **Assumes merged:** MYAI-54 (one row per turn) and MYAI-55 (legacy row structure: `.assistant-header-row`, full-width `.thought-timeline-wrapper` and `.message-content-wrapper`; thought header geometry). A-35, A-36 and A-37 are closed by MYAI-55's layout; this ticket verifies them and fixes what is left.
- **Rules:** `docs/standards/frontend.md` (typed API shapes in `src/api/`, query keys defined in `api/`, pure logic in `src/lib/` with tests, no inline styles except `// dynamic-style`, CSS custom properties, focus visible), `docs/frontend.md`.
- **Legacy reference:**
  - Model label: `static/js/model-manager.js` builds a display name per configured role from `GET /api/models/config` (`getModelDisplayName`: role key capitalised, with fixed names for `main`, `text`, `vision`, `vision2`, `coder`, followed by the last path segment of the model id in brackets) and `resolveModelDisplayName` falls back to the raw id. `static/js/message-manager.js:203-205`: footer `display:flex; margin-top:4px; padding:0 4px`, label `0.65rem`, weight 500, opacity 0.8; the action row is rendered inside `.message-content-wrapper`, after the footer.
  - Files button: `static/script.js` (block "Files visibility state"): opacity 0.35 and not clickable unless the chat is in file-system mode or a workspace is open.
  - Measured (MYAI-52 `metrics/d-chat-long.txt`): label 10.4px/500/0.8; footer height 20.9px; user action row 94x26.
- **Current code (`frontend/src/`):**
  - `features/chat/MessageList.tsx`: `.bot-model-label` shows the raw `model` id; `MessageActions` for an assistant turn and the `.turn-notice` / `.chat-error` blocks are siblings of the row body, so they start at the avatar's x, not the bubble's; the edit `Textarea` has no autofocus.
  - `features/chat/MessageActions.tsx`: `IconButton size="sm"` (28px).
  - `features/chat/ChatPage.tsx` `ChatTitle`: the rename `<input>` reuses `.chat-title-display` and the wrapper has an inline `style` block (one entry in `test/inline-style.test.ts` `BASELINE`).
  - `styles/legacy.css`: `.bot-model-label` (0.6rem, 600); no colour rule for links inside `.message-content`; `styles/components.css` has `.message-actions-container .ui-icon-button`, `.turn-notice`, `.chat-error`, "Message edit box".
  - `api/settings.ts`: `ModelConfig` types only `general.text` and `research.main`; `modelsApi.config`; the query key `['models', 'config']` is written inline in `features/composer/Composer.tsx`.
  - `app/RootLayout.tsx`: `#nav-files-btn` has one state.

### Approach
- **Model display name.** `lib/model-options.ts` gains `modelDisplayNames(config)` (role map to display names with the legacy naming rules) and `displayModelName(id, names)` (fallback: the id). `ModelConfig` is widened to string maps for `general` and `research`; the key moves to `settingsKeys.modelConfig`. A hook `features/chat/useModelDisplayName.ts` reads the cached config; the label shows the display name and its CSS takes the legacy inline values for size, weight and opacity (the uppercase and letter-spacing from `styles/legacy.css` `.bot-model-label` stay, as in legacy). The hook and the composer share one query definition (`modelConfigQuery` in `api/settings.ts`: key, function and the composer's current stale time), so both observers use the same options.
- **Actions and notices inside the bubble column.** `MessageActions` for an assistant turn, the Stopped/Retry notice and the inline error render inside `.message-content-wrapper` after the footer, as legacy does, so they share the bubble's left edge. Action buttons are 26px with an 8px gap.
- **Title rename field.** A dedicated `.chat-title-input` class that matches the pill (font, size, padding, radius, border, width fitted to the header); the wrapper's inline styles move into the existing `.chat-header-content` rule's companion in `components.css`.
- **Edit box.** The textarea takes focus when the box opens (`autoFocus`, with an `onFocus` handler that moves the caret to the end), and has `resize: none` (it already grows with its content).
- **Links and code.** Links inside message content and artifact previews use the accent colour in both themes (legacy uses the browser default, which is unreadable on dark: a deliberate difference). In dark, highlighted code inside `.code-block-wrapper` gets a transparent background so the block has one surface; the light theme's code block already has one surface and is left as is.
- **Files button.** Dimmed (opacity 0.35) while the open chat has no files; it stays clickable, because the React files panel can create files in any chat (legacy disables it; recorded difference). A hook `features/artifacts/useHasArtifacts.ts` (new) runs the artifacts list query for the route's chat id (read with `useMatch('/chat/:chatId')`) under the same key the panel uses, exported from `ArtifactPanel`'s module as `artifactsKey(scope)` in `api/filesystem.ts`.
- **Rejected:** hard-coding role names in the component (the mapping is data from the proxy config); disabling the files button as legacy does (would block a working feature).

### Out of scope
- Thought box and row structure: MYAI-55. Mobile values: MYAI-59. Composer buttons: MYAI-61.
- Hover lift of the bubble and the model picker's labels (not in the findings).

### Steps
#### Step 1: Model display names
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/lib/model-options.ts` (modify: new `modelDisplayNames`, `displayModelName`), `frontend/src/lib/model-options.test.ts` (modify), `frontend/src/api/settings.ts` (modify: `ModelConfig`, `settingsKeys.modelConfig`, `modelConfigQuery`), `frontend/src/features/composer/Composer.tsx` (modify: use the key), `frontend/src/features/chat/useModelDisplayName.ts` (create), `frontend/src/features/chat/useModelDisplayName.test.tsx` (create)
- **Change:** as in Approach ("Model display name").
- **Verification:** unit tests: `vision_small` with `Google/Gemma4-26B-A4B-it` gives `Vision_small (Gemma4-26B-A4B-it)`; `text`, `main`, `vision`, `vision2`, `coder` give the fixed names; an unknown id falls back to itself; the hook returns the raw id while the config is not loaded.

#### Step 2: Label, actions and notices in the bubble column
- **Status:** todo
- **Depends on:** 1
- **Files:** `frontend/src/features/chat/MessageList.tsx` (modify: label text, where `MessageActions`, `.turn-notice` and `.chat-error` render), `frontend/src/features/chat/MessageActions.tsx` (modify only if a prop is needed for placement), `frontend/src/features/chat/MessageList.test.tsx` (modify), `frontend/src/styles/components.css` (modify: "Chat transcript" block: `.bot-message-footer`, `.bot-model-label`, `.message-actions-container .ui-icon-button`, `.turn-notice`, `.chat-error`), `frontend/src/test/css-coverage.test.ts` (modify: drop `bot-message-footer` from `TODO_UNSTYLED` once it has a rule)
- **Change:** as in Approach ("Actions and notices inside the bubble column") and the label values from Context.
- **Verification:** component tests: the label shows the display name; the action row, the Stopped notice and the inline error are descendants of `.message-content-wrapper`.

#### Step 3: Title rename field and edit box
- **Status:** todo
- **Depends on:** 2
- **Files:** `frontend/src/features/chat/ChatPage.tsx` (modify: `ChatTitle`), `frontend/src/features/chat/ChatPage.test.tsx` (modify), `frontend/src/features/chat/MessageList.tsx` (modify: `UserTurn` editor focus), `frontend/src/features/chat/MessageList.test.tsx` (modify), `frontend/src/styles/components.css` (modify: new `.chat-title-input`, header content class; "Message edit box" block), `frontend/src/test/inline-style.test.ts` (modify: remove the `ChatPage.tsx` baseline entry)
- **Change:** as in Approach ("Title rename field", "Edit box").
- **Verification:** component tests: opening the editor focuses the textarea, and Escape then closes it; the rename input has the class `chat-title-input` and no `style` attribute on its wrapper. The inline-style guard passes with the lower baseline.

#### Step 4: Links, dark code blocks, files button state
- **Status:** todo
- **Depends on:** 3
- **Files:** `frontend/src/styles/components.css` (modify: link colour in message content; dark `code.hljs` background in `.code-block-wrapper`; `.top-right-btn` dimmed state), `frontend/src/app/RootLayout.tsx` (modify: dimmed state for `#nav-files-btn`), `frontend/src/app/RootLayout.test.tsx` (modify), `frontend/src/features/artifacts/useHasArtifacts.ts` (create), `frontend/src/features/artifacts/useHasArtifacts.test.tsx` (create), `frontend/src/api/filesystem.ts` (modify: `artifactsKey`), `frontend/src/features/artifacts/ArtifactPanel.tsx` (modify: use `artifactsKey`)
- **Change:** as in Approach ("Links and code", "Files button").
- **Verification:** component tests: on a chat with no files the button has the dimmed class and is still enabled; with a file it does not. Colour checks are in Step 5.

#### Step 5: Geometry and colour check against legacy, docs, full checks
- **Status:** todo
- **Depends on:** 2, 3, 4
- **Files:** `docs/frontend.md` (modify: Conventions line on the model display name)
- **Change:** docs match the code.
- **Verification:** MYAI-52 rig (`~/.claude/tickets/My-AI/MYAI-52-evidence/scripts/up.sh`, `node metrics.mjs d '/chat/{long}'`): no difference above 1px for `.bot-message .avatar`, `.thought-container`, `.message-content-wrapper`, `.bot-message-footer`, `.bot-model-label` and `.message-actions-container`, and the label's font size, weight and opacity equal legacy's. With `scripts/s8.mjs`: the link colour is the accent colour in light and dark, the dark `code` background is transparent, and `.edit-textarea` has `resize: none`. Then from `frontend/`: `npm run typecheck`, `npm run lint`, `npm run test`, `npm run build`; from the repo root `pytest tests` and `scripts/check.sh --frontend-only`.

### Tests
- Unit: `lib/model-options.test.ts`, `features/chat/useModelDisplayName.test.tsx`.
- Component: `MessageList.test.tsx`, `ChatPage.test.tsx`, `RootLayout.test.tsx`.
- Guards: `test/css-coverage.test.ts`, `test/inline-style.test.ts`.
- Live comparison: `metrics.mjs` and `s8.mjs` against the legacy instance.

### Risks and open questions
- **The stub config in the rig names roles differently from production;** the unit tests use the production role keys from `inference_proxy/config.json`.
- **Accent-coloured links and an always-clickable files button differ from legacy** on purpose; both are recorded in Approach.
- **Shared file:** `MessageList.tsx` is also changed by MYAI-62 and MYAI-63; this ticket lands after MYAI-55.

### Success criteria
- [ ] Metric diff against legacy at 1440px shows no difference above 1px for bubble, thought header, avatar, model label and footer
- [ ] Model label shows the legacy display name
- [ ] Action rows, Stopped/Retry and inline errors align with the bubble
- [ ] Title rename field matches the pill; edit box is focused on open with no resize handle
- [ ] Links and code blocks are readable in both themes
- [ ] Files button is dimmed when the chat has no files
- [ ] Checks pass
### Reviewer brief
- **Objective:** close the remaining 1440px differences from legacy in the chat row: model label, action and notice alignment, title rename field, edit box focus, readable links and code, dimmed files button.
- **Decisions:** display names from `GET /api/models/config` with the legacy naming rules (`modelDisplayNames`, `displayModelName`, `useModelDisplayName`, shared `modelConfigQuery`); label keeps legacy uppercase and takes legacy size, weight and opacity; actions, Stopped/Retry and inline errors render inside `.message-content-wrapper`; 26px action buttons; `.chat-title-input`; edit textarea autofocus and `resize: none`; accent-coloured links in both themes and a transparent dark `code.hljs` background (deliberate differences from legacy); files button dimmed but clickable when the chat has no files (`useHasArtifacts`).
- **Out of scope:** thought box and row structure (MYAI-55), mobile values (MYAI-59), composer buttons (MYAI-61), bubble hover lift, model picker labels.
- **Success criteria:** no metric difference above 1px against legacy for bubble, thought header, avatar, label and footer; legacy display name; aligned actions and notices; styled rename field and focused edit box; readable links and code in both themes; dimmed files button for a chat without files; checks pass.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- **Round 1:** validator PASS (9 minor). Judged PASS after checking `styles/legacy.css` `.bot-model-label`, `ArtifactPanel.tsx` query key, `Field.tsx` `Textarea` and `ChatPage.tsx`. Fixed inline: uppercase kept and stated; files button dims on "no files" alone (matches the criterion); `useHasArtifacts` and `artifactsKey` named; caret mechanism; `resize: none` check; light code block stated as unchanged; step dependencies reflect shared files; wrapper class named; one shared query definition.

## Implementation notes
Branch bugfix/chat-row-geometry, base bugfix/thought-box-timeline (autopilot batch item 11).
### Implementation progress
- [x] Step 1: model display names - lib/model-options.ts (`modelDisplayNames`, `displayModelName`), `modelConfigQuery`/`settingsKeys.modelConfig` in api/settings.ts, `useModelDisplayName`
- [x] Step 2: label shows the display name; action row, Stopped notice and inline error render inside the answer column (BotBody `footer`); 26px action buttons; `.chat-error` margin
- [x] Step 3: `.chat-title-input` and `.chat-title-row` (inline style removed, ChatPage baseline entry dropped); edit textarea autofocus with caret at the end, `resize: none`
- [x] Step 4: accent links, transparent dark `code.hljs`, `artifactsKey`, `useChatHasNoFiles`, dimmed (still clickable) files button
- [x] Step 5: docs/frontend.md Conventions
Deviations: the hook is `useChatHasNoFiles` (file named after it), not `useHasArtifacts`; a chat's file list always contains its empty `workspace` folder, so folders do not count as files; `queryFn` of `modelConfigQuery` is a wrapper so spies on `modelsApi.config` work.
### Smoke test (2026-11-10)
check.sh --frontend-only: typecheck, lint, 435 tests, build pass.
Live (rig: stub + React backend + legacy backend): metrics at 1440px show no chat-row difference above 1px for avatar, thought container, answer wrapper, footer, label and action row; label `GENERAL TEXT (AUDIT-MODEL)` with a mocked config; actions and the Stopped notice share the answer's x (464); edit box focused, caret at end, resize none; rename field focused with the pill's font/radius; links accent in light and dark; dark code background transparent; files button 0.35 for a chat without files.
Rig note: the first rigs of this batch (items 9 and 10) pointed their stub at the wrong script folder, so `/api/models` answered 500 there; fixed here.

PR: https://github.com/archit342000/My-AI/pull/111, branch bugfix/chat-row-geometry, base bugfix/thought-box-timeline

## Verification

### Acceptance review (2026-11-10)
Criteria ticked on the live and e2e results recorded in the PR's Testing section (checks run on throwaway backends during the autopilot run; scripts in `MYAI-60-evidence/`).
All criteria covered.

## Review history
### Round 1 - 2026-11-10
Verdict: Request changes (1 MAJOR). Single Haiku reviewer.
- R1-1 [MAJOR] files-button dim never refreshed after a turn created files - Fixed: send-turn invalidates the chat's file list when a turn ends; tests (send-turn, RootLayout un-dim).
- R1-2 hook's folder test differed from the panel's - Fixed: uses `isDirectoryEntry`; test for a folder without an id.
- R1-3 weak RootLayout test - Fixed: positive control and un-dim after invalidation.
- R1-4 caret reset on every focus - Fixed: placed once per editor open.
- R1-5 [MINOR] silent raw-id fallback when the config fails - Rejected: the raw id is the required fallback and the failure is a network error already visible to the user as a missing label name; adding logging has no convention here.
- R1-6 wrapper created a QueryClient per render - Fixed. R1-7 docs query keys sentence - Fixed. R1-8 stray blank line - Fixed. R1-9 duplicated config shape - Fixed (imports ModelConfig).
- R1-10 [NIT] raw 26px/32rem/3px in CSS - Rejected: 26px is the legacy button size the ticket requires; no size tokens exist for these.
Resolution: check.sh passes (437 tests); live checks re-run (label, edit box, files button dim, notice alignment, geometry unchanged). Round 1 fixes were not re-reviewed.


## Log
- 2026-11-10: created
- 2026-11-10: added to epic MYAI-53
- 2026-11-10: linked blocked_by MYAI-55
- 2026-11-10: linked conflicts_with MYAI-59
- 2026-11-10: plan validated, 1 rounds
- 2026-11-10: acceptance criteria reviewed against the recorded results (6 ticked, 0 left open)
- 2026-11-10: closed by the user after the PR merged into develop
