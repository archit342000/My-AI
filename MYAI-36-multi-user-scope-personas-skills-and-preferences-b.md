---
id: MYAI-36
title: "Multi-user: scope personas, skills and preferences by owner"
status: done
created: 2026-11-09
updated: 2026-11-10
links:
  blocks: [MYAI-42]
  blocked_by: [MYAI-9, MYAI-34]
  conflicts_with: [MYAI-35, MYAI-37, MYAI-38, MYAI-39, MYAI-40]
  split_from: [MYAI-32]
---

## Description
Split from MYAI-32 (Step 4: Scope personas, skills and preferences). Part of making My-AI multi-user behind Cloudflare Access. Implement after MYAI-1 to MYAI-31 have merged.

Read the MYAI-32 Plan first: the Audit (single-user assumptions with file references), the Approach, the Decisions and the Reviewer brief are binding for this ticket. Step scope from MYAI-32:

- **Depends on:** MYAI-34
- **Files:** `backend/database/wrapper/persona_ops.py`, `skill_ops.py`, `preference_ops.py` (modify: `user_id` everywhere, per-user default persona, `persona_name_exists`). `backend/chat/router.py` (modify: personas and skills routes). `backend/tools/router.py` (modify: preference routes). `backend/chat/tool_handler.py` (modify): `user_id` in `system_ctx` from the chat owner. `backend/tools/preferences.py`, `backend/tools/skills_tool.py` (modify: take `user_id`). `backend/chat/handler.py` (modify): per-user preferences and skills in the prompt. Tests for each.
- **Change:** as in Approach.
- **Verification:** two-user tests: route CRUD, the preference tools and `use_skill` see only the owner's rows; the prompt for user B contains none of user A's preferences or skills; the same skill name can exist for two users.

## Acceptance criteria
- [x] Persona, skill and preference routes list and change only the caller's rows; another user's id gives 404 (tested per route)
- [x] The default persona is per user; the same skill name can exist for two users
- [x] The preference tools and `use_skill` act only on the chat owner's rows (`user_id` comes from `ToolHandler`, never from model arguments)
- [x] The prompt for user B contains none of user A's preferences or skills
- [x] Tests pass and `ruff check .` is clean

## Plan
**Date:** 2026-11-09  **Status:** Validated

### Objective
Make personas, skills and preferences (the `memories` table) per user, on every path: the REST routes, the model tools (`add`/`edit`/`delete_user_preference`, `get_skill_details`), prompt assembly, the per-user default persona, and the `persona_id` and `folder` values a chat can be pointed at.

### Context
- **Requirement:** this ticket's Description and Acceptance criteria. MYAI-32 Plan: Audit items 3 and 6, Step 4.
- **Assumes merged:**
  - MYAI-33: `current_user_id()`.
  - MYAI-34: `user_id` on `personas`, `skills` and `memories`; skills unique on `(user_id, name)`.
  - MYAI-35:
    - `db.get_chat_owner` and `require_workspace_owner`.
    - The `backend/conftest.py` fixtures `user_a`, `user_b`, `two_users` and `login_as`.
    - Every chat route checks ownership first.
    - Generators run without the user context, so code on the turn path uses the chat owner.
  - MYAI-9: `persona_name_exists(name, exclude_id=None)`.
  - MYAI-11 and MYAI-22: preference delete and update return 404 when the wrapper returns False.
  - MYAI-22: routes read bodies with `read_json_object`.
