"""Kept recovery backups: list them, show one in File Explorer, delete them.

UXSpec BackupLocation 2026-10-16 and its Amendment (Sergei: deletion is permanent; Delete all
includes backups from saves that were not verified).

The page never names a path. Each backup it sees carries an opaque id issued here, by the list
or by the save outcome that kept it. Every action resolves the id to the path this process
issued it for and checks that file again on disk: a regular `<comic>.<digits>.bak` (the name
app.write_metadata gives it) inside a `.comic-metadata-backups` folder, inside the configured
library once links are resolved, with no link or reparse point on the file or its folder.
"""
import hashlib
import hmac
import os
import re
import secrets
import stat
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import app

FOLDER = '.comic-metadata-backups'
NAME = re.compile(r'(.+)\.([0-9]{1,20})\.bak')
LIMIT = 500  # Newest listed; the page says when there are more (Amendment A3).
REASONS = ('save_not_verified', 'delete_refused', 'not_saved')  # not_saved: read-only file, proved unchanged.
_SECRET = secrets.token_bytes(32)
_ID = re.compile(r'[0-9a-f]{32}')
_IDS = OrderedDict()  # id -> the backup path it was issued for
_IDS_LOCK = threading.Lock()
_REPARSE = 0x400


class BackupError(ValueError):
    """One code per row of the spec's error tables."""
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def display(path):
    """The path as Explorer's address bar shows it: no \\\\?\\ prefix."""
    text = os.fspath(path)
    if text.startswith('\\\\?\\UNC\\'):
        return '\\\\' + text[8:]
    if text.startswith('\\\\?\\'):
        return text[4:]
    return text


def issue(path):
    """The opaque id the page sends back for this backup. The same backup keeps its id."""
    import library_lock
    key = library_lock.identity(path)
    ident = hmac.new(_SECRET, key.encode('utf-8', 'surrogatepass'), hashlib.sha256).hexdigest()[:32]
    with _IDS_LOCK:
        _IDS[ident] = display(path)
        _IDS.move_to_end(ident)
        while len(_IDS) > 4 * LIMIT:
            _IDS.popitem(last=False)
    return ident


def resolve(ident):
    if not isinstance(ident, str) or not _ID.fullmatch(ident):
        raise BackupError('not_found')
    with _IDS_LOCK:
        path = _IDS.get(ident)
    if path is None:
        raise BackupError('not_found')
    return path


def _table(con):
    con.execute('CREATE TABLE IF NOT EXISTS kept_backups(backup TEXT PRIMARY KEY, path TEXT, reason TEXT, created REAL)')


def record(path, backup, reason):
    """Why a backup was kept, stored when it is kept (Amendment A7.3). A scan alone cannot
    know it. Never raises: a backup without a record lists as Reason not recorded."""
    try:
        import library_lock
        with app.db() as con:
            _table(con)
            con.execute('INSERT OR REPLACE INTO kept_backups VALUES(?,?,?,?)',
                        (library_lock.identity(backup), str(path), reason, time.time()))
    except Exception:
        pass


def _forget(path):
    try:
        import library_lock
        with app.db() as con:
            _table(con)
            con.execute('DELETE FROM kept_backups WHERE backup=?', (library_lock.identity(path),))
    except Exception:
        pass


def checked(path):
    """(backup, comic) when `path` is a backup this app keeps for a comic in the configured
    library; BackupError otherwise. Containment is checked on the resolved path."""
    import library_lock
    root = app.live_root()
    if not root:
        raise BackupError('refused')
    path = app.filesystem_path(display(path))
    match = NAME.fullmatch(path.name)
    folder = path.parent
    if not match or folder.name != FOLDER:
        raise BackupError('refused')
    if not library_lock.contains(library_lock.identity(root), library_lock.identity(path)):
        raise BackupError('refused')
    if not folder.parent.is_dir():
        raise BackupError('folder_unavailable')
    for item, directory in ((folder, True), (path, False)):
        try:
            info = item.lstat()
        except FileNotFoundError:
            raise BackupError('not_found') from None
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & _REPARSE:
            raise BackupError('refused')
        if directory and not stat.S_ISDIR(info.st_mode):
            raise BackupError('not_found')
        if not directory and not stat.S_ISREG(info.st_mode):
            raise BackupError('refused')
    return path, folder.parent / match[1]


def writing(comic):
    """True while a metadata writer holds this comic's write guard (Amendment A7.4)."""
    import file_lock
    try:
        fd = file_lock.open_lock(app.write_lock_path(comic), create=False)
    except OSError:
        return False  # Never locked, so nobody holds it.
    try:
        if not file_lock.try_lock(fd):
            return True
        file_lock.unlock(fd)
        return False
    finally:
        os.close(fd)


def _backups_in(folder):
    directory = app.filesystem_path(folder) / FOLDER
    try:
        info = directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or getattr(info, 'st_file_attributes', 0) & _REPARSE:
            return []
        found = []
        with os.scandir(directory) as entries:
            for entry in entries:
                match = NAME.fullmatch(entry.name)
                if not match:
                    continue
                try:
                    entry_info = entry.stat(follow_symlinks=False)
                except OSError:
                    continue
                if stat.S_ISREG(entry_info.st_mode) and not getattr(entry_info, 'st_file_attributes', 0) & _REPARSE:
                    found.append((int(match[2]), entry.name, directory / entry.name, match[1], entry_info.st_size))
        return found
    except OSError:
        return []


