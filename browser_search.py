"""Project-owned Lens browser and optional quota-limited SerpApi fallback.

Only cover bytes leave the computer. All returned links are unverified leads.
Human-verification pages are reported, never solved automatically.
"""
import hashlib
import io
import json
import os
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image
import app
import reverse_image
import storage


class HumanVerification(Exception):
    def __init__(self,url):
        self.url=url
        super().__init__('Google requires human verification.')


def settings():
    path=app.BASE/'config.json'
    config=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    return config.get('browser_search',{})


def api_key():
    value=os.environ.get('SERPAPI_API_KEY','').strip()
    if value:return value
    config_path=app.BASE/'config.json'
    config=json.loads(config_path.read_text(encoding='utf-8')) if config_path.exists() else {}
    for path in (app.BASE/'.env',Path(config.get('env_file') or app.BASE/'.env')):
        if not path.is_file():continue
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            name,sep,value=line.partition('=')
            if sep and name.strip().upper()=='SERPAPI_API_KEY':return value.strip().strip('\"\'')
    return ''


def status(**changes):
    path=app.DATA/'browser-search.json'
    previous=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    if changes:
        previous.update(changes,timestamp=time.time());storage.save(path,previous)
    heartbeat=app.DATA/'browser-heartbeat'
    previous['alive']=heartbeat.exists() and time.time()-json.loads(heartbeat.read_text(encoding='utf-8'))['timestamp']<15
    return previous


def cover_bytes(path):
    data,_,_=reverse_image.cover(path,0)
    with Image.open(io.BytesIO(data)) as image:
        image=image.convert('RGB');image.thumbnail((1000,1000))
        output=io.BytesIO();image.save(output,'JPEG',quality=80)
    if len(output.getvalue())>500_000:raise ValueError('Cover is too large for image search.')
    return output.getvalue()


def normalize_links(items):
    found=[];seen=set()
    for item in items:
        url=item.get('url') or item.get('link') or ''
        p=urllib.parse.urlparse(url)
        if p.hostname in {'www.google.com','google.com'} and p.path=='/url':
            args=urllib.parse.parse_qs(p.query);url=(args.get('q') or args.get('url') or [''])[0];p=urllib.parse.urlparse(url)
        host=(p.hostname or '').lower()
        if p.scheme!='https' or not host or p.username or p.password:continue
        if host=='google.com' or host.endswith(('.google.com','.gstatic.com','.googleusercontent.com')):continue
        if host in {'support.google.com','accounts.google.com','policies.google.com','serpapi.com'}:continue
        if url in seen:continue
        seen.add(url);found.append({'url':url,'title':str(item.get('title') or host)[:300]})
    return found[:10]


def challenge(url,text):
    text=text.lower()
    return '/sorry/' in url or any(marker in text for marker in ('unusual traffic','verify you are human','confirm you are not a robot','making sure you’re not a bot','making sure you\'re not a bot'))


def reserve(provider,limit,period):
    if limit<=0:raise ValueError(provider+' request limit reached.')
    now=time.time()
    with app.db() as con:
        con.execute('CREATE TABLE IF NOT EXISTS image_search_requests(provider TEXT,period TEXT,timestamp REAL)')
        con.execute('BEGIN IMMEDIATE')
        count=con.execute('SELECT COUNT(*) FROM image_search_requests WHERE provider=? AND period=?',(provider,period)).fetchone()[0]
        if count>=limit:raise ValueError(provider+' request limit reached.')
        # Failed attempts count conservatively too.
        con.execute('INSERT INTO image_search_requests VALUES(?,?,?)',(provider,period,now))


def cached(data):
    key='browser-cover:v1:'+hashlib.sha256(data).hexdigest()
    with app.db() as con:
        row=con.execute('SELECT value FROM cache WHERE key=? AND fetched>?',(key,time.time()-30*86400)).fetchone()
    return key,json.loads(row['value']) if row else None


def save_cache(key,leads):
    # Empty results are retried later rather than cached for a month.
    if leads:
        with app.db() as con:con.execute('INSERT OR REPLACE INTO cache VALUES(?,?,?)',(key,json.dumps(leads),time.time()))


