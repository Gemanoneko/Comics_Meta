"""Restart an exited worker; its queue lock prevents concurrent writers."""
import os
import sqlite3
import subprocess
import sys
import threading
import pause_control


def _error_stream():
    """Where a worker's stderr goes: this process's own (engine.log under the app), else nowhere.

    Before 0.6.7 workers were launched with no standard handles at all: on Windows a child given none gets none
    (close_fds), so its sys.stderr was None and every line it printed there was dropped without an error: the
    state-file restore line (storage.read_json), its own error lines and the traceback of a crash (TrayQA v0.6.4
    finding 1, v0.6.6 finding 3). Standard output stays out of the log (batch.apply prints a line per comic)."""
    try:
        sys.stderr.fileno()
        return sys.stderr
    except (AttributeError, OSError, ValueError):  # None, closed or not a file (a test's StringIO).
        return subprocess.DEVNULL


def supervise(base, stop, launch=None, script='worker.py', baseline=None):
    launch = launch or subprocess.Popen
    baseline = baseline or pause_control.stop_generation
    child = None
    reported = None  # Last launch failure written to the log; a repeat is not rewritten.
    while not stop.is_set():
        if child is None or child.poll() is not None:
            try:
                # Read the Quit generation before re-checking stop: a Quit that lands
                # during launch is then newer than the worker's baseline and still seen.
                env = dict(os.environ, **{pause_control.STOP_BASELINE_ENV: str(baseline())})
                if stop.is_set():
                    break
                # -B: no __pycache__ in the installed runtime; the next update verifies its closure.
                child = launch([sys.executable, '-B', str(base / script)], cwd=base, env=env,
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=_error_stream(),
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                reported = None
            except (OSError, sqlite3.Error, ValueError) as exc:
                child = None
                # A refused or failed launch was silent: the dashboard only ever said a
                # restart was being attempted (installed 0.2.1 QA, M1). Log it once per cause.
                failure = (exc.__class__.__name__, str(exc))
                if failure != reported:
                    reported = failure
                    try:
                        print('Could not start', script + '; retrying every 30 s:', *failure, file=sys.stderr, flush=True)
                    except (OSError, ValueError):
                        pass  # A log that cannot be written must not end the retries.
        # Back off even when another worker owns the lock or startup fails.
        stop.wait(30)
    # Do not terminate a worker that might be rewriting an archive.


def start(base):
    stop = threading.Event()
    threading.Thread(target=supervise, args=(base, stop), daemon=True).start()
    threading.Thread(target=supervise, args=(base, stop, None, 'browser_worker.py'), daemon=True).start()
    return stop
