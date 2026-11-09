"""Safety net for the runner tests. The runner deletes everything under its scratch roots (/tmp, /var/tmp, /dev/shm) and
its sandbox base, so no test may ever run with the real ones: a handler thread that outlives its test would otherwise
wipe the machine's real /tmp.

The roots are therefore replaced for the whole session at import time (before any test or handler can run) and never
restored; each test only starts from empty directories."""
import os
import shutil
import tempfile
from pathlib import Path

import pytest

# Tests run unprivileged (no uid switch): the flag is honoured only for a non-root process (sandbox_user.check_privilege).
os.environ["CODE_RUNNER_ALLOW_UNPRIVILEGED"] = "1"

import executor  # noqa: E402
import runner_helper  # noqa: E402

_SESSION_BASE = Path(tempfile.mkdtemp(prefix="runner-tests-"))
_ROOTS = [_SESSION_BASE / "tmp", _SESSION_BASE / "var-tmp", _SESSION_BASE / "dev-shm"]
for _root in _ROOTS:
    _root.mkdir(parents=True)
_MQUEUE = _SESSION_BASE / "mqueue"
_MQUEUE.mkdir()
runner_helper.MQUEUE_DIR = str(_MQUEUE)  # never the real /dev/mqueue
executor.SANDBOX_BASE = str(_ROOTS[0] / "sandbox")
executor.SCRATCH_ROOTS = tuple(str(r) for r in _ROOTS)
if not all(p.startswith(str(_SESSION_BASE)) for p in executor.SCRATCH_ROOTS + (executor.SANDBOX_BASE,)):
    raise RuntimeError("runner tests must never use the real scratch roots")  # not an assert: survives python -O


def pytest_configure(config):
    """pytest's own tmp_path directories live under the session base too, never under the real /tmp."""
    config.option.basetemp = str(_SESSION_BASE / "pytest-tmp")


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_SESSION_BASE, ignore_errors=True)


@pytest.fixture(autouse=True)
def _never_signal_every_process(monkeypatch):
    """kill(-1) (every process of the uid) and killpg(0) would end the developer's session: no test may send them."""
    real_kill, real_killpg = os.kill, os.killpg

    def kill(pid, sig):
        if pid <= 0 and sig != 0:
            raise AssertionError(f"a test tried to send signal {sig} to pid {pid}")
        return real_kill(pid, sig)

    def killpg(pgid, sig):
        if pgid <= 1 and sig != 0:
            raise AssertionError(f"a test tried to send signal {sig} to process group {pgid}")
        return real_killpg(pgid, sig)

    monkeypatch.setattr(os, "kill", kill)
    monkeypatch.setattr(os, "killpg", killpg)


@pytest.fixture(autouse=True)
def isolated_scratch():
    """Every test starts with empty scratch roots; the roots are the session's temp dirs, never the real ones."""
    for root in _ROOTS:
        for entry in list(root.iterdir()):
            shutil.rmtree(entry, ignore_errors=True) if entry.is_dir() and not entry.is_symlink() else entry.unlink()
    if executor.SCRATCH_ROOTS != tuple(str(r) for r in _ROOTS):
        raise RuntimeError("a test left the scratch roots pointing somewhere else")
    if executor.SANDBOX_BASE != str(_ROOTS[0] / "sandbox") or runner_helper.MQUEUE_DIR != str(_MQUEUE):
        raise RuntimeError("a test left the sandbox base or mqueue directory pointing somewhere else")
    yield _ROOTS
