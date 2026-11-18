"""tools/nested_comicinfo_merge.py: merge nested ComicInfo into the root copy, then remove it (Sergei 2026-11-18, option d).

Fill-empty (the root wins) through the app's own write path; the dry run writes nothing. Sergei's rulings: copies that
name a different Series or Number are merged; a nested "None" is blank; where a nested date part would sit beside a
root date that differs, the nested date is left out; each backup is deleted once its archive is re-read and verified,
after the dropped nested values and the whole nested copy are saved. Isolated catalog and library.
"""
import base64
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
        plan = tool.plan_merge(app, xml(ROOT), xml(NESTED))
        self.assertEqual(plan['fills'], {'Summary': 'Lobo and Deadman team up.', 'Year': '1995', 'Month': '2',
                                         'Pages': '<Pages: 1 element(s), 1 child element(s)>'})
        # Series and Number say the same thing written another way; Genre differs. The root wins each time.
        self.assertEqual(plan['dropped'], {
            'Series': {'nested': 'Lobo/Deadman: The Brave and the Bald', 'root': 'Lobo-Deadman - The Brave And The Bald', 'why': 'root wins'},
            'Number': {'nested': '001', 'root': '1', 'why': 'root wins'},
            'Genre': {'nested': 'Superhero', 'root': 'Humor', 'why': 'root wins'}})
        self.assertEqual((plan['skip'], plan['notes'], plan['nested_none']), ([], [], []))

    def test_a_nested_date_beside_a_differing_root_date_is_left_out(self):
        plan = tool.plan_merge(app, xml('<ComicInfo><Year>2024</Year></ComicInfo>'), xml(NESTED))
        self.assertEqual(plan['skip'], ['Year', 'Month', 'Day'])
        self.assertNotIn('Month', plan['fills'])  # Before (hold rule): the archive was held; plain fill-empty adds Month 2.
        self.assertEqual(plan['dropped']['Year'], {'nested': '1995', 'root': '2024', 'why': 'root date stays'})
        self.assertEqual(plan['dropped']['Month'], {'nested': '2', 'root': '', 'why': 'root date stays'})
        self.assertIn('Summary', plan['fills'])  # Everything else is merged.
        # The same year: the month joins it, nothing is left out.
        plan = tool.plan_merge(app, xml('<ComicInfo><Year>1995</Year></ComicInfo>'), xml(NESTED))
        self.assertEqual((plan['skip'], plan['fills']['Month']), ([], '2'))
        # The root holds the whole date: nothing would be filled, so nothing is skipped; the root wins.
        plan = tool.plan_merge(app, xml('<ComicInfo><Year>2024</Year><Month>11</Month></ComicInfo>'),
                               xml('<ComicInfo><Year>2025</Year><Month>1</Month></ComicInfo>'))
        self.assertEqual((plan['fills'], plan['skip'], sorted(plan['dropped'])), ({}, [], ['Month', 'Year']))

    def test_a_different_series_or_number_is_merged_and_noted(self):
        plan = tool.plan_merge(app, xml('<ComicInfo><Series>Batman</Series><Number>2</Number></ComicInfo>'), xml(NESTED))
        self.assertEqual(plan['notes'], ['Series named differently', 'Number named differently'])
        self.assertIn('Summary', plan['fills'])
        self.assertEqual(plan['dropped']['Number']['root'], '2')

    def test_a_nested_none_is_blank(self):
        plan = tool.plan_merge(app, xml('<ComicInfo><Number>1</Number></ComicInfo>'),
                               xml('<ComicInfo><Number>None</Number><Title>None</Title><Genre>Humor</Genre></ComicInfo>'))
        self.assertEqual((plan['fills'], plan['dropped'], plan['notes']), ({'Genre': 'Humor'}, {}, []))
        self.assertEqual(plan['nested_none'], ['Number', 'Title'])


