"""Container-level check of the split-uid isolation. NOT a pytest module: run it inside a built runtime container, as root,
against the real server, e.g. (unique names, never the production container):

    docker exec my-ai-verify-runtime python3 /app/tests/container_check.py

Each scenario prints one PASS/FAIL line; the exit code is 0 only if all pass. Needs the server on localhost:8100 and the
API key at /run/keys/CODE_RUNNER_API_KEY (or CODE_RUNNER_API_KEY_FILE).
"""
import json
import os
import sys
import threading
import time
import urllib.request

BASE = "http://127.0.0.1:8100"
KEY_FILE = os.environ.get("CODE_RUNNER_API_KEY_FILE", "/run/keys/CODE_RUNNER_API_KEY")


def _key() -> str:
    with open(KEY_FILE, encoding="utf-8") as handle:
        return handle.read().strip()


def call(method: str, path: str, body=None, timeout: int = 240):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(BASE + path, data=data, method=method,
                                     headers={"X-API-KEY": _key(), "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def run(language: str, code: str, timeout: int = 60) -> dict:
    return call("POST", "/execute", {"language": language, "code": code, "timeout": timeout})


def run_py(code: str, timeout: int = 60) -> dict:
    return run("python", code, timeout)


# ---- scenarios -------------------------------------------------------------------------------------------------

HELLO = {
    "python": "print('ok')",
    "c": '#include <stdio.h>\nint main(){puts("ok");return 0;}',
    "cpp": '#include <iostream>\nint main(){std::cout<<"ok\\n";}',
    "java": 'public class Main { public static void main(String[] a){ System.out.println("ok"); } }',
    "javascript": "console.log('ok')",
    "typescript": "console.log('ok' as string)",
    "go": 'package main\nimport "fmt"\nfunc main(){ fmt.Println("ok") }',
    "rust": 'fn main(){ println!("ok"); }',
    "bash": "echo ok",
    "php": "<?php echo \"ok\\n\";",
    "sql": "select 'ok' as v;",
}


def all_languages_run():
    bad = {lang: (r["exit_code"], r["stderr"][-120:]) for lang, code in HELLO.items()
           for r in [run(lang, code, 120)] if r["exit_code"] != 0 or "ok" not in r["stdout"]}
    return not bad, bad or f"{len(HELLO)} languages"


def child_is_the_runner_uid_without_capabilities():
    r = run_py("import os\nprint(os.getuid(), os.getgid(), os.getgroups())\n"
               "print([l.split()[1] for l in open('/proc/self/status') if l.startswith('CapEff')][0])")
    uid_line, caps = r["stdout"].splitlines()[:2]
    return uid_line.startswith("61001 61001 []") and int(caps, 16) == 0, r["stdout"].strip()


def leftovers_are_gone_before_the_next_run():
    leave = r'''
import ctypes, os, subprocess
libc = ctypes.CDLL(None, use_errno=True); rt = ctypes.CDLL("librt.so.1", use_errno=True)
print("shm", libc.shmget(0x5151, 4096, 0o1000 | 0o600), "sem", libc.semget(0x5252, 1, 0o1000 | 0o600), "msg", libc.msgget(0x5353, 0o1000 | 0o600))
open("/tmp/leftover", "w").write("x"); open("/var/tmp/leftover2", "w").write("x"); open("/dev/shm/posix", "w").write("x")
print("mq", rt.mq_open(b"/checkq", 0o102, 0o600, None))
p = subprocess.Popen(["sleep", "300"], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print("escapee", p.pid)
'''
    first = run_py(leave)
    look = r'''
import os
me = os.getuid()
procs = [p for p in os.listdir("/proc") if p.isdigit() and p != str(os.getpid()) and os.stat("/proc/" + p).st_uid == me]
ipc = sum(1 for t in ("shm", "sem", "msg") for l in open("/proc/sysvipc/" + t).read().splitlines()[1:] if l.split()[{"shm": 7, "sem": 4, "msg": 7}[t]] == str(me))
files = [f for d in ("/tmp", "/var/tmp", "/dev/shm", "/dev/mqueue") for f in os.listdir(d) if f in ("leftover", "leftover2", "posix", "checkq")]
print(procs, ipc, files)
'''
    second = run_py(look)
    ok = first["exit_code"] == 0 and second["stdout"].strip() == "[] 0 []"
    return ok, {"first": first["stdout"].split(), "second": second["stdout"].strip(), "err": second["stderr"][-200:]}


def writes_are_refused():
    r = run_py('import os\nfor d in ("/opt/runner/python", "/opt/runner/node", "/app", "/run/keys", "/etc", "/usr"):\n'
               '    try:\n        open(os.path.join(d, "planted"), "w").write("x"); print("WRITTEN", d)\n'
               '    except Exception as e:\n        print("refused", d, type(e).__name__)')
    return "WRITTEN" not in r["stdout"] and r["stdout"].count("refused") == 6, r["stdout"].strip()


def key_and_server_are_out_of_reach():
    r = run_py(r'''
import ctypes, os, signal
def t(label, fn):
    try: fn(); print("REACHED", label)
    except Exception as e: print("refused", label, type(e).__name__)
t("key", lambda: open("/run/keys/CODE_RUNNER_API_KEY").read())
t("keys dir", lambda: os.listdir("/run/keys"))
t("pid1 environ", lambda: open("/proc/1/environ").read())
t("kill init", lambda: os.kill(1, signal.SIGSTOP))
libc = ctypes.CDLL(None, use_errno=True)
server = [p for p in os.listdir("/proc") if p.isdigit() and "server.py" in open(f"/proc/{p}/cmdline").read()]
for pid in server:
    t(f"server {pid} environ", lambda: open(f"/proc/{pid}/environ").read())
    t(f"kill server {pid}", lambda: os.kill(int(pid), signal.SIGSTOP))
    print("ptrace", "refused" if libc.ptrace(16, int(pid), 0, 0) != 0 else "REACHED")
t("setuid 0", lambda: os.setuid(0))
print("servers seen", len(server))
''')
    seen = r["stdout"].strip().splitlines()[-1] if r["stdout"].strip() else ""
    return "REACHED" not in r["stdout"] and seen not in ("", "servers seen 0"), r["stdout"].strip().splitlines()[-4:]


def two_runs_serialise():
    out = []

    def go():
        r = run_py("import time\nprint(time.time())\ntime.sleep(1)\nprint(time.time())")
        out.append(tuple(float(x) for x in r["stdout"].split()))

    threads = [threading.Thread(target=go) for _ in range(2)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    (_, end1), (start2, _) = sorted(out)
    return start2 >= end1, [round(v, 2) for pair in sorted(out) for v in pair]


def forks_work_under_the_process_limit():
    r = run_py("import subprocess\nprint(sum(subprocess.run(['true']).returncode == 0 for _ in range(30)))")
    return r["stdout"].strip() == "30", r["stdout"].strip() or r["stderr"][-120:]


def installs_import_but_cannot_be_modified():
    pip = call("POST", "/install", {"packages": ["six"], "package_manager": "pip"})
    npm = call("POST", "/install", {"packages": ["left-pad"], "package_manager": "npm"})
    py = run_py("import six\nprint('six', six.__version__)")
    js = run("javascript", "console.log('left-pad', typeof require('left-pad'))")
    modify = run_py("import os, six\ntry:\n    open(os.path.dirname(six.__file__) + '/x', 'w'); print('MODIFIED')\nexcept Exception as e:\n    print('refused')")
    listed = call("GET", "/packages?manager=pip")
    ok = (pip["success"] and npm["success"] and "six" in py["stdout"] and "left-pad" in js["stdout"]
          and "refused" in modify["stdout"] and any(p["name"].lower() == "six" for p in listed["packages"]))
    return ok, {"pip": pip["success"], "npm": npm["success"], "py": py["stdout"].strip(), "js": js["stdout"].strip(), "modify": modify["stdout"].strip()}


def non_writable_trees_do_not_wedge_cleanup():
    make = "import os\nos.makedirs('/tmp/trap/a/b')\nopen('/tmp/trap/a/b/f','w').write('x')\nos.chmod('/tmp/trap/a/b', 0)\nos.chmod('/tmp/trap/a', 0o555)\nprint('made')"
    first = run_py(make)
    second = run_py("import os\nprint(os.path.exists('/tmp/trap'))")
    return first["exit_code"] == 0 and first["error"] is None and second["stdout"].strip() == "False" and second["error"] is None, \
        {"first": first["error"], "second": second["stdout"].strip(), "err": second["error"]}


SCENARIOS = [
    ("all 11 languages run", all_languages_run),
    ("user code runs as uid 61001 with no capabilities", child_is_the_runner_uid_without_capabilities),
    ("leftovers (setsid process, SysV IPC, scratch files, POSIX queue) are gone before the next run", leftovers_are_gone_before_the_next_run),
    ("writes to /opt/runner, /app, /run/keys, /etc and /usr are refused", writes_are_refused),
    ("the API key, the server's environment, signals and ptrace are out of reach", key_and_server_are_out_of_reach),
    ("a tree the user made non-writable does not wedge cleanup", non_writable_trees_do_not_wedge_cleanup),
    ("two simultaneous runs serialise", two_runs_serialise),
    ("forks work under the process limit", forks_work_under_the_process_limit),
    ("pip and npm installs import for user code but cannot be modified by it", installs_import_but_cannot_be_modified),
]


def main() -> int:
    failed = 0
    for name, scenario in SCENARIOS:
        started = time.time()
        try:
            ok, detail = scenario()
        except Exception as exc:  # a scenario that cannot even run is a failure, with the reason
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        failed += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {name}  ({time.time() - started:.1f}s)  {detail}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
