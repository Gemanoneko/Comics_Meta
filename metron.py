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
    import credential_store
    return credential_store.setting('METRON_API_TOKEN')

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
        import pause_control, research_runtime
        research_runtime.research_checkpoint()
        with app.db() as con:
            row = con.execute('SELECT value FROM cache WHERE key=? AND fetched>?', (cache_key, time.time()-7*86400)).fetchone()
        if row:
            return json.loads(row['value'])
        state = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {}
        if state.get('retry_at', 0) > time.time():
            raise ProviderDeferred('Metron is waiting before retrying; other sources remain available.','metron',state['retry_at'])
        pause_control.sleep(max(0, state.get('last_request', 0)+3.2-time.time()))
        research_runtime.research_checkpoint()
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


COVER_IMAGES = 3  # Enrichment D: archive images compared with each Metron cover.


def verified_cover(path,url):
    """False, or what accepted the cover (v0.5.0 review F4): {'comparison': 'today'|'aligned'|'wraparound',
    'page': archive image 1-3}. 'today' is the comparison 0.4.1 used; the others are Enrichment D's."""
    import automatic,reverse_image,research_runtime
    research_runtime.research_checkpoint()
    parsed=urllib.parse.urlparse(url)
    if parsed.scheme!='https' or parsed.hostname!='static.metron.cloud' or parsed.username or parsed.password or parsed.port not in (None,443):return False
    with research_runtime.stage('Metron cover verification'):
        with urllib.request.build_opener(NoRedirect()).open(url,timeout=25) as response:
            remote=response.read(20*1024*1024+1)
        if len(remote)>20*1024*1024:return False
        import pipeline_config
        if not pipeline_config.matching('cover_rule_v2'):
            local,_,_=reverse_image.cover(path,0)
            return {'comparison':'today','page':1} if automatic.covers_agree(local,remote) else False
        # Enrichment D: the revised comparison, on the first archive image and then the next two
        # (scanners often put a credits page first). The first image behaves as before: an unreadable one fails
        # the lookup. Pages 2 and 3 are only extra chances (v0.5.0 review F3): one that will not read or decode
        # (truncated, not an image, a bad CRC, too large) is no match for that page, so the variant covers are
        # still tried and the miss is an ordinary miss, not an error retried every few hours.
        import cover_match,pause_control
        for index in range(COVER_IMAGES):
            try:
                local,_,_=reverse_image.cover(path,index)
                comparison=cover_match.compare(local,remote)
            except pause_control.PauseRequested:
                raise
            except Exception:
                if index==0:raise
                continue
            if comparison:return {'comparison':comparison,'page':index+1}
        return False


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


# Enrichment C: Metron series types whose issue 1 an unnumbered book can be.
ONE_ISSUE_TYPES = {'One-Shot', 'Graphic Novel', 'Trade Paperback', 'Hardcover', 'Omnibus'}
# A number, volume, book, part or chapter anywhere in the name: the book is not plainly unnumbered. An underscore
# name ("Vampirella_V3_002_") hides its number from app.parse_name, so it never counts as unnumbered either.
NUMBERED_NAME = re.compile(r'\d|_|#|\b(?:vol(?:ume)?|book|part|chapter|tome)\b', re.I)
RULES_VERSION = 2  # Raised when Metron's matching rules change; misses recorded under older rules are asked again.


def unnumbered_book(path):
    """The filename names no number of any kind outside brackets, and no "(of N)" part (Enrichment C)."""
    from pathlib import Path
    stem = Path(path).stem
    if re.search(r'\(\s*of\s*\d+\s*\)', stem, re.I):
        return False
    return not NUMBERED_NAME.search(re.sub(r'\([^)]*\)|\[[^]]*\]', ' ', stem))


def identity(row, old):
    """(series, number, year, rule) Metron can search for this comic, or None.

    rule says how the year was found and what it must agree with:
    'year'           the ComicInfo Year or a "(YYYY)" in the filename; the issue's cover year
    'filename_year'  Enrichment B: a cover date or year app.parse_name does not read (year_hints.filename_year)
    'folder_year'    Enrichment B: the folder's year; the series' start year, not the cover year
    'yearless'       Enrichment B: no year at all (off unless switched on: measured too loose)
    'unnumbered'     Enrichment C: no issue number; searched as issue 1 of a one-shot, graphic novel or collection"""
    import research, pipeline_config, year_hints
    series, number = research.query_identity(row, old)
    if not series:
        return None
    year, rule = str(old.get('Year') or row.get('year') or ''), 'year'
    if not year and pipeline_config.matching('filename_year_formats'):
        year, rule = year_hints.filename_year(row['path']), 'filename_year'
    if not number:
        if year and pipeline_config.matching('unnumbered_as_one') and unnumbered_book(row['path']):
            return series, '1', year, 'unnumbered'
        return None
    if year:
        return series, number, year, rule
    if pipeline_config.matching('folder_year'):
        start = year_hints.folder_year(row['path'])
        if start:
            return series, number, start, 'folder_year'
    if pipeline_config.matching('yearless'):
        return series, number, '', 'yearless'
    return None


