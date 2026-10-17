"""Folder-level "Your help is needed" lines: Check and requeue, Open folder, Show in folder,
Delete backup and requeue, Close and recheck folder (UXSpec FolderHelpActions 2026-10-16 and its
Amendment with Sergei's answers).

The page never names a path. A line is addressed by its ticket id (the queue file's stem) and a
problem row by an opaque id this process issued in a check. Every route re-reads the ticket, its
plan and the files on disk; nothing the page holds is trusted beyond those ids.

The check only reads. Its one write is the close at the end: the ticket leaves needs_attention and
the unwritten comics' research records are made due, so the next pass of the folder plans them
again from what is on disk. Delete backup and requeue deletes only the kept backups, and the app's
own leftover temporary files, that the check offered and the click offers again from disk: every
comic, backup and temporary file is proved again with that comic's write guard held, and the deletes
run under the same hold (Amendment A8; the backup must hash to the comic as planned, v0.2.5 review
M1; temporary files and the recomputed offer, Amendment 2 B2 and B9).
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
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import NamedTuple
import app
import storage

CODES = ('interrupted', 'comic_changed', 'outside_folder', 'not_verified', 'backup_kept', 'library_busy', 'other')
INTERRUPTED = 'Interrupted batch; inspect results and retained backups before requeuing.'
FINDINGS = ('zip_failed', 'written_changed', 'unwritten_changed', 'missing', 'temp_left', 'backup_left')  # Section 4.2 order.
LIMIT = 20  # Problem rows returned; the page says how many more there are.
BACKUPS = '.comic-metadata-backups'
TEMPORARY = '.metadata-tmp'  # app._write_metadata_guarded writes '{comic file name}.metadata-tmp' beside the comic.
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
    'changed': 'a comic or one of its files changed since the check.',
    'file_gone': 'a file from the check is no longer there.',
    'writing': 'a comic in this folder is being written now.',
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


class _Refused(Exception):
    """A proof failed with a comic's write guard held; the caller words it once the guards are released."""
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class Finding(NamedTuple):
    """One problem row. `basis` is the comic's proof ('original', 'written' or None) for a backup or a
    temporary file; `covered` says the Delete offer may include it (A3, Amendment 2 B2); `unproved` says
    why a backup is not covered: 'comic', 'backup' or 'unread' (Amendment 2 B6)."""
    code: str
    name: str
    target: Path
    basis: str | None = None
    covered: bool = False
    unproved: str | None = None


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


def backup_state(backup, entry):
    """'same' when the backup is byte for byte the comic as the plan recorded it before any write (the
    SHA-256 rule app.remove_verified_backup applies to the app's own cleanup), 'differs' when it holds
    other bytes, 'unread' when it cannot be read to compare (Amendment 2 B6)."""
    try:
        return 'same' if _digest(backup) == entry['sha256'] else 'differs'
    except OSError:
        return 'unread'


def backup_proved(backup, entry):
    """True when backup_state is 'same'. For a comic proved 'original' that is also the comic as it is
    now. A backup left by another write holds another version of the comic, so it is never offered and
    never deleted (v0.2.5 review M1)."""
    return backup_state(backup, entry) == 'same'


# The app's own temporary file (Amendment 2 B2.3, B9.3) ----------------------------------------

def temporary_path(comic):
    """Exactly the name app._write_metadata_guarded gives its temporary archive: beside the comic,
    '{comic file name}.metadata-tmp'. No other name or place is ever the app's."""
    return comic.with_name(comic.name + TEMPORARY)


