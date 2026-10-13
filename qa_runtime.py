"""Private installed QA network/process exclusions; production is unaffected."""
import hashlib
import json
import os
from pathlib import Path
import sys


def install():
    if os.environ.get('COMICS_META_QA')!='1':return
    root=Path(os.environ.get('COMICS_META_QA_ROOT',''))
    policy_path=Path(os.environ.get('COMICS_META_QA_POLICY',''))
    expected=os.environ.get('COMICS_META_QA_POLICY_SHA256','')
    if not root.is_absolute() or not root.name.startswith('illuminati-cmo-qa-') or not policy_path.is_absolute() or not policy_path.is_relative_to(root):raise RuntimeError('Private QA policy unavailable')
    for value in [policy_path,*policy_path.parents]:
        if value.is_symlink() or (value.exists() and getattr(value.lstat(),'st_file_attributes',0)&0x400):raise RuntimeError('Private QA policy path unavailable')
    raw=policy_path.read_bytes()
    if len(raw)>32768 or len(expected)!=64 or hashlib.sha256(raw).hexdigest()!=expected:raise RuntimeError('Private QA policy identity differs')
    policy=json.loads(raw)
    port=policy['enginePort']
    if policy.get('root')!=str(root) or port in (8765,11434) or not isinstance(port,int):raise RuntimeError('Private QA engine scope differs')
    if Path(os.environ.get('COMICS_META_STATE_ROOT','')).resolve()!= (root/'state').resolve():raise RuntimeError('Private QA state scope differs')
    allowed_python=os.path.normcase(os.path.abspath(sys.executable))
    sevenzip=os.environ.get('COMICS_META_7ZIP')
    allowed_native=os.path.normcase(os.path.abspath(sevenzip)) if sevenzip else None
    def audit(event,args):
        if event=='socket.connect':
            address=args[1]
            if not isinstance(address,tuple) or len(address)<2 or address[0] not in ('127.0.0.1','localhost','::1') or address[1]!=port:raise PermissionError('Private QA external connection refused')
        elif event=='socket.getaddrinfo':
            if args[0] not in ('127.0.0.1','localhost','::1',None):raise PermissionError('Private QA external lookup refused')
        elif event=='socket.bind':
            address=args[1]
            if not isinstance(address,tuple) or address[0] not in ('127.0.0.1','localhost','::1') or address[1]!=port:raise PermissionError('Private QA socket binding refused')
        elif event=='subprocess.Popen':
            executable=os.path.normcase(os.path.abspath(str(args[0])))
            if executable not in (allowed_python,allowed_native):raise PermissionError('Private QA native child refused')
            child_env=args[3]
            if child_env is not None and any(child_env.get(key)!=os.environ.get(key) for key in ('COMICS_META_QA','COMICS_META_QA_ROOT','COMICS_META_QA_POLICY','COMICS_META_QA_POLICY_SHA256','COMICS_META_STATE_ROOT')):raise PermissionError('Private QA child exclusions missing')
        elif event in ('os.system','os.exec','os.posix_spawn'):raise PermissionError('Private QA alternate process launch refused')
    sys.addaudithook(audit)
