# AGENTS.md

Guide for AI agents working on `My-AI`. Details live in `docs/`; this file only holds the rules that always apply.

## Always

1. **Read the local `README.md`** of a component before changing its code, and keep it accurate.
   If code and README disagree, trust the code and fix the README in the same change.
2. **Run the tests** for what you changed, and the parent test directories, before calling a task done.
   Every source file needs a matching `tests/test_<module>.py`. See `docs/standards/testing.md`.
3. **Use `venv/bin/python`** for all Python. Never the system interpreter.
4. **Put configuration in `backend/config.py`**, use `db` from `backend.database` (no raw SQL), and log with `log_event()`.
5. **Do not mask errors** with fallbacks or empty `try/except`. Make small, incremental edits.
6. **Inference is external.** Never add logic to start, manage, or deploy the llama.cpp server here.
7. **Stop and ask** before doing anything that contradicts a documented rule.

## Where to look

| Need | Read |
|------|------|
| System overview, boundaries, component map | `docs/architecture.md` |
| Coding rules | `docs/standards/coding.md` |
| Testing rules and commands | `docs/standards/testing.md` |
| Branches, commits, version, changelog | `docs/standards/git.md` |
| Writing and maintaining docs | `docs/standards/docs.md` |
| Known traps | `docs/pitfalls.md` |
