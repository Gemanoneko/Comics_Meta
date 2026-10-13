"""Sergei 2026-10-13, item 1: Publisher from the book only when the cover reading's publisher
AND the credits/indicia pages agree, both under the canonical full-name rule. Its own switch,
"in_book": {"publisher_agreement": ...}, on since Sergei's decision after the pilot the same day
("false" switches it off). The pilot reports the agreement against comics an external source verified.

The switch is set through config.json, which 1c34df2 ignores, so each positive control
fails there. Synthetic archives and readings; the local model and every source are mocked.
"""
import hashlib
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
import cover_tasks
import in_book
import pipeline_config
import providers
import research
import worker
from test_worker import scratch_directory

IMAGE = {'title': 'SPAWN', 'issue': '1', 'publisher': 'Image Comics'}
INDICIA = {'indicia': 'SPAWN #1, May 1992. Published by Image Comics, Inc. (c) 1992 Todd McFarlane Productions.',
           'credits': 'Story & Art: Todd McFarlane', 'pages': ['002.jpg', '024.jpg'], 'model': 'gemma3:4b'}


def judge(hint, reading, old=None, name='Spawn 001 (1992).cbz'):
    row = {'path': 'Library/' + name, 'size': 10, 'mtime': 1, 'metadata': json.dumps(old or {})}
    saved = {'cover_identification': hint, 'cover_signature': [10, 1]}
    if reading is not None:
        saved.update(credits_reading=reading, credits_signature=[10, 1])
    return in_book.identify(row, old or {}, saved)


class AgreementRuleTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app, 'BASE', self.root))
        self.config({'publisher_agreement': True})

    def config(self, section):
        (self.root / 'config.json').write_text(json.dumps({'in_book': section}), encoding='utf-8')

    def test_both_readings_name_the_same_publisher(self):
        book = judge(IMAGE, INDICIA)
        self.assertEqual(book['fields'], {'Series': 'Spawn', 'Number': '1', 'Publisher': 'Image Comics'})
        evidence = book['evidence']['fields']['Publisher']
        self.assertEqual(evidence['from'], 'cover and credits/indicia pages agree')
        self.assertIn('image comics / image comics', evidence['rule'])
        self.assertIn('named the same way on the cover and on the credits or indicia pages', in_book.notes(book))
        # A publisher-only fill for a comic whose Series and Number are already there.
        self.assertEqual(judge(IMAGE, INDICIA, {'Series': 'Spawn', 'Number': '1'})['fields'], {'Publisher': 'Image Comics'})

    def test_one_reading_alone_or_disagreeing_readings_write_no_publisher(self):
        for hint, reading in ((IMAGE, None),                                                         # cover alone
                              (dict(IMAGE, publisher=''), INDICIA),                                  # indicia alone
                              (IMAGE, dict(INDICIA, indicia='SPAWN #1. Published by Dark Horse Comics.')),  # disagree
                              (IMAGE, dict(INDICIA, indicia='SPAWN #1. Image Comics and Dark Horse Comics.')),  # two named
                              (dict(IMAGE, publisher='IMAGE'), INDICIA),                             # cover partial
                              (IMAGE, dict(INDICIA, indicia='SPAWN #1. Image.', credits=''))):        # indicia partial
            book = judge(hint, reading)
            self.assertEqual(book['fields'], {'Series': 'Spawn', 'Number': '1'}, (hint, reading))
        self.assertIsNone(judge(IMAGE, dict(INDICIA, indicia='SPAWN #1. Published by Dark Horse Comics.'), {'Series': 'Spawn', 'Number': '1'}))

    def test_credits_named_publisher_counts_as_the_printed_reading(self):
        reading = dict(INDICIA, indicia='SPAWN #1, May 1992.', credits='Story: Todd McFarlane\nPublished by Image Comics')
        self.assertEqual(judge(IMAGE, reading)['fields']['Publisher'], 'Image Comics')

    def test_switch_off_and_the_retired_one_reading_switch(self):
        self.config({})
        self.assertEqual(judge(IMAGE, INDICIA)['fields']['Publisher'], 'Image Comics')  # On by default.
        self.config({'publisher_agreement': False})
        self.assertEqual(judge(IMAGE, INDICIA)['fields'], {'Series': 'Spawn', 'Number': '1'})
        self.config({'publisher': True, 'publisher_agreement': False})  # v0.1.3: Publisher from the cover alone. Retired.
        self.assertEqual(judge(IMAGE, None)['fields'], {'Series': 'Spawn', 'Number': '1'})
        self.assertEqual(judge(IMAGE, INDICIA)['fields'], {'Series': 'Spawn', 'Number': '1'})
        self.assertEqual(in_book.judge_credits({'path': 'Library/Spawn 001 (1992).cbz', 'size': 1, 'mtime': 1}, {}, INDICIA, [1, 1],
                                               creators=False)['fields'], {'Series': 'Spawn', 'Number': '1'})  # No Year by default either.

    def test_credits_tier_needs_the_cover_to_agree_too(self):
        row = {'path': 'Library/Spawn 001 (1992).cbz', 'size': 1, 'mtime': 1}
        self.assertNotIn('Publisher', in_book.judge_credits(row, {}, INDICIA, [1, 1], creators=False)['fields'])
        self.assertEqual(in_book.judge_credits(row, {}, INDICIA, [1, 1], creators=False, cover=IMAGE)['fields']['Publisher'], 'Image Comics')
        self.assertNotIn('Publisher', in_book.judge_credits(row, {}, INDICIA, [1, 1], creators=False,
                                                            cover=dict(IMAGE, publisher='DC Comics'))['fields'])

    def test_identity_rules_still_come_first(self):
        web = 'https://comicvine.gamespot.com/spawn-1/4000-123/'
        self.assertIsNone(judge(IMAGE, INDICIA, {'Series': 'Spawn', 'Number': '1', 'Web': web}))


