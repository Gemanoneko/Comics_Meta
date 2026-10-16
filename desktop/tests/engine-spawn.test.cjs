'use strict';
// The engine is spawned with no bytecode writing for its whole tree (Sergei's real 0.2.2->0.2.3
// update failed because workers wrote __pycache__ into the installed runtime). child_process.spawn
// is replaced before engine.cjs loads, so nothing is started.
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs/promises'),path=require('node:path');
const childProcess=require('node:child_process');const {EventEmitter}=require('node:events');
const calls=[];
childProcess.spawn=(file,args,options)=>{calls.push({file,args,options});const child=new EventEmitter();child.exitCode=1;child.stdin={on(){},write(){}};return child;};
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
    assert.equal(options.env.PYTHONDONTWRITEBYTECODE,'1');  // Inherited by the supervisor's workers.
    assert.equal(options.windowsHide,true);
  }finally{assert.equal(path.dirname(root),path.resolve(scratch));await fs.rm(root,{recursive:true});}
});
