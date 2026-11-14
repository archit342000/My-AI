---
id: MYAI-52
title: "Full frontend audit: every component, live and in code"
status: in-progress
created: 2026-11-10
updated: 2026-11-10
links:
  relates_to: [MYAI-53]
---

## Description
The React frontend (`frontend/`) was heavily reworked on `develop` (158 files, +12.4k lines since `main`) and is now visibly broken. Inspect every component both live (desktop and mobile viewports, real streaming turns) and at code level, and report every defect, down to single-pixel misalignments. This ticket is report-only: no fixes. Its findings feed a fix epic.

Bugs the user already saw (2026-11-10), all to be reproduced and root-caused:
- weird behaviour when starting a chat;
- the thought process box is broken;
- several turns appear in response to a single message (tied to the thought box);
- the tools menu ("research agent" etc.) opens at a wrong position;
- on mobile the chat screen does not move up when the keyboard opens.

The user expects the real list to be much longer.

## Acceptance criteria
- [x] Every component/page under `frontend/src` is inspected in code and live, and listed in a coverage table.
- [x] Each of the five user-reported bugs is reproduced (or explained) with a root cause at `file:line`.
- [x] Every finding has: ID, component, severity, repro, expected vs actual, root cause, evidence.
- [x] Desktop and mobile viewports are both covered; visual defects have screenshots.
- [x] Findings are grouped so a fix epic and child tickets can be cut from them.

## Plan
1. Baseline: audit `origin/develop` (5a15a5c). Run typecheck, lint, vitest, e2e and record failures.
2. Code pass: read every file under `frontend/src` (app, components/ui, features, lib, state, api, styles) against the legacy UI in `static/` as the reference behaviour.
3. Live pass: run the app against a throwaway DB and a scripted inference stub (inference is external), drive it with Playwright at 1440x900 and 390x844, screenshot each component and state.
4. Write findings below; then cut the epic.

## Implementation notes
- 2026-11-10: branch `worktree-bridge-cse_014HoMhozpKqM9obHCdkxBtW` fast-forwarded to `origin/develop` (5a15a5c); no code changed (report-only).
- Live rig: `MYAI-52-evidence/scripts/up.sh` starts the stub (:5091), the React instance (:5092) and a legacy instance (:5093) on `/tmp/myai48/data`. Needs `HF_HUB_OFFLINE=1` and a cached tokenizer name in the stub's model config.
- Method: code read of every file under `frontend/src`; scripted tours with an overflow check per screen; computed-style and geometry diff of shared selectors against legacy (`scripts/metrics.mjs`); flow scripts for send, race, stop, retry, edit, reattach, temp chat, modes, uploads, keyboard.

## Verification
### Audit run 2026-11-10

- **Ref audited:** `origin/develop` 5a15a5c (production build served by Flask). **Reference for expected behaviour:** the legacy UI (`static/`, same data, served on a second instance).
- **Setup:** throwaway `DATA_DIR`, `AUTH_PROVIDER=static` (admin), scripted inference stub (reasoning, tool calls, multi-step, long markdown, slow stream, clarification, file write, HTTP 500). Chrome via Playwright at 1440x900 and iPhone 13 / Pixel 7, light and dark. Nothing touched the live app, data or model server.
- **Baseline checks:** `npm run typecheck`, `npm run lint`, `npm test` (59 files, 355 tests) all pass on this build. `npm run e2e` not run (port 5173 in use by another session; the three specs mock the chat detail, so they cannot see A-01).
- **Evidence:** `MYAI-52-evidence/` — `shots/` (tours `tour-{d,m}-{light,dark}`, `tour-m2-light`, React-vs-legacy pairs `c-*`, flow shots `f-*`, `k-*`), `metrics/*.txt` (exact px/style diffs vs legacy), `scripts/` (stub, drivers), `working-notes.md`.
- **Severity:** S1 broken or blocks a core flow · S2 major functional or visual defect · S3 minor defect · S4 pixel/polish. Paths are relative to `frontend/src/`.

### Coverage

