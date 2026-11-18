"""VerseDB (Sergei 2026-11-18; pilot Team/Research/ComicsMetaOrganizer/VerseDBPrecision_2026-11-18.md): a fallback after
Metron, GCD offline and the ComicVine name search, on Metron's rules plus a no-year rule only under `!BD`, with a
language preference, off by default, paced and capped under VerseDB's 300 an hour.

Mocked VerseDB answers, covers and sources only; nothing leaves the machine. Each refusal test has a positive control
beside it: with the one gate under test taken away, the same comic is accepted."""
import json
import time
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch
import app
import pipeline_config
import source_scheduling
import versedb
from provider_wait import ProviderDeferred
from test_worker import scratch_directory

COVER = 'https://r2.versedb.com/uploads/issues/%d/cover_lg.webp'
SECRET = 'synthetic-versedb-token-0123456789'


def series(id, name, start, end=None, language='en', publisher='Pub', number=None, kind='regular_series', count=12,
           i18n=None, aliases=None):
    return {'id': id, 'name': name, 'start_year': start, 'end_year': end, 'language': language, 'publisher_name': publisher,
            'number': number, 'publication_type': kind, 'cached_issues_count': count, 'name_i18n': i18n or {},
            'aliases_i18n': aliases or {}}


def issue(id, series_id, number, cover='2016-09-01', release=None, name=''):
    return {'id': id, 'series_id': series_id, 'issue_number': number, 'name': name, 'cover_date': cover,
            'release_date': release, 'cover_url': COVER % id, 'slug': 'issue-%d' % id}


def loose(value):
    """The fake search's own folding, independent of versedb.fold_key."""
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value).lower()) if c.isalnum() and not unicodedata.combining(c))


class FakeVerseDB:
    """series?q=: every series one of whose names holds the query's first word (VerseDB's search is loose);
    series/<id>/issues?q=: that series' issues whose number holds q."""
    def __init__(self, series_list, issues, extra=0):
        self.series, self.issues, self.extra, self.asked = series_list, issues, extra, []

    def __call__(self, path, **params):
        self.asked.append(path)
        if path == 'series':
            word = loose(params['q'].split()[0])
            found = [dict(s) for s in self.series if any(word in loose(n) for n, _ in versedb.names(s))]
            return {'data': found, 'meta': {'total': len(found), 'last_page': 1}}
        sid = int(path.split('/')[1])
        listed = [dict(i) for i in self.issues if i['series_id'] == sid and params['q'] in str(i['issue_number'])]
        return {'data': listed, 'meta': {'total': len(listed) + self.extra, 'last_page': 2 if self.extra else 1}}


def row_for(path):
    series_name, number, year = app.parse_name(path)
    return {'path': path, 'series': series_name, 'number': number, 'year': year}


WITCHBLADE = series(11, 'Witchblade', 1995, 2015, publisher='Image')
WITCHBLADE_119 = issue(1119, 11, '119', '2008-09-01', name='Witchblade #119')
CANARI_FR = series(21, 'Canari', 2014, language='fr', publisher='Soleil')
CANARI_DE = series(22, 'Cañari', 2016, language='de', publisher='Splitter')
CANARI = [issue(2102, 21, '2', None, name='La dernière vague'), issue(2202, 22, '2', None, name='Die letzte Welle')]


class Lookup(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(app, 'DATA', Path(self.enterContext(scratch_directory())) / 'data'))
        self.enterContext(patch.object(versedb, 'token', return_value=SECRET))
        self.enterContext(patch.object(pipeline_config, 'matching', side_effect=lambda name: pipeline_config.MATCHING_DEFAULTS[name]))

    def lookup(self, fake, path, old=None, agree=None, schedule=None):
        covers = lambda path, url: {'comparison': 'aligned', 'page': 1} if agree is None or url in agree else False
        with patch.object(versedb, 'request', side_effect=fake), patch.object(versedb, 'verified_cover', side_effect=covers):
            return versedb.lookup(row_for(path), old or {}, schedule)


