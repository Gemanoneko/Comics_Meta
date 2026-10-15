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
class FileInfo(C.Structure):
    _fields_ = [('attributes', W.DWORD), ('created', W.FILETIME), ('accessed', W.FILETIME),
        ('written', W.FILETIME), ('volume', W.DWORD), ('size_high', W.DWORD),
        ('size_low', W.DWORD), ('links', W.DWORD), ('index_high', W.DWORD), ('index_low', W.DWORD)]

def api(name, result, *args):
    function = getattr(K, name)
    function.restype, function.argtypes = result, list(args)
    return function

close = api('CloseHandle', W.BOOL, HANDLE)
create_file = api('CreateFileW', HANDLE, W.LPCWSTR, W.DWORD, W.DWORD, C.c_void_p, W.DWORD, W.DWORD, HANDLE)
read_file = api('ReadFile', W.BOOL, HANDLE, C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.c_void_p)
final_path = api('GetFinalPathNameByHandleW', W.DWORD, HANDLE, W.LPWSTR, W.DWORD, W.DWORD)
file_info = api('GetFileInformationByHandle', W.BOOL, HANDLE, C.POINTER(FileInfo))
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

def handle_identity(handle):
    info = FileInfo()
    require(file_info(handle, C.byref(info)), 'Held file identity')
    return (info.volume, info.index_high, info.index_low)

def path_identity(filename):
    # Legitimate readers must share the existing logger's write access; the
    # reader still omits SHARE_DELETE. Never reopen a writer or truncate logs.
    handle = create_file(str(filename), 0x80000000, 3, None, 3, 0x00200000, None)
    if handle == INVALID:raise OSError(C.get_last_error(), 'Read live log identity')
    try:return handle_identity(handle)
    finally:close(handle)

class LockedFiles:
    def __init__(self):
        self.handles = []
        self.directories = set()
        self.identities = {}

    def open(self, filename, expected=None, directory=False):
        filename = str(filename)
        if not Path(filename).is_absolute() or any(x in filename for x in ('\0', '\r', '\n')):
            raise ValueError('Invalid absolute path')
        # Hold every ancestor against replacement; reject reparse points.
        for parent in reversed(Path(filename).parents):
            self._open(str(parent), directory=True)
        handle = self._open(filename, directory=directory)
        if directory:
            return handle
        chunks = []
        while True:
            buffer, size = C.create_string_buffer(65536), W.DWORD()
            require(read_file(handle, buffer, len(buffer), C.byref(size), None), 'Read locked source')
            if not size.value:
                break
            chunks.append(buffer.raw[:size.value])
        raw = b''.join(chunks)
        if expected is not None and hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('Pinned file hash mismatch: ' + filename)
        return raw

    def _open(self, filename, directory):
        if directory and os.path.normcase(filename) in self.directories:return None
        if os.stat(filename, follow_symlinks=False).st_file_attributes & 0x400:
            raise ValueError('Reparse path refused: ' + filename)
        # Metadata-only ancestor opens do not establish deny-delete sharing.
        handle = create_file(filename, 0x80000000, 1, None, 3,
            0x00200000 | (0x02000000 if directory else 0), None)
        if handle == INVALID:
            raise OSError(C.get_last_error(), 'Open share-read-only: ' + filename)
        self.handles.append(handle)
        info = FileInfo()
        require(file_info(handle, C.byref(info)), 'Held path attributes')
        if info.attributes & 0x400 or bool(info.attributes & 0x10) != directory:
            raise ValueError('Unsafe held path type: ' + filename)
        self.identities[os.path.normcase(filename)] = (info.volume, info.index_high, info.index_low)
        if directory:self.directories.add(os.path.normcase(filename))
        buffer = C.create_unicode_buffer(32768)
        n = final_path(handle, buffer, len(buffer), 0)
        require(0 < n < len(buffer), 'Final handle identity')
        actual = buffer.value.removeprefix('\\?\\')
        # Device prefix is exactly \\?\, not an arbitrary alias.
        if buffer.value.startswith('\\\\?\\'):
            actual = buffer.value[4:]
        if os.path.normcase(actual.rstrip('\\')) != os.path.normcase(filename.rstrip('\\')):
            raise ValueError('Canonical handle path differs: ' + filename)
        return handle

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        for handle in reversed(self.handles):
            close(handle)

def active(job):
    accounting = Accounting()
    require(query_job(job, 1, C.byref(accounting), C.sizeof(accounting), None), 'Query owned job')
    return accounting.active

