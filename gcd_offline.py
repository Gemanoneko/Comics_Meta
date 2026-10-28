"""Offline GCD provider and transactional index replacement. Inputs are read-only."""
import datetime
import json
import os
import re
import shutil
import sqlite3
import threading
import time
import uuid
import zipfile
from contextlib import closing, contextmanager
from pathlib import Path
import app
import file_lock
import storage
from gcd_matching import Matcher, folder_year, series_key

RULES = 'gcd-offline-1'
MAX_DUMP = 16_000_000_000
INDEX_SPACE = 800_000_000
_lock = threading.RLock()
_thread = None
_cancel = threading.Event()
_current_cache = (None, None)


class GcdError(ValueError):
    def __init__(self, code, **details):
        super().__init__(code)
        self.code, self.details = code, details


def root():
    return app.DATA / 'gcd-offline'


def plain(path):
    path = Path(path)
    for part in (path, *path.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if part.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise GcdError('build_failed')
    return path


def read_json(path):
    if not path.exists():
        return {}
    if path.stat().st_size > 65536:
        raise GcdError('build_failed')
    return json.loads(path.read_text(encoding='utf-8'))


def current():
    global _current_cache
    pointer = root() / 'current.json'
    try:
        stat = pointer.stat()
        key = (str(pointer), stat.st_mtime_ns, stat.st_size)
    except FileNotFoundError:
        return None
    with _lock:
        if _current_cache[0] == key:
            return dict(_current_cache[1]) if _current_cache[1] else None
        value = read_json(pointer)
        if not re.fullmatch(r'index-[0-9a-f]{32}\.sqlite', str(value.get('index', ''))):
            raise GcdError('build_failed')
        if not plain(root() / value['index']).is_file():
            raise GcdError('build_failed')
        _current_cache = (key, value)
        return dict(value)


def rules_stamp():
    value = current()
    return value['rules'] if value else RULES + ':none'


def status():
    ready = current()
    if ready:
        ready['age_days'] = max(0, (datetime.date.today() - datetime.date.fromisoformat(ready['dump_date'])).days)
    attempt = read_json(root() / 'attempt.json')
    if attempt.get('state') == 'building':
        fd = file_lock.open_lock(plain(root() / 'build.lock'))
        try:
            if file_lock.try_lock(fd):
                attempt.update(state='failed', code='interrupted')
                storage.save(root() / 'attempt.json', attempt)
                file_lock.unlock(fd)
        finally:
            os.close(fd)
    if attempt.get('started'):
        attempt['elapsed_seconds'] = max(0, int((attempt.get('ended') or time.time()) - attempt['started']))
    return {'current': ready, 'attempt': attempt or None}


def inspect_source(selected):
    """Read only the archive directory/header; never extract during preview."""
    if not isinstance(selected, str) or not selected or not Path(selected).is_absolute():
        raise GcdError('zip_missing')
    source = Path(selected)
    try:
        stat = source.stat()
        if not source.is_file():
            raise GcdError('zip_missing')
        if source.suffix.lower() == '.db':
            member, expanded = source.name, stat.st_size
            with source.open('rb') as handle:
                magic = handle.read(16)
        else:
            try:
                with zipfile.ZipFile(source) as archive:
                    files = [entry for entry in archive.infolist() if not entry.is_dir()]
                    if len(files) != 1 or not files[0].filename.lower().endswith('.db'):
                        raise GcdError('not_gcd_dump')
                    entry = files[0]
                    if entry.flag_bits & 1 or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                        raise GcdError('not_gcd_dump')
                    member, expanded = entry.filename, entry.file_size
                    with archive.open(entry) as handle:
                        magic = handle.read(16)
            except zipfile.BadZipFile:
                raise GcdError('not_a_zip') from None
        if magic != b'SQLite format 3\0' or not 0 < expanded <= MAX_DUMP:
            raise GcdError('not_gcd_dump')
        date = re.search(r'(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)', member)
        if not date:
            raise GcdError('not_gcd_dump')
        dump = datetime.date.fromisoformat(date[1]).isoformat()
    except GcdError:
        raise
    except (OSError, ValueError, RuntimeError):
        raise GcdError('zip_missing') from None
    volume = plain(root())
    while not volume.exists():
        volume = volume.parent
    needed = INDEX_SPACE + (expanded if source.suffix.lower() != '.db' else 0)
    free = shutil.disk_usage(volume).free
    active = current()
    relation = 'same_dump' if active and dump == active['dump_date'] else 'older_dump' if active and dump < active['dump_date'] else 'newer'
    result = {'path': str(source), 'file_name': source.name, 'dump_date': dump, 'size': stat.st_size,
              'signature': [stat.st_size, stat.st_mtime_ns], 'member': member, 'expanded': expanded,
              'needed': needed, 'free': free, 'drive': volume.anchor, 'relation': relation}
    if free < needed:
        raise GcdError('disk_space', **result)
    return result


SCHEMA = {
    'gcd_series': 'id name sort_name year_began year_ended publisher_id language_id country_id issue_count publication_type_id publishing_format is_singleton deleted',
    'gcd_publisher': 'id name', 'stddata_language': 'id code', 'stddata_country': 'id code',
    'gcd_series_publication_type': 'id name',
    'gcd_issue': 'id series_id number key_date on_sale_date title barcode valid_isbn page_count rating indicia_publisher_id variant_of_id deleted',
    'gcd_indicia_publisher': 'id name', 'gcd_issue_brand_emblem': 'issue_id brand_id', 'gcd_brand': 'id name',
    'gcd_story': 'id issue_id type_id title script pencils inks colors letters editing characters synopsis genre sequence_number deleted',
    'gcd_story_credit': 'story_id credit_type_id creator_id deleted', 'gcd_creator_name_detail': 'id name',
    'gcd_issue_credit': 'issue_id creator_id deleted credit_type_id',
}


def check_schema(source):
    with closing(sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True)) as con:
        con.execute('PRAGMA trusted_schema=OFF')
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table, columns in SCHEMA.items():
            if table not in tables or not set(columns.split()) <= {r[1] for r in con.execute('PRAGMA table_info(' + table + ')')}:
                raise GcdError('schema_unsupported')