class LensBrowser:
    def __init__(self,options):
        from playwright.sync_api import sync_playwright
        self.runtime=sync_playwright().start();self.context=None;self.options=options

    def open(self,visible=False):
        if self.context:self.context.close()
        profile=app.DATA/'lens-profile';profile.mkdir(parents=True,exist_ok=True)
        import maintenance
        maintenance.browser_cache(profile)
        self.context=self.runtime.chromium.launch_persistent_context(str(profile),channel=self.options.get('channel','msedge'),headless=not visible,locale='en-US',accept_downloads=False,args=['--disk-cache-size=67108864','--media-cache-size=16777216'])
        self.page=self.context.pages[0] if self.context.pages else self.context.new_page()
        self.page.set_default_timeout(15_000)

    def check(self):
        if challenge(self.page.url,self.page.locator('body').inner_text(timeout=10_000)):
            raise HumanVerification(self.page.url)

    def search(self,data):
        if not self.context:self.open()
        self.page.goto('https://www.google.com/imghp?hl=en&safe=off',wait_until='domcontentloaded',timeout=45_000)
        self.check()
        reject=self.page.get_by_role('button',name='Reject all',exact=True)
        if reject.count() and reject.first.is_visible():reject.first.click()
        if not self.page.locator('input[type=file]').count():
            self.page.get_by_role('button',name='Search by image',exact=True).click()
        self.page.locator('input[type=file]').first.set_input_files({'name':'cover.jpg','mimeType':'image/jpeg','buffer':data})
        deadline=time.time()+60
        while time.time()<deadline:
            import pause_control
            if pause_control.requested():raise pause_control.PauseRequested()
            self.page.wait_for_timeout(1000);self.check()
            if '/search' not in self.page.url:continue
            # Capture only linked result cards, excluding navigation/footer links.
            items=self.page.locator('a[href]').evaluate_all("nodes => nodes.filter(a => a.querySelector('img')).map(a => ({url:a.href,title:a.innerText || a.getAttribute('aria-label') || a.querySelector('img')?.alt || ''}))")
            leads=normalize_links(items)
            if leads:return leads
        return []

    def human_session(self,url):
        p=urllib.parse.urlparse(url)
        if p.scheme!='https' or not (p.hostname=='google.com' or (p.hostname or '').endswith('.google.com')):
            raise ValueError('Verification URL is not a Google page.')
        self.open(visible=True)
        self.page.goto(url,wait_until='domcontentloaded',timeout=45_000)
        deadline=time.time()+600
        while time.time()<deadline:
            import pause_control
            if pause_control.requested():return False
            self.page.wait_for_timeout(2000)
            if not challenge(self.page.url,self.page.locator('body').inner_text()):
                # Keep the browser the user just verified, including its session.
                return True
        self.open();return False

    def close(self):
        if self.context:self.context.close()
        self.runtime.stop()
        import maintenance
        maintenance.browser_cache(app.DATA/'lens-profile')


def request_json(request):
    try:
        with urllib.request.urlopen(request,timeout=60) as response:
            raw=response.read(5_000_001)
        if len(raw)>5_000_000:raise ValueError()
        value=json.loads(raw)
        if value.get('error'):raise ValueError()
        return value
    except Exception:
        # Do not propagate request URLs, API keys or returned account details.
        raise ValueError('SerpApi request failed; check account availability.') from None


def serpapi_search(data,options):
    key=api_key()
    if not key or not options.get('serpapi_fallback'):raise ValueError('SerpApi fallback is not configured.')
    reserve('serpapi',min(250,int(options.get('serpapi_monthly_limit',250))),datetime.now(timezone.utc).strftime('%Y-%m'))
    boundary='ComicCover'+uuid.uuid4().hex
    body=(f'--{boundary}\r\nContent-Disposition: form-data; name="api_key"\r\n\r\n{key}\r\n--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="cover.jpg"\r\nContent-Type: image/jpeg\r\n\r\n'.encode()+data+f'\r\n--{boundary}--\r\n'.encode())
    upload=request_json(urllib.request.Request('https://serpapi.com/image',data=body,headers={'Content-Type':'multipart/form-data; boundary='+boundary}))
    image_id=upload.get('image_id')
    if not isinstance(image_id,str) or not image_id:raise ValueError('SerpApi upload did not return an image identifier.')
    params=urllib.parse.urlencode({'engine':'google_lens','image_id':image_id,'api_key':key,'hl':'en','safe':'off','type':'all'})
    result=request_json(urllib.request.Request('https://serpapi.com/search.json?'+params))
    return normalize_links(result.get('visual_matches',[])+result.get('exact_matches',[]))
