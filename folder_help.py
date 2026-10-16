"""Folder-level "Your help is needed" lines: Check and requeue, Open folder, Show in folder,
Delete backup and requeue, Close and recheck folder (UXSpec FolderHelpActions 2026-10-16 and its
Amendment with Sergei's answers).

The page never names a path. A line is addressed by its ticket id (the queue file's stem) and a
problem row by an opaque id this process issued in a check. Every route re-reads the ticket, its
plan and the files on disk; nothing the page holds is trusted beyond those ids.

The check only reads. Its one write is the close at the end: the ticket leaves needs_attention and
the unwritten comics' research records are made due, so the next pass of the folder plans them
again from what is on disk. Delete backup and requeue deletes only kept backups the check offered,
each comic proved again under its write guard immediately before its backup is deleted (Amendment A8).
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import stat
import threading
import time
import zipfile
from collections import OrderedDict
from contextlib import contextmanager
from pathlib import Path
import app
import storage

CODES = ('interrupted', 'comic_changed', 'outside_folder', 'not_verified', 'backup_kept', 'library_busy', 'other')
INTERRUPTED = 'Interrupted batch; inspect results and retained backups before requeuing.'
FINDINGS = ('zip_failed', 'written_changed', 'unwritten_changed', 'missing', 'temp_left', 'backup_left')  # Section 4.2 order.
LIMIT = 20  # Problem rows returned; the page says how many more there are.
BACKUPS = '.comic-metadata-backups'
_NOT_VERIFIED = ('Archive validation failed.', 'Archive contents changed unexpectedly.', 'Backup verification failed.')
_NOT_VERIFIED_PREFIXES = ('Temporary archive metadata verification failed for', 'Readback verification failed for')
_LIBRARY_BUSY_PREFIXES = ('The library lock is busy.', 'Another Comics Meta copy is using this library',
                          'A new library claim could not be locked.', 'The library lock folder is unavailable')
_SHA = re.compile(r'[0-9a-f]{64}')
_ID = re.compile(r'[0-9a-f]{32}')
_REPARSE = 0x400
_SECRET = secrets.token_bytes(32)
_IDS = OrderedDict()  # problem id -> {'ticket', 'code', 'target'} it was issued for
_IDS_LOCK = threading.Lock()
_BUSY = threading.Lock()  # One check, delete or close at a time across all lines.

# The page words every known code itself; these fill "{server message}" only for unknown ones,
# mid-sentence, so they start in lower case.
MESSAGES = {
    'gone': 'this folder is not waiting for help.',
    'paused': 'processing is paused.',
    'busy': 'this folder is already being checked.',
    'folder_unavailable': 'this folder is unavailable.',
    'outside_library': 'this folder is not in the current library.',
    'library_busy': 'another copy of the app is using this library.',
    'plan_unreadable': 'the saved plan for this folder cannot be read.',
    'not_found': 'file not found.',
    'failed': 'File Explorer could not be opened.',
}


class HelpError(Exception):
    """One code per row of the spec's outcome tables; `extra` rides along in the payload."""
    def __init__(self, code, message=None, **extra):
        super().__init__(message or MESSAGES.get(code, 'the request could not be completed.'))
        self.code = code
        self.extra = extra

    def payload(self):
        return {'error': str(self), 'code': self.code, **self.extra}


def classify(value):
    """The reason code for an exception or stored error text (section 5). Never raises; 'other' is the fallback."""
    try:
        import library_lock
        if isinstance(value, library_lock.LibraryBusy):
            return 'library_busy'
        text = str(value if value is not None else '').strip()
        if text == INTERRUPTED:
            return 'interrupted'
        if text.startswith('A completed archive changed before batch resume'):
            return 'comic_changed'
        if text == 'Target must stay in the planned folder.':
            return 'outside_folder'
        if text in _NOT_VERIFIED or text.startswith(_NOT_VERIFIED_PREFIXES):
            return 'not_verified'
        if text == 'Backup cleanup target is outside the expected folder.':
            return 'backup_kept'
        if text.startswith(_LIBRARY_BUSY_PREFIXES):
            return 'library_busy'
    except Exception:
        pass
    return 'other'


def attention(named):
    """Payload lines for the needs_attention tickets in `named` [(stem, ticket)], in queue order.
    A ticket saved before 0.2.5 has no code; its stored text is classified here, never in the page."""
    items = []
    for stem, ticket in sorted(named, key=lambda pair: pair[0]):
        if not isinstance(ticket, dict) or ticket.get('state') != 'needs_attention':
            continue
        error = ticket.get('error')
        error = '' if error is None else str(error)
        code = ticket.get('code') if ticket.get('code') in CODES else classify(error)
        items.append({'id': stem, 'code': code, 'folder': str(ticket.get('folder') or ''), 'error': error})
    return items


