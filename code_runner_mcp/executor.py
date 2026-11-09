import json
import logging
import os
import re
import signal
import subprocess
import threading
import time
import uuid
from typing import Dict, List, Optional, Any
from pydantic import BaseModel

import runner_helper
import sandbox_user

logger = logging.getLogger(__name__)

# Where every run's sandbox lives, and the directories user code can write to outside it. They are cleared before and
# after each run (see clear_scratch). Module attributes, read on every call, so tests can point them at a temp dir.
SANDBOX_BASE = "/tmp/sandbox"
SCRATCH_ROOTS = ("/tmp", "/var/tmp", "/dev/shm")
CLEANUP_FAILED = "Runner cleanup failed."
BUSY = "Code runner is busy; try again shortly."
LOCK_WAIT = 600  # seconds a run waits for the runner lock before answering busy
# The runner runs one thing at a time. The app already serialises its calls, but it can give up on a call (cancelled,
# client timeout) while the runner is still busy; without this lock the next run would start, and clear_scratch() would
# delete the directories, under the one still running. Held from the pre-run clear to the post-run clear.
RUN_LOCK = threading.Lock()
# Set by a failed clean-up, cleared by the next successful one. While set, /health answers 503 (the container shows
# unhealthy) and runs are refused by the pre-run clean-up, which keeps failing until the leftover is gone.
TAINTED = False


def scratch_roots() -> tuple:
    """The directories user code can write to outside its sandbox (the sandbox base is cleared too, see clear_scratch)."""
    return tuple(SCRATCH_ROOTS)


def ensure_sandbox_base() -> None:
    """Create the sandbox base the runner uid creates its per-run directories in (sticky, world-writable)."""
    os.makedirs(SANDBOX_BASE, exist_ok=True)
    os.chmod(SANDBOX_BASE, 0o1777)


def run_helper(command: str, payload: dict, kind: str = "runner", timeout: int = 30) -> List[str]:
    """
    Run a `runner_helper` command as the runner (or runner-pkg) uid and return the failures it reports.

    With the uid switch (a root server) the helper is a child started with `sandbox_user.spawn_kwargs(kind)`; in the
    unprivileged dev/test mode the same functions run in this process. Raises RuntimeError when the helper itself fails.
    """
    if not sandbox_user.isolation_enabled():
        if command == "make_sandbox":
            runner_helper.make_sandbox(payload["path"], payload.get("files", []))
            return []
        if command == "remove_tree":
            return runner_helper.remove_tree(payload["path"])
        if command == "clean_uid":
            return runner_helper.clean_uid(payload["roots"], payload["sandbox_base"], kill_processes=False, remove_ipc=False)
        raise RuntimeError(f"unknown helper command {command!r}")
    proc = subprocess.run(
        ["python3", sandbox_user.HELPER_PATH, command],
        input=json.dumps(payload), capture_output=True, text=True, timeout=timeout, cwd="/",
        env={"PATH": os.environ.get("PATH", sandbox_user.DEFAULT_PATH), "LANG": os.environ.get("LANG", "C.UTF-8")},
        **sandbox_user.spawn_kwargs(kind),
    )
    lines = proc.stdout.strip().splitlines()
    try:
        reply = json.loads(lines[-1]) if lines else {}
    except ValueError:
        reply = {}
    if "error" in reply:
        raise RuntimeError(reply["error"])
    if not reply:  # no (or unreadable) reply is never a success, whatever the exit code
        raise RuntimeError(f"runner helper {command} gave no reply (exit {proc.returncode}): {proc.stderr.strip()[-200:]}")
    return list(reply.get("failed", []))


def remove_sandbox(path: str) -> List[str]:
    """Remove a run directory through the helper (the root server cannot read inside trees the runner uid made)."""
    return run_helper("remove_tree", {"path": path})


def _owned_by_isolated_uid(path: str) -> bool:
    try:
        return os.lstat(path).st_uid in sandbox_user.isolated_uids()
    except FileNotFoundError:
        return False
    except OSError:
        return True  # cannot even look at it: treat as left behind


PROCESS_EXIT_WAIT = 1.0  # seconds to let killed processes disappear before reporting them


def isolated_processes() -> List[str]:
    """Pids of live (not zombie) processes whose real uid is one of the isolated uids. Reads the Uid line of
    /proc/<pid>/status: the owner of /proc/<pid> is root for a process that made itself non-dumpable."""
    found = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            uid, state = None, ""
            with open(f"/proc/{entry}/status", encoding="utf-8") as status:
                for line in status:
                    if line.startswith("Uid:"):
                        uid = int(line.split()[1])
                    elif line.startswith("State:"):
                        state = line.split()[1]
        except OSError:
            continue
        if uid in sandbox_user.isolated_uids() and state != "Z":
            found.append(entry)
    return found


