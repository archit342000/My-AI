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

## Suites

| Suite | Command (repo root unless noted) | In `check.sh` |
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
| Full stack | in `frontend/`: `npm run e2e:stack` (starts the real backend with a scripted model, see below) | no |

Run each suite in its own pytest process; combining them causes duplicate-module collection errors.
All commands above use the env vars and `venv/bin/python` described under "Running tests".
`scripts/check.sh` runs every suite marked "In `check.sh`" (use `--python-only` or `--frontend-only` to narrow it) and is the merge gate; there is no hosted CI.
Enable the optional pre-push hook with `git config core.hooksPath scripts/hooks`.

## Frontend tests

Run from `frontend/`: `npm run typecheck`, `npm run lint`, `npm run test`. End-to-end specs
(`npm run e2e`) need the dev server on :5173 and the backend on :5000. See `docs/frontend.md`.

`npm run e2e:stack` starts the real Flask backend on a throwaway data directory with a scripted model
(`frontend/e2e/stack/`) and drives the built UI: send, multi-round tool turns, stop and retry,
and temporary chat. It is not part of
`scripts/check.sh`. It needs the repo `venv` Python (or `E2E_PYTHON`), a cached tokenizer
(`E2E_TOKENIZER`, default `Qwen/Qwen3.6-35B-A3B`) and a built `dist/`. A spec for a known bug can be
marked `test.fail()` (and a unit test `it.fails`) so the suite stays green; the change that fixes the bug removes the
marker, because Playwright and Vitest report an unexpected pass. Fixtures in
`src/test/fixtures/api/` are recorded with `node e2e/stack/record-fixtures.mjs` against a running stack.
