"""Server-owned, single-use per-comic identity recovery plans.

No browser-supplied metadata is trusted. All mutations require the shared writer
archive guard, an unchanged full metadata snapshot and explicit confirmation.
"""
import hashlib
import json
import re
import secrets
import stat
import threading
import time
from pathlib import Path
from urllib.parse import urlparse
import app
import discovery_state
import provenance

IDENTITY = ('Series', 'Number', 'Year', 'Month', 'Day')
TTL = 600
_PLANS = {}
_MUTEX = threading.Lock()
WEB = re.compile(r'https?://(?:www\.)?comicvine(?:\.gamespot)?\.com/[^\s,;]*?4000-([1-9]\d{0,11})(?=/|[\s,;]|$)(?:/[^\s,;]*)?', re.I)
SEPARATORS = ' \t\r\n,;'  # What WEB accepts between links.
# Save outcomes (BackupLocation 2026-10-16 section 3; Futaba 0.2.3 m1 for the read-only case).
NOT_VERIFIED = 'The change was not verified. Check the file and retained recovery backup before trying again.'
NOT_VERIFIED_NO_BACKUP = 'The change was not verified. No recovery backup was made. Check the file before trying again.'
READ_ONLY = "The change was not saved because this comic file is read-only. The file was not changed. Turn off Read-only in the file's Properties, then try again."
SAVED = 'Change saved and verified.'
SAVED_BACKUP_KEPT = 'Change saved and verified. The recovery backup could not be deleted and was retained.'

class RecoveryError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def issue_id(value):
    if isinstance(value, bool):
        raise RecoveryError('invalid_link', 'Enter a ComicVine issue page link.')
    text = str(value).strip()
    if re.fullmatch(r'[1-9]\d{0,11}', text):
        return int(text)
    try:
        parsed = urlparse(text)
        port = parsed.port
        host = parsed.hostname
    except ValueError:
        raise RecoveryError('invalid_link', 'Enter a ComicVine issue page link.') from None
    if (parsed.scheme in ('http', 'https') and host in
            ('comicvine.gamespot.com', 'www.comicvine.gamespot.com', 'comicvine.com', 'www.comicvine.com')
            and not parsed.username and not parsed.password and not port
            and not parsed.query and not parsed.fragment):
        match = re.search(r'(?:^|/)4000-([1-9]\d{0,11})(?:/|$)', parsed.path)
        if match:
            return int(match[1])
    raise RecoveryError('invalid_link', 'Enter a ComicVine issue page link.')

def canonical(number):
    return 'https://comicvine.gamespot.com/issue/4000-' + str(issue_id(number)) + '/'

def snapshot(comic_id):
    row = app.comic(int(comic_id))
    root = app.live_root()
    import library_lock
    if not root or not library_lock.contains(library_lock.identity(root), library_lock.identity(row['path'])):
        raise RecoveryError('outside_library', 'Comic is not in the current library.')
    path = app.filesystem_path(row['path'])
    for component in (path, *path.parents):
        info = component.lstat()
        if component.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise RecoveryError('unavailable', 'Linked archive paths require review before recovery.')
    # Resolved containment includes parent-directory links; never traverse outside root.
    if path.is_symlink() or row['status'] == 'absent':
        raise RecoveryError('unavailable', 'This comic is unavailable for recovery.')
    stat = path.stat()
    if [stat.st_size, stat.st_mtime_ns] != [row['size'], row['mtime']]:
        raise RecoveryError('stale', 'This comic or its evidence changed. Review the updated values before saving.')
    metadata, status, error = app.read_metadata(path)
    if status == 'unsupported' or error:
        raise RecoveryError('unavailable', 'Only readable CBZ comics can be changed here.')
    with app.db() as con:
        discovery_state.initialize(con)
        found = con.execute('SELECT value FROM discovery_records WHERE path=?', (row['path'],)).fetchone()
    record = json.loads(found[0]) if found else {}
    import problems
    problem = problems.classify(record, [row['size'], row['mtime']])
    return row, metadata, record, problem

