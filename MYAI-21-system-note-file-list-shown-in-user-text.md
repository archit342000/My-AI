---
id: MYAI-21
title: "Stored user text shows the \"[System Note]\" file list"
status: done
created: 2026-11-09
updated: 2026-11-09
links:
  blocked_by: [MYAI-6, MYAI-20]
  relates_to: [MYAI-30]
---

## Description
Found while planning MYAI-6. The router appends a `[System Note: ...]` file list to the stored user message content so the model sees attachments. The UI shows that text in the user bubble. After MYAI-6 attachments are stored as structured `messages.attachments`, so the note can be hidden from display.

## Acceptance criteria
- [x] The user bubble does not show the System Note text
- [x] The model still receives the file information
- [x] Old messages without structured attachments still display sensibly

## Plan

**Date:** 2026-11-09  **Status:** Validated  **Base:** origin/develop 6a13e04  **Depends on (hard gates; don't start before both are merged):** MYAI-6 (`StoredMessage.attachments` mapped to `Turn.files: UploadedFile[]`) and MYAI-20 (the edit keeps the note server-side)

### Objective
Stop showing the `[System Note: The user has attached the following files ...]` block in React user bubbles and in the edit box. The stored content and what the model receives stay as they are. Messages that have no structured attachments still show which files were attached.

### Context
- Requirement: Description and Acceptance criteria above.
- The note is appended to the stored user text by `chat_completions` (`backend/chat/router.py:304, 321`):
  - Format: `\n\n[System Note: The user has attached the following files. Use the \`document_agent\` tool with the provided file_id to read their contents if needed:\n- <name> (ID: <file_id>)\n...]`.
  - It sits at the end of the plain string or of the first text part. The model reads it from the stored content.
- React display: `toTurns` and `parseUserContent` (`frontend/src/lib/chat-model.ts:37-56, 97-99`) return the raw text, which `UserTurn` (`frontend/src/features/chat/MessageList.tsx`) renders with `Markdown` and also uses as the edit `draft`.
- MYAI-6 (planned) adds `messages.attachments`, backfills it from existing `files` collections, and maps it to `turn.files` with chips in `UserTurn`. Messages whose files have no collection row stay without `files`.
- MYAI-20 (planned) re-appends the note server-side on edit when the draft lacks it. Without MYAI-20, a draft without the note would drop the file information when saved.
- Legacy UI (`static/script.js`) renders the stored text too. It's out of scope; this ticket is the React UI (the default since 5.0.0; see Risks).
- Tests: `frontend/src/lib/chat-model.test.ts`, `frontend/src/features/chat/MessageList.test.tsx`.
- Rules:
  - `docs/standards/frontend.md`: pure helpers in `lib/`, tests next to the source, no inline styles (the inline-style test baseline).
  - `docs/standards/testing.md`.

### Approach
- **Display-only strip.** Add a pure `splitAttachmentNote(text: string): { text: string; noteFiles: UploadedFile[] }` in `frontend/src/lib/chat-model.ts`.
  - It finds the last `\n\n[System Note: The user has attached the following files` block running to the end of the text.
  - It parses each line of the block with `/^- (.+) \(ID: ([^)]+)\)\]?$/`. The last entry ends with the closing `]` (`"\n".join(file_notes) + "]"`, router.py:304, 321).
  - Each match becomes `{ file_id, name, size: 0, mime_type: '' }`, the same defaults MYAI-6's `parseAttachments` uses for missing fields.
  - It returns the text before the block and the entries. The block is stripped even when no entry parses; a malformed note is still the router's note.
  - If no note is found, it returns the text unchanged with no entries.
- **Use it in `toTurns`** for user messages. `turn.text` becomes the stripped text.
  - If the turn has no MYAI-6 `files`, the parsed entries become `files`, with `file_id` set to the id and `name` set to the name. Old messages without structured attachments then still show chips with the same markup as MYAI-6.
  - If `files` exist, the parsed entries are ignored.
- **The edit draft uses the stripped text.** MYAI-20 keeps the note on save.
- Rejected alternatives:
  - Strip on the server when serving messages: the stored content must stay intact for the model, and the API would then differ from the DB.
  - Hide the note with CSS: it's plain text inside the Markdown, so there's no element to target.

### Steps
#### Step 1: Note parser
- **Files:** `frontend/src/lib/chat-model.ts` (modify): new exported `splitAttachmentNote`, with a doc comment.
- **Change:** as in Approach. It matches only the exact prefix the router writes, so user text that merely mentions "System Note" is untouched. Entries that don't match `- <name> (ID: <id>)` are skipped (for example a file name containing a newline, which splits across lines), while the block is still stripped.
- **Verification:** Step 3 tests.

#### Step 1b: Contract comment in the router
- **Files:** `backend/chat/router.py` (modify): a one-line comment above the two note-building lines (304, 321) saying the format is parsed for display by `splitAttachmentNote` in `frontend/src/lib/chat-model.ts`. The frontend parser gets the reverse comment. No behaviour change.
- **Verification:** `venv/bin/ruff check .`.

#### Step 2: Apply it in `toTurns`
- **Files:** `frontend/src/lib/chat-model.ts` (modify): `toTurns`, user branch.
- **Change:** keep `const { text: rawText, images } = parseUserContent(clean(m.content))`, then `const { text, noteFiles } = splitAttachmentNote(rawText)`. Set `text` on the turn. Set `files` to `parseAttachments(m.attachments)` (MYAI-6) when non-empty, otherwise to `noteFiles` (already `UploadedFile[]`). This needs MYAI-6's `Turn.files` field, so it can't compile before MYAI-6. `images` are unchanged.
- **Verification:** Step 3 tests.

#### Step 3: Tests
- **Files:** `frontend/src/lib/chat-model.test.ts` (modify); `frontend/src/features/chat/MessageList.test.tsx` (modify).
- **Change:**
  - `splitAttachmentNote`:
    - text with a two-entry note gives the clean text and both entries, including the last one, which ends in `]`;
    - a malformed note with no parseable entries is still stripped and gives no entries;
    - no note gives the text unchanged;
    - a user's own "[System Note:" mid-text is unchanged;
    - a note inside multimodal content (the first text part) is stripped.
  - `toTurns`:
    - a `StoredMessage` with `attachments` set gives a turn whose text has no note and whose `files` come from `attachments`;
    - a `StoredMessage` without `attachments` gives a turn whose `files` come from the note entries.
  - `MessageList`:
    - a stored user message with a note renders without "System Note" text and with the file chips;
    - opening Edit shows the stripped text in the textarea;
    - Save sends the stripped draft to `chatsApi.editMessage`. MYAI-20's server merge re-appends the note, which is why MYAI-20 is a hard gate. Save & regenerate goes through the same `editMessage` call and then MYAI-20's `resumeTurn`, which is covered by MYAI-20's tests.
- **Verification:** `cd frontend && npm run typecheck && npm run lint && npm run test`.

#### Step 4: Docs, full gate, live check
- **Files:** `docs/frontend.md` (modify): one bullet in `## Conventions`, after the `renderMarkdown` bullet, saying the router's attachment System Note is stripped from user bubbles and shown as file chips (parsed in `src/lib/chat-model.ts`).
- **Change:**
  - Run `scripts/check.sh`.
  - Live check in the React UI with Playwright and a throwaway `DATA_DIR`:
    - send a message with a PDF;
    - the bubble shows only the typed text and a chip;
    - reload: same result;
    - the stored message (`GET /api/chats/<id>`) still contains the note;
    - the model's reply can still use `document_agent` with the file id.
- **Verification:** all pass; results go in Verification.

### Tests
- Precondition: `npm ci` in `frontend/`.
- `cd frontend && npm run typecheck && npm run lint && npm run test && npm run build`
- `scripts/check.sh`
- Live check in Step 4

### Risks and open questions
- **Ordering (hard gate).** Start only after MYAI-6 and MYAI-20 are merged. Without MYAI-20, saving the stripped draft would drop the note and the model would lose the file ids.
- **No e2e spec.** `docs/standards/frontend.md` asks for a Playwright spec for new user flows. This is a display change in the existing send and edit flows, not a new flow, so unit tests plus the Step 4 live check cover it.
- **README check.** `frontend/README.md` lists `src/lib/` as "chat model" and doesn't describe message rendering or the edit draft, so no change is needed. Re-check after implementing (AGENTS.md rule 1).
- **Legacy UI still shows the note.** Out of scope (the React UI is the default). It could be a follow-up if the legacy UI is kept.
- **The note format is a contract between the router and the UI.** If the router's wording changes, the parser stops matching and the note shows again (fail-visible, not lossy). Mitigation: a comment in both places naming the other.
- No blocking open questions.

### Success criteria
- [ ] The user bubble and edit box don't show the System Note text (Steps 2-3, live check)
- [ ] The model still receives the file information; stored content is unchanged (live check)
- [ ] Old messages without structured attachments show the files as chips parsed from the note (Step 3)
- [ ] Tests and `scripts/check.sh` pass; docs updated

### Validation log
- Round 1 (2026-11-09, Haiku): FAIL, 3 BLOCKING and 7 MINOR. My judgement: FAIL is valid; I checked all 10.
  - B1: the stripped draft drops the note on save before MYAI-20. Valid. MYAI-20 is now a hard gate, with a save test.
  - B2: `UploadedFile` needs `size` and `mime_type` (completions.ts:27-32). Valid. Defaults 0 and ''.
  - B3: the last entry ends with `]`. Valid (router.py:304, 321). Regex specified, with a two-entry test.
  - M4: malformed note. Stripped anyway; tested.
  - M5: mixed `attachments`/`files` names. Fixed per layer.
  - M6: `Turn.files` needs MYAI-6. Hard gate stated.
  - M7: e2e spec. Justified as not a new flow.
  - M8: docs anchor. Named.
  - M9: README check. Recorded.
  - M10: save-path test. Added.
- Round 2 (2026-11-09, Haiku, diff-scoped): PASS, 4 MINOR. My judgement: PASS; all three round 1 BLOCKING items were confirmed resolved, and the regex was checked line by line against router.py.
  - M1: no `parsed` variable in `toTurns`. Valid. Variable named.
  - M2: the router comment was unscheduled. Valid. Step 1b added.
  - M3: regenerate path. Covered by MYAI-20; stated.
  - M4: newline in a file name. Stated under the malformed-note rule.

## Implementation notes
### Autopilot run (2026-11-09)
- Mode: automatic (batch-autopilot batch 3, item 2/2)
- Branch: bugfix/hide-system-note  PR base: develop  Starting commit: 77a0908
- Dirty before start: none
- Work files: frontend/src/lib/chat-model.ts, frontend/src/lib/chat-model.test.ts, frontend/src/features/chat/MessageList.test.tsx, backend/chat/router.py (comments only), docs/frontend.md
- Counters: fix 0/10, review 1/5, re-verify 1
- Last completed stage: 6 ship  Next: none
- Hard blocker: none
- WIP commit: none

### Autopilot decisions (2026-11-09)
- Stage 1: plan already Validated (2 rounds); reused, not re-planned. Its hard gates (MYAI-6 and MYAI-20) are merged (develop 77a0908).

### Baseline (2026-11-09)
At develop 77a0908: frontend vitest 281 pass (48 files); chat tests 140 pass; the other backend suites fail only on async tests (pytest-asyncio not installed in the venv).

### Implementation progress
- [x] Step 1: note parser - frontend/src/lib/chat-model.ts (`splitAttachmentNote`)
- [x] Step 1b: contract comments - backend/chat/router.py (above both note-building lines), chat-model.ts (the reverse)
- [x] Step 2: `toTurns` strips the note; `files` are the stored attachments, else the note's files
- [x] Step 3: tests - frontend/src/lib/chat-model.test.ts, frontend/src/features/chat/MessageList.test.tsx (bubble hides the note and shows the chip; the editor opens with the text only and saves it)
- [x] Step 4: docs - docs/frontend.md; full checks (see Smoke test); live check is the verify stage
Branch: bugfix/hide-system-note
Note: an image message's text still renders as `[object Object]` (the follow-up ticket's image-message item: `toTurns` stringifies the decoded content list), so for those messages the bubble shows that instead of the note; the multimodal-content case here is covered at the `toTurns` level with the JSON string form.

