"""In-book tier 1 (Sergei, 2026-10-12): a saved cover reading that agrees with the filename is enough.

Accuracy fixtures: cover and filename agree; disagree; an unnumbered book; a
collection whose cover carries an inner issue number; a previews or ad page as the
first image. Synthetic archives and readings only; no model, provider or network.
"""
import io
import json
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
import app
import automatic
import batch
import coverage_priority
import cover_tasks
import discovery_state
import in_book
import pipeline_config
import providers
import research
import worker
from test_worker import scratch_directory


def judge(name, hint, old=None, indicia=None):
    """indicia: a credits/indicia reading of the same pages (publisher agreement, Sergei 2026-10-13)."""
    row = {'path': 'Library/Series/' + name, 'size': 10, 'mtime': 1, 'metadata': json.dumps(old or {})}
    saved = {'cover_identification': hint, 'cover_signature': [10, 1]}
    if indicia is not None:
        saved.update(credits_reading={'indicia': indicia, 'credits': ''}, credits_signature=[10, 1])
    return in_book.identify(row, old or {}, saved)


class AccuracyFixtureTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(pipeline_config, 'in_book_cover', return_value=True))
        # The publisher rule is measured with its switch on; it is off by default (F21, ConfigSwitchTests).
        self.enterContext(patch.object(pipeline_config, 'in_book_publisher_agreement', return_value=True))
        # With it on, a reading from another signature is checked against the write ledger: an isolated catalog.
        self.enterContext(patch.object(app, 'DATA', Path(self.enterContext(scratch_directory())) / 'data'))

    def test_cover_and_filename_agree_writes_series_and_number_only(self):
        book = judge('Spawn 001 (1992) (digital).cbz', {'title': 'SPAWN', 'issue': '#1', 'publisher': 'Image Comics',
                                                        'creators': ['Todd McFarlane'], 'search_query': 'Spawn 1'},
                     indicia='SPAWN #1. Published by Image Comics, Inc.')
        self.assertEqual(book['fields'], {'Series': 'Spawn', 'Number': '1', 'Publisher': 'Image Comics'})
        self.assertEqual(book['evidence']['fields']['Series']['agreement'], 'exact')
        self.assertEqual(book['evidence']['not_taken_from_cover'], ['creators', 'year'])
        for title, issue in (('The Amazing Spider-Man', 'No. 129'), ('AMAZING SPIDER-MAN #129', ''), ('Amazing Spider-Man', '129 of 300')):
            self.assertEqual(judge('Amazing Spider-Man 129 (1974).cbz', {'title': title, 'issue': issue})['fields'],
                             {'Series': 'Amazing Spider-Man', 'Number': '129'}, (title, issue))

    def test_cover_title_within_a_longer_filename_series_agrees_for_numbered_files(self):
        book = judge('Uncanny X-Men 141 (1981).cbz', {'title': 'X-MEN', 'issue': '141'})
        self.assertEqual(book['fields'], {'Series': 'Uncanny X-Men', 'Number': '141'})
        self.assertEqual(book['evidence']['fields']['Series']['agreement'], 'cover_title_within_filename')
        # A reading-order prefix in the filename is not part of the series (found in the live-reading projection).
        self.assertIsNone(judge('003 Strange Academy - Blood Hunt 002 (2024).cbz', {'title': 'STRANGE Academy', 'issue': '2'}))
        self.assertEqual(judge('100 Bullets 001 (1999).cbz', {'title': '100 BULLETS', 'issue': '1'})['fields'],
                         {'Series': '100 Bullets', 'Number': '1'})
        self.assertIsNone(judge("Vampirella Monthly 14 - World's End 2 [1999-04].cbz", {'title': 'Vampirella', 'issue': '2 of 3'}))
        self.assertIsNone(judge('DuckTales 012 [Gladstone] - DuckTales s1 012.cbz', {'title': 'DuckTales', 'issue': 'No. 12'}))

    def test_bare_number_in_parentheses_is_the_issue_number(self):
        self.assertEqual(judge('Conan the Barbarian (252).cbz', {'title': 'Conan the Barbarian', 'issue': '252'})['fields'],
                         {'Series': 'Conan the Barbarian', 'Number': '252'})
        self.assertIsNone(judge('Conan the Barbarian (180).cbz', {'title': 'Conan the Barbarian', 'issue': '75'}))
        self.assertIsNone(judge('Conan the Barbarian (59).cbz', {'title': 'Conan the Barbarian', 'issue': 'FEB 02498'}))
        self.assertEqual(judge('Watchmen (1987).cbz', {'title': 'Watchmen', 'issue': '1'})['fields'], {'Series': 'Watchmen'})  # A year is not a number.

    def test_translation_tagged_in_the_filename_is_not_written(self):
        self.assertIsNone(judge('The Walking Dead #105 [rus].cbz', {'title': 'THE WALKING DEAD', 'issue': '105', 'publisher': 'Image Comics'}))
        self.assertIsNone(judge('Spawn 001 (fr).cbz', {'title': 'SPAWN', 'issue': '1'}))

    def test_disagreeing_cover_writes_nothing(self):
        # An unread number ({'issue': ''}, or none at all) writes from the filename since
        # Sergei 2026-10-13: FilenameNumberTests.
        for hint in ({'title': 'SPAWN', 'issue': '2'},             # different number
                     {'title': 'SPAWN', 'issue': 'VOL. 2 #3'},     # not one plain number
                     {'title': 'SUPERMAN', 'issue': '1'},          # different title
                     {'title': '', 'issue': '1'},                  # unread title
                     {'title': '', 'issue': ''}):                  # nothing read
            self.assertIsNone(judge('Spawn 001 (1992).cbz', hint), hint)
        # A cover title longer than the filename series means the filename may be missing words.
        self.assertIsNone(judge('Batman 001 (2018).cbz', {'title': 'BATMAN DAMNED', 'issue': '1'}))
        # Generic or publisher-only cover text identifies no series.
        self.assertIsNone(judge('Marvel Comics Presents 012 (1989).cbz', {'title': 'MARVEL', 'issue': '12'}))
        self.assertIsNone(judge('Spawn Special Edition 001 (1992).cbz', {'title': 'SPECIAL EDITION', 'issue': '1'}))

    def test_unnumbered_book_gets_series_only_from_an_exact_title(self):
        self.assertEqual(judge('Watchmen (1987).cbz', {'title': 'WATCHMEN', 'issue': ''})['fields'], {'Series': 'Watchmen'})
        self.assertEqual(judge('Watchmen TPB (1987).cbz', {'title': 'Watchmen'})['fields'], {'Series': 'Watchmen'})
        self.assertEqual(judge('The Milkman Murders (2012).cbz', {'title': 'Milkman Murders'})['fields'], {'Series': 'The Milkman Murders'})
        self.assertIsNone(judge('Batman - Year One (1988).cbz', {'title': 'BATMAN'}))  # Partial title: not this book.

    def test_collection_with_an_inner_issue_number(self):
        # The cover reproduces issue #1's art; the file is the whole collection. No Number is taken.
        book = judge('Batman - The Long Halloween (1998).cbz', {'title': 'Batman: The Long Halloween', 'issue': '#1'})
        self.assertEqual(book['fields'], {'Series': 'Batman - The Long Halloween'})
        self.assertEqual(book['evidence']['rule'], 'unnumbered whole book: cover title agrees exactly')
        # A volume, book or part number is not an issue number, even when the cover agrees.
        for name in ('Saga Vol. 1 (2012).cbz', 'Saga v1 (2012).cbz', 'Saga TPB 1 (2012).cbz', 'Saga Book 1 (2012).cbz',
                     'Amazing Spider-Man v2 036 (2002).cbz'):
            self.assertIsNone(judge(name, {'title': 'SAGA' if 'Saga' in name else 'Amazing Spider-Man', 'issue': '1' if 'Saga' in name else '36'}), name)

    def test_previews_or_ad_page_as_first_image(self):
        for hint in ({'title': 'TODD McFARLANE TOYS', 'issue': ''}, {'title': 'PREVIEWS', 'issue': '#50'},
                     {'title': 'SPAWN', 'issue': '51', 'search_query': 'Next issue: Spawn #51'}):
            self.assertIsNone(judge('Spawn 050 (1996).cbz', hint), hint)
        self.assertIsNone(judge('Previews 2015-03 (2015).cbz', {'title': 'PREVIEWS'}))
        self.assertIsNone(judge('Previews 0315 (2015).cbz', {'title': 'PREVIEWS', 'issue': ''}))

    def test_publisher_only_canonical_and_named_in_full(self):
        # Each reading is held to the v0.1.3 canonical full-name rule; both must name the same publisher.
        def publisher(value, indicia=None):
            indicia = value if indicia is None and isinstance(value, str) else indicia
            return judge('Spawn 001 (1992).cbz', {'title': 'SPAWN', 'issue': '1', 'publisher': value},
                         indicia=indicia or '')['fields'].get('Publisher')
        self.assertEqual(publisher('Marvel Comics Group', 'Published by Marvel Comics Group'), 'Marvel')
        self.assertEqual(publisher('DARK HORSE BOOKS', 'Dark Horse Books, a division of Dark Horse Comics'), 'Dark Horse Comics')
        self.assertEqual(publisher('Vertigo DC Comics', 'Published by DC Comics. Vertigo is a trademark'), 'DC Comics')
        for partial in ('MARVEL', 'Image', 'Dark', 'Marvel Knights', 'Kitchen Sink Press', ['Image Comics'], None,
                        'DC DARK HORSE COMICS', 'DARK HORSE COMICS DYNAMITE'):  # Ambiguous: two publishers named.
            self.assertIsNone(publisher(partial), partial)

    def test_never_overwrites_and_needs_embedded_identity_to_agree(self):
        hint = {'title': 'SPAWN', 'issue': '1', 'publisher': 'Image Comics'}
        indicia = 'SPAWN #1. Image Comics, Inc.'
        self.assertEqual(judge('Spawn 001 (1992).cbz', hint, {'Series': 'Spawn'}, indicia)['fields'], {'Number': '1', 'Publisher': 'Image Comics'})
        self.assertEqual(judge('Spawn 001 (1992).cbz', hint, {'Series': 'The Spawn', 'Number': '001'}, indicia)['fields'], {'Publisher': 'Image Comics'})
        self.assertIsNone(judge('Spawn 001 (1992).cbz', hint, {'Series': 'Spawn', 'Number': '1', 'Publisher': 'Other'}, indicia))
        self.assertIsNone(judge('Spawn 001 (1992).cbz', hint, {'Series': 'Curse of the Spawn'}))
        self.assertIsNone(judge('Spawn 001 (1992).cbz', hint, {'Number': '2'}))
        self.assertIsNone(judge('Watchmen (1987).cbz', {'title': 'WATCHMEN'}, {'Number': '1'}))

    def test_reading_must_belong_to_this_archive_and_the_switch_is_reversible(self):
        row = {'path': 'Spawn 001.cbz', 'size': 10, 'mtime': 2, 'metadata': '{}'}
        saved = {'cover_identification': {'title': 'SPAWN', 'issue': '1'}, 'cover_signature': [10, 1]}
        self.assertIsNone(in_book.identify(row, {}, saved))  # Archive changed since the reading.
        self.assertFalse(in_book.ready(row, saved))
        saved['cover_signature'] = [10, 2]
        self.assertTrue(in_book.ready(row, saved))
        with patch.object(pipeline_config, 'in_book_cover', return_value=False):
            self.assertFalse(in_book.ready(row, saved))

    def test_identity_rules_block_comicvine_ids_and_recorded_conflicts(self):
        hint = {'title': 'SPAWN', 'issue': '#1', 'publisher': 'Image Comics'}
        web = 'https://comicvine.gamespot.com/spawn-1/4000-123/'
        self.assertIsNotNone(judge('Spawn 001 (1992).cbz', hint))  # Positive control: no Web id, no conflict.
        self.assertIsNotNone(judge('Spawn 001 (1992).cbz', hint, {'Web': 'https://metron.cloud/issue/1/'}))  # Not a ComicVine issue.
        indicia = 'SPAWN #1. Image Comics, Inc.'
        self.assertIsNotNone(judge('Spawn 001 (1992).cbz', hint, {'Series': 'Spawn', 'Number': '1'}, indicia))  # Publisher only.
        self.assertIsNone(judge('Spawn 001 (1992).cbz', hint, {'Web': web}, indicia))  # Before: Series, Number and Publisher.
        self.assertIsNone(judge('Spawn 001 (1992).cbz', hint, {'Series': 'Spawn', 'Number': '1', 'Web': web}, indicia))  # Before: Publisher.
        row = {'path': 'Spawn 001 (1992).cbz', 'size': 10, 'mtime': 1, 'metadata': '{}'}
        saved = {'cover_identification': hint, 'cover_signature': [10, 1]}
        conflict = {'id': '123', 'volume': {'name': 'Another Series'}, 'issue_number': '7'}
        for previous in ({'outcome': 'identity_conflict'}, {'outcome': 'needs_identity_lookup', 'conflict_issue': conflict}):
            self.assertIsNone(in_book.identify(row, {}, saved, previous=previous))
            self.assertFalse(in_book.ready(row, saved, previous))  # Never made due by the tier, so no re-pass loop.
        self.assertTrue(in_book.ready(row, saved, {'outcome': 'needs_identity_lookup'}))  # Positive control.
        row['metadata'] = json.dumps({'Web': web})
        self.assertFalse(in_book.ready(row, saved))


