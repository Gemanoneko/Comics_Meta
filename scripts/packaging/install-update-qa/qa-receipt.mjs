// Translate real, separately bound Sandbox observations. Never substitutes for them.
import fs from 'node:fs';
import path from 'node:path';
import {digest,requireThat,verifyInventory,selectGuestLaunch,systemExit,selectPackagedClient,assertRememberedGeometryRestored} from './common.mjs';

function json(file){const raw=fs.readFileSync(file);return {path:file,sha256:digest(raw),value:JSON.parse(raw)};}
function normal(result){return result?.ok===true&&result.code===0&&result.closed===true&&result.forced===false&&result.timedOut===false&&result.outputComplete===true&&result.native?.complete===true&&result.native.zero===true&&result.native.active===0&&result.native.unsignaled===0;}
function same(a,b){return JSON.stringify(a)===JSON.stringify(b);}
export function validateSandboxClientClosure(host,plan) {
  const final=host.finalObservation?.clients,client=host.client;
  requireThat(host.clientSignaled===true&&client?.pid>0&&final&&Array.isArray(final.processes)&&final.currentSid===client.owner,'Retained owned Sandbox UI closure/current-user proof missing');
  const ui=path.resolve(plan.clientApp.imagePath).toLowerCase(),broker=path.resolve(path.dirname(plan.clientApp.imagePath),'WindowsSandboxServer.exe').toLowerCase();
  requireThat(path.resolve(client.image).toLowerCase()===ui&&!final.processes.some(process=>process.pid===client.pid),'Retained owned Sandbox UI remains in actual inventory');
  requireThat(final.processes.length<=1&&final.processes.every(process=>Number.isSafeInteger(process.pid)&&process.pid>0&&process.pid!==client.pid&&
    process.parent===client.pid&&process.owner===final.currentSid&&typeof process.image==='string'&&path.resolve(process.image).toLowerCase()===broker&&
    typeof process.command==='string'&&process.command.trim().toLowerCase()==='"'+path.resolve(process.image).toLowerCase()+'"'),
    'Actual inventory contains active UI, foreign process or unauthenticated Sandbox broker');
  return {retainedUiPid:client.pid,retainedUiSignaled:host.clientSignaled,observedBrokerRecords:final.processes};
}
export function validateGuestPhase({root,mode,plan,manifestSha256}) {
  requireThat(['processing','paused'].includes(mode),'Unknown actual update phase');
  const output=path.join(root,'output-'+mode);
  const host=json(path.join(root,'host-'+mode+'-owned.json')),session=json(path.join(root,'host-session-'+mode+'.json'));
  const guest=json(path.join(output,'guest-owned.json')),wrapper=json(path.join(output,'guest-wrapper.json')),run=json(path.join(output,'update-result.json'));
  const request=json(path.join(output,'session-request.json')),start=json(path.join(root,'host-'+mode+'-started.json'));
  requireThat(normal(host.value)&&normal(guest.value),'Host/guest owner not normal/complete/zero');
  requireThat(start.value.sessionSha256===request.sha256&&start.value.manifestSha256===manifestSha256&&request.value.manifestSha256===manifestSha256,'Actual invocation manifest/request mismatch');
  const h=session.value,w=wrapper.value,r=run.value,nonce=plan.runs[mode].nonce;
  requireThat(h.pass===true&&w.pass===true&&r.pass===true&&[h,w,r,request.value].every(x=>x.mode===mode&&x.nonce===nonce),'Guest phase outcome/nonce mismatch');
  requireThat([h,w,r].every(x=>x.sourceHead===plan.sourceHead&&x.artifact.sha256===plan.artifact.sha256)&&w.sourceIdentity===plan.sourceIdentity&&r.sourceIdentity===plan.sourceIdentity,'Guest tested source/artifact identity mismatch');
  requireThat(w.shutdownRequested===true&&w.identity.user.toLowerCase()==='wdagutilityaccount'&&w.identity.tokenName?.split('\\').at(-1).toLowerCase()==='wdagutilityaccount'&&/^S-1-5-21-(?:\d+-){3}\d+$/.test(w.identity.tokenSid||'')&&w.identity.computer.toLowerCase()!==plan.hostName.toLowerCase(),'Actual isolated guest shutdown not established');
  requireThat(/^[a-f0-9-]{36}$/.test(h.computeId)&&!h.baseline.some(x=>x.id===h.computeId)&&same(h.baseline,h.after),'Owned VM identity/closure/baseline missing');
  requireThat(h.client?.pid>0&&h.guestStarted?.nonce===nonce&&h.guestStarted.manifestSha256===manifestSha256&&same(h.guest,w),'Bound client/guest completion missing');
  requireThat(selectGuestLaunch([h.kernelLaunch],{...request.value,sessionSha256:request.sha256,guestPid:h.guestStarted.identity.pid}).systemId.toLowerCase()===h.computeId&&
    systemExit([h.kernelExit],h.computeId,request.value.startedEpochMs)&&h.clientSignaled===true&&
    same(h.finalObservation?.hcs?.computes,h.baseline),'Actual OS-bound launch/system-exit/client closure missing');
  const hostClientClosure=validateSandboxClientClosure(h,plan);
  requireThat(selectPackagedClient([h.clientActivation],[h.client],{...plan.clientApp,currentSid:h.finalObservation.clients.currentSid,startedEpochMs:request.value.startedEpochMs}).client.pid===h.client.pid,'Actual packaged UI activation missing');
  requireThat(r.priorVersion===plan.priorVersion&&r.nextVersion===plan.version&&r.priorInstallation?.exit?.code===0&&r.priorInstallation.exit.signal===null&&r.priorInstallation.versionFile===plan.priorVersion&&r.priorRegistration?.DisplayVersion===plan.priorVersion&&r.nextRegistration?.DisplayVersion===plan.version,'Real prior/next installation registration not established');
  requireThat(r.priorExit?.code===0&&r.priorExit.signal===null&&r.relaunch?.version===plan.version&&r.relaunch.pid>0&&!r.relaunch.qa&&r.relaunch.user.toLowerCase()==='wdagutilityaccount','Real ordinary installed old-to-new relaunch not established');
  const before=r.oldObserver?.events?.find(x=>x.kind==='before-installer-helper');
  const accepted=r.oldObserver?.events?.find(x=>x.kind==='installer-receipt');
  requireThat(before?.engines?.length>0&&before.engines.every(x=>x.exit?.code===0&&x.exit.signal===null)&&accepted?.receipt?.started===true&&accepted.receipt.accepted===true&&accepted.receipt.installer_pid>0&&before.time<=accepted.time,'Real old engine closure before actual installer missing');
  requireThat(r.realProcessing?.taggedFixtures>0&&r.realProcessing.pendingFixtures>0&&r.realProcessing.processes.some(x=>String(x.CommandLine).includes('worker')),'Initial real worker/queue activity missing');
  const paused=mode==='paused';
  requireThat(r.priorShell?.control?.user_requested===paused&&r.nextShell?.control?.user_requested===paused&&r.nextShell.loadedShellVersion===plan.version&&r.after.userPaused===paused,'Actual user-pause choice/version not preserved');
  for(const field of ['configSha256','legacySha256','credentialSha256','credentialFileSha256','manual','manualArchiveSha256','manualLedger','recoverySha256'])requireThat(r.before[field]!==undefined&&same(r.before[field],r.after[field]),'State preservation failed: '+field);
  requireThat(Object.values(r.before.credentialPresence).length===4&&Object.values(r.before.credentialPresence).every(x=>x===true)&&r.before.credentialsMatchExpected===true&&r.after.credentialsMatchExpected===true&&r.before.manualLedger.length>0&&r.before.history.length>0,'Credential/manual/history fixture absent');
  const after=new Map(r.after.history.map(row=>[row[0],JSON.stringify(row)]));requireThat(r.before.history.every(row=>after.get(row[0])===JSON.stringify(row)),'Old history not preserved');
  requireThat(same(r.priorBounds,r.nextBounds)&&Array.isArray(r.remaining)&&r.remaining.length===0,'Actual geometry/Quit/remaining-process check missing');
  assertRememberedGeometryRestored(r.priorGeometry,r.nextGeometry);
  requireThat(r.feed.some(x=>x.name===plan.artifact.name&&x.authorized)&&r.feed.some(x=>x.name==='latest.yml'&&x.authorized),'No real authenticated update download/feed observed');
  requireThat(r.postUpdateActivity?.history?.length>0,'Actual post-update core fixture action missing');
  if(paused)requireThat(r.nextShell.control.phase==='paused'&&r.resumeRequested==='actual rendered Resume clicked','Actual paused/resume workflow missing');
  return {mode,priorVersion:plan.priorVersion,nextVersion:plan.version,relaunchVersion:r.relaunch.version,
    actualOldToNew:true,initialUserPaused:paused,computeId:h.computeId,clientPid:h.client.pid,
    nativeResult:guest.value.native,hostNativeResult:host.value.native,hostClientClosure,
    provenance:[host,session,guest,wrapper,run,request,start].map(({path,sha256})=>({path,sha256}))};
}

