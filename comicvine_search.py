"""ComicVine name search: a fallback after Metron and GCD offline found no match (Sergei 2026-11-18).

Off unless config.json says "sources": {"enabled": ["ComicVine search"]} (pipeline_config.OPT_IN_SOURCES).

It is what the read-only pilot measured (Team/Research/ComicsMetaOrganizer/ComicVinePilot_2026-11-17.md: on comics
another tool had tagged, read from the filename only, 157 of 157 accepted matches were the right issue, and 0 of 68
covers of other runs with the same name and number were accepted), on Metron's rules and acceptance checks:

1. identity(): the series, number and year Metron's rules read (metron.identity with its live defaults): 'year',
   'filename_year', 'folder_year' and 'unnumbered'. Never 'yearless' or 'collection_label' (separate decisions),
   and never Metron's other spellings: the series is searched as filed.
2. search?resources=volume&query=<series>&limit=100, first page only: the volumes whose series_key is the comic's.
   'folder_year': the volume's start year is the folder's year. 'unnumbered': the volume has exactly one issue (it
   stands in for Metron's one-shot and collection series types, which ComicVine lacks).
3. issues?filter=volume:<ids>,issue_number:<n>: the same number and, for the year rules, the cover year. A full page
   cannot show that the candidate is the only one and is refused.
4. Exactly one issue, otherwise no match.
5. Its cover: archive images 1-3 against ComicVine's medium image (cover_match, as metron.verified_cover).
6. The issue's details (issue/4000-<id>, the ComicVine ID path's own request and cache entry): the same issue,
   volume, series, number and year again. Fields: what the ID path writes (automatic.verified_issue_fields), with
   the volume's publisher from the search answer, so no volume request is needed.

Requests (ComicVine allows 200 per resource per hour): this source's own rolling-hour allowance per resource
(HOURLY), never more than RESOURCE_CEILING on one resource from both paths together (app.comicvine_requests), and
SPACING seconds between its own requests. It never enters the ID path's allowance (app.reserve_request: 180 an
hour, 20 s apart) and never holds its lock, so it cannot delay or use up the ID path; it does wait while the ID
path's shared cooldown runs. A refusal or failure of its own request pauses only this source (STATUS file), not
the ID path. Its answers share app.api's 30-day cache.
"""
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from html import unescape
import app
import storage
from provider_wait import ProviderDeferred

NAME = 'ComicVine search'          # The source name in config.json, source_schedule and the evidence.
PROVIDER = 'comicvine_search'      # ProviderDeferred's provider: never 'comicvine', the ID path's hold key.
ORIGIN = 'name_search'             # Its rows in app.comicvine_requests.
RULES = ('year', 'filename_year', 'folder_year', 'unnumbered')
RULES_VERSION = 1
MATCHING = ('filename_year_formats', 'folder_year', 'unnumbered_as_one', 'cover_rule_v2')  # Switches it follows.
# Rolling-hour allowance per ComicVine resource. "issue" is shared with the ID path, which may use up to 180 an
# hour: 180 + 15 stays under ComicVine's 200. "search" and "issues" leave at least 40 for the dashboard's manual
# search. Only an accepted candidate asks "issue" (about 6% of searched comics in the pilot).
HOURLY = {'search': 150, 'issues': 150, 'issue': 15}
RESOURCE_CEILING = 190             # Both paths together, per resource and rolling hour.
SPACING = 10.0                     # Seconds between this source's request starts (the pilot's second run).
COVER_SPACING = 3.0                # Seconds between cover downloads (not API requests).
COVER_IMAGES = 3                   # Archive images compared with the ComicVine cover, as Metron.
PAGE = 100                         # Results per page; a full issue page cannot establish uniqueness.
RATE_LIMIT_WAIT = 3600
FAILURE_WAIT = 300
TIMEOUT = 25
MAX_ANSWER = 5 * 1024 * 1024
MAX_COVER = 20 * 1024 * 1024
USER_AGENT = 'LocalComicMetadataPilot/0.1'  # The ID path's.
VOLUME_FIELDS = 'id,name,start_year,publisher,count_of_issues'
ISSUE_FIELDS = 'id,name,issue_number,cover_date,image,volume,site_detail_url'
# A comic whose ComicInfo already cites Metron, GCD or ComicVine is outside the measured pool; ComicVine-linked
# comics belong to the ID path.
CITES = re.compile(r'metron|comics\.org|grand comics database|comic\s*vine|cvdb', re.I)
AFTER = ('Metron', 'GCD offline')
MISS = 'no_verified_match'
FOUND = ('verified', 'verified_no_new_data')
IMAGE_HOSTS = ('comicvine.gamespot.com', 'comicvine.com')
IMAGE_DOMAINS = ('.comicvine.com', '.giantbomb.com')

