import contextlib
import io
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock
import supervisor
from test_worker import scratch_directory

CODE = Path(supervisor.__file__).resolve().parent
# Stands in for app.py: its stderr is the log file (the broker gives app.py engine.log), and the real supervisor
# launches the worker once with the real Popen.
APP = r'''
import subprocess, sys, threading
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import supervisor
base, stop, started = Path(sys.argv[2]), threading.Event(), []
def launch(*args, **kwargs):
    try:
        started.append(subprocess.Popen(*args, **kwargs)); return started[-1]
    finally:
        stop.set()  # One supervisor pass.
supervisor.supervise(base, stop, launch, 'worker.py', baseline=lambda: 0)
print('worker exit', started[0].wait(60), file=sys.stderr, flush=True)
'''
# Stands in for the metadata worker: it reads a damaged progress.json and puts its previous copy back, as
# batch.progress does through storage.read_json, then prints the record to stdout.
WORKER = r'''
import os, sys
from pathlib import Path
sys.path.insert(0, os.environ['SUPERVISOR_TEST_CODE'])
import storage
path = Path(__file__).with_name('progress.json')
storage.save(path, {'step': 'first'}, keep_previous=True)
storage.save(path, {'step': 'second'}, keep_previous=True)
path.write_bytes(bytes(64))
print('record', storage.read_json(path), flush=True)
'''


class StopAfter:
    def __init__(self, count):
        self.count = count
        self.waits = []

    def is_set(self):
        return self.count == 0

    def wait(self, seconds):
        self.waits.append(seconds)
        self.count -= 1


class SupervisorTests(unittest.TestCase):
    def test_running_child_is_never_restarted_or_terminated(self):
        child = Mock()
        child.poll.return_value = None
        launch = Mock(return_value=child)
        stop = StopAfter(3)
        supervisor.supervise(Path('project'), stop, launch, baseline=lambda: 0)
        self.assertEqual(launch.call_count, 1)
        child.terminate.assert_not_called()
        self.assertEqual(stop.waits, [30, 30, 30])

    def test_exited_worker_is_restarted_with_backoff(self):
        child = Mock()
        child.poll.return_value = 1
        launch = Mock(return_value=child)
        supervisor.supervise(Path('project'), StopAfter(3), launch, baseline=lambda: 0)
        self.assertEqual(launch.call_count, 3)

    def test_launch_failure_retries_without_spinning(self):
        launch = Mock(side_effect=[OSError('unavailable'), Mock()])
        stop = StopAfter(2)
        supervisor.supervise(Path('project'), stop, launch, baseline=lambda: 0)
        self.assertEqual(launch.call_count, 2)
        self.assertEqual(stop.waits, [30, 30])

    def test_launch_failure_is_logged_once_per_cause(self):
        # A refused launch was silent (installed 0.2.1 QA, M1); now it reaches the engine log.
        refused = PermissionError('Private QA native child refused')
        log = io.StringIO()
        with contextlib.redirect_stderr(log):
            supervisor.supervise(Path('project'), StopAfter(4), Mock(side_effect=[
                refused, refused, Mock(**{'poll.return_value': 1}), OSError('unavailable')]), baseline=lambda: 0)
        lines = log.getvalue().splitlines()
        self.assertEqual(lines, [
            'Could not start worker.py; retrying every 30 s: PermissionError Private QA native child refused',
            'Could not start worker.py; retrying every 30 s: OSError unavailable'])

    def test_crashed_browser_worker_is_restarted_on_the_next_check(self):
        child = Mock()
        child.poll.side_effect = [None, 1]  # Running at the first check, crashed by the second.
        launch = Mock(return_value=child)
        stop = StopAfter(3)
        supervisor.supervise(Path('project'), stop, launch, 'browser_worker.py', baseline=lambda: 0)
        self.assertEqual(launch.call_count, 2)
        self.assertEqual(launch.call_args.args[0][-1], str(Path('project') / 'browser_worker.py'))
        # -B: a worker writes no __pycache__ into the installed runtime (0.2.2->0.2.3 update failure).
        self.assertEqual(launch.call_args.args[0][1:], ['-B', str(Path('project') / 'browser_worker.py')])
        self.assertEqual(stop.waits, [30, 30, 30])


class WorkerLogTests(unittest.TestCase):
    """TrayQA v0.6.4 finding 1 / v0.6.6 finding 3: a worker's restore line never reached engine.log. Workers were
    launched with no standard handles, so on Windows their sys.stderr was None and the line was dropped silently."""

    def test_a_workers_restore_line_reaches_the_app_log_and_its_stdout_does_not(self):
        base = Path(self.enterContext(scratch_directory()))
        (base / 'worker.py').write_text(WORKER, encoding='utf-8')
        log = base / 'engine.log'
        env = dict(os.environ, SUPERVISOR_TEST_CODE=str(CODE), PYTHONDONTWRITEBYTECODE='1')
        with open(log, 'ab') as handle:
            app = subprocess.run([sys.executable, '-I', '-B', '-c', APP, str(CODE), str(base)], cwd=base, env=env,
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=handle, timeout=120)
        text = log.read_text(encoding='utf-8', errors='replace')
        self.assertEqual(app.returncode, 0, text)
        self.assertIn('worker exit 0', text)  # The worker ran and its parent's own line is in the log.
        self.assertEqual(text.count('Saved progress.json could not be read; its previous copy was put back'), 1, text)
        self.assertNotIn('record', text)  # Standard output stays out (batch.apply prints a line per comic).
        self.assertEqual((base / 'progress.json.unreadable').read_bytes(), bytes(64))  # The restore did happen.
