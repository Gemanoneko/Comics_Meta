'use strict';
// The tray in a private QA profile, through the real main.cjs (main-fixture.cjs).
// A QA profile has no tray by default: on the user's own desktop a tray registers an icon with Explorer under his
// logon (a second icon beside his app's, and a record in his Windows profile). A QA policy with "tray": true gets the
// tray on the line the installed app runs. That is for a separate desktop with no shell tray only
// (scripts/qa/private-desktop.py). The release smoke needs it: the tray's Quit is this app's close invariant, and the
// 0.6.10 candidate at 86425b1 had no way to reach it in a QA profile.
const test=require('node:test'),assert=require('node:assert/strict'),path=require('node:path');
const {mainFixture,flush}=require('./main-fixture.cjs');
const root=path.resolve('fixture-qa');
const policy=extra=>({root,profile:path.join(root,'profile'),cache:path.join(root,'cache'),state:path.join(root,'state'),locks:path.join(root,'locks'),
  enginePort:18980,feedURL:'http://127.0.0.1:18981/feed/'+'a'.repeat(32)+'/',feedToken:'b'.repeat(64),...extra});
const status={setup:{configured:true},control:{requested:false,phase:'running'}};
const ready={ready:true,startWith:()=>Promise.resolve(status),callWith:()=>Promise.resolve(status)};

test('a QA policy with "tray": true gets the installed app\'s tray, and its Quit runs the real quit',async()=>{
  const f=mainFixture({qaPolicy:policy({tray:true}),engine:ready});await flush();
  assert.equal(f.trays,1);
  assert.equal(f.trayTip,'Comic Metadata — Processing enabled');
  assert.deepEqual(Array.from(f.trayMenu,item=>[item.label??item.type,item.enabled]),[['&Open',undefined],['&Pause && release GPU',true],['separator',undefined],['&Quit',true]]);
  // Still a QA profile: the window is offscreen and the tray's Open shows nothing.
  f.trayMenu[0].click();
  assert.equal(f.window.options.webPreferences.offscreen,true);assert.deepEqual([f.window.shown,f.window.focused],[0,0]);
  // As installed: the close button hides to the tray, and the tray's Quit ends the app.
  assert.equal(f.window.close(),false);await flush();assert.equal(f.stopper.runs,0);
  f.trayQuit().click();await flush();
  assert.deepEqual([f.stopper.runs,f.stopper.mode],[1,'quit']);assert.deepEqual([f.trayQuit().label,f.trayQuit().enabled],['Quitting…',false]);
  f.stopper.settle.resolve(true);await flush();
  assert.deepEqual([f.quits,f.trayDestroyed],[1,true]);
});

test('a QA policy without "tray": true has no tray, and its close button quits',async()=>{
  for(const extra of [{},{tray:false}]){
    const f=mainFixture({qaPolicy:policy(extra),engine:ready});await flush();
    assert.equal(f.trays,0);assert.equal(f.trayMenu,null);
    assert.equal(f.window.close(),false);await flush();
    assert.deepEqual([f.stopper.runs,f.stopper.mode],[1,'quit']);
  }
});

test('the installed app always has its tray',async()=>{
  const f=mainFixture({engine:ready});await flush();
  assert.equal(f.trays,1);assert.equal(f.trayTip,'Comic Metadata — Processing enabled');
  assert.deepEqual([f.trayQuit().label,f.trayQuit().enabled],['&Quit',true]);
});
