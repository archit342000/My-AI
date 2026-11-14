---
id: MYAI-40
title: "Multi-user: per-user rate limits on turns and web search"
status: done
created: 2026-11-09
updated: 2026-11-10
links:
  blocks: [MYAI-42]
  blocked_by: [MYAI-7, MYAI-35]
  conflicts_with: [MYAI-36, MYAI-39]
  split_from: [MYAI-32]
---

## Description
Split from MYAI-32 (Step 8: Per-user rate limits). Part of making My-AI multi-user behind Cloudflare Access. Implement after MYAI-1 to MYAI-31 have merged.

Read the MYAI-32 Plan first: the Audit (single-user assumptions with file references), the Approach, the Decisions and the Reviewer brief are binding for this ticket. Step scope from MYAI-32:

- **Depends on:** MYAI-35
- **Files:** `backend/auth/rate_limit.py` (create): a fixed-window limiter keyed by `user_id`. `backend/config.py` (modify: `RATE_LIMIT_TURNS_PER_MINUTE`, `RATE_LIMIT_SEARCHES_PER_DAY`, `RATE_LIMIT_EXEMPT_ADMIN`). `backend/chat/router.py` (modify: `chat_completions`, `resume_chat`, checked before MYAI-7's turn claim). The Tavily call sites `backend/tools/agents/search_web_agent/agent.py`, `backend/tools/agents/research_agent/agent.py` and `backend/tools/agents/research_agent/research_utils.py` (modify: check the chat owner's search limit before each `tavily_client.execute_tool`). Tests for each.
- **Change:** as in Approach. Exceeding a limit gives 429 `{"error": ...}` and a `log_event`, with nothing written.
- **Verification:** unit tests for the window rollover and per-user independence; route tests for 429 on send and resume; the search tool returns a short `Error:` result when the limit is hit.

## Acceptance criteria
- [ ] Send and resume return 429 `{"error": ...}` when the caller's turn limit is exceeded, before the turn claim, with nothing written
- [ ] Tavily calls stop with a short `Error:` result once the chat owner's search limit is reached
- [ ] Limits are per user and set in `backend/config.py`; the admin exemption is configurable
- [ ] Tests pass and `ruff check .` is clean

## Plan
**Date:** 2026-11-09  **Status:** Validated

### Objective
Stop one user from exhausting shared inference and search capacity. Each user gets a limit on turn starts (send and resume) per minute and on web searches per day. Limits come from `backend/config.py`, apply per user, can exempt the admin, and answer with 429 (routes) or a short `Error:` result (search), with nothing written.

### Context
- **Requirement:** this ticket's Description and Acceptance criteria. MYAI-32 Plan: Approach "Rate limits", Step 8.
- **Assumes merged:**
  - MYAI-33: `current_user()` and `db.get_user`.
  - MYAI-35:
    - `chat_completions` order: validate `uploadedFiles`, then `claim_chat`, then `claim_turn`.
    - `resume_chat` checks the owner first.
    - `db.get_chat_owner`; the `login_as` fixture.
  - MYAI-38: the `gitMode` 403 helper in both routes.
  - MYAI-7 and MYAI-19: `claim_turn` in both routes. MYAI-7 Step 5 makes the React `consume` treat a 400 as a toast only.
- **Current code:**
  - `chat_completions` is at `backend/chat/router.py:247` and `resume_chat` at 446.
  - **Tavily is called in two places:**
    - `search_web_agent` flow (`backend/tools/agents/search_web_agent/agent.py:50-78`): a retry loop around `tavily_client.execute_tool("async_tavily_search_tool", ...)`. The flow has `chat_id` (28).
    - `ResearchAgent`'s search step (`backend/tools/agents/research_agent/agent.py:1196-1215`): a per-query loop calling `_execute_mcp_tool(tavily_client, "async_tavily_search_tool", ..., chat_id=self.chat_id)`, collecting `search_errors`.
  - The app runs as one process (MYAI-32 Context), so in-memory counters are process-wide.
  - React's `consume` (`frontend/src/features/chat/send-turn.ts`) interrupts on most errors; after MYAI-7, a 400 shows a toast only.
