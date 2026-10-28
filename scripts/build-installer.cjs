'use strict';
// Lean installer build (Sergei 2026-10-15): `npm run pack` from this checkout.
// 1. Verifies the pinned offline toolchain made by prepare-runtime.mjs
//    (dependencies, Python/7-Zip runtime, Electron/NSIS/rcedit) - no downloads.
// 2. Stages build/staged (runtime + engine sources + licenses) and its manifest.
// 3. Runs the normal electron-builder NSIS build in a child process
//    (scripts/packaging/build-lean.cjs), which never executes the generated
//    NSIS uninstaller stub.
// Success = child exit 0 AND its final `leanBuild` receipt AND the installer
// bytes it names. Output: dist/Comic-Metadata-Setup-<version>.exe.
// Optional: --inputs <dir>  (default build/toolchain)
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const {spawn}=require('node:child_process');
const {need,plain,readInputs,verifyTree}=require('./packaging/toolchain-inputs.cjs');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const root=path.resolve(__dirname,'..');
const args=process.argv.slice(2);
need(args.length===0||(args.length===2&&args[0]==='--inputs'&&args[1]&&!args[1].startsWith('--')),
  'usage: build-installer.cjs [--inputs <prepared-directory>]');
const inputs=plain(path.resolve(args[1]||path.join(root,'build','toolchain')));
const nativeRoot=path.join(inputs,'native'),capsule=path.join(inputs,'capsule');
const dependencies=path.join(inputs,'dependencies','node_modules');

function walk(dir,base=dir,out={files:[],directories:[]}){
  for(const e of fs.readdirSync(dir,{withFileTypes:true})){
    const p=path.join(dir,e.name),rel=path.relative(base,p).split(path.sep).join('/');
    if(e.isSymbolicLink())throw new Error('Reparse entry refused: '+p);
    if(e.isDirectory()){out.directories.push(rel);walk(p,base,out);}
    else if(e.isFile())out.files.push({path:rel,sha256:sha(fs.readFileSync(p))});
    else throw new Error('Nonregular entry refused: '+p);
  }
  return out;
}
const sorted=t=>({directories:[...t.directories].sort(),files:[...t.files].sort((a,b)=>a.path<b.path?-1:a.path>b.path?1:0)});

function stage(version){
  const build=path.join(root,'build'),staged=path.join(build,'staged');
  plain(staged);plain(path.join(build,'staged-manifest.json'));
  if(fs.existsSync(staged))walk(staged);
  fs.rmSync(staged,{recursive:true,force:true});
  fs.rmSync(path.join(build,'staged-manifest.json'),{force:true});
  fs.cpSync(capsule,staged,{recursive:true,errorOnExist:true,force:false});
  const mapping=[];
  const put=(from,packaged)=>{const to=path.join(staged,packaged);fs.mkdirSync(path.dirname(to),{recursive:true});fs.copyFileSync(from,to,fs.constants.COPYFILE_EXCL);return sha(fs.readFileSync(from));};
  const engine=(source,packaged)=>mapping.push({source,packaged,sha256:put(path.join(root,source),packaged)});
  for(const name of fs.readdirSync(root).sort()){
    if(fs.statSync(path.join(root,name)).isFile()&&(name.endsWith('.py')||name==='VERSION'||name==='requirements.txt'))engine(name,'engine/'+name);
  }
  for(const f of sorted(walk(path.join(root,'static'))).files)engine('static/'+f.path,'engine/static/'+f.path);
  engine('desktop/installer_launch.py','engine/installer_launch.py');
  put(path.join(capsule,'runtime','python','LICENSE.txt'),'licenses/Python-LICENSE.txt');
  put(path.join(root,'scripts','packaging','runtime-lock.json'),'licenses/runtime-lock.json');
  const python=sorted(walk(path.join(staged,'runtime','python')));
  const helper=sha(fs.readFileSync(path.join(staged,'engine','installer_launch.py')));
  fs.writeFileSync(path.join(staged,'engine','update-runtime-manifest.json'),
    JSON.stringify({helperSha256:helper,python:{directories:python.directories,files:python.files},schema:1},null,2)+'\n',{flag:'wx'});
  const manifest={schema:2,version,builder:'lean',engineSources:mapping,...sorted(walk(staged))};
  const raw=Buffer.from(JSON.stringify(manifest,null,2)+'\n');
  fs.writeFileSync(path.join(build,'staged-manifest.json'),raw,{flag:'wx'});
  return sha(raw);
}

