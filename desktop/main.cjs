'use strict';
const {app,BrowserWindow,Tray,Menu,Notification,nativeTheme,nativeImage,screen,shell,ipcMain,dialog:folderPicker}=require('electron');
const fs=require('node:fs');const path=require('node:path');
const {Engine}=require('./engine.cjs');const {GracefulStop}=require('./graceful-stop.cjs');const {Updates}=require('./updates.cjs');
const qa=process.env.COMICS_META_QA==='1';
let qaRoot=null;
if(qa){
  qaRoot=process.env.COMICS_META_QA_ROOT;
  const temp=path.resolve(process.env.TEMP||'');
  if(!qaRoot || !path.isAbsolute(qaRoot) || !path.resolve(qaRoot).startsWith(temp+path.sep))throw Error('QA root must be owned temporary output');
  qaRoot=path.resolve(qaRoot);app.setPath('userData',path.join(qaRoot,'profile'));app.setPath('cache',path.join(qaRoot,'cache'));
  const port=Number(process.env.COMICS_META_QA_PORT);if(!Number.isInteger(port)||port<1024||port>65535||port===8765)throw Error('QA must use a non-live port');
  for(let dir=qaRoot;dir!==path.dirname(dir);dir=path.dirname(dir)){if(fs.lstatSync(dir).isSymbolicLink())throw Error('QA link refused');}
}
const locked=app.requestSingleInstanceLock();
if(!locked){app.exit(0);}else{
  nativeTheme.themeSource='dark';app.setAppUserModelId('com.illuminati.comicmetadata');
  let window=null,tray=null,dialog=null,engine=null,stopper=null,updates=null,finalExit=false,polling=false,misses=0,restarts=[];
  let state={service:'starting',control:null,update:{phase:'idle',check:'idle'},stopping:null};let trayPause=false;
  const profile=app.getPath('userData');const boundsFile=path.join(profile,'window.json');
  const local=process.env.LOCALAPPDATA;if(!qa && !local)throw Error('Local app state is unavailable');
  const stateRoot=qa?path.join(qaRoot,'state'):path.join(local,'ComicsMeta');
  const logFolder=path.join(stateRoot,'logs');fs.mkdirSync(logFolder,{recursive:true});
  const log=error=>{try{fs.appendFileSync(path.join(logFolder,'desktop.log'),new Date().toISOString()+' '+String(error.stack||error)+'\n');}catch{}};
  function broadcast(){for(const target of [window,dialog])if(target&&!target.isDestroyed())target.webContents.send('shell-state',state);refreshTray();}
  function exit(){finalExit=true;if(tray)tray.destroy();app.quit();}
  function show(){if(dialog&&!dialog.isDestroyed()){if(!qa){dialog.show();dialog.focus();}return;}if(window){if(window.isMinimized())window.restore();if(!qa){window.show();window.focus();}window.webContents.send('shell-refresh');}}
  function notify(title,body,onShow){if(qa || !Notification.isSupported())return;const notice=new Notification({title,body,silent:true});notice.once('show',()=>onShow?.());notice.once('click',show);notice.show();}
  function initialBounds(){
    const work=screen.getPrimaryDisplay().workArea;const defaults={width:Math.max(640,Math.min(1280,Math.floor(work.width*.9))),height:Math.max(480,Math.min(860,Math.floor(work.height*.9)))};
    try{const saved=JSON.parse(fs.readFileSync(boundsFile,'utf8'));if(!['x','y','width','height'].every(key=>Number.isInteger(saved[key]))||saved.width<640||saved.height<480)return defaults;
      const display=screen.getAllDisplays().find(({workArea:r})=>Math.min(saved.x+saved.width,r.x+r.width)-Math.max(saved.x,r.x)>=100&&Math.min(saved.y+saved.height,r.y+r.height)-Math.max(saved.y,r.y)>=50&&saved.width<=r.width&&saved.height<=r.height);
      return display?saved:defaults;
    }catch{return defaults;}
  }
  function saveBounds(){if(!window||window.isDestroyed()||window.isMinimized())return;try{fs.mkdirSync(profile,{recursive:true});const tmp=boundsFile+'.tmp';fs.writeFileSync(tmp,JSON.stringify({...window.getNormalBounds(),maximized:window.isMaximized()}));fs.renameSync(tmp,boundsFile);}catch(error){log(error);}}
  function refreshTray(){if(!tray)return;
    const c=state.control;let label='Starting…';let icon='processing';
    if(state.stopping)label=state.stopping.mode==='install'?'Installing update…':'Quitting…';
    else if(state.service==='setup')label='Setup required';
    else if(state.service==='failed'){label='Local service not responding. Open the window for details.';icon='error';}
    else if(c?.requested){icon='paused';label=c.phase==='pausing'?'Pausing. Finishing the current operation.':c.error?'Paused. GPU release not confirmed.':c.gpu_released?'Paused. Gemma released from GPU.':'Paused. Releasing Gemma from GPU…';}
    else if(state.verification){icon='verification';label='Needs your verification: Google Lens';}else if(state.service==='ready')label='Processing enabled';
    if(!state.update.dismissed&&['available','ready','confirm'].includes(state.update.phase))label+=' · Update available';
    const image=nativeImage.createFromPath(path.join(__dirname,'assets','tray-'+icon+'.png'));if(!image.isEmpty())tray.setImage(image);
    tray.setToolTip(('Comic Metadata — '+label).slice(0,127));
    const paused=Boolean(c?.requested);const enabled=state.service==='ready'&&!stopper?.busy;
    tray.setContextMenu(Menu.buildFromTemplate([{label:'&Open',click:show},{label:paused?'&Resume processing':'&Pause && release GPU',enabled,click:async()=>{try{const fresh=await engine.call('/api/shell/status');if(Boolean(fresh.control.requested)!==paused)return;await engine.call(paused?'/api/resume':'/api/pause',{});trayPause=!paused;await poll();}catch(error){log(error);}}},{type:'separator'},{label:stopper?.busy?'Quitting…':'&Quit',enabled:!stopper?.busy,click:()=>quit()}]));
  }
  function senderAllowed(event){return [window,dialog].some(target=>target&&!target.isDestroyed()&&event.sender===target.webContents&&event.senderFrame===target.webContents.mainFrame);}
  ipcMain.handle('shell-snapshot',event=>{if(!senderAllowed(event))throw Error('Untrusted shell sender');return state;});
  ipcMain.handle('setup-status',async event=>{if(!senderAllowed(event))throw Error('Untrusted shell sender');return (await engine.call('/api/shell/status')).setup;});
  ipcMain.handle('setup-browse',async event=>{if(!senderAllowed(event)||state.service!=='setup')throw Error('Setup unavailable');const result=await folderPicker.showOpenDialog(window,{properties:['openDirectory'],title:'Choose your comic library folder'});return result.canceled?null:result.filePaths[0];});
  let saving=false;
  ipcMain.handle('setup-save',async(event,body)=>{
    if(!senderAllowed(event)||state.service!=='setup'||saving)throw Error('Setup unavailable');
    if(!body||typeof body.folder!=='string'||!body.keys||typeof body.keys!=='object')return {error:'folder_invalid'};
    saving=true;try{
      const result=await engine.call('/api/shell/setup',body);state.service='ready';state.control=(await engine.call('/api/shell/status')).control;window.loadURL('http://127.0.0.1:'+engine.port);broadcast();return result;
    }catch(error){return error.payload?.error?error.payload:{error:'save_failed'};}finally{saving=false;}
  });
  ipcMain.handle('shell-action',async(event,name)=>{if(!senderAllowed(event)||typeof name!=='string')throw Error('Untrusted shell action');
    const actions={quit:()=>quit(),retryService:()=>start(),openLogs:()=>shell.openPath(logFolder),check:()=>updates?.check(true),download:()=>updates?.download(),dismiss:()=>updates?.dismiss(),confirm:()=>updates?.confirm(),cancelConfirm:()=>updates?.cancelConfirm(),install:()=>updates?.install(),retryUpdate:()=>updates?.retry(),cancelStop:()=>stopper?.cancel(),forceQuit:()=>stopper?.force()};
    if(!Object.hasOwn(actions,name))throw Error('Unsupported shell action');return actions[name]();});
  function secure(target,allowed){target.webContents.setWindowOpenHandler(()=>({action:'deny'}));target.webContents.on('will-navigate',(event,url)=>{if(!allowed(url))event.preventDefault();});target.webContents.on('page-title-updated',event=>event.preventDefault());target.webContents.on('before-input-event',(event,input)=>{if(input.type==='keyDown'&&input.control&&!input.alt&&input.key.toLowerCase()==='q'&&!stopper?.busy&&target.isVisible()){event.preventDefault();quit();}});}
  async function quit(){if(stopper?.busy)return;trayPause=false;try{if(!stopper){exit();return;}state.stopping={mode:'quit'};broadcast();if(await stopper.run('quit'))exit();}catch(error){log(error);await engine?.forceStop();exit();}finally{state.stopping=null;broadcast();}}
  function stoppingDialog(value){state.stopping=value;if(!dialog){
    if(!qa)window.showInactive();dialog=new BrowserWindow({parent:window,modal:true,width:440,resizable:false,minimizable:false,maximizable:false,show:false,backgroundColor:'#1b202b',webPreferences:{preload:path.join(__dirname,'preload.cjs'),contextIsolation:true,nodeIntegration:false,sandbox:true,offscreen:qa}});
    dialog.setMenu(null);secure(dialog,url=>url.startsWith('file://'));dialog.loadFile(path.join(__dirname,'stopping.html'));dialog.once('ready-to-show',()=>{if(!qa)dialog.show();broadcast();});dialog.on('close',event=>{if(stopper.busy){event.preventDefault();stopper.cancel();}});
  }broadcast();}
  async function poll(){if(polling||!engine?.ready)return;polling=true;try{const fresh=await engine.call('/api/shell/status');misses=0;state.service=fresh.setup?.configured?'ready':'setup';state.control=fresh.control;state.verification=fresh.verification;
    if(trayPause&&!fresh.control.requested)trayPause=false;
    if(trayPause&&fresh.control.phase==='paused'&&(fresh.control.gpu_released||fresh.control.error)){trayPause=false;if(!stopper.busy&&!(window.isVisible()&&window.isFocused()))notify('Comic Metadata',fresh.control.error?'Paused. GPU release not confirmed.':'Paused. Gemma released from GPU.');}
  }catch(error){log(error);if(++misses>=3)state.service='failed';}finally{polling=false;broadcast();}}
  async function start(){if(stopper?.busy)return;state.service='starting';state.failure=null;broadcast();try{const initial=await engine.start();state.service=initial.setup?.configured?'ready':'setup';if(state.service==='setup')window.loadFile(path.join(__dirname,'setup.html'));else window.loadURL('http://127.0.0.1:'+engine.port);await poll();}catch(error){log(error);state.service='failed';state.failure=error.code||'ENGINE_EXIT';await engine.forceStop();window.loadFile(path.join(__dirname,'startup.html'));broadcast();}}
  app.on('second-instance',show);app.on('before-quit',event=>{if(!finalExit){event.preventDefault();quit();}});app.on('window-all-closed',()=>{});
  app.whenReady().then(()=>{
    const bounds=initialBounds();window=new BrowserWindow({...bounds,minWidth:640,minHeight:480,title:'Comic Metadata',show:false,backgroundColor:'#12151c',autoHideMenuBar:true,icon:path.join(__dirname,'assets','icon.ico'),webPreferences:{preload:path.join(__dirname,'preload.cjs'),contextIsolation:true,nodeIntegration:false,sandbox:true,offscreen:qa}});
    if(bounds.maximized)window.maximize();secure(window,url=>url==='http://127.0.0.1:'+engine?.port+'/'||url.startsWith('file://'));
    let timer;for(const name of ['move','resize','maximize','unmaximize'])window.on(name,()=>{clearTimeout(timer);timer=setTimeout(saveBounds,400);});window.on('show',()=>window.webContents.send('shell-refresh'));window.on('focus',()=>window.webContents.send('shell-refresh'));
    window.on('close',event=>{if(finalExit)return;event.preventDefault();if(!tray){quit();return;}window.hide();const marker=path.join(profile,'tray-notice-shown');if(!fs.existsSync(marker))notify('Comic Metadata is still running','Processing continues in the tray. Right-click the icon to pause or quit.',()=>fs.writeFileSync(marker,'shown'));});
    window.on('query-session-end',()=>{engine?.call('/api/shell/pause',{}).catch(log);setTimeout(async()=>{await engine?.forceStop();exit();},2500);});
    window.once('ready-to-show',()=>{if(!qa)window.show();});window.loadFile(path.join(__dirname,'startup.html'));
    Menu.setApplicationMenu(Menu.buildFromTemplate([{label:'&File',submenu:[{label:'&Exit',accelerator:'Ctrl+Q',click:()=>quit()}]},{label:'&Edit',submenu:[{role:'undo'},{role:'redo'},{type:'separator'},{role:'cut'},{role:'copy'},{role:'paste'},{role:'selectAll'}]},{label:'&View',submenu:[{role:'reload'},{role:'forceReload'},{role:'toggleDevTools'},{type:'separator'},{role:'resetZoom'},{role:'zoomIn'},{role:'zoomOut'},{role:'togglefullscreen'}]}]));
    try{const icon=nativeImage.createFromPath(path.join(__dirname,'assets','tray-processing.png'));if(icon.isEmpty())throw Error('Tray image missing');tray=new Tray(icon);tray.on('click',show);tray.on('double-click',show);}catch(error){log(error);tray=null;}
    engine=new Engine({resources:app.isPackaged?process.resourcesPath:path.join(__dirname,'..','build','staged'),state:stateRoot,locks:qa?path.join(qaRoot,'locks'):path.join(local,'ComicsMeta','locks'),port:qa?Number(process.env.COMICS_META_QA_PORT):8765,log:path.join(logFolder,'engine.log')});
    stopper=new GracefulStop(engine);stopper.on('stage',stoppingDialog);stopper.on('finished',()=>{if(dialog){dialog.removeAllListeners('close');dialog.close();dialog=null;}state.stopping=null;broadcast();});
    const {autoUpdater}=require('electron-updater');updates=new Updates({updater:autoUpdater,stopper,engine,log,exit,qaInstallDirectory:qa?process.env.COMICS_META_QA_INSTALL_DIR:undefined});updates.on('state',value=>{state.update={...value};broadcast();});
    engine.on('exit',()=>{if(stopper.busy||finalExit)return;restarts=restarts.filter(time=>Date.now()-time<60000);if(restarts.length<3){restarts.push(Date.now());setTimeout(start,500);}else{state.service='failed';state.failure='RESTART_EXHAUSTED';broadcast();}});engine.on('engine-error',log);
    start().then(()=>{if(state.service==='ready'&&app.isPackaged){setTimeout(()=>updates.check(false),5000);setInterval(()=>updates.check(false),86400000);}});setInterval(poll,3000);
  }).catch(error=>{console.error(error);app.exit(1);});
}
