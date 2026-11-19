"""Atomic, durable JSON replacement with short Windows reader-lock retries.

save() writes the new file beside the old one, puts its bytes on the disk (flush and fsync), and only then renames
it over the old one with MOVEFILE_WRITE_THROUGH, as setup_state's save already did. A stop at any moment leaves the
complete old file or the complete new one. Before 2026-11-17 the rename could reach the disk before the bytes: after
the unclean stop of 2026-11-13, progress.json, folders.json and browser-search.json came back full size and all
zeros (Docs/ComicsMetaOrganizer_ZeroFillDiagnosis_2026-11-17.md). replace_durably() does the same for a finished file
written elsewhere (the comic writer's temporary archive, 0.6.8); flush_file() and flush_directory() put an existing
file's bytes, or a folder's entries, on the disk.

The state files a lost record stops the app for (progress.json, folders.json, browser-search.json) are saved with
keep_previous: the record being replaced, if it reads, is kept as <name>.bak. read_json() puts that copy back when the
file cannot be read, instead of waiting for someone to remove the file (0.6.2's behaviour, kept for a file with no
readable copy).

Any process may be the one that reads a damaged file first: the dashboard's poll as well as the worker that owns the
file. Putting the copy back and every keep_previous save of the same file therefore run one at a time, across threads
and processes (exclusive()). Before 0.6.6 the re-check and the put-back were apart (the .unreadable evidence write sat
between them), so a worker that restored and saved its next step in that window had the step overwritten by the
older copy (code review v0.6.4 N1).
"""
import contextlib
import ctypes
import hashlib
import json
import os
import sys
import threading
import time
import uuid
from pathlib import Path

MOVEFILE_REPLACE_EXISTING = 0x1
MOVEFILE_WRITE_THROUGH = 0x8
BACKUP = '.bak'             # The previous good record, beside the file.
UNREADABLE = '.unreadable'  # The last file read_json() could not read, kept as evidence when it put the copy back.
SAVE_LOCK_WAIT = 30.0       # Seconds a keep_previous save or a restore waits for another holder of the file's lock.
WAIT_OBJECT_0, WAIT_ABANDONED, WAIT_TIMEOUT = 0x0, 0x80, 0x102
GENERIC_WRITE, SHARE_ALL, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS = 0x40000000, 0x7, 3, 0x02000000
INVALID_HANDLE = (1 << (8 * ctypes.sizeof(ctypes.c_void_p))) - 1
_move_file = None
_flush_api = None
_mutex_api = None
_local_locks = {}
_local_locks_guard = threading.Lock()


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


def replace_durably(source, destination):
    """Rename a finished file over another so that both the bytes and the rename are on the disk when this returns:
    flush_file(source), then the write-through rename. Code review v0.6.7 Q1: a comic rewritten through a temporary
    archive and os.replace() was verified from the OS cache only, then its backup was deleted; a power loss in that
    window could keep the rename and the deletion (journaled metadata) but not the new archive's data."""
    flush_file(source)
    _move(source, destination)


def _open_handle(path, directory):
    """A Windows handle with write access (FlushFileBuffers needs it) that shares read, write and delete, so it never
    blocks a reader such as YACReader. Folders need FILE_FLAG_BACKUP_SEMANTICS."""
    global _flush_api
    if _flush_api is None:
        from ctypes import wintypes
        api = ctypes.WinDLL('kernel32', use_last_error=True)
        api.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                    wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        api.CreateFileW.restype = wintypes.HANDLE
        api.FlushFileBuffers.argtypes, api.FlushFileBuffers.restype = [wintypes.HANDLE], wintypes.BOOL
        api.CloseHandle.argtypes, api.CloseHandle.restype = [wintypes.HANDLE], wintypes.BOOL
        _flush_api = api
    handle = _flush_api.CreateFileW(str(path), GENERIC_WRITE, SHARE_ALL, None, OPEN_EXISTING,
                                    FILE_FLAG_BACKUP_SEMANTICS if directory else 0, None)
    if handle is None or handle == INVALID_HANDLE:
        raise ctypes.WinError(ctypes.get_last_error())
    return handle


