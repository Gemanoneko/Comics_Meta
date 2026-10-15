'use strict';
const path=require('node:path');
const {createHash}=require('node:crypto');
const {decodeUninstaller,LIMITS}=require('./decoder.cjs');
const PINS=Object.freeze({version:'26.15.3',
  nsisUtil:'fca86cb65c9a9e63744204379cad053ad14b774bff4f33eafec797227dd0dbf1',
  NsisTarget:'43a6cb5c64b0f0f889bc9dd9d66fa351e5294cd6a7baedfa834c0067fd123372'});
const sha256=b=>createHash('sha256').update(b).digest('hex');
function required(value,message){if(!value)throw new Error('Safe NSIS entry: '+message);}
// Caller installs on ONE actual target instance in its owned pinned builder.
// Adapters are mandatory native-held I/O/signing and loaded-module boundaries;
// this source does not replace those boundaries with ordinary Node fs calls.
function installForTarget(target,context){
  required(process.platform==='win32'&&process.arch==='x64','Windows x64 only');
  required(context&&context.version===PINS.version,'pinned builder version');
  required(context.NsisTarget&&target.constructor===context.NsisTarget,'exact target class');
  for(const key of ['nsisUtil','NsisTarget']){
    required(Buffer.isBuffer(context.sourceBytes?.[key])&&sha256(context.sourceBytes[key])===PINS[key],key+' source identity');
  }
  required(typeof context.assertLoadedSources==='function','native-held loader binding required');
  // Must assert actual loaded class/module cache paths correspond to these exact
  // retained sources and pinned full dependency closure. Raw source hashes alone
  // do not authenticate an arbitrary caller-supplied JavaScript function/class.
  required(context.assertLoadedSources({target,NsisTarget:context.NsisTarget,pins:PINS})===true,
    'synchronous verified loaded source binding');
  required(typeof context.checkBudget==='function','original budget callback');
  required(Number.isInteger(context.x64Arch),'pinned Arch.x64 enum');
  const io=context.io;
  for(const name of ['assertOwnedPaths','readTemplateHeld','readCompiledHeld','referenceDecode','writeExclusiveAndSeal','signAndSeal'])
    required(typeof io?.[name]==='function',name+' adapter required');
  required(typeof context.templatesDir==='string'&&path.isAbsolute(context.templatesDir),'pinned template root');
  const own=Object.getOwnPropertyDescriptor(target,'computeScriptAndSignUninstaller');
  required(!own,'target must use original prototype method');
  const original=context.NsisTarget.prototype.computeScriptAndSignUninstaller;
  required(typeof original==='function'&&target.computeScriptAndSignUninstaller===original,'original pinned method binding');
  async function safeMethod(defines,commands,installerPath,sharedHeader,archs){
    required(this===target,'single target binding'); context.checkBudget();
    required(process.platform==='win32'&&process.arch==='x64','Windows x64 only');
    required(archs instanceof Map&&archs.size===1&&archs.has(context.x64Arch),'exact x64 target map');
    required(typeof installerPath==='string'&&path.isAbsolute(installerPath),'absolute compiler output');
    const packager=this.packager;
    const customScriptPath=await packager.getResource(this.options.script,'installer.nsi');
    const templatePath=customScriptPath||path.join(context.templatesDir,'installer.nsi');
    const template=await io.readTemplateHeld(templatePath,4*1024**2);
    required(Buffer.isBuffer(template.bytes)&&template.bytes.length<=4*1024**2&&template.identity!=null,'held template bytes/identity');
    const script=template.bytes.toString('utf8');
    if(customScriptPath!=null){
      context.log?.({reason:'custom NSIS script is used'},'uninstaller is not signed by electron-builder');
      return {script,isCustomScript:true};
    }
    const uninstallerPath=path.join(this.outDir,`${path.basename(installerPath,'exe')}__uninstaller.exe`);
    await io.assertOwnedPaths({installerPath,uninstallerPath,outDir:this.outDir,templatePath});
    defines.BUILD_UNINSTALLER=null;
    defines.UNINSTALLER_OUT_FILE=uninstallerPath;
    context.checkBudget();
    // Exactly the upstream pinned script/defines/makensis flow. This authorized
    // compiler operation remains in the caller's original native Job graph.
    await this.executeMakensis(defines,commands,sharedHeader+(await this.computeFinalScript(script,false,archs)));
    context.checkBudget();
    const compiled=await io.readCompiledHeld(installerPath,LIMITS.input);
    required(Buffer.isBuffer(compiled.bytes)&&compiled.bytes.length<=LIMITS.input&&compiled.identity!=null,'held compiler output bytes/identity');
    const decoded=decodeUninstaller(compiled.bytes,context.checkBudget);
    // Required actual compiled comparison, with the exact pinned upstream PURE
    // reader on this SAME parent-held input. Never a bootstrap/VM fallback.
    const reference=await io.referenceDecode(installerPath,decoded.bytes);
    required(reference&&reference.equal===true&&reference.reference?.sha256===decoded.receipt.outputSha256,
      'actual pinned upstream pure-reader byte equivalence');
    const staged=await io.writeExclusiveAndSeal(uninstallerPath,decoded.bytes);
    required(staged&&staged.identity!=null&&staged.size===decoded.bytes.length&&staged.sha256===decoded.receipt.outputSha256,
      'exclusive output strong bytes receipt');
    // The adapter alone controls writer/reader sharing transitions for optional
    // legitimate signing, then reacquires exact signed bytes/ID as a strong hold.
    // It MUST call this closure exactly once and may never execute the bootstrap.
    let signCalls=0;
    const signed=await io.signAndSeal(uninstallerPath,async()=>{
      required(++signCalls===1,'signIf called once');context.checkBudget();
      return packager.signIf(uninstallerPath);
    });
    required(signCalls===1&&signed&&signed.identity!=null&&Number.isSafeInteger(signed.size)&&signed.size>0&&
      typeof signed.sha256==='string'&&/^[0-9a-f]{64}$/.test(signed.sha256),'signed output strong receipt');
    context.checkBudget();
    context.onReceipt?.({decoder:decoded.receipt,reference,compiledIdentity:compiled.identity,
      staged,signed,bootstrapExecuted:false});
    delete defines.BUILD_UNINSTALLER;
    defines.UNINSTALLER_OUT_FILE=uninstallerPath;
    return {script,isCustomScript:false};
  }
  Object.defineProperty(target,'computeScriptAndSignUninstaller',{value:safeMethod,writable:false,configurable:true});
  return ()=>{
    required(target.computeScriptAndSignUninstaller===safeMethod,'override identity changed');
    delete target.computeScriptAndSignUninstaller;
  };
}
module.exports={installForTarget,PINS};
