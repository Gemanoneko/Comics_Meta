"""ComicVine name search (Sergei 2026-11-18; pilot Team/Research/ComicsMetaOrganizer/ComicVinePilot_2026-11-17.md): a
fallback after Metron and GCD offline find nothing, on Metron's rules, off by default, with its own per-resource
ComicVine allowance that never touches the ID path's.

Mocked ComicVine answers, covers and sources only; nothing leaves the machine. Each refusal test has a positive
control beside it: with the one gate under test taken away, the same comic is accepted."""
import io
import json
import re
import time
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch
import app
import comicvine_search
import pipeline_config
import source_scheduling
from provider_wait import ProviderDeferred
from test_worker import scratch_directory

IMAGE = 'https://comicvine.gamespot.com/a/uploads/scale_medium/%d.jpg'


def volume(id, name, start, count=6, publisher='Magnetic Press'):
    return {'id': id, 'name': name, 'start_year': str(start), 'count_of_issues': count,
            'publisher': {'id': 1, 'name': publisher}}


def cv_issue(id, vol, number, date, name=''):
    return {'id': id, 'issue_number': number, 'cover_date': date, 'name': name,
            'volume': {'id': vol['id'], 'name': vol['name']}, 'image': {'medium_url': IMAGE % id},
            'site_detail_url': 'https://comicvine.gamespot.com/issue-%d/4000-%d/' % (id, id)}


class FakeComicVine:
    """search: every volume holding each word of the query (ComicVine's search is loose); issues: the filter's volumes
    and exact issue_number; issue/4000-N: the issue with credits and a description, plus any override."""
    def __init__(self, volumes, issues, overrides=None, page=None):
        self.volumes, self.issues, self.overrides, self.page, self.asked = volumes, issues, overrides or {}, page, []

    def __call__(self, resource, **params):
        self.asked.append(resource)
        if resource == 'search':
            words = params['query'].lower().split()
            return [dict(v) for v in self.volumes if all(w in v['name'].lower() for w in words)]
        if resource == 'issues':
            found = re.fullmatch(r'volume:([\d|]+),issue_number:(\S+)', params['filter'])
            ids = {int(x) for x in found[1].split('|')}
            listed = [dict(i) for i in self.issues if i['volume']['id'] in ids and i['issue_number'] == found[2]]
            return listed + (self.page or [])
        number = int(resource.split('-')[1])
        detail = dict(next(i for i in self.issues if i['id'] == number), description='<p>A verified synopsis source.</p>',
                      person_credits=[{'name': 'Writer A', 'role': 'writer'}, {'name': 'Artist B', 'role': 'penciler, cover'}],
                      character_credits=[{'name': 'Hero'}])
        detail.update(self.overrides.get(number, {}))
        return detail


def switches(**on):
    values = dict(pipeline_config.MATCHING_DEFAULTS, **on)
    return lambda name: values[name]


def row_for(path):
    series, number, year = app.parse_name(path)
    return {'path': path, 'series': series, 'number': number, 'year': year}


LUMINAE = volume(101, 'Luminae', 2016)
LUMINAE_3 = cv_issue(5003, LUMINAE, '3', '2016-09-01')


class Lookup(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(app, 'DATA', Path(self.enterContext(scratch_directory())) / 'data'))
        self.enterContext(patch.object(app, 'api_key', return_value='synthetic'))

    def lookup(self, fake, path, old=None, agree=None, schedule=None, **on):
        covers = lambda path, url: {'comparison': 'aligned', 'page': 2} if agree is None or url in agree else False
        with patch.object(pipeline_config, 'matching', side_effect=switches(**on)), \
                patch.object(comicvine_search, 'request', side_effect=fake), \
                patch.object(comicvine_search, 'verified_cover', side_effect=covers):
            return comicvine_search.lookup(row_for(path), old or {}, schedule)