| Area | Files | Code | Live desktop | Live mobile |
|---|---|---|---|---|
| App shell, routing, user gate | `app/*`, `main.tsx`, `index.html` | yes | yes | yes |
| Sidebar, workspaces, context menus | `app/Sidebar.tsx`, `features/sidebar/*` | yes | yes | yes |
| Home, chat page, transcript, thought box, tool cards, actions | `features/home`, `features/chat/*`, `lib/chat-model.ts` | yes | yes | yes |
| Composer, slash menu, attachments, tools menu | `features/composer/*`, `features/tools/ToolsMenu.tsx` | yes | yes | yes |
| Streaming (send, stop, retry, edit, reattach, temp chat) | `send-turn.ts`, `stream-reducer.ts`, `state/stream-store.ts`, `api/*` | yes | yes | partly (send/stop) |
| Markdown, code, math, tables, lightbox | `lib/markdown/*`, `components/markdown/*` | yes | yes | yes |
| Artifacts drawer/panel, editor, versions | `features/artifacts/*` | yes | yes | yes |
| Workspace page | `features/workspace/*` | yes | yes | yes |
| Chat/System settings, manage dialogs | `features/settings/*` | yes | yes | yes |
| Portal, code history | `features/tools/*` | yes | yes (portal: 503, no browser service) | no |
| Logs page | `features/logs/*` | yes | yes | yes |
| UI primitives | `components/ui/*` | yes | via the screens above | via the screens above |
| Themes, particles | `lib/theme.ts`, `lib/particles.ts`, `styles/*` | yes | light + dark | light (dark: 16 screens) |

Not covered live: real on-screen keyboard on a physical phone (simulated through `visualViewport`), iOS Safari, image attachments with vision on, research/browsing/git agents (need external services), drag-and-drop of chats, `/dev/ui` (dev build only), non-admin role.

### The five reported bugs

| Reported | Verdict | Findings |
|---|---|---|
| Weird behaviour when starting a chat | Reproduced: blank flash, lost focus/typed text, and "This chat no longer exists." for the whole reply when the create call loses a race | A-11 … A-15 |
| Thought process box is messed up | Reproduced: one box per model step, box-in-box body, no timeline, wrong live label, collapses itself | A-01 … A-10 |
| Several turns for one message | Reproduced: 4 bot rows for a 3-tool turn (legacy: 1) | A-01, A-02 |
| Tools menu at a weird position | Reproduced: floats 73px above the wrench (desktop), mid-screen on mobile | A-18, A-19 |
| Chat does not move up with the mobile keyboard | Root cause found: viewport meta lost `interactive-widget=resizes-content`; only the composer is translated | A-22 … A-25 |

### Findings

**1. Transcript turn model and thought box**

| ID | Sev | Finding (actual vs expected) | Root cause | Evidence |
|---|---|---|---|---|
| A-01 | S1 | One user message renders several assistant rows: each stored assistant message (one per tool round) becomes its own row with its own avatar, thought box, bubble and model label. MULTI = 4 rows, TOOL = 2 rows (the first has no text, only a thought box and a model label). Legacy shows one turn. | `lib/chat-model.ts:131-160` `toTurns` pushes a turn per assistant message; legacy groups everything between two user messages (`static/script.js:838-960`). | `c-d-multi-react.png` vs `c-d-multi-legacy.png` |
| A-02 | S1 | Live and persisted views disagree: while streaming, all steps are merged into one row with text concatenated without separators ("Interim note 1. Interim note 2. …"); on completion the row splits into N rows. | `stream-reducer.ts:89-90` appends to one `content`/`reasoning`; `MessageList.tsx:436` swaps the live row for persisted rows. | `d10-multi-live*.png`, `d11-multi-done.png` |
| A-03 | S1 | Tool calls and results vanish after the turn is saved (visible only while live). | API returns `tool_calls` as an array; `chat-model.ts:66-69` `JSON.parse`s it, throws, returns `[]`. `api/types.ts:26` types it as string. | `d13-multi-tools-open.png`; API dump in notes |
| A-04 | S2 | Expanded thought body is a card inside a card (double border, 16px inset); legacy shows a timeline of collapsible REASONING / CALL / TOOL RESULT cards in order. No per-step structure at all. | `ThoughtBlock.tsx:105` gives reasoning the bubble classes `message-content raw-text-content`; `ToolActivityFeed` is appended after all reasoning instead of interleaved. | `tour-d-light/35-*.png` vs `c-d-long-exp-legacy.png`, `c-d-multi-exp-legacy.png` |
| A-05 | S2 | Live header says "Thinking…" only until the first content token, then "Thought Process" even while later steps are still reasoning or running tools. | `MessageList.tsx:272` `thinking = !live.content`. | `f-live-content-streaming.png` |
| A-06 | S2 | Reasoning is not visible while it streams unless the user expands the box; the box the user expanded collapses when the turn completes (and whenever the row remounts). | `expanded` is local state in `BotBody` (`MessageList.tsx:207`); live row and persisted row are different components. | s5 test 1 |
| A-07 | S2 | Tool pills ("Get Time · Done") render outside the thought box between header and bubble; legacy keeps tool activity inside the box. | `MessageList.tsx:221` `ToolSummary` placement. | `d10-tool-live1.png` |
| A-08 | S3 | Model label shows under an empty area while the model is still thinking (no bubble yet). | `MessageList.tsx:229-233` renders the footer whenever `model` is set. | `d10-tool-live1.png` |
| A-09 | S3 | No "open full view" button on the thought header (legacy has an expand-to-modal control). | Not ported (`thought-full-view-modal`). | `c-d-multi-legacy.png` |
| A-10 | S3 | Stored `event` rows, sub-agent history and `assistant_active` rows are ignored when building turns; sub-agent stream deltas are only counted. | `chat-model.ts:140-162`, `stream-reducer.ts:78-79`. | code |

