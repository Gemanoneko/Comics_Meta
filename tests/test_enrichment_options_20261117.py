"""Options 2, 3 and 5 (Sergei 2026-11-17, Docs/ComicsMetaOrganizer_EnrichmentDiagnosis_2026-11-17.md): Metron series
spellings and collection labels, each behind a matching switch that is off by default; spread re-asks, long-miss
back-off and the settled GCD offline miss (config "scheduling", on by default).

Mocked Metron answers, cover checks and GCD index only; nothing leaves the machine."""
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import app
import metron
import pipeline_config
import source_scheduling
from test_worker import scratch_directory


def issue(id, name, number, date, began=None, kind=None, title='', volume=None, image=None):
    series = {'name': name, 'year_began': began if began is not None else int(date[:4])}
    if volume is not None:
        series['volume'] = volume
    if kind:
        series['series_type'] = {'name': kind}
    return {'id': id, 'series': series, 'number': number, 'cover_date': date, 'title': title,
            'image': image or 'https://static.metron.cloud/%d.jpg' % id}


class WordMetron:
    """Metron's name search as observed on the live cache: every word of series_name appears in the series name
    ("Star Wars Annual" lists "Star Wars Adventures Annual 2018"); number and cover_year filter exactly."""
    def __init__(self, issues):
        self.issues, self.asked, self.details = {i['id']: i for i in issues}, [], []

    def __call__(self, endpoint, **params):
        if endpoint == 'issue/':
            self.asked.append(dict(params))
            words = params['series_name'].lower().split()
            found = [dict(i) for i in self.issues.values()
                     if all(w in i['series']['name'].lower().split() for w in words)
                     and ('number' not in params or i['number'] == params['number'])
                     and ('cover_year' not in params or i['cover_date'].startswith(str(params['cover_year'])))]
            for item in found:
                item['series'] = {k: v for k, v in item['series'].items() if k != 'series_type'}  # Lists carry no type.
            return {'count': len(found), 'next': None, 'results': found}
        self.details.append(int(endpoint.split('/')[1]))
        return dict(self.issues[int(endpoint.split('/')[1])], desc='')


def switches(**on):
    values = dict(pipeline_config.MATCHING_DEFAULTS, **on)
    return lambda name: values[name]


class Lookup(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(app, 'DATA', Path(self.enterContext(scratch_directory())) / 'data'))

    def lookup(self, fake, path, old=None, covers=lambda path, url: {'comparison': 'aligned', 'page': 1}, **on):
        row = {'path': path, 'series': app.parse_name(path)[0], 'number': app.parse_name(path)[1], 'year': app.parse_name(path)[2]}
        with patch.object(pipeline_config, 'matching', side_effect=switches(**on)), \
                patch.object(metron, 'token', return_value='synthetic'), patch.object(metron, 'request', side_effect=fake), \
                patch.object(metron, 'verified_cover', side_effect=covers):
            return metron.lookup(row, old or {})


