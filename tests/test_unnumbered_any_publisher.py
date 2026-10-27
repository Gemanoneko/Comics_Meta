"""Lens/web leads for any publisher and for unnumbered books.

Fixture scenario: "The Milkman Murders" 2012 one-shot. Its saved Lens leads
were rejected because the book has no issue number and its publisher is not
in the fixed hint list. Mocked pages and covers only; no public requests.
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
import web_search
from test_worker import scratch_directory

MILKMAN_PAGE={
    'url':'https://www.catalog.example/books/the-milkman-murders',
    'title':'The Milkman Murders HC :: Profile :: Example Catalog',
    'headings':['The Milkman Murders HC'],
    'text':'A suburban family is pushed to the edge when a stranger arrives.',
    'identity_text':'The Milkman Murders HC. Published 2012 by Dark Horse Books. Written by Joe Casey; art by Steve Parkhouse.',
    'image':'/covers/milkman.jpg'}


class UnnumberedAnyPublisherTests(unittest.TestCase):
    def setUp(self):
        # Evidence writes take the catalog lock; keep it out of the checkout's data/.
        self.enterContext(patch.object(app,'DATA',Path(self.enterContext(scratch_directory()))/'data'))
        self.row={'path':'Dark Horse/The Milkman Murders (2012).cbz','series':'The Milkman Murders','number':'','year':'2012'}
        self.old={'Writer':'Joe Casey','Penciller':'Steve Parkhouse'}
        self.read=self.enterContext(patch.object(web_search,'read',return_value=b'remote cover'))
        self.enterContext(patch('reverse_image.cover',return_value=(b'local cover','','')))
        self.agree=self.enterContext(patch('automatic.covers_agree',return_value=True))
        # The page names a hardcover; the local archive is book-length, not a single issue.
        self.pages=self.enterContext(patch.object(research,'archive_pages',return_value=120))

    def verify(self,row=None,old=None,page=None,hint=None,require_cover=True):
        return research.verify_web_source(row or self.row,self.old if old is None else old,page or MILKMAN_PAGE,hint,require_cover=require_cover)

    def test_filename_has_no_issue_number(self):
        self.assertEqual(app.parse_name('The Milkman Murders (2012).cbz'),('The Milkman Murders','','2012'))

    def test_one_shot_confirmed_by_title_creators_and_cover(self):
        result=self.verify()
        self.assertEqual(result['fields'],{'Series':'The Milkman Murders'})  # No empty Number or invented Publisher.
        self.assertIn('named creator',result['sources'][0]['scope'])
        self.assertIn('cover agrees',result['sources'][0]['scope'])

    def test_any_publisher_named_by_the_page_is_confirmed(self):
        result=self.verify(hint={'publisher':'Dark Horse Books','creators':[]})
        self.assertEqual(result['fields']['Publisher'],'Dark Horse Books')
        unnamed=self.verify(hint={'publisher':'Kitchen Sink Press','creators':[]})
        self.assertNotIn('Publisher',unnamed['fields'])

    def test_cover_credits_can_supply_the_creators(self):
        result=self.verify(old={},hint={'creators':['Story by Joe Casey','Art: Steve Parkhouse']})
        self.assertIsNotNone(result)

    def test_search_or_cover_match_alone_never_authorizes(self):
        self.assertIsNone(self.verify(old={}))  # Title and cover agree; no known creator.
        self.assertIsNone(self.verify(old={'Writer':'Casey'}))  # A surname alone is not enough.
        self.assertIsNone(self.verify(page=dict(MILKMAN_PAGE,identity_text='The Milkman Murders HC, 2012, Dark Horse Books.')))
        self.agree.return_value=False
        self.assertIsNone(self.verify())
        self.agree.return_value=True
        self.assertIsNone(self.verify(page=dict(MILKMAN_PAGE,image=None)))

    def test_cover_is_mandatory_even_for_search_results(self):
        self.agree.return_value=False
        self.assertIsNone(self.verify(require_cover=False))
        self.read.assert_called_once()

    def test_title_must_be_exact_and_unnumbered(self):
        for title in ('The Milkman Murders #1','Milkman','The Milkman Murders Returns','Milkman Murders Vol. 2'):
            page=dict(MILKMAN_PAGE,title=title,headings=[])
            self.assertIsNone(self.verify(page=page),title)
        # A page with no book format: the title still matches, but only a file
        # that says it is a book (here "HC" in its name) takes the book route.
        plain=dict(MILKMAN_PAGE,title='Example Catalog - The Milkman Murders (2012)',headings=[])
        self.assertTrue(research.title_matches(plain['title'],'The Milkman Murders'))
        self.assertIsNone(self.verify(page=plain))
        self.assertIsNotNone(self.verify(row=dict(self.row,path='Dark Horse/The Milkman Murders HC (2012).cbz'),page=plain))

    def test_year_must_still_agree(self):
        self.assertIsNone(self.verify(page=dict(MILKMAN_PAGE,identity_text=MILKMAN_PAGE['identity_text'].replace('2012','2004'))))

    def test_numbered_comic_keeps_mandatory_issue_number(self):
        row=dict(self.row,path='The Milkman Murders 002 (2012).cbz',number='2')
        self.assertIsNone(self.verify(row=row))  # Page title has no '#2'.
        numbered=dict(MILKMAN_PAGE,title='The Milkman Murders #1',headings=[])
        self.assertIsNone(self.verify(row=row,page=numbered))
        result=self.verify(row=row,page=dict(numbered,title='The Milkman Murders #2'))
        self.assertEqual(result['fields']['Number'],'2')

    def test_numbered_comic_from_unlisted_publisher_needs_creators_and_cover(self):
        row={'path':'Boom/Example Saga 003 (2019).cbz','series':'Example Saga','number':'3','year':'2019'}
        page={'url':'https://catalog.example/example-saga-3','title':'Example Saga #3','headings':[],
              'identity_text':'Example Saga #3 (2019), BOOM! Studios. Writer Jane Example.','image':'https://catalog.example/3.jpg'}
        result=self.verify(row=row,old={'Writer':'Jane Example'},page=page,hint={'publisher':'BOOM! Studios'},require_cover=False)
        self.assertEqual(result['fields'],{'Series':'Example Saga','Number':'3','Publisher':'BOOM! Studios'})
        self.read.assert_called_once()
        self.assertIsNone(self.verify(row=row,old={},page=page,hint={'publisher':'BOOM! Studios'},require_cover=False))

    def test_established_hinted_publisher_route_is_unchanged(self):
        row={'path':'Lady Death & Shi (Avatar)/comic.cbz','series':'Lady Death & Shi','number':'1','year':'2007'}
        page={'url':'https://example.org/issue','title':'Lady Death / Shi (2007) #1 - Details','identity_text':'Avatar Press 2007'}
        result=self.verify(row=row,old={},page=page,require_cover=False)
        self.assertEqual(result['fields'],{'Series':'Lady Death & Shi','Number':'1','Publisher':'Avatar Press'})
        self.read.assert_not_called()

    def test_general_web_query_has_no_empty_issue_marker(self):
        with scratch_directory() as d,patch.object(research,'CACHE',Path(d)), \
             patch.object(web_search,'search',return_value=[{'url':MILKMAN_PAGE['url'],'title':'hit'}]) as search, \
             patch.object(web_search,'source',return_value=MILKMAN_PAGE):
            result=research.general_lookup(self.row,self.old)
        self.assertEqual(search.call_args.args[0],'The Milkman Murders comics')
        self.assertEqual(result['fields'],{'Series':'The Milkman Murders'})


class MilkmanDiscoveryTests(unittest.TestCase):
    """End-to-end discovery with saved Lens leads; the archive write is only queued."""
    def setUp(self):
        self.root=Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app,'DATA',self.root/'data'))
        self.enterContext(patch.object(app,'BASE',self.root))
        self.enterContext(patch.object(app,'live_root',return_value=str(self.root)))
        self.enterContext(patch.object(research,'CACHE',self.root/'evidence'))
        import browser_search  # The cover queue is joined only while Lens is on (Enrichment E); tested switched on.
        self.enterContext(patch.object(browser_search,'settings',return_value={'enabled':True}))
        self.folder=self.root/'Dark Horse';self.folder.mkdir()
        self.path=self.folder/'The Milkman Murders (2012).cbz'
        import zipfile
        with zipfile.ZipFile(self.path,'w') as archive:  # A book-length archive (placeholder pages).
            for page in range(60):archive.writestr('%03d.jpg'%page,b'isolated fixture page')
        stat=self.path.stat();self.signature=[stat.st_size,stat.st_mtime_ns]
        import discovery_state
        with app.db() as con:
            discovery_state.initialize(con)
            con.execute('INSERT INTO comics(path,root,size,mtime,series,number,year,metadata,status,seen) VALUES(?,?,?,?,?,?,?,?,?,?)',
                        (str(self.path),str(self.folder),stat.st_size,stat.st_mtime_ns,'The Milkman Murders','','2012','{}','missing',1))
        self.row={'path':str(self.path),'size':stat.st_size,'mtime':stat.st_mtime_ns}
        # The Lens search already ran and saved its leads.
        cover_tasks.enqueue(self.row);self.assertIsNotNone(cover_tasks.claim())
        cover_tasks.record(self.row,[{'url':MILKMAN_PAGE['url'],'title':'The Milkman Murders HC'}])

    def discover(self,page):
        import archive_conversion,worker,local_model,research_runtime,discovery_state,getcomics
        now=time.time()
        statuses={k:{'status':'human_verification','retry_at':now+5000} for k in scheduling.KEYS.values()}
        previous={'version':automatic.MATCHER_VERSION,'signature':self.signature,'retry_at':0,
                  'source_schedule':{name:{'result':'unavailable','next_at':now+5000} for name in scheduling.KEYS}}
        hint={'title':'The Milkman Murders','issue':'','publisher':'Dark Horse Books','creators':['Joe Casey','Steve Parkhouse'],'search_query':''}
        patches=[patch.object(app,'scan'),patch.object(archive_conversion,'one',return_value=False),
                 patch.object(discovery_state,'load',return_value={'checked':{str(self.path):previous}}),
                 patch.object(providers,'statuses',return_value=statuses),
                 patch.object(worker,'QUEUE',self.root/'queue'),
                 patch.object(worker.pause_control,'requested',return_value=False),
                 patch.object(research_runtime,'reuse',return_value=None),patch.object(research_runtime,'remember'),
                 patch.object(automatic,'lookup_unidentified',return_value=None),patch.object(app,'api',side_effect=AssertionError('No ComicVine request')),
                 patch.object(research,'publisher_lookup',return_value=None),
                 patch.object(research,'general_lookup',return_value=None),patch.object(research,'wiki_candidates',return_value=[]),
                 patch.object(getcomics,'lookup',return_value=None),
                 patch.object(web_search,'source',return_value=page),patch.object(web_search,'read',return_value=b'remote cover'),
                 patch('reverse_image.cover',return_value=(b'local cover','','')),patch.object(automatic,'covers_agree',return_value=True),
                 patch.object(local_model,'available',return_value=True),patch.object(local_model,'identify_cover',return_value=hint),
                 patch.object(local_model,'sourced_synopsis',return_value=None)]
        with ExitStack() as stack:
            for item in patches:stack.enter_context(item)
            enqueue=stack.enter_context(patch.object(worker,'enqueue'))
            automatic.discover(self.folder,coverage_only=True)
        with app.db() as con:
            record=json.loads(con.execute('SELECT value FROM discovery_records WHERE path=?',(str(self.path),)).fetchone()[0])
            task=con.execute('SELECT state FROM cover_tasks WHERE path=?',(str(self.path),)).fetchone()[0]
        return enqueue,record,task,now

    def test_saved_lens_lead_now_identifies_the_one_shot(self):
        enqueue,record,task,_=self.discover(MILKMAN_PAGE)
        self.assertEqual(record['outcome'],'queued')
        entry=json.loads(enqueue.call_args.args[0].read_text(encoding='utf-8'))['entries'][0]
        self.assertEqual({k:entry['fields'][k] for k in entry['fields'] if k!='Notes'},{'Series':'The Milkman Murders','Publisher':'Dark Horse Books'})
        self.assertIn(MILKMAN_PAGE['url'],entry['fields']['Notes'])
        self.assertEqual(task,'leads_found')

    def test_unverified_leads_leave_the_comic_searchable(self):
        page=dict(MILKMAN_PAGE,identity_text='The Milkman Murders HC, 2012.')  # No creator named.
        enqueue,record,task,now=self.discover(page)
        enqueue.assert_not_called()
        self.assertEqual(record['outcome'],'needs_identity_lookup')
        self.assertLessEqual(record['retry_at'],now+86400+60)  # Rechecked within a day; never final.
        self.assertEqual(task,'leads_unverified')  # Lens searches again after its cache expires.


if __name__=='__main__':
    unittest.main()
