'use strict';
// Lean installer build child (Sergei 2026-10-15). Run only by scripts/build-installer.cjs.
// Normal electron-builder NSIS build with the offline native tools. The generated
// NSIS BUILD_UNINSTALLER stub is NEVER executed: the pinned safe route
// (nsis-safe/install-nsis-route.cjs + safe-entry.cjs) replaces upstream's
// "run the stub" step with the pure-JS decoder, cross-checked byte-for-byte
// against upstream's pure UninstallerReader. The I/O adapter here is plain fs.
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const crypto=require('node:crypto');
const {retainFailureExit}=require('./failure-exit.cjs');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const need=(value,message)=>{if(!value)throw new Error('Lean build: '+message);};

function leanIo({installer,uninstaller,outDir,template,reader,work}){
  const leaf=p=>{const bytes=fs.readFileSync(p);return {path:p,size:bytes.length,sha256:sha(bytes),identity:sha(bytes)};};
  let signCalls=0;
  return {
    async assertOwnedPaths(v){
      need(v.installerPath===installer&&v.uninstallerPath===uninstaller&&v.outDir===outDir&&v.templatePath===template,
        'unexpected NSIS role paths '+JSON.stringify(v));
      return {verified:true};
    },
    async readTemplateHeld(p,maximum){
      need(p===template,'template role');const bytes=fs.readFileSync(p);need(bytes.length<=maximum,'template bound');
      return {bytes,identity:sha(bytes)};
    },
    async readCompiledHeld(p,maximum){
      need(p===installer,'compiled stub role');const bytes=fs.readFileSync(p);need(bytes.length<=maximum,'compiled stub bound');
      return {bytes,identity:sha(bytes)};
    },
    async referenceDecode(p,decoded){
      need(p===installer&&Buffer.isBuffer(decoded),'reference input');
      const out=path.join(work,'upstream-reference-uninstaller.bin');
      fs.rmSync(out,{force:true});
      await reader.exec(p,out); // upstream pure JS reader; reads bytes, never executes
      const ref=fs.readFileSync(out);fs.rmSync(out,{force:true});
      return {equal:ref.equals(decoded),reference:{size:ref.length,sha256:sha(ref)}};
    },
    async writeExclusiveAndSeal(p,bytes){
      need(p===uninstaller,'uninstaller role');fs.writeFileSync(p,bytes,{flag:'wx'});return leaf(p);
    },
    async signAndSeal(p,sign){
      need(p===uninstaller&&++signCalls===1,'one uninstaller sign call');await sign();return leaf(p);
    },
    async beforeFinalCompiler(){return {};},
    async afterFinalCompilerAndRelease(){return {};},
    receipt(){return {signCalls};}
  };
}

// electron-builder 26 runs `npm prefix/list` on Windows through
// `powershell.exe -EncodedCommand`; this machine's AV blocks that. Decode the
// exact upstream wrapper and run the same npm query via node + npm-cli.js.
function routeNpm(root){
  const cp=require('node:child_process');
  const cli=path.join(path.dirname(process.execPath),'node_modules','npm','bin','npm-cli.js');
  need(fs.existsSync(cli),'npm-cli.js next to node');
  const collector=require(path.join(root,'node_modules','app-builder-lib','out','node-module-collector','nodeModulesCollector.js'));
  const original=cp.spawn,calls=[];
  cp.spawn=function(command,args,options){
    if(typeof command!=='string'||!/^powershell(\.exe)?$/i.test(path.basename(command)))return original.apply(this,arguments);
    need(Array.isArray(args)&&args.length===4&&args[2]==='-EncodedCommand','only the collector PowerShell wrapper');
    const script=Buffer.from(args[3],'base64').toString('utf16le');
    const m=/; & ('(?:[^']|'')*'(?: '(?:[^']|'')*')*); exit \$LASTEXITCODE$/.exec(script);
    need(m,'recognised collector command');
    const tokens=[...m[1].matchAll(/'((?:[^']|'')*)'/g)].map(x=>x[1].replace(/''/g,"'"));
    const [npm,...npmArgs]=tokens;
    need(/^npm(\.cmd)?$/i.test(path.basename(npm||'')),'collector runs npm only, got '+npm);
    need(JSON.stringify(collector.buildPowerShellEncodedArgs(npm,npmArgs))===JSON.stringify(args),'exact upstream encoding');
    calls.push(npmArgs);
    return original.call(cp,process.execPath,[cli,...npmArgs],{...options,shell:false,windowsHide:true});
  };
  return {calls,restore(){cp.spawn=original;}};
}

