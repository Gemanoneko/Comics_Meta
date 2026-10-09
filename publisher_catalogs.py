"""Public publisher/distributor catalogs; cached evidence and conservative matching."""
import json
import re
import time
import urllib.parse
from html import unescape
from html.parser import HTMLParser
import app
from provider_wait import ProviderDeferred

HOSTS={'www.darkhorse.com':'darkhorse_catalog','darkhorse.com':'darkhorse_catalog','digital.darkhorse.com':'darkhorse_catalog',
       'imagecomics.com':'image_catalog','www.imagecomics.com':'image_catalog',
       'previewsworld.com':'previews_catalog','www.previewsworld.com':'previews_catalog'}
NAMES={'darkhorse_catalog':'Dark Horse','image_catalog':'Image Comics','previews_catalog':'PREVIEWSworld'}


def provider(url):return HOSTS.get(urllib.parse.urlparse(url).hostname)


def tables(con):
    con.execute('CREATE TABLE IF NOT EXISTS catalog_requests(provider TEXT,timestamp REAL)')
    con.execute('CREATE TABLE IF NOT EXISTS catalog_status(provider TEXT PRIMARY KEY,status TEXT,retry_at REAL,last_request REAL)')


def reserve(name):
    import pause_control
    while True:
        if pause_control.requested():raise pause_control.PauseRequested()
        with app.db() as con:
            tables(con)
            con.execute('BEGIN IMMEDIATE')
            state=con.execute('SELECT * FROM catalog_status WHERE provider=?',(name,)).fetchone()
            now=time.time()
            if state and (state['status']=='human_verification' or state['retry_at']>now):
                raise ProviderDeferred(NAMES[name]+' unavailable; cached evidence remains usable.',name,state['retry_at'])
            used=con.execute('SELECT COUNT(*),MIN(timestamp) FROM catalog_requests WHERE provider=? AND timestamp>?',(name,now-86400)).fetchone()
            if used[0]>=300:raise ProviderDeferred(NAMES[name]+' daily request budget reached.',name,used[1]+86400)
            delay=max(0,(state['last_request'] if state else 0)+5-now)
            if not delay:
                con.execute('INSERT INTO catalog_requests VALUES(?,?)',(name,now))
                con.execute("INSERT OR REPLACE INTO catalog_status VALUES(?,'requesting',0,?)",(name,now))
                return
        pause_control.sleep(delay)


def mark(name,status):
    with app.db() as con:
        tables(con)
        con.execute('UPDATE catalog_status SET status=?,retry_at=? WHERE provider=?',(status,time.time()+3600 if status=='unavailable' else 0,name))


def statuses():
    with app.db() as con:
        tables(con)
        rows={r['provider']:{'status':r['status'],'retry_at':r['retry_at']} for r in con.execute('SELECT * FROM catalog_status')}
    return {name:rows.get(name,{'status':'ready'}) for name in NAMES}


def title_key(title):
    import research
    title=re.sub(r'\s*\((?:19|20)\d{2}\)\s*$', '',title)
    title=re.sub(r'\b(?:volume|vol\.?|v)\s*0*(\d+)\b',r'volume\1',title,flags=re.I)
    title=re.sub(r'\b(?:TPB|TP|HC|hardcover|paperback)\b','',title,flags=re.I)
    return research.normalize(title)


class Description(HTMLParser):
    def __init__(self):super().__init__();self.depth=0;self.text=[]
    def handle_starttag(self,tag,attrs):
        if tag in ('br','img','input','meta','link','hr'):return
        if self.depth:self.depth+=1
        elif any(re.search(r'\b(?:book-description|product-description|issue-description|synopsis)\b',v or '') for k,v in attrs if k in ('class','id')):self.depth=1
    def handle_endtag(self,tag):
        if self.depth and tag not in ('br','img','input','meta','link','hr'):self.depth-=1
    def handle_data(self,text):
        if self.depth:self.text.append(text)


def enrich(raw,source):
    parser=Description();parser.feed(raw)
    if parser.text:source['text']=re.sub(r'\s+',' ',' '.join(parser.text)).strip()[:12000]
    return source


