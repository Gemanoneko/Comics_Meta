"""Skipped Lens searches keep their queue place; no cover-search state is final.

Isolated catalog, mocked browser and SerpApi; no public requests or archive writes.
"""
import json
import time
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
import app
import browser_search
import browser_worker as worker
import cover_tasks
import research
from test_worker import scratch_directory

NO_CANDIDATES='No usable cover-search candidates; retry after one day.'


class LensSkipTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app,'DATA',self.root/'data'))
        self.enterContext(patch.object(app,'live_root',return_value=str(self.root)))
        self.enterContext(patch.object(research,'CACHE',self.root/'research'))
        self.enterContext(patch.object(worker.pause_control,'requested',return_value=False))
        self.enterContext(patch.object(worker.search,'cover_bytes',return_value=b'fixture cover'))
        self.enterContext(patch.object(worker.search,'cached',return_value=('fixture-key',None)))
        self.fallback=self.enterContext(patch.object(worker.search,'serpapi_search',return_value=[]))
        self.browser=Mock();self.browser.search.return_value=[{'url':'https://catalog.example/issue','title':'Issue'}]
        self.options={'daily_request_limit':100,'serpapi_fallback':False}
        self.path=self.comic('first.cbz')
        self.other=self.comic('second.cbz')
        self.now=time.time()
        # The first task is an old retry-wait (e.g. a legacy mislabel); the
        # second is a newer pending search queued behind it.
        self.set_task(self.path,'retry_wait',self.now-3*86400,NO_CANDIDATES)
        self.set_task(self.other,'pending',self.now-86400,'queued')

    def comic(self,name):
        path=self.root/name;path.write_bytes(b'isolated fixture '+name.encode())
        stat=path.stat()
        with app.db() as con:
            con.execute("INSERT INTO comics(path,size,mtime,metadata,status) VALUES(?,?,?,'{}','missing')",(str(path),stat.st_size,stat.st_mtime_ns))
        cover_tasks.enqueue({'path':str(path),'size':stat.st_size,'mtime':stat.st_mtime_ns})
        return str(path)

    def set_task(self,path,state,updated,detail):
        with app.db() as con:con.execute('UPDATE cover_tasks SET state=?,updated=?,detail=? WHERE path=?',(state,updated,detail,path))

    def task(self,path=None):
        with app.db() as con:return dict(con.execute('SELECT * FROM cover_tasks WHERE path=?',(path or self.path,)).fetchone())

    def claim_first(self):
        row=cover_tasks.claim()
        self.assertEqual(row['path'],self.path)
        return row

    def assert_kept_in_place(self,reason):
        task=self.task()
        self.assertEqual(task['state'],'retry_wait')
        self.assertEqual(task['updated'],self.now-3*86400)  # Same queue position and wait.
        self.assertIn(reason,task['detail'])
        self.assertNotIn('No usable',task['detail'])
        row=cover_tasks.claim()
        self.assertEqual(row['path'],self.path)  # Still first in line.
        cover_tasks.release(row,task['detail'])

    def test_cooldown_skip_keeps_queue_position_wait_and_true_reason(self):
        retry_at=self.now+1800
        browser_search.legacy_status(browser_retry_at=retry_at)
        hold=worker.process(self.claim_first(),self.browser,self.options)
        self.browser.search.assert_not_called()
        self.assert_kept_in_place('Google Lens is cooling down.')
        self.assertEqual(hold,retry_at)
        self.assertEqual(browser_search.legacy_status()['browser_retry_at'],retry_at)
        self.assertIn('keep their place',browser_search.legacy_status()['detail'])

    def test_daily_cap_skip_keeps_queue_position(self):
        today=time.strftime('%Y-%m-%d',time.gmtime())
        browser_search.reserve('browser',1,today)
        self.options['daily_request_limit']=1
        hold=worker.process(self.claim_first(),self.browser,self.options)
        self.browser.search.assert_not_called()
        self.assert_kept_in_place('Daily Google Lens search limit reached.')
        # Held until the next UTC day, when the count resets; no Lens cooldown.
        self.assertEqual(hold%86400,0)
        self.assertTrue(self.now<hold<=self.now+86400)
        self.assertEqual(browser_search.legacy_status().get('browser_retry_at',0),0)

    def test_google_robot_check_skip_keeps_queue_position_and_remembers_task(self):
        self.browser.search.side_effect=browser_search.HumanVerification('https://www.google.com/sorry/index?continue=fixture')
        hold=worker.process(self.claim_first(),self.browser,self.options)
        self.assert_kept_in_place('Google Lens asked for human verification.')
        self.assertGreater(hold,self.now)
        state=browser_search.legacy_status()
        self.assertTrue(state['human_verification'])
        self.assertEqual(state['verification_task']['path'],self.path)
        # While the check is pending, later claims are skipped the same way.
        hold=worker.process(self.claim_first(),self.browser,self.options)
        self.assertEqual(self.browser.search.call_count,1)
        self.assert_kept_in_place('Google Lens needs human verification.')

    def test_serpapi_cap_during_lens_hold_keeps_queue_position(self):
        browser_search.legacy_status(browser_retry_at=self.now+1800)
        self.options['serpapi_fallback']=True
        self.fallback.side_effect=ValueError('serpapi request limit reached.')
        worker.process(self.claim_first(),self.browser,self.options)
        self.fallback.assert_called_once()
        self.assert_kept_in_place('SerpApi fallback unavailable: serpapi request limit reached.')

    def test_genuine_empty_search_still_waits_one_day(self):
        self.browser.search.return_value=[]
        self.assertIsNone(worker.process(self.claim_first(),self.browser,self.options))
        task=self.task()
        self.assertEqual((task['state'],task['detail']),('retry_wait',NO_CANDIDATES))
        self.assertGreater(task['updated'],self.now-1)
        self.assertEqual(cover_tasks.claim()['path'],self.other)  # Moved behind other work.

    def test_empty_serpapi_fallback_is_a_genuine_search(self):
        browser_search.legacy_status(browser_retry_at=self.now+1800)
        self.options['serpapi_fallback']=True
        worker.process(self.claim_first(),self.browser,self.options)
        self.assertEqual(self.task()['detail'],NO_CANDIDATES)

    def test_browser_failure_is_not_labelled_as_no_candidates(self):
        self.browser.search.side_effect=RuntimeError('synthetic browser failure')
        self.assertIsNone(worker.process(self.claim_first(),self.browser,self.options))
        task=self.task()
        self.assertEqual(task['state'],'retry_wait')
        self.assertEqual(task['detail'],'Cover search could not finish; retry after one day.')

    def test_successful_search_records_leads_and_clears_remembered_task(self):
        browser_search.legacy_status(verification_task={'path':'old'},verification_url='https://www.google.com/sorry/x')
        worker.process(self.claim_first(),self.browser,self.options)
        self.assertEqual(self.task()['state'],'leads_found')
        self.assertEqual(browser_search.legacy_status()['verification_task'],{})


