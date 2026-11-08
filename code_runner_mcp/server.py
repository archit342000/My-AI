import json
import os
import subprocess
from typing import List, Dict, Optional
from pydantic import BaseModel
from executor import CodeExecutor, ExecutionResult
from fastapi import FastAPI, Header, HTTPException, Depends, status, WebSocket, WebSocketDisconnect
import asyncio
import shutil

app = FastAPI(title="My-AI Sandboxed Code Runner")

# Load API Key on startup
API_KEY_FILE = os.environ.get("API_KEY_FILE", "")
API_KEY = ""
if API_KEY_FILE and os.path.exists(API_KEY_FILE):
    try:
        with open(API_KEY_FILE, "r") as f:
            API_KEY = f.read().strip()
    except Exception:
        pass

if not API_KEY:
    API_KEY = os.environ.get("CODE_RUNNER_API_KEY", "")

def verify_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-KEY")):
    # If API_KEY is configured, enforce verification
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key."
        )

# Request Models
class ExecuteRequest(BaseModel):
    code: Optional[str] = None
    language: str
    stdin: Optional[str] = ""
    timeout: Optional[int] = 30
    sql_target: Optional[str] = "sqlite"
    args: Optional[List[str]] = []
    entry_file: Optional[str] = None
    files: Optional[List[Dict[str, str]]] = None
    max_output_size: Optional[int] = 65536

class InstallRequest(BaseModel):
    packages: List[str]
    package_manager: str  # "pip" or "npm"

# Endpoints
@app.post("/execute", response_model=ExecutionResult, dependencies=[Depends(verify_api_key)])
def execute_code(req: ExecuteRequest):
    return CodeExecutor.execute(
        language=req.language,
        code=req.code,
        stdin=req.stdin,
        timeout=req.timeout,
        sql_target=req.sql_target,
        args=req.args,
        entry_file=req.entry_file,
        files=req.files,
        max_output_size=req.max_output_size
    )

@app.post("/install", dependencies=[Depends(verify_api_key)])
def install_packages(req: InstallRequest):
    mgr = req.package_manager.lower()
    pkgs = req.packages
    
    if not pkgs:
        return {"stdout": "", "stderr": "", "exit_code": 0, "success": True}

    if mgr == "pip":
        # Install with --user to avoid permissions issue as runner user
        cmd = ["pip", "install", "--user", "--no-cache-dir"] + pkgs
        cwd = None
    elif mgr == "npm":
        # Install in home directory of the runner user
        cmd = ["npm", "install", "--no-save"] + pkgs
        cwd = "/home/runner"
        os.makedirs(cwd, exist_ok=True)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported package manager: {mgr}")

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=120)
        return {
            "stdout": res.stdout,
            "stderr": res.stderr,
            "exit_code": res.returncode,
            "success": res.returncode == 0
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": "Installation timed out after 120 seconds.",
            "exit_code": -1,
            "success": False
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": str(e),
            "exit_code": 1,
            "success": False
        }

@app.get("/packages", dependencies=[Depends(verify_api_key)])
def list_packages(manager: str = "pip"):
    mgr = manager.lower()
    packages = []
    
    if mgr == "pip":
        cmd = ["pip", "list", "--format=json"]
        cwd = None
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=30)
            if res.returncode == 0:
                data = json.loads(res.stdout)
                for item in data:
                    packages.append({
                        "name": item.get("name"),
                        "version": item.get("version")
                    })
        except Exception:
            pass
    elif mgr == "npm":
        cmd = ["npm", "list", "--json", "--depth=0"]
        cwd = "/home/runner"
        if os.path.exists(cwd):
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=30)
                if res.returncode == 0:
                    data = json.loads(res.stdout)
                    deps = data.get("dependencies", {})
                    for name, details in deps.items():
                        packages.append({
                            "name": name,
                            "version": details.get("version", "unknown")
                        })
            except Exception:
                pass
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported package manager: {mgr}")

    return {
        "packages": packages,
        "package_manager": mgr
    }

