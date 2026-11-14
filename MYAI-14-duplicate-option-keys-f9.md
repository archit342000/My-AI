---
id: MYAI-14
title: "F9: duplicate option keys in model lists (not reproduced)"
status: done
created: 2026-11-08
updated: 2026-11-09
---

## Description
Report F9 (Low). The 'Model' label appearing twice and the placeholder wrap are fixed. The duplicate option keys in the model lists are not in the report text and were not reproduced; keep this open only if a duplicate id appears in real data. Not blocked.

## Acceptance criteria
- [x] Reproduce with duplicate model ids, or close as not reproduced (closed as not reproduced, 2026-11-09)

## Plan
**Date:** 2026-11-09  **Status:** Validated

### Objective
Decide, with evidence, whether duplicate model ids can reach the frontend model lists and cause duplicate React keys (report F9, Low). If they can, apply the smallest fix; if not, close the ticket as not reproduced. Investigation first; code changes only on the "reproduced" branch.

### Context
- **Requirement:** Acceptance criterion "Reproduce with duplicate model ids, or close as not reproduced". Code read at origin/develop 6a13e04 (the earlier Implementation note was taken at e327094; the model-list code it describes is unchanged at 6a13e04). Implementation branches from origin/develop. Correction to that note: `ChatSettingsModal` does not key the model options itself; they are keyed by `Select.tsx` `key={option.value}` (its own `key={key}` at line 92 is for tabs).
- **Assumptions (no user available):** (A1) Per the Description ("keep this open only if a duplicate id appears in real data"), "reproduced" means a real `/api/models/` or upstream `/v1/models` response contains a repeated `id`. The synthetic test (Step 3) and the upstream check (Step 2) are supporting evidence only; neither alone triggers the fix. (A2) If there is no usable 200 response from either endpoint (401, unreachable or unparseable), the outcome is "not reproduced", with the Step 2 finding recorded so the ticket can be reopened if real data ever shows a duplicate. (A3) If duplicates happen, keep one entry per id, preferring the best status (loaded > loading > other).
- **Docs and rules:** `docs/standards/frontend.md` (stable `key`s from ids; pure logic in `src/lib/` with a Vitest test next to it; run `npm run typecheck`, `lint`, `test` from `frontend/`). `docs/standards/testing.md` ("a bug fix adds a test that fails without the fix"; frontend commands; `scripts/check.sh --frontend-only`). `AGENTS.md`/`CLAUDE.md` general rules.
- **Data path (no dedupe anywhere):**
  - `frontend/src/api/settings.ts` `modelsApi.list` returns `GET /api/models/` `.data` unchanged.
  - `backend/models/__init__.py` `pass_through` streams `/api/models/*` to `config.AI_PROXY_URL` unchanged.
  - `inference_proxy/router.py` `proxy_get_models` returns the upstream llama.cpp server's `GET {AI_URL}/v1/models` body unchanged.
  - So the frontend list is exactly the upstream server's `/v1/models` `data` array; duplicates can only originate upstream.
- **Where lists are built and keyed:**
  - `frontend/src/lib/model-options.ts`: `sortModels` (sort only, no dedupe), `modelSelectOptions` (maps each model to `{ value: m.id, ... }`).
  - `frontend/src/features/settings/ModelsDialog.tsx`: instance list `<li key={m.id}>` over `sortModels(...)`; speed-test `Select` with `modelSelectOptions(...)`.
  - `frontend/src/features/settings/ChatSettingsModal.tsx`: model `Select` with `modelSelectOptions(models.data ?? [])`.
  - `frontend/src/components/ui/Select.tsx`: options rendered with `key={option.value}`; `aria-selected={option.value === value}` (a repeated id would render two selected options); grouping via `frontend/src/lib/option-groups.ts` `groupOptions` (no dedupe).
  - `frontend/src/features/composer/Composer.tsx` uses `models.data.some/find` only (no keyed list; unaffected).
- **Existing tests:** `frontend/src/lib/model-options.test.ts`, `frontend/src/features/settings/ModelsDialog.test.tsx` (mocks `modelsApi.list` via `vi.spyOn`).

### Approach
Reproduce in three layers: (1) live data if a stack is reachable, (2) upstream behaviour for how `/v1/models` ids are produced, (3) a throwaway frontend test that feeds duplicate ids to show the concrete failure mode. Apply the decision rule. If reproduced, dedupe once in `sortModels` (both the instance list and `modelSelectOptions` go through it), keeping the best-ranked entry per id. Rejected: index-based or composite keys (hides the duplicate but still shows two rows and two `aria-selected` options, and the standard forbids index keys for reorderable lists); deduping in the backend or proxy (pass-throughs by design, see `backend/models/README.md`).

