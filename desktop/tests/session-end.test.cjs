'use strict';
// Windows sign-out or shutdown (query-session-end) through the real main.cjs: the shell always exits, and before
// Windows ends it. A forced stop that threw skipped exit() (main.cjs:113 until 0.6.7), and since 0.6.7 the forced stop
// may take the broker's whole 30 s closure wait (Judy's Quit spec rev 2, R6 item 4).
const test=require('node:test'),assert=require('node:assert/strict');
const {mainFixture,flush}=require('./main-fixture.cjs');

async function sessionEnd(forceWith){
  const f=mainFixture({engine:{forceWith}});const rejections=[];const onRejection=error=>rejections.push(error);
  process.on('unhandledRejection',onRejection);f.cleanup=()=>process.off('unhandledRejection',onRejection);f.rejections=rejections;
  f.window.emit('query-session-end',{preventDefault(){}});await flush();return f;
}
test('a forced stop that throws at sign-out or shutdown still exits',async()=>{
  const f=await sessionEnd(()=>Promise.reject(Error('Owned engine closure was not confirmed')));
  try{
    await f.tick(2499);assert.equal(f.engine.forceStops,0);
    await f.tick(1);assert.equal(f.engine.forceStops,1);
    assert.equal(f.quits,1);assert.equal(f.engine.leftovers,1);assert.deepEqual(f.rejections,[]);
  }finally{f.cleanup();}
});
test('a forced stop that has not returned 2 s later: the shell exits anyway and leaves a leftover record',async()=>{
  const f=await sessionEnd(()=>new Promise(()=>{}));
  try{
    await f.tick(2500+1999);assert.equal(f.quits,0);
    await f.tick(1);assert.equal(f.quits,1);assert.equal(f.engine.leftovers,1);
  }finally{f.cleanup();}
});
test('a confirmed forced stop exits at once with no record',async()=>{
  const f=await sessionEnd(()=>Promise.resolve(true));
  try{await f.tick(2500);assert.equal(f.quits,1);assert.equal(f.engine.leftovers,0);}finally{f.cleanup();}
});
