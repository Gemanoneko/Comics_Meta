(function () {
  const fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process'),electron=require('electron');
  const policy=JSON.parse(fs.readFileSync(process.env.CMO_SANDBOX_PLAN));
  if(process.env.COMICS_META_QA||process.env.USERNAME.toLowerCase()!=='wdagutilityaccount')throw Error('Expected ordinary installed guest mode');
  const q=globalThis.__cmoInstalledQA={electron,policy,engines:[],events:[],menu:null};
  const updater=require('electron-updater').autoUpdater;
  updater.setFeedURL({provider:'generic',url:policy.feedURL,requestHeaders:{Authorization:'Bearer '+policy.feedToken}});
  updater.requestHeaders={Authorization:'Bearer '+policy.feedToken};
  const record=value=>{
    q.events.push({...value,time:Date.now()});
    fs.writeFileSync(process.env.CMO_QA_OBSERVER,JSON.stringify({pid:process.pid,version:electron.app.getVersion(),events:q.events},null,2));
  };
  q.renderers=new Map();
  electron.app.on('browser-window-created',(_event,window)=>{
    const contents=window.webContents,item={id:contents.id,finished:false,failure:null};q.renderers.set(contents.id,item);
    record({kind:'window-created',webContentsId:contents.id});
    contents.on('did-start-loading',()=>{item.finished=false;});
    contents.on('did-finish-load',()=>{item.finished=true;record({kind:'renderer-loaded',webContentsId:contents.id,path:new URL(contents.getURL()).pathname});});
    contents.on('render-process-gone',(_event,details)=>{item.failure={kind:'renderer-gone',reason:details.reason,exitCode:details.exitCode};record({...item.failure,webContentsId:contents.id});});
    contents.on('did-fail-load',(_event,errorCode,_description,_url,isMainFrame)=>{if(isMainFrame&&errorCode!==-3){item.failure={kind:'renderer-load-failed',errorCode};record({...item.failure,webContentsId:contents.id});}});
    window.once('ready-to-show',()=>record({kind:'window-ready-to-show',webContentsId:contents.id}));
  });
  const realSpawn=cp.spawn;
  cp.spawn=function(file,args,options){
    const direct=path.join(process.resourcesPath,'runtime','python','python.exe');
    const engine=args?.[1]===path.join(process.resourcesPath,'engine','engine_host.py');
    if(engine){
      if(path.resolve(file)!==direct||args[0]!=='-B'||path.resolve(options?.env?.COMICS_META_STATE_ROOT||'')!==path.resolve(process.env.LOCALAPPDATA,'ComicsMeta'))throw Error('Unexpected installed engine spawn');
      const child=realSpawn.call(this,file,args,options);
      const item={pid:child.pid,child,token:options.env.COMICS_META_SHELL_TOKEN,exit:null};q.engines.push(item);
      child.once('exit',(code,signal)=>{item.exit={code,signal};record({kind:'engine-exit',pid:child.pid,code,signal});});
      record({kind:'engine-start',pid:child.pid});return child;
    }
    const capsule=path.join(process.env.LOCALAPPDATA,'ComicsMeta','work','update-launch')+path.sep;
    if(!path.resolve(file).startsWith(capsule)||!String(file).endsWith(path.join('runtime','python','python.exe'))||
       JSON.stringify(args?.slice(0,3))!==JSON.stringify(['-I','-S','-B'])||!String(args[3]).endsWith(path.join('engine','installer_launch.py')))
      throw Error('Unexpected installed update child');
    if(!q.engines.length||!q.engines.every(item=>item.exit?.code===0&&item.exit.signal===null))throw Error('Old engine still alive at installer-helper launch');
    record({kind:'before-installer-helper',engines:q.engines.map(item=>({pid:item.pid,exit:item.exit})),helper:file});
    const child=realSpawn.call(this,file,args,options);
    let output='';child.stdout.on('data',chunk=>{
      output+=chunk.toString('utf8');if(output.length>4096)throw Error('Installer receipt exceeded its bound');
      const end=output.indexOf('\n');if(end>=0&&!q.installerReceipt){q.installerReceipt=JSON.parse(output.slice(0,end));record({kind:'installer-receipt',helperPid:child.pid,receipt:q.installerReceipt});}
    });
    return child;
  };
  const realMenu=electron.Tray.prototype.setContextMenu;
  electron.Tray.prototype.setContextMenu=function(menu){q.menu=menu;return realMenu.call(this,menu);};
  q.window=()=>electron.BrowserWindow.getAllWindows().find(window=>!window.isDestroyed());
  q.renderer=()=>{const contents=q.window()?.webContents;if(!contents)return {present:false};const item=q.renderers.get(contents.id);return {present:true,url:contents.getURL(),loading:contents.isLoadingMainFrame(),finished:item?.finished===true,failure:item?.failure};};
  q.state=()=>{
    q.statePromise=q.window().webContents.executeJavaScript("new Promise((resolve,reject)=>{let off;const timer=setTimeout(()=>reject(Error('Shell snapshot timeout')),5000);off=window.comicDesktop.onState(value=>{clearTimeout(timer);off?.();resolve(value);});})");
    return q.statePromise;
  };
  q.action=name=>{q.actionPromise=q.window().webContents.executeJavaScript('window.comicDesktop.action('+JSON.stringify(name)+')');return q.actionPromise;};
  q.setup=(folder,keys)=>{q.setupPromise=q.window().webContents.executeJavaScript('window.comicDesktop.saveSetup('+JSON.stringify(folder)+','+JSON.stringify(keys)+')');return q.setupPromise;};
  q.pause=()=>{const item=q.menu?.items.find(item=>item.label==='&Pause && release GPU'&&item.enabled);if(!item)throw Error('Real pause menu unavailable');q.pausePromise=Promise.resolve(item.click());return 'real pause requested';};
  q.quit=()=>{const item=q.menu?.items.find(item=>item.label==='&Quit'&&item.enabled);if(!item)throw Error('Real Quit menu unavailable');q.quitPromise=Promise.resolve(item.click());return 'real Quit requested';};
  return {pid:process.pid,exe:process.execPath,version:electron.app.getVersion(),installed:true};
})()