function main(){
  const version=fs.readFileSync(path.join(root,'VERSION'),'utf8').trim();
  const pkg=JSON.parse(fs.readFileSync(path.join(root,'package.json'),'utf8'));
  if(pkg.version!==version)throw new Error('VERSION '+version+' and package.json '+pkg.version+' differ');
  console.log('Verifying prepared toolchain ...');
  const manifest=readInputs(root,inputs);
  need(process.versions.node===manifest.nodeVersion,'build requires Node '+manifest.nodeVersion);
  const npm=JSON.parse(fs.readFileSync(path.join(path.dirname(process.execPath),'node_modules','npm','package.json')));
  need(npm.version===manifest.npmVersion,'build requires npm '+manifest.npmVersion+' beside Node');
  const modules=path.join(root,'node_modules');
  plain(modules);
  if(!fs.existsSync(modules)){console.log('Copying offline dependencies into node_modules ...');fs.cpSync(dependencies,modules,{recursive:true,errorOnExist:true,force:false});}
  verifyTree(modules,manifest.trees.dependencies);
  console.log('Staging runtime and engine for '+version+' ...');
  const stagedSha=stage(version);
  const build=path.join(root,'build'),tmp=path.join(build,'tmp'),npmDir=path.join(build,'npm');
  plain(tmp);plain(npmDir);plain(path.join(build,'cache'));plain(path.join(root,'dist'));
  if(fs.existsSync(tmp))walk(tmp);
  fs.rmSync(tmp,{recursive:true,force:true});
  for(const d of [tmp,path.join(build,'cache'),npmDir])fs.mkdirSync(d,{recursive:true});
  for(const name of ['user.npmrc','global.npmrc'])fs.writeFileSync(path.join(npmDir,name),'');
  const dist=path.join(root,'dist');
  if(fs.existsSync(dist))for(const name of fs.readdirSync(dist))if(name.endsWith('__uninstaller.exe'))fs.rmSync(path.join(dist,name));
  const env={...process.env,TEMP:tmp,TMP:tmp,ELECTRON_BUILDER_CACHE:path.join(build,'cache'),
    COMICS_META_LEAN_BUILD:'1',COMICS_META_STAGED_MANIFEST_SHA256:stagedSha,COMICS_META_NATIVE_ROOT:nativeRoot,
    NPM_CONFIG_USERCONFIG:path.join(npmDir,'user.npmrc'),NPM_CONFIG_GLOBALCONFIG:path.join(npmDir,'global.npmrc'),
    NPM_CONFIG_CACHE:path.join(npmDir,'cache'),NPM_CONFIG_OFFLINE:'true',NPM_CONFIG_IGNORE_SCRIPTS:'true',
    NPM_CONFIG_AUDIT:'false',NPM_CONFIG_FUND:'false',NPM_CONFIG_UPDATE_NOTIFIER:'false'};
  for(const key of ['GH_TOKEN','GITHUB_TOKEN','CSC_LINK','CSC_KEY_PASSWORD','WIN_CSC_LINK','WIN_CSC_KEY_PASSWORD'])delete env[key];
  console.log('Building '+version+' installer ...');
  const child=spawn(process.execPath,[path.join(__dirname,'packaging','build-lean.cjs')],{cwd:root,env,stdio:['ignore','pipe','inherit'],windowsHide:true});
  let stdout='';
  child.stdout.on('data',chunk=>{stdout+=chunk;process.stdout.write(chunk);});
  child.on('close',code=>{
    // Exit 0 alone is not success (async-exit-hook can mask a failure as 0).
    const last=stdout.trim().split(/\r?\n/).pop()||'';
    let receipt=null;try{receipt=JSON.parse(last).leanBuild||null;}catch{}
    let ok=code===0&&receipt&&receipt.bootstrapExecuted===false&&receipt.version===version;
    if(ok){const bytes=fs.readFileSync(receipt.installer);ok=bytes.length===receipt.size&&sha(bytes)===receipt.sha256;}
    if(!ok){console.error('BUILD FAILED (child exit '+code+(receipt?'':', no success receipt')+')');process.exitCode=1;return;}
    console.log('BUILD OK '+receipt.installer+' '+receipt.size+' bytes sha256 '+receipt.sha256);
  });
}
main();