**2. Starting a chat and sending**

| ID | Sev | Finding | Root cause | Evidence |
|---|---|---|---|---|
| A-11 | S1 | If the chat-create PATCH is slower than the chat GET (400ms in the test; plausible through the tunnel), the page shows only "This chat no longer exists." for the entire reply: no transcript, no composer, no stop button. It recovers when the stream ends. | `Composer.tsx:270` navigates before `send-turn.ts:186-207` creates the chat; `useChatQueries.ts` does not retry a 404; `ChatPage.tsx:115-122` replaces the whole page on error. | `f-start-race.png`, s4 B |
| A-12 | S2 | On the first send the main area goes hero → blank (`.chat-loading`) → transcript within ~100ms (visible flash). | Route change mounts `ChatPage` with a pending query. | s4 A timeline |
| A-13 | S2 | Focus leaves the composer on the first send (focus = body) and text typed right after pressing Enter is lost; on a phone the keyboard closes. | `HomePage` and `ChatPage` each mount their own `Composer`; navigation remounts it. | s4 A |
| A-14 | S2 | At the end of a turn the transcript briefly shows the turn twice (4 rows then 2). | `send-turn.ts:98-100` awaits the refetch before `finish()`. | s4 A (833ms → 836ms) |
| A-15 | S3 | The new chat appears in the sidebar only after the first stream chunk, and is not highlighted until then. | `send-turn.ts:66-70`. | `d03-start-500.png` |
| A-16 | S1 | Temporary chat cannot send: the first message is refused with the toast "Could not load this chat. Reload the page and try again."; "Save Chat" then opens a 404 chat. | `send-turn.ts:173-176`: a temporary chat is not `isNewChat` and has no cached detail. | `f-temp-live.png`, s5 test 7 |
| A-17 | S2 | Streaming state is global: while chat A streams, chat B's send button is "Stop" (it stops A) and Enter in B is ignored silently (text stays, no message). | Single slot in `state/stream-store.ts`; `send-turn.ts:164` returns without feedback; `Composer.tsx:55-56`. | s5 test 5 |

**3. Popovers and the tools menu**

| ID | Sev | Finding | Root cause | Evidence |
|---|---|---|---|---|
| A-18 | S1 | Tools menu opens 73px above the wrench on desktop (panel bottom 754, button top 827) and covers the greeting; on a 390px phone it floats mid-screen, offset to the right. | `components/ui/Popover.tsx:83-84`: the flip-above branch sets `top = anchor.top - GAP - maxHeight` with `maxHeight` capped at 480, not the panel's real height (411). `ToolsMenu.tsx` uses the default `bottom` placement. | `d02-home-tools.png`, `tour-m-light/02-home-tools.png` |
| A-19 | S2 | Same bug hits every popover that flips upward: Select lists near the bottom of a dialog and context menus opened low on the screen. | Same lines. | code; `tour-d-light/09-*.png` (does not flip there) |
| A-20 | S3 | Searchable Select: the search input overflows the list panel on the right (clipped border), desktop and mobile. | `styles/components.css:384` `.ui-select__search` width + margin. | `tour-d-light/44-*.png`, `tour-m-light/43-*.png` |
| A-21 | S3 | Popover and Tooltip use `window.innerHeight`/no clamping: wrong under an on-screen keyboard; tooltips near the top or side edges are cut. Tools button keeps its active background after the menu closes. | `Popover.tsx:128-131`, `Tooltip.tsx:27-28`. | code |

**4. Mobile keyboard and viewport**

| ID | Sev | Finding | Root cause | Evidence |
|---|---|---|---|---|
| A-22 | S1 | With the keyboard open the transcript does not move: only the composer is translated up; the last message stays behind the composer and keyboard (last row bottom 711px vs visible bottom 539px). | `frontend/index.html:5` viewport meta dropped `interactive-widget=resizes-content, maximum-scale=1.0, user-scalable=no` (legacy `static/index.html:6-7`), so Android no longer resizes the layout; `hooks/useKeyboardOffset.ts` moves `#chat-input-area` only. | `k-keyboard-react.png`, s6 |
| A-23 | S2 | iOS handling is gone: `<html>` never gets `is-ios`, so the iOS rules (`styles/legacy.css:5450-5490`: momentum scroll, opaque glass fallbacks) are dead, and the rubber-band `touchmove` lock is not ported. | Not ported from `static/js/scroll-manager.js:88-102`. | code; `htmlClass: ""` in s6 |
| A-24 | S2 | Transcript does not scroll to keep the latest message visible when the keyboard opens. | No handler; `--composer-h` ignores the keyboard offset. | s6 |
| A-25 | S3 | Pinch-zoom is now possible and inputs can trigger focus zoom on iOS (legacy disabled both). | Same meta tag. | code |