def provider(number):
    number = issue_id(number)
    resource = 'issue/4000-' + str(number)
    issue = app.api(resource)
    if not isinstance(issue, dict) or str(issue.get('id')) != str(number):
        raise RecoveryError('insufficient', 'The returned issue identity cannot be checked.')
    volume = issue.get('volume')
    image = issue.get('image')
    if (not isinstance(volume, dict) or not isinstance(volume.get('name'), str)
            or not isinstance(issue.get('issue_number'), str)
            or (image is not None and not isinstance(image, dict))):
        raise RecoveryError('insufficient', 'The returned issue identity cannot be checked.')
    for key in ('id', 'start_year'):
        value = volume.get(key)
        if value is not None and (isinstance(value, bool) or not isinstance(value, (str, int)) or not re.fullmatch(r'[1-9]\d{0,11}', str(value))):
            raise RecoveryError('insufficient', 'The returned volume evidence cannot be checked.')
    cover = (image or {}).get('small_url')
    if cover == '':
        cover = None
    if cover is not None:
        if not isinstance(cover, str):
            raise RecoveryError('insufficient', 'The returned cover evidence cannot be checked.')
        try:
            cover_url = urlparse(cover)
            valid_cover = (cover_url.scheme == 'https' and bool(cover_url.hostname)
                           and not cover_url.username and not cover_url.password and not cover_url.port)
        except ValueError:
            valid_cover = False
        if not valid_cover:
            raise RecoveryError('insufficient', 'The returned cover evidence cannot be checked.')
    fields = {'Series': str(volume.get('name') or ''), 'Number': str(issue.get('issue_number') or '')}
    date = issue.get('cover_date')
    if date is None:
        date = ''
    if not isinstance(date, str):
        raise RecoveryError('insufficient', 'The returned issue date cannot be checked.')
    verified_date = None
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', date):
        import datetime
        try:
            valid = datetime.date.fromisoformat(date)
        except ValueError:
            pass
        else:
            verified_date = date
            fields.update(Year=str(valid.year), Month=str(valid.month), Day=str(valid.day))
    # app.api stores exactly this key; report the actual cache time, never now.
    with app.db() as con:
        cached = con.execute('SELECT fetched FROM cache WHERE key=?', (resource + '?format=json',)).fetchone()
    checked = float(cached[0]) if cached else 0
    if not checked or checked <= time.time() - 30 * 86400:
        raise RecoveryError('stale_provider', 'This issue has no current verified evidence. Check it again.')
    source = {'issue_id': number, 'volume_id': volume.get('id'), 'volume_name': volume.get('name'),
              'volume_start_year': volume.get('start_year'), 'issue_date': verified_date,
              'url': canonical(number), 'cover': cover,
              'checked_at': checked, 'saved_result': time.time() - checked > 5, 'fields': fields}
    source['revision'] = digest({'issue': issue, 'checked_at': checked})
    return source

def provider_failure(exc):
    if isinstance(exc, RecoveryError):
        return {'code': exc.code, 'message': str(exc)}
    from provider_wait import ProviderDeferred
    if isinstance(exc, app.ComicVineNotFound):
        return {'code': 'not_found', 'message': 'ComicVine could not find this issue. Check the link or search by series.'}
    if isinstance(exc, ProviderDeferred):
        return {'code': getattr(exc, 'cause', 'unavailable'), 'message': 'ComicVine cannot check this issue now. Check provider status before trying again.'}
    return {'code': getattr(exc, 'code', 'unavailable'), 'message': 'This issue could not be checked. Try again when ComicVine is available.'}

def evidence(comic_id, candidate=None):
    row, old, record, problem = snapshot(comic_id)
    result = {'comic': row['id'], 'path': row['path'], 'signature': [row['size'], row['mtime']],
              'record_revision': digest(record), 'embedded': {key: old.get(key, '') for key in IDENTITY + ('Web',)},
              'filename': dict(zip(('Series', 'Number', 'Year'), app.parse_name(row['path']))),
              'problem': problem, 'provider': None, 'provider_error': None}
    number = candidate or (problem or {}).get('issue_id')
    if number:
        try:
            result['provider'] = provider(number)
        except Exception as exc:
            result['provider_error'] = provider_failure(exc)
    import pause_control
    result['paused'] = pause_control.requested()
    return result

