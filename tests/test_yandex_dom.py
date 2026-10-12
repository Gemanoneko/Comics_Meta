"""Actual headless DOM/UI checks with every request fulfilled locally."""
import json
import os
from pathlib import Path
import unittest
import urllib.parse
import free_search_browser as browser


@unittest.skipUnless(os.environ.get('COMICS_TEST_CDP'),'Requires owned offline headless fixture')
class YandexDOMTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        endpoint=os.environ['COMICS_TEST_CDP'];parsed=urllib.parse.urlparse(endpoint)
        assert parsed.scheme=='http' and parsed.hostname=='127.0.0.1' and parsed.port
        cls.runtime=sync_playwright().start();cls.browser=cls.runtime.chromium.connect_over_cdp(endpoint)

    @classmethod
    def tearDownClass(cls):cls.browser.close();cls.runtime.stop()

    def setUp(self):
        self.context=self.browser.new_context();self.addCleanup(self.context.close)
        self.context.route('**/*',lambda route:route.abort())
        self.page=self.context.new_page()

    def test_yandex_visible_cards_text_query_and_ad_exclusion(self):
        self.page.set_content('''<input name="text" value="Fixture #1 comics"><ul>
            <li class="serp-item serp-item_ad"><h2><a href="https://example.org/ad">Advert</a></h2></li>
            <li class="serp-item" style="opacity:0"><h2><a href="https://example.org/hidden">Hidden</a></h2></li>
            <li class="serp-item"><h2><a href="https://example.org/issue">Fixture <b>#1</b><span aria-hidden="true">Wrong</span></a></h2></li></ul>''')
        args=browser.result_arguments('Fixture #1 comics','yandex')
        self.assertEqual(self.page.evaluate(browser.RESULTS_READY,args),{'items':[{'url':'https://example.org/issue','title':'Fixture #1'}]})
        self.page.locator('input').fill('Other comic')
        self.assertFalse(self.page.evaluate(browser.RESULTS_READY,args))

    def test_unknown_yandex_empty_or_challenge_page_never_fabricates_results(self):
        for body in ('No results found','<div class="Captcha">Are you not a robot?</div>','<li class="serp-item"><h2><a href="https://example.org/issue"><span style="opacity:0">Wrong title</span></a></h2></li>'):
            self.page.set_content('<input name="text" value="Fixture">'+body)
            self.assertFalse(self.page.evaluate(browser.RESULTS_READY,browser.result_arguments('Fixture','yandex')))


