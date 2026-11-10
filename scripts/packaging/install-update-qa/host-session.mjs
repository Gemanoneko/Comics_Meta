// Own one classic Sandbox session; never shutdown the host or kill a compute system.
import fs from 'node:fs';
import path from 'node:path';
import {spawn,spawnSync} from 'node:child_process';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {digest,requireThat,writeJson,normalizeComputeJson,selectGuestLaunch,systemExit,safeGuestIdentity,selectPackagedClient} from './common.mjs';
const input=path.dirname(fileURLToPath(import.meta.url)),plan=JSON.parse(fs.readFileSync(input+'/plan.json'));
const [mode,sessionSha]=process.argv.slice(2),output=path.join(plan.hostRoot,'output-'+mode);
const requestRaw=fs.readFileSync(path.join(output,'session-request.json'));requireThat(digest(requestRaw)===sessionSha,'Session request changed');
const request=JSON.parse(requestRaw),deadline=request.deadlineEpochMs-2000;
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function time(){const x=deadline-Date.now();requireThat(x>0,'Original host deadline exhausted');return x;}
const ps=plan.hostTools['WindowsPowerShell/v1.0/powershell.exe'].path;
function osQuery(script){const r=spawnSync(ps,['-NoLogo','-NoProfile','-NonInteractive','-Command',script],{windowsHide:true,encoding:'utf8',timeout:Math.min(10000,time()),maxBuffer:1024*1024});requireThat(r.status===0,'Read-only host session query failed');return JSON.parse(r.stdout||'null');}
function clients(){return osQuery("$s=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value;$p=@(Get-CimInstance Win32_Process | Where-Object {$_.Name -in @('WindowsSandbox.exe','WindowsSandboxClient.exe','WindowsSandboxRemoteSession.exe','WindowsSandboxServer.exe','wsb.exe')} | ForEach-Object {$o=Invoke-CimMethod -InputObject $_ -MethodName GetOwnerSid;[pscustomobject]@{pid=$_.ProcessId;parent=$_.ParentProcessId;image=$_.ExecutablePath;command=$_.CommandLine;owner=$o.Sid}});@{currentSid=$s;processes=$p}|ConvertTo-Json -Depth 4 -Compress");}
function activations(){return osQuery(`$since=[DateTimeOffset]::FromUnixTimeMilliseconds(${request.startedEpochMs}).LocalDateTime;$rows=@(Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-AppModel-Runtime/Admin';Id=201;StartTime=$since} -ErrorAction SilentlyContinue | ForEach-Object {[xml]$x=$_.ToXml();$d=@{};foreach($v in $x.Event.EventData.Data){$d[$v.Name]=[string]$v.'#text'};if($d.PackageName -eq 'MicrosoftWindows.WindowsSandbox_0.8.107.0_x64__cw5n1h2txyewy'){[pscustomobject]@{eventId=$_.Id;recordId=$_.RecordId;timeMs=([DateTimeOffset]$_.TimeCreated).ToUnixTimeMilliseconds();processId=[int]$d.ProcessID;packageName=$d.PackageName;imageName=$d.ImageName;applicationName=$d.ApplicationName}}});ConvertTo-Json -InputObject $rows -Depth 4 -Compress`);}
function computeSnapshot(){const r=spawnSync(plan.hostTools['hcsdiag.exe'].path,['list','-raw'],{windowsHide:true,encoding:'utf8',timeout:Math.min(10000,time()),maxBuffer:1024*1024});requireThat(r.status===0,'Read-only raw compute inventory failed');return {raw:r.stdout,computes:normalizeComputeJson(r.stdout)};}
function computes(){return computeSnapshot().computes;}
// Project only this nonce's guest-entry event and this bound system's exit events.
// Setup process events may contain transient passwords and are never serialized.
function events(systemId) {
  const id=systemId||'';requireThat(!id||/^[a-f0-9-]{36}$/.test(id),'Invalid event system ID');
  requireThat(/^[a-f0-9]{32}$/.test(request.nonce)&&Number.isSafeInteger(request.startedEpochMs),'Invalid event request');
  return osQuery(`$since=[DateTimeOffset]::FromUnixTimeMilliseconds(${request.startedEpochMs}).LocalDateTime;$rows=@(Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-Hyper-V-Compute-Operational';Id=2500,2008,2009;StartTime=$since} -ErrorAction SilentlyContinue | ForEach-Object {[xml]$x=$_.ToXml();$d=$x.Event.UserData.VmlEventLog;$sid=[string]$d.SystemId;if($_.Id -eq 2500){$p=$null;try{$p=([string]$d.Parameter1)|ConvertFrom-Json}catch{};if($p -and ([string]$p.CommandLine).Contains('${request.nonce}') -and ([string]$p.CommandLine).Contains('guest-entry.mjs')){[pscustomobject]@{eventId=$_.Id;recordId=$_.RecordId;timeMs=([DateTimeOffset]$_.TimeCreated).ToUnixTimeMilliseconds();systemId=$sid;result=[string]$d.Result;processId=[int]$d.Parameter0;commandLine=[string]$p.CommandLine;user=[string]$p.User;existingLogin=$p.UseExistingLogin}}}elseif('${id}' -ne '' -and $sid.ToLowerInvariant() -eq '${id}'){[pscustomobject]@{eventId=$_.Id;recordId=$_.RecordId;timeMs=([DateTimeOffset]$_.TimeCreated).ToUnixTimeMilliseconds();systemId=$sid;result=[string]$d.Result;notification=[string]$d.Parameter0;exitResult=[string]$d.Parameter1}}});ConvertTo-Json -InputObject $rows -Depth 5 -Compress`);
}
const baseline=computes(),before=clients();
requireThat(baseline.every(x=>x.state==='SavedAsTemplate')&&before.processes.length===0,'Another active Sandbox/compute session is not ours');
const result={schema:1,mode,nonce:request.nonce,sourceHead:plan.sourceHead,artifact:plan.artifact,baseline,started:Date.now(),pass:false};
let child,clientHandle,computeId,clientPid,observationSequence=0;
function observe(label){const snapshot={observedEpochMs:Date.now(),label,hcs:computeSnapshot(),clients:clients(),events:events(computeId),activations:activations()};writeJson(path.join(plan.hostRoot,`host-observation-${mode}-${++observationSequence}.json`),snapshot);return snapshot;}
const require=createRequire(import.meta.url),koffi=require(input+'/ownership/node_modules/koffi'),kernel=koffi.load('kernel32.dll');
const open=kernel.func('void* __stdcall OpenProcess(uint32_t,bool,uint32_t)'),wait=kernel.func('uint32_t __stdcall WaitForSingleObject(void*,uint32_t)'),close=kernel.func('bool __stdcall CloseHandle(void*)');
const image=kernel.func('bool __stdcall QueryFullProcessImageNameW(void*,uint32_t,void*,void*)');
try {
  child=spawn(plan.hostTools['WindowsSandbox.exe'].path,[request.config],{windowsHide:true,stdio:['ignore','pipe','pipe']});
  let out='',err='';child.stdout.on('data',b=>{out+=b;requireThat(out.length<65536,'Sandbox output exceeded bound');});child.stderr.on('data',b=>{err+=b;requireThat(err.length<65536,'Sandbox diagnostics exceeded bound');});
  let launchError;child.once('error',e=>{launchError=String(e);});
  const startupEnd=Math.min(Date.now()+90000,deadline-60000);
  let started;
  while(Date.now()<startupEnd){if(launchError)throw Error(launchError);const file=path.join(output,'guest-started.json');if(fs.existsSync(file)){started=JSON.parse(fs.readFileSync(file));break;}if(child.exitCode!==null&&child.exitCode!==0)throw Error('Sandbox launcher failed: '+child.exitCode);await sleep(250);}
  const active=observe('before-binding');
  requireThat(started?.nonce===request.nonce&&started.mode===mode&&started.sourceHead===plan.sourceHead&&started.manifestSha256===request.manifestSha256&&safeGuestIdentity(started.identity,plan.hostName),'Guest startup identity not established');
  result.kernelLaunch=selectGuestLaunch(active.events,{...request,sessionSha256:sessionSha,guestPid:started.identity.pid});computeId=result.kernelLaunch.systemId.toLowerCase();result.computeId=computeId;result.guestStarted=started;
  requireThat(!baseline.some(x=>x.id===computeId)&&active.hcs.computes.some(x=>x.id===computeId&&x.systemType==='VirtualMachine'),'OS-created guest system not present/new');
  const {client,activation}=selectPackagedClient(active.activations,active.clients.processes,{...plan.clientApp,currentSid:before.currentSid,startedEpochMs:request.startedEpochMs});result.clientActivation=activation;
  clientPid=client.pid;clientHandle=open(0x00101000,false,clientPid);requireThat(clientHandle,'Cannot retain exact Sandbox client');
  const buf=Buffer.alloc(65536),len=Buffer.alloc(4);len.writeUInt32LE(32768);
  requireThat(image(clientHandle,0,buf,len)&&path.resolve(buf.subarray(0,len.readUInt32LE()*2).toString('utf16le')).toLowerCase()===path.resolve(client.image).toLowerCase(),'Sandbox client image changed');
  if(started.identity.virtualMachineId)requireThat(started.identity.virtualMachineId.replace(/[{}]/g,'').toLowerCase()===computeId,'Guest/host compute ID mismatch');
  requireThat(wait(clientHandle,0)===258,'Bound Sandbox client already exited');result.client=client;
  writeJson(path.join(output,'go.json'),{schema:1,nonce:request.nonce,mode,computeId,clientPid,manifestSha256:request.manifestSha256});
  let nextPresenceCheck=0;
  while(Date.now()<deadline-5000){const file=path.join(output,'guest-wrapper.json');if(fs.existsSync(file)){result.guest=JSON.parse(fs.readFileSync(file));break;}
    if(Date.now()>=nextPresenceCheck){const current=computes();nextPresenceCheck=Date.now()+1000;if(!current.some(x=>x.id===computeId)){observe('guest-disappeared-without-wrapper');throw Error('Bound Sandbox disappeared before guest completion wrapper; failed cleanup, no acceptance');}}
    await sleep(250);}
  requireThat(result.guest?.nonce===request.nonce&&result.guest.shutdownRequested===true,'No bound guest completion/shutdown request');
  let vanished=false;
  while(Date.now()<deadline-2000){const current=computes(),exited=systemExit(events(computeId),computeId,request.startedEpochMs);if(exited&&!current.some(x=>x.id===computeId)&&JSON.stringify(current)===JSON.stringify(baseline)){vanished=true;result.after=current;result.kernelExit=exited;break;}await sleep(500);}
  requireThat(vanished,'Exact owned Sandbox compute session did not disappear');
  // The guest is already gone. WM_CLOSE may only tidy this exact retained client.
  if(wait(clientHandle,0)===258){
    const user=koffi.load('user32.dll'),enumType=koffi.proto('bool __stdcall CmoSandboxWindow(void*, intptr_t)');
    const windowPid=user.func('uint32_t __stdcall GetWindowThreadProcessId(void*,void*)');
    const post=user.func('bool __stdcall PostMessageW(void*,uint32_t,uintptr_t,intptr_t)');
    const enumerate=user.func('bool __stdcall EnumWindows(void*,intptr_t)');
    const callback=koffi.register(hwnd=>{const pid=Buffer.alloc(4);windowPid(hwnd,pid);if(pid.readUInt32LE()===clientPid)post(hwnd,0x0010,0,0);return true;},koffi.pointer(enumType));
    try{enumerate(callback,0);}finally{koffi.unregister(callback);}
  }
  while(Date.now()<deadline&&wait(clientHandle,0)===258)await sleep(200);
  requireThat(wait(clientHandle,0)===0,'Owned Sandbox client did not exit; window assistance required');
  result.clientSignaled=true;
  const final=computes();requireThat(JSON.stringify(final)===JSON.stringify(baseline),'Host compute inventory not restored');
  result.finalObservation=observe('successful-closure');
  requireThat(result.guest.pass===true,'Guest install/update tests failed');result.pass=true;
} catch(error){result.error=String(error.stack||error);
  // No kill/retry: allow the independent guest watchdog to finish and retain facts.
  try {
    observe('failure-before-closure-wait');
    while(Date.now()<deadline-2000){
      const snapshot=computeSnapshot(),c=clients();
      if(JSON.stringify(snapshot.computes)===JSON.stringify(baseline)&&c.processes.length===0){result.failureClosure=observe('failed-attempt-closed');if(clientHandle)result.failureClientSignaled=wait(clientHandle,0)===0;break;}
      await sleep(500);
    }
  }catch(closureError){result.closureError=String(closureError);}
}
finally {
  if(clientHandle)close(clientHandle);result.finished=Date.now();
  fs.writeFileSync(path.join(plan.hostRoot,'host-session-'+mode+'.json'),JSON.stringify(result,null,2)+'\n',{flag:'wx'});
  console.log(JSON.stringify({mode,pass:result.pass,computeId,error:result.error||null}));
}
process.exitCode=result.pass?0:1;
