"""Cached read-only metadata sources. Public text is evidence, never instructions."""
import base64
import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from html import unescape
from pathlib import Path
import app
import storage

LOCK=threading.Lock()
HOSTS={'gcd':'www.comics.org','google_books':'www.googleapis.com'}
BUDGETS={'gcd':1000,'google_books':500}

def setting(name):
    if os.environ.get(name):return os.environ[name].strip()
    config=json.loads((app.BASE/'config.json').read_text(encoding='utf-8'))
    for path in [app.BASE/'.env',app.BASE.parents[1]/'.env',Path(config.get('env_file',app.BASE/'.env'))]:
        if path.is_file():
            for line in path.read_text(encoding='utf-8-sig').splitlines():
                key,sep,value=line.strip().removeprefix('export ').partition('=')
                if sep and key.strip()==name:
                    value=value.strip()
                    return value[1:-1] if len(value)>1 and value[0]==value[-1] and value[0] in ('\"',"'") else value
    return ''

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError('Source redirect refused.')

def status_path(provider):return app.DATA/(provider+'-status.json')

def request(provider,path,params=None):
    """Never put keys in cache identifiers, errors, or persisted status."""
    if provider not in HOSTS or not path.startswith('/') or '?' in path:
        raise ValueError('Unsupported metadata source.')
    params=dict(params or {})
    headers={'Accept':'application/json','User-Agent':'ComicMetadata/0.5 (personal catalog)'}
    cache_key=provider+':'+path+':'+json.dumps(params,sort_keys=True)
    if provider=='gcd':
        email,password=setting('GCD_EMAIL'),setting('GCD_PASSWORD')
        if not email or not password:raise ValueError('GCD credentials not configured.')
        headers['Authorization']='Basic '+base64.b64encode((email+':'+password).encode()).decode()
    else:
        secret=setting('GOOGLE_BOOKS_API_KEY')
        if not secret:raise ValueError('Google Books key not configured.')
        params['key']=secret
    url='https://'+HOSTS[provider]+path+('?' + urllib.parse.urlencode(params) if params else '')
    with LOCK:
        with app.db() as con:
            con.execute('CREATE TABLE IF NOT EXISTS provider_requests (provider TEXT, timestamp REAL)')
            cached=con.execute('SELECT value FROM cache WHERE key=? AND fetched>?',(cache_key,time.time()-7*86400)).fetchone()
            used=con.execute('SELECT COUNT(*) FROM provider_requests WHERE provider=? AND timestamp>?',(provider,time.time()-86400)).fetchone()[0]
        if cached:return json.loads(cached['value'])
        target=status_path(provider)
        state=json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
        if state.get('retry_at',0)>time.time():raise ValueError(provider+' is waiting before retrying.')
        if used>=BUDGETS[provider]:
            state.update(status='daily_budget_wait',retry_at=time.time()+3600)
            storage.save(target,state)
            raise ValueError(provider+' daily application budget reached.')
        time.sleep(max(0,state.get('last_request',0)+3.2-time.time()))
        state.update(status='requesting',last_request=time.time(),requests_last_day=used+1)
        storage.save(target,state)
        with app.db() as con:con.execute('INSERT INTO provider_requests VALUES (?,?)',(provider,time.time()))
        try:
            with urllib.request.build_opener(NoRedirect()).open(urllib.request.Request(url,headers=headers),timeout=25) as response:
                raw=response.read(3_000_001)
            if len(raw)>3_000_000:raise ValueError('Response too large.')
            result=json.loads(raw)
            if not isinstance(result,dict):raise ValueError('Unsupported response schema.')
            with app.db() as con:con.execute('INSERT OR REPLACE INTO cache VALUES (?,?,?)',(cache_key,json.dumps(result),time.time()))
            state.update(status='available',retry_at=0,checked_at=time.time(),http_status=200)
            storage.save(target,state)
            return result
        except Exception as exc:
            code=exc.code if isinstance(exc,urllib.error.HTTPError) else None
            delay=3600
            if code==429:
                try:delay=max(1,int(exc.headers.get('Retry-After',3600)))
                except (TypeError,ValueError):pass
            state.update(status='access_rejected' if code in (401,403) else 'unavailable',http_status=code,retry_at=time.time()+delay,checked_at=time.time())
            storage.save(target,state)
            raise ValueError(provider+' unavailable; retry scheduled.') from None

