"""v0.1.2 review round 2: Lens holds, dashboard text, post-check reads and lead
saving (Senua F4-F8; Futaba Q-4, Q-7, Q-9; Judy's string review).

Isolated catalog, mocked browser and Playwright page; no network.
"""
import hashlib
import json
import os
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from playwright.sync_api import Error as PlaywrightError
import app
import browser_search
import browser_worker as worker
import cover_tasks
import lens_verification
import research
from test_worker import scratch_directory
from test_lens_verified_page import FakePage,SORRY,lens_browser

COOLING_DOWN='Google Lens is cooling down. Queued covers keep their place; searching resumes automatically.'
DAILY_LIMIT='Daily Google Lens search limit reached. Queued covers keep their place; searching resumes when the limit resets.'


class HeldSearchTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app,'DATA',self.root/'data'))
        self.enterContext(patch.object(app,'live_root',return_value=str(self.root)))
        self.enterContext(patch.object(research,'CACHE',self.root/'research'))
        self.enterContext(patch.object(worker.pause_control,'requested',return_value=False))
        self.enterContext(patch.object(worker.search,'cover_bytes',return_value=b'fixture cover'))
        self.enterContext(patch.object(worker.search,'cached',return_value=('fixture-key',None)))
        self.browser=Mock();self.browser.search.return_value=[{'url':'https://catalog.example/issue','title':'Issue'}]
        self.options={'daily_request_limit':100}
        path=self.root/'comic.cbz';path.write_bytes(b'isolated fixture')
        stat=path.stat();self.row={'path':str(path),'size':stat.st_size,'mtime':stat.st_mtime_ns}
        with app.db() as con:
            con.execute("INSERT INTO comics(path,size,mtime,metadata,status) VALUES(?,?,?,'{}','missing')",(str(path),stat.st_size,stat.st_mtime_ns))
        cover_tasks.enqueue(self.row)

    def task(self):
        with app.db() as con:return dict(con.execute('SELECT * FROM cover_tasks').fetchone())

    def test_daily_limit_is_reported_as_the_limit_not_a_cooldown(self):
        # F7 / Q-4 / Sergei's daily-limit bug: the re-raised ValueError reached
        # the generic handler, which set a one-hour cooldown and the
        # "could not finish" error beside the daily-limit detail.
        browser_search.reserve('browser',1,time.strftime('%Y-%m-%d',time.gmtime()))
        self.options['daily_request_limit']=1
        hold=worker.process(cover_tasks.claim(),self.browser,self.options)
        state=browser_search.legacy_status()
        self.assertEqual(state.get('browser_retry_at',0),0)
        self.assertEqual(state.get('browser_error',''),'')
        self.assertEqual(state['detail'],DAILY_LIMIT)
        self.assertEqual(hold%86400,0)  # Re-checked when the UTC day (and the count) resets.
        self.assertIn('Daily Google Lens search limit reached. Not searched; kept in its queue place until this clears.',self.task()['detail'])
        self.browser.search.assert_not_called()

    def test_cooldown_and_human_check_show_the_cooldown_text(self):
        browser_search.legacy_status(browser_retry_at=time.time()+1800)
        worker.process(cover_tasks.claim(),self.browser,self.options)
        self.assertEqual(browser_search.legacy_status()['detail'],COOLING_DOWN)
        self.assertIn('Google Lens is cooling down.',self.task()['detail'])
        browser_search.legacy_status(browser_retry_at=0)
        self.browser.search.side_effect=browser_search.HumanVerification('https://www.google.com/sorry/index?continue=fixture')
        worker.process(cover_tasks.claim(),self.browser,self.options)  # Asked for a check.
        self.assertEqual(browser_search.legacy_status()['detail'],COOLING_DOWN)
        self.assertIn('Google Lens asked for human verification.',self.task()['detail'])  # Stored detail kept.
        worker.process(cover_tasks.claim(),self.browser,self.options)  # Check still pending.
        self.assertEqual(browser_search.legacy_status()['detail'],COOLING_DOWN)
        self.assertIn('Google Lens needs human verification.',self.task()['detail'])

    def test_legacy_fallback_setting_during_a_hold_is_not_a_search(self):
        # SerpApi was removed (Sergei 2026-10-16). An old config that still turns
        # its fallback on leaves a held comic in place with the Lens reason only.
        browser_search.legacy_status(browser_retry_at=time.time()+1800)
        self.options.update(serpapi_fallback=True,serpapi_monthly_limit=250)
        before=self.task()
        hold=worker.process(cover_tasks.claim(),self.browser,self.options)
        task=self.task()
        self.assertEqual((task['state'],task['updated']),(before['state'],before['updated']))
        self.assertEqual(task['detail'],'Google Lens is cooling down. Not searched; kept in its queue place until this clears.')
        self.assertGreater(hold,time.time())
        self.browser.search.assert_not_called()

    def evidence(self):
        target=research.CACHE/('evidence-'+hashlib.sha256(self.row['path'].encode()).hexdigest()+'.json')
        return json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}

    def test_identity_found_during_the_search_is_not_overwritten(self):
        # F6: discovery verifies identity in the gap between process()'s state
        # check and the lead write; record() used to INSERT OR REPLACE anyway.
        row=cover_tasks.claim();real=cover_tasks.record
        def racing(*args,**options):
            cover_tasks.identified(row)
            return real(*args,**options)
        with patch.object(worker.cover_tasks,'record',side_effect=racing):
            worker.process(row,self.browser,self.options)
        self.assertEqual(self.task()['state'],'not_needed')  # Before: leads_found.
        self.assertNotIn('reverse_image_matches',self.evidence())

    def test_positive_control_a_queued_search_still_records_its_leads(self):
        worker.process(cover_tasks.claim(),self.browser,self.options)
        self.assertEqual(self.task()['state'],'leads_found')
        self.assertEqual(self.evidence()['reverse_image_matches'][0]['url'],'https://catalog.example/issue')

    def test_a_late_post_check_page_adds_to_saved_leads_instead_of_replacing_them(self):
        cover_tasks.record(self.row,[{'url':'https://catalog.example/first','title':'First'}])
        cover_tasks.enqueue(self.row)  # Leads failed verification: leads_unverified.
        task={'path':self.row['path'],'size':self.row['size'],'mtime':self.row['mtime']}
        self.assertEqual(cover_tasks.record_verified_page(task,[{'url':'https://catalog.example/second','title':'Second'}]),1)
        urls=[lead['url'] for lead in self.evidence()['reverse_image_matches']]
        self.assertEqual(urls,['https://catalog.example/second','https://catalog.example/first'])