**5. Mobile layout (390px)**

| ID | Sev | Finding | Root cause | Evidence |
|---|---|---|---|---|
| A-26 | S2 | Assistant bubble is 297px wide, indented by the avatar column; legacy uses the full 340px with the avatar above. | `styles/components.css:1307-1326` `.bot-turn` grid has no mobile variant. | `tour-m-light/32-*.png` vs `c-m-long-legacy.png` |
| A-27 | S2 | The 54px files button overlaps the first messages and the thought chevron. | `#nav-files-btn` fixed, transcript has no matching top/right inset. | `tour-m-light/17-chat-multi.png` |
| A-28 | S2 | Drawer: "New workspace" button is pushed out of view (row = New Chat + clock); drawer is see-through, page text bleeds through; it stays open behind any dialog opened from it. | Rail/expanded CSS shows the temp button on mobile (legacy hides it); mobile keeps `backdrop-filter` glass (legacy uses opaque 0.96); `RootLayout.tsx:33-35` closes on navigation only. | `tour-m-light/06-sidebar.png`, `tour-m2-light/01-system.png` |
| A-29 | S3 | Hamburger is a 40px grey circle at 10,10; legacy is a 56px rounded square at 20,20 with a blue icon. It covers the "Logs" page title. | `styles/components.css:1094-1107`. | `metrics/m-home.txt`, `tour-m2-light/17-logs-network.png` |
| A-30 | S2 | Workspace page header overflows: "New chat in this workspace" is cut at the right edge (right = 501px on a 390px screen); rename row overflows too. | Inline flex row with no wrap, `WorkspacePage.tsx:79-160`. | `tour-m-light/38-workspace.png` |
| A-31 | S3 | Toasts sit on top of the composer and send button. | `.ui-toast-viewport` bottom offset. | `tour-m2-light/19-toast.png`, `f-temp-live.png` |
| A-32 | S3 | Dialogs: no mobile sheet layout; body is cut at the bottom edge with no padding; model rows truncate names to ~12 characters beside a wide button; edit-message buttons wrap to two rows. | `Modal` has no small-screen variant; fixed-width `.model-row__action`. | `tour-m2-light/01,10`, `tour-m-light/20-chat-edit.png` |
| A-33 | S3 | Mobile keeps blur(20px) glass on sidebar, composer, thought box and title header; legacy switches these to opaque surfaces on phones. | Legacy mobile overrides are not matched by the new markup. | `metrics/m-chat-long.txt` |
| A-34 | S4 | Files button is hidden on the home page (legacy shows it dimmed). | `RootLayout.tsx:84`. | `c-m-home-*.png` |

**6. Chat row layout and pixel parity (1440px, vs legacy)**

| ID | Sev | Finding | Root cause | Evidence |
|---|---|---|---|---|
| A-35 | S2 | Bubble starts at x=508, width 724; legacy 464 / 768 (the bubble runs under the avatar). All content (headings, tables, code) is 44px narrower and shifted. | `.bot-turn` grid (`components.css:1307`). | `metrics/d-chat-long.txt` |
| A-36 | S3 | Thought header 47px tall at x=508; legacy 56px at x=512. | `.thought-section-wrapper` is `display:block` (legacy flex, gap 8px). | same |
| A-37 | S3 | Avatar sits 15px higher than legacy and is no longer centred on the thought header (y 274.8 vs 289.8). | `.bot-turn__avatar { padding-top: 4px }`. | same |
| A-38 | S3 | Model label: 9.6px / weight 600 / opacity 1 / raw id ("STUB/AUDIT-MODEL"); legacy 10.4px / 500 / 0.8 and the role name ("VISION_SMALL (AUDIT-MODEL)"). Footer lost its 4px padding and margin. | `.bot-message-footer`, `.bot-model-label` overrides; display-name mapping not ported. | same; `c-d-multi-*.png` |
| A-39 | S4 | Message action row is 100x28 (legacy 94x26, 6px further left); bot actions start at x=478 while the bubble starts at 508. | `MessageActions` uses `IconButton` sm. | `tour-d-light/19,20` |
| A-40 | S4 | Stopped/Retry notice and inline error start at x=464, not aligned with the bubble (508). | `.turn-notice`, `.chat-error` outside the grid. | `f-stopped.png` |
| A-41 | S3 | Redact/"retrying" notice is unstyled text with a stray "|" where the spinner should be, and prints the backend's raw error including an internal URL. | `.validation-fixing` has no rule; `.processing-spinner` not sized here; `MessageList.tsx:283`. | `tour-d-light/75-stream-error.png` |
| A-42 | S4 | Markdown links use the browser default blue (rgb 0,0,238): unreadable on the dark theme. Same in legacy. | No `.message-content a` colour. | `tour-d-dark/35-*.png` |
| A-43 | S4 | Dark theme code blocks show a lighter inner rectangle (hljs background inside `pre`). Same in legacy. | `code.hljs` background. | `tour-d-dark/34-*.png` |
| A-44 | S3 | Chat title rename field is unstyled: Arial bold, 2px black border, wider than the pill. | `ChatPage.tsx:50` reuses `.chat-title-display` on an `<input>`. | `tour-d-light/23-*.png` |
| A-45 | S3 | Message edit box: textarea is not focused when it opens, so Escape/Enter do nothing until clicked; native resize handle shows. | `MessageList.tsx:100-117` has no autofocus. | s5 (`edit focus=`), `tour-d-light/21-*.png` |
| A-46 | S4 | The files button is always full opacity (legacy 0.35 when the chat has no files). | No "has files" state. | `metrics/d-chat-long.txt` |

