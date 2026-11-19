"""Nested ComicInfo, Sergei 2026-11-18 (option c).

508 archives in the library hold a ComicInfo.xml inside a folder (for example a Comixology scrape kept beside the
pages); 150 of them have no root copy. The app read only the root copy, so those comics read as having no metadata,
and its first write added a root copy that started blank and lacked the nested copy's fields (Lobo-Deadman,
SourceSwitchOn finding 1).

Now: with no root copy and exactly one nested copy, the nested copy is the comic's existing metadata; the root copy
a write adds starts from all of it, and that write removes the nested copy (option d), so one ComicInfo remains.
Several nested copies, or one that cannot be read, are ignored and kept as before. Catalog rows read before the fix
are read once more by the folder scan.

Option d for archives with a root and one nested copy: write_metadata(merge_nested=...) fills the root copy from the
nested one (fill-empty, the root wins) and removes it; the entry check allows exactly that one removal.

Isolated catalog and archives.
"""
import json
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
import app
from test_worker import scratch_directory

NESTED = ('<?xml version="1.0"?><ComicInfo><Series>Lobo/Deadman: The Brave and the Bald</Series><Number>1</Number>'
          '<Summary>Lobo and Deadman team up.</Summary><Genre>Superhero</Genre><Volume>1995</Volume></ComicInfo>')
ROOT = '<?xml version="1.0"?><ComicInfo><Series>Root Series</Series></ComicInfo>'
# A Comixology-style scrape (code review v0.6.7 q2): store dates, a PageCount, a case twin, a year as Volume, "None".
STORE_DATED = ('<?xml version="1.0"?><ComicInfo><Series>Lobo/Deadman: The Brave and the Bald</Series><Number>None</Number>'
               '<Summary>Lobo and Deadman team up.</Summary><Volume>1995</Volume><Year>2022</Year><Month>3</Month>'
               '<Day>28</Day><PageCount>91</PageCount><writer>alan grant</writer><Writer>Alan Grant</Writer></ComicInfo>')
FOLDER = 'Lobo-Deadman - The Brave and the Bald 001 (1995)/'


def make_comic(path, root=None, nested=(), raw_nested=()):
    """nested: ComicInfo texts stored inside folders, in this order; raw_nested: (name, bytes) entries as given."""
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr(FOLDER + '001.jpg', b'cover')
        archive.writestr(FOLDER + '002.jpg', b'page' * 100)
        for index, text in enumerate(nested):
            archive.writestr((FOLDER if index == 0 else 'extra%d/' % index) + 'ComicInfo.xml', text)
        for name, data in raw_nested:
            archive.writestr(name, data)
        if root is not None:
            archive.writestr('ComicInfo.xml', root)
    return path


def entries(path):
    with zipfile.ZipFile(path) as archive:
        return {i.filename: (i.CRC, i.file_size) for i in archive.infolist()}


def catalog_row(path):
    with app.db() as con:
        return dict(con.execute('SELECT * FROM comics WHERE path=?', (str(path),)).fetchone())


class Isolated(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app, 'DATA', self.root / 'data'))
        self.folder = self.root / 'Lobo'
        self.folder.mkdir()
        self.path = self.folder / 'Lobo-Deadman - The Brave and the Bald 001 (1995).cbz'


