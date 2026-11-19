"""Code review v0.6.7 fixes for 0.6.8 (Docs/ComicsMetaOrganizer_CodeReview_v0.6.7_2026-11-18.md).

Q1: a written comic is on the disk before its backup is deleted. The writer rewrote the comic through a temporary
archive and os.replace(), checked it (from the OS cache) and returned; Approve, the worker's batch and
remove_verified_backups then deleted the backup. After a power loss NTFS can keep the rename and the deletion while
the new archive's data never reached the disk: the comic unreadable, its backup gone. The Disk model of
test_storage_durable stands in for the power cut: bytes never flushed (fsync) read back as zeros.

Isolated catalog and archives.
"""
import os
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
import app
import storage
from test_storage_durable import Disk
from test_worker import scratch_directory

ROOT_XML = '<?xml version="1.0"?><ComicInfo><Series>Lobo</Series></ComicInfo>'


def make_comic(path):
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('001.jpg', b'cover' * 200)
        archive.writestr('002.jpg', b'page' * 400)
        archive.writestr('ComicInfo.xml', ROOT_XML)
    return path


def catalog_row(path):
    with app.db() as con:
        return dict(con.execute('SELECT * FROM comics WHERE path=?', (str(path),)).fetchone())


class Library(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app, 'DATA', self.root / 'data'))
        self.folder = self.root / 'Lobo'
        self.folder.mkdir()
        self.path = make_comic(self.folder / 'Lobo 001 (1990).cbz')
        app.scan([str(self.folder)], recursive=False)

    def backups(self):
        return sorted(p.name for p in self.folder.rglob('*.bak'))


class DurableArchiveTests(Library):
    """Q1 in the app's own write paths."""
    def setUp(self):
        super().setUp()
        self.original_bytes = self.path.read_bytes()
        self.disk = Disk()
        self.enterContext(patch.object(storage.os, 'fsync', self.disk.fsync))
        self.enterContext(patch.object(storage, '_move_file', self.disk.move_file))
        self.at_removal = []
        real = app.remove_verified_backup

        def remove(path, backup, original_sha256):
            # What the disk holds of the comic at the moment its only other copy goes.
            ino = os.stat(app.filesystem_path(path)).st_ino
            renames = [event for event in self.disk.events if event[0] == 'rename']
            renamed = [flags for event, flags in zip(renames, self.disk.flags) if event[1] == ino]
            self.at_removal.append((ino in self.disk.durable, renamed))
            return real(path, backup, original_sha256)
        self.enterContext(patch.object(app, 'remove_verified_backup', remove))

    def assert_survives_a_power_cut(self):
        self.disk.power_cut(app.filesystem_path(self.path))
        with zipfile.ZipFile(self.path) as archive:
            self.assertIsNone(archive.testzip())
        self.assertEqual(app.read_metadata(self.path)[0].get('Writer'), 'Alan Grant')

    def test_the_worker_path_flushes_the_archive_before_its_backup_is_deleted(self):
        # remove_verified_backups=True: the batch the worker runs, and every other self-deleting write.
        app.write_metadata(catalog_row(self.path), {'Writer': 'Alan Grant'}, remove_verified_backups=True)
        write_through = storage.MOVEFILE_REPLACE_EXISTING | storage.MOVEFILE_WRITE_THROUGH
        # Before: (False, []): never flushed, renamed with os.replace().
        self.assertEqual(self.at_removal, [(True, [write_through])])
        self.assertEqual(self.backups(), [])
        self.assert_survives_a_power_cut()

    def test_r1_the_backup_is_on_disk_before_the_rename_makes_it_the_only_copy_of_the_original(self):
        # Code review v0.6.8 R1: the write keeps its backup (Approve-style before the caller deletes it, or a kept
        # backup); a power cut right after the write must not zero it while the comic holds the new values.
        backup = app.write_metadata(catalog_row(self.path), {'Writer': 'Alan Grant'}, verify_readback=True)
        backup_ino = os.stat(app.filesystem_path(backup)).st_ino
        fsynced = [event[1] for event in self.disk.events if event[0] == 'fsync']
        renames = [i for i, event in enumerate(self.disk.events) if event[0] == 'rename' and event[2] == self.path.name]
        self.assertEqual(len(renames), 1)
        self.assertIn(('fsync', backup_ino), self.disk.events[:renames[0]])  # Before: never flushed at all.
        self.assertIn(backup_ino, fsynced)
        self.disk.power_cut(app.filesystem_path(backup))
        with zipfile.ZipFile(backup) as copy:
            self.assertIsNone(copy.testzip())
            self.assertIsNone(app.metadata_xml(copy.read('ComicInfo.xml')).find('Writer'))  # The original, readable.
        self.assertEqual(Path(backup).read_bytes(), self.original_bytes)

    def test_r1_a_read_only_comics_backup_is_flushed_and_reported(self):
        # shutil.copy2 copies the read-only bit, and a flush needs write access: the first R1 commit refused the
        # flush before the write reported its backup, so Approve lost its "not verified, backup kept" outcome.
        import stat
        os.chmod(self.path, stat.S_IREAD)
        self.addCleanup(os.chmod, self.path, stat.S_IREAD | stat.S_IWRITE)
        attempt = {}
        with self.assertRaises(PermissionError):  # Windows refuses to replace a read-only comic, as before.
            app.write_metadata(catalog_row(self.path), {'Writer': 'Alan Grant'}, attempt=attempt)
        backup = app.filesystem_path(attempt['backup'])
        self.addCleanup(os.chmod, backup, stat.S_IREAD | stat.S_IWRITE)
        self.assertIn(os.stat(backup).st_ino, self.disk.durable)
        self.assertFalse(os.stat(backup).st_mode & stat.S_IWRITE)  # Its read-only bit put back, as copy2 made it.
        self.assertEqual(backup.read_bytes(), self.original_bytes)

    def test_the_approve_path_deletes_the_backup_only_after_the_write_is_on_disk(self):
        # As Approve (and batch.apply) do it: the write returns, then the caller deletes the backup.
        with self.path.open('rb') as handle:
            import hashlib
            original = hashlib.file_digest(handle, 'sha256').hexdigest()
        backup = app.write_metadata(catalog_row(self.path), {'Writer': 'Alan Grant'}, verify_readback=True)
        app.remove_verified_backup(str(self.path), backup, original)
        self.assertEqual([durable for durable, _ in self.at_removal], [True])
        self.assert_survives_a_power_cut()


