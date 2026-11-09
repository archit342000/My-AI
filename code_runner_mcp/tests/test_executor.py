import json
import os
import subprocess
import threading
import time
from unittest.mock import patch

import pytest

import executor
from executor import CodeExecutor
from helpers import _gone, _grandchild_code, read_pid

def test_execute_python_success():
    res = CodeExecutor.execute(
        language="python",
        code="print('Hello from sandbox')"
    )
    assert res.exit_code == 0
    assert "Hello from sandbox" in res.stdout
    assert res.stderr == ""
    assert not res.timed_out

def test_execute_python_error():
    res = CodeExecutor.execute(
        language="python",
        code="raise ValueError('Intentional error')"
    )
    assert res.exit_code != 0
    assert "ValueError: Intentional error" in res.stderr
    assert not res.timed_out

def test_execute_python_timeout():
    res = CodeExecutor.execute(
        language="python",
        code="import time\ntime.sleep(2)",
        timeout=1
    )
    assert res.timed_out
    assert "timed out" in res.error

def test_execute_python_multi_file():
    files = [
        {"path": "main.py", "content": "from helpers.utils import add\nprint(add(2, 3))"},
        {"path": "helpers/__init__.py", "content": ""},
        {"path": "helpers/utils.py", "content": "def add(a, b): return a + b"}
    ]
    res = CodeExecutor.execute(
        language="python",
        files=files,
        entry_file="main.py"
    )
    assert res.exit_code == 0
    assert "5" in res.stdout

def test_execute_sqlite():
    import shutil
    if not shutil.which("sqlite3"):
        pytest.skip("sqlite3 executable not found in path")
    res = CodeExecutor.execute(
        language="sql",
        code="CREATE TABLE test (val TEXT);\nINSERT INTO test VALUES ('hello');\nSELECT * FROM test;",
        sql_target="sqlite"
    )
    assert res.exit_code == 0
    assert "hello" in res.stdout

def test_execute_sql_mysql_is_rejected(monkeypatch):
    import os
    import executor as executor_module
    # Pin the sandbox id so the test can check that execute() removes that directory.
    monkeypatch.setattr(executor_module.uuid, "uuid4", lambda: type("U", (), {"hex": "mysqlreject"})())
    res = CodeExecutor.execute(
        language="sql",
        code="SELECT 1;",
        sql_target="mysql"
    )
    assert res.exit_code == 1
    assert "MySQL is not available" in res.error
    assert not res.timed_out
    assert not os.path.exists(os.path.join(executor_module.SANDBOX_BASE, "mysqlreject"))  # the isolated base, never the real /tmp

def test_prepare_sandbox_mysql_error_returns_sandbox_dir_for_cleanup():
    import os
    import shutil
    prep = CodeExecutor.prepare_sandbox(
        language="sql",
        code="SELECT 1;",
        sql_target="mysql"
    )
    assert "MySQL is not available" in prep["error"]
    # the sandbox is made by the helper only after the checks pass, so nothing exists yet; removing it is a safe no-op
    assert not os.path.exists(prep["sandbox_dir"])
    assert executor.remove_sandbox(prep["sandbox_dir"]) == []

def test_execute_cpp():
    import shutil
    if not shutil.which("g++"):
        pytest.skip("g++ not found in path")
    res = CodeExecutor.execute(
        language="cpp",
        code='#include <iostream>\nint main() {\n    std::cout << "Hello from C++" << std::endl;\n    return 0;\n}'
    )
    assert res.exit_code == 0
    assert "Hello from C++" in res.stdout


# --- clean between runs: per-run HOME/TMPDIR, process groups, scratch clearing ------------------------------------

def test_home_and_tmpdir_are_inside_the_sandbox():
    prep = CodeExecutor.prepare_sandbox(language="python", code="print(1)")
    try:
        sandbox = prep["sandbox_dir"]
        assert prep["env"]["HOME"] == os.path.join(sandbox, "home") and os.path.isdir(prep["env"]["HOME"])
        assert prep["env"]["TMPDIR"] == os.path.join(sandbox, "tmp") and os.path.isdir(prep["env"]["TMPDIR"])
        assert prep["env"]["PYTHONPATH"] == "/opt/runner/python"  # installed packages still load
        assert prep["env"]["NODE_PATH"] == "/opt/runner/node/node_modules"
    finally:
        executor.clear_scratch()


