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
| `src/lib/` | Pure logic with unit tests: markdown pipeline, chat model, scroll, particles, theme |
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
  toggle (a user's `gitMode` stays off) and the browser portal button. This is convenience only; the server enforces it.

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

## Known gaps

- Sub-agent reasoning and tool calls are in the thought box's lists without an agent label, and the newest event shows as the live status line; sub-agent text is kept in the steps but not drawn. The legacy per-agent renderers are not ported.
- The code-execution WebSocket (live runs) is not wired; history is read-only.
- The file tree shows one level; nested folders are listed but not expandable.
