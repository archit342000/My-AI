---
id: MYAI-49
title: "Batch 5 follow-ups: PDF page numbers, reindex, indexing gate, legacy edit/copy"
status: todo
created: 2026-11-09
updated: 2026-11-20
links:
  relates_to: [MYAI-12, MYAI-30]
---

## Description
Open items left by the merged batch 5 PRs (#67 to #71), found in review and verification.

1. **PDF page numbers.** Since the RAG text fix, PDF chunks get `page_number` metadata, but when a page's text has only single newlines (what PDF extraction yields) the chunkers report line 1 for every chunk, so later pages' chunks get `page_number` 1. With blank-line paragraph breaks the numbers resolve per page. Fix idea: map chunks to pages by their position in the text, not by line number.
2. **Existing RAG chunks.** Files indexed before the fix keep JSON chunks (and PDFs have no `page_number`). There is no reindex path (`_process_file_background` skips files that already have `content_text`). Fix idea: a one-off script (read `content_text`, `FileRAG.delete_file`, `store_file`).
3. **Short-content gate.** The 50-character gate in `FileRAG.store_file` and its callers in `backend/files/manager.py` measure the stored JSON wrapper, not the text that is indexed, so a very short text file passes. Pre-existing.
4. **Legacy edit and copy.** The legacy UI's edit textarea and copy action still contain the "[System Note: ...]" block (they read the stored content). Fix idea: strip the note for those two paths only; `backend/chat/message_edit.py` re-appends the stored note when the edited text lacks it.

## Acceptance criteria
- [ ] Chunks of later PDF pages carry the right `page_number` even when page text has no blank lines
- [ ] A documented or scripted way to reindex files indexed before the JSON fix
- [ ] The short-content gate measures the text that is indexed (or is recorded as intended)
- [ ] The legacy edit textarea and copy do not include the System Note, stored content unchanged

## Plan

**Date:** 2026-11-20  **Status:** Draft - unresolved issues

### Objective
Make RAG chunks of PDFs carry the page they come from, give operators a way to re-index files that were indexed before the page/text fix, make the short-content gate measure the text that is actually indexed, and keep the "[System Note: ...]" attachment block out of the legacy UI's edit box and copy action without changing stored content.

### Context
- Requirement: the four items and acceptance criteria of this ticket. Assumption: re-indexing is an operator command (like `backend.auth.cli`), not an API route or a startup migration.
- Rules: `AGENTS.md` (config in `backend/config.py`, `db` for SQL, `log_event`, 1:1 tests, no masked errors); `docs/standards/testing.md`; `docs/standards/errors-and-logging.md`; `docs/data.md` (Vector store; `RAGManager` owns collections); `docs/frontend.md:5,19` (legacy UI kept for one release).
- PDF text: `backend/files/pdf_extractor.py` `extract_with_pymupdf` stores `{"format":"pages","pages":[...]}` with each page stripped. `backend/rag/file_rag.py` `FileRAG.store_file` runs `strip_page_markers(content_to_index_text(content_text))` (`backend/rag/chunking.py`), which returns the clean text and `page_map` (first clean line of each page). Chunks get `page_number` from `resolve_page_number(chunk.line_start, page_map)`.
- Cause of the bug: `chunk_document_text` (and `chunk_mixed_text`) split on blank lines and give every sentence/word sub-chunk of a paragraph the paragraph's first line; extractor pages have no blank lines, so the whole PDF is one paragraph and every chunk resolves to page 1. `backend/rag/tests/test_file_rag.py` `test_store_file_indexes_page_json_as_page_text_with_page_numbers` passes only because its pages end in `"\n"`.
- Gate: `FileRAG.store_file` returns `[]` when `len(content_text.strip()) < 50`, measured on the stored JSON wrapper; `backend/files/manager.py` repeats `len(content_text.strip()) > 50` before calling `store_file` in `upload_file`, `upload_file_async` and `_process_file_background`.
- Re-index: `_process_file_background` skips files that already have `content_text`; `FileRAG.delete_file(file_id)` (sync, returns `RAGStore.cleanup`'s bool) and `await FileRAG.store_file(file_id, chat_id, content_text, filename)` exist; `RAGStore.store` (`backend/rag/store.py`) falls back to lexical-only when embeddings fail and logs upsert errors without raising. Managers are built as in `backend/tools/agents/document_agent/tools.py` `_get_managers` (`RAGProvider.get_manager`). `backend/auth/cli.py` is the CLI pattern (argparse, `main(argv) -> int`, `init_db()`, tests in `backend/auth/tests/test_cli.py`). Files rows are read in `backend/database/wrapper/artifact_ops.py` (`get_file`, `get_chat_files`); no "all files" query exists. Image, video and audio files store a placeholder as `content_text`, which the upload path keeps out of RAG with `is_media`.
- Legacy UI: the note is stripped for display inline in `static/js/message-manager.js` `createMessageBubble` (which also parses its file list for the attachment pills); `editMessageAction` puts the raw first text part into the textarea; `static/script.js` `.copy-msg-btn` handler copies the raw text. Legacy edit sends the textarea text as a new message after `DELETE`ing the old one (`sendMessage`, "Phase 0"), so the note text is what keeps the attachments on the edited message. For images the router appends the note to the first text part of a multimodal list.
- Rules: `AGENTS.md` (config in `backend/config.py`, `db` for SQL, `log_event`, 1:1 tests, no masked errors); `docs/standards/testing.md`; `docs/standards/errors-and-logging.md`; `docs/data.md` (Vector store; `RAGManager` owns collections); `docs/frontend.md` (legacy UI kept for one release).

### Approach
- Pages: for page-based content detected as `document`, `mixed` or `unknown` (the types that go to the paragraph chunkers), chunk each page on its own and stamp that page's number on its chunks, instead of mapping line numbers back to pages. A new `split_pages(clean_text, page_map)` in `chunking.py` returns `(page, text)` pairs; `store_file` runs the chosen chunker per page and numbers chunks sequentially across pages, so no such chunk spans two pages. Page-based content detected as `spreadsheet` or `code` keeps today's whole-text chunking (the spreadsheet chunker takes its header from the first line, which per-page input would break). Rejected: fixing line tracking in every chunker (four chunkers, sub-chunk line accounting, larger change).
- Gate: `store_file` keeps its cheap first checks (not initialised, empty, raw length under `FILE_RAG_MIN_CONTENT_CHARS`, so short malformed content is still skipped silently; the hard-coded 50 is replaced by the setting) and then also returns `[]` when the clean text after `content_to_index_text` and `strip_page_markers` is shorter than `FILE_RAG_MIN_CONTENT_CHARS` (new in `backend/config.py`, default 50; a text of exactly 50 characters is indexed, as `< 50` does today). The manager's three call sites keep `not is_media` and drop only their own `> 50` length check, leaving the length decision to `store_file`. PDF extraction gates (`PDF_EXTRACTION_MIN_CONTENT`, `pdf_extractor.py`) decide OCR fallback, not indexing, and stay.
- Re-index (redesigned twice: anything that relied on `RAGStore.store`, which swallows embedding and upsert failures, could not tell a real replacement from a partial one): embed first, then write, then prune. `store_file`'s chunk building moves into `FileRAG.build_chunks(file_id, chat_id, content_text, filename=None, timestamp=None, file_type_override=None) -> (documents, metadatas, ids)` (same gate, page handling and ids; `store_file` keeps working through it). A new `async FileRAG.reindex_file(file_id, chat_id, content_text, filename) -> str` returns `"reindexed"`, `"skipped"` or `"failed"`: it builds the chunks; with none (below the gate) it deletes the file's old chunks through `delete_file` and returns `"skipped"`, or `"failed"` when `delete_file` returns false; otherwise it awaits `rag_manager.embed_texts(documents, task="document")` and returns `"failed"` before writing anything if that raises or returns a different number of vectors than documents; the new chunks get fresh ids for this run (`<file_id>_r<run>_chunk_<i>`, `<run>` a millisecond timestamp), so the writes never merge into old rows or their metadata; it writes them to `vector_collection` (with the embeddings) and `bm25_collection` in batches of `config.CHROMA_UPSERT_BATCH_SIZE` (a new setting in `backend/config.py`, default 100, the value `RAGStore.store` falls back to today through `getattr`); if any write raises, it deletes the new ids it wrote from both collections and returns `"failed"`; otherwise it deletes the file's older ids from both collections and returns `"reindexed"`. The older ids are read once per collection before any write (`get(where={"file_id": ...})`), and only that snapshot is deleted; when a snapshot is empty its delete is skipped (Chroma rejects an empty id list). A failed delete after the writes is logged and returns `"failed"` with the new set in place and some old rows left, which a rerun removes. `build_chunks` errors (an invalid stored payload) propagate and the CLI counts them as failures. Invariant: the file's old chunks stay in place until the full new set is in both collections, and a failed run leaves only the old set. The CLI `python -m backend.files.cli reindex [--file-id ID]` lists files with `db.get_indexable_files(file_id=None)` (`id, chat_id, original_filename, mime_type, content_text`), skips media (their `content_text` is a placeholder, as the upload path's `is_media` check assumes), runs `reindex_file` for each with `asyncio.run`, catches any exception per file (a per-file boundary: one bad file must not stop the run; the exception is logged, counted and not hidden) and logs it with `log_event("file_reindex_error", {"file_id", "error": error_detail(e)})` as a failure, prints the three counts to stdout and each failure's file id to stderr, like `backend/auth/cli.py` (owner decision 1: operator CLIs under `backend/*/cli.py` may print), and exits 1 when any file failed or a given `--file-id` is not found. It is an operator command for an app that is not running: the documented procedure stops the app, runs the command in a one-off container (`docker compose -f docker/docker-compose.yml run --rm app ...`) and starts the app again; nothing in the code enforces that. Re-indexing all files also gives old PDFs page numbers. New public functions get type hints and docstrings (`docs/standards/python.md`).
- Legacy (redesigned after two rounds: a note kept in UI state outlived the edit): a shared `splitSystemNote(text)` helper (moved out of `createMessageBubble`, exposed as `window.MessageManager.splitSystemNote`) returns `{text, note, files}` (`files` is the list it parses today for the attachment pills, `noteFiles`), removing every note block (an edit that adds files makes the router append a second one) and returning them joined as `note`. For array (multimodal) content, edit and copy apply it to the first text part, as `backend/chat/message_edit.py` does. Copy uses the stripped text. Edit shows the stripped text and records the note together with the chat it belongs to: `editNote = {chatId, note}` in `script.js` module scope, set through a new `deps.setEditNote` on every edit (`note` empty when the message has none). In `sendMessage`, only on the user-initiated path (after the `isGenerating` guard and the `/help` and `/skills` interceptors, and only when it is not a resume, reattach or approved-plan call), before Phase 0: `const note = editNote && editNote.chatId === currentChatId ? editNote.note : ""` is read and `editNote` is set to null; `const sentContent = content + note` is then used wherever `content` built the user message (the chat title keeps using `content`). `loadChat`, `loadWorkspace` and `startNewChat` also set `editNote` to null. `sentContent` (not `content`) is what the empty-message check tests, so an edit sent with an empty textarea still sends the note as it does today (the textarea used to hold it), and Phase 0 runs exactly as now. Invariants: a note is appended only to the next user send in the same chat after an edit, with no chat change in between; internal sends (resume, reattach, approved plan) never consume or carry it; Phase 0 and the empty-message check behave as today. This mirrors `backend/chat/message_edit.py` (the note is re-appended to the edited text). Stored content is unchanged.

### Out of scope
- Running the re-index on the live data (an operator step after deploy).
- The OCR/extraction gates in `pdf_extractor.py` and `manager._extract_pdf_content`.
- The older `RAGManager.chunk_text` chunker and line metadata for non-page files.
- React UI (already strips the note: `splitAttachmentNote` in `frontend/src/lib/chat-model.ts`).

### Steps
#### Step 1: Per-page chunking for page-based files
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/rag/chunking.py` (modify: new `split_pages`); `backend/rag/file_rag.py` (modify: `FileRAG.store_file`); `backend/rag/tests/test_chunking.py`, `backend/rag/tests/test_file_rag.py` (modify)
- **Change:** `split_pages` slices the clean text by the start lines in `page_map` and drops empty pages. In `store_file`, when `page_map` is non-empty and the detected type is `document`, `mixed` or `unknown`, chunk each page's text with the chosen chunker and set `page_number` to that page on each of its chunks (no line metadata, as today); chunk ids and `chunk_index` stay sequential from 0. Other types and non-page content are unchanged.
- **Verification:** new test with extractor-shaped pages (stripped, single newlines, large enough to split) asserts chunks of page 2 and 3 carry `page_number` 2 and 3 and ids are `<id>_chunk_0..n`; a spreadsheet-shaped PDF still chunks as one text; `split_pages` tests for empty pages and a single page; existing `test_file_rag.py` and `test_chunking.py` pass.

#### Step 2: Gate on the indexed text, in one place
- **Status:** todo
- **Depends on:** Step 1
- **Files:** `backend/config.py` (modify: `FILE_RAG_MIN_CONTENT_CHARS`); `backend/rag/file_rag.py` (modify: `store_file`); `backend/files/manager.py` (modify: `upload_file`, `upload_file_async`, `_process_file_background`); `backend/rag/tests/test_file_rag.py`, `backend/files/tests/test_manager.py`, `backend/tests/test_config.py` (modify)
- **Change:** as in Approach (Gate): the first checks stay in place except that the raw-length check compares with `FILE_RAG_MIN_CONTENT_CHARS` instead of the hard-coded 50 (the raw text is never shorter than the clean text, so it only skips what the clean check would also skip), then the clean-text check against `config.FILE_RAG_MIN_CONTENT_CHARS`; the three manager call sites keep `not is_media` and drop their `> 50` check, and `upload_file_async` treats an empty result from `store_file` as the gate's normal skip (an info `log_event`, no `RuntimeError` and no warning).
- **Verification:** a text file whose text is 25 characters (wrapper over 50) is not indexed; one with exactly 50 characters is; an image upload is still not indexed; a short text upload through `upload_file_async` logs no warning; with the setting patched to 10, a 15-character text is indexed; manager tests that asserted the old `> 50` branch are updated and pass; `test_store_file` and `test_store_file_page_based` in `backend/rag/tests/test_file_rag.py` (which patch `strip_page_markers` to return a 10-character text) are updated to a text above the gate; `backend/tests/test_config.py` covers the new setting.

#### Step 3: Query for files to re-index
- **Status:** todo
- **Depends on:** none
- **Files:** `backend/database/wrapper/artifact_ops.py` (modify: new `get_indexable_files`); `backend/database/wrapper/tests/test_artifact_ops.py` (modify)
- **Change:** `get_indexable_files(file_id=None)` returns `id, chat_id, original_filename, mime_type, content_text` for rows with non-empty `content_text`, optionally one id, ordered by id; no cache.
- **Verification:** tests: rows without content are skipped, the id filter works, an unknown id gives `[]`.

#### Step 4: Re-index without losing chunks, and the command
- **Status:** todo
- **Depends on:** Steps 1, 2, 3
- **Files:** `backend/config.py` (modify: `CHROMA_UPSERT_BATCH_SIZE`); `backend/tests/test_config.py` (modify); `backend/rag/file_rag.py` (modify: new `build_chunks`, `reindex_file`; `store_file` uses `build_chunks`); `backend/rag/tests/test_file_rag.py` (modify); `backend/files/cli.py` (create); `backend/files/tests/test_cli.py` (create)
- **Change:** as in Approach (Re-index). Older ids come from `vector_collection.get(where={"file_id": ...})` and `bm25_collection.get(...)` and are removed with `delete(ids=[...])`. The CLI follows `backend/auth/cli.py` (argparse, `main(argv) -> int`, `init_db()`, an `if __name__ == "__main__"` guard), builds `FileRAG` as `backend/tools/agents/document_agent/tools.py` `_get_managers` does, and exits 2 when `FILE_RAG_ENABLED` is false.
- **Verification:** `reindex_file` tests on a store pre-seeded with the file's old chunks under the same ids: with more, equal and fewer new chunks both collections end with exactly the new chunks (new text, and metadata keys exactly as a fresh `store_file` would write them); with `embed_texts` raising or returning too few vectors, both collections keep the old rows unchanged and the result is `"failed"`; with the BM25 write raising after the vector write succeeded, both collections hold only the old rows and the result is `"failed"`; with `CHROMA_UPSERT_BATCH_SIZE` patched to 2 and five chunks, each collection gets three write calls of sizes 2, 2 and 1; a file with no old chunks is written and no delete is called; a below-gate file ends with no chunks and `"skipped"`, and a false `delete_file` gives `"failed"`. CLI tests with a mocked `FileRAG` and db: media skipped, `--file-id` limits to one, an unknown `--file-id` exits 1, an exception for one file is logged as `file_reindex_error`, printed to stderr, and the rest continue with exit 1; the stdout counts line is asserted; disabled RAG exits 2 without touching anything. `build_chunks` tests (gate, page numbers, ids, the `timestamp` and `file_type_override` arguments); `store_file` tests still pass.

#### Step 5: Legacy note helper, copy and edit
- **Status:** todo
- **Depends on:** none
- **Files:** `static/js/message-manager.js` (modify: `splitSystemNote` on the `MessageManager` object, used by `createMessageBubble` and `editMessageAction`, which calls `deps.setEditNote`); `static/script.js` (modify: `editNote` variable and its setter in the `MessageManager.init` deps, `.copy-msg-btn` handler, `sendMessage`); `static/js/tests/test_message-manager.js`, `static/tests/test_script.js` (modify)
- **Change:** as in Approach (Legacy). `splitSystemNote` applies the existing marker logic (prefix, trailing `]`) repeatedly from the end until no note block is left, and returns `{text, note, files}`: `note` is the removed blocks as stored (with their leading blank lines), `files` the file list parsed from them as `createMessageBubble` does today for the pills. Copy copies `text`. `sentContent` is trimmed like `content` when the edited text is empty, so a note-only send stores the note without a leading blank line, as today.
- **Verification:** node tests: helper splits and leaves note-less text alone, and removes two note blocks; edit and copy of an array (image plus attachment) message show no note; the edit textarea has no note; an edit send in a saved chat and in a temporary chat carries the note once; a send after New chat, after opening another chat, or after leaving and returning to the chat carries no note; a resume, reattach or `/help` does not consume it; editing a message without a note after one with a note sends no note; an edit sent with an empty textarea sends the note alone, as today; `chatHistory[index].content` still holds the note after edit and copy; copy writes text without the note; attachment pills of an edited message survive the edit send and a reload (the re-appended note carries the file list); existing display tests pass (`node --test static/tests/test_script.js static/tests/test_logs.js` and `node --test static/js/tests/test_message-manager.js`).

#### Step 6: Docs
- **Status:** todo
- **Depends on:** Steps 1-5
- **Files:** `docs/standards/errors-and-logging.md` (modify: "Use `backend/logging` only; no `print()` outside `scripts/` CLIs" becomes "...outside `scripts/` and the operator CLIs `backend/*/cli.py`, which print results and errors for the operator and still log with `log_event()`", owner decision 1), `docs/standards/coding.md` and `docs/standards/python.md` (modify: the same carve-out next to their "`log_event()`, not `print()`" lines), `backend/rag/README.md`, `backend/files/README.md`, `static/js/README.md`, `static/README.md` (one line on the `script.js` row: edits keep the attachment note out of the box and re-append it on send), `docs/data.md`, `docs/architecture.md`, `docs/pitfalls.md` (modify)
- **Change:** RAG README: per-page chunking (and its known limit for PDFs detected as spreadsheet or code, owner decision 2) and the gate on indexed text; files README: a Core Files row for `cli.py` and the `reindex` command (stop the app, then `docker compose -f docker/docker-compose.yml run --rm app python -m backend.files.cli reindex`) and when to run it; `static/js/README.md`: `splitSystemNote` in message-manager's key symbols; `docs/data.md` Vector store: one line pointing to the command for files indexed before the page/text fix; `docs/architecture.md`: the reindex CLI next to the user CLI; `docs/pitfalls.md`: chunkers split paragraphs on blank lines, so extracted PDF text needs per-page chunking for page numbers.
- **Verification:** `pytest tests` (docs guardrails) passes.

### Tests
- `pytest backend/rag`, `pytest backend/files`, `pytest backend/database`, then `pytest backend` and `pytest tests` (env vars from `docs/standards/testing.md`), `ruff check .`.
- `node --test static/tests/test_script.js static/tests/test_logs.js` and `node --test static/js/tests/test_message-manager.js`.
- `scripts/check.sh`.

### Risks and open questions
- PDFs detected as spreadsheet or code keep whole-text chunking and can still report page 1 for later chunks (known limit; extractor text is almost always detected as document or mixed).
- Per-page chunking changes chunk boundaries for PDFs (no chunk spans a page break); retrieval quality is expected to be equal or better, but re-index results differ from today's.
- Re-indexing all files re-embeds everything (cost and time proportional to stored text) and needs the app stopped; `--file-id` allows a gradual run.

### Decisions for the owner
1. **Output of the re-index command.** `docs/standards/errors-and-logging.md`: "Use `backend/logging` only; no `print()` outside `scripts/` CLIs." The command lives in `backend/files/cli.py` (like `backend/auth/cli.py`, which already prints) and an operator needs to see its counts. Options: (a) allow `print()` in operator CLIs under `backend/*/cli.py` and say so in `errors-and-logging.md`; (b) put the command under `scripts/`; (c) report only through `log_event` and the exit code. Recommendation: (a), matching the existing user CLI.
   **Owner's answer (2026-11-20): (a)**; Step 6 amends `docs/standards/errors-and-logging.md` to allow `print()` in operator CLIs under `backend/*/cli.py`.
2. **Page numbers for PDFs detected as spreadsheet or code.** Acceptance criterion 1 reads as all PDFs; the plan applies per-page chunking only to document, mixed and unknown types, because the spreadsheet chunker takes its header from the first line of its input. Options: (a) narrow the criterion to text-like PDFs and record the limit; (b) also chunk spreadsheet and code PDFs per page, accepting a header per page. Recommendation: (a), since extracted PDF text is almost always detected as document or mixed.
   **Owner's answer (2026-11-20): (a)**; the criterion is read as text-like PDFs and the limit is recorded in `backend/rag/README.md` (Step 6).

### Success criteria
- [ ] Chunks of later pages of PDFs detected as `document`, `mixed` or `unknown` carry the right `page_number` with extractor-shaped text (Step 1 test; spreadsheet/code PDFs are a recorded limit, owner decision 2)
- [ ] `python -m backend.files.cli reindex` re-indexes files, documented in the files README and `docs/data.md`
- [ ] The short-content gate measures the indexed text, in one place, with the threshold in config
- [ ] Legacy edit box and copy show no System Note; the edited message keeps its attachment note (file ids for the model, pills in the UI); stored content unchanged
- [ ] `scripts/check.sh` passes

### Reviewer brief
- Objective: give PDF chunks their page numbers, a safe way to re-index files indexed before the page/text fix, a short-content gate on the indexed text, and a legacy edit box and copy without the System Note.
- Key decisions: per-page chunking for PDFs detected as document, mixed or unknown (spreadsheet/code PDFs are a recorded limit, owner decision); the gate on the clean text with `FILE_RAG_MIN_CONTENT_CHARS`, the manager keeps `not is_media`; `FileRAG.build_chunks` and `reindex_file` embed first, write fresh per-run ids in batches, roll back their own writes on failure and only then delete the old snapshot; `python -m backend.files.cli reindex`, run with the app stopped, prints its counts (owner decision: operator CLIs under `backend/*/cli.py` may print); the legacy note is keyed by chat, consumed only by user sends, re-appended on send, and `splitSystemNote` keeps the pill file list.
- Out of scope: running the re-index on live data, PDF extraction gates, the older `RAGManager.chunk_text`, the React UI.
- Success criteria: as listed in the plan.
The decisions above are intended; report a problem with one only if it breaks a requirement or a documented rule.

### Validation log
Path: pair, Haiku validators, judged against the code.
- Round 1: both FAIL. Valid (blocking): note state crossing two legacy files; static/js README; temporary-chat edits losing the note; media placeholders indexed; re-index deleting what it could not replace.
- Round 2: both FAIL. Valid: note leaking to a new chat and empty-send deletes (blocking); mid-run embedding failure (blocking). Both mechanisms redesigned (note keyed by chat; upsert-verify-prune). An earlier edit of mine had deleted Context items and the Pages/Gate approach; found and rebuilt in round 4.
- Round 3 (full): both FAIL. Valid: presence check passes on stale same-id rows (blocking, third re-index failure -> redesigned: embed first, direct writes); multimodal note (blocking).
- Round 4 (full): both FAIL. Valid: pills lost from `noteFiles`; the empty-edit guard left a deferred delete (the guard was dropped; today's behaviour kept). Disproved: the hard-coded gate (already moved to config in the Approach). Owner decisions raised: print() in the CLI, page-number criterion.
- Round 5 (full, last): both FAIL. Valid: `CHROMA_UPSERT_BATCH_SIZE` missing from config; prune must use a snapshot taken before the writes; empty delete lists; the `splitSystemNote` contract. All fixed after the cap, not re-validated.
- Owner decisions (2026-11-20): (1) operator CLIs under `backend/*/cli.py` may print; (2) the page-number criterion covers PDFs detected as document, mixed or unknown. Owner round: valid (coding.md and python.md also forbid print), fixed.
- Unresolved: the round-5 fixes and the owner-round fixes in Steps 4-6 have not been through a validation round.

## Implementation notes

## Verification

## Review history

## Log
- 2026-11-09: created from the review and verification of PRs #67 to #71 (user asked for a follow-up ticket)
- 2026-11-20: plan drafted, unresolved issues (5 rounds; round-5 fixes not re-validated)
