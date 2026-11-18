"""Code review v0.6.5 (Docs/ComicsMetaOrganizer_CodeReview_v0.6.5_2026-11-18.md): S1 saved results outlive a source
switch, S2 the ID path's ComicVine headroom, S3 inline pacing in the discovery thread, N2 the snapshot URI.

Each test has a positive control: with the fix taken away (a patched constant or the old expression), the same
setup shows the finding again. Mocked sources only; nothing leaves the machine."""
import json
import sqlite3
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import app
import comicvine_search
import pipeline_config
import research_runtime
import source_scheduling
import versedb
from provider_wait import PacingDeferred, ProviderDeferred
from test_worker import scratch_directory

import test_refinement_share as share  # noqa: E402  (its classes are not re-collected: only the module is bound)


def on(*names):
    return lambda name: name in names


class SavedResultTests(unittest.TestCase):
    """S1: a saved result is planned again only while its source is on and its rules still hold."""

    def versedb_result(self, rules=None):
        return {'provider': 'VerseDB', 'match_rule': 'year', 'fields': {'Series': 'X', 'Web': 'https://versedb.com/issue/1/x'},
                'name_search': {'rules': rules or versedb.rules_stamp()}, 'sources': [{'url': 'https://versedb.com/issue/1/x'}]}

    def test_fallback_results_need_their_switch_and_their_rules(self):
        cv = {'provider': 'ComicVine', 'name_search': {'rules': comicvine_search.rules_stamp()}, 'fields': {}}
        with patch.object(pipeline_config, 'source_enabled', side_effect=on('VerseDB', 'ComicVine search')):
            self.assertTrue(source_scheduling.reusable(self.versedb_result()))  # Control: on, same rules.
            self.assertTrue(source_scheduling.reusable(cv))
            self.assertFalse(source_scheduling.reusable(self.versedb_result('versedb-0:')))
            self.assertFalse(source_scheduling.reusable(dict(cv, name_search={'rules': 'cv-search-0:'})))
        with patch.object(pipeline_config, 'source_enabled', side_effect=on()):
            self.assertFalse(source_scheduling.reusable(self.versedb_result()))
            self.assertFalse(source_scheduling.reusable(cv))
            # The ComicVine ID path's own issue text has no switch: unchanged.
            self.assertTrue(source_scheduling.reusable({'provider': 'ComicVine', 'fields': {}}))
            self.assertTrue(source_scheduling.reusable({'provider': 'Verified web research', 'fields': {}}))

    def test_metron_and_gcd_offline_follow_their_switches_and_rules(self):
        import gcd_offline
        metron = {'provider': 'Metron', 'match_rule': 'folder_year', 'cover_match': {'comparison': 'aligned'}}
        values = dict(pipeline_config.MATCHING_DEFAULTS)
        with patch.object(pipeline_config, 'matching', side_effect=lambda name: values[name]):
            self.assertTrue(source_scheduling.reusable(metron))  # Control: Metron on, its rule's switch on.
            with patch.object(pipeline_config, 'source_enabled', side_effect=on()):
                self.assertFalse(source_scheduling.reusable(metron))
            values['folder_year'] = False
            self.assertFalse(source_scheduling.reusable(metron))
            values.update(folder_year=True, cover_rule_v2=False)
            self.assertFalse(source_scheduling.reusable(metron))  # Accepted by the revised cover rule, now off.
            values['cover_rule_v2'] = True
            self.assertFalse(source_scheduling.reusable(dict(metron, name_spelling='add_the')))  # Spellings are off.
            self.assertTrue(source_scheduling.reusable(dict(metron, match_rule='year')))
        with patch.object(gcd_offline, 'rules_stamp', return_value='gcd-new'):
            self.assertTrue(source_scheduling.reusable({'provider': 'GCD offline', 'rules': 'gcd-new'}))
            self.assertFalse(source_scheduling.reusable({'provider': 'GCD offline', 'rules': 'gcd-old'}))
            with patch.object(pipeline_config, 'source_enabled', side_effect=on()):
                self.assertFalse(source_scheduling.reusable({'provider': 'GCD offline', 'rules': 'gcd-new'}))


