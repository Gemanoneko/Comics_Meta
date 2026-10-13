"""Owned-shell pause expires without changing a human pause or crossing state roots."""
import unittest
from pathlib import Path
from unittest.mock import patch
import app
import pause_control
from test_worker import scratch_directory

class ShellPauseTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app, 'DATA', self.root / 'data'))
        self.clock = self.enterContext(patch.object(pause_control.time, 'monotonic', return_value=100))
        self.enterContext(patch.object(pause_control, 'unload_model'))

    def test_shell_pause_acknowledges_gpu_and_cancel_restores_running(self):
        control = pause_control.shell_pause(True)
        self.assertTrue(control['requested'])
        self.assertFalse(control['user_requested'])
        self.assertEqual(control['phase'], 'pausing')
        self.assertTrue(pause_control.checkpoint('metadata'))
        self.assertTrue(pause_control.checkpoint('browser'))
        control = pause_control.status()
        self.assertEqual(control['phase'], 'paused')
        self.assertTrue(control['gpu_released'])
        self.assertFalse(pause_control.shell_pause(False)['requested'])
        self.assertFalse(pause_control.checkpoint('metadata'))

    def test_cancel_and_expiry_preserve_user_pause(self):
        pause_control.change(True)
        pause_control.shell_pause(True)
        self.assertTrue(pause_control.shell_pause(False)['user_requested'])
        pause_control.shell_pause(True)
        self.clock.return_value = 116
        self.assertTrue(pause_control.status()['requested'])
        self.assertTrue(pause_control.status()['user_requested'])

    def test_crashed_shell_lease_expires_and_stale_ack_cannot_fake_next_pause(self):
        pause_control.shell_pause(True)
        pause_control.checkpoint('metadata')
        pause_control.checkpoint('browser')
        self.clock.return_value = 116
        self.assertFalse(pause_control.requested())
        self.assertFalse(pause_control.status()['user_requested'])
        self.assertEqual(pause_control.shell_pause(True)['phase'], 'pausing')

    def test_renewing_lease_does_not_reset_acknowledgement_or_gpu_release(self):
        pause_control.shell_pause(True)
        pause_control.checkpoint('metadata')
        pause_control.checkpoint('browser')
        self.clock.return_value = 110
        self.assertEqual(pause_control.shell_pause(True)['phase'], 'paused')
        self.clock.return_value = 120
        self.assertTrue(pause_control.status()['gpu_released'])
