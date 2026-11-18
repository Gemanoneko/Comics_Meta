"""VerseDB: a fallback after Metron, GCD offline and the ComicVine name search found no match (Sergei 2026-11-18).

Off unless config.json says "sources": {"enabled": ["VerseDB"]} (pipeline_config.OPT_IN_SOURCES). The token is
VERSEDB_TOKEN from the environment, the state root's .env or config env_file (credential_store.setting); it is sent
only as a bearer header to versedb.com and never logged, cached or written. Without it the source reports itself
unavailable and asks nothing.

It is what the read-only precision pilot measured (Team/Research/ComicsMetaOrganizer/VerseDBPrecision_2026-11-18.md:
on 120 comics with a known identity, asked as bare filenames, 64 accepted with the language preference, all 64 the
right album or issue, 63 the tag's own edition; 52 of 52 with the plain gate):

1. identity(): Metron's rules with its live defaults ('year', 'filename_year', 'folder_year', 'unnumbered'), and,
   only for comics under the library's `!BD` folder, 'yearless_bd': a number and no year anywhere. That allowance is
   where the pilot needed and measured it (no `!BD` filename carries a year; 14 of 14 BD no-year accepts right).
   Western no-year comics stay out: that is Metron's open B3 decision (its pilot found 9 wrong runs among 41
   unique candidates), and 11 Western no-year accepts do not settle it.
2. series?q=<series>&limit=50: series whose accent-folded name key equals the comic's, by name, a per-language name
   or an alias (matched_by). None, and the name ends in "Vol N"/"vN": the base name is searched once more, and the
   series' volume number must be N.
3. Year pre-filter on the series' start and end years (one year either side); folder year: the start year itself.
   Unnumbered: a one-shot, graphic novel or collected-edition series, or one with a single issue.
4. Language preference (prefer, never filter): French under `!BD`, English elsewhere. When any candidate series is
   in the preferred language, only those are kept; otherwise all stay.
5. More than MAX_SERIES candidate series: no match.
6. series/<id>/issues?q=<number>&limit=100 for each: the same issue number and, for the year rules, a cover or
   release year equal to the year. A list with more pages cannot show one candidate and is refused.
7. Exactly one issue, then its cover against archive images 1-3 (cover_match.archive_match, as Metron).
No variant-cover retry and no detail request, as measured.

Writes a small set: Series, Number, Title, Year/Month/Day (cover date), Web (the VerseDB issue page) and, outside
`!BD`, Publisher (the `!BD` files are translations of the edition matched). Notes name the source URL and carry the
credit VerseDB's terms ask for ("Comic book data from VerseDB", with versedb.com).

Requests: per-comic lookups only, never a bulk download or mirror (terms, section 12). At most HOURLY in any rolling
hour (VerseDB allows 300), SPACING seconds apart, answers cached CACHE_DAYS days. A 429 waits out Retry-After; a low
X-RateLimit-Remaining waits for the next hour; refusals and failures pause only this source (STATUS file).
"""
import json
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import PureWindowsPath
import app
import comicvine_search
import storage
from provider_wait import PacingDeferred, ProviderDeferred

NAME = 'VerseDB'
PROVIDER = 'versedb'
BASE_URL = 'https://versedb.com/api/v1/'
SITE = 'https://versedb.com'
ATTRIBUTION = 'Comic book data from VerseDB (https://versedb.com)'
TOKEN = 'VERSEDB_TOKEN'
RULES = ('year', 'filename_year', 'folder_year', 'unnumbered', 'yearless_bd')
RULES_VERSION = 1
MATCHING = ('filename_year_formats', 'folder_year', 'unnumbered_as_one', 'cover_rule_v2')  # Metron switches it follows.
AFTER = ('Metron', 'GCD offline', 'ComicVine search')
BD_FOLDER = '!bd'
PREFERRED = {True: 'fr', False: 'en'}  # Under `!BD`: French (the original editions); elsewhere English.
SEARCH_LIMIT = 50                       # VerseDB's maximum page; the pilot's first page.
ISSUE_LIMIT = 100
MAX_SERIES = 5
ONE_BOOK_TYPES = {'one_shot', 'graphic_novel', 'collected_edition'}
HOURLY = 280                            # VerseDB: 300 an hour on the free tier; the rest is headroom.
SPACING = 12.0
REMAINING_FLOOR = 10                    # Below this X-RateLimit-Remaining, wait for the next hour.
COVER_SPACING = 3.0
CACHE_DAYS = 30
RATE_LIMIT_WAIT = 3600
AUTH_WAIT = 3600
FAILURE_WAIT = 300
TIMEOUT = 25
MAX_ANSWER = 5 * 1024 * 1024
MAX_COVER = 20 * 1024 * 1024
USER_AGENT = 'ComicMetadata/0.6 (personal catalog)'
CITES = comicvine_search.CITES          # One cite list for both fallbacks.
PATHS = re.compile(r'series|series/\d+/issues')