- **Current code:**
  - **`PersonaOperations`** (`backend/database/wrapper/persona_ops.py`):
    - `get_all_personas()` (22), `get_persona(id)` (29), `get_default_persona()` (36).
    - `create_persona(...)` (43) and `update_persona(...)` (78) both run `UPDATE personas SET is_default = 0` across all rows when the default is set (57, 88).
    - `delete_persona(id)` (98).
  - **`SkillOpsMixin`** (`skill_ops.py`):
    - `add_skill(skill_id, name, description, instructions)` (14) is an upsert with `ON CONFLICT(id) DO UPDATE`, and the PUT route reuses it.
    - `get_skill` (48), `get_skill_by_name` (62), `get_all_skills` (76), `delete_skill` (89).
  - **`PreferenceOpsMixin`** (`preference_ops.py`): `get_all_preferences()` (13), `add_preference(content, tag)` (30), `update_preference(id, content, tag)` (53), `delete_preference(id)` (77), `clear_preferences()` (100).
  - **Routes:**
    - The persona routes (`backend/chat/router.py:609-662`) and skill routes (668-735).
    - The preference routes in `backend/tools/router.py:96-145`.
  - **Model tools:**
    - `backend/tools/preferences.py`: `add_user_preference`, `edit_user_preference`, `delete_user_preference`, each taking `**kwargs`.
    - `backend/tools/skills_tool.py`: `get_skill_details(skill_name, **kwargs)`.
    - `ToolHandler._execute_pure_tool` (`backend/chat/tool_handler.py:265-300`) injects `system_ctx` (chat id, parent ids, tool call id) into tools that accept it. `ToolHandler.__init__` is at 18.
  - **Turn path:**
    - `ChatHandler.initiate_chat` syncs request kwargs into the chat: `folder` becomes `workspace_id` (`backend/chat/handler.py:132-133`), and `persona_id` takes a persona snapshot through `db.get_persona` (135-147).
    - The prompt uses `db.get_all_preferences()` and `db.get_all_skills()` (306-310).
    - `PromptBuilder.persona_content` falls back to `db.get_persona(persona_id)` (`backend/chat/prompt_builder.py:34-45`).
    - `save_chat_endpoint` stores `persona_id` unchecked (`router.py:110`).
    - The `folder` path bypasses MYAI-35's `workspace_id` checks, which cover only save and patch.
- **Rules:** `docs/standards/api.md` (personas and skills keep the `{"success": false, "error": ...}` shape); `docs/standards/testing.md`; `AGENTS.md` 4 and 5.

### Approach
- **Wrapper:** `user_id` is a required positional parameter (no default; empty raises `ValueError`) on every persona, skill and preference method.
  - Reads add `WHERE user_id = ?`.
  - Single-row updates and deletes add `AND user_id = ?` and return False when no row matched, so foreign ids behave as "not found".
  - `create_persona` and `update_persona` clear `is_default` only within the user, so the default is per user.
  - `update_persona` runs the target `UPDATE ... WHERE id = ? AND user_id = ?` first and returns that statement's `cursor.rowcount > 0`, not `conn.total_changes`. Only when it matched and `is_default == 1` does it clear the user's other defaults (`UPDATE personas SET is_default = 0 WHERE user_id = ? AND id != ?`). A foreign id therefore changes nothing and returns False.
  - `add_skill(skill_id, name, description, instructions, user_id)`: the insert stores `user_id`. The conflict branch updates only when the existing row has the same owner (`ON CONFLICT(id) DO UPDATE ... WHERE skills.user_id = excluded.user_id`), and returns False when nothing was written, so a foreign id can't be taken over. "Nothing written" is `c.rowcount == 0`, read right after the `INSERT` and before the existing `COMMIT`; the `COMMIT`/`ROLLBACK` handling is unchanged. A same-owner name clash still raises `IntegrityError`, which the routes already catch.
  - `persona_name_exists(name, user_id, exclude_id=None)`.