def test_a_run_sees_its_own_home_and_tmp_and_leaves_nothing_behind(isolated_scratch):
    res = CodeExecutor.execute(language="python", code="import os, pathlib\nprint(os.environ['HOME'])\nprint(os.environ['TMPDIR'])\n"
                                                       "pathlib.Path(os.environ['TMPDIR'], 'x').write_text('1')")
    home, tmp = res.stdout.split()[:2]
    assert home.startswith(executor.SANDBOX_BASE) and tmp.startswith(executor.SANDBOX_BASE)
    for root in isolated_scratch:
        assert list(root.iterdir()) == []  # the sandbox and every scratch directory are empty again


def test_every_user_code_subprocess_starts_a_new_session():
    import shutil
    if not (shutil.which("gcc") and shutil.which("sqlite3")):
        pytest.skip("gcc and sqlite3 are needed for the compile and sql phases")
    calls = []
    real_popen = subprocess.Popen

    def spy(*args, **kwargs):
        calls.append(kwargs)
        return real_popen(*args, **kwargs)

    with patch("executor.subprocess.Popen", spy):
        CodeExecutor.execute(language="c", code="int main(){return 0;}")  # compile phase + run phase
        CodeExecutor.execute(language="sql", code="select 1;")
        CodeExecutor.execute(language="python", code="print(1)")
    assert len(calls) >= 4 and all(c.get("start_new_session") is True for c in calls)


def test_the_process_group_is_killed_after_a_timeout(tmp_path):
    pidfile = tmp_path / "pid"
    res = CodeExecutor.execute(language="python", code=_grandchild_code(pidfile) + "time.sleep(30)", timeout=2)
    assert res.timed_out
    assert _gone(read_pid(pidfile)), "a grandchild survived the timeout"


def test_the_process_group_is_killed_after_a_normal_exit(tmp_path):
    pidfile = tmp_path / "pid"
    res = CodeExecutor.execute(language="python", code=_grandchild_code(pidfile) + "print('done')")
    assert res.exit_code == 0
    assert _gone(read_pid(pidfile)), "a background child survived a normal exit"


def test_kill_group_of_an_exited_process_is_a_noop():
    proc = subprocess.Popen(["true"], start_new_session=True)
    proc.wait()
    executor.kill_group(proc.pid)  # must not raise


def test_default_scratch_roots_and_sandbox_base_are_the_documented_ones():
    # read from the source, so the autouse fixture's temp roots do not hide a regression
    import importlib.util
    spec = importlib.util.spec_from_file_location("executor_fresh", executor.__file__)
    fresh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fresh)
    assert fresh.SANDBOX_BASE == "/tmp/sandbox"
    assert fresh.SCRATCH_ROOTS == ("/tmp", "/var/tmp", "/dev/shm")


