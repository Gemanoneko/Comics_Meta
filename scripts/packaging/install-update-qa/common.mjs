import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

export const digest = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
export function requireThat(condition, message) { if (!condition) throw Error(message); }
export function member(root, relative) {
  requireThat(typeof relative === 'string' && relative && !relative.includes('\\') &&
    !/[:\u0000-\u001f]/.test(relative) && relative.split('/').every(p => p && p !== '.' && p !== '..'), 'Unsafe manifest member');
  const resolved = path.resolve(root, ...relative.split('/'));
  requireThat(path.relative(root, resolved) && !path.relative(root, resolved).startsWith('..' + path.sep), 'Manifest escape');
  return resolved;
}
export function inventory(root) {
  const result = [];
  function visit(folder) {
    for (const name of fs.readdirSync(folder).sort()) {
      const file = path.join(folder, name), stat = fs.lstatSync(file);
      requireThat(!stat.isSymbolicLink(), 'Input/output link refused');
      if (stat.isDirectory()) visit(file);
      else {
        requireThat(stat.isFile(), 'Special input/output refused');
        result.push({path:path.relative(root,file).replaceAll('\\','/'),size:stat.size,sha256:digest(fs.readFileSync(file))});
      }
    }
  }
  visit(root);
  return result.sort((a,b) => a.path < b.path ? -1 : a.path > b.path ? 1 : 0);
}
export function verifyInventory(root, expected, {allowManifest=false}={}) {
  requireThat(Array.isArray(expected) && expected.length > 0 && expected.length < 20000, 'Invalid file manifest');
  const names = new Set();
  for (const item of expected) {
    member(root,item.path);
    requireThat(!names.has(item.path.toLowerCase()) && /^[a-f0-9]{64}$/.test(item.sha256) &&
      Number.isSafeInteger(item.size) && item.size >= 0 && item.size <= 2*1024**3, 'Invalid file manifest record');
    names.add(item.path.toLowerCase());
  }
  const actual = inventory(root).filter(item => !allowManifest || item.path !== 'input-manifest.json');
  const normalized=expected.map(({path,size,sha256})=>({path,size,sha256})).sort((a,b)=>a.path<b.path?-1:a.path>b.path?1:0);
  requireThat(JSON.stringify(actual) === JSON.stringify(normalized), 'Input membership or bytes changed');
}
export function writeJson(file, value) {
  fs.writeFileSync(file, JSON.stringify(value,null,2)+'\n', {flag:'wx'});
}
export function safeGuestIdentity(value, hostName) {
  return process.platform === 'win32' && path.resolve(value.scriptRoot).toLowerCase() === 'c:\\cmoinput' &&
    value.user?.toLowerCase() === 'wdagutilityaccount' && value.profile?.toLowerCase() === 'c:\\users\\wdagutilityaccount' &&
    value.tokenName?.split('\\').at(-1).toLowerCase()==='wdagutilityaccount' && /^S-1-5-21-(?:\d+-){3}\d+$/.test(value.tokenSid||'') &&
    typeof value.computer === 'string' && value.computer && value.computer.toLowerCase() !== hostName.toLowerCase() &&
    /virtual machine/i.test(value.model || '');
}
export function parseComputeList(text) {
  const records=[];let current;
  for(const line of text.split(/\r?\n/)) {
    const id=/^([a-f0-9-]{36})\s*$/i.exec(line);
    if(id){current={id:id[1].toLowerCase(),description:''};records.push(current);}
    else if(current&&line.trim())current.description+=(current.description?' ':'')+line.trim();
  }
  requireThat(records.every(x=>/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/.test(x.id)),'Unrecognized compute ID');
  return records.sort((a,b)=>a.id.localeCompare(b.id));
}
export function normalizeComputeJson(text) {
  const rows=JSON.parse(text);
  requireThat(Array.isArray(rows),'HCS JSON enumeration is not an array');
  return rows.map(row=>{
    requireThat(/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(row.Id||''),'Invalid raw HCS ID');
    return {id:row.Id.toLowerCase(),systemType:row.SystemType,runtimeOsType:row.RuntimeOsType,
      owner:row.Owner,runtimeId:row.RuntimeId?.toLowerCase(),state:row.State};
  }).sort((a,b)=>a.id.localeCompare(b.id));
}
export function selectGuestLaunch(events,{mode,nonce,manifestSha256,sessionSha256,startedEpochMs,guestPid}) {
  const expected=['c:\\cmoinput\\node\\node.exe','c:\\cmoinput\\guest-entry.mjs','--mode',mode,'--nonce',nonce,'--manifest-sha',manifestSha256,'--session-sha',sessionSha256];
  const matches=events.filter(event=>{
    const args=String(event.commandLine||'').trim().split(/\s+/);
    if(args.length!==expected.length)return false;
    for(let i=0;i<2;i++)args[i]=args[i].replace(/\\+/g,'\\').toLowerCase();
    return args.every((value,i)=>value===expected[i])&&event.user==='WDAGUtilityAccount'&&event.existingLogin===true&&
      event.result==='0x00000000'&&Number(event.processId)===guestPid&&Number.isSafeInteger(guestPid)&&guestPid>0&&
      event.timeMs>=startedEpochMs&&/^[a-f0-9-]{36}$/i.test(event.systemId||'');
  });
  const unique=new Map(matches.map(event=>[event.systemId.toLowerCase()+':'+event.processId,event]));
  requireThat(unique.size===1,'No unique OS-created guest process matches the exact current request/PID');
  return [...unique.values()][0];
}
export function systemExit(events,systemId,startedEpochMs) {
  return events.find(event=>[2008,2009].includes(event.eventId)&&event.systemId?.toLowerCase()===systemId&&
    event.timeMs>=startedEpochMs&&event.notification==='1'&&event.exitResult==='0x00000000'&&
    (event.eventId===2009||event.result==='0x00000000'));
}
export function selectPackagedClient(events,clients,{packageName,applicationName,imageName,imagePath,currentSid,startedEpochMs}) {
  const candidates=clients.filter(client=>client.owner===currentSid&&typeof client.image==='string'&&path.resolve(client.image).toLowerCase()===path.resolve(imagePath).toLowerCase());
  requireThat(candidates.length===1,'No unique current-user pinned packaged Sandbox UI');
  const client=candidates[0];
  const matching=events.filter(event=>event.eventId===201&&event.packageName===packageName&&event.applicationName===applicationName&&
    event.imageName===imageName&&event.processId===client.pid&&Number.isSafeInteger(client.pid)&&client.pid>0&&event.timeMs>=startedEpochMs);
  requireThat(new Set(matching.map(event=>event.processId)).size===1,'No exact fresh OS activation for packaged Sandbox UI');
  return {client,activation:matching[0]};
}
export function failedGuestWorkflow(value,{mode,nonce,sourceHead,artifactSha256}) {
  return value?.schema===1&&value.pass===false&&typeof value.error==='string'&&value.error.length>0&&
    value.mode===mode&&value.nonce===nonce&&value.sourceHead===sourceHead&&value.artifact?.sha256===artifactSha256&&
    Number.isSafeInteger(value.finished)&&value.finished>=value.started;
}
export async function requestVerifiedInspectorQuit(client,verifiedConnection) {
  if(!client||client!==verifiedConnection)return {requested:false,skipped:'Inspector connection did not pass exact readonly target identity checks'};
  if(client.debuggerPaused)await client.call('Debugger.resume',{},1000);
  await client.evaluate(INSTALLED_REQUIRE_EXPRESSION+"('electron').app.quit();'failed QA graceful Quit requested'",false,3000);
  return {requested:true};
}
// Runtime.evaluate has no CommonJS wrapper lexical require. Anchor module lookup
// to the installed app only after its readonly process identity has been checked.
export const INSTALLED_REQUIRE_EXPRESSION="process.getBuiltinModule('module').createRequire(process.resourcesPath+'/app.asar/package.json')";
export async function inspectInstalledRuntime(client,{pid,exe,local,resources,version}) {
  const actual=await client.evaluate("({pid:process.pid,exe:process.execPath,resources:process.resourcesPath,local:process.env.LOCALAPPDATA,user:process.env.USERNAME,qa:process.env.COMICS_META_QA,builtinModule:typeof process.getBuiltinModule,nodeVersion:process.versions.node,electronVersion:process.versions.electron})");
  requireThat(actual.pid===pid&&Number.isSafeInteger(pid)&&pid>0&&path.resolve(actual.exe).toLowerCase()===path.resolve(exe).toLowerCase()&&
    path.resolve(actual.resources).toLowerCase()===path.resolve(resources).toLowerCase()&&actual.local===local&&
    actual.user?.toLowerCase()==='wdagutilityaccount'&&!actual.qa&&actual.builtinModule==='function','Actual next readonly process/resources/policy identity differs');
  actual.version=await client.evaluate(INSTALLED_REQUIRE_EXPRESSION+"('electron').app.getVersion()");
  requireThat(actual.version===version,'Actual next installed app version differs');return actual;
}
export function installedObserverExpression(feedURL,feedToken) {
  return "(()=>{const r="+INSTALLED_REQUIRE_EXPRESSION+",e=r('electron'),u=r('electron-updater').autoUpdater;u.setFeedURL({provider:'generic',url:"+JSON.stringify(feedURL)+",requestHeaders:{Authorization:"+JSON.stringify('Bearer '+feedToken)+"}});u.requestHeaders={Authorization:"+JSON.stringify('Bearer '+feedToken)+"};globalThis.__cmoInstalledQA={window:()=>e.BrowserWindow.getAllWindows().find(w=>!w.isDestroyed()),state(){this.statePromise=this.window().webContents.executeJavaScript(\"new Promise(r=>{let off;off=window.comicDesktop.onState(s=>{off?.();r(s)});})\");return this.statePromise},action(name){this.actionPromise=this.window().webContents.executeJavaScript('window.comicDesktop.action('+JSON.stringify(name)+')');return this.actionPromise}};return true})()";
}
export const REQUEST_WINDOW_GEOMETRY_EXPRESSION="(()=>{const e="+INSTALLED_REQUIRE_EXPRESSION+"('electron'),w=globalThis.__cmoInstalledQA.window(),d=e.screen.getDisplayMatching(w.getNormalBounds()),a=d.workArea,min=w.getMinimumSize();const width=Math.min(900,a.width-80),height=Math.min(600,a.height-80);if(width<min[0]||height<min[1])throw Error('Guest work area cannot hold a valid geometry fixture');const requested={x:a.x+Math.min(40,Math.floor((a.width-width)/2)),y:a.y+Math.min(40,Math.floor((a.height-height)/2)),width,height};const requestedAt=Date.now();w.setBounds(requested);return {intent:{x:40,y:40,width:900,height:600},requested,requestedAt,immediate:w.getNormalBounds(),workArea:a,scaleFactor:d.scaleFactor,minimum:min}})()";
export const WINDOW_GEOMETRY_EXPRESSION="(()=>{const r="+INSTALLED_REQUIRE_EXPRESSION+",e=r('electron'),fs=r('node:fs'),p=r('node:path'),c=r('node:crypto'),w=globalThis.__cmoInstalledQA.window(),profile=e.app.getPath('userData'),expected=p.join(process.env.APPDATA,'Comic Metadata');if(process.env.USERNAME?.toLowerCase()!=='wdagutilityaccount'||p.resolve(profile).toLowerCase()!==p.resolve(expected).toLowerCase())throw Error('Geometry fixture profile differs');const file=p.join(profile,'window.json');let saved=null;if(fs.existsSync(file)){const s=fs.lstatSync(file);if(!s.isFile()||s.isSymbolicLink()||s.size>4096)throw Error('Unexpected guest window state file');const raw=fs.readFileSync(file,'utf8');saved={path:file,raw,sha256:c.createHash('sha256').update(raw).digest('hex'),parsed:JSON.parse(raw),mtimeMs:s.mtimeMs}}const normal=w.getNormalBounds(),d=e.screen.getDisplayMatching(normal);return {capturedAt:Date.now(),normal,outer:w.getBounds(),content:w.getContentBounds(),maximized:w.isMaximized(),minimum:w.getMinimumSize(),display:{id:d.id,scaleFactor:d.scaleFactor,workArea:d.workArea,bounds:d.bounds},saved}})()";
const rectangle=value=>value&&['x','y','width','height'].every(key=>Number.isInteger(value[key]))&&value.width>0&&value.height>0;
const sameRectangle=(a,b)=>['x','y','width','height'].every(key=>a[key]===b[key]);
export function rememberedGeometryMatches(value,notBeforeEpochMs=0) {
  try {
    if(!rectangle(value.normal)||!rectangle(value.outer)||!rectangle(value.content)||typeof value.maximized!=='boolean'||
      !rectangle(value.display?.workArea)||!Number.isFinite(value.display.scaleFactor)||!(value.display.scaleFactor>0)||!Array.isArray(value.minimum)||value.minimum.length!==2||!value.minimum.every(n=>Number.isInteger(n)&&n>0)||
      value.normal.width<value.minimum[0]||value.normal.height<value.minimum[1]||!value.saved||
      !Number.isFinite(value.saved.mtimeMs)||value.saved.mtimeMs<notBeforeEpochMs||typeof value.saved.raw!=='string'||Buffer.byteLength(value.saved.raw)>4096||digest(Buffer.from(value.saved.raw))!==value.saved.sha256)return false;
    const parsed=JSON.parse(value.saved.raw);return Object.keys(parsed).sort().join(',')==='height,maximized,width,x,y'&&
      sameRectangle(parsed,value.normal)&&parsed.maximized===value.maximized&&JSON.stringify(parsed)===JSON.stringify(value.saved.parsed);
  }catch{return false;}
}
export async function settledRememberedGeometry(read,{deadlineEpochMs,notBeforeEpochMs=0,now=Date.now,pause=ms=>new Promise(resolve=>setTimeout(resolve,ms)),onSample=()=>{}}) {
  let key,stableSince;
  while(now()<deadlineEpochMs){const budget=deadlineEpochMs-now();if(budget<=0)break;const value=await read(Math.min(2000,budget));onSample(value);if(now()>=deadlineEpochMs)break;
    if(rememberedGeometryMatches(value,notBeforeEpochMs)){
      const next=JSON.stringify({normal:value.normal,outer:value.outer,content:value.content,maximized:value.maximized,display:value.display,saved:value.saved.sha256});
      if(next!==key){key=next;stableSince=now();}else if(now()-stableSince>=600)return value;
    }else{key=undefined;stableSince=undefined;}
    const remaining=deadlineEpochMs-now();if(remaining>0)await pause(Math.min(200,remaining));
  }
  throw Error('Actual settled geometry and durable window.json did not agree before original deadline');
}
export function assertRememberedGeometryRestored(prior,next) {
  requireThat(rememberedGeometryMatches(prior)&&rememberedGeometryMatches(next),'Settled native/durable window state proof missing');
  requireThat(sameRectangle(prior.normal,next.normal)&&prior.maximized===next.maximized&&prior.saved.raw===next.saved.raw&&prior.saved.sha256===next.saved.sha256,'Actual remembered geometry/window.json changed');
  requireThat(prior.display.scaleFactor===next.display.scaleFactor&&sameRectangle(prior.display.workArea,next.display.workArea),'Guest display changed during restoration fixture');
}
export async function requestDashboardTransition(client) {
  return client.evaluate("(()=>{const q=globalThis.__cmoInstalledQA;if(q.dashboardTransition)throw Error('Dashboard action already requested');q.dashboardTransition={requestedAt:Date.now(),outcome:'pending'};q.action('setupOpenDashboard').then(()=>{q.dashboardTransition.outcome='resolved';q.dashboardTransition.settledAt=Date.now();},()=>{q.dashboardTransition.outcome='rejected';q.dashboardTransition.settledAt=Date.now();});return 'actual setupOpenDashboard requested once'})()",false);
}
export function dashboardFrameReady(value) {
  return value?.present===true&&value.finished===true&&value.loading===false&&!value.failure&&value.url==='http://127.0.0.1:8765/';
}
export function wsConfig(input,output,mode,nonce,manifestSha,sessionSha) {
  const escape=x=>x.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
  requireThat(['processing','paused'].includes(mode)&&/^[a-f0-9]{32}$/.test(nonce)&&[manifestSha,sessionSha].every(x=>/^[a-f0-9]{64}$/.test(x)),'Invalid bounded launch identity');
  return `<Configuration>
<vGPU>Disable</vGPU><Networking>Disable</Networking><AudioInput>Disable</AudioInput><VideoInput>Disable</VideoInput>
<PrinterRedirection>Disable</PrinterRedirection><ClipboardRedirection>Disable</ClipboardRedirection><MemoryInMB>4096</MemoryInMB>
<MappedFolders><MappedFolder><HostFolder>${escape(input)}</HostFolder><SandboxFolder>C:\\CMOInput</SandboxFolder><ReadOnly>true</ReadOnly></MappedFolder>
<MappedFolder><HostFolder>${escape(output)}</HostFolder><SandboxFolder>C:\\CMOOutput</SandboxFolder><ReadOnly>false</ReadOnly></MappedFolder></MappedFolders>
<LogonCommand><Command>C:\\CMOInput\\node\\node.exe C:\\CMOInput\\guest-entry.mjs --mode ${mode} --nonce ${nonce} --manifest-sha ${manifestSha} --session-sha ${sessionSha}</Command></LogonCommand>
</Configuration>\n`;
}

