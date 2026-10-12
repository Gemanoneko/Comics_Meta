"""Cached publisher research. External text is evidence, never instructions."""
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
import app

CACHE = app.DATA / 'research'

def wiki_status(now=None):
    now=time.time() if now is None else now
    target=app.DATA/'wikipedia-status.json'
    state=json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
    retry=state.get('retry_at',0)
    return {'status':'cooldown_wait' if retry>now else 'available','retry_at':retry if retry>now else 0}


def wiki_rate_wait(error):
    now=time.time()
    value=error.headers.get('Retry-After') if error.headers else None
    retry=now+3600  # Existing first-error retry when the server supplies no valid deadline.
    if value:
        try:retry=now+max(1,int(value))
        except (TypeError,ValueError):
            try:retry=max(now+1,parsedate_to_datetime(value).timestamp())
            except (TypeError,ValueError,OverflowError):pass
    # The browser and metadata process can share research; never replace a longer hold.
    import storage
    with app.db() as con:
        con.execute('BEGIN IMMEDIATE')
        target=app.DATA/'wikipedia-status.json'
        state=json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
        retry=max(retry,state.get('retry_at',0))
        storage.save(target,{'status':'cooldown_wait','retry_at':retry,'http_status':429,'checked_at':now})
    from provider_wait import ProviderDeferred
    return ProviderDeferred('Wikipedia is rate limited; retry scheduled.','wikipedia',retry)


def fetch(url):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in {'coffincomicsshop.com', 'coffincomics.com', 'en.wikipedia.org'}:
        raise ValueError('Unapproved research source.')
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / (hashlib.sha256(url.encode()).hexdigest() + '.json')
    if target.exists() and time.time() - target.stat().st_mtime < 7 * 86400:
        return json.loads(target.read_text(encoding='utf-8'))
    if parsed.hostname=='en.wikipedia.org':
        state=wiki_status()
        if state['retry_at']:
            from provider_wait import ProviderDeferred
            raise ProviderDeferred('Wikipedia is waiting before retrying.','wikipedia',state['retry_at'])
    request = urllib.request.Request(url, headers={'User-Agent':'ComicMetadataResearch/0.2 (personal catalog)'})
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            if urllib.parse.urlparse(response.url).hostname != parsed.hostname:
                raise ValueError('Research redirected to another host.')
            raw = response.read(3_000_001)
    except urllib.error.HTTPError as error:
        if parsed.hostname=='en.wikipedia.org' and error.code==429:
            raise wiki_rate_wait(error) from None
        raise
    if len(raw) > 3_000_000:
        raise ValueError('Research response too large.')
    result = json.loads(raw)
    temp = target.with_suffix('.tmp'); temp.write_text(json.dumps(result), encoding='utf-8'); temp.replace(target)
    return result

def normalize(value):
    return re.sub(r'[^a-z0-9]', '', str(value).lower())


def series_key(value):
    return normalize(re.sub(r"^Brian Pulido['’]s\s+",'',str(value),flags=re.I))

def query_identity(row, old):
    series = old.get('Series') or row.get('series') or ''
    number = old.get('Number') or row.get('number') or ''
    # Chapter filenames supply the subtitle; do not confuse chapter with issue number.
    chapter = re.search(r'\(Chapter\s+\d+\)\s*-\s*(.*?)\s+\d+\s*\(\d{4}\)', Path(row['path']).stem, re.I)
    if chapter and normalize(chapter.group(1)) not in normalize(series):
        subtitle=chapter.group(1)
        if normalize(subtitle).startswith(normalize(series)):
            title=old.get('Title','')
            series=title if normalize(title).startswith(normalize(series)) and not re.search(r'\bchapter\b',title,re.I) else subtitle
        else:series += ': ' + subtitle
    return series, str(number)

def product_matches(title, series, number):
    title=re.sub(r'^(?:GCD\s*::\s*Issue\s*::\s*)','',title)
    match = re.match(r'^(.*?)\s*#\s*(\d+(?:\.\d+)?[A-Za-z]?)\b', title)
    name=re.sub(r'\s*\([^)]*\b(?:19|20)\d{2}\b[^)]*\)\s*',' ',match[1]) if match else ''
    name=re.sub(r"^Brian Pulido['’]s\s+",'',name,flags=re.I)
    return bool(match and normalize(name) == normalize(series)
                and issue_number(match[2]) == issue_number(number))

def issue_number(value):
    value=str(value).strip().lower()
    match=re.fullmatch(r'(\d+(?:\.\d+)?)([a-z]?)',value)
    if match:
        from decimal import Decimal
        return format(Decimal(match[1]).normalize(),'f')+match[2]
    return normalize(value)


def publisher_hint(row,old,cover_hint=None):
    if old.get('Publisher'):return old['Publisher']
    aliases={'avatar':'Avatar Press','avatarpress':'Avatar Press','coffin':'Coffin Comics','coffincomics':'Coffin Comics','image':'Image Comics','imagecomics':'Image Comics','marvel':'Marvel','marvelcomics':'Marvel','dc':'DC Comics','dccomics':'DC Comics'}
    hint=aliases.get(normalize((cover_hint or {}).get('publisher') or ''))
    if hint:return hint
    path=row.get('path','').lower()
    if '(avatar)' in path or '!avatar press' in path:return 'Avatar Press'
    return ''  # A folder hint must still agree with the external source.