class AcceptanceTests(Lookup):
    def test_year_rule_writes_identity_and_the_id_paths_fields(self):
        fake = FakeComicVine([LUMINAE], [LUMINAE_3])
        result = self.lookup(fake, r'Y:\Comix\!BD\Luminae\Luminae 003 (2016).cbz')
        fields = result['fields']
        self.assertEqual((fields['Series'], fields['Number'], fields['Year'], fields['Month']), ('Luminae', '3', '2016', '09'))
        self.assertEqual(fields['Web'], 'https://comicvine.gamespot.com/issue-5003/4000-5003/')
        self.assertEqual(fields['Publisher'], 'Magnetic Press')  # From the search answer: no volume request.
        self.assertEqual((fields['Writer'], fields['Penciller'], fields['Characters']), ('Writer A', 'Artist B', 'Hero'))
        self.assertNotIn('CoverArtist', fields)  # As the ID path: a primary issue id names no variant's artist.
        self.assertNotIn('Summary', fields)      # Synopsis review stays separate.
        self.assertEqual((result['provider'], result['match_rule'], result['status']), ('ComicVine', 'year', 'issue_verified'))
        self.assertEqual(result['cover_match'], {'comparison': 'aligned', 'page': 2, 'image': 'primary'})
        self.assertEqual(result['name_search']['issue_id'], 5003)
        self.assertEqual((result['name_search']['volume_id'], result['name_search']['query']), (101, 'Luminae'))
        self.assertEqual(result['sources'][0]['url'], fields['Web'])
        self.assertEqual(fake.asked, ['search', 'issues', 'issue/4000-5003'])

    def test_filename_date_folder_year_and_unnumbered_rules(self):
        fake = FakeComicVine([LUMINAE], [LUMINAE_3])
        self.assertEqual(self.lookup(fake, r'Y:\Comix\Luminae\Luminae 003 (2016-09).cbz')['match_rule'], 'filename_year')
        fake = FakeComicVine([LUMINAE], [cv_issue(5003, LUMINAE, '3', '2017-01-01')])
        result = self.lookup(fake, r'Y:\Comix\Luminae (2016)\Luminae 003.cbz')
        self.assertEqual(result['match_rule'], 'folder_year')  # The series' start year; the cover year may be later.
        one = volume(202, 'Tales of the Quiet Hour', 2019, count=1)
        fake = FakeComicVine([one], [cv_issue(6001, one, '1', '2019-05-01')])
        result = self.lookup(fake, r'Y:\Comix\Tales\Tales of the Quiet Hour (2019).cbz')
        self.assertEqual((result['match_rule'], result['fields']['Number']), ('unnumbered', '1'))


class RefusalTests(Lookup):
    """Hard negatives from the pilot's look-alike set, each with its positive control."""

    def test_same_name_and_number_other_run_cover_refused(self):
        # A European album against the US series of the same name, number and year: only the cover tells them apart.
        us = volume(301, 'Blackwood', 2018, publisher='Dark Horse')
        fake = FakeComicVine([us], [cv_issue(7001, us, '1', '2018-03-01')])
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\!BD\Blackwood\Blackwood 001 (2018).cbz', agree=set()))
        self.assertNotIn('issue/4000-7001', fake.asked)  # Refused before the detail request.
        control = self.lookup(FakeComicVine([us], [cv_issue(7001, us, '1', '2018-03-01')]),
                              r'Y:\Comix\!BD\Blackwood\Blackwood 001 (2018).cbz')
        self.assertEqual(control['name_search']['issue_id'], 7001)  # Positive control: cover gate removed, accepted.

    def test_two_runs_with_that_name_number_and_year_are_no_match(self):
        a, b = volume(401, 'Mercy', 2020), volume(402, 'Mercy', 2020, publisher='Image')
        fake = FakeComicVine([a, b], [cv_issue(8001, a, '1', '2020-02-01'), cv_issue(8002, b, '1', '2020-07-01')])
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\Mercy\Mercy 001 (2020).cbz'))
        fake = FakeComicVine([a], [cv_issue(8001, a, '1', '2020-02-01')])
        self.assertEqual(self.lookup(fake, r'Y:\Comix\Mercy\Mercy 001 (2020).cbz')['name_search']['issue_id'], 8001)  # Control.

    def test_other_run_with_another_cover_year_is_no_match(self):
        old_run, new_run = volume(501, 'Mercy', 1998), volume(502, 'Mercy', 2020)
        issues = [cv_issue(9001, old_run, '1', '1998-05-01'), cv_issue(9002, new_run, '1', '2020-02-01')]
        result = self.lookup(FakeComicVine([old_run, new_run], issues), r'Y:\Comix\Mercy\Mercy 001 (1998).cbz')
        self.assertEqual(result['name_search']['issue_id'], 9001)  # The year picks the 1998 run, never 2020's #1.
        self.assertIsNone(self.lookup(FakeComicVine([new_run], issues[1:]), r'Y:\Comix\Mercy\Mercy 001 (1998).cbz'))
        with patch.object(comicvine_search, 'year_agrees', return_value=True):  # Positive control: no year check.
            self.assertEqual(self.lookup(FakeComicVine([new_run], issues[1:]), r'Y:\Comix\Mercy\Mercy 001 (1998).cbz')['name_search']['issue_id'], 9002)

    def test_a_longer_series_name_is_another_series(self):
        longer = volume(601, 'Luminae Chronicles', 2016)
        fake = FakeComicVine([longer], [cv_issue(9101, longer, '3', '2016-09-01')])
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\Luminae\Luminae 003 (2016).cbz'))
        self.assertEqual(fake.asked, ['search'])  # No exact-name volume: nothing more is asked.
        import research
        with patch.object(research, 'series_key', side_effect=lambda value: 'same'):  # Control: no exact-name filter.
            self.assertIsNotNone(self.lookup(FakeComicVine([longer], [cv_issue(9101, longer, '3', '2016-09-01')]),
                                             r'Y:\Comix\Luminae\Luminae 003 (2016).cbz'))

    def test_folder_year_must_be_the_volumes_start_year(self):
        later = volume(701, 'Luminae', 2018)
        fake = FakeComicVine([later], [cv_issue(9201, later, '3', '2018-09-01')])
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\Luminae (2016)\Luminae 003.cbz'))
        fake = FakeComicVine([later], [cv_issue(9201, later, '3', '2018-09-01')])
        self.assertIsNotNone(self.lookup(fake, r'Y:\Comix\Luminae (2018)\Luminae 003.cbz'))  # Control.

    def test_unnumbered_book_needs_a_single_issue_volume(self):
        series = volume(801, 'Tales of the Quiet Hour', 2019, count=6)
        fake = FakeComicVine([series], [cv_issue(9301, series, '1', '2019-05-01')])
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\Tales\Tales of the Quiet Hour (2019).cbz'))  # Issue 1 of a run.
        one = dict(series, count_of_issues=1)
        fake = FakeComicVine([one], [cv_issue(9301, one, '1', '2019-05-01')])
        self.assertIsNotNone(self.lookup(fake, r'Y:\Comix\Tales\Tales of the Quiet Hour (2019).cbz'))  # Control.

    def test_a_full_issue_page_cannot_show_one_candidate(self):
        other = volume(901, 'Luminae', 2016)
        filler = [cv_issue(20000 + n, other, '3', '1999-01-01') for n in range(99)]
        fake = FakeComicVine([LUMINAE], [LUMINAE_3], page=filler)
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\Luminae\Luminae 003 (2016).cbz'))
        fake = FakeComicVine([LUMINAE], [LUMINAE_3], page=filler[:98])
        self.assertIsNotNone(self.lookup(fake, r'Y:\Comix\Luminae\Luminae 003 (2016).cbz'))  # Control: 99 is a whole list.

    def test_details_must_name_the_same_issue_series_number_and_year(self):
        path = r'Y:\Comix\Luminae\Luminae 003 (2016).cbz'
        for override in ({'issue_number': '4'}, {'volume': {'id': 101, 'name': 'Luminae Chronicles'}},
                         {'volume': {'id': 999, 'name': 'Luminae'}}, {'cover_date': '2017-01-01'}, {'id': 1}):
            self.assertIsNone(self.lookup(FakeComicVine([LUMINAE], [LUMINAE_3], {5003: override}), path), override)
        self.assertIsNotNone(self.lookup(FakeComicVine([LUMINAE], [LUMINAE_3], {5003: {}}), path))  # Control.

    def test_a_different_detail_image_is_checked_again(self):
        other = {'image': {'medium_url': IMAGE % 1}}
        fake = FakeComicVine([LUMINAE], [LUMINAE_3], {5003: other})
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\Luminae\Luminae 003 (2016).cbz', agree={IMAGE % 5003}))
        fake = FakeComicVine([LUMINAE], [LUMINAE_3], {5003: other})
        self.assertIsNotNone(self.lookup(fake, r'Y:\Comix\Luminae\Luminae 003 (2016).cbz', agree={IMAGE % 5003, IMAGE % 1}))


