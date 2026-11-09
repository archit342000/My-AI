"""Operations that must run as the runner uid: the root server (no CAP_DAC_OVERRIDE, CAP_CHOWN or CAP_FOWNER) cannot
create files that uid can use, nor clear what it left behind (0700 trees, SysV IPC objects).

Two ways in, same functions:
- as a script, `python3 runner_helper.py <command>` with a JSON payload on stdin, started by the server as the runner
  (or runner-pkg) uid (see `sandbox_user.spawn_kwargs`);
- imported, in the unprivileged dev/test mode where no uid switch happens (see `sandbox_user.isolation_enabled`).

Commands: make_sandbox, remove_tree, clean_uid.
"""
import json
import os
import shutil
import signal
import subprocess
import sys
from typing import Dict, List

DIR_MODE = 0o755
MQUEUE_DIR = "/dev/mqueue"  # a module attribute so tests never touch the real one
FILE_MODE = 0o644
PRIVATE_MODE = 0o700


def _inside(base: str, path: str) -> bool:
    base = os.path.abspath(base)
    path = os.path.abspath(path)
    return path == base or path.startswith(base + os.sep)


def make_sandbox(path: str, files: List[Dict[str, str]]) -> None:
    """
    Create the run directory (and `home/`, `tmp/`) and write the files, with explicit modes (not the umask): the
    directory and its subdirectories 0755 and the files 0644, so the root server can traverse and read the entry file;
    `home/` and `tmp/` 0700. Paths must stay inside the run directory.
    """
    os.makedirs(path, mode=DIR_MODE, exist_ok=True)
    os.chmod(path, DIR_MODE)
    for private in ("home", "tmp"):
        os.makedirs(os.path.join(path, private), mode=PRIVATE_MODE, exist_ok=True)
        os.chmod(os.path.join(path, private), PRIVATE_MODE)
    for item in files:
        rel = item.get("path")
        if not rel or os.path.isabs(rel) or ".." in rel.split("/"):
            raise ValueError(f"unsafe path: {rel!r}")
        full = os.path.join(path, rel)
        if not _inside(path, full):
            raise ValueError(f"path escapes the sandbox: {rel!r}")
        if rel.split("/")[0] in ("home", "tmp"):
            raise ValueError(f"{rel!r} is under a private directory (home/, tmp/) the root server cannot read")
        parent = os.path.dirname(full)
        missing = []
        probe = parent
        while not os.path.isdir(probe) and _inside(path, probe):
            missing.append(probe)
            probe = os.path.dirname(probe)
        for directory in reversed(missing):
            os.mkdir(directory, DIR_MODE)
            os.chmod(directory, DIR_MODE)
        if not _inside(os.path.realpath(path), os.path.realpath(parent)):
            raise ValueError(f"path escapes the sandbox through a symlink: {rel!r}")
        fd = os.open(full, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, FILE_MODE)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(item.get("content", ""))
        os.chmod(full, FILE_MODE)


def _make_removable(path: str) -> None:
    """Restore owner rwx on a tree (user code may have made directories 0555 or 0000) so it can be removed."""
    for root, dirs, _files in os.walk(path, topdown=True, followlinks=False):
        try:
            os.chmod(root, os.stat(root).st_mode | 0o700)
        except OSError:
            pass
        for name in dirs:
            full = os.path.join(root, name)
            if os.path.islink(full):
                continue
            try:
                os.chmod(full, os.stat(full).st_mode | 0o700)
            except OSError:
                pass


def remove_tree(path: str) -> List[str]:
    """Remove a file, symlink or tree (never following symlinks). Returns the paths that could not be removed."""
    failed: List[str] = []
    if not os.path.lexists(path):
        return failed
    if os.path.isdir(path) and not os.path.islink(path):
        _make_removable(path)
        if sys.version_info >= (3, 12):
            shutil.rmtree(path, onexc=lambda _fn, p, _exc: failed.append(p))
        else:
            shutil.rmtree(path, onerror=lambda _fn, p, _info: failed.append(p))
    else:
        try:
            os.unlink(path)
        except OSError:
            failed.append(path)
    return failed


def remove_entries(roots: List[str], uid: int) -> List[str]:
    """Remove every entry directly inside each root that is owned by `uid` (the roots stay)."""
    failed: List[str] = []
    for root in roots:
        try:
            names = os.listdir(root)
        except FileNotFoundError:
            continue
        except OSError:
            failed.append(root)
            continue
        for name in names:
            path = os.path.join(root, name)
            try:
                if os.lstat(path).st_uid != uid:
                    continue
            except FileNotFoundError:
                continue
            except OSError:
                failed.append(path)
                continue
            failed.extend(remove_tree(path))
    return failed


SYSV = (("/proc/sysvipc/shm", 7, "-m"), ("/proc/sysvipc/sem", 4, "-s"), ("/proc/sysvipc/msg", 7, "-q"))


def sysv_objects(uid: int) -> List[tuple]:
    """(ipcrm flag, id) of every SysV shm/sem/msg object owned by `uid`, read from /proc/sysvipc."""
    found = []
    for table, uid_col, flag in SYSV:
        try:
            lines = open(table, encoding="utf-8").read().splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            cols = line.split()
            if len(cols) > uid_col and int(cols[uid_col]) == uid:
                found.append((flag, cols[1]))
    return found


def remove_sysv_ipc(uid: int) -> List[str]:
    failed = []
    for flag, ident in sysv_objects(uid):
        result = subprocess.run(["ipcrm", flag, ident], capture_output=True, text=True)
        if result.returncode != 0:
            failed.append(f"sysv-ipc:{flag}{ident}")
    return failed


def clean_uid(roots: List[str], sandbox_base: str, kill_processes: bool = True, remove_ipc: bool = True) -> List[str]:
    """
    Remove what this uid left behind: its entries in the scratch roots, `/dev/mqueue` and the sandbox base, its SysV IPC
    objects and, last, every process of the uid (`kill(-1)` spares the caller, so run it after everything else).
    Returns the failures.
    """
    uid = os.getuid()
    failed = remove_entries(list(roots) + [sandbox_base, MQUEUE_DIR], uid)
    if remove_ipc:
        failed.extend(remove_sysv_ipc(uid))
    if kill_processes:
        try:
            os.kill(-1, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except OSError as exc:
            failed.append(f"kill:{exc}")
    return failed


def main(argv: List[str]) -> int:
    command = argv[1] if len(argv) > 1 else ""
    payload = json.loads(sys.stdin.read() or "{}")
    os.umask(0o022)
    try:
        if command == "make_sandbox":
            make_sandbox(payload["path"], payload.get("files", []))
            failed: List[str] = []
        elif command == "remove_tree":
            failed = remove_tree(payload["path"])
        elif command == "clean_uid":
            failed = clean_uid(payload.get("roots", []), payload.get("sandbox_base", ""))
        else:
            print(json.dumps({"error": f"unknown command {command!r}"}))
            return 2
    except Exception as exc:  # reported to the server, which refuses the run: never swallowed
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}))
        return 1
    print(json.dumps({"failed": failed}))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