class Killed(BaseException):
    """The process ends here: Quit's 30 s Closing cap terminating the engine's Job mid-Approve, a crash, a power cut.
    BaseException, so no `except Exception` in the writer runs, as with a real kill."""


class InterruptedWriteTests(Library):
    """Q2: the Closing cap can stop a manual Approve mid-write. Quit still always ends; the next start (or the comic's
    next write) finishes or undoes what the stopped write left: no temporary archive that blocks later writes, no
    written comic without its history."""
    def setUp(self):
        super().setUp()
        self.temporary = app.filesystem_path(self.path).with_name(self.path.name + '.metadata-tmp')
        self.original = self.path.read_bytes()

    def pending(self):
        folder = app.DATA / 'pending-writes'
        return sorted(p.name for p in folder.iterdir()) if folder.is_dir() else []

    def stop_at_rename(self, after):
        """Run an Approve-style write that is killed at its rename: just after it (after=True) or just before, with
        its temporary archive left on the disk as a kill leaves it."""
        real = storage.replace_durably

        def killed(source, destination, check=None):
            if after:
                real(source, destination, check=check)
            else:
                os.replace(source, str(source) + '.kept')
            raise Killed()
        with patch.object(storage, 'replace_durably', killed), self.assertRaises(Killed):
            app.write_metadata(catalog_row(self.path), {'Writer': 'Alan Grant'}, verify_readback=True,
                               overwrite_fields=('Web',), history_source='https://comicvine.gamespot.com/x/4000-1/')
        if not after:
            os.replace(str(self.temporary) + '.kept', self.temporary)

    def history(self):
        with app.db() as con:
            return [tuple(r) for r in con.execute(
                'SELECT h.source, l.writer, l.fields, l.origin FROM history h JOIN write_ledger l ON l.history_id=h.id')]

    def test_a_write_stopped_after_its_rename_gets_its_history_at_the_next_start(self):
        self.stop_at_rename(after=True)
        self.assertEqual(self.history(), [])  # What the stop left: a written comic with no history.
        outcomes = app.recover_interrupted_writes()  # The next start, before any worker.
        self.assertEqual([o['outcome'] for o in outcomes], ['recorded'])
        self.assertEqual(self.history(), [('https://comicvine.gamespot.com/x/4000-1/', 'manual', '{"Writer": "Alan Grant"}', 'recovered')])
        row = catalog_row(self.path)
        stat = self.path.stat()
        self.assertEqual((row['size'], row['mtime'], row['status']), (stat.st_size, stat.st_mtime_ns, 'tagged'))
        import provenance
        self.assertEqual(len(provenance.chain(row)), 1)  # The write chains to the archive: its provenance holds.
        self.assertEqual(self.pending(), [])
        self.assertEqual(len(self.backups()), 1)  # Kept (no proven original hash here), and listed with its reason.
        with app.db() as con:
            self.assertEqual([r[0] for r in con.execute('SELECT reason FROM kept_backups')], ['delete_refused'])
        self.assertEqual(app.recover_interrupted_writes(), [])  # Once.

    def test_a_write_stopped_before_its_rename_is_undone_at_the_next_start(self):
        self.stop_at_rename(after=False)
        self.assertTrue(self.temporary.exists())  # What blocked every later write to this comic.
        outcomes = app.recover_interrupted_writes()
        self.assertEqual([(o['outcome'], o['backup_removed']) for o in outcomes], [('undone', True)])
        self.assertFalse(self.temporary.exists())
        self.assertEqual(self.backups(), [])  # Proven an exact copy of the unchanged comic, so deleted.
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual((self.history(), self.pending()), ([], []))
        # The comic can be written again.
        app.write_metadata(catalog_row(self.path), {'Writer': 'Alan Grant'}, remove_verified_backups=True)
        self.assertEqual(app.read_metadata(self.path)[0]['Writer'], 'Alan Grant')

    def test_the_comics_next_write_recovers_first_if_no_start_came_between(self):
        self.stop_at_rename(after=False)
        # Before: ValueError('A temporary file already exists; inspect it before proceeding.')
        app.write_metadata(catalog_row(self.path), {'Writer': 'Alan Grant'}, remove_verified_backups=True)
        self.assertEqual(app.read_metadata(self.path)[0]['Writer'], 'Alan Grant')
        self.assertEqual((self.backups(), self.pending()), ([], []))
        self.stop_at_rename(after=True)
        # The stopped write changed the comic, so the next plan (made before it) is refused, after its history.
        stale = catalog_row(self.path)
        app.recover_interrupted_writes()
        with self.assertRaises(app.ArchiveChanged):
            app.write_metadata(stale, {'Penciller': 'Val Semeiks'})

    def test_an_ordinary_failure_before_the_rename_leaves_no_record(self):
        # The caller's own failure handling (F29) owns the backup, as before.
        with patch.object(zipfile.ZipFile, 'testzip', return_value='002.jpg'), self.assertRaisesRegex(ValueError, 'validation'):
            app.write_metadata(catalog_row(self.path), {'Writer': 'Alan Grant'})
        self.assertEqual(self.pending(), [])
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertFalse(self.temporary.exists())

    def test_an_unreadable_record_is_set_aside_and_never_blocks_the_comic(self):
        record = app.pending_write_path(self.path)
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_bytes(b'\x00' * 40)  # Damaged on the disk.
        # Before the fix: every write of this comic raised on the record, for good.
        app.write_metadata(catalog_row(self.path), {'Writer': 'Alan Grant'}, remove_verified_backups=True)
        self.assertEqual(app.read_metadata(self.path)[0]['Writer'], 'Alan Grant')
        self.assertEqual(self.pending(), [record.name + '.unreadable'])  # Kept as evidence, out of the way.
        self.assertEqual(app.recover_interrupted_writes(), [])

    def test_a_comic_changed_by_another_program_since_is_left_alone(self):
        self.stop_at_rename(after=False)
        make_comic(self.path)  # Saved again elsewhere: a new signature.
        os.utime(self.path, ns=(1, 1))
        outcomes = app.recover_interrupted_writes()
        self.assertEqual([o['outcome'] for o in outcomes], ['changed'])
        self.assertTrue(self.temporary.exists())  # Folder help shows it, as before.
        self.assertEqual(len(self.backups()), 1)


if __name__ == '__main__':
    unittest.main()
