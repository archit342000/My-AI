---
id: MYAI-69
title: "Regression guards: real-shape fixtures, stub-backed e2e, inline styles"
status: done
epic: MYAI-53
created: 2026-11-10
updated: 2026-11-10
links:
  relates_to: [MYAI-54]
---

## Description
All checks pass while the main flows are broken: tests use hand-written shapes, e2e replaces the chat detail, and the inline-style ratchet stopped above zero.

Findings (MYAI-52, Verification): A-85, A-86. Evidence and the live test rig are in `~/.claude/tickets/My-AI/MYAI-52-evidence/`.

## Acceptance criteria
- [x] Shared fixtures recorded from the real API (multi-step turn with array `tool_calls`) are used by unit tests
- [x] A scripted inference stub and a Playwright project run send, multi-tool, stop, retry and temporary-chat flows against the real backend
- [x] A visual check script compares key geometry with stored numbers
- [x] The unused `ContextMenu` is removed and the inline-style guard can only shrink; its remaining entries belong to MYAI-60, 65, 66 and 67 and reach zero with them

## Plan
**Date:** 2026-11-10  **Status:** Validated

### Objective
Make the test suite able to see the kind of breakage the audit found: fixtures in the real API shape, an end-to-end run against the real backend with a scripted model, a geometry check with stored numbers, and a tighter inline-style guard.

### Context
- **Requirement:** this ticket's Description and Acceptance criteria (findings A-85, A-86 in MYAI-52).
- **Rules:** `docs/standards/testing.md` (isolated tests: no real network or LLM, temporary data directories, never `backend/data`; suites table; e2e is outside `scripts/check.sh`), `docs/standards/frontend.md` (new user flows get a Playwright spec; fixtures for streaming live in `src/test/fixtures/stream/`), `AGENTS.md` (inference is external: nothing here starts or manages llama.cpp; use `venv/bin/python`), memory of the repo owner: no hosted CI workflows.
- **Current state:**
  - `frontend/src/lib/chat-model.test.ts` builds messages by hand, not in the API's shape (`tool_calls` as a JSON string, and it expects one turn per assistant row), and component tests such as `features/chat/ChatPage.test.tsx` use one-message turns; the API returns `tool_calls` as a list and several assistant rows per turn.
  - `frontend/e2e/*.spec.ts` (`chat-send`, `artifact-overlay`, `user-roles`) run against the dev server on :5173 and replace `/v1/chat/completions` and the chat detail with `page.route`; `frontend/playwright.config.ts` has one `desktop` project and no `webServer`.
  - `frontend/src/test/inline-style.test.ts` holds a per-file `BASELINE`; `frontend/src/components/ui/ContextMenu.tsx` (with `ContextMenu.test.tsx`) is used only by `features/dev/PrimitivesDemo.tsx`; `docs/standards/frontend.md` and `docs/frontend.md` still name `ContextMenu` as a shared primitive.
  - The audit's rig (outside the repo, `~/.claude/tickets/My-AI/MYAI-52-evidence/scripts/`): `stub.py` (scripted OpenAI-style stream by keyword: plain, TOOL, MULTI, SLOW, CLARIFY, FILE, ERR), `serve.py`, `up.sh` (Flask on a throwaway `DATA_DIR` with `AUTH_PROVIDER=static`, `AI_PROXY_URL` pointing at the stub, `HF_HUB_OFFLINE=1`), `metrics.mjs` (geometry against legacy).
  - The backend loads a tokenizer named by the proxy's model config (`backend/models/__init__.py` `load_model_config`); the rig used a locally cached one.