class AcceptanceTests(Lookup):
    def test_western_year_rule_writes_the_small_field_set_and_credit(self):
        fake = FakeVerseDB([WITCHBLADE], [WITCHBLADE_119])
        result = self.lookup(fake, r'Y:\Comix\Image\Witchblade\Witchblade 119 (2008).cbz')
        self.assertEqual(result['fields'], {'Series': 'Witchblade', 'Number': '119', 'Title': 'Witchblade #119', 'Year': '2008',
                                            'Month': '09', 'Day': '01', 'Publisher': 'Image',
                                            'Web': 'https://versedb.com/issue/1119/issue-1119'})
        self.assertEqual(result['attribution'], 'Comic book data from VerseDB (https://versedb.com)')
        self.assertEqual((result['provider'], result['match_rule'], result['status']), ('VerseDB', 'year', 'issue_verified'))
        self.assertEqual(result['cover_match'], {'comparison': 'aligned', 'page': 1, 'image': 'primary'})
        search = result['name_search']
        self.assertEqual((search['series_id'], search['issue_id'], search['matched_by'], search['preferred']), (11, 1119, 'name', 'en'))
        self.assertEqual(fake.asked, ['series', 'series/11/issues'])

    def test_bd_album_with_no_year_prefers_the_french_edition(self):
        fake = FakeVerseDB([CANARI_FR, CANARI_DE], CANARI)
        result = self.lookup(fake, r'Y:\Comix\!BD\Canari\Canari 002.cbz')
        self.assertEqual((result['match_rule'], result['name_search']['issue_id'], result['name_search']['preferred']), ('yearless_bd', 2102, 'fr'))
        self.assertNotIn('Publisher', result['fields'])  # The `!BD` files are translations of the edition matched.
        self.assertNotIn('Year', result['fields'])
        with patch.object(versedb, 'PREFERRED', {True: 'xx', False: 'xx'}):  # Positive control: no preference.
            self.assertIsNone(self.lookup(FakeVerseDB([CANARI_FR, CANARI_DE], CANARI), r'Y:\Comix\!BD\Canari\Canari 002.cbz'))

    def test_preference_never_filters(self):
        cinebook = series(31, 'Valerian and Laureline', 2010, language='en', publisher='Cinebook')
        fake = FakeVerseDB([cinebook], [issue(3101, 31, '1', None)])
        self.assertEqual(self.lookup(fake, r'Y:\Comix\!BD\Valerian\Valerian and Laureline 001.cbz')['name_search']['issue_id'], 3101)

    def test_accents_are_folded_not_dropped(self):
        ekho = series(41, 'Ekhö Monde Miroir', 2013, language='fr')
        fake = FakeVerseDB([ekho], [issue(4102, 41, '2', None)])
        self.assertIsNotNone(self.lookup(fake, r'Y:\Comix\!BD\Ekho monde miroir\Ekho monde miroir 002.cbz'))
        import research
        with patch.object(versedb, 'fold_key', side_effect=research.series_key):  # Control: the app's key drops "ö".
            self.assertIsNone(self.lookup(FakeVerseDB([ekho], [issue(4102, 41, '2', None)]), r'Y:\Comix\!BD\Ekho monde miroir\Ekho monde miroir 002.cbz'))

    def test_an_alias_counts_and_is_flagged(self):
        tomb = series(51, 'Tomb Raider: The Series', 1999, 2004, aliases={'en': ['Tomb Raider']})
        fake = FakeVerseDB([tomb], [issue(5128, 51, '28', '2003-01-01')])
        result = self.lookup(fake, r'Y:\Comix\Image\Tomb Raider\Tomb Raider 28 (2003).cbz')
        self.assertEqual((result['name_search']['matched_by'], result['fields']['Series']), ('alias:en', 'Tomb Raider: The Series'))

    def test_volume_label_searches_the_base_name_and_needs_that_volume(self):
        first, second = series(61, 'Ghost', 1995, 1998, number=1), series(62, 'Ghost', 1998, 2000, number=2)
        issues = [issue(6105, 61, '5', '1995-09-01'), issue(6205, 62, '5', '1998-09-01')]
        result = self.lookup(FakeVerseDB([first, second], issues), r'Y:\Comix\Dark Horse\Ghost\Ghost v2 005 (1998).cbz')
        self.assertEqual((result['name_search']['issue_id'], result['name_search']['volume']), (6205, 2))
        unnumbered = dict(second, number=None)
        self.assertIsNone(self.lookup(FakeVerseDB([first, unnumbered], issues), r'Y:\Comix\Dark Horse\Ghost\Ghost v2 005 (1998).cbz'))