def verify_clean() -> List[str]:
    """
    Check, as the server, that nothing of the isolated uids is left: entries in the scratch roots and the sandbox base,
    `/dev/mqueue` entries, SysV IPC objects and processes. An entry owned by those uids counts even when its contents
    cannot be listed. Returns what is left.
    """
    left: List[str] = []
    base = os.path.abspath(SANDBOX_BASE)
    for root in dict.fromkeys(scratch_roots() + (SANDBOX_BASE, runner_helper.MQUEUE_DIR)):
        try:
            names = os.listdir(root)
        except FileNotFoundError:
            continue
        except OSError:
            left.append(root)
            continue
        for name in names:
            path = os.path.join(root, name)
            if os.path.abspath(path) == base:
                continue
            if _owned_by_isolated_uid(path):
                left.append(path)
    if sandbox_user.isolation_enabled():
        for uid in sandbox_user.isolated_uids():
            left.extend(f"sysv-ipc:{flag}{ident}" for flag, ident in runner_helper.sysv_objects(uid))
        deadline = time.monotonic() + PROCESS_EXIT_WAIT
        while True:
            alive = isolated_processes()
            if not alive or time.monotonic() >= deadline:
                break
            time.sleep(0.02)  # just-killed processes need a moment to be reaped
        left.extend(f"process:{pid}" for pid in alive)
    return left


def clear_scratch() -> List[str]:
    """
    Clean up after the isolated uids and verify it: a helper running as each uid removes that uid's files, IPC objects
    and processes, then the server checks nothing is left. Returns what could not be cleaned (each logged as
    runner_cleanup_error); an empty list means clean.
    """
    failed: List[str] = []
    kinds = ("runner", "pkg") if sandbox_user.isolation_enabled() else ("runner",)
    for kind in kinds:
        try:
            failed.extend(run_helper("clean_uid", {"roots": list(scratch_roots()), "sandbox_base": SANDBOX_BASE}, kind))
        except Exception as exc:  # a broken helper is a cleanup failure, never silently ignored
            failed.append(f"helper:{kind}:{exc}")
    failed.extend(verify_clean())
    global TAINTED
    TAINTED = bool(failed)
    for path in dict.fromkeys(failed):
        logger.error("runner_cleanup_error path=%s", path)
    return list(dict.fromkeys(failed))


def kill_group(pid: int, wait: float = 1.0) -> None:
    """SIGKILL the process group started for a run (user code and everything it spawned or backgrounded) and wait,
    bounded, until no member is left, so the clean-up that follows does not race a dying process."""
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        try:
            os.killpg(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.01)


def _run_in_group(cmd, cwd, env, timeout, input_text=None, text=True):
    """Run cmd in its own session so its whole process group can be killed afterwards. Returns
    (returncode, stdout, stderr); raises subprocess.TimeoutExpired after killing the group."""
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        env=env,
        text=text,
        **sandbox_user.spawn_kwargs("runner"),
    )
    try:
        out, err = proc.communicate(input=input_text, timeout=timeout)
        return proc.returncode, out, err
    except subprocess.TimeoutExpired:
        kill_group(proc.pid)
        try:
            proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            # something outside the group (setsid) still holds the pipes: give up on its output rather than hang
            # while holding the runner lock
            for stream in (proc.stdout, proc.stderr, proc.stdin):
                try:
                    if stream:
                        stream.close()
                except Exception:
                    pass
        raise
    finally:
        kill_group(proc.pid)


