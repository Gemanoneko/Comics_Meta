"""The real GCD panel in an owned, offline browser; picker and HTTP are fixtures."""
import json
import os
import re
import unittest
import urllib.parse
from pathlib import Path
from test_shell_ui_dom import HeadlessPage

ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.environ.get('COMICS_TEST_CDP'),'Requires canonical owned headless browser')
class GcdDOMTests(HeadlessPage):
    def setUp(self):
        super().setUp()
        self.state={'current':None,'attempt':None}
        self.preview={'path':'C:/Downloads/'+('long-path-'*20)+'current.zip','file_name':'current.zip','dump_date':'2026-10-16','size':1_900_000_000,'needed':7_500_000_000,'free':10_000_000_000,'drive':'C:', 'relation':'newer'}
        self.posts=[];self.fail=False
        self.context.add_init_script('window.setInterval=()=>0;window.comicDesktop={browseGcd:async()=>"C:/Downloads/current.zip"};')
        self.page.route('https://gcd-fixture.invalid/**',self.route)

    def route(self,route):
        path=urllib.parse.urlparse(route.request.url).path
        if path=='/':
            source=(ROOT/'static/index.html').read_text(encoding='utf8')
            style=re.search(r'<style>(.*?)</style>',source,re.S)[1]
            panel=source[source.index('<section class="panel gcd-panel"'):]
            panel=panel[:panel.index('</section>')+10]
            return route.fulfill(content_type='text/html; charset=utf-8',body='<html><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><style>'+style+'</style><link rel="stylesheet" href="/gcd-offline.css">'+panel+'<script src="/gcd-offline.js"></script></html>')
        if path in ('/gcd-offline.js','/gcd-offline.css'):
            return route.fulfill(content_type='text/css; charset=utf-8' if path.endswith('.css') else 'text/javascript; charset=utf-8',body=(ROOT/'static'/path[1:]).read_text(encoding='utf8'))
        if path=='/api/gcd-offline':return route.fulfill(status=503 if self.fail else 200,json=self.state)
        data=json.loads(route.request.post_data or '{}');self.posts.append((path,data))
        if path.endswith('/inspect'):return route.fulfill(status=400 if 'code' in self.preview else 200,json=self.preview)
        if path.endswith('/build'):
            self.state['attempt']={'id':'build','state':'building','stage':2,'stage_percent':10,'overall_percent':None,'elapsed_seconds':5}
            return route.fulfill(json=self.state)
        if path.endswith('/cancel'):
            self.state['attempt']={'id':'build','state':'cancelled','code':'cancelled'}
            return route.fulfill(json=self.state)
        route.abort()

    def ready(self,age=13):
        self.state={'current':{'index':'fixture','dump_date':'2026-10-16','built':1_793_180_000,'file_name':'current.zip','age_days':age},'attempt':None}

    def open(self,width=640):
        self.page.set_viewport_size({'width':width,'height':1000})
        self.page.goto('https://gcd-fixture.invalid/')
        self.page.wait_for_function("document.querySelector('[data-summary]').textContent!=='Checking…'")
        self.page.locator('#gcdPanel>details').evaluate('(n)=>n.open=true')

    def rects(self):
        result=self.page.evaluate('''()=>{
          const panel=document.querySelector('#gcdPanel').getBoundingClientRect();
          const rects=[...document.querySelectorAll('#gcdPanel button,#gcdPanel input,#gcdPanel summary,#gcdPanel a')].filter(n=>n.checkVisibility()).map(n=>{const r=n.getBoundingClientRect();return {name:n.textContent||n.title,tag:n.tagName,x:r.x,y:r.y,width:r.width,height:r.height};});
          const overlaps=[];for(let i=0;i<rects.length;i++)for(let j=i+1;j<rects.length;j++){const a=rects[i],b=rects[j];if(Math.min(a.x+a.width,b.x+b.width)>Math.max(a.x,b.x)+.5&&Math.min(a.y+a.height,b.y+b.height)>Math.max(a.y,b.y)+.5)overlaps.push([a.name,b.name]);}
          return {rects,overlaps,overflow:document.documentElement.scrollWidth-document.documentElement.clientWidth,left:panel.left,right:panel.right};}''')
        self.assertEqual(result['overflow'],0,result)
        self.assertEqual(result['overlaps'],[],result)
        for rect in result['rects']:
            self.assertGreaterEqual(rect['width'],24,rect)
            self.assertGreaterEqual(rect['height'],32 if rect['tag']=='BUTTON' else 24,rect)
            self.assertGreaterEqual(rect['x'],result['left']-.5,rect)
            self.assertLessEqual(rect['x']+rect['width'],result['right']+.5,rect)
        return result

    def test_age_boundary_guidance_and_all_preview_layouts(self):
        evidence=[]
        for width in (320,640):
            self.ready(13);self.open(width)
            self.assertNotIn('This dump is',self.page.locator('#gcdPanel').inner_text())
            self.ready(14);self.page.evaluate('()=>GcdOffline.refresh()')
            self.assertIn('This dump is 14 days old',self.page.locator('#gcdPanel').inner_text())
            self.page.locator('.gcd-help').evaluate('(n)=>n.open=true')
            self.assertIn('Download SQLite Dump',self.page.locator('.gcd-help').inner_text())
            evidence.append(self.rects())
            if width==640 and os.environ.get('COMICS_META_TEST_SCRATCH'):
                self.page.locator('#gcdPanel').screenshot(path=str(Path(os.environ['COMICS_META_TEST_SCRATCH'])/'gcd-ready-14-days.png'))
            for relation,label in (('newer','Build index'),('same_dump','Rebuild index'),('older_dump','Use older dump')):
                self.preview['relation']=relation
                self.page.get_by_role('button',name='Choose GCD file',exact=True).click()
                self.page.get_by_role('button',name=label,exact=True).wait_for()
                evidence.append(self.rects())
                self.page.get_by_role('button',name='Cancel',exact=True).click()
            self.page.locator('#gcdPanel>details').evaluate('(n)=>n.open=false')
            self.assertFalse(self.page.get_by_role('button',name='Choose GCD file',exact=True).is_visible())
        if os.environ.get('COMICS_META_TEST_SCRATCH'):
            (Path(os.environ['COMICS_META_TEST_SCRATCH'])/'gcd-ui-rects.json').write_text(json.dumps(evidence,indent=2),encoding='utf8')

    def test_build_cancel_keyboard_focus_and_terminal_error_layouts(self):
        self.open(320)
        self.page.get_by_role('button',name='Choose GCD file',exact=True).focus()
        self.page.keyboard.press('Enter')
        self.page.get_by_role('button',name='Build index',exact=True).wait_for()
        self.assertEqual(self.page.evaluate('document.activeElement.tagName'),'H3')
        self.page.get_by_role('button',name='Build index',exact=True).focus();self.page.keyboard.press('Enter')
        self.page.get_by_role('button',name='Cancel update').wait_for()
        self.assertEqual(sum(p[0].endswith('/build') for p in self.posts),1)
        self.rects()
        self.page.get_by_role('button',name='Cancel update').click()
        self.page.get_by_role('button',name='Choose GCD file',exact=True).wait_for()
        self.assertIn('GCD update cancelled.',self.page.locator('#gcdPanel').inner_text())
        for code in ('zip_missing','not_a_zip','not_gcd_dump','schema_unsupported','interrupted','build_failed'):
            self.state['attempt']={'id':code,'state':'failed','code':code}
            self.page.evaluate('()=>GcdOffline.refresh()');self.rects()
        self.fail=True;self.page.evaluate('()=>GcdOffline.refresh()')
        self.assertIn('Status unavailable',self.page.locator('[data-summary]').inner_text())
        self.rects()
