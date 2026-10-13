"""Local comic metadata pilot. Python standard library only."""
import secrets
import argparse
import hashlib
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
from provider_wait import ProviderDeferred
import app_paths

BASE = Path(__file__).resolve().parent  # Code: modules, static/, VERSION.
STATE_ROOT = app_paths.state_root()  # State: config.json, .env, data/, batches/, work/.
DATA = STATE_ROOT / 'data'
BIBLIOGRAPHIC_FIELDS=('Series','Title','Number','Count','Volume','Year','Month','Day','Writer','Penciller','Inker','Colorist','Letterer','CoverArtist','Editor','Publisher','Imprint','Genre','Tags','Characters','Teams','Locations','StoryArc','SeriesGroup','LanguageISO','Format','AgeRating','ISBN','GTIN')
JOB = {'running': False, 'visited': 0, 'changed': 0, 'errors': 0, 'message': 'Ready'}
LOCK = threading.Lock()
API_LOCK = threading.Lock()


def load_config():
    path = STATE_ROOT / 'config.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def env_files(config=None):
    """Secret files in lookup order: the state root's .env, then config env_file.

    A relative env_file is read from the state root, not the current folder."""
    config = load_config() if config is None else config
    paths = [STATE_ROOT / '.env']
    if config.get('env_file'):
        configured = Path(config['env_file'])
        paths.append(configured if configured.is_absolute() else STATE_ROOT / configured)
    return paths


def live_root():
    automatic = load_config().get('automatic', {})
    return automatic.get('library_root') or automatic.get('root') or ''


def scope_filter(root):
    # A literal path prefix avoids treating underscores and percent signs as wildcards.
    prefix = str(Path(root)).rstrip('\\/') + os.sep if root else ''
    return "(?='' OR substr(path,1,?)=? COLLATE NOCASE)", (prefix, len(prefix), prefix)


def api_key():
    from credential_store import setting
    return setting('COMICVINE_API_KEY')



class Connection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


