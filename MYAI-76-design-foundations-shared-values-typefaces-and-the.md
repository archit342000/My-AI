---
id: MYAI-76
title: "Design foundations: shared values, typefaces and themes"
status: done
epic: MYAI-75
created: 2026-11-10
updated: 2026-11-11
links:
  blocks: [MYAI-77, MYAI-78, MYAI-93]
---

## Description
Bring the Console at Rest values into the React frontend and make them the only source of colour, lettering, spacing, corners, shadows, layers and movement. Covers: consuming `tokens.css` from the design-system repository (how it is brought in is a planning decision), loading Sora, Instrument Sans and JetBrains Mono, Light / Dark / System themes with the near-black night, the solid-panel fallback for devices that cannot blur, and reduced motion. Rule book Parts 2 and 4.

Design system: repository `console-at-rest` (github.com/archit342000/console-at-rest, local `~/Coding/repos/console-at-rest`): `RULEBOOK.md`, `tokens.css`, `tokens.json`, `reference/console-at-rest.html`.

## Acceptance criteria
- [x] The frontend takes every colour, size, corner, shadow, layer and speed from the shared values; no component introduces a raw value
- [x] The three typefaces load and are applied by job (headings, text, typewriter labels and code)
- [x] Light, Dark and System work; Dark is the neutral near-black; the choice persists and applies before first paint
- [x] Solid-panel mode and reduced motion both work app-wide
- [x] The legacy colour and font variables still needed by unconverted screens keep working until those screens are converted
- [x] Checked in a browser on computer and phone, day and night

## Plan
**Date:** 2026-11-11  **Status:** Validated

### Objective
Make the Console at Rest shared values the single source of colour, lettering, spacing, corners, shadows, layers and movement in `frontend/`, load the three typefaces, and wire Light / Dark / System, solid-panel mode and reduced motion app-wide, without breaking screens that still use the legacy variables.

### Context
- Requirement: ticket Description and Acceptance criteria. Design source: `~/Coding/repos/console-at-rest/tokens.css` (rule book v1.2, commit `fa07a6c`), `RULEBOOK.md` Parts 2 and 4.
- Rules: `docs/standards/frontend.md` (CSS custom properties only, tests next to `src/lib/` and `src/state/` files, Prettier, no `any`), `docs/standards/dependencies.md` (caret ranges, lockfile committed, no vendored library code), `docs/frontend.md` "Theme" and "Browser state" (theme key is global; only `html` carries the page colour), `docs/standards/docs.md`, `docs/standards/gitflow.md`.
- Current behaviour:
  - `frontend/src/main.tsx` imports `styles/legacy.css` then `styles/components.css`.
  - `styles/legacy.css` line 1 imports Outfit, JetBrains Mono and Lora from Google Fonts and defines the legacy variables in `:root` and `.dark` (`--accent`, `--bg-base`, `--content-primary`, `--font-heading`, `--font-body`, `--font-mono`, `--font-serif`, `--glass-*`, ...). `styles/components.css` defines more (`--surface-elevated`, `--scrim`, `--focus-ring`, `--danger*`, `--space-1..6`, `--radius-sm`) and sets the `html` background.
  - Theme: `public/theme-init.js` and `lib/theme.ts` (`resolveDark`, `applyDarkClass`) toggle the `dark` class on `<html>`; `hooks/useThemeSync.ts` keeps it in step; `state/ui-store.ts` holds `themeMode` under `my_ai_theme_mode`. `lib/theme.test.ts` keeps the script and `resolveDark` in step. `e2e/theme-background.spec.ts` checks the class before first render.
  - `tokens.css` switches night by `data-theme` on `<html>` (or the OS setting when it is absent), solid panels by `data-glass="solid"`, and removes all animation and transition under `prefers-reduced-motion`.
  - Names defined by both `tokens.css` and the legacy sheets: `--accent`, `--ease-spring`, `--ease-liquid`, `--glass-blur`, `--scrim`, `--space-1..6` (`--space-5` and `--space-6` differ: 20/24 legacy, 24/36 shared; used 9 times in `components.css`, never in `.tsx`). Keyframes named by both: `checkPop`, `fadeScale`, `popOverIn`, `shimmer`.
  - No `.tsx` file contains a hex colour today.

