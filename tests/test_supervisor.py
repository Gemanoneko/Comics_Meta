import contextlib
import io
import unittest
from pathlib import Path
from unittest.mock import Mock
import supervisor


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