- **Rules:** `docs/standards/api.md` (short error bodies; status codes); `docs/standards/python.md` (shared state under a lock; config only in `backend/config.py`); `docs/standards/testing.md` (deterministic tests, no sleeps); `docs/standards/frontend.md`.

### Approach
- **`backend/auth/rate_limit.py` (new):** `FixedWindowLimiter(limit: int, window_seconds: int, clock=time.monotonic)`.
  - `try_acquire(key) -> tuple[bool, int]` returns whether the hit is allowed and the seconds until the window resets.
  - It holds per-key `(window_start, count)` under a `threading.Lock`. A denied attempt doesn't count. `limit <= 0` means unlimited.
  - Module singletons: `turn_limiter` (`RATE_LIMIT_TURNS_PER_MINUTE`, 60 s) and `search_limiter` (`RATE_LIMIT_SEARCHES_PER_DAY`, 86 400 s).
  - `is_exempt(user: dict)` is true when `user["role"] == "admin"` and `RATE_LIMIT_EXEMPT_ADMIN`. Callers key the limiter on `user["id"]`.
  - `reset_limiters()` clears both singletons, for tests. An autouse fixture added to `backend/conftest.py` (created by MYAI-35) calls it before each test, so limiter state never leaks between tests.
  - Fixed windows were chosen for simplicity, since bursts at a window edge are acceptable at this scale.
