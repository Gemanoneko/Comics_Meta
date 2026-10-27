"""Project-owned Lens browser.

Only cover bytes leave the computer. All returned links are unverified leads.
Human-verification pages are reported, never solved automatically.
"""
import hashlib
import io
import json
import os
import time
import urllib.parse
from PIL import Image
import app
import reverse_image
import storage
import threading

VERIFICATION_LOCK=threading.Lock()
# Worker-only state: the challenge URL and the comic whose search hit it.
# Neither may enter a dashboard/API response.
PRIVATE_KEYS=('verification_url','verification_task')


def public(state):
    """Copy of cover status that is safe for the local HTTP API."""
    return {key:value for key,value in dict(state).items() if key not in PRIVATE_KEYS}


class HumanVerification(Exception):
    def __init__(self,url):
        self.url=url
        super().__init__('Google requires human verification.')


def settings():
    options=app.load_config().get('browser_search',{})
    options=dict(options) if isinstance(options,dict) else {}
    import pipeline_config
    # Enrichment E: Lens runs only with its own opt-in, whatever the older "enabled" key says.
    options['enabled']=bool(options.get('enabled')) and pipeline_config.lens_enabled()
    return options


def legacy_status(**changes):
    path=app.DATA/'browser-search.json'
    previous=json.loads(storage.read_text(path)) if path.exists() else {}
    if changes:
        previous.update(changes,timestamp=time.time());storage.save(path,previous)
    heartbeat=app.DATA/'browser-heartbeat'
    # The worker's heartbeat thread replaces this file every 2 s; a plain read
    # meeting that replace crashed the worker at start (installed 0.2.1 QA, M3).
    previous['alive']=heartbeat.exists() and time.time()-json.loads(storage.read_text(heartbeat))['timestamp']<15
    previous['verification_pending']=(app.DATA/'browser-resume').exists() or (previous['alive'] and previous.get('human_verification') and previous.get('verification_state') in ('opening','open'))
    return previous

def status(**changes):
    previous=legacy_status(**changes)
    import lens_verification
    current=lens_verification.status()
    if current.get('request_id'):
        previous.update(verification_state=current['phase'],verification_window=current['window'],
                        verification_pending=current['verification_pending'],verification=current)
    return previous

def request_verification():
    import lens_verification
    return lens_verification.request()


def cover_bytes(path):
    data,_,_=reverse_image.cover(path,0)
    with Image.open(io.BytesIO(data),formats=('JPEG','PNG','WEBP')) as image:  # Never EPS/Ghostscript (review F1).
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
        if host in {'support.google.com','accounts.google.com','policies.google.com'}:continue
        if url in seen:continue
        seen.add(url);found.append({'url':url,'title':str(item.get('title') or host)[:300]})
    return found[:10]


def challenge(url,text):
    text=text.lower()
    return '/sorry/' in url or any(marker in text for marker in ('unusual traffic','verify you are human','confirm you are not a robot','making sure you’re not a bot','making sure you\'re not a bot'))


LENS_VISIBLE = '''nodes => nodes.slice(0,20).some(element => {
    const rect=element.getBoundingClientRect();
    if (!rect.width || !rect.height) return false;
    for(let node=element;node;node=node.parentElement){
        const style=getComputedStyle(node);
        if(node.hidden || node.getAttribute('aria-hidden')==='true' || style.display==='none' ||
           style.visibility==='hidden' || style.visibility==='collapse' || Number(style.opacity)===0)return false;
    }
    return true;
})'''


RESULT_LINKS="nodes => nodes.filter(a => a.querySelector('img')).map(a => ({url:a.href,title:a.innerText || a.getAttribute('aria-label') || a.querySelector('img')?.alt || ''}))"


def result_leads(page):
    """Linked result cards only, excluding navigation/footer links."""
    return normalize_links(page.locator('a[href]').evaluate_all(RESULT_LINKS))


# A post-solve redirect settles within seconds. Errors that keep coming for
# longer than this are a broken page, reported with their error class.
TRANSIENT_ERROR_LIMIT=30
TRANSIENT_ERROR_SECONDS=60


def transient_page_error(page,exc):
    """A page read interrupted by navigation, not a failed verification.

    After a solved check Google redirects to the original results; reads made
    while that document is replaced can time out or lose their context.
    A closed window is never transient.
    """
    try:
        from playwright.sync_api import Error as PlaywrightError
    except ImportError:return False
    if not isinstance(exc,PlaywrightError):return False
    try:return not page.is_closed()
    except Exception:return False


