"""Nested ComicInfo, Sergei 2026-11-18 (option c).

508 archives in the library hold a ComicInfo.xml inside a folder (for example a Comixology scrape kept beside the
pages); 150 of them have no root copy. The app read only the root copy, so those comics read as having no metadata,
and its first write added a root copy that started blank and lacked the nested copy's fields (Lobo-Deadman,
SourceSwitchOn finding 1).

Now: with no root copy and exactly one nested copy, the nested copy is the comic's existing metadata; the root copy
a write adds starts from it, and the nested copy is never changed. Several nested copies, or one that cannot be read,
are ignored as before. Catalog rows read before the fix are read once more by the folder scan.

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
    def test_the_written_root_copy_starts_from_the_nested_copy_and_leaves_it_unchanged(self):
        make_comic(self.path, nested=[NESTED])
        before = entries(self.path)
        app.scan([str(self.folder)], recursive=False)
        app.write_metadata(catalog_row(self.path), {'Series': 'Lobo/Deadman', 'Writer': 'Alan Grant', 'Number': '1'},
                           verify_readback=True)
        with zipfile.ZipFile(self.path) as archive:
            root = app.metadata_xml(archive.read('ComicInfo.xml'))
            nested = archive.read(FOLDER + 'ComicInfo.xml').decode()
        # Before: the root copy held only Series, Writer and Number.
        self.assertEqual(root.findtext('Summary'), 'Lobo and Deadman team up.')
        self.assertEqual(root.findtext('Genre'), 'Superhero')
        self.assertEqual(root.findtext('Series'), 'Lobo/Deadman: The Brave and the Bald')  # Filled already: kept.
        self.assertEqual(root.findtext('Writer'), 'Alan Grant')
        self.assertEqual(nested, NESTED)
        after = entries(self.path)
        self.assertEqual({k: v for k, v in after.items() if k != 'ComicInfo.xml'}, before)
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

    def test_with_several_nested_copies_the_root_copy_starts_blank_as_before(self):
        make_comic(self.path, nested=[NESTED, NESTED.replace('Superhero', 'Humor')])
        before = entries(self.path)
        app.scan([str(self.folder)], recursive=False)
        app.write_metadata(catalog_row(self.path), {'Writer': 'Alan Grant'}, verify_readback=True)
        self.assertEqual(app.read_metadata(self.path)[0], {'Writer': 'Alan Grant'})
        self.assertEqual({k: v for k, v in entries(self.path).items() if k != 'ComicInfo.xml'}, before)


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
