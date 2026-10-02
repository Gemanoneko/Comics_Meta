import sqlite3
import unittest
from pathlib import Path
import app


class LiveScopeTests(unittest.TestCase):
    def test_only_descendants_match_and_wildcards_are_literal(self):
        root=str(Path('library_100%').resolve())
        expected=str(Path(root)/'comic.cbz')
        paths=[expected,str(Path(root+'extra')/'other.cbz'),str(Path(root.replace('_','X').replace('%','anything'))/'other.cbz')]
        con=sqlite3.connect(':memory:')
        try:
            con.execute('CREATE TABLE comics(path TEXT)')
            con.executemany('INSERT INTO comics VALUES(?)',[(p,) for p in paths])
            scope,args=app.scope_filter(root)
            self.assertEqual([r[0] for r in con.execute('SELECT path FROM comics WHERE '+scope,args)],[expected])
        finally:
            con.close()
