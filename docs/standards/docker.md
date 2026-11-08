# Docker and infrastructure standards

Applies to `docker/` and the services it defines. Rule 9 in `docs/standards/coding.md` (never modify existing containers) still applies.

## Images

- Pin a specific base tag (`python:3.12-slim`, `node:22-slim`, `mcr.microsoft.com/playwright/python:v1.59.0-jammy`).
  Never `latest` in new images (`Dockerfile.bastion` uses `alpine:latest`; pin it when next touched).
- Use multi-stage builds when a build toolchain is not needed at runtime (frontend stage in `docker/Dockerfile`).
- Install system packages with `--no-install-recommends` and delete apt lists in the same `RUN`. Use `pip install --no-cache-dir` and `npm ci`.
- Copy dependency manifests first, install, then copy source, so layers cache.
- Run as a non-root user (`appuser`, `runner`, `pwuser`). Switch to root only to install packages, then drop back.
  No `--privileged` or extra capabilities.

## Compose (`docker/docker-compose.yml`)

- Services share the `secure-internal` network and reach each other by service name. Publish host ports only for services a user must reach.
- Secrets use Docker `secrets:` and are read through `get_secret` or a `*_FILE` variable. Never put secrets in `environment:`,
  images or committed files.
- Mount only what a service needs; use `:ro` for credentials and keys. Persistent data lives in the data volume or a named volume.
- Set `restart: unless-stopped` on long-running services.
- Anything that runs untrusted or heavy work sets `deploy.resources.limits` (see `code_runner_mcp` and `mysql_db`).
- Health checks: none are defined today. Add a `healthcheck:` to any service you add or substantially change.

## Tool containers (MCP)

- Isolation is the point: `code_runner_mcp` and `playwright_mcp` get no app secrets, no app database and no host access.
- Inference is external (`docs/architecture.md`): do not add llama.cpp, model loaders or GPU services here.

## Testing containers

- Use unique container and project names for temporary builds (`docker/docker-compose.testing.yml`) and remove them when done.