def product_url(url,name):
    p=urllib.parse.urlparse(url)
    if provider(url)!=name:return False
    if name=='darkhorse_catalog':return bool(re.fullmatch(r'/books/(?:\d+-\d+|[a-f0-9]{32})/[a-z0-9-]+/?',p.path,re.I))
    if name=='image_catalog':return bool(re.fullmatch(r'/comics/releases/[a-z0-9-]+/?',p.path))
    return bool(re.fullmatch(r'/Catalog/[A-Z0-9]+/?',p.path,re.I))


def verify(row,old,source,name):
    import research,providers,web_search,reverse_image,automatic
    if not product_url(source['url'],name):return None
    known=old.get('Publisher','')
    expected={'darkhorse_catalog':'Dark Horse Comics','image_catalog':'Image Comics'}.get(name,known)
    if not expected:return None
    if known and research.normalize(known)!=research.normalize(expected):return None
    identity=dict(old,Publisher=expected)
    if not providers.is_book(row,old):
        year=str(old.get('Year') or row.get('year') or '')
        date=re.search(r'(?:Release date|Publication Date|Originally Published|In Shops)\s*:?\s*([^|\n]{0,100}?\b(?:19|20)\d{2}\b)',source['identity_text'],re.I)
        if year and (not date or not re.search(r'\b'+re.escape(year)+r'\b',date[1])):return None
        return research.verify_web_source(row,identity,source,require_cover=True)
    title=old.get('Title') or old.get('Series') or row.get('series','')
    if not any(title_key(h)==title_key(title) for h in source['headings']):return None
    year=str(old.get('Year') or row.get('year') or '')
    body=source['identity_text']
    # An explicit product date is required; copyright/footer years cannot verify editions.
    date=re.search(r'(?:Release date|Publication Date|Originally Published|In Shops)\s*:?\s*([^|\n]{0,100}?\b(?:19|20)\d{2}\b)',body,re.I)
    if year and (not date or not re.search(r'\b'+re.escape(year)+r'\b',date[1])):return None
    isbn=re.sub(r'[^0-9X]','',old.get('ISBN','').upper())
    source_isbns={re.sub(r'[^0-9X]','',v.upper()) for v in re.findall(r'ISBN(?:-1[03])?\s*:?\s*([0-9X -]{10,25})',body,re.I)}
    if isbn:
        if isbn not in source_isbns:return None
    else:
        if not source.get('image'):return None
        remote=web_search.read(urllib.parse.urljoin(source['url'],source['image']),binary=True)
        local,_,_=reverse_image.cover(row['path'],0)
        if not automatic.covers_agree(local,remote):return None
    return {'provider':NAMES[name],'fields':{'Publisher':expected},'sources':[dict(source,scope='Exact collected-edition title, available release year and ISBN or cover verified')],'status':'web_issue_found'}


def lookup(row,old,name):
    import research,web_search,getcomics
    series,number=research.query_identity(row,old)
    expected={'darkhorse_catalog':'darkhorse','image_catalog':'image'}.get(name)
    hint=research.normalize(old.get('Publisher','')+' '+row.get('path',''))
    if expected and expected not in hint:return None
    query=old.get('Title') or series
    if not query:return None
    if number and not __import__('providers').is_book(row,old):query+=' #'+number
    if name=='previews_catalog':
        links=web_search.search('site:previewsworld.com/Catalog/ '+query)
    else:
        base='https://www.darkhorse.com/search/' if name=='darkhorse_catalog' else 'https://imagecomics.com/search/results'
        url=base+'?'+urllib.parse.urlencode({'s':query})
        key='catalog-search:'+url
        with app.db() as con:cached=con.execute('SELECT value FROM cache WHERE key=? AND fetched>?',(key,time.time()-7*86400)).fetchone()
        if cached:links=json.loads(cached['value'])
        else:
            parser=getcomics.Links();parser.feed(web_search.read(url))
            links=[dict(r,url=urllib.parse.urljoin(base,r['url'])) for r in parser.links]
            with app.db() as con:con.execute('INSERT OR REPLACE INTO cache VALUES(?,?,?)',(key,json.dumps(links),time.time()))
    book=__import__('providers').is_book(row,old)
    candidates=list(dict.fromkeys(r['url'] for r in links if product_url(r['url'],name) and
        (title_key(r['title'])==title_key(old.get('Title') or series) if book else research.product_matches(r['title'],series,number))))
    if len(candidates)!=1:return None
    return verify(row,old,web_search.source(candidates[0]),name)