**7. Composer and attachments**

| ID | Sev | Finding | Root cause | Evidence |
|---|---|---|---|---|
| A-47 | S3 | "+" button is 32x32 with 8px radius and sits 4px low; the wrench beside it is 40x40 round (legacy: both 40px round). | `#attach-btn` is an `IconButton`; `#tools-button` is a raw button. | `metrics/d-home.txt` |
| A-48 | S4 | Send button is grey at 0.5 opacity when empty (legacy solid blue); placeholder reads "Type a message…" (legacy "Start a conversation..."); a gradient band sits behind the composer. | `Composer.tsx` disabled state; `components.css:1125`. | `c-d-home-*.png` |
| A-49 | S2 | Uploading a file on the home page creates a "New Conversation" chat in the sidebar before anything is sent; "New Chat" keeps the chip, and after a reload the chip is gone but the ghost chat and its file remain. | `Composer.tsx:197-201` uploads under a fresh chat id; nothing discards it. | s7; ghost rows in `tour-m-light/06-sidebar.png` |
| A-50 | S2 | Chips staged for one chat carry into temporary mode and other chats (the file belongs to a different chat id). | `chatForUploads` and `attachments` are not reset on route/mode change. | `tour-d-light/17-temp-chat.png` |
| A-51 | S3 | No drag-and-drop or paste upload; no image preview before send (legacy `file-upload-zone`, `file-preview-container`). | Not ported. | code (0 hits) |
| A-52 | S4 | With 10 lines typed the box stops growing at 200px and the first lines scroll out with no fade; "+" and wrench stay vertically centred on the tall box. | `.input-container` alignment. | `tour-d-light/04-*.png` |
| A-53 | S3 | `/help` only shows a 3s toast; `/skills` works. Slash menu is fine otherwise. | `Composer.tsx:257-261`. | `tour-d-light/74-*.png` |

**8. Streaming behaviour**

| ID | Sev | Finding | Root cause | Evidence |
|---|---|---|---|---|
| A-54 | S1 | A turn that asks for clarification hangs forever at "Thinking… / Request Clarification · Running": there is no UI to answer. | Clarification popover not ported (`static/js/clarification-popover.js`, `/api/tools/active`, `/api/tools/clarification/response`). | `d11-clarify-done.png` |
| A-55 | S2 | Retry on a multi-step turn deletes only the last assistant message and resumes, so earlier tool rounds stay; Delete removes one step, not the turn. | `MessageList.tsx:391-401`, per-message ids. | s5 test 6 |
| A-56 | S3 | After Stop the partial reply is shown, but a reload loses it (only "Retry response" remains). | Client-only `interrupted` state. | s5 test 3 |
| A-57 | S2 | File-system mode: the files panel neither opens nor refreshes when the agent writes a file. | `send-turn.ts:98-100` invalidates chat and chats only; no stream handling of file updates (legacy `handleFileSystemUpdate`). | s5 test 8 |
| A-58 | S3 | No resume banner for an interrupted turn (`resume_needed`), no model-switch overlay, no research plan/progress UI; `last_model` is never saved with the chat. | Not ported. | code (0 hits) |
| A-59 | S3 | Markdown is re-rendered in full on every chunk (selection lost, "Copied" label resets, mermaid re-runs). | `Markdown.tsx:11` on the whole text. | code |
| A-60 | S3 | Relative links in replies (`a.file-link`) navigate the browser to a non-route ("Page not found"); mermaid pop-out button does nothing. | `renderer.ts:109-111`, `Markdown.tsx:86`. | code |