### Smoke test (2026-11-09)
vitest 291 pass (48 files), typecheck clean, lint only the existing forms.tsx warning, build ok; chat tests 140, tests 32, ruff clean; `scripts/check.sh --python-only`: only the baseline async-plugin failures.

PR: https://github.com/archit342000/My-AI/pull/62, branch bugfix/hide-system-note, base develop

## Verification
### Verification plan (2026-11-09, light form: one pure parser + `toTurns`, frontend only; stored data must stay intact)
**Diff base:** origin/develop 77a0908. **Scope:** `splitAttachmentNote` and `toTurns` in `frontend/src/lib/chat-model.ts` (React display only), contract comments in `router.py`, docs. Out of scope: the legacy UI, the `[object Object]` rendering of image messages (follow-up ticket).
**Environment and isolation:** this branch's app on 127.0.0.1:5099 with the built React frontend, `DATA_DIR=/tmp/myai21-data` (fresh DB), `AI_PROXY_URL=http://127.0.0.1:5098` (fake proxy, fast mode, logs every upstream request). Never touch :5000/:5001, containers, `backend/data` or a real `chats.db`. Teardown: kill PIDs, delete the temp dir, compare ports/containers/git status to the snapshot.
Scripts: `scripts/fake_proxy.py`, `scripts/ui.js` (Playwright, files as buffers).