def remove_owned(path):
    """Only our exact staging/index names, under the non-linked app-data index root."""
    path = plain(path)
    if path.parent != plain(root()) or not re.fullmatch(r'(?:stage-[0-9a-f]{32}|index-[0-9a-f]{32}\.sqlite)', path.name):
        raise GcdError('build_failed')
    if not path.exists():
        return
    if path.is_dir():
        for child in path.rglob('*'):
            plain(child)
        shutil.rmtree(path)
    else:
        path.unlink()


def start(selected, force=False):
    global _thread
    if type(force) is not bool:
        raise GcdError('build_failed')
    info = inspect_source(selected)
    with _lock:
        plain(root()).mkdir(parents=True, exist_ok=True)
        fd = file_lock.open_lock(plain(root() / 'build.lock'))
        if not file_lock.try_lock(fd):
            os.close(fd)
            raise GcdError('busy')
        try:
            # Recheck relation while holding the build lock.
            active = current()
            relation = 'same_dump' if active and info['dump_date'] == active['dump_date'] else 'older_dump' if active and info['dump_date'] < active['dump_date'] else None
            if relation and not force:
                raise GcdError(relation)
            _cancel.clear()
            attempt = {'id':uuid.uuid4().hex, 'state':'building', 'started':time.time(), 'stage':1, 'stage_percent':0, 'overall_percent':0}
            storage.save(root() / 'attempt.json', attempt)
            _thread = threading.Thread(target=_build, args=(info, attempt, fd), name='gcd-index-build', daemon=True)
            _thread.start()
        except BaseException:
            file_lock.unlock(fd)
            os.close(fd)
            raise
    return status()


def cancel():
    with _lock:
        attempt = read_json(root() / 'attempt.json')
        if attempt.get('state') == 'building' and attempt.get('stage') != 6:
            _cancel.set()
    return status()


