"""Folder help lines (UXSpec FolderHelpActions 2026-10-16 and its Amendment): reason codes, Check and
requeue, Delete backup and requeue, Close and recheck folder, Open folder and Show in folder.

Throwaway fixture library and queue only (spec 9.6, A10.4): Check and requeue closes tickets and
Delete backup and requeue deletes files. File Explorer is stubbed."""
import io
import json
import os
import time
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import app
import batch
import discovery_state
import folder_help
import kept_backups
import library_lock
import pause_control
import progress_snapshot
import worker
from test_worker import scratch_directory

TICKET = '1760000000000000001'
MTIME = 1_700_000_000_123_456_789


class Fixture(unittest.TestCase):
    """A library folder, a plan written by the automatic pass, its ticket needing attention."""
    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        self.library = self.root / 'library'
        self.folder = (self.library / 'Batman [1940] Ü').resolve()
        self.folder.mkdir(parents=True)
        self.enterContext(patch.object(app, 'DATA', self.root / 'data'))
        self.enterContext(patch.object(app, 'live_root', return_value=str(self.library)))
        self.enterContext(patch.object(worker, 'QUEUE', self.root / 'queue'))
        self.paused = False
        self.enterContext(patch.object(pause_control, 'requested', side_effect=lambda: self.paused))
        self.select = self.enterContext(patch.object(kept_backups, '_select'))
        self.open_folder = self.enterContext(patch.object(kept_backups, '_open_folder'))
        worker.QUEUE.mkdir(parents=True)
        self.batch = self.root / 'batches' / TICKET
        self.batch.mkdir(parents=True)
        self.entries, self.results, self.failed = [], [], []
        folder_help._IDS.clear()

    def comic(self, name, comment=b'aaaa', record=True):
        path = self.folder / name
        with zipfile.ZipFile(path, 'w') as archive:
            archive.comment = comment
            archive.writestr('001.jpg', b'PAGEDATA' * 64)
        os.utime(path, ns=(MTIME, MTIME))
        info = path.stat()
        entry = {'path': str(path.resolve()), 'action': 'write', 'sha256': batch.digest(path),
                 'signature': [info.st_size, info.st_mtime_ns], 'changes': {'Series': {'before': '', 'after': 'Batman'}},
                 'fields': {'Series': 'Batman'}, 'method': 'test'}
        self.entries.append(entry)
        if record:
            discovery_state.save_one(path.resolve(), {'signature': [info.st_size, info.st_mtime_ns], 'outcome': 'queued',
                                                      'retry_at': time.time() + 30 * 86400})
        return path

    def written(self, path, sha256=False):
        """Mark the comic written and verified, as batch.apply records it."""
        info = path.stat()
        result = {'path': str(path.resolve()), 'backup': 'x', 'output_signature': [info.st_size, info.st_mtime_ns],
                  'metadata_readback_verified': True, 'backup_removed_after_verification': True}
        if sha256:
            result['output_sha256'] = batch.digest(path)  # Not recorded by batch.apply today (after_state).
        self.results.append(result)

    def backup(self, path, ns=1_760_000_000_000_000_000, data=None):
        folder = self.folder / '.comic-metadata-backups'
        folder.mkdir(exist_ok=True)
        target = folder / (path.name + '.' + str(ns) + '.bak')
        target.write_bytes(data if data is not None else path.read_bytes())
        return target

    def save(self, error=folder_help.INTERRUPTED, code='interrupted', state='needs_attention'):
        (self.batch / 'plan.json').write_text(json.dumps({'folder': str(self.folder), 'entries': self.entries}), encoding='utf-8')
        if self.results:
            (self.batch / 'results.json').write_text(json.dumps(self.results), encoding='utf-8')
        if self.failed:
            (self.batch / 'failed.json').write_text(json.dumps(self.failed), encoding='utf-8')
        ticket = {'plan': str(self.batch / 'plan.json'), 'folder': str(self.folder), 'state': state, 'error': error}
        if code:
            ticket['code'] = code
        (worker.QUEUE / (TICKET + '.json')).write_text(json.dumps(ticket), encoding='utf-8')

    def ticket(self):
        return json.loads((worker.QUEUE / (TICKET + '.json')).read_text(encoding='utf-8'))

    def record(self, path):
        with app.db() as con:
            found = con.execute('SELECT value FROM discovery_records WHERE path=?', (str(path.resolve()),)).fetchone()
        return json.loads(found['value'])

    def snapshot(self):
        """Every file in the library folder with its bytes and mtime."""
        return {str(p.relative_to(self.folder)): (p.read_bytes(), p.stat().st_mtime_ns) for p in sorted(self.folder.rglob('*')) if p.is_file()}

    def refused(self, call, code):
        with self.assertRaises(folder_help.HelpError) as caught:
            call()
        self.assertEqual(caught.exception.code, code)
        return caught.exception


