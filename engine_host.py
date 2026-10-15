"""Isolated Windows fixed-contract candidate; not deployed."""
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

PRODUCTION_DEADLINE_MS = 600000
CONTRACT_ID = 'guard-safety-selftests'
STARTED = globals().get('BOOTSTRAP_STARTED', time.monotonic())
if os.name != 'nt' or C.sizeof(C.c_void_p) != 8:
    raise RuntimeError('Only reviewed Windows x64 is supported')
K = C.WinDLL('kernel32', use_last_error=True)
HANDLE = W.HANDLE
SIZE = C.c_size_t
INVALID = C.c_void_p(-1).value

class Security(C.Structure):
    _fields_ = [('size', W.DWORD), ('descriptor', C.c_void_p), ('inherit', W.BOOL)]
class BasicLimit(C.Structure):
    _fields_ = [('processTime', C.c_longlong), ('jobTime', C.c_longlong), ('flags', W.DWORD), ('minWorking', SIZE), ('maxWorking', SIZE), ('activeLimit', W.DWORD), ('affinity', SIZE), ('priority', W.DWORD), ('scheduling', W.DWORD)]
class Limits(C.Structure):
    _fields_ = [('basic', BasicLimit), ('io', C.c_ulonglong * 6), ('processMemory', SIZE), ('jobMemory', SIZE), ('peakProcess', SIZE), ('peakJob', SIZE)]
class Accounting(C.Structure):
    _fields_ = [('times', C.c_longlong * 4), ('faults', W.DWORD), ('total', W.DWORD), ('active', W.DWORD), ('terminated', W.DWORD)]
class Startup(C.Structure):
    _fields_ = [('cb', W.DWORD), ('reserved', W.LPWSTR), ('desktop', W.LPWSTR), ('title', W.LPWSTR), ('x', W.DWORD), ('y', W.DWORD), ('width', W.DWORD), ('height', W.DWORD), ('xchars', W.DWORD), ('ychars', W.DWORD), ('fill', W.DWORD), ('flags', W.DWORD), ('show', W.WORD), ('reservedSize', W.WORD), ('reservedBytes', C.c_void_p), ('stdin', HANDLE), ('stdout', HANDLE), ('stderr', HANDLE)]
class StartupEx(C.Structure):
    _fields_ = [('startup', Startup), ('attributes', C.c_void_p)]
class ProcessInfo(C.Structure):
    _fields_ = [('process', HANDLE), ('thread', HANDLE), ('pid', W.DWORD), ('tid', W.DWORD)]

def api(name, result, *args):
    function = getattr(K, name)
    function.restype, function.argtypes = result, list(args)
    return function

close = api('CloseHandle', W.BOOL, HANDLE)
create_file = api('CreateFileW', HANDLE, W.LPCWSTR, W.DWORD, W.DWORD, C.c_void_p, W.DWORD, W.DWORD, HANDLE)
read_file = api('ReadFile', W.BOOL, HANDLE, C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.c_void_p)
final_path = api('GetFinalPathNameByHandleW', W.DWORD, HANDLE, W.LPWSTR, W.DWORD, W.DWORD)
create_job = api('CreateJobObjectW', HANDLE, C.c_void_p, W.LPCWSTR)
set_job = api('SetInformationJobObject', W.BOOL, HANDLE, C.c_int, C.c_void_p, W.DWORD)
query_job = api('QueryInformationJobObject', W.BOOL, HANDLE, C.c_int, C.c_void_p, W.DWORD, C.c_void_p)
assign_job = api('AssignProcessToJobObject', W.BOOL, HANDLE, HANDLE)
terminate_job = api('TerminateJobObject', W.BOOL, HANDLE, W.UINT)
terminate_process = api('TerminateProcess', W.BOOL, HANDLE, W.UINT)
resume_thread = api('ResumeThread', W.DWORD, HANDLE)
wait_process = api('WaitForSingleObject', W.DWORD, HANDLE, W.DWORD)
exit_code = api('GetExitCodeProcess', W.BOOL, HANDLE, C.POINTER(W.DWORD))
init_attributes = api('InitializeProcThreadAttributeList', W.BOOL, C.c_void_p, W.DWORD, W.DWORD, C.POINTER(SIZE))
update_attributes = api('UpdateProcThreadAttribute', W.BOOL, C.c_void_p, W.DWORD, SIZE, C.c_void_p, SIZE, C.c_void_p, C.c_void_p)
delete_attributes = api('DeleteProcThreadAttributeList', None, C.c_void_p)
create_process = api('CreateProcessW', W.BOOL, W.LPCWSTR, W.LPWSTR, C.c_void_p, C.c_void_p, W.BOOL, W.DWORD, C.c_void_p, W.LPCWSTR, C.c_void_p, C.POINTER(ProcessInfo))
write_file = api('WriteFile', W.BOOL, HANDLE, C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.c_void_p)
seek_file = api('SetFilePointerEx', W.BOOL, HANDLE, C.c_longlong, C.c_void_p, W.DWORD)
truncate_file = api('SetEndOfFile', W.BOOL, HANDLE)