export function strictQAReceipt({root,input,manifestSha256,artifacts,entryReceipt,qaReport,codeReview}) {
  const manifest=json(path.join(input,'input-manifest.json'));requireThat(manifest.sha256===manifestSha256,'Wrong reviewed installed-QA input manifest');
  verifyInventory(input,manifest.value.files,{allowManifest:true});const plan=JSON.parse(fs.readFileSync(path.join(input,'plan.json')));
  const phases=['processing','paused'].map(mode=>validateGuestPhase({root,mode,plan,manifestSha256}));
  const entry=json(entryReceipt.path);requireThat(entry.sha256===entryReceipt.sha256&&normal(entry.value),'Formal entry raw owner failed');
  requireThat(typeof entry.value.out==='string'&&entry.value.out.includes('Entry-check receipt v2: comic-metadata v'+plan.version+' @ '+plan.sourceHead+' (dirty: N)')&&/\bcheck pass\b/.test(entry.value.out),'Actual successful full entry receipt absent');
  for(const [item,verdict] of [[qaReport,'**Verdict:** GO'],[codeReview,'**Verdict:** RELEASE CLEAR']]){
    const raw=fs.readFileSync(item.path);requireThat(digest(raw)===item.sha256&&path.basename(item.path).includes('v'+plan.version)&&raw.toString('utf8').includes(verdict)&&raw.toString('utf8').includes(plan.sourceHead),'Named exact final QA/review report absent or wrong source');
  }
  requireThat(Array.isArray(artifacts)&&artifacts.length===3&&artifacts.some(x=>x.name===plan.artifact.name&&x.sha256===plan.artifact.sha256&&x.size===plan.artifact.size),'QA artifact list differs');
  return {schema:1,verdict:'GO',version:plan.version,sourceHead:plan.sourceHead,sourceIdentity:plan.sourceIdentity,
    packagedInstall:true,packagedClose:true,statePreserved:true,noOwnedEngineBeforeReplacement:true,
    updateFlow:{actualOldToNew:true,priorVersion:plan.priorVersion,nextVersion:plan.version,relaunchVersion:plan.version},
    artifacts,installUpdatePhases:phases,provenance:{inputManifest:{path:manifest.path,sha256:manifest.sha256},entryReceipt,qaReport,codeReview,
      naturalNextExit:'The pinned guest-update harness requires WaitForSingleObject=signaled and GetExitCodeProcess=0 before pass; guest owner and exact process absence also required.'}};
}
