"""Offline request ownership, durable outcomes and cancellation interleavings."""
import json
import os
import time
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
import app
import browser_search as search
import lens_verification as lens
import lens_browser_owner as owner
import pause_control
from test_worker import scratch_directory


class LensTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app,'DATA',self.root/'data'))
        self.enterContext(patch.object(lens,'_owner',None))
        pause_control.requested();lens.initialize()
        (app.DATA/'browser-heartbeat').write_text(json.dumps({'pid':os.getpid(),'timestamp':time.time()}))
        search.legacy_status(human_verification=True,verification_url='https://www.google.com/sorry/fixture',browser_retry_at=4102444800)
        self.browser=Mock();self.browser.minimize.return_value=True
        self.browser.human_session.side_effect=self.success

    def success(self,url,admitted,observation):
        admitted();observation('load');observation('observe');return True

    def raw(self):
        with app.db() as con:return lens.read(con)

    def pause_resume(self):pause_control.change(True);pause_control.change(False)

    def test_queued_request_receipt_duplicate_and_legacy_overlay(self):
        first=search.request_verification();second=search.request_verification()
        self.assertEqual(second['state'],'already_requested');self.assertEqual(first['request_id'],second['request_id'])
        self.assertTrue(search.status()['verification_pending'])
        self.assertEqual(self.raw()['phase'],'queued')
        self.assertGreater(self.raw()['requested_at'],0)

    def test_ordinary_cover_updates_cannot_erase_failed_outcome_or_hold(self):
        lens.request();self.browser.human_session.side_effect=RuntimeError('private URL token')
        self.assertIsNone(lens.service(self.browser,{}));self.browser.close.assert_called_once()
        search.status(state='waiting',detail='Other cover progress',verification_state='required')
        self.assertEqual(lens.status()['phase'],'failed');self.assertEqual(lens.status()['failure'],'open')
        self.assertEqual(self.raw()['error_class'],'RuntimeError')
        self.assertNotIn('private',json.dumps(self.raw()));self.assertEqual(search.legacy_status()['browser_retry_at'],4102444800)
        with app.db() as con:self.assertGreaterEqual(con.execute('SELECT COUNT(*) FROM lens_verification_events').fetchone()[0],4)

    def test_success_retains_session_and_never_resets_backoff_or_quota(self):
        search.reserve('browser',1,'fixture');lens.request()
        self.assertIs(lens.service(self.browser,{}),self.browser)
        self.browser.close.assert_not_called()
        self.assertEqual(lens.status()['window'],'minimized');self.assertFalse(lens.status()['human_verification'])
        self.assertEqual(search.legacy_status()['browser_retry_at'],4102444800)
        with app.db() as con:self.assertEqual(con.execute('SELECT COUNT(*) FROM image_search_requests').fetchone()[0],1)

    def test_later_challenge_is_actionable_after_success(self):
        lens.request();lens.service(self.browser,{})
        search.legacy_status(human_verification=True,verification_state='required')
        self.assertEqual(lens.status()['phase'],'required');self.assertEqual(lens.request()['state'],'queued')

    def test_launch_and_load_failures_have_distinct_receipts(self):
        def failure(url,admitted,observation):observation('load');raise TimeoutError('private')
        lens.request();self.browser.human_session.side_effect=failure
        lens.service(self.browser,{})
        self.assertEqual(lens.status()['failure'],'load');self.assertEqual(self.raw()['stage'],'load')
        self.assertEqual(self.raw()['window'],'closed');self.assertIsNotNone(self.raw()['opened_at'])

    def test_timeout_is_unfinished_and_retry_gets_new_identity(self):
        lens.request();old=self.raw()['request_id'];self.browser.human_session.return_value=False;self.browser.human_session.side_effect=None
        lens.service(self.browser,{})
        self.assertEqual(lens.status()['failure'],'unfinished')
        self.assertNotEqual(lens.request()['request_id'],old)

    def test_pause_resume_inside_launch_closes_and_does_not_succeed(self):
        def cancel(url,admitted,observation):self.pause_resume();admitted()
        lens.request();self.browser.human_session.side_effect=cancel
        self.assertIsNone(lens.service(self.browser,{}));self.browser.close.assert_called_once()
        self.assertEqual(lens.status()['failure'],'interrupted');self.assertEqual(lens.status()['window'],'closed')

    def test_pause_after_human_success_before_minimize_closes(self):
        def success_then_cancel(*args):self.success(*args);self.pause_resume();return True
        lens.request();self.browser.human_session.side_effect=success_then_cancel
        self.assertIsNone(lens.service(self.browser,{}));self.browser.minimize.assert_not_called()
        self.assertEqual(lens.status()['window'],'closed')

    def test_pause_during_minimize_is_caught_at_final_transaction(self):
        lens.request();self.browser.minimize.side_effect=lambda:(self.pause_resume() or True)
        self.assertIsNone(lens.service(self.browser,{}));self.browser.close.assert_called_once()
        self.assertEqual(lens.status()['failure'],'interrupted');self.assertEqual(lens.status()['window'],'closed')

    def test_rapid_pause_resume_after_completed_session_closes_before_reuse(self):
        lens.request();lens.service(self.browser,{});self.pause_resume()
        self.assertIsNone(lens.service(self.browser,{}));self.browser.close.assert_called_once()
        self.assertEqual(lens.status()['window'],'closed')

    def test_server_restart_cancels_open_request_without_replay(self):
        def restart(url,admitted,observation):observation('load');lens.server_started();admitted()
        lens.request();self.browser.human_session.side_effect=restart
        self.assertIsNone(lens.service(self.browser,{}));self.assertEqual(lens.status()['failure'],'interrupted')
        lens.service(None,{})
        self.assertEqual(self.browser.human_session.call_count,1)

    def test_worker_restart_preserves_failed_receipt_and_cancels_marker(self):
        lens.request();old=self.raw()['request_id'];lens.initialize()
        self.assertEqual(self.raw()['request_id'],old);self.assertEqual(lens.status()['failure'],'interrupted')
        self.assertFalse((app.DATA/'browser-resume').exists())

    def test_dead_owner_never_reports_retained_window_as_open(self):
        lens.request();lens.service(self.browser,{})
        (app.DATA/'browser-heartbeat').write_text(json.dumps({'pid':-1,'timestamp':time.time()}))
        self.assertFalse(lens.status()['alive']);self.assertEqual(lens.status()['window'],'unknown')
        with self.assertRaises(ValueError):lens.request()

    def test_unknown_closure_retains_failure_and_exits_instead_of_retry(self):
        lens.request();self.browser.human_session.side_effect=ValueError()
        self.browser.close.side_effect=owner.ClosureUnknown('fixture')
        with self.assertRaises(owner.ClosureUnknown):lens.service(self.browser,{})
        self.assertEqual(self.raw()['window'],'unknown');self.assertEqual(self.raw()['stage'],'closure')
        with self.assertRaises(ValueError):lens.request()

    def test_request_rejects_pause_missing_challenge_and_unregistered_owner(self):
        pause_control.change(True)
        with self.assertRaises(ValueError):lens.request()
        pause_control.change(False);search.legacy_status(human_verification=False)
        with self.assertRaises(ValueError):lens.request()
        self.assertNotIn('verification_url',lens.status());self.assertNotIn('owner',lens.status())

    def test_queued_generation_cancel_has_no_browser_launch(self):
        lens.request();self.pause_resume()
        with patch.object(search,'LensBrowser') as browser:lens.service(None,{})
        browser.assert_not_called();self.assertEqual(lens.status()['failure'],'interrupted')
        self.assertFalse((app.DATA/'browser-resume').exists())

    def test_server_restart_removes_queued_wake_marker(self):
        lens.request();lens.server_started()
        self.assertFalse((app.DATA/'browser-resume').exists());self.assertEqual(lens.status()['failure'],'interrupted')

    def test_new_request_retains_window_truth_until_restart_closes_it(self):
        lens.request();lens.service(self.browser,{})
        search.legacy_status(human_verification=True);lens.request()
        self.assertEqual(self.raw()['window'],'minimized')
        lens.server_started();self.assertEqual(self.raw()['phase'],'closing')
        self.assertIsNone(lens.service(self.browser,{}));self.browser.close.assert_called_once()
        self.assertEqual(self.raw()['window'],'closed');self.assertEqual(self.raw()['failure'],'interrupted')


