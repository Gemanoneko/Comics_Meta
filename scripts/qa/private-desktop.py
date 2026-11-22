"""Private Win32 desktop for tray QA (Comic Metadata).

A tray made on the user's own desktop registers an icon with Explorer under his logon: a second icon in his
notification area and a record in his Windows profile. This helper runs a program on a separate desktop of the same
window station. No shell tray exists there, so a tray has nothing to register with. It never calls SwitchDesktop (its
desktop handle has no switch right): nothing is shown and the input desktop does not change.

Run with -B so no __pycache__ is written:

  python -B private-desktop.py check [--record FILE]
      Creates a desktop, starts a probe on it and checks from inside that no shell tray and no explorer.exe window is
      reachable. Exit 0 only if that holds, the same probe finds the tray on the caller's own desktop (the control),
      the input desktop is unchanged and Explorer's tray records are unchanged.

  python -B private-desktop.py run --record FILE -- EXE [ARG...]
      The same check first; a failed check starts nothing (exit 250). Then starts EXE on that desktop with this
      process's environment, working folder and stdio, waits, and exits with EXE's exit code. FILE names the desktop
      and EXE's PID while it runs, and afterwards the exit code and Explorer's tray records before and after.
      While EXE runs it sits in a kill-on-close Job, so ending this helper ends EXE and its children. When EXE exits by
      itself that Job is released first: a child EXE left behind keeps running, for the caller's own closure check to
      find. Exit 252 if the Job could not be released (leftovers may then have been ended here; closure is unproven).

  python -B private-desktop.py windows --under FOLDER [--desktop NAME]
      Top-level windows of programs under FOLDER, on desktop NAME or on the caller's own desktop.

  python -B private-desktop.py snapshot
      Explorer's tray records (HKCU, read only): count, names and a digest.

Tray smoke of the packaged app (private QA profile, any Python 3 with ctypes; the standard library only):
  1. Add "tray": true to the QA policy before hashing it. Without it a QA profile has no tray.
  2. Start the app through this helper, not directly, with the environment, working folder and arguments it would
     otherwise get:
       python -B scripts/qa/private-desktop.py run --record RECORD.json -- EXTRACT\\ComicMetadata.exe --inspect-brk=...
     From Node: spawn(PYTHON, ['-B', HELPER, 'run', '--record', RECORD, '--', EXE, ...args], {env, cwd, stdio}).
     The spawned PID is this helper's. The app's PID is "pid" in RECORD once "phase" is "running" (or process.pid
     over the inspector). To end the app from outside, end the helper.
  3. Keep RECORD with the evidence: the check made from inside the desktop, and Explorer's tray records before and
     after ("trayRecordsUnchanged" must be true). "windows --under EXTRACT --desktop NAME" lists the app's windows
     there; without --desktop it must list none.
  Never use "tray": true for a run that is not started this way: on the user's own desktop the tray registers.

Proven with harmless programs only (2026-11-22). Not yet proven with the app: that Electron keeps a working Tray when
Explorer cannot be reached, and that its offscreen windows behave on a desktop that is never shown.
"""
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import os
import secrets
import subprocess
import sys
import time
import winreg

if os.name != 'nt' or C.sizeof(C.c_void_p) != 8:
    raise SystemExit('Windows x64 only')
U = C.WinDLL('user32', use_last_error=True)
K = C.WinDLL('kernel32', use_last_error=True)
H = W.HANDLE
ENUM = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
# Read, enumerate, and the create-window right CreateDesktop itself needs. No DESKTOP_SWITCHDESKTOP (0x0100): this
# handle cannot take the screen.
DESKTOP_ACCESS = 0x0001 | 0x0002 | 0x0040 | 0x00020000
REFUSED, FAILED, NOT_RELEASED = 250, 251, 252