class ConfigSwitchTests(unittest.TestCase):
    def test_config_switch_reads_config_json(self):
        with scratch_directory() as directory, patch.object(app, 'BASE', Path(directory)):
            self.assertTrue(pipeline_config.in_book_cover())  # On when not configured.
            (Path(directory) / 'config.json').write_text(json.dumps({'in_book': {'cover': False}}))
            self.assertFalse(pipeline_config.in_book_cover())
            # Sergei 2026-10-13: publisher only when the cover and credits/indicia readings agree,
            # under its own switch, on since the pilot (164 of 165 agreed with Metron).
            hint = {'title': 'SPAWN', 'issue': '1', 'publisher': 'Image Comics'}
            indicia = 'SPAWN #1. Published by Image Comics.'
            (Path(directory) / 'config.json').write_text(json.dumps({'in_book': {}}))
            self.assertTrue(pipeline_config.in_book_publisher_agreement())  # On when not configured.
            self.assertEqual(judge('Spawn 001 (1992).cbz', hint, indicia=indicia)['fields'],
                             {'Series': 'Spawn', 'Number': '1', 'Publisher': 'Image Comics'})
            self.assertEqual(judge('Spawn 001 (1992).cbz', hint)['fields'], {'Series': 'Spawn', 'Number': '1'})  # Cover alone.
            (Path(directory) / 'config.json').write_text(json.dumps({'in_book': {'publisher_agreement': False}}))
            self.assertFalse(pipeline_config.in_book_publisher_agreement())
            self.assertEqual(judge('Spawn 001 (1992).cbz', hint, indicia=indicia)['fields'], {'Series': 'Spawn', 'Number': '1'})
            # The v0.1.3 one-reading switch is retired. Before: Publisher "Image Comics" from the cover alone.
            (Path(directory) / 'config.json').write_text(json.dumps({'in_book': {'publisher': True, 'publisher_agreement': False}}))
            self.assertEqual(judge('Spawn 001 (1992).cbz', hint)['fields'], {'Series': 'Spawn', 'Number': '1'})
            self.assertEqual(judge('Spawn 001 (1992).cbz', hint, indicia=indicia)['fields'], {'Series': 'Spawn', 'Number': '1'})
            (Path(directory) / 'config.json').write_text(json.dumps({'in_book': {'publisher_agreement': 'no'}}))
            self.assertTrue(pipeline_config.in_book_publisher_agreement())  # Only a literal false switches it off.


