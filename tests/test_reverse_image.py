import io
import json
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
import app
import reverse_image
from test_worker import scratch_directory


class ReverseImageTests(unittest.TestCase):
    def test_links_are_leads_and_only_comicvine_issue_links_bridge(self):
        rows=reverse_image.normalize({'results':{'matches':[{'score':99,'backlinks':[
            {'backlink':'javascript:alert(1)'},
            {'backlink':'https://comicvine.gamespot.com/threshold-13/4000-123/'},
            {'backlink':'https://other.example/4000-999/'},
            {'backlink':'https://comicvine.gamespot.com/threshold-13/4000-123/'}]}]}})
        self.assertEqual(len(rows),2);self.assertEqual(rows[0]['comicvine_issue'],123)
        self.assertIsNone(rows[1]['comicvine_issue'])

    def test_cover_only_upload_cache_and_persistent_budget(self):
        with scratch_directory() as directory:
            root=Path(directory);comic=root/'private-name.cbz'
            with zipfile.ZipFile(comic,'w') as archive:
                archive.writestr('01.jpg',b'cover-only');archive.writestr('02.jpg',b'private-interior')
            with patch.object(app,'DATA',root/'data'),patch.object(reverse_image,'settings',return_value=({'enabled':True,'monthly_request_limit':1},'secret-key')),patch.object(reverse_image.urllib.request,'urlopen',return_value=io.BytesIO(json.dumps({'code':200,'results':{'matches':[]}}).encode())) as send:
                reverse_image.search(comic)
                request=send.call_args.args[0]
                self.assertIn(b'cover-only',request.data);self.assertNotIn(b'private-interior',request.data)
                self.assertNotIn(b'private-name',request.data)
                self.assertTrue(reverse_image.search(comic)['cached']);self.assertEqual(send.call_count,1)
                with self.assertRaisesRegex(ValueError,'Monthly'):reverse_image.search(comic,1)

    def test_disabled_search_never_uploads(self):
        with scratch_directory() as directory:
            root=Path(directory);comic=root/'comic.cbz'
            with zipfile.ZipFile(comic,'w') as archive:archive.writestr('01.jpg',b'cover')
            with patch.object(app,'DATA',root/'data'),patch.object(reverse_image,'settings',return_value=({},'')),patch.object(reverse_image.urllib.request,'urlopen') as send:
                with self.assertRaisesRegex(ValueError,'disabled'):reverse_image.search(comic)
                send.assert_not_called()
