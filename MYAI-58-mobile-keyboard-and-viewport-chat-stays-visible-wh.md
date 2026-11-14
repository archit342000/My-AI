---
id: MYAI-58
title: "Mobile keyboard and viewport: chat stays visible while typing"
status: done
epic: MYAI-53
created: 2026-11-10
updated: 2026-11-10
links:
  conflicts_with: [MYAI-56, MYAI-61]
---

## Description
With the on-screen keyboard open only the composer moves; the transcript stays behind the keyboard. The viewport meta lost `interactive-widget=resizes-content` and the zoom limits, the `is-ios` class and iOS scroll lock were not ported, and the transcript is not scrolled when the keyboard opens.

Findings (MYAI-52, Verification): A-22, A-23, A-24, A-25. Evidence and the live test rig are in `~/.claude/tickets/My-AI/MYAI-52-evidence/`.

## Acceptance criteria
- [x] Viewport meta matches legacy (`interactive-widget=resizes-content`, `maximum-scale=1.0`, `user-scalable=no`, `viewport-fit=cover`)
- [x] With a keyboard that overlays the page, the transcript's visible area ends above the composer and the last message is visible
- [ ] `is-ios` is set on iOS and the legacy iOS rules apply; page rubber-banding is blocked outside scroll areas
- [x] Opening the keyboard while pinned to the bottom keeps the last message in view
- [x] Unit tests cover the offset logic; a Playwright spec simulates the visual viewport

## Plan
**Date:** 2026-11-10  **Status:** Validated

### Objective
Keep the chat usable while typing on a phone: restore the legacy viewport behaviour so the layout resizes with the keyboard, keep the last message visible above the composer when the keyboard overlays the page, and bring back the iOS handling the legacy UI had.

### Context
- **Requirement:** this ticket's Description and Acceptance criteria (findings A-22 to A-25 in MYAI-52).
- **Rules:** `docs/standards/frontend.md` (pure logic in `src/lib/` with a test next to it, hooks in their own files, effects clean up listeners, new user flows get a Playwright spec), `docs/frontend.md`.
- **Legacy behaviour:**
  - `static/index.html:6-7`: `<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover, interactive-widget=resizes-content">`.
  - `static/js/scroll-manager.js` `initScrollManager`: adds `is-ios` to `<html>` on iOS/iPadOS, blocks `touchmove` outside a list of scroll areas on iOS, and sets `translateY(-offset)` on `#chat-input-area` where `offset = innerHeight - visualViewport.height` (ignored at 10px or less).
  - `frontend/src/styles/legacy.css` (block starting "iOS/iPadOS layout scroll", `.is-ios …` selectors): momentum scrolling on scroll areas, `backdrop-filter: none`, opaque glass fallbacks.
- **Current code (`frontend/`):**
  - `index.html:5`: viewport meta is `width=device-width, initial-scale=1.0, viewport-fit=cover`.
  - `src/hooks/useKeyboardOffset.ts` returns the offset from `computeKeyboardOffset` (`src/lib/scroll.ts`); `src/features/composer/Composer.tsx` applies it as `translateY` on `#chat-input-area` and publishes `--composer-h` on `<html>`.
  - `src/styles/components.css` `.messages-list { padding-bottom: calc(var(--composer-h, 180px) + var(--space-4)) }`: the keyboard offset is not part of it.
  - `src/features/chat/useAutoFollow.ts` scrolls to the end on child resize while pinned; it does not react to viewport changes.
  - `src/lib/scroll-lock.ts` has `isIOS()`; nothing adds the `is-ios` class and no `touchmove` lock exists.
  - Measured (MYAI-52 `scripts/s6.mjs`, Pixel 7, keyboard simulated as a 300px smaller visual viewport): composer moves to 449-539px, transcript box stays 72-839px, last message bottom at 711px (hidden).