- **Config (`backend/config.py`):** `RATE_LIMIT_TURNS_PER_MINUTE` (default 10), `RATE_LIMIT_SEARCHES_PER_DAY` (default 200), `RATE_LIMIT_EXEMPT_ADMIN` (default True). They're read in the file's existing non-secret style: `int(os.getenv(...))` and `os.getenv(...).lower() == "true"`, as for `PLAYWRIGHT_HEADLESS`.
- **Turn limit in routes**, with `user = current_user()`:
  - **Exact position in `chat_completions`:** after MYAI-38's `gitMode` check and before `uploadedFiles` validation and `claim_chat` (which writes the chat row), so a 429 writes nothing. MYAI-35 replaces today's `db.ensure_chat_exists(chat_id)` (`router.py:268`, the current first write) with `claim_chat` at that later position (MYAI-35 Approach, "Chat router"). So once MYAI-35 has merged, no write comes before this check.
  - **Exact position in `resume_chat`:** after MYAI-35's owner check (a read) and MYAI-38's `gitMode` check, and before `claim_turn`.
  - So a foreign chat id costs a turn hit in completions (the ownership check there is `claim_chat`, which must stay after the limit), but not in resume (rejected first). That's accepted.
  - The router imports the module (`from backend.auth import rate_limit`) and calls `rate_limit.turn_limiter.try_acquire(...)` and `rate_limit.is_exempt(...)` through it, so the singleton is read at call time and a test's `patch.object(rate_limit, "turn_limiter", ...)` takes effect.
  - Order: first, with no current user (which MYAI-33's hook rules out), return 401 `{"error": "Unauthorized"}` (fail closed). That deliberately differs from MYAI-35's 404: no resource is being looked up here, so "not authenticated" is the accurate status. Then, unless `is_exempt(user)`, call `rate_limit.turn_limiter.try_acquire(user["id"])`.
  - On deny: 429 `{"error": "Too many requests; try again shortly."}` with a `Retry-After` header and `log_event("rate_limited", {"kind": "turns"})`. A foreign chat id still costs the caller a turn hit; that's accepted, since the check must come before the write in `claim_chat`.
- **Search limit:**
  - New helper `check_search_limit(chat_id) -> Optional[str]` in `backend/auth/rate_limit.py`. It resolves the chat owner (`db.get_chat_owner`, then `db.get_user` for the role) and returns None when allowed. Otherwise it returns `"Error: Daily web search limit reached."` and logs `rate_limited` with `kind="searches"`. With no owner, it returns the same error (fail closed).
  - The search result follows the ticket's criterion ("a short `Error:` result"), not MYAI-32's 429, which applies to routes only.
  - `search_web_agent` calls it once after its "Search Web Agent Started." message is written (`agent.py:40-50`) and before its retry loop (one search = one hit, not one per retry). On a message it returns early, emitting the same kind of failure event and yield as its post-loop failure path (`agent.py:79` onwards), but with exactly `Error: Daily web search limit reached.` as the message, and it sets `agent.result` to that message as the post-loop path does. It skips the "Search failed after N attempts" wrapper and makes no Tavily call.
  - `ResearchAgent._execute_internal_searches` calls it before each query, placed before the per-query `try:` (`agent.py:1204`), so the generic `except Exception` (1238) that appends to `search_errors` and continues can't swallow it. On a message, it raises a new `SearchLimitReached` exception (defined in `rate_limit.py`).
    - The section caller's initial-search loop (`agent.py:809-828`) gets an `except SearchLimitReached: raise` ahead of its generic `except Exception as search_err:`. It doesn't retry, and the outer section handler (`agent.py:788-790`) emits its usual `Section {idx} failed: <message>. Research halted.` line with the limit text as the message, instead of "returned zero usable results".
    - The follow-up gap search (`_execute_internal_searches(..., is_followup=True)`, `agent.py:877`) isn't in a `try`. There, `SearchLimitReached` is caught around that one await. The block then falls through to its normal tail: it writes the `followup_searches` collection with no new results and emits `EVENT_GAP_SEARCHES_DONE`, then reaches the state machine's `continue` (`agent.py:865-895`). `_parse_section_state` then sees the gap searches as done, so the section moves on with the results it already has instead of re-entering that state. It logs `rate_limited`, and the limit doesn't halt the whole research run.
  - `research_utils.py`, named in MYAI-32 and the ticket, has no Tavily call of its own (it only defines the generic `_execute_mcp_tool`), so it's deliberately not changed.
- **Frontend:** `consume` handles `ApiError` status 429 (imported from `frontend/src/api/client.ts`, as MYAI-7 Step 5 does; its `status` field) the same way as MYAI-7's 400: a toast with the server message, no interrupt (nothing was stored).
- **Rejected:**
  - Flask-Limiter: a new dependency for two counters.
  - Token-based inference limits: they need usage accounting the app doesn't do; turn starts are the cost driver.
  - Persisting counters in SQLite: a restart resetting the window is acceptable.

### Out of scope
Limits on other endpoints (uploads, file systems); per-user quotas on tokens or storage; admin UI for limits.

### Steps
#### Step 1: Limiter and config
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/auth/rate_limit.py` (create); `backend/auth/tests/test_rate_limit.py` (create; `backend/auth/__init__.py` and `backend/auth/tests/__init__.py` exist from MYAI-33); `backend/conftest.py` (modify: autouse `reset_limiters`); `backend/config.py` (modify); `backend/tests/test_config.py` (modify).
- **Change:** as in Approach.
- **Verification:** with an injected fake clock (no sleeps):
  - The limit is enforced and resets at the window boundary.
  - Keys are independent.
  - Denied attempts don't count.
  - `limit=0` is unlimited.
  - `Retry-After` seconds are correct.
  - The admin exemption is honoured.
  - `check_search_limit` returns the message when exhausted and for a missing owner.

#### Step 2: Routes
- **Status:** todo
- **Depends on:** 1
- **Files:** `backend/chat/router.py` (modify): `chat_completions`, `resume_chat`. `backend/chat/tests/test_router.py` (modify).
- **Change:** as in Approach.
- **Verification:**
  - Tests replace the module singleton with `patch.object(rate_limit, "turn_limiter", FixedWindowLimiter(1, 60, clock=fake_clock))`, which is restored after the test. With that limit of 1, the second send by a user gets 429 with `Retry-After`, and `claim_chat`, `claim_turn` and the message write aren't called. The same holds for resume.
  - Another user still gets through.
  - The admin isn't limited when exempt.
  - The existing route tests still pass (they log in through `login_as`, and the autouse reset keeps counters clean).

#### Step 3: Search call sites
- **Status:** todo
- **Depends on:** 1
- **Files:** `backend/tools/agents/search_web_agent/agent.py`, `backend/tools/agents/research_agent/agent.py` (modify). `backend/tools/agents/search_web_agent/tests/test_agent.py`, `backend/tools/agents/research_agent/tests/test_agent.py` (modify). Their existing tests use chats with no owner (for example `"test_chat"`), so the fixtures patch the imported names `backend.tools.agents.search_web_agent.agent.check_search_limit` and `backend.tools.agents.research_agent.agent.check_search_limit` to return None for the existing success-path tests, and new tests patch them to return the message.
- **Change:** as in Approach.
- **Verification:**
  - With a mocked `tavily_client`, an exhausted limit means `execute_tool` isn't called and the agent result carries the limit message.
  - A search that needs retries counts as one hit.
  - The research step raises `SearchLimitReached` at the first denied query, the section isn't retried (the patched search is called once), and the section's failure message is the limit message. A limit reached during the follow-up gap search keeps the section's earlier results. The section reaches its next state (the gap-search DONE event is emitted once), and the patched limit check is called exactly once for that state, which shows there's no re-entry loop. The test seeds the section history with the initial-search and reflection DONE events, so it starts at the gap-search state.
  - Existing search and research tests still pass.

#### Step 4: Frontend 429
- **Status:** todo
- **Depends on:** none (needs MYAI-7's `ApiError` branch in `consume`, assumed merged)
- **Files:** `frontend/src/features/chat/send-turn.ts` (modify): `consume`. `frontend/src/features/chat/send-turn.test.ts` (modify; created by MYAI-6 and MYAI-7).
- **Change:** as in Approach.
- **Verification:** a 429 `ApiError` shows the toast and doesn't call `interrupt`; `npm run typecheck`, `lint` and `test` pass.

#### Step 5: Docs and full gate
- **Status:** todo
- **Depends on:** 2, 3, 4
- **Files:** `docs/standards/api.md` (modify: add 429 to the status codes, with `Retry-After`); `docs/standards/security.md` (modify: one line on per-user limits); `backend/auth/README.md` (modify: `rate_limit.py` row); `backend/chat/README.md`, `backend/tools/agents/search_web_agent/README.md`, `backend/tools/agents/research_agent/README.md` (modify: one line each on the limit); `README.md` (check only; the limits are documented in `backend/auth/README.md`, keeping the root README within budget).
- **Change:** docs match the code.
- **Verification:** with the env from `docs/standards/testing.md`: `pytest backend/auth`, `backend/chat`, `backend/tools`, `tests`, then `pytest backend`; the frontend checks; `ruff check .`.

### Tests
Covered per step, using a fake clock and patched limits.

### Risks and open questions
- **Counters reset on restart** and aren't shared across processes; that's fine for the single-process app.
- **Long research turns can use many searches;** the default of 200 a day may need tuning. It's a config value.

### Success criteria
- [ ] Send and resume give 429 with `Retry-After` when a user exceeds the turn limit, before any write.
- [ ] Web searches stop with `Error: Daily web search limit reached.` once the chat owner's limit is reached; a retried search counts once.
- [ ] Limits are per user and set in `backend/config.py`, and the admin exemption is configurable.
- [ ] React shows a 429 as a toast without interrupting.
- [ ] Tests pass and `ruff check .` is clean.

### Reviewer brief
- **Objective:** per-user limits on turn starts (send and resume) per minute and on web searches per day. Routes answer 429 with `Retry-After`; searches return `Error: Daily web search limit reached.`; nothing is written when limited.
- **Key decisions:**
  - `backend/auth/rate_limit.py`: an in-memory `FixedWindowLimiter` with an injectable clock; `turn_limiter` and `search_limiter` singletons; `is_exempt(user)` (admin, configurable); `reset_limiters()` with an autouse fixture in `backend/conftest.py`; `check_search_limit(chat_id)` keyed on the chat owner (fails closed); `SearchLimitReached`.
  - Config uses the file's existing `os.getenv` style.
  - Routes call `rate_limit.turn_limiter` through the module: in completions before `uploadedFiles` validation and `claim_chat`, in resume after the owner check and before `claim_turn`. No user gives 401.
  - `search_web` checks once before its retry loop and returns early with the exact message, setting `agent.result`.
  - Research: the check sits before the per-query `try`. `SearchLimitReached` isn't retried for initial searches; follow-up gap searches catch it and fall through to their DONE event.
  - `research_utils.py` is left unchanged, since it has no Tavily call.
  - React shows a 429 as a toast.
- **Out of scope:** limits on other endpoints, token or storage quotas, an admin UI.
- **Success criteria:** as listed in the Plan.

The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- **Round 1:** the validator returned FAIL (4 BLOCKING, 6 MINOR). My judgement: FAIL.
  - All four BLOCKING issues were valid and fixed:
    - The insertion point was ambiguous, so the exact positions are now spelled out.
    - The `search_web` error came out wrapped, so there's an early return with the exact message.
    - The existing ownerless tests needed `check_search_limit` patched.
    - Singleton reset and the None-key behaviour were defined.
  - MINOR, fixed: research retry burn (`SearchLimitReached`); `research_utils` explained; config style and the `is_exempt` signature; READMEs; dependencies noted; the ticket's criterion cited for the search result.
- **Round 2 (diff-scoped):** the validator returned FAIL (1 BLOCKING, 6 MINOR). My judgement: FAIL.
  - BLOCKING, valid: the per-query generic `except` would swallow the exception. The check is now before the `try`.
  - MINOR, fixed: re-raise in the section caller; gap-search behaviour; patch targets; 401 before `is_exempt`; singleton patching; position relative to the "Started" write.
- **Round 3 (diff-scoped):** the validator returned FAIL (2 BLOCKING, 1 MINOR). My judgement: FAIL.
  - Valid and fixed: the gap-search catch could re-enter its state forever (it now falls through to the DONE event); a name import would defeat `patch.object` (the router now calls through the module).
  - MINOR: the MYAI-35 `ensure_chat_exists` replacement is noted.
- **Round 4 (diff-scoped):** the validator returned PASS (0 BLOCKING, 4 MINOR). My judgement: PASS. MINOR, fixed: `agent.result` set on the early return; the real section failure format; the 401 versus 404 rationale; test seeding for the gap-search state.

## Implementation notes
### Autopilot run (2026-11-09)
batch-autopilot item 10/13; branch feature/multi-user-rate-limits, base feature/multi-user-browser-profiles-portal (stacked on the MYAI-39 PR); no pre-existing dirty files.

### Baseline (2026-11-09)
backend+tests: 10 failed (async-plugin: test_cache_system 2, test_research_utils 2, test_code_executor 6), rest pass.

### Implementation progress
- [x] Step 1: Limiter and config - backend/auth/rate_limit.py, backend/auth/tests/test_rate_limit.py, backend/conftest.py (autouse reset), backend/config.py, backend/tests/test_config.py
- [x] Step 2: Routes - backend/chat/router.py (`_turn_rate_limited`, after the git-mode check, before file checks and `claim_chat`; resume before `claim_turn`), backend/chat/tests/test_router.py. Deviation: `chat_completions` already rejects a foreign chat id with 404 before the git-mode check (MYAI-37/38 order), so a foreign id never spends a turn hit there either (better than the plan's accepted cost).
- [x] Step 3: Search call sites - search_web_agent/agent.py, research_agent/agent.py (+tests; autouse patch of `check_search_limit` in both test files)
- [x] Step 4: Frontend 429 - frontend/src/features/chat/send-turn.ts (+test)
- [x] Step 5: Docs - docs/standards/api.md, security.md, backend/auth, chat, search_web_agent, research_agent READMEs
- Branch: feature/multi-user-rate-limits (base feature/multi-user-browser-profiles-portal)

### Smoke test (2026-11-09)
backend+tests: 10 failed (identical baseline), 1633 passed. frontend: typecheck, lint clean; vitest 316 passed. ruff clean. scripts/check.sh --python-only: ruff pass, same pre-existing failures.
PR: https://github.com/archit342000/My-AI/pull/93, branch feature/multi-user-rate-limits, base feature/multi-user-browser-profiles-portal

## Verification

### Verification plan and results (2026-11-09)
Live on the real app (throwaway DATA_DIR, signed JWTs, RATE_LIMIT_TURNS_PER_MINUTE=2; evidence MYAI-40-evidence/drive.out): V1 bob's 3rd turn in the window is 429 (200,200,429): PASS. V2 body and Retry-After (58): PASS. V3 the refused turn wrote nothing (no bob-chat-3 in his chats): PASS. V4 resume shares the count: 429: PASS. V5 alice (admin, exempt) 5 turns never limited: PASS. V6 unknown user 403: PASS. V7 bob's other API unaffected: PASS.
BLOCKED live: the Tavily search limit (needs the Tavily service); covered by unit tests with a mocked client (message, no Tavily call, one hit for retries, research halt/skip behaviour).

## Review history
### Round 1 - 2026-11-09
Verdict: Request changes (one Haiku reviewer; diff ~400 lines). Resolution: fixing 4, rejecting 2. Checks: backend+tests 10 failed (baseline) / 1633 passed; frontend 316 passed, typecheck and lint clean; ruff clean.
- R1-1 [MAJOR] research_agent/agent.py:814 - an initial-search limit halts the whole research run with a nested message - Rejected: this is the validated plan (the section fails with the limit message as `Section N failed: <msg>. Research halted.`; `flow_fn` wraps it in its usual failure text); containing it to one section would let a limited user keep running other sections.
- R1-2 [MAJOR] research section retry charges the same queries again - Rejected: the plan checks before each query, each query is a real Tavily call, and "a retried search counts once" is the `search_web` retry loop (one hit, tested); documented in the research README.
- R1-3 [MINOR] research README said "halts the section" - Fixed.
- R1-4 [NIT] clock read outside the lock - Fixed.
- R1-5 [NIT] docs did not say a later 400 has already spent a turn - Fixed (api.md).
- R1-6 [NIT] gap-search batch results dropped on a limit - Fixed by documenting it (research README).

## Log
- 2026-11-09: created (split from MYAI-32 Step 8)
- 2026-11-09: linked split_from MYAI-32 (Step 8)
- 2026-11-09: linked blocked_by MYAI-35
- 2026-11-09: linked blocked_by MYAI-7
- 2026-11-09: linked blocks MYAI-42
- 2026-11-09: linked conflicts_with MYAI-36 (shared files per MYAI-32 Steps intro)
- 2026-11-09: linked conflicts_with MYAI-39 (shared files per MYAI-32 Steps intro)
- 2026-11-09: plan validated, 4 rounds
- 2026-11-09 batch-autopilot: shipped https://github.com/archit342000/My-AI/pull/93, base feature/multi-user-browser-profiles-portal
- 2026-11-10: closed (merged into develop via the PR recorded in Implementation notes; deployed to myai.architanand.dev)