class SavedResultDiscoveryTests(share.Fixture):
    """S1, the review's probe: a saved VerseDB result and VerseDB switched off."""

    def discover(self, enabled):
        import archive_conversion, automatic, cover_tasks, gcd_offline, local_model, metron, publisher_catalogs, research, worker
        from contextlib import ExitStack
        (self.fixture / 'config.json').write_text(json.dumps({'sources': {'enabled': enabled}}), encoding='utf-8')
        folder = self.root / 'F'
        folder.mkdir(exist_ok=True)
        path = folder / 'Witchblade 119 (2008).cbz'
        path.write_bytes(b'isolated fixture')
        stat = path.stat()
        with app.db() as con:
            con.execute('INSERT INTO comics(path,root,size,mtime,series,number,year,metadata,status,seen) VALUES(?,?,?,?,?,?,?,?,?,?)',
                        (str(path), str(folder), stat.st_size, stat.st_mtime_ns, 'Witchblade', '119', '2008', '{}', 'missing', 1))
        saved = {'provider': 'VerseDB', 'match_rule': 'year', 'status': 'issue_verified', 'attribution': versedb.ATTRIBUTION,
                 'fields': {'Series': 'Witchblade', 'Number': '119', 'Web': 'https://versedb.com/issue/1119/x'},
                 'name_search': {'rules': versedb.rules_stamp()}, 'sources': [{'url': 'https://versedb.com/issue/1119/x', 'text': ''}]}
        nothing = lambda *args, **kwargs: None
        patches = [patch.object(app, 'scan'), patch.object(archive_conversion, 'one', return_value=False),
                   patch.object(worker.pause_control, 'requested', return_value=False), patch.object(automatic.batch, 'progress'),
                   patch.object(research_runtime, 'reuse', return_value=dict(saved)), patch.object(metron, 'token', return_value='synthetic'),
                   patch.object(metron, 'lookup', side_effect=nothing), patch.object(gcd_offline, 'lookup', side_effect=nothing),
                   patch.object(research, 'publisher_lookup', side_effect=nothing), patch.object(research, 'resolve_leads', side_effect=nothing),
                   patch.object(local_model, 'available', return_value=False), patch.object(cover_tasks, 'enqueue'),
                   patch.object(publisher_catalogs, 'lookup', side_effect=nothing),
                   patch.object(app, 'api', side_effect=AssertionError('no ComicVine call')),
                   patch.object(versedb, 'request', side_effect=AssertionError('no VerseDB request'))]
        with ExitStack() as stack:
            for item in patches:
                stack.enter_context(item)
            automatic.discover(folder)
        plans = [json.loads(p.read_text(encoding='utf-8')) for p in (self.fixture / 'batches').glob('*/plan.json')]
        return [e for plan in plans for e in plan['entries']]

    def test_switched_off_source_is_not_written_from_saved_evidence(self):
        self.assertEqual(self.discover([]), [])  # Before the fix: a plan entry "Automatic verified lookup: VerseDB".

    def test_positive_control_switched_on_the_saved_result_is_written(self):
        (entry,) = self.discover(['VerseDB'])
        self.assertEqual(entry['fields']['Web'], 'https://versedb.com/issue/1119/x')


