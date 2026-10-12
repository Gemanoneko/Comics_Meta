"""Cached publisher research. External text is evidence, never instructions."""
import hashlib
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zipfile
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

def evidence_target(path):
    return CACHE / ('evidence-' + hashlib.sha256(str(path).encode()).hexdigest() + '.json')


def read_evidence(path):
    target = evidence_target(path)
    return json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}


def merge_evidence(path, result):
    """Read/merge/write one evidence file. The caller holds the shared lock
    (an open BEGIN IMMEDIATE on the catalog), as save_evidence does."""
    CACHE.mkdir(parents=True, exist_ok=True)
    target = evidence_target(path)
    previous = json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
    result = dict(previous, **result, path=str(path))
    import storage
    storage.save(target,result)
    return target


def save_evidence(path, result):
    # Serialize read/merge/write across discovery and the separate browser process.
    with app.db() as con:
        con.execute('BEGIN IMMEDIATE')
        return merge_evidence(path, result)

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


TITLE_SEPARATOR=r'(\s+(?:\||::|-|–|—|·)\s+)'
FORMAT_WORDS=r'tpb|hc|sc|gn|ogn|hardcover|softcover|paperback|trade paperback|graphic novel|one[- ]?shot|collected edition'
BOOK_FORMAT=re.compile(r'\s+('+FORMAT_WORDS+r')\s*$',re.I)
FORMAT_ONLY=re.compile(r'^\s*(?:'+FORMAT_WORDS+r')\s*$',re.I)
YEAR_PAREN=re.compile(r'\s*\([^)]*\b(?:19|20)\d{2}\b[^)]*\)\s*')
# A run of years, e.g. "(2018 - 2021)" or "(2018-)", marks a series page.
YEAR_RANGE=re.compile(r'\(\s*(?:19|20)\d{2}\s*[-–—]\s*(?:(?:19|20)\d{2}|present|current|ongoing)?\s*\)',re.I)
# Words that make a page-title segment more than a site name, format or year:
# numbering, series/edition pages, other media, character pages.
NOT_SITE_WORDS={'issue','issues','part','parts','vol','vols','volume','volumes','chapter','chapters','episode','episodes',
                'season','seasons','tome','no','nr','number','series','run','omnibus','absolute','deluxe','edition','editions',
                'compendium','library','collection','collections','collected','complete','box','variant','variants','cover','covers',
                'review','reviews','preview','previews','annual','annuals','special','specials','film','films','movie','movies',
                'tv','television','game','games','novel','novels','soundtrack','character','characters','team','teams',
                'ii','iii','iv','vi','vii','viii','ix','xi','xii'}
# Numbering spelled out: "Book Two", "Act III", "Arc One".
WORD_NUMBERING=re.compile(r'\b(?:book|act|arc)\s+(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|[ivx]{1,4})\b',re.I)
SERIES_URL=re.compile(r'/(?:series|volumes?|comic-series|comics-series)(?:/|$)|/4050-\d',re.I)
ONE_SHOT_FORMATS={'oneshot'}
BOOK_PAGES=48  # Fewer images than this reads as a single issue, not a collected edition.
LOCAL_BOOK=re.compile(r'\b(?:one[- ]?shots?|ogn|gn|graphic novels?)\b',re.I)
LOCAL_BOOK_FORMATS={'oneshot','graphicnovel','tpb','hc','gn','ogn','tradepaperback','hardcover','omnibus'}
# Editors are credited across a publisher's whole line; they identify no book.
CREATOR_FIELDS=('Writer','Penciller','Inker','Colorist','Letterer','CoverArtist')
ROLE_WORDS={'story','script','scripts','written','writer','words','art','artist','artists','pencil','pencils','penciller','inks','inker',
            'colors','colours','colorist','colourist','letters','letterer','cover','covers','by','and','created','illustrated','illustrator','with','plot',
            'drawn','painted','inked','penciled','pencilled','colored','coloured','lettered'}
ROLE_LABEL=re.compile(r'^\s*(?:(?:'+'|'.join(sorted(ROLE_WORDS-{'by','and','with'}))+r')\b[\s&,/+]*(?:and\b\s*)?)*(?:by\b|:)\s*',re.I)
# A cover-read "creator" that is a company, a character or a title word is not a person.
NOT_PERSON_WORDS={'comics','comic','comix','press','publishing','publications','publisher','entertainment','studio','studios','books',
                  'media','productions','presents','edition','issue','volume','vol','variant','cover','collection','special','annual',
                  'graphic','novel','series','league','universe','the','of','man','woman','men','women','girl','boy','inc','ltd','llc',
                  'group','worldwide'}