def db():
    DATA.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DATA / 'catalog.sqlite', timeout=30, factory=Connection)
    try:
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
            CREATE INDEX IF NOT EXISTS history_path ON history(path);
            -- v0.1.4 (Sergei 2026-10-13): which fields each verified write set, and the archive
            -- signature before and after it, so a value the in-book tiers wrote can be told apart
            -- from one Sergei or another program wrote since (provenance.py).
            CREATE TABLE IF NOT EXISTS write_ledger(
                history_id INTEGER PRIMARY KEY, path TEXT, source TEXT, writer TEXT, fields TEXT,
                input_size INTEGER, input_mtime INTEGER, output_size INTEGER, output_mtime INTEGER, origin TEXT);
            CREATE TABLE IF NOT EXISTS api_requests(timestamp REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS api_state(id INTEGER PRIMARY KEY, last_attempt REAL, blocked_until REAL);
            INSERT OR IGNORE INTO api_state VALUES(1,0,0);
            CREATE TABLE IF NOT EXISTS catalog_migrations(name TEXT PRIMARY KEY);
        ''')
        refresh_fractional_numbers(con)
    except BaseException:
        con.close()
        raise
    return con


def refresh_fractional_numbers(con):
    """One in-service catalog repair; archives and embedded metadata are untouched.

    Older parse_name stripped every leading zero, including the zero before a decimal.
    Only rows still holding that exact old parse are repaired; renamed files and human
    metadata stay as they are. The transaction and marker make concurrent starts safe.
    """
    name = 'filename-leading-zero-fraction-v014'
    if con.execute('SELECT 1 FROM catalog_migrations WHERE name=?', (name,)).fetchone():
        return
    con.execute('BEGIN IMMEDIATE')
    try:
        if not con.execute('SELECT 1 FROM catalog_migrations WHERE name=?', (name,)).fetchone():
            rows = con.execute("SELECT id,path,number FROM comics WHERE number LIKE '.%'").fetchall()
            for row in rows:
                number = parse_name(row['path'])[1]
                if number.startswith('0.') and row['number'] == number[1:]:
                    con.execute('UPDATE comics SET number=? WHERE id=? AND number=?',
                                (number, row['id'], row['number']))
            con.execute('INSERT INTO catalog_migrations(name) VALUES(?)', (name,))
        con.commit()
    except BaseException:
        con.rollback()
        raise


def parse_name(path):
    title = Path(path).stem
    years = re.findall(r'\((19\d{2}|20\d{2})\)', title)
    clean = re.sub(r'\([^)]*\)|\[[^]]*\]', ' ', title)
    # Only a terminal issue number is trusted; complex chapter naming stays for review.
    match = re.search(r'(?:\s|#)(\d+(?:\.\d+)?[A-Za-z]?)\s*$', clean)
    number = (match.group(1).lstrip('0') or '0') if match else ''
    if number.startswith('.'):
        number = '0' + number
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
            raise ProviderDeferred(f'Metadata lookup is cooling down; retry in about {minutes} minutes.','comicvine',state['blocked_until'],'cooldown')
        con.execute('DELETE FROM api_requests WHERE timestamp<=?', (now - 3600,))
        count = con.execute('SELECT COUNT(*) FROM api_requests').fetchone()[0]
        if count >= 180:
            raise ProviderDeferred('Local hourly request budget reached. Pause and retry later; cached results remain available.','comicvine',con.execute('SELECT MIN(timestamp) FROM api_requests').fetchone()[0]+3600,'limit')
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
    storage.save(DATA/'comicvine-status.json',dict({'status':status,'checked_at':time.time(),'retry_at':0},**details))


class ComicVineNotFound(ValueError):
    """ComicVine answered that the requested object does not exist (status 101,
    "Object Not Found"), such as a dead or mistyped Web issue id. This is an
    answer about one object, not an outage: no shared cooldown, and the answer
    is cached for NOT_FOUND_SECONDS (F17)."""


NOT_FOUND_SECONDS = 7 * 86400
NOT_FOUND_PREFIX = 'comicvine-not-found:'


def not_found_payload(error):
    """The JSON body of an HTTP 404 that ComicVine marks "Object Not Found", else None.

    Any other 404 (an HTML error page, a moved API) stays an outage."""
    if error.code != 404:
        return None
    try:
        payload = json.loads(error.read(1024 * 1024))
    except Exception:
        return None
    return payload if isinstance(payload, dict) and payload.get('status_code') == 101 else None


def api(resource, **params):
    params['format'] = 'json'
    cache_key = resource + '?' + urllib.parse.urlencode(sorted(params.items()))
    with API_LOCK:
        with db() as con:
            cached = con.execute('SELECT value FROM cache WHERE key=? AND fetched>?',
                                 (cache_key, time.time() - 30 * 86400)).fetchone()
            missing = None if cached else con.execute('SELECT 1 FROM cache WHERE key=? AND fetched>?',
                                                      (NOT_FOUND_PREFIX + cache_key, time.time() - NOT_FOUND_SECONDS)).fetchone()
        if cached:
            return json.loads(cached['value'])
        if missing:
            raise ComicVineNotFound(f'ComicVine reports that {resource} does not exist (Object Not Found).')
        # The cache needs no key: a missing key must not hide a cached answer,
        # such as an identity conflict (F16).
        key = api_key()
        if not key:
            raise ProviderDeferred('Set COMICVINE_API_KEY to enable online lookup.','comicvine',0,'no_key')
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
            try:
                payload = not_found_payload(exc)
            finally:
                exc.close()  # The error body is not needed beyond this point.
            if payload is None:
                if exc.code == 429:
                    cooldown()
                    comicvine_event('rate_limit_wait',http_status=429)
                    raise ProviderDeferred('Comic Vine rate limit reached. Online lookup paused for one hour; cached results remain available.','comicvine',time.time()+3600,'limit') from None
                cooldown(300)
                comicvine_event('access_rejected' if exc.code in (401,403) else 'connection_error',http_status=exc.code,retry_at=time.time()+300)
                raise ProviderDeferred(f'Metadata service returned HTTP {exc.code}; try again later.','comicvine',time.time()+3600,'unreachable') from None
        except (urllib.error.URLError,TimeoutError,OSError,json.JSONDecodeError):
            cooldown(300)
            comicvine_event('connection_error',retry_at=time.time()+300)
            raise ProviderDeferred('Cannot reach the metadata service. Check the connection and try again.','comicvine',time.time()+3600,'unreachable') from None
        if payload.get('status_code') == 107:
            cooldown()
            comicvine_event('rate_limit_wait')
            raise ProviderDeferred('Comic Vine rate limit reached. Online lookup paused for one hour; cached results remain available.','comicvine',time.time()+3600,'limit')
        if payload.get('status_code') == 101:
            # ComicVine answered: this object does not exist. Remember the answer;
            # other requests are unaffected (F17).
            with db() as con:
                con.execute('INSERT OR REPLACE INTO cache VALUES(?,?,?)', (NOT_FOUND_PREFIX + cache_key,
                            json.dumps({'status_code': 101, 'error': str(payload.get('error') or 'Object Not Found')[:200]}), time.time()))
            comicvine_event('available')
            raise ComicVineNotFound(f'ComicVine reports that {resource} does not exist (Object Not Found).')
        if payload.get('status_code') != 1:
            cooldown(300)
            comicvine_event('access_rejected',retry_at=time.time()+300)
            raise ProviderDeferred('Metadata service did not accept the request.','comicvine',time.time()+300,'rejected')
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


def remove_verified_backup(path, backup, original_sha256):
    import library_lock
    library_lock.require(path)  # Raises before any change if another copy owns the library.
    path, backup = filesystem_path(path), filesystem_path(backup)
    intended = path.parent / '.comic-metadata-backups'
    if (backup.is_symlink() or intended.is_symlink()
            or getattr(backup.stat(), 'st_file_attributes', 0) & 0x400
            or getattr(intended.stat(), 'st_file_attributes', 0) & 0x400
            or backup.parent != intended or not backup.name.startswith(path.name + '.')
            or backup.suffix != '.bak'):
        raise ValueError('Backup cleanup target is outside the expected folder.')
    with backup.open('rb') as handle:
        if hashlib.file_digest(handle, 'sha256').hexdigest() != original_sha256:
            raise ValueError('Backup verification failed.')
    backup.unlink()
    try: intended.rmdir()
    except OSError: pass


class ArchiveChanged(ValueError):
    """The archive is no longer what the write was planned against; nothing was written
    to it and any backup already made is kept. A plan skips the comic and plans it
    again from what the archive holds now (v0.1.3 review F22)."""


def write_metadata(row, fields, *, append_notes=False, overwrite_fields=(), remove_verified_backups=False,
                   expected=None, history_source=None, attempt=None, writer='manual'):
    """Write fields into a CBZ's ComicInfo.xml with a backup, temporary-archive checks and readback.

    expected: {field: value} the archive's ComicInfo must still hold, checked on the
    archive as it is read for this write, before any backup or change. A plan decides
    "empty" (or "this value") from an earlier read; a field changed since then, for
    example tagged in another program during the pass, is never overwritten (F22).
    history_source: provenance stored with the write history in the same transaction
    (default: the written Web link), for example 'in-book:cover' (F27).
    attempt: an optional dict. Once this call's backup copy is complete its path is
    stored in attempt['backup'], so a caller whose write then fails knows exactly which
    backup this call made (v0.1.3 review F29). A backup name already in use is never
    reused, so that path always names a file this call created.
    writer: 'automatic' for the service's own plans, 'manual' (default) for anything Sergei
    starts. The write ledger records it with the fields this call set and the archive
    signature before and after, in the history transaction (provenance.py)."""
    import library_lock
    try:
        scanned_root = row['root']
    except (KeyError, IndexError):
        scanned_root = None
    library_lock.require(row['path'], scanned_root)  # Raises before any change if another copy owns the library.
    path = filesystem_path(row['path'])
    stat = path.stat()
    if stat.st_size != row['size'] or stat.st_mtime_ns != row['mtime']:
        raise ArchiveChanged('File changed since scanning. Rescan first.')
    if path.suffix.lower() != '.cbz':
        raise ValueError('Only CBZ writing is supported.')
    temporary = path.with_name(path.name + '.metadata-tmp')
    if temporary.exists():
        raise ValueError('A temporary file already exists; inspect it before proceeding.')
    if remove_verified_backups:
        with path.open('rb') as handle:
            original_sha256 = hashlib.file_digest(handle, 'sha256').hexdigest()
    # Parse before backing up; preserve unknown XML fields and page metadata.
    with zipfile.ZipFile(path) as source:
        infos = source.infolist()
        names = [i.filename for i in infos if i.filename.lower() == 'comicinfo.xml']
        if len({i.filename for i in infos}) != len(infos) or len(names) > 1:
            raise ValueError('Duplicate ZIP entries require manual review.')
        present, _, _ = read_metadata(path)
        if expected:
            # Whitespace-only counts as empty, as it does for planning and the write below.
            stale = sorted(key for key, value in expected.items() if (present.get(key) or '').strip() != (value or '').strip())
            if stale:
                raise ArchiveChanged('ComicInfo changed since planning (' + ', '.join(stale) + '); nothing written.')
        xml = metadata_xml(source.read(names[0])) if names else ET.Element('ComicInfo')
        expected_fields = {}
        written = {}  # Fields this call sets (not Notes, not values it leaves in place).
        for key, value in fields.items():
            node = xml.find(key)
            if node is None:
                node = ET.SubElement(xml, key)
            if key == 'Notes' and append_notes and (node.text or '').strip():
                if value not in node.text:
                    node.text += '\n\n' + value
            elif key in overwrite_fields or not (node.text or '').strip():
                node.text = value
                if key != 'Notes':
                    written[key] = value or ''
            expected_fields[key] = node.text or ''
        # XML parsers normalize literal CR/CRLF to LF. Character references
        # preserve source text exactly, including Windows paragraph breaks.
        xml_bytes = ET.tostring(xml, encoding='utf-8', xml_declaration=True).replace(b'\r', b'&#13;')
    backup_dir = path.parent / '.comic-metadata-backups'
    backup_dir.mkdir(exist_ok=True)
    backup = backup_dir / (path.name + '.' + str(time.time_ns()) + '.bak')
    if backup.exists():
        raise ValueError('A backup with this name already exists; nothing written.')
    shutil.copy2(path, backup)
    if attempt is not None:
        attempt['backup'] = str(backup)
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
            readback = metadata_xml(check.read('ComicInfo.xml'))
            for key,value in expected_fields.items():
                if readback.findtext(key,default='') != value:
                    raise ValueError('Temporary archive metadata verification failed for '+key)
        current = path.stat()
        if (current.st_size, current.st_mtime_ns) != (stat.st_size, stat.st_mtime_ns):
            raise ArchiveChanged('Comic changed while preparing metadata. Original retained.')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    metadata, _, _ = read_metadata(path)
    if remove_verified_backups:
        for key, value in expected_fields.items():
            if metadata.get(key, '') != value:
                raise ValueError('Readback verification failed for ' + key)
    before = stat
    stat = path.stat()
    source_text = str(history_source)[:200] if history_source else fields.get('Web', '')
    with db() as con:
        con.execute("UPDATE comics SET size=?,mtime=?,metadata=?,status='tagged',error='' WHERE id=?",
                    (stat.st_size, stat.st_mtime_ns, json.dumps(metadata), row['id']))
        history_id = con.execute('INSERT INTO history(path,backup,source,timestamp) VALUES(?,?,?,?)',
                                 (str(path), str(backup), source_text, time.time())).lastrowid
        con.execute('INSERT INTO write_ledger VALUES(?,?,?,?,?,?,?,?,?,?)',
                    (history_id, str(row['path']), source_text, writer, json.dumps(written, ensure_ascii=False),
                     before.st_size, before.st_mtime_ns, stat.st_size, stat.st_mtime_ns, 'write'))
    if remove_verified_backups:
        remove_verified_backup(path, backup, original_sha256)
    return str(backup)


def inventory_totals(counts):
    total = sum(value for status, value in counts.items() if status != 'absent')
    return {'total': total, 'updated': counts.get('tagged', 0),
            'corrupted': counts.get('corrupted', 0), 'conversion': counts.get('unsupported', 0)}


def metadata_present_count(con, root):
    scope, params = scope_filter(root)
    fields = ','.join('?' for _ in BIBLIOGRAPHIC_FIELDS)
    return con.execute("SELECT COUNT(*) FROM comics WHERE "+scope+
        " AND status IN ('embedded','tagged') AND trim(COALESCE(json_extract(metadata,'$.Summary'),''))<>''"
        " AND EXISTS(SELECT 1 FROM json_each(comics.metadata) WHERE key IN ("+fields+
        ") AND trim(COALESCE(value,''))<>'')", (*params, *BIBLIOGRAPHIC_FIELDS)).fetchone()[0]


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
            if url.path in ('/reverse-image.js','/lens-control.js','/shell-ui.js'):
                return self.respond((BASE / 'static' / url.path.lstrip('/')).read_bytes(), mime='text/javascript; charset=utf-8')
            if url.path == '/api/shell/status':
                token = os.environ.get('COMICS_META_SHELL_TOKEN', '')
                if not token or not secrets.compare_digest(self.headers.get('X-ComicsMeta-Shell', ''), token):
                    return self.respond({'error': 'Untrusted shell'}, 403)
                import pause_control, browser_search, lens_verification
                verification = lens_verification.status()
                cover = browser_search.public(browser_search.legacy_status())
                return self.respond({'owned': True, 'version': self.server.loaded_version,
                                     'control': pause_control.status(),
                                     'verification': bool(verification.get('human_verification') or cover.get('human_verification')),
                                     'job_running': bool(JOB.get('running')),
                                     'setup': self.server.setup_status()})
            if url.path == '/api/state':
                with db() as con:
                    root = live_root()
                    scope, scope_args = scope_filter(root)
                    counts = {r['status']: r['n'] for r in con.execute('SELECT status,COUNT(*) n FROM comics WHERE '+scope+' GROUP BY status',scope_args)}
                    roots = [root] if root else [r['path'] for r in con.execute('SELECT path FROM roots')]
                    totals = inventory_totals(counts)
                    totals['metadata_and_synopsis'] = metadata_present_count(con, root)
                    totals['needs_information'] = totals['total'] - totals['metadata_and_synopsis']
                return self.respond({'version':getattr(self.server,'loaded_version',''), 'job': JOB.copy(), 'counts': counts, 'totals': totals, 'roots': roots,
                                     'online': bool(api_key())})
            if url.path == '/api/browser-verification':
                import lens_verification,yandex_verification,pause_control
                result=lens_verification.status()
                import browser_search
                # Challenge URLs and the comic that hit them stay worker-only.
                result['cover']=browser_search.public(browser_search.legacy_status())
                result['control']=pause_control.status()
                # Yandex is no longer searched; without a state the dashboard keeps its row hidden.
                result['yandex']=yandex_verification.status() if yandex_verification.active() else None
                return self.respond(result)
            if url.path == '/api/progress':
                import pause_control
                try:result=self.server.progress_snapshot.get(args.get('completed_revision',[None])[0])
                except ValueError as exc:return self.respond({'error':str(exc)},503)
                # Pause status is authoritative, even while aggregates refresh.
                result['control']=pause_control.status()
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
                    import problems
                    if status in category:
                        where='WHERE '+scope+" AND path LIKE ? AND status IN ('embedded','tagged') AND "+category[status]
                        params=(*scope_args,'%'+search+'%')
                    elif status in problems.CODES:
                        # Failure-filter spec: comics whose current record holds this reason (one per comic).
                        con.execute('CREATE TEMP TABLE IF NOT EXISTS problem_paths(path TEXT PRIMARY KEY)')
                        con.execute('DELETE FROM temp.problem_paths')
                        con.executemany('INSERT OR IGNORE INTO temp.problem_paths VALUES(?)',
                                        [(p,) for p in problems.paths_with(con,live_root(),status,search)])
                        where='WHERE path IN (SELECT path FROM temp.problem_paths)'
                        params=()
                    else:
                        where = "WHERE "+scope+" AND path LIKE ? AND (?='' OR status=?)"
                        params = (*scope_args, '%' + search + '%', status, status)
                    rows = con.execute('SELECT * FROM comics ' + where + ' ORDER BY path LIMIT 100 OFFSET ?', (*params, offset)).fetchall()
                    total = con.execute('SELECT COUNT(*) FROM comics ' + where, params).fetchone()[0]
                    found = problems.for_rows(con, rows)
                result_rows = []
                for r in rows:
                    item = dict(r)
                    if item['path'] in found:
                        item['problem'] = found[item['path']]
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
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):
            return
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
            if self.path == '/api/shell/setup':
                token = os.environ.get('COMICS_META_SHELL_TOKEN', '')
                if not token or not secrets.compare_digest(self.headers.get('X-ComicsMeta-Shell', ''), token):
                    return self.respond({'error': 'Untrusted shell'}, 403)
                import setup_state
                try:
                    with self.server._setup_mutex:
                        if self.server._quitting:raise setup_state.SetupError('save_failed')
                        result = setup_state.save(body.get('folder'), body.get('keys', {}))
                        self.server.activate_setup()
                    return self.respond(result)
                except setup_state.SetupError as exc:
                    return self.respond({'error': exc.code, 'field': getattr(exc, 'field', None)}, 400)
            if self.path in ('/api/shell/pause', '/api/shell/cancel-pause'):
                token = os.environ.get('COMICS_META_SHELL_TOKEN', '')
                if not token or not secrets.compare_digest(self.headers.get('X-ComicsMeta-Shell', ''), token):
                    return self.respond({'error': 'Untrusted shell'}, 403)
                return self.respond(pause_control.shell_pause(self.path == '/api/shell/pause'))
            if self.path in ('/api/pause','/api/resume'):
                return self.respond(pause_control.change(self.path=='/api/pause'))
            if self.path == '/api/quit':
                # Allowed while paused; Quit never changes the saved Pause setting.
                return self.respond(self.server.begin_quit())
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
            if self.path == '/api/try-again':
                # Failure-filter spec R4. Allowed while paused: it only clears a stop flag in
                # the comic's record; the one attempt runs at the next pass after Resume.
                import problems
                changed, problem = problems.try_again(int(body['comic']))
                return self.respond({'ok': True, 'changed': changed, 'problem': problem})
            if getattr(self.server, 'setup_required', False):
                return self.respond({'error': 'Finish setup before starting processing.'}, 403)
            if pause_control.requested():
                raise ValueError('Processing is paused. Resume before starting manual work.')
            if self.path == '/api/browser-resume':
                import browser_search
                return self.respond(browser_search.request_verification())
            if self.path == '/api/yandex-verification':
                import yandex_verification
                if not yandex_verification.active():raise ValueError('Yandex web search is switched off.')
                return self.respond(yandex_verification.request(body))
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
                import imprints
                if body.get('comic') is not None:
                    import automatic
                    row=comic(int(body['comic']))
                    present,_,_=read_metadata(filesystem_path(row['path']))
                    fields,_,_=automatic.external_plan(present,fields,{},False)
                    return self.respond(fields)
                return self.respond(imprints.split(fields))  # What Approve writes: an imprint in Imprint.
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
                    import automatic
                    row=comic(int(body['comic']))
                    present,_,_=read_metadata(filesystem_path(row['path']))
                    fields,_,_=automatic.external_plan(present,fields,{},False)
                    backup = write_metadata(row,fields,remove_verified_backups=True)
                return self.respond({'ok': True, 'backup': backup, 'backup_removed_after_verification': True})
            self.respond({'error': 'Not found'}, 404)
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):
            return
        except Exception as exc:
            self.respond({'error': str(exc)}, 400)


class LocalServer(ThreadingHTTPServer):
    allow_reuse_address = False

    def __init__(self,*args,**kwargs):
        # Capture once for this running server; a disk update cannot relabel it.
        try:
            value=(BASE/'VERSION').read_text(encoding='utf-8').strip()
            self.loaded_version=value if re.fullmatch(r'v?\d+\.\d+\.\d+',value) else ''
        except (OSError,UnicodeError):self.loaded_version=''
        self.setup_required=False
        self._setup_mutex=threading.Lock()
        if os.environ.get('COMICS_META_SHELL_TOKEN'):
            import setup_state
            self.setup_required = not setup_state.status()['configured']
        self.supervisor_stop=None
        self.worker_leases={}
        self._quit_mutex=threading.Lock()
        self._quitting=False
        super().__init__(*args,**kwargs)
        import yandex_verification,lens_verification,progress_snapshot
        yandex_verification.server_started()
        lens_verification.server_started()
        self.progress_snapshot=progress_snapshot.Snapshot()

    def setup_status(self):
        if not os.environ.get('COMICS_META_SHELL_TOKEN'):return {'configured': True}
        import setup_state
        return setup_state.status()

    def activate_setup(self):
        if not self.setup_required:return
        import library_lock, supervisor
        library_lock.claim_configured('dashboard')
        self.supervisor_stop=supervisor.start(BASE)
        self.setup_required=False

    def server_close(self):
        if hasattr(self,'progress_snapshot'):self.progress_snapshot.close()
        super().server_close()

    def begin_quit(self):
        """Quit: workers finish their current safe step and exit, then the server stops."""
        with self._quit_mutex:
            if not self._quitting:
                self._quitting=True
                threading.Thread(target=self.finish_quit,name='graceful-quit',daemon=True).start()
        return {'ok':True,'stopping':True}

    def finish_quit(self,worker_timeout=None):
        import pause_control
        try:
            if self.supervisor_stop is not None:self.supervisor_stop.set()  # No new workers.
            pause_control.request_stop()
            with LOCK:  # An in-flight manual write finishes first.
                self.worker_leases=pause_control.hold_worker_leases(worker_timeout)
        except Exception as exc:
            # Keep serving rather than strand a worker that may still be writing.
            print('Quit did not complete; the server keeps running:',exc.__class__.__name__,exc,file=sys.stderr,flush=True)
            with self._quit_mutex:self._quitting=False
            return False
        self.shutdown()
        return True

    def server_bind(self):
        if os.name == 'nt':
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-browser', action='store_true')
    options = parser.parse_args(argv)
    with db():
        pass
    import library_lock, pause_control, supervisor
    pause_control.begin_run()
    if os.environ.get('COMICS_META_SHELL_TOKEN'):pause_control.shell_pause(False)
    try:
        library_lock.claim_configured('dashboard')
    except library_lock.LibraryBusy as exc:
        print(str(exc), file=sys.stderr, flush=True)
        return library_lock.EXIT_LIBRARY_BUSY
    server = LocalServer(('127.0.0.1', options.port), Handler)
    supervisor_stop = server.supervisor_stop = threading.Event() if server.setup_required else supervisor.start(BASE)
    address = f'http://127.0.0.1:{options.port}'
    print(f'Comic metadata pilot: {address}\nKeep this window open. Ctrl+C stops the app.')
    if not options.no_browser:
        webbrowser.open(address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        supervisor_stop.set()
        server.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
