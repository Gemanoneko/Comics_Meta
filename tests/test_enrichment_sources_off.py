"""Enrichment E (Sergei 2026-10-26): GCD, Dark Horse, Google Books, Open Library and Google Lens are off by default.

Isolated state root; no provider, browser or model is reached."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch
import app
import browser_search
import lens_verification
import pipeline_config
import providers
from test_worker import scratch_directory

RETIRED = {'GCD', 'Dark Horse', 'Google Books', 'Open Library local index'}


class SourcesOffTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app, 'STATE_ROOT', self.root))
        self.enterContext(patch.object(app, 'DATA', self.root / 'data'))

    def config(self, value):
        (self.root / 'config.json').write_text(json.dumps(value), encoding='utf-8')

    def test_zero_yield_sources_are_off_by_default(self):
        self.assertTrue(RETIRED <= pipeline_config.disabled_sources())
        self.assertTrue(pipeline_config.source_enabled('Metron'))
        self.assertTrue(pipeline_config.source_enabled('Image Comics'))

    def test_an_explicit_disabled_list_does_not_turn_them_back_on(self):
        # A config.json written before 2026-10-26 names its own list; the four stay off anyway.
        self.config({'sources': {'disabled': ['GetComics']}})
        self.assertTrue(RETIRED <= pipeline_config.disabled_sources())
        self.assertTrue(pipeline_config.source_enabled('General free web'))  # The explicit list still rules the rest.

    def test_sources_enabled_turns_one_back_on(self):
        self.config({'sources': {'disabled': [], 'enabled': ['GCD']}})
        self.assertTrue(pipeline_config.source_enabled('GCD'))
        self.assertFalse(pipeline_config.source_enabled('Dark Horse'))

    def test_lens_is_off_even_when_browser_search_is_enabled(self):
        self.config({'browser_search': {'enabled': True, 'daily_request_limit': 100}})
        self.assertFalse(browser_search.settings()['enabled'])
        self.assertEqual(browser_search.settings()['daily_request_limit'], 100)
        self.config({'browser_search': {'enabled': True, 'lens': True}})
        self.assertTrue(browser_search.settings()['enabled'])  # Explicit opt-in.
        self.config({'browser_search': {'enabled': False, 'lens': True}})
        self.assertFalse(browser_search.settings()['enabled'])

    def lens_status(self, legacy, stored):
        lens_verification.initialize()
        with app.db() as con:
            lens_verification.save(con, stored)
        with patch.object(browser_search, 'legacy_status', return_value=legacy):
            return lens_verification.status()

    def test_lens_off_never_asks_for_human_verification(self):
        self.config({'browser_search': {'enabled': True}})
        legacy = {'human_verification': True, 'alive': True}
        stored = {'phase': 'open', 'window': 'open', 'owner': 'x', 'owner_pid': 1, 'generation': 0, 'stage': 'observe'}
        state = self.lens_status(legacy, stored)
        self.assertFalse(state['human_verification'])  # Before: True, so the tray and dashboard asked for a check.
        self.assertEqual((state['phase'], state['window'], state['failure'], state['verification_pending']), ('idle', 'closed', '', False))
        # Positive control: with Lens switched on the same stored state still asks.
        self.config({'browser_search': {'enabled': True, 'lens': True}})
        self.assertTrue(self.lens_status(legacy, stored)['human_verification'])

    def test_switched_off_sources_report_switched_off(self):
        import getcomics, publisher_catalogs, web_search, research
        with patch.object(providers, 'comicvine_status', return_value={'status': 'configured'}), \
                patch.object(getcomics, 'status', return_value={'status': 'human_verification'}), \
                patch.object(publisher_catalogs, 'statuses', return_value={'darkhorse_catalog': {'status': 'daily_budget_wait'},
                                                                          'image_catalog': {'status': 'available'},
                                                                          'previews_catalog': {'status': 'unavailable'}}), \
                patch.object(web_search, 'free_status', return_value={'status': 'available'}), \
                patch.object(research, 'wiki_status', return_value={'status': 'available'}):
            statuses = providers.statuses()
        for key in ('gcd', 'google_books', 'open_library', 'darkhorse_catalog', 'getcomics', 'previews_catalog', 'free_web', 'wikipedia'):
            self.assertEqual(statuses[key], {'status': 'switched_off'}, key)  # Before: stale budget and verification states.
        self.assertEqual(statuses['image_catalog'], {'status': 'available'})
        self.assertEqual(statuses['comicvine'], {'status': 'configured'})


class ScreenFactsTests(unittest.TestCase):
    """DesktopShell spec §12: what the page needs to leave switched-off things off the screen."""
    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app, 'STATE_ROOT', self.root))
        self.enterContext(patch.object(app, 'DATA', self.root / 'data'))

    def test_browser_verification_says_whether_lens_is_on(self):
        import io
        from types import SimpleNamespace
        from unittest.mock import Mock
        def answer():
            handler = object.__new__(app.Handler)
            handler.server = SimpleNamespace(server_port=8765)
            handler.path = '/api/browser-verification'
            handler.respond = Mock()
            handler.rfile = io.BytesIO(b'')
            handler.headers = {'Origin': 'http://127.0.0.1:8765', 'Host': '127.0.0.1:8765', 'Content-Length': '0'}
            with patch.object(lens_verification, 'status', return_value={'engine': 'google_lens'}), \
                    patch.object(browser_search, 'legacy_status', return_value={}):
                handler.do_GET()
            return handler.respond.call_args.args[0]
        with patch.object(lens_verification, 'lens_on', return_value=False):
            self.assertIs(answer()['enabled'], False)  # Before: no such field; the page read the worker's stale cover state.
        with patch.object(lens_verification, 'lens_on', return_value=True):
            self.assertIs(answer()['enabled'], True)

    def test_setup_and_keys_answers_name_the_hidden_google_books_row(self):
        import setup_state
        self.assertEqual(setup_state.hidden_keys(), ['GOOGLE_BOOKS_API_KEY'])  # Before: no such field.
        self.assertEqual(setup_state.key_status()['hidden_keys'], ['GOOGLE_BOOKS_API_KEY'])
        (self.root / 'config.json').write_text(json.dumps({'sources': {'enabled': ['Google Books']}}), encoding='utf-8')
        self.assertEqual(setup_state.key_status()['hidden_keys'], [])  # Source on: the row returns.
        self.assertEqual(setup_state.status()['hidden_keys'], [])


class LensOffProgressTests(unittest.TestCase):
    def test_no_cover_search_is_reported_queued_while_lens_is_off(self):
        import progress_snapshot, cover_tasks
        with patch.object(cover_tasks, 'status', return_value={'pending': 20007}):
            with patch.object(browser_search, 'settings', return_value={'enabled': False}):
                self.assertEqual(progress_snapshot.cover_research(), {})  # Before: 20,007 "browser cover searches queued".
            with patch.object(browser_search, 'settings', return_value={'enabled': True}):
                self.assertEqual(progress_snapshot.cover_research(), {'pending': 20007})


class LensOffDiscoveryTests(unittest.TestCase):
    def test_no_cover_search_is_queued_while_lens_is_off(self):
        import automatic, cover_tasks
        with patch.object(browser_search, 'settings', return_value={'enabled': False}), patch.object(cover_tasks, 'enqueue') as enqueue:
            automatic.queue_cover_search({'path': 'x.cbz'})
        enqueue.assert_not_called()
        with patch.object(browser_search, 'settings', return_value={'enabled': True}), patch.object(cover_tasks, 'enqueue') as enqueue:
            automatic.queue_cover_search({'path': 'x.cbz'})
        enqueue.assert_called_once()


if __name__ == '__main__':
    unittest.main()