def display(path):
    import kept_backups
    return kept_backups.display(path)


# Tickets, folders and plans ------------------------------------------------------------------

def _ticket_path(ident):
    """The queue file a ticket id names. An id is a file stem: no separator, drive or wildcard."""
    import worker
    if (not isinstance(ident, str) or not 0 < len(ident) <= 200 or not ident.isprintable()
            or any(c in ident for c in '\\/:*?"<>|') or ident.strip(' .') != ident):
        raise HelpError('gone')
    path = worker.QUEUE / (ident + '.json')
    if path.parent != worker.QUEUE or path.name != ident + '.json':
        raise HelpError('gone')
    return path


def _read_ticket(path):
    try:
        item = json.loads(storage.read_text(path))
    except FileNotFoundError:
        raise HelpError('gone') from None
    except (OSError, ValueError):
        raise HelpError('other', 'the saved queue item for this folder cannot be read.') from None
    if not isinstance(item, dict) or item.get('state') != 'needs_attention':
        raise HelpError('gone')
    return item


def _folder(item):
    """The ticket's folder, resolved, once it is inside the configured library and present."""
    import library_lock
    root, folder = app.live_root(), item.get('folder')
    if not root or not isinstance(folder, str) or not folder:
        raise HelpError('folder_unavailable')
    if not library_lock.contains(library_lock.identity(root), library_lock.identity(folder)):
        raise HelpError('outside_library')
    try:
        info = app.filesystem_path(folder).stat()
    except OSError:
        raise HelpError('folder_unavailable') from None
    if not stat.S_ISDIR(info.st_mode):
        raise HelpError('folder_unavailable')
    return Path(display(folder)).resolve()


def _paused():
    import pause_control
    return pause_control.requested()


def _json_list(path):
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:
        return []
    if not isinstance(value, list):
        raise ValueError('not a list')
    return value


def _plan(item, folder):
    """(write entries [(path, entry)], verified results by path, skipped or failed paths).

    HelpError plan_unreadable, with the Close and recheck offer, when the saved plan is missing,
    cannot be read, or names a file outside its folder (Amendment A8.8)."""
    try:
        plan_path = Path(item['plan']).resolve()
        plan = json.loads(plan_path.read_text(encoding='utf-8'))
        if not isinstance(plan, dict) or not isinstance(plan.get('entries'), list):
            raise ValueError('entries')
        if Path(plan['folder']).resolve() != folder:
            raise ValueError('folder')
        results = _json_list(plan_path.parent / 'results.json')
        not_done = _json_list(plan_path.parent / 'skipped.json') + _json_list(plan_path.parent / 'failed.json')
        entries, seen = [], set()
        for entry in plan['entries']:
            if not isinstance(entry, dict) or not isinstance(entry.get('path'), str):
                raise ValueError('entry')
            if entry.get('action') != 'write':
                continue
            if not isinstance(entry.get('sha256'), str):
                raise ValueError('sha256')
            path = Path(entry['path']).resolve()
            if path.parent != folder:
                raise ValueError('outside')
            if str(path) not in seen:
                seen.add(str(path))
                entries.append((path, entry))
        finished = {r['path']: r for r in results
                    if isinstance(r, dict) and isinstance(r.get('path'), str) and r.get('metadata_readback_verified')}
        skipped = {str(Path(r['path']).resolve()) for r in not_done if isinstance(r, dict) and isinstance(r.get('path'), str)}
    except Exception:
        raise HelpError('plan_unreadable', offer={'kind': 'close_recheck'}) from None
    return entries, finished, skipped


# Fingerprints (Amendment A1, A8.1) -----------------------------------------------------------

def _fingerprint(size, mtime, sha256):
    if (isinstance(size, int) and not isinstance(size, bool) and isinstance(mtime, int) and not isinstance(mtime, bool)
            and isinstance(sha256, str) and _SHA.fullmatch(sha256)):
        return size, mtime, sha256
    return None


def before_state(entry):
    """The plan's record of the comic before any write: (size, mtime, SHA-256), or None."""
    signature = entry.get('signature')
    if isinstance(signature, list) and len(signature) == 2:
        return _fingerprint(signature[0], signature[1], entry.get('sha256'))
    return _fingerprint(entry.get('size'), entry.get('mtime'), entry.get('sha256'))


