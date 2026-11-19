'use strict';
// The engine is spawned with no bytecode writing for its whole tree (Sergei's real 0.2.2->0.2.3
// update failed because workers wrote __pycache__ into the installed runtime). child_process.spawn
// is replaced before engine.cjs loads, so nothing is started.
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path');
const childProcess=require('node:child_process');const {EventEmitter}=require('node:events');
const calls=[];let brokerExit=126;
childProcess.spawn=(file,args,options)=>{calls.push({file,args,options});const child=new EventEmitter();child.pid=123;child.exitCode=brokerExit;child.stdin={on(){},write(){}};return child;};
const {Engine}=require('../engine.cjs');
async function resourcesIn(root){const resources=path.join(root,'resources');await fs.mkdir(path.join(resources,'runtime','python'),{recursive:true});await fs.mkdir(path.join(resources,'engine'));
  await fs.writeFile(path.join(resources,'runtime','python','python.exe'),'');await fs.writeFile(path.join(resources,'engine','engine_host.py'),'');return resources;}
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
// Quit always closes (Sergei 2026-11-18): a start whose own cleanup leaves a part running reports the start's failure,
// and the next start's broker re-checks the leftover record. Until 0.6.7 it became CLOSURE_UNCONFIRMED, and every
// later start returned at once (main.cjs guard), so Try again did nothing.
test('a start whose cleanup leaves a part running reports its own failure and leaves a leftover record',async()=>{
  const scratch=process.env.COMICS_META_TEST_SCRATCH;assert.ok(scratch);const root=await fs.mkdtemp(path.join(scratch,'engine-leftover-'));
  try{
    const engine=new Engine({resources:await resourcesIn(root),state:path.join(root,'state'),locks:path.join(root,'locks'),port:0,log:path.join(root,'logs','engine.log')});
    brokerExit=124;
    await assert.rejects(engine.start(),error=>error.code==='ENGINE_EXIT');
    const record=JSON.parse(await fs.readFile(path.join(root,'locks','leftover-'+engine.owner+'.json'),'utf8'));
    assert.equal(record.owner,engine.owner);
  }finally{brokerExit=126;assert.equal(path.dirname(root),path.resolve(scratch));await fs.rm(root,{recursive:true});}
});
// Judy's Quit spec rev 2, R2 and R4 items 4-5: a broker that refused to start because the previous session's part
// still runs (exit 123) is PREVIOUS_CLOSING, carries the oldest leftover record's own time, and shows no "Stopping".
test('broker exit 123 is PREVIOUS_CLOSING with the leftover record\'s time and no stopping phase',async()=>{
  const scratch=process.env.COMICS_META_TEST_SCRATCH;assert.ok(scratch);const root=await fs.mkdtemp(path.join(scratch,'engine-previous-'));
  try{
    const locks=path.join(root,'locks');await fs.mkdir(locks);
    await fs.writeFile(path.join(locks,'leftover-'+'a'.repeat(64)+'.json'),JSON.stringify({schema:1,owner:'a'.repeat(64),written:1763476000.5,members:[[4242,1]]}));
    await fs.writeFile(path.join(locks,'leftover-'+'b'.repeat(64)+'.json'),JSON.stringify({schema:1,owner:'b'.repeat(64),written:1763476900,members:null}));
    const engine=new Engine({resources:await resourcesIn(root),state:path.join(root,'state'),locks,port:0,log:path.join(root,'logs','engine.log')});
    const phases=[];engine.on('startup-phase',phase=>phases.push(phase));engine.closureWaitMs=60000;
    brokerExit=123;
    const began=Date.now();
    await assert.rejects(engine.start(),error=>error.code==='PREVIOUS_CLOSING'&&error.leftoverSince===1763476000500);
    assert.ok(Date.now()-began<1000);assert.deepEqual(phases,[]);
    await fs.writeFile(path.join(locks,'leftover-'+'a'.repeat(64)+'.json'),'not json');  // Unreadable: its file time counts.
    const stat=await fs.stat(path.join(locks,'leftover-'+'a'.repeat(64)+'.json'));
    assert.equal(engine.leftoverSince(),Math.min(stat.mtimeMs,1763476900000));
  }finally{brokerExit=126;assert.equal(path.dirname(root),path.resolve(scratch));await fs.rm(root,{recursive:true});}
});
// Code review v0.6.7 Q3: since 0.6.7 a forced stop gives up after the closure wait + 1 s, so a restart can start a
// new broker beside one that is frozen. When the old broker finally exited, its exit handler marked the new, healthy
// engine not ready and emitted exit with wasReady=true; main.cjs then auto-restarted and force-stopped that engine.
test('a late exit of an old broker leaves the new engine ready and emits nothing',async()=>{
  const scratch=process.env.COMICS_META_TEST_SCRATCH;assert.ok(scratch);const root=await fs.mkdtemp(path.join(scratch,'engine-stale-exit-'));
  try{
    const engine=new Engine({resources:await resourcesIn(root),state:path.join(root,'state'),locks:path.join(root,'locks'),port:0,log:path.join(root,'logs','engine.log')});
    brokerExit=null;engine.closureWaitS=1;engine.closureWaitMs=100;  // Brokers stay alive; each ignores 'force'.
    engine.call=async()=>({owned:true,phase:'ready'});  // The startup endpoint of whichever broker is current.
    await engine.start();
    const old=engine.child;assert.equal(engine.ready,true);
    const exits=[];engine.on('exit',(code,wasReady)=>exits.push([code,wasReady]));
    engine.ready=false;  // That engine stopped answering: the restart force-stops it, gives up, and starts anew.
    await engine.start();
    const current=engine.child;assert.notEqual(current,old);assert.equal(engine.ready,true);
    old.exitCode=124;old.emit('exit',124);  // The frozen old broker ends at last.
    assert.equal(engine.ready,true);assert.deepEqual(exits,[]);  // Before: ready false, exits [[124,true]].
    current.exitCode=126;current.emit('exit',126);  // Positive control: the current broker's exit still counts.
    assert.equal(engine.ready,false);assert.deepEqual(exits,[[126,true]]);
  }finally{brokerExit=126;assert.equal(path.dirname(root),path.resolve(scratch));await fs.rm(root,{recursive:true});}
});
