"""Isolated Windows fixed-contract candidate; not deployed."""
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

PRODUCTION_DEADLINE_MS = 600000
CONTRACT_ID = 'guard-safety-selftests'
# Quit always closes the app (Sergei 2026-11-18). When the broker ends its Job it terminates it again every
# RETERMINATE_EVERY seconds for up to the closure wait the shell passes (--closure-wait, desktop/engine.cjs
# CLOSURE_WAIT_S: the one constant the quit dialog names too). A part that is still finishing a disk operation after
# that is named in locks/leftover-<owner>.json and the broker exits with CLOSURE_LEFTOVER; the shell exits anyway, and
# the next broker re-checks the record before it starts anything (previous_session_closing).
# Until 0.6.7 this code meant a refused closure (code review v0.6.6 T1), and the shell refused Quit and Retry over it.
CLOSURE_LEFTOVER = 124
RETERMINATE_EVERY = 5.0  # Seconds the Job is given to empty after each termination.
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
open_process = api('OpenProcess', HANDLE, W.DWORD, W.BOOL, W.DWORD)
process_times = api('GetProcessTimes', W.BOOL, HANDLE, C.POINTER(W.FILETIME), C.POINTER(W.FILETIME), C.POINTER(W.FILETIME), C.POINTER(W.FILETIME))
QUERY_LIMITED, SYNCHRONIZE, TERMINATE = 0x1000, 0x100000, 0x0001
MAX_MEMBERS = 1024

class ProcessIds(C.Structure):
    _fields_ = [('assigned', W.DWORD), ('listed', W.DWORD), ('ids', C.c_size_t * MAX_MEMBERS)]

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
    parser.add_argument('--closure-wait',type=float,required=True)  # Seconds; desktop/engine.cjs CLOSURE_WAIT_S.
    options=parser.parse_args()
    if not 1<=options.port<=65535 or options.parent_pid<=0:raise ValueError('Invalid owner')
    if not 0<options.closure_wait<=600:raise ValueError('Invalid closure wait')
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
    proc=ProcessInfo(); attributes=None; result=None; failure=None
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
                forced=True  # The Job is terminated below, with every other path.
                break
        if forced:
            result=125
        else:
            exit_value=W.DWORD();require(exit_code(proc.process,C.byref(exit_value)),'Owned engine exit')
            result=exit_value.value if exit_value.value in (0,75) else 126
    except BaseException as error:
        failure=error
    # Every path ends here: whatever happened above, the Job is terminated and its own count decides closure.
    owner=os.environ.get('COMICS_META_CLAIM_OWNER','')
    try:closed=close_job(job,options.closure_wait)
    except OSError:closed=False  # A count that cannot be read is not proof.
    if closed:
        forget_leftover(owner)
        try:
            import library_lock
            library_lock.retire_engine_claims(owner)
        except Exception as error:
            # The Job is proven empty, so these claims are unlocked and the next claimant sweeps them. A retirement
            # failure must not hide the closure the broker proved (code review M3: it raised, exit code 1).
            note('Engine claims were not retired: '+type(error).__name__+' '+str(error))
    else:
        record_leftover(job,owner,options.closure_wait)  # Before the Job handle closes: its member list is read here.
    close(job)
    if proc.thread:close(proc.thread)
    if proc.process:close(proc.process)
    if attributes is not None:delete_attributes(attributes)
    close(parent)
    if not closed:
        if failure is not None:
            import traceback
            note(''.join(traceback.format_exception(failure)).rstrip())
        return CLOSURE_LEFTOVER
    if failure is not None:raise failure  # The Job is empty: exit code 1 with the cause in engine.log, as before.
    return result

def note(line):
    """One line to engine.log (stderr). A log that cannot be written must not change the exit code."""
    try:print(line,file=sys.stderr,flush=True)
    except (OSError,ValueError,AttributeError):pass