def flush_file(path):
    """Put a file's data and size on the disk (os.fsync: FlushFileBuffers on Windows). Raises OSError when it cannot."""
    if os.name != 'nt':
        descriptor = os.open(path, os.O_RDONLY)
    else:
        import msvcrt
        handle = _open_handle(path, False)
        try:
            descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        except BaseException:
            _flush_api.CloseHandle(handle)
            raise
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def flush_directory(path):
    """Put a folder's entries on the disk: a rename into it, or a name removed from it. Raises OSError when it cannot."""
    if os.name != 'nt':
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return
    handle = _open_handle(path, True)
    try:
        if not _flush_api.FlushFileBuffers(handle):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        _flush_api.CloseHandle(handle)


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


def _lock_name(path):
    """One name per file whatever its spelling (letter case, short names, junctions): its real path, case-folded."""
    try:
        real = os.path.realpath(path)
    except OSError:
        real = os.path.abspath(path)
    return 'Local\\ComicMetadata.save.' + hashlib.sha256(os.path.normcase(real).encode('utf-8')).hexdigest()


def _mutexes():
    global _mutex_api
    if _mutex_api is None:
        from ctypes import wintypes
        api = ctypes.WinDLL('kernel32', use_last_error=True)
        api.CreateMutexW.argtypes, api.CreateMutexW.restype = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR], wintypes.HANDLE
        api.WaitForSingleObject.argtypes, api.WaitForSingleObject.restype = [wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD
        api.ReleaseMutex.argtypes, api.ReleaseMutex.restype = [wintypes.HANDLE], wintypes.BOOL
        api.CloseHandle.argtypes, api.CloseHandle.restype = [wintypes.HANDLE], wintypes.BOOL
        _mutex_api = api
    return _mutex_api


@contextlib.contextmanager
def exclusive(path):
    """Hold the save lock of one state file: keep_previous saves and read_json's restore of that file run one at a
    time across threads and processes. A named Windows mutex, so nothing is left on disk and a holder that dies
    releases it (an abandoned mutex is acquired normally). TimeoutError after SAVE_LOCK_WAIT seconds; nothing written."""
    name = _lock_name(path)
    if os.name != 'nt':  # The app runs on Windows; elsewhere one process's threads are kept apart.
        with _local_locks_guard:
            lock = _local_locks.setdefault(name, threading.Lock())
        if not lock.acquire(timeout=SAVE_LOCK_WAIT):
            raise TimeoutError('Another save of ' + Path(path).name + ' did not finish.')
        try:
            yield
        finally:
            lock.release()
        return
    api = _mutexes()
    handle = api.CreateMutexW(None, False, name)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        result = api.WaitForSingleObject(handle, int(SAVE_LOCK_WAIT * 1000))
        if result == WAIT_TIMEOUT:
            raise TimeoutError('Another save of ' + Path(path).name + ' did not finish.')
        if result not in (WAIT_OBJECT_0, WAIT_ABANDONED):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            yield
        finally:
            api.ReleaseMutex(handle)
    finally:
        api.CloseHandle(handle)


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
    if not keep_previous:
        _write(path, data)
        return
    with exclusive(path):  # Never inside another process's restore of this file (read_json).
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
    neither the file nor its copy reads: nothing is guessed.

    The re-check, the evidence and the put-back hold the file's save lock (exclusive), so no keep_previous save of
    the file lands between them: whoever reads the damage first restores it, and every other reader finds it good."""
    path = Path(path)
    good, value = _parse(_read_bytes(path), valid)
    if good:
        return value
    with exclusive(path):
        raw = _read_bytes(path)  # Another process may have put it back, or saved a new record, meanwhile.
        good, value = _parse(raw, valid)
        if good:
            return value
        try:
            saved = _read_bytes(backup(path))
        except FileNotFoundError:
            saved = None
        good, previous = _parse(saved, valid) if saved is not None else (False, None)
        if not good:
            raise ValueError('Saved ' + path.name + ' cannot be read and has no readable previous copy.')
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