class STARTUPINFO(C.Structure):
    _fields_ = [('cb', W.DWORD), ('lpReserved', W.LPWSTR), ('lpDesktop', W.LPWSTR), ('lpTitle', W.LPWSTR),
                ('dwX', W.DWORD), ('dwY', W.DWORD), ('dwXSize', W.DWORD), ('dwYSize', W.DWORD),
                ('dwXCountChars', W.DWORD), ('dwYCountChars', W.DWORD), ('dwFillAttribute', W.DWORD),
                ('dwFlags', W.DWORD), ('wShowWindow', W.WORD), ('cbReserved2', W.WORD), ('lpReserved2', C.c_void_p),
                ('hStdInput', H), ('hStdOutput', H), ('hStdError', H)]


class PROCESS_INFORMATION(C.Structure):
    _fields_ = [('hProcess', H), ('hThread', H), ('dwProcessId', W.DWORD), ('dwThreadId', W.DWORD)]


class JOB_LIMITS(C.Structure):  # JOBOBJECT_EXTENDED_LIMIT_INFORMATION
    _fields_ = [('PerProcessUserTimeLimit', C.c_longlong), ('PerJobUserTimeLimit', C.c_longlong),
                ('LimitFlags', W.DWORD), ('MinimumWorkingSetSize', C.c_size_t), ('MaximumWorkingSetSize', C.c_size_t),
                ('ActiveProcessLimit', W.DWORD), ('Affinity', C.c_size_t), ('PriorityClass', W.DWORD),
                ('SchedulingClass', W.DWORD), ('IoInfo', C.c_ulonglong * 6), ('ProcessMemoryLimit', C.c_size_t),
                ('JobMemoryLimit', C.c_size_t), ('PeakProcessMemoryUsed', C.c_size_t),
                ('PeakJobMemoryUsed', C.c_size_t)]


def sig(function, result, *arguments):
    function.restype, function.argtypes = result, list(arguments)


sig(U.CreateDesktopW, H, W.LPCWSTR, W.LPCWSTR, C.c_void_p, W.DWORD, W.DWORD, C.c_void_p)
sig(U.OpenDesktopW, H, W.LPCWSTR, W.DWORD, W.BOOL, W.DWORD)
sig(U.OpenInputDesktop, H, W.DWORD, W.BOOL, W.DWORD)
sig(U.CloseDesktop, W.BOOL, H)
sig(U.GetThreadDesktop, H, W.DWORD)
sig(U.GetProcessWindowStation, H)
sig(U.GetUserObjectInformationW, W.BOOL, H, C.c_int, C.c_void_p, W.DWORD, C.POINTER(W.DWORD))
sig(U.FindWindowW, W.HWND, W.LPCWSTR, W.LPCWSTR)
sig(U.GetShellWindow, W.HWND)
sig(U.GetForegroundWindow, W.HWND)
sig(U.EnumWindows, W.BOOL, ENUM, W.LPARAM)
sig(U.EnumDesktopWindows, W.BOOL, H, ENUM, W.LPARAM)
sig(U.GetClassNameW, C.c_int, W.HWND, W.LPWSTR, C.c_int)
sig(U.GetWindowThreadProcessId, W.DWORD, W.HWND, C.POINTER(W.DWORD))
sig(U.IsWindowVisible, W.BOOL, W.HWND)
sig(U.CreateWindowExW, W.HWND, W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD, C.c_int, C.c_int, C.c_int, C.c_int, W.HWND,
    H, H, C.c_void_p)
sig(U.DestroyWindow, W.BOOL, W.HWND)
sig(K.GetCurrentThreadId, W.DWORD)
sig(K.GetCurrentProcess, H)
sig(K.OpenProcess, H, W.DWORD, W.BOOL, W.DWORD)
sig(K.QueryFullProcessImageNameW, W.BOOL, H, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD))
sig(K.CloseHandle, W.BOOL, H)
sig(K.GetStdHandle, H, W.DWORD)
sig(K.DuplicateHandle, W.BOOL, H, H, H, C.POINTER(H), W.DWORD, W.BOOL, W.DWORD)
sig(K.CreateProcessW, W.BOOL, W.LPCWSTR, W.LPWSTR, C.c_void_p, C.c_void_p, W.BOOL, W.DWORD, C.c_void_p, W.LPCWSTR,
    C.POINTER(STARTUPINFO), C.POINTER(PROCESS_INFORMATION))