def close_job(job,wait):
    """Terminate the Job, and again every RETERMINATE_EVERY seconds, until it counts no member or `wait` seconds have
    passed. True once it is empty; raises OSError if the count cannot be read."""
    deadline=time.monotonic()+wait
    while True:
        if not terminate_job(job,125):
            # The count below still decides closure; until 0.6.7 a failed termination went unnoticed.
            note('Engine Job termination failed (Windows error '+str(C.get_last_error())+').')
        if job_emptied(job,min(RETERMINATE_EVERY,max(0.0,deadline-time.monotonic()))):return True
        if time.monotonic()>=deadline:return False
        note('Owned engine descendants remain after termination; terminating again.')

def job_emptied(job,seconds):
    """True once the Job counts no active process, within `seconds`; raises OSError if it cannot be read."""
    until=time.monotonic()+seconds
    while active_engine(job):
        if time.monotonic()>=until:return False
        time.sleep(.01)
    return True

def active_engine(job):
    counts=Accounting()
    require(query_job(job,1,C.byref(counts),C.sizeof(counts),None),'Engine descendants')
    return counts.active

def lock_dir():
    """The library claims' lock folder (library_lock.lock_dir), read without importing the engine."""
    value=os.environ.get('COMICS_META_LOCK_DIR','').strip()
    if value:return Path(value)
    local=os.environ.get('LOCALAPPDATA')
    return (Path(local) if local else Path.home()/'.local'/'state')/'ComicsMeta'/'locks'

def leftover_path(owner):
    return lock_dir()/('leftover-'+owner+'.json')

def open_member(pid,rights):
    """A handle on process `pid`, or None when no such process exists; raises OSError when it cannot be opened."""
    handle=open_process(rights,False,pid)
    if handle:return handle
    error=C.get_last_error()
    if error==87:return None  # ERROR_INVALID_PARAMETER: no process has this ID.
    raise OSError(error,'Open process '+str(pid))

def created(handle):
    """The process's creation time (FILETIME, 100 ns units): with its PID, it names one process for good."""
    times=[W.FILETIME() for _ in range(4)]
    require(process_times(handle,*[C.byref(value) for value in times]),'Process creation time')
    return (times[0].dwHighDateTime<<32)|times[0].dwLowDateTime

def job_members(job):
    """[[pid, creation time]] of the Job's members, or None when the list cannot be read whole."""
    ids=ProcessIds()
    if not query_job(job,3,C.byref(ids),C.sizeof(ids),None) or ids.listed!=ids.assigned:return None
    members=[]
    for pid in ids.ids[:ids.listed]:
        try:handle=open_member(int(pid),QUERY_LIMITED)
        except OSError:return None
        if handle is None:continue  # Ended since it was listed.
        try:members.append([int(pid),created(handle)])
        except OSError:return None
        finally:close(handle)
    return members

def record_leftover(job,owner,wait):
    """Name the parts still running in locks/leftover-<owner>.json. The shell exits anyway; the next broker re-checks
    the record before it starts anything. Without a member list the next check falls back to the engine's claims."""
    try:members=job_members(job)
    except OSError:members=None
    if not re.fullmatch('[0-9a-f]{64}',owner or ''):
        import secrets
        owner=secrets.token_hex(32)
    described='no member list' if members is None else ', '.join('pid '+str(pid) for pid,_ in members) or 'none listed'
    note('Engine parts still running after the '+format(wait,'g')+' s closure wait ('+described+'); recorded for the next start.')
    path=leftover_path(owner)
    try:
        path.parent.mkdir(parents=True,exist_ok=True)
        temporary=path.with_suffix('.tmp')
        temporary.write_text(json.dumps({'schema':1,'owner':owner,'written':time.time(),'members':members}),encoding='utf-8')
        os.replace(temporary,path)
    except OSError as error:
        note('Leftover record not written: '+type(error).__name__+' '+str(error))

def forget_leftover(owner):
    """A Job proven empty leaves no record: remove the provisional one the shell writes when it stops waiting."""
    if not re.fullmatch('[0-9a-f]{64}',owner or ''):return
    try:leftover_path(owner).unlink(missing_ok=True)
    except OSError as error:note('Leftover record not removed: '+type(error).__name__+' '+str(error))

if __name__=='__main__':raise SystemExit(main())
