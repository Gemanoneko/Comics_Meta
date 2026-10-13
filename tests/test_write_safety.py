"""v0.1.3 review F22, F23 and F27: what a multi-comic plan does when an archive is not as planned.

F22: a ComicInfo edit made after the folder scan (for example in another tagger
while the pass runs) is never overwritten; the comic is skipped and nothing of
it is deleted. Two guards, each tested on its own: the archive must match the
scan's signature, and its ComicInfo must still hold every planned "before" value
when it is read for the write.

F23: one archive that cannot be written no longer strands the rest of its plan.
It is recorded, the others are written, and it is offered again after the daily
retry. An archive that may have been written but did not verify still stops the
plan for inspection with its backup kept.

Isolated catalog, queue and archives; every source is mocked.
"""
import json
import time
import unittest
import warnings
import zipfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
import app
import automatic
import batch
import coverage_priority
import discovery_state
import in_book
import pipeline_config
import providers
import research
import worker
from test_worker import scratch_directory

SERGEI = '<?xml version="1.0"?><ComicInfo><Series>Spawn (Sergei)</Series><Number>1</Number></ComicInfo>'


def make_comic(path, comicinfo=None, duplicate=False):
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('001.jpg', b'cover ' + path.name.encode())
        archive.writestr('002.jpg', b'page' * 100)
        if duplicate:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)  # zipfile warns about the duplicate this fixture needs.
                archive.writestr('002.jpg', b'a second entry with the same name')
        if comicinfo:
            archive.writestr('ComicInfo.xml', comicinfo)
    return path


def rewrite(path, comicinfo):
    """Another program writes the archive: new content and a new modification time."""
    before = path.stat().st_mtime_ns
    while True:
        make_comic(path, comicinfo)
        if path.stat().st_mtime_ns != before:
            return path
        time.sleep(0.01)


def catalog_row(path):
    with app.db() as con:
        return dict(con.execute('SELECT * FROM comics WHERE path=?', (str(path),)).fetchone())


def backups(folder):
    return sorted(p.name for p in (folder / '.comic-metadata-backups').glob('*'))


