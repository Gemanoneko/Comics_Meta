"""Kept backups (UXSpec BackupLocation 2026-10-16 Amendment): list, show in folder, delete.

Throwaway fixture library only; File Explorer is stubbed (spec section 7.6, Amendment A6.6)."""
import io
import json
import os
import stat
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import app
import kept_backups
from test_worker import scratch_directory


def writable(*paths):
    for path in paths:
        if os.path.exists(path):
            os.chmod(path, stat.S_IREAD | stat.S_IWRITE)


class KeptBackupTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        self.library = self.root / 'library'
        self.series = self.library / 'Séries [One], two'
        self.series.mkdir(parents=True)
        self.enterContext(patch.object(app, 'DATA', self.root / 'data'))
        self.enterContext(patch.object(app, 'live_root', return_value=str(self.library)))
        self.comic = self.series / 'Comic 001.cbz'
        with zipfile.ZipFile(self.comic, 'w') as archive:
            archive.writestr('001.jpg', b'page')
        self.elsewhere = self.root / 'elsewhere'
        self.elsewhere.mkdir()
        with zipfile.ZipFile(self.elsewhere / 'Other.cbz', 'w') as archive:
            archive.writestr('001.jpg', b'page')
        app.scan([str(self.library)])
        app.scan([str(self.elsewhere)])  # In the catalog but outside the configured library.
        app.JOB['running'] = False
        kept_backups._IDS.clear()
        self.folder = self.series / '.comic-metadata-backups'

    def tearDown(self):
        app.JOB['running'] = False
        kept_backups._IDS.clear()

    def backup(self, ns, size=10, comic=None, folder=None):
        folder = folder or self.folder
        folder.mkdir(exist_ok=True)
        path = folder / ((comic or self.comic.name) + '.' + str(ns) + '.bak')
        path.write_bytes(b'x' * size)
        return path

    def listed(self):
        return kept_backups.listing()

    def test_lists_only_owned_backups_newest_first_with_reasons(self):
        older = self.backup(1_700_000_000_000_000_000, 10)
        newer = self.backup(1_800_000_000_000_000_000, 20)
        kept_backups.record(self.comic, app.filesystem_path(newer), 'save_not_verified')
        (self.folder / 'notes.txt').write_text('not a backup')
        (self.folder / (self.comic.name + '.bak')).write_bytes(b'no time stamp')
        (self.series / (self.comic.name + '.1.bak')).write_bytes(b'outside the backup folder')
        self.backup(1_900_000_000_000_000_000, 5, 'Other.cbz', self.elsewhere / '.comic-metadata-backups')
        result = self.listed()
        self.assertEqual([item['created'] for item in result['items']], [1.8e9, 1.7e9])
        self.assertEqual([item['reason'] for item in result['items']], ['save_not_verified', None])
        self.assertEqual((result['count'], result['bytes'], result['bounded']), (2, 30, False))
        first = result['items'][0]
        self.assertEqual((first['name'], first['folder'], first['size']), (self.comic.name, str(self.series), 20))
        self.assertNotIn('\\\\?\\', first['folder'])
        for item in result['items']:
            self.assertRegex(item['id'], '^[0-9a-f]{32}$')
            self.assertNotIn(str(self.root), json.dumps(item['id']))
        self.assertEqual(self.listed()['items'][0]['id'], first['id'])  # The same backup keeps its id.
        self.assertTrue(older.exists() and newer.exists())

    def test_the_bound_is_disclosed(self):
        for ns in (1, 2, 3):
            self.backup(1_700_000_000_000_000_000 + ns)
        with patch.object(kept_backups, 'LIMIT', 2):
            result = self.listed()
        self.assertEqual((result['count'], result['bounded']), (2, True))
        self.assertEqual(self.listed()['bounded'], False)  # Control: under the bound nothing is hidden.

    def test_no_library_lists_nothing_and_a_missing_drive_is_unavailable(self):
        self.backup(1_700_000_000_000_000_000)
        with patch.object(app, 'live_root', return_value=''):
            self.assertEqual(self.listed()['items'], [])
        with patch.object(app, 'live_root', return_value=str(self.root / 'unplugged')):
            with self.assertRaises(kept_backups.BackupError):
                self.listed()

    def test_a_write_in_progress_is_neither_listed_nor_deletable(self):
        self.backup(1_700_000_000_000_000_000)
        ident = self.listed()['items'][0]['id']
        with app.comic_write_guard(self.comic):
            self.assertEqual(self.listed()['items'], [])
            self.assertEqual(kept_backups.delete([ident])['failed'], [{'id': ident, 'code': 'writing'}])
        self.assertEqual(len(self.listed()['items']), 1)  # Control: listed again once the writer is done.

    def test_delete_removes_exactly_the_listed_ids(self):
        first = self.backup(1_700_000_000_000_000_000, 10)
        second = self.backup(1_800_000_000_000_000_000, 20)
        kept_backups.record(self.comic, second, 'delete_refused')
        ids = [item['id'] for item in self.listed()['items']]
        late = self.backup(1_900_000_000_000_000_000, 5)  # Appeared after the list was read.
        result = kept_backups.delete(ids)
        self.assertEqual((sorted(result['deleted']), result['failed'], result['freed']), (sorted(ids), [], 30))
        self.assertFalse(first.exists() or second.exists())
        self.assertTrue(late.exists())
        with app.db() as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM kept_backups').fetchone()[0], 0)
        self.assertEqual(kept_backups.delete(ids)['failed'][0]['code'], 'not_found')
        kept_backups.delete([self.listed()['items'][0]['id']])
        self.assertFalse(self.folder.exists())  # The emptied backup folder goes too.
        self.assertTrue(self.comic.exists())

    def test_read_only_backup_of_a_read_only_comic_is_deleted(self):
        path = self.backup(1_700_000_000_000_000_000)
        os.chmod(path, stat.S_IREAD)
        self.addCleanup(writable, path)
        ident = self.listed()['items'][0]['id']
        self.assertEqual(kept_backups.delete([ident])['deleted'], [ident])
        self.assertFalse(path.exists())

    def test_routes_never_take_a_path(self):
        path = self.backup(1_700_000_000_000_000_000)
        for ident in (str(path), str(app.filesystem_path(path)), 'f' * 32, 7, None):
            self.assertIn(kept_backups.delete([ident])['failed'][0]['code'], ('not_found',))
            with self.assertRaises(kept_backups.BackupError) as caught:
                kept_backups.reveal(ident)
            self.assertEqual(caught.exception.code, 'not_found')
        self.assertTrue(path.exists())

    def test_delete_refuses_anything_but_a_backup_in_the_library(self):
        other_backup = self.backup(1, 5, 'Other.cbz', self.elsewhere / '.comic-metadata-backups')
        loose = self.series / (self.comic.name + '.1.bak')
        loose.write_bytes(b'not in the backup folder')
        odd = self.folder / 'notes.bak'
        self.folder.mkdir()
        odd.write_bytes(b'not a backup name')
        for target in (other_backup, loose, odd, self.comic):
            with self.subTest(target=target.name):
                ident = kept_backups.issue(target)  # As if the server had issued an id for it.
                self.assertEqual(kept_backups.delete([ident])['failed'], [{'id': ident, 'code': 'refused'}])
                self.assertTrue(target.exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows junctions')
    def test_linked_backup_folder_is_refused(self):
        import _winapi
        target = self.elsewhere / 'linked-target'
        target.mkdir()
        (target / (self.comic.name + '.1.bak')).write_bytes(b'outside the library')
        _winapi.CreateJunction(str(target), str(self.folder))
        path = self.folder / (self.comic.name + '.1.bak')
        self.assertEqual(self.listed()['items'], [])
        ident = kept_backups.issue(path)
        self.assertEqual(kept_backups.delete([ident])['failed'][0]['code'], 'refused')
        self.assertTrue((target / (self.comic.name + '.1.bak')).exists())
        os.rmdir(self.folder)  # Removes the junction only.

    def test_reveal_selects_the_file_and_falls_back_to_its_folder(self):
        path = self.backup(1_700_000_000_000_000_000)
        ident = self.listed()['items'][0]['id']
        with patch.object(kept_backups, '_select') as select, patch.object(kept_backups, '_open_folder') as folder:
            self.assertEqual(kept_backups.reveal(ident), {'ok': True})
        select.assert_called_once_with(str(path))
        folder.assert_not_called()
        with patch.object(kept_backups, '_select', side_effect=OSError('too long')), patch.object(kept_backups, '_open_folder') as folder:
            kept_backups.reveal(ident)
        folder.assert_called_once_with(str(self.folder))
        with patch.object(kept_backups, '_select', side_effect=OSError), patch.object(kept_backups, '_open_folder', side_effect=OSError):
            with self.assertRaises(kept_backups.BackupError) as caught:
                kept_backups.reveal(ident)
        self.assertEqual(caught.exception.code, 'failed')
        path.unlink()
        with patch.object(kept_backups, '_select') as select, self.assertRaises(kept_backups.BackupError) as caught:
            kept_backups.reveal(ident)
        self.assertEqual(caught.exception.code, 'not_found')
        select.assert_not_called()
        os.rename(self.series, self.root / 'moved')
        with self.assertRaises(kept_backups.BackupError) as caught:
            kept_backups.reveal(ident)
        self.assertEqual(caught.exception.code, 'folder_unavailable')

    def handler(self, method, path, body=None, **headers):
        item = object.__new__(app.Handler)
        item.server = SimpleNamespace(server_port=8765, setup_required=False)
        item.path = path
        raw = json.dumps(body).encode() if body is not None else b''
        item.headers = {'Host': '127.0.0.1:8765', 'Origin': 'http://127.0.0.1:8765', 'Content-Length': str(len(raw)), **headers}
        item.rfile = io.BytesIO(raw)
        replies = []
        item.respond = lambda payload, status=200, mime='application/json': replies.append((status, payload))
        getattr(item, 'do_' + method)()
        return replies[-1]

    def test_routes_are_same_origin_ids_only_and_allowed_while_paused(self):
        path = self.backup(1_700_000_000_000_000_000)
        status, listed = self.handler('GET', '/api/backups')
        self.assertEqual((status, listed['count']), (200, 1))
        self.assertEqual(self.handler('GET', '/api/backups', **{'Sec-Fetch-Site': 'cross-site'})[0], 403)
        self.assertEqual(self.handler('GET', '/api/backups?path=' + str(path))[0], 400)
        ident = listed['items'][0]['id']
        for body in ({'id': ident, 'path': str(path)}, {'path': str(path)}, [ident]):
            self.assertEqual(self.handler('POST', '/api/backups/reveal', body)[0], 400)
        for body in ({'ids': []}, {'ids': [ident, ident]}, {'ids': [ident], 'path': str(path)}, {'path': str(path)}, {'ids': [[ident]]}):
            self.assertEqual(self.handler('POST', '/api/backups/delete', body)[0], 400, body)
        self.assertTrue(path.exists())
        import pause_control
        with patch.object(pause_control, 'requested', return_value=True), patch.object(kept_backups, '_select') as select:
            self.assertEqual(self.handler('POST', '/api/backups/reveal', {'id': ident}), (200, {'ok': True}))
            select.assert_called_once()
            status, result = self.handler('POST', '/api/backups/delete', {'ids': [ident]})
        self.assertEqual((status, result['deleted']), (200, [ident]))
        self.assertFalse(path.exists())


class ApplyOutcomeTests(unittest.TestCase):
    """/api/apply tells its outcomes apart and returns the kept backup (Amendment A1, A7.1)."""
    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app, 'DATA', self.root / 'data'))
        self.path = self.root / 'Example.cbz'
        with zipfile.ZipFile(self.path, 'w') as archive:
            archive.writestr('001.jpg', b'unchanged page')
            archive.writestr('ComicInfo.xml', '<ComicInfo><Title>Personal title</Title></ComicInfo>')
        self.original = self.path.read_bytes()
        app.scan([str(self.root)], recursive=False)
        app.JOB['running'] = False
        with app.db() as con:
            self.row = dict(con.execute('SELECT * FROM comics WHERE path=?', (str(self.path),)).fetchone())
        self.addCleanup(lambda: writable(self.path, *self.backups()))

    def backups(self):
        return sorted((self.root / '.comic-metadata-backups').glob('*.bak'))

    def apply(self):
        import pause_control
        handler = object.__new__(app.Handler)
        handler.path = '/api/apply'
        handler.server = SimpleNamespace(server_port=8765)
        body = json.dumps({'comic': self.row['id'], 'issue': 1}).encode()
        handler.headers = {'Host': '127.0.0.1:8765', 'Origin': 'http://127.0.0.1:8765', 'Content-Length': str(len(body))}
        handler.rfile = io.BytesIO(body)
        with patch.object(pause_control, 'requested', return_value=False), patch.object(app, 'api', return_value={'description': 'Premise.'}), patch.object(handler, 'respond') as respond:
            handler.do_POST()
        return respond.call_args.args[0], (respond.call_args.args[1] if len(respond.call_args.args) > 1 else 200)

    def test_refused_cleanup_after_a_verified_save_is_a_success_that_keeps_the_backup(self):
        with patch.object(app, 'remove_verified_backup', side_effect=ValueError('Backup verification failed.')):
            result, status = self.apply()
        self.assertEqual(status, 200)
        self.assertEqual((result['verified'], result['backup_retained'], result['backup_removed_after_verification']), (True, True, False))
        self.assertRegex(result['backup_id'], '^[0-9a-f]{32}$')
        self.assertEqual(app.read_metadata(self.path)[0]['Summary'], 'Premise.')
        self.assertEqual([p.name for p in self.backups()], [Path(result['backup']).name])
        with app.db() as con:
            self.assertEqual(con.execute('SELECT reason FROM kept_backups').fetchall()[0][0], 'delete_refused')

    def test_verified_save_still_deletes_its_backup(self):
        result, status = self.apply()
        self.assertEqual((status, result['backup_retained'], result['backup_removed_after_verification']), (200, False, True))
        self.assertNotIn('backup_id', result)
        self.assertEqual(self.backups(), [])

    @unittest.skipUnless(os.name == 'nt', 'Windows refuses to replace a read-only file')
    def test_failure_after_the_backup_copy_returns_that_backup(self):
        os.chmod(self.path, stat.S_IREAD)
        result, status = self.apply()
        self.assertEqual(status, 400)
        self.assertEqual(result['error'], 'The change was not verified. Check the file and retained recovery backup before trying again.')
        self.assertRegex(result['backup_id'], '^[0-9a-f]{32}$')
        self.assertEqual([p.name for p in self.backups()], [Path(result['backup']).name])
        self.assertEqual(self.path.read_bytes(), self.original)
        with app.db() as con:
            self.assertEqual(con.execute('SELECT reason FROM kept_backups').fetchall()[0][0], 'save_not_verified')

    def test_a_failure_before_any_backup_is_the_server_text(self):
        self.path.write_bytes(self.original + b'changed')  # Stale signature: refused before the copy.
        result, status = self.apply()
        self.assertEqual(status, 400)
        self.assertNotIn('backup', result)
        self.assertIn('changed', result['error'])
        self.assertEqual(self.backups(), [])


if __name__ == '__main__':
    unittest.main()