_stamp = (None, '')


def rules_stamp():
    """The matching rules in force; a Metron miss recorded under another stamp is asked once more.
    Kept until config.json changes: scheduling asks for it per comic, and each answer reads config.json."""
    global _stamp
    import pipeline_config
    key = pipeline_config.config_key()
    if _stamp[0] == key:
        return _stamp[1]
    value = str(RULES_VERSION) + ':' + ','.join(name for name in sorted(pipeline_config.MATCHING_DEFAULTS) if pipeline_config.matching(name))
    _stamp = (key, value)
    return value


def year_agrees(item, rule, year):
    if rule == 'folder_year':
        return str((item.get('series') or {}).get('year_began') or '') == str(year)
    if rule == 'yearless':
        return True
    return str(item.get('cover_date') or '').startswith(str(year)+'-')


def lookup(row, old):
    """Accept a unique exact series/number/year candidate only after cover agreement.

    The series name is also searched in its punctuation and volume variants, and
    a candidate whose primary cover differs is checked against its variant covers
    before it is rejected; a variant match drops the primary cover's barcode.
    Enrichment B/C: the year may come from a filename date or the folder's series start year, and an unnumbered
    book is searched as issue 1 of a one-shot, graphic novel or collection (identity). Uniqueness and cover
    agreement are required exactly as before."""
    import research
    import automatic
    import reverse_image
    found = identity(row, old)
    if not token() or not found:
        return None
    series, number, year, rule = found
    for name, key, volume in name_variants(series):
        if rule in ('folder_year', 'yearless'):
            import research_runtime
            with research_runtime.stage('Metron candidate search'):
                payload = request('issue/', series_name=name, number=research.issue_number(number))  # Every year.
        else:
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
               and year_agrees(i, rule, year)]
    if len(matches)!=1:
        return None
    candidate=matches[0]
    preview=candidate.get('image') or ''
    # primary holds what accepted the cover (verified_cover's record, v0.5.0 review F4), or a plain truth value.
    primary=not preview or verified_cover(row['path'],preview)
    import research_runtime
    with research_runtime.stage('Metron issue details'):
        detail = request('issue/'+str(int(candidate['id']))+'/')
    if (detail.get('id')!=candidate['id'] or not same_series(detail, key, volume)
        or research.issue_number(detail.get('number')) != research.issue_number(number)
        or not year_agrees(detail, rule, year)):
        return None
    if rule == 'unnumbered' and ((detail.get('series') or {}).get('series_type') or {}).get('name') not in ONE_ISSUE_TYPES:
        return None  # Issue 1 of an ordinary series is not what an unnumbered book is.
    url = detail.get('image') or ''
    if primary and (not preview or url!=preview):primary=verified_cover(row['path'],url)
    variant=None
    accepted=primary
    if not primary:
        # The comic may carry a variant cover of this exact issue.
        for item in [v for v in detail.get('variants') or [] if isinstance(v,dict) and v.get('image')][:MAX_VARIANT_COVERS]:
            found=verified_cover(row['path'],item['image'])
            if found:
                variant,accepted=item,found;break
        if not variant:return None
    # Which cover accepted the write and how (v0.5.0 review F4), kept beside match_rule in the evidence and pass plan.
    cover_match=dict(accepted) if isinstance(accepted,dict) else {}
    cover_match['image']='variant: '+str(variant.get('name') or 'unnamed') if variant else 'primary'
    language=(detail.get('series') or {}).get('language')
    if language and str(language).lower() not in ('en','eng','english'):return None
    fields=metadata_fields(detail)
    if variant:fields.pop('GTIN',None)  # The detail's barcode belongs to the primary cover.
    text=unescape(re.sub('<[^>]+>',' ',detail.get('desc') or '')).strip()
    scope='Exact issue identity and '+('variant cover ('+str(variant.get('name') or 'unnamed')+')' if variant else 'cover')+' verified'
    # match_rule (Enrichment B/C) stays in the evidence and the pass plan, so writes made under a looser rule can be found.
    return {'provider':'Metron','metadata_version':2,'match_rule':rule,'cover_match':cover_match,'fields':fields,'sources':[{'url':'https://metron.cloud/issue/'+str(detail['id'])+'/', 'title':detail.get('issue') or series+' #'+number, 'text':text,'scope':scope,'retrieved':time.time()}] if text else [],'status':'issue_verified'}
