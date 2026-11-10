# frontend

React 19 + TypeScript + Vite single-page app. Replaces the legacy UI in `static/` (served at `/legacy/`).

## Commands

| Command | What it does |
|---|---|
| `npm run dev` | Vite dev server on :5173, proxies `/api`, `/v1`, `/legacy` to Flask on :5000 (`BACKEND_URL` to override) |
| `npm run build` | Typecheck, then build to `dist/` (Flask serves it when `FRONTEND=react`) |
| `npm run typecheck` / `lint` / `test` | Strict TS, ESLint, Vitest + Testing Library |
| `npm run e2e` | Playwright, uses system Chrome at `/opt/google/chrome/chrome` |
| `node scripts/gen-icons.cjs` | Regenerates `src/components/icons/workspace-icons.generated.ts` from `static/js/icons.js` |
| `node scripts/gen-tool-labels.cjs` | Regenerates `src/features/chat/tool-labels.generated.ts` from `static/js/constants.js` |

## Layout

| Path | Contents |
|---|---|
| `src/api/` | Typed fetch client (`client.ts`), SSE reader (`sse.ts`), chat/workspace calls (`chats.ts`), server types |
| `src/app/` | `UserGate` (loads `/api/me` first), router, root layout, sidebar |
| `src/components/` | Shared UI: `ui/` (Modal, Toast, ContextMenu), `icons/`, `markdown/`, `background/` |
| `src/features/` | Feature folders: `chat/`, `sidebar/`, `home/`, `dev/` (dev-only primitives page at `/dev/ui`) |
| `public/` | Files copied as-is to the `dist/` root (`theme-init.js`, loaded from `index.html` before the app) |
| `src/lib/` | Pure logic with unit tests: markdown pipeline, chat model, scroll, particles, theme |
| `src/state/` | Zustand stores (UI state, current user `user-store.ts`) |
| `src/styles/legacy.css` | The legacy stylesheet, imported unchanged so existing class names keep working |

## Conventions

- Keep legacy class names and `localStorage` keys so existing browsers and styles keep working. Settings keys are per user through `nsKey()` (the admin keeps the existing names, others get `<key>:<userId>`); admin-only controls are hidden with `useIsAdmin()`. See `docs/frontend.md`.
- Server state goes through TanStack Query; UI state through Zustand.
- Markdown HTML is always sanitised by DOMPurify before it reaches the DOM.
- Every modal must close on Escape (use `Modal`, which handles the stack).