export class Inspector {
  constructor(socket) {
    this.socket=socket; this.sequence=1; this.pending=new Map(); this.waiters=new Map();this.history=[];this.debuggerPaused=false;
    const remember=entry=>{const actual={time:Date.now(),...entry};this.history.push(actual);if(this.history.length>64)this.history.shift();try{this.onTrace?.(actual);}catch{this.traceError='Inspector diagnostic trace write failed';}};this.remember=remember;
    const disconnected=()=>{remember({kind:'socket-closed',pending:this.pending.size});for(const waiter of this.pending.values()){clearTimeout(waiter.timer);waiter.reject(Error('Inspector socket closed during '+waiter.method));}this.pending.clear();for(const waiter of this.waiters.values()){clearTimeout(waiter.timer);waiter.reject(Error('Inspector socket closed'));}this.waiters.clear();};
    socket.addEventListener('close',disconnected,{once:true});
    socket.addEventListener('message', event => {
      const record=JSON.parse(event.data);
      if(record.id) {
        const waiter=this.pending.get(record.id); if(!waiter)return;
        this.pending.delete(record.id); clearTimeout(waiter.timer);
        remember({kind:'response',id:record.id,method:waiter.method,error:Boolean(record.error)});
        record.error ? waiter.reject(Error(JSON.stringify(record.error))) : waiter.resolve(record.result);
      } else if(record.method) {
        if(record.method==='Debugger.paused'){this.debuggerPaused=true;remember({kind:'paused',reason:record.params?.reason,locations:record.params?.callFrames?.slice(0,3).map(frame=>({url:frame.url,lineNumber:frame.location?.lineNumber}))});}
        if(record.method==='Debugger.resumed'){this.debuggerPaused=false;remember({kind:'resumed'});}
        const waiter=this.waiters.get(record.method); if(!waiter)return;
        this.waiters.delete(record.method); clearTimeout(waiter.timer); waiter.resolve(record.params);
      }
    });
  }
  static async connect(port, timeout=10000) {
    const deadline=Date.now()+timeout;
    while(Date.now()<deadline) {
      try {
        const response=await fetch('http://127.0.0.1:'+port+'/json/list',{signal:AbortSignal.timeout(1000)});
        const target=(await response.json()).find(item=>item.type==='node');
        if(target) {
          const url=new URL(target.webSocketDebuggerUrl);
          requireThat(url.protocol==='ws:' && url.hostname==='127.0.0.1' && Number(url.port)===port,'Unexpected inspector endpoint');
          const socket=new WebSocket(url.href);
          await new Promise((resolve,reject)=>{socket.addEventListener('open',resolve,{once:true});socket.addEventListener('error',reject,{once:true});});
          const client=new Inspector(socket); await client.call('Runtime.enable'); return client;
        }
      } catch {}
      await new Promise(resolve=>setTimeout(resolve,100));
    }
    throw Error('Private inspector endpoint absent');
  }
  call(method,params={},timeoutMs=10000) {
    requireThat(Number.isInteger(timeoutMs)&&timeoutMs>0&&timeoutMs<=10000,'Invalid private inspector call bound');
    return new Promise((resolve,reject)=>{
      const id=this.sequence++,expressionSha256=typeof params.expression==='string'?digest(Buffer.from(params.expression)):undefined;
      this.remember({kind:'request',id,method,expressionSha256,awaitPromise:params.awaitPromise});
      const timer=setTimeout(()=>{this.pending.delete(id);this.remember({kind:'timeout',id,method,expressionSha256});reject(Error('Inspector call timed out: '+method+(expressionSha256?' expression '+expressionSha256:'')));},timeoutMs);
      this.pending.set(id,{resolve,reject,timer,method}); this.socket.send(JSON.stringify({id,method,params}));
    });
  }
  event(method) {
    return new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>{this.waiters.delete(method);reject(Error('Inspector event timed out: '+method));},10000);
      this.waiters.set(method,{resolve,reject,timer});
    });
  }
  async evaluate(expression, awaitPromise=true,timeoutMs=10000) {
    const result=await this.call('Runtime.evaluate',{expression,awaitPromise,returnByValue:true},timeoutMs);
    requireThat(!result.exceptionDetails,'Inspector evaluation failed: '+JSON.stringify(result.exceptionDetails));
    return result.result?.value;
  }
  close() { this.socket.close(); }
}
