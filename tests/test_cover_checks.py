"""v0.1.2 review round 2: candidate-cover reads (Senua F2) and near-blank covers (Futaba Q-3).

Mocked search, pages and image downloads; real Pillow decoding; isolated catalog.
"""
import hashlib
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image, ImageDraw
import app
import automatic
import getcomics
import research
import web_search
from test_worker import scratch_directory


def evidence(path):
    target=research.CACHE/('evidence-'+hashlib.sha256(path.encode()).hexdigest()+'.json')
    return json.loads(target.read_text(encoding='utf-8'))


def png(image):
    output=io.BytesIO();image.save(output,format='PNG');return output.getvalue()


def busy_cover():
    image=Image.new('RGB',(160,240),'navy');draw=ImageDraw.Draw(image)
    for i in range(12):draw.rectangle((i*11,30+i*10,40+i*9,100+i*11),fill=(40+i*15,170-i*9,60+i*8))
    return png(image)


ROW={'path':'Example Saga 003 (2019).cbz','series':'Example Saga','number':'3','year':'2019'}
OLD={'Writer':'Jane Example'}


def page(url):
    return {'url':url,'title':'Example Saga #3','headings':[],'image':'/cover.jpg',
            'identity_text':'Example Saga #3 (2019). Writer Jane Example.','text':'Example Saga #3 (2019).'}


class CandidateCoverReadTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app,'DATA',self.root/'data'))
        self.enterContext(patch.object(research,'CACHE',self.root/'research'))
        self.cover=busy_cover()
        self.enterContext(patch('reverse_image.cover',return_value=(self.cover,'image/png','.png')))
        # The first candidate's "image" is a hotlink-protection HTML page.
        images={'https://first.example/cover.jpg':b'<html>Hotlinking is not allowed</html>',
                'https://second.example/cover.jpg':self.cover}
        self.enterContext(patch.object(web_search,'read',side_effect=lambda url,**_:images[url]))
        self.enterContext(patch.object(web_search,'source',side_effect=page))

    def test_undecodable_cover_counts_as_unverified_and_the_lookup_continues(self):
        hits=[{'url':'https://first.example/issue'},{'url':'https://second.example/issue'}]
        with patch.object(web_search,'search',return_value=hits):
            result=research.general_lookup(ROW,OLD)  # Before the fix: UnidentifiedImageError escaped.
        self.assertEqual(result['sources'][0]['url'],'https://second.example/issue')
        saved=evidence(ROW['path'])
        self.assertEqual(len(saved['web_candidates']),2)  # Evidence is saved, not lost.
        self.assertIn('Candidate cover could not be compared (UnidentifiedImageError).',saved['web_errors'])

    def test_undecodable_cover_does_not_abandon_the_remaining_leads(self):
        research.save_evidence(ROW['path'],{'reverse_image_matches':[{'url':'https://first.example/issue'},{'url':'https://second.example/issue'}]})
        result=research.resolve_leads(ROW,OLD)
        self.assertEqual(result['sources'][0]['url'],'https://second.example/issue')
        self.assertEqual([lead['verified'] for lead in evidence(ROW['path'])['lead_verification']],[False,True])


class CoverFetchProviderStateTests(unittest.TestCase):
    """A failed candidate image never blocks GetComics or a publisher catalog."""
    def setUp(self):
        self.root=Path(self.enterContext(scratch_directory()))
        self.enterContext(patch.object(app,'DATA',self.root/'data'))
        self.enterContext(patch.object(web_search,'validate_url'))
        self.enterContext(patch('reverse_image.cover',return_value=(busy_cover(),'image/png','.png')))
        with app.db() as con:
            con.execute('CREATE TABLE IF NOT EXISTS getcomics_state(id INTEGER PRIMARY KEY,last_request REAL,blocked INTEGER,status TEXT)')
            con.execute("INSERT OR IGNORE INTO getcomics_state VALUES(1,0,0,'ready')")

    def test_getcomics_image_failure_leaves_getcomics_available(self):
        source=dict(page('https://getcomics.org/other-comics/example-saga-3/'),image='https://getcomics.org/wp-content/cover.jpg')
        with patch.object(web_search.urllib.request.OpenerDirector,'open',side_effect=OSError('403 hotlink')):
            self.assertIsNone(research.verify_web_source(ROW,OLD,source))
        with app.db() as con:
            state=dict(con.execute('SELECT * FROM getcomics_state WHERE id=1').fetchone())
        self.assertEqual(state['blocked'],0)  # Before the fix: 1, permanently (no reset path).
        self.assertNotEqual(state['status'],'access_blocked')

    def test_page_read_failures_still_mark_the_provider(self):
        # Positive control: the provider-state path itself is unchanged.
        with patch.object(web_search.urllib.request.OpenerDirector,'open',side_effect=OSError('403')):
            with self.assertRaises(web_search.SearchBlocked):web_search.read('https://getcomics.org/other-comics/example/')
        with app.db() as con:
            self.assertEqual(con.execute('SELECT blocked FROM getcomics_state WHERE id=1').fetchone()[0],1)


class NearBlankCoverTests(unittest.TestCase):
    """Q-3: two different near-blank covers agreed through the pixel shortcut."""
    def blank(self,corner):
        image=Image.new('RGB',(400,600),(8,8,8));draw=ImageDraw.Draw(image)
        x,y={'top-left':(10,10),'bottom-right':(300,540)}[corner]
        draw.rectangle((x,y,x+60,y+30),fill='white')
        return png(image)

    def test_different_near_blank_covers_do_not_agree(self):
        self.assertFalse(automatic.covers_agree(self.blank('top-left'),self.blank('bottom-right')))
        # A flat cover carries no evidence, so it never verifies anything.
        self.assertFalse(automatic.covers_agree(self.blank('top-left'),self.blank('top-left')))

    def test_detailed_covers_still_agree(self):
        self.assertTrue(automatic.covers_agree(busy_cover(),busy_cover()))


if __name__=='__main__':
    unittest.main()
