'use strict';
const fs=require('node:fs');
const path=require('node:path');
const {spawnSync}=require('node:child_process');
if(process.env.COMICS_META_HELD_TEST!=='1'||!process.env.COMICS_META_TEST_SCRATCH||!process.env.COMICS_META_TEST_PROTECTED_ROOTS)throw new Error('Python tests require independently reviewed isolated test supervisor');
const runtime=process.env.COMICS_META_TEST_PYTHON;
if(!runtime||!path.isAbsolute(runtime)||!fs.statSync(runtime).isFile())throw new Error('Pinned test Python missing');
// Isolated path/byte/Job ownership is held by the calling reviewed supervisor.
const result=spawnSync(runtime,['-I','-B','-c',"import os,sys,unittest; sys.path.insert(0,os.getcwd()); result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover('tests')); raise SystemExit(not result.wasSuccessful())"],{cwd:path.resolve(__dirname,'..'),windowsHide:true,stdio:'inherit',timeout:540000});
if(result.error)throw result.error;process.exitCode=result.status===0?0:1;