FOLD=str.maketrans({'ø':'o','Ø':'O','ł':'l','Ł':'L','đ':'d','Đ':'D','æ':'ae','Æ':'Ae','œ':'oe','Œ':'Oe','ß':'ss','þ':'th','Þ':'Th','ı':'i'})
# Canonical publisher names. A cover reader's partial or one-word publisher
# ("Dark", "Image", "Boom") is only written when a distinctive phrase for the
# whole publisher appears on the page, and then under its canonical name.
PUBLISHERS={
    'Avatar Press':({'avatar','avatarpress'},('avatar press',)),
    'Coffin Comics':({'coffin','coffincomics'},('coffin comics',)),
    'Image Comics':({'image','imagecomics'},('image comics',)),
    'Marvel':({'marvel','marvelcomics'},('marvel comics','marvel entertainment','marvel worldwide','published by marvel','publisher marvel')),
    'DC Comics':({'dc','dccomics'},('dc comics','dc entertainment','published by dc','publisher dc')),
    'Dark Horse Comics':({'darkhorse','darkhorsecomics'},('dark horse',)),
    'IDW Publishing':({'idw','idwpublishing'},('idw',)),
    'BOOM! Studios':({'boom','boomstudios'},('boom studios',)),
    'Dynamite Entertainment':({'dynamite','dynamiteentertainment'},('dynamite entertainment','dynamite comics')),
    'Oni Press':({'oni','onipress'},('oni press',)),
    'Titan Comics':({'titan','titancomics'},('titan comics',)),
    'Valiant':({'valiant','valiantcomics','valiantentertainment'},('valiant comics','valiant entertainment')),
    'Archie Comics':({'archie','archiecomics'},('archie comics',)),
    'Top Shelf Productions':({'topshelf','topshelfproductions'},('top shelf productions',)),
    'Fantagraphics':({'fantagraphics'},('fantagraphics',)),
    'First Comics':({'first','firstcomics'},('first comics',)),
}


def fold(value):
    """Letters without accents, so "Jiří Kylián" and "Jiri Kylian" agree."""
    value=unicodedata.normalize('NFKD',str(value or '').translate(FOLD))
    return ''.join(c for c in value if not unicodedata.combining(c))


def words(value):
    return re.findall(r'[^\W\d_]+',fold(value).lower())


def book_key(value):
    """Normalized book title; a leading article is optional."""
    return series_key(re.sub(r'^\s*the\s+','',str(value),flags=re.I))


def site_segment(segment):
    """A page-title segment that only names a site, a format or a year."""
    segment=segment.strip()
    if not segment or FORMAT_ONLY.match(segment) or re.fullmatch(r'\(?(?:19|20)\d{2}\)?',segment):return True
    if re.search(r'\d',segment) or WORD_NUMBERING.search(segment):return False  # Issue, part, volume or book numbering.
    return not NOT_SITE_WORDS.intersection(words(segment))


def title_format(title,series):
    """Format word ('' for none) when the title names exactly this unnumbered book, else None.

    A page title or heading may add site names, a year or a format word (TPB,
    HC, one-shot). Every other segment must be one of those: a numbered issue,
    part, volume, chapter, series, omnibus/absolute edition, review or other
    media page never matches.
    """
    title=re.sub(r'^(?:GCD\s*::\s*Issue\s*::\s*)','',str(title)).strip()
    expected=book_key(BOOK_FORMAT.sub('',str(series)).strip())
    if not expected or YEAR_RANGE.search(title):return None
    title=YEAR_PAREN.sub(' ',title).strip()
    pieces=re.split(TITLE_SEPARATOR,title);parts=pieces[0::2];separators=pieces[1::2]
    for start in range(len(parts)):
        for stop in range(start+1,len(parts)+1):
            part=parts[start]+''.join(separators[i]+parts[i+1] for i in range(start,stop-1))
            if re.search(r'#\s*\d',part):continue
            found=BOOK_FORMAT.search(part)
            if book_key(BOOK_FORMAT.sub('',part).strip())!=expected:continue
            others=parts[:start]+parts[stop:]
            if not all(site_segment(other) for other in others):continue
            formats=[found[1]] if found else []
            formats+=[other.strip() for other in others if FORMAT_ONLY.match(other)]
            return normalize(formats[0]) if formats else ''
    return None


def title_matches(title,series):
    """Exact title of an unnumbered book (one-shot, graphic novel, collection)."""
    return title_format(title,series) is not None


def archive_pages(path):
    try:
        with zipfile.ZipFile(app.filesystem_path(path)) as archive:
            return sum(1 for i in archive.infolist() if i.filename.lower().endswith(('.jpg','.jpeg','.png','.webp')))
    except (OSError,ValueError,zipfile.BadZipFile):return 0


