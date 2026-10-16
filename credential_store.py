"""User-bound DPAPI replacements; existing environment files stay untouched."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import re
import app

ALLOWED_KEYS = ('COMICVINE_API_KEY', 'METRON_API_TOKEN', 'GOOGLE_BOOKS_API_KEY', 'BRAVE_SEARCH_API_KEY')
# Keys of removed sources (SerpApi, 2026-10-16). A value saved by an earlier
# version still loads and is kept as saved; nothing reads it or offers it.
RETIRED_KEYS = ('SERPAPI_API_KEY',)
POINTER = '_credential_file'


class CredentialError(Exception):
    def __init__(self):
        super().__init__('Saved credentials could not be opened.')


def plain(path):
    path = Path(path)
    for entry in (path, *path.parents):
        try:
            info = entry.lstat()
        except FileNotFoundError:
            continue
        if entry.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise CredentialError()
    return path


def _crypt(data, protect):
    if os.name != 'nt':
        raise CredentialError()
    class Blob(ctypes.Structure):
        _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_ubyte))]
    crypt32 = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    local_free = kernel32.LocalFree
    local_free.argtypes, local_free.restype = [ctypes.c_void_p], ctypes.c_void_p
    buffer = ctypes.create_string_buffer(data)
    incoming = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    entropy_buffer = ctypes.create_string_buffer(b'Comic Metadata API credentials v1')
    entropy = Blob(len(entropy_buffer.raw)-1, ctypes.cast(entropy_buffer, ctypes.POINTER(ctypes.c_ubyte)))
    function = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    try:
        # No LOCAL_MACHINE flag: only this Windows user's DPAPI context decrypts.
        if not function(ctypes.byref(incoming), None, ctypes.byref(entropy), None, None, 1, ctypes.byref(output)):
            raise CredentialError()
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        ctypes.memset(buffer, 0, ctypes.sizeof(buffer))
        if output.pbData:
            ctypes.memset(output.pbData, 0, output.cbData)
            local_free(ctypes.cast(output.pbData, ctypes.c_void_p))


def encrypt(values):
    return _crypt(json.dumps(values, ensure_ascii=False).encode('utf-8'), True)


def _validated(values):
    if not isinstance(values, dict) or any(name not in ALLOWED_KEYS + RETIRED_KEYS or not isinstance(value, str) or any(c in value for c in '\r\n\0') for name, value in values.items()):
        raise CredentialError()
    return values


def saved(config=None):
    config = app.load_config() if config is None else config
    pointer = config.get(POINTER)
    if pointer is not None and (not isinstance(pointer, str) or not re.fullmatch(r'credentials/[a-f0-9]{32}\.dpapi', pointer)):
        raise CredentialError()
    try:
        values = {} if pointer is None else _validated(json.loads(_crypt(plain(app.STATE_ROOT / pointer).read_bytes(), False).decode('utf-8')))
        overlay_path = plain(app.STATE_ROOT / 'credentials' / 'current.dpapi')
        if overlay_path.is_file():
            overlay = json.loads(_crypt(overlay_path.read_bytes(), False).decode('utf-8'))
            if not isinstance(overlay, dict) or set(overlay) != {'schema', 'base_generation', 'keys'} or type(overlay['schema']) is not int or overlay['schema'] != 1:
                raise CredentialError()
            generation=overlay['base_generation']
            if generation is not None and (not isinstance(generation,str) or not re.fullmatch(r'credentials/[a-f0-9]{32}\.dpapi',generation)):
                raise CredentialError()
            keys = _validated(overlay['keys'])
            # A later first-run config generation invalidates the old overlay.
            # Its new base already includes the previously saved keys.
            if overlay['base_generation'] == pointer:
                values.update(keys)
        return values
    except (OSError, ValueError, TypeError, UnicodeError):
        raise CredentialError() from None


def _environment(name):
    value = os.environ.get(name, '').strip()
    if value:
        return value
    wanted = name.upper()
    for key, candidate in os.environ.items():
        if key.upper() == wanted and candidate.strip():
            return candidate.strip()
    return ''


def setting(name, *, config=None, saved_values=None):
    # Key names match in any case in the environment and in env files, as in
    # v0.1.4 (a live .env spelled one in mixed case). Saved values keep their
    # canonical names.
    value = _environment(name)
    if value:
        return value
    if name in ALLOWED_KEYS:
        value = (saved(config) if saved_values is None else saved_values).get(name, '')
        if value:
            return value
    for path in app.env_files(config):
        if not path.is_file():
            continue
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            line = line.strip().removeprefix('export ').strip()
            if not line or line.startswith('#'):
                continue
            key, separator, candidate = line.partition('=')
            if separator and key.strip().upper() == name.upper():
                candidate = candidate.strip()
                if len(candidate) > 1 and candidate[0] == candidate[-1] and candidate[0] in ('"', "'"):
                    candidate = candidate[1:-1]
                else:
                    candidate = candidate.split(' #', 1)[0].strip()
                if candidate:
                    return candidate
            # Preserve the legacy ComicVine bare-key format.
            if name == 'COMICVINE_API_KEY' and re.fullmatch(r'[a-fA-F0-9]{40}', line):
                return line
    return ''
