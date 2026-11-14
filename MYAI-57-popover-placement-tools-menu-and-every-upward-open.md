---
id: MYAI-57
title: "Popover placement: tools menu and every upward-opening popover"
status: done
epic: MYAI-53
created: 2026-11-10
updated: 2026-11-10
links:
  blocks: [MYAI-59]
---

## Description
Popovers that open upward are positioned from their maximum height, not their real height, so the tools menu floats 73px above its button (mid-screen on phones). The searchable Select's search field overflows its panel, and popovers ignore the visual viewport and tooltips are not clamped.

Findings (MYAI-52, Verification): A-18, A-19, A-20, A-21. Evidence and the live test rig are in `~/.claude/tickets/My-AI/MYAI-52-evidence/`.

## Acceptance criteria
- [x] Tools menu sits 8px above the wrench on desktop at any viewport height
- [x] On a 390px screen the tools menu is a bottom sheet anchored above the composer
- [x] A Select or context menu that flips upward touches its anchor (4px gap)
- [x] Select search field stays inside the panel
- [ ] Popovers stay inside the visual viewport; tooltips are clamped to the screen edges
- [x] Tests cover the upward placement

## Plan
**Date:** 2026-11-10  **Status:** Validated

### Objective
Make every popover sit on its anchor: the tools menu directly above the wrench (a bottom sheet above the composer on phones), upward-flipping selects and menus touching their trigger, the select search field inside its panel, and popovers and tooltips kept inside the visible viewport.

### Context
- **Requirement:** this ticket's Description and Acceptance criteria (findings A-18 to A-21 in MYAI-52).
- **Rules:** `docs/standards/frontend.md` (pure logic in `src/lib/` with a test next to it, hooks in their own `useCamelCase` files, inline styles only for dynamic values with `// dynamic-style`, CSS custom properties, keyboard operable), `docs/frontend.md`.
- **Current code (`frontend/src/`):**
  - `components/ui/Popover.tsx`: `computePosition(anchor, placement, width, minWidth, viewport)` is a module-private function. For `bottom` placement with too little room below it returns `top = anchor.top - GAP - maxHeight` with `maxHeight = min(above, 480)`, so a panel shorter than 480px floats above its anchor. `top` placement anchors by `bottom` and is correct. `right` placement sets `top` from the anchor and a `maxHeight` to the viewport bottom. The viewport is `window.innerWidth/innerHeight`; updates run on window `resize` and capture-phase `scroll`.
  - `features/tools/ToolsMenu.tsx`: `<Popover>` with the default `bottom` placement, `width={320}`, anchored to `#tools-button`. Measured at 1440x900: panel bottom 754, button top 827.
  - `components/ui/Select.tsx` and `components/ui/Menu.tsx` (including `SubMenu`, `placement="right"`) use `Popover`; the context menu passes `point`.
  - `styles/components.css`: `.ui-select__search { margin: var(--space-2) }` on a full-width `.ui-input` (overflows the panel on the right); `.ui-popover`, `.tools-panel`, `.ui-tooltip` blocks.
  - `components/ui/Tooltip.tsx`: fixed position above the anchor centre with `translate(-50%, -100%)`, no clamping.
  - Tests: `components/ui/primitives.test.tsx` (Tooltip, Select, Menu), `features/tools/ToolsMenu.test.tsx`.

