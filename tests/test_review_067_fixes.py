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

    def test_the_approve_path_deletes_the_backup_only_after_the_write_is_on_disk(self):
        # As Approve (and batch.apply) do it: the write returns, then the caller deletes the backup.
        with self.path.open('rb') as handle:
            import hashlib
            original = hashlib.file_digest(handle, 'sha256').hexdigest()
        backup = app.write_metadata(catalog_row(self.path), {'Writer': 'Alan Grant'}, verify_readback=True)
        app.remove_verified_backup(str(self.path), backup, original)
        self.assertEqual([durable for durable, _ in self.at_removal], [True])
        self.assert_survives_a_power_cut()


if __name__ == '__main__':
    unittest.main()
