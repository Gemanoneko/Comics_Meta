import io
import json
import time
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
from PIL import Image
import app
import browser_search
import browser_worker
import cover_tasks
import research
from test_worker import scratch_directory


class BrowserSearchTests(unittest.TestCase):
    def test_search_navigation_and_unsafe_links_are_not_candidates(self):
        rows=browser_search.normalize_links([
            {'url':'https://www.google.com/search?q=comic'},
            {'url':'https://www.google.com/url?q=https%3A%2F%2Fcatalog.example%2Fissue'},
            {'url':'https://catalog.example/issue'},
            {'url':'https://secret@catalog.example/other'},
            {'url':'javascript:alert(1)'},
            {'url':'https://accounts.google.com/login'}])
        self.assertEqual(rows,[{'url':'https://catalog.example/issue','title':'catalog.example'}])

    def test_budget_persists_and_does_not_allow_overrun(self):
        with scratch_directory() as d,patch.object(app,'DATA',Path(d)/'data'):
            browser_search.reserve('serpapi',1,'2026-10')
            with self.assertRaisesRegex(ValueError,'limit'):browser_search.reserve('serpapi',1,'2026-10')
            browser_search.reserve('serpapi',1,'2026-11')

    def test_human_challenge_is_reported_without_solving_it(self):
        self.assertTrue(browser_search.challenge('https://www.google.com/sorry/index',''))
        self.assertTrue(browser_search.challenge('https://google.com','Our systems have detected unusual traffic'))
        self.assertFalse(browser_search.challenge('https://google.com/search','Comic results'))

    def test_task_claim_is_exclusive_and_browser_retry_does_not_write_folder_state(self):
        with scratch_directory() as d,patch.object(app,'DATA',Path(d)/'data'),patch.object(app,'live_root',return_value=d),patch.object(research,'CACHE',Path(d)/'research'):
            path=str(Path(d)/'comic.cbz')
            with app.db() as con:con.execute("INSERT INTO comics(path,size,mtime,metadata,status) VALUES(?,1,2,'{}','missing')",(path,))
            row={'path':path,'size':1,'mtime':2};cover_tasks.enqueue(row)
            self.assertIsNotNone(cover_tasks.claim());self.assertIsNone(cover_tasks.claim())
            cover_tasks.record(row,[{'url':'https://catalog.example/issue','title':'Issue'}])
            with app.db() as con:
                self.assertEqual(con.execute('SELECT folder FROM cover_retries').fetchone()[0],d)
                self.assertEqual(con.execute('SELECT state FROM cover_tasks').fetchone()[0],'leads_found')
            self.assertFalse((Path(d)/'data/folders.json').exists())
            import scheduler
            state=Path(d)/'folder-state.json'
            state.write_text(json.dumps({'root':d,'folders':{d:{'next_scan':time.time()+600}},'inventoried_at':time.time()}))
            with patch.object(scheduler,'STATE',state):
                self.assertEqual(scheduler.select(d),d)
            with app.db() as con:self.assertEqual(con.execute('SELECT COUNT(*) FROM cover_retries').fetchone()[0],0)

    def test_serpapi_upload_uses_cover_bytes_and_cache_is_local(self):
        responses=[{'image_id':'upload-token'},{'visual_matches':[{'link':'https://catalog.example/issue','title':'Comic'}]}]
        with scratch_directory() as d,patch.object(app,'DATA',Path(d)/'data'),patch.object(browser_search,'api_key',return_value='test-secret'),patch.object(browser_search,'request_json',side_effect=responses) as send:
            result=browser_search.serpapi_search(b'cover-only',{'serpapi_fallback':True,'serpapi_monthly_limit':1})
            request=send.call_args_list[0].args[0]
            self.assertIn(b'cover-only',request.data);self.assertIn(b'filename="cover.jpg"',request.data)
            self.assertEqual(result[0]['title'],'Comic')
            key,_=browser_search.cached(b'cover-only');browser_search.save_cache(key,result)
            self.assertEqual(browser_search.cached(b'cover-only')[1],result)
            with self.assertRaisesRegex(ValueError,'limit'):browser_search.serpapi_search(b'another',{'serpapi_fallback':True,'serpapi_monthly_limit':1})
            self.assertEqual(send.call_count,2)

    def test_changed_archive_never_records_candidates(self):
        with scratch_directory() as d:
            path=Path(d)/'comic.cbz';path.write_bytes(b'changed')
            row={'path':str(path),'size':1,'mtime':1}
            with patch.object(cover_tasks,'finish') as finish,patch.object(cover_tasks,'record') as record:
                browser_worker.process(row,Mock(),{})
                self.assertEqual(finish.call_args.args[1],'stale');record.assert_not_called()

    def test_api_errors_do_not_expose_key_in_exception(self):
        with patch.object(browser_search.urllib.request,'urlopen',side_effect=ValueError('secret-api-key')):
            with self.assertRaises(ValueError) as caught:browser_search.request_json(Mock())
            self.assertNotIn('secret-api-key',str(caught.exception))

    def test_challenge_records_help_and_fallback_leads_without_writing_metadata(self):
        with scratch_directory() as d,patch.object(app,'DATA',Path(d)/'data'),patch.object(research,'CACHE',Path(d)/'research'):
            path=Path(d)/'comic.cbz';path.write_bytes(b'archive')
            stat=path.stat();row={'path':str(path),'size':stat.st_size,'mtime':stat.st_mtime_ns,'metadata':'{}'}
            cover_tasks.enqueue(row)
            browser=Mock();browser.search.side_effect=browser_search.HumanVerification('https://www.google.com/sorry/index')
            leads=[{'url':'https://catalog.example/issue','title':'Issue'}]
            with patch.object(browser_search,'cover_bytes',return_value=b'cover'),patch.object(browser_search,'serpapi_search',return_value=leads):
                browser_worker.process(row,browser,{'serpapi_fallback':True,'daily_request_limit':1})
            state=browser_search.status()
            self.assertTrue(state['human_verification']);self.assertEqual(state['provider'],'serpapi')
            with app.db() as con:
                self.assertEqual(con.execute('SELECT state FROM cover_tasks').fetchone()[0],'leads_found')
                self.assertEqual(con.execute('SELECT COUNT(*) FROM history').fetchone()[0],0)
            self.assertEqual(path.read_bytes(),b'archive')
