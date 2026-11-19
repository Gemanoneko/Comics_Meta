'use strict';
// Quit always ends the process (Sergei 2026-11-18; ProcessRules § Desktop App / GUI Rules; Judy's Quit spec rev 2, R1
// and R4 items 1-3), driven through the real main.cjs (main-fixture.cjs): one continuous Quit state on one surface.
const test=require('node:test'),assert=require('node:assert/strict');
const {mainFixture,flush}=require('./main-fixture.cjs');

async function quitting(options){const f=mainFixture(options);f.action('quit');await flush();assert.equal(f.stopper.runs,1);return f;}
const pausing={stage:'pausing',mode:'quit',control:{phase:'pausing'},elapsed:1600,gpuElapsed:0};

test('the quit state holds from Quit accepted to exit; the stopper finishing neither clears it nor closes the dialog',async()=>{
  const f=await quitting();
  assert.deepEqual(f.state().stopping,{mode:'quit'});
  f.stopper.emit('stage',pausing);await flush();
  const dialog=f.dialog;assert.ok(dialog);assert.equal(dialog.shown,1);  // The existing stages keep show().
  f.stopper.emit('stage',{stage:'ending',mode:'quit'});
  // Same frame: the open dialog is told before anything else happens, and no second dialog is made.
  assert.equal(dialog.lastState.stopping.stage,'ending');assert.equal(dialog.lastState.stopping.waitSeconds,30);assert.equal(f.windows.length,2);
  f.stopper.settle.resolve(true);  // 'finished' fires first, then the run resolves.
  assert.equal(f.state().stopping.stage,'ending');assert.equal(f.dialog,dialog);
  await flush();
  assert.equal(f.quits,1);assert.equal(f.trayDestroyed,true);
});

test('with no dialog yet, the ending dialog appears 1.5 s after Quit was accepted, without focus',async()=>{
  const f=await quitting();
  await f.tick(200);f.stopper.emit('stage',{stage:'ending',mode:'quit'});
  await f.tick(1299);assert.equal(f.dialog,null);
  await f.tick(1);const dialog=f.dialog;assert.ok(dialog,'dialog at 1.5 s');
  assert.equal(dialog.shownInactive,1);assert.equal(dialog.shown,0);assert.equal(dialog.focused,0);
  assert.equal(f.window.shownInactive,1);assert.equal(f.window.focused,0);  // A hidden window is shown without focus.
  assert.equal(dialog.lastState.stopping.stage,'ending');
});

test('a forced close that ends within 1.5 s shows no dialog',async()=>{
  const f=await quitting();
  f.stopper.emit('stage',{stage:'ending',mode:'quit'});await f.tick(500);
  f.stopper.settle.resolve(true);await flush();assert.equal(f.quits,1);
  await f.tick(5000);assert.equal(f.windows.length,1);
});

test('the detail gains its second sentence at 10 s, and the number follows the engine\'s closure wait',async()=>{
  const f=await quitting({engine:{closureWaitS:12}});
  f.stopper.emit('stage',{stage:'ending',mode:'quit'});
  assert.equal(f.state().stopping.waitSeconds,12);
  await f.tick(9999);assert.equal(f.state().stopping.late,false);
  await f.tick(1);assert.equal(f.state().stopping.late,true);assert.equal(f.dialog.lastState.stopping.late,true);
});

test('the shell exits by the closure wait + 1 s even if the forced stop never returns, and records a leftover',async()=>{
  const f=await quitting();
  f.stopper.emit('stage',{stage:'ending',mode:'quit'});
  await f.tick(31499);assert.equal(f.quits,0);
  await f.tick(1);assert.equal(f.quits,1);assert.equal(f.engine.leftovers,1);
});

test('the tray reads Quitting… and its Quit stays disabled until exit; a second Quit does nothing',async()=>{
  const f=await quitting();
  assert.deepEqual([f.trayQuit().label,f.trayQuit().enabled],['Quitting…',false]);
  f.stopper.emit('stage',{stage:'ending',mode:'quit'});f.stopper.busy=false;f.stopper.emit('finished');await flush();  // Between the stopper and exit().
  assert.deepEqual([f.trayQuit().label,f.trayQuit().enabled],['Quitting…',false]);
  f.action('quit');f.trayQuit().click();f.app.emit('before-quit',{preventDefault(){}});await flush();
  assert.equal(f.stopper.runs,1);
});

test('the error path: the ending state, the forced stop, the dialog through the wait, then exit',async()=>{
  let finish;const f=await quitting({engine:{forceWith:()=>new Promise(resolve=>{finish=resolve;})}});
  f.stopper.settle.reject(Error('status refused'));await flush();
  assert.equal(f.state().stopping.stage,'ending');assert.equal(f.engine.forceStops,1);
  await f.tick(1500);assert.ok(f.dialog);assert.equal(f.dialog.shownInactive,1);
  assert.deepEqual([f.trayQuit().label,f.trayQuit().enabled],['Quitting…',false]);
  finish(false);await flush();assert.equal(f.quits,1);
});

