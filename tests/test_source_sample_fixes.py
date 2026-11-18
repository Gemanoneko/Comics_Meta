"""Futaba's source sample 2026-11-18 (Docs/ComicsMetaOrganizer_SourceSample_2026-11-18.md): F2, a bracketed
"(part N of M)" passed the unnumbered guard and was asked as issue 1; F3, a ComicVine name ending in a space was
written as it came. Each test has a positive control. Mocked sources only."""
import re
import unittest
from pathlib import Path
from unittest.mock import patch
import app
import comicvine_search
import metron
import pipeline_config
import versedb
from test_worker import scratch_directory
from test_comicvine_search import FakeComicVine, cv_issue, volume
from test_versedb import FakeVerseDB, issue as vdb_issue, series as vdb_series

NINJAK = r'Y:\Comix\Valiant\Ninjak\Ninjak The Complete Classic Omnibus (part 2 of 2) (2018) (digital) (Verbal-DCP).cbz'


def old_unnumbered_book(path):
    """The guard before the fix, kept here as the positive control."""
    stem = Path(path).stem
    if re.search(r'\(\s*of\s*\d+\s*\)', stem, re.I):
        return False
    return not metron.NUMBERED_NAME.search(re.sub(r'\([^)]*\)|\[[^]]*\]', ' ', stem))


def row_for(path):
    series, number, year = app.parse_name(path)
    return {'path': path, 'series': series, 'number': number, 'year': year}


class BracketedPartTests(unittest.TestCase):
    def test_a_bracketed_part_label_is_not_an_unnumbered_whole_book(self):
        for name in ('Omnibus (part 2 of 2) (2018).cbz', 'Omnibus (part 1 of 2) (2018).cbz', 'Omnibus (1 of 3) (2018).cbz',
                     'Omnibus (Part Two) (2018).cbz', 'Omnibus (Vol. 3) (2018).cbz', 'Omnibus (Book II) (2018).cbz',
                     'Omnibus [Chapter 1] (2018).cbz', 'Omnibus (of 4) (2018).cbz', 'Omnibus (Part 3 - The End) (2018).cbz'):
            self.assertFalse(metron.unnumbered_book(name), name)
        self.assertTrue(old_unnumbered_book(NINJAK))  # Positive control: the old guard let it through.
        self.assertFalse(metron.unnumbered_book(NINJAK))

    def test_ordinary_brackets_still_leave_a_whole_book_unnumbered(self):
        for name in ('The King in Yellow (2015) (digital-Empire).cbz', 'Buffy - The Lost Summers (2023) (Digital-Empire).cbz',
                     'Title (c2c) (2009) (1920px).cbz', 'Title (Book Club Edition) (2001).cbz', 'Title (Director\'s Cut) (2010).cbz',
                     'Title (Book of Shadows) (2004).cbz', 'Title (Marvel Collection) (2012).cbz'):
            self.assertTrue(metron.unnumbered_book(name), name)

    def test_neither_fallback_asks_a_part_file_as_issue_1(self):
        omnibus = volume(701, 'Ninjak: The Complete Classic Omnibus', 2018, count=1)
        path_whole = NINJAK.replace(' (part 2 of 2)', '')
        defaults = lambda name: pipeline_config.MATCHING_DEFAULTS[name]
        with scratch_directory() as directory, patch.object(app, 'DATA', Path(directory) / 'data'), \
                patch.object(app, 'api_key', return_value='synthetic'), patch.object(versedb, 'token', return_value='synthetic'), \
                patch.object(pipeline_config, 'matching', side_effect=defaults), \
                patch.object(comicvine_search, 'verified_cover', return_value={'comparison': 'today', 'page': 1}), \
                patch.object(versedb, 'verified_cover', return_value={'comparison': 'today', 'page': 1}):
            for path in (NINJAK, path_whole):
                cv = FakeComicVine([omnibus], [cv_issue(7101, omnibus, '1', '2018-06-01')])
                vdb = FakeVerseDB([vdb_series(81, 'Ninjak: The Complete Classic Omnibus', 2018, kind='collected_edition', count=1)],
                                  [vdb_issue(8101, 81, '1', '2018-06-01')])
                with patch.object(comicvine_search, 'request', side_effect=cv), patch.object(versedb, 'request', side_effect=vdb):
                    cv_result = comicvine_search.lookup(row_for(path), {})
                    vdb_result = versedb.lookup(row_for(path), {})
                if path == NINJAK:
                    self.assertEqual((cv_result, vdb_result, cv.asked, vdb.asked), (None, None, [], []))
                else:  # Positive control: the whole omnibus, unlabelled, is asked and matched as issue 1.
                    self.assertEqual((cv_result['match_rule'], vdb_result['match_rule']), ('unnumbered', 'unnumbered'))
        self.assertIsNone(metron.identity(row_for(NINJAK), {}))  # Metron's rule C refuses it too.


class TrailingSpaceTests(unittest.TestCase):
    def test_comicvine_fields_are_trimmed(self):
        fields = app.metadata_from_issue({'volume': {'name': 'Blade: First Bite Infinity Comic '}, 'issue_number': ' 4',
                                          'name': ' Chapter 4 ', 'site_detail_url': 'https://comicvine.gamespot.com/x/4000-1/',
                                          'person_credits': [{'name': 'Writer A ', 'role': 'writer'}], 'description': ' '})
        self.assertEqual((fields['Series'], fields['Number'], fields['Title'], fields['Writer']),
                         ('Blade: First Bite Infinity Comic', '4', 'Chapter 4', 'Writer A'))
        self.assertNotIn('Summary', fields)  # Whitespace only is no value.

    def test_the_name_search_matches_and_writes_the_trimmed_name(self):
        blade = volume(702, 'Blade: First Bite Infinity Comic ', 2023, publisher='Marvel')
        fake = FakeComicVine([blade], [cv_issue(7201, blade, '4', '2023-08-01')])
        with scratch_directory() as directory, patch.object(app, 'DATA', Path(directory) / 'data'), \
                patch.object(app, 'api_key', return_value='synthetic'), \
                patch.object(pipeline_config, 'matching', side_effect=lambda name: pipeline_config.MATCHING_DEFAULTS[name]), \
                patch.object(comicvine_search, 'request', side_effect=fake), \
                patch.object(comicvine_search, 'verified_cover', return_value={'comparison': 'today', 'page': 1}):
            result = comicvine_search.lookup(row_for(r'Y:\Comix\Marvel\Blade First Bite Infinity Comic 004 (2023).cbz'), {})
        self.assertEqual(result['fields']['Series'], 'Blade: First Bite Infinity Comic')  # Before: a trailing space.
        self.assertEqual(result['name_search']['volume'], 'Blade: First Bite Infinity Comic')
        # Positive control: the raw ComicVine name does end in a space, and the name comparison ignores it.
        self.assertTrue(blade['name'].endswith(' '))


if __name__ == '__main__':
    unittest.main()
