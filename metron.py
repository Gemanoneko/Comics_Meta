"""Read-only Metron lookup with persistent pacing and secret-safe failures."""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from html import unescape
import app
import storage

STATE = app.DATA / 'metron-status.json'
LOCK = threading.Lock()

def token():
    if os.environ.get('METRON_API_TOKEN'):
        return os.environ['METRON_API_TOKEN'].strip()
    settings = json.loads((app.BASE / 'config.json').read_text(encoding='utf-8'))
    for path in [app.BASE / '.env', app.BASE.parents[1] / '.env', Path(settings.get('env_file', app.BASE / '.env'))]:
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
        with app.db() as con:
            row = con.execute('SELECT value FROM cache WHERE key=? AND fetched>?', (cache_key, time.time()-7*86400)).fetchone()
        if row:
            return json.loads(row['value'])
        state = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {}
        if state.get('retry_at', 0) > time.time():
            raise ValueError('Metron is waiting before retrying; other sources remain available.')
        time.sleep(max(0, state.get('last_request', 0)+3.2-time.time()))
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
            raise ValueError('Metron '+status.replace('_',' ')+'; retry scheduled, other sources remain available.') from None

def lookup(row, old):
    """Accept a unique exact series/number/year candidate only after cover agreement."""
    import research
    import automatic
    import reverse_image
    series, number = research.query_identity(row, old)
    year = old.get('Year') or row.get('year')
    if not token() or not series or not number or not year:
        return None
    payload = request('issue/', series_name=series, number=research.issue_number(number), cover_year=year)
    # A truncated candidate list cannot establish uniqueness.
    if payload.get('next'):
        return None
    matches = [i for i in payload.get('results', []) if research.series_key((i.get('series') or {}).get('name'))==research.series_key(series)
               and research.issue_number(i.get('number'))==research.issue_number(number)
               and str(i.get('cover_date') or '').startswith(str(year)+'-')]
    if len(matches)!=1:
        return None
    detail = request('issue/'+str(int(matches[0]['id']))+'/')
    if research.series_key((detail.get('series') or {}).get('name')) != research.series_key(series) or research.issue_number(detail.get('number')) != research.issue_number(number):
        return None
    url = detail.get('image') or ''
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme!='https' or parsed.hostname!='static.metron.cloud' or parsed.username or parsed.password or parsed.port not in (None,443):
        return None
    with urllib.request.build_opener(NoRedirect()).open(url,timeout=25) as response:
        remote=response.read(20*1024*1024+1)
    if len(remote)>20*1024*1024:
        return None
    local, _, _ = reverse_image.cover(row['path'],0)
    if not automatic.covers_agree(local,remote):
        return None
    fields={'Series':series,'Number':str(detail['number'])}
    text=unescape(re.sub('<[^>]+>',' ',detail.get('desc') or '')).strip()
    return {'provider':'Metron','fields':fields,'sources':[{'url':'https://metron.cloud/issue/'+str(detail['id'])+'/', 'title':detail.get('issue') or series+' #'+number, 'text':text,'scope':'Exact issue identity and cover verified','retrieved':time.time()}] if text else [],'status':'issue_verified'}
