'use strict';
const fs=require('node:fs/promises');
const path=require('node:path');
const crypto=require('node:crypto');
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const {retainFailureExit}=require('./failure-exit.cjs');
async function main(){
  if(process.platform!=='win32'||process.arch!=='x64'||process.env.COMICS_META_HELD_BUILD!=='1')throw new Error('Use the independently reviewed atomic Windows build supervisor');
  const contractPath=process.env.COMICS_META_BUILD_CONTRACT;
  const expected=process.env.COMICS_META_BUILD_CONTRACT_SHA256;
  if(!contractPath||!path.isAbsolute(contractPath)||! /^[a-f0-9]{64}$/.test(expected||''))throw new Error('Missing pinned held build contract');
  const raw=await fs.readFile(contractPath);if(hash(raw)!==expected)throw new Error('Build contract changed');
  const c=JSON.parse(raw);const root=path.resolve(__dirname,'../..');
  if(c.schema!==1||path.resolve(c.snapshotRoot)!==root||path.resolve(process.cwd())!==root)throw new Error('Build source identity mismatch');
  const version=(await fs.readFile(path.join(root,'VERSION'),'utf8')).trim();
  const pkg=JSON.parse(await fs.readFile(path.join(root,'package.json'),'utf8'));
  if(version!==c.version||pkg.version!==version)throw new Error('Source version mismatch');
  if(!['qa','production'].includes(c.profile))throw new Error('Unknown build profile');
  const parts=version.split('.').map(Number);
  if(c.profile==='production'&&(parts[0]===0&&parts[1]<2))throw new Error('First production installer requires Sully minor version bump');
  for(const name of ['electronDist','builderCache','nsisRoot','nsisPlugins','rcedit','sevenZip'])if(!c[name]||!path.isAbsolute(c[name]))throw new Error('Missing authenticated offline native tool '+name);
  const sevenZipBytes=await fs.readFile(c.sevenZip);
  if(hash(sevenZipBytes)!==c.sevenZipSha256)throw new Error('Held offline 7za identity changed');
  process.env.ELECTRON_BUILDER_7ZIP_PATH=c.sevenZip;
  process.env.ELECTRON_BUILDER_CACHE=c.builderCache;
  process.env.ELECTRON_BUILDER_NSIS_DIR=c.nsisRoot;
  process.env.ELECTRON_BUILDER_NSIS_RESOURCES_DIR=c.nsisPlugins;
  process.env.ELECTRON_BUILDER_RCEDIT_PATH=c.rcedit;
  process.env.CSC_IDENTITY_AUTO_DISCOVERY='false';
  // Refuse implicit native downloads even if an upstream branch regresses.
  const net=require('node:net');
  net.Socket.prototype.connect=function(){throw new Error('Build contract forbids network downloads');};
  // Do not require electron/index.js: that entry implicitly downloads install.js.
  if(!Number.isSafeInteger(c.originalDeadlineUnixMs)||Date.now()>=c.originalDeadlineUnixMs)throw new Error('Original build deadline missing or expired');
  const checkBudget=()=>{if(Date.now()>=c.originalDeadlineUnixMs)throw new Error('Original complete build deadline');};
  const ioPath=process.env.COMICS_META_NSIS_IO_CONFIG;
  const ioSha=process.env.COMICS_META_NSIS_IO_CONFIG_SHA256;
  if(!ioPath||!path.isAbsolute(ioPath)||! /^[a-f0-9]{64}$/.test(ioSha||''))throw new Error('Missing parent-held NSIS I/O configuration');
  const ioBytes=await fs.readFile(ioPath);
  if(hash(ioBytes)!==ioSha)throw new Error('NSIS I/O configuration changed');
  const decoderControls=require('./nsis-safe/decoder-cases.cjs').runSynthetic();
  console.log(JSON.stringify({decoderControls}));
  // Legacy-path makensis inputs are measured on the actual materialized snapshot
  // and broker-bound output roles before any builder module loads.
  const roles=JSON.parse(ioBytes);
  const nsisPathBound=require('./nsis-path-bound.cjs').assertNsisPathBound({root,nsisRoot:c.nsisRoot,nsisPlugins:c.nsisPlugins,
    tempRoot:require('node:os').tmpdir(),installer:roles.installer,uninstaller:roles.uninstaller,packageName:pkg.name,version});
  console.log(JSON.stringify({nsisPathBound}));
  // Initialize the normal upstream entry before inspecting its internal classes.
  // Interception is installed below before build() can construct any target.
  const {build,Platform,Arch}=require('electron-builder');
  const {prepare}=require('./nsis-safe/install-nsis-route.cjs');
  const {createIo}=require('./nsis-safe/client.cjs');
  const binding=await prepare(root,checkBudget);
  const io=createIo(ioBytes,ioSha,checkBudget,binding.reference);
  const npmRoute=await require('./npm-query-route.cjs').install(root,c,checkBudget);
  const route=binding.install(io,Arch.x64);
  try {
    await build({projectDir:root,config:{...require('../../electron-builder.config.cjs'),electronVersion:'43.7.9',electronDist:c.electronDist},targets:Platform.WINDOWS.createTarget(['nsis'],Arch.x64),publish:'never'});
    checkBudget();
    console.log(JSON.stringify({safeNsisRoute:route.receipt(),nativeIo:io.receipt(),npmQueries:npmRoute.receipt(),bootstrapExecuted:false}));
  } finally {route.restore();npmRoute.restore();}
}
main().catch(e=>{console.error(e&&e.stack?e.stack:String(e));retainFailureExit();});
