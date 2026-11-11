# frontend

React 19 + TypeScript + Vite single-page app. Replaces the legacy UI in `static/` (served at `/legacy/`).

## Commands

| Command                                          | What it does                                                                                                                                                                                            |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `npm run dev`                                    | Vite dev server on :5173, proxies `/api`, `/v1`, `/legacy` to Flask on :5000 (`BACKEND_URL` to override)                                                                                                |
| `npm run build`                                  | Typecheck, then build to `dist/` (Flask serves it when `FRONTEND=react`)                                                                                                                                |
| `npm run typecheck` / `lint` / `test`            | Strict TS, ESLint, Vitest + Testing Library                                                                                                                                                             |
| `npm run e2e`                                    | Playwright, uses system Chrome at `/opt/google/chrome/chrome`; the `phone` project (390px Chrome with touch) runs `mobile-layout.spec.ts` and `mobile-keyboard.spec.ts`, the `desktop` project the rest |
| `npm run e2e:stack`                              | Playwright against the real backend with a scripted model (needs venv Python, a cached tokenizer and `dist/`; not in `check.sh`)                                                                        |
| `node scripts/gen-icons.cjs`                     | Regenerates `src/components/icons/workspace-icons.generated.ts` from `static/js/icons.js`                                                                                                               |
| `node scripts/gen-tool-labels.cjs`               | Regenerates `src/features/chat/tool-labels.generated.ts` from `static/js/constants.js`                                                                                                                  |
| `node scripts/sync-design-tokens.cjs <checkout>` | Refreshes `src/styles/tokens.css` from a checkout of the `console-at-rest` design repository                                                                                                            |

## Layout

| Path              | Contents                                                                                                                                                               |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/api/`        | Typed fetch client (`client.ts`), SSE reader (`sse.ts`), chat/workspace calls (`chats.ts`), server types                                                               |
| `src/app/`        | `UserGate` (loads `/api/me` first), router, root layout, sidebar                                                                                                       |
| `src/components/` | Shared UI: `ui/` (buttons, fields, menus, layers, states), `icons/`, `markdown/`, `background/`                                                                        |
| `src/features/`   | Feature folders: `chat/`, `composer/`, `sidebar/`, `artifacts/`, `workspace/`, `settings/`, `tools/`, `logs/`, `home/`, `dev/` (dev-only primitives page at `/dev/ui`) |
| `public/`         | Files copied as-is to the `dist/` root (`theme-init.js`, loaded from `index.html` before the app)                                                                      |
| `src/lib/`        | Pure logic with unit tests: markdown pipeline, chat model, scroll, particles, theme                                                                                    |
| `src/state/`      | Zustand stores (UI state, current user `user-store.ts`)                                                                                                                |
| `src/styles/`     | `tokens.css` (shared design values, synced copy, never edited), `fonts.css`, `ds/` (the app's own sheets, one per area)                                                |

## Conventions

- The look follows the Console at Rest design system (design repository `console-at-rest`); styles use only the shared values. Keep the existing `localStorage` keys so existing browsers keep working. Settings keys are per user through `nsKey()` (the admin keeps the existing names, others get `<key>:<userId>`; newer keys: `my_ai_modes`, and `userPreferences` inside `my_ai_chat_defaults`); admin-only controls are hidden with `useIsAdmin()`. See `docs/frontend.md`.
- Server state goes through TanStack Query; UI state through Zustand.
- Markdown HTML is always sanitised by DOMPurify before it reaches the DOM.
- Every modal must close on Escape (use `Modal`, which handles the stack). Layers close newest first (`Modal`, `Window`, `Sheet`, `Popover`); the settings page closes on Escape once nothing is open on top of it.