class CompletionTests(unittest.TestCase):
    def page(self,url,text='Google Search'):
        page=Mock();page.url=url;page.locator.return_value.inner_text.return_value=text
        page.locator.return_value.evaluate_all.return_value=True
        return page

    def test_unknown_or_unrelated_pages_never_mean_verified(self):
        for url,text in [('https://evil.example/search','Search'),('https://www.google.com/privacy','Google'),
                         ('https://www.google.com/search',''),('https://www.google.com/search','Something went wrong'),
                         ('https://secret@www.google.com/search','Google'),('http://www.google.com/search','Google'),
                         ('https://www.google.com:8443/search','Google'),('https://www.google.com/sorry/','Google')]:
            self.assertFalse(search.verification_complete(self.page(url,text)),url)

    def test_expected_page_needs_usable_visible_control(self):
        page=self.page('https://www.google.com/imghp');self.assertTrue(search.verification_complete(page))
        page.locator.return_value.evaluate_all.return_value=False;page.get_by_role.return_value.evaluate_all.return_value=False
        self.assertFalse(search.verification_complete(page))

    def test_no_browser_owner_means_no_driver_or_profile(self):
        with patch.object(owner,'_owner',None):
            with self.assertRaises(ValueError):owner.acquire()


class BrowserOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app,'DATA',self.root))
        self.enterContext(patch('maintenance.browser_cache'))
        self.enterContext(patch.object(lens,'session_closed'))
        self.acquire=self.enterContext(patch.object(owner,'acquire',return_value=self.root/'lens-profile'))
        self.real_release=owner.release
        self.release=self.enterContext(patch.object(owner,'release'))
        self.playwright=self.enterContext(patch('playwright.sync_api.sync_playwright'))
        self.runtime=self.playwright.return_value.start.return_value
        self.context=self.runtime.chromium.launch_persistent_context.return_value
        self.context.pages=[Mock()]

    def test_ownership_is_required_before_playwright_start_and_assignment_failure_launches_nothing(self):
        self.acquire.side_effect=ValueError('Job assignment failure')
        with self.assertRaises(ValueError):search.LensBrowser({}).open()
        self.playwright.assert_not_called()

    def test_profile_admission_precedes_driver_and_normal_close_stops_then_releases(self):
        events=[];self.acquire.side_effect=lambda:(events.append('acquire') or self.root/'lens-profile')
        self.playwright.return_value.start.side_effect=lambda:(events.append('driver') or self.runtime)
        self.runtime.stop.side_effect=lambda:events.append('stop')
        self.release.side_effect=lambda:events.append('release')
        browser=search.LensBrowser({});browser.open();browser.close()
        self.assertEqual(events,['acquire','driver','stop','release'])
        self.assertTrue(self.runtime.chromium.launch_persistent_context.call_args.kwargs['headless'])

    def test_launch_failure_stops_driver_before_lease_release(self):
        self.runtime.chromium.launch_persistent_context.side_effect=RuntimeError('launch failed')
        with self.assertRaises(RuntimeError):search.LensBrowser({}).open()
        self.runtime.stop.assert_called_once();self.release.assert_called_once()

    def test_cancellation_after_driver_start_does_not_launch_window(self):
        admitted=Mock(side_effect=[None,None,None,pause_control.PauseRequested()])
        with self.assertRaises(pause_control.PauseRequested):search.LensBrowser({}).open(True,admitted)
        self.runtime.chromium.launch_persistent_context.assert_not_called();self.release.assert_called_once()

    def test_closure_unknown_preserves_lease_and_escapes_worker_exception_handlers(self):
        browser=search.LensBrowser({});browser.open()
        self.release.side_effect=owner.ClosureUnknown('fixture')
        with self.assertRaises(owner.ClosureUnknown):browser.close()
        self.assertTrue(browser.leased);self.assertFalse(issubclass(owner.ClosureUnknown,Exception))

    def test_active_descendant_or_query_failure_never_releases_lock(self):
        for query in (Mock(return_value=2),Mock(side_effect=owner.ClosureUnknown('query'))):
            lease=Mock()
            with patch.object(owner,'_query',query),patch.object(owner,'_lease',lease),patch.object(owner.time,'monotonic',side_effect=[0,6]):
                with self.assertRaises(owner.ClosureUnknown):self.real_release()
                lease.close.assert_not_called()

    def test_never_opened_close_does_not_touch_any_profile(self):
        with patch('maintenance.browser_cache') as cleanup,patch.object(owner,'checked_profile') as checked:
            search.LensBrowser({}).close()
        cleanup.assert_not_called();checked.assert_not_called();self.release.assert_not_called()

    def test_cleanup_requires_confirmed_closure_and_valid_profile_before_release(self):
        browser=search.LensBrowser({});browser.open();events=[]
        with patch.object(owner,'closed',side_effect=lambda:events.append('closed')),patch.object(owner,'checked_profile',side_effect=lambda:(events.append('validate') or self.root/'lens-profile')),patch('maintenance.browser_cache',side_effect=lambda _:events.append('cleanup')):
            self.release.side_effect=lambda:events.append('release');browser.close()
        self.assertEqual(events,['closed','validate','cleanup','release'])

    def test_redirected_profile_never_reaches_cleanup(self):
        browser=search.LensBrowser({});browser.open()
        with patch.object(owner,'checked_profile',side_effect=ValueError('redirected')),patch('maintenance.browser_cache') as cleanup:
            with self.assertRaises(ValueError):browser.close()
        cleanup.assert_not_called();self.release.assert_called_once()

    def test_redirected_lock_file_is_rejected_before_open_or_write(self):
        lock=app.DATA/'lens-profile.lock'
        with patch.object(Path,'exists',return_value=True),patch.object(Path,'is_symlink',autospec=True,side_effect=lambda p:p==lock),patch.object(Path,'lstat') as stat,patch.object(Path,'open') as opened:
            stat.return_value.st_file_attributes=0
            with self.assertRaises(ValueError):owner.checked_profile()
        opened.assert_not_called()
