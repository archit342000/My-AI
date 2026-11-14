---
id: MYAI-61
title: "Composer and attachments: button sizes, ghost chats, stale chips"
status: done
epic: MYAI-53
created: 2026-11-10
updated: 2026-11-10
links:
  blocked_by: [MYAI-56]
  conflicts_with: [MYAI-58]
---

## Description
The attach and tools buttons differ in size and shape, the send button and placeholder differ from legacy, uploading before sending leaves ghost chats and orphan files, chips follow the user into other chats and temporary mode, and drag-drop/paste upload is missing.

Findings (MYAI-52, Verification): A-47, A-48, A-49, A-50, A-51, A-52, A-53. Evidence and the live test rig are in `~/.claude/tickets/My-AI/MYAI-52-evidence/`.

## Acceptance criteria
- [ ] Attach and tools buttons match legacy (attach 36x40, tools 40x40, both round and aligned); send button and placeholder match legacy
- [ ] Abandoning staged files (New Chat, navigation, reload) leaves no chat row and no stored file
- [x] Chips never appear in a chat they were not uploaded for
- [ ] Files can be dropped on the chat area or pasted into the composer
- [ ] Tall input keeps its buttons bottom-aligned
- [x] `/help` shows the command list where the user can read it

## Plan
**Date:** 2026-11-10  **Status:** Validated

### Objective
Fix the composer's controls and file staging: matching attach and tools buttons, legacy send button and placeholder, no ghost chats or orphan files from abandoned uploads, chips that stay with the chat they were uploaded for, drop and paste upload, bottom-aligned buttons on a tall input, and a readable `/help`.

### Context
- **Requirement:** this ticket's Description and Acceptance criteria (findings A-47 to A-53 in MYAI-52).
- **Assumes merged:** MYAI-56 (a single `<Composer />` rendered by `app/RootLayout.tsx` for `/` and `/chat/:chatId`, chat id read with `useMatch`, text and staged files cleared through `onAccepted`).
- **Rules:** `docs/standards/frontend.md` (pure logic in `src/lib/` or feature modules with tests, hooks in their own files, components never call `fetch` directly, inline styles only with `// dynamic-style`, real buttons with accessible names, new user flows get a Playwright spec), `docs/frontend.md`.
- **Server facts:** `POST /api/files/upload` stores a file under the `chat_id` it is given; `GET /api/chats` lists chats that have content, and a stored file counts (`backend/chat/router.py` `list_chats`); `DELETE /api/files/<id>` removes a file.
- **Legacy reference:** `static/index.html`: placeholder "Start a conversation..."; `#attach-btn` and `#tools-button` are both `.input-action-btn` (40px round; `frontend/src/styles/legacy.css` narrows the attach button with `#attach-btn.input-action-btn { padding: 0; width: 36px }`, so legacy measures 36x40 and 40x40); the send button is disabled only while files upload (`static/script.js` `checkSendButtonState`), so it stays blue when the box is empty; `static/js/attachment-manager.js` handles drop on `#file-upload-zone`.
- **Current code (`frontend/src/`):**
  - `features/composer/Composer.tsx`: `#attach-btn` is an `IconButton` (32px, 8px radius) while `ToolsMenu`'s button is a raw `.input-action-btn`; placeholder "Type a message…"; the send button is `disabled` whenever `canSend` is false, which applies the legacy grey `.send-btn:disabled` look to an empty box; `attachments` is one list for the whole composer; `chatForUploads` gets a generated id on the first file picked on `/`; `/help` shows a 3 second toast.
  - `features/composer/attachments.ts` (pure helpers, tested), `AttachmentChip.tsx`, `api/files.ts` (`uploadFile`, `deleteFile`).
  - `app/Sidebar.tsx` `newChat`: discards the temporary chat and navigates to `/`; it does not touch staged files.
  - Measured (MYAI-52 `scripts/s7.mjs`): upload on `/` adds a "New Conversation" row; after New Chat the chip remains; after a reload the chip is gone and the row and file remain.