class CollectionLabelTests(Lookup):
    SAGA = [issue(9, 'Saga', '2', '2012-04-01', began=2012, kind='Single Issue'),
            issue(902, 'Saga', '2', '2013-06-01', began=2012, kind='Trade Paperback', title='Volume Two')]

    def test_off_by_default_and_in_the_shipped_defaults(self):
        self.assertIs(pipeline_config.MATCHING_DEFAULTS['collection_label'], False)
        fake = WordMetron(self.SAGA)
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\Saga\Saga v02 (2013) (Digital).cbz'))
        self.assertEqual(fake.asked, [])  # "v02" is no issue number: today's rules cannot search it.

    def test_volume_label_is_issue_n_of_a_collection_series(self):
        for name in ('Saga v02 (2013) (Digital).cbz', 'Saga Vol. 2 (2013).cbz', 'Saga Vol 02 (2013).cbz', 'Saga Book 2 (2013).cbz'):
            fake = WordMetron(self.SAGA)
            result = self.lookup(fake, 'Y:\\Comix\\Saga\\' + name, collection_label=True)
            self.assertEqual(result['fields']['Web'], 'https://metron.cloud/issue/902/', name)
            self.assertEqual((result['match_rule'], result['fields']['Number'], result['fields']['Format']),
                             ('collection_label', '2', 'Trade Paperback'), name)
            self.assertEqual(fake.asked[0], {'series_name': 'Saga', 'cover_year': '2013'}, name)

    def test_hard_negative_same_name_number_and_year_single_issue_only(self):
        # Only an ordinary issue #2 carries that name, number and year: volume 2 is not issue 2.
        fake = WordMetron([issue(9, 'Saga', '2', '2013-04-01', began=2013, kind='Single Issue')])
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\Saga\Saga v02 (2013).cbz', collection_label=True))
        fake = WordMetron([issue(9, 'Saga', '2', '2013-04-01', began=2013, kind='One-Shot')])
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\Saga\Saga v02 (2013).cbz', collection_label=True))

    def test_issue_and_collection_sharing_name_number_and_year_pick_the_collection(self):
        both = [issue(1, 'Saga', '1', '2012-03-01', began=2012, kind='Single Issue'),
                issue(901, 'Saga', '1', '2012-10-01', began=2012, kind='Trade Paperback')]
        fake = WordMetron(both)
        result = self.lookup(fake, r'Y:\Comix\Saga\Saga v01 (2012).cbz', collection_label=True)
        self.assertEqual(result['fields']['Web'], 'https://metron.cloud/issue/901/')
        self.assertEqual(sorted(fake.details), [1, 901])  # Lists carry no series type: both details were asked.

    def test_two_collections_with_that_number_and_year_are_not_a_match(self):
        fake = WordMetron([issue(901, 'Saga', '1', '2012-10-01', kind='Trade Paperback'),
                           issue(951, 'Saga', '1', '2012-11-01', kind='Hardcover')])
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\Saga\Saga v01 (2012).cbz', collection_label=True))

    def test_a_binding_the_filename_names_must_be_the_series_type(self):
        fake = WordMetron([issue(902, 'Saga', '2', '2013-06-01', kind='Trade Paperback')])
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\Saga\Saga v02 (HC) (2013).cbz', collection_label=True))
        fake = WordMetron([issue(952, 'Saga', '2', '2013-06-01', kind='Hardcover')])
        self.assertEqual(self.lookup(fake, r'Y:\Comix\Saga\Saga v02 (HC) (2013).cbz', collection_label=True)['fields']['Web'],
                         'https://metron.cloud/issue/952/')
        fake = WordMetron([issue(952, 'Saga', '2', '2013-06-01', kind='Hardcover')])
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\Saga\Saga v02 (TPB) (2013).cbz', collection_label=True))

    def test_subtitle_must_not_name_another_book(self):
        fake = WordMetron([issue(907, 'Ice Cream Man', '7', '2022-02-23', began=2018, kind='Trade Paperback', title='Certain Descents')])
        self.assertIsNotNone(self.lookup(fake, r'Y:\Comix\ICM\Ice Cream Man v07 - Certain Descents (2022).cbz', collection_label=True))
        fake = WordMetron([issue(907, 'Ice Cream Man', '7', '2022-02-23', began=2018, kind='Trade Paperback', title='Certain Descents')])
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\ICM\Ice Cream Man v07 - Heavy Narration (2022).cbz', collection_label=True))
        fake = WordMetron([issue(902, 'Saga', '2', '2013-06-01', kind='Trade Paperback', title='Volume Two')])
        self.assertIsNotNone(self.lookup(fake, r'Y:\Comix\Saga\Saga Vol. 2 - The Long Way (2013).cbz', collection_label=True))

    def test_cover_must_still_agree(self):
        fake = WordMetron(self.SAGA)
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\Saga\Saga v02 (2013).cbz', covers=lambda path, url: False, collection_label=True))

    def test_cover_year_must_be_the_files_year(self):
        fake = WordMetron(self.SAGA)
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\Saga\Saga v02 (2014).cbz', collection_label=True))

    def test_comicinfo_that_says_something_else_keeps_the_ordinary_rules(self):
        self.assertIsNone(metron.collection_identity({'path': r'Y:\Comix\Saga\Saga v02 (2013).cbz'}, 'Saga', '2'))
        self.assertIsNone(metron.collection_identity({'path': r'Y:\Comix\Saga\Saga Vol 02 (2013).cbz'}, 'Saga Vol', '3'))
        self.assertEqual(metron.collection_identity({'path': r'Y:\Comix\Saga\Saga Vol 02 (2013).cbz'}, 'Saga Vol', '2'), ('Saga', '2', ''))
        with patch.object(pipeline_config, 'matching', side_effect=switches(collection_label=True)):
            found = metron.identity({'path': r'Y:\Comix\Saga\Saga v02 (2013).cbz', 'series': 'Saga v02', 'number': '', 'year': '2013'},
                                    {'Series': 'Saga', 'Number': '2', 'Year': '2013'})
        self.assertEqual(found, ('Saga', '2', '2013', 'year'))

    def test_no_year_or_nested_labels_are_not_collection_labels(self):
        with patch.object(pipeline_config, 'matching', side_effect=switches(collection_label=True)):
            row = {'path': r'Y:\Comix\Saga\Saga v02.cbz', 'series': 'Saga v02', 'number': '', 'year': ''}
            self.assertIsNone(metron.identity(row, {}))
            row = {'path': r'Y:\Comix\X\Conan v2 Book 3 (2005).cbz', 'series': 'Conan v2 Book 3', 'number': '', 'year': '2005'}
            self.assertNotEqual((metron.identity(row, {}) or [None] * 4)[3], 'collection_label')
            row = {'path': r'Y:\Comix\X\Batman v3 012 (2017).cbz', 'series': 'Batman v3', 'number': '12', 'year': '2017'}
            self.assertEqual(metron.identity(row, {})[3], 'year')  # A series volume with an issue number stays an issue.

    def test_switch_changes_the_rules_stamp_only_when_on(self):
        with patch.object(pipeline_config, 'matching', side_effect=switches()):
            off = metron.rules_stamp()
        with patch.object(pipeline_config, 'matching', side_effect=switches(collection_label=True)):
            on = metron.rules_stamp()
        self.assertEqual(off, '3:cover_rule_v2,filename_year_formats,folder_year,unnumbered_as_one')  # As shipped in 0.6.3.
        self.assertIn('collection_label', on)


