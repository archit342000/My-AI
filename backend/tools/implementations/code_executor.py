import json
import logging
import os
import requests
import uuid
from typing import Optional, List, Dict, Any

from backend import config
from backend.database import db
from backend.file_system.utils import resolve_owner_and_physical_path
from backend.logging import log_event
from backend.tools.clarify import request_clarification
from code_runner_mcp.safety import classify_code

logger = logging.getLogger(__name__)

def find_project_root(physical_path: str, root_dir: str) -> str:
    """
    Find the project root by searching upwards for configuration/project files,
    stopping when the VFS root directory is reached.
    """
    markers = {
        "setup.py", "pyproject.toml", "__init__.py",
        "package.json", "pom.xml", "build.gradle",
        "go.mod", "Cargo.toml", "Makefile", "CMakeLists.txt"
    }
    current = os.path.dirname(physical_path)
    root_dir_abs = os.path.abspath(root_dir)
    
    while True:
        current_abs = os.path.abspath(current)
        if any(os.path.exists(os.path.join(current_abs, m)) for m in markers):
            return current_abs
        if current_abs == root_dir_abs or len(current_abs) <= len(root_dir_abs):
            break
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
        
    return root_dir_abs

async def run_code(
    code: str,
    language: str,
    stdin: Optional[str] = None,
    sql_target: Optional[str] = "sqlite",
    chat_id: Optional[str] = None,
    tool_call_id: Optional[str] = None,
    parent_message_id: Optional[str] = None,
    **kwargs
) -> str:
    """Execute code in a sandboxed environment."""
    lang = language.lower()
    stdin = stdin or ""
    sql_target = sql_target or "sqlite"

    # Get timeout from settings
    timeout = db.get_setting("code_runner_timeout", config.CODE_RUNNER_DEFAULT_TIMEOUT)

    # Perform safety classification check
    safety_status = classify_code(code, lang)
    if safety_status == "dangerous":
        question = (
            f"Warning: The code you are about to run contains potentially dangerous commands "
            f"(e.g. system calls, network access, file write/delete, or mutative SQL):\n\n"
            f"```\n{code}\n```\n\nDo you want to proceed with executing this code?"
        )
        options = ["Yes, run it", "No, cancel"]
        response = await request_clarification(
            question=question,
            options=options,
            chat_id=chat_id,
            tool_call_id=tool_call_id,
            parent_message_id=parent_message_id,
            **kwargs
        )
        if "Yes" not in response:
            return "Execution cancelled by user."

    # Call the external code runner service
    url = f"{config.CODE_RUNNER_URL.rstrip('/')}/execute"
    headers = {"X-API-KEY": config.CODE_RUNNER_API_KEY}
    payload = {
        "code": code,
        "language": lang,
        "stdin": stdin,
        "timeout": timeout,
        "sql_target": sql_target,
        "max_output_size": db.get_setting("code_runner_max_output_size", config.CODE_RUNNER_MAX_OUTPUT_SIZE)
    }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=timeout + 5)
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        logger.error(f"Failed to communicate with code runner service: {e}")
        log_event("code_executor_run_code_error", {"chat_id": chat_id, "error": type(e).__name__})
        return "Error: Failed to execute code. Code runner service is unavailable."

    stdout = data.get("stdout", "")
    stderr = data.get("stderr", "")
    exit_code = data.get("exit_code", 0)
    exec_time = data.get("execution_time_ms", 0)
    timed_out = data.get("timed_out", False)

    # Store execution record in DB
    record_id = "exec_" + uuid.uuid4().hex[:16]
    if chat_id:
        try:
            db.add_code_execution_record(
                record_id=record_id,
                chat_id=chat_id,
                message_id=parent_message_id,
                tool_call_id=tool_call_id,
                language=lang,
                code=code,
                stdin=stdin,
                files_json=None,
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                execution_time_ms=exec_time,
                timed_out=1 if timed_out else 0
            )
        except Exception as e:
            logger.error(f"Failed to log code execution in DB: {e}")

    # Format result for the LLM response
    result_str = f"**Language:** {lang} | **Exit Code:** {exit_code} | **Time:** {exec_time}ms"
    if timed_out:
        result_str += " | **TIMED OUT**"
    result_str += f"\n\n**stdout:**\n```\n{stdout}\n```\n\n**stderr:**\n```\n{stderr}\n```"
    return result_str

