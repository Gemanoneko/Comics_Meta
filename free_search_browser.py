"""Ordinary DuckDuckGo results in a dedicated, bounded browser session."""
import base64
import ipaddress
import os
import re
import sys
import threading
import time
import urllib.parse
from pathlib import Path
import app


class BrowserUnavailable(ValueError):
    pass


_mutex = threading.Lock()
_job = None  # Deliberately held until process exit; never inherited by children.
_query_job = None
_retained = []  # Unknown closure retains both profile locks until worker exits.
_worker_owner = None


def enable_worker_owner():
    """Only worker.main calls this after acquiring its serial metadata lease."""
    global _worker_owner
    if Path(sys.argv[0]).resolve()!= (app.BASE/'worker.py').resolve():
        raise BrowserUnavailable('Regular search registration requires the metadata worker entry point.')
    _worker_owner=os.getpid()


def own_descendants():
    """Fail closed before launch unless Windows will close our browser descendants."""
    global _job,_query_job
    if _worker_owner!=os.getpid():raise BrowserUnavailable('Regular search is owned by the metadata worker; no browser launched.')
    if os.name != 'nt':
        raise BrowserUnavailable('Regular search requires the supported Windows browser owner.')
    if _job is not None:return
    import ctypes
    from ctypes import wintypes as w
    class Limits(ctypes.Structure):
        _fields_=[('process_time',ctypes.c_int64),('job_time',ctypes.c_int64),('flags',w.DWORD),
                  ('min_ws',ctypes.c_size_t),('max_ws',ctypes.c_size_t),('active',w.DWORD),
                  ('affinity',ctypes.c_size_t),('priority',w.DWORD),('scheduling',w.DWORD)]
    class Counters(ctypes.Structure):
        _fields_=[(name,ctypes.c_uint64) for name in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]
    class Extended(ctypes.Structure):
        _fields_=[('limits',Limits),('io',Counters),('process_memory',ctypes.c_size_t),
                  ('job_memory',ctypes.c_size_t),('peak_process',ctypes.c_size_t),('peak_job',ctypes.c_size_t)]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,w.LPCWSTR];kernel.CreateJobObjectW.restype=w.HANDLE
    kernel.SetInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD];kernel.SetInformationJobObject.restype=w.BOOL
    kernel.GetCurrentProcess.restype=w.HANDLE
    kernel.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE];kernel.AssignProcessToJobObject.restype=w.BOOL
    kernel.CloseHandle.argtypes=[w.HANDLE];kernel.CloseHandle.restype=w.BOOL
    kernel.QueryInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD,ctypes.c_void_p];kernel.QueryInformationJobObject.restype=w.BOOL
    handle=kernel.CreateJobObjectW(None,None)
    info=Extended();info.limits.flags=0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not handle:raise BrowserUnavailable('Browser ownership is unavailable; no browser launched.')
    if not kernel.SetInformationJobObject(handle,9,ctypes.byref(info),ctypes.sizeof(info)) or not kernel.AssignProcessToJobObject(handle,kernel.GetCurrentProcess()):
        kernel.CloseHandle(handle)
        raise BrowserUnavailable('Browser ownership is unavailable; no browser launched.')
    _job=handle
    class Accounting(ctypes.Structure):
        _fields_=[(name,ctypes.c_int64) for name in ('user','kernel','period_user','period_kernel')]+[(name,w.DWORD) for name in ('faults','total','active','terminated')]
    def active():
        info=Accounting()
        if not kernel.QueryInformationJobObject(handle,1,ctypes.byref(info),ctypes.sizeof(info),None):
            raise BrowserUnavailable('Browser descendant closure cannot be verified.')
        return info.active
    _query_job=active


ENGINES={
    'ddg':{'base':'https://duckduckgo.com/','profile':'ddg-profile','selector':'li[data-layout="organic"] article[data-testid="result"] h2 a[data-testid="result-title-a"]','empty_selector':'[data-testid="no-results"]',
           'hosts':('duckduckgo.com','www.duckduckgo.com','links.duckduckgo.com','improving.duckduckgo.com','external-content.duckduckgo.com')},
    'bing':{'base':'https://www.bing.com/search','profile':'bing-profile','selector':'ol#b_results > li.b_algo h2 a','empty_selector':'ol#b_results > li.b_no',
            'hosts':('bing.com','www.bing.com','r.bing.com','th.bing.com','ts1.mm.bing.net','ts2.mm.bing.net','ts3.mm.bing.net','ts4.mm.bing.net')}
}


