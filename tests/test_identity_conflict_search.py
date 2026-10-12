"""Sergei 2026-10-12: a comic whose ComicVine issue disagrees with its embedded
series/number (identity_conflict) keeps searching every other source, including
saved leads and the Lens cover queue. The write gate is unchanged: the conflict
still blocks metadata-field plans, and other sources still verify on their own.

Isolated catalog; ComicVine, sources, leads and the local model are mocked.
"""
import json
import time
import unittest
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


class IdentityConflictSearchTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app,'DATA',self.root/'data'))
        self.enterContext(patch.object(app,'BASE',self.root))
        self.enterContext(patch.object(app,'live_root',return_value=str(self.root)))
        self.enterContext(patch.object(research,'CACHE',self.root/'evidence'))
        self.folder=self.root/'Example';self.folder.mkdir()
        self.path=self.folder/'Example 001 (2020).cbz';self.path.write_bytes(b'isolated fixture')
        stat=self.path.stat();self.signature=[stat.st_size,stat.st_mtime_ns]
        self.old={'Series':'Example','Number':'1','Year':'2020','Web':WEB,'Summary':'Existing synopsis.'}
        import discovery_state
        with app.db() as con:
            discovery_state.initialize(con);cover_tasks.table(con)
            con.execute('INSERT INTO comics(path,root,size,mtime,series,number,year,metadata,status,seen) VALUES(?,?,?,?,?,?,?,?,?,?)',
                        (str(self.path),str(self.folder),stat.st_size,stat.st_mtime_ns,'Example','1','2020',json.dumps(self.old),'embedded',1))

    def discover(self,leads=None,issue=CONFLICTING):
        import archive_conversion,worker,local_model,research_runtime,discovery_state,getcomics
        now=time.time()
        statuses={k:{'status':'human_verification','retry_at':now+5000} for k in scheduling.KEYS.values()}
        previous={'version':automatic.MATCHER_VERSION,'signature':self.signature,'retry_at':0,
                  'source_schedule':{name:{'result':'unavailable','next_at':now+5000} for name in scheduling.KEYS}}
        patches=[patch.object(app,'scan'),patch.object(archive_conversion,'one',return_value=False),
                 patch.object(discovery_state,'load',return_value={'checked':{str(self.path):previous}}),
                 patch.object(providers,'statuses',return_value=statuses),
                 patch.object(worker,'QUEUE',self.root/'queue'),
                 patch.object(worker.pause_control,'requested',return_value=False),
                 patch.object(research_runtime,'reuse',return_value=None),patch.object(research_runtime,'remember'),
                 patch.object(app,'api',side_effect=lambda path,**_:issue if path=='issue/4000-123' else {}),
                 patch.object(research,'publisher_lookup',return_value=None),
                 patch.object(research,'general_lookup',return_value=None),patch.object(research,'wiki_candidates',return_value=[]),
                 patch.object(getcomics,'lookup',return_value=None),
                 patch.object(local_model,'available',return_value=False)]
        with ExitStack() as stack:
            for item in patches:stack.enter_context(item)
            self.resolve=stack.enter_context(patch.object(research,'resolve_leads',return_value=leads))
            enqueue=stack.enter_context(patch.object(worker,'enqueue'))
            automatic.discover(self.folder,coverage_only=True)
        with app.db() as con:
            record=json.loads(con.execute('SELECT value FROM discovery_records WHERE path=?',(str(self.path),)).fetchone()[0])
            task=con.execute('SELECT state FROM cover_tasks WHERE path=?',(str(self.path),)).fetchone()
        return enqueue,record,task[0] if task else None

    def test_conflicting_comic_keeps_searching_and_joins_the_cover_queue(self):
        enqueue,record,task=self.discover()
        self.assertEqual(record['outcome'],'identity_conflict')
        self.resolve.assert_called_once()  # Saved web and Lens leads are checked (before: skipped).
        self.assertEqual(task,'pending')    # Lens cover search queued (before: never queued).
        enqueue.assert_not_called()

    VERIFIED={'provider':'Verified web research','fields':{'Series':'Example','Number':'1','Publisher':'Example Press'},
              'sources':[{'url':'https://catalog.example/example-1','text':'Example #1.'}],'status':'web_issue_found'}

    def test_write_gate_is_unchanged_for_a_conflict(self):
        enqueue,record,task=self.discover(leads=self.VERIFIED)
        self.assertEqual(record['outcome'],'identity_conflict')
        enqueue.assert_not_called()  # No metadata-field plan while ComicVine disagrees.

    def test_positive_control_the_same_lead_is_written_without_a_conflict(self):
        enqueue,record,task=self.discover(leads=self.VERIFIED,issue={})  # ComicVine returned nothing.
        self.assertEqual(record['outcome'],'queued')
        entry=json.loads(enqueue.call_args.args[0].read_text(encoding='utf-8'))['entries'][0]
        self.assertEqual(entry['fields']['Publisher'],'Example Press')

    def test_matching_comicvine_issue_still_skips_the_extra_search(self):
        # Positive control: the change is limited to conflicts.
        matching={'id':123,'volume':{'name':'Example','id':5},'issue_number':'1','description':'<p>Example.</p>'}
        enqueue,record,task=self.discover(issue=matching)
        self.assertNotEqual(record['outcome'],'identity_conflict')
        self.resolve.assert_not_called()
        self.assertIsNone(task)


if __name__=='__main__':
    unittest.main()
