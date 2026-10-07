"""Local comic metadata pilot. Python standard library only."""
import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import zipfile
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA = BASE / 'data'
BIBLIOGRAPHIC_FIELDS=('Series','Title','Number','Count','Volume','Year','Month','Day','Writer','Penciller','Inker','Colorist','Letterer','CoverArtist','Editor','Publisher','Imprint','Genre','Tags','Characters','Teams','Locations','StoryArc','SeriesGroup','LanguageISO','Format','AgeRating','ISBN','GTIN')
JOB = {'running': False, 'visited': 0, 'changed': 0, 'errors': 0, 'message': 'Ready'}
LOCK = threading.Lock()
API_LOCK = threading.Lock()


def live_root():
    config_path = BASE / 'config.json'
    config = json.loads(config_path.read_text(encoding='utf-8')) if config_path.exists() else {}
    automatic = config.get('automatic', {})
    return automatic.get('library_root') or automatic.get('root') or ''


def scope_filter(root):
    # A literal path prefix avoids treating underscores and percent signs as wildcards.
    prefix = str(Path(root)).rstrip('\\/') + os.sep if root else ''
    return "(?='' OR substr(path,1,?)=? COLLATE NOCASE)", (prefix, len(prefix), prefix)


def api_key():
    value = os.environ.get('COMICVINE_API_KEY', '').strip()
    if value:
        return value
    config_path = BASE / 'config.json'
    config = json.loads(config_path.read_text(encoding='utf-8')) if config_path.exists() else {}
    paths = [BASE / '.env', BASE.parents[1] / '.env']
    if config.get('env_file'):
        paths.append(Path(config['env_file']))
    for path in paths:
        if not path.is_file():
            continue
        raw = path.read_text(encoding='utf-8-sig').strip()
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('export '):
                line = line[7:].strip()
            if '=' in line:
                name, candidate = line.split('=', 1)
                if name.strip() != 'COMICVINE_API_KEY':
                    continue
                candidate = candidate.strip()
                if len(candidate) >= 2 and candidate[0] == candidate[-1] and candidate[0] in {'"', "'"}:
                    candidate = candidate[1:-1]
                else:
                    candidate = candidate.split(' #', 1)[0].strip()
                if candidate:
                    return candidate
            elif re.fullmatch(r'[a-fA-F0-9]{40}', line):
                return line
    return ''


class Connection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


def db():
    DATA.mkdir(exist_ok=True)
    con = sqlite3.connect(DATA / 'catalog.sqlite', timeout=30, factory=Connection)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA journal_mode=WAL')
    con.executescript('''
        CREATE TABLE IF NOT EXISTS roots(path TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS comics(
            id INTEGER PRIMARY KEY, path TEXT UNIQUE, root TEXT,
            size INTEGER, mtime INTEGER, series TEXT, number TEXT, year TEXT,
            metadata TEXT, status TEXT, error TEXT, seen INTEGER);
        CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY, value TEXT, fetched REAL);
        CREATE TABLE IF NOT EXISTS history(
            id INTEGER PRIMARY KEY, path TEXT, backup TEXT, source TEXT, timestamp REAL);
        CREATE TABLE IF NOT EXISTS api_requests(timestamp REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS api_state(id INTEGER PRIMARY KEY, last_attempt REAL, blocked_until REAL);
        INSERT OR IGNORE INTO api_state VALUES(1,0,0);
    ''')
    return con


def parse_name(path):
    title = Path(path).stem
    years = re.findall(r'\((19\d{2}|20\d{2})\)', title)
    clean = re.sub(r'\([^)]*\)|\[[^]]*\]', ' ', title)
    # Only a terminal issue number is trusted; complex chapter naming stays for review.
    match = re.search(r'(?:\s|#)(\d+(?:\.\d+)?[A-Za-z]?)\s*$', clean)
    number = match.group(1).lstrip('0') or '0' if match else ''
    series = clean[:match.start()] if match else clean
    series = re.sub(r'\s+', ' ', series).strip(' -_')
    return series, number, years[0] if years else ''


def filesystem_path(path):
    """Support Windows long paths and literal trailing-dot folder names."""
    value = os.path.abspath(path)
    if os.name == 'nt' and not value.startswith('\\\\?\\'):
        value = '\\\\?\\UNC\\' + value[2:] if value.startswith('\\\\') else '\\\\?\\' + value
    return Path(value)


