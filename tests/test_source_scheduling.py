import unittest
from pathlib import Path
from unittest.mock import patch
import json
import app,scheduler,source_scheduling as scheduling,research_runtime as runtime
from provider_wait import ProviderDeferred
from test_worker import scratch_directory


class SchedulingTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app,'DATA',self.root/'data'))
        with app.db():pass

    def test_no_new_data_does_not_stop_a_richer_verified_source(self):
        old={'Series':'Example','Number':'1'}
        thin={'fields':{'Series':'Example','Number':'1'},'sources':[]}
        rich={'fields':{'Writer':'Verified writer'},'sources':[]}
        result=runtime.first_verified([('thin',lambda r,o:thin),('rich',lambda r,o:rich)],{},old,lambda *args:None,
                                      concurrency=1,accept=lambda result:scheduling.useful(result,old))
        self.assertEqual(result,rich)
        self.assertFalse(scheduling.useful({'sources':[{'text':'Too short'}]},old))
        self.assertTrue(scheduling.useful({'sources':[{'text':'word '*25}]},old))
        self.assertFalse(scheduling.useful({'sources':[{'text':'word '*25}]},dict(old,Summary='Already present')))

    def test_source_misses_back_off_with_a_seven_day_cap(self):
        previous={}
        for expected in (86400,172800,345600,604800,604800):
            previous=scheduling.record(previous,None,None,{},100)
            self.assertEqual(previous['next_at'],100+expected)
        self.assertFalse(scheduling.ready('Metron',previous,{},101))
        self.assertTrue(scheduling.ready('Metron',previous,{},previous['next_at']))

    def test_provider_wait_does_not_become_a_comic_error_or_hourly_retry(self):
        attempt=scheduling.record({},None,ProviderDeferred('Unavailable','gcd',300),{},100)
        previous={'signature':[10,1],'version':9,'retry_at':10000,'source_schedule':{'GCD':attempt}}
        for status in ({'status':'human_verification'},{'status':'unavailable','retry_at':300},{'status':'unavailable','retry_at':0}):
            self.assertFalse(scheduling.due(previous,[10,1],9,{'gcd':status},now=500))
        self.assertTrue(scheduling.due(previous,[10,1],9,{'gcd':{'status':'available'}},now=200))
        self.assertTrue(scheduling.ready('GCD',attempt,{'gcd':{'status':'available'}},200))
        self.assertFalse(scheduling.ready('GCD',attempt,{'gcd':{'status':'human_verification'}},500))

    def test_changed_files_and_new_leads_bypass_previous_retry(self):
        previous={'signature':[10,1],'version':9,'retry_at':10000}
        self.assertFalse(scheduling.due(previous,[10,1],9,{},now=100))
        self.assertTrue(scheduling.due(previous,[11,2],9,{},now=100))
        self.assertTrue(scheduling.due(previous,[10,1],10,{},now=100))
        self.assertTrue(scheduling.due(previous,[10,1],9,{},new_leads=True,now=100))

    def test_first_source_attempt_preserves_access_to_existing_provider_caches(self):
        self.assertTrue(scheduling.ready('GCD',{}, {'gcd':{'status':'unavailable','retry_at':1000}},100))
        error=scheduling.record({},None,ValueError('Verification failed'),{},100)
        self.assertEqual(error['result'],'error')
        self.assertEqual(error['next_at'],3700)
        previous={'signature':[10,1],'version':9,'retry_at':10000,'source_schedule':{'GCD':error}}
        self.assertFalse(scheduling.due(previous,[10,1],9,{},now=3600))
        self.assertTrue(scheduling.due(previous,[10,1],9,{},now=3700))

    def test_isbn_and_publisher_sources_are_prioritized_without_dropping_fallbacks(self):
        sources=[(n,None) for n in ('Metron','GCD','Google Books','Open Library local index','Dark Horse')]
        ranked=scheduling.order(sources,{'path':'Example.cbz'},{'ISBN':'123'})
        self.assertEqual([x[0] for x in ranked[:2]],['Open Library local index','Google Books'])
        ranked=scheduling.order(sources,{'path':'Example.cbz'},{'Publisher':'Dark Horse Comics'})
        self.assertEqual(ranked[0][0],'Dark Horse')
        self.assertCountEqual([x[0] for x in ranked],[x[0] for x in sources])

    def test_large_folder_continuation_rotates_without_losing_checkpoint(self):
        a=self.root/'A';b=self.root/'B';a.mkdir();b.mkdir()
        (a/'one.cbz').touch();(b/'two.cbz').touch()
        with patch.object(scheduler,'STATE',self.root/'folders.json'):
            self.assertEqual(scheduler.select(self.root),str(a))
            scheduler.finish(a,queued=True)
            self.assertEqual(scheduler.select(self.root),str(b))
            scheduler.finish(b)
            self.assertEqual(scheduler.select(self.root),str(a))
            state=json.loads(scheduler.STATE.read_text())
            self.assertIn('last_pass',state['folders'][str(a)])

    def test_discovery_continues_past_thin_cached_evidence_and_queues_useful_fields(self):
        import automatic,research,worker,metron,providers,archive_conversion,cover_tasks,local_model
        folder=self.root/'comics';folder.mkdir();path=folder/'Example 001 (2024).cbz';path.write_bytes(b'fixture')
        with app.db() as con:
            con.execute('INSERT INTO comics(path,root,size,mtime,series,number,year,metadata,status,seen) VALUES(?,?,?,?,?,?,?,?,?,?)',
                (str(path),str(folder),7,1,'Example','1','2024',json.dumps({'Series':'Example','Number':'1'}),'embedded',1))
        thin={'fields':{'Series':'Example','Number':'1'},'sources':[]}
        rich={'provider':'GCD','fields':{'Writer':'Verified writer'},'sources':[{'url':'https://example.org','text':'word '*25}]}
        with patch.object(app,'BASE',self.root),patch.object(app,'scan'),patch.object(research,'CACHE',self.root/'research'),patch.object(research,'save_evidence'),patch.object(runtime,'reuse',return_value=thin),patch.object(automatic,'lookup_unidentified',return_value=None),patch.object(archive_conversion,'one',return_value=False),patch.object(providers,'statuses',return_value={}),patch.object(metron,'token',return_value='synthetic'),patch.object(metron,'lookup',return_value=thin),patch.object(providers,'gcd_lookup',return_value=rich),patch.object(worker,'enqueue') as enqueue,patch.object(cover_tasks,'identified'):
            for proposal in (None,{'summary':'Verified teaser','model':'fixture','sources':['https://example.org']}):
                enqueue.reset_mock()
                with patch.object(automatic.discovery_state,'load',return_value={'checked':{}}),patch.object(local_model,'available',return_value=True),patch.object(local_model,'sourced_synopsis',return_value=proposal) as synopsis:
                    self.assertTrue(automatic.discover(folder))
                synopsis.assert_called_once()
                self.assertEqual(enqueue.call_count,1)
                plan=json.loads(enqueue.call_args.args[0].read_text())
                self.assertEqual(plan['entries'][0]['fields']['Writer'],'Verified writer')
                self.assertEqual(plan['entries'][0]['fields'].get('Summary'),'Verified teaser' if proposal else None)
                self.assertEqual('Summary' in plan['entries'][0]['changes'],bool(proposal))


if __name__=='__main__':unittest.main()
