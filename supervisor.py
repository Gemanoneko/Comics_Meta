"""Restart an exited worker; its queue lock prevents concurrent writers."""
import os
import subprocess
import sys
import threading


def supervise(base, stop, launch=None, script='worker.py'):
    launch = launch or subprocess.Popen
    child = None
    while not stop.is_set():
        if child is None or child.poll() is not None:
            try:
                child = launch([sys.executable, str(base / script)], cwd=base,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            except OSError:
                child = None
        # Back off even when another worker owns the lock or startup fails.
        stop.wait(30)
    # Do not terminate a worker that might be rewriting an archive.


def start(base):
    stop = threading.Event()
    threading.Thread(target=supervise, args=(base, stop), daemon=True).start()
    threading.Thread(target=supervise, args=(base, stop, None, 'browser_worker.py'), daemon=True).start()
    return stop