def after_state(result):
    """The verified after-state results.json records for the comic, or None.

    batch.apply records the output size and mtime but no output hash, so today this is always None
    and a written comic is never proved (Amendment A1: no recorded fingerprint means no match)."""
    if not isinstance(result, dict):
        return None
    signature = result.get('output_signature')
    if not (isinstance(signature, list) and len(signature) == 2):
        return None
    return _fingerprint(signature[0], signature[1], result.get('output_sha256'))


def _digest(path):
    with app.filesystem_path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def prove(path, entry, result, digest=None):
    """'original' or 'written' when the comic is byte for byte that recorded state, else None.
    Size, mtime and the hash of bytes read in this request must all match (Amendment A8.1);
    `digest` is one this same request just read."""
    try:
        info = app.filesystem_path(path).stat()
    except OSError:
        return None
    for basis, recorded in (('original', before_state(entry)), ('written', after_state(result))):
        if recorded is None or (info.st_size, info.st_mtime_ns) != recorded[:2]:
            continue
        if digest is None:
            try:
                digest = _digest(path)
            except OSError:
                return None
        if digest == recorded[2]:
            return basis
    return None


# The check (read-only until the close) -------------------------------------------------------

def _issue(ticket, code, target):
    key = '\0'.join((ticket, code, os.path.normcase(str(target))))
    ident = hmac.new(_SECRET, key.encode('utf-8', 'surrogatepass'), hashlib.sha256).hexdigest()[:32]
    with _IDS_LOCK:
        _IDS[ident] = {'ticket': ticket, 'code': code, 'target': str(target)}
        _IDS.move_to_end(ident)
        while len(_IDS) > 50 * LIMIT:
            _IDS.popitem(last=False)
    return ident


def _issued(ident, ticket):
    if not isinstance(ident, str) or not _ID.fullmatch(ident):
        return None
    with _IDS_LOCK:
        found = _IDS.get(ident)
    return found if found and found['ticket'] == ticket else None


