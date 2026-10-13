"""Hold and verify an updater payload while its exact installer process runs.

One bounded JSON line on stdin; one sanitized startup receipt on stdout.
Windows native calls are loaded only when the helper actually runs on Windows.
This module neither downloads payloads nor selects an install destination.
"""
import base64
import binascii
import ctypes
import hashlib
import hmac
import json
import ntpath
import os
import re
import subprocess
import sys
import time

MAX_INPUT = 8192
MAX_SIZE = 2 * 1024 * 1024 * 1024
OBSERVE_MS = 400
PRELAUNCH_SECONDS = 8

class LaunchError(Exception):
    def __init__(self, phase, code):
        self.phase, self.code = phase, code
        super().__init__(phase + ':' + code)


def absolute_windows_path(value, executable=False):
    if not isinstance(value, str) or len(value) > 30000 or any(c in value for c in '\r\n\0'):
        raise LaunchError('input', 'invalid_path')
    drive, tail = ntpath.splitdrive(value)
    # Updater payloads are local files. Device/UNC/relative paths and ADS are refused.
    if not re.fullmatch(r'[A-Za-z]:', drive) or not tail.startswith(('\\', '/')):
        raise LaunchError('input', 'invalid_path')
    parts = tail.replace('/', '\\').split('\\')[1:]
    if not parts or any(not part or part in ('.', '..') or part.endswith((' ', '.'))
                        or any(c in part for c in ':<>"|?*')
                        or re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', part, re.I)
                        for part in parts):
        raise LaunchError('input', 'invalid_path')
    path = drive.upper() + '\\' + '\\'.join(parts)
    if executable and not path.lower().endswith('.exe'):
        raise LaunchError('input', 'invalid_payload')
    return path


def validate_request(value):
    if not isinstance(value, dict) or not {'path', 'size', 'sha512', 'parent_pid'} <= set(value) or set(value) - {'path', 'size', 'sha512', 'parent_pid', 'install_dir'}:
        raise LaunchError('input', 'invalid_schema')
    size, parent = value['size'], value['parent_pid']
    if isinstance(size, bool) or not isinstance(size, int) or not 0 < size <= MAX_SIZE:
        raise LaunchError('input', 'invalid_size')
    if isinstance(parent, bool) or not isinstance(parent, int) or not 0 < parent <= 0xFFFFFFFF:
        raise LaunchError('input', 'invalid_parent')
    encoded = value['sha512']
    try:
        if not isinstance(encoded, str) or len(encoded) != 88:
            raise ValueError()
        digest = base64.b64decode(encoded, validate=True)
        if len(digest) != 64 or base64.b64encode(digest).decode('ascii') != encoded:
            raise ValueError()
    except (ValueError, binascii.Error):
        raise LaunchError('input', 'invalid_digest') from None
    result = {'path': absolute_windows_path(value['path'], executable=True), 'size': size,
              'digest': digest, 'parent_pid': parent}
    if 'install_dir' in value:
        result['install_dir'] = absolute_windows_path(value['install_dir'])
    return result


def ancestors(path):
    result = []
    current = ntpath.dirname(path)
    while current:
        result.append(current)
        parent = ntpath.dirname(current)
        if parent == current:
            break
        current = parent
    return list(reversed(result))


def arguments(request):
    result = [request['path'], '--updated', '/S', '--force-run']
    if request.get('install_dir'):
        result.append('/D=' + request['install_dir'])  # NSIS requires /D last.
    return result


