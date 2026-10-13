"""#2: a folder pass keeps working after the first queued comic and writes one multi-comic plan.

Before v0.1.3 discovery returned after the first queued comic, so every write
paid for a fresh folder scan, provider status read and catalog probe. Isolated
catalog and archives; every source is mocked.
"""
import json
import unittest
import zipfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
import app
import automatic
import batch
import research
import worker
from test_worker import scratch_directory


def make_comic(path, page=b'page'):
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('001.jpg', b'cover ' + path.name.encode())
        archive.writestr('002.jpg', page * 50)
    return path


class PassPlanDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        for target, name, value in ((app, 'DATA', self.root / 'data'), (app, 'BASE', self.root),
                                    (research, 'CACHE', self.root / 'research'), (worker, 'QUEUE', self.root / 'queue')):
            self.enterContext(patch.object(target, name, value))
        self.folder = self.root / 'Example'
        self.folder.mkdir()
        self.paths = [make_comic(self.folder / ('Example %03d (2024).cbz' % i)) for i in (1, 2, 3)]

    def discover(self, synopsis=None):
        import archive_conversion, cover_tasks, getcomics, local_model, metron, open_library, providers, publisher_catalogs, research_runtime
        def lookup(row, old):
            number = Path(row['path']).stem.split()[1]
            return {'provider': 'Metron', 'metadata_version': 2, 'fields': {'Writer': 'Writer ' + number},
                    'sources': [{'url': 'https://metron.example/' + number, 'text': ('story ' + number + ' ') * 15}]}
        patches = [patch.object(archive_conversion, 'one', return_value=False), patch.object(providers, 'statuses', return_value={}),
                   patch.object(worker.pause_control, 'requested', return_value=False), patch.object(automatic.batch, 'progress'),
                   patch.object(research_runtime, 'reuse', return_value=None), patch.object(research_runtime, 'remember'),
                   patch.object(automatic, 'lookup_unidentified', return_value=None), patch.object(app, 'api', return_value=None),
                   patch.object(metron, 'token', return_value='synthetic'), patch.object(metron, 'lookup', side_effect=lookup),
                   patch.object(providers, 'gcd_lookup', return_value=None), patch.object(providers, 'google_lookup', return_value=None),
                   patch.object(open_library, 'lookup', return_value=None), patch.object(publisher_catalogs, 'lookup', return_value=None),
                   patch.object(getcomics, 'lookup', return_value=None), patch.object(research, 'publisher_lookup', return_value=None),
                   patch.object(cover_tasks, 'identified'),
                   patch.object(local_model, 'available', return_value=synopsis is not None),
                   patch.object(local_model, 'sourced_synopsis', side_effect=synopsis or (lambda sources, diagnostics: None))]
        with ExitStack() as stack:
            for item in patches:
                stack.enter_context(item)
            return automatic.discover(self.folder)

    def plans(self):
        tickets = sorted(worker.QUEUE.glob('*.json'))
        return [json.loads(Path(json.loads(t.read_text(encoding='utf-8'))['plan']).read_text(encoding='utf-8')) for t in tickets]

    def test_one_pass_queues_every_due_comic_in_one_plan_and_ticket(self):
        self.assertTrue(self.discover())
        plans = self.plans()
        self.assertEqual(len(plans), 1)  # Before: one plan and one pass per comic.
        entries = plans[0]['entries']
        self.assertEqual([Path(e['path']).name for e in entries], [p.name for p in self.paths])
        self.assertEqual([e['fields']['Writer'] for e in entries], ['Writer 001', 'Writer 002', 'Writer 003'])
        self.assertTrue(all(e['sha256'] == batch.digest(e['path']) for e in entries))

    def test_plan_size_is_bounded_and_the_folder_continues_next_pass(self):
        with patch.object(automatic, 'MAX_PLAN_ENTRIES', 2):
            self.assertTrue(self.discover())
        self.assertEqual(len(self.plans()[0]['entries']), 2)

    def test_synopsis_joins_its_own_comics_entry(self):
        def synopsis(sources, diagnostics):
            if sources[0]['url'].endswith('002'):
                return {'summary': 'Teaser for two.', 'model': 'fixture', 'sources': [sources[0]['url']]}
            return None
        self.discover(synopsis)
        entries = {Path(e['path']).name: e for e in self.plans()[0]['entries']}
        self.assertEqual(entries['Example 002 (2024).cbz']['fields']['Summary'], 'Teaser for two.')
        self.assertNotIn('Summary', entries['Example 001 (2024).cbz']['fields'])
        self.assertNotIn('Summary', entries['Example 003 (2024).cbz']['fields'])


class MultiComicApplyTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app, 'DATA', self.root / 'data'))
        self.enterContext(patch.object(app, 'BASE', self.root))
        (self.root / 'data').mkdir()
        self.enterContext(patch.object(batch.pause_control, 'requested', return_value=False))
        self.folder = self.root / 'Example'
        (self.folder / 'Subfolder').mkdir(parents=True)
        make_comic(self.folder / 'Subfolder' / 'Deeper 001.cbz')
        self.paths = [make_comic(self.folder / ('Example %03d.cbz' % i)) for i in (1, 2)]
        app.scan([str(self.folder)], recursive=False)
        self.plan = self.root / 'batch' / 'plan.json'
        self.plan.parent.mkdir()
        self.plan.write_text(json.dumps({'folder': str(self.folder), 'entries': [
            {'path': str(p), 'action': 'write', 'sha256': batch.digest(p), 'changes': {'Title': {'before': '', 'after': 'Verified ' + p.stem}},
             'fields': {'Title': 'Verified ' + p.stem}} for p in self.paths]}))

    def test_a_comic_changed_after_planning_does_not_block_the_rest_of_the_plan(self):
        make_comic(self.paths[0], page=b'changed')  # Before: the whole plan stopped for inspection.
        batch.apply(self.plan, remove_verified_backups=True)
        self.assertFalse(app.read_metadata(self.paths[0])[0].get('Title'))
        self.assertEqual(app.read_metadata(self.paths[1])[0]['Title'], 'Verified Example 002')
        skipped = json.loads((self.plan.parent / 'skipped.json').read_text())
        self.assertEqual([Path(s['path']).name for s in skipped], ['Example 001.cbz'])
        results = json.loads((self.plan.parent / 'results.json').read_text())
        self.assertEqual([Path(r['path']).name for r in results], ['Example 002.cbz'])
        self.assertTrue(all(r['metadata_readback_verified'] and r['backup_removed_after_verification'] for r in results))

    def test_entries_do_not_rewalk_the_folder_tree(self):
        real = app.scan
        calls = []
        def scan(roots, recursive=True):
            calls.append(recursive)
            return real(roots, recursive)
        with patch.object(app, 'scan', side_effect=scan):
            batch.apply(self.plan, remove_verified_backups=True)
        self.assertEqual(calls, [False])  # Only the final non-recursive repeat scan (before: 3 recursive scans).
        for path in self.paths:
            self.assertTrue(app.read_metadata(path)[0]['Title'].startswith('Verified'))

    def test_a_stale_catalog_row_is_refreshed_before_writing(self):
        with app.db() as con:
            con.execute('UPDATE comics SET mtime=1 WHERE path=?', (str(self.paths[0]),))
        batch.apply(self.plan, remove_verified_backups=True)
        self.assertEqual(app.read_metadata(self.paths[0])[0]['Title'], 'Verified Example 001')


if __name__ == '__main__':
    unittest.main()
