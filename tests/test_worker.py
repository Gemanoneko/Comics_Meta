import json
import tempfile
import shutil
import uuid
from contextlib import contextmanager
import unittest
from pathlib import Path
from unittest.mock import patch
import worker
import app

@contextmanager
def scratch_directory():
    intended = Path(__file__).resolve().parents[1] / 'work' / 'test-runs'
    root = intended / str(uuid.uuid4())
    root.mkdir(parents=True)
    try:
        yield str(root)
    finally:
        assert root.resolve().parent == intended.resolve()
        shutil.rmtree(root)


class QueueTests(unittest.TestCase):
    def setUp(self):
        directory=self.enterContext(scratch_directory())
        self.enterContext(patch.object(app,'DATA',Path(directory)/'catalog'))
        control=patch.object(worker.pause_control,'requested',return_value=False)
        control.start();self.addCleanup(control.stop)
    def test_advance_and_do_not_replay_completed_work(self):
        with scratch_directory() as directory:
            root = Path(directory)
            with patch.object(worker, 'QUEUE', root / 'queue'), patch.object(worker.batch, 'apply') as apply:
                for name in ('001', '002'):
                    plan = root / name / 'plan.json'; plan.parent.mkdir()
                    plan.write_text(json.dumps({'folder':name,'entries':[{'action':'write'}]}))
                    worker.enqueue(plan); worker.enqueue(plan)
                self.assertTrue(worker.run_one()); self.assertTrue(worker.run_one())
                self.assertFalse(worker.run_one())
                self.assertEqual(apply.call_count, 2)
                self.assertTrue(all(c.kwargs['remove_verified_backups'] for c in apply.call_args_list))

    def test_failed_batch_is_flagged_and_next_folder_runs(self):
        with scratch_directory() as directory:
            root = Path(directory)
            with patch.object(worker, 'QUEUE', root / 'queue'), patch.object(worker.batch, 'apply', side_effect=[ValueError('Source changed'), None]) as apply:
                for name in ('001', '002'):
                    plan = root / name / 'plan.json'; plan.parent.mkdir()
                    plan.write_text(json.dumps({'folder':name,'entries':[{'action':'write'}]})); worker.enqueue(plan)
                worker.run_one(); worker.run_one()
                first = json.loads((worker.QUEUE/'001.json').read_text())
                self.assertEqual(first['state'],'needs_attention')
                self.assertFalse(worker.run_one()); self.assertEqual(apply.call_count,2)


if __name__ == '__main__':
    unittest.main()