class SpellingTests(Lookup):
    def test_off_by_default(self):
        self.assertIs(pipeline_config.MATCHING_DEFAULTS['metron_spellings'], False)
        fake = WordMetron([issue(5, 'The Walking Dead', '5', '2004-02-01', began=2003)])
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\TWD\Walking Dead 005 (2004).cbz'))

    def test_leading_the_added_reuses_the_same_search(self):
        fake = WordMetron([issue(5, 'The Walking Dead', '5', '2004-02-01', began=2003)])
        result = self.lookup(fake, r'Y:\Comix\TWD\Walking Dead 005 (2004).cbz', metron_spellings=True)
        self.assertEqual((result['fields']['Web'], result['name_spelling']), ('https://metron.cloud/issue/5/', 'add_the'))
        self.assertEqual({a['series_name'] for a in fake.asked}, {'Walking Dead'})

    def test_leading_the_dropped(self):
        fake = WordMetron([issue(7, 'Boys', '7', '2007-03-01', began=2006)])
        result = self.lookup(fake, r'Y:\Comix\Boys\The Boys 007 (2007).cbz', metron_spellings=True)
        self.assertEqual((result['fields']['Web'], result['name_spelling']), ('https://metron.cloud/issue/7/', 'drop_the'))

    def test_ampersand_and_and(self):
        fake = WordMetron([issue(3, 'Batman and Robin', '3', '2009-10-01', began=2009)])
        result = self.lookup(fake, r'Y:\Comix\BR\Batman & Robin 003 (2009).cbz', metron_spellings=True)
        self.assertEqual((result['fields']['Web'], result['name_spelling']), ('https://metron.cloud/issue/3/', 'and_ampersand'))
        fake = WordMetron([issue(4, 'Batman & Robin', '4', '2009-11-01', began=2009)])
        result = self.lookup(fake, r'Y:\Comix\BR\Batman and Robin 004 (2009).cbz', metron_spellings=True)
        self.assertEqual(result['fields']['Web'], 'https://metron.cloud/issue/4/')

    def test_series_year_must_be_the_series_start_year(self):
        runs = [issue(16, 'Batman', '1', '2016-08-01', began=2016), issue(11, 'Batman', '1', '2011-11-01', began=2011)]
        fake = WordMetron(runs)
        result = self.lookup(fake, r'Y:\Comix\B\x.cbz', old={'Series': 'Batman (2016)', 'Number': '1', 'Year': '2016'}, metron_spellings=True)
        self.assertEqual((result['fields']['Web'], result['name_spelling']), ('https://metron.cloud/issue/16/', 'series_year'))
        # Hard negative: the only "Batman" #1 of that cover year began in another year.
        fake = WordMetron([issue(11, 'Batman', '1', '2016-11-01', began=2011)])
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\B\x.cbz', old={'Series': 'Batman (2016)', 'Number': '1', 'Year': '2016'}, metron_spellings=True))

    def test_hard_negatives_identity_checks_unchanged(self):
        # The spelling finds a series, but the number, the year or the cover does not agree.
        fake = WordMetron([issue(5, 'The Walking Dead', '6', '2004-02-01')])
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\TWD\Walking Dead 005 (2004).cbz', metron_spellings=True))
        fake = WordMetron([issue(5, 'The Walking Dead', '5', '2005-02-01')])
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\TWD\Walking Dead 005 (2004).cbz', metron_spellings=True))
        fake = WordMetron([issue(5, 'The Walking Dead', '5', '2004-02-01')])
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\TWD\Walking Dead 005 (2004).cbz', covers=lambda path, url: False, metron_spellings=True))
        # Two "The" series with that number and year: not unique.
        fake = WordMetron([issue(5, 'The Walking Dead', '5', '2004-02-01', volume=1), issue(55, 'The Walking Dead', '5', '2004-09-01', volume=2)])
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\TWD\Walking Dead 005 (2004).cbz', metron_spellings=True))

    def test_a_series_found_as_filed_is_not_respelled(self):
        fake = WordMetron([issue(1, 'Boys', '1', '2006-10-01'), issue(2, 'The Boys', '1', '2006-10-01')])
        result = self.lookup(fake, r'Y:\Comix\Boys\The Boys 001 (2006).cbz', metron_spellings=True)
        self.assertEqual(result['fields']['Web'], 'https://metron.cloud/issue/2/')
        self.assertNotIn('name_spelling', result)
        self.assertEqual([a['series_name'] for a in fake.asked], ['The Boys'])

    def test_spelling_variants(self):
        self.assertEqual([(n, k, b, s) for n, k, _, b, s in metron.spelling_variants('Walking Dead')],
                         [('Walking Dead', 'thewalkingdead', None, 'add_the')])
        self.assertEqual([(n, k, s) for n, k, _, _, s in metron.spelling_variants('The Walking Dead')],
                         [('Walking Dead', 'walkingdead', 'drop_the')])
        self.assertEqual([(n, k, b, s) for n, k, _, b, s in metron.spelling_variants('Batman (2016)')],
                         [('Batman', 'batman', '2016', 'series_year'), ('Batman', 'thebatman', '2016', 'add_the')])
        self.assertIn(('Batman Robin', 'batmanandrobin', 'and_ampersand'),
                      [(n, k, s) for n, k, _, _, s in metron.spelling_variants('Batman & Robin')])
        self.assertEqual(metron.spelling_variants('The'), [])  # Nothing left once "The" is dropped.