def metadata_xml(raw):
    inspected=raw.replace(b'\x00',b'').upper()
    if b'<!DOCTYPE' in inspected or b'<!ENTITY' in inspected:
        raise ValueError('XML entity declarations are not supported.')
    try:return ET.fromstring(raw)
    except ET.ParseError:
        declaration=re.match(rb'.*?encoding=[\"\x27]([^\"\x27]+)',raw[:200],re.S)
        encoding='utf-16' if raw.startswith((b'\xff\xfe',b'\xfe\xff')) else declaration[1].decode('ascii').lower() if declaration else 'utf-8-sig'
        if encoding not in ('utf-8','utf8','utf-8-sig','utf-16','utf-16le','utf-16be','iso-8859-1','windows-1252','cp1252'):
            raise
        text=raw.decode(encoding)
        # Illegal controls are separators, not story text. Preserve their spacing.
        text=re.sub('[\x00-\x08\x0b\x0c\x0e-\x1f]','\n',text)
        # Recover bare ampersands without changing CDATA or comments.
        parts=re.split(r'(<!\[CDATA\[.*?\]\]>|<!--.*?-->)',text,flags=re.S)
        for index in range(0,len(parts),2):
            parts[index]=re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[0-9a-fA-F]+;)','&amp;',parts[index])
        return ET.fromstring(''.join(parts))


def read_metadata(path):
    path = filesystem_path(path)
    if path.suffix.lower() != '.cbz':
        return {}, 'unsupported', 'CBR/CB7 are inventoried only in this pilot.'
    with path.open('rb') as handle:signature=handle.read(8)
    if signature.startswith((b'7z\xbc\xaf\x27\x1c',b'Rar!')):
        return {}, 'unsupported', 'Readable RAR/7-Zip container with a .cbz filename; automatic ZIP metadata writes are unavailable.'
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if n.lower() == 'comicinfo.xml']
        if len(names) > 1:
            raise ValueError('Multiple ComicInfo.xml entries; review before writing.')
        if not names:
            return {}, 'missing', ''
        if archive.getinfo(names[0]).file_size > 2_000_000:
            raise ValueError('Metadata exceeds the 2 MB limit.')
        raw = archive.read(names[0])
        xml = metadata_xml(raw)
        if xml.tag != 'ComicInfo':
            raise ValueError('Unexpected metadata root.')
        return {n.tag: n.text or '' for n in xml if n.tag != 'Pages'}, 'embedded', ''