class ReasonCodeTests(unittest.TestCase):
    def test_each_section_5_reason_and_the_fallback(self):
        cases = {
            folder_help.INTERRUPTED: 'interrupted',
            'A completed archive changed before batch resume; inspect it before retrying.': 'comic_changed',
            'Target must stay in the planned folder.': 'outside_folder',
            'Archive validation failed.': 'not_verified', 'Archive contents changed unexpectedly.': 'not_verified',
            'Temporary archive metadata verification failed for Series': 'not_verified',
            'Readback verification failed for Summary': 'not_verified', 'Backup verification failed.': 'not_verified',
            'Backup cleanup target is outside the expected folder.': 'backup_kept',
            'The library lock is busy. Nothing was changed; try again shortly.': 'library_busy',
            'Another Comics Meta copy is using this library (state folder: X). This copy will not change it.': 'library_busy',
            'A new library claim could not be locked. Nothing was changed.': 'library_busy',
            'The library lock folder is unavailable (OSError), so this copy will not change the library.': 'library_busy',
            "[WinError 5] Access is denied: 'D:\\\\Comics\\\\x.cbz'": 'other', "'entries'": 'other', '': 'other', None: 'other',
        }
        for text, code in cases.items():
            with self.subTest(text=text):
                self.assertEqual(folder_help.classify(text), code)
                if text:
                    self.assertEqual(folder_help.classify(ValueError(text)), code)
        self.assertEqual(folder_help.classify(library_lock.LibraryBusy('any words')), 'library_busy')

    def test_payload_has_id_and_code_in_queue_order_and_classifies_old_tickets(self):
        named = [('20', {'state': 'needs_attention', 'folder': 'D:\\B', 'error': 'Archive validation failed.'}),
                 ('10', {'state': 'needs_attention', 'folder': 'D:\\A', 'error': '', 'code': 'other'}),
                 ('15', {'state': 'complete', 'folder': 'D:\\C'}),
                 ('30', {'state': 'needs_attention', 'folder': 'D:\\D', 'error': 'x', 'code': 'not-a-code'})]
        self.assertEqual(folder_help.attention(named), [
            {'id': '10', 'code': 'other', 'folder': 'D:\\A', 'error': ''},
            {'id': '20', 'code': 'not_verified', 'folder': 'D:\\B', 'error': 'Archive validation failed.'},
            {'id': '30', 'code': 'other', 'folder': 'D:\\D', 'error': 'x'}])

    def test_snapshot_files_name_each_ticket(self):
        with scratch_directory() as directory:
            queue = Path(directory)
            for stem in ('2', '1'):
                (queue / (stem + '.json')).write_text(json.dumps({'state': 'needs_attention', 'folder': stem, 'error': ''}))
            (queue / 'heartbeat').write_text('{}')
            files = progress_snapshot.Files()
            try:
                self.assertEqual([stem for stem, _ in files.queue_named(queue)], ['1', '2'])
                self.assertEqual(files.queue(queue), [{'state': 'needs_attention', 'folder': '1', 'error': ''},
                                                      {'state': 'needs_attention', 'folder': '2', 'error': ''}])
            finally:
                files.close()

    def test_worker_stores_the_code_at_the_needs_attention_site(self):
        with scratch_directory() as directory:
            root = Path(directory)
            with patch.object(app, 'DATA', root / 'catalog'), patch.object(worker, 'QUEUE', root / 'queue'), \
                    patch.object(worker.pause_control, 'requested', return_value=False), \
                    patch.object(worker.batch, 'apply', side_effect=[ValueError('Readback verification failed for Series'),
                                                                     library_lock.LibraryBusy('Locked elsewhere'), ValueError('')]):
                for name in ('001', '002', '003'):
                    plan = root / name / 'plan.json'
                    plan.parent.mkdir()
                    plan.write_text(json.dumps({'folder': name, 'entries': [{'action': 'write'}]}))
                    worker.enqueue(plan)
                    worker.run_one()
                codes = [json.loads((worker.QUEUE / (n + '.json')).read_text())['code'] for n in ('001', '002', '003')]
        self.assertEqual(codes, ['not_verified', 'library_busy', 'other'])


