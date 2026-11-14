---
id: MYAI-93
title: "Adopt the design system: everything after the foundations, in one change"
status: done
epic: MYAI-75
created: 2026-11-11
updated: 2026-11-11
links:
  blocked_by: [MYAI-76]
  relates_to: [MYAI-94, MYAI-95, MYAI-96]
  split_from: [MYAI-77, MYAI-78, MYAI-79, MYAI-80, MYAI-81, MYAI-82, MYAI-83, MYAI-84, MYAI-85, MYAI-86, MYAI-87, MYAI-88, MYAI-89, MYAI-90, MYAI-91]
---

## Description
Convert the whole React frontend to the Console at Rest design in one change, on top of the foundations (MYAI-76). This ticket merges MYAI-77 to MYAI-91 at the user's request (2026-11-11): the scope of each is kept below as a part.

Design system: repository `console-at-rest` (github.com/archit342000/console-at-rest, local `~/Coding/repos/console-at-rest`): `RULEBOOK.md` (v1.2), `tokens.css`, `tokens.json`, `reference/console-at-rest.html`. Where the React code and the legacy UI in `static/` differ, the reference page is right. Frontend only: a backend gap found on the way becomes its own ticket and is not fixed here.

### Part 1: Background: dot sphere and night stars to the new spec (was MYAI-77)
Update the ambient background (`frontend/src/lib/particles.ts`, `components/background`) to Rule book Part 3: 75% size, 600 dots on a computer and 250 on a phone placed by the golden angle, oval stretch to the screen's shape, Azure dot colours, strength by screen kind (open, reading, working), still stars at night, no haze. It reacts to the pointer, ripples on send and pulses while the app is working; pressing the app's mark sends a ripple.

### Part 2: Core building blocks: buttons, inputs, choices, menus, labels (was MYAI-78)
Build the shared pieces every screen uses, to Rule book Part 7.1 to 7.5 and 7.14, in `frontend/src/components/ui`: the five button kinds with all states (including busy, small, icon-only with tips, link, toggle), text boxes of every kind used by My-AI, our own drop-down (bottom sheet on phones), switch, tick box, side-by-side pick-one / tabs, pick-one circles, slider, tags, menus (icons, groups, keys, ticked, off, menu inside a menu), hover tips, chips, count badges, the status light and typewriter label, tick rule, icons redrawn in the one outline style, and the keyboard focus ring.

### Part 3: Layers that open on top: pop-ups, windows, sheets, messages (was MYAI-79)
Rebuild the things that open over the app to Rule book Part 7.11 and Part 6: the confirming pop-up (only for what cannot be undone), the large window shell (title, status, close), the bottom sheet on phones, the small pop-up attached to a button, brief messages including one with Undo, the notice strip, the whole-screen wait, and the bigger view with zoom. Replaces `Modal`, `ConfirmDialog`, `Toast`.

### Part 4: App frame: navigation panel, header and page shells (was MYAI-80)
Rebuild the frame around every screen to Rule book Part 5: the floating navigation panel (New chat, temporary chat, new workspace, Workspaces, chats grouped by day with a per-chat menu including Move to a workspace, Settings / System / Logs), its collapsed icon rail with name tags, the content panel with header (title, status light, actions) and tick rule, the optional resizable side panel, and the full-screen page shell with Back used by Settings. Phone drawer behaviour is in the phone ticket.

### Part 5: Home and the message box (was MYAI-81)
Restyle Home and the composer to the design: the greeting over the open sphere, the message box (attach, Tools menu with five switches and chips for what is on, send turning into Stop), slash-command suggestions, upload pills with progress and failure, the file drop area, and temporary chat (notice strip, dashed panel edge, Save chat).

### Part 6: Conversation: messages, thought process and answer content (was MYAI-82)
Restyle the chat thread to the design: user messages (no avatars, Read more on long ones, skill names highlighted, edit in place), answers (model and time label, streaming with Stop), one folded Thought process box holding thoughts and tool calls in order with an Open bigger view, and all answer content: headings, lists, code box with Copy, notes, tables, maths, diagrams with the bigger view, numbered sources, message actions. Also the question card, research plan card and helpers card.

### Part 7: Files panel and editor (was MYAI-83)
Rebuild the Files panel and editor (`features/artifacts`) to the design, bringing back what the legacy UI had: folder tree with counts, search across names and contents with the matching line, per-file menu and right-click (run, download, rename or move, delete), new file and folder, the where-and-name small pop-up (attached, per step 4), editor with line numbers and current line, language and version labels, saving by itself, Code / Preview with live tick boxes, undo, redo, copy, run with an output strip, research-plan Approve / Suggest changes, a resizable panel, and Full screen.

### Part 8: Workspace page (was MYAI-84)
Restyle the Workspace page (`features/workspace`) to the design: header with the workspace icon (icon picker), name, rename and delete, chat cards, and the file browser side by side with the editor. Includes the workspace menu in the navigation panel.

### Part 9: Settings as a full-screen page (was MYAI-85)
Move all settings out of dialogs into one full-screen Settings page to the design: a section list (tabs on a phone) and one scrolling column with Chat, Models, Personas, Skills, Memory, Agents and System, using the add / edit / delete list pattern, the speed test with its chart, and the whole-screen wait while models switch. Settings apply at once with no Save button. Every setting the app has today keeps a place.

### Part 10: Logs page (was MYAI-86)
Restyle the Logs page (`features/logs`) to the design: Network / Events / App / Database as tabs, a filter, one-line entries that fold open for detail, even spacing, and the designed empty and loading states.

### Part 11: Tool windows: browser, code runs, version history (was MYAI-87)
Rebuild the three tool windows (`features/tools`, versions) on the large-window shell: the browser window (starting, live, not running with Try again), code run history (foldable runs with code, output or error, and how it ended), and version history (versions listed, the chosen one shown, Restore).

### Part 12: Awkward states and dead ends on every screen (was MYAI-88)
Give every screen its empty, loading, problem, offline and long-text versions and the dead-end screens to Rule book 7.12 and 7.13: placeholder shapes matching the real layout, the notice strip with Try again, offline behaviour of the message box, one-line cut-off for long names, and the 'chat no longer exists' and 'something broke' screens with their dotted drawings.

### Part 13: Phones and Android behaviour (was MYAI-89)
Make the app behave as Rule book Part 6 on phones: every screen edge to edge with no inset cards, drawing behind the status and gesture bars, 48 touch targets, the navigation panel as a slide-in drawer, pop-ups as bottom sheets, the message box riding above the keyboard, Back undoing the newest layer first and only leaving from Home, and solid panels where blur is unavailable.

### Part 14: Wording pass (was MYAI-90)
Bring every label, button, message, error, time, date and number in the frontend in line with Rule book Part 9: verb-and-thing buttons, first-word capitals only, errors that say what happened and what to do, plain names for technical things with a hint, 24-hour times and day-before-month dates.

### Part 15: Remove the old look and final check (was MYAI-91)
Once every screen is converted: remove `legacy.css` and any styles, variables, fonts and components the new design replaced, update `docs/frontend.md` and `frontend/README.md`, and run the Rule book Part 10 checklist on every screen (computer, tablet, phone; day and night; solid panels; reduced motion; keyboard only).

## Acceptance criteria
**Part 1: Background: dot sphere and night stars to the new spec**
- [x] Sphere size, dot count, spacing, stretch and colours match the rule book on computer and phone
- [x] A shared "words on the sphere" helper draws the fade behind each line and button, re-measures on resize and font load, and uses the `--fade` values (rule book 3.3)
- [x] Strength follows the screen kind: full on Home, dimmed behind chats and settings
- [x] Ripple on send, pulse while thinking, ripple on pressing the app's mark
- [x] Still stars at night, none by day, no haze
- [x] Drawn once and still under reduced motion; no measurable slowdown while typing or streaming

**Part 2: Core building blocks: buttons, inputs, choices, menus, labels**
- [x] Each piece exists once, matches the reference page in every state, day and night
- [x] A control that is switched off for a changeable reason shows the reason
- [x] The browser's own drop-down is not used anywhere
- [x] Everything is reachable by keyboard with the shared focus ring; icon-only buttons have a tip and a spoken name
- [x] The developer preview page (`features/dev`) shows all of them

**Part 3: Layers that open on top: pop-ups, windows, sheets, messages**
- [x] Pop-ups are used only to confirm irreversible actions; everything else that was a dialog has a designed home
- [x] On a phone, pop-ups rise from the bottom and large windows fill the screen
- [x] Brief messages stack correctly, last 2.6 s, or 6 s with Undo
- [x] Escape and Back close the newest layer first; focus is kept inside and returned afterwards
- [x] Layer order follows the six fixed layers

**Part 4: App frame: navigation panel, header and page shells**
- [x] Navigation panel open and collapsed match the reference; the choice persists
- [x] Chat rows show time, selection and the per-chat menu (rename, move with sub-list, delete); right-click opens the same menu
- [x] Header shows the page title, status light and actions on every screen
- [x] The big content panel is tinted, not heavily blurred, so the sphere shows
- [x] Tablet, computer and very-wide widths lay out as the rule book describes

**Part 5: Home and the message box**
- [x] Home shows the greeting over the sphere at full strength with no panel over it
- [x] The greeting and the header's status word have the fade behind each line of words (rule book 3.3)
- [x] Tools menu matches the design, including tools that are off with the reason shown
- [x] Slash suggestions, upload states and drop-to-attach match the reference
- [x] Temporary chat is clearly marked and can be saved
- [x] All of it works on a phone above the keyboard

**Part 6: Conversation: messages, thought process and answer content**
- [x] No avatars; long sent messages fold; skill names are highlighted
- [x] Thoughts and tool calls appear together in one Thought process box, folded by default, in the order they happened
- [x] Every kind of answer content matches the reference; wide content scrolls inside its own box
- [ ] Question, research plan and helpers cards match the reference
- [x] Streaming, Stop, edit, retry, copy and delete all behave as designed