### Approach
- **Viewport meta as legacy.** With `interactive-widget=resizes-content`, Chrome on Android resizes the layout when the keyboard opens, so the whole app (already sized with `dvh`/`svh` in `legacy.css`) moves up and the offset stays 0. The zoom limits come back with it.
- **Overlay keyboards (iOS Safari, or any browser that only shrinks the visual viewport):** the offset already moves the composer; it is also published as `--keyboard-offset` on `<html>` next to `--composer-h`, and the transcript's bottom padding adds it, so the scrollable content ends above the raised composer. `computeKeyboardOffset` also subtracts the visual viewport's `offsetTop` (a third parameter defaulting to 0), so a page the browser scrolled does not double-count.
- **Stay at the bottom.** `useAutoFollow` scrolls to the end when the window or the visual viewport resizes while the reader is pinned. It scrolls two animation frames after the event, so the padding from `--keyboard-offset` (set by a state update in `useKeyboardOffset`) is already applied when the scroll height is read.
- **iOS class and scroll lock.** A new hook `hooks/usePlatformClass.ts`, called once from `app/RootLayout.tsx`, adds `is-ios` to `<html>` on iOS and registers the non-passive `touchmove` guard: touches outside a scroll area are prevented. The allowed areas are a constant in `lib/scroll-lock.ts` (`#messages`, `.modal-body`, `.cm-scroller`, `.sidebar-content`, `.thought-body-inner`, `#chat-textarea`, `.workspace-view`, `.artifact-panel`, `.ui-popover`, `.logs-main`): the legacy entries that exist in React, plus the React scroll areas legacy had under other names or did not have (files panel, popover lists, logs). Legacy entries with no React element are left out.
- **Rejected:** resizing `#messages` with JavaScript on every viewport event (the meta tag does it natively where supported, and padding covers the rest); dropping the transform and relying on the meta alone (iOS Safari ignores `interactive-widget`).

### Out of scope
- Popover placement under the keyboard: MYAI-57.
- Mobile layout fixes (bubble width, drawer, dialogs) and the opaque mobile surfaces for non-iOS phones: MYAI-59.
- Testing on a physical device farm; the verify stage uses the simulated viewport and, if the user can provide it, one real phone check.

### Steps
#### Step 1: Viewport meta
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/index.html` (modify: viewport meta), `frontend/src/test/viewport-meta.test.ts` (create)
- **Change:** the meta content becomes the legacy string above.
- **Verification:** the new test reads `index.html` and asserts the content includes `interactive-widget=resizes-content`, `maximum-scale=1.0`, `user-scalable=no` and `viewport-fit=cover`.

#### Step 2: Offset logic and CSS variable
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/lib/scroll.ts` (modify: `computeKeyboardOffset` takes the viewport `offsetTop`), `frontend/src/lib/scroll.test.ts` (modify), `frontend/src/hooks/useKeyboardOffset.ts` (modify: pass `offsetTop`, set and remove `--keyboard-offset` on `<html>`), `frontend/src/hooks/useKeyboardOffset.test.ts` (create), `frontend/src/styles/components.css` (modify: `.messages-list` padding in the "Chat transcript" block)
- **Change:** as in Approach ("Overlay keyboards").
- **Verification:** unit tests: offsets of 10px or less are 0; `offsetTop` is subtracted; the hook sets `--keyboard-offset` when the visual viewport shrinks and removes it on unmount and when disabled.

#### Step 3: Keep the latest message in view
- **Status:** todo
- **Depends on:** 2
- **Files:** `frontend/src/features/chat/useAutoFollow.ts` (modify: window and `visualViewport` resize listeners), `frontend/src/features/chat/useAutoFollow.test.ts` (create)
- **Change:** as in Approach ("Stay at the bottom"); listeners are removed on unmount.
- **Verification:** unit tests with a fake element: a viewport resize while pinned calls `scrollTo` with the full scroll height; after the reader scrolled up it does not.

