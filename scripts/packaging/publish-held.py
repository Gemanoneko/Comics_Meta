"""Promote exact QA-cleared production artifacts; never rebuild or mutate tags."""
import ctypes as C
from ctypes import wintypes as W
import hashlib,json,os,re,sys,time
from pathlib import Path
STARTED=time.monotonic()
if os.name!='nt' or len(sys.argv)!=4 or sys.argv[1] not in ('--check','--publish'):raise RuntimeError('Reviewed Windows promotion receipt required')
k=C.WinDLL('kernel32',use_last_error=True);k.GetCurrentProcess.restype=W.HANDLE;k.IsProcessInJob.argtypes=[W.HANDLE,W.HANDLE,C.POINTER(W.BOOL)]
in_job=W.BOOL()
if not k.IsProcessInJob(k.GetCurrentProcess(),None,C.byref(in_job)) or not in_job.value:raise RuntimeError('Outer atomic release ownership required')
HERE=Path(__file__).absolute().parent
exec(compile((HERE/'held-paths.py').read_bytes(),str(HERE/'held-paths.py'),'exec'),globals())
exec(compile((HERE/'owned-job.py').read_bytes(),str(HERE/'owned-job.py'),'exec'),globals())
REPOSITORY='Gemanoneko/Comics_Meta'
def sha(raw):return hashlib.sha256(raw).hexdigest()
with HeldPaths() as held:
    p=held.hold(Path(sys.argv[2]));raw=p.read_bytes()
    if not re.fullmatch('[a-f0-9]{64}',sys.argv[3]) or sha(raw)!=sys.argv[3]:raise RuntimeError('Promotion receipt identity mismatch')
    c=json.loads(raw)
    if c['schema']!=1 or c['repository']!=REPOSITORY or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+',c['version']):raise RuntimeError('Invalid fixed repository/version receipt')
    version=c['version'];parts=list(map(int,version.split('.')))
    if parts[0]==0 and parts[1]<2:raise RuntimeError('No code-only/old patch release can replace first installer')
    if not re.fullmatch('[a-f0-9]{40}',c['sourceHead']) or not re.fullmatch('[a-f0-9]{64}',c['sourceIdentity']):raise RuntimeError('Missing exact source receipt')
    def read_receipt(item):
        f=held.hold(Path(item['path']));b=f.read_bytes()
        if sha(b)!=item['sha256']:raise RuntimeError('Receipt byte drift')
        return json.loads(b)
    build=read_receipt(c['buildReceipt']);qa=read_receipt(c['qaReceipt'])
    if build['version']!=version or build['sourceIdentity']!=c['sourceIdentity'] or build['sourceHead']!=c['sourceHead'] or build['profile']!='production':raise RuntimeError('Not the exact production build source')
    if build['nativeResult']['root_exit']!=0 or build['nativeResult']['active_after']!=0 or build['nativeResult']['reason']!='completed':raise RuntimeError('Build closure was not proven')
    if qa['schema']!=1 or qa['verdict']!='GO' or qa['version']!=version or qa['sourceIdentity']!=c['sourceIdentity'] or qa['sourceHead']!=c['sourceHead']:raise RuntimeError('QA identity/verdict mismatch')
    required=('packagedInstall','packagedClose','statePreserved','noOwnedEngineBeforeReplacement')
    if not all(qa.get(x) is True for x in required):raise RuntimeError('Required packaged/state/closure QA missing')
    update=qa['updateFlow']
    if update['actualOldToNew'] is not True or update['nextVersion']!=version or update['relaunchVersion']!=version or update['priorVersion']==version:raise RuntimeError('Actual version update/relaunch proof missing')
    for key,verdict in (('qaReport','**Verdict:** GO'),('codeReview','**Verdict:** RELEASE CLEAR')):
        entry=c[key];report=held.hold(entry['path']);raw_report=report.read_bytes()
        if sha(raw_report)!=entry['sha256'] or ('v'+version) not in report.name or verdict not in raw_report.decode('utf-8'):raise RuntimeError('Named exact version review/report missing')
    artifact_root=Path(c['artifactRoot']);held.hold(artifact_root,True)
    installer='Comic-Metadata-Setup-'+version+'.exe'
    names={installer,installer+'.blockmap','latest.yml'}
    if {x['name'] for x in c['artifacts']}!=names or len(c['artifacts'])!=3 or c['artifacts']!=qa['artifacts']:raise RuntimeError('Exact QA artifact list/hash receipt missing')
    artifacts=[]
    buildfiles={x['path']:x['sha256'] for x in build['artifacts']['files']}
    for item in c['artifacts']:
        if item['name'] not in names or '/' in item['name'] or '\\' in item['name']:raise RuntimeError('Unsafe artifact name')
        file=held.hold(artifact_root/item['name']);data=file.read_bytes()
        if len(data)!=item['size'] or sha(data)!=item['sha256'] or hashlib.sha512(data).hexdigest()!=item['sha512Hex'] or buildfiles.get(item['name'])!=sha(data):raise RuntimeError('Artifact version/source/size/hash receipt differs')
        artifacts.append(file)
    latest=(artifact_root/'latest.yml').read_text('utf-8')
    versions=re.findall(r'^version:\s*["\']?([0-9]+\.[0-9]+\.[0-9]+)["\']?\s*$',latest,re.M)
    if versions!=[version] or installer not in latest:raise RuntimeError('Update feed version/artifact mismatch')
    if sys.argv[1]=='--check':
        print(json.dumps({'state':'validated; not published','version':version,'artifacts':3,'rebuild':False}));raise SystemExit(0)
    logroot=Path(c['evidenceRoot'])
    if not logroot.is_absolute() or not logroot.name.startswith('illuminati-cmo-publish-'):raise RuntimeError('Fresh owned publication evidence root required')
    held.mkdir(logroot,True)
    gh=held.hold(c['ghExecutable']);node=held.hold(c['nodeExecutable'])
    if sha(gh.read_bytes())!=c['ghSha256'] or sha(node.read_bytes())!=c['nodeSha256']:raise RuntimeError('CLI runtime identity differs')
    notes=held.hold(c['releaseNotes']['path'])
    if sha(notes.read_bytes())!=c['releaseNotes']['sha256']:raise RuntimeError('Release notes changed')
    env={'SystemRoot':r'C:\Windows','WINDIR':r'C:\Windows','ComSpec':r'C:\Windows\System32\cmd.exe','PATH':str(gh.parent)+r';C:\Windows\System32','HOME':str(logroot),'USERPROFILE':str(logroot),'TEMP':str(logroot),'TMP':str(logroot),'GH_CONFIG_DIR':c['ghConfigDirectory'],'GH_HOST':'github.com','COMICS_META_HELD_PUBLICATION':'1','COMICS_META_GH_EXECUTABLE':str(gh)}
    counter=0
    def command(executable,argv):
        global counter
        counter+=1;result=owned_job(executable,argv,logroot,logroot/('step-'+str(counter)),STARTED+540,None,environment_override=env)
        if result['reason']!='completed' or result['root_exit']!=0 or result['active_after']!=0:raise RuntimeError('Publication command failed; STOP, inspect actual remote state')
        return result
    tag='v'+version
    reference=json.loads(command(gh,['api','repos/'+REPOSITORY+'/git/ref/tags/'+tag])['stdout'])['object']
    if reference['type']=='tag':reference=json.loads(command(gh,['api','repos/'+REPOSITORY+'/git/tags/'+reference['sha']])['stdout'])['object']
    if reference['type']!='commit' or reference['sha']!=c['sourceHead']:raise RuntimeError('Named remote tag does not identify exact tested source')
    command(gh,['release','create',tag,*map(str,artifacts),'--repo',REPOSITORY,'--verify-tag','--title','Comic Metadata '+version,'--notes-file',str(notes)])
    remote=json.loads(command(gh,['api','repos/'+REPOSITORY+'/releases/tags/'+tag])['stdout'])
    remoteassets={a['name']:a for a in remote['assets']}
    if set(remoteassets)!=names or any(remoteassets[x['name']]['size']!=x['size'] or remoteassets[x['name']].get('digest')!='sha256:'+x['sha256'] for x in c['artifacts']):raise RuntimeError('Published asset digest/size differs; STOP before cleanup')
    cleanup=held.hold(HERE.parent/'cleanup-releases.js')
    if sha(cleanup.read_bytes())!=c['cleanupScriptSha256']:raise RuntimeError('Cleanup source identity differs')
    command(node,[str(cleanup),'--apply'])
    print(json.dumps({'published':remote['html_url'],'version':version,'artifacts':3,'rebuild':False,'owned_commands':counter}))
