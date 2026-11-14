---
id: MYAI-30
title: "Legacy UI shows the \"[System Note]\" file list in user messages"
status: done
created: 2026-11-09
updated: 2026-11-09
links:
  relates_to: [MYAI-6, MYAI-21, MYAI-49]
---

## Description
Found while planning MYAI-21, which hides the router's attachment System Note in the React UI only. The legacy UI (`static/script.js`) still renders the stored user text, including `[System Note: The user has attached the following files ...]`. Only needed if the legacy UI is kept.

## Acceptance criteria
- [x] Legacy user bubbles don't show the System Note text
- [x] Attached files are still visible (chips or a short list)
- [x] Stored content and what the model receives are unchanged

## Plan

**Date:** 2026-11-09  **Status:** Validated  **Base:** origin/develop 6a13e04

### Objective
Mostly a correction: the legacy UI already strips the System Note from user bubbles. This plan confirms that with tests and closes the one real gap, showing attached files when the message has no `files` collection.

### Context
- Requirement: Description and Acceptance criteria above. The Description, written while planning MYAI-21, assumed the legacy UI shows the note. The code says otherwise.
- **AC1 is mostly met on develop.** `MessageManager.createMessageBubble` (`static/js/message-manager.js:37-40`) removes both note variants (`document_agent` and the older `read_file` wording) from user text, and `static/js/tests/test_message-manager.js:162-173` tests the `document_agent` variant. The regex is `[\s\S]*?\]`, which stops at the first `]`. For a file named like `r[1].pdf`, residue such as `x.pdf (ID: file-3)]` stays visible (the validator checked this in node), so AC1 isn't fully met.
- **AC2 is partly met.** `createMessageBubble` builds `combinedFiles` from `files` plus any `collections` of type `files` (message-manager.js:84-100) and renders `file-attachment-pill`s (lines 110-125).
  - On reload, `static/script.js` passes `files: turn.uploadedFiles` and `collections: turn.collections` (around lines 1031-1040). `uploadedFiles` is never persisted: it exists only on the live send path, and `messages` rows (`SELECT *`, message_ops.py:73) have no such field. So on reload the only file source is the `files` collection (written at router.py:344-349).
  - `collections` come from `db.get_woven_history` (`backend/database/wrapper/history_ops.py`), which attaches them only when the chat has an order map (per MYAI-6's Context).
  - So a user message whose files aren't in a loaded collection shows no pills once the note is stripped: the file names are lost from view.
- **AC3:** the stripping is display-only (`createMessageBubble`), and stored content is untouched.
- MYAI-6 (planned) adds `messages.attachments` (`[{file_id, name, size, mime_type}]`) to `GET /api/chats/<id>`. MYAI-21 (planned) does the same fallback for React by parsing the note's `- <name> (ID: <id>)` lines.
- Tests: `node --test static/js/tests/test_message-manager.js`, which needs `npm ci` at the repo root for jsdom.
- Rules:
  - `static/js/README.md`: tests in `static/js/tests/`.
  - AGENTS.md rule 1: keep READMEs accurate.
  - Keep legacy class names; no new inline-style rules beyond the existing markup.

### Approach
- **Fix the strip for AC1.** The router always appends the note at the end of the text (router.py:304, 321). Replace the two `[\s\S]*?\]` regexes with one rule: find the last occurrence of `\n\n[System Note: The user has attached the following files` (either wording) and cut from there to the end of the text. A `]` inside a file name then can't end the strip early. Test the `read_file` variant, a name containing `]`, and that user text with "[System Note:" mid-sentence (no `\n\n` prefix, or not at the end) is unchanged.
- **File fallback for AC2.** In `createMessageBubble`, for `role === "user"`:
  - Parse only the cut-off note block, never the user's own text, so a user-typed bullet like `- item (ID: x)` can't create a pill. Collect its lines with `/^- (.+) \(ID: ([^)]+)\)\]?$/gm` (the same pattern as MYAI-21; the last entry ends with `]`) into `noteFiles` as `{ name, file_id }`.
  - After `combinedFiles` is built from `files` and collections, if it's empty, use `noteFiles`.
  - The note-derived pills reuse the existing pill markup (`f.name`).
  - This is a deliberate display fallback, not error masking (AGENTS.md rule 5). A missing collection is a normal state today: `get_woven_history` returns no `collections` without an order map (history_ops.py:104-105). The note is the stored record of which files were attached, and showing it is display, not recovery from a failure. No logging, since it isn't an error.
- **Prefer structured attachments once MYAI-6 lands (conditional).** If MYAI-6 has merged, `static/script.js`'s history render passes `files: turn.attachments`, replacing the dead `turn.uploadedFiles`. If it hasn't, skip Step 2; the note fallback covers the gap.
- Rejected: stripping on the server, for the same reason as MYAI-21 (stored content must stay intact for the model).

### Steps
#### Step 1: Note-file fallback in the bubble
- **Files:** `static/js/message-manager.js` (modify): `createMessageBubble`.
- **Change:** as in Approach. Parse only when `role === "user"` and `text` contains `[System Note: The user has attached the following files`.
- **Verification:** Step 3 tests.

#### Step 2: Use stored attachments on reload (only if MYAI-6 has merged)
- **Files:** `static/script.js` (modify): the `createMessageBubble` call in the history render (around line 1038).
- **Change:** `files: turn.attachments`. Skip the step entirely if MYAI-6 isn't merged.
- **Verification:** the live check shows pills from `attachments` on a new chat after a reload.

#### Step 3: Tests
- **Files:** `static/js/tests/test_message-manager.js` (modify). Add the tests inside the same `describe` block as the existing stripping test, after it (around line 173), so they run after the shared JSDOM `setup` test.
- **Change:**
  - The `read_file` variant is stripped.
  - A note with a file named `r[1].pdf` is stripped completely (no `]` or `(ID:` residue).
  - A user bullet `- item (ID: x)` with no note creates no pill and stays in the text.
  - User text with "[System Note:" mid-sentence (no `\n\n` prefix) is unchanged.
  - A two-entry note with no `files` and no collections renders two `file-attachment-pill`s with both names, including the last entry, which ends in `]`.
  - With a `files` collection present, pills come from the collection and the note entries aren't duplicated.
  - The stored text passed in isn't mutated (the function works on a local copy).
- **Verification:** `npm ci` (repo root, once), then `node --test static/js/tests/test_message-manager.js`.

#### Step 4: Live check and docs
- **Change:** with a throwaway `DATA_DIR`, open the legacy UI with Playwright:
  - Send a message with a PDF; the bubble shows the text and a pill.
  - Reload; same result.
  - For a chat whose `files` collection is missing, the pill still shows. Create the fixture with the db wrapper against the throwaway `DATA_DIR`, not raw SQL (AGENTS.md rule 4): `venv/bin/python -c "from backend.database import db; db.ensure_chat_exists('t1'); db.add_message('t1', 'user', 'hi\n\n[System Note: The user has attached the following files. Use the `document_agent` tool with the provided file_id to read their contents if needed:\n- a.pdf (ID: f1)]')"`.
  - `GET /api/chats/<id>` still contains the note.
  No docs change: `static/js/README.md` describes `message-manager.js` as "Unified message bubble rendering and action lifecycle", which stays accurate, and the README has no detail on note handling.
- **Verification:** all pass; results go in Verification.

### Tests
- Precondition: `npm ci` at the repo root.
- `node --test static/js/tests/test_message-manager.js`
- `scripts/check.sh` (it doesn't run the legacy node tests, so run them explicitly).

### Risks and open questions
- **The ticket is smaller than it looked.** The legacy UI already hides the note in normal cases. The work is the `]`-in-name residue (AC1) and showing file names when no collection is loaded (AC2).
- **Note format contract.** As in MYAI-21, the router's note wording is now parsed in two UIs. Mitigation: MYAI-21 Step 1b adds a comment in router.py naming the parsers; extend it to name `message-manager.js`.
- No blocking open questions.

### Success criteria
- [ ] Legacy user bubbles don't show the System Note (both variants), proven by tests (Step 3)
- [ ] Attached files show as pills even without a `files` collection (Steps 1 and 3, live check)
- [ ] Stored content and what the model receives are unchanged (live check)

### Validation log
- Round 1 (2026-11-09, Haiku): PASS, 8 MINOR. My judgement: PASS. All 8 were valid and applied:
  - `uploadedFiles` is never persisted, so Step 2 now uses `attachments` and only if MYAI-6 has merged;
  - pills are parsed from the note block only (no spurious pills from user bullets; tested);
  - the strip now cuts from the note's start to the end of the text, fixing `]` in names (AC1 residue; tested);
  - the display-fallback rationale is stated against rule 5;
  - the live fixture uses the db wrapper;
  - the README row is confirmed accurate;
  - the test insertion point is named.

## Implementation notes

### Autopilot run (2026-11-09)
Batch 5 item. Branch bugfix/legacy-hide-system-note from origin/develop a1a9333, PR base develop. Dirty files before start: none. MYAI-6 has merged (`messages.attachments`), so Step 2 applies.

### Baseline (2026-11-09)
At develop a1a9333: `node --test static/js/tests/test_message-manager.js` 21 pass.

### Implementation progress
- [x] Step 1: `createMessageBubble` cuts the note from its last occurrence (prefix `\n\n[System Note: The user has attached the following files`, text must end with `]`), parses its `- name (ID: id)` lines into `noteFiles`, drops repeated `file_id`s, and uses `noteFiles` only when no files, attachments or collections are loaded
- [x] Step 2: static/script.js passes `files: turn.uploadedFiles || turn.attachments` at both history render sites
- [x] Step 3: 7 new tests (28 pass); three fail against develop's message-manager.js (`]` in a name, pills from the note, no repeated pill), checked with a scratch copy
- [x] Step 4: live check below; no doc change (static/js/README.md stays accurate)
Deviation: the legacy `formatMarkdown` stub in the test harness prefixes "[MD] ", so tests avoid asserting on a bare `]`.

### Smoke test (2026-11-09)
`node --test static/js/tests/test_message-manager.js` 28 pass; frontend and backend untouched, no other suite affected.
None yet.

PR: https://github.com/archit342000/My-AI/pull/71, branch bugfix/legacy-hide-system-note, base develop

## Verification
### Verification plan (2026-11-09, light form)
Real app (5099, DATA_DIR /tmp/myai30-data seeded through the db wrapper), the legacy UI at /legacy/, Playwright (`scripts/seed.py`, `scripts/ui.js`). Never touches :5000/:5001, containers, backend/data or a real chats.db.
| ID | Criterion | Scenario | Expected |
|----|-----------|----------|----------|
| V1 | AC1, AC2 | chat with a stored `attachments` field whose name differs from the note | note hidden, one pill with the stored name |
| V2 | AC1, AC2 | chat with the note only (no attachments, no collection) | note hidden, a pill per note entry |
| V3 | AC1 | file named `r[1].pdf` | no residue in the text, one pill |
| V4 | AC3 | GET /api/chats/<id> | stored content still has the note |
Not run yet.

### Results (2026-11-09)
**Commit verified:** a1a9333 (+ uncommitted). Hashes: message-manager.js 93cb09d9, test_message-manager.js de8d1e04, script.js c0c1237f.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | ui.log: text "please read these", pill `stored-attachment.pdf` (first run, same names: ui-run1.log) |
| V2 | PASS | ui.log: pills `b.pdf`, `c.docx` |
| V3 | PASS | ui.log: no residue, pill `r[1].pdf` |
| V4 | PASS | ui.log: stored content keeps the note |

No console errors; screenshots ui-a/b/c.png. Teardown: processes stopped, /tmp/myai30-data removed, ports free, containers and git status unchanged. The model-side input is unchanged by construction (display-only edit; the server is untouched). **Verdict: verified (4/4 PASS).**

## Review history
### Round 1 - 2026-11-09
Verdict: Approve with comments. Scope: origin/develop a1a9333..working tree, 3 files, single Haiku reviewer.
- R1-1 [MINOR] script.js:1038,1448 - `uploadedFiles || attachments` lets an empty array hide the stored attachments - Static - Fixed (`uploadedFiles?.length ? ... : attachments`)
- R1-2 [MINOR] message-manager.js:44 - the short prefix plus closing `]` also cuts a user-typed look-alike note - Static - Rejected: same rule as the React parser and the validated plan; a typed full look-alike note is an accepted edge case
- R1-3 [MINOR] comment claimed the same parse as chat-model.ts - Static - Fixed (comment states the shared rule and the newline-name difference)
- R1-4 [MINOR] de-duplication ran for every role - Static - Fixed (user messages only) plus an assistant-bubble test
- R1-5 [MINOR] edit textarea and copy still contain the note - Static - Deferred as pre-existing (those paths are untouched; the requirement names the bubbles); follow-up: strip the note for the textarea and copy only
- R1-6 [NIT] residue test did not assert the pill name - Static - Fixed
Resolution: fixed 4, rejected 1, deferred 1. Checks: 29 node tests pass. Runtime change in script.js and message-manager.js: live V1-V4 re-run, all PASS (ui-rerun.log).

## Log
- 2026-11-09: created (follow-up found while planning MYAI-17 to MYAI-25)
- 2026-11-09: linked relates_to MYAI-21 (same fix for the React UI)
- 2026-11-09: plan validated, 1 Haiku round.
- 2026-11-09: linked relates_to MYAI-6 (uses messages.attachments for pills once MYAI-6 merges)
- 2026-11-09: autopilot started (batch-autopilot)
- 2026-11-09: implemented, smoke tests pass
- 2026-11-09: verified live, 4/4 PASS
- 2026-11-09: review round 1 Approve with comments; fixed 4, rejected 1, deferred 1; live re-run PASS
- 2026-11-09: shipped, PR https://github.com/archit342000/My-AI/pull/71
- 2026-11-09: batch-autopilot: shipped, base develop
- 2026-11-09: linked relates_to MYAI-49 (follow-ups from batch 5)
- 2026-11-09: closed, PR merged
