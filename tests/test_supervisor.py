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
        supervisor.supervise(Path('project'), stop, launch)
        self.assertEqual(launch.call_count, 1)
        child.terminate.assert_not_called()
        self.assertEqual(stop.waits, [30, 30, 30])

    def test_exited_worker_is_restarted_with_backoff(self):
        child = Mock()
        child.poll.return_value = 1
        launch = Mock(return_value=child)
        supervisor.supervise(Path('project'), StopAfter(3), launch)
        self.assertEqual(launch.call_count, 3)

    def test_launch_failure_retries_without_spinning(self):
        launch = Mock(side_effect=[OSError('unavailable'), Mock()])
        stop = StopAfter(2)
        supervisor.supervise(Path('project'), stop, launch)
        self.assertEqual(launch.call_count, 2)
        self.assertEqual(stop.waits, [30, 30])