| ID | Criterion | Scenario | Type | Method | Files | Expected |
|----|-----------|----------|------|--------|-------|----------|
| V1 | Bubble hides the note; the model still gets the file info | UI: send a message with one text file, then another with two files; reload | happy | browser + API + upstream log | chat-model.ts | bubble shows the typed text and chips only (no "System Note"), also after reload; `GET /api/chats/<id>` still returns the content WITH the note and `attachments`; the upstream request's user message contains the note with the file ids |
| V2 | Edit box shows the text only; the note survives an edit | UI: Edit that message, change the text, Save & regenerate | happy | browser + DB + upstream log | chat-model.ts, MessageList.tsx | textarea holds only the typed text; after saving the stored content has the new text and still the System Note (server merge), one user row, a new reply, the upstream request again has the note, chips still shown |
| V3 | Old messages without structured attachments display sensibly | take a message sent with a file and set its `attachments` to NULL in the throwaway DB (an old row); open it in the UI | regression | browser + DB | chat-model.ts | no System Note text; chips parsed from the note (file names) |
| V4 | Plain and look-alike text unchanged | UI: a message without files; a message whose own text contains "[System Note: x]" | edge | browser | chat-model.ts | both shown exactly as typed |
| V5 | Regression | vitest, typecheck, lint, build, chat/tests, tests dir, ruff | regression | CLI | all | only baseline failures |
| V6 | Edge cases from review round 1 (added 2026-11-09) | (a) an attachment-only message (empty-ish typed text) shows only chips, its edit box is empty and Save / Save & regenerate are disabled; (b) an edit whose draft contains a typed `\n\n[System Note: x]` keeps the router note in the stored content after Save | edge | browser + API + DB | chat-model.ts, MessageList.tsx, message_edit.py | (a) no System Note text, chips shown, textarea empty, both Save buttons disabled; (b) stored content = the draft followed by the router note with the file name |

