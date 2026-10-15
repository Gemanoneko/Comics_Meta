'use strict';
// SOURCE ONLY: fixed parent-file RPC, no Koffi, process, network or service.
const fs=require('node:fs/promises');
const path=require('node:path');
const {createHash}=require('node:crypto');
const sha256=b=>createHash('sha256').update(b).digest('hex');
function need(value,message){if(!value)throw new Error('NSIS held I/O: '+message);}
function createIo(configBytes,configSha256,checkBudget,reference){
  need(Buffer.isBuffer(configBytes)&&configBytes.length<=4096&&sha256(configBytes)===configSha256,'pinned configuration bytes');
  need(typeof checkBudget==='function','original caller budget');
  need(process.platform==='win32'&&process.arch==='x64','Windows x64 RPC client');
  need(reference&&typeof reference.reader?.exec==='function'&&typeof reference.assertBound==='function'&&
    reference.assertBound(reference.reader,'fca86cb65c9a9e63744204379cad053ad14b774bff4f33eafec797227dd0dbf1')===true,
    'actual pinned pure upstream reader source/module binding');
  const c=JSON.parse(configBytes.toString('utf8'));
  const keys=['schema','jobRoot','rpcRoot','outDir','installer','uninstaller','template','templateSha256','nonce','deadlineUnixMs','allowSignerReplacement','limits'];
  need(Object.keys(c).sort().join('|')===keys.sort().join('|')&&c.schema===1,'configuration schema');
  need(/^[0-9a-f]{64}$/.test(c.nonce)&&/^[0-9a-f]{64}$/.test(c.templateSha256),'configuration pins/nonce');
  need(Number.isSafeInteger(c.deadlineUnixMs)&&typeof c.allowSignerReplacement==='boolean','fixed deadline/sign policy');
  const expectedLimits={requests:20,jsonEach:4096,jsonTotal:65536,fileBytes:33554432,rpcBinaryBytes:134217728};
  need(c.limits&&Object.keys(c.limits).sort().join('|')===Object.keys(expectedLimits).sort().join('|')&&
    Object.entries(expectedLimits).every(([key,value])=>c.limits[key]===value),'exact fixed limits');
  for(const key of ['jobRoot','rpcRoot','outDir','installer','uninstaller','template'])need(typeof c[key]==='string'&&path.isAbsolute(c[key]),'absolute fixed '+key);
  need(c.rpcRoot===path.join(c.jobRoot,'nsis-io-rpc-'+c.nonce.slice(0,12))&&
    c.outDir===path.join(c.jobRoot,'source','dist')&&path.dirname(c.installer)===c.outDir&&
    c.uninstaller===path.join(c.outDir,path.basename(c.installer,'exe')+'__uninstaller.exe')&&
    c.template===path.join(c.jobRoot,'source','node_modules','app-builder-lib','templates','nsis','installer.nsi'),'fixed role paths');
  let sequence=0,busy=false,jsonBytes=configBytes.length,signCalls=0;
  const receipts=[];
  let compiledProof=null,referencePayload=null;
  function budget(){checkBudget();need(Date.now()<c.deadlineUnixMs,'original absolute deadline');}
  async function exists(filename){try{await fs.stat(filename);return true;}catch(error){if(error.code==='ENOENT')return false;throw error;}}
  async function writeClosed(filename,bytes){
    budget();const h=await fs.open(filename,'wx');
    try{
      let offset=0;
      while(offset<bytes.length){
        budget();const take=Math.min(65536,bytes.length-offset);
        const result=await h.write(bytes,offset,take,null);
        need(Number.isInteger(result.bytesWritten)&&result.bytesWritten>0&&result.bytesWritten<=take,'exact positive write progress');
        offset+=result.bytesWritten;
      }
      await h.sync();
    }finally{await h.close();}
  }
  async function readBounded(filename,maximum){
    budget();const h=await fs.open(filename,'r');const chunks=[];let total=0;
    try{
      const st=await h.stat();need(st.isFile()&&st.size<=maximum,'regular bounded response/data');
      while(true){
        budget();const buffer=Buffer.alloc(65536),result=await h.read(buffer,0,buffer.length,null);
        if(result.bytesRead===0)break;
        total+=result.bytesRead;need(total<=maximum,'response/data grew beyond bound');
        chunks.push(buffer.subarray(0,result.bytesRead));
      }
    }finally{await h.close();}
    return Buffer.concat(chunks,total);
  }
  async function rpc(operation,args,payload){
    need(!busy,'one serial request');busy=true;
    try{
      budget();need(++sequence<=c.limits.requests,'request limit');
      const id=String(sequence).padStart(4,'0');
      if(payload!==undefined){
        need(Buffer.isBuffer(payload)&&payload.length>0&&payload.length<=c.limits.fileBytes,'payload bound');
        const payloadPath=path.join(c.rpcRoot,id+'.payload.bin');
        await writeClosed(payloadPath,payload);
        args={...args,payload:payloadPath,size:payload.length,sha256:sha256(payload)};
      }
      const request={schema:1,nonce:c.nonce,sequence,deadlineUnixMs:c.deadlineUnixMs,operation,arguments:args};
      const encoded=Buffer.from(JSON.stringify(request)+'\n');
      jsonBytes+=encoded.length;
      need(encoded.length<=c.limits.jsonEach&&jsonBytes<=c.limits.jsonTotal,'JSON request/aggregate bound');
      const temporary=path.join(c.rpcRoot,id+'.request.tmp'),published=path.join(c.rpcRoot,id+'.request.json');
      await writeClosed(temporary,encoded);
      need(!(await exists(published)),'unique published request');
      // Only the CLOSED request is atomically published. Parent native read/share1
      // additionally refuses any still-open request or binary-payload writer.
      await fs.rename(temporary,published);
      const ready=path.join(c.rpcRoot,id+'.response.ready');
      while(!(await exists(ready))){budget();await new Promise(resolve=>setTimeout(resolve,8));}
      const raw=await readBounded(path.join(c.rpcRoot,id+'.response.json'),c.limits.jsonEach);
      jsonBytes+=raw.length;need(jsonBytes<=c.limits.jsonTotal,'response aggregate bound');
      const response=JSON.parse(raw.toString('utf8'));
      need(Object.keys(response).sort().join('|')===['schema','nonce','sequence','deadlineUnixMs','ok','result'].sort().join('|')&&
        response.schema===1&&response.nonce===c.nonce&&response.sequence===sequence&&
        response.deadlineUnixMs===c.deadlineUnixMs&&response.ok===true,'parent response binding');
      receipts.push({operation,sequence,result:response.result});return response.result;
    }finally{busy=false;}
  }
  async function readRole(operation,filename,maximum){
    const proof=await rpc(operation,{path:filename,maximum});
    need(proof.path===filename&&Number.isSafeInteger(proof.size)&&proof.size>=0&&proof.size<=maximum&&
      /^[0-9a-f]{64}$/.test(proof.sha256)&&Array.isArray(proof.identity)&&proof.identity.length===3,'parent native read receipt');
    const bytes=await readBounded(filename,maximum);
    need(bytes.length===proof.size&&sha256(bytes)===proof.sha256,'child reads exact parent strongly-held bytes');
    return {...proof,bytes};
  }
  const io={
    async assertOwnedPaths(value){
      need(value.installerPath===c.installer&&value.uninstallerPath===c.uninstaller&&value.outDir===c.outDir&&value.templatePath===c.template,'owned role binding');
      return rpc('assert-paths',{installer:c.installer,uninstaller:c.uninstaller,outDir:c.outDir,template:c.template});
    },
    async readTemplateHeld(filename,maximum){
      need(filename===c.template&&maximum===4*1024**2,'exact template role');
      return readRole('read-template',filename,maximum);
    },
    async readCompiledHeld(filename,maximum){
      need(filename===c.installer&&maximum===c.limits.fileBytes,'exact compiler-output role');
      const result=await readRole('read-compiled',filename,maximum);compiledProof=result;return result;
    },
    async referenceDecode(filename,decodedBytes){
      need(filename===c.installer&&compiledProof&&Buffer.isBuffer(decodedBytes)&&!referencePayload,
        'one validated compiled reference comparison');
      const transition=await rpc('begin-reference',{path:filename});
      need(transition.input.sha256===compiledProof.sha256&&transition.input.size===compiledProof.size&&
        transition.output===path.join(c.rpcRoot,'upstream-reference.evidence.bin'),'same held input/fresh fixed reference output');
      budget();await reference.reader.exec(filename,transition.output);budget();
      const result=await rpc('end-reference',{path:filename,output:transition.output},decodedBytes);
      need(result.equal===true&&result.reference.sha256===sha256(decodedBytes)&&
        result.reference.size===decodedBytes.length&&result.decodedPayload.sha256===sha256(decodedBytes)&&
        result.decodedPayload.size===decodedBytes.length,'actual full reference bytes comparison receipt');
      referencePayload=result.decodedPayload;return result;
    },
    async writeExclusiveAndSeal(filename,bytes){
      need(filename===c.uninstaller&&referencePayload&&bytes.length===referencePayload.size&&sha256(bytes)===referencePayload.sha256,
        'exact reference-verified decoded-output role');
      const proof=await rpc('stage-decoded',{path:filename,payload:referencePayload.path,
        size:referencePayload.size,sha256:referencePayload.sha256});
      need(proof.path===filename&&proof.size===bytes.length&&proof.sha256===sha256(bytes),'actual staged receipt');return proof;
    },
    async releaseHeld(filename){
      need(filename===c.installer||filename===c.uninstaller,'finite released leaf role');
      return rpc('release-held',{path:filename});
    },
    async signAndSeal(filename,signClosure){
      need(filename===c.uninstaller&&typeof signClosure==='function'&&signCalls===0,'one exact signer closure');
      const transition=await rpc('begin-sign',{path:filename});
      need(/^[0-9a-f]{64}$/.test(transition.token),'parent sign transition token');
      budget();signCalls++;await signClosure();budget();
      const signed=await rpc('end-sign',{path:filename,token:transition.token,signCalls});
      // The final compiler REUSES installerPath immediately after safe method
      // return. Explicitly release only this actual parent's compiled-stub lease.
      await io.releaseHeld(c.installer);
      return signed;
    },
    async beforeFinalCompiler(){return rpc('final-compiler',{path:c.installer});},
    async afterFinalCompilerAndRelease(){
      // Keep signed input protected through final makensis read, then release
      // before upstream Promise.all(signIf(installer), unlink(uninstaller)).
      return io.releaseHeld(c.uninstaller);
    },
    receipt(){return {schema:1,requests:sequence,jsonBytes,signCalls,operations:receipts};}
  };
  return io;
}

function installFinalCompiler(target,io){
  need(target&&!Object.hasOwn(target,'executeMakensis')&&typeof target.executeMakensis==='function','original compiler method');
  const original=target.executeMakensis;let phase=0;
  async function scopedCompiler(...args){
    need(this===target&&phase>=0&&phase<2,'exact serial two-compile instance flow');
    if(phase===0){phase=-1;try{const result=await original.apply(this,args);phase=1;return result;}catch(error){phase=3;throw error;}}
    phase=2;
    await io.beforeFinalCompiler();
    const result=await original.apply(this,args);
    await io.afterFinalCompilerAndRelease();return result;
  }
  Object.defineProperty(target,'executeMakensis',{value:scopedCompiler,writable:false,configurable:true});
  return ()=>{need(target.executeMakensis===scopedCompiler,'compiler wrapper identity');delete target.executeMakensis;};
}
module.exports={createIo,installFinalCompiler};
