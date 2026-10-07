import unittest
import sqlite3
import json
from pathlib import Path
from contextlib import closing
import app


class InventoryTotalsTests(unittest.TestCase):
    def test_live_totals_exclude_missing_paths_and_do_not_count_existing_metadata_as_app_writes(self):
        result = app.inventory_totals({'tagged': 4, 'embedded': 9, 'missing': 5,
                                       'absent': 30, 'corrupted': 2, 'unsupported': 3, 'error': 1})
        self.assertEqual(result, {'total': 24, 'updated': 4, 'corrupted': 2, 'conversion': 3})

    def test_empty_inventory_has_zero_counters(self):
        self.assertEqual(app.inventory_totals({}), {'total': 0, 'updated': 0, 'corrupted': 0, 'conversion': 0})

    def test_coverage_requires_both_fields_and_synopsis_within_live_scope(self):
        root = str(Path('library').resolve())
        with closing(sqlite3.connect(':memory:')) as con:
            con.execute('CREATE TABLE comics(path TEXT,metadata TEXT,status TEXT)')
            rows = [('embedded', {'Title': 'Existing', 'Summary': 'Premise'}),
                    ('tagged', {'Series': 'Updated', 'Summary': 'Premise'}),
                    ('embedded', {'Summary': 'Only synopsis'}),
                    ('tagged', {'Title': 'No synopsis'}),
                    ('absent', {'Title': 'Gone', 'Summary': 'Premise'}),
                    ('embedded', {'Title': '  ', 'Summary': '  '})]
            con.executemany('INSERT INTO comics VALUES(?,?,?)',
                [(str(Path(root)/str(i)), json.dumps(m), status) for i,(status,m) in enumerate(rows)])
            con.execute('INSERT INTO comics VALUES(?,?,?)',
                        (str(Path(root+'other')/'outside'),json.dumps({'Title':'Other','Summary':'Premise'}),'embedded'))
            self.assertEqual(app.metadata_present_count(con, root), 2)
