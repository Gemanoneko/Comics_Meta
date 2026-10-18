"""Correctness only: bounded research, ownership, cancellation and source waits."""
import threading
import unittest
from unittest.mock import patch

import pause_control
import research_runtime as runtime
import source_scheduling as scheduling


class EligibilityTests(unittest.TestCase):
    def record(self):
        return {'signature':[1,2], 'version':9, 'retry_at':10,
                'outcome':'needs_identity_lookup', 'source_schedule':{
                    name:{'result':'no_verified_match','next_at':200}
                    for name in scheduling.KEYS}}

    def test_expired_comic_retry_does_not_override_all_source_deadlines(self):
        previous=self.record()
        self.assertFalse(scheduling.due(previous,[1,2],9,{},now=100))
        self.assertTrue(scheduling.due(previous,[1,2],9,{},now=200))

    def test_changes_and_new_evidence_wake_waiting_comic(self):
        previous=self.record()
        self.assertTrue(scheduling.due(previous,[2,2],9,{},now=100))
        self.assertTrue(scheduling.due(previous,[1,2],10,{},now=100))
        self.assertTrue(scheduling.due(previous,[1,2],9,{},new_leads=True,now=100))

    def test_legacy_success_hold_and_untried_source_keep_normal_retry(self):
        for outcome in ('queued','current','identity_conflict','web_issue_found'):
            previous=self.record();previous['outcome']=outcome
            self.assertTrue(scheduling.due(previous,[1,2],9,{},now=100))
        previous=self.record();previous['hold']={'at':1}
        self.assertTrue(scheduling.due(previous,[1,2],9,{},now=100))
        previous=self.record();previous['source_schedule'].pop('Metron')
        self.assertTrue(scheduling.due(previous,[1,2],9,{},now=100))

    def test_recovered_provider_wakes_waiting_comic(self):
        previous=self.record()
        previous['source_schedule']['Metron']={'result':'unavailable','next_at':200}
        self.assertTrue(scheduling.due(previous,[1,2],9,{'metron':{'status':'available'}},now=100))
        self.assertFalse(scheduling.due(previous,[1,2],9,{'metron':{'status':'unavailable','retry_at':200}},now=100))


class LookaheadTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(pause_control,'requested',return_value=False))
        self.enterContext(patch.object(runtime.ComicLookahead,'unchanged',return_value=True))
        self.rows=[dict(path=str(i),size=1,mtime=2,metadata='{}') for i in range(4)]

    def test_two_comics_overlap_but_a_third_is_not_submitted(self):
        barrier=threading.Barrier(3)
        release=threading.Event()
        started=[]
        def lookup(row,old):
            started.append(row['path']);barrier.wait(timeout=5)
            if not release.wait(5):raise AssertionError('Test release missing')
            return row['path']
        with runtime.ComicLookahead() as lane:
            lane.configure(self.rows,lookup)
            try:
                lane.advance();barrier.wait(timeout=5)
                self.assertEqual(set(started),{'0','1'})
                self.assertEqual(len(lane.pending),2)
            finally:release.set()
            self.assertEqual(lane.result(self.rows[1],{},None),'1')
            self.assertEqual(lane.result(self.rows[0],{},None),'0')

    def test_provider_error_is_delivered_once_without_retry(self):
        calls=[]
        def lookup(row,old):
            calls.append(row['path'])
            if row['path']=='0':raise ValueError('source failure')
            return 'verified'
        with runtime.ComicLookahead() as lane:
            lane.configure(self.rows[:2],lookup);lane.advance()
            with self.assertRaisesRegex(ValueError,'source failure'):
                lane.result(self.rows[0],{},None)
            self.assertEqual(lane.result(self.rows[1],{},None),'verified')
        self.assertCountEqual(calls,['0','1'])

    def test_changed_comic_cannot_supply_a_result(self):
        with runtime.ComicLookahead() as lane:
            lane.configure(self.rows[:1],lambda *args:'verified');lane.advance()
            lane.pending['0'].result()
            with patch.object(lane,'unchanged',return_value=False):
                with self.assertRaisesRegex(ValueError,'changed after'):
                    lane.result(self.rows[0],{},None)

    def test_pause_prevents_submission_and_consumption(self):
        with runtime.ComicLookahead() as lane:
            lane.configure(self.rows[:1],lambda *args:'verified')
            with patch.object(pause_control,'requested',return_value=True):
                lane.advance();self.assertFalse(lane.pending)
            lane.advance();lane.pending['0'].result()
            with patch.object(pause_control,'requested',return_value=True):
                with self.assertRaises(pause_control.PauseRequested):
                    lane.result(self.rows[0],{},None)

    def test_exit_drains_and_does_not_publish_or_persist_results(self):
        lane=runtime.ComicLookahead()
        with lane:
            lane.configure(self.rows,lambda *args:'verified');lane.advance()
        self.assertTrue(lane.cancelled.is_set())
        self.assertTrue(all(f.done() for f in lane.pending.values()))
        with runtime.ComicLookahead() as fresh:
            self.assertFalse(fresh.pending)

    def test_nonprefetched_comic_uses_existing_lookup(self):
        with runtime.ComicLookahead() as lane:
            self.assertEqual(lane.result(self.rows[0],{},lambda *args:'normal'),'normal')

    def test_cooperative_cancel_stops_next_provider_step(self):
        started=threading.Event();release=threading.Event();calls=[]
        def lookup(row,old):
            started.set()
            if not release.wait(5):raise AssertionError('Test release missing')
            runtime.research_checkpoint()
            calls.append('second provider request')
        with runtime.ComicLookahead() as lane:
            lane.configure(self.rows[:1],lookup);lane.advance()
            try:
                self.assertTrue(started.wait(5));lane.cancelled.set()
            finally:release.set()
            with self.assertRaises(pause_control.PauseRequested):
                lane.result(self.rows[0],{},None)
        self.assertEqual(calls,[])
        runtime.research_checkpoint()  # Cancellation never leaks onto the owner.
