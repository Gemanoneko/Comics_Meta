"""F17 (v0.1.2 review round 4): ComicVine's "Object Not Found" for the issue a
comic's Web field names is an answer about that comic, not an outage. It sets
no shared ComicVine pause, it is cached, and the comic keeps searching every
other source with strict verification and may be written from one. A saved
conflict still blocks field writes. A comic held by a genuine, transient
ComicVine pause says why, and is asked again when that pause ends.

The REAL app.api runs: its SQLite cache and not-found cache, cooldown, hourly
budget, 20 s request pacing and key lookup, with the REAL discovery_state,
row ordering, due logic, reuse/remember and cover_tasks. Only
urllib.request.urlopen is replaced, plus (as in the other identity-conflict
tests) the source lookups and the local model. A virtual clock lets the pacing
sleep and "five minutes later" pass without waiting: sleep() advances time().
Nothing touches the network or this checkout's data/.
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
import research
import research_runtime
from provider_wait import ProviderDeferred
from test_worker import scratch_directory

DEAD_WEB='https://comicvine.gamespot.com/dead-1/4000-999/'
GOOD_WEB='https://comicvine.gamespot.com/good-1/4000-123/'
NOT_FOUND={'status_code':101,'error':'Object Not Found','limit':0,'offset':0,'results':[]}
MATCHING={'id':123,'name':'The Good Begins','volume':{'name':'Good','id':5},'issue_number':'1','description':'<p>Good one.</p>'}
CONFLICTING={'id':999,'volume':{'name':'Another Series','id':6},'issue_number':'7','description':'<p>Another book.</p>'}
VOLUME={'id':5,'name':'Good','publisher':{'name':'Example Press'}}
DEAD_LEAD={'provider':'Verified web research','fields':{'Series':'Dead','Number':'1','Publisher':'Example Press'},
           'sources':[{'url':'https://catalog.example/dead-1','text':'Dead #1.'}],'status':'web_issue_found'}
GOOD_LEAD={'provider':'Verified web research','fields':{'Series':'Good','Number':'1','Publisher':'Example Press'},
           'sources':[{'url':'https://catalog.example/good-1','text':'Good #1.'}],'status':'web_issue_found'}
A='A Dead 001 (2020).cbz'
B='B Good 001 (2020).cbz'


def ok(results):
    return {'status_code':1,'error':'OK','results':results}


def http_error(code,body):
    return lambda url:urllib.error.HTTPError(url,code,'test',{},io.BytesIO(body))


class Clock:
    """Wall time plus an offset. sleep() advances the offset instead of waiting."""
    def __init__(self):
        self.real=time.time
        self.offset=0.0

    def time(self):
        return self.real()+self.offset

    def sleep(self,seconds):
        self.offset+=max(0,seconds)


class ComicVineWorld(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app,'DATA',self.root/'data'))
        self.enterContext(patch.object(app,'BASE',self.root))
        self.enterContext(patch.object(app,'live_root',return_value=str(self.root)))
        self.enterContext(patch.object(research,'CACHE',self.root/'evidence'))
        self.enterContext(patch.dict(os.environ,{'COMICVINE_API_KEY':'test-key'}))
        self.folder=self.root/'Lib';self.folder.mkdir()
        self.clock=Clock()
        self.enterContext(patch.object(time,'time',self.clock.time))
        self.enterContext(patch.object(time,'sleep',self.clock.sleep))
        self.answers={}
        self.requests=[]
        self.leads={}
        self.strict={}
        self.publisher_strict={}
        import discovery_state
        with app.db() as con:
            discovery_state.initialize(con);cover_tasks.table(con)

    def add(self,name,old):
        path=self.folder/name
        with zipfile.ZipFile(path,'w') as archive:  # Real pages: evidence reuse keys on them.
            archive.writestr('001.png',name.encode()+b' page one')
            archive.writestr('002.png',name.encode()+b' page two')
        stat=path.stat()
        with app.db() as con:
            con.execute('INSERT INTO comics(path,root,size,mtime,series,number,year,metadata,status,seen) VALUES(?,?,?,?,?,?,?,?,?,?)',
                        (str(path),str(self.folder),stat.st_size,stat.st_mtime_ns,old.get('Series'),old.get('Number'),old.get('Year'),json.dumps(old),'embedded',1))
        return path

    def dead_comic(self):
        return self.add(A,{'Series':'Dead','Number':'1','Year':'2020','Summary':'Existing synopsis.','Web':DEAD_WEB})

    def good_comic(self):
        with app.db() as con:  # The volume is cached: one ComicVine request per good comic.
            con.execute('INSERT OR REPLACE INTO cache VALUES(?,?,?)',('volume/4050-5?format=json',json.dumps(VOLUME),time.time()))
        self.answers['issue/4000-123']=ok(MATCHING)
        return self.add(B,{'Series':'Good','Number':'1','Year':'2020','Summary':'Existing synopsis.','Web':GOOD_WEB})

    def urlopen(self,request,timeout=None):
        resource=urllib.parse.urlparse(request.full_url).path.removeprefix('/api/').strip('/')
        self.requests.append(resource)
        answer=self.answers[resource]
        if callable(answer):
            raise answer(request.full_url)
        return io.BytesIO(json.dumps(answer).encode())

    def resolve(self,row,old,hint=None,strict=False):
        name=Path(row['path']).name
        self.strict.setdefault(name,[]).append(strict)
        return self.leads.get(name)

    def publisher(self,row,old,strict=False):
        self.publisher_strict.setdefault(Path(row['path']).name,[]).append(strict)
        return None

    def passes(self):
        """Discovery passes over the folder until it is done; returns the queued plans."""
        import archive_conversion,worker,local_model,getcomics
        plans=[]
        def enqueue(target):
            entry=json.loads(Path(target).read_text(encoding='utf-8'))['entries'][0]
            plans.append((Path(entry['path']).name,sorted(k for k in entry['fields'] if k!='Notes')))
        patches=[patch.object(app,'scan'),patch.object(archive_conversion,'one',return_value=False),
                 patch.object(worker,'QUEUE',self.root/'queue'),
                 patch.object(worker,'enqueue',side_effect=enqueue),
                 patch.object(worker.pause_control,'requested',return_value=False),
                 patch.object(urllib.request,'urlopen',side_effect=self.urlopen),
                 patch.object(research_runtime,'first_verified',return_value=None),
                 patch.object(research,'publisher_lookup',side_effect=self.publisher),
                 patch.object(research,'general_lookup',return_value=None),
                 patch.object(research,'wiki_candidates',return_value=[]),
                 patch.object(research,'resolve_leads',side_effect=self.resolve),
                 patch.object(getcomics,'lookup',return_value=None),
                 patch.object(local_model,'available',return_value=False)]
        with ExitStack() as stack:
            for item in patches:stack.enter_context(item)
            for _ in range(5):  # A queued write ends a pass; run the folder to completion.
                if not automatic.discover(self.folder,coverage_only=True):break
        return plans

    def record(self,name):
        with app.db() as con:
            row=con.execute('SELECT value FROM discovery_records WHERE path=?',(str(self.folder/name),)).fetchone()
        return json.loads(row[0]) if row else {}

    def paused_until(self):
        with app.db() as con:
            return con.execute('SELECT blocked_until FROM api_state WHERE id=1').fetchone()[0]


class DeadWebIdDiscoveryTests(ComicVineWorld):
    def test_dead_id_sets_no_pause_and_writes_from_a_strict_source(self):
        self.dead_comic()
        self.answers['issue/4000-999']=NOT_FOUND
        self.leads[A]=DEAD_LEAD
        plans=self.passes()
        self.assertEqual(self.requests,['issue/4000-999'])
        self.assertLessEqual(self.paused_until(),time.time())  # Before: a 5-minute ComicVine pause for everyone.
        self.assertEqual(self.strict[A],[True])
        self.assertEqual(self.publisher_strict[A],[True])
        self.assertEqual(plans,[(A,['Publisher'])])  # Before: held, no plan, every day.
        record=self.record(A)
        self.assertEqual(record['outcome'],'queued')
        self.assertIn('ComicVine issue 999',record['detail'])
        self.assertIn('does not exist',record['detail'])
        self.assertNotIn('comicvine',record['provider_waits'])

    def test_valid_comic_after_a_dead_id_gets_its_request_and_writes(self):
        self.dead_comic()
        self.good_comic()
        self.answers['issue/4000-999']=NOT_FOUND
        plans=self.passes()
        self.assertEqual(self.requests,['issue/4000-999','issue/4000-123'])  # Before: B's request never made.
        self.assertEqual(plans,[(B,['Publisher','Title'])])
        self.assertEqual(self.record(B)['outcome'],'queued')
        self.assertEqual(self.record(A)['outcome'],'needs_identity_lookup')  # No source verified A.
        self.assertGreater(self.record(A)['retry_at'],time.time()+23*3600)  # Daily, as any unidentified comic.

    def test_dead_id_answer_is_cached(self):
        self.dead_comic()
        self.answers['issue/4000-999']=NOT_FOUND
        self.passes()
        self.clock.offset+=86400+60  # The next day's pass.
        self.requests.clear()
        self.passes()
        self.assertEqual(self.requests,[])
        self.assertIn('does not exist',self.record(A)['detail'])

    def test_reused_evidence_is_not_written_for_a_dead_id_without_strict_verification(self):
        path=self.dead_comic()
        self.answers['issue/4000-999']=NOT_FOUND
        with app.db() as con:
            row=dict(con.execute('SELECT * FROM comics WHERE path=?',(str(path),)).fetchone())
        # Evidence remembered while the comic had no checked Web id, not verified strictly.
        research_runtime.remember(path,row,json.loads(row['metadata']),DEAD_LEAD,automatic.MATCHER_VERSION)
        plans=self.passes()  # The lead does not pass strict verification this time.
        self.assertEqual(plans,[])
        self.assertEqual(self.strict.get(A),[True])  # Searched again, strictly (before: never searched).
        self.assertEqual(self.record(A)['outcome'],'needs_identity_lookup')

    def test_saved_conflict_still_blocks_when_the_web_id_is_now_dead(self):
        self.dead_comic()
        self.answers['issue/4000-999']=ok(CONFLICTING)
        self.leads[A]=DEAD_LEAD
        self.assertEqual(self.passes(),[])
        self.assertEqual(self.record(A)['outcome'],'identity_conflict')
        self.clock.offset+=86400+60
        with app.db() as con:
            self.assertEqual(con.execute("UPDATE cache SET fetched=fetched-31*86400 WHERE key LIKE 'issue/%'").rowcount,1)
        self.answers['issue/4000-999']=NOT_FOUND
        self.requests.clear()
        plans=self.passes()
        self.assertEqual(self.requests,['issue/4000-999'])
        self.assertEqual(plans,[])  # The saved conflict still blocks field writes.
        record=self.record(A)
        self.assertEqual(record['outcome'],'identity_conflict')
        self.assertEqual(record['conflict_issue']['id'],'999')
        self.assertLessEqual(self.paused_until(),time.time())  # Before: a ComicVine pause.
        self.assertIn('conflict saved on an earlier pass',record['detail'])

    def test_outage_still_holds_and_says_why(self):
        self.good_comic()
        self.answers['issue/4000-123']=lambda url:urllib.error.URLError('test: unreachable')
        self.leads[B]=GOOD_LEAD
        plans=self.passes()
        self.assertEqual(self.requests,['issue/4000-123'])
        self.assertEqual(plans,[])  # Held: no field write while ComicVine cannot answer.
        self.assertEqual(self.strict[B],[True])
        self.assertGreater(self.paused_until(),time.time())  # A genuine outage still pauses ComicVine.
        record=self.record(B)
        self.assertEqual(record['outcome'],'needs_identity_lookup')
        self.assertLessEqual(record['retry_at'],time.time()+3600+60)  # When the outage wait ends (before: 24 h).
        self.assertIn('Field writes held',record.get('detail',''))  # Before: no reason anywhere on the record.
        self.assertIn('Cannot reach the metadata service',record.get('detail',''))

    def test_comic_held_by_a_transient_pause_is_asked_again_when_it_ends(self):
        self.add(A,{'Series':'Dead','Number':'1','Year':'2020','Summary':'Existing synopsis.','Web':DEAD_WEB})
        self.answers['issue/4000-999']=http_error(503,b'<html>Service Unavailable</html>')  # A genuine outage on A.
        self.good_comic()
        self.leads[B]=GOOD_LEAD
        self.assertEqual(self.passes(),[])
        self.assertEqual(self.requests,['issue/4000-999'])  # B is deferred by the pause A started.
        held=self.record(B)
        self.assertEqual(held['outcome'],'needs_identity_lookup')
        self.assertLessEqual(held['retry_at'],time.time()+300+60)  # About five minutes (before: 24 h).
        self.assertGreaterEqual(held['retry_at'],self.paused_until())  # Not before the pause ends.
        self.clock.offset+=360
        self.requests.clear()
        plans=self.passes()
        self.assertEqual(self.requests,['issue/4000-123'])  # A's own retry is an hour away.
        self.assertEqual(plans,[(B,['Publisher','Title'])])
        self.assertIn('cooling down',held.get('detail',''))  # The held pass said why.

    def test_missing_key_hold_says_why_and_keeps_the_daily_retry(self):
        self.good_comic()
        with patch.dict(os.environ,{'COMICVINE_API_KEY':''}):
            self.assertEqual(app.api_key(),'')  # Precondition: no key from the environment or any .env file.
            self.assertEqual(self.passes(),[])
        self.assertEqual(self.requests,[])
        record=self.record(B)
        self.assertEqual(record['outcome'],'needs_identity_lookup')
        self.assertIn('Set COMICVINE_API_KEY',record.get('detail',''))  # Before: no reason on the record.
        self.assertGreater(record['retry_at'],time.time()+23*3600)  # No known end, so no early retry loop.

    def test_positive_control_a_valid_comic_alone_writes(self):
        self.good_comic()
        plans=self.passes()
        self.assertEqual(self.requests,['issue/4000-123'])
        self.assertEqual(plans,[(B,['Publisher','Title'])])
        self.assertNotIn('detail',self.record(B))


class ComicVineNotFoundApiTests(ComicVineWorld):
    def call(self,resource='issue/4000-999'):
        with patch.object(urllib.request,'urlopen',side_effect=self.urlopen):
            return app.api(resource)

    def status(self):
        return json.loads((app.DATA/'comicvine-status.json').read_text(encoding='utf-8'))['status']

    def test_status_101_is_a_cached_answer_without_a_pause(self):
        self.answers['issue/4000-999']=NOT_FOUND
        with self.assertRaisesRegex(app.ComicVineNotFound,'does not exist'):self.call()
        self.assertLessEqual(self.paused_until(),time.time())  # Before: cooldown(300).
        self.assertEqual(self.status(),'available')  # Before: 'access_rejected' on the dashboard.
        with self.assertRaises(app.ComicVineNotFound):self.call()
        self.assertEqual(self.requests,['issue/4000-999'])  # The second answer came from the cache.
        self.clock.offset+=app.NOT_FOUND_SECONDS+60
        with self.assertRaises(app.ComicVineNotFound):self.call()
        self.assertEqual(self.requests,['issue/4000-999']*2)  # Asked again once the cached answer expires.

    def test_http_404_marked_object_not_found_is_the_same_answer(self):
        self.answers['issue/4000-999']=http_error(404,json.dumps(NOT_FOUND).encode())
        with self.assertRaises(app.ComicVineNotFound):self.call()
        self.assertLessEqual(self.paused_until(),time.time())

    def test_positive_control_other_failures_still_pause_comicvine(self):
        cases={'issue/4000-1':http_error(404,b'<html>Not Found</html>'),
               'issue/4000-2':{'status_code':100,'error':'Invalid API Key','results':[]},
               'issue/4000-3':http_error(503,b'')}
        for resource,answer in cases.items():
            with self.subTest(resource=resource):
                with app.db() as con:con.execute('UPDATE api_state SET blocked_until=0,last_attempt=0 WHERE id=1')
                self.answers[resource]=answer
                with self.assertRaises(ProviderDeferred):self.call(resource)
                self.assertGreater(self.paused_until(),time.time())
                with app.db() as con:
                    self.assertIsNone(con.execute('SELECT 1 FROM cache WHERE key LIKE ?',('%'+resource+'%',)).fetchone())


if __name__=='__main__':
    unittest.main()
