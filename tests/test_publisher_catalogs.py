import unittest
import json
from pathlib import Path
from unittest.mock import patch
import publisher_catalogs as catalog
import app
import pause_control
from provider_wait import ProviderDeferred
from test_worker import scratch_directory


class CatalogTests(unittest.TestCase):
    def test_book_volume_aliases_do_not_merge_different_volumes(self):
        self.assertEqual(catalog.title_key('Black Hammer Omnibus v01 (2022)'),catalog.title_key('Black Hammer Omnibus Volume 1 TPB'))
        self.assertNotEqual(catalog.title_key('Black Hammer Omnibus v01'),catalog.title_key('Black Hammer Omnibus v02'))

    def test_wrong_book_year_and_isbn_are_rejected(self):
        source={'url':'https://www.darkhorse.com/books/3010-429/black-hammer-omnibus-volume-2-tpb/','headings':['Black Hammer Omnibus Volume 2 TPB'],
                'identity_text':'Release date: Oct 12, 2022 ISBN: 9781234567890 Copyright 2024','text':'Story premise'}
        row={'series':'Black Hammer Omnibus v02','path':'Book TPB.cbz','year':'2024'}
        old={'Format':'Trade Paperback','Publisher':'Dark Horse Comics','ISBN':'9781234567890'}
        self.assertIsNone(catalog.verify(row,old,source,'darkhorse_catalog'))
        row['year']='2022';old['ISBN']='9781234567891'
        self.assertIsNone(catalog.verify(row,old,source,'darkhorse_catalog'))
        old['ISBN']='9781234567890'
        self.assertIsNotNone(catalog.verify(row,old,source,'darkhorse_catalog'))

    def test_wrong_issue_is_rejected_without_fetching_cover(self):
        source={'url':'https://imagecomics.com/comics/releases/example-2','title':'Example #2','headings':['Example #2'],
                'identity_text':'Originally Published: May 1, 2020 Image Comics','text':'Story','image':'https://cdn.imagecomics.com/cover.jpg'}
        with patch('web_search.read') as read:
            self.assertIsNone(catalog.verify({'series':'Example','number':'1','year':'2020','path':'Example.cbz'},{},source,'image_catalog'))
            read.assert_not_called()

    def test_challenge_stops_requests_and_pause_prevents_network_reservations(self):
        with scratch_directory() as folder,patch.object(app,'DATA',Path(folder)),patch.object(pause_control,'requested',return_value=False):
            catalog.reserve('darkhorse_catalog');catalog.mark('darkhorse_catalog','human_verification')
            with self.assertRaises(ProviderDeferred):catalog.reserve('darkhorse_catalog')
            with patch.object(pause_control,'requested',return_value=True):
                with self.assertRaises(pause_control.PauseRequested):catalog.reserve('image_catalog')

    def test_description_excludes_account_navigation_and_footer(self):
        source={'text':'Generic site description'}
        catalog.enrich('<nav>Login</nav><div class="book-description"><p>Story premise.</p><p>Collects issues.</p></div><footer>Copyright</footer>',source)
        self.assertEqual(source['text'],'Story premise. Collects issues.')

    def test_non_product_and_similar_hosts_are_rejected(self):
        self.assertFalse(catalog.product_url('https://imagecomics.com/comics/series/example','image_catalog'))
        self.assertFalse(catalog.product_url('https://imagecomics.com.evil.example/comics/releases/example-1','image_catalog'))


class CatalogBudgetStatusTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app,'DATA',self.root/'data'))
        self.now=100000
        self.enterContext(patch.object(catalog.time,'time',return_value=self.now))
        with app.db() as con:
            catalog.tables(con)

    def requests(self,name,count,first=None):
        first=self.now-100 if first is None else first
        with app.db() as con:
            con.executemany('INSERT INTO catalog_requests VALUES(?,?)',[(name,first)]*count)
            con.execute("INSERT OR REPLACE INTO catalog_status VALUES(?,'available',0,?)",(name,first))

    def test_exact_300_requests_overrides_stored_available_without_mutation(self):
        self.requests('darkhorse_catalog',300)
        self.assertEqual(catalog.statuses()['darkhorse_catalog'],{'status':'daily_budget_wait','retry_at':self.now-100+86400})
        self.assertEqual(catalog.statuses()['darkhorse_catalog']['status'],'daily_budget_wait')
        with app.db() as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM catalog_requests').fetchone()[0],300)
            self.assertEqual(con.execute('SELECT status,retry_at FROM catalog_status').fetchone()[:],('available',0))

    def test_299_requests_and_other_publisher_remain_available(self):
        self.requests('darkhorse_catalog',299)
        self.requests('image_catalog',1)
        status=catalog.statuses()
        self.assertEqual(status['darkhorse_catalog'],{'status':'available','retry_at':0})
        self.assertEqual(status['image_catalog'],{'status':'available','retry_at':0})
        self.assertEqual(status['previews_catalog'],{'status':'ready'})

    def test_rolling_window_reset_excludes_exactly_24_hour_old_request(self):
        self.requests('darkhorse_catalog',299)
        with app.db() as con:
            con.execute('INSERT INTO catalog_requests VALUES(?,?)',('darkhorse_catalog',self.now-86400+1))
        self.assertEqual(catalog.statuses()['darkhorse_catalog']['retry_at'],self.now+1)
        with patch.object(catalog.time,'time',return_value=self.now+1):
            self.assertEqual(catalog.statuses()['darkhorse_catalog'],{'status':'available','retry_at':0})

    def test_human_hold_and_longer_provider_cooldown_are_preserved(self):
        self.requests('darkhorse_catalog',300)
        self.requests('image_catalog',300)
        with app.db() as con:
            con.execute("UPDATE catalog_status SET status='human_verification',retry_at=0 WHERE provider='darkhorse_catalog'")
            con.execute("UPDATE catalog_status SET status='unavailable',retry_at=? WHERE provider='image_catalog'",(self.now+100000,))
        status=catalog.statuses()
        self.assertEqual(status['darkhorse_catalog'],{'status':'human_verification','retry_at':0})
        self.assertEqual(status['image_catalog'],{'status':'unavailable','retry_at':self.now+100000})

    def test_reserve_still_enforces_existing_budget(self):
        self.requests('darkhorse_catalog',300)
        with patch.object(pause_control,'requested',return_value=False):
            with self.assertRaises(ProviderDeferred) as caught:
                catalog.reserve('darkhorse_catalog')
        self.assertEqual(caught.exception.retry_at,self.now-100+86400)

    def test_coverage_moves_past_budget_wait_to_other_untouched_folder(self):
        import scheduler,providers,worker,coverage_priority,discovery_state,automatic
        self.requests('darkhorse_catalog',300)
        library=self.root/'library';library.mkdir()
        folders={}
        with app.db() as con:
            discovery_state.initialize(con)
            for folder,name,written in [('A','waiting.cbz',False),('B','refine.cbz',True),('Z','new.cbz',False)]:
                directory=library/folder;directory.mkdir();path=directory/name
                folders[str(directory)]={'next_scan':0}
                con.execute('INSERT INTO comics(path,size,mtime,metadata,status) VALUES(?,10,1,?,?)',(str(path),'{}','embedded'))
                if written:con.execute('INSERT INTO history(path) VALUES(?)',(str(path),))
                if folder=='A':
                    previous={'version':automatic.MATCHER_VERSION,'signature':[10,1],'retry_at':self.now+86400,
                              'source_schedule':{'Dark Horse':{'result':'unavailable','next_at':self.now-100+86400}}}
                    con.execute('INSERT INTO discovery_records VALUES(?,?)',(str(path),json.dumps(previous)))
        state={'root':str(library),'inventoried_at':self.now,'folders':folders}
        with patch.object(scheduler,'STATE',self.root/'folders.json'),patch.object(worker,'QUEUE',self.root/'queue'), \
             patch.object(coverage_priority.research,'CACHE',self.root/'evidence'), \
             patch.object(providers,'statuses',side_effect=catalog.statuses):
            scheduler.save(state)
            self.assertEqual(scheduler.select(library,now=self.now,with_mode=True),{'folder':str(library/'Z'),'coverage_only':True})
        with app.db() as con:
            saved=json.loads(con.execute('SELECT value FROM discovery_records').fetchone()[0])
            self.assertEqual(saved['retry_at'],self.now+86400)
            self.assertEqual(saved['source_schedule']['Dark Horse']['next_at'],self.now-100+86400)
