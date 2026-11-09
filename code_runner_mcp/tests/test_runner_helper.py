"""runner_helper: the operations that run as the runner uid (here in-process, in a temp directory)."""
import json
import os
import stat
import subprocess
import sys

import pytest

import runner_helper as rh


def mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


def test_make_sandbox_uses_explicit_modes_whatever_the_umask(tmp_path):
    old = os.umask(0o077)  # a strict umask must not make the entry unreadable for the root server
    try:
        rh.make_sandbox(str(tmp_path / "run"), [{"path": "main.py", "content": "print(1)"},
                                                {"path": "pkg/sub/mod.py", "content": "x = 1"}])
    finally:
        os.umask(old)
    run = tmp_path / "run"
    assert mode(run) == 0o755 and mode(run / "pkg") == 0o755 and mode(run / "pkg" / "sub") == 0o755
    assert mode(run / "home") == 0o700 and mode(run / "tmp") == 0o700
    assert mode(run / "main.py") == 0o644 and (run / "main.py").read_text() == "print(1)"
    assert mode(run / "pkg" / "sub" / "mod.py") == 0o644


@pytest.mark.parametrize("bad", ["../escape.py", "/etc/passwd", "a/../../b.py", ""])
def test_make_sandbox_refuses_unsafe_paths(tmp_path, bad):
    with pytest.raises(ValueError):
        rh.make_sandbox(str(tmp_path / "run"), [{"path": bad, "content": "x"}])
    assert not (tmp_path / "escape.py").exists()


def test_make_sandbox_does_not_follow_a_symlink_planted_at_a_file_path(tmp_path):
    run = tmp_path / "run"
    rh.make_sandbox(str(run), [])
    target = tmp_path / "victim"
    target.write_text("keep")
    os.symlink(target, run / "main.py")
    with pytest.raises(OSError):
        rh.make_sandbox(str(run), [{"path": "main.py", "content": "overwritten"}])
    assert target.read_text() == "keep"


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses the permission checks this test is about")
def test_remove_tree_removes_a_tree_the_user_made_non_writable(tmp_path):
    tree = tmp_path / "tree"
    (tree / "a" / "b").mkdir(parents=True)
    (tree / "a" / "b" / "f").write_text("x")
    os.chmod(tree / "a" / "b", 0o000)
    os.chmod(tree / "a", 0o555)
    assert rh.remove_tree(str(tree)) == []
    assert not tree.exists()


def test_remove_tree_unlinks_a_symlink_without_following_it(tmp_path):
    target = tmp_path / "keep"
    target.mkdir()
    (target / "f").write_text("x")
    link = tmp_path / "link"
    os.symlink(target, link)
    assert rh.remove_tree(str(link)) == []
    assert not link.exists() and (target / "f").exists()


def test_remove_entries_removes_only_entries_owned_by_the_uid(tmp_path):
    root = tmp_path / "scratch"
    root.mkdir()
    (root / "mine").write_text("x")
    (root / "dir").mkdir()
    (root / "dir" / "f").write_text("x")
    assert rh.remove_entries([str(root)], os.getuid() + 12345) == []  # someone else's uid: nothing is touched
    assert sorted(os.listdir(root)) == ["dir", "mine"]
    assert rh.remove_entries([str(root)], os.getuid()) == []
    assert os.listdir(root) == [] and root.exists()


def test_remove_entries_ignores_a_missing_root(tmp_path):
    assert rh.remove_entries([str(tmp_path / "nope")], os.getuid()) == []


def test_sysv_objects_parse_the_owner_column(tmp_path, monkeypatch):
    shm = tmp_path / "shm"
    shm.write_text("key shmid perms size cpid lpid nattch uid gid cuid cgid\n0 7 600 4096 1 1 0 61001 61001 61001 61001\n0 8 600 4096 1 1 0 0 0 0 0\n")
    sem = tmp_path / "sem"
    sem.write_text("key semid perms nsems uid gid cuid cgid\n0 3 600 1 61001 61001 61001 61001\n")
    monkeypatch.setattr(rh, "SYSV", ((str(shm), 7, "-m"), (str(sem), 4, "-s"), (str(tmp_path / "missing"), 7, "-q")))
    assert rh.sysv_objects(61001) == [("-m", "7"), ("-s", "3")]
    assert rh.sysv_objects(0) == [("-m", "8")]