def _build(info, attempt, fd):
    from gcd_index import build_index
    stage = root() / ('stage-' + attempt['id'])
    target = root() / ('index-' + attempt['id'] + '.sqlite')
    switched = False
    def progress(number, percent):
        if _cancel.is_set():
            raise InterruptedError('cancelled')
        # SQL stages have no reliable percent until they finish; never estimate their progress.
        attempt.update(stage=number, stage_percent=percent, overall_percent=100 if number == 6 and percent == 100 else None)
        storage.save(root() / 'attempt.json', attempt)
    try:
        # An interrupted attempt cannot be active while this process owns the lock.
        for stale in root().glob('stage-*'):
            remove_owned(stale)
        stage.mkdir()
        source = Path(info['path'])
        progress(1, 100)
        if source.suffix.lower() == '.db':
            dump = source
        else:
            dump = stage / 'dump.db'
            with zipfile.ZipFile(source) as archive, archive.open(info['member']) as reader, dump.open('xb') as writer:
                total = 0
                while chunk := reader.read(1024 * 1024):
                    if _cancel.is_set():
                        raise InterruptedError('cancelled')
                    total += len(chunk)
                    if total > info['expanded'] or total > MAX_DUMP:
                        raise GcdError('not_gcd_dump')
                    writer.write(chunk)
                    if total % (64 * 1024 * 1024) < len(chunk):
                        progress(2, round(100 * total / info['expanded'], 1))
                if total != info['expanded']:
                    raise GcdError('not_gcd_dump')
            progress(2, 100)
        if [source.stat().st_size, source.stat().st_mtime_ns] != info['signature']:
            raise GcdError('zip_missing')
        check_schema(dump)
        build_index(dump, target, info['dump_date'], progress, _cancel.is_set)
        if [source.stat().st_size, source.stat().st_mtime_ns] != info['signature']:
            raise GcdError('zip_missing')
        # Remove the uncompressed copy before publishing success. Never touch the selected source.
        remove_owned(stage)
        with _lock:
            progress(6, None)
            active = {'index':target.name, 'dump_date':info['dump_date'], 'built':time.time(), 'file_name':info['file_name'],
                      'rules':RULES + ':' + info['dump_date'] + ':' + attempt['id']}
            storage.save(root() / 'current.json', active)
            switched = True
            attempt.update(state='ready', stage=6, stage_percent=100, overall_percent=100)
    except Exception as exc:
        attempt.update(state='cancelled' if _cancel.is_set() or isinstance(exc, InterruptedError) else 'failed',
                       code='cancelled' if _cancel.is_set() or isinstance(exc, InterruptedError) else exc.code if isinstance(exc, GcdError) else 'build_failed')
    finally:
        try:
            remove_owned(stage)
            if not switched:
                remove_owned(target)
            # Old readers hold their own SQLite connection. Windows keeps a busy old index until a later build.
            active = current()
            for old in root().glob('index-*.sqlite'):
                if active and old.name == active['index']:
                    continue
                try:
                    remove_owned(old)
                except OSError:
                    pass
        except Exception:
            attempt.update(state='failed', code='build_failed', cleanup_pending=True)
        attempt['ended'] = time.time()
        try:
            storage.save(root() / 'attempt.json', attempt)
        finally:
            file_lock.unlock(fd)
            os.close(fd)


def legends_path(path):
    """Sergei's 2026-10-28 hold: every explicitly Star Wars Legends-labelled file."""
    return 'star wars legends' in str(path).casefold()


def lookup(row, old, *, index=None, diagnostics=None):
    import coverage_priority
    import research
    if legends_path(row['path']):
        if diagnostics is not None: diagnostics['excluded'] = 'Star Wars Legends tree'
        return None
    if not coverage_priority.language_eligible(row, old):
        return None
    active = current() if index is None else {'dump_date':'measurement', 'rules':RULES}
    if not active:
        return None
    with closing(sqlite3.connect((root() / active['index']).resolve().as_uri() + '?mode=ro', uri=True)) if index is None else _borrow(index) as con:
        con.row_factory = sqlite3.Row
        matcher = Matcher(con)
        path = row['path']
        series, number = research.query_identity(row, old)
        g5 = re.fullmatch(r'[#\W_]*(\d{1,4})[\W_]*', series)
        if g5 and not old.get('Series') and not re.search(r'(?<!\d)' + g5[1] + r'(?!\d)', Path(path).parent.name):
            if diagnostics is not None: diagnostics['excluded'] = 'number-only G5'
            return None
        year = str(old.get('Year') or row.get('year') or '')
        year_source = 'ComicInfo' if old.get('Year') else 'file name (YYYY)' if year else 'none'
        rule, candidates, _, _, series_map, target = matcher.match_guarded(path, series, number, year, year_source, folder_year(path))
        if diagnostics is not None: diagnostics.update(rule=rule, candidates=len(candidates))
        if len(candidates) != 1:
            return None
        issue = candidates[0]
        matched = series_map[issue['series_id']]
        if rule in ('unnumbered', 'collection') and re.search(r'complete\s+vol|\d+\s+of\s+\d+|\[\s*\[|\(\s*\(', Path(path).name, re.I):
            if diagnostics is not None: diagnostics['excluded'] = 'unparsed collection name'
            return None
        fields, _ = matcher.gcd_fields(issue, matched, target)
        if old.get('Series') and series_key(old['Series']) in (series_key(fields['Series']), matched['sort_key']):
            fields['Series'] = old['Series']
        count = re.search(r'\(\s*of\s+(\d+)\s*\)', Path(path).name, re.I)
        if count: fields['Count'] = count[1]
        saved = con.execute('SELECT value FROM fields WHERE issue_id=?', (issue['id'],)).fetchone()
        summary = '\n\n'.join(json.loads(saved[0]).get('Summary', [])) if saved else ''
        credit = 'Metadata from the Grand Comics Database (www.comics.org), CC BY-SA 4.0, data dump ' + active['dump_date'] + ': ' + fields['Web']
        return {'provider':'GCD offline', 'fields':fields, 'sources':[{'url':fields['Web'], 'text':summary, 'title':matched['name']}],
                'match_rule':rule, 'rules':active['rules'], 'attribution':credit}


@contextmanager
def _borrow(con):
    yield con
