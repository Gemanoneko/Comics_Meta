'use strict';
// Source24 exit-status seam. Synthetic only: no builder, makensis or Electron.
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {spawnSync}=require('node:child_process');
const seam=path.resolve(__dirname,'..','..','scripts','packaging','failure-exit.cjs');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
// Exact pinned prepare08 dependency bytes for the optional actual-vendor run.
const PINNED={'async-exit-hook/index.js':'78e91cdddafd1c616fa859c33de05199e291051826fe420b45e72b8a196fb9ad','temp-file/out/main.js':'c4bce3ea8cff4c0f4db72ddfddd070932032994497468c49cf0644d7264dc6c2'};
const modules=process.env.COMICS_META_TEST_BUILDER_MODULES;
function fixtureDir(){const scratch=process.env.COMICS_META_TEST_SCRATCH;assert.ok(scratch&&path.isAbsolute(scratch));return fs.mkdtempSync(path.join(scratch,'exit-'));}
// catch='control' reproduces the pre-source24 catch (exitCode=1 only).
const CATCH="main().catch(e=>{console.error(e.message);if(mode==='seam')require(SEAM).retainFailureExit();else process.exitCode=1;});\n";
function run(dir,body,mode){
  const file=path.join(dir,'fixture.cjs');
  fs.writeFileSync(file,"'use strict';\nconst fs=require('node:fs'),path=require('node:path');\nconst SEAM="+JSON.stringify(seam)+",MODULES="+JSON.stringify(modules||'')+";\nconst mode=process.argv[2];\n"+body+CATCH);
  const result=spawnSync(process.execPath,[file,mode],{cwd:dir,windowsHide:true,encoding:'utf8',timeout:60000,
    env:{SystemRoot:process.env.SystemRoot||'C:\\Windows',WINDIR:process.env.WINDIR||'C:\\Windows',PATH:'C:\\Windows\\System32',TEMP:dir,TMP:dir}});
  assert.equal(result.error,undefined);assert.equal(result.signal,null);
  return result;
}
// Same shape as async-exit-hook 2.0.1: beforeExit -> async cleanup -> nextTick process.exit(0).
const MODEL="let called=false;process.on('beforeExit',()=>{if(called)return;called=true;setTimeout(()=>{process.stdout.write('cleaned\\n');process.nextTick(()=>process.exit(0));},20);});\n"+
  "async function main(){if(mode==='success')return;throw new Error('synthetic builder failure');}\n";
test('modelled vendor beforeExit exit(0) overrides the old catch; seam keeps cleanup and exits 1',()=>{
  const dir=fixtureDir();
  try{
    const control=run(dir,MODEL,'control');
    assert.equal(control.status,0,'positive control: old catch is overridden to native exit 0');
    assert.match(control.stdout,/cleaned/);assert.match(control.stderr,/synthetic builder failure/);
    const fixed=run(dir,MODEL,'seam');
    assert.equal(fixed.status,1);assert.match(fixed.stdout,/cleaned/);assert.match(fixed.stderr,/synthetic builder failure/);
    const success=run(dir,MODEL,'success');
    assert.equal(success.status,0);assert.match(success.stdout,/cleaned/);
  }finally{fs.rmSync(dir,{recursive:true});}
});
test('retainFailureExit sets failure code and one final exit listener only',()=>{
  const listeners=[];const proc={exitCode:undefined,on(event,fn){listeners.push([event,fn]);}};
  require(seam).retainFailureExit(proc);
  assert.equal(proc.exitCode,1);assert.equal(listeners.length,1);assert.equal(listeners[0][0],'exit');
  proc.exitCode=0;listeners[0][1](0);assert.equal(proc.exitCode,1);
});
// Actual pinned temp-file 3.4.0 + async-exit-hook 2.0.1 (hash-verified copies).
test('actual pinned temp-file exit hook: old catch exits 0, seam exits 1, temp root removed',{skip:!modules&&'COMICS_META_TEST_BUILDER_MODULES (pinned dependency closure) not set'},()=>{
  assert.ok(path.isAbsolute(modules));
  for(const [rel,pin] of Object.entries(PINNED))assert.equal(sha(fs.readFileSync(path.join(modules,rel))),pin,'pinned vendor bytes '+rel);
  const body="const {TmpDir}=require(path.join(MODULES,'temp-file'));\n"+
    "async function main(){const t=new TmpDir('probe');const f=await t.getTempFile({suffix:'probe'});fs.writeFileSync(f,'x');process.stdout.write(JSON.stringify({tempBase:path.dirname(f)})+'\\n');if(mode==='success')return;throw new Error('synthetic builder failure');}\n";
  for(const [mode,status] of [['control',0],['seam',1],['success',0]]){
    const dir=fixtureDir();
    try{
      const result=run(dir,body,mode);
      assert.equal(result.status,status,mode+' native exit');
      const tempBase=JSON.parse(result.stdout.split('\n').find(line=>line.startsWith('{'))).tempBase;
      assert.equal(path.dirname(path.resolve(tempBase)).toLowerCase(),path.resolve(dir).toLowerCase(),'vendor temp root inside fixture');
      assert.equal(fs.existsSync(tempBase),false,mode+': vendor async cleanup removed its temp root');
    }finally{fs.rmSync(dir,{recursive:true});}
  }
});