sig(K.WaitForSingleObject, W.DWORD, H, W.DWORD)
sig(K.GetExitCodeProcess, W.BOOL, H, C.POINTER(W.DWORD))
sig(K.TerminateProcess, W.BOOL, H, W.UINT)
sig(K.ResumeThread, W.DWORD, H)
sig(K.CreateJobObjectW, H, C.c_void_p, W.LPCWSTR)
sig(K.SetInformationJobObject, W.BOOL, H, C.c_int, C.c_void_p, W.DWORD)
sig(K.AssignProcessToJobObject, W.BOOL, H, H)


def object_name(handle):
    needed, text = W.DWORD(0), C.create_unicode_buffer(256)
    return text.value if handle and U.GetUserObjectInformationW(handle, 2, text, C.sizeof(text), C.byref(needed)) else None


def input_desktop():
    """The desktop that has the screen and the keyboard; None when it cannot be opened (lock screen, UAC)."""
    handle = U.OpenInputDesktop(0, False, 0x0001)
    try:
        return object_name(handle)
    finally:
        if handle:
            U.CloseDesktop(handle)


def image_of(pid):
    handle = K.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return None
    try:
        size = W.DWORD(32768)
        text = C.create_unicode_buffer(size.value)
        return text.value if K.QueryFullProcessImageNameW(handle, 0, text, C.byref(size)) else None
    finally:
        K.CloseHandle(handle)


def top_level_windows(desktop=None):
    """Class, owner and visibility of each top-level window. No message is sent to any window."""
    found = []

    def each(hwnd, _):
        name, pid = C.create_unicode_buffer(256), W.DWORD(0)
        U.GetClassNameW(hwnd, name, 256)
        U.GetWindowThreadProcessId(hwnd, C.byref(pid))
        found.append({'class': name.value, 'pid': pid.value, 'image': image_of(pid.value),
                      'visible': bool(U.IsWindowVisible(hwnd))})
        return True
    callback = ENUM(each)
    if desktop:
        U.EnumDesktopWindows(desktop, callback, 0)  # Returns FALSE for a desktop with no windows.
    else:
        U.EnumWindows(callback, 0)
    return found


def is_explorer(window):
    return os.path.basename(window['image'] or '').lower() == 'explorer.exe'


def survey(detail, nonce=None):
    """What is reachable from this thread's desktop. With a nonce it first makes one never-shown window of its own, so
    that finding nothing else is a finding and not a blind search."""
    own = U.CreateWindowExW(0, 'Static', 'cmo-desktop-probe-' + nonce, 0, 0, 0, 0, 0, None, None, None, None) if nonce else None
    try:
        windows = top_level_windows()
        result = {
            'pid': os.getpid(), 'windowStation': object_name(U.GetProcessWindowStation()),
            'desktop': object_name(U.GetThreadDesktop(K.GetCurrentThreadId())), 'inputDesktop': input_desktop(),
            'shellTray': bool(U.FindWindowW('Shell_TrayWnd', None)),
            'secondaryTray': bool(U.FindWindowW('Shell_SecondaryTrayWnd', None)),
            'progman': bool(U.FindWindowW('Progman', None)), 'shellWindow': bool(U.GetShellWindow()),
            'topLevelWindows': len(windows), 'explorerWindows': sum(1 for item in windows if is_explorer(item))}
        if nonce:
            result['ownWindowCreated'] = bool(own)
            result['ownWindowFound'] = bool(own) and U.FindWindowW('Static', 'cmo-desktop-probe-' + nonce) == own
            result['ownWindowEnumerated'] = any(item['pid'] == os.getpid() and item['class'] == 'Static' for item in windows)
        if detail:
            result['windows'] = windows
        return result
    finally:
        if own:
            U.DestroyWindow(own)


