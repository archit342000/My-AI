---
id: MYAI-43
title: "Follow-ups from batch 1 (PRs #55-#57): upload 500, Retry guard, resume body, async test plugin"
status: todo
created: 2026-11-09
updated: 2026-11-20
links:
  relates_to: [MYAI-6, MYAI-10, MYAI-11, MYAI-20, MYAI-22, MYAI-24, MYAI-44]
---

## Description
Defects and gaps found while shipping MYAI-6, MYAI-10 and MYAI-11. None block those PRs. Items 6 and 7 are already tracked elsewhere and listed only so nothing is lost.

1. **Non-object `uploadedFiles` item gives 500.** `POST /v1/chat/completions` iterates `files` and calls `f.get('file_id')` (backend/chat/router.py, the file-note loop, line 284 at 6a13e04). A list such as `[null, "junk", 5]` raises AttributeError, so the client gets 500. Should be 400 `{"error": ...}` (docs/standards/api.md). Related to MYAI-22 (routes crash on bad input), kept separate because it is in `chat_completions`.
2. **Retry does nothing while a stream is running.** `retry()` in frontend/src/features/chat/MessageList.tsx deletes the assistant reply, then `resumeTurn` (send-turn.ts) returns silently when `useStreamStore.getState().chatId` is set. The reply is gone, nothing regenerates, no toast. Same behaviour existed with `sendTurn` before MYAI-6. Check the guard before the delete, or show a toast when the resume is refused.
3. **`/resume` body keys.** `resume_chat` (backend/chat/router.py) strips only `model`, `researchMode`, `userPreferences`, `fileSystemMode`, `browsingMode` (`RESUME_STRIP_KEYS`). `messages: []`, `chatId` and `uploadedFiles` flow into `initiate_chat(**kwargs)`, and the comment says mode flags must not be synced. Harmless today (MYAI-6 verified live) but inconsistent: strip the keys that are not read, or make `resumeTurn` send only what resume reads.
4. **`pytest-asyncio` is not a dev dependency.** `requirements-dev.txt` lists only pytest and ruff; some tests use `@pytest.mark.asyncio` (for example backend/database/tests/test_cache_system.py, backend/tools/tests/test_code_executor.py, tavily_mcp/tests/test_server.py) and fail with "async def functions not natively supported". Seen as about 20 failures across the backend, tavily_mcp and code_runner_mcp suites, so `scripts/check.sh` is red on a fresh venv. Decide: add pytest-asyncio to requirements-dev.txt (and configure the mode) or convert those tests to the anyio marker the other tests use. Update docs/standards/testing.md if the convention changes.
5. **Image messages render as `[object Object],[object Object]` in the React UI** (found while verifying MYAI-20). `GET /api/chats/<id>` returns a multimodal user message's `content` as a decoded list (`get_messages` parses it), and `toTurns` in frontend/src/lib/chat-model.ts passes it through `clean()` which calls `String()`, so `parseUserContent` never sees the parts and the bubble shows `[object Object]`. The edit box then opens with that text too, so an edit that is saved without retyping stores the garbage as the text (images are kept by MYAI-20). Fix in `toTurns` (accept an array of parts as well as a JSON string) with a test. Evidence: ui-preexisting-image-message.png in the MYAI-20 evidence folder.
6. Already tracked: `update_preference` returns 500 for an unknown id and routes crash without a JSON body: MYAI-22. Edit "Save & regenerate" adds a user row without attachments and loses them on a later Retry: MYAI-20.
7. Already tracked: dropping the unused `file_system_counters` table and `get_next_file_system_counter` after MYAI-10: MYAI-24.

## Acceptance criteria
- [ ] `POST /v1/chat/completions` with a non-object `uploadedFiles` item returns 400 with a JSON error and persists nothing
- [ ] Retry never deletes a reply without regenerating (guard before the delete, or a visible message)
- [ ] `/resume` strips or documents every key it does not read
- [ ] A user message with an image shows its text (not `[object Object]`) in the transcript and in the edit box
- [ ] The async tests run on a fresh venv from `requirements-dev.txt`, and `scripts/check.sh --python-only` is green

