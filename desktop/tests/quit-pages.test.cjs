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

test('the existing stages are unchanged',()=>{
  const p=page('stopping');p.push({stopping:{...pausing,stage:'closing',control:{phase:'paused',gpu_released:true}},update:{phase:'idle'}});
  assert.equal(p.el('status').textContent,'Gemma released from GPU. Closing…');
  assert.equal(p.el('cancel').disabled,true);assert.equal(p.el('force').disabled,true);assert.equal(p.el('actions').hidden,false);
  assert.equal(p.el('cancel').title,'Stop quitting. Processing resumes unless you had paused it.');
  assert.equal(p.el('force').title,'Exit without waiting. An interrupted write keeps its recovery backup.');
});

test('a quit dialog shown before the first stage reads as pausing, with both buttons',()=>{
  const p=page('stopping');p.push({stopping:{mode:'quit'},update:{phase:'idle'}});
  assert.equal(p.el('status').textContent,'Pausing — finishing the current operation. Progress is saved.');
  assert.equal(p.el('actions').hidden,false);assert.equal(p.el('cancel').disabled,false);assert.equal(p.doc.activeElement,p.el('cancel'));
});
