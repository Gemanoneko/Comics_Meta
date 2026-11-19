'use strict';
// The quit dialog (stopping.html/js) against Judy's Quit spec rev 2, R1: strings exact, buttons, Escape, focus.
const test=require('node:test'),assert=require('node:assert/strict');
const {page}=require('./page-fixture.cjs');
const pausing={mode:'quit',stage:'pausing',control:{phase:'pausing',waiting_for:['metadata']},elapsed:2000,gpuElapsed:0};
const ending=(extra={})=>({stopping:{mode:'quit',stage:'ending',waitSeconds:30,late:false,...extra},update:{phase:'idle'}});

test('the ending state: status, the 30-second detail, then the recovery sentence at 10 s; no buttons',()=>{
  const p=page('stopping');p.push({stopping:pausing,update:{phase:'idle'}});
  assert.equal(p.doc.activeElement,p.el('cancel'));  // Unchanged: a dialog opened in a pausing stage focuses Cancel quit.
  p.push(ending());
  assert.equal(p.el('title').textContent,'Quitting Comic Metadata');
  assert.equal(p.el('status').textContent,'Stopping the local service…');
  assert.equal(p.el('detail').textContent,'This can take up to 30 seconds.');
  assert.equal(p.el('actions').hidden,true);  // The row is hidden, not emptied.
  assert.deepEqual(p.buttons().map(button=>button.textContent),['Cancel quit','Quit now']);
  assert.equal(p.el('detail').getAttribute('role'),'status');assert.equal(p.el('status').getAttribute('role'),'status');
  p.push(ending({late:true}));
  assert.equal(p.el('detail').textContent,'This can take up to 30 seconds. An interrupted write keeps its recovery backup.');
});

test('the number in the text is the shell\'s closure wait, not a literal',()=>{
  const p=page('stopping');p.push(ending({waitSeconds:7}));
  assert.equal(p.el('detail').textContent,'This can take up to 7 seconds.');
});

test('Quit now pressed: focus moves from the vanished button to the status line',()=>{
  const p=page('stopping');p.push({stopping:pausing,update:{phase:'idle'}});
  p.el('force').focus();p.el('force').click();assert.deepEqual(p.actions,['forceQuit']);
  p.push(ending());
  assert.equal(p.doc.activeElement,p.el('status'));assert.equal(p.el('status').tabIndex,-1);
});

test('a dialog first created in the ending state takes no focus',()=>{
  const p=page('stopping');p.push(ending());
  assert.equal(p.doc.activeElement,null);
});

test('in the ending state Escape does nothing, and no later stage brings the buttons back',()=>{
  const p=page('stopping');p.push({stopping:pausing,update:{phase:'idle'}});
  p.key('Escape');assert.deepEqual(p.actions,['cancelStop']);  // Positive control: Escape cancels while it can.
  p.push(ending());p.key('Escape');assert.deepEqual(p.actions,['cancelStop']);
  p.push({stopping:pausing,update:{phase:'idle'}});
  assert.equal(p.el('actions').hidden,true);assert.equal(p.el('status').textContent,'Stopping the local service…');
});

// Judy's Quit spec rev 3 (copy fix, Sergei 2026-11-19): the Closing stage states the time left, 2 x the closure wait,
// from 5 s in (the shell's late flag); its disabled buttons say why they are off; nothing else is in its detail.
const closingState=(extra={},control={phase:'paused',gpu_released:true})=>({stopping:{mode:'quit',stage:'closing',control,elapsed:2000,waitSeconds:30,late:false,...extra},update:{phase:'idle'}});
const ROW1='This can take up to 60 seconds.',ROW2='Cannot cancel: the app is already closing.',ROW3='The app is already closing and exits by itself.';

test('rev 3 Closing: status unchanged, buttons disabled with rows 2 and 3, detail empty until 5 s, then row 1',()=>{
  const p=page('stopping');p.push({stopping:pausing,update:{phase:'idle'}});p.push(closingState());
  assert.equal(p.el('status').textContent,'Gemma released from GPU. Closing…');  // Row 5: unchanged.
  assert.equal(p.el('cancel').disabled,true);assert.equal(p.el('force').disabled,true);assert.equal(p.el('actions').hidden,false);
  assert.equal(p.el('cancel').title,ROW2);assert.equal(p.el('force').title,ROW3);  // Before: the promising pausing tooltips.
  assert.equal(p.el('detail').textContent,'');  // A healthy quit leaves Closing before 5 s: no number flashes.
  assert.equal(p.el('detail').getAttribute('role'),'status');  // Live before its text is set: announced once.
  p.push(closingState({late:true,elapsed:7000}));
  assert.equal(p.el('detail').textContent,ROW1);
  p.push(closingState({late:true},{phase:'paused',error:'nvidia-smi failed'}));
  assert.equal(p.el('status').textContent,'GPU release not confirmed. Closing…');assert.equal(p.el('detail').textContent,ROW1);
});

