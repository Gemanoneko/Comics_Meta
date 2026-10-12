"""Bounded public-web research; blocked searches are retried, never bypassed."""
import hashlib
import ipaddress
import json
import os
import re
import socket
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
import app
from provider_wait import ProviderDeferred

class SearchBlocked(ProviderDeferred):
    def __init__(self,message,provider='',retry_at=0,engine=None):
        super().__init__(message,provider,retry_at)
        self.engine=engine


def free_browser_search(query,engine='ddg'):
    import free_search_browser
    try:return free_search_browser.search(query,engine)
    except free_search_browser.BrowserUnavailable as exc:raise SearchBlocked(str(exc)) from None

def config():
    path=app.BASE/'config.json'
    return json.loads(path.read_text(encoding='utf-8')).get('web_search',{}) if path.exists() else {}

def key():
    value=os.environ.get('BRAVE_SEARCH_API_KEY','')
    if value:return value.strip()
    settings=json.loads((app.BASE/'config.json').read_text(encoding='utf-8'))
    for path in [app.BASE/'.env',Path(settings.get('env_file',app.BASE/'.env'))]:
        if path.exists():
            for line in path.read_text(encoding='utf-8-sig').splitlines():
                if line.strip().startswith('BRAVE_SEARCH_API_KEY='):
                    return line.strip().split('=',1)[1].strip().strip('\"\'')
    return ''

def validate_url(url):
    parsed=urllib.parse.urlparse(url)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None,443):
        raise ValueError('Only public HTTPS source URLs are supported.')
    for info in socket.getaddrinfo(parsed.hostname,443,type=socket.SOCK_STREAM):
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise ValueError('Non-public source address rejected.')

class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        validate_url(newurl)
        import getcomics
        if getcomics.is_host(newurl):getcomics.reserve()
        import publisher_catalogs
        name=publisher_catalogs.provider(newurl)
        if name:publisher_catalogs.reserve(name)
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def read(url,headers=None,binary=False):
    validate_url(url)
    import getcomics
    limited=getcomics.is_host(url)
    if limited:getcomics.reserve()
    import publisher_catalogs
    catalog=publisher_catalogs.provider(url)
    if catalog:publisher_catalogs.reserve(catalog)
    opener=urllib.request.build_opener(SafeRedirect())
    request=urllib.request.Request(url,headers=dict({'User-Agent':'ComicMetadataResearch/0.3'},**(headers or {})))
    try:
        with opener.open(request,timeout=25) as response:
            raw=response.read(2_000_001)
            if len(raw)>2_000_000:raise ValueError('Source response too large.')
            text=raw.decode('utf-8',errors='replace') if not binary else ''
            if limited:
                if any(marker in text.lower() for marker in ('verify you are human','prove you are human','just a moment','cf-chl-','challenge-platform','checking your browser')):
                    getcomics.mark('human_verification',True)
                    raise SearchBlocked('GetComics needs human verification; automatic requests stopped.')
                getcomics.mark('available')
            if catalog:
                if any(marker in text.lower() for marker in ('verify you are human','just a moment','cf-chl-','challenge-platform','prove you are human')):
                    publisher_catalogs.mark(catalog,'human_verification')
                    raise ProviderDeferred('Catalog needs human verification; requests stopped.',catalog)
                publisher_catalogs.mark(catalog,'available')
            return raw if binary else text
    except ProviderDeferred:
        raise
    except Exception as exc:
        if limited:getcomics.mark('access_blocked',True)
        if catalog:
            publisher_catalogs.mark(catalog,'unavailable')
            raise ProviderDeferred('Catalog unavailable; retry scheduled.',catalog,time.time()+3600) from None
        # URLs or headers must never leak a credential in a dashboard error.
        raise SearchBlocked('Web source unavailable or blocked; no bypass attempted.') from None

class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.text=[];self.title=[];self.in_title=False;self.hidden=0;self.links=[];self.link=None;self.image=None;self.description=None;self.headings=[];self.heading=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag in ('script','style','noscript'):self.hidden+=1
        if tag=='title':self.in_title=True
        if tag=='h1':self.heading=''
        if tag=='meta' and a.get('property')=='og:image':self.image=a.get('content')
        if tag=='meta' and (a.get('name')=='description' or a.get('property')=='og:description'):
            self.description=a.get('content')
        if tag=='a' and 'result__a' in a.get('class',''):
            self.link={'url':a.get('href',''),'title':''}
    def handle_endtag(self,tag):
        if tag in ('script','style','noscript'):self.hidden=max(0,self.hidden-1)
        if tag=='title':self.in_title=False
        if tag=='h1' and self.heading is not None:self.headings.append(self.heading);self.heading=None
        if tag=='a' and self.link:self.links.append(self.link);self.link=None
    def handle_data(self,data):
        if self.hidden:return
        self.text.append(data)
        if self.in_title:self.title.append(data)
        if self.heading is not None:self.heading+=data
        if self.link:self.link['title']+=data