### Approach
- **Bring the values in as a synced copy.** `frontend/src/styles/tokens.css` is a byte-for-byte copy of the design repository's file under a one-line stamp (version and commit). `frontend/scripts/sync-design-tokens.cjs <path>` refreshes it. Assumption (logged): this is first-party design data, not library code, so the "do not vendor" rule does not apply. Rejected: an npm git dependency or submodule on a private repository (breaks `npm ci` in a clean or Docker build without credentials).
- **Load order: legacy, components, tokens, bridge.** Shared values load after the legacy sheets so they win every shared name. A new `styles/bridge.css` re-points the legacy variables still used by unconverted screens to the shared values (`--bg-base`, `--bg-primary`, `--bg-dark` to `--bg`; `--content-primary` to `--fg`; `--content-muted` to `--muted`; `--font-heading`/`--font-body`/`--font-mono`/`--font-serif` to `--display`/`--font`/`--mono`/`--font`; the `--accent-*` family, `--focus-ring`, `--danger*`, `--surface-elevated`, glass and border variables). Each is declared once on `:root`, after the legacy sheets, so it wins in both themes. Bridge contains only `var()`, `color-mix()` and numbers already in `tokens.css`; no new hex values. It is deleted by the last ticket of the epic.
- **Spacing clash:** in `components.css` rename the 9 uses of `--space-5` and `--space-6` to legacy aliases `--legacy-space-5` (20px) and `--legacy-space-6` (24px) defined in that file, and delete its own `--space-1..6` definitions, so the shared spacing names carry the shared values and no legacy layout moves.
- **Themes:** keep the `dark` class (legacy selectors need it) and additionally set `data-theme="light|dark"` to the resolved theme in both `theme-init.js` and `lib/theme.ts`. Always explicit, so System works without relying on the media query branch of `tokens.css`.
- **Solid panels:** new device preference `glassMode: 'auto' | 'frosted' | 'solid'` in `ui-store` under a new global key `my_ai_glass_mode`. `auto` (default) resolves to solid when the browser supports neither `backdrop-filter` nor `-webkit-backdrop-filter`. The resolved value is set as `data-glass` before first paint and kept in step by `useThemeSync`. In `bridge.css`, `:root[data-glass="solid"]` also removes `backdrop-filter` everywhere and makes the bridged legacy glass surfaces solid, so unconverted screens obey it. The Settings control for it belongs to the settings ticket; here it is reachable from the dev page.
- **Typefaces:** self-host with `@fontsource-variable/sora`, `@fontsource-variable/instrument-sans` and `@fontsource-variable/jetbrains-mono` (5.x; no request to a third party, works offline). Remove the Google Fonts import. `tokens.css` names the families "Sora", "Instrument Sans", "JetBrains Mono"; the variable packages register "... Variable" names, so `styles/fonts.css` adds `@font-face` aliases with `local()`-free `src` pointing at the same files under the plain names. Rejected: keeping Google Fonts (external request from a self-hosted app).
- **Reduced motion:** the rule in `tokens.css` covers every CSS animation and transition. The particle canvas does not check the setting today (`lib/particles.ts`, `components/background/AmbientBackground.tsx`): `startParticles` gets a `reduceMotion: () => boolean` option; when it returns true the canvas draws one frame and does not loop or react to the pointer, and it redraws on theme or setting change. The full sphere rework stays in the next ticket.
- **Guard:** a unit test fails if `tokens.css` loses its stamp, if `bridge.css` or `fonts.css` contains a hex colour, or if any non-test, non-generated `.tsx` under `src/` contains one.

### Out of scope
- Restyling any component or screen (later tickets). Unconverted screens change only through the bridged variables (new blue, paper, near-black night, typefaces).
- The dot sphere and stars (next ticket). A user-facing Settings control for solid panels or motion.
- Removing `legacy.css` or `bridge.css`.

### Steps
#### Step 1: Synced shared values
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/styles/tokens.css` (create), `frontend/scripts/sync-design-tokens.cjs` (create)
- **Change:** script copies the given `tokens.css` and prepends the stamp line (version read from the design repository's `RULEBOOK.md` with the pattern `^Version (\d+\.\d+)`, commit from `git rev-parse --short HEAD`, both passed or detected); run it against `~/Coding/repos/console-at-rest`.
- **Verification:** file body equals the source; stamp names v1.2 and `fa07a6c`.

#### Step 2: Typefaces
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/package.json` and `package-lock.json` (modify), `frontend/src/styles/fonts.css` (create), `frontend/src/styles/legacy.css` (modify: delete line 1 import only), `frontend/src/main.tsx` (modify: import `fonts.css` first)
- **Change:** add the three packages; `fonts.css` imports them and declares the plain-name aliases with `font-display: swap`.
- **Verification:** `npm run build` emits the woff2 files; no request to `fonts.googleapis.com` or `fonts.gstatic.com` in the browser.

#### Step 3: Bridge and load order
- **Status:** todo
- **Depends on:** 1, 2
- **Files:** `frontend/src/styles/bridge.css` (create), `frontend/src/styles/components.css` (modify: spacing rename, remove `--space-1..6`), `frontend/src/main.tsx` (modify imports: after `fonts.css`, the order is legacy, components, tokens, bridge)
- **Change:** as in Approach, including the solid-panel rules and `body`/`html` using `--font` and `--bg`.
- **Verification:** computed `--accent`, `--bg`, `--fg` on `<html>` equal the shared values in both themes; computed `--bg-base` equals `--bg`; a `components.css` rule that used `--space-5` still computes 20px.

