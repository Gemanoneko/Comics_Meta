'use strict';
// Loads the real desktop/main.cjs in a VM with stand-in Electron, engine, stopper and updater, a controlled clock and
// controlled timers (window-restore.test.cjs does the same for window bounds). Nothing is started or shown.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),{pathToFileURL}=require('node:url'),{EventEmitter}=require('node:events');
const desktop=path.join(__dirname,'..');
const source=fs.readFileSync(path.join(desktop,'main.cjs'),'utf8');
const flush=async(times=5)=>{for(let i=0;i<times;i++)await new Promise(resolve=>setImmediate(resolve));};
function mainFixture({engine:engineOptions={},realStopper=false}={}){
  const f={windows:[],handlers:{},logs:[],quits:0,trayMenu:null,trayDestroyed:false,clock:0,timers:new Map(),nextTimer:1,engine:null,stopper:null,files:new Map()};
  class Window extends EventEmitter{
    constructor(options){super();this.options=options;this.visible=false;this.shown=0;this.shownInactive=0;this.focused=0;this.destroyed=false;this.loads=[];this.url='';this.sent=[];
      this.webContents=Object.assign(new EventEmitter(),{send:(channel,value)=>this.sent.push([channel,structuredClone(value)]),setWindowOpenHandler(){},mainFrame:{},getURL:()=>this.url,stop(){}});f.windows.push(this);}
    setBounds(){}getNormalBounds(){return {x:0,y:0,width:900,height:600};}isDestroyed(){return this.destroyed;}isMinimized(){return false;}isMaximized(){return false;}maximize(){}restore(){}
    isVisible(){return this.visible;}isFocused(){return false;}setMenu(){}
    show(){this.visible=true;this.shown++;this.emit('show');}showInactive(){this.visible=true;this.shownInactive++;}focus(){this.focused++;}hide(){this.visible=false;}
    loadFile(file){this.loads.push(path.basename(file));this.url=pathToFileURL(file).href;setImmediate(()=>this.emit('ready-to-show'));return Promise.resolve();}
    loadURL(url){this.loads.push(url);this.url=url;return Promise.resolve();}
    close(){let prevented=false;this.emit('close',{preventDefault(){prevented=true;}});if(!prevented)this.destroyed=true;return !prevented;}
    get lastState(){return [...this.sent].reverse().find(([channel])=>channel==='shell-state')?.[1];}
  }
  class Engine extends EventEmitter{constructor(options){super();Object.assign(this,{options,ready:false,closureWaitS:30,port:1,forceStops:0,leftovers:0,starts:0},engineOptions);f.engine=this;}
    start(){this.starts++;return this.startWith?this.startWith(this.starts):new Promise(()=>{});}
    call(endpoint){return this.callWith?this.callWith(endpoint):Promise.reject(Error('offline'));}
    forceStop(){this.forceStops++;return this.forceWith?this.forceWith():Promise.resolve(true);}
    recordLeftover(){this.leftovers++;}}
  class Stop extends EventEmitter{constructor(engine){super();Object.assign(this,{engine,busy:false,runs:0,cancels:0,forces:0});f.stopper=this;}
    run(mode){this.busy=true;this.mode=mode;this.runs++;return new Promise((resolve,reject)=>{this.settle={
      resolve:value=>{this.busy=false;this.emit('finished');resolve(value);},reject:error=>{this.busy=false;this.emit('finished');reject(error);}};});}
    cancel(){this.cancels++;}force(){this.forces++;}}
  class Updates extends EventEmitter{constructor(){super();this.state={phase:'idle'};}}
  class Tray extends EventEmitter{setImage(){}setToolTip(value){f.trayTip=value;}setContextMenu(menu){f.trayMenu=menu;}destroy(){f.trayDestroyed=true;}}
  const app=new EventEmitter();let ready;
  Object.assign(app,{getVersion:()=>'0.6.7',getPath:()=>path.resolve('fixture-profile'),requestSingleInstanceLock:()=>true,setAppUserModelId(){},isPackaged:false,
    whenReady:()=>({then(callback){ready=callback;return {catch(){}};}}),quit(){f.quits++;},exit(){}});
  const fakeFs={readFileSync(file){if(!f.files.has(file))throw Object.assign(Error('ENOENT'),{code:'ENOENT'});return f.files.get(file);},mkdirSync(){},existsSync:file=>f.files.has(file),
    appendFileSync(_file,value){f.logs.push(String(value));},writeFileSync(file,value){f.files.set(file,String(value));},renameSync(from,to){f.files.set(to,f.files.get(from));f.files.delete(from);}};
  const electron={app,BrowserWindow:Window,Tray,Menu:{buildFromTemplate:value=>value,setApplicationMenu(){}},Notification:{isSupported:()=>false},
    nativeTheme:{},nativeImage:{createFromPath:()=>({isEmpty:()=>false,addRepresentation(){}})},screen:{getPrimaryDisplay:()=>({workArea:{x:0,y:0,width:1600,height:900}}),getAllDisplays:()=>[{workArea:{x:0,y:0,width:1600,height:900}}]},
    shell:{openPath:()=>Promise.resolve('')},ipcMain:{handle(name,fn){f.handlers[name]=fn;}},session:{},dialog:{}};
  const modules={electron,'node:fs':fakeFs,'node:path':path,'node:url':require('node:url'),'node:crypto':require('node:crypto'),
    './engine.cjs':{Engine},'./graceful-stop.cjs':realStopper?{GracefulStop:class extends require('../graceful-stop.cjs').GracefulStop{constructor(engine){super(engine);f.stopper=this;}}}:{GracefulStop:Stop},'./updates.cjs':{Updates},'./qa-policy.cjs':{loadPolicy:()=>null},'electron-updater':{autoUpdater:{}}};
  vm.runInNewContext(source,{require(name){if(!Object.hasOwn(modules,name))throw Error('Unexpected dependency '+name);return modules[name];},
    __dirname:desktop,process:{platform:'win32',env:{LOCALAPPDATA:path.resolve('fixture-local')},resourcesPath:''},console,
    performance:{now:()=>f.clock},setTimeout(fn,ms){const id=f.nextTimer++;f.timers.set(id,{fn,at:f.clock+Math.max(0,ms||0)});return id;},clearTimeout:id=>f.timers.delete(id),setInterval:()=>0});
  ready();
  Object.defineProperty(f,'dialog',{get:()=>f.windows[1]&&!f.windows[1].destroyed?f.windows[1]:null});
  Object.assign(f,{app,window:f.windows[0],
    async tick(ms){const until=f.clock+ms;for(;;){const due=[...f.timers].filter(([,t])=>t.at<=until).sort((a,b)=>a[1].at-b[1].at)[0];if(!due)break;f.timers.delete(due[0]);f.clock=Math.max(f.clock,due[1].at);due[1].fn();await flush();}f.clock=until;await flush();},
    sender(target=f.window){return {sender:target.webContents,senderFrame:target.webContents.mainFrame};},
    action(name,target){return f.handlers['shell-action'](f.sender(target),name);},
    state(){return structuredClone(f.handlers['shell-snapshot'](f.sender()));},  // A plain copy: the VM's objects have their own prototypes.
    trayQuit(){return f.trayMenu.at(-1);}});
  return f;
}
module.exports={mainFixture,flush};
