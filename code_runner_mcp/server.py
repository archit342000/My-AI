import time
import hmac
import json
import logging
import os
import subprocess
from typing import List, Dict, Optional
from pydantic import BaseModel, StrictInt
import executor as executor_module
from executor import BUSY, CLEANUP_FAILED, RUN_LOCK, CodeExecutor, ExecutionResult, clear_scratch, kill_group, remove_sandbox
import sandbox_user
from fastapi import FastAPI, Header, HTTPException, Depends, status, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import asyncio
from package_names import validate_packages

logger = logging.getLogger(__name__)

# Ceiling for any client timeout (seconds). It stays below the relay's 600 s idle timeout (relay.py),
# so a long silent run is never cut by the relay before the runner times it out itself.
MAX_TIMEOUT = 580
DEFAULT_TIMEOUT = 30

app = FastAPI(title="My-AI Sandboxed Code Runner")

API_KEY_FILE = os.environ.get("API_KEY_FILE", "")


def load_api_key() -> str:
    """
    Loads the API key: the file named by `API_KEY_FILE` if it exists, else `CODE_RUNNER_API_KEY`.

    Returns:
        The stripped, non-empty key.

    Raises:
        RuntimeError: If no key is configured, so the service refuses to start instead of running open.
        OSError: If the key file exists but cannot be read.
    """
    key = ""
    if API_KEY_FILE and os.path.exists(API_KEY_FILE):
        try:
            with open(API_KEY_FILE, "r") as f:
                key = f.read().strip()
        except PermissionError as exc:
            raise RuntimeError(
                f"Cannot read {API_KEY_FILE}: the server runs without CAP_DAC_OVERRIDE, so the host key file must be "
                "readable by root (mode 644, or owned by root)") from exc
    if not key:
        key = os.environ.get("CODE_RUNNER_API_KEY", "").strip()
    if not key:
        raise RuntimeError("No API key configured: set API_KEY_FILE (a readable file) or CODE_RUNNER_API_KEY")
    return key


# Fail closed: importing this module (and so starting the service) needs a key and the right privileges.
API_KEY = load_api_key()
sandbox_user.check_privilege()
executor_module.ensure_sandbox_base()


def _key_matches(candidate: Optional[str]) -> bool:
    """Constant-time comparison of a presented key with the configured one; a missing key never matches."""
    return candidate is not None and hmac.compare_digest(candidate.encode("utf-8"), API_KEY.encode("utf-8"))


def verify_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-KEY")) -> None:
    """Dependency for the HTTP routes: 401 unless the `X-API-KEY` header carries the configured key."""
    if not _key_matches(x_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key."
        )

# Request Models
class ExecuteRequest(BaseModel):
    code: Optional[str] = None
    language: str
    stdin: Optional[str] = ""
    timeout: StrictInt | str | None = None   # a digit string is accepted; bools and floats are rejected (422)
    sql_target: Optional[str] = "sqlite"
    args: Optional[List[str]] = []
    entry_file: Optional[str] = None
    files: Optional[List[Dict[str, str]]] = None
    max_output_size: Optional[int] = 65536

class InstallRequest(BaseModel):
    packages: List[str]
    package_manager: str  # "pip" or "npm"

def _parse_timeout(value: object) -> int:
    """
    Turns a client timeout into seconds within `1..MAX_TIMEOUT`.

    Args:
        value: `None` (the default of 30), an integer, or a string of ASCII digits.

    Returns:
        The timeout in seconds; out-of-range integers are clamped, not rejected.

    Raises:
        ValueError: If the value is a bool, a float, a non-digit string or any other type.
    """
    if value is None:
        return DEFAULT_TIMEOUT
    if isinstance(value, bool):
        raise ValueError("timeout must be an integer")
    if isinstance(value, str):
        if not (value.isascii() and value.isdigit()):
            raise ValueError("timeout must be an integer")
        value = int(value)
    if not isinstance(value, int):
        raise ValueError("timeout must be an integer")
    return max(1, min(value, MAX_TIMEOUT))


COMPILE_TIMEOUT = 15  # seconds; the HTTP route uses the same bound


# Endpoints
@app.post("/execute", response_model=ExecutionResult, dependencies=[Depends(verify_api_key)])
def execute_code(req: ExecuteRequest):
    try:
        timeout = _parse_timeout(req.timeout)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return CodeExecutor.execute(
        language=req.language,
        code=req.code,
        stdin=req.stdin,
        timeout=timeout,
        sql_target=req.sql_target,
        args=req.args,
        entry_file=req.entry_file,
        files=req.files,
        max_output_size=req.max_output_size
    )