# Readiness and extraction share one DOM observation: an attached hidden card
# is not a rendered result. Bound inspection before returning five safe links.
RESULTS_READY = r'''({selector, emptySelector, query}) => {
    const clean = value => value.replace(/\s+/g, ' ').trim();
    const visible = element => {
        const rect = element.getBoundingClientRect();
        if (!rect.width || !rect.height) return false;
        for (let node = element; node; node = node.parentElement) {
            const style = getComputedStyle(node);
            if (style.display === 'none' || style.visibility === 'hidden' ||
                style.visibility === 'collapse' || Number(style.opacity) === 0 ||
                node.hidden || node.getAttribute('aria-hidden') === 'true') return false;
        }
        return true;
    };
    const renderedText = element => {
        const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
        const parts = [];
        for (let node = walker.nextNode(), inspected = 0; node && inspected < 100; node = walker.nextNode(), inspected++) {
            if (!node.textContent.trim() || !visible(node.parentElement)) continue;
            const range = document.createRange();
            range.selectNodeContents(node);
            const rect = range.getBoundingClientRect();
            if (rect.width && rect.height) parts.push(node.textContent);
        }
        return clean(parts.join(' '));
    };
    const inputs = [...document.querySelectorAll('input[name="q"], textarea[name="q"]')];
    const shown = inputs.filter(visible);
    if (!shown.length || !shown.every(input => clean(input.value) === clean(query))) return false;
    const nodes = [...document.querySelectorAll(selector)].slice(0, 100);
    const items = nodes.filter(visible).map(a => ({url: a.href, title: renderedText(a)}))
        .filter(item => item.title).slice(0, 10);
    if (items.length) return {items};
    // An explicit rendered empty-state is distinct from hidden/unready cards.
    const empty = [...document.querySelectorAll(emptySelector)].filter(visible);
    if (!nodes.length && empty.some(node => /\b(?:no results (?:found|for)|there are no results for)\b/i.test(renderedText(node))))
        return {items: []};
    return false;
}'''


def rendered_results(page,query,engine):
    def correct_query():
        url=urllib.parse.urlparse(page.url)
        expected=urllib.parse.urlparse(ENGINES[engine]['base'])
        return (url.scheme=='https' and url.hostname in ENGINES[engine]['hosts'][:2]
                and url.path==expected.path and urllib.parse.parse_qs(url.query).get('q')==[query])
    if not correct_query():
        raise BrowserUnavailable('Regular free search returned a different page or query; no results accepted.')
    handle=None
    try:
        handle=page.wait_for_function(RESULTS_READY,arg={'selector':ENGINES[engine]['selector'],'emptySelector':ENGINES[engine]['empty_selector'],'query':query},timeout=15_000)
        result=handle.json_value()
    except Exception:
        if challenge(page.url,page.locator('body').inner_text(timeout=10_000),engine):
            raise BrowserUnavailable('Free search requested human verification; no bypass attempted.') from None
        raise BrowserUnavailable('Regular free search did not render usable visible titles for the requested query.') from None
    finally:
        if handle:handle.dispose()
    if not correct_query():
        raise BrowserUnavailable('Regular free search changed its page or query; no results accepted.')
    if challenge(page.url,page.locator('body').inner_text(timeout=10_000),engine):
        raise BrowserUnavailable('Free search requested human verification; no bypass attempted.')
    links=normalize_links(result['items'],engine)
    if result['items'] and not links:
        raise BrowserUnavailable('Regular free search rendered no usable public result links.')
    return links


def challenge(url,text,engine='ddg'):
    parsed=urllib.parse.urlparse(url)
    if engine=='bing':
        return any(part in parsed.path.lower() for part in ('/captcha','/challenge','/sorry')) or any(marker in text.lower() for marker in
                ('verify you are human','unusual traffic from your','verify that you are not a robot','enter the characters you see'))
    return ('anomaly' in parsed.path.lower() or any(marker in text.lower() for marker in
            ('bots use duckduckgo','verify you are human','complete the following challenge','anomaly.js')))


def normalize_links(items,engine='ddg'):
    if engine not in ENGINES:raise BrowserUnavailable('Unsupported free search engine.')
    result=[];seen=set()
    for item in items:
        try:
            title=item.get('title','').strip()
            if not title:continue
            url=urllib.parse.urljoin(ENGINES[engine]['base'],item.get('url',''))
            if len(url)>8192:continue
            parsed=urllib.parse.urlparse(url)
            if engine=='bing' and parsed.hostname=='www.bing.com' and parsed.path=='/ck/a':
                redirect=urllib.parse.parse_qs(parsed.query).get('u',[])
                if len(redirect)!=1 or not redirect[0].startswith('a1'):continue
                encoded=redirect[0][2:]
                if len(encoded)>5500 or not re.fullmatch(r'[A-Za-z0-9_-]+={0,2}',encoded):continue
                url=base64.b64decode(encoded+'='*((-len(encoded))%4),altchars=b'-_',validate=True).decode('utf-8',errors='strict')
                parsed=urllib.parse.urlparse(url)
            elif engine=='ddg':
                redirect=urllib.parse.parse_qs(parsed.query).get('uddg')
                if redirect:url=redirect[0];parsed=urllib.parse.urlparse(url)
            host=(parsed.hostname or '').lower().rstrip('.')
            if len(url)>4096 or any(ord(c)<=32 or ord(c)==127 for c in url) or parsed.scheme!='https' or not host or parsed.username or parsed.password or parsed.port not in (None,443):continue
            if host in ('duckduckgo.com','bing.com') or host.endswith(('.duckduckgo.com','.bing.com','.bing.net')):continue
            if host=='localhost' or host.endswith(('.localhost','.local','.internal')):continue
            try:
                if not ipaddress.ip_address(host).is_global:continue
            except ValueError:
                if re.fullmatch(r'[0-9.]+',host):continue
        except (ValueError,UnicodeError):continue
        if url in seen:continue
        seen.add(url);result.append({'url':url,'title':title[:500]})
        if len(result)==5:break
    return result


