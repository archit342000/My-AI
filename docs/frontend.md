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
| `src/app/` | User gate, router, root layout, sidebar |
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
- Generated files (`*.generated.ts`) come from `scripts/`. Do not edit them by hand.

## Streaming

`features/chat/stream-reducer.ts` mirrors the legacy read loop in `static/script.js`:
content and reasoning deltas, tool-call fragments merged by id, tool results attached to calls,
`event` deltas (activity labels, not answer text), sub-agent deltas (counted, not shown yet),
and `__redact__` rolling back to the last snapshot. Recorded fixtures live in `src/test/fixtures/stream/`.

## Files panel

Above 1024px the open files drawer sits beside the chat: it publishes `--right-sidebar-width` so `main` (the transcript and the composer) narrows, as in
the legacy page; at 1024px and below it overlays. The selected row is kept in view, leaving a file with unsaved edits (switching, closing, new file)
asks first, and the file on screen stays until the next one has loaded. File actions: Rename, Move to folder, Download and Copy contents
(the "More" menu; a file read from disk cannot be renamed or moved), New folder, and Delete folder (right-click a folder; the server only removes an
empty one). Version history shows the current version, views a version, compares it with the current one (the server's line-by-line diff) and restores it
after a confirmation; it needs a chat, so it is not offered for a file opened in a workspace.

## Known gaps

- Sub-agent activity feeds are not rendered (their messages are hidden from the transcript).
- The code-execution WebSocket (live runs) is not wired; history is read-only.
- Mermaid pop-out and file-link navigation are not implemented.