class ComicVineHeadroomTests(unittest.TestCase):
    """S2: both paths together stay under ComicVine's 200 per resource and hour; the ID path keeps priority."""
    NOW = 2_000_000.0

    def setUp(self):
        self.enterContext(patch.object(app, 'DATA', Path(self.enterContext(scratch_directory())) / 'data'))

    def rows(self, resource, origin, count, at):
        with app.db() as con:
            con.executemany('INSERT INTO comicvine_requests VALUES(?,?,?)', [(at, resource, origin)] * count)

    def id_path_until_refused(self, start, calls=170):
        """The review's probe: the ID path asks "search" every 20 s, within one rolling hour, until it is refused."""
        t, made = start, 0
        for _ in range(calls):
            try:
                app.reserve_request(t, resource='search')
            except ProviderDeferred as exc:
                return made, exc
            made += 1
            t += 20
        return made, None

    def test_after_the_name_search_used_its_share_the_id_path_stops_under_the_limit(self):
        self.rows('search', 'name_search', 150, self.NOW - 60)
        made, refusal = self.id_path_until_refused(self.NOW)
        with app.db() as con:
            total = con.execute("SELECT COUNT(*) FROM comicvine_requests WHERE resource='search'").fetchone()[0]
            blocked = con.execute('SELECT blocked_until FROM api_state WHERE id=1').fetchone()[0]
        self.assertEqual((made, total), (48, 198))  # Before the fix: 120 more, 241 in one rolling hour.
        self.assertEqual((refusal.provider, refusal.cause, blocked), ('comicvine', 'limit', 0))  # A local wait, no cooldown.
        self.assertIn('search requests reached their hourly limit', str(refusal))

    def test_positive_control_without_the_limit_the_probe_goes_past_200(self):
        self.rows('search', 'name_search', 150, self.NOW - 60)
        with patch.object(app, 'COMICVINE_RESOURCE_LIMIT', 10 ** 6):
            made, refusal = self.id_path_until_refused(self.NOW)
        self.assertGreater(150 + made, 200)

    def test_issue_and_volume_never_reach_the_limit_from_the_name_search(self):
        self.assertLess(comicvine_search.HOURLY['issue'] + 180, app.COMICVINE_RESOURCE_LIMIT)
        self.assertNotIn('volume', comicvine_search.HOURLY)
        # The name search's whole "issue" share and 179 ID-path requests: the ID path's 180th is still allowed.
        self.rows('issue', 'name_search', comicvine_search.HOURLY['issue'], self.NOW - 60)
        self.rows('issue', 'app', 179, self.NOW - 60)
        with app.db() as con:
            con.executemany('INSERT INTO api_requests VALUES(?)', [(self.NOW - 60,)] * 179)
        self.assertEqual(app.reserve_request(self.NOW, resource='issue/4000-1'), 0)
        with app.db() as con:
            con.execute("DELETE FROM comicvine_requests WHERE timestamp=? AND origin='app'", (self.NOW,))
            con.execute('DELETE FROM api_requests WHERE timestamp=?', (self.NOW,))
            con.execute('UPDATE api_state SET last_attempt=0 WHERE id=1')
        with patch.object(app, 'COMICVINE_RESOURCE_LIMIT', 194):  # Control: the check does guard "issue" too.
            with self.assertRaises(ProviderDeferred):
                app.reserve_request(self.NOW, resource='issue/4000-1')

    def test_the_name_search_steps_aside_after_a_manual_search(self):
        self.rows('search', 'app', 1, self.NOW - 100)
        with self.assertRaises(ProviderDeferred) as raised:
            comicvine_search.reserve('search', self.NOW)
        self.assertEqual(raised.exception.retry_at, self.NOW - 100 + comicvine_search.STEP_ASIDE)
        self.assertEqual(comicvine_search.reserve('issue/4000-1', self.NOW), 0)  # Its detail requests are not affected.
        self.assertEqual(comicvine_search.reserve('search', self.NOW - 100 + comicvine_search.STEP_ASIDE + 10), 0)
        with patch.object(comicvine_search, 'STEP_ASIDE', 0):  # Control: without the step-aside it would ask.
            self.rows('issues', 'app', 1, self.NOW + 600)
            self.assertEqual(comicvine_search.reserve('issues', self.NOW + 620), 0)