class Library(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app, 'DATA', self.root / 'data'))
        self.library = self.root / 'Comix'
        self.merge = make_comic(self.library / 'Lobo' / 'Lobo-Deadman 001 (1995).cbz', root=ROOT, nested=[NESTED])
        self.renamed = make_comic(self.library / 'Lobo' / 'Lobo-Deadman 002 (1995).cbz',
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
        renamed = entries['Lobo-Deadman 002 (1995).cbz']
        self.assertEqual((renamed['action'], renamed['notes']), ('merge', ['Number named differently']))  # Before: held.
        with open(self.report.with_suffix('.csv'), encoding='utf-8-sig', newline='') as handle:
            rows = [r for r in csv.DictReader(handle) if r['archive'].endswith('001 (1995).cbz')]
        self.assertEqual([(r['change'], r['field']) for r in rows][:2], [('fill', 'Summary'), ('fill', 'Year')])
        self.assertIn(('nested value dropped (root wins)', 'Genre', 'Superhero', 'Humor'),
                      [(r['change'], r['field'], r['nested value'], r['root value kept']) for r in rows])
        self.assertEqual({r['nested entry removed'] for r in rows}, {FOLDER + 'ComicInfo.xml'})
        report = self.report.read_text(encoding='utf-8')
        self.assertIn('| Root + one nested (this merge) | 2 |', report)
        self.assertIn('| Held (see below) | 0 |', report)
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

    def backups(self):
        return sorted(p.name for p in self.library.rglob('*.bak'))

    def test_apply_merges_verifies_saves_the_dropped_values_then_deletes_the_backup(self):
        with zipfile.ZipFile(self.merge) as archive:
            before = {i.filename: i.CRC for i in archive.infolist()}
            nested = archive.read(FOLDER + 'ComicInfo.xml')
        counts = self.apply('run1')
        self.assertEqual(counts, {'written': 2})  # Before: the second (Number named differently) was held.
        with zipfile.ZipFile(self.merge) as archive:
            root = app.metadata_xml(archive.read('ComicInfo.xml'))
            after = {i.filename: i.CRC for i in archive.infolist()}
        self.assertEqual(root.findtext('Summary'), 'Lobo and Deadman team up.')
        self.assertEqual(root.findtext('Genre'), 'Humor')  # The root value stays.
        self.assertEqual(root.find('Pages')[0].get('Type'), 'FrontCover')
        self.assertEqual(sorted(after), ['ComicInfo.xml', FOLDER + '001.jpg', FOLDER + '002.jpg'])
        self.assertEqual({k: v for k, v in after.items() if k != 'ComicInfo.xml'},
                         {k: v for k, v in before.items() if k in (FOLDER + '001.jpg', FOLDER + '002.jpg')})
        self.assertEqual(self.backups(), [])  # Sergei: each backup goes once its archive is verified.
        out = self.root / 'run1'
        with open(out / 'dropped-nested-values.csv', encoding='utf-8-sig', newline='') as handle:
            dropped = [r for r in csv.DictReader(handle) if r['archive'] == str(self.merge)]
        self.assertEqual({(r['field'], r['nested value'], r['root value kept'], r['why']) for r in dropped},
                         {('Series', 'Lobo/Deadman: The Brave and the Bald', 'Lobo-Deadman - The Brave And The Bald', 'root wins'),
                          ('Number', '001', '1', 'root wins'), ('Genre', 'Superhero', 'Humor', 'root wins')})
        copies = {json.loads(line)['archive']: json.loads(line) for line in (out / 'removed-nested-copies.jsonl').read_text(encoding='utf-8').splitlines()}
        self.assertEqual(base64.b64decode(copies[str(self.merge)]['xml_base64']), nested)  # The whole nested copy, byte for byte.
        results = [json.loads(line) for line in (out / 'results.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual({r['backup_removed'] for r in results}, {True})
        with app.db() as con:
            rows = con.execute('SELECT h.source, l.writer FROM history h JOIN write_ledger l ON l.history_id=h.id').fetchall()
        self.assertEqual({tuple(r) for r in rows}, {('nested-comicinfo-merge', 'manual')})
        # Once more: no nested copy left, nothing written.
        self.assertEqual(self.apply('run2'), {'skipped': 2})

    def test_a_failed_check_keeps_the_backup_saves_nothing_and_stops_the_run(self):
        # Negative control for the delete gate: a written archive that does not pass is never left without its backup.
        with patch.object(tool, 'verify_written', return_value='entries other than ComicInfo changed'):
            counts = self.apply('run1')
        self.assertEqual(counts, {'stopped': 1})  # The second archive was not touched.
        self.assertEqual(len(self.backups()), 1)
        self.assertFalse((self.root / 'run1' / 'dropped-nested-values.csv').exists())
        with zipfile.ZipFile(self.renamed) as archive:
            self.assertIn(FOLDER + 'ComicInfo.xml', archive.namelist())

    def test_the_check_catches_a_changed_page_and_a_missing_merged_value(self):
        plan = json.loads(self.report.with_suffix('.json').read_text(encoding='utf-8'))
        entry = next(e for e in plan['entries'] if e['path'] == str(self.merge))
        with app.db() as con:
            row = dict(con.execute('SELECT * FROM comics WHERE path=?', (str(self.merge),)).fetchone())
        backup = app.write_metadata(row, {}, merge_nested=dict(entry['remove'], tags=list(entry['fills'])), writer='manual')
        self.assertIsNone(tool.verify_written(app, entry, backup))  # Positive control: the real write passes.
        self.assertIn('merged value', tool.verify_written(app, dict(entry, fills=dict(entry['fills'], Genre='x')), backup))
        with zipfile.ZipFile(self.merge) as archive:
            members = [(i.filename, archive.read(i.filename)) for i in archive.infolist()]
        with zipfile.ZipFile(self.merge, 'w') as archive:
            for name, data in members:
                archive.writestr(name, data[:-1] + b'X' if name.endswith('002.jpg') else data)
        self.assertEqual(tool.verify_written(app, entry, backup), 'entries other than ComicInfo changed')

    def test_a_backup_that_cannot_be_proven_is_kept(self):
        with patch.object(app, 'remove_verified_backup', side_effect=ValueError('Backup verification failed.')):
            counts = self.apply('run1')
        self.assertEqual(counts, {'stopped': 1})
        self.assertEqual(len(self.backups()), 1)

    def test_a_root_changed_since_the_dry_run_is_skipped(self):
        with app.db() as con:
            row = dict(con.execute('SELECT * FROM comics WHERE path=?', (str(self.merge),)).fetchone())
        app.write_metadata(row, {'Summary': 'Sergei wrote this.'}, remove_verified_backups=True)
        self.assertEqual(self.apply('run1'), {'skipped': 1, 'written': 1})
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
