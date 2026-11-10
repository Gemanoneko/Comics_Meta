// Data-only adaptation of the reviewed 0.6.1 lean build to the unchanged publisher.
// This does not run a build or claim packaged installation/update QA.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {digest,requireThat,member,verifyInventory} from './common.mjs';

const ACCEPTED = Object.freeze({
  version:'0.6.1',sourceHead:'516c812d90b9482f5cd63003d660f178e0c65444',
  sourceIdentity:'1fcb6ac83fd9218c83387519cfd115c548703bc0c85770b2772031ab7d383a9a',
  dispatcher:'6d620b5bb0ead4f9cffd6401fc7227311550ff3b5a44a58054c9fd5dfebbe3c2',
  node:'1c63f1417e2e26d83ca9a9ec1d548524ab1305bc7209d90ebca56257ff0d84ed',
  installer:'888fb8c71aab605afb5201b534b37c54510c40f85a2396f0917befbe49a17aca',
  size:149538531,
});
const samePath=(a,b)=>path.resolve(a).toLowerCase()===path.resolve(b).toLowerCase();
function regular(file) {
  requireThat(typeof file==='string'&&path.isAbsolute(file),'Absolute evidence path required');
  requireThat(fs.lstatSync(file).isFile()&&!fs.lstatSync(file).isSymbolicLink()&&samePath(fs.realpathSync(file),file),'Canonical regular evidence required');
  return fs.readFileSync(file);
}
function pinned(ref) {
  requireThat(ref&&/^[a-f0-9]{64}$/.test(ref.sha256),'Pinned evidence reference required');
  const bytes=regular(ref.path);requireThat(digest(bytes)===ref.sha256,'Evidence byte drift');return bytes;
}

export function strictBuildReceipt({version,sourceHead,sourceIdentity,sourceRoot,sourceManifest,owned,dispatcher,artifactRoot}) {
  requireThat(version===ACCEPTED.version&&sourceHead===ACCEPTED.sourceHead&&sourceIdentity===ACCEPTED.sourceIdentity,'Wrong accepted version/source');
  const sourceRaw=pinned(sourceManifest);
  requireThat(sourceManifest.sha256===sourceIdentity,'Source manifest identity mismatch');
  const manifest=JSON.parse(sourceRaw),files=manifest.files.map(({path,size,sha256})=>({path,size,sha256})).sort((a,b)=>a.path<b.path?-1:a.path>b.path?1:0);
  requireThat(files.length===378,'Accepted source membership mismatch');
  verifyInventory(sourceRoot,files);
  const sourceFiles=new Map(files.map(item=>[item.path,item]));
  const pkg=JSON.parse(regular(member(sourceRoot,'package.json')));
  requireThat(pkg.version===version&&regular(member(sourceRoot,'VERSION')).toString('utf8').trim()===version,'Source version mismatch');
  // The accepted source/config builds the ordinary shipped bytes. QA isolation is
  // an external runtime policy, not an alternate executable/build profile.
  for(const name of ['electron-builder.config.cjs','scripts/build-installer.cjs','scripts/packaging/build-lean.cjs'])requireThat(sourceFiles.has(name),'Production construction input missing');
  requireThat(dispatcher.sha256===ACCEPTED.dispatcher,'Unreviewed build dispatcher');pinned(dispatcher);
  const record=JSON.parse(pinned(owned));
  requireThat(record.sourceHead===sourceHead,'Build source HEAD mismatch');
  requireThat(record.kind==='result'&&record.ok===true&&record.code===0&&record.signal===null&&record.error===null&&
    record.closed===true&&record.forced===false&&record.timedOut===false&&record.overflow===false&&record.truncated===false&&record.outputComplete===true&&
    record.native?.complete===true&&record.native.zero===true&&['active','assigned','listed','unsignaled'].every(key=>record.native[key]===0),
    'Complete successful native Job closure required');
  requireThat(typeof record.out==='string'&&record.err===''&&record.supervisorErr==='','Unexpected build output/error');
  const command=record.command;
  requireThat(command&&Array.isArray(command.args)&&command.args.length===3&&command.args[1]==='--inputs','Unexpected build command');
  requireThat(digest(regular(command.file))===ACCEPTED.node,'Wrong actual build Node');
  const buildRoot=path.dirname(path.dirname(command.args[0]));
  requireThat(samePath(command.args[0],member(buildRoot,'scripts/build-installer.cjs')),'Wrong build producer');
  for(const name of ['electron-builder.config.cjs','scripts/build-installer.cjs','scripts/packaging/build-lean.cjs'])requireThat(digest(regular(member(buildRoot,name)))===sourceFiles.get(name).sha256,'Build construction source drift');
  const successes=[];
  for(const line of record.out.split(/\r?\n/)) {try {const value=JSON.parse(line);if(value.leanBuild)successes.push(value.leanBuild);}catch{}}
  requireThat(successes.length===1,'Exactly one actual lean build result required');
  const lean=successes[0],installer='Comic-Metadata-Setup-'+version+'.exe';
  requireThat(lean.version===version&&lean.bootstrapExecuted===false&&lean.referenceEqual===true&&lean.signCalls===1&&
    lean.size===ACCEPTED.size&&lean.sha256===ACCEPTED.installer&&samePath(lean.installer,member(buildRoot,'dist/'+installer)),
    'Actual production lean build result mismatch');
  requireThat(record.out.includes('BUILD OK '+lean.installer+' '+lean.size+' bytes sha256 '+lean.sha256),'Producer success proof absent');
  const artifacts=[installer,installer+'.blockmap','latest.yml'].map(name=>{
    const bytes=regular(member(artifactRoot,name));
    return {name,size:bytes.length,sha256:digest(bytes),sha512Hex:crypto.createHash('sha512').update(bytes).digest('hex')};
  });
  const main=artifacts[0];requireThat(main.size===lean.size&&main.sha256===lean.sha256,'Artifact differs from actual build');
  const latest=regular(member(artifactRoot,'latest.yml')).toString('utf8');
  const versions=[...latest.matchAll(/^version:\s*["']?([0-9]+\.[0-9]+\.[0-9]+)["']?\s*$/gm)].map(m=>m[1]);
  const hashes=[...latest.matchAll(/^\s*sha512:\s*(\S+)\s*$/gm)].map(m=>m[1]);
  const encoded=Buffer.from(main.sha512Hex,'hex').toString('base64');
  requireThat(versions.length===1&&versions[0]===version&&hashes.length===2&&hashes.every(h=>h===encoded)&&
    latest.includes('url: '+installer)&&latest.includes('path: '+installer)&&latest.includes('size: '+main.size),'Actual update feed mismatch');
  return {artifacts,receipt:{schema:1,version,profile:'production',sourceHead,sourceIdentity,
    nativeResult:{root_exit:record.code,active_after:record.native.active,reason:'completed'},
    nativeResultReceipt:owned,artifacts:{files:artifacts.map(({name,size,sha256})=>({path:name,size,sha256})),directories:[]},
    provenance:{kind:'reviewed-canonical-lean-build translation',sourceManifest,dispatcher,owned,
      productionConfig:sourceFiles.get('electron-builder.config.cjs'),sourceFilesVerified:files.length,
      canonicalNative:record.native,leanBuild:lean},
    state:'build completed; packaged installation/update QA still required'}};
}
