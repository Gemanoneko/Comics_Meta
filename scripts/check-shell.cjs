'use strict';
const fs=require('node:fs');
const path=require('node:path');
const {spawnSync}=require('node:child_process');
if(process.env.COMICS_META_HELD_TEST!=='1'||!process.env.COMICS_META_TEST_SCRATCH||!process.env.COMICS_META_TEST_PROTECTED_ROOTS)throw new Error('Shell tests require independently reviewed isolated test supervisor');
const root=path.resolve(__dirname,'..');
const directory=path.join(root,'desktop','tests');
const tests=fs.readdirSync(directory,{withFileTypes:true}).filter(entry=>entry.name.endsWith('.test.cjs')).sort((a,b)=>a.name<b.name?-1:a.name>b.name?1:0);
if(!tests.length||tests.length>1000||tests.some(entry=>!entry.isFile()||entry.isSymbolicLink()))throw new Error('Unexpected shell test inventory');
// The caller pins this complete source inventory and Node runtime and retains
// the original total deadline and native Job ownership for every test child.
// Explicit argv preserves the complete former desktop/tests/*.test.cjs set.
const result=spawnSync(process.execPath,['--test',...tests.map(entry=>path.join(directory,entry.name))],{cwd:root,windowsHide:true,stdio:'inherit',timeout:540000});
if(result.error)throw result.error;
process.exitCode=result.status===0?0:1;
