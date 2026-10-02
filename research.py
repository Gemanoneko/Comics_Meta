"""Cached publisher research. External text is evidence, never instructions."""
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from html import unescape
from pathlib import Path
import app

CACHE = app.DATA / 'research'

def fetch(url):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in {'coffincomicsshop.com', 'coffincomics.com', 'en.wikipedia.org'}:
        raise ValueError('Unapproved research source.')
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / (hashlib.sha256(url.encode()).hexdigest() + '.json')
    if target.exists() and time.time() - target.stat().st_mtime < 7 * 86400:
        return json.loads(target.read_text(encoding='utf-8'))
    request = urllib.request.Request(url, headers={'User-Agent':'ComicMetadataResearch/0.2 (personal catalog)'})
    with urllib.request.urlopen(request, timeout=25) as response:
        if urllib.parse.urlparse(response.url).hostname != parsed.hostname:
            raise ValueError('Research redirected to another host.')
        raw = response.read(3_000_001)
    if len(raw) > 3_000_000:
        raise ValueError('Research response too large.')
    result = json.loads(raw)
    temp = target.with_suffix('.tmp'); temp.write_text(json.dumps(result), encoding='utf-8'); temp.replace(target)
    return result

def normalize(value):
    return re.sub(r'[^a-z0-9]', '', str(value).lower())

def query_identity(row, old):
    series = old.get('Series') or row.get('series') or ''
    number = old.get('Number') or row.get('number') or ''
    # Chapter filenames supply the subtitle; do not confuse chapter with issue number.
    chapter = re.search(r'\(Chapter\s+\d+\)\s*-\s*(.*?)\s+\d+\s*\(\d{4}\)', Path(row['path']).stem, re.I)
    if chapter and normalize(chapter.group(1)) not in normalize(series):
        series += ': ' + chapter.group(1)
    return series, str(number)

def product_matches(title, series, number):
    match = re.match(r'^(.*?)\s*#\s*(\d+[A-Za-z]?)\b', title)
    return bool(match and normalize(match[1]) == normalize(series)
                and issue_number(match[2]) == issue_number(number))

def issue_number(value):
    value=normalize(value)
    match=re.fullmatch(r'(\d+)([a-z]?)',value)
    return str(int(match[1]))+match[2] if match else value

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
    return [{'title':r['title'],'url':'https://en.wikipedia.org/?curid='+str(r['pageid']),
             'scope':'Series candidate; issue not verified'} for r in result.get('query',{}).get('search',[])]

def general_lookup(row,old,cover_hint=None):
    import web_search
    series,number=query_identity(row,old)
    publisher=old.get('Publisher') or ''
    if not publisher:
        aliases={'avatar':'Avatar Press','avatarpress':'Avatar Press','coffin':'Coffin Comics',
                 'coffincomics':'Coffin Comics','image':'Image Comics','imagecomics':'Image Comics',
                 'marvel':'Marvel','marvelcomics':'Marvel','dc':'DC Comics','dccomics':'DC Comics'}
        publisher=aliases.get(normalize((cover_hint or {}).get('publisher') or ''),'')
    query='"'+series+'" #'+number+' '+publisher+' '+str(old.get('Year') or row.get('year') or '')+' comic synopsis'
    queries=[query]
    hint=(cover_hint or {}).get('search_query')
    if isinstance(hint,str) and hint.strip() and normalize(hint)!=normalize(query):queries.append(hint[:200]+' comic')
    candidates=[];errors=[];sources=[]
    for query in queries[:2]:
        try:hits=web_search.search(query)
        except ValueError as exc:
            errors.append(str(exc));break
        candidates.extend(hits)
        for hit in hits[:3]:
            try:
                source=web_search.source(hit['url'])
                title=source['title']
                # Remove common catalog prefixes, not meaningful series text.
                title=re.sub(r'^(?:GCD\s*::\s*Issue\s*::\s*)','',title)
                body=source['identity_text']
                year=str(old.get('Year') or row.get('year') or '')
                if not product_matches(title,series,number):continue
                if not publisher or normalize(publisher) not in normalize(body):continue
                if year and not re.search(r'\b'+re.escape(year)+r'\b',body):continue
                # Discussion posts are leads, not sole identity proof.
                host=urllib.parse.urlparse(source['url']).hostname or ''
                if host=='reddit.com' or host.endswith('.reddit.com'):continue
                source['scope']='Exact issue title, publisher and year agree; edition-specific facts excluded'
                sources.append(source)
                break
            except ValueError as exc:errors.append(str(exc))
        if sources:break
    save_evidence(row['path'],{'web_candidates':candidates,'web_errors':errors,'web_queries':queries})
    if not sources:return None
    return {'fields':{'Series':series,'Number':issue_number(number),'Publisher':publisher},
            'sources':sources,'identity':{'series':series,'number':number},'status':'web_issue_found'}
