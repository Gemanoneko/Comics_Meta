'use strict';
const test=require('node:test');const assert=require('node:assert/strict');const {GracefulStop,PAUSE_LIMIT_MS}=require('../graceful-stop.cjs');
function engine(states){let calls=[];return {ready:true,calls,call:async(endpoint)=>{calls.push(endpoint);return endpoint==='/api/shell/status'?states.shift():{};},stop:async()=>calls.push('stop'),forceStop:async()=>calls.push('force')};}
test('incomplete setup exits without requesting GPU or worker pause',async()=>{const e=engine([{setup:{configured:false}}]);assert.equal(await new GracefulStop(e).run(),true);assert.deepEqual(e.calls,['/api/shell/status','stop']);});
test('install waits for acknowledged GPU release then stops, with no force path',async()=>{const e=engine([{setup:{configured:true}},{control:{phase:'paused',gpu_released:true}}]);assert.equal(await new GracefulStop(e).run('install'),true);assert.deepEqual(e.calls,['/api/shell/status','/api/shell/pause','/api/shell/status','/api/shell/pause','stop']);});
test('install communication failure cannot force a running engine',async()=>{const e=engine([{setup:{configured:true}}]);e.call=async endpoint=>{e.calls.push(endpoint);if(endpoint==='/api/shell/status'&&e.calls.filter(x=>x===endpoint).length>1)throw Error('offline');return {setup:{configured:true}};};await assert.rejects(new GracefulStop(e).run('install'));assert.ok(!e.calls.includes('force'));assert.ok(e.calls.includes('/api/shell/cancel-pause'));});
test('cancel restores temporary pause without touching human pause',async()=>{const e=engine([{setup:{configured:true}}]);const s=new GracefulStop(e);const call=e.call;e.call=async(endpoint)=>{const result=await call(endpoint);if(endpoint==='/api/shell/pause')s.cancel();return result;};assert.equal(await s.run(),false);assert.ok(e.calls.includes('/api/shell/cancel-pause'));assert.ok(!e.calls.includes('/api/resume'));assert.ok(!e.calls.includes('stop'));});
test('acknowledged GPU release error still requires paused quiescence before owned stop for install',async()=>{const e=engine([{setup:{configured:true}},{control:{phase:'paused',gpu_released:false,error:'synthetic acknowledged GPU release failure'}}]);assert.equal(await new GracefulStop(e).run('install'),true);assert.deepEqual(e.calls,['/api/shell/status','/api/shell/pause','/api/shell/status','/api/shell/pause','stop']);assert.ok(!e.calls.includes('force'));});
test('install pause deadline fails and cancels transient pause without stopping or forcing',async()=>{const e=engine([{setup:{configured:true}}]);const original=Date.now;let clock=0;Date.now=()=>clock;const call=e.call;e.call=async(endpoint)=>{const result=await call(endpoint);if(endpoint==='/api/shell/pause')clock=600001;return result;};try{await assert.rejects(new GracefulStop(e).run('install'),error=>/timed out/.test(error.message)&&error.code==='PAUSE_TIMEOUT');assert.equal(PAUSE_LIMIT_MS,600000);assert.deepEqual(e.calls,['/api/shell/status','/api/shell/pause','/api/shell/cancel-pause']);assert.ok(!e.calls.includes('stop'));assert.ok(!e.calls.includes('force'));}finally{Date.now=original;}});
// Quit always ends the process (Sergei 2026-11-18; Judy's Quit spec rev 2, R1 and R4 item 1): every quit path that does
// not end gracefully announces the 'ending' stage once, before its forced stop, and nothing follows it.
function quitEngine({ready=true,status=()=>({setup:{configured:true},control:{phase:'pausing'}}),stop}={}){
  const e={ready,closureWaitS:0.05,events:[],calls:[],stopTimeouts:[],
    call:async endpoint=>{e.events.push(endpoint);return endpoint==='/api/shell/status'?status(e):{};},
    stop:stop||(async({timeoutMs})=>{e.stopTimeouts.push(timeoutMs);e.events.push('stop');}),
    forceStop:async()=>{e.events.push('force');return true;}};
  return e;
}
function watch(stopper,e){stopper.on('stage',value=>e.events.push('stage:'+value.stage));return stopper;}
test('Quit now shows the ending at once and starts the forced stop without waiting for the status poll',async()=>{
  let release;const e=quitEngine();
  e.call=async endpoint=>{e.events.push(endpoint);if(endpoint==='/api/shell/status'&&e.events.filter(x=>x===endpoint).length===2){await new Promise(resolve=>{release=resolve;});return {control:{phase:'pausing'}};}return endpoint==='/api/shell/status'?{setup:{configured:true},control:{phase:'pausing'}}:{};};
  const s=watch(new GracefulStop(e),e);const run=s.run('quit');
  while(!release)await new Promise(resolve=>setImmediate(resolve));  // The second status call is pending.
  s.force();
  assert.deepEqual(e.events.slice(-2),['stage:ending','force']);  // Same frame: no poll in between.
  release();assert.equal(await run,true);
  assert.equal(e.events.filter(x=>x==='force').length,1);assert.ok(!e.events.slice(e.events.indexOf('stage:ending')+1).some(x=>x.startsWith('stage:')),e.events.join());  // No stage after the ending.
  s.cancel();assert.equal(s.cancelled,false);
});
test('every forced quit path announces the ending before its forced stop',async()=>{
  const cases={
    'engine not ready':quitEngine({ready:false}),
    'two failed status calls':(()=>{const e=quitEngine();let n=0;e.call=async endpoint=>{e.events.push(endpoint);if(endpoint==='/api/shell/status'&&++n>1)throw Error('offline');return endpoint==='/api/shell/status'?{setup:{configured:true}}:{};};return e;})(),
    'error path':(()=>{const e=quitEngine();e.call=async()=>{throw Error('refused');};return e;})(),
    'setup page stop fails':quitEngine({status:()=>({setup:{configured:false}}),stop:async()=>{throw Error('Owned engine stop timed out');}}),
  };
  for(const [name,e] of Object.entries(cases)){
    assert.equal(await watch(new GracefulStop(e),e).run('quit'),true,name);
    const ending=e.events.indexOf('stage:ending');assert.ok(ending>=0&&ending<e.events.indexOf('force'),name+': '+e.events.join(','));
    assert.equal(e.events.filter(x=>x==='stage:ending').length,1,name);
  }
});
test('the 10-minute cap ends with the ending stage and the forced stop',async()=>{
  const e=quitEngine();const original=Date.now;let clock=0;Date.now=()=>clock;
  const call=e.call;e.call=async endpoint=>{const result=await call(endpoint);if(endpoint==='/api/shell/pause')clock=PAUSE_LIMIT_MS;return result;};
  try{assert.equal(await watch(new GracefulStop(e),e).run('quit'),true);}finally{Date.now=original;}
  assert.deepEqual(e.events.slice(-2),['stage:ending','force']);
});
test('the setup page shows the ending state for its stop, and a clean stop needs no force',async()=>{
  const e=quitEngine({status:()=>({setup:{configured:false}})});
  assert.equal(await watch(new GracefulStop(e),e).run('quit'),true);
  assert.deepEqual(e.events,['/api/shell/status','stage:ending','stop']);
});
// Judy's R6 item 1: "Closing…" disables both buttons; it used to last up to the rest of the 10-minute cap.
test('the closing stage lasts no longer than the closure wait, then the forced path ends the quit',async()=>{
  const e=quitEngine({status:()=>({setup:{configured:true},control:{phase:'paused',gpu_released:true}}),
    stop:({timeoutMs})=>{e.stopTimeouts.push(timeoutMs);return new Promise((_,reject)=>setTimeout(()=>reject(Error('Owned engine stop timed out')),timeoutMs));}});
  const began=performance.now();assert.equal(await watch(new GracefulStop(e),e).run('quit'),true);
  assert.deepEqual(e.stopTimeouts,[50]);assert.ok(performance.now()-began<2000);
  assert.deepEqual(e.events.slice(-3),['stage:closing','stage:ending','force']);
});
test('install keeps its own flow: no ending stage and no forced stop',async()=>{
  const e=quitEngine({status:()=>({setup:{configured:true},control:{phase:'paused',gpu_released:true}})});
  assert.equal(await watch(new GracefulStop(e),e).run('install'),true);
  assert.ok(!e.events.includes('stage:ending')&&!e.events.includes('force'));assert.equal(e.stopTimeouts[0]>50,true);
});