### Approach
- **Recorded fixtures.** `frontend/src/test/fixtures/api/` (new) holds JSON captured from the real backend through the stub: chat details for a plain turn, a one-tool turn and a three-tool turn (list `tool_calls`, tool rows, `parent_id`), plus the chat list. A small typed loader `fixtures/api/index.ts` exposes them. `lib/chat-model.test.ts` gains cases that run `parseToolCalls` and `toTurns` on them. `fixtures/chat-detail.ts` does not exist yet (MYAI-54 creates it for edge cases and it is independent of these recordings); assertions that only pass after MYAI-54 are added as expected failures (see below).
- **Stack e2e.** A scripted model stub in Node with no dependencies, `frontend/e2e/stack/model-stub.mjs` (the scenarios of the rig's `stub.py`, plus the proxy's config and model-list endpoints), and a launcher `frontend/e2e/stack/start-stack.mjs` that creates a temporary data directory, starts the stub and the Flask app (`venv/bin/python`, with `DATA_DIR` and `CHROMA_PATH` inside the temporary directory, `AUTH_PROVIDER=static`, `ADMIN_EMAIL` and `AUTH_STATIC_EMAIL`, `AI_PROXY_URL` at the stub, `FRONTEND=react`, `HF_HUB_OFFLINE=1`) on free ports, waits for `/api/version`, and removes the directory on exit. A second Playwright config `frontend/playwright.stack.config.ts` (`testDir: 'e2e/stack'`, the same Chrome `launchOptions` as `playwright.config.ts`) uses it as `webServer` and points `baseURL` at the Flask port; `playwright.config.ts` gets `testIgnore: 'stack/**'` so `npm run e2e` does not pick these specs up; `npm run e2e:stack` builds the app and runs it. Nothing touches the real model server or `backend/data`.
- **Stack specs** in `frontend/e2e/stack/`: `send.spec.ts` (plain turn, reload shows the same row), `multi-tool.spec.ts` (one assistant row live and after reload, tool entries present after reload), `stop-retry.spec.ts` (stop keeps a partial reply, retry regenerates one turn), `temp-chat.spec.ts` (temporary chat sends and saves). Specs whose behaviour is fixed by another ticket carry `test.fail()` with the ticket's subject in a comment; that ticket removes the marker.
- **Geometry check.** `frontend/e2e/stack/geometry.spec.ts` measures the rectangles of the key chat elements at 1440x900 and 390x844 and compares them with `frontend/e2e/stack/geometry.json` (the legacy numbers recorded in the audit), 1px tolerance; entries not yet matching are listed under an `expectedFail` key in that file and reported, so the file shows exactly what is still off.
- **Inline-style guard and dead code.** `ContextMenu.tsx` and its test are deleted, its demo section removed and its `BASELINE` entry dropped; the guard additionally fails when a file not in `BASELINE` gains an inline style (it already does) and when an entry is higher than the current count (it already does), so it stays a ratchet. Docs name `Menu` and `Popover` instead of `ContextMenu`.
- **Rejected:** a Python stub under `frontend/` (would fall under the Python 1:1 test-mapping rule for a test helper); adding the stack run to `scripts/check.sh` (it needs Chrome and a cached tokenizer; it stays a documented manual suite like the existing e2e); pixel screenshots (brittle; rectangles are what the audit used).

### Out of scope
- Fixing the defects the new specs expose (their own tickets).
- Removing the remaining inline styles in files owned by MYAI-60, 65, 66 and 67.
- Hosted CI.

