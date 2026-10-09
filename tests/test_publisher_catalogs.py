import unittest
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
