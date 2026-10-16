"""Mocked cover searches; no browser, network, model, or real comic writes."""
import json
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
import app
import browser_worker as worker
import cover_tasks
from test_worker import scratch_directory


class BrowserCooldownTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app,'DATA',self.root/'data'))
        path=self.root/'fixture.cbz';path.write_bytes(b'isolated fixture')
        stat=path.stat()
        self.row={'path':str(path),'size':stat.st_size,'mtime':stat.st_mtime_ns,'metadata':json.dumps({})}
        with app.db() as con:cover_tasks.table(con)
        self.clock=100
        self.enterContext(patch.object(worker.time,'time',side_effect=lambda:self.clock))
        self.enterContext(patch.object(worker.pause_control,'requested',return_value=False))
        self.state={'browser_retry_at':200}
        def status(**changes):
            self.state.update(changes)
            return dict(self.state)
        self.enterContext(patch.object(worker.search,'status',side_effect=status))
        self.enterContext(patch.object(worker.search,'cover_bytes',return_value=b'fixture cover'))
        self.cached=self.enterContext(patch.object(worker.search,'cached',return_value=('fixture-key',None)))
        self.reserve=self.enterContext(patch.object(worker.search,'reserve'))
        self.enterContext(patch.object(worker.search,'save_cache'))
        self.record=self.enterContext(patch.object(worker.cover_tasks,'record'))
        self.finish=self.enterContext(patch.object(worker.cover_tasks,'finish'))
        self.browser=Mock()
        self.browser.search.return_value=[{'url':'https://example.org/issue','title':'Fixture'}]
        self.options={'daily_request_limit':100}

    def test_repeated_wait_preserves_deadline_without_request_or_browser(self):
        for now in (100,120,199):
            self.clock=now
            worker.process(self.row,self.browser,self.options)
            self.assertEqual(self.state['browser_retry_at'],200)
        self.reserve.assert_not_called()
        self.browser.search.assert_not_called()

    def test_expiry_permits_mocked_search_with_original_budget(self):
        self.clock=200
        worker.process(self.row,self.browser,self.options)
        self.reserve.assert_called_once()
        self.assertEqual(self.reserve.call_args.args[:2],('browser',100))
        self.browser.search.assert_called_once_with(b'fixture cover')
        self.assertEqual(self.state['browser_retry_at'],0)
        self.record.assert_called_once()

    def test_actual_failure_starts_original_one_hour_wait(self):
        self.state['browser_retry_at']=99
        self.browser.search.side_effect=ValueError('Synthetic browser error')
        worker.process(self.row,self.browser,self.options)
        self.assertEqual(self.state['browser_retry_at'],3700)
        self.reserve.assert_called_once()
        self.browser.search.assert_called_once()

    def test_budget_refusal_holds_until_the_limit_resets_without_a_cooldown(self):
        # The daily cap is not a browser failure: before the fix it set a fresh
        # one-hour cooldown (3700) and the generic could-not-finish error.
        self.state['browser_retry_at']=99
        self.reserve.side_effect=ValueError('browser request limit reached.')
        hold=worker.process(self.row,self.browser,self.options)
        self.assertEqual(self.state['browser_retry_at'],99)
        self.assertNotIn('browser_error',self.state)
        self.assertEqual(hold,86400)  # Next UTC day, when the count resets.
        self.assertEqual(self.state['detail'],worker.HELD_DAILY_LIMIT)
        self.browser.search.assert_not_called()

    def test_cached_leads_remain_usable_during_longer_cooldown(self):
        self.state['browser_retry_at']=100000
        self.cached.return_value=('fixture-key',[{'url':'https://example.org/cached','title':'Fixture'}])
        worker.process(self.row,self.browser,self.options)
        self.reserve.assert_not_called()
        self.browser.search.assert_not_called()
        self.assertEqual(self.state['browser_retry_at'],100000)
        self.record.assert_called_once()

    def test_human_challenge_hold_survives_repeated_wait(self):
        self.state['browser_retry_at']=99
        self.browser.search.side_effect=worker.search.HumanVerification('https://www.google.com/sorry/fixture')
        worker.process(self.row,self.browser,self.options)
        self.assertEqual(self.state['browser_retry_at'],3700)
        self.assertTrue(self.state['human_verification'])
        self.assertEqual(self.state['verification_state'],'required')
        self.clock=120
        worker.process(self.row,self.browser,self.options)
        self.assertEqual(self.state['browser_retry_at'],3700)
        self.assertTrue(self.state['human_verification'])
        self.assertEqual(self.browser.search.call_count,1)

    def test_legacy_fallback_setting_is_ignored_during_a_cooldown(self):
        # SerpApi was removed (Sergei 2026-10-16). An old config that still turns
        # its fallback on holds the search like any cooldown: no request, no leads.
        self.options.update(serpapi_fallback=True,serpapi_monthly_limit=250)
        hold=worker.process(self.row,self.browser,self.options)
        self.assertEqual(hold,200)
        self.reserve.assert_not_called()
        self.browser.search.assert_not_called()
        self.assertEqual(self.state['browser_retry_at'],200)
        self.record.assert_not_called()
        self.finish.assert_not_called()
