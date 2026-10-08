import json
import unittest
from pathlib import Path
from unittest.mock import patch
import server_host
from test_worker import scratch_directory


class ServerHostTests(unittest.TestCase):
    def test_records_failure_exit_for_windows_restart_and_preserves_bounded_log_tail(self):
        with scratch_directory() as folder:
            base = Path(folder)
            data = base / 'data'
            data.mkdir()
            (data / 'server-error.log').write_bytes(b'x' * 400000)
            with patch.object(server_host, 'BASE', base), patch.object(server_host.subprocess, 'Popen') as launch:
                launch.return_value.wait.return_value = 7
                self.assertEqual(server_host.main(), 7)
            self.assertEqual(json.loads((data / 'server-exit.json').read_text())['exit_code'], 7)
            self.assertEqual((data / 'server-error.previous.log').stat().st_size, 262144)
            self.assertEqual(launch.call_args.kwargs['cwd'], base)

    def test_normal_shutdown_does_not_report_failure(self):
        with scratch_directory() as folder:
            with patch.object(server_host, 'BASE', Path(folder)), patch.object(server_host.subprocess, 'Popen') as launch:
                launch.return_value.wait.return_value = 0
                self.assertEqual(server_host.main(), 0)
