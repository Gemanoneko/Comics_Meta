"""Code review v0.6.8 fixes for 0.6.9 (Docs/ComicsMetaOrganizer_CodeReview_v0.6.8_2026-11-19.md).

r2: a flush needs a handle with write access. Another program that holds the file open without sharing write (a
reader or thumbnailer that opens it with FILE_SHARE_READ only) made CreateFileW fail at once with Windows error 32,
and the write stopped. Futaba reproduced it with such a holder on the written comic (TrayQA v0.6.8). The flush now
waits that holder out for a while (Sergei 2026-11-19), in the app's Approve and worker writes as in the merge tool.

R3: a CBR/CB7 converted to CBZ is flushed to disk (file and folder) before its original is deleted.

Futaba's TrayQA v0.6.8 finding 1: a library claim lock that cannot be opened for writing counts only when it is really
locked, as engine_host.held_claims (q1) already does.

Isolated catalog and archives; the holders are real Windows handles in this process.
"""
import ctypes
import io
import json
import os
import stat
import subprocess
import threading
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import app
import archive_conversion
import file_lock
import library_lock
import storage
from test_library_lock import LockFixture
from test_storage_durable import Disk
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

    def held_at_the_rename(self, release_after=None):
        """Another program opens the comic itself right before the writer's rename over it. Windows refuses to replace
        an open file (MoveFileExW gives error 5, whatever sharing the holder allows)."""
        real = storage.flush_file

        def flush_file(path):
            result = real(path)
            if str(path).endswith('.metadata-tmp'):  # The temporary archive's flush comes right before the rename.
                holder = Holder(app.filesystem_path(self.path))
                self.holders.append(holder.release_after(release_after) if release_after else holder)
            return result
        return patch.object(storage, 'flush_file', flush_file)

    def test_r2_approve_and_the_worker_wait_out_a_reader_holding_the_comic_at_its_rename(self):
        # Sergei 2026-11-19 (r2 follow-up). Before: PermissionError [WinError 5] at once, the comic unchanged.
        for mode, field, options in (('approve', 'Writer', {'verify_readback': True, 'overwrite_fields': ('Web',)}),
                                     ('worker', 'Penciller', {'remove_verified_backups': True})):
            with self.subTest(mode=mode):
                with self.held_at_the_rename(release_after=.4):
                    app.write_metadata(catalog_row(self.path), {field: 'Written by ' + mode}, **options)
                self.assertIsNotNone(self.holders[-1].released_at)
                self.assertEqual(app.read_metadata(self.path)[0].get(field), 'Written by ' + mode)

    def assert_unchanged_after_a_refused_rename(self, before, started, at_most):
        self.assertLess(time.monotonic() - started, at_most)
        self.assertEqual(self.path.read_bytes(), before)  # Unchanged, as before 0.6.9.
        self.assertFalse(self.path.with_name(self.path.name + '.metadata-tmp').exists())
        self.assertFalse(app.pending_write_path(str(self.path)).exists())
        with app.db() as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM history').fetchone()[0], 0)

    def test_r2_a_comic_still_held_at_its_rename_stays_unchanged(self):
        before, started, attempt = self.path.read_bytes(), time.monotonic(), {}
        with self.held_at_the_rename(), patch.object(storage, 'RENAME_HELD_WAIT', .3), \
                self.assertRaises(PermissionError):
            app.write_metadata(catalog_row(self.path), {'Writer': 'Alan Grant'}, attempt=attempt, verify_readback=True)
        self.assertGreaterEqual(time.monotonic() - started, .3)  # It waited.
        self.assert_unchanged_after_a_refused_rename(before, started, 5)

    def test_r2_a_read_only_comic_is_still_refused_at_once(self):
        # Error 5 is also what a read-only comic gives; that is never waited for (code review v0.6.8 R1 keeps its outcome).
        os.chmod(self.path, stat.S_IREAD)
        self.addCleanup(os.chmod, self.path, stat.S_IREAD | stat.S_IWRITE)
        before, started = self.path.read_bytes(), time.monotonic()
        with self.assertRaises(PermissionError):
            app.write_metadata(catalog_row(self.path), {'Writer': 'Alan Grant'}, verify_readback=True)
        for backup in self.folder.rglob('*.bak'):
            os.chmod(backup, stat.S_IREAD | stat.S_IWRITE)  # copy2 copied the read-only bit; let scratch cleanup remove it.
        self.assert_unchanged_after_a_refused_rename(before, started, 2)


