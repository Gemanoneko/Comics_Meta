import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const args=process.argv.slice(2);
if(args.length!==3||!['--check','--publish'].includes(args[0])||!path.isAbsolute(args[1])||! /^[a-f0-9]{64}$/.test(args[2]))throw new Error('Usage: release.mjs --check|--publish <absolute QA promotion receipt> <receipt SHA256>');
if(process.platform!=='win32')throw new Error('Reviewed Windows release supervisor required');
// This path never rebuilds. The held supervisor validates and uploads exact QA bytes.
const result=spawnSync('C:/Python314/python.exe',['-I','-S','-B',path.join(root,'scripts/packaging/publish-held.py'),...args],{cwd:root,stdio:'inherit',windowsHide:true,timeout:540000});
if(result.error)throw result.error;process.exitCode=result.status===0?0:1;