test('rev 3 Closing suppresses "Waiting for" and the Quit now line (C7 check 5)',()=>{
  const p=page('stopping');
  p.push(closingState({elapsed:70000,late:true},{phase:'paused',gpu_released:true,waiting_for:['metadata']}));
  assert.equal(p.el('detail').textContent,ROW1);  // Exactly row 1. Before: "Waiting for: comic processing Quit now exits ...".
  p.push(closingState({elapsed:70000,late:false},{phase:'paused',gpu_released:true,waiting_for:['metadata','browser']}));
  assert.equal(p.el('detail').textContent,'');
  assert.doesNotMatch(p.el('detail').textContent,/Waiting for|Quit now exits without waiting/);
});

test('rev 3: the numbers are the shell\'s (policy 12 gives 24, then 12), and 1 reads "1 second"',()=>{
  const p=page('stopping');p.push(closingState({waitSeconds:12,late:true}));
  assert.equal(p.el('detail').textContent,'This can take up to 24 seconds.');
  p.push(ending({waitSeconds:12}));assert.equal(p.el('detail').textContent,'This can take up to 12 seconds.');
  const q=page('stopping');q.push(ending({waitSeconds:1}));assert.equal(q.el('detail').textContent,'This can take up to 1 second.');
  const source=require('node:fs').readFileSync(require('node:path').join(__dirname,'..','stopping.js'),'utf8');
  assert.doesNotMatch(source,/\b(30|60)\b/);  // No literal 30 or 60 seconds (C7 check 3); 30000/60000 ms thresholds are not numbers shown.
});

test('rev 3 leaves the pausing and GPU stages and install mode as they were',()=>{
  const p=page('stopping');p.push({stopping:{...pausing,elapsed:70000},update:{phase:'idle'}});
  assert.equal(p.el('detail').textContent,'Waiting for: comic processing Quit now exits without waiting. An interrupted write keeps its recovery backup.');
  assert.equal(p.el('cancel').title,'Stop quitting. Processing resumes unless you had paused it.');
  assert.equal(p.el('force').title,'Exit without waiting. An interrupted write keeps its recovery backup.');
  assert.equal(p.el('cancel').disabled,false);
  const i=page('stopping');
  i.push({stopping:{mode:'install',stage:'closing',control:{phase:'paused',gpu_released:true},elapsed:2000,late:true,waitSeconds:30},update:{phase:'idle',version:'0.6.8'}});
  assert.equal(i.el('status').textContent,'Gemma released from GPU. The app restarts to install.');
  assert.equal(i.el('detail').textContent,'');  // No time sentence in install mode (C6 item 1).
  assert.equal(i.el('cancel').title,'Stop the install. Processing resumes unless you had paused it.');
});

// The startup screen's "previous session still closing" states (Judy's Quit spec rev 2, R2): P1, P2 (checking), P3.
const base={service:'failed',failure:'PREVIOUS_CLOSING',update:{phase:'idle'},loadedShellVersion:'0.6.7'};
const P1_DETAIL='Part of the local service has not ended yet. Try again in a moment.';
const P3_DETAIL='Part of the local service has not ended yet. Try again, or restart your PC to clear it.';
function previous(p,{age=30000,attempt=p.now-1000}={}){return {...base,startupAttempt:attempt,checkedAt:p.now,leftoverSince:p.now-age};}
function checking(p,attempt){return {...base,service:'starting',failure:null,startupPhase:'previous',startupAttempt:attempt,checkedAt:p.now-5000,leftoverSince:p.now-35000};}
const view=p=>({heading:p.el('status').textContent,detail:p.el('detail').textContent,detailShown:p.el('detail').style.visibility!=='hidden',
  checked:p.el('checked').textContent,checkedShown:!p.el('checked').hidden&&p.el('checked').style.visibility!=='hidden',actions:!p.el('actions').hidden,
  buttons:p.buttons().map(button=>[button.textContent,button.title,button.disabled,button.getAttribute('aria-busy')])});