**9. Chat settings and modes**

| ID | Sev | Finding | Root cause | Evidence |
|---|---|---|---|---|
| A-61 | S2 | File System, Browsing and Code Execution toggles and "User preferences" reset on every reload; opening an existing chat never restores its model, modes, persona or sampling (legacy did, `static/script.js:715-800`). A file-system chat continued after a reload is sent with the mode off. | `state/settings-store.ts:95-104` persists research only; nothing reads the chat detail. | s5 test 8 |
| A-62 | S2 | Thinking profile "None" does not turn thinking off: the request still carries `enable_thinking: true` (legacy sets it from the profile, `static/js/settings-manager.js:413-419`). Chat defaults (`my_ai_chat_defaults`) and the research depth selector (Regular/Deep) are not ported. | `ChatSettingsModal.tsx:138` sets `thinking_profile` only. | code |
| A-63 | S3 | Slider number box clamps on every keystroke: typing 5000 gives 32768 and the field cannot be cleared; values are left-aligned in one box and right-aligned in another; a native spinner appears on hover. | `components/ui/Slider.tsx:42-45`. | s7; `tour-d-light/48-*.png` |
| A-64 | S4 | Slider track shows no fill; "Reset to model default" is indented 13px from the labels; "Model updated" status never clears; the dialog keeps a large empty area on the first two tabs. | Fill cause not isolated (the `--fill` variable is set); ghost button padding. | `tour-d-light/43,48` |

**10. Sidebar and workspaces**

| ID | Sev | Finding | Root cause | Evidence |
|---|---|---|---|---|
| A-65 | S3 | Workspace icon shrinks to ~4px when the name is long (also in the "Move to workspace" submenu). | Inline flex row without `flex-shrink: 0` (`RecentChats.tsx:363-370`). | `tour-d-light/03,08` |
| A-66 | S3 | Collapsed rail: brand logo is clipped at the left edge (x 3-18) and the toggle is not aligned with the rail icons (47 vs 36). | `components.css:2458-2466`. | `tour-d-light/16-*.png` |
| A-67 | S4 | Footer is 34px taller than legacy (email row), so Settings/System/Logs sit 34px higher and the chat list is 34px shorter; temp-chat button is full opacity inside a chat (legacy dims it to 0.4 there); new-workspace icon is a plain grid (legacy grid-plus); Logs has no active state on `/logs`. | `Sidebar.tsx:212-216` and CSS. | `metrics/d-home.txt` |
| A-68 | S3 | Sidebar resize handle is rendered but does nothing; collapsed state is not remembered. | `Sidebar.tsx:63` has no handlers (legacy `syncSidebarWidth`). | code |
| A-69 | S3 | Logs link and workspace delete do full page loads (`<a href>`, `window.location.assign`). | `Sidebar.tsx:204`, `WorkspacePage.tsx:62`. | code |
| A-70 | S4 | Icon picker dialog is taller than the viewport (bottom row cut, no scroll cue). | `IconPickerDialog` + modal max-height. | `tour-d-light/13-*.png` |
| A-71 | S3 | Workspace page: two "Files" headings, a phantom "workspace" folder in an empty 400px white panel, rename field with a 2px black border and legacy pill buttons, unevenly spaced icon buttons, chat cards without a card surface, no chat count; files only appear after pressing the top-right button. | Inline styles in `WorkspacePage.tsx`; directory entries rendered as folders. | `tour-d-light/39-41` |

**11. Artifacts**

| ID | Sev | Finding | Root cause | Evidence |
|---|---|---|---|---|
| A-72 | S2 | The drawer overlays the chat and covers the right half of the composer and messages instead of resizing the chat (legacy right sidebar pushes content). | `.artifact-drawer` fixed overlay. | `tour-d-light/25-*.png` |
| A-73 | S3 | With a file open the tree shrinks and clips the selected row ("page.html" cut in half). | `.artifact-tree--compact` max-height (`components.css:1693`). | `tour-d-light/30-*.png` |
| A-74 | S3 | Switching files or closing the drawer discards unsaved edits without asking; the viewer disappears while the next file loads. | `ArtifactPanel.tsx:63-65, 232`. | code |
| A-75 | S3 | Missing vs legacy: rename/move, new folder, delete folder, download, copy, undo/redo, run file, live terminal, version diff, approve/suggest, autosave indicator, language badge. Versions dialog uses legacy pill buttons and inline styles, has no error handling on "View". | Not ported; `VersionsDialog.tsx`. | `tour-d-light/27-*.png`, code |

**12. Settings dialogs and form primitives**