#### Step 4: iOS class and touch guard
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/lib/scroll-lock.ts` (modify: export the allowed-areas constant and a pure `isScrollAreaTarget(target)`), `frontend/src/lib/scroll-lock.test.ts` (create), `frontend/src/hooks/usePlatformClass.ts` (create), `frontend/src/hooks/usePlatformClass.test.ts` (create), `frontend/src/app/RootLayout.tsx` (modify: call the hook), `frontend/src/app/RootLayout.test.tsx` (modify)
- **Change:** as in Approach ("iOS class and scroll lock").
- **Verification:** unit tests: with an iPhone user agent the hook adds `is-ios` and a `touchmove` on the page background is prevented while one inside `#messages` is not; with a desktop user agent neither happens; the listener is removed on unmount.

#### Step 5: Phone spec, docs and full checks
- **Status:** todo
- **Depends on:** 1, 2, 3, 4
- **Files:** `frontend/e2e/mobile-keyboard.spec.ts` (create), `frontend/playwright.config.ts` (modify: add a phone project using `devices['Pixel 7']` with `testMatch` limited to the mobile specs, and `testIgnore` for them on the desktop project), `docs/frontend.md` (modify: a short "Mobile" note: viewport meta, keyboard offset variable, `is-ios`)
- **Change:** the spec opens a chat with a long reply (chat detail mocked as in `e2e/chat-send.spec.ts`), focuses the composer and shrinks `visualViewport.height` by 300px (property override plus a `resize` event, as `MYAI-52-evidence/scripts/s6.mjs` does).
- **Verification:** the spec asserts the composer's bottom edge is at the visible bottom and the last message's bottom edge is above the composer's top edge (this is how the criterion "the transcript's visible area ends above the composer" is read: its scrollable content ends there; the scroll container itself keeps its size in overlay mode). Then from `frontend/`: `npm run typecheck`, `npm run lint`, `npm run test`, `npm run build`, `npm run e2e`; from the repo root `pytest tests` and `scripts/check.sh --frontend-only`.

### Tests
- Unit: `lib/scroll.test.ts`, `lib/scroll-lock.test.ts`, `hooks/useKeyboardOffset.test.ts`, `hooks/usePlatformClass.test.ts`, `features/chat/useAutoFollow.test.ts`, `test/viewport-meta.test.ts`.
- Component: `app/RootLayout.test.tsx`.
- E2E: `e2e/mobile-keyboard.spec.ts` (phone project).

### Risks and open questions
- **Real keyboards cannot be driven from Playwright;** the spec proves the overlay path only. The resize path depends on the meta tag, which the unit test pins. A check on the user's own phone at verify time is the final proof.
- **`.is-ios * { backdrop-filter: none }` changes the look on iPhones** to the legacy fallbacks; this is the legacy behaviour and is intended.
- **`user-scalable=no`** disables pinch zoom, as legacy did; recorded as a deliberate parity choice.
- **Shared files:** `Composer.tsx` and `RootLayout.tsx` are also changed by MYAI-56 and MYAI-61 (linked as conflicts); land one, then merge `develop` into the other.

### Success criteria
- [ ] Viewport meta matches legacy
- [ ] With an overlaying keyboard the last message is visible above the composer
- [ ] `is-ios` and the touch guard are active on iOS only
- [ ] Opening the keyboard while pinned keeps the last message in view
- [ ] Unit tests and the phone spec pass; `typecheck`, `lint`, `test`, `build` pass
### Reviewer brief
- **Objective:** the chat stays usable while typing on a phone: legacy viewport meta, last message visible above the composer with an overlaying keyboard, legacy iOS handling restored.
- **Decisions:** viewport meta copied from legacy (`interactive-widget=resizes-content`, `maximum-scale=1.0`, `user-scalable=no`); `useKeyboardOffset` also publishes `--keyboard-offset` and the transcript padding adds it; `computeKeyboardOffset` subtracts `offsetTop`; `useAutoFollow` re-scrolls on window and visual-viewport resize while pinned; `hooks/usePlatformClass.ts` adds `is-ios` and the iOS `touchmove` guard with an allowed-areas constant in `lib/scroll-lock.ts`; no JavaScript resizing of `#messages`.
- **Out of scope:** popover placement (MYAI-57), mobile layout and non-iOS opaque surfaces (MYAI-59), device-farm testing.
- **Success criteria:** meta matches legacy; last message visible above the composer in overlay mode; `is-ios` and the guard on iOS only; pinned transcript follows the keyboard; unit tests, the phone spec and checks pass.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- **Round 1:** validator PASS (6 minor). Judged PASS after checking `static/js/scroll-manager.js`, `frontend/playwright.config.ts`, `lib/scroll.ts` and `useAutoFollow.ts`. All six fixed inline: allowed-areas list explained; reading of acceptance criterion 2 stated; phone project scoped with `testMatch`; scroll timing after the padding update; `offsetTop` default 0; shared-file note for MYAI-56/61.