def publisher_lookup(row, old):
    approved=app.DATA/'verified-sources.json'
    if approved.exists():
        import reverse_image
        raw,_,_=reverse_image.cover(row['path'],0)
        cover_hash=hashlib.sha256(raw).hexdigest()
        for record in json.loads(approved.read_text(encoding='utf-8')):
            if record.get('cover_sha256')==cover_hash:
                return record['result']
    if normalize(old.get('Publisher')) != 'coffincomics':
        return None
    series, number = query_identity(row, old)
    if not series or not number:
        return None
    url = 'https://coffincomicsshop.com/search/suggest.json?' + urllib.parse.urlencode({
        'q':series + ' #' + number, 'resources[type]':'product', 'resources[limit]':10})
    payload = fetch(url)
    products = payload.get('resources', {}).get('results', {}).get('products', [])
    matches = [p for p in products if product_matches(p.get('title',''), series, number)]
    if not matches:
        return None
    evidence = []
    for product in matches:
        path = urllib.parse.urlparse(product.get('url','')).path
        if not re.fullmatch(r'/products/[a-z0-9-]+', path):
            continue
        detail = fetch('https://coffincomicsshop.com' + path + '.json').get('product', {})
        if not product_matches(detail.get('title',''),series,number) or normalize(detail.get('vendor')) != 'coffincomics':
            continue
        evidence.append({'url':'https://coffincomicsshop.com'+path, 'title':detail['title'],
                         'text':unescape(re.sub('<[^>]+>', ' ', detail.get('body_html') or '')),
                         'scope':'Exact issue title; cover edition unverified', 'retrieved':time.time()})
        break
    if not evidence:
        return None
    # Edition-specific dates, art credits and page counts are deliberately not inferred.
    fields = {'Publisher':'Coffin Comics'}
    writers = re.search(r'Story:\s*(.*?)\s*(?:Interiors|Art|Cover):',evidence[0]['text'],re.I|re.S)
    if writers:
        names = re.sub(r'\s+', ' ',writers[1]).strip()
        if names and len(names) < 250:
            fields['Writer'] = names
    return {'fields':fields, 'identity':{'series':series,'number':number},
            'sources':evidence, 'status':'publisher_issue_found'}

def save_evidence(path, result):
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / ('evidence-' + hashlib.sha256(str(path).encode()).hexdigest() + '.json')
    # Serialize read/merge/write across discovery and the separate browser process.
    with app.db() as con:
        con.execute('BEGIN IMMEDIATE')
        previous = json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
        result = dict(previous, **result, path=str(path))
        import storage
        storage.save(target,result)
    return target

def wiki_candidates(row, old):
    series,number = query_identity(row,old)
    if not series:
        return []
    url = 'https://en.wikipedia.org/w/api.php?' + urllib.parse.urlencode({
        'action':'query','list':'search','srsearch':series+' comics','srlimit':3,'format':'json'})
    result = fetch(url)
    # Discovery only: a series article does not establish this issue's identity.
    candidates=[r for r in result.get('query',{}).get('search',[]) if normalize(series) in normalize(r['title'])]
    def rank(candidate):
        title=candidate['title'].lower()
        snippet=unescape(re.sub('<[^>]+>',' ',candidate.get('snippet',''))).lower()
        comic=bool(re.search(r'\b(?:comics?|comic books?|graphic novels?)\b',title))
        screen=bool(re.search(r'\b(?:film|television|tv series|episodes?)\b',title))
        return (not comic,screen,not bool(re.search(r'\b(?:comics?|comic books?)\b',snippet)))
    return [{'title':r['title'],'pageid':r['pageid'],'url':'https://en.wikipedia.org/?curid='+str(r['pageid']),
             'scope':'Series candidate; issue not verified'} for r in sorted(candidates,key=rank)]


def wiki_footer_search(url):
    parsed=urllib.parse.urlparse(url)
    host=(parsed.hostname or '').lower().removeprefix('www.')
    return (host in {'google.com','bing.com','duckduckgo.com','search.yahoo.com'} and parsed.path in {'/search','/html/','/html','/'}) or (host=='jstor.org' and parsed.path=='/action/doBasicSearch')


def wiki_lead_rank(lead,series,number):
    path=urllib.parse.unquote(urllib.parse.urlparse(lead['url']).path)
    issue=bool(number and re.search(r'(?<!\d)0*'+re.escape(issue_number(number))+r'(?!\d)',path))
    specific=bool(re.search(r'/(?:issues?|comics?|products?)(?:/|[-_])',path,re.I))
    return (not (issue and normalize(series) in normalize(path)),not specific)


