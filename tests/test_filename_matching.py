"""Naming repairs must recover syntax without choosing an edition or identity."""
import json
import sqlite3
import unittest
from unittest.mock import patch

import app
import filename_identity as names
import gcd_matching
import gcd_offline
import metron
import research
import research_runtime
import source_scheduling


def row(path):
    series, number, year = names.legacy_parse(path)
    return dict(path=path, series=series, number=number, year=year)


class FilenameTests(unittest.TestCase):
    def test_padded_underscore_issue_and_fraction(self):
        for path, expected in [
            ('Shadowman_010_(1997)_(digital).cbz', ('Shadowman', '10', '1997')),
            ('Tarot_Witch_Of_The_Black_Rose_088(2014)(c2c).cbz', ('Tarot_Witch_Of_The_Black_Rose', '88', '2014')),
            ('Power_Girl_001_(2009).cbz', ('Power_Girl', '1', '2009')),
            ('Example_000.5_(2024).cbz', ('Example', '0.5', '2024')),
        ]:
            with self.subTest(path=path):
                self.assertEqual(app.parse_name(path), expected)

    def test_title_digits_and_unpadded_underscore_stay_unresolved(self):
        for path in ('District_9.cbz', 'District_9_(2009).cbz', '2000_AD.cbz', 'Title_12.cbz'):
            self.assertEqual(app.parse_name(path)[1], '', path)
        self.assertEqual(app.parse_name('2000_AD_001_(2024).cbz'), ('2000_AD', '1', '2024'))

    def test_ordinary_parse_and_fraction_are_preserved(self):
        for path in ('Example 001A (2024).cbz', 'Example #000.5.cbz', 'Example 001 (of 4) (2024).cbz', '2000 AD 001.cbz'):
            self.assertEqual(app.parse_name(path), names.legacy_parse(path))

    def test_scanner_requires_exact_suffix_after_annotation(self):
        path = 'Star Wars Fact File 005 (De Agostini) (2002) KFRONE HAMPTA.cbz'
        self.assertEqual(app.parse_name(path), ('Star Wars Fact File', '5', '2002'))
        for path in ('Example 005 (2002) Unknown Scanner.cbz', 'Example 005 KFRONE HAMPTA.cbz', 'Example 005 (2002) KFRONE HAMPTA extra.cbz'):
            self.assertEqual(app.parse_name(path), names.legacy_parse(path))

    def test_old_catalog_parse_refreshes_without_catalog_mutation(self):
        original = row('Power_Girl_001_(2009).cbz')
        before = dict(original)
        self.assertEqual(research.query_identity(original, {}), ('Power_Girl', '1'))
        self.assertEqual(original, before)
        self.assertEqual(research.query_identity(original, {'Series':'Chosen series','Number':'9'}), ('Chosen series','9'))
        self.assertEqual(research.query_identity(dict(original,series='Catalog override'), {}), ('Catalog override',''))

    def test_corrected_identity_does_not_reuse_old_cached_identity(self):
        original = row('Power_Girl_001_(2009).cbz')
        corrected = research_runtime.identity(original, {})
        self.assertNotEqual(corrected[:2], [research.series_key(original['series']), original['number']])
        self.assertEqual(corrected[:2], ['powergirl', '1'])

    def test_metron_keeps_yearless_disabled_and_embedded_identity(self):
        self.assertEqual(metron.identity(row('Power_Girl_001_(2009).cbz'), {})[:2], ('Power_Girl','1'))
        self.assertIsNone(metron.identity(row('Power_Girl_001.cbz'), {}))
        self.assertEqual(metron.identity(row('Power_Girl_001_(2009).cbz'), {'Series':'Chosen','Number':'8'})[:2], ('Chosen','8'))

    def test_collection_shape_does_not_turn_nested_or_fanmade_into_a_volume(self):
        self.assertEqual(names.collection('Home Sick Pilots v02 - I Wanna Be a Walking Weapon (2021).cbz'), ('Home Sick Pilots','2','I Wanna Be a Walking Weapon'))
        self.assertEqual(names.collection('Promethea Book 3 (2002).cbz'), ('Promethea','3',''))
        for path in ('The Books of Faerie Vol.2 - Auberon Book 2 (2000).cbz', 'Example v2 003 (2000).cbz', 'Example Book 2 (2024) (Fan-Made).cbz', 'Example Book 2 - Part 3 (2024).cbz'):
            self.assertIsNone(names.collection(path), path)


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(':memory:')
        self.addCleanup(self.con.close)
        self.con.row_factory = sqlite3.Row
        self.con.executescript('''
            CREATE TABLE series(id INTEGER PRIMARY KEY,name TEXT,key TEXT,sort_key TEXT,year_began INT,year_ended INT,publisher TEXT,lang TEXT,country TEXT,issue_count INT,pub_type TEXT,fmt TEXT,singleton INT);
            CREATE TABLE issue(id INTEGER PRIMARY KEY,series_id INT,number TEXT,num_key TEXT,alt_key TEXT,num_txt TEXT,alt_txt TEXT,key_date TEXT,year INT,on_sale TEXT,sale_year INT,title TEXT,barcode TEXT,isbn TEXT,page_count REAL,rating TEXT,indicia TEXT,brand TEXT,variants INT);
            CREATE TABLE fields(issue_id INTEGER PRIMARY KEY,value TEXT);
            CREATE TABLE gtin_counts(value TEXT,uses INT);
        ''')
        self.matcher = gcd_matching.Matcher(self.con)

    def candidate(self, sid=1, iid=1, series='Example', number='2', year=2021, title='The Subtitle', fmt='collected edition', pub_type='book'):
        self.con.execute('INSERT OR IGNORE INTO series VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                         (sid,series,research.series_key(series),research.series_key(series),2020,2024,'Image','en','us',6,pub_type,fmt,0))
        self.con.execute('INSERT INTO issue(id,series_id,num_key,num_txt,year,key_date,title,isbn,variants) VALUES(?,?,?,?,?,?,?,?,0)',
                         (iid,sid,number,number,year,str(year)+'-01-01',title,'9780785128908'))
        self.con.execute('INSERT INTO fields VALUES(?,?)',(iid,json.dumps({})))

    def match(self, path, old=None):
        original = row(path)
        return gcd_offline.lookup(original, old or {}, index=self.con)

    def test_volume_subtitle_requires_exact_collection_title_and_number(self):
        self.candidate()
        result = self.match('Example v02 - The Subtitle (2021).cbz')
        self.assertEqual(result['fields']['Web'], 'https://www.comics.org/issue/1/')
        self.assertEqual(result['fields']['Number'], '2')
        self.assertEqual(result['match_rule'], 'collection-label')
        self.assertIsNone(self.match('Example v03 - The Subtitle (2021).cbz'))
        self.assertIsNone(self.match('Example v02 - Other Subtitle (2021).cbz'))
        self.assertIsNone(self.match('Example v02 - The Subtitle (2022).cbz'))
        self.assertIsNone(self.match('Example v02 - The Subtitle.cbz'))

    def test_book_number_is_collection_volume_not_single_issue(self):
        self.candidate(number='3',year=2002,title='')
        self.candidate(sid=2,iid=2,number='3',year=2002,title='',fmt='ongoing series',pub_type='magazine')
        self.assertEqual(self.match('Example Book 3 (2002).cbz')['fields']['Web'], 'https://www.comics.org/issue/1/')

    def test_two_collection_editions_stay_ambiguous(self):
        self.candidate()
        self.candidate(sid=2,iid=2,fmt='hardcover')
        self.assertIsNone(self.match('Example Vol.2 - The Subtitle (2021).cbz'))

    def test_new_collection_fallback_requires_issue_date_not_series_start(self):
        self.candidate(year=2021)
        self.con.execute('UPDATE issue SET year=NULL,key_date=NULL')
        self.con.execute('UPDATE series SET year_began=2021')
        self.assertIsNone(self.match('Example Vol.2 - The Subtitle (2021).cbz'))

    def test_lookup_stamps_captured_index_not_later_pointer(self):
        self.candidate(series='Example',number='1',year=2021,title='',fmt='ongoing series',pub_type='magazine')
        from contextlib import nullcontext
        with patch.object(gcd_offline,'current',side_effect=[{'index':'index-a.sqlite','dump_date':'2026-10-16','rules':'index-A'},
                                                          {'index':'index-b.sqlite','dump_date':'2026-11-10','rules':'index-B'}]) as current, \
                patch.object(gcd_offline,'closing',return_value=nullcontext(self.con)), \
                patch.object(gcd_offline.sqlite3,'connect',return_value=self.con):
            result=gcd_offline.lookup(row('Example 001 (2021).cbz'),{})
        self.assertEqual(result['rules'],gcd_offline.RULES+':index-A')
        self.assertEqual(current.call_count,1)

    def test_hc_and_tpb_require_positive_distinct_format_evidence(self):
        self.candidate(fmt='trade paperback')
        self.candidate(sid=2,iid=2,fmt='hardcover')
        self.assertEqual(self.match('Example Vol.2 - The Subtitle (2021) (TPB).cbz')['fields']['Web'], 'https://www.comics.org/issue/1/')
        self.assertEqual(self.match('Example Vol.2 - The Subtitle (2021) (HC).cbz')['fields']['Web'], 'https://www.comics.org/issue/2/')
        self.con.execute("UPDATE series SET fmt='collected edition'")
        self.assertIsNone(self.match('Example Vol.2 - The Subtitle (2021) (HC).cbz'))
        self.assertIsNone(self.match('Example Vol.2 - The Subtitle (2021) (TPB).cbz'))

    def test_embedded_identity_or_format_disagreement_stays_held(self):
        self.candidate()
        path = 'Example Vol.2 - The Subtitle (2021).cbz'
        for old in ({'Series':'Different'}, {'Number':'9'}, {'Format':'Single Issue'}):
            self.assertIsNone(self.match(path,old), old)

    def test_language_legends_and_filename_count_are_preserved(self):
        self.candidate()
        for path in ('Star Wars Legends/Example v02 - The Subtitle (2021).cbz', 'Example v02 - The Subtitle (2021) [rus].cbz'):
            self.assertIsNone(self.match(path))
        result = self.match('Example v02 - The Subtitle (of 4) (2021).cbz')
        self.assertEqual(result['fields']['Count'], '4')

    def test_new_rule_stamp_applies_to_existing_index_and_wakes_once(self):
        with patch.object(gcd_offline,'current',return_value={'rules':'gcd-offline-1:old-index'}):
            stamp = gcd_offline.rules_stamp()
            self.assertIn('gcd-offline-2:',stamp)
            previous = {'signature':[1,2],'version':9,'outcome':'needs_identity_lookup','retry_at':9999,
                        'source_schedule':{'GCD offline':{'result':'no_verified_match','rules':'gcd-offline-1:old-index','next_at':9999}}}
            self.assertTrue(source_scheduling.due(previous,[1,2],9,{},now=1))
            previous['source_schedule']['GCD offline']['rules'] = stamp
            self.assertFalse(source_scheduling.due(previous,[1,2],9,{},now=1))

    def test_prior_exact_match_and_ambiguity_are_not_reduced_by_fallback(self):
        self.candidate(series='Example Vol.2 - The Subtitle',number='1',year=2021,fmt='one-shot',pub_type='magazine')
        self.candidate(sid=2,iid=2)
        # The explicit title exists in the index: do not substitute a shorter series.
        self.assertIsNone(self.match('Example Vol.2 - The Subtitle (2021).cbz'))