class InBookPipelineTests(unittest.TestCase):
    """A saved reading writes Series/Number through the real queue and archive writer, with no source call."""

    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        for target, name, value in ((app, 'DATA', self.root / 'data'), (app, 'BASE', self.root),
                                    (research, 'CACHE', self.root / 'research'), (worker, 'QUEUE', self.root / 'queue')):
            self.enterContext(patch.object(target, name, value))
        self.enterContext(patch.object(pipeline_config, 'in_book_cover', return_value=True))
        self.enterContext(patch.object(worker.pause_control, 'requested', return_value=False))
        self.enterContext(patch.object(providers, 'statuses', return_value={}))
        import archive_conversion
        self.enterContext(patch.object(archive_conversion, 'one', return_value=False))
        self.enterContext(patch.object(automatic.batch, 'progress'))
        # Any external source call fails the test.
        boom = AssertionError('No external source may be consulted for an in-book write')
        for target, name in ((app, 'api'), (automatic, 'lookup_unidentified'), (research, 'publisher_lookup'),
                             (research, 'resolve_leads'), (research, 'general_lookup'), (research, 'wiki_candidates')):
            self.enterContext(patch.object(target, name, side_effect=boom))
        import local_model
        self.enterContext(patch.object(local_model, 'available', return_value=False))
        self.folder = self.root / 'Spawn'
        self.folder.mkdir()

    def comic(self, name):
        from PIL import Image
        cover = io.BytesIO()
        Image.new('RGB', (60, 90), 'red').save(cover, format='JPEG')
        path = self.folder / name
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('001.jpg', cover.getvalue())
            archive.writestr('002.jpg', b'page' * 100)
        app.scan([str(self.folder)], recursive=False)
        return path

    def reading(self, path, hint):
        with app.db() as con:
            row = con.execute('SELECT size,mtime FROM comics WHERE path=?', (str(path),)).fetchone()
        research.save_evidence(path, {'cover_identification': hint, 'cover_signature': [row['size'], row['mtime']],
                                      'status': 'search_hint_only'})

    def test_agreeing_cover_is_written_with_provenance_and_no_external_source(self):
        path = self.comic('Spawn 001 (1992).cbz')
        self.reading(path, {'title': 'SPAWN', 'issue': '#1', 'publisher': 'Image Comics', 'creators': ['Todd McFarlane']})
        with app.db() as con:
            cover_tasks.table(con)
            con.execute("INSERT INTO cover_tasks VALUES(?,?,?,?,?)", (str(path), '[]', 'pending', time.time(), 'queued'))
        self.assertTrue(automatic.discover(self.folder))
        tickets = list(worker.QUEUE.glob('*.json'))
        self.assertEqual(len(tickets), 1)
        plan_path = json.loads(tickets[0].read_text(encoding='utf-8'))['plan']
        entry = json.loads(Path(plan_path).read_text(encoding='utf-8'))['entries'][0]
        self.assertEqual(entry['source'], 'in-book:cover')
        self.assertNotIn('Writer', entry['fields'])
        with app.db() as con:
            record = json.loads(con.execute('SELECT value FROM discovery_records WHERE path=?', (str(path),)).fetchone()[0])
            task = con.execute('SELECT state FROM cover_tasks WHERE path=?', (str(path),)).fetchone()[0]
        self.assertEqual((record['outcome'], record['tier']), ('queued', 'in_book'))
        self.assertEqual(task, 'not_needed')  # The comic identified itself; no Lens search.
        self.assertTrue(worker.run_one())
        metadata, _, _ = app.read_metadata(path)
        self.assertEqual((metadata['Series'], metadata['Number']), ('Spawn', '1'))
        self.assertNotIn('Publisher', metadata)  # F21: the cover reading's publisher is off by default.
        self.assertNotIn('Writer', metadata)
        self.assertNotIn('Year', metadata)
        self.assertIn('In-book identification', metadata['Notes'])
        with app.db() as con:
            sources = [r[0] for r in con.execute('SELECT source FROM history')]
        self.assertEqual(sources, ['in-book:cover'])
        evidence = research.read_evidence(path)['in_book']
        self.assertEqual(evidence['fields']['Number']['from'], 'filename')
        self.assertFalse(list(self.folder.glob('.comic-metadata-backups/*')))  # Backup removed after verification.

    def test_disagreeing_cover_is_not_written_and_not_made_due(self):
        path = self.comic('Spawn 001 (1992).cbz')
        self.reading(path, {'title': 'SPAWN', 'issue': '2'})
        with app.db() as con:
            row = dict(con.execute('SELECT * FROM comics WHERE path=?', (str(path),)).fetchone())
        previous = {'version': automatic.MATCHER_VERSION, 'signature': [row['size'], row['mtime']], 'retry_at': time.time() + 86400}
        self.assertFalse(coverage_priority.lookup_flags(row, previous, {}, automatic.MATCHER_VERSION,
                                                        coverage_priority.saved_evidence(path), time.time())[0])

    def test_agreeing_reading_makes_a_waiting_comic_due(self):
        # Before v0.1.3 a comic with a usable reading waited for its ordinary research retry.
        path = self.comic('Spawn 001 (1992).cbz')
        self.reading(path, {'title': 'SPAWN', 'issue': '1'})
        with app.db() as con:
            row = dict(con.execute('SELECT * FROM comics WHERE path=?', (str(path),)).fetchone())
        previous = {'version': automatic.MATCHER_VERSION, 'signature': [row['size'], row['mtime']], 'retry_at': time.time() + 86400}
        self.assertTrue(coverage_priority.lookup_flags(row, previous, {}, automatic.MATCHER_VERSION,
                                                       coverage_priority.saved_evidence(path), time.time())[0])


