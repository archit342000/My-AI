---
id: MYAI-72
title: "Model speed test: streamed run with live figures"
status: done
epic: MYAI-53
created: 2026-11-10
updated: 2026-11-10
links:
  split_from: [MYAI-70]
---

## Description
The React model manager posts to `/api/models/test-speed` and reads the reply as one JSON document, but the endpoint streams events (status lines, token deltas, timings and usage), so the test cannot show progress and its result is not usable. Legacy (`static/js/telemetry-chart.js`) reads the stream and shows status, tokens in context, time to first token, prefill and decode speed, a chart across turns, a target-context slider and a Stop button.

Findings (MYAI-52, Verification): A-80 (telemetry chart for the speed test).

## Acceptance criteria
- [x] Running the speed test shows the server's status text and live figures: tokens in context, average time to first token, prefill tokens per second and decode tokens per second
- [x] A chart shows decode speed against context size across turns
- [x] The target context size can be chosen before the run and the run can be stopped
- [ ] A failure shows the server's error; the dialog stays usable
- [ ] The feature is admin only, as today

## Plan
**Date:** 2026-11-10  **Status:** Validated

### Objective
Make the model speed test work in the React model manager: read the test as the event stream it is, show the status and live figures, plot decode speed against context size, allow choosing the target context and stopping the run.

### Context
- **Requirement:** this ticket's Description and Acceptance criteria (the speed-test part of finding A-80 in MYAI-52).
- **Rules:** `docs/standards/frontend.md` (typed API calls in `src/api/`, the SSE reader in `api/sse.ts`, pure logic in `src/lib/` with tests, effects clean up streams, no inline styles except `// dynamic-style`, no new runtime dependencies without need), `AGENTS.md` (inference is external; this only calls the existing proxy endpoint), the repo's QA plan rule not to run speed tests against the shared inference server during testing.
- **Server facts:** `POST /api/models/test-speed` (admin, passed through `backend/models/__init__.py` to `inference_proxy/router.py` `proxy_test_model_speed`) takes `{ model, target_context_threshold }` and streams `data:` lines: `{ test_status }` texts (unloading, loading, "Starting Turn N (Current Context: a/b)", "Completed…"), model deltas (`choices[0].delta.content`), `timings` (`prompt_ms`, `prompt_n`, `predicted_ms`, `predicted_n`), `usage.total_tokens`, and `{ error }`. It unloads every loaded model first.
- **Legacy reference:** `static/js/telemetry-chart.js` (`runTest` and the stream loop: per turn, time to first token = `prompt_ms` (milliseconds), prefill speed = `prompt_n / (prompt_ms / 1000)` tokens per second, decode speed = `predicted_n / (predicted_ms / 1000)` tokens per second; a zero or missing `prompt_ms` / `predicted_ms` gives 0, as the legacy code guards it; the three figures shown are running averages over turns; tokens in context from `usage.total_tokens`, else `prompt_n + predicted_n`; an `error` event aborts the test (although the proxy sends some `error` events and then carries on, for example "Failed to fully unload existing models. Proceeding anyway..."); `drawTelemetryChart` plots the points on a canvas), `static/index.html` (`#test-speed-context-slider`: 1,000 to 1,000,000 in steps of 1,000, default 128,000; Run and Stop buttons).
- **Current code (`frontend/src/`):** `api/settings.ts` `modelsApi.testSpeed` uses `apiJson` and a fixed context of 4096 from `features/settings/ModelsDialog.tsx`, which prints the result as JSON text; `api/sse.ts` `readSse`; `components/ui/Slider.tsx`, `Badge`, `Button`.

### Approach
- **Stream call.** `modelsApi.testSpeedStream(model, targetContext, signal)` posts with `apiRequest` and yields parsed events through `readSse`; `testSpeed` goes once the panel replaces its caller.
- **Pure reducer.** `lib/speed-test.ts` (new): `emptySpeedTest()` and `applySpeedEvent(state, event)` keep the status text, the turn count, the running averages (time to first token, prefill, decode), the tokens in context and the chart points (`{ contextTokens, decodeTps }`, one per turn), using the legacy formulas (tokens in context from `usage.total_tokens`, else `prompt_n + predicted_n`). An `error` event is kept as a warning line and the run goes on (a deliberate difference from legacy, because the proxy continues after some of them); the run is failed when the stream ends without a "Completed" status, and then the last warning is shown as the error.
- **Panel.** `features/settings/SpeedTestPanel.tsx` (new) replaces the speed-test part of `ModelsDialog`: model `Select`, target-context `Slider` (1,000 to 1,000,000, step 1,000, `decimals={0}`), Run and Stop buttons, the status line, four figures, and the chart. The run lives in a hook `features/settings/useSpeedTest.ts` (new) that owns the `AbortController`, feeds events to the reducer, aborts on Stop and on unmount, and refreshes the model list when the run ends. Before starting, a `ConfirmDialog` says that the test unloads all loaded models.
- **Chart.** `features/settings/SpeedChart.tsx` (new): an inline SVG polyline with axes and min/max labels computed by a pure helper `chartGeometry(points, width, height)` in `lib/speed-test.ts`; no charting dependency.
- **Rejected:** porting the legacy canvas code (imperative and tied to DOM ids); polling instead of streaming (the endpoint only streams).

