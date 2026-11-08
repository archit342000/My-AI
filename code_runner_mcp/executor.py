import os
import re
import shutil
import subprocess
import time
import uuid
from typing import Dict, List, Optional, Any
from pydantic import BaseModel

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
        sandbox_dir = os.path.join("/tmp/sandbox", sandbox_id)
        os.makedirs(sandbox_dir, exist_ok=True)

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
                    
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    with open(full_path, "w", encoding="utf-8") as file_obj:
                        file_obj.write(file_content)
                
                if entry_file:
                    written_entry_file = os.path.join(sandbox_dir, entry_file)
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
                with open(written_entry_file, "w", encoding="utf-8") as file_obj:
                    file_obj.write(code_content)

            if not written_entry_file or not os.path.exists(written_entry_file):
                return {"error": "No valid entry file found.", "sandbox_dir": sandbox_dir}

            # 3. Setup stripped environment
            env = {
                "PATH": os.environ.get("PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"),
                "HOME": os.environ.get("HOME", "/home/runner"),
                "LANG": os.environ.get("LANG", "en_US.UTF-8"),
                "TMPDIR": "/tmp",
                "PYTHONPATH": "/home/runner/.local/lib/python3.12/site-packages",
                "NODE_PATH": "/home/runner/node_modules",
                "PYTHONUNBUFFERED": "1"
            }

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
    def execute(
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
            shutil.rmtree(sandbox_dir, ignore_errors=True)
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
                comp_res = subprocess.run(
                    compile_cmd,
                    capture_output=True,
                    cwd=cwd,
                    env=env,
                    timeout=15
                )
                if comp_res.returncode != 0:
                    return ExecutionResult(
                        stdout="",
                        stderr=comp_res.stderr.decode("utf-8", errors="replace"),
                        exit_code=comp_res.returncode,
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
                    res = subprocess.run(
                        cmd,
                        input=sql_content,
                        text=True,
                        capture_output=True,
                        cwd=cwd,
                        env=env,
                        timeout=timeout
                    )
                    stdout = res.stdout
                    stderr = res.stderr
                    exit_code = res.returncode
                except subprocess.TimeoutExpired:
                    timed_out = True
                    stdout = ""
                    stderr = f"Execution timed out after {timeout} seconds."
                    exit_code = -1
            else:
                # Standard language run
                try:
                    res = subprocess.run(
                        run_cmd,
                        input=stdin,
                        text=True,
                        capture_output=True,
                        cwd=cwd,
                        env=env,
                        timeout=timeout
                    )
                    stdout = res.stdout
                    stderr = res.stderr
                    exit_code = res.returncode
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
            # Clean up the sandbox directory
            shutil.rmtree(sandbox_dir, ignore_errors=True)
