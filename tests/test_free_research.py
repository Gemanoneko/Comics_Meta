"""Isolated free fallback fixtures; no real requests, models or archive writes."""
import json
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
        self.options={'provider':'brave','daily_request_limit':100}
        self.enterContext(patch.object(web,'config',side_effect=lambda:self.options))
        with app.db() as con:
            con.execute('CREATE TABLE IF NOT EXISTS web_state(id INTEGER PRIMARY KEY,blocked_until REAL)')
            con.execute('CREATE TABLE IF NOT EXISTS web_requests(timestamp REAL)')
            con.execute('INSERT OR REPLACE INTO web_state VALUES(1,?)',(self.now+7200,))
        self.row={'path':str(self.root/'Example 001.cbz'),'series':'Example','number':'1','year':'2024'}
        self.old={'Series':'Example','Number':'1','Publisher':'Synthetic Press'}
        self.result={'fields':{'Writer':'Verified fixture creator'},'sources':[{'url':'https://example.org/issue','text':'premise '*25}],'status':'web_issue_found'}

    def test_explicit_free_ignores_brave_hold_and_never_uses_paid_key(self):
        with patch.object(web,'read',return_value='<a class="result__a" href="https://example.org/issue">Example #1</a>') as read,patch.object(web,'key') as key:
            self.assertEqual(web.free_status()['status'],'available')
            self.assertEqual(web.search('Example',free_only=True)[0]['url'],'https://example.org/issue')
            self.assertTrue(read.call_args.args[0].startswith('https://html.duckduckgo.com/'))
            key.assert_not_called()
        with app.db() as con:self.assertEqual(con.execute('SELECT blocked_until FROM web_state WHERE id=1').fetchone()[0],self.now+7200)

    def test_installed_free_hold_is_retained_with_exact_retry(self):
        self.options['provider']='free'
        with patch.object(web,'read') as read:
            with self.assertRaises(web.SearchBlocked) as caught:web.search('Example',free_only=True)
            self.assertEqual(caught.exception.retry_at,self.now+7200)
            self.assertEqual(caught.exception.provider,'free_web')
            read.assert_not_called()

    def test_shared_application_cap_remains_with_exact_rolling_release(self):
        with app.db() as con:con.executemany('INSERT INTO web_requests VALUES(?)',[(self.now-100,)]*100)
        self.assertEqual(web.free_status(),{'status':'daily_budget_wait','retry_at':self.now-100+86400})
        with patch.object(web,'read') as read:
            with self.assertRaises(web.SearchBlocked) as caught:web.search('Example',free_only=True)
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
        with patch.object(web,'read',return_value='anomaly.js'):
            with self.assertRaises(web.SearchBlocked) as caught:web.search('Example',free_only=True)
        self.assertEqual(caught.exception.retry_at,self.now+3600)
        with patch.object(web.time,'time',return_value=self.now+100),patch.object(web,'read') as read:
            with self.assertRaises(web.SearchBlocked) as again:web.search('Different',free_only=True)
            self.assertEqual(again.exception.retry_at,self.now+3600)
            read.assert_not_called()
        with patch.object(web.time,'time',return_value=self.now+3600):self.assertEqual(web.free_status()['status'],'available')

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
