# Releasing

## Steps

1. **Release branch:** cut `release/X.Y.Z` from `develop` once the planned work is merged (`docs/standards/gitflow.md`). Only fixes, docs and the version bump go in.
2. **Verify:** `scripts/check.sh` (ruff, the pytest suites in `docs/standards/testing.md`, and the frontend typecheck, lint, test and build).
   Optionally run `npm run e2e` against a running stack.
3. **Audit dependencies:** `npm audit` in `frontend/` and `pip list --outdated` in `venv/`; act on anything severe (`docs/standards/dependencies.md`).
4. **Bump the version** in `backend/version.py` (`VERSION_MAJOR/MINOR/PATCH`), and in `package.json` and `frontend/package.json`.
   Keep all three equal by hand (`backend/tests/test_version.py` checks only the root `package.json`, not `frontend/package.json`).
   Update the version shown in the root `README.md`.
   SemVer: breaking API or data change = major, new feature = minor, fix = patch.
5. **Changelog:** `venv/bin/python scripts/changelog.py --since <previous-tag-or-ref> --version X.Y.Z` prints the entry from conventional commits.
   Add it to the release notes. History through v4.10.0 stays in `docs/archive/`.
6. **Build:** `docker compose -f docker/docker-compose.yml build`. The image builds the React app in its first stage.
7. **Merge, tag, back-merge:** commit `chore(release): X.Y.Z`, open a PR into `main`, merge with a merge commit, tag `vX.Y.Z` on `main` and push the tag,
   then merge back into `develop` and delete the release branch. Hotfixes use `hotfix/X.Y.Z` the same way.
8. **Deploy and smoke test:** start the stack, load `/`, send a chat message, and check `/logs` for errors.

## Deployment

Deploy only from tagged releases on `main` (`vX.Y.Z`), never from `develop` or a feature branch.

## Back out

Redeploy the previous tag. Schema migrations only add or rebuild forward (`docs/data.md`); restore `DATA_DIR` from a backup
if a release must be fully reverted.

## Legacy UI retirement

The vanilla UI in `static/` stays at `/legacy/` for one release after 5.0.0, selectable with `FRONTEND=legacy`. In the next release:
remove `static/`, the `/legacy` routes in `app.py`, the root `package.json`/`build_cm6.mjs` bundle, `src/styles/legacy.css` coupling if no longer needed,
and the `FRONTEND` switch; then update `docs/architecture.md` and `docs/frontend.md`.
