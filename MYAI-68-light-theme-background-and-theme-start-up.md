---
id: MYAI-68
title: "Light theme background and theme start-up"
status: done
epic: MYAI-53
created: 2026-11-10
updated: 2026-11-10
---

## Description
The particle background is invisible in the light theme because the page background is painted over it, and the theme class is applied only after React mounts.

Findings (MYAI-52, Verification): A-83, A-84. Evidence and the live test rig are in `~/.claude/tickets/My-AI/MYAI-52-evidence/`.

## Acceptance criteria
- [x] Particles are visible in light and dark on home and chat, and absent on logs
- [x] Routes without the canvas still have an opaque page background
- [x] No light flash when loading with the dark theme

## Plan
**Date:** 2026-11-10  **Status:** Validated

### Objective
Bring the particle background back in the light theme without losing the opaque page background on routes that have no canvas, and apply the theme before first paint so a dark-theme user does not see a light flash.

### Context
- **Requirement:** this ticket's Description and Acceptance criteria (findings A-83, A-84 in MYAI-52).
- **Rules:** `docs/standards/frontend.md` (CSS custom properties, persisted key names unchanged, pure logic in `src/lib/` with tests), `docs/standards/security.md` (no inline script that handles untrusted data; check it for script rules before adding one), `docs/frontend.md` (the theme key `my_ai_theme_mode` is a global device preference).
- **Current code (`frontend/`):**
  - `src/styles/components.css` "Page background": `html, body { background-color: var(--bg-primary); }`. `src/styles/legacy.css`: `#ambient-bg { position: fixed; inset: 0; z-index: -1; background: var(--bg-base) }`, `body { background: transparent }`, `.dark body { background: transparent }`. The `body` rule in `components.css` wins in light (it is later and equally specific) and paints over the negative-z-index canvas; in dark the more specific `.dark body` rule keeps `body` transparent, which is why particles show only in dark (measured in MYAI-52 `scripts/s8.mjs`: light `body` is `rgb(248, 247, 244)`, dark `body` is transparent). CSS paints a non-positioned block's own background after negative-z-index layers, and `body`'s background is its own here because `html` has one too. Confirmed live with `scripts/s9.mjs`: forcing `body` transparent in the light theme brings the particles back (`shots/f-particles-body-transparent.png`).
  - `src/app/RootLayout.tsx`: `<AmbientBackground />` is not rendered on `/logs`; `.logs-page` has its own opaque background.
  - `src/hooks/useThemeSync.ts` + `src/lib/theme.ts` (`resolveDark`, `applyDarkClass`): the `dark` class and the highlight theme are applied in an effect after React mounts. `index.html` has no script before the module entry. `src/state/ui-store.ts` reads `my_ai_theme_mode` (`light`, `dark`, `system`, default `system`).

### Approach
- **Background.** Only `html` gets the page colour; the `body` selector is removed from the rule so `body` stays transparent in both themes (as `legacy.css` sets it). The root background is painted beneath everything, including the fixed canvas at `z-index: -1`, so the particles are visible again and routes without the canvas still have an opaque page.
- **Theme before paint.** A tiny classic script `public/theme-init.js` (new, loaded from `<head>` before the module entry, same origin, no inline code) reads `my_ai_theme_mode` and the `prefers-color-scheme` media query and sets the `dark` class on `<html>`. It uses the same rule as `resolveDark`; a unit test loads the file and checks it against `resolveDark` for every mode and OS setting so the two cannot drift. `useThemeSync` keeps running after mount (it also installs the highlight theme and follows later changes).
- **Rejected:** an inline `<script>` in `index.html` (a separate file works under any script policy and can be tested); raising the canvas above the body background with z-index (it would cover page content).

### Out of scope
- Particle behaviour, counts or colours. Link and code colours (MYAI-60).
- The blurred page text visible through dialog surfaces (second half of finding A-84): it is the legacy glass design and is left as is.

### Steps
#### Step 1: Page background
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/styles/components.css` (modify: "Page background" block)
- **Change:** as in Approach ("Background"); the comment is updated to say why only `html` is painted.
- **Verification:** MYAI-52 rig (`~/.claude/tickets/My-AI/MYAI-52-evidence/scripts/up.sh`, `node s8.mjs`): `body` is transparent and `html` has the page colour in light and dark; a screenshot of `/` in light shows particles; `/logs` has no transparent area (page pixels at the sidebar's glass edge are not white) and no `#bg-stars` canvas in the document.

