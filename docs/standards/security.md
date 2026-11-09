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
- File-system routes are checked by one blueprint hook (`require_fs_owner` in `backend/file_system/router.py`) that collects every
  `chat_id` and `workspace_id` from the query, JSON body and URL, so a new route there is covered without extra wiring; a route that
  takes the owner from anywhere else must call the checks itself. Uploaded-file routes use `require_file_owner`; model tools that take
  a `file_id` call `file_for_chat(file_id, chat_id)` (same-owner check, so a user's other chats still work) and answer "File not found";
  RAG retrieval for a file also filters on the file's `chat_id`. Code execution (run-file, history, the live-run WebSocket) checks the
  chat owner before reading or running anything.
- Every chat, workspace, file, file-system, RAG, code-execution, persona, skill and preference path is now owner-checked.

## Admin-only
- Everything that changes process-wide state, exposes other users' data or reaches host-wide tools is admin only (`admin` role,
  `backend/auth/context.py`): non-admins get `403 {"error": "Forbidden"}` with no side effect.
  - Routes: system, agent and browser settings (`/api/tools/config/*`, GET too, since they hold the git allow-list and runner limits),
    the whole logs blueprint (`/api/logs/*`, via a `before_request` using `forbid_non_admin`, so new routes are covered; it includes the
    raw database tables), model load, unload and every non-GET `/api/models` call (reading the model list stays open), and `/legacy/*` (with `FRONTEND=legacy` the same static files are the main UI for every user, a deployment choice; the data routes behind them stay checked).
  - The model pass-through never forwards the caller's identity: `Host`, `Cookie`, `Authorization` and `Cf-Access-Jwt-Assertion`
    are dropped for every method.
  - Tools: set `admin_only=True` on a `ToolSpec` that reaches host-wide state (today `git_agent`, `execute_git`, `install_packages`).
    The registry offers such tools only when `active_modes["admin"]` (the chat owner's role), and `ToolHandler` refuses them for any
    other owner even when the model names one. Turning git mode on (`gitMode` in completions or resume) is a `403` for non-admins,
    and the handler drops it as a second line of defence.
  - The browser portal (`/api/tools/portal/*`) is admin only (a `before_request` in `app.py`, 403 for everyone else). It shows the
    one shared portal browser, so only the admin may see or drive it, and only the admin's browsing runs attach to it.

## Deployment

- Only `app` is routed through the Cloudflare tunnel: it is the only service on the external `edge` network
  (`docker/docker-compose.yml`, created by the architanand.dev gateway stack, with the alias `my-ai`). Never route or attach `bastion_ssh`
  (port 2222) or `inference-proxy` (port 5001), and publish no new ports. The app itself publishes none.
- Set `ADMIN_EMAIL` (seeded as the admin on every start), `CF_ACCESS_TEAM_DOMAIN` and `CF_ACCESS_AUD`; add other users inside
  the app container with `docker compose -f docker/docker-compose.yml exec app python -m backend.auth.cli add <email>` (see
  `backend/auth/README.md`). With no gateway, create the network once: `docker network create --subnet 10.250.0.0/24 edge`. `AUTH_PROVIDER=static` trusts every request and is for
  local development only.
- Served at `https://myai.architanand.dev` (Access team `architanand.cloudflareaccess.com`; the `CF_ACCESS_*` and `ADMIN_EMAIL`
  defaults in the compose file are the non-secret values of that deployment). Keep the Access policy **owner-only** until the
  per-user scoping of files, RAG and code runs is merged; only then allow other identities.
- `app` trusts one hop of `X-Forwarded-Proto` (`ProxyFix`, `app.py`) so its own redirects stay https behind the tunnel; that is only safe because
  `app` is reachable only through the tunnel and the internal network, never published. Do not publish it directly.
- `app` sets `gw_priority: 1` on `secure-internal`, so its default route stays on My-AI's own network. A host firewall drops new
  connections from the edge subnet to private ranges and the host, so outbound traffic (inference server, LAN) must not leave via
  `edge`. After a deploy, `docker compose -f docker/docker-compose.yml exec app ip route` must not show a default via `10.250.0.1`.

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
- Browser state is per user: each user's browsing agent gets its own persistent profile, `playwright_data/profiles/<user id>`
  (cookies, logins, storage), chosen server-side from the chat owner and validated against `[a-z0-9_-]{1,64}`. Users never share a
  profile. Only the admin's runs may attach to the portal browser. The old shared `default_profile` is retired (saved logins in it
  are not carried over).
- Per-user rate limits (`backend/auth/rate_limit.py`, in memory, one window per user, reset by a restart): turn starts per minute (`RATE_LIMIT_TURNS_PER_MINUTE`) and web searches per day (`RATE_LIMIT_SEARCHES_PER_DAY`), so one user cannot use up shared inference or Tavily capacity. Sends and resumes answer `429` before anything is written; a search over the limit returns `Error: Daily web search limit reached.`, also for a chat with no owner (fail closed). The admin is exempt unless `RATE_LIMIT_EXEMPT_ADMIN` is false.
- Code runs are serialised in the app and again by a lock inside the runner, and bounded per user (`CODE_RUNNER_MAX_QUEUED_PER_USER`, default 2; waits longer
  than `CODE_RUNNER_QUEUE_TIMEOUT`, default 120 s, are refused with a "busy" message), so one user cannot queue the runner full.
  User code runs as the dedicated uid `runner` (61001) and installs as `runner-pkg` (61002), neither a real host uid (`RLIMIT_NPROC` is
  counted host-wide per uid). The runtime server is root with only `SETUID`, `SETGID` and `KILL`, `no-new-privileges`, `init` and a
  read-only root filesystem (exception recorded in `docs/standards/docker.md`); the writable paths are the tmpfs mounts `/tmp` (exec),
  `/var/tmp`, `/dev/shm` and `/dev/mqueue`. Children start with `subprocess(user=, group=, extra_groups=[])` and a `prlimit` wrapper
  (process and open-file limits only; memory is the cgroup's). Each run gets its own `HOME` and `TMPDIR` inside its sandbox, which a
  helper running as the runner uid creates; after every run a helper kills every process of the uid, removes its SysV IPC objects and
  its files in the scratch roots, `/dev/mqueue` and the sandbox base, and the server verifies nothing is left (`/proc/sysvipc`, `/proc`, the
  directories). If anything cannot be cleaned the next run is refused ("Runner cleanup failed.") and a failed clean-up after a run is
  reported on that run. The API key lives in a root-only `0700` tmpfs directory (`/run/keys`), so user code can neither read it nor the
  server's environment, signal or ptrace the server, nor write `/opt/runner` (installed packages), `/app` or any persistent path.
  Residuals: the host key file must stay readable by root (mode 644 or root-owned: the server has no `CAP_DAC_OVERRIDE`); user code
  shares the kernel and the default seccomp profile (no profile change here); `/dev/mqueue` is writable and is cleaned like scratch;
  tmpfs pages count against the container's memory limit, so user code can fill it (the cgroup, not the tmpfs sizes, is the bound);
  a silent program is stopped by its timeout, not by a client that stays connected without reading; a live run whose client
  disconnects while it is still queued for the lock starts and is killed on its first receive; the source tree mounted at `/app`
  must be world-readable because the helper runs from it as the runner uid.
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