- **Routes:** every persona, skill and preference route passes `current_user_id()`. A foreign id behaves exactly like a missing one, using each route's 404 shape. For preference update and delete, that's the 404 that MYAI-22 and MYAI-11 add (today they return 500). MYAI-9's `persona_name_exists` calls in `create_persona` and `update_persona` pass the caller's id.
- **Model tools:**
  - `ToolHandler.__init__` resolves `self.user_id = db.get_chat_owner(chat_id)` once, and `system_ctx` gains `user_id`.
  - The ticket's "`use_skill`" is the `get_skill_details` tool (`backend/tools/skills_tool.py:11`); there's no tool named `use_skill`.
  - The preference tools and `get_skill_details` take `user_id` as a keyword argument and pass it to the wrapper. They declare it in their signatures, so injection works even without `**kwargs` filtering.
  - With no `user_id` (no owner, which shouldn't happen after MYAI-35), the tools return `Error: ...` and log `tool_missing_owner`.
  - The model can't supply `user_id`: `system_ctx` is merged after the model's arguments (`{**args, **system_ctx}`), so it overrides any model value, and the tool schemas don't declare it.
- **Turn path:**
  - In `ChatHandler.initiate_chat`, the owner (`db.get_chat_owner(self.chat_id)`) is fetched once.
  - A falsy `persona_id` (None or empty) passes through unchanged, so a chat can still clear its persona (`handler.py:135-137`; the frontend sends `persona_id: o.personaId`). A truthy `persona_id` kwarg is applied only if the owner owns it (`db.get_persona(persona_id, owner)`). Otherwise it's ignored and logged (`chat_foreign_persona_ignored`), with no snapshot.
  - A falsy `folder` (empty string) passes through unchanged as today (`handler.py:132` applies any non-None value), so a chat can leave its workspace. A truthy `folder` is applied only if `db.get_workspace_owner(folder)` equals the owner. Otherwise it's ignored and logged (`chat_foreign_workspace_ignored`).
  - Ignoring rather than failing keeps the streaming contract: the generator has already started, so it can't return 404.
  - The prompt uses `db.get_all_preferences(owner)` and `db.get_all_skills(owner)`.
  - `PromptBuilder.persona_content` gets the owner from `chat_metadata["user_id"]` (added by MYAI-34) for its fallback lookup.
- **`save_chat_endpoint`:** a truthy `persona_id` that isn't the caller's gives 404 `{"error": "Persona not found"}` before the save. That's the chat routes' plain error shape (`save_chat_endpoint` already returns `{"error": ...}`); the `success` shape belongs to the persona and skill routes. A falsy one is saved as today.
- **Rejected:**
  - Rejecting a foreign `persona_id` or `folder` in the handler with an exception: it breaks the SSE stream mid-flight. The route-level checks (save, and MYAI-35's patch) already return 404 for direct writes.
  - Letting the model pass `user_id`: it must come from the server.

### Out of scope
Chat and workspace routes (MYAI-35, except the `persona_id` check in `save_chat_endpoint` and the handler kwargs above); file, RAG and code-execution scoping (MYAI-37); git and admin tools (MYAI-38).

### Steps
#### Step 1: Persona wrapper
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/database/wrapper/persona_ops.py` (modify), `backend/database/wrapper/tests/test_persona_ops.py` (modify), `backend/database/wrapper/tests/test_chat_ops.py` (modify: its persona calls pass an owner). A grep of callers of the changed persona, skill and preference methods finds only the files named in Steps 1-5, plus `backend/chat/tests/test_skills_inference.py` (mocks only; Step 5).
- **Change:** as in Approach. Steps 1 and 2 change wrapper signatures, so callers outside the wrapper are red until Steps 3-5 land. Steps 1-5 merge together, and each step's verification runs only its own tests; the full gate is Step 6.
- **Verification:**
  - Two owners on a temp DB: lists, get and default are per user.
  - Setting user a's default leaves user b's default.
  - Update and delete of a foreign id return False and change nothing, including when the foreign persona is a default and the caller has a default of their own.
  - Name checks are per user.

#### Step 2: Skill and preference wrappers
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/database/wrapper/skill_ops.py`, `preference_ops.py` (modify); `backend/database/wrapper/tests/test_skill_ops.py`, `test_preference_ops.py` (modify).
- **Change:** as in Approach.
- **Verification:**
  - The same skill name is allowed for two users, and a duplicate name for one user raises `IntegrityError`.
  - `add_skill` with a foreign id returns False and leaves the row unchanged.
  - `get_skill_by_name` is per user.
  - Preference CRUD and `clear_preferences(user_a)` leave user b's rows.

#### Step 3: Routes
- **Status:** todo
- **Depends on:** 1, 2
- **Files:** `backend/chat/router.py` (modify): persona and skill routes, and `persona_id` in `save_chat_endpoint`. `backend/tools/router.py` (modify): preference routes. `backend/chat/tests/test_router.py`, `backend/tools/tests/test_router.py` (modify): log in through `login_as`; add two-user tests.
- **Change:** as in Approach. The skill PUT treats a False from `add_skill` as 404.
- **Verification:** for each persona, skill and preference route, user b gets 404 (or the empty list) for user a's data, and the wrapper is called with `user_b`'s id. Save with a foreign `persona_id` gives 404 and doesn't call `save_chat`.

#### Step 4: Tools
- **Status:** todo
- **Depends on:** 2
- **Files:** `backend/chat/tool_handler.py` (modify): `__init__` and `system_ctx`. `backend/tools/preferences.py`, `backend/tools/skills_tool.py` (modify). `backend/chat/tests/test_tool_handler.py`, `backend/tools/tests/test_preferences.py`, `backend/tools/tests/test_skills_tool.py` (modify).
- **Change:** as in Approach. `ToolHandler.__init__` now calls `db.get_chat_owner`, so the existing `test_tool_handler.py` tests patch `backend.chat.tool_handler.db.get_chat_owner` (or the module's `db`) to return `user_a`'s id.
- **Verification:**
  - `_execute_pure_tool` passes the chat owner's id even when the model's arguments include `user_id`.
  - The preference tools list and change only the owner's rows.
  - `get_skill_details` doesn't find another user's skill.
  - A missing owner returns an `Error:` string.

#### Step 5: Turn path
- **Status:** todo
- **Depends on:** 1, 2
- **Files:** `backend/chat/handler.py` (modify): the kwargs sync block and the prompt context. `backend/chat/prompt_builder.py` (modify): `persona_content`. `backend/chat/tests/test_handler.py`, `test_prompt_builder.py`, `test_skills_inference.py` (modify: its `get_all_skills` mocks assert they're called with the chat owner).
- **Change:** as in Approach.
- **Verification:**
  - The prompt for user b's chat contains none of user a's preferences or skills.
  - A foreign `persona_id` leaves `persona_id` and `persona_snapshot` unchanged and logs the event.
  - A foreign `folder` leaves `workspace_id` unchanged.
  - An own persona and folder apply as before.

#### Step 6: Docs and full gate
- **Status:** todo
- **Depends on:** 3, 4, 5
- **Files:** `backend/database/wrapper/README.md` (modify: persona, skill and preference rows are per user); `backend/tools/README.md` (modify: tools receive `user_id` from the server, never from the model); `docs/tools.md` (modify: one line saying tools that touch user data take `user_id` from `system_ctx`).
- **Change:** docs match the code.
- **Verification:** with the env from `docs/standards/testing.md`: `pytest backend/database`, `backend/chat`, `backend/tools`, then `pytest backend`, `pytest tests`; `ruff check .`.

### Tests
Covered per step; two-user tests assert both the status or result and the absence of writes to the other user's rows.

### Risks and open questions
- **`PromptBuilder` relies on `chat_metadata` including `user_id`.** `get_chat` returns `SELECT *`, so the column appears after MYAI-34; Step 5 tests assert it.
- **A model-chosen `skill_name` from another user** just fails as "not found". No cross-user leak, since the lookup is scoped.

### Success criteria
- [x] Persona, skill and preference routes act only on the caller's rows; foreign ids give 404.
- [x] The default persona and skill-name uniqueness are per user.
- [x] The preference tools and `get_skill_details` use the server-provided owner, never a model value.
- [x] Prompts include only the chat owner's preferences and skills; foreign `persona_id` and `folder` values are ignored on the turn path and rejected on save.
- [x] Tests pass and `ruff check .` is clean.

### Reviewer brief
- **Objective:** make personas, skills and preferences per user across routes, model tools, prompt assembly, the default persona, and the `persona_id` and `folder` a chat can point at.
- **Key decisions:**
  - Required `user_id` on every persona, skill and preference wrapper method. Foreign ids act as not found.
  - `update_persona` runs the target update first and uses its `rowcount`; the default is cleared per user, only after a match.
  - `add_skill` is an upsert guarded by `WHERE skills.user_id = excluded.user_id`, with `rowcount == 0` meaning False.
  - Routes pass `current_user_id()`. `persona_name_exists` gets the caller's id.
  - `ToolHandler` resolves the chat owner once and injects `user_id` through `system_ctx`, which overrides any model-supplied value. The preference tools and `get_skill_details` (the ticket's "`use_skill`") use it.
  - On the turn path the owner comes from the chat. A truthy foreign `persona_id` or `folder` is ignored and logged; a falsy one passes through. Prompts use only the owner's preferences and skills. `save_chat_endpoint` gives 404 for a truthy foreign `persona_id`.
  - Steps 1-5 merge together; Step 6 is the full gate.
- **Out of scope:** chat and workspace routes (MYAI-35), file, RAG and code scoping (MYAI-37), admin tools (MYAI-38).
- **Success criteria:** as listed in the Plan.

The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- **Round 1:** the validator returned FAIL (2 BLOCKING, 7 MINOR). My judgement: FAIL.
  - Both BLOCKING issues were valid and fixed:
    - `update_persona` with `total_changes` and the clear-first order could return True for a foreign id. Now it's target-first and uses `rowcount`.
    - Ownership checks would reject a null `persona_id`. Falsy values now pass through.
  - The MINOR issues, all valid and fixed: `add_skill` `rowcount` detection; the preference 404 depends on MYAI-11 and MYAI-22; the `use_skill` to `get_skill_details` mapping; Steps 1-5 merge together; `test_skills_inference.py` added; `persona_name_exists` callers named; `test_tool_handler` patches `get_chat_owner`.
- **Round 2 (diff-scoped):** the validator returned PASS (0 BLOCKING, 2 MINOR). My judgement: PASS. MINOR, fixed: a falsy `folder` passes through; the 404 body shape for chat routes stated.

## Implementation notes
### Autopilot run (2026-11-09)
- Mode: automatic (batch-autopilot item 6/13)
- Branch: feature/multi-user-scope-personas-skills  PR base: feature/multi-user-scope-chats-by-owner (stacked on MYAI-35's PR #88; chain: #84 > #87 > #88)  Starting commit: 344f70d77e6c4732136aec583104f3af4562bc6d
- Dirty before start: none
- Work files: backend/database/wrapper/{persona,skill,preference}_ops.py, backend/chat/{router,handler,prompt_builder,tool_handler}.py, backend/tools/{router,preferences,skills_tool}.py, docs, tests
- Counters: fix 0/10, review 1/5, re-verify 1
- Last completed stage: 5 review (clean)  Next: done (shipped)
- Hard blocker: none
- WIP commit: none

### Autopilot decisions (2026-11-09)
- Plan already validated (2 rounds); stage 1 skipped.
- Stacked on the MYAI-35 branch (blocked_by 34; chain stacking puts 36 after 35 so MYAI-42 has one base).
- Deviation: `ToolHandler.user_id` is a lazy property (read from the db on first use, then kept) instead of being read in `__init__`: every `ChatHandler` builds a `ToolHandler`, and the Plan's eager read would have put a db access into every handler construction (and into ~30 tests). Behaviour is the same: resolved once, injected through `system_ctx`.
- Decision: `user_id` is placed right after the required arguments (`create_persona(name, content, user_id, ...)`, `update_persona(id, name, content, user_id, ...)`) and last on the others; all callers are updated and an empty value raises `ValueError`.
- Note: the skill-name guard triggers added by MYAI-34 are kept; the wrapper now always sets an owner so they only guard legacy/direct writes (docs/data.md updated).

### Baseline (2026-11-09)
`pytest backend tests` on the base (MYAI-35 branch): 10 failed (async-plugin: test_cache_system x2, test_research_utils x2, test_code_executor x6), 1362 passed.

### Implementation progress
- [x] Step 1: Persona wrapper - persona_ops.py (`user_id` everywhere; per-user default; `update_persona` target-first with `rowcount`)
- [x] Step 2: Skill and preference wrappers - skill_ops.py (`add_skill` guarded upsert returning False for a foreign id; `delete_skill` returns False for missing/foreign), preference_ops.py
- [x] Step 3: Routes - persona, skill, preference routes pass `current_user_id()`; foreign ids are each route's 404; `save_chat_endpoint` 404 for a foreign `persona_id`
- [x] Step 4: Tools - `ToolHandler.user_id` (lazy) injected via `system_ctx`; preference tools and `get_skill_details` take `user_id`, error + `tool_missing_owner` without it
- [x] Step 5: Turn path - `initiate_chat` applies a truthy `persona_id`/`folder` only if the owner owns it (else ignored + logged), falsy values pass through; prompt uses the owner's preferences and skills; `PromptBuilder.persona_content` looks up among the owner's personas
- [x] Step 6: Docs - wrapper README, tools README, docs/tools.md, security.md, data.md
- Branch: feature/multi-user-scope-personas-skills

### Smoke test (2026-11-09)
`pytest backend tests`: 10 failed (baseline), 1390 passed. `ruff check .`: clean.

PR: https://github.com/archit342000/My-AI/pull/89, branch feature/multi-user-scope-personas-skills, base feature/multi-user-scope-chats-by-owner

## Verification

### Verification plan and results (2026-11-09)
Live: the real app on a throwaway DATA_DIR (/tmp, removed) with the MYAI-33 harness (real `CloudflareAccessProvider`, signed test JWTs), users alice (admin) and bob. Script `MYAI-36-evidence/scripts/drive.py`, results `live-results.json`.
| ID | Scenario | Status |
|----|----------|--------|
| V1 | the same persona name for two users (both 201); lists per user, each with its own default | PASS |
| V2 | bob gets 404 on update and delete of alice's persona; alice's persona and default untouched | PASS |
| V3 | the same skill name for two users; a duplicate for one user is 400; lists per user | PASS |
| V4 | bob gets 404 on update and delete of alice's skill; alice's skill untouched | PASS |
| V5 | preference lists per user; bob gets 404 changing alice's preference; bob's reset clears only his | PASS |
| V6 | saving a chat with alice's `persona_id` is 404 and creates no chat; with bob's own it works | PASS |
| V7 | regression: `pytest backend tests` baseline failures only; ruff clean | PASS |
Verdict: verified (14 checks / 7 scenarios). Covered by unit and real-temporary-DB tests rather than live: the preference tools and `get_skill_details` acting only on the owner's rows, the prompt for user B containing none of user A's skills or preferences, and the turn-path `persona_id`/`folder` handling (they need the inference service).

## Review history

### Round 1 - 2026-11-09
Verdict: Approve with comments (no BLOCKER/MAJOR). Scope: working tree vs HEAD, 27 files / ~870 lines, 1 Haiku reviewer.
- R1-1 [MINOR] tool_handler.py - the lazy owner read in `system_ctx` ran outside a try on every pure tool call; a db error would raise mid-stream - Static - Fixed: guarded (logs, owner None; tools then report "no owner"); test
- R1-2 [MINOR] chat/router.py save, chat/handler.py - a non-string `persona_id`/`folder`/`workspace_id` reached sqlite (500; or an exception after the stream started) - Static - Fixed: save returns 400; the handler ignores and logs it; tests
- R1-3 [MINOR] tools/README.md - row named a non-existent tool `manage_user_preferences` - Static - Fixed: the three real tool names
- R1-4 [NIT] preferences.py, skills_tool.py - `user_id` parameters lacked type hints - Static - Fixed
- R1-5 [NIT] skills_tool.py - the "missing owner" branch duplicates the helper in preferences.py - Static - Rejected: two lines in a different module; sharing would make skills_tool import a private helper from preferences
Resolution: 4 Fixed, 1 Rejected. `pytest backend tests` 10 failed (baseline), 1403 passed; ruff clean. Runtime: tool_handler.py, chat/router.py, chat/handler.py. Re-verify: live re-run PASS (live-results-rerun1.json). Review loop clean (1/5).

## Log
- 2026-11-09: created (split from MYAI-32 Step 4)
- 2026-11-09: linked split_from MYAI-32 (Step 4)
- 2026-11-09: linked blocked_by MYAI-34
- 2026-11-09: linked blocked_by MYAI-9
- 2026-11-09: linked blocks MYAI-42
- 2026-11-09: linked conflicts_with MYAI-35 (shared files per MYAI-32 Steps intro)
- 2026-11-09: linked conflicts_with MYAI-37 (shared files per MYAI-32 Steps intro)
- 2026-11-09: linked conflicts_with MYAI-38 (shared files per MYAI-32 Steps intro)
- 2026-11-09: linked conflicts_with MYAI-39 (shared files per MYAI-32 Steps intro)
- 2026-11-09: linked conflicts_with MYAI-40 (shared files per MYAI-32 Steps intro)
- 2026-11-09: plan validated, 2 rounds
- 2026-11-09: autopilot started (batch)
- 2026-11-09: implemented, smoke tests pass (baseline failures only)
- 2026-11-09: verified 14 PASS, 0 FAIL
- 2026-11-09: review round 1: Approve with comments (3 MINOR, 2 NIT); resolved, re-verified
- 2026-11-09: PR opened: https://github.com/archit342000/My-AI/pull/89 (stacked on MYAI-35's PR). batch-autopilot: shipped
- 2026-11-10: closed (merged into develop via the PR recorded in Implementation notes; deployed to myai.architanand.dev)
