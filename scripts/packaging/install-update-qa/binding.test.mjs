import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {selectGuestLaunch,systemExit,normalizeComputeJson,selectPackagedClient} from './common.mjs';
const evidence=JSON.parse(fs.readFileSync(new URL('../../../Docs/ComicsMetaOrganizer_InstallUpdateBindingEvidence_v0.6.1_2026-11-10.json',import.meta.url)));
const captured=evidence.kernelClosure.computeEvents.find(x=>x.Id===2500);
const parameters=JSON.parse(captured.Message.match(/parameters '(.*)', result/)[1]);
const launch={eventId:2500,timeMs:Date.parse(captured.TimeCreated),systemId:evidence.kernelClosure.actualComputeId,
  commandLine:parameters.CommandLine,user:parameters.User,existingLogin:parameters.UseExistingLogin,
  result:captured.Message.match(/result (0x[0-9A-Fa-f]+)/)[1],processId:Number(captured.Message.match(/process ID (\d+)/)[1])};
const request={mode:'processing',nonce:evidence.kernelClosure.nonce,manifestSha256:evidence.kernelClosure.originalManifestSha256,
 sessionSha256:'0d7fe17276b68b558533cd057f134bd8807c89f7befe673956e934df314c7731',startedEpochMs:launch.timeMs-1000,guestPid:7508};
test('captured successful exact OS guest launch binds and duplicate notification deduplicates',()=>{
 assert.equal(selectGuestLaunch([launch,launch],request).systemId,evidence.kernelClosure.actualComputeId);
});
for(const field of ['nonce','manifestSha256','sessionSha256','guestPid'])test('launch refuses wrong '+field,()=>{
 assert.throws(()=>selectGuestLaunch([launch],{...request,[field]:field==='guestPid'?7509:'f'.repeat(field==='nonce'?32:64)}));
});
test('launch refuses stale/unsuccessful/non-WDAG or multiple systems',()=>{
 for(const change of [{timeMs:request.startedEpochMs-1},{result:'0x00000001'},{user:'Administrator'},{existingLogin:false}])assert.throws(()=>selectGuestLaunch([{...launch,...change}],request));
 assert.throws(()=>selectGuestLaunch([launch,{...launch,systemId:'11111111-1111-1111-1111-111111111111'}],request));
});
const exits=evidence.kernelSystemExited.events.map(x=>({eventId:x.EventId,timeMs:Date.parse(x.TimeCreated),systemId:x.SystemId,
 result:x.QueryResult,notification:x.Notification,exitResult:x.SystemExitResult}));
test('captured system-exited notification1 result0 proves exact system exit',()=>assert.ok(systemExit(exits,launch.systemId,request.startedEpochMs)));
test('exit refuses wrong system, stale, nonzero exit or unsuccessful query',()=>{
 assert.equal(systemExit(exits,'11111111-1111-1111-1111-111111111111',request.startedEpochMs),undefined);
 for(const change of [{timeMs:0},{notification:'2'},{exitResult:'0x00000001'},{eventId:2008,result:'0x00000001'}])assert.equal(systemExit([{...exits[0],...change}],launch.systemId,request.startedEpochMs),undefined);
});
test('raw HCS keeps stable template identity, normalizes GUID case and refuses malformed JSON',()=>{
 const baseline=[{Id:'A90A3CA5-CF2C-4AA3-8DA2-E81E62EB3A71',RuntimeId:'A90A3CA5-CF2C-4AA3-8DA2-E81E62EB3A71',SystemType:'VirtualMachine',RuntimeOsType:'Windows',Owner:'CmService',State:'SavedAsTemplate'}];
 assert.equal(normalizeComputeJson(JSON.stringify(baseline))[0].state,'SavedAsTemplate');
 assert.equal(normalizeComputeJson(JSON.stringify(baseline))[0].id,'a90a3ca5-cf2c-4aa3-8da2-e81e62eb3a71');
 assert.throws(()=>normalizeComputeJson('{}'));assert.throws(()=>normalizeComputeJson('[{"Id":"bad"}]'));
});
const packaged=JSON.parse(fs.readFileSync(new URL('../../../Docs/ComicsMetaOrganizer_InstallUpdateClientBindingEvidence_v0.6.1_2026-11-10.json',import.meta.url)));
const activation=packaged.activation.events[0];
const client={pid:activation.processId,owner:'test-current-user',image:packaged.pinnedUI.path};
const clientRequest={packageName:activation.packageName,applicationName:activation.applicationName,imageName:activation.imageName,
 imagePath:packaged.pinnedUI.path,currentSid:client.owner,startedEpochMs:activation.timeMs-1000};
test('captured packaged UI activation selects a matching current-user pinned process fixture',()=>assert.equal(selectPackagedClient([activation],[client],clientRequest).client.pid,63276));
test('packaged binding refuses wrong PID, package, app, image, stale activation and wrong user/path',()=>{
 for(const change of [{processId:63277},{packageName:'wrong'},{applicationName:'wrong'},{imageName:'wrong'},{timeMs:0}])assert.throws(()=>selectPackagedClient([{...activation,...change}],[client],clientRequest));
 for(const change of [{owner:'other-user'},{image:'C:/wrong.exe'},{pid:63277}])assert.throws(()=>selectPackagedClient([activation],[{...client,...change}],clientRequest));
 assert.throws(()=>selectPackagedClient([activation],[client,{...client,pid:63277}],clientRequest));
});
