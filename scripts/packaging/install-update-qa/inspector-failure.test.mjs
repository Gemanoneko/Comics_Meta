import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {EventEmitter} from 'node:events';
import path from 'node:path';
import {Inspector,failedGuestWorkflow,digest,requestVerifiedInspectorQuit,requestDashboardTransition,dashboardFrameReady} from './common.mjs';
class Socket extends EventTarget {
  send(text){this.last=JSON.parse(text);}
  close(){this.dispatchEvent(new Event('close'));}
  answer(result){this.dispatchEvent(new MessageEvent('message',{data:JSON.stringify({id:this.last.id,result})}));}
}
test('inspector retains exact request hash and response identity without expression secrets',async()=>{
 const socket=new Socket(),client=new Inspector(socket),expression="'synthetic-secret-value'";
 const durable=[];client.onTrace=record=>durable.push(record);const originalSend=socket.send;socket.send=function(text){assert.equal(durable.at(-1).kind,'request');return originalSend.call(this,text);};
 const promise=client.evaluate(expression);socket.answer({result:{value:7}});assert.equal(await promise,7);
 assert.equal(client.history[0].expressionSha256,digest(Buffer.from(expression)));
 assert.equal(JSON.stringify(client.history).includes('synthetic-secret-value'),false);assert.equal(client.pending.size,0);socket.close();
});
test('inspector timeout identifies expression and close rejects pending calls immediately',async()=>{
 const socket=new Socket(),client=new Inspector(socket);
 await assert.rejects(client.evaluate('1+2',true,5),/Runtime.evaluate expression [a-f0-9]{64}/);
 const pending=client.call('Runtime.evaluate',{expression:'3+4'});socket.close();await assert.rejects(pending,/socket closed during Runtime.evaluate/);assert.equal(client.pending.size,0);
});
test('inspector records unexpected paused/resumed diagnostics without raw exception values',()=>{
 const socket=new Socket(),client=new Inspector(socket);
 socket.dispatchEvent(new MessageEvent('message',{data:JSON.stringify({method:'Debugger.paused',params:{reason:'exception',data:{secret:'do-not-copy'},callFrames:[{url:'file:///installed/main.cjs',location:{lineNumber:3}}]}})}));
 assert.equal(client.debuggerPaused,true);assert.equal(client.history.at(-1).reason,'exception');assert.equal(JSON.stringify(client.history).includes('do-not-copy'),false);
 socket.dispatchEvent(new MessageEvent('message',{data:JSON.stringify({method:'Debugger.resumed'})}));assert.equal(client.debuggerPaused,false);socket.close();
});
test('private Job abort signal accepts only this actual failed phase, never success/wrong identity/incomplete result',()=>{
 const request={mode:'processing',nonce:'a'.repeat(32),sourceHead:'b'.repeat(40),artifactSha256:'c'.repeat(64)};
 const value={schema:1,mode:request.mode,nonce:request.nonce,sourceHead:request.sourceHead,artifact:{sha256:request.artifactSha256},pass:false,error:'Inspector timed out',started:10,finished:20};
 assert.equal(failedGuestWorkflow(value,request),true);
 for(const change of [{pass:true},{nonce:'wrong'},{mode:'paused'},{sourceHead:'wrong'},{artifact:{sha256:'wrong'}},{error:''},{finished:undefined},{finished:9}])assert.equal(failedGuestWorkflow({...value,...change},request),false);
});
test('observer distinguishes setup URL during navigation from completed load and captures renderer failure',()=>{
 const app=new EventEmitter();app.getVersion=()=> '0.6.0';
 const contents=new EventEmitter();contents.id=1;let loading=true;
 contents.getURL=()=> 'file:///installed/desktop/setup.html';contents.isLoadingMainFrame=()=>loading;
 const window=new EventEmitter();window.webContents=contents;window.isDestroyed=()=>false;
 const electron={app,BrowserWindow:{getAllWindows:()=>[window]},Tray:class {setContextMenu(){}}};
 const updater={setFeedURL(){}};
 const context={URL,process:{pid:1,resourcesPath:'C:/installed/resources',env:{USERNAME:'WDAGUtilityAccount',CMO_SANDBOX_PLAN:'unused',CMO_QA_OBSERVER:'unused',LOCALAPPDATA:'C:/Users/WDAGUtilityAccount/AppData/Local'}},
 require:name=>({'node:fs':{readFileSync:()=>JSON.stringify({feedURL:'http://127.0.0.1/',feedToken:'synthetic'}),writeFileSync(){}},'node:path':path,'node:child_process':{spawn(){}},electron,'electron-updater':{autoUpdater:updater}}[name])};
 vm.runInNewContext(fs.readFileSync(new URL('./observer.cjs',import.meta.url),'utf8'),context);
 app.emit('browser-window-created',{},window);const observer=context.__cmoInstalledQA;
 assert.equal(observer.renderer().url.endsWith('/setup.html'),true);assert.equal(observer.renderer().finished,false);assert.equal(observer.renderer().loading,true);
 loading=false;contents.emit('did-finish-load');assert.equal(observer.renderer().finished,true);assert.equal(observer.renderer().loading,false);
 contents.emit('render-process-gone',{}, {reason:'crashed',exitCode:9});assert.equal(observer.renderer().failure.reason,'crashed');
 assert.equal(observer.events.filter(x=>x.kind==='renderer-loaded').length,1);
});
test('graceful failure cleanup never resumes or quits rejected/unverified or replacement inspector target',async()=>{
 let mutations=0;const rejected={debuggerPaused:true,call(){mutations++;},evaluate(){mutations++;}};
 assert.equal((await requestVerifiedInspectorQuit(rejected,null)).requested,false);
 const priorVerified={};assert.equal((await requestVerifiedInspectorQuit(rejected,priorVerified)).requested,false);
 assert.equal(mutations,0);
});
test('graceful failure cleanup mutates only the exact verified connection with fixed bounds',async()=>{
 const calls=[],verified={debuggerPaused:true,async call(...args){calls.push(args);},async evaluate(...args){calls.push(args);}};
 assert.equal((await requestVerifiedInspectorQuit(verified,verified)).requested,true);
 assert.deepEqual(calls[0],['Debugger.resume',{},1000]);assert.equal(calls[1][1],false);assert.equal(calls[1][2],3000);assert.match(calls[1][0],/app\.quit/);
});
test('dashboard navigation does not await pending old context, submits once and requires completed new frame',async()=>{
 let submitted=0;const context={__cmoInstalledQA:{action:name=>{assert.equal(name,'setupOpenDashboard');submitted++;return new Promise(()=>{});}}};
 const client={evaluate:async(expression,awaitPromise)=>{assert.equal(awaitPromise,false);return vm.runInNewContext(expression,context);}};
 assert.equal(await requestDashboardTransition(client),'actual setupOpenDashboard requested once');assert.equal(submitted,1);
 assert.equal(context.__cmoInstalledQA.dashboardTransition.outcome,'pending');
 await assert.rejects(requestDashboardTransition(client),/already requested/);assert.equal(submitted,1);
 const frame={present:true,finished:true,loading:false,url:'file:///installed/setup.html'};assert.equal(dashboardFrameReady(frame),false);
 assert.equal(dashboardFrameReady({...frame,url:'http://127.0.0.1:8765/',loading:true,finished:false}),false);
 assert.equal(dashboardFrameReady({...frame,url:'http://127.0.0.1:8765/'}),true);
 assert.equal(dashboardFrameReady({...frame,url:'http://127.0.0.1:8765/',failure:{reason:'crashed'}}),false);
});