## Plan

**Date:** 2026-11-20  **Status:** Validated

### Objective
Close the batch 1 follow-ups still open: pin the non-object `uploadedFiles` fix with a test, stop the per-reply Retry from deleting a reply it cannot regenerate, make `/resume` forward only the body keys it reads, make the async tests run on a fresh venv, and show image messages' text instead of `[object Object]`.

### Context
- Requirement: items 1-5 and the five acceptance criteria (items 6 and 7 are tracked elsewhere).
- Item 1 is fixed on develop: `chat_completions` (`backend/chat/router.py`) returns `400 {"error": "uploadedFiles must be a list"}` for a non-list and `400 {"error": "Unknown file"}` for any item that is not an attached file's object, before `claim_chat`/`claim_turn`. `backend/chat/tests/test_router.py` covers non-lists and dict items, but no list holding `null`, a string or a number.
- Item 2: `MessageList.tsx` `retry(assistantIdx)` calls `chatsApi.deleteMessage` with no busy check, then `resumeTurn` (`send-turn.ts`) returns early when `useStreamStore` has a `chatId`. The per-reply button (`MessageActions.tsx`, "Retry response") has no `disabled` input; it is visible while this chat sends a new message (the previous reply is still last) and while another chat streams. `retryLast` and the stopped-row Retry already check `storeBusy`.
- Item 3: `resume_chat` forwards every body key except `RESUME_STRIP_KEYS` to `ChatHandler.initiate_chat(**kwargs)` (`backend/chat/handler.py`). `initiate_chat` reads `gitMode`, `codeExecutionMode`, `enable_thinking`, `temperature`, `top_p`, `max_tokens`, `thinking_budget_tokens`, `top_k`, `min_p`, `presence_penalty`, `frequency_penalty`, `thinking_profile`, `folder`, `persona_id` (plus the stripped mode flags and `userPreferences`). The React `resumeTurn` body (`buildCompletionBody`, `frontend/src/api/completions.ts`) also carries `lastModelName`, `messages`, `visionEnabled`, `chatId`, `stream`, `stream_options`, `code_execution_mode`, which flow through unused; keys named like `files`, `user_message` or `parent_type` would bind to internal parameters.
- Item 4: 29 tests in 6 files use `@pytest.mark.asyncio` (`backend/file_system/tests/test_manager.py`, `backend/tools/tests/test_code_executor.py`, `backend/tools/agents/research_agent/tests/test_research_utils.py`, `backend/database/tests/test_cache_system.py`, `tavily_mcp/tests/test_server.py`, `playwright_mcp/tests/test_server.py`); about 378 use `@pytest.mark.anyio`, which runs with the `anyio` pytest plugin; `anyio` arrives only transitively (through `httpx` in `requirements.txt`). `requirements-dev.txt` (`-r requirements.txt`, pytest, ruff) has no pytest-asyncio; no conftest sets an `anyio_backend`. `code_runner_mcp` has no async tests (the ticket's mention is stale), but its suite imports `fastapi` (`code_runner_mcp/requirements.txt`), which `requirements-dev.txt` does not install, so `scripts/check.sh --python-only` is also red on a fresh venv for that reason.
- Item 5: `GET /api/chats/<id>` serves stored JSON content decoded (`message_ops.py` `get_messages` `_parse_json_field`), so a vision user message arrives as an array. `frontend/src/lib/chat-model.ts` `clean()` returns `String(value)`, giving `[object Object],…`; `parseUserContent` then fails to parse it. The edit box starts from `turn.text` (`MessageList.tsx` `UserTurn`).
- Rules: `docs/standards/testing.md`, `docs/standards/api.md` (one turn per chat, `/resume`), `docs/standards/dependencies.md`, `docs/standards/frontend.md`.

### Approach
- Item 1: a regression test only.
- Item 2 (redesigned after two rounds of failures in the client-side delete-then-resume sequence): the client no longer deletes the reply itself. `POST /api/chats/<id>/resume` takes an optional `replace_from` (the id of the reply's first stored message). The route validates it before anything else is taken (an integer, else 400), and deletes from that message (`db.delete_message`, the same cascade the DELETE route uses) only after `claim_turn` has succeeded and the last user message has been found, immediately before `initiate_chat`, then resumes as today. If something fails after the delete (the handler raises, or the stream ends in an error), the person sees the existing error (the route's 500 body or the stream's `data: {"error": ...}` row with its Retry), so the loss is never silent. Invariants: the reply is deleted only by the server, only while it holds this chat's turn claim for the regeneration, and only after the rate limit and the claim have both passed; a refused resume (turn in progress, turn limit, bad id) deletes nothing, so the reply stays and the existing refusal toast explains why. An id that is not part of the reply to the last user message (not in this chat, the prompt itself, or an older turn) releases the claim and answers 409. React `retry()` calls `resumeTurn(queryClient, chatId, { replaceFrom: Number(firstMessageId(turn)) })` (message ids are strings in `chat-model.ts`; the server needs an integer) instead of `chatsApi.deleteMessage` + `resumeTurn`; the per-reply button is also disabled while the stream store is busy (one control fewer to click into a refusal). Rejected: client-side re-checks after the delete (the window cannot be closed on the client).
- Item 3: replace the strip list with an allowlist on the server: `RESUME_FORWARD_KEYS` = the settings keys `initiate_chat` reads that are forwarded today (everything it reads except `researchMode`, `browsingMode`, `fileSystemMode` and `userPreferences`, which stay unforwarded; `gitMode` and `codeExecutionMode` keep being forwarded as now). Unknown keys are dropped, including `model_name` and `parent_type`, which `_run_background_turn` would read from the forwarded kwargs; no client sends them, so resume behaviour is unchanged for every client. `replace_from` is consumed by the route and never forwarded. Rejected: trimming the client body only (the server would still forward whatever another client sends).
- Item 4: convert the `asyncio` marks in the suites `check.sh` runs (21 tests in 5 files) to `anyio`, the repo's convention; pin `anyio` in `requirements-dev.txt` (it is only transitive today) and add `-r code_runner_mcp/requirements.txt` so the code_runner_mcp suite imports; state the convention in `docs/standards/testing.md`. `playwright_mcp` (own image, not in `check.sh`) is left as is. Rejected: adding pytest-asyncio (two async plugins, mode configuration).
- Item 5: `clean()` turns a non-string value back into JSON text (`JSON.stringify`), so decoded arrays and objects reach `parseUserContent` and every other reader (assistant text, reasoning, tool results) as JSON text equal in meaning to what was stored (whitespace may differ: a user who typed `[1, 2]` sees `[1,2]`, and saving an unchanged edit of such a message stores the compact form; accepted, since today the same message shows as `1,2` or `[object Object]`). This departs from the ticket's suggestion (accept arrays in `toTurns`) on purpose: the decoding affects every `clean()` reader, not only user rows, and one change fixes them all.

### Out of scope
- Items 6 and 7 (MYAI-22, MYAI-20, MYAI-24).
- `code_execution_mode` vs `codeExecutionMode` naming between client and handler (noted under risks).
- Changing the server to stop decoding message content.
- `playwright_mcp/tests/test_server.py` markers (that suite runs in its own image, outside `check.sh`).
- The per-minute turn slot a rejected send spends (documented in `docs/standards/api.md`).

### Steps
#### Step 1: Regression test for non-object `uploadedFiles` items
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/chat/tests/test_router.py` (modify)
- **Change:** parametrized test posting `uploadedFiles` lists containing `null`, `"junk"` and `5`: 400 `{"error": "Unknown file"}`, no `claim_chat`/`ensure_chat_exists`, no `add_message`, no claim taken.
- **Verification:** the test passes on develop and fails if the `isinstance(attached, dict)` guard is removed (checked once locally).

#### Step 2: Retry replaces the reply on the server, under the turn claim
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/chat/router.py` (modify: `resume_chat`); `backend/chat/tests/test_router.py` (modify); `frontend/src/features/chat/send-turn.ts` (modify: `resumeTurn` optional `{ replaceFrom }` added to the body as `replace_from`); `frontend/src/features/chat/MessageList.tsx` (modify: `retry`, `AssistantTurn` passes `retryDisabled={storeBusy}` to `MessageActions`, the only input to the Retry button's disabled state); `frontend/src/features/chat/MessageActions.tsx` (modify: `retryDisabled` prop with the reason "A reply is being written"); `frontend/src/features/chat/send-turn.test.ts`, `frontend/src/features/chat/MessageList.test.tsx`, `frontend/src/features/chat/MessageActions.test.tsx` (create), `frontend/e2e/stop-races.spec.ts` (modify)
- **Change:** as in Approach item 2. In `resume_chat`, read `replace_from` with the body (400 `{"error": "replace_from must be a message id"}` for anything but an integer, booleans included, before the rate limit and claim); after `claim_turn` succeeds and the last user message is found, check that `replace_from` is the first message of this chat after the last user message (the smallest id greater than the last user message's id, from the messages already loaded), so it is the start of the reply to that message, never the prompt itself, a row inside the reply, or a later turn another tab added; otherwise release the claim and answer 409 `{"error": "This reply is no longer the latest. Reload the chat and try again."}`; then `db.delete_message(chat_id, replace_from)` right before `initiate_chat`. `retry` in `MessageList.tsx` returns early when the stream store is busy (`BUSY_TOAST` for another chat, as `resumeTurn` does) and otherwise calls `resumeTurn(queryClient, chatId, { replaceFrom: Number(firstMessageId(turn)) })`; it no longer calls `chatsApi.deleteMessage`.
- **Verification:** backend tests: with `replace_from`, the message is deleted after the claim and `initiate_chat` runs; when the claim is refused (400) or the rate limit hits (429), `delete_message` is not called; a non-integer (including `true`) gives 400 before any claim; an id not in the chat, the user message's own id, an id inside the reply (not its first row) and an id from before the last user message (a stale tab) each release the claim, give 409 and delete nothing; a `get_messages` failure before the delete leaves the reply in place; all of these fail on the current code. Frontend tests: Retry posts `/resume` with a numeric `replace_from` (asserted as a JSON number) and makes no DELETE; a 400 or 429 refusal toasts and the reply stays; with the store busy the button is disabled (`MessageActions.test.tsx` covers `retryDisabled`, whose tooltip reason is "A reply is being written") and `retry` does nothing; existing retry tests updated for the new call; "a failed delete shows a toast and does not resume" is removed (the client no longer deletes).

#### Step 3: `/resume` forwards only the keys it reads
- **Status:** todo
- **Depends on:** Step 2 (same function and test file; `replace_from` must be consumed before the allowlist)
- **Files:** `backend/chat/router.py` (modify: `resume_chat`, `RESUME_FORWARD_KEYS` module constant); `backend/chat/tests/test_router.py` (modify)
- **Change:** `extra_body = {k: v for k, v in resume_body.items() if k in RESUME_FORWARD_KEYS}` with `RESUME_FORWARD_KEYS = {"gitMode", "codeExecutionMode", "enable_thinking", "temperature", "top_p", "max_tokens", "thinking_budget_tokens", "top_k", "min_p", "presence_penalty", "frequency_penalty", "thinking_profile", "folder", "persona_id"}`; the comment keeps today's reason for not forwarding `researchMode`, `browsingMode`, `fileSystemMode` and `userPreferences`, and says other keys are dropped.
- **Verification:** test posts the full React resume body plus `files`, `user_message`, `parent_type`, `model_name`, `replace_from`: `initiate_chat` receives only allowlisted keys with their values (the test fails on the current code); existing resume tests pass.

#### Step 4: Async tests use anyio
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/file_system/tests/test_manager.py`, `backend/tools/tests/test_code_executor.py`, `backend/tools/agents/research_agent/tests/test_research_utils.py`, `backend/database/tests/test_cache_system.py`, `tavily_mcp/tests/test_server.py` (modify: `@pytest.mark.asyncio` → `@pytest.mark.anyio`); `requirements-dev.txt` (modify: `-r code_runner_mcp/requirements.txt`, and `anyio==4.16.0`, the version pip resolves today for the current `requirements.txt`, checked against anyio's release notes for the pytest plugin and confirmed by `pip check` in the fresh venv); `docs/standards/testing.md`, `docs/standards/dependencies.md` (modify)
- **Change:** replace the marker, adding no fixtures; rewrite the two comments in `backend/tools/tests/test_code_executor.py` that mention "the pytest-asyncio plugin that the older tests need". testing.md: async tests are marked `@pytest.mark.anyio` (asyncio backend by default); pytest-asyncio is not used. dependencies.md: the sentence on lines 5-6 now says `requirements-dev.txt` adds pytest, ruff, `anyio` and the code runner's requirements; line 7 (MCP services keep their own `requirements.txt`): add that `requirements-dev.txt` also includes `code_runner_mcp/requirements.txt` so its tests run in the dev venv, as the one recorded exception, and that `anyio` is pinned there for the test marker.
- **Verification:** in a fresh venv built from `requirements-dev.txt` alone (no pytest-asyncio), `scripts/check.sh --python-only` passes; `grep -rn "mark.asyncio" backend tavily_mcp code_runner_mcp inference_proxy tests` finds nothing.

#### Step 5: Decoded message content shows as text
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/lib/chat-model.ts` (modify: `clean`, `parseUserContent`); `frontend/src/api/types.ts` (modify: `content` comment/type allows a decoded value); `frontend/src/lib/chat-model.test.ts`, `frontend/src/features/chat/MessageList.test.tsx` (modify)
- **Change:** `clean` returns strings as they are and `JSON.stringify(value)` for other non-absent values. `parseUserContent` treats a JSON array as content parts only when every item is an object with a `type` of `text` or `image_url`; any other JSON (a typed `[1, 2]`) stays plain text.
- **Verification:** tests: a user row whose `content` is an array of a text and an image part gives the text and the image; the edit box opens with the text only; an assistant row with decoded `[1, 2]` shows `[1,2]`; a tool row whose content arrived decoded shows its JSON text; a user message typed as `[1, 2]` shows and opens in the edit box as `[1,2]` (text kept; the accepted whitespace change, pinned), not as an empty message; these fail on the current code; existing tests pass.

#### Step 6: Docs
- **Status:** todo
- **Depends on:** Steps 2, 3, 5
- **Files:** `docs/standards/api.md` (modify: widen the `409` status bullet to cover a resume whose `replace_from` is no longer the latest reply; `/resume` uses the chat's stored message, forwards only the listed settings, and takes `replace_from`: 400 for a non-integer before the rate limit and claim, 409 for a message that is not part of the latest reply, after the claim, deletion only under the claim), `backend/chat/README.md` (modify: resume line), `docs/frontend.md` (modify: message content may arrive decoded; the client re-encodes it)
- **Change:** one or two lines each; `docs/frontend.md` (191 lines) stays under its 200-line budget.
- **Verification:** `pytest tests` passes, including `tests/test_docs.py`.

### Tests
- With `venv/bin/python -m pytest` and the env vars in `docs/standards/testing.md`: `backend/chat`, `backend`, `inference_proxy`, `tavily_mcp`, `tests`, and `cd code_runner_mcp && PYTHONPATH=. ../venv/bin/python -m pytest`; `venv/bin/python -m ruff check .`.
- Frontend: `npm run typecheck`, `npm run lint`, `npm run test`, `npm run build`; `npm run e2e:stack` (covers "Retry regenerates the reply" in `frontend/e2e/stack/stop-retry.spec.ts`), and `frontend/e2e/stop-races.spec.ts`, which mocks the old DELETE-then-resume order and is updated in Step 2 to expect a single `/resume` with `replace_from`.
- `scripts/check.sh` on a fresh venv from `requirements-dev.txt`.

### Risks and open questions
- The React client sends `code_execution_mode` but `initiate_chat` reads `codeExecutionMode`, so that setting is not applied on send or resume today; separate from this ticket.
- Pre-existing: the resume rate limit runs before the claim, so the retry window after a Stop can spend several turn slots; unchanged here.
- `POST /api/chats/<id>/resume` gains an optional `replace_from`; `DELETE /api/chats/<id>/messages/<id>` is unchanged for its other callers.
- Converting markers could expose a test that relied on pytest-asyncio's event-loop fixture; Step 4's verification runs every converted file.
- A fresh venv from `requirements-dev.txt` installs `easyocr` (and its torch dependency) from `requirements.txt`; that is slow but needed for the two OCR tests.

### Success criteria
- [ ] A non-object `uploadedFiles` item gives 400 JSON and persists nothing (test, Step 1)
- [ ] Retry never deletes a reply without regenerating: the server deletes it only under the turn claim (Step 2)
- [ ] `/resume` forwards only the keys it reads; documented (Steps 3, 6)
- [ ] A user message with an image shows its text in the transcript and the edit box (Step 5)
- [ ] The async tests run on a fresh venv from `requirements-dev.txt`; `scripts/check.sh --python-only` is green (Step 4)

### Reviewer brief
- Objective: close the batch 1 follow-ups: a regression test for non-object `uploadedFiles`, a Retry that never deletes a reply without regenerating, `/resume` forwarding only the keys it reads, async tests that run on a fresh venv, and image messages shown as text.
- Key decisions: Retry sends `replace_from` (a number) on `/resume`; the server deletes the reply only under the turn claim, only when it is the first row after the last user message (else 409), right before `initiate_chat`. `/resume` uses an allowlist of forwarded keys. `asyncio` markers become `anyio` (playwright_mcp excluded); `requirements-dev.txt` adds the code runner's requirements and `anyio==4.16.0`. `clean()` re-encodes decoded content and `parseUserContent` only treats typed part arrays as parts (JSON-looking text may show with compact whitespace).
- Out of scope: items 6 and 7 (tracked elsewhere), `code_execution_mode` naming, server-side content decoding, playwright_mcp markers, the turn slot a refused resume spends.
- Success criteria: as listed in the plan.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
Path: pair (requirement and standards; failure scenarios), Haiku validators, judged against the code each round.
- Round 1: both FAIL. Valid: Retry could delete a reply while a send started during the delete (blocking); check.sh red on a fresh venv because code_runner_mcp needs fastapi (blocking, reframed from a stale claim about async marks there). Minors fixed (allowlist wording, threading, anyio pin, playwright scope, tool-row test, README, suites). Disproved: none.
- Round 2: L1 PASS; L2 FAIL. Valid: `consume` swallows 400/429, so the boolean return could not show a refused resume (blocking, second failure of the client-side delete-then-resume) -> redesigned: the server deletes under the turn claim (`replace_from`). Accepted risk: compact JSON whitespace for JSON-looking user text.
- Round 3 (full after redesign): both FAIL. Valid: string message ids vs integer `replace_from`; the prompt or a newer turn could be deleted; a typed "[1, 2]" would become empty. All fixed (Number(), first-row-after-last-user rule with 409, typed-parts check).
- Round 4 (scoped): both PASS. Disproved: stale reply shown during regeneration (hidden() covers it), Retry on older replies (only the last reply has Retry). Minors fixed inline (409 bullet, bool rejected, e2e specs, prop wiring, dependencies line).

## Implementation notes

## Verification
Not run yet.

## Review history
None yet.

## Log
- 2026-11-09: created from the batch 1 follow-ups (PRs #55, #56, #57)
- 2026-11-09: added item 5 (image messages render as [object Object]) found while verifying MYAI-20
- 2026-11-09: linked relates_to MYAI-44 (batch 2 follow-ups)
- 2026-11-20: plan validated, 4 rounds