def tray_records():
    """Explorer's per-program tray records in the user's registry. Read only."""
    def key_state(root, path):
        try:
            key = winreg.OpenKey(root, path, 0, winreg.KEY_READ)
        except OSError:
            return None
        with key:
            subkeys, values, written = winreg.QueryInfoKey(key)
            names = [winreg.EnumKey(key, index) for index in range(subkeys)]
            state = []
            for name in names:
                with winreg.OpenKey(key, name, 0, winreg.KEY_READ) as sub:
                    state.append([name, list(winreg.QueryInfoKey(sub))])
            for index in range(values):
                name, value, kind = winreg.EnumValue(key, index)
                state.append(['=' + name, kind, hashlib.sha256(repr(value).encode('utf-8', 'replace')).hexdigest()])
            return {'subkeys': subkeys, 'values': values, 'lastWrite': written, 'names': sorted(names),
                    'stateSha256': hashlib.sha256(json.dumps(sorted(state, key=str)).encode()).hexdigest()}
    return {'NotifyIconSettings': key_state(winreg.HKEY_CURRENT_USER, r'Control Panel\NotifyIconSettings'),
            'TrayNotify': key_state(winreg.HKEY_CURRENT_USER, r'Software\Classes\Local Settings\Software\Microsoft\Windows\CurrentVersion\TrayNotify')}


def start(executable, arguments, desktop, flags, stdio):
    startup, process = STARTUPINFO(), PROCESS_INFORMATION()
    startup.cb, startup.lpDesktop = C.sizeof(startup), desktop
    inherit = False
    if stdio:
        handles = []
        for number in (-10, -11, -12):
            source, copy = K.GetStdHandle(number), H()
            me = K.GetCurrentProcess()
            good = source and source != H(-1).value and K.DuplicateHandle(me, source, me, C.byref(copy), 0, True, 2)
            handles.append(copy if good else None)
        if any(handles):
            startup.hStdInput, startup.hStdOutput, startup.hStdError = handles
            startup.dwFlags, inherit = 0x100, True  # STARTF_USESTDHANDLES
    command = C.create_unicode_buffer(subprocess.list2cmdline([executable, *arguments]))
    if not K.CreateProcessW(executable, command, None, None, inherit, flags, None, None, C.byref(startup), C.byref(process)):
        raise OSError('CreateProcess failed: ' + str(C.get_last_error()))
    return process


def wait(process, seconds=None):
    """The exit code, or None if it is still running after the given seconds."""
    deadline = None if seconds is None else time.monotonic() + seconds
    while True:
        state = K.WaitForSingleObject(process.hProcess, 250)
        if state == 0:
            break
        if state != 0x102:  # Anything but WAIT_TIMEOUT.
            raise OSError('Wait failed: ' + str(C.get_last_error()))
        if deadline is not None and time.monotonic() > deadline:
            return None
    code = W.DWORD(0)
    K.GetExitCodeProcess(process.hProcess, C.byref(code))
    return code.value


def write_record(filename, record):
    text = json.dumps(record, indent=1)
    if not filename:
        return
    with open(filename + '.tmp', 'w', encoding='utf-8') as handle:
        handle.write(text)
    os.replace(filename + '.tmp', filename)


