import hashlib
import io
import json
import shutil
import sys
import unittest
import uuid
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app


class ManualBackupCleanupTests(unittest.TestCase):
    def setUp(self):
        self.scratch = Path(__file__).resolve().parents[1] / 'scratch' / 'manual-backup-cleanup-2026-10-10'
        self.root = self.scratch / str(uuid.uuid4())
        self.root.mkdir(parents=True)
        self.data_patch = patch.object(app, 'DATA', self.root / 'data')
        self.data_patch.start()
        self.path = self.root / 'Example.cbz'
        with zipfile.ZipFile(self.path, 'w') as archive:
            archive.writestr('001.jpg', b'unchanged page')
            archive.writestr('ComicInfo.xml', '<ComicInfo><Title>Personal title</Title></ComicInfo>')
        self.original = self.path.read_bytes()
        app.scan([str(self.root)], recursive=False)
        with app.db() as con:
            self.row = dict(con.execute('SELECT * FROM comics WHERE path=?', (str(self.path),)).fetchone())

    def tearDown(self):
        self.data_patch.stop()
        assert self.root.resolve().parent == self.scratch.resolve()
        shutil.rmtree(self.root)
        app.JOB['running'] = False

    def backups(self):
        return list((self.root / '.comic-metadata-backups').glob('*.bak'))

    def test_success_removes_backup_and_preserves_existing_fields_and_pages(self):
        backup = app.write_metadata(self.row, {'Title': 'Provider title', 'Summary': 'Premise.\r\nNext line.'}, remove_verified_backups=True)
        self.assertFalse(Path(backup).exists())
        self.assertFalse((self.root / '.comic-metadata-backups').exists())
        self.assertEqual(app.read_metadata(self.path)[0]['Title'], 'Personal title')
        self.assertEqual(app.read_metadata(self.path)[0]['Summary'], 'Premise.\r\nNext line.')
        with zipfile.ZipFile(self.path) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(archive.read('001.jpg'), b'unchanged page')

    def test_default_direct_writer_retains_legacy_backup(self):
        backup = app.write_metadata(self.row, {'Summary': 'Premise.'})
        self.assertEqual(Path(backup).read_bytes(), self.original)

    def test_final_readback_mismatch_retains_original_backup(self):
        read = app.read_metadata
        calls = 0
        def mismatch(path):
            nonlocal calls
            calls += 1
            value = read(path)
            if calls == 2:
                value[0]['Summary'] = 'Unexpected final text'
            return value
        with patch.object(app, 'read_metadata', side_effect=mismatch):
            with self.assertRaisesRegex(ValueError, 'Readback verification failed'):
                app.write_metadata(self.row, {'Summary': 'Premise.'}, remove_verified_backups=True)
        self.assertEqual(self.backups()[0].read_bytes(), self.original)

    def test_backup_hash_drift_is_retained(self):
        copy = shutil.copy2
        def drift(source, target):
            result = copy(source, target)
            with Path(target).open('ab') as handle:
                handle.write(b'unexpected backup drift')
            return result
        with patch.object(app.shutil, 'copy2', side_effect=drift):
            with self.assertRaisesRegex(ValueError, 'Backup verification failed'):
                app.write_metadata(self.row, {'Summary': 'Premise.'}, remove_verified_backups=True)
        self.assertEqual(len(self.backups()), 1)

    def test_source_changed_since_inventory_is_never_written(self):
        self.path.write_bytes(self.original + b'changed')
        with self.assertRaisesRegex(ValueError, 'File changed'):
            app.write_metadata(self.row, {'Summary': 'Premise.'}, remove_verified_backups=True)
        self.assertEqual(self.path.read_bytes(), self.original + b'changed')
        self.assertEqual(self.backups(), [])

    def test_delete_failure_retains_original_backup(self):
        unlink = Path.unlink
        def deny_backup(path, *args, **kwargs):
            if path.suffix == '.bak':
                raise PermissionError('Backup is locked')
            return unlink(path, *args, **kwargs)
        with patch.object(Path, 'unlink', deny_backup):
            with self.assertRaises(PermissionError):
                app.write_metadata(self.row, {'Summary': 'Premise.'}, remove_verified_backups=True)
        self.assertEqual(self.backups()[0].read_bytes(), self.original)

    def test_cleanup_refuses_backup_outside_owned_folder(self):
        outside = self.root / 'Example.cbz.1.bak'
        outside.write_bytes(self.original)
        with self.assertRaises((ValueError, FileNotFoundError)):
            app.remove_verified_backup(self.path, outside, hashlib.sha256(self.original).hexdigest())
        self.assertEqual(outside.read_bytes(), self.original)

    def test_manual_endpoint_requests_verified_cleanup_and_reports_it(self):
        handler = object.__new__(app.Handler)
        handler.path = '/api/apply'
        handler.server = SimpleNamespace(server_port=8765)
        body = json.dumps({'comic': self.row['id'], 'issue': 1}).encode()
        handler.headers = {'Host': '127.0.0.1:8765', 'Origin': 'http://127.0.0.1:8765', 'Content-Length': str(len(body))}
        handler.rfile = io.BytesIO(body)
        app.JOB['running'] = False
        import pause_control
        with patch.object(pause_control, 'requested', return_value=False), patch.object(app, 'api', return_value={'description': 'Premise.'}), patch.object(handler, 'respond') as respond:
            handler.do_POST()
        result = respond.call_args.args[0]
        self.assertTrue(result['ok'])
        self.assertTrue(result['backup_removed_after_verification'])
        self.assertFalse(Path(result['backup']).exists())
