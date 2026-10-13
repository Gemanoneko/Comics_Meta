import json
import os
import subprocess
import sys
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch
import app
import archive_conversion
import browser_worker
import file_lock
import library_lock
import maintenance
import pause_control
import worker
from test_worker import scratch_directory

CODE = Path(__file__).resolve().parents[1]
HOLDER = '''
import sys, library_lock
library_lock.acquire(sys.argv[1], "test holder")
print("held", flush=True)
sys.stdin.readline()
'''


class LockFixture(unittest.TestCase):
    """A throwaway lock folder, library and two state roots ("this copy" and "the other copy")."""

    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        self.locks = self.root / 'locks'
        self.library = self.root / 'Comics'
        self.library.mkdir()
        self.state = self.root / 'this-copy'
        self.other_state = self.root / 'other-copy'
        self.enterContext(patch.dict(os.environ, {library_lock.LOCK_DIR_ENV: str(self.locks)}))
        self.enterContext(patch.object(app, 'STATE_ROOT', self.state))
        self.enterContext(patch.object(app, 'DATA', self.state / 'data'))
        self.enterContext(patch.object(pause_control, '_stop_baseline', None))
        self.enterContext(patch.object(library_lock, '_role', None))
        held = []
        self.enterContext(patch.object(library_lock, '_held', held))
        self.addCleanup(lambda: [claim.release() for claim in list(held)])

    def other_copy_claims(self, folder=None):
        with patch.object(app, 'STATE_ROOT', self.other_state):
            claim = library_lock.acquire(folder or self.library, 'other copy')
        self.addCleanup(claim.release)
        return claim

    def configure(self, root):
        self.state.mkdir(exist_ok=True)
        (self.state / 'config.json').write_text(json.dumps({'automatic': {'enabled': True, 'root': str(root)}}),
                                                encoding='utf-8')

    def comic(self, name='Example 001.cbz'):
        path = self.library / name
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('001.jpg', b'cover')
        stat = path.stat()
        return path, {'id': 1, 'path': str(path), 'root': str(self.library), 'size': stat.st_size,
                      'mtime': stat.st_mtime_ns}


