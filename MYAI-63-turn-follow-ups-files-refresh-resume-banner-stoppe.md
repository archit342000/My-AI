---
id: MYAI-63
title: "Turn follow-ups: files refresh, resume banner, stopped replies, links"
status: done
epic: MYAI-53
created: 2026-11-10
updated: 2026-11-10
links:
  blocked_by: [MYAI-54]
  blocks: [MYAI-64, MYAI-73]
---

## Description
After a turn the files panel is not refreshed or opened when the agent wrote files, an interrupted turn has no resume banner, a stopped partial reply is lost on reload, markdown is re-rendered in full on every chunk, and file links and the mermaid pop-out do nothing useful.

Findings (MYAI-52, Verification): A-56, A-57, A-58, A-59, A-60. Evidence and the live test rig are in `~/.claude/tickets/My-AI/MYAI-52-evidence/`.

## Acceptance criteria
- [x] Files written during a turn appear in the panel without a reload, and the panel opens in file-system mode
- [x] A chat with `resume_needed` shows a resume banner that continues the turn
- [ ] A stopped reply is still shown after a reload (or the Stop notice explains it was discarded)
- [x] Streaming does not reset text selection or copy labels on every chunk
- [ ] File links open the file in the files panel; mermaid pop-out opens a full-view
- [x] `last_model` is saved with the chat

## Plan
**Date:** 2026-11-10  **Status:** Validated

### Objective
Finish what should happen around a turn: the files panel reflects files the agent wrote, an interrupted turn offers Resume, the Stop notice is truthful about what is kept, streaming does not re-render the whole reply on every chunk, file links and the mermaid pop-out work, and the chat remembers its model.

### Context
- **Requirement:** this ticket's Description and Acceptance criteria (findings A-56 to A-60 in MYAI-52).
- **Assumes merged:** MYAI-54 (`LiveTurn.steps` with tool steps; one live row; `consume` in `features/chat/send-turn.ts` refetches the chat and then calls `finish()`).
- **Rules:** `docs/standards/frontend.md` (server data through TanStack Query with keys from `api/`, invalidate rather than refetch by hand, pure logic in `src/lib/` with tests, one component per file, model HTML only through `renderMarkdown`, new user flows get a Playwright spec), `docs/frontend.md` (Known gaps must stay accurate). No backend change.
- **Server facts:**
  - `GET /api/chats/<id>` returns `resume_needed` (false while a turn runs or after an explicit stop) and `last_model` (`backend/chat/handler.py` `get_history`).
  - `PATCH /api/chats/<id>` accepts `last_model` and `resume_suppressed` (`backend/chat/router.py` `patch_chat_endpoint`); `POST /api/chats/<id>/resume` continues from the last stored user message.
  - `POST /api/chats/<id>/stop` rolls the chat back to the last user message and clears the stream cache (`stop_chat`): a stopped partial reply is deliberately not stored.
  - File tools are `create_fs_file`, `create_directory`, `delete_directory`, `replace_fs_text`, `replace_fs_lines`, `move_fs_file`, `delete_fs_file`, `patch_file_system`, `file_system_agent` (`backend/tools/catalog/filesystem.py`); the read-only ones are `grep_files`, `read_fs_file`, `ls_files`, `preview_file_systems`.
- **Legacy reference:** `static/script.js` `showResumeBanner` (text "This conversation was interrupted. Resume where it left off?", Resume and Dismiss, Dismiss PATCHes `resume_suppressed: 1`); the click handler for `.file-link` opens the file whose `filename` or `title` equals the link's `data-path`; `last_model` is PATCHed when the model changes and after a turn; `handleFileSystemUpdate` refreshes the file list during a turn.
- **Current code (`frontend/src/`):**
  - `features/chat/send-turn.ts` `consume`: invalidates `queryKeys.chat` and `queryKeys.chats` only; the new-chat PATCH has no `last_model`. `api/chats.ts` `ChatPatch` has neither `last_model` nor `resume_suppressed`; `api/types.ts` `ChatDetail` has no `resume_needed` or `file_system_mode`.
  - `features/artifacts/ArtifactPanel.tsx`: list query key `['artifacts', scopeKey(scope)]`, selection in local state; `state/ui-store.ts` `artifactsOpen`.
  - `features/chat/MessageList.tsx` `InterruptedAssistant`: "Stopped" badge and Retry; the partial reply lives only in `state/stream-store.ts` `interrupted`. `showUserRetry` offers "Retry response" under a user turn with no reply.
  - `components/markdown/Markdown.tsx`: one `renderMarkdown(text)` per render for the whole text; `.file-link` anchors get no handler (the browser follows the relative `href`); the `zoom-popout-btn` branch in `applyZoom` returns without doing anything.
  - `docs/frontend.md` Known gaps lists "Mermaid pop-out and file-link navigation are not implemented".

