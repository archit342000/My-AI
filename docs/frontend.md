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

Backend: `FRONTEND=react|legacy` selects which UI Flask serves at `/`. `/legacy/` always serves the old UI.
A React build missing from `dist/` returns 503 with the build command.

## Layout

| Path | Contents |
|------|----------|
| `src/api/` | Typed `fetch` client, SSE reader, endpoint modules per area |
| `src/app/` | User gate, router, root layout (holds the one composer for `/` and `/chat/:chatId`), sidebar |
| `src/components/` | Shared UI: `ui/` (Modal, Toast, ContextMenu, ConfirmDialog), `icons/`, `markdown/`, `background/` |
| `src/features/` | `chat/`, `composer/`, `sidebar/`, `artifacts/`, `workspace/`, `settings/`, `tools/`, `logs/`, `home/`, `dev/` |
| `src/lib/` | Pure logic with unit tests: markdown pipeline, chat model, popover placement, scroll, particles, theme |
| `src/state/` | Zustand stores: UI, settings, stream, modal, current user |
| `src/styles/legacy.css` | Legacy stylesheet, imported unchanged; class names are shared with the legacy UI |
| `scripts/` | Generators for icon and tool-label data from `static/js/` |

## State

- **Server state:** TanStack Query. Query keys live in `api/chats.ts` and `api/settings.ts`.
- **UI state:** Zustand. Stream state (`state/stream-store.ts`) holds the in-flight turn.
- **Browser state:** `localStorage` keys keep the legacy names and formats (`my_ai_selected_model`,
  `my_ai_sampling_params`, `chatWorkspaces`, ...). Do not rename them. They are per user: every read and write goes
  through `nsKey()` (`lib/user-storage.ts`), which keeps these exact names for the admin (who owns all existing
  browser data) and uses `<key>:<userId>` for any other user. The theme and artifact-drawer width stay global (device
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
- **Admin gating:** the UI hides what the server refuses for a user (`useIsAdmin()`): the Logs link and page, the runner
  settings and the agent, model and stealth links in System Settings, the four admin dialogs in `DialogHost`, the Git Agent
  toggle (a user's `gitMode` stays off), the "Git agent" section of System Settings (GitHub token, allowed git commands) and the browser
  portal button. This is convenience only; the server enforces it.

## Conventions

- Keep legacy class names so the shared stylesheet still applies.
- Every model's HTML goes through `renderMarkdown` (DOMPurify). Do not inject unsanitised HTML.
- The attachment `[System Note: ...]` the router appends to a user message is for the model: `src/lib/chat-model.ts` strips it from
  user bubbles and the edit box and shows its files as chips. The stored message keeps it.
- Dialogs use `Modal`, which handles Escape (top of stack only), focus trap, focus restore and scroll lock.
  Management lists (`CrudDialog`: skills, personas, memory) show the form's own title and put Cancel then Save in the modal footer;
  the form gets the dialog's `formId` and reports `setCanSave`. The persona form offers only the flags the server stores. Number inputs (`.ui-input[type=number]`) hide the native spinner everywhere; typing is the way to change them.
  The browser portal's iframe sits on a neutral surface token (not black) while it loads. Log rows are expanded by a stable key
  (`rowKeys`); identical id-less rows are told apart by their order from the end, so when the oldest of several identical rows falls
  off the row limit the rest shift (known limit).
  While a form is open, Escape, the backdrop and the close button return to the list (so typed text is not lost by accident), the
  back chevron steps up one level (form, list, parent dialog), and focus moves to the first control of the new view.
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

System Settings: "New chat defaults" (thinking profile, user preferences, max tokens, thinking budget) edit the store's `defaults` through
`setDefaults`, so the next new chat starts from them while an open chat keeps its own values. "Delete all chats" (any user, behind a
confirmation) stops a turn that is generating, deletes the caller's chats, discards a temporary chat and returns to the empty home page. The
Git agent section (admin) keeps the GitHub token write-only: it is sent once, never read back, and only "Configured" or "Not configured" is shown;
the allowed git commands are saved on each change with the full list. The memory dialog has a text search, a tag filter and a sort (newest or
oldest); the skills dialog has a text search (client-side, `lib/list-filter.ts`).

**Dropped from legacy:** "Reset app" (it cleared the saved connection settings, which no longer exist under Cloudflare Access, together with the saved
model and theme and then reloaded). The model and theme can be changed in their own dialogs; nothing else in it is needed.

The thought box is the legacy timeline: one box per assistant turn with collapsible entries in the order they happened (Reasoning, `Call: <tool>`, `Tool Result: <tool>`, event dividers, and a labelled group per sub-agent run, which also shows that agent's text). Built by `lib/thought-timeline.ts` from the turn's steps, drawn by `ThoughtBox`, `TimelineEntry` and `ThoughtFullView` (a dialog with every entry open). The header says "Thinking..." with the newest event or running tool for as long as the turn streams, and "Thought Process" after. Whether a box is open is kept in `state/thought-store.ts` by `chatId:ordinal` (the number of user turns up to the one it answers), so it stays open when the live reply is replaced by the saved one; deleting a turn forgets the chat's open boxes. A turn with nothing to show has no box. The retry notice is fixed text with a spinner; the server's message is not shown.

## Known gaps

- The legacy per-agent renderers (research, browsing) are not ported; sub-agent steps show as a labelled group of entries.
- The code-execution WebSocket (live runs) is not wired; history is read-only.
- The file tree shows one level; nested folders are listed but not expandable.