def text(value):return unescape(re.sub('<[^>]+>',' ',str(value or ''))).strip()

def cover_matches(path,url):
    import automatic,reverse_image
    p=urllib.parse.urlparse(url)
    allowed={'covers.comics.org','files1.comics.org','files2.comics.org','www.comics.org','books.google.com','books.googleusercontent.com'}
    if p.scheme=='http' and p.hostname in allowed:url='https:'+url[5:];p=urllib.parse.urlparse(url)
    if p.scheme!='https' or p.hostname not in allowed or p.username or p.password or p.port not in (None,443):return False
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'ComicMetadata/0.5 (personal catalog)'})
        with urllib.request.build_opener(NoRedirect()).open(req,timeout=25) as response:remote=response.read(20*1024*1024+1)
    except Exception:
        raise ValueError('Source cover unavailable; identity not verified.') from None
    if len(remote)>20*1024*1024:return False
    local,_,_=reverse_image.cover(path,0)
    return automatic.covers_agree(local,remote)

def gcd_lookup(row,old):
    import research
    if not setting('GCD_EMAIL') or not setting('GCD_PASSWORD'):return None
    series,number=research.query_identity(row,old)
    year=str(old.get('Year') or row.get('year') or '')
    if not series or not number or not year:return None
    endpoint='/api/series/name/'+urllib.parse.quote(series,safe='')+'/issue/'+urllib.parse.quote(research.issue_number(number),safe='')+'/year/'+year+'/'
    payload=request('gcd',endpoint)
    if not payload.get('results'):
        # Missing GCD key dates must not hide a cover-confirmable issue.
        payload=request('gcd',endpoint.rsplit('/year/',1)[0]+'/')
    if payload.get('next'):return None
    verified=[]
    for candidate in payload.get('results',[])[:10]:
        api_url=urllib.parse.urlparse(candidate.get('api_url',''))
        if api_url.hostname!='www.comics.org' or not re.fullmatch(r'/api/issue/\d+/',api_url.path):continue
        detail=request('gcd',api_url.path)
        # The search's series_name is a display string including publisher/year.
        series_url=urllib.parse.urlparse(detail.get('series',''))
        if series_url.hostname!='www.comics.org' or not re.fullmatch(r'/api/series/\d+/',series_url.path):continue
        series_data=request('gcd',series_url.path)
        if research.series_key(series_data.get('name'))!=research.series_key(series):continue
        if research.issue_number(detail.get('number'))!=research.issue_number(number):continue
        if detail.get('key_date') and not str(detail['key_date']).startswith(year):continue
        try:
            if not cover_matches(row['path'],detail.get('cover') or ''):continue
        except ValueError:
            storage.save(status_path('gcd'),{'status':'cover_unavailable','checked_at':time.time()})
            continue
        fields={'Series':series_data['name'],'Number':str(detail['number'])}
        # Only issue-wide story credits; exclude cover, advertisements and editorial material.
        stories=[s for s in detail.get('story_set',[]) if s.get('type')=='comic story']
        for source,dest in [('script','Writer'),('pencils','Penciller'),('inks','Inker'),('colors','Colorist'),('letters','Letterer')]:
            values=sorted({text(s.get(source)) for s in stories if text(s.get(source)) not in ('','None','?')})
            if values:fields[dest]='; '.join(values)
        synopsis='\n'.join(text(s.get('synopsis')) for s in stories if s.get('synopsis'))
        issue_id=api_url.path.strip('/').split('/')[-1]
        verified.append({'provider':'GCD','fields':fields,'sources':[{'url':'https://www.comics.org/issue/'+issue_id+'/', 'title':series+' #'+number,'text':synopsis,'scope':'Exact series, issue number and cover verified; available key date checked','retrieved':time.time()}] if synopsis else [],'status':'issue_verified'})
    return verified[0] if len(verified)==1 else None