class AgreementDiscoveryTests(unittest.TestCase):
    """The credits pages are read once, in the in-book pass, only while the switch is on."""

    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        for target, name, value in ((app, 'DATA', self.root / 'data'), (app, 'BASE', self.root),
                                    (research, 'CACHE', self.root / 'research'), (worker, 'QUEUE', self.root / 'queue')):
            self.enterContext(patch.object(target, name, value))
        (self.root / 'data').mkdir()
        (self.root / 'data' / 'progress.json').write_text('{"completed": []}', encoding='utf-8')
        import archive_conversion, getcomics, local_model, metron, open_library, publisher_catalogs, research_runtime
        for target, name, value in ((worker.pause_control, 'requested', False), (batch.pause_control, 'requested', False),
                                    (providers, 'statuses', {}), (archive_conversion, 'one', False),
                                    (local_model, 'available', True), (local_model, 'identify_cover', None),
                                    (local_model, 'sourced_synopsis', None), (research_runtime, 'reuse', None),
                                    (metron, 'token', ''), (providers, 'gcd_lookup', None), (providers, 'google_lookup', None),
                                    (open_library, 'lookup', None), (publisher_catalogs, 'lookup', None), (getcomics, 'lookup', None),
                                    (research, 'publisher_lookup', None), (research, 'resolve_leads', None),
                                    (research, 'general_lookup', None), (research, 'wiki_candidates', [])):
            self.enterContext(patch.object(target, name, return_value=value))
        self.enterContext(patch.object(batch, 'progress'))
        self.enterContext(patch.object(cover_tasks, 'enqueue'))
        self.enterContext(patch.object(cover_tasks, 'identified'))
        self.enterContext(patch.object(app, 'api', side_effect=AssertionError('no ComicVine call without a Web id')))
        self.read = self.enterContext(patch.object(local_model, 'read_credits', return_value=INDICIA))
        self.folder = self.root / 'Spawn'
        self.folder.mkdir()
        self.path = self.folder / 'Spawn 001 (1992).cbz'
        self.write_comic()

    def write_comic(self, comicinfo=None):
        from PIL import Image
        cover = io.BytesIO()
        Image.new('RGB', (60, 90), 'red').save(cover, format='JPEG')
        before = self.path.stat().st_mtime_ns if self.path.exists() else None
        while True:
            with zipfile.ZipFile(self.path, 'w') as archive:
                archive.writestr('001.jpg', cover.getvalue())
                for page in range(2, 5):
                    archive.writestr('%03d.jpg' % page, b'page %d' % page)
                if comicinfo:
                    archive.writestr('ComicInfo.xml', comicinfo)
            if self.path.stat().st_mtime_ns != before:
                break
            time.sleep(0.01)
        app.scan([str(self.folder)], recursive=False)

    def row(self):
        with app.db() as con:
            return dict(con.execute('SELECT * FROM comics WHERE path=?', (str(self.path),)).fetchone())

    def config(self, section):
        (self.root / 'config.json').write_text(json.dumps({'in_book': section}), encoding='utf-8')

    def cover_reading(self, hint=IMAGE):
        row = self.row()
        research.save_evidence(self.path, {'cover_identification': hint, 'cover_signature': [row['size'], row['mtime']]})

    def run_pass(self):
        automatic.discover(self.folder)
        entries = []
        for _, item in worker.tickets():
            if item['state'] == 'pending':
                entries += json.loads(Path(item['plan']).read_text(encoding='utf-8'))['entries']
        worker.run_one()
        return entries

    def test_switched_on_the_credits_pages_are_read_and_the_publisher_written(self):
        self.config({'publisher_agreement': True})
        self.cover_reading()
        entries = self.run_pass()
        self.read.assert_called_once()  # Before (1c34df2): never read; no Publisher.
        self.assertEqual(entries[0]['fields']['Publisher'], 'Image Comics')
        self.assertEqual(app.read_metadata(self.path)[0]['Publisher'], 'Image Comics')
        saved = research.read_evidence(self.path)
        self.assertEqual(saved['credits_reading']['indicia'], INDICIA['indicia'])
        self.assertEqual(saved['in_book']['fields']['Publisher']['from'], 'cover and credits/indicia pages agree')

    def test_disagreeing_pages_write_series_and_number_only(self):
        self.config({'publisher_agreement': True})
        self.cover_reading(dict(IMAGE, publisher='DC Comics'))
        entries = self.run_pass()
        self.read.assert_called_once()
        self.assertEqual(set(entries[0]['changes']), {'Series', 'Number'})
        self.assertNotIn('Publisher', app.read_metadata(self.path)[0])

    def test_switched_off_nothing_is_read(self):
        self.config({'publisher_agreement': False})
        self.cover_reading()
        entries = self.run_pass()
        self.read.assert_not_called()
        self.assertEqual(set(entries[0]['changes']), {'Series', 'Number'})

    def test_a_cover_without_a_known_publisher_is_not_read(self):
        self.config({'publisher_agreement': True})
        self.cover_reading(dict(IMAGE, publisher='Kitchen Sink Press'))
        self.run_pass()
        self.read.assert_not_called()  # The agreement could never hold: no GPU spent.

    def test_a_failed_reading_still_writes_series_and_number(self):
        self.config({'publisher_agreement': True})
        self.cover_reading()
        self.read.side_effect = RuntimeError('model crashed')
        entries = self.run_pass()
        self.assertEqual(set(entries[0]['changes']), {'Series', 'Number'})
        self.assertEqual(research.read_evidence(self.path)['credits_reading_error']['error'], 'RuntimeError')

    def test_a_failed_reading_is_no_reading_and_is_not_repeated(self):
        # Pilot 2026-10-13: 8 of 403 reads failed (unterminated JSON, an unreadable page).
        self.config({'publisher_agreement': True})
        self.cover_reading()
        self.read.side_effect = json.JSONDecodeError('Unterminated string', '{"indicia": "SPAWN', 12)
        entries = self.run_pass()
        self.assertEqual(set(entries[0]['changes']), {'Series', 'Number'})  # Never agreement.
        self.assertEqual(research.read_evidence(self.path)['credits_reading_error']['error'], 'JSONDecodeError')
        self.run_pass()  # The comic changed (written) and is due again: the same pages are not read twice.
        self.assertEqual(self.read.call_count, 1)
        self.assertNotIn('Publisher', app.read_metadata(self.path)[0])
        self.write_comic('<ComicInfo><Series>Spawn</Series><Number>1</Number></ComicInfo>')  # Other pages now.
        self.cover_reading()
        self.run_pass()
        self.assertEqual(self.read.call_count, 2)  # Positive control: new pages are read.

    def test_publisher_added_later_to_a_comic_the_app_wrote(self):
        # Written with the switch off; the cover reading predates that write. The app's own write
        # changed only ComicInfo.xml, so the reading still describes these pages.
        self.config({'publisher_agreement': False})
        self.cover_reading()
        self.run_pass()
        self.assertNotIn('Publisher', app.read_metadata(self.path)[0])
        self.config({'publisher_agreement': True})
        entries = self.run_pass()
        self.read.assert_called_once()
        self.assertEqual(entries[0]['changes'], {'Publisher': {'before': '', 'after': 'Image Comics'}})
        self.assertEqual(app.read_metadata(self.path)[0]['Publisher'], 'Image Comics')

    def test_no_later_publisher_after_another_program_saved_the_comic(self):
        self.config({'publisher_agreement': False})
        self.cover_reading()
        self.run_pass()
        metadata = app.read_metadata(self.path)[0]
        # Another program re-saves the archive with the same identity: its pages may differ now.
        self.write_comic('<ComicInfo><Series>%s</Series><Number>%s</Number></ComicInfo>' % (metadata['Series'], metadata['Number']))
        self.config({'publisher_agreement': True})
        entries = self.run_pass()
        self.read.assert_not_called()
        self.assertFalse([e for e in entries if 'Publisher' in e['changes']])


