"""Shared helpers for the runner tests."""
import os
import time


def _gone(pid, deadline=10):
    """True once the process no longer exists (polled, so the test does not depend on a guessed delay)."""
    end = time.time() + deadline
    while time.time() < end:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        try:  # a killed process nobody has reaped yet (a zombie) is gone for our purposes
            with open(f"/proc/{pid}/stat", encoding="utf-8") as stat:
                if stat.read().rsplit(")", 1)[1].split()[0] == "Z":
                    return True
        except (OSError, IndexError):
            return True
        time.sleep(0.05)
    return False


def read_pid(pidfile, deadline=10):
    """The pid the child wrote, waiting until the file has its content (it is created before it is written)."""
    end = time.time() + deadline
    while time.time() < end:
        try:
            text = pidfile.read_text().strip()
        except FileNotFoundError:
            text = ""
        if text:
            return int(text)
        time.sleep(0.02)
    raise AssertionError("the child never wrote its pid")


def _grandchild_code(pidfile):
    # a same-group grandchild that would outlive the run; its pid is written before the parent does anything else
    return ("import subprocess, time\n"
            f"p = subprocess.Popen(['sleep', '60'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\nopen({str(pidfile)!r}, 'w').write(str(p.pid))\n")
