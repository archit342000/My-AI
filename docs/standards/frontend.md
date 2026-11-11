# Frontend standards

Applies to `frontend/`. Layout, state placement and run commands are in `docs/frontend.md`.

## Tooling (already configured)

- **TypeScript** `strict`, plus `noUncheckedIndexedAccess`, `noUnusedLocals`, `noUnusedParameters`, `verbatimModuleSyntax`.
  Handle `undefined` from indexing. Use `import type` for type-only imports.
- **ESLint** 9 with `typescript-eslint` and `react-hooks`. `npm run lint` must pass with no new warnings.
- **Prettier** (`.prettierrc.json`): single quotes, trailing commas, 100 columns. Run it on files you touch.
- Before finishing: `npm run typecheck`, `npm run lint`, `npm run test` from `frontend/`.

## TypeScript

- No `any`. Use `unknown` and narrow, or define a type. A `// eslint-disable` needs a one-line reason.
- Type all API responses in `src/api/`. Components never call `fetch` directly.
- No non-null assertions (`!`) to silence the compiler; fix the type or check the value.
- Prefer `type` for data shapes and unions, `interface` only for extendable object contracts.

## React

- Function components and hooks only. One component per file; the file is named after the component (`PascalCase.tsx`).
- Hooks are `useCamelCase` in their own files; pure logic goes to `src/lib/` with unit tests, not into components.
- Components stay presentational where possible; side effects live in hooks or `src/api/`.
- Effects: list every dependency (the lint rule is not optional), clean up subscriptions, timers and streams.
- Do not store derived data in state; compute it. Use stable `key`s (ids, never array index for reorderable lists).
- Files exporting components export only components (`react-refresh` rule).

## State

- **Server data:** TanStack Query only. Keys are defined in `api/`. Invalidate, do not refetch by hand.
- **UI state:** Zustand stores in `src/state/`, one concern per store, selectors in components (no whole-store subscriptions).
- **Persisted browser state:** keep existing `localStorage` key names and formats (see `docs/frontend.md`). User settings go through `nsKey()` (`lib/user-storage.ts`): the admin keeps the existing names and any other user's keys get a `:<userId>` suffix, so no key is renamed.

## Styling and accessibility

- Colours, lettering, spacing, corners, shadows, layers and speeds come from the shared values in `src/styles/tokens.css` (a synced copy of the
  `console-at-rest` design repository; never edit it; add a missing value to that repository first, then re-sync). No hardcoded hex values or magic pixel sizes in components.
  `bridge.css` keeps legacy variable names working until each screen is converted; new code does not use those names.
- Reuse the shared UI primitives (`Modal`, `Toast`, `Menu`, `Popover`, `ConfirmDialog`) instead of building new ones.
- Interactive elements are real `<button>`/`<a>` elements with an accessible name. Icon-only buttons need `aria-label`.
- Everything must be keyboard operable; keep focus visible.

## Security

- Render model or user HTML only through `renderMarkdown` (DOMPurify). `dangerouslySetInnerHTML` is allowed only in the existing
  markdown and icon components; any new use needs a reviewer note.
- Never put secrets in frontend code, `VITE_*` variables or `localStorage`.

## Tests

- Every file in `src/lib/` and `src/state/` has a Vitest test next to it (`name.test.ts`). Components with logic get Testing Library tests
  that query by role/label, not by class or test id when avoidable.
- New user flows get a Playwright spec in `e2e/`. Streaming changes update the fixtures in `src/test/fixtures/stream/`.
- Generated files (`*.generated.ts`) are never edited by hand.
