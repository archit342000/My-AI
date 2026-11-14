---
id: MYAI-49
title: "Batch 5 follow-ups: PDF page numbers, reindex, indexing gate, legacy edit/copy"
status: todo
created: 2026-11-09
updated: 2026-11-09
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

## Implementation notes

## Verification

## Review history

## Log
- 2026-11-09: created from the review and verification of PRs #67 to #71 (user asked for a follow-up ticket)
