'use strict';
// Source only until the complete parent-held compiler graph is reviewed.
const fs=require('node:fs/promises');
const path=require('node:path');
const {createHash}=require('node:crypto');
const {installForTarget,PINS}=require('./safe-entry.cjs');
const {installFinalCompiler}=require('./client.cjs');
const hash=b=>createHash('sha256').update(b).digest('hex');
const functionSource=Function.prototype.toString;
const need=(value,message)=>{if(!value)throw Error('Pinned NSIS route: '+message);};
function classBytes(raw,name,exportLine){
  const text=raw.toString('utf8'),start=text.indexOf('class '+name+' '),end=text.indexOf(exportLine,start);
  need(start>=0&&end>start&&text.indexOf('class '+name+' ',start+1)<0,'unique class source '+name);
  return text.slice(start,end).trim();
}
async function prepare(root,checkBudget){
  need(process.platform==='win32'&&process.arch==='x64'&&path.isAbsolute(root),'owned Windows x64 root');
  need(typeof checkBudget==='function','original budget');checkBudget();
  const nodeModules=path.join(root,'node_modules');
  const paths={NsisTarget:path.join(nodeModules,'app-builder-lib','out','targets','nsis','NsisTarget.js'),
    nsisUtil:path.join(nodeModules,'app-builder-lib','out','targets','nsis','nsisUtil.js')};
  const sourceBytes={};
  for(const key of Object.keys(paths)){
    checkBudget();const b=await fs.readFile(paths[key]);
    need(b.length<=1024**2&&hash(b)===PINS[key],'actual held module source '+key);sourceBytes[key]=b;
    need(require.resolve(paths[key])===paths[key],'resolved module path '+key);
  }
  const actualPackage=JSON.parse(await fs.readFile(path.join(nodeModules,'app-builder-lib','package.json'),'utf8'));
  need(actualPackage.version===PINS.version,'actual builder package version');
  const modules={NsisTarget:require(paths.NsisTarget),nsisUtil:require(paths.nsisUtil)};
  const Original=modules.NsisTarget.NsisTarget,Reader=modules.nsisUtil.UninstallerReader;
  const templateRoot=path.join(nodeModules,'app-builder-lib','templates','nsis');
  need(typeof Original==='function'&&typeof Reader==='function','actual class exports');
  need(functionSource.call(Original)===classBytes(sourceBytes.NsisTarget,'NsisTarget','exports.NsisTarget = NsisTarget;'),'actual target class/source binding');
  need(functionSource.call(Reader)===classBytes(sourceBytes.nsisUtil,'UninstallerReader','exports.UninstallerReader = UninstallerReader;'),'actual reader class/source binding');
  need(path.resolve(modules.nsisUtil.nsisTemplatesDir)===templateRoot,'actual immutable template root');
  function boundModule(key){
    const cache=require.cache[paths[key]];
    return cache&&cache.loaded&&cache.filename===paths[key]&&cache.exports===modules[key];
  }
  function assertReader(reader,pin){
    return boundModule('nsisUtil')&&reader===Reader&&modules.nsisUtil.UninstallerReader===Reader&&
      pin===PINS.nsisUtil&&functionSource.call(Reader)===classBytes(sourceBytes.nsisUtil,'UninstallerReader','exports.UninstallerReader = UninstallerReader;');
  }
  need(boundModule('NsisTarget')&&assertReader(Reader,PINS.nsisUtil),'loaded module cache binding');
  let installed=false,constructed=0;const restorers=[],receipts=[];
  return {
    reference:{reader:Reader,assertBound:assertReader},
    install(io,x64Arch){
      checkBudget();need(!installed&&Number.isInteger(x64Arch),'one route installation');
      installed=true;
      need(boundModule('NsisTarget')&&modules.NsisTarget.NsisTarget===Original,'original sole target export');
      const proxy=new Proxy(Original,{construct(Target,args){
        checkBudget();need(Target===Original&&++constructed===1&&args[2]==='nsis','one exact NSIS target');
        const target=Reflect.construct(Original,args,Original);
        need(Object.getPrototypeOf(target)===Original.prototype&&target.constructor===Original,'exact target instance');
        need(target.options.script==null,'only pinned default template graph');
        const assertLoadedSources=({target:actual,NsisTarget,pins})=>
          actual===target&&NsisTarget===Original&&pins===PINS&&boundModule('NsisTarget')&&
          modules.NsisTarget.NsisTarget===proxy&&assertReader(Reader,PINS.nsisUtil)&&
          functionSource.call(Original)===classBytes(sourceBytes.NsisTarget,'NsisTarget','exports.NsisTarget = NsisTarget;');
        const restoreSafe=installForTarget(target,{version:PINS.version,NsisTarget:Original,sourceBytes,
          assertLoadedSources,templatesDir:templateRoot,x64Arch,io,checkBudget,
          onReceipt:receipt=>{need(receipts.length===0&&receipt.bootstrapExecuted===false,'one pure extraction');receipts.push(receipt);}});
        const restoreCompiler=installFinalCompiler(target,io);
        restorers.push(()=>{restoreCompiler();restoreSafe();});
        return target;
      }});
      modules.NsisTarget.NsisTarget=proxy;
      need(modules.NsisTarget.NsisTarget===proxy,'installed export binding');
      return {
        receipt(){need(constructed===1&&receipts.length===1,'completed real pure-extraction flow');return {schema:1,constructed,receipts,bootstrapExecuted:false,sourcePins:PINS};},
        restore(){
          need(modules.NsisTarget.NsisTarget===proxy,'route export changed');
          for(const restore of restorers.reverse())restore();
          modules.NsisTarget.NsisTarget=Original;
        }
      };
    }
  };
}
module.exports={prepare};