def listing():
    """Kept backups in the configured library, newest first, at most LIMIT.

    Backups only ever sit in the folder of a comic the app wrote, so the catalog's comic
    folders are the ones checked; the library itself is not walked. Runs on request only,
    never on the 2-second poll."""
    import library_lock
    root = app.live_root()
    if not root:
        return {'items': [], 'count': 0, 'bytes': 0, 'bounded': False}
    if not os.path.isdir(root):
        raise BackupError('folder_unavailable')
    library = library_lock.identity(root)
    scope, params = app.scope_filter(root)
    with app.db() as con:
        _table(con)
        folders = sorted({os.path.dirname(row[0]) for row in con.execute('SELECT path FROM comics WHERE ' + scope, params)})
        reasons = {row[0]: row[1] for row in con.execute('SELECT backup, reason FROM kept_backups')}
    with ThreadPoolExecutor(8) as pool:  # A network library answers each folder check slowly.
        found = [item for group in pool.map(_backups_in, folders) for item in group]
    found.sort(key=lambda item: (-item[0], item[1]))
    items, bounded = [], False
    for created, _, path, comic_name, size in found:
        if not library_lock.contains(library, library_lock.identity(path)):
            continue
        if writing(path.parent.parent / comic_name):
            continue  # Belongs to a write still in progress: neither listed nor deletable.
        if len(items) == LIMIT:
            bounded = True
            break
        reason = reasons.get(library_lock.identity(path))
        items.append({'id': issue(path), 'name': comic_name, 'folder': display(path.parent.parent),
                      'size': size, 'created': created / 1e9, 'reason': reason if reason in REASONS else None})
    return {'items': items, 'count': len(items), 'bytes': sum(item['size'] for item in items), 'bounded': bounded}


_shell = None


def _select(path):
    """Explorer's own Show in folder: a window on the folder with this file selected.
    In-process shell call, so no child process is started."""
    global _shell
    import ctypes
    from ctypes import wintypes
    if _shell is None:
        shell = ctypes.WinDLL('shell32')
        shell.ILCreateFromPathW.restype = ctypes.c_void_p
        shell.ILCreateFromPathW.argtypes = [wintypes.LPCWSTR]
        shell.ILFree.argtypes = [ctypes.c_void_p]
        shell.ILFree.restype = None
        shell.SHOpenFolderAndSelectItems.argtypes = [ctypes.c_void_p, wintypes.UINT, ctypes.c_void_p, wintypes.DWORD]
        shell.SHOpenFolderAndSelectItems.restype = ctypes.HRESULT  # A failure raises OSError.
        _shell = shell
    com = ctypes.WinDLL('ole32')
    started = com.CoInitializeEx(None, 0x2)  # Apartment-threaded, this request thread only.
    try:
        item = _shell.ILCreateFromPathW(path)
        if not item:
            raise OSError('File Explorer cannot address this file.')
        try:
            _shell.SHOpenFolderAndSelectItems(item, 0, None, 0)
        finally:
            _shell.ILFree(item)
    finally:
        if started in (0, 1):
            com.CoUninitialize()


def _open_folder(path):
    os.startfile(path)


def reveal(ident):
    """Show the backup selected in File Explorer. Nothing is written."""
    path, _ = checked(resolve(ident))
    try:
        _select(display(path))
    except OSError:
        # A path longer than MAX_PATH may not select (spec section 8.3): open its folder instead.
        try:
            _open_folder(display(path.parent))
        except OSError:
            raise BackupError('failed') from None
    return {'ok': True}


def _unlink(path):
    try:
        path.unlink()
    except PermissionError:
        # A backup of a read-only comic is read-only too (shutil.copy2 keeps the attribute).
        if not getattr(path.lstat(), 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_READONLY:
            raise
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
        path.unlink()


def delete_one(path, before_unlink=None):
    """Permanently delete one backup under its comic's write guard; returns the bytes freed.

    before_unlink(comic), when given, runs under the guard right before the delete; whatever it
    raises stops the delete and propagates (FolderHelpActions Amendment A8.2 proves the comic there)."""
    import library_lock
    path, comic = checked(path)
    library_lock.require(path)  # Raises before any change if another copy owns the library.
    with app.comic_write_guard(comic):
        path, comic = checked(path)  # Again, under the guard.
        if before_unlink is not None:
            before_unlink(comic)
        size = path.lstat().st_size
        _unlink(path)
    _forget(path)
    try:
        path.parent.rmdir()  # Only when empty, as the verified-backup cleanup does.
    except OSError:
        pass
    return size


def delete(idents):
    """Permanently delete exactly these listed backups, each under its comic's write guard."""
    deleted, failed, freed = [], [], 0
    for ident in idents:
        try:
            freed += delete_one(resolve(ident))
            deleted.append(ident)
        except BackupError as exc:
            failed.append({'id': ident, 'code': exc.code})
        except app.ArchiveChanged:
            failed.append({'id': ident, 'code': 'writing'})
        except PermissionError:
            failed.append({'id': ident, 'code': 'in_use'})
        except FileNotFoundError:
            failed.append({'id': ident, 'code': 'not_found'})
        except Exception:
            failed.append({'id': ident, 'code': 'failed'})
    return {'deleted': deleted, 'failed': failed, 'freed': freed}
