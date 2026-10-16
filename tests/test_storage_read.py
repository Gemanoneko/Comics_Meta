"""storage.read_text: a status/heartbeat/lease read survives a brief Windows replace refusal."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import storage


class ReadTextTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.mkdtemp(dir=os.environ.get('COMICS_META_TEST_SCRATCH'))
        self.addCleanup(lambda: (self.path.unlink(missing_ok=True), os.rmdir(folder)))
        self.path = Path(folder) / 'browser-heartbeat'
        storage.save(self.path, {'pid': 1, 'timestamp': 2})

    def test_brief_refusal_is_retried(self):
        # The installed 0.2.1 browser worker died on this refusal (QA M3).
        real = Path.read_text
        calls = []
        def flaky(path, *args, **kwargs):
            calls.append(path)
            if len(calls) < 3:
                raise PermissionError(13, 'Permission denied')
            return real(path, *args, **kwargs)
        with patch.object(Path, 'read_text', flaky), patch.object(storage.time, 'sleep') as sleep:
            self.assertIn('"timestamp": 2', storage.read_text(self.path))
        self.assertEqual(len(calls), 3)
        self.assertEqual(sleep.call_count, 2)

    def test_lasting_refusal_and_other_errors_are_raised(self):
        with patch.object(Path, 'read_text', side_effect=PermissionError(13, 'Permission denied')) as read, \
                patch.object(storage.time, 'sleep'):
            with self.assertRaises(PermissionError):
                storage.read_text(self.path)
        self.assertEqual(read.call_count, 20)
        with patch.object(storage.time, 'sleep') as sleep, self.assertRaises(FileNotFoundError):
            storage.read_text(self.path.with_name('missing'))
        sleep.assert_not_called()