| ID | Sev | Finding | Root cause | Evidence |
|---|---|---|---|---|
| A-76 | S4 | Mixed button systems in one dialog: "Save code runner settings" is a 48px legacy pill with a shadow next to 36px primitives; code-runner inputs are 48px tall, selects 36px. | `SystemSettingsModal.tsx:114` `btn-primary`, `form-styles.ts`. | `tour-d-light/49,50` |
| A-77 | S4 | Sub-dialog titles are centred, top-level titles left-aligned; the dialog jumps vertically between list and form; the title stays "Skills" while adding. | `.ui-modal__header-row` with a back button. | `tour-d-light/52-60` |
| A-78 | S4 | Forms: hint text touches the next field label; Save/Cancel sit left in the body with Save first (PromptDialog: footer, Cancel first); persona form has no Code Execution toggle although the API stores one. | `CrudList`/form CSS; `PersonasDialog.tsx`. | `tour-d-light/54,56,59` |
| A-79 | S4 | Agent configuration: last card is clipped by the footer; model manager: "Run speed test" touches the select (0px gap); number inputs show native spinners on hover. | `.agent-card` list padding; `ModelsDialog.tsx:103`. | `tour-d-light/61,62` |
| A-80 | S3 | Missing vs legacy: git PAT and allowed commands, clear all chats, reset app, telemetry chart for the speed test (raw JSON now), preferences search/filter/sort, skills search. | Not ported. | code (0 hits) |

**13. Logs and tool dialogs**

| ID | Sev | Finding | Root cause | Evidence |
|---|---|---|---|---|
| A-81 | S3 | Logs table runs off the right edge (Type column cut) and the page is off-centre (left margin 296px, right 16px); expanded rows are tracked by index, so the 5s refresh expands the wrong rows. | `.logs-page` width; `LogsPage.tsx:51, 72-80`. | `tour-d-light/67-*.png` |
| A-82 | S3 | Code execution history picks the streaming chat's id before the open chat's, dumps raw JSON and has no error state; the portal dialog ignores the session it creates. | `CodeHistoryDialog.tsx:8-10`, `PortalDialog.tsx`. | code, `tour-d-light/65,66` |

**14. Theme and background**

| ID | Sev | Finding | Root cause | Evidence |
|---|---|---|---|---|
| A-83 | S2 | The particle background is invisible everywhere in the light theme (it shows in dark, and in legacy in both). | `styles/components.css:2250-2253` paints `html, body` with `--bg-primary`, covering `#ambient-bg` (z-index -1); a dark rule makes `body` transparent again. | `c-d-home-react.png` vs `c-d-home-legacy.png`, s8 |
| A-84 | S4 | The theme class is applied after React mounts (light flash for dark users; not compared with legacy); every dialog shows a blurred dark smudge of the page text through its glass surface. | `hooks/useThemeSync.ts`; modal glass opacity. | code, `tour-d-light/52-*.png` |

**15. Tests and leftovers**

| ID | Sev | Finding | Root cause | Evidence |
|---|---|---|---|---|
| A-85 | S2 | 355 unit tests and lint pass while A-01, A-03, A-11, A-16, A-18 and A-22 ship: no test feeds `toTurns` the real API shape (array `tool_calls`, several assistant messages), none checks popover placement, the create/fetch order, the temporary-chat send or the viewport meta. E2E specs replace the chat detail with a fixture. | Test gaps. | baseline run |
| A-86 | S4 | 37 inline `style={{…}}` blocks remain (ratchet baseline not at zero: RecentChats 10, WorkspacePage 7, VersionsDialog 6, forms 6, SystemSettings 6 …); `components/ui/ContextMenu.tsx` is unused outside the demo page. | Phase 7 of the QA plan not finished. | `test/inline-style.test.ts` |

### Race pass 2026-11-10 (follow-up to the user's report over the Cloudflare tunnel)
Method: the rig (`MYAI-52-evidence/scripts/up.sh`) with Playwright `page.route` adding latency to `/api/**` and `/v1/**`: random 40-600ms on every call (`race.mjs`, 5 runs per flow) and targeted delays with a request/response timeline (`race2.mjs`, cases A B C D F G I N Q S). Backend ordering read in `backend/chat/router.py` (`chat_completions`, `resume_chat`, `stop_chat`), `backend/task_manager/{executor,manager,worker}.py`.

**The reported symptom is A-11.** "Error that the chat does not exist, then the messages are there" reproduces exactly: the create `PATCH /api/chats/<id>` leaves ~20ms before the page's `GET /api/chats/<id>`; when the GET is answered first it is a 404, the page shows "This chat no longer exists." (no composer, no Stop) for the whole reply, and the transcript appears when the end-of-stream refetch lands. Hit 3/5 with 40-600ms jitter and once in a single run with 80-300ms (`race2.mjs` I); never with no latency. Fix is planned in MYAI-56 (unchanged).

