"""Which uid user code (and package installs) run as, with what limits and environment.

The runtime server runs as root holding only SETUID, SETGID and KILL (docker/docker-compose.yml). Everything a user
can influence runs as a dedicated uid that is not a real host uid: `RLIMIT_NPROC` is counted host-wide per uid, so a
uid shared with a host user would make fork limits meaningless, and a host-owned file would be owned by user code.

`CODE_RUNNER_ALLOW_UNPRIVILEGED=1` is for tests and local development only: it is honoured for a non-root process
(which cannot switch uid), never for root, so user code can never run as root through it.
"""
import os
from typing import Dict, List, Optional

RUNNER_UID = int(os.environ.get("CODE_RUNNER_UID", "61001"))
RUNNER_GID = int(os.environ.get("CODE_RUNNER_GID", "61001"))
PKG_UID = int(os.environ.get("CODE_RUNNER_PKG_UID", "61002"))
PKG_GID = int(os.environ.get("CODE_RUNNER_PKG_GID", "61002"))

PKG_PYTHON_DIR = "/opt/runner/python"
PKG_NODE_DIR = "/opt/runner/node"
PKG_HOME = "/opt/runner/pkg-home"
# The cwd of package-manager children: chdir happens before the uid switch and the root server cannot enter the 0700
# pkg-home, so they start in a 0755 directory (pip and npm are given explicit target directories).
PKG_CWD = "/opt/runner"
HELPER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runner_helper.py")

# Limits applied with `prlimit` after the uid switch (never in preexec_fn before setuid). Memory is bounded by the
# container's cgroup, not RLIMIT_AS: the JVM needs about 2 GB of address space.
NPROC_LIMIT = 256
NOFILE_LIMIT = 1024

CAP_KILL, CAP_SETGID, CAP_SETUID = 5, 6, 7
REQUIRED_CAPS = (1 << CAP_KILL) | (1 << CAP_SETGID) | (1 << CAP_SETUID)

DEFAULT_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"


def allow_unprivileged() -> bool:
    return os.environ.get("CODE_RUNNER_ALLOW_UNPRIVILEGED") == "1"


def isolation_enabled() -> bool:
    """True when children are switched to the runner uids (a root server); False in the unprivileged dev/test mode."""
    return not allow_unprivileged()


STATUS_PATH = "/proc/self/status"


def read_cap_eff() -> int:
    with open(STATUS_PATH, encoding="utf-8") as status:
        for line in status:
            if line.startswith("CapEff:"):
                return int(line.split()[1], 16)
    raise RuntimeError(f"CapEff not found in {STATUS_PATH}")


def check_privilege(euid: Optional[int] = None, cap_eff: Optional[int] = None, flag: Optional[bool] = None) -> None:
    """
    Refuse to start in a state where user code could run with the server's privileges.

    A root server must hold SETUID, SETGID and KILL (to drop to the runner uids and clean up after them) and must not
    have the unprivileged flag set. A non-root process may run only with the flag (tests, local development).
    `euid`, `cap_eff` and `flag` are injectable so the root cases can be tested without being root.
    """
    euid = os.geteuid() if euid is None else euid
    flag = allow_unprivileged() if flag is None else flag
    if euid == 0:
        if flag:
            raise RuntimeError("CODE_RUNNER_ALLOW_UNPRIVILEGED must not be set for a root server: user code would run as root")
        caps = read_cap_eff() if cap_eff is None else cap_eff
        if caps != REQUIRED_CAPS:
            raise RuntimeError("The code runner must hold exactly the SETUID, SETGID and KILL capabilities "
                               f"(has {caps:#x}, needs {REQUIRED_CAPS:#x}); see docker/docker-compose.yml")
        check_uids()
        return
    if not flag:
        raise RuntimeError("The code runner must start as root (with only SETUID, SETGID and KILL) so it can run user code as a "
                           "separate uid; set CODE_RUNNER_ALLOW_UNPRIVILEGED=1 only for tests or local development")


MIN_SANDBOX_ID = 1000


def check_uids() -> None:
    """The runner and package uids/gids must be unprivileged, distinct and different from root and any normal user."""
    ids = {"CODE_RUNNER_UID": RUNNER_UID, "CODE_RUNNER_GID": RUNNER_GID, "CODE_RUNNER_PKG_UID": PKG_UID, "CODE_RUNNER_PKG_GID": PKG_GID}
    bad = [name for name, value in ids.items() if value < MIN_SANDBOX_ID]
    if bad:
        raise RuntimeError(f"{', '.join(bad)} must be at least {MIN_SANDBOX_ID}: user code must never run as root or a system uid")
    if RUNNER_UID == PKG_UID or RUNNER_GID == PKG_GID:
        raise RuntimeError("The runner and runner-pkg uids and gids must differ, or user code could modify installed packages")


def uids(kind: str = "runner") -> Dict[str, int]:
    return {"uid": PKG_UID, "gid": PKG_GID} if kind == "pkg" else {"uid": RUNNER_UID, "gid": RUNNER_GID}


def isolated_uids() -> tuple:
    """The uids whose processes, IPC objects and files cleanup removes and verifies (this process's own uid in dev mode)."""
    if isolation_enabled():
        return (RUNNER_UID, PKG_UID)
    return (os.getuid(),)


def spawn_kwargs(kind: str = "runner") -> dict:
    """`subprocess` / `asyncio.create_subprocess_exec` keyword arguments for a child of the given kind."""
    kwargs = {"start_new_session": True}
    if isolation_enabled():
        ids = uids(kind)
        kwargs.update(user=ids["uid"], group=ids["gid"], extra_groups=[])
    return kwargs


def limited(argv: List[str]) -> List[str]:
    """Prefix argv with `prlimit` (applied after the uid switch). Unchanged in the unprivileged dev/test mode."""
    if not isolation_enabled():
        return list(argv)
    return ["prlimit", f"--nproc={NPROC_LIMIT}", f"--nofile={NOFILE_LIMIT}", *argv]


def run_env(sandbox_dir: str) -> Dict[str, str]:
    """Environment of a user-code run: HOME and TMPDIR inside the sandbox, installed packages on the language paths."""
    return {
        "PATH": os.environ.get("PATH", DEFAULT_PATH),
        "HOME": os.path.join(sandbox_dir, "home"),
        "LANG": os.environ.get("LANG", "en_US.UTF-8"),
        "TMPDIR": os.path.join(sandbox_dir, "tmp"),
        "PYTHONPATH": PKG_PYTHON_DIR,
        "NODE_PATH": os.path.join(PKG_NODE_DIR, "node_modules"),
        "PYTHONUNBUFFERED": "1",
    }


def pkg_env(manager: str) -> Dict[str, str]:
    """Environment of a package manager run as runner-pkg: pip needs PATH; npm needs a writable HOME and cache."""
    env = {"PATH": os.environ.get("PATH", DEFAULT_PATH), "LANG": os.environ.get("LANG", "en_US.UTF-8")}
    for name, value in os.environ.items():  # the package proxy settings (PIP_*, npm_config_*) reach the install
        if name.startswith(("PIP_", "npm_config_")):
            env[name] = value
    if manager == "npm":
        env["HOME"] = PKG_HOME
        env["npm_config_cache"] = os.path.join(PKG_HOME, ".npm")
    return env