class NoFinalCoverStateTests(unittest.TestCase):
    """Cover leads that never verify are searched again; nothing parks for good."""
    def setUp(self):
        self.root=Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app,'DATA',self.root/'data'))
        self.enterContext(patch.object(app,'live_root',return_value=str(self.root)))
        self.enterContext(patch.object(research,'CACHE',self.root/'research'))
        path=self.root/'comic.cbz';path.write_bytes(b'fixture')
        stat=path.stat();self.row={'path':str(path),'size':stat.st_size,'mtime':stat.st_mtime_ns}
        with app.db() as con:
            con.execute("INSERT INTO comics(path,size,mtime,metadata,status) VALUES(?,?,?,'{}','missing')",(str(path),stat.st_size,stat.st_mtime_ns))
        cover_tasks.enqueue(self.row)
        self.assertIsNotNone(cover_tasks.claim())
        cover_tasks.record(self.row,[{'url':'https://catalog.example/lead','title':'Lead'}])

    def state(self):
        with app.db() as con:return dict(con.execute('SELECT * FROM cover_tasks').fetchone())

    def test_unverified_leads_are_searched_again_after_cache_lifetime(self):
        self.assertEqual(self.state()['state'],'leads_found')
        cover_tasks.enqueue(self.row)  # Discovery: every source, including these leads, failed.
        task=self.state()
        self.assertEqual(task['state'],'leads_unverified')
        self.assertIn('30-day',task['detail'])
        self.assertIsNone(cover_tasks.claim(task['updated']+29*86400))
        self.assertEqual(cover_tasks.claim(task['updated']+30*86400+1)['path'],self.row['path'])

    def test_repeat_discovery_passes_do_not_postpone_the_search(self):
        cover_tasks.enqueue(self.row);first=self.state()['updated']
        cover_tasks.enqueue(self.row)
        self.assertEqual(self.state()['updated'],first)

    def test_identity_found_elsewhere_cancels_the_repeat_search(self):
        cover_tasks.enqueue(self.row);cover_tasks.identified(self.row)
        self.assertEqual(self.state()['state'],'not_needed')

    def test_changed_archive_requeues_immediately(self):
        cover_tasks.enqueue(dict(self.row,mtime=self.row['mtime']+1))
        self.assertEqual(self.state()['state'],'pending')


if __name__=='__main__':
    unittest.main()
