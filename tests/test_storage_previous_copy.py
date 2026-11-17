"""Fix B (2026-11-17, Sergei-approved; Docs/ComicsMetaOrganizer_ZeroFillDiagnosis_2026-11-17.md §4 B).

progress.json, folders.json and browser-search.json keep their previous good record as <name>.bak. When a file
cannot be read (all zeros, cut short, not the expected record), its reader puts the copy back, keeps the unreadable
file as <name>.unreadable and logs one line, and the app carries on. This replaces 0.6.2's "preserve and wait" for a
file that has a readable copy; with no readable copy, 0.6.2's behaviour stands (tests/test_startup_recovery.py)."""
import contextlib
import io
import json
import shutil
import tempfile
import os
import unittest
from pathlib import Path
from unittest.mock import patch
import app
import batch
import browser_search
import progress_snapshot
import scheduler
import storage
from test_worker import scratch_directory


def damage(path, shape):
    """What the 2026-11-13 stop left: full size and all zeros; or a file cut short."""
    size = path.stat().st_size
    path.write_bytes(b'\0' * size if shape == 'zeros' else path.read_bytes()[:size // 2])
    return path.read_bytes()


class PreviousCopyTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp(dir=os.environ.get('COMICS_META_TEST_SCRATCH')))
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.path = self.folder / 'progress.json'

    def names(self):
        return sorted(p.name for p in self.folder.iterdir())

    def test_each_save_keeps_the_record_it_replaces(self):
        storage.save(self.path, {'phase': 'one'}, keep_previous=True)
        self.assertEqual(self.names(), ['progress.json'])  # Nothing to keep yet.
        storage.save(self.path, {'phase': 'two'}, keep_previous=True)
        storage.save(self.path, {'phase': 'three'}, keep_previous=True)
        self.assertEqual(json.loads(storage.backup(self.path).read_text(encoding='utf-8')), {'phase': 'two'})
        self.assertEqual(json.loads(self.path.read_text(encoding='utf-8')), {'phase': 'three'})
        storage.save(self.folder / 'metron-status.json', {'a': 1})
        storage.save(self.folder / 'metron-status.json', {'a': 2})
        self.assertNotIn('metron-status.json.bak', self.names())  # Only the state files that ask for it.

    def test_an_unreadable_file_is_replaced_by_its_previous_copy(self):
        for shape in ('zeros', 'cut short'):
            with self.subTest(shape=shape):
                storage.save(self.path, {'phase': 'older', 'completed': [1]}, keep_previous=True)
                storage.save(self.path, {'phase': 'newer', 'completed': [1, 2]}, keep_previous=True)
                copy = storage.backup(self.path).read_bytes()
                damaged = damage(self.path, shape)
                log = io.StringIO()
                with contextlib.redirect_stderr(log):
                    self.assertEqual(storage.read_json(self.path), {'phase': 'older', 'completed': [1]})
                    self.assertEqual(storage.read_json(self.path), {'phase': 'older', 'completed': [1]})
                self.assertEqual(self.path.read_bytes(), copy)
                self.assertEqual((self.folder / 'progress.json.unreadable').read_bytes(), damaged)
                self.assertEqual(storage.backup(self.path).read_bytes(), copy)
                self.assertEqual(log.getvalue().count('progress.json could not be read; its previous copy was put back'), 1)
                self.assertEqual(self.names(), ['progress.json', 'progress.json.bak', 'progress.json.unreadable'])

    def test_a_record_of_the_wrong_shape_counts_as_unreadable(self):
        storage.save(self.path, {'completed': []}, keep_previous=True, valid=batch.progress_record)
        storage.save(self.path, {'completed': [1]}, keep_previous=True, valid=batch.progress_record)
        self.path.write_text('{"completed": "lost"}', encoding='utf-8')
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(storage.read_json(self.path, valid=batch.progress_record), {'completed': []})

    def test_an_unreadable_file_never_replaces_the_good_copy(self):
        storage.save(self.path, {'phase': 'one'}, keep_previous=True)
        storage.save(self.path, {'phase': 'two'}, keep_previous=True)
        copy = storage.backup(self.path).read_bytes()
        damage(self.path, 'zeros')
        storage.save(self.path, {'phase': 'three'}, keep_previous=True)  # A writer that did not read first.
        self.assertEqual(storage.backup(self.path).read_bytes(), copy)
        self.assertEqual(json.loads(self.path.read_text(encoding='utf-8')), {'phase': 'three'})

    def test_a_missing_file_is_not_restored(self):
        storage.save(self.path, {'phase': 'one'}, keep_previous=True)
        storage.save(self.path, {'phase': 'two'}, keep_previous=True)
        self.path.unlink()  # Removed on purpose (as on 2026-11-14): start afresh, not from the copy.
        with self.assertRaises(FileNotFoundError):
            storage.read_json(self.path)
        self.assertEqual(self.names(), ['progress.json.bak'])

    def test_with_no_readable_copy_nothing_is_guessed_and_nothing_is_written(self):
        for copy in (None, b'\0' * 64):
            with self.subTest(copy=copy):
                damaged = b'\0' * 1644
                self.path.write_bytes(damaged)
                if copy is not None:
                    storage.backup(self.path).write_bytes(copy)
                with self.assertRaises(ValueError):
                    storage.read_json(self.path)
                self.assertEqual(self.path.read_bytes(), damaged)
                self.assertNotIn('progress.json.unreadable', self.names())


class StateFilesRecoverTests(unittest.TestCase):
    """The three files the 2026-11-13 stop zero-filled, through the app's own readers."""
    def setUp(self):
        folder = Path(self.enterContext(scratch_directory()))
        self.data = folder
        self.enterContext(patch.object(app, 'DATA', folder))
        self.enterContext(patch.object(scheduler, 'STATE', folder / 'folders.json'))
        self.enterContext(contextlib.redirect_stderr(io.StringIO()))

    def saved_twice(self):
        batch.progress(phase='Folder complete', current_folder='Older', completed=[{'batch': '1', 'folder': 'A'}])
        batch.progress(phase='Automatic metadata lookup', current_folder='Fairest')
        folders = {'folders': {'Y:\\Comix\\%d' % i: {'next_scan': i, 'state': 'pass_complete'} for i in range(500)}}
        scheduler.save(folders)
        scheduler.finish('Y:\\Comix\\7')
        browser_search.legacy_status(state='searching')
        browser_search.legacy_status(state='paused', detail='Paused; cover queue retained.')

    def test_the_2026_11_13_damage_no_longer_stops_the_app(self):
        for shape in ('zeros', 'cut short'):
            with self.subTest(shape=shape):
                self.saved_twice()
                for name in ('progress.json', 'folders.json', 'browser-search.json'):
                    damage(self.data / name, shape)
                files = progress_snapshot.Files()
                try:
                    result = progress_snapshot.collect(files)
                finally:
                    files.close()
                self.assertNotIn('progress_unavailable', result)
                self.assertEqual(result['phase'], 'Folder complete')  # One progress step lost, not the record.
                self.assertNotIn('folders_unavailable', result)
                self.assertEqual(result['folders']['total'], 500)  # The schedule, not a rebuild from empty.
                self.assertNotIn('status_unavailable', result['browser_search'])
                self.assertTrue(batch.progress_available())
                self.assertEqual(browser_search.legacy_status()['state'], 'searching')
                for name in ('progress.json', 'folders.json', 'browser-search.json'):
                    self.assertTrue((self.data / (name + '.unreadable')).is_file(), name)

    def test_each_reader_puts_its_own_file_back(self):
        self.saved_twice()
        damage(self.data / 'progress.json', 'zeros')
        self.assertTrue(batch.progress_available())  # The metadata worker runs queued batches again.
        batch.progress(detail='carries on')
        self.assertEqual(json.loads((self.data / 'progress.json').read_text(encoding='utf-8'))['detail'], 'carries on')
        damage(self.data / 'folders.json', 'cut short')
        self.assertEqual(len(scheduler.load()['folders']), 500)
        scheduler.finish('Y:\\Comix\\8')  # Folder selection and finishing work again.
        self.assertEqual(scheduler.load()['folders']['Y:\\Comix\\8']['state'], 'pass_complete')
        damage(self.data / 'browser-search.json', 'zeros')
        browser_search.legacy_status(state='waiting')  # The cover worker no longer waits for a person.
        self.assertEqual(browser_search.legacy_status()['state'], 'waiting')


if __name__ == '__main__':
    unittest.main()