def verify_web_source(row,old,source,cover_hint=None,require_cover=False):
    """Reject broad series articles, wrong issues and discussion-only identity claims."""
    series,number=query_identity(row,old)
    publisher=publisher_hint(row,old,cover_hint)
    host=urllib.parse.urlparse(source['url']).hostname or ''
    if host=='reddit.com' or host.endswith('.reddit.com'):return None
    titles=[source.get('title',''),*source.get('headings',[])]
    if not any(product_matches(t,series,number) for t in titles):return None
    body=source.get('identity_text') or source.get('text','')
    if not publisher or normalize(publisher) not in normalize(body):return None
    year=str(old.get('Year') or row.get('year') or '')
    if year and not re.search(r'\b'+re.escape(year)+r'\b',body):return None
    if require_cover:
        import web_search,reverse_image,automatic
        image=source.get('image')
        if not image:return None
        image=urllib.parse.urljoin(source['url'],image)
        remote=web_search.read(image,binary=True)
        local,_,_=reverse_image.cover(row['path'],0)
        if not automatic.covers_agree(local,remote):return None
    evidence=dict(source,scope='Exact issue, publisher and available year agree'+('; cover agrees' if require_cover else '; edition-specific facts excluded'))
    return {'provider':'Verified web research','fields':{'Series':series,'Number':issue_number(number),'Publisher':publisher},'sources':[evidence],'identity':{'series':series,'number':number},'status':'web_issue_found'}


def resolve_leads(row,old,cover_hint=None):
    """Follow relevant wiki references and saved web/reverse-image results automatically."""
    import web_search
    target=CACHE/('evidence-'+hashlib.sha256(row['path'].encode()).hexdigest()+'.json')
    evidence=json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
    leads=list(evidence.get('web_candidates',[]))+list(evidence.get('reverse_image_matches',[]))
    inspected=[];errors=[];wiki_leads=[];skipped=[];deferred=None
    series,number=query_identity(row,old)
    wiki=[c for c in evidence.get('wiki_candidates',[]) if normalize(series) in normalize(c.get('title',''))]
    for candidate in wiki[:2]:
        if not candidate.get('pageid'):continue
        try:
            url='https://en.wikipedia.org/w/api.php?'+urllib.parse.urlencode({'action':'query','prop':'extlinks','pageids':candidate['pageid'],'ellimit':20,'format':'json'})
            payload=fetch(url)
            for page in payload.get('query',{}).get('pages',{}).values():
                for link in page.get('extlinks',[]):
                    value=link.get('*') or link.get('url','')
                    if value.startswith('https://'):
                        if wiki_footer_search(value):skipped.append(value)
                        else:wiki_leads.append({'url':value,'title':candidate['title']})
        except ValueError as exc:
            from provider_wait import ProviderDeferred
            if isinstance(exc,ProviderDeferred):deferred=exc
            errors.append(str(exc))
    leads.extend(sorted(wiki_leads,key=lambda lead:wiki_lead_rank(lead,series,number)))
    seen=set()
    for lead in leads:
        url=lead.get('url','')
        if not url or url in seen:continue
        seen.add(url)
        if len(seen)>8:break
        try:
            source=web_search.source(url)
            verified=verify_web_source(row,old,source,cover_hint,require_cover=True)
            inspected.append({'url':url,'verified':bool(verified)})
            if verified:
                save_evidence(row['path'],{'lead_verification':inspected,'lead_errors':errors,'wiki_leads_skipped':skipped})
                return verified
        except ValueError as exc:errors.append(str(exc))
    save_evidence(row['path'],{'lead_verification':inspected,'lead_errors':errors,'wiki_leads_skipped':skipped})
    if deferred:raise deferred
    return None

def general_lookup(row,old,cover_hint=None):
    import web_search
    series,number=query_identity(row,old)
    publisher=publisher_hint(row,old,cover_hint)
    query=series+' #'+number+' comics'
    # Ordinary browser engines share one budget and pacing gate, including Yandex.
    # Cover hints still participate in the unchanged issue/source verifier.
    queries=[query]
    candidates=[];errors=[];sources=[];deferred=[];engines=[]
    for engine in web_search.FREE_ENGINES:
        engines.append(engine)
        try:hits=web_search.search(query,free_only=True,engine=engine)
        except ValueError as exc:
            from provider_wait import ProviderDeferred
            if isinstance(exc,ProviderDeferred):deferred.append(exc)
            errors.append(str(exc));continue
        candidates.extend(hits)
        for hit in hits[:3]:
            try:
                source=web_search.source(hit['url'])
                verified=verify_web_source(row,old,source,cover_hint)
                if not verified:continue
                sources.extend(verified['sources'])
                break
            except ValueError as exc:errors.append(str(exc))
        if sources:break
    save_evidence(row['path'],{'web_candidates':candidates,'web_errors':errors,'web_queries':queries,'web_engines':engines})
    if not sources:
        if deferred:raise min(deferred,key=lambda error:error.retry_at if error.retry_at>0 else float('inf'))
        return None
    return {'fields':{'Series':series,'Number':issue_number(number),'Publisher':publisher},
            'sources':sources,'identity':{'series':series,'number':number},'status':'web_issue_found'}
