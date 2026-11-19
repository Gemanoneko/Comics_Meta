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
from collections import Counter
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
        self.assertEqual(plan['fills'], {'Summary': 'Lobo and Deadman team up.', 'Pages': '<Pages: 1 element(s), 1 child element(s)>'})
        # Series and Number say the same thing written another way; Genre differs. The root wins each time. The
        # nested date is never copied, listed with the rule that keeps it out.
        self.assertEqual(plan['dropped'], {
            'Series': {'nested': 'Lobo/Deadman: The Brave and the Bald', 'root': 'Lobo-Deadman - The Brave And The Bald', 'why': 'root wins'},
            'Number': {'nested': '001', 'root': '1', 'why': 'root wins'},
            'Genre': {'nested': 'Superhero', 'root': 'Humor', 'why': 'root wins'},
            'Year': {'nested': '1995', 'root': '', 'why': 'nested date never copied'},
            'Month': {'nested': '2', 'root': '', 'why': 'nested date never copied'}})
        self.assertEqual((plan['notes'], plan['nested_none']), ([], []))

    def test_rule_1_a_nested_date_is_never_copied(self):
        # Futaba F1: before, a root with no date (or only a Year) got the nested store date.
        for root in ('<ComicInfo/>', '<ComicInfo><Year>1995</Year></ComicInfo>', '<ComicInfo><Year>2024</Year></ComicInfo>'):
            with self.subTest(root=root):
                plan = tool.plan_merge(app, xml(root), xml(NESTED))
                self.assertFalse({'Year', 'Month', 'Day'} & set(plan['fills']))
                self.assertEqual(plan['dropped']['Month'], {'nested': '2', 'root': '', 'why': 'nested date never copied'})
                self.assertIn('Summary', plan['fills'])  # Everything else is merged.

    def test_rule_2_pagecount_is_never_copied(self):
        # Futaba F2. The app never writes PageCount, so it is left out, not computed.
        plan = tool.plan_merge(app, xml('<ComicInfo/>'), xml('<ComicInfo><PageCount>91</PageCount><Genre>Humor</Genre></ComicInfo>'))
        self.assertEqual((plan['fills'], plan['dropped']['PageCount']['why']), ({'Genre': 'Humor'}, 'PageCount never copied'))

    def test_rule_3_a_letter_case_twin_is_never_copied(self):
        # Futaba F3: `writer` beside a root `Writer`, or beside a nested one.
        plan = tool.plan_merge(app, xml('<ComicInfo><Writer>Greg Pak</Writer></ComicInfo>'), xml('<ComicInfo><writer>Greg Pak</writer></ComicInfo>'))
        self.assertEqual((plan['fills'], plan['dropped']['writer']['why']), ({}, 'same tag in another letter case'))
        plan = tool.plan_merge(app, xml('<ComicInfo/>'), xml('<ComicInfo><writer>A</writer><Writer>B</Writer></ComicInfo>'))
        self.assertEqual((plan['fills'], plan['dropped']['writer']['why']), ({'Writer': 'B'}, 'same tag in another letter case'))
        # Positive control: an odd tag with no twin is copied.
        self.assertEqual(tool.plan_merge(app, xml('<ComicInfo/>'), xml('<ComicInfo><Issue>4</Issue></ComicInfo>'))['fills'], {'Issue': '4'})

    def test_rule_4_a_volume_that_is_a_year_is_never_copied(self):
        # Futaba F4.
        plan = tool.plan_merge(app, xml('<ComicInfo/>'), xml('<ComicInfo><Volume>1980</Volume></ComicInfo>'))
        self.assertEqual((plan['fills'], plan['dropped']['Volume']['why']), ({}, 'Volume is a year'))
        self.assertEqual(tool.plan_merge(app, xml('<ComicInfo/>'), xml('<ComicInfo><Volume>2</Volume></ComicInfo>'))['fills'], {'Volume': '2'})

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
        self.broken = make_comic(self.library / 'Lobo' / 'Lobo-Deadman 003 (1995).cbz',  # As Ms. Tree v04 (Futaba F5).
                                 root=ROOT.replace('<Number>1<', '<Number>3<').replace('</ComicInfo>', '<Year>2022</Year><Month>10</Month></ComicInfo>'),
                                 nested=['<ComicInfo><Web>https://example.com/x/Web></ComicInfo>'])
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
                                   'Lobo-Deadman 003 (1995).cbz': 'root_and_nested', 'Busy 001.cbz': 'busy', 'Nested 001.cbz': 'nested_only', 'Plain 001.cbz': 'none',
                                   'Several 001.cbz': 'root_and_several_nested'})  # The backup folder is skipped.

    def test_the_plan_lists_fields_the_nested_entry_removed_and_zip_order(self):
        self.dry_run()
        plan = json.loads(self.report.with_suffix('.json').read_text(encoding='utf-8'))
        entries = {Path(e['path']).name: e for e in plan['entries']}
        merge = entries['Lobo-Deadman 001 (1995).cbz']
        self.assertEqual((merge['action'], list(merge['fills']), merge['remove']['name'], merge['first_in_zip']),
                         ('merge', ['Summary', 'Pages'], FOLDER + 'ComicInfo.xml', 'nested'))
        self.assertTrue(merge['root_is_last_entry'])
        renamed = entries['Lobo-Deadman 002 (1995).cbz']
        self.assertEqual((renamed['action'], renamed['notes']), ('merge', ['Number named differently']))
        with open(self.report.with_suffix('.csv'), encoding='utf-8-sig', newline='') as handle:
            rows = [r for r in csv.DictReader(handle) if r['archive'].endswith('001 (1995).cbz')]
        self.assertEqual([(r['change'], r['field']) for r in rows][:2], [('fill', 'Summary'), ('fill', 'Pages')])
        found = [(r['change'], r['field'], r['nested value'], r['root value kept']) for r in rows]
        self.assertIn(('nested value dropped (root wins)', 'Genre', 'Superhero', 'Humor'), found)
        self.assertIn(('nested value dropped (nested date never copied)', 'Year', '1995', ''), found)
        self.assertEqual({r['nested entry removed'] for r in rows}, {FOLDER + 'ComicInfo.xml'})
        report = self.report.read_text(encoding='utf-8')
        self.assertIn('| Root + one nested (this merge) | 3 |', report)
        self.assertIn('| Held (see below) | 1 |', report)
        self.assertIn('| nested date never copied | 4 | 2 |', report)  # Year and Month in 001 and 002.
        self.assertIn('--apply', report)

    def test_the_held_line_names_the_root(self):
        # Futaba F5: before, a held archive read "root: - #-, no date" although its root names the comic.
        self.dry_run()
        held = [line for line in self.report.read_text(encoding='utf-8').splitlines() if 'Lobo-Deadman 003' in line and 'unreadable' in line]
        self.assertEqual(len(held), 1)
        self.assertIn('root: Lobo-Deadman - The Brave And The Bald #3, 2022-10; nested: (unreadable)', held[0])


