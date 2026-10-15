'use strict';
// Preserve upstream collection and stream/exit semantics; avoid shell launchers.
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const equal=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
async function install(root,c,checkBudget){
  const raw=fs.readFileSync(c.npmRuntimeManifest);
  if(crypto.createHash('sha256').update(raw).digest('hex')!==c.npmRuntimeManifestSha256)throw Error('Pinned npm launch manifest changed');
  const m=JSON.parse(raw),cli=path.join(m.root,'bin/npm-cli.js');
  const leaf=m.files.find(x=>x.path==='bin/npm-cli.js');
  if(path.resolve(m.root)!==path.join(path.dirname(process.execPath),'node_modules/npm')||m.version!=='11.20.0'||!leaf||crypto.createHash('sha256').update(fs.readFileSync(cli)).digest('hex')!==leaf.sha256)throw Error('Pinned npm CLI differs');
  const cp=require('node:child_process');
  const cross=require(require.resolve('cross-spawn',{paths:[root]}));
  const collector=require(path.join(root,'node_modules/app-builder-lib/out/node-module-collector/nodeModulesCollector.js'));
  const originalNative=cp.spawn,originalCross=cross.spawn;
  const proto=collector.NodeModulesCollector.prototype,originalStream=proto.streamCollectorCommandToFile;
  const allowed=[['prefix','-w'],['list','-a','--include','prod','--include','optional','--omit','dev','--json','--long','--silent','--loglevel=error'],['config','list']];
  const commands=['npm','npm.cmd',m.wrapper.path];
  const calls=[];
  const isNpm=command=>typeof command==='string'&&(command.toLowerCase()==='npm'||command.toLowerCase()==='npm.cmd'||path.resolve(command).toLowerCase()===path.resolve(m.wrapper.path).toLowerCase());
  proto.streamCollectorCommandToFile=function(command,args,cwd,file){
    if(!isNpm(command)||!allowed.some(x=>equal(x,args)))throw Error('Unsupported package collector command');
    return originalStream.call(this,m.wrapper.path,args,cwd,file);
  };
  function launch(args,options,origin){
    checkBudget();
    if(!allowed.some(x=>equal(x,args))||!options||options.shell||!options.cwd||path.resolve(options.cwd)!==path.resolve(root))throw Error('Unsupported npm collector query or launch scope');
    const env=options.env||process.env;
    for(const key of ['NPM_CONFIG_USERCONFIG','NPM_CONFIG_GLOBALCONFIG','NPM_CONFIG_CACHE','NPM_CONFIG_PREFIX','NPM_CONFIG_OFFLINE','NPM_CONFIG_IGNORE_SCRIPTS'])if(env[key]!==process.env[key]||!env[key])throw Error('Private npm launch environment changed');
    calls.push({origin,args:[...args],executable:process.execPath,cli});
    return originalNative.call(cp,process.execPath,[cli,...args],{...options,shell:false,windowsHide:true,env});
  }
  cross.spawn=function(command,args,options){
    if(isNpm(command))return launch(args,options,'workspace');
    return originalCross.apply(this,arguments);
  };
  cp.spawn=function(command,args,options){
    if(command==='powershell.exe'){
      for(const query of allowed)for(const npm of commands)if(equal(args,collector.buildPowerShellEncodedArgs(npm,query)))return launch(query,options,'collector');
      throw Error('Unrecognized encoded collector command; shell execution forbidden');
    }
    if(isNpm(command))return launch(args,options,'direct');
    return originalNative.apply(this,arguments);
  };
  return {receipt(){return {schema:1,calls:[...calls],shellExecuted:false};},restore(){cp.spawn=originalNative;cross.spawn=originalCross;proto.streamCollectorCommandToFile=originalStream;}};
}
module.exports={install};