class ClaimTests(LockFixture):
    def test_processes_of_one_copy_share_a_library(self):
        dashboard = library_lock.acquire(self.library, 'dashboard')
        metadata = library_lock.acquire(self.library, 'metadata worker')
        self.addCleanup(dashboard.release)
        self.addCleanup(metadata.release)
        self.assertTrue(dashboard.held and metadata.held)

    def test_other_copy_is_refused_on_same_parent_or_child_folder(self):
        self.other_copy_claims()
        for folder in (self.library, self.root, self.library / 'Marvel'):
            with self.subTest(folder=folder), self.assertRaises(library_lock.LibraryBusy) as caught:
                library_lock.acquire(folder, 'dashboard')
            self.assertEqual(caught.exception.owner['state_root'], str(self.other_state))
            self.assertIn(str(self.other_state), str(caught.exception))
        sibling = self.root / 'Manga'
        library_lock.acquire(sibling, 'dashboard').release()  # A different library is free.

    def test_release_frees_the_library(self):
        other = self.other_copy_claims()
        with self.assertRaises(library_lock.LibraryBusy):
            library_lock.acquire(self.library)
        other.release()
        library_lock.acquire(self.library).release()
        self.assertEqual(list((self.locks / 'claims').iterdir()), [])

    def test_spellings_of_one_folder_are_one_library(self):
        self.other_copy_claims()
        for spelling in (str(self.library).upper(), str(self.library) + os.sep, '\\\\?\\' + str(self.library)):
            with self.subTest(spelling=spelling), self.assertRaises(library_lock.LibraryBusy):
                library_lock.acquire(spelling)

    def test_leftover_process_of_another_copy_blocks_until_it_ends(self):
        env = dict(os.environ, COMICS_META_STATE_ROOT=str(self.other_state), **{library_lock.LOCK_DIR_ENV: str(self.locks)})
        holder = subprocess.Popen([sys.executable, '-S', '-B', '-c', HOLDER, str(self.library)], cwd=CODE, env=env,
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(holder.stdout.readline().strip(), 'held', holder.stderr.read() if holder.poll() else '')
            with self.assertRaises(library_lock.LibraryBusy) as caught:
                library_lock.acquire(self.library, 'dashboard')
            self.assertEqual(caught.exception.owner['pid'], holder.pid)
        finally:
            holder.kill()  # Like a crash: no release code runs.
            holder.wait(30)
            holder.stdin.close();holder.stdout.close();holder.stderr.close()
        deadline = time.monotonic() + 10  # Windows may take a moment to drop a killed process's locks.
        while True:
            try:
                claim = library_lock.acquire(self.library, 'dashboard')
                break
            except library_lock.LibraryBusy:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.1)
        self.addCleanup(claim.release)
        names = sorted(p.name for p in (self.locks / 'claims').iterdir())
        self.assertEqual(len(names), 2)  # Only this claim's .lock and .json; the crashed claim was swept.
        self.assertTrue(all(name.startswith(str(os.getpid()) + '-') for name in names))

    def test_unreadable_live_claim_is_treated_as_busy(self):
        claims = self.locks / 'claims'
        claims.mkdir(parents=True)
        fd = file_lock.open_lock(claims / 'foreign.lock')
        self.addCleanup(os.close, fd)
        self.assertTrue(file_lock.try_lock(fd))
        (claims / 'foreign.json').write_text('not json', encoding='utf-8')
        with self.assertRaises(library_lock.LibraryBusy) as caught:
            library_lock.acquire(self.library)
        self.assertEqual(caught.exception.owner['state_root'], 'unknown')

    def test_unusable_lock_folder_fails_closed(self):
        blocker = self.root / 'not-a-folder'
        blocker.write_text('file')
        with patch.dict(os.environ, {library_lock.LOCK_DIR_ENV: str(blocker / 'locks')}):
            with self.assertRaises(library_lock.LibraryBusy):
                library_lock.acquire(self.library)

    def test_configured_library_is_claimed_and_none_without_configuration(self):
        self.assertIsNone(library_lock.claim_configured('dashboard'))
        self.configure(self.library)
        claim = library_lock.claim_configured('dashboard')
        self.assertEqual(claim.identity, library_lock.identity(self.library))
        self.assertIs(library_lock.require(self.library / 'Marvel' / 'x.cbz'), claim)  # Reused, not re-claimed.

    def test_write_outside_the_configured_library_claims_the_scanned_root(self):
        self.configure(self.root / 'Elsewhere')
        claim = library_lock.require(self.library / 'Marvel' / 'x.cbz', root=self.library)
        self.assertEqual(claim.identity, library_lock.identity(self.library))
        loose = library_lock.require(self.root / 'Loose' / 'y.cbz')
        self.assertEqual(loose.identity, library_lock.identity(self.root / 'Loose'))


