// The only shutdown invocation is in this guest-only entrypoint after identity validation.
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {performance} from 'node:perf_hooks';
import {digest,requireThat,verifyInventory,writeJson,safeGuestIdentity,failedGuestWorkflow} from './common.mjs';

const root=path.dirname(fileURLToPath(import.meta.url));
const args=process.argv.slice(2);
requireThat(args.length===8 && args[0]==='--mode' && args[2]==='--nonce' && args[4]==='--manifest-sha' && args[6]==='--session-sha','Exact guest arguments required');
const mode=args[1],nonce=args[3],expected=args[5];
requireThat(['processing','paused'].includes(mode) && /^[a-f0-9]{32}$/.test(nonce) && /^[a-f0-9]{64}$/.test(expected),'Invalid guest identity');
const bytes=fs.readFileSync(path.join(root,'input-manifest.json'));
requireThat(digest(bytes)===expected,'Input manifest identity changed');
const manifest=JSON.parse(bytes),plan=JSON.parse(fs.readFileSync(path.join(root,'plan.json')));
requireThat(manifest.schema===1 && plan.schema===1 && plan.runs[mode].nonce===nonce,'Wrong guest phase');
const identity={scriptRoot:root,pid:process.pid,user:process.env.USERNAME,profile:process.env.USERPROFILE,computer:process.env.COMPUTERNAME};
// Guest built-in OS query is read-only. It cannot enable a host shutdown path.
const identityQuery=spawnSync('C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',[
  '-NoLogo','-NoProfile','-NonInteractive','-Command',"$m=Get-CimInstance Win32_ComputerSystem;$i=[Security.Principal.WindowsIdentity]::GetCurrent();[pscustomobject]@{Model=$m.Model;Manufacturer=$m.Manufacturer;Name=$m.Name;TokenName=$i.Name;TokenSid=$i.User.Value;Profile=[Environment]::GetFolderPath('UserProfile')} | ConvertTo-Json -Compress"
],{windowsHide:true,encoding:'utf8',timeout:10000,maxBuffer:65536});
requireThat(identityQuery.status===0,'Guest OS identity query failed');
const machine=JSON.parse(identityQuery.stdout); identity.model=machine.Model; identity.manufacturer=machine.Manufacturer;
identity.computer=machine.Name;identity.tokenName=machine.TokenName;identity.tokenSid=machine.TokenSid;identity.profile=machine.Profile;
requireThat(safeGuestIdentity(identity,plan.hostName),'This entrypoint is not inside the intended Windows Sandbox guest');
const output='C:/CMOOutput';
const started=Date.now();
let result,failed;
try {
  const requestRaw=fs.readFileSync(output+'/session-request.json');
  requireThat(digest(requestRaw)===args[7],'Original host deadline request differs');
  const request=JSON.parse(requestRaw),remaining=request.deadlineEpochMs-Date.now();
  requireThat(request.mode===mode&&request.nonce===nonce&&request.manifestSha256===expected&&remaining>90000&&remaining<=600000&&request.startedEpochMs<=Date.now()+10000,'Invalid original host deadline');
  const deadline=performance.now()+remaining;
  verifyInventory(root,manifest.files,{allowManifest:true});
  requireThat(fs.statSync(output).isDirectory() && JSON.stringify(fs.readdirSync(output))===JSON.stringify(['session-request.json']),'Guest evidence output has unexpected files');
  writeJson(output+'/guest-started.json',{schema:1,mode,nonce,manifestSha256:expected,sourceHead:plan.sourceHead,identity});
  const gateEnd=Math.min(performance.now()+45000,deadline-60000);
  while(!fs.existsSync(output+'/go.json')&&performance.now()<gateEnd)await new Promise(resolve=>setTimeout(resolve,100));
  requireThat(fs.existsSync(output+'/go.json'),'Host did not establish unique owned Sandbox identity; no installer started');
  const go=JSON.parse(fs.readFileSync(output+'/go.json'));
  requireThat(go.nonce===nonce&&go.mode===mode&&go.manifestSha256===expected&&/^[a-f0-9-]{36}$/.test(go.computeId)&&Number.isSafeInteger(go.clientPid),'Host session go identity differs');
  const qroot='C:/Q/illuminati-cmo-qa-'+mode;fs.mkdirSync(qroot,{recursive:true});
  const {runOwned,createPrivateJob}=await import(pathToFileURL(path.join(root,'owner/bounded-check.mjs')));
  const environment={SystemRoot:'C:\\Windows',WINDIR:'C:\\Windows',ComSpec:'C:\\Windows\\System32\\cmd.exe',
    PATH:'C:\\Windows\\System32',TEMP:'C:\\Q',TMP:'C:\\Q',USERPROFILE:process.env.USERPROFILE,USERNAME:process.env.USERNAME,
    LOCALAPPDATA:process.env.LOCALAPPDATA,APPDATA:process.env.APPDATA,PYTHONDONTWRITEBYTECODE:'1',PYTHONUTF8:'1',PYTHONIOENCODING:'utf-8'};
  const budget=Math.floor(deadline-performance.now()-60000);requireThat(budget>2000,'Guest preflight consumed the original work budget');
  let appJob,workflowAbort,abortError;
  const monitor=setInterval(()=>{
    if(!appJob||workflowAbort)return;
    try{
      const file=output+'/update-result.json';if(!fs.existsSync(file))return;
      const raw=fs.readFileSync(file),value=JSON.parse(raw);
      if(!failedGuestWorkflow(value,{mode,nonce,sourceHead:plan.sourceHead,artifactSha256:plan.artifact.sha256}))return;
      workflowAbort={schema:1,mode,nonce,reason:'Failed guest workflow after bounded graceful cleanup; abort only its own private app Job',observedEpochMs:Date.now(),resultSha256:digest(raw)};
      writeJson(output+'/guest-workflow-abort.json',workflowAbort);
      appJob.terminate();
    }catch(error){abortError=String(error);}
  },250);
  try {
    result=await runOwned(process.execPath,[path.join(root,'guest-update.mjs'),mode,nonce],{cwd:qroot,env:environment,
      timeoutMs:budget,maxBytes:4*1024*1024,koffiRoot:path.join(root,'ownership/node_modules/koffi'),
      jobFactory:koffiRoot=>{appJob=createPrivateJob(koffiRoot);return appJob;}});
  }finally{clearInterval(monitor);}
  if(workflowAbort)result.workflowAbort=workflowAbort;if(abortError)result.workflowAbortError=abortError;
  writeJson(path.join(output,'guest-owned.json'),result);
  requireThat(result.ok && result.code===0 && result.closed && !result.forced && !result.timedOut && result.outputComplete &&
    result.native?.complete===true && result.native.zero===true,'Guest install/update owner did not close normally');
} catch(error) { failed=String(error.stack||error); }
finally {
  // No host code can reach this branch: guest identity was checked before try.
  try {writeJson(path.join(output,'guest-wrapper.json'),{schema:1,mode,nonce,identity,started,finished:Date.now(),
    sourceHead:plan.sourceHead,sourceIdentity:plan.sourceIdentity,artifact:plan.artifact,
    pass:!failed,failed:failed||null,shutdownRequested:true});}
  finally {spawnSync('C:/Windows/System32/shutdown.exe',['/s','/f','/t','0'],{windowsHide:true,timeout:5000});}
}