#### Step 4: Theme and glass logic
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/lib/theme.ts` (modify: `applyDarkClass` also sets `data-theme`; new `resolveGlass`, `applyGlass`), `frontend/src/lib/theme.test.ts` (modify), `frontend/public/theme-init.js` (modify: `data-theme`, `data-glass`), `frontend/src/state/ui-store.ts` and `ui-store.test.ts` (modify: `GlassMode`, `glassMode`, `setGlassMode`, key `my_ai_glass_mode`), `frontend/src/hooks/useThemeSync.ts` (modify: accept and apply glass mode), its only caller `frontend/src/app/RootLayout.tsx` (modify), `frontend/src/lib/particles.ts` and `particles.test.ts` (modify: `reduceMotion` option), `frontend/src/components/background/AmbientBackground.tsx` (modify: pass it from `matchMedia('(prefers-reduced-motion: reduce)')` and re-run on change)
- **Change:** as in Approach. `theme-init.js` stays tolerant of blocked storage and missing APIs.
- **Verification:** unit tests cover every mode and OS combination for both attributes, the unsupported-blur fallback, script/app parity, and that `startParticles` schedules no further frame when `reduceMotion()` is true.

#### Step 5: Dev page section
- **Status:** todo
- **Depends on:** 3, 4
- **Files:** `frontend/src/features/dev/FoundationsDemo.tsx` (create), `frontend/src/features/dev/PrimitivesDemo.tsx` (modify: render it), `frontend/src/styles/components.css` (modify: `foundations-` block)
- **Change:** colour swatches, the type scale by job, spacing, corner and shadow samples, and Light / Dark / System and Auto / Frosted / Solid switches wired to `ui-store`. Uses only shared values, through classes in a new block of `styles/components.css` (no inline `style={`, so `src/test/inline-style.test.ts` stays green).
- **Verification:** `/dev/ui` shows the section in both themes and both glass modes.

#### Step 6: Guard test
- **Status:** todo
- **Depends on:** 1, 2, 3
- **Files:** `frontend/src/lib/design-tokens.test.ts` (create)
- **Change:** the three checks under "Guard".
- **Verification:** `npm run test` passes; adding a hex colour to a `.tsx` makes it fail (checked once by hand, then reverted).

#### Step 7: Tests and docs
- **Status:** todo
- **Depends on:** 3, 4
- **Files:** `frontend/e2e/theme-background.spec.ts` (modify: also assert `data-theme` before first render), `docs/frontend.md` (modify: Layout rows, Theme paragraph, the new global key), `frontend/README.md` (modify: Layout, Commands row for the sync script), `docs/standards/frontend.md` (modify: styling rule names `tokens.css` as the only source and `bridge.css` as temporary)
- **Change:** as listed. `docs/frontend.md` is 190 lines against a 200-line limit (`tests/test_docs.py`, `DOCS_MAX_LINES`): remove the duplicated "Server state" bullet (the first of the two), fold the new facts into the existing Theme and Browser state bullets, and add at most two Layout rows, so the file ends at 200 lines or fewer.
- **Verification:** `wc -l docs/frontend.md` is at most 200; `scripts/check.sh` passes (docs guardrails included).

### Tests
- Vitest: `lib/theme.test.ts`, `lib/particles.test.ts`, `state/ui-store.test.ts`, `lib/design-tokens.test.ts`. Run `npm run typecheck`, `npm run lint`, `npm run test`, `npm run build` from `frontend/`.
- Playwright: `npm run e2e` (desktop and phone projects); `theme-background.spec.ts` updated.
- Gate: `scripts/check.sh`.
- The browser check on computer and phone, day and night, including solid panels and reduced motion, is done live in the verify stage on `/`, a chat, `/dev/ui` and Settings.

### Risks and open questions
- Shared keyframes `checkPop`, `fadeScale`, `popOverIn`, `shimmer` replace the legacy ones of the same name: check popovers, toasts and skeletons still animate sensibly.
- The reduced-motion rule is global and `!important`: confirm no legacy behaviour depends on a `transitionend` or `animationend` event.
- Unconverted screens will look different (new blue, paper, night, typefaces). Expected; any e2e assertion on old colours is updated to the bridged value.
- Assumption: a synced copy is acceptable under the "do not vendor" rule (see Approach).

### Success criteria
- [ ] `<html>` computes the shared values for colour, lettering, spacing, corners, shadows, layers and movement; legacy variables resolve to them
- [ ] Sora, Instrument Sans and JetBrains Mono load from the app itself and are applied to headings, text and labels/code
- [ ] Light, Dark and System set `data-theme` and the `dark` class before first paint and persist; Dark is `#070708`
- [ ] `data-glass="solid"` removes blur and makes panels solid on every screen; it is automatic where blur is unsupported
- [ ] With reduced motion requested, nothing animates
- [ ] No hex colour in any `.tsx`, `bridge.css` or `fonts.css`; the guard test enforces it. Other raw values (sizes, corners, shadows, layers, speeds) are held by the styling rule in `docs/standards/frontend.md` and by review as each screen is converted
- [ ] With reduced motion requested the particle canvas draws once and stands still
- [ ] `scripts/check.sh` and `npm run e2e` pass

### Reviewer brief
- Objective: make the Console at Rest shared values the only source of colour, lettering, spacing, corners, shadows, layers and movement in `frontend/`; load the three typefaces; wire Light / Dark / System, solid panels and reduced motion app-wide; keep unconverted screens working.
- Decisions: `styles/tokens.css` is a synced copy of the design repository's file (stamp line, sync script); load order is fonts, legacy, components, tokens, bridge; `styles/bridge.css` re-points legacy variables to the shared ones and is temporary; `--space-5`/`--space-6` uses in `components.css` become `--legacy-space-*`; themes set both the `dark` class and `data-theme`; `glassMode` (auto, frosted, solid) is a global device preference under `my_ai_glass_mode`, automatic where blur is unsupported; typefaces are self-hosted through `@fontsource-variable/*`; the particle canvas draws one still frame under reduced motion; a guard test bans hex colours in `.tsx`, `bridge.css` and `fonts.css`.
- Out of scope: restyling any component or screen; the sphere rework; a Settings control for solid panels or motion; removing `legacy.css` or `bridge.css`.
- Success: shared values computed on `<html>` in both themes and bridged legacy names follow them; the three typefaces load from the app; `data-theme` and `dark` set before first paint and persist; solid mode removes blur everywhere; nothing animates under reduced motion; `scripts/check.sh` and `npm run e2e` pass.

The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- Round 1: validator FAIL, judged FAIL. Valid BLOCKING: (1) canvas does not honour reduced motion and no step added it: added the `reduceMotion` option to Step 4; (2) Step 2 could not verify because nothing imported `fonts.css`: Step 2 now imports it in `main.tsx`; (3) `docs/frontend.md` 190 of 200 lines: Step 7 now removes the duplicate bullet and caps additions. Valid MINOR, fixed: unnamed caller (`RootLayout.tsx`), inline-style ratchet (classes, no inline styles), version parse rule, live-browser check placed in the verify stage, guard scope stated honestly in Success criteria.
- Round 2 (diff-scoped): validator PASS, judged PASS (spot-checked `particles.ts`, `RootLayout.tsx`, line counts). Two MINOR fixed mechanically: Step 6 depends on 2; `particles.test.ts` added to Tests.

## Implementation notes
### Autopilot run (2026-11-11)
- Mode: automatic (batch)
- Branch: feature/design-foundations  PR base: develop  Starting commit: 7f3c1ce
- Dirty before start: none
- Work files: see Implementation progress
- Counters: fix 0/10, review 2/5, re-verify 1
- Last completed stage: 6 ship  Next: none
- Hard blocker: none
- WIP commit: none

### Autopilot decisions (2026-11-11)
- plan: how are the shared values brought in? A synced copy with a stamp and a sync script (assumption: first-party design data, not vendored library code). Reason: a git dependency on a private repository breaks clean and Docker builds.
- plan: typefaces from Google Fonts or self-hosted? Self-hosted `@fontsource-variable/*`. Reason: no third-party request from a self-hosted app; works offline.
- plan: where is the solid-panel switch? Store and automatic fallback here, dev page control only; the Settings control belongs to MYAI-85.
- plan: `--font-serif` (Lora) is dropped and mapped to the text typeface. Reason: the design has three typefaces.
- batch: user asked (2026-11-11) for backend gaps to become tickets and for deploys to myai.architanand.dev as tickets complete; deploying from a feature branch contradicts `docs/release.md` ("deploy only from tagged releases"), done on the user's explicit instruction.

### Baseline (2026-11-11)
- `npm run typecheck`, `npm run lint`: pass. `npm run test`: 110 files, 869 tests, all pass.

### Implementation progress
- Branch: feature/design-foundations
- [x] Step 1: Synced shared values - `frontend/src/styles/tokens.css`, `frontend/scripts/sync-design-tokens.cjs` (v1.2 @ fa07a6c, body identical to source)
- [x] Step 2: Typefaces - `frontend/package.json`, `package-lock.json`, `src/styles/fonts.css`, `src/styles/legacy.css`, `src/main.tsx`. Deviation: `fonts.css` declares its own `@font-face` rules under the plain family names pointing at the packages' woff2 files (latin and latin-ext), instead of importing the packages' CSS and aliasing; same files, one registration.
- [x] Step 3: Bridge and load order - `src/styles/bridge.css`, `src/styles/components.css`, `src/main.tsx`. Note: `--space-5`/`--space-6` had 10 uses (2 and 8), not 9.
- [x] Step 4: Theme and glass logic - `src/lib/theme.ts`, `theme.test.ts`, `public/theme-init.js`, `src/state/ui-store.ts`, `ui-store.test.ts`, `src/hooks/useThemeSync.ts`, `src/app/RootLayout.tsx`, `src/lib/particles.ts`, `particles.test.ts`, `src/components/background/AmbientBackground.tsx`
- [x] Step 5: Dev page section - `src/features/dev/FoundationsDemo.tsx`, `PrimitivesDemo.tsx`, `src/styles/components.css` (class names written out in full for `src/test/css-coverage.test.ts`)
- [x] Step 6: Guard test - `src/lib/design-tokens.test.ts` (checked by hand that a hex colour in a `.tsx` fails it; reverted)
- [x] Step 7: Tests and docs - `e2e/theme-background.spec.ts`, `docs/frontend.md` (192 lines), `frontend/README.md`, `docs/standards/frontend.md`
- Prettier was run on touched files; it also reformatted existing lines in `PrimitivesDemo.tsx`, `particles.ts` and `ui-store.ts`.

### Smoke test (2026-11-11)
- `npm run typecheck`, `npm run lint`: pass. `npm run test`: 111 files, 884 tests, all pass. `npm run build`: pass, woff2 files emitted, no `googleapis` in the built CSS. `pytest tests` (docs guardrails): 68 pass.
- `npm run e2e` against this worktree (dev server :5183, throwaway backend :5195 from `e2e/stack/start-stack.mjs`): 61 pass, 1 fail (`chat-start.spec.ts` "the first send ... lists the chat at once"); rerun alone three times: passes every time. Treated as order-dependent, not caused by this change; rechecked in verify.
- Environment note: the default e2e target (:5173 and :5000) is the main checkout's dev server and a Cloudflare-protected backend; e2e for this batch always runs against :5183 and :5195.

PR: https://github.com/archit342000/My-AI/pull/121, branch feature/design-foundations, base develop

## Verification
### Verification plan (2026-11-11)
**Diff base:** 7f3c1ce. Evidence: `~/.claude/tickets/My-AI/MYAI-76-evidence/`.

#### Scope
Shared values, bridge, typefaces, `data-theme`, `data-glass`, reduced motion on the canvas, dev page section, docs. Out of scope: restyled components, the sphere rework, a Settings control for panels.

#### Environment and isolation
- Backend: `frontend/e2e/stack/start-stack.mjs` on 127.0.0.1:5195 (static sign-in, temporary `DATA_DIR` under the system temp dir, scripted model on :5196). Dev server for this worktree on :5183 with `BACKEND_URL` set to it. Built app served by the same backend at :5195.
- Never touched: the live `my-ai-*` containers, the real data directory, port 5173/5000 (main checkout), the user's browser profile (the harness uses its own temporary profile).
- Harness: `scripts/verify.cjs` (Playwright driving system Chrome against the two URLs; prints computed values, writes screenshots).

#### Scenarios
| ID | Criterion | Scenario | Type | Method | Files | Expected | Evidence |
|----|-----------|----------|------|--------|-------|----------|----------|
| V1 | shared values in force | Light: computed `--accent`, `--bg`, `--fg`, `--space-5`, `--r-ctl`, `--shadow`, `--z-popup`, `--t-base` on `<html>`; `html` background | happy | browser | tokens.css, main.tsx | values equal `tokens.css` day block; background rgb(244, 242, 238) | results.json |
| V2 | Dark is near-black | Dark saved: `data-theme=dark`, `dark` class, background rgb(7, 7, 8), `--accent` #1A73D1 | happy | browser | theme.ts, theme-init.js | as stated | results.json |
| V3 | System works | No saved theme, OS dark then OS light | happy | browser | theme-init.js, useThemeSync.ts | theme follows the OS | results.json |
| V4 | choice persists, applies at runtime | Switch theme on `/dev/ui`, reload | happy | browser | ui-store.ts, FoundationsDemo.tsx | attribute changes at once and survives reload | results.json |
| V5 | legacy variables keep working | `--bg-base`, `--content-primary`, `--font-body`, `--surface-elevated`, `--focus-ring` resolve to shared values in both themes; `.ui-demo` gap (uses `--legacy-space-6`) is 24px | regression | browser | bridge.css, components.css | equal to the shared values; 24px | results.json |
| V6 | three typefaces by job | `document.fonts` has Sora, Instrument Sans, JetBrains Mono loaded; `body` uses Instrument Sans; the foundations page-title sample uses Sora, the label sample JetBrains Mono; no request to a font host | happy | browser, network | fonts.css, bridge.css | as stated; font files 200 from the app origin | results.json |
| V7 | solid panels app-wide | Pick Solid on `/dev/ui`; count elements with a computed `backdrop-filter` on `/`, `/dev/ui`, with a dialog open; reload | happy | browser | bridge.css, theme.ts, ui-store.ts | `data-glass=solid`, zero blurred elements, persists; Frosted brings blur back | results.json |
| V8 | solid is automatic without blur | `CSS.supports` reports no backdrop-filter, nothing saved | edge | browser | theme-init.js, theme.ts | `data-glass=solid` before and after mount | results.json |
| V9 | reduced motion | OS asks for less motion: canvas has pixels, two captures 1.2 s apart are identical, `document.getAnimations()` is empty after a hover and opening a menu | happy | browser | particles.ts, AmbientBackground.tsx, tokens.css | identical frames, no animations | results.json |
| V10 | (control for V9) | Normal motion: two canvas captures differ | regression | browser | particles.ts | frames differ | results.json |
| V11 | bad saved values | `my_ai_theme_mode=purple`, `my_ai_glass_mode=x` | failure | browser | theme-init.js, ui-store.ts | follows system and auto; no console error | results.json |
| V12 | built app (production path) | Built `dist/` served by the backend: `data-theme` set, fonts load from the app, no font-host request | happy | browser | main.tsx, fonts.css, theme-init.js | as stated | results.json |
| V13 | checked on computer and phone, day and night | Screenshots of `/`, `/dev/ui`, a dialog at 1440 and 390 wide, both themes, and solid; viewed; console errors collected | non-functional | browser | all styles | new blue, paper, near-black, typefaces visible; nothing broken or unreadable; no console errors | shots/ |
| V14 | no regressions | `scripts/check.sh --frontend-only`; docs guardrails; full `npm run e2e` against :5183 | regression | CLI | all | pass | logs |

### Results (2026-11-11)
- Commit verified: 7f3c1ce plus uncommitted work files (content hashes):
  - `docs/frontend.md` f45a24d7b4
  - `docs/standards/frontend.md` b1ca2e5ce6
  - `frontend/README.md` bb45df35fc
  - `frontend/e2e/theme-background.spec.ts` 5254f711f4
  - `frontend/package-lock.json` 431df9531e
  - `frontend/package.json` dcc2bfa369
  - `frontend/public/theme-init.js` 800fdbae68
  - `frontend/src/app/RootLayout.tsx` 049b95054f
  - `frontend/src/components/background/AmbientBackground.tsx` 3074c6ad81
  - `frontend/src/features/dev/PrimitivesDemo.tsx` fa59552923
  - `frontend/src/hooks/useThemeSync.ts` 1a6714c3b4
  - `frontend/src/lib/particles.test.ts` f3a1807bcd
  - `frontend/src/lib/particles.ts` f75edd520d
  - `frontend/src/lib/theme.test.ts` 08d3fecff3
  - `frontend/src/lib/theme.ts` d8fd56afb9
  - `frontend/src/main.tsx` e2be338012
  - `frontend/src/state/ui-store.test.ts` 5212398448
  - `frontend/src/state/ui-store.ts` a58a0c4199
  - `frontend/src/styles/components.css` c03ada5691
  - `frontend/src/styles/legacy.css` 5bb670b648
  - `frontend/scripts/sync-design-tokens.cjs` 151ed33987
  - `frontend/src/features/dev/FoundationsDemo.tsx` 3173199f30
  - `frontend/src/lib/design-tokens.test.ts` c5aae3e404
  - `frontend/src/styles/bridge.css` a8ca988f33
  - `frontend/src/styles/fonts.css` fce626d433
  - `frontend/src/styles/tokens.css` f2cf58a9d8
- Verdict: **verified**. 14 PASS, 0 FAIL, 0 BLOCKED.

| ID | Status | Observed | Evidence |
|----|--------|----------|----------|
| V1 | PASS | `--accent` #0B6BCB, `--bg` #F4F2EE, `--fg` #171A21, `--space-5` 24px, `--r-ctl` 12px 12px 12px 3px, `--z-popup` 30, `--t-base` 0.2s; html background rgb(244, 242, 238) | results.json |
| V2 | PASS | `data-theme=dark`, `dark` class, background rgb(7, 7, 8), `--accent` #1A73D1 | results.json |
| V3 | PASS | no saved theme: OS dark gives dark, OS light gives light | results.json |
| V4 | PASS | Dark chosen on `/dev/ui`: applied at once, kept after reload, stored `dark` | results.json |
| V5 | PASS | five bridged legacy names equal the shared values in light and in dark; `--font-body` is Instrument Sans; `.ui-demo` gap 24px | results.json |
| V6 | PASS | Sora, Instrument Sans, JetBrains Mono loaded; body Instrument Sans, page title Sora, label JetBrains Mono; only host contacted is the app; woff2 200 | results.json |
| V7 | PASS | Solid: `data-glass=solid`, 0 blurred elements on `/dev/ui`, with a dialog open and on `/` after navigation; stored `solid`; Frosted restores blur (3 elements) | results.json, shots/solid-* |
| V8 | PASS | no backdrop-filter support: `solid` at first render and after mount | results.json |
| V9 | PASS | reduced motion: canvas lit (35510 pixels), two captures 1.2 s apart identical after pointer moves; 0 running animations with a menu open and with a dialog open | results.json |
| V10 | PASS | normal motion: the two captures differ | results.json |
| V11 | PASS | unknown saved values: follows system and auto; no console error | results.json |
| V12 | PASS | built app from the backend: `data-theme` set, near-black, Sora available, fonts 200 from the app, no other host | results.json |
| V13 | PASS | 16 screenshots at 1440 and 390, light and dark, plus solid; viewed home (both themes, both widths), foundations, dialog, solid home: new blue, paper, near-black and the three typefaces show; nothing broken or unreadable; no console errors on any | shots/ |
| V14 | PASS | `scripts/check.sh --frontend-only`: ALL CHECKS PASSED; docs guardrails 68 pass; `npm run e2e` on a fresh throwaway backend: 62 passed | check-frontend.log, e2e-fresh.log |

Notes:
- The harness first re-seeded storage on every page load, which hid V4 and ran V5's dark half in light. Harness bug, fixed in `scripts/verify.cjs` (seed once per tab) and rerun; results above are from the rerun.
- Full e2e runs against a backend that already held chats from earlier runs failed 1 to 8 sidebar-listing specs (`chat-start`, `new-workspace`, `stack/send`, `stack/temp-chat`), differing per run (e2e.log, e2e-rerun.log). On a fresh backend all 62 pass. Cause: leftover data in the shared throwaway backend, not this change. The e2e suite is run on a fresh backend from now on.
- Pre-existing, not part of this change: the `desktop` project's own `testIgnore` replaces the top-level one in `playwright.config.ts`, so `e2e/stack/*.spec.ts` also run under `npm run e2e`.
- The solid-mode home screenshot caught the greeting mid entrance animation (semi-transparent text); timing of the capture, not a defect.
- Residual risk: unconverted screens were checked on home, the dev page and a dialog only; other screens get their own check as each is converted.
- Environment kept running for the rest of the batch (backend :5195 restarted fresh per run, dev server :5183); torn down when the batch ends.

### Results (re-run 1, 2026-11-11)
- Reason: review round 1 fixes changed runtime files. Commit 7f3c1ce plus uncommitted work files (content hashes):
  - `docs/frontend.md` 4f7d670cd8
  - `docs/standards/frontend.md` b1ca2e5ce6
  - `frontend/README.md` bb45df35fc
  - `frontend/e2e/theme-background.spec.ts` a2916ed3b0
  - `frontend/package-lock.json` 431df9531e
  - `frontend/package.json` dcc2bfa369
  - `frontend/public/theme-init.js` 800fdbae68
  - `frontend/src/app/RootLayout.tsx` 049b95054f
  - `frontend/src/components/background/AmbientBackground.tsx` 0df4f045e4
  - `frontend/src/features/dev/PrimitivesDemo.tsx` f21fa8b033
  - `frontend/src/hooks/useThemeSync.ts` 1a6714c3b4
  - `frontend/src/lib/particles.test.ts` fe7dc29e00
  - `frontend/src/lib/particles.ts` e9fbc4a251
  - `frontend/src/lib/theme.test.ts` 1e6ff21564
  - `frontend/src/lib/theme.ts` d8fd56afb9
  - `frontend/src/main.tsx` e2be338012
  - `frontend/src/state/ui-store.test.ts` 5212398448
  - `frontend/src/state/ui-store.ts` 0a32d02ec4
  - `frontend/src/styles/components.css` c9dc5f6171
  - `frontend/src/styles/legacy.css` 5bb670b648
  - `frontend/scripts/sync-design-tokens.cjs` 43d133c3b0
  - `frontend/src/features/dev/FoundationsDemo.tsx` c759ce38fd
  - `frontend/src/hooks/useThemeSync.test.ts` 579b573182
  - `frontend/src/lib/design-tokens.test.ts` 9f57b86dc2
  - `frontend/src/styles/bridge.css` 7617de89bc
  - `frontend/src/styles/fonts.css` fce626d433
  - `frontend/src/styles/tokens.css` f2cf58a9d8
- Verdict: **verified**. Re-ran every harness scenario (V1 to V13) and V14 on a fresh backend: 14 PASS, 0 FAIL, 0 BLOCKED.
- V4, V5, V7, V9, V10 (the scenarios touching changed files): same observations as the first run (solid: 0 blurred elements on all three views; reduced motion: identical frames, 0 animations; normal motion: frames differ; bridged names equal in both themes; theme choice persists).
- V14: `scripts/check.sh --frontend-only` ALL CHECKS PASSED (112 files, 894 tests); docs guardrails 68 pass; `npm run e2e` on a fresh backend 67 passed (5 new tests). Logs: check-frontend-rerun1.log, e2e-rerun1-fresh.log.

## Review history

### Round 1 - 2026-11-11
- Verdict: **Request changes**. Scope: base 7f3c1ce, 26 files, about 1,300 changed lines; four Haiku reviewers (correctness, standards and security, tests, requirements and docs); requirement available.
- R1-1 [MAJOR] `frontend/src/styles/bridge.css:84` - solid mode does not beat three legacy blur rules that are `!important` behind id selectors (`legacy.css:1353`, `:1745`, `:4396`), so "removes every backdrop-filter" is not true for them - Static (selectors confirmed; the first two ids are not rendered by the React app) - Fixed: `bridge.css` names `#model-switch-overlay` and `#thought-full-view-modal .modal-header` under the solid rule with `!important` (the third rule reads `--glass-blur`, which is `none` in solid)
- R1-2 [MAJOR] `frontend/e2e/theme-background.spec.ts:56` - comment says "no blur anywhere in solid mode" but nothing asserts it; reduced motion, typeface loading and System mode have no automated browser check - Static - Fixed: `e2e/theme-background.spec.ts` gains five tests (solid has zero blurred elements; no-blur browser goes solid; System follows the OS; three typefaces loaded with no font-host request; reduced motion keeps the canvas still and no animation runs); the misleading comment is corrected
- R1-3 [MINOR] `frontend/src/styles/bridge.css:33`, `:80` - `--accent-rgb` triplets are hand copies of `--accent`; nothing keeps them in step - Static - Fixed: unit test in `lib/design-tokens.test.ts` keeps `--accent-rgb` equal to `--accent` in both themes; bridge header explains the one mirrored value
- R1-4 [MINOR] `frontend/src/components/background/AmbientBackground.tsx:12` - under reduced motion every class change on `<html>` (not only `dark`) rebuilds the canvas - Static - Fixed: `AmbientBackground.tsx` redraws only when the `dark` class actually flips
- R1-5 [MINOR] `frontend/src/hooks/useThemeSync.ts` - no test, unlike the other hooks - Static - Fixed: `hooks/useThemeSync.test.ts` (system follows OS changes, explicit theme ignores it, listener cleanup, `data-glass`)
- R1-6 [MINOR] `frontend/src/lib/particles.test.ts:74` - reduced-motion test passes vacuously if no frame was queued; pointer and resize branches untested - Static - Fixed: `particles.test.ts` asserts the first frame exists and draws, and covers the pointer and resize branches under reduced motion
- R1-7 [MINOR] `frontend/src/lib/theme.test.ts:124` - the prefixed-only blur branch of `theme-init.js` is not exercised - Static - Fixed: `theme.test.ts` covers the prefixed-only branch of `theme-init.js`
- R1-8 [MINOR] `frontend/src/lib/design-tokens.test.ts` - the guard is never shown to catch a violation; no check that every legacy variable still resolves after the bridge and rename - Static - Fixed: the guard has a negative test; new test that every `var()` read by the stylesheets is defined, with the 13 already-undefined legacy names as a shrinking allow-list
- R1-9 [MINOR] `frontend/src/styles/components.css` foundations block - raw sizes (96px, 48px, 112px, 72px) and an unexplained +24px on the spacing bars - Static - Fixed: foundations sizes use shared spacing values; comment explains the bars' common base
- R1-10 [MINOR] `docs/frontend.md:34` - `scripts/` row does not mention the token sync; bridge header does not say corners, layers and easing are deliberately not bridged; `color-mix()` needs a stated minimum browser - Static - Fixed: `docs/frontend.md` scripts row and `color-mix()` minimum browsers; bridge header lists what is deliberately not bridged
- R1-11 [MINOR] `frontend/scripts/sync-design-tokens.cjs:21` - stamps HEAD without checking the source files are committed - Static - Fixed: `sync-design-tokens.cjs` refuses to stamp when `tokens.css` or `RULEBOOK.md` is uncommitted in the source
- R1-12 [MINOR] `PrimitivesDemo.tsx`, `ui-store.ts`, `particles.ts` - Prettier reflowed lines the change does not touch (`docs/standards/review.md` "no unrelated reformatting") - Static - Fixed: formatting-only hunks reverted in `PrimitivesDemo.tsx`, `ui-store.ts`, `particles.ts`
- R1-13 [NIT] `frontend/src/features/dev/FoundationsDemo.tsx:118` - `value as ThemeMode` / `as GlassMode` casts - Static - Fixed: casts replaced by a lookup in typed lists (`FoundationsDemo.tsx`)
- R1-14 `frontend/src/lib/particles.ts:7` hex palette `PARTICLE_COLORS` instead of `--dot-1..5` - Pre-existing (the sphere is reworked in the next ticket)
- R1-15 raw colours and sizes in `components.css` and `legacy.css` blocks not converted yet, dead legacy declarations now shadowed by the bridge, 19 `var()` names never defined - Pre-existing (converted screen by screen; removed with the old look)
- Triage: all 13 open findings valid; fixing 13, rejecting 0, asking about 0. R1-14 and R1-15 deferred as pre-existing (R1-14 to MYAI-77, R1-15 to the screen tickets and MYAI-91).
- Resolution: 13 fixed, 0 rejected, 2 deferred (pre-existing). Runtime files changed by fixes: `styles/bridge.css`, `styles/components.css`, `components/background/AmbientBackground.tsx`, `features/dev/FoundationsDemo.tsx`, `scripts/sync-design-tokens.cjs`. Checks: typecheck and lint pass; unit 112 files, 894 tests pass; `theme-background.spec.ts` 13 pass.
- Dismissed: "fonts may not resolve in the build" (three reviewers): disproved by verification V6 and V12 (woff2 emitted, 200 from the app, families loaded); kept only as the missing automated check in R1-2. "Guard should also ban rgb(), px and scan .css/.ts": the guard's hex-only scope is the plan's stated decision; other raw values are held by the styling rule and review. `padding: 72px` at `components.css:3169`: pre-existing line, only its variable name changed.
- Not covered: runtime behaviour beyond the findings (see Verification).

### Round 2 - 2026-11-11
- Verdict: **Request changes** (one MAJOR, tests only). Scope: base 7f3c1ce, 27 files, about 1,550 changed lines; four Haiku reviewers; requirement available.
- Triage: 13 valid (fixing 13), 8 rejected, 3 deferred, 0 needing a decision.
- R2-1 [MAJOR] `frontend/src/components/background/AmbientBackground.tsx:12` - the redraw on a theme flip under reduced motion has no test (three reviewers) - Static - Fixed: `AmbientBackground.test.tsx` (flip redraws once, unrelated class does not, normal motion untouched, cleanup on unmount)
- R2-2 [MINOR] `frontend/src/styles/bridge.css:9` - header does not say that `--accent`, `--glass-blur`, `--scrim` and the two easings now carry the shared values on unconverted screens, nor that `data-theme` switches on two old light-theme editor rules (`legacy.css:3601`, `:3603`) - Static - Fixed: header says so (the restyle through shared names is the plan's intent; reported as MAJOR, judged MINOR)
- R2-3 [MINOR] `frontend/src/lib/theme.ts:11` - stray doc line above `applyHighlightTheme`; "Always explicit" wording - Static - Fixed
- R2-4 [MINOR] `frontend/src/lib/particles.test.ts` - pointer test passed with or without the guard; `stop()` not in `afterEach` - Static - Fixed: compares the redraw with and without pointer activity under fixed time and randomness; cleanup in `afterEach` (not shown failing without the guard: source was not reverted to check)
- R2-5 [MINOR] `frontend/src/lib/design-tokens.test.ts` - test titles overstate (stamp format only; hex only); accent lookup could match a later block - Static - Fixed: titles reworded, lookups confined to their block
- R2-6 [MINOR] `frontend/src/lib/theme.test.ts` - standard-property-only branch of `supportsBackdropBlur` untested - Static - Fixed
- R2-7 [MINOR] `frontend/e2e/theme-background.spec.ts` - font test only watched two hosts - Static - Fixed: any font file from another origin fails it
- R2-8 [MINOR] `frontend/src/styles/components.css:3521` - comment wording on the spacing bars - Static - Fixed
- R2-9 [NIT] `docs/standards/frontend.md:37` ("there"), `ui-store.ts:41` (comment placement), `AmbientBackground.tsx:35` (unread dependency) - Static - Fixed
- R2-10 [MINOR] `components.css` foundations block - raw `letter-spacing` values; `tokens.css` names no tracking values (they appear only in its comments) - Static - Deferred: needs tracking names added to the design repository first; follow-up for the design system, then MYAI-78
- R2-11 [MINOR] `frontend/src/state/ui-store.ts:82` - `readGlass` (like the existing `readTheme`) does not survive a storage read that throws - Static - Pre-existing pattern, deferred
- R2-12 [MINOR] `AmbientBackground.tsx:27` with `particles.ts:221` - under reduced motion a theme flip regenerates the sphere's random dots - Static - Deferred to MYAI-77, which reworks the sphere
- Rejected: `padding: 72px` at `components.css:3169` and `--legacy-space-5/6` raw sizes (intended bridge for unconverted blocks; R1 dismissal stands); `1px` borders (hairline edges are the rule book's own value); `color-mix()` without fallback (floor documented in round 1); dev showcase is scope creep (plan step 5; dev-only route); allow-list keyed by name (a ratchet by name is enough); fixed wait in the still-canvas e2e test (a negative check; the moving case is covered by the unit tests and V10); solid and animation checks only on `/` (dialog and dev page covered in Verification); "theme-init blocked storage untested" (disproved: `theme.test.ts` "survives blocked storage and a missing media query"); "fonts may not resolve in the build" (disproved again: V6, V12 and the new e2e test); dead `Outfit`/`Lora` declarations in `legacy.css` (R1-15, removed with the old look).
- Resolution: 13 fixed, 8 rejected, 3 deferred. The MAJOR fix touched tests only; other fixes touched tests, comments and docs only, so the loop ends here and no re-verify is needed. Checks: typecheck, lint pass; unit 113 files pass; `theme-background.spec.ts` 13 pass; docs guardrails 68 pass.

## Log
- 2026-11-10: created
- 2026-11-10: added to epic MYAI-75
- 2026-11-10: linked blocks MYAI-77 (provides pieces it needs)
- 2026-11-10: linked blocks MYAI-78 (provides pieces it needs)
- 2026-11-11: autopilot started (batch)
- 2026-11-11: plan validated, 2 rounds
- 2026-11-11: implemented, smoke tests pass (one order-dependent e2e failure, passes alone)
- 2026-11-11: verified, 14 pass, 0 fail, 0 blocked; fix loop 0/10
- 2026-11-11: review round 1: request changes (2 major, 10 minor, 1 nit; 2 pre-existing)
- 2026-11-11: review round 1 resolved: 13 fixed, 2 deferred (pre-existing)
- 2026-11-11: re-verified after review fixes: 14 pass, e2e 67 pass
- 2026-11-11: review round 2 resolved (13 fixed, 8 rejected, 3 deferred); loop clean after 2 of 5
- 2026-11-11: shipped, PR #121 into develop (3 commits)
- 2026-11-11: batch-autopilot: shipped, base develop
- 2026-11-11: deployed for viewing: this branch's frontend build copied into the folder the live app serves (frontend only; previous build backed up in the worktree's plans/deploy-backups)
- 2026-11-11: linked blocks MYAI-93 (provides the shared values)
- 2026-11-11: merged into develop (PR 121, merge commit 2d6cce1)
- 2026-11-11: closed
