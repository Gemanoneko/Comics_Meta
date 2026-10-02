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

class SearchBlocked(ValueError):
    pass

def config():
    return json.loads((app.BASE/'config.json').read_text(encoding='utf-8')).get('web_search',{})

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
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def read(url,headers=None,binary=False):
    validate_url(url)
    opener=urllib.request.build_opener(SafeRedirect())
    request=urllib.request.Request(url,headers=dict({'User-Agent':'ComicMetadataResearch/0.3'},**(headers or {})))
    try:
        with opener.open(request,timeout=25) as response:
            raw=response.read(2_000_001)
            if len(raw)>2_000_000:raise ValueError('Source response too large.')
            return raw if binary else raw.decode('utf-8',errors='replace')
    except Exception as exc:
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

def cached(query):
    cache_key='web-search:'+config().get('provider','free')+':'+query
    with app.db() as con:
        row=con.execute('SELECT value FROM cache WHERE key=? AND fetched>?',(cache_key,time.time()-7*86400)).fetchone()
    return cache_key,json.loads(row['value']) if row else None

def search(query):
    query=re.sub(r'\s+',' ',query).strip()[:500]
    if not query:return []
    cache_key,result=cached(query)
    if result is not None:return result
    now=time.time()
    with app.db() as con:
        con.execute('CREATE TABLE IF NOT EXISTS web_requests(timestamp REAL)')
        con.execute('CREATE TABLE IF NOT EXISTS web_state(id INTEGER PRIMARY KEY,blocked_until REAL)')
        con.execute('INSERT OR IGNORE INTO web_state VALUES(1,0)')
        con.execute('BEGIN IMMEDIATE') if not con.in_transaction else None
        if con.execute('SELECT blocked_until FROM web_state WHERE id=1').fetchone()[0]>now:
            raise SearchBlocked('General web search is cooling down; cached sources remain available.')
        count=con.execute('SELECT COUNT(*) FROM web_requests WHERE timestamp>?',(now-86400,)).fetchone()[0]
        if count>=int(config().get('daily_request_limit',100)):
            raise SearchBlocked('Daily web-search request cap reached.')
        previous=con.execute('SELECT MAX(timestamp) FROM web_requests').fetchone()[0] or 0
        con.execute('INSERT INTO web_requests VALUES(?)',(now,))
    delay=max(0,3-(now-previous))
    if delay:time.sleep(delay)
    try:
        if config().get('provider','free')=='brave':
            token=key()
            if not token:raise SearchBlocked('BRAVE_SEARCH_API_KEY is not configured.')
            url='https://api.search.brave.com/res/v1/web/search?'+urllib.parse.urlencode({'q':query,'count':5,'safesearch':'off'})
            payload=json.loads(read(url,{'X-Subscription-Token':token}))
            result=[{'url':r['url'],'title':r.get('title','')} for r in payload.get('web',{}).get('results',[])][:5]
        else:
            raw=read('https://html.duckduckgo.com/html/?'+urllib.parse.urlencode({'q':query,'kp':'-2'}))
            if any(marker in raw.lower() for marker in ('anomaly.js','bots use duckduckgo','verify you are human')):
                raise SearchBlocked('Free search requested human verification; no bypass attempted.')
            page=Page();page.feed(raw);result=[]
            for item in page.links[:5]:
                url=urllib.parse.urljoin('https://duckduckgo.com',item['url'])
                redirect=urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get('uddg')
                if redirect:url=redirect[0]
                if urllib.parse.urlparse(url).scheme=='https':result.append(dict(item,url=url))
            if not result and 'no results' not in raw.lower():
                raise SearchBlocked('Free search did not return a usable result page.')
        with app.db() as con:con.execute('INSERT OR REPLACE INTO cache VALUES(?,?,?)',(cache_key,json.dumps(result),time.time()))
        return result
    except SearchBlocked:
        with app.db() as con:con.execute('UPDATE web_state SET blocked_until=? WHERE id=1',(time.time()+3600,))
        raise

def source(url):
    cache_key='web-source:'+url
    with app.db() as con:
        cached=con.execute('SELECT value FROM cache WHERE key=? AND fetched>?',(cache_key,time.time()-7*86400)).fetchone()
    if cached:return json.loads(cached['value'])
    page=Page();page.feed(read(url))
    result={'url':url,'title':' '.join(page.title),'headings':page.headings,'text':re.sub(r'\s+',' ',page.description or ' '.join(page.text))[:12000],
            'identity_text':re.sub(r'\s+',' ',' '.join(page.text))[:24000],
            'image':page.image,'retrieved':time.time(),'scope':'Web candidate; identity must be verified'}
    with app.db() as con:con.execute('INSERT OR REPLACE INTO cache VALUES(?,?,?)',(cache_key,json.dumps(result),time.time()))
    return result
