"""Browser-worker-only private Job and exclusive dedicated Lens profile lease."""
import os
import sys
import time
from pathlib import Path
import app

_owner=None
_job=None
_query=None
_lease=None


class ClosureUnknown(SystemExit):
    """Exit the owner so Windows closes its private Job; never retry in-process."""


def enable():
    global _owner
    if Path(sys.argv[0]).resolve()!=(app.BASE/'browser_worker.py').resolve():
        raise ValueError('Lens registration requires the browser worker entry point.')
    _owner=os.getpid()


def own_descendants():
    global _job,_query
    if _owner!=os.getpid() or os.name!='nt':raise ValueError('Lens browser ownership is unavailable.')
    if _job is not None:return
    import ctypes
    from ctypes import wintypes as w
    class Limits(ctypes.Structure):
        _fields_=[('process_time',ctypes.c_int64),('job_time',ctypes.c_int64),('flags',w.DWORD),
                  ('min_ws',ctypes.c_size_t),('max_ws',ctypes.c_size_t),('active',w.DWORD),
                  ('affinity',ctypes.c_size_t),('priority',w.DWORD),('scheduling',w.DWORD)]
    class Counters(ctypes.Structure):
        _fields_=[(name,ctypes.c_uint64) for name in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]
    class Extended(ctypes.Structure):
        _fields_=[('limits',Limits),('io',Counters),('process_memory',ctypes.c_size_t),
                  ('job_memory',ctypes.c_size_t),('peak_process',ctypes.c_size_t),('peak_job',ctypes.c_size_t)]
    class Accounting(ctypes.Structure):
        _fields_=[(name,ctypes.c_int64) for name in ('user','kernel','period_user','period_kernel')]+[(name,w.DWORD) for name in ('faults','total','active','terminated')]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,w.LPCWSTR];kernel.CreateJobObjectW.restype=w.HANDLE
    kernel.SetInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD];kernel.SetInformationJobObject.restype=w.BOOL
    kernel.GetCurrentProcess.restype=w.HANDLE
    kernel.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE];kernel.AssignProcessToJobObject.restype=w.BOOL
    kernel.QueryInformationJobObject.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD,ctypes.c_void_p];kernel.QueryInformationJobObject.restype=w.BOOL
    kernel.CloseHandle.argtypes=[w.HANDLE];kernel.CloseHandle.restype=w.BOOL
    handle=kernel.CreateJobObjectW(None,None)
    limits=Extended();limits.limits.flags=0x2000
    if not handle:raise ValueError('Lens browser ownership is unavailable.')
    if not kernel.SetInformationJobObject(handle,9,ctypes.byref(limits),ctypes.sizeof(limits)) or not kernel.AssignProcessToJobObject(handle,kernel.GetCurrentProcess()):
        kernel.CloseHandle(handle);raise ValueError('Lens browser ownership is unavailable.')
    def active():
        value=Accounting()
        if not kernel.QueryInformationJobObject(handle,1,ctypes.byref(value),ctypes.sizeof(value),None):raise ClosureUnknown('Lens closure could not be verified.')
        return value.active
    _job=handle;_query=active


def closed():
    if _query is None:return
    deadline=time.monotonic()+5
    while _query()!=1:
        if time.monotonic()>=deadline:raise ClosureUnknown('Lens descendants remain; owner is exiting.')
        time.sleep(.05)


def checked_profile():
    profile=app.DATA/'lens-profile'
    # Check every existing ancestor before mkdir/following any path.
    for path in (profile,app.DATA/'lens-profile.lock',*profile.parents):
        if path.exists() and (path.is_symlink() or bool(getattr(path.lstat(),'st_file_attributes',0)&0x400)):
            raise ValueError('Lens profile cannot use a redirected path.')
    return profile


def acquire():
    global _lease
    own_descendants();closed()
    if _lease is not None:raise ValueError('Lens profile already leased.')
    profile=checked_profile()
    profile.mkdir(parents=True,exist_ok=True)
    handle=(app.DATA/'lens-profile.lock').open('a+b')
    try:
        import msvcrt
        handle.seek(0);handle.write(b'0');handle.flush();handle.seek(0)
        msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
    except BaseException:handle.close();raise
    _lease=handle
    return profile


def release():
    global _lease
    closed()
    if _lease is not None:_lease.close();_lease=None