class Isolated(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        for target, name, value in ((app, 'DATA', self.root / 'data'), (app, 'BASE', self.root),
                                    (research, 'CACHE', self.root / 'research'), (worker, 'QUEUE', self.root / 'queue')):
            self.enterContext(patch.object(target, name, value))
        (self.root / 'data').mkdir()
        (self.root / 'data' / 'progress.json').write_text('{"completed": []}', encoding='utf-8')
        self.enterContext(patch.object(worker.pause_control, 'requested', return_value=False))
        self.enterContext(patch.object(batch.pause_control, 'requested', return_value=False))
        self.enterContext(patch.object(batch, 'progress'))
        self.folder = self.root / 'Spawn'
        self.folder.mkdir()

    def plan(self, entries):
        target = self.root / 'batches' / str(time.time_ns()) / 'plan.json'
        target.parent.mkdir(parents=True)
        target.write_text(json.dumps({'folder': str(self.folder), 'method': 'test', 'entries': entries}), encoding='utf-8')
        return target

    def entry(self, path, changes, signature=None):
        entry = {'path': str(path), 'action': 'write', 'sha256': batch.digest(path), 'method': 'test',
                 'changes': {k: {'before': '', 'after': v} for k, v in changes.items()}, 'fields': dict(changes)}
        if signature is not None:
            entry['signature'] = signature
        return entry

    def recorded(self, plan, name):
        target = plan.parent / name
        return [Path(item['path']).name for item in json.loads(target.read_text(encoding='utf-8'))] if target.exists() else []


class EditDuringPassTests(Isolated):
    """F22."""

    def discover_with_edit(self, path):
        """One in-book pass in which Sergei tags the comic in another program after the folder scan."""
        import archive_conversion, cover_tasks, local_model
        real = in_book.identify
        edited = []

        def identify(*args, **kwargs):
            book = real(*args, **kwargs)
            if book and not edited:
                rewrite(path, SERGEI)
                edited.append(True)
            return book
        with ExitStack() as stack:
            for target, name, kwargs in ((pipeline_config, 'in_book_cover', {'return_value': True}),
                                         (providers, 'statuses', {'return_value': {}}),
                                         (archive_conversion, 'one', {'return_value': False}),
                                         (local_model, 'available', {'return_value': False}),
                                         (cover_tasks, 'identified', {}),
                                         (in_book, 'identify', {'side_effect': identify})):
                stack.enter_context(patch.object(target, name, **kwargs))
            for target, name in ((app, 'api'), (automatic, 'lookup_unidentified'), (research, 'publisher_lookup'),
                                 (research, 'resolve_leads'), (research, 'general_lookup'), (research, 'wiki_candidates')):
                stack.enter_context(patch.object(target, name, side_effect=AssertionError('no source call')))
            queued = automatic.discover(self.folder)
        self.assertEqual(edited, [True])
        return queued

    def test_an_edit_made_after_the_folder_scan_is_kept_and_its_comic_skipped(self):
        # Senua's probe P2. Before: Series became "Spawn", the ticket completed and no backup was left.
        path = make_comic(self.folder / 'Spawn 001 (1992).cbz')
        app.scan([str(self.folder)], recursive=False)
        row = catalog_row(path)
        research.save_evidence(path, {'cover_identification': {'title': 'SPAWN', 'issue': '1'},
                                      'cover_signature': [row['size'], row['mtime']]})
        self.assertTrue(self.discover_with_edit(path))
        ticket = next(worker.QUEUE.glob('*.json'))
        plan = Path(json.loads(ticket.read_text(encoding='utf-8'))['plan'])
        self.assertTrue(worker.run_one())
        self.assertEqual(app.read_metadata(path)[0].get('Series'), 'Spawn (Sergei)')
        self.assertEqual(json.loads(ticket.read_text(encoding='utf-8'))['state'], 'complete')
        self.assertEqual(json.loads(plan.read_text(encoding='utf-8'))['entries'][0]['signature'], [row['size'], row['mtime']])
        self.assertEqual(self.recorded(plan, 'skipped.json'), [path.name])
        self.assertEqual(self.recorded(plan, 'results.json'), [])
        with app.db() as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM history').fetchone()[0], 0)
            record = json.loads(con.execute('SELECT value FROM discovery_records WHERE path=?', (str(path),)).fetchone()[0])
        self.assertEqual(record['outcome'], 'write_skipped')
        # The archive changed, so the comic is due again and judged from what it holds now.
        app.scan([str(self.folder)], recursive=False)
        fresh = catalog_row(path)
        self.assertTrue(coverage_priority.lookup_flags(fresh, record, {}, automatic.MATCHER_VERSION,
                                                       coverage_priority.saved_evidence(path), time.time())[0])

    def test_signature_guard_skips_an_archive_changed_after_the_scan(self):
        # The edit touches another field, so only the scan signature can tell.
        path = make_comic(self.folder / 'Spawn 001 (1992).cbz')
        app.scan([str(self.folder)], recursive=False)
        row = catalog_row(path)
        rewrite(path, '<?xml version="1.0"?><ComicInfo><Title>Sergei title</Title></ComicInfo>')
        plan = self.plan([self.entry(path, {'Series': 'Spawn'}, signature=[row['size'], row['mtime']])])
        batch.apply(plan, remove_verified_backups=True)
        metadata = app.read_metadata(path)[0]
        self.assertNotIn('Series', metadata)  # Before: written, because the digest was taken after the edit.
        self.assertEqual(metadata['Title'], 'Sergei title')
        self.assertEqual(self.recorded(plan, 'skipped.json'), [path.name])
        self.assertEqual(backups(self.folder), [])

    def test_comicinfo_guard_keeps_a_field_filled_since_planning(self):
        # No scan signature (a plan written before this guard); the digest is the edited archive's.
        path = rewrite(make_comic(self.folder / 'Spawn 001 (1992).cbz'), SERGEI)
        app.scan([str(self.folder)], recursive=False)
        plan = self.plan([self.entry(path, {'Series': 'Spawn', 'Number': '1'})])
        batch.apply(plan, remove_verified_backups=True)
        self.assertEqual(app.read_metadata(path)[0]['Series'], 'Spawn (Sergei)')  # Before: overwritten with "Spawn".
        skipped = json.loads((plan.parent / 'skipped.json').read_text(encoding='utf-8'))
        self.assertIn('ComicInfo changed since planning (Number, Series)', skipped[0]['reason'])
        self.assertEqual(backups(self.folder), [])

    def test_write_metadata_checks_expected_values_before_any_backup(self):
        path = make_comic(self.folder / 'Spawn 001 (1992).cbz', SERGEI)
        app.scan([str(self.folder)], recursive=False)
        original = path.read_bytes()
        with self.assertRaises(app.ArchiveChanged):
            app.write_metadata(catalog_row(path), {'Series': 'Spawn'}, overwrite_fields={'Series'}, expected={'Series': ''})
        self.assertEqual(path.read_bytes(), original)
        self.assertFalse((self.folder / '.comic-metadata-backups').exists())
        # Positive control: the value the plan expected is still there, so the write goes ahead.
        app.write_metadata(catalog_row(path), {'Series': 'Spawn'}, overwrite_fields={'Series'}, expected={'Series': 'Spawn (Sergei)'},
                           remove_verified_backups=True)
        self.assertEqual(app.read_metadata(path)[0]['Series'], 'Spawn')

    def test_history_source_is_written_with_the_history_row(self):
        # F27: provenance no longer depends on a second transaction after the write commits.
        path = make_comic(self.folder / 'Spawn 001 (1992).cbz')
        app.scan([str(self.folder)], recursive=False)
        app.write_metadata(catalog_row(path), {'Series': 'Spawn'}, history_source='in-book:cover', remove_verified_backups=True)
        with app.db() as con:
            self.assertEqual([r[0] for r in con.execute('SELECT source FROM history')], ['in-book:cover'])


class FailingArchiveTests(Isolated):
    """F23."""

    def test_one_failing_archive_does_not_strand_the_rest_and_is_retried_daily(self):
        # Senua's probe P1. Before: the ticket needed attention and the comics after the failure were never written.
        paths = [make_comic(self.folder / ('Example %03d.cbz' % i), duplicate=(i == 2)) for i in (1, 2, 3, 4)]
        app.scan([str(self.folder)], recursive=False)
        (self.folder / 'Example 003.cbz.metadata-tmp').write_bytes(b'left over from an interrupted write')
        plan = automatic.PassPlan(self.folder)
        for path in paths:
            row = catalog_row(path)
            plan.add(path, {'Title': {'before': '', 'after': 'T ' + path.stem}}, {'Title': 'T ' + path.stem}, 'test',
                     signature=[row['size'], row['mtime']])
            discovery_state.save_one(path, {'version': automatic.MATCHER_VERSION, 'signature': [row['size'], row['mtime']],
                                            'outcome': 'queued', 'tier': 'in_book', 'retry_at': time.time() + 30 * 86400})
        ticket = next(worker.QUEUE.glob('*.json'))
        self.assertTrue(worker.run_one())
        self.assertEqual(json.loads(ticket.read_text(encoding='utf-8'))['state'], 'complete')
        titles = [app.read_metadata(path)[0].get('Title') for path in paths]
        self.assertEqual(titles, ['T Example 001', None, None, 'T Example 004'])
        failed = json.loads((plan.target.parent / 'failed.json').read_text(encoding='utf-8'))
        self.assertEqual([Path(f['path']).name for f in failed], ['Example 002.cbz', 'Example 003.cbz'])
        self.assertIn('Duplicate ZIP entries', failed[0]['reason'])
        self.assertIn('temporary file already exists', failed[1]['reason'])
        self.assertEqual(backups(self.folder), [])  # Written comics verified and cleaned; nothing backed up for the failures.
        # Recorded, out of the pending set, and offered again after the daily retry, not at every pass.
        self.assertNotIn(coverage_priority.path_key(paths[1]), coverage_priority.pending_paths())
        now = time.time()
        with app.db() as con:
            record = json.loads(con.execute('SELECT value FROM discovery_records WHERE path=?', (str(paths[1]),)).fetchone()[0])
        self.assertEqual(record['outcome'], 'write_failed')
        self.assertAlmostEqual(record['retry_at'] - now, discovery_state.WRITE_RETRY_SECONDS, delta=60)
        row = catalog_row(paths[1])
        reading = {'cover_identification': {'title': 'Example', 'issue': '2'}, 'cover_signature': [row['size'], row['mtime']]}
        with patch.object(pipeline_config, 'in_book_cover', return_value=True):
            self.assertTrue(in_book.ready(row, reading, record))  # The saved reading alone would make it due at once.
            flags = lambda at: coverage_priority.lookup_flags(row, record, {}, automatic.MATCHER_VERSION, reading, at)[0]
            self.assertFalse(flags(now))
            self.assertTrue(flags(now + discovery_state.WRITE_RETRY_SECONDS + 1))
            changed = dict(row, mtime=row['mtime'] + 1)  # A repaired archive is due at once.
            self.assertTrue(coverage_priority.lookup_flags(changed, record, {}, automatic.MATCHER_VERSION, reading, now)[0])

    def test_an_archive_that_may_be_written_but_did_not_verify_still_stops_the_plan(self):
        # The carve-out keeps v0.1.2's rule: never continue past an unverified write or remove its backup.
        paths = [make_comic(self.folder / ('Example %03d.cbz' % i)) for i in (1, 2)]
        app.scan([str(self.folder)], recursive=False)
        first = self.entry(paths[0], {'Title': 'Written'})
        first['changes']['Title']['after'] = 'Something else'  # The readback cannot match.
        plan = self.plan([first, self.entry(paths[1], {'Title': 'Second'})])
        with self.assertRaisesRegex(ValueError, 'Readback verification failed'):
            batch.apply(plan, remove_verified_backups=True)
        self.assertEqual(len(backups(self.folder)), 1)  # Kept for inspection.
        self.assertNotIn('Title', app.read_metadata(paths[1])[0])
        self.assertEqual(self.recorded(plan, 'failed.json'), [])


if __name__ == '__main__':
    unittest.main()
