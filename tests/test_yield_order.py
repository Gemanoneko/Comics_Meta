"""#7 yield ordering: in-book writes, never-tried Metron-searchable comics and missing
metadata first; ComicVine only after Metron and only by an embedded issue ID.

Isolated catalog; every provider is mocked.
"""
import json
import time
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
import app
import automatic
import coverage_priority as coverage
import pipeline_config
import research
import worker
from test_worker import scratch_directory


def row(name, status='embedded', metadata=None):
    return {'path': 'Library/' + name, 'size': 10, 'mtime': 1, 'status': status, 'metadata': json.dumps(metadata or {}),
            'series': '', 'number': '', 'year': ''}


class OrderTests(unittest.TestCase):
    def test_highest_yield_comics_come_first(self):
        searchable = {'Series': 'Example', 'Number': '1', 'Year': '2024'}
        tried = row('a tried.cbz', 'missing', searchable)
        embedded_untried = row('b embedded.cbz', 'embedded', searchable)
        missing_untried = row('c missing.cbz', 'missing', searchable)
        unsearchable = row('d no year.cbz', 'missing', {'Series': 'Example', 'Number': '1'})
        in_book = row('z ready 001.cbz', 'missing')
        checked = {tried['path']: {'signature': [10, 1], 'source_schedule': {'Metron': {'result': 'no_verified_match'}}}}
        evidence = {in_book['path']: {'cover_identification': {'title': 'Ready', 'issue': '1'}, 'cover_signature': [10, 1]}}
        with patch.object(pipeline_config, 'in_book_cover', return_value=True):
            ordered = coverage.order_rows([tried, embedded_untried, missing_untried, unsearchable, in_book], checked, set(), set(),
                                          evidence=lambda path: evidence.get(path, {}))
        # Before: plain path order after the research-state keys.
        self.assertEqual([Path(r['path']).name for r in ordered],
                         ['z ready 001.cbz', 'c missing.cbz', 'b embedded.cbz', 'd no year.cbz', 'a tried.cbz'])

    def test_a_recorded_identity_conflict_is_not_ranked_as_in_book_writable(self):
        ready = row('z ready 001.cbz', 'missing')
        other = row('a other.cbz', 'missing', {'Series': 'Example', 'Number': '1', 'Year': '2024'})
        evidence = {ready['path']: {'cover_identification': {'title': 'Ready', 'issue': '1'}, 'cover_signature': [10, 1]}}
        def order(checked):
            with patch.object(pipeline_config, 'in_book_cover', return_value=True):
                ranked = coverage.order_rows([other, ready], checked, set(), set(), evidence=lambda path: evidence.get(path, {}))
            return [Path(r['path']).name for r in ranked]
        self.assertEqual(order({}), ['z ready 001.cbz', 'a other.cbz'])  # Positive control: the in-book comic first.
        self.assertEqual(order({ready['path']: {'signature': [10, 1], 'outcome': 'identity_conflict'}}),
                         ['a other.cbz', 'z ready 001.cbz'])  # The conflict blocks the in-book write.

    def test_a_changed_archive_counts_as_untried(self):
        previous = {'signature': [9, 9], 'source_schedule': {'Metron': {'result': 'no_verified_match'}}}
        self.assertTrue(coverage.metron_untried(row('x.cbz', metadata={'Series': 'X', 'Number': '1', 'Year': '2000'}), previous))


class ComicVineOrderTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        for target, name, value in ((app, 'DATA', self.root / 'data'), (app, 'BASE', self.root),
                                    (research, 'CACHE', self.root / 'research'), (worker, 'QUEUE', self.root / 'queue')):
            self.enterContext(patch.object(target, name, value))
        self.folder = self.root / 'Example'
        self.folder.mkdir()
        self.path = self.folder / 'Example 001 (2024).cbz'
        self.path.write_bytes(b'isolated fixture')
        self.calls = []

    def discover(self, old, metron_result, comicvine_issue=None):
        """One pass. `comicvine_issue` is the answer for the Web issue: a dict, or an exception to raise."""
        import archive_conversion, cover_tasks, discovery_state, getcomics, local_model, metron, open_library, providers, publisher_catalogs, research_runtime
        with app.db() as con:
            discovery_state.initialize(con)
            stat=self.path.stat()
            con.execute('INSERT INTO comics(path,root,size,mtime,series,number,year,metadata,status,seen) VALUES(?,?,?,?,?,?,?,?,?,?)',
                        (str(self.path), str(self.folder), stat.st_size, stat.st_mtime_ns, 'Example', '1', '2024', json.dumps(old), 'embedded', 1))
        def comicvine(resource, **params):
            self.calls.append('ComicVine ' + resource)
            if not resource.startswith('issue/'):
                return {}
            answer = comicvine_issue or {'id': 5, 'volume': {'name': 'Example', 'id': 9}, 'issue_number': '1', 'description': ''}
            if isinstance(answer, Exception):
                raise answer
            return answer
        def metron_lookup(row, old):
            self.calls.append('Metron')
            return metron_result
        patches = [patch.object(app, 'scan'), patch.object(archive_conversion, 'one', return_value=False),
                   patch.object(providers, 'statuses', return_value={}), patch.object(worker.pause_control, 'requested', return_value=False),
                   patch.object(automatic.batch, 'progress'), patch.object(research_runtime, 'reuse', return_value=None),
                   patch.object(research_runtime, 'remember'), patch.object(app, 'api', side_effect=comicvine),
                   patch.object(automatic, 'lookup_unidentified', side_effect=lambda row, old: self.calls.append('ComicVine search')),
                   patch.object(metron, 'token', return_value='synthetic'), patch.object(metron, 'lookup', side_effect=metron_lookup),
                   patch.object(providers, 'gcd_lookup', return_value=None), patch.object(providers, 'google_lookup', return_value=None),
                   patch.object(open_library, 'lookup', return_value=None), patch.object(publisher_catalogs, 'lookup', return_value=None),
                   patch.object(getcomics, 'lookup', return_value=None), patch.object(research, 'publisher_lookup', return_value=None),
                   patch.object(research, 'resolve_leads', return_value=None), patch.object(local_model, 'available', return_value=False),
                   patch.object(cover_tasks, 'enqueue'), patch.object(cover_tasks, 'identified')]
        with ExitStack() as stack:
            for item in patches:
                stack.enter_context(item)
            automatic.discover(self.folder)
        with app.db() as con:
            self.record = json.loads(con.execute('SELECT value FROM discovery_records').fetchone()[0])

    def planned(self):
        tickets = list(worker.QUEUE.glob('*.json')) if worker.QUEUE.exists() else []
        return [e for t in tickets for e in json.loads(Path(json.loads(t.read_text())['plan']).read_text())['entries']]

    def test_comic_without_a_comicvine_id_never_searches_comicvine(self):
        self.discover({'Series': 'Example', 'Number': '1', 'Year': '2024'}, None)
        self.assertNotIn('ComicVine search', self.calls)  # Before: a 20-second-paced ComicVine search first.
        self.assertFalse([c for c in self.calls if c.startswith('ComicVine')])
        self.assertIn('Metron', self.calls)

    WEB_ID = {'Series': 'Example', 'Number': '1', 'Year': '2024', 'Web': 'https://comicvine.gamespot.com/example/4000-5/'}
    METRON = {'provider': 'Metron', 'metadata_version': 2, 'fields': {'Writer': 'Verified writer'}, 'sources': []}

    def test_metron_answers_before_comicvine_for_a_comic_with_an_id(self):
        self.discover(self.WEB_ID, self.METRON)
        # Before v0.1.3: ComicVine first. Before the v0.1.2 rebase: ['Metron'] only, with no identity check.
        self.assertEqual(self.calls, ['Metron', 'ComicVine issue/4000-5'])  # No ComicVine volume request either.
        self.assertEqual([e['fields']['Writer'] for e in self.planned()], ['Verified writer'])

    def test_metron_answer_is_not_written_while_the_comicvine_issue_conflicts(self):
        self.discover(self.WEB_ID, self.METRON, {'id': 5, 'volume': {'name': 'Another Series', 'id': 7}, 'issue_number': '9'})
        self.assertEqual(self.planned(), [])  # Before the rebase: Writer written, the conflict never seen.
        self.assertEqual(self.record['outcome'], 'identity_conflict')
        self.assertEqual(self.record['conflict_issue']['id'], '5')

    def test_metron_answer_is_held_until_comicvine_can_answer(self):
        from provider_wait import ProviderDeferred
        self.discover(self.WEB_ID, self.METRON, ProviderDeferred('ComicVine is cooling down.', 'comicvine', time.time() + 300))
        self.assertEqual(self.planned(), [])  # Before the rebase: Writer written during the outage.
        self.assertEqual(self.record['outcome'], 'needs_identity_lookup')
        self.assertIn('Field writes held', self.record['detail'])
        self.assertEqual(research.read_evidence(self.path)['provider'], 'Metron')  # The answer is kept as evidence.

    def test_metron_answer_may_be_written_for_a_dead_comicvine_id(self):
        # v0.1.2: a dead id is an answer, not an outage; catalog providers keep their own checks.
        self.discover(self.WEB_ID, self.METRON, app.ComicVineNotFound('test: dead id'))
        self.assertEqual([e['fields']['Writer'] for e in self.planned()], ['Verified writer'])
        self.assertIn('does not exist', self.record['detail'])

    def test_comicvine_id_is_used_after_metron_finds_nothing(self):
        old = {'Series': 'Example', 'Number': '1', 'Year': '2024', 'Web': 'https://comicvine.gamespot.com/example/4000-5/'}
        self.discover(old, None)
        self.assertEqual(self.calls[:2], ['Metron', 'ComicVine issue/4000-5'])
        self.assertEqual(self.calls.count('Metron'), 1)  # The later source round does not repeat Metron.


if __name__ == '__main__':
    unittest.main()
