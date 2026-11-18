'use strict';
// "The previous session is still closing." (Judy's Quit spec rev 2, R2 and R4 item 4) through the real main.cjs:
// the start fails with PREVIOUS_CLOSING (broker exit 123), Try again re-checks it (P2, at least 0.5 s), the startup
// page is reused (no reload, so no blank frame), and Quit there exits at once.
const test=require('node:test'),assert=require('node:assert/strict');
const {mainFixture,flush}=require('./main-fixture.cjs');
const closing=leftoverSince=>Object.assign(Error('The previous session is still closing'),{code:'PREVIOUS_CLOSING',leftoverSince});

test('a start refused by a running part of the previous session shows the P screen with its times and tray label',async()=>{
  const since=Date.now()-75000;const f=mainFixture({engine:{startWith:()=>Promise.reject(closing(since))}});await flush();
  const state=f.state();
  assert.deepEqual([state.service,state.failure,state.leftoverSince],['failed','PREVIOUS_CLOSING',since]);
  assert.ok(Math.abs(state.checkedAt-Date.now())<5000);
  assert.equal(f.trayTip,'Comic Metadata — Previous session still closing. Open the window for details.');
  assert.deepEqual([f.trayQuit().label,f.trayQuit().enabled],['&Quit',true]);
  assert.deepEqual(f.window.loads,['startup.html']);  // Only the first load: the failure reuses the startup page.
});

test('Try again shows "checking" for at least 0.5 s, then the new result with a new check time, with no reload',async()=>{
  let started=0;const f=mainFixture({engine:{startWith:()=>{started++;return Promise.reject(closing(null));}}});await flush();
  const first=f.state();assert.equal(first.failure,'PREVIOUS_CLOSING');
  const firstSeen=first.leftoverSince;assert.equal(firstSeen,first.checkedAt);  // No record time: the first time this shell saw it.
  await new Promise(resolve=>setTimeout(resolve,20));  // Real time moves, so the next check time differs.
  f.action('retryService');await flush();
  assert.equal(started,2);
  assert.deepEqual([f.state().service,f.state().startupPhase,f.state().failure],['starting','previous',null]);
  await f.tick(499);assert.equal(f.state().startupPhase,'previous');
  await f.tick(1);const second=f.state();
  assert.deepEqual([second.service,second.failure],['failed','PREVIOUS_CLOSING']);
  assert.ok(second.checkedAt>first.checkedAt);assert.equal(second.leftoverSince,firstSeen);
  assert.deepEqual(f.window.loads,['startup.html']);
});

test('after a passed check the normal start phases follow, never before the 0.5 s hold',async()=>{
  const f=mainFixture({engine:{startWith:n=>n===1?Promise.reject(closing(1)):new Promise(()=>{})}});await flush();
  f.action('retryService');await flush();
  await f.tick(100);f.engine.emit('startup-phase','starting');f.engine.emit('startup-phase','catalog');await flush();
  assert.equal(f.state().startupPhase,'previous');
  await f.tick(400);assert.equal(f.state().startupPhase,'catalog');
  f.engine.emit('startup-phase','library');assert.equal(f.state().startupPhase,'library');
});

test('another failure after a re-check shows its own screen; a normal start never shows "checking"',async()=>{
  const port=Object.assign(Error('Port occupied'),{code:'PORT_BUSY'});
  const f=mainFixture({engine:{startWith:n=>Promise.reject(n===1?closing(1):port)}});await flush();
  f.action('retryService');await flush();await f.tick(500);
  assert.deepEqual([f.state().service,f.state().failure],['failed','PORT_BUSY']);
  f.action('retryService');await flush();
  assert.equal(f.state().startupPhase,'starting');  // A re-check only follows the P screen.
});

test('a failure reached from the dashboard still loads the startup page',async()=>{
  const f=mainFixture({engine:{startWith:n=>n===1?Promise.resolve({setup:{configured:true}}):Promise.reject(closing(1))}});await flush();
  assert.equal(f.window.url,'http://127.0.0.1:1');
  f.action('retryService');await flush();
  assert.deepEqual(f.window.loads,['startup.html','http://127.0.0.1:1','startup.html']);
});

test('Quit on the P screen, also while it re-checks, exits at once with no dialog',async()=>{
  for(const during of ['P1','P2']){
    const f=mainFixture({realStopper:true,engine:{startWith:n=>n===1?Promise.reject(closing(1)):new Promise(()=>{})}});await flush();
    if(during==='P2'){f.action('retryService');await flush();assert.equal(f.state().startupPhase,'previous');}
    f.action('quit');await flush();
    assert.equal(f.quits,1,during);assert.equal(f.engine.forceStops,1,during);
    await f.tick(5000);assert.equal(f.windows.length,1,during);
  }
});
