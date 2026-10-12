"""Isolated catalog/queue fixtures; no real archives, providers or models."""
import json
import os
import shutil
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
import app
from test_worker import scratch_directory
import automatic
import coverage_priority as coverage
import discovery_state
import providers
import scheduler
import worker


class CoveragePriorityTests(unittest.TestCase):
    def setUp(self):
        # Fixtures live in a removed-after-use scratch folder (or under an
        # explicit COMICS_TEST_SCRATCH) and are deleted after each test.
        explicit = os.environ.get('COMICS_TEST_SCRATCH')
        container = Path(explicit) if explicit else Path(self.enterContext(scratch_directory()))
        self.fixture = container / ('fixture-' + uuid.uuid4().hex)
        self.fixture.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.fixture, ignore_errors=True)
        self.root = self.fixture / 'library'
        self.root.mkdir()
        self.enterContext(patch.object(app, 'DATA', self.fixture / 'data'))
        self.enterContext(patch.object(scheduler, 'STATE', self.fixture / 'folders.json'))
        self.enterContext(patch.object(worker, 'QUEUE', self.fixture / 'queue'))
        self.enterContext(patch.object(coverage.research, 'CACHE', self.fixture / 'evidence'))
        self.statuses = {}
        self.enterContext(patch.object(providers, 'statuses', side_effect=lambda: self.statuses))
        with app.db() as con:
            discovery_state.initialize(con)
        self.state = {'root': str(self.root), 'folders': {}, 'inventoried_at': 1000}

    def row(self, folder, name, *, written=False, metadata=None, previous=None, status='embedded'):
        folder = self.root / folder
        folder.mkdir(exist_ok=True)
        path = folder / name
        self.state['folders'].setdefault(str(folder), {'next_scan': 0})
        metadata = {} if metadata is None else metadata
        with app.db() as con:
            con.execute('INSERT INTO comics(path,size,mtime,metadata,status) VALUES(?,10,1,?,?)',
                        (str(path), json.dumps(metadata), status))
            if written:
                con.execute('INSERT INTO history(path) VALUES(?)', (str(path),))
            if previous is not None:
                con.execute('INSERT INTO discovery_records VALUES(?,?)', (str(path), json.dumps(previous)))
        return {'path': str(path), 'size': 10, 'mtime': 1, 'metadata': json.dumps(metadata), 'status': status}

    def select(self,now=1000):
        scheduler.save(self.state)
        result = scheduler.select(self.root, now=now, with_mode=True)
        self.state = json.loads(scheduler.STATE.read_text(encoding='utf-8'))
        return result

    def waiting(self, **extra):
        return dict(version=automatic.MATCHER_VERSION, signature=[10, 1], retry_at=2000, **extra)

    def test_history_including_extended_paths_overrides_transient_catalog_status(self):
        old = self.row('A', 'old.cbz', status='missing')
        new = self.row('A', 'new.cbz', status='tagged')
        extended = '\\\\?\\' + old['path']
        with app.db() as con:
            con.execute('INSERT INTO history(path) VALUES(?)', (extended,))
            written = coverage.written_paths(con)
        self.assertIn(coverage.path_key(old['path']), written)
        self.assertEqual([r['path'] for r in coverage.order_rows([old, new], {}, written, set())], [new['path'], old['path']])
        self.assertEqual(self.select(), {'folder': str(self.root/'A'), 'coverage_only': True})
        self.assertEqual(coverage.path_key('\\\\?\\UNC\\host\\share\\comic.cbz'), '\\\\host\\share\\comic.cbz')

    def test_within_folder_changed_refinement_follows_never_updated(self):
        old = self.row('A', 'a-old.cbz', written=True)
        new = self.row('A', 'z-new.cbz')
        checked = {new['path']: {'signature': [10, 1], 'outcome': 'current'}}
        ordered = coverage.order_rows([old, new], checked, {coverage.path_key(old['path'])}, set())
        self.assertEqual([r['path'] for r in ordered], [new['path'], old['path']])

    def test_cross_folder_coverage_precedes_older_refinement_folder(self):
        self.row('A', 'refine.cbz', written=True)
        self.row('Z', 'new.cbz')
        self.state['folders'][str(self.root/'A')]['next_scan'] = -1
        self.assertEqual(self.select(), {'folder': str(self.root/'Z'), 'coverage_only': True})

    def test_mixed_folder_coverage_pass_never_researches_refinement(self):
        self.row('A', 'refine.cbz', written=True)
        self.row('A', 'waiting.cbz', previous=self.waiting())
        self.row('Z', 'new.cbz')
        self.assertEqual(self.select()['folder'], str(self.root/'Z'))
        import archive_conversion
        with patch.object(app, 'scan'), patch.object(archive_conversion, 'one', return_value=False), \
             patch.object(automatic.batch, 'progress'), patch.object(worker.pause_control, 'requested', return_value=False), \
             patch.object(automatic.time, 'time', return_value=1000), \
             patch.object(app, 'api') as api, patch.object(worker, 'enqueue') as enqueue:
            self.assertFalse(automatic.discover(self.root/'A', coverage_only=True))
        api.assert_not_called()
        enqueue.assert_not_called()

    def test_waiting_firstpass_allows_refinement_without_resetting_retry(self):
        self.row('A', 'refine.cbz', written=True)
        first = self.row('Z', 'new.cbz', previous=self.waiting())
        self.assertEqual(self.select(), {'folder': str(self.root/'A'), 'coverage_only': False})
        with app.db() as con:
            record = json.loads(con.execute('SELECT value FROM discovery_records WHERE path=?', (first['path'],)).fetchone()[0])
        self.assertEqual(record, self.waiting())

    def test_provider_wait_is_preserved_and_new_availability_reopens_coverage(self):
        self.row('A', 'refine.cbz', written=True)
        previous = self.waiting(source_schedule={'GetComics': {'result': 'unavailable', 'next_at': 2000}})
        self.row('Z', 'new.cbz', previous=previous)
        self.statuses = {'getcomics': {'status': 'human_verification'}}
        self.assertFalse(self.select()['coverage_only'])
        self.statuses = {'getcomics': {'status': 'available'}}
        self.assertEqual(self.select(), {'folder': str(self.root/'Z'), 'coverage_only': True})

    def test_ineligible_firstpass_does_not_starve_refinements(self):
        self.row('A', 'refine.cbz', written=True)
        self.row('B', 'french.cbz', metadata={'LanguageISO': 'fr'})
        self.row('C', 'broken.cbz', status='corrupted')
        self.assertFalse(self.select()['coverage_only'])

    def test_active_or_unresolved_tickets_are_not_planned_twice(self):
        self.row('A', 'refine.cbz', written=True)
        candidate = self.row('Z', 'new.cbz')
        worker.QUEUE.mkdir()
        plan = self.fixture/'plan.json'
        plan.write_text(json.dumps({'entries': [{'action': 'write', 'path': candidate['path']}]}))
        for state in ('pending', 'running', 'needs_attention'):
            (worker.QUEUE/'ticket.json').write_text(json.dumps({'state': state, 'plan': str(plan)}))
            self.assertFalse(self.select()['coverage_only'])
            self.assertEqual(coverage.order_rows([candidate], {}, set(), coverage.pending_paths()), [])
        (worker.QUEUE/'ticket.json').write_text(json.dumps({'state': 'complete', 'plan': str(plan)}))
        self.assertTrue(self.select()['coverage_only'])

    def test_probe_cursor_defers_refinement_until_bounded_check_finishes(self):
        self.row('A', 'refine.cbz', written=True)
        for i in range(3):
            self.row('B', str(i)+'.cbz', previous=self.waiting())
        self.row('Z', 'new.cbz')
        with patch.object(coverage, 'PROBE_LIMIT', 2):
            self.assertIsNone(self.select())
            cursor = self.state['coverage_cursor']
            self.assertTrue(self.state['coverage_pending'])
            self.assertEqual(self.select(), {'folder': str(self.root/'Z'), 'coverage_only': True})
            self.assertGreater(self.state['coverage_cursor'], cursor)

    def test_no_due_folders_clears_stale_probe_pending(self):
        self.row('A', 'new.cbz')
        self.state['folders'][str(self.root/'A')]['next_scan'] = 2000
        self.state.update(coverage_pending=True, coverage_cursor='stale')
        self.assertIsNone(self.select())
        self.assertFalse(self.state['coverage_pending'])
        self.assertNotIn('coverage_cursor', self.state)

    def test_saved_leads_and_metron_upgrade_keep_existing_due_exceptions(self):
        row = self.row('A', 'new.cbz')
        previous = self.waiting()
        self.assertFalse(coverage.lookup_flags(row, previous, {}, 9, {}, 1000)[0])
        self.assertTrue(coverage.lookup_flags(row, previous, {}, 9, {'reverse_image_signature': [10, 1], 'reverse_image_matches': ['lead']}, 1000)[0])
        self.assertTrue(coverage.lookup_flags(row, previous, {}, 9, {'verified_evidence': {'result': {'provider': 'Metron', 'metadata_version': 1}}}, 1000)[0])

    def test_stable_waiting_snapshot_reuses_proof_until_earliest_retry(self):
        self.row('A','refine.cbz',written=True)
        previous=self.waiting();previous['retry_at']=1010
        self.row('Z','new.cbz',previous=previous)
        self.assertFalse(self.select()['coverage_only'])
        self.assertEqual(self.state['coverage_recheck_at'],1010)
        with patch.object(coverage,'lookup_flags',side_effect=AssertionError('Stable waiting backlog rescanned')):
            self.assertFalse(self.select(now=1001)['coverage_only'])
        self.assertTrue(self.select(now=1011)['coverage_only'])

    def test_snapshot_invalidates_on_write_history_and_pending_paths(self):
        self.row('A','refine.cbz',written=True)
        waiting=self.row('Z','new.cbz',previous=self.waiting())
        self.assertFalse(self.select()['coverage_only'])
        snapshot=self.state['coverage_snapshot']
        with app.db() as con:
            con.execute('INSERT INTO history(path) VALUES(?)',(waiting['path'],))
        self.assertFalse(self.select()['coverage_only'])
        self.assertNotEqual(self.state['coverage_snapshot']['history'],snapshot['history'])
        worker.QUEUE.mkdir()
        plan=self.fixture/'plan.json'
        plan.write_text(json.dumps({'entries':[{'action':'write','path':waiting['path']}]}))
        (worker.QUEUE/'ticket.json').write_text(json.dumps({'state':'pending','plan':str(plan)}))
        self.assertFalse(self.select()['coverage_only'])
        self.assertEqual(self.state['coverage_snapshot']['pending'],[coverage.path_key(waiting['path'])])

    def test_growing_inventory_advances_cursor_then_rechecks_new_earlier_folder(self):
        self.row('A','refine.cbz',written=True)
        for i in range(3):self.row('B',str(i)+'.cbz',previous=self.waiting())
        with patch.object(coverage,'PROBE_LIMIT',2):
            self.assertIsNone(self.select())
            first_cursor=self.state['coverage_cursor']
            self.row('AA','new.cbz')
            self.assertIsNone(self.select())
            self.assertTrue(self.state['coverage_pending'])
            self.assertNotIn('coverage_cursor',self.state)
            self.assertEqual(self.select(),{'folder':str(self.root/'AA'),'coverage_only':True})
        self.assertTrue(first_cursor)

    def test_future_folder_becoming_due_invalidates_waiting_snapshot(self):
        self.row('A','refine.cbz',written=True)
        self.row('Z','new.cbz')
        self.state['folders'][str(self.root/'Z')]['next_scan']=1001
        self.assertEqual(self.select(now=1000),{'folder':str(self.root/'A'),'coverage_only':False})
        self.assertEqual(self.select(now=1001),{'folder':str(self.root/'Z'),'coverage_only':True})

    def test_unicode_case_history_alias_is_not_a_first_update(self):
        old=self.row('A','Étage.cbz')
        self.row('Z','new.cbz')
        with app.db() as con:
            con.execute('INSERT INTO history(path) VALUES(?)',('\\\\?\\'+old['path'].replace('Étage.cbz','éTAGE.CBZ'),))
        self.assertEqual(self.select(),{'folder':str(self.root/'Z'),'coverage_only':True})


if __name__ == '__main__':
    unittest.main()
