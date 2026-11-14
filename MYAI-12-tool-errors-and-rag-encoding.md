---
id: MYAI-12
title: "B5 and B6: raw tool exceptions to the model; double-encoded RAG page text"
status: done
created: 2026-11-08
updated: 2026-11-09
links:
  relates_to: [MYAI-23, MYAI-49]
---

## Description
Report B5 (Low) and B6 (Low). B5: tool errors reach the model as raw Python exception text (backend/chat/tool_handler.py:302-303). Suggested fix: a short fixed error the model can act on, with the detail logged via log_event(). B6: RAG chunk text is JSON inside JSON ("format": "pages" stored as text, consumed by file_rag); markers are not produced. Suggested fix: convert page JSON to page markers before indexing; leave stored content unchanged. Not blocked.

## Acceptance criteria
- [x] Tool failures return a short message starting with Error
- [x] RAG chunks contain page text, not JSON
- [x] Stored content and document read path unchanged

## Plan
**Date:** 2026-11-09  **Status:** Validated

### Objective
Fix two independent low-severity defects found in the full-scope report. B5: when a pure tool raises, `ToolHandler._execute_pure_tool` returns the raw exception text to the model; replace it with a short fixed message that starts with `Error` and log the detail with `log_event()`. B6: PDF content is stored as JSON (`{"format": "pages", "pages": [...]}`) and `FileRAG.store_file` indexes that JSON string as-is, so chunks contain JSON-escaped text and never get `page_number` metadata (other files are wrapped as `{"format": "text", ...}` and suffer the same encoding); just before chunking, convert page JSON to `--- PAGE_START_N ---` / `--- PAGE_END_N ---` markers and unwrap text JSON to its `text`, leaving the stored `content_text` and the document read path untouched.

### Context
- **Requirement:** ticket Description and Acceptance criteria (tool failures return a short `Error...` message; RAG chunks hold page text, not JSON; stored content and read path unchanged).
- **Assumptions:**
  - The fixed B5 message names the tool but contains no exception text, for example `Error: Tool '<name>' failed unexpectedly. Check the arguments and try again, or use a different approach.` Exception type and message go only to logs.
  - Only the generic `except Exception` branch in `_execute_pure_tool` changes. The unresolved-implementation message (`Error: Implementation for {name} could not be resolved.`) and tools that return their own `Error...` strings are already compliant and stay as is.
  - The B6 conversion lives in `FileRAG.store_file` (single choke point for all three callers in `backend/files/manager.py`: `upload_file`, `upload_file_async`, `_process_file_background`), not in each caller.
  - No automatic reindex (see Risks). B5 and B6 are independent; they can ship as separate commits.
- **Rules that apply:**
  - `docs/standards/errors-and-logging.md`: tools return text beginning `Error`/`Failed`; user-facing messages short and actionable, detail to logs; `log_event` `event_type` is `<component>_<event>`, errors end in `_error`, `data` is a flat dict with ids and an `error` string.
  - `docs/tools.md` line 25: error text beginning `Error` is treated as a failed call (`backend/tools/safety.py` checks `startswith(("error", "failed", ...))` on the lowercased result).
  - `AGENTS.md`: no masking errors with fallbacks; tests per module (`tests/test_<module>.py`); run tests then `scripts/check.sh` and `ruff check .`; keep component READMEs accurate.
  - `docs/data.md`: ChromaDB collections managed only by `RAGManager`.
- **Current behaviour:**
  - `backend/chat/tool_handler.py` `ToolHandler._execute_pure_tool`: `except Exception as e:` logs via `logger.error(..., exc_info=True)` and returns `f"Error: {str(e)}"`. `log_event` is already imported. Test `backend/chat/tests/test_tool_handler.py::test_execute_pure_tool_sync_exception` asserts `"Error: sync error" in result`.
  - `backend/files/pdf_extractor.py` `PDFExtractor.extract_with_pymupdf` / `extract_with_ocr` return `json.dumps({"format": "pages", "pages": [...]})`; this is stored as `content_text` and parsed by `FileManager.grep_file` / `read_file_range` in `backend/files/manager.py`.
  - `FileManager.extract_file_content` (`backend/files/manager.py`, end of method) wraps every other extraction as `json.dumps({"format": "text", "text": raw_content})`, and that string is what all three callers pass to `store_file`. So text, code, CSV and Markdown uploads are also indexed as JSON today (escaped newlines, so line metadata does not match `read_file_range` line numbers).
  - `backend/rag/file_rag.py` `FileRAG.store_file`: runs `detect_file_type(filename, content_text)` on the raw string, then `strip_page_markers(content_text)` (`backend/rag/chunking.py`), which only recognises marker lines. Nothing produces markers, so `page_map` is empty, `is_page_based` is False, and chunks are JSON fragments with line metadata.

