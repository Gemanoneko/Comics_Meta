import json
import io
import threading
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
import app
import pause_control
import research
import research_runtime as runtime
import providers
from provider_wait import ProviderDeferred
from test_worker import scratch_directory


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app,'DATA',self.root/'data'))
        self.enterContext(patch.object(pause_control,'requested',return_value=False))
        with app.db():pass

    def test_two_sources_overlap_and_keep_priority_without_starting_more(self):
        barrier=threading.Barrier(2)
        callbacks=[]
        caller=threading.get_ident()
        def first(row,old):
            barrier.wait(timeout=3)
            time.sleep(.05)
            return {'provider':'first'}
        def second(row,old):
            barrier.wait(timeout=3)
            return {'provider':'second'}
        def unexpected(row,old):self.fail('Scheduled another source after verified match')
        result=runtime.first_verified([('first',first),('second',second),('third',unexpected)],{}, {},
            lambda name,result,error:callbacks.append((name,result,error,threading.get_ident())))
        self.assertEqual(result['provider'],'first')
        self.assertEqual(len(callbacks),2)
        self.assertTrue(all(c[3]==caller and c[2] is None for c in callbacks))

    def test_errors_do_not_stop_remaining_sources_and_concurrency_is_capped(self):
        lock=threading.Lock();active=0;peak=0;callbacks=[]
        def lookup(row,old):
            nonlocal active,peak
            with lock:active+=1;peak=max(peak,active)
            time.sleep(.01)
            with lock:active-=1
            raise ValueError('Lookup failed')
        result=runtime.first_verified([(str(i),lookup) for i in range(6)],{}, {},
            lambda n,r,e:callbacks.append(e),concurrency=10)
        self.assertIsNone(result)
        self.assertEqual(peak,2)
        self.assertEqual(len(callbacks),6)
        self.assertTrue(all(isinstance(e,ValueError) for e in callbacks))

    def test_pause_drains_running_sources_without_starting_more(self):
        paused=threading.Event();barrier=threading.Barrier(2);calls=[];completed=[]
        def lookup(row,old):
            calls.append(True)
            barrier.wait(timeout=3)
            paused.set()
            time.sleep(.02)
            return None
        with patch.object(pause_control,'requested',side_effect=paused.is_set):
            with self.assertRaises(pause_control.PauseRequested):
                runtime.first_verified([('a',lookup),('b',lookup),('c',lookup)],{}, {},
                    lambda n,r,e:completed.append(n))
        self.assertEqual(len(calls),2)
        self.assertCountEqual(completed,['a','b'])

    def test_stage_counts_success_failure_and_preserves_original_error(self):
        with runtime.stage('Example'):pass
        with self.assertRaisesRegex(ValueError,'original'):
            with runtime.stage('Example'):raise ValueError('original')
        metric=runtime.metrics()['stages'][0]
        self.assertEqual(metric['calls'],2)
        self.assertEqual(metric['errors'],1)
        self.assertGreaterEqual(metric['seconds'],0)
        with patch.object(app,'db',side_effect=OSError('disk')):
            with self.assertRaisesRegex(ValueError,'original'):
                with runtime.stage('Example'):raise ValueError('original')

    def make_comic(self,page=b'original',xml='<ComicInfo/>'):
        path=self.root/'Example 001 (2024).cbz'
        with zipfile.ZipFile(path,'w') as archive:
            archive.writestr('01.jpg',page)
            archive.writestr('ComicInfo.xml',xml)
        return path

    def test_verified_evidence_survives_metadata_write_but_not_page_or_identity_change(self):
        path=self.make_comic()
        row={'series':'Example','number':'1','year':'2024','path':str(path)}
        old={}
        result={'provider':'Verified source','fields':{'Title':'Beginning'},'sources':[{'url':'https://example.org/issue/1','text':'Evidence'}]}
        with patch.object(research,'save_evidence') as save:
            runtime.remember(path,row,old,result,9)
        saved=save.call_args.args[1]
        self.make_comic(xml='<ComicInfo><Summary>Reviewed synopsis</Summary></ComicInfo>')
        self.assertEqual(runtime.reuse(path,row,old,saved,9),result)
        self.assertEqual(runtime.reuse(path,row,{'Title':'Beginning'},saved,9),result)
        for changed in ({'Number':'2'},{'Year':'2023'},{'ISBN':'another'},{'Title':'Different'},{'Series':'Different'}):
            self.assertIsNone(runtime.reuse(path,row,changed,saved,9))
        self.assertIsNone(runtime.reuse(path,row,old,saved,10))
        expired=json.loads(json.dumps(saved));expired['verified_evidence']['verified_at']=time.time()-31*86400
        self.assertIsNone(runtime.reuse(path,row,old,expired,9))
        self.assertIsNone(runtime.reuse(path,row,old,result,9))
        self.make_comic(page=b'replacement')
        self.assertIsNone(runtime.reuse(path,row,old,saved,9))

    def test_unreadable_archive_does_not_stop_research_for_evidence_reuse(self):
        path=self.make_comic();row={'series':'Example','number':'1','year':'2024','path':str(path)}
        saved={'verified_evidence':{'identity':runtime.identity(row,{}),'version':9,'verified_at':time.time()}}
        path.write_bytes(b'not a ZIP')
        self.assertIsNone(runtime.reuse(path,row,{},saved,9))
        with patch.object(research,'save_evidence') as save:
            runtime.remember(path,row,{}, {'sources':[{'url':'https://example.org'}]},9)
            save.assert_not_called()

    def test_independent_provider_requests_overlap_and_reserve_separate_budgets(self):
        barrier=threading.Barrier(2)
        def open_response(*args,**kwargs):
            barrier.wait(timeout=3)
            return io.BytesIO(b'{"results":[]}')
        with patch.object(providers,'setting',return_value='synthetic'),patch.object(providers.urllib.request,'build_opener') as opener:
            opener.return_value.open.side_effect=open_response
            runtime.first_verified([(p,lambda r,o,p=p:providers.request(p,'/synthetic')) for p in ('gcd','google_books')],{}, {},lambda *args:None)
            self.assertEqual(opener.return_value.open.call_count,2)
        with app.db() as con:
            counts=dict(con.execute('SELECT provider,COUNT(*) FROM provider_requests GROUP BY provider'))
        self.assertEqual(counts,{'gcd':1,'google_books':1})

    def test_parallel_research_cannot_exceed_provider_budget_and_cache_stays_usable(self):
        with app.db() as con:
            con.execute('CREATE TABLE provider_requests(provider TEXT,timestamp REAL)')
            for name,limit in providers.BUDGETS.items():
                con.executemany('INSERT INTO provider_requests VALUES(?,?)',[(name,time.time())]*limit)
                key=name+':/cached:{}'
                con.execute('INSERT INTO cache VALUES(?,?,?)',(key,'{"cached":true}',time.time()))
        errors=[]
        with patch.object(providers,'setting',return_value='synthetic'),patch.object(providers.urllib.request,'build_opener') as opener:
            runtime.first_verified([(p,lambda r,o,p=p:providers.request(p,'/uncached')) for p in providers.BUDGETS],{}, {},lambda n,r,e:errors.append(e))
            self.assertEqual(len(errors),2)
            self.assertTrue(all(isinstance(e,ProviderDeferred) for e in errors))
            for name in providers.BUDGETS:self.assertEqual(providers.request(name,'/cached'),{'cached':True})
            opener.assert_not_called()
        with app.db() as con:
            self.assertEqual(dict(con.execute('SELECT provider,COUNT(*) FROM provider_requests GROUP BY provider')),providers.BUDGETS)

    def test_same_provider_parallel_requests_share_one_cached_network_response(self):
        with patch.object(providers,'setting',return_value='synthetic'),patch.object(providers.urllib.request,'build_opener') as opener:
            opener.return_value.open.return_value=io.BytesIO(b'{"results":[]}')
            runtime.first_verified([(str(i),lambda r,o:providers.request('gcd','/shared')) for i in range(2)],{}, {},lambda *args:None)
            self.assertEqual(opener.return_value.open.call_count,1)

    def test_paused_provider_requests_do_not_reach_network(self):
        import metron
        with patch.object(pause_control,'requested',return_value=True),patch.object(metron,'token',return_value='synthetic'),patch.object(providers.urllib.request,'build_opener') as opener:
            for provider in providers.BUDGETS:
                with self.assertRaises(pause_control.PauseRequested):providers.request(provider,'/paused')
            with self.assertRaises(pause_control.PauseRequested):metron.request('issue/')
            opener.assert_not_called()

    def test_throughput_counts_checks_and_distinct_verified_writes_in_observed_window(self):
        with patch.object(runtime.time,'time',return_value=100000):
            self.assertIsNone(runtime.throughput())
            runtime.record_check('current');runtime.record_check('queued')
        with app.db() as con:
            con.executemany('INSERT INTO history(path,backup,source,timestamp) VALUES(?,?,?,?)',
                [('same.cbz','','verified',100020),('same.cbz','','verified',100025),('old.cbz','','verified',90000)])
        with patch.object(runtime.time,'time',return_value=100060):
            report=runtime.throughput()
            self.assertEqual((report['checks'],report['queued'],report['writes'],report['updated_comics'],report['window_seconds']),(2,1,2,1,60))
        with patch.object(runtime.time,'time',return_value=101000):runtime.record_check('current')
        with patch.object(runtime.time,'time',return_value=104000):
            report=runtime.throughput()
            self.assertEqual((report['checks'],report['writes'],report['window_seconds']),(1,0,3600))
        with patch.object(runtime.time,'time',return_value=800000):runtime.record_check('current')
        with app.db() as con:self.assertEqual(con.execute('SELECT COUNT(*) FROM throughput_buckets').fetchone()[0],1)


if __name__=='__main__':unittest.main()
