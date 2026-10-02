import json
import sqlite3
from contextlib import closing
import unittest
from pathlib import Path
from unittest.mock import patch
import providers
import open_library
import app
import batch
import zipfile
from test_worker import scratch_directory

class ProviderTests(unittest.TestCase):
    def test_source_summary_writer_readback_and_backup_cleanup(self):
        with scratch_directory() as d:
            base=Path(d);folder=base/'comics';folder.mkdir();data=base/'data';data.mkdir()
            comic=folder/'Garlic.cbz'
            with zipfile.ZipFile(comic,'w') as archive:
                archive.writestr('01.jpg',b'original cover bytes')
                archive.writestr('02.jpg',b'original story page bytes')
            with patch.object(app,'BASE',base),patch.object(app,'DATA',data):
                app.scan([str(folder)])
                summary='Garlic faces an unfamiliar challenge when a vampire moves into the nearby castle.'
                plan=base/'plan.json'
                plan.write_text(json.dumps({'folder':str(folder),'entries':[{'path':str(comic),'action':'write','sha256':batch.digest(comic),'fields':{'Summary':summary},'changes':{'Summary':{'before':'','after':summary}}}]}))
                batch.apply(plan,remove_verified_backups=True)
                self.assertEqual(app.read_metadata(comic)[0]['Summary'],summary)
                with zipfile.ZipFile(comic) as archive:self.assertEqual(archive.read('02.jpg'),b'original story page bytes')
                self.assertEqual(list(folder.rglob('*.bak')),[])

    def test_single_issue_is_not_a_book_candidate(self):
        with patch.object(providers,'setting',return_value='test'),patch.object(providers,'request') as request:
            self.assertIsNone(providers.google_lookup({'path':'Threshold 013 (1999).cbz','series':'Threshold'},{}))
            request.assert_not_called()

    def test_google_exact_isbn_and_ambiguity(self):
        row={'path':'Garlic.cbz','series':'Garlic'};old={'ISBN':'9780062995081'}
        item={'id':'abc','volumeInfo':{'title':'Garlic and the Vampire','language':'en','industryIdentifiers':[{'type':'ISBN_13','identifier':'9780062995081'}],'description':'A vampire arrives.'}}
        with patch.object(providers,'setting',return_value='test'):
            with patch.object(providers,'request',return_value={'items':[item]}):
                self.assertEqual(providers.google_lookup(row,old)['fields']['Title'],'Garlic and the Vampire')
            with patch.object(providers,'request',return_value={'items':[item,item]}):
                self.assertIsNone(providers.google_lookup(row,old))
            item['volumeInfo']['industryIdentifiers'][0]['identifier']='123'
            with patch.object(providers,'request',return_value={'items':[item]}):self.assertIsNone(providers.google_lookup(row,old))

    def test_gcd_wrong_year_or_cover_cannot_write(self):
        row={'path':'Threshold.cbz','series':'Threshold','number':'13','year':'1999'}
        candidate={'api_url':'https://www.comics.org/api/issue/1/'}
        detail={'series':'https://www.comics.org/api/series/2/','number':'13','key_date':'1999-01-01','cover':'https://covers.comics.org/x.jpg'}
        with patch.object(providers,'setting',return_value='test'),patch.object(providers,'cover_matches',return_value=False):
            with patch.object(providers,'request',side_effect=[{'results':[candidate]},detail,{'name':'Threshold'}]):self.assertIsNone(providers.gcd_lookup(row,{}))
            detail['key_date']='2000-01-01'
            with patch.object(providers,'request',side_effect=[{'results':[candidate]},detail,{'name':'Threshold'}]):self.assertIsNone(providers.gcd_lookup(row,{}))

    def test_redirects_refused(self):
        with self.assertRaises(ValueError):providers.NoRedirect().redirect_request(None,None,302,'',{},'https://other.example')

    def test_offline_work_description_requires_exact_edition_isbn(self):
        with scratch_directory() as d:
            index=Path(d)/'index.sqlite'
            with closing(sqlite3.connect(index)) as con, con:
                con.execute('CREATE TABLE records(key TEXT PRIMARY KEY,value TEXT)')
                for record in [{'key':'/books/OL1M','title':'Garlic','isbn_13':['9780062995081'],'works':[{'key':'/works/OL2W'}]}, {'key':'/works/OL2W','title':'Garlic','description':{'value':'A vampire arrives.'}}]:
                    con.execute('INSERT INTO records VALUES (?,?)',(record['key'],json.dumps(record)))
            with patch.object(open_library,'INDEX',index):
                self.assertIsNone(open_library.lookup({'path':'x.cbz'},{}))
                result=open_library.lookup({'path':'x.cbz'},{'ISBN':'9780062995081'})
                self.assertEqual(result['sources'][0]['text'],'A vampire arrives.')
