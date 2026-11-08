# scripts
**Role:** Release tooling and RAG/evaluation experiments that run outside the app.

## Layout
| File | Purpose |
|------|---------|
| `check.sh` | Runs all CI checks locally (ruff, backend and MCP tests, frontend checks). `hooks/pre-push` runs it before each push. |
| `changelog.py` | Prints release notes from conventional commits (`docs/release.md`). |
| `run_evals.py` | Runs the query set in `test_queries.json` against the app. |
| `test_rag_*.py`, `test_chunking.py`, `test_classifier_parameters.py`, `stress_test_chunking.py` | RAG parameter and chunking experiments (grid search). |
| `generate_test_data_corpus.py`, `fetch_real_test_data.py`, `test_rag_data/` | Test corpora for those experiments. |

## Context
- **Depends on:** `backend.rag` and, for evaluations, a running inference server and embeddings endpoint.
- **Flow:** scripts read configuration through `backend/config.py` like the app; results are printed or written under `scratch/`.

## Conventions
- Unit tests for release tooling are in `tests/` here. The `test_*.py` experiment files are scripts, not part of CI;
  some fail without external services (`docs/standards/testing.md`).
- CLIs may use `print()`; application code may not.
