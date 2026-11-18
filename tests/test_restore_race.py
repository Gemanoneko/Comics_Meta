"""Code review v0.6.4 N1 (fixed in 0.6.6): putting a state file's previous copy back never rolls back a newer save.

storage.read_json re-checked a damaged file, wrote the .unreadable evidence (an fsync'd file of up to ~1.7 MB) and
only then put the .bak copy back. A worker that restored the file itself and saved its next step inside that window
lost the step: the dashboard's poll (progress_snapshot) wrote the older copy over it. The restore and every
keep_previous save of one file now run one at a time, across threads and processes (storage.exclusive).

Each race test puts the other writer's save inside that window, as Senua's probe did. Before the fix the newer record
was replaced by the older copy; now the save waits for the restore and lands after it."""
import contextlib
import io
import json
import os
import subprocess
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
import app
import batch
import progress_snapshot
import scheduler
import storage
from test_storage_previous_copy import damage
from test_worker import scratch_directory

CODE = Path(storage.__file__).resolve().parent
# Another process saving one record: it imports storage, says so, waits for "go", saves, and says so.
SAVER = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
import storage
print("ready", flush=True)
sys.stdin.readline()
storage.save(sys.argv[2], json.loads(sys.argv[3]), keep_previous=True)
print("saved", flush=True)
'''
# Another process holding one file's save lock until its stdin closes (or it is killed).
HOLDER = r'''
import sys
sys.path.insert(0, sys.argv[1])
import storage
with storage.exclusive(sys.argv[2]):
    print("held", flush=True)
    sys.stdin.readline()
