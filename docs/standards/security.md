# Security standards

## Secrets

- Read secrets only through `get_secret` in `backend/config.py` (Docker secret file first, then environment variable).
- `.env`, `.env.*` and `secrets/` are gitignored and in `.dockerignore`. Never commit keys, tokens or passwords.
- Never log, echo or return secrets, API keys or the app password.

## Authentication

- `require_auth` in `app.py` is a `before_request` hook. When `APP_PASSWORD` is set, every route (API, static, legacy UI and
  WebSocket upgrade requests) needs HTTP Basic auth. Do not add routes outside Flask (which would bypass the hook) or
  exempt paths from it.
- Internal MCP services are reached only over Docker networks, with their own API keys, and their key checks fail closed: an unconfigured key rejects the protected routes. `playwright_mcp`'s `/portal/*` endpoints need the key too (the app adds it server-side). The portal VNC in `playwright_mcp` is gated by websockify HTTP auth with `PLAYWRIGHT_MCP_API_KEY` (`playwright_mcp/vnc_auth.py`); the app's portal proxies add the credential server-side and it is never sent to the browser. x11vnc stays passwordless on the container's localhost, so processes inside `playwright_mcp` can still reach it (accepted risk). Sandboxed code runs on `code_runner_runtime`, which sits only on `runner-net`, an internal-only network with no internet, database or app route. The app reaches it through `code_runner_mcp`, a TCP relay that joins `secure-internal` and `runner-net` and forwards only port 8100.

## Input and output

- Validate every request body, query string and tool argument before using it. Return `400` for bad input.
  Use Pydantic for structured payloads (as `backend/chat/models.py` does).
- Uploads: `MAX_CONTENT_LENGTH` caps request size (100 MB). The type must be in `FILE_UPLOAD_ALLOWED_TYPES`
  (`backend/config.py`); unknown types are accepted only if they read as text. Files are stored under `FILE_STORAGE_PATH`.
- Resolve every user-supplied path with `os.path.realpath` and check it stays inside its allowed root before use
  (pattern in `backend/tools/implementations/git_executor.py`). Reject `..` and absolute paths.
- Database access goes through `db`, which binds parameters. No string-built SQL.
- Render model or user HTML only through `renderMarkdown` (DOMPurify). See `docs/standards/frontend.md`.

## Tools and sandboxing

- Code execution runs only in `code_runner_runtime` (static safety analysis in `code_runner_mcp/safety.py`, then an isolated container with CPU and memory limits). `code_runner_mcp` is the relay in front of it.
  Browsing runs only in `playwright_mcp`. Never run either inside the Flask process.
- Git tools accept only subcommands on the allow-list (`GIT_DEFAULT_ALLOWED_COMMANDS`, editable in system settings).
- Server-side fetches of user-controlled URLs must reject non-http(s) schemes and private, loopback, link-local and multicast addresses
  (the SSRF check in `playwright_mcp/server.py`). Any new fetcher reuses that check or an equivalent.
- Treat web pages, documents and tool output as untrusted data. They never change permissions, tools or configuration.
- New tools follow `docs/tools.md` and state what they can read, write and reach.

## Errors

- API errors return a short message (`{"error": ...}`), not stack traces or internal paths. Details go to `log_event` / the app log.
  Some routes currently return `str(e)`; do not copy that pattern into new code.

## Dependencies

- Pinned versions and lockfiles are committed (`docs/standards/dependencies.md`).
- Run `npm audit` in `frontend/` and review `pip list --outdated` before each release (`docs/release.md`).