def scan(roots, recursive=True):
    try:
        for root_text in roots:
            root = Path(root_text).resolve()
            if not root.is_dir():
                raise ValueError(f'Folder is unavailable: {root}')
            generation = time.time_ns()
            with db() as con:
                con.execute('INSERT OR IGNORE INTO roots VALUES (?)', (str(root),))
                for folder, dirs, files in os.walk(filesystem_path(root), onerror=lambda e: (_ for _ in ()).throw(e)):
                    dirs[:] = [d for d in dirs if d not in {'.yacreaderlibrary', '.comic-metadata-backups'} and not d.startswith('.comic-metadata-convert-')]
                    if not recursive:dirs[:] = []
                    for name in files:
                        native_folder = folder
                        if native_folder.startswith('\\\\?\\UNC\\'):
                            native_folder = '\\\\' + native_folder[8:]
                        elif native_folder.startswith('\\\\?\\'):
                            native_folder = native_folder[4:]
                        path = Path(native_folder) / name
                        if path.suffix.lower() not in {'.cbz', '.cbr', '.cb7'}:
                            continue
                        JOB['visited'] += 1
                        try:
                            stat = filesystem_path(path).stat()
                            old = con.execute('SELECT * FROM comics WHERE path=?', (str(path),)).fetchone()
                            if old and old['size'] == stat.st_size and old['mtime'] == stat.st_mtime_ns:
                                restored_status = old['status']
                                if restored_status == 'absent':
                                    restored_status = 'unsupported' if path.suffix.lower() != '.cbz' else 'embedded' if json.loads(old['metadata']) else 'missing'
                                    if restored_status == 'embedded' and con.execute('SELECT 1 FROM history WHERE path IN (?,?) LIMIT 1',(str(path),str(filesystem_path(path)))).fetchone():
                                        restored_status = 'tagged'
                                con.execute('UPDATE comics SET seen=?,status=? WHERE id=?', (generation, restored_status, old['id']))
                                continue
                            metadata, status, error = read_metadata(path)
                            series, number, year = parse_name(path)
                            series = metadata.get('Series') or series
                            number = metadata.get('Number') or number
                            year = metadata.get('Year') or year
                        except Exception as exc:
                            JOB['errors'] += 1
                            if not filesystem_path(path).exists():
                                continue
                            stat = filesystem_path(path).stat()
                            with filesystem_path(path).open('rb') as handle:signature=handle.read(4)
                            status='corrupted' if isinstance(exc,zipfile.BadZipFile) and signature.startswith(b'PK') else 'error'
                            metadata, error = {}, str(exc)
                            series, number, year = parse_name(path)
                        con.execute('''INSERT INTO comics(path,root,size,mtime,series,number,year,metadata,status,error,seen)
                            VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET
                            root=excluded.root,size=excluded.size,mtime=excluded.mtime,series=excluded.series,
                            number=excluded.number,year=excluded.year,metadata=excluded.metadata,
                            status=excluded.status,error=excluded.error,seen=excluded.seen''',
                            (str(path), str(root), stat.st_size, stat.st_mtime_ns, series, number, year,
                             json.dumps(metadata), status, error, generation))
                        JOB['changed'] += 1
                        if JOB['visited'] % 100 == 0:
                            con.commit()
                # Only a completed traversal may mark files absent. No files are deleted.
                for candidate in con.execute('SELECT id,path FROM comics WHERE root=? AND seen<>?',(str(root),generation)).fetchall():
                    candidate_path=Path(candidate['path'])
                    if not recursive and candidate_path.parent!=root:
                        continue  # Subfolders were deliberately outside this scan.
                    try:
                        filesystem_path(candidate_path).stat()
                    except FileNotFoundError:
                        con.execute("UPDATE comics SET status='absent' WHERE id=?",(candidate['id'],))
                    except OSError:
                        pass  # An inaccessible file is not confirmed missing.
        JOB['message'] = 'Scan complete'
    except Exception as exc:
        JOB['message'] = str(exc)
    finally:
        JOB['running'] = False


def comic(comic_id):
    with db() as con:
        row = con.execute('SELECT * FROM comics WHERE id=?', (comic_id,)).fetchone()
    if row is None:
        raise ValueError('Comic not found.')
    return dict(row)