class PilotPublisherTests(unittest.TestCase):
    def test_pilot_reports_agreement_against_verified_publishers_and_its_gate(self):
        import pilot_credits
        with scratch_directory() as directory:
            root = Path(directory)
            (root / 'library').mkdir()
            data = root / 'data'
            (data / 'research').mkdir(parents=True)
            readings, covers, files = {}, {}, []
            for name, cover, printed, verified, provider in (
                    ('Spawn 001 (1992).cbz', 'Image Comics', 'Published by Image Comics', 'Image', 'Metron'),
                    ('Hellboy 001 (1994).cbz', 'Dark Horse Comics', 'Dark Horse Comics, Inc.', 'Dark Horse', 'GCD'),
                    ('Sandman 001 (1989).cbz', 'DC Comics', 'Published by DC Comics', 'Vertigo', 'Metron'),     # same house
                    ('Saga 001 (2012).cbz', 'Image Comics', 'Published by Dark Horse Comics', 'Image', 'Metron')):  # differ
                comic = root / 'library' / name
                with zipfile.ZipFile(comic, 'w') as archive:
                    for page in range(4):
                        archive.writestr('%03d.jpg' % page, b'page %d' % page)
                series = name.split(' 001')[0]
                fields = {'Series': series, 'Number': '1', 'Publisher': verified}
                evidence = data / 'research' / ('evidence-' + hashlib.sha256(str(comic).encode()).hexdigest() + '.json')
                evidence.write_text(json.dumps({'path': str(comic), 'verified_evidence': {'result': {'provider': provider, 'fields': fields}}}))
                readings[str(comic)] = {'indicia': series.upper() + ' #1. ' + printed, 'credits': ''}
                covers[str(comic)] = {'title': series.upper(), 'issue': '1', 'publisher': cover}
                files += [comic, evidence]
            before = {p: p.read_bytes() for p in files}
            target, report = pilot_credits.run(root / 'out', data, reader=lambda path: readings[path],
                                               cover_reader=lambda path: covers[path], min_writes=3, max_disagreements=0)
            self.assertEqual({p: p.read_bytes() for p in before}, before)  # Archives and evidence untouched.
            agreement = report['publisher_agreement']
            self.assertEqual((agreement['comics'], agreement['both_same'], agreement['both_different']), (4, 3, 1))
            self.assertEqual(agreement['would_write'], {'agree': 3, 'disagree': 0, 'not_in_source': 0})
            self.assertEqual(agreement['cover_alone'], {'agree': 4, 'disagree': 0, 'not_in_source': 0})
            self.assertEqual(report['publisher_gate']['checked_writes'], 3)
            self.assertTrue(report['publisher_gate']['passed'])  # Vertigo agrees with its parent DC.
            self.assertEqual(report['sources'], {'GCD': 1, 'Metron': 3})
            self.assertEqual(report['seconds_per_comic']['credits_reading']['n'], 4)
            self.assertEqual(report['seconds_per_comic']['cover_reading']['n'], 4)
            sandman = next(c for c in report['comics'] if 'Sandman' in c['path'])
            self.assertEqual(sandman['publisher']['verdict'], 'agree')
            _, passing = pilot_credits.run(root / 'out', data, reader=lambda path: readings[path],
                                           cover_reader=lambda path: covers[path], min_writes=3, max_disagreements=1)
            self.assertTrue(passing['publisher_gate']['passed'])
            self.assertTrue(target.is_file())


if __name__ == '__main__':
    unittest.main()