@app.websocket("/ws/execute")
async def execute_ws(websocket: WebSocket, api_key: Optional[str] = None):
    # Verify API key
    expected_api_key = API_KEY
    if expected_api_key and api_key != expected_api_key:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid API key.")
        return
        
    await websocket.accept()
    
    sandbox_dir = None
    process = None
    
    try:
        # 1. Receive initial configuration
        config_data = await websocket.receive_json()
        language = config_data.get("language")
        code = config_data.get("code")
        files = config_data.get("files")
        entry_file = config_data.get("entry_file")
        args = config_data.get("args") or []
        sql_target = config_data.get("sql_target", "sqlite")
        timeout = config_data.get("timeout", 30)

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
            await websocket.send_json({"type": "stderr", "data": prep["error"]})
            await websocket.send_json({"type": "exit", "code": 1})
            return
            
        cwd = prep["cwd"]
        env = prep["env"]
        compile_cmd = prep["compile_cmd"]
        run_cmd = prep["run_cmd"]
        written_entry_file = prep["written_entry_file"]
        lang = prep["lang"]

        # 3. Compilation phase
        if compile_cmd:
            await websocket.send_json({"type": "stdout", "data": "Compiling...\n"})
            comp_process = await asyncio.create_subprocess_exec(
                *compile_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env
            )
            comp_stdout, comp_stderr = await comp_process.communicate()
            if comp_process.returncode != 0:
                await websocket.send_json({
                    "type": "stderr",
                    "data": comp_stderr.decode("utf-8", errors="replace")
                })
                await websocket.send_json({
                    "type": "exit",
                    "code": comp_process.returncode
                })
                return
            await websocket.send_json({"type": "stdout", "data": "Compilation successful!\n"})

        # 4. Start execution process
        if lang == "sql":
            with open(written_entry_file, "r", encoding="utf-8") as f_obj:
                sql_content = f_obj.read()
            
            # SQLite (MySQL is rejected in prepare_sandbox)
            cmd = ["sqlite3", "sandbox.db", "-header", "-column"]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env
            )
            process.stdin.write(sql_content.encode("utf-8"))
            process.stdin.close()
        else:
            process = await asyncio.create_subprocess_exec(
                *run_cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env
            )

        # 5. Concurrent tasks for stdout/stderr streaming and stdin reading
        async def read_stdout():
            try:
                while True:
                    data = await process.stdout.read(1024)
                    if not data:
                        break
                    await websocket.send_json({
                        "type": "stdout",
                        "data": data.decode("utf-8", errors="replace")
                    })
            except Exception:
                pass

        async def read_stderr():
            try:
                while True:
                    data = await process.stderr.read(1024)
                    if not data:
                        break
                    await websocket.send_json({
                        "type": "stderr",
                        "data": data.decode("utf-8", errors="replace")
                    })
            except Exception:
                pass

        async def read_stdin():
            try:
                while True:
                    msg = await websocket.receive_json()
                    if msg.get("type") == "stdin" and msg.get("data") is not None:
                        stdin_data = msg["data"].encode("utf-8")
                        process.stdin.write(stdin_data)
                        await process.stdin.drain()
            except WebSocketDisconnect:
                try:
                    process.terminate()
                except Exception:
                    pass
            except Exception:
                pass

        stdout_task = asyncio.create_task(read_stdout())
        stderr_task = asyncio.create_task(read_stderr())
        stdin_task = asyncio.create_task(read_stdin())
        
        try:
            exit_code = await asyncio.wait_for(process.wait(), timeout=timeout)
            await asyncio.sleep(0.1)
            await websocket.send_json({
                "type": "exit",
                "code": exit_code
            })
        except asyncio.TimeoutError:
            try:
                process.kill()
            except Exception:
                pass
            await websocket.send_json({
                "type": "stderr",
                "data": f"\nExecution timed out after {timeout} seconds."
            })
            await websocket.send_json({
                "type": "exit",
                "code": -1
            })
        finally:
            stdout_task.cancel()
            stderr_task.cancel()
            stdin_task.cancel()
            try:
                if not process.stdin.is_closing():
                    process.stdin.close()
            except Exception:
                pass

    except Exception as e:
        try:
            await websocket.send_json({"type": "stderr", "data": f"\nServer error during execution: {e}"})
            await websocket.send_json({"type": "exit", "code": 1})
        except Exception:
            pass
    finally:
        if sandbox_dir:
            shutil.rmtree(sandbox_dir, ignore_errors=True)

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "languages": ["python", "c", "cpp", "java", "javascript", "typescript", "go", "rust", "bash", "php", "sql"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8100)
