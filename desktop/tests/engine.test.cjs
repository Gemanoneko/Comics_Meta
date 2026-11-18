'use strict';
const test=require('node:test');const assert=require('node:assert/strict');const {EventEmitter}=require('node:events');const {Engine}=require('../engine.cjs');
function fixture(exitCode=null){const engine=new Engine({resources:'fixture',state:'fixture',locks:'fixture',port:18980,log:'fixture'});const child=new EventEmitter();child.exitCode=exitCode;child.commands=[];child.kill=()=>{throw Error('Root-only kill must not be used');};child.stdin={writable:true,write:command=>{child.commands.push(command);queueMicrotask(()=>{child.exitCode=125;child.emit('exit',125);});}};engine.child=child;return {engine,child};}
test('force sends the private broker command and waits for acknowledged whole-job closure',async()=>{const {engine,child}=fixture();await engine.forceStop();assert.deepEqual(child.commands,['force\n']);assert.equal(child.exitCode,125);});
test('unexpected dead broker exit cannot claim engine closure without its engine identity',async()=>{const {engine}=fixture(1);engine.closureWaitMs=200;await assert.rejects(engine.forceStop(),/closure/);});
// TrayQA v0.6.4 finding 2: a broker ended from outside (exit code 1) left Retry and tray Quit dead, because only the
// broker's own exit code could confirm closure. Its Job is kill-on-close, so Windows ends the tree with it; the shell
// now confirms that itself: the engine port is free and no process holding one of this engine's library claims lives.
const fs=require('node:fs'),path=require('node:path'),net=require('node:net'),{spawnSync}=require('node:child_process');
const OWNER='a'.repeat(64),OTHER='b'.repeat(64);
function deadPid(){const result=spawnSync(process.execPath,['-e',''],{windowsHide:true});assert.equal(result.status,0);return result.pid;}
function freePort(){return new Promise(resolve=>{const server=net.createServer();server.listen(0,'127.0.0.1',()=>{const {port}=server.address();server.close(()=>resolve(port));});});}
async function deadBroker(t,claims,exitCode=1){
  const scratch=process.env.COMICS_META_TEST_SCRATCH;assert.ok(scratch);
  const locks=fs.mkdtempSync(path.join(scratch,'engine-closure-'));t.after(()=>fs.rmSync(locks,{recursive:true,force:true}));
  fs.mkdirSync(path.join(locks,'claims'));
  for(const [owner,pid] of claims)for(const suffix of ['.lock','.json'])fs.writeFileSync(path.join(locks,'claims','engine-'+owner+'-'+pid+'-0123456789ab'+suffix),'');
  const {engine,child}=fixture(exitCode);Object.assign(engine,{locks,port:await freePort(),owner:OWNER,closureWaitMs:400});
  return {engine,child};
}
// Code review v0.6.6 T1: exit code 1 also meant the broker's own "descendants remain" failure, which the shell's
// weaker check then overruled. The broker now reports that failure as 124, and nothing the shell sees confirms it.
test('a broker that reported its own closure failure stays unconfirmed even with its port free and no claim holder',async t=>{
  const {engine,child}=await deadBroker(t,[[OWNER,deadPid()]],124);
  await assert.rejects(engine.forceStop(),/closure/);
  assert.deepEqual(child.commands,[]);
  child.exitCode=1;await engine.forceStop();  // Positive control: the same tree after an outside end is confirmed.
});
test('tray Quit after the broker reported its own closure failure fails closed',async t=>{
  const {GracefulStop}=require('../graceful-stop.cjs');
  const {engine}=await deadBroker(t,[],124);
  await assert.rejects(new GracefulStop(engine).run('quit'),/closure/);
});
test('a broker that ended on its own is closed once its port is free and its claim holders have ended',async t=>{
  const {engine,child}=await deadBroker(t,[[OWNER,deadPid()],[OTHER,process.pid]]);  // Another engine's live claim is not this one's.
  await engine.forceStop();
  assert.deepEqual(child.commands,[]);  // Nothing is asked of a broker that has already ended.
});
test('a dead broker stays unconfirmed while a process holding one of its claims lives',async t=>{
  const {engine}=await deadBroker(t,[[OWNER,deadPid()],[OWNER,process.pid]]);
  await assert.rejects(engine.forceStop(),/closure/);
});
test('a dead broker stays unconfirmed while its engine port is still bound, and closes once it is free',async t=>{
  const {engine}=await deadBroker(t,[]);
  const server=net.createServer();await new Promise(resolve=>server.listen(engine.port,'127.0.0.1',resolve));
  try{await assert.rejects(engine.forceStop(),/closure/);}finally{await new Promise(resolve=>server.close(resolve));}
  await engine.forceStop();
});
test('a dead broker with an unreadable claim folder stays unconfirmed',async t=>{
  const {engine}=await deadBroker(t,[]);fs.rmSync(path.join(engine.locks,'claims'),{recursive:true});fs.writeFileSync(path.join(engine.locks,'claims'),'');
  await assert.rejects(engine.forceStop(),/closure/);
});
test('tray Quit after the broker ended on its own exits instead of failing closed',async t=>{
  const {GracefulStop}=require('../graceful-stop.cjs');
  const {engine}=await deadBroker(t,[[OWNER,deadPid()]]);
  assert.equal(engine.ready,false);
  assert.equal(await new GracefulStop(engine).run('quit'),true);
});
test('missing owner stream refuses force rather than killing only the broker',async()=>{const {engine,child}=fixture();child.stdin.writable=false;await assert.rejects(engine.forceStop(),/control unavailable/);assert.equal(child.exitCode,null);});
test('normal stop rejects a nonzero broker return',async()=>{const {engine,child}=fixture();engine.call=async()=>{queueMicrotask(()=>{child.exitCode=1;child.emit('exit',1);});return {ok:true};};await assert.rejects(engine.stop(),/not confirmed/);});
test('concurrent force requests share one broker closure',async()=>{const {engine,child}=fixture();await Promise.all([engine.forceStop(),engine.forceStop()]);assert.deepEqual(child.commands,['force\n']);});
test('signal exit never claims confirmed broker closure',async()=>{const {engine,child}=fixture();child.signalCode='SIGTERM';await assert.rejects(engine.forceStop(),/closure/);assert.deepEqual(child.commands,[]);});
test('quit during port probe prevents a late broker spawn',async()=>{
  const net=require('node:net'),original=net.createServer;let listening;
  net.createServer=()=>({once(){},listen(_port,_host,callback){listening=callback;},close(callback){callback();}});
  try{const engine=new Engine({resources:'never-used',state:'never-used',locks:'never-used',port:18980,log:'never-used'});const pending=engine.start();await engine.forceStop();listening();await assert.rejects(pending,error=>error.code==='START_CANCELLED');assert.equal(engine.child,null);}finally{net.createServer=original;}
});
