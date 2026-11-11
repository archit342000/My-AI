# Frontend

The UI is a React 19 + TypeScript single-page app in `frontend/`, built with Vite.
Flask serves the built app from `frontend/dist/` when `FRONTEND=react`, which is the default.
The previous vanilla UI stays at `/legacy/` for one release and then gets removed.

## Run, build, test

| Task | Command (from `frontend/`) |
|------|----------------------------|
| Install | `npm ci` (Node 22+) |
| Dev server | `npm run dev` (http://localhost:5173, proxies `/api`, `/v1`, `/legacy` to Flask on :5000) |
| Build | `npm run build` (typecheck, then `dist/`) |
| Typecheck, lint | `npm run typecheck`, `npm run lint` |
| Unit tests | `npm run test` (Vitest + Testing Library) |
| End to end | `npm run e2e` (Playwright, system Chrome at `/opt/google/chrome/chrome`) |
| Full-stack end to end | `npm run e2e:stack` (real backend and scripted model; not in `check.sh`; see `docs/standards/testing.md`) |

Backend: `FRONTEND=react|legacy` selects which UI Flask serves at `/`. `/legacy/` always serves the old UI.
A React build missing from `dist/` returns 503 with the build command.

## Layout

| Path | Contents |
|------|----------|
| `src/api/` | Typed `fetch` client, SSE reader, endpoint modules per area |
| `src/app/` | User gate, router, root layout (holds the one composer for `/` and `/chat/:chatId`), sidebar |
| `src/components/` | Shared UI: `ui/` (Button, Field, Select, Toggle, Slider, Tabs, Menu, Popover, Sheet, Modal, Window, ConfirmDialog, Toast, Notice, Skeleton, EmptyState, DeadEnd), `icons/`, `markdown/`, `background/` |
| `src/features/` | `chat/`, `composer/`, `sidebar/`, `artifacts/`, `workspace/`, `settings/`, `tools/`, `logs/`, `home/`, `dev/` |
| `src/lib/` | Pure logic with unit tests: markdown pipeline, chat model, popover placement, scroll, particles, theme |
| `public/` | Files copied as-is to the `dist/` root: `theme-init.js`, loaded from `index.html` before the app |
| `src/state/` | Zustand stores: UI, settings, stream, modal, current user |
| `src/styles/` | `tokens.css` (the Console at Rest shared values, a synced copy: never edit), `fonts.css`, and `ds/` (the app's own sheets, one per area: base, controls, layers, frame, home, chat, content, files, workspace, settings, logs, tools, states, phone, dev) |
| `scripts/` | Generators for icon and tool-label data from `static/js/`; `sync-design-tokens.cjs` copies `tokens.css` from the design repository |

## State

- **Sidebar:** its width and collapsed state are device preferences (`my_ai_sidebar_width`, `my_ai_sidebar_collapsed`, kept by `ui-store`,
  global on purpose like the theme and `my_ai_artifact_width`, not per user). On a phone the drawer always starts closed and opening it is not
  remembered. `useSidebarResize` drives the handle (drag and arrow keys) and keeps `--sidebar-width` at the sidebar's real width. Deliberate
  differences from legacy: the signed-in email row in the footer (multi-user), a Logs link that is an in-app `NavLink`, and a files section on
  the workspace page that is always shown (one "Files" section; the server's empty `workspace` placeholder folder is hidden there).
- **Staged files:** `state/attachment-store.ts` keeps the files staged for sending per chat (the open chat's id, the temporary chat's id,
  or a draft id for the next new chat), so a chip only shows in the chat it was uploaded for. Files staged for a new chat that is never
  sent are deleted when the user presses New Chat, leaves the landing page, discards a temporary chat (the server marks it on its first send, hides it from the lists until saved and removes it after a day) or closes the page
  (`features/composer/draft-cleanup.ts`, `useDraftCleanup`); a draft in an existing chat is kept. Files can be picked, dropped on the
  page area or pasted; `/help` opens a list of commands and skills.
- **Theme:** `public/theme-init.js` (loaded from `index.html` before the app) sets the `dark` class, `data-theme` and `data-glass` on `<html>` from `my_ai_theme_mode`, `my_ai_glass_mode`, the OS setting and whether the browser can blur, before first paint; `useThemeSync` keeps them in step after mount. A unit test keeps the script in step with `resolveDark` and `resolveGlass`. It tolerates blocked storage and missing APIs on purpose: it runs before the app and must never stop the page from loading. `data-theme` is always explicit and is what every sheet reads (the `dark` class is still set but no style reads it). Panels: `glassMode` is `auto`, `frosted` or `solid`; `auto` is solid only where blur is unsupported, and solid removes every `backdrop-filter`. Less motion: `tokens.css` removes all CSS animation and the particle canvas draws one still frame. Only `html` carries the page colour: a `body` background would paint above the fixed particle canvas.
- **Server state:** TanStack Query. Query keys live in `api/chats.ts`, `api/settings.ts` and `api/filesystem.ts`.
- **UI state:** Zustand. Stream state (`state/stream-store.ts`) holds the in-flight turn.
- **Browser state:** `localStorage` keys keep the legacy names and formats (`my_ai_selected_model`,
  `my_ai_sampling_params`, `chatWorkspaces`, ...). Do not rename them. They are per user: every read and write goes
  through `nsKey()` (`lib/user-storage.ts`), which keeps these exact names for the admin (who owns all existing
  browser data) and uses `<key>:<userId>` for any other user. The theme, panel mode (`my_ai_glass_mode`) and artifact-drawer width stay global (device
  preferences).
- **Per-chat settings:** `state/settings-store.ts` holds the active values (what the next send uses) and a `defaults` snapshot
  (what a new chat starts from, mirrored in storage). Opening a chat (`features/chat/useChatSettings.ts`, once per chat when the
  chat has loaded and the model list has loaded or failed) copies the chat's saved model, modes, persona, preferences and sampling values over the
  active ones (`applyChat`); leaving the chat puts the defaults back (`resetToDefaults`). While a chat's values are active the
  setters change the active values only, so one chat's settings never become the defaults; a toggle changed in an open chat is
  sent with the next message and lasts for that visit. The file-system, browsing and code-execution toggles persist in
  `my_ai_modes`, user preferences in the `userPreferences` field of `my_ai_chat_defaults`. `enable_thinking` always follows the
  thinking profile (`lib/thinking.ts`: "none" is off). "Reset to model default" on temperature or top p lasts for the visit: the server keeps the
  saved value when a request omits it, so reopening the chat brings it back.
- **Current user:** `app/UserGate.tsx` loads `GET /api/me` before anything user-dependent renders (no retry on 401), records
  the user in `state/user-store.ts`, calls `initUserStorage` and `settings-store.hydrate()` (the only place that reads
  storage), then renders the app. A 401 shows "Your session has expired." with a Reload button (full page from the gate,
  banner from `RootLayout` for a later request); a 403 shows a toast and still throws `ApiError`.
- **Admin gating:** the UI hides what the server refuses for a user (`useIsAdmin()`): the Logs link and page, the System link, the
  admin-only parts of Settings (model loading, agents, runner, git agent: GitHub token and allowed git commands), the Git agent toggle
  (a user's `gitMode` stays off) and the browser portal button. This is convenience only; the server enforces it.

## Conventions

- **Look:** the app follows the Console at Rest design system (rule book, shared values and reference demo in the design repository
  `console-at-rest`). Colours, lettering, corners, shadows, layers and speeds come only from `styles/tokens.css` (refresh with
  `node scripts/sync-design-tokens.cjs <checkout>`); spacing uses the named steps where one fits (the reference page's in-between sizes such as 6, 10 and 14px are not named yet and are written out). Load order in `main.tsx`:
  fonts, tokens, then `ds/*` with `phone.css` after the screens. Guards: `lib/design-tokens.test.ts` (no raw colours, corners, shadows, layers or
  speeds; `styles/` holds only those three entries), `test/css-coverage.test.ts`, `test/inline-style.test.ts` and `test/wording.test.ts`
  (plain wording, one-character ellipsis). The typefaces (Sora, Instrument Sans, JetBrains Mono) are served by the app from `@fontsource-variable/*`.
- **Icons:** the app's icons draw the design system's starting set (rule book 2.6) from `components/icons/icon-paths.ts`; the workspace registry only adds the icons a workspace can be given.
- **Sizes:** phone up to 599px, tablet 600 to 1023px, computer from 1024px. Touch targets are 48px on a phone, 44px elsewhere.
- Every model's HTML goes through `renderMarkdown` (DOMPurify). Do not inject unsanitised HTML.
- The attachment `[System Note: ...]` the router appends to a user message is for the model: `src/lib/chat-model.ts` strips it from
  user bubbles and the edit box and shows its files as chips. The stored message keeps it.
- A reply's model label shows the legacy display name (`General Text (<model>)`, built from `/api/models/config` by
  `lib/model-options.ts`; the raw id until the config is loaded). Action rows, the Stopped notice and inline errors render inside the
  answer column. The files button is dimmed (still clickable) while the open chat has no files; links in answers use the accent
  colour in both themes. These last two differ from the legacy UI on purpose.
- **Layers:** `Modal` (small dialogs), `Window` (tool windows: browser, code run history, version history, thought process), `Sheet` and
  `Popover` (a menu is a sheet from the bottom on a phone). All handle Escape (top of the stack only), focus trap, focus restore and scroll
  lock. On a phone, Back closes the newest layer first (`lib/back-layer.ts`, one history step shared by every open layer; the settings page
  is left out because it navigates with `replace`). Number inputs hide the native spinner. Log rows are expanded by a stable key (`rowKeys`);
  identical id-less rows are told apart by their order from the end, so when the oldest falls off the row limit the rest shift (known limit).
- **Awkward states:** loading shows `Skeleton` placeholders in the shape of what is coming; an empty list shows `EmptyState` (a dotted
  drawing, one line, one action); not found, gone, signed out, no access and a crash show `DeadEnd` screens from `app/DeadEnds.tsx`
  (`ErrorBoundary` catches render errors); offline is said in the composer.
- Generated files (`*.generated.ts`) come from `scripts/`. Do not edit them by hand.

## Streaming

`features/chat/stream-reducer.ts` mirrors the legacy read loop in `static/script.js`:
content and reasoning deltas, tool-call fragments merged by id, tool results attached to calls,
`event` deltas (activity labels, not answer text) and `__redact__` rolling back to the last snapshot.
Recorded fixtures live in `src/test/fixtures/stream/`.

A reply is one assistant turn: everything between two user messages is an ordered list of steps
(reasoning, text, tool call with its result, event; `Step` in `src/lib/chat-model.ts`). The live reducer and
`toTurns` (stored messages) build the same list, so the live row and the saved row have the same structure.
Sub-agent steps carry the agent name and sit after the tool call that started them. While a chat streams,
the live row replaces the persisted rows of the turn being generated. Retry and Delete act on the whole turn
(they delete its first stored message; the server removes the rest). Text steps are joined with a blank line.

A turn can wait for the user: the server repeats a `request_clarification` tool call (same id) once its callback is registered, and the
reducer keeps that as `LiveTurn.pendingRequest` without touching the step it repeats (a code-runner approval repeats the run's id).
`ClarificationPrompt` shows the question and options under the live reply; answering posts `/api/tools/clarification/response`, the
`tool_result` closes the request, Cancel stops the turn. A reload reattaches to the running turn and the replayed stream brings the
prompt back.
Starting a chat: `sendTurn` puts the new chat in the detail and list caches, starts the stream store and only then
calls the `navigate` callback, so the chat page mounts with data (no loading, error or not-found state) and the
sidebar lists the chat at once. The composer clears its text and files only when `sendTurn` accepts the turn
(`onAccepted`). One turn runs at a time: Stop shows only in the chat that is generating, and a send or Retry in
another chat is refused with a toast that says why. A chat page shows not-found for a 404 unless its own turn is
starting (the server creates the chat a moment after the page opens); other load errors show only when the chat
has no data. If creating a new chat fails, the typed text is lost and the page shows not-found with a way back.

After a turn: when a file-changing tool finishes (`lib/fs-tools.ts`), the stream consumer invalidates the files list
of the chat and, the first time in a turn and only in file-system mode, opens the files drawer. A chat the server marks
`resume_needed` shows a Resume/Dismiss banner (replacing the Retry button under the last message). A stopped reply is
not saved by the server, and its notice says so. While a reply streams it is rendered block by block
(`StreamingMarkdown`), so finished blocks keep their DOM; saved replies render in one pass. Blocks end at blank lines
outside code and math fences, so a loose list or a table with blank lines is drawn per block until the reply is saved. File links in a reply open
the file in the files drawer (`ui-store.openArtifact`), and the mermaid pop-out opens the diagram in a dialog.
The resume banner is per chat: while another chat generates, its Resume is refused with the busy toast. While a reply streams, each block is
rendered on its own, so a JSON-escaped `\n` in a one-line block can look different until the reply is saved.
A stopped reply's notice lives only in the open page: after a reload the reply is gone, as the server rolled it back.
The chat's model is saved as `last_model` with the first send and whenever it changes.

Stop, Retry and delete follow the server's state: `stopTurn` marks the store `stopping`, posts the stop request and aborts the stream; `consume` waits
for the stop request before it refetches the chat, so the screen never shows replies the server has since rolled back, and the composer shows a
disabled "Stopping" button and the stopped row's Retry is disabled until the store is idle. The live row and the Stopped/failed row are never drawn
together. A send or Retry refused as "a response is already in progress" within 3 seconds of a stop is repeated (5 attempts, 400 ms apart), because
the server only signals the old worker; a refusal that remains puts the stopped partial reply back and the composer puts the typed text and files
back (only into an empty box). `reattachTurn` makes the store busy only once a stream came back, so reopening a stopped chat never flashes Stop.
Deleting a chat (or discarding a temporary one) stops its turn first (`stopIfStreaming`). Limit: nothing on the server bounds how long a worker takes
to exit, so a slower exit still ends in the refusal toast with the reply and text kept. A stop request that never answers keeps the chat in "Stopping" until the browser gives up on it; a reload
recovers. A chat whose stop was answered a moment ago (or that has a stopped row) is not reattached to, even if the refetch still says it is running. Each repeated attempt after a stop uses one of the user's turns per minute (the server counts a request refused as "in progress"), so a repeat that fails 5 times costs 5; and a turn another tab starts during that short window is attached when the chat next refetches.

Settings is a full-screen page (`features/settings/SettingsPage.tsx`; the navigation and Files panels step aside while it is open), opened with `?settings=<part>` on whatever page is
underneath, so the chat stays mounted and its own settings are not reset (`/settings[/:section]` redirects there). Parts: Chat, Models,
Personas, Skills, Memory, Agents, System. A change saves by itself and the header's light says "Saved" (`lib/save-light.ts`); only list
items (personas, skills, memory, agents) and the GitHub token have a Save button. Outside a chat the Chat part edits the store's `defaults`
(`setDefaults`), so the next new chat starts from them; in an open chat it edits that chat's values. "Delete all chats" (any user, behind a
confirmation) stops a turn that is generating, deletes the caller's chats, discards a temporary chat and returns to the empty home page. The
GitHub token is write-only: sent once, never read back, shown only as "Configured" or "Not configured". Memory has a text search, a tag
filter and a sort; skills have a text search (client-side, `lib/list-filter.ts`).

The thought box is a timeline: one box per assistant turn with its entries along a line in the order they happened: thoughts as plain text, each tool call as one row that folds open (status light, plain name, what it was asked; inside, what was sent and what came back), event dividers, and a box per sub-agent run holding that agent's own entries. Built by `lib/thought-timeline.ts` from the turn's steps, drawn by `ThoughtBox`, `TimelineEntry` and `ThoughtFullView` ("Open bigger": a window with every entry open). The header says "Thinking…" with the newest event or running tool for as long as the turn streams, and "Thought process" after. Whether a box is open is kept in `state/thought-store.ts` by `chatId:ordinal` (the number of user turns up to the one it answers), so it stays open when the live reply is replaced by the saved one; deleting a turn forgets the chat's open boxes. A turn with nothing to show has no box. The retry notice is fixed text with a spinner; the server's message is not shown.

## Phones

Phone rules (599px and below) live in `src/styles/ds/phone.css` and beside each screen's own rules, and are checked at 390px by
`e2e/mobile-layout.spec.ts` (the `phone` Playwright project). The side panel becomes an opaque drawer that starts closed and closes when
a layer opens; menus open as sheets from the bottom; windows, the files panel and the settings page take the whole screen with opaque
backgrounds; every control is at least 48px. Toasts sit above the composer (`--composer-h`).

The viewport meta (`index.html`) is `interactive-widget=resizes-content` (the layout resizes with the on-screen keyboard
where the browser supports it), `maximum-scale=1.0, user-scalable=no` and `viewport-fit=cover`. Where the keyboard only overlays the page
(iOS Safari), `useKeyboardOffset` raises the composer by the covered height and publishes it as `--keyboard-offset` on `<html>`; the
transcript pads its bottom by it and `useAutoFollow` scrolls a pinned reader to the end again when the window or visual viewport
resizes. `usePlatformClass` (called by `RootLayout`) adds `is-ios` to `<html>` on iOS and iPadOS and blocks
touches that start outside a scroll area (`SCROLL_AREAS` in `lib/scroll-lock.ts`) so the page cannot rubber-band. The phone Playwright
project simulates the keyboard by shrinking `visualViewport.height` (`e2e/mobile-keyboard.spec.ts`).

## Files panel

One browser (`features/artifacts/FileBrowser.tsx`: tree, search, editor, preview, run output) is used beside a chat
(`ArtifactDrawer`, an `<aside aria-label="Files">`), on the workspace page and full screen. `ArtifactPanel` moves the same DOM box between
those places, so the open file, undo history, scroll positions and width survive. From 1024px the drawer is a third panel of the frame beside the chat
(its width is `--artifact-width`), so `main` narrows; on a tablet it overlays; on a phone it takes the screen. Edits save by themselves after a short
pause (`useAutoSave`); switching file or closing saves first and stays put if that fails, so there is no "discard changes?" prompt. File
actions: Rename, Move (a place picker), Download, Copy, New file or folder, Delete (the server only removes an empty folder; a file read
from disk cannot be renamed or moved). Version history is a two-pane window: pick a version, see it or its difference from the current one,
restore after a confirmation. Run and version history need a chat: for a file opened in a workspace they are shown switched off, with the reason.

## Known gaps

- Per-agent renderers (research, browsing) do not exist; sub-agent steps show as a labelled group of entries.
- The code-execution WebSocket (live runs) is not wired; history is read-only.
- File search matches names, and text only in files opened so far (the server has no content search).
- The previous vanilla UI in `static/` (served at `/legacy/`) keeps its old look until it is removed (`docs/release.md`).
