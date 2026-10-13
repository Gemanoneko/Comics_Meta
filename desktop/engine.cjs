'use strict';
const {spawn}=require('node:child_process');
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const net=require('node:net');
const {EventEmitter}=require('node:events');
class Engine extends EventEmitter {
  constructor({resources,state,locks,port,log}) {super();Object.assign(this,{resources,state,locks,port,log});this.token=crypto.randomBytes(32).toString('hex');this.child=null;this.ready=false;}
  async call(endpoint,body) {
    if(!this.child || this.child.exitCode!==null)throw Error('Owned engine unavailable');
    const url='http://127.0.0.1:'+this.port;
    const response=await fetch(url+endpoint,{method:body===undefined?'GET':'POST',signal:AbortSignal.timeout(2500),headers:{'X-ComicsMeta-Shell':this.token,...(body===undefined?{}:{Origin:url,'Content-Type':'application/json'})},...(body===undefined?{}:{body:JSON.stringify(body)})});
    const payload=await response.json();
    if(!response.ok)throw Object.assign(Error('Owned engine request refused'),{payload});
    return payload;
  }
  async start() {
    if(this.child && this.child.exitCode===null)return;
    this.ready=false;
    await new Promise((resolve,reject)=>{const probe=net.createServer();probe.once('error',()=>reject(Object.assign(Error('Port occupied'),{code:'PORT_BUSY'})));probe.listen(this.port,'127.0.0.1',()=>probe.close(resolve));});
    const python=path.join(this.resources,'runtime','python','python.exe');
    const host=path.join(this.resources,'engine','engine_host.py');
    for(const file of [python,host])if(!fs.existsSync(file))throw Object.assign(Error('Runtime missing'),{code:'RUNTIME_MISSING'});
    fs.mkdirSync(this.state,{recursive:true});fs.mkdirSync(path.dirname(this.log),{recursive:true});
    const out=fs.openSync(this.log,'a');
    try {this.child=spawn(python,['-B',host,'--parent-pid',String(process.pid),'--port',String(this.port)],{cwd:path.dirname(host),windowsHide:true,stdio:['pipe',out,out],env:{...process.env,COMICS_META_STATE_ROOT:this.state,COMICS_META_LOCK_DIR:this.locks,COMICS_META_SHELL_TOKEN:this.token,COMICS_META_7ZIP:path.join(this.resources,'runtime','7zip','7z.exe')}});}finally{fs.closeSync(out);}
    // A private authenticated owner stream supplements the held PID handle.
    // EOF proves this exact shell is gone even if Windows reuses its PID.
    this.child.stdin.on('error',error=>this.emit('engine-error',error));
    this.child.stdin.write(this.token+'\n');
    this.child.once('exit',(code)=>{this.ready=false;this.emit('exit',code);});
    this.child.once('error',error=>this.emit('engine-error',error));
    const until=Date.now()+30000;
    while(Date.now()<until){
      if(this.child.exitCode!==null)throw Object.assign(Error('Engine exited'),{code:this.child.exitCode===75?'LIBRARY_BUSY':'ENGINE_EXIT'});
      try{const status=await this.call('/api/shell/status');if(status.owned){this.ready=true;return status;}}catch{}
      await new Promise(resolve=>setTimeout(resolve,250));
    }
    throw Object.assign(Error('Engine start timed out'),{code:'START_TIMEOUT'});
  }
  async stop({timeoutMs=600000}={}) {
    if(!this.child || this.child.exitCode!==null)return;
    const child=this.child;
    await this.call('/api/quit',{});
    const code=await new Promise((resolve,reject)=>{if(child.exitCode!==null)return resolve(child.exitCode);const timer=setTimeout(()=>reject(Error('Owned engine stop timed out')),timeoutMs);child.once('exit',value=>{clearTimeout(timer);resolve(value);});child.once('error',error=>{clearTimeout(timer);reject(error);});});
    if(code!==0)throw Error('Owned engine stop was not confirmed');
  }
  async forceStop() {
    const child=this.child;if(!child)return;if(child.exitCode!==null){if(child.exitCode===0||child.exitCode===125)return;throw Error('Owned engine closure was not confirmed');}
    // Ask the native broker to terminate and confirm its whole private Job.
    // Killing only the broker would observe root exit before descendant closure.
    if(!child.stdin?.writable)throw Error('Owned engine control unavailable');
    child.stdin.write('force\n');
    const code=await new Promise((resolve,reject)=>{if(child.exitCode!==null)return resolve(child.exitCode);const timer=setTimeout(()=>reject(Error('Owned engine closure unconfirmed')),10000);child.once('exit',value=>{clearTimeout(timer);resolve(value);});child.once('error',error=>{clearTimeout(timer);reject(error);});});
    if(code!==0&&code!==125)throw Error('Owned engine closure failed');
  }
}
module.exports={Engine};
