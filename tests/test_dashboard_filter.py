"""The collection status filter offers every status (Judy, 2026-10-12)."""
import unittest
from html.parser import HTMLParser
from pathlib import Path


class Options(HTMLParser):
    def __init__(self):
        super().__init__();self.inside=False;self.current=None;self.options=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='select' and attrs.get('id')=='status':self.inside=True
        elif tag=='option' and self.inside:self.current=[attrs.get('value'),'']
    def handle_endtag(self,tag):
        if tag=='option' and self.current is not None:self.options.append(tuple(self.current));self.current=None
        elif tag=='select':self.inside=False
    def handle_data(self,data):
        if self.current is not None:self.current[1]+=data


class StatusFilterTests(unittest.TestCase):
    def test_no_embedded_metadata_is_a_real_option(self):
        parser=Options();parser.feed((Path(__file__).resolve().parents[1]/'static'/'index.html').read_text(encoding='utf-8'))
        values=[value for value,_ in parser.options]
        # Before the fix the second option's opening tag was missing, so the
        # browser dropped "No embedded metadata" from the dropdown.
        self.assertIn(('missing','No embedded metadata'),parser.options)
        self.assertEqual(values[:2],['','missing'])
        self.assertEqual(len(values),len(set(values)))


if __name__=='__main__':
    unittest.main()
