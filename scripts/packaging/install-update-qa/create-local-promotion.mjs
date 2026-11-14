// Promote a real packaged smoke without claiming an installed update occurred.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {digest,requireThat,member,writeJson} from './common.mjs';

function pinned(ref){
  requireThat(ref&&path.isAbsolute(ref.path)&&/^[a-f0-9]{64}$/.test(ref.sha256||''),'Pinned evidence required');
  const st=fs.lstatSync(ref.path);requireThat(st.isFile()&&!st.isSymbolicLink()&&path.resolve(fs.realpathSync(ref.path)).toLowerCase()===path.resolve(ref.path).toLowerCase(),'Canonical evidence file required');
  const raw=fs.readFileSync(ref.path);requireThat(digest(raw)===ref.sha256,'Evidence byte drift');return raw;
}
const json=ref=>JSON.parse(pinned(ref));
function normal(r){return r?.ok===true&&r.code===0&&r.closed===true&&r.forced===false&&r.timedOut===false&&r.outputComplete===true&&r.native?.complete===true&&r.native.zero===true&&['active','assigned','listed','unsignaled'].every(k=>r.native[k]===0);}
function archiveFiles(archive){
  const files=new Map();let cursor=0;
  const str=(buffer)=>buffer.toString('utf8').replace(/\0.*$/s,'');
  while(cursor+512<=archive.length){
    const header=archive.subarray(cursor,cursor+512);if(header.every(byte=>byte===0))break;
    const name=str(header.subarray(0,100)),prefix=str(header.subarray(345,500));
    const full=prefix?prefix+'/'+name:name,type=String.fromCharCode(header[156]||48),size=parseInt(str(header.subarray(124,136)).trim()||'0',8);
    requireThat(Number.isSafeInteger(size)&&size>=0&&cursor+512+size<=archive.length,'Invalid source archive');
    if(type==='0'){requireThat(full&&!files.has(full),'Duplicate archive member');files.set(full,digest(archive.subarray(cursor+512,cursor+512+size)));}
    else requireThat(type==='5'||type==='g','Unsupported archive member');
    cursor+=512+Math.ceil(size/512)*512;
  }
  requireThat(files.size>0,'Empty source archive');return files;
}
export function createLocalPromotion(c){
  requireThat(/^\d+\.\d+\.\d+$/.test(c.version||'')&&/^[a-f0-9]{40}$/.test(c.sourceHead||''),'Exact product identity required');
  const manifest=json(c.sourceManifest),archive=pinned(c.sourceArchive),owned=json(c.buildOwned),smoke=json(c.smokeEvidence),smokeOwner=json(c.smokeOwned),binding=json(c.packageBinding);
  const sourceIdentity=c.sourceManifest.sha256;
  requireThat(manifest.head===c.sourceHead&&manifest.archiveSha===digest(archive)&&owned.sourceHead===c.sourceHead&&owned.archiveSha===manifest.archiveSha,'Source archive/build identity mismatch');
  requireThat(path.isAbsolute(c.repoRoot),'Product repository root required');
  const git=spawnSync('git',['archive','--format=tar',c.sourceHead],{cwd:c.repoRoot,encoding:null,maxBuffer:128*1024*1024,windowsHide:true});
  requireThat(git.status===0&&digest(git.stdout)===manifest.archiveSha,'Source archive does not match product commit');
  requireThat(Array.isArray(manifest.files)&&manifest.files.length>0,'Empty source manifest');
  const archived=archiveFiles(archive),entries=new Map();for(const f of manifest.files){requireThat(!entries.has(f.path)&&/^[a-f0-9]{64}$/.test(f.sha256)&&archived.get(f.path)===f.sha256,'Source archive membership/bytes differ');entries.set(f.path,f.sha256);const actual=fs.readFileSync(member(c.sourceRoot,f.path));requireThat(digest(actual)===f.sha256,'Build source byte drift');}
  requireThat(entries.size===archived.size,'Source archive membership differs');
  const scoped=[];function walk(folder,rel){for(const item of fs.readdirSync(folder,{withFileTypes:true})){const name=rel?rel+'/'+item.name:item.name,full=path.join(folder,item.name);requireThat(!item.isSymbolicLink(),'Linked build input refused');if(item.isDirectory())walk(full,name);else{requireThat(item.isFile(),'Special build input refused');scoped.push(name);}}}
  for(const dir of ['desktop','static','scripts'])walk(path.join(c.sourceRoot,dir),dir);
  for(const item of fs.readdirSync(c.sourceRoot,{withFileTypes:true}))if(item.name.endsWith('.py')){requireThat(item.isFile()&&!item.isSymbolicLink(),'Invalid engine input');scoped.push(item.name);}
  const expected=[...entries.keys()].filter(name=>name.startsWith('desktop/')||name.startsWith('static/')||name.startsWith('scripts/')||(!name.includes('/')&&name.endsWith('.py'))).sort();
  requireThat(JSON.stringify(scoped.sort())===JSON.stringify(expected),'Extra or missing production build input');
  requireThat(JSON.parse(fs.readFileSync(member(c.sourceRoot,'package.json'))).version===c.version&&fs.readFileSync(member(c.sourceRoot,'VERSION'),'utf8').trim()===c.version,'Source version mismatch');
  requireThat(normal(owned)&&owned.kind==='result'&&owned.signal===null&&owned.error===null&&owned.overflow===false&&owned.truncated===false&&owned.supervisorErr===''&&owned.err==='','Owned build closure missing');
  requireThat(owned.command?.args?.length===3&&owned.command.args[1]==='--inputs'&&path.resolve(owned.command.args[0])===path.resolve(c.sourceRoot,'scripts/build-installer.cjs')&&digest(fs.readFileSync(owned.command.file))===c.buildNodeSha256,'Unexpected actual build command');
  const results=[];for(const line of owned.out.split(/\r?\n/)){try{const o=JSON.parse(line);if(o.leanBuild)results.push(o.leanBuild);}catch{}}
  requireThat(results.length===1,'Expected one production build receipt');const build=results[0],installer='Comic-Metadata-Setup-'+c.version+'.exe';
  requireThat(build.version===c.version&&build.bootstrapExecuted===false&&build.referenceEqual===true&&build.signCalls===1&&owned.out.includes('BUILD OK '+build.installer+' '+build.size+' bytes sha256 '+build.sha256),'Production build result missing');
  const artifacts=[installer,installer+'.blockmap','latest.yml'].map(name=>{const data=fs.readFileSync(member(c.artifactRoot,name));return {name,size:data.length,sha256:digest(data),sha512Hex:crypto.createHash('sha512').update(data).digest('hex')};});
  requireThat(path.resolve(build.installer)===path.resolve(c.artifactRoot,installer)&&artifacts[0].size===build.size&&artifacts[0].sha256===build.sha256,'Installer differs from actual build');
  const feed=fs.readFileSync(member(c.artifactRoot,'latest.yml'),'utf8'),encoded=Buffer.from(artifacts[0].sha512Hex,'hex').toString('base64');
  const versions=[...feed.matchAll(/^version:\s*["']?([0-9]+\.[0-9]+\.[0-9]+)["']?\s*$/gm)].map(m=>m[1]);const hashes=[...feed.matchAll(/^\s*sha512:\s*(\S+)\s*$/gm)].map(m=>m[1]);
  requireThat(versions.length===1&&versions[0]===c.version&&hashes.length===2&&hashes.every(h=>h===encoded)&&feed.includes('url: '+installer)&&feed.includes('path: '+installer)&&feed.includes('size: '+build.size),'Update feed mismatch');
  requireThat(normal(smokeOwner)&&smoke.pass===true&&smoke.startup?.packaged===true&&smoke.startup.version===c.version&&smoke.startup.engine?.owned===true&&smoke.startup.engine.httpStatus===200&&smoke.startup.violations?.length===0&&smoke.close?.code===0&&smoke.close.signal===null&&smoke.close.remaining?.length===0&&smoke.quitRequested==='actual tray Quit requested','Packaged smoke/closure missing');
  requireThat(smoke.spec?.sourceHead===c.sourceHead&&smoke.spec.manifest===sourceIdentity&&smoke.spec.installer===artifacts[0].sha256&&smoke.spec.feed===artifacts[2].sha256,'Packaged smoke identity mismatch');
  requireThat(binding.method==='static-installer-extraction'&&binding.closed===true&&binding.installerSha256===artifacts[0].sha256&&binding.exeSha256===smoke.spec.exe&&binding.asarSha256===smoke.spec.asar,'Installer to tested runtime binding missing');
  const extraction=json(binding.owner),archiver=JSON.parse(fs.readFileSync(member(c.sourceRoot,'scripts/packaging/toolchain-lock.json'))).archiverSha256;
  requireThat(normal(extraction.result)&&extraction.toolSha256===archiver&&digest(fs.readFileSync(extraction.command.file))===archiver&&extraction.command.args.includes(build.installer)&&extraction.command.args.includes('ComicMetadata.exe')&&extraction.command.args.includes('resources\\app.asar'),'Owned static extraction proof missing');
  requireThat(smoke.markResources?.matches===8&&smoke.markResources.distinctNormal===4&&smoke.markResources.distinctSmall===4&&['processing','paused','resumed'].every(k=>smoke[k]?.exact===true),'Tray smoke evidence incomplete');
  const asarLog=pinned(c.asarEvidence).toString('utf8');for(const state of ['processing','paused','verification','error'])for(const [field,suffix] of [['normal',''],['small','-16']]){const filename='desktop/assets/tray-'+state+suffix+'.png',sha=entries.get(filename);requireThat(sha&&smoke.trayBytes?.[state]?.[field]===sha&&asarLog.includes(filename+' '+sha),'Packaged tray source mapping mismatch');}
  for(const [ref,verdict] of [[c.qaReport,'**Tray-smoke verdict: GO**'],[c.codeReview,'**Verdict:** RELEASE CLEAR']]){const report=pinned(ref).toString('utf8');requireThat(path.basename(ref.path).includes('v'+c.version)&&report.includes(verdict)&&report.includes(c.sourceHead),'Scoped QA/review source verdict missing');if(ref===c.qaReport)for(const value of [smoke.spec.installer,smoke.spec.exe,smoke.spec.asar,smoke.spec.feed,sourceIdentity,path.basename(c.smokeEvidence.path),path.basename(c.smokeOwned.path)])requireThat(report.includes(value),'Scoped QA attestation does not identify evidence');}
  const out=path.resolve(c.outputRoot);requireThat(path.isAbsolute(c.outputRoot)&&!fs.existsSync(out),'Fresh promotion output required');
  requireThat(path.basename(c.evidenceRoot).startsWith('illuminati-cmo-publish-')&&!fs.existsSync(c.evidenceRoot),'Fresh publication evidence target required');
  for(const [file,hash] of [[c.ghExecutable,c.ghSha256],[c.nodeExecutable,c.nodeSha256],[c.cleanupScript,c.cleanupScriptSha256],[c.releaseNotes.path,c.releaseNotes.sha256]])requireThat(path.isAbsolute(file)&&digest(fs.readFileSync(file))===hash,'Publication dependency drift');
  requireThat(fs.statSync(c.ghConfigDirectory).isDirectory(),'Authenticated gh config missing');
  fs.mkdirSync(out);
  const rawBuild={schema:1,version:c.version,profile:'production',sourceIdentity,sourceHead:c.sourceHead,nativeResult:{root_exit:owned.code,active_after:owned.native.active,reason:'completed'},artifacts:{files:artifacts.map(a=>({path:a.name,size:a.size,sha256:a.sha256}))},provenance:{owned:c.buildOwned,sourceManifest:c.sourceManifest,sourceArchive:c.sourceArchive}};
  const qa={schema:2,profile:'packaged-smoke-manual-update',verdict:'GO',version:c.version,sourceHead:c.sourceHead,sourceIdentity,artifacts,installedUpdate:'deferred-to-user',smokeClosureLink:'independent-qa-report-attestation',provenance:{smokeEvidence:c.smokeEvidence,smokeOwned:c.smokeOwned,packageBinding:c.packageBinding,asarEvidence:c.asarEvidence}};
  const buildPath=path.join(out,'build-receipt.json'),qaPath=path.join(out,'qa-receipt.json');writeJson(buildPath,rawBuild);writeJson(qaPath,qa);
  const promotion={schema:1,repository:'Gemanoneko/Comics_Meta',version:c.version,sourceHead:c.sourceHead,sourceIdentity,buildReceipt:{path:buildPath,sha256:digest(fs.readFileSync(buildPath))},qaReceipt:{path:qaPath,sha256:digest(fs.readFileSync(qaPath))},artifactRoot:c.artifactRoot,artifacts,qaReport:c.qaReport,codeReview:c.codeReview,evidenceRoot:c.evidenceRoot,ghExecutable:c.ghExecutable,ghSha256:c.ghSha256,nodeExecutable:c.nodeExecutable,nodeSha256:c.nodeSha256,ghConfigDirectory:c.ghConfigDirectory,releaseNotes:c.releaseNotes,cleanupScriptSha256:c.cleanupScriptSha256};
  const file=path.join(out,'promotion.json');writeJson(file,promotion);return {path:file,sha256:digest(fs.readFileSync(file)),sourceHead:c.sourceHead,profile:qa.profile,installedUpdate:qa.installedUpdate,artifacts};
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){requireThat(process.argv.length===4&&/^[a-f0-9]{64}$/.test(process.argv[3]),'Exact config and hash required');const raw=fs.readFileSync(process.argv[2]);requireThat(digest(raw)===process.argv[3],'Config byte drift');console.log(JSON.stringify(createLocalPromotion(JSON.parse(raw))));}
