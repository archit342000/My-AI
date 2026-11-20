# API standards

Applies to Flask routes (`backend/*/router.py`, `app.py`) and the contract the React and legacy UIs rely on.
Client code lives in `frontend/src/api/`.

## Structure

- One blueprint per domain, in that domain's `router.py`, registered in `app.py` with a URL prefix:
  `/api/chats`, `/api/tools`, `/api/file_systems`, `/api/files`, `/api/logs`, `/api/models`, `/api` (personas, skills), `/v1/chat` (OpenAI-compatible).
- Routes stay thin: parse and validate input, call the domain code, shape the response. Business logic lives outside the router.
- Resources are plural nouns (`/chats`, `/skills/<id>`). Use `GET` read, `POST` create/action, `PUT` replace, `PATCH` partial update, `DELETE` remove.
  Action endpoints are `POST /<resource>/<id>/<verb>` (for example `/chats/<id>/stop`).
- Every route is behind `authenticate_request` (`app.py`). New routes need no extra wiring and must not bypass it (see `docs/standards/security.md`).
- Changing a response shape, path or `localStorage` key is a breaking change: update `frontend/src/api/` and the legacy UI in the same change.

## Requests and responses

- JSON in, JSON out (`jsonify`). Field names are `snake_case` on the server; the typed client in `frontend/src/api/` maps them.
- Success returns the resource or `{"success": true}`; creates return the new resource.
- Status codes: `200` ok, `400` invalid input, `401` not authenticated (set by `authenticate_request`), `403` forbidden operation (also an unknown or inactive user),
  `404` not found (also another user's chat or workspace, so ids are not confirmed), `409` conflict (a chat's turn has not ended in time to delete it), `413` upload too large, `429` over the caller's turn limit (with a `Retry-After` header in seconds), `500` unexpected failure.
- Error body is `{"error": "<short message>"}`. The personas and skills routes also include `"success": false`; keep that there for
  compatibility but use the plain form elsewhere. Do not return stack traces or `str(e)` of internal exceptions from new code; the wording rules for every user-facing message are in `docs/standards/errors-and-logging.md`.
- Validate before acting, and fail with `400` (not a partial write).
- Routes that read a JSON body use `read_json_object` (`backend/utils.py`): a missing, malformed or non-object body is `400 {"error": "Request body must be a JSON object"}` (the personas and skills routes add `"success": false`), never Flask's HTML 400/415 page or a 500. Pass `required=False` only when every field is optional: an absent body (nothing, `null`, `[]`) is then accepted as `{}`, while a malformed or non-object body is still a 400.

## Workspace files: versions and running a file

A workspace file has no chat, so these routes take `workspace_id` in place of `chat_id` (a chat still works as before; passing neither is `400`):
- `GET /api/file_systems/<id>/versions`, `GET /api/file_systems/<id>/versions/<n>`, `GET /api/file_systems/<id>/current-version`
  (query string) and `POST /api/file_systems/<id>/versions/<n>/restore` and `POST /api/file_systems/<id>/diff` (query string or JSON body).
  Restoring writes the workspace file on disk. An unknown file or another user's workspace is `404`.
- `POST /api/tools/code-execution/run-file` with `{"path", "workspace_id"}` runs the workspace file with the same runner limits. The workspace
  must belong to the caller (`404` otherwise); `"default"` is `400`. A workspace run keeps no run history, and code the safety check marks
  dangerous is refused (the result is an `Error:` text asking the person to run it from a chat to confirm), because there is no chat to ask in.

## File search