**Part 7: Files panel and editor**
- [x] Every feature listed works in the Files panel beside a chat and in a workspace
- [x] Edits save by themselves with a Saving / Saved light; there is no Save button
- [x] Full screen fills the window and returns exactly where it was
- [x] On a phone: the list, then the editor, edge to edge
- [x] Unsaved work is never lost when switching files or closing the panel

**Part 8: Workspace page**
- [x] Page matches the reference on computer and phone
- [x] Workspace icon can be changed with the icon picker and shows in the navigation panel
- [x] Empty workspace shows the designed empty screen
- [x] Rename and delete behave as designed (delete confirms)

**Part 9: Settings as a full-screen page**
- [x] Settings opens as a page with Back, not a pop-up; System opens the same page at its section
- [x] All seven sections are present and no existing setting is lost
- [x] Changes apply at once and show Saving / Saved
- [x] Personas, skills and memory use the shared list pattern; deletes confirm
- [x] Speed test shows the chart, four figures and Stop; switching models shows the whole-screen wait

**Part 10: Logs page**
- [x] Page matches the reference on computer and phone
- [x] Entries fold open in place with one tint; long values wrap or scroll inside their box
- [x] Filter and count behave as designed

**Part 11: Tool windows: browser, code runs, version history**
- [x] All three open from where the design puts them and match the reference
- [x] Each has its empty, loading and failed states
- [x] On a phone each is a full screen that Back closes

**Part 12: Awkward states and dead ends on every screen**
- [x] Every screen has all five states and they match the reference
- [x] A chat or workspace that no longer exists shows the dead-end screen, not a blank or raw error
- [x] An unexpected failure shows 'Something broke on our side' with a way out
- [x] No error code is shown unless asked for

**Part 13: Phones and Android behaviour**
- [x] No screen is an inset card on a phone
- [x] All touch targets are at least 48
- [ ] Back order matches the rule book on a real Android device
- [x] The message box stays visible above the keyboard
- [x] Solid-panel mode is chosen automatically where blur is unsupported

**Part 14: Wording pass**
- [x] No button reads Submit, OK or Yes
- [x] Only first words and proper names are capitalised
- [x] Every error message says what happened and what to do next
- [x] Times, dates, durations and numbers follow Part 9 everywhere

**Part 15: Remove the old look and final check**
- [x] `legacy.css` and unused old components are gone and nothing references them
- [ ] No raw colour, size, corner, shadow or speed remains outside the shared values
- [x] The Part 10 checklist passes on every screen, with evidence recorded
- [x] Frontend docs describe the new structure and point to the design-system repository
- [x] `scripts/check.sh --frontend-only` passes

**Whole change**
- [x] No feature or setting available before the change is lost
- [x] Checked in a browser on computer, tablet and phone, day and night, on every screen
- [x] `scripts/check.sh --frontend-only` and the Playwright suite pass

## Plan
**Date:** 2026-11-11  **Status:** Validated

### Objective
Convert every screen, pop-up and state of the React frontend to the Console at Rest design (rule book v1.2 and its reference page), on top of the shared values already in place, and remove the old look. One change, fifteen parts, no feature or setting lost.

### Context
- Requirement: the ticket's fifteen parts and their acceptance criteria. Design source: `~/Coding/repos/console-at-rest/RULEBOOK.md` (Parts 2 to 10), `reference/console-at-rest.html` (markup and CSS of every piece and screen), `tokens.css` (synced to `frontend/src/styles/tokens.css`).
- Rules: `docs/standards/frontend.md` (shared values only, one component per file, hooks and pure logic with tests, primitives reused, no `any`), `docs/standards/testing.md`, `docs/standards/docs.md` (200-line limit on `docs/*.md`, 100 on READMEs), `docs/frontend.md`, `frontend/README.md`, `docs/standards/gitflow.md`.
- Current code (all under `frontend/src/`):
  - Styling: `styles/legacy.css` (6,290 lines) and `styles/components.css` (3,570 lines), bridged by `styles/bridge.css`. 65 class names and 14 ids used in TSX are styled only by `legacy.css`. Guard tests: `test/css-coverage.test.ts`, `test/inline-style.test.ts`, `lib/design-tokens.test.ts`.
  - Tests lean on class and id selectors: about 205 selector uses over 99 distinct names in `src/**/*.test.*` and `e2e/*.spec.ts` (for example `#sidebar`, `.chat-list-item`, `#chat-textarea`, `.bot-message`).
  - Frame: `app/RootLayout.tsx`, `app/Sidebar.tsx`, `app/routes.tsx` (routes `/`, `/chat/:chatId`, `/workspace/:workspaceId`, `/logs`, `/dev/ui`), `features/sidebar/RecentChats.tsx`, `features/sidebar/IconPickerDialog.tsx`.
  - Primitives in `components/ui/`: `Button`, `IconButton` (in `Button.tsx`), `Field`, `Select`, `Toggle`, `RadioCards`, `SegmentedControl`, `Slider`, `Badge`, `Menu`, `Popover`, `Tooltip`, `Modal`, `ConfirmDialog`, `PromptDialog`, `Toast`, `EmptyState`; icons in `components/icons/`.
  - Screens: `features/home/HomePage.tsx`, `features/composer/` (`Composer.tsx`, `AttachmentChip.tsx`, `HelpDialog.tsx`), `features/chat/` (`ChatPage.tsx`, `MessageList.tsx`, `ThoughtBox.tsx`, `TimelineEntry.tsx`, `ThoughtFullView.tsx`, `MessageActions.tsx`, `ClarificationPrompt.tsx`, `ResumeBanner.tsx`, `ClippedText.tsx`), `components/markdown/`, `features/artifacts/` (`ArtifactDrawer.tsx`, `ArtifactPanel.tsx`, `CodeEditor.tsx`, `MoveFileDialog.tsx`, `VersionsDialog.tsx`), `features/workspace/WorkspacePage.tsx`, `features/logs/LogsPage.tsx`, `features/tools/` (`ToolsMenu.tsx`, `PortalDialog.tsx`, `CodeHistoryDialog.tsx`, `RunCard.tsx`).
  - Settings are dialogs opened through `state/modal-store.ts` (`DialogName`) and rendered by `features/settings/DialogHost.tsx`: `ChatSettingsModal`, `SystemSettingsModal`, `PreferencesDialog` (memory), `SkillsDialog`, `PersonasDialog`, `AgentConfigDialog`, `ModelsDialog`, `StealthDialog`, with `CrudList.tsx`, `SpeedTestPanel.tsx`, `SpeedChart.tsx`, `ChatDefaultsSection.tsx`, `GitSettingsSection.tsx`.
  - Background: `lib/particles.ts` (900 dots, hex palette `PARTICLE_COLORS`, jittered Fibonacci), `components/background/AmbientBackground.tsx`.
  - Backend routes the editor can use already exist (`backend/file_system/router.py`: create, patch, delete, folders, versions, diff, restore; `backend/tools/router.py`: `/code-execution/run-file`, history; portal init). There is no route that searches file contents.