**A-14 is worse than recorded.** The doubled transcript at the end of a turn lasts one sidebar-list round trip, not 3ms: 250-500ms at 80-300ms latency (`race2.mjs` D: `u2b2` from 3030ms to 3537ms; also I, S4), on every turn, including retry and edit. Cause confirmed: `consume`'s `finally` awaits the chat refetch and then the list refetch before `finish()`. Over the tunnel this is a visible "two turns for one message" flash and adds to the multi-turn report. Planned in MYAI-54 (severity S2, was S3).

New findings:

| ID | Sev | Finding | Cause | Evidence |
|---|---|---|---|---|
| A-87 | S1 | After Stop the UI is ready again as soon as its refetch returns, not when the server has stopped. If `POST /stop` is still on its way (1.5s in the test), Retry or a new message is refused with the toast "a response is already in progress"; the stopped partial reply disappears, and a typed message is lost (the box was cleared before the send). | `stopTurn` aborts the stream, then `consume`'s `finally` refetches and calls `finish()` without waiting for `/stop`; `sendTurn`/`resumeTurn` call `start()`, which clears `interrupted`; `Composer.send` clears the text first. Legacy awaits `/stop` and then reloads the chat (`static/script.js` 3664-3670). | `race2.mjs` S1, S2, Q2 |
| A-88 | S2 | After Stop in a multi-step turn the screen shows replies the server has deleted: the refetch (7 rows, `is_running: true`) is answered before `/stop` rolls the chat back to the user message; three stored rows stay with no "Stopped" marker and no Retry until a reload, which then shows only the user message. | Same ordering: the refetch races the rollback in `stop_chat`; nothing refetches after `/stop` answers. | `race2.mjs` S3 |
| A-89 | S3 | For the duration of the stop refetch (250-400ms with latency) the live row and the "Stopped" row are both shown and the button still says Stop; Retry clicked in that window does nothing and says nothing. | `MessageList` renders `LiveAssistant` while the stream store has a chat id and `InterruptedAssistant` as soon as `interrupt()` is called; `resumeTurn` returns silently when a chat id is set. | `race2.mjs` C (100ms), S4 |
| A-90 | S3 | The chat detail cached by the stop refetch keeps `is_running: true`. Leaving the chat and coming back fires a reattach (`GET /stream` answers 204): the Stop button flashes and the stopped partial reply is gone. | `ChatPage` reattach effect trusts the cached flag on mount; `reattachTurn` calls `start()` (which clears `interrupted`) before it knows there is a stream. | `race2.mjs` N |
| A-91 | S2 | Deleting the chat that is streaming stops nothing: the app goes to the home page, whose send button is "Stop" for the deleted chat until the turn ends (17s in the test), Enter there does nothing, and the server generates the whole reply for a chat that no longer exists. | `RecentChats.confirmDelete` calls only `chatsApi.remove`; `DELETE /api/chats/<id>` (`backend/chat/router.py`) does not stop the task. | `race2.mjs` F |

Checked and clean (no anomaly in 5 jittered runs each, plus the timelines): a follow-up sent the moment the reply ends; Retry after a finished reply; edit + regenerate (the refetch and `/resume` leave together, the refetch can return `is_running: true` and is corrected by the end-of-turn refetch); reload mid-stream and leaving and returning mid-stream (reattach replays once, one row at the end); double Enter (one send); `is_running` at a normal end of turn (false in every run: the response body ends after the task state is cleared). Not tested here: temporary chat (cannot send at all, A-16), uploads during the first send, two tabs on one chat.

Server note (outside the frontend epic): `DELETE /api/chats/<id>` leaves a running turn alive, and `task_manager.stop_task` only signals the worker, so a turn can still count as running for a moment after `/stop` answers.

## Review history

## Log
- 2026-11-10: created, started
- 2026-11-10: audit done, 86 findings (A-01 … A-86) recorded under Verification
- 2026-11-10: linked relates_to MYAI-53 (fix epic cut from the findings)
- 2026-11-10: corrections found while planning: A-47 legacy attach button is 36x40 (not 40x40); A-64 root cause is `styles/legacy.css` `input[type="range"]` rules outranking `.ui-slider__input`; A-33 legacy opaque surfaces are iOS-only (`is-ios`)
- 2026-11-10: found while planning MYAI-67 (extends A-78): the persona form's Git mode toggle is never saved; the persona API reads neither `git_mode` nor `code_execution_mode`. Backend gap, not in the epic's scope
- 2026-11-10: race pass with injected latency: reported new-chat symptom confirmed as A-11, A-14 raised to S2, 5 new findings (A-87 … A-91)
