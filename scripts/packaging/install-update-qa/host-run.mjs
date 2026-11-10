// One reviewed, explicitly approved classic Sandbox window per invocation.
import fs from 'node:fs';
import path from 'node:path';
import {performance} from 'node:perf_hooks';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {digest,verifyInventory,requireThat,writeJson,wsConfig} from './common.mjs';
const started=performance.now(),deadline=started+600000;
const input=path.dirname(fileURLToPath(import.meta.url)),mode=process.argv[2],expected=process.argv[3];
requireThat(process.argv.length===4&&['processing','paused'].includes(mode)&&/^[a-f0-9]{64}$/.test(expected),'Exact reviewed host phase/manifest required');
const raw=fs.readFileSync(input+'/input-manifest.json');requireThat(digest(raw)===expected,'Reviewed input manifest differs');const manifest=JSON.parse(raw);
verifyInventory(input,manifest.files,{allowManifest:true});const plan=JSON.parse(fs.readFileSync(input+'/plan.json'));
requireThat(path.resolve(plan.inputRoot)===input&&process.env.COMPUTERNAME.toLowerCase()===plan.hostName.toLowerCase(),'Wrong host/staging root');
for(const item of Object.values(plan.hostTools))requireThat(digest(fs.readFileSync(item.path))===item.sha256,'Host OS tool byte drift');
const output=path.join(plan.hostRoot,'output-'+mode);requireThat(fs.readdirSync(output).length===0,'Fresh empty phase output required');
requireThat(!fs.existsSync(path.join(plan.hostRoot,'host-'+mode+'-owned.json'))&&!fs.existsSync(path.join(plan.hostRoot,'host-session-'+mode+'.json')),'Prior invocation retained; no duplicate');
const request={schema:1,mode,nonce:plan.runs[mode].nonce,manifestSha256:expected,sourceHead:plan.sourceHead,
  startedEpochMs:Date.now(),deadlineEpochMs:Date.now()+Math.floor(deadline-performance.now()),config:path.join(plan.hostRoot,mode+'-live.wsb')};
writeJson(path.join(output,'session-request.json'),request);
const sessionSha=digest(fs.readFileSync(path.join(output,'session-request.json')));
fs.writeFileSync(request.config,wsConfig(input,output,mode,request.nonce,expected,sessionSha),{flag:'wx'});
writeJson(path.join(plan.hostRoot,'host-'+mode+'-started.json'),{...request,sessionSha256:sessionSha,configSha256:digest(fs.readFileSync(request.config))});
const remain=Math.floor(deadline-performance.now());requireThat(remain>2000,'Host preflight exhausted original deadline');
const {runOwned}=await import(pathToFileURL(input+'/owner/bounded-check.mjs'));
const temp=path.join(plan.hostRoot,'host-temp-'+mode);fs.mkdirSync(temp);
const env={SystemRoot:'C:\\Windows',WINDIR:'C:\\Windows',ComSpec:'C:\\Windows\\System32\\cmd.exe',PATH:'C:\\Windows\\System32',
  TEMP:temp,TMP:temp,USERPROFILE:process.env.USERPROFILE,USERNAME:process.env.USERNAME,APPDATA:process.env.APPDATA,LOCALAPPDATA:process.env.LOCALAPPDATA,COMPUTERNAME:process.env.COMPUTERNAME};
const owned=await runOwned(process.execPath,[input+'/host-session.mjs',mode,sessionSha],{cwd:plan.hostRoot,env,timeoutMs:remain,maxBytes:2*1024*1024,koffiRoot:input+'/ownership/node_modules/koffi'});
writeJson(path.join(plan.hostRoot,'host-'+mode+'-owned.json'),owned);
requireThat(owned.ok&&owned.closed&&!owned.forced&&!owned.timedOut&&owned.outputComplete&&owned.native?.complete&&owned.native.zero,'Host Sandbox session failed/closure uncertain; no automatic retry');
verifyInventory(input,manifest.files,{allowManifest:true});console.log(JSON.stringify({mode,pass:true,sourceHead:plan.sourceHead,artifact:plan.artifact.sha256}));