class CheckTests(Fixture):
    def test_clean_check_closes_and_makes_only_the_unwritten_comics_due(self):
        done = self.comic('Batman 001.cbz')
        self.written(done)
        waiting = self.comic('Batman 002.cbz')
        failed = self.comic('Batman 003.cbz')
        self.failed.append({'path': str(failed.resolve()), 'reason': 'Duplicate ZIP entries require manual review.'})
        self.save()
        before = self.snapshot()
        started = time.time()
        self.assertEqual(folder_help.check(TICKET), {'ok': True, 'unwritten': 1, 'written': 1})
        ticket = self.ticket()
        self.assertEqual((ticket['state'], ticket['closed_by']), ('closed', 'check_and_requeue'))
        self.assertLessEqual(self.record(waiting)['retry_at'], time.time())
        self.assertGreaterEqual(self.record(waiting)['retry_at'], started)
        self.assertGreater(self.record(failed)['retry_at'], time.time() + 86400)  # Its own wait record is kept.
        self.assertEqual(self.snapshot(), before)  # No comic or other file changed.
        self.refused(lambda: folder_help.check(TICKET), 'gone')  # Closed: the line leaves.

    def test_singular_and_nothing_planned_counts(self):
        self.comic('Solo.cbz')
        self.save()
        self.assertEqual(folder_help.check(TICKET), {'ok': True, 'unwritten': 1, 'written': 0})
        self.entries.clear()
        self.save()
        self.assertEqual(folder_help.check(TICKET), {'ok': True, 'unwritten': 0, 'written': 0})

    def test_every_finding_sorted_with_nothing_changed(self):
        damaged = self.comic('a damaged.cbz')
        data = damaged.read_bytes()
        damaged.write_bytes(data.replace(b'PAGEDATA', b'PAGEDATX', 1))  # Same size, bad CRC.
        os.utime(damaged, ns=(MTIME, MTIME))
        written = self.comic('B written.cbz')
        self.written(written)
        self.results[-1]['output_signature'][1] += 1
        edited = self.comic('c edited.cbz')
        edited.write_bytes(edited.read_bytes().replace(b'aaaa', b'aaab'))
        os.utime(edited, ns=(MTIME, MTIME))
        gone = self.comic('D gone.cbz')
        gone.unlink()
        left = self.comic('e left.cbz')
        (self.folder / 'e left.cbz.metadata-tmp').write_bytes(b'partial')
        backup = self.backup(left)
        self.save()
        before = self.snapshot()
        result = folder_help.check(TICKET)
        self.assertEqual(result['code'], 'problems')
        self.assertEqual(result['total'], 6)
        self.assertEqual([(row['name'], row['finding'], row['file']) for row in result['problems']], [
            ('a damaged.cbz', 'zip_failed', 'a damaged.cbz'), ('B written.cbz', 'written_changed', 'B written.cbz'),
            ('c edited.cbz', 'unwritten_changed', 'c edited.cbz'), ('D gone.cbz', 'missing', self.folder.name),
            ('e left.cbz', 'temp_left', 'e left.cbz.metadata-tmp'), ('e left.cbz', 'backup_left', backup.name)])
        self.assertEqual(result['problems'][-1]['basis'], 'original')
        self.assertNotIn('offer', result)  # temp_left with backup_left: no offer (A3).
        for row in result['problems']:
            self.assertRegex(row['id'], '^[0-9a-f]{32}$')
            self.assertNotIn(str(self.root), json.dumps(row))
        self.assertEqual(self.ticket()['state'], 'needs_attention')
        self.assertEqual(self.snapshot(), before)
        self.assertGreater(self.record(left)['retry_at'], time.time() + 86400)

    def test_offer_needs_every_finding_a_proved_backup_and_all_on_screen(self):
        comics = [self.comic('Issue %02d.cbz' % n) for n in range(21)]
        for path in comics:
            self.backup(path)
        self.save()
        result = folder_help.check(TICKET)
        self.assertEqual((result['total'], len(result['problems'])), (21, 20))
        self.assertNotIn('offer', result)  # More than 20: no offer.
        self.entries.pop()
        self.save()
        result = folder_help.check(TICKET)
        self.assertEqual(result['total'], 20)
        self.assertEqual(result['offer']['kind'], 'delete_backup')  # Control: 20 on screen are offered.
        self.assertEqual(len(result['offer']['backups']), 20)
        self.assertEqual(result['offer']['unwritten'], 20)
        self.assertEqual({b['basis'] for b in result['offer']['backups']}, {'original'})

    def test_one_byte_or_one_mtime_different_is_not_proved(self):
        same_size = self.comic('Same size.cbz')
        self.backup(same_size)
        same_size.write_bytes(same_size.read_bytes().replace(b'aaaa', b'aaab'))
        os.utime(same_size, ns=(MTIME, MTIME))
        self.save()
        result = folder_help.check(TICKET)
        self.assertEqual([r['finding'] for r in result['problems']], ['unwritten_changed', 'backup_left'])
        self.assertNotIn('basis', result['problems'][1])
        self.assertNotIn('offer', result)
        self.entries.clear()
        touched = self.comic('Touched.cbz')
        self.backup(touched)
        os.utime(touched, ns=(MTIME, MTIME + 10**7))  # NTFS keeps 100 ns steps: move it by 10 ms.
        self.save()
        result = folder_help.check(TICKET)
        self.assertNotIn('offer', result)
        self.assertNotIn('basis', result['problems'][-1])
        os.utime(touched, ns=(MTIME, MTIME))  # Control: the recorded mtime proves it again.
        self.assertEqual(folder_help.check(TICKET)['offer']['backups'][0]['basis'], 'original')

    def test_written_basis_needs_a_recorded_after_hash(self):
        path = self.comic('Written.cbz')
        self.backup(path)  # The comic as it was before the write...
        path.write_bytes(path.read_bytes().replace(b'aaaa', b'bbbb'))
        os.utime(path, ns=(MTIME, MTIME + 10**9))  # ...and as the write left it.
        self.written(path)
        self.save()
        self.assertNotIn('offer', folder_help.check(TICKET))  # batch.apply records no output hash.
        self.results.clear()
        self.written(path, sha256=True)
        self.save()
        result = folder_help.check(TICKET)
        self.assertEqual(result['offer']['backups'][0]['basis'], 'written')
        self.assertEqual(result['offer']['unwritten'], 0)

    def test_all_or_none_with_one_unverifiable_backup(self):
        good = self.comic('Good.cbz')
        bad = self.comic('Bad.cbz')
        self.backup(good)
        self.backup(bad)
        del self.entries[-1]['signature']  # No recorded size and mtime: its before-state cannot be proved.
        self.save()
        result = folder_help.check(TICKET)
        self.assertEqual([(r['name'], r['finding'], r.get('basis')) for r in result['problems']],
                         [('Bad.cbz', 'backup_left', None), ('Good.cbz', 'backup_left', 'original')])
        self.assertNotIn('offer', result)

    def test_missing_or_damaged_plan_offers_close_and_recheck(self):
        path = self.comic('Waiting.cbz')
        other = self.comic('Other.cbz')
        self.save()
        (self.batch / 'plan.json').unlink()
        exc = self.refused(lambda: folder_help.check(TICKET), 'plan_unreadable')
        self.assertEqual(exc.payload()['offer'], {'kind': 'close_recheck'})
        (self.batch / 'plan.json').write_text('{"entries": [', encoding='utf-8')
        exc = self.refused(lambda: folder_help.check(TICKET), 'plan_unreadable')
        self.assertEqual(exc.payload()['offer'], {'kind': 'close_recheck'})
        before = self.snapshot()
        self.assertEqual(folder_help.close_recheck(TICKET), {'ok': True})
        self.assertEqual((self.ticket()['state'], self.ticket()['closed_by']), ('closed', 'close_recheck'))
        self.assertLessEqual(self.record(path)['retry_at'], time.time())
        self.assertLessEqual(self.record(other)['retry_at'], time.time())
        self.assertEqual(self.snapshot(), before)

    def test_close_and_recheck_is_refused_while_the_plan_can_be_read(self):
        self.comic('Readable.cbz')
        self.save()
        self.refused(lambda: folder_help.close_recheck(TICKET), 'plan_readable')
        self.assertEqual(self.ticket()['state'], 'needs_attention')

    def edit(self, path, old=b'aaaa', new=b'aaab'):
        """One byte different, same size and mtime: the comic changed after the batch was planned."""
        path.write_bytes(path.read_bytes().replace(old, new))
        os.utime(path, ns=(MTIME, MTIME))

    def test_every_finding_changed_after_planning_offers_close_and_recheck(self):
        done = self.comic('A done.cbz')
        self.written(done)
        first, second = self.comic('B edited.cbz'), self.comic('C edited.cbz')
        same = self.comic('D unchanged.cbz')
        failed = self.comic('E failed.cbz')
        self.failed.append({'path': str(failed.resolve()), 'reason': 'Duplicate ZIP entries require manual review.'})
        self.edit(first)
        self.save()
        result = folder_help.check(TICKET)
        self.assertEqual(([r['finding'] for r in result['problems']], result['offer']), (['unwritten_changed'], {'kind': 'close_recheck'}))
        self.edit(second)
        result = folder_help.check(TICKET)
        self.assertEqual((result['total'], result['offer']), (2, {'kind': 'close_recheck'}))
        self.assertEqual(self.ticket()['state'], 'needs_attention')  # The check closed nothing.
        before = self.snapshot()
        started = time.time()
        self.assertEqual(folder_help.close_recheck(TICKET), {'ok': True})
        self.assertEqual((self.ticket()['state'], self.ticket()['closed_by']), ('closed', 'close_recheck'))
        for path in (first, second, same):
            self.assertGreaterEqual(self.record(path)['retry_at'], started)
            self.assertLessEqual(self.record(path)['retry_at'], time.time())
        for path in (done, failed):  # Written, or waiting on its own record: not made due.
            self.assertGreater(self.record(path)['retry_at'], time.time() + 86400)
        self.assertEqual(self.snapshot(), before)  # No comic, temp or backup file changed.

    def test_close_and_recheck_needs_every_finding_changed_after_planning(self):
        edited, damaged = self.comic('Edited.cbz'), self.comic('Damaged.cbz')
        self.edit(edited)
        self.edit(damaged, b'PAGEDATA', b'PAGEDATX')  # Bad CRC: zip_failed, not unwritten_changed.
        self.save()
        result = folder_help.check(TICKET)
        self.assertEqual([r['finding'] for r in result['problems']], ['zip_failed', 'unwritten_changed'])
        self.assertNotIn('offer', result)
        self.refused(lambda: folder_help.close_recheck(TICKET), 'plan_readable')
        self.edit(damaged, b'PAGEDATX', b'PAGEDATA')  # Control: only the changed comic is left.
        self.assertEqual(folder_help.check(TICKET)['offer'], {'kind': 'close_recheck'})
        (self.folder / 'Edited.cbz.metadata-tmp').write_bytes(b'partial')  # Changed between check and click.
        exc = self.refused(lambda: folder_help.close_recheck(TICKET), 'plan_readable')
        self.assertEqual(exc.payload()['error'], 'this folder changed since the check; use Check and requeue')
        self.assertEqual(self.ticket()['state'], 'needs_attention')
        (self.folder / 'Edited.cbz.metadata-tmp').unlink()
        self.edit(edited, b'aaab', b'aaaa')  # Back as planned: the check would requeue it, so no close.
        self.refused(lambda: folder_help.close_recheck(TICKET), 'plan_readable')
        self.assertEqual(self.ticket()['state'], 'needs_attention')
        self.assertTrue(folder_help.check(TICKET)['ok'])

    def test_guards_paused_busy_gone_unavailable_and_outside(self):
        self.comic('Guarded.cbz')
        self.save()
        self.paused = True
        for call in (lambda: folder_help.check(TICKET), lambda: folder_help.close_recheck(TICKET),
                     lambda: folder_help.delete_backups(TICKET, ['0' * 32])):
            self.refused(call, 'paused')
        self.paused = False
        with folder_help._BUSY:
            self.refused(lambda: folder_help.check(TICKET), 'busy')
        self.refused(lambda: folder_help.check('1760000000000000002'), 'gone')
        for bad in ('..\\queue\\x', 'C:\\x', '../x', '', 'x/y', ' x'):
            self.refused(lambda: folder_help.check(bad), 'gone')
        with patch.object(app, 'live_root', return_value=str(self.root / 'elsewhere')):
            for call in (lambda: folder_help.check(TICKET), lambda: folder_help.close_recheck(TICKET),
                         lambda: folder_help.delete_backups(TICKET, ['0' * 32]), lambda: folder_help.reveal(TICKET)):
                self.assertEqual(self.refused(call, 'outside_library').payload()['error'], 'this folder is not in the current library.')
        os.rename(self.folder, self.library / 'moved')
        self.refused(lambda: folder_help.check(TICKET), 'folder_unavailable')
        os.rename(self.library / 'moved', self.folder)
        with patch.object(library_lock, 'require', side_effect=library_lock.LibraryBusy('busy')):
            self.refused(lambda: folder_help.check(TICKET), 'library_busy')
        self.assertEqual(self.ticket()['state'], 'needs_attention')
        self.assertEqual(folder_help.check(TICKET)['ok'], True)  # Control: unguarded, it closes.

    def test_pause_between_the_check_and_the_close_closes_nothing(self):
        self.comic('Late.cbz')
        self.save()
        real = folder_help._inspect

        def pause_during(*args):
            found = real(*args)
            self.paused = True
            return found
        with patch.object(folder_help, '_inspect', side_effect=pause_during):
            self.refused(lambda: folder_help.check(TICKET), 'paused')
        self.assertEqual(self.ticket()['state'], 'needs_attention')