@unittest.skipUnless(archive_conversion.SEVEN_ZIP.exists(), '7-Zip unavailable')
class DurableConversionTests(unittest.TestCase):
    """R3: CBR/CB7 to CBZ conversion wrote the CBZ, renamed it with os.replace (no flush, not written through),
    verified it from the OS cache and deleted the original, with no backup. After a power loss NTFS can keep the rename
    and the deletion while the CBZ's bytes never reached the disk: a zero-filled CBZ, the original gone. The Disk model
    of test_storage_durable stands in for the power cut."""

    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app, 'DATA', self.root / 'data'))
        self.enterContext(patch.object(archive_conversion.pause_control, 'requested', return_value=False))
        self.disk, self.at_removal, self.folder_flushes = Disk(), [], []
        self.enterContext(patch.object(storage.os, 'fsync', self.disk.fsync))
        self.enterContext(patch.object(storage, '_move_file', self.disk.move_file))
        real_flush_directory, real_unlink = storage.flush_directory, os.unlink

        def flush_directory(path):
            self.folder_flushes.append(Path(path))
            return real_flush_directory(path)

        def unlink(path, *args, **kwargs):
            # What the disk holds of the new CBZ at the moment its original goes.
            if Path(path).suffix in ('.cb7', '.conversion-original'):
                final = self.final
                renames = [flags for event, flags in zip([e for e in self.disk.events if e[0] == 'rename'], self.disk.flags)
                           if event[2] == final.name]
                self.at_removal.append((os.stat(final).st_ino in self.disk.durable, renames,
                                        any(os.path.samefile(folder, final.parent) for folder in self.folder_flushes)))
            return real_unlink(path, *args, **kwargs)
        self.enterContext(patch.object(storage, 'flush_directory', flush_directory))
        self.enterContext(patch.object(os, 'unlink', unlink))

    def original(self, name):
        folder = self.root / 'input'
        folder.mkdir()
        Image.new('RGB', (20, 20), 'red').save(folder / '001.png')
        (folder / 'ComicInfo.xml').write_text('<ComicInfo><Title>Example</Title></ComicInfo>')
        path = self.root / 'Example.cb7'
        subprocess.run([str(archive_conversion.SEVEN_ZIP), 'a', '-t7z', str(path), '001.png', 'ComicInfo.xml'], cwd=folder,
                       capture_output=True, check=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if name != path.name:
            path = path.rename(self.root / name)
        self.final = path.with_suffix('.cbz')
        return path

    def assert_durable_before_the_original_goes(self, original):
        result = archive_conversion.convert(original)
        self.assertTrue(result['original_removed'])
        write_through = storage.MOVEFILE_REPLACE_EXISTING | storage.MOVEFILE_WRITE_THROUGH
        # Before: [(False, [], False)]: never flushed, renamed with os.replace, folder never flushed.
        self.assertEqual(self.at_removal, [(True, [write_through], True)])
        self.disk.power_cut(self.final)
        with zipfile.ZipFile(self.final) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(archive.read('001.png'), (self.root / 'input' / '001.png').read_bytes())

    def test_r3_a_cb7_is_on_the_disk_as_a_cbz_before_the_original_is_deleted(self):
        original = self.original('Example.cb7')
        self.assert_durable_before_the_original_goes(original)
        self.assertFalse(original.exists())

    def test_r3_a_cbz_named_7z_is_replaced_durably_before_its_set_aside_original_is_deleted(self):
        self.assert_durable_before_the_original_goes(self.original('Example.cbz'))
        self.assertFalse(list(self.root.glob('*.conversion-original')))

    def test_r3_a_cbz_that_cannot_be_flushed_never_costs_the_original(self):
        original = self.original('Example.cb7')
        before = original.read_bytes()
        with patch.object(storage, 'flush_file', side_effect=OSError(5, 'Access is denied')):
            with self.assertRaises(OSError):
                archive_conversion.convert(original)
        self.assertEqual(original.read_bytes(), before)  # Kept; no CBZ was renamed into place.
        self.assertFalse(self.final.exists())
        self.assertEqual(self.at_removal, [])


class UnopenableClaimTests(LockFixture):
    """Futaba's TrayQA v0.6.8 finding 1: library_lock._overlapping_owner counted any claim lock it could not open for
    writing as a live claim. Read-only claim locks whose .json records were missing (nobody holding them) then failed
    every start with LIBRARY_BUSY ("Another Comics Meta copy is using this library (state folder: unknown)"), and Try
    again did not help. Now the rule of engine_host.held_claims (code review v0.6.7 q1): only a lock conflict counts."""

    def setUp(self):
        super().setUp()
        self.claims = self.locks / 'claims'
        self.claims.mkdir(parents=True)

    def read_only_lock(self, name='engine-' + 'a' * 64 + '-4242-0123456789ab.lock', held=False):
        lock = self.claims / name
        fd = file_lock.open_lock(lock)
        if held:
            self.assertTrue(file_lock.try_lock(fd))  # A live claimant: the lock is really held.
            self.addCleanup(os.close, fd)
        else:
            os.close(fd)
        os.chmod(lock, stat.S_IREAD)
        self.addCleanup(lambda: lock.exists() and os.chmod(lock, stat.S_IREAD | stat.S_IWRITE))
        return lock

    def claim(self):
        claim = library_lock.acquire(self.library, 'dashboard')
        self.addCleanup(claim.release)
        return claim

    def test_finding_1_a_read_only_claim_lock_nobody_holds_never_blocks_a_start(self):
        self.read_only_lock()  # Its .json record missing, as in Futaba's edge probe.
        self.assertTrue(self.claim().held)  # Before: LibraryBusy (state folder: unknown).

    def test_finding_1_a_read_only_lock_of_another_copy_that_has_ended_never_blocks_a_start(self):
        lock = self.read_only_lock()
        lock.with_suffix('.json').write_text(json.dumps({
            'state_root': str(self.other_state), 'state_identity': library_lock.identity(self.other_state),
            'library': str(self.library), 'library_identity': library_lock.identity(self.library)}), encoding='utf-8')
        self.assertTrue(self.claim().held)  # Before: LibraryBusy naming the other copy's state folder.

    def test_finding_1_a_claim_lock_that_cannot_be_opened_at_all_is_logged_once_and_not_counted(self):
        lock = self.claims / 'foreign.lock'
        lock.write_bytes(b'')
        real_open_lock, real_open = file_lock.open_lock, os.open

        def refuse(path, *args):
            if Path(path).name == lock.name:
                raise PermissionError(13, 'Access is denied', str(path))
        with patch.object(library_lock, '_unopenable_logged', set(), create=True), \
                patch.object(file_lock, 'open_lock', lambda path, create=True: refuse(path) or real_open_lock(path, create)), \
                patch.object(library_lock.os, 'open', lambda path, flags, *rest: refuse(path) or real_open(path, flags, *rest)), \
                patch('sys.stderr', new_callable=io.StringIO) as log:
            self.claim().release()  # Before: LibraryBusy (state folder: unknown).
            self.claim()
        self.assertEqual(log.getvalue().count('foreign.lock cannot be opened'), 1)
        self.assertTrue(lock.exists())  # Not counted, and not removed either.

    def test_positive_control_a_read_only_claim_lock_a_live_process_holds_still_refuses(self):
        self.read_only_lock(held=True)  # No record: a held claim that cannot be read is not proof the library is free.
        with self.assertRaises(library_lock.LibraryBusy) as caught:
            self.claim()
        self.assertEqual(caught.exception.owner['state_root'], 'unknown')


if __name__ == '__main__':
    unittest.main()
