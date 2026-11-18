'use strict';
// The engine is spawned with no bytecode writing for its whole tree (Sergei's real 0.2.2->0.2.3
// update failed because workers wrote __pycache__ into the installed runtime). child_process.spawn
// is replaced before engine.cjs loads, so nothing is started.
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path');
const childProcess=require('node:child_process');const {EventEmitter}=require('node:events');
const calls=[];
childProcess.spawn=(file,args,options)=>{calls.push({file,args,options});const child=new EventEmitter();child.pid=123;child.exitCode=126;child.stdin={on(){},write(){}};return child;};
const {Engine}=require('../engine.cjs');
test('engine and all its descendants run with bytecode writing off',async()=>{
  const scratch=process.env.COMICS_META_TEST_SCRATCH;assert.ok(scratch);const root=await fs.mkdtemp(path.join(scratch,'engine-spawn-'));
  try{
    const resources=path.join(root,'resources');await fs.mkdir(path.join(resources,'runtime','python'),{recursive:true});await fs.mkdir(path.join(resources,'engine'));
    await fs.writeFile(path.join(resources,'runtime','python','python.exe'),'');await fs.writeFile(path.join(resources,'engine','engine_host.py'),'');
    const engine=new Engine({resources,state:path.join(root,'state'),locks:path.join(root,'locks'),port:0,log:path.join(root,'logs','engine.log')});
    await assert.rejects(engine.start(),/Engine exited/);
    assert.equal(calls.length,1);
    const [{args,options}]=calls;
    assert.equal(args[0],'-B');
    // Quit always closes (Sergei 2026-11-18): the broker's closure wait is the shell's one constant (R4 item 2).
    assert.equal(require('../engine.cjs').CLOSURE_WAIT_S,30);
    assert.deepEqual(args.slice(-2),['--closure-wait','30']);
    assert.equal(options.env.PYTHONDONTWRITEBYTECODE,'1');  // Inherited by the supervisor's workers.
    assert.equal(options.windowsHide,true);
  }finally{assert.equal(path.dirname(root),path.resolve(scratch));await fs.rm(root,{recursive:true});}
});
test('Retry after the broker ended on its own starts a new broker (TrayQA v0.6.4 finding 2)',async()=>{
  const scratch=process.env.COMICS_META_TEST_SCRATCH;assert.ok(scratch);const root=await fs.mkdtemp(path.join(scratch,'engine-retry-'));
  try{
    const resources=path.join(root,'resources');await fs.mkdir(path.join(resources,'runtime','python'),{recursive:true});await fs.mkdir(path.join(resources,'engine'));
    await fs.writeFile(path.join(resources,'runtime','python','python.exe'),'');await fs.writeFile(path.join(resources,'engine','engine_host.py'),'');
    const engine=new Engine({resources,state:path.join(root,'state'),locks:path.join(root,'locks'),port:0,log:path.join(root,'logs','engine.log')});
    engine.closureWaitMs=400;
    await assert.rejects(engine.start(),/Engine exited/);  // The first broker, as spawned.
    const first=engine.child,owner=calls.at(-1).options.env.COMICS_META_CLAIM_OWNER;
    first.exitCode=1;  // Ended from outside: no confirmed closure code.
    const before=calls.length;
    await assert.rejects(engine.start(),/Engine exited/);  // Retry.
    assert.equal(calls.length,before+1);  // A new broker was started ...
    assert.notEqual(engine.child,first);
    assert.notEqual(calls.at(-1).options.env.COMICS_META_CLAIM_OWNER,owner);  // ... with its own claim identity.
  }finally{assert.equal(path.dirname(root),path.resolve(scratch));await fs.rm(root,{recursive:true});}
});
// Code review v0.6.6 t1 (seen by Futaba): Retry read the stop generation only after its own closure wait, so a tray
// Quit inside that wait did not cancel it, and a broker was started 14 ms before the shell exited.
test('tray Quit during Retry\'s closure wait cancels Retry: no broker is started',async()=>{
  const net=require('node:net'),{GracefulStop}=require('../graceful-stop.cjs');
  const scratch=process.env.COMICS_META_TEST_SCRATCH;assert.ok(scratch);const root=await fs.mkdtemp(path.join(scratch,'engine-quit-retry-'));
  const holder=net.createServer();await new Promise(resolve=>holder.listen(0,'127.0.0.1',resolve));let held=true;
  try{
    const resources=path.join(root,'resources');await fs.mkdir(path.join(resources,'runtime','python'),{recursive:true});await fs.mkdir(path.join(resources,'engine'));
    await fs.writeFile(path.join(resources,'runtime','python','python.exe'),'');await fs.writeFile(path.join(resources,'engine','engine_host.py'),'');
    const engine=new Engine({resources,state:path.join(root,'state'),locks:path.join(root,'locks'),port:holder.address().port,log:path.join(root,'logs','engine.log')});
    // A broker ended from outside whose engine port is still bound: Retry waits for closure (no claims folder: none held).
    const dead=new EventEmitter();dead.exitCode=1;dead.signalCode=null;dead.stdin={writable:false};
    Object.assign(engine,{child:dead,owner:'e'.repeat(64),closureWaitMs:5000});
    const before=calls.length;
    const retry=engine.start();
    await new Promise(resolve=>setTimeout(resolve,300));  // Retry is inside its closure wait.
    const quit=new GracefulStop(engine).run('quit');  // Tray Quit: the engine is not ready, so it shares the wait.
    await new Promise(resolve=>holder.close(resolve));held=false;  // The port frees: closure is confirmed.
    assert.equal(await quit,true);
    await assert.rejects(retry,error=>error.code==='START_CANCELLED');
    assert.equal(calls.length,before);  // No broker was started for a shell that is exiting.
  }finally{if(held)await new Promise(resolve=>holder.close(resolve));assert.equal(path.dirname(root),path.resolve(scratch));await fs.rm(root,{recursive:true});}
});