class ReadTests(Isolated):
    def test_a_single_nested_copy_is_read_when_there_is_no_root_copy(self):
        make_comic(self.path, nested=[NESTED])
        metadata, status, error = app.read_metadata(self.path)
        # Before: ({}, 'missing', '').
        self.assertEqual(status, 'embedded')
        self.assertEqual(metadata['Series'], 'Lobo/Deadman: The Brave and the Bald')
        self.assertEqual(metadata['Summary'], 'Lobo and Deadman team up.')
        self.assertEqual(error, '')

    def test_a_nested_only_none_is_blank(self):
        # Sergei 2026-11-18 (after Futaba's sample): as in the merge, a nested "None" is blank. Before, the comic read
        # Number "None" and the app looked up issue "None".
        make_comic(self.path, nested=[NESTED.replace('<Number>1</Number>', '<Number>None</Number>')])
        metadata = app.read_metadata(self.path)[0]
        self.assertNotIn('Number', metadata)
        self.assertEqual(metadata['Summary'], 'Lobo and Deadman team up.')
        app.scan([str(self.folder)], recursive=False)
        self.assertEqual(catalog_row(self.path)['number'], '1')  # The filename's number, not "None".
        app.write_metadata(catalog_row(self.path), {'Writer': 'Alan Grant'}, verify_readback=True)
        with zipfile.ZipFile(self.path) as archive:
            self.assertIsNone(app.metadata_xml(archive.read('ComicInfo.xml')).find('Number'))

    def test_a_nested_only_copy_follows_the_merges_left_out_rules(self):
        # Code review v0.6.7 q2 (Sergei's tightening ruling of 2026-11-18, as for the merge): before, a nested-only
        # copy was read whole, store dates, PageCount, case twins and a year-like Volume included.
        make_comic(self.path, nested=[STORE_DATED])
        metadata = app.read_metadata(self.path)[0]
        for tag in ('Year', 'Month', 'Day', 'PageCount', 'writer', 'Volume', 'Number'):
            self.assertNotIn(tag, metadata)
        self.assertEqual((metadata['Writer'], metadata['Summary'], metadata['Series']),
                         ('Alan Grant', 'Lobo and Deadman team up.', 'Lobo/Deadman: The Brave and the Bald'))
        # Positive control: a Volume that is a number is the comic's.
        make_comic(self.path, nested=[STORE_DATED.replace('<Volume>1995</Volume>', '<Volume>2</Volume>')])
        self.assertEqual(app.read_metadata(self.path)[0]['Volume'], '2')

    def test_the_root_copy_wins_over_a_nested_one(self):
        make_comic(self.path, root=ROOT, nested=[NESTED])
        self.assertEqual(app.read_metadata(self.path), ({'Series': 'Root Series'}, 'embedded', ''))

    def test_several_nested_copies_are_ignored(self):
        make_comic(self.path, nested=[NESTED, NESTED.replace('Superhero', 'Humor')])
        self.assertEqual(app.read_metadata(self.path), ({}, 'missing', ''))

    def test_a_nested_copy_that_cannot_be_read_is_ignored(self):
        for data in (b'<ComicInfo><Series>broken', b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><ComicInfo/>',
                     b'<?xml version="1.0"?><Other><Series>x</Series></Other>', b'x' * 2_000_001):
            with self.subTest(data=data[:30]):
                make_comic(self.path, raw_nested=[(FOLDER + 'ComicInfo.xml', data)])
                self.assertEqual(app.read_metadata(self.path), ({}, 'missing', ''))

    def test_only_a_file_named_comicinfo_xml_counts(self):
        make_comic(self.path, raw_nested=[('__MACOSX/' + FOLDER + '._ComicInfo.xml', NESTED.encode()),
                                          (FOLDER + 'ComicInfo.xml.bak', NESTED.encode())])
        self.assertEqual(app.read_metadata(self.path), ({}, 'missing', ''))
        make_comic(self.path, raw_nested=[('Folder\\ComicInfo.xml', NESTED.encode())])  # A backslash-named entry.
        self.assertEqual(app.read_metadata(self.path)[0]['Number'], '1')

    def test_a_broken_root_copy_still_raises(self):
        make_comic(self.path, root='<ComicInfo><Series>broken', nested=[NESTED])
        with self.assertRaises(Exception):
            app.read_metadata(self.path)


