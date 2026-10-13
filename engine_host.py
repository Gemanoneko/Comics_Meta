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
    parent=api('OpenProcess',HANDLE,W.DWORD,W.BOOL,W.DWORD)(0x100000,False,options.parent_pid)
    require(parent,'Hold shell parent identity')
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
        set_handle=api('SetHandleInformation',W.BOOL,HANDLE,W.DWORD,W.DWORD)
        for handle in stdio:require(set_handle(handle,1,1),'Inherit owned stdio')
        require(update_attributes(attributes,0,0x20002,stdio,C.sizeof(stdio),None,None),'Only service stdio inherited')
        startup=StartupEx();startup.startup.cb=C.sizeof(startup);startup.startup.flags=0x101
        startup.startup.stdin,startup.startup.stdout,startup.startup.stderr=stdio
        startup.attributes=C.cast(attributes,C.c_void_p)
        code=Path(__file__).resolve().parent
        argv=[sys.executable,'-B',str(code/'app.py'),'--no-browser','--port',str(options.port)]
        command=C.create_unicode_buffer(subprocess.list2cmdline(argv))
        if wait_process(parent,0)!=0x102:raise RuntimeError('Shell owner already exited')
        require(create_process(sys.executable,command,None,None,True,0x08000000|0x4|0x80000,None,str(code),C.byref(startup),C.byref(proc)),'Owned engine creation')
        require(resume_thread(proc.thread)!=0xFFFFFFFF,'Resume owned engine')
        while wait_process(proc.process,100)==0x102:
            if wait_process(parent,0)!=0x102:
                require(terminate_job(job,125),'Shell exit closes only owned engine tree')
                break
        exit_value=W.DWORD();require(exit_code(proc.process,C.byref(exit_value)),'Owned engine exit')
        return exit_value.value
    finally:
        if job:
            terminate_job(job,125)
            until=time.monotonic()+5
            while active_engine(job) and time.monotonic()<until:time.sleep(.01)
            close(job)
        if proc.thread:close(proc.thread)
        if proc.process:close(proc.process)
        if attributes is not None:delete_attributes(attributes)
        close(parent)

def active_engine(job):
    counts=Accounting()
    require(query_job(job,1,C.byref(counts),C.sizeof(counts),None),'Engine descendants')
    return counts.active

if __name__=='__main__':raise SystemExit(main())
