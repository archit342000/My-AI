---
id: MYAI-43
title: "Follow-ups from batch 1 (PRs #55-#57): upload 500, Retry guard, resume body, async test plugin"
status: todo
created: 2026-11-09
updated: 2026-11-09
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
Not planned yet. Items 1-4 are independent and can be split into separate tickets or PRs if preferred.

## Implementation notes

## Verification
Not run yet.

## Review history
None yet.

## Log
- 2026-11-09: created from the batch 1 follow-ups (PRs #55, #56, #57)
- 2026-11-09: added item 5 (image messages render as [object Object]) found while verifying MYAI-20
- 2026-11-09: linked relates_to MYAI-44 (batch 2 follow-ups)