def verification_complete(page):
    """Only a usable Google search page proves the human challenge ended."""
    p=urllib.parse.urlparse(page.url)
    if (p.scheme!='https' or p.hostname not in {'google.com','www.google.com','lens.google.com'}
            or p.username or p.password or p.port not in (None,443)
            or p.path.rstrip('/') not in {'','/search','/imghp'}):return False
    text=page.locator('body').inner_text(timeout=10_000).strip()
    if not text or challenge(page.url,text) or any(value in text.lower() for value in ('this site can’t be reached','this site cannot be reached','something went wrong','internal server error')):return False
    fields=page.locator('input[name="q"], textarea[name="q"]')
    if fields.evaluate_all(LENS_VISIBLE):return True
    button=page.get_by_role('button',name='Search by image',exact=True)
    return bool(button.evaluate_all(LENS_VISIBLE))


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
        self.runtime=None;self.context=None;self.options=options;self.leased=False
        self.verified_leads=[]

    def open(self,visible=False,admitted=lambda:None):
        from playwright.sync_api import sync_playwright
        import lens_browser_owner
        admitted();self.close();admitted()
        profile=lens_browser_owner.acquire();self.leased=True;self.profile=profile
        try:
            import maintenance
            maintenance.browser_cache(profile)
            admitted();self.runtime=sync_playwright().start();admitted()
            self.context=self.runtime.chromium.launch_persistent_context(str(profile),channel=self.options.get('channel','msedge'),headless=not visible,locale='en-US',accept_downloads=False,args=['--disk-cache-size=67108864','--media-cache-size=16777216'])
            admitted()
            self.page=self.context.pages[0] if self.context.pages else self.context.new_page()
            self.page.set_default_timeout(15_000)
        except BaseException:
            self.close();raise

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
            leads=result_leads(self.page)
            if leads:return leads
        return []

    def human_session(self,url,admitted=lambda:None,observation=lambda stage:None):
        p=urllib.parse.urlparse(url)
        if (p.scheme!='https' or p.username or p.password or p.port not in (None,443)
                or len(url)>8192 or any(ord(c)<=32 or ord(c)==127 for c in url)
                or not (p.hostname=='google.com' or (p.hostname or '').endswith('.google.com'))):
            raise ValueError('Verification URL is not a Google page.')
        admitted();observation('launch');self.open(visible=True,admitted=admitted)
        admitted();observation('load')
        self.page.goto(url,wait_until='domcontentloaded',timeout=45_000)
        admitted();observation('observe')
        self.verified_leads=[]
        deadline=time.monotonic()+600
        errors=0;first_error=None
        while time.monotonic()<deadline:
            admitted();self.page.wait_for_timeout(500);admitted()
            try:done=verification_complete(self.page)
            except Exception as exc:
                # The post-solve redirect can interrupt a probe; keep observing.
                if not transient_page_error(self.page,exc):raise
                errors+=1
                if first_error is None:first_error=time.monotonic()
                if errors>=TRANSIENT_ERROR_LIMIT or time.monotonic()-first_error>=TRANSIENT_ERROR_SECONDS:raise
                continue
            errors=0;first_error=None
            if done:
                # Keep the browser the user just verified, including its session.
                self.verified_leads=self.verified_page_leads(admitted)
                return True
        return False

    def verified_page_leads(self,admitted,seconds=20):
        """Read the results page Google loads after a solved check.

        These are the original Lens results for the search that hit the check.
        A failure here never turns a completed verification into a failed one.
        """
        deadline=time.monotonic()+seconds
        while True:
            admitted()
            try:
                if urllib.parse.urlparse(self.page.url).path.rstrip('/')!='/search':return []
                leads=result_leads(self.page)
                if leads or time.monotonic()>=deadline:return leads
                self.page.wait_for_timeout(1000)
            except Exception as exc:
                import pause_control
                if isinstance(exc,pause_control.PauseRequested):raise
                if not transient_page_error(self.page,exc) or time.monotonic()>=deadline:return []
                time.sleep(.5)  # Let the redirect settle instead of re-reading at once.

    def alive(self):
        """The browser window is still open; the user may have closed it."""
        try:return self.context is not None and getattr(self,'page',None) is not None and not self.page.is_closed()
        except Exception:return False

    def minimize(self):
        """Keep the verified browser session intact while hiding its window."""
        try:
            session=self.context.new_cdp_session(self.page)
            try:
                window=session.send('Browser.getWindowForTarget')
                session.send('Browser.setWindowBounds',{'windowId':window['windowId'],'bounds':{'windowState':'minimized'}})
                return True
            finally:session.detach()
        except Exception:return False

    def close(self):
        import lens_browser_owner
        if not self.leased and self.runtime is None and self.context is None:return
        try:
            if self.context:self.context.close()
        finally:
            try:
                if self.runtime:self.runtime.stop()
            finally:
                if self.leased:
                    # No cache access until descendants are proven closed and
                    # the exact leased profile is revalidated. Keep the lock
                    # throughout cleanup, including failed launch cleanup.
                    lens_browser_owner.closed()
                    try:
                        profile=lens_browser_owner.checked_profile()
                        if profile!=self.profile:raise ValueError('Lens profile changed while leased.')
                        import maintenance
                        maintenance.browser_cache(profile)
                    finally:lens_browser_owner.release()
        self.context=None;self.runtime=None;self.leased=False
        import lens_verification
        lens_verification.session_closed()
