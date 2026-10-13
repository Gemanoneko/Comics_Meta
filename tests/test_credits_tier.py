"""Stretch: in-book credits/indicia tier (off by default) and its read-only pilot harness.

Synthetic readings and archives; the local model and every source are mocked.
"""
import hashlib
import json
import unittest
import zipfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
import app
import automatic
import in_book
import pipeline_config
import research
import worker
from test_worker import scratch_directory

SPAWN = {'indicia': 'SPAWN #1, May 1992. Published by Image Comics, Inc. Spawn and its logos are (c) 1992 Todd McFarlane Productions.',
         'credits': 'Story & Art: Todd McFarlane\nColors: Steve Oliff / Olyoptics\nLetters: Tom Orzechowski\nEditor: Eric Stephenson\nCover by Todd McFarlane',
         'pages': ['002.jpg', '024.jpg'], 'model': 'gemma3:4b'}


def judge(name, reading, old=None, creators=None):
    return in_book.judge_credits({'path': 'Library/' + name, 'size': 1, 'mtime': 1}, old or {}, reading, [1, 1], creators=creators)


class CreditsJudgeTests(unittest.TestCase):
    def test_indicia_naming_series_and_issue_writes_identity_cover_date_and_publisher(self):
        book = judge('Spawn 001 (1992).cbz', SPAWN, creators=False)
        self.assertEqual(book['fields'], {'Series': 'Spawn', 'Number': '1', 'Year': '1992', 'Month': '05'})  # F21: publisher off by default.
        with patch.object(pipeline_config, 'in_book_publisher', return_value=True):
            book = judge('Spawn 001 (1992).cbz', SPAWN, creators=False)
        self.assertEqual(book['fields'], {'Series': 'Spawn', 'Number': '1', 'Year': '1992', 'Month': '05', 'Publisher': 'Image Comics'})
        self.assertEqual(book['evidence']['source'], 'in-book:credits')
        entry = in_book.entry('Library/Spawn 001 (1992).cbz', book, 'digest')
        self.assertEqual(entry['source'], 'in-book:credits')
        self.assertIn('printed cover date', entry['fields']['Notes'])

    def test_creators_only_from_labelled_credits_and_only_when_asked(self):
        book = judge('Spawn 001 (1992).cbz', SPAWN, creators=True)
        self.assertEqual((book['fields']['Writer'], book['fields']['Penciller']), ('Todd McFarlane', 'Todd McFarlane'))
        self.assertEqual((book['fields']['Colorist'], book['fields']['Letterer']), ('Steve Oliff', 'Tom Orzechowski'))
        self.assertNotIn('CoverArtist', book['fields'])
        self.assertNotIn('Editor', book['fields'])
        self.assertNotIn('Writer', judge('Spawn 001 (1992).cbz', SPAWN)['fields'])  # Off unless switched on.

    def test_copyright_year_alone_never_becomes_the_year(self):
        reading = dict(SPAWN, indicia='SPAWN #1. Published by Image Comics. (c) 1992 Todd McFarlane Productions.')
        self.assertNotIn('Year', judge('Spawn 001 (1992).cbz', reading)['fields'])

    def test_other_issue_unnumbered_file_or_missing_indicia_writes_nothing(self):
        self.assertIsNone(judge('Spawn 002 (1992).cbz', SPAWN))
        self.assertIsNone(judge('Spawn (1992).cbz', SPAWN))
        self.assertIsNone(judge('Spawn 001 (1992).cbz', dict(SPAWN, indicia='')))
        self.assertIsNone(judge('Batman 001 (1992).cbz', SPAWN))
        self.assertIsNone(judge('Spawn 001 (1992).cbz', SPAWN, {'Series': 'Curse of the Spawn'}))

    def test_saved_reading_is_used_only_when_switched_on(self):
        row = {'path': 'Library/Spawn 001 (1992).cbz', 'size': 1, 'mtime': 1, 'metadata': '{}'}
        saved = {'credits_reading': SPAWN, 'credits_signature': [1, 1]}
        self.assertFalse(pipeline_config.in_book_credits_pages())
        self.assertFalse(in_book.ready(row, saved))
        with patch.object(pipeline_config, 'in_book_credits_pages', return_value=True):
            self.assertTrue(in_book.ready(row, saved))
            self.assertFalse(in_book.ready(dict(row, mtime=2), saved))  # Archive changed since the reading.


class CreditsDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        for target, name, value in ((app, 'DATA', self.root / 'data'), (app, 'BASE', self.root),
                                    (research, 'CACHE', self.root / 'research'), (worker, 'QUEUE', self.root / 'queue')):
            self.enterContext(patch.object(target, name, value))
        self.folder = self.root / 'Spawn'
        self.folder.mkdir()
        self.path = self.folder / 'Spawn 001 (1992).cbz'
        with zipfile.ZipFile(self.path, 'w') as archive:
            for page in range(4):
                archive.writestr('%03d.jpg' % page, b'page %d' % page)

    def discover(self):
        import archive_conversion, cover_tasks, local_model, metron, providers, research_runtime
        enqueued = []
        patches = [patch.object(archive_conversion, 'one', return_value=False), patch.object(providers, 'statuses', return_value={}),
                   patch.object(worker.pause_control, 'requested', return_value=False), patch.object(automatic.batch, 'progress'),
                   patch.object(research_runtime, 'reuse', return_value=None), patch.object(app, 'api', return_value=None),
                   patch.object(metron, 'token', return_value=''), patch.object(providers, 'gcd_lookup', return_value=None),
                   patch.object(providers, 'google_lookup', return_value=None), patch.object(research, 'publisher_lookup', return_value=None),
                   patch.object(research, 'resolve_leads', return_value=None), patch.object(local_model, 'available', return_value=True),
                   patch.object(local_model, 'identify_cover', return_value={'title': 'Something else', 'issue': ''}),
                   patch.object(local_model, 'sourced_synopsis', return_value=None),
                   patch.object(cover_tasks, 'enqueue', side_effect=lambda row: enqueued.append(row['path']))]
        with ExitStack() as stack:
            for item in patches:
                stack.enter_context(item)
            self.read = stack.enter_context(patch.object(local_model, 'read_credits', return_value=SPAWN))
            automatic.discover(self.folder)
        return enqueued

    def test_off_by_default_no_credits_reading_and_the_lens_queue_as_before(self):
        enqueued = self.discover()
        self.read.assert_not_called()
        self.assertEqual(enqueued, [str(self.path)])
        self.assertFalse(list(worker.QUEUE.glob('*.json')))

    def test_switched_on_the_indicia_identifies_the_comic(self):
        (self.root / 'config.json').write_text(json.dumps({'in_book': {'credits_pages': True}}))
        enqueued = self.discover()
        self.read.assert_called_once()
        self.assertEqual(enqueued, [])  # The comic identified itself; no Lens search.
        plan = json.loads(Path(json.loads(next(worker.QUEUE.glob('*.json')).read_text())['plan']).read_text())
        entry = plan['entries'][0]
        self.assertEqual(entry['source'], 'in-book:credits')
        self.assertEqual(entry['fields']['Year'], '1992')
        self.assertNotIn('Writer', entry['fields'])  # Creators need their own switch.
        self.assertEqual(research.read_evidence(self.path)['credits_signature'], [self.path.stat().st_size, self.path.stat().st_mtime_ns])


    def test_switched_on_it_never_reads_a_comic_whose_web_names_a_comicvine_issue(self):
        # v0.1.2 identity rules first: ComicVine gives no answer here, so the comic is held.
        (self.root / 'config.json').write_text(json.dumps({'in_book': {'credits_pages': True}}))
        with zipfile.ZipFile(self.path, 'a') as archive:
            archive.writestr('ComicInfo.xml', '<ComicInfo><Web>https://comicvine.gamespot.com/spawn-1/4000-123/</Web></ComicInfo>')
        self.discover()
        self.read.assert_not_called()  # Before the rebase: a credits reading and a Series/Number/Year write.
        self.assertFalse(list(worker.QUEUE.glob('*.json')))
        with app.db() as con:
            record = json.loads(con.execute('SELECT value FROM discovery_records').fetchone()[0])
        self.assertEqual(record['outcome'], 'needs_identity_lookup')

class PilotHarnessTests(unittest.TestCase):
    def test_pilot_compares_with_metron_and_writes_only_its_report(self):
        import pilot_credits
        with scratch_directory() as directory:
            root = Path(directory)
            comic = root / 'library' / 'Spawn 001 (1992).cbz'
            comic.parent.mkdir()
            with zipfile.ZipFile(comic, 'w') as archive:
                for page in range(4):
                    archive.writestr('%03d.jpg' % page, b'page %d' % page)
            data = root / 'data'
            (data / 'research').mkdir(parents=True)
            metron = {'Series': 'Spawn', 'Number': '1', 'Year': '1992', 'Month': '05', 'Publisher': 'Image',
                      'Writer': 'Todd McFarlane', 'Penciller': 'Todd McFarlane', 'Colorist': 'Steve Oliff'}
            evidence = data / 'research' / ('evidence-' + hashlib.sha256(str(comic).encode()).hexdigest() + '.json')
            evidence.write_text(json.dumps({'path': str(comic), 'verified_evidence': {'result': {'provider': 'Metron', 'fields': metron}}}))
            before = {p: p.read_bytes() for p in [comic, evidence]}
            target, report = pilot_credits.run(root / 'out', data, reader=lambda path: SPAWN)
            self.assertEqual({p: p.read_bytes() for p in before}, before)  # Archive and evidence untouched.
            self.assertEqual(sorted(p.name for p in data.rglob('*')), sorted(['research', evidence.name]))
            self.assertEqual((report['comics_read'], report['tier_fired']), (1, 1))
            self.assertEqual(report['fields']['Number'], {'written': 1, 'agree': 1, 'disagree': 0, 'not_in_metron': 0})
            self.assertEqual(report['fields']['Letterer']['not_in_metron'], 1)
            self.assertTrue(target.is_file())


if __name__ == '__main__':
    unittest.main()