def cached(query,free_only=False,engine=None):
    cache_key='web-search:'+('bing' if engine=='bing' else 'free' if free_only or engine=='ddg' else config().get('provider','free'))+':'+query
    with app.db() as con:
        row=con.execute('SELECT value FROM cache WHERE key=? AND fetched>?',(cache_key,time.time()-7*86400)).fetchone()
    result=json.loads(row['value']) if row else None
    # Old Bing captures included attached hidden cards with blank titles. Leave
    # those records intact; any replacement must pass ordinary holds/budgets.
    if engine=='bing' and result is not None and not usable_bing_results(result):result=None
    return cache_key,result


def usable_bing_results(result):
    return isinstance(result,list) and all(isinstance(item,dict) and isinstance(item.get('title'),str)
        and item['title'].strip() and isinstance(item.get('url'),str) and item['url'].startswith('https://') for item in result)

FREE_ENGINES=('ddg','bing')


def free_state_id(engine='ddg'):
    if engine=='bing':return 3
    # Keep the installed free route's saved hold. A configured paid vendor's
    # legacy hold remains separate from the explicitly requested free route.
    return 1 if config().get('provider','free')!='brave' else 2


def free_policy():
    options=config()
    # Application trial bounds, not a published allowance from the search provider.
    return min(300,max(1,int(options.get('free_daily_request_limit',300)))),max(120,int(options.get('free_min_interval_seconds',120)))