def local_book(row,old):
    """The file itself says it is a standalone book, not an issue named without its number."""
    import providers
    if providers.is_book(row,old) or LOCAL_BOOK.search(str(row.get('path',''))):return True
    if normalize(old.get('Format')) in LOCAL_BOOK_FORMATS:return True
    return str(old.get('Count') or '').strip()=='1'  # A one-issue series is a one-shot.


def standalone_book(row,old,formats):
    """An unnumbered file only takes the book route when the file, or the page
    together with a book-length archive, shows it is a whole book."""
    if local_book(row,old):return True
    if ONE_SHOT_FORMATS.intersection(formats):return True
    return any(formats) and archive_pages(row['path'])>=BOOK_PAGES


def credit_names(value):
    """Names in one credit string; "Surname, First" stays one person."""
    names=[]
    for part in re.split(r'\s*;\s*',str(value or '')):
        items=[item.strip() for item in part.split(',')]
        if (len(items)>1 and len(items)%2==0 and all(' ' not in item for item in items[0::2])
                and all(re.fullmatch(r"[^\W\d_][\w'’.-]*(?:\s+[^\W\d_]\.?)?",item) for item in items)):
            names.extend(items[i+1]+' '+items[i] for i in range(0,len(items),2))
            continue
        names.extend(re.split(r'\s*(?:,|&|/|\band\b)\s*',part,flags=re.I))
    return names


def name_words(name):
    parts=words(ROLE_LABEL.sub('',name))
    # An unlabelled role word ("Pencils John Romita") is dropped only while a
    # full name remains, so "Art Spiegelman" keeps his first name.
    while len(parts)>2 and parts[0] in ROLE_WORDS:parts=parts[1:]
    return parts


def person(raw,parts,title_words,publisher_words):
    """Model-read cover credits must look like a person, not a title or company."""
    if len(raw.split())<2 or not 2<=len(parts)<=4:return False  # "Spider-Man", "X-Men"
    if NOT_PERSON_WORDS.intersection(parts):return False
    return not set(parts)<=title_words and not set(parts)<=publisher_words


def creator_names(old,cover_hint=None,row=None):
    """Full creator names from embedded credits and visible cover credits."""
    values=[(old.get(key),False) for key in CREATOR_FIELDS]
    hinted=(cover_hint or {}).get('creators')
    if isinstance(hinted,str):hinted=[hinted]
    if isinstance(hinted,list):values.extend((value,True) for value in hinted if isinstance(value,str))
    title_words=set(words(' '.join(str(value or '') for value in (old.get('Series'),old.get('Title'),(row or {}).get('series'),(cover_hint or {}).get('title')))))
    publisher_words=set(words(' '.join([str(old.get('Publisher') or ''),str((cover_hint or {}).get('publisher') or ''),*PUBLISHERS])))
    names=[]
    for value,model in values:
        for name in credit_names(value):
            parts=name_words(name)
            if model and not person(ROLE_LABEL.sub('',name),parts,title_words,publisher_words):continue
            # A surname alone is too common to identify a book.
            if len(parts)>=2 and sum(map(len,parts))>=5 and parts not in names:names.append(parts)
    return names


def named(phrase,text):
    """Whole-word phrase match on letters only."""
    return ' '+' '.join(phrase)+' ' in ' '+' '.join(words(text))+' '


def canonical_publisher(value):
    key=normalize(fold(value))
    return next((name for name,(aliases,_) in PUBLISHERS.items() if key in aliases),'')


def named_in_full(value,body):
    """The page names this multi-word publisher as a whole name, not as part of a longer one."""
    expected=words(value)
    if len(expected)<2:return False  # One word ("Dark", "Image") proves nothing.
    text=fold(body)
    tokens=[(m[0],m.start(),m.end()) for m in re.finditer(r'[^\W\d_]+',text)]
    lowered=[token[0].lower() for token in tokens]
    def continues(index,gap):
        # A capitalized word directly next to the match extends the name.
        return 0<=index<len(tokens) and gap.strip()=='' and tokens[index][0][0].isupper()
    for i in range(len(tokens)-len(expected)+1):
        if lowered[i:i+len(expected)]!=expected:continue
        end=i+len(expected)-1
        before=text[tokens[i-1][2]:tokens[i][1]] if i else ''
        after=text[tokens[end][2]:tokens[end+1][1]] if end+1<len(tokens) else ''
        if not continues(i-1,before) and not continues(end+1,after):return True
    return False


