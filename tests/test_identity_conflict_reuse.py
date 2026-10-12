"""F10 (v0.1.2 review): an identity_conflict must keep blocking metadata-field
plans on the NEXT pass, when the first pass remembered verified evidence.

Two real discovery passes with the real research_runtime.remember/reuse on a
real CBZ, in an isolated catalog. ComicVine, sources, leads and the local model
are mocked; nothing touches the network or this checkout's data/.
"""
import json
import time
import unittest
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
from test_worker import scratch_directory

WEB='https://comicvine.gamespot.com/example-1/4000-123/'
CONFLICTING={'id':123,'volume':{'name':'Another Series','id':5},'issue_number':'7','description':'<p>Another book entirely.</p>'}
MATCHING={'id':123,'volume':{'name':'Example','id':5},'issue_number':'1','description':'<p>Example issue one.</p>'}
VERIFIED={'provider':'Verified web research','fields':{'Series':'Example','Number':'1','Publisher':'Example Press'},
          'sources':[{'url':'https://catalog.example/example-1','text':'Example #1.'}],'status':'web_issue_found'}


class IdentityConflictReuseTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app,'DATA',self.root/'data'))
        self.enterContext(patch.object(app,'BASE',self.root))
        self.enterContext(patch.object(app,'live_root',return_value=str(self.root)))
        self.enterContext(patch.object(research,'CACHE',self.root/'evidence'))
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

    def discover(self,leads,issues):
        """One discovery pass; `issues` maps a ComicVine issue resource to its response.

        Returns (outcome, planned fields or None, ComicVine issue requests, lead lookups).
        """
        import archive_conversion,worker,local_model,discovery_state,getcomics
        now=time.time()
        statuses={k:{'status':'human_verification','retry_at':now+5000} for k in scheduling.KEYS.values()}
        previous={'version':automatic.MATCHER_VERSION,'signature':self.signature,'retry_at':0,
                  'source_schedule':{name:{'result':'unavailable','next_at':now+5000} for name in scheduling.KEYS}}
        calls=[]
        def api(resource,**_):
            calls.append(resource)
            return issues.get(resource,{})
        patches=[patch.object(app,'scan'),patch.object(archive_conversion,'one',return_value=False),
                 patch.object(discovery_state,'load',return_value={'checked':{str(self.path):previous}}),
                 patch.object(providers,'statuses',return_value=statuses),
                 patch.object(worker,'QUEUE',self.root/'queue'),
                 patch.object(worker.pause_control,'requested',return_value=False),
                 patch.object(app,'api',side_effect=api),
                 patch.object(research,'publisher_lookup',return_value=None),
                 patch.object(research,'general_lookup',return_value=None),patch.object(research,'wiki_candidates',return_value=[]),
                 patch.object(getcomics,'lookup',return_value=None),
                 patch.object(local_model,'available',return_value=False)]
        with ExitStack() as stack:
            for item in patches:stack.enter_context(item)
            resolve=stack.enter_context(patch.object(research,'resolve_leads',return_value=leads))
            enqueue=stack.enter_context(patch.object(worker,'enqueue'))
            automatic.discover(self.folder,coverage_only=True)
        with app.db() as con:
            record=json.loads(con.execute('SELECT value FROM discovery_records WHERE path=?',(str(self.path),)).fetchone()[0])
        fields=json.loads(Path(enqueue.call_args.args[0]).read_text(encoding='utf-8'))['entries'][0]['fields'] if enqueue.called else None
        return record['outcome'],fields,[c for c in calls if c.startswith('issue/')],resolve.call_count

    def remembered(self):
        return research.read_evidence(self.path).get('verified_evidence',{})

    def test_conflict_still_blocks_field_writes_on_the_next_pass(self):
        issues={'issue/4000-123':CONFLICTING}
        outcome,fields,_,_=self.discover(leads=VERIFIED,issues=issues)
        self.assertEqual(outcome,'identity_conflict')
        self.assertIsNone(fields)
        self.assertEqual(self.remembered()['result']['provider'],'Verified web research')  # Pass 1 saved reusable evidence.
        outcome,fields,issue_calls,lead_lookups=self.discover(leads=None,issues=issues)
        self.assertEqual(lead_lookups,0)  # Pass 2 really reused the saved evidence.
        self.assertEqual(outcome,'identity_conflict')
        self.assertIsNone(fields)  # Before the fix: queued {'Publisher': 'Example Press'}.
        self.assertEqual(issue_calls,['issue/4000-123'])  # Re-checked; served from the 30-day API cache in production.

    def test_positive_control_reused_evidence_still_writes_without_a_conflict(self):
        # ComicVine returned nothing: no conflict, so the reused lead may still fill empty fields.
        outcome,fields,_,_=self.discover(leads=VERIFIED,issues={})
        self.assertEqual(outcome,'queued')
        outcome,fields,_,lead_lookups=self.discover(leads=None,issues={})
        self.assertEqual(lead_lookups,0)
        self.assertEqual(outcome,'queued')
        self.assertEqual(fields['Publisher'],'Example Press')

    def test_saved_matching_issue_is_reused_without_asking_comicvine_again(self):
        issues={'issue/4000-123':MATCHING}
        outcome,_,issue_calls,_=self.discover(leads=None,issues=issues)
        self.assertNotEqual(outcome,'identity_conflict')
        self.assertEqual(issue_calls,['issue/4000-123'])
        self.assertEqual(self.remembered()['issue']['id'],123)
        outcome,_,issue_calls,_=self.discover(leads=None,issues=issues)
        self.assertNotEqual(outcome,'identity_conflict')
        self.assertEqual(issue_calls,[])  # The verified issue saved with the evidence is enough.

    def test_saved_issue_is_not_reused_once_web_names_another_issue(self):
        self.discover(leads=None,issues={'issue/4000-123':MATCHING})
        self.assertEqual(self.remembered()['issue']['id'],123)
        # Web now names a different ComicVine issue, one that disagrees with the embedded identity.
        with app.db() as con:
            con.execute('UPDATE comics SET metadata=? WHERE path=?',
                        (json.dumps(dict(self.old,Web='https://comicvine.gamespot.com/another-7/4000-456/')),str(self.path)))
        outcome,fields,issue_calls,_=self.discover(leads=None,issues={'issue/4000-456':dict(CONFLICTING,id=456)})
        self.assertEqual(issue_calls,['issue/4000-456'])
        self.assertEqual(outcome,'identity_conflict')
        self.assertIsNone(fields)


if __name__=='__main__':
    unittest.main()
