---
id: MYAI-110
title: "Frontend: source chips and [[n]] markers under an answer"
status: todo
created: 2026-11-14
updated: 2026-11-14
links:
  relates_to: [MYAI-100]
---

## Description
Answers now cite numbered sources as `[[n]]` and the server sends a `sources` chunk and stores a `sources` collection on the assistant message (`AnswerSource`: n, kind web|file, title, locator, detail). Render the marker in the text as a small number and show numbered chips under the answer ("1 playwright.dev · Auto-waiting"); a file source opens the file. Links use only http/https locators. The reducer ignores the chunk today.

## Acceptance criteria
- [ ] The marker renders as a number and each cited source shows as a chip, live and after a reload
- [ ] A marker with no matching source renders as plain text
- [ ] Chips for files open the file at its lines where the panel supports it
- [ ] Unit tests cover web, file, unknown number and an answer without sources

## Plan

## Implementation notes

## Verification

## Review history

## Log
- 2026-11-14: created from the follow-ups of the batch run for MYAI-94 to MYAI-103