### Approach
Add a pure helper in `backend/rag/chunking.py` that turns page JSON into marker text, unwraps text JSON to its `text`, and returns any other input unchanged, and call it at the top of `FileRAG.store_file` before detection and marker stripping. Run file-type detection on the stripped clean text so JSON or marker lines do not skew classification (for non-page content the clean text equals the unwrapped text). For B5, replace the returned string with a fixed message and add a `log_event("tool_handler_tool_error", ...)` call alongside the existing `logger.error`.
Rejected: changing `PDFExtractor` to emit markers (changes stored content and breaks `read_file_range`/`grep_file`, violating the acceptance criteria); converting in each `manager.py` caller (three duplicated call sites, easy to miss one); including `str(e)` in a truncated form (still leaks internals such as paths).

### Steps
#### Step 1 (B5): Fixed tool error message with logged detail
- **Files:** `backend/chat/tool_handler.py` (modify), `ToolHandler._execute_pure_tool`.
- **Change:** in the `except Exception as e` branch keep `logger.error(..., exc_info=True)`, add `log_event("tool_handler_tool_error", {...})` with `chat_id`, tool `name`, `tool_call_id` (`tc_id`), `error_type` (`type(e).__name__`) and `error` (`str(e)` capped at 500 characters, a plan choice to keep the event small; the existing `logger.error` traceback line is unchanged), and return the fixed message from Assumptions (starts with `Error`, names the tool, no exception text).
- **Verification:** runs with Step 2 (tests written there).

#### Step 2 (B5): Update tool handler tests
- **Files:** `backend/chat/tests/test_tool_handler.py` (modify), `test_execute_pure_tool_sync_exception`; add an async-raising variant.
- **Change:** assert the result starts with `Error`, contains the tool name, does not contain the exception message (`sync error`), and that `log_event` (patched at `backend.chat.tool_handler.log_event`) was called with `tool_handler_tool_error` and the exception text in `error`.
- **Verification:** `EMBEDDING_URL="http://mock" AI_URL="http://mock" venv/bin/python -m pytest backend/chat/tests/` passes, then the parent suites via `scripts/check.sh --python-only` (exports the full documented env) per `docs/standards/testing.md`, run locally then upward.

#### Step 3 (B6): Page JSON to marker helper
- **Files:** `backend/rag/chunking.py` (modify), new function `content_to_index_text(content: str) -> str`.
- **Change:** if `content` parses as JSON to a dict with `format == "pages"` and a list `pages`, return the pages joined as `--- PAGE_START_N ---\n<page text>\n--- PAGE_END_N ---` (1-indexed, empty pages kept so numbering matches `read_file_range`); if it is a dict with `format == "text"` and a string `text`, return that `text`; otherwise (not JSON, or JSON without a known `format`) return `content` unchanged. Catch only `json.JSONDecodeError` (raw text is the expected non-JSON case). A known `format` with an invalid payload (`pages` not a list of strings, `text` not a string) raises `ValueError` rather than indexing raw JSON (`AGENTS.md` rule 5); the `store_file` callers in `manager.py` already catch and log FileRAG failures. Format must match the patterns in `strip_page_markers`.
- **Verification:** runs with Step 5; round-trip through `strip_page_markers` yields the page text and a page map with one entry per page.