def plan_fields(old, action, source=None, target=None):
    web = old.get('Web', '')
    matches = list(WEB.finditer(web))
    if target is not None:
        matches = [match for match in matches if match.group(1) == str(target)]
    if len(matches) != 1:
        raise RecoveryError('ambiguous_link', 'The exact ComicVine link to change cannot be identified. Review the file first.')
    match = matches[0]
    if action == 'remove_link':
        # One separator goes with the link: 'a; X; b' becomes 'a; b', not 'a; ; b' (Futaba 0.2.3 m2).
        before, after = web[:match.start()], web[match.end():]
        if not after.strip(SEPARATORS):
            return {'Web': before.rstrip(SEPARATORS)}
        return {'Web': (before if before.strip(SEPARATORS) else '') + after.lstrip(SEPARATORS)}
    if action not in ('keep_file', 'use_provider') or not source:
        raise RecoveryError('invalid_action', 'Choose an available recovery option.')
    fields = source['fields']
    if not fields.get('Series') or not fields.get('Number'):
        raise RecoveryError('insufficient', 'Series and issue number cannot be checked for this issue.')
    import automatic
    if action == 'keep_file' and not automatic.identity_matches(old, {'volume': {'name': fields['Series']}, 'issue_number': fields['Number']}):
        raise RecoveryError('conflict', 'This issue still differs from the file. Choose another issue, or review the ComicVine identity option.')
    if action == 'keep_file' and old.get('Year') and fields.get('Year') and provenance.disagrees('Year', old['Year'], fields['Year']):
        raise RecoveryError('conflict', 'This issue still differs from the file. Choose another issue, or review the ComicVine identity option.')
    changed = {}
    replacement = web[:match.start()] + source['url'] + web[match.end():]
    if replacement != web:
        changed['Web'] = replacement
    if action == 'use_provider':
        for field in IDENTITY:
            if field in fields and provenance.disagrees(field, old.get(field, ''), fields[field]):
                changed[field] = fields[field]
    if not changed:
        raise RecoveryError('no_change', 'These values already agree. Nothing needs to be changed.')
    return changed

def preview(comic_id, action, candidate=None):
    if action not in ('remove_link', 'keep_file', 'use_provider'):
        raise RecoveryError('invalid_action', 'Choose an available recovery option.')
    row, old, record, problem = snapshot(comic_id)
    if not problem or problem['code'] not in ('dead_link', 'conflict'):
        raise RecoveryError('stale', 'This comic no longer has this link problem. Refresh its status.')
    source = provider(candidate or problem.get('issue_id')) if action != 'remove_link' else None
    fields = plan_fields(old, action, source, problem.get('issue_id'))
    import pause_control
    if pause_control.requested():
        raise RecoveryError('paused', 'Processing is paused. Resume processing before saving a change.')
    token = secrets.token_urlsafe(32)
    stored = {'comic': row['id'], 'action': action, 'row': row, 'old': old, 'record_revision': digest(record),
              'source': source, 'fields': fields, 'created': time.time()}
    with _MUTEX:
        expired = [key for key, value in _PLANS.items() if time.time() - value['created'] > TTL]
        for key in expired:
            del _PLANS[key]
        if len(_PLANS) >= 256:
            raise RecoveryError('busy', 'Too many pending reviews. Close an old review and try again.')
        _PLANS[token] = stored
    return {'token': token, 'action': action, 'changes': [{'field': key, 'before': old.get(key, ''), 'after': value}
            for key, value in fields.items()], 'source': source, 'filename': Path(row['path']).name}

def archive_sha256(path):
    with app.filesystem_path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()

def unchanged_read_only(path, original_sha256):
    """True only when the comic file is read-only and still byte-identical to before the save,
    so 'not changed' is measured, not assumed (Futaba 0.2.3 m1)."""
    try:
        info = app.filesystem_path(path).stat()
        return bool(getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_READONLY) and archive_sha256(path) == original_sha256
    except Exception:
        return False