class WriteGuardTests(LockFixture):
    def test_metadata_write_is_refused_before_any_change(self):
        path, row = self.comic()
        before = path.read_bytes()
        other = self.other_copy_claims()
        with self.assertRaises(library_lock.LibraryBusy):
            app.write_metadata(row, {'Title': 'Verified'}, remove_verified_backups=True)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(sorted(p.name for p in self.library.iterdir()), [path.name])  # No backup or temp file.
        other.release()
        app.write_metadata(row, {'Title': 'Verified'}, remove_verified_backups=True)  # Same write, library free.
        self.assertEqual(app.read_metadata(path)[0]['Title'], 'Verified')

    def test_backup_removal_is_refused(self):
        path, _ = self.comic()
        backup = self.library / '.comic-metadata-backups' / (path.name + '.1.bak')
        backup.parent.mkdir()
        backup.write_bytes(path.read_bytes())
        self.other_copy_claims()
        with self.assertRaises(library_lock.LibraryBusy):
            app.remove_verified_backup(path, backup, 'unused')
        self.assertTrue(backup.exists())

    def test_conversion_stops_the_folder_pass_instead_of_recording_a_failure(self):
        path = self.library / 'Example 001.cbr'
        path.write_bytes(b'Rar!fixture')
        with app.db() as con:
            con.execute("INSERT INTO comics(path,root,size,mtime,status) VALUES(?,?,?,?,'unsupported')",
                        (str(path), str(self.library), 11, 1))
        self.other_copy_claims()
        with patch.object(archive_conversion, 'SEVEN_ZIP', Mock(**{'is_file.return_value': True})), \
                patch.object(archive_conversion, 'signature', side_effect=AssertionError('Read after refusal')):
            with self.assertRaises(library_lock.LibraryBusy):
                archive_conversion.one(self.library)
        with app.db() as con:
            self.assertIsNone(con.execute('SELECT 1 FROM conversions').fetchone())  # No failure recorded.
            self.assertEqual(con.execute('SELECT status FROM comics').fetchone()[0], 'unsupported')

    def test_maintenance_keeps_conversion_staging_in_a_library_it_does_not_own(self):
        source = self.library / 'Example 001.cbr'
        source.write_bytes(b'source')
        stage = self.library / '.comic-metadata-convert-fixture'
        stage.mkdir()
        (stage / 'page.jpg').write_bytes(b'page')
        stat = source.stat()
        with app.db() as con:
            con.execute('CREATE TABLE conversion_staging(path TEXT PRIMARY KEY,source TEXT,signature TEXT,created REAL)')
            con.execute('INSERT INTO conversion_staging VALUES(?,?,?,0)',
                        (str(stage), str(source), json.dumps([stat.st_size, stat.st_mtime_ns])))
        other = self.other_copy_claims()
        maintenance.run(True)
        self.assertTrue(stage.exists())
        other.release()
        maintenance.run(True)  # Positive control: the same cleanup runs once the library is free.
        self.assertFalse(stage.exists())


class StartupTests(LockFixture):
    def setUp(self):
        super().setUp()
        self.configure(self.library)
        self.other_copy_claims()

    def test_dashboard_exits_with_busy_code_before_serving(self):
        with patch.object(app, 'LocalServer') as server, patch('supervisor.start') as supervise:
            self.assertEqual(app.main(['--no-browser', '--port', '0']), library_lock.EXIT_LIBRARY_BUSY)
        server.assert_not_called()
        supervise.assert_not_called()

    # The first step after the claim raises, so a broken lock fails the test instead of
    # leaving a real worker loop running.
    def test_metadata_worker_exits_before_any_work(self):
        with patch.object(worker, 'QUEUE', self.state / 'data' / 'queue'), \
                patch('free_search_browser.enable_worker_owner', side_effect=AssertionError('Worker started')) as owner:
            self.assertIsNone(worker.main())
        owner.assert_not_called()

    def test_cover_worker_exits_before_any_work(self):
        with patch('lens_browser_owner.enable', side_effect=AssertionError('Worker started')) as owner:
            self.assertIsNone(browser_worker.main(once=True))
        owner.assert_not_called()
        # Its own lease was released on the way out.
        fd = file_lock.open_lock(self.state / 'data' / 'browser-worker.lock')
        self.addCleanup(os.close, fd)
        self.assertTrue(file_lock.try_lock(fd))


class DashboardClaimTests(LockFixture):
    def test_dashboard_claims_the_configured_library_and_wires_quit_to_the_supervisor(self):
        self.configure(self.library)
        server = Mock(setup_required=False)
        server.serve_forever.side_effect = KeyboardInterrupt
        with patch.object(app, 'LocalServer', return_value=server), patch('supervisor.start') as supervise:
            self.assertEqual(app.main(['--no-browser', '--port', '0']), 0)
        self.assertIs(server.supervisor_stop, supervise.return_value)
        supervise.return_value.set.assert_called_once()
        with self.assertRaises(library_lock.LibraryBusy):
            self.other_copy_claims()


if __name__ == '__main__':
    unittest.main()
