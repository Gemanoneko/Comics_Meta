// Data-only rebind to the actual accepted geometry-fix build. Never launches work.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {digest,inventory,verifyInventory,writeJson,requireThat} from './common.mjs';
const scripts=path.dirname(fileURLToPath(import.meta.url)),tool=path.resolve(scripts,'../../..');
const priorRoot=path.join(tool,'scratch/install-update-061-20261110'),base=path.join(priorRoot,'retry07/input');
const root=path.join(priorRoot,'retry08'),input=path.join(root,'input'),build=path.join(tool,'scratch/geometry-fix-061-20261110');
const sourceHead='516c812d90b9482f5cd63003d660f178e0c65444',sourceIdentity='1fcb6ac83fd9218c83387519cfd115c548703bc0c85770b2772031ab7d383a9a';
const baseRaw=fs.readFileSync(base+'/input-manifest.json');
requireThat(process.platform==='win32'&&digest(baseRaw)==='75e740c2eb289363483ff9e3ee718146d488bcc5ff02536e5c643860fb6b1355','Reviewed geometry runtime snapshot changed');
verifyInventory(base,JSON.parse(baseRaw).files,{allowManifest:true});
requireThat(!fs.existsSync(root),'Fresh retry08 required; no automatic duplicate');
const runtime=['common.mjs','guest-entry.mjs','guest-update.mjs','observer.cjs','state-fixture.py','host-session.mjs','host-run.mjs'];
for(const name of runtime)requireThat(digest(fs.readFileSync(path.join(scripts,name)))===digest(fs.readFileSync(path.join(base,name))),'Reviewed runtime semantic drift: '+name);
const sourceRaw=fs.readFileSync(path.join(build,'source-manifest.json'));requireThat(digest(sourceRaw)==='1fcb6ac83fd9218c83387519cfd115c548703bc0c85770b2772031ab7d383a9a'&&JSON.parse(sourceRaw).files.length===378,'Actual source identity/count changed');
const ownedRaw=fs.readFileSync(path.join(build,'build-owned.json'));requireThat(digest(ownedRaw)==='0f50c4a71b1dfc15833fcb9b6a88b2097c6878009ca8b4fad067d0367ff81f88','Actual new build receipt changed');
const owned=JSON.parse(ownedRaw);requireThat(owned.sourceHead===sourceHead&&owned.ok&&owned.code===0&&owned.closed&&!owned.forced&&!owned.timedOut&&owned.outputComplete&&owned.native?.complete&&owned.native.zero,'Actual new build not normally complete');
const dispatcher=path.join(build,'build-owned.mjs');requireThat(digest(fs.readFileSync(dispatcher))==='6d620b5bb0ead4f9cffd6401fc7227311550ff3b5a44a58054c9fd5dfebbe3c2','Reviewed new build dispatcher changed');
const packageFile=path.join(priorRoot,'new-package-516c812.json'),packageRaw=fs.readFileSync(packageFile);requireThat(digest(packageRaw)==='b55d1608a4a9592538a1a3fe285bd63bb34b99a7d12e5b03eae96898b822efc9','Actual new package inventory changed');
const packaged=JSON.parse(packageRaw);requireThat(packaged.sourceHead===sourceHead&&packaged.sourceIdentity===sourceIdentity&&packaged.packageFiles.length===621,'Wrong actual new package identity/count');
const artifactRoot=path.join(build,'candidate/dist'),artifactRecords=JSON.parse(fs.readFileSync(path.join(build,'artifacts.json')));
requireThat(artifactRecords.length===3&&artifactRecords.map(x=>x.name).sort().join('|')===['Comic-Metadata-Setup-0.6.1.exe','Comic-Metadata-Setup-0.6.1.exe.blockmap','latest.yml'].sort().join('|'),'Wrong actual artifact membership');
const artifacts=new Map(artifactRecords.map(item=>{const bytes=fs.readFileSync(path.join(artifactRoot,item.name));requireThat(bytes.length===item.size&&digest(bytes)===item.sha256&&crypto.createHash('sha512').update(bytes).digest('hex')===item.sha512Hex,'Actual new artifact byte drift');return [item.name,{...item,bytes}];}));
const installer=artifacts.get('Comic-Metadata-Setup-0.6.1.exe');requireThat(installer.size===149538531&&installer.sha256==='888fb8c71aab605afb5201b534b37c54510c40f85a2396f0917befbe49a17aca','Wrong accepted new installer');
const sha512=Buffer.from(installer.sha512Hex,'hex').toString('base64'),latest=artifacts.get('latest.yml').bytes.toString('utf8');
const hashes=[...latest.matchAll(/^\s*sha512:\s*(\S+)\s*$/gm)];requireThat(/^version: 0\.6\.1\s*$/m.test(latest)&&hashes.length===2&&hashes.every(match=>match[1]===sha512)&&latest.includes('size: '+installer.size),'Actual new feed identity differs');
const plan=JSON.parse(fs.readFileSync(base+'/plan.json'));
for(const item of Object.values(plan.hostTools))requireThat(digest(fs.readFileSync(item.path))===item.sha256,'Pinned host/Sandbox package drift');
fs.mkdirSync(root);fs.cpSync(base,input,{recursive:true,errorOnExist:true,force:false});
for(const [name,item] of artifacts)fs.writeFileSync(path.join(input,'next',name),item.bytes);
fs.writeFileSync(path.join(input,'accepted-build-source.json'),sourceRaw);fs.writeFileSync(path.join(input,'accepted-build-owned.json'),ownedRaw);
Object.assign(plan,{sourceHead,sourceIdentity,hostRoot:root,inputRoot:input,packageFiles:packaged.packageFiles,
 artifact:{version:'0.6.1',name:installer.name,size:installer.size,sha256:installer.sha256,sha512}});
for(const mode of ['processing','paused']){plan.runs[mode].nonce=crypto.randomBytes(16).toString('hex');fs.mkdirSync(path.join(root,'output-'+mode));}
fs.writeFileSync(path.join(input,'plan.json'),JSON.stringify(plan,null,2)+'\n');
const files=inventory(input).filter(item=>item.path!=='input-manifest.json');fs.writeFileSync(path.join(input,'input-manifest.json'),JSON.stringify({schema:1,files},null,2)+'\n');verifyInventory(input,files,{allowManifest:true});
const manifestSha256=digest(fs.readFileSync(path.join(input,'input-manifest.json')));
writeJson(path.join(root,'rebind-receipt.json'),{schema:1,sourceHead,sourceIdentity,priorRuntimeManifestSha256:digest(baseRaw),manifestSha256,files:files.length,
 runtime:files.filter(item=>runtime.includes(item.path)),artifact:plan.artifact,packageInventory:{path:packageFile,sha256:digest(packageRaw),files:packaged.packageFiles.length},root,input});
console.log(JSON.stringify({root,input,manifestSha256,files:files.length,sourceHead,sourceIdentity,artifact:plan.artifact}));