class ScopeTests(Lookup):
    def test_rules_left_out_ask_nothing_whatever_metrons_switches_say(self):
        fake = FakeComicVine([LUMINAE], [LUMINAE_3])
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\Luminae\Luminae 003.cbz'))  # Numbered, no year anywhere.
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\Luminae\Luminae 003.cbz', yearless=True))  # Metron's B3 on.
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\Luminae\Luminae.cbz'))  # Unnumbered and no year.
        self.assertEqual(fake.asked, [])
        # Metron's collection label switched on does not change what the name search asks.
        import metron
        saga = row_for(r'Y:\Comix\Saga\Saga v02 (2013).cbz')
        with patch.object(pipeline_config, 'matching', side_effect=switches(collection_label=True, yearless=True)):
            self.assertEqual(metron.identity(saga, {})[3], 'collection_label')  # Control: Metron's switch is on.
            self.assertEqual(metron.identity(row_for(r'Y:\Comix\Luminae\Luminae 003.cbz'), {})[3], 'yearless')
            found = comicvine_search.identity(saga, {})
            self.assertIsNone(comicvine_search.identity(row_for(r'Y:\Comix\Luminae\Luminae 003.cbz'), {}))
        self.assertNotEqual((found or ('', '', '', ''))[3], 'collection_label')

    def test_identity_is_metrons_with_its_live_defaults(self):
        import metron
        paths = [r'Y:\Comix\A\Alpha 001 (2001).cbz', r'Y:\Comix\A (1999)\Alpha 002.cbz', r'Y:\Comix\A\Alpha 003 (2003-04).cbz',
                 r'Y:\Comix\A\Alpha (2004).cbz', r'Y:\Comix\A\Alpha 004.cbz', r'Y:\Comix\A\Alpha v02 (2005).cbz',
                 r'Y:\Comix\A\Alpha Vol. 3 (2006).cbz', r'Y:\Comix\A\Alpha.cbz', r'Y:\Comix\A\Alpha 005 [2007].cbz']
        with patch.object(pipeline_config, 'matching', side_effect=switches()):
            for path in paths:
                self.assertEqual(comicvine_search.identity(row_for(path), {}), metron.identity(row_for(path), {}), path)

    def test_comics_citing_a_source_are_left_to_it(self):
        fake = FakeComicVine([LUMINAE], [LUMINAE_3])
        for old in ({'Web': 'https://comicvine.gamespot.com/x/4000-1/'}, {'Notes': 'Tagged with ComicTagger using info from Comic Vine'},
                    {'Notes': '[CVDB123]'}, {'Web': 'https://metron.cloud/issue/1/'}, {'Web': 'https://www.comics.org/issue/1/'}):
            self.assertIsNone(self.lookup(fake, r'Y:\Comix\Luminae\Luminae 003 (2016).cbz', old=old), old)
        self.assertEqual(fake.asked, [])
        self.assertIsNotNone(self.lookup(fake, r'Y:\Comix\Luminae\Luminae 003 (2016).cbz', old={'Web': 'https://example.com/'}))

    def test_runs_only_after_metron_and_gcd_offline_missed(self):
        path = r'Y:\Comix\Luminae\Luminae 003 (2016).cbz'
        miss = {'result': 'no_verified_match'}
        self.assertIsNotNone(self.lookup(FakeComicVine([LUMINAE], [LUMINAE_3]), path, schedule={'Metron': miss, 'GCD offline': miss}))
        for found in ('verified', 'verified_no_new_data'):
            fake = FakeComicVine([LUMINAE], [LUMINAE_3])
            self.assertIsNone(self.lookup(fake, path, schedule={'Metron': {'result': found}, 'GCD offline': miss}))
            self.assertEqual(fake.asked, [])
        for waiting in ({'Metron': {'result': 'unavailable'}, 'GCD offline': miss}, {'Metron': miss, 'GCD offline': {'result': 'error'}},
                        {'Metron': miss}):
            fake = FakeComicVine([LUMINAE], [LUMINAE_3])
            with self.assertRaises(ProviderDeferred) as raised:
                self.lookup(fake, path, schedule=waiting)
            self.assertEqual(raised.exception.provider, 'comicvine_search')  # Never the ID path's hold key.
            self.assertEqual(fake.asked, [])
        with patch.object(pipeline_config, 'source_enabled', side_effect=lambda name: name != 'GCD offline'):
            self.assertIsNotNone(self.lookup(FakeComicVine([LUMINAE], [LUMINAE_3]), path, schedule={'Metron': miss}))

    def test_no_key_asks_nothing(self):
        fake = FakeComicVine([LUMINAE], [LUMINAE_3])
        with patch.object(app, 'api_key', return_value=''):
            self.assertIsNone(self.lookup(fake, r'Y:\Comix\Luminae\Luminae 003 (2016).cbz'))
        self.assertEqual(fake.asked, [])


class SwitchTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app, 'STATE_ROOT', self.root))

    def config(self, value):
        (self.root / 'config.json').write_text(json.dumps(value), encoding='utf-8')

    def test_off_by_default_even_with_an_explicit_disabled_list(self):
        self.assertIn('ComicVine search', pipeline_config.OPT_IN_SOURCES)
        self.assertFalse(pipeline_config.source_enabled('ComicVine search'))
        self.config({'sources': {'disabled': []}})
        self.assertFalse(pipeline_config.source_enabled('ComicVine search'))
        self.config({'sources': {'disabled': ['GetComics', 'Image Comics']}})  # Sergei's live form (option 6).
        self.assertFalse(pipeline_config.source_enabled('ComicVine search'))
        self.config({'sources': {'disabled': ['GetComics', 'Image Comics'], 'enabled': ['ComicVine search']}})
        self.assertTrue(pipeline_config.source_enabled('ComicVine search'))
        self.assertFalse(pipeline_config.source_enabled('GCD'))  # Naming it turns on nothing else.


class BudgetTests(unittest.TestCase):
    NOW = 1_000_000.0

    def setUp(self):
        self.enterContext(patch.object(app, 'DATA', Path(self.enterContext(scratch_directory())) / 'data'))

    def rows(self, resource, origin, count, at):
        with app.db() as con:
            con.executemany('INSERT INTO comicvine_requests VALUES(?,?,?)', [(at, resource, origin)] * count)

    def test_spacing_between_its_own_requests_only(self):
        self.assertEqual(comicvine_search.reserve('search', self.NOW), 0)
        self.assertEqual(comicvine_search.reserve('issues', self.NOW + 4), 6)
        self.assertEqual(comicvine_search.reserve('issues', self.NOW + 10), 0)
        self.rows('issue', 'app', 1, self.NOW + 19)  # An ID-path request does not delay it.
        self.assertEqual(comicvine_search.reserve('issue/4000-1', self.NOW + 20), 0)

    def test_hourly_allowance_per_resource_is_a_rolling_window(self):
        self.rows('search', 'name_search', 150, self.NOW - 100)
        with self.assertRaises(ProviderDeferred) as raised:
            comicvine_search.reserve('search', self.NOW)
        self.assertEqual((raised.exception.retry_at, raised.exception.cause, raised.exception.provider),
                         (self.NOW - 100 + 3600, 'limit', 'comicvine_search'))
        self.assertEqual(comicvine_search.reserve('issues', self.NOW), 0)  # Another resource has its own allowance.
        self.assertEqual(comicvine_search.reserve('search', self.NOW + 3500 + 10), 0)  # Those slots have rolled out.

    def test_issue_allowance_keeps_room_for_the_id_path(self):
        self.rows('issue', 'name_search', 15, self.NOW - 10)
        with self.assertRaises(ProviderDeferred):
            comicvine_search.reserve('issue/4000-1', self.NOW)
        self.assertLessEqual(comicvine_search.HOURLY['issue'] + 180, 195)  # The ID path's 180 plus this stay under 200.

    def test_both_paths_together_stay_under_comicvines_limit(self):
        self.rows('search', 'app', 190, self.NOW - 10)  # The dashboard's manual search, heavily used.
        with self.assertRaises(ProviderDeferred) as raised:
            comicvine_search.reserve('search', self.NOW)
        self.assertEqual(raised.exception.cause, 'limit')

    def test_never_enters_or_delays_the_id_paths_allowance(self):
        self.rows('search', 'name_search', 149, self.NOW - 100)
        self.rows('issues', 'name_search', 149, self.NOW - 100)
        self.assertEqual(comicvine_search.reserve('search', self.NOW), 0)
        self.assertEqual(app.reserve_request(self.NOW + 1, resource='issue/4000-1'), 0)  # Not 19 s, not over budget.
        with app.db() as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM api_requests').fetchone()[0], 1)
            self.assertEqual([tuple(r) for r in con.execute("SELECT resource,origin FROM comicvine_requests WHERE origin='app'")], [('issue', 'app')])

    def test_waits_for_the_shared_cooldown_and_its_own(self):
        with app.db() as con:
            con.execute('UPDATE api_state SET blocked_until=? WHERE id=1', (self.NOW + 100,))
        with self.assertRaises(ProviderDeferred) as raised:
            comicvine_search.reserve('search', self.NOW)
        self.assertEqual((raised.exception.retry_at, raised.exception.cause), (self.NOW + 100, 'cooldown'))
        with app.db() as con:
            con.execute('UPDATE api_state SET blocked_until=0 WHERE id=1')
        comicvine_search.status_path().parent.mkdir(parents=True, exist_ok=True)
        comicvine_search.status_path().write_text(json.dumps({'status': 'rate_limit_wait', 'retry_at': self.NOW + 50}))
        with self.assertRaises(ProviderDeferred):
            comicvine_search.reserve('search', self.NOW)
        self.assertEqual(app.reserve_request(self.NOW), 0)  # The ID path does not wait for the name search's pause.

    def test_only_its_three_resources(self):
        with self.assertRaises(ValueError):
            comicvine_search.reserve('volume/4050-1', self.NOW)


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class RequestTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(app, 'DATA', Path(self.enterContext(scratch_directory())) / 'data'))
        self.enterContext(patch.object(app, 'api_key', return_value='synthetic'))
        self.enterContext(patch.object(comicvine_search, 'SPACING', 0))

    def answer(self, payload):
        return lambda request, timeout=None: Response(json.dumps(payload).encode())

    def test_answers_share_the_id_paths_cache_both_ways(self):
        detail = {'id': 7, 'issue_number': '1', 'volume': {'id': 1, 'name': 'X'}}
        with patch('urllib.request.urlopen', side_effect=self.answer({'status_code': 1, 'results': detail})) as opened:
            self.assertEqual(comicvine_search.request('issue/4000-7'), detail)
        self.assertEqual(opened.call_count, 1)
        with patch('urllib.request.urlopen', side_effect=AssertionError('no request')):
            self.assertEqual(app.api('issue/4000-7'), detail)  # The ID path reads the name search's answer.
            self.assertEqual(comicvine_search.request('issue/4000-7'), detail)
        with app.db() as con:
            con.execute('INSERT INTO cache VALUES(?,?,?)', ('issue/4000-8?format=json', json.dumps({'id': 8}), time.time()))
        with patch('urllib.request.urlopen', side_effect=AssertionError('no request')):
            self.assertEqual(comicvine_search.request('issue/4000-8'), {'id': 8})

    def test_a_rate_limit_pauses_only_the_name_search(self):
        refusal = urllib.error.HTTPError('https://comicvine.gamespot.com/api/search/', 420, 'Enhance Your Calm', {}, io.BytesIO(b'{}'))
        with patch('urllib.request.urlopen', side_effect=refusal):
            with self.assertRaises(ProviderDeferred) as raised:
                comicvine_search.request('search', query='Luminae')
        self.assertEqual((raised.exception.provider, raised.exception.cause), ('comicvine_search', 'limit'))
        status = comicvine_search.read_status()
        self.assertEqual(status['status'], 'rate_limit_wait')
        self.assertGreater(status['retry_at'], time.time() + 3500)
        with app.db() as con:
            self.assertEqual(con.execute('SELECT blocked_until FROM api_state WHERE id=1').fetchone()[0], 0)
        self.assertFalse((app.DATA / 'comicvine-status.json').exists())  # The dashboard's ComicVine line is untouched.
        self.assertEqual(app.reserve_request(), 0)
        with patch('urllib.request.urlopen', side_effect=AssertionError('no request')):
            with self.assertRaises(ProviderDeferred):
                comicvine_search.request('search', query='Other')  # Its own hour-long pause.

    def test_status_107_and_errors(self):
        with patch('urllib.request.urlopen', side_effect=self.answer({'status_code': 107})):
            with self.assertRaises(ProviderDeferred) as raised:
                comicvine_search.request('search', query='A')
        self.assertEqual(raised.exception.cause, 'limit')
        comicvine_search.status_path().unlink()
        failure = urllib.error.HTTPError('u', 500, 'x', {}, io.BytesIO(b''))
        with patch('urllib.request.urlopen', side_effect=failure):
            with self.assertRaises(ProviderDeferred) as raised:
                comicvine_search.request('search', query='B')
        self.assertEqual(raised.exception.cause, 'unreachable')
        self.assertLess(comicvine_search.read_status()['retry_at'], time.time() + 400)

    def test_cover_downloads_stay_on_comicvines_image_hosts(self):
        self.assertTrue(comicvine_search.image_allowed('https://comicvine.gamespot.com/a/uploads/scale_medium/1.jpg'))
        self.assertTrue(comicvine_search.image_allowed('https://static.comicvine.com/uploads/1.jpg'))
        for url in ('http://comicvine.gamespot.com/a.jpg', 'https://evil.example/a.jpg', 'https://comicvine.gamespot.com.evil.example/a.jpg',
                    'https://user@comicvine.gamespot.com/a.jpg', 'https://comicvine.gamespot.com:8443/a.jpg', ''):
            self.assertFalse(comicvine_search.image_allowed(url), url)
        with patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('no download')):
            self.assertIsNone(comicvine_search.download_cover('https://evil.example/a.jpg'))
        with self.assertRaises(ValueError):
            comicvine_search.SameHosts().redirect_request(None, None, 302, 'Found', {}, 'https://evil.example/a.jpg')


