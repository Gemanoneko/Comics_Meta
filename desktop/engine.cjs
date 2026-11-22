'use strict';
const {spawn}=require('node:child_process');
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const net=require('node:net');
const {EventEmitter}=require('node:events');
// Broker exit codes that report its whole Job empty (engine_host.py): the engine's own 0/75, 126 for any other
// engine exit, 125 for a forced stop; and 123, a start the broker refused because a previous session's part still
// runs (PREVIOUS_CLOSING): it created nothing, so there is nothing to wait for (Judy's Quit spec rev 2, R4 item 5).
const CONFIRMED_EXIT=[0,75,123,125,126];
// Parts still ran after the broker's whole closure wait (engine_host.py CLOSURE_LEFTOVER). The broker named them in
// locks/leftover-<owner>.json; the shell never confirms closure over this code (code review v0.6.6 T1), but it no
// longer refuses Quit or Retry over it either: the next broker re-checks the record before it starts anything.
const LEFTOVER_EXIT=124;
const PREVIOUS_CLOSING_EXIT=123;
// One wait for a forced stop, in seconds (Sergei 2026-11-18; Judy's Quit spec rev 2, R4 item 2): the broker
// re-terminates its Job for up to this long before it records what is left (engine_host.py --closure-wait), the shell
// waits one second more for its answer (R4 item 3), and the quit dialog names the number.
const CLOSURE_WAIT_S=30;
class Engine extends EventEmitter {
  constructor({resources,state,locks,port,log}) {super();Object.assign(this,{resources,state,locks,port,log});this.token=crypto.randomBytes(32).toString('hex');this.child=null;this.owner=null;this.ready=false;this.starting=null;this.stopping=null;this.stopGeneration=0;this.closureWaitMs=10000;this.closureWaitS=CLOSURE_WAIT_S;}
  async call(endpoint,body) {
    if(!this.child || this.child.exitCode!==null)throw Error('Owned engine unavailable');
    const url='http://127.0.0.1:'+this.port;
    const response=await fetch(url+endpoint,{method:body===undefined?'GET':'POST',signal:AbortSignal.timeout(2500),headers:{'X-ComicsMeta-Shell':this.token,...(body===undefined?{}:{Origin:url,'Content-Type':'application/json'})},...(body===undefined?{}:{body:JSON.stringify(body)})});
    const payload=await response.json();
    if(!response.ok)throw Object.assign(Error('Owned engine request refused (HTTP '+response.status+')'),{payload});
    return payload;
  }
  async start() {
    if(this.starting)return this.starting;
    this.starting=this.startOwned();
    try{return await this.starting;}finally{this.starting=null;}
  }
  async startOwned() {
    let generation=this.stopGeneration;
    if(this.child){
      if(this.ready)return this.call('/api/shell/status');
      // The generation is read as soon as this start's own forceStop has begun, not after it ends: a tray Quit during
      // its closure wait (up to 10 s since 0.6.6) shares that promise and moves the generation on, and must cancel
      // this start. Read afterwards, it let Retry start a broker as the shell exited (code review v0.6.6 t1).
      const pending=this.forceStop();generation=this.stopGeneration;await pending;
    }
    this.ready=false;
    await new Promise((resolve,reject)=>{const probe=net.createServer();probe.once('error',()=>reject(Object.assign(Error('Port occupied'),{code:'PORT_BUSY'})));probe.listen(this.port,'127.0.0.1',()=>probe.close(resolve));});
    if(generation!==this.stopGeneration)throw Object.assign(Error('Engine start cancelled'),{code:'START_CANCELLED'});
    const python=path.join(this.resources,'runtime','python','python.exe');
    const host=path.join(this.resources,'engine','engine_host.py');
    for(const file of [python,host])if(!fs.existsSync(file))throw Object.assign(Error('Runtime missing'),{code:'RUNTIME_MISSING'});
    fs.mkdirSync(this.state,{recursive:true});fs.mkdirSync(path.dirname(this.log),{recursive:true});
    const out=fs.openSync(this.log,'a');
    // PYTHONDONTWRITEBYTECODE reaches every descendant (supervisor workers too): no __pycache__ may
    // appear in the installed runtime, whose closure the next update verifies (0.2.2->0.2.3 failure).
    // PYTHONUTF8 reaches them the same way (0.6.10): the broker, app.py and both workers run in UTF-8 mode, so their
    // standard streams (this log) take any file name. Since 0.6.7 a worker has real standard handles, and its cp1251
    // stdout could not encode a name with U+00B2 (superscript two), which stopped the batch. Every launch in the tree
    // (engine_host.py, supervisor.py) must stay free of -I and -E: either makes Python ignore the variable.
    const owner=this.owner=crypto.randomBytes(32).toString('hex');
    try {this.child=spawn(python,['-B',host,'--parent-pid',String(process.pid),'--port',String(this.port),'--closure-wait',String(this.closureWaitS)],{cwd:path.dirname(host),windowsHide:true,stdio:['pipe',out,out],env:{...process.env,PYTHONDONTWRITEBYTECODE:'1',PYTHONUTF8:'1',COMICS_META_STATE_ROOT:this.state,COMICS_META_LOCK_DIR:this.locks,COMICS_META_SHELL_TOKEN:this.token,COMICS_META_CLAIM_OWNER:owner,COMICS_META_7ZIP:path.join(this.resources,'runtime','7zip','7z.exe')}});}finally{fs.closeSync(out);}
    // A private authenticated owner stream supplements the held PID handle.
    // EOF proves this exact shell is gone even if Windows reuses its PID.
    // Only the current broker's exit changes the engine's state (code review v0.6.7 Q3). Since 0.6.7 a forced stop
    // gives up after the closure wait + 1 s and Retry starts a new broker beside a frozen one; that old broker's late
    // exit marked the new, healthy engine not ready, and the auto-restart then force-stopped it mid-write.
    const child=this.child;
    child.once('exit',(code)=>{if(this.child!==child)return;const wasReady=this.ready;this.ready=false;this.emit('exit',code,wasReady);});
    this.child.once('error',error=>this.emit('engine-error',error));
    if(!this.child.pid){this.child=null;throw Object.assign(Error('Engine process could not be started'),{code:'ENGINE_EXIT'});}
    if(!this.child.stdin){throw Object.assign(Error('Engine control unavailable'),{code:'ENGINE_EXIT'});}
    this.child.stdin.on('error',error=>this.emit('engine-error',error));
    this.child.stdin.write(this.token+'\n');
    // The observed competing catalog workload took 122.6 s. Give initialization
    // 600 s overall, but do not let an absent or stalled endpoint wait that long.
    const budgetMs=600000,reachabilityMs=20000,started=performance.now();
    let lastResponse=started,lastPhase='';
    try{
      while(performance.now()-started<budgetMs){
        // 123: the broker started nothing because a previous session's part still runs (Judy's Quit spec rev 2, R2).
        if(this.child.exitCode===PREVIOUS_CLOSING_EXIT&&this.child.signalCode==null)throw Object.assign(Error('The previous session is still closing'),{code:'PREVIOUS_CLOSING',leftoverSince:this.leftoverSince()});
        if(this.child.exitCode!==null||this.child.signalCode!=null)throw Object.assign(Error('Engine exited'),{code:this.child.exitCode===75?'LIBRARY_BUSY':'ENGINE_EXIT'});
        let status;try{status=await this.call('/api/shell/startup');}catch{}
        if(status?.owned&&['starting','catalog','control','library','service','ready','failed'].includes(status.phase)){lastResponse=performance.now();if(status.phase!==lastPhase){lastPhase=status.phase;this.emit('startup-phase',status.phase);}if(status.phase==='failed')throw Object.assign(Error('Engine initialization failed'),{code:status.error==='LIBRARY_BUSY'?'LIBRARY_BUSY':'STARTUP_FAILED'});if(status.phase==='ready'){this.ready=true;return status;}}
        if(performance.now()-lastResponse>=reachabilityMs)throw Object.assign(Error('Engine startup endpoint did not respond'),{code:'START_UNRESPONSIVE',budgetMs:reachabilityMs});
        await new Promise(resolve=>setTimeout(resolve,500));
      }
      throw Object.assign(Error('Engine start timed out'),{code:'START_TIMEOUT',budgetMs});
    }catch(error){
      // The start's own failure is what the screen reports. A part left running is recorded by this forced stop,
      // and the next start's broker re-checks it (Sergei 2026-11-18); until 0.6.7 an unconfirmed closure here became
      // its own failure and blocked every later start.
      if(error.code!=='PREVIOUS_CLOSING')this.emit('startup-phase','stopping');  // 123: nothing was started, so nothing to stop.
      await this.forceStop();
      throw error;
    }
  }
  async stop({timeoutMs=600000}={}) {
    if(!this.child || this.child.exitCode!==null)return;
    const child=this.child;
    await this.call('/api/quit',{});
    const code=await new Promise((resolve,reject)=>{if(child.exitCode!==null)return resolve(child.exitCode);const timer=setTimeout(()=>reject(Error('Owned engine stop timed out')),timeoutMs);child.once('exit',value=>{clearTimeout(timer);resolve(value);});child.once('error',error=>{clearTimeout(timer);reject(error);});});
    if(code!==0)throw Error('Owned engine stop was not confirmed');
  }
  async forceStop() {
    this.stopGeneration++;
    if(this.stopping)return this.stopping;
    this.stopping=this.forceStopOwned();
    try{return await this.stopping;}finally{this.stopping=null;}
  }
  // Resolves true when the engine's closure is confirmed and false when it is not; it never refuses (Quit always
  // closes the app, Sergei 2026-11-18). Unconfirmed, a leftover record names the engine for the next start's broker,
  // which refuses to start anything beside a part that still runs (engine_host.py previous_session_closing). It
  // resolves within closureWaitS + 1 s even when the broker never answers (Judy's Quit spec rev 2, R4 item 3).
  async forceStopOwned() {
    const child=this.child,owner=this.owner;if(!child)return true;
    const deadline=performance.now()+(this.closureWaitS+1)*1000;
    if(child.exitCode===null&&child.signalCode==null){
      // Ask the native broker to terminate and confirm its whole private Job. Killing only the broker would observe
      // root exit before descendant closure. Without the owner stream the broker forces itself when the stream ends.
      if(child.stdin?.writable)child.stdin.write('force\n');
      await new Promise(resolve=>{if(child.exitCode!==null||child.signalCode!=null)return resolve();const timer=setTimeout(resolve,deadline-performance.now());const done=()=>{clearTimeout(timer);resolve();};child.once('exit',done);child.once('error',done);});
    }
    if(child.signalCode==null&&CONFIRMED_EXIT.includes(child.exitCode))return true;
    // The broker ended without reporting: ended from outside (exit code 1, as an outside kill ends it), a crash, or a
    // failure before its Job held anything or after it proved the Job empty (exit code 1 too). Its Job is
    // kill-on-close and only the broker held a handle to it, so Windows ends the whole tree with the broker; closure
    // is claimed once the shell sees that itself (treeEnded, TrayQA v0.6.4 finding 2), within what is left of the wait.
    if(child.exitCode!==null&&child.exitCode!==LEFTOVER_EXIT&&child.signalCode==null&&await this.treeEnded(Math.min(this.closureWaitMs,Math.max(0,deadline-performance.now()))))return true;
    this.recordLeftover(owner);
    return false;
  }
  recordLeftover(owner=this.owner) {
    // The broker writes its own record, with every live member, when it can (exit 124). The shell only fills in a
    // record without a process list when there is none: the broker ended without one, or has not answered (it then
    // replaces this record with its own, or removes it once it proves its Job empty). Checked by the engine's claims.
    if(!/^[0-9a-f]{64}$/.test(owner||''))return;
    try{fs.mkdirSync(this.locks,{recursive:true});fs.writeFileSync(path.join(this.locks,'leftover-'+owner+'.json'),JSON.stringify({schema:1,owner,written:Date.now()/1000,members:null,source:'shell'}),{flag:'wx'});}
    catch(error){if(error.code!=='EEXIST')this.emit('engine-error',error);}
  }
  leftoverSince() {
    // The oldest leftover record's own write time (ms), else its file time; null when none can be read. The startup
    // screen's "restart your PC" line counts from it (R4 item 4).
    let names;try{names=fs.readdirSync(this.locks);}catch{return null;}
    let oldest=null;
    for(const name of names){
      if(!/^leftover-.*.json$/.test(name))continue;const file=path.join(this.locks,name);let time=null;
      try{const written=JSON.parse(fs.readFileSync(file,'utf8'))?.written;if(Number.isFinite(written)&&written>0)time=written*1000;}catch{}
      if(time===null)try{time=fs.statSync(file).mtimeMs;}catch{}
      if(time!==null&&(oldest===null||time<oldest))oldest=time;
    }
    return oldest;
  }
  async treeEnded(waitMs=this.closureWaitMs) {
    // Seen within waitMs: the engine port is free (the dashboard server is gone) and none of this engine's
    // library claims is still held (every process that can change the library holds one: engine-<owner>-<pid>-<id>,
    // library_lock.acquire). A missing claims folder means no claim: it cannot be removed while a claim is held.
    // Anything unreadable is not proof.
    if(!/^[0-9a-f]{64}$/.test(this.owner||''))return false;
    const until=performance.now()+waitMs;
    while(true){
      if(this.claimHoldersEnded()&&await this.portFree())return true;
      if(performance.now()>=until)return false;
      await new Promise(resolve=>setTimeout(resolve,200));
    }
  }
  claimHoldersEnded() {
    // A claim is held while its holder keeps byte 0 of <claim>.lock locked (file_lock: a mandatory byte-range lock,
    // so reading that byte fails with EBUSY). That is the claim itself; until 0.6.7 the PID in the claim's name was
    // asked instead, and Windows may give a dead holder's PID to another process (code review v0.6.6 t2). The lock
    // also stays held until an ended holder's handles are closed.
    const folder=path.join(this.locks,'claims');let names;
    try{names=fs.readdirSync(folder);}catch(error){return error.code==='ENOENT';}
    const claim=new RegExp('^(engine-'+this.owner+'-(\\d+)-[0-9a-f]{12})\\.(?:lock|json)$'),claims=new Map();
    for(const name of names){const match=claim.exec(name);if(match)claims.set(match[1],Number(match[2]));}
    for(const [stem,pid] of claims){
      // The record is written after the lock is taken, so it is looked for first: with it, a free lock is proof.
      // Without it, the claimant may be between creating its .lock and locking it, so its named PID counts too.
      const recorded=fs.existsSync(path.join(folder,stem+'.json'));
      const lock=lockState(path.join(folder,stem+'.lock'));
      if(lock==='missing')continue;  // Released: the .lock is created first and removed first.
      if(lock!=='free')return false;  // Held, or unreadable: not proof.
      if(!recorded&&pidAlive(pid))return false;
    }
    return true;
  }
  portFree() {
    return new Promise(resolve=>{const probe=net.createServer();probe.once('error',()=>resolve(false));probe.listen(this.port,'127.0.0.1',()=>probe.close(()=>resolve(true)));});
  }
}
function lockState(file) {
  let fd;
  try{fd=fs.openSync(file,'r');}catch(error){return error.code==='ENOENT'?'missing':'unreadable';}
  try{fs.readSync(fd,Buffer.alloc(1),0,1,0);return 'free';}catch(error){return error.code==='EBUSY'?'held':'unreadable';}
  finally{fs.closeSync(fd);}
}
function pidAlive(pid) {
  try{process.kill(pid,0);return true;}catch(error){return error.code!=='ESRCH';}  // Only "no such process" is proof.
}
module.exports={Engine,CLOSURE_WAIT_S};
