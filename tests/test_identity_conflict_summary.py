"""F12 (v0.1.2 review): while an identity_conflict stands, the only write is an
empty Summary, and its source must pass the same named-creator and agreeing-
cover checks as any other lead: the hinted-publisher route is closed. The
Summary-only plan leaves the comic counted as unresolved.

Isolated catalog; ComicVine, sources, leads, covers and the local model are mocked.
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
import getcomics
import providers
import research
import source_scheduling as scheduling
import web_search
from test_worker import scratch_directory

WEB='https://comicvine.gamespot.com/example-1/4000-123/'
CONFLICTING={'id':123,'volume':{'name':'Another Series','id':5},'issue_number':'7','description':'<p>Another book entirely.</p>'}
ROW={'path':'Example 001 (2020).cbz','series':'Example','number':'1','year':'2020'}
OLD={'Series':'Example','Number':'1','Year':'2020','Publisher':'Example Press','Writer':'Jane Writer'}


def page(text):
    return {'url':'https://shop.example/example-1','title':'Example #1','headings':[],'text':text,'image':'/cover.jpg'}


class StrictVerificationTests(unittest.TestCase):
    HINTED=page('Example #1 (2020) from Example Press.')  # Publisher and year only: no creator.
    CREDITED=page('Example #1 (2020) from Example Press. Written by Jane Writer.')

    def test_positive_control_hinted_route_verifies_without_creator_or_cover(self):
        with patch.object(research,'cover_agrees') as cover:
            self.assertIsNotNone(research.verify_web_source(ROW,OLD,self.HINTED))
        cover.assert_not_called()

    def test_strict_closes_the_hinted_route(self):
        with patch.object(research,'cover_agrees',return_value=True):
            self.assertIsNone(research.verify_web_source(ROW,OLD,self.HINTED,strict=True))  # No named creator.

    def test_strict_needs_an_agreeing_cover(self):
        with patch.object(research,'cover_agrees',return_value=False):
            self.assertIsNone(research.verify_web_source(ROW,OLD,self.CREDITED,strict=True))

    def test_strict_verifies_with_named_creator_and_agreeing_cover(self):
        with patch.object(research,'cover_agrees',return_value=True):
            verified=research.verify_web_source(ROW,OLD,self.CREDITED,strict=True)
        self.assertIn('named creator',verified['sources'][0]['scope'])
        self.assertIn('cover agrees',verified['sources'][0]['scope'])


class GetComicsBookRouteTests(unittest.TestCase):
    ROW={'path':'Example TPB (2020).cbz','series':'Example','number':'','year':'2020'}
    OLD={'Series':'Example','Title':'Example','Publisher':'Example Press','Year':'2020'}
    LINKS='<a href="/other-comics/example-tpb-2020/">Example (2020)</a>'
    SOURCE={'url':'https://getcomics.org/other-comics/example-tpb-2020/','title':'Example (2020)','headings':['Example (2020)'],
            'text':'Example (2020) from Example Press.','identity_text':'Example (2020) from Example Press.'}

    def lookup(self,**kwargs):
        with scratch_directory() as folder,patch.object(app,'DATA',Path(folder)), \
             patch.object(web_search,'read',return_value=self.LINKS),patch.object(web_search,'source',return_value=self.SOURCE):
            return getcomics.lookup(self.ROW,self.OLD,**kwargs)

    def test_positive_control_book_only_route_supplies_synopsis_evidence(self):
        self.assertEqual(self.lookup()['provider'],'GetComics')

    def test_book_only_route_is_closed_during_a_conflict(self):
        self.assertIsNone(self.lookup(strict=True))


class ConflictSummaryDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app,'DATA',self.root/'data'))
        self.enterContext(patch.object(app,'BASE',self.root))
        self.enterContext(patch.object(app,'live_root',return_value=str(self.root)))
        self.enterContext(patch.object(research,'CACHE',self.root/'evidence'))
        self.folder=self.root/'Example';self.folder.mkdir()
        self.path=self.folder/'Example 001 (2020).cbz'
        with zipfile.ZipFile(self.path,'w') as archive:
            archive.writestr('001.png',b'synthetic page one')
            archive.writestr('002.png',b'synthetic page two')
        stat=self.path.stat();self.signature=[stat.st_size,stat.st_mtime_ns]
        self.old={'Series':'Example','Number':'1','Year':'2020','Web':WEB,'Summary':''}
        # v0.1.3 switches GetComics, general web and wiki off by default; their code is kept,
        # so the strict routes are checked with every source switched back on.
        (self.root/'config.json').write_text(json.dumps({'sources':{'disabled':[]}}),encoding='utf-8')
        import discovery_state
        with app.db() as con:
            discovery_state.initialize(con);cover_tasks.table(con)
            con.execute('INSERT INTO comics(path,root,size,mtime,series,number,year,metadata,status,seen) VALUES(?,?,?,?,?,?,?,?,?,?)',
                        (str(self.path),str(self.folder),stat.st_size,stat.st_mtime_ns,'Example','1','2020',json.dumps(self.old),'embedded',1))

    WEB_RESULT={'provider':'Verified web research','fields':{'Series':'Example','Number':'1','Publisher':'Example Press'},'status':'web_issue_found',
                'sources':[{'url':'https://shop.example/example-1','text':' '.join(['Example issue one introduces its hero.']*5)}]}

    def discover(self,issue,web_result=None):
        """GetComics, saved leads, general web and wiki are open; every other source waits."""
        import archive_conversion,worker,local_model,discovery_state
        now=time.time()
        statuses={k:{'status':'human_verification','retry_at':now+5000} for k in scheduling.KEYS.values()}
        statuses['getcomics']={'status':'available','retry_at':0}
        waiting=set(scheduling.KEYS)-{'GetComics','General free web','Wikipedia/wiki'}
        previous={'version':automatic.MATCHER_VERSION,'signature':self.signature,'retry_at':0,
                  'source_schedule':{name:{'result':'unavailable','next_at':now+5000} for name in waiting}}
        proposal={'summary':'A teaser.','model':'m','sources':['https://shop.example/example-1']}
        patches=[patch.object(app,'scan'),patch.object(archive_conversion,'one',return_value=False),
                 patch.object(discovery_state,'load',return_value={'checked':{str(self.path):previous}}),
                 patch.object(providers,'statuses',return_value=statuses),
                 patch.object(worker,'QUEUE',self.root/'queue'),
                 patch.object(worker.pause_control,'requested',return_value=False),
                 patch.object(app,'api',side_effect=lambda resource,**_:issue if resource=='issue/4000-123' else {}),
                 patch.object(research,'publisher_lookup',return_value=None),
                 patch.object(research,'wiki_candidates',return_value=[{'title':'Example','pageid':1}]),
                 patch.object(local_model,'available',return_value=True),
                 patch.object(local_model,'identify_cover',return_value=None),
                 patch.object(local_model,'sourced_synopsis',return_value=proposal)]
        with ExitStack() as stack:
            for item in patches:stack.enter_context(item)
            self.getcomics=stack.enter_context(patch.object(getcomics,'lookup',return_value=None))
            self.leads=stack.enter_context(patch.object(research,'resolve_leads',return_value=None))
            self.general=stack.enter_context(patch.object(research,'general_lookup',return_value=web_result))
            enqueue=stack.enter_context(patch.object(worker,'enqueue'))
            automatic.discover(self.folder,coverage_only=True)
        with app.db() as con:
            record=json.loads(con.execute('SELECT value FROM discovery_records WHERE path=?',(str(self.path),)).fetchone()[0])
        fields=json.loads(Path(enqueue.call_args.args[0]).read_text(encoding='utf-8'))['entries'][0]['fields'] if enqueue.called else None
        return record['outcome'],fields

    def strict_flags(self):
        calls=[self.getcomics.call_args,self.general.call_args,*self.leads.call_args_list]
        self.assertTrue(all(calls),'every verifier route was searched')
        return {call.kwargs.get('strict',False) for call in calls}

    def test_every_web_verifier_route_is_strict_during_a_conflict(self):
        self.discover(issue=CONFLICTING)
        self.assertEqual(self.leads.call_count,2)  # Saved leads, then wiki leads.
        self.assertEqual(self.strict_flags(),{True})

    def without_web(self):
        """No ComicVine issue in Web, so nothing to conflict with."""
        with app.db() as con:
            con.execute('UPDATE comics SET metadata=? WHERE path=?',
                        (json.dumps({k:v for k,v in self.old.items() if k!='Web'}),str(self.path)))

    def test_positive_control_routes_are_not_strict_without_a_conflict(self):
        self.without_web()
        self.discover(issue={})
        self.assertEqual(self.strict_flags(),{False})

    def test_summary_only_plan_keeps_the_conflict_unresolved(self):
        outcome,fields=self.discover(issue=CONFLICTING,web_result=self.WEB_RESULT)
        self.assertEqual(set(fields),{'Summary','Notes'})  # No metadata fields while the conflict stands.
        self.assertEqual(outcome,'identity_conflict')        # Before: 'queued', hidden from the unresolved count.

    def test_positive_control_the_same_source_is_queued_without_a_conflict(self):
        self.without_web()
        outcome,fields=self.discover(issue={},web_result=self.WEB_RESULT)
        self.assertEqual(outcome,'queued')
        self.assertEqual(fields['Publisher'],'Example Press')


if __name__=='__main__':
    unittest.main()
