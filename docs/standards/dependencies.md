# Dependencies

## Python

- `requirements.txt` is the runtime set for the main app. Pin exact versions (`==`) for anything the app imports.
  `requirements-dev.txt` adds pytest and ruff for development and `scripts/check.sh`.
- The MCP services keep their own `requirements.txt` (`code_runner_mcp`, `playwright_mcp`, `tavily_mcp`) because they run in separate images.
  A change to a library shared with the main app (for example `mcp`, `starlette`, `httpx`) is checked in both places.
- To add a package: confirm the current version and API in the official docs, pin it, install it in `venv/`, and run the affected tests.
  Prefer the standard library or an existing dependency first.
- To upgrade: read the release notes, bump one package (or one tightly coupled group) per commit, run the full test suite.
- Known duplication: `pypdf` and `PyPDF2` are both listed, and `python-magic` is listed but not imported by the backend.
  Remove them only with a change that confirms nothing uses them.

## JavaScript

- `frontend/package-lock.json` is committed; install with `npm ci`. Use caret ranges in `package.json`.
- Upgrade with `npm update <pkg>` or `npm install <pkg>@latest`, then run `npm run typecheck`, `lint`, `test` and `build`.
- The root `package.json` (esbuild bundle of CodeMirror into `static/js/cm6.bundle.js`) serves only the legacy UI at `/legacy/`.
  Do not extend it; it goes away with the legacy UI (`docs/release.md`).

## Containers

- Base images are pinned (`docs/standards/docker.md`). Bump them deliberately, rebuild, and run the stack's tests.

## Hygiene

- Remove dependencies when their last import goes away.
- Do not vendor or copy library code into the repo.
- Review `npm audit` and `pip list --outdated` before each release.