LOCK = threading.Lock()
COVER_LOCK = threading.Lock()
_last_cover = [0.0]
_stamp = (None, '')


def token():
    import credential_store
    return credential_store.setting(TOKEN)


def status_path():
    return app.DATA / 'versedb-status.json'


def read_status():
    try:
        value = json.loads(status_path().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def set_status(status, retry_at=0, **details):
    storage.save(status_path(), dict({'status': status, 'checked_at': time.time(), 'retry_at': retry_at}, **details))


def cites(old):
    return comicvine_search.cites(old)


def in_bd(path):
    return any(part.casefold() == BD_FOLDER for part in PureWindowsPath(str(path)).parts[:-1])


def fold_key(value):
    """research.series_key after folding accents ("Mattéo" -> "matteo"); series_key alone drops accented letters."""
    import research
    text = unicodedata.normalize('NFKD', str(value or ''))
    return research.series_key(''.join(c for c in text if not unicodedata.combining(c)))


def identity(row, old):
    """(series, number, year, rule) VerseDB may search, or None: the ComicVine name search's identity (Metron's rules)
    and, under `!BD` only, a number with no year at all ('yearless_bd')."""
    import comicvine_search, research
    found = comicvine_search.identity(row, old)
    if not found and in_bd(row['path']):
        series, number = research.query_identity(row, old)
        if series and number and not str(old.get('Year') or row.get('year') or ''):
            found = series, number, '', 'yearless_bd'
    if found and not fold_key(found[0]):
        return None  # A name in another script ("Зайчик") has no key to compare: nothing is asked.
    return found


def can_search(row, old):
    """Whether VerseDB could ask anything for this comic (credentials aside). Not a subset of Metron's: `!BD` comics
    with no year are searchable here."""
    return not cites(old) and identity(row, old) is not None


def rules_stamp():
    global _stamp
    import pipeline_config
    key = pipeline_config.config_key()
    if _stamp[0] == key:
        return _stamp[1]
    value = 'versedb-' + str(RULES_VERSION) + ':' + ','.join(name for name in MATCHING if pipeline_config.matching(name))
    _stamp = (key, value)
    return value


def after_misses(schedule):
    import comicvine_search
    return comicvine_search.after_misses(schedule, AFTER)


def reserve(now=None):
    """0 once a request is entered in the ledger, else the seconds to wait first; ProviderDeferred while this
    source's own wait runs or its rolling-hour allowance is used."""
    now = time.time() if now is None else now
    own_wait = read_status().get('retry_at', 0)
    if own_wait > now:
        raise ProviderDeferred('VerseDB is waiting after a refused or failed request; other sources remain available.',
                               PROVIDER, own_wait, 'cooldown')
    with app.db() as con:
        con.execute('BEGIN IMMEDIATE')
        con.execute('DELETE FROM versedb_requests WHERE timestamp<=?', (now - 3600,))
        used, first, last = con.execute('SELECT COUNT(*),MIN(timestamp),MAX(timestamp) FROM versedb_requests').fetchone()
        if used >= HOURLY:
            raise ProviderDeferred('VerseDB used its hourly allowance; other sources remain available.', PROVIDER, first + 3600, 'limit')
        delay = max(0.0, (last or 0) + SPACING - now)
        if delay:
            return delay
        con.execute('INSERT INTO versedb_requests VALUES(?)', (now,))
        return 0.0


_MISSING = object()


def cache_key(path, params):
    return 'versedb:' + path + '?' + urllib.parse.urlencode(sorted(params.items()))


def cached(key):
    with app.db() as con:
        row = con.execute('SELECT value FROM cache WHERE key=? AND fetched>?', (key, time.time() - CACHE_DAYS * 86400)).fetchone()
    return json.loads(row['value']) if row else _MISSING


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('VerseDB API redirect refused.')  # The bearer token goes to versedb.com only.


def next_hour(now):
    return (int(now // 3600) + 1) * 3600 + 60


def request(path, **params):
    """One VerseDB API answer: from the cache, or one paced GET."""
    import qa_runtime, research_runtime
    if not PATHS.fullmatch(path):
        raise ValueError('Unsupported VerseDB path.')
    key = cache_key(path, params)
    with LOCK:
        while True:
            research_runtime.research_checkpoint()
            answer = cached(key)
            if answer is not _MISSING:
                return answer
            if qa_runtime.policy() is not None:
                raise ProviderDeferred('Private QA uses cached provider answers only.', PROVIDER, 0, 'no_key')
            secret = token()
            if not secret:
                raise ProviderDeferred('Set VERSEDB_TOKEN to enable VerseDB.', PROVIDER, 0, 'no_key')
            delay = reserve()
            if not delay:
                break
            if not research_runtime.pacing_wait(delay):
                # Code review v0.6.5 S3: the pass may not spend this wait; the comic comes back shortly.
                raise PacingDeferred('VerseDB waits for its request spacing; the comic is asked again shortly.',
                                     PROVIDER, time.time() + delay)
        return fetch(path, params, secret, key)


def fetch(path, params, secret, key):
    url = BASE_URL + path + '?' + urllib.parse.urlencode(params)
    headers = {'Authorization': 'Bearer ' + secret, 'Accept': 'application/json', 'User-Agent': USER_AGENT}
    now = time.time()
    try:
        with urllib.request.build_opener(NoRedirect()).open(urllib.request.Request(url, headers=headers), timeout=TIMEOUT) as response:
            remaining = response.headers.get('X-RateLimit-Remaining')
            raw = response.read(MAX_ANSWER + 1)
        if len(raw) > MAX_ANSWER:
            raise ValueError('answer too large')
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError('unexpected answer')
    except urllib.error.HTTPError as exc:
        code = exc.code
        retry = exc.headers.get('Retry-After') if exc.headers else None
        try:
            exc.close()  # The error body is not needed.
        except Exception:
            pass
        if code == 429:
            try:
                wait = max(60, int(retry))
            except (TypeError, ValueError):
                wait = RATE_LIMIT_WAIT
            set_status('rate_limit_wait', now + wait, http_status=429)
            raise ProviderDeferred('VerseDB rate limit reached; it waits before asking again.', PROVIDER, now + wait, 'limit') from None
        if code in (401, 403):
            set_status('authentication_failed', now + AUTH_WAIT, http_status=code)
            raise ProviderDeferred('VerseDB did not accept the token; check VERSEDB_TOKEN.', PROVIDER, now + AUTH_WAIT, 'rejected') from None
        set_status('connection_error', now + FAILURE_WAIT, http_status=code)
        raise ProviderDeferred('VerseDB returned HTTP ' + str(code) + '; it tries again later.', PROVIDER, now + FAILURE_WAIT, 'unreachable') from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        set_status('connection_error', now + FAILURE_WAIT)
        raise ProviderDeferred('VerseDB could not be reached; it tries again later.', PROVIDER, now + FAILURE_WAIT, 'unreachable') from None
    with app.db() as con:
        con.execute('INSERT OR REPLACE INTO cache VALUES(?,?,?)', (key, json.dumps(payload), time.time()))
    try:
        low = remaining is not None and int(remaining) <= REMAINING_FLOOR
    except ValueError:
        low = False
    set_status('available', next_hour(now) if low else 0, remaining=remaining)
    return payload


def image_allowed(url):
    try:
        parsed = urllib.parse.urlparse(str(url))
        port = parsed.port
    except ValueError:
        return False
    host = (parsed.hostname or '').lower()
    return (parsed.scheme == 'https' and not parsed.username and not parsed.password and port in (None, 443)
            and (host == 'versedb.com' or host.endswith('.versedb.com')))


class SameHosts(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not image_allowed(newurl):
            raise ValueError('VerseDB cover redirect refused.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_cover(url):
    """The cover image bytes (no token sent), or None for a URL off VerseDB's hosts or an image over 20 MB."""
    import pause_control, research_runtime
    if not image_allowed(url):
        return None
    with COVER_LOCK:
        pause_control.sleep(max(0.0, _last_cover[0] + COVER_SPACING - time.time()))
        research_runtime.research_checkpoint()
        _last_cover[0] = time.time()
        with urllib.request.build_opener(SameHosts()).open(urllib.request.Request(url, headers={'User-Agent': USER_AGENT}), timeout=TIMEOUT) as response:
            remote = response.read(MAX_COVER + 1)
    return None if len(remote) > MAX_COVER else remote


def verified_cover(path, url):
    import cover_match, research_runtime
    research_runtime.research_checkpoint()
    remote = download_cover(url)
    if remote is None:
        return False
    return cover_match.archive_match(path, remote)


def names(series):
    """(name, how it matched) for every name VerseDB gives a series: its name, per-language names and aliases."""
    found = [(series.get('name'), 'name')]
    for language, value in (series.get('name_i18n') or {}).items():
        if isinstance(value, dict):
            found.append((value.get('value'), 'name:' + str(language)))
    for language, values in (series.get('aliases_i18n') or {}).items():
        for value in values if isinstance(values, list) else []:
            found.append((value, 'alias:' + str(language)))
    return [(value, how) for value, how in found if isinstance(value, str) and value.strip()]


def named(answer, key):
    """[(series, matched_by)] whose folded name key is `key` (never an empty key)."""
    if not key:
        return []
    kept = []
    for series in (answer or {}).get('data') or []:
        if not isinstance(series, dict) or not isinstance(series.get('id'), int):
            continue
        how = next((how for value, how in names(series) if fold_key(value) == key), None)
        if how:
            kept.append((series, how))
    return kept


def language(series):
    return str(series.get('language') or '').split('-')[0].lower()


def year_of(value):
    text = str(value or '')
    return text[:4] if re.match(r'\d{4}-', text) else ''


def series_years_fit(series, rule, year):
    start, end = series.get('start_year'), series.get('end_year')
    if rule == 'folder_year':
        return str(start or '') == str(year)
    if rule == 'yearless_bd':
        return True
    try:
        wanted = int(year)
    except ValueError:
        return False
    if isinstance(start, int) and wanted < start - 1:
        return False
    if isinstance(end, int) and wanted > end + 1:
        return False
    return True


def issue_year_fits(issue, rule, year):
    if rule in ('folder_year', 'yearless_bd'):
        return True  # Folder year: the series' start year was checked. No year: only the number counts.
    return str(year) in (year_of(issue.get('cover_date')), year_of(issue.get('release_date')))


def cover_url(issue):
    images = issue.get('images') if isinstance(issue.get('images'), dict) else {}
    return str(issue.get('cover_url') or images.get('cover_lg') or images.get('cover_md') or '')


def issue_page(issue):
    slug = str(issue.get('slug') or '')
    return SITE + '/issue/' + str(int(issue['id'])) + ('/' + slug if re.fullmatch(r'[a-z0-9-]+', slug) else '')


def lookup(row, old, schedule=None):
    """A verified VerseDB match for this comic, or None.

    schedule: the comic's source_schedule in a discovery pass; the lookup runs only after every switched-on source
    in AFTER answered with no match (comicvine_search.after_misses). Tools pass None to skip that order."""
    import research
    if cites(old):
        return None
    found = identity(row, old)
    if not found or found[3] not in RULES:
        return None
    if schedule is not None:
        state = after_misses(schedule)
        if state == 'found':
            return None
        if state == 'waiting':
            raise ProviderDeferred('VerseDB waits until Metron, GCD offline and the ComicVine name search have answered this comic.',
                                   PROVIDER, time.time() + 3600)
    if not token():
        raise ProviderDeferred('Set VERSEDB_TOKEN to enable VerseDB.', PROVIDER, 0, 'no_key')
    series_name, number, year, rule = found
    bd = in_bd(row['path'])
    wanted = research.issue_number(number)
    candidates = named(request('series', q=series_name, limit=SEARCH_LIMIT), fold_key(series_name))
    volume = None
    if not candidates:
        import metron
        tail = metron.VOLUME_TAIL.search(series_name)
        base = series_name[:tail.start()].strip(' -:,') if tail else ''
        if base:
            volume = int(tail[1])
            candidates = [(s, how) for s, how in named(request('series', q=base, limit=SEARCH_LIMIT), fold_key(base))
                          if str(s.get('number')) == str(volume)]
    candidates = [(s, how) for s, how in candidates if series_years_fit(s, rule, year)]
    if rule == 'unnumbered':
        candidates = [(s, how) for s, how in candidates
                      if s.get('publication_type') in ONE_BOOK_TYPES or s.get('cached_issues_count') == 1]
    preferred = PREFERRED[bd]
    in_language = [(s, how) for s, how in candidates if language(s) == preferred]
    if in_language:
        candidates = in_language  # Prefer, never filter: with none in that language every candidate stays.
    if not candidates or len(candidates) > MAX_SERIES:
        return None
    matches = []
    for series, how in candidates:
        answer = request('series/' + str(int(series['id'])) + '/issues', q=wanted, limit=ISSUE_LIMIT)
        issues = (answer or {}).get('data') or []
        meta = (answer or {}).get('meta') or {}
        if meta.get('last_page', 1) not in (None, 1) or (isinstance(meta.get('total'), int) and meta['total'] > len(issues)):
            return None  # More pages cannot show one candidate.
        matches += [(series, how, issue) for issue in issues
                    if isinstance(issue, dict) and isinstance(issue.get('id'), int)
                    and research.issue_number(issue.get('issue_number')) == wanted and issue_year_fits(issue, rule, year)]
    if len(matches) != 1:
        return None
    series, how, issue = matches[0]
    image = cover_url(issue)
    accepted = verified_cover(row['path'], image) if image else False
    if not accepted:
        return None
    web = issue_page(issue)
    fields = {'Series': series.get('name'), 'Number': issue.get('issue_number'), 'Title': issue.get('name'), 'Web': web}
    date = str(issue.get('cover_date') or '')
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', date):
        fields.update(zip(('Year', 'Month', 'Day'), date.split('-')))
    if not bd and series.get('publisher_name'):
        fields['Publisher'] = series['publisher_name']
    fields = {k: str(v).strip() for k, v in fields.items() if isinstance(v, (str, int)) and str(v).strip()}
    return {'provider': NAME, 'match_rule': rule, 'cover_match': dict(accepted, image='primary'),
            # Kept beside match_rule in the evidence and the pass-plan entry, so a wrong write can be traced.
            'name_search': {'query': series_name, 'number': wanted, 'year': year, 'series_id': series['id'],
                            'series': series.get('name'), 'matched_by': how, 'language': language(series) or None,
                            'preferred': preferred, 'start_year': series.get('start_year'), 'volume': volume,
                            'candidates': len(candidates), 'issue_id': issue['id'], 'rules': rules_stamp()},
            'fields': fields,
            'sources': [{'url': web, 'title': issue.get('name') or series_name + ' #' + number, 'text': '',
                         'scope': 'Exact series, issue number and year from a VerseDB search; one candidate; cover verified',
                         'retrieved': time.time()}],
            'attribution': ATTRIBUTION,
            'status': 'issue_verified'}
