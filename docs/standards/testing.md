# Testing standards

## Rules

1. **1:1 test mapping:** every source file has a test file in its directory's `tests/` subdirectory
   (`module.py` has `tests/test_<module>.py`).
2. **Coverage:** test every function. Test classes as a whole, including all methods.
3. **Run locally, then upward:** run the tests in the directory you changed, then every parent
   `tests/` directory up to the root (for example `backend/database/tests/`, `backend/tests/`, `tests/`).
4. **Keep tests current:** if a change breaks a test because the intended behavior changed, update the test.
5. **No regressions:** a change must not break unrelated tests.
6. **Report results:** summarize what you ran and the outcome when you finish a task.

## Running tests

Many backend modules need environment variables and `PYTHONPATH=.` to pass validation:

```bash
EMBEDDING_URL="http://mock" AI_URL="http://mock" AI_API_KEY="dummy" PYTHONPATH=. \
  venv/bin/python -m pytest <path>
```

The local README of each component lists its own tests. Read it before running them.

## What a good test does

- Asserts behavior and outputs, including failure paths and edge cases, not implementation details.
- Is isolated: no real network, LLM, embedding or MCP calls. Mock at the boundary (`mcp_client`, `requests`/`httpx`, `backend.inference`).
- Uses temporary directories and databases (`tmp_path`, a test `DATA_DIR`); never touches `backend/data`.
- Is deterministic: no sleeps for timing, no dependence on test order or wall-clock time.
- Registers regressions: a bug fix adds a test that fails without the fix.
- Coverage has no numeric gate; the 1:1 mapping and "test every function" rules are the bar.

## Suites and CI

| Suite | Command (repo root unless noted) | In CI |
|-------|----------------------------------|-------|
| Docs guardrails | `pytest tests` | yes |
| Backend | `pytest backend` | yes |
| Inference proxy | `pytest inference_proxy` | yes |
| Tavily MCP | `pytest tavily_mcp` | yes |
| Code runner MCP | `cd code_runner_mcp && PYTHONPATH=. pytest` | yes |
| Playwright MCP | needs its pinned dependencies (own image) | no |
| `scripts/` | experiment scripts; some need external services | no |
| Frontend | in `frontend/`: `npm run typecheck`, `lint`, `test`, `build` | yes |
| End to end | `npm run e2e` (needs running stack and Chrome) | no |

Run each suite in its own pytest process; combining them causes duplicate-module collection errors.
All commands above use the env vars and `venv/bin/python` described under "Running tests".
`scripts/check.sh` runs every suite marked "In CI" (use `--python-only` or `--frontend-only` to narrow it) and is the source of truth
when hosted CI is unavailable. `.github/workflows/ci.yml` runs the same checks on GitHub.
Enable the optional pre-push hook with `git config core.hooksPath scripts/hooks`.

## Frontend tests

Run from `frontend/`: `npm run typecheck`, `npm run lint`, `npm run test`. End-to-end specs
(`npm run e2e`) need the dev server on :5173 and the backend on :5000. See `docs/frontend.md`.
