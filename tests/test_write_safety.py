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

F29: a write that fails after the backup step (a page with a bad CRC, a replace
refused because the comic is open elsewhere) removes the backup it made, and only
that one, once the archive is confirmed to hold the planned bytes. Repeated failures
on one unchanged archive wait 1, 2, 4 and 7 days, then automatic retries stop until
the archive changes.

Isolated catalog, queue and archives; every source is mocked.
"""
import json
import os
import sqlite3
import time
import unittest
import warnings
import zipfile
from contextlib import ExitStack, contextmanager
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


def damaged_comic(path):
    """Page 002 fails its CRC check. The folder scan reads only ComicInfo, so the catalog
    lists this comic like any other; its write fails after the backup step (F29)."""
    page = b'page' * 100 + path.name.encode()
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_STORED) as archive:
        archive.writestr('001.jpg', b'cover ' + path.name.encode())
        archive.writestr('002.jpg', page)
    data = bytearray(path.read_bytes())
    data[data.find(page) + 10] ^= 0xFF
    path.write_bytes(bytes(data))
    return path


def discovery_record(path):
    with app.db() as con:
        return json.loads(con.execute('SELECT value FROM discovery_records WHERE path=?', (str(path),)).fetchone()[0])


class Clock:
    """time.time moved forward by a virtual offset."""

    def __init__(self):
        self.offset = 0.0
        self.real = time.time

    def time(self):
        return self.real() + self.offset


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


class FailedWriteBackupTests(Isolated):
    """F29."""

    def copies_of(self, name, made, after=None):
        """shutil.copy2 that notes each backup of the comic `name` (the backup step ran)."""
        real = app.shutil.copy2

        def copy2(src, dst, *args, **kwargs):
            result = real(src, dst, *args, **kwargs)
            if Path(src).name == name:
                made.append(Path(dst))
                if after:
                    after(Path(dst))
            return result
        return patch.object(app.shutil, 'copy2', side_effect=copy2)

    def test_a_failed_write_removes_only_the_backup_it_made(self):
        # Senua's probe T6, with older backups beside it. Before: the failed attempt's full copy stayed.
        paths = [make_comic(self.folder / 'Example 001.cbz'), damaged_comic(self.folder / 'Example 002.cbz'),
                 make_comic(self.folder / 'Example 003.cbz')]
        app.scan([str(self.folder)], recursive=False)
        folder = self.folder / '.comic-metadata-backups'
        folder.mkdir()
        older = {'Example 002.cbz.1000.bak': b'an older backup of the damaged comic',
                 'Example 009.cbz.1000.bak': b'a backup of another comic'}
        for name, body in older.items():
            (folder / name).write_bytes(body)
        plan = self.plan([self.entry(path, {'Title': 'T ' + path.stem}, signature=[catalog_row(path)['size'], catalog_row(path)['mtime']])
                          for path in paths])
        made = []
        with self.copies_of('Example 002.cbz', made):
            batch.apply(plan, remove_verified_backups=True)
        self.assertEqual([app.read_metadata(path)[0].get('Title') for path in paths], ['T Example 001', None, 'T Example 003'])
        self.assertEqual(len(made), 1)  # The failure came after the backup step: the case F29 is about.
        # Only this attempt's backup is gone; every other one is untouched, byte for byte,
        # including an older backup of the same comic.
        self.assertFalse(made[0].exists())
        self.assertEqual({p.name: p.read_bytes() for p in folder.iterdir()}, older)
        failed = json.loads((plan.parent / 'failed.json').read_text(encoding='utf-8'))
        self.assertEqual([Path(f['path']).name for f in failed], ['Example 002.cbz'])
        self.assertIn('Bad CRC-32', failed[0]['reason'])
        self.assertEqual(Path(failed[0]['backup']).name, made[0].name)
        self.assertTrue(failed[0]['backup_removed_after_verification'])

    def test_a_damaged_comic_backs_off_then_stops_and_leaves_no_backup(self):
        # Senua's probe T7 over 30 virtual days. Before: planned again every day, one full backup left per attempt.
        good = make_comic(self.folder / 'Example 001.cbz')
        bad = damaged_comic(self.folder / 'Example 002.cbz')
        app.scan([str(self.folder)], recursive=False)
        for path, issue in ((good, '1'), (bad, '2')):
            row = catalog_row(path)
            research.save_evidence(path, {'cover_identification': {'title': 'EXAMPLE', 'issue': issue},
                                          'cover_signature': [row['size'], row['mtime']]})
        clock = Clock()
        made, present = [], []
        backup_folder = self.folder / '.comic-metadata-backups'
        passes = 0
        with ExitStack() as stack:
            self.mock_sources(stack)
            stack.enter_context(patch.object(time, 'time', clock.time))
            stack.enter_context(self.copies_of(bad.name, made, after=lambda dst: present.append(len(list(backup_folder.iterdir())))))
            attempts = []
            while clock.offset < 30 * 86400:  # A folder pass every 6 hours.
                before = len(made)
                automatic.discover(self.folder)
                while worker.run_one():
                    pass
                if len(made) > before:
                    attempts.append(clock.offset)
                present.append(len(backups(self.folder)))
                clock.offset += 6 * 3600
                passes += 1
            now = clock.time()
        self.assertEqual(passes, 120)
        self.assertTrue(app.read_metadata(good)[0])  # The good comic was written as usual.
        self.assertEqual(backups(self.folder), [])
        self.assertLessEqual(max(present), 1)  # At most one backup at any moment: the attempt's own, while it runs.
        gaps = [round((later - earlier) / 86400, 2) for earlier, later in zip(attempts, attempts[1:])]
        self.assertEqual(gaps, [1, 2, 4, 7])  # Five attempts, then none for the last 16 days.
        record = discovery_record(bad)
        self.assertEqual(record['outcome'], 'write_failed')
        self.assertEqual((record['write_failures']['count'], record['write_failures']['stopped']), (5, True))
        self.assertTrue(record['detail'].startswith('Automatic writes stopped after 5 failed attempts on this unchanged archive.'))
        self.assertIn('Bad CRC-32', record['detail'])
        held = [t for t in map(lambda p: json.loads(p.read_text(encoding='utf-8')), worker.QUEUE.glob('*.json'))
                if any(Path(e['path']).name == bad.name for e in json.loads(Path(t['plan']).read_text(encoding='utf-8'))['entries'])]
        self.assertEqual([t['state'] for t in held], ['complete'] * 5)
        # Stopped for good on this archive; due again at once when the archive changes.
        row = catalog_row(bad)
        saved = coverage_priority.saved_evidence(bad)
        with patch.object(pipeline_config, 'in_book_cover', return_value=True):
            self.assertTrue(in_book.ready(row, saved, record))
            self.assertFalse(coverage_priority.lookup_flags(row, record, {}, automatic.MATCHER_VERSION, saved, now + 365 * 86400)[0])
            changed = dict(row, mtime=row['mtime'] + 1)
            self.assertTrue(coverage_priority.lookup_flags(changed, record, {}, automatic.MATCHER_VERSION, saved, now)[0])

    def mock_sources(self, stack):
        import archive_conversion, cover_tasks, getcomics, local_model, metron, open_library, publisher_catalogs, research_runtime
        for target, name, kwargs in (
                (archive_conversion, 'one', {'return_value': False}), (providers, 'statuses', {'return_value': {}}),
                (research_runtime, 'reuse', {'return_value': None}), (research_runtime, 'remember', {}),
                (automatic, 'lookup_unidentified', {'return_value': None}), (app, 'api', {'return_value': None}),
                (metron, 'token', {'return_value': None}), (providers, 'gcd_lookup', {'return_value': None}),
                (providers, 'google_lookup', {'return_value': None}), (open_library, 'lookup', {'return_value': None}),
                (publisher_catalogs, 'lookup', {'return_value': None}), (getcomics, 'lookup', {'return_value': None}),
                (research, 'publisher_lookup', {'return_value': None}), (research, 'resolve_leads', {'return_value': None}),
                (research, 'general_lookup', {'return_value': None}), (research, 'wiki_candidates', {'return_value': []}),
                (cover_tasks, 'enqueue', {}), (local_model, 'available', {'return_value': False}),
                (pipeline_config, 'in_book_cover', {'return_value': True})):
            stack.enter_context(patch.object(target, name, **kwargs))

    def test_failed_writes_wait_longer_then_stop_until_the_archive_changes(self):
        path = make_comic(self.folder / 'Example 002.cbz')
        app.scan([str(self.folder)], recursive=False)
        row = catalog_row(path)
        signature = [row['size'], row['mtime']]
        planned = {'version': automatic.MATCHER_VERSION, 'signature': signature, 'outcome': 'queued', 'tier': 'in_book',
                   'retry_at': time.time() + 30 * 86400}
        now = time.time()
        waits = []
        for attempt in range(1, discovery_state.WRITE_FAILED_LIMIT + 1):
            discovery_state.save_one(path, dict(planned))  # The pass that plans the comic again.
            self.assertTrue(discovery_state.write_not_done(path, 'write_failed', "Bad CRC-32 for file '002.jpg'", now=now))
            record = discovery_record(path)
            self.assertEqual(record['write_failures']['count'], attempt)
            self.assertEqual(record['write_failures']['stopped'], attempt == discovery_state.WRITE_FAILED_LIMIT)
            if attempt == 1:
                self.assertTrue(record['detail'].startswith("Write failed (attempt 1 of 5 on this archive): Bad CRC-32 for file '002.jpg'."))
                self.assertIn('Next attempt in 1 day,', record['detail'])
            if attempt < discovery_state.WRITE_FAILED_LIMIT:
                waits.append((record['retry_at'] - now) / 86400)
                now = record['retry_at'] + 1
            if attempt == 2:
                # A skipped write (ComicInfo changed, signature kept) waits a day and is not counted as a failure.
                discovery_state.write_not_done(path, 'write_skipped', 'ComicInfo changed since planning (Series); nothing written.', now=now)
                skipped = discovery_record(path)
                self.assertEqual((skipped['write_failures']['count'], skipped['retry_at'] - now), (2, discovery_state.WRITE_RETRY_SECONDS))
        self.assertEqual(waits, [1, 2, 4, 7])
        self.assertTrue(record['write_failures']['stopped'])
        self.assertEqual(record['retry_at'], 0)
        self.assertIn('It is tried again once the file changes', record['detail'])
        self.assertEqual(discovery_state.counts(self.folder), {'write_failed': 1})  # Still valid JSON for the dashboard counts.
        reading = {'cover_identification': {'title': 'Example', 'issue': '2'}, 'cover_signature': signature}
        with patch.object(pipeline_config, 'in_book_cover', return_value=True):
            self.assertTrue(in_book.ready(row, reading, record))  # The saved reading alone would make it due at once.
            flags = lambda at, at_row=row: coverage_priority.lookup_flags(at_row, record, {}, automatic.MATCHER_VERSION, reading, at)[0]
            self.assertFalse(flags(now + 365 * 86400))
            changed = dict(row, mtime=row['mtime'] + 1)
            self.assertTrue(flags(now, changed))
        # A pass on the changed archive starts a new run.
        discovery_state.save_one(path, dict(planned, signature=[row['size'], row['mtime'] + 1]))
        self.assertNotIn('write_failures', discovery_record(path))
        discovery_state.write_not_done(path, 'write_failed', 'Bad CRC-32', now=now)
        record = discovery_record(path)
        self.assertEqual((record['write_failures']['count'], record['retry_at'] - now), (1, 86400))

    def test_a_successful_write_keeps_its_normal_backup_chain(self):
        # Positive control: the F29 cleanup never reaches a written comic's backup.
        kept, cleaned = make_comic(self.folder / 'Example 001.cbz'), make_comic(self.folder / 'Example 002.cbz')
        app.scan([str(self.folder)], recursive=False)
        original = kept.read_bytes()
        plan = self.plan([self.entry(kept, {'Title': 'Kept'})])
        batch.apply(plan)  # `batch.py apply` without --remove-verified-backups keeps verified backups.
        result = json.loads((plan.parent / 'results.json').read_text(encoding='utf-8'))[0]
        backup = Path(result['backup'])
        self.assertEqual(backup.read_bytes(), original)
        self.assertEqual((result['backup_sha256_verified'], result['backup_removed_after_verification']), (True, False))
        with app.db() as con:
            self.assertEqual([r[0] for r in con.execute('SELECT backup FROM history')], [result['backup']])
        # The worker's mode: the backup is removed only after readback and the SHA-256 check.
        plan = self.plan([self.entry(cleaned, {'Title': 'Cleaned'})])
        batch.apply(plan, remove_verified_backups=True)
        result = json.loads((plan.parent / 'results.json').read_text(encoding='utf-8'))[0]
        self.assertTrue(result['backup_removed_after_verification'])
        self.assertFalse(Path(result['backup']).exists())
        self.assertEqual(backups(self.folder), [backup.name])
        self.assertEqual([app.read_metadata(p)[0]['Title'] for p in (kept, cleaned)], ['Kept', 'Cleaned'])

    def test_a_failure_after_the_archive_was_replaced_keeps_its_backup(self):
        # Senua's probe T9: the catalog is locked after os.replace. The backup is now the only copy of the original.
        paths = [make_comic(self.folder / ('Example %03d.cbz' % i)) for i in (1, 2)]
        app.scan([str(self.folder)], recursive=False)
        original = paths[0].read_bytes()
        plan = self.plan([self.entry(path, {'Title': 'T ' + path.stem}) for path in paths])
        real_db, locked = app.db, []

        @contextmanager
        def db():
            with real_db() as con:
                class Locked:
                    def __getattr__(self, name):
                        return getattr(con, name)

                    def execute(self, sql, *args):
                        if sql.startswith('UPDATE comics SET size=?,mtime=?,metadata=?') and not locked:
                            locked.append(True)
                            raise sqlite3.OperationalError('database is locked')
                        return con.execute(sql, *args)
                yield Locked()
        with patch.object(app, 'db', db), self.assertRaisesRegex(sqlite3.OperationalError, 'locked'):
            batch.apply(plan, remove_verified_backups=True)
        self.assertEqual(locked, [True])
        self.assertEqual(app.read_metadata(paths[0])[0]['Title'], 'T Example 001')  # The archive was replaced.
        names = backups(self.folder)
        self.assertEqual(len(names), 1)
        self.assertEqual((self.folder / '.comic-metadata-backups' / names[0]).read_bytes(), original)
        self.assertEqual(self.recorded(plan, 'failed.json'), [])
        self.assertNotIn('Title', app.read_metadata(paths[1])[0])  # The plan stopped for inspection.

    def test_a_failure_on_an_archive_changed_by_another_program_keeps_its_backup(self):
        # The replace is refused after another program rewrote the comic: it no longer holds the planned bytes.
        path = make_comic(self.folder / 'Spawn 001 (1992).cbz')
        app.scan([str(self.folder)], recursive=False)
        original = path.read_bytes()
        plan = self.plan([self.entry(path, {'Title': 'Mine'})])
        real_replace = os.replace

        def replace(src, dst, *args, **kwargs):
            if Path(dst).name == path.name:
                make_comic(path, SERGEI)
                raise PermissionError(32, 'The process cannot access the file because it is being used by another process')
            return real_replace(src, dst, *args, **kwargs)
        with patch.object(app.os, 'replace', side_effect=replace), self.assertRaises(PermissionError):
            batch.apply(plan, remove_verified_backups=True)
        self.assertEqual(app.read_metadata(path)[0]['Series'], 'Spawn (Sergei)')
        names = backups(self.folder)
        self.assertEqual(len(names), 1)
        self.assertEqual((self.folder / '.comic-metadata-backups' / names[0]).read_bytes(), original)
        self.assertEqual(self.recorded(plan, 'failed.json'), [])

    def test_a_refused_replace_on_an_unchanged_archive_removes_its_backup(self):
        # Senua's probe T8: another program holds the comic open, so Windows refuses the replace.
        paths = [make_comic(self.folder / ('Example %03d.cbz' % i)) for i in (1, 2)]
        app.scan([str(self.folder)], recursive=False)
        plan = self.plan([self.entry(path, {'Title': 'T ' + path.stem}) for path in paths])
        real_replace = os.replace

        def replace(src, dst, *args, **kwargs):
            if Path(dst).name == paths[0].name:
                raise PermissionError(32, 'The process cannot access the file because it is being used by another process')
            return real_replace(src, dst, *args, **kwargs)
        made = []
        with patch.object(app.os, 'replace', side_effect=replace), self.copies_of(paths[0].name, made):
            batch.apply(plan, remove_verified_backups=True)
        self.assertEqual(len(made), 1)
        self.assertEqual([app.read_metadata(path)[0].get('Title') for path in paths], [None, 'T Example 002'])
        self.assertEqual(self.recorded(plan, 'failed.json'), ['Example 001.cbz'])
        self.assertEqual(backups(self.folder), [])

    def test_a_backup_that_does_not_match_the_planned_digest_is_kept(self):
        # The cleanup removes a backup only when its SHA-256 is the planned digest.
        path = damaged_comic(self.folder / 'Example 002.cbz')
        app.scan([str(self.folder)], recursive=False)
        plan = self.plan([self.entry(path, {'Title': 'T'})])
        made = []
        with self.copies_of(path.name, made, after=lambda dst: dst.write_bytes(dst.read_bytes() + b'!')):
            batch.apply(plan, remove_verified_backups=True)
        failed = json.loads((plan.parent / 'failed.json').read_text(encoding='utf-8'))
        self.assertIn('Backup kept: Backup verification failed.', failed[0]['reason'])
        self.assertFalse(failed[0]['backup_removed_after_verification'])
        self.assertEqual(backups(self.folder), [made[0].name])


if __name__ == '__main__':
    unittest.main()
