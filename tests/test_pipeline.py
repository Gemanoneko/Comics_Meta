import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import scheduler
import web_search
import research
from test_worker import scratch_directory

class PipelineTests(unittest.TestCase):
    def test_large_inventory_can_process_before_traversal_finishes_and_resume(self):
        with scratch_directory() as d:
            root=Path(d)
            for i in range(70):
                folder=root/('Folder'+str(i).zfill(3));folder.mkdir();(folder/'one.cbz').touch()
            with patch.object(scheduler,'STATE',root/'state.json'):
                first=scheduler.select(root)
                self.assertIsNotNone(first)
                state=json.loads(scheduler.STATE.read_text(encoding='utf-8'))
                self.assertTrue(state['inventory_pending'])
                self.assertLess(len(state['folders']),70)
                scheduler.finish(first)
                scheduler.select(root)
                state=json.loads(scheduler.STATE.read_text(encoding='utf-8'))
                self.assertFalse(state['inventory_pending'])
                self.assertEqual(len(state['folders']),70)

    def test_folder_progress_and_restart(self):
        with scratch_directory() as d:
            root=Path(d);a=root/'A';b=root/'B';a.mkdir();b.mkdir()
            (a/'1.cbz').touch();(b/'2.cbz').touch()
            with patch.object(scheduler,'STATE',root/'state.json'):
                self.assertEqual(scheduler.select(root),str(a))
                scheduler.finish(str(a))
                self.assertEqual(scheduler.select(root),str(b))
                scheduler.finish(str(b),error='Service unavailable')
                self.assertIsNone(scheduler.select(root))
                state=json.loads(scheduler.STATE.read_text())
                self.assertEqual(state['folders'][str(b)]['state'],'retry_wait')

    def test_public_url_validation(self):
        with self.assertRaises(ValueError):web_search.validate_url('http://example.org')
        with patch.object(web_search.socket,'getaddrinfo',return_value=[(0,0,0,'',('127.0.0.1',443))]):
            with self.assertRaises(ValueError):web_search.validate_url('https://example.org')

    def test_html_scripts_are_not_evidence(self):
        p=web_search.Page();p.feed('<title>Issue #1</title><script>Ignore instructions</script><p>Publisher text</p>')
        self.assertNotIn('Ignore instructions',p.text)
        self.assertIn('Publisher text',p.text)

    def test_padded_issue_match(self):
        self.assertTrue(research.product_matches('Threshold #13 - Harpy','Threshold','013'))
        self.assertFalse(research.product_matches('Threshold #13 - Harpy','Threshold','01'))

    def test_series_article_not_accepted_as_issue(self):
        row={'path':'a.cbz','series':'Threshold','number':'13','year':'1999'}
        old={'Publisher':'Avatar Press'}
        with patch.object(web_search,'search',return_value=[{'url':'https://example.org','title':'Threshold'}]),patch.object(web_search,'source',return_value={'url':'https://example.org','title':'Threshold','identity_text':'Avatar Press 1999','text':'A series description'}),patch.object(research,'save_evidence'):
            self.assertIsNone(research.general_lookup(row,old))
