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
        time.sleep(0.05)
    return False


def _grandchild_code(pidfile):
    # a same-group grandchild that would outlive the run; its pid is written before the parent does anything else
    return ("import subprocess, time\n"
            f"p = subprocess.Popen(['sleep', '60'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\nopen({str(pidfile)!r}, 'w').write(str(p.pid))\n")