### Steps
#### Step 1: Check live data (if available)
- **Files:** none (read-only); evidence in `~/.claude/tickets/My-AI/MYAI-14-evidence/` (create).
- **Change:** Do not start the stack for this. Run `E=~/.claude/tickets/My-AI/MYAI-14-evidence; mkdir -p "$E"`, then:
  1. Backend: `code=$(curl -s --max-time 10 -o "$E/api-models.json" -w '%{http_code}' ${APP_PASSWORD:+-u ":$APP_PASSWORD"} http://localhost:5000/api/models/)` (`app.py` `require_auth` returns 401 when `APP_PASSWORD` is set and missing or wrong).
  2. If `code` is not 200, run the upstream fallback: `code2=$(curl -s --max-time 10 -o "$E/v1-models.json" -w '%{http_code}' http://localhost:8080/v1/models)` (`AI_URL` defaults to `http://localhost:8080` in `inference_proxy/config.py`). Whichever path is taken, also try `curl -s --max-time 10 -o "$E/props.json" -w '%{http_code}' http://localhost:8080/props` and keep the file only on 200 (Step 2 uses its build info).
  3. For whichever file has a 200, list repeated ids: `jq '[.data[].id] | group_by(.) | map(select(length>1))' <file>` (`jq` is at `/usr/bin/jq`). If jq cannot parse the 200 body (not JSON, or no `.data`), record "unusable response", which counts as no usable 200 in Step 4.
  Record each status as 200, "401 (password missing or rejected)" or "unreachable" (curl code 000).
- **Verification:** ticket Implementation notes record the statuses and the repeated-id result (list or "none"), with links to the saved files.

#### Step 2: Check the upstream id source
- **Files:** none (read-only).
- **Change:** In the llama.cpp repository (`ggml-org/llama.cpp`, `tools/server/`, at the commit hash in the `/props` build info from Step 1 if it has one, else `master`; read it with `gh api 'repos/ggml-org/llama.cpp/contents/tools/server?ref=<hash or master>'` to list the files, then fetch the file that builds the models list or a web fetch of the same GitHub source), find how the `/v1/models` list is built in router mode and whether entries are stored in a map keyed by model name (unique) or a list that can repeat a name from several sources (cache, `--models-dir`, preset). Outcome is one of: "unique by construction", "can repeat" (cite the code), or "inconclusive" (source not found or ambiguous). This is supporting evidence only (A1).
- **Verification:** ticket notes record the outcome, the file and commit/tag checked, and a link.

#### Step 3: Demonstrate the failure mode with a duplicate-id test
- **Files:** `frontend/src/lib/model-options.test.ts` (modify), `frontend/src/features/settings/ModelsDialog.test.tsx` (modify).
- **Change:** Add a case feeding the same id twice (different statuses) to `modelSelectOptions`/`sortModels`, asserting one entry per id; add a `ModelsDialog` case with a mocked duplicate list asserting one instance row per id and no React duplicate-key warning (spy on `console.error`).
- **Verification:** `npm run test` from `frontend/` shows the new cases failing on current code (expected), which documents the failure mode. Record the failure output in the ticket. These edits are kept or reverted in Step 4 only.

#### Step 4: Apply the decision rule
- **Change:** Reproduced = Step 1 found a repeated id in real data. Steps 2 and 3 do not change the outcome. If reproduced, keep the Step 3 tests and go to Step 5. If not (no repeated id, or no usable 200 response from either endpoint, per A2), revert the Step 3 test edits with `git checkout -- <the two test files>` (do not commit failing tests) and go to Step 6.
- **Verification:** the decision and its evidence are recorded in the ticket's Implementation notes.

#### Step 5 (conditional, reproduced only): Dedupe by id in `sortModels`
- **Files:** `frontend/src/lib/model-options.ts` (modify `sortModels`; `modelSelectOptions` inherits it).
- **Change:** After sorting, keep the first entry per `id` (the best-ranked, since loaded sorts first). Update the `sortModels` doc comment ("Loaded models first, then loading, then the rest; ties sort by id.") to say it also drops repeated ids. Leave the misplaced "Options for the model picker (plan F-25)" block (lines 28-31, directly above the `sortModels` comment) unchanged. No component changes needed (`ModelsDialog` and `ChatSettingsModal` already go through these helpers). Keep the Step 3 tests as the regression tests.
- **Verification:** Step 3 tests pass; `npm run typecheck`, `npm run lint`, `npm run test` from `frontend/` pass (or `scripts/check.sh --frontend-only`).

#### Step 6 (conditional, not reproduced only): Close as not reproduced
- **Files:** the ticket only.
- **Change:** Record the evidence from Steps 1 to 3 in Implementation notes, tick the acceptance criterion via the "close as not reproduced" branch, and close the ticket with the `ticket` skill. No code change, no PR.
- **Verification:** ticket status is done with the evidence linked; `git status` in the implementation branch is clean.

