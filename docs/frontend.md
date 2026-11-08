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
| `src/app/` | Router, root layout, sidebar |
| `src/components/` | Shared UI: `ui/` (Modal, Toast, ContextMenu, ConfirmDialog), `icons/`, `markdown/`, `background/` |
| `src/features/` | `chat/`, `composer/`, `sidebar/`, `artifacts/`, `workspace/`, `settings/`, `tools/`, `logs/`, `home/`, `dev/` |
| `src/lib/` | Pure logic with unit tests: markdown pipeline, chat model, scroll, particles, theme |
| `src/state/` | Zustand stores: UI, settings, stream, modal |
| `src/styles/legacy.css` | Legacy stylesheet, imported unchanged; class names are shared with the legacy UI |
| `scripts/` | Generators for icon and tool-label data from `static/js/` |

## State

- **Server state:** TanStack Query. Query keys live in `api/chats.ts` and `api/settings.ts`.
- **UI state:** Zustand. Stream state (`state/stream-store.ts`) holds the in-flight turn.
- **Browser state:** `localStorage` keys keep the legacy names and formats (`my_ai_selected_model`,
  `my_ai_sampling_params`, `chatWorkspaces`, ...). Do not rename them.

## Conventions

- Keep legacy class names so the shared stylesheet still applies.
- Every model's HTML goes through `renderMarkdown` (DOMPurify). Do not inject unsanitised HTML.
- Dialogs use `Modal`, which handles Escape (top of stack only), focus trap, focus restore and scroll lock.
- Generated files (`*.generated.ts`) come from `scripts/`. Do not edit them by hand.

## Streaming

`features/chat/stream-reducer.ts` mirrors the legacy read loop in `static/script.js`:
content and reasoning deltas, tool-call fragments merged by id, tool results attached to calls,
`event` deltas (activity labels, not answer text), sub-agent deltas (counted, not shown yet),
and `__redact__` rolling back to the last snapshot. Recorded fixtures live in `src/test/fixtures/stream/`.

## Known gaps

- Sub-agent activity feeds are not rendered (their messages are hidden from the transcript).
- The code-execution WebSocket (live runs) is not wired; history is read-only.
- Mermaid pop-out and file-link navigation are not implemented.
- The file tree shows one level; nested folders are listed but not expandable.