### Out of scope
- Changes to the proxy endpoint, including its behaviour of unloading models.
- Saving or comparing past runs.

### Steps
#### Step 1: Stream call and reducer
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/api/settings.ts` (modify: add `testSpeedStream`; `testSpeed` is removed in Step 3 with its last caller), `frontend/src/lib/speed-test.ts` (create), `frontend/src/lib/speed-test.test.ts` (create), `frontend/src/test/fixtures/stream/speed-test.sse` (create: status lines, two turns with deltas, timings and usage, completion)
- **Change:** as in Approach ("Stream call", "Pure reducer", `chartGeometry`).
- **Verification:** unit tests on the fixture: after two turns the averages equal the hand-computed values, tokens in context equal the last `usage.total_tokens`, there are two chart points and the status is the completion text; a turn without `usage` takes its tokens from the timings; an `error` event followed by more events leaves the run going with a warning, and a stream that ends without "Completed" is failed with that warning; `chartGeometry` maps the extreme points to the plot corners.

#### Step 2: Hook
- **Status:** todo
- **Depends on:** 1
- **Files:** `frontend/src/features/settings/useSpeedTest.ts` (create), `frontend/src/features/settings/useSpeedTest.test.tsx` (create)
- **Change:** as in Approach (the hook).
- **Verification:** tests with a mocked `fetch` (the SSE helpers in `src/test/fixtures/sse.ts`): starting a run moves through running to done with the reducer's figures; Stop aborts the request and leaves the figures gathered so far with the status "Stopped"; unmounting aborts; an HTTP error shows its message.

#### Step 3: Panel and chart
- **Status:** todo
- **Depends on:** 2
- **Files:** `frontend/src/features/settings/SpeedTestPanel.tsx` (create), `frontend/src/features/settings/SpeedChart.tsx` (create), `frontend/src/features/settings/SpeedTestPanel.test.tsx` and `SpeedChart.test.tsx` (create), `frontend/src/api/settings.ts` (modify: remove `testSpeed`), `frontend/src/features/settings/ModelsDialog.tsx` (modify: use the panel), `frontend/src/features/settings/ModelsDialog.test.tsx` (modify), `frontend/src/styles/components.css` (modify: new "Speed test" block)
- **Change:** as in Approach ("Panel", "Chart").
- **Verification:** component tests: Run asks for confirmation and then starts with the chosen model and context; the four figures and the status update from the stream; the chart renders one point per turn and its axis labels show the minimum and maximum; Stop is shown only while running; a failed run shows the error and Run is usable again.

#### Step 4: Docs and full checks
- **Status:** todo
- **Depends on:** 3
- **Files:** `frontend/e2e/speed-test.spec.ts` (create: with `/api/models/test-speed` answered from the fixture stream by `page.route`, run, see the figures and the chart, and stop a second run), `docs/frontend.md` (modify only if it mentions the speed test)
- **Change:** docs match the code.
- **Verification:** from `frontend/`: `npm run typecheck`, `npm run lint`, `npm run test`, `npm run build`, and `npm run e2e` for the new spec (outside the merge gate; needs the dev server and backend); from the repo root `pytest tests` and `scripts/check.sh --frontend-only`. No live run against the shared inference server; the verify stage uses the fixture stream through a mocked route, and a real run only if the user asks for one.

### Tests
- Unit: `lib/speed-test.test.ts`.
- Component and hook: `useSpeedTest.test.tsx`, `SpeedTestPanel.test.tsx`, `SpeedChart.test.tsx`, `ModelsDialog.test.tsx`.
- E2E: `e2e/speed-test.spec.ts`.

### Risks and open questions
- **The test unloads the user's loaded models;** the confirmation states it, as the only safeguard on the client.
- **Mid-stream `error` events** are warnings here and fatal in legacy; a run that truly failed is still reported, because it ends without a "Completed" status.
- **Shared file:** `ModelsDialog.tsx` is also touched by MYAI-67 (imports and spacing).

### Success criteria
- [ ] Status text and live figures (tokens in context, time to first token, prefill and decode speed) update during a run
- [ ] A chart shows decode speed against context size across turns
- [ ] Target context can be chosen and the run can be stopped
- [ ] A failure shows the server's error and the dialog stays usable
- [ ] Admin only, as today; checks pass
### Reviewer brief
- **Objective:** the model speed test streams its run and shows live status, running averages and a chart, as the legacy telemetry panel does, in place of the raw JSON dump.
- **Decisions:** `modelsApi.testSpeedStream` through `apiRequest` and `readSse`; a pure reducer in `lib/speed-test.ts` with the legacy formulas (time to first token = `prompt_ms`, prefill = `prompt_n / (prompt_ms / 1000)`, decode = `predicted_n / (predicted_ms / 1000)`, 0 when the time is 0; running averages); `SpeedTestPanel` replaces the speed-test part of `ModelsDialog`, the run owned by `useSpeedTest` with Stop; `SpeedChart` is an inline SVG with a pure geometry helper, no charting dependency; stream warnings are listed without ending the run.
- **Out of scope:** changes to the proxy endpoint, including its unloading of models; saving or comparing past runs.
- **Success criteria:** status and live figures update during a run; a chart of decode speed against context size; target context selectable and the run stoppable; a failure shows the server's error and the dialog stays usable; admin only; checks pass.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- **Round 1 (Haiku): FAIL.** Judged FAIL. Valid BLOCKING: the speed formulas divided by milliseconds, giving figures 1000 times too small against `static/js/telemetry-chart.js`; fixed to the per-second formulas. Also fixed: warnings versus fatal errors in the stream, an e2e spec and a chart test added.
- **Round 2 (Haiku): PASS.** Judged PASS. MINOR (valid, fixed inline): the formulas had no guard for a zero or missing time; the legacy guard (`telemetry-chart.js` lines 492-499) is now stated in Context.

## Implementation notes
- [x] Steps 1-4 done on branch feature/model-speed-test: `testSpeedStream`, `lib/speed-test.ts` reducer, `useSpeedTest`, `SpeedTestPanel`, `SpeedChart`, ModelsDialog rewired, e2e spec; old `testSpeed` and `.model-result` removed. No docs mentioned the speed test.
- Smoke: scripts/check.sh --frontend-only passes.
- PR: https://github.com/archit342000/My-AI/pull/119, branch feature/model-speed-test, base develop

## Verification

### Acceptance review (2026-11-10)
Criteria ticked on the live and e2e results recorded in the PR's Testing section (checks run on throwaway backends during the autopilot run; scripts in `MYAI-72-evidence/`).
Left unticked, no PASS recorded:
- criterion 4: failure display: unit/component tests only, not live
- criterion 5: admin gating unchanged and not re-checked in this change
### Results (2026-11-10)
Live on a throwaway backend with a stub proxy (rig in MYAI-72-evidence/scripts, screenshots in shots/): figures 933 ms / 2783.07 / 36.11 tok/s / 8,800 tokens match hand values; 3 chart points; warning listed; Stop gives "Stopped"; desktop and phone, light and dark; no console errors; e2e spec 2 passed. Not run: real inference server (would unload shared models).

## Review history
### Round 1 - 2026-11-10 (Haiku): Request changes, then fixed
R1-1 [MAJOR] stream cut off while generating counted as Completed - Fixed (only a Completed status succeeds; test flipped). R1-2 [MINOR] stale run could overwrite a newer one - Fixed (controller guard + test). R1-3 [MINOR] NaN from non-numeric figures - Fixed (num helper + test). R1-6 dead `.model-result` css - Fixed. R1-7 padding constant - Fixed. R1-4 focus/label association, R1-5 chart accessible name, R1-8 comment width - Deferred (listed as follow-ups in the PR). Fixes were not re-reviewed.

## Log
- 2026-11-10: created (split from MYAI-70)
- 2026-11-10: added to epic MYAI-53
- 2026-11-10: plan validated, 2 rounds
- 2026-11-10 batch-autopilot: shipped, base develop
- 2026-11-10: acceptance criteria reviewed against the recorded results (3 ticked, 2 left open)
- 2026-11-10: closed by the user after the PR merged into develop; 2 acceptance criteria left unticked as known limits (see Verification, Acceptance review)
