"""Enrichment A (Sergei 2026-10-26): refinement gets a fixed share of passes; comics no source can search are not re-asked.

Isolated catalog, queue and evidence; no archive, provider or model is reached."""
import json
import os
import shutil
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
import app
from test_worker import scratch_directory
import automatic
import coverage_priority as coverage
import discovery_state
import pipeline_config
import providers
import scheduler
import source_scheduling
import worker


class Fixture(unittest.TestCase):
    def setUp(self):
        container = Path(self.enterContext(scratch_directory()))
        self.fixture = container / ('fixture-' + uuid.uuid4().hex)
        self.fixture.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.fixture, ignore_errors=True)
        self.root = self.fixture / 'library'
        self.root.mkdir()
        self.enterContext(patch.object(app, 'DATA', self.fixture / 'data'))
        self.enterContext(patch.object(app, 'STATE_ROOT', self.fixture))
        self.enterContext(patch.object(scheduler, 'STATE', self.fixture / 'folders.json'))
        self.enterContext(patch.object(worker, 'QUEUE', self.fixture / 'queue'))
        self.enterContext(patch.object(coverage.research, 'CACHE', self.fixture / 'evidence'))
        self.enterContext(patch.object(providers, 'statuses', return_value={}))
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
            con.execute('INSERT INTO comics(path,size,mtime,metadata,status) VALUES(?,10,1,?,?)', (str(path), json.dumps(metadata), status))
            if written:
                con.execute('INSERT INTO history(path) VALUES(?)', ('\\\\?\\' + str(path),))
            if previous is not None:
                con.execute('INSERT INTO discovery_records VALUES(?,?)', (str(path), json.dumps(previous)))
        return {'path': str(path), 'size': 10, 'mtime': 1, 'metadata': json.dumps(metadata), 'status': status}

    def select(self, now=1000):
        scheduler.save(self.state)
        result = scheduler.select(self.root, now=now, with_mode=True)
        self.state = json.loads(scheduler.STATE.read_text(encoding='utf-8'))
        return result


class RefinementShareTests(Fixture):
    def test_a_refinement_turn_follows_every_first_update_pass(self):
        self.row('A', 'tagged.cbz', written=True)  # Written, never researched since: due for refinement.
        self.row('Z', 'new.cbz')
        self.assertEqual(self.select(), {'folder': str(self.root / 'Z'), 'coverage_only': True})
        # Before: Z again, for as long as any unwritten comic was due anywhere.
        self.assertEqual(self.select(), {'folder': str(self.root / 'A'), 'coverage_only': False, 'refine': True})
        self.assertEqual(self.select(), {'folder': str(self.root / 'Z'), 'coverage_only': True})

    def test_without_refinement_work_the_turn_falls_through(self):
        self.row('Z', 'new.cbz')
        self.row('Y', 'other.cbz')
        self.assertTrue(self.select()['coverage_only'])
        self.assertTrue(self.select()['coverage_only'])  # No written comic is due: no refinement turn is spent.

    def test_never_refined_comics_come_before_other_refinement_work(self):
        stamp = dict(version=automatic.MATCHER_VERSION, signature=[10, 1], retry_at=0)
        self.row('A', 'researched.cbz', written=True, previous=stamp)  # Due again, but already researched since its write.
        self.row('B', 'tagged.cbz', written=True, previous=dict(stamp, signature=[9, 1]))  # Written since its research.
        self.row('Z', 'new.cbz')
        self.select()
        self.assertEqual(self.select()['folder'], str(self.root / 'B'))

    def test_a_refinement_pass_researches_written_comics_only(self):
        written = self.row('A', 'tagged.cbz', written=True)
        new = self.row('A', 'new.cbz')
        keys = {coverage.path_key(written['path'])}
        self.assertEqual([r['path'] for r in coverage.order_rows([written, new], {}, keys, set(), refine=True)], [written['path']])
        self.assertEqual(len(coverage.order_rows([written, new], {}, keys, set())), 2)  # Ordinary passes keep both.

    def test_worker_hands_the_refinement_mode_to_discovery(self):
        calls = []
        with patch.object(automatic, 'discover', side_effect=lambda folder, **kw: calls.append(kw) or False):
            worker.discover_selection({'folder': 'A', 'coverage_only': False, 'refine': True})
        self.assertEqual(calls, [{'coverage_only': False, 'refine': True}])


