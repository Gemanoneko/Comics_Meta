"""Restart an exited worker; its queue lock prevents concurrent writers."""
import os
import sqlite3
import subprocess
import sys
import threading
import pause_control


def supervise(base, stop, launch=None, script='worker.py', baseline=None):
    launch = launch or subprocess.Popen
    baseline = baseline or pause_control.stop_generation
    child = None
    while not stop.is_set():
        if child is None or child.poll() is not None:
            try:
                # Read the Quit generation before re-checking stop: a Quit that lands
                # during launch is then newer than the worker's baseline and still seen.
                env = dict(os.environ, **{pause_control.STOP_BASELINE_ENV: str(baseline())})
                if stop.is_set():
                    break
                child = launch([sys.executable, str(base / script)], cwd=base, env=env,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            except (OSError, sqlite3.Error, ValueError):
                child = None
        # Back off even when another worker owns the lock or startup fails.
        stop.wait(30)
    # Do not terminate a worker that might be rewriting an archive.


def start(base):
    stop = threading.Event()
    threading.Thread(target=supervise, args=(base, stop), daemon=True).start()
    threading.Thread(target=supervise, args=(base, stop, None, 'browser_worker.py'), daemon=True).start()
    return stop
