// One inert native-ownership probe. Never starts an app, Sandbox or shutdown command.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {digest,requireThat,verifyInventory,writeJson} from './common.mjs';
const script=fileURLToPath(import.meta.url),tool=path.resolve(path.dirname(script),'../../..');
const root=path.join(tool,'scratch/native-failure-abort-061-20261110');
const input=path.join(tool,'scratch/install-update-061-20261110/retry03/input');
const manifestSha='f69e0559cdac7748fc1164ed3e79dfb261975dc74ef85e593bde81e8a511d96e';
const [role,identity]=process.argv.slice(2);
requireThat(process.platform==='win32'&&process.arch==='x64'&&process.argv.length===4,'Exact Windows probe arguments required');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const ownerModule=()=>import(pathToFileURL(path.join(input,'owner/bounded-check.mjs')));
const environment={SystemRoot:'C:\\Windows',WINDIR:'C:\\Windows',ComSpec:'C:\\Windows\\System32\\cmd.exe',PATH:'C:\\Windows\\System32',TEMP:path.join(root,'temp'),TMP:path.join(root,'temp')};
if(role==='run') {
  requireThat(/^[a-f0-9]{64}$/.test(identity)&&digest(fs.readFileSync(script))===identity,'Reviewed probe source changed');
  requireThat(path.resolve(process.execPath).toLowerCase()===path.resolve(input,'node/node.exe').toLowerCase(),'Use pinned staged Node');
  const raw=fs.readFileSync(input+'/input-manifest.json');requireThat(digest(raw)===manifestSha,'Reviewed input manifest changed');verifyInventory(input,JSON.parse(raw).files,{allowManifest:true});
  requireThat(!fs.existsSync(root),'Fresh fixed probe scratch required; no automatic duplicate');fs.mkdirSync(root);fs.mkdirSync(path.join(root,'temp'));
  const nonce=crypto.randomBytes(16).toString('hex');writeJson(path.join(root,'plan.json'),{nonce,sourceSha256:identity,manifestSha256:manifestSha});
  const {runOwned}=await ownerModule();
  const owned=await runOwned(process.execPath,[script,'probe',nonce],{cwd:root,env:environment,timeoutMs:60000,maxBytes:1024*1024,koffiRoot:input+'/ownership/node_modules/koffi'});
  writeJson(path.join(root,'outer-owned.json'),owned);
  requireThat(owned.ok&&owned.code===0&&owned.closed&&!owned.forced&&!owned.timedOut&&owned.outputComplete&&owned.native?.complete&&owned.native.zero,'Native probe outer owner failed');
  console.log(JSON.stringify({pass:true,root,outerNative:owned.native}));
} else {
  const plan=JSON.parse(fs.readFileSync(path.join(root,'plan.json')));
  requireThat(plan.nonce===identity&&/^[a-f0-9]{32}$/.test(identity)&&plan.sourceSha256===digest(fs.readFileSync(script))&&plan.manifestSha256===manifestSha,'Probe child identity changed');
  if(role==='leaf')setTimeout(()=>process.exit(0),30000);
  else if(role==='tree') {
    const leaf=spawn(process.execPath,[script,'leaf',identity],{cwd:root,env:environment,windowsHide:true,stdio:'ignore'});
    leaf.once('error',error=>{throw error;});
    leaf.once('spawn',()=>writeJson(path.join(root,'tree-ready.json'),{nonce:identity,rootPid:process.pid,descendantPid:leaf.pid}));
    setTimeout(()=>process.exit(0),30000);
  } else if(role==='sibling') {
    process.stdin.setEncoding('utf8');let message='';process.stdin.on('data',chunk=>{message+=chunk;if(message.trim()==='quit')process.exit(0);});
    console.log(JSON.stringify({siblingReady:process.pid}));setTimeout(()=>process.exit(0),30000);
  } else {
    requireThat(role==='probe','Unknown probe role');
    const {runOwned,createPrivateJob}=await ownerModule();
    const require=createRequire(import.meta.url),koffi=require(input+'/ownership/node_modules/koffi'),kernel=koffi.load('kernel32.dll');
    const open=kernel.func('void* __stdcall OpenProcess(uint32_t,bool,uint32_t)'),wait=kernel.func('uint32_t __stdcall WaitForSingleObject(void*,uint32_t)'),close=kernel.func('bool __stdcall CloseHandle(void*)');
    const image=kernel.func('bool __stdcall QueryFullProcessImageNameW(void*,uint32_t,void*,void*)');
    const handles=[];
    function retain(pid){const handle=open(0x00101000,false,pid);requireThat(handle,'Cannot retain exact inert probe process');handles.push(handle);const buffer=Buffer.alloc(65536),size=Buffer.alloc(4);size.writeUInt32LE(32768);requireThat(image(handle,0,buffer,size)&&path.resolve(buffer.subarray(0,size.readUInt32LE()*2).toString('utf16le')).toLowerCase()===path.resolve(process.execPath).toLowerCase(),'Probe process image mismatch');return handle;}
    const evidence={schema:1,nonce:identity,sourceSha256:plan.sourceSha256,manifestSha256:manifestSha,started:Date.now(),pass:false};
    let sibling,innerPromise,job,innerFinished=false,terminated=false;
    try {
      sibling=spawn(process.execPath,[script,'sibling',identity],{cwd:root,env:environment,windowsHide:true,stdio:['pipe','pipe','pipe']});
      sibling.stdin.on('error',()=>{});sibling.stdout.resume();sibling.stderr.resume();
      await new Promise((resolve,reject)=>{sibling.once('spawn',resolve);sibling.once('error',reject);});
      const siblingHandle=retain(sibling.pid);evidence.siblingPid=sibling.pid;
      innerPromise=runOwned(process.execPath,[script,'tree',identity],{cwd:root,env:environment,timeoutMs:15000,maxBytes:65536,koffiRoot:input+'/ownership/node_modules/koffi',jobFactory:koffiRoot=>{job=createPrivateJob(koffiRoot);return job;}}).then(result=>{innerFinished=true;return result;});
      const readyFile=path.join(root,'tree-ready.json'),readyDeadline=Date.now()+10000;
      while(!fs.existsSync(readyFile)&&Date.now()<readyDeadline&&!innerFinished)await sleep(20);
      requireThat(fs.existsSync(readyFile),'Owned root/descendant did not become ready');const ready=JSON.parse(fs.readFileSync(readyFile));
      requireThat(ready.nonce===identity&&Number.isSafeInteger(ready.rootPid)&&Number.isSafeInteger(ready.descendantPid)&&ready.rootPid!==ready.descendantPid,'Owned probe tree identity invalid');
      const rootHandle=retain(ready.rootPid),leafHandle=retain(ready.descendantPid);evidence.tree=ready;evidence.before=job.sample();
      requireThat(evidence.before.complete&&evidence.before.active>=3&&[rootHandle,leafHandle,siblingHandle].every(handle=>wait(handle,0)===258),'Real probe processes not live in expected Job');
      job.terminate();terminated=true;evidence.termination='Exact captured inner createPrivateJob.terminate; no numeric PID termination';
      evidence.inner=await innerPromise;
      evidence.after={rootSignaled:wait(rootHandle,0)===0,descendantSignaled:wait(leafHandle,0)===0,siblingStillLive:wait(siblingHandle,0)===258};
      requireThat(evidence.inner.ok===false&&evidence.inner.closed&&evidence.inner.native?.complete&&evidence.inner.native.zero&&Object.values(evidence.after).every(Boolean),'Inner abort closure or unrelated sibling isolation failed');
      const siblingExit=new Promise(resolve=>sibling.once('close',(code,signal)=>resolve({code,signal})));sibling.stdin.end('quit\n');
      evidence.siblingExit=await siblingExit;requireThat(evidence.siblingExit.code===0&&evidence.siblingExit.signal===null&&wait(siblingHandle,0)===0,'Unrelated sibling did not exit gracefully');
      evidence.pass=true;
    }catch(error){evidence.error=String(error.stack||error);}
    finally {
      if(job&&!innerFinished&&!terminated){try{job.terminate();terminated=true;}catch(error){evidence.cleanupError=String(error);}}
      if(innerPromise&&!innerFinished)evidence.cleanupInner=await innerPromise;
      if(sibling&&sibling.exitCode===null)sibling.stdin.end('quit\n');
      for(const handle of handles)close(handle);
      evidence.finished=Date.now();writeJson(path.join(root,'native-probe.json'),evidence);
    }
    console.log(JSON.stringify({pass:evidence.pass,after:evidence.after,error:evidence.error}));process.exitCode=evidence.pass?0:1;
  }
}