def checked_desktop(record, scratch):
    """Creates the desktop and fills the record with the control, the probe and the reasons to refuse (none = usable)."""
    station = object_name(U.GetProcessWindowStation())
    name = 'cmo-qa-' + secrets.token_hex(6)
    record.update({'launcherPid': os.getpid(), 'desktop': name, 'windowStation': station,
                   'inputDesktopBefore': input_desktop(), 'foregroundBefore': U.GetForegroundWindow(),
                   'trayRecordsBefore': tray_records(), 'control': survey(False)})
    problems = record['problems'] = []
    existing = U.OpenDesktopW(name, 0, False, 0x0001)
    if existing:
        U.CloseDesktop(existing)
        problems.append('a desktop of this name already exists')
        return None, None
    handle = U.CreateDesktopW(name, None, None, 0, DESKTOP_ACCESS, None)
    if not handle:
        problems.append('CreateDesktop failed: ' + str(C.get_last_error()))
        return None, None
    target = station + '\\' + name
    out = os.path.join(scratch, name + '.probe.json')
    nonce = secrets.token_hex(8)
    try:
        process = start(sys.executable, ['-B', '-I', os.path.abspath(__file__), 'probe', out, nonce], target, 0x08000000, False)
        code = wait(process, 30)
        if code is None:
            K.TerminateProcess(process.hProcess, 1)
        K.CloseHandle(process.hThread)
        K.CloseHandle(process.hProcess)
        with open(out, encoding='utf-8') as source:
            probe = record['probe'] = json.load(source)
        record['probeExit'] = code
    except (OSError, ValueError) as error:
        problems.append('the probe did not report: ' + str(error))
        probe = record['probe'] = None
    finally:
        if os.path.exists(out):
            os.remove(out)
    control = record['control']
    if not (control['shellTray'] and control['explorerWindows'] > 0):
        problems.append('control failed: the probe does not find the shell tray on the caller\'s own desktop')
    if probe:
        if probe['desktop'] != name or probe['windowStation'] != station:
            problems.append('the probe did not run on the private desktop')
        if not (probe['ownWindowCreated'] and probe['ownWindowFound'] and probe['ownWindowEnumerated']):
            problems.append('the probe could not see its own window, so its search proves nothing')
        if probe['shellTray'] or probe['secondaryTray'] or probe['progman'] or probe['shellWindow']:
            problems.append('a shell tray or shell window is reachable from the private desktop')
        if probe['explorerWindows']:
            problems.append('an explorer.exe window is on the private desktop')
        if probe['inputDesktop'] == name:
            problems.append('the private desktop has the screen')
    return handle, target


def finish(record, handle):
    if handle:
        record['windowsLeftOnDesktop'] = len(top_level_windows(handle))
        record['desktopHandleClosed'] = bool(U.CloseDesktop(handle))
    record.update({'inputDesktopAfter': input_desktop(), 'foregroundAfter': U.GetForegroundWindow(),
                   'trayRecordsAfter': tray_records()})
    record['inputDesktopUnchanged'] = record['inputDesktopAfter'] == record['inputDesktopBefore']
    record['foregroundUnchanged'] = record['foregroundAfter'] == record['foregroundBefore']
    # A tray made by a program Explorer has not seen adds a record. The user's own apps may touch existing ones.
    names = lambda records: {key: value and value['names'] for key, value in records.items()}
    record['trayRecordsUnchanged'] = names(record['trayRecordsAfter']) == names(record['trayRecordsBefore'])
    record['trayRecordStateUnchanged'] = record['trayRecordsAfter'] == record['trayRecordsBefore']


def command_check(arguments):
    filename = arguments[arguments.index('--record') + 1] if '--record' in arguments else None
    record = {'command': 'check'}
    handle, _ = checked_desktop(record, os.path.dirname(os.path.abspath(filename)) if filename else os.getcwd())
    finish(record, handle)
    if handle:
        gone = U.OpenDesktopW(record['desktop'], 0, False, 0x0001)
        record['desktopGone'] = not gone
        if gone:
            U.CloseDesktop(gone)
            record['problems'].append('the private desktop still exists after its handle was closed')
    if not record['inputDesktopUnchanged']:
        record['problems'].append('the input desktop changed during the check')
    if not record['trayRecordsUnchanged']:
        record['problems'].append('Explorer\'s tray records changed during the check')
    record['pass'] = not record['problems']
    write_record(filename, record)
    print(json.dumps({key: record.get(key) for key in ('pass', 'problems', 'desktop', 'control', 'probe', 'inputDesktopBefore',
                                                      'inputDesktopAfter', 'foregroundUnchanged', 'trayRecordsUnchanged',
                                                      'trayRecordStateUnchanged', 'desktopHandleClosed', 'desktopGone')}, indent=1))
    return 0 if record['pass'] else REFUSED


