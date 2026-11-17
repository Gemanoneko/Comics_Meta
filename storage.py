"""Atomic, durable JSON replacement with short Windows reader-lock retries.

save() writes the new file beside the old one, puts its bytes on the disk (flush and fsync), and only then renames
it over the old one with MOVEFILE_WRITE_THROUGH, as setup_state's save already did. A stop at any moment leaves the
complete old file or the complete new one. Before 2026-11-17 the rename could reach the disk before the bytes: after
the unclean stop of 2026-11-13, progress.json, folders.json and browser-search.json came back full size and all
zeros (Docs/ComicsMetaOrganizer_ZeroFillDiagnosis_2026-11-17.md).

The state files a lost record stops the app for (progress.json, folders.json, browser-search.json) are saved with
keep_previous: the record being replaced, if it reads, is kept as <name>.bak. read_json() puts that copy back when the
file cannot be read, instead of waiting for someone to remove the file (0.6.2's behaviour, kept for a file with no
readable copy).
"""
import ctypes
import json
import os
import sys
import time
import uuid
from pathlib import Path

MOVEFILE_REPLACE_EXISTING = 0x1
MOVEFILE_WRITE_THROUGH = 0x8
BACKUP = '.bak'             # The previous good record, beside the file.
UNREADABLE = '.unreadable'  # The last file read_json() could not read, kept as evidence when it put the copy back.
_move_file = None


def _move(source, destination):
    """Rename source over destination. On Windows the rename reaches the disk before this returns."""
    global _move_file
    if os.name != 'nt':
        os.replace(source, destination)
        return
    if _move_file is None:
        from ctypes import wintypes
        move = ctypes.WinDLL('kernel32', use_last_error=True).MoveFileExW
        move.argtypes, move.restype = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD], wintypes.BOOL
        _move_file = move
    if not _move_file(str(source), str(destination), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH):
        raise ctypes.WinError(ctypes.get_last_error())  # Access denied or a sharing violation is a PermissionError.


def _write(path, data):
    """Replace path with data (bytes), durably."""
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with open(temporary, 'xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(20):
            try:
                _move(temporary, path)
                return
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(.05)
    finally:
        if temporary.exists():
            temporary.unlink()


def is_object(value):
    return isinstance(value, dict)


def backup(path):
    path = Path(path)
    return path.with_name(path.name + BACKUP)


def _parse(raw, valid):
    """(True, record) when raw is a JSON record valid() accepts, else (False, None). All zero bytes, a cut-off file
    or a record of the wrong shape all read as (False, None)."""
    try:
        value = json.loads(raw.decode('utf-8'))
    except (ValueError, UnicodeError):
        return False, None
    return (True, value) if valid(value) else (False, None)


def save(path, value, *, keep_previous=False, valid=is_object):
    path = Path(path)
    # Text-mode line ends, as Path.write_text wrote them before.
    data = json.dumps(value, ensure_ascii=False, indent=2).replace('\n', os.linesep).encode('utf-8')
    if keep_previous:
        try:
            current = _read_bytes(path)
        except FileNotFoundError:
            current = None
        if current is not None and _parse(current, valid)[0]:
            _write(backup(path), current)  # A file that does not read never replaces the good copy.
    _write(path, data)


def read_json(path, *, valid=is_object):
    """The record save(path, ..., keep_previous=True) wrote.

    A file that cannot be read (all zeros, cut off, not JSON, or not the record valid() expects) is replaced by its
    previous good copy: the unreadable file is kept as <name>.unreadable, the copy is put back, and one line is
    logged. Raises FileNotFoundError when the file is missing (a missing file is never restored) and ValueError when
    neither the file nor its copy reads: nothing is guessed."""
    path = Path(path)
    good, value = _parse(_read_bytes(path), valid)
    if good:
        return value
    try:
        saved = _read_bytes(backup(path))
    except FileNotFoundError:
        saved = None
    good, previous = _parse(saved, valid) if saved is not None else (False, None)
    if not good:
        raise ValueError('Saved ' + path.name + ' cannot be read and has no readable previous copy.')
    raw = _read_bytes(path)  # Another process may have put it back, or saved a new record, meanwhile.
    good, value = _parse(raw, valid)
    if good:
        return value
    _write(path.with_name(path.name + UNREADABLE), raw)
    _write(path, saved)
    print('Saved ' + path.name + ' could not be read; its previous copy was put back. The unreadable file was kept '
          'as ' + path.name + UNREADABLE + '.', file=sys.stderr, flush=True)
    return previous


def _read_bytes(path):
    for attempt in range(20):
        try:
            return Path(path).read_bytes()
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(.05)


def read_text(path):
    """Text of a status, heartbeat or lease file that save() may be replacing right now.

    While the replace runs, Windows briefly refuses a plain open with
    PermissionError (errno 13), in the writer's own process too. Retried with
    the writer's bound; a refusal that outlasts it is raised. Other errors,
    including a missing file, are raised at once.
    """
    for attempt in range(20):
        try:
            return Path(path).read_text(encoding='utf-8')
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(.05)