`GET /api/file_systems/search?chat_id=<id>|workspace_id=<id>&q=<text>&limit=<n>` searches the current contents of every file in the
scope (a chat's files plus its workspace's, or a workspace's), with the same per-user access and the same `workspace/` paths as
`GET /api/file_systems`. The match is case-insensitive plain text per line (no regex); `q` is trimmed, and lines are split on `\n` as in the editor. Every file of the scope is read on each request (only the result count is bounded). Response:
`{"results": [{"file_system_id", "path", "line_number", "line"}], "truncated": bool}`, in file then line order; `truncated` is true when
more hits exist than `limit`. `limit` defaults to `FILE_SEARCH_DEFAULT_RESULTS` (50) and is clamped to `FILE_SEARCH_MAX_RESULTS` (200);
`line` is cut to `FILE_SEARCH_MAX_LINE_CHARS` (300), starting at the match when it lies beyond the cut. `400` for a missing or whitespace `q`, a `q` over `FILE_SEARCH_MAX_QUERY_CHARS` (200),
a `limit` that is not an integer or is below 1, or no scope; `404` for another user's chat or workspace; a chat that does not exist
yet gives an empty result (or its workspace's hits). The typed client is `artifactsApi.search` in `frontend/src/api/filesystem.ts`.

## Streaming (SSE)

- Streaming endpoints return `text/event-stream`; each event is `data: <json>\n\n`. Generation endpoints:
  `POST /v1/chat/completions`, `GET /api/chats/<id>/stream` (re-attach), `POST /api/chats/<id>/resume`.
- Payloads follow the OpenAI chunk format with the project's extensions: content and reasoning deltas, tool-call fragments,
  tool results, `event` activity labels, sub-agent deltas and `__redact__`. The reader and fixtures are described in `docs/frontend.md`.
- Sources: web pages (`search_web`, `visit_page`) and successful `read_fs_file` reads in a main turn are numbered per chat (`[[1]]`, `[[2]]`, ...; numbers never change and
  continue across turns, kept in a hidden `source_registry` collection; an unreadable registry fails the turn instead of restarting the numbers). The numbers reach the model with the tool result: a text result ends with a `Sources:` block
  (`[[n]] title - address`), a dict result (a file read) gains a `sources` list, and the same stored text goes to the client. The model cites with `[[n]]` in the answer.
  After a turn that finishes normally and whose answer cites numbered sources, one event `data: {"sources": [{"n", "kind", "title", "locator", "detail"}]}` is sent and the
  same list is stored as a `sources` collection on the turn's last assistant message, so `GET /api/chats/<id>` serves it in that message's `collections`.
  `kind` is `web` (`locator` is the address; `title` is the page title, or the address for `visit_page`) or `file` (`locator` is the path; `detail` says what was read: `lines 10-20`, `from line 10`, `outline`, or null for the whole file). Only `http`/`https` addresses are web sources; titles are one line, at most 200 characters. The registry is stored under the non-numeric anchor `chat:<chat id>`, so it is never served on a message.
  Answers that cite nothing send and store nothing; a failed or stopped turn sends nothing.
- Research progress: a research run sends `data: {"parent_type": "research", "research_progress": {...}}` each time its state changes (scouting, plan awaiting
  approval, before the first section and after every section, at synthesis, done or failed; also when a section starts). The snapshot is
  `{"title", "phase", "steps": [{"index", "heading", "state", "duration_ms"}], "steps_done", "steps_total", "pages_read"}`. `phase` is one of `scouting`, `planning`,
  `awaiting_approval`, `executing`, `synthesizing`, `done`, `failed`; a step `state` is `pending`, `running`, `done` or `failed`, and `duration_ms`
  (from the stored section's last start event to its complete event, so a retried step counts only the attempt that finished) is set only on a `done` step. `done` is sent only when the run really finished (a run paused for the user sends no terminal snapshot). Pages read is refreshed after each section's search phases, not during one. The latest snapshot is also stored as the `research_progress` collection under
  the research tool call and served in the `collections` of the assistant message that made the call, so a reload shows the same card (a re-attached stream gets the next snapshot, or the stored one from the chat). The research run's Stop is the chat's Stop.
- File list root: `GET /api/file_systems?chat_id=|workspace_id=` also returns `"root"`, the leading folder that is the scope's own root so a client can hide it: `"workspace/"` for
  a workspace-only scope (every file path there starts with it, and stays so: ids and paths are unchanged everywhere), `""` for a chat scope (where `workspace/` separates the
  workspace's files from the chat's own) and for a chat that does not exist yet and names no workspace (one that does is listed as that workspace, with `"workspace/"`). The React client hides the root level in the Files panel; the legacy UI reads only `file_systems`
  and keeps showing it (it is removed in a later release).
- Temporary chats: `POST /v1/chat/completions` takes an optional boolean `temporary` (anything else is `400 {"error": "temporary must be true or false"}`, checked before the chat is claimed). On a chat's
  first send (no messages yet) it marks the chat temporary (`chats.is_temporary`); later sends never change the mark. A temporary chat is never in `GET /api/chats` or a workspace's list, but
  `GET /api/chats/<id>` still serves it to its owner. `PATCH /api/chats/<id>` with `{"is_temporary": false}` saves it (the only accepted value; any other is `400`, checked before the chat is claimed).
  An unsaved temporary chat whose last turn is older than `TEMPORARY_CHAT_TTL_SECONDS` (default 86400) is removed, like `DELETE /api/chats/<id>`, on its owner's next `GET /api/chats`
  (a chat with a running turn, or one being sent to, is skipped; at most 20 chats go per request, so a listing stays quick; a failure is logged and retried next time). Chats created before the mark existed stay listed.
- Durations: every `tool_result` delta (and the stored `tool` row, main or sub-agent) carries `duration_ms`, the milliseconds the call took (`0` only for the calls refused once the tool-round limit is reached; other refusals are timed like any call; an agent call covers the whole sub-agent run). A turn that finishes normally sends one last event `data: {"turn": {"duration_ms": N}}`
  and stores `N` on the turn's last assistant row (the event is sent only when `N` was stored); a failed or stopped turn sends and stores nothing, and a resumed turn times only the resumed part.
  Older rows have `duration_ms: null`. `GET /api/chats/<id>` returns the stored values.
- Helper runs: each time a helper (sub-agent) starts, changes what it is doing, or ends, the stream carries
  `data: {"parent_type": <caller's parent_type>, "agent_run": {"id", "name", "parent_id", "state", "activity", "started_at", "duration_ms"}}`. `id` is the tool call that started the helper;
  `state` is `running` (sent at the start and whenever `activity` changes: the helper's latest status text or `Using <tool>`, at most 120 characters), then `done` or `failed` at the end with
  `duration_ms` (the same number as the tool result's); `started_at` is epoch seconds; `parent_id` is the enclosing run's id for a helper called by another helper (research calls the
  search helper), else null. A run is `failed` when the helper raised, could not be resolved (a `running` chunk is still sent first), or its result starts with `Error:` or is an agent's own failure text (`<name> failed.`, `<name> failed:`, `failed during execution`, `failed after N attempts`); a normal first line that merely contains "failed" does not count. `activity` is the last status text or tool the helper reported and is not cleared when a tool returns. A helper that raises sends `failed` and the exception still propagates (no tool result is stored); a stopped turn is rolled back and sends no end chunk for its open run. `duration_ms` is the same number as the tool result's whenever one is stored. Finished runs are stored as an
  `agent_runs` collection (merged by `id`) on the assistant message (top-level runs) or on the outer tool call (nested runs), and served in `collections`; a client that reloads mid-run
  gets the chunks again through the stream re-attach. Helper runs are sequential (the model's tool calls and a helper's own calls run one after another) and may nest; none run in parallel.
- Errors during a stream are sent as `data: {"error": "<message>"}` and the stream ends. Never raise after the response has started.
- A turn runs independently of the HTTP request: the client may disconnect and re-attach. Stop it with `POST /api/chats/<id>/stop`, which answers only after the turn's worker has exited (waiting at most `TASK_STOP_WAIT_SECONDS`, default 5) with `{"status": "success", "stopped": true}`; if the worker is still alive after the wait it still rolls back and answers `"stopped": false`. `DELETE /api/chats/<id>` and `DELETE /api/chats` (clear all, the caller's chats only) stop running turns first and answer `409 {"error": "The chat is still stopping its response; try again in a moment."}`, deleting nothing, when a turn has not ended within the wait.
- `POST /v1/chat/completions` checks in this order: another user's chat is `404`; `uploadedFiles` that are not attached to the chat are
  `400 {"error": "Unknown file"}`; then the chat is created for the caller (or confirmed theirs) and the turn slot is claimed. A rejected
  request writes nothing.
- `POST /v1/chat/completions` and `POST /api/chats/<id>/resume` also count against a per-user turn limit (`RATE_LIMIT_TURNS_PER_MINUTE`, default 10; zero or less is unlimited; the admin is exempt unless `RATE_LIMIT_EXEMPT_ADMIN` is false): over it the answer is `429 {"error": "Too many requests; try again shortly."}` with `Retry-After`, checked after the git-mode check and before any file check, chat claim or write, so a refused request writes nothing. Sends and resumes share one count per user. A request refused after the limit check (an `Unknown file`, a bad `temporary` or a turn-in-progress `400`) has already used a turn. The React client shows a 429 as a toast (no inline error row).
- One turn runs per chat. While a turn is running or starting, `POST /v1/chat/completions` and `POST /api/chats/<id>/resume`
  for that chat return `400 {"error": "a response is already in progress"}` and start nothing (a send also stores nothing);
  re-attach with `GET /api/chats/<id>/stream` instead. The React client shows that message as a toast (no inline error row).
- Yield incrementally and flush each event; do not buffer the whole response.

## WebSockets

- `flask-sock` routes: `/api/tools/portal/ws` (browser portal) and `/api/tools/code-execution/ws` (live code runs).
  They pass through `authenticate_request` like HTTP. Message framing is documented in the owning module.

## Versioning

- `GET /api/version` returns the version from `backend/version.py`. There is no URL versioning; compatibility is kept by following
  the breaking-change rule above.