class RefusalTests(Lookup):
    def test_no_year_only_under_bd(self):
        fake = FakeVerseDB([WITCHBLADE], [WITCHBLADE_119])
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\Image\Witchblade\Witchblade 119.cbz'))
        self.assertEqual(fake.asked, [])  # Western no-year: Metron's open B3 question, nothing is asked.
        self.assertIsNotNone(self.lookup(FakeVerseDB([WITCHBLADE], [WITCHBLADE_119]), r'Y:\Comix\!BD\Witchblade\Witchblade 119.cbz'))  # Control.

    def test_a_longer_series_name_is_another_series(self):
        annual = series(12, 'Witchblade Annual', 1995)
        fake = FakeVerseDB([WITCHBLADE, annual], [WITCHBLADE_119, issue(1219, 12, '119', '2008-10-01')])
        self.assertEqual(self.lookup(fake, r'Y:\Comix\Image\Witchblade\Witchblade 119 (2008).cbz')['name_search']['issue_id'], 1119)
        self.assertNotIn('series/12/issues', fake.asked)
        self.assertIsNone(self.lookup(FakeVerseDB([annual], [issue(1219, 12, '119', '2008-10-01')]),
                                      r'Y:\Comix\Image\Witchblade\Witchblade 119 (2008).cbz'))

    def test_more_than_five_candidate_series_is_no_match(self):
        many = [series(70 + n, 'Supergirl', 1990 + n) for n in range(6)]
        fake = FakeVerseDB(many, [issue(7501, 75, '1', '2025-01-01')])
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\DC\Supergirl\Supergirl 001 (2025).cbz'))
        self.assertEqual(fake.asked, ['series'])
        fake = FakeVerseDB(many[1:], [issue(7501, 75, '1', '2025-01-01')])
        self.assertEqual(self.lookup(fake, r'Y:\Comix\DC\Supergirl\Supergirl 001 (2025).cbz')['name_search']['issue_id'], 7501)  # Control.

    def test_same_name_and_number_other_year_is_no_match(self):
        other = series(81, 'Mercy', 2010)
        fake = FakeVerseDB([other], [issue(8101, 81, '1', '2011-02-01', '2010-12-20')])
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\Mercy\Mercy 001 (2016).cbz'))
        with patch.object(versedb, 'issue_year_fits', return_value=True):  # Control: no year check.
            self.assertIsNotNone(self.lookup(FakeVerseDB([other], [issue(8101, 81, '1', '2011-02-01')]), r'Y:\Comix\Mercy\Mercy 001 (2016).cbz'))
        # A release year counts as the pilot measured it.
        fake = FakeVerseDB([other], [issue(8101, 81, '1', '2017-01-01', '2016-11-20')])
        self.assertIsNotNone(self.lookup(fake, r'Y:\Comix\Mercy\Mercy 001 (2016).cbz'))

    def test_series_that_ended_before_the_year_is_not_asked(self):
        ended = series(82, 'Mercy', 1990, 1993)
        fake = FakeVerseDB([ended], [issue(8201, 82, '1', '2016-02-01')])
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\Mercy\Mercy 001 (2016).cbz'))
        self.assertEqual(fake.asked, ['series'])

    def test_cover_must_agree(self):
        fake = FakeVerseDB([WITCHBLADE], [WITCHBLADE_119])
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\Image\Witchblade\Witchblade 119 (2008).cbz', agree=set()))
        self.assertIsNotNone(self.lookup(FakeVerseDB([WITCHBLADE], [WITCHBLADE_119]), r'Y:\Comix\Image\Witchblade\Witchblade 119 (2008).cbz',
                                         agree={COVER % 1119}))  # Control.

    def test_two_editions_with_that_number_in_one_language_are_no_match(self):
        a, b = series(91, 'Questor', 2010, language='fr'), series(92, 'Questor', 2012, language='fr', publisher='Other')
        fake = FakeVerseDB([a, b], [issue(9102, 91, '2', None), issue(9202, 92, '2', None)])
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\!BD\Questor\Questor 002.cbz'))
        fake = FakeVerseDB([a], [issue(9102, 91, '2', None)])
        self.assertIsNotNone(self.lookup(fake, r'Y:\Comix\!BD\Questor\Questor 002.cbz'))  # Control.

    def test_more_issue_pages_cannot_show_one_candidate(self):
        fake = FakeVerseDB([WITCHBLADE], [WITCHBLADE_119], extra=1)
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\Image\Witchblade\Witchblade 119 (2008).cbz'))

    def test_folder_year_must_be_the_series_start(self):
        later = series(93, 'Luminae', 2018)
        fake = FakeVerseDB([later], [issue(9303, 93, '3', '2019-01-01')])
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\Luminae (2016)\Luminae 003.cbz'))
        self.assertIsNotNone(self.lookup(FakeVerseDB([later], [issue(9303, 93, '3', '2019-01-01')]), r'Y:\Comix\Luminae (2018)\Luminae 003.cbz'))

    def test_unnumbered_book_needs_a_single_book_series(self):
        run = series(94, 'Tales of the Quiet Hour', 2019, count=6)
        path = r'Y:\Comix\Tales\Tales of the Quiet Hour (2019).cbz'
        self.assertIsNone(self.lookup(FakeVerseDB([run], [issue(9401, 94, '1', '2019-05-01')]), path))
        one_shot = dict(run, publication_type='one_shot')
        self.assertEqual(self.lookup(FakeVerseDB([one_shot], [issue(9401, 94, '1', '2019-05-01')]), path)['match_rule'], 'unnumbered')

    def test_names_in_other_scripts_and_cited_comics_ask_nothing(self):
        fake = FakeVerseDB([WITCHBLADE], [WITCHBLADE_119])
        self.assertIsNone(self.lookup(fake, r'Y:\Comix\!BD\Зайчик\Зайчик 002.cbz'))
        for old in ({'Web': 'https://versedb.com/issue/1/x'}, {'Web': 'https://metron.cloud/issue/1/'},
                    {'Notes': 'using info from Comic Vine'}, {'Web': 'https://www.comics.org/issue/1/'}):
            self.assertIsNone(self.lookup(fake, r'Y:\Comix\Image\Witchblade\Witchblade 119 (2008).cbz', old=old), old)
        self.assertEqual(fake.asked, [])

    def test_no_token_reports_unavailable_and_asks_nothing(self):
        fake = FakeVerseDB([WITCHBLADE], [WITCHBLADE_119])
        with patch.object(versedb, 'token', return_value=''):
            with self.assertRaises(ProviderDeferred) as raised:
                self.lookup(fake, r'Y:\Comix\Image\Witchblade\Witchblade 119 (2008).cbz')
        self.assertEqual((raised.exception.provider, raised.exception.cause), ('versedb', 'no_key'))
        self.assertEqual(fake.asked, [])

    def test_runs_after_metron_gcd_offline_and_the_comicvine_name_search(self):
        path = r'Y:\Comix\Image\Witchblade\Witchblade 119 (2008).cbz'
        miss = {'result': 'no_verified_match'}
        on = lambda name: name in ('Metron', 'GCD offline', 'ComicVine search', 'VerseDB')
        with patch.object(pipeline_config, 'source_enabled', side_effect=on):
            everyone = {'Metron': miss, 'GCD offline': miss, 'ComicVine search': miss}
            self.assertIsNotNone(self.lookup(FakeVerseDB([WITCHBLADE], [WITCHBLADE_119]), path, schedule=everyone))
            fake = FakeVerseDB([WITCHBLADE], [WITCHBLADE_119])
            self.assertIsNone(self.lookup(fake, path, schedule=dict(everyone, **{'ComicVine search': {'result': 'verified'}})))
            with self.assertRaises(ProviderDeferred):
                self.lookup(fake, path, schedule=dict(everyone, **{'ComicVine search': {'result': 'unavailable'}}))
            self.assertEqual(fake.asked, [])
        with patch.object(pipeline_config, 'source_enabled', side_effect=lambda name: name in ('Metron', 'GCD offline', 'VerseDB')):
            self.assertIsNotNone(self.lookup(FakeVerseDB([WITCHBLADE], [WITCHBLADE_119]), path, schedule={'Metron': miss, 'GCD offline': miss}))