def collect_project_files(chat_id: str, path: str):
    """Walk and collect files in directory tree for code execution."""
    _, _, physical_target_path = resolve_owner_and_physical_path(chat_id, path)
    _, _, chat_root_dir = resolve_owner_and_physical_path(chat_id, "")
    
    if not os.path.exists(physical_target_path):
        raise FileNotFoundError(f"File '{path}' does not exist.")
        
    ext = os.path.splitext(physical_target_path)[1].lower()
    lang = config.CODE_EXTENSION_MAP.get(ext)
    if not lang:
        raise ValueError(f"File extension '{ext}' is not supported for execution.")
        
    project_root = find_project_root(physical_target_path, chat_root_dir)
    
    files_list = []
    total_size = 0
    max_files = 100
    max_total_size = 5 * 1024 * 1024
    
    for dirpath, _, filenames in os.walk(project_root):
        if ".git" in dirpath.split(os.sep):
            continue
        for filename in filenames:
            if len(files_list) >= max_files:
                break
            full_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(full_path, project_root)
            
            try:
                file_size = os.path.getsize(full_path)
                if total_size + file_size > max_total_size:
                    continue
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if "\0" in content:
                    continue
                files_list.append({"path": rel_path, "content": content})
                total_size += file_size
            except Exception:
                continue
                
    entry_file = os.path.relpath(physical_target_path, project_root)
    return lang, files_list, entry_file

async def run_file(
    path: str,
    stdin: Optional[str] = None,
    args: Optional[List[str]] = None,
    sql_target: Optional[str] = "sqlite",
    chat_id: Optional[str] = None,
    tool_call_id: Optional[str] = None,
    parent_message_id: Optional[str] = None,
    **kwargs
) -> str:
    """Execute a file from the virtual file system including all project tree files."""
    if not chat_id:
        return "Error: Missing chat context."

    # Resolve target file relative path to physical file path
    try:
        _, _, physical_target_path = resolve_owner_and_physical_path(chat_id, path)
        _, _, chat_root_dir = resolve_owner_and_physical_path(chat_id, "")
    except Exception as e:
        return f"Error: Failed to resolve file path: {e}"

    if not os.path.exists(physical_target_path):
        return f"Error: File '{path}' does not exist."

    # Map extension to language
    ext = os.path.splitext(physical_target_path)[1].lower()
    lang = config.CODE_EXTENSION_MAP.get(ext)
    if not lang:
        return f"Error: File extension '{ext}' is not supported for execution."

    # Find the project root
    project_root = find_project_root(physical_target_path, chat_root_dir)

    # Collect recursively all text files under project root
    files_list = []
    total_size = 0
    max_files = 100
    max_total_size = 5 * 1024 * 1024 # 5MB limit
    
    for dirpath, _, filenames in os.walk(project_root):
        # Prevent traversal of special dirs
        if ".git" in dirpath.split(os.sep):
            continue
        for filename in filenames:
            if len(files_list) >= max_files:
                break
            full_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(full_path, project_root)
            
            try:
                file_size = os.path.getsize(full_path)
                if total_size + file_size > max_total_size:
                    continue
                
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
                # Skip binary files containing null bytes
                if "\0" in content:
                    continue
                
                files_list.append({"path": rel_path, "content": content})
                total_size += file_size
            except Exception:
                continue

    entry_file = os.path.relpath(physical_target_path, project_root)
    stdin = stdin or ""
    args = args or []
    sql_target = sql_target or "sqlite"

    # Get timeout from settings
    timeout = db.get_setting("code_runner_timeout", config.CODE_RUNNER_DEFAULT_TIMEOUT)

    # Read target code content for safety classification check
    target_code = ""
    for f in files_list:
        if f["path"] == entry_file:
            target_code = f["content"]
            break

    if target_code:
        safety_status = classify_code(target_code, lang)
        if safety_status == "dangerous":
            question = (
                f"Warning: The entry file '{entry_file}' contains potentially dangerous commands:\n\n"
                f"```\n{target_code[:300]}...\n```\n\nDo you want to proceed with executing this file?"
            )
            options = ["Yes, run it", "No, cancel"]
            response = await request_clarification(
                question=question,
                options=options,
                chat_id=chat_id,
                tool_call_id=tool_call_id,
                parent_message_id=parent_message_id,
                **kwargs
            )
            if "Yes" not in response:
                return "Execution cancelled by user."

    # Call the external code runner service
    url = f"{config.CODE_RUNNER_URL.rstrip('/')}/execute"
    headers = {"X-API-KEY": config.CODE_RUNNER_API_KEY}
    payload = {
        "language": lang,
        "entry_file": entry_file,
        "files": files_list,
        "stdin": stdin,
        "args": args,
        "timeout": timeout,
        "sql_target": sql_target,
        "max_output_size": db.get_setting("code_runner_max_output_size", config.CODE_RUNNER_MAX_OUTPUT_SIZE)
    }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=timeout + 5)
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        logger.error(f"Failed to communicate with code runner service: {e}")
        return f"Error: Failed to execute file. Code runner service is unavailable: {e}"

    stdout = data.get("stdout", "")
    stderr = data.get("stderr", "")
    exit_code = data.get("exit_code", 0)
    exec_time = data.get("execution_time_ms", 0)
    timed_out = data.get("timed_out", False)

    # Store execution record in DB
    record_id = "exec_" + uuid.uuid4().hex[:16]
    if chat_id:
        try:
            db.add_code_execution_record(
                record_id=record_id,
                chat_id=chat_id,
                message_id=parent_message_id,
                tool_call_id=tool_call_id,
                language=lang,
                code=f"File: {entry_file}",
                stdin=stdin,
                files_json=json.dumps(files_list),
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                execution_time_ms=exec_time,
                timed_out=1 if timed_out else 0
            )
        except Exception as e:
            logger.error(f"Failed to log code execution in DB: {e}")

    # Format result for LLM
    result_str = f"**File:** {path} | **Language:** {lang} | **Exit Code:** {exit_code} | **Time:** {exec_time}ms"
    if timed_out:
        result_str += " | **TIMED OUT**"
    result_str += f"\n\n**stdout:**\n```\n{stdout}\n```\n\n**stderr:**\n```\n{stderr}\n```"
    return result_str

