"""#4: Yandex removed; sources that produced nothing are switched off by default, reversibly.

Isolated catalog and evidence; every engine, page and provider is mocked.
"""
import io
import json
import time
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import app
import automatic
import pipeline_config
import research
import source_scheduling as scheduling
import web_search as web
import yandex_verification
from test_worker import scratch_directory


class YandexRemovedTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app, 'DATA', self.root / 'data'))
        self.enterContext(patch.object(research, 'CACHE', self.root / 'evidence'))
        with app.db() as con:
            # The saved Yandex hold and verification state stay exactly as they are.
            con.execute('CREATE TABLE IF NOT EXISTS web_state(id INTEGER PRIMARY KEY,blocked_until REAL)')
            con.execute('INSERT INTO web_state VALUES(4,123.0)')
            con.execute('CREATE TABLE IF NOT EXISTS yandex_verification(id INTEGER PRIMARY KEY,value TEXT NOT NULL)')
            con.execute('INSERT INTO yandex_verification VALUES(1,?)', (json.dumps({'phase': 'required', 'human_verification': True}),))

    def kept(self):
        with app.db() as con:
            return (con.execute('SELECT blocked_until FROM web_state WHERE id=4').fetchone()[0],
                    json.loads(con.execute('SELECT value FROM yandex_verification WHERE id=1').fetchone()[0]))

    def test_regular_research_searches_duckduckgo_and_bing_only(self):
        engines = []
        with patch.object(web, 'search', side_effect=lambda query, free_only, engine: engines.append(engine) or []):
            research.general_lookup({'path': str(self.root / 'Example 001.cbz'), 'series': 'Example', 'number': '1'}, {})
        self.assertEqual(engines, ['ddg', 'bing'])  # Before: 'yandex' as a third engine.
        self.assertEqual(self.kept(), (123.0, {'phase': 'required', 'human_verification': True}))
        self.assertFalse(yandex_verification.active())
        self.assertNotIn('yandex', web.free_status()['engines'])

    def handler(self, path, body=None):
        handler = object.__new__(app.Handler)
        handler.server = SimpleNamespace(server_port=8765)
        handler.path = path
        handler.respond = Mock()
        raw = json.dumps(body or {}).encode()
        handler.rfile = io.BytesIO(raw)
        handler.headers = {'Origin': 'http://127.0.0.1:8765', 'Host': '127.0.0.1:8765', 'Content-Length': str(len(raw))}
        return handler

    def test_dashboard_shows_no_yandex_row_and_no_window_can_be_requested(self):
        import lens_verification, browser_search
        with patch.object(lens_verification, 'status', return_value={}), patch.object(browser_search, 'legacy_status', return_value={}):
            handler = self.handler('/api/browser-verification')
            handler.do_GET()
        self.assertIsNone(handler.respond.call_args.args[0]['yandex'])  # The dashboard keeps its Yandex row hidden.
        handler = self.handler('/api/yandex-verification', {'engine': 'yandex'})
        handler.do_POST()
        self.assertEqual(handler.respond.call_args.args[1], 400)
        self.assertIn('switched off', handler.respond.call_args.args[0]['error'])
        self.assertEqual(self.kept()[1], {'phase': 'required', 'human_verification': True})


class SourceSwitchTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app, 'BASE', self.root))

        self.enterContext(patch.object(app, 'STATE_ROOT', self.root))
        self.enterContext(patch.object(app, 'DATA', self.root / 'data'))
        self.enterContext(patch.object(research, 'CACHE', self.root / 'evidence'))
        self.now = time.time()

    def config(self, value):
        (self.root / 'config.json').write_text(json.dumps(value))

    def test_default_list_and_reversible_config(self):
        retired = {'GCD', 'Dark Horse', 'Google Books', 'Open Library local index'}  # Enrichment E (2026-10-26).
        self.assertEqual(pipeline_config.disabled_sources(), {'General free web', 'Wikipedia/wiki', 'Saved lead re-checks', 'GetComics', 'PREVIEWSworld'} | retired)
        self.assertTrue(pipeline_config.source_enabled('Metron'))
        self.config({'sources': {'disabled': []}})
        self.assertEqual(pipeline_config.disabled_sources(), retired)
        self.config({'sources': {'disabled': [], 'enabled': sorted(retired)}})
        self.assertEqual(pipeline_config.disabled_sources(), set())
        self.config({'sources': {'disabled': ['GCD']}})
        self.assertFalse(pipeline_config.source_enabled('GCD'))
        self.assertTrue(pipeline_config.source_enabled('GetComics'))

    def test_switched_off_free_attempt_does_not_make_a_comic_due(self):
        previous = {'version': 9, 'signature': [10, 1], 'retry_at': self.now + 86400,
                    'source_schedule': {'General free web': {'result': 'no_verified_match', 'next_at': self.now - 1},
                                        'GetComics': {'result': 'unavailable', 'next_at': self.now - 1}}}
        statuses = {'free_web': {'status': 'available', 'retry_at': 0}, 'getcomics': {'status': 'available'}}
        self.assertFalse(scheduling.due(previous, [10, 1], 9, statuses, now=self.now))  # Before: due every day.
        self.config({'sources': {'disabled': []}})
        self.assertTrue(scheduling.due(previous, [10, 1], 9, statuses, now=self.now))

    def discover(self, metadata, api=None):
        """One discovery pass with every source mocked. Returns [(source, strict)] in call order."""
        import archive_conversion, cover_tasks, discovery_state, getcomics, local_model, metron, open_library, providers, publisher_catalogs, research_runtime, worker
        folder = self.root / 'Example'
        folder.mkdir()
        path = folder / 'Example 001 (2024).cbz'
        path.write_bytes(b'isolated fixture')
        with app.db() as con:
            discovery_state.initialize(con)
            stat=path.stat()
            con.execute('INSERT INTO comics(path,root,size,mtime,series,number,year,metadata,status,seen) VALUES(?,?,?,?,?,?,?,?,?,?)',
                        (str(path), str(folder), stat.st_size, stat.st_mtime_ns, 'Example', '1', '2024', json.dumps(metadata), 'missing', 1))
        called = []
        def source(name):
            return lambda *args, **kwargs: called.append((name, kwargs.get('strict', False)))
        patches = [patch.object(app, 'scan'), patch.object(archive_conversion, 'one', return_value=False),
                   patch.object(providers, 'statuses', return_value={}), patch.object(worker, 'QUEUE', self.root / 'queue'),
                   patch.object(worker.pause_control, 'requested', return_value=False), patch.object(automatic.batch, 'progress'),
                   patch.object(research_runtime, 'reuse', return_value=None), patch.object(automatic, 'lookup_unidentified', return_value=None),
                   patch.object(app, 'api', side_effect=api or AssertionError('no ComicVine call')),
                   patch.object(metron, 'token', return_value='synthetic'), patch.object(metron, 'lookup', side_effect=source('Metron')),
                   patch.object(providers, 'gcd_lookup', side_effect=source('GCD')), patch.object(providers, 'google_lookup', side_effect=source('Google Books')),
                   patch.object(open_library, 'lookup', side_effect=source('Open Library')),
                   patch.object(publisher_catalogs, 'lookup', side_effect=lambda row, old, name, strict=False: called.append((name, strict))),
                   patch.object(getcomics, 'lookup', side_effect=source('GetComics')),
                   patch.object(research, 'publisher_lookup', side_effect=source('publisher')),
                   patch.object(research, 'resolve_leads', side_effect=source('saved leads')), patch.object(research, 'general_lookup', side_effect=source('free web')),
                   patch.object(research, 'wiki_candidates', side_effect=source('wiki')), patch.object(local_model, 'available', return_value=False),
                   patch.object(cover_tasks, 'enqueue')]
        with ExitStack() as stack:
            for item in patches:
                stack.enter_context(item)
            automatic.discover(folder)
        self.path = path
        return called

    def test_discovery_skips_switched_off_sources_and_records_why(self):
        called = [name for name, strict in self.discover({})]
        self.assertIn('Metron', called)
        for off in ('GetComics', 'previews_catalog', 'free web', 'wiki'):
            self.assertNotIn(off, called)  # Before: every one was tried.
        self.assertIn('image_catalog', called)  # An enabled catalog still runs (its mock takes v0.1.2's strict).
        self.assertNotIn('darkhorse_catalog', called)  # Enrichment E: off by default.
        attempts = {a['provider']: a['result'] for a in research.read_evidence(self.path)['provider_attempts']}
        self.assertEqual((attempts['GetComics'], attempts['PREVIEWSworld'], attempts['Dark Horse'], attempts['GCD']),
                         ('switched_off',) * 4)

    def test_switches_apply_on_top_of_the_strict_routes_during_a_hold(self):
        # v0.1.2: Web names a ComicVine issue that cannot be checked, so every web-verified route is strict.
        from provider_wait import ProviderDeferred
        def unavailable(resource, **params):
            raise ProviderDeferred('ComicVine is cooling down.', 'comicvine', time.time() + 300)
        called = dict(self.discover({'Series': 'Example', 'Number': '1', 'Year': '2024',
                                     'Web': 'https://comicvine.gamespot.com/example-1/4000-5/'}, unavailable))
        for off in ('GetComics', 'previews_catalog', 'free web', 'wiki'):
            self.assertNotIn(off, called)  # Switched off, strict or not.
        for name in ('image_catalog', 'publisher', 'saved leads'):  # Dark Horse is off since Enrichment E.
            self.assertIs(called[name], True, name)  # Enabled routes keep v0.1.2's strict verification.
        with app.db() as con:
            record = json.loads(con.execute('SELECT value FROM discovery_records').fetchone()[0])
        self.assertEqual(record['outcome'], 'needs_identity_lookup')  # Held.

    def test_positive_control_enabled_routes_are_not_strict_without_a_comicvine_id(self):
        called = dict(self.discover({'Series': 'Example', 'Number': '1', 'Year': '2024'}))
        for name in ('image_catalog', 'publisher', 'saved leads'):
            self.assertIs(called[name], False, name)


class SavedLeadRecheckTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app, 'BASE', self.root))

        self.enterContext(patch.object(app, 'STATE_ROOT', self.root))
        self.enterContext(patch.object(app, 'DATA', self.root / 'data'))
        self.enterContext(patch.object(research, 'CACHE', self.root / 'evidence'))
        self.row = {'path': str(self.root / 'Example 001 (2024).cbz'), 'series': 'Example', 'number': '1', 'year': '2024', 'size': 10, 'mtime': 1}
        self.old = {}
        research.save_evidence(self.row['path'], {'reverse_image_matches': [{'url': 'https://lead.example/one', 'title': 'Example #1'}]})
        self.fetched = []
        def source(url):
            self.fetched.append(url)
            return {'url': url, 'title': 'Something else entirely', 'headings': [], 'text': '', 'identity_text': ''}
        self.enterContext(patch.object(web, 'source', side_effect=source))

    def test_rejected_lead_is_not_fetched_again_but_new_leads_are(self):
        self.assertIsNone(research.resolve_leads(self.row, self.old))
        self.assertIsNone(research.resolve_leads(self.row, self.old))
        self.assertEqual(self.fetched, ['https://lead.example/one'])  # Before: fetched on every daily pass.
        research.save_evidence(self.row['path'], {'reverse_image_matches': [{'url': 'https://lead.example/one'}, {'url': 'https://lead.example/two'}]})
        research.resolve_leads(self.row, self.old)
        self.assertEqual(self.fetched, ['https://lead.example/one', 'https://lead.example/two'])

    def test_changed_archive_or_identity_and_the_switch_allow_a_recheck(self):
        research.resolve_leads(self.row, self.old)
        research.resolve_leads(dict(self.row, mtime=2), self.old)  # Archive changed (e.g. after a write).
        research.resolve_leads(dict(self.row, mtime=2), {'Series': 'Example', 'Number': '1', 'Publisher': 'Image Comics'})
        self.assertEqual(len(self.fetched), 3)
        (self.root / 'config.json').write_text(json.dumps({'sources': {'disabled': []}}))
        research.resolve_leads(self.row, self.old)
        self.assertEqual(len(self.fetched), 4)

    def test_lead_rejected_under_strict_verification_is_checked_again_without_it(self):
        research.resolve_leads(self.row, self.old, strict=True)
        research.resolve_leads(self.row, self.old, strict=True)
        self.assertEqual(len(self.fetched), 1)  # The strict rejection is remembered while strict.
        research.resolve_leads(self.row, self.old)
        self.assertEqual(len(self.fetched), 2)  # A hold or dead id ended: the hinted route may accept it now.
        research.resolve_leads(self.row, self.old)
        self.assertEqual(len(self.fetched), 2)

    def test_failed_download_is_retried(self):
        def broken(url):
            self.fetched.append(url)
            raise ValueError('Web source unavailable')
        with patch.object(web, 'source', side_effect=broken):
            research.resolve_leads(self.row, self.old)
            research.resolve_leads(self.row, self.old)
        self.assertEqual(len(self.fetched), 2)


if __name__ == '__main__':
    unittest.main()
