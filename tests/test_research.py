import unittest
from unittest.mock import patch
import research

class PublisherTests(unittest.TestCase):
    def test_issue_and_edition_boundaries(self):
        self.assertTrue(research.product_matches('Hellwitch: Hellbourne #1 - Premiere Edition','Hellwitch: Hellbourne','1'))
        self.assertFalse(research.product_matches('Hellwitch: Hellbourne #10 - Edition','Hellwitch: Hellbourne','1'))
        self.assertFalse(research.product_matches('Hellwitch: Forsaken #1','Hellwitch: Hellbourne','1'))

    def test_chapter_subtitle_not_issue_number(self):
        row={'path':'Hellwitch (Chapter 02) - Forsaken 001 (2020).cbz','series':'Hellwitch','number':'1'}
        self.assertEqual(research.query_identity(row,{}),('Hellwitch: Forsaken','1'))

    def test_external_source_allowlist(self):
        with self.assertRaises(ValueError):research.fetch('http://127.0.0.1/secret')

    def test_synopsis_reviewer_rejection(self):
        import local_model
        with patch.object(local_model,'chat',side_effect=[{'summary':'A '*25,'sufficient':True,'narrative':True,'evidence':['source quote']},{'supported':False,'spoiler_free':True}]):
            self.assertIsNone(local_model.sourced_synopsis([{'url':'https://example.org','text':'source quote'}]))

    def test_archive_story_inference_disabled(self):
        import local_model
        with self.assertRaises(ValueError):local_model.synopsis_proposal('unused')

    def test_fabricated_quote_rejected(self):
        import local_model
        with patch.object(local_model,'chat',return_value={'summary':'A '*25,'sufficient':True,'narrative':True,'evidence':['invented quote']}):
            self.assertIsNone(local_model.sourced_synopsis([{'url':'https://example.org','text':'actual evidence'}]))

    def test_occupant_not_promoted_to_leader(self):
        import local_model
        text='The sole occupant is Nocturne.'
        with patch.object(local_model,'chat',return_value={'summary':'A '*22+' led by Nocturne','sufficient':True,'narrative':True,'evidence':[text]}):
            self.assertIsNone(local_model.sourced_synopsis([{'url':'https://example.org','text':text}]))

    def test_source_backed_draft_accepted(self):
        import local_model
        source={'url':'https://example.org','text':'A rebel confronts the queen in a city where rival factions compete for power, while a mysterious visitor offers a dangerous bargain.'}
        draft={'summary':source['text'],'sufficient':True,'narrative':True,'evidence':[source['text']]}
        review={'supported':True,'spoiler_free':True,'narrative':True,'claims':[{'supported':True,'quote':source['text']}]}
        with patch.object(local_model,'chat',side_effect=[draft,review]):
            self.assertEqual(local_model.sourced_synopsis([source])['sources'],[source['url']])