class PacingTests(unittest.TestCase):
    """S3: fallback pacing waits are bounded per discovery pass; a longer wait defers the comic."""

    def test_the_pass_budget(self):
        slept = []
        with patch.object(research_runtime.pause_control, 'sleep', side_effect=slept.append):
            with research_runtime.pacing_pass(30):
                self.assertTrue(research_runtime.pacing_wait(10))
                self.assertTrue(research_runtime.pacing_wait(12))
                self.assertFalse(research_runtime.pacing_wait(10))  # 8 s left.
                self.assertTrue(research_runtime.pacing_wait(8))
            self.assertTrue(research_runtime.pacing_wait(100))  # Outside a pass (the tools): always waits.
        self.assertEqual(slept, [10, 12, 8, 100])

    def test_a_request_the_pass_cannot_wait_for_is_deferred_not_slept(self):
        with scratch_directory() as directory, patch.object(app, 'DATA', Path(directory) / 'data'), \
                patch.object(app, 'api_key', return_value='synthetic'), \
                patch.object(research_runtime.pause_control, 'sleep', side_effect=AssertionError('no sleep')), \
                patch('urllib.request.urlopen', side_effect=AssertionError('no request')):
            with app.db() as con:
                con.execute('INSERT INTO comicvine_requests VALUES(?,?,?)', (time.time(), 'search', 'name_search'))
            with research_runtime.pacing_pass(5):
                with self.assertRaises(PacingDeferred) as raised:
                    comicvine_search.request('search', query='Luminae')
            self.assertTrue(raised.exception.pacing)
            self.assertEqual(raised.exception.provider, 'comicvine_search')
            with patch.object(versedb, 'token', return_value='synthetic'):
                with app.db() as con:
                    con.execute('INSERT INTO versedb_requests VALUES(?)', (time.time(),))
                with research_runtime.pacing_pass(5):
                    with self.assertRaises(PacingDeferred):
                        versedb.request('series', q='Luminae', limit=50)


class PacingDiscoveryTests(share.Fixture):
    """S3 in a real pass: 20 comics that each need the ComicVine name search, on a simulated clock."""

    def test_versedb_is_not_asked_while_the_name_search_is_paced(self):
        clock, records = self.run_pass(0.0, enabled=['ComicVine search', 'VerseDB'])
        later = [r for r in records if r['source_schedule']['ComicVine search']['result'] == 'unavailable']
        self.assertEqual(len(later), 19)  # Only the first comic got a request: no budget for waits.
        for record in later:
            self.assertNotIn('VerseDB', record['source_schedule'])  # No hour-long gate wait recorded.
            self.assertLessEqual(record['retry_at'] - time.time(), research_runtime.PACING_REVISIT + 120)
        first = [r for r in records if r['source_schedule']['ComicVine search']['result'] == 'no_verified_match']
        self.assertEqual([r['source_schedule']['VerseDB']['result'] for r in first], ['no_verified_match'])  # Control: asked.

    def run_pass(self, budget, enabled=('ComicVine search',)):
        import archive_conversion, automatic, cover_tasks, gcd_offline, local_model, metron, publisher_catalogs, research, worker
        from contextlib import ExitStack
        (self.fixture / 'config.json').write_text(json.dumps({'sources': {'enabled': list(enabled)}}), encoding='utf-8')
        folder = self.root / 'F'
        folder.mkdir(exist_ok=True)
        for n in range(1, 21):
            path = folder / ('Series %s 001 (2016).cbz' % chr(64 + n))
            path.write_bytes(b'isolated fixture %d' % n)
            stat = path.stat()
            with app.db() as con:
                con.execute('INSERT INTO comics(path,root,size,mtime,series,number,year,metadata,status,seen) VALUES(?,?,?,?,?,?,?,?,?,?)',
                            (str(path), str(folder), stat.st_size, stat.st_mtime_ns, 'Series %s' % chr(64 + n), '001', '2016', '{}', 'missing', 1))
        clock = {'now': time.time(), 'slept': 0.0, 'requests': 0}

        def sleep(seconds):
            clock['now'] += seconds
            clock['slept'] += seconds

        def fetch(resource, params, key, cache_key):
            clock['requests'] += 1
            return []  # No such volume: one request per comic.
        nothing = lambda *args, **kwargs: None
        patches = [patch.object(app, 'scan'), patch.object(archive_conversion, 'one', return_value=False),
                   patch.object(worker.pause_control, 'requested', return_value=False), patch.object(automatic.batch, 'progress'),
                   patch.object(research_runtime, 'reuse', return_value=None), patch.object(metron, 'token', return_value='synthetic'),
                   patch.object(metron, 'lookup', side_effect=nothing), patch.object(gcd_offline, 'lookup', side_effect=nothing),
                   patch.object(research, 'publisher_lookup', side_effect=nothing), patch.object(research, 'resolve_leads', side_effect=nothing),
                   patch.object(local_model, 'available', return_value=False), patch.object(cover_tasks, 'enqueue'),
                   patch.object(publisher_catalogs, 'lookup', side_effect=nothing),
                   patch.object(app, 'api', side_effect=AssertionError('no ID-path call')), patch.object(app, 'api_key', return_value='synthetic'),
                   patch.object(comicvine_search, 'fetch', side_effect=fetch),
                   patch.object(versedb, 'token', return_value='synthetic'),
                   patch.object(versedb, 'fetch', side_effect=lambda *a: {'data': [], 'meta': {'total': 0, 'last_page': 1}}),
                   patch.object(research_runtime.pause_control, 'sleep', side_effect=sleep),
                   patch.object(comicvine_search.time, 'time', side_effect=lambda: clock['now']),
                   patch.object(research_runtime, 'PACING_PER_PASS', budget)]
        with ExitStack() as stack:
            for item in patches:
                stack.enter_context(item)
            automatic.discover(folder)
        with app.db() as con:
            records = [json.loads(v) for (v,) in con.execute('SELECT value FROM discovery_records')]
        return clock, records

    def test_a_pass_spends_at_most_its_budget_and_revisits_the_rest_soon(self):
        clock, records = self.run_pass(30.0)
        self.assertLessEqual(clock['slept'], 30.0)
        self.assertEqual(clock['requests'], 4)  # The first at once, then three 10 s waits.
        deferred = [r for r in records if r['source_schedule']['ComicVine search']['result'] == 'unavailable']
        self.assertEqual(len(deferred), 16)
        for record in deferred:
            self.assertTrue(record['provider_waits']['comicvine_search']['pacing'])
            self.assertLessEqual(record['retry_at'] - time.time(), research_runtime.PACING_REVISIT + 120)  # Not a day.

    def test_positive_control_an_unbounded_pass_sleeps_through_every_comic(self):
        clock, records = self.run_pass(float('inf'))
        self.assertEqual(clock['requests'], 20)
        self.assertGreaterEqual(clock['slept'], 190.0)  # 19 waits of 10 s inside one pass, the review's S3.


