"""Local first-run save with one atomic config/credential-generation commit."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sqlite3
import threading
import uuid
import app
import credential_store
import file_lock
import library_lock

_mutex = threading.Lock()


class SetupError(Exception):
    def __init__(self, code, field='library'):
        self.code, self.field = code, field
        super().__init__(code)  # Never include a path, key, OS error or traceback in UI copy.


def _folder(value):
    if not isinstance(value, str) or not value.strip():
        raise SetupError('folder_required')
    value = value.strip()
    if any(char in value for char in '\0\r\n'):
        raise SetupError('folder_invalid')
    path = Path(value)
    if not path.is_absolute():
        raise SetupError('folder_invalid')
    try:
        if not path.is_dir():
            raise SetupError('folder_missing')
        # Local readability only; no test writes and no archive/provider inspection.
        with os.scandir(path) as entries:
            next(entries, None)
        return str(path.resolve(strict=True))
    except PermissionError:
        raise SetupError('folder_unreadable') from None
    except FileNotFoundError:
        raise SetupError('folder_missing') from None
    except OSError:
        raise SetupError('validation_failed') from None


def _config():
    try:
        value = app.load_config()
        if not isinstance(value, dict) or not isinstance(value.get('automatic', {}), dict):
            raise ValueError()
        return value
    except (OSError, ValueError, TypeError):
        raise SetupError('save_failed', '') from None


def _user_paused():
    path = app.DATA / 'catalog.sqlite'
    if not path.is_file():
        return False
    try:
        # Do not create a DB, run migrations, write pause rows or change WAL mode.
        connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=5)
        try:
            if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='processing_control'").fetchone():
                return False
            row = connection.execute('SELECT paused FROM processing_control WHERE id=1').fetchone()
            return bool(row and row[0])
        finally:
            connection.close()
    except (OSError, sqlite3.Error):
        raise SetupError('save_failed', '') from None


def status():
    config = _config()
    automatic = config.get('automatic', {})
    library = automatic.get('library_root') or automatic.get('root') or ''
    if library:
        library = _folder(library)  # Unavailable existing state is an error, never first-run reset.
    try:
        stored = credential_store.saved(config)
        keys = {name: bool(credential_store.setting(name, config=config, saved_values=stored)) for name in credential_store.ALLOWED_KEYS}
    except (OSError, ValueError, credential_store.CredentialError):
        raise SetupError('save_failed', '') from None
    return {'configured': bool(library), 'user_paused': _user_paused(), 'saved_keys': keys, 'library': library}


def _replace(source, destination):
    if os.name == 'nt':
        move = ctypes.WinDLL('kernel32', use_last_error=True).MoveFileExW
        move.argtypes, move.restype = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD], wintypes.BOOL
        if not move(str(source), str(destination), 0x1 | 0x8):
            raise OSError('Atomic setup commit failed')
    else:
        os.replace(source, destination)  # Synthetic fixture support; DPAPI save itself remains Windows-only.


def _durable_write(path, data):
    credential_store.plain(path)
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def save(folder, keys):
    library = _folder(folder)
    if not isinstance(keys, dict) or any(name not in credential_store.ALLOWED_KEYS for name in keys):
        raise SetupError('key_invalid', '')
    replacements = {}
    for name, value in keys.items():
        if not isinstance(value, str) or any(char in value for char in '\r\n\0'):
            raise SetupError('key_invalid', name)
        value = value.strip()
        if value:
            replacements[name] = value
    claim = None
    lock = None
    temporary = None
    try:
        with _mutex:
            state = credential_store.plain(app.STATE_ROOT)
            state.mkdir(parents=True, exist_ok=True)
            credential_store.plain(state / 'setup.lock')
            lock = file_lock.open_lock(state / 'setup.lock')
            if not file_lock.try_lock(lock):
                raise SetupError('save_failed', '')
            try:
                claim = library_lock.acquire(library, role='setup')
            except library_lock.LibraryBusy:
                raise SetupError('library_busy') from None
            config = _config()
            paused = _user_paused()
            saved = credential_store.saved(config)
            saved.update(replacements)
            # Compute public booleans before the single final commit so success has
            # no fallible post-commit secret reads or provider calls.
            presence = {name: bool(saved.get(name) or credential_store.setting(name, config=config, saved_values=saved)) for name in credential_store.ALLOWED_KEYS}
            if replacements:
                encrypted = credential_store.encrypt(saved)
                folder = credential_store.plain(state / 'credentials')
                folder.mkdir(exist_ok=True)
                generation = folder / (uuid.uuid4().hex + '.dpapi')
                _durable_write(generation, encrypted)
                config[credential_store.POINTER] = 'credentials/' + generation.name
            automatic = dict(config.get('automatic', {}))
            automatic.update(library_root=library, root=library, enabled=True)
            config['automatic'] = automatic
            destination = credential_store.plain(state / 'config.json')
            temporary = state / ('config.' + uuid.uuid4().hex + '.tmp')
            _durable_write(temporary, json.dumps(config, ensure_ascii=False, indent=2).encode('utf-8'))
            # All referenced encrypted data is already durable. One atomic replace
            # switches settings and credential generation together; failure retains
            # the previous config/pointer. Unreferenced ciphertext is recovery evidence.
            _replace(temporary, destination)
            temporary = None
            return {'configured': True, 'user_paused': paused, 'saved_keys': presence, 'library': library}
    except SetupError:
        raise
    except (OSError, ValueError, TypeError, credential_store.CredentialError):
        raise SetupError('save_failed', '') from None
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
        if claim is not None:
            claim.release()  # Every launched engine reclaims before any processing.
        if lock is not None:
            os.close(lock)


def save_keys(keys):
    """One atomic encrypted-key replacement; config and processing are read-only."""
    if not isinstance(keys, dict) or any(name not in credential_store.ALLOWED_KEYS for name in keys):
        raise SetupError('key_invalid', '')
    replacements = {}
    for name, value in keys.items():
        if not isinstance(value, str) or any(char in value for char in '\r\n\0'):
            raise SetupError('key_invalid', name)
        value = value.strip()
        if value:
            replacements[name] = value
    temporary = None
    lock = None
    try:
        with _mutex:
            state = credential_store.plain(app.STATE_ROOT)
            credential_store.plain(state / 'setup.lock')
            lock = file_lock.open_lock(state / 'setup.lock')
            if not file_lock.try_lock(lock):
                raise SetupError('save_failed', '')
            config = _config()
            saved = credential_store.saved(config)
            saved.update(replacements)
            presence = {name: bool(saved.get(name) or credential_store.setting(name, config=config, saved_values=saved)) for name in credential_store.ALLOWED_KEYS}
            if replacements:
                folder = credential_store.plain(state / 'credentials')
                folder.mkdir(exist_ok=True)
                destination = credential_store.plain(folder / 'current.dpapi')
                temporary = folder / (uuid.uuid4().hex + '.tmp')
                encrypted = credential_store.encrypt({'schema': 1, 'base_generation': config.get(credential_store.POINTER), 'keys': saved})
                _durable_write(temporary, encrypted)
                _replace(temporary, destination)
                temporary = None
            return {'saved_keys': presence}
    except SetupError:
        raise
    except (OSError, ValueError, TypeError, credential_store.CredentialError):
        raise SetupError('save_failed', '') from None
    finally:
        if temporary is not None:
            try:temporary.unlink(missing_ok=True)
            except OSError:pass
        if lock is not None:os.close(lock)


def key_status():
    try:
        config = _config()
        stored = credential_store.saved(config)
        return {'saved_keys': {name: bool(credential_store.setting(name, config=config, saved_values=stored)) for name in credential_store.ALLOWED_KEYS}}
    except (OSError, ValueError, credential_store.CredentialError):
        raise SetupError('save_failed', '') from None