#### Step 2: Theme before first paint
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/public/theme-init.js` (create), `frontend/index.html` (modify: `<script src="/theme-init.js"></script>` in `<head>`), `frontend/eslint.config.js` (modify: browser globals for `public/*.js`), `frontend/src/lib/theme.test.ts` (modify: load the script file and compare with `resolveDark`), `app.py` (read only: confirm the built file is served from `frontend/dist/`; no change expected)
- **Change:** as in Approach ("Theme before paint").
- **Verification:** unit test: for stored `light`, `dark`, `system` and no stored value, with the OS preference on and off, the script sets or clears the `dark` class exactly as `resolveDark` says. Built app, on the MYAI-52 rig (static auth, so no token is needed): `curl` of `/theme-init.js` returns the script.

#### Step 3: Browser check, docs and full checks
- **Status:** todo
- **Depends on:** 1, 2
- **Files:** `frontend/e2e/theme-background.spec.ts` (create), `docs/frontend.md` (modify: one line on `theme-init.js` in the State section)
- **Change:** the spec opens `/` with `my_ai_theme_mode` set to `dark` and to `light`, then `/logs`.
- **Verification:** the spec asserts that `<html>` has the `dark` class before the app's root has any child (checked from an init script that records the class at `DOMContentLoaded`), that `getComputedStyle(document.body).backgroundColor` is transparent in both themes, that the canvas has drawn non-transparent pixels in light, and that `/logs` has no `#bg-stars` element. Then from `frontend/`: `npm run typecheck`, `npm run lint`, `npm run test`, `npm run build`, and `npm run e2e` (outside the merge gate; needs the dev server on :5173 and the backend on :5000); from the repo root `pytest tests` and `scripts/check.sh --frontend-only`.

### Tests
- Unit: `lib/theme.test.ts`.
- E2E: `e2e/theme-background.spec.ts`.
- Live: `s8.mjs` and a light-theme screenshot.

### Risks and open questions
- **Flask must serve `/theme-init.js`:** `app.py`'s catch-all serves existing files under `frontend/dist/`; Step 2 verifies it on the built app. If it does not, the file is referenced under `/assets/` through Vite instead (import with `?url`).
- **A `body`-level background elsewhere:** any other rule that paints `body` would hide the canvas again; Step 1's check covers light and dark.

### Success criteria
- [ ] Particles are visible in light and dark on home and chat, and absent on logs
- [ ] Routes without the canvas still have an opaque page background
- [ ] No light flash when loading with the dark theme
- [ ] Checks pass
### Reviewer brief
- **Objective:** particles visible again in the light theme with an opaque page on routes without the canvas, and the theme applied before first paint.
- **Decisions:** only `html` is painted with the page colour and `body` stays transparent (a `body` background paints above the `z-index: -1` canvas); a small same-origin classic script `public/theme-init.js` sets the `dark` class from `my_ai_theme_mode` and the OS preference before the app loads, tested against `resolveDark`; `useThemeSync` keeps running; no inline script.
- **Out of scope:** particle behaviour and colours, link and code colours (MYAI-60), the blurred page text behind dialogs (legacy glass design).
- **Success criteria:** particles in light and dark on home and chat and none on logs; opaque page background everywhere; no light flash with the dark theme; checks pass.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- **Round 1:** validator FAIL (1 blocking, 5 minor). Judged PASS. The blocking issue ("the `body` rule cannot hide a negative-z-index layer; the cause must be particle colours") is disproved: CSS paints in-flow block backgrounds after negative-z-index layers, the audit measured an opaque `body` in light and a transparent one in dark, and `scripts/s9.mjs` shows the particles returning in light as soon as `body` is forced transparent (screenshot saved in the MYAI-52 evidence). Minors fixed inline: where the `curl` check runs (static-auth rig); a check that `/logs` has no canvas; the dialog smudge moved to Out of scope; ESLint globals for the public script; what `npm run e2e` needs.

## Implementation notes
Branch bugfix/light-theme-background, base develop (autopilot batch item 17).
### Implementation progress
- [x] Step 1: components.css "Page background": only `html` painted, `body` stays transparent
- [x] Step 2: public/theme-init.js (classic same-origin script, no inline code), `<script src="/theme-init.js">` in index.html, theme.test.ts compares it with `resolveDark` for every mode and OS setting plus unknown/blocked storage
- [x] Step 3: e2e/theme-background.spec.ts, docs/frontend.md Theme line
Deviations: no ESLint change: `eslint.config.js` only lints `*.ts`/`*.tsx`, so the public script is not linted and needs no globals entry. The built `dist/theme-init.js` is served by Flask's existing catch-all (checked with curl).
### Smoke test (2026-11-10)
check.sh --frontend-only: typecheck, lint, tests, build pass; e2e theme-background 4/4.
Live: light and dark `/`: `html` opaque (248,247,244 / 9,9,11), `body` transparent, canvas present, particles visible in light (screenshot); `/logs`: no canvas, `html` opaque; `<html>` is dark before the first render with the dark theme saved.

PR: https://github.com/archit342000/My-AI/pull/117, branch bugfix/light-theme-background, base develop

## Verification

### Acceptance review (2026-11-10)
Criteria ticked on the live and e2e results recorded in the PR's Testing section (checks run on throwaway backends during the autopilot run; scripts in `MYAI-68-evidence/`).
All criteria covered.

## Review history
### Round 1 - 2026-11-10
Verdict: Approve with comments (4 MINOR). Single Haiku reviewer.
- R1-1 chat route untested - Fixed (canvas test on `/` and a chat route, both themes). R1-2 logs opaque check only in light - Fixed (both themes).
- R1-3 `public/` missing from the layout tables - Fixed (README and docs/frontend.md).
- R1-4 silent try/catch in theme-init.js diverges from readTheme - Rejected as a change, documented: the script runs before the app and must never stop the page from loading; the reason is in docs/frontend.md.
Resolution: check.sh passes; e2e theme-background 7/7. Round 1 fixes were not re-reviewed.


## Log
- 2026-11-10: created
- 2026-11-10: added to epic MYAI-53
- 2026-11-10: plan validated, 1 rounds
- 2026-11-10: acceptance criteria reviewed against the recorded results (3 ticked, 0 left open)
- 2026-11-10: closed by the user after the PR merged into develop
