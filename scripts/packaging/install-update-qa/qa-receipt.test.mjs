import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {validateGuestPhase,validateSandboxClientClosure} from './qa-receipt.mjs';
test('missing real guest evidence cannot produce install/update acceptance',()=>{
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'cmo-qa-receipt-'));
  try{assert.throws(()=>validateGuestPhase({root,mode:'processing',plan:{},manifestSha256:'a'.repeat(64)}));}
  finally{fs.rmSync(root,{recursive:true});}
});
test('a synthetic pass flag without real ownership proof is refused',()=>{
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'cmo-qa-receipt-'));
  try{
    const out=path.join(root,'output-processing');fs.mkdirSync(out);
    for(const name of ['host-processing-owned.json','host-session-processing.json','host-processing-started.json'])fs.writeFileSync(path.join(root,name),JSON.stringify({pass:true}));
    for(const name of ['guest-owned.json','guest-wrapper.json','update-result.json','session-request.json'])fs.writeFileSync(path.join(out,name),JSON.stringify({pass:true}));
    assert.throws(()=>validateGuestPhase({root,mode:'processing',plan:{},manifestSha256:'a'.repeat(64)}),/owner/);
  }finally{fs.rmSync(root,{recursive:true});}
});
// Captured retry08 processing UI46556 and its authenticated non-UI broker8340.
const packageRoot='C:\\Program Files\\WindowsApps\\MicrosoftWindows.WindowsSandbox_0.8.107.0_x64__cw5n1h2txyewy';
const sid='S-1-5-21-478701085-1013477356-1211919822-1000';
const client={pid:46556,owner:sid,image:packageRoot+'\\WindowsSandboxRemoteSession.exe'};
const broker={pid:8340,parent:46556,image:packageRoot+'\\WindowsSandboxServer.exe',command:'"'+packageRoot+'\\WindowsSandboxServer.exe" ',owner:sid};
const plan={clientApp:{imagePath:client.image}};
const captured=()=>({client:{...client},clientSignaled:true,finalObservation:{clients:{currentSid:sid,processes:[{...broker}]}}});
test('captured actual non-UI broker preserves raw observation after exact owned UI exit',()=>{
 const host=captured(),before=JSON.stringify(host),proof=validateSandboxClientClosure(host,plan);
 assert.equal(proof.retainedUiSignaled,true);assert.equal(proof.observedBrokerRecords[0].pid,8340);assert.equal(JSON.stringify(host),before);
 host.finalObservation.clients.processes=[];assert.equal(validateSandboxClientClosure(host,plan).observedBrokerRecords.length,0);
});
test('active owned/foreign UI or unsignaled retained client cannot produce closure',()=>{
 const unsignaled=captured();unsignaled.clientSignaled=false;assert.throws(()=>validateSandboxClientClosure(unsignaled,plan));
 for(const process of [{...client,parent:0,command:'"'+client.image+'"'},{...broker,pid:123,image:'C:\\Windows\\System32\\WindowsSandboxClient.exe'}]){
  const host=captured();host.finalObservation.clients.processes=[process];assert.throws(()=>validateSandboxClientClosure(host,plan));
 }
});
test('arbitrary or foreign broker path/user/parent/command and multiple brokers are refused',()=>{
 for(const change of [{image:'C:\\Other\\WindowsSandboxServer.exe'},{owner:'foreign-user'},{parent:1},{pid:client.pid},{command:broker.command+'--extra'}]){
  const host=captured();host.finalObservation.clients.processes=[{...broker,...change}];assert.throws(()=>validateSandboxClientClosure(host,plan));
 }
 const host=captured();host.finalObservation.clients.processes.push({...broker,pid:8341});assert.throws(()=>validateSandboxClientClosure(host,plan));
 const foreign=captured();foreign.finalObservation.clients.currentSid='foreign-user';assert.throws(()=>validateSandboxClientClosure(foreign,plan));
});