### Steps
#### Step 1: Model stub and stack launcher
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/e2e/stack/model-stub.mjs` (create), `frontend/e2e/stack/start-stack.mjs` (create), `frontend/playwright.stack.config.ts` (create), `frontend/playwright.config.ts` (modify: `testIgnore` for `stack/**`), `frontend/package.json` (modify: script `e2e:stack`), `frontend/eslint.config.js` (modify only if the new `.mjs` files need an override)
- **Change:** as in Approach ("Stack e2e"). The tokenizer name served by the stub's config comes from the environment variable `E2E_TOKENIZER`, defaulting to `Qwen/Qwen3.6-35B-A3B` (the tokenizer of the `general.vision` model in `inference_proxy/config.json`, and the one the audit rig ran with); the launcher fails with a clear message when the backend cannot load it offline.
- **Verification:** `node frontend/e2e/stack/start-stack.mjs --check` starts both processes, prints the base URL, `GET /api/me` answers as the admin and `GET /api/models/` lists the stub model, then everything stops and the temporary directory is gone; `backend/data` is untouched (its modification time does not change); `npx playwright test --list` with the default config lists no spec under `e2e/stack/`.

#### Step 2: Recorded API fixtures
- **Status:** todo
- **Depends on:** 1
- **Files:** `frontend/e2e/stack/record-fixtures.mjs` (create: drives the stack and writes the JSON), `frontend/src/test/fixtures/api/*.json` and `frontend/src/test/fixtures/api/index.ts` (create), `frontend/src/lib/chat-model.test.ts` and `frontend/src/features/chat/ChatPage.test.tsx` (modify: one case each on the recorded three-tool chat)
- **Change:** as in Approach ("Recorded fixtures"). Ids and timestamps are kept as recorded.
- **Verification:** `npm run test`: on the recorded three-tool chat, `parseToolCalls` returns the calls from the list form and the messages contain three tool rows; the turn-count assertion (one assistant turn) and the `ChatPage` assertion (one assistant row) are active if MYAI-54 is merged and marked `it.fails` otherwise.

#### Step 3: Stack specs
- **Status:** todo
- **Depends on:** 1
- **Files:** `frontend/e2e/stack/send.spec.ts`, `multi-tool.spec.ts`, `stop-retry.spec.ts`, `temp-chat.spec.ts` (create)
- **Change:** as in Approach ("Stack specs").
- **Verification:** `npm run e2e:stack`: `send` and the stop half of `stop-retry` pass on current `develop`; the others pass or are reported as expected failures, each with its marker comment.

#### Step 4: Geometry check
- **Status:** todo
- **Depends on:** 1
- **Files:** `frontend/e2e/stack/geometry.spec.ts` (create), `frontend/e2e/stack/geometry.json` (create: numbers from `~/.claude/tickets/My-AI/MYAI-52-evidence/metrics/`)
- **Change:** as in Approach ("Geometry check").
- **Verification:** `npm run e2e:stack` reports the matching entries as passed and lists the `expectedFail` entries; changing one stored number by 5px makes the spec fail.

#### Step 5: Dead primitive and guard
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/components/ui/ContextMenu.tsx` and `ContextMenu.test.tsx` (delete), `frontend/src/features/dev/PrimitivesDemo.tsx` (modify), `frontend/src/test/inline-style.test.ts` (modify: drop the entry), `frontend/src/styles/components.css` and `frontend/src/styles/legacy.css` (modify only to delete rules used solely by `ContextMenu`, if `test/css-coverage.test.ts` requires it), `docs/standards/frontend.md`, `docs/frontend.md` and `frontend/README.md` (modify: primitive names)
- **Change:** as in Approach ("Inline-style guard and dead code").
- **Verification:** `npm run typecheck`, `npm run lint`, `npm run test` pass; no file under `frontend/src` imports `components/ui/ContextMenu` (the `onContextMenu` handlers in `RecentChats.tsx` are unrelated).

#### Step 6: Docs and full checks
- **Status:** todo
- **Depends on:** 2, 3, 4, 5
- **Files:** `docs/standards/testing.md` (modify: Suites table row "End to end (stack)" with the command and its needs), `docs/frontend.md` (modify: Run, build, test table), `frontend/README.md` (modify: Commands table)
- **Change:** document `npm run e2e:stack`, what it starts, that it is not part of `scripts/check.sh`, and how fix tickets remove `test.fail()` markers.
- **Verification:** from `frontend/`: `npm run typecheck`, `npm run lint`, `npm run test`, `npm run build`, `npm run e2e:stack`; from the repo root `pytest tests` (docs guardrails) and `scripts/check.sh --frontend-only`.

### Tests
- Unit: `lib/chat-model.test.ts` on the recorded fixtures.
- E2E (stack): `e2e/stack/*.spec.ts`.
- Guards: `test/inline-style.test.ts`, `test/css-coverage.test.ts`.

### Risks and open questions
- **Tokenizer availability:** the backend needs a tokenizer in the local Hugging Face cache; on a machine without one the stack cannot start. The launcher says so and the docs name the variable.
- **Expected-failure markers can be forgotten;** each names the ticket subject, and Playwright reports a `test.fail()` that unexpectedly passes as a failure, which forces the cleanup.
- **Recorded fixtures drift** when the API changes; `record-fixtures.mjs` regenerates them.

### Success criteria
- [ ] Unit tests use fixtures recorded from the real API (three-tool turn with list `tool_calls`)
- [ ] `npm run e2e:stack` runs send, multi-tool, stop, retry and temporary-chat flows against the real backend with the scripted model, on a temporary data directory
- [ ] A geometry check compares key rectangles with stored numbers
- [ ] `ContextMenu` is removed and the inline-style guard only shrinks
- [ ] Docs describe the new suite; checks pass
### Reviewer brief
- **Objective:** tests that can see the audit's kind of breakage: real-shape fixtures, an end-to-end run against the real backend with a scripted model, a geometry check, a tighter inline-style guard.
- **Decisions:** JSON fixtures recorded from the real backend under `src/test/fixtures/api/` with a typed loader; a dependency-free Node model stub and launcher in `frontend/e2e/stack/` that start Flask on a temporary `DATA_DIR` with static auth and `HF_HUB_OFFLINE=1`; a second Playwright config and `npm run e2e:stack`; the default config ignores `stack/**`; stack specs for send, multi-tool, stop, retry and temporary chat, with `test.fail()` markers for behaviour fixed by other tickets; a geometry spec against stored legacy numbers with an `expectedFail` list; `ContextMenu` deleted and docs updated; the stack run stays outside `scripts/check.sh`; no Python under `frontend/`.
- **Out of scope:** fixing what the specs expose, inline styles owned by MYAI-60, 65, 66 and 67, hosted CI.
- **Success criteria:** unit tests on recorded fixtures; `npm run e2e:stack` covers the five flows on a temporary data directory; geometry check with stored numbers; `ContextMenu` gone and the guard only shrinks; docs describe the suite; checks pass.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- **Round 1:** validator FAIL (2 blocking, 4 minor). Judged FAIL. Valid blocking: `DATA_DIR` was missing from the launcher's environment list (the app would have written to `backend/data`); the default Playwright config would have picked up `e2e/stack` specs (added `testIgnore`). Minors fixed: which tests use the fixtures (`chat-model.test.ts` and `ChatPage.test.tsx`); `fixtures/chat-detail.ts` stated as not yet existing; Chrome launch options reused; the default tokenizer named.
- **Round 2 (diff-scoped):** validator PASS (1 minor). Judged PASS. Fixed inline: wording on what the hand-built messages get wrong.

## Implementation notes
Branch feature/regression-guards off develop. Built: dependency-free model stub, launcher (temp DATA_DIR, static auth, offline tokenizer), `npm run e2e:stack` config, specs (send, multi-tool, stop/retry, temp chat, geometry with legacy numbers and expectedFail list), recorded API fixtures (plain, one-tool, three-tool) with unit tests, ContextMenu removed with docs and baselines, docs rows.
- Known-bug specs use `test.fail()` / `it.fails`: multi-tool x2, temp chat, toTurns, ChatPage; the fixing changes delete the markers.
- Not done: version of geometry.json recorded once from the legacy UI (no recorder script; method noted in its comment). Chat list fixture dropped (unused).
- PR: https://github.com/archit342000/My-AI/pull/118, branch feature/regression-guards, base develop
- Smoke: scripts/check.sh --frontend-only passes (361 tests); npm run e2e:stack 9 passed (3 expected failures).

## Verification

### Acceptance review (2026-11-10)
Criteria ticked on the live and e2e results recorded in the PR's Testing section (checks run on throwaway backends during the autopilot run; scripts in `MYAI-69-evidence/`).
All criteria covered.
### Results (2026-11-10)
- `npm run e2e:stack`: 9 passed, incl. 3 expected failures; geometry +5px mutation fails as intended; `start-stack.mjs --check` shows /api/me and /api/models, cleans its temp dir.
- Unit tests on recorded fixtures: it.fails markers confirmed to fail on develop.

## Review history
### Round 1 - 2026-11-10 (Haiku, clean context): Approve with comments after fixes
Fixed: R1-1 loader comment made honest; R1-2 botContent selector now targets the reply (geometry still matches expectations); R1-3/4/5 launcher teardown on startup failure, waits for backend exit, own stub port env, graceful shutdown in config; R1-8 spec renamed; R1-9 sleep replaced by poll; R1-10 startChat waits for reply row; R1-11 unused fixture removed/used; R1-12 new lines wrapped; R1-13 geometry method noted; R1-14 config in tsconfig; R1-15 README added; R1-16 ERR token match.
Rejected/kept: R1-6 test.fail covers whole test (accepted: markers are removed by the fixing tickets; send.spec is the positive control); R1-7 toTurns marker (turn model lives in toTurns by design).
Fixes after the review were not re-reviewed.

## Log
- 2026-11-10: created
- 2026-11-10: added to epic MYAI-53
- 2026-11-10: linked relates_to MYAI-54
- 2026-11-10: acceptance criterion on inline styles narrowed during planning: the remaining baseline entries are in files owned by MYAI-60, 65, 66 and 67, which remove them
- 2026-11-10: plan validated, 2 rounds
- 2026-11-10 batch-autopilot: shipped, base develop
- 2026-11-10: acceptance criteria reviewed against the recorded results (4 ticked, 0 left open)
- 2026-11-10: closed by the user after the PR merged into develop
