import unittest
import io
import json
import time
from pathlib import Path
from unittest.mock import patch
import metron
import app
from test_worker import scratch_directory

class MetronTests(unittest.TestCase):
    def setUp(self):
        root=Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app,'DATA',root/'data'))
        self.enterContext(patch.object(metron,'STATE',root/'metron.json'))
    def test_credential_never_follows_redirect(self):
        with self.assertRaises(ValueError):
            metron.NoRedirect().redirect_request(None,None,302,'',{},'https://other.example/')

    def test_missing_token_does_not_search(self):
        with patch.object(metron,'token',return_value=''), patch.object(metron,'request') as request:
            self.assertIsNone(metron.lookup({'path':'x.cbz','series':'Threshold','number':'13','year':'1999'},{}))
            request.assert_not_called()

    def test_ambiguous_or_partial_results_cannot_be_written(self):
        row={'path':'x.cbz','series':'Threshold','number':'13','year':'1999'}
        issue={'id':1,'series':{'name':'Threshold'},'number':'13','cover_date':'1999-01-01'}
        with patch.object(metron,'token',return_value='test'):
            for payload in ({'results':[issue,issue]}, {'results':[issue],'next':'more'}):
                with patch.object(metron,'request',return_value=payload):
                    self.assertIsNone(metron.lookup(row,{}))

    def test_wrong_issue_or_series_rejected(self):
        row={'path':'x.cbz','series':'Threshold','number':'13','year':'1999'}
        for series,number in [('Threshold','12'),('Another Threshold','13')]:
            payload={'results':[{'id':1,'series':{'name':series},'number':number,'cover_date':'1999-01-01'}]}
            with patch.object(metron,'token',return_value='test'),patch.object(metron,'request',return_value=payload):
                self.assertIsNone(metron.lookup(row,{}))

    def test_year_candidates_share_one_network_query_for_rejected_covers(self):
        items=[{'id':i,'series':{'name':'Example'},'number':str(i),'cover_date':'2024-01-01','image':'https://static.metron.cloud/'+str(i)+'.jpg'} for i in (1,2,3)]
        payload={'count':3,'next':None,'results':items}
        with patch.object(metron,'token',return_value='synthetic'),patch.object(metron,'verified_cover',return_value=False),patch.object(metron.urllib.request,'build_opener') as opener:
            response=io.BytesIO(json.dumps(payload).encode());response.headers={}
            opener.return_value.open.return_value=response
            for i in (1,2,3):
                self.assertIsNone(metron.lookup({'path':'x.cbz','series':'Example','number':str(i),'year':'2024'},{}))
            self.assertEqual(opener.return_value.open.call_count,1)
            with app.db() as con:
                keys=[r['key'] for r in con.execute("SELECT key FROM cache WHERE key LIKE 'metron:%'")]
            self.assertEqual(len(keys),1)
            self.assertNotIn('number=',keys[0])

    def test_partial_year_list_falls_back_to_narrow_search(self):
        partial={'count':101,'next':'more','results':[]}
        complete={'count':0,'next':None,'results':[]}
        with patch.object(metron,'request',side_effect=[partial,complete]) as request:
            self.assertEqual(metron.candidates('Example','1','2024'),complete)
            self.assertEqual(request.call_args_list[1].kwargs,{'series_name':'Example','number':'1','cover_year':'2024'})
        with patch.object(metron,'request',side_effect=[{'count':2,'results':[]},complete]) as request:
            self.assertEqual(metron.candidates('Example','1','2024'),complete)
            self.assertEqual(request.call_count,2)

    def test_detail_identity_and_changed_cover_still_require_verification(self):
        candidate={'id':1,'series':{'name':'Example'},'number':'1','cover_date':'2024-01-01','image':'https://static.metron.cloud/one.jpg'}
        detail=dict(candidate,desc='A verified story teaser.')
        row={'path':'x.cbz','series':'Example','number':'1','year':'2024'}
        with patch.object(metron,'token',return_value='synthetic'):
            for changed in ({'id':2},{'number':'2'},{'series':{'name':'Another'}},{'cover_date':'2023-01-01'}):
                with patch.object(metron,'request',side_effect=[{'results':[candidate]},dict(detail,**changed)]),patch.object(metron,'verified_cover',return_value=True):
                    self.assertIsNone(metron.lookup(row,{}))
            with patch.object(metron,'request',side_effect=[{'results':[candidate]},dict(detail,image='https://static.metron.cloud/new.jpg')]),patch.object(metron,'verified_cover',side_effect=[True,False]) as verify:
                self.assertIsNone(metron.lookup(row,{}));self.assertEqual(verify.call_count,2)
            with patch.object(metron,'request',side_effect=[{'results':[candidate]},detail]),patch.object(metron,'verified_cover',return_value=True) as verify:
                self.assertEqual(metron.lookup(row,{})['fields']['Number'],'1');self.assertEqual(verify.call_count,1)
