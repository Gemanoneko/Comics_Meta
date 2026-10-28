"""Offline dump lifecycle, exact matching and scheduling against synthetic databases."""
import json
import sqlite3
import threading
import unittest
import zipfile
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
import app
import gcd_index
import gcd_offline as gcd
import source_scheduling
from test_worker import scratch_directory


class GcdTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app,'DATA',self.root/'data'))
        gcd._current_cache=(None,None)
        gcd._cancel.clear()

    def dump(self,date='2026-10-16'):
        path=self.root/(date+'.db')
        with closing(sqlite3.connect(path)) as con, con:
            for table,columns in gcd.SCHEMA.items():
                con.execute('CREATE TABLE '+table+' ('+', '.join(c+(' INTEGER' if c=='id' or c.endswith('_id') or c in ('deleted','year_began','year_ended','issue_count','is_singleton') else ' TEXT') for c in columns.split())+')')
            con.execute("INSERT INTO gcd_publisher VALUES(1,'Dark Horse')")
            con.execute("INSERT INTO stddata_language VALUES(1,'en')")
            con.execute("INSERT INTO stddata_country VALUES(1,'us')")
            con.execute("INSERT INTO gcd_series_publication_type VALUES(1,'comic book')")
            con.execute("INSERT INTO gcd_series VALUES(1,'The Example','Example',2024,2024,1,1,1,12,1,'comic book',0,0)")
            con.execute("INSERT INTO gcd_issue(id,series_id,number,key_date,on_sale_date,title,barcode,valid_isbn,deleted) VALUES(1,1,'1','2024-01-01','2024-01-01','Issue title','123456789012','',0)")
            con.execute("INSERT INTO gcd_story(id,issue_id,type_id,script,synopsis,sequence_number,deleted) VALUES(1,1,19,'Writer Name','An independently reviewed story source.',1,0)")
        return path

    def build(self,path):
        index=self.root/'index.sqlite'
        gcd_index.build_index(path,index,path.stem,lambda *_:None,lambda:False)
        return index

    def test_match_keeps_cover_series_and_filename_count_and_unique_gtin(self):
        index=self.build(self.dump())
        with closing(sqlite3.connect(index)) as con:
            result=gcd.lookup({'path':'Example 001 (of 4) (2024).cbz','series':'Example','number':'1','year':'2024'}, {'Series':'Example'},index=con)
        self.assertEqual(result['fields']['Series'],'Example')
        self.assertEqual(result['fields']['Count'],'4')
        self.assertEqual(result['fields']['Publisher'],'Dark Horse Comics')
        self.assertEqual(result['fields']['GTIN'],'123456789012')
        self.assertIn('CC BY-SA 4.0',result['attribution'])

    def test_shared_gtin_and_whole_legends_tree_are_held(self):
        path=self.dump()
        with closing(sqlite3.connect(path)) as con, con:
            con.execute("INSERT INTO gcd_issue(id,series_id,number,barcode,deleted) VALUES(2,1,'2','123456789012',0)")
        index=self.build(path)
        with closing(sqlite3.connect(index)) as con:
            row={'path':'Example 001 (2024).cbz','series':'Example','number':'1','year':'2024'}
            self.assertNotIn('GTIN',gcd.lookup(row,{},index=con)['fields'])
            for publisher in ('Dark Horse', 'Marvel', 'CrossGen Comics'):
                with self.subTest(publisher=publisher):
                    con.execute('UPDATE series SET publisher=?', (publisher,))
                    for path in ('Star Wars Legends/Example 001 (2024).cbz', 'Y:\\Comix\\Star Wars\\STAR WARS LEGENDS\\Subfolder\\Example 001 (2024).cbz', 'Other/Star Wars Legends Example 001.cbz'):
                        diagnostic={}
                        held=dict(row,path=path)
                        self.assertIsNone(gcd.lookup(held,{},index=con,diagnostics=diagnostic))
                        self.assertEqual(diagnostic['excluded'],'Star Wars Legends tree')
                        self.assertFalse(source_scheduling.can_search('GCD offline',held,{}))
                    self.assertIsNotNone(gcd.lookup(row,{},index=con))
            self.assertFalse(gcd.legends_path('Other/Legends 001.cbz'))

    def test_publisher_imprint_uses_existing_date_aware_rules(self):
        from gcd_matching import Matcher
        index=self.build(self.dump())
        with closing(sqlite3.connect(index)) as con:
            con.row_factory=sqlite3.Row
            matcher=Matcher(con)
            issue=dict(con.execute('SELECT * FROM issue WHERE id=1').fetchone())
            series=dict(con.execute('SELECT * FROM series WHERE id=1').fetchone())
            for name,year,parent in [('WildStorm',1998,'Image Comics'),('WildStorm',2000,'DC Comics'),
                                     ('Archaia',2010,'Archaia'),('Archaia',2014,'BOOM! Studios'),
                                     ('WildStorm',None,None)]:
                with self.subTest(name=name,year=year):
                    fields,_=matcher.gcd_fields(dict(issue,year=year,sale_year=None),dict(series,publisher=name),'1')
                    self.assertEqual(fields.get('Publisher'),parent)
                    if parent and parent!=name:self.assertEqual(fields['Imprint'],name)

    def test_lifecycle_inspect_swap_same_dump_refusal_and_cancel_keep_old(self):
        path=self.dump()
        before=path.read_bytes()
        self.assertEqual(gcd.inspect_source(str(path))['dump_date'],'2026-10-16')
        gcd.start(str(path));gcd._thread.join(10)
        self.assertFalse(gcd._thread.is_alive())
        active=gcd.current()
        self.assertIsNotNone(active,gcd.status())
        with self.assertRaises(gcd.GcdError) as error:gcd.start(str(path))
        self.assertEqual(error.exception.code,'same_dump')
        entered=threading.Event();released=threading.Event()
        def slow(*args):
            entered.set();released.wait(5)
            raise InterruptedError()
        with patch.object(gcd_index,'build_index',side_effect=slow):
            gcd.start(str(path),True);self.assertTrue(entered.wait(5))
            gcd.cancel();released.set();gcd._thread.join(10)
        self.assertEqual(gcd.current(),active)
        self.assertEqual(gcd.status()['attempt']['state'],'cancelled')
        self.assertEqual(list(gcd.root().glob('stage-*')),[])
        self.assertEqual(path.read_bytes(),before)

    def test_invalid_zip_and_disk_shortage_never_replace_pointer(self):
        path=self.root/'bad.zip';path.write_text('not a zip')
        with self.assertRaises(gcd.GcdError) as error:gcd.inspect_source(str(path))
        self.assertEqual(error.exception.code,'not_a_zip')
        source=self.dump()
        with patch.object(gcd.shutil,'disk_usage',return_value=type('Space',(),{'free':1})()):
            with self.assertRaises(gcd.GcdError) as error:gcd.inspect_source(str(source))
        self.assertEqual(error.exception.code,'disk_space')
        self.assertIsNone(gcd.current())

    def test_rules_stamp_retries_miss_once_after_swap(self):
        previous={'signature':[1,2],'version':9,'outcome':'needs_identity_lookup','retry_at':10**20,
                  'source_schedule':{'GCD offline':{'result':'no_verified_match','rules':'old','next_at':10**20}}}
        with patch.object(gcd,'current',return_value={'rules':'new'}), patch.object(gcd,'rules_stamp',return_value='new'):
            self.assertTrue(source_scheduling.due(previous,[1,2],9,{},now=1))
            previous['source_schedule']['GCD offline']['rules']='new'
            self.assertFalse(source_scheduling.due(previous,[1,2],9,{},now=1))