def _plain_file(path):
    """A regular file that is not a link or reparse point, by lstat. False if it cannot be read."""
    try:
        info = app.filesystem_path(path).lstat()
    except OSError:
        return False
    return stat.S_ISREG(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & _REPARSE


def _temporary_checked(temp, comic, folder):
    """The refusals Kept backups applies to a backup, applied to the temporary file: the exact name for
    this comic, in the comic's own folder (a real folder, no link), inside the configured library, a
    regular file with no link or reparse point. _Refused('file_gone') when it is not there."""
    import library_lock
    root = app.live_root()
    if temp != temporary_path(comic) or comic.parent != folder or not root:
        raise _Refused('changed')
    if not library_lock.contains(library_lock.identity(root), library_lock.identity(temp)):
        raise _Refused('changed')
    try:
        info = app.filesystem_path(folder).lstat()
    except OSError:
        raise _Refused('file_gone') from None
    if not stat.S_ISDIR(info.st_mode) or getattr(info, 'st_file_attributes', 0) & _REPARSE:
        raise _Refused('changed')
    try:
        info = app.filesystem_path(temp).lstat()
    except FileNotFoundError:
        raise _Refused('file_gone') from None
    except OSError:
        raise _Refused('changed') from None
    if not stat.S_ISREG(info.st_mode) or getattr(info, 'st_file_attributes', 0) & _REPARSE:
        raise _Refused('changed')


def _delete_temporary(temp, comic, folder):
    """Delete the app's temporary file for this comic. The caller holds the comic's write guard and has
    proved the comic under it: a live writer owns its temporary file and removes it itself (B9.2)."""
    import kept_backups
    import library_lock
    if not app.write_guard_held(comic):
        raise app.ArchiveChanged('Metadata write guard was not held; nothing deleted.')
    _temporary_checked(temp, comic, folder)  # Again, right before the unlink.
    library_lock.require(temp)  # Raises before any change if another copy owns the library.
    kept_backups._unlink(app.filesystem_path(temp))


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
    """Every finding for the plan's comics, sorted, each backup and temporary file with its comic's
    proof and whether the Delete offer may cover it. Reads only."""
    findings = []
    try:
        backups = _kept_backups(folder, {path.name for path, _ in entries})
    except OSError:
        raise HelpError('other', 'the recovery backup folder could not be read') from None
    for path, entry in entries:
        key, name, digest = str(path), path.name, None
        result = finished.get(key)
        kept = backups.get(name, [])
        temporary = temporary_path(path)
        temp_left = os.path.lexists(app.filesystem_path(temporary))
        if key in skipped:
            # A skipped or failed comic has its own wait record, so it is not a problem by itself. When it has
            # a kept backup or a temporary file it still takes the zip test: a damaged comic keeps them off the offer (M1).
            if (kept or temp_left) and app.filesystem_path(path).is_file() and not _zip_ok(path):
                findings.append(Finding('zip_failed', name, path))
        else:
            if not app.filesystem_path(path).is_file():
                findings.append(Finding('missing', name, folder))
            elif not _zip_ok(path):
                findings.append(Finding('zip_failed', name, path))
            else:
                info = app.filesystem_path(path).stat()
                if result is not None:
                    if result.get('output_signature') != [info.st_size, info.st_mtime_ns]:
                        findings.append(Finding('written_changed', name, path))
                else:
                    recorded = before_state(entry)
                    try:
                        digest = _digest(path)
                    except OSError:
                        raise HelpError('other', name + ' could not be read') from None
                    if digest != entry['sha256'] or (recorded is not None and (info.st_size, info.st_mtime_ns) != recorded[:2]):
                        findings.append(Finding('unwritten_changed', name, path))
        if not (kept or temp_left):
            continue
        basis = prove(path, entry, result, digest)
        if temp_left:
            # B2.1 and B2.3: only beside a comic proved untouched since before the write (never 'written'),
            # and only a regular file. Its contents are not read.
            findings.append(Finding('temp_left', name, temporary, basis, basis == 'original' and _plain_file(temporary)))
        for backup in kept:
            state = backup_state(backup, entry) if basis else None
            if state == 'same':
                findings.append(Finding('backup_left', name, backup, basis, True))
            else:
                findings.append(Finding('backup_left', name, backup, unproved='backup' if state == 'differs'
                                        else 'unread' if state == 'unread' else 'comic'))
    findings.sort(key=lambda f: (f.name.casefold(), FINDINGS.index(f.code), f.target.name.casefold()))
    return findings


def _unwritten(entries, finished, skipped):
    return [path for path, _ in entries if str(path) not in finished and str(path) not in skipped]


def _closable(findings):
    """Close and recheck folder is offered for a readable plan only when every finding is a comic that
    changed after the batch was planned (Sergei's 2a, 2026-10-16): nothing is damaged or left behind,
    and the next folder pass plans those comics again from what is on disk."""
    return bool(findings) and all(f.code == 'unwritten_changed' for f in findings)


def _deletable(findings):
    """Every finding a covered kept backup or app temporary file, and all of them on screen (A3, A8.4,
    Amendment 2 B2 conditions 1, 2, 3 and 5). The write-guard condition (B2.4) is the caller's."""
    return bool(findings) and len(findings) <= LIMIT and all(f.covered for f in findings)


def _writing(findings, entries):
    """B2.4 at the check: True while a writer holds the write guard of any comic on the line."""
    import kept_backups
    comics = {path.name: path for path, _ in entries}
    return any(kept_backups.writing(comics[name]) for name in {f.name for f in findings})


def _problems(ident, findings, entries, finished, skipped):
    """The section 4.2 result, with the Delete offer only when every finding is a proved kept backup of a
    proved comic or the app's own temporary file beside an untouched comic, all of them are on screen and
    no comic on the line is being written (Amendment A3, A8.4, Amendment 2 B2), or the Close and recheck
    offer when every finding is `unwritten_changed` (_closable)."""
    rows = []
    for finding in findings[:LIMIT]:
        row = {'id': _issue(ident, finding.code, finding.target), 'name': finding.name, 'finding': finding.code,
               'file': finding.target.name}
        if finding.code == 'backup_left':
            if finding.covered:
                row['basis'] = finding.basis
            else:
                row['unproved'] = finding.unproved
        rows.append(row)
    result = {'code': 'problems', 'total': len(findings), 'problems': rows}
    if _deletable(findings) and not _writing(findings, entries):
        result['offer'] = {'kind': 'delete_backup', 'unwritten': len(_unwritten(entries, finished, skipped)),
                           'backups': [{'id': r['id'], 'name': r['name'], 'basis': r['basis']}
                                       for r in rows if r['finding'] == 'backup_left'],
                           'temps': [{'id': r['id'], 'name': r['name'], 'file': r['file']}
                                     for r in rows if r['finding'] == 'temp_left']}
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


def _ids(value):
    return isinstance(value, list) and all(isinstance(i, str) and _ID.fullmatch(i) for i in value)


def _matched(ident, findings, backup_ids, temp_ids, fresh):
    """B9.1: the ids sent must name exactly the files this click's own check offers. An id issued for a
    file that is no longer one of this ticket's findings (deleted, or its backup folder replaced) is
    `file_gone`; any other difference, including no offer at all, is `changed`. Nothing is deleted yet."""
    present = {(f.code, os.path.normcase(str(f.target))) for f in findings}
    sent, unknown = set(), False
    for ids, code in ((backup_ids, 'backup_left'), (temp_ids, 'temp_left')):
        for sent_id in ids:
            found = _issued(sent_id, ident)
            if not found or found['code'] != code:
                unknown = True
                continue
            key = (code, os.path.normcase(found['target']))
            if key not in present:
                raise HelpError('file_gone', check=fresh())
            sent.add(key)
    if unknown or not _deletable(findings) or sent != present:
        raise HelpError('changed', check=fresh())


def delete_backups(ident, backup_ids, temp_ids=None):
    """Delete backup (and temporary file) and requeue (Amendment A8, Amendment 2 B9).

    The click checks the folder again and goes on only when the ids sent are exactly the files that check
    offers (B9.1). It then takes the write guard of every comic in the offer and keeps each until the end
    (one hold per comic over its proofs and deletes, B9.2), proves every comic, backup and temporary file
    again under the guards, and only then deletes, comic by comic in name order, the temporary file first
    and then the backups (B9.3). Last, the full check runs again and closes only if it is clean."""
    import kept_backups
    import library_lock
    temp_ids = [] if temp_ids is None else temp_ids
    if (not _ids(backup_ids) or not _ids(temp_ids) or not 0 < len(backup_ids) + len(temp_ids) <= LIMIT
            or len(set(backup_ids + temp_ids)) != len(backup_ids) + len(temp_ids)):
        raise HelpError('invalid', 'choose the offered backups')
    with _guarded(ident) as (ticket_path, item, folder):
        entries, finished, skipped = _plan(item, folder)
        comics = {path.name: (path, entry) for path, entry in entries}
        findings = _inspect(folder, entries, finished, skipped)
        _matched(ident, findings, backup_ids, temp_ids, lambda: _problems(ident, findings, entries, finished, skipped))
        names = sorted({f.name for f in findings}, key=lambda name: (name.casefold(), name))
        counts = {'backup_left': 0, 'temp_left': 0}

        def tally():
            return {'deleted': sum(counts.values()), 'total': len(findings),
                    'deleted_backups': counts['backup_left'], 'deleted_temps': counts['temp_left']}

        def stop(code=None):
            """A delete that cannot go on: before the first delete nothing changed, after it the counts."""
            if code and not sum(counts.values()):
                return HelpError(code) if code != 'changed' else _Refused(code)
            return HelpError('delete_failed', **tally())
        try:
            with ExitStack() as held:
                for name in names:
                    path = comics[name][0]
                    try:
                        held.enter_context(app.comic_write_guard(path))
                    except app.ArchiveChanged:
                        if kept_backups.writing(path):
                            raise HelpError('writing', **tally()) from None
                        raise HelpError('other', 'a comic could not be locked for the delete') from None
                for name in names:  # All proofs for all comics before the first delete (A8.5).
                    path, entry = comics[name]
                    mine = [f for f in findings if f.name == name]
                    if prove(path, entry, finished.get(str(path))) != mine[0].basis:
                        raise _Refused('changed')
                    for f in mine:
                        if f.code == 'temp_left':
                            _temporary_checked(f.target, path, folder)
                            continue
                        try:
                            kept_backups.checked(f.target)
                        except kept_backups.BackupError as exc:
                            raise _Refused('file_gone' if exc.code == 'not_found' else 'changed') from None
                        if not backup_proved(f.target, entry):
                            raise _Refused('changed')
                for name in names:
                    path = comics[name][0]
                    for f in sorted((f for f in findings if f.name == name),
                                    key=lambda f: (f.code != 'temp_left', f.target.name.casefold())):
                        try:
                            if f.code == 'temp_left':
                                _delete_temporary(f.target, path, folder)
                            else:
                                kept_backups.delete_held(f.target)
                        except FileNotFoundError:
                            continue  # Already gone at its own delete: done, not failed, not counted.
                        except _Refused as exc:
                            if exc.code == 'file_gone':
                                continue
                            raise stop('changed') from None
                        except kept_backups.BackupError as exc:
                            if exc.code == 'not_found':
                                continue
                            raise stop('changed') from None
                        except app.ArchiveChanged:
                            raise HelpError('writing', **tally()) from None
                        except library_lock.LibraryBusy:
                            raise stop('library_busy') from None
                        except Exception:
                            raise stop() from None
                        counts[f.code] += 1
        except _Refused as exc:
            raise HelpError(exc.code, check=_fresh(ident, item, folder)) from None  # The guards are released.
        deleted = tally()
        try:
            if _paused():
                raise HelpError('paused')
            result = _check(ident, ticket_path, _read_ticket(ticket_path), folder)
        except HelpError as exc:
            if exc.code == 'gone':
                raise
            raise HelpError('not_requeued', str(exc), reason='paused' if exc.code == 'paused' else 'other', **deleted) from None
        if result.get('ok'):
            return dict(result, deleted=deleted['deleted'], deleted_backups=deleted['deleted_backups'],
                        deleted_temps=deleted['deleted_temps'])
        raise HelpError('not_requeued', 'the check found problems', reason='problems', check=result, **deleted)


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