### Results (2026-11-09)
Verified at HEAD 77a0908c1213e40eef728749b0129dfff4d2d677 plus uncommitted (hash prefixes): backend/chat/router.py 699b79a1, docs/frontend.md 3df42e40, frontend/src/features/chat/MessageList.test.tsx d577bb78, frontend/src/lib/chat-model.test.ts e6a92767, frontend/src/lib/chat-model.ts e8195f6f.
Isolation: app 127.0.0.1:5099 (DATA_DIR=/tmp/myai21-data, built React frontend), fake proxy 127.0.0.1:5098; :5000/:5001, containers, backend/data and any real chats.db untouched. Teardown: PIDs killed, 5098/5099 free, temp dir removed, containers and git status identical to the snapshot.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | v1-v4-ui.log, ui-v1-*.png: with one file and with two files the bubble shows the typed text plus chips only, before and after a reload; `GET`/DB still has the content WITH the System Note and the `attachments` list; the upstream request's user message contains the note with the file names |
| V2 | PASS | v1-v4-ui.log, ui-v2-after-edit.png: the edit box held only `please read my notes`; after Save & regenerate one user row with the new text, the System Note still in the stored content, one new reply, one upstream request with the new text and the note, chip still shown |
| V3 | PASS | v1-v4-ui.log, ui-v3-old-row.png: a row with `attachments` set to NULL (an old message) shows no System Note and chips `a.txt`, `b.txt` parsed from the note |
| V4 | PASS | v1-v4-ui.log: a plain message is unchanged with no chips; a message that mentions `[System Note: x]` in its own text is shown untouched |
| V5 | PASS | v5-regression.log: vitest 291, typecheck clean, lint only the existing warning, chat/tests 140, tests 32, ruff clean |