### Approach
- **Files follow the turn.** `lib/fs-tools.ts` (new) holds the set of file-changing tool names and `changedFiles(steps)` (true when a finished tool step is one of them). During a turn, when a new such result arrives, and again when the turn ends, `consume` invalidates the artifacts list for that chat (a new `artifactsKey(scope)` in `api/filesystem.ts`, built from the `scopeKey` helper moved there from `ArtifactPanel.tsx`, and used by `ArtifactPanel`). The first time a turn changes files in a chat whose detail has `file_system_mode` on, the drawer opens (`useUiStore.setArtifactsOpen(true)`), once per turn.
- **Resume banner.** `features/chat/ResumeBanner.tsx` (new), shown at the end of the transcript when the chat detail has `resume_needed` and no turn is streaming: the legacy text, Resume (`resumeTurn`) and Dismiss (PATCH `resume_suppressed: 1`, then invalidate the chat). It replaces the "Retry response" button under the last user turn in that state, so there is one control.
- **Stopped notice says what happens.** The server discards a stopped reply, so the notice under a stopped partial reply reads "Stopped. This partial reply is not saved." next to Retry. No client-side persistence is added.
- **Cheaper streaming render.** `lib/markdown/blocks.ts` (new) `splitBlocks(text)` cuts the text at blank lines that are outside code fences and math blocks. The live row renders its text (MYAI-54's `turnText(live.steps)`) through `components/markdown/StreamingMarkdown.tsx` (new): one memoised `Markdown` per block, so only the last block is re-rendered as text arrives (selection and Copy labels in finished blocks are kept; the block still being written keeps changing by nature); when the stream ends the saved row renders with the single-pass `Markdown` as today (footnotes and reference links resolve there).
- **File links and mermaid pop-out.** `Markdown`'s click handler intercepts `a.file-link`: it prevents navigation and calls `useUiStore`'s new `openArtifact(path)` (opens the drawer and records the requested path); `ArtifactPanel` selects the file whose `title` or `filename` equals the requested path, or, once the list has loaded, shows a toast when none matches. On the home page (temporary chat), which has no files drawer, the click shows the toast "Open the chat to view its files". The pop-out button (handled before the zoom branch in the click handler; the "not implemented" comment in `applyZoom` goes) opens `components/markdown/MermaidDialog.tsx` (new, built on `Modal`) with the rendered diagram's SVG cloned into it.
- **Model remembered.** The new-chat PATCH includes `last_model`, and a send in an existing chat whose detail has a different `last_model` PATCHes it after the turn is accepted; a refusal (the server returns 400 for research chats) is ignored without a toast.
- **Rejected:** storing stopped replies in `localStorage` (the server's rollback is the source of truth and the next turn would not contain them); block-wise rendering for saved messages too (cross-block footnotes would break).

### Out of scope
- Restoring the chat's model, modes and persona when it is opened: MYAI-64 (this ticket only saves `last_model`).
- Research plan UI, model-switch overlay and sub-agent renderers: MYAI-70. Clarification prompts: MYAI-62.
- Artifact panel layout and file actions: MYAI-66.

### Steps
#### Step 1: Types and API fields
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/api/types.ts` (modify: `ChatDetail.resume_needed`, `file_system_mode`), `frontend/src/api/chats.ts` (modify: `ChatPatch.last_model`, `resume_suppressed`), `frontend/src/api/filesystem.ts` (modify: new `artifactsKey`, `scopeKey` moved in), `frontend/src/features/artifacts/ArtifactPanel.tsx` (modify: use `artifactsKey`), `frontend/src/features/artifacts/ArtifactPanel.test.tsx` (modify only if it asserts the key)
- **Change:** type the fields the server already returns and accepts; one shared artifacts key.
- **Verification:** `npm run typecheck`; the existing artifact tests pass.

#### Step 2: Files follow the turn
- **Status:** todo
- **Depends on:** 1
- **Files:** `frontend/src/lib/fs-tools.ts` (create), `frontend/src/lib/fs-tools.test.ts` (create), `frontend/src/features/chat/send-turn.ts` (modify: `consume`), `frontend/src/features/chat/send-turn.test.ts` (modify), `frontend/src/test/fixtures/stream/files.sse` (create: a turn with a `create_fs_file` call, its result and a multi-block reply), `frontend/src/test/fixtures/stream/stream.test.ts` (modify: the fixture reduces to a finished `create_fs_file` step and the full multi-block text)
- **Change:** as in Approach ("Files follow the turn").
- **Verification:** unit tests: a stream with a finished `create_fs_file` step invalidates the artifacts key once when the result arrives and once at the end; a read-only tool does not; with `file_system_mode` on in the cached detail the drawer flag is set once; with it off the flag is untouched.

#### Step 3: Resume banner and Stop notice
- **Status:** todo
- **Depends on:** 1
- **Files:** `frontend/src/features/chat/ResumeBanner.tsx` (create), `frontend/src/features/chat/ResumeBanner.test.tsx` (create), `frontend/src/features/chat/MessageList.tsx` (modify: props for `resumeNeeded`, banner placement, `showUserRetry`, stopped text), `frontend/src/features/chat/ChatPage.tsx` and `frontend/src/features/home/HomePage.tsx` (modify: pass `resume_needed`), `frontend/src/features/chat/MessageList.test.tsx` (modify), `frontend/src/styles/components.css` (modify: banner rules in the "Chat transcript" block, reusing the legacy `.resume-banner` classes)
- **Change:** as in Approach ("Resume banner", "Stopped notice says what happens").
- **Verification:** component tests: with `resume_needed` the banner shows and "Retry response" does not; Resume calls `resumeTurn`; Dismiss PATCHes `resume_suppressed: 1` and the banner goes after the refetch; while streaming no banner shows; a stopped reply shows the new sentence.

#### Step 4: Block-wise streaming render
- **Status:** todo
- **Depends on:** 3 (shared file `MessageList.tsx`, no functional dependency)
- **Files:** `frontend/src/lib/markdown/blocks.ts` (create), `frontend/src/lib/markdown/blocks.test.ts` (create), `frontend/src/components/markdown/StreamingMarkdown.tsx` (create), `frontend/src/components/markdown/StreamingMarkdown.test.tsx` (create), `frontend/src/features/chat/MessageList.tsx` (modify: live row uses it)
- **Change:** as in Approach ("Cheaper streaming render").
- **Verification:** unit tests: blank lines inside a fenced block or a `$$` block do not split; joining the blocks gives the input back. Component test: appending text to the last block leaves the DOM nodes of earlier blocks identical (same node references).

#### Step 5: File links and mermaid pop-out
- **Status:** todo
- **Depends on:** 1
- **Files:** `frontend/src/state/ui-store.ts` (modify: `requestedArtifactPath`, `openArtifact`, `clearRequestedArtifact`), `frontend/src/state/ui-store.test.ts` (modify), `frontend/src/components/markdown/Markdown.tsx` (modify: click handler), `frontend/src/components/markdown/MermaidDialog.tsx` (create), `frontend/src/components/markdown/Markdown.test.tsx` (create), `frontend/src/features/artifacts/ArtifactPanel.tsx` (modify: select the requested path), `frontend/src/features/artifacts/ArtifactPanel.test.tsx` (modify)
- **Change:** as in Approach ("File links and mermaid pop-out"). The dialog's SVG is the already sanitised, already rendered diagram node; no new HTML source is introduced.
- **Verification:** component tests: clicking a `.file-link` does not change the location, opens the drawer and selects the matching file; an unknown path shows a toast; the pop-out button opens a dialog that closes on Escape.

#### Step 6: Save the model with the chat
- **Status:** todo
- **Depends on:** 2
- **Files:** `frontend/src/features/chat/send-turn.ts` (modify: new-chat PATCH, PATCH on change), `frontend/src/features/chat/send-turn.test.ts` (modify)
- **Change:** as in Approach ("Model remembered").
- **Verification:** unit tests: the new-chat PATCH body has `last_model`; a send with a different model PATCHes `last_model` once; a send with the same model does not; a 400 from that PATCH shows no toast.

#### Step 7: End-to-end spec, docs and full checks
- **Status:** todo
- **Depends on:** 2, 3, 4, 5, 6
- **Files:** `frontend/e2e/turn-follow-ups.spec.ts` (create), `docs/frontend.md` (modify: Streaming section and Known gaps: remove the mermaid and file-link gap, describe the resume banner and the files refresh)
- **Change:** the spec mocks a chat detail with `resume_needed`, a stream with a `create_fs_file` call and result, and the artifacts list.
- **Verification:** the spec asserts the banner resumes the turn, the files drawer opens with the new file after the turn, and a file link in the reply selects it. Then from `frontend/`: `npm run typecheck`, `npm run lint`, `npm run test`, `npm run build`, `npm run e2e`; from the repo root `pytest tests` and `scripts/check.sh --frontend-only`. Live (MYAI-52 rig): the `FILE` scenario opens the drawer with `hello.md`.

### Tests
- Unit: `lib/fs-tools.test.ts`, `lib/markdown/blocks.test.ts`, `state/ui-store.test.ts`, `features/chat/send-turn.test.ts`.
- Component: `ResumeBanner.test.tsx`, `StreamingMarkdown.test.tsx`, `Markdown.test.tsx`, `MessageList.test.tsx`, `ArtifactPanel.test.tsx`.
- E2E: `e2e/turn-follow-ups.spec.ts`.

### Risks and open questions
- **Block boundaries can shift while a fence is still open** (an unclosed fence makes the rest one block); that block simply re-renders until it closes.
- **The drawer opening by itself** follows legacy and only happens in file-system mode; the user can close it and it stays closed for the rest of that turn.
- **Shared files:** `MessageList.tsx` (MYAI-55, 60, 62), `send-turn.ts` and its test (MYAI-54, 56, 64), `stream.test.ts` (MYAI-54), `ArtifactPanel.tsx` (MYAI-60, 66), `ChatPage.tsx` and `HomePage.tsx` (MYAI-56, 64). `artifactsKey` in `api/filesystem.ts` is also planned by MYAI-60: whichever lands first defines it and the other reuses it.

### Success criteria
- [ ] Files written during a turn appear without a reload; the drawer opens in file-system mode
- [ ] A chat with `resume_needed` shows a banner that resumes or dismisses
- [ ] The Stop notice says the partial reply is not saved
- [ ] Earlier blocks are not re-rendered while a reply streams
- [ ] File links open the file in the panel; mermaid pop-out opens a full view
- [ ] `last_model` is saved with the chat
- [ ] Checks and the new spec pass
### Reviewer brief
- **Objective:** files panel follows the turn, interrupted turns offer Resume, the Stop notice is truthful, streaming re-renders only the block being written, file links and the mermaid pop-out work, `last_model` is saved.
- **Decisions:** `lib/fs-tools.ts` names the file-changing tools; `consume` invalidates `artifactsKey(scope)` on such a result and at turn end and opens the drawer once per turn in file-system mode; `ResumeBanner` replaces "Retry response" when `resume_needed`; stopped replies are not persisted (server rolls back) and the notice says so; `StreamingMarkdown` renders the live text by blocks from `lib/markdown/blocks.ts`, saved messages keep the single pass; `.file-link` clicks call `ui-store.openArtifact(path)` and `ArtifactPanel` selects the file; `MermaidDialog` for the pop-out; `last_model` in the new-chat PATCH and on change, with a 400 ignored.
- **Out of scope:** restoring a chat's settings on open (MYAI-64), research UI and sub-agent renderers (MYAI-70), clarification prompts (MYAI-62), panel layout and file actions (MYAI-66).
- **Success criteria:** files appear without a reload and the drawer opens in file-system mode; resume banner works; Stop notice states the reply is not saved; earlier blocks are not re-rendered while streaming; file links and pop-out work; `last_model` saved; checks and the new spec pass.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- **Round 1:** validator FAIL (1 blocking, 9 minor). Judged FAIL. Valid blocking: streaming changes without a fixture update (added `fixtures/stream/files.sse`). Disproved: "`frontend` has no `.resume-banner` rules" (`styles/legacy.css` has them). Minors fixed: `artifactsKey` marked new with `scopeKey` moved; scope of the streaming criterion stated; live text source named (`turnText`); 400 on `last_model` for research chats ignored; file link on the home page; wait for the list before the "not found" toast; pop-out dispatch and stale comment; step dependencies; shared files.
- **Round 2 (diff-scoped):** validator PASS (4 minor). Judged PASS. Fixed inline: what the fixture test asserts; shared-file list and `artifactsKey` ownership; dependency wording.

## Implementation notes
### Autopilot run (2026-11-10)
- Mode: automatic (batch)
- Branch: bugfix/turn-follow-ups  PR base: bugfix/start-chat-and-send (stacked on PR #102)  Starting commit: bca30f1
- Dirty before start: none
- Work files: api/{types,chats,filesystem}.ts, lib/{fs-tools,markdown/blocks}.ts(+tests), chat/{send-turn,MessageList,ChatPage,ResumeBanner}, markdown/{Markdown,StreamingMarkdown,MermaidDialog}, ui-store, ArtifactPanel, components.css, fixtures/stream/files.sse, e2e/turn-follow-ups.spec.ts, docs/frontend.md
- Counters: fix 0/10, review 3/5, re-verify 3
- Last completed stage: 4 verify  Next: done (shipped)
- Hard blocker: none
- WIP commit: none

### Autopilot decisions (2026-11-10)
- Stage 1: ticket already holds a validated plan; skipped re-planning.
- Legacy `.resume-banner` CSS already exists in legacy.css, so no banner CSS was added to components.css (the plan listed it); two new classes (`streaming-blocks`, `mermaid-popout`) got rules because the CSS-coverage test requires them.
PR: https://github.com/archit342000/My-AI/pull/103, branch bugfix/turn-follow-ups, base bugfix/start-chat-and-send

## Verification

### Acceptance review (2026-11-10)
Criteria ticked on the live and e2e results recorded in the PR's Testing section (checks run on throwaway backends during the autopilot run; scripts in `MYAI-63-evidence/`).
Left unticked, no PASS recorded:
- criterion 3: Stop notice intermittent live (about 1 run in 3, the Stop-versus-refetch race)
- criterion 5: file links and mermaid pop-out only covered by mocked-route e2e and component tests

### Verification plan (2026-11-10)
**Diff base:** bca30f1 (PR #102 tip). **Isolation:** throwaway DATA_DIR /tmp/myai63/data, stub model :5191, backend :5192 serving this branch's build; no containers touched. Scripts: `MYAI-63-evidence/scripts/` (up.sh, stub.py, serve.py, lib.mjs, v63.mjs). Teardown: kill listeners on 5191/5192, rm -rf /tmp/myai63.

| ID | Criterion | Scenario | Method | Files | Expected |
|----|-----------|----------|--------|-------|----------|
| V1 | files appear without reload, drawer opens in file-system mode | chat with File System Mode on, stub FILE scenario (create_fs_file) | browser | send-turn.ts, fs-tools.ts, ArtifactPanel.tsx | drawer open with hello.md right after the turn, no reload |
| V2 | resume banner | send ERR (stub fails, user message stored, no reply), reload; then click Dismiss in one chat and Resume in another | browser+network | ResumeBanner.tsx, MessageList.tsx, ChatPage.tsx | banner shown instead of Retry; Resume posts /resume; Dismiss removes it and it stays gone after reload |
| V3 | stop notice truthful | send SLOW, Stop, then reload | browser | MessageList.tsx | notice says the partial reply is not saved; after reload the reply is gone |
| V4 | streaming keeps finished blocks | during SLOW stream mark the first paragraph's DOM node and select text in it; after more chunks the node is the same and the selection is intact | browser | StreamingMarkdown.tsx, blocks.ts | same node, selection kept |
| V5 | last_model saved | send in a new chat; GET /api/chats/<id> | API | send-turn.ts | last_model equals the selected model |
| V6 | regression | vitest, typecheck, lint, build, e2e specs | CLI | all | pass |
| V7 | no console errors | collect console/page errors in V1-V5 | browser | all | none unexpected |
File links and the mermaid pop-out need assistant text the stub cannot produce; they are covered by the e2e spec (file link, against mocked routes) and component tests (pop-out) and reported as not verified against the real backend.


### Results (2026-11-10)
HEAD bca30f1 + uncommitted work.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | File System Mode on, FILE scenario: drawer opened by itself right after the turn listing `notes/hello.md` (`shots/V1-drawer-after-turn.png`) |
| V2 | PASS | ERR chat reloaded: banner shown, no "Retry response"; Resume sent `POST /api/chats/<id>/resume`; Dismiss removed the banner at once and after reload (Retry response back) |
| V3 | PASS | after Stop: "This partial reply is not saved."; after reload the reply is gone (0 bot rows) |
| V4 | PASS | while SLOW streamed 2 to 5 blocks, the first block kept its DOM node (marker) and the selected text stayed selected |
| V5 | PASS | new chat's `last_model` = Stub/Audit-Model |
| V6 | PASS | vitest 436/436, typecheck, lint, build; e2e turn-follow-ups, chat-start, chat-send 5/5 |
| V7 | PASS | no console/page/http errors in any scenario |

Not verified against the real backend: file link click and mermaid pop-out (the stub cannot produce such replies); covered by the e2e spec (file link, mocked routes) and component tests (pop-out).
Verdict: partly verified live (V1-V5), links and pop-out by e2e/component tests only.

### Results (re-run 1, 2026-11-10)
V1-V5 PASS again after the round 1 fixes. e2e: 1 unexplained failure of the files spec in the first run after the fixes, 18 consecutive passes afterwards. Teardown done.

### Results (re-run 2, 2026-11-10)
V1-V5 PASS again after the round 2 fixes. e2e: the files spec's link locator also matched a sidebar chat left by the live run (spec fixed by scoping to the transcript); after that, 35 consecutive passes of the 3 specs, but 2 further failures were seen in runs made right after the heavy live script (one `toContainText` timeout, cause not captured). Treat the e2e specs as possibly load-sensitive; teardown done.

### Results (re-run 3, 2026-11-10)
V1, V2, V4, V5 PASS again. V3 (Stop notice): the notice shows in about 1 of 3 runs. Cause (checked with a request log): when the chat refetch after Stop lands before the server has finished stopping, it still says is_running, the page reattaches and that clears the interrupted state, so the "not saved" notice disappears. This is the existing Stop-versus-refetch race that the stop-and-delete ticket (MYAI-73) is about; it is not introduced here and is not fixed here. e2e: 3 specs, 4 of 4 runs pass on a warmed backend; failures seen only in runs made right after starting the backend or right after the heavy live script (cause not captured), so the specs may be load-sensitive.
Verdict: partly verified (V1, V2, V4, V5 pass; V3 intermittent because of the stop race; file link and pop-out by e2e/component tests only).

## Review history
### Round 3 - 2026-11-10
Verdict: Approve with comments (0 BLOCKER/MAJOR, 6 MINOR, 1 NIT). Resolution: fixed 5, documented 2. Checks: vitest 456/456, typecheck, lint, build, scripts/check.sh --frontend-only pass. Runtime changed only for MINOR items, so the review loop ends here.
- R3-1 [MINOR] ui-store.test.ts over 100 columns (file was clean at base) - Static - Fixed (prettier)
- R3-2 [MINOR] the drawer could open for another chat while a turn runs - Static - Fixed: opens only if the chat is on screen; test (failed before)
- R3-3 [MINOR] banner is per chat, brief says "no turn streams" - Static - Documented in docs/frontend.md
- R3-4 [MINOR] unanswered file request survives drawer close or chat change - Static - Fixed: closing the drawer and leaving the chat drop it; test (failed before)
- R3-5 [MINOR] a stray `$$` line made the rest of the reply one block - Static - Fixed: text openers need a later closing `$$`; test (failed before)
- R3-6 [MINOR] per-block newline normalisation differs from the saved render for one-line blocks with a literal \n - Static - Documented in docs/frontend.md
- R3-7 [NIT] StrictMode comment inaccurate - Static - Fixed: the effect reads the store and the comment says so

### Round 2 - 2026-11-10
Verdict: Request changes (2 MAJOR, 6 MINOR, 4 NIT). Resolution: fixed 10, rejected 2. Checks: vitest 453/453, typecheck, lint, build; live V1-V5 pass again. Runtime changed (blocks.ts, StreamingMarkdown, ArtifactPanel, send-turn).
- R2-1 [MAJOR] the block being written still re-renders, so a selection or "Copied" label inside a growing code block resets - Static - Rejected: the plan limits the guarantee to finished blocks ("the block still being written keeps changing by nature") and it is a documented decision; live V4 shows finished blocks and their selection kept
- R2-2 [MAJOR] a `<think>` tag spanning a blank line was split across blocks - Static - Fixed: parseContent runs on the whole text before splitting; test (failed before)
- R2-3 [MINOR] `$$` opener with text on its line not recognised - Static - Fixed (odd count of `$$` per line opens/closes); test (failed before)
- R2-4 [MINOR] whitespace-only text gave a blank block - Static - Fixed; test (failed before)
- R2-5 [MINOR] aria-labelledby/describedby not rewritten in the pop-out clone - Static - Fixed; tests incl. id-prefix and regex-character ids (failed before)
- R2-6 [MINOR] ArtifactPanel: request never cleared on list error; toast twice under StrictMode - Static - Fixed: error toast and clear, clear before toast; tests (list error failed before)
- R2-7 [MINOR] new files not Prettier-formatted - Static - Fixed (prettier --write on this ticket's new files)
- R2-8 [MINOR] missing tests - Static - Fixed (think across blocks, whitespace, `$$` opener, aria ids, id prefixes, list error, one toast, filesAvailable)
- R2-9 [MINOR] Stop notice does not survive a reload - Static - Fixed: docs say so (the ticket allows the notice)
- R2-10 [NIT] MermaidDialog maxWidth literal - Static - Rejected: other dialogs pass literal sizes to Modal (e.g. maxWidth={560})
- R2-11 [NIT] casts and CSS - Static - Fixed: Markdown cast removed, double blank line removed; the clone cast and `.streaming-blocks` rule stay (needed by TypeScript and by the CSS-coverage test)
- R2-12 [NIT] cached last_model not updated after PATCH - Static - Fixed: cache updated after a successful PATCH; test (failed before)

### Round 1 - 2026-11-10
Verdict: Request changes (3 MAJOR, 6 MINOR, 1 NIT, one Haiku reviewer). Resolution: fixed 9, rejected 1. Checks: vitest 444/444, typecheck, lint, build; e2e: one run of the files spec failed right after the fixes and could not be reproduced (18 later runs of the specs all passed), so treat it as a possible flake; live V1-V5 pass again; streaming screenshot shows one bubble with the selection kept. Runtime changed.
- R1-1 [MAJOR] StreamingMarkdown.tsx - wrapper and blocks all had `message-content`, nested bordered bubbles while streaming - Static - Fixed: blocks use `streaming-block`; checked in the browser
- R1-2 [MAJOR] two components in one file - Static - Fixed: `StreamingBlock.tsx`
- R1-3 [MAJOR] ArtifactPanel.tsx - drawer opened on a stale cached list reported "File not found" - Static - Fixed: wait while refetching; test with a stale cache (failed before)
- R1-4 [MINOR] blocks.ts - trailing blank gave an empty block - Static - Fixed (blank-only pieces join their neighbour); test (failed before)
- R1-5 [MINOR] blocks.ts - inline code at line start taken as a fence - Static - Fixed; test (failed before)
- R1-6 [MINOR] block edge cases untested - Static - Fixed: tilde, indented, CRLF, list, table tests; docs say loose lists and tables are drawn per block until saved
- R1-7 [MINOR] MermaidDialog.tsx - cloned SVG duplicated ids - Static - Fixed: `lib/markdown/svg-ids.ts` prefixes ids and references; tests
- R1-8 [MINOR] resumeTurn blamed another chat on a same-chat double click - Static - Fixed; test (failed before)
- R1-9 [MINOR] banner hidden when the last turn has a reply even if resume_needed - Static - Fixed: shown whenever the server says so; test (failed before)
- R1-10 [NIT] toast wording on pages without a files drawer - Static - Rejected: it is the plan's decided text; replies are only drawn on chat pages and the home page


## Log
- 2026-11-10: created
- 2026-11-10: added to epic MYAI-53
- 2026-11-10: linked blocked_by MYAI-54
- 2026-11-10: linked blocks MYAI-64
- 2026-11-10: plan validated, 2 rounds
- 2026-11-10: linked blocks MYAI-73 (same code in send-turn, MessageList, Composer)
- 2026-11-10: autopilot started (batch); implemented; verified
- 2026-11-10: review round 1 resolved (9 fixed, 1 rejected); re-verify pass
- 2026-11-10: review round 2 resolved (10 fixed, 2 rejected); re-verify pass
- 2026-11-10: review round 3 resolved; loop clean; V3 intermittent (stop race, MYAI-73)
- 2026-11-10: batch-autopilot: shipped, base bugfix/start-chat-and-send, PR #103
- 2026-11-10: acceptance criteria reviewed against the recorded results (4 ticked, 2 left open)
- 2026-11-10: closed by the user after the PR merged into develop; 2 acceptance criteria left unticked as known limits (see Verification, Acceptance review)
