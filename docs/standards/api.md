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
  compatibility but use the plain form elsewhere. Do not return stack traces or `str(e)` of internal exceptions from new code.
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

## Streaming (SSE)

- Streaming endpoints return `text/event-stream`; each event is `data: <json>\n\n`. Generation endpoints:
  `POST /v1/chat/completions`, `GET /api/chats/<id>/stream` (re-attach), `POST /api/chats/<id>/resume`.
- Payloads follow the OpenAI chunk format with the project's extensions: content and reasoning deltas, tool-call fragments,
  tool results, `event` activity labels, sub-agent deltas and `__redact__`. The reader and fixtures are described in `docs/frontend.md`.
- Errors during a stream are sent as `data: {"error": "<message>"}` and the stream ends. Never raise after the response has started.
- A turn runs independently of the HTTP request: the client may disconnect and re-attach. Stop it with `POST /api/chats/<id>/stop`, which answers only after the turn's worker has exited (waiting at most `TASK_STOP_WAIT_SECONDS`, default 5) with `{"status": "success", "stopped": true}`; if the worker is still alive after the wait it still rolls back and answers `"stopped": false`. `DELETE /api/chats/<id>` and `DELETE /api/chats` (clear all, the caller's chats only) stop running turns first and answer `409 {"error": "The chat is still stopping its response; try again in a moment."}`, deleting nothing, when a turn has not ended within the wait.
- `POST /v1/chat/completions` checks in this order: another user's chat is `404`; `uploadedFiles` that are not attached to the chat are
  `400 {"error": "Unknown file"}`; then the chat is created for the caller (or confirmed theirs) and the turn slot is claimed. A rejected
  request writes nothing.
- `POST /v1/chat/completions` and `POST /api/chats/<id>/resume` also count against a per-user turn limit (`RATE_LIMIT_TURNS_PER_MINUTE`, default 10; zero or less is unlimited; the admin is exempt unless `RATE_LIMIT_EXEMPT_ADMIN` is false): over it the answer is `429 {"error": "Too many requests; try again shortly."}` with `Retry-After`, checked after the git-mode check and before any file check, chat claim or write, so a refused request writes nothing. Sends and resumes share one count per user. A request refused after the limit check (an `Unknown file` or turn-in-progress `400`) has already used a turn. The React client shows a 429 as a toast (no inline error row).
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
