import unittest
from unittest.mock import patch
import metron

class MetronTests(unittest.TestCase):
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
