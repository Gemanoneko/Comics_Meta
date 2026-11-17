"""storage.save is durable (fix A, 2026-11-17, Docs/ComicsMetaOrganizer_ZeroFillDiagnosis_2026-11-17.md).

After the unclean stop of 2026-11-13, three state files came back full size and all zeros: the rename had reached the
disk, the bytes had not. These tests model that stop. A file's name and size survive it; bytes that were never
flushed to the disk (fsync) read back as zeros, or the file is cut short. The saved file must still read as the new
record, and the rename itself must be written through."""
import ctypes
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import storage


class Disk:
    """Which files' bytes reached the disk (fsync), and every rename in order."""
    def __init__(self):
        self.durable, self.events, self.flags = set(), [], []
        self.real_fsync = os.fsync

    def fsync(self, fd):
        self.durable.add(os.fstat(fd).st_ino)
        self.events.append(('fsync', os.fstat(fd).st_ino))
        return self.real_fsync(fd)

    def move_file(self, source, destination, flags):
        self.flags.append(flags)
        self.events.append(('rename', os.stat(source).st_ino, Path(destination).name))
        os.replace(source, destination)
        return True

    def power_cut(self, path, shape='zeros'):
        """What the unclean stop leaves of path."""
        size = path.stat().st_size
        if path.stat().st_ino in self.durable:
            return
        path.write_bytes(b'\0' * size if shape == 'zeros' else path.read_bytes()[:size // 2])


class DurableSaveTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp(dir=os.environ.get('COMICS_META_TEST_SCRATCH')))
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.disk = Disk()
        for patcher in (patch.object(storage.os, 'fsync', self.disk.fsync),
                        patch.object(storage, '_move_file', self.disk.move_file)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_a_stop_right_after_the_save_leaves_the_new_record(self):
        for shape in ('zeros', 'cut short'):
            with self.subTest(shape=shape):
                path = self.folder / ('progress-' + shape.replace(' ', '-') + '.json')
                storage.save(path, {'phase': 'old', 'completed': [1, 2, 3]})
                record = {'phase': 'Automatic metadata lookup', 'completed': list(range(400)), 'detail': 'é'}
                storage.save(path, record)
                self.disk.power_cut(path, shape)
                self.assertEqual(json.loads(path.read_bytes().decode('utf-8')), record)

    def test_bytes_reach_the_disk_before_the_rename(self):
        path = self.folder / 'folders.json'
        storage.save(path, {'folders': {'a': {'next_scan': 1}}})
        (fsync, written), (rename, renamed, name) = self.disk.events
        self.assertEqual((fsync, rename, name), ('fsync', 'rename', 'folders.json'))
        self.assertEqual(written, renamed)
        self.assertEqual(path.stat().st_ino, renamed)

    def test_the_rename_is_written_through(self):
        storage.save(self.folder / 'browser-search.json', {'state': 'paused'})
        self.assertEqual(self.disk.flags, [storage.MOVEFILE_REPLACE_EXISTING | storage.MOVEFILE_WRITE_THROUGH])
        self.assertEqual((storage.MOVEFILE_REPLACE_EXISTING, storage.MOVEFILE_WRITE_THROUGH), (0x1, 0x8))

    def test_a_reader_holding_the_file_is_waited_for_and_nothing_is_left_behind(self):
        path = self.folder / 'browser-heartbeat'
        refusals = []

        def busy(source, destination, flags):
            if len(refusals) < 2:
                refusals.append(flags)
                ctypes.set_last_error(32)  # ERROR_SHARING_VIOLATION: a reader has the file open.
                return False
            return self.disk.move_file(source, destination, flags)
        with patch.object(storage, '_move_file', busy), patch.object(storage.time, 'sleep') as sleep:
            storage.save(path, {'pid': 1, 'timestamp': 2})
        self.assertEqual(len(refusals), 2)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(json.loads(path.read_text(encoding='utf-8')), {'pid': 1, 'timestamp': 2})
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), ['browser-heartbeat'])

    def test_a_lasting_refusal_is_raised_and_the_old_file_kept(self):
        path = self.folder / 'metron-status.json'
        storage.save(path, {'status': 'available'})

        def refused(source, destination, flags):
            ctypes.set_last_error(5)  # ERROR_ACCESS_DENIED
            return False
        with patch.object(storage, '_move_file', refused), patch.object(storage.time, 'sleep'), \
                self.assertRaises(PermissionError):
            storage.save(path, {'status': 'requesting'})
        self.assertEqual(json.loads(path.read_text(encoding='utf-8')), {'status': 'available'})
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), ['metron-status.json'])

    def test_the_saved_bytes_are_unchanged(self):
        # Before the fix, Path.write_text wrote the same text with the platform's line ends.
        path = self.folder / 'comicvine-status.json'
        record = {'status': 'available', 'detail': 'Ünïcode', 'nested': {'a': [1, 2]}}
        storage.save(path, record)
        expected = json.dumps(record, ensure_ascii=False, indent=2).replace('\n', os.linesep).encode('utf-8')
        self.assertEqual(path.read_bytes(), expected)


if __name__ == '__main__':
    unittest.main()
