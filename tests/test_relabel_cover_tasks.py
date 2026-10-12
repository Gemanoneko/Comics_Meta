"""The one-time v0.1.2 relabel script: dry run, apply and rollback on an isolated catalog."""
import hashlib
import io
import json
import sqlite3
import unittest
from contextlib import contextmanager,redirect_stdout
from pathlib import Path
import relabel_cover_tasks as relabel
from test_worker import scratch_directory

LEGACY=relabel.LEGACY_DETAIL


@contextmanager
def database(path):
    """Commit and always close, so Windows can remove the scratch folder."""
    con=sqlite3.connect(path)
    try:
        with con:yield con
    finally:con.close()


class RelabelTests(unittest.TestCase):
    def setUp(self):
        self.data=Path(self.enterContext(scratch_directory()))/'data';self.data.mkdir()
        self.db=self.data/'catalog.sqlite'
        with database(self.db) as con:
            con.execute('PRAGMA journal_mode=WAL')
            con.execute('CREATE TABLE cover_tasks(path TEXT PRIMARY KEY, signature TEXT, state TEXT, updated REAL, detail TEXT)')
            con.executemany('INSERT INTO cover_tasks VALUES(?,?,?,?,?)',[
                ('blocked-a.cbz','[1,2]','retry_wait',1000.5,LEGACY),
                ('blocked-b.cbz','[1,2]','retry_wait',2000.25,LEGACY),
                ('failed.cbz','[1,2]','retry_wait',3000.0,'Cover search could not finish; retry after one day.'),
                ('pending.cbz','[1,2]','pending',4000.0,relabel.QUEUED_DETAIL),
                ('leads.cbz','[1,2]','leads_unverified',5000.0,LEGACY)])
            con.execute('CREATE TABLE processing_control(id INTEGER PRIMARY KEY,paused INTEGER,generation INTEGER,model_unloaded INTEGER,unload_attempt REAL,error TEXT)')
            con.execute("INSERT INTO processing_control VALUES(1,1,7,1,0,'')")
            con.execute('CREATE TABLE processing_ack(worker TEXT PRIMARY KEY,generation INTEGER,timestamp REAL)')
            con.executemany('INSERT INTO processing_ack VALUES(?,?,?)',[('metadata',7,1.0),('browser',7,1.0)])
        self.original=self.rows()

    def run_script(self,*args):
        output=io.StringIO()
        with redirect_stdout(output):code=relabel.main([*args,'--data',str(self.data)])
        return code,json.loads(output.getvalue())

    def rows(self):
        with database(self.db) as con:
            return {r[0]:r[1:] for r in con.execute('SELECT path,state,updated,detail FROM cover_tasks ORDER BY path')}

    def digest(self):
        with database(self.db) as con:return hashlib.sha256(json.dumps(list(con.iterdump())).encode()).hexdigest()

    def test_dry_run_counts_and_writes_nothing(self):
        before=self.digest()
        code,result=self.run_script()
        self.assertEqual(code,0)
        self.assertEqual(result,{'mode':'dry-run','paused':True,'to_relabel':2,'backup_rows':0,'restorable':0})
        self.assertEqual(self.digest(),before)

    def test_apply_requeues_with_the_same_queue_time_and_rollback_restores_exactly(self):
        code,result=self.run_script('--apply')
        self.assertEqual((code,result['relabeled'],result['backup_rows']),(0,2,2))
        rows=self.rows()
        self.assertEqual(rows['blocked-a.cbz'],('pending',1000.5,relabel.QUEUED_DETAIL))
        self.assertEqual(rows['blocked-b.cbz'],('pending',2000.25,relabel.QUEUED_DETAIL))
        for untouched in ('failed.cbz','pending.cbz','leads.cbz'):self.assertEqual(rows[untouched],self.original[untouched])
        self.assertEqual(self.run_script()[1]['restorable'],2)
        code,result=self.run_script('--rollback')
        self.assertEqual((code,result['restored'],result['left_as_is']),(0,2,0))
        self.assertEqual(self.rows(),self.original)
        with database(self.db) as con:
            self.assertIsNone(con.execute("SELECT 1 FROM sqlite_master WHERE name=?",(relabel.BACKUP,)).fetchone())

    def test_rollback_leaves_rows_that_moved_on(self):
        self.run_script('--apply')
        with database(self.db) as con:  # Searched after the relabel: a genuine result now.
            con.execute("UPDATE cover_tasks SET state='leads_found',updated=9999,detail='Search candidates saved; automatic identity verification pending.' WHERE path='blocked-a.cbz'")
        code,result=self.run_script('--rollback')
        self.assertEqual((result['restored'],result['left_as_is']),(1,1))
        self.assertEqual(self.rows()['blocked-a.cbz'][0],'leads_found')
        self.assertEqual(self.rows()['blocked-b.cbz'],self.original['blocked-b.cbz'])

    def test_refuses_unless_paused_and_never_stacks_backups(self):
        with database(self.db) as con:con.execute('UPDATE processing_control SET paused=0')
        code,result=self.run_script('--apply')
        self.assertEqual(code,2);self.assertIn('not paused',result['refused'])
        self.assertEqual(self.rows(),self.original)
        with database(self.db) as con:con.execute('UPDATE processing_control SET paused=1')
        self.run_script('--apply')
        code,result=self.run_script('--apply')
        self.assertEqual(code,2);self.assertIn('Roll it back first',result['refused'])

    def test_missing_catalog_is_refused_without_creating_one(self):
        output=io.StringIO()
        with redirect_stdout(output):code=relabel.main(['--data',str(self.data/'absent')])
        self.assertEqual(code,2)
        self.assertIn('No catalog',json.loads(output.getvalue())['refused'])
        self.assertFalse((self.data/'absent').exists())


if __name__=='__main__':
    unittest.main()