def owned_job(executable, arguments, cwd, logs, deadline, lease, *, _assignment_supported=True, input_bytes=None, environment_override=None, retain_outputs=None):
    """Atomic Job + bounded anonymous pipes; one deadline includes final drains."""
    import threading
    job=create_job(None,None);require(job,'Create private job')
    process=ProcessInfo();attributes=None;child_handles=[];read_handles=[];log_handles=[];evidence_handles=[];threads=[]
    locks=LockedFiles();state={'bytes':0,'overflow':False,'error':None};mutex=threading.Lock();captured=[[],[]];reason=None
    pipe=api('CreatePipe',W.BOOL,C.POINTER(HANDLE),C.POINTER(HANDLE),C.c_void_p,W.DWORD)
    set_handle=api('SetHandleInformation',W.BOOL,HANDLE,W.DWORD,W.DWORD)
    cap=16*1024*1024
    try:
        limits=Limits();limits.basic.flags=0x2000
        require(set_job(job,9,C.byref(limits),C.sizeof(limits)),'Set kill-on-close')
        logs=Path(logs);locks.open(logs.parent,directory=True)
        logs.mkdir();locks.open(logs,directory=True)
        log_identities=[]
        security=Security(C.sizeof(Security),None,True)
        stdin_name='NUL' if input_bytes is None else str(logs/'stdin.json')
        stdin=create_file(stdin_name,0x80000000 if input_bytes is None else 0xC0000000,1,C.byref(security),3 if input_bytes is None else 1,0,None)
        if stdin==INVALID:raise OSError(C.get_last_error(),'Owned stdin')
        child_handles.append(stdin)
        if input_bytes is not None:handle_write(stdin,input_bytes);require(seek_file(stdin,0,None,0),'Rewind input')
        for name in ['stdout.log','stderr.log']:
            read,write=HANDLE(),HANDLE()
            require(pipe(C.byref(read),C.byref(write),C.byref(security),4096),'Owned anonymous pipe')
            require(set_handle(read,1,0),'Parent reader not inherited')
            read_handles.append(read.value);child_handles.append(write.value)
            log=create_file(str(logs/name),0xC0000000,1,None,1,0x00200000,None)
            if log==INVALID:raise OSError(C.get_last_error(),'Bounded evidence output')
            log_handles.append(log)
            identity=handle_identity(log)
            if path_identity(logs/name)!=identity:raise RuntimeError('New log path identity differs')
            log_identities.append(identity)
        size=SIZE();init_attributes(None,2,0,C.byref(size));attributes=C.create_string_buffer(size.value)
        require(init_attributes(attributes,2,0,C.byref(size)),'Initialize attributes')
        inherit=(HANDLE*3)(*child_handles)
        require(update_attributes(attributes,0,0x20002,inherit,C.sizeof(inherit),None,None),'Only stdio inherited')
        if not _assignment_supported:raise OSError('Atomic Job assignment unavailable')
        job_list=(HANDLE*1)(job)
        require(update_attributes(attributes,0,0x2000D,job_list,C.sizeof(job_list),None,None),'Atomic Job list required')
        startup=StartupEx();startup.startup.cb=C.sizeof(startup);startup.startup.flags=0x101
        startup.startup.stdin,startup.startup.stdout,startup.startup.stderr=child_handles
        startup.attributes=C.cast(attributes,C.c_void_p)
        scratch=str(logs.parent)
        environment={'SystemRoot':r'C:\Windows','WINDIR':r'C:\Windows','ComSpec':r'C:\Windows\System32\cmd.exe','PATHEXT':'.COM;.EXE;.BAT;.CMD',
            'PATH':r'C:\Program Files\nodejs;C:\Windows\System32','TEMP':scratch,'TMP':scratch,'USERPROFILE':scratch,'HOME':scratch,'npm_config_cache':str(Path(scratch)/'npm-cache')}
        if environment_override is not None:
            if not isinstance(environment_override,dict) or not environment_override or any(not isinstance(k,str) or not isinstance(v,str) or not k or '=' in k or '\0' in k+v for k,v in environment_override.items()):raise ValueError('Invalid fixed child environment')
            if len({k.upper() for k in environment_override})!=len(environment_override):raise ValueError('Duplicate child environment key')
            environment=dict(environment_override)
        block=C.create_unicode_buffer('\0'.join(k+'='+v for k,v in sorted(environment.items(),key=lambda x:x[0].upper()))+'\0\0')
        if time.monotonic()>=deadline-5:raise TimeoutError('Setup consumed total budget')
        if lease is not None and not lease():raise RuntimeError('Original owner closed before launch')
        command=C.create_unicode_buffer(subprocess.list2cmdline([str(executable),*arguments]))
        require(create_process(str(executable),command,None,None,True,0x08000000|0x4|0x400|0x80000,block,str(cwd),C.byref(startup),C.byref(process)),'Create hidden suspended owned child')
        def drain(index):
            try:
                while True:
                    buffer,count=C.create_string_buffer(65536),W.DWORD()
                    if not read_file(read_handles[index],buffer,len(buffer),C.byref(count),None):
                        if C.get_last_error()==109:return
                        raise OSError(C.get_last_error(),'Owned pipe drain')
                    if not count.value:return
                    with mutex:
                        remaining=cap-state['bytes'];accepted=min(count.value,max(0,remaining));state['bytes']+=accepted
                        if accepted:
                            chunk=buffer.raw[:accepted];captured[index].append(chunk);handle_write(log_handles[index],chunk)
                        if count.value>accepted:
                            state['overflow']=True
                            require(terminate_job(job,124),'Output cap closes owned producer')
                            return
            except BaseException as error:
                state['error']=str(error)
                terminate_job(job,125)
        for index in range(2):
            thread=threading.Thread(target=drain,args=(index,),daemon=True);threads.append(thread);thread.start()
        if time.monotonic()>=deadline-5:raise TimeoutError('Deadline before resume')
        if lease is not None and not lease():raise RuntimeError('Original owner closed before resume')
        require(resume_thread(process.thread)!=0xFFFFFFFF,'Resume already assigned child')
        # Parent closes writers immediately. Only owned descendants can keep a
        # pipe open; abrupt parent death closes the noninherited Job handle.
        for index in [1,2]:close(child_handles[index]);child_handles[index]=None
        identity=create_file(str(logs/'identity.json'),0xC0000000,1,None,1,0x00200000,None)
        if identity==INVALID:raise OSError(C.get_last_error(),'Owned identity')
        evidence_handles.append(identity)
        handle_write(identity,json.dumps({'runner_pid':os.getpid(),'root_pid':process.pid}).encode())
        while active(job):
            if lease is not None and not lease():
                reason='owner-exited';require(terminate_job(job,125),'Original owner closes owned tree');break
            if time.monotonic()>=deadline-5:
                reason='deadline';require(terminate_job(job,124),'Deadline closes owned tree');break
            time.sleep(0.01)
        closure_end=min(deadline,time.monotonic()+5)
        while active(job) and time.monotonic()<closure_end:time.sleep(0.01)
        if active(job):raise RuntimeError('Descendant closure unknown')
        for thread in threads:thread.join(max(0,deadline-time.monotonic()))
        if any(thread.is_alive() for thread in threads):raise RuntimeError('Stream closure unknown')
        if state['error']:raise RuntimeError('Drain failed: '+state['error'])
        for index,name in enumerate(['stdout.log','stderr.log']):
            if handle_identity(log_handles[index])!=log_identities[index] or path_identity(logs/name)!=log_identities[index]:
                raise RuntimeError('Live log path identity changed')
            if handle_read(log_handles[index],cap)!=b''.join(captured[index]):
                raise RuntimeError('Held log bytes differ from captured stream')
        if time.monotonic()>deadline:raise TimeoutError('Postcondition exceeded total budget')
        require(wait_process(process.process,max(0,int((deadline-time.monotonic())*1000)))==0,'Root terminated')
        code=W.DWORD();require(exit_code(process.process,C.byref(code)),'Root exit identity')
        if code.value==259:raise RuntimeError('Root still active')
        if retain_outputs is not None:
            outputs=[(logs/name,log_handles[index]) for index,name in enumerate(['stdout.log','stderr.log'])]
            outputs.append((logs/'identity.json',identity))
            retain_outputs([(str(filename),handle_identity(handle),hashlib.sha256(handle_read(handle,cap)).hexdigest()) for filename,handle in outputs])
        return {'reason':'output-limit' if state['overflow'] else reason or 'completed','root_pid':process.pid,'root_exit':code.value,'active_after':0,
            'elapsed_ms':round((time.monotonic()-STARTED)*1000),'production_deadline_ms':600000,'output_bytes':state['bytes'],
            'log_identities':{name:list(log_identities[index]) for index,name in enumerate(['stdout.log','stderr.log'])},
            'stdout':b''.join(captured[0]).decode('utf-8',errors='replace'),'stderr':b''.join(captured[1]).decode('utf-8',errors='replace')}
    finally:
        if process.process:terminate_process(process.process,125)
        require(terminate_job(job,125),'Fail-closed termination')
        while active(job) and time.monotonic()<deadline:time.sleep(0.01)
        known=active(job)==0
        for handle in child_handles:
            if handle:close(handle)
        for thread in threads:thread.join(max(0,deadline-time.monotonic()))
        if any(thread.is_alive() for thread in threads):known=False
        for handle in read_handles+log_handles+evidence_handles:close(handle)
        close(job)
        if process.thread:close(process.thread)
        if process.process:close(process.process)
        if attributes is not None:delete_attributes(attributes)
        locks.__exit__()
        if not known:raise RuntimeError('Owned tree/drain closure unproved')