@unittest.skipUnless(os.environ.get('COMICS_TEST_CDP'),'Requires owned offline headless fixture')
class DashboardDOMTests(YandexDOMTests):
    def setUp(self):
        super().setUp()
        self.root=Path(__file__).resolve().parents[1]
        self.current={'engine':'yandex','phase':'required','human_verification':True,'verification_pending':False,
                      'window':'closed','alive':True,'availability':'available','retry_at':0,'failure':''}
        self.posts=[]
        self.context.add_init_script('window.setInterval=()=>0;')
        self.page.route('https://comics-fixture.invalid/**',self.route)
        self.page.goto('https://comics-fixture.invalid/')
        self.page.wait_for_function("document.querySelector('#appVersion').textContent==='v0.1.0'")

    def route(self,route):
        path=urllib.parse.urlparse(route.request.url).path
        if path=='/':return route.fulfill(body=(self.root/'static/index.html').read_text(encoding='utf-8'),content_type='text/html')
        if path=='/reverse-image.js':return route.fulfill(body='',content_type='text/javascript')
        if path=='/api/state':
            if getattr(self,'state_mode','')=='delayed':self.pending_state=route;return
            if getattr(self,'state_mode','')=='failed':return route.fulfill(status=503,json={'error':'Fixture service unavailable'})
            data=self.state_payload()
            if getattr(self,'state_mode','')=='missing':data.pop('version')
        elif path=='/api/progress':data={'control':{},'providers':{'free_web':{'status':'available','engines':{'yandex':{'verification':self.current}}}},'browser_search':{'alive':True,'human_verification':True},'queue':{'alive':True},'timestamp':1}
        elif path=='/api/comics':data={'rows':[],'total':0}
        elif path=='/api/yandex-verification':
            self.posts.append(json.loads(route.request.post_data));self.current=dict(self.current,phase='queued',verification_pending=True);data={'ok':True,'state':'queued'}
        else:return route.abort()
        route.fulfill(json=data)

    def state_payload(self):
        return {'version':'0.1.0','roots':[],'job':{'message':'Ready','visited':0,'changed':0,'running':False},'counts':{},'totals':{}}

    def render(self,**changes):
        state=dict(self.current,**changes)
        self.page.evaluate('state=>YandexControl.render(state,{})',state)
        return self.page.locator('#yandexStatus').inner_text()

    def test_exact_states_and_recovery_without_repeated_announcements(self):
        expected={
            'required':'Yandex needs your verification. Other processing continues.',
            'queued':'Verification queued until the current operation finishes.',
            'opening':'Opening the Yandex verification window.',
            'open':'Complete Yandex verification in the browser window.',
            'failed':'Yandex verification did not finish. Open a new window when ready.',
            'pausing':'Pausing; closing the Yandex window safely.',
            'paused':'Paused. Resume processing to continue.'}
        for phase,text in expected.items():
            self.assertEqual(self.render(phase=phase),'Yandex web search: '+text)
        self.assertIn('could not open',self.render(phase='failed',failure='open'))
        self.assertIn('Verification complete. Automatic searches',self.render(phase='verified',human_verification=False))
        self.page.evaluate('YandexControl.unavailable()')
        self.assertIn('Status unavailable',self.page.locator('#yandexStatus').inner_text())
        self.assertIn('Ready.',self.render(phase='idle',human_verification=False))
        self.page.evaluate("window.announcements=0;new MutationObserver(r=>announcements+=r.length).observe(document.querySelector('#yandexStatus'),{childList:true,subtree:true});")
        for _ in range(3):self.render(phase='idle',human_verification=False)
        self.assertEqual(self.page.evaluate('announcements'),0)

    def test_budget_pacing_and_cooldown_are_truthful_even_after_owner_restart(self):
        future=self.page.evaluate('Date.now()/1000+90000')
        self.assertIn('Verification queued until ',self.render(phase='queued',retry_at=future,availability='daily_budget_wait'))
        self.assertTrue(self.page.locator('#yandexVerification').is_disabled())
        self.assertIn('Web search budget reached.',self.render(phase='idle',human_verification=False,retry_at=future,availability='daily_budget_wait'))
        self.assertIn('Next search after ',self.render(phase='idle',human_verification=False,retry_at=future,availability='pacing_wait'))
        self.assertIn('search unavailable. Retry after ',self.render(phase='idle',human_verification=False,retry_at=future,availability='cooldown_wait'))
        self.assertEqual(self.render(phase='searching',human_verification=False,retry_at=future,availability='pacing_wait'),'Yandex web search: Searching.')

    def test_keyboard_action_deduplication_and_success_focus(self):
        self.render();button=self.page.locator('#yandexVerification');button.focus();button.press('Space')
        self.page.wait_for_function("document.querySelector('#yandexVerification').disabled")
        self.page.evaluate("document.querySelector('#yandexVerification').click()")
        self.page.wait_for_function("document.querySelector('#yandexStatus').textContent.includes('queued')")
        self.assertEqual(self.posts,[{'engine':'yandex'}])
        self.render(phase='open')
        self.render(phase='verified',human_verification=False)
        self.assertEqual(self.page.evaluate('document.activeElement.id'),'yandexStatus')
        self.assertTrue(button.is_hidden())
        self.page.keyboard.press('Tab')
        self.assertTrue(self.page.evaluate("document.activeElement.tagName==='SUMMARY'"))
        self.assertEqual(self.page.locator('#browserResume').inner_text(),'Open browser verification')

    def test_version_loading_valid_invalid_failure_recovery_and_no_reannouncement(self):
        for value,expected in [('0.1.0','v0.1.0'),('v0.1.0','v0.1.0'),('', 'Version unavailable'),(None,'Version unavailable'),('latest<script>','Version unavailable'),('0.2.0','v0.2.0')]:
            self.page.evaluate('value=>renderVersion(value)',value)
            self.assertEqual(self.page.locator('#appVersion').inner_text(),expected)
        self.assertEqual(self.page.locator('#appVersion').get_attribute('aria-label'),'App version 0.2.0')
        self.assertIsNone(self.page.locator('#appVersion').get_attribute('tabindex'))

    def test_actual_state_loading_missing_failure_and_recovery(self):
        self.state_mode='delayed';self.page.goto('https://comics-fixture.invalid/')
        self.assertEqual(self.page.locator('#appVersion').inner_text(),'Version loading…')
        self.pending_state.fulfill(json=self.state_payload())
        self.page.wait_for_function("document.querySelector('#appVersion').textContent==='v0.1.0'")
        self.state_mode='missing';self.page.evaluate('state()')
        self.assertEqual(self.page.locator('#appVersion').inner_text(),'Version unavailable')
        self.state_mode='';self.page.evaluate('state()')
        self.assertEqual(self.page.locator('#appVersion').inner_text(),'v0.1.0')
        self.state_mode='failed';self.page.evaluate('state()')
        self.assertEqual(self.page.locator('#appVersion').inner_text(),'Version unavailable')
        self.state_mode='';self.page.evaluate('state()')
        self.assertEqual(self.page.locator('#appVersion').inner_text(),'v0.1.0')

    def test_rects_states_zoom_and_open_dialog(self):
        output=Path(os.environ['COMICS_TEST_EVIDENCE']);output.mkdir(parents=True,exist_ok=True)
        rows=[]
        for width,zoom in ((1440,1),(320,1),(1440,2),(320,2)):
            self.page.set_viewport_size({'width':width,'height':1100})
            self.page.evaluate('zoom=>document.body.style.zoom=zoom',str(zoom))
            for phase in ('required','queued','opening','open','failed','verified','idle','paused'):
                self.render(phase=phase,human_verification=phase not in {'verified','idle'})
                rects=self.page.evaluate('''() => {
                    const targets=Object.fromEntries(['appVersion','pauseControl','controlStatus','browserStatus','browserResume','yandexStatus','yandexVerification'].map(id=>[id,document.getElementById(id)]));
                    targets.title=document.querySelector('header h1');targets.previousBatches=document.querySelector('#completedBatches').closest('details').querySelector('summary');
                    return Object.fromEntries(Object.entries(targets).map(([id,e])=>{const r=e.getBoundingClientRect();return [id,{x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom,hidden:e.hidden}];}));}''')
                for name in ('appVersion','pauseControl','yandexStatus','yandexVerification'):
                    rect=rects[name]
                    if rect['hidden']:continue
                    self.assertGreater(rect['width'],0,(width,zoom,phase,name,rect))
                    self.assertLessEqual(rect['right'],width+1,(width,zoom,phase,name,rect))
                if not rects['yandexVerification']['hidden']:
                    self.assertGreaterEqual(rects['yandexVerification']['height'],24)
                    self.assertGreaterEqual(rects['yandexVerification']['width'],24)
                    self.assertGreaterEqual(rects['yandexVerification']['y'],rects['yandexStatus']['bottom']-1)
                    self.assertGreaterEqual(rects['previousBatches']['y'],rects['yandexVerification']['bottom']-1)
                self.assertGreaterEqual(rects['pauseControl']['y'],rects['appVersion']['bottom']+7)
                rows.append({'viewport_width':width,'zoom':zoom,'phase':phase,'rects':rects})
            self.render(phase='required');self.page.keyboard.press('Tab');self.page.locator('#yandexVerification').focus()
            focus=self.page.locator('#yandexVerification').evaluate('(e)=>{const s=getComputedStyle(e);return {outline:s.outline,offset:s.outlineOffset,background:s.backgroundColor,color:s.color,focusVisible:e.matches(":focus-visible")}}')
            self.assertTrue(focus['focusVisible']);self.assertIn('2px',focus['outline'])
            rows.append({'viewport_width':width,'zoom':zoom,'focused_yandex':focus})
            self.page.screenshot(path=str(output/f'ui-{width}-{zoom}.png'),full_page=True)
            self.page.evaluate("document.querySelector('#review').showModal()")
            self.assertTrue(self.page.locator('#review').is_visible())
            self.assertTrue(self.page.evaluate("document.querySelector('#review').contains(document.activeElement)"))
            self.page.screenshot(path=str(output/f'dialog-{width}-{zoom}.png'))
            self.page.evaluate("document.querySelector('#review').close()")
        (output/'ui-rects.json').write_text(json.dumps(rows,indent=2))


if __name__=='__main__':unittest.main()