Verdict: verified. 5 of 5 pass, 0 FAIL, 0 BLOCKED. Browser console errors: none. Not covered: image attachments (an image message still renders as `[object Object]`, tracked in the follow-up ticket), the legacy UI (out of scope), a PDF.
Scripts: scripts/fake_proxy.py, ui.js.
### Results (re-run 1, 2026-11-09)
Re-run after review round 1 fixes (full router prefix in the edit helper, strip only when the text ends with `]`, newline-tolerant parsing, Save disabled for an empty draft, chip keys, tests, comments). HEAD 77a0908c1213e40eef728749b0129dfff4d2d677 plus uncommitted: see the hash line in rerun1/ evidence summary below. Frontend rebuilt first; fresh throwaway state (app 5099, fake proxy 5098); ports free afterwards, containers and git status identical to the snapshot. Evidence in rerun1/.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | rerun1/v1-v4-ui.log: one file and two files, bubble shows the typed text plus chips only, also after reload; stored content still has the note and `attachments`; the upstream request has the note |
| V2 | PASS | rerun1/v1-v4-ui.log: the edit box held only the typed text; after Save & regenerate the stored content has the new text and the System Note, one user row, a new reply, one upstream request with the note, chip shown |
| V3 | PASS | rerun1/v1-v4-ui.log: an old row (`attachments` NULL) shows chips parsed from the note and no System Note |
| V4 | PASS | rerun1/v1-v4-ui.log: plain text and a `[System Note: x]` look-alike unchanged |
| V5 | PASS | rerun1/v5-regression.log: vitest 294, typecheck clean, lint only the existing warning, chat/tests 142, tests 32, ruff clean |
| V6 | PASS | rerun1/v6.log, ui-v6a-attachment-only.png: (a) an attachment-only message shows only its chip, the edit box holds no text and Save and Save & regenerate are disabled; (b) a PUT whose draft contains a typed `[System Note: typed by me]` stores the draft followed by the router note with `keep-me.txt` and the file id, and `attachments` kept |

Verdict: verified. 6 of 6 pass, 0 FAIL, 0 BLOCKED. Browser console errors: none. Not covered: image attachments (still `[object Object]`, tracked in the follow-up ticket), the legacy UI, a PDF.
Scripts: scripts/fake_proxy.py, ui.js, v6.js.

