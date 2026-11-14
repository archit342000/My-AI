---
id: MYAI-96
title: "Backend: what the design needs that the server does not send"
status: todo
created: 2026-11-11
updated: 2026-11-11
links:
  split_into: [MYAI-97, MYAI-98, MYAI-99, MYAI-100, MYAI-101, MYAI-102, MYAI-103]
  relates_to: [MYAI-93, MYAI-94, MYAI-95]
---

## Description
While the frontend was moved to the Console at Rest design (MYAI-93) and compared page by page with the design's reference, these gaps turned out to need the server. The frontend shows what it can today and leaves the rest out; nothing here is a frontend bug. Two other backend gaps already have their own tickets: search across file contents (MYAI-94) and running a file and keeping version history in a workspace (MYAI-95).

1. **How long things took.** The reference shows a duration on every tool call ("0.1 s", "38 s") and on the whole Thought process box ("46 s"). The stream and the saved messages carry no start or end time for a tool call or for a turn. Needed: a start and end time (or a duration) per tool call and per assistant turn, in the stream and in what is stored.
2. **Research plan card.** The reference shows research as a card in the chat: the plan's steps, which are done, which one is running, "3 of 6 steps · 12 pages read", a duration per finished step, and Stop research. Today research progress arrives only as loose activity labels and as a `research_plan` file. Needed: structured progress events (the list of steps, the state of each, counts) the chat can draw, live and after a reload.
3. **Helpers card.** The reference shows sub-agents at work as a card: each helper's name, what it is doing now, whether it is working or done, and for how long. Today a sub-agent's steps arrive tagged with the agent's name and are shown as a group inside the Thought process box. Needed: an explicit start and end per sub-agent run, its current activity, and whether helpers can run at the same time.
4. **Sources under an answer.** The reference shows numbered source chips under an answer ("1 playwright.dev · Auto-waiting") and a small number in the text where a source is used. The server sends no list of sources for an answer. Needed: the sources an answer used (title, address or file and line), saved with the message, and a marker in the text where each is cited.
5. **Temporary chats that are abandoned.** A temporary chat that is neither saved nor discarded (the tab is closed or crashes before the discard call) stays on the server and later shows up in the chat list as an ordinary chat. Seen during browser tests: two unsaved temporary chats were listed after their pages closed. Needed: the server should keep a chat marked temporary out of the list and remove it after a while unless it is saved.
6. **Workspace files sit under a `workspace` folder.** Files created in a workspace come back with a leading `workspace/` folder, so the file tree has one extra level the reference does not have and the person never asked for. Needed: return workspace files relative to the workspace's own root (or say which leading folder is the root so the frontend can hide it safely).
7. **Server messages that are not plain wording.** Some error and status texts from the server reach the screen as written (three full stops instead of an ellipsis, error codes, raw exception text on the Logs page and in a failed file run). Needed: a pass over user-facing server messages against the design's wording rules (say what happened and what to do, no codes), or a stable error code per failure so the frontend can word it.
8. **Stopping a turn has no time limit.** Nothing bounds how long a worker takes to exit after Stop, so a slow exit ends in "a response is already in progress" for the next send (already described in `docs/frontend.md`). Needed: a bounded stop, or a state the frontend can wait on.

## Acceptance criteria
- [ ] Tool calls and assistant turns carry a duration in the stream and in stored messages
- [ ] Research progress is sent as structured events the chat can draw as a plan card, live and after a reload
- [ ] Sub-agent runs have an explicit start, end and current activity
- [ ] An answer's sources are stored and sent with it
- [ ] An abandoned temporary chat never appears in the chat list and is removed after a set time
- [ ] Workspace files are returned relative to the workspace root
- [ ] User-facing server messages follow the wording rules, or each failure has a stable code
- [ ] Stop completes within a set time, or reports a state the frontend can wait on
- [ ] API changes are documented and the frontend types in `frontend/src/api/` are updated in the same change

## Plan

## Implementation notes
This ticket was split on 2026-11-11: items 1 to 7 are MYAI-97 to MYAI-103. Item 8 (bounded Stop) got no ticket: `docs/standards/api.md` says `POST /api/chats/<id>/stop` already waits for the worker (at most `TASK_STOP_WAIT_SECONDS`) and answers `"stopped": false` if it is still alive. What remains is frontend and docs: `docs/frontend.md` still says the server only signals the old worker, and the client retries a refused send after a stop instead of using `stopped`.
Frontend follow-ups once the data exists (each is small): show durations in `features/chat/TimelineEntry.tsx` and `ThoughtBox.tsx`; add the research plan and helpers cards to the live reply in `features/chat/MessageList.tsx`; add source chips under an answer; drop the `workspace` level in `features/artifacts/FileTree.tsx`.

This ticket is wide. It should probably be split by item (1 to 4 belong together as "richer turn data") before planning.

## Verification

## Review history

## Log
- 2026-11-11: created at the user's request, from gaps found while adopting the design system (MYAI-93)
- 2026-11-11: linked relates_to MYAI-93 (where the gaps were found), MYAI-94 and MYAI-95 (backend gaps already ticketed)
- 2026-11-11: linked split_into MYAI-97
- 2026-11-11: linked split_into MYAI-98
- 2026-11-11: linked split_into MYAI-99
- 2026-11-11: linked split_into MYAI-100
- 2026-11-11: linked split_into MYAI-101
- 2026-11-11: linked split_into MYAI-102
- 2026-11-11: linked split_into MYAI-103
- 2026-11-11: split into MYAI-97 to MYAI-103; item 8 left as a frontend/docs note