def free_engine_status(engine,now=None):
    if engine not in FREE_ENGINES:raise ValueError('Unsupported free search engine.')
    now=time.time() if now is None else now
    limit,interval=free_policy()
    with app.db() as con:
        exists={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        hold=con.execute('SELECT blocked_until FROM web_state WHERE id=?',(free_state_id(engine),)).fetchone() if 'web_state' in exists else None
        used=con.execute('SELECT COUNT(*),MIN(timestamp) FROM web_requests WHERE timestamp>?',(now-86400,)).fetchone() if 'web_requests' in exists else (0,None)
        previous=con.execute('SELECT MAX(timestamp) FROM web_requests').fetchone()[0] if 'web_requests' in exists else None
    retry=hold[0] if hold else 0
    status='cooldown_wait' if retry>now else 'available'
    if previous is not None and previous+interval>max(now,retry):
        status='pacing_wait';retry=previous+interval
    if used[0]>=limit:
        status='daily_budget_wait';retry=max(retry,used[1]+86400)
    return {'status':status,'retry_at':retry if retry>now else 0}


def free_status(now=None):
    now=time.time() if now is None else now
    engines={engine:free_engine_status(engine,now) for engine in FREE_ENGINES}
    result=dict(min(engines.values(),key=lambda state:state['retry_at']))
    result['engines']=engines
    return result


def search(query,free_only=False,engine=None):
    query=re.sub(r'\s+',' ',query).strip()[:500]
    if not query:return []
    if engine is not None and engine not in FREE_ENGINES:raise ValueError('Unsupported free search engine.')
    options=config()
    is_free=free_only or engine is not None or options.get('provider','free')!='brave'
    choices=(engine,) if engine else FREE_ENGINES
    empty=set()
    if is_free:
        for choice in choices:
            cache_key,result=cached(query,True,choice)
            if result is not None:
                if result or engine:return result
                empty.add(choice)
        if len(empty)==len(choices):return []
    else:
        cache_key,result=cached(query,free_only)
        if result is not None:return result
    limit,interval=free_policy() if is_free else (int(options.get('daily_request_limit',100)),3)
    with app.db() as con:
        con.execute('CREATE TABLE IF NOT EXISTS web_requests(timestamp REAL)')
        con.execute('CREATE TABLE IF NOT EXISTS web_state(id INTEGER PRIMARY KEY,blocked_until REAL)')
        con.execute('BEGIN IMMEDIATE') if not con.in_transaction else None
        if is_free:
            eligible=[choice for choice in choices if choice not in empty]
            for choice in eligible:con.execute('INSERT OR IGNORE INTO web_state VALUES(?,0)',(free_state_id(choice),))
            now=time.time()
            waits={choice:con.execute('SELECT blocked_until FROM web_state WHERE id=?',(free_state_id(choice),)).fetchone()[0] for choice in eligible}
            selected=next((choice for choice in eligible if waits[choice]<=now),None)
            if selected is None:
                selected=min(eligible,key=waits.get)
                raise SearchBlocked('Free search engines are cooling down; cached sources remain available.','free_web',waits[selected],selected)
            engine=selected;state_id=free_state_id(engine);cache_key='web-search:'+('bing' if engine=='bing' else 'free')+':'+query
        else:
            state_id=1;con.execute('INSERT OR IGNORE INTO web_state VALUES(?,0)',(state_id,))
        now=time.time()  # Recheck after acquiring the shared reservation lock.
        until=con.execute('SELECT blocked_until FROM web_state WHERE id=?',(state_id,)).fetchone()[0]
        if until>now:
            raise SearchBlocked('General web search is cooling down; cached sources remain available.','free_web' if is_free else 'web',until,engine)
        count,first=con.execute('SELECT COUNT(*),MIN(timestamp) FROM web_requests WHERE timestamp>?',(now-86400,)).fetchone()
        if count>=limit:
            raise SearchBlocked('Daily web-search request cap reached.','free_web' if is_free else 'web',first+86400,engine)
        previous=con.execute('SELECT MAX(timestamp) FROM web_requests').fetchone()[0]
        if is_free and previous is not None and previous+interval>now:
            raise SearchBlocked('Free searches are paced; cached sources remain available.','free_web',previous+interval,engine)
        con.execute('INSERT INTO web_requests VALUES(?)',(now,))
    delay=0 if is_free else max(0,3-(now-(previous or 0)))
    if delay:time.sleep(delay)
    try:
        if not is_free:
            token=key()
            if not token:raise SearchBlocked('BRAVE_SEARCH_API_KEY is not configured.')
            url='https://api.search.brave.com/res/v1/web/search?'+urllib.parse.urlencode({'q':query,'count':5,'safesearch':'off'})
            payload=json.loads(read(url,{'X-Subscription-Token':token}))
            result=[{'url':r['url'],'title':r.get('title','')} for r in payload.get('web',{}).get('results',[])][:5]
        else:
            result=free_browser_search(query,engine)
            if engine=='bing' and not usable_bing_results(result):
                raise SearchBlocked('Regular Bing search returned unusable result titles; no results cached.')
            result=[dict(item,engine=engine) for item in result]
        with app.db() as con:con.execute('INSERT OR REPLACE INTO cache VALUES(?,?,?)',(cache_key,json.dumps(result),time.time()))
        return result
    except SearchBlocked as exc:
        until=time.time()+3600
        with app.db() as con:
            con.execute('UPDATE web_state SET blocked_until=MAX(blocked_until,?) WHERE id=?',(until,state_id))
            until=con.execute('SELECT blocked_until FROM web_state WHERE id=?',(state_id,)).fetchone()[0]
        raise SearchBlocked(str(exc),'free_web' if is_free else 'web',until,engine) from None

def source(url):
    cache_key='web-source:'+url
    import publisher_catalogs
    if publisher_catalogs.provider(url):cache_key='catalog-source:v1:'+url
    with app.db() as con:
        cached=con.execute('SELECT value FROM cache WHERE key=? AND fetched>?',(cache_key,time.time()-7*86400)).fetchone()
    if cached:return json.loads(cached['value'])
    raw=read(url)
    page=Page();page.feed(raw)
    result={'url':url,'title':' '.join(page.title),'headings':page.headings,'text':re.sub(r'\s+',' ',page.description or ' '.join(page.text))[:12000],
            'identity_text':re.sub(r'\s+',' ',' '.join(page.text))[:24000],
            'image':page.image,'retrieved':time.time(),'scope':'Web candidate; identity must be verified'}
    import publisher_catalogs
    if publisher_catalogs.provider(url):publisher_catalogs.enrich(raw,result)
    with app.db() as con:con.execute('INSERT OR REPLACE INTO cache VALUES(?,?,?)',(cache_key,json.dumps(result),time.time()))
    return result