class DeleteBackupTests(Fixture):
    def offered(self):
        result = folder_help.check(TICKET)
        self.assertIn('offer', result, result)
        return [b['id'] for b in result['offer']['backups']]

    def test_deletes_exactly_the_offered_backups_then_requeues(self):
        first, second = self.comic('One.cbz'), self.comic('Two.cbz')
        backups = [self.backup(first), self.backup(second)]
        unrelated = self.backup(self.folder / 'Not in plan.cbz', data=b'other')
        self.save()
        ids = self.offered()
        comics = {p.name: p.read_bytes() for p in (first, second)}
        self.assertEqual(folder_help.delete_backups(TICKET, ids), {'ok': True, 'unwritten': 2, 'written': 0, 'deleted': 2})
        self.assertEqual([p.exists() for p in backups], [False, False])
        self.assertTrue(unrelated.exists())
        self.assertEqual({p.name: p.read_bytes() for p in (first, second)}, comics)
        self.assertEqual(self.ticket()['state'], 'closed')

    def test_a_comic_changed_between_check_and_click_deletes_nothing(self):
        path = self.comic('Changed.cbz')
        backup = self.backup(path)
        self.save()
        ids = self.offered()
        path.write_bytes(path.read_bytes().replace(b'aaaa', b'aaab'))
        os.utime(path, ns=(MTIME, MTIME))  # Same size, same mtime, one byte different.
        exc = self.refused(lambda: folder_help.delete_backups(TICKET, ids), 'changed')
        self.assertTrue(backup.exists())
        check = exc.payload()['check']
        self.assertEqual([r['finding'] for r in check['problems']], ['unwritten_changed', 'backup_left'])
        self.assertNotIn('offer', check)
        self.assertEqual(self.ticket()['state'], 'needs_attention')

    def test_proved_again_under_the_guard_right_before_the_delete(self):
        path = self.comic('Raced.cbz')
        backup = self.backup(path)
        self.save()
        ids = self.offered()
        real = kept_backups.delete_one

        def change_then_delete(target, before_unlink=None):
            path.write_bytes(path.read_bytes().replace(b'aaaa', b'aaab'))
            os.utime(path, ns=(MTIME, MTIME))
            return real(target, before_unlink=before_unlink)
        with patch.object(kept_backups, 'delete_one', side_effect=change_then_delete):
            self.refused(lambda: folder_help.delete_backups(TICKET, ids), 'changed')
        self.assertTrue(backup.exists())

    def test_a_backup_that_appeared_after_the_check_is_kept(self):
        path = self.comic('Late backup.cbz')
        offered = self.backup(path)
        self.save()
        ids = self.offered()
        late = self.backup(path, ns=1_770_000_000_000_000_000)
        exc = self.refused(lambda: folder_help.delete_backups(TICKET, ids), 'not_requeued')
        payload = exc.payload()
        self.assertEqual((payload['deleted'], payload['reason'], payload['check']['total']), (1, 'problems', 1))
        self.assertFalse(offered.exists())
        self.assertTrue(late.exists())
        self.assertEqual(self.ticket()['state'], 'needs_attention')

    def test_a_failed_delete_stops_the_loop_and_reports_the_counts(self):
        paths = [self.comic(name) for name in ('A.cbz', 'B.cbz', 'C.cbz')]
        backups = [self.backup(p) for p in paths]
        self.save()
        ids = self.offered()
        real, calls = kept_backups._unlink, []

        def locked_second(target):
            calls.append(target)
            if len(calls) == 2:
                raise PermissionError('in use')
            return real(target)
        with patch.object(kept_backups, '_unlink', side_effect=locked_second):
            exc = self.refused(lambda: folder_help.delete_backups(TICKET, ids), 'delete_failed')
        self.assertEqual((exc.payload()['deleted'], exc.payload()['total']), (1, 3))
        self.assertEqual([b.exists() for b in backups], [False, True, True])
        self.assertEqual(self.ticket()['state'], 'needs_attention')

    def test_pause_after_the_delete_reports_not_requeued(self):
        path = self.comic('Paused.cbz')
        self.backup(path)
        self.save()
        ids = self.offered()
        real = kept_backups.delete_one

        def delete_then_pause(*args, **kwargs):
            freed = real(*args, **kwargs)
            self.paused = True
            return freed
        with patch.object(kept_backups, 'delete_one', side_effect=delete_then_pause):
            payload = self.refused(lambda: folder_help.delete_backups(TICKET, ids), 'not_requeued').payload()
        self.assertEqual((payload['deleted'], payload['reason']), (1, 'paused'))
        self.assertEqual(self.ticket()['state'], 'needs_attention')

    def test_only_ids_this_check_issued_for_this_ticket(self):
        path = self.comic('Ids.cbz')
        backup = self.backup(path)
        self.save()
        ids = self.offered()
        for bad in (ids + ids, [], ['../x'], [str(backup)], 'abc', [1]):
            with self.subTest(bad=bad):
                self.refused(lambda: folder_help.delete_backups(TICKET, bad), 'invalid')
        self.refused(lambda: folder_help.delete_backups(TICKET, ['f' * 32]), 'changed')  # Well formed, never issued.
        self.assertTrue(backup.exists())


