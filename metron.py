"""Read-only Metron lookup with persistent pacing and secret-safe failures."""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from html import unescape
import app
from provider_wait import ProviderDeferred
import storage

STATE = app.DATA / 'metron-status.json'
LOCK = threading.Lock()

def token():
    if os.environ.get('METRON_API_TOKEN'):
        return os.environ['METRON_API_TOKEN'].strip()
    for path in app.env_files():
        if path.is_file():
            for line in path.read_text(encoding='utf-8-sig').splitlines():
                name, separator, value = line.strip().removeprefix('export ').partition('=')
                if separator and name.strip() == 'METRON_API_TOKEN':
                    return value.strip().strip('\"\'')
    return ''

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('Metron API redirect refused.')

def request(endpoint, **params):
    if not re.fullmatch(r'(issue|series)(/\d+)?/', endpoint):
        raise ValueError('Unsupported Metron endpoint.')
    secret = token()
    if not secret:
        raise ValueError('Metron token is not configured.')
    url = 'https://metron.cloud/api/' + endpoint + '?' + urllib.parse.urlencode(params)
    cache_key = 'metron:' + url
    with LOCK:
        import pause_control
        if pause_control.requested():raise pause_control.PauseRequested()
        with app.db() as con:
            row = con.execute('SELECT value FROM cache WHERE key=? AND fetched>?', (cache_key, time.time()-7*86400)).fetchone()
        if row:
            return json.loads(row['value'])
        state = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {}
        if state.get('retry_at', 0) > time.time():
            raise ProviderDeferred('Metron is waiting before retrying; other sources remain available.','metron',state['retry_at'])
        pause_control.sleep(max(0, state.get('last_request', 0)+3.2-time.time()))
        state.update(last_request=time.time(), status='requesting')
        storage.save(STATE, state)
        req = urllib.request.Request(url, headers={'Authorization':'Bearer '+secret, 'Accept':'application/json', 'User-Agent':'ComicMetadata/0.4 (personal catalog)'})
        try:
            with urllib.request.build_opener(NoRedirect()).open(req, timeout=25) as response:
                headers = response.headers
                raw = response.read(3_000_001)
            if len(raw)>3_000_000:
                raise ValueError('Response too large.')
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError('Unexpected response.')
            state.update(status='available', retry_at=0, checked_at=time.time())
            for scope in ('Burst', 'Sustained'):
                remaining = headers.get('X-RateLimit-'+scope+'-Remaining')
                reset = headers.get('X-RateLimit-'+scope+'-Reset')
                if remaining is not None and reset is not None:
                    state[scope.lower()] = {'remaining':int(remaining), 'reset':int(reset)}
                    if int(remaining)<=0:
                        state['retry_at']=max(state['retry_at'],int(reset))
            storage.save(STATE, state)
            with app.db() as con:
                con.execute('INSERT OR REPLACE INTO cache(key,value,fetched) VALUES(?,?,?)', (cache_key,json.dumps(payload),time.time()))
            return payload
        except Exception as exc:
            code = exc.code if isinstance(exc, urllib.error.HTTPError) else None
            delay = 3600
            if code == 429:
                try: delay = max(1, int(exc.headers.get('Retry-After',3600)))
                except (ValueError, TypeError): pass
            status = 'authentication_failed' if code in (401,403) else 'unavailable'
            state.update(status=status, retry_at=time.time()+delay, checked_at=time.time(), http_status=code)
            storage.save(STATE, state)
            raise ProviderDeferred('Metron '+status.replace('_',' ')+'; retry scheduled, other sources remain available.','metron',state['retry_at']) from None

def candidates(series,number,year):
    """Share a complete year list; a partial list falls back to exact issue search."""
    import research_runtime
    with research_runtime.stage('Metron candidate search'):
        payload=request('issue/',series_name=series,cover_year=year)
        results=payload.get('results',[])
        if payload.get('next') or payload.get('count',len(results))!=len(results):
            payload=request('issue/',series_name=series,number=number,cover_year=year)
        return payload


def verified_cover(path,url):
    import automatic,reverse_image,research_runtime
    parsed=urllib.parse.urlparse(url)
    if parsed.scheme!='https' or parsed.hostname!='static.metron.cloud' or parsed.username or parsed.password or parsed.port not in (None,443):return False
    with research_runtime.stage('Metron cover verification'):
        with urllib.request.build_opener(NoRedirect()).open(url,timeout=25) as response:
            remote=response.read(20*1024*1024+1)
        if len(remote)>20*1024*1024:return False
        local,_,_=reverse_image.cover(path,0)
        return automatic.covers_agree(local,remote)


