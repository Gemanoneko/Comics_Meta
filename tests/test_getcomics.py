import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import app
import getcomics
import web_search
from test_worker import scratch_directory


class GetComicsTests(unittest.TestCase):
    def test_persistent_interval_shared_across_calls(self):
        with scratch_directory() as folder, patch.object(app,'DATA',Path(folder)), patch.object(getcomics.time,'time',return_value=1000):
            getcomics.reserve()
            with self.assertRaises(web_search.SearchBlocked):getcomics.reserve()
            self.assertEqual(getcomics.status()['retry_at'],1300)
            with patch.object(getcomics.time,'time',return_value=1300):getcomics.reserve()

    def test_human_challenge_stops_future_requests(self):
        response=MagicMock();response.read.return_value=b'<title>Just a moment</title>prove you are human'
        opener=MagicMock();opener.open.return_value.__enter__.return_value=response
        with scratch_directory() as folder, patch.object(app,'DATA',Path(folder)), patch.object(web_search,'validate_url'), patch.object(web_search.urllib.request,'build_opener',return_value=opener):
            with self.assertRaises(web_search.SearchBlocked):web_search.read('https://getcomics.org/?s=Example')
            self.assertEqual(getcomics.status()['status'],'human_verification')
            with self.assertRaises(web_search.SearchBlocked):getcomics.reserve()
            self.assertEqual(opener.open.call_count,1)

    def test_other_sites_are_not_limited(self):
        self.assertFalse(getcomics.is_host('https://getcomics.org.evil.example/'))
        self.assertTrue(getcomics.is_host('https://getcomics.org/other-comics/example/'))

    def test_ambiguous_issues_do_not_fetch_or_write_metadata(self):
        html='<a href="/other-comics/example-1-2020/">Example #1 (2020)</a><a href="/other-comics/example-1-2021/">Example #1 (2021)</a>'
        with scratch_directory() as folder, patch.object(app,'DATA',Path(folder)), patch.object(web_search,'read',return_value=html), patch.object(web_search,'source') as source:
            result=getcomics.lookup({'series':'Example','number':'1','path':'Example 001.cbz'}, {})
            self.assertIsNone(result)
            source.assert_not_called()