## Implementation notes
Branch bugfix/ios-keyboard, base develop (autopilot batch item 14).
### Implementation progress
- [x] Step 1: viewport meta (index.html) + test/viewport-meta.test.ts
- [x] Step 2: computeKeyboardOffset offsetTop, `--keyboard-offset` from useKeyboardOffset (+tests), transcript padding
- [x] Step 3: useAutoFollow re-scrolls on window and visual-viewport resize while pinned (+test)
- [x] Step 4: SCROLL_AREAS / isScrollAreaTarget, usePlatformClass (is-ios + touchmove guard), called from RootLayout (+tests)
- [x] Step 5: e2e/mobile-keyboard.spec.ts, `phone` Playwright project (Pixel 7), docs/frontend.md "Mobile"
Deviations: the phone-width padding rule is `#messages.messages-list ... !important` because legacy.css fixes `#messages` padding with !important at 768px and below (found live: the first version of the rule had no effect).
### Smoke test (2026-11-10)
check.sh --frontend-only: typecheck, lint, 371 tests, build pass; e2e phone 2/2 twice.
Live (Pixel 7 profile, keyboard simulated as a 300px smaller visual viewport): composer top 449 / bottom 539 (the visible bottom), last message bottom 433 (above the composer), transcript scrolled to the end; before the fix the last message stayed at 711.
Not verified: a real phone keyboard (Playwright cannot open one); iOS-only behaviour is covered by unit tests with an iPhone user agent.

PR: https://github.com/archit342000/My-AI/pull/114, branch bugfix/ios-keyboard, base develop

## Verification

### Acceptance review (2026-11-10)
Criteria ticked on the live and e2e results recorded in the PR's Testing section (checks run on throwaway backends during the autopilot run; scripts in `MYAI-58-evidence/`).
Left unticked, no PASS recorded:
- criterion 3: iOS-only behaviour covered by unit tests with iPhone/iPad user agents, not on a device

## Review history
### Round 1 - 2026-11-10
Verdict: Request changes (2 MAJOR). Single Haiku reviewer.
- R1-1 [MAJOR] `.composer-chips` scroll area missing from SCROLL_AREAS - Fixed (+test).
- R1-2 [MAJOR] iPadOS branch of `isIOS` untested - Fixed: isIOS cases (iPhone, iPad-as-Mac, desktop Mac, Linux) and a usePlatformClass iPad case.
- R1-3 [MINOR] animation frames not cancelled on unmount - Fixed.
- R1-4 [MINOR] comment on the two-frame wait was inaccurate - Fixed.
- R1-5 [MINOR] visualViewport stub cleanup in a test - Fixed (afterEach).
- R1-6 [MINOR] spec relied on a coarse pointer without saying so - Fixed (asserted).
- R1-7 [MINOR] README e2e row - Fixed. R1-8 [NIT] cast in a test mock - Fixed.
Resolution: check.sh passes (374 tests); phone e2e 2/2 twice after the fixes. Round 1 fixes were not re-reviewed. Not verified: a real phone keyboard.


## Log
- 2026-11-10: created
- 2026-11-10: added to epic MYAI-53
- 2026-11-10: linked conflicts_with MYAI-56
- 2026-11-10: linked conflicts_with MYAI-61
- 2026-11-10: plan validated, 1 rounds
- 2026-11-10: acceptance criteria reviewed against the recorded results (4 ticked, 1 left open)
- 2026-11-10: closed by the user after the PR merged into develop; 1 acceptance criteria left unticked as known limits (see Verification, Acceptance review)
