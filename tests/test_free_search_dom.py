"""Offline DOM regressions; attach only to the canonical owned QA browser.

Ordinary unittest runs skip this fixture. The reviewed QA harness supplies its
fresh loopback CDP endpoint via COMICS_TEST_CDP; this module launches no browser.
Every page request is locally fulfilled or aborted, never sent to a provider.
"""
import os
import unittest
import urllib.parse
from unittest.mock import patch
import free_search_browser as browser


@unittest.skipUnless(os.environ.get('COMICS_TEST_CDP'), 'Requires canonical owned offline browser fixture')
class RenderedSearchDOMTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        endpoint=os.environ['COMICS_TEST_CDP']
        parsed=urllib.parse.urlparse(endpoint)
        assert parsed.scheme=='http' and parsed.hostname=='127.0.0.1' and parsed.port and not parsed.path
        from playwright.sync_api import sync_playwright
        cls.runtime=sync_playwright().start()
        cls.connection=cls.runtime.chromium.connect_over_cdp(endpoint)
        cls.context=cls.connection.new_context()
        cls.context.route('**/*',lambda route:route.abort())
        cls.page=cls.context.new_page()

    @classmethod
    def tearDownClass(cls):
        cls.context.close()
        cls.connection.close()
        cls.runtime.stop()

    def render(self,content,engine='bing',field='<input name="q" value="Fixture #1 comics">'):
        self.page.set_content('<!doctype html><html><body>'+field+content+'</body></html>')
        return self.page.evaluate(browser.RESULTS_READY,{'query':'Fixture #1 comics','selector':browser.ENGINES[engine]['selector'],
                                                       'emptySelector':browser.ENGINES[engine]['empty_selector']})

    def card(self,title='Fixture #1',style='',url='https://example.org/issue'):
        return '<li class="b_algo" '+style+'><h2><a href="'+url+'">'+title+'</a></h2></li>'

    def test_hidden_cards_before_visible_result_never_consume_result_slots(self):
        hidden=''.join(self.card('Hidden issue '+str(n),'style="display:none"') for n in range(12))
        hidden+=self.card('Invisible title','style="opacity:0"')+self.card('Invisible title','aria-hidden="true"')
        hidden+=self.card('Invisible title','style="visibility:hidden"')+self.card('  ')
        result=self.render('<ol id="b_results">'+hidden+self.card('Visible <strong>Fixture #1</strong>')+'</ol>')
        self.assertEqual(result,{'items':[{'url':'https://example.org/issue','title':'Visible Fixture #1'}]})

    def test_hidden_nonempty_descendant_and_empty_title_are_unready(self):
        for title in ('<span style="opacity:0">Wrong comic</span>','<span aria-hidden="true">Wrong comic</span>','   '):
            self.assertFalse(self.render('<ol id="b_results">'+self.card(title)+'</ol>'))

    def test_empty_message_must_be_visible_in_engine_empty_state(self):
        self.assertFalse(self.render('<div>No results found</div><ol id="b_results"></ol>'))
        for content in ('<li class="b_no" style="opacity:0">No results found</li>',
                        '<li class="b_no"><span style="opacity:0">No results found</span></li>',
                        '<li class="b_no">Loading...</li>'):
            self.assertFalse(self.render('<ol id="b_results">'+content+'</ol>'))
        self.assertEqual(self.render('<ol id="b_results"><li class="b_no">No results found for this query</li></ol>'),{'items':[]})

    def test_mismatched_hidden_or_ambiguous_search_fields_are_unready(self):
        cards='<ol id="b_results">'+self.card()+'</ol>'
        for field in ('','<input name="q" value="Other comic">','<input hidden name="q" value="Fixture #1 comics">',
                      '<input name="q" value="Fixture #1 comics"><input name="q" value="Other comic">'):
            self.assertFalse(self.render(cards,field=field))

    def test_textarea_query_and_delayed_rendering_are_supported(self):
        result=self.render('<ol id="b_results">'+self.card()+'</ol>',field='<textarea name="q">Fixture #1 comics</textarea>')
        self.assertEqual(result['items'][0]['title'],'Fixture #1')
        self.assertFalse(self.render('<ol id="b_results">'+self.card('')+'</ol>'))
        self.page.evaluate("setTimeout(() => document.querySelector('h2 a').textContent='Fixture #1', 50)")
        handle=self.page.wait_for_function(browser.RESULTS_READY,arg={'selector':browser.ENGINES['bing']['selector'],
            'emptySelector':browser.ENGINES['bing']['empty_selector'],'query':'Fixture #1 comics'},timeout=2000)
        self.assertEqual(handle.json_value()['items'][0]['title'],'Fixture #1');handle.dispose()

    def test_ads_navigation_and_nonorganic_links_are_excluded_for_both_engines(self):
        result=self.render('<a href="https://example.org/nav">Navigation</a><ol id="b_results"><li class="b_ad"><h2><a href="https://example.org/ad">Ad</a></h2></li>'+self.card()+'</ol>')
        self.assertEqual(len(result['items']),1)
        ddg='<li data-layout="organic"><article data-testid="result"><h2><a data-testid="result-title-a" href="https://example.org/ddg">Fixture #1</a></h2></article></li>'
        self.assertEqual(self.render(ddg,'ddg')['items'][0]['url'],'https://example.org/ddg')

    def test_real_readiness_and_safe_redirect_flow_from_locally_fulfilled_page(self):
        query='Fixture #1 comics'
        url='https://www.bing.com/search?'+urllib.parse.urlencode({'q':query})
        html='<input name="q" value="Fixture #1 comics"><ol id="b_results">'+self.card(url='https://www.bing.com/ck/a?u=a1aHR0cHM6Ly9leGFtcGxlLm9yZy9pc3N1ZQ')+'</ol>'
        self.page.route(url,lambda route:route.fulfill(status=200,content_type='text/html',body=html))
        try:
            self.page.goto(url)
            self.assertEqual(browser.rendered_results(self.page,query,'bing'),[{'url':'https://example.org/issue','title':'Fixture #1'}])
        finally:self.page.unroute(url)


if __name__=='__main__':unittest.main()
