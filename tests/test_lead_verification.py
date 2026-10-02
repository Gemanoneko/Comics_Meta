import json
import unittest
from pathlib import Path
from unittest.mock import patch
import research,web_search
import io
from test_worker import scratch_directory


class LeadVerificationTests(unittest.TestCase):
    def setUp(self):
        self.row={'path':'Lady Death & Shi (Avatar)/comic.cbz','series':'Lady Death & Shi','number':'1','year':'2007'}
        self.source={'url':'https://example.org/issue','title':'Lady Death / Shi (2007) #1 - Details','text':'Story premise','identity_text':'Avatar Press 2007','image':'https://example.org/cover.jpg'}

    def test_fractional_issue_is_not_issue_five(self):
        self.assertEqual(research.issue_number('00.50'),'0.5')
        self.assertFalse(research.product_matches('Lady Death #5','Lady Death','0.5'))
        self.assertTrue(research.product_matches('Lady Death #0.5','Lady Death','0.5'))

    def test_catalog_title_with_year_and_prefix(self):
        self.assertTrue(research.product_matches("GCD :: Issue :: Brian Pulido's Lady Death (Avatar Press, 2007 Series) #01",'Lady Death','1'))

    def test_creator_prefix_and_crossover_chapter_do_not_hide_series(self):
        self.assertEqual(research.series_key("Brian Pulido's Lady Death: Sacrilege"),research.series_key('Lady Death - Sacrilege'))
        row={'path':'Hellwitch (Chapter 04) - Hellwitch vs. Lady Death - Wargasm 001 (2022).cbz','series':'Hellwitch'}
        self.assertEqual(research.query_identity(row,{'Series':'Hellwitch','Title':'Hellwitch vs. Lady Death: Wargasm','Number':'1'})[0],'Hellwitch vs. Lady Death: Wargasm')

    def test_folder_publisher_is_only_a_hint(self):
        self.assertIsNotNone(research.verify_web_source(self.row,{},self.source))
        wrong=dict(self.source,identity_text='DC Comics 2007')
        self.assertIsNone(research.verify_web_source(self.row,{},wrong))

    def test_wrong_issue_broad_article_and_reddit_rejected(self):
        for changes in ({'title':'Lady Death #2'},{'title':'Lady Death'},{'url':'https://www.reddit.com/r/comics/issue'}):
            self.assertIsNone(research.verify_web_source(self.row,{},dict(self.source,**changes)))

    def test_cover_disagreement_blocks_lead(self):
        with patch.object(web_search,'read',return_value=b'image'),patch('reverse_image.cover',return_value=(b'local','','')),patch('automatic.covers_agree',return_value=False):
            self.assertIsNone(research.verify_web_source(self.row,{},self.source,require_cover=True))

    def test_wiki_results_must_relate_to_series(self):
        payload={'query':{'search':[{'title':'Lady Death','pageid':1},{'title':'Avatar: The Last Airbender','pageid':2}]}}
        row=dict(self.row,series='Lady Death')
        with patch.object(research,'fetch',return_value=payload):
            self.assertEqual([r['pageid'] for r in research.wiki_candidates(row,{})],[1])

    def test_verified_saved_lead_is_resolved_without_new_search(self):
        with scratch_directory() as d,patch.object(research,'CACHE',Path(d)),patch.object(web_search,'source',return_value=self.source),patch.object(web_search,'read',return_value=b'image'),patch('reverse_image.cover',return_value=(b'local','','')),patch('automatic.covers_agree',return_value=True):
            research.save_evidence(self.row['path'],{'web_candidates':[{'url':self.source['url']}]})
            result=research.resolve_leads(self.row,{})
            self.assertEqual(result['fields']['Number'],'1')
            self.assertIn('cover agrees',result['sources'][0]['scope'])

    def test_cover_layout_survives_scan_brightness_but_not_different_art(self):
        from PIL import Image,ImageDraw,ImageEnhance
        from automatic import covers_agree
        cover=Image.new('RGB',(160,240),'navy');draw=ImageDraw.Draw(cover)
        for i in range(12):draw.rectangle((i*11,30+i*10,40+i*9,100+i*11),fill=(40+i*15,170-i*9,60+i*8))
        def raw(im):
            b=io.BytesIO();im.save(b,format='PNG');return b.getvalue()
        scan=ImageEnhance.Brightness(cover).enhance(.6)
        self.assertTrue(covers_agree(raw(cover),raw(scan)))
        other=cover.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        self.assertFalse(covers_agree(raw(cover),raw(other)))
