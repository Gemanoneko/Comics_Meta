"""Isolated free fallback fixtures; no real requests, models or archive writes."""
import json
import hashlib
import urllib.error
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
import app,automatic,providers,research,source_scheduling as scheduling,web_search as web
from provider_wait import ProviderDeferred
from test_worker import scratch_directory


class FreeResearchTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app,'DATA',self.root/'data'))
        self.enterContext(patch.object(app,'BASE',self.root))
        self.enterContext(patch.object(research,'CACHE',self.root/'evidence'))
        self.now=100000
        self.enterContext(patch.object(web.time,'time',return_value=self.now))
        self.options={'provider':'brave','daily_request_limit':100,'free_daily_request_limit':100}
        self.enterContext(patch.object(web,'config',side_effect=lambda:self.options))
        self.enterContext(patch.object(web,'free_browser_search',side_effect=AssertionError('Unexpected browser request in isolated fixture')))
        with app.db() as con:
            con.execute('CREATE TABLE IF NOT EXISTS web_state(id INTEGER PRIMARY KEY,blocked_until REAL)')
            con.execute('CREATE TABLE IF NOT EXISTS web_requests(timestamp REAL)')
            con.execute('INSERT OR REPLACE INTO web_state VALUES(1,?)',(self.now+7200,))
        self.row={'path':str(self.root/'Example 001.cbz'),'series':'Example','number':'1','year':'2024'}
        self.old={'Series':'Example','Number':'1','Publisher':'Synthetic Press'}
        self.result={'fields':{'Writer':'Verified fixture creator'},'sources':[{'url':'https://example.org/issue','text':'premise '*25}],'status':'web_issue_found'}

    def test_explicit_free_ignores_brave_hold_and_never_uses_paid_key(self):
        with patch.object(web,'free_browser_search',return_value=[{'url':'https://example.org/issue','title':'Example #1'}]) as read,patch.object(web,'key') as key:
            self.assertEqual(web.free_status()['status'],'available')
            self.assertEqual(web.search('Example',free_only=True)[0]['url'],'https://example.org/issue')
            read.assert_called_once_with('Example','ddg')
            key.assert_not_called()
        with app.db() as con:self.assertEqual(con.execute('SELECT blocked_until FROM web_state WHERE id=1').fetchone()[0],self.now+7200)

    def test_installed_free_hold_is_retained_with_exact_retry(self):
        self.options['provider']='free'
        with patch.object(web,'read') as read:
            with self.assertRaises(web.SearchBlocked) as caught:web.search('Example',free_only=True,engine='ddg')
            self.assertEqual(caught.exception.retry_at,self.now+7200)
            self.assertEqual(caught.exception.provider,'free_web')
            read.assert_not_called()

    def test_shared_application_cap_remains_with_exact_rolling_release(self):
        with app.db() as con:con.executemany('INSERT INTO web_requests VALUES(?)',[(self.now-100,)]*100)
        self.assertEqual(web.free_engine_status('ddg'),{'status':'daily_budget_wait','retry_at':self.now-100+86400})
        with patch.object(web,'read') as read:
            with self.assertRaises(web.SearchBlocked) as caught:web.search('Example',free_only=True,engine='ddg')
            self.assertEqual(caught.exception.retry_at,self.now-100+86400)
            read.assert_not_called()

    def test_cached_free_result_usable_while_held_and_exhausted(self):
        self.options['provider']='free'
        with app.db() as con:
            con.executemany('INSERT INTO web_requests VALUES(?)',[(self.now-100,)]*100)
            con.execute('INSERT INTO cache VALUES(?,?,?)',('web-search:free:Example',json.dumps([{'url':'https://example.org/cached'}]),self.now))
        with patch.object(web,'read') as read:
            self.assertEqual(web.search('Example',free_only=True),[{'url':'https://example.org/cached'}])
            read.assert_not_called()
        with app.db() as con:self.assertEqual(con.execute('SELECT COUNT(*) FROM web_requests').fetchone()[0],100)

    def test_challenge_sets_free_hold_and_observation_does_not_extend_it(self):
        with patch.object(web,'free_browser_search',side_effect=web.SearchBlocked('Free search requested human verification; no bypass attempted.')):
            with self.assertRaises(web.SearchBlocked) as caught:web.search('Example',free_only=True)
        self.assertEqual(caught.exception.retry_at,self.now+3600)
        with patch.object(web.time,'time',return_value=self.now+100),patch.object(web,'read') as read:
            with self.assertRaises(web.SearchBlocked) as again:web.search('Different',free_only=True,engine='ddg')
            self.assertEqual(again.exception.retry_at,self.now+3600)
            read.assert_not_called()
        with patch.object(web.time,'time',return_value=self.now+3600):self.assertEqual(web.free_status()['status'],'available')

    def test_new_browser_failure_preserves_concurrently_saved_longer_hold(self):
        def failed(query,engine='ddg'):
            with app.db() as con:con.execute('INSERT OR REPLACE INTO web_state VALUES(2,?)',(self.now+7200,))
            raise web.SearchBlocked('Fixture browser challenge')
        with patch.object(web,'free_browser_search',side_effect=failed):
            with self.assertRaises(web.SearchBlocked) as caught:web.search('Fixture',free_only=True)
        self.assertEqual(caught.exception.retry_at,self.now+7200)

    def previous(self,attempts=None):
        return {'version':9,'signature':[10,1],'retry_at':self.now+86400,'source_schedule':attempts or {}}

    def test_legacy_records_do_not_gain_immediate_free_retry(self):
        self.assertFalse(scheduling.due(self.previous(),[10,1],9,{'free_web':{'status':'available'}},now=self.now))

    def test_free_retry_expires_independently_but_future_miss_does_not_loop(self):
        prev=self.previous({'General free web':{'result':'unavailable','next_at':self.now+100}})
        self.assertFalse(scheduling.due(prev,[10,1],9,{'free_web':{'status':'cooldown_wait','retry_at':self.now+100}},now=self.now))
        self.assertTrue(scheduling.due(prev,[10,1],9,{'free_web':{'status':'available'}},now=self.now+100))
        prev['source_schedule']['General free web']=scheduling.record({},None,None,self.old,self.now+100)
        self.assertFalse(scheduling.due(prev,[10,1],9,{'free_web':{'status':'available'}},now=self.now+101))

    def test_due_free_error_cannot_spin_during_a_longer_global_hold(self):
        prev=self.previous({'General free web':{'result':'error','next_at':self.now-1}})
        self.assertFalse(scheduling.due(prev,[10,1],9,{'free_web':{'status':'cooldown_wait','retry_at':self.now+100}},now=self.now))

    def test_wiki_retry_independent_of_exhausted_free_search(self):
        prev=self.previous({'Wikipedia/wiki':{'result':'error','next_at':self.now}})
        self.assertTrue(scheduling.due(prev,[10,1],9,{'free_web':{'status':'daily_budget_wait','retry_at':self.now+5000}},now=self.now))

    def test_wiki_verified_lead_works_when_search_deferred(self):
        schedules={};seen=[]
        def completed(name,result,error):
            schedules[name]=scheduling.record(schedules.get(name,{}),result,error,self.old,self.now);seen.append(name)
        with patch.object(research,'general_lookup',side_effect=web.SearchBlocked('held','free_web',self.now+5000)), \
             patch.object(research,'wiki_candidates',return_value=[{'title':'Example','pageid':1}]), \
             patch.object(research,'resolve_leads',return_value=self.result):
            result,found=automatic.free_fallback(self.row,self.old,None,schedules,{'free_web':{'status':'daily_budget_wait','retry_at':self.now+5000}},completed)
        self.assertEqual(result,self.result);self.assertTrue(found)
        self.assertEqual(schedules['General free web']['next_at'],self.now+5000)
        self.assertEqual(seen,['General free web','Wikipedia/wiki'])

    def test_recorded_future_free_wait_skips_search_but_not_wiki(self):
        schedules={'General free web':{'result':'unavailable','next_at':self.now+5000}}
        with patch.object(research,'general_lookup') as general,patch.object(research,'wiki_candidates',return_value=[{'title':'Example','pageid':1}]),patch.object(research,'resolve_leads',return_value=self.result):
            self.assertEqual(automatic.free_fallback(self.row,self.old,None,schedules,{'free_web':{'status':'cooldown_wait','retry_at':self.now+5000}},Mock())[0],self.result)
            general.assert_not_called()

    def test_wrong_issue_and_broad_series_article_never_authorize_metadata(self):
        for title in ('Example','Example #2'):
            self.assertIsNone(research.verify_web_source(self.row,self.old,{'url':'https://example.org/page','title':title,'identity_text':'Synthetic Press 2024 premise'}))

    def test_general_lookup_propagates_wait_after_saving_diagnostics(self):
        with patch.object(web,'search',side_effect=web.SearchBlocked('held','free_web',self.now+5000)) as search:
            with self.assertRaises(ProviderDeferred) as caught:research.general_lookup(self.row,self.old)
        self.assertEqual(caught.exception.retry_at,self.now+5000)
        self.assertTrue(search.call_args.kwargs['free_only'])

    def discover(self,thin_issue=False,description=''):
        import archive_conversion,worker,local_model,research_runtime,discovery_state
        folder=self.root/'library';folder.mkdir();path=folder/'Example 001.cbz';path.write_bytes(b'isolated fixture')
        old={'Series':'Example','Number':'1','Publisher':'Synthetic Press'}
        if thin_issue:old['Web']='https://comicvine.gamespot.com/example/4000-1/'
        with app.db() as con:
            discovery_state.initialize(con)
            con.execute('INSERT INTO comics(path,root,size,mtime,series,number,year,metadata,status,seen) VALUES(?,?,?,?,?,?,?,?,?,?)',(str(path),str(folder),16,1,'Example','1','2024',json.dumps(old),'embedded',1))
        statuses={k:{'status':'human_verification','retry_at':self.now+5000} for k in scheduling.KEYS.values() if k!='free_web'}
        statuses['free_web']={'status':'available','retry_at':0}
        previous={'version':9,'signature':[16,1],'retry_at':0,'source_schedule':{name:{'result':'unavailable','next_at':self.now+5000} for name in scheduling.KEYS if name!='General free web'}}
        issue={'volume':{'name':'Example'},'issue_number':'1','description':description}
        synopsis={'summary':'Verified premise','model':'fixture','sources':['https://example.org/issue']}
        with patch.object(app,'scan'),patch.object(archive_conversion,'one',return_value=False), \
             patch.object(discovery_state,'load',return_value={'checked':{str(path):previous}}), \
             patch.object(providers,'statuses',return_value=statuses), \
             patch.object(worker,'QUEUE',self.root/'queue'),patch.object(worker,'enqueue') as enqueue, \
             patch.object(worker.pause_control,'requested',return_value=False), \
             patch.object(research_runtime,'reuse',return_value=None),patch.object(research_runtime,'remember'), \
             patch.object(automatic,'lookup_unidentified',return_value=None),patch.object(app,'api',return_value=issue if thin_issue else None), \
             patch.object(automatic,'verified_issue_fields',return_value={}), \
             patch.object(research,'publisher_lookup',return_value=None),patch.object(research,'resolve_leads',return_value=None), \
             patch.object(research,'general_lookup',return_value=self.result) as free,patch.object(research,'wiki_candidates') as wiki, \
             patch.object(local_model,'available',return_value=thin_issue),patch.object(local_model,'sourced_synopsis',return_value=synopsis):
            self.assertTrue(automatic.discover(folder,coverage_only=True))
            enqueue.assert_called_once();free.assert_called_once();wiki.assert_not_called()
            plan=json.loads(enqueue.call_args.args[0].read_text(encoding='utf-8'))
            return plan['entries'][0]

    def test_exhausted_apis_and_cover_sources_still_queue_verified_free_fields(self):
        self.assertEqual(self.discover()['fields']['Writer'],'Verified fixture creator')

    def test_thin_api_issue_can_queue_verified_free_synopsis(self):
        self.assertEqual(self.discover(thin_issue=True)['fields']['Summary'],'Verified premise')

    def test_short_positive_api_description_can_use_verified_free_synopsis(self):
        self.assertEqual(self.discover(thin_issue=True,description='<p>A brief placeholder synopsis.</p>')['fields']['Summary'],'Verified premise')

    def wiki_error(self,retry='120'):
        return urllib.error.HTTPError('https://en.wikipedia.org/w/api.php',429,'Too Many Requests',{'Retry-After':retry},None)

    def wiki_response(self,url,payload):
        response=Mock();response.url=url;response.read.return_value=json.dumps(payload).encode()
        response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        return response

    def test_wiki_429_blocks_next_comic_without_extending_deadline(self):
        url='https://en.wikipedia.org/w/api.php?action=query&one=1'
        with patch.object(research.urllib.request,'urlopen',side_effect=self.wiki_error()) as open:
            with self.assertRaises(ProviderDeferred) as first:research.fetch(url)
            self.assertEqual(first.exception.provider,'wikipedia')
            self.assertEqual(first.exception.retry_at,self.now+120)
            with patch.object(research.time,'time',return_value=self.now+10):
                with self.assertRaises(ProviderDeferred) as second:research.fetch(url+'&other=2')
            self.assertEqual(second.exception.retry_at,self.now+120);self.assertEqual(open.call_count,1)
        self.assertEqual(research.wiki_status()['retry_at'],self.now+120)

    def test_wiki_cached_response_usable_during_global_hold(self):
        research.wiki_rate_wait(self.wiki_error())
        url='https://en.wikipedia.org/w/api.php?action=cached'
        research.CACHE.mkdir();target=research.CACHE/(hashlib.sha256(url.encode()).hexdigest()+'.json')
        target.write_text('{"query":{"cached":true}}',encoding='utf-8')
        with patch.object(research.urllib.request,'urlopen') as open:
            self.assertTrue(research.fetch(url)['query']['cached']);open.assert_not_called()

    def test_wiki_deadline_expiry_allows_network_without_resetting_other_holds(self):
        research.wiki_rate_wait(self.wiki_error('1'))
        url='https://en.wikipedia.org/w/api.php?action=expired'
        with patch.object(research.time,'time',return_value=self.now+1),patch.object(research.urllib.request,'urlopen',return_value=self.wiki_response(url,{'query':{}})) as open:
            self.assertEqual(research.wiki_status()['status'],'available');self.assertEqual(research.fetch(url),{'query':{}});open.assert_called_once()
        with app.db() as con:self.assertEqual(con.execute('SELECT blocked_until FROM web_state WHERE id=1').fetchone()[0],self.now+7200)

    def test_wiki_http_date_retry_and_longer_hold_are_preserved(self):
        from email.utils import formatdate
        self.assertEqual(research.wiki_rate_wait(self.wiki_error(formatdate(self.now+600,usegmt=True))).retry_at,self.now+600)
        self.assertEqual(research.wiki_rate_wait(self.wiki_error('10')).retry_at,self.now+600)

    def test_wiki_invalid_retry_uses_existing_first_error_delay(self):
        self.assertEqual(research.wiki_rate_wait(self.wiki_error('invalid')).retry_at,self.now+3600)

    def test_wiki_global_wait_schedules_independently_and_recovers(self):
        prev=self.previous({'Wikipedia/wiki':{'result':'unavailable','next_at':self.now+120}})
        statuses={'wikipedia':{'status':'cooldown_wait','retry_at':self.now+120},'free_web':{'status':'daily_budget_wait','retry_at':self.now+5000}}
        self.assertFalse(scheduling.ready('Wikipedia/wiki',prev['source_schedule']['Wikipedia/wiki'],statuses,self.now))
        self.assertFalse(scheduling.due(prev,[10,1],9,statuses,now=self.now))
        statuses['wikipedia']={'status':'available','retry_at':0}
        self.assertTrue(scheduling.due(prev,[10,1],9,statuses,now=self.now+120))

    def test_comic_article_ranks_before_matching_tv_and_film(self):
        payload={'query':{'search':[{'title':'Example (TV series)','pageid':1},{'title':'Example (film)','pageid':2},{'title':'Example (comics)','pageid':3}]}}
        with patch.object(research,'fetch',return_value=payload):candidates=research.wiki_candidates(self.row,self.old)
        self.assertEqual(candidates[0]['pageid'],3);self.assertEqual(len(candidates),3)

    def test_wiki_footer_searches_do_not_consume_issue_lead_slots(self):
        research.save_evidence(self.row['path'],{'wiki_candidates':[{'title':'Example (comics)','pageid':1}]})
        footers=['https://www.google.com/search?q=Example','https://www.jstor.org/action/doBasicSearch?Query=Example']
        leads=footers+['https://example.org/article/'+str(i) for i in range(8)]+['https://example.org/comics/Example-1']
        payload={'query':{'pages':{'1':{'extlinks':[{'*':url} for url in leads]}}}}
        source={'url':leads[-1],'title':'Example #1','text':'Synthetic Press 2024 verified issue premise','image':'https://example.org/cover.jpg'}
        with patch.object(research,'fetch',return_value=payload),patch.object(web,'source',return_value=source) as fetch_source, \
             patch.object(web,'read',return_value=b'remote'),patch('reverse_image.cover',return_value=(b'local',None,None)),patch.object(automatic,'covers_agree',return_value=True):
            self.assertIsNotNone(research.resolve_leads(self.row,self.old))
        self.assertEqual(fetch_source.call_args.args[0],leads[-1]);self.assertEqual(fetch_source.call_count,1)
        evidence=json.loads((research.CACHE/('evidence-'+hashlib.sha256(self.row['path'].encode()).hexdigest()+'.json')).read_text(encoding='utf-8'))
        self.assertEqual(evidence['wiki_leads_skipped'],footers)

    def test_wiki_leads_keep_eight_limit_and_reject_wrong_issue(self):
        research.save_evidence(self.row['path'],{'wiki_candidates':[{'title':'Example (comics)','pageid':1}]})
        payload={'query':{'pages':{'1':{'extlinks':[{'*':'https://example.org/comics/Example-'+str(i)} for i in range(2,14)]}}}}
        source={'url':'https://example.org/comics/Example-2','title':'Example #2','identity_text':'Synthetic Press 2024','image':'cover.jpg'}
        with patch.object(research,'fetch',return_value=payload),patch.object(web,'source',return_value=source) as fetch_source,patch.object(web,'read') as cover:
            self.assertIsNone(research.resolve_leads(self.row,self.old));self.assertEqual(fetch_source.call_count,8);cover.assert_not_called()

    def test_wiki_extlinks_deferral_is_recorded_and_propagated(self):
        research.save_evidence(self.row['path'],{'wiki_candidates':[{'title':'Example (comics)','pageid':1}]})
        with patch.object(research,'fetch',side_effect=ProviderDeferred('held','wikipedia',self.now+120)):
            with self.assertRaises(ProviderDeferred) as caught:research.resolve_leads(self.row,self.old)
        self.assertEqual(caught.exception.retry_at,self.now+120)

    def test_free_trial_defaults_are_300_and_120_while_brave_limit_stays_100(self):
        self.options.pop('free_daily_request_limit')
        self.assertEqual(web.free_policy(),(300,120))
        self.assertEqual(self.options['daily_request_limit'],100)
        self.options.update(free_daily_request_limit=999,free_min_interval_seconds=1)
        self.assertEqual(web.free_policy(),(300,120))

    def test_free_300_boundary_preserves_legacy_ledger_and_exact_release(self):
        self.options['free_daily_request_limit']=300
        with app.db() as con:con.executemany('INSERT INTO web_requests VALUES(?)',[(self.now-1000,)]*300)
        self.assertEqual(web.free_engine_status('ddg'),{'status':'daily_budget_wait','retry_at':self.now-1000+86400})
        with patch.object(web,'read') as read:
            with self.assertRaises(web.SearchBlocked):web.search('Boundary',free_only=True)
            read.assert_not_called()
        with patch.object(web.time,'time',return_value=self.now-1000+86400),patch.object(web,'free_browser_search',return_value=[]):
            self.assertEqual(web.search('Reset',free_only=True),[])
        with app.db() as con:self.assertEqual(con.execute('SELECT COUNT(*) FROM web_requests').fetchone()[0],301)

    def test_free_pacing_119_waits_120_reserves_without_sleep(self):
        with app.db() as con:con.execute('INSERT INTO web_requests VALUES(?)',(self.now-119,))
        self.assertEqual(web.free_engine_status('ddg'),{'status':'pacing_wait','retry_at':self.now+1})
        with patch.object(web,'read') as read,patch.object(web.time,'sleep') as sleep:
            with self.assertRaises(web.SearchBlocked) as caught:web.search('Paced',free_only=True)
            self.assertEqual(caught.exception.retry_at,self.now+1);read.assert_not_called();sleep.assert_not_called()
        with app.db() as con:self.assertEqual(con.execute('SELECT COUNT(*) FROM web_requests').fetchone()[0],1)
        with patch.object(web.time,'time',return_value=self.now+1),patch.object(web,'free_browser_search',return_value=[]),patch.object(web.time,'sleep') as sleep:
            self.assertEqual(web.search('Paced',free_only=True),[]);sleep.assert_not_called()
        with app.db() as con:self.assertEqual(con.execute('SELECT COUNT(*) FROM web_requests').fetchone()[0],2)

    def test_free_cached_query_ignores_pacing_and_does_not_charge(self):
        with app.db() as con:
            con.execute('INSERT INTO web_requests VALUES(?)',(self.now,))
            con.execute('INSERT INTO cache VALUES(?,?,?)',('web-search:free:Cached',json.dumps([]),self.now))
        with patch.object(web,'read') as read:
            self.assertEqual(web.search('Cached',free_only=True,engine='ddg'),[]);read.assert_not_called()
        with app.db() as con:self.assertEqual(con.execute('SELECT COUNT(*) FROM web_requests').fetchone()[0],1)

    def test_free_concurrent_reservations_allow_one_request_and_no_sliding_wait(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        barrier=Barrier(2)
        def search(query):
            barrier.wait()
            try:return ('ok',web.search(query,free_only=True))
            except web.SearchBlocked as exc:return ('wait',exc.retry_at)
        with patch.object(web,'free_browser_search',return_value=[]) as read:
            with ThreadPoolExecutor(max_workers=2) as pool:
                one=pool.submit(search,'Concurrent1');two=pool.submit(search,'Concurrent2');results=[one.result(timeout=5),two.result(timeout=5)]
            self.assertEqual(sum(v[0]=='ok' for v in results),1);self.assertEqual(read.call_count,1)
            self.assertIn(('wait',self.now+120),results)
            with patch.object(web.time,'time',return_value=self.now+60):
                with self.assertRaises(web.SearchBlocked) as caught:web.search('Afterrestart',free_only=True)
            self.assertEqual(caught.exception.retry_at,self.now+120)
        with app.db() as con:self.assertEqual(con.execute('SELECT COUNT(*) FROM web_requests').fetchone()[0],1)

    def test_brave_keeps_100_cap_and_three_second_spacing(self):
        with app.db() as con:con.execute('UPDATE web_state SET blocked_until=0 WHERE id=1');con.execute('INSERT INTO web_requests VALUES(?)',(self.now-1,))
        with patch.object(web,'key',return_value='fixture-key'),patch.object(web,'read',return_value='{"web":{"results":[]}}') as read,patch.object(web.time,'sleep') as sleep:
            self.assertEqual(web.search('Vendor'),[]);sleep.assert_called_once_with(2);self.assertTrue(read.call_args.args[0].startswith('https://api.search.brave.com/'))
        with app.db() as con:con.executemany('INSERT INTO web_requests VALUES(?)',[(self.now-1000,)]*98)
        with patch.object(web,'read') as read:
            with self.assertRaises(web.SearchBlocked):web.search('Vendorlimit')
            read.assert_not_called()

    def test_pacing_and_challenge_holds_do_not_disable_wiki_or_move_deadlines(self):
        self.options['provider']='free'
        with app.db() as con:con.execute('INSERT INTO web_requests VALUES(?)',(self.now,))
        self.assertEqual(web.free_engine_status('ddg')['retry_at'],self.now+7200)
        prev=self.previous({'Wikipedia/wiki':{'result':'no_verified_match','next_at':self.now}})
        self.assertTrue(scheduling.due(prev,[10,1],9,{'free_web':web.free_status(),'wikipedia':{'status':'available'}},now=self.now))
        with patch.object(web,'read') as read:
            with self.assertRaises(web.SearchBlocked) as caught:web.search('Held',free_only=True,engine='ddg')
            self.assertEqual(caught.exception.retry_at,self.now+7200);read.assert_not_called()

    def test_bing_eligible_while_ddg_held_separate_cache_and_hold(self):
        self.options['provider']='free'
        with patch.object(web,'free_browser_search',return_value=[{'url':'https://example.org/issue','title':'Fixture #1'}]) as browser:
            result=web.search('Fixture',free_only=True)
            browser.assert_called_once_with('Fixture','bing')
            self.assertEqual(result[0]['engine'],'bing')
        with app.db() as con:
            self.assertEqual(con.execute('SELECT blocked_until FROM web_state WHERE id=1').fetchone()[0],self.now+7200)
            self.assertIsNotNone(con.execute('SELECT 1 FROM cache WHERE key=?',('web-search:bing:Fixture',)).fetchone())
            self.assertIsNone(con.execute('SELECT 1 FROM cache WHERE key=?',('web-search:free:Fixture',)).fetchone())

    def test_invalid_bing_cache_is_retained_while_budget_and_holds_still_block(self):
        self.options['provider']='free'
        raw=json.dumps([{'url':'https://www.lidl.com/','title':'','engine':'bing'}])
        key='web-search:bing:Fixture'
        with app.db() as con:
            con.execute('INSERT INTO cache VALUES(?,?,?)',(key,raw,self.now))
            con.execute('INSERT INTO web_state VALUES(3,?)',(self.now+8000,))
            con.executemany('INSERT INTO web_requests VALUES(?)',[(self.now-100,)]*100)
        with self.assertRaises(web.SearchBlocked) as caught:web.search('Fixture',True,engine='bing')
        self.assertEqual(caught.exception.retry_at,self.now+8000)
        with app.db() as con:
            self.assertEqual(con.execute('SELECT value FROM cache WHERE key=?',(key,)).fetchone()[0],raw)
            self.assertEqual(con.execute('SELECT COUNT(*) FROM web_requests').fetchone()[0],100)
            self.assertEqual(con.execute('SELECT blocked_until FROM web_state WHERE id=1').fetchone()[0],self.now+7200)

    def test_invalid_bing_cache_replacement_requires_normal_pacing_and_reservation(self):
        key='web-search:bing:Fixture'
        with app.db() as con:
            con.execute('INSERT INTO cache VALUES(?,?,?)',(key,json.dumps([{'url':'https://example.org/hidden','title':' '}]),self.now))
            con.execute('INSERT INTO web_requests VALUES(?)',(self.now-119,))
        with self.assertRaises(web.SearchBlocked) as caught:web.search('Fixture',True,engine='bing')
        self.assertEqual(caught.exception.retry_at,self.now+1)
        valid=[{'url':'https://example.org/issue','title':'Fixture #1'}]
        with patch.object(web.time,'time',return_value=self.now+1),patch.object(web,'free_browser_search',return_value=valid) as browser:
            self.assertEqual(web.search('Fixture',True,engine='bing')[0]['title'],'Fixture #1')
            browser.assert_called_once_with('Fixture','bing')
        with app.db() as con:self.assertEqual(con.execute('SELECT COUNT(*) FROM web_requests').fetchone()[0],2)

    def test_valid_bing_cache_and_explicit_empty_cache_stay_usable_during_holds(self):
        for query,value in [('Valid',[{'url':'https://example.org/issue','title':'Fixture #1','engine':'bing'}]),('Empty',[])]:
            with app.db() as con:
                con.execute('INSERT OR REPLACE INTO web_state VALUES(3,?)',(self.now+8000,))
                con.execute('INSERT INTO cache VALUES(?,?,?)',('web-search:bing:'+query,json.dumps(value),self.now))
            self.assertEqual(web.search(query,True,engine='bing'),value)
        with app.db() as con:self.assertEqual(con.execute('SELECT COUNT(*) FROM web_requests').fetchone()[0],0)

    def test_invalid_new_bing_results_do_not_poison_cache_or_claim_a_challenge(self):
        with patch.object(web,'free_browser_search',return_value=[{'url':'https://example.org/hidden','title':''}]):
            with self.assertRaises(web.SearchBlocked) as caught:web.search('Fixture',True,engine='bing')
        self.assertNotIn('human verification',str(caught.exception))
        self.assertEqual(caught.exception.retry_at,self.now+3600)
        with app.db() as con:
            self.assertIsNone(con.execute('SELECT * FROM cache WHERE key=?',('web-search:bing:Fixture',)).fetchone())
            self.assertEqual(con.execute('SELECT COUNT(*) FROM web_requests').fetchone()[0],1)
            self.assertEqual(con.execute('SELECT blocked_until FROM web_state WHERE id=1').fetchone()[0],self.now+7200)

    def test_empty_ddg_then_bing_is_next_paced_turn_not_second_request_now(self):
        with patch.object(web,'free_browser_search',return_value=[]) as browser:
            self.assertEqual(web.search('Fixture',True,engine='ddg'),[])
            with self.assertRaises(web.SearchBlocked) as wait:web.search('Fixture',True,engine='bing')
            self.assertEqual(wait.exception.retry_at,self.now+120)
            browser.assert_called_once_with('Fixture','ddg')
            with patch.object(web.time,'time',return_value=self.now+120):
                self.assertEqual(web.search('Fixture',True,engine='ddg'),[])
                self.assertEqual(web.search('Fixture',True,engine='bing'),[])
            self.assertEqual(browser.call_count,2)
        with app.db() as con:self.assertEqual(con.execute('SELECT COUNT(*) FROM web_requests').fetchone()[0],2)

    def test_cached_wrong_ddg_then_bing_same_query_and_cover_hint_still_verified(self):
        wrong={'url':'https://example.org/wrong','title':'Example #2','identity_text':'Synthetic Press 2024'}
        exact=dict(wrong,url='https://example.org/exact',title='Example #1')
        queries=[];covers=[]
        def search(query,free_only=False,engine=None):
            queries.append((query,engine));return [{'url':wrong['url'] if engine=='ddg' else exact['url']}]
        actual=research.verify_web_source
        def verify(row,old,source,cover_hint=None,**options):
            covers.append(cover_hint);return actual(row,old,source,cover_hint,**options)
        hint={'search_query':'Keep this hint for matching; do not submit another query'}
        with patch.object(web,'search',side_effect=search),patch.object(web,'source',side_effect=lambda url:wrong if url==wrong['url'] else exact),patch.object(research,'verify_web_source',side_effect=verify):
            self.assertIsNotNone(research.general_lookup(self.row,self.old,hint))
        self.assertEqual(queries,[('Example #1 comics','ddg'),('Example #1 comics','bing')]);self.assertEqual(covers,[hint,hint])

    def test_bing_tagged_future_wait_cannot_wake_on_ddg_availability(self):
        wait=web.SearchBlocked('Bing held','free_web',self.now+500,'bing')
        attempt=scheduling.record({},None,wait,self.old,self.now)
        prev=self.previous({'General free web':attempt})
        states={'free_web':{'status':'available','retry_at':0,'engines':{'ddg':{'status':'available','retry_at':0},'bing':{'status':'cooldown_wait','retry_at':self.now+500}}}}
        self.assertFalse(scheduling.due(prev,[10,1],9,states,now=self.now))
        self.assertFalse(scheduling.ready('General free web',attempt,states,self.now))
        states['free_web']['engines']['bing']={'status':'available','retry_at':0}
        self.assertTrue(scheduling.due(prev,[10,1],9,states,now=self.now+500))
        self.assertTrue(scheduling.ready('General free web',attempt,states,self.now+500))

    def test_actual_free_stage_records_engine_wait_without_losing_tag(self):
        schedules={}
        def search(query,free_only=False,engine=None):
            if engine=='ddg':return []
            raise web.SearchBlocked('Bing held','free_web',self.now+500,'bing')
        def completed(name,result,error):schedules[name]=scheduling.record({},result,error,self.old,self.now)
        with patch.object(web,'search',side_effect=search),patch.object(research,'wiki_candidates',return_value=[]):
            automatic.free_fallback(self.row,self.old,None,schedules,{},completed)
        self.assertEqual(schedules['General free web']['engine'],'bing')
        self.assertEqual(schedules['General free web']['next_at'],self.now+500)

    def test_both_engine_misses_use_ordinary_backoff_not_provider_recovery_loop(self):
        with patch.object(web,'search',return_value=[]):self.assertIsNone(research.general_lookup(self.row,self.old))
        attempt=scheduling.record({},None,None,self.old,self.now)
        self.assertEqual(attempt['next_at'],self.now+86400)
        states={'free_web':{'status':'available','retry_at':0,'engines':{e:{'status':'available','retry_at':0} for e in web.FREE_ENGINES}}}
        self.assertFalse(scheduling.due(self.previous({'General free web':attempt}),[10,1],9,states,now=self.now+120))

    def test_shared_concurrent_engines_reserve_only_one_and_cap_both(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        barrier=Barrier(2)
        def search(engine):
            barrier.wait()
            try:web.search('Fixture '+engine,True,engine=engine);return 'ok'
            except web.SearchBlocked:return 'wait'
        with patch.object(web,'free_browser_search',return_value=[]) as browser,ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(search,'ddg');b=pool.submit(search,'bing')
            self.assertCountEqual([a.result(timeout=5),b.result(timeout=5)],['ok','wait'])
            self.assertEqual(browser.call_count,1)
        self.options['free_daily_request_limit']=300
        with app.db() as con:con.executemany('INSERT INTO web_requests VALUES(?)',[(self.now-100,)]*299)
        states=web.free_status()
        self.assertTrue(all(state['status']=='daily_budget_wait' for state in states['engines'].values()))