def kept(path, backup, reason):
    """Record why a backup stays and issue the page's id for it (BackupLocation Amendment A7.3)."""
    import kept_backups
    kept_backups.record(path, backup, reason)
    return kept_backups.issue(backup)

def discard_verified_backup(path, backup, original_sha256):
    """Remove a saved-and-verified change's backup (Sergei 2026-10-16, option B).

    app.remove_verified_backup deletes only that file, only from the comic's own backup
    folder and only when it still holds the original's SHA-256. Any refusal keeps the
    backup; the change itself stays saved and verified. Returns True once removed."""
    try:
        app.remove_verified_backup(path, backup, original_sha256)
    except Exception:
        return False
    return True

def confirm(token, confirmation):
    if confirmation is not True or not isinstance(token, str):
        raise RecoveryError('confirmation', 'Review and explicitly confirm this change.')
    with _MUTEX:
        plan = _PLANS.pop(token, None)
    if not plan or time.time() - plan['created'] > TTL:
        raise RecoveryError('stale', 'This comic or its evidence changed. Review the updated values before saving.')
    import pause_control
    attempt = {}
    # Primary integrates this cross-process guard into every app.write_metadata call.
    with app.LOCK, app.comic_write_guard(plan['row']['path']):
        if pause_control.requested():
            raise RecoveryError('paused', 'Processing is paused. Resume processing before saving a change.')
        row, old, record, problem = snapshot(plan['comic'])
        if ([row['size'], row['mtime']] != [plan['row']['size'], plan['row']['mtime']]
                or old != plan['old'] or digest(record) != plan['record_revision']):
            raise RecoveryError('stale', 'This comic or its evidence changed. Review the updated values before saving.')
        source = plan['source']
        if source and provider(source['issue_id'])['revision'] != source['revision']:
            raise RecoveryError('stale', 'This comic or its evidence changed. Review the updated values before saving.')
        # Under the writer guard, before the backup copy: what the backup must equal to be removed.
        original_sha256 = archive_sha256(row['path'])
        try:
            backup = app.write_metadata(row, plan['fields'], overwrite_fields=set(plan['fields']), expected=old,
                expected_snapshot=old, verify_readback=True, attempt=attempt,
                history_source='recovery:' + plan['action'] + ':' + str((source or {}).get('issue_id') or (problem or {}).get('issue_id') or ''),
                writer='manual', guard_held=True)
            after, _, _ = app.read_metadata(row['path'])
            expected = dict(old, **plan['fields'])
            if after != expected:
                raise RecoveryError('verification', 'The resulting metadata did not match the approved fields. Recovery backup retained.')
        except Exception:
            # Never claim unchanged after the writer may have replaced the archive: only a
            # read-only file whose bytes still match is reported as not changed.
            made = attempt.get('backup')
            result = {'ok': False, 'verified': False, 'backup': made,
                      'message': READ_ONLY if unchanged_read_only(row['path'], original_sha256) else NOT_VERIFIED if made else NOT_VERIFIED_NO_BACKUP}
            if made:
                result['backup_id'] = kept(row['path'], made, 'save_not_verified')
            return result
        # Saved and the full metadata verified: the backup is a redundant copy, as for
        # automatic writes and /api/apply. Only this path removes it; every failure above keeps it.
        removed = discard_verified_backup(row['path'], backup, original_sha256)
        backup_id = None if removed else kept(row['path'], backup, 'delete_refused')
        # Old signature-bound problems clear naturally. Do not erase a newer worker record.
        updated = app.comic(plan['comic'])
        with app.db() as con:
            discovery_state.initialize(con)
            found = con.execute('SELECT value FROM discovery_records WHERE path=?', (row['path'],)).fetchone()
            current = json.loads(found[0]) if found else {}
            import problems
            problem = problems.classify(current, [updated['size'], updated['mtime']])
        result = {'ok': True, 'verified': True, 'backup': backup, 'backup_retained': not removed,
                  'backup_removed_after_verification': removed,
                  'metadata': after, 'problem': problem, 'message': SAVED if removed else SAVED_BACKUP_KEPT}
        if backup_id:
            result['backup_id'] = backup_id
        return result