def checked_profile(engine='ddg'):
    if engine not in ENGINES:raise BrowserUnavailable('Unsupported free search engine.')
    name=ENGINES[engine]['profile']
    profile=app.DATA/name
    # Never attach to a user/Lens profile or follow a planted link.
    for path in (app.DATA,profile,app.DATA/(name+'.lock')):
        if path.is_symlink() or (hasattr(path,'is_junction') and path.is_junction()):
            raise BrowserUnavailable('Dedicated search profile is linked; browser not launched.')
    app.DATA.mkdir(parents=True,exist_ok=True)
    if profile.resolve().parent!=app.DATA.resolve():raise BrowserUnavailable('Invalid dedicated search profile.')
    return profile


def search(query,engine='ddg'):
    if engine not in ENGINES:raise BrowserUnavailable('Unsupported free search engine.')
    if not _mutex.acquire(blocking=False):raise BrowserUnavailable('Dedicated search browser is already owned.')
    lock=None;runtime=None;context=None;locked=False;owned=False
    try:
        profile=checked_profile(engine)
        lock=(app.DATA/(ENGINES[engine]['profile']+'.lock')).open('a+b')
        if lock.tell()==0:lock.write(b'0');lock.flush()
        lock.seek(0)
        import msvcrt
        try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True
        except OSError:raise BrowserUnavailable('Dedicated search browser is already owned.') from None
        own_descendants()
        owned=True
        if _query_job()!=1:raise BrowserUnavailable('Metadata descendants are not at a browser-safe boundary.')
        from playwright.sync_api import sync_playwright
        import pause_control
        if pause_control.requested():raise pause_control.PauseRequested()
        runtime=sync_playwright().start()
        context=runtime.chromium.launch_persistent_context(str(profile),channel='msedge',headless=True,
            locale='en-US',accept_downloads=False,args=['--disk-cache-size=67108864','--media-cache-size=16777216'])
        # Search rendering must not become unbudgeted publisher navigation or a download.
        context.route('**/*',lambda route:route.continue_() if urllib.parse.urlparse(route.request.url).hostname in ENGINES[engine]['hosts'] else route.abort())
        page=context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(15_000)
        params={'q':query}
        if engine=='ddg':params['ia']='web'
        page.goto(ENGINES[engine]['base']+'?'+urllib.parse.urlencode(params),wait_until='domcontentloaded',timeout=45_000)
        if challenge(page.url,page.locator('body').inner_text(timeout=10_000),engine):
            raise BrowserUnavailable('Free search requested human verification; no bypass attempted.')
        if pause_control.requested():raise pause_control.PauseRequested()
        return rendered_results(page,query,engine)
    except BrowserUnavailable:raise
    except Exception as exc:
        import pause_control
        if isinstance(exc,pause_control.PauseRequested):raise
        raise BrowserUnavailable('Regular search browser unavailable; no bypass attempted.') from None
    finally:
        cleanup_error=None
        try:
            if context:context.close()
        except Exception as exc:cleanup_error=exc
        finally:
            try:
                if runtime:runtime.stop()
            except Exception as exc:cleanup_error=exc
            finally:
                if owned:
                    deadline=time.monotonic()+5
                    try:
                        while _query_job()!=1 and time.monotonic()<deadline:time.sleep(.05)
                        if _query_job()!=1:cleanup_error=BrowserUnavailable('Browser descendants did not close; profile remains held.')
                    except Exception as exc:cleanup_error=exc
                if cleanup_error:
                    _retained.append((lock,runtime,context))
                    raise BrowserUnavailable('Browser closure unverified; profile remains held until worker exits.') from None
                if lock:
                    try:
                        if locked:
                            lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
                        lock.close()
                    except Exception:
                        _retained.append((lock,runtime,context))
                        raise BrowserUnavailable('Browser profile release failed; ownership remains held.') from None
                _mutex.release()


def close():
    """A paused worker must have returned through search's owner-thread finally."""
    if _mutex.locked():raise BrowserUnavailable('Search browser has not reached its safe closure boundary.')