LOCK = threading.Lock()
COVER_LOCK = threading.Lock()
_last_cover = [0.0]
_stamp = (None, '')


def status_path():
    return app.DATA / 'comicvine-search-status.json'


def read_status():
    try:
        value = json.loads(status_path().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def set_status(status, wait=0, **details):
    now = time.time()
    storage.save(status_path(), dict({'status': status, 'checked_at': now, 'retry_at': now + wait if wait else 0}, **details))


def cites(old):
    return bool(CITES.search(str(old.get('Web') or '') + ' ' + str(old.get('Notes') or '')))


def identity(row, old):
    """(series, number, year, rule) as metron.identity reads them with yearless and collection_label off, or None.

    The same switches decide filename years, folder years and unnumbered books for both sources ("same rules as
    Metron"); Metron's optional yearless and collection-label rules never apply here."""
    import metron, pipeline_config, research, year_hints
    series, number = research.query_identity(row, old)
    if not series:
        return None
    year, rule = str(old.get('Year') or row.get('year') or ''), 'year'
    if not year and pipeline_config.matching('filename_year_formats'):
        year, rule = year_hints.filename_year(row['path']), 'filename_year'
    if not number:
        if year and pipeline_config.matching('unnumbered_as_one') and metron.unnumbered_book(row['path']):
            return series, '1', year, 'unnumbered'
        return None
    if year:
        return series, number, year, rule
    if pipeline_config.matching('folder_year'):
        start = year_hints.folder_year(row['path'])
        if start:
            return series, number, start, 'folder_year'
    return None


def can_search(row, old):
    """Whether the name search could ask anything for this comic (credentials aside): a subset of Metron's."""
    return not cites(old) and identity(row, old) is not None


def rules_stamp():
    """Its matching rules; a miss recorded under another stamp is asked once more (source_scheduling.ready)."""
    global _stamp
    import pipeline_config
    key = pipeline_config.config_key()
    if _stamp[0] == key:
        return _stamp[1]
    value = 'cv-search-' + str(RULES_VERSION) + ':' + ','.join(name for name in MATCHING if pipeline_config.matching(name))
    _stamp = (key, value)
    return value


def after_misses(schedule, after=AFTER):
    """'asked' when every switched-on source in `after` answered this comic with no match; 'found' when one found it
    (verified, even with nothing new); otherwise 'waiting' (unavailable, an error, or never asked).
    VerseDB passes its own list (versedb.AFTER)."""
    import pipeline_config
    state = 'asked'
    for name in after:
        if not pipeline_config.source_enabled(name):
            continue
        result = (schedule.get(name) or {}).get('result')
        if result in FOUND:
            return 'found'
        if result != MISS:
            state = 'waiting'
    return state


def reserve(resource, now=None):
    """0 once a request on `resource` is entered in the ledger, else the seconds to wait first.

    Raises ProviderDeferred while ComicVine's shared cooldown or this source's own wait runs, or when the
    resource's rolling-hour allowance is used (retry when its oldest request is an hour old)."""
    family = app.comicvine_resource(resource)
    if family not in HOURLY:
        raise ValueError('The ComicVine name search does not use this resource.')
    now = time.time() if now is None else now
    own_wait = read_status().get('retry_at', 0)
    if own_wait > now:
        raise ProviderDeferred('ComicVine name search is waiting after a refused or failed request; other sources remain available.',
                               PROVIDER, own_wait, 'cooldown')
    with app.db() as con:
        con.execute('BEGIN IMMEDIATE')
        blocked = con.execute('SELECT blocked_until FROM api_state WHERE id=1').fetchone()[0]
        if blocked > now:
            raise ProviderDeferred('ComicVine is cooling down; the name search waits with it.', PROVIDER, blocked, 'cooldown')
        con.execute('DELETE FROM comicvine_requests WHERE timestamp<=?', (now - 3600,))
        own, own_first = con.execute('SELECT COUNT(*),MIN(timestamp) FROM comicvine_requests WHERE resource=? AND origin=?',
                                     (family, ORIGIN)).fetchone()
        every, every_first = con.execute('SELECT COUNT(*),MIN(timestamp) FROM comicvine_requests WHERE resource=?',
                                         (family,)).fetchone()
        if own >= HOURLY[family]:
            raise ProviderDeferred('ComicVine name search used its hourly allowance for ' + family + '; other sources remain available.',
                                   PROVIDER, own_first + 3600, 'limit')
        if every >= RESOURCE_CEILING:
            raise ProviderDeferred('ComicVine ' + family + ' requests are near their hourly limit; the name search waits.',
                                   PROVIDER, every_first + 3600, 'limit')
        last = con.execute('SELECT MAX(timestamp) FROM comicvine_requests WHERE origin=?', (ORIGIN,)).fetchone()[0] or 0
        delay = max(0.0, last + SPACING - now)
        if delay:
            return delay
        con.execute('INSERT INTO comicvine_requests VALUES(?,?,?)', (now, family, ORIGIN))
        return 0.0


_MISSING = object()


def cached(cache_key):
    """app.api's cache entry for this request (30 days), _MISSING, or ComicVineNotFound for a remembered 101."""
    with app.db() as con:
        row = con.execute('SELECT value FROM cache WHERE key=? AND fetched>?', (cache_key, time.time() - 30 * 86400)).fetchone()
        if row:
            return json.loads(row['value'])
        missing = con.execute('SELECT 1 FROM cache WHERE key=? AND fetched>?',
                              (app.NOT_FOUND_PREFIX + cache_key, time.time() - app.NOT_FOUND_SECONDS)).fetchone()
    if missing:
        raise app.ComicVineNotFound('ComicVine reports that the issue does not exist (Object Not Found).')
    return _MISSING


def request(resource, **params):
    """One ComicVine API answer for the name search, from app.api's cache or one paced request."""
    import pause_control, qa_runtime, research_runtime
    params['format'] = 'json'
    cache_key = resource + '?' + urllib.parse.urlencode(sorted(params.items()))  # app.api's key: answers are shared.
    with LOCK:
        while True:
            research_runtime.research_checkpoint()
            answer = cached(cache_key)
            if answer is not _MISSING:
                return answer
            if qa_runtime.policy() is not None:
                raise ProviderDeferred('Private QA uses cached provider answers only.', PROVIDER, 0, 'no_key')
            key = app.api_key()
            if not key:
                raise ProviderDeferred('Set COMICVINE_API_KEY to enable online lookup.', PROVIDER, 0, 'no_key')
            delay = reserve(resource)
            if not delay:
                break
            pause_control.sleep(delay)
        return fetch(resource, params, key, cache_key)


def fetch(resource, params, key, cache_key):
    url = 'https://comicvine.gamespot.com/api/' + resource + '/?' + urllib.parse.urlencode(dict(params, api_key=key))
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': USER_AGENT}), timeout=TIMEOUT) as response:
            raw = response.read(MAX_ANSWER + 1)
        if len(raw) > MAX_ANSWER:
            raise ValueError('answer too large')
        payload = json.loads(raw)
    except urllib.error.HTTPError as exc:
        try:
            payload = app.not_found_payload(exc)
        finally:
            exc.close()
        if payload is None:
            if exc.code in (420, 429):
                set_status('rate_limit_wait', RATE_LIMIT_WAIT, http_status=exc.code)
                raise ProviderDeferred('ComicVine refused the name search for now (rate limit); it waits an hour.',
                                       PROVIDER, time.time() + RATE_LIMIT_WAIT, 'limit') from None
            set_status('access_rejected' if exc.code in (401, 403) else 'connection_error', FAILURE_WAIT, http_status=exc.code)
            raise ProviderDeferred('ComicVine returned HTTP ' + str(exc.code) + ' to the name search; it tries again later.',
                                   PROVIDER, time.time() + FAILURE_WAIT, 'unreachable') from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        set_status('connection_error', FAILURE_WAIT)
        raise ProviderDeferred('ComicVine could not be reached for the name search; it tries again later.',
                               PROVIDER, time.time() + FAILURE_WAIT, 'unreachable') from None
    code = payload.get('status_code') if isinstance(payload, dict) else None
    if code == 107:
        set_status('rate_limit_wait', RATE_LIMIT_WAIT, status_code=107)
        raise ProviderDeferred('ComicVine refused the name search for now (rate limit); it waits an hour.',
                               PROVIDER, time.time() + RATE_LIMIT_WAIT, 'limit')
    if code == 101:
        with app.db() as con:
            con.execute('INSERT OR REPLACE INTO cache VALUES(?,?,?)', (app.NOT_FOUND_PREFIX + cache_key,
                        json.dumps({'status_code': 101, 'error': str(payload.get('error') or 'Object Not Found')[:200]}), time.time()))
        set_status('available')
        raise app.ComicVineNotFound('ComicVine reports that ' + resource + ' does not exist (Object Not Found).')
    if code != 1:
        set_status('access_rejected', FAILURE_WAIT, status_code=code)
        raise ProviderDeferred('ComicVine did not accept the name search request; it tries again later.',
                               PROVIDER, time.time() + FAILURE_WAIT, 'rejected')
    result = payload.get('results')
    with app.db() as con:
        con.execute('INSERT OR REPLACE INTO cache VALUES(?,?,?)', (cache_key, json.dumps(result), time.time()))
    set_status('available')
    return result


def image_allowed(url):
    try:
        parsed = urllib.parse.urlparse(str(url))
        port = parsed.port
    except ValueError:
        return False
    host = (parsed.hostname or '').lower()
    return (parsed.scheme == 'https' and not parsed.username and not parsed.password and port in (None, 443)
            and (host in IMAGE_HOSTS or host.endswith(IMAGE_DOMAINS)))


class SameHosts(urllib.request.HTTPRedirectHandler):
    """A cover redirect must stay on ComicVine's image hosts."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not image_allowed(newurl):
            raise ValueError('ComicVine cover redirect refused.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_cover(url):
    """ComicVine's cover image bytes, or None for a URL off its image hosts or an image over 20 MB."""
    import pause_control, research_runtime
    if not image_allowed(url):
        return None
    with COVER_LOCK:
        pause_control.sleep(max(0.0, _last_cover[0] + COVER_SPACING - time.time()))
        research_runtime.research_checkpoint()
        _last_cover[0] = time.time()
        request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.build_opener(SameHosts()).open(request, timeout=TIMEOUT) as response:
            remote = response.read(MAX_COVER + 1)
    return None if len(remote) > MAX_COVER else remote


def verified_cover(path, url):
    """False, or what accepted the cover: {'comparison': 'today'|'aligned'|'wraparound', 'page': 1-3}.

    metron.verified_cover's comparison on ComicVine's image (cover_match.archive_match): an unreadable first archive
    image fails the lookup, pages 2 and 3 are extra chances only."""
    import cover_match, research_runtime
    research_runtime.research_checkpoint()
    remote = download_cover(url)
    if remote is None:
        return False
    return cover_match.archive_match(path, remote, COVER_IMAGES)


def volume_id(item):
    try:
        return int((item.get('volume') or {}).get('id') or 0)
    except (TypeError, ValueError, AttributeError):
        return 0


def image_url(item):
    image = item.get('image') if isinstance(item, dict) else None
    return str(image.get('medium_url') or '') if isinstance(image, dict) else ''


def year_agrees(item, rule, year):
    if rule == 'folder_year':
        return True  # The volume's start year was the folder's year (search stage); a cover year may be later.
    return str(item.get('cover_date') or '').startswith(str(year) + '-')


def lookup(row, old, schedule=None):
    """A verified ComicVine match for this comic, or None.

    schedule: the comic's source_schedule in a discovery pass. The search runs only after every switched-on source
    in AFTER answered with no match (after_misses): when one found the comic it returns None, and while one has not
    answered it waits (ProviderDeferred). Tools pass None to skip that order (they have no pass)."""
    import automatic, research
    if cites(old):
        return None
    found = identity(row, old)
    if not found or found[3] not in RULES or not app.api_key():
        return None
    if schedule is not None:
        state = after_misses(schedule)
        if state == 'found':
            return None
        if state == 'waiting':
            raise ProviderDeferred('ComicVine name search waits until Metron and GCD offline have answered this comic.',
                                   PROVIDER, time.time() + 3600)
    series, number, year, rule = found
    key = research.series_key(series)
    wanted = research.issue_number(number)
    volumes = request('search', query=series, resources='volume', limit=PAGE, field_list=VOLUME_FIELDS)
    named = [v for v in volumes or [] if isinstance(v, dict) and v.get('id') and research.series_key(v.get('name')) == key]
    if rule == 'folder_year':
        named = [v for v in named if str(v.get('start_year') or '') == str(year)]
    if rule == 'unnumbered':
        named = [v for v in named if str(v.get('count_of_issues')) == '1']
    try:
        kept = {int(v['id']): v for v in named}
    except (TypeError, ValueError):
        return None
    if not kept:
        return None
    issues = request('issues', filter='volume:' + '|'.join(str(i) for i in sorted(kept)) + ',issue_number:' + wanted,
                     limit=PAGE, field_list=ISSUE_FIELDS)
    if not isinstance(issues, list) or len(issues) >= PAGE:
        return None  # A full page cannot show the candidate is the only one.
    matches = [i for i in issues if isinstance(i, dict) and volume_id(i) in kept
               and research.issue_number(i.get('issue_number')) == wanted and year_agrees(i, rule, year)]
    if len(matches) != 1:
        return None
    candidate = matches[0]
    try:
        issue_id = int(candidate['id'])
    except (KeyError, TypeError, ValueError):
        return None
    volume = kept[volume_id(candidate)]
    preview = image_url(candidate)
    accepted = verified_cover(row['path'], preview) if preview else False
    if not accepted:
        return None
    detail = request('issue/4000-' + str(issue_id))
    if (not isinstance(detail, dict) or str(detail.get('id')) != str(issue_id) or volume_id(detail) != volume_id(candidate)
            or research.series_key((detail.get('volume') or {}).get('name')) != key
            or research.issue_number(detail.get('issue_number')) != wanted or not year_agrees(detail, rule, year)):
        return None  # Metron's detail checks: the same issue, series, number and year.
    url = image_url(detail)
    if url and url != preview:
        accepted = verified_cover(row['path'], url)
        if not accepted:
            return None
    fields = automatic.verified_issue_fields(detail)
    publisher = (volume.get('publisher') or {}).get('name') if isinstance(volume.get('publisher'), dict) else None
    if publisher and str(publisher).strip():
        fields['Publisher'] = str(publisher).strip()
    if not fields.get('Web'):
        fields['Web'] = 'https://comicvine.gamespot.com/issue/4000-' + str(issue_id) + '/'
    text = unescape(re.sub('<[^>]+>', ' ', str(detail.get('description') or ''))).strip()
    return {'provider': 'ComicVine', 'match_rule': rule,
            'cover_match': dict(accepted, image='primary'),
            # Kept beside match_rule in the evidence and the pass-plan entry, so a wrong write can be traced.
            'name_search': {'query': series, 'number': wanted, 'year': year, 'volume_id': volume_id(candidate),
                            'volume': volume.get('name'), 'start_year': volume.get('start_year'),
                            'volumes': len(kept), 'issue_id': issue_id, 'rules': rules_stamp()},
            'fields': fields,
            'sources': [{'url': fields['Web'], 'title': detail.get('name') or series + ' #' + number, 'text': text,
                         'scope': 'Exact series, issue number and year from a ComicVine name search; one candidate; cover verified',
                         'retrieved': time.time()}],
            'status': 'issue_verified'}
