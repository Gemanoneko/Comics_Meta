"""Sergei 2026-10-13, item 2: a numbered file whose cover number could not be read gets
Series and Number from the filename alone, when the cover TITLE agrees with the filename
series. The v0.1.3 skips stay: reading-order prefixes, chapter numbering, a number in
brackets ("(180)"), translation tags and collections. Provenance: 'in-book:filename-number'.

Accuracy fixtures are synthetic readings shaped like the live ones; no model or source.
"""
import io
import json
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
import app
import automatic
import cover_tasks
import coverage_priority
import in_book
import pipeline_config
import providers
import research
import worker
from test_worker import scratch_directory


def judge(name, hint, old=None):
    row = {'path': 'Library/Series/' + name, 'size': 10, 'mtime': 1, 'metadata': json.dumps(old or {})}
    return in_book.identify(row, old or {}, {'cover_identification': hint, 'cover_signature': [10, 1]})


class FilenameNumberTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(pipeline_config, 'in_book_cover', return_value=True))

    def test_unread_cover_number_writes_series_and_number_from_the_filename(self):
        # Before (1c34df2): None for every one of these.
        for hint in ({'title': 'SPAWN', 'issue': ''}, {'title': 'SPAWN'}, {'title': 'SPAWN', 'issue': None},
                     {'title': 'SPAWN', 'issue': 'N/A'}, {'title': 'SPAWN', 'issue': '?'}, {'title': 'Spawn', 'issue': '  '}):
            book = judge('Spawn 001 (1992) (digital).cbz', hint)
            self.assertIsNotNone(book, hint)
            self.assertEqual(book['fields'], {'Series': 'Spawn', 'Number': '1'}, hint)
            self.assertEqual(book['evidence']['source'], 'in-book:filename-number')
            self.assertEqual(book['evidence']['fields']['Number']['from'], 'filename alone')
            self.assertEqual(book['evidence']['fields']['Number']['cover_number'], 'unread')
        book = judge('Uncanny X-Men 141 (1981).cbz', {'title': 'X-MEN', 'issue': ''})
        self.assertEqual(book['fields'], {'Series': 'Uncanny X-Men', 'Number': '141'})
        self.assertEqual(book['evidence']['fields']['Series']['agreement'], 'cover_title_within_filename')

    def test_entry_records_its_own_provenance(self):
        book = judge('Spawn 001 (1992).cbz', {'title': 'SPAWN', 'issue': ''})
        entry = in_book.entry('Library/Series/Spawn 001 (1992).cbz', book, 'digest')
        self.assertEqual(entry['source'], 'in-book:filename-number')
        self.assertEqual(entry['method'], in_book.FILENAME_NUMBER_METHOD)
        self.assertIn('the cover shows no plain issue number', entry['fields']['Notes'])
        self.assertIn('from the filename alone', entry['fields']['Notes'])

    def test_a_cover_number_that_was_read_still_decides(self):
        self.assertEqual(judge('Spawn 001 (1992).cbz', {'title': 'SPAWN', 'issue': '#1'})['evidence']['source'], 'in-book:cover')
        for issue in ('2', 'VOL. 2 #3', 'Annual', 'Book Two', 'FEB 02498', ['1']):  # Different, or numbering text.
            self.assertIsNone(judge('Spawn 001 (1992).cbz', {'title': 'SPAWN', 'issue': issue}), issue)

    def test_the_title_must_still_agree(self):
        for hint in ({'title': 'SUPERMAN', 'issue': ''}, {'title': '', 'issue': ''}, {'title': 'BATMAN DAMNED'}):
            self.assertIsNone(judge('Batman 001 (2018).cbz', hint), hint)
        self.assertIsNone(judge('Marvel Comics Presents 012 (1989).cbz', {'title': 'MARVEL', 'issue': ''}))

    def test_skips_kept_from_v013(self):
        unread = {'issue': ''}
        cases = (
            ('003 Strange Academy - Blood Hunt 002 (2024).cbz', 'STRANGE Academy'),       # reading-order prefix
            ("Vampirella Monthly 14 - World's End 2 [1999-04].cbz", 'Vampirella'),        # chapter-style numbering
            ('DuckTales 012 [Gladstone] - DuckTales s1 012.cbz', 'DuckTales'),
            ('The Walking Dead #105 [rus].cbz', 'THE WALKING DEAD'),                     # translation
            ('Spawn 001 (fr).cbz', 'SPAWN'),
            ('Saga Vol. 1 (2012).cbz', 'SAGA'), ('Saga TPB 1 (2012).cbz', 'SAGA'),       # collections
            ('Saga Book 1 (2012).cbz', 'SAGA'), ('Batman Omnibus 2.cbz', 'BATMAN'),
            ('Berserk Chapter 300.cbz', 'BERSERK'), ('Naruto Ch 12.cbz', 'NARUTO'),       # chapter numbers
        )
        for name, title in cases:
            self.assertIsNone(judge(name, dict(unread, title=title)), name)

    def test_numbers_the_filename_alone_cannot_settle(self):
        unread = {'issue': ''}
        for name, title in (('Conan the Barbarian (180).cbz', 'Conan the Barbarian'),     # "(180)": the only number
                            ('Batman 5 (180).cbz', 'BATMAN'),                            # beside another numbering
                            ('Batman 5 [180].cbz', 'BATMAN'),
                            ('Naruto (Chapter 5) - Kakashi 3 (2005).cbz', 'NARUTO'),     # chapter numbering in brackets
                            ('Doctor Who Episode 4 2.cbz', 'DOCTOR WHO'),
                            ('Previews 0315 (2015).cbz', 'PREVIEWS'),                    # catalog; date code
                            ('Previews 315 (2015).cbz', 'PREVIEWS'),
                            ('Batman 0315.cbz', 'BATMAN')):                              # MMYY date code
            self.assertIsNone(judge(name, dict(unread, title=title)), name)
        # Positive controls: the same files are written when the cover shows the number, or the
        # number is an ordinary one.
        self.assertEqual(judge('Conan the Barbarian (180).cbz', {'title': 'Conan the Barbarian', 'issue': '180'})['fields']['Number'], '180')
        self.assertEqual(judge('Batman 315.cbz', {'title': 'BATMAN', 'issue': ''})['fields'], {'Series': 'Batman', 'Number': '315'})
        self.assertEqual(judge('Batman 5 (2016).cbz', {'title': 'BATMAN', 'issue': ''})['fields']['Number'], '5')  # A year is not a number.

    def test_cover_issue_text_shapes_from_the_live_readings(self):
        # The ~3,925 numbered files whose cover gave no plain number: 776 empty readings, the rest text.
        def number(name, issue, title='SPAWN'):
            book = judge(name, {'title': title, 'issue': issue})
            return book['fields'].get('Number') if book else None
        for issue in ('1 (OF 4)', '#1 (of 4)', 'ISSUE ONE', 'NUMBER ONE', 'ONE', 'Nº 1', 'N°1', '1 US', '1 #1', 'ISSUE NO. 1',
                      '1: A Future Uncertain', 'Oct #1', 'Human Race #1 of 4', 'Nº 1 MARCH'):
            self.assertEqual(number('Spawn 001 (1992).cbz', issue), '1', issue)                  # the same number, other wording
        self.assertEqual(number('Lady Death Origins 007 (2015).cbz', 'Origins #07', 'LADY DEATH'), '7')
        # A bare number after other words may be part of a title ("UNIT 731", "MELTDOWN 2"): unclear, not written.
        for name, issue, title in (('Lady Death Origins 007 (2015).cbz', 'ORIGINS 07', 'LADY DEATH'),
                                   ('The Collector - Unit 731 (2023) (digital).cbz', 'UNIT 731', 'THE COLLECTOR'),
                                   ('Havok & Wolverine - Meltdown #02.cbz', 'MELTDOWN 2', 'HAVOK & WOLVERINE'),
                                   ('Star Wars Infinities - A New Hope 02.cbz', 'A NEW HOPE 2 OF 4', 'STAR WARS')):
            self.assertIsNone(number(name, issue, title), name)
        for issue in ('JUNE 2005', "MAY '95", 'November 1998', 'DEC 1', '$2.99', 'TRUE GHOST STORIES', 'The Crucible'):
            self.assertEqual(number('Spawn 001 (1992).cbz', issue), '1', issue)                  # no issue number on the cover
        for issue in ('ISSUE TWO', '2 (OF 4)', '#2', 'FEB 02498'):
            self.assertIsNone(number('Spawn 001 (1992).cbz', issue), issue)                      # another number
        self.assertIsNone(number('Lady Death Origins 007 (2015).cbz', 'Origins #08', 'LADY DEATH'))
        for issue in ('PART 2 OF 3', 'BOOK 2', 'Book Two', 'VOLUME 3', 'Chapter 6', 'EPISODE 1', 'SEASON ZERO', 'PART II', 'V2'):
            self.assertIsNone(number('Spawn 001 (1992).cbz', issue), issue)                      # another numbering
        for issue in ('Issue 1 #2', 'ANNUAL', '2005 SWIMSUIT SPECIAL', '1 - Альдоран'):
            self.assertIsNone(number('Spawn 001 (1992).cbz', issue), issue)                      # unclear, or another kind
        self.assertEqual(number('Spawn Annual 001 (1999).cbz', 'ANNUAL', 'SPAWN ANNUAL'), '1')  # The filename names the kind.

    def test_filename_numbers_that_are_not_issue_numbers(self):
        unread = {'issue': ''}
        for name, title in (('Drowned Girl GN (1990) c2c (DC) 17689.cbz', 'DROWNED GIRL'),       # live snapshot
                            ('Lady Death - Bikini Special 2005 (shaw001).cbz', 'LADY DEATH'),
                            ('Spawn c2c 5.cbz', 'SPAWN'), ('Batman 12345.cbz', 'BATMAN'),
                            ('Batman HC 3.cbz', 'BATMAN'), ('Hellboy Omnibus 2.cbz', 'HELLBOY'),
                            ('Mezz - Galactic Tour 2494.cbz', 'MEZZ'), ('Detective Comics 1027.cbz', 'DETECTIVE COMICS'),
                            ('Torchwood 003.3 (2018).cbz', 'TORCHWOOD')):
            self.assertIsNone(judge(name, dict(unread, title=title)), name)
        self.assertEqual(judge('Lady Death - Bikini Special 2005 (shaw001).cbz', {'title': 'LADY DEATH', 'issue': '2005'})['fields']['Number'],
                         '2005')  # Control: the cover-confirmed rule is unchanged.
        self.assertEqual(judge('Mages 001.cbz', {'title': 'MAGES', 'issue': ''})['fields']['Number'], '1')  # Control for the script rule.

    def test_half_issues_keep_their_zero(self):
        # app.parse_name turns "0.5" into ".5"; before this fix the filename-only rule read it as issue 5.
        book = judge('Lady Death - The Crucible 0.5 (1996) (shaw001).cbz', {'title': 'LADY DEATH', 'issue': 'The Crucible'})
        self.assertEqual(book['fields']['Number'], '0.5')
        self.assertEqual(judge('Lady Death 0.5 (1994).cbz', {'title': 'LADY DEATH', 'issue': '0.5'})['fields']['Number'], '0.5')

    def test_embedded_values_must_agree_and_are_never_overwritten(self):
        hint = {'title': 'SPAWN', 'issue': ''}
        self.assertEqual(judge('Spawn 001 (1992).cbz', hint, {'Series': 'Spawn'})['fields'], {'Number': '1'})
        self.assertIsNone(judge('Spawn 001 (1992).cbz', hint, {'Number': '2'}))
        self.assertIsNone(judge('Spawn 001 (1992).cbz', hint, {'Series': 'Curse of the Spawn'}))
        self.assertIsNone(judge('Spawn 001 (1992).cbz', hint, {'Series': 'Spawn', 'Number': '1'}))

    def test_switch_and_identity_rules(self):
        hint = {'title': 'SPAWN', 'issue': ''}
        with scratch_directory() as directory, patch.object(app, 'BASE', Path(directory)):
            self.assertTrue(pipeline_config.in_book_filename_number())  # On when not configured.
            (Path(directory) / 'config.json').write_text(json.dumps({'in_book': {'filename_number': False}}))
            self.assertFalse(pipeline_config.in_book_filename_number())
            self.assertIsNone(judge('Spawn 001 (1992).cbz', hint))
            self.assertIsNotNone(judge('Spawn 001 (1992).cbz', {'title': 'SPAWN', 'issue': '1'}))  # The cover rule is separate.
        web = 'https://comicvine.gamespot.com/spawn-1/4000-123/'
        self.assertIsNone(judge('Spawn 001 (1992).cbz', hint, {'Web': web}))
        row = {'path': 'Spawn 001 (1992).cbz', 'size': 10, 'mtime': 1, 'metadata': '{}'}
        saved = {'cover_identification': hint, 'cover_signature': [10, 1]}
        self.assertTrue(in_book.ready(row, saved))
        self.assertFalse(in_book.ready(row, saved, {'outcome': 'identity_conflict'}))