test('the dialog\'s close button cancels the quit while it can, and does nothing once the ending has begun',async()=>{
  const f=await quitting();
  f.stopper.emit('stage',pausing);await flush();
  assert.equal(f.dialog.close(),false);assert.equal(f.stopper.cancels,1);
  f.stopper.emit('stage',{stage:'ending',mode:'quit'});
  assert.equal(f.dialog.close(),false);assert.equal(f.stopper.cancels,1);
  f.stopper.settle.resolve(true);await flush();assert.equal(f.quits,1);
});

test('Cancel quit is the one way back: state cleared, dialog closed, Quit works again',async()=>{
  const f=await quitting();
  f.stopper.emit('stage',pausing);await flush();const dialog=f.dialog;
  f.stopper.settle.resolve(false);await flush();
  assert.equal(f.state().stopping,null);assert.equal(dialog.destroyed,true);assert.equal(f.quits,0);
  assert.deepEqual([f.trayQuit().label,f.trayQuit().enabled],['&Quit',true]);
  f.action('quit');await flush();assert.equal(f.stopper.runs,2);
});

test('an install keeps its own flow: its dialog closes when the stopper finishes',async()=>{
  const f=mainFixture();
  f.stopper.busy=true;f.stopper.emit('stage',{stage:'closing',mode:'install',control:{phase:'paused',gpu_released:true},elapsed:2000});await flush();
  const dialog=f.dialog;assert.ok(dialog);
  f.stopper.busy=false;f.stopper.emit('finished');
  assert.equal(f.state().stopping,null);assert.equal(dialog.destroyed,true);
});

test('the dialog exists by 1.5 s on every path, even before the stopper reports a stage (R4 item 1)',async()=>{
  const f=await quitting();  // An unresponsive engine: its first status call is still pending.
  await f.tick(1499);assert.equal(f.dialog,null);
  await f.tick(1);assert.ok(f.dialog);await flush();
  assert.equal(f.dialog.shown,1);assert.equal(f.dialog.shownInactive,0);  // Not the ending state: as today's stages.
  assert.deepEqual(f.dialog.lastState.stopping,{mode:'quit'});
});

test('Cancel quit before 1.5 s leaves no dialog behind',async()=>{
  const f=await quitting();
  await f.tick(500);f.stopper.settle.resolve(false);await flush();
  await f.tick(5000);assert.equal(f.windows.length,1);assert.equal(f.state().stopping,null);
});

// Judy's Quit spec rev 3 (copy fix, Sergei 2026-11-19): the shell sends the closure wait with Quit's Closing stage
// and marks it late at 5 s, by the same timers as the ending's 10 s sentence; install mode is unchanged.
test('Quit\'s Closing stage carries the closure wait and turns late at 5 s; the ending still follows',async()=>{
  const f=await quitting({engine:{closureWaitS:12}});
  f.stopper.emit('stage',{stage:'closing',mode:'quit',control:{phase:'paused',gpu_released:true},elapsed:3400});await flush();
  assert.equal(f.state().stopping.stage,'closing');
  assert.equal(f.state().stopping.waitSeconds,12);assert.equal(f.state().stopping.late,false);  // Before: no waitSeconds.
  await f.tick(4999);assert.equal(f.state().stopping.late,false);
  await f.tick(1);assert.equal(f.state().stopping.late,true);assert.equal(f.dialog.lastState.stopping.late,true);
  f.stopper.emit('stage',{stage:'ending',mode:'quit'});
  assert.deepEqual([f.state().stopping.stage,f.state().stopping.waitSeconds,f.state().stopping.late],['ending',12,false]);
});

test('a healthy Closing that ends within 5 s never turns late',async()=>{
  const f=await quitting();
  f.stopper.emit('stage',{stage:'closing',mode:'quit',control:{phase:'paused',gpu_released:true},elapsed:2000});await flush();
  await f.tick(1000);f.stopper.settle.resolve(true);await flush();
  assert.equal(f.quits,1);assert.equal(f.dialog.lastState.stopping.late,false);
});

test('install mode\'s Closing is passed on as the stopper reports it',async()=>{
  const f=mainFixture();f.stopper.busy=true;
  const closing={stage:'closing',mode:'install',control:{phase:'paused',gpu_released:true},elapsed:2000};
  f.stopper.emit('stage',closing);await flush();
  assert.deepEqual(f.state().stopping,closing);
  await f.tick(6000);assert.deepEqual(f.state().stopping,closing);
});