class Response:
    def __init__(self, payload, remaining='250'):
        self.body, self.headers = json.dumps(payload).encode(), {'X-RateLimit-Remaining': remaining}

    def read(self, limit=None):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class RequestTests(unittest.TestCase):
    NOW = 1_000_000.0

    def setUp(self):
        self.enterContext(patch.object(app, 'DATA', Path(self.enterContext(scratch_directory())) / 'data'))
        self.enterContext(patch.object(versedb, 'token', return_value=SECRET))

    def no_spacing(self):
        return patch.object(versedb, 'SPACING', 0)

    def test_pacing_and_rolling_hourly_allowance(self):
        self.assertEqual(versedb.reserve(self.NOW), 0)
        self.assertEqual(versedb.reserve(self.NOW + 5), 7)
        with app.db() as con:
            con.executemany('INSERT INTO versedb_requests VALUES(?)', [(self.NOW - 100,)] * 279)
        with self.assertRaises(ProviderDeferred) as raised:
            versedb.reserve(self.NOW + 20)
        self.assertEqual((raised.exception.retry_at, raised.exception.cause), (self.NOW - 100 + 3600, 'limit'))
        self.assertEqual(versedb.reserve(self.NOW + 3600 - 99 + 12), 0)  # Those requests have rolled out.
        self.assertLessEqual(versedb.HOURLY, 300)
        self.assertGreaterEqual(versedb.SPACING, 12)

    def test_token_goes_only_in_the_header_and_answers_are_cached(self):
        seen = []

        def answer(request, timeout=None):
            seen.append(request)
            return Response({'data': [], 'meta': {'total': 0, 'last_page': 1}})
        with self.no_spacing(), patch('urllib.request.OpenerDirector.open', side_effect=answer):
            self.assertEqual(versedb.request('series', q='Witchblade', limit=50)['data'], [])
            versedb.request('series', q='Witchblade', limit=50)
        self.assertEqual(len(seen), 1)  # The second answer came from the cache.
        self.assertEqual(seen[0].full_url, 'https://versedb.com/api/v1/series?q=Witchblade&limit=50')
        self.assertEqual(seen[0].get_header('Authorization'), 'Bearer ' + SECRET)
        with app.db() as con:
            stored = ' '.join(r[0] + r[1] for r in con.execute('SELECT key,value FROM cache'))
        self.assertNotIn(SECRET, stored + versedb.status_path().read_text(encoding='utf-8'))

    def test_a_429_waits_out_retry_after_and_pauses_only_versedb(self):
        refusal = urllib.error.HTTPError('https://versedb.com/api/v1/series', 429, 'Too Many Attempts.', {'Retry-After': '120'}, None)
        with self.no_spacing(), patch('urllib.request.OpenerDirector.open', side_effect=refusal):
            with self.assertRaises(ProviderDeferred) as raised:
                versedb.request('series', q='A', limit=50)
        self.assertEqual((raised.exception.provider, raised.exception.cause), ('versedb', 'limit'))
        status = versedb.read_status()
        self.assertEqual(status['status'], 'rate_limit_wait')
        self.assertAlmostEqual(status['retry_at'], time.time() + 120, delta=5)
        self.assertNotIn(SECRET, str(raised.exception) + json.dumps(status))
        with self.no_spacing(), patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('no request')):
            with self.assertRaises(ProviderDeferred):
                versedb.request('series', q='B', limit=50)
        self.assertEqual(app.reserve_request(), 0)  # ComicVine is untouched.

    def test_a_refused_token_and_a_low_remaining_count(self):
        refusal = urllib.error.HTTPError('u', 401, 'Unauthenticated', {}, None)
        with self.no_spacing(), patch('urllib.request.OpenerDirector.open', side_effect=refusal):
            with self.assertRaises(ProviderDeferred) as raised:
                versedb.request('series', q='A', limit=50)
        self.assertEqual((raised.exception.cause, versedb.read_status()['status']), ('rejected', 'authentication_failed'))
        versedb.status_path().unlink()
        with self.no_spacing(), patch('urllib.request.OpenerDirector.open', return_value=Response({'data': []}, remaining='4')):
            versedb.request('series', q='C', limit=50)
        retry = versedb.read_status()['retry_at']
        self.assertGreater(retry, time.time())
        self.assertEqual((retry - 60) % 3600, 0)  # The next hour, when VerseDB's window starts again.

    def test_only_its_api_paths_and_no_redirects(self):
        with self.assertRaises(ValueError):
            versedb.request('user/collection')
        with self.assertRaises(ValueError):
            versedb.NoRedirect().redirect_request(None, None, 302, 'Found', {}, 'https://elsewhere.example/')

    def test_covers_only_from_versedbs_hosts(self):
        self.assertTrue(versedb.image_allowed('https://r2.versedb.com/uploads/issues/1/cover_lg.webp'))
        for url in ('http://r2.versedb.com/a.webp', 'https://versedb.com.evil.example/a.webp', 'https://evil.example/a.webp',
                    'https://user@r2.versedb.com/a.webp', ''):
            self.assertFalse(versedb.image_allowed(url), url)
        with patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('no download')):
            self.assertIsNone(versedb.download_cover('https://evil.example/a.webp'))


