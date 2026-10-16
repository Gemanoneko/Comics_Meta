'use strict';
const fs=require('node:fs/promises');const path=require('node:path');const crypto=require('node:crypto');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
module.exports=async function(context){
  if(process.env.COMICS_META_HELD_BUILD!=='1'&&process.env.COMICS_META_LEAN_BUILD!=='1')throw new Error('Run through scripts/build-installer.cjs');
  const root=context.packager.projectDir;const stage=path.join(root,'build','staged');
  const raw=await fs.readFile(path.join(root,'build','staged-manifest.json'));
  if(sha(raw)!==process.env.COMICS_META_STAGED_MANIFEST_SHA256)throw new Error('Staged manifest identity changed');
  const manifest=JSON.parse(raw);if(manifest.schema!==2)throw new Error('Expected held source/runtime manifest schema2');
  const files=[];const directories=[];
  async function walk(dir){for(const e of await fs.readdir(dir,{withFileTypes:true})){
    const p=path.join(dir,e.name);const rel=path.relative(stage,p).split(path.sep).join('/');
    if(e.isSymbolicLink())throw new Error('Staged reparse entry refused');
    if(e.isDirectory()){directories.push(rel);await walk(p);}else if(e.isFile())files.push({path:rel,sha256:sha(await fs.readFile(p))});else throw new Error('Staged nonregular entry');
  }}
  await walk(stage);files.sort((a,b)=>a.path.localeCompare(b.path,'en'));directories.sort();
  const expected=[...manifest.files].sort((a,b)=>a.path.localeCompare(b.path,'en'));
  if(JSON.stringify(files)!==JSON.stringify(expected)||JSON.stringify(directories)!==JSON.stringify([...manifest.directories].sort()))throw new Error('Complete staged path/byte inventory changed');
  const capsule=JSON.parse(await fs.readFile(path.join(stage,'engine','update-runtime-manifest.json'),'utf8'));
  const keys=(value,expected)=>value&&typeof value==='object'&&!Array.isArray(value)&&JSON.stringify(Object.keys(value).sort())===JSON.stringify([...expected].sort());
  const relative=value=>typeof value==='string'&&value.length>0&&!value.includes('\\')&&!value.includes(':')&&value.split('/').every(x=>x&&x!=='.'&&x!=='..');
  const hex=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
  if(!keys(capsule,['schema','python','helperSha256'])||capsule.schema!==1||!keys(capsule.python,['files','directories'])||!Array.isArray(capsule.python.files)||!Array.isArray(capsule.python.directories)||!hex(capsule.helperSha256))throw new Error('Invalid update runtime manifest schema');
  const capsuleNames=new Set();
  for(const item of capsule.python.files){
    if(!keys(item,['path','sha256'])||!relative(item.path)||!hex(item.sha256)||capsuleNames.has(item.path.toLowerCase()))throw new Error('Invalid/duplicate Python file member');
    capsuleNames.add(item.path.toLowerCase());
  }
  for(const name of capsule.python.directories){
    if(!relative(name)||capsuleNames.has(name.toLowerCase()))throw new Error('Invalid/duplicate Python directory member');
    capsuleNames.add(name.toLowerCase());
  }
  const prefix='runtime/python/';
  const pythonFiles=files.filter(x=>x.path.startsWith(prefix)).map(x=>({path:x.path.slice(prefix.length),sha256:x.sha256}));
  const pythonDirectories=directories.filter(x=>x.startsWith(prefix)).map(x=>x.slice(prefix.length)).sort();
  const capsuleFiles=capsule.python.files.map(x=>({path:x.path,sha256:x.sha256})).sort((a,b)=>a.path.localeCompare(b.path,'en'));
  if(JSON.stringify(pythonFiles)!==JSON.stringify(capsuleFiles)||JSON.stringify(pythonDirectories)!==JSON.stringify([...capsule.python.directories].sort()))throw new Error('Complete packaged Python path/type/hash closure differs');
  if(sha(await fs.readFile(path.join(stage,'engine','installer_launch.py')))!==capsule.helperSha256)throw new Error('Packaged update helper hash differs');
  const version=(await fs.readFile(path.join(root,'VERSION'),'utf8')).trim();
  if(version!==manifest.version||version!==context.packager.appInfo.version||(await fs.readFile(path.join(stage,'engine','VERSION'),'utf8')).trim()!==version)throw new Error('Bundled/displayed version mismatch');
  if(!manifest.engineSources.some(x=>x.source==='comic_recovery.py')||!manifest.engineSources.some(x=>x.source==='desktop/installer_launch.py'))throw new Error('Recovery/update-launch helper closure missing');
  for(const item of manifest.engineSources){
    if(item.source.split('/').some(x=>x==='..')||item.packaged.split('/').some(x=>x==='..'))throw new Error('Unsafe engine source mapping');
    if(sha(await fs.readFile(path.join(root,item.source)))!==item.sha256||sha(await fs.readFile(path.join(stage,item.packaged)))!==item.sha256)throw new Error('Engine source differs: '+item.source);
  }
};
