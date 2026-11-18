'use strict';
const {spawn}=require('node:child_process');
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const net=require('node:net');
const {EventEmitter}=require('node:events');
// Broker exit codes that report its whole Job empty (engine_host.py): the engine's own 0/75, 126 for any other
// engine exit, 125 for a forced stop.
const CONFIRMED_EXIT=[0,75,125,126];
class Engine extends EventEmitter {
  constructor({resources,state,locks,port,log}) {super();Object.assign(this,{resources,state,locks,port,log});this.token=crypto.randomBytes(32).toString('hex');this.child=null;this.owner=null;this.ready=false;this.starting=null;this.stopping=null;this.stopGeneration=0;this.closureWaitMs=10000;}
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
    if(this.child){
      if(this.ready)return this.call('/api/shell/status');
      await this.forceStop();
    }
    const generation=this.stopGeneration;
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
    const owner=this.owner=crypto.randomBytes(32).toString('hex');
    try {this.child=spawn(python,['-B',host,'--parent-pid',String(process.pid),'--port',String(this.port)],{cwd:path.dirname(host),windowsHide:true,stdio:['pipe',out,out],env:{...process.env,PYTHONDONTWRITEBYTECODE:'1',COMICS_META_STATE_ROOT:this.state,COMICS_META_LOCK_DIR:this.locks,COMICS_META_SHELL_TOKEN:this.token,COMICS_META_CLAIM_OWNER:owner,COMICS_META_7ZIP:path.join(this.resources,'runtime','7zip','7z.exe')}});}finally{fs.closeSync(out);}
    // A private authenticated owner stream supplements the held PID handle.
    // EOF proves this exact shell is gone even if Windows reuses its PID.
    this.child.once('exit',(code)=>{const wasReady=this.ready;this.ready=false;this.emit('exit',code,wasReady);});
    this.child.once('error',error=>this.emit('engine-error',error));
    if(!this.child.pid){this.child=null;throw Object.assign(Error('Engine process could not be started'),{code:'ENGINE_EXIT'});}
    if(!this.child.stdin){throw Object.assign(Error('Engine control unavailable'),{code:'CLOSURE_UNCONFIRMED'});}
    this.child.stdin.on('error',error=>this.emit('engine-error',error));
    this.child.stdin.write(this.token+'\n');
    // The observed competing catalog workload took 122.6 s. Give initialization
    // 600 s overall, but do not let an absent or stalled endpoint wait that long.
    const budgetMs=600000,reachabilityMs=20000,started=performance.now();
    let lastResponse=started,lastPhase='';
    try{
      while(performance.now()-started<budgetMs){
        if(this.child.exitCode!==null||this.child.signalCode!=null)throw Object.assign(Error('Engine exited'),{code:this.child.exitCode===75?'LIBRARY_BUSY':'ENGINE_EXIT'});
        let status;try{status=await this.call('/api/shell/startup');}catch{}
        if(status?.owned&&['starting','catalog','control','library','service','ready','failed'].includes(status.phase)){lastResponse=performance.now();if(status.phase!==lastPhase){lastPhase=status.phase;this.emit('startup-phase',status.phase);}if(status.phase==='failed')throw Object.assign(Error('Engine initialization failed'),{code:status.error==='LIBRARY_BUSY'?'LIBRARY_BUSY':'STARTUP_FAILED'});if(status.phase==='ready'){this.ready=true;return status;}}
        if(performance.now()-lastResponse>=reachabilityMs)throw Object.assign(Error('Engine startup endpoint did not respond'),{code:'START_UNRESPONSIVE',budgetMs:reachabilityMs});
        await new Promise(resolve=>setTimeout(resolve,500));
      }
      throw Object.assign(Error('Engine start timed out'),{code:'START_TIMEOUT',budgetMs});
    }catch(error){
      this.emit('startup-phase','stopping');
      try{await this.forceStop();}catch(closure){throw Object.assign(Error('Owned engine closure unconfirmed'),{code:'CLOSURE_UNCONFIRMED',cause:closure});}
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
  async forceStopOwned() {
    const child=this.child;if(!child)return;if(child.signalCode!=null)throw Error('Owned engine closure was not confirmed');
    if(child.exitCode===null){
      // Ask the native broker to terminate and confirm its whole private Job.
      // Killing only the broker would observe root exit before descendant closure.
      if(!child.stdin?.writable)throw Error('Owned engine control unavailable');
      child.stdin.write('force\n');
      await new Promise((resolve,reject)=>{if(child.exitCode!==null)return resolve();const timer=setTimeout(()=>reject(Error('Owned engine closure unconfirmed')),45000);child.once('exit',()=>{clearTimeout(timer);resolve();});child.once('error',error=>{clearTimeout(timer);reject(error);});});
    }
    if(CONFIRMED_EXIT.includes(child.exitCode))return;
    // The broker ended without reporting its Job empty: ended from outside (exit code 1), or its own closure check
    // failed. Before 0.6.6 only its exit code could confirm closure, so Retry and tray Quit stayed refused for good
    // (TrayQA v0.6.4 finding 2). Its Job is kill-on-close and only the broker held a handle to it, so Windows ends
    // the whole tree with the broker; closure is claimed only once the shell sees that itself (treeEnded).
    if(child.signalCode==null&&await this.treeEnded())return;
    throw Error('Owned engine closure was not confirmed');
  }
  async treeEnded() {
    // Seen within closureWaitMs: the engine port is free (the dashboard server is gone) and no process lives that
    // holds one of this engine's library claims (every process that can change the library holds one; its name
    // carries the holder's PID: engine-<owner>-<pid>-<id>, library_lock.acquire). Anything unreadable is not proof.
    if(!/^[0-9a-f]{64}$/.test(this.owner||''))return false;
    const until=performance.now()+this.closureWaitMs;
    while(true){
      if(this.claimHoldersEnded()&&await this.portFree())return true;
      if(performance.now()>=until)return false;
      await new Promise(resolve=>setTimeout(resolve,200));
    }
  }
  claimHoldersEnded() {
    let names;
    try{names=fs.readdirSync(path.join(this.locks,'claims'));}catch(error){return error.code==='ENOENT';}
    const claim=new RegExp('^engine-'+this.owner+'-(\\d+)-[0-9a-f]{12}\\.(?:lock|json)$');
    for(const name of names){
      const match=claim.exec(name);if(!match)continue;
      try{process.kill(Number(match[1]),0);return false;}catch(error){if(error.code!=='ESRCH')return false;}
    }
    return true;
  }
  portFree() {
    return new Promise(resolve=>{const probe=net.createServer();probe.once('error',()=>resolve(false));probe.listen(this.port,'127.0.0.1',()=>probe.close(()=>resolve(true)));});
  }
}
module.exports={Engine};