class FilenameNumberPipelineTests(unittest.TestCase):
    """Through the real queue and writer: provenance in history, Notes and evidence; no source call."""

    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        for target, name, value in ((app, 'DATA', self.root / 'data'), (app, 'BASE', self.root),
                                    (research, 'CACHE', self.root / 'research'), (worker, 'QUEUE', self.root / 'queue')):
            self.enterContext(patch.object(target, name, value))
        self.enterContext(patch.object(worker.pause_control, 'requested', return_value=False))
        self.enterContext(patch.object(providers, 'statuses', return_value={}))
        import archive_conversion, local_model
        self.enterContext(patch.object(archive_conversion, 'one', return_value=False))
        self.enterContext(patch.object(automatic.batch, 'progress'))
        self.enterContext(patch.object(local_model, 'available', return_value=False))
        boom = AssertionError('No external source may be consulted for an in-book write')
        for target, name in ((app, 'api'), (automatic, 'lookup_unidentified'), (research, 'publisher_lookup'),
                             (research, 'resolve_leads'), (research, 'general_lookup'), (research, 'wiki_candidates')):
            self.enterContext(patch.object(target, name, side_effect=boom))
        self.folder = self.root / 'Spawn'
        self.folder.mkdir()

    def test_unread_number_is_written_with_its_own_provenance(self):
        from PIL import Image
        cover = io.BytesIO()
        Image.new('RGB', (60, 90), 'red').save(cover, format='JPEG')
        path = self.folder / 'Spawn 007 (1993).cbz'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('001.jpg', cover.getvalue())
            archive.writestr('002.jpg', b'page' * 100)
        app.scan([str(self.folder)], recursive=False)
        with app.db() as con:
            row = dict(con.execute('SELECT * FROM comics WHERE path=?', (str(path),)).fetchone())
        research.save_evidence(path, {'cover_identification': {'title': 'SPAWN', 'issue': ''}, 'cover_signature': [row['size'], row['mtime']]})
        self.assertTrue(in_book.ready(row, coverage_priority.saved_evidence(path)))  # Before: not due, waits for research.
        with patch.object(cover_tasks, 'identified'):
            self.assertTrue(automatic.discover(self.folder))
        self.assertTrue(worker.run_one())
        metadata = app.read_metadata(path)[0]
        self.assertEqual((metadata['Series'], metadata['Number']), ('Spawn', '7'))
        self.assertIn('the cover shows no plain issue number', metadata['Notes'])
        with app.db() as con:
            self.assertEqual([r[0] for r in con.execute('SELECT source FROM history')], ['in-book:filename-number'])
        self.assertEqual(research.read_evidence(path)['in_book']['source'], 'in-book:filename-number')


if __name__ == '__main__':
    unittest.main()