def is_book(row,old):
    # Single-issue series must not receive a collected edition's description.
    return bool(old.get('ISBN') or re.search(r'\b(TPB|HC|omnibus|graphic novel|collected edition)\b',row['path'],re.I) or old.get('Format') in ('Trade Paperback','Hardcover','Graphic Novel','Omnibus'))

def google_lookup(row,old):
    import research
    if not setting('GOOGLE_BOOKS_API_KEY') or not is_book(row,old):return None
    title=old.get('Title') or old.get('Series') or row.get('series') or ''
    isbn=re.sub('[^0-9X]','',old.get('ISBN','').upper())
    if not title and not isbn:return None
    payload=request('google_books','/books/v1/volumes',{'q':'isbn:'+isbn if isbn else 'intitle:"'+title+'"','maxResults':10,'langRestrict':'en'})
    matches=[]
    for item in payload.get('items',[]):
        info=item.get('volumeInfo',{})
        if info.get('language')!='en':continue
        ids={re.sub('[^0-9X]','',i.get('identifier','').upper()) for i in info.get('industryIdentifiers',[]) if i.get('type') in ('ISBN_10','ISBN_13')}
        if isbn:
            if isbn not in ids:continue
        elif research.normalize(info.get('title'))!=research.normalize(title) or not cover_matches(row['path'],info.get('imageLinks',{}).get('thumbnail','')):continue
        fields={'Title':info['title']}
        if info.get('authors'):fields['Writer']=', '.join(info['authors'])
        if info.get('publisher'):fields['Publisher']=info['publisher']
        if not isbn and ids:fields['ISBN']=sorted(ids)[0]
        description=text(info.get('description'))
        volume_id=str(item.get('id',''))
        if not re.fullmatch(r'[A-Za-z0-9_-]+',volume_id):continue
        matches.append({'provider':'Google Books','fields':fields,'sources':[{'url':'https://books.google.com/books?id='+volume_id,'title':info['title'],'text':description,'scope':'ISBN or exact title and cover verified','retrieved':time.time()}] if description else [],'status':'edition_verified'})
    return matches[0] if len(matches)==1 else None

def statuses():
    result={'comicvine':comicvine_status()}
    for provider in ('metron','gcd','google_books'):
        target=status_path(provider)
        result[provider]=json.loads(target.read_text(encoding='utf-8')) if target.exists() else {'status':'not_used_yet'}
    result['open_library']={'status':'offline_index_ready' if (app.DATA/'open-library.sqlite').exists() else 'awaiting_bulk_data'}
    import getcomics
    result['getcomics']=getcomics.status()
    return result

def comicvine_status():
    now=time.time()
    with app.db() as con:
        budget=con.execute('SELECT COUNT(*) AS used,MIN(timestamp) AS first FROM api_requests WHERE timestamp>?',(now-3600,)).fetchone()
        api_state=con.execute('SELECT * FROM api_state WHERE id=1').fetchone()
    target=status_path('comicvine')
    result=json.loads(target.read_text(encoding='utf-8')) if target.exists() else {'status':'configured'}
    result.update(requests_last_hour=budget['used'],hourly_application_budget=180)
    if not app.api_key():result.update(status='not_configured',retry_at=0)
    elif api_state['blocked_until']>now:result.update(status='rate_limit_wait',retry_at=api_state['blocked_until'])
    elif budget['used']>=180:result.update(status='hourly_budget_wait',retry_at=budget['first']+3600)
    elif result['status'] in ('rate_limit_wait','hourly_budget_wait') or (result['status']=='requesting' and now-result.get('checked_at',0)>60):
        result.update(status='configured',retry_at=0)
    return result