class SchedulingTests(unittest.TestCase):
    def test_long_misses_and_rules(self):
        self.assertIn('VerseDB', source_scheduling.LONG_MISS_SOURCES)
        stamp = versedb.rules_stamp()
        attempt = {'result': 'no_verified_match', 'next_at': time.time() + 30 * 86400, 'rules': stamp}
        self.assertFalse(source_scheduling.ready('VerseDB', attempt, {}, time.time()))
        self.assertTrue(source_scheduling.ready('VerseDB', dict(attempt, rules='versedb-0:'), {}, time.time()))

    def test_bd_comics_with_no_year_become_searchable_and_switching_on_wakes_markers(self):
        bd = {'path': r'Y:\Comix\!BD\Canari\Canari 002.cbz', 'series': 'Canari', 'number': '002', 'year': ''}
        metron_only = lambda name: name == 'Metron'
        with_versedb = lambda name: name in ('Metron', 'VerseDB')
        with patch.object(pipeline_config, 'source_enabled', side_effect=metron_only):
            self.assertTrue(source_scheduling.nothing_can_search(bd, {}))
            before = source_scheduling.search_fingerprint()
        with patch.object(pipeline_config, 'source_enabled', side_effect=with_versedb):
            self.assertTrue(source_scheduling.can_search('VerseDB', bd, {}))
            self.assertFalse(source_scheduling.nothing_can_search(bd, {}))
            self.assertNotEqual(source_scheduling.search_fingerprint(), before)  # Marked BD comics are asked again.
        western = dict(bd, path=r'Y:\Comix\Image\Canari\Canari 002.cbz')
        self.assertFalse(source_scheduling.can_search('VerseDB', western, {}))