class PostCheckPageTests(unittest.TestCase):
    """F4 / F5 / Q-7: the observe loop and the post-check read."""
    def test_persistent_page_errors_end_the_session_with_their_class(self):
        page=FakePage(solve_after=10**9)
        page.locator=lambda selector:SimpleNamespace(inner_text=Mock(side_effect=PlaywrightError('evaluate script broke')),
                                                    evaluate_all=Mock(return_value=False))
        page.url='https://www.google.com/search?q=fixture'
        browser=lens_browser(page)
        browser.open=lambda visible=False,admitted=lambda:None:setattr(browser,'page',page) or setattr(browser,'context',SimpleNamespace(close=lambda:None))
        page.goto=lambda url,**_:None
        clock=iter(range(0,10**6,1))
        with patch.object(browser_search.time,'monotonic',side_effect=lambda:next(clock)):
            with self.assertRaises(PlaywrightError):browser.human_session(SORRY)  # Before: retried until the 600 s deadline.

    def test_short_redirect_errors_are_still_tolerated(self):
        page=FakePage(body_errors=[PlaywrightError('Execution context was destroyed')]*3)
        self.assertTrue(lens_browser(page).human_session(SORRY))

    def test_post_check_read_waits_between_retries(self):
        page=FakePage();page.url='https://www.google.com/search?vsrid=fixture'
        browser=lens_browser(page);browser.page=page
        calls=[]
        def leads(_):
            calls.append(1)
            if len(calls)<3:raise PlaywrightError('Execution context was destroyed')
            return [{'url':'https://catalog.example/lead','title':'Lead'}]
        with patch.object(browser_search,'result_leads',side_effect=leads),patch.object(browser_search.time,'sleep') as sleep:
            self.assertEqual(len(browser.verified_page_leads(lambda:None)),1)
        self.assertEqual(sleep.call_count,2)  # Before: re-read at once, a hot loop.


class ClosedAfterSolveTests(unittest.TestCase):
    """F4: a window closed during the post-check read is recorded as closed."""
    def setUp(self):
        self.root=Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app,'DATA',self.root/'data'))
        self.enterContext(patch.object(lens_verification,'_owner',None))
        lens_verification.initialize()
        (app.DATA/'browser-heartbeat').write_text(json.dumps({'pid':os.getpid(),'timestamp':time.time()}))
        browser_search.legacy_status(human_verification=True,verification_url=SORRY,browser_retry_at=time.time()+3600)
        lens_verification.request()

    def test_closed_window_is_not_reported_open_and_the_browser_is_released(self):
        page=FakePage();browser=lens_browser(page)
        def closing_read(admitted):
            page.closed=True;return []  # The user closed the window during the read.
        browser.verified_page_leads=closing_read
        browser.minimize=Mock(return_value=False)
        result=lens_verification.service(browser,{})
        with app.db() as con:receipt=lens_verification.read(con)
        self.assertEqual((receipt['phase'],receipt['window']),('verified','closed'))  # Before: verified / open.
        self.assertIsNone(result.context)  # The next search opens a fresh browser.
        browser.minimize.assert_not_called()
        self.assertFalse(browser_search.legacy_status()['human_verification'])

    def test_open_window_is_still_minimized(self):
        browser=lens_browser(FakePage())
        lens_verification.service(browser,{})
        with app.db() as con:self.assertEqual(lens_verification.read(con)['window'],'minimized')


if __name__=='__main__':
    unittest.main()
