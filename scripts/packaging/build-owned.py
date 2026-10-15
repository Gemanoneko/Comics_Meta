"""Held assembly/build supervisor. Invoke only within reviewed outer atomic Job.
The external exact contract and every runtime/native/source byte require review.
"""
import ctypes as C
from ctypes import wintypes as W
import hashlib,json,os,re,secrets,sys,time
from contextlib import ExitStack
from pathlib import Path
STARTED=time.monotonic()
BOOTSTRAP_STARTED=STARTED
if os.name!='nt' or len(sys.argv)!=3:raise RuntimeError('Reviewed Windows contract path and SHA256 required')
k=C.WinDLL('kernel32',use_last_error=True)
k.GetCurrentProcess.restype=W.HANDLE;k.IsProcessInJob.argtypes=[W.HANDLE,W.HANDLE,C.POINTER(W.BOOL)]
in_job=W.BOOL()
if not k.IsProcessInJob(k.GetCurrentProcess(),None,C.byref(in_job)) or not in_job.value:raise RuntimeError('Outer atomic Windows ownership is mandatory')
HERE=Path(__file__).absolute().parent
exec(compile((HERE/'held-paths.py').read_bytes(),str(HERE/'held-paths.py'),'exec'),globals())
# This audited module provides nested atomic assignment, bounded streams and closure.
exec(compile((HERE/'owned-job.py').read_bytes(),str(HERE/'owned-job.py'),'exec'),globals())
def digest(raw):return hashlib.sha256(raw).hexdigest()
def safe_rel(value):
    if not isinstance(value,str) or not value or any(p in ('','..','.') for p in value.split('/')) or '\\' in value or ':' in value:raise RuntimeError('Unsafe contract member')
    return value
def inventory(root):
    files=[];dirs=[]
    for current,names,leaves in os.walk(root,followlinks=False):
        for name in names:
            p=Path(current)/name
            if p.lstat().st_file_attributes&0x400 or not p.is_dir():raise RuntimeError('Reparse/non-directory tree member')
            dirs.append(p.relative_to(root).as_posix())
        for name in leaves:
            p=Path(current)/name
            if p.lstat().st_file_attributes&0x400 or not p.is_file():raise RuntimeError('Reparse/nonregular tree member')
            files.append({'path':p.relative_to(root).as_posix(),'sha256':digest(p.read_bytes())})
    return {'files':sorted(files,key=lambda x:x['path']),'directories':sorted(dirs)}