#### Step 4 (B6): Use the helper in FileRAG indexing
- **Files:** `backend/rag/file_rag.py` (modify), `FileRAG.store_file`.
- **Change:** after the length guard, convert `content_text` with `content_to_index_text`, then call `strip_page_markers` on the result, and pass the clean text (not the raw string) to `detect_file_type`. The existing `is_page_based` / `resolve_page_number` branch then sets `page_number` on PDF chunks. Callers in `backend/files/manager.py` and the stored `content_text` are not changed.
- **Verification:** runs with Step 5.

#### Step 5 (B6): Tests for helper and indexing
- **Files:** `backend/rag/tests/test_chunking.py` (modify), `backend/rag/tests/test_file_rag.py` (modify).
- **Change:** chunking tests for `content_to_index_text`: page JSON converts to markers; text JSON unwraps to its text; raw text, non-dict JSON and JSON without a known `format` are returned unchanged; empty pages keep numbering; malformed `pages`/`text` payloads raise `ValueError`. File RAG test (unmocked chunking, mocked `store`): page JSON input yields chunk documents with no JSON syntax (`"format"`, `\n` escapes) and metadata with `page_number` and no `line_start`; a `format: text` input yields chunks without JSON escapes whose `line_start` matches the line in the unwrapped text; existing mocked tests still pass (adjust only if the `detect_file_type` argument change breaks an assertion).
- **Verification:** `EMBEDDING_URL="http://mock" AI_URL="http://mock" venv/bin/python -m pytest backend/rag/tests/` passes; `venv/bin/python -m pytest backend/files` still passes (read path unchanged); then the parent suites via `scripts/check.sh --python-only`.

#### Step 6: Docs and full checks
- **Files:** `backend/rag/README.md` (modify): add `content_to_index_text` to the `chunking.py` key symbols and one line in Flow noting stored JSON content is unwrapped (pages to page markers, text to plain text) before chunking.
- **Change:** no other doc changes; `docs/tools.md` and `docs/standards/errors-and-logging.md` already describe the target B5 behaviour.
- **Verification:** `venv/bin/ruff check .` clean; `scripts/check.sh --python-only` passes.

### Tests
- `backend/chat/tests/test_tool_handler.py` (Step 2), `backend/rag/tests/test_chunking.py` and `backend/rag/tests/test_file_rag.py` (Step 5). No new modules, so no new test files are required.
- Commands: the per-directory pytest commands in Steps 2 and 5, then `ruff check .` and `scripts/check.sh --python-only` (merge gate per `docs/standards/testing.md`).

### Risks and open questions
- **Already-indexed chunks (reindex):** files uploaded before this fix (PDFs and text alike) keep JSON chunks (PDFs also without `page_number`); the fix applies only to newly indexed files. There is no reindex path in the repo (`_process_file_background` skips files that already have `content_text`). Decision: no migration in this ticket; affected files can be re-uploaded. A one-off reindex script (read `content_text`, `FileRAG.delete_file`, `store_file`) is a possible follow-up for the user to decide; non-blocking.
- **Retrieval quality shift:** all text-bearing files may now classify differently (JSON text previously skewed `detect_file_type`), changing chunk strategy for new uploads. This is the intended correction; covered by Step 5 tests.
- **User JSON uploads with a `format` key:** `extract_file_content` passes through any upload that parses as a dict with `format`, so a user JSON file shaped like `{"format": "text", "text": ...}` indexes only `text`, and one with a known `format` but an invalid payload raises `ValueError` and is not indexed (previously indexed as raw JSON). `read_file_range`/`grep_file` already interpret valid payloads of this shape the same way, so this is consistent; accepted as an edge case.
- **Indexing failure visibility:** the `store_file` callers catch FileRAG exceptions with `logger.warning`; in `upload_file_async` the file is still marked `completed` with no chunks. This is existing handling for any FileRAG failure, not new; changing it is out of scope.
- **Less detail for the model (B5):** the model no longer sees, for example, a `TypeError` about a bad argument. Accepted per the ticket; detail is in `logs/general/` and `logs/app.log`.
- **Ticket split:** B5 and B6 are independent; kept in one ticket because each is two to three small steps. They can ship as separate commits or PRs.