class RevealTests(Fixture):
    def test_open_folder_and_show_in_folder_by_id(self):
        path = self.comic('Shown.cbz')
        gone = self.comic('Gone.cbz')
        gone.unlink()
        backup = self.backup(path)
        self.save()
        rows = {r['finding']: r['id'] for r in folder_help.check(TICKET)['problems']}
        self.assertEqual(folder_help.reveal(TICKET), {'ok': True})
        self.open_folder.assert_called_with(str(self.folder))
        folder_help.reveal(TICKET, rows['backup_left'])
        self.select.assert_called_with(str(backup.resolve()))
        folder_help.reveal(TICKET, rows['missing'])
        self.open_folder.assert_called_with(str(self.folder))
        self.select.side_effect = OSError('too long')
        folder_help.reveal(TICKET, rows['backup_left'])  # Over MAX_PATH: its folder opens instead.
        self.open_folder.assert_called_with(str(self.folder / '.comic-metadata-backups'))
        self.open_folder.side_effect = OSError('no shell')
        self.refused(lambda: folder_help.reveal(TICKET, rows['backup_left']), 'failed')
        self.open_folder.side_effect = None
        backup.unlink()
        self.refused(lambda: folder_help.reveal(TICKET, rows['backup_left']), 'not_found')
        self.refused(lambda: folder_help.reveal(TICKET, 'f' * 32), 'not_found')
        self.paused = True
        self.assertEqual(folder_help.reveal(TICKET), {'ok': True})  # Allowed while paused.
        os.rename(self.folder, self.library / 'moved')
        self.refused(lambda: folder_help.reveal(TICKET), 'folder_unavailable')
        os.rename(self.library / 'moved', self.folder)
        self.save(state='complete')
        self.refused(lambda: folder_help.reveal(TICKET), 'gone')


