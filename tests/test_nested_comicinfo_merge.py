"""tools/nested_comicinfo_merge.py: merge nested ComicInfo into the root copy, then remove it (Sergei 2026-11-18, option d).

Fill-empty (the root wins) through the app's own write path; the dry run writes nothing. Isolated catalog and library.
"""
import csv
import importlib.util
import json
import os
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from unittest.mock import patch
import app
from test_worker import scratch_directory

CODE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('nested_comicinfo_merge', CODE / 'tools' / 'nested_comicinfo_merge.py')
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

NESTED = ('<?xml version="1.0"?><ComicInfo><Series>Lobo/Deadman: The Brave and the Bald</Series><Number>001</Number>'
          '<Summary>Lobo and Deadman team up.</Summary><Genre>Superhero</Genre><Year>1995</Year><Month>2</Month>'
          '<Pages><Page Image="0" Type="FrontCover"/></Pages></ComicInfo>')
ROOT = ('<?xml version="1.0"?><ComicInfo><Series>Lobo-Deadman - The Brave And The Bald</Series><Number>1</Number>'
        '<Genre>Humor</Genre></ComicInfo>')
FOLDER = 'Lobo 001/'


def xml(value):
    return ET.fromstring(value)


def make_comic(path, root=None, nested=()):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr(FOLDER + '001.jpg', b'cover ' + path.name.encode())
        for index, value in enumerate(nested):
            archive.writestr((FOLDER if index == 0 else 'extra%d/' % index) + 'ComicInfo.xml', value)
        archive.writestr(FOLDER + '002.jpg', b'page' * 100)
        if root is not None:
            archive.writestr('ComicInfo.xml', root)
    return path


def snapshot(folder):
    return {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in sorted(folder.rglob('*')) if p.is_file()}


class PlanTests(unittest.TestCase):
    def test_fill_empty_with_the_root_winning_and_each_dropped_value_listed(self):
        fills, dropped, hold = tool.plan_merge(app, xml(ROOT), xml(NESTED))
        self.assertEqual(fills, {'Summary': 'Lobo and Deadman team up.', 'Year': '1995', 'Month': '2',
                                 'Pages': '<Pages: 1 element(s), 1 child element(s)>'})
        # Series and Number say the same thing written another way; Genre differs and the root wins.
        self.assertEqual(dropped, {'Series': 'Lobo/Deadman: The Brave and the Bald', 'Number': '001', 'Genre': 'Superhero'})
        self.assertEqual(hold, '')

    def test_a_nested_date_part_beside_a_differing_root_date_is_held(self):
        hold = tool.plan_merge(app, xml('<ComicInfo><Year>2024</Year></ComicInfo>'), xml(NESTED))[2]
        self.assertIn('date', hold)
        self.assertEqual(tool.plan_merge(app, xml('<ComicInfo><Year>1995</Year></ComicInfo>'), xml(NESTED))[2], '')
        # The date is only held when the merge would fill a part of it: here the root holds all of it.
        root = xml('<ComicInfo><Year>2024</Year><Month>11</Month></ComicInfo>')
        nested = xml('<ComicInfo><Year>2025</Year><Month>1</Month></ComicInfo>')
        self.assertEqual(tool.plan_merge(app, root, nested), ({}, {'Year': '2025', 'Month': '1'}, ''))

    def test_a_different_series_or_number_is_held(self):
        self.assertIn('Number', tool.plan_merge(app, xml('<ComicInfo><Number>2</Number></ComicInfo>'), xml(NESTED))[2])
        self.assertIn('Series', tool.plan_merge(app, xml('<ComicInfo><Series>Batman</Series></ComicInfo>'), xml(NESTED))[2])


class Library(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app, 'DATA', self.root / 'data'))
        self.library = self.root / 'Comix'
        self.merge = make_comic(self.library / 'Lobo' / 'Lobo-Deadman 001 (1995).cbz', root=ROOT, nested=[NESTED])
        self.differs = make_comic(self.library / 'Lobo' / 'Lobo-Deadman 002 (1995).cbz',
                                  root=ROOT.replace('<Number>1<', '<Number>2<'), nested=[NESTED])
        self.nested_only = make_comic(self.library / 'Other' / 'Nested 001.cbz', nested=[NESTED])
        self.plain = make_comic(self.library / 'Other' / 'Plain 001.cbz')
        self.several = make_comic(self.library / 'Other' / 'Several 001.cbz', root=ROOT, nested=[NESTED, NESTED])
        self.busy = make_comic(self.library / 'Other' / 'Busy 001.cbz', root=ROOT, nested=[NESTED])
        (self.busy.parent / (self.busy.name + '.metadata-tmp')).write_bytes(b'')
        make_comic(self.library / 'Lobo' / '.comic-metadata-backups' / 'Lobo-Deadman 001 (1995).cbz', root=ROOT, nested=[NESTED])
        self.report = self.root / 'out' / 'DryRun.md'
        self.report.parent.mkdir()

    def dry_run(self):
        return tool.dry_run(app, self.library, self.report)