async function main(){
  need(process.platform==='win32'&&process.arch==='x64'&&process.env.COMICS_META_LEAN_BUILD==='1','run through scripts/build-installer.cjs');
  const root=path.resolve(__dirname,'../..');
  need(path.resolve(process.cwd())===root,'cwd is the checkout root');
  const pkg=JSON.parse(fs.readFileSync(path.join(root,'package.json'),'utf8'));
  const version=fs.readFileSync(path.join(root,'VERSION'),'utf8').trim();
  need(pkg.version===version,'VERSION and package.json agree');
  const nativeRoot=process.env.COMICS_META_NATIVE_ROOT;
  need(nativeRoot&&path.isAbsolute(nativeRoot),'native tool root');
  const nsisRoot=path.join(nativeRoot,'nsis'),nsisPlugins=path.join(nativeRoot,'nsis-resources');
  const electronDist=path.join(nativeRoot,'electron'),rcedit=path.join(nativeRoot,'winCodeSign');
  const sevenZip=path.join(root,'node_modules','7zip-bin','win','x64','7za.exe');
  for(const p of [path.join(electronDist,'electron.exe'),path.join(nsisRoot,'Bin','makensis.exe'),path.join(rcedit,'rcedit-x64.exe'),sevenZip])need(fs.existsSync(p),'missing tool '+p);
  Object.assign(process.env,{ELECTRON_BUILDER_7ZIP_PATH:sevenZip,ELECTRON_BUILDER_NSIS_DIR:nsisRoot,
    ELECTRON_BUILDER_NSIS_RESOURCES_DIR:nsisPlugins,ELECTRON_BUILDER_RCEDIT_PATH:rcedit,CSC_IDENTITY_AUTO_DISCOVERY:'false'});
  // Offline only: any implicit tool download fails loudly instead of fetching.
  require('node:net').Socket.prototype.connect=function(){throw new Error('Lean build is offline; a network download was attempted');};

  const config=require('../../electron-builder.config.cjs');
  const outDir=path.join(root,config.directories.output);
  const installer=path.join(outDir,config.win.artifactName.replace('${version}',version));
  const uninstaller=path.join(outDir,path.basename(installer,'exe')+'__uninstaller.exe');
  const template=path.join(root,'node_modules','app-builder-lib','templates','nsis','installer.nsi');
  // makensis 3.04 is not long-path aware: refuse before anything is compiled.
  const nsisPathBound=require('./nsis-path-bound.cjs').assertNsisPathBound({root,nsisRoot,nsisPlugins,
    tempRoot:os.tmpdir(),installer,uninstaller,packageName:pkg.name,version});
  console.log(JSON.stringify({nsisPathBound}));

  const deadline=Date.now()+30*60*1000;
  const budget=()=>need(Date.now()<deadline,'30 minute build deadline');
  const {build,Platform,Arch}=require('electron-builder');
  const binding=await require('./nsis-safe/install-nsis-route.cjs').prepare(root,budget);
  const io=leanIo({installer,uninstaller,outDir,template,reader:binding.reference.reader,work:os.tmpdir()});
  const npm=routeNpm(root);
  const route=binding.install(io,Arch.x64);
  try{
    await build({projectDir:root,config:{...config,electronVersion:pkg.devDependencies.electron,electronDist},
      targets:Platform.WINDOWS.createTarget(['nsis'],Arch.x64),publish:'never'});
    const extraction=route.receipt();
    const r=extraction.receipts[0];
    need(r.bootstrapExecuted===false&&r.reference.equal===true&&r.reference.reference.sha256===r.decoder.outputSha256,'pure uninstaller extraction receipt');
    need(!fs.existsSync(uninstaller),'intermediate uninstaller removed by builder');
    const bytes=fs.readFileSync(installer);
    console.log(JSON.stringify({leanBuild:{version,installer,size:bytes.length,sha256:sha(bytes),
      uninstallerSha256:r.decoder.outputSha256,referenceEqual:true,signCalls:io.receipt().signCalls,
      npmQueries:npm.calls,bootstrapExecuted:false}}));
  }finally{route.restore();npm.restore();}
}
main().catch(e=>{console.error(e&&e.stack?e.stack:String(e));retainFailureExit();});
