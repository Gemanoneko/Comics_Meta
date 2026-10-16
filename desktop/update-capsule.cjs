'use strict';
const fs=require('node:fs/promises');
const path=require('node:path');
const crypto=require('node:crypto');
const digest=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
function relative(value){
  if(typeof value!=='string'||!value||/[<>"|?*\u0000-\u001f]/.test(value)||value.includes('\\')||value.includes(':')||value.split('/').some(part=>!part||part==='.'||part==='..'||/[. ]$/.test(part)))throw Error('Unsafe update runtime member');
  return value;
}
async function ancestors(target){
  const resolved=path.resolve(target);let current=path.parse(resolved).root;
  for(const part of resolved.slice(current.length).split(path.sep).filter(Boolean)){current=path.join(current,part);const stat=await fs.lstat(current);if(!stat.isDirectory()||stat.isSymbolicLink())throw Error('Update runtime ancestor is not a regular directory');}
}
// Bytecode caches (Sergei's real 0.2.2->0.2.3 update): a Python run without -B writes __pycache__\*.pyc
// beside the modules it imports. They are never in the manifest and never copied (the capsule is built
// from the manifest alone), so an unlisted __pycache__ holding only regular .pyc files (or the
// interpreter's own .pyc.<n> write temporaries) is left out of the INSTALLED source's inventory.
// Anything else in it (another file, a link, a subfolder) keeps the folder in, and the check refuses.
// The capsule copy is always inventoried strictly.
const BYTECODE=/^[^/\\]+\.pyc(?:\.[0-9]+)?$/;
async function bytecodeOnly(folder){for(const item of await fs.readdir(folder,{withFileTypes:true})){if(!BYTECODE.test(item.name))return false;const stat=await fs.lstat(path.join(folder,item.name));if(!stat.isFile()||stat.isSymbolicLink())return false;}return true;}
async function inventory(root,{listed=null}={}){
  await ancestors(root);const files=[],directories=[];
  async function visit(folder){for(const item of await fs.readdir(folder,{withFileTypes:true})){const absolute=path.join(folder,item.name),name=path.relative(root,absolute).split(path.sep).join('/');relative(name);const stat=await fs.lstat(absolute);if(stat.isSymbolicLink())throw Error('Update runtime contains a link');if(stat.isDirectory()){if(listed&&item.name==='__pycache__'&&!listed.has(name)&&await bytecodeOnly(absolute))continue;directories.push(name);await visit(absolute);}else if(stat.isFile()){files.push({path:name,sha256:digest(await fs.readFile(absolute))});}else throw Error('Update runtime contains a special file');}}
  await visit(root);return{files:files.sort((a,b)=>a.path.localeCompare(b.path,'en')),directories:directories.sort()};
}
function normalized(manifest){
  if(manifest?.schema!==1||!Array.isArray(manifest.python?.files)||!Array.isArray(manifest.python?.directories)||! /^[a-f0-9]{64}$/.test(manifest.helperSha256))throw Error('Invalid update runtime manifest');
  const seen=new Set();const files=manifest.python.files.map(item=>{const name=relative(item.path),fold=name.toLowerCase();if(seen.has(fold)||! /^[a-f0-9]{64}$/.test(item.sha256))throw Error('Duplicate or invalid update runtime member');seen.add(fold);return{path:name,sha256:item.sha256};});
  const directories=manifest.python.directories.map(name=>{relative(name);const fold=name.toLowerCase();if(seen.has(fold))throw Error('Duplicate update runtime directory');seen.add(fold);return name;});
  if(!files.some(item=>item.path==='python.exe')||!files.some(item=>/^python[0-9]+\.dll$/.test(item.path)))throw Error('Update runtime interpreter closure missing');
  return{files:files.sort((a,b)=>a.path.localeCompare(b.path,'en')),directories:directories.sort()};
}

async function modulePaths(root,python,expected){
  const configs=expected.files.filter(item=>/^python[0-9]+\._pth$/.test(item.path));if(configs.length!==1)throw Error('Update runtime module-path closure missing');
  const lines=(await fs.readFile(path.join(python,configs[0].path),'utf8')).split(/\r?\n/).map(line=>line.trim()).filter(line=>line&&!line.startsWith('#'));
  const resolved=[];
  for(const line of lines){if(line==='import site'||line.startsWith('import ')||path.isAbsolute(line)||/[:\\\u0000-\u001f]/.test(line))throw Error('Unsafe update runtime module path');const target=path.resolve(python,line),rel=path.relative(root,target);if(!rel||rel==='..'||rel.startsWith('..'+path.sep)||path.isAbsolute(rel))throw Error('Update runtime module path escapes capsule');await ancestors(path.dirname(target));const stat=await fs.lstat(target);if(stat.isSymbolicLink()||(!stat.isDirectory()&&!stat.isFile()))throw Error('Unsafe update runtime module path');resolved.push(target);}
  if(!resolved.includes(python)||!resolved.includes(path.join(root,'engine'))||!resolved.includes(path.join(python,'python'+configs[0].path.match(/^python([0-9]+)/)[1]+'.zip')))throw Error('Update runtime required module path missing');
  return resolved;
}

// Everything alive during NSIS replacement is copied outside the installed tree.
// Failed/uncertain capsules remain evidence; never delete a potentially loaded DLL.
async function prepareUpdateCapsule({resources,workRoot}){
  const install=path.resolve(resources),base=path.resolve(workRoot);
  const within=path.relative(path.dirname(install),base);if(!within||(!within.startsWith('..'+path.sep)&&within!=='..'&&!path.isAbsolute(within)))throw Error('Update capsule must be outside the installed resources');
  await ancestors(install);await ancestors(path.dirname(base));await fs.mkdir(base,{recursive:false}).catch(error=>{if(error.code!=='EEXIST')throw error;});await ancestors(base);
  const manifestPath=path.join(install,'engine','update-runtime-manifest.json');const manifestStat=await fs.lstat(manifestPath);if(!manifestStat.isFile()||manifestStat.isSymbolicLink()||manifestStat.size>2*1024*1024)throw Error('Invalid update runtime manifest file');
  const manifest=JSON.parse(await fs.readFile(manifestPath,'utf8')),expected=normalized(manifest);
  const source=path.join(install,'runtime','python'),helper=path.join(install,'engine','installer_launch.py');await ancestors(path.dirname(helper));
  const helperStat=await fs.lstat(helper);if(!helperStat.isFile()||helperStat.isSymbolicLink())throw Error('Invalid updater helper');const helperBytes=await fs.readFile(helper);if(digest(helperBytes)!==manifest.helperSha256)throw Error('Updater helper identity differs');
  const installed={listed:new Set(expected.directories)};
  if(JSON.stringify(await inventory(source,installed))!==JSON.stringify(expected))throw Error('Update runtime source closure differs');
  const root=await fs.mkdtemp(path.join(base,'launch-'));await ancestors(root);const runtime=path.join(root,'runtime');await fs.mkdir(runtime);await ancestors(runtime);const python=path.join(runtime,'python');await fs.mkdir(python);await ancestors(python);const engine=path.join(root,'engine');await fs.mkdir(engine);await ancestors(engine);
  for(const name of [...expected.directories].sort((a,b)=>a.split('/').length-b.split('/').length||a.localeCompare(b))){await ancestors(path.dirname(path.join(python,name)));await fs.mkdir(path.join(python,name));}
  for(const item of expected.files){const src=path.join(source,item.path),dest=path.join(python,item.path);await ancestors(path.dirname(src));await ancestors(path.dirname(dest));const stat=await fs.lstat(src);if(!stat.isFile()||stat.isSymbolicLink())throw Error('Updater runtime input type changed');const bytes=await fs.readFile(src);if(digest(bytes)!==item.sha256)throw Error('Updater runtime input changed');await fs.writeFile(dest,bytes,{flag:'wx'});}
  const copiedHelper=path.join(engine,'installer_launch.py');await fs.writeFile(copiedHelper,helperBytes,{flag:'wx'});
  await fs.writeFile(path.join(root,'runtime-manifest.json'),JSON.stringify(manifest),{flag:'wx'});
  if(JSON.stringify(await inventory(source,installed))!==JSON.stringify(expected)||JSON.stringify(await inventory(python))!==JSON.stringify(expected)||digest(await fs.readFile(helper))!==manifest.helperSha256||digest(await fs.readFile(copiedHelper))!==manifest.helperSha256)throw Error('Update capsule closure changed');
  await modulePaths(root,python,expected);
  return{python:path.join(python,'python.exe'),helper:copiedHelper,root};
}
module.exports={prepareUpdateCapsule,inventory,normalized,modulePaths};
