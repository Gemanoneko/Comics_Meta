"""v0.1.2 review round 2: the identity check behind any-publisher and unnumbered
confirmations (Senua F1, F3, F9; Futaba Q-1, Q-2).

Mocked pages, covers and model output only; no public requests, no real comics.
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
import web_search
from test_worker import scratch_directory


def book_archive(path,pages):
    with zipfile.ZipFile(path,'w') as archive:
        for page in range(pages):archive.writestr('%03d.jpg'%page,b'placeholder page')


class TitleSegmentTests(unittest.TestCase):
    """F1(a): a title segment matches only beside site names, formats or years."""
    def test_issue_part_volume_series_and_edition_pages_never_match(self):
        for title,series in (('Saga - Issue 12 | Image Comics','Saga'),
                             ('Batman: The Killing Joke - Part 1 | DC','Batman: The Killing Joke'),
                             ('Hellboy: Seed of Destruction - Vol. 2 - Dark Horse','Hellboy: Seed of Destruction'),
                             ('GCD :: Series :: Spawn','Spawn'),
                             ('Venom (2018 - 2021) | Comic Series | Marvel','Venom'),
                             ('Venom (2018-) | Marvel','Venom'),
                             ('Ronin (2015) - Omnibus','Ronin'),
                             ('The Sandman | Absolute Edition','The Sandman'),
                             ('The Milkman Murders - Vol. 2','The Milkman Murders'),
                             ('The Milkman Murders - Book Two','The Milkman Murders'),
                             ('Maus - Review','Maus'),
                             ('Watchmen | Characters | DC','Watchmen'),
                             ('Watchmen - Film','Watchmen')):
            self.assertFalse(research.title_matches(title,series),title)

    def test_site_names_formats_and_years_still_match(self):
        # Control: these shapes matched before the fix and still do.
        for title,series in (('The Milkman Murders HC :: Profile :: Example Catalog','The Milkman Murders'),
                             ('Example Catalog - The Milkman Murders (2012)','The Milkman Murders'),
                             ('Maus | Graphic Novel | Pantheon','Maus'),
                             ('Batman: The Killing Joke One-Shot - DC','Batman: The Killing Joke'),
                             ('The Milkman Murders - Wikipedia','The Milkman Murders'),
                             ('The Milkman Murders | 2012 | Example Catalog','The Milkman Murders'),
                             ('The Milkman Murders | TPB','The Milkman Murders')):
            self.assertTrue(research.title_matches(title,series),title)

    def test_the_matched_title_reports_its_book_format(self):
        for title,series,expected in (('The Milkman Murders HC :: Profile :: Example Catalog','The Milkman Murders','hc'),
                                      ('Example Catalog - The Milkman Murders (2012)','The Milkman Murders',''),
                                      ('Maus | Graphic Novel | Pantheon','Maus','graphicnovel'),
                                      ('Batman: The Killing Joke One-Shot - DC','Batman: The Killing Joke','oneshot'),
                                      ('The Milkman Murders - Wikipedia','The Milkman Murders',''),
                                      ('The Milkman Murders | TPB','The Milkman Murders','tpb')):
            self.assertEqual(research.title_format(title,series),expected,title)

    def test_series_page_urls_are_rejected_for_unnumbered_books(self):
        row={'path':'Spawn TPB (1992).cbz','series':'Spawn','number':'','year':'1992'}
        page={'url':'https://www.comics.org/series/1234/','title':'Spawn','headings':[],
              'identity_text':'Spawn 1992 by Todd McFarlane','image':'/cover.jpg'}
        with patch.object(web_search,'read',return_value=b'remote cover'),patch('reverse_image.cover',return_value=(b'local cover','','')),patch.object(automatic,'covers_agree',return_value=True):
            self.assertIsNone(research.verify_web_source(row,{'Writer':'Todd McFarlane'},page))
            self.assertIsNotNone(research.verify_web_source(row,{'Writer':'Todd McFarlane'},dict(page,url='https://catalog.example/spawn-tpb')))


class UnnumberedBookSignalTests(unittest.TestCase):
    """F1(b): "no number found" alone no longer means "a whole book"."""
    def setUp(self):
        self.root=Path(self.enterContext(scratch_directory()))
        for item in (patch.object(web_search,'read',return_value=b'remote cover'),patch('reverse_image.cover',return_value=(b'local cover','','')),patch.object(automatic,'covers_agree',return_value=True)):self.enterContext(item)
        self.old={'Writer':'Brian K. Vaughan'}
        self.page={'url':'https://catalog.example/saga','title':'Saga | Image Comics','headings':[],
                   'identity_text':'Saga, 2012. Written by Brian K. Vaughan, art by Fiona Staples.','image':'/saga.jpg'}

    def row(self,name,pages=0):
        path=self.root/name
        if pages:book_archive(path,pages)
        return {'path':str(path),'series':'Saga','number':'','year':'2012'}

    def test_single_issue_named_without_its_number_is_not_a_book(self):
        # Before the fix this returned a match, so the series page's text could
        # become the Summary of Saga #1.
        self.assertIsNone(research.verify_web_source(self.row('Saga (2012).cbz',pages=24),self.old,self.page))

    def test_the_file_can_say_it_is_a_book(self):
        for name,old in (('Saga TPB (2012).cbz',{}),('Saga One-Shot (2012).cbz',{}),('Saga (2012).cbz',{'Format':'Graphic Novel'}),
                         ('Saga (2012).cbz',{'Count':'1'}),('Saga (2012).cbz',{'ISBN':'9781607066019'})):
            self.assertIsNotNone(research.verify_web_source(self.row(name),dict(self.old,**old),self.page),name)

    def test_a_page_format_needs_a_book_length_archive_unless_it_is_a_one_shot(self):
        hardcover=dict(self.page,title='Saga HC | Image Comics')
        self.assertIsNone(research.verify_web_source(self.row('Saga (2012).cbz',pages=24),self.old,hardcover))
        self.assertIsNotNone(research.verify_web_source(self.row('Saga (2012).cbz',pages=60),self.old,hardcover))
        one_shot=dict(self.page,title='Saga One-Shot | Image Comics')
        self.assertIsNotNone(research.verify_web_source(self.row('Saga (2012).cbz',pages=24),self.old,one_shot))

    def test_wrong_page_shapes_fail_even_for_a_real_book(self):
        row=self.row('Saga TPB (2012).cbz')
        for title in ('Saga - Issue 12 | Image Comics','Saga | Comic Series | Image Comics','Saga - Deluxe Edition'):
            self.assertIsNone(research.verify_web_source(row,self.old,dict(self.page,title=title)),title)


class CreatorNameTests(unittest.TestCase):
    """F1(c) and Q-1: real creator names only, and every real name usable."""
    def test_model_read_companies_characters_and_title_echoes_are_not_creators(self):
        old={'Series':'Batman: Year One'}
        hint={'publisher':'DC','creators':['Marvel Comics','Spider-Man','Batman Year One','Dark Horse','The Amazing Team','Frank Miller']}
        self.assertEqual(research.creator_names(old,hint),[['frank','miller']])

    def test_model_read_blurbs_and_places_are_not_creators(self):
        # F11(b), v0.1.2 review round 2. Embedded credits are never filtered this way.
        hint={'creators':['New York Times Bestseller','Eisner Award Winner','Eisner Award-Winning','Gotham City','Neil Gaiman']}
        self.assertEqual(research.creator_names({},hint),[['neil','gaiman']])
        self.assertEqual(research.creator_names({'Writer':'Jane City'}),[['jane','city']])

    def test_editor_credits_do_not_count(self):
        self.assertEqual(research.creator_names({'Editor':'Diana Schutz'}),[])
        self.assertEqual(research.creator_names({'Editor':'Diana Schutz','Writer':'Joe Casey'}),[['joe','casey']])

    def test_art_as_a_first_name_survives(self):
        self.assertEqual(research.creator_names({'Writer':'Art Spiegelman'}),[['art','spiegelman']])
        self.assertEqual(research.creator_names({'Penciller':'Art Adams'}),[['art','adams']])
        self.assertEqual(research.creator_names({},{'creators':['Art by Frank Miller','Story: Joe Casey','Pencils John Romita Jr']}),
                         [['frank','miller'],['joe','casey'],['john','romita','jr']])

    def test_surname_first_credits_are_one_person(self):
        self.assertEqual(research.creator_names({'Writer':'Casey, Joe'}),[['joe','casey']])
        self.assertEqual(research.creator_names({'Writer':'Casey, Joe; Parkhouse, Steve'}),[['joe','casey'],['steve','parkhouse']])
        self.assertEqual(research.creator_names({'Writer':'Alan Moore, Dave Gibbons'}),[['alan','moore'],['dave','gibbons']])

    def test_accents_fold_on_both_sides(self):
        self.assertTrue(research.named(research.creator_names({'Writer':'Jiri Kylian'})[0],'Story by Jiří Kylián.'))
        self.assertTrue(research.named(research.creator_names({'Writer':'Jiří Kylián'})[0],'Story by JIRI KYLIAN.'))

    def test_maus_page_crediting_art_spiegelman_now_verifies(self):
        row={'path':'Maus TPB (1986).cbz','series':'Maus','number':'','year':'1986'}
        page={'url':'https://catalog.example/maus','title':'Maus | Pantheon','headings':[],
              'identity_text':'Maus (1986). By Art Spiegelman.','image':'/maus.jpg'}
        with patch.object(web_search,'read',return_value=b'remote cover'),patch('reverse_image.cover',return_value=(b'local cover','','')),patch.object(automatic,'covers_agree',return_value=True):
            self.assertIsNotNone(research.verify_web_source(row,{'Writer':'Art Spiegelman'},page))


class PublisherConfirmationTests(unittest.TestCase):
    """F3 / Q-2: no bag-of-words publisher, and canonical names."""
    row={'path':'fixture.cbz'}

    def confirm(self,hint,body):
        return research.confirmed_publisher(self.row,{},{'publisher':hint},body)

    def test_partial_and_one_word_hints_are_not_confirmed_by_incidental_words(self):
        self.assertEqual(self.confirm('Dark','Published by Dark Horse Books.'),'')
        self.assertEqual(self.confirm('Image','See image gallery. Click the image to enlarge.'),'')
        self.assertEqual(self.confirm('Boom','Sales went boom.'),'')
        self.assertEqual(self.confirm('Kitchen Sink','Published by Kitchen Sink Press.'),'')
        self.assertEqual(self.confirm('Horse Books','Published by Dark Horse Books.'),'')

    def test_known_publishers_are_written_under_their_canonical_name(self):
        self.assertEqual(self.confirm('Image','Image Comics presents Saga.'),'Image Comics')
        self.assertEqual(self.confirm('Boom','Published by BOOM! Studios.'),'BOOM! Studios')
        self.assertEqual(self.confirm('Top Shelf','Published by Top Shelf Productions.'),'Top Shelf Productions')  # Not the partial 'Top Shelf'.
        self.assertEqual(self.confirm('Top Shelf Productions','Published by Top Shelf Productions.'),'Top Shelf Productions')
        self.assertEqual(self.confirm('Dark Horse','Published 2012 by Dark Horse Books.'),'Dark Horse Comics')

    def test_a_full_name_on_the_page_is_written_as_read(self):
        self.assertEqual(self.confirm('Dark Horse Books','Published 2012 by Dark Horse Books. Written by Joe Casey.'),'Dark Horse Books')
        self.assertEqual(self.confirm('Kitchen Sink Press','Published by Dark Horse Books.'),'')


class WrongBookSummaryTests(unittest.TestCase):
    """The key harm: a wrong book's page must not fill an empty Summary.

    Discovery end to end with a saved Lens lead; the local model is mocked to
    propose a synopsis from whatever source verification lets through.
    """
    def setUp(self):
        self.root=Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app,'DATA',self.root/'data'))
        self.enterContext(patch.object(app,'BASE',self.root))
        self.enterContext(patch.object(app,'live_root',return_value=str(self.root)))
        self.enterContext(patch.object(research,'CACHE',self.root/'evidence'))
        self.folder=self.root/'Image';self.folder.mkdir()

    def comic(self,pages):
        # pages=24: Saga #1 saved without its issue number (a single issue).
        # pages=60: a book-length archive of the same title (the positive control).
        self.path=self.folder/'Saga (2012).cbz';book_archive(self.path,pages)
        stat=self.path.stat();self.signature=[stat.st_size,stat.st_mtime_ns]
        import discovery_state
        with app.db() as con:
            discovery_state.initialize(con)
            con.execute('INSERT INTO comics(path,root,size,mtime,series,number,year,metadata,status,seen) VALUES(?,?,?,?,?,?,?,?,?,?)',
                        (str(self.path),str(self.folder),stat.st_size,stat.st_mtime_ns,'Saga','','2012','{}','missing',1))
        self.row={'path':str(self.path),'size':stat.st_size,'mtime':stat.st_mtime_ns}
        cover_tasks.enqueue(self.row);self.assertIsNotNone(cover_tasks.claim())

    def discover(self,page):
        import archive_conversion,worker,local_model,research_runtime,discovery_state,getcomics
        cover_tasks.record(self.row,[{'url':page['url'],'title':page['title']}])
        now=time.time()
        statuses={k:{'status':'human_verification','retry_at':now+5000} for k in scheduling.KEYS.values()}
        previous={'version':automatic.MATCHER_VERSION,'signature':self.signature,'retry_at':0,
                  'source_schedule':{name:{'result':'unavailable','next_at':now+5000} for name in scheduling.KEYS}}
        hint={'title':'Saga','issue':'','publisher':'Image','creators':['Brian K. Vaughan','Fiona Staples'],'search_query':''}
        proposal={'summary':'A whole-series synopsis from the wrong page.','model':'fixture','sources':[page['url']]}
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
                 patch.object(local_model,'sourced_synopsis',return_value=proposal)]
        with ExitStack() as stack:
            for item in patches:stack.enter_context(item)
            enqueue=stack.enter_context(patch.object(worker,'enqueue'))
            automatic.discover(self.folder,coverage_only=True)
        return enqueue

    def page(self,title):
        return {'url':'https://imagecomics.example/saga','headings':[],'image':'/saga.jpg','title':title,
                'text':'Saga is an epic space opera about a family at war with the universe. '*3,
                'identity_text':'Saga (2012) by Brian K. Vaughan and Fiona Staples. Image Comics.'}

    def assert_no_plan(self,title):
        self.comic(24)
        self.discover(self.page(title)).assert_not_called()  # No plan: no Summary, no Notes claiming identity.

    def test_positive_control_the_right_book_page_still_fills_the_summary(self):
        self.comic(60)
        enqueue=self.discover(self.page('Saga HC | Image Comics'))
        entry=json.loads(enqueue.call_args.args[0].read_text(encoding='utf-8'))['entries'][0]
        self.assertEqual(entry['fields']['Summary'],'A whole-series synopsis from the wrong page.')
        self.assertEqual(entry['fields']['Publisher'],'Image Comics')

    def test_series_landing_page_never_fills_the_summary_of_an_unnumbered_issue(self):
        self.assert_no_plan('Saga | Image Comics')

    def test_another_issue_page_never_fills_the_summary(self):
        self.assert_no_plan('Saga - Issue 12 | Image Comics')

    def test_series_listing_page_never_fills_the_summary(self):
        self.assert_no_plan('Saga | Comic Series | Image Comics')


if __name__=='__main__':
    unittest.main()
