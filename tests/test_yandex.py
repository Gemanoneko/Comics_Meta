"""Offline Yandex routing, admission, ownership and interruption regressions."""
import io
import json
import os
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
import app
import free_search_browser as browser
import pause_control
import source_scheduling
import web_search as web
import yandex_verification as verification
from test_worker import scratch_directory
import test_free_search_browser as regular


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app,'BASE',self.root))
        self.enterContext(patch.object(app,'STATE_ROOT',self.root))
        self.enterContext(patch.object(app,'DATA',self.root/'data'))
        self.now=1_000_000
        self.enterContext(patch.object(time,'time',side_effect=lambda:self.now))
        self.enterContext(patch.object(web,'config',return_value={}))
        self.enterContext(patch.object(verification,'_owner',None))
        pause_control.requested();verification.initialize()
        (app.DATA/'queue').mkdir()
        self.heartbeat()
        self.browser=self.enterContext(patch.object(browser,'verify_yandex',side_effect=AssertionError('No unexpected visible session')))
        self.enterContext(patch.object(browser,'close'))

    def heartbeat(self):
        (app.DATA/'queue/heartbeat').write_text(json.dumps({'pid':os.getpid(),'timestamp':self.now}))

    def state(self):
        with app.db() as con:return verification.read(con)

    def count(self):
        with app.db() as con:
            if not con.execute("SELECT 1 FROM sqlite_master WHERE name='web_requests'").fetchone():return 0
            return con.execute('SELECT COUNT(*) FROM web_requests').fetchone()[0]

    def challenge(self):verification.required('https://yandex.com/showcaptcha?fixture=1','Fixture #1 comics')
    def queue(self):self.challenge();return verification.request({'engine':'yandex'})

    def test_only_explicit_yandex_body_and_real_challenge_can_queue(self):
        for body in ({},{'engine':'bing'},{'engine':'yandex','url':'https://evil.example/'},[],'yandex'):
            with self.assertRaises(ValueError):verification.request(body)
        with self.assertRaises(ValueError):verification.request({'engine':'yandex'})
        self.assertFalse(verification.service());self.assertEqual(self.count(),0)

    def test_duplicate_intent_is_idempotent_and_never_opens_from_status(self):
        self.queue();first=self.state()['request']
        self.assertEqual(verification.request({'engine':'yandex'})['state'],'already_requested')
        self.assertEqual(self.state()['request'],first)
        for _ in range(3):self.assertTrue(verification.status()['verification_pending'])
        self.browser.assert_not_called();self.assertEqual(self.count(),0)
        public=verification.status()
        self.assertNotIn('url',public);self.assertNotIn('query',public);self.assertNotIn('owner',public)

    def test_shared_full_budget_queues_without_reserving_or_opening(self):
        self.queue()
        with app.db() as con:
            con.execute('CREATE TABLE web_requests(timestamp REAL)')
            con.executemany('INSERT INTO web_requests VALUES(?)',[(self.now-200,)]*300)
        self.assertFalse(verification.service());self.assertEqual(self.count(),300)
        status=verification.status();self.assertEqual(status['availability'],'daily_budget_wait')
        self.assertEqual(status['retry_at'],self.now-200+86400);self.assertEqual(status['phase'],'queued')

    def test_slow_startup_navigation_fence_keeps_actual_120_seconds(self):
        # Search reserves t0, starts navigation t30. A verification at t120
        # must remain queued until t150, irrespective of its faster startup.
        with app.db() as con:
            con.execute('CREATE TABLE web_requests(timestamp REAL)');con.execute('INSERT INTO web_requests VALUES(?)',(self.now,))
        self.now+=30;self.assertEqual(web.admit_navigation(),0)
        self.now+=90;self.heartbeat();self.queue()
        self.assertFalse(verification.service());self.assertEqual(self.count(),1)
        self.assertEqual(verification.status()['retry_at'],self.now+30)
        self.assertEqual(web.free_engine_status('bing')['retry_at'],self.now+30)
        self.assertEqual(web.admit_navigation(),self.now+30)
        self.now+=30;self.heartbeat();self.assertEqual(web.admit_navigation(),0)
        self.assertEqual(self.count(),1)  # The fence never changes quota usage.

    def test_normal_navigation_guard_uses_same_fence_without_cooldown_reset(self):
        self.assertEqual(web.admit_navigation(),0)
        self.now+=10
        with patch.object(browser,'search',side_effect=browser.NavigationWait(self.now+110)):
            with self.assertRaises(web.SearchBlocked) as caught:web.free_browser_search('Fixture','ddg')
        self.assertTrue(caught.exception.pacing);self.assertEqual(caught.exception.retry_at,self.now+110)
        self.assertEqual(self.count(),0)

    def test_verification_delayed_start_blocks_next_normal_engine_without_extra_charge(self):
        self.queue()
        def verify(url,query,opened,admitted):
            self.now+=40;self.heartbeat();admitted();self.assertEqual(web.admit_navigation(),0);opened();return True
        self.browser.side_effect=verify
        self.assertTrue(verification.service());self.assertEqual(self.count(),1)
        self.now+=80;self.heartbeat()
        with patch.object(web,'free_browser_search') as search:
            with self.assertRaises(web.SearchBlocked) as caught:web.search('Next issue',True,'bing')
            self.assertEqual(caught.exception.retry_at,self.now+40);search.assert_not_called()
        self.assertEqual(self.count(),1)

    def test_lower_cap_longer_pacing_and_longer_hold_preserved(self):
        self.queue()
        with patch.object(web,'config',return_value={'free_daily_request_limit':2,'free_min_interval_seconds':900}):
            with app.db() as con:
                con.execute('CREATE TABLE web_requests(timestamp REAL)');con.execute('INSERT INTO web_requests VALUES(?)',(self.now-120,))
                con.execute('CREATE TABLE web_state(id INTEGER PRIMARY KEY,blocked_until REAL)');con.execute('INSERT INTO web_state VALUES(4,?)',(self.now+1800,))
            self.assertFalse(verification.service());self.assertEqual(verification.status()['retry_at'],self.now+1800)
            with app.db() as con:con.execute('UPDATE web_state SET blocked_until=0 WHERE id=4')
            self.assertEqual(verification.status()['retry_at'],self.now+780)
            with app.db() as con:con.execute('INSERT INTO web_requests VALUES(?)',(self.now-5000,))
            self.assertEqual(verification.status()['availability'],'daily_budget_wait')

    def test_success_closes_before_clearing_only_human_flag(self):
        self.queue()
        with app.db() as con:
            con.execute('CREATE TABLE web_state(id INTEGER PRIMARY KEY,blocked_until REAL)')
            con.executemany('INSERT INTO web_state VALUES(?,?)',[(1,self.now+100),(3,self.now+200),(4,0)])
        def verify(url,query,opened,admitted):
            self.assertEqual(self.count(),1);opened();self.assertEqual(self.state()['phase'],'open')
            with app.db() as con:con.execute('UPDATE web_state SET blocked_until=? WHERE id=4',(self.now+700,))
            return True
        self.browser.side_effect=verify
        browser.close.side_effect=lambda:self.assertTrue(self.state()['human_verification'])
        self.assertTrue(verification.service());self.assertEqual(self.state()['phase'],'verified')
        self.assertFalse(self.state()['human_verification']);self.assertEqual(self.state()['window'],'closed')
        with app.db() as con:self.assertEqual([tuple(row) for row in con.execute('SELECT * FROM web_state ORDER BY id')],[(1,self.now+100),(3,self.now+200),(4,self.now+700)])
        self.assertEqual(self.count(),1);self.assertFalse(verification.service())

    def test_failure_or_user_close_keeps_challenge_and_counted_attempt(self):
        self.queue();self.browser.side_effect=lambda url,query,opened,admitted:(opened(),False)[1]
        self.assertTrue(verification.service());self.assertTrue(self.state()['human_verification'])
        self.assertEqual(self.state()['phase'],'failed');self.assertEqual(self.count(),1)

    def test_launch_failure_exposes_retry_without_automatic_second_window(self):
        self.queue();self.browser.side_effect=ValueError('private diagnostic')
        self.assertTrue(verification.service());self.assertEqual(verification.status()['failure'],'open')
        self.assertFalse(verification.service());self.browser.assert_called_once()

    def test_unproven_closure_cannot_clear_human_or_claim_success(self):
        self.queue();self.browser.side_effect=lambda url,query,opened,admitted:True
        browser.close.side_effect=browser.BrowserUnavailable('closure unverified')
        with self.assertRaises(browser.BrowserUnavailable):verification.service()
        self.assertTrue(self.state()['human_verification']);self.assertNotEqual(self.state()['phase'],'verified')

    def test_pause_and_resume_generation_cancel_unconsumed_intent(self):
        self.queue();pause_control.change(True);pause_control.change(False)
        self.assertFalse(verification.service());self.assertIsNone(self.state()['request']);self.assertEqual(self.count(),0)
        self.assertFalse(verification.service())

    def test_pause_during_open_closes_then_preserves_challenge(self):
        self.queue()
        def verify(url,query,opened,admitted):opened();pause_control.change(True);raise pause_control.PauseRequested()
        self.browser.side_effect=verify
        self.assertTrue(verification.service());self.assertTrue(self.state()['human_verification'])
        self.assertIsNone(self.state()['request']);self.assertEqual(verification.status()['phase'],'paused')
        pause_control.change(False);self.assertFalse(verification.service())

    def test_quit_during_open_closes_and_keeps_the_challenge(self):
        self.queue()
        def verify(url,query,opened,admitted):
            opened();admitted();pause_control.request_stop();admitted()
            self.fail('Quit was not noticed')
        self.browser.side_effect=verify
        with patch.object(pause_control,'_stop_baseline',pause_control.stop_generation()):
            self.assertTrue(verification.service())
        self.assertTrue(self.state()['human_verification']);self.assertIsNone(self.state()['request'])
        self.assertEqual(self.state()['failure'],'paused')

    def test_pause_resume_between_observations_cancels_original_intent(self):
        self.queue()
        def verify(url,query,opened,admitted):
            opened();admitted();pause_control.change(True);pause_control.change(False);admitted()
            self.fail('A cancelled generation was accepted')
        self.browser.side_effect=verify
        self.assertTrue(verification.service());self.assertTrue(self.state()['human_verification'])
        self.assertIsNone(self.state()['request']);self.assertFalse(verification.service())

    def test_server_restart_invalidates_queued_and_open_surviving_worker_intent(self):
        self.queue();verification.server_started()
        self.assertFalse(verification.service());self.assertEqual(self.count(),0)
        verification.request({'engine':'yandex'})
        def verify(url,query,opened,admitted):
            opened();verification.server_started();admitted()
            self.fail('Server restart failed to invalidate intent')
        self.browser.side_effect=verify
        self.assertTrue(verification.service());self.assertTrue(self.state()['human_verification'])
        self.assertEqual(self.state()['phase'],'required');self.assertEqual(self.state()['window'],'closed')
        self.assertFalse(verification.service())

    def test_restart_cancels_visible_intent_and_stale_owner_cannot_request(self):
        self.queue();owner=self.state()['owner'];verification.initialize()
        self.assertNotEqual(self.state()['owner'],owner);self.assertIsNone(self.state()['request'])
        self.assertFalse(verification.service())
        self.now+=30
        with self.assertRaisesRegex(ValueError,'unavailable'):verification.request({'engine':'yandex'})
        self.assertFalse(verification.status()['alive'])

    def test_yandex_cache_and_hold_identity_cannot_alias_existing_engines(self):
        self.assertEqual(web.free_state_id('yandex'),4)
        self.assertEqual(len({web.cached('Fixture',True,e)[0] for e in web.FREE_ENGINES}),3)
        with patch.object(web,'free_browser_search',return_value=[{'url':'https://example.org/issue','title':'Fixture #1'}]) as search:
            result=web.search('Fixture',True,'yandex');self.assertEqual(result[0]['engine'],'yandex')
            self.challenge();self.assertEqual(web.search('Fixture',True,'yandex'),result)
            self.assertEqual(search.call_count,1)
            with self.assertRaisesRegex(web.SearchBlocked,'verification'):web.search('Other',True,'yandex')
        self.assertEqual(self.count(),1)

    def test_actual_challenge_marks_only_yandex_and_ordinary_error_does_not(self):
        with patch.object(browser,'search',side_effect=browser.HumanVerification('https://yandex.com/showcaptcha','Fixture')):
            with self.assertRaises(web.SearchBlocked):web.search('Fixture',True,'yandex')
        self.assertTrue(self.state()['human_verification']);self.assertEqual(self.count(),1)
        self.assertEqual(web.free_engine_status('yandex')['status'],'human_verification')
        self.assertNotEqual(web.free_engine_status('bing')['status'],'human_verification')

    def test_ordinary_dom_failure_is_cooldown_not_human_verification(self):
        with patch.object(browser,'search',side_effect=browser.BrowserUnavailable('unready DOM')):
            with self.assertRaises(web.SearchBlocked):web.search('Fixture',True,'yandex')
        self.assertFalse(self.state()['human_verification']);self.assertEqual(self.state()['phase'],'unavailable')
        self.assertEqual(web.free_engine_status('yandex')['retry_at'],self.now+3600)

    def test_yandex_schedule_tag_roundtrips_and_human_hold_blocks_retry(self):
        failure=web.SearchBlocked('Needs verification','free_web',0,'yandex')
        attempt=source_scheduling.record({},None,failure,{},self.now)
        self.assertEqual(attempt['engine'],'yandex')
        status={'free_web':{'engines':{'yandex':{'status':'human_verification','retry_at':0}}}}
        self.assertFalse(source_scheduling.ready('General free web',attempt,status,self.now+10000))
        status['free_web']['engines']['bing']={'status':'available','retry_at':0}
        self.assertFalse(source_scheduling.ready('General free web',attempt,status,self.now+30))
        self.assertTrue(source_scheduling.ready('General free web',attempt,status,self.now+3600))

    def test_endpoint_rejects_untrusted_origin_pause_and_arbitrary_url(self):
        self.challenge()
        handler=object.__new__(app.Handler);handler.server=SimpleNamespace(server_port=8765)
        handler.path='/api/yandex-verification';handler.respond=Mock()
        def post(body,origin='http://127.0.0.1:8765'):
            raw=json.dumps(body).encode();handler.rfile=io.BytesIO(raw)
            handler.headers={'Origin':origin,'Host':'127.0.0.1:8765','Content-Length':str(len(raw))}
            handler.do_POST();return handler.respond.call_args
        self.assertEqual(post({'engine':'yandex'},'https://evil.example').args[1],403)
        self.assertEqual(post({'engine':'yandex','url':'https://evil.example'}).args[1],400)
        self.assertEqual(post({'engine':'yandex'}).args[0]['state'],'queued')
        pause_control.change(True);self.assertEqual(post({'engine':'yandex'}).args[1],400)


