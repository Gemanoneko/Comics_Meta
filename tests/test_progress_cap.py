"""#12: a bounded progress payload and fewer whole-library walks. Isolated files only."""
import json
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
import app
import batch
import progress_snapshot
import scheduler
from test_worker import scratch_directory


class ProgressPayloadTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app, 'DATA', self.root / 'data'))
        self.enterContext(patch.object(app, 'BASE', self.root))
        (self.root / 'data').mkdir()

    def batches(self, count):
        return [{'batch': str(1000 + i), 'folder': 'Folder %d' % i, 'updated': 1, 'review': 0} for i in range(count)]

    def test_dashboard_payload_lists_recent_batches_and_counts_all(self):
        rows = self.batches(6000)
        (self.root / 'data' / 'progress.json').write_text(json.dumps({'phase': 'x', 'completed': rows}))
        for name in ('discovery_state', 'cover_tasks', 'browser_search', 'providers', 'research_runtime', 'pause_control'):
            __import__(name)
        with patch('discovery_state.counts', return_value={}), patch('cover_tasks.status', return_value={}), \
                patch('browser_search.status', return_value={}), patch('providers.statuses', return_value={}), \
                patch('research_runtime.metrics', return_value={}), patch('pause_control.status', return_value={}):
            with progress_snapshot.Files() as files:
                payload = progress_snapshot.collect(files)
        self.assertEqual(payload['completed'], rows[-100:])  # Before: all 6000 on every poll.
        self.assertEqual(payload['completed_total'], 6000)

    def test_progress_file_keeps_recent_batches_and_archives_the_rest_in_order(self):
        (self.root / 'data' / 'progress.json').write_text(json.dumps({'completed': self.batches(250)}))
        folder = self.root / 'Example'
        folder.mkdir()
        comic = folder / 'Example 001.cbz'
        with zipfile.ZipFile(comic, 'w') as archive:
            archive.writestr('001.jpg', b'cover')
        plan = self.root / 'batch-9' / 'plan.json'
        plan.parent.mkdir()
        plan.write_text(json.dumps({'folder': str(folder), 'entries': [{'path': str(comic), 'action': 'write', 'sha256': batch.digest(comic),
                                    'changes': {'Title': {'before': '', 'after': 'T'}}, 'fields': {'Title': 'T'}}]}))
        with patch.object(batch.pause_control, 'requested', return_value=False):
            batch.apply(plan, remove_verified_backups=True)
        kept = json.loads((self.root / 'data' / 'progress.json').read_text())['completed']
        self.assertEqual(len(kept), 200)  # Before: the list grew by one batch per write, forever.
        self.assertEqual(kept[-1]['batch'], 'batch-9')
        archived = [json.loads(line) for line in (self.root / 'data' / 'progress-history.jsonl').read_text().splitlines()]
        self.assertEqual(archived, self.batches(250)[:51])  # Nothing is lost.


class InventoryIntervalTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app, 'BASE', self.root))
        self.enterContext(patch.object(app, 'DATA', self.root / 'data'))
        self.enterContext(patch.object(scheduler, 'STATE', self.root / 'folders.json'))
        self.library = self.root / 'library'
        (self.library / 'A').mkdir(parents=True)
        (self.library / 'A' / 'one.cbz').touch()

    def walks(self, now):
        scheduler.select(self.library, now=now)
        return bool(json.loads(scheduler.STATE.read_text()).get('inventory_visited'))

    def finished_walk(self, at):
        scheduler.select(self.library, now=at)
        state = json.loads(scheduler.STATE.read_text())
        self.assertFalse(state.get('inventory_pending'))
        state['inventory_visited'] = 0
        scheduler.save(state)

    def test_library_is_walked_every_six_hours_not_every_ten_minutes(self):
        self.finished_walk(1000)
        self.assertFalse(self.walks(1000 + 700))  # Before: a new walk after 10 minutes.
        self.assertTrue(self.walks(1000 + 6 * 3600 + 1))

    def test_interval_is_configurable_with_a_ten_minute_floor(self):
        self.finished_walk(1000)
        (self.root / 'config.json').write_text(json.dumps({'automatic': {'inventory_interval_seconds': 60}}))
        self.assertFalse(self.walks(1000 + 300))
        self.assertTrue(self.walks(1000 + 601))


if __name__ == '__main__':
    unittest.main()