def metadata_fields(detail):
    """Issue-wide facts only; primary issue credits cannot establish variant covers."""
    series=detail.get('series') or {}
    fields={'Series':series.get('name'),'Number':detail.get('number'),'Title':detail.get('title'),
            'Publisher':(detail.get('publisher') or {}).get('name'),'Imprint':(detail.get('imprint') or {}).get('name'),
            'Volume':series.get('volume'),'LanguageISO':series.get('language'),
            'AgeRating':(detail.get('rating') or {}).get('name'),
            'Web':'https://metron.cloud/issue/'+str(detail['id'])+'/'}
    date=detail.get('cover_date') or ''
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}',date):fields.update(zip(('Year','Month','Day'),date.split('-')))
    roles={'writer':'Writer','artist':'Penciller','penciller':'Penciller','penciler':'Penciller','inker':'Inker',
           'colorist':'Colorist','letterer':'Letterer','editor':'Editor','translator':'Translator'}
    credits={}
    for credit in detail.get('credits',[]):
        name=credit.get('creator')
        if not isinstance(name,str) or not name.strip():continue
        for role in credit.get('role',[]):
            field=roles.get(str(role.get('name','')).lower())
            if field:credits.setdefault(field,[]).append(name.strip())
    fields.update({field:', '.join(dict.fromkeys(names)) for field,names in credits.items()})
    for source,target in [('characters','Characters'),('teams','Teams'),('arcs','StoryArc')]:
        names=[item.get('name') for item in detail.get(source,[]) if isinstance(item,dict) and item.get('name')]
        if names:fields[target]=', '.join(dict.fromkeys(names))
    genres=[g.get('name') for g in series.get('genres',[]) if g.get('name')]
    if genres:fields['Genre']=', '.join(dict.fromkeys(genres))
    kind=(series.get('series_type') or {}).get('name','')
    formats={'Single Issue':'Single Issue','Limited Series':'Single Issue','One-Shot':'One-Shot',
             'Trade Paperback':'Trade Paperback','Hardcover':'Hardcover','Graphic Novel':'Graphic Novel','Omnibus':'Omnibus'}
    if kind in formats:fields['Format']=formats[kind]
    isbn=re.sub(r'[^0-9X]','',str(detail.get('isbn') or '').upper())
    if re.fullmatch(r'\d{9}[\dX]|\d{13}',isbn):fields['ISBN']=isbn
    barcode=str(detail.get('upc') or '')
    if re.fullmatch(r'\d{8}|\d{12,14}',barcode):fields['GTIN']=barcode
    return {key:str(value) for key,value in fields.items() if isinstance(value,(str,int)) and str(value).strip()}


VOLUME_TAIL = re.compile(r'[\s,(-]+(?:vol(?:ume)?\.?\s*|v)(\d+)\)?\s*$', re.I)
MAX_VARIANT_COVERS = 8


def name_variants(series):
    """(search name, expected series key, required series volume) in search order.

    The name as filed, then " - " and ": " swapped (Metron's name search is
    literal; the identity key ignores punctuation), then without a trailing
    "Vol. N" / "vN", which must then match Metron's series volume when it has one."""
    import research
    key = research.series_key(series)
    names = [(series, key, None)]
    if ' - ' in series:
        names.append((series.replace(' - ', ': '), key, None))
    elif ': ' in series:
        names.append((series.replace(': ', ' - '), key, None))
    tail = VOLUME_TAIL.search(series)
    base = series[:tail.start()].strip(' -:,') if tail else ''
    if base:
        names.append((base, research.series_key(base), int(tail[1])))
    return names


def same_series(item, key, volume):
    import research
    series = item.get('series') or {}
    if research.series_key(series.get('name')) != key:
        return False
    found = series.get('volume')
    return volume is None or found in (None, '') or str(found).strip() == str(volume)


def lookup(row, old):
    """Accept a unique exact series/number/year candidate only after cover agreement.

    The series name is also searched in its punctuation and volume variants, and
    a candidate whose primary cover differs is checked against its variant covers
    before it is rejected; a variant match drops the primary cover's barcode."""
    import research
    import automatic
    import reverse_image
    series, number = research.query_identity(row, old)
    year = old.get('Year') or row.get('year')
    if not token() or not series or not number or not year:
        return None
    for name, key, volume in name_variants(series):
        payload = candidates(name,research.issue_number(number),year)
        # A truncated candidate list cannot establish uniqueness.
        if payload.get('next'):
            return None
        named = [i for i in payload.get('results', []) if same_series(i, key, volume)]
        if named:
            break  # This name is the series; other spellings are not tried.
    else:
        return None
    matches = [i for i in named if research.issue_number(i.get('number'))==research.issue_number(number)
               and str(i.get('cover_date') or '').startswith(str(year)+'-')]
    if len(matches)!=1:
        return None
    candidate=matches[0]
    preview=candidate.get('image') or ''
    primary=not preview or verified_cover(row['path'],preview)
    import research_runtime
    with research_runtime.stage('Metron issue details'):
        detail = request('issue/'+str(int(candidate['id']))+'/')
    if (detail.get('id')!=candidate['id'] or not same_series(detail, key, volume)
        or research.issue_number(detail.get('number')) != research.issue_number(number)
        or not str(detail.get('cover_date') or '').startswith(str(year)+'-')):
        return None
    url = detail.get('image') or ''
    if primary and (not preview or url!=preview):primary=verified_cover(row['path'],url)
    variant=None
    if not primary:
        # The comic may carry a variant cover of this exact issue.
        for item in [v for v in detail.get('variants') or [] if isinstance(v,dict) and v.get('image')][:MAX_VARIANT_COVERS]:
            if verified_cover(row['path'],item['image']):
                variant=item;break
        if not variant:return None
    language=(detail.get('series') or {}).get('language')
    if language and str(language).lower() not in ('en','eng','english'):return None
    fields=metadata_fields(detail)
    if variant:fields.pop('GTIN',None)  # The detail's barcode belongs to the primary cover.
    text=unescape(re.sub('<[^>]+>',' ',detail.get('desc') or '')).strip()
    scope='Exact issue identity and '+('variant cover ('+str(variant.get('name') or 'unnamed')+')' if variant else 'cover')+' verified'
    return {'provider':'Metron','metadata_version':2,'fields':fields,'sources':[{'url':'https://metron.cloud/issue/'+str(detail['id'])+'/', 'title':detail.get('issue') or series+' #'+number, 'text':text,'scope':scope,'retrieved':time.time()}] if text else [],'status':'issue_verified'}
