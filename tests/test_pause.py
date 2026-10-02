import json
import unittest
from pathlib import Path
from unittest.mock import patch
import app
import batch
import local_model
import pause_control
import worker
import test_app


class PauseTests(unittest.TestCase):
    setUp=test_app.LibraryTests.setUp
    tearDown=test_app.LibraryTests.tearDown
    make=test_app.LibraryTests.make
    def test_pause_is_durable_and_requires_both_workers(self):
        self.assertFalse(pause_control.requested())
        pause_control.change(True)
        self.assertTrue(pause_control.requested())
        with patch.object(pause_control,'unload_model') as unload:
            pause_control.checkpoint('metadata')
            self.assertEqual(pause_control.status()['phase'],'pausing')
            pause_control.checkpoint('browser')
            pause_control.checkpoint('metadata')
            self.assertEqual(unload.call_count,1)
        self.assertEqual(pause_control.status()['phase'],'paused')
        self.assertTrue(pause_control.status()['gpu_released'])
        pause_control.change(True)
        self.assertEqual(pause_control.status()['phase'],'paused')
        pause_control.change(False)
        self.assertFalse(pause_control.requested())
        pause_control.change(True)
        self.assertEqual(pause_control.status()['phase'],'pausing')

    def test_paused_model_call_never_reaches_ollama(self):
        pause_control.change(True)
        with patch('urllib.request.urlopen') as network:
            with self.assertRaises(pause_control.PauseRequested):local_model.chat('test')
            network.assert_not_called()

    def test_unload_failure_does_not_claim_gpu_released(self):
        pause_control.change(True)
        with patch.object(pause_control,'unload_model',side_effect=OSError):
            pause_control.checkpoint('metadata');pause_control.checkpoint('browser')
        self.assertFalse(pause_control.status()['gpu_released'])
        self.assertTrue(pause_control.status()['error'])

    def test_batch_resumes_without_rewriting_verified_archive(self):
        paths=[self.make('Example 001.cbz'),self.make('Example 002.cbz')]
        plan_dir=self.temp_path/'batch';plan_dir.mkdir()
        plan=plan_dir/'plan.json'
        plan.write_text(json.dumps({'folder':str(self.root),'entries':[
            {'path':str(p),'action':'write','sha256':batch.digest(p),'changes':{'Title':{'before':'','after':'Verified title'}},'fields':{'Title':'Verified title'}} for p in paths]}))
        (self.temp_path/'data').mkdir()
        with patch.object(app,'BASE',self.temp_path):
            with patch.object(pause_control,'requested',side_effect=[False,True]):
                with self.assertRaises(pause_control.PauseRequested):batch.apply(plan,True)
            first_signature=paths[0].stat().st_mtime_ns
            self.assertEqual(app.read_metadata(paths[0])[0]['Title'],'Verified title')
            self.assertFalse(app.read_metadata(paths[1])[0].get('Title'))
            with patch.object(pause_control,'requested',return_value=False):batch.apply(plan,True)
            self.assertEqual(paths[0].stat().st_mtime_ns,first_signature)
            self.assertEqual(app.read_metadata(paths[1])[0]['Title'],'Verified title')
            results=json.loads((plan_dir/'results.json').read_text())
            self.assertEqual(len(results),2)
            self.assertTrue(all(r['backup_removed_after_verification'] for r in results))

    def test_paused_queue_keeps_ticket_pending(self):
        plan=self.temp_path/'plan.json'
        plan.write_text(json.dumps({'folder':str(self.root),'entries':[{'action':'write'}]}))
        with patch.object(worker,'QUEUE',self.temp_path/'queue'),patch.object(batch,'apply') as apply:
            ticket=worker.enqueue(plan)
            pause_control.change(True)
            self.assertFalse(worker.run_one());apply.assert_not_called()
            pause_control.change(False)
            apply.side_effect=pause_control.PauseRequested()
            worker.run_one()
            self.assertEqual(json.loads(ticket.read_text())['state'],'pending')
            apply.side_effect=None
            worker.run_one()
            self.assertEqual(json.loads(ticket.read_text())['state'],'complete')