with HeldPaths() as held, ExitStack() as lifetime:
    contract_path=held.hold(Path(sys.argv[1]))
    raw=contract_path.read_bytes()
    if not re.fullmatch('[a-f0-9]{64}',sys.argv[2]) or digest(raw)!=sys.argv[2]:raise RuntimeError('Pinned contract differs')
    c=json.loads(raw)
    entry_started=STARTED
    original=c.get('originalStartedMonotonic')
    if type(original) not in (int,float) or not 0<original<=entry_started or time.monotonic()>=original+530:
        raise RuntimeError('Original startup-inclusive build clock required')
    STARTED=original
    if type(c.get('originalDeadlineUnixMs')) is not int or time.time()*1000>=c['originalDeadlineUnixMs']:
        raise RuntimeError('Original build wall deadline missing or expired')
    # Retain the actual reporting parent; outer reviewed guardian owns this entire
    # process tree and its foreground lifetime. A PID is never reopened later.
    parent_handle=api('OpenProcess',HANDLE,W.DWORD,W.BOOL,W.DWORD)(0x00101000,False,os.getppid())
    require(parent_handle,'Retain exact build reporting parent')
    lifetime.callback(close,parent_handle)
    get_times=api('GetProcessTimes',W.BOOL,HANDLE,*([C.POINTER(W.FILETIME)]*4))
    def created(handle):
        stamps=[W.FILETIME() for _ in range(4)]
        require(get_times(handle,*[C.byref(x) for x in stamps]),'Build parent creation identity')
        return (stamps[0].dwHighDateTime<<32)|stamps[0].dwLowDateTime
    current=api('GetCurrentProcess',HANDLE)()
    if created(parent_handle)>created(current):raise RuntimeError('Build parent identity reused')
    def owner_lease():return wait_process(parent_handle,0)==258
    if not owner_lease():raise RuntimeError('Original build owner closed')

    if c['schema']!=1 or c['profile'] not in ('qa','production') or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+',c['version']):raise RuntimeError('Unsupported contract')
    jobroot=Path(c['jobRoot'])
    if not jobroot.is_absolute() or not jobroot.name.startswith('illuminati-cmo-build-'):raise RuntimeError('Owned build root required')
    source=Path(c['sourceRoot'])
    if source.name=='Comics Meta Organizer':raise RuntimeError('Live source checkout is excluded')
    def manifest(filename,expected):
        p=held.hold(filename);b=p.read_bytes()
        if digest(b)!=expected:raise RuntimeError('Input manifest drift')
        return json.loads(b)
    source_manifest=manifest(c['sourceManifest'],c['sourceManifestSha256'])
    sourcefiles=source_manifest['files']
    if source_manifest['sourceHead']!=c['sourceHead'] or not re.fullmatch('[a-f0-9]{40}',c['sourceHead']):raise RuntimeError('Exact source HEAD receipt missing')
    allowed={'VERSION','requirements.txt','package.json','package-lock.json','electron-builder.config.cjs'}
    def selected_source_names():
        names=[p.name for p in source.iterdir() if p.is_file() and (p.suffix=='.py' or p.name in allowed)]
        for folder in ('desktop','static','scripts'):
            for p in (source/folder).rglob('*'):
                if p.is_file():names.append(p.relative_to(source).as_posix())
        return sorted(names)
    if selected_source_names()!=sorted(x['path'] for x in sourcefiles):raise RuntimeError('Build source filename-set differs')
    for item in sourcefiles:
        p=held.hold(source/safe_rel(item['path']))
        if digest(p.read_bytes())!=item['sha256']:raise RuntimeError('Build source byte drift')
    required={'comic_recovery.py','desktop/installer_launch.py','scripts/build-installer.cjs','desktop/assets/icon.ico'}
    if not required.issubset({x['path'] for x in sourcefiles}):raise RuntimeError('Required packaged recovery/launcher/icon source missing')
    if (source/'VERSION').read_text().strip()!=c['version'] or json.loads((source/'package.json').read_bytes())['version']!=c['version']:raise RuntimeError('Version differs')
    runtime=Path(c['runtimeRoot']);runtime_manifest=manifest(c['runtimeManifest'],c['runtimeManifestSha256'])
    if inventory(runtime)!={'files':runtime_manifest['files'],'directories':runtime_manifest['directories']}:raise RuntimeError('Authenticated runtime path/bytes differ')
    held.tree(runtime)
    if inventory(runtime)!={'files':runtime_manifest['files'],'directories':runtime_manifest['directories']}:raise RuntimeError('Runtime differs after holds')
    modules=Path(c['dependenciesRoot']);module_files=manifest(c['dependencyManifest'],c['dependencyManifestSha256'])
    if inventory(modules)['files']!=sorted(module_files,key=lambda x:x['path']):raise RuntimeError('Dependencies complete path/byte closure differs')
    held.tree(modules)
    if inventory(modules)['files']!=sorted(module_files,key=lambda x:x['path']):raise RuntimeError('Dependencies differ after holds')
    native_root=Path(c['nativeRoot']);native_manifest=manifest(c['nativeManifest'],c['nativeManifestSha256'])
    if inventory(native_root)!=native_manifest:raise RuntimeError('Offline native tool closure differs')
    held.tree(native_root)
    if inventory(native_root)!=native_manifest:raise RuntimeError('Native tools differ after holds')
    for key in ('electronDist','nsisRoot','nsisPlugins','rcedit'):
        p=Path(c[key])
        if not p.is_relative_to(native_root):raise RuntimeError('Native path outside held closure')
    for p in (Path(c['electronDist'])/'electron.exe',Path(c['nsisRoot'])/'Bin/makensis.exe',Path(c['rcedit'])/'rcedit-x64.exe'):
        if not p.is_file():raise RuntimeError('Required offline native executable absent')
    held.mkdir(jobroot,True)
    snapshot=held.mkdir(jobroot/'source',True)
    if Path(c['snapshotRoot'])!=snapshot or Path(c['builderCache'])!=jobroot/'builder-cache':raise RuntimeError('Snapshot/cache contract mismatch')
    held.mkdir(c['builderCache'],True)
    def copy_file(src,dest):
        held.hold(src);held.mkdir(dest.parent)
        with dest.open('xb') as output:output.write(src.read_bytes())
        held.hold(dest)
    for item in sourcefiles:copy_file(source/item['path'],snapshot/item['path'])
    for item in module_files:copy_file(modules/item['path'],snapshot/'node_modules'/item['path'])
    stage=held.mkdir(snapshot/'build/staged',True)
    for item in runtime_manifest['files']:copy_file(runtime/item['path'],stage/item['path'])
    engine=held.mkdir(stage/'engine',True);mapping=[]
    for item in sourcefiles:
        name=item['path']
        if ('/' not in name and (name.endswith('.py') or name in ('VERSION','requirements.txt'))) or name.startswith('static/'):
            target='engine/'+name
        elif name=='desktop/installer_launch.py':target='engine/installer_launch.py'
        else:continue
        copy_file(source/name,stage/target);mapping.append({'source':name,'packaged':target,'sha256':item['sha256']})
    licenses=held.mkdir(stage/'licenses',True)
    copy_file(runtime/'runtime/python/LICENSE.txt',licenses/'Python-LICENSE.txt')
    copy_file(source/'scripts/packaging/runtime-lock.json',licenses/'runtime-lock.json')
    # No temporary output anchor may become authenticated runtime content.
    # Overlap real-child holds before retiring each owned anchor; an empty
    # stage directory fails explicitly instead of being filtered from inventory.
    held.retire_anchors(stage)
    python_prefix='runtime/python/'
    python_identity=inventory(stage/'runtime/python')
    authenticated_python={'files':sorted([{'path':item['path'][len(python_prefix):],'sha256':item['sha256']} for item in runtime_manifest['files'] if item['path'].startswith(python_prefix)],key=lambda x:x['path']),'directories':sorted([name[len(python_prefix):] for name in runtime_manifest['directories'] if name.startswith(python_prefix)])}
    if python_identity!=authenticated_python:raise RuntimeError('Packaged Python closure differs from authenticated runtime')
    update_runtime={'schema':1,'python':python_identity,'helperSha256':digest((engine/'installer_launch.py').read_bytes())}
    update_runtime_path=engine/'update-runtime-manifest.json'
    with update_runtime_path.open('xb') as output:output.write((json.dumps(update_runtime,sort_keys=True,indent=2)+'\n').encode())
    held.hold(update_runtime_path)
    stage_identity=inventory(stage)
    staged={'schema':2,'version':c['version'],'profile':c['profile'],'sourceIdentity':c['sourceManifestSha256'],'sourceHead':c['sourceHead'],'runtimeIdentity':c['runtimeManifestSha256'],'engineSources':mapping,**stage_identity}
    staged_path=snapshot/'build/staged-manifest.json'
    with staged_path.open('xb') as output:output.write((json.dumps(staged,sort_keys=True,indent=2)+'\n').encode())
    held.hold(staged_path)
    held.mkdir(snapshot/'dist',True)
    # Source/dependency clones are immutable producer inputs. Dist alone stays
    # mutable/anchored until the producer closes; build/stage is already sealed.
    for directory in sorted(snapshot.iterdir()):
        if directory.is_dir() and directory.name not in ('build','dist'):
            held.retire_anchors(directory)
    held.retire_anchors(snapshot/'build')
    held.retire_anchors(snapshot,recursive=False)
    held.seal_tree(stage)
    for directory in sorted(snapshot.iterdir()):
        if directory.is_dir() and directory.name not in ('build','dist'):
            held.seal_tree(directory)
    def cloned_inputs():
        value=inventory(snapshot)
        def selected(name):return name.split('/')[0] not in ('build','dist')
        return {'files':[item for item in value['files'] if selected(item['path'])],'directories':[name for name in value['directories'] if selected(name)]}
    clone_identity=cloned_inputs()
    env={'SystemRoot':r'C:\Windows','WINDIR':r'C:\Windows','ComSpec':r'C:\Windows\System32\cmd.exe','PATH':r'C:\Program Files\nodejs;C:\Windows\System32','HOME':str(jobroot),'USERPROFILE':str(jobroot),'LOCALAPPDATA':str(jobroot),'APPDATA':str(jobroot),'TEMP':str(jobroot),'TMP':str(jobroot),'COMICS_META_HELD_BUILD':'1','COMICS_META_BUILD_CONTRACT':str(contract_path),'COMICS_META_BUILD_CONTRACT_SHA256':sys.argv[2],'COMICS_META_STAGED_MANIFEST_SHA256':digest(staged_path.read_bytes())}
    node=held.hold(c['nodeExecutable'])
    if digest(node.read_bytes())!=c['nodeSha256']:raise RuntimeError('Node identity differs')
    # The broker services finite owned-file requests from the existing lease
    # callback. It creates no service, listener, thread or extra native process.
    lease_path=snapshot/'scripts/packaging/nsis-safe/lease-rpc.py'
    lease_raw=lease_path.read_bytes()
    expected_lease=next(item['sha256'] for item in sourcefiles if item['path']=='scripts/packaging/nsis-safe/lease-rpc.py')
    if digest(lease_raw)!=expected_lease:raise RuntimeError('Held NSIS broker source differs')
    broker_scope={'__name__':'held_nsis_io_broker','__file__':str(lease_path)}
    exec(compile(lease_raw,str(lease_path),'exec'),broker_scope)
    def open_rpc_leaf(lib,filename,sharing=1):
        value=Path(filename).absolute()
        handle=create_file(str(value),0x80000000,sharing,None,3,0x00200000,None)
        if handle==INVALID:raise OSError(C.get_last_error(),'Acquire exact NSIS RPC leaf')
        try:
            held._validate(value,handle,False)
            return handle
        except BaseException:
            close(handle);raise
    nonce=secrets.token_hex(32)
    installer=snapshot/'dist'/('Comic-Metadata-Setup-'+c['version']+'.exe')
    template=snapshot/'node_modules/app-builder-lib/templates/nsis/installer.nsi'
    template_sha=next(item['sha256'] for item in module_files if item['path']=='app-builder-lib/templates/nsis/installer.nsi')
    broker_config={'schema':1,'jobRoot':str(jobroot),'rpcRoot':str(jobroot/('nsis-io-rpc-'+nonce[:12])),
        'outDir':str(snapshot/'dist'),'installer':str(installer),'uninstaller':str(installer.parent/(installer.name[:-3]+'__uninstaller.exe')),
        'template':str(template),'templateSha256':template_sha,'nonce':nonce,
        'deadlineUnixMs':c['originalDeadlineUnixMs'],'allowSignerReplacement':False}
    broker=broker_scope['NativeIoLease'](dict(globals()),{'opened':open_rpc_leaf},held,lifetime,broker_config,STARTED,STARTED+530,owner_lease)
    env['COMICS_META_NSIS_IO_CONFIG']=broker.config_receipt['path']
    env['COMICS_META_NSIS_IO_CONFIG_SHA256']=broker.config_receipt['sha256']
    retained_build_logs=[]
    def retain_build_logs(files):
        for filename,identity,expected_hash in files:
            handle=open_rpc_leaf(dict(globals()),filename,sharing=3)
            lifetime.callback(close,handle)
            if handle_identity(handle)!=tuple(identity):raise RuntimeError('Build logger handoff identity changed')
            retained_build_logs.append((filename,tuple(identity),expected_hash))
    result=owned_job(node,[str(snapshot/'scripts/packaging/build-entry.cjs')],snapshot,jobroot/'build-logs',STARTED+530,broker.service,environment_override=env,retain_outputs=retain_build_logs)
    for filename,identity,expected_hash in retained_build_logs:
        handle=open_rpc_leaf(dict(globals()),filename)
        lifetime.callback(close,handle)
        if handle_identity(handle)!=identity or digest(handle_read(handle,16*1024**2))!=expected_hash:
            raise RuntimeError('Completed build logger strong bytes changed')

    broker_inventory=broker.finalize_after_closure(result)
    broker_receipt=broker.receipt(require_complete=True)

    if result['reason']!='completed' or result['root_exit']!=0 or result['active_after']!=0:raise RuntimeError('Build failed or native closure unknown')
    held.retire_anchors(snapshot/'dist')
    if inventory(stage)!=stage_identity or inventory(runtime)!={'files':runtime_manifest['files'],'directories':runtime_manifest['directories']} or inventory(modules)['files']!=sorted(module_files,key=lambda x:x['path']) or inventory(native_root)!=native_manifest or selected_source_names()!=sorted(x['path'] for x in sourcefiles):raise RuntimeError('Held input path/byte closure changed across build')
    if cloned_inputs()!=clone_identity:raise RuntimeError('Cloned desktop/scripts/dependencies input path/type/bytes changed')
    for item in sourcefiles:
        if digest((source/item['path']).read_bytes())!=item['sha256']:raise RuntimeError('Original source bytes changed across build')
    artifacts=inventory(snapshot/'dist')
    receipt={'schema':1,'version':c['version'],'profile':c['profile'],'sourceIdentity':c['sourceManifestSha256'],'sourceHead':c['sourceHead'],'runtimeIdentity':c['runtimeManifestSha256'],'nativeResult':result,'nsisIo':broker_receipt,'nsisIoInventory':broker_inventory,'artifacts':artifacts,'state':'build completed; packaged QA/update proof still required'}
    with (jobroot/'build-receipt.json').open('xb') as output:output.write((json.dumps(receipt,sort_keys=True,indent=2)+'\n').encode())
    print(json.dumps({'root_exit':result['root_exit'],'active_after':result['active_after'],'version':c['version'],'artifacts':len(artifacts['files']),'qa':'pending'}))
