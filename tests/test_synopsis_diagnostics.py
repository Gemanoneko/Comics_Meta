import io
import json
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch
import app,local_model,pause_control
from provider_wait import ProviderDeferred
from test_worker import scratch_directory


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app,'DATA',self.root/'data'))
        self.enterContext(patch.object(pause_control,'requested',return_value=False))
        self.source={'url':'https://example.org','text':'A rebel confronts the queen in a city where rival factions compete for power, while a mysterious visitor offers a dangerous bargain.'}

    def test_span_selection_still_needs_independent_spoiler_and_quote_review(self):
        draft={'candidate_id':0,'sufficient':True,'narrative':True}
        review={'supported':True,'spoiler_free':True,'narrative':True,'reason':'Supported','claims':[{'claim':'Teaser','supported':True,'quotes':[self.source['text']]}]}
        with patch.object(local_model,'chat',side_effect=[draft,review]) as chat:
            d={};result=local_model.sourced_synopsis([self.source],d)
            self.assertEqual(result['summary'],self.source['text']);self.assertEqual(d['status'],'accepted')
            self.assertEqual(chat.call_args_list[0].kwargs['schema'],local_model.DRAFT_SCHEMA)
            self.assertEqual(chat.call_args_list[1].kwargs['schema'],local_model.REVIEW_SCHEMA)
        for changed in ({'spoiler_free':False},{'supported':False},{'claims':[{'supported':True,'quotes':['invented quote']}]}):
            with patch.object(local_model,'chat',side_effect=[draft,dict(review,**changed)]):
                d={};self.assertIsNone(local_model.sourced_synopsis([self.source],d));self.assertEqual(d['status'],'rejected')

    def test_invalid_id_and_boolean_types_are_rejected_with_reasons(self):
        for response,reason in [({'candidate_id':100,'sufficient':True,'narrative':True},'invalid_source_span'),
                                ({'candidate_id':True,'sufficient':True,'narrative':True},'invalid_source_span'),
                                ({'candidate_id':0,'sufficient':True,'narrative':'A story'},'draft_invalid')]:
            with patch.object(local_model,'chat',return_value=response):
                d={};self.assertIsNone(local_model.sourced_synopsis([self.source],d));self.assertEqual(d['reason'],reason)

    def test_schema_is_sent_to_the_local_model(self):
        response=io.BytesIO(json.dumps({'message':{'content':'{"candidate_id":0,"sufficient":true,"narrative":true}'}}).encode())
        with patch.object(local_model.urllib.request,'urlopen',return_value=response) as request:
            local_model.chat('select',schema=local_model.DRAFT_SCHEMA)
            body=json.loads(request.call_args.args[0].data)
            self.assertEqual(body['format'],local_model.DRAFT_SCHEMA)

    def test_comicvine_http_error_preserves_retry_status_and_typed_deferral(self):
        error=urllib.error.HTTPError('https://example.org',403,'Forbidden',{},None)
        with patch.object(app,'api_key',return_value='synthetic'),patch.object(app,'reserve_request',return_value=0),patch.object(app.urllib.request,'urlopen',side_effect=error):
            with self.assertRaises(ProviderDeferred):app.api('issue/4000-1')
        state=json.loads((app.DATA/'comicvine-status.json').read_text())
        self.assertEqual(state['status'],'access_rejected');self.assertEqual(state['http_status'],403);self.assertGreater(state['retry_at'],0)