class SchedulingTests(unittest.TestCase):
    DAY = 86400

    def settings(self, **values):
        defaults = dict(pipeline_config.SCHEDULING_DEFAULTS, retry_spread=0, **values)
        return lambda name: defaults[name]

    def test_every_miss_waits_long(self):
        with patch.object(pipeline_config, 'scheduling', side_effect=self.settings()):
            first = source_scheduling.record({}, None, None, {}, 0, rules='r', long_miss=True)
            self.assertEqual((first['result'], first['next_at']), ('no_verified_match', 30 * self.DAY))
            self.assertEqual(source_scheduling.record({}, None, None, {}, 0, rules='r')['next_at'], self.DAY)  # Others unchanged.
            deferred = source_scheduling.record({}, None, ProviderDeferred('wait', 'comicvine_search', 500), {}, 0, long_miss=True)
            self.assertEqual(deferred['next_at'], 500)  # A wait is not a miss.
        with patch.object(pipeline_config, 'scheduling', side_effect=self.settings(long_miss_days=0)):
            self.assertEqual(source_scheduling.record({}, None, None, {}, 0, long_miss=True)['next_at'], self.DAY)
        self.assertIn('ComicVine search', source_scheduling.LONG_MISS_SOURCES)
        self.assertNotIn('Metron', source_scheduling.LONG_MISS_SOURCES)

    def test_a_miss_under_other_rules_is_asked_again(self):
        stamp = comicvine_search.rules_stamp()
        attempt = {'result': 'no_verified_match', 'next_at': time.time() + 30 * self.DAY, 'rules': stamp}
        self.assertFalse(source_scheduling.ready('ComicVine search', attempt, {}, time.time()))
        self.assertTrue(source_scheduling.ready('ComicVine search', dict(attempt, rules='cv-search-0:'), {}, time.time()))
        with patch.object(pipeline_config, 'matching', side_effect=switches(folder_year=False)):
            self.assertNotEqual(comicvine_search.rules_stamp(), stamp)
        with patch.object(pipeline_config, 'matching', side_effect=switches(collection_label=True, yearless=True)):
            self.assertEqual(comicvine_search.rules_stamp(), stamp)  # Metron-only switches never wake its misses.

    def test_marker_and_fingerprint(self):
        unsearchable = {'path': r'Y:\Comix\A\Alpha.cbz', 'series': 'Alpha', 'number': '', 'year': ''}
        on = lambda name: name in ('Metron', 'ComicVine search')
        with patch.object(pipeline_config, 'source_enabled', side_effect=on), \
                patch.object(pipeline_config, 'matching', side_effect=switches()):
            self.assertFalse(source_scheduling.can_search('ComicVine search', unsearchable, {}))
            self.assertTrue(source_scheduling.nothing_can_search(unsearchable, {}))
            with patch.object(comicvine_search, 'can_search', return_value=True):  # Positive control: the branch decides.
                self.assertFalse(source_scheduling.nothing_can_search(unsearchable, {}))
            dated = dict(unsearchable, path=r'Y:\Comix\A\Alpha 001 (2001).cbz', number='1', year='2001')
            self.assertTrue(source_scheduling.can_search('ComicVine search', dated, {}))
            self.assertFalse(source_scheduling.can_search('ComicVine search', dated, {'Web': 'https://comicvine.gamespot.com/a/4000-1/'}))
            with_search = source_scheduling.search_fingerprint()
        with patch.object(pipeline_config, 'source_enabled', side_effect=lambda name: name == 'Metron'):
            self.assertEqual(source_scheduling.search_fingerprint(), with_search)  # Switching it wakes no marked comic.
        with patch.object(pipeline_config, 'source_enabled', side_effect=lambda name: name == 'ComicVine search'):
            self.assertIn('ComicVine search', source_scheduling.search_fingerprint()['sources'])  # Without Metron it counts.

    def test_switching_on_makes_unresolved_comics_due_once(self):
        import metron
        now = time.time()
        waiting = {'result': 'no_verified_match', 'next_at': now + 20 * self.DAY, 'failures': 6}
        previous = {'version': 9, 'signature': [1, 1], 'outcome': 'needs_identity_lookup', 'retry_at': now - 1,
                    'source_schedule': {'Metron': dict(waiting, rules=metron.rules_stamp()), 'GCD offline': dict(waiting)}}
        off = lambda name: name in ('Metron', 'GCD offline')
        on = lambda name: name in ('Metron', 'GCD offline', 'ComicVine search')
        import gcd_offline
        with patch.object(gcd_offline, 'current', return_value=None):
            with patch.object(pipeline_config, 'source_enabled', side_effect=off):
                self.assertFalse(source_scheduling.due(previous, [1, 1], 9, {}, now=now))
            with patch.object(pipeline_config, 'source_enabled', side_effect=on):
                self.assertTrue(source_scheduling.due(previous, [1, 1], 9, {}, now=now))  # Never asked by the name search.
                asked = dict(previous, source_schedule=dict(previous['source_schedule'], **{'ComicVine search': dict(
                    waiting, rules=comicvine_search.rules_stamp())}))
                self.assertFalse(source_scheduling.due(asked, [1, 1], 9, {}, now=now))  # Asked: waits with the others.