def settings(**values):
    merged = dict(pipeline_config.SCHEDULING_DEFAULTS, **values)
    return lambda name: merged[name]


class RetrySpreadTests(unittest.TestCase):
    """Option 5: weekly re-asks spread out, long-standing misses wait 30 days."""
    DAY = 86400

    def record_misses(self, count, rules=None, start=None, **values):
        import source_scheduling
        previous = dict(start or {})
        waits = []
        with patch.object(pipeline_config, 'scheduling', side_effect=settings(**values)):
            for _ in range(count):
                previous = source_scheduling.record(previous, None, None, {}, 100, rules=rules)
                if rules is not None:
                    previous['rules'] = rules
                waits.append(previous['next_at'] - 100)
        return previous, waits

    def test_waits_without_spread_then_thirty_days_after_six_misses(self):
        _, waits = self.record_misses(8, retry_spread=0)
        self.assertEqual([w / self.DAY for w in waits], [1, 2, 4, 7, 7, 30, 30, 30])  # Before: 7 days forever.

    def test_long_miss_back_off_can_be_switched_off(self):
        _, waits = self.record_misses(8, retry_spread=0, long_miss_after=0)
        self.assertEqual([w / self.DAY for w in waits], [1, 2, 4, 7, 7, 7, 7, 7])
        _, waits = self.record_misses(7, retry_spread=0, long_miss_after=3, long_miss_days=14)
        self.assertEqual([w / self.DAY for w in waits], [1, 2, 14, 14, 14, 14, 14])

    def test_spread_stretches_each_wait_by_up_to_half(self):
        import source_scheduling
        with patch.object(source_scheduling, 'SPREAD', return_value=1.0):
            _, waits = self.record_misses(5)
        self.assertEqual([w / self.DAY for w in waits], [1.5, 3, 6, 10.5, 10.5])
        with patch.object(source_scheduling, 'SPREAD', return_value=0.0):
            _, waits = self.record_misses(5)
        self.assertEqual([w / self.DAY for w in waits], [1, 2, 4, 7, 7])
        # Comics asked the same hour come due over three and a half days, not one.
        stamps = []
        with patch.object(pipeline_config, 'scheduling', side_effect=settings()):
            for _ in range(400):
                stamps.append(source_scheduling.record({'failures': 4}, None, None, {}, 0)['next_at'])
        self.assertGreater(max(stamps) - min(stamps), 3 * self.DAY)
        self.assertTrue(all(7 * self.DAY <= s <= 10.5 * self.DAY for s in stamps))

    def test_misses_are_counted_under_the_rules_in_force(self):
        previous, _ = self.record_misses(7, rules='3:a', retry_spread=0)
        self.assertEqual(previous['failures'], 7)
        _, waits = self.record_misses(2, rules='3:b', start=previous, retry_spread=0)
        self.assertEqual([w / self.DAY for w in waits], [1, 2])  # New rules: the short waits again.
        _, waits = self.record_misses(1, rules=None, start=previous, retry_spread=0)
        self.assertEqual(waits, [30 * self.DAY])  # A source without rules keeps counting.

    def test_found_something_and_errors_are_unchanged(self):
        import source_scheduling
        from provider_wait import ProviderDeferred
        with patch.object(pipeline_config, 'scheduling', side_effect=settings()):
            self.assertEqual(source_scheduling.record({'failures': 9}, {'fields': {'Writer': 'W'}}, None, {}, 100),
                             {'result': 'verified', 'failures': 0, 'next_at': 100 + self.DAY})
            self.assertEqual(source_scheduling.record({'failures': 9}, None, ValueError('x'), {}, 100)['next_at'], 100 + 6 * 3600)
            self.assertEqual(source_scheduling.record({'failures': 9}, None, ProviderDeferred('wait', 'metron', 500), {}, 100)['next_at'], 500)

    def test_bad_settings_fall_back_to_defaults(self):
        for bad in ('x', None, -1, True, float('nan'), float('inf')):
            with patch.object(pipeline_config, 'section', return_value={'retry_spread': bad, 'long_miss_after': bad, 'gcd_offline_miss_final': bad if bad is not True else 'yes'}):
                self.assertEqual(pipeline_config.scheduling('retry_spread'), 0.5, bad)
                self.assertEqual(pipeline_config.scheduling('long_miss_after'), 6, bad)
                self.assertIs(pipeline_config.scheduling('gcd_offline_miss_final'), True, bad)
        with patch.object(pipeline_config, 'section', return_value={'retry_spread': 0, 'gcd_offline_miss_final': False}):
            self.assertEqual(pipeline_config.scheduling('retry_spread'), 0)
            self.assertIs(pipeline_config.scheduling('gcd_offline_miss_final'), False)


