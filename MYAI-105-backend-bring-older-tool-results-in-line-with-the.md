---
id: MYAI-105
title: "Backend: bring older tool results in line with the plain-message rule"
status: todo
created: 2026-11-14
updated: 2026-11-14
links:
  relates_to: [MYAI-103]
---

## Description
MYAI-103 left the model-facing tool results that still carry exception text: `backend/tools/preferences.py`, `tasks.py`, `clipboard.py`, `implementations/git_executor.py`, `backend/files/manager.py` (regex and extraction errors), `backend/tavily_mcp/server.py`, `research_agent/research_utils.py`, and the file-system AI tools in `backend/file_system/manager.py` (read, replace, rename, metadata, delete results). The standard (`errors-and-logging.md`) now says new or changed tool results carry no exception text. Convert these: keep the leading `Error`/`Failed` word, send a fixed text, log the detail with `log_event(..., error_detail(e))`. Path-rule wording stays as written (`PathRuleError`).

## Acceptance criteria
- [ ] No tool result in the listed modules contains exception text
- [ ] Each converted site logs the detail with `log_event` and has a test that forces the failure
- [ ] The note in `errors-and-logging.md` about older tools is removed

## Plan

## Implementation notes

## Verification

## Review history

## Log
- 2026-11-14: created from the follow-ups of the batch run for MYAI-94 to MYAI-103