def command_run(arguments):
    if '--' not in arguments or '--record' not in arguments[:arguments.index('--')]:
        raise SystemExit('usage: run --record FILE -- EXE [ARG...]')
    filename = os.path.abspath(arguments[arguments.index('--record') + 1])
    executable, *rest = arguments[arguments.index('--') + 1:]
    if not os.path.isabs(executable) or not os.path.isfile(executable):
        raise SystemExit('EXE must be an absolute path to a file')
    record = {'command': 'run', 'executable': executable, 'phase': 'checking'}
    handle, target = checked_desktop(record, os.path.dirname(filename))
    if record['problems']:
        record['phase'] = 'refused'
        finish(record, handle)
        write_record(filename, record)
        return REFUSED
    job = K.CreateJobObjectW(None, None)
    limits = JOB_LIMITS()
    limits.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    try:
        if not job or not K.SetInformationJobObject(job, 9, C.byref(limits), C.sizeof(limits)):
            raise OSError('Job setup failed: ' + str(C.get_last_error()))
        process = start(executable, rest, target, 0x4, True)  # CREATE_SUSPENDED: it joins the Job before it runs.
        if not K.AssignProcessToJobObject(job, process.hProcess):
            error = C.get_last_error()
            K.TerminateProcess(process.hProcess, 1)
            raise OSError('Job assignment failed: ' + str(error))
    except OSError as error:
        record.update({'phase': 'failed', 'error': str(error)})
        finish(record, handle)
        write_record(filename, record)
        return FAILED
    record.update({'phase': 'running', 'pid': process.dwProcessId})
    write_record(filename, record)
    K.ResumeThread(process.hThread)
    code = wait(process)
    limits.LimitFlags = 0
    released = bool(K.SetInformationJobObject(job, 9, C.byref(limits), C.sizeof(limits)))
    if released:
        K.CloseHandle(job)
    record.update({'phase': 'exited', 'exitCode': code, 'jobReleased': released})
    finish(record, handle)
    write_record(filename, record)
    if not released:
        return NOT_RELEASED
    return code - (1 << 32) if code >= 1 << 31 else code  # Windows codes above 0x7FFFFFFF, as Python can pass them on.


def command_windows(arguments):
    folder = os.path.abspath(arguments[arguments.index('--under') + 1]).lower().rstrip('\\') + '\\'
    name = arguments[arguments.index('--desktop') + 1] if '--desktop' in arguments else None
    handle = U.OpenDesktopW(name, 0, False, 0x0041) if name else None
    if name and not handle:
        raise SystemExit('No such desktop: ' + name)
    try:
        windows = top_level_windows(handle)
    finally:
        if handle:
            U.CloseDesktop(handle)
    matching = [item for item in windows if (item['image'] or '').lower().startswith(folder)]
    print(json.dumps({'desktop': name or object_name(U.GetThreadDesktop(K.GetCurrentThreadId())), 'topLevelWindows': len(windows),
                      'matching': matching}, indent=1))
    return 0


def main(arguments):
    if arguments[:1] == ['probe']:
        with open(arguments[1], 'w', encoding='utf-8') as out:
            json.dump(survey(True, arguments[2]), out)
        return 0
    if arguments[:1] == ['check']:
        return command_check(arguments[1:])
    if arguments[:1] == ['run']:
        return command_run(arguments[1:])
    if arguments[:1] == ['windows'] and '--under' in arguments:
        return command_windows(arguments[1:])
    if arguments[:1] == ['snapshot']:
        print(json.dumps(tray_records(), indent=1))
        return 0
    raise SystemExit(__doc__)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
