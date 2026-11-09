# Security standards

## Secrets

- Read secrets only through `get_secret` in `backend/config.py` (Docker secret file first, then environment variable).
- `.env`, `.env.*` and `secrets/` are gitignored and in `.dockerignore`. Never commit keys, tokens or passwords.
- Never log, echo or return secrets, API keys or auth tokens.

## Authentication

- `authenticate_request` in `app.py` is a `before_request` hook. Every route (API, static, legacy UI and WebSocket upgrade
  requests) needs an identity from the configured provider (`backend/auth/`): no valid identity is 401, an unknown or
  inactive user is 403. Do not add routes outside Flask (which would bypass the hook) or exempt paths from it.
- The default provider `cloudflare_access` verifies the `Cf-Access-Jwt-Assertion` header: RS256 only, with `aud`, `iss`, `exp`,
  `iat` and `email` required. JWKS failures fail closed. Tokens are never logged. The `static` provider (`AUTH_PROVIDER=static`)
  trusts every request and is for local development only; there is no network or header bypass.
- Internal MCP services are reached only over Docker networks, with their own API keys, and their key checks fail closed: an unconfigured key rejects the protected routes. `playwright_mcp`'s `/portal/*` endpoints need the key too (the app adds it server-side). The portal VNC in `playwright_mcp` is gated by websockify HTTP auth with `PLAYWRIGHT_MCP_API_KEY` (`playwright_mcp/vnc_auth.py`); x11vnc stays passwordless on the container's localhost, so processes inside `playwright_mcp` can still reach it (accepted risk). Sandboxed code runs on `code_runner_runtime`, which sits only on `runner-net`, an internal-only network with no internet, database or app route. The app reaches it through `code_runner_mcp`, a TCP relay that joins `secure-internal` and `runner-net` and forwards only port 8100. `/install` goes through `pkg-proxy`, an nginx reverse proxy with three fixed upstreams (PyPI, `files.pythonhosted.org`, `registry.npmjs.org`) that serves GET and HEAD only; it joins `runner-net` and its own `pkg-egress` network, holds no secrets or mounts, and is not on `secure-internal`. Docker enforces the topology (`internal: true` removes the route out, separate bridges isolate networks) but has no per-destination egress allowlist, so the registry-only limit is enforced by the proxy configuration; the proxy container itself has general egress through `pkg-egress`. Optional, documented and not applied: a host `DOCKER-USER` rule that limits traffic from the `myai-pkg-egress` bridge to TCP 443 and DNS (UDP and TCP 53) and drops the rest (`iptables -I DOCKER-USER -i myai-pkg-egress -p tcp --dport 443 -j ACCEPT`, the same for `-p udp`/`-p tcp --dport 53`, then `-I DOCKER-USER -i myai-pkg-egress -j DROP` placed last); it limits ports only, not destinations. Residual: sandboxed code can reach the proxy, so it can send arbitrary GET requests (any path, query string and the headers nginx does not strip) to the three registry hosts and read the replies, a low-bandwidth outbound channel to public hosts that `/install` allows anyway; request bodies are not forwarded. The proxy shares `runner-net` with the runtime and the relay.

## Ownership

- Chats and workspaces belong to one user (`user_id`). A chat or workspace route calls `require_chat_owner` or
  `require_workspace_owner` (`backend/auth/ownership.py`) before any read, write, task claim or stream; `claim_chat` creates a
  chat for the caller or refuses another user's, and `reject_foreign_chat` lets a route validate input first without revealing
  another user's chat. A foreign or missing id is `404` and writes nothing, and the check fails closed without a current user.
  Admins get no bypass: `admin` governs configuration, not other users' data. Tests assert the status and that no write mock
  was called (fixtures: `backend/conftest.py`).
- Covered so far: the chat and workspace routes, the tools-router callbacks, file-system creation and file upload, and personas, skills
  and preferences (every wrapper method takes `user_id`; model tools get it from the chat owner via `system_ctx`, never from model
  arguments). Not yet owner-checked (a later change scopes them): the other file, file-system, RAG and code-execution routes.

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
