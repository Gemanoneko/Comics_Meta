'use strict';
const {EventEmitter}=require('node:events');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
// The pause cap for quit and install (DesktopShell spec §3). The install timeout banner reads its minutes from here.
const PAUSE_LIMIT_MS=600000;
class GracefulStop extends EventEmitter {
  constructor(engine){super();this.engine=engine;this.busy=false;this.cancelled=false;this.forced=false;this.stage='idle';}
  cancel(){if(this.busy && this.stage!=='closing')this.cancelled=true;}
  force(){if(this.busy && this.mode==='quit')this.forced=true;}
  async run(mode='quit') {
    if(this.busy)return false;
    this.busy=true;this.mode=mode;this.cancelled=false;this.forced=false;
    const start=Date.now();let pausedAt=null;let failures=0;
    try {
      if(!this.engine.ready){if(mode==='install')throw Error('Engine unavailable');await this.engine.forceStop();return true;}
      const initial=await this.engine.call('/api/shell/status');
      if(initial.setup && !initial.setup.configured){await this.engine.stop({timeoutMs:10000});return true;}
      await this.engine.call('/api/shell/pause',{});
      while(true){
        if(this.cancelled){await this.engine.call('/api/shell/cancel-pause',{});return false;}
        if(mode==='install' && Date.now()-start>=PAUSE_LIMIT_MS)throw Object.assign(Error('Pause and install timed out; installation was not started'),{code:'PAUSE_TIMEOUT'});
        if(this.forced || (mode==='quit' && Date.now()-start>=PAUSE_LIMIT_MS)){await this.engine.forceStop();return true;}
        let status;
        try{status=await this.engine.call('/api/shell/status');failures=0;await this.engine.call('/api/shell/pause',{});}catch(error){
          if(mode==='install')throw error;
          if(++failures>=2){await this.engine.forceStop();return true;}
          await sleep(500);continue;
        }
        const control=status.control;this.stage=control.phase==='paused'?'gpu':'pausing';
        if(this.stage==='gpu' && pausedAt===null)pausedAt=Date.now();
        if(control.phase==='paused' && (control.gpu_released || control.error)){
          this.stage='closing';this.emit('stage',{stage:'closing',mode,control,elapsed:Date.now()-start});
          await this.engine.stop({timeoutMs:Math.max(1,PAUSE_LIMIT_MS-(Date.now()-start))});return true;
        }
        if(Date.now()-start>=1500)this.emit('stage',{stage:this.stage,mode,control,elapsed:Date.now()-start,gpuElapsed:pausedAt?Date.now()-pausedAt:0});
        await sleep(500);
      }
    } catch(error) {
      try{if(this.engine.ready)await this.engine.call('/api/shell/cancel-pause',{});}catch{}
      throw error;
    } finally {this.busy=false;this.stage='idle';this.emit('finished');}
  }
}
module.exports={GracefulStop,PAUSE_LIMIT_MS};
