import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {validateGuestPhase} from './qa-receipt.mjs';
test('missing real guest evidence cannot produce install/update acceptance',()=>{
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'cmo-qa-receipt-'));
  try{assert.throws(()=>validateGuestPhase({root,mode:'processing',plan:{},manifestSha256:'a'.repeat(64)}));}
  finally{fs.rmSync(root,{recursive:true});}
});
test('a synthetic pass flag without real ownership proof is refused',()=>{
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'cmo-qa-receipt-'));
  try{
    const out=path.join(root,'output-processing');fs.mkdirSync(out);
    for(const name of ['host-processing-owned.json','host-session-processing.json','host-processing-started.json'])fs.writeFileSync(path.join(root,name),JSON.stringify({pass:true}));
    for(const name of ['guest-owned.json','guest-wrapper.json','update-result.json','session-request.json'])fs.writeFileSync(path.join(out,name),JSON.stringify({pass:true}));
    assert.throws(()=>validateGuestPhase({root,mode:'processing',plan:{},manifestSha256:'a'.repeat(64)}),/owner/);
  }finally{fs.rmSync(root,{recursive:true});}
});
