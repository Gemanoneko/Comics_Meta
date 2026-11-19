"""Code review v0.6.8 fixes for 0.6.9 (Docs/ComicsMetaOrganizer_CodeReview_v0.6.8_2026-11-19.md).

r2: a flush needs a handle with write access. Another program that holds the file open without sharing write (a
reader or thumbnailer that opens it with FILE_SHARE_READ only) made CreateFileW fail at once with Windows error 32,
and the write stopped. Futaba reproduced it with such a holder on the written comic (TrayQA v0.6.8). The flush now
waits that holder out for a while (Sergei 2026-11-19), in the app's Approve and worker writes as in the merge tool.

Isolated catalog and archives; the holders are real Windows handles in this process.
"""
import ctypes
import os
import threading
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
import app
import storage
from test_worker import scratch_directory

ROOT_XML = '<?xml version="1.0"?><ComicInfo><Series>Lobo</Series></ComicInfo>'
GENERIC_READ, FILE_SHARE_READ, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS = 0x80000000, 0x1, 3, 0x02000000


class Holder:
    """Another program's handle on a file or folder: read access, sharing read only, as a reader that does not share
    write access opens it. A flush's CreateFileW (write access) then fails with Windows error 32 until it closes."""

    def __init__(self, path, directory=False):
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                       wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes, kernel.CloseHandle.restype = [wintypes.HANDLE], wintypes.BOOL
        self._kernel, self._guard = kernel, threading.Lock()
        handle = kernel.CreateFileW(str(path), GENERIC_READ, FILE_SHARE_READ, None, OPEN_EXISTING,
                                    FILE_FLAG_BACKUP_SEMANTICS if directory else 0, None)
        if handle is None or handle == wintypes.HANDLE(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        self.handle, self.released_at = handle, None

    def release(self):
        with self._guard:
            handle, self.handle = self.handle, None
            if handle is not None:
                self._kernel.CloseHandle(handle)
                self.released_at = time.monotonic()

    def release_after(self, seconds):
        timer = threading.Timer(seconds, self.release)
        timer.daemon = True
        timer.start()
        return self


def make_comic(path):
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('001.jpg', b'cover' * 200)
        archive.writestr('002.jpg', b'page' * 400)
        archive.writestr('ComicInfo.xml', ROOT_XML)
    return path


def catalog_row(path):
    with app.db() as con:
        return dict(con.execute('SELECT * FROM comics WHERE path=?', (str(path),)).fetchone())


@unittest.skipUnless(os.name == 'nt', 'Windows sharing modes')
class HeldFlushTests(unittest.TestCase):
    """r2 in storage.flush_file and flush_directory, which every app write flushes through."""

    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        self.path = self.root / 'Lobo 001 (1990).cbz'
        self.path.write_bytes(b'comic' * 100)

    def hold(self, path, directory=False):
        holder = Holder(path, directory)
        self.addCleanup(holder.release)
        return holder

    def test_r2_a_flush_waits_out_a_reader_that_does_not_share_write(self):
        for target, directory in ((self.path, False), (self.root, True)):
            with self.subTest(directory=directory):
                holder = self.hold(target, directory).release_after(.4)
                flush = storage.flush_directory if directory else storage.flush_file
                flush(target)  # Before: PermissionError [WinError 32] at once.
                self.assertIsNotNone(holder.released_at)  # It really waited for the holder.

    def test_r2_a_reader_that_never_lets_go_is_raised_after_the_wait(self):
        self.hold(self.path)
        started = time.monotonic()
        with patch.object(storage, 'FLUSH_HELD_WAIT', .3), self.assertRaises(PermissionError) as caught:
            storage.flush_file(self.path)
        self.assertEqual(caught.exception.winerror, 32)
        self.assertGreaterEqual(time.monotonic() - started, .3)
        self.assertLess(time.monotonic() - started, 5)

    def test_r2_any_other_error_is_raised_at_once(self):
        started = time.monotonic()
        with self.assertRaises(FileNotFoundError):
            storage.flush_file(self.root / 'missing.cbz')
        self.assertLess(time.monotonic() - started, 1)  # Only a holder's sharing violation is waited for.


@unittest.skipUnless(os.name == 'nt', 'Windows sharing modes')
class HeldWriteTests(unittest.TestCase):
    """r2 through the app's own writer, as Approve and the worker call it."""

    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app, 'DATA', self.root / 'data'))
        self.folder = self.root / 'Lobo'
        self.folder.mkdir()
        self.path = make_comic(self.folder / 'Lobo 001 (1990).cbz')
        app.scan([str(self.folder)], recursive=False)
        self.holders = []
        self.addCleanup(lambda: [holder.release() for holder in self.holders])

    def backups(self):
        return sorted(p.name for p in self.folder.rglob('*.bak'))

    def test_r2_approve_waits_out_a_reader_holding_its_new_backup(self):
        real = app.shutil.copy2

        def copy2(source, destination, *args, **kwargs):
            result = real(source, destination, *args, **kwargs)
            if str(destination).endswith('.bak'):  # A scanner opens the fresh backup without sharing write.
                self.holders.append(Holder(destination).release_after(.4))
            return result
        attempt = {}
        with patch.object(app.shutil, 'copy2', copy2):
            # Approve's call: verify_readback, the caller deletes the backup afterwards.
            backup = app.write_metadata(catalog_row(self.path), {'Writer': 'Alan Grant'}, attempt=attempt,
                                        verify_readback=True, overwrite_fields=('Web',))  # Before: PermissionError.
        self.assertEqual(len(self.holders), 1)
        self.assertIsNotNone(self.holders[0].released_at)
        self.assertEqual(attempt['backup'], backup)
        self.assertEqual(app.read_metadata(self.path)[0].get('Writer'), 'Alan Grant')
        with app.db() as con:
            self.assertEqual([r[0] for r in con.execute('SELECT backup FROM history')], [backup])

    def test_r2_the_worker_waits_out_a_reader_holding_its_temporary_archive(self):
        real = storage.replace_durably

        def replace_durably(source, destination):
            self.holders.append(Holder(source).release_after(.4))  # Held between its last write and its flush.
            return real(source, destination)
        with patch.object(storage, 'replace_durably', replace_durably):
            # The worker's call (batch.apply with remove_verified_backups): the writer deletes the backup itself.
            app.write_metadata(catalog_row(self.path), {'Writer': 'Alan Grant'}, remove_verified_backups=True)
        self.assertEqual(len(self.holders), 1)
        self.assertIsNotNone(self.holders[0].released_at)
        self.assertEqual(app.read_metadata(self.path)[0].get('Writer'), 'Alan Grant')
        self.assertEqual(self.backups(), [])  # Written, verified, flushed, then its backup deleted.


if __name__ == '__main__':
    unittest.main()