class YandexBrowserTests(unittest.TestCase):
    def setUp(self):regular.RegularSearchTests.setUp(self)

    def test_normal_query_dedicated_profile_and_text_parameter(self):
        self.assertTrue(browser.search('Fixture #1 comics','yandex'))
        self.assertIn('/search/?text=Fixture+%231+comics',self.page.goto.call_args.args[0])
        args=self.runtime.chromium.launch_persistent_context.call_args
        self.assertEqual(args.args[0],str(self.root/'yandex-profile'));self.assertTrue(args.kwargs['headless'])

    def test_observed_challenge_has_safe_retained_url_without_interaction(self):
        self.page.goto.side_effect=lambda *a,**kw:setattr(self.page,'url','https://yandex.com/showcaptcha?fixture=1')
        self.body.inner_text.return_value='Are you not a robot?'
        with self.assertRaises(browser.HumanVerification) as caught:browser.search('Fixture','yandex')
        self.assertEqual(caught.exception.query,'Fixture');self.page.click.assert_not_called()
        self.context.close.assert_called_once()

    def test_untrusted_retained_challenge_url_never_launches(self):
        for url in ('http://yandex.com/showcaptcha','https://yandex.com.evil.example/showcaptcha','https://user:secret@yandex.com/showcaptcha','https://127.0.0.1/showcaptcha','https://yandex.com:444/showcaptcha','https://yandex.com/mail'):
            self.assertFalse(browser.yandex_url(url))
            with self.assertRaises(browser.BrowserUnavailable):browser.verify_yandex(url,'Fixture',Mock(),Mock())
        self.runtime.chromium.launch_persistent_context.assert_not_called()

    def test_human_session_observes_rendered_success_then_closes_profile(self):
        self.page.is_closed.return_value=False
        self.page.evaluate.return_value={'items':[{'url':'https://example.org/issue','title':'Fixture'}]}
        self.page.goto.side_effect=lambda *a,**kw:setattr(self.page,'url','https://yandex.com/search/?text=Fixture')
        opened=Mock()
        self.assertTrue(browser.verify_yandex('https://yandex.com/showcaptcha','Fixture',opened,Mock()))
        self.assertFalse(self.runtime.chromium.launch_persistent_context.call_args.kwargs['headless'])
        opened.assert_called_once();self.page.click.assert_not_called();self.context.close.assert_called_once();browser.close()

    def test_closed_or_timed_out_window_does_not_clear_challenge(self):
        self.page.is_closed.return_value=True
        self.assertFalse(browser.verify_yandex('https://yandex.com/showcaptcha','Fixture',Mock(),Mock()))
        self.context.close.assert_called_once()

    def test_popup_and_navigation_guards_do_not_allow_external_destination(self):
        browser.search('Fixture','yandex');route_handler=self.context.route.call_args.args[1]
        for url,allowed in [('https://yandex.com/showcaptcha',True),('https://evil.example/search/',False),('https://yandex.com/mail',False)]:
            route=Mock();route.request.url=url;route.request.is_navigation_request.return_value=True;route.request.frame.parent_frame=None
            route_handler(route);(route.continue_ if allowed else route.abort).assert_called_once()
        popup=Mock();self.context.on.call_args.args[1](popup);popup.close.assert_called_once()

    def test_cancellation_after_driver_start_does_not_launch_visible_browser(self):
        admitted=Mock(side_effect=[None,None,pause_control.PauseRequested()])
        with self.assertRaises(pause_control.PauseRequested):browser.verify_yandex('https://yandex.com/showcaptcha','Fixture',Mock(),admitted)
        self.runtime.chromium.launch_persistent_context.assert_not_called();self.runtime.stop.assert_called_once()

    def test_cancellation_after_launch_prevents_navigation_and_closes(self):
        admitted=Mock(side_effect=[None,None,None,pause_control.PauseRequested()])
        with self.assertRaises(pause_control.PauseRequested):browser.verify_yandex('https://yandex.com/showcaptcha','Fixture',Mock(),admitted)
        self.page.goto.assert_not_called();self.context.close.assert_called_once()


class VersionTests(unittest.TestCase):
    def test_server_reports_captured_version_after_file_changes(self):
        root=Path(self.enterContext(scratch_directory()));(root/'VERSION').write_text('0.1.0')
        with patch.object(app,'BASE',root),patch.object(app,'STATE_ROOT',root),patch.object(app,'DATA',root/'data'),patch.object(app.ThreadingHTTPServer,'__init__',return_value=None):
            server=app.LocalServer(('127.0.0.1',0),app.Handler)
            (root/'VERSION').write_text('9.9.9')
            self.assertEqual(server.loaded_version,'0.1.0')
            self.assertEqual(app.LocalServer(('127.0.0.1',0),app.Handler).loaded_version,'9.9.9')
            (root/'VERSION').write_bytes(bytes([255]))
            self.assertEqual(app.LocalServer(('127.0.0.1',0),app.Handler).loaded_version,'')


if __name__=='__main__':unittest.main()