def test_clean_uid_in_process_mode_removes_entries_and_never_kills_without_being_asked(tmp_path):
    root, base = tmp_path / "scratch", tmp_path / "sandbox"
    root.mkdir(); base.mkdir()
    (root / "left").write_text("x"); (base / "run").mkdir()
    assert rh.clean_uid([str(root)], str(base), kill_processes=False, remove_ipc=False) == []
    assert os.listdir(root) == [] and os.listdir(base) == []


def run_script(command, payload):
    return subprocess.run([sys.executable, rh.__file__, command], input=json.dumps(payload), capture_output=True, text=True)


def test_script_entry_point_reports_failures_and_errors_as_json(tmp_path):
    ok = run_script("make_sandbox", {"path": str(tmp_path / "run"), "files": [{"path": "m.py", "content": "x"}]})
    assert ok.returncode == 0 and json.loads(ok.stdout.splitlines()[-1]) == {"failed": []}
    bad = run_script("make_sandbox", {"path": str(tmp_path / "run2"), "files": [{"path": "../x", "content": "x"}]})
    assert bad.returncode == 1 and "unsafe path" in json.loads(bad.stdout.splitlines()[-1])["error"]
    unknown = run_script("nope", {})
    assert unknown.returncode == 2


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses the permission checks this test is about")
def test_remove_tree_reports_what_it_could_not_remove(tmp_path, monkeypatch):
    locked = tmp_path / "locked"
    locked.mkdir()
    (locked / "f").write_text("x")
    monkeypatch.setattr(rh, "_make_removable", lambda path: None)  # simulate a tree the owner cannot unlock
    os.chmod(locked, 0o500)
    try:
        assert rh.remove_tree(str(locked)) != []
    finally:
        os.chmod(locked, 0o700)


def test_make_sandbox_refuses_a_symlinked_directory_component(tmp_path):
    run, outside = tmp_path / "run", tmp_path / "outside"
    rh.make_sandbox(str(run), [])
    outside.mkdir()
    os.symlink(outside, run / "pkg")
    with pytest.raises((ValueError, OSError)):
        rh.make_sandbox(str(run), [{"path": "pkg/mod.py", "content": "x"}])
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize("rel", ["home/x.py", "tmp/x.py"])
def test_make_sandbox_refuses_files_under_the_private_directories(tmp_path, rel):
    with pytest.raises(ValueError, match="private"):
        rh.make_sandbox(str(tmp_path / "run"), [{"path": rel, "content": "x"}])


def test_remove_sysv_ipc_runs_ipcrm_for_each_owned_object_and_reports_failures(monkeypatch):
    monkeypatch.setattr(rh, "sysv_objects", lambda uid: [("-m", "7"), ("-s", "3"), ("-q", "9")])
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return type("P", (), {"returncode": 1 if argv[-1] == "3" else 0})()

    monkeypatch.setattr(rh.subprocess, "run", fake_run)
    assert rh.remove_sysv_ipc(61001) == ["sysv-ipc:-s3"]
    assert calls == [["ipcrm", "-m", "7"], ["ipcrm", "-s", "3"], ["ipcrm", "-q", "9"]]


def test_sysv_objects_include_message_queues(tmp_path, monkeypatch):
    msg = tmp_path / "msg"
    msg.write_text("key msqid perms cbytes qnum lspid lrpid uid gid cuid cgid\n0 5 600 0 0 0 0 61001 61001 61001 61001\n")
    monkeypatch.setattr(rh, "SYSV", ((str(msg), 7, "-q"),))
    assert rh.sysv_objects(61001) == [("-q", "5")]


def test_clean_uid_kills_only_when_asked_and_uses_kill_minus_one(tmp_path, monkeypatch):
    kills = []
    monkeypatch.setattr(rh.os, "kill", lambda pid, sig: kills.append((pid, sig)))
    monkeypatch.setattr(rh, "MQUEUE_DIR", str(tmp_path / "mq"))
    monkeypatch.setattr(rh, "remove_sysv_ipc", lambda uid: [])
    rh.clean_uid([str(tmp_path)], str(tmp_path / "sb"), kill_processes=False)
    assert kills == []
    rh.clean_uid([str(tmp_path)], str(tmp_path / "sb"))
    assert kills == [(-1, rh.signal.SIGKILL)]
