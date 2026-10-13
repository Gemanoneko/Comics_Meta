'use strict';
const {EventEmitter}=require('node:events');
const fs=require('node:fs/promises');
const {createReadStream}=require('node:fs');
const crypto=require('node:crypto');
const {spawn}=require('node:child_process');
const path=require('node:path');
class Updates extends EventEmitter {
  constructor({updater,stopper,engine,log,exit,qaInstallDirectory}){
    super();Object.assign(this,{updater,stopper,engine,log,exit,qaInstallDirectory});this.state={phase:'idle',check:'idle',dismissed:false};this.info=null;this.file=null;this.operation=null;
    updater.autoDownload=false;updater.autoInstallOnAppQuit=false;updater.allowDowngrade=false;
    updater.on('update-available',info=>{this.info=info;this.patch({phase:this.file?'ready':'available',version:info.version,check:'idle',dismissed:false});});
    updater.on('update-not-available',()=>{this.patch({check:'current'});setTimeout(()=>this.patch({check:'idle'}),5000);});
    let lastProgress=0;
    updater.on('download-progress',progress=>{if(Date.now()-lastProgress<500)return;lastProgress=Date.now();this.patch({phase:'downloading',percent:Math.max(0,Math.min(100,Math.floor(progress.percent)))});});
    updater.on('update-downloaded',info=>{this.info=info;this.file=info.downloadedFile;this.patch({phase:'ready',version:info.version,dismissed:false});});
    updater.on('error',error=>{this.log(error);});
  }
  patch(values){Object.assign(this.state,values);this.emit('state',this.state);}
  async check(manual=false){
    if(this.operation || this.stopper.busy)return;
    if(manual)this.patch({dismissed:false,check:'checking'});
    this.operation='check';
    try{await this.updater.checkForUpdates();if(this.file)this.patch({phase:'ready',dismissed:false,check:'idle'});}catch(error){this.log(error);this.patch({check:'idle',...(manual?{phase:'check-failed',dismissed:false}:{})});}finally{this.operation=null;}
  }
  async download(){
    if(this.operation || this.stopper.busy || !this.info)return;
    this.operation='download';this.patch({phase:'downloading',percent:0,dismissed:false});
    try{const files=await this.updater.downloadUpdate();this.file=files[0];await this.verify();this.patch({phase:'ready'});}catch(error){this.log(error);this.file=null;this.patch({phase:error.code==='DAMAGED'?'damaged':'download-failed'});}finally{this.operation=null;}
  }
  async verify(){
    if(!this.file || !this.info)throw Object.assign(Error('Missing verified download'),{code:'DAMAGED'});
    const stat=await fs.lstat(this.file);if(!stat.isFile() || stat.isSymbolicLink() || !stat.size || stat.size>2*1024**3)throw Object.assign(Error('Invalid installer file'),{code:'DAMAGED'});
    const expected=(this.info.files||[]).find(file=>String(file.url).endsWith('.exe')) || this.info;
    if(typeof expected.sha512!=='string' || (expected.size!==undefined && stat.size!==expected.size))throw Object.assign(Error('Missing installer integrity'),{code:'DAMAGED'});
    const digest=crypto.createHash('sha512');for await(const chunk of createReadStream(this.file))digest.update(chunk);
    if(digest.digest('base64')!==expected.sha512)throw Object.assign(Error('Installer digest mismatch'),{code:'DAMAGED'});
  }
  confirm(){if(this.state.phase==='ready' && !this.operation)this.patch({phase:'confirm'});}
  cancelConfirm(){if(this.state.phase==='confirm')this.patch({phase:'ready'});}
  dismiss(){if(!['downloading','confirm','installing'].includes(this.state.phase))this.patch({dismissed:true});}
  async install(){
    if(this.operation || this.state.phase!=='confirm')return;
    this.operation='install';this.patch({phase:'ready'});
    try{
      await this.verify();
      if(!await this.stopper.run('install'))return;
      // The fixed per-user NSIS contract is launched only after all engine
      // workers/browser descendants have exited. Observe spawn before quitting
      // so a startup error can restore the earlier engine and user-pause state.
      await this.verify();
      const args=['--updated','/S','--force-run'];
      if(this.qaInstallDirectory)args.push('/D='+this.qaInstallDirectory);
      const installer=spawn(this.file,args,{windowsHide:true,stdio:'ignore',detached:false,env:{...process.env}});
      await new Promise((resolve,reject)=>{installer.once('spawn',resolve);installer.once('error',reject);});
      installer.unref();this.patch({phase:'installing'});this.exit();
    }catch(error){
      this.log(error);
      if(!this.engine.ready){try{await this.engine.start();}catch(restartError){this.log(restartError);}}
      this.patch({phase:error.code==='DAMAGED'?'damaged':'installer-failed',dismissed:false});
    }finally{this.operation=null;}
  }
  async retry(){if(this.state.phase==='check-failed')return this.check(true);if(this.state.phase==='installer-failed'){this.patch({phase:'confirm'});return this.install();}return this.download();}
}
module.exports={Updates};
