import unittest
import automatic

class IdentityTests(unittest.TestCase):
    def test_ambiguous_or_wrong_publisher_rejected(self):
        v = {'name':'Threshold','publisher':{'name':'Avatar Press'},'id':1}
        self.assertEqual(automatic.unique_volume([v],'Threshold','Avatar Press'),v)
        self.assertIsNone(automatic.unique_volume([v,v],'Threshold','Avatar Press'))
        self.assertIsNone(automatic.unique_volume([v],'Threshold','DC Comics'))
        self.assertIsNone(automatic.unique_volume([v],'Threshold',None))

    def test_different_cover_rejected(self):
        import io
        from PIL import Image, ImageDraw
        a=Image.new('RGB',(100,150),'white');ImageDraw.Draw(a).rectangle((0,0,49,149),fill='black')
        b=Image.new('RGB',(100,150),'white');ImageDraw.Draw(b).rectangle((50,0,99,149),fill='black')
        x=io.BytesIO();y=io.BytesIO();a.save(x,format='PNG');b.save(y,format='PNG')
        self.assertTrue(automatic.covers_agree(x.getvalue(),x.getvalue()))
        self.assertFalse(automatic.covers_agree(x.getvalue(),y.getvalue()))

    def test_mismatched_issue_or_series_rejected(self):
        old = {'Series':'Threshold', 'Number':'13'}
        issue = {'volume':{'name':'Threshold'}, 'issue_number':'13'}
        self.assertTrue(automatic.identity_matches(old,issue))
        issue['issue_number'] = '12'
        self.assertFalse(automatic.identity_matches(old,issue))
        issue['issue_number'] = '13'; issue['volume']['name'] = 'Threshold: The Hunted'
        self.assertFalse(automatic.identity_matches(old,issue))
        self.assertFalse(automatic.identity_matches({},issue))