import test_refinement_share as share  # noqa: E402  (its classes are not re-collected: only the module is bound)


class DiscoveryTests(share.Fixture):
    """One discovery pass: Metron and GCD offline mocked to miss, the name search's ComicVine answers faked."""

    def discover(self, name, enabled=True, metron_result=None, metron_error=None):
        import archive_conversion, automatic, cover_tasks, gcd_offline, local_model, metron, publisher_catalogs, research, research_runtime, worker
        from contextlib import ExitStack
        if enabled:
            (self.fixture / 'config.json').write_text(json.dumps({'sources': {'enabled': ['ComicVine search']}}), encoding='utf-8')
        folder = self.root / 'F'
        folder.mkdir(exist_ok=True)
        path = folder / name
        path.write_bytes(b'isolated fixture')
        stat = path.stat()
        series, number, year = app.parse_name(path)
        with app.db() as con:
            con.execute('INSERT INTO comics(path,root,size,mtime,series,number,year,metadata,status,seen) VALUES(?,?,?,?,?,?,?,?,?,?)',
                        (str(path), str(folder), stat.st_size, stat.st_mtime_ns, series, number, year, '{}', 'missing', 1))

        def metron_lookup(row, old):
            if metron_error:
                raise metron_error
            return metron_result
        self.fake = FakeComicVine([LUMINAE], [LUMINAE_3])
        nothing = lambda *args, **kwargs: None
        patches = [patch.object(app, 'scan'), patch.object(archive_conversion, 'one', return_value=False),
                   patch.object(worker.pause_control, 'requested', return_value=False), patch.object(automatic.batch, 'progress'),
                   patch.object(research_runtime, 'reuse', return_value=None), patch.object(metron, 'token', return_value='synthetic'),
                   patch.object(metron, 'lookup', side_effect=metron_lookup), patch.object(gcd_offline, 'lookup', side_effect=nothing),
                   patch.object(research, 'publisher_lookup', side_effect=nothing), patch.object(research, 'resolve_leads', side_effect=nothing),
                   patch.object(local_model, 'available', return_value=False), patch.object(cover_tasks, 'enqueue'),
                   patch.object(publisher_catalogs, 'lookup', side_effect=nothing),
                   patch.object(app, 'api', side_effect=AssertionError('no ComicVine ID-path call')),
                   patch.object(app, 'api_key', return_value='synthetic'),
                   patch.object(comicvine_search, 'request', side_effect=self.fake),
                   patch.object(comicvine_search, 'verified_cover', return_value={'comparison': 'today', 'page': 1})]
        with ExitStack() as stack:
            for item in patches:
                stack.enter_context(item)
            automatic.discover(folder)
        with app.db() as con:
            record = json.loads(con.execute('SELECT value FROM discovery_records WHERE path=?', (str(path.resolve()),)).fetchone()[0])
        plans = [json.loads(p.read_text(encoding='utf-8')) for p in (self.fixture / 'batches').glob('*/plan.json')]
        return record, [e for plan in plans for e in plan['entries']]

    def test_a_match_after_metron_and_gcd_missed_is_planned_with_its_evidence(self):
        record, entries = self.discover('Luminae 003 (2016).cbz')
        self.assertEqual(record['outcome'], 'queued')
        self.assertEqual(record['source_schedule']['ComicVine search']['result'], 'verified')
        self.assertEqual(record['source_schedule']['ComicVine search']['rules'], comicvine_search.rules_stamp())
        self.assertEqual(record['source_schedule']['Metron']['result'], 'no_verified_match')
        (entry,) = entries
        self.assertEqual(entry['match_rule'], 'year')
        self.assertEqual(entry['cover_match'], {'comparison': 'today', 'page': 1, 'image': 'primary'})
        self.assertEqual(entry['name_search']['issue_id'], 5003)
        self.assertEqual(entry['fields']['Web'], 'https://comicvine.gamespot.com/issue-5003/4000-5003/')
        self.assertTrue(entry['fields']['Notes'].startswith('Automatic verified lookup: ComicVine. '))
        self.assertIn('https://comicvine.gamespot.com/issue-5003/4000-5003/', entry['fields']['Notes'])
        self.assertEqual(self.fake.asked, ['search', 'issues', 'issue/4000-5003'])

    def test_off_by_default_asks_nothing_and_records_nothing(self):
        record, entries = self.discover('Luminae 003 (2016).cbz', enabled=False)
        self.assertEqual(entries, [])
        self.assertEqual(self.fake.asked, [])
        self.assertNotIn('ComicVine search', record['source_schedule'])
        self.assertEqual(record['outcome'], 'needs_identity_lookup')

    def test_not_asked_when_metron_found_the_comic(self):
        found = {'provider': 'Metron', 'metadata_version': 2, 'match_rule': 'year', 'status': 'issue_verified',
                 'fields': {'Series': 'Luminae', 'Number': '3', 'Web': 'https://metron.cloud/issue/1/'},
                 'sources': [{'url': 'https://metron.cloud/issue/1/', 'text': ''}]}
        record, entries = self.discover('Luminae 003 (2016).cbz', metron_result=found)
        self.assertEqual(self.fake.asked, [])
        self.assertNotIn('ComicVine search', record['source_schedule'])
        self.assertEqual(entries[0]['fields']['Web'], 'https://metron.cloud/issue/1/')

    def test_waits_while_metron_cannot_answer(self):
        record, entries = self.discover('Luminae 003 (2016).cbz', metron_error=ProviderDeferred('Metron waits', 'metron', time.time() + 600))
        self.assertEqual(self.fake.asked, [])
        self.assertEqual(entries, [])
        attempt = record['source_schedule']['ComicVine search']
        self.assertEqual((attempt['result'], attempt['failures']), ('unavailable', 0))
        self.assertIn('comicvine_search', record['provider_waits'])
        self.assertNotIn('comicvine', record['provider_waits'])  # The ID path's hold logic never sees it.