class ArchiveMatchTests(unittest.TestCase):
    def test_pages_two_and_three_are_extra_chances_and_page_one_must_read(self):
        import cover_match, reverse_image
        pages = {0: b'credits', 1: OSError('bad CRC'), 2: b'cover'}

        def cover(path, index):
            value = pages[index]
            if isinstance(value, Exception):
                raise value
            return value, None, None
        with patch.object(reverse_image, 'cover', side_effect=cover), \
                patch.object(cover_match, 'compare', side_effect=lambda local, remote: 'aligned' if local == remote else None), \
                patch.object(pipeline_config, 'matching', return_value=True):
            self.assertEqual(cover_match.archive_match('x.cbz', b'cover'), {'comparison': 'aligned', 'page': 3})
            self.assertIs(cover_match.archive_match('x.cbz', b'other'), False)
            pages[0] = ValueError('unreadable')
            with self.assertRaises(ValueError):
                cover_match.archive_match('x.cbz', b'cover')


import test_refinement_share as share  # noqa: E402  (its classes are not re-collected: only the module is bound)


class DiscoveryTests(share.Fixture):
    def discover(self, name, folder='F', enabled=('ComicVine search', 'VerseDB'), cv_volumes=()):
        import archive_conversion, automatic, comicvine_search, cover_tasks, gcd_offline, local_model, metron, publisher_catalogs, research, research_runtime, worker
        from contextlib import ExitStack
        (self.fixture / 'config.json').write_text(json.dumps({'sources': {'enabled': list(enabled)}}), encoding='utf-8')
        directory = self.root / folder
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / name
        path.write_bytes(b'isolated fixture')
        stat = path.stat()
        series_name, number, year = app.parse_name(path)
        with app.db() as con:
            con.execute('INSERT INTO comics(path,root,size,mtime,series,number,year,metadata,status,seen) VALUES(?,?,?,?,?,?,?,?,?,?)',
                        (str(path), str(directory), stat.st_size, stat.st_mtime_ns, series_name, number, year, '{}', 'missing', 1))
        self.calls = []
        cv = lambda resource, **params: self.calls.append('comicvine:' + resource) or list(cv_volumes) if resource == 'search' else []
        self.fake = FakeVerseDB([WITCHBLADE, CANARI_FR, CANARI_DE], [WITCHBLADE_119] + CANARI)

        def verse(path, **params):
            self.calls.append('versedb:' + path)
            return self.fake(path, **params)
        nothing = lambda *args, **kwargs: None
        patches = [patch.object(app, 'scan'), patch.object(archive_conversion, 'one', return_value=False),
                   patch.object(worker.pause_control, 'requested', return_value=False), patch.object(automatic.batch, 'progress'),
                   patch.object(research_runtime, 'reuse', return_value=None), patch.object(metron, 'token', return_value='synthetic'),
                   patch.object(metron, 'lookup', side_effect=nothing), patch.object(gcd_offline, 'lookup', side_effect=nothing),
                   patch.object(research, 'publisher_lookup', side_effect=nothing), patch.object(research, 'resolve_leads', side_effect=nothing),
                   patch.object(local_model, 'available', return_value=False), patch.object(cover_tasks, 'enqueue'),
                   patch.object(publisher_catalogs, 'lookup', side_effect=nothing),
                   patch.object(app, 'api', side_effect=AssertionError('no ComicVine ID-path call')),
                   patch.object(app, 'api_key', return_value='synthetic'),
                   patch.object(comicvine_search, 'request', side_effect=cv),
                   patch.object(versedb, 'token', return_value=SECRET), patch.object(versedb, 'request', side_effect=verse),
                   patch.object(versedb, 'verified_cover', return_value={'comparison': 'today', 'page': 1})]
        with ExitStack() as stack:
            for item in patches:
                stack.enter_context(item)
            automatic.discover(directory)
        with app.db() as con:
            record = json.loads(con.execute('SELECT value FROM discovery_records WHERE path=?', (str(path.resolve()),)).fetchone()[0])
        plans = [json.loads(p.read_text(encoding='utf-8')) for p in (self.fixture / 'batches').glob('*/plan.json')]
        return record, [e for plan in plans for e in plan['entries']]

    def test_asked_after_the_comicvine_name_search_missed_with_the_credit_in_notes(self):
        record, entries = self.discover('Witchblade 119 (2008).cbz')
        self.assertEqual(self.calls, ['comicvine:search', 'versedb:series', 'versedb:series/11/issues'])
        self.assertEqual(record['source_schedule']['ComicVine search']['result'], 'no_verified_match')
        self.assertEqual(record['source_schedule']['VerseDB']['result'], 'verified')
        (entry,) = entries
        self.assertEqual((entry['match_rule'], entry['name_search']['issue_id']), ('year', 1119))
        notes = entry['fields']['Notes']
        self.assertTrue(notes.startswith('Automatic verified lookup: VerseDB. '))
        self.assertIn('https://versedb.com/issue/1119/issue-1119', notes)
        self.assertIn('\nComic book data from VerseDB (https://versedb.com)', notes)

    def test_bd_album_with_no_year_after_every_other_source(self):
        record, entries = self.discover('Canari 002.cbz', folder='!BD/Canari')
        (entry,) = entries
        self.assertEqual((entry['match_rule'], entry['fields']['Web']), ('yearless_bd', 'https://versedb.com/issue/2102/issue-2102'))
        self.assertNotIn('Publisher', entry['fields'])
        self.assertNotIn('comicvine:search', self.calls)  # The name search cannot ask a comic with no year.

    def test_not_asked_when_the_comicvine_name_search_found_it_or_when_off(self):
        import comicvine_search
        found = {'provider': 'ComicVine', 'match_rule': 'year', 'status': 'issue_verified',
                 'fields': {'Series': 'Witchblade', 'Number': '119', 'Web': 'https://comicvine.gamespot.com/x/4000-1/'},
                 'sources': [{'url': 'https://comicvine.gamespot.com/x/4000-1/', 'text': ''}]}
        with patch.object(comicvine_search, 'lookup', return_value=found):
            record, entries = self.discover('Witchblade 119 (2008).cbz')
        self.assertFalse([c for c in self.calls if c.startswith('versedb:')])
        self.assertNotIn('VerseDB', record['source_schedule'])
        self.assertEqual(entries[0]['fields']['Web'], 'https://comicvine.gamespot.com/x/4000-1/')

    def test_off_by_default(self):
        record, entries = self.discover('Witchblade 119 (2008).cbz', folder='G', enabled=())
        self.assertEqual((self.calls, entries), ([], []))
        self.assertNotIn('VerseDB', record['source_schedule'])