def test_two_runs_never_overlap_even_when_started_together():
    code = "import time\nprint(time.time())\ntime.sleep(1)\nprint(time.time())"
    spans = []

    def run():
        out = CodeExecutor.execute(language="python", code=code).stdout.split()
        spans.append((float(out[0]), float(out[1])))

    threads = [threading.Thread(target=run) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    (s1, e1), (s2, e2) = sorted(spans)
    assert s2 >= e1, "the second run started before the first one had finished"


def test_clear_scratch_removes_everything_under_every_root_and_keeps_the_roots(isolated_scratch):
    for i, root in enumerate(isolated_scratch):
        (root / f"file{i}").write_text("x")
        (root / f"dir{i}").mkdir()
        (root / f"dir{i}" / "inner").write_text("y")
    (isolated_scratch[0] / "link").symlink_to(isolated_scratch[1])  # a symlink is removed, never followed
    assert executor.clear_scratch() == []
    assert all(root.is_dir() and list(root.iterdir()) == [] for root in isolated_scratch)
    assert os.path.isdir(isolated_scratch[1])


def test_clear_scratch_reads_the_module_roots_on_every_call(tmp_path, monkeypatch):
    other = tmp_path / "other-root"
    other.mkdir()
    (other / "x").write_text("1")
    monkeypatch.setattr(executor, "SCRATCH_ROOTS", (str(other),))
    assert executor.scratch_roots() == (str(other),)
    executor.clear_scratch()
    assert list(other.iterdir()) == []


def test_a_failed_removal_is_reported_and_logged(isolated_scratch, caplog):
    (isolated_scratch[0] / "stuck").write_text("x")
    real_unlink = os.unlink

    def failing_unlink(path, *a, **k):
        if str(path).endswith("stuck"):
            raise PermissionError("nope")
        return real_unlink(path, *a, **k)

    with patch("executor.os.unlink", failing_unlink), caplog.at_level("ERROR"):
        failed = executor.clear_scratch()
    assert failed == [str(isolated_scratch[0] / "stuck")]
    assert any("runner_cleanup_error" in r.getMessage() and "stuck" in r.getMessage() for r in caplog.records)


def test_a_post_run_clear_failure_is_reported_in_the_result():
    with patch("executor.clear_scratch", side_effect=[[], ["/tmp/stuck"]]):  # pre-run ok, post-run fails
        res = CodeExecutor.execute(language="python", code="print('ran')")
    assert "ran" in res.stdout and res.error == "Runner cleanup failed."


def test_a_pre_run_clear_failure_refuses_the_run_without_executing_it():
    with patch("executor.clear_scratch", return_value=["/tmp/leftover"]), patch("executor.subprocess.Popen") as popen:
        res = CodeExecutor.execute(language="python", code="print('must not run')")
    popen.assert_not_called()
    assert res.error == "Runner cleanup failed." and res.exit_code == 1 and res.stdout == ""


def test_leftovers_of_a_previous_run_are_gone_before_the_next_run_starts(isolated_scratch):
    (isolated_scratch[0] / "left-by-run-1").write_text("secret")
    (isolated_scratch[2] / "shm-left").write_text("secret")
    res = CodeExecutor.execute(language="python", code=f"import os\nprint(os.path.exists({str(isolated_scratch[0] / 'left-by-run-1')!r}), os.path.exists({str(isolated_scratch[2] / 'shm-left')!r}))")
    assert res.stdout.split() == ["False", "False"]


def test_a_detached_child_holding_the_pipes_cannot_wedge_the_runner(tmp_path):
    # setsid escapes the group kill (a documented residual) and keeps the output pipes open: execute() must still return
    pidfile = tmp_path / "escapee"
    code = ("import subprocess\n"
            f"p = subprocess.Popen(['sleep', '60'], start_new_session=True)\nopen({str(pidfile)!r}, 'w').write(str(p.pid))\n"
            "print('parent done')")
    try:
        started = time.time()
        res = CodeExecutor.execute(language="python", code=code, timeout=1)
        assert time.time() - started < 30
        assert not executor.RUN_LOCK.locked()
    finally:
        try:
            os.kill(read_pid(pidfile), 9)  # the escapee is the test's to clean up
        except (FileNotFoundError, ValueError, ProcessLookupError):
            pass
    assert res.error in (None, "Execution timed out")


def test_execute_answers_busy_when_the_runner_lock_cannot_be_taken(monkeypatch):
    monkeypatch.setattr(executor, "LOCK_WAIT", 0.2)
    with executor.RUN_LOCK:
        res = CodeExecutor.execute(language="python", code="print(1)")
    assert res.error == executor.BUSY and res.exit_code == 1 and res.stdout == ""


def test_a_failed_cleanup_is_added_to_the_runs_own_error():
    with patch("executor.clear_scratch", side_effect=[[], ["/tmp/stuck"]]):
        res = CodeExecutor.execute(language="python", code="import time\ntime.sleep(5)", timeout=1)
    assert res.timed_out and res.error == "Execution timed out Runner cleanup failed."


def test_kill_group_does_not_return_until_every_member_is_gone(tmp_path):
    pidfile = tmp_path / "pid"
    proc = subprocess.Popen(["python3", "-c", _grandchild_code(pidfile) + "time.sleep(60)"], start_new_session=True)
    grandchild = read_pid(pidfile)
    executor.kill_group(proc.pid)
    proc.wait()  # reap the leader only after kill_group has returned
    with pytest.raises(ProcessLookupError):
        os.kill(grandchild, 0)  # the grandchild was already gone when kill_group returned


# --- uid isolation: the helper does the creating and cleaning, children run as the runner uid ------------------------

class TestIsolation:
    @pytest.fixture(autouse=True)
    def isolated(self, monkeypatch):
        monkeypatch.delenv("CODE_RUNNER_ALLOW_UNPRIVILEGED")

    def test_run_helper_starts_the_helper_as_the_requested_uid_with_a_json_payload(self):
        done = type("P", (), {"stdout": '{"failed": []}\n', "stderr": "", "returncode": 0})()
        with patch("executor.subprocess.run", return_value=done) as run:
            assert executor.run_helper("make_sandbox", {"path": "/tmp/sandbox/x", "files": []}) == []
            assert executor.run_helper("clean_uid", {"roots": [], "sandbox_base": "/tmp/sandbox"}, kind="pkg") == []
        runner_call, pkg_call = run.call_args_list
        assert runner_call.args[0][-1] == "make_sandbox" and runner_call.kwargs["user"] == 61001
        assert pkg_call.kwargs["user"] == 61002 and pkg_call.kwargs["extra_groups"] == []
        assert json.loads(runner_call.kwargs["input"])["path"] == "/tmp/sandbox/x"
        assert runner_call.kwargs["env"].keys() == {"PATH", "LANG"}  # the server's environment (the key) never reaches it

    def test_run_helper_reports_failures_and_raises_on_a_helper_error(self):
        failed = type("P", (), {"stdout": '{"failed": ["/tmp/stuck"]}\n', "stderr": "", "returncode": 1})()
        with patch("executor.subprocess.run", return_value=failed):
            assert executor.run_helper("clean_uid", {"roots": [], "sandbox_base": ""}) == ["/tmp/stuck"]
        broken = type("P", (), {"stdout": '{"error": "OSError: boom"}\n', "stderr": "", "returncode": 1})()
        with patch("executor.subprocess.run", return_value=broken), pytest.raises(RuntimeError, match="boom"):
            executor.run_helper("make_sandbox", {"path": "/x", "files": []})
        crashed = type("P", (), {"stdout": "", "stderr": "Traceback", "returncode": 139})()
        with patch("executor.subprocess.run", return_value=crashed), pytest.raises(RuntimeError, match="no reply \(exit 139\)"):
            executor.run_helper("make_sandbox", {"path": "/x", "files": []})

    def test_user_code_children_run_as_the_runner_uid_under_prlimit(self):
        calls = []

        class FakePopen:
            returncode = 0
            pid = 4242

            def __init__(self, cmd, **kwargs):
                calls.append((cmd, kwargs))

            def communicate(self, input=None, timeout=None):
                return "", ""

        with patch("executor.run_helper", return_value=[]), patch("executor.subprocess.Popen", FakePopen), \
             patch("executor.kill_group"), patch("executor.clear_scratch", return_value=[]), patch("executor.os.path.exists", return_value=True):
            CodeExecutor.execute(language="c", code="int main(){return 0;}")
        assert len(calls) == 2  # compile and run
        for cmd, kwargs in calls:
            assert cmd[0] == "prlimit" and "--nproc=256" in cmd and not any(a.startswith("--as") for a in cmd)
            assert kwargs["user"] == 61001 and kwargs["group"] == 61001 and kwargs["extra_groups"] == []
            assert kwargs["start_new_session"] is True
            assert kwargs["env"]["PYTHONPATH"] == "/opt/runner/python"

    def test_the_sandbox_is_made_and_removed_by_the_helper_around_a_successful_run(self):
        class FakePopen:
            returncode = 0
            pid = 4243

            def __init__(self, cmd, **kwargs):
                pass

            def communicate(self, input=None, timeout=None):
                return "hi\n", ""

        with patch("executor.run_helper", return_value=[]) as helper, patch("executor.clear_scratch", return_value=[]), \
             patch("executor.subprocess.Popen", FakePopen), patch("executor.kill_group"), \
             patch("executor.os.path.exists", return_value=True):
            res = CodeExecutor.execute(language="python", code="print(1)")
        assert res.error is None and res.stdout == "hi\n"
        commands = [c.args[0] for c in helper.call_args_list]
        assert commands[0] == "make_sandbox" and commands[-1] == "remove_tree"

    def test_clear_scratch_runs_the_helper_as_both_uids_then_verifies(self):
        with patch("executor.run_helper", return_value=[]) as helper, patch("executor.verify_clean", return_value=[]):
            assert executor.clear_scratch() == []
        assert [c.args[0] for c in helper.call_args_list] == ["clean_uid", "clean_uid"]
        assert [c.args[2] if len(c.args) > 2 else c.kwargs.get("kind") for c in helper.call_args_list] == ["runner", "pkg"]

    def test_a_broken_helper_or_leftovers_are_cleanup_failures(self):
        with patch("executor.run_helper", side_effect=RuntimeError("boom")), patch("executor.verify_clean", return_value=["process:7"]):
            failed = executor.clear_scratch()
        assert any("boom" in f for f in failed) and "process:7" in failed

    def test_verify_clean_finds_leftover_entries_ipc_objects_and_processes(self, isolated_scratch, monkeypatch):
        me = os.getuid()
        monkeypatch.setattr("executor.sandbox_user.isolated_uids", lambda: (me,))  # "the runner uid" is this test's own uid
        monkeypatch.setattr("executor.runner_helper.sysv_objects", lambda uid: [("-m", "7")])
        (isolated_scratch[0] / "left").write_text("x")
        os.symlink("/nonexistent", isolated_scratch[1] / "dangling")  # an owned entry counts even if it points nowhere
        left = executor.verify_clean()
        assert str(isolated_scratch[0] / "left") in left and str(isolated_scratch[1] / "dangling") in left
        assert "sysv-ipc:-m7" in left and f"process:{os.getpid()}" in left

    def test_verify_clean_skips_the_sandbox_base_itself_but_not_a_sibling_owned_by_the_uid(self, isolated_scratch, monkeypatch):
        monkeypatch.setattr("executor.sandbox_user.isolated_uids", lambda: (os.getuid(),))
        monkeypatch.setattr("executor.runner_helper.sysv_objects", lambda uid: [])
        monkeypatch.setattr("executor.isolated_processes", lambda: [])
        executor.ensure_sandbox_base()  # owned by "the isolated uid" too: only the base itself is exempt
        (isolated_scratch[0] / "sibling").write_text("x")
        left = executor.verify_clean()
        assert executor.SANDBOX_BASE not in left and str(isolated_scratch[0] / "sibling") in left

    def test_verify_clean_ignores_entries_of_other_uids(self, isolated_scratch, monkeypatch):
        monkeypatch.setattr("executor.sandbox_user.isolated_uids", lambda: (os.getuid() + 12345,))
        monkeypatch.setattr("executor.runner_helper.sysv_objects", lambda uid: [])
        monkeypatch.setattr("executor.isolated_processes", lambda: [])
        (isolated_scratch[0] / "server-file").write_text("x")
        assert executor.verify_clean() == []

    def test_verify_clean_reports_an_unlistable_root(self, monkeypatch):
        monkeypatch.setattr("executor.sandbox_user.isolated_uids", lambda: (os.getuid(),))
        monkeypatch.setattr("executor.runner_helper.sysv_objects", lambda uid: [])
        monkeypatch.setattr("executor.isolated_processes", lambda: [])
        real = os.listdir

        def listdir(path="."):
            if str(path) == executor.SCRATCH_ROOTS[0]:
                raise PermissionError("denied")
            return real(path)

        monkeypatch.setattr("executor.os.listdir", listdir)
        assert executor.SCRATCH_ROOTS[0] in executor.verify_clean()

    def test_isolated_processes_finds_live_processes_of_the_uid(self, monkeypatch):
        monkeypatch.setattr("executor.sandbox_user.isolated_uids", lambda: (os.getuid(),))
        assert str(os.getpid()) in executor.isolated_processes()
        monkeypatch.setattr("executor.sandbox_user.isolated_uids", lambda: (os.getuid() + 12345,))
        assert executor.isolated_processes() == []

    def test_a_missing_or_unreadable_helper_reply_is_never_a_success(self):
        for stdout, code in (("", 0), ("not json\n", 0)):
            done = type("P", (), {"stdout": stdout, "stderr": "", "returncode": code})()
            with patch("executor.subprocess.run", return_value=done), pytest.raises(RuntimeError, match="no reply"):
                executor.run_helper("make_sandbox", {"path": "/x", "files": []})

    def test_the_dev_mode_helper_rejects_an_unknown_command_and_never_kills_or_removes_ipc(self, monkeypatch):
        monkeypatch.setenv("CODE_RUNNER_ALLOW_UNPRIVILEGED", "1")
        with pytest.raises(RuntimeError, match="unknown helper command"):
            executor.run_helper("nope", {})
        with patch("executor.runner_helper.clean_uid", return_value=[]) as clean:
            executor.run_helper("clean_uid", {"roots": [], "sandbox_base": "/x"})
        assert clean.call_args.kwargs == {"kill_processes": False, "remove_ipc": False}  # kill(-1) would kill the developer's session


@pytest.mark.parametrize("bad", ["/run/keys/CODE_RUNNER_API_KEY", "../escape.py", "a/../../escape.py"])
def test_an_entry_file_outside_the_sandbox_is_rejected_before_the_server_reads_it(bad):
    with patch("executor.run_helper", return_value=[]) as helper:
        prep = CodeExecutor.prepare_sandbox(language="sql", files=[{"path": "query.sql", "content": "select 1;"}], entry_file=bad)
    assert prep["error"] == "Invalid entry file path."
    helper.assert_not_called()


def test_a_normal_nested_entry_file_is_accepted(isolated_scratch):
    prep = CodeExecutor.prepare_sandbox(language="python", files=[{"path": "pkg/main.py", "content": "print(1)"}], entry_file="pkg/main.py")
    try:
        assert prep["error"] is None and prep["written_entry_file"].endswith("/pkg/main.py") and prep["cwd"].endswith("/pkg")
    finally:
        executor.remove_sandbox(prep["sandbox_dir"])