def _kept_backups(folder, names):
    """{comic name: [backup paths]} kept for these comics, as Kept backups names them. OSError if unreadable."""
    import kept_backups
    directory = app.filesystem_path(folder) / BACKUPS
    try:
        info = directory.lstat()
    except FileNotFoundError:
        return {}
    if not stat.S_ISDIR(info.st_mode) or getattr(info, 'st_file_attributes', 0) & _REPARSE:
        return {}  # The app never makes this; Kept backups neither lists nor deletes what is inside.
    found = {}
    with os.scandir(directory) as entries:
        for item in entries:
            match = kept_backups.NAME.fullmatch(item.name)
            if not match or match[1] not in names:
                continue
            info = item.stat(follow_symlinks=False)
            if stat.S_ISREG(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & _REPARSE:
                found.setdefault(match[1], []).append(folder / BACKUPS / item.name)
    return {name: sorted(paths, key=lambda p: p.name) for name, paths in found.items()}


def _zip_ok(path):
    try:
        with zipfile.ZipFile(app.filesystem_path(path)) as archive:
            return archive.testzip() is None
    except OSError:
        raise HelpError('other', path.name + ' could not be read') from None
    except Exception:
        return False


def _inspect(folder, entries, finished, skipped):
    """Every finding for the plan's comics, sorted, each backup with its comic's proof. Reads only."""
    findings = []
    try:
        backups = _kept_backups(folder, {path.name for path, _ in entries})
    except OSError:
        raise HelpError('other', 'the recovery backup folder could not be read') from None
    for path, entry in entries:
        key, name, digest = str(path), path.name, None
        result = finished.get(key)
        if key not in skipped:  # A skipped or failed comic has its own wait record; it is not a problem.
            if not app.filesystem_path(path).is_file():
                findings.append(('missing', name, folder, None))
            elif not _zip_ok(path):
                findings.append(('zip_failed', name, path, None))
            else:
                info = app.filesystem_path(path).stat()
                if result is not None:
                    if result.get('output_signature') != [info.st_size, info.st_mtime_ns]:
                        findings.append(('written_changed', name, path, None))
                else:
                    recorded = before_state(entry)
                    try:
                        digest = _digest(path)
                    except OSError:
                        raise HelpError('other', name + ' could not be read') from None
                    if digest != entry['sha256'] or (recorded is not None and (info.st_size, info.st_mtime_ns) != recorded[:2]):
                        findings.append(('unwritten_changed', name, path, None))
        temporary = path.with_name(name + '.metadata-tmp')
        if os.path.lexists(app.filesystem_path(temporary)):
            findings.append(('temp_left', name, temporary, None))
        kept = backups.get(name, [])
        if kept:
            basis = prove(path, entry, result, digest)
            findings.extend(('backup_left', name, backup, basis) for backup in kept)
    findings.sort(key=lambda f: (f[1].casefold(), FINDINGS.index(f[0]), f[2].name.casefold()))
    return findings


def _unwritten(entries, finished, skipped):
    return [path for path, _ in entries if str(path) not in finished and str(path) not in skipped]


def _closable(findings):
    """Close and recheck folder is offered for a readable plan only when every finding is a comic that
    changed after the batch was planned (Sergei's 2a, 2026-10-16): nothing is damaged or left behind,
    and the next folder pass plans those comics again from what is on disk."""
    return bool(findings) and all(f[0] == 'unwritten_changed' for f in findings)


def _problems(ident, findings, entries, finished, skipped):
    """The section 4.2 result, with the Delete backup offer only when every finding is a kept backup
    of a proved comic and all of them are on screen (Amendment A3, A8.4), or the Close and recheck
    offer when every finding is `unwritten_changed` (_closable)."""
    rows = []
    for code, name, target, basis in findings[:LIMIT]:
        row = {'id': _issue(ident, code, target), 'name': name, 'finding': code, 'file': target.name}
        if code == 'backup_left' and basis:
            row['basis'] = basis
        rows.append(row)
    result = {'code': 'problems', 'total': len(findings), 'problems': rows}
    if findings and len(findings) <= LIMIT and all(f[0] == 'backup_left' and f[3] for f in findings):
        result['offer'] = {'kind': 'delete_backup', 'unwritten': len(_unwritten(entries, finished, skipped)),
                           'backups': [{'id': r['id'], 'name': r['name'], 'basis': r['basis']} for r in rows]}
    elif _closable(findings):
        result['offer'] = {'kind': 'close_recheck'}
    return result


def _fresh(ident, item, folder):
    """The current check result, never closing anything; a plan that cannot be read reports so."""
    try:
        entries, finished, skipped = _plan(item, folder)
        return _problems(ident, _inspect(folder, entries, finished, skipped), entries, finished, skipped)
    except HelpError as exc:
        return {'code': exc.code, **exc.extra}


def _check(ident, ticket_path, item, folder):
    """Close and requeue when nothing is found, else the problems. The caller holds the guards."""
    entries, finished, skipped = _plan(item, folder)
    findings = _inspect(folder, entries, finished, skipped)
    if findings:
        return _problems(ident, findings, entries, finished, skipped)
    unwritten = _unwritten(entries, finished, skipped)
    written = sum(str(path) in finished for path, _ in entries)
    _close(ticket_path, 'check_and_requeue', unwritten)
    return {'ok': True, 'unwritten': len(unwritten), 'written': written}


def _close(ticket_path, how, due):
    """Re-read the pause state and the ticket, make these comics due at the folder's next pass, close."""
    import discovery_state
    if _paused():
        raise HelpError('paused')
    item = _read_ticket(ticket_path)
    discovery_state.due_now(due)
    item.update(state='closed', closed_by=how, closed=time.time())
    storage.save(ticket_path, item)


@contextmanager
def _guarded(ident):
    """Pause guard, then single flight across all lines, needs_attention, folder inside the live library."""
    import library_lock
    if _paused():
        raise HelpError('paused')
    if not _BUSY.acquire(blocking=False):
        raise HelpError('busy')
    try:
        ticket_path = _ticket_path(ident)
        item = _read_ticket(ticket_path)
        folder = _folder(item)
        try:
            library_lock.require(folder)
        except library_lock.LibraryBusy:
            raise HelpError('library_busy') from None
        yield ticket_path, item, folder
    finally:
        _BUSY.release()


def check(ident):
    """Check and requeue (section 8.3)."""
    with _guarded(ident) as (ticket_path, item, folder):
        return _check(ident, ticket_path, item, folder)


def close_recheck(ident):
    """Close and recheck folder (Amendment A8.8 and Sergei's 2a, 2026-10-16). The inspection runs again at
    the click: the close is allowed only while the plan cannot be read, or while every finding is a comic
    changed after the batch was planned (_closable); anything else is refused as `plan_readable` (the
    folder changed since the check). No comic, temporary or backup file is touched. A readable plan makes
    its unwritten comics due, as Check and requeue does (a skipped or failed comic keeps its own wait);
    an unreadable one makes due the folder's comics still waiting on a plan."""
    import discovery_state
    with _guarded(ident) as (ticket_path, item, folder):
        try:
            entries, finished, skipped = _plan(item, folder)
        except HelpError:
            due = [path for path, record in discovery_state.load(folder)['checked'].items()
                   if isinstance(record, dict) and record.get('outcome') == 'queued']
        else:
            if not _closable(_inspect(folder, entries, finished, skipped)):
                raise HelpError('plan_readable', 'this folder changed since the check; use Check and requeue')
            due = _unwritten(entries, finished, skipped)
        _close(ticket_path, 'close_recheck', due)
        return {'ok': True}


def delete_backups(ident, backup_ids):
    """Delete backup and requeue (Amendment A8): prove every offered backup's comic, then delete each
    under its comic's write guard after proving it again, run the full check again, close only if clean."""
    import kept_backups
    if (not isinstance(backup_ids, list) or not 0 < len(backup_ids) <= LIMIT
            or not all(isinstance(i, str) and _ID.fullmatch(i) for i in backup_ids) or len(set(backup_ids)) != len(backup_ids)):
        raise HelpError('invalid', 'choose the offered backups')
    with _guarded(ident) as (ticket_path, item, folder):
        entries, finished, skipped = _plan(item, folder)
        comics = {path.name: (path, entry) for path, entry in entries}
        try:
            current = _kept_backups(folder, set(comics))
        except OSError:
            raise HelpError('other', 'the recovery backup folder could not be read') from None
        # A8.3: only ids this check issued that are still this ticket's kept backups now.
        now = {os.path.normcase(str(path)): name for name, paths in current.items() for path in paths}
        targets = []
        for backup_id in backup_ids:
            found = _issued(backup_id, ident)
            name = found and found['code'] == 'backup_left' and now.get(os.path.normcase(found['target']))
            if not name:
                raise HelpError('changed', check=_fresh(ident, item, folder))
            targets.append((Path(found['target']), name))
        # A8.5: all before any. Every comic is proved before the first delete.
        for _, name in targets:
            path, entry = comics[name]
            if not prove(path, entry, finished.get(str(path))):
                raise HelpError('changed', check=_fresh(ident, item, folder))
        deleted = 0
        for backup, name in sorted(targets, key=lambda target: target[0].name.casefold()):
            path, entry = comics[name]

            def again(comic, path=path, entry=entry):
                # Under the comic's write guard, immediately before this delete (A8.2).
                if not prove(path, entry, finished.get(str(path))):
                    raise HelpError('changed')
            try:
                kept_backups.delete_one(backup, before_unlink=again)
            except HelpError:
                if not deleted:
                    raise HelpError('changed', check=_fresh(ident, item, folder)) from None
                raise HelpError('delete_failed', deleted=deleted, total=len(targets)) from None
            except Exception:
                raise HelpError('delete_failed', deleted=deleted, total=len(targets)) from None
            deleted += 1
        try:
            if _paused():
                raise HelpError('paused')
            result = _check(ident, ticket_path, _read_ticket(ticket_path), folder)
        except HelpError as exc:
            if exc.code == 'gone':
                raise
            raise HelpError('not_requeued', str(exc), deleted=deleted, reason='paused' if exc.code == 'paused' else 'other') from None
        if result.get('ok'):
            return dict(result, deleted=deleted)
        raise HelpError('not_requeued', 'the check found problems', deleted=deleted, reason='problems', check=result)


# Open folder and Show in folder (section 6) --------------------------------------------------

def reveal(ident, problem=None):
    """Open the ticket's folder, or show the file a problem row names, in File Explorer. Nothing is written."""
    import kept_backups
    item = _read_ticket(_ticket_path(ident))
    folder = _folder(item)
    target = None
    if problem is not None:
        found = _issued(problem, ident)
        if not found:
            raise HelpError('not_found')
        if found['code'] != 'missing':  # A missing comic has no file to select: open the folder.
            target = Path(found['target'])
            if target.parent not in (folder, folder / BACKUPS):
                raise HelpError('not_found')
            try:
                info = app.filesystem_path(target).lstat()
            except OSError:
                raise HelpError('not_found') from None
            if not stat.S_ISREG(info.st_mode) or getattr(info, 'st_file_attributes', 0) & _REPARSE:
                raise HelpError('not_found')
    try:
        if target is None:
            kept_backups._open_folder(display(folder))
        else:
            try:
                kept_backups._select(display(target))
            except OSError:
                kept_backups._open_folder(display(target.parent))  # Over MAX_PATH Explorer may not select (8.3).
    except OSError:
        raise HelpError('failed') from None
    return {'ok': True}
