'use strict';
// SOURCE ONLY. No top-level test execution. Later reviewed Job may call this.
const assert=require('node:assert/strict');
const {deflateRawSync}=require('node:zlib');
const {decodeUninstaller,LIMITS}=require('./decoder.cjs');
const signature=Buffer.from('efbeadde4e756c6c736f6674496e7374','hex');
function header(flags,total){const b=Buffer.alloc(28);b.writeUInt32LE(flags,0);signature.copy(b,4);b.writeUInt32LE(total,24);return b;}
function fixture({compressed=false,double=false}={}){
  const stub=Buffer.alloc(0x210);stub.write('MZ');stub.writeUInt32LE(0x80,0x3c);
  stub.writeUInt32LE(0x4550,0x80);stub.writeUInt16LE(0x14c,0x84);stub.writeUInt16LE(1,0x86);
  stub.writeUInt16LE(0xe0,0x94);stub.writeUInt16LE(0x10b,0x98);stub.writeUInt32LE(0x200,0x98+60);
  stub.write('.text',0x178);stub.writeUInt32LE(16,0x178+16);stub.writeUInt32LE(0x200,0x178+20);
  stub.fill(0x6a,0x200);
  const inner=Buffer.concat([header(1,32),Buffer.from('89abcdef','hex')]);
  const payload=compressed?deflateRawSync(inner):inner;
  const word=Buffer.alloc(4);word.writeUInt32LE((payload.length+(compressed?0x80000000:0))>>>0);
  const block=Buffer.concat([word,payload]);
  const body=Buffer.concat([block,...(double?[block]:[]),Buffer.from('11223344','hex')]);
  return {input:Buffer.concat([stub,header(0,28+body.length),body]),stub,inner};
}
function runSynthetic(){
  let passed=0;
  for(const compressed of [false,true]){
    const f=fixture({compressed}),original=Buffer.from(f.input);
    const result=decodeUninstaller(f.input);
    assert.deepEqual(result.bytes,Buffer.concat([f.stub,f.inner]));
    assert.deepEqual(f.input,original);assert.equal(result.receipt.crcVerified,false);
    assert.equal(result.receipt.outerOpaqueTrailerHex,'11223344');passed++;
  }
  const reject=mutate=>{const f=fixture();mutate(f.input);assert.throws(()=>decodeUninstaller(f.input));passed++;};
  reject(b=>b[0]=0);reject(b=>b.writeUInt32LE(0xfffffff0,0x3c));
  reject(b=>b.writeUInt16LE(LIMITS.sections+1,0x86));
  reject(b=>b.writeUInt32LE(0x100,0x178+20));
  reject(b=>b.writeUInt32LE(16,0x210));
  reject(b=>b.writeUInt32LE(1,0x210));
  reject(b=>b.writeUInt32LE(0x7fffffff,0x210+28));
  reject(b=>b.writeUInt32LE(0,0x210+28+4));
  reject(b=>b.writeUInt32LE(31,0x210+28+4+24));
  assert.throws(()=>decodeUninstaller(fixture({double:true}).input));passed++;
  assert.throws(()=>decodeUninstaller(Buffer.alloc(LIMITS.input+1)));passed++;
  return {scope:'Synthetic pure decoder component cases; no compiled/installed proof',passed};
}
module.exports={runSynthetic};
