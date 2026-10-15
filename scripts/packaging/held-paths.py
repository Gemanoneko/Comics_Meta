"""Windows pathname chains held against deletion/replacement while consumed.

A guard subprocess that exits before the write is not sufficient. The caller
must keep HeldPaths alive across extraction and all child build processes.
Reparse/type checks apply at acquisition and admission, not to every possible
concurrent same-user metadata mutation. See the committed protection contract.
"""
import ctypes as C
from ctypes import wintypes as W
import os
from pathlib import Path
import uuid

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
        self.directory_keys=set()
        self.compatible=set()
        self.anchors={}
        self.mutable=set()
        self.policies={}
        self.kernel.SetFileInformationByHandle.argtypes=[W.HANDLE,C.c_int,C.c_void_p,W.DWORD]
        self.kernel.SetFileInformationByHandle.restype=W.BOOL
    def hold(self,value,directory=False):
        """Acquire an immutable input component; honor admission on cache hits.

        Internal owned-directory construction uses separate bootstrap/ancestor
        acquisition. Whole-tree admission additionally declares empty members.
        """
        value=Path(value).absolute()
        if not value.is_absolute():raise RuntimeError('Absolute path required')
        for parent in reversed(value.parents):self._open(parent,True,'ancestor')
        self._open(value,directory,'immutable')
        return value
    def _open(self,value,directory,policy='immutable'):
        key=os.path.normcase(str(value))
        if key in self.handles:
            if (key in self.directory_keys)!=directory:raise RuntimeError('Cached path type differs: '+str(value))
            self._validate(value,self.handles[key],directory,self.identities[key])
            if directory and policy=='immutable':
                if any(anchor.parent==value or anchor.parent.is_relative_to(value) for anchor in self.anchor_paths()):
                    raise RuntimeError('Retire owned anchors in entire subtree before immutable admission')
                if self.policies[key]!='immutable-empty':self.policies[key]='immutable';self.mutable.discard(key)
            return
        info=value.lstat()
        if info.st_file_attributes&0x400:raise RuntimeError('Reparse path refused: '+str(value))
        if directory != value.is_dir():raise RuntimeError('Unexpected path type: '+str(value))
        flags=0x00200000|(0x02000000 if directory else 0)
        # A metadata-only/zero-access directory open does not participate in
        # read/write/delete sharing checks. Request read-bearing access on
        # every ancestor as well as the leaf. Start strict; child-compatible
        # sharing is an explicit overlap transition after a direct child hold.
        handle=self.kernel.CreateFileW(str(value),0x80000000,1,None,3,flags,None)
        if handle==C.c_void_p(-1).value:raise OSError(C.get_last_error(),'Hold path '+str(value))
        self.handles[key]=handle
        if directory:self.directory_keys.add(key);self.policies[key]=policy
        self.identities[key]=self._validate(value,handle,directory)
        parent=os.path.normcase(str(value.parent))
        if parent!=key and parent in self.handles:self._children(value.parent,value)

    def _validate(self,value,handle,directory,expected=None):
        key=os.path.normcase(str(value))
        held_info=FileInfo()
        if not self.kernel.GetFileInformationByHandle(handle,C.byref(held_info)):
            raise OSError(C.get_last_error(),'Held attributes')
        if held_info.attributes&0x400 or bool(held_info.attributes&0x10)!=directory:
            raise RuntimeError('Unsafe held path type: '+str(value))
        identity=(held_info.volume,held_info.index_high,held_info.index_low)
        if expected is not None and identity!=expected:raise RuntimeError('Held object changed: '+str(value))
        final=C.create_unicode_buffer(32768)
        count=self.kernel.GetFinalPathNameByHandleW(handle,final,len(final),0)
        if not 0<count<len(final):raise OSError(C.get_last_error(),'Held final path')
        actual=final.value[4:] if final.value.startswith('\\\\?\\') else final.value
        if os.path.normcase(actual.rstrip('\\'))!=key.rstrip('\\'):raise RuntimeError('Held identity differs: '+str(value))
        return identity

    def _children(self,parent,child):
        """Permit child mutations while retaining both directory and direct child.

        The child's hold stays owned until this guard closes. Callers must not
        use a child that their admitted producer is allowed to replace.
        """
        parent,child=Path(parent),Path(child)
        key,childkey=os.path.normcase(str(parent)),os.path.normcase(str(child))
        if child.parent!=parent or childkey not in self.handles or key not in self.directory_keys:
            raise RuntimeError('Held direct child required before directory transition')
        if self.policies[key]=='immutable-empty':raise RuntimeError('Immutable empty input cannot enter child-compatible phase')
        self._validate(child,self.handles[childkey],childkey in self.directory_keys,self.identities[childkey])
        self._validate(parent,self.handles[key],True,self.identities[key])
        if key in self.compatible:return
        new=self.kernel.CreateFileW(str(parent),0x80000000,3,None,3,0x02200000,None)
        if new==C.c_void_p(-1).value:raise OSError(C.get_last_error(),'Child-compatible directory')
        try:
            self._validate(parent,new,True,self.identities[key])
            if not self.kernel.CloseHandle(self.handles[key]):raise OSError(C.get_last_error(),'Retire strict directory hold')
        except BaseException:
            self.kernel.CloseHandle(new);raise
        self.handles[key]=new;self.compatible.add(key)

    def _anchor(self,value):
        """Create only inside a newly owned directory before producer admission."""
        key=os.path.normcase(str(value))
        if key in self.anchors:return
        self._check_mutable(value)
        if self.policies.get(key)!='mutable-bootstrap':raise RuntimeError('Anchor requires newly owned mutable bootstrap')
        anchor=value/('.cmo-owned-anchor-'+uuid.uuid4().hex)
        # CREATE_NEW, read+DELETE, no write/delete sharing. Exact-handle
        # disposition later retires only this authenticated disposable file.
        handle=self.kernel.CreateFileW(str(anchor),0x80010000,1,None,1,0x00200000,None)
        if handle==C.c_void_p(-1).value:raise OSError(C.get_last_error(),'Create owned directory anchor')
        anchor_key=os.path.normcase(str(anchor));self.handles[anchor_key]=handle
        self.identities[anchor_key]=self._validate(anchor,handle,False)
        self.anchors[key]=(anchor,anchor_key)
        self.mutable.add(key)
        self.policies[key]='mutable'
        if set(value.iterdir())!={anchor}:raise RuntimeError('Unexpected member before owned directory admission')
        self._children(value,anchor)

    def retire_anchors(self,value,recursive=True):
        """Anchor-free handoff; real direct children overlap every retirement.

        Fails for an intentionally empty directory. Never filters an anchor
        from an authenticated input or invents content for immutable trees.
        """
        value=Path(value).absolute()
        chosen=[(key,item) for key,item in self.anchors.items() if item[0].parent==value or (recursive and item[0].parent.is_relative_to(value))]
        for key,(anchor,anchor_key) in sorted(chosen,key=lambda item:len(item[1][0].parts),reverse=True):
            parent=anchor.parent
            self._check_mutable(parent)
            real=[p for p in sorted(parent.iterdir()) if p!=anchor]
            if not real:raise RuntimeError('Empty directory needs explicit handoff policy: '+str(parent))
            # Hold every actual child, not an arbitrary unverified name. The
            # caller subsequently compares its complete anchor-free inventory.
            for child in real:self._open(child,child.is_dir(),'ancestor')
            self._children(parent,real[0])
            self._validate(anchor,self.handles[anchor_key],False,self.identities[anchor_key])
            # FILE_DISPOSITION_INFO.DeleteFile is a one-byte BOOLEAN.
            disposition=C.c_ubyte(1)
            if not self.kernel.SetFileInformationByHandle(self.handles[anchor_key],4,C.byref(disposition),C.sizeof(disposition)):
                raise OSError(C.get_last_error(),'Retire exact owned anchor')
            if not self.kernel.CloseHandle(self.handles[anchor_key]):raise OSError(C.get_last_error(),'Close retired anchor')
            del self.handles[anchor_key];del self.identities[anchor_key];del self.anchors[key]
            if anchor.exists():raise RuntimeError('Owned anchor retirement incomplete')

    def anchor_paths(self):
        return {item[0] for item in self.anchors.values()}

    def _check_mutable(self,value):
        # Admission applies to the full lexical subtree, including existing
        # intermediate directories that have never been cached. Canonical
        # acquisition below separately rejects aliases/reparse components.
        for path in (value,*value.parents):
            if self.policies.get(os.path.normcase(str(path)),'').startswith('immutable'):
                raise RuntimeError('Immutable input cannot become an output directory')

    def seal_tree(self,value):
        """Explicit immutable producer-input admission, with no anchor exemption."""
        value=Path(value).absolute()
        if any(p.parent==value or p.parent.is_relative_to(value) for p in self.anchor_paths()):
            raise RuntimeError('Owned anchors remain before immutable admission')
        self.tree(value)
        for key in self.directory_keys:
            path=Path(key)
            if path==value or path.is_relative_to(value):
                if self.policies[key]!='immutable-empty':self.policies[key]='immutable'
                self.mutable.discard(key)
    def mkdir(self,value,exclusive=False):
        value=Path(value).absolute()
        self._check_mutable(value)
        missing=[];current=value
        while not current.exists():
            # lstat sees dangling redirects; those must never count as absent.
            try:current.lstat()
            except FileNotFoundError:pass
            else:raise RuntimeError('Existing non-directory output: '+str(current))
            missing.append(current);current=current.parent
        for parent in reversed(current.parents):self._open(parent,True,'ancestor')
        self._open(current,True,'ancestor')
        if exclusive and not missing:raise RuntimeError('Output already exists: '+str(value))
        for part in reversed(missing):
            part.mkdir(exist_ok=False);self._open(part,True,'mutable-bootstrap');self._anchor(part)
        return value
    def tree(self,value,empty_policy='strict'):
        """Admit exact immutable members; empty dirs stay strict and inventoried."""
        if empty_policy not in ('strict','reject'):raise ValueError('Explicit immutable-empty policy required')
        value=self.hold(value,True)
        for entry in sorted(value.rglob('*')):self.hold(entry,entry.is_dir())
        for key in self.directory_keys:
            path=Path(key)
            if (path==value or path.is_relative_to(value)) and key not in self.compatible:
                if empty_policy=='reject':raise RuntimeError('Empty immutable directory needs explicit policy: '+str(path))
                if next(path.iterdir(),None) is not None:raise RuntimeError('Unheld child appeared during immutable-empty admission')
                # Represent the directory in the exact input inventory; no
                # placeholder, child writes or generic reparse immutability.
                self.policies[key]='immutable-empty';self.mutable.discard(key)
        return value
    def __enter__(self):return self
    def __exit__(self,*unused):
        # Release parents before their direct-child anchors/holds. No parent
        # remains in its compatible phase after its protecting child closes.
        keys=sorted(self.directory_keys,key=lambda key:len(Path(key).parts))
        keys += [key for key in self.handles if key not in self.directory_keys]
        for key in keys:self.kernel.CloseHandle(self.handles[key])
        self.handles.clear()
        self.identities.clear()
        self.directory_keys.clear();self.compatible.clear();self.anchors.clear();self.mutable.clear()
        self.policies.clear()