def handle_write(handle, raw):
    wrote = W.DWORD()
    require(write_file(handle, raw, len(raw), C.byref(wrote), None) and wrote.value == len(raw), 'Write exact owned bytes')

def handle_read(handle, maximum=1048576):
    require(seek_file(handle, 0, None, 0), 'Rewind held output')
    chunks = []
    total = 0
    while True:
        buffer, count = C.create_string_buffer(65536), W.DWORD()
        require(read_file(handle, buffer, len(buffer), C.byref(count), None), 'Read held output')
        if not count.value: return b''.join(chunks)
        total += count.value
        if total > maximum: raise ValueError('Owned output exceeds reviewed bound')
        chunks.append(buffer.raw[:count.value])

def lease_state(handle, state):
    require(seek_file(handle, 0, None, 0), 'Rewind lease state')
    handle_write(handle, state)
    require(truncate_file(handle), 'Truncate exact lease state')
    require(api('FlushFileBuffers', W.BOOL, HANDLE)(handle), 'Persist fail-closed state')

def require(ok, operation):
    if not ok:
        raise OSError(C.get_last_error(), operation)


# Production service ownership: no detached worker/browser may outlive this shell.
def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--parent-pid',type=int,required=True)
    parser.add_argument('--port',type=int,default=8765)
    options=parser.parse_args()
    if not 1<=options.port<=65535 or options.parent_pid<=0:raise ValueError('Invalid owner')
    if not os.environ.get('COMICS_META_STATE_ROOT') or not os.environ.get('COMICS_META_SHELL_TOKEN'):
        raise ValueError('A selected state root and shell identity are required')
    token=os.environ['COMICS_META_SHELL_TOKEN']
    if len(token)!=64 or any(c not in '0123456789abcdef' for c in token):raise ValueError('Invalid original shell nonce')
    parent=api('OpenProcess',HANDLE,W.DWORD,W.BOOL,W.DWORD)(0x100000,False,options.parent_pid)
    require(parent,'Hold shell parent identity')
    # The sole writer is the shell-created pipe; neither PID reuse nor a
    # recreated process can inherit that writer after the original shell exits.
    import secrets
    get_std=api('GetStdHandle',HANDLE,W.DWORD)
    owner_input=get_std(0xFFFFFFF6)
    peek=api('PeekNamedPipe',W.BOOL,HANDLE,C.c_void_p,W.DWORD,C.c_void_p,C.POINTER(W.DWORD),C.c_void_p)
    def available_owner_bytes():
        count=W.DWORD()
        if not peek(owner_input,None,0,None,C.byref(count),None):
            if C.get_last_error()==109:return None
            raise OSError(C.get_last_error(),'Original shell owner pipe status')
        return count.value
    expected=token.encode('ascii')
    supplied=b'';wanted=expected+b'\n';handshake_deadline=time.monotonic()+8
    try:
        while len(supplied)<len(wanted):
            if time.monotonic()>=handshake_deadline:raise TimeoutError('Original shell owner handshake deadline')
            count=available_owner_bytes()
            if count is None:raise RuntimeError('Original shell owner stream closed')
            if not count:time.sleep(.01);continue
            buffer=C.create_string_buffer(min(count,len(wanted)-len(supplied)));read=W.DWORD()
            require(read_file(owner_input,buffer,len(buffer),C.byref(read),None),'Read exact original shell nonce')
            if not read.value:raise RuntimeError('Original shell owner nonce EOF')
            supplied+=buffer.raw[:read.value]
        if not secrets.compare_digest(supplied,wanted):raise RuntimeError('Original shell owner stream unavailable')
    except BaseException:
        close(parent)
        raise
    def owner_stopped():
        # EOF or any control byte closes the owned tree fail-closed. Native
        # polling leaves no buffered-stdin daemon alive during clean shutdown.
        return available_owner_bytes()!=0
    job=create_job(None,None); require(job,'Create engine job')
    proc=ProcessInfo(); attributes=None
    try:
        limits=Limits();limits.basic.flags=0x2000
        require(set_job(job,9,C.byref(limits),C.sizeof(limits)),'Engine kill-on-close')
        size=SIZE();init_attributes(None,2,0,C.byref(size));attributes=C.create_string_buffer(size.value)
        require(init_attributes(attributes,2,0,C.byref(size)),'Engine attributes')
        joblist=(HANDLE*1)(job)
        require(update_attributes(attributes,0,0x2000D,joblist,C.sizeof(joblist),None,None),'Atomic engine Job required')
        get_std=api('GetStdHandle',HANDLE,W.DWORD)
        stdio=(HANDLE*3)(get_std(0xFFFFFFF6),get_std(0xFFFFFFF5),get_std(0xFFFFFFF4))
        inherited=(HANDLE*len(set(stdio)))(*dict.fromkeys(stdio))
        set_handle=api('SetHandleInformation',W.BOOL,HANDLE,W.DWORD,W.DWORD)
        for handle in stdio:require(set_handle(handle,1,1),'Inherit owned stdio')
        require(update_attributes(attributes,0,0x20002,inherited,C.sizeof(inherited),None,None),'Only service stdio inherited')
        startup=StartupEx();startup.startup.cb=C.sizeof(startup);startup.startup.flags=0x101
        startup.startup.stdin,startup.startup.stdout,startup.startup.stderr=stdio
        startup.attributes=C.cast(attributes,C.c_void_p)
        code=Path(__file__).resolve().parent
        argv=[sys.executable,'-B',str(code/'app.py'),'--no-browser','--port',str(options.port)]
        command=C.create_unicode_buffer(subprocess.list2cmdline(argv))
        if owner_stopped() or wait_process(parent,0)!=0x102:raise RuntimeError('Shell owner already exited')
        require(create_process(sys.executable,command,None,None,True,0x08000000|0x4|0x80000,None,str(code),C.byref(startup),C.byref(proc)),'Owned engine creation')
        require(resume_thread(proc.thread)!=0xFFFFFFFF,'Resume owned engine')
        forced=False
        while wait_process(proc.process,100)==0x102:
            if owner_stopped() or wait_process(parent,0)!=0x102:
                forced=True
                require(terminate_job(job,125),'Shell exit closes only owned engine tree')
                break
        if forced:
            until=time.monotonic()+5
            while active_engine(job) and time.monotonic()<until:time.sleep(.01)
            if active_engine(job):raise RuntimeError('Owned engine descendants remain')
            return 125
        exit_value=W.DWORD();require(exit_code(proc.process,C.byref(exit_value)),'Owned engine exit')
        return exit_value.value
    finally:
        closed=True
        if job:
            terminate_job(job,125)
            until=time.monotonic()+5
            while active_engine(job) and time.monotonic()<until:time.sleep(.01)
            closed=active_engine(job)==0
            close(job)
        if proc.thread:close(proc.thread)
        if proc.process:close(proc.process)
        if attributes is not None:delete_attributes(attributes)
        close(parent)
        if not closed:raise RuntimeError('Engine descendant closure unconfirmed')

def active_engine(job):
    counts=Accounting()
    require(query_job(job,1,C.byref(counts),C.sizeof(counts),None),'Engine descendants')
    return counts.active

if __name__=='__main__':raise SystemExit(main())