class Applied(Library):
    def setUp(self):
        super().setUp()
        self.addCleanup(os.environ.__setitem__, 'COMICS_META_STATE_ROOT', os.environ['COMICS_META_STATE_ROOT'])
        app.scan([str(self.library)])
        self.dry_run()

    def apply(self, out, **options):
        with patch.object(app, 'live_root', return_value=str(self.library)):
            return tool.apply(self.report.with_suffix('.json'), self.root / out, CODE, app.STATE_ROOT, **options)

    def backups(self):
        return sorted(p.name for p in self.library.rglob('*.bak'))


class ApplyTests(Applied):
    def test_apply_merges_verifies_saves_the_dropped_values_then_deletes_the_backup(self):
        with zipfile.ZipFile(self.merge) as archive:
            before = {i.filename: i.CRC for i in archive.infolist()}
            nested = archive.read(FOLDER + 'ComicInfo.xml')
        counts = self.apply('run1')
        self.assertEqual(counts, {'written': 2, 'held': 1})
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
                          ('Number', '001', '1', 'root wins'), ('Genre', 'Superhero', 'Humor', 'root wins'),
                          ('Year', '1995', '', 'nested date never copied'), ('Month', '2', '', 'nested date never copied')})
        self.assertIsNone(root.find('Year'))
        copies = {json.loads(line)['archive']: json.loads(line) for line in (out / 'removed-nested-copies.jsonl').read_text(encoding='utf-8').splitlines()}
        self.assertEqual(base64.b64decode(copies[str(self.merge)]['xml_base64']), nested)  # The whole nested copy, byte for byte.
        results = [json.loads(line) for line in (out / 'results.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual({r['backup_removed'] for r in results}, {True})
        with app.db() as con:
            rows = con.execute('SELECT h.source, l.writer FROM history h JOIN write_ledger l ON l.history_id=h.id').fetchall()
        self.assertEqual({tuple(r) for r in rows}, {('nested-comicinfo-merge', 'automatic')})  # Rule 5: not Sergei's.
        # Once more: no nested copy left, nothing written.
        self.assertEqual(self.apply('run2'), {'skipped': 2, 'held': 1})

    def test_rule_5_the_merge_is_not_recorded_as_sergeis_so_earlier_in_book_values_stay_correctable(self):
        # Before: the merge was a 'manual' write, which makes every value in the comic Sergei's, so the Title the
        # in-book tier wrote earlier could no longer be replaced by a verified source (provenance.in_book_values).
        import provenance
        with app.db() as con:
            row = dict(con.execute('SELECT * FROM comics WHERE path=?', (str(self.merge),)).fetchone())
        app.write_metadata(row, {'Title': 'From the cover'}, writer='automatic', history_source='in-book:cover',
                           remove_verified_backups=True)
        self.assertEqual(self.apply('run1'), {'written': 2, 'held': 1})
        with app.db() as con:
            row = dict(con.execute('SELECT * FROM comics WHERE path=?', (str(self.merge),)).fetchone())
            # The merged Summary is correctable too since Sergei's 2026-11-19 rule (next test).
            self.assertEqual(provenance.in_book_values(row, app.read_metadata(self.merge)[0], con),
                             {'Title': 'From the cover', 'Summary': 'Lobo and Deadman team up.'})

    def test_sergei_2026_11_19_merged_values_may_be_corrected_later_like_in_book_values(self):
        # Before: {}: the merged values counted as metadata that came with the file, never replaced.
        import automatic, provenance
        self.assertEqual(self.apply('run1'), {'written': 2, 'held': 1})

        def current():
            with app.db() as con:
                row = dict(con.execute('SELECT * FROM comics WHERE path=?', (str(self.merge),)).fetchone())
            old = app.read_metadata(self.merge)[0]
            return row, old, provenance.in_book_values(row, old)
        row, old, replaceable = current()
        self.assertEqual(replaceable, {'Summary': 'Lobo and Deadman team up.'})
        # A verified source's disagreeing Summary replaces the merged one; the root's own Genre (it came with the
        # file) and Series stay: the 2026-10-13 rule is otherwise unchanged.
        fields, changes, replaced = automatic.external_plan(
            old, {'Summary': 'A verified synopsis.', 'Genre': 'Action', 'Series': 'Lobo/Deadman'}, replaceable, True)
        self.assertEqual(fields, {'Summary': 'A verified synopsis.'})
        self.assertEqual(replaced, {'Summary': {'in_book': 'Lobo and Deadman team up.', 'external': 'A verified synopsis.'}})
        self.assertEqual(changes['Summary']['before'], 'Lobo and Deadman team up.')  # batch.apply's F22 guard.
        # Sergei's manual write afterwards makes every value in the comic his: nothing is replaceable any more.
        app.write_metadata(row, {'Writer': 'Alan Grant'}, writer='manual', remove_verified_backups=True)
        self.assertEqual(current()[2], {})

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

    def test_q1_each_archive_is_on_disk_before_its_backup_goes_whatever_engine_wrote_it(self):
        # Code review v0.6.7 Q1: verify_written can read the new archive from the OS cache. The tool flushes the
        # archive and its folder itself, so even a writer that flushes nothing (as 0.6.7's: os.replace) is safe.
        import storage
        from test_storage_durable import Disk
        disk, at_removal = Disk(), []
        real = app.remove_verified_backup

        def remove(path, backup, original):
            at_removal.append((Path(path).name, os.stat(app.filesystem_path(path)).st_ino in disk.durable))
            return real(path, backup, original)
        with patch.object(storage, 'replace_durably', os.replace), patch.object(storage.os, 'fsync', disk.fsync), \
                patch.object(app, 'remove_verified_backup', remove):
            self.assertEqual(self.apply('run1'), {'written': 2, 'held': 1})
        # Before: [(..., False), (..., False)].
        self.assertEqual(at_removal, [(self.merge.name, True), (self.renamed.name, True)])
        disk.power_cut(app.filesystem_path(self.merge))
        with zipfile.ZipFile(self.merge) as archive:
            self.assertIsNone(archive.testzip())

    def test_q1_an_archive_that_cannot_be_flushed_keeps_its_backup_and_stops_the_run(self):
        with patch.object(tool, 'make_durable', side_effect=OSError(5, 'Access is denied')):
            counts = self.apply('run1')
        self.assertEqual(counts, {'stopped': 1})
        self.assertEqual(len(self.backups()), 1)
        result = json.loads((self.root / 'run1' / 'results.jsonl').read_text(encoding='utf-8'))
        self.assertIn('could not be flushed', result['reason'])

    def test_a_backup_that_cannot_be_proven_is_kept(self):
        with patch.object(app, 'remove_verified_backup', side_effect=ValueError('Backup verification failed.')):
            counts = self.apply('run1')
        self.assertEqual(counts, {'stopped': 1})
        self.assertEqual(len(self.backups()), 1)

    def test_a_root_changed_since_the_dry_run_is_skipped(self):
        with app.db() as con:
            row = dict(con.execute('SELECT * FROM comics WHERE path=?', (str(self.merge),)).fetchone())
        app.write_metadata(row, {'Summary': 'Sergei wrote this.'}, remove_verified_backups=True)
        self.assertEqual(self.apply('run1'), {'skipped': 1, 'written': 1, 'held': 1})
        self.assertEqual(app.read_metadata(self.merge)[0]['Summary'], 'Sergei wrote this.')
        with zipfile.ZipFile(self.merge) as archive:
            self.assertIn(FOLDER + 'ComicInfo.xml', archive.namelist())  # Kept until a fresh dry run plans it.

    def test_an_engine_without_the_nested_merge_is_refused(self):
        original = self.merge.read_bytes()
        with patch.object(app, 'write_metadata', lambda row, fields, **options: None):  # As in v0.6.6 and earlier.
            with self.assertRaisesRegex(SystemExit, 'no nested merge'):
                self.apply('run1')
        self.assertEqual(self.merge.read_bytes(), original)

    def test_an_engine_that_cannot_recover_an_interrupted_write_is_refused(self):
        # 0.6.7's engine: no durable rename and no pending-write record, so an interrupted apply could not be finished.
        original, recovery = self.merge.read_bytes(), getattr(app, 'recover_interrupted_write', None)
        if recovery is not None:
            del app.recover_interrupted_write
        try:
            with self.assertRaisesRegex(SystemExit, '0.6.8'):
                self.apply('run1')
        finally:
            if recovery is not None:
                app.recover_interrupted_write = recovery
        self.assertEqual(self.merge.read_bytes(), original)

    def test_a_plan_for_another_library_is_refused(self):
        with patch.object(app, 'live_root', return_value=str(self.root / 'Elsewhere')):
            with self.assertRaises(SystemExit):
                tool.apply(self.report.with_suffix('.json'), self.root / 'run1', CODE, app.STATE_ROOT)


class Killed(BaseException):
    """The apply's process ends here (a crash, a power cut, Ctrl+C): no `except Exception` runs, as with a real stop."""


class ResumeTests(Applied):
    """Code review v0.6.7 q4: an interrupted apply can be finished or undone. Before 0.6.8 a re-run needed a new
    --out, skipped the archive that was being written (now root-only), and left its backup, the only copy of its
    dropped nested values, behind."""
    def interrupt(self, where):
        """Run the apply until it is stopped on the first archive at `where`."""
        import storage
        real_replace, real_verify, real_remove, real_durable = (storage.replace_durably, tool.verify_written,
                                                                app.remove_verified_backup, tool.make_durable)

        def replace(source, destination):
            if where == 'before rename':
                os.replace(source, str(source) + '.kept')  # A kill leaves the temporary archive on the disk.
                raise Killed()
            real_replace(source, destination)
            if where == 'after rename':
                raise Killed()

        def verify(app_, entry, backup):
            if where == 'while verifying':
                raise Killed()
            return real_verify(app_, entry, backup)

        def durable(app_, path):
            if where == 'after saving the record':
                raise Killed()
            return real_durable(app_, path)

        def remove(path, backup, original):
            real_remove(path, backup, original)
            if where == 'after deleting the backup':
                raise Killed()
        with patch.object(storage, 'replace_durably', replace), patch.object(tool, 'verify_written', verify), \
                patch.object(tool, 'make_durable', durable), patch.object(app, 'remove_verified_backup', remove), \
                self.assertRaises(Killed):
            self.apply('run1')
        temporary = self.merge.with_name(self.merge.name + '.metadata-tmp')
        if where == 'before rename':
            os.replace(str(app.filesystem_path(temporary)) + '.kept', app.filesystem_path(temporary))

    def history(self):
        with app.db() as con:
            return sorted((Path(r[0]).name, r[1], r[2]) for r in con.execute(
                'SELECT l.path, h.source, l.writer FROM history h JOIN write_ledger l ON l.history_id=h.id'))

    def dropped_rows(self):
        with open(self.root / 'run1' / 'dropped-nested-values.csv', encoding='utf-8-sig', newline='') as handle:
            return Counter(Path(r['archive']).name for r in csv.DictReader(handle))

    def assert_both_merged(self):
        self.assertEqual(self.backups(), [])
        for path in (self.merge, self.renamed):
            with zipfile.ZipFile(path) as archive:
                self.assertEqual([n for n in archive.namelist() if n.lower().endswith('comicinfo.xml')], ['ComicInfo.xml'])
            self.assertEqual(app.read_metadata(path)[0]['Summary'], 'Lobo and Deadman team up.')
        self.assertEqual(self.history(), [(self.merge.name, 'nested-comicinfo-merge', 'automatic'),
                                          (self.renamed.name, 'nested-comicinfo-merge', 'automatic')])
        self.assertEqual(self.dropped_rows(), {self.merge.name: 5, self.renamed.name: 5})  # Each archive's rows once.
        copies = [json.loads(line)['archive'] for line in (self.root / 'run1' / 'removed-nested-copies.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(sorted(copies), sorted([str(self.merge), str(self.renamed)]))
        self.assertFalse((app.DATA / 'pending-writes').exists() and any((app.DATA / 'pending-writes').iterdir()))

    def test_stopped_inside_the_write_after_its_rename_resume_records_the_history_and_finishes(self):
        self.interrupt('after rename')
        self.assertEqual(self.history(), [])  # Rewritten, nothing recorded, backup kept, no result line.
        self.assertEqual(len(self.backups()), 1)
        self.assertEqual(self.apply('run1', resume=True), {'written': 2, 'held': 1})
        self.assert_both_merged()
        results = [json.loads(line) for line in (self.root / 'run1' / 'results.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual([(Path(r['path']).name, r['outcome'], r.get('resumed', False)) for r in results],
                         [(self.merge.name, 'written', True), (self.renamed.name, 'written', False)])

    def test_stopped_before_the_rename_resume_undoes_it_then_merges_as_planned(self):
        self.interrupt('before rename')
        temporary = app.filesystem_path(self.merge.with_name(self.merge.name + '.metadata-tmp'))
        self.assertTrue(temporary.exists())
        self.assertEqual(self.apply('run1', resume=True), {'written': 2, 'held': 1})
        self.assertFalse(temporary.exists())
        self.assert_both_merged()

    def test_stopped_while_verifying_resume_finishes(self):
        self.interrupt('while verifying')
        self.assertEqual(len(self.backups()), 1)
        self.assertEqual(self.apply('run1', resume=True), {'written': 2, 'held': 1})
        self.assert_both_merged()

    def test_stopped_after_saving_the_record_resume_finishes_without_saving_it_twice(self):
        self.interrupt('after saving the record')
        self.assertEqual(self.dropped_rows(), {self.merge.name: 5})
        self.assertEqual(self.apply('run1', resume=True), {'written': 2, 'held': 1})
        self.assert_both_merged()

    def test_stopped_after_deleting_the_backup_resume_records_the_result(self):
        self.interrupt('after deleting the backup')
        self.assertEqual(self.backups(), [])
        self.assertEqual(self.apply('run1', resume=True), {'written': 2, 'held': 1})
        self.assert_both_merged()

    def test_recover_finishes_or_undoes_the_interrupted_archive_and_writes_nothing_new(self):
        self.interrupt('before rename')
        second = self.renamed.read_bytes()
        self.assertEqual(self.apply('run1', recover_only=True), {'held': 1})
        self.assertFalse(app.filesystem_path(self.merge.with_name(self.merge.name + '.metadata-tmp')).exists())
        self.assertEqual(self.backups(), [])  # Undone: the comic is the original and its backup was an exact copy.
        with zipfile.ZipFile(self.merge) as archive:
            self.assertIn(FOLDER + 'ComicInfo.xml', archive.namelist())
        self.assertEqual(self.renamed.read_bytes(), second)  # Nothing new started.
        self.assertEqual(self.apply('run1', resume=True), {'written': 2, 'held': 1})  # A later --resume carries on.
        self.assert_both_merged()

    def test_resume_refuses_after_a_stop_and_for_another_plan_or_folder(self):
        with patch.object(tool, 'verify_written', return_value='entries other than ComicInfo changed'):
            self.assertEqual(self.apply('run1'), {'stopped': 1})
        with self.assertRaisesRegex(SystemExit, 'stopped at'):
            self.apply('run1', resume=True)
        with self.assertRaisesRegex(SystemExit, 'earlier apply'):
            self.apply('elsewhere', resume=True)
        (self.root / 'run1' / 'run.json').write_text(json.dumps({'plan_sha256': '0' * 64}), encoding='utf-8')
        with self.assertRaisesRegex(SystemExit, 'another plan'):
            self.apply('run1', resume=True)
        with self.assertRaisesRegex(SystemExit, 'new or empty'):
            self.apply('run1')  # Without --resume a used folder is still refused.


if __name__ == '__main__':
    unittest.main()