async def install_packages(
    packages: List[str],
    package_manager: str,
    chat_id: Optional[str] = None,
    tool_call_id: Optional[str] = None,
    parent_message_id: Optional[str] = None,
    **kwargs
) -> str:
    """Install packages in the code runner environment after user confirmation."""
    if not packages:
        return "No packages specified for installation."

    mgr = package_manager.lower()
    if mgr not in ["pip", "npm"]:
        return f"Error: Unsupported package manager: {package_manager}"

    # Build confirmation message
    packages_list = "\n".join(f"- {pkg}" for pkg in packages)
    question = (
        f"I need to install the following {package_manager} packages in the sandbox:\n\n"
        f"{packages_list}\n\n"
        f"Approve installation?"
    )
    options = ["Yes, install", "No, cancel"]
    
    response = await request_clarification(
        question=question,
        options=options,
        chat_id=chat_id,
        tool_call_id=tool_call_id,
        parent_message_id=parent_message_id,
        **kwargs
    )
    if "Yes" not in response:
        return "Installation cancelled by user."

    # Call /install API
    url = f"{config.CODE_RUNNER_URL.rstrip('/')}/install"
    headers = {"X-API-KEY": config.CODE_RUNNER_API_KEY}
    payload = {
        "packages": packages,
        "package_manager": mgr
    }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=130)
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        logger.error(f"Failed to run package installation: {e}")
        return f"Error: Failed to install packages. Code runner service is unavailable: {e}"

    success = data.get("success", False)
    stdout = data.get("stdout", "")
    stderr = data.get("stderr", "")

    if success:
        return f"Successfully installed packages: {', '.join(packages)}\n\n**Output:**\n```\n{stdout}\n```"
    else:
        return f"Failed to install packages: {', '.join(packages)}\n\n**Output:**\n```\n{stdout}\n```\n\n**Error:**\n```\n{stderr}\n```"

async def list_packages(
    package_manager: str,
    chat_id: Optional[str] = None,
    tool_call_id: Optional[str] = None,
    **kwargs
) -> str:
    """List installed packages in the sandbox environment."""
    mgr = package_manager.lower()
    if mgr not in ["pip", "npm"]:
        return f"Error: Unsupported package manager: {package_manager}"

    url = f"{config.CODE_RUNNER_URL.rstrip('/')}/packages?manager={mgr}"
    headers = {"X-API-KEY": config.CODE_RUNNER_API_KEY}

    try:
        res = requests.get(url, headers=headers, timeout=35)
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        logger.error(f"Failed to fetch packages list: {e}")
        return f"Error: Failed to fetch packages. Code runner service is unavailable: {e}"

    packages = data.get("packages", [])
    if not packages:
        return f"No packages currently installed via {package_manager}."

    result_str = f"**Installed {package_manager} packages:**\n\n| Package | Version |\n| :--- | :--- |\n"
    for pkg in packages:
        result_str += f"| {pkg.get('name')} | {pkg.get('version')} |\n"
        
    result_str += f"\nTotal: {len(packages)} packages"
    return result_str