class SnapshotUriTests(unittest.TestCase):
    """N2: the shared snapshot reads the right catalog read-only whatever the folder name holds."""

    def load(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('metron_would_write', Path(app.BASE) / 'tools' / 'metron_would_write.py')
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        return tool

    def test_hash_and_percent_in_the_live_folder(self):
        tool = self.load()
        with scratch_directory() as directory:
            live = Path(directory) / 'li#ve %41'
            (live / 'data').mkdir(parents=True)
            with sqlite3.connect(str(live / 'data' / 'catalog.sqlite')) as con:
                con.execute('CREATE TABLE marker(value TEXT)')
                con.execute("INSERT INTO marker VALUES('live catalog')")
            con.close()
            (live / 'config.json').write_text('{}', encoding='utf-8')
            before = sorted(p.name for p in Path(directory).iterdir())
            state = tool.snapshot(live, Path(directory) / 'out')
            with sqlite3.connect(str(state / 'data' / 'catalog.sqlite')) as con:
                self.assertEqual(con.execute('SELECT value FROM marker').fetchall(), [('live catalog',)])
            con.close()
            self.assertEqual(sorted(p.name for p in Path(directory).iterdir()), sorted(before + ['out']))  # No stray file.
            self.assertIn('%23', tool.readonly_uri(live / 'data' / 'catalog.sqlite'))
            # Positive control: the old URI stops at '#', so mode=ro is lost and another file is opened.
            old = 'file:' + str(live / 'data' / 'catalog.sqlite').replace('\\', '/') + '?mode=ro'
            stray = sqlite3.connect(old, uri=True)
            try:
                self.assertEqual(stray.execute("SELECT name FROM sqlite_master WHERE name='marker'").fetchall(), [])
            finally:
                stray.close()


if __name__ == '__main__':
    unittest.main()