@app.post("/install", dependencies=[Depends(verify_api_key)])
def install_packages(req: InstallRequest) -> dict:
    """
    Installs packages with pip or npm.

    Only plain package names are accepted (see `package_names.py`): a leading `-`, a URL, a path or more than
    the allowed number of packages is a 400 and nothing is run.
    """
    mgr = req.package_manager.lower()
    pkgs = req.packages

    if not pkgs:
        return {"stdout": "", "stderr": "", "exit_code": 0, "success": True}

    if mgr not in ("pip", "npm"):
        raise HTTPException(status_code=400, detail=f"Unsupported package manager: {mgr}")
    try:
        validate_packages(mgr, pkgs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if mgr == "pip":
        cmd = ["pip", "install", "--target", sandbox_user.PKG_PYTHON_DIR, "--upgrade", "--no-cache-dir"] + pkgs
    else:
        cmd = ["npm", "install", "--prefix", sandbox_user.PKG_NODE_DIR] + pkgs

    # Installs run as runner-pkg (never root, never the user-code uid) into /opt/runner, one thing at a time on the runner.
    if not RUN_LOCK.acquire(timeout=executor_module.LOCK_WAIT):
        return {"stdout": "", "stderr": BUSY, "exit_code": 1, "success": False}
    try:
        try:
            res = subprocess.run(sandbox_user.limited(cmd), capture_output=True, text=True, cwd=sandbox_user.PKG_CWD if sandbox_user.isolation_enabled() else None,
                                 timeout=120, env=sandbox_user.pkg_env(mgr), **sandbox_user.spawn_kwargs("pkg"))
            result = {
                "stdout": res.stdout,
                "stderr": res.stderr,
                "exit_code": res.returncode,
                "success": res.returncode == 0
            }
        except subprocess.TimeoutExpired:
            result = {"stdout": "", "stderr": "Installation timed out after 120 seconds.", "exit_code": -1, "success": False}
        except Exception as e:
            result = {"stdout": "", "stderr": str(e), "exit_code": 1, "success": False}
        if clear_scratch():  # the installer's processes and temp files must not outlive the install
            result["success"] = False
            result["stderr"] = f"{result['stderr']}\n{CLEANUP_FAILED}".strip()
        return result
    finally:
        RUN_LOCK.release()

@app.get("/packages", dependencies=[Depends(verify_api_key)])
def list_packages(manager: str = "pip"):
    mgr = manager.lower()
    packages = []
    if mgr not in ("pip", "npm"):
        raise HTTPException(status_code=400, detail=f"Unsupported package manager: {mgr}")
    cwd = sandbox_user.PKG_CWD if sandbox_user.isolation_enabled() else None
    # Listing also runs as runner-pkg (no subprocess the server starts for a request runs as root) and under the runner
    # lock, so a run's clean-up (which kills every process of that uid) cannot cut it off.
    if not RUN_LOCK.acquire(timeout=executor_module.LOCK_WAIT):
        raise HTTPException(status_code=503, detail=BUSY)
    try:
        run_kwargs = dict(capture_output=True, text=True, cwd=cwd, timeout=30, env=sandbox_user.pkg_env(mgr), **sandbox_user.spawn_kwargs("pkg"))
        if mgr == "pip":
            try:
                res = subprocess.run(sandbox_user.limited(["pip", "list", "--path", sandbox_user.PKG_PYTHON_DIR, "--format=json"]), **run_kwargs)
                if res.returncode == 0:
                    for item in json.loads(res.stdout):
                        packages.append({"name": item.get("name"), "version": item.get("version")})
            except Exception:
                logger.exception("pip list failed")
        else:
            try:
                res = subprocess.run(sandbox_user.limited(["npm", "list", "--prefix", sandbox_user.PKG_NODE_DIR, "--json", "--depth=0"]), **run_kwargs)
                if res.returncode == 0:
                    for name, details in json.loads(res.stdout).get("dependencies", {}).items():
                        packages.append({"name": name, "version": details.get("version", "unknown")})
            except Exception:
                logger.exception("npm list failed")

    finally:
        RUN_LOCK.release()

    return {
        "packages": packages,
        "package_manager": mgr
    }

SEND_TIMEOUT = 10  # seconds; a client that stops reading must not hold the runner lock


async def _send(websocket: WebSocket, frame: dict) -> None:
    """Send a frame, giving up (TimeoutError, handled like a disconnect) if the client does not read it in time."""
    await asyncio.wait_for(websocket.send_json(frame), timeout=SEND_TIMEOUT)


async def _kill(pid: int) -> None:
    """kill_group off the event loop (it waits, bounded, for the group to disappear)."""
    await asyncio.to_thread(kill_group, pid)


@app.websocket("/ws/execute")
async def execute_ws(websocket: WebSocket) -> None:
    """Live code execution over a WebSocket. The key is read from the `X-API-KEY` header, like the HTTP routes."""
    if not _key_matches(websocket.headers.get("x-api-key")):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid API key.")
        return


    await websocket.accept()
    
    sandbox_dir = None
    process = None
    comp_process = None
    cleaned = []
    holding_lock = False
    
    try:
        # 1. Receive initial configuration
        config_data = await websocket.receive_json()
        language = config_data.get("language")
        code = config_data.get("code")
        files = config_data.get("files")
        entry_file = config_data.get("entry_file")
        args = config_data.get("args") or []
        sql_target = config_data.get("sql_target", "sqlite")
        try:
            timeout = _parse_timeout(config_data.get("timeout"))
        except ValueError:
            logger.warning("Rejected a live run with an invalid timeout")
            await _send(websocket, {"type": "stderr", "data": "Error: timeout must be an integer.\n"})
            await _send(websocket, {"type": "exit", "code": 1})
            return

        # One run at a time on the runner, whatever the app thinks (see executor.RUN_LOCK); polled so a cancelled
        # handler never leaves the lock held.
        lock_deadline = time.monotonic() + executor_module.LOCK_WAIT
        while not RUN_LOCK.acquire(blocking=False):
            if time.monotonic() >= lock_deadline:
                await _send(websocket, {"type": "stderr", "data": f"Error: {BUSY}\n"})
                await _send(websocket, {"type": "exit", "code": 1})
                return
            await asyncio.sleep(0.05)
        holding_lock = True

        async def finish(code: int, message: str = "", clear: bool = True) -> None:
            """Kill what the run left running, clear the scratch, release the runner, then tell the client: the lock is
            not held across the closing frames, and every frame sent while it is held is bounded by SEND_TIMEOUT, so a client that stops reading cannot block the runner for good. Runs once: a second call
            (for example after a failed send was mistaken for a timeout) does nothing."""
            nonlocal holding_lock
            if cleaned:
                return
            cleaned.append(True)
            cleanup_failed = False
            try:
                for proc in (comp_process, process):
                    if proc is not None:
                        await _kill(proc.pid)
                # Synchronous on purpose (no await between here and the lock release): a cancellation cannot release the
                # runner lock while a clean-up thread is still working. The helpers are bounded and take about 30 ms.
                if sandbox_dir:
                    cleanup_failed = bool(remove_sandbox(sandbox_dir))
                if clear and holding_lock:  # only the run that holds the runner clears the shared directories
                    cleanup_failed = bool(clear_scratch()) or cleanup_failed
            finally:
                # whatever happened above (even a cancellation during the awaited kill), the group is dead before the
                # runner is handed to the next run
                for proc in (comp_process, process):
                    if proc is not None:
                        try:
                            kill_group(proc.pid, wait=0)
                        except Exception:
                            logger.exception("runner_kill_error")
                if holding_lock:
                    holding_lock = False
                    RUN_LOCK.release()
            if message:
                await _send(websocket, {"type": "stderr", "data": message})
            if cleanup_failed:
                await _send(websocket, {"type": "stderr", "data": f"\nError: {CLEANUP_FAILED}\n"})
            await _send(websocket, {"type": "exit", "code": code})

        # Nothing a previous run left behind may be visible to this one; if it cannot be removed, refuse the run.
        if clear_scratch():
            await finish(1, f"Error: {CLEANUP_FAILED}\n", clear=False)
            return

        # 2. Prepare sandbox using CodeExecutor
        prep = CodeExecutor.prepare_sandbox(
            language=language,
            code=code,
            sql_target=sql_target,
            args=args,
            entry_file=entry_file,
            files=files
        )
        
        sandbox_dir = prep.get("sandbox_dir")
        if prep.get("error"):
            await finish(1, prep["error"])
            return
            
        cwd = prep["cwd"]
        env = prep["env"]
        compile_cmd = prep["compile_cmd"]
        run_cmd = prep["run_cmd"]
        written_entry_file = prep["written_entry_file"]
        lang = prep["lang"]

        # 3. Compilation phase
        if compile_cmd:
            await _send(websocket, {"type": "stdout", "data": "Compiling...\n"})
            comp_process = await asyncio.create_subprocess_exec(
                *sandbox_user.limited(compile_cmd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
                **sandbox_user.spawn_kwargs("runner")
            )
            try:
                comp_stdout, comp_stderr = await asyncio.wait_for(comp_process.communicate(), timeout=COMPILE_TIMEOUT)
            except asyncio.TimeoutError:
                await _kill(comp_process.pid)
                await _send(websocket, {"type": "stderr", "data": f"Compilation timed out after {COMPILE_TIMEOUT} seconds.\n"})
                await finish(1)
                return
            if comp_process.returncode != 0:
                await _send(websocket, {
                    "type": "stderr",
                    "data": comp_stderr.decode("utf-8", errors="replace")
                })
                await finish(comp_process.returncode)
                return
            await _send(websocket, {"type": "stdout", "data": "Compilation successful!\n"})

        # 4. Start execution process
        if lang == "sql":
            with open(written_entry_file, "r", encoding="utf-8") as f_obj:
                sql_content = f_obj.read()
            
            # SQLite (MySQL is rejected in prepare_sandbox)
            cmd = ["sqlite3", "sandbox.db", "-header", "-column"]

            process = await asyncio.create_subprocess_exec(
                *sandbox_user.limited(cmd),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
                **sandbox_user.spawn_kwargs("runner")
            )
            process.stdin.write(sql_content.encode("utf-8"))
            process.stdin.close()
        else:
            process = await asyncio.create_subprocess_exec(
                *sandbox_user.limited(run_cmd),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
                **sandbox_user.spawn_kwargs("runner")
            )

        # 5. Concurrent tasks for stdout/stderr streaming and stdin reading
        async def read_stdout():
            try:
                while True:
                    data = await process.stdout.read(1024)
                    if not data:
                        break
                    await _send(websocket, {
                        "type": "stdout",
                        "data": data.decode("utf-8", errors="replace")
                    })
            except Exception:
                await _kill(process.pid)  # the client stopped reading or went away: do not hold the runner for it

        async def read_stderr():
            try:
                while True:
                    data = await process.stderr.read(1024)
                    if not data:
                        break
                    await _send(websocket, {
                        "type": "stderr",
                        "data": data.decode("utf-8", errors="replace")
                    })
            except Exception:
                await _kill(process.pid)

        async def read_stdin():
            try:
                while True:
                    msg = await websocket.receive_json()
                    if msg.get("type") == "stdin" and msg.get("data") is not None:
                        stdin_data = msg["data"].encode("utf-8")
                        process.stdin.write(stdin_data)
                        await asyncio.wait_for(process.stdin.drain(), timeout=SEND_TIMEOUT)
            except Exception:  # a disconnect or a broken stdin: either way the run has no client any more
                await _kill(process.pid)

        stdout_task = asyncio.create_task(read_stdout())
        stderr_task = asyncio.create_task(read_stderr())
        stdin_task = asyncio.create_task(read_stdin())
        
        timed_out = False
        exit_code = -1
        try:
            exit_code = await asyncio.wait_for(process.wait(), timeout=timeout)
            await asyncio.sleep(0.1)
        except asyncio.TimeoutError:
            timed_out = True
            await _kill(process.pid)
        finally:
            stdout_task.cancel()
            stderr_task.cancel()
            stdin_task.cancel()
            try:
                if not process.stdin.is_closing():
                    process.stdin.close()
            except Exception:
                pass

        # Outside the try above, so a failed send in finish() cannot be mistaken for a run timeout
        if timed_out:
            await finish(-1, f"\nExecution timed out after {timeout} seconds.")
        else:
            await finish(exit_code)

    except Exception as e:
        if not cleaned:  # finish() already told the client (or tried to)
            try:
                await _send(websocket, {"type": "stderr", "data": f"\nServer error during execution: {e}"})
                await _send(websocket, {"type": "exit", "code": 1})
            except Exception:
                pass
    finally:
        # Whatever path got here (error, disconnect, cancellation), nothing of the run may survive it. Synchronous on
        # purpose: under cancellation an awaited call here would be cancelled again and the lock would never be freed.
        try:
            if not cleaned:  # finish() already did all of this, before releasing the lock
                for proc in (comp_process, process):
                    if proc is not None:
                        try:
                            kill_group(proc.pid)
                        except Exception:
                            logger.exception("runner_kill_error")
                if sandbox_dir:
                    remove_sandbox(sandbox_dir)
                if holding_lock:  # only the run that holds the runner may clear the shared directories
                    clear_scratch()
        finally:
            if holding_lock:
                holding_lock = False
                RUN_LOCK.release()

@app.get("/health")
def health_check():
    if executor_module.TAINTED:  # the last clean-up failed: leftovers of a run may still be there
        return JSONResponse(status_code=503, content={"status": "tainted"})
    return {
        "status": "ok",
        "languages": ["python", "c", "cpp", "java", "javascript", "typescript", "go", "rust", "bash", "php", "sql"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8100)
