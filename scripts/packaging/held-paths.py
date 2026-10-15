"""Windows packaging paths held against deletion/redirection until work completes.

A guard subprocess that exits before the write is not sufficient. The caller
must keep HeldPaths alive across extraction and all child build processes.
"""
import ctypes as C
from ctypes import wintypes as W
import os
from pathlib import Path

class FileInfo(C.Structure):
    _fields_=[('attributes',W.DWORD),('created',W.FILETIME),('accessed',W.FILETIME),
        ('written',W.FILETIME),('volume',W.DWORD),('size_high',W.DWORD),
        ('size_low',W.DWORD),('links',W.DWORD),('index_high',W.DWORD),('index_low',W.DWORD)]

class HeldPaths:
    def __init__(self):
        if os.name != 'nt': raise RuntimeError('Native Windows held-path guard required')
        self.kernel=C.WinDLL('kernel32',use_last_error=True)
        self.kernel.CreateFileW.restype=W.HANDLE
        self.kernel.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,C.c_void_p,W.DWORD,W.DWORD,W.HANDLE]
        self.kernel.CloseHandle.argtypes=[W.HANDLE]
        self.kernel.GetFinalPathNameByHandleW.argtypes=[W.HANDLE,W.LPWSTR,W.DWORD,W.DWORD]
        self.kernel.GetFinalPathNameByHandleW.restype=W.DWORD
        self.kernel.GetFileInformationByHandle.argtypes=[W.HANDLE,C.POINTER(FileInfo)]
        self.kernel.GetFileInformationByHandle.restype=W.BOOL
        self.handles={}
        self.identities={}
    def hold(self,value,directory=False):
        value=Path(value).absolute()
        if not value.is_absolute():raise RuntimeError('Absolute path required')
        for parent in reversed(value.parents):self._open(parent,True)
        self._open(value,directory)
        return value
    def _open(self,value,directory):
        key=os.path.normcase(str(value))
        if key in self.handles:return
        info=value.lstat()
        if info.st_file_attributes&0x400:raise RuntimeError('Reparse path refused: '+str(value))
        if directory != value.is_dir():raise RuntimeError('Unexpected path type: '+str(value))
        flags=0x00200000|(0x02000000 if directory else 0)
        # A metadata-only/zero-access directory open does not participate in
        # read/write/delete sharing checks. Request read-bearing access on
        # every ancestor as well as the leaf, and never share write or delete.
        handle=self.kernel.CreateFileW(str(value),0x80000000,1,None,3,flags,None)
        if handle==C.c_void_p(-1).value:raise OSError(C.get_last_error(),'Hold path '+str(value))
        self.handles[key]=handle
        held_info=FileInfo()
        if not self.kernel.GetFileInformationByHandle(handle,C.byref(held_info)):
            raise OSError(C.get_last_error(),'Held attributes')
        if held_info.attributes&0x400 or bool(held_info.attributes&0x10)!=directory:
            raise RuntimeError('Unsafe held path type: '+str(value))
        self.identities[key]=(held_info.volume,held_info.index_high,held_info.index_low)
        final=C.create_unicode_buffer(32768)
        count=self.kernel.GetFinalPathNameByHandleW(handle,final,len(final),0)
        if not 0<count<len(final):raise OSError(C.get_last_error(),'Held final path')
        actual=final.value[4:] if final.value.startswith('\\\\?\\') else final.value
        if os.path.normcase(actual.rstrip('\\'))!=key.rstrip('\\'):raise RuntimeError('Held identity differs: '+str(value))
    def mkdir(self,value,exclusive=False):
        value=Path(value).absolute()
        missing=[];current=value
        while not current.exists():
            # lstat sees dangling redirects; those must never count as absent.
            try:current.lstat()
            except FileNotFoundError:pass
            else:raise RuntimeError('Existing non-directory output: '+str(current))
            missing.append(current);current=current.parent
        self.hold(current,True)
        if exclusive and not missing:raise RuntimeError('Output already exists: '+str(value))
        for part in reversed(missing):
            part.mkdir(exist_ok=False);self.hold(part,True)
        return value
    def tree(self,value):
        value=self.hold(value,True)
        for entry in sorted(value.rglob('*')):self.hold(entry,entry.is_dir())
        return value
    def __enter__(self):return self
    def __exit__(self,*unused):
        for handle in reversed(list(self.handles.values())):self.kernel.CloseHandle(handle)
        self.handles.clear()
        self.identities.clear()