### Approach
- **Buttons and text as legacy.** `#attach-btn` becomes a raw `.input-action-btn` button like the tools button (keeping its id and the accessible name "Attach files"), which gives the legacy sizes (36x40 and 40x40) from the existing `legacy.css` rules with no new CSS. The placeholder is "Start a conversation...". The send button keeps the `disabled` attribute only while uploads run or no model is selected (when another chat is streaming it stays enabled and MYAI-56's refusal toast explains the block); with an empty box it uses `aria-disabled` and ignores clicks, so it keeps the blue look. The input row aligns its buttons to the bottom edge.
- **Staging per chat.** Staged files live in a new store `state/attachment-store.ts`, keyed by the chat they were uploaded for (`routeChatId`, the temporary chat id, or a draft id for the next new chat). The draft id lives in the store (`draftChatId`, replacing the composer's `chatForUploads` state), so it survives route changes; it is renewed after a send or a discard. The composer shows only the list for the open chat. The upload queue keeps running for every key.
- **Abandoned drafts are cleaned up.** `discardDraft(key)` deletes the uploaded files of that key through `deleteFile` and clears it. It runs for the unsent new-chat draft when the user presses New Chat or navigates away from `/` without sending (a draft staged in an existing chat is kept while the user looks at other chats: it belongs to a real chat and creates no row), when a temporary chat is discarded, and on `pagehide` (not persisted) for every key with unsent files, using a keepalive request so it survives the unload. Deleting the last file of a chat with no messages removes its row from the server's list; the chat list is refreshed.
- **Drop and paste.** A hook `features/composer/useFileDrop.ts` accepts files dropped on `<main>` while a composer is shown (with a visible drop state) and files pasted into the textarea; both go through the same `addFiles` path as the picker.
- **`/help`.** It opens a small dialog (`features/composer/HelpDialog.tsx`, built on `Modal`) listing the built-in commands and the user's skills from `slashCommandsFor`.
- **Rejected:** restoring chips after a reload from `sessionStorage` (the `File` objects are gone and half-processed uploads cannot be resumed; deleting is simpler and leaves nothing behind); keeping one global attachment list and clearing it on navigation (loses a draft when the user only peeks at another chat).

### Out of scope
- Image previews beyond the existing chip thumbnail, vision handling and upload limits.
- Mobile keyboard behaviour (MYAI-58) and the start-chat flow (MYAI-56).
- Backend changes (for example a server-side sweep of orphan files).

### Steps
#### Step 1: Attachment store
- **Status:** todo
- **Depends on:** none
- **Files:** `frontend/src/state/attachment-store.ts` (create: lists by key, `add`, `update`, `remove`, `clear`, `discardDraft`), `frontend/src/state/attachment-store.test.ts` (create), `frontend/src/api/files.ts` (modify: `deleteFile` accepts a keepalive option), `frontend/src/api/files.test.ts` (modify)
- **Change:** as in Approach ("Staging per chat", "Abandoned drafts are cleaned up": the store part).
- **Verification:** unit tests: lists are independent per key; `discardDraft` calls `deleteFile` for each uploaded file of that key only and empties it; a file still uploading is marked for deletion when it lands; the keepalive option reaches `fetch`.

#### Step 2: Composer uses the store
- **Status:** todo
- **Depends on:** 1
- **Files:** `frontend/src/features/composer/Composer.tsx` (modify: staging state, upload queue, draft key), `frontend/src/features/composer/Composer.test.tsx` (modify)
- **Change:** the composer reads and writes the list for the open chat's key (the id from `useMatch('/chat/:chatId')` as MYAI-56 leaves it, else the temporary chat id, else the draft id); sending clears that key only (through MYAI-56's `onAccepted`); the queue effect covers all keys.
- **Verification:** component tests: a file staged on `/chat/a` is not shown on `/chat/b` and is shown again on `/chat/a`; a file staged on `/` is not shown after entering temporary mode; sending on `/chat/a` leaves `/chat/b`'s staged file untouched.

#### Step 3: Clean up abandoned drafts
- **Status:** todo
- **Depends on:** 2
- **Files:** `frontend/src/app/Sidebar.tsx` (modify: `newChat` discards the new-chat draft), `frontend/src/app/RootLayout.tsx` (modify: its path-change effect discards the new-chat draft when the path leaves `/`; after a send the draft is already empty because `onAccepted` cleared it), `frontend/src/app/RootLayout.test.tsx` (modify), `frontend/src/features/chat/temporary-chat.ts` (modify: `discardTemporaryChat` discards its draft), `frontend/src/features/composer/useDraftCleanup.ts` (create: `pagehide` handler), tests next to each (`Sidebar.test.tsx`, `temporary-chat.test.ts` (modify), `useDraftCleanup.test.ts` (create)), `frontend/src/features/composer/Composer.tsx` (modify: call the hook)
- **Change:** as in Approach ("Abandoned drafts are cleaned up").
- **Verification:** unit and component tests: New Chat with a staged file on `/` calls `deleteFile` and invalidates the chat list; so does opening another chat from `/` with a staged file, while sending from `/` does not; a file staged in `/chat/a` survives a visit to `/chat/b`; a non-persisted `pagehide` deletes unsent files with keepalive and a persisted one does not; discarding a temporary chat deletes its staged files.

#### Step 4: Buttons, placeholder, send state, alignment
- **Status:** todo
- **Depends on:** 2
- **Files:** `frontend/src/features/composer/Composer.tsx` (modify), `frontend/src/features/composer/Composer.test.tsx` and `frontend/src/features/chat/ChatPage.test.tsx` (modify: placeholder text, send-state expectations), `frontend/e2e/chat-send.spec.ts` (modify only if it relies on the old placeholder), `frontend/src/styles/components.css` (modify: "Composer" block: row alignment, `aria-disabled` send state)
- **Change:** as in Approach ("Buttons and text as legacy").
- **Verification:** component tests: with an empty box the send button is not `disabled`, has `aria-disabled="true"` and a click sends nothing; during an upload it is `disabled`; the placeholder is the legacy text. Live (MYAI-52 rig, `node metrics.mjs d '/'`): `#attach-btn`, `#tools-button` and `#send-btn` show no difference from legacy (36x40, 40x40, 40x40).

#### Step 5: Drop and paste
- **Status:** todo
- **Depends on:** 2
- **Files:** `frontend/src/features/composer/useFileDrop.ts` (create), `frontend/src/features/composer/useFileDrop.test.tsx` (create), `frontend/src/features/composer/Composer.tsx` (modify: `addFiles` shared by picker, drop and paste), `frontend/src/styles/components.css` (modify: drop-state class in the "Composer" block)
- **Change:** as in Approach ("Drop and paste").
- **Verification:** component tests: dropping two files on the main area stages two chips; pasting a file into the textarea stages one and pasting text still inserts text; a drag without files shows no drop state.

#### Step 6: `/help` dialog
- **Status:** todo
- **Depends on:** 2
- **Files:** `frontend/src/features/composer/HelpDialog.tsx` (create), `frontend/src/features/composer/HelpDialog.test.tsx` (create), `frontend/src/features/composer/Composer.tsx` (modify: `/help` opens it), `frontend/src/features/composer/Composer.test.tsx` (modify)
- **Change:** as in Approach ("`/help`").
- **Verification:** component tests: `/help` opens a dialog listing `/help`, `/skills` and each skill with its description, and closes on Escape with focus back in the textarea.

#### Step 7: End-to-end spec, docs and full checks
- **Status:** todo
- **Depends on:** 3, 4, 5, 6
- **Files:** `frontend/e2e/composer-attachments.spec.ts` (create), `docs/frontend.md` (modify: State section: the attachment store and draft cleanup)
- **Change:** the spec mocks `/api/files/upload` and `DELETE /api/files/*`, stages a file on `/`, presses New Chat and reloads.
- **Verification:** the spec asserts the delete request was sent, no chip remains and no extra chat row appears; a dropped file shows a chip. Then from `frontend/`: `npm run typecheck`, `npm run lint`, `npm run test`, `npm run build`, `npm run e2e`; from the repo root `pytest tests` and `scripts/check.sh --frontend-only`.

### Tests
- Unit: `state/attachment-store.test.ts`, `api/files.test.ts`, `features/chat/temporary-chat.test.ts`, `features/composer/useDraftCleanup.test.ts`.
- Component: `Composer.test.tsx`, `useFileDrop.test.tsx`, `HelpDialog.test.tsx`, `Sidebar.test.tsx`, `ChatPage.test.tsx`.
- E2E: `e2e/composer-attachments.spec.ts`.

### Risks and open questions
- **A crash or a killed tab skips `pagehide`,** leaving a ghost chat as today; a server-side sweep would close that gap and is a backend change (out of scope; suggest a follow-up ticket if it matters).
- **`aria-disabled` on the send button** keeps it focusable; the click handler must stay a no-op when nothing can be sent.
- **Shared file:** `Composer.tsx` is also changed by MYAI-58 (linked as a conflict).

### Success criteria
- [ ] Attach and tools buttons match legacy sizes and are aligned; send button and placeholder match legacy
- [ ] Abandoned staged files leave no chat row and no stored file (New Chat, navigating away from an unsent new chat, leaving a temporary chat, reload)
- [ ] Chips appear only in the chat they were uploaded for
- [ ] Files can be dropped on the chat area or pasted
- [ ] Buttons stay bottom-aligned on a tall input
- [ ] `/help` opens a readable list
- [ ] Checks and the new spec pass
### Reviewer brief
- **Objective:** composer controls as legacy, no ghost chats or orphan files from abandoned uploads, chips scoped to their chat, drop and paste upload, bottom-aligned buttons, a readable `/help`.
- **Decisions:** attach button is a raw `.input-action-btn` (legacy sizes 36x40 beside the 40x40 tools button); legacy placeholder; empty box uses `aria-disabled` so the send button stays blue, `disabled` only for uploads or no model; staged files in `state/attachment-store.ts` keyed by chat with a store-held draft id; the unsent new-chat draft is deleted on New Chat, on leaving `/`, with a temporary chat, and on non-persisted `pagehide` (keepalive delete); drafts in existing chats are kept; `useFileDrop` for drop and paste; `/help` opens `HelpDialog`.
- **Out of scope:** image previews, vision and upload limits, mobile keyboard (MYAI-58), start-chat flow (MYAI-56), server-side orphan sweep.
- **Success criteria:** buttons match legacy sizes and align; send button and placeholder match legacy; abandoned staged files leave no chat row or file; chips only in their chat; drop and paste work; bottom-aligned buttons on a tall input; `/help` lists commands; checks and the new spec pass.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
- **Round 1:** validator FAIL (3 blocking, 2 minor). Judged FAIL. Valid: `legacy.css` `#attach-btn.input-action-btn { width: 36px }` means legacy's attach button is 36x40 (acceptance criterion and plan corrected to the legacy sizes); a disabled send button while another chat streams contradicted MYAI-56 (now stays enabled); navigation away from an unsent new chat was not cleaned up (now discarded in `RootLayout`'s path effect). Minors fixed: Step 6 dependency; chat id source named.
- **Round 2 (diff-scoped):** validator PASS (3 minor). Judged PASS. Fixed inline: draft id kept in the store; the "chat just sent" exception removed (the draft is already cleared by `onAccepted`); attach button keeps its id and accessible name.

