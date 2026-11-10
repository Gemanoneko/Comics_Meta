import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import crypto from 'node:crypto';
import {spawn,spawnSync} from 'node:child_process';
import {createRequire} from 'node:module';
import {digest,requireThat,writeJson,Inspector,member,requestVerifiedInspectorQuit,requestDashboardTransition,dashboardFrameReady,inspectInstalledRuntime,installedObserverExpression,REQUEST_WINDOW_GEOMETRY_EXPRESSION,WINDOW_GEOMETRY_EXPRESSION,settledRememberedGeometry,assertRememberedGeometryRestored} from './common.mjs';

const input='C:/CMOInput',output='C:/CMOOutput';
const plan=JSON.parse(fs.readFileSync(input+'/plan.json'));
const [mode,nonce]=process.argv.slice(2);
requireThat(['processing','paused'].includes(mode)&&plan.runs[mode].nonce===nonce&&process.env.USERNAME?.toLowerCase()==='wdagutilityaccount','Wrong isolated guest phase');
const root=path.resolve('C:/Q/illuminati-cmo-qa-'+mode),install=path.join(process.env.LOCALAPPDATA,'Programs','comic-metadata'),exe=path.join(install,'ComicMetadata.exe');
const state=path.join(process.env.LOCALAPPDATA,'ComicsMeta');
const deadline=JSON.parse(fs.readFileSync(output+'/session-request.json')).deadlineEpochMs-60000;
const evidence={schema:1,mode,nonce,sourceHead:plan.sourceHead,sourceIdentity:plan.sourceIdentity,artifact:plan.artifact,
  priorVersion:plan.priorVersion,nextVersion:plan.version,started:Date.now(),pass:false};
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function remain(){const value=deadline-Date.now();requireThat(value>0,'Original guest work deadline reached');return value;}
async function until(read,accept,what){while(remain()>0){const value=await read();if(accept(value))return value;await sleep(200);}throw Error(what);}
const env={...process.env,CMO_SANDBOX_CASE_ROOT:root,COMICS_META_STATE_ROOT:state,PYTHONDONTWRITEBYTECODE:'1'};
delete env.COMICS_META_QA;delete env.COMICS_META_QA_POLICY;delete env.COMICS_META_QA_ROOT;
const ps='C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe';
function query(script){const r=spawnSync(ps,['-NoLogo','-NoProfile','-NonInteractive','-Command',script],{windowsHide:true,encoding:'utf8',timeout:Math.min(10000,remain()),maxBuffer:2*1024*1024});requireThat(r.status===0,'Guest OS readback failed');return JSON.parse(r.stdout.trim()||'null');}
function installedProcesses(){const a=install.replaceAll("'","''"),b=path.join(state,'work','update-launch').replaceAll("'","''");const value=query("@((Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -and ($_.ExecutablePath.StartsWith('"+a+"',[System.StringComparison]::OrdinalIgnoreCase) -or $_.ExecutablePath.StartsWith('"+b+"',[System.StringComparison]::OrdinalIgnoreCase)) } | Select-Object ProcessId,ParentProcessId,ExecutablePath,CommandLine,@{n='CreatedMs';e={([DateTimeOffset]$_.CreationDate).ToUnixTimeMilliseconds()}})) | ConvertTo-Json -Compress");return Array.isArray(value)?value:value?[value]:[];}
function fixture(action){const r=spawnSync(path.join(install,'resources/runtime/python/python.exe'),['-B',input+'/state-fixture.py',action],{cwd:path.join(install,'resources/engine'),env,windowsHide:true,encoding:'utf8',timeout:Math.min(220000,remain()),maxBuffer:2*1024*1024});requireThat(r.status===0,'Guest fixture failed: '+r.stderr);return JSON.parse(r.stdout.trim());}
function registration(version){const value=query("@(Get-ChildItem 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall' | ForEach-Object {Get-ItemProperty $_.PSPath} | Where-Object {$_.DisplayName -eq 'Comic Metadata "+version+"'} | Select-Object DisplayName,DisplayVersion,UninstallString) | ConvertTo-Json -Compress");const rows=Array.isArray(value)?value:value?[value]:[];requireThat(rows.length===1&&rows[0].DisplayName==='Comic Metadata '+version&&rows[0].DisplayVersion===version,'Actual guest product version registration differs');const quoted=/^\"([^\"]+)\"/.exec(rows[0].UninstallString||'');requireThat(quoted&&path.dirname(quoted[1]).toLowerCase()===install.toLowerCase(),'Actual guest registered install location differs');return {...rows[0],registeredDirectory:path.dirname(quoted[1])};}
async function child(file,args,options={}){const c=spawn(file,args,{windowsHide:true,stdio:['ignore','pipe','pipe'],...options});let out='',err='';c.stdout.on('data',x=>{out+=x;requireThat(out.length<1024*1024,'Child output overflow');});c.stderr.on('data',x=>{err+=x;requireThat(err.length<1024*1024,'Child error output overflow');});const exit=new Promise((resolve,reject)=>{c.once('error',reject);c.once('close',(code,signal)=>resolve({code,signal,out,err}));});return {child:c,exit,diagnostics:()=>({pid:c.pid,exitCode:c.exitCode,stderr:err.slice(-8192).replaceAll(feedToken,'[redacted]').replace(/synthetic-sandbox-key-\d+/g,'[redacted]')})};}
const feedToken=crypto.randomBytes(32).toString('hex'),feedPath='/feed/'+crypto.randomBytes(16).toString('hex')+'/';
const feedURL='http://127.0.0.1:18995'+feedPath;
const feedCalls=[],modelCalls=[];
const feed=http.createServer((req,res)=>{
  const u=new URL(req.url,'http://127.0.0.1');
  const name=u.pathname.startsWith(feedPath)?u.pathname.slice(feedPath.length):'';
  feedCalls.push({name,method:req.method,authorized:req.headers.authorization==='Bearer '+feedToken});
  if(req.headers.authorization!=='Bearer '+feedToken||!['latest.yml',plan.artifact.name,plan.artifact.name+'.blockmap'].includes(name)){res.writeHead(404).end();return;}
  const file=member(input,'next/'+name),stat=fs.statSync(file);
  const range=/^bytes=(\d+)-(\d*)$/.exec(req.headers.range||'');
  if(range){const start=Number(range[1]),end=range[2]?Number(range[2]):stat.size-1;if(start>end||end>=stat.size){res.writeHead(416).end();return;}res.writeHead(206,{'Content-Length':end-start+1,'Content-Range':`bytes ${start}-${end}/${stat.size}`,'Accept-Ranges':'bytes'});fs.createReadStream(file,{start,end}).pipe(res);}
  else {res.writeHead(200,{'Content-Length':stat.size});fs.createReadStream(file).pipe(res);}
});
const model=http.createServer((req,res)=>{modelCalls.push(req.url);res.writeHead(200,{'Content-Type':'application/json'}).end(JSON.stringify(req.url==='/api/generate'?{done:true}:{models:[]}));});
async function listen(server,port){await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(port,'127.0.0.1',resolve);});}
let old,inspector,verifiedInspector=null,nextHandle;
let traceBytes=0;
function traceInspector(client,target){client.onTrace=record=>{const line=JSON.stringify({mode,nonce,target,stage:evidence.stage||'prior debugger startup',...record})+'\n';traceBytes+=Buffer.byteLength(line);if(traceBytes<=512*1024)fs.appendFileSync(output+'/inspector-trace.jsonl',line);else evidence.inspectorTraceTruncated=true;};}
const require=createRequire(import.meta.url),koffi=require(input+'/ownership/node_modules/koffi');
const kernel=koffi.load('kernel32.dll');
const open=kernel.func('void* __stdcall OpenProcess(uint32_t,bool,uint32_t)');
const wait=kernel.func('uint32_t __stdcall WaitForSingleObject(void*,uint32_t)');
const code=kernel.func('bool __stdcall GetExitCodeProcess(void*,void*)');
const close=kernel.func('bool __stdcall CloseHandle(void*)');
const image=kernel.func('bool __stdcall QueryFullProcessImageNameW(void*,uint32_t,void*,void*)');
function holdExact(pid){const h=open(0x00101000,false,pid);requireThat(h,'Cannot retain exact relaunched app');const buffer=Buffer.alloc(65536),length=Buffer.alloc(4);length.writeUInt32LE(32768);if(!image(h,0,buffer,length)||path.resolve(buffer.subarray(0,length.readUInt32LE()*2).toString('utf16le')).toLowerCase()!==path.resolve(exe).toLowerCase()){close(h);throw Error('Wrong relaunched image');}return h;}
async function shellState(client){return client.evaluate("globalThis.__cmoInstalledQA.state()",true);}
async function action(client,name){return client.evaluate('globalThis.__cmoInstalledQA.action('+JSON.stringify(name)+')',true);}
try {
  requireThat(!fs.existsSync(state),'Fresh Sandbox already has ComicsMeta state');
  const prior=member(input,'prior/'+plan.priorArtifact.name);
  requireThat(fs.statSync(prior).size===plan.priorArtifact.size&&digest(fs.readFileSync(prior))===plan.priorArtifact.sha256,'Wrong prior installer');
  requireThat(!fs.existsSync(install),'Fresh Sandbox already has an installed app');
  const localPrior=path.join(root,plan.priorArtifact.name);fs.copyFileSync(prior,localPrior,fs.constants.COPYFILE_EXCL);
  const first=await child(localPrior,['/S']);
  const firstExit=await first.exit;requireThat(firstExit.code===0&&firstExit.signal===null,'Actual prior installation failed');
  requireThat(fs.existsSync(exe),'Actual prior installation produced no app');
  evidence.priorInstallation={exit:firstExit,versionFile:fs.readFileSync(path.join(install,'resources/engine/VERSION'),'utf8').trim()};
  requireThat(evidence.priorInstallation.versionFile===plan.priorVersion,'Wrong prior installed engine version');
  evidence.priorRegistration=registration(plan.priorVersion);
  const prepared=fixture('prepare');evidence.fixture=prepared;
  const conversion=await child(path.join(install,'resources/runtime/7zip/7z.exe'),['a','-t7z',prepared.conversionArchive,prepared.conversionCover]);
  requireThat((await conversion.exit).code===0,'Bundled7Zip failed to prepare actual conversion fixture');
  await listen(feed,18995);await listen(model,11434);
  const localPlan=path.join(root,'case-plan.json');writeJson(localPlan,{feedURL,feedToken});
  env.CMO_SANDBOX_PLAN=localPlan;env.CMO_QA_OBSERVER=path.join(output,'old-observer.json');
  old=await child(exe,['--inspect-brk=127.0.0.1:18991'],{env,cwd:install});
  inspector=await Inspector.connect(18991);traceInspector(inspector,'prior');await inspector.call('Debugger.enable');const pausedEvent=inspector.event('Debugger.paused');await inspector.call('Runtime.runIfWaitingForDebugger');const paused=await pausedEvent;
  const frame=paused.callFrames?.[0]?.callFrameId;requireThat(frame,'Prior app did not pause before main');
  const target=await inspector.call('Debugger.evaluateOnCallFrame',{callFrameId:frame,expression:'({pid:process.pid,exe:process.execPath,resources:process.resourcesPath,user:process.env.USERNAME,profile:process.env.LOCALAPPDATA,qa:process.env.COMICS_META_QA,builtinModule:typeof process.getBuiltinModule})',returnByValue:true});
  requireThat(!target.exceptionDetails&&target.result.value.pid===old.child.pid&&path.resolve(target.result.value.exe)===exe&&path.resolve(target.result.value.resources)===path.join(install,'resources')&&target.result.value.builtinModule==='function'&&target.result.value.profile===process.env.LOCALAPPDATA&&target.result.value.user.toLowerCase()==='wdagutilityaccount'&&!target.result.value.qa,'Wrong prior inspector target');verifiedInspector=inspector;
  const injected=await inspector.call('Debugger.evaluateOnCallFrame',{callFrameId:frame,expression:fs.readFileSync(input+'/observer.cjs','utf8'),returnByValue:true});
  requireThat(!injected.exceptionDetails&&injected.result.value.version===plan.priorVersion,'Prior observer did not bind exact app');await inspector.call('Debugger.resume');
  evidence.stage='prior setup page';
  evidence.priorRenderer=await until(()=>inspector.evaluate('globalThis.__cmoInstalledQA.renderer()'),value=>{
    evidence.lastPriorRenderer=value;requireThat(!value.failure,'Prior installed renderer failed: '+JSON.stringify(value.failure));
    return value.present&&value.finished&&!value.loading&&value.url.endsWith('/setup.html');
  },'Prior first-run setup did not finish loading');
  evidence.stage='prior setup preload ready';
  requireThat(await inspector.evaluate("globalThis.__cmoInstalledQA.window().webContents.executeJavaScript(\"document.readyState==='complete'&&typeof window.comicDesktop?.saveSetup==='function'&&Boolean(document.querySelector('#setupForm'))\")"),'Actual setup DOM/preload not ready');
  const keys=Object.fromEntries(['COMICVINE_API_KEY','METRON_API_TOKEN','GOOGLE_BOOKS_API_KEY','BRAVE_SEARCH_API_KEY'].map((name,i)=>[name,'synthetic-sandbox-key-'+i]));
  evidence.stage='prior saveSetup';const saved=await inspector.evaluate('globalThis.__cmoInstalledQA.setup('+JSON.stringify(prepared.library)+','+JSON.stringify(keys)+')');
  requireThat(saved.configured===true,'Real first-run setup failed');evidence.setupSave={configured:saved.configured,savedKeys:saved.saved_keys};
  evidence.stage='prior openDashboard request';requireThat(await requestDashboardTransition(inspector)==='actual setupOpenDashboard requested once','Actual dashboard request was not submitted');
  evidence.stage='prior dashboard frame ready';
  evidence.dashboardTransition=await until(()=>inspector.evaluate('({...globalThis.__cmoInstalledQA.renderer(),navigation:globalThis.__cmoInstalledQA.dashboardTransition})'),value=>{
    evidence.lastDashboardRenderer=value;requireThat(!value.failure,'Prior dashboard renderer failed: '+JSON.stringify(value.failure));return dashboardFrameReady(value);
  },'Actual dashboard navigation did not finish');
  evidence.stage='prior dashboard preload ready';
  requireThat(await inspector.evaluate("globalThis.__cmoInstalledQA.window().webContents.executeJavaScript(\"document.readyState==='complete'&&typeof window.comicDesktop?.onState==='function'&&typeof window.comicDesktop?.action==='function'\")"),'Actual dashboard DOM/preload not ready');
  evidence.stage='prior service ready';
  await until(()=>shellState(inspector),s=>s.service==='ready','Prior service did not become ready');
  evidence.stage='prior remembered bounds';
  evidence.geometryRequest=await inspector.evaluate(REQUEST_WINDOW_GEOMETRY_EXPRESSION);
  evidence.geometryAfterRequest=await settledRememberedGeometry(budget=>inspector.evaluate(WINDOW_GEOMETRY_EXPRESSION,true,budget),{deadlineEpochMs:Math.min(deadline,Date.now()+5000),notBeforeEpochMs:evidence.geometryRequest.requestedAt,onSample:value=>{evidence.lastPriorGeometry=value;}});
  evidence.stage='prior real processing';
  const working=await until(()=>Promise.resolve(fixture('snapshot')),s=>s.taggedFixtures>0&&s.pendingFixtures>0,'No actual processing with remaining queue');
  evidence.realProcessing={taggedFixtures:working.taggedFixtures,pendingFixtures:working.pendingFixtures,processes:installedProcesses()};
  requireThat(evidence.realProcessing.processes.some(p=>String(p.CommandLine).includes('worker')),'No real installed worker observed');
  requireThat(fs.existsSync(prepared.conversionArchive.replace(/\.cb7$/,'.cbz'))&&!fs.existsSync(prepared.conversionArchive),'Real bundled conversion did not complete');
  if(mode==='paused')await inspector.evaluate('globalThis.__cmoInstalledQA.pause()',false);
  const beforeControl=await until(()=>shellState(inspector),s=>s.control?.user_requested===(mode==='paused')&&(mode!=='paused'||s.control.phase==='paused'),'Wrong initial user-pause state');
  evidence.priorShell=beforeControl;
  evidence.stage='prior real update check/download';
  await action(inspector,'check');await until(()=>shellState(inspector),s=>['available','ready'].includes(s.update.phase)&&s.update.version===plan.version,'Update not offered by actual updater');
  await action(inspector,'download');await until(()=>shellState(inspector),s=>s.update.phase==='ready','Actual installer download did not verify');
  await action(inspector,'confirm');requireThat((await shellState(inspector)).update.phase==='confirm','Actual install confirmation absent');
  evidence.before=fixture('snapshot');
  requireThat(evidence.before.credentialsMatchExpected&&Object.values(evidence.before.credentialPresence).length===4&&Object.values(evidence.before.credentialPresence).every(Boolean),'The real four synthetic credentials did not decrypt/persist');
  evidence.stage='prior exact persisted geometry before replacement';
  evidence.priorGeometry=await settledRememberedGeometry(budget=>inspector.evaluate(WINDOW_GEOMETRY_EXPRESSION,true,budget),{deadlineEpochMs:Math.min(deadline,Date.now()+5000),notBeforeEpochMs:evidence.geometryRequest.requestedAt,onSample:value=>{evidence.lastPriorGeometry=value;}});evidence.priorBounds=evidence.priorGeometry.normal;
  const triggered=await inspector.evaluate("globalThis.__cmoInstalledQA.action('install');'actual install action requested'",false);evidence.triggered=triggered;verifiedInspector=null;inspector.close();inspector=null;
  evidence.stage='real installer handoff/relaunch';
  const priorExit=await old.exit;requireThat(priorExit.code===0&&priorExit.signal===null,'Prior app did not exit naturally');evidence.priorExit=priorExit;
  const observer=JSON.parse(fs.readFileSync(env.CMO_QA_OBSERVER));evidence.oldObserver=observer;
  const before=observer.events.find(x=>x.kind==='before-installer-helper');const accepted=observer.events.find(x=>x.kind==='installer-receipt')?.receipt;
  requireThat(before?.engines?.length&&before.engines.every(e=>e.exit?.code===0)&&accepted?.started&&accepted.accepted&&accepted.installer_pid>0,'Actual old-engine/install handoff not proved');
  const next=await until(()=>Promise.resolve(installedProcesses()),a=>a.some(p=>path.resolve(p.ExecutablePath).toLowerCase()===exe.toLowerCase()&&!String(p.CommandLine).includes('--type=')&&p.ProcessId!==old.child.pid),'Actual installer did not relaunch next app');
  const nextMain=next.find(p=>path.resolve(p.ExecutablePath).toLowerCase()===exe.toLowerCase()&&!String(p.CommandLine).includes('--type=')&&p.ProcessId!==old.child.pid);
  nextHandle=holdExact(nextMain.ProcessId);requireThat(wait(nextHandle,0)===258,'Relaunched app exited before observation');
  const expectedExe=plan.packageFiles.find(item=>item.path==='ComicMetadata.exe');requireThat(expectedExe&&digest(fs.readFileSync(exe))===expectedExe.sha256,'Relaunched executable does not match final package');
  verifiedInspector=null;process._debugProcess(nextMain.ProcessId);inspector=await Inspector.connect(9229);traceInspector(inspector,'next');
  evidence.stage='next readonly process/resources/version identity';
  const actual=await inspectInstalledRuntime(inspector,{pid:nextMain.ProcessId,exe,resources:path.join(install,'resources'),version:plan.version,local:process.env.LOCALAPPDATA});verifiedInspector=inspector;evidence.relaunch=actual;
  evidence.stage='next verified observer/service/state';
  await inspector.evaluate(installedObserverExpression(feedURL,feedToken));
  const afterShell=await until(()=>shellState(inspector),s=>s.service==='ready'&&s.loadedShellVersion===plan.version&&s.control?.user_requested===(mode==='paused')&&(mode!=='paused'||s.control.phase==='paused'),'Next app did not restore actual service/user pause');evidence.nextShell=afterShell;
  evidence.nextRegistration=registration(plan.version);
  evidence.nextProcesses=installedProcesses();requireThat(evidence.nextProcesses.filter(p=>String(p.CommandLine).includes('engine_host.py')).length===1,'Next version does not have exactly one actual engine host');
  evidence.stage='next exact settled/restored geometry';
  evidence.nextGeometry=await settledRememberedGeometry(budget=>inspector.evaluate(WINDOW_GEOMETRY_EXPRESSION,true,budget),{deadlineEpochMs:Math.min(deadline,Date.now()+5000),onSample:value=>{evidence.lastNextGeometry=value;}});evidence.nextBounds=evidence.nextGeometry.normal;assertRememberedGeometryRestored(evidence.priorGeometry,evidence.nextGeometry);
  evidence.after=fixture('snapshot');
  requireThat(evidence.after.credentialsMatchExpected&&Object.values(evidence.after.credentialPresence).every(Boolean),'The updated app did not preserve/decrypt the four real synthetic credentials');
  for(const key of ['configSha256','legacySha256','credentialSha256','credentialFileSha256','manual','manualArchiveSha256','manualLedger','recoverySha256'])
    requireThat(JSON.stringify(evidence.before[key])===JSON.stringify(evidence.after[key]),'State preservation failed: '+key);
  const afterHistory=new Map(evidence.after.history.map(row=>[row[0],JSON.stringify(row)]));
  requireThat(evidence.before.history.every(row=>afterHistory.get(row[0])===JSON.stringify(row)),'Historical records were lost or changed');
  requireThat(evidence.after.userPaused===(mode==='paused'),'Durable user-pause choice changed');
  for(const item of plan.packageFiles){const file=member(install,item.path);requireThat(fs.statSync(file).size===item.size&&digest(fs.readFileSync(file))===item.sha256,'Installed next-version byte drift: '+item.path);}
  if(mode==='paused'){
    requireThat(!evidence.after.history.some(row=>String(row[1]).includes('Sandbox QA Fixture')&&Number(row[4])*1000>=Number(nextMain.CreatedMs)),'Paused app wrote a fixture before explicit Resume');
    evidence.resumeRequested=await inspector.evaluate("globalThis.__cmoInstalledQA.window().webContents.executeJavaScript(\"(()=>{const b=document.querySelector('#pauseControl');if(!b||b.disabled||!/Resume/.test(b.textContent))throw Error('Real rendered Resume unavailable');b.click();return 'actual rendered Resume clicked'})()\")",true);
    await until(()=>shellState(inspector),s=>s.control?.user_requested===false&&s.control.phase!=='paused','Actual Resume did not enable processing');
  }
  evidence.postUpdateActivity=await until(()=>Promise.resolve(fixture('snapshot')),s=>s.history.some(row=>String(row[1]).includes('Sandbox QA Fixture')&&Number(row[4])*1000>=Number(nextMain.CreatedMs)),'No actual post-update fixture processing');
  await inspector.evaluate("globalThis.__cmoInstalledQA.action('quit');'actual packaged Quit requested'",false);verifiedInspector=null;inspector.close();inspector=null;
  await until(()=>Promise.resolve(wait(nextHandle,0)),v=>v===0,'Actual next Quit did not exit');const exit=Buffer.alloc(4);requireThat(code(nextHandle,exit)&&exit.readUInt32LE()===0,'Next app did not quit naturally with0');
  evidence.remaining=await until(()=>Promise.resolve(installedProcesses()),a=>a.length===0,'Installed/capsule processes remain');
  evidence.feed=feedCalls;evidence.model=modelCalls;evidence.pass=true;
} catch(error){evidence.error=String(error.stack||error);evidence.inspectorTrace=inspector?.history;evidence.oldDiagnostics=old?.diagnostics();}
finally {
  if(!evidence.pass&&inspector){
    evidence.errorCleanup={started:Date.now(),requested:false};
    try{
      Object.assign(evidence.errorCleanup,await requestVerifiedInspectorQuit(inspector,verifiedInspector));
      if(evidence.errorCleanup.requested){const graceEnd=Math.min(Date.now()+5000,deadline);while(Date.now()<graceEnd&&((old&&old.child.exitCode===null)||(nextHandle&&wait(nextHandle,0)===258)))await sleep(100);}
    }catch(error){evidence.errorCleanup.error=String(error);}
    evidence.errorCleanup.finished=Date.now();evidence.errorCleanup.oldExitCode=old?.child.exitCode;
  }
  verifiedInspector=null;try{inspector?.close();}catch{}if(nextHandle)close(nextHandle);feed.close();feed.closeAllConnections();model.close();model.closeAllConnections();
  evidence.finished=Date.now();writeJson(output+'/update-result.json',evidence);
}
process.exitCode=evidence.pass?0:1;