## Review history
### Round 1 - 2026-11-09
Verdict: Request changes (2 MAJOR). Scope: 5 uncommitted files vs 77a0908 (small mode, one Haiku reviewer given the Description, Acceptance criteria and the plan's Objective/Approach/Out of scope/Success criteria). Findings checked against the code; R1-2 reproduced by calling the helper (a draft containing `[System Note: x]` comes back without the router note).
- R1-1 [MAJOR] frontend/src/lib/chat-model.ts:106 - two non-null assertions (`match[2]!`, `match[1]!`); docs/standards/frontend.md:17 forbids `!` - Static - Fixed: `matchAll` destructured with defaults, no `!`, chat-model.ts
- R1-2 [MAJOR] backend/chat/message_edit.py `_with_note`/`_split_note` - the server detects "already has a note" with the short marker `\n\n[System Note:` while the client strips only the full router prefix; now that drafts no longer carry the note, a draft containing a typed `\n\n[System Note:` makes the server skip re-appending the router note, so the stored message loses the file ids the model needs (and a stored typed marker is mistaken for the router note) - Fixed: message_edit.py uses the full router prefix for both the note split and the already-has-note check (tests written first and failed before the fix), message_edit.py, test_message_edit.py
- R1-3 [MINOR] chat-model.ts `splitAttachmentNote` - text containing the full prefix is cut to the end even when it is not a router note, hiding the suffix from the bubble and edit box (which the server then re-appends on save); only strip when the block ends with `]` as the router writes it - Static - Fixed: strip only when the text ends with `]` (the router's note), tests, chat-model.ts
- R1-4 [MINOR] chat-model.ts:92 - the per-line regex drops a chip for a file name containing a newline - Static - Fixed: lazy `[\s\S]+?` entry regex tolerates a newline in a name, test, chat-model.ts
- R1-5 [MINOR] MessageList.tsx edit box - for an attachment-only message the draft is now empty, so Save and Save & regenerate send empty content and get a 400 "Content required" toast; disable them for an empty draft - Static - Fixed: Save and Save & regenerate disabled and `save()` returns for an empty draft, test, MessageList.tsx
- R1-6 [MINOR] send-turn.ts `historyFromCache` - the wire `messages` history now carries stripped text; the server reads only `messages[-1]`, so no model effect, but it is undocumented: add a comment - Static - Fixed: comment in historyFromCache that the server ignores prior history, send-turn.ts
- R1-7 [MINOR] chat-model.test.ts - the multimodal test name says "first text part" but parsing joins all text parts; the router writes one text part - Static - Fixed: multimodal test names the single-text-part router shape, chat-model.test.ts
- R1-8 [MINOR] chat-model.test.ts:3 and MessageList.test.tsx - added lines over 100 columns (docs/standards/frontend.md; the files already fail prettier at the base, only my added lines are in scope) - Static - Fixed: my added lines wrapped to 100 columns (long note string literals left whole), chat-model.test.ts, MessageList.test.tsx, MessageList.tsx
- R1-9 [NIT] router.py:311/329 and chat-model.ts:143 - the contract comment is duplicated and over 100 columns - Static - Fixed: one short contract comment per router branch naming splitAttachmentNote and message_edit.py, router.py
- R1-10 [NIT] chat-model.ts:86-92 - the JSDoc says the last line ends with `]` but the regex made it optional; the comments should also name message_edit.py - Static - Fixed: JSDoc and regex agree (the note ends with `]`) and name message_edit.py, chat-model.ts
- R1-11 [NIT] chat-model.test.ts - the "user-typed System Note mention" test does not contain the prefix, so it would pass with a naive check - Static - Fixed: tests for a typed full prefix without a closing `]` and for a user-typed mention, chat-model.test.ts
- R1-12 [NIT] MessageList.tsx chips keyed by `file_id`, which can repeat for note-parsed files - Static - Fixed: chips keyed `${i}:${file_id}`, MessageList.tsx
Dismissed: none. Pre-existing: none.

Resolution: 12 Fixed, 0 Rejected. Runtime behaviour changed by R1-2 (backend/chat/message_edit.py) and R1-1/3/4/5/12 (frontend/src/lib/chat-model.ts, frontend/src/features/chat/MessageList.tsx): live re-verify of V1-V4 needed. Checks: chat/tests 142, tests 32, ruff clean; vitest 294, typecheck clean, lint only the existing warning, build ok.


## Log
- 2026-11-09: created (follow-up found while planning MYAI-2 to MYAI-16)
- 2026-11-09: plan validated, 2 Haiku rounds.
- 2026-11-09: linked blocked_by MYAI-6 (needs Turn.files and messages.attachments from MYAI-6)
- 2026-11-09: linked blocked_by MYAI-20 (the stripped draft relies on MYAI-20 re-appending the note on edit)
- 2026-11-09: linked relates_to MYAI-30 (same fix for the React UI)
- 2026-11-09: autopilot started (batch-autopilot)
- 2026-11-09: implemented, smoke tests pass (only baseline async-plugin failures)
- 2026-11-09: verified: 5 PASS, 0 FAIL, 0 BLOCKED
- 2026-11-09: review round 1: Request changes (2 MAJOR, 6 MINOR, 4 NIT)
- 2026-11-09: review round 1 resolved: 12 fixed; runtime files changed, re-verify needed
- 2026-11-09: re-verified after review fixes: 6 PASS (V6 added), 0 FAIL, 0 BLOCKED
- 2026-11-09: PR opened #62 (batch-autopilot: shipped, base develop)
- 2026-11-09: PR #62 merged into develop; closed