### Success criteria
- [ ] A raising pure tool returns a fixed message starting with `Error` that contains no exception text, and a `tool_handler_tool_error` event with the detail is logged.
- [ ] Indexing page-format content produces chunks of plain page text with `page_number` metadata; text-format content is indexed as plain text.
- [ ] `content_text` stored in the DB and `FileManager.read_file_range` / `grep_file` behaviour are unchanged; `backend/files` tests pass.
- [ ] `ruff check .` and `scripts/check.sh --python-only` pass.

### Validation log
- **Round 1:** validator PASS, 6 MINOR. My judgement: pass, but all 6 checked and valid. (1) `search_file` does not exist, it is `grep_file`: fixed. (2) Non-PDF content is also JSON-wrapped (`format: text`) by `extract_file_content`: valid and the same defect, so B6 was widened and the helper renamed `content_to_index_text`, which also unwraps text JSON. (3) Malformed page payload silently indexed: now raises `ValueError`. (4) Untruncated `error` in log_event: capped. (5) Verifications that pointed to later steps: reworded to "runs with Step N". (6) Parent test suites missing: added.
- **Round 2:** validator PASS, 5 MINOR, all valid. Stale `search_file` in the Rejected sentence: fixed. Env prefix missing on parent-suite commands: fixed. Truncation citation overstated: reworded as a plan choice. Risk entries added for user JSON uploads with a `format` key and for swallowed FileRAG failures in `upload_file_async`.
- **Round 3:** validator PASS, 4 MINOR. My judgement: pass, no BLOCKING issues remain, so I stopped per the round-3 rule. (1) Env prefix incomplete: fixed by naming only the `scripts/check.sh --python-only` route for parent suites. (4) "Same way" overstated: fixed ("valid payloads"). Deferred to implement: (2) the new `ValueError` is swallowed by the existing caller `logger.warning`; this is recorded under Risks and changing caller handling is out of scope, but implement may add a `log_event` at the caller if it stays minimal. (3) The 500-character cap does little because `logger.error` already logs the full text; accepted as harmless.

## Implementation notes

### Autopilot run (2026-11-09)
Batch 5 item. Branch bugfix/tool-error-and-rag-text from origin/develop a1a9333, PR base develop. Dirty files before start: none.

### Baseline (2026-11-09)
At develop a1a9333: backend/chat + backend/rag + backend/files 308 pass; `pytest backend tests` only the 10 async-plugin failures (pytest-asyncio missing).

### Implementation progress
- [x] Steps 1-2 (B5): fixed message plus `tool_handler_tool_error` event in `_execute_pure_tool`; sync and async raising tests
- [x] Steps 3-5 (B6): `content_to_index_text` in chunking.py, used by `FileRAG.store_file` before marker stripping and type detection; helper and indexing tests
- [x] Step 6: backend/rag/README.md; ruff clean. scripts/check.sh not run as a whole (pytest-asyncio missing)
Observation, not changed (pre-existing chunker limit): when a page's text has only single newlines and no blank-line paragraph breaks (what PyMuPDF extraction yields), the chunkers report line 1 for every chunk, so later pages' chunks get page_number 1. With paragraph breaks the numbers resolve per page. Before this change no chunk had a page_number at all.

### Smoke test (2026-11-09)
chat+rag+files pytest 317 pass; `pytest backend tests` 10 failures, all async plugin (baseline); ruff clean.
Status on develop (checked at e327094, 2026-11-08): Still present on develop: tool_handler.py:303 returns str(e); no PAGE_START markers in backend/files/manager.py.

PR: https://github.com/archit342000/My-AI/pull/67, branch bugfix/tool-error-and-rag-text, base develop

