# Releasing

## Steps

1. **Branch and merge:** work happens on a version-prefixed branch (`docs/standards/git.md`); merge to `main` once checks pass.
2. **Verify:** `ruff check .`, the pytest suites listed in `docs/standards/testing.md`, and in `frontend/` `npm run typecheck`, `lint`, `test`, `build`.
   Optionally run `npm run e2e` against a running stack.
3. **Audit dependencies:** `npm audit` in `frontend/` and `pip list --outdated` in `venv/`; act on anything severe (`docs/standards/dependencies.md`).
4. **Bump the version** in `backend/version.py` (`VERSION_MAJOR/MINOR/PATCH`), and in `package.json` and `frontend/package.json`.
   Keep all three equal by hand (`backend/tests/test_version.py` checks only the root `package.json`, not `frontend/package.json`).
   Update the version shown in the root `README.md`.
   SemVer: breaking API or data change = major, new feature = minor, fix = patch.
5. **Changelog:** `venv/bin/python scripts/changelog.py --since <previous-tag-or-ref> --version X.Y.Z` prints the entry from conventional commits.
   Add it to the release notes. History through v4.10.0 stays in `docs/archive/`.
6. **Build:** `docker compose -f docker/docker-compose.yml build`. The image builds the React app in its first stage.
7. **Tag and push:** commit `chore(release): X.Y.Z`, tag `vX.Y.Z`, push the branch and tag.
8. **Deploy and smoke test:** start the stack, load `/`, send a chat message, and check `/logs` for errors.

## Back out

Redeploy the previous tag. Schema migrations only add or rebuild forward (`docs/data.md`); restore `DATA_DIR` from a backup
if a release must be fully reverted.

## Legacy UI retirement

The vanilla UI in `static/` stays at `/legacy/` for one release after 5.0.0, selectable with `FRONTEND=legacy`. In the next release:
remove `static/`, the `/legacy` routes in `app.py`, the root `package.json`/`build_cm6.mjs` bundle, `src/styles/legacy.css` coupling if no longer needed,
and the `FRONTEND` switch; then update `docs/architecture.md` and `docs/frontend.md`.