class RouteTests(Fixture):
    def handler(self, path, body):
        item = object.__new__(app.Handler)
        item.server = SimpleNamespace(server_port=8765, setup_required=False)
        item.path = path
        raw = json.dumps(body).encode()
        item.headers = {'Host': '127.0.0.1:8765', 'Origin': 'http://127.0.0.1:8765', 'Content-Length': str(len(raw))}
        item.rfile = io.BytesIO(raw)
        replies = []
        item.respond = lambda payload, status=200, mime='application/json': replies.append((status, payload))
        item.do_POST()
        return replies[-1]

    def test_ids_only_paused_refused_by_the_server_and_reveal_allowed(self):
        path = self.comic('Route.cbz')
        backup = self.backup(path)
        self.save()
        for route, body in (('/api/attention/check', {'ticket': TICKET, 'path': str(self.folder)}),
                            ('/api/attention/check', {'folder': str(self.folder)}),
                            ('/api/attention/close', {'ticket': TICKET, 'plan': 'x'}),
                            ('/api/attention/delete-backups', {'ticket': TICKET, 'backups': [str(backup)]}),
                            ('/api/attention/delete-backups', {'ticket': TICKET, 'paths': [str(backup)]}),
                            ('/api/attention/reveal', {'ticket': TICKET, 'path': str(backup)}),
                            ('/api/attention/check', {'ticket': str(worker.QUEUE / TICKET)})):
            status, reply = self.handler(route, body)
            self.assertEqual(status, 400, (route, body))
            self.assertIn(reply['code'], ('invalid', 'gone'), (route, body))
        self.assertTrue(backup.exists())
        self.assertEqual(self.ticket()['state'], 'needs_attention')
        self.paused = True
        status, reply = self.handler('/api/attention/check', {'ticket': TICKET})
        self.assertEqual((status, reply['code']), (400, 'paused'))
        self.assertEqual(self.handler('/api/attention/reveal', {'ticket': TICKET}), (200, {'ok': True}))
        self.paused = False
        status, reply = self.handler('/api/attention/check', {'ticket': TICKET})
        self.assertEqual((status, reply['code'], reply['offer']['kind']), (200, 'problems', 'delete_backup'))
        ids = [b['id'] for b in reply['offer']['backups']]
        self.paused = True
        status, reply = self.handler('/api/attention/delete-backups', {'ticket': TICKET, 'backups': ids})
        self.assertEqual((status, reply['code']), (400, 'paused'))
        self.assertTrue(backup.exists())
        self.paused = False
        status, reply = self.handler('/api/attention/delete-backups', {'ticket': TICKET, 'backups': ids})
        self.assertEqual((status, reply), (200, {'ok': True, 'unwritten': 1, 'written': 0, 'deleted': 1}))
        self.assertFalse(backup.exists())


if __name__ == '__main__':
    unittest.main()
