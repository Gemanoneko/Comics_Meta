'use strict';
const {EventEmitter}=require('node:events');
const fs=require('node:fs/promises');
const {createReadStream}=require('node:fs');
const crypto=require('node:crypto');
const {launchInstaller}=require('./installer-launch.cjs');
const path=require('node:path');
class Updates extends EventEmitter {
  constructor({updater,stopper,engine,log,exit,qaInstallDirectory,qaArtifact,launch=launchInstaller,record=()=>{}}){
    super();Object.assign(this,{updater,stopper,engine,log,exit,qaInstallDirectory,qaArtifact,launch,record});this.state={phase:'idle',check:'idle',dismissed:false};this.info=null;this.file=null;this.fileIdentity=null;this.operation=null;
    updater.autoDownload=false;updater.autoInstallOnAppQuit=false;updater.allowDowngrade=false;
    updater.on('update-available',info=>{try{this.validateInfo(info);}catch(error){this.log(error);this.info=null;this.file=null;this.fileIdentity=null;this.patch({phase:'check-failed',check:'idle',dismissed:false});return;}const identity=this.identity(info);if(this.fileIdentity!==identity){this.file=null;this.fileIdentity=null;}this.info=structuredClone(info);this.patch({phase:this.file?'ready':'available',version:info.version,check:'idle',dismissed:false});});
    updater.on('update-not-available',()=>{this.info=null;this.file=null;this.fileIdentity=null;this.patch({phase:'idle',check:'current'});setTimeout(()=>this.patch({check:'idle'}),5000);});
    let lastProgress=0;
    updater.on('download-progress',progress=>{if(Date.now()-lastProgress<500)return;lastProgress=Date.now();this.patch({phase:'downloading',percent:Math.max(0,Math.min(100,Math.floor(progress.percent)))});});
    // The download promise performs integrity validation before publishing Ready.
    updater.on('update-downloaded',info=>{if(this.operation==='download'&&this.identity(info)===this.identity(this.info))this.file=info.downloadedFile;});
    updater.on('error',error=>{this.log(error);});
  }
  validateInfo(info){
    if(!info||typeof info.version!=='string'||!/^\d+\.\d+\.\d+$/.test(info.version)||!Array.isArray(info.files))throw Object.assign(Error('Invalid update metadata'),{code:'DAMAGED'});
    const installers=info.files.filter(item=>typeof item.url==='string'&&item.url.endsWith('.exe'));
    if(installers.length!==1)throw Object.assign(Error('Invalid installer metadata'),{code:'DAMAGED'});
    const file=installers[0];const digest=typeof file.sha512==='string'?Buffer.from(file.sha512,'base64'):Buffer.alloc(0);
    if(digest.length!==64||digest.toString('base64')!==file.sha512||!Number.isSafeInteger(file.size)||file.size<1||file.size>2*1024**3)throw Object.assign(Error('Invalid installer integrity'),{code:'DAMAGED'});
    if(this.qaArtifact&&(info.version!==this.qaArtifact.version||path.basename(new URL(file.url,'http://127.0.0.1/').pathname)!==this.qaArtifact.name||file.size!==this.qaArtifact.size||file.sha512!==this.qaArtifact.sha512))throw Object.assign(Error('Private QA artifact identity differs'),{code:'DAMAGED'});
    return file;
  }
  identity(info){const file=(info?.files||[]).find(item=>String(item.url).endsWith('.exe'));return JSON.stringify([info?.version,file?.url,file?.sha512,file?.size]);}
  patch(values){Object.assign(this.state,values);this.emit('state',this.state);}
  async check(manual=false){
    if(this.operation || this.stopper.busy || this.state.phase==='installer-uncertain')return;
    if(manual)this.patch({dismissed:false,check:'checking'});
    this.operation='check';
    try{await this.updater.checkForUpdates();if(this.file)this.patch({phase:'ready',dismissed:false,check:'idle'});}catch(error){this.log(error);this.patch({check:'idle',...(manual?{phase:'check-failed',dismissed:false}:{})});}finally{this.operation=null;}
  }
  async download(){
    if(this.operation || this.stopper.busy || !this.info)return;
    const downloadIdentity=this.identity(this.info);this.validateInfo(this.info);this.operation='download';this.patch({phase:'downloading',percent:0,dismissed:false});
    try{const files=await this.updater.downloadUpdate();if(downloadIdentity!==this.identity(this.info))throw Object.assign(Error('Update changed during download'),{code:'DAMAGED'});this.file=files[0];this.fileIdentity=downloadIdentity;await this.verify();this.patch({phase:'ready'});}catch(error){this.log(error);this.file=null;this.fileIdentity=null;this.patch({phase:error.code==='DAMAGED'?'damaged':'download-failed'});}finally{this.operation=null;}
  }
  async verify(){
    if(!this.file || !this.info || this.fileIdentity!==this.identity(this.info))throw Object.assign(Error('Missing verified download'),{code:'DAMAGED'});
    const stat=await fs.lstat(this.file);if(!stat.isFile() || stat.isSymbolicLink() || !stat.size || stat.size>2*1024**3)throw Object.assign(Error('Invalid installer file'),{code:'DAMAGED'});
    const expected=this.validateInfo(this.info);
    if(typeof expected.sha512!=='string' || (expected.size!==undefined && stat.size!==expected.size))throw Object.assign(Error('Missing installer integrity'),{code:'DAMAGED'});
    const digest=crypto.createHash('sha512');for await(const chunk of createReadStream(this.file))digest.update(chunk);
    if(digest.digest('base64')!==expected.sha512)throw Object.assign(Error('Installer digest mismatch'),{code:'DAMAGED'});
  }
  confirm(){if(this.state.phase==='ready' && !this.operation)this.patch({phase:'confirm'});}
  cancelConfirm(){if(this.state.phase==='confirm')this.patch({phase:'ready'});}
  dismiss(){if(!['downloading','confirm','installing','installer-uncertain'].includes(this.state.phase))this.patch({dismissed:true});}
  async install(){
    if(this.operation || this.state.phase!=='confirm')return;
    this.operation='install';this.patch({phase:'ready'});let launcherInvoked=false;
    try{
      await this.verify();
      if(!await this.stopper.run('install'))return;
      // The fixed per-user NSIS contract is launched only after all engine
      // workers/browser descendants have exited. Observe spawn before quitting
      // so a startup error can restore the earlier engine and user-pause state.
      await this.verify();
      const expected=this.validateInfo(this.info);
      launcherInvoked=true;const receipt=await this.launch({python:path.join(this.engine.resources,'runtime','python','python.exe'),helper:path.join(this.engine.resources,'engine','installer_launch.py'),path:this.file,size:expected.size,sha512:expected.sha512,parent_pid:process.pid,install_dir:this.qaInstallDirectory});
      this.recordAttempt(receipt);this.patch({phase:'installing'});this.exit();
    }catch(error){
      if(!launcherInvoked)error.installerStarted=false;let restoreFailed=false;this.log(error);this.recordAttempt(error.installerReceipt||{started:error.installerStarted??null,accepted:false,phase:error.installerStarted===false?'not-started':'unknown',code:error.code||'INSTALLER_OUTCOME_UNKNOWN'});
      if(!this.engine.ready&&(error.installerStarted===false||error.code==='DAMAGED')){try{await this.engine.start();}catch(restartError){restoreFailed=true;this.log(restartError);}}
      const uncertain=error.code!=='DAMAGED'&&error.installerStarted!==false;this.patch({phase:error.code==='DAMAGED'?'damaged':uncertain?'installer-uncertain':'installer-failed',installerStarted:uncertain?error.installerStarted??null:false,restoreFailed,dismissed:false});
    }finally{this.operation=null;}
  }
  recordAttempt(receipt){try{this.record({schema:1,time:new Date().toISOString(),expectedVersion:this.info?.version||null,artifact:this.info?this.validateInfo(this.info):null,receipt});}catch(error){this.log(error);}}
  async retry(){if(this.state.phase==='installer-uncertain')return;if(this.state.phase==='check-failed')return this.check(true);if(this.state.phase==='installer-failed'){this.patch({phase:'confirm'});return this.install();}return this.download();}
}
module.exports={Updates};
