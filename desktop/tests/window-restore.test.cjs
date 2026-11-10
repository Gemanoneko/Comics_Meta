'use strict';
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');const vm=require('node:vm');const {EventEmitter}=require('node:events');
const source=fs.readFileSync(path.join(__dirname,'..','main.cjs'),'utf8');
const rectangle={x:40,y:40,width:900,height:600};

function fixture(saved={...rectangle,maximized:false},{platform='win32',displays=[{workArea:{x:0,y:0,width:1626,height:835}}]}={}){
  const files=new Map(),windows=[],order=[],timers=new Map();let ready,clock=0,nextTimer=1;
  const profile=path.resolve('fixture-profile'),stateFile=path.join(profile,'window.json');
  if(saved!==null)files.set(stateFile,typeof saved==='string'?saved:JSON.stringify(saved));
  const fakeFs={readFileSync(file){if(!files.has(file))throw Error('ENOENT');return files.get(file);},
    mkdirSync(){},existsSync(){return false;},appendFileSync(){},writeFileSync(file,value){files.set(file,String(value));},
    renameSync(from,to){files.set(to,files.get(from));files.delete(from);}};
  class Window extends EventEmitter{
    constructor(options){super();this.options=options;this.normal={x:options.x??0,y:options.y??0,width:options.width,height:options.height};
      // Fault model from retry07: same accepted saved outer DIP rectangle grows
      // during Windows constructor's repeated position/read-size conversions.
      // This is not a substitute for the actual 250%-DPI packaged regression.
      if(platform==='win32'&&Number.isInteger(options.x)){this.normal.width+=2;this.normal.height+=2;}
      this.maximized=false;this.minimized=false;this.boundsCalls=[];this.shown=[];
      this.webContents=new EventEmitter();Object.assign(this.webContents,{send(){},setWindowOpenHandler(){},mainFrame:{}});windows.push(this);}
    setBounds(value){this.boundsCalls.push({...value});this.normal={...value};order.push('setBounds');this.emit('resize');}
    getNormalBounds(){return {...this.normal};}isDestroyed(){return false;}isMinimized(){return this.minimized;}isMaximized(){return this.maximized;}
    maximize(){order.push('maximize');this.maximized=true;this.emit('maximize');}
    show(){order.push('show');this.shown.push(this.getNormalBounds());this.emit('show');}
    loadFile(){this.emit('ready-to-show');return Promise.resolve();}loadURL(){return Promise.resolve();}
  }
  class Engine extends EventEmitter{start(){return new Promise(()=>{});}}
  class Stop extends EventEmitter{}
  class Updates extends EventEmitter{constructor(){super();this.state={phase:'idle'};}}
  class Tray extends EventEmitter{setImage(){}setToolTip(){}setContextMenu(){}}
  const app=new EventEmitter();Object.assign(app,{getVersion:()=> '0.6.1',getPath:()=>profile,requestSingleInstanceLock:()=>true,
    setAppUserModelId(){},isPackaged:false,whenReady:()=>({then(callback){ready=callback;return {catch(){}};}})});
  const electron={app,BrowserWindow:Window,Tray,Menu:{buildFromTemplate:value=>value,setApplicationMenu(){}},Notification:{isSupported:()=>false},
    nativeTheme:{},nativeImage:{createFromPath:()=>({isEmpty:()=>false})},screen:{getPrimaryDisplay:()=>displays[0],getAllDisplays:()=>displays},
    shell:{},ipcMain:{handle(){}},session:{},dialog:{}};
  const modules={electron,'node:fs':fakeFs,'node:path':path,'node:url':require('node:url'),'node:crypto':require('node:crypto'),
    './engine.cjs':{Engine},'./graceful-stop.cjs':{GracefulStop:Stop},'./updates.cjs':{Updates},
    './qa-policy.cjs':{loadPolicy:()=>null},'electron-updater':{autoUpdater:{}}};
  vm.runInNewContext(source,{require(name){assert.ok(Object.hasOwn(modules,name),'Unexpected startup dependency '+name);return modules[name];},
    __dirname:path.join(__dirname,'..'),process:{platform,env:{LOCALAPPDATA:path.resolve('fixture-local')},resourcesPath:''},console,
    setTimeout(fn,ms){const id=nextTimer++;timers.set(id,{fn,at:clock+ms});return id;},clearTimeout:id=>timers.delete(id),setInterval:()=>0});
  ready();
  return {window:windows[0],order,files,stateFile,tick(ms){clock+=ms;for(const[id,t]of [...timers])if(t.at<=clock){timers.delete(id);t.fn();}},
    persisted(){return JSON.parse(files.get(stateFile));}};
}

test('restores the exact saved outer DIP rectangle after constructor conversion, before showing',()=>{
  const f=fixture();assert.deepEqual(f.window.getNormalBounds(),rectangle);
  assert.deepEqual(f.window.boundsCalls,[rectangle]);assert.deepEqual(f.window.shown,[rectangle]);
  assert.ok(f.order.indexOf('setBounds')<f.order.indexOf('show'));
});
test('normal saved bounds are applied before maximize and survive repeated save/restore',()=>{
  let saved={...rectangle,maximized:true};
  for(let launch=0;launch<5;launch++){
    const f=fixture(saved);assert.deepEqual(f.window.getNormalBounds(),rectangle);assert.equal(f.window.isMaximized(),true);
    assert.ok(f.order.indexOf('setBounds')<f.order.indexOf('maximize'));f.window.emit('resize');f.tick(400);saved=f.persisted();
    assert.deepEqual(saved,{...rectangle,maximized:true});
  }
});
test('first launch and corrupt, undersized, offscreen or oversized saved state retain defaults',()=>{
  for(const saved of [null,'bad json',{...rectangle,width:639},{...rectangle,x:5000},{...rectangle,width:2000},{...rectangle,x:40.5}]){
    const f=fixture(saved);assert.equal(f.window.boundsCalls.length,0);assert.equal(f.window.options.width,1280);assert.equal(f.window.options.height,751);
    assert.equal(f.window.options.minWidth,640);assert.equal(f.window.options.minHeight,480);
  }
});
test('constructor keeps a secondary display position to select its DPI before exact restoration',()=>{
  const saved={...rectangle,x:2010};const f=fixture(saved,{displays:[{workArea:{x:0,y:0,width:1626,height:835}},{workArea:{x:2000,y:0,width:1600,height:1000}}]});
  assert.equal(f.window.options.x,2010);assert.equal(f.window.options.y,40);assert.deepEqual(f.window.getNormalBounds(),saved);
});
test('later user resize persists after the existing 400ms debounce, without resetting to restored bounds',()=>{
  const f=fixture();const changed={x:70,y:80,width:1000,height:700};f.window.setBounds(changed);f.tick(399);
  assert.deepEqual(f.persisted(),{...rectangle,maximized:false});f.tick(1);assert.deepEqual(f.persisted(),{...changed,maximized:false});
  f.window.minimized=true;f.window.normal={x:-32000,y:-32000,width:1,height:1};f.window.emit('resize');f.tick(400);
  assert.deepEqual(f.persisted(),{...changed,maximized:false});
});
test('non-Windows restoration keeps its existing constructor behavior',()=>{
  const f=fixture(undefined,{platform:'linux'});assert.deepEqual(f.window.getNormalBounds(),rectangle);assert.equal(f.window.boundsCalls.length,0);
});