def confirmed_publisher(row,old,cover_hint,body):
    """Any publisher, but only one the source page itself names in full."""
    for value in (old.get('Publisher'),publisher_hint(row,old,cover_hint),(cover_hint or {}).get('publisher')):
        if not isinstance(value,str) or not value.strip():continue
        canonical=canonical_publisher(value)
        if canonical:
            if any(named(words(phrase),body) for phrase in PUBLISHERS[canonical][1]):return canonical
        elif named_in_full(value,body):return value.strip()
    return ''


def cover_agrees(row,source,errors=None):
    """Any failure to read or decode either cover means "not verified" for this source."""
    image=source.get('image')
    if not image:return False
    import web_search,reverse_image,automatic,pause_control
    try:
        # A candidate's image never changes a provider's block or availability state.
        remote=web_search.read(urllib.parse.urljoin(source['url'],image),binary=True,mark_failures=False)
        local,_,_=reverse_image.cover(row['path'],0)
        return bool(automatic.covers_agree(local,remote))
    except pause_control.PauseRequested:raise
    except Exception as exc:
        if errors is not None:errors.append('Candidate cover could not be compared ('+type(exc).__name__+').')
        return False


def verify_web_source(row,old,source,cover_hint=None,require_cover=False,errors=None):
    """Reject broad series articles, wrong issues and discussion-only identity claims.

    A numbered comic always needs its exact issue number in the page title; an
    unnumbered book needs its exact title without one, and must show it is a
    whole book (the file says so, or the page names a book format and the
    archive is book-length); series pages never match. The established route
    (hinted publisher named on the page) is unchanged. Any other publisher, or
    an unnumbered book, additionally needs a known creator named on the page and
    an agreeing cover. A search or cover match alone never authorizes a write.
    """
    series,number=query_identity(row,old)
    if not series:return None
    host=urllib.parse.urlparse(source['url']).hostname or ''
    if host=='reddit.com' or host.endswith('.reddit.com'):return None
    titles=[source.get('title',''),*source.get('headings',[])]
    if number:
        if not any(product_matches(t,series,number) for t in titles):return None
    else:
        if SERIES_URL.search(urllib.parse.urlparse(source['url']).path):return None
        formats=[f for f in (title_format(t,series) for t in titles) if f is not None]
        if not formats or not standalone_book(row,old,formats):return None
    body=source.get('identity_text') or source.get('text','')
    year=str(old.get('Year') or row.get('year') or '')
    if year and not re.search(r'\b'+re.escape(year)+r'\b',body):return None
    publisher=publisher_hint(row,old,cover_hint)
    hinted=bool(number) and bool(publisher) and normalize(publisher) in normalize(body)
    if hinted:
        scope='Exact issue, publisher and available year agree'
    else:
        text=' '+' '.join(words(body))+' '
        if not any(' '+' '.join(name)+' ' in text for name in creator_names(old,cover_hint,row)):return None
        publisher=confirmed_publisher(row,old,cover_hint,body)
        require_cover=True
        scope=('Exact issue' if number else 'Exact title')+', named creator'+(', publisher' if publisher else '')+' and available year agree'
    if require_cover and not cover_agrees(row,source,errors):return None
    evidence=dict(source,scope=scope+('; cover agrees' if require_cover else '; edition-specific facts excluded'))
    fields={'Series':series}
    if number:fields['Number']=issue_number(number)
    if publisher:fields['Publisher']=publisher
    return {'provider':'Verified web research','fields':fields,'sources':[evidence],'identity':{'series':series,'number':number},'status':'web_issue_found'}


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
            verified=verify_web_source(row,old,source,cover_hint,require_cover=True,errors=errors)
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
    # An unnumbered book (one-shot, graphic novel, collection) has no '#'.
    query=series+(' #'+number if number else '')+' comics'
    # Ordinary browser engines share one budget and pacing gate, including Yandex.
    # Cover hints still participate in the unchanged issue/source verifier.
    queries=[query]
    candidates=[];errors=[];sources=[];deferred=[];engines=[];fields={}
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
                verified=verify_web_source(row,old,source,cover_hint,errors=errors)
                if not verified:continue
                sources.extend(verified['sources']);fields=verified['fields']
                break
            except ValueError as exc:errors.append(str(exc))
        if sources:break
    save_evidence(row['path'],{'web_candidates':candidates,'web_errors':errors,'web_queries':queries,'web_engines':engines})
    if not sources:
        if deferred:raise min(deferred,key=lambda error:error.retry_at if error.retry_at>0 else float('inf'))
        return None
    # Only fields the verifier confirmed; never an empty Number or Publisher.
    return {'fields':fields,'sources':sources,'identity':{'series':series,'number':number},'status':'web_issue_found'}