class Windows:
    READ = 0x80000000
    ATTRIBUTES = 0x80
    SHARE_READ = 1
    OPEN_EXISTING = 3
    BACKUP_SEMANTICS = 0x02000000
    OPEN_REPARSE_POINT = 0x00200000
    REPARSE = 0x400
    DIRECTORY = 0x10
    WAIT_TIMEOUT = 258
    WAIT_OBJECT = 0
    SYNCHRONIZE = 0x00100000
    QUERY_LIMITED = 0x1000
    INVALID = ctypes.c_void_p(-1).value

    def __init__(self):
        if os.name != 'nt':
            raise LaunchError('platform', 'windows_required')
        from ctypes import wintypes as wt
        self.wt = wt
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        class FILE_INFO(ctypes.Structure):
            _fields_ = [('attributes', wt.DWORD), ('created', wt.FILETIME), ('accessed', wt.FILETIME),
                        ('written', wt.FILETIME), ('volume', wt.DWORD), ('size_high', wt.DWORD),
                        ('size_low', wt.DWORD), ('links', wt.DWORD), ('index_high', wt.DWORD), ('index_low', wt.DWORD)]
        class STARTUP(ctypes.Structure):
            _fields_ = [('cb', wt.DWORD), ('reserved', wt.LPWSTR), ('desktop', wt.LPWSTR), ('title', wt.LPWSTR),
                        ('x', wt.DWORD), ('y', wt.DWORD), ('width', wt.DWORD), ('height', wt.DWORD),
                        ('chars_x', wt.DWORD), ('chars_y', wt.DWORD), ('fill', wt.DWORD), ('flags', wt.DWORD),
                        ('show', wt.WORD), ('reserved2_size', wt.WORD), ('reserved2', ctypes.POINTER(wt.BYTE)),
                        ('stdin', wt.HANDLE), ('stdout', wt.HANDLE), ('stderr', wt.HANDLE)]
        class PROCESS(ctypes.Structure):
            _fields_ = [('process', wt.HANDLE), ('thread', wt.HANDLE), ('pid', wt.DWORD), ('thread_id', wt.DWORD)]
        self.FILE_INFO, self.STARTUP, self.PROCESS = FILE_INFO, STARTUP, PROCESS
        signatures = {
            'CreateFileW': ([wt.LPCWSTR, wt.DWORD, wt.DWORD, wt.LPVOID, wt.DWORD, wt.DWORD, wt.HANDLE], wt.HANDLE),
            'GetFileInformationByHandle': ([wt.HANDLE, ctypes.POINTER(FILE_INFO)], wt.BOOL),
            'GetFileSizeEx': ([wt.HANDLE, ctypes.POINTER(ctypes.c_longlong)], wt.BOOL),
            'ReadFile': ([wt.HANDLE, wt.LPVOID, wt.DWORD, ctypes.POINTER(wt.DWORD), wt.LPVOID], wt.BOOL),
            'CloseHandle': ([wt.HANDLE], wt.BOOL),
            'OpenProcess': ([wt.DWORD, wt.BOOL, wt.DWORD], wt.HANDLE),
            'WaitForSingleObject': ([wt.HANDLE, wt.DWORD], wt.DWORD),
            'GetExitCodeProcess': ([wt.HANDLE, ctypes.POINTER(wt.DWORD)], wt.BOOL),
            'CreateProcessW': ([wt.LPCWSTR, wt.LPWSTR, wt.LPVOID, wt.LPVOID, wt.BOOL, wt.DWORD,
                                wt.LPVOID, wt.LPCWSTR, ctypes.POINTER(STARTUP), ctypes.POINTER(PROCESS)], wt.BOOL),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self.kernel, name)
            function.argtypes, function.restype = args, result

    def close(self, handle):
        if handle not in (None, 0, self.INVALID):
            self.kernel.CloseHandle(handle)

    def parent(self, pid):
        handle = self.kernel.OpenProcess(self.SYNCHRONIZE | self.QUERY_LIMITED, False, pid)
        if not handle or self.kernel.WaitForSingleObject(handle, 0) != self.WAIT_TIMEOUT:
            self.close(handle)
            raise LaunchError('parent', 'parent_unavailable')
        return handle

    def alive(self, handle):
        # The held process handle pins identity even if its PID is later reused.
        return self.kernel.WaitForSingleObject(handle, 0) == self.WAIT_TIMEOUT

    def hold(self, path, directory=False):
        handle = self.kernel.CreateFileW('\\\\?\\' + path,
            self.ATTRIBUTES if directory else self.READ,
            self.SHARE_READ, None, self.OPEN_EXISTING,
            self.OPEN_REPARSE_POINT | (self.BACKUP_SEMANTICS if directory else 0), None)
        if handle in (None, 0, self.INVALID):
            raise LaunchError('hold', 'handle_unavailable')
        info = self.FILE_INFO()
        if not self.kernel.GetFileInformationByHandle(handle, ctypes.byref(info)):
            self.close(handle)
            raise LaunchError('hold', 'attributes_unavailable')
        if info.attributes & self.REPARSE or bool(info.attributes & self.DIRECTORY) != directory:
            self.close(handle)
            raise LaunchError('hold', 'unsafe_file_type')
        return handle

    def verify(self, handle, expected_size, expected_digest, deadline=None):
        size = ctypes.c_longlong()
        if not self.kernel.GetFileSizeEx(handle, ctypes.byref(size)) or size.value != expected_size:
            raise LaunchError('verify', 'size_mismatch')
        digest = hashlib.sha512()
        remaining = expected_size
        buffer = ctypes.create_string_buffer(1024 * 1024)
        received = self.wt.DWORD()
        while remaining:
            if deadline is not None and time.monotonic() >= deadline:
                raise LaunchError('deadline', 'prelaunch_timeout')
            wanted = min(remaining, len(buffer))
            if not self.kernel.ReadFile(handle, buffer, wanted, ctypes.byref(received), None):
                raise LaunchError('verify', 'read_failed')
            if not 0 < received.value <= wanted:
                raise LaunchError('verify', 'short_read')
            digest.update(buffer.raw[:received.value])
            remaining -= received.value
        if not hmac.compare_digest(digest.digest(), expected_digest):
            raise LaunchError('verify', 'digest_mismatch')

    def create(self, request):
        startup, process = self.STARTUP(), self.PROCESS()
        startup.cb = ctypes.sizeof(startup)
        startup.flags, startup.show = 1, 0  # STARTF_USESHOWWINDOW, SW_HIDE.
        command = ctypes.create_unicode_buffer(subprocess.list2cmdline(arguments(request)))
        if not self.kernel.CreateProcessW(request['path'], command, None, None, False,
                                         0x08000000, None, None, ctypes.byref(startup), ctypes.byref(process)):
            raise LaunchError('create', 'create_failed')
        self.close(process.thread)
        return process.process, int(process.pid)

    def observe(self, handle, milliseconds):
        result = self.kernel.WaitForSingleObject(handle, milliseconds)
        if result == self.WAIT_TIMEOUT:
            return None
        if result != self.WAIT_OBJECT:
            raise LaunchError('observe', 'wait_failed')
        code = self.wt.DWORD()
        if not self.kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
            raise LaunchError('observe', 'exit_status_unavailable')
        return int(code.value)

    def wait(self, handle):
        # Never release the verified payload while this exact process may be alive.
        # An API wait failure is not proof of exit; keep ownership and retry.
        while True:
            result = self.kernel.WaitForSingleObject(handle, 1000)
            if result == self.WAIT_OBJECT:
                return
            if result == self.WAIT_TIMEOUT:
                continue
            code = self.wt.DWORD()
            if self.kernel.GetExitCodeProcess(handle, ctypes.byref(code)) and code.value != 259:
                return
            time.sleep(0.1)


