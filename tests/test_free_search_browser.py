"""Mocked regular search/lifecycle fixtures: no actual browser or requests."""
import unittest
from unittest.mock import Mock,patch
from pathlib import Path
import app,free_search_browser as browser,research,web_search as web
from test_worker import scratch_directory


class RegularSearchTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app,'DATA',self.root))
        self.enterContext(patch.object(browser,'own_descendants'))
        self.enterContext(patch.object(browser,'_query_job',return_value=1))
        self.enterContext(patch('msvcrt.locking'))
        self.page=Mock();self.page.url='https://duckduckgo.com/?q=fixture'
        self.body=Mock();self.body.inner_text.return_value='Ordinary results'
        self.links=Mock();self.links.evaluate_all.return_value=[{'url':'https://www.darkhorse.com/comics/15-681/star-wars-the-clone-wars-3/','title':'Star Wars: The Clone Wars #3'}]
        self.page.locator.side_effect=lambda selector:self.body if selector=='body' else self.links
        self.context=Mock();self.context.pages=[self.page]
        self.runtime=Mock();self.runtime.chromium.launch_persistent_context.return_value=self.context
        self.enterContext(patch('playwright.sync_api.sync_playwright',return_value=Mock(start=Mock(return_value=self.runtime))))
        self.enterContext(patch('pause_control.requested',return_value=False))

    def test_regular_query_dedicated_profile_and_organic_only_bounds(self):
        result=browser.search('Star Wars - The Clone Wars #3 comics')
        self.assertEqual(result[0]['title'],'Star Wars: The Clone Wars #3')
        self.assertIn('q=Star+Wars+-+The+Clone+Wars+%233+comics',self.page.goto.call_args.args[0])
        self.assertEqual(self.runtime.chromium.launch_persistent_context.call_args.args[0],str(self.root/'ddg-profile'))
        self.assertIn('result-title-a',self.page.locator.call_args.args[0])
        self.assertIn('li[data-layout="organic"] article',self.page.locator.call_args.args[0])
        self.context.close.assert_called_once();self.runtime.stop.assert_called_once();browser.close()

    def test_links_bound_dedup_redirect_and_no_navigation_credentials(self):
        items=[{'url':'https://duckduckgo.com/settings'}, {'url':'https://user:secret@example.org/a'},
               {'url':'https://duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.org%2F1','title':'One'},
               {'url':'https://example.org/1'}]+[{'url':'https://example.org/'+str(n)} for n in range(2,20)]
        self.assertEqual([x['url'] for x in browser.normalize_links(items)],[f'https://example.org/{n}' for n in range(1,6)])

    def test_actual_challenge_closes_context_and_does_not_solve(self):
        self.body.inner_text.return_value='Unfortunately, bots use DuckDuckGo too. Complete the following challenge.'
        with self.assertRaisesRegex(browser.BrowserUnavailable,'human verification'):browser.search('Fixture #1 comics')
        self.context.close.assert_called_once();self.runtime.stop.assert_called_once();self.links.evaluate_all.assert_not_called()
        browser.close()

    def test_no_results_only_when_explicit_otherwise_unknown_page_fails(self):
        self.links.first.wait_for.side_effect=TimeoutError()
        self.body.inner_text.return_value='No results found'
        self.assertEqual(browser.search('Fixture'),[])
        self.body.inner_text.return_value='Unknown page'
        with self.assertRaisesRegex(browser.BrowserUnavailable,'usable result'):browser.search('Fixture')

    def test_profile_busy_does_not_launch_browser(self):
        import msvcrt
        with patch.object(msvcrt,'locking',side_effect=OSError()):
            with self.assertRaisesRegex(browser.BrowserUnavailable,'already owned'):browser.search('Fixture')
        self.runtime.chromium.launch_persistent_context.assert_not_called()

    def test_pause_closes_and_never_parses_more_results(self):
        import pause_control
        with patch.object(pause_control,'requested',side_effect=[False,True]):
            with self.assertRaises(pause_control.PauseRequested):browser.search('Fixture')
        self.context.close.assert_called_once();self.runtime.stop.assert_called_once();browser.close()

    def test_subrequests_cannot_navigate_publisher_or_local_resource(self):
        browser.search('Fixture')
        route_handler=self.context.route.call_args.args[1]
        for url,allowed in [('https://duckduckgo.com/?q=fixture',True),('https://www.darkhorse.com/comics/fixture',False),('http://127.0.0.1:8765/',False)]:
            route=Mock();route.request.url=url;route_handler(route)
            (route.continue_ if allowed else route.abort).assert_called_once()

    def test_simple_query_keeps_exact_issue_verifier(self):
        row={'path':'fixture.cbz','series':'Star Wars - The Clone Wars','number':'3','year':'2008'}
        old={'Series':row['series'],'Number':'3','Publisher':'Dark Horse','Year':'2008'}
        exact={'url':'https://www.darkhorse.com/comics/15-681/star-wars-the-clone-wars-3/','title':'Star Wars: The Clone Wars #3','headings':[],
               'text':'Dark Horse 2008 Eighty million Togruta from the planet of Kiros.','identity_text':'Dark Horse 2008'}
        with patch.object(web,'search',return_value=[{'url':exact['url']}]) as search,patch.object(web,'source',return_value=exact),patch.object(research,'save_evidence'):
            self.assertIsNotNone(research.general_lookup(row,old))
            search.assert_called_once_with('Star Wars - The Clone Wars #3 comics',free_only=True)
        for title in ('Star Wars: The Clone Wars #2','Star Wars: The Clone Wars (comic series)'):
            self.assertIsNone(research.verify_web_source(row,old,dict(exact,title=title)))

    def test_unknown_cleanup_retains_profile_until_owner_exit(self):
        self.runtime.stop.side_effect=OSError('fixture stop failure')
        before=len(browser._retained)
        try:
            with self.assertRaisesRegex(browser.BrowserUnavailable,'closure unverified'):browser.search('Fixture')
            with self.assertRaisesRegex(browser.BrowserUnavailable,'safe closure'):browser.close()
            with self.assertRaisesRegex(browser.BrowserUnavailable,'already owned'):browser.search('Fixture')
        finally:
            # Release mock-only quarantined handles after recording fail-closed behavior.
            for lock,_,_ in browser._retained[before:]:lock.close()
            del browser._retained[before:]
            browser._mutex.release()

    def test_manual_process_cannot_register_or_assign_job(self):
        import sys,ctypes
        with patch.object(browser,'_worker_owner',None),patch.object(sys,'argv',['app.py']),patch.object(ctypes,'WinDLL') as native:
            with self.assertRaisesRegex(browser.BrowserUnavailable,'entry point'):browser.enable_worker_owner()
            # Remove the search fixture's ownership mock for this explicit contract check.
            with self.assertRaisesRegex(browser.BrowserUnavailable,'metadata worker'):_actual_ownership()
            native.assert_not_called()

    def test_native_assignment_failure_closes_only_unassigned_handle(self):
        import ctypes,os
        kernel=Mock();kernel.CreateJobObjectW.return_value=123;kernel.SetInformationJobObject.return_value=1
        kernel.AssignProcessToJobObject.return_value=0
        with patch.object(browser,'_worker_owner',os.getpid()),patch.object(browser,'_job',None),patch.object(ctypes,'WinDLL',return_value=kernel):
            with self.assertRaisesRegex(browser.BrowserUnavailable,'ownership is unavailable'):_actual_ownership()
            kernel.CloseHandle.assert_called_once_with(123)
        self.runtime.chromium.launch_persistent_context.assert_not_called()

    def test_live_descendant_count_retains_profile_after_graceful_stop(self):
        before=len(browser._retained)
        try:
            with patch.object(browser,'_query_job',side_effect=[1,2,2]),patch.object(browser.time,'monotonic',side_effect=[0,6]):
                with self.assertRaisesRegex(browser.BrowserUnavailable,'closure unverified'):browser.search('Fixture')
            self.assertTrue(browser._mutex.locked())
        finally:
            for lock,_,_ in browser._retained[before:]:lock.close()
            del browser._retained[before:];browser._mutex.release()

    def test_start_failure_with_live_driver_retains_profile(self):
        before=len(browser._retained)
        start=Mock(side_effect=OSError('Fixture driver started but handshake failed'))
        try:
            with patch('playwright.sync_api.sync_playwright',return_value=Mock(start=start)), \
                 patch.object(browser,'_query_job',side_effect=[1,2,2]),patch.object(browser.time,'monotonic',side_effect=[0,6]):
                with self.assertRaisesRegex(browser.BrowserUnavailable,'closure unverified'):browser.search('Fixture')
            self.assertTrue(browser._mutex.locked())
        finally:
            for lock,_,_ in browser._retained[before:]:lock.close()
            del browser._retained[before:];browser._mutex.release()


_actual_ownership=browser.own_descendants


if __name__=='__main__':unittest.main()
