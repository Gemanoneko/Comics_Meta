"""Complete history, atomic file revisions and bounded independent reads."""
import io
import json
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
import app
import progress_snapshot as progress
from test_worker import scratch_directory


class SnapshotTests(unittest.TestCase):
    def test_full_legacy_history_and_opt_in_revision_preserve_every_row(self):
        rows=[{'folder':str(i),'updated':i} for i in range(6000)]
        snapshot=progress.Snapshot(lambda _: {'completed':rows,'completed_revision':'one','queue':{'complete':6000}})
        snapshot.refresh()
        self.assertEqual(snapshot.get()['completed'],rows)
        compact=snapshot.get('one');self.assertNotIn('completed',compact)
        self.assertEqual(snapshot.get('old')['completed'],rows)
        snapshot.get()['completed'].clear();self.assertEqual(len(snapshot.get()['completed']),6000)
        snapshot.collector=lambda _: {'completed':rows+[{'folder':'new','updated':1}],'completed_revision':'two'}
        snapshot.refresh();self.assertEqual(len(snapshot.get('one')['completed']),6001)

    def test_only_one_slow_collector_and_status_reads_do_not_wait_for_it(self):
        entered=threading.Event();release=threading.Event();calls=[]
        def collect(_):calls.append(1);entered.set();release.wait(3);return {'completed':[]}
        snapshot=progress.Snapshot(collect)
        try:
            with self.assertRaises(ValueError):snapshot.get()
            self.assertTrue(entered.wait(1))
            start=time.monotonic()
            for _ in range(20):
                with self.assertRaises(ValueError):snapshot.get()
            self.assertLess(time.monotonic()-start,.2);self.assertEqual(len(calls),1)
        finally:release.set();snapshot.close()

    def test_failed_refresh_keeps_entire_last_snapshot(self):
        snapshot=progress.Snapshot(lambda _: {'completed':[{'folder':'keep'}]});snapshot.refresh()
        snapshot.collector=Mock(side_effect=OSError('fixture'));snapshot.refresh()
        self.assertEqual(snapshot.get()['completed'],[{'folder':'keep'}]);self.assertTrue(snapshot.get()['snapshot_stale'])

    def test_file_cache_detects_replacement_removal_and_updates_without_writes(self):
        with scratch_directory() as directory:
            root=Path(directory);path=root/'one.json';raw='{"state":"pending"}';path.write_text(raw)
            files=progress.Files();first=files.queue(root);self.assertEqual(first,[{'state':'pending'}])
            with patch.object(Path,'read_text',side_effect=AssertionError('unchanged file read')):self.assertEqual(files.queue(root),first)
            other=root/'replacement';other.write_text('{"state":"complete"}');other.replace(path)
            self.assertEqual(files.queue(root),[{'state':'complete'}]);path.unlink()
            self.assertEqual(files.queue(root),[]);self.assertNotIn(path,files.values)

    def handler(self,path):
        handler=object.__new__(app.Handler);handler.path=path;handler.headers={'Host':'127.0.0.1:12345'}
        handler.server=SimpleNamespace(server_port=12345,progress_snapshot=Mock())
        handler.respond=Mock();return handler

    def test_fast_lens_api_does_not_touch_expensive_progress(self):
        handler=self.handler('/api/browser-verification')
        with patch('lens_verification.status',return_value={'phase':'queued'}),patch('browser_search.legacy_status',return_value={}),patch('pause_control.status',return_value={'requested':False}),patch('yandex_verification.status',return_value={}):handler.do_GET()
        handler.server.progress_snapshot.get.assert_not_called()
        self.assertEqual(handler.respond.call_args.args[0]['phase'],'queued')

    def test_progress_pause_is_current_even_when_aggregate_is_cached(self):
        handler=self.handler('/api/progress?completed_revision=old');handler.server.progress_snapshot.get.return_value={'completed':[1,2],'control':{'requested':False}}
        with patch('pause_control.status',return_value={'requested':True}):handler.do_GET()
        self.assertTrue(handler.respond.call_args.args[0]['control']['requested'])
        self.assertEqual(handler.respond.call_args.args[0]['completed'],[1,2])
        handler.server.progress_snapshot.get.assert_called_once_with('old')

    def test_disconnect_is_not_answered_twice(self):
        handler=self.handler('/api/progress');handler.server.progress_snapshot.get.return_value={}
        handler.respond.side_effect=ConnectionAbortedError()
        with patch('pause_control.status',return_value={}):handler.do_GET()
        self.assertEqual(handler.respond.call_count,1)
