"""Hold a process's exit with a debugger. Test and QA harness only; the app never uses it.

A process whose exit event a debugger has not continued stays unsignalled after TerminateProcess: WaitForSingleObject
reports it running, as an engine part still finishing a disk operation does. That is what the broker's start-time
check of a leftover record sees (engine_host.previous_session_closing). The Job's active count, however, drops at once
(measured 2026-11-18), so this cannot stand in for a member the broker's own closure wait counts.

Modes:
  exit    continue every debug event except the process's exit, which is held until released.
  freeze  continue nothing: the whole process stops at once. Holding the broker this way lets the shell's own wait
          (closure wait + 1 s) run out, with the quit dialog's ending state on screen the whole time.

Command line (Futaba's harness; same user, no elevation):
  python -B -I tests/debug_hold.py --pid <pid> [--mode exit|freeze] [--seconds <s>]
                                   [--write-record <locks folder> [--age <s>]]
It prints "held <pid>" once attached and releases after --seconds (default 60) or when its stdin closes.
--write-record also writes locks/leftover-<random owner>.json naming that process (PID and creation time), written
--age seconds ago (default 0; 180 shows the 2-minute screen), as a broker leaves it after its closure wait. The next
start then shows "The previous session is still closing." until the hold ends. The record is not removed here: the
next start that finds the process gone removes it.
"""
import argparse
import ctypes as C
from pathlib import Path
from ctypes import wintypes as W
import sys
import threading
import time

K = C.WinDLL('kernel32', use_last_error=True)


def _api(name, result, *args):
    function = getattr(K, name)
    function.restype, function.argtypes = result, list(args)
    return function


_attach = _api('DebugActiveProcess', W.BOOL, W.DWORD)
_detach = _api('DebugActiveProcessStop', W.BOOL, W.DWORD)
_kill_on_exit = _api('DebugSetProcessKillOnExit', W.BOOL, W.BOOL)
_wait_event = _api('WaitForDebugEvent', W.BOOL, C.c_void_p, W.DWORD)
_continue = _api('ContinueDebugEvent', W.BOOL, W.DWORD, W.DWORD, W.DWORD)
_close = _api('CloseHandle', W.BOOL, W.HANDLE)
_open = _api('OpenProcess', W.HANDLE, W.DWORD, W.BOOL, W.DWORD)
_times = _api('GetProcessTimes', W.BOOL, W.HANDLE, C.POINTER(W.FILETIME), C.POINTER(W.FILETIME),
              C.POINTER(W.FILETIME), C.POINTER(W.FILETIME))
EXCEPTION, CREATE_PROCESS, EXIT_PROCESS, LOAD_DLL = 1, 3, 5, 6
CONTINUE, NOT_HANDLED, BREAKPOINT = 0x00010002, 0x80010001, 0x80000003


class Hold:
    """Debug `pid` from a private thread (Windows ties a debuggee to the thread that attached)."""

    def __init__(self, pid, mode='exit'):
        if mode not in ('exit', 'freeze'):
            raise ValueError('mode')
        self.pid, self.mode, self.error = pid, mode, None
        self.attached, self.exit_held, self._release = threading.Event(), threading.Event(), threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        if not self.attached.wait(10) or self.error is not None:
            self.release()
            raise OSError(self.error or 0, 'Debugger could not hold process %d' % pid)

    def release(self):
        self._release.set()
        self._thread.join(10)

    def _run(self):
        if not _attach(self.pid):
            self.error = C.get_last_error()
            self.attached.set()
            return
        _kill_on_exit(False)  # This harness ending never ends the process it held.
        event, pending = C.create_string_buffer(256), None
        while True:
            if pending is not None:
                if not self._release.wait(0.1):
                    continue
                _continue(pending[0], pending[1], CONTINUE)
                if not pending[2]:
                    _detach(self.pid)
                return
            if not _wait_event(event, 100):
                if self._release.is_set():
                    _detach(self.pid)
                    return
                continue
            code, pid, tid = (W.DWORD.from_buffer(event, offset).value for offset in (0, 4, 8))
            if code in (CREATE_PROCESS, LOAD_DLL):
                handle = C.c_void_p.from_buffer(event, 16).value
                if handle:
                    _close(handle)
            if self.mode == 'freeze':
                pending = (pid, tid, False)
                self.attached.set()
                continue
            if code == EXIT_PROCESS:
                pending = (pid, tid, True)
                self.exit_held.set()
                continue
            status = CONTINUE
            if code == EXCEPTION:
                if W.DWORD.from_buffer(event, 16).value == BREAKPOINT:
                    self.attached.set()  # The break-in Windows injects once attached.
                else:
                    status = NOT_HANDLED
            _continue(pid, tid, status)


def created(pid):
    """The process's creation time (FILETIME, 100 ns), as engine_host.created reads it."""
    handle = _open(0x1000, False, pid)
    if not handle:
        raise OSError(C.get_last_error(), 'Open process %d' % pid)
    try:
        times = [W.FILETIME() for _ in range(4)]
        if not _times(handle, *[C.byref(value) for value in times]):
            raise OSError(C.get_last_error(), 'Process times')
        return (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
    finally:
        _close(handle)


def write_record(locks, pid, age):
    """locks/leftover-<owner>.json naming `pid`, as engine_host.record_leftover writes it."""
    import json
    import secrets
    owner = secrets.token_hex(32)
    folder = Path(locks)
    folder.mkdir(parents=True, exist_ok=True)
    record = folder / ('leftover-' + owner + '.json')
    record.write_text(json.dumps({'schema': 1, 'owner': owner, 'written': time.time() - age,
                                  'members': [[pid, created(pid)]]}), encoding='utf-8')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--mode', choices=('exit', 'freeze'), default='exit')
    parser.add_argument('--seconds', type=float, default=60.0)
    parser.add_argument('--write-record', metavar='LOCKS')
    parser.add_argument('--age', type=float, default=0.0)
    options = parser.parse_args()
    hold = Hold(options.pid, options.mode)
    print('held %d' % options.pid, flush=True)
    if options.write_record:
        print('record %s' % write_record(options.write_record, options.pid, options.age), flush=True)
    done = threading.Event()
    threading.Thread(target=lambda: (sys.stdin.read(), done.set()), daemon=True).start()
    done.wait(options.seconds)
    hold.release()
    print('released %d' % options.pid, flush=True)


if __name__ == '__main__':
    main()