## Implementation notes
Branch bugfix/composer-controls, base bugfix/start-chat-and-send (autopilot batch item 12).
### Implementation progress
- [x] Step 1: state/attachment-store.ts (+test), deleteFile keepalive (+test), lib/chat-id.ts
- [x] Step 2: Composer reads/writes the open chat's list; upload queue covers all chats; send clears only that chat and renews the draft id
- [x] Step 3: draft-cleanup.ts (New Chat, leaving `/`), temporary chat discard, useDraftCleanup (pagehide, keepalive)
- [x] Step 4: attach button is a raw `.input-action-btn`, legacy placeholder, send button aria-disabled when empty (disabled only for uploads / no model), buttons bottom-aligned
- [x] Step 5: useFileDrop (drop on `<main>`, drop state) and paste
- [x] Step 6: HelpDialog for `/help`
- [x] Step 7: e2e/composer-attachments.spec.ts, docs/frontend.md
Deviations: `generateChatId` moved to lib/chat-id.ts (re-exported from send-turn) so the store does not import a feature; the store resets in test setup.
### Smoke test (2026-11-10)
check.sh --frontend-only: typecheck, lint, 438 tests, build pass; e2e composer-attachments 4/4 twice; metrics at 1440px: attach, tools, send buttons no difference from legacy.
Not verified live: pagehide cleanup (unit tests only); a crash or killed tab still leaves a ghost chat (no server sweep, out of scope).

