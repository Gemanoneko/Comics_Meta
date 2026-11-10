import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {test} from 'node:test';
import {digest,inventory,verifyInventory,member,parseComputeList,wsConfig,safeGuestIdentity} from './common.mjs';
test('input membership validation is order-independent but refuses tamper, extra files and traversal',()=>{
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'cmo-manifest-control-'));
  try{
    fs.writeFileSync(path.join(root,'a'),'real control');
    const records=inventory(root);
    verifyInventory(root,records.map(x=>({sha256:x.sha256,size:x.size,path:x.path})));
    assert.throws(()=>member(root,'../other'));assert.throws(()=>member(root,'C:/other'));assert.throws(()=>member(root,'x\\other'));
    fs.writeFileSync(path.join(root,'a'),'wrong control');assert.throws(()=>verifyInventory(root,records));
    fs.writeFileSync(path.join(root,'a'),'real control');fs.writeFileSync(path.join(root,'extra'),'extra');assert.throws(()=>verifyInventory(root,records));
  }finally{fs.rmSync(root,{recursive:true});}
});
test('compute parsing preserves template and unique IDs without stop semantics',()=>{
  const rows=parseComputeList('a90a3ca5-cf2c-4aa3-8da2-e81e62eb3a71\n    VM, SavedAsTemplate, A90A3CA5-CF2C-4AA3-8DA2-E81E62EB3A71, CmService\n');
  assert.equal(rows.length,1);assert.match(rows[0].description,/SavedAsTemplate/);
});
test('guest identity rejects the real host/user and wrong mapped path',()=>{
  assert.equal(safeGuestIdentity({scriptRoot:'C:/CMOInput',user:'AnGeLZzZ',profile:'C:/Users/AnGeLZzZ',computer:'ILLUMINATI',model:'Virtual Machine'},'ILLUMINATI'),false);
  assert.equal(safeGuestIdentity({scriptRoot:'C:/wrong',user:'WDAGUtilityAccount',profile:'C:/Users/WDAGUtilityAccount',computer:'different',model:'Virtual Machine'},'ILLUMINATI'),false);
  const guest={scriptRoot:'C:/CMOInput',user:'WDAGUtilityAccount',tokenName:'GUEST\\WDAGUtilityAccount',tokenSid:'S-1-5-21-11-22-33-504',profile:'C:\\Users\\WDAGUtilityAccount',computer:'GUEST',model:'Virtual Machine'};
  assert.equal(safeGuestIdentity(guest,'ILLUMINATI'),process.platform==='win32');
  assert.equal(safeGuestIdentity({...guest,tokenName:'HOST\\AnGeLZzZ'},'ILLUMINATI'),false);
  assert.equal(safeGuestIdentity({...guest,computer:'ILLUMINATI'},'ILLUMINATI'),false);
});
test('Sandbox configuration has only two maps, disabled host integrations and exact guest-only entrypoint',()=>{
  const xml=wsConfig('C:\\own\\input','C:\\own\\output','processing','a'.repeat(32),'b'.repeat(64),'c'.repeat(64));
  assert.equal((xml.match(/<MappedFolder>/g)||[]).length,2);assert.match(xml,/<ReadOnly>true<\/ReadOnly>/);
  for(const feature of ['vGPU','Networking','AudioInput','VideoInput','PrinterRedirection','ClipboardRedirection'])assert.ok(xml.includes('<'+feature+'>Disable</'+feature+'>'));
  assert.match(xml,/C:\\CMOInput\\node\\node.exe C:\\CMOInput\\guest-entry.mjs/);assert.doesNotMatch(xml,/shutdown/i);
  assert.throws(()=>wsConfig('x','y','other','a'.repeat(32),'b'.repeat(64),'c'.repeat(64)));
  assert.equal(digest(Buffer.from('abc')),'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
});