def run(request, native, receipt):
    held, parent, process = [], None, None
    reported = False
    waited = False
    deadline = time.monotonic() + PRELAUNCH_SECONDS
    def check_deadline():
        if time.monotonic() >= deadline:
            raise LaunchError('deadline', 'prelaunch_timeout')
    def report(value):
        nonlocal reported
        if not reported:
            reported = True  # Even a broken stdout must never cause duplicate receipts.
            receipt(value)
    try:
        parent = native.parent(request['parent_pid'])
        check_deadline()
        for folder in ancestors(request['path']):
            held.append(native.hold(folder, directory=True))
            check_deadline()
        payload = native.hold(request['path'])
        held.append(payload)
        check_deadline()
        native.verify(payload, request['size'], request['digest'], deadline=deadline)
        check_deadline()  # Never initiate a delayed launch after the setup deadline.
        if not native.alive(parent):
            raise LaunchError('parent', 'parent_exited_before_launch')
        check_deadline()
        process, pid = native.create(request)
        early = native.observe(process, OBSERVE_MS)
        if early is not None:
            raise LaunchError('observe', 'installer_exited_early')
        report({'started': True, 'accepted': True, 'phase': 'started', 'installer_pid': pid})
        native.wait(process)
        waited = True
        return 0
    except LaunchError as exc:
        report({'started': process is not None, 'accepted': False, 'phase': exc.phase, 'code': exc.code})
        return 1
    except Exception:
        report({'started': process is not None, 'accepted': False, 'phase': 'internal', 'code': 'startup_failed'})
        return 1
    finally:
        # A failed observation/receipt is not permission to release a running payload.
        if process is not None and not waited:
            native.wait(process)
        native.close(process)
        for handle in reversed(held):
            native.close(handle)
        native.close(parent)


def emit(receipt):
    sys.stdout.write(json.dumps(receipt, separators=(',', ':')) + '\n')
    sys.stdout.flush()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise LaunchError('input', 'invalid_schema')
        result[key] = value
    return result


def main(stdin=None, native=None, receipt=emit):
    stream = stdin if stdin is not None else sys.stdin.buffer
    reported = False
    def report(value):
        nonlocal reported
        if not reported:
            reported = True
            receipt(value)
    try:
        raw = stream.readline(MAX_INPUT + 1)
        if not raw or len(raw) > MAX_INPUT or not raw.endswith(b'\n') or stream.read(1):
            raise LaunchError('input', 'invalid_input')
        request = validate_request(json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object))
        return run(request, native if native is not None else Windows(), report)
    except LaunchError as exc:
        report({'started': False, 'accepted': False, 'phase': exc.phase, 'code': exc.code})
        return 1
    except Exception:
        report({'started': False, 'accepted': False, 'phase': 'input', 'code': 'invalid_input'})
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
