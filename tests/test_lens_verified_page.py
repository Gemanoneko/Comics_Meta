"""Post-solve Google redirect: transient page errors and result-page leads.

A fake page stands in for Playwright; no browser, Google or Lens is contacted.
"""
import json
import os
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from playwright.sync_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeout
import app
import browser_search
import browser_worker
import cover_tasks
import lens_verification
import research
from test_worker import scratch_directory

SORRY='https://www.google.com/sorry/index?continue=https://www.google.com/search%3Fvsrid%3Dfixture'
RESULTS='https://www.google.com/search?vsrid=fixture&udm=26'
CARDS=[{'url':'https://www.google.com/search?q=nav','title':'Navigation'},
       {'url':'https://catalog.example/books/milkman','title':'The Milkman Murders HC'},
       {'url':'https://shop.example/milkman-murders','title':'Milkman Murders'}]


class Locator:
    def __init__(self,page,selector):self.page=page;self.selector=selector
    def inner_text(self,timeout=None):
        if self.page.body_errors:raise self.page.body_errors.pop(0)
        return self.page.text
    def evaluate_all(self,script):
        if self.selector=='a[href]':return self.page.cards if self.page.url==RESULTS else []
        return self.page.url==RESULTS  # Visible search box on the results page.


class FakePage:
    """Stays on the challenge for a few polls, then Google loads the results."""
    def __init__(self,solve_after=3,body_errors=(),cards=CARDS):
        self.url='about:blank';self.polls=0;self.solve_after=solve_after
        self.body_errors=list(body_errors);self.cards=cards;self.closed=False;self.text='Visual matches'
    def goto(self,url,**_):self.url=url
    def wait_for_timeout(self,_):
        self.polls+=1
        if self.polls>=self.solve_after:self.url=RESULTS
    def locator(self,selector):return Locator(self,selector)
    def get_by_role(self,*_,**__):return Locator(self,'button')
    def is_closed(self):return self.closed


def lens_browser(page):
    browser=browser_search.LensBrowser({})
    def opened(visible=False,admitted=lambda:None):browser.page=page;browser.context=SimpleNamespace(close=lambda:None)
    browser.open=opened
    browser.minimize=lambda:True
    return browser


class PostSolveRedirectTests(unittest.TestCase):
    def test_timeout_while_results_replace_the_challenge_is_not_a_failure(self):
        # Root cause of the first-attempt TimeoutError: a body read during the
        # post-solve navigation used to escape and fail the whole session.
        page=FakePage(body_errors=[PlaywrightTimeout('Timeout 10000ms exceeded.')])
        self.assertTrue(lens_browser(page).human_session(SORRY))
        self.assertEqual(page.body_errors,[])

    def test_destroyed_context_during_navigation_is_not_a_failure(self):
        page=FakePage(body_errors=[PlaywrightError('Execution context was destroyed, most likely because of a navigation')])
        self.assertTrue(lens_browser(page).human_session(SORRY))

    def test_closed_window_still_ends_the_session(self):
        page=FakePage(body_errors=[PlaywrightError('Target page, context or browser has been closed')]);page.closed=True
        with self.assertRaises(PlaywrightError):lens_browser(page).human_session(SORRY)

    def test_unrelated_error_still_ends_the_session(self):
        page=FakePage(body_errors=[RuntimeError('unexpected')])
        with self.assertRaises(RuntimeError):lens_browser(page).human_session(SORRY)

    def test_results_page_after_the_solve_is_read_as_leads(self):
        browser=lens_browser(FakePage())
        self.assertTrue(browser.human_session(SORRY))
        self.assertEqual([lead['url'] for lead in browser.verified_leads],
                         ['https://catalog.example/books/milkman','https://shop.example/milkman-murders'])

    def test_no_results_page_means_no_leads(self):
        page=FakePage();browser=lens_browser(page)
        with patch.object(browser_search,'verification_complete',side_effect=lambda p:setattr(p,'url','https://www.google.com/imghp') or True):
            self.assertTrue(browser.human_session(SORRY))
        self.assertEqual(browser.verified_leads,[])


class VerifiedPageLeadTests(unittest.TestCase):
    """Service level: the solved check's results reach the comic that hit it."""
    def setUp(self):
        self.root=Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app,'DATA',self.root/'data'))
        self.enterContext(patch.object(app,'live_root',return_value=str(self.root)))
        self.enterContext(patch.object(research,'CACHE',self.root/'research'))
        self.enterContext(patch.object(lens_verification,'_owner',None))
        self.enterContext(patch.object(lens_verification,'lens_on',return_value=True))  # Enrichment E: Lens is opt-in; tested switched on.
        self.enterContext(patch.object(browser_worker.pause_control,'requested',return_value=False))
        lens_verification.initialize()
        (app.DATA/'browser-heartbeat').write_text(json.dumps({'pid':os.getpid(),'timestamp':time.time()}))
        path=self.root/'The Milkman Murders (2012).cbz';path.write_bytes(b'isolated fixture')
        stat=path.stat();self.task={'path':str(path),'size':stat.st_size,'mtime':stat.st_mtime_ns}
        with app.db() as con:
            con.execute("INSERT INTO comics(path,size,mtime,metadata,status) VALUES(?,?,?,'{}','missing')",(str(path),stat.st_size,stat.st_mtime_ns))
        cover_tasks.enqueue(self.task)
        # The comic's search hit the check (as recorded by browser_worker.process).
        browser_search.legacy_status(human_verification=True,verification_url=SORRY,verification_task=self.task,browser_retry_at=time.time()+3600)
        lens_verification.request()

    def state(self):
        with app.db() as con:return con.execute('SELECT state FROM cover_tasks').fetchone()[0]

    def evidence(self):
        return research.CACHE.glob('evidence-*.json')

    def test_first_attempt_succeeds_through_redirect_and_saves_original_results(self):
        browser=lens_browser(FakePage(body_errors=[PlaywrightTimeout('Timeout 10000ms exceeded.')]))
        result=browser_worker.verification_request(browser,{})
        status=lens_verification.status()
        with app.db() as con:receipt=lens_verification.read(con)
        # Before the fix this receipt was: failed / unfinished / TimeoutError.
        self.assertEqual((status['phase'],status['failure'],receipt.get('error_class')),('verified','',''))
        self.assertIs(result,browser)
        self.assertEqual(self.state(),'leads_found')
        saved=json.loads(next(self.evidence()).read_text(encoding='utf-8'))
        self.assertEqual([lead['url'] for lead in saved['reverse_image_matches']],
                         ['https://catalog.example/books/milkman','https://shop.example/milkman-murders'])
        self.assertEqual(browser_search.legacy_status()['verification_task'],{})
        self.assertIn('2 candidate links saved',browser_search.legacy_status()['detail'])

    def test_changed_archive_does_not_receive_the_results(self):
        Path(self.task['path']).write_bytes(b'changed archive bytes')
        browser_worker.verification_request(lens_browser(FakePage()),{})
        self.assertEqual(self.state(),'pending')
        self.assertEqual(list(self.evidence()),[])

    def test_identified_comic_does_not_receive_the_results(self):
        cover_tasks.identified(self.task)
        browser_worker.verification_request(lens_browser(FakePage()),{})
        self.assertEqual(self.state(),'not_needed')
        self.assertEqual(list(self.evidence()),[])


if __name__=='__main__':
    unittest.main()
