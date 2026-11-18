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
        self.assertEqual((source, writer), ('nested-comicinfo-merge', 'manual'))
        self.assertEqual(json.loads(fields), {'Number': '1', 'Summary': 'Lobo and Deadman team up.', 'Genre': 'Superhero', 'Volume': '1995'})

    def test_a_nested_none_is_blank(self):
        # Sergei 2026-11-18: some scrapers write the text "None" for a missing value.
        make_comic(self.path, root='<ComicInfo><Series>Root Series</Series></ComicInfo>',
                   nested=[NESTED.replace('<Number>1</Number>', '<Number>None</Number>')])
        app.scan([str(self.folder)], recursive=False)
        self.merge(tags=['Summary', 'Genre', 'Volume'])  # Before: Number "None" was filled, outside the plan.
        self.assertNotIn('Number', app.read_metadata(self.path)[0])

    def test_skipped_tags_are_not_filled_and_the_nested_copy_still_goes(self):
        # Sergei 2026-11-18: where the nested date would sit beside a different root date, the root date stays.
        make_comic(self.path, root='<ComicInfo><Series>Root Series</Series><Year>1980</Year><Month>3</Month></ComicInfo>',
                   nested=[NESTED.replace('</ComicInfo>', '<Year>2022</Year><Month>6</Month><Day>28</Day></ComicInfo>')])
        app.scan([str(self.folder)], recursive=False)
        self.merge(tags=['Number', 'Summary', 'Genre', 'Volume'], skip=['Year', 'Month', 'Day'])
        metadata = app.read_metadata(self.path)[0]
        self.assertEqual((metadata['Year'], metadata['Month'], metadata.get('Day')), ('1980', '3', None))
        self.assertEqual(metadata['Summary'], 'Lobo and Deadman team up.')
        with zipfile.ZipFile(self.path) as archive:
            self.assertEqual([n for n in archive.namelist() if n.lower().endswith('comicinfo.xml')], ['ComicInfo.xml'])
        # Positive control: without the skip the same merge would fill Day, which the plan does not list.
        make_comic(self.path, root='<ComicInfo><Series>Root Series</Series><Year>1980</Year><Month>3</Month></ComicInfo>',
                   nested=[NESTED.replace('</ComicInfo>', '<Year>2022</Year><Month>6</Month><Day>28</Day></ComicInfo>')])
        app.scan([str(self.folder)], recursive=False)
        with self.assertRaisesRegex(app.ArchiveChanged, 'not planned \\(Day\\)'):
            self.merge(tags=['Number', 'Summary', 'Genre', 'Volume'])

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
        with self.assertRaisesRegex(app.ArchiveChanged, 'not planned \\(Volume\\)'):
            self.merge(tags=['Number', 'Summary', 'Genre'])
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