import test_refinement_share as share  # noqa: E402  (its classes are not re-collected: only the module is bound)


class SettledGcdMissTests(share.Fixture):
    """Option 5: a GCD offline miss under the same index and rules is final, so Enrichment A's marker works again."""
    INDEX = {'index': 'index-' + '0' * 32 + '.sqlite', 'dump_date': '2026-10-16', 'rules': 'gcd-offline-1:2026-10-16:' + '0' * 32}

    def setUp(self):
        super().setUp()
        import gcd_offline
        self.enterContext(patch.object(gcd_offline, 'current', side_effect=lambda: dict(self.INDEX)))

    def settled(self, **attempt):
        import gcd_offline
        return dict({'result': 'no_verified_match', 'failures': 1, 'next_at': 0, 'rules': gcd_offline.rules_stamp()}, **attempt)

    def test_settled_only_under_the_same_index_and_rules(self):
        self.assertTrue(source_scheduling.gcd_offline_settled(self.settled()))
        self.assertTrue(source_scheduling.gcd_offline_settled(self.settled(result='verified_no_new_data')))
        self.assertFalse(source_scheduling.gcd_offline_settled(self.settled(rules='gcd-offline-2:gcd-offline-1:2026-09-01:' + '1' * 32)))
        self.assertFalse(source_scheduling.gcd_offline_settled(self.settled(result='error')))
        self.assertFalse(source_scheduling.gcd_offline_settled(self.settled(result='unavailable')))
        self.assertFalse(source_scheduling.gcd_offline_settled({}))
        with patch.object(pipeline_config, 'scheduling', side_effect=settings(gcd_offline_miss_final=False)):
            self.assertFalse(source_scheduling.gcd_offline_settled(self.settled()))

    def test_nothing_can_search_counts_a_settled_gcd_miss(self):
        row = {'path': str(self.root / 'F' / 'Example 001.cbz'), 'series': 'Example', 'number': '1', 'year': ''}
        with patch.object(pipeline_config, 'matching', return_value=False):
            self.assertFalse(source_scheduling.nothing_can_search(row, {}))  # Before (and with no attempt): GCD offline can.
            self.assertTrue(source_scheduling.nothing_can_search(row, {}, {'GCD offline': self.settled()}))
            with patch.object(pipeline_config, 'scheduling', side_effect=settings(gcd_offline_miss_final=False)):
                self.assertFalse(source_scheduling.nothing_can_search(row, {}, {'GCD offline': self.settled()}))
        dated = {'path': str(self.root / 'F' / 'Example 001 (2024).cbz'), 'series': 'Example', 'number': '1', 'year': '2024'}
        self.assertFalse(source_scheduling.nothing_can_search(dated, {}, {'GCD offline': self.settled()}))  # Metron can.

    def test_discovery_marks_the_comic_and_a_new_dump_wakes_it(self):
        import gcd_offline
        with patch.object(pipeline_config, 'matching', side_effect=lambda name: False), \
                patch.object(gcd_offline, 'lookup', side_effect=lambda *a, **k: None):
            record = share.UnsearchableTests.discover_one(self, 'Example 001.cbz')
            self.assertEqual(record['source_schedule']['GCD offline']['rules'], gcd_offline.rules_stamp())
            self.assertEqual(record['unsearchable'], source_scheduling.search_fingerprint())  # Before: no marker.
            self.assertFalse(source_scheduling.due(record, record['signature'], record['version'], {}, now=time.time() + 400 * 86400))
            self.INDEX = dict(self.INDEX, index='index-' + '2' * 32 + '.sqlite', rules='gcd-offline-1:2026-12-01:' + '2' * 32)
            self.assertTrue(source_scheduling.due(record, record['signature'], record['version'], {}, now=time.time()))

    def test_switching_the_setting_off_wakes_marked_comics(self):
        import gcd_offline
        with patch.object(pipeline_config, 'matching', side_effect=lambda name: False), \
                patch.object(gcd_offline, 'lookup', side_effect=lambda *a, **k: None):
            record = share.UnsearchableTests.discover_one(self, 'Example 004.cbz')
            on = source_scheduling.search_fingerprint()
            with patch.object(pipeline_config, 'scheduling', side_effect=settings(gcd_offline_miss_final=False)):
                self.assertNotEqual(source_scheduling.search_fingerprint(), on)
                self.assertTrue(source_scheduling.due(record, record['signature'], record['version'], {}, now=time.time() + 400 * 86400))
            with patch.object(pipeline_config, 'scheduling', side_effect=settings(gcd_offline_miss_final=False)):
                record = share.UnsearchableTests.discover_one(self, 'Example 005.cbz')
            self.assertNotIn('unsearchable', record)  # Off: as in 0.6.3, GCD offline still counts as able to search.


