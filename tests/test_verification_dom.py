"""Actual offline DOM: delayed transport, preserved history and Lens outcomes."""
import json
import os
import unittest
import urllib.parse
from pathlib import Path
from test_yandex_dom import YandexDOMTests


@unittest.skipUnless(os.environ.get('COMICS_TEST_CDP'),'Requires owned offline headless fixture')
class VerificationDOMTests(YandexDOMTests):
    def setUp(self):
        super().setUp()
        self.root=Path(__file__).resolve().parents[1]
        self.lens={'engine':'google_lens','phase':'required','human_verification':True,'window':'closed','alive':True,'updated':1,'verification_pending':False,'control':{}}
        self.yandex={'engine':'yandex','phase':'required','human_verification':True,'window':'closed','alive':True,'availability':'available','retry_at':0}
        self.posts=[];self.gets={};self.pending={};self.delay=set();self.failed=set();self.revision='one';self.completed=[{'folder':'Fixture '+str(i),'updated':i} for i in range(6000)]
        self.context.add_init_script('window.setInterval=()=>0;')
        self.page.route('https://comics-fixture.invalid/**',self.route)
        self.page.goto('https://comics-fixture.invalid/')
        self.page.wait_for_function("document.querySelector('#browserResume').textContent==='Open Google Lens verification' && !document.querySelector('#browserResume').hidden && document.querySelector('#completedBatches').children.length===6000")

    def route(self,route):
        parsed=urllib.parse.urlparse(route.request.url);path=parsed.path
        if path=='/':return route.fulfill(body=(self.root/'static/index.html').read_text(encoding='utf-8'),content_type='text/html')
        if path=='/lens-control.js':return route.fulfill(body=(self.root/'static/lens-control.js').read_text(encoding='utf-8'),content_type='text/javascript')
        if path=='/reverse-image.js':return route.fulfill(body='',content_type='text/javascript')
        self.gets[path]=self.gets.get(path,0)+1
        if path in self.delay:self.pending[path]=route;return
        if path in self.failed:return route.fulfill(status=503,json={'error':'Fixture unavailable'})
        if path=='/api/state':data={'version':'0.1.1','roots':[],'job':{'message':'Ready','running':False,'visited':0,'changed':0},'counts':{},'totals':{}}
        elif path=='/api/comics':data={'rows':[],'total':0}
        elif path=='/api/browser-verification':data=dict(self.lens,yandex=self.yandex)
        elif path=='/api/progress':
            data={'queue':{'alive':True},'timestamp':1,'completed_revision':self.revision}
            if urllib.parse.parse_qs(parsed.query).get('completed_revision')!=[self.revision]:data['completed']=self.completed
        elif path in {'/api/browser-resume','/api/yandex-verification'}:
            self.posts.append(path)
            target=self.lens if path.endswith('browser-resume') else self.yandex
            target.update(phase='queued',verification_pending=True,updated=target.get('updated',0)+1)
            data={'ok':True,'state':'queued'}
        else:return route.abort()
        route.fulfill(json=data)

    def render(self,**changes):
        self.lens.update(changes);self.lens['updated']+=1
        self.page.evaluate('v=>LensControl.render(v)',self.lens)
        return self.page.locator('#browserStatus').inner_text()

    def test_engine_labels_tooltips_all_states_and_recovery(self):
        for phase,label in [('required','Open Google Lens verification'),('queued','Google Lens verification queued'),('opening','Opening Google Lens verification…'),('open','Google Lens window open'),('closing','Closing Google Lens verification…'),('failed','Retry Google Lens verification')]:
            self.render(phase=phase,window='open' if phase=='open' else 'closed',verification_pending=phase in {'queued','opening','open','closing'},failure='open')
            button=self.page.locator('#browserResume');self.assertEqual(button.inner_text(),label)
            self.assertEqual(button.get_attribute('title'),self.page.locator('#browserHelp').inner_text())
            self.assertEqual(button.is_disabled(),phase in {'queued','opening','open','closing'})
        self.page.evaluate('LensControl.unavailable()');self.assertTrue(button.is_disabled());self.assertIn('Google Lens status unavailable',button.get_attribute('title'))
        self.render(phase='required');self.assertFalse(button.is_disabled())

    def test_lens_completion_needs_actually_rendered_google_search_control(self):
        import browser_search
        bodies=['<input name="q" style="opacity:0">','<div aria-hidden="true"><input name="q"></div>',
                '<input name="q" style="display:none">','<button style="opacity:0">Search by image</button>',
                '<input name="q">','<button>Search by image</button>']
        for index,body in enumerate(bodies):
            self.page.route('https://www.google.com/search',lambda route:route.fulfill(body='<p>Google Search</p>'+body,content_type='text/html'))
            self.page.goto('https://www.google.com/search')
            self.assertEqual(browser_search.verification_complete(self.page),index>=4)
            self.page.unroute('https://www.google.com/search')

    def test_failure_is_sticky_under_general_progress_and_older_status(self):
        self.render(phase='failed',failure='load');expected=self.page.locator('#browserStatus').inner_text()
        self.page.evaluate('progress()');self.assertEqual(self.page.locator('#browserStatus').inner_text(),expected)
        self.page.evaluate('v=>LensControl.render(v)',dict(self.lens,phase='required',updated=0))
        self.assertEqual(self.page.locator('#browserStatus').inner_text(),expected)
        self.failed.add('/api/progress');self.page.evaluate('progress()')
        self.assertEqual(self.page.locator('#browserStatus').inner_text(),expected)
        self.assertFalse(self.page.locator('#browserResume').is_disabled())

    def test_slow_progress_requests_do_not_overlap_or_block_lens_click(self):
        before=self.gets['/api/progress'];self.delay.add('/api/progress')
        self.page.evaluate('()=>{for(let i=0;i<20;i++)progress();return true}')
        self.page.wait_for_function("document.querySelector('#appVersion').textContent==='v0.1.1'")
        self.page.locator('#browserResume').click()
        self.page.wait_for_function("document.querySelector('#browserResume').textContent==='Google Lens verification queued'")
        self.assertEqual(self.gets['/api/progress']-before,1);self.assertEqual(self.posts,['/api/browser-resume'])
        self.delay.clear()
        self.pending['/api/progress'].fulfill(status=503,json={'error':'Fixture delayed failure'})
        self.page.evaluate('progress()')
        self.assertIn('queued',self.page.locator('#browserStatus').inner_text())

    def test_failed_disabled_retry_explains_closure_or_owner_wait(self):
        self.render(phase='failed',failure='interrupted',window='unknown')
        self.assertTrue(self.page.locator('#browserResume').is_disabled())
        self.assertEqual(self.page.locator('#browserResume').get_attribute('title'),'Google Lens verification cannot restart until its window is confirmed closed.')
        self.render(window='closed',alive=False)
        self.assertEqual(self.page.locator('#browserResume').get_attribute('title'),'Google Lens verification is unavailable. Waiting for its browser to become ready.')

    def test_full_history_only_changes_when_new_revision_arrives(self):
        self.page.evaluate("window.historyChanges=0;new MutationObserver(r=>historyChanges+=r.length).observe(document.querySelector('#completedBatches'),{childList:true})")
        for _ in range(3):self.page.evaluate('progress()')
        self.assertEqual(self.page.locator('#completedBatches p').count(),6000);self.assertEqual(self.page.evaluate('historyChanges'),0)
        self.completed.append({'folder':'Last retained record','updated':1});self.revision='two';self.page.evaluate('progress()')
        self.assertEqual(self.page.locator('#completedBatches p').count(),6001);self.assertEqual(self.page.evaluate('historyChanges'),1)

    def test_preclick_lens_status_cannot_reenable_action_after_post(self):
        stale=dict(self.lens,yandex=self.yandex);self.delay.add('/api/browser-verification')
        self.page.evaluate('()=>{verification();return true}')
        self.page.locator('#browserResume').click();self.assertEqual(self.posts,['/api/browser-resume'])
        self.page.evaluate("document.querySelector('#browserResume').click()")
        self.delay.clear();self.pending['/api/browser-verification'].fulfill(json=stale)
        self.page.wait_for_function("document.querySelector('#browserStatus').textContent.includes('queued') && document.querySelector('#browserResume').disabled")
        self.page.evaluate('refreshVerification()');self.assertEqual(self.posts,['/api/browser-resume'])

    def test_preclick_yandex_status_cannot_reenable_action_after_post(self):
        stale=dict(self.lens,yandex=dict(self.yandex));self.delay.add('/api/browser-verification')
        self.page.evaluate('()=>{verification();return true}')
        self.page.locator('#yandexVerification').click();self.assertEqual(self.posts,['/api/yandex-verification'])
        self.delay.clear();self.pending['/api/browser-verification'].fulfill(json=stale)
        self.page.evaluate('refreshVerification()')
        self.assertTrue(self.page.locator('#yandexVerification').is_disabled());self.assertIn('queued',self.page.locator('#yandexVerification').inner_text())

    def test_independent_status_failure_disables_then_recovers(self):
        self.failed.add('/api/browser-verification');self.page.evaluate('verification()')
        self.assertTrue(self.page.locator('#browserResume').is_disabled());self.assertIn('status unavailable',self.page.locator('#browserStatus').inner_text())
        self.failed.clear();self.page.evaluate('verification()');self.assertFalse(self.page.locator('#browserResume').is_disabled())

    def test_rejected_post_uses_healthy_authoritative_status(self):
        self.failed.add('/api/browser-resume');self.page.locator('#browserResume').click()
        self.page.evaluate('refreshVerification()')
        self.assertGreaterEqual(self.gets.get('/api/browser-resume',0),1)
        self.assertEqual(self.page.locator('#browserResume').inner_text(),'Open Google Lens verification')
        self.assertFalse(self.page.locator('#browserResume').is_disabled())
        self.assertNotIn('unavailable',self.page.locator('#browserStatus').inner_text())

    def test_keyboard_submission_and_success_keep_nearby_focus(self):
        button=self.page.locator('#browserResume');button.focus();button.press('Enter')
        self.page.wait_for_function("document.querySelector('#browserResume').disabled")
        self.render(phase='open',window='open');self.render(phase='verified',window='minimized',human_verification=False)
        self.assertEqual(self.page.evaluate('document.activeElement.id'),'browserStatus');self.assertTrue(button.is_hidden())
        self.page.keyboard.press('Tab');self.assertEqual(self.page.evaluate('document.activeElement.id'),'yandexVerification')

    def test_rectangles_and_copy_at_320_and_desktop(self):
        output=Path(os.environ['COMICS_TEST_EVIDENCE']);output.mkdir(parents=True,exist_ok=True);rows=[]
        for width in (320,1440):
            self.page.set_viewport_size({'width':width,'height':1100})
            for phase in ('required','queued','opening','open','closing','failed','verified','paused'):
                self.render(phase=phase,human_verification=phase!='verified',window='minimized' if phase=='verified' else 'closed',failure='load',paused=phase=='paused',verification_pending=phase in {'queued','opening','open'})
                data=self.page.evaluate('''() => ['browserStatus','browserResume','yandexStatus','yandexVerification'].map(id=>{const e=document.getElementById(id),r=e.getBoundingClientRect();return {id,hidden:e.hidden,text:e.textContent,x:r.x,y:r.y,width:r.width,height:r.height,scroll:e.scrollWidth,client:e.clientWidth}})''')
                for row in data:
                    if not row['hidden']:
                        self.assertLessEqual(row['x']+row['width'],width+1)
                        self.assertLessEqual(row['scroll'],row['client']+1)
                rows.append({'viewport':width,'phase':phase,'rects':data})
            self.render(phase='failed',human_verification=True,window='closed',failure='load',paused=False,verification_pending=False)
            self.page.locator('#browserResume').focus()
            self.page.screenshot(path=str(output/f'lens-{width}-focused.png'),full_page=False)
        (output/'lens-rectangles.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
