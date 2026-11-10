# Full-stack end to end suite

Runs the built UI against the real Flask backend with a scripted model (`model-stub.mjs`), on a throwaway
data directory. Start it with `npm run e2e:stack` from `frontend/` (needs a built `dist/`, the repo `venv`
Python or `E2E_PYTHON`, and a cached tokenizer named by `E2E_TOKENIZER`). It is not part of `scripts/check.sh`.

| File                  | Purpose                                                                                                                    |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `start-stack.mjs`     | Starts stub and backend, waits for `/api/version`, cleans up; `--check` verifies and exits                                 |
| `model-stub.mjs`      | OpenAI-style stub; keyword in the last user message picks the scenario (`NOTHINK`, `TOOL`, `MULTI`, `LONG`, `SLOW`, `ERR`) |
| `*.spec.ts`           | Send, multi-tool, stop and retry, temporary chat, geometry                                                                 |
| `geometry.json`       | Legacy-UI rectangles and the `expectedFail` list (it can only shrink)                                                      |
| `record-fixtures.mjs` | Re-records `src/test/fixtures/api/*.json` from a running stack                                                             |

A spec for a known bug can be marked `test.fail()` (and a unit test `it.fails`) so the suite stays green; the fixing change deletes the marker when
Playwright reports the unexpected pass. Environment: `E2E_STACK_PORT` (default 5195), `E2E_STUB_PORT`
(default port + 1), `E2E_PYTHON`, `E2E_TOKENIZER`.