class WouldWriteListingTests(unittest.TestCase):
    def test_listing_refuses_unknown_rules_and_folders_inside_the_live_state(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('metron_would_write', Path(app.BASE) / 'tools' / 'metron_would_write.py')
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        self.assertEqual(set(tool.RULES), {'collection_label', 'metron_spellings', 'yearless'})
        with self.assertRaises(SystemExit):
            tool.check_out_folder(Path(r'C:\Users\X\AppData\Local\ComicsMeta\pilot'), Path(r'C:\Users\X\AppData\Local\ComicsMeta'), Path(r'Y:\Comix'))
        with self.assertRaises(SystemExit):
            tool.check_out_folder(Path(r'Y:\Comix\pilot'), Path(r'C:\Users\X\AppData\Local\ComicsMeta'), Path(r'Y:\Comix'))
        self.assertIsNone(tool.check_out_folder(Path(r'C:\Temp\pilot'), Path(r'C:\Users\X\AppData\Local\ComicsMeta'), Path(r'Y:\Comix')))

    def load(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('metron_would_write', Path(app.BASE) / 'tools' / 'metron_would_write.py')
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        return tool

    def test_tagged_mode_reads_comicvine_tags_and_never_counts_our_own_writes(self):
        tool = self.load()
        self.assertEqual(tool.comicvine_id({'Web': 'https://comicvine.gamespot.com/saga-1/4000-337212/'}), '337212')
        self.assertEqual(tool.comicvine_id({'Notes': 'Tagged with ComicTagger 1.6 using info from Comic Vine. [Issue ID 4321]'}), '4321')
        self.assertEqual(tool.comicvine_id({'Notes': '[CVDB98765]'}), '98765')
        self.assertIsNone(tool.comicvine_id({'Notes': 'Issue ID 4321'}))  # Not said to be ComicVine's.
        self.assertIsNone(tool.comicvine_id({'Web': 'https://metron.cloud/issue/12/ https://comicvine.gamespot.com/x/4000-1/'}))
        self.assertIsNone(tool.comicvine_id({'Web': 'https://www.comics.org/issue/5/', 'Notes': '[CVDB1]'}))

    def test_tagged_mode_judges_by_cv_id_then_number_and_year(self):
        tool = self.load()
        self.assertEqual(tool.judge('100', {}, {'cv_id': 100}), 'right')
        self.assertEqual(tool.judge('100', {}, {'cv_id': 101}), 'wrong')
        old = {'Number': '2', 'Year': '2013'}
        self.assertEqual(tool.judge('100', old, {'cv_id': None, 'number': '2', 'cover_date': '2014-01-01'}), 'right_no_cv_id')
        self.assertEqual(tool.judge('100', old, {'cv_id': None, 'number': '2', 'cover_date': '2016-01-01'}), 'wrong_no_cv_id')
        self.assertEqual(tool.judge('100', old, {'number': '3', 'cover_date': '2013-01-01'}), 'wrong_no_cv_id')
        with self.assertRaises(SystemExit):
            tool.main(['--rule', 'metron_spellings', '--tagged', '--out', r'C:\Temp\never-made'])


if __name__ == '__main__':
    unittest.main()
