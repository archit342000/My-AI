# Testing standards

## Rules

1. **1:1 test mapping:** every source file has a test file in its directory's `tests/` subdirectory
   (`module.py` has `tests/test_module.py`).
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
