'use strict';
const path=require('node:path');const {spawnSync}=require('node:child_process');
const args=process.argv.slice(2);
if(args.length!==2||!path.isAbsolute(args[0])||! /^[a-f0-9]{64}$/.test(args[1]))throw new Error('Usage: build-installer.cjs <absolute reviewed build contract> <SHA256>; invoke only through outer atomic Windows Job');
const result=spawnSync('C:/Python314/python.exe',['-I','-S','-B',path.join(__dirname,'packaging','build-owned.py'),...args],{cwd:path.resolve(__dirname,'..'),stdio:'inherit',windowsHide:true,timeout:550000});
if(result.error)throw result.error;process.exitCode=result.status===0?0:1;