class WouldWriteToolTests(unittest.TestCase):
    def load(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('versedb_would_write', Path(app.BASE) / 'tools' / 'versedb_would_write.py')
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        return tool

    def test_known_identity_and_judging(self):
        tool = self.load()
        self.assertEqual(tool.known_identity({'Series': 'Canari', 'Number': '2', 'Notes': 'Tagged with ComicTagger using info from Comic Vine'}), ('Canari', '2'))
        self.assertIsNone(tool.known_identity({'Series': 'Canari', 'Number': '2'}))  # No verified source named.
        self.assertIsNone(tool.known_identity({'Series': 'Canari', 'Number': '2', 'Notes': 'Comic book data from VerseDB; Comic Vine'}))
        self.assertEqual(tool.judge(('Cañari', '2'), {'Series': 'Canari', 'Number': '2'}), 'right')
        self.assertEqual(tool.judge(('Canari', '3'), {'Series': 'Canari', 'Number': '2'}), 'check_by_hand')

    def test_refuses_an_output_folder_inside_the_live_state(self):
        with self.assertRaises(SystemExit):
            self.load().main(['--out', r'C:\Users\X\AppData\Local\ComicsMeta\v', '--live', r'C:\Users\X\AppData\Local\ComicsMeta'])


if __name__ == '__main__':
    unittest.main()