PR: https://github.com/archit342000/My-AI/pull/112, branch bugfix/composer-controls, base bugfix/start-chat-and-send

## Verification

### Acceptance review (2026-11-10)
Criteria ticked on the live and e2e results recorded in the PR's Testing section (checks run on throwaway backends during the autopilot run; scripts in `MYAI-61-evidence/`).
Left unticked, no PASS recorded:
- criterion 1: attach/tools/send sizes match legacy live; the placeholder was not compared
- criterion 2: New Chat cleanup verified; page-close cleanup is unit tests only
- criterion 4: drop verified; paste not verified
- criterion 5: tall input alignment not recorded as checked

## Review history
### Round 1 - 2026-11-10
Verdict: Request changes (5 MAJOR). Single Haiku reviewer.
- R1-1 [MAJOR] pagehide cleanup unmounted on routes without a composer - Fixed: `useDraftCleanup` runs in RootLayout; test on `/logs`.
- R1-2 [MAJOR] upload still running at close is never deleted - Deferred: the page is gone when it lands; needs a server-side sweep (out of scope, backend). Follow-up suggested.
- R1-3 [MAJOR] discarded draft left the skeleton chat row in the DB - Fixed: `discardNewChatDraft` also removes the draft chat (404 tolerated); tests.
- R1-4 [MAJOR] failed deletes silently swallowed - Fixed: toast with the count; test.
- R1-5 [MAJOR] an errored chip blocks send - Rejected: existing, tested behaviour (a failed chip must be removed or retried rather than silently dropped from the message); the new rule covers only uploads and a missing model as the ticket's plan says for the button's `disabled` state beyond that.
- R1-6 [MAJOR] lib/chat-id.ts had no test - Fixed.
- R1-7 [NIT] two import paths for generateChatId - Fixed (re-export dropped).
- R1-8 [MINOR] drop state stuck after a cancelled drag - Fixed: reset on window dragend/drop; test.
Resolution: check.sh passes (443 tests); e2e 4/4 re-run. Round 1 fixes were not re-reviewed.


## Log
- 2026-11-10: created
- 2026-11-10: added to epic MYAI-53
- 2026-11-10: linked conflicts_with MYAI-56
- 2026-11-10: linked conflicts_with MYAI-58
- 2026-11-10: link changed: blocked_by MYAI-56 (was conflicts_with; the plan builds on its single composer)
- 2026-11-10: acceptance criterion 1 corrected during planning: legacy's attach button is 36x40, not 40x40
- 2026-11-10: plan validated, 2 rounds
- 2026-11-10: acceptance criteria reviewed against the recorded results (2 ticked, 4 left open)
- 2026-11-10: closed by the user after the PR merged into develop; 4 acceptance criteria left unticked as known limits (see Verification, Acceptance review)