### Tests
- New Vitest cases in `frontend/src/lib/model-options.test.ts` and `frontend/src/features/settings/ModelsDialog.test.tsx` (written in Step 3; kept or reverted by Step 4; on the reproduced branch they are the regression tests that fail without the fix).
- Run from `frontend/`: `npm run typecheck`, `npm run lint`, `npm run test`; or `scripts/check.sh --frontend-only`. No e2e spec: no new user flow.

### Risks and open questions
- **Live data may be unavailable:** then the outcome is "not reproduced" (A2). Mitigation: Step 2 records whether upstream could repeat ids; if it says "can repeat", the closing note says so explicitly so the ticket can be reopened when real data shows it.
- **Defensive fix without reproduction:** a one-line dedupe is cheap, but the ticket scopes it to real duplicates, so it is not planned for the not-reproduced branch.
- **Open question (non-blocking):** should a repeated id with conflicting statuses be shown as the best status (A3) or flagged? Default: best status.

### Success criteria
- [ ] Evidence for or against duplicate ids is recorded in the ticket (live data or "unreachable", upstream behaviour, failure-mode test result).
- [ ] Reproduced: `sortModels` dedupes by id, regression tests pass, frontend checks pass.
- [ ] Not reproduced: ticket closed as not reproduced, no code changes left behind.

### Validation log
- **Round 1:** validator FAIL (1 BLOCKING, 6 MINOR). My judgement: FAIL, BLOCKING valid. (1) valid: the decision rule let an upstream capability trigger the fix, but the Description scopes it to real data; A1, A2, Step 4 and Risks now make real data the only trigger. (2) valid: Step 2 now names the repo, path and outcome categories. (3) valid: Context reconciles e327094 with 6a13e04. (4) valid: Step 5 names the comment to edit. (5) valid: the Implementation note's "ChatSettingsModal keys by id" claim is corrected in Context (the note itself is left as earlier content). (6) valid: Step 1 got an explicit reachability check. (7) valid: Step 3, Step 4 and Tests now agree that Step 4 is the only keep-or-revert point.
- **Round 2 (diff-scoped):** validator PASS (0 BLOCKING, 3 MINOR); round-1 BLOCKING confirmed resolved. My judgement: PASS. (1) valid: `app.py` `require_auth` returns 401 when `APP_PASSWORD` is set; Step 1 now passes `-u` and records a 401 separately. (2) valid: the misplaced comment block is above `sortModels`; wording fixed. (3) valid: Step 2 now says where the version comes from and how the source is read.
- **Round 3 (diff-scoped):** validator FAIL (1 BLOCKING, 4 MINOR). My judgement: FAIL, BLOCKING valid. (1) valid: `-w '%{http_code}'` without `-o` appended the code to the JSON and broke jq; Step 1 rewritten to save the body with `-o` and capture the code. (2) valid: Step 2 now uses `?ref=`. (3) valid: Step 4 covers the 401 case. (4) valid: a 401 is recorded as "password missing or rejected". (5) valid: the fallback runs whenever the backend is not 200.
- **Round 4 (diff-scoped):** validator PASS (0 BLOCKING, 5 MINOR); round-3 BLOCKING confirmed resolved. My judgement: PASS; stopped per the after-round-3 rule. I applied the MINORs as small text edits without another round: (1) fallback status captured in `code2`; (2) and (3) `/props` is tried on every path, kept only on 200; (4) an unparseable 200 counts as "unusable response"; (5) A2 and Step 4 now say "no usable 200 response". All five were checked against the plan text and `app.py`.

## Implementation notes

### Autopilot run (2026-11-09)
Batch 7 item. Branch bugfix/model-option-keys (local only, no commits, no PR). Dirty files before start: none.

### Investigation (2026-11-09)
Evidence in `MYAI-14-evidence/investigation.md`.
- Live data: not queried (standing rule: never touch :5000/:5001 or live containers); by assumption A2 this means no usable 200, so the outcome is "not reproduced".
- Upstream: llama.cpp `tools/server/server-models.cpp` stores models in a name-keyed `mapping` and checks alias collisions, so `/v1/models` ids are unique by construction.
- Failure mode: feeding a repeated id to `modelSelectOptions` gives two options (test failed as expected; reverted, nothing committed).
Decision (plan Step 4/6): not reproduced; no code change. Reopen if a duplicate id ever appears in real `/api/models/` data; the one-line dedupe in `sortModels` is described in the plan.
Status on develop (checked at e327094, 2026-11-08): Key by id in ChatSettingsModal and ModelsDialog; no duplicate reproduced.

## Verification
Not run yet.

## Review history
None yet.

## Log
- 2026-11-08: created from reports/full-scope-final-report-2026-11-08.md
- 2026-11-09: plan validated, 4 rounds
- 2026-11-09: autopilot started (batch-autopilot)
- 2026-11-09: investigated: not reproduced (upstream ids unique by construction; live data not queried by rule); closed per plan Step 6, no PR
- 2026-11-09: batch-autopilot: closed as not reproduced, base develop
