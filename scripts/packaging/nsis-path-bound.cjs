'use strict';
// Fail-closed legacy path preflight for the held NSIS compiler (source24).
// Pinned makensis 3.0.4.1 opens !include, plugin, icon and File inputs through
// non-long-path-aware Win32 calls. Actual23 failed its first !include because the
// authentic StdUtils.nsh snapshot path was 264 characters. This measures every
// ACTUAL materialized file the compiler can be handed or open (templates, build
// resources, NSIS/plugin closure, include-directory enumeration patterns) plus
// the broker-bound output roles, and refuses before the builder module loads.
const fs=require('node:fs');
const path=require('node:path');
const LIMIT=254;
function need(value,message){if(!value)throw new Error('NSIS path bound: '+message);}
function walk(root,out){
  need(path.isAbsolute(root),'absolute root '+root);
  const stat=fs.lstatSync(root);
  need(stat.isDirectory()&&!stat.isSymbolicLink(),'real directory '+root);
  out.push(path.join(root,'*.*'));
  for(const entry of fs.readdirSync(root,{withFileTypes:true})){
    const child=path.join(root,entry.name);
    need(!entry.isSymbolicLink(),'no reparse member '+child);
    if(entry.isDirectory())walk(child,out);
    else{need(entry.isFile(),'regular member '+child);out.push(child);}
  }
  return out;
}
function measureNsisPaths(o){
  for(const key of ['root','nsisRoot','nsisPlugins','tempRoot','installer','uninstaller'])need(typeof o[key]==='string'&&path.isAbsolute(o[key]),'absolute '+key);
  need(/^[a-z0-9-]+$/.test(o.packageName||'')&&/^[0-9]+\.[0-9]+\.[0-9]+$/.test(o.version||''),'package name/version');
  const candidates=[];
  walk(path.join(o.root,'node_modules','app-builder-lib','templates','nsis'),candidates);
  walk(path.join(o.root,'desktop','assets'),candidates);
  walk(o.nsisRoot,candidates);
  walk(o.nsisPlugins,candidates);
  const outDir=path.dirname(o.installer);
  need(path.dirname(o.uninstaller)===outDir,'output roles share one directory');
  candidates.push(o.installer,o.uninstaller,path.join(outDir,`${o.packageName}-${o.version}-x64.nsis.7z`));
  // temp-file root t-<6> holding counter-named messages.nsh; makensis own temp.
  candidates.push(path.join(o.tempRoot,'t-XXXXXX','zzzz-messages.nsh'),path.join(o.tempRoot,'nstFFFF.tmp'));
  let longest='';
  for(const candidate of candidates)if(candidate.length>longest.length)longest=candidate;
  return {count:candidates.length,max:longest.length,longest};
}
function assertNsisPathBound(o,limit=LIMIT){
  need(Number.isInteger(limit)&&limit>0,'positive integer limit');
  const measured=measureNsisPaths(o);
  need(measured.max<=limit,`${measured.max} characters exceeds ${limit}: ${measured.longest}`);
  return {limit,...measured};
}
module.exports={LIMIT,measureNsisPaths,assertNsisPathBound};
