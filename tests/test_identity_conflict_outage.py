"""F16 (v0.1.2 review round 3): when Web names a ComicVine issue and ComicVine
cannot answer, the comic is not unidentified. A conflict saved on an earlier
pass still stands; otherwise every field write is held for that pass, while the
comic keeps searching strictly. app.api reads its cache before it needs the key.

The REAL app.api runs here: its 30-day SQLite cache, cooldown, hourly budget and
key lookup. Only urllib.request.urlopen is replaced. Real reuse/remember on a
real CBZ, in an isolated catalog; nothing touches the network or data/.
"""
import io
import json
import os
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
import app
import automatic
import cover_tasks
import providers
import research
import source_scheduling as scheduling
from provider_wait import ProviderDeferred
from test_worker import scratch_directory

WEB='https://comicvine.gamespot.com/example-1/4000-123/'
CONFLICTING={'id':123,'volume':{'name':'Another Series','id':5},'issue_number':'7','description':'<p>Another book entirely.</p>'}
MATCHING={'id':123,'name':'The Example Begins','volume':{'name':'Example','id':5},'issue_number':'1','description':'<p>Example issue one.</p>'}
VOLUME={'id':5,'name':'Example','publisher':{'name':'Example Press'}}
VERIFIED={'provider':'Verified web research','fields':{'Series':'Example','Number':'1','Publisher':'Example Press'},
          'sources':[{'url':'https://catalog.example/example-1','text':'Example #1.'}],'status':'web_issue_found'}


class IdentityConflictOutageTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app,'DATA',self.root/'data'))
        self.enterContext(patch.object(app,'BASE',self.root))
        self.enterContext(patch.object(app,'live_root',return_value=str(self.root)))
        self.enterContext(patch.object(research,'CACHE',self.root/'evidence'))
        self.enterContext(patch.dict(os.environ,{'COMICVINE_API_KEY':'test-key'}))
        self.folder=self.root/'Example';self.folder.mkdir()
        self.path=self.folder/'Example 001 (2020).cbz'
        # Real page entries: verified-evidence reuse keys on the archive's pages.
        with zipfile.ZipFile(self.path,'w') as archive:
            archive.writestr('001.png',b'synthetic page one')
            archive.writestr('002.png',b'synthetic page two')
        stat=self.path.stat();self.signature=[stat.st_size,stat.st_mtime_ns]
        self.old={'Series':'Example','Number':'1','Year':'2020','Web':WEB,'Summary':'Existing synopsis.'}
        import discovery_state
        with app.db() as con:
            discovery_state.initialize(con);cover_tasks.table(con)
            con.execute('INSERT INTO comics(path,root,size,mtime,series,number,year,metadata,status,seen) VALUES(?,?,?,?,?,?,?,?,?,?)',
                        (str(self.path),str(self.folder),stat.st_size,stat.st_mtime_ns,'Example','1','2020',json.dumps(self.old),'embedded',1))
        self.answers={'issue/4000-123':CONFLICTING}
        self.network_up=True
        self.requests=[]

    def urlopen(self,request,timeout=None):
        resource=urllib.parse.urlparse(request.full_url).path.removeprefix('/api/').strip('/')
        self.requests.append(resource)
        if not self.network_up:
            raise urllib.error.URLError('test: ComicVine unreachable')
        return io.BytesIO(json.dumps({'status_code':1,'results':self.answers[resource]}).encode())

    def record(self):
        with app.db() as con:
            row=con.execute('SELECT value FROM discovery_records WHERE path=?',(str(self.path),)).fetchone()
        return json.loads(row[0]) if row else {}

    def discover(self,leads=None,previous='saved'):
        """One discovery pass. `previous`: 'saved' is the record the last pass
        saved; 'legacy' is that record without a saved conflict, as written before
        this fix; 'none' is a first pass. Every other source waits.

        Returns (outcome, planned fields or None, record, strict flags given to leads).
        """
        import archive_conversion,worker,local_model,discovery_state,getcomics
        now=time.time()
        statuses={k:{'status':'human_verification','retry_at':now+5000} for k in scheduling.KEYS.values()}
        waiting={'retry_at':0,'source_schedule':{name:{'result':'unavailable','next_at':now+5000} for name in scheduling.KEYS}}
        record={} if previous=='none' else self.record()
        if previous=='legacy':record.pop('conflict_issue',None)
        record=dict(record or {'version':automatic.MATCHER_VERSION,'signature':self.signature},**waiting)
        with app.db() as con:  # No 20 s request pacing between test passes.
            con.execute('UPDATE api_state SET last_attempt=0 WHERE id=1')
        patches=[patch.object(app,'scan'),patch.object(archive_conversion,'one',return_value=False),
                 patch.object(discovery_state,'load',return_value={'checked':{str(self.path):record}}),
                 patch.object(providers,'statuses',return_value=statuses),
                 patch.object(worker,'QUEUE',self.root/'queue'),
                 patch.object(worker.pause_control,'requested',return_value=False),
                 patch.object(urllib.request,'urlopen',side_effect=self.urlopen),
                 patch.object(research,'general_lookup',return_value=None),patch.object(research,'wiki_candidates',return_value=[]),
                 patch.object(getcomics,'lookup',return_value=None),
                 patch.object(local_model,'available',return_value=False)]
        with ExitStack() as stack:
            for item in patches:stack.enter_context(item)
            resolve=stack.enter_context(patch.object(research,'resolve_leads',return_value=leads))
            self.publisher=stack.enter_context(patch.object(research,'publisher_lookup',return_value=None))
            enqueue=stack.enter_context(patch.object(worker,'enqueue'))
            automatic.discover(self.folder,coverage_only=True)
        fields=json.loads(Path(enqueue.call_args.args[0]).read_text(encoding='utf-8'))['entries'][0]['fields'] if enqueue.called else None
        saved=self.record()
        return saved['outcome'],fields,saved,[c.kwargs.get('strict',False) for c in resolve.call_args_list]

    def find_conflict(self):
        """Pass 1: ComicVine answers with the conflicting issue; a lead verifies and is remembered."""
        outcome,fields,_,_=self.discover(leads=VERIFIED,previous='none')
        self.assertEqual(outcome,'identity_conflict')
        self.assertIsNone(fields)
        self.assertEqual(research.read_evidence(self.path)['verified_evidence']['result']['provider'],'Verified web research')
        self.requests.clear()

    def expire_cache(self):
        with app.db() as con:
            self.assertEqual(con.execute('UPDATE cache SET fetched=fetched-31*86400').rowcount,1)

    def comicvine_wait(self,record):
        return record['provider_waits']['comicvine']['reason']

    def test_expired_cache_and_failed_request_hold_field_writes(self):
        self.find_conflict()
        self.expire_cache()
        self.network_up=False
        outcome,fields,record,_=self.discover(previous='legacy')
        self.assertEqual(self.requests,['issue/4000-123'])  # The real client tried the network.
        self.assertIn('Cannot reach',self.comicvine_wait(record))
        self.assertIsNone(fields)  # Before: queued {'Publisher': 'Example Press'} from the reused evidence.
        self.assertEqual(outcome,'needs_identity_lookup')
        self.assertEqual(research.read_evidence(self.path)['verified_evidence']['result']['provider'],'Verified web research')  # Kept.

    def test_cooldown_holds_field_writes_and_the_search_stays_strict(self):
        with app.db() as con:
            con.execute('UPDATE api_state SET blocked_until=? WHERE id=1',(time.time()+3600,))
        outcome,fields,record,strict=self.discover(leads=VERIFIED,previous='none')
        self.assertEqual(self.requests,[])
        self.assertIn('cooling down',self.comicvine_wait(record))
        self.assertIsNone(fields)  # Before: queued {'Publisher': 'Example Press'}.
        self.assertEqual(strict,[True])  # Still searched, strictly (before: [False]).
        self.assertTrue(self.publisher.call_args.kwargs['strict'])
        self.assertEqual(outcome,'needs_identity_lookup')

    def test_spent_hourly_budget_holds_field_writes(self):
        self.find_conflict()
        self.expire_cache()
        now=time.time()
        with app.db() as con:
            con.executemany('INSERT INTO api_requests VALUES(?)',[(now,)]*180)
        outcome,fields,record,_=self.discover(previous='legacy')
        self.assertEqual(self.requests,[])
        self.assertIn('hourly request budget',self.comicvine_wait(record))
        self.assertIsNone(fields)  # Before: queued {'Publisher': 'Example Press'}.
        self.assertEqual(outcome,'needs_identity_lookup')

    def test_missing_key_still_reads_a_fresh_cached_conflict(self):
        self.find_conflict()
        with patch.dict(os.environ,{'COMICVINE_API_KEY':''}):
            self.assertEqual(app.api_key(),'')  # Precondition: no key from the environment or any .env file.
            outcome,fields,_,_=self.discover(previous='legacy')
        self.assertEqual(self.requests,[])
        self.assertIsNone(fields)  # Before: queued {'Publisher': 'Example Press'}; the key check hid the cache.
        self.assertEqual(outcome,'identity_conflict')

    def test_api_reads_the_cache_before_it_needs_the_key(self):
        with app.db() as con:
            con.execute('INSERT INTO cache VALUES(?,?,?)',('issue/4000-123?format=json',json.dumps(CONFLICTING),time.time()))
        with patch.dict(os.environ,{'COMICVINE_API_KEY':''}),patch.object(urllib.request,'urlopen',side_effect=self.urlopen):
            self.assertEqual(app.api('issue/4000-123'),CONFLICTING)
            with self.assertRaisesRegex(ProviderDeferred,'Set COMICVINE_API_KEY'):app.api('issue/4000-456')
        self.assertEqual(self.requests,[])

    def test_saved_conflict_blocks_field_writes_without_comicvine(self):
        self.find_conflict()
        self.assertEqual(self.record()['conflict_issue']['id'],'123')  # Persisted with the record.
        self.expire_cache()
        self.network_up=False
        outcome,fields,record,_=self.discover(previous='saved')
        self.assertEqual(self.requests,['issue/4000-123'])
        self.assertIsNone(fields)
        self.assertEqual(outcome,'identity_conflict')  # Known offline, not merely held.
        self.assertEqual(record['conflict_issue']['id'],'123')  # Carried to the next pass.

    def test_held_comic_is_written_once_comicvine_answers(self):
        self.answers={'issue/4000-123':MATCHING}
        with app.db() as con:  # The volume is already cached; one request per pass.
            con.execute('INSERT INTO cache VALUES(?,?,?)',('volume/4050-5?format=json',json.dumps(VOLUME),time.time()))
        self.network_up=False
        outcome,fields,_,strict=self.discover(leads=VERIFIED,previous='none')
        self.assertIsNone(fields)  # Before: queued during the outage, from a non-strict lead.
        self.assertEqual(strict,[True])
        with app.db() as con:  # The failed request started a 5-minute cooldown; it has passed.
            con.execute('UPDATE api_state SET blocked_until=0 WHERE id=1')
        self.network_up=True
        outcome,fields,record,_=self.discover(previous='saved')
        self.assertEqual(outcome,'queued')
        self.assertEqual(fields['Publisher'],'Example Press')
        self.assertNotIn('conflict_issue',record)

    def test_positive_control_a_matching_comic_writes_when_comicvine_answers(self):
        self.answers={'issue/4000-123':MATCHING}
        with app.db() as con:
            con.execute('INSERT INTO cache VALUES(?,?,?)',('volume/4050-5?format=json',json.dumps(VOLUME),time.time()))
        outcome,fields,record,_=self.discover(previous='none')
        self.assertEqual(self.requests,['issue/4000-123'])
        self.assertEqual(outcome,'queued')
        self.assertEqual(fields['Publisher'],'Example Press')
        self.assertEqual(fields['Title'],'The Example Begins')
        self.assertNotIn('conflict_issue',record)


class CoffinShopStrictTests(unittest.TestCase):
    ROW={'path':'Coffin Example 001.cbz','series':'Coffin Example','number':'1','year':'2020'}
    OLD={'Series':'Coffin Example','Number':'1','Publisher':'Coffin Comics'}

    def lookup(self,**options):
        with scratch_directory() as d,patch.object(app,'DATA',Path(d)/'data'), \
             patch.object(research,'fetch',return_value={}) as fetch:
            result=research.publisher_lookup(self.ROW,self.OLD,**options)
        return result,fetch.call_count

    def test_strict_closes_the_title_only_shop_route(self):
        self.assertEqual(self.lookup(strict=True),(None,0))

    def test_positive_control_the_shop_is_searched_without_strict(self):
        self.assertEqual(self.lookup(),(None,1))


if __name__=='__main__':
    unittest.main()
