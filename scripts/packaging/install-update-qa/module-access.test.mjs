import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {inspectInstalledRuntime,INSTALLED_REQUIRE_EXPRESSION,requestVerifiedInspectorQuit,installedObserverExpression} from './common.mjs';
const scratch=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../../scratch');
function fixture(){
  const root=fs.mkdtempSync(path.join(scratch,'module-context-')),app=path.join(root,'app.asar');
  fs.mkdirSync(app);fs.writeFileSync(path.join(app,'package.json'),'{}');
  for(const [name,source] of [['electron',"module.exports={app:{quits:0,getVersion:()=> '0.6.1',quit(){this.quits++}},BrowserWindow:{getAllWindows:()=>[{isDestroyed:()=>false,webContents:{executeJavaScript:async()=>({service:'ready'})}}]}}"],['electron-updater',"module.exports={autoUpdater:{marker:'anchored-updater',setFeedURL(value){this.feed=value}}}"]]){
    const folder=path.join(app,'node_modules',name);fs.mkdirSync(folder,{recursive:true});fs.writeFileSync(path.join(folder,'package.json'),'{"main":"index.cjs"}');fs.writeFileSync(path.join(folder,'index.cjs'),source);
  }
  let moduleCalls=0;
  const context=vm.createContext({process:{pid:process.pid,execPath:process.execPath,resourcesPath:root,
    env:{LOCALAPPDATA:root,USERNAME:'WDAGUtilityAccount'},versions:{node:process.versions.node,electron:'43.7.9'},
    getBuiltinModule(name){moduleCalls++;return process.getBuiltinModule(name);}}});
  const client={async evaluate(expression){return vm.runInContext(expression,context);}};
  const expected={pid:process.pid,exe:process.execPath,resources:root,local:root,version:'0.6.1'};
  return {root,context,client,expected,moduleCalls:()=>moduleCalls,electron:createRequire(path.join(app,'package.json'))('electron'),
    close(){assert.equal(path.dirname(root),scratch);fs.rmSync(root,{recursive:true,force:true});}};
}
test('real getBuiltinModule/createRequire resolves installed modules and verified cleanup without global require',async()=>{
 const f=fixture();try{
   assert.equal(vm.runInContext('typeof require',f.context),'undefined');
   assert.equal((await inspectInstalledRuntime(f.client,f.expected)).version,'0.6.1');
   assert.equal(await f.client.evaluate(INSTALLED_REQUIRE_EXPRESSION+"('electron-updater').autoUpdater.marker"),'anchored-updater');
   assert.equal(await f.client.evaluate(installedObserverExpression('http://127.0.0.1:18995/test/','synthetic-control-token')),true);
   assert.equal((await f.client.evaluate('globalThis.__cmoInstalledQA.state()')).service,'ready');
   assert.equal((await requestVerifiedInspectorQuit(f.client,f.client)).requested,true);assert.equal(f.electron.app.quits,1);assert.ok(f.moduleCalls()>=3);
 }finally{f.close();}
});
test('wrong OS identity or resources anchor is rejected before any module access/action',async()=>{
 const f=fixture();try{
   for(const change of [{pid:process.pid+1},{resources:path.join(f.root,'wrong-anchor')},{local:'wrong-profile'}])await assert.rejects(inspectInstalledRuntime(f.client,{...f.expected,...change}),/identity differs/);
   f.context.process.env.COMICS_META_QA='1';await assert.rejects(inspectInstalledRuntime(f.client,f.expected),/identity differs/);
   assert.equal(f.moduleCalls(),0);assert.equal(f.electron.app.quits,0);assert.equal(f.context.__cmoInstalledQA,undefined);
 }finally{f.close();}
});
test('wrong app version remains readonly and cannot establish a verified cleanup connection',async()=>{
 const f=fixture();try{
   f.electron.app.getVersion=()=> '0.6.0';let verified=null;
   await assert.rejects(async()=>{await inspectInstalledRuntime(f.client,f.expected);verified=f.client;},/version differs/);
   assert.equal(verified,null);assert.equal((await requestVerifiedInspectorQuit(f.client,verified)).requested,false);assert.equal(f.electron.app.quits,0);assert.equal(f.context.__cmoInstalledQA,undefined);
 }finally{f.close();}
});