### Approach
- **Placement as tested pure logic.** Move the placement maths to `lib/popover-position.ts`: `computePosition` (same inputs plus the panel's measured height and the visible viewport rectangle) and `tooltipPosition`. Rules: a panel that opens upward is anchored by its bottom edge (`bottom` set, `top` unset), so its real height no longer matters; a `right` panel that would run past the bottom is shifted up to fit; every result is clamped to the viewport rectangle with the existing 8px margin.
- **Measure, then place.** `Popover` keeps a ref to its panel and re-runs the placement when the panel's size changes (`ResizeObserver`), passing the measured height. The first paint stays hidden until a position exists, as today.
- **Visible viewport.** `Popover` reads `window.visualViewport` (width, height, `offsetTop`, `offsetLeft`) when present, falling back to the window size, and also updates on `visualViewport` `resize` and `scroll`.
- **Tools menu.** `placement="top"` on desktop (8px above the wrench, `width={320}`). At 768px and below it becomes a sheet anchored above the composer box: `ToolsMenu` passes `width` as the visible viewport width minus 16px, read from `window.visualViewport` (else `window.innerWidth`) when the menu opens (the `width` prop is what `Popover` applies), and the 8px side margin comes from the existing clamping. `ToolsMenu` takes an optional `sheetAnchorRef` (the composer's `.input-container`, which `Composer` already holds in `inputContainer`) and a new hook `hooks/useMediaQuery.ts` reports the breakpoint.
- **Select search field.** The field is sized to the panel minus its margins (CSS only).
- **Tooltip.** `Tooltip` keeps a ref on its bubble, measures it in a layout effect after it renders and uses `tooltipPosition` to keep it inside the viewport, placing it below the anchor when there is no room above.
- **Rejected:** fixing only the tools menu by switching its placement (A-19 would remain for selects and context menus); a positioning library (the project keeps runtime dependencies lean and the rules are small).

### Out of scope
- The focus ring left on the tools button after closing with Escape (keyboard focus returning to the trigger is intended).
- Other mobile layout work: MYAI-59. Keyboard handling of the composer itself: MYAI-58.
- Restyling menus, selects or tooltips.

### Steps
#### Step 1: Placement logic
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/lib/popover-position.ts` (create: `computePosition`, `tooltipPosition`, their types), `frontend/src/lib/popover-position.test.ts` (create)
- **Change:** as in Approach ("Placement as tested pure logic"); the constants `MARGIN`, `GAP`, `TOP_GAP` and the `zeroRect` helper for point anchors move here.
- **Verification:** unit tests: `bottom` with room opens below; without room it returns `bottom = viewport height - anchor top + GAP` (4px; the distance from the viewport's bottom edge, as the existing `top` placement computes it) and no `top`; `top` placement is unchanged; `right` near the viewport bottom is shifted up to fit a measured height; a point anchor near the bottom opens upward from the point; results respect an offset visual viewport; tooltip x is clamped at both edges and flips below at the top edge.

#### Step 2: Popover uses it, measures and follows the visual viewport
- **Status:** todo
- **Depends on:** 1
- **Files:** `frontend/src/components/ui/Popover.tsx` (modify: remove the private `computePosition` and `zeroRect`, panel ref, `ResizeObserver` guarded with `typeof ResizeObserver === 'undefined'` as `Composer.tsx` does, viewport source and listeners), `frontend/src/components/ui/primitives.test.tsx` (modify)
- **Change:** as in Approach ("Measure, then place", "Visible viewport"). The public props do not change.
- **Verification:** component tests: a Select whose trigger sits at the bottom of the viewport renders its list with a `bottom` style and no `top`; the existing Select and Menu keyboard tests and the slash-menu tests in `features/composer/Composer.test.tsx` still pass; closing the popover removes its window and `visualViewport` `resize` and `scroll` listeners (asserted with spies on `removeEventListener`).

#### Step 3: Tools menu placement and phone sheet
- **Status:** todo
- **Depends on:** 2
- **Files:** `frontend/src/hooks/useMediaQuery.ts` (create), `frontend/src/hooks/useMediaQuery.test.ts` (create), `frontend/src/features/tools/ToolsMenu.tsx` (modify: `placement`, `sheetAnchorRef`, width), `frontend/src/features/composer/Composer.tsx` (modify: pass `inputContainer` to `ToolsMenu`), `frontend/src/features/tools/ToolsMenu.test.tsx` (modify), `frontend/src/styles/components.css` (modify: "Tools menu (tools-panel)" block for the sheet)
- **Change:** as in Approach ("Tools menu").
- **Verification:** component tests: on a wide viewport the panel is anchored to the button with `top` placement; with the media query matching it is anchored to the composer box and spans the viewport width minus the margins; Escape and outside press still close it.

#### Step 4: Select search field and tooltip clamping
- **Status:** todo
- **Depends on:** 1
- **Files:** `frontend/src/styles/components.css` (modify: `.ui-select__search` in the "Select (ui-select)" block), `frontend/src/components/ui/Tooltip.tsx` (modify), `frontend/src/components/ui/primitives.test.tsx` (modify)
- **Change:** as in Approach ("Select search field", "Tooltip").
- **Verification:** component test: a tooltip on an anchor at the left edge is positioned with its left side inside the viewport. The search field is checked in Step 5.

#### Step 5: Browser check, docs and full checks
- **Status:** todo
- **Depends on:** 3, 4
- **Files:** `frontend/e2e/popover-placement.spec.ts` (create), `docs/frontend.md` (modify: the `src/lib/` row of the Layout table names popover placement)
- **Change:** a Playwright spec that opens the tools menu on `/` at 1440x900 and at 390x844, opens the model select in Chat Settings, and opens a chat context menu from the last sidebar row.
- **Verification:** the spec asserts: desktop tools panel bottom is 8px above the wrench's top (1px tolerance); on the phone viewport the panel's bottom is above the composer box and its sides are 8px from the screen edges; the select's search field right edge is inside the list panel; the context menu lies fully inside the viewport. Then from `frontend/`: `npm run typecheck`, `npm run lint`, `npm run test`, `npm run build`; `npm run e2e` for the spec; `scripts/check.sh --frontend-only` from the repo root.

### Tests
- Unit: `lib/popover-position.test.ts`, `hooks/useMediaQuery.test.ts`.
- Component: `components/ui/primitives.test.tsx`, `features/tools/ToolsMenu.test.tsx`.
- E2E: `e2e/popover-placement.spec.ts`.

### Risks and open questions
- **jsdom has no layout and no `ResizeObserver`:** `Popover` guards the observer, component tests stub the anchor's `getBoundingClientRect`, and the real geometry is covered by the Playwright spec.
- **Composer slash menu** already uses `placement="top"` and must keep its position (Step 2 verification runs its tests).

### Success criteria
- [ ] Tools menu is 8px above the wrench on desktop at any height
- [ ] Tools menu is a sheet above the composer at 390px
- [ ] Upward-flipping selects and menus touch their anchor
- [ ] Select search field stays inside the panel
- [ ] Popovers and tooltips stay inside the visible viewport
- [ ] Unit, component and e2e tests cover the upward placement; `typecheck`, `lint`, `test`, `build` pass
### Reviewer brief
- **Objective:** every popover sits on its anchor and inside the visible viewport; the tools menu is above the wrench on desktop and a sheet above the composer on phones.
- **Decisions:** placement maths moves to `lib/popover-position.ts` (`computePosition`, `tooltipPosition`); upward panels are anchored by `bottom`; `Popover` measures its panel (`ResizeObserver`, guarded) and uses `window.visualViewport`; `ToolsMenu` uses `placement="top"`, and at 768px and below anchors to the composer box with a viewport-wide width via `hooks/useMediaQuery.ts`; select search field fixed in CSS; `Tooltip` measures and clamps; no positioning library; `Popover` props unchanged.
- **Out of scope:** the focus ring on the tools button after Escape, other mobile layout (MYAI-59), composer keyboard handling (MYAI-58), restyling.
- **Success criteria:** tools menu 8px above the wrench at any height; sheet above the composer at 390px; upward selects and menus touch their anchor (4px); search field inside the panel; popovers and tooltips inside the visible viewport; unit, component and e2e tests; checks pass.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- **Round 1:** validator FAIL (1 blocking, 7 minor). Judged FAIL. Valid blocking: Step 1 verification described the upward `bottom` value wrongly (fixed to `viewport height - anchor top + GAP`). Minors fixed: sheet width source; `ResizeObserver` guard; slash-menu tests named; listener-removal check; `zeroRect` placed; tooltip ref and layout effect; docs edit made unconditional.
- **Round 2 (diff-scoped):** validator PASS (3 minor). Judged PASS. All three fixed inline (width read on open, `GAP` named, `visualViewport` listeners in the removal check).

## Implementation notes
Branch bugfix/popover-placement, base bugfix/thought-box-timeline (autopilot batch item 9, stacked-on for the chain to MYAI-59; no code dependency on the base).
### Implementation progress
- [x] Step 1: lib/popover-position.ts (+test)
- [x] Step 2: Popover measures (ResizeObserver, guarded), uses the visual viewport; Popover.test.tsx
- [x] Step 3: hooks/useMediaQuery.ts (+test), ToolsMenu top placement and phone sheet, Composer passes the composer box
- [x] Step 4: select search field CSS, Tooltip measure and clamp (Tooltip.test.tsx)
- [x] Step 5: e2e/popover-placement.spec.ts, docs/frontend.md
Deviations: Popover gains an optional `positionRef` (element to place against); the plan said props unchanged, but with the composer box as `anchorRef` the outside-press check would treat clicks in the composer as inside, so the anchor stays the wrench and only the placement uses the box. `.ui-select__search` rule needed `.ui-input.` for specificity.
### Smoke test (2026-11-10)
check.sh --frontend-only: typecheck, lint, 443 tests, build pass.

PR: https://github.com/archit342000/My-AI/pull/109, branch bugfix/popover-placement, base bugfix/thought-box-timeline

## Verification

### Acceptance review (2026-11-10)
Criteria ticked on the live and e2e results recorded in the PR's Testing section (checks run on throwaway backends during the autopilot run; scripts in `MYAI-57-evidence/`).
Left unticked, no PASS recorded:
- criterion 5: tooltip clamping at screen edges: unit tests only

## Review history
### Round 1 - 2026-11-10
Verdict: Request changes (3 MAJOR). Single Haiku reviewer.
- R1-1 [MAJOR] Prettier on new Popover.test.tsx - Fixed.
- R1-2 [MAJOR] context-menu upward flip untested - Fixed: unit test (point near bottom: bottom 24px, no top) and e2e asserts the 4px gap from the pointer.
- R1-3 [MAJOR] ContextMenu.tsx primitive still guesses its height - Rejected: used only by the dev PrimitivesDemo; the production chat context menu goes through Menu and Popover, which is fixed. Follow-up: align or remove the dev-only ContextMenu.
- R1-4 [MINOR] .tools-popover--sheet repeated the base radius - Fixed: class and rule removed.
- R1-5 [MINOR] viewport read written three times - Fixed: `readVisibleViewport` in lib (tested); MARGIN imported.
- R1-6 [MINOR] tooltip not clamped at the bottom when flipped - Fixed, test added.
- R1-7 [MINOR] matchMedia guard - Fixed: guard removed (setup stub exists; other code calls it unguarded).
- R1-8 [NIT] class queries in tests - Fixed where a role exists. R1-9 [NIT] `as number` casts - Fixed.
Resolution: check.sh passes (445 tests); e2e 4/4 three runs in a row; live V1-V5 re-run. Round 1 fixes were not re-reviewed. Not verified live: tooltip clamping at screen edges (unit tests only). The rig's /api/models returns 500 (stub has no model list): rig artefact, unrelated.


## Log
- 2026-11-10: created
- 2026-11-10: added to epic MYAI-53
- 2026-11-10: linked blocks MYAI-59
- 2026-11-10: plan validated, 2 rounds
- 2026-11-10: acceptance criteria reviewed against the recorded results (5 ticked, 1 left open)
- 2026-11-10: closed by the user after the PR merged into develop; 1 acceptance criteria left unticked as known limits (see Verification, Acceptance review)
