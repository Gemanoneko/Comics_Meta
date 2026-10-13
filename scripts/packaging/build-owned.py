"""Held assembly/build supervisor. Invoke only within reviewed outer atomic Job.
The external exact contract and every runtime/native/source byte require review.
"""
import ctypes as C
from ctypes import wintypes as W
import hashlib,json,os,re,sys,time
from pathlib import Path
STARTED=time.monotonic()
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
with HeldPaths() as held:
    contract_path=held.hold(Path(sys.argv[1]))
    raw=contract_path.read_bytes()
    if not re.fullmatch('[a-f0-9]{64}',sys.argv[2]) or digest(raw)!=sys.argv[2]:raise RuntimeError('Pinned contract differs')
    c=json.loads(raw)
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
    stage_identity=inventory(stage)
    staged={'schema':2,'version':c['version'],'profile':c['profile'],'sourceIdentity':c['sourceManifestSha256'],'sourceHead':c['sourceHead'],'runtimeIdentity':c['runtimeManifestSha256'],'engineSources':mapping,**stage_identity}
    staged_path=snapshot/'build/staged-manifest.json'
    with staged_path.open('xb') as output:output.write((json.dumps(staged,sort_keys=True,indent=2)+'\n').encode())
    held.hold(staged_path)
    held.mkdir(snapshot/'dist',True)
    env={'SystemRoot':r'C:\Windows','WINDIR':r'C:\Windows','ComSpec':r'C:\Windows\System32\cmd.exe','PATH':r'C:\Program Files\nodejs;C:\Windows\System32','HOME':str(jobroot),'USERPROFILE':str(jobroot),'LOCALAPPDATA':str(jobroot),'APPDATA':str(jobroot),'TEMP':str(jobroot),'TMP':str(jobroot),'COMICS_META_HELD_BUILD':'1','COMICS_META_BUILD_CONTRACT':str(contract_path),'COMICS_META_BUILD_CONTRACT_SHA256':sys.argv[2],'COMICS_META_STAGED_MANIFEST_SHA256':digest(staged_path.read_bytes())}
    node=held.hold(c['nodeExecutable'])
    if digest(node.read_bytes())!=c['nodeSha256']:raise RuntimeError('Node identity differs')
    result=owned_job(node,[str(snapshot/'scripts/packaging/build-entry.cjs')],snapshot,jobroot/'build-logs',STARTED+540,None,environment_override=env)
    if result['reason']!='completed' or result['root_exit']!=0 or result['active_after']!=0:raise RuntimeError('Build failed or native closure unknown')
    if inventory(stage)!=stage_identity or inventory(runtime)!={'files':runtime_manifest['files'],'directories':runtime_manifest['directories']} or inventory(modules)['files']!=sorted(module_files,key=lambda x:x['path']) or inventory(native_root)!=native_manifest or selected_source_names()!=sorted(x['path'] for x in sourcefiles):raise RuntimeError('Held input path/byte closure changed across build')
    artifacts=inventory(snapshot/'dist')
    receipt={'schema':1,'version':c['version'],'profile':c['profile'],'sourceIdentity':c['sourceManifestSha256'],'sourceHead':c['sourceHead'],'runtimeIdentity':c['runtimeManifestSha256'],'nativeResult':result,'artifacts':artifacts,'state':'build completed; packaged QA/update proof still required'}
    with (jobroot/'build-receipt.json').open('xb') as output:output.write((json.dumps(receipt,sort_keys=True,indent=2)+'\n').encode())
    print(json.dumps({'root_exit':result['root_exit'],'active_after':result['active_after'],'version':c['version'],'artifacts':len(artifacts['files']),'qa':'pending'}))