'''


class Window:
    """Stands in for storage._write. When the restore writes its .unreadable evidence (between its re-check and putting
    the copy back), runs `writer` elsewhere and gives it `wait` seconds to finish before the restore goes on."""
    def __init__(self, start, finished, wait=1.0):
        self.start, self.finished, self.wait = start, finished, wait
        self.original, self.fired, self.saved_in_window = storage._write, False, None

    def __call__(self, path, data):
        self.original(path, data)
        if (not self.fired and Path(path).name.endswith(storage.UNREADABLE)
                and threading.current_thread() is threading.main_thread()):
            self.fired = True
            self.start()
            self.saved_in_window = self.finished(self.wait)


class Racer:
    """A writer on another thread, as the worker process is to the dashboard."""
    def __init__(self, writer):
        self.writer, self.done, self.errors = writer, threading.Event(), []
        self.thread = threading.Thread(target=self.run, daemon=True)

    def run(self):
        try:
            self.writer()
        except BaseException as exc:  # Reported by the test, not lost in the thread.
            self.errors.append(exc)
        finally:
            self.done.set()

    def join(self):
        self.thread.join(30)
        if self.errors:
            raise self.errors[0]


def record(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


class RestoreRaceTests(unittest.TestCase):
    def setUp(self):
        self.data = Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app, 'DATA', self.data))
        self.enterContext(patch.object(scheduler, 'STATE', self.data / 'folders.json'))
        self.enterContext(contextlib.redirect_stderr(io.StringIO()))

    def dashboard_read(self, name, default, valid):
        files = progress_snapshot.Files()
        try:
            return files.read(self.data / name, default, valid)
        finally:
            files.close()

    def race(self, name, reader, writer):
        racer = Racer(writer)
        window = Window(racer.thread.start, racer.done.wait)
        with patch.object(storage, '_write', side_effect=window):
            seen = reader()
        racer.join()
        self.assertTrue(window.fired, 'the restore never reached its window')
        return seen, window

    def test_the_dashboard_restore_never_rolls_back_the_workers_next_progress_step(self):
        batch.progress(phase='Folder complete', completed=[{'batch': '1'}])
        batch.progress(phase='Automatic metadata lookup', current_folder='Fairest')
        zeros = damage(self.data / 'progress.json', 'zeros')
        seen, window = self.race(
            'progress.json',
            lambda: self.dashboard_read('progress.json', {}, batch.progress_record),
            lambda: batch.progress(phase='Advancing to next folder', detail='newer step'))
        self.assertEqual(seen['phase'], 'Folder complete')  # The dashboard still shows the saved copy at once.
        saved = record(self.data / 'progress.json')
        self.assertEqual((saved['phase'], saved.get('detail')), ('Advancing to next folder', 'newer step'))  # Kept, ...
        self.assertFalse(window.saved_in_window)  # ... because the worker's save waited for the restore.
        self.assertEqual(saved['completed'], [{'batch': '1'}])
        self.assertEqual(record(storage.backup(self.data / 'progress.json'))['phase'], 'Folder complete')
        self.assertEqual((self.data / 'progress.json.unreadable').read_bytes(), zeros)

    def test_the_dashboard_restore_never_rolls_back_a_finished_folder(self):
        scheduler.save({'folders': {'Y:\\Comix\\A': {'next_scan': 1, 'state': 'scheduled'}}})
        scheduler.save({'folders': {'Y:\\Comix\\A': {'next_scan': 2, 'state': 'scheduled'}}})
        damage(self.data / 'folders.json', 'cut short')
        seen, window = self.race(
            'folders.json',
            lambda: self.dashboard_read('folders.json', None, scheduler.schedule_record),
            lambda: scheduler.finish('Y:\\Comix\\A'))
        self.assertEqual(seen['folders']['Y:\\Comix\\A']['next_scan'], 1)
        self.assertEqual(record(self.data / 'folders.json')['folders']['Y:\\Comix\\A']['state'], 'pass_complete')
        self.assertFalse(window.saved_in_window)

    def test_a_save_from_another_process_waits_for_the_restore(self):
        path = self.data / 'progress.json'
        storage.save(path, {'phase': 'older', 'completed': []}, keep_previous=True)
        storage.save(path, {'phase': 'lost', 'completed': []}, keep_previous=True)
        damage(path, 'zeros')
        newer = {'phase': 'from another process', 'completed': []}
        saver = subprocess.Popen([sys.executable, '-S', '-B', '-c', SAVER, str(CODE), str(path), json.dumps(newer)],
                                 cwd=CODE, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(saver.kill)
        self.assertEqual(saver.stdout.readline().strip(), 'ready', saver.stderr.read() if saver.poll() is not None else '')

        def go():
            saver.stdin.write('go\n')
            saver.stdin.flush()

        def finished(wait):
            try:
                saver.wait(wait)
                return True
            except subprocess.TimeoutExpired:
                return False

        window = Window(go, finished, wait=2.0)
        with patch.object(storage, '_write', side_effect=window):
            seen = storage.read_json(path, valid=batch.progress_record)
        out, err = saver.communicate(timeout=60)
        self.assertEqual((saver.returncode, out.strip()), (0, 'saved'), err)
        self.assertEqual(seen['phase'], 'older')
        self.assertEqual(record(path), newer)
        self.assertFalse(window.saved_in_window)
        self.assertEqual(record(storage.backup(path))['phase'], 'older')

    def test_positive_control_with_no_other_writer_the_copy_is_put_back_once(self):
        batch.progress(phase='Folder complete')
        batch.progress(phase='Automatic metadata lookup')
        damage(self.data / 'progress.json', 'zeros')
        log = io.StringIO()
        with contextlib.redirect_stderr(log):
            self.assertEqual(self.dashboard_read('progress.json', {}, batch.progress_record)['phase'], 'Folder complete')
            self.assertEqual(self.dashboard_read('progress.json', {}, batch.progress_record)['phase'], 'Folder complete')
        self.assertEqual(record(self.data / 'progress.json')['phase'], 'Folder complete')
        self.assertEqual(log.getvalue().count('its previous copy was put back'), 1)
        self.assertEqual(sorted(p.name for p in self.data.iterdir()),
                         ['progress.json', 'progress.json.bak', 'progress.json.unreadable'])  # The lock leaves no file.


class SaveLockTests(unittest.TestCase):
    def setUp(self):
        self.data = Path(self.enterContext(scratch_directory()))
        self.path = self.data / 'progress.json'

    def hold(self, path):
        holder = subprocess.Popen([sys.executable, '-S', '-B', '-c', HOLDER, str(CODE), str(path)], cwd=CODE,
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: (holder.kill(), holder.wait(30), holder.stdin.close(), holder.stdout.close(),
                                 holder.stderr.close()))
        self.assertEqual(holder.stdout.readline().strip(), 'held', holder.stderr.read() if holder.poll() is not None else '')
        return holder

    def test_a_lock_held_too_long_refuses_the_save_and_keeps_the_file(self):
        storage.save(self.path, {'phase': 'kept'}, keep_previous=True)
        self.hold(str(self.path).upper())  # Another spelling of the same file is the same lock.
        with patch.object(storage, 'SAVE_LOCK_WAIT', 0.3), self.assertRaises(TimeoutError):
            storage.save(self.path, {'phase': 'refused'}, keep_previous=True)
        self.assertEqual(record(self.path), {'phase': 'kept'})
        storage.save(self.data / 'folders.json', {'folders': {}}, keep_previous=True)  # Another file is not held.
        storage.save(self.path, {'phase': 'plain'})  # A save without a previous copy never waits for the lock.

    def test_a_lock_left_by_a_killed_process_is_free(self):
        holder = self.hold(self.path)
        holder.kill()
        holder.wait(30)
        with patch.object(storage, 'SAVE_LOCK_WAIT', 10):
            storage.save(self.path, {'phase': 'after the crash'}, keep_previous=True)
        self.assertEqual(record(self.path), {'phase': 'after the crash'})


if __name__ == '__main__':
    unittest.main()
