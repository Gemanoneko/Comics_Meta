'use strict';
const {EventEmitter}=require('node:events');
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
// The pause cap for quit and install (DesktopShell spec §3). The install timeout banner reads its minutes from here.
const PAUSE_LIMIT_MS=600000;
class GracefulStop extends EventEmitter {
  constructor(engine){super();this.engine=engine;this.busy=false;this.cancelled=false;this.forced=false;this.stage='idle';this.ending=null;}
  cancel(){if(this.busy && !['closing','ending'].includes(this.stage))this.cancelled=true;}
  // Quit now: the dialog switches to the ending state in the same frame and the forced stop starts at once, not at the
  // next status poll (Judy's Quit spec rev 2, R1 and check 3).
  force(){if(this.busy && this.mode==='quit' && !['closing','ending'].includes(this.stage)){this.forced=true;this.end().catch(()=>{});}}
  // Quit always ends the process (Sergei 2026-11-18; ProcessRules § Desktop App / GUI Rules). Every quit path that does
  // not end gracefully ends here: the 'ending' stage is announced once, before the forced stop starts, and no other
  // stage follows it (R4 item 1). The forced stop resolves within the engine's closure wait + 1 s and never refuses.
  announceEnding(){if(this.stage!=='ending'){this.stage='ending';this.emit('stage',{stage:'ending',mode:this.mode});}}
  end(){this.announceEnding();this.ending??=this.engine.forceStop();return this.ending.then(()=>true);}
  async run(mode='quit') {
    if(this.busy)return false;
    this.busy=true;this.mode=mode;this.cancelled=false;this.forced=false;this.ending=null;this.stage='idle';
    const start=Date.now();let pausedAt=null;let failures=0;
    try {
      if(!this.engine.ready){if(mode==='install')throw Error('Engine unavailable');return await this.end();}
      const initial=await this.engine.call('/api/shell/status');
      if(initial.setup && !initial.setup.configured){
        if(mode==='install'){await this.engine.stop({timeoutMs:10000});return true;}
        // The setup page pauses nothing: its stop is the whole wait, shown as the ending state (R1, R4 item 1).
        this.announceEnding();
        try{await this.engine.stop({timeoutMs:10000});return true;}catch{return await this.end();}
      }
      await this.engine.call('/api/shell/pause',{});
      while(true){
        if(this.forced)return await this.end();
        if(this.cancelled){await this.engine.call('/api/shell/cancel-pause',{});return false;}
        if(mode==='install' && Date.now()-start>=PAUSE_LIMIT_MS)throw Object.assign(Error('Pause and install timed out; installation was not started'),{code:'PAUSE_TIMEOUT'});
        if(mode==='quit' && Date.now()-start>=PAUSE_LIMIT_MS)return await this.end();
        let status;
        try{status=await this.engine.call('/api/shell/status');failures=0;await this.engine.call('/api/shell/pause',{});}catch(error){
          if(mode==='install')throw error;
          if(this.forced || ++failures>=2)return await this.end();
          await sleep(500);continue;
        }
        if(this.forced)return await this.end();  // Quit now during the status call: no stage after the ending.
        const control=status.control;this.stage=control.phase==='paused'?'gpu':'pausing';
        if(this.stage==='gpu' && pausedAt===null)pausedAt=Date.now();
        if(control.phase==='paused' && (control.gpu_released || control.error)){
          this.stage='closing';this.emit('stage',{stage:'closing',mode,control,elapsed:Date.now()-start});
          const left=Math.max(1,PAUSE_LIMIT_MS-(Date.now()-start));
          if(mode==='install'){await this.engine.stop({timeoutMs:left});return true;}
          // Judy's R6 item 1: "Closing…" has no buttons, so it may last no longer than the one closure wait; then the
          // forced path (the ending state), so Quit always ends. Paused covers the workers only: a manual Approve begun
          // before Quit may still be writing and be stopped here; the engine's next start finishes or undoes that
          // write from its pending-write record (code review v0.6.7 Q2, app.recover_interrupted_write).
          try{await this.engine.stop({timeoutMs:Math.min(this.engine.closureWaitS*1000,left)});return true;}
          catch{return await this.end();}
        }
        if(Date.now()-start>=1500)this.emit('stage',{stage:this.stage,mode,control,elapsed:Date.now()-start,gpuElapsed:pausedAt?Date.now()-pausedAt:0});
        await sleep(500);
      }
    } catch(error) {
      if(mode==='quit')return await this.end();  // The error path: the ending state, then the forced stop (R1).
      try{if(this.engine.ready)await this.engine.call('/api/shell/cancel-pause',{});}catch{}
      throw error;
    } finally {this.busy=false;this.stage='idle';this.emit('finished');}
  }
}
module.exports={GracefulStop,PAUSE_LIMIT_MS};