class WouldWriteToolTests(unittest.TestCase):
    def load(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('comicvine_would_write', Path(app.BASE) / 'tools' / 'comicvine_would_write.py')
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        return tool

    def test_tagged_mode_never_counts_this_apps_own_comicvine_writes(self):
        tool = self.load()
        shared = tool.metron_tool()
        self.assertEqual(tool.tag_id({'Web': 'https://comicvine.gamespot.com/saga-1/4000-337212/'}, shared), '337212')
        self.assertEqual(tool.tag_id({'Notes': 'Tagged with ComicTagger using info from Comic Vine. [Issue ID 4321]'}, shared), '4321')
        own = {'Web': 'https://comicvine.gamespot.com/x/4000-9/', 'Notes': 'Automatic verified lookup: ComicVine. Issue or edition identity checked'}
        self.assertIsNone(tool.tag_id(own, shared))
        self.assertIsNone(tool.tag_id({'Web': 'https://comicvine.gamespot.com/x/4000-9/', 'Notes': 'Automatic match: unique exact series and publisher'}, shared))

    def test_refuses_an_output_folder_inside_the_live_state_or_library(self):
        tool = self.load()
        with self.assertRaises(SystemExit):
            tool.main(['--out', r'C:\Users\X\AppData\Local\ComicsMeta\cv', '--live', r'C:\Users\X\AppData\Local\ComicsMeta'])


if __name__ == '__main__':
    unittest.main()