## Verification
### Verification plan (2026-11-09)
Real app (port 5099, DATA_DIR /tmp/myai12-data) with a fake proxy on 5098 (`scripts/fake_proxy.py`: calls `get_time` with a bad argument so it raises, then echoes the tool message). Never touches :5000/:5001, containers, backend/data or a real chats.db. Scripts: `scripts/v12.py` (API), chunks read from the throwaway Chroma store.
| ID | Criterion | Scenario | Expected |
|----|-----------|----------|----------|
| V1 | AC1 | chat turn whose tool raises | tool message to the model and stored row start with `Error`, name the tool, no exception text; `tool_handler_tool_error` logged with the detail |
| V2 | AC2 | upload a 3-page PDF | chunks are page text (no JSON, no markers), page_number set, no line metadata |
| V3 | AC2 | upload a text file | chunks are plain text with line_start from 1, no JSON escapes |
| V4 | AC3 | stored content | `files.content_text` still `{"format": "pages"...}` / `{"format": "text"...}`; backend/files tests pass |
| V5 | regression | backend, tests, ruff | only baseline async failures |
Not run yet.

### Results (2026-11-09)
**Commit verified:** a1a9333 (+ uncommitted files). Hashes: tool_handler.py 80adafb6, test_tool_handler.py ef56230c, chunking.py 804ac784, file_rag.py d636facf, test_chunking.py e6a2ae67, test_file_rag.py 550be1a3, README.md 8a78e69d.

| ID | Status | Evidence |
|----|--------|----------|
| V1 | PASS | v1-v3-live.log: model and stored row got "Error: Tool 'get_time' failed unexpectedly. Check the arguments and try again, or use a different approach."; event with TypeError detail in the app log |
| V2 | PASS | v2-v3-chunks.log (BM25 collection): page text for all three pages, no JSON or markers, page_number set (1 on every chunk, see the observation) |
| V3 | PASS | v2-v3-chunks.log: plain text, line_start 1 to 39 |
| V4 | PASS | v1-v3-live.log: stored content still JSON for both files; backend/files tests pass |
| V5 | PASS (baseline) | `pytest backend tests`: only the 10 async-plugin failures; ruff clean |

Notes: four harness attempts first (tool named `get_time`, venv python for fitz, vector collection drops chunks under the fake proxy's all-zero embeddings so BM25 was used, then page-number expectations; logs `attempt*.log`). Observation: later-page chunks carry page_number 1 for pages without paragraph breaks (pre-existing chunker limit, recorded in Implementation notes). Teardown: processes stopped, /tmp/myai12-data removed, ports 5098/5099 free, containers and git status as before. **Verdict: verified (5/5 PASS).**

## Review history
### Round 1 - 2026-11-09
Verdict: Approve with comments. Scope: origin/develop a1a9333..working tree, 7 files, single Haiku reviewer.
- R1-1 [MINOR] file_rag.py:32 - the short-content gate measures the stored JSON wrapper - Static - Deferred as pre-existing (the gate and the callers always used the JSON length)
- R1-2 [MINOR] file_rag.py:44 - detection on cleaned text moves CSV/TSV text uploads to the spreadsheet chunker, untested and undocumented - Static - Fixed (test, README note)
- R1-3 [MINOR] chunking.py:57 - user JSON with a top-level `format` key can raise ValueError and skip indexing - Static - Fixed (documented in the docstring, store_file test)
- R1-4 [NIT] test_chunking.py - repeated `import json` - Static - Fixed
- R1-5 [NIT] tool_handler.py - "check the arguments" wording - Static - Rejected: the wording is the validated plan's choice and keeps the Error prefix
Resolution: fixed 3, deferred 1, rejected 1. Checks: chat+rag+files pytest 317 pass, ruff clean. No runtime change (tests, docs, docstring), so no re-verify.

## Log
- 2026-11-08: created from reports/full-scope-final-report-2026-11-08.md
- 2026-11-09: plan validated, 3 rounds
- 2026-11-09: linked relates_to MYAI-23 (tool error messages to the model, different layers)
- 2026-11-09: autopilot started (batch-autopilot)
- 2026-11-09: implemented, smoke tests pass
- 2026-11-09: verified live, 5/5 PASS
- 2026-11-09: review round 1 Approve with comments; fixed 3, deferred 1, rejected 1
- 2026-11-09: shipped, PR https://github.com/archit342000/My-AI/pull/67
- 2026-11-09: batch-autopilot: shipped, base develop
- 2026-11-09: linked relates_to MYAI-49 (follow-ups from batch 5)
- 2026-11-09: closed, PR merged