class UnsearchableTests(Fixture):
    def unresolved(self, **extra):
        return dict(version=automatic.MATCHER_VERSION, signature=[10, 1], retry_at=0, outcome='needs_identity_lookup', **extra)

    def test_a_comic_no_source_can_search_is_not_due_again(self):
        mark = source_scheduling.search_fingerprint()
        previous = self.unresolved(unsearchable=mark)
        self.assertFalse(source_scheduling.due(previous, [10, 1], automatic.MATCHER_VERSION, {}, now=1000))  # Before: due daily.
        # A changed archive, new leads or a matcher change still wake it.
        self.assertTrue(source_scheduling.due(previous, [11, 1], automatic.MATCHER_VERSION, {}, now=1000))
        self.assertTrue(source_scheduling.due(previous, [10, 1], automatic.MATCHER_VERSION, {}, new_leads=True, now=1000))
        # So does switching a source back on or changing the matching rules.
        self.assertTrue(source_scheduling.due(self.unresolved(unsearchable=dict(mark, sources=['Metron'])), [10, 1], automatic.MATCHER_VERSION, {}, now=1000))
        self.assertTrue(source_scheduling.due(self.unresolved(unsearchable=dict(mark, rules='old')), [10, 1], automatic.MATCHER_VERSION, {}, now=1000))

    def test_what_counts_as_searchable(self):
        def row(name):
            return {'path': str(self.root / 'F' / name), 'series': '', 'number': '', 'year': ''}
        import app as application
        def parsed(name):
            r = row(name)
            r['series'], r['number'], r['year'] = application.parse_name(r['path'])
            return r
        self.assertFalse(source_scheduling.nothing_can_search(parsed('Example 001 (2024).cbz'), {}))  # Metron can.
        with patch.object(pipeline_config, 'matching', return_value=False):
            self.assertTrue(source_scheduling.nothing_can_search(parsed('Example 001.cbz'), {}))  # No year, every rule off.
            self.assertTrue(source_scheduling.nothing_can_search(parsed('Example (2024).cbz'), {}))  # No number.
            self.assertFalse(source_scheduling.nothing_can_search(parsed('Example (2024).cbz'), {'Publisher': 'Coffin Comics', 'Series': 'Example', 'Number': '1'}))
            self.assertFalse(source_scheduling.nothing_can_search(parsed('Image Example (2024).cbz'), {}))  # Image catalog title search.

    def discover_one(self, name, cover_read=True):
        """One discovery pass over one comic, every source mocked to find nothing. Returns its saved record."""
        import archive_conversion, cover_tasks, local_model, metron, research, research_runtime
        from contextlib import ExitStack
        folder = self.root / 'F'
        folder.mkdir(exist_ok=True)
        path = folder / name
        path.write_bytes(b'isolated fixture')
        stat = path.stat()
        series, number, year = app.parse_name(path)
        with app.db() as con:
            con.execute('INSERT INTO comics(path,root,size,mtime,series,number,year,metadata,status,seen) VALUES(?,?,?,?,?,?,?,?,?,?)',
                        (str(path), str(folder), stat.st_size, stat.st_mtime_ns, series, number, year, '{}', 'missing', 1))
        if cover_read:
            research.save_evidence(path.resolve(), {'cover_identification': {'title': 'unreadable'}, 'cover_signature': [stat.st_size, stat.st_mtime_ns]})
        nothing = lambda *args, **kwargs: None
        patches = [patch.object(app, 'scan'), patch.object(archive_conversion, 'one', return_value=False),
                   patch.object(worker.pause_control, 'requested', return_value=False), patch.object(automatic.batch, 'progress'),
                   patch.object(research_runtime, 'reuse', return_value=None), patch.object(metron, 'token', return_value='synthetic'),
                   patch.object(metron, 'lookup', side_effect=nothing), patch.object(research, 'publisher_lookup', side_effect=nothing),
                   patch.object(research, 'resolve_leads', side_effect=nothing), patch.object(local_model, 'available', return_value=False),
                   patch.object(cover_tasks, 'enqueue'), patch.object(app, 'api', side_effect=AssertionError('no ComicVine call'))]
        import publisher_catalogs
        patches.append(patch.object(publisher_catalogs, 'lookup', side_effect=lambda *a, **k: None))
        with ExitStack() as stack:
            for item in patches:
                stack.enter_context(item)
            automatic.discover(folder)
        with app.db() as con:
            return json.loads(con.execute('SELECT value FROM discovery_records WHERE path=?', (str(path.resolve()),)).fetchone()[0])

    def test_discovery_marks_a_comic_nothing_can_search(self):
        with patch.object(pipeline_config, 'matching', side_effect=lambda name: False):
            record = self.discover_one('Example 001.cbz')  # Numbered, no year, every looser rule off.
            self.assertEqual(record['outcome'], 'needs_identity_lookup')
            self.assertEqual(record['unsearchable'], source_scheduling.search_fingerprint())  # Before: no marker.

    def test_discovery_leaves_searchable_or_unread_comics_unmarked(self):
        self.assertNotIn('unsearchable', self.discover_one('Example 002 (2024).cbz'))  # Metron can search it.
        with patch.object(pipeline_config, 'matching', side_effect=lambda name: False):
            self.assertNotIn('unsearchable', self.discover_one('Example 003.cbz', cover_read=False))  # Cover not read yet.

    def test_a_metron_miss_under_older_rules_is_asked_once_more(self):
        import metron
        old_attempt = {'result': 'no_verified_match', 'failures': 4, 'next_at': 5000}
        self.assertTrue(source_scheduling.ready('Metron', old_attempt, {}, 1000))  # Before: waited for next_at.
        current = dict(old_attempt, rules=metron.rules_stamp())
        self.assertFalse(source_scheduling.ready('Metron', current, {}, 1000))
        self.assertFalse(source_scheduling.ready('GCD', old_attempt, {}, 1000))  # Only Metron's rules changed.


if __name__ == '__main__':
    unittest.main()
