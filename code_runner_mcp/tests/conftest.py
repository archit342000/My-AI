"""Safety net for the runner tests. The runner deletes everything under its scratch roots (/tmp, /var/tmp, /dev/shm) and
its sandbox base, so no test may ever run with the real ones: a handler thread that outlives its test would otherwise
wipe the machine's real /tmp.

The roots are therefore replaced for the whole session at import time (before any test or handler can run) and never
restored; each test only starts from empty directories."""
import shutil
import tempfile
from pathlib import Path

import pytest

import executor

_SESSION_BASE = Path(tempfile.mkdtemp(prefix="runner-tests-"))
_ROOTS = [_SESSION_BASE / "tmp", _SESSION_BASE / "var-tmp", _SESSION_BASE / "dev-shm"]
for _root in _ROOTS:
    _root.mkdir(parents=True)
executor.SANDBOX_BASE = str(_ROOTS[0] / "sandbox")
executor.SCRATCH_ROOTS = tuple(str(r) for r in _ROOTS)
if not all(p.startswith(str(_SESSION_BASE)) for p in executor.SCRATCH_ROOTS + (executor.SANDBOX_BASE,)):
    raise RuntimeError("runner tests must never use the real scratch roots")  # not an assert: survives python -O


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_SESSION_BASE, ignore_errors=True)


@pytest.fixture(autouse=True)
def isolated_scratch():
    """Every test starts with empty scratch roots; the roots are the session's temp dirs, never the real ones."""
    for root in _ROOTS:
        for entry in list(root.iterdir()):
            shutil.rmtree(entry, ignore_errors=True) if entry.is_dir() and not entry.is_symlink() else entry.unlink()
    if executor.SCRATCH_ROOTS != tuple(str(r) for r in _ROOTS):
        raise RuntimeError("a test left the scratch roots pointing somewhere else")
    yield _ROOTS