class ExecutionResult(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    execution_time_ms: int
    language: str
    timed_out: bool
    error: Optional[str] = None

class CodeExecutor:
    @classmethod
    def prepare_sandbox(
        cls,
        language: str,
        code: Optional[str] = None,
        sql_target: str = "sqlite",
        args: Optional[List[str]] = None,
        entry_file: Optional[str] = None,
        files: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        lang = language.lower()
        args = args or []
        
        # 1. Create a unique sandbox directory
        sandbox_id = uuid.uuid4().hex
        sandbox_dir = os.path.join(SANDBOX_BASE, sandbox_id)
        files_to_write: List[Dict[str, str]] = []

        try:
            # MySQL is not served here: the runner has no database credentials or route.
            if lang == "sql" and sql_target == "mysql":
                return {"error": "MySQL is not available in the code runner; use sqlite.", "sandbox_dir": sandbox_dir}

            # 2. Write files
            written_entry_file = None
            
            if files:
                # Recreate directory structure
                for f in files:
                    rel_path = f.get("path")
                    # Prevent directory traversal attacks
                    if not rel_path or ".." in rel_path or rel_path.startswith("/"):
                        continue
                    file_content = f.get("content", "")
                    full_path = os.path.abspath(os.path.join(sandbox_dir, rel_path))
                    if not full_path.startswith(os.path.abspath(sandbox_dir)):
                        continue
                    files_to_write.append({"path": rel_path, "content": file_content})

                if entry_file:
                    candidate = os.path.abspath(os.path.join(sandbox_dir, entry_file))
                    # The root server stats (and, for SQL, reads) the entry file: it must be a plain path inside the sandbox.
                    if os.path.isabs(entry_file) or ".." in entry_file.split("/") or not candidate.startswith(os.path.abspath(sandbox_dir) + os.sep):
                        return {"error": "Invalid entry file path.", "sandbox_dir": sandbox_dir}
                    written_entry_file = candidate
            else:
                # Single file execution via `code` string
                code_content = code or ""
                if lang == "python":
                    entry_name = "main.py"
                elif lang == "c":
                    entry_name = "main.c"
                elif lang == "cpp":
                    entry_name = "main.cpp"
                elif lang == "java":
                    # Parse public class name
                    class_match = re.search(r"\bpublic\s+class\s+(\w+)\b", code_content)
                    class_name = class_match.group(1) if class_match else "Main"
                    entry_name = f"{class_name}.java"
                elif lang == "javascript":
                    entry_name = "main.js"
                elif lang == "typescript":
                    entry_name = "main.ts"
                elif lang == "go":
                    entry_name = "main.go"
                elif lang == "rust":
                    entry_name = "main.rs"
                elif lang == "bash":
                    entry_name = "script.sh"
                elif lang == "php":
                    entry_name = "index.php"
                elif lang == "sql":
                    entry_name = "query.sql"
                else:
                    entry_name = "code.txt"

                written_entry_file = os.path.join(sandbox_dir, entry_name)
                files_to_write.append({"path": entry_name, "content": code_content})

            # The files are written, and the run directory made, by the runner uid (the helper): the server cannot.
            failures = run_helper("make_sandbox", {"path": sandbox_dir, "files": files_to_write})
            if failures:
                return {"error": "Could not prepare the sandbox.", "sandbox_dir": sandbox_dir}

            if not written_entry_file or not os.path.exists(written_entry_file):
                return {"error": "No valid entry file found.", "sandbox_dir": sandbox_dir}

            # 3. Setup stripped environment
            env = sandbox_user.run_env(sandbox_dir)

            cwd = os.path.dirname(written_entry_file)
            entry_basename = os.path.basename(written_entry_file)

            # 4. Process compile and execution commands
            compile_cmd = None
            run_cmd = []

            if lang == "python":
                run_cmd = ["python3", entry_basename] + args
            elif lang == "c":
                binary_path = "./a.out"
                compile_cmd = ["gcc", "-O2", "-o", "a.out", entry_basename]
                run_cmd = ["stdbuf", "-o0", "-e0", binary_path] + args
            elif lang == "cpp":
                binary_path = "./a.out"
                compile_cmd = ["g++", "-O2", "-o", "a.out", entry_basename]
                run_cmd = ["stdbuf", "-o0", "-e0", binary_path] + args
            elif lang == "java":
                # Compile
                compile_cmd = ["javac", entry_basename]
                # Determine class name to execute
                class_basename = os.path.splitext(entry_basename)[0]
                run_cmd = ["stdbuf", "-o0", "-e0", "java", "-cp", ".", class_basename] + args
            elif lang == "javascript":
                run_cmd = ["node", entry_basename] + args
            elif lang == "typescript":
                run_cmd = ["tsx", entry_basename] + args
            elif lang == "go":
                run_cmd = ["go", "run", entry_basename] + args
            elif lang == "rust":
                binary_path = "./a.out"
                compile_cmd = ["rustc", "-o", "a.out", entry_basename]
                run_cmd = ["stdbuf", "-o0", "-e0", binary_path] + args
            elif lang == "bash":
                run_cmd = ["bash", entry_basename] + args
            elif lang == "php":
                run_cmd = ["stdbuf", "-o0", "-e0", "php", entry_basename] + args
            elif lang == "sql":
                pass
            else:
                return {"error": f"Unsupported language: {lang}", "sandbox_dir": sandbox_dir}

            return {
                "sandbox_dir": sandbox_dir,
                "cwd": cwd,
                "env": env,
                "compile_cmd": compile_cmd,
                "run_cmd": run_cmd,
                "written_entry_file": written_entry_file,
                "lang": lang,
                "error": None
            }
        except Exception as e:
            return {"error": str(e), "sandbox_dir": sandbox_dir}

    @classmethod
    def execute(cls, language: str, *args, **kwargs) -> ExecutionResult:
        """Run code between two scratch clean-ups: leftovers of earlier runs are removed first (a failure refuses the
        run), and whatever this run left behind (files, background processes' files) is removed afterwards (a failure
        is reported on the result)."""
        if not RUN_LOCK.acquire(timeout=LOCK_WAIT):
            return ExecutionResult(stdout="", stderr="", exit_code=1, execution_time_ms=0,
                                   language=language.lower(), timed_out=False, error=BUSY)
        try:
            if clear_scratch():
                return ExecutionResult(stdout="", stderr="", exit_code=1, execution_time_ms=0,
                                       language=language.lower(), timed_out=False, error=CLEANUP_FAILED)
            try:
                result = cls._execute(language, *args, **kwargs)
            except BaseException:
                clear_scratch()  # an unexpected error must not leave this run's files for the next one
                raise
            if clear_scratch():
                result.error = f"{result.error} {CLEANUP_FAILED}" if result.error else CLEANUP_FAILED
            return result
        finally:
            RUN_LOCK.release()

    @classmethod
    def _execute(
        cls,
        language: str,
        code: Optional[str] = None,
        stdin: Optional[str] = None,
        timeout: int = 30,
        sql_target: str = "sqlite",
        args: Optional[List[str]] = None,
        entry_file: Optional[str] = None,
        files: Optional[List[Dict[str, str]]] = None,
        max_output_size: int = 65536
    ) -> ExecutionResult:
        stdin = stdin or ""

        prep = cls.prepare_sandbox(
            language=language,
            code=code,
            sql_target=sql_target,
            args=args,
            entry_file=entry_file,
            files=files
        )
        
        sandbox_dir = prep.get("sandbox_dir")
        if prep.get("error"):
            remove_sandbox(sandbox_dir)
            return ExecutionResult(
                stdout="",
                stderr="",
                exit_code=1,
                execution_time_ms=0,
                language=language.lower(),
                timed_out=False,
                error=prep["error"]
            )
            
        cwd = prep["cwd"]
        env = prep["env"]
        compile_cmd = prep["compile_cmd"]
        run_cmd = prep["run_cmd"]
        written_entry_file = prep["written_entry_file"]
        lang = prep["lang"]

        try:
            # Compilation phase if required
            if compile_cmd:
                comp_code, _comp_out, comp_err = _run_in_group(sandbox_user.limited(compile_cmd), cwd, env, 15, text=False)
                if comp_code != 0:
                    return ExecutionResult(
                        stdout="",
                        stderr=comp_err.decode("utf-8", errors="replace"),
                        exit_code=comp_code,
                        execution_time_ms=0,
                        language=lang,
                        timed_out=False,
                        error="Compilation failed."
                    )

            # Run phase
            start_time = time.time()
            timed_out = False
            
            if lang == "sql":
                # SQL execution
                with open(written_entry_file, "r", encoding="utf-8") as f_obj:
                    sql_content = f_obj.read()
                
                # SQLite (MySQL is rejected in prepare_sandbox)
                cmd = ["sqlite3", "sandbox.db", "-header", "-column"]

                try:
                    exit_code, stdout, stderr = _run_in_group(sandbox_user.limited(cmd), cwd, env, timeout, input_text=sql_content)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    stdout = ""
                    stderr = f"Execution timed out after {timeout} seconds."
                    exit_code = -1
            else:
                # Standard language run
                try:
                    exit_code, stdout, stderr = _run_in_group(sandbox_user.limited(run_cmd), cwd, env, timeout, input_text=stdin)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    stdout = ""
                    stderr = f"Execution timed out after {timeout} seconds."
                    exit_code = -1

            exec_time_ms = int((time.time() - start_time) * 1000)

            # 5. Cap outputs
            def cap_output(text: str) -> str:
                if len(text.encode("utf-8")) > max_output_size:
                    # truncate and append notice
                    truncated = text.encode("utf-8")[:max_output_size].decode("utf-8", errors="ignore")
                    return truncated + "\n\n[OUTPUT TRUNCATED]"
                return text

            return ExecutionResult(
                stdout=cap_output(stdout),
                stderr=cap_output(stderr),
                exit_code=exit_code,
                execution_time_ms=exec_time_ms,
                language=lang,
                timed_out=timed_out,
                error=None if not timed_out else "Execution timed out"
            )

        except Exception as e:
            return ExecutionResult(
                stdout="",
                stderr="",
                exit_code=1,
                execution_time_ms=0,
                language=lang,
                timed_out=False,
                error=str(e)
            )
        finally:
            # Remove this run's sandbox (as the runner uid); the scratch roots are cleaned by execute()
            remove_sandbox(sandbox_dir)