class DryRunTests(Library):
    def test_the_dry_run_writes_nothing_to_the_library_or_a_catalog(self):
        before = snapshot(self.library)
        records = self.dry_run()
        self.assertEqual(snapshot(self.library), before)
        self.assertFalse((self.root / 'data').exists())  # No catalog was opened.
        layouts = {Path(r['path']).name: r['layout'] for r in records}
        self.assertEqual(layouts, {'Lobo-Deadman 001 (1995).cbz': 'root_and_nested', 'Lobo-Deadman 002 (1995).cbz': 'root_and_nested',
                                   'Busy 001.cbz': 'busy', 'Nested 001.cbz': 'nested_only', 'Plain 001.cbz': 'none',
                                   'Several 001.cbz': 'root_and_several_nested'})  # The backup folder is skipped.

    def test_the_plan_lists_fields_the_nested_entry_removed_and_zip_order(self):
        self.dry_run()
        plan = json.loads(self.report.with_suffix('.json').read_text(encoding='utf-8'))
        entries = {Path(e['path']).name: e for e in plan['entries']}
        merge = entries['Lobo-Deadman 001 (1995).cbz']
        self.assertEqual((merge['action'], list(merge['fills']), merge['remove']['name'], merge['first_in_zip']),
                         ('merge', ['Summary', 'Year', 'Month', 'Pages'], FOLDER + 'ComicInfo.xml', 'nested'))
        self.assertTrue(merge['root_is_last_entry'])
        self.assertEqual(entries['Lobo-Deadman 002 (1995).cbz']['action'], 'hold')
        with open(self.report.with_suffix('.csv'), encoding='utf-8-sig', newline='') as handle:
            rows = [r for r in csv.DictReader(handle) if r['archive'].endswith('001 (1995).cbz')]
        self.assertEqual([(r['change'], r['field']) for r in rows][:2], [('fill', 'Summary'), ('fill', 'Year')])
        self.assertIn(('nested value dropped (root wins)', 'Genre', 'Superhero'), [(r['change'], r['field'], r['value']) for r in rows])
        self.assertEqual({r['nested entry removed'] for r in rows}, {FOLDER + 'ComicInfo.xml'})
        report = self.report.read_text(encoding='utf-8')
        self.assertIn('| Root + one nested (this merge) | 2 |', report)
        self.assertIn('--apply', report)


class ApplyTests(Library):
    def setUp(self):
        super().setUp()
        self.addCleanup(os.environ.__setitem__, 'COMICS_META_STATE_ROOT', os.environ['COMICS_META_STATE_ROOT'])
        app.scan([str(self.library)])
        self.dry_run()

    def apply(self, out):
        with patch.object(app, 'live_root', return_value=str(self.library)):
            return tool.apply(self.report.with_suffix('.json'), self.root / out, CODE, app.STATE_ROOT)

    def test_apply_merges_through_the_app_write_path_and_removes_the_nested_copy(self):
        before = {i.filename: i.CRC for i in zipfile.ZipFile(self.merge).infolist()}
        counts = self.apply('run1')
        self.assertEqual(counts, {'written': 1, 'held': 1})  # The held archive is not touched.
        with zipfile.ZipFile(self.merge) as archive:
            root = app.metadata_xml(archive.read('ComicInfo.xml'))
            after = {i.filename: i.CRC for i in archive.infolist()}
        self.assertEqual(root.findtext('Summary'), 'Lobo and Deadman team up.')
        self.assertEqual(root.findtext('Genre'), 'Humor')  # The root value stays.
        self.assertEqual(root.find('Pages')[0].get('Type'), 'FrontCover')
        self.assertEqual(sorted(after), ['ComicInfo.xml', FOLDER + '001.jpg', FOLDER + '002.jpg'])
        self.assertEqual({k: v for k, v in after.items() if k != 'ComicInfo.xml'},
                         {k: v for k, v in before.items() if k in (FOLDER + '001.jpg', FOLDER + '002.jpg')})
        self.assertEqual(len(list((self.merge.parent / '.comic-metadata-backups').glob('Lobo-Deadman 001*.bak'))), 1)
        with app.db() as con:
            source, writer = con.execute('SELECT h.source, l.writer FROM history h JOIN write_ledger l ON l.history_id=h.id').fetchone()
        self.assertEqual((source, writer), ('nested-comicinfo-merge', 'manual'))
        # Once more: no nested copy left, nothing written.
        self.assertEqual(self.apply('run2'), {'skipped': 1, 'held': 1})

    def test_a_root_changed_since_the_dry_run_is_skipped(self):
        with app.db() as con:
            row = dict(con.execute('SELECT * FROM comics WHERE path=?', (str(self.merge),)).fetchone())
        app.write_metadata(row, {'Summary': 'Sergei wrote this.'}, remove_verified_backups=True)
        self.assertEqual(self.apply('run1'), {'skipped': 1, 'held': 1})
        self.assertEqual(app.read_metadata(self.merge)[0]['Summary'], 'Sergei wrote this.')
        with zipfile.ZipFile(self.merge) as archive:
            self.assertIn(FOLDER + 'ComicInfo.xml', archive.namelist())  # Kept until a fresh dry run plans it.

    def test_an_engine_without_the_nested_merge_is_refused(self):
        original = self.merge.read_bytes()
        with patch.object(app, 'write_metadata', lambda row, fields, **options: None):  # As in v0.6.6 and earlier.
            with self.assertRaisesRegex(SystemExit, 'no nested merge'):
                self.apply('run1')
        self.assertEqual(self.merge.read_bytes(), original)

    def test_a_plan_for_another_library_is_refused(self):
        with patch.object(app, 'live_root', return_value=str(self.root / 'Elsewhere')):
            with self.assertRaises(SystemExit):
                tool.apply(self.report.with_suffix('.json'), self.root / 'run1', CODE, app.STATE_ROOT)


if __name__ == '__main__':
    unittest.main()
