'use strict';
const {spawn}=require('node:child_process');
function launchInstaller({python,helper,path,size,sha512,parent_pid,install_dir},spawnChild=spawn){
  return new Promise((resolve,reject)=>{
    let child,settled=false,bytes=0,line='';
    const failure=(code,started,receipt)=>Object.assign(Error('Installer startup could not be confirmed'),{code,installerStarted:started,installerReceipt:receipt||null});
    const finish=(error,receipt)=>{if(settled)return;settled=true;clearTimeout(timer);if(receipt?.accepted){child.unref();child.stdout?.unref?.();child.stderr?.unref?.();resolve(receipt);}else reject(error);};
    const timer=setTimeout(()=>finish(failure('INSTALLER_OUTCOME_UNKNOWN',null)),12000);
    try{child=spawnChild(python,['-I','-S','-B',helper],{windowsHide:true,stdio:['pipe','pipe','pipe'],detached:false});}
    catch{finish(failure('INSTALLER_NOT_STARTED',false));return;}
    child.once('error',()=>finish(failure('INSTALLER_NOT_STARTED',false)));
    child.once('exit',()=>{if(!settled)finish(failure('INSTALLER_OUTCOME_UNKNOWN',null));});
    child.stderr.on('data',()=>{}); // Native helper emits no sensitive diagnostic text.
    child.stdout.on('data',chunk=>{if(settled)return;bytes+=chunk.length;if(bytes>4096){finish(failure('INSTALLER_OUTCOME_UNKNOWN',null));return;}line+=chunk.toString('utf8');const end=line.indexOf('\n');if(end<0)return;
      let receipt;try{receipt=JSON.parse(line.slice(0,end));}catch{finish(failure('INSTALLER_OUTCOME_UNKNOWN',null));return;}
      if(typeof receipt.started!=='boolean'||typeof receipt.accepted!=='boolean'||typeof receipt.phase!=='string'){finish(failure('INSTALLER_OUTCOME_UNKNOWN',null));return;}
      if(receipt.accepted&&receipt.started&&receipt.phase==='started'&&Number.isSafeInteger(receipt.installer_pid)&&receipt.installer_pid>0)finish(null,receipt);
      else if(!receipt.accepted)finish(failure(receipt.started?'INSTALLER_OUTCOME_UNKNOWN':'INSTALLER_NOT_STARTED',receipt.started,receipt));
      else finish(failure('INSTALLER_OUTCOME_UNKNOWN',null));
    });
    child.stdin.on('error',()=>finish(failure('INSTALLER_OUTCOME_UNKNOWN',null)));
    const request={path,size,sha512,parent_pid,...(install_dir?{install_dir}:{})};child.stdin.end(JSON.stringify(request)+'\n');
  });
}
module.exports={launchInstaller};