class WriteTests(Isolated):
    def test_the_written_root_copy_starts_from_the_nested_copy_which_it_replaces(self):
        make_comic(self.path, nested=[NESTED.replace('</ComicInfo>', '<Pages><Page Image="0" Type="FrontCover"/></Pages></ComicInfo>')])
        before = entries(self.path)
        app.scan([str(self.folder)], recursive=False)
        app.write_metadata(catalog_row(self.path), {'Series': 'Lobo/Deadman', 'Writer': 'Alan Grant', 'Number': '1'},
                           verify_readback=True)
        with zipfile.ZipFile(self.path) as archive:
            root = app.metadata_xml(archive.read('ComicInfo.xml'))
            names = archive.namelist()
        # Before: the root copy held only Series, Writer and Number, and the nested copy stayed beside it.
        self.assertEqual(root.findtext('Summary'), 'Lobo and Deadman team up.')
        self.assertEqual(root.findtext('Genre'), 'Superhero')
        self.assertEqual(root.find('Pages')[0].get('Type'), 'FrontCover')  # All of it, Pages included.
        self.assertEqual(root.findtext('Series'), 'Lobo/Deadman: The Brave and the Bald')  # Filled already: kept.
        self.assertEqual(root.findtext('Writer'), 'Alan Grant')
        # Option d: the nested copy is gone and nothing else changed, so the archive holds one ComicInfo.
        self.assertEqual([n for n in names if n.lower().endswith('comicinfo.xml')], ['ComicInfo.xml'])
        after = entries(self.path)
        self.assertEqual({k: v for k, v in after.items() if k != 'ComicInfo.xml'},
                         {k: v for k, v in before.items() if k != FOLDER + 'ComicInfo.xml'})
        metadata = app.read_metadata(self.path)[0]
        self.assertEqual(metadata['Summary'], 'Lobo and Deadman team up.')
        with app.db() as con:
            written = json.loads(con.execute('SELECT fields FROM write_ledger').fetchone()[0])
        self.assertEqual(written, {'Writer': 'Alan Grant'})  # The ledger names only what this write set.

    def test_a_nested_only_write_leaves_out_what_the_merge_leaves_out_and_saves_the_whole_copy_first(self):
        # q2: before, the app's next write (the worker's automatic ones included) moved the store date, PageCount, the
        # case twin and the year-like Volume into the root copy, and the store Year made fill-empty skip the cover date.
        make_comic(self.path, nested=[STORE_DATED])
        app.scan([str(self.folder)], recursive=False)
        backup = app.write_metadata(catalog_row(self.path), {'Year': '1995', 'Month': '2', 'Number': '1'},
                                    remove_verified_backups=True, writer='automatic', history_source='Metron')
        with zipfile.ZipFile(self.path) as archive:
            root = app.metadata_xml(archive.read('ComicInfo.xml'))
            names = archive.namelist()
        self.assertEqual([n for n in names if n.lower().endswith('comicinfo.xml')], ['ComicInfo.xml'])
        self.assertEqual((root.findtext('Year'), root.findtext('Month'), root.find('Day')), ('1995', '2', None))  # The cover date.
        for tag in ('PageCount', 'writer', 'Volume'):
            self.assertIsNone(root.find(tag), tag)
        self.assertEqual((root.findtext('Writer'), root.findtext('Number')), ('Alan Grant', '1'))
        self.assertFalse(Path(backup).exists())  # The backup went once verified ...
        records = [json.loads(line) for line in (app.DATA / 'removed-nested-copies.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len(records), 1)  # ... after the nested copy was saved whole, with what the root left out.
        import base64
        self.assertEqual(base64.b64decode(records[0]['xml_base64']).decode('utf-8'), STORE_DATED)
        self.assertEqual((records[0]['archive'], records[0]['entry']), (str(self.path), FOLDER + 'ComicInfo.xml'))
        self.assertEqual({tag: why for tag, _, why in records[0]['left_out']},
                         {'Number': 'a nested "None" is blank', 'Volume': 'Volume is a year', 'Year': 'nested date never copied',
                          'Month': 'nested date never copied', 'Day': 'nested date never copied',
                          'PageCount': 'PageCount never copied', 'writer': 'same tag in another letter case'})

    def test_a_planned_empty_field_the_nested_copy_holds_is_refused(self):
        make_comic(self.path, nested=[NESTED])
        app.scan([str(self.folder)], recursive=False)
        original = self.path.read_bytes()
        with self.assertRaises(app.ArchiveChanged):
            app.write_metadata(catalog_row(self.path), {'Summary': 'Other'}, overwrite_fields={'Summary'}, expected={'Summary': ''})
        self.assertEqual(self.path.read_bytes(), original)

    def test_with_several_nested_copies_the_root_copy_starts_blank_and_they_stay_as_before(self):
        make_comic(self.path, nested=[NESTED, NESTED.replace('Superhero', 'Humor')])
        before = entries(self.path)
        app.scan([str(self.folder)], recursive=False)
        app.write_metadata(catalog_row(self.path), {'Writer': 'Alan Grant'}, verify_readback=True)
        self.assertEqual(app.read_metadata(self.path)[0], {'Writer': 'Alan Grant'})
        self.assertEqual({k: v for k, v in entries(self.path).items() if k != 'ComicInfo.xml'}, before)

    def test_a_root_copy_write_without_a_merge_keeps_the_nested_copy(self):
        make_comic(self.path, root=ROOT, nested=[NESTED])
        before = entries(self.path)
        app.scan([str(self.folder)], recursive=False)
        app.write_metadata(catalog_row(self.path), {'Writer': 'Alan Grant'}, verify_readback=True)
        self.assertEqual({k: v for k, v in entries(self.path).items() if k != 'ComicInfo.xml'},
                         {k: v for k, v in before.items() if k != 'ComicInfo.xml'})

    def test_a_page_changed_during_the_rewrite_is_still_caught_when_the_nested_copy_goes(self):
        # Negative control for the entry check: the allowed removal does not hide any other change.
        make_comic(self.path, nested=[NESTED])
        app.scan([str(self.folder)], recursive=False)
        original = self.path.read_bytes()
        real = app.shutil.copyfileobj

        def corrupt(src, dst, length=0):
            data = src.read()
            dst.write(data[:-1] + b'X' if data.startswith(b'page') else data)
        with patch.object(app.shutil, 'copyfileobj', side_effect=corrupt):
            with self.assertRaisesRegex(ValueError, 'Archive contents changed unexpectedly'):
                app.write_metadata(catalog_row(self.path), {'Writer': 'Alan Grant'})
        self.assertIs(app.shutil.copyfileobj, real)
        self.assertEqual(self.path.read_bytes(), original)


class MergeTests(Isolated):
    """Option d for an archive with a root and exactly one nested copy (tools/nested_comicinfo_merge.py)."""

    NESTED_FULL = NESTED.replace('</ComicInfo>', '<Writer>Alan Grant</Writer><Writer>Mike Baron</Writer>'
                                 '<Pages><Page Image="0" Type="FrontCover"/></Pages></ComicInfo>')

    def merge(self, **override):
        with zipfile.ZipFile(self.path) as archive:
            info = archive.getinfo(FOLDER + 'ComicInfo.xml')
        merge = {'name': info.filename, 'crc': info.CRC, 'size': info.file_size,
                 'tags': ['Number', 'Summary', 'Genre', 'Volume', 'Writer', 'Pages']}
        merge.update(override)
        return app.write_metadata(catalog_row(self.path), {}, merge_nested=merge, writer='manual', verify_readback=True,
                                  history_source='nested-comicinfo-merge')

    def test_the_merge_fills_the_root_copy_keeps_its_values_and_removes_the_nested_copy(self):
        make_comic(self.path, root=ROOT.replace('</ComicInfo>', '<Summary> </Summary></ComicInfo>'), nested=[self.NESTED_FULL])
        before = entries(self.path)
        app.scan([str(self.folder)], recursive=False)
        backup = Path(self.merge())
        self.assertTrue(backup.exists())  # Kept.
        with zipfile.ZipFile(self.path) as archive:
            root = app.metadata_xml(archive.read('ComicInfo.xml'))
            names = archive.namelist()
        self.assertEqual(root.findtext('Series'), 'Root Series')  # Both hold one: the root wins.
        self.assertEqual(root.findtext('Summary'), 'Lobo and Deadman team up.')  # Blank in the root: filled.
        self.assertEqual([e.text for e in root.findall('Writer')], ['Alan Grant', 'Mike Baron'])  # Repeated: both.
        self.assertEqual(root.find('Pages')[0].get('Type'), 'FrontCover')
        self.assertEqual(len(root.findall('Summary')), 1)
        self.assertEqual([n for n in names if n.lower().endswith('comicinfo.xml')], ['ComicInfo.xml'])
        self.assertEqual({k: v for k, v in entries(self.path).items() if k != 'ComicInfo.xml'},
                         {k: v for k, v in before.items() if k.lower() not in ('comicinfo.xml', (FOLDER + 'ComicInfo.xml').lower())})
        with app.db() as con:
            source, writer, fields = con.execute('SELECT h.source, l.writer, l.fields FROM history h JOIN write_ledger l ON l.history_id=h.id').fetchone()
        self.assertEqual((source, writer), ('nested-comicinfo-merge', 'manual'))  # The writer is the caller's choice.
        # Volume 1995 is a year, so it is not copied (Futaba F4).
        self.assertEqual(json.loads(fields), {'Number': '1', 'Summary': 'Lobo and Deadman team up.', 'Genre': 'Superhero'})

    def test_r2_a_merge_saves_the_whole_nested_copy_and_its_dropped_values_before_the_rename(self):
        # Code review v0.6.8 R2: the tool saved them only after its checks passed, so a stopped or interrupted merge
        # left them only in the backup. The writer now saves them before the rename, as for a nested-only copy.
        import storage
        make_comic(self.path, root=ROOT.replace('</ComicInfo>', '<Genre>Humor</Genre></ComicInfo>'), nested=[self.NESTED_FULL])
        with zipfile.ZipFile(self.path) as archive:
            raw = archive.read(FOLDER + 'ComicInfo.xml')
        app.scan([str(self.folder)], recursive=False)
        seen = []

        def stopped(source, destination):
            seen.append((app.DATA / 'removed-nested-copies.jsonl').exists())  # On the disk before the rename?
            raise KeyboardInterrupt()  # The process stops at the rename.
        with patch.object(storage, 'replace_durably', stopped), self.assertRaises(KeyboardInterrupt):
            self.merge(tags=['Number', 'Summary', 'Volume', 'Writer', 'Pages'])
        self.assertEqual(seen, [True])  # Before: [False]; nothing was saved by the writer at all.
        records = [json.loads(line) for line in (app.DATA / 'removed-nested-copies.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len(records), 1)
        import base64
        self.assertEqual(base64.b64decode(records[0]['xml_base64']), raw)  # The whole nested copy, byte for byte.
        self.assertEqual((records[0]['kind'], records[0]['entry']), ('merge', FOLDER + 'ComicInfo.xml'))
        self.assertEqual({row[0]: row[1:] for row in records[0]['left_out']},
                         {'Series': ['Lobo/Deadman: The Brave and the Bald', 'root wins', 'Root Series'],
                          'Genre': ['Superhero', 'root wins', 'Humor'], 'Volume': ['1995', 'Volume is a year', '']})

    def test_a_nested_none_is_blank(self):
        # Sergei 2026-11-18: some scrapers write the text "None" for a missing value.
        make_comic(self.path, root='<ComicInfo><Series>Root Series</Series></ComicInfo>',
                   nested=[NESTED.replace('<Number>1</Number>', '<Number>None</Number>')])
        app.scan([str(self.folder)], recursive=False)
        self.merge(tags=['Summary', 'Genre'])  # Before: Number "None" was filled, outside the plan.
        self.assertNotIn('Number', app.read_metadata(self.path)[0])

    def merged(self, root, nested, tags):
        """The root copy after a merge of `nested` into `root`, planned for `tags`."""
        make_comic(self.path, root=root, nested=[nested])
        app.scan([str(self.folder)], recursive=False)
        self.merge(tags=tags)
        with zipfile.ZipFile(self.path) as archive:
            self.assertEqual([n for n in archive.namelist() if n.lower().endswith('comicinfo.xml')], ['ComicInfo.xml'])
            return app.metadata_xml(archive.read('ComicInfo.xml'))

    def test_nested_dates_are_never_copied_even_into_a_root_with_no_date(self):
        # Futaba F1, Sergei 2026-11-18: nested dates are store dates; the app fills cover dates later.
        root = self.merged('<ComicInfo><Series>Root Series</Series></ComicInfo>',
                           NESTED.replace('</ComicInfo>', '<Year>2022</Year><Month>6</Month><Day>28</Day></ComicInfo>'),
                           ['Number', 'Summary', 'Genre'])  # Before: Year, Month and Day were filled, outside the plan.
        self.assertEqual([root.find(p) for p in ('Year', 'Month', 'Day')], [None, None, None])
        self.assertEqual(root.findtext('Summary'), 'Lobo and Deadman team up.')

    def test_nested_pagecount_is_never_copied(self):
        # Futaba F2: the nested count often disagrees with the archive; the app never writes PageCount.
        root = self.merged('<ComicInfo><Series>Root Series</Series></ComicInfo>',
                           NESTED.replace('</ComicInfo>', '<PageCount>91</PageCount></ComicInfo>'), ['Number', 'Summary', 'Genre'])
        self.assertIsNone(root.find('PageCount'))

    def test_a_letter_case_twin_is_never_copied(self):
        # Futaba F3: `writer` beside a `Writer` in the root or in the nested copy.
        root = self.merged('<ComicInfo><Series>Root Series</Series><Writer>Alan Grant</Writer></ComicInfo>',
                           NESTED.replace('</ComicInfo>', '<writer>Alan Grant</writer></ComicInfo>'), ['Number', 'Summary', 'Genre'])
        self.assertEqual([e.tag for e in root if e.tag.lower() == 'writer'], ['Writer'])
        root = self.merged('<ComicInfo><Series>Root Series</Series></ComicInfo>',
                           NESTED.replace('</ComicInfo>', '<writer>A</writer><Writer>Alan Grant</Writer></ComicInfo>'),
                           ['Number', 'Summary', 'Genre', 'Writer'])  # The schema's spelling is kept.
        self.assertEqual([(e.tag, e.text) for e in root if e.tag.lower() == 'writer'], [('Writer', 'Alan Grant')])
        # Positive control: an odd tag with no twin is copied as it is.
        root = self.merged('<ComicInfo><Series>Root Series</Series></ComicInfo>',
                           NESTED.replace('</ComicInfo>', '<Artist>Ernie Chan</Artist></ComicInfo>'), ['Number', 'Summary', 'Genre', 'Artist'])
        self.assertEqual(root.findtext('Artist'), 'Ernie Chan')

    def test_a_nested_volume_that_is_a_year_is_never_copied(self):
        # Futaba F4: the app's Volume is the volume number.
        root = self.merged('<ComicInfo><Series>Root Series</Series></ComicInfo>', NESTED, ['Number', 'Summary', 'Genre'])
        self.assertIsNone(root.find('Volume'))  # Before: Volume 1995 was filled, outside the plan.
        root = self.merged('<ComicInfo><Series>Root Series</Series></ComicInfo>', NESTED.replace('<Volume>1995<', '<Volume>2<'),
                           ['Number', 'Summary', 'Genre', 'Volume'])
        self.assertEqual(root.findtext('Volume'), '2')  # Positive control: a volume number is copied.

    def test_a_nested_copy_changed_since_planning_is_refused_before_any_backup(self):
        make_comic(self.path, root=ROOT, nested=[NESTED])
        app.scan([str(self.folder)], recursive=False)
        original = self.path.read_bytes()
        for override in ({'crc': 1}, {'size': 1}, {'name': 'Other/ComicInfo.xml'}):
            with self.subTest(override=override), self.assertRaises(app.ArchiveChanged):
                self.merge(**override)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertFalse((self.folder / '.comic-metadata-backups').exists())

    def test_a_merge_that_would_fill_an_unplanned_field_is_refused(self):
        make_comic(self.path, root=ROOT, nested=[NESTED])
        app.scan([str(self.folder)], recursive=False)
        original = self.path.read_bytes()
        with self.assertRaisesRegex(app.ArchiveChanged, 'not planned \\(Genre\\)'):
            self.merge(tags=['Number', 'Summary'])
        self.assertEqual(self.path.read_bytes(), original)

    def test_several_nested_copies_or_no_root_copy_are_refused(self):
        for layout in ({'root': ROOT, 'nested': [NESTED, NESTED]}, {'nested': [NESTED]}):
            with self.subTest(layout=list(layout)):
                make_comic(self.path, **layout)
                app.scan([str(self.folder)], recursive=False)
                with self.assertRaises(app.ArchiveChanged):
                    self.merge()


class CatalogTests(Isolated):
    def scan_with_old_reader(self):
        """The catalog as the app before the fix left it: the comic read as having no ComicInfo."""
        with patch.object(app, 'nested_comicinfo', return_value=False):
            app.scan([str(self.folder)], recursive=False)
        with app.db() as con:  # This catalog was created by the fixed app, so the once-only queue ran empty.
            self.assertIsNone(con.execute('SELECT 1 FROM nested_recheck').fetchone())
            con.execute('DELETE FROM catalog_migrations WHERE name=?', ('nested-comicinfo-recheck-v067',))
            con.commit()
        self.assertEqual(catalog_row(self.path)['status'], 'missing')

    def test_an_unchanged_row_read_before_the_fix_is_read_once_more(self):
        make_comic(self.path, nested=[NESTED])
        self.scan_with_old_reader()
        app.scan([str(self.folder)], recursive=False)
        row = catalog_row(self.path)
        # Before: still 'missing' with no metadata, because the scan reads only changed files.
        self.assertEqual(row['status'], 'embedded')
        self.assertEqual(json.loads(row['metadata'])['Summary'], 'Lobo and Deadman team up.')
        self.assertEqual(row['series'], 'Lobo/Deadman: The Brave and the Bald')
        with app.db() as con:
            self.assertIsNone(con.execute('SELECT 1 FROM nested_recheck').fetchone())
        with patch.object(app, 'read_metadata', side_effect=AssertionError('read again')):
            app.scan([str(self.folder)], recursive=False)  # Unchanged and no longer queued: not read again.

    def test_a_row_with_no_comicinfo_at_all_leaves_the_queue_unchanged(self):
        make_comic(self.path)
        self.scan_with_old_reader()
        before = catalog_row(self.path)
        app.scan([str(self.folder)], recursive=False)
        after = catalog_row(self.path)
        self.assertEqual({k: after[k] for k in ('status', 'metadata', 'size', 'mtime', 'error')},
                         {k: before[k] for k in ('status', 'metadata', 'size', 'mtime', 'error')})
        with app.db() as con:
            self.assertIsNone(con.execute('SELECT 1 FROM nested_recheck').fetchone())

    def test_a_read_failure_keeps_the_row_and_its_place_in_the_queue(self):
        make_comic(self.path, nested=[NESTED])
        self.scan_with_old_reader()
        with patch.object(app, 'read_metadata', side_effect=PermissionError('in use')):
            app.scan([str(self.folder)], recursive=False)
        row = catalog_row(self.path)
        self.assertEqual((row['status'], row['error']), ('missing', ''))  # Not turned into an error.
        app.scan([str(self.folder)], recursive=False)
        self.assertEqual(catalog_row(self.path)['status'], 'embedded')

    def test_rows_read_after_the_fix_are_not_queued(self):
        make_comic(self.path)
        app.scan([str(self.folder)], recursive=False)
        with app.db() as con:
            self.assertIsNone(con.execute('SELECT 1 FROM nested_recheck').fetchone())


if __name__ == '__main__':
    unittest.main()