### Approach
- **One stylesheet per area, shared values only.** New folder `styles/ds/` with `base.css`, `controls.css`, `layers.css`, `frame.css`, `home.css`, `chat.css`, `content.css`, `files.css`, `workspace.css`, `settings.css`, `logs.css`, `tools.css`, `states.css`, `phone.css`, `dev.css`, imported in that order from `main.tsx` after `tokens.css`. Rules are ported from the reference page's CSS. Each step moves its area's rules out of `legacy.css` and `components.css` into its `ds` file, rewritten to the design; when the last step ends the two old files and `bridge.css` are empty and are deleted.
- **Keep behaviour, change structure only where the design does.** Components keep their logic, stores, queries and API calls. Markup changes where the design differs (navigation panel, one Thought process box, settings page, tool windows, sheets). Rejected: rewriting components from the reference markup (loses tested behaviour).
- **Selectors that tests and scripts hook onto stay.** The ids and class names used by tests, `lib/scroll-lock.ts` (`SCROLL_AREAS`) and e2e specs are kept as hooks and restyled; a test selector changes only where the element itself is replaced, and then moves to a role or label query.
- **Settings become a route.** `/settings` and `/settings/:section` render a new `features/settings/SettingsPage.tsx` with seven section components built from the existing dialogs' bodies. `DialogName` keeps only `portal` and `code-history`; every `show(...)` of a removed name (`system-settings`, `chat-settings`, `preferences`, `skills`, `personas`, `agent-config`, `models`, `stealth`) and every Manage link becomes navigation to the section. The Chat section edits the open chat's values when it was opened from a chat (it says which chat) and the new-chat defaults otherwise, as the two dialogs do today. Every control in the eight dialogs gets a row in a section; a checklist of them is kept in the ticket and verified. Settings apply at once: existing immediate setters stay; forms that create or edit an item (persona, skill, memory, model) keep an explicit Save, as rule book 7.7 allows (decision made in the owner's place; listed for review). Section homes: Chat (per-chat and new-chat defaults: model, modes, persona, preferences, sampling, thinking), Models (model list and config, speed test), Personas, Skills, Memory (the preferences and memory dialog), Agents (agent config, stealth browsing, the Git agent section), System (theme, panels, runner and connection settings, delete all chats, signed-in user). Admin-only sections and rows stay hidden for other users through `useIsAdmin()`.
- **Layers.** `Modal` becomes the confirming pop-up; a new `Window` shell (title, status, close) carries tool windows and the bigger views; a new `Sheet` is what `Modal`, `Window`, `Menu` and `Select` turn into at phone width; `Toast` gains Undo and the 2.6 s / 6 s timings; new `Notice` strip and `HoldScreen`. Layer order uses the six `--z-*` values. Escape and Back keep going through `lib/modal-stack.ts`.
- **Sphere.** `lib/particles.ts` is rewritten to rule book 3.1 (600 / 250 dots by golden angle, 75% size, round except a slight stretch on phones, colours read from `--dot-1..5`, strength from `--sphere-open` / `--sphere-read` by a `data-dim` attribute the routes set, ripple and pulse entry points, night stars on a second canvas). A new `components/background/OnSphere.tsx` with `lib/sphere-fade.ts` draws the fade behind each line and button (rule book 3.3) and is used by the greeting, the header status word on Home and the dead-end screens.
- **Phones.** Rule book Part 6 in `ds/phone.css` plus `Sheet`; Back handling extends the existing modal stack with a history entry per open layer (new `hooks/useBackLayer.ts`).
- **Wording.** One pass over every user-facing string to rule book Part 9; `lib/labels.ts` and a new `lib/format-time.ts` hold 24-hour times, day-before-month dates and durations.
- **Backend gaps become tickets, not code.** Known now: no search across file contents (the Files search matches names, and contents only of files already loaded, until a route exists). Others found while implementing are added the same way.
- **Size.** The user asked for one plan and one change; the plan therefore has sixteen steps, one per part plus scaffolding, each kept to files, change and check.

### Out of scope
- Backend or API changes (tickets instead). Changes to the design itself. Extracting components into the design repository. The portfolio site and Android apps. The legacy UI under `static/` and `/legacy/`.

### Steps
#### Step 1: Scaffolding
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/styles/ds/*.css` (create, the fifteen files named above), `frontend/src/main.tsx` (modify), `frontend/src/lib/design-tokens.test.ts` (modify: the hex ban covers `styles/ds/`), `frontend/src/test/css-coverage.test.ts` (modify only if its file list is hard-coded)
- **Change:** create the files with a header each, wire the imports, put the page basics (body lettering, selection, scrollbars, focus ring, `.sec`/`.dat` typewriter labels, tick rule) in `base.css`.
- **Verification:** `npm run test` and `npm run build` pass; the app looks as before.

#### Step 2: Background (Part 1)
- **Status:** todo
- **Depends on:** 1
- **Files:** `frontend/src/lib/particles.ts` and `particles.test.ts` (modify), `frontend/src/lib/sphere-fade.ts` and `sphere-fade.test.ts` (create), `frontend/src/components/background/AmbientBackground.tsx` and its test (modify), `frontend/src/components/background/OnSphere.tsx` and test (create), `frontend/src/app/RootLayout.tsx` (modify: `data-dim`, canvas on every route), `frontend/src/lib/sphere-signal.ts` and test (create: a tiny publish/subscribe for `ripple` and `busy`), `frontend/src/features/composer/Composer.tsx` (modify: publish `ripple` on send), `frontend/src/state/stream-store.ts` (modify: publish `busy` when a turn starts and ends), `frontend/src/app/Sidebar.tsx` (modify: the app mark publishes `ripple`), `styles/ds/base.css`
- **Change:** as in Approach. `startParticles` returns an object `{ stop, ripple, setBusy }` in place of the bare cleanup function (its callers and tests change to match); `AmbientBackground` connects them to `sphere-signal`, which the composer's send, the stream store and the app mark publish to.
- **Verification:** unit tests for dot count, golden-angle placement, stretch rule, strength by `data-dim`, still frame; in the browser the sphere is round, 75%, dims behind a chat, ripples on send, stars only at night.

#### Step 3: Core building blocks (Part 2)
- **Status:** todo
- **Depends on:** 1
- **Files:** `frontend/src/components/ui/` existing files (modify), plus new `Checkbox.tsx`, `Tabs.tsx`, `Tag.tsx`, `Chip.tsx`, `StatusLight.tsx`, `TickRule.tsx`, `Kbd.tsx`, each with a test; `frontend/src/components/icons/icon-paths.ts` (modify: one outline style, missing icons added); `styles/ds/controls.css`; `frontend/src/features/dev/PrimitivesDemo.tsx` (modify: shows every piece and state)
- **Change:** five button kinds and states; inputs; own drop-down everywhere (no native `<select>` left in `src/`); switch; tick box; tabs; pick-one circles; slider; tags, chips, badges; menus with groups, keys, ticks, off items with a reason, sub-menus; tips; status light; labels. A switched-off control takes a `reason` shown as a tip and hint.
- **Verification:** component tests for new pieces and changed behaviour; `grep -rn "<select" src` is empty; dev page reviewed in both themes.

#### Step 4: Layers on top (Part 3)
- **Status:** todo
- **Depends on:** 3
- **Files:** `components/ui/Modal.tsx`, `ConfirmDialog.tsx`, `PromptDialog.tsx`, `Toast.tsx`, `components/ui/toast-store.ts`, `Popover.tsx`, `Menu.tsx`, `Select.tsx` (modify) with tests; new `components/ui/Window.tsx`, `Sheet.tsx`, `Notice.tsx`, `HoldScreen.tsx`, `Viewer.tsx` with tests; `components/markdown/ImageLightbox.tsx`, `MermaidDialog.tsx` (modify: use `Viewer`); `styles/ds/layers.css`
- **Change:** as in Approach. Every current dialog is classified, so the centred pop-up is left only for confirming what cannot be undone: `ConfirmDialog` uses stay pop-ups; `PromptDialog` (name or rename something) becomes the small pop-up attached to the control that opened it, built on `Popover`; `MoveFileDialog` and new file or folder become the reference page's where-and-name piece, also an attached small pop-up (step 8); `IconPickerDialog` becomes an attached small pop-up (step 9); `HelpDialog`, the thought bigger view, image and diagram views, portal, code history and versions become `Window`s; the eight settings dialogs become the page (step 10).
- **Verification:** tests for focus trap and return, Escape order across stacked layers, toast timings and Undo, sheet at phone width.

#### Step 5: App frame (Part 4)
- **Status:** todo
- **Depends on:** 3, 4
- **Files:** `app/RootLayout.tsx`, `app/Sidebar.tsx`, `app/useSidebarResize.ts`, `features/sidebar/RecentChats.tsx` (modify) with tests; new `app/PageHeader.tsx`, `app/PageShell.tsx` with tests; `styles/ds/frame.css`
- **Change:** floating navigation panel (actions, Workspaces, chats grouped by day with time and per-chat menu including Move to a workspace with a sub-list and right-click), collapsed icon rail with name tags, content panel with header (title, status light, actions) and tick rule, side panel slot, full-page shell with Back. `--side` 252 and `--rail` 70; the collapsed choice persists as today.
- **Verification:** `Sidebar.test.tsx`, `RootLayout.test.tsx`, `e2e/sidebar-workspace.spec.ts` updated and passing; frame checked at 820, 1280 and 2000 wide.

#### Step 6: Home and the message box (Part 5)
- **Status:** todo
- **Depends on:** 2, 5
- **Files:** `features/home/HomePage.tsx`, `features/composer/Composer.tsx`, `AttachmentChip.tsx`, `HelpDialog.tsx`, `features/tools/ToolsMenu.tsx` (modify) with tests; `styles/ds/home.css`
- **Change:** greeting through `OnSphere`; message box (attach, Tools menu with switches and chips for what is on, send turning into Stop), slash suggestions, upload pills with progress and failure, drop area, temporary chat (notice strip, dashed panel edge, Save chat).
- **Verification:** composer tests and `e2e/composer-attachments.spec.ts`, `chat-start.spec.ts`, `mobile-keyboard.spec.ts` pass.

#### Step 7: Conversation (Part 6)
- **Status:** todo
- **Depends on:** 4, 5
- **Files:** `features/chat/ChatPage.tsx`, `MessageList.tsx`, `ThoughtBox.tsx`, `TimelineEntry.tsx`, `ThoughtFullView.tsx`, `MessageActions.tsx`, `ClarificationPrompt.tsx`, `ResumeBanner.tsx`, `ClippedText.tsx`, `components/markdown/Markdown.tsx`, `StreamingMarkdown.tsx` (modify) with tests; `styles/ds/chat.css`, `styles/ds/content.css`
- **Change:** user messages without avatars, Read more, skill names highlighted, edit in place; answers with model and time label; one folded Thought process box with thoughts and tool calls in order and a bigger view in a `Window`; answer content (headings, lists, code box with Copy, notes, tables, maths, diagrams with `Viewer`, sources, actions); question, research plan and helpers cards.
- **Verification:** chat tests, stream fixtures and `e2e/thought-box.spec.ts`, `chat-send.spec.ts`, `turn-follow-ups.spec.ts`, `stop-races.spec.ts` pass; streaming, Stop, edit, retry, copy and delete are each exercised in the browser after the restyle (their logic is unchanged).

#### Step 8: Files panel and editor (Part 7)
- **Status:** todo
- **Depends on:** 4, 5
- **Files:** `features/artifacts/ArtifactDrawer.tsx`, `ArtifactPanel.tsx`, `CodeEditor.tsx`, `MoveFileDialog.tsx`, `artifact-tree.ts` (modify) with tests; new `features/artifacts/FileTree.tsx`, `FileSearch.tsx`, `EditorToolbar.tsx`, `RunOutput.tsx`, `useAutoSave.ts`, `file-search.ts` with tests; `api/filesystem.ts` (modify: add `codeExecApi.runFile` for the existing route `/api/tools/code-execution/run-file`) with its test; `styles/ds/files.css`
- **Change:** nested folder tree with counts, search (names, and contents of loaded files, showing the matching line), per-file menu and right-click, new file and folder, where-and-name small pop-up (attached, per step 4), line numbers and current line, language and version labels, saving by itself with a Saving / Saved light and no Save button, Code / Preview with live tick boxes, undo, redo, copy, run with an output strip, research-plan Approve / Suggest changes, resizable panel, Full screen. Unsaved text is flushed before switching file or closing.
- **Verification:** unit tests for the tree, search and auto-save (including flush on switch and close); `e2e/artifact-actions.spec.ts`, `artifact-overlay.spec.ts` updated and passing; a test opens Full screen, leaves it and finds the same file, scroll position and panel width.

#### Step 9: Workspace page (Part 8)
- **Status:** todo
- **Depends on:** 8
- **Files:** `features/workspace/WorkspacePage.tsx`, `features/sidebar/IconPickerDialog.tsx` (modify) with tests; `styles/ds/workspace.css`
- **Change:** header with icon (picker), name, rename, delete (confirms); chat cards; file browser beside the editor; designed empty screen.
- **Verification:** workspace tests and `e2e/new-workspace.spec.ts`, `sidebar-workspace.spec.ts` pass.

#### Step 10: Settings page (Part 9)
- **Status:** todo
- **Depends on:** 4, 5
- **Files:** new `features/settings/SettingsPage.tsx`, `sections/ChatSection.tsx`, `ModelsSection.tsx`, `PersonasSection.tsx`, `SkillsSection.tsx`, `MemorySection.tsx`, `AgentsSection.tsx`, `SystemSection.tsx`, `SavedLight.tsx` with tests; `app/routes.tsx`, `state/modal-store.ts`, `features/settings/DialogHost.tsx`, `CrudList.tsx`, `SpeedTestPanel.tsx`, `SpeedChart.tsx`, `ChatDefaultsSection.tsx`, `GitSettingsSection.tsx`, `forms.tsx` (modify); the eight dialog files and their tests (delete after their bodies and tests move); `app/Sidebar.tsx`, `features/composer/Composer.tsx`, `features/tools/ToolsMenu.tsx` (modify: navigate instead of `show`); `styles/ds/settings.css`
- **Change:** as in Approach, including the panels switch (Auto / Frosted / Solid) and theme in System, the speed test with its chart and four figures, and `HoldScreen` while models switch.
- **Verification:** before the dialogs are touched, a `### Settings checklist` is written to the ticket's Implementation notes listing every control in the eight dialog files (and `ChatDefaultsSection`, `GitSettingsSection`, `SpeedTestPanel`) with its section; each is ticked when it works on the page; section tests; `e2e/settings-parity.spec.ts`, `speed-test.spec.ts`, `user-roles.spec.ts` updated and passing.

#### Step 11: Logs page (Part 10)
- **Status:** todo
- **Depends on:** 3, 5
- **Files:** `features/logs/LogsPage.tsx` (modify) with test; `styles/ds/logs.css`
- **Change:** tabs for Network / Events / App / Database, filter with count, one-line entries that fold open in place, designed empty and loading states.
- **Verification:** logs tests pass; page checked at both widths.

#### Step 12: Tool windows (Part 11)
- **Status:** todo
- **Depends on:** 4
- **Files:** `features/tools/PortalDialog.tsx`, `CodeHistoryDialog.tsx`, `RunCard.tsx`, `features/artifacts/VersionsDialog.tsx` (modify) with tests; `styles/ds/tools.css`
- **Change:** each on the `Window` shell with empty, loading and failed states (browser: starting, live, not running with Try again); full screen with Back on phones.
- **Verification:** tests for the three windows' states.

#### Step 13: Awkward states and dead ends (Part 12)
- **Status:** todo
- **Depends on:** 5, 6, 7, 8, 9, 10, 11, 12
- **Files:** new `components/ui/Skeleton.tsx`, `DeadEnd.tsx`, `hooks/useOnline.ts` with tests; `components/ui/EmptyState.tsx`, `app/routes.tsx` (not-found), `app/UserGate.tsx`, each screen file from steps 6 to 12 (modify); new `app/ErrorBoundary.tsx` with test; `styles/ds/states.css`
- **Change:** empty, loading (placeholder shapes matching the layout), problem (notice strip with Try again), offline (message box behaviour) and long-text (one-line cut-off) versions of every screen; "chat no longer exists", "workspace no longer exists", "page not found" and "something broke on our side" dead ends with the dotted drawings; error codes only behind a "Show details".
- **Verification:** tests per state; each screen driven into each state in the browser.

#### Step 14: Phones (Part 13)
- **Status:** todo
- **Depends on:** 13
- **Files:** `styles/ds/phone.css`; `hooks/useBackLayer.ts` with test (create); `lib/modal-stack.ts`, `app/RootLayout.tsx`, `components/ui/Sheet.tsx` (modify); `e2e/mobile-layout.spec.ts`, `mobile-keyboard.spec.ts` (modify)
- **Change:** rule book Part 6: edge to edge, no inset cards, safe-area padding, 48 touch targets, navigation drawer, sheets, message box above the keyboard, Back closes the newest layer first and leaves only from Home. Automatic solid panels where blur is unsupported already exist (`resolveGlass` and `supportsBackdropBlur` in `lib/theme.ts`, applied by `public/theme-init.js`); this step makes the new phone surfaces obey `data-glass="solid"`.
- **Verification:** phone e2e project passes; a touch-target check in the phone spec asserts every button and link is at least 48 high or wide enough; Back order tested with `history.back()`; the existing e2e test for a browser without blur still passes and no element blurs on any phone screen in solid mode.

#### Step 15: Wording (Part 14)
- **Status:** todo
- **Depends on:** 13
- **Files:** every component with user-facing text; `lib/labels.ts` (modify), `lib/format-time.ts` and test (create); tests and specs that assert on text
- **Change:** rule book Part 9. A unit test scans `src/**/*.tsx` for button text `Submit`, `OK`, `Yes` and fails on any.
- **Verification:** the scan test passes; text assertions updated; times and dates checked in chat rows, messages, logs and versions.

#### Step 16: Remove the old look, docs, final check (Part 15)
- **Status:** todo
- **Depends on:** 14, 15
- **Files:** `styles/legacy.css`, `styles/components.css`, `styles/bridge.css` (delete), `main.tsx`, `lib/design-tokens.test.ts` (modify: in `styles/ds/` ban raw colours (hex, `rgb(`, `hsl(`), and `border-radius`, `box-shadow`, `z-index`, `transition` and `animation` durations that are not a `var()`; ban hex colours in `.ts`/`.tsx`; drop the bridge checks. Layout lengths that the shared values do not name are allowed only as multiples of the spacing steps or documented one-offs), `test/css-coverage.test.ts`, `test/inline-style.test.ts` (modify paths), `docs/frontend.md`, `frontend/README.md`, `docs/standards/frontend.md`, `docs/release.md` (the `legacy.css` mention), `lib/theme.ts` (comment that names `bridge.css`)
- **Change:** delete what nothing uses (styles, unused components, `PARTICLE_COLORS`, legacy font names); docs describe the new structure and point to the design repository, within their line limits.
- **Verification:** `grep -rn "legacy.css\|bridge.css\|components.css" frontend/src docs` finds nothing; `scripts/check.sh --frontend-only`, docs guardrails and `npm run e2e` (fresh backend) pass; rule book Part 10 checklist run on every screen, with the results table and screenshots recorded in the ticket's Verification section and evidence folder.

### Tests
- Vitest and Testing Library next to each new or changed file; `npm run typecheck`, `lint`, `test`, `build` from `frontend/`.
- Playwright: existing specs updated where markup changed, plus `e2e/design-system.spec.ts` (create in step 16): each screen at 1440, 820 and 390 wide in both themes has no horizontal page scroll, no console error and no text on the bare sphere outside `OnSphere`.
- Run e2e against the batch's throwaway stack (backend :5195 restarted fresh, dev server :5183).
- Gate: `scripts/check.sh --frontend-only` and `pytest tests`.

### Risks and open questions
- Size: the change touches most of `frontend/src`. Mitigation: steps are ordered so the app runs after each; checks run after each step; work is committed per step on the one branch and shipped as one pull request.
- Selector churn in tests: hooks are kept; where an element is replaced the test moves to role or label queries.
- Settings parity: a control could be dropped when eight dialogs become one page. Mitigation: the per-control checklist and `e2e/settings-parity.spec.ts`.
- Auto-save could lose or overwrite work. Mitigation: flush on switch, close and page hide; version history stays; tests for each.
- "Back order on a real Android device" cannot be checked on hardware here; it is tested with browser history in the phone project and reported as not verified on a device.
- Backend gap ticket to create: search across file contents.

### Success criteria
- [x] Every acceptance criterion of Parts 1 to 15 is met and checked in the browser on computer, tablet and phone, day and night
- [x] No feature or setting available before the change is lost (settings checklist complete; file editor features all present)
- [x] `legacy.css`, `components.css` and `bridge.css` are gone; styles use only shared values
- [x] `scripts/check.sh --frontend-only`, docs guardrails and the Playwright suite pass
- [x] Backend gaps found are recorded as tickets

### Reviewer brief
- Objective: convert every screen, pop-up and state of the React frontend to the Console at Rest design (rule book v1.2, reference page) and remove the old look, in one change, losing no feature or setting.
- Decisions: one stylesheet per area under `styles/ds/`, shared values only, old sheets and the bridge deleted at the end; components keep their logic and change markup only where the design does; ids and class names that tests hook onto stay; settings are a route (`/settings/:section`) with seven sections and forms that create or edit an item keep an explicit Save; the centred pop-up only confirms irreversible actions, naming and picking use small attached pop-ups, larger things use a `Window`, phones use a `Sheet`; the sphere follows rule book 3.1 and words on it get the per-line fade (3.3); wording follows rule book Part 9; a guard test bans raw colours, corners, shadows, layers and durations in `styles/ds/`; backend gaps are recorded as tickets, not fixed.
- Out of scope: backend or API changes; changes to the design; extracting components into the design repository; the portfolio and Android; the legacy UI under `static/`.
- Success: every part's acceptance criteria met on computer, tablet and phone, day and night; nothing lost; `legacy.css`, `components.css`, `bridge.css` gone; `scripts/check.sh --frontend-only`, docs guardrails and Playwright pass.

The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- Round 1: validator FAIL, judged FAIL. Valid BLOCKING: (1) dialogs that are not confirmations were left as pop-ups against rule book 7.11: step 4 now classifies every dialog; (2) step 2 lacked the files that make the sphere ripple and pulse: added `sphere-signal`, `Composer.tsx`, `stream-store.ts`, `Sidebar.tsx`. Valid MINOR, fixed: toast-store path; `runFile` is an addition; Save on create/edit forms flagged as a decision; settings checklist and section homes for Stealth and Git; retry, delete and Full screen verification; guard widened beyond colours and evidence location named; automatic solid panels referenced to existing code; commits per step, one pull request.
- Round 2 (diff-scoped): validator PASS, judged PASS. Three MINOR fixed mechanically: all removed dialog names become navigation; `startParticles` return shape stated; `lib/theme.ts` comment added to step 16.

## Implementation notes
### Autopilot run (2026-11-11)
- Mode: automatic (batch)
- Branch: feature/design-system-screens  PR base: feature/design-foundations  Starting commit: 8f561bc
- Dirty before start: none
- Work files: everything changed on the branch since 8f561bc (commits 0320b39..82c62b9 and earlier step commits)
- Counters: fix 2/10, review 2/5, re-verify 2
- Last completed stage: 6 ship  Next: none
- Hard blocker: none
- WIP commit: none

### Autopilot decisions (2026-11-11)
- batch: MYAI-77 to MYAI-91 merged into this ticket at the user's request; one plan and one pull request, not split despite the plan skill's size gate.
- plan: forms that create or edit an item (persona, skill, memory, model) keep an explicit Save (rule book 7.7); everything else applies at once.
- plan: the Chat section edits the open chat's values when opened from a chat and the new-chat defaults otherwise, as today's two dialogs do.
- plan: test hooks (ids and class names) are kept; selectors move to role or label only where an element is replaced.
- plan: Files search covers names and the contents of loaded files until the backend has a search route (MYAI-94 created).
- plan: work is committed step by step on the branch during implementation (an exception to "no commits before ship", because of the size), and shipped as one pull request.
- batch: e2e always against the throwaway stack (:5195 fresh, :5183); deploy after ship by copying the build into the live app's served folder.

### Baseline (2026-11-11)
- Same tree as the shipped foundations branch: `npm run typecheck`, `npm run lint` pass; `npm run test` 113 files, 900 tests pass; `npm run e2e` (fresh throwaway backend) 67 pass.

### Implementation progress
- Branch: feature/design-system-screens
- [x] Step 1: Scaffolding - `styles/ds/*.css` (15 files), `main.tsx`, `lib/design-tokens.test.ts`; `css-coverage.test.ts` needed no change (it lists `styles/` recursively). Unit: 901 pass.
- [x] Step 2: Background - `lib/particles.ts` (rewritten; returns `{ stop, ripple, setBusy, refresh }`), `lib/sphere-signal.ts`, `lib/sphere-fade.ts`, `components/background/AmbientBackground.tsx`, `OnSphere.tsx`, `hooks/useSphereDim.ts`, `Composer.tsx` (ripple on send), `state/stream-store.ts` (busy), `HomePage.tsx`, `RootLayout.tsx` (canvas on every route), `styles/ds/base.css`, tests, `e2e/theme-background.spec.ts`. Deviations: `data-dim` is published by a new hook `useSphereDim` called from the screen (home is open, everything else reads), not by `RootLayout`; the app mark's ripple moves to step 5, where the mark is rebuilt; the Logs page now has the sphere (dimmed), so its e2e test changed. Unit 915 pass; theme spec 15 pass.
- Decision: Prettier is run on every touched file (frontend standard), accepting reflow in files this change restyles anyway.
- [x] Step 3: Core building blocks - `styles/ds/controls.css`, `ds/dev.css`, `ds/states.css` (empty screen); `components/ui/Button.tsx` (quiet, link, `reason`), `Menu.tsx` (groups, ticked item, keys, reason), new `Checkbox`, `Tabs`, `Tag`, `Chip`, `StatusLight`, `TickRule`, `Kbd` with tests; `icons/icon-paths.ts` (`minus`); `features/dev/PrimitivesDemo.tsx`; old blocks removed from `components.css`. Notes: the icon set was already one outline style (stroke 2, round ends), so only missing icons are added as screens need them; no native `<select>` exists in `src/`; the drop-down's bottom sheet on phones comes with `Sheet` in step 4. Unit 925 pass.
- [x] Step 4: Layers on top - `styles/ds/layers.css`; `components/ui/Modal.tsx` (`variant`, `status`), new `Window`, `Sheet`, `Notice`, `HoldScreen`, `Viewer` (+ `lib/viewer-zoom.ts`), `Toast`/`toast-store` (action, 2.6 s and 6 s), `PromptDialog` (attached small pop-up when given `anchorRef`, sheet on a phone), `Popover` (`sheetOnPhone`, used by `Menu` and `Select`); `ImageLightbox` and `MermaidDialog` use `Viewer`; `HelpDialog` and `ThoughtFullView` use `Window`; old modal, toast and lightbox rules removed from both legacy sheets; tests in `components/ui/layers.test.tsx`, `lib/viewer-zoom.test.ts`. Notes: the prompt's default button reads Save, not OK; error messages still stay until dismissed (existing behaviour, kept so a failure cannot be missed); call sites hand `PromptDialog` its anchor in steps 5 and 8; portal, code history and versions move to `Window` in step 12, settings dialogs in step 10. Unit 940 pass.
- [x] Step 5: App frame - `styles/ds/frame.css`; `app/Sidebar.tsx` (rewritten: app mark that ripples, quiet New chat, temporary chat, new workspace with an attached name pop-up, foot rows, rail), `features/sidebar/RecentChats.tsx` (Today / Earlier groups, time per row, a menu button per chat, attached rename), `app/RootLayout.tsx` (header: menu button, title place, status light, Files button; tick rule), new `app/FilesButton.tsx`, `HeaderStatus.tsx`, `PageTitle.tsx`, `page-header-context.ts`, `hooks/useOnline.ts`, `lib/format-time.ts`, `lib/breakpoints.ts` (phone is under 600 everywhere), icons; old frame rules removed from both legacy sheets; tests. Deviations: no separate `PageShell.tsx` yet (the Back shell arrives with the settings page in step 10); page titles are put in the header through `PageTitle` (a portal) instead of a `PageHeader` component; Settings and System still open the dialogs until step 10. Unit 961 pass.
- Decision: the full Playwright suite is not run after every step (specs for screens not yet converted fail and each failure waits a minute). Each screen step updates and runs its own specs; the full suite runs once the screens are done and again at the end. After step 5, 12 of the first 26 specs fail, all in areas converted later (files, settings, workspace) or asserting the old sidebar geometry (updated in this ticket).
- [x] Step 6: Home and the message box - `styles/ds/home.css`; `features/home/HomePage.tsx` (greeting through `OnSphere`), `features/composer/Composer.tsx` (files and text on top, a row with attach, Tools, chips for tools that are on, and send / Stop; notice strip and dashed edge for a temporary chat; drop hint inside the box), `features/tools/ToolsMenu.tsx`, new `features/tools/modes.ts`, `ActiveTools.tsx` with tests; old rules removed. Plain tool names (Research, Files, Browsing, Git, Code). Unit 966 pass; e2e `composer-attachments`, `chat-start`, `mobile-keyboard`, `popover-placement` pass; three `mobile-layout` tests wait for step 14 (phones).
- [x] Step 7: conversation - `ds/chat.css`, `ds/content.css`, `MessageList.tsx`, `ThoughtBox.tsx`, `TimelineEntry.tsx`, `UserText.tsx`, `lib/user-text.ts`, `lib/thought-timeline.ts`, `lib/chat-model.ts`, `lib/theme.ts`. Unit 974 pass; specs thought-box, chat-send, chat-start, stop-races, stack multi-tool/stop-retry pass.
  - Decision: `e2e/stack/geometry.spec.ts` + `geometry.json` removed (they pinned the old layout to 1px; the layout is replaced on purpose). README and `docs/standards/testing.md` updated.
  - Decision: the injected highlight.js theme is removed; code colours come from `--code-*`.
  - Decision: message rows no longer carry the `chat-row` class (clashed with the navigation rows).
  - Pending for step 8: `turn-follow-ups.spec.ts` files-panel test fails until the files panel is converted. `stack/send.spec.ts` sidebar-title test is order-dependent on a shared backend (passes on a fresh one).
- [x] Step 8: files panel and editor - `features/artifacts/{ArtifactPanel,ArtifactDrawer,FileBrowser,FileTree,FileSearch,EditorToolbar,RunOutput,FilePlacePopup,CodeEditor}.tsx`, `useAutoSave.ts`, `file-search.ts`, `task-list.ts`, `artifact-tree.ts`, `api/filesystem.ts` (`codeExecApi.runFile`, `file_system_type`), `app/FilesButton.tsx`, `state/ui-store.ts`, `components/ui/Button.tsx` (IconButton `reason`), `lib/markdown/renderer.ts`, `styles/ds/files.css`. Unit 1001 pass; specs artifact-actions (3, incl. full screen), artifact-overlay, turn-follow-ups pass.
  - Deviation: the browser lives in new `FileBrowser.tsx`; `ArtifactPanel.tsx` is the host that moves it to full screen (one DOM box moved, never rebuilt, so the file, undo history, scroll and width survive). `MoveFileDialog` replaced by `FilePlacePopup` (the where-and-name pop-up, also used for new file / new folder / rename). Extra helper `task-list.ts`.
  - Decision: the Files panel is portalled into `#app-root` as a third panel (no more `--right-sidebar-width`); it overlays the content on tablets and is a full screen on phones. Default width 400.
  - Decision: no "discard changes" questions any more: unsaved text is saved before switching file, closing, running or opening history; if a save fails the file stays open with a notice and Try again. `artifactsDirty` removed from the store.
  - Decision: markdown/HTML files open in Preview, new files in Code; code files have no Code/Preview control.
  - Decision: research-plan Approve / Suggest changes shows when the open file is `research_plan_pending` and the chat's live turn waits on a question; it answers that question (the same call the chat card makes).
  - Decision: `@codemirror/theme-one-dark` removed, `@lezer/highlight` declared (editor colours from `--code-*`).
  - Fixed in passing (needed for live tick boxes): a task-list item rendered two tick boxes (marked 18 lists the box as a token); inline styles removed from it.
  - Backend gaps: MYAI-94 (content search; the panel searches names and the text of opened files), MYAI-95 created (run and version history for workspace files; both are off in a workspace and say why).
  - Environment: the code runner is not available on the throwaway backend, so Run shows "Did not run" there; the success path is unit-tested.
- [x] Step 9: workspace page - `features/workspace/WorkspacePage.tsx`, `features/sidebar/IconPickerDialog.tsx`, `lib/workspace-icon.ts` (new, shared default icon), `features/sidebar/RecentChats.tsx`, `styles/ds/workspace.css`. Unit 1007 pass; specs new-workspace, sidebar-workspace (6) pass.
  - Decision: the default workspace icon is the folder (was the grid), in the page and the navigation panel; an emoji icon from the old app is still shown as it is.
  - Decision: the icon picker follows the reference: a tap chooses, Save keeps it, "Back to the folder" resets; icons are named in plain words.
  - Decision: rename is the attached small pop-up (default button "Save"); the page title in the header is "Workspace" and the name is the page's own heading.
- [x] Step 10: settings page - new `features/settings/{SettingsPage,SettingsRedirect,SavedLight}.tsx`, `settings-nav.ts`, `sections/{Chat,Models,Personas,Skills,Memory,Agents,System}Section.tsx`, `lib/save-light.ts`; modified `CrudList.tsx` (inline list), `forms.tsx`, `SpeedTestPanel.tsx`, `GitSettingsSection.tsx` (`GitSettings`), `DialogHost.tsx`, `state/modal-store.ts` (`portal`, `code-history` only), `app/{RootLayout,Sidebar,routes}.tsx`, `features/composer/Composer.tsx`, `styles/ds/settings.css`; the eight dialog files and `ChatDefaultsSection.tsx` removed, their tests moved to the sections. Unit 1030 pass; specs settings-parity (6), speed-test (2), user-roles (3) pass. Checklist above ticked: every control checked on the page (unit tests per section, live on computer and phone).
  - Deviation (recorded for review): the page is a layer over the content panel addressed as `?settings=<part>` on the page that is open, not a separate route. A separate route unmounts the chat page, which resets the chat's own settings (`useChatSettings`) and would lose a change made in Settings on the way back. `/settings` and `/settings/:section` exist and lead to `/?settings=<part>`.
  - Decision: the Chat part edits the active values (the open chat's when over a chat, said in its lead line; the new-chat starting values otherwise); over a chat the four new-chat defaults are listed apart. The mode toggles stay in the Tools menu (not duplicated here).
  - Decision: applied at once with the light: every setter, agent limits (on leaving the box or Enter), browser stealth, git allowed commands, code runner limits (on leaving the box or Enter, checked where typed). Explicit Save stays only for list items (persona, skill, preference) and the write-only GitHub token ("Save token").
  - Decision: "Reset preferences" moved from System to Memory as "Reset memory" (it resets what Memory lists).
  - Decision: loading a model shows the whole-screen wait until the model reports loaded; a failed request ends it with the reason; it gives up after 3 minutes and says the load carries on.
  - Decision: not added from the reference because the app has no such setting: model server address / connection check, background movement switch.
  - Wording done here (ahead of step 15): Max tokens is "Longest answer", User preferences is "Use what it remembers about you", speed figures are Progress / First word after / Reading speed / Writing speed.
- [x] Step 11: logs page - `features/logs/LogsPage.tsx`, `log-levels.ts` (`logSummary`; `scalarColumns`, `columnLabel` removed with the table), tests, `styles/ds/logs.css`. Unit 1037 pass; checked at computer and phone width, day and night.
  - Decision: the four logs are one segmented choice (as the reference), not page tabs; every log uses the same folding rows, so the table and its column code are gone. Chat ids are reached through "Open the chat" inside the opened row.
  - Decision: "Rows" is "Last N"; the level filter is plain chips (Debug / Info / Warning / Error); a text line that starts with a date and time shows that time.
- [x] Step 12: tool windows - `features/tools/{PortalDialog,CodeHistoryDialog,RunCard}.tsx`, `features/artifacts/VersionsDialog.tsx` (+ `fileName`), tests, `styles/ds/tools.css`, `styles/ds/layers.css` (a window is opaque on a phone). Unit 1042 pass; the three windows checked on computer and phone with mocked data (runs, a browser that does not start, versions and a comparison).
  - Decision: a run is one folding line (newest open); the outcome words stay Passed / Failed (exit N) / Timed out. Version rows are picked to read them (no View button); Compare with current is a toggle on the chosen version; Restore still confirms.
- [x] Step 13: states and dead ends - new `components/ui/{Skeleton,DeadEnd,DottedDrawing}.tsx`, `app/{ErrorBoundary,DeadEnds}.tsx`; modified `EmptyState.tsx` (drawings replace icons), `app/{App,routes,UserGate}.tsx`, `features/chat/ChatPage.tsx`, `features/workspace/WorkspacePage.tsx`, `features/sidebar/RecentChats.tsx`, `features/composer/Composer.tsx` (offline), `lib/sphere-fade.ts` (a patch behind the drawing), `styles/ds/states.css`; tests for each. Unit 1063 pass; specs chat-start, chat-send, user-roles, stop-races, theme-background, new-workspace pass (25). Driven in the browser: missing chat, missing workspace (phone), unknown address, offline message box.
  - Decision: a dead end is an open screen (sphere at full strength, words on it with the fade), as `useSphereDim` already describes; the gate's screens (session ended, account not loaded) use the same component before the app frame exists.
  - Decision: `useOnline.ts` already existed from step 5; the header light and now the message box use it. Offline, sending is switched off and nothing is queued (the notice says sending is paused).
  - Slip, corrected before commit: a formatter run over the whole `src` folder reformatted 41 untouched files and the synced `tokens.css`; every file whose only change was formatting was restored from HEAD and `legacy.css` had its rule removals re-applied. From here the formatter is only run on the files a step changed.
- [x] Step 14: phones - `styles/ds/phone.css`, new `lib/back-layer.ts`, `hooks/useBackLayer.ts`, `hooks/useHomeBeneath.ts` with tests; modified `lib/modal-stack.ts` (layers answer Back; `back: false` for the settings page, which has its own address), `components/ui/{Popover,HoldScreen}.tsx`, `features/artifacts/{ArtifactDrawer,ArtifactPanel,FileBrowser}.tsx`, `app/RootLayout.tsx`, `styles/ds/{frame,files,settings,logs}.css`; `e2e/mobile-layout.spec.ts` rewritten (14 tests), `mobile-keyboard.spec.ts` passing. Unit 1069 pass; phone project 14/14 twice in a row.
  - Decision: one extra history step exists while any layer is open (not one per layer); Back lands on it, the newest layer closes and the step is put back while layers remain. Known limit: after moving to another page from inside a layer (a chat picked in the drawer) the old step stays beneath, so one Back press there does nothing visible.
  - Decision: "only leaves from Home": when the app is opened straight on another page on a phone, Home is put beneath it once (`useHomeBeneath`).
  - Decision: `Sheet.tsx` needed no change: it already registers through `pushModal`; menus and drop-downs register in `Popover.tsx`.
  - Decision: touch targets. A chip keeps its size and its remove button reaches past the chip's edge to 48; a task line in a file preview is the target for its tick box (pressing the line ticks it); a link inside a sentence of an answer keeps its line. The message box is pressed as a whole.
  - Found by the phone run and fixed: the version-history step of `artifact-actions.spec.ts` and an ambiguous Model locator in `popover-placement.spec.ts` (both from earlier steps).
- [x] Step 15: wording - one pass over fallback error messages (about 35 strings), `features/chat/tool-names.ts` (sentence case, proper names kept), ellipsis as one character (placeholders, "Thinking…", the server's three dots tidied in `stream-reducer.ts`), `MessageActions.tsx` ("Delete message"), `SpeedChart.tsx` ("tokens/s"), `lib/markdown/renderer.ts` (tips in sentence case); new `src/test/wording.test.ts` (six scan checks). Unit 1075 pass; chat specs pass (15).
  - Decision: `lib/format-time.ts` was created in step 5 and already holds times, dates and durations; the scan now forbids `toLocaleDateString`, `toLocaleTimeString` and a bare `toLocaleString()` outside it.
  - Decision: the tool-label table stays generated in title case; the display function turns it into sentence case, so a regenerated table needs no hand edits.
  - Left as it is: texts the server sends (error messages shown as given, apart from the trailing three dots of the redact notice).
- [x] Step 16: remove the old look, docs, final check - deleted `styles/legacy.css`, `components.css`, `bridge.css`, `components/ui/Badge.tsx`; `main.tsx` loads fonts, tokens, `ds/*`; `lib/design-tokens.test.ts` rewritten (styles folder contents, raw colours, corners, shadows, layers, speeds, undefined variables); `e2e/design-system.spec.ts` (new, 30 cases); docs (`docs/frontend.md` 190 lines, `docs/standards/frontend.md`, `docs/release.md`, `frontend/README.md`). Commit 82c62b9.
  - Fix found by the final look: on a tablet with the side panel open the settings column was too narrow and a wide control overlapped its description; wide rows now stack when the column is under 520px (container query in `ds/settings.css`).
  - `e2e/stack/temp-chat.spec.ts` still used a removed id; it now presses "Save chat" by name.
  - Left as is (out of plan): `theme-init.js` still sets the `dark` class although no style reads it.

### Smoke test (2026-11-11)
- `scripts/check.sh --frontend-only`: ALL CHECKS PASSED (typecheck, lint, 140 files / 1078 unit tests, build).
- Docs guardrails `pytest tests`: 68 passed.
- Playwright on a fresh throwaway backend (`npx playwright test e2e/`, both projects): 105 run, 104 passed, 1 failed (`stack/temp-chat`, stale id in the spec); fixed, re-run passes.

### Settings checklist (2026-11-11, written before the dialogs were touched)
Every control of the eight dialogs and `ChatDefaultsSection`, `GitSettingsSection`, `SpeedTestPanel`, with its home on the page. Ticked when it works there.

Chat (from `ChatSettingsModal`, `ChatDefaultsSection`)
- [x] Model (select, searchable)
- [x] User preferences (switch)
- [x] Thinking profile (General / Precision / None)
- [x] Persona (select, None first)
- [x] Max tokens (slider 256 to 32768)
- [x] Thinking budget (slider 0 to 8000)
- [x] Temperature (model default until set; slider 0 to 2; reset)
- [x] Top P (model default until set; slider 0 to 1; reset)
- [x] New-chat defaults: thinking profile, user preferences, max tokens, thinking budget (shown apart while a chat's own values are active)

Models, admin (from `ModelsDialog`, `SpeedTestPanel`)
- [x] Search models
- [x] Model rows with Loaded / Loading / Not loaded / Status unknown
- [x] Load, Unload (whole-screen wait while a model loads)
- [x] Speed test: model to test (select), target context (slider), Run (confirms), Stop
- [x] Speed test: status line, four figures, chart, warnings, error

Personas (from `PersonasDialog`)
- [x] List with default marker and first-sentence preview
- [x] New / edit form: name, instructions, Default persona, Research mode, File system mode, Browsing mode
- [x] Delete (confirms)

Skills (from `SkillsDialog`)
- [x] List, search
- [x] New / edit form: name (slash prefix), description, instructions, with their checks
- [x] Delete (confirms)

Memory (from `PreferencesDialog`, `SystemSettingsModal`)
- [x] List with tag, search, tag filter, sort
- [x] New / edit form: preference, tag
- [x] Delete (confirms)
- [x] Reset preferences (confirms)

Agents, admin (from `AgentConfigDialog`, `StealthDialog`, `GitSettingsSection`)
- [x] Per agent: max tokens, thinking budget, thinking profile
- [x] Browser stealth: Minimal / Advanced
- [x] GitHub token (write-only, says whether one is set)
- [x] Allowed git commands (tick boxes)

System (from `SystemSettingsModal`)
- [x] Theme: Light / Dark / System
- [x] Panels: Auto / Frosted / Solid (new, from the foundations change)
- [x] Vision input (switch)
- [x] Code runner, admin: timeout, memory limit, CPU limit, max output
- [x] Delete all chats (confirms)
- [x] Version, signed-in user
- [x] The six "Manage" links are replaced by the section list

### After shipping (2026-11-11): two gaps reported from the live site on a phone
- Memory list overflowed sideways: a long entry was one unbroken line (the tooltip wrapper could not shrink) and the settings column could scroll sideways. Now an entry wraps onto up to three lines, the column only scrolls up and down, and on a narrow column the search box takes a row and the filters share the next. Files: `styles/ds/settings.css`; phone test added to `e2e/mobile-layout.spec.ts`.
- Thought process did not look like the reference page: thoughts were folded "Reasoning" rows and each tool was two rows ("Call:", "Result:"). Now thoughts are plain text on the line; a tool call is one row (light, plain name, what it was asked; "Running" or "Failed" in words) that folds open to what was sent and what came back; "Open bigger" is a plain button inside the open box. `TimelineItem` has one `tool` kind (was `call` + `result`); `toolDetail`, `toolFailed` added to `lib/thought-timeline.ts`. Not shown: how long each tool or the whole turn took (the server does not send it).
- Checks: gate passes (1099 unit tests), docs checks pass, 88 browser tests for the affected specs pass; looked at on phone and computer, day and night. Commit 9f8b75b, pushed to the same pull request, deployed.

### Reference pass (2026-11-11): every page of the design's reference compared with the app
Method: the reference page was driven through its own controls (5 pages x 6 states, 17 chat moments, day and night, computer and phone: 62 screenshots) and compared with the app's matching screens by eye and, for the frame, chat and workspace, by measured sizes. Where the reference and the rule book disagree the rule book was followed (bar title 18px, page title 26 to 36px).
Closed: settings full screen (side panels hidden); icons from the design's starting set (send, attach, tools, edit, delete, copy, try again, search, file, folder, history, run, undo, redo, full screen, more, settings parts); message actions always shown; model label as a typewriter label with a dot before the time; formulas in a box; workspace column 60rem, cards fill the row, card time "Today · 14:02"; file rows say their kind; editor bar shows the file name and the language's proper name; temporary chat strip across the top with a dashed panel edge; chat row menu order (Rename, Move to a workspace, Delete) and width; window bars carry the tick rule with the subject beside the title; run rows start with the time; versions say "My AI" and "You"; temperature and top P are boxes that can be left empty ("model default"); "Save and resend"; navigation panel 252 wide; chat row text centred on a phone.
Kept on purpose (the app has more than the reference): expanding workspaces in the navigation panel, the signed-in email, "New chat here" and the chat count on the workspace page, a number box beside sliders, the thinking budget, the row limit on Logs, the x on tool chips, a second "Save" when editing a message, status words on run rows.
Not possible without the server (MYAI-96): how long a tool and a turn took; the research plan card; the helpers card; source chips under an answer. The acceptance line about those cards is unticked for research plan and helpers; the question card exists.
Not compared one by one in this pass: the Building blocks page against the developer preview, and the empty, loading, problem and offline states of each page (both were compared when they were built, steps 2, 3 and 13).
Checks: gate passes (1105 unit tests), docs checks pass, 142 browser tests pass on a fresh backend. Commit 04df343.

PR: https://github.com/archit342000/My-AI/pull/122, branch feature/design-system-screens, base feature/design-foundations (retargeted to develop and merged 2026-11-11, merge commit 7dd16d3)

## Verification

### Verification plan (2026-11-11)
**Diff base:** 8f561bc  **Environment:** throwaway backend http://127.0.0.1:5195 (temporary data folder, static sign-in, scripted model), this worktree's dev server http://localhost:5183. Nothing real is touched. Evidence: `~/.claude/tickets/My-AI/MYAI-93-evidence/` (`part10/` screenshots and `results.json`, `steps/` screenshots taken while building each step, `scripts/part10.cjs`).

| ID | Covers | Scenario | Method | Expected |
|----|--------|----------|--------|----------|
| V1 | Parts 1, 15 | Sphere, stars, theme before first paint, solid panels, less motion, typefaces | `e2e/theme-background.spec.ts` (11) | all pass |
| V2 | Parts 2, 3 | Controls and layers: placement of menus, Escape and focus, toasts | unit tests in `components/ui/*`, `e2e/popover-placement.spec.ts` (4), dev preview screenshots `steps/s3-dev-*` | all pass, matches reference |
| V3 | Part 4 | Side panel open and collapsed, chat row menu, workspaces | `e2e/sidebar-workspace.spec.ts` (5), `e2e/new-workspace.spec.ts`, screenshots `steps/s16-rail`, `s16-home-*` | all pass |
| V4 | Part 5 | Home, composer, slash menu, attachments, temporary chat | `e2e/chat-start` (2), `composer-attachments` (4), `stack/temp-chat`, screenshots `s6-home-*`, `s16-home-light` | all pass |
| V5 | Part 6 | Send, stream, stop, retry, thought box, follow-ups, multi-tool | `e2e/chat-send`, `stop-races` (3), `thought-box`, `turn-follow-ups` (2), `stack/send` (2), `stack/stop-retry` (2), `stack/multi-tool` (2), screenshots `s7-*` | all pass |
| V6 | Part 7 | Files panel: tree, search, edit with auto-save, full screen and back, actions, phone list then editor | `e2e/artifact-actions` (3), `artifact-overlay`, screenshots `s8-*` | all pass |
| V7 | Part 8 | Workspace page, icon picker, empty, rename, delete | unit tests in `features/workspace`, screenshots `s9-ws-*` | pass |
| V8 | Part 9 | Settings page: seven parts, nothing lost, saves by itself, lists, speed test, roles | `e2e/settings-parity` (6), `speed-test` (2), `user-roles` (3), settings checklist in Implementation notes, screenshots `s10-*`, `s16-settings-*` | all pass |
| V9 | Part 10 | Logs page folds, filter, count | unit tests in `features/logs`, screenshots `s11-logs-*` | pass |
| V10 | Part 11 | Browser, code runs, version history windows | unit tests in `features/tools`, `features/artifacts`, `e2e/artifact-actions` (version history) | pass |
| V11 | Part 12 | Empty, loading, problem, offline, gone, broke | unit tests `components/ui/states.test.tsx`, `app/*`, screenshots `s13-gone-*`, `part10/not-found-*` | pass |
| V12 | Part 13 | Phone: 48 targets, Back closes newest layer, keyboard, opaque drawer, full-screen layers | `e2e/mobile-layout` (12), `mobile-keyboard` (2) in the `phone` project | all pass |
| V13 | Part 13 | Back order on a real Android device | needs a device | BLOCKED |
| V14 | Part 14 | Wording | `src/test/wording.test.ts` (6 scans) | pass |
| V15 | Part 15 | Old sheets gone; no raw values | `grep -rn "legacy.css\|bridge.css\|components.css" frontend/src docs`, `lib/design-tokens.test.ts` | no hits; pass |
| V16 | Part 15, whole | Rule book Part 10 on every screen: 7 screens x 3 widths x day and night, plus solid panels with less motion | `scripts/part10.cjs` (measures sideways scroll, typefaces, Main buttons, phone target sizes, focus ring on 12 Tab stops, blur count in solid mode, running animations and canvas stillness under less motion, console errors) and looking at the screenshots | all clean |
| V17 | Part 15, whole | Every screen at 3 widths in both themes: fits, no console error, no words on the bare sphere | `e2e/design-system.spec.ts` (30) | all pass |
| V18 | whole | Gate | `scripts/check.sh --frontend-only`, `pytest tests` | pass |

### Results (2026-11-11)
Commit verified: 82c62b9 (no uncommitted work files).

| ID | Status | Evidence |
|----|--------|----------|
| V1-V12, V14, V17 | PASS | Playwright run on a fresh backend: 105 tests, all pass after the one spec fix (see Smoke test); unit suite 140 files / 1078 tests |
| V13 | BLOCKED | no Android device here; the Back behaviour is covered in Chrome's phone emulation by `mobile-layout.spec.ts` only |
| V15 | PASS | grep finds nothing in `frontend/src`, `docs/*.md`, `docs/standards`; design-values test passes |
| V16 | PASS | `part10/results.json`: 42 screen runs, sideways scroll 0, only Sora / Instrument Sans / JetBrains Mono, at most one Main button, no phone target under 48 (the only hit is the bare text area inside the 48+ message box), ring on every Tab stop (12 of 12 on each of 28 computer and tablet runs), 0 console errors; 7 solid + less-motion runs: 0 blurred elements, 0 running animations, canvas still. Screenshots looked at by eye: home, chat, files, workspace, settings, logs, not found at mixed widths and themes |
| V18 | PASS | see Smoke test |

Verdict: verified except V13 (real-device Back order).

Not covered by a measurement: text contrast was not re-measured in the app (the shared values were checked for it in the design repository); very-wide (1600+) layout was looked at during step 5 only.

## Review history

### Round 1 - 2026-11-11
Verdict: Request changes. Scope: base 8f561bc...82c62b9, 265 files, four Haiku reviewers (correctness, standards and security, tests, requirements and docs), requirement = Description, Acceptance criteria and the Reviewer brief. Every finding checked against the code before it was kept.

| ID | Sev | Where | Problem | Status |
|----|-----|-------|---------|--------|
| R1-1 | MAJOR | `features/artifacts/FileBrowser.tsx` | typed text stayed on screen after saving, hiding a later change to the same file and able to overwrite it | Fixed: draft cleared once its text is saved; test fails without the fix |
| R1-2 | MAJOR | `features/artifacts/useAutoSave.ts`, `ArtifactDrawer.tsx` | a failed save when the panel closes (phone Back, unmount) was silent; page-hide save had no keepalive | Fixed: `onLost` toast, `leaving` saves use keepalive under 30,000 characters; tests. Not changed: phone Back still closes the panel before the save result is known (Back has already happened) |
| R1-3 | MAJOR | `features/workspace/WorkspacePage.tsx` | failed chat list showed the empty workspace | Fixed: retryable problem notice; test |
| R1-4 | MAJOR | `e2e/design-system.spec.ts` | loading check used a class that does not exist | Fixed: `.skel` |
| R1-5 | MAJOR | `components/background/OnSphere.test.tsx` | re-measure on resize and font load untested | Fixed: test added |
| R1-6 | MAJOR | `e2e/design-system.spec.ts` | "every screen" claimed, five covered | Fixed: all seven settings parts added (66 cases), header says which screens |
| R1-7 | MAJOR | `docs/frontend.md`, `frontend/README.md` | stale claims (`--right-sidebar-width`, names-only search, `CrudDialog`, layout table, "not offered") | Fixed |
| R1-8 | MINOR | `components/ui/ConfirmDialog.tsx` | default label "Confirm" | Fixed: label required |
| R1-9 | MINOR | `features/artifacts/VersionsDialog.tsx`, `FileBrowser.tsx` runFile | late answers shown for the wrong version or file | Fixed: request tokens |
| R1-10 | MINOR | `features/artifacts/file-search.ts` | snippet could miss the match on an indented long line | Fixed; test |
| R1-11 | MINOR | `FileBrowser.tsx` remove | waiting save for a deleted file kept failing | Fixed: `discard`; test |
| R1-12 | MINOR | `components/icons/icon-paths.ts` | `in` matched inherited names | Fixed |
| R1-13 | MINOR | `features/sidebar/IconPickerDialog.tsx` | Save with nothing chosen wiped an older emoji icon | Fixed; test |
| R1-14 | MINOR | `WorkspacePage.tsx` delete | "no longer exists" flashed before going home | Fixed: navigate first |
| R1-15 | MINOR | guards (`wording.test.ts`, `css-coverage.test.ts`, `inline-style.test.ts`, `design-tokens.test.ts`), `FileBrowser.tsx` lint reason, `CodeEditor.tsx` sizes, `ChatSection.test.tsx` `!`, `sphere-fade.test.ts`, hooks without tests | looser than their names or missing | Fixed |
| R1-16 | MAJOR | `styles/ds/*.css` | about 400 spacing and size values are written out (6, 10, 14, 18px...), not shared values; the guard does not check them | Deferred: the reference page uses the same in-between sizes and the shared values do not name them; needs names in the design repository first. Docs now say this. The criterion "No raw ... size ... remains" is met for colours, corners, shadows, layers and speeds only |
| R1-17 | MAJOR | `FileBrowser.tsx` search | text is searched only in files opened so far | Deferred: needs the server (MYAI-94); recorded in the plan decisions and docs |
| R1-18 | MINOR | `lib/back-layer.ts` | extra history step left behind when the page changes while a layer is open | Deferred: known limit recorded at step 14 |
| R1-19 | MINOR | `lib/particles.ts` `ctx!`, `Composer.test.tsx` `!`, `lib/cx.ts`, `lib/roving.ts`, `state/modal-store.ts` without tests | - | Pre-existing (same at 8f561bc) |

Dismissed: icon picker in a centred pop-up (follows the reference page; decision at step 9); several components in `DeadEnds.tsx`, `FileSearch.tsx`, `Skeleton.tsx` (same practice as `Button.tsx`, `Field.tsx`, `Menu.tsx` at the base); save light "stuck on Not saved" (disproved: the next save sets Saving, then Saved); raw error text on the Logs page (admin-only diagnostic page, an existing test requires the reason); geometry spec removed (decision at step 7); inner corners up to 8px (rule book's inner-corner rule, documented in the test); number formatting with an explicit locale; Android Back as a docs "known gap" (verification status, not behaviour); settings as `?settings=` and not a route (deviation recorded at step 10).

Resolution: 15 fixed, 3 deferred, 1 pre-existing. Checks after the fixes: `scripts/check.sh --frontend-only` passes (142 files, 1091 tests), docs guardrails 68 pass, Playwright 141 pass on a fresh backend. Commit 147f00b. Fixes changed runtime behaviour in the files panel, workspace page and icon picker; covered by the re-run suites.

### Round 2 - 2026-11-11
Verdict: Request changes. Scope: 82c62b9...147f00b (the round 1 fixes), one Haiku reviewer, all areas.

| ID | Sev | Where | Problem | Status |
|----|-----|-------|---------|--------|
| R2-1 | BLOCKER | `FileBrowser.tsx` remove | waiting text dropped before the delete was known to succeed | Fixed: dropped in `onSuccess` |
| R2-2 | MAJOR | `FileBrowser.tsx` saveFile | keepalive limit counted characters, not bytes | Fixed: byte size under 60,000 |
| R2-3 | MAJOR | `useAutoSave.ts` | a save in flight for a deleted file was restored on failure and retried for ever | Fixed: gone ids are dropped; test |
| R2-4 | MAJOR | `VersionsDialog.tsx` | late answer applied after the window closed | Fixed: closing bumps the request; test for a late answer |
| R2-5 | MAJOR | `icon-paths.ts` | no test | Fixed: `icon-paths.test.ts` |
| R2-6 | MINOR | `FileBrowser.tsx` runFile | run token taken after the save | Fixed |
| R2-7 | MINOR | `useAutoSave.ts` page hide | waits for a save in flight before the keepalive one | Deferred: limit written in the code; a save in flight cannot be overtaken without sending stale-over-new text |
| R2-8 | MINOR | `useHomeBeneath.test.tsx` | only checks the page shown, not the history order | Deferred: needs a browser router; not covered by a browser spec either |
| R2-9 | MINOR | `css-coverage.test.ts` | comment named the wrong users of the hooks | Fixed |

Dismissed: tests for the run-token guard and the byte boundary (R2-6 and R2-2 are one-line guards; left without their own tests).

Resolution: 7 fixed, 2 deferred. Checks: typecheck, lint, 143 files / 1095 unit tests pass; files and workspace browser specs (12) pass; build passes. Commit 701ed3b. These fixes were not re-reviewed by a clean reviewer.

## Log
- 2026-11-11: created by merging MYAI-77 to MYAI-91 at the user's request
- 2026-11-11: added to epic MYAI-75
- 2026-11-11: linked blocked_by MYAI-76 (needs the shared values first)
- 2026-11-11: linked split_from MYAI-77 to MYAI-91 (their scope moved here in full)
- 2026-11-11: autopilot started (batch), stacked on the foundations branch
- 2026-11-11: linked relates_to MYAI-94 (backend gap: search across file contents)
- 2026-11-11: plan validated, 2 rounds
- 2026-11-11: implemented (16 steps), smoke tests pass
- 2026-11-11: verified, 17 scenario groups pass, 1 blocked (real Android device)
- 2026-11-11: review round 1: request changes; 15 fixed, 3 deferred, 1 pre-existing
- 2026-11-11: review round 2: 7 fixed, 2 deferred
- 2026-11-11: PR opened (stacked on the foundations PR); build deployed to the live served folder
- 2026-11-11: batch-autopilot: shipped, base feature/design-foundations
- 2026-11-11: fixed memory overflow on phones and matched the thought process to the reference; pushed and deployed
- 2026-11-11: reference pass done; differences closed; merged into develop (PR 122)
- 2026-11-11: linked relates_to MYAI-96 (what the design needs from the server)
- 2026-11-11: closed. Unticked criteria: real Android Back order (not checked on a device), raw sizes (in-between spacing not named yet), research plan and helpers cards (need the server, MYAI-96)
