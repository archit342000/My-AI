# Review and definition of done

A change is done when every item below is true. Use it as the checklist for self-review and pull requests.

## Checklist

1. **Scope:** the change does one thing, with small incremental edits and no unrelated reformatting.
2. **Tests:** new or changed source files have `tests/test_<module>.py`; tests for the changed directory and every parent `tests/`
   directory pass (`docs/standards/testing.md`). Frontend: `typecheck`, `lint`, `test` pass.
3. **Lint:** `venv/bin/python -m ruff check .` is clean. CI runs the same checks.
4. **Standards:** follows `python.md`, `frontend.md`, `docker.md`, `security.md`, `api.md` and `errors-and-logging.md` where relevant.
   Anything that contradicts a documented rule was agreed with the owner first.
5. **Docs:** component README updated if role, dependencies or constraints changed; `docs/` updated for new contracts, data
   or tools; `tests/test_docs.py` passes.
6. **Pitfalls:** a new entry in `docs/pitfalls.md` if the work uncovered a trap others could hit.
7. **Compatibility:** no change to API shapes, stored data or `localStorage` keys without updating every consumer and adding a migration.
8. **Security:** no secrets, no unsanitised HTML, no new unvalidated input, no unchecked paths or URLs.
9. **Commits:** conventional prefixes, reason in the body when not obvious (`docs/standards/git.md`); branch and PR base follow `docs/standards/gitflow.md`.
10. **Report:** the summary states what changed, what was run and the results, and anything left undone.

## Reviewing

- Check behavior first (does it do what was asked, including failure paths), then tests, then standards compliance, then style.
- Comment on the code, not the author; say what to change and why. Mark non-blocking remarks as optional.
- Do not approve changes you have not read in full, or that leave failing tests.
