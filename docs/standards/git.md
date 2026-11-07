# Git and versioning

- **Branches** start with the version number, for example `3.1.0-feature-name`.
- **Commits** use short conventional prefixes: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
  Put the reason for the change in the body when it is not obvious.
- **Version** has one source of truth: `backend/version.py`. `package.json` and the docs must match it
  (`backend/tests/test_version.py` checks this).
- **Changelog:** new entries are generated from commit messages (see `docs/standards/docs.md`).
  The history up to v4.10.0 is frozen in `docs/archive/`.