def reserve_request(now=None):
    """Persist a conservative global allowance, including failed attempts."""
    now = time.time() if now is None else now
    with db() as con:
        con.execute('BEGIN IMMEDIATE')
        state = con.execute('SELECT * FROM api_state WHERE id=1').fetchone()
        if state['blocked_until'] > now:
            minutes = max(1, int((state['blocked_until'] - now + 59) // 60))
            raise ValueError(f'Metadata lookup is cooling down; retry in about {minutes} minutes.')
        con.execute('DELETE FROM api_requests WHERE timestamp<=?', (now - 3600,))
        count = con.execute('SELECT COUNT(*) FROM api_requests').fetchone()[0]
        if count >= 180:
            raise ValueError('Local hourly request budget reached. Pause and retry later; cached results remain available.')
        delay = max(0, 20 - (now - state['last_attempt']))
        if delay:
            return delay
        con.execute('INSERT INTO api_requests VALUES(?)', (now,))
        con.execute('UPDATE api_state SET last_attempt=? WHERE id=1', (now,))
        return 0


def cooldown(seconds=3600):
    with db() as con:
        con.execute('UPDATE api_state SET blocked_until=MAX(blocked_until,?) WHERE id=1',
                    (time.time() + seconds,))


def comicvine_event(status, **details):
    import storage
    DATA.mkdir(parents=True,exist_ok=True)
    storage.save(DATA/'comicvine-status.json',dict(status=status,checked_at=time.time(),retry_at=0,**details))


def api(resource, **params):
    key = api_key()
    if not key:
        raise ValueError('Set COMICVINE_API_KEY before starting the app to enable online lookup.')
    params['format'] = 'json'
    cache_key = resource + '?' + urllib.parse.urlencode(sorted(params.items()))
    with API_LOCK:
        with db() as con:
            cached = con.execute('SELECT value FROM cache WHERE key=? AND fetched>?',
                                 (cache_key, time.time() - 30 * 86400)).fetchone()
        if cached:
            return json.loads(cached['value'])
        # Shared SQLite reservations survive restarts and coordinate app processes.
        delay = reserve_request()
        while delay:
            time.sleep(min(delay, 20))
            delay = reserve_request()
        query = dict(params, api_key=key)
        comicvine_event('requesting')
        request = urllib.request.Request('https://comicvine.gamespot.com/api/' + resource + '/?' +
                                         urllib.parse.urlencode(query), headers={'User-Agent': 'LocalComicMetadataPilot/0.1'})
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                cooldown()
                comicvine_event('rate_limit_wait',http_status=429)
                raise ValueError('Comic Vine rate limit reached. Online lookup paused for one hour; cached results remain available.') from None
            comicvine_event('access_rejected' if exc.code in (401,403) else 'connection_error',http_status=exc.code)
            raise ValueError(f'Metadata service returned HTTP {exc.code}; try again later.') from None
        except (urllib.error.URLError,TimeoutError,OSError,json.JSONDecodeError):
            comicvine_event('connection_error')
            raise ValueError('Cannot reach the metadata service. Check the connection and try again.') from None
        if payload.get('status_code') == 107:
            cooldown()
            comicvine_event('rate_limit_wait')
            raise ValueError('Comic Vine rate limit reached. Online lookup paused for one hour; cached results remain available.')
        if payload.get('status_code') != 1:
            comicvine_event('access_rejected')
            raise ValueError('Metadata service did not accept the request.')
        result = payload['results']
        with db() as con:
            con.execute('INSERT OR REPLACE INTO cache VALUES(?,?,?)', (cache_key, json.dumps(result), time.time()))
        comicvine_event('available')
        return result


def metadata_from_issue(issue):
    from html import unescape
    description = issue.get('description') or ''
    description = re.sub(r'<(?:br\s*/?|/p)>', '\n', description, flags=re.I)
    summary = unescape(re.sub(r'<[^>]+>', '', description)).strip()
    volume = issue.get('volume') or {}
    fields = {'Series': volume.get('name'), 'Number': issue.get('issue_number'),
              'Title': issue.get('name'), 'Summary': summary, 'Web': issue.get('site_detail_url')}
    date = issue.get('cover_date') or ''
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', date):
        fields.update(zip(('Year', 'Month', 'Day'), date.split('-')))
    roles = {'writer': 'Writer', 'penciler': 'Penciller', 'inker': 'Inker',
             'colorist': 'Colorist', 'letterer': 'Letterer', 'cover': 'CoverArtist', 'editor': 'Editor'}
    for role, field in roles.items():
        names = [p['name'] for p in issue.get('person_credits', [])
                 if role in [r.strip().lower() for r in (p.get('role') or '').split(',')]]
        if names:
            fields[field] = ', '.join(dict.fromkeys(names))
    characters = [p['name'] for p in issue.get('character_credits', [])]
    if characters:
        fields['Characters'] = ', '.join(characters)
    return {k: str(v) for k, v in fields.items() if v}


def write_metadata(row, fields, *, append_notes=False, overwrite_fields=()):
    path = filesystem_path(row['path'])
    stat = path.stat()
    if stat.st_size != row['size'] or stat.st_mtime_ns != row['mtime']:
        raise ValueError('File changed since scanning. Rescan first.')
    if path.suffix.lower() != '.cbz':
        raise ValueError('Only CBZ writing is supported.')
    temporary = path.with_name(path.name + '.metadata-tmp')
    if temporary.exists():
        raise ValueError('A temporary file already exists; inspect it before proceeding.')
    # Parse before backing up; preserve unknown XML fields and page metadata.
    with zipfile.ZipFile(path) as source:
        infos = source.infolist()
        names = [i.filename for i in infos if i.filename.lower() == 'comicinfo.xml']
        if len({i.filename for i in infos}) != len(infos) or len(names) > 1:
            raise ValueError('Duplicate ZIP entries require manual review.')
        read_metadata(path)
        xml = metadata_xml(source.read(names[0])) if names else ET.Element('ComicInfo')
        for key, value in fields.items():
            node = xml.find(key)
            if node is None:
                node = ET.SubElement(xml, key)
            if key == 'Notes' and append_notes and (node.text or '').strip():
                if value not in node.text:
                    node.text += '\n\n' + value
            elif key in overwrite_fields or not (node.text or '').strip():
                node.text = value
        xml_bytes = ET.tostring(xml, encoding='utf-8', xml_declaration=True)
    backup_dir = path.parent / '.comic-metadata-backups'
    backup_dir.mkdir(exist_ok=True)
    backup = backup_dir / (path.name + '.' + str(time.time_ns()) + '.bak')
    shutil.copy2(path, backup)
    try:
        with zipfile.ZipFile(path) as source, zipfile.ZipFile(temporary, 'w') as target:
            target.comment = source.comment
            for info in source.infolist():
                if info.filename.lower() == 'comicinfo.xml':
                    continue
                with source.open(info) as src, target.open(info, 'w') as dst:
                    shutil.copyfileobj(src, dst, length=1024 * 1024)
            target.writestr('ComicInfo.xml', xml_bytes, compress_type=zipfile.ZIP_DEFLATED)
        with zipfile.ZipFile(temporary) as check, zipfile.ZipFile(backup) as original:
            if check.testzip() is not None:
                raise ValueError('Archive validation failed.')
            before = [(i.filename, i.CRC, i.file_size) for i in original.infolist() if i.filename.lower() != 'comicinfo.xml']
            after = [(i.filename, i.CRC, i.file_size) for i in check.infolist() if i.filename.lower() != 'comicinfo.xml']
            if before != after:
                raise ValueError('Archive contents changed unexpectedly.')
        current = path.stat()
        if (current.st_size, current.st_mtime_ns) != (stat.st_size, stat.st_mtime_ns):
            raise ValueError('Comic changed while preparing metadata. Original retained.')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    metadata, _, _ = read_metadata(path)
    stat = path.stat()
    with db() as con:
        con.execute("UPDATE comics SET size=?,mtime=?,metadata=?,status='tagged',error='' WHERE id=?",
                    (stat.st_size, stat.st_mtime_ns, json.dumps(metadata), row['id']))
        con.execute('INSERT INTO history(path,backup,source,timestamp) VALUES(?,?,?,?)',
                    (str(path), str(backup), fields.get('Web', ''), time.time()))
    return str(backup)


def inventory_totals(counts):
    total = sum(value for status, value in counts.items() if status != 'absent')
    return {'total': total, 'updated': counts.get('tagged', 0),
            'corrupted': counts.get('corrupted', 0), 'conversion': counts.get('unsupported', 0)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def respond(self, payload, status=200, mime='application/json'):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}':
            return self.respond({'error': 'Untrusted host'}, 403)
        try:
            url = urllib.parse.urlparse(self.path)
            args = urllib.parse.parse_qs(url.query)
            if url.path == '/':
                return self.respond((BASE / 'static/index.html').read_bytes(), mime='text/html; charset=utf-8')
            if url.path == '/reverse-image.js':
                return self.respond((BASE / 'static/reverse-image.js').read_bytes(), mime='text/javascript; charset=utf-8')
            if url.path == '/api/state':
                with db() as con:
                    root = live_root()
                    scope, scope_args = scope_filter(root)
                    counts = {r['status']: r['n'] for r in con.execute('SELECT status,COUNT(*) n FROM comics WHERE '+scope+' GROUP BY status',scope_args)}
                    roots = [root] if root else [r['path'] for r in con.execute('SELECT path FROM roots')]
                return self.respond({'job': JOB.copy(), 'counts': counts, 'totals': inventory_totals(counts), 'roots': roots,
                                     'online': bool(api_key())})
            if url.path == '/api/progress':
                import pause_control
                progress = DATA / 'progress.json'
                result = json.loads(progress.read_text(encoding='utf-8')) if progress.exists() else {'phase':'Ready','current_folder':'','completed':[]}
                queue_dir = DATA / 'queue'
                tickets = [json.loads(p.read_text(encoding='utf-8')) for p in queue_dir.glob('*.json')]
                heartbeat = queue_dir / 'heartbeat'
                alive = heartbeat.exists() and time.time() - json.loads(heartbeat.read_text(encoding='utf-8'))['timestamp'] < 15
                result['queue'] = {'alive': alive, 'pending':sum(t['state']=='pending' for t in tickets),
                                   'running':sum(t['state']=='running' for t in tickets),
                                   'complete':sum(t['state']=='complete' for t in tickets),
                                   'attention':[{'folder':t['folder'],'error':t.get('error','')} for t in tickets if t['state']=='needs_attention']}
                import discovery_state
                result['research'] = discovery_state.counts(live_root())
                result['live_root'] = live_root()
                result['control'] = pause_control.status()
                import cover_tasks
                result['cover_research'] = cover_tasks.status()
                import browser_search
                result['browser_search'] = browser_search.status()
                import providers
                result['providers'] = providers.statuses()
                folders_path=DATA/'folders.json'
                if folders_path.exists():
                    folder_state=json.loads(folders_path.read_text(encoding='utf-8'))
                    scheduled=folder_state.get('folders',{})
                    result['folders']={'total':len(scheduled),'scanned':sum(bool(v.get('last_pass')) and not v.get('error') for v in scheduled.values()),'passes_complete':sum(v.get('state')=='pass_complete' for v in scheduled.values()),'retry_wait':sum(v.get('state')=='retry_wait' for v in scheduled.values()),
                                       'next_scan_at':min((v.get('next_scan',0) for v in scheduled.values()),default=None),'inventory_pending':bool(folder_state.get('inventory_pending')),'directories_visited':folder_state.get('inventory_visited',0)}
                return self.respond(result)
            if url.path == '/api/comics':
                search = args.get('q', [''])[0]
                status = args.get('status', [''])[0]
                offset = max(0, int(args.get('offset', ['0'])[0]))
                with db() as con:
                    scope, scope_args = scope_filter(live_root())
                    descriptive="EXISTS(SELECT 1 FROM json_each(comics.metadata) WHERE key IN ("+','.join("'"+key+"'" for key in BIBLIOGRAPHIC_FIELDS)+") AND trim(COALESCE(value,''))<>'')"
                    summary="trim(COALESCE(json_extract(metadata,'$.Summary'),''))<>''"
                    category={
                        'needs_synopsis':descriptive+' AND NOT ('+summary+')',
                        'metadata_complete':descriptive+' AND '+summary,
                        'synopsis_only':'NOT ('+descriptive+') AND '+summary,
                    }
                    if status in category:
                        where='WHERE '+scope+" AND path LIKE ? AND status IN ('embedded','tagged') AND "+category[status]
                        params=(*scope_args,'%'+search+'%')
                    else:
                        where = "WHERE "+scope+" AND path LIKE ? AND (?='' OR status=?)"
                        params = (*scope_args, '%' + search + '%', status, status)
                    rows = con.execute('SELECT * FROM comics ' + where + ' ORDER BY path LIMIT 100 OFFSET ?', (*params, offset)).fetchall()
                    total = con.execute('SELECT COUNT(*) FROM comics ' + where, params).fetchone()[0]
                result_rows = []
                for r in rows:
                    item = dict(r)
                    item['has_synopsis'] = bool(json.loads(item['metadata']).get('Summary','').strip())
                    metadata=json.loads(item['metadata'])
                    item['has_metadata']=any(str(metadata.get(key,'')).strip() for key in BIBLIOGRAPHIC_FIELDS)
                    result_rows.append(item)
                return self.respond({'rows': result_rows, 'total': total})
            if url.path == '/api/cover':
                row = comic(int(args['id'][0]))
                if 'index' in args:
                    import reverse_image
                    data,mime,_ = reverse_image.cover(row['path'],int(args['index'][0]))
                    return self.respond(data,mime=mime)
                with zipfile.ZipFile(filesystem_path(row['path'])) as archive:
                    images = sorted([i for i in archive.infolist() if i.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))], key=lambda i: i.filename)
                    if not images or images[0].file_size > 20_000_000:
                        raise ValueError('No suitable cover preview.')
                    mime = 'image/png' if images[0].filename.lower().endswith('.png') else 'image/webp' if images[0].filename.lower().endswith('.webp') else 'image/jpeg'
                    return self.respond(archive.read(images[0]), mime=mime)
            self.respond({'error': 'Not found'}, 404)
        except Exception as exc:
            self.respond({'error': str(exc)}, 400)

    def do_POST(self):
        # Only this local application's browser origin can make changes.
        expected = f'http://127.0.0.1:{self.server.server_port}'
        if self.headers.get('Origin') != expected or self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}':
            return self.respond({'error': 'Untrusted origin'}, 403)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length < 100_000:
                raise ValueError('Invalid request size.')
            body = json.loads(self.rfile.read(length))
            import pause_control
            if self.path in ('/api/pause','/api/resume'):
                return self.respond(pause_control.change(self.path=='/api/pause'))
            if self.path == '/api/open-folder':
                with db() as con:
                    scope, params = scope_filter(live_root())
                    row = con.execute('SELECT path FROM comics WHERE id=? AND '+scope, (int(body['comic']), *params)).fetchone()
                if row is None:
                    raise ValueError('Comic is not in the current library.')
                folder = filesystem_path(row['path']).parent
                if not folder.is_dir():
                    raise ValueError('Folder is unavailable. Check that the library drive is connected.')
                os.startfile(str(folder))
                return self.respond({'ok': True})
            if pause_control.requested():
                raise ValueError('Processing is paused. Resume before starting manual work.')
            if self.path == '/api/browser-resume':
                import browser_search
                return self.respond(browser_search.request_verification())
            if self.path == '/api/scan':
                with LOCK:
                    if JOB['running']:
                        raise ValueError('A scan is already running.')
                    roots = body.get('roots', [])
                    if not roots:
                        roots = [live_root()] if live_root() else []
                    if not roots:
                        raise ValueError('Enter a comics folder first.')
                    for root in roots:
                        if not Path(root).is_dir():
                            raise ValueError(f'Folder is unavailable: {root}')
                    JOB.update(running=True, visited=0, changed=0, errors=0, message='Scanning')
                    threading.Thread(target=scan, args=(roots,), daemon=True).start()
                return self.respond({'ok': True})
            if self.path == '/api/search':
                result = api('search', query=body['query'], resources='volume', limit=20,
                             field_list='id,name,start_year,publisher,image,count_of_issues')
                return self.respond(result)
            if self.path == '/api/issues':
                volume_id = int(body['volume'])
                filters = f'volume:{volume_id}'
                if body.get('number'):
                    filters += ',issue_number:' + str(body['number'])
                result = api('issues', filter=filters, limit=100,
                             field_list='id,name,issue_number,cover_date,image,site_detail_url')
                return self.respond(result)
            if self.path == '/api/preview':
                issue = api('issue/4000-' + str(int(body['issue'])))
                fields = metadata_from_issue(issue)
                volume_id = (issue.get('volume') or {}).get('id')
                if volume_id:
                    volume = api('volume/4050-' + str(int(volume_id)), field_list='publisher')
                    publisher = (volume.get('publisher') or {}).get('name')
                    if publisher:
                        fields['Publisher'] = publisher
                return self.respond(fields)
            if self.path == '/api/apply':
                with LOCK:
                    if JOB['running']:
                        raise ValueError('Wait for scanning to finish.')
                    # Fetch trusted provider fields; do not accept arbitrary XML from browser input.
                    issue = api('issue/4000-' + str(int(body['issue'])))
                    fields = metadata_from_issue(issue)
                    volume_id = (issue.get('volume') or {}).get('id')
                    if volume_id:
                        volume = api('volume/4050-' + str(int(volume_id)), field_list='publisher')
                        if (volume.get('publisher') or {}).get('name'):
                            fields['Publisher'] = volume['publisher']['name']
                    backup = write_metadata(comic(int(body['comic'])), fields)
                return self.respond({'ok': True, 'backup': backup})
            self.respond({'error': 'Not found'}, 404)
        except Exception as exc:
            self.respond({'error': str(exc)}, 400)


class LocalServer(ThreadingHTTPServer):
    allow_reuse_address = False

    def server_bind(self):
        if os.name == 'nt':
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-browser', action='store_true')
    options = parser.parse_args()
    with db():
        pass
    server = LocalServer(('127.0.0.1', options.port), Handler)
    import supervisor
    supervisor_stop = supervisor.start(BASE)
    address = f'http://127.0.0.1:{options.port}'
    print(f'Comic metadata pilot: {address}\nKeep this window open. Ctrl+C stops the app.')
    if not options.no_browser:
        webbrowser.open(address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
    finally:
        supervisor_stop.set()
