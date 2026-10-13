'use strict';
const fs=require('node:fs/promises');
const path=require('node:path');
const crypto=require('node:crypto');
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
async function main(){
  if(process.platform!=='win32'||process.arch!=='x64'||process.env.COMICS_META_HELD_BUILD!=='1')throw new Error('Use the independently reviewed atomic Windows build supervisor');
  const contractPath=process.env.COMICS_META_BUILD_CONTRACT;
  const expected=process.env.COMICS_META_BUILD_CONTRACT_SHA256;
  if(!contractPath||!path.isAbsolute(contractPath)||! /^[a-f0-9]{64}$/.test(expected||''))throw new Error('Missing pinned held build contract');
  const raw=await fs.readFile(contractPath);if(hash(raw)!==expected)throw new Error('Build contract changed');
  const c=JSON.parse(raw);const root=path.resolve(__dirname,'../..');
  if(c.schema!==1||path.resolve(c.snapshotRoot)!==root||path.resolve(process.cwd())!==root)throw new Error('Build source identity mismatch');
  const version=(await fs.readFile(path.join(root,'VERSION'),'utf8')).trim();
  if(version!==c.version||JSON.parse(await fs.readFile(path.join(root,'package.json'),'utf8')).version!==version)throw new Error('Source version mismatch');
  if(!['qa','production'].includes(c.profile))throw new Error('Unknown build profile');
  const parts=version.split('.').map(Number);
  if(c.profile==='production'&&(parts[0]===0&&parts[1]<2))throw new Error('First production installer requires Sully minor version bump');
  for(const name of ['electronDist','builderCache','nsisRoot','nsisPlugins','rcedit'])if(!c[name]||!path.isAbsolute(c[name]))throw new Error('Missing authenticated offline native tool '+name);
  process.env.ELECTRON_BUILDER_CACHE=c.builderCache;
  process.env.ELECTRON_BUILDER_NSIS_DIR=c.nsisRoot;
  process.env.ELECTRON_BUILDER_NSIS_RESOURCES_DIR=c.nsisPlugins;
  process.env.ELECTRON_BUILDER_RCEDIT_PATH=c.rcedit;
  process.env.CSC_IDENTITY_AUTO_DISCOVERY='false';
  // Refuse implicit native downloads even if an upstream branch regresses.
  const net=require('node:net');
  net.Socket.prototype.connect=function(){throw new Error('Build contract forbids network downloads');};
  // Do not require electron/index.js: that entry implicitly downloads install.js.
  const {build,Platform,Arch}=require('electron-builder');
  await build({projectDir:root,config:{...require('../../electron-builder.config.cjs'),electronVersion:'43.7.9',electronDist:c.electronDist},targets:Platform.WINDOWS.createTarget(['nsis'],Arch.x64),publish:'never'});
}
main().catch(e=>{console.error(e.message);process.exitCode=1;});
