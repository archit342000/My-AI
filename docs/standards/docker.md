# Docker and infrastructure standards

Applies to `docker/` and the services it defines. Rule 9 in `docs/standards/coding.md` (never modify existing containers) still applies.

## Images

- Pin a specific base tag (`python:3.12-slim`, `node:22-slim`, `mcr.microsoft.com/playwright/python:v1.59.0-jammy`).
  Never `latest` in new images (`Dockerfile.bastion` uses `alpine:latest`; pin it when next touched).
- Use multi-stage builds when a build toolchain is not needed at runtime (frontend stage in `docker/Dockerfile`).
- Install system packages with `--no-install-recommends` and delete apt lists in the same `RUN`. Use `pip install --no-cache-dir` and `npm ci`.
- Copy dependency manifests first, install, then copy source, so layers cache.
- A service that needs no toolchain gets its own slim image: the code-runner relay uses `Dockerfile.relay`, not the runner image, so `my-ai-code-runner` is built once.
- Run as a non-root user (`appuser`, `relay`, `pwuser`; the code runner's `runner` is uid 61001 with no home or shell, see the exception below). Switch to root only to install packages, then drop back.
  No `--privileged` or extra capabilities.
- **Exception: `code_runner_runtime`** (approved by the user, 2026-11-10). Its server runs as root holding only `SETUID`, `SETGID` and
  `KILL`, with `no-new-privileges`, `init` and a read-only root filesystem, and drops every user-code and package-install process to
  dedicated uids (`runner` 61001, `runner-pkg` 61002) that are not real host uids. Root is needed because only a root process can
  start children as another uid; without `CAP_DAC_OVERRIDE`, `CAP_CHOWN` and `CAP_FOWNER` it still cannot read or clear what those uids
  own, so a helper running as the uid creates and cleans each sandbox. No other service may copy this; see "Tools and sandboxing" in
  `docs/standards/security.md`.

## Compose (`docker/docker-compose.yml`)

- Services share the `secure-internal` network and reach each other by service name. `app` also joins the external `edge` network (`edge`, subnet 10.250.0.0/24, created by the gateway that runs the tunnel connector, alias `my-ai`) and no other service does; `app` keeps its default route on `secure-internal` (`gw_priority: 1`). The sandboxed runtime (`code_runner_runtime`) is the exception: it sits only on the internal-only `runner-net`. The app reaches it through the relay `code_runner_mcp`, which joins both networks. The package proxy `pkg-proxy` is the other exception: it joins `runner-net` and the egress-only `pkg-egress` bridge (no `secure-internal`, no secrets, no mounts). Publish host ports only for services a user must reach.
- Secrets use Docker `secrets:` and are read through `get_secret` or a `*_FILE` variable. Never put secrets in `environment:`,
  images or committed files.
- Mount only what a service needs; use `:ro` for credentials and keys. Persistent data lives in the data volume or a named volume.
- Set `restart: unless-stopped` on long-running services.
- Anything that runs untrusted or heavy work sets `deploy.resources.limits` (see `code_runner_runtime` and `mysql_db`).
- Health checks: `code_runner_runtime` defines one (`GET /health`), the relay `code_runner_mcp` checks its own loopback health port 8101 (so it stays healthy while the runtime is down), `pkg-proxy` one on `/healthz`, `playwright_mcp` a TCP check on 8001; other services define none yet. Add a `healthcheck:` to any service you add or substantially change.

## Tool containers (MCP)

- Isolation is the point: `code_runner_mcp` and `playwright_mcp` get no app secrets, no app database and no host access.
- Inference is external (`docs/architecture.md`): do not add llama.cpp, model loaders or GPU services here.

## Testing containers

- Use unique container and project names for temporary builds (`docker/docker-compose.testing.yml`) and remove them when done.