test('P1: strings, check time, buttons in order with their tooltips, all enabled; the heading has focus',()=>{
  const p=page('startup');p.push(previous(p));const v=view(p);
  assert.equal(v.heading,'The previous session is still closing.');assert.equal(v.detail,P1_DETAIL);assert.equal(v.detailShown,true);
  assert.equal(v.checked,'Checked at '+new Date(p.now).toLocaleTimeString()+'.');assert.equal(v.checkedShown,true);assert.match(v.checked,/^Checked at .*\d\d.*\.$/);
  assert.equal(v.actions,true);
  assert.deepEqual(v.buttons,[['Try again','Check the previous session again. The app starts once it has ended.',false,null],
    ['Open log folder',"Open the local app's log folder.",false,null],['Quit','Close Comic Metadata.',false,null]]);
  assert.equal(p.doc.activeElement,p.el('status'));
  const order=p.doc.order.map(element=>element.id);assert.ok(order.indexOf('detail')<order.indexOf('checked')&&order.indexOf('checked')<order.indexOf('actions'));
  assert.equal(p.el('checked').getAttribute('role'),null);assert.equal(p.el('checked').getAttribute('aria-live'),null);  // Not live.
});

test('P2: Try again re-checks: its label stays, it is disabled and busy; texts stay in place, hidden; logs and Quit work',()=>{
  const p=page('startup');p.push(previous(p));
  p.el('retry').click();assert.deepEqual(p.actions,['retryService']);assert.equal(p.doc.activeElement,p.el('status'));
  const attempt=p.now;p.push(checking(p,attempt));let v=view(p);
  assert.equal(v.heading,'Checking the previous session…');
  assert.equal(v.detail,P1_DETAIL);assert.equal(v.detailShown,false);assert.equal(v.checkedShown,false);assert.ok(v.checked.startsWith('Checked at '));
  assert.deepEqual(v.buttons,[['Try again','Checking the previous session…',true,'true'],['Open log folder',"Open the local app's log folder.",false,null],['Quit','Close Comic Metadata.',false,null]]);
  p.push(checking(p,attempt));assert.equal(p.el('retry').disabled,true);  // A repeated state does not re-enable it.
  p.el('quit').click();p.el('logs').click();assert.deepEqual(p.actions,['retryService','quit','openLogs']);
  p.tick(9999);assert.equal(view(p).detailShown,false);
  p.tick(1);v=view(p);assert.equal(v.detail,'This is taking longer than usual.');assert.equal(v.detailShown,true);
  p.push(checking(p,attempt));assert.equal(view(p).detailShown,true);
  p.push(previous(p,{attempt}));v=view(p);  // The result: P1 again, with the new check time.
  assert.equal(v.detail,P1_DETAIL);assert.equal(v.detailShown,true);assert.equal(v.checkedShown,true);assert.equal(v.buttons[0][2],false);assert.equal(v.buttons[0][3],null);
  assert.equal(p.doc.activeElement,p.el('status'));
});

test('P3: the same screen once the record is 2 minutes old, with the restart line',()=>{
  const p=page('startup');p.push(previous(p,{age:119999}));assert.equal(view(p).detail,P1_DETAIL);
  p.push(previous(p,{age:120000}));const v=view(p);
  assert.equal(v.heading,'The previous session is still closing.');assert.equal(v.detail,P3_DETAIL);assert.equal(v.buttons[0][1],'Check the previous session again. The app starts once it has ended.');
});

test('a passed check runs the normal start phases: the buttons and the check time hide as in any start',()=>{
  const p=page('startup');p.push(previous(p));const attempt=p.now;p.push(checking(p,attempt));
  p.push({...base,service:'starting',failure:null,startupPhase:'starting',startupAttempt:attempt});const v=view(p);
  assert.equal(v.heading,'Starting the local service…');assert.equal(v.detail,'');assert.equal(v.detailShown,true);assert.equal(v.actions,false);assert.equal(v.checkedShown,false);
});

test('a normal start never shows "checking", and the other failure screens are unchanged',()=>{
  const p=page('startup');p.push({...base,service:'starting',failure:null,startupPhase:'starting',startupAttempt:p.now});
  assert.equal(p.el('status').textContent,'Starting the local service…');assert.equal(p.el('actions').hidden,true);
  p.push({...base,failure:'PORT_BUSY',startupAttempt:p.now});const v=view(p);
  assert.equal(v.heading,'Could not start the local service.');assert.equal(v.detail,'Another app is using the local service port. Close the other copy, then try again.');
  assert.equal(v.checkedShown,false);assert.deepEqual(v.buttons[0],['Try again','Try starting the local service again.',false,null]);
});

test('a quit dialog shown before the first stage reads as pausing, with both buttons',()=>{
  const p=page('stopping');p.push({stopping:{mode:'quit'},update:{phase:'idle'}});
  assert.equal(p.el('status').textContent,'Pausing — finishing the current operation. Progress is saved.');
  assert.equal(p.el('actions').hidden,false);assert.equal(p.el('cancel').disabled,false);assert.equal(p.doc.activeElement,p.el('cancel'));
});
