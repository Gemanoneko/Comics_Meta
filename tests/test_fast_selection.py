"""#3: folder selection stays fast on a large catalog and a long queue history.

Synthetic catalog and queue only. Before v0.1.3 one 256-row probe joined every
comic against an unindexed history list (13.8 s at 60,000 comics), and every
worker loop re-read every completed queue ticket.
"""
import json
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import app
import automatic
import coverage_priority as coverage
import discovery_state
import worker
from test_worker import scratch_directory


class ProbeSpeedTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app, 'DATA', self.root / 'data'))
        self.enterContext(patch.object(worker, 'QUEUE', self.root / 'queue'))
        self.enterContext(patch.object(coverage.research, 'CACHE', self.root / 'evidence'))
        self.library = str(self.root / 'library')
        waiting = json.dumps({'version': automatic.MATCHER_VERSION, 'signature': [10, 1], 'retry_at': 4e9})
        comics, history, records = [], [], []
        for i in range(30000):
            path = self.library + '\\Series %04d\\Comic %05d.cbz' % (i // 20, i)
            comics.append((path, 10, 1, '{}', 'missing'))
            records.append((path, waiting))
            if i % 10 == 0:
                history.append(('\\\\?\\' + path,))
        with app.db() as con:
            discovery_state.initialize(con)
            con.executemany('INSERT INTO comics(path,size,mtime,metadata,status) VALUES(?,?,?,?,?)', comics)
            con.executemany('INSERT INTO history(path) VALUES(?)', history)
            con.executemany('INSERT INTO discovery_records VALUES(?,?)', records)
        self.due = {self.library + '\\Series %04d' % i for i in range(1500)}

    def probe(self, state):
        started = time.perf_counter()
        result = coverage.firstpass_folder(self.library, self.due, state, {}, automatic.MATCHER_VERSION, 1000)
        return result, time.perf_counter() - started

    def test_one_bounded_probe_is_fast_and_skips_written_history(self):
        state = {'root': self.library, 'folders': {}}
        result, first = self.probe(state)
        self.assertIsNone(result)
        self.assertTrue(state['coverage_pending'])
        cursor = state['coverage_cursor']
        # 256 unwritten comics were probed: written ones (every tenth, saved with a
        # Windows extended-path prefix) are not counted.
        self.assertEqual(cursor, self.library + '\\Series %04d\\Comic %05d.cbz' % (284 // 20, 284))
        result, second = self.probe(state)
        self.assertLess(max(first, second), 1.0, (first, second))  # Before: several seconds per probe.
        with app.db() as con:
            self.assertTrue(con.execute("SELECT 1 FROM sqlite_master WHERE name='comics_path_nocase'").fetchone())


class TicketCacheTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app, 'DATA', self.root / 'data'))
        self.enterContext(patch.object(worker, 'QUEUE', self.root / 'queue'))
        self.enterContext(patch.object(worker.pause_control, 'requested', return_value=False))
        worker.QUEUE.mkdir()
        for i in range(3):
            (worker.QUEUE / ('%03d.json' % i)).write_text(json.dumps({'plan': 'p%d' % i, 'folder': 'F', 'state': 'complete'}))

    def test_completed_tickets_are_read_once(self):
        worker.tickets()
        reads = []
        real = Path.read_text
        with patch.object(Path, 'read_text', autospec=True, side_effect=lambda self, *a, **k: reads.append(self.name) or real(self, *a, **k)):
            self.assertEqual([item['state'] for _, item in worker.tickets()], ['complete'] * 3)
        self.assertEqual(reads, [])  # Before: every ticket on every loop.

    def test_requeued_ticket_is_seen_and_run(self):
        worker.tickets()
        (worker.QUEUE / '001.json').write_text(json.dumps({'plan': 'p1', 'folder': 'F', 'state': 'pending', 'requeued': True}))
        with patch.object(worker.batch, 'apply') as apply:
            self.assertTrue(worker.run_one())
        apply.assert_called_once_with('p1', remove_verified_backups=True)
        self.assertEqual(json.loads((worker.QUEUE / '001.json').read_text())['state'], 'complete')
        self.assertFalse(worker.run_one())

    def test_pending_tickets_are_always_read_from_disk(self):
        (worker.QUEUE / '009.json').write_text(json.dumps({'plan': 'p9', 'folder': 'F', 'state': 'pending'}))
        worker.tickets()
        (worker.QUEUE / '009.json').write_text(json.dumps({'plan': 'p9', 'folder': 'F', 'state': 'running'}))
        self.assertEqual(dict((p.name, i['state']) for p, i in worker.tickets())['009.json'], 'running')


if __name__ == '__main__':
    unittest.main()
