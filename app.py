"""Local comic metadata pilot. Python standard library only."""
import secrets
from contextlib import contextmanager
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
import qa_runtime
qa_runtime.install()
import image_safety  # Disable the external EPS decoder before any cover can be read.
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
            -- ComicVine name search (2026-11-18): every ComicVine request of the last hour by resource ("search",
            -- "issues", "issue", "volume") and origin ("app": reserve_request, "name_search": comicvine_search),
            -- because ComicVine counts 200 requests per resource per hour. Pruned to one hour by both reservations.
            CREATE TABLE IF NOT EXISTS comicvine_requests(timestamp REAL NOT NULL, resource TEXT NOT NULL, origin TEXT NOT NULL);
            -- VerseDB (2026-11-18): its API requests of the last hour (versedb.reserve).
            CREATE TABLE IF NOT EXISTS versedb_requests(timestamp REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS catalog_migrations(name TEXT PRIMARY KEY);
            -- Nested ComicInfo (Sergei 2026-11-18, option c): comics with no ComicInfo as last read, to be read once
            -- more by the folder scan even though unchanged (queue_nested_recheck).
            CREATE TABLE IF NOT EXISTS nested_recheck(id INTEGER PRIMARY KEY);
        ''')
        refresh_fractional_numbers(con)
        queue_nested_recheck(con)
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


def queue_nested_recheck(con):
    """Once per catalog: queue every CBZ row that read as having no ComicInfo for one more read.

    Sergei 2026-11-18 (option c): a single nested ComicInfo.xml is now the comic's metadata when there is no root
    copy. The folder scan reads only changed files, so rows read before this would keep showing no metadata, and a
    plan made from them would be refused at write time ("ComicInfo changed since planning") on every pass. Only the
    queue is filled here (SQL, no file access); the folder scan does the reads as it reaches each folder
    (nested_recheck). Rows read after this point are read with nested ComicInfo already, so they are not queued.
    An absent row with no metadata comes back as 'missing', so it is queued too."""
    name = 'nested-comicinfo-recheck-v067'
    if con.execute('SELECT 1 FROM catalog_migrations WHERE name=?', (name,)).fetchone():
        return
    con.execute('BEGIN IMMEDIATE')
    try:
        if not con.execute('SELECT 1 FROM catalog_migrations WHERE name=?', (name,)).fetchone():
            con.execute("INSERT OR IGNORE INTO nested_recheck(id) SELECT id FROM comics WHERE path LIKE '%.cbz' AND "
                        "(status='missing' OR (status='absent' AND COALESCE(metadata,'{}') IN ('{}','')))")
            con.execute('INSERT INTO catalog_migrations(name) VALUES(?)', (name,))
        con.commit()
    except BaseException:
        con.rollback()
        raise


def parse_name(path):
    from filename_identity import parse_name as parse
    return parse(path)


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


def nested_comicinfo(name):
    """True for a ComicInfo.xml entry inside a folder of the archive (not the root copy)."""
    parts = name.replace('\\', '/').split('/')
    return len(parts) > 1 and parts[-1].lower() == 'comicinfo.xml'


def _comicinfo_xml(archive, name):
    if archive.getinfo(name).file_size > 2_000_000:
        raise ValueError('Metadata exceeds the 2 MB limit.')
    xml = metadata_xml(archive.read(name))
    if xml.tag != 'ComicInfo':
        raise ValueError('Unexpected metadata root.')
    return xml


def comicinfo_entry(archive):
    """(entry name, parsed ComicInfo) the app reads from an open ZIP and starts a write from, or (None, None).

    The root ComicInfo.xml when there is one: several root copies, or one that cannot be read, raise as before.
    Nested ComicInfo, Sergei 2026-11-18 (option c): with no root copy, exactly one ComicInfo.xml inside a folder
    (for example a Comixology scrape kept beside the pages) is the comic's existing metadata, so the root copy a
    write adds starts from it, and that write removes the nested copy (option d), so the archive keeps one ComicInfo
    holding all of it. A bare "None" in it (some scrapers write it for a missing Number) is blank and left out
    (Sergei 2026-11-18). The merge's other left-out rules apply too (nested_left_out; Sergei's tightening ruling of
    2026-11-18, applied to nested-only copies in 0.6.8, code review v0.6.7 q2): no nested Year, Month or Day (store
    dates; read as the comic's, they made fill-empty skip the cover date), no PageCount, no letter-case twin, no
    Volume that is a year. They are not read and not carried into the root copy; the write that removes the nested
    copy first saves it whole (removed_nested_copy). Several nested copies, or a single one that cannot be read, are
    ignored and kept, as they were before: the comic reads as having no ComicInfo."""
    names = archive.namelist()
    root = [n for n in names if n.lower() == 'comicinfo.xml']
    if len(root) > 1:
        raise ValueError('Multiple ComicInfo.xml entries; review before writing.')
    if root:
        return root[0], _comicinfo_xml(archive, root[0])
    nested = [n for n in names if nested_comicinfo(n)]
    if len(nested) != 1:
        return None, None
    try:
        xml = _comicinfo_xml(archive, nested[0])
    except Exception:
        return None, None  # Unreadable, oversized or not ComicInfo: ignored, as before.
    for element, _ in nested_only_left_out(xml):
        xml.remove(element)
    return nested[0], xml


def nested_only_left_out(nested):
    """[(element, why)]: a nested-only copy's elements that are not the comic's metadata. A bare "None" (blank), and
    what the merge never copies (nested_left_out), judged against an empty root. Listed before any is removed."""
    empty = ET.Element('ComicInfo')
    left = []
    for element in nested:
        if not comicinfo_filled(element):
            continue
        why = 'a nested "None" is blank' if not nested_donor(element) else nested_left_out(element.tag, empty, nested)
        if why:
            left.append((element, why))
    return left


def _describe(elements):
    """One value for a record: the text, texts joined by ' | ' for a repeated tag, or a short note for structure."""
    if all(not len(e) for e in elements):
        return ' | '.join((e.text or '').strip() for e in elements)
    return '<%s: %d element(s), %d child element(s)>' % (elements[0].tag, len(elements), sum(len(e) for e in elements))


def merge_left_out(root, nested, merged):
    """[[tag, nested value, why, root value kept]]: each value of a merged nested copy the root copy did not take
    (code review v0.6.8 R2). root is the root copy before the merge, merged the tags it filled. Why is the merge's own
    rule (nested_left_out) or 'root wins'; a value the root already says the same way is not listed."""
    left = []
    for tag in dict.fromkeys(e.tag for e in nested):
        donors = [e for e in nested if e.tag == tag and nested_donor(e)]
        if tag in merged or not donors:
            continue
        current = [e for e in root if e.tag == tag and comicinfo_filled(e)]
        if current and [_element_key(e) for e in donors] == [_element_key(e) for e in current]:
            continue
        left.append([tag, _describe(donors), nested_left_out(tag, root, nested) or 'root wins',
                     _describe(current) if current else ''])
    return left


def removed_nested_copy(path, name, raw, backup, root=None, merged=()):
    """Before the rename, so before any caller can delete the backup: the nested copy a write removes, whole, and each
    value of it the root copy did not take, appended to data/removed-nested-copies.jsonl and flushed to disk. So no
    nested value is ever only in a backup: not after a merge the tool stopped or that was interrupted, nor once the
    worker deletes a verified backup.

    A nested-only copy (q2): root is None; left_out lists what nested_only_left_out leaves out. A merge (code review
    v0.6.8 R2): root is the root copy before the merge and merged the tags it filled; left_out lists each nested value
    not taken, with why and the root value kept (merge_left_out). The merge tool keeps its own record in its --out."""
    try:
        nested = metadata_xml(raw)
        if root is None:
            left = [[e.tag, _describe([e]), why] for e, why in nested_only_left_out(nested)]
        else:
            left = merge_left_out(root, nested, merged)
    except Exception:
        left = None  # Unreadable here (it was read for the write): the whole copy below still says everything.
    import base64
    line = json.dumps({'time': time.time(), 'kind': 'nested-only' if root is None else 'merge', 'archive': str(path),
                       'entry': name, 'left_out': left, 'backup': str(backup),
                       'xml_base64': base64.b64encode(raw).decode('ascii')}, ensure_ascii=True)
    target = DATA / 'removed-nested-copies.jsonl'
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, 'ab') as handle:
        # A line a power cut tore (cut short or zero-filled) never swallows this one: it starts on a line of its own.
        torn = handle.tell() > 0 and _last_byte(target) != b'\n'
        handle.write((('\n' if torn else '') + line + '\n').encode('ascii'))
        handle.flush()
        os.fsync(handle.fileno())


def _last_byte(path):
    with open(path, 'rb') as handle:
        handle.seek(-1, os.SEEK_END)
        return handle.read(1)


def comicinfo_filled(element):
    """An element that says something: text, child elements (Pages) or attributes."""
    return bool((element.text or '').strip()) or len(element) > 0 or bool(element.attrib)


def nested_donor(element):
    """A nested element the merge may copy: it says something, and is not the bare text "None" some scrapers write
    for a missing value (Sergei 2026-11-18: a nested "None" counts as blank)."""
    if not len(element) and not element.attrib and (element.text or '').strip() == 'None':
        return False
    return comicinfo_filled(element)


# The ComicInfo schema's element names (ComicInfo 2.0 and 2.1).
COMICINFO_TAGS = frozenset((
    'Title Series Number Count Volume AlternateSeries AlternateNumber AlternateCount Summary Notes Year Month Day '
    'Writer Penciller Inker Colorist Letterer CoverArtist Editor Translator Publisher Imprint Genre Tags Web PageCount '
    'LanguageISO Format BlackAndWhite Manga Characters Teams Locations ScanInformation StoryArc StoryArcNumber '
    'SeriesGroup AgeRating Pages CommunityRating MainCharacterOrTeam Review GTIN').split())


def nested_left_out(tag, root, nested):
    """Why the nested merge never copies this nested tag, or '' (Sergei 2026-11-18, after Futaba's sample).

    - Year, Month, Day: nested dates are store or release dates, not cover dates; the app fills cover dates.
    - PageCount: the nested count often disagrees with the archive, and the app never writes PageCount.
    - A tag that differs from another tag in the root or the nested copy only in letter case (`writer` beside
      `Writer`): readers match exact names, so it would only duplicate. The schema's own spelling is never left out
      for the sake of a non-schema twin.
    - Volume when it is a four-digit year: the app's Volume is the volume number."""
    if tag in ('Year', 'Month', 'Day'):
        return 'nested date never copied'
    if tag == 'PageCount':
        return 'PageCount never copied'
    if tag == 'Volume' and any(re.fullmatch(r'\s*\d{4}\s*', e.text or '') for e in nested if e.tag == tag and not len(e)):
        return 'Volume is a year'
    if isinstance(tag, str):
        twins = {e.tag for e in (*root, *nested) if isinstance(e.tag, str) and e.tag != tag and e.tag.lower() == tag.lower()}
        if twins and not (tag in COMICINFO_TAGS and not twins & COMICINFO_TAGS):
            return 'same tag in another letter case'
    return ''


def merge_comicinfo(root, nested):
    """Fill-empty from a nested ComicInfo into the root copy, element by element (Sergei 2026-11-18, option d).

    Every tag the nested copy fills and the root copy does not is copied, all of its elements in order (a repeated
    tag, Pages and other structured elements included); where both fill a tag, the root copy wins. A nested "None"
    is blank. A blank root element of that tag is replaced. Never copied (nested_left_out): Year, Month, Day,
    PageCount, a tag that is another tag's letter-case twin, and a Volume that is a year. Changes `root` in place and
    returns the tags filled, in the nested copy's order."""
    import copy
    filled = []
    for tag in dict.fromkeys(child.tag for child in nested):
        donors = [e for e in nested if e.tag == tag and nested_donor(e)]
        current = [e for e in root if e.tag == tag]
        if not donors or any(comicinfo_filled(e) for e in current) or nested_left_out(tag, root, nested):
            continue
        for element in current:
            root.remove(element)
        for element in donors:
            element = copy.deepcopy(element)
            element.tail = None
            root.append(element)
        filled.append(tag)
    return filled


def _element_key(element):
    return (element.tag, sorted(element.attrib.items()), element.text or '', [_element_key(c) for c in element])


def read_metadata(path):
    path = filesystem_path(path)
    if path.suffix.lower() != '.cbz':
        return {}, 'unsupported', 'CBR/CB7 are inventoried only in this pilot.'
    with path.open('rb') as handle:signature=handle.read(8)
    if signature.startswith((b'7z\xbc\xaf\x27\x1c',b'Rar!')):
        return {}, 'unsupported', 'Readable RAR/7-Zip container with a .cbz filename; automatic ZIP metadata writes are unavailable.'
    with zipfile.ZipFile(path) as archive:
        name, xml = comicinfo_entry(archive)
        if name is None:
            return {}, 'missing', ''
        return {n.tag: n.text or '' for n in xml if n.tag != 'Pages'}, 'embedded', ''


def reconcile_missing(con, candidates, allowed_folders=None):
    """Retire only unchanged rows whose readable parent and file stat prove absence."""
    by_folder={};uncertain=0;proven=[]
    for candidate in candidates:
        folder=Path(candidate['path']).parent
        key=os.path.normcase(os.path.normpath(str(folder)))
        if allowed_folders is not None and key not in allowed_folders:continue
        by_folder.setdefault(key,(folder,[]))[1].append(candidate)
    for folder,rows in by_folder.values():
        try:
            with os.scandir(filesystem_path(folder)) as entries:
                present={os.path.normcase(entry.name) for entry in entries}
        except OSError:
            uncertain+=len(rows);continue
        for row in rows:
            candidate=Path(row['path'])
            if os.path.normcase(candidate.name) in present:continue
            try:filesystem_path(candidate).stat()
            except FileNotFoundError:
                proven.append(row)
            except OSError:uncertain+=1
    # Do not hold a SQLite write lock while inspecting unrelated folders/shares.
    for row in proven:
        result=con.execute("UPDATE comics SET status='absent' WHERE id=? AND path IS ? AND status IS ? AND size IS ? AND mtime IS ? AND seen IS ?",
                           (row['id'],row['path'],row['status'],row['size'],row['mtime'],row['seen']))
        if not result.rowcount:uncertain+=1
    return uncertain


def nested_recheck(con, comic_id, path):
    """read_metadata's answer for an unchanged row queued by queue_nested_recheck, when it now finds a nested-only
    ComicInfo; else None, and the row stays as the scan found it.

    The row leaves the queue once its archive was read, whatever it held. An archive that cannot be read now stays
    queued for the next scan and keeps its row: a passing read failure never turns a comic into an error."""
    if not con.execute('SELECT 1 FROM nested_recheck WHERE id=?', (comic_id,)).fetchone():
        return None
    try:
        found = read_metadata(path)
    except Exception:
        return None
    con.execute('DELETE FROM nested_recheck WHERE id=?', (comic_id,))
    return found if found[1] == 'embedded' else None


def scan(roots, recursive=True):
    try:
        for root_text in roots:
            root = Path(root_text).resolve()
            if not root.is_dir():
                raise ValueError(f'Folder is unavailable: {root}')
            generation = time.time_ns()
            with db() as con:
                con.execute('INSERT OR IGNORE INTO roots VALUES (?)', (str(root),))
                traversed = {}
                for folder, dirs, files in os.walk(filesystem_path(root), onerror=lambda e: (_ for _ in ()).throw(e)):
                    dirs[:] = [d for d in dirs if d not in {'.yacreaderlibrary', '.comic-metadata-backups'} and not d.startswith('.comic-metadata-convert-')]
                    if not recursive:dirs[:] = []
                    native_folder = folder
                    if native_folder.startswith('\\\\?\\UNC\\'):
                        native_folder = '\\\\' + native_folder[8:]
                    elif native_folder.startswith('\\\\?\\'):
                        native_folder = native_folder[4:]
                    traversed[os.path.normcase(os.path.normpath(native_folder))] = Path(native_folder)
                    for name in files:
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
                                found = nested_recheck(con, old['id'], path) if restored_status == 'missing' else None
                                if found is None:
                                    con.execute('UPDATE comics SET seen=?,status=? WHERE id=?', (generation, restored_status, old['id']))
                                    continue
                            else:
                                found = None
                            metadata, status, error = found or read_metadata(path)
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
                # A row may have been indexed by a different scan root. Select by
                # indexed literal path range, then restrict to folders actually
                # traversed. Excluded, missing and inaccessible folders are not proof.
                prefix=str(root).rstrip('\\/')+os.sep
                upper=prefix[:-1]+chr(ord(prefix[-1])+1)
                candidates=con.execute("SELECT id,path,seen,size,mtime,status FROM comics WHERE path>=? AND path<? AND (seen IS NULL OR seen<>?) AND status<>'absent'",(prefix,upper,generation)).fetchall()
                reconcile_missing(con,candidates,traversed)
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


def comicvine_resource(resource):
    """The resource ComicVine counts a request against: "issue/4000-1" -> "issue", "search" -> "search"."""
    return str(resource).split('/', 1)[0]


# ComicVine allows 200 requests per resource per hour. Code review v0.6.5 S2: both paths together stay under it, so
# ComicVine never refuses an ID-path request (a refusal sets the shared cooldown that stops every lookup).
COMICVINE_RESOURCE_LIMIT = 198


def reserve_request(now=None, resource=None):
    """Persist a conservative global allowance, including failed attempts.

    resource (ComicVine name search, 2026-11-18): the request is also entered in the per-resource ledger
    `comicvine_requests`, so the name search can see this path's use of each resource. This path's own allowance
    (180 an hour, 20 s apart) is unchanged and never counts name-search requests. Code review v0.6.5 S2: it does
    count them toward ComicVine's per-resource limit, and refuses one of its own requests (a local wait, no shared
    cooldown) before both paths together reach COMICVINE_RESOURCE_LIMIT on that resource. The name search stops
    earlier (comicvine_search: 190 in all, its own shares, and stepping aside after manual searches), so this path
    keeps the last of the headroom."""
    now = time.time() if now is None else now
    with db() as con:
        con.execute('BEGIN IMMEDIATE')
        state = con.execute('SELECT * FROM api_state WHERE id=1').fetchone()
        if state['blocked_until'] > now:
            minutes = max(1, int((state['blocked_until'] - now + 59) // 60))
            raise ProviderDeferred(f'Metadata lookup is cooling down; retry in about {minutes} minutes.','comicvine',state['blocked_until'],'cooldown')
        con.execute('DELETE FROM api_requests WHERE timestamp<=?', (now - 3600,))
        con.execute('DELETE FROM comicvine_requests WHERE timestamp<=?', (now - 3600,))
        count = con.execute('SELECT COUNT(*) FROM api_requests').fetchone()[0]
        if count >= 180:
            raise ProviderDeferred('Local hourly request budget reached. Pause and retry later; cached results remain available.','comicvine',con.execute('SELECT MIN(timestamp) FROM api_requests').fetchone()[0]+3600,'limit')
        if resource:
            family = comicvine_resource(resource)
            every, first = con.execute('SELECT COUNT(*),MIN(timestamp) FROM comicvine_requests WHERE resource=?', (family,)).fetchone()
            if every >= COMICVINE_RESOURCE_LIMIT:
                minutes = max(1, int((first + 3600 - now + 59) // 60))
                raise ProviderDeferred(f'ComicVine {family} requests reached their hourly limit; retry in about {minutes} minutes. Cached results remain available.',
                                       'comicvine', first + 3600, 'limit')
        delay = max(0, 20 - (now - state['last_attempt']))
        if delay:
            return delay
        con.execute('INSERT INTO api_requests VALUES(?)', (now,))
        if resource:
            con.execute('INSERT INTO comicvine_requests VALUES(?,?,?)', (now, comicvine_resource(resource), 'app'))
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
        if qa_runtime.policy() is not None:
            raise ProviderDeferred('Private QA uses cached provider answers only.','comicvine',0,'no_key')
        # The cache needs no key: a missing key must not hide a cached answer,
        # such as an identity conflict (F16).
        key = api_key()
        if not key:
            raise ProviderDeferred('Set COMICVINE_API_KEY to enable online lookup.','comicvine',0,'no_key')
        # Shared SQLite reservations survive restarts and coordinate app processes.
        delay = reserve_request(resource=resource)
        while delay:
            time.sleep(min(delay, 20))
            delay = reserve_request(resource=resource)
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


def manual_issue_fields(present, fields, issue):
    """An explicit issue choice replaces its link; keep other populated fields."""
    import automatic
    planned, _, _ = automatic.external_plan(present, fields, {}, False)
    selected = fields.get('Web')
    if selected and issue.get('id'):
        # Keep unrelated reference URLs while removing all previous ComicVine issue links.
        other = re.sub(r'https?://(?:www\.)?(?:comicvine\.gamespot\.com|comicvine\.com)/[^\s,;]*4000-\d+[^\s,;]*', '', present.get('Web', ''), flags=re.I)
        other = other.strip(' ,;\n\r\t')
        planned['Web'] = (other + '\n' if other else '') + selected
    return planned


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
    # Futaba's source sample 2026-11-18 (F3): ComicVine names can end in a space ("Blade: First Bite Infinity Comic ").
    return {k: str(v).strip() for k, v in fields.items() if v and str(v).strip()}


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



_write_guard_state=threading.local()


def write_lock_path(path):
    """The lock file comic_write_guard holds for this archive."""
    import library_lock
    canonical=library_lock.identity(filesystem_path(path))
    return DATA/'write-locks'/(hashlib.sha256(canonical.encode('utf-8')).hexdigest()+'.lock')


@contextmanager
def comic_write_guard(path):
    """One OS-held metadata writer per canonical archive, including same-state workers."""
    import file_lock, library_lock
    canonical=library_lock.identity(filesystem_path(path))
    folder=DATA/'write-locks'
    for entry in (folder,*folder.parents):
        try:info=entry.lstat()
        except FileNotFoundError:continue
        if entry.is_symlink() or getattr(info,'st_file_attributes',0)&0x400:
            raise ArchiveChanged('Metadata write lock path is unavailable; nothing written.')
    folder.mkdir(parents=True,exist_ok=True)
    lock_path=write_lock_path(path)
    if lock_path.is_symlink() or (lock_path.exists() and getattr(lock_path.lstat(),'st_file_attributes',0)&0x400):
        raise ArchiveChanged('Metadata write lock path is unavailable; nothing written.')
    fd=file_lock.open_lock(lock_path)
    acquired=False
    try:
        acquired=file_lock.try_lock(fd)
        if not acquired:raise ArchiveChanged('Another metadata write is in progress. Review this comic again.')
        held=getattr(_write_guard_state,'held',set())
        _write_guard_state.held=held
        held.add(canonical)
        try:yield
        finally:held.discard(canonical)
    finally:
        try:
            if acquired:file_lock.unlock(fd)
        finally:os.close(fd)


def write_guard_held(path):
    """True when this thread holds comic_write_guard for this archive."""
    import library_lock
    return library_lock.identity(filesystem_path(path)) in getattr(_write_guard_state,'held',set())


def _flush_copy(path):
    """storage.flush_file for a copy that may carry its original's read-only bit (shutil.copy2 copies it): a flush
    needs a handle with write access, so the bit is lifted for the flush only and put back."""
    import stat as stat_module, storage
    mode = os.stat(path).st_mode
    if mode & stat_module.S_IWRITE:
        storage.flush_file(path)
        return
    os.chmod(path, mode | stat_module.S_IWRITE)
    try:
        storage.flush_file(path)
    finally:
        os.chmod(path, mode)


def pending_write_path(path):
    """The record of a write in progress on this archive (code review v0.6.7 Q2), named as its write lock.

    _write_metadata_guarded saves it durably before the backup copy, adds the archive's next signature ('after') just
    before the rename, and removes it once the history is recorded. A process stopped in between (Quit's Closing cap,
    a crash, a power loss) leaves it for recover_interrupted_write."""
    return DATA/'pending-writes'/(write_lock_path(path).stem+'.json')


def _recovery_note(text):
    print('Interrupted write recovery: '+text,file=sys.stderr,flush=True)


def recover_interrupted_writes():
    """Finish or undo every write a stopped process left half-done (code review v0.6.7 Q2). Run at start, with the
    library claimed and before any worker. Never raises: a record that cannot be handled now is kept for the next
    start (or for its comic's next write), and logged."""
    folder=DATA/'pending-writes'
    try:records=sorted(folder.glob('*.json')) if folder.is_dir() else []
    except OSError as exc:
        _recovery_note('records could not be listed ('+type(exc).__name__+' '+str(exc)[:200]+').')
        return []
    outcomes=[]
    for record in records:
        try:outcomes.append(recover_interrupted_write(record))
        except Exception as exc:
            _recovery_note(record.name+' kept for the next start ('+type(exc).__name__+' '+str(exc)[:200]+').')
    return outcomes


def recover_interrupted_write(record_path, record_backup=True):
    """Finish or undo the write one pending record describes, under that comic's write guard (taken here unless this
    thread holds it). Returns {'path', 'outcome', 'backup', 'backup_removed'}; outcome is:

    - 'recorded': the rename happened and the comic reads as the write planned: its history and ledger row (writer and
      source as planned, origin 'recovered') and the catalog row are recorded now. The backup is kept and listed in
      Kept backups as "Saved; backup could not be deleted": the original's hash is not known here.
    - 'already recorded': the history was recorded before the stop; only the record was left. The backup, if any, is
      kept and listed the same way.
    - 'not verified': renamed, but the comic does not read as planned: no history; the backup is kept as "Save not
      verified".
    - 'undone': never renamed; the comic is exactly what the write started from. Its temporary archive is deleted
      (the comic's next write would refuse it) and its backup is deleted once its SHA-256 equals the comic's, else
      kept as "Not saved; file was not changed".
    - 'changed': the comic is neither; another program changed or removed it since. Nothing is touched.

    record_backup=False leaves Kept backups' reasons alone (the merge tool deletes the backup itself after its own
    checks). Raises (record kept) when the comic's write guard or the library claim cannot be had, or the record
    cannot be read."""
    import library_lock, storage
    record_path=Path(record_path)
    try:
        raw=json.loads(storage.read_text(record_path))
        if (not isinstance(raw,dict) or raw.get('schema')!=1 or not isinstance(raw.get('path'),str)
                or pending_write_path(raw['path']).name!=record_path.name
                or not isinstance(raw.get('before'),list) or not isinstance(raw.get('backup'),str)):
            raise ValueError('not a pending-write record of this app')
    except FileNotFoundError:
        return {'path':None,'outcome':'gone','backup':None,'backup_removed':False}
    except (OSError,ValueError) as exc:
        # Never a block for good: the record is set aside as evidence and the comic's writes go on (a temporary
        # archive beside it still refuses them, as before 0.6.8, until Folder help clears it).
        os.replace(record_path,record_path.with_name(record_path.name+'.unreadable'))
        _recovery_note(record_path.name+' could not be read ('+type(exc).__name__+' '+str(exc)[:200]+'); kept as '
                       +record_path.name+'.unreadable.')
        return {'path':None,'outcome':'unreadable','backup':None,'backup_removed':False}
    if not write_guard_held(raw['path']):
        with comic_write_guard(raw['path']):
            return recover_interrupted_write(record_path,record_backup)
    library_lock.require(raw['path'])  # Raises, keeping the record, while another copy owns the library.
    path=filesystem_path(raw['path'])
    backup=filesystem_path(raw['backup'])
    temporary=path.with_name(path.name+'.metadata-tmp')
    try:
        current=path.stat()
        signature=[current.st_size,current.st_mtime_ns]
    except FileNotFoundError:
        signature=None
    removed=False
    if raw.get('after') and signature==raw['after']:
        outcome=_record_interrupted_write(raw,path,signature)
        reason='save_not_verified' if outcome=='not verified' else 'delete_refused'
    elif signature==raw.get('before'):
        outcome,reason='undone','not_saved'
        temporary.unlink(missing_ok=True)  # This write's own, unfinished: the comic is still what it started from.
        if backup.exists():
            try:
                with path.open('rb') as handle:
                    remove_verified_backup(raw['path'],backup,hashlib.file_digest(handle,'sha256').hexdigest())
                removed=True
            except Exception:
                pass  # A partial or differing copy is kept.
    else:
        outcome,reason='changed',None
    if record_backup and reason and not removed and backup.exists():
        import kept_backups
        kept_backups.record(raw['path'],backup,reason)
    record_path.unlink(missing_ok=True)
    _recovery_note(Path(raw['path']).name+': '+outcome+('; its backup was deleted' if removed else '; its backup is kept' if backup.exists() else '')+'.')
    return {'path':raw['path'],'outcome':outcome,'backup':raw['backup'],'backup_removed':removed}


def _record_interrupted_write(raw, path, signature):
    """The history, ledger and catalog rows a write renamed before its process stopped did not record."""
    metadata,_,_=read_metadata(path)
    if any(metadata.get(key,'')!=value for key,value in (raw.get('expected') or {}).items()):
        return 'not verified'
    with db() as con:
        if con.execute('SELECT 1 FROM history WHERE backup=?',(raw['backup'],)).fetchone():
            return 'already recorded'
        con.execute("UPDATE comics SET size=?,mtime=?,metadata=?,status='tagged',error='' WHERE id=?",
                    (signature[0],signature[1],json.dumps(metadata),raw['id']))
        history_id=con.execute('INSERT INTO history(path,backup,source,timestamp) VALUES(?,?,?,?)',
                               (raw['history_path'],raw['backup'],raw['source'],raw.get('time') or time.time())).lastrowid
        con.execute('INSERT INTO write_ledger VALUES(?,?,?,?,?,?,?,?,?,?)',
                    (history_id,raw['path'],raw['source'],raw['writer'],json.dumps(raw.get('written') or {},ensure_ascii=False),
                     raw['before'][0],raw['before'][1],signature[0],signature[1],'recovered'))
    return 'recorded'


def write_metadata(row, fields, *, append_notes=False, overwrite_fields=(), remove_verified_backups=False,
                   expected=None, history_source=None, attempt=None, writer='manual',
                   expected_snapshot=None, verify_readback=False, guard_held=False, merge_nested=None):
    import library_lock
    try:scanned_root=row['root']
    except (KeyError,IndexError):scanned_root=None
    library_lock.require(row['path'],scanned_root)
    options=dict(append_notes=append_notes,overwrite_fields=overwrite_fields,
                 remove_verified_backups=remove_verified_backups,expected=expected,
                 history_source=history_source,attempt=attempt,writer=writer,
                 expected_snapshot=expected_snapshot,verify_readback=verify_readback,
                 merge_nested=merge_nested)
    if guard_held:
        if library_lock.identity(filesystem_path(row['path'])) not in getattr(_write_guard_state,'held',set()):
            raise ArchiveChanged('Metadata write guard was not held; nothing written.')
        return _write_metadata_guarded(row,fields,**options)
    with comic_write_guard(row['path']):
        return _write_metadata_guarded(row,fields,**options)


def _write_metadata_guarded(row, fields, *, append_notes=False, overwrite_fields=(), remove_verified_backups=False,
                   expected=None, history_source=None, attempt=None, writer='manual', expected_snapshot=None, verify_readback=False,
                   merge_nested=None):
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
    merge_nested (Sergei 2026-11-18, option d): {'name', 'crc', 'size', 'tags'} for an archive with a root and
    exactly one nested ComicInfo. The nested entry must still be that one (name, CRC, size); merge_comicinfo fills
    the root copy from it (fill-empty, the root wins, a nested "None" is blank, never a date, PageCount, letter-case
    twin or year-like Volume), refuses to fill a tag outside 'tags', and the write removes it. A nested-only comic's nested copy
    (the one the new root copy started from) is removed the same way without being asked. The entry check then
    allows exactly that one removal.
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
    if pending_write_path(row['path']).exists():
        # An earlier write of this comic was stopped part-way (code review v0.6.7 Q2): finish or undo it first, under
        # this write's guard. A finished one changed the comic, so the signature check below refuses this plan.
        recover_interrupted_write(pending_write_path(row['path']))
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
        if expected_snapshot is not None and present!=expected_snapshot:
            raise ArchiveChanged('ComicInfo changed since this preview; nothing written.')
        if expected:
            # Whitespace-only counts as empty, as it does for planning and the write below.
            stale = sorted(key for key, value in expected.items() if (present.get(key) or '').strip() != (value or '').strip())
            if stale:
                raise ArchiveChanged('ComicInfo changed since planning (' + ', '.join(stale) + '); nothing written.')
        # The copy read_metadata read: the root one, else a single nested one (Sergei 2026-11-18).
        source_name, xml = comicinfo_entry(source)
        if xml is None:
            xml = ET.Element('ComicInfo')
        expected_fields = {}
        written = {}  # Fields this call sets (not Notes, not values it leaves in place).
        # Nested ComicInfo, Sergei 2026-11-18 (option d): the one nested entry this write removes, as
        # (name, CRC, size). The new root copy carries all of it, so the archive keeps one ComicInfo.
        drop, merged, nested_raw, merge_root = None, [], None, None
        if merge_nested is not None:
            nested = [i for i in infos if nested_comicinfo(i.filename)]
            if (source_name is None or nested_comicinfo(source_name) or len(nested) != 1
                    or nested[0].filename != merge_nested['name']
                    or (nested[0].CRC, nested[0].file_size) != (merge_nested['crc'], merge_nested['size'])):
                raise ArchiveChanged('Nested ComicInfo changed since planning; nothing written.')
            import copy
            merge_root = copy.deepcopy(xml)  # The root copy before the merge, for the record of what it did not take.
            nested_raw = source.read(nested[0].filename)
            merged = merge_comicinfo(xml, _comicinfo_xml(source, nested[0].filename))
            unplanned = sorted(set(merged) - set(merge_nested['tags']))
            if unplanned:
                raise ArchiveChanged('The merge would fill fields not planned (' + ', '.join(unplanned) + '); nothing written.')
            drop = (nested[0].filename, nested[0].CRC, nested[0].file_size)
            for tag in merged:
                elements = [e for e in xml if e.tag == tag]
                if tag not in ('Notes', 'Pages') and len(elements) == 1 and not len(elements[0]):
                    written[tag] = elements[0].text or ''
        elif source_name is not None and nested_comicinfo(source_name):
            # A nested-only comic: the new root copy started from what of it is the comic's metadata (q2), so it goes.
            info = source.getinfo(source_name)
            drop = (info.filename, info.CRC, info.file_size)
            nested_raw = source.read(source_name)
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
    import storage
    source_text = str(history_source)[:200] if history_source else fields.get('Web', '')
    # Code review v0.6.7 Q2: what this write is about to do, on the disk before the backup copy, so that a process
    # stopped part-way (Quit's 30 s Closing cap, a crash, a power loss) leaves no temporary archive that blocks later
    # writes and no written comic without its history: recover_interrupted_write finishes or undoes it at the next
    # start (or at this comic's next write). 'after' is added once the temporary archive is complete and verified.
    pending = pending_write_path(row['path'])
    journal = {'schema': 1, 'path': str(row['path']), 'id': row['id'], 'history_path': str(path), 'backup': str(backup),
               'before': [stat.st_size, stat.st_mtime_ns], 'source': source_text, 'writer': writer,
               'written': written, 'expected': expected_fields}
    pending.parent.mkdir(parents=True, exist_ok=True)
    storage.save(pending, journal, ensure_ascii=True)
    replaced = False
    try:
        shutil.copy2(path, backup)
        if attempt is not None:
            attempt['backup'] = str(backup)
        # Code review v0.6.8 R1: the backup's bytes on the disk before the rename below makes it the only copy of
        # the original (every value this write replaces or drops). Without it a power cut could keep a full-size,
        # zero-filled backup beside the correctly written comic.
        _flush_copy(backup)
        try:
            with zipfile.ZipFile(path) as source, zipfile.ZipFile(temporary, 'w') as target:
                target.comment = source.comment
                for info in source.infolist():
                    if info.filename.lower() == 'comicinfo.xml' or (drop and info.filename == drop[0]):
                        continue
                    with source.open(info) as src, target.open(info, 'w') as dst:
                        shutil.copyfileobj(src, dst, length=1024 * 1024)
                target.writestr('ComicInfo.xml', xml_bytes, compress_type=zipfile.ZIP_DEFLATED)
            with zipfile.ZipFile(temporary) as check, zipfile.ZipFile(backup) as original:
                if check.testzip() is not None:
                    raise ValueError('Archive validation failed.')
                # Every other entry is unchanged, in order. The one exception is the nested ComicInfo this write
                # merged (drop): the original held exactly that entry, unchanged, and the result does not.
                entries = [(i.filename, i.CRC, i.file_size) for i in original.infolist() if i.filename.lower() != 'comicinfo.xml']
                before = [entry for entry in entries if not (drop and entry[0] == drop[0])]
                after = [(i.filename, i.CRC, i.file_size) for i in check.infolist() if i.filename.lower() != 'comicinfo.xml']
                if before != after or (drop and len(entries) - len(before) != 1) or (drop and drop not in entries):
                    raise ValueError('Archive contents changed unexpectedly.')
                readback = metadata_xml(check.read('ComicInfo.xml'))
                for key,value in expected_fields.items():
                    if readback.findtext(key,default='') != value:
                        raise ValueError('Temporary archive metadata verification failed for '+key)
                for tag in merged:
                    if [_element_key(e) for e in readback if e.tag == tag] != [_element_key(e) for e in xml if e.tag == tag]:
                        raise ValueError('Temporary archive metadata verification failed for '+tag)
            current = path.stat()
            if (current.st_size, current.st_mtime_ns) != (stat.st_size, stat.st_mtime_ns):
                raise ArchiveChanged('Comic changed while preparing metadata. Original retained.')
            if nested_raw is not None:
                # q2 (a nested-only copy) and code review v0.6.8 R2 (a merge): the nested entry goes with values the
                # root copy did not take. The whole copy and those values are saved before the rename, so before any
                # caller (the merge tool after its checks, the worker, Approve) can delete or keep the backup.
                removed_nested_copy(row['path'], drop[0], nested_raw, backup, root=merge_root, merged=merged)
            finished = temporary.stat()  # The rename keeps the size and modification time: the archive's next signature.
            storage.save(pending, dict(journal, after=[finished.st_size, finished.st_mtime_ns], time=time.time()),
                         ensure_ascii=True)
            # Code review v0.6.7 Q1: the new archive's bytes reach the disk before the rename, and the rename before
            # this returns (storage.replace_durably, as storage's durable save). Every caller that then deletes the
            # backup (Approve, the worker's batch, remove_verified_backups, the nested merge tool) deletes it only after.
            storage.replace_durably(temporary, path)
            replaced = True
        finally:
            temporary.unlink(missing_ok=True)
        metadata, _, _ = read_metadata(path)
        if remove_verified_backups or verify_readback:
            for key, value in expected_fields.items():
                if metadata.get(key, '') != value:
                    raise ValueError('Readback verification failed for ' + key)
        before = stat
        stat = path.stat()
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
    except Exception:
        # Nothing replaced: the comic is unchanged and the caller's failure handling (F29) owns the backup. Once the
        # rename happened the record stays, so the history a failed step did not record is recovered.
        if not replaced:
            pending.unlink(missing_ok=True)
        raise
    pending.unlink(missing_ok=True)
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
            if url.path == '/api/shell/startup':
                token = os.environ.get('COMICS_META_SHELL_TOKEN', '')
                if not token or not secrets.compare_digest(self.headers.get('X-ComicsMeta-Shell', ''), token):
                    return self.respond({'error': 'Untrusted shell'}, 403)
                return self.respond({'owned': True, 'phase': self.server.startup_phase, 'error': self.server.startup_error,
                                     'setup': {'configured': not self.server.setup_required} if self.server.startup_phase == 'ready' else None})
            if getattr(self.server,'startup_phase','ready') != 'ready':
                return self.respond({'error': 'Service starting'}, 503)
            if url.path == '/':
                return self.respond((BASE / 'static/index.html').read_bytes(), mime='text/html; charset=utf-8')
            if url.path == '/api/gcd-offline':
                if self.headers.get('Sec-Fetch-Site') not in (None,'same-origin','none'):
                    return self.respond({'error':'Untrusted origin'},403)
                import gcd_offline
                return self.respond(gcd_offline.status())
            if url.path in ('/gcd-offline.js','/gcd-offline.css'):
                return self.respond((BASE/'static'/url.path.lstrip('/')).read_bytes(),mime='text/css; charset=utf-8' if url.path.endswith('.css') else 'text/javascript; charset=utf-8')
            if url.path in ('/reverse-image.js','/lens-control.js','/shell-ui.js','/comic-recovery.js','/kept-backups.js','/folder-help.js','/update-stats.js'):
                return self.respond((BASE / 'static' / url.path.lstrip('/')).read_bytes(), mime='text/javascript; charset=utf-8')
            if url.path == '/comic-recovery.css':
                return self.respond((BASE/'static/comic-recovery.css').read_bytes(),mime='text/css; charset=utf-8')
            if url.path == '/api/recovery/evidence':
                if self.headers.get('Sec-Fetch-Site') not in (None,'same-origin','none'):
                    return self.respond({'error':'Untrusted origin'},403)
                import comic_recovery
                try:
                    if set(args)-{'comic','issue'} or len(args.get('comic',[]))!=1 or len(args.get('issue',[]))>1:
                        raise comic_recovery.RecoveryError('invalid_link','Choose a comic and an available issue.')
                    return self.respond(comic_recovery.evidence(int(args['comic'][0]),args.get('issue',[None])[0]))
                except comic_recovery.RecoveryError as exc:
                    return self.respond({'error':str(exc),'code':exc.code},400)
            if url.path == '/api/backups':
                # Kept backups (BackupLocation Amendment A2-A3): same-origin only, like recovery evidence.
                if self.headers.get('Sec-Fetch-Site') not in (None,'same-origin','none'):
                    return self.respond({'error':'Untrusted origin'},403)
                import kept_backups
                try:
                    if args:raise kept_backups.BackupError('unavailable')
                    return self.respond(kept_backups.listing())
                except Exception:
                    return self.respond({'error':'unavailable','code':'unavailable'},400)
            if url.path == '/api/shell/keys':
                token = os.environ.get('COMICS_META_SHELL_TOKEN', '')
                if not token or not secrets.compare_digest(self.headers.get('X-ComicsMeta-Shell', ''), token):
                    return self.respond({'error': 'Untrusted shell'}, 403)
                import setup_state
                try:return self.respond(setup_state.key_status())
                except setup_state.SetupError:return self.respond({'error':'save_failed'},400)
            if url.path == '/api/shell/status':
                token = os.environ.get('COMICS_META_SHELL_TOKEN', '')
                if not token or not secrets.compare_digest(self.headers.get('X-ComicsMeta-Shell', ''), token):
                    return self.respond({'error': 'Untrusted shell'}, 403)
                import pause_control, lens_verification
                verification = lens_verification.status()
                lens_action = bool(verification.get('human_verification') and verification.get('alive') and not verification.get('paused') and verification.get('phase') not in {'queued','opening','open','closing','paused'} and (verification.get('phase') != 'failed' or (verification.get('window') == 'closed' and not verification.get('verification_pending'))))
                engines = ['Google Lens'] if lens_action else []
                return self.respond({'owned': True, 'version': self.server.loaded_version,
                                     'control': pause_control.status(),
                                     'verification': bool(engines), 'verification_engines': engines,
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
            if url.path == '/api/update-stats':
                # Update statistics panel (UXSpec UpdateStats 2026-10-26): read-only counts from write history.
                import update_stats
                try:
                    return self.respond(update_stats.report(args))
                except update_stats.StatsError as exc:
                    return self.respond({'error':str(exc),'code':exc.code},400)
            if url.path == '/api/browser-verification':
                import lens_verification,yandex_verification,pause_control
                result=lens_verification.status()
                # DesktopShell spec §12.2: the page hides the Lens line from this, not from the worker's cover state.
                result['enabled']=lens_verification.lens_on()
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
                    conversion_total = con.execute("SELECT COUNT(*) FROM comics WHERE "+scope+" AND status='unsupported'",scope_args).fetchone()[0] if status=='unsupported' else None
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
                return self.respond({'rows': result_rows, 'total': total, **({'conversion_total':conversion_total} if conversion_total is not None else {})})
            if url.path == '/api/cover':
                import reverse_image
                # A malformed id is a clean 400, never Python's int() text (Futaba 0.2.3 m6).
                def number(name):
                    values = args.get(name, [])
                    return int(values[0]) if len(values) == 1 and re.fullmatch('[0-9]{1,18}', values[0]) else None
                if number('id') is None:
                    return self.respond({'error': 'Choose a comic.'}, 400)
                if 'index' in args:
                    if number('index') is None:
                        return self.respond({'error': 'Choose a suitable image among the first five archive images.'}, 400)
                    row = comic(number('id'))
                    data,mime,_ = reverse_image.cover(row['path'],number('index'))
                    return self.respond(data,mime=mime)
                # Cover in this file (FileCover 2026-10-16): by comic id only, same-origin as recovery evidence.
                if self.headers.get('Sec-Fetch-Site') not in (None,'same-origin','none'):
                    return self.respond({'error':'Untrusted origin'},403)
                if set(args)!={'id'} or len(args['id'])!=1:
                    raise ValueError('Choose a comic.')
                return self.respond(reverse_image.preview(comic(int(args['id'][0]))['path']),mime='image/jpeg')
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
        if getattr(self.server,'startup_phase','ready') != 'ready':
            return self.respond({'error': 'Service starting'}, 503)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length < 100_000:
                raise ValueError('Invalid request size.')
            body = json.loads(self.rfile.read(length))
            if self.path == '/api/conversion/recheck':
                if body != {}:raise ValueError('Invalid conversion check.')
                root=live_root()
                if not root:raise ValueError('A configured library is required.')
                with db() as con:
                    scope,params=scope_filter(root)
                    rows=con.execute("SELECT id,path,status,size,mtime,seen FROM comics WHERE "+scope+" AND status='unsupported'",params).fetchall()
                    uncertain=reconcile_missing(con,rows)
                return self.respond({'uncertain':uncertain})
            if self.path in ('/api/gcd-offline/inspect','/api/gcd-offline/build','/api/gcd-offline/cancel'):
                import gcd_offline
                try:
                    if not isinstance(body,dict):raise gcd_offline.GcdError('build_failed')
                    if self.path.endswith('/cancel'):
                        if body:raise gcd_offline.GcdError('build_failed')
                        result=gcd_offline.cancel()
                    else:
                        allowed={'zip'} if self.path.endswith('/inspect') else {'zip','force'}
                        if set(body)-allowed or 'zip' not in body:raise gcd_offline.GcdError('zip_missing')
                        result=gcd_offline.inspect_source(body['zip']) if self.path.endswith('/inspect') else gcd_offline.start(body['zip'],body.get('force',False))
                    return self.respond(result)
                except gcd_offline.GcdError as exc:
                    return self.respond({'error':exc.code,'code':exc.code,**exc.details},400)
            import pause_control
            if self.path in ('/api/recovery/preview','/api/recovery/confirm'):
                import comic_recovery
                try:
                    if not isinstance(body,dict):
                        raise comic_recovery.RecoveryError('invalid_action','Choose an available recovery option.')
                    if self.path=='/api/recovery/preview':
                        if set(body)-{'comic','action','issue'} or not {'comic','action'}<=set(body):
                            raise comic_recovery.RecoveryError('invalid_action','Choose an available recovery option.')
                        result=comic_recovery.preview(body['comic'],body['action'],body.get('issue'))
                    else:
                        if set(body)!={'token','confirm'}:
                            raise comic_recovery.RecoveryError('confirmation','Review and explicitly confirm this change.')
                        result=comic_recovery.confirm(body['token'],body['confirm'])
                    return self.respond(result)
                except comic_recovery.RecoveryError as exc:
                    return self.respond({'error':str(exc),'code':exc.code},400)
            if self.path == '/api/shell/keys':
                token = os.environ.get('COMICS_META_SHELL_TOKEN', '')
                if not token or not secrets.compare_digest(self.headers.get('X-ComicsMeta-Shell', ''), token):
                    return self.respond({'error': 'Untrusted shell'}, 403)
                import setup_state
                try:
                    if not isinstance(body,dict) or set(body)!={'keys'}:raise setup_state.SetupError('key_invalid','')
                    with self.server._setup_mutex:
                        if self.server._quitting or self.server.setup_required:raise setup_state.SetupError('save_failed','')
                        result=setup_state.save_keys(body['keys'])
                    return self.respond(result)
                except setup_state.SetupError as exc:
                    return self.respond({'error':exc.code,'field':exc.field},400)
            if self.path == '/api/shell/setup':
                token = os.environ.get('COMICS_META_SHELL_TOKEN', '')
                if not token or not secrets.compare_digest(self.headers.get('X-ComicsMeta-Shell', ''), token):
                    return self.respond({'error': 'Untrusted shell'}, 403)
                import setup_state, library_lock
                try:
                    with self.server._setup_mutex:
                        if self.server._quitting or not self.server.setup_required:raise setup_state.SetupError('save_failed')
                        result = setup_state.save(body.get('folder'), body.get('keys', {}),retain_claim=True)
                        try:
                            self.server.activate_setup()
                        except library_lock.LibraryBusy:
                            raise setup_state.SetupError('library_busy') from None
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
            if self.path in ('/api/backups/reveal','/api/backups/delete'):
                # Allowed while paused: neither changes a comic. Ids only, never a path (Amendment A7.5-A7.6).
                import kept_backups
                try:
                    if self.path == '/api/backups/reveal':
                        if not isinstance(body,dict) or set(body)!={'id'}:raise kept_backups.BackupError('not_found')
                        return self.respond(kept_backups.reveal(body['id']))
                    ids=body.get('ids') if isinstance(body,dict) and set(body)=={'ids'} else None
                    if not isinstance(ids,list) or not 0<len(ids)<=kept_backups.LIMIT or not all(isinstance(i,str) for i in ids) or len(set(ids))!=len(ids):
                        raise kept_backups.BackupError('failed')
                    return self.respond(kept_backups.delete(ids))
                except kept_backups.BackupError as exc:
                    return self.respond({'error':exc.code,'code':exc.code},400)
            if self.path == '/api/attention/reveal':
                # FolderHelpActions 8.3: Open folder / Show in folder. Allowed while paused; ids only, never a path.
                import folder_help
                try:
                    if not isinstance(body,dict) or 'ticket' not in body or set(body)-{'ticket','problem'}:
                        raise folder_help.HelpError('gone')
                    return self.respond(folder_help.reveal(body['ticket'],body.get('problem')))
                except folder_help.HelpError as exc:
                    return self.respond(exc.payload(),400)
            if self.path == '/api/try-again':
                # Failure-filter spec R4. Allowed while paused: it only clears a stop flag in
                # the comic's record; the one attempt runs at the next pass after Resume.
                import problems
                changed, problem = problems.try_again(int(body['comic']))
                return self.respond({'ok': True, 'changed': changed, 'problem': problem})
            if getattr(self.server, 'setup_required', False):
                return self.respond({'error': 'Finish setup before starting processing.'}, 403)
            if self.path in ('/api/attention/check','/api/attention/delete-backups','/api/attention/close'):
                # FolderHelpActions 8.3, Amendment A8 and Amendment 2 B9.4: the ticket id (and the offered
                # backup and temporary-file ids), never a path. Each refuses with its own 'paused' code,
                # ahead of the generic guard below.
                import folder_help
                try:
                    keys={'/api/attention/delete-backups':({'ticket','backups'},{'ticket','backups','temps'})}.get(self.path,({'ticket'},))
                    if not isinstance(body,dict) or set(body) not in keys:
                        raise folder_help.HelpError('invalid','choose a folder that needs help')
                    if self.path == '/api/attention/check':
                        return self.respond(folder_help.check(body['ticket']))
                    if self.path == '/api/attention/close':
                        return self.respond(folder_help.close_recheck(body['ticket']))
                    return self.respond(folder_help.delete_backups(body['ticket'],body['backups'],body.get('temps',[])))
                except folder_help.HelpError as exc:
                    return self.respond(exc.payload(),400)
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
                    fields=manual_issue_fields(present,fields,issue)
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
                    import automatic, kept_backups
                    row=comic(int(body['comic']))
                    present,_,_=read_metadata(filesystem_path(row['path']))
                    fields=manual_issue_fields(present,fields,issue)
                    # The page tells every outcome apart (BackupLocation Amendment A1, A7.1).
                    attempt={}
                    with comic_write_guard(row['path']):
                        # Under the writer guard, before the backup copy: what the backup must equal to be removed.
                        with filesystem_path(row['path']).open('rb') as handle:
                            original_sha256=hashlib.file_digest(handle,'sha256').hexdigest()
                        try:
                            backup=write_metadata(row,fields,attempt=attempt,verify_readback=True,guard_held=True,
                                                  overwrite_fields=('Web',),expected_snapshot=present)
                        except Exception:
                            made=attempt.get('backup')
                            if not made:raise  # Nothing was copied: the server text, as before.
                            kept_backups.record(row['path'],made,'save_not_verified')
                            result=({'error':'The change was not verified. Check the file and retained recovery backup before trying again.',
                                     'verified':False,'backup':made,'backup_id':kept_backups.issue(made)},400)
                        else:
                            try:
                                remove_verified_backup(row['path'],backup,original_sha256)
                                removed=True
                            except Exception:
                                removed=False  # Saved and verified; only the redundant copy stays.
                                kept_backups.record(row['path'],backup,'delete_refused')
                            result=({'ok':True,'verified':True,'backup':backup,'backup_retained':not removed,
                                     'backup_removed_after_verification':removed,
                                     **({} if removed else {'backup_id':kept_backups.issue(backup)})},200)
                return self.respond(*result)
            self.respond({'error': 'Not found'}, 404)
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):
            return
        except Exception as exc:
            self.respond({'error': str(exc)}, 400)


class LocalServer(ThreadingHTTPServer):
    allow_reuse_address = False

    def __init__(self,*args,defer_startup=False,**kwargs):
        # Capture once for this running server; a disk update cannot relabel it.
        try:
            value=(BASE/'VERSION').read_text(encoding='utf-8').strip()
            self.loaded_version=value if re.fullmatch(r'v?\d+\.\d+\.\d+',value) else ''
        except (OSError,UnicodeError):self.loaded_version=''
        self.setup_required=False
        self._setup_mutex=threading.Lock()
        self.startup_phase='starting' if defer_startup else 'ready'
        self.startup_error=None
        self.supervisor_stop=None
        self.worker_leases={}
        self._quit_mutex=threading.Lock()
        self._quitting=False
        super().__init__(*args,**kwargs)
        if not defer_startup:self.initialize()

    def initialize(self):
        if os.environ.get('COMICS_META_SHELL_TOKEN'):
            import setup_state
            self.setup_required = not setup_state.status()['configured']
        import yandex_verification,lens_verification,progress_snapshot
        yandex_verification.server_started()
        lens_verification.server_started()
        self.progress_snapshot=progress_snapshot.Snapshot()

    def setup_status(self):
        if not os.environ.get('COMICS_META_SHELL_TOKEN'):return {'configured': True}
        import setup_state
        result = setup_state.status()
        result['configured'] = not self.setup_required
        return result

    def activate_setup(self):
        if not self.setup_required:return
        import library_lock, supervisor
        library_lock.claim_configured('dashboard')
        self.supervisor_stop=supervisor.start(BASE)
        self.setup_required=False

    def server_close(self):
        if hasattr(self,'progress_snapshot'):self.progress_snapshot.close()
        super().server_close()
        if getattr(self,'_quitting',False):
            import library_lock
            library_lock.release_all()  # Quit already holds worker leases; no writer remains.

    def begin_quit(self):
        """Quit: workers finish their current safe step and exit, then the server stops."""
        with self._quit_mutex:
            if not self._quitting:
                self._quitting=True
                threading.Thread(target=self.finish_quit,name='graceful-quit',daemon=True).start()
        return {'ok':True,'stopping':True}

    def finish_quit(self,worker_timeout=None):
        import pause_control
        with self._setup_mutex:
            if self.setup_required:
                self.shutdown()
                return True
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
    if not os.environ.get('COMICS_META_SHELL_TOKEN'):
        # Keep the original direct/terminal contract; the shell has its own
        # authenticated early-start protocol below.
        with db():pass
        import library_lock, pause_control, supervisor
        pause_control.begin_run()
        try:library_lock.claim_configured('dashboard')
        except library_lock.LibraryBusy as exc:
            print(str(exc),file=sys.stderr,flush=True);return library_lock.EXIT_LIBRARY_BUSY
        recover_interrupted_writes()  # Code review v0.6.7 Q2: before any worker can write.
        server=LocalServer(('127.0.0.1',options.port),Handler)
        server.supervisor_stop=threading.Event() if server.setup_required else supervisor.start(BASE)
        address=f'http://127.0.0.1:{options.port}'
        print(f'Comic metadata pilot: {address}\nKeep this window open. Ctrl+C stops the app.')
        if not options.no_browser:webbrowser.open(address)
        try:server.serve_forever()
        except KeyboardInterrupt:pass
        finally:
            if server.supervisor_stop is not None:server.supervisor_stop.set()
            server.server_close()
        return 0
    server = LocalServer(('127.0.0.1', options.port), Handler, defer_startup=True)
    result = [0]
    def catalog_step(operation):
        # SQLite's 30 s busy timeout is per attempt, not the startup deadline.
        # Each operation here is transactional/idempotent; no worker has launched.
        while True:
            try:return operation()
            except sqlite3.OperationalError as exc:
                if getattr(exc,'sqlite_errorcode',0) & 255 not in (sqlite3.SQLITE_BUSY,sqlite3.SQLITE_LOCKED):raise
                print('Startup catalog busy; waiting to retry.',file=sys.stderr,flush=True)
                time.sleep(.25)
    def initialize():
        import library_lock, pause_control, supervisor
        try:
            server.startup_phase='catalog'
            def open_catalog():
                with db():pass
            catalog_step(open_catalog)
            server.startup_phase='control'
            catalog_step(pause_control.begin_run)
            if os.environ.get('COMICS_META_SHELL_TOKEN'):catalog_step(lambda:pause_control.shell_pause(False))
            server.startup_phase='library'
            library_lock.claim_configured('dashboard')
            # Code review v0.6.7 Q2: finish or undo a write the last session was stopped in (Quit's Closing cap, a
            # crash), with the library claimed and before any worker starts. Never raises.
            recover_interrupted_writes()
            server.startup_phase='service'
            catalog_step(server.initialize)
            server.supervisor_stop = threading.Event() if server.setup_required else supervisor.start(BASE)
            server.startup_phase='ready'
            if not options.no_browser:webbrowser.open(f'http://127.0.0.1:{options.port}')
        except Exception as exc:
            result[0]=library_lock.EXIT_LIBRARY_BUSY if isinstance(exc,library_lock.LibraryBusy) else 1
            print('Startup failed:',type(exc).__name__,str(exc),file=sys.stderr,flush=True)
            server.startup_error='LIBRARY_BUSY' if result[0]==library_lock.EXIT_LIBRARY_BUSY else 'STARTUP_FAILED'
            server.startup_phase='failed'
            server.shutdown()
    threading.Thread(target=initialize,name='service-startup',daemon=True).start()
    address = f'http://127.0.0.1:{options.port}'
    print(f'Comic metadata pilot: {address}\nKeep this window open. Ctrl+C stops the app.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if server.supervisor_stop is not None:server.supervisor_stop.set()
        server.server_close()
    return result[0]


if __name__ == '__main__':
    sys.exit(main())
