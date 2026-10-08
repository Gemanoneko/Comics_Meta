"""Metadata-only GetComics fallback with a durable shared five-minute budget."""
import json
import re
import time
import urllib.parse
from html.parser import HTMLParser
import app


def is_host(url):
    return urllib.parse.urlparse(url).hostname in ('getcomics.org', 'www.getcomics.org')


def reserve():
    import web_search
    with app.db() as con:
        con.execute('CREATE TABLE IF NOT EXISTS getcomics_state(id INTEGER PRIMARY KEY,last_request REAL,blocked INTEGER,status TEXT)')
        con.execute("INSERT OR IGNORE INTO getcomics_state VALUES(1,0,0,'ready')")
        con.execute('BEGIN IMMEDIATE') if not con.in_transaction else None
        state = con.execute('SELECT * FROM getcomics_state WHERE id=1').fetchone()
        if state['blocked']: raise web_search.SearchBlocked('GetComics needs human verification or rejected access; automatic requests stopped.')
        if time.time() < state['last_request'] + 300: raise web_search.SearchBlocked('GetComics five-minute request interval; retry later.')
        con.execute("UPDATE getcomics_state SET last_request=?,status='requesting' WHERE id=1", (time.time(),))


def mark(status, blocked=False):
    with app.db() as con:
        con.execute('UPDATE getcomics_state SET status=?,blocked=? WHERE id=1', (status,int(blocked)))


def status():
    with app.db() as con:
        exists=con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='getcomics_state'").fetchone()
        state=con.execute('SELECT * FROM getcomics_state WHERE id=1').fetchone() if exists else None
    if not state:return {'status':'ready'}
    return {'status':state['status'], 'retry_at':0 if state['blocked'] else state['last_request']+300}


class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self.current=None
    def handle_starttag(self,tag,attrs):
        if tag=='a':self.current={'url':dict(attrs).get('href',''),'title':''}
    def handle_data(self,data):
        if self.current:self.current['title']+=data
    def handle_endtag(self,tag):
        if tag=='a' and self.current:
            self.links.append(self.current);self.current=None


def lookup(row, old):
    import research, web_search, providers
    series, number=research.query_identity(row,old)
    if not series:return None
    query=(old.get('Title') or series) if providers.is_book(row,old) else series+(' #'+number if number else '')
    url='https://getcomics.org/?'+urllib.parse.urlencode({'s':query})
    cache_key='getcomics-search:'+query
    with app.db() as con:
        cached=con.execute('SELECT value FROM cache WHERE key=? AND fetched>?',(cache_key,time.time()-7*86400)).fetchone()
    if cached:links=json.loads(cached['value'])
    else:
        parser=Links();parser.feed(web_search.read(url));links=parser.links
        with app.db() as con:con.execute('INSERT OR REPLACE INTO cache VALUES(?,?,?)',(cache_key,json.dumps(links),time.time()))
    candidates=[]
    for link in links:
        target=urllib.parse.urljoin('https://getcomics.org/',link['url'])
        if not is_host(target) or not re.fullmatch(r'/(?:marvel-comics|dc|other-comics)/[a-z0-9-]+/?',urllib.parse.urlparse(target).path):continue
        title=link['title'].strip()
        book_title=re.sub(r'\s*\((?:19|20)\d{2}\)\s*$', '',title)
        book=providers.is_book(row,old)
        if research.product_matches(title,series,number) or (book and research.normalize(book_title)==research.normalize(old.get('Title') or series)):
            if target not in candidates:candidates.append(target)
    if len(candidates)!=1:return None
    source=web_search.source(candidates[0])
    verified=research.verify_web_source(row,old,source)
    if verified:return verified
    if not providers.is_book(row,old):return None
    # Book-only synopsis evidence: exact edition title, year and known publisher.
    publisher=old.get('Publisher','');year=str(old.get('Year') or row.get('year') or '')
    if not publisher or not year or not re.search(r'\b'+re.escape(year)+r'\b',source['identity_text']):return None
    if research.normalize(publisher) not in research.normalize(source['identity_text']):return None
    if not any(research.normalize(re.sub(r'\s*\((?:19|20)\d{2}\)\s*$', '',t))==research.normalize(old.get('Title') or series) for t in source['headings']):return None
    return {'provider':'GetComics','fields':{},'sources':[dict(source,scope='Exact book title, publication year and existing publisher agree; synopsis evidence only')],'status':'web_issue_found'}