WEB = 'https://comicvine.gamespot.com/spawn-1/4000-123/'


class InBookIdentityRuleTests(unittest.TestCase):
    """The v0.1.2 identity rules come before the in-book tier (rebase onto v0.1.2).

    A comic whose Web names a ComicVine issue has an agreeing cover reading that
    would fill Publisher. Held (ComicVine cannot answer), conflicting and dead-id
    passes write nothing from the cover; ComicVine's own agreeing answer still writes.
    """

    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        for target, name, value in ((app, 'DATA', self.root / 'data'), (app, 'BASE', self.root),
                                    (research, 'CACHE', self.root / 'research'), (worker, 'QUEUE', self.root / 'queue')):
            self.enterContext(patch.object(target, name, value))
        import archive_conversion, getcomics, local_model, metron, open_library, publisher_catalogs
        import source_scheduling
        now = time.time()
        waiting = {key: {'status': 'human_verification', 'retry_at': now + 5000} for key in source_scheduling.KEYS.values()}
        for target, name, value in ((pipeline_config, 'in_book_cover', True), (pipeline_config, 'in_book_publisher_agreement', True),
                                    (worker.pause_control, 'requested', False),
                                    (providers, 'statuses', waiting), (archive_conversion, 'one', False),
                                    (local_model, 'available', False), (metron, 'lookup', None), (providers, 'gcd_lookup', None),
                                    (providers, 'google_lookup', None), (open_library, 'lookup', None),
                                    (publisher_catalogs, 'lookup', None), (getcomics, 'lookup', None),
                                    (research, 'publisher_lookup', None), (research, 'resolve_leads', None),
                                    (research, 'general_lookup', None), (research, 'wiki_candidates', [])):
            self.enterContext(patch.object(target, name, return_value=value))
        self.enterContext(patch.object(automatic.batch, 'progress'))
        self.enterContext(patch.object(cover_tasks, 'enqueue'))
        self.enterContext(patch.object(automatic, 'lookup_unidentified', side_effect=AssertionError('no ComicVine search')))
        self.folder = self.root / 'Spawn'
        self.folder.mkdir()

    def comic(self, web=WEB):
        from PIL import Image
        cover = io.BytesIO()
        Image.new('RGB', (60, 90), 'red').save(cover, format='JPEG')
        path = self.folder / 'Spawn 001 (1992).cbz'
        info = '<ComicInfo><Series>Spawn</Series><Number>1</Number><Summary>Existing synopsis.</Summary>' + (
            '<Web>' + web + '</Web>' if web else '') + '</ComicInfo>'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('001.jpg', cover.getvalue())
            archive.writestr('ComicInfo.xml', info)
        app.scan([str(self.folder)], recursive=False)
        with app.db() as con:
            discovery_state.initialize(con)
            row = dict(con.execute('SELECT * FROM comics WHERE path=?', (str(path),)).fetchone())
        research.save_evidence(path, {'cover_identification': {'title': 'SPAWN', 'issue': '#1', 'publisher': 'Image Comics'},
                                      'cover_signature': [row['size'], row['mtime']], 'status': 'search_hint_only',
                                      'credits_reading': {'indicia': 'SPAWN #1. Published by Image Comics, Inc.', 'credits': ''},
                                      'credits_signature': [row['size'], row['mtime']]})
        return path, row

    def discover(self, answer):
        """One pass; `answer` is what app.api does for the Web issue. Returns (planned entries, record)."""
        def api(resource, **params):
            if resource == 'volume/4050-5':
                return {'id': 5, 'name': 'Spawn', 'publisher': {'name': 'Image'}}
            if isinstance(answer, Exception):
                raise answer
            return answer
        with patch.object(app, 'api', side_effect=api):
            automatic.discover(self.folder)
        entries = []
        for ticket in worker.QUEUE.glob('*.json'):
            plan = json.loads(Path(json.loads(ticket.read_text(encoding='utf-8'))['plan']).read_text(encoding='utf-8'))
            entries.extend(plan['entries'])
        with app.db() as con:
            record = json.loads(con.execute('SELECT value FROM discovery_records').fetchone()[0])
        return entries, record

    def assert_no_in_book_write(self, entries, path, row, record):
        self.assertFalse([e for e in entries if e.get('source') == 'in-book:cover'])
        self.assertNotIn('in_book', research.read_evidence(path))
        self.assertNotEqual(record.get('tier'), 'in_book')
        self.assertFalse(in_book.ready(row, coverage_priority.saved_evidence(path), record))  # Not made due by the tier.

    def test_held_comic_gets_no_in_book_write(self):
        from provider_wait import ProviderDeferred
        path, row = self.comic()
        entries, record = self.discover(ProviderDeferred('ComicVine is cooling down.', 'comicvine', time.time() + 300))
        self.assertEqual(entries, [])  # Before: an in-book Publisher write during the hold.
        self.assertEqual(record['outcome'], 'needs_identity_lookup')
        self.assertIn('Field writes held', record['detail'])
        self.assert_no_in_book_write(entries, path, row, record)

    def test_conflicting_comic_gets_no_in_book_write(self):
        path, row = self.comic()
        entries, record = self.discover({'id': 123, 'volume': {'name': 'Another Series', 'id': 9}, 'issue_number': '7'})
        self.assertEqual(entries, [])  # Before: an in-book Publisher write despite the conflict.
        self.assertEqual(record['outcome'], 'identity_conflict')
        self.assert_no_in_book_write(entries, path, row, record)

    def test_dead_id_gets_no_in_book_write(self):
        path, row = self.comic()
        entries, record = self.discover(app.ComicVineNotFound('test: dead id'))
        self.assertEqual(entries, [])  # A cover reading is not a strict verification.
        self.assertIn('does not exist', record['detail'])
        self.assert_no_in_book_write(entries, path, row, record)

    def test_positive_control_comicvine_agreeing_still_writes_from_comicvine(self):
        path, row = self.comic()
        entries, record = self.discover({'id': 123, 'name': 'Questions', 'volume': {'name': 'Spawn', 'id': 5}, 'issue_number': '1'})
        self.assertEqual(len(entries), 1)
        self.assertNotEqual(entries[0].get('source'), 'in-book:cover')
        self.assertEqual(entries[0]['fields']['Title'], 'Questions')

    def test_positive_control_same_comic_without_a_web_id_is_written_in_book(self):
        path, row = self.comic(web=None)
        entries, record = self.discover(AssertionError('no ComicVine call without a Web id'))
        self.assertEqual([e['source'] for e in entries], ['in-book:cover'])
        self.assertEqual(entries[0]['fields']['Publisher'], 'Image Comics')


if __name__ == '__main__':
    unittest.main()
